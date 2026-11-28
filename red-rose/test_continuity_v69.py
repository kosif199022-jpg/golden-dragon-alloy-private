import copy, unittest
from rose_continuity_v69 import check


def good():
    return {"fps": 30, "duration_frames": 270, "shots": [
        {"id": "1", "start_frame": 0, "end_frame": 90, "shot_type": "wide", "camera_move": "slow push-in",
         "subject_motion": "hero walks along the platform", "action_start": "reaches for the bench",
         "state": {"location": "station platform", "wardrobe.hero": "red coat", "prop.bench": "facing left"}},
        {"id": "2", "start_frame": 90, "end_frame": 180, "shot_type": "medium", "camera_move": "drift right",
         "subject_motion": "hero turns the bench", "action_result": "hand lands on the bench and turns it",
         "state": {"prop.bench": "facing camera"}, "changes": {"prop.bench": "hero turned it in this shot"}},
        {"id": "3", "start_frame": 180, "end_frame": 270, "shot_type": "close-up", "camera_move": "handheld sway",
         "subject_motion": "hero sits and exhales", "cut_in": "hard", "hard_cut_reason": "reveal of the letter"},
    ]}


def codes(r):
    return {i["code"] for i in r["issues"]}


class Continuity69(unittest.TestCase):
    def test_pass(self):
        r = check(good())
        self.assertEqual(r["status"], "pass", r["issues"])
        self.assertEqual(r["seconds"], 9.0)
        self.assertEqual(r["justified_changes"][0]["key"], "prop.bench")
        self.assertFalse(r["rendered_frames_checked"])

    def test_silent_drift(self):
        s = good(); s["shots"][2]["state"] = {"wardrobe.hero": "blue coat"}
        r = check(s); self.assertIn("continuity_drift", codes(r)); self.assertEqual(r["status"], "review_required")

    def test_carry_forward_detects_drift_later(self):
        s = good(); s["shots"][2]["state"] = {"prop.bench": "facing left"}  # reverts with no reason
        self.assertIn("continuity_drift", codes(check(s)))

    def test_gap_overlap_duration(self):
        s = good(); s["shots"][1]["start_frame"] = 95
        self.assertIn("timeline_gap", codes(check(s)))
        s = good(); s["shots"][1]["start_frame"] = 80
        self.assertIn("timeline_overlap", codes(check(s)))
        s = good(); s["duration_frames"] = 300
        self.assertIn("duration_mismatch", codes(check(s)))

    def test_slideshow(self):
        s = good(); s["shots"][1]["camera_move"] = "static"; s["shots"][1]["subject_motion"] = ""
        c = codes(check(s)); self.assertTrue({"static_camera", "no_subject_motion"} <= c)
        s["allow_static"] = True
        self.assertFalse({"static_camera", "no_subject_motion"} & codes(check(s)))

    def test_repeated_shot_type_and_dangling_action(self):
        s = good(); s["shots"][1]["shot_type"] = "wide"; del s["shots"][1]["action_result"]
        c = codes(check(s)); self.assertTrue({"repeated_shot_type", "dangling_action"} <= c)

    def test_hard_cut_needs_reason(self):
        s = good(); del s["shots"][2]["hard_cut_reason"]
        self.assertIn("unjustified_hard_cut", codes(check(s)))

    def test_camera_variety_and_short_beat(self):
        s = good()
        for sh in s["shots"]:
            sh["camera_move"] = "slow push-in"
        self.assertIn("camera_not_varied", codes(check(s)))
        s = good(); s["shots"][0]["end_frame"] = 10; s["shots"][1]["start_frame"] = 10
        self.assertIn("very_short_beat", codes(check(s)))

    def test_rejects_bad_input(self):
        for bad in ({"shots": []}, {"fps": 29.97, "shots": good()["shots"]}):
            with self.assertRaises(ValueError):
                check(bad)
        s = good(); s["shots"][0]["end_frame"] = 90.5
        with self.assertRaises(ValueError):
            check(s)
        s = good(); s["shots"][1]["id"] = "1"
        with self.assertRaises(ValueError):
            check(s)


if __name__ == "__main__":
    unittest.main()
