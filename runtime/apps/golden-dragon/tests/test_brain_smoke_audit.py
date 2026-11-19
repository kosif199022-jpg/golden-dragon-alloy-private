import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
p = Path(__file__).resolve().parents[1] / "forge" / "brain_smoke_audit.py"
spec = importlib.util.spec_from_file_location("brain_smoke_audit", p)
import sys
sys.path.insert(0, str(p.parent))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
class SmokeAuditTests(unittest.TestCase):
    def test_conservation_and_search(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "brain.json"
            path.write_text(json.dumps({"instructions": [{"text": "Python testing security",
                "sources": [{"path": "a"}]}], "quality_quarantine": [{"instruction": {"text": "q"}}],
                "requires_review": [{"text": "c"}]}))
            result = mod.audit(path, ["python", "testing"])
            self.assertTrue(result["passed"])
            self.assertEqual(result["preserved_total"], 3)
    def test_missing_source_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "brain.json"
            path.write_text(json.dumps({"instructions": [{"text": "Python", "sources": []}]}))
            self.assertFalse(mod.audit(path, ["python"])["passed"])
if __name__ == "__main__":
    unittest.main()
