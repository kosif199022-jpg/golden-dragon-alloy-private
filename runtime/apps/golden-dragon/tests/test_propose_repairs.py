import importlib.util
import unittest
from pathlib import Path
p = Path(__file__).resolve().parents[1] / "forge" / "propose_repairs.py"
spec = importlib.util.spec_from_file_location("propose_repairs", p)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
class RepairTests(unittest.TestCase):
    def test_proposes_context_without_auto_apply(self):
        item = {"text": "Always verify the", "reasons": ["incomplete_end"],
                "context_matches": [{"source": "a", "line": 2,
                  "context": "# Title\nAlways verify the\nresults before publishing."}]}
        got = mod.suggest([item])[0]
        self.assertEqual(got["suggestions"][0]["candidate"],
                         "Always verify the results before publishing.")
        self.assertFalse(got["auto_applied"])
    def test_no_unrelated_heading_join(self):
        item = {"text": "Always verify output", "context_matches": [
            {"source": "a", "line": 2, "context": "# Title\nAlways verify output\n## Next"}]}
        self.assertEqual(mod.suggest([item])[0]["suggestions"], [])
if __name__ == "__main__":
    unittest.main()
