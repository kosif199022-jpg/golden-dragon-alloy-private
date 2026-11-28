import json, tempfile, unittest
from pathlib import Path
import rose_styles_v70 as st

REG = st.registry()


class Styles70(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.lib = Path(self.tmp.name)
        for s in REG:
            if s["source"].startswith("pack:"):
                d = self.lib / s["source"][5:]
                d.mkdir()
                (d / s["doc"]).parent.mkdir(parents=True, exist_ok=True)
                (d / s["doc"]).write_text("# doc", encoding="utf-8")
                (d / "LICENSE.md").write_text("rights", encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_registry_is_complete_and_valid(self):
        ids = {s["id"] for s in REG}
        for must in ("el-ragel-wel-sit", "maven-gta", "maven-3d-v2", "maven-toon", "khaam-motion", "khaam-reminder"):
            self.assertIn(must, ids)
        for s in REG:
            self.assertTrue(set(s["layers"]) <= set(st.ROLES), s["id"])
            self.assertTrue(s["credit"], s["id"])
        native = [s for s in REG if s["source"].startswith("native:")]
        for s in native:
            self.assertTrue((st.SKILL / s["doc"]).is_file(), s["doc"])

    def test_menu_lists_all_and_filters(self):
        m = st.menu(lib=self.lib, tested={})
        self.assertEqual(m["styles"], len(REG))
        self.assertFalse(m["execution_allowed"])
        f = st.menu(need=["characters", "places"], lib=self.lib, tested={})
        flat = [x for v in f["families"].values() for x in v]
        self.assertTrue(flat and all({"characters", "places"} <= set(x["layers"]) for x in flat))
        self.assertTrue(all(x["render_test"] == "not_tested_here" for x in flat))
        with self.assertRaises(ValueError):
            st.menu(need=["dragons"], lib=self.lib, tested={})

    def test_show_and_rights(self):
        r = st.show("maven-gta", lib=self.lib, tested={})
        self.assertIn("LICENSE.md", r["rights_files"])
        self.assertTrue(r["doc_path"].endswith("SKILL.md"))
        with self.assertRaises(ValueError):
            st.show("nope", lib=self.lib, tested={})

    def test_segment_cocktail_whole_frames(self):
        r = st.cocktail("el-ragel-wel-sit+maven-gta+khaam-motion", 10, lib=self.lib, tested={})
        self.assertEqual(r["status"], "plan_ready", r["blockers"])
        segs = r["plan"]["segments"]
        self.assertEqual(segs[0]["start_frame"], 0)
        self.assertEqual(segs[-1]["end_frame"], 300)
        for a, b in zip(segs, segs[1:]):
            self.assertEqual(a["end_frame"], b["start_frame"])
        self.assertTrue(any("not yet render-tested" in w for w in r["warnings"]))

    def test_layer_cocktail_same_scene_rule(self):
        bad = st.cocktail("characters=el-ragel-wel-sit,places=maven-gta", 8, lib=self.lib, tested={})
        self.assertEqual(bad["status"], "blocked")
        ok = st.cocktail("characters=maven-gta,places=maven-gta,captions=khaam-motion", 8, lib=self.lib, tested={})
        self.assertEqual(ok["status"], "plan_ready", ok["blockers"])
        self.assertEqual(ok["plan"]["overlays"], [{"role": "captions", "style": "khaam-motion"}])
        role = st.cocktail("maps=el-ragel-wel-sit", 8, lib=self.lib, tested={})
        self.assertEqual(role["status"], "blocked")

    def test_gates(self):
        self.assertEqual(st.cocktail("vox-motion", 8, aspect="16:9", lib=self.lib, tested={})["status"], "blocked")
        self.assertEqual(st.cocktail("khaam-documentary", 8, aspect="9:16", lib=self.lib, tested={})["status"], "blocked")
        d = st.cocktail("khaam-reminder", 8, lib=self.lib, tested={})
        self.assertTrue(any("dua" in w for w in d["warnings"]))
        empty = Path(self.tmp.name) / "empty"; empty.mkdir()
        self.assertEqual(st.cocktail("maven-toon", 8, lib=empty, tested={})["status"], "blocked")

    def test_tested_status_from_evidence(self):
        r = st.cocktail("maven-toon", 8, lib=self.lib, tested={"maven-toon": {"status": "rendered_ok"}})
        self.assertFalse(any("not yet render-tested" in w for w in r["warnings"]))

    def test_bad_inputs(self):
        for t in ("", "zzz", "dragons=maven-gta"):
            with self.assertRaises(ValueError):
                st.cocktail(t, 8, lib=self.lib, tested={})
        with self.assertRaises(ValueError):
            st.cocktail("maven-gta", 0, lib=self.lib, tested={})


if __name__ == "__main__":
    unittest.main()
