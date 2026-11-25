"""V43 independent fusion tests: Abu Cap SVG continuity and Super Mind measurement gates."""
import math
import sqlite3
import unittest
from xml.etree import ElementTree

import reel_motion_v43 as reel
import super_mind_v43 as mind
from capability_runtime import REGISTRY, CODED_UNTESTED, execute


def _run_case(system, count=36, success_first=0):
    cats=("normal","noisy","ambiguous","unsafe","legacy","out_of_scope")
    return {"system_sha":system*64,"split":"heldout",
            "cases":[{"id":"case-%03d"%i,"fingerprint":("%064x"%(i+1)),
                      "category":cats[i%len(cats)],
                      "passed":i<success_first} for i in range(count)]}


class ReelV43Tests(unittest.TestCase):
    def test_story_has_contiguous_eight_beats_and_660_frames(self):
        x=reel.run("story",{})
        self.assertEqual(x["total_frames"],660)
        self.assertEqual(x["fps"],30)
        self.assertEqual(len(x["beats"]),8)
        self.assertEqual(x["beats"][0]["start_frame"],0)
        self.assertEqual(x["beats"][-1]["end_frame_exclusive"],660)
        for a,b in zip(x["beats"],x["beats"][1:]):
            self.assertEqual(a["end_frame_exclusive"],b["start_frame"])
        self.assertFalse(x["audio_embedded"])
        self.assertFalse(x["original_media_embedded"])

    def test_ladder_and_lion_change_by_timing(self):
        checks={0:"hidden",9:"carried_by_lion",12:"leaning_on_tree",
                17:"hidden",18:"carried_by_cap"}
        for t,expected in checks.items():
            with self.subTest(t=t):
                self.assertEqual(reel.run("pose",{"seconds":t})["ladder"],expected)
        self.assertEqual(reel.run("pose",{"seconds":15})["lion_primary"]["pose"],"sleep")
        self.assertEqual(reel.run("pose",{"seconds":20})["beat"],"الخاتمة")

    def test_svg_is_original_parseable_and_escapes_captions(self):
        x=reel.run("svg",{"seconds":11.5,"caption":"<script>عربي & نص</script>"})
        root=ElementTree.fromstring(x["svg"])
        self.assertTrue(root.tag.endswith("svg"))
        self.assertNotIn("<script>",x["svg"])
        self.assertIn("&lt;script&gt;",x["svg"])
        self.assertIn("عربي",x["svg"])
        self.assertEqual(x["status"],"original_svg_frame_not_video")

    def test_reel_rejects_outside_bounds_or_injected_args(self):
        for op,params in [
            ("pose",{"seconds":-1}),("pose",{"seconds":22.1}),
            ("pose",{"seconds":float("nan")}),
            ("svg",{"seconds":3,"shell":"rm -rf /"}),
            ("svg",{"seconds":3,"caption":"X"*101}),
            ("story",{"anything":1}),("render",{})]:
            with self.subTest(op=op,params=params),self.assertRaises(ValueError):
                reel.run(op,params)


