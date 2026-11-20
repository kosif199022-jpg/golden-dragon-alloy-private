"""Tests for source-aware lexical knowledge retrieval."""
import importlib.util
import unittest
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1] / "forge" / "query_distilled.py"
spec = importlib.util.spec_from_file_location("query_distilled", MODULE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class RetrievalTests(unittest.TestCase):
    def setUp(self):
        self.index = {"schema_version": 1, "knowledge": [
            {"heading": "Video animation", "body": "Animate an original scene",
             "source": "video/SKILL.md", "fingerprint": "video1"},
            {"heading": "Accounting", "body": "Prepare journal entries",
             "source": "finance/SKILL.md", "fingerprint": "finance1"}
        ]}

    def test_relevant_result_with_provenance(self):
        result = module.search(self.index, "video animation")
        self.assertEqual(result[0]["source"], "video/SKILL.md")
        self.assertEqual(result[0]["fingerprint"], "video1")

    def test_empty_and_unknown_queries(self):
        self.assertEqual(module.search(self.index, ""), [])
        self.assertEqual(module.search(self.index, "unmatchedterm"), [])

    def test_limit(self):
        self.assertEqual(len(module.search(self.index, "scene journal", limit=1)), 1)

if __name__ == "__main__":
    unittest.main()
