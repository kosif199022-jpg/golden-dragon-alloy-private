"""Integration tests for the actual generated Golden Dragon Windows application."""
import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

GD = Path(__file__).resolve().parents[1]
APP = GD / "app"
FORGE = GD / "forge"
sys.path.insert(0, str(APP))
import golden_knowledge_bridge as bridge

spec = importlib.util.spec_from_file_location("gd_knowledge", FORGE / "gd_patches" / "gd_knowledge.py")
patcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(patcher)


class GoldenKnowledgeIntegrationTests(unittest.TestCase):
    def test_repo_bundle_is_queryable_from_app_bridge(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(bridge, "CACHE", Path(temp)):
                database = bridge.verified_database()
                self.assertTrue(database.exists())
                self.assertGreater(database.stat().st_size, 1_000_000)
                info = bridge.status()
                self.assertTrue(info["ok"], info)
                self.assertEqual(info["counts"]["active"], 16315)
                output = bridge.search("python testing", limit=2)
                self.assertTrue(output["ok"], output)
                self.assertTrue(output["matches"])
                self.assertTrue(output["matches"][0]["sources"])
                tool_json, failure = bridge.dispatch({"action": "search", "query": "testing"})
                self.assertFalse(failure)
                self.assertTrue(json.loads(tool_json)["ok"])
                _, error = bridge.dispatch({"action": "execute", "query": "delete files"})
                self.assertTrue(error)

    def test_bad_zip_data_does_not_become_executable_or_cached(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            corrupt = root / "bad.zip"
            content = b"definitely not a sqlite database"
            manifest = {"files": {"golden_dragon.sqlite": {
                "bytes": len(content), "sha256": "0" * 64}}}
            with zipfile.ZipFile(corrupt, "w") as output:
                output.writestr("golden_dragon.sqlite", content)
                output.writestr("manifest.json", json.dumps(manifest))
            with self.assertRaises(ValueError):
                bridge.verified_database(corrupt, root / "cache")
            self.assertFalse((root / "cache" / "golden_dragon.sqlite").exists())

    def test_integrated_app_tracks_generated_stamp_and_build(self):
        stamp = json.loads((APP / ".gd_generated.json").read_text(encoding="utf-8"))
        self.assertIn("knowledge_integration", stamp)
        for rel, expected in stamp["files"].items():
            data = (APP / rel).read_bytes()
            self.assertEqual(hashlib.sha256(data).hexdigest(), expected, rel)
        app = (APP / "app.py").read_text(encoding="utf-8-sig")
        ui = (APP / "ui" / "index.html").read_text(encoding="utf-8-sig")
        build = (APP / "build.ps1").read_text(encoding="utf-8-sig")
        self.assertIn("def knowledge_search(self,", app)
        self.assertIn('tool("knowledge"', app)
        self.assertIn('name == "knowledge"', app)
        self.assertIn('id="gdkPane"', ui)
        self.assertIn("pywebview.api.knowledge_search", ui)
        self.assertIn("golden-dragon-runtime.zip;knowledge", build)
        self.assertIn("--hidden-import golden_knowledge_bridge", build)
        self.assertIn("--hidden-import golden_dragon_runtime", build)

    def test_generator_will_restore_app_integration(self):
        # Use self-contained fixtures, not backup files outside Git.
        base_app = (
            "import brain\n"
            '    tool("rebuild_app",\n'
            '        if name == "fusion":\n'
            '            return fusion_dispatch(a)\n'
            '    def brain_status(self):\n'
        )
        self.assertIn("knowledge_search", patcher.patch_app(base_app))
        self.assertIn('id="gdkPane"', patcher.patch_ui("<html><body></body></html>"))
        base_build = '--add-data "$here\\fusion;fusion" --hidden-import dragon_fusion'
        self.assertIn("golden-dragon-runtime.zip", patcher.patch_build(base_build))


if __name__ == "__main__":
    unittest.main()
