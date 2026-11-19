"""Golden Dragon: standalone read-only knowledge and verified local adapters.

Requires only Python 3.10+ standard library and the bundled golden_dragon.sqlite.
Source skill text is treated as untrusted reference data, never executed.
"""
import argparse
import csv
from contextlib import contextmanager
import hashlib
import json
import re
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATABASE = HERE / "golden_dragon.sqlite"
PROVENANCE_KEYS = ("active", "quality_review", "conflict_review")
META = re.compile(r"^\s*(?:name|description|version|author|license|allowed-tools):", re.I)
TERM = re.compile(r"[^\W_]+", re.UNICODE)
CAPABILITIES = {
    "brain.status": "Read the number and status of preserved knowledge records.",
    "brain.search": "Find source-linked active knowledge; quarantined records are excluded.",
    "brain.verify": "Verify SHA-256 digests of all installed Golden Dragon files.",
    "file.sha256": "Read a local file and compute its SHA-256; no modifications.",
    "json.inspect": "Validate a local JSON file and summarize its shape.",
    "csv.inspect": "Read and summarize a local CSV header and row count.",
}
MAX_FILE_BYTES = 100 * 1024 * 1024


@contextmanager
def readonly_connection(database=DATABASE):
    file = Path(database).resolve()
    if not file.is_file():
        raise FileNotFoundError("Golden Dragon database is missing: " + str(file))
    conn = sqlite3.connect(file.as_uri() + "?mode=ro", uri=True)
    try:
        conn.execute("PRAGMA query_only=ON")
        yield conn
    finally:
        conn.close()


def status(database=DATABASE):
    with readonly_connection(database) as con:
        counts = {key: 0 for key in PROVENANCE_KEYS}
        for key, count in con.execute("SELECT status, COUNT(*) FROM knowledge GROUP BY status"):
            counts[key] = count
        integrity = con.execute("PRAGMA quick_check").fetchone()[0]
        return {"counts": counts, "total_canonical": sum(counts.values()),
                "integrity": integrity,
                "provenance": "Full original records stored in JSON payloads; fused variants preserved.",
                "executable_adapters": len(CAPABILITIES), "passed": integrity == "ok"}


def tokenize(query):
    return list(dict.fromkeys(x.casefold() for x in TERM.findall(query)))[:32]


def search(query, limit=5, database=DATABASE):
    terms = tokenize(query)
    if not terms:
        return []
    with readonly_connection(database) as con:
        fts_row = con.execute("SELECT value FROM manifest WHERE key='fts5'").fetchone()
        fts5 = bool(json.loads(fts_row[0])) if fts_row else False
        limit = min(100, max(1, limit))
        if fts5:
            expression = " OR ".join('"' + w.replace('"', '""') + '"' for w in terms)
            query_sql = ("SELECT k.status,k.text,k.payload FROM knowledge_fts f "
                         "JOIN knowledge k ON k.id=f.rowid "
                         "WHERE knowledge_fts MATCH ? AND k.status='active' "
                         "ORDER BY bm25(knowledge_fts) LIMIT ?")
            rows = con.execute(query_sql, (expression, limit * 12)).fetchall()
        else:
            # Python-side fallback for SQLite installations compiled without FTS5.
            rows = con.execute("SELECT status,text,payload FROM knowledge WHERE status='active'").fetchall()
            rows = sorted(
                (r for r in rows if any(t in r[1].casefold() for t in terms)),
                key=lambda r: -sum(t in r[1].casefold() for t in terms))
        found = []
        for kind, content, payload in rows:
            if META.match(content):
                continue
            original = json.loads(payload)
            found.append({"text": content, "sources": original.get("sources", []),
                          "original_variants": len(
                              original.get("verified_format_fusion", {}).get("variants", [original])),
                          "status": kind})
            if len(found) >= limit:
                break
        return found



def verify_install(root=HERE):
    root = Path(root)
    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    expected = manifest["files"]
    failures = []
    for name, info in expected.items():
        if Path(name).name != name or name in (".", ".."):
            failures.append({"file": name, "reason": "invalid_manifest_path"})
            continue
        path = root / name
        if not path.is_file():
            failures.append({"file": name, "reason": "missing"})
            continue
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
        if digest.hexdigest() != info["sha256"] or path.stat().st_size != info["bytes"]:
            failures.append({"file": name, "reason": "digest_mismatch"})
    return {"passed": not failures, "checked": len(expected), "failures": failures}


def inspect_path(file):
    path = Path(file).resolve(strict=True)
    if not path.is_file():
        raise ValueError("Expected a regular file")
    if path.stat().st_size > MAX_FILE_BYTES:
        raise ValueError("File exceeds 100 MiB inspection limit")
    return path


def file_sha256(file):
    path = inspect_path(file)
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return {"path": str(path), "bytes": path.stat().st_size, "sha256": digest.hexdigest()}


def json_inspect(file):
    path = inspect_path(file)
    with path.open(encoding="utf-8-sig") as handle:
        data = json.load(handle)
    kind = type(data).__name__
    result = {"path": str(path), "valid": True, "type": kind}
    if isinstance(data, dict):
        result["top_level_keys"] = list(data)[:30]
        result["keys_total"] = len(data)
    elif isinstance(data, list):
        result["items"] = len(data)
    return result


def csv_inspect(file, max_rows=5000):
    path = inspect_path(file)
    if max_rows < 1 or max_rows > 5000:
        raise ValueError("max_rows must be from 1 through 5000")
    with path.open(encoding="utf-8-sig", newline="") as handle:
        first = handle.read(4096)
        handle.seek(0)
        try:
            dialect = csv.Sniffer().sniff(first, delimiters=",;\t|")
        except csv.Error:
            dialect = csv.excel
        reader = csv.reader(handle, dialect)
        header = next(reader, [])
        observed = 0
        for row in reader:
            if row:
                observed += 1
            if observed >= max_rows:
                break
    return {"path": str(path), "header": header[:100], "columns": len(header),
            "rows_examined": observed, "max_rows": max_rows,
            "more_rows_possible": observed == max_rows}


def main(argv=None, database=DATABASE):
    parser = argparse.ArgumentParser(description="Golden Dragon offline, read-only runtime")
    sub = parser.add_subparsers(dest="operation", required=True)
    sub.add_parser("capabilities")
    sub.add_parser("status")
    sub.add_parser("verify")
    find = sub.add_parser("search")
    find.add_argument("question")
    find.add_argument("--limit", type=int, default=5)
    digest = sub.add_parser("sha256")
    digest.add_argument("file")
    inspect_json = sub.add_parser("json")
    inspect_json.add_argument("file")
    inspect_csv = sub.add_parser("csv")
    inspect_csv.add_argument("file")
    inspect_csv.add_argument("--max-rows", type=int, default=5000)
    args = parser.parse_args(argv)
    actions = {
        "capabilities": lambda: CAPABILITIES,
        "status": lambda: status(database),
        "verify": lambda: verify_install(),
        "search": lambda: search(args.question, args.limit, database),
        "sha256": lambda: file_sha256(args.file),
        "json": lambda: json_inspect(args.file),
        "csv": lambda: csv_inspect(args.file, args.max_rows),
    }
    try:
        result = actions[args.operation]()
    except (OSError, ValueError, sqlite3.Error, json.JSONDecodeError, UnicodeError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}), file=sys.stderr)
        return 2
    print(json.dumps({"ok": True, "result": result}, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
