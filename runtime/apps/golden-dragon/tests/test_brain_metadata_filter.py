import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
p = Path(__file__).resolve().parents[1] / "forge" / "brain_query.py"
spec = importlib.util.spec_from_file_location("brain_query", p)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
class MetadataTests(unittest.TestCase):
    def test_metadata_not_returned_as_instructions(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "brain.json"
            f.write_text(json.dumps({"instructions": [
                {"text": "description: Python testing", "sources": [{"path": "a"}]},
                {"text": "Run Python testing with assertions", "sources": [{"path": "b"}]}
            ]}))
            found = mod.search(f, "python testing")
            self.assertEqual(len(found), 1)
            self.assertEqual(found[0]["sources"][0]["path"], "b")
if __name__ == "__main__":
    unittest.main()
