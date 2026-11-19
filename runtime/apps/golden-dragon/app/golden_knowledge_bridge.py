"""Safe read-only integration of the independent knowledge bundle into Golden Dragon.

Source skills remain untrusted reference data. No arbitrary command execution.
The ZIP ships with the app; the verified SQLite member is cached per-user.
"""
import hashlib
import json
import os
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


def status():
    try:
        result = knowledge.status(verified_database())
        return {"ok": result["passed"], **result, "integration": "embedded read-only knowledge"}
    except (OSError, KeyError, ValueError, zipfile.BadZipFile, json.JSONDecodeError) as exc:
        return {"ok": False, "why": f"{type(exc).__name__}: {exc}"[:250]}


def search(text, limit=5):
    if not isinstance(text, str) or not text.strip():
        return {"ok": True, "matches": []}
    if len(text) > 2000:
        return {"ok": False, "why": "Query is too long"}
    try:
        limit = min(10, max(1, int(limit)))
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
