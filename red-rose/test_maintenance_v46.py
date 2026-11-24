import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import rose_env
import rose_catalog
import rose_maintenance as m


class MaintenanceTests(unittest.TestCase):
    def test_snapshot_loads_catalog_and_status_once(self):
        entry = {"needs": {"programs": ["ffmpeg"]}, "static_label": "coded_untested"}
        entries = {"a": entry, "b": entry, "c": {"needs": {"pc_only": True}}}
        with patch.object(rose_catalog, "load", return_value={"entries": entries}) as load, \
             patch.object(rose_env, "load_status", return_value={}) as status, \
             patch.object(rose_env, "missing_here", return_value=[]) as deps:
            counts = rose_env.usable_counts()
        self.assertEqual(load.call_count, 1)
        self.assertEqual(status.call_count, 1)
        self.assertEqual(deps.call_count, 1)
        self.assertEqual(counts["coded_untested"], 2)
        self.assertEqual(counts["pc_only"], 1)

    def test_exact_repair_requires_approval(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)/"verify_media.py"
            original = "def f(p):\n" + m.OLD_HASH + "\n"
            p.write_text(original, encoding="utf-8")
            self.assertEqual(m.audit(tmp)["known_repairs"], [p.name])
            self.assertEqual(m.repair(tmp)["status"], "approval_required")
            self.assertEqual(p.read_text(encoding="utf-8"), original)

    def test_repair_rejects_failed_candidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)/"verify_media.py"
            original = "def f(p):\n" + m.OLD_HASH + "\n"
            p.write_text(original, encoding="utf-8")
            with patch.object(m, "run_tests", return_value={"ok": False}):
                self.assertEqual(m.repair(tmp, approve=True)["status"], "candidate_rejected")
            self.assertEqual(p.read_text(encoding="utf-8"), original)

    def test_approved_candidate_only_after_tests(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)/"verify_media.py"
            p.write_text("def f(p):\n" + m.OLD_HASH + "\n", encoding="utf-8")
            with patch.object(m, "run_tests", return_value={"ok": True}):
                result = m.repair(tmp, approve=True)
            self.assertEqual(result["status"], "repaired")
            self.assertIn(m.NEW_HASH, p.read_text(encoding="utf-8"))
            self.assertEqual(result["after_sha256"], hashlib.sha256(p.read_bytes()).hexdigest())
            self.assertEqual(m.repair(tmp, approve=True)["status"], "clean")

    def test_ambiguous_pattern_refused(self):
        text = "def f(p):\n" + m.OLD_HASH + "\n" + m.OLD_HASH
        self.assertIsNone(m.candidate(text, m.OLD_HASH, m.NEW_HASH))


if __name__ == "__main__":
    unittest.main()
