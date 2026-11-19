"""Read-only integrity audit of the PRIVATE Golden Dragon Alloy memory.

Validates the live-memory snapshot and the historical private-memory baseline.
Never prints private memory text, changes snapshots, or uploads anything.
"""
from __future__ import annotations

import argparse
from contextlib import closing
import hashlib
import json
from pathlib import Path, PurePosixPath
import sqlite3

ROOT = Path(__file__).resolve().parents[1]
STORE = ROOT / "owner-memory"
DATABASE = ROOT / "kb" / "alloy.db"


def _digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_relative(value: object) -> tuple[str, ...] | None:
    if not isinstance(value, str) or not value or "\\" in value or ":" in value or "\0" in value:
        return None
    parts = PurePosixPath(value).parts
    if not parts or value.startswith("/") or any(x in (".", "..", "") for x in parts):
        return None
    if PurePosixPath(*parts).as_posix() != value:
        return None
    return parts


def _private_count(database: Path, issues: list[str]) -> int:
    if not database.is_file():
        issues.append("database_missing")
        return 0
    try:
        with closing(sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)) as con:
            con.execute("PRAGMA query_only=ON")
            if con.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                issues.append("database_integrity_failed")
            return int(con.execute(
                "SELECT COUNT(*) FROM units WHERE kind='memory' OR status='private'"
            ).fetchone()[0])
    except (sqlite3.Error, OSError, TypeError, ValueError):
        issues.append("database_unreadable")
        return 0


def audit(store: Path = STORE, database: Path = DATABASE, min_private: int = 163) -> dict:
    """Fail closed on lost, corrupted, unexpected, or unsafe memory files."""
    store, database = Path(store), Path(database)
    live = store / "live"
    manifest_file = store / "snapshot_manifest.json"
    issues: list[str] = []
    expected: set[str] = set()
    validated = 0
    total_bytes = 0

    try:
        manifest = json.loads(manifest_file.read_text(encoding="utf-8-sig"))
        entries = manifest["files"]
        if not isinstance(entries, list) or manifest.get("private_only") is not True:
            raise ValueError("invalid manifest")
        if manifest.get("count") != len(entries):
            issues.append("manifest_count_mismatch")
    except (OSError, UnicodeError, ValueError, KeyError, TypeError):
        entries = []
        issues.append("manifest_missing_or_invalid")

    for item in entries:
        if not isinstance(item, dict):
            issues.append("manifest_entry_invalid")
            continue
        rel = item.get("path")
        parts = _safe_relative(rel)
        if parts is None:
            issues.append("unsafe_snapshot_path")
            continue
        if rel in expected:
            issues.append("duplicate_snapshot_path")
            continue
        expected.add(rel)
        path = live.joinpath(*parts)
        current = live
        if not live.is_dir():
            issues.append("live_snapshot_missing")
            continue
        unsafe_link = False
        for name in parts:
            current = current / name
            if current.is_symlink():
                unsafe_link = True
                break
        if unsafe_link or not path.resolve().is_relative_to(live.resolve()):
            issues.append("unsafe_snapshot_link")
            continue
        if not path.is_file():
            issues.append("snapshot_file_missing")
            continue
        try:
            declared_bytes = item.get("bytes")
            declared_digest = item.get("sha256")
            if (type(declared_bytes) is not int or declared_bytes < 0
                    or not isinstance(declared_digest, str) or len(declared_digest) != 64):
                issues.append("snapshot_metadata_invalid")
                continue
            if path.stat().st_size != declared_bytes or _digest(path) != declared_digest:
                issues.append("snapshot_digest_mismatch")
                continue
            total_bytes += declared_bytes
            validated += 1
        except OSError:
            issues.append("snapshot_file_unreadable")

    if live.exists():
        actual = {p.relative_to(live).as_posix() for p in live.rglob("*") if p.is_file()}
        if actual - expected:
            issues.append("unlisted_snapshot_files")

    journal = store / "journal.jsonl"
    events = 0
    if journal.exists():
        seen: set[str] = set()
        try:
            with journal.open("r", encoding="utf-8-sig") as stream:
                for line in stream:
                    if not line.strip():
                        continue
                    try:
                        item = json.loads(line)
                    except (ValueError, UnicodeError):
                        issues.append("journal_invalid_json")
                        continue
                    if not isinstance(item, dict) or not item.get("id") or not item.get("text"):
                        issues.append("journal_invalid_record")
                        continue
                    if item["id"] in seen:
                        issues.append("journal_duplicate_record")
                    seen.add(item["id"])
                    events += 1
        except (OSError, UnicodeError):
            issues.append("journal_unreadable")

    private_units = _private_count(database, issues)
    if private_units < max(0, min_private):
        issues.append("historical_private_memory_below_baseline")
    return {
        "passed": not issues,
        "verified_snapshot_files": validated,
        "manifest_files": len(entries),
        "verified_snapshot_bytes": total_bytes,
        "append_only_journal_events": events,
        "historical_private_units": private_units,
        "minimum_historical_private_units": min_private,
        "issue_codes": sorted(set(issues)),
        "private_text_exposed": False,
        "read_only": True,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit private Golden Dragon memory without revealing it")
    parser.add_argument("--store", type=Path, default=STORE)
    parser.add_argument("--database", type=Path, default=DATABASE)
    parser.add_argument("--min-private", type=int, default=163)
    args = parser.parse_args(argv)
    result = audit(args.store, args.database, args.min_private)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
