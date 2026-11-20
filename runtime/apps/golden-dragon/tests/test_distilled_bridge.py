"""Opt-in bridge tests without importing the full app."""
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

FORGE = Path(__file__).resolve().parents[1] / "forge"
spec = importlib.util.spec_from_file_location("gd_distilled_bridge", FORGE / "modules" / "gd_distilled_bridge.py")
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)

class BridgeTests(unittest.TestCase):
    def test_missing_index_is_disabled(self):
        self.assertFalse(bridge.distilled_search("animation", index_path="/nonexistent/gd-index.json")["enabled"])

    def test_search_is_read_only_and_preserves_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "index.json"
            index = {"schema_version": 1, "knowledge": [
                {"heading": "Animation", "body": "Create animation frames",
                 "source": "animation/SKILL.md", "fingerprint": "123"}]}
            path.write_text(json.dumps(index), encoding="utf-8")
            before = path.read_bytes()
            result = bridge.distilled_search("animation", index_path=path)
            self.assertTrue(result["enabled"])
            self.assertEqual(result["results"][0]["source"], "animation/SKILL.md")
            self.assertEqual(path.read_bytes(), before)

if __name__ == "__main__":
    unittest.main()
