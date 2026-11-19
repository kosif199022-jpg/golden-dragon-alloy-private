import importlib.util
import unittest
from pathlib import Path

path = Path(__file__).resolve().parents[1] / "forge" / "cross_title_blender.py"
spec = importlib.util.spec_from_file_location("cross_title_blender", path)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class CrossTitleTests(unittest.TestCase):
    def test_similar_titles_preserve_both_sources(self):
        entries = [
            {"id": "a", "text": "# Python testing automation\none", "sources": [{"path": "a"}]},
            {"id": "b", "text": "# Testing automation Python\nanother", "sources": [{"path": "b"}]},
            {"id": "c", "text": "# Cooking pasta recipe\nthird", "sources": [{"path": "c"}]},
        ]
        clusters = mod.group(entries)
        self.assertEqual(len(clusters), 1)
        self.assertEqual({e["id"] for e in clusters[0]}, {"a", "b"})
        self.assertEqual({e["sources"][0]["path"] for e in clusters[0]}, {"a", "b"})
    def test_single_word_not_auto_merged(self):
        entries = [{"id": str(i), "text": "# Python\ntext", "sources": []} for i in range(2)]
        self.assertEqual(mod.group(entries), [])

if __name__ == "__main__":
    unittest.main()
