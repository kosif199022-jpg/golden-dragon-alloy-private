"""V29 tests: bias-aware decision reviews, editable video beats and RTL layout."""
import math
import unittest
from intelligence_director_v29 import run, OPS


class V29IntelligenceTests(unittest.TestCase):
    def _options(self):
        return [{"id":"unverified","benefit":10,"risk":5,"cost":2,
                 "reversible":.5,"estimated_success":.99,"base_rate":.2,
                 "evidence":[]},
                {"id":"measured","benefit":8,"risk":1,"cost":2,
                 "reversible":.9,"estimated_success":.8,"base_rate":.75,
                 "evidence":["verified","verified","measured"]}]

    def test_unverified_confidence_is_shrunk_to_base_rate(self):
        r=run("decision_review",{"goal":"Choose safe media export","options":self._options()})
        first=next(x for x in r["ranking"] if x["id"]=="unverified")
        self.assertEqual(first["calibrated_success"],.2)
        self.assertIn("possible_overconfidence",first["flags"])
        self.assertEqual(r["leading_option"],"measured")
        self.assertEqual(r["status"],"advisory_not_executed")

    def test_irreversible_option_needs_human(self):
        o=self._options();o[0]["reversible"]=0;o[0]["risk"]=9
        r=run("decision_review",{"goal":"Delete media","options":o})
        self.assertTrue(r["human_review_required"])

    def test_high_stakes_and_urgency_need_human(self):
        r=run("decision_review",{"goal":"Medical claim","options":self._options(),"high_stakes":True})
        self.assertTrue(r["human_review_required"])
        r=run("decision_review",{"goal":"Immediate task","options":self._options(),"deadline_hours":2})
        self.assertTrue(r["human_review_required"])

    def test_external_truth_not_inferred(self):
        a=run("decision_review",{"goal":"Evidence","options":self._options()})
        self.assertIn("user-supplied assumptions",a["warning"])

    def test_reject_malformed_options(self):
        cases=[
            {"goal":"bad","options":[self._options()[0]]},
            {"goal":"bad","options":[self._options()[0],dict(self._options()[0])]},
            {"goal":"bad","options":[dict(self._options()[0],evidence=["bogus"]),self._options()[1]]},
            {"goal":"bad","options":[dict(self._options()[0],estimated_success=float("nan")),self._options()[1]]},
            {"goal":"bad","options":self._options(),"cmd":"rm -rf /"},
        ]
        for x in cases:
            with self.subTest(x=x),self.assertRaises(ValueError):
                run("decision_review",x)

    def _story(self, **override):
        spec={"goal":"مونتاج تعليمي","seconds":6,"fps":24,"style":"toon",
              "beats":[{"label":"مقدمة","caption":"العلم جميل","weight":1},
                       {"label":"الفكرة","caption":"A1 فيزياء الحركة","weight":2},
                       {"label":"نهاية","caption":"شاهد النتيجة","weight":1}]}
        spec.update(override)
        return run("storyboard_plan",spec)

    def test_exact_total_frames_and_nonoverlap(self):
        r=self._story()
        self.assertEqual(r["total_frames"],144)
        self.assertEqual(sum(s["duration_frames"] for s in r["shots"]),144)
        self.assertEqual(r["shots"][-1]["end_frame_exclusive"],144)
        for a,b in zip(r["shots"],r["shots"][1:]):
            self.assertEqual(a["end_frame_exclusive"],b["start_frame"])
        self.assertEqual(r["status"],"editable_plan_not_rendered")

    def test_arabic_caption_kept_whole_words(self):
        r=self._story(has_voice=True)
        self.assertEqual(r["shots"][0]["caption_text"],"العلم جميل")
        self.assertEqual(r["shots"][1]["text_direction"],"rtl")
        self.assertTrue(all(s["text_animation_unit"]=="whole_word" for s in r["shots"]))
        self.assertIn("word_alignment_requires_real_audio_or_trusted_timestamps",r["open_reviews"])

    def test_rights_flag_exposed_without_publish(self):
        r=self._story(assets_rights_confirmed=False)
        self.assertIn("verify_asset_rights_before_render_or_publish",r["open_reviews"])
        r2=self._story(assets_rights_confirmed=True)
        self.assertNotIn("verify_asset_rights_before_render_or_publish",r2["open_reviews"])

    def test_styles_and_aspect_validation(self):
        r=self._story(style="saas",aspect="16:9")
        self.assertEqual(r["canvas"],{"width":1920,"height":1080})
        with self.assertRaises(ValueError):
            self._story(style="python-exec")
        with self.assertRaises(ValueError):
            self._story(fps=True)

    def test_many_shots_below_duration_rejected(self):
        with self.assertRaises(ValueError):
            self._story(seconds=5,beats=[{"label":str(i)} for i in range(12)])

    def test_layout_nonoverflow_and_rtl(self):
        r=run("layout_audit",{"width":500,"height":180,"padding":10,
             "gap":10,"direction":"row","rtl":True,
             "items":[{"id":"logo","min_size":80,"weight":1},
                      {"id":"title","min_size":180,"weight":3}]})
        self.assertEqual(r["overflow_pixels"],0)
        self.assertEqual(len(r["placements"]),2)
        a,b=r["placements"]
        self.assertGreater(a["x"],b["x"])
        self.assertEqual(a["width"]+b["width"]+10,480)

    def test_layout_overflow_reported(self):
        r=run("layout_audit",{"width":200,"height":120,"direction":"row",
             "items":[{"id":"a","min_size":150},{"id":"b","min_size":150}]})
        self.assertGreater(r["overflow_pixels"],0)
        self.assertIn("items_overflow_major_axis",r["warnings"])

    def test_layout_invalid_schema_rejected(self):
        with self.assertRaises(ValueError):
            run("layout_audit",{"width":500,"height":500,"items":[{"id":"a","script":"pwn"}]})
        with self.assertRaises(ValueError):
            run("layout_audit",{"width":500,"height":500,"items":[{"id":"x"},{"id":"x"}]})
        with self.assertRaises(ValueError):
            run("unknown",{})

    def test_ops_are_bounded(self):
        self.assertEqual(set(OPS),{"decision_review","storyboard_plan","layout_audit"})


if __name__=="__main__":
    unittest.main()