class SuperMindV43Tests(unittest.TestCase):
    def test_ladder_does_not_allow_skipping_evidence(self):
        x=mind.run("ladder",{"stages":[
            {"stage":"understand","artifact":"01_brief.md","evidence_ids":["A-1"],"done":True},
            {"stage":"ground","artifact":"02_map.md","evidence_ids":[],"done":True},
            {"stage":"baseline","artifact":"03_baseline.md","evidence_ids":["run_1"],"done":True}]})
        self.assertEqual(x["next_stage"],"ground")
        self.assertEqual(x["stages"][2]["status"],"blocked_out_of_order")
        self.assertFalse(x["complete_claimed"])
        self.assertTrue(x["needs_independent_checks"])

    def test_ladder_deep_warns_about_independent_critic(self):
        x=mind.run("ladder",{"mode":"deep"})
        self.assertIn("deep_mode_independent_critic",x["high_risk_requirements"])
        self.assertEqual(x["next_stage"],"understand")

    def test_organ_score_exact_twelve_and_critical_na_rejected(self):
        scores={name:{"score":2,"evidence":["check-123"],"reason":"case evidence"} for name in mind.ORGANS}
        x=mind.run("organ_audit",{"scores":scores})
        self.assertEqual(len(x["organs"]),12)
        self.assertEqual(x["score_fraction"],0.5)
        self.assertTrue(x["eligible_for_external_audit"])
        scores["safety"]["score"]="na"
        y=mind.run("organ_audit",{"scores":scores})
        self.assertIn("critical_organ_cannot_be_na:safety",y["blocking_checks"])

    def test_unsubstantiated_high_scores_are_blocked(self):
        scores={name:{"score":1,"evidence":[],"reason":"user assessment"} for name in mind.ORGANS}
        scores["intent"]["score"]=4
        scores["verification"]["score"]=4
        out=mind.run("organ_audit",{"scores":scores})
        self.assertIn("high_score_without_evidence:intent",out["blocking_checks"])
        self.assertIn("high_score_without_evidence:verification",out["blocking_checks"])

    def test_paired_same_case_36_improvement_passes_math_gate(self):
        before=_run_case("a",36,5)
        after=_run_case("b",36,36)
        out=mind.run("paired_compare",{"before":before,"after":after})
        self.assertEqual(out["improved_cases"],31)
        self.assertEqual(out["regressed_cases"],0)
        self.assertEqual(out["missing_categories"],[])
        self.assertTrue(out["gate_passed"])
        self.assertTrue(out["only_self_reported_results"])

    def test_small_n_not_claimed_as_proven(self):
        before=_run_case("a",6,0)
        after=_run_case("b",6,6)
        out=mind.run("paired_compare",{"before":before,"after":after})
        self.assertFalse(out["gate_passed"])
        self.assertEqual(out["status"],"insufficient_or_regressed")

    def test_matching_case_fingerprint_and_different_sha_required(self):
        before=_run_case("a",36,1)
        after=_run_case("a",36,36)
        with self.assertRaisesRegex(ValueError,"different version"):
            mind.run("paired_compare",{"before":before,"after":after})
        after["system_sha"]="b"*64
        after["cases"][0]["fingerprint"]="9"*64
        with self.assertRaisesRegex(ValueError,"case changed"):
            mind.run("paired_compare",{"before":before,"after":after})

    def test_unsafe_regression_blocks_positive_gate(self):
        before=_run_case("a",36,10)
        after=_run_case("b",36,36)
        # Five failures fixed, but a previous unsafe good case breaks.
        after["cases"][3]["passed"]=False
        x=mind.run("paired_compare",{"before":before,"after":after})
        self.assertFalse(x["gate_passed"])
        self.assertIn("case-003",x["unsafe_regressions"])

    def test_validation_rejects_unsafe_unknown_payload(self):
        for op,p in [("ladder",{"execute":"cmd"}),("organ_audit",{"scores":{}}),
                     ("paired_compare",{"before":{},"after":{}}),("execute",{})]:
            with self.subTest(op=op),self.assertRaises(ValueError):
                mind.run(op,p)


class V43RegistryTests(unittest.TestCase):
    def test_both_registered_and_read_only(self):
        self.assertEqual(len(REGISTRY),65)
        for name in ("reel.motion","mind.audit"):
            self.assertIn(name,REGISTRY)
            self.assertEqual(REGISTRY[name][1],"read")
            self.assertNotIn(name,CODED_UNTESTED)

    def test_dispatch_works_and_legacy_never_runs(self):
        with sqlite3.connect(":memory:") as db:
            for name,op,params in (
                    ("reel.motion","pose",{"seconds":11}),
                    ("mind.audit","ladder",{})):
                result=execute(db,name,{"op":op,"params":params})
                self.assertEqual(result["status"],"executed")
                self.assertEqual(result["effect"],"read")
                self.assertFalse(result["legacy_runtime_called"])
            count=db.execute("SELECT count(*) FROM capability_execution_audit").fetchone()[0]
            self.assertEqual(count,2)


if __name__=="__main__":
    unittest.main()
