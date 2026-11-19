import importlib.util
import unittest
from pathlib import Path
p = Path(__file__).resolve().parents[1] / "forge" / "brain_quality.py"
spec = importlib.util.spec_from_file_location("brain_quality", p)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
class QualityTests(unittest.TestCase):
    def test_flags_incomplete_fragment(self):
        result = mod.audit([{"text": "mechanisms or framework candidates; verify their actual Skill sources before", "sources": [{"path": "a"}]}])
        self.assertEqual(len(result), 1)
        self.assertIn("fragment_start", result[0]["reasons"])
    def test_preserves_valid_sentence(self):
        self.assertEqual(mod.audit([{"text": "Always verify the output before delivery.", "sources": [{"path": "b"}]}]), [])
if __name__ == "__main__":
    unittest.main()
