"""Safe read-only integration of the independent knowledge bundle into Golden Dragon.

Source skills remain untrusted reference data. No arbitrary command execution.
The ZIP ships with the app; the verified SQLite member is cached per-user.
"""
import hashlib
import json
import os
import re
import sqlite3
from contextlib import closing
import unicodedata
import threading
import zipfile
from pathlib import Path

import golden_dragon_runtime as knowledge

ROOT = Path(getattr(__import__("sys"), "_MEIPASS", Path(__file__).resolve().parent))
BUNDLE = ROOT / "knowledge" / "golden-dragon-runtime.zip"
if not BUNDLE.exists():
    BUNDLE = Path(__file__).resolve().parent.parent / "knowledge" / "golden-dragon-runtime.zip"
CACHE = Path(os.environ.get("APPDATA", Path.home())) / "GoldenDragon" / "knowledge"
_LOCK = threading.RLock()
_MAX_DB_SIZE = 100 * 1024 * 1024


def verified_database(bundle=None, cache=None):
    """Only extract golden_dragon.sqlite after verifying the signed-in-bundle hashes.

    Integrity hashes detect accidental corruption; they are NOT a signature or
    substitute for trusting the source of the bundled ZIP.
    """
    bundle = Path(bundle or BUNDLE)
    cache = Path(cache or CACHE)
    if not bundle.is_file():
        raise FileNotFoundError("Bundled Golden Dragon knowledge was not installed")
    with _LOCK:
        with zipfile.ZipFile(bundle, "r") as archive:
            if archive.testzip() is not None:
                raise ValueError("Damaged knowledge bundle")
            manifest = json.loads(archive.read("manifest.json"))
            names = archive.namelist()
            if len(names) != len(set(names)) or set(names) != set(manifest["files"]) | {"manifest.json"}:
                raise ValueError("Unexpected knowledge bundle layout")
            key = "golden_dragon.sqlite"
            meta = manifest["files"][key]
            if not 0 < meta["bytes"] <= _MAX_DB_SIZE:
                raise ValueError("Knowledge database exceeds size limit")
            # Validate the database contents even when cached.
            target = Path(cache) / key
            if target.is_file() and target.stat().st_size == meta["bytes"]:
                if _sha256(target) == meta["sha256"]:
                    return target
            target.parent.mkdir(parents=True, exist_ok=True)
            tmp = target.with_name(key + f".{os.getpid()}.tmp")
            try:
                digest = hashlib.sha256()
                total = 0
                with archive.open(key) as source, tmp.open("wb") as output:
                    for data in iter(lambda: source.read(1024 * 1024), b""):
                        total += len(data)
                        if total > _MAX_DB_SIZE:
                            raise ValueError("Expanded knowledge database exceeds limit")
                        digest.update(data)
                        output.write(data)
                if total != meta["bytes"] or digest.hexdigest() != meta["sha256"]:
                    raise ValueError("Knowledge database digest mismatch")
                tmp.replace(target)
            finally:
                tmp.unlink(missing_ok=True)
            return target


def _sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()



def _private_alloy_database():
    """Local-only optional full Alloy DB; never shipped with the public app."""
    folder = os.environ.get("GOLDEN_DRAGON_ALLOY_HOME", "")
    base = Path(folder) if folder else Path.home() / "golden-dragon-alloy"
    db = (base / "kb" / "alloy.db").resolve()
    return db if db.is_file() else None


def _private_alloy_search(query, limit=5, database=None):
    """Search source-linked active units; NEVER expose private memory by default."""
    db = Path(database) if database is not None else _private_alloy_database()
    if db is None or not db.is_file():
        return []
    simplified = unicodedata.normalize("NFKC", query).casefold()
    simplified = "".join(c for c in simplified if not (0x064b <= ord(c) <= 0x065f or ord(c) == 0x0670))
    simplified = simplified.translate(str.maketrans({
        "أ": "ا", "إ": "ا", "آ": "ا", "ى": "ي", "ة": "ه", "ؤ": "و", "ئ": "ي"}))
    terms = list(dict.fromkeys(re.findall(r"\w+", simplified)))[:20]
    if not terms:
        return []
    match = " OR ".join('"' + t.replace('"', '""') + '"*' if len(t) >= 3 else
                        '"' + t.replace('"', '""') + '"' for t in terms)
    with closing(sqlite3.connect(Path(db).resolve().as_uri() + "?mode=ro", uri=True)) as con:
        con.execute("PRAGMA query_only=ON")
        rows = con.execute(
            "SELECT u.title,u.summary,u.path,u.sources,u.kind "
            "FROM fts JOIN units u ON u.rowid=fts.rowid "
            "WHERE fts MATCH ? AND u.status='active' AND u.kind!='memory' "
            "ORDER BY bm25(fts, 8.0, 4.0, 1.0) LIMIT ?", (match, min(int(limit), 10))).fetchall()
    out = []
    for title, summary, path, raw_sources, kind in rows:
        try:
            sources = json.loads(raw_sources or "[]")
        except (ValueError, TypeError):
            sources = []
        sources = [x for x in sources if isinstance(x, dict)][:8]
        if not sources and path:
            sources = [{"path": str(path)}]
        content = (str(title or "") + chr(10) + str(summary or "")).strip()
        out.append({"text": content[:1300], "sources": sources,
                    "original_variants": 1, "origin": "private-full-alloy", "kind": kind})
    return out


def _private_alloy_count():
    db = _private_alloy_database()
    if not db:
        return 0
    with closing(sqlite3.connect(db.resolve().as_uri() + "?mode=ro", uri=True)) as con:
        return con.execute("SELECT count(*) FROM units").fetchone()[0]



def status():
    try:
        result = knowledge.status(verified_database())
        try:
            full_count = _private_alloy_count()
        except (sqlite3.Error, OSError, ValueError):
            full_count = 0
        return {"ok": result["passed"], **result,
                "integration": "embedded read-only knowledge",
                "alloy_units_available": full_count}
    except (OSError, KeyError, ValueError, zipfile.BadZipFile, json.JSONDecodeError) as exc:
        return {"ok": False, "why": f"{type(exc).__name__}: {exc}"[:250]}


def search(text, limit=5):
    if not isinstance(text, str) or not text.strip():
        return {"ok": True, "matches": []}
    if len(text) > 2000:
        return {"ok": False, "why": "Query is too long"}
    try:
        limit = min(10, max(1, int(limit)))
        try:
            matches = _private_alloy_search(text, limit)
        except (sqlite3.Error, OSError, ValueError, KeyError):
            matches = []
        if not matches:
            matches = knowledge.search(text, limit, verified_database())
        # Expose bounded, traceable text, never execute it as instructions.
        return {"ok": True, "matches": [
            {"text": record["text"][:1300],
             "sources": record.get("sources", [])[:8],
             "original_variants": record.get("original_variants", 1)}
            for record in matches]}
    except (OSError, ValueError, KeyError, zipfile.BadZipFile, json.JSONDecodeError) as exc:
        return {"ok": False, "why": f"{type(exc).__name__}: {exc}"[:250]}


def dispatch(arguments):
    operation = arguments.get("action") if isinstance(arguments, dict) else None
    if operation == "status":
        response = status()
    elif operation == "search":
        response = search(arguments.get("query", ""), arguments.get("limit", 5))
    else:
        response = {"ok": False, "why": "Only read-only status and search are available to the AI tool"}
    return json.dumps(response, ensure_ascii=False)[:20000], not response.get("ok", False)
