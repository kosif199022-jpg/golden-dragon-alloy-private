import tempfile, unittest
from pathlib import Path
import rose_direct_v71 as dr
import rose_borrow_v71 as bw
import rose_styles_v70 as st

REG = st.registry()


class Lib:
    def __enter__(self):
        self.tmp = tempfile.TemporaryDirectory()
        lib = Path(self.tmp.name)
        for s in REG:
            if s["source"].startswith("pack:"):
                p = lib / s["source"][5:] / s["doc"]
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text("# doc", encoding="utf-8")
        return lib

    def __exit__(self, *a):
        self.tmp.cleanup()


class Direct71(unittest.TestCase):
    def test_genres(self):
        self.assertEqual(dr.genre_of("اعمل دعاء يوم الجمعة")[0], "dua")
        self.assertEqual(dr.genre_of("موشن جرافيك لكلمات أغنية")[0], "song")
        self.assertEqual(dr.genre_of("اشرح إزاي المحرك بيشتغل")[0], "explainer")
        self.assertEqual(dr.genre_of("xyz"), ("story", False))

    def test_treatment_is_continuous_and_varied(self):
        with Lib() as lib:
            r = dr.direct("قصة كرتون عن جندي فضل مستني", 20, lib=lib)
        shots = r["shot_list"]
        self.assertEqual(shots[0]["start_frame"], 0)
        self.assertEqual(shots[-1]["end_frame"], 600)
        for a, b in zip(shots, shots[1:]):
            self.assertEqual(a["end_frame"], b["start_frame"])
            self.assertNotEqual(a["shot_type"], b["shot_type"])
        self.assertEqual(r["continuity"]["errors"], 0, r["continuity"]["issues"])
        self.assertEqual([b["role"] for b in r["beats"]], ["hook", "setup", "escalation", "pivot", "payoff"])
        self.assertFalse(r["rendered"])
        self.assertEqual(r["status"], "draft_for_owner_review")

    def test_cocktail_assigns_by_layers_and_mixes(self):
        with Lib() as lib:
            r = dr.direct("قصة", 30, cocktail="el-ragel-wel-sit+maven-gta+khaam-motion", lib=lib)
        used = {b["style"] for b in r["beats"]}
        self.assertGreaterEqual(len(used), 2)
        self.assertEqual(r["cocktail"]["status"], "plan_ready", r["cocktail"]["blockers"])
        self.assertEqual(set(r["unused_styles"]) | used, {"el-ragel-wel-sit", "maven-gta", "khaam-motion"})

    def test_bad_input(self):
        with self.assertRaises(ValueError):
            dr.direct("", 20)
        with self.assertRaises(ValueError):
            dr.direct("قصة", 1)
        with self.assertRaises(ValueError):
            dr.direct("قصة", 20, cocktail="nope")
        with self.assertRaises(ValueError):
            dr.direct("قصة", 20, genre="opera")

    def test_every_role_defined(self):
        for g, (_, beats) in dr.GENRES.items():
            self.assertAlmostEqual(sum(w for _, w in beats), 1.0, places=6, msg=g)
            for role, _ in beats:
                self.assertIn(role, dr.ROLE)
                self.assertTrue(set(dr.ROLE[role][6]) <= set(st.ROLES), role)


class Borrow71(unittest.TestCase):
    def test_lists_styles_and_tools(self):
        with Lib() as lib:
            r = bw.borrow(lib=lib, tested={})
        self.assertEqual(r["styles"], len(REG))
        self.assertEqual(r["tools"], len(bw.tool_registry()))
        self.assertIn("teardown", {t["id"] for t in r["list_tools"]})
        self.assertFalse(r["execution_allowed"])

    def test_filter_by_owner_words(self):
        with Lib() as lib:
            r = bw.borrow(for_text="ماكينة قطاع تفكيك", lib=lib, tested={})
        self.assertEqual(r["list_tools"][0]["id"], "teardown")
        with Lib() as lib:
            g = bw.borrow(kind="styles", for_text="GTA", lib=lib, tested={})
        self.assertIn("maven-gta", [s["id"] for s in g["list_styles"]])

    def test_detect(self):
        self.assertTrue(bw.available("path:" + __file__))
        self.assertFalse(bw.available("which:definitely-not-a-program-xyz"))
        with self.assertRaises(ValueError):
            bw.available("magic:x")
        with self.assertRaises(ValueError):
            bw.borrow(kind="everything")


if __name__ == "__main__":
    unittest.main()
