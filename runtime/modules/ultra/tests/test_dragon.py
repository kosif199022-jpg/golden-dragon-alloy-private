"""Black Dragon Ultra engine tests.  Run:  python -m unittest discover -s tests -v   (from the skill folder)"""
import importlib.util, json, subprocess, sys, tempfile, unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location("dragon", Path(__file__).resolve().parents[1] / "scripts" / "dragon.py")
dragon = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(dragon)


def top(task):
    hits = dragon.route(task, 1)
    return hits[0]["dir"] if hits else None


class Routing(unittest.TestCase):
    CASES = {
        "اعمل مونتاج ريلز على الإيقاع مع ترجمة عربية": "video-montage",
        "ازالة خلفية صورة منتج وكتابة عرض خاص": "image-studio",
        "حلل برنامج exe بالهندسة العكسية": "reverse-engineer-anything",
        "اكتب سكريبت ريل وهوك عن القهوة": "kosif-reel-hooks",
        "فيديو موشن انترو لشركتي": "kosif-web-film",
        "تعليق صوتي بصوتي وتفريغ ملف الى srt": "kosif-voice-studio",
        "برومبت كلينج لفيلم قصير مع ستوري بورد": "kosif-kling-director",
        "مشاهد بالظلال مثل مسرح الظل": "kosif-shadow-theatre",
        "write a plan then debug with tdd": "obra-superpowers",
    }

    def test_top_module(self):
        for task, want in self.CASES.items():
            with self.subTest(task=task):
                self.assertEqual(top(task), want)

    def test_every_module_parsed(self):
        mods = dragon.all_modules()
        self.assertGreaterEqual(len(mods), 21)
        for m in mods:
            with self.subTest(m=m["dir"]):
                self.assertTrue(m["description"] and not m["description"].startswith(">"), m["description"][:40])


class Arabic(unittest.TestCase):
    def test_normalise(self):
        self.assertEqual(dragon.norm("إِضاءة"), "اضاءه")
        self.assertIn("مونتاج", dragon.tokens("والمونتاج"))


class Learning(unittest.TestCase):
    def test_ledger_boost_changes_route(self):
        with tempfile.TemporaryDirectory() as t:
            dragon.LEDGER = Path(t) / "ledger.jsonl"
            task = "تصميم بوست لمطعم"
            dragon.LEDGER.write_text(json.dumps({"task": task, "modules": ["kosif-superskills-library"], "result": "passed"}, ensure_ascii=False) + "\n", encoding="utf-8")
            hits = dragon.route(task, 3)
            self.assertEqual(hits[0]["dir"], "kosif-superskills-library")
            self.assertGreater(hits[0]["learned"], 0)


class Verify(unittest.TestCase):
    def test_image_and_missing(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / "a.png"; Image.new("RGB", (64, 32)).save(p)
            r = dragon.probe_file(p)
            self.assertTrue(r["ok"]); self.assertEqual((r["width"], r["height"]), (64, 32))
            self.assertFalse(dragon.probe_file(Path(t) / "none.mp4")["exists"])

    @unittest.skipUnless(dragon.find_exe("ffmpeg"), "ffmpeg missing")
    def test_video(self):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / "v.mp4"
            subprocess.run([dragon.find_exe("ffmpeg"), "-v", "error", "-f", "lavfi", "-i", "testsrc=size=320x180:rate=25:duration=2",
                            "-f", "lavfi", "-i", "sine=frequency=440:duration=2", "-shortest", "-c:v", "libx264", "-c:a", "aac", str(p)], check=True)
            r = dragon.probe_file(p)
            self.assertTrue(r["ok"]); self.assertAlmostEqual(r["duration_s"], 2, delta=0.2)
            self.assertIn("loudness_lufs", r)


class Exec(unittest.TestCase):
    def test_exec_rejects_escape(self):
        r = subprocess.run([sys.executable, str(Path(dragon.__file__)), "exec", "image-studio", "../../../x.py"], capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0)

    def test_exec_runs_module_script(self):
        r = subprocess.run([sys.executable, str(Path(dragon.__file__)), "exec", "image-studio", "scripts/check_tools.py", "--json"],
                           capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(r.returncode, 0, r.stderr); self.assertIn("tools", json.loads(r.stdout))


if __name__ == "__main__":
    unittest.main()
