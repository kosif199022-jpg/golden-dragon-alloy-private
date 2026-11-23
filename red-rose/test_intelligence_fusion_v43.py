"""Red Rose V43 — meaningful tests for distilled cognition and reel timing."""
from __future__ import annotations
import json
import unittest
from pathlib import Path
from intelligence_fusion_v43 import ORGANS, STEPS, OPS, run

ROOT = Path(__file__).resolve().parent
SOURCE = json.loads((ROOT/"examples"/"abu_kab_reel_v43.json").read_text(encoding="utf-8"))
REEL_KEYS = ("title","width","height","fps","frames","shots",
             "frame_inventory_count","music","seekable")


def reel():
    return {name:SOURCE[name] for name in REEL_KEYS}


def organs(score=2):
    return [{"id":x, "score":score, "evidence":[]} for x in ORGANS]


def cases(heldout=24):
    return [{"id":f"case_{i}", "case_sha":f"{i+99:064x}",
             "split":"heldout", "category":"unsafe" if i==0 else "normal",
             "before_pass":False, "after_pass":True} for i in range(heldout)]


def evaluation(**updates):
    x={"before_sha":"a"*64, "after_sha":"b"*64,
       "cases":cases(), "heldout_systems_seen":2}
    x.update(updates)
    return x


class SourceFusionTests(unittest.TestCase):
    def test_declared_ops_and_organ_count(self):
        self.assertEqual(len(OPS),7)
        self.assertEqual(len(ORGANS),12)
        self.assertEqual(len(STEPS),9)

    def test_readiness_is_not_invented_iq(self):
        r=run("readiness",{"app":"Red Rose","organs":organs(2)})
        self.assertEqual(r["readiness_index"],50)
        self.assertEqual(r["provisional_band"],"L2")
        self.assertEqual(r["status"],"self_reported_readiness_not_certified")

    def test_high_organs_without_evidence_flagged(self):
        r=run("readiness",{"organs":organs(4)})
        self.assertEqual(len(r["evidence_missing_for_high_scores"]),12)
        self.assertEqual(r["readiness_index"],100)
        self.assertIn("not_certified",r["status"])

    def test_critical_organs_cannot_be_na(self):
        oscores=organs()
        oscores[-3]["score"]=None   # learning
        with self.assertRaises(ValueError):
            run("readiness",{"organs":oscores})

    def test_missing_or_duplicate_organ_rejected(self):
        scores=organs()
        scores[1]["id"]="intent"
        with self.assertRaises(ValueError):
            run("readiness",{"organs":scores})

    def test_ladder_next_step_requires_evidence(self):
        r=run("ladder",{"stages":[{"step":"understand","passed":True,
                                 "evidence":["brief.md:12"]}]})
        self.assertEqual(r["next_step"],"ground")
        self.assertFalse(r["all_stages_claimed_passed"])
        with self.assertRaises(ValueError):
            run("ladder",{"stages":[{"step":"understand","passed":True}]})

    def test_ladder_cannot_skip_or_masquerade_as_verified(self):
        with self.assertRaises(ValueError):
            run("ladder",{"stages":[{"step":"prove","passed":True,"evidence":["x"]}]})
        done=[{"step":x,"passed":True,"evidence":[f"evidence:{i}"]}
              for i,x in enumerate(STEPS)]
        r=run("ladder",{"stages":done})
        self.assertTrue(r["all_stages_claimed_passed"])
        self.assertIn("not_independently_verified",r["status"])

    def test_paired_eval_detects_large_heldout_gain(self):
        r=run("paired_eval",evaluation())
        self.assertEqual(r["heldout_count"],24)
        self.assertEqual(r["heldout_improved"],24)
        self.assertEqual(r["heldout_regressed"],0)
        self.assertTrue(r["gate_met"])
        self.assertLess(r["mcnemar_exact_p"],.05)
        self.assertIn("requires_independent_review",r["verdict"])

    def test_paired_eval_rejects_same_binary(self):
        with self.assertRaises(ValueError):
            run("paired_eval",evaluation(after_sha="a"*64))

    def test_paired_eval_does_not_certify_contaminated_heldout(self):
        r=run("paired_eval",evaluation(heldout_systems_seen=3))
        self.assertTrue(r["heldout_contaminated"])
        self.assertEqual(r["verdict"],"not_established")

    def test_paired_eval_blocks_unsafe_regression(self):
        payload=evaluation()
        payload["cases"][0]["before_pass"]=True
        payload["cases"][0]["after_pass"]=False
        r=run("paired_eval",payload)
        self.assertEqual(r["unsafe_regressions"],["case_0"])
        self.assertFalse(r["gate_met"])

    def test_paired_eval_not_established_with_small_sample(self):
        r=run("paired_eval",evaluation(cases=cases(6)))
        self.assertFalse(r["gate_met"])
        self.assertEqual(r["verdict"],"not_established")

    def test_abu_kab_source_scene_coverage_and_credit(self):
        r=run("reel_preflight",reel())
        self.assertEqual(r["frames"],660)
        self.assertEqual(r["fps"],30)
        self.assertEqual(r["duration_seconds"],22)
        self.assertEqual(r["shot_count"],6)
        self.assertTrue(r["preflight_passed"],r["warnings"])
        self.assertIn("CC BY 3.0",r["music_attribution"])
        self.assertIn("not_media_verified",r["status"])

    def test_seek_is_deterministic_and_cannot_execute_html(self):
        p=reel()
        a=run("reel_seek",{"project":p,"time_seconds":2.8})
        b=run("reel_seek",{"project":p,"time_seconds":2.8})
        self.assertEqual(a,b)
        self.assertEqual(a["frame"],84)
        self.assertEqual(a["shot_id"],"climb")
        last=run("reel_seek",{"project":p,"time_seconds":21.9})
        self.assertEqual(last["shot_id"],"endcard")
        self.assertEqual(last["tag"],"cta")
        with self.assertRaises(ValueError):
            run("reel_seek",{"project":p,"time_seconds":22})

    def test_reel_gap_and_missing_music_credit_flagged(self):
        p=reel()
        p["shots"]=[dict(x) for x in p["shots"]]
        p["shots"][2]["start_frame"]=180
        p["music"]={**p["music"],"attribution":""}
        r=run("reel_preflight",p)
        self.assertFalse(r["preflight_passed"])
        self.assertIn("gap_or_overlap_before_false_safety",r["warnings"])
        self.assertIn("music_credit_or_license_link_missing",r["warnings"])

    def test_reel_frame_inventory_guard(self):
        p=reel(); p["frame_inventory_count"]=659
        r=run("reel_preflight",p)
        self.assertIn("frame_inventory_mismatch",r["warnings"])

    def test_rig_event_script_not_executable_in_audit(self):
        p=reel()
        p["shell"]="rm -rf /"
        with self.assertRaises(ValueError):
            run("reel_preflight",p)
        with self.assertRaises(ValueError):
            run("anything",{})


if __name__=="__main__":
    unittest.main()
