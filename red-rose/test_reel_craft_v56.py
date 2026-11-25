"""V56 reel.craft: script check, story plan, steady-beat gate, delivery gate, gated credit overlay; safe unzip."""
import os
import random
import shutil
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path

import capability_runtime as cr
import media_library_v35
import reel_craft_v56 as rc

HAS_FF = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))

GOOD = "\n".join(["القهوجي مابياخدش فلوس على أول كوباية.",
                  "في قهوة صغيرة في شبرا، عم حسن بيصب الشاي من الفجر.",
                  "وبعدين ييجي الزبون التاني ويدفع عادي.",
                  "بس الكل كان بيضحك عليه.",
                  "وفجأة القهوة بقت مليانة كل يوم.",
                  "تعرف ليه؟ اللي يشرب أول كوباية ببلاش بيرجع.",
                  "وكوباية واحدة جابت شارع كامل."])


def _arabic_font():
    """A real Arabic-capable .ttf for the credit test, if this machine has one (never committed)."""
    env = os.environ.get("RED_ROSE_TEST_ARABIC_FONT")
    if env and Path(env).is_file():
        return env
    if shutil.which("fc-list"):
        out = subprocess.run(["fc-list", ":lang=ar", "file"], capture_output=True, text=True).stdout
        for line in out.splitlines():
            p = line.split(":")[0].strip()
            if p.lower().endswith((".ttf", ".otf")) and Path(p).is_file():
                return p
    return None


class ScriptCheck(unittest.TestCase):
    def test_good_egyptian_micro_fable_passes(self):
        r = rc.run("script_check", {"text": GOOD, "seconds": 23})
        self.assertTrue(r["ok"], [c for c in r["checks"] if not c["ok"]])

    def test_question_hook_greeting_and_mixed_dialect_fail(self):
        r = rc.run("script_check", {"text": "هل تعلم ليه الشاي بيتشرب سخن جدا كل يوم في مصر؟\nهسه نشوف.\nخلاص.", "seconds": 15})
        failed = {c["check"].split(" (")[0] for c in r["checks"] if not c["ok"]}
        self.assertFalse(r["ok"])
        self.assertIn("hook is a flat statement, not a question", failed)
        self.assertIn("no greeting / 'in this video' / 'wait till the end' opener", failed)
        self.assertTrue(any(c["check"].startswith("one register") and not c["ok"] for c in r["checks"]))

    def test_recorded_voice_skips_length_and_bad_register_is_rejected(self):
        r = rc.run("script_check", {"text": GOOD, "seconds": 60, "voice_recorded": True})
        self.assertTrue(r["ok"])
        with self.assertRaises(ValueError):
            rc.run("script_check", {"text": GOOD, "seconds": 20, "register": "xx"})
        with self.assertRaises(ValueError):
            rc.run("script_check", {"text": GOOD, "seconds": 20, "surprise": 1})


class StoryPlan(unittest.TestCase):
    def test_frames_add_up_light_changes_and_camera_never_stops(self):
        p = rc.run("story_plan", {"lines": GOOD.split("\n"), "seconds": 23, "fps": 30})
        self.assertEqual(p["frames"], 690)
        self.assertEqual(sum(s["frames"] for s in p["scenes"]), 690)
        lights = [s["light"] for s in p["scenes"]]
        self.assertEqual(lights[0], "day")
        self.assertEqual(lights[-1], "sunset")
        self.assertIn("golden", lights)
        self.assertTrue(all(a != b for a, b in zip(lights, lights[1:])), "a new scene only when the light changes")
        beats = p["camera_beats"]
        self.assertEqual(beats[0]["move"], "extreme_close_up_key_object")
        self.assertTrue(all(b2["frame"] - b1["frame"] <= 30 for b1, b2 in zip(beats, beats[1:])))
        moves = [b["move"] for b in beats[1:]]
        self.assertGreater(moves.count("push_in"), moves.count("pull_out"))


class TempoSteadiness(unittest.TestCase):
    def test_periodic_grid_gives_its_bpm(self):
        r = rc.run("tempo_steadiness", {"onsets": [0.1 + 0.5 * i for i in range(14)]})
        self.assertTrue(r["steady_beat"])
        self.assertEqual(r["bpm"], 120.0)

    def test_unrelated_impacts_never_get_a_bpm(self):
        r = rc.run("tempo_steadiness", {"onsets": [0.1, 0.46, 1.19, 1.77, 2.81, 3.17, 4.1, 5.55]})
        self.assertFalse(r["steady_beat"])
        self.assertIsNone(r["bpm"])
        false_pos = 0
        for seed in range(60):
            rng = random.Random(seed)
            t, ev = 0.0, [0.0]
            for _ in range(rng.randint(8, 40)):
                t += rng.uniform(0.2, 1.2)
                ev.append(t)
            false_pos += rc.run("tempo_steadiness", {"onsets": ev})["steady_beat"]
        self.assertEqual(false_pos, 0)

    def test_jittered_real_tempi_are_found(self):
        for seed in range(20):
            rng = random.Random(1000 + seed)
            bpm = rng.uniform(70, 190)
            ev = [0.3 + i * 60 / bpm + rng.uniform(-0.02, 0.02) for i in range(rng.randint(12, 40))]
            r = rc.run("tempo_steadiness", {"onsets": ev})
            self.assertTrue(r["steady_beat"], (bpm, r))
            self.assertLess(min(abs(r["bpm"] - bpm), abs(r["bpm"] - 2 * bpm), abs(r["bpm"] - bpm / 2)), 1.0)


