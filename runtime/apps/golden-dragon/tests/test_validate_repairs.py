import importlib.util
import unittest
from pathlib import Path
p = Path(__file__).resolve().parents[1] / "forge" / "validate_repairs.py"
spec = importlib.util.spec_from_file_location("validate_repairs", p)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
class ValidationTests(unittest.TestCase):
    def test_safe_continuation_remains_review_only(self):
        rows = mod.validate([{"original": "Always verify",
            "suggestions": [{"candidate": "Always verify source documents before delivery.",
                             "source": "a", "line": 2}]}])
        self.assertEqual(rows[0]["proposals"][0]["classification"], "reviewable")
        self.assertFalse(rows[0]["auto_applied"])
    def test_rejects_unrelated_or_sensitive_content(self):
        rows = mod.validate([{"original": "Always verify",
            "suggestions": [{"candidate": "Never verify source documents."},
                            {"candidate": "Always verify password=abc123"}]}])
        self.assertEqual([x["classification"] for x in rows[0]["proposals"]],
                         ["rejected", "rejected"])
if __name__ == "__main__":
    unittest.main()
