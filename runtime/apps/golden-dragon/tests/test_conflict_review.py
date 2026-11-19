import importlib.util
import unittest
from pathlib import Path
p = Path(__file__).resolve().parents[1] / "forge" / "conflict_review.py"
spec = importlib.util.spec_from_file_location("conflict_review", p)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class ConflictTests(unittest.TestCase):
    def test_opposite_instructions_flagged_not_resolved(self):
        items = [
            {"text": "Always expose diagnostic information", "sources": [{"path": "a"}]},
            {"text": "Never expose diagnostic information", "sources": [{"path": "b"}]},
        ]
        result = mod.detect(items)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["positive"][0]["sources"][0]["path"], "a")
        self.assertEqual(result[0]["negative"][0]["sources"][0]["path"], "b")
    def test_unrelated_instructions_not_flagged(self):
        self.assertEqual(mod.detect([
            {"text": "Always verify document contents", "sources": []},
            {"text": "Never expose secret credentials", "sources": []}
        ]), [])
if __name__ == "__main__":
    unittest.main()
