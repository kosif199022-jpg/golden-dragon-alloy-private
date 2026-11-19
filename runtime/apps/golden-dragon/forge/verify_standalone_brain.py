"""Audit a standalone Golden Dragon SQLite knowledge bundle against its source."""
import argparse
import hashlib
import json
import sqlite3
from pathlib import Path

def audit(brain_path, database):
    source = json.loads(Path(brain_path).read_text(encoding="utf-8-sig"))
    expected = {"active": source.get("instructions", []),
                "quality_review": source.get("quality_quarantine", []),
                "conflict_review": source.get("requires_review", [])}
    con = sqlite3.connect(f"file:{Path(database).resolve().as_posix()}?mode=ro", uri=True)
    try:
        mismatches = []
        checked = 0
        for status, entries in expected.items():
            cursor = con.execute("SELECT payload FROM knowledge WHERE status=? ORDER BY id", (status,))
            actual = (json.loads(row[0]) for row in cursor)
            sentinel = object()
            from itertools import zip_longest
            for idx, (left, right) in enumerate(zip_longest(entries, actual, fillvalue=sentinel)):
                checked += 1
                if left != right:
                    mismatches.append({"status": status, "index": idx})
                    if len(mismatches) >= 20:
                        break
        integrity = con.execute("PRAGMA integrity_check").fetchone()[0]
        return {"expected": {k: len(v) for k, v in expected.items()},
                "records_checked": checked, "integrity": integrity,
                "mismatches": mismatches, "passed": integrity == "ok" and not mismatches}
    finally:
        con.close()

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("brain")
    p.add_argument("database")
    p.add_argument("--report", required=True)
    a = p.parse_args()
    result = audit(a.brain, a.database)
    Path(a.report).write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result))
    if not result["passed"]:
        raise SystemExit(1)
