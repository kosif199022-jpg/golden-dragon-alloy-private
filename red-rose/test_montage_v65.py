import unittest,tempfile,shutil,json,hashlib,subprocess
from pathlib import Path
from rose_montage_v65 import plan,render,ff,probe,video_check,job_lock
def setup_job(root):
    for name,col in (("red","red"),("blue","blue")):
        ff(["-f","lavfi","-i",f"color=c={col}:s=320x480:r=30:d=2","-c:v","libx264","-pix_fmt","yuv420p","-threads","2",root/(name+".mp4")])
    ff(["-f","lavfi","-i","sine=frequency=440:sample_rate=48000:duration=5","-c:a","pcm_s16le",root/"tone.wav"])
    return {"kind":"general","rights_confirmed":True,"workspace":str(root),"width":180,"height":320,"fps":30,"shots":[{"file":"red.mp4","frames":30,"source_start_frame":10},{"file":"blue.mp4","frames":30,"overlap_frames":9,"transition":"smooth-fade"}],"audio":"tone.wav"}
class Montage65(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory();self.addCleanup(self.t.cleanup);self.root=Path(self.t.name).resolve()
        (self.root/"a.mp4").write_bytes(b"fixture");(self.root/"b.mp4").write_bytes(b"fixture")
        self.j={"kind":"general","rights_confirmed":True,"workspace":str(self.root),"width":180,"height":320,"fps":30,"shots":[{"file":"a.mp4","frames":20},{"file":"b.mp4","frames":20,"overlap_frames":5,"transition":"fade"}],"allow_silent":True}
    def test_exact_plan(self):
        self.assertEqual(plan(self.j)["frames"],35);self.assertEqual(plan(self.j)["shots"][1]["timeline_start"],15)
    def test_approve(self):
        with self.assertRaises(PermissionError):render(self.j,self.root/"out.mp4")
        self.assertFalse((self.root/".rose-montage-v65").exists())
    def test_dua(self):
        self.j["kind"]="dua"
        with self.assertRaises(ValueError):plan(self.j)
    def test_rights(self):
        self.j["rights_confirmed"]=False
        with self.assertRaises(ValueError):plan(self.j)
    def test_no_silent_default(self):
        del self.j["allow_silent"]
        with self.assertRaises(ValueError):plan(self.j)
    def test_triple_overlap(self):
        self.j["shots"].append({"file":"a.mp4","frames":20,"overlap_frames":15,"transition":"fade"})
        with self.assertRaises(ValueError):plan(self.j)
    def test_path(self):
        self.j["shots"][0]["file"]="../other.mp4"
        with self.assertRaises(ValueError):plan(self.j)
    def test_no_overwrite(self):
        with self.assertRaises(ValueError):render(self.j,self.root/"a.mp4",True)
    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),"ffmpeg required")
    def test_render_resume_and_corruption(self):
        j=setup_job(self.root)
        first=render(j,self.root/"one.mp4",True);self.assertTrue(first["technical_pass"]);self.assertTrue(first["exact_pts"]);self.assertEqual(first["frames"],51)
        self.assertEqual(len(first["chunks_built"]),5);self.assertEqual(first["cache_hits"],[])
        pix=ff(["-i",self.root/"one.mp4","-vf","scale=2:2","-pix_fmt","rgb24","-f","rawvideo","pipe:1"])
        frames=[pix[i:i+12] for i in range(0,len(pix),12)];self.assertEqual(len(frames),51)
        self.assertGreater(frames[21][0],200);self.assertLess(frames[21][2],30)
        self.assertGreater(frames[29][2],200);self.assertLess(frames[29][0],30)
        self.assertGreater(frames[25][0],40);self.assertGreater(frames[25][2],40)
        second=render(j,self.root/"two.mp4",True);self.assertEqual(len(second["cache_hits"]),5);self.assertEqual(second["chunks_built"],[])
        self.assertEqual(first["sha256"],second["sha256"])
        cached=next((self.root/".rose-montage-v65").glob("*/blend-001.mp4"));cached.write_bytes(b"corrupted")
        third=render(j,self.root/"three.mp4",True);self.assertEqual(third["chunks_built"],["blend-001"]);self.assertEqual(third["sha256"],first["sha256"])
    def test_lock_released_after_failure(self):
        p=self.root/"lock"
        with self.assertRaises(RuntimeError):
            with job_lock(p):raise RuntimeError("simulated interruption")
        with job_lock(p):self.assertTrue(p.is_file())
    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),"ffmpeg required")
    def test_audio_normalized(self):
        j=setup_job(self.root);j["normalize_audio"]=True
        r=render(j,self.root/"normalized.mp4",True);self.assertTrue(r["audio_loudness_verified"]);self.assertLessEqual(abs(r["loudness"]["integrated_lufs"]+16),1.5)
    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),"ffmpeg required")
    def test_sixty_fps_assembly(self):
        j=setup_job(self.root);j["fps"]=60
        j["shots"]=[{"file":"red.mp4","frames":90},{"file":"blue.mp4","frames":90,"overlap_frames":30,"transition":"fade"}]
        r=render(j,self.root/"60.mp4",True)
        self.assertEqual(r["frames"],150);self.assertTrue(r["exact_pts"])
    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),"ffmpeg required")
    def test_still_zoom(self):
        # Original synthetic pattern, no external assets.
        from struct import pack
        import zlib
        w,h=128,128
        def c(t,d):return pack(">I",len(d))+t+d+pack(">I",zlib.crc32(t+d)&0xffffffff)
        raw=b"".join(b"\0"+bytes([220 if (x//16+y//16)%2==0 else 40 for x in range(w) for k in range(3)]) for y in range(h))
        (self.root/"pattern.png").write_bytes(b"\x89PNG\r\n\x1a\n"+c(b"IHDR",pack(">IIBBBBB",w,h,8,2,0,0,0))+c(b"IDAT",zlib.compress(raw))+c(b"IEND",b""))
        self.j["shots"]=[{"file":"pattern.png","frames":15,"zoom_end":1.3}]
        a=render(self.j,self.root/"zoom.mp4",True);self.assertEqual(a["frames"],15)
        pix=ff(["-i",self.root/"zoom.mp4","-vf","scale=32:32","-pix_fmt","rgb24","-f","rawvideo","pipe:1"])
        self.assertNotEqual(pix[:3072],pix[-3072:])
if __name__=="__main__":unittest.main()
