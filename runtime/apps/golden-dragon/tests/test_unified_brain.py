import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
p = Path(__file__).resolve().parents[1] / "forge" / "unified_brain.py"
spec = importlib.util.spec_from_file_location("unified_brain", p)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
class BrainTests(unittest.TestCase):
    def test_quarantines_conflicts_preserves_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            instructions = [{"text": "Always verify documents", "sources": [{"path": "a"}]}, {"text": "Never verify documents", "sources": [{"path": "b"}]}, {"text": "Always save reports", "sources": [{"path": "c"}]}]
            conflicts = [{"positive": [instructions[0]], "negative": [instructions[1]]}]
            (root / "i.json").write_text(json.dumps(instructions))
            (root / "c.json").write_text(json.dumps(conflicts))
            result = mod.build(root / "i.json", root / "c.json", root / "out")
            self.assertEqual(result["instructions_in_brain"], 1)
            self.assertEqual(result["requires_review"], 2)
            data = json.loads((root / "out" / "brain.json").read_text())
            self.assertEqual(data["instructions"][0]["sources"][0]["path"], "c")
if __name__ == "__main__":
    unittest.main()
