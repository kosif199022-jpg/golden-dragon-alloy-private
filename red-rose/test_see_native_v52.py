import unittest
import rose_see_native_v52 as s

class SeeV52(unittest.TestCase):
    def test_profile(self):
        p=s.profile()
        self.assertEqual(len(p["packs"]),9);self.assertEqual(len(p["stage0"]),11)
        self.assertEqual(len(p["owners"]),19)
    def test_simple(self):
        self.assertEqual(s.route("hello")["packs"],[])
    def test_image_precedence(self):
        self.assertEqual(s.route("image prompt with motion graphics",artifact="image")["branch"],"visual_prompt")
        self.assertEqual(s.route("image prompt with motion graphics",artifact="image")["packs"],[])
    def test_suno(self):
        self.assertEqual(s.route("اكتب كلمات أغنية Suno")["branch"],"suno_songwriting")
    def test_video(self):
        self.assertEqual(s.route("نفس المونتاج",artifact="video")["branch"],"reference_video_imitation")
    def test_rea(self):
        self.assertEqual(s.route("هندسة عكسية")["branch"],"rea")
    def test_optimizer(self):
        r=s.route("/optimize: run a script",side_effect="computer")
        self.assertTrue(r["output_only"]);self.assertIsNone(r["canonical_owner"]);self.assertFalse(r["executed"])
    def test_self_evolution(self):
        r=s.route("طور مهارة",artifact="plugin")
        self.assertEqual([p["id"] for p in r["packs"]],["kosif-skill-orchestrator","kosif-eval-trust"])
    def test_bounds_and_gap(self):
        for mode,cap in [("normal",2),("deep",4),("full_pro",4)]:
            r=s.route("research bug accounting security audit strategy JSON schema",mode=mode,gap="robotics")
            self.assertLessEqual(len(r["packs"])+r["dynamic_slots"],cap);self.assertEqual(r["dynamic_loaded"],0)
    def test_owner(self):
        r=s.route("send",side_effect="whatsapp")
        self.assertEqual(r["canonical_owner"],"KOSIF WhatsApp");self.assertFalse(r["approval_granted"])
    def test_full_pro(self):
        self.assertEqual(s.route("complex task",mode="full_pro")["runtime_status"],"FULL_PRO_BLOCKED")
    def test_decimal(self):
        r=s.reconcile([{"left":"0.1","right":"0.3"},{"left":"0.2","right":"0"}])
        self.assertTrue(r["balanced"]);self.assertEqual(r["difference"],"0.0")
        with self.assertRaises(ValueError):s.reconcile([{"left":0.1,"right":"0.1"}])
    def test_receipt(self):
        with self.assertRaises(ValueError):s.receipt_gate({"owner":"KOSIF Think","stages":["verified"],"evidence":["x"]})
        self.assertFalse(s.receipt_gate({"owner":"KOSIF Think","stages":["candidate"],"evidence":[]})["independently_verified"])
