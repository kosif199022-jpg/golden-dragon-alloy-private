import importlib.util
import unittest
from pathlib import Path

p = Path(__file__).resolve().parents[1] / "forge" / "instruction_blender.py"
spec = importlib.util.spec_from_file_location("instruction_blender", p)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class InstructionTests(unittest.TestCase):
    def test_dedup_and_sources(self):
        entries = [
            {"text": "# One\nAlways verify the output.", "sources": [{"path": "a"}]},
            {"text": "# Two\nAlways verify the output.", "sources": [{"path": "b"}]},
        ]
        result = mod.extract(entries)
        self.assertEqual(len(result), 1)
        self.assertEqual({s["path"] for s in result[0]["sources"]}, {"a", "b"})
    def test_negative_instruction_retained(self):
        result = mod.extract([{"text": "# Security\nNever expose secret credentials.", "sources": [{"path": "a"}]}])
        self.assertEqual(len(result), 1)
        self.assertTrue(result[0]["negative"])

if __name__ == "__main__":
    unittest.main()
