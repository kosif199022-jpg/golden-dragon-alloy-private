import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
p = Path(__file__).resolve().parents[1] / "forge" / "verify_lossless_fusion.py"
spec = importlib.util.spec_from_file_location("verify_lossless_fusion", p)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class FusionAuditTests(unittest.TestCase):
    def test_detects_tampering_and_preserves_originals(self):
        with tempfile.TemporaryDirectory() as tmp:
            old = Path(tmp) / "old.json"
            new = Path(tmp) / "new.json"
            first = {"text": "Never delete original files.", "sources": [{"path": "a"}]}
            second = {"text": "Never delete original files;", "sources": [{"path": "b"}]}
            data = {"instructions": [first, second],
                    "quality_quarantine": [], "requires_review": []}
            old.write_text(json.dumps(data), encoding="utf-8")
            merged = {"text": first["text"],
                      "sources": first["sources"] + second["sources"],
                      "verified_format_fusion": {"variants": [
                          {"original_index": 0, "record": first},
                          {"original_index": 1, "record": second}]}}
            data["instructions"] = [merged]
            new.write_text(json.dumps(data), encoding="utf-8")
            self.assertTrue(mod.audit(old, new)["passed"])
            merged["verified_format_fusion"]["variants"][1]["record"] = {"text": "tampered"}
            new.write_text(json.dumps(data), encoding="utf-8")
            result = mod.audit(old, new)
            self.assertFalse(result["passed"])
            self.assertEqual(result["missing"], 1)

if __name__ == "__main__":
    unittest.main()