@unittest.skipUnless(HAS_FF, "ffmpeg/ffprobe not installed")
class MediaOps(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="rose-v56-test-"))
        self.src = self.tmp / "in.mp4"
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                        "testsrc2=s=1080x1920:r=30:d=4", "-f", "lavfi", "-i", "sine=f=330:d=4",
                        "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest",
                        "-movflags", "+faststart", str(self.src)], check=True)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_delivery_gate_passes_standard_and_names_each_failure(self):
        self.assertTrue(rc.run("delivery_gate", {"source": str(self.src)})["ok"])
        bad = self.tmp / "bad.mp4"
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                        "testsrc2=s=720x1280:r=25:d=1", "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
                        str(bad)], check=True)
        r = rc.run("delivery_gate", {"source": str(bad)})
        self.assertFalse(r["ok"])
        self.assertEqual({c["check"] for c in r["checks"] if not c["ok"]}, {"size", "fps", "faststart", "audio"})

    def test_credit_overlay_needs_owner_approval_through_the_runtime(self):
        out = self.tmp / "out.mp4"
        r = cr.execute(None, "reel.craft", {"op": "credit_overlay",
                                           "params": {"source": str(self.src), "output": str(out), "approve_write": True}})
        self.assertEqual(r["status"], "approval_required")
        self.assertFalse(out.exists())

    def test_credit_overlay_keeps_audio_and_frames_and_never_overwrites(self):
        font = _arabic_font()
        if not font:
            self.skipTest("no Arabic-capable font on this machine (set RED_ROSE_TEST_ARABIC_FONT)")
        out = self.tmp / "out.mp4"
        r = rc.run("credit_overlay", {"source": str(self.src), "output": str(out), "approve_write": True,
                                      "preset": "veryfast", "font_file": font})
        self.assertEqual(r["status"], "written")
        self.assertTrue(r["audio_byte_identical"])
        self.assertEqual(r["frames"], r["source_frames"])
        self.assertTrue(r["gate"]["ok"], r["gate"])
        self.assertFalse([p for p in self.tmp.iterdir() if p.name.startswith(".rose-v56-")], "staging left behind")
        with self.assertRaises(ValueError):
            rc.run("credit_overlay", {"source": str(self.src), "output": str(out), "approve_write": True})
        with self.assertRaises(PermissionError):
            rc.run("credit_overlay", {"source": str(self.src), "output": str(self.tmp / "x.mp4")})


class SafeUnzip(unittest.TestCase):
    def _zip(self, d, name, add):
        p = Path(d) / name
        with zipfile.ZipFile(p, "w") as z:
            add(z)
        return p

    def test_unsafe_members_are_refused_before_writing(self):
        with tempfile.TemporaryDirectory() as d:
            def sym(z):
                info = zipfile.ZipInfo("link")
                info.external_attr = 0o120777 << 16
                z.writestr(info, "/etc/passwd")
            cases = {"trav.zip": lambda z: z.writestr("../x", "1"), "drive.zip": lambda z: z.writestr("C:/x", "1"),
                     "backslash.zip": lambda z: z.writestr("a\\..\\..\\x", "1"), "sym.zip": sym}
            for name, add in cases.items():
                with self.assertRaises(ValueError, msg=name):
                    media_library_v35._safe_extract(self._zip(d, name, add), Path(d) / "out")
            self.assertFalse((Path(d) / "out").exists())
            media_library_v35._safe_extract(self._zip(d, "ok.zip", lambda z: z.writestr("a/b.txt", "hi")), Path(d) / "ok")
            self.assertEqual((Path(d) / "ok" / "a" / "b.txt").read_text(), "hi")


class Registry(unittest.TestCase):
    def test_registered_as_mixed_with_per_op_effects(self):
        self.assertEqual(cr.REGISTRY["reel.craft"][1], "mixed")
        self.assertIs(cr.IO_ADAPTERS["reel.craft"], rc)
        self.assertEqual(set(rc.OPS), set(rc.EFFECTS))
        self.assertEqual([o for o in rc.OPS if rc.EFFECTS[o] == "write"], ["credit_overlay"])


if __name__ == "__main__":
    unittest.main()
