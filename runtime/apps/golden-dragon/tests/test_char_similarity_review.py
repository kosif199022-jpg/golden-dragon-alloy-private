import importlib.util
import unittest
from pathlib import Path

p = Path(__file__).resolve().parents[1] / "forge" / "char_similarity_review.py"
spec = importlib.util.spec_from_file_location("char_similarity_review", p)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class CharReviewTests(unittest.TestCase):
    def test_discovers_rewordings_without_auto_merge(self):
        values = [
            {"text": "Always verify invoice totals against the original purchase documents.", "sources": [{"path": "a"}]},
            {"text": "Always verify invoice totals against original purchase documents.", "sources": [{"path": "b"}]},
            {"text": "Generate animated three dimensional scenes with custom lighting and rendering.", "sources": [{"path": "c"}]},
        ]
        pairs, stats = mod.find_pairs(values, threshold=.75)
        self.assertTrue(any(x["left_index"] == 0 and x["right_index"] == 1 for x in pairs))
        self.assertTrue(all(x["decision"] == "pending_manual_review" for x in pairs))
        self.assertEqual(pairs[0]["left_sources"][0]["path"], "a")
        self.assertEqual(stats["compared"], 3)

    def test_arabic_and_negation_warning(self):
        self.assertTrue(mod.opposition_hint(
            "Never overwrite an existing database without user approval.",
            "Overwrite an existing database without user approval."))
        self.assertTrue(mod.opposition_hint(
            "\u0644\u0627 \u062a\u062d\u0630\u0641 \u0627\u0644\u0645\u0644\u0641\u0627\u062a \u0627\u0644\u0623\u0635\u0644\u064a\u0629 \u0628\u0639\u062f \u0627\u0644\u062f\u0645\u062c",
            "\u0627\u062d\u0641\u0638 \u0627\u0644\u0645\u0644\u0641\u0627\u062a \u0627\u0644\u0623\u0635\u0644\u064a\u0629 \u0628\u0639\u062f \u0627\u0644\u062f\u0645\u062c"))
        self.assertFalse(mod.opposition_hint(
            "Never overwrite an existing database.", "Do not overwrite an existing database."))

    def test_no_matches_for_empty(self):
        pairs, stats = mod.find_pairs([{"text": ""}])
        self.assertEqual(pairs, [])
        self.assertEqual(stats["compared"], 0)

if __name__ == "__main__":
    unittest.main()
