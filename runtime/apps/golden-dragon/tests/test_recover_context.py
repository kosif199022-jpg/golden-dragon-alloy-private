import importlib.util
import tempfile
import unittest
from pathlib import Path

p = Path(__file__).resolve().parents[1] / "forge" / "recover_context.py"
spec = importlib.util.spec_from_file_location("recover_context", p)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class RecoveryTests(unittest.TestCase):
    def test_recovers_line_and_context(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "SKILL.md").write_text("# Topic\nAlways verify output before\ndelivery is approved.\n", encoding="utf-8")
            items = [{"text": "Always verify output before", "reasons": ["incomplete_end"],
                      "sources": [{"path": "SKILL.md", "section": 0}]}]
            got = mod.recover(items, root)
            self.assertEqual(got[0]["context_matches"][0]["line"], 2)
            self.assertIn("delivery is approved.", got[0]["context_matches"][0]["context"])

    def test_blocks_outside_root_and_identifies_metadata(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            got = mod.recover([{"text": "name: example", "sources": [{"path": "../escape.md"}]}], root)
            self.assertEqual(got[0]["category"], "metadata")
            self.assertEqual(got[0]["context_matches"], [])

if __name__ == "__main__":
    unittest.main()
