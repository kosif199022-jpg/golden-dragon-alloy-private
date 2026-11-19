"""Synthetic fixtures only: no real owner memory ever appears in test logs."""
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from memory_integrity import audit


class MemoryIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = self.root / "owner-memory"
        self.live = self.store / "live"
        self.live.mkdir(parents=True)
        self.notes = self.live / "lessons.jsonl"
        self.notes.write_text('{"id":"a","text":"retain the source"}\n', encoding="utf-8")
        self.db = self.root / "alloy.db"
        with sqlite3.connect(self.db) as con:
            con.execute("CREATE TABLE units(kind TEXT, status TEXT)")
            con.execute("INSERT INTO units VALUES ('memory', 'private')")
        self._write_manifest()

    def _write_manifest(self, entries=None):
        if entries is None:
            entries = [{"path": "lessons.jsonl", "bytes": self.notes.stat().st_size,
                        "sha256": hashlib.sha256(self.notes.read_bytes()).hexdigest()}]
        (self.store / "snapshot_manifest.json").write_text(json.dumps({
            "version": 1, "private_only": True, "files": entries, "count": len(entries)
        }), encoding="utf-8")

    def test_valid_memory_and_journal(self):
        (self.store / "journal.jsonl").write_text('{"id":"b","text":"future correction"}\n', encoding="utf-8")
        result = audit(self.store, self.db, 1)
        self.assertTrue(result["passed"])
        self.assertEqual(result["verified_snapshot_files"], 1)
        self.assertEqual(result["historical_private_units"], 1)
        self.assertEqual(result["append_only_journal_events"], 1)
        self.assertNotIn("future correction", json.dumps(result))

    def test_detects_changed_bytes(self):
        self.notes.write_text("changed", encoding="utf-8")
        result = audit(self.store, self.db, 1)
        self.assertFalse(result["passed"])
        self.assertIn("snapshot_digest_mismatch", result["issue_codes"])

    def test_rejects_traversal(self):
        self._write_manifest([{"path": "../outside.json", "bytes": 1, "sha256": "0" * 64}])
        result = audit(self.store, self.db, 1)
        self.assertFalse(result["passed"])
        self.assertIn("unsafe_snapshot_path", result["issue_codes"])

    def test_detects_private_memory_loss(self):
        result = audit(self.store, self.db, 2)
        self.assertFalse(result["passed"])
        self.assertIn("historical_private_memory_below_baseline", result["issue_codes"])

    def test_rejects_unlisted_file_and_duplicate_journal(self):
        (self.live / "unexpected.json").write_text("{}", encoding="utf-8")
        (self.store / "journal.jsonl").write_text(
            '{"id":"b","text":"first"}\n{"id":"b","text":"second"}\n',
            encoding="utf-8")
        result = audit(self.store, self.db, 1)
        self.assertFalse(result["passed"])
        self.assertIn("unlisted_snapshot_files", result["issue_codes"])
        self.assertIn("journal_duplicate_record", result["issue_codes"])


if __name__ == "__main__":
    unittest.main()
