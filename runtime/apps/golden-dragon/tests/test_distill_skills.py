"""Regression tests for Golden Dragon static skill distillation."""
import importlib.util
import tempfile
import unittest
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1] / "forge" / "distill_skills.py"
spec = importlib.util.spec_from_file_location("distill_skills", MODULE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class DistillationTests(unittest.TestCase):
    def test_headings_duplicates_and_headingless(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for folder, text in [
                ("alpha", "# Alpha\n\nShared instructions\n\n## Unique\n\nUse tool A"),
                ("beta", "# Beta\n\nShared instructions"),
                ("gamma", "Plain skill with no markdown headings")]:
                p = root / folder / "SKILL.md"
                p.parent.mkdir()
                p.write_text(text, encoding="utf-8")
            result = module.distill(root)
            self.assertEqual(result["statistics"]["skills"], 3)
            self.assertEqual(result["statistics"]["duplicate_sections"], 1)
            self.assertEqual(result["statistics"]["unique_sections"], 3)
            self.assertTrue(any(x["heading"] == "Full document" for x in result["knowledge"]))
            self.assertTrue((root / "alpha" / "SKILL.md").exists())

    def test_preamble_is_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "SKILL.md").write_text("Important setup instructions\n\n# Usage\n\nRun safely", encoding="utf-8")
            result = module.distill(root)
            self.assertEqual(result["statistics"]["unique_sections"], 2)
            self.assertEqual(result["knowledge"][0]["heading"], "Preamble")
            self.assertIn("Important setup", result["knowledge"][0]["body"])

    def test_source_symlink_is_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "original.txt"
            target.write_text("# Secret\n\nDo not index", encoding="utf-8")
            link = root / "SKILL.md"
            try:
                link.symlink_to(target)
            except (OSError, NotImplementedError):
                self.skipTest("symlinks unavailable")
            result = module.distill(root)
            self.assertEqual(result["statistics"]["skills"], 0)

    def test_oversized_file_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            p = root / "SKILL.md"
            p.write_text("x" * (module.MAX_FILE_BYTES + 1), encoding="utf-8")
            result = module.distill(root)
            self.assertEqual(result["statistics"]["errors"], 1)
            self.assertEqual(result["statistics"]["skills"], 0)

if __name__ == "__main__":
    unittest.main()
