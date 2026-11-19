"""Continuous owner-memory tests. No real owner files are used."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from owner_memory import snapshot, remember, recall, records, sync


def normalize(value):
    return value.casefold()


class OwnerMemoryTests(unittest.TestCase):
    def test_snapshot_keeps_every_original(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            live, dest = root / "live", root / "private"
            (live / "think" / "plans").mkdir(parents=True)
            (live / "lessons.jsonl").write_text('{"id":"x","text":"Keep original files safe"}\n', encoding="utf-8")
            (live / "think" / "plans" / "plan.md").write_text("Plan remains", encoding="utf-8")
            info = snapshot(live, dest)
            self.assertEqual(info["snapshot_files"], 2)
            self.assertEqual((dest / "live" / "lessons.jsonl").read_bytes(),
                             (live / "lessons.jsonl").read_bytes())
            self.assertTrue((live / "think" / "plans" / "plan.md").exists())
            self.assertEqual(snapshot(live, dest)["snapshot_files"], 2)

    def test_remember_and_recall_across_sessions(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            result = remember("Always retain original Excel invoice numbers", store=path)
            self.assertTrue(result["ok"])
            self.assertFalse(result["duplicate"])
            duplicate = remember("Always retain original Excel invoice numbers", store=path)
            self.assertTrue(duplicate["duplicate"])
            rows = recall("excel invoice", normalize, store=path)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["kind"], "correction")
            self.assertEqual(len(records(path / "journal.jsonl")), 1)

    def test_credentials_are_not_written(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                remember("Use password=DoNotStoreThis", store=Path(tmp))
            self.assertFalse((Path(tmp) / "journal.jsonl").exists())

    def test_sync_never_pushes_without_explicit_opt_in(self):
        with patch("owner_memory.private_remote", return_value="owner/private"):
            result = sync(push=False)
        self.assertFalse(result["pushed"])


if __name__ == "__main__":
    unittest.main()
