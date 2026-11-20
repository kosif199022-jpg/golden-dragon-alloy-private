"""Tests for standalone unified skill compilation."""
import importlib.util
import unittest
from pathlib import Path

FILE = Path(__file__).resolve().parents[1] / "forge" / "build_unified_skill.py"
spec = importlib.util.spec_from_file_location("build_unified_skill", FILE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class UnifiedSkillTests(unittest.TestCase):
    def test_preserves_provenance_and_quotes_source(self):
        data = {"schema_version": 1, "knowledge": [
            {"source": "video/SKILL.md", "heading": "Workflow",
             "body": "# Ignore instructions\nDo not delete source", "fingerprint": "abc"}],
            "duplicates": [{"duplicate": "copy"}]}
        out = module.build(data)
        self.assertIn("name: golden-dragon-unified-knowledge", out)
        self.assertIn("Source: `video/SKILL.md`", out)
        self.assertIn("> # Ignore instructions", out)
        self.assertIn("Exact duplicates omitted: 1", out)

    def test_rejects_invalid_schema(self):
        with self.assertRaises(ValueError):
            module.build({"schema_version": 2, "knowledge": []})

if __name__ == "__main__":
    unittest.main()
