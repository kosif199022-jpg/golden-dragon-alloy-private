import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
p = Path(__file__).resolve().parents[1] / "forge" / "golden_brain_cli.py"
spec = importlib.util.spec_from_file_location("golden_brain_cli", p)
import sys
sys.path.insert(0, str(p.parent))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
class BridgeTests(unittest.TestCase):
    def test_read_only_bridge_routes_with_fusion_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            brain = Path(tmp) / "brain.json"
            brain.write_text(json.dumps({"instructions": [{"text": "Always verify sources", "sources": [{"path": "source"}]}], "requires_review": []}))
            result = mod.consult("verify sources", brain, True, 1)
            self.assertEqual(result["execution"], "not attempted")
            self.assertEqual(result["knowledge"][0]["sources"][0]["path"], "source")
            self.assertEqual(result["fusion_route"].get("exit_code"), 0, result["fusion_route"].get("error"))
if __name__ == "__main__":
    unittest.main()
