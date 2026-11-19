import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
p = Path(__file__).resolve().parents[1] / "forge" / "ranked_brain_query.py"
spec = importlib.util.spec_from_file_location("ranked_brain_query", p)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class RankedQueryTests(unittest.TestCase):
    def test_ranks_all_terms_and_excludes_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "brain.json"
            f.write_text(json.dumps({"instructions": [
                {"text": "description: python testing", "sources": [{"path": "meta"}]},
                {"text": "Use python testing assertions", "sources": [{"path": "best"}]},
                {"text": "python python python", "sources": [{"path": "partial"}]}
            ]}))
            got = mod.search(f, "python testing")
            self.assertEqual(got[0]["sources"][0]["path"], "best")
            self.assertEqual(got[0]["matched_terms"], 2)
            self.assertEqual(len(got), 2)
    def test_empty_and_missing_terms(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "brain.json"
            f.write_text(json.dumps({"instructions": [{"text": "Run tests", "sources": []}]}))
            self.assertEqual(mod.search(f, ""), [])
            self.assertEqual(mod.search(f, "unrelated"), [])
if __name__ == "__main__":
    unittest.main()
