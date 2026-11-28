import unittest,tempfile,zipfile,json,shutil,subprocess
from pathlib import Path
from rose_skill_corpus_v61 import build,status,search
from rose_media_contract_v61 import compile_plan,seek,verify
def spec():
    return {"character":"Nour fictional cartoon","setting":"Cairo garden","style":"warm 3D animation","fps":24,"width":144,"height":256,"shots":[{"frames":96,"action":"smiles","speaker":"Nour","dialogue":"يلا نحافظ على البيئة"},{"frames":96,"action":"waves"},{"frames":96,"action":"walks"}]}
class Fusion61Tests(unittest.TestCase):
    def test_index(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);z=p/"skills.zip";o=p/"index.db"
            with zipfile.ZipFile(z,"w") as f:
                f.writestr("a--ffmpeg/SKILL.md","video ffmpeg editing")
                f.writestr("b--ffmpeg/SKILL.md","video ffmpeg editing")
                f.writestr("x--accounting/SKILL.md","accounting finance audit")
                f.writestr("../escape/SKILL.md","never execute")
                f.writestr("x/script.py","raise RuntimeError()")
            with self.assertRaises(PermissionError):build(z,o)
            r=build(z,o,True);self.assertEqual(r["counts"]["indexed"],3);self.assertEqual(r["counts"]["unique_content"],2);self.assertEqual(r["counts"]["skipped_unsafe_or_oversized"],1)
            self.assertEqual(status(o),r);self.assertEqual(len(search(o,"مونتاج ffmpeg")),1);self.assertEqual(len(search(o,"محاسبة")),1)
            with self.assertRaises(FileExistsError):build(z,o,True)
    def test_split(self):
        p=compile_plan(spec());self.assertEqual(p["frames"],288);self.assertEqual([x["frames"] for x in p["clips"]],[192,96]);self.assertIn("يلا نحافظ على البيئة",p["clips"][0]["prompt"]);self.assertFalse(p["generation_performed"])
    def test_dialogue_overload(self):
        j=spec();j["shots"][0]["dialogue"]="كلمة "*30;p=compile_plan(j);self.assertFalse(p["ready_for_review"])
    def test_clip_limit(self):
        j=spec();j["shots"][0]["frames"]=240;self.assertFalse(compile_plan(j)["ready_for_review"])
    def test_deterministic(self):
        j=spec();j["mode"]="local";j["shots"][1]["overlap_frames"]=12;p=compile_plan(j);self.assertEqual(p["frames"],276)
        a=seek(p,90);seek(p,200);self.assertEqual(a,seek(p,90));self.assertEqual(a["active"],[1,2]);self.assertEqual(seek(p,84)["mix"],0);self.assertEqual(seek(p,95)["mix"],1)
    def test_overlap(self):
        j=spec();j["shots"][0]["overlap_frames"]=1
        with self.assertRaises(ValueError):compile_plan(j)
    def test_triple_overlap(self):
        j=spec();j["mode"]="local";j["shots"][1]["overlap_frames"]=50;j["shots"][2]["overlap_frames"]=50
        with self.assertRaises(ValueError):compile_plan(j)
    def test_captions(self):
        j=spec();j["captions"]=[{"start_frame":0,"end_frame":20,"text":"نص"}];p=compile_plan(j);self.assertEqual(seek(p,19)["caption"],"نص");self.assertIsNone(seek(p,20)["caption"])
    def test_dua_gate(self):
        j=spec();j["mode"]="dua";self.assertTrue(compile_plan(j)["dua_asset_gate_required"])
    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),"FFmpeg required")
    def test_real_media(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);c={"fps":24,"frames":24,"width":144,"height":256,"audio_required":True}
            for name,color,length in [("good","red","1"),("black","black","1"),("short","red","0.5")]:
                o=p/(name+".mp4")
                subprocess.run(["ffmpeg","-v","error","-f","lavfi","-i",f"color={color}:s=144x256:r=24:d={length}","-f","lavfi","-i","sine=frequency=330:duration=1","-c:v","libx264","-pix_fmt","yuv420p","-c:a","aac",str(o)],check=True,timeout=30)
                q=verify(o,c)
                self.assertEqual(q["technical_pass"],name=="good",q)
                if name=="short":self.assertFalse(q["checks"]["frame_count"])
                if name=="black":self.assertFalse(q["checks"]["first_frame_nonblack"])
if __name__=="__main__":unittest.main()
