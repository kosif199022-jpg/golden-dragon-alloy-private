"""Regression tests for conservative near-duplicate review."""
import importlib.util
import unittest
from pathlib import Path

path = Path(__file__).resolve().parents[1] / "forge" / "review_similar_skills.py"
spec = importlib.util.spec_from_file_location("review_similar_skills", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class SimilarityTests(unittest.TestCase):
    def test_similar_sections_group_without_removal(self):
        common = "prepare timeline audio video animation render scene motion camera lighting composition export"
        data = {"knowledge": [
            {"source": "one", "heading": "A", "body": common, "fingerprint": "a"},
            {"source": "two", "heading": "B", "body": common + " output", "fingerprint": "b"},
            {"source": "three", "heading": "C", "body": "finance journal ledger taxes", "fingerprint": "c"}]}
        result = module.candidate_groups(data, threshold=0.8)
        self.assertEqual(len(result["candidate_groups"]), 1)
        self.assertEqual(len(result["candidate_groups"][0]["members"]), 2)
        self.assertTrue(result["sources_preserved"])

    def test_invalid_threshold(self):
        with self.assertRaises(ValueError):
            module.candidate_groups({"knowledge": []}, threshold=0)

if __name__ == "__main__":
    unittest.main()
