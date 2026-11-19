import importlib.util
import unittest
from pathlib import Path
p = Path(__file__).resolve().parents[1] / "forge" / "apply_approved_repairs.py"
spec = importlib.util.spec_from_file_location("apply_approved_repairs", p)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class ApprovalTests(unittest.TestCase):
    def setUp(self):
        self.original = {"text": "Always verify", "sources": [{"path": "a"}]}
        self.brain = {"instructions": [{"text": "Use source citations", "sources": [{"path": "b"}]}],
                      "quality_quarantine": [{"instruction": self.original, "quality_review": {}}],
                      "requires_review": [{"text": "Never expose keys"}]}
        self.queue = [{"original": "Always verify", "choices": [{"candidate": "Always verify results."}]}]
    def test_no_approvals_preserves_quarantine(self):
        output, n = mod.apply(self.brain, self.queue, [])
        self.assertEqual(n, 0)
        self.assertEqual(len(output["quality_quarantine"]), 1)
        self.assertEqual(len(output["instructions"]), 1)
    def test_explicit_approval_preserves_provenance(self):
        output, n = mod.apply(self.brain, self.queue, [
            {"original": "Always verify", "approved_candidate": "Always verify results."}])
        self.assertEqual(n, 1)
        self.assertEqual(output["instructions"][-1]["sources"][0]["path"], "a")
        self.assertEqual(len(output["requires_review"]), 1)
    def test_rejects_unlisted_candidate(self):
        with self.assertRaises(ValueError):
            mod.apply(self.brain, self.queue, [
                {"original": "Always verify", "approved_candidate": "Never verify"}])
if __name__ == "__main__":
    unittest.main()
