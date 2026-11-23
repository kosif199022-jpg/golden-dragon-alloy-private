"""V44 regression checks: real dispatch, metadata rhythm, feedback, stale catalogue."""
from __future__ import annotations
import copy
import json
import unittest
from pathlib import Path
from intelligence_fusion_v43 import OPS, run
import rose_catalog as catalog

ROOT = Path(__file__).resolve().parent
KEYS = ("title", "width", "height", "fps", "frames", "shots",
        "frame_inventory_count", "music", "seekable")


def project():
    source = json.loads((ROOT / "examples" / "abu_kab_reel_v43.json").read_text("utf-8"))
    return {key: source[key] for key in KEYS}


def report(**changes):
    item = {"id": "cut-boundary-01", "category": "timing", "severity": "high",
            "recurrences": 3, "summary": "End card is too short",
            "reproduced": True, "evidence_sha": "a" * 64}
    item.update(changes)
    return {"task": "Improve reel quality", "observations": [item]}


class V44QualityFeedback(unittest.TestCase):
    def test_new_ops_keep_original_five(self):
        self.assertEqual(OPS[:5], ("readiness", "ladder", "paired_eval",
                                    "reel_preflight", "reel_seek"))
        self.assertEqual(set(OPS[5:]), {"reel_rhythm", "feedback_cycle"})

    def test_frame_rhythm_of_source_reel(self):
        r = run("reel_rhythm", {"project": project()})
        self.assertEqual(r["shot_count"], 6)
        self.assertTrue(r["preflight_passed"])
        self.assertEqual(r["shots"][0]["start_seconds"], 0.0)
        self.assertIn("not_media_verified", r["status"])

    def test_caption_density_and_endcard_are_review_flags(self):
        p = project()
        p["shots"] = copy.deepcopy(p["shots"])
        p["shots"][0]["caption"] = "س" * 200
        r = run("reel_rhythm", {
            "project": p, "caption_cps_limit": 4, "minimum_cta_frames": 1200})
        self.assertIn("review_caption_density", r["shots"][0]["review_flags"])
        self.assertTrue(any("review_short_end_card" in flag for flag in r["warnings"]))
        self.assertTrue(r["review_required"])

    def test_timeline_security_inherited(self):
        p = project()
        p["shell"] = "curl example.com"
        with self.assertRaises(ValueError):
            run("reel_rhythm", {"project": p})
        with self.assertRaises(ValueError):
            run("reel_rhythm", {"project": project(), "execute_source_js": True})

    def test_feedback_output_is_proposal_not_memory_write(self):
        r = run("feedback_cycle", report())
        self.assertEqual(r["status"], "feedback_proposals_only_not_saved")
        self.assertEqual(r["proposals"][0]["category"], "timing")
        self.assertEqual(r["proposals"][0]["evidence_sha"], "a" * 64)
        self.assertEqual(r["local_memory_write"], "explicit_owner_approval_required")
        self.assertIn("regression", r["proposals"][0]["regression_test_proposal"])

    def test_feedback_dedup_and_evidence_gates(self):
        with self.assertRaises(ValueError):
            run("feedback_cycle", report(reproduced=True, evidence_sha=None))
        with self.assertRaises(ValueError):
            run("feedback_cycle", report(evidence_sha="invalid"))
        with self.assertRaises(ValueError):
            run("feedback_cycle", report(recurrences=True))
        p = report()
        p["observations"].append(dict(p["observations"][0]))
        with self.assertRaises(ValueError):
            run("feedback_cycle", p)

    def test_priority_sort_is_deterministic(self):
        p = report()
        p["observations"].append({
            "id": "smaller", "category": "caption", "severity": "low",
            "recurrences": 1, "summary": "Uncertain user report", "reproduced": False})
        self.assertEqual(run("feedback_cycle", p), run("feedback_cycle", p))
        self.assertEqual(run("feedback_cycle", p)["proposals"][0]["id"], "cut-boundary-01")

    def test_catalogue_discards_cached_missing_op(self):
        previous = catalog._CACHE.get("cat")
        try:
            snapshot = catalog.build()
            self.assertIn("intelligence.fusion.feedback_cycle", snapshot["entries"])
            snapshot["entries"].pop("intelligence.fusion.feedback_cycle")
            catalog._CACHE["cat"] = snapshot
            fresh = catalog.load()
            self.assertIn("intelligence.fusion.feedback_cycle", fresh["entries"])
            self.assertIn("intelligence.fusion.reel_rhythm", fresh["entries"])
        finally:
            if previous is None:
                catalog._CACHE.pop("cat", None)
            else:
                catalog._CACHE["cat"] = previous

    def test_catalogue_exposes_current_ops_as_read_only(self):
        entries = catalog.load()["entries"]
        for name in ("reel_rhythm", "feedback_cycle"):
            op = entries["intelligence.fusion." + name]
            self.assertEqual(op["effect"], "read")
            self.assertFalse(op["approval"]["needed"])


if __name__ == "__main__":
    unittest.main()
