import importlib.util
import unittest
from pathlib import Path
p = Path(__file__).resolve().parents[1] / "forge" / "near_duplicate_review.py"
spec = importlib.util.spec_from_file_location("near_duplicate_review", p)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
class CandidateTests(unittest.TestCase):
    def test_near_duplicate_is_review_only(self):
        data = [{"text": "Validate invoices before posting ledger entries against source documents", "sources": [{"path": "a"}]},
                {"text": "Validate invoices before posting ledger entries against source records", "sources": [{"path": "b"}]},
                {"text": "Animate characters with keyframes and lighting effects", "sources": [{"path": "c"}]}]
        found = mod.candidates(data, threshold=.7)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["decision"], "review_required")
        self.assertEqual(found[0]["left_sources"][0]["path"], "a")
        self.assertEqual(found[0]["right_sources"][0]["path"], "b")
    def test_no_merge_when_unrelated(self):
        data = [{"text": "One two three four five six seven"},
                {"text": "Alpha beta gamma delta epsilon zeta eta"}]
        self.assertEqual(mod.candidates(data), [])
if __name__ == "__main__":
    unittest.main()
