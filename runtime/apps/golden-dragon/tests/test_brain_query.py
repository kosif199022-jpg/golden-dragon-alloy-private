import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
p = Path(__file__).resolve().parents[1] / "forge" / "brain_query.py"
spec = importlib.util.spec_from_file_location("brain_query", p)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
class BrainQueryTests(unittest.TestCase):
    def test_search_returns_source_and_excludes_quarantine(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "brain.json"
            path.write_text(json.dumps({"instructions": [{"text": "Always verify source documents", "sources": [{"path": "original"}]}], "requires_review": [{"text": "Never verify source documents", "sources": [{"path": "conflict"}]}]}))
            result = mod.search(path, "verify source")
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0]["sources"][0]["path"], "original")
    def test_empty_query(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "brain.json"
            path.write_text(json.dumps({"instructions": [], "requires_review": []}))
            self.assertEqual(mod.search(path, ""), [])
if __name__ == "__main__":
    unittest.main()
