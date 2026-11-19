"""Regression checks for the Golden Dragon knowledge blender."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

FORGE = Path(__file__).resolve().parents[1] / "forge"

def load(name):
    spec = importlib.util.spec_from_file_location(name, FORGE / (name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

class BlenderTests(unittest.TestCase):
    def test_preserves_unique_and_deduplicates_exact(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "skills"
            for name, content in {
                "a": "# Search\nSearch docs safely.\n## Validate\nCheck sources.",
                "b": "# Search\nSearch docs safely.\n## Export\nWrite output.",
            }.items():
                path = root / name
                path.mkdir(parents=True)
                (path / "SKILL.md").write_text(content, encoding="utf-8")
            output = Path(tmp) / "out"
            report = load("skill_blender").blend(root, output)
            self.assertEqual(report["files_scanned"], 2)
            self.assertEqual(report["source_sections"], 4)
            self.assertEqual(report["unique_sections"], 3)
            entries = json.loads((output / "knowledge.json").read_text(encoding="utf-8"))
            self.assertEqual(max(len(x["sources"]) for x in entries), 2)
            semantic = load("semantic_blender").merge(output / "knowledge.json", output)
            self.assertEqual(semantic["variants"], 3)
            self.assertEqual(semantic["topics"], 3)

    def test_refuses_output_inside_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "skills"
            root.mkdir()
            with self.assertRaises(ValueError):
                load("skill_blender").blend(root, root / "out")

if __name__ == "__main__":
    unittest.main()
