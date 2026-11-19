import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

p = Path(__file__).resolve().parents[1] / "forge" / "quality_gate.py"
spec = importlib.util.spec_from_file_location("quality_gate", p)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class QualityGateTests(unittest.TestCase):
    def test_quarantine_preserves_all_sources(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            a = {"text": "Always verify reports", "sources": [{"path": "a"}]}
            b = {"text": "Never reveal keys", "sources": [{"path": "b"}]}
            c = {"text": "Use safe logging", "sources": [{"path": "c"}]}
            (root / "brain.json").write_text(json.dumps({"instructions": [a, b], "requires_review": [c]}))
            (root / "review.json").write_text(json.dumps([{"text": b["text"], "context_matches": [{"source": "b", "line": 4}]}]))
            report = mod.build(root / "brain.json", root / "review.json", root / "out")
            self.assertEqual(report["preserved_total"], 3)
            self.assertEqual(report["quality_quarantined"], 1)
            gated = json.loads((root / "out" / "brain_quality_gated.json").read_text())
            self.assertEqual(gated["instructions"], [a])
            self.assertEqual(gated["quality_quarantine"][0]["instruction"], b)
            self.assertEqual(gated["requires_review"], [c])

if __name__ == "__main__":
    unittest.main()
