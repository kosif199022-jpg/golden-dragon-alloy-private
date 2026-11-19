import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

p = Path(__file__).resolve().parents[1] / "forge" / "similarity_triage.py"
spec = importlib.util.spec_from_file_location("similarity_triage", p)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class SimilarityTriageTests(unittest.TestCase):
    def test_numbers_and_negation_are_not_merged(self):
        self.assertIn("different_numbers", mod.classify(
            "Step 3 of 6 for review", "Step 6 of 6 for review")["risk_flags"])
        self.assertIn("different_negation", mod.classify(
            "Never delete source materials", "Delete source materials")["risk_flags"])
        self.assertEqual(mod.classify(
            "Never delete source materials", "Delete source materials")["classification"], "review_required")

    def test_source_preserving_format_merge(self):
        first = {"text": "Follow safety checks before deploying.", "sources": [{"path": "one"}]}
        second = {"text": "Follow safety checks before deploying;", "sources": [{"path": "two"}]}
        third = {"text": "Always check release notes.", "sources": [{"path": "three"}]}
        brain = {"instructions": [first, second, third],
                 "quality_quarantine": [{"instruction": {"text": "Hold for review"}}],
                 "requires_review": [{"text": "Potential conflict"}]}
        pair = {"left_index": 0, "right_index": 1,
                "left_text": first["text"], "right_text": second["text"]}
        enriched, safe = mod.triage(brain, [pair])
        self.assertEqual(len(safe), 1)
        self.assertEqual(enriched[0]["classification"], "safe_format_only")
        preview, ledger = mod.make_preview(brain, safe)
        self.assertEqual(len(preview["instructions"]), 2)
        self.assertEqual(len(ledger), 1)
        merged = preview["instructions"][0]
        self.assertEqual(len(merged["verified_format_fusion"]["variants"]), 2)
        self.assertEqual(len(merged["sources"]), 2)
        self.assertEqual(len(preview["quality_quarantine"]), 1)
        self.assertEqual(len(preview["requires_review"]), 1)
        self.assertEqual(len(brain["instructions"]), 3)

    def test_reject_stale_candidates(self):
        brain = {"instructions": [{"text": "do not delete"}]}
        with self.assertRaises(ValueError):
            mod.triage(brain, [{"left_index": 0, "right_index": 2,
                                "left_text": "do not delete", "right_text": "delete"}])
        self.assertEqual(mod.classify(
            "allowed-tools: Read Bash", "allowed-tools: Read Bash Write")["classification"],
            "review_required")

if __name__ == "__main__":
    unittest.main()
