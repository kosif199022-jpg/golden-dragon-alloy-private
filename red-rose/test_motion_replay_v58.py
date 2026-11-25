import unittest, tempfile, json, shutil, subprocess, sys
from pathlib import Path
import rose_motion_replay_v58 as m
np,cv2=m.np,m.cv2

def fixture(n=12):
    rows=[]
    for i in range(n):
        rows.append({"frame":i,"t":i/12,"segment":0,"transform":{"matrix":[[1,0,i*.5],[0,1,i*.25]]},"luma":100,"overlays":{"caption":{"visible":True,"bbox":[.25,.4,.75,.6],"ink_pixels_proxy":100},"title":{"ink_pixels_proxy":50}}})
    return {"schema":1,"sample_step":1,"source_fps":12,"source_frames":n,"decoded_frames":n,"geometry":[128,192],"proxy_geometry":[128,192],"source_sha256":"a"*64,"records":rows}
def scenes(n=12):
    return [{"a":0,"b":n/12,"reference_frame":.25}]
@unittest.skipUnless(np is not None and cv2 is not None,'OpenCV/numpy required')
class ReplayTests(unittest.TestCase):
    def test_measured_translation(self):
        p=m.plan(fixture(),scenes())
        self.assertEqual(p["frames"],12);self.assertAlmostEqual(p["scenes"][0]["frames"][-1]["camera"][0],5.5/128)
        self.assertFalse(p["style_verified"])
    def test_loss_rebase(self):
        t=fixture();t["records"][4]["transform"]=None;t["records"][5]["segment"]=1
        p=m.plan(t,scenes());f=p["scenes"][0]["frames"]
        self.assertEqual(p["loss_frames"],1);self.assertEqual(f[4]["camera_state"],"unmeasured_identity")
        self.assertEqual(f[5]["camera"],[0,0,1,0])
    def test_caption_and_fade(self):
        t=fixture();t["records"][8]["overlays"]["caption"]["visible"]=False;t["records"][8]["luma"]=10
        f=m.plan(t,scenes())["scenes"][0]["frames"][8]
        self.assertEqual(f["caption"][-1],0);self.assertLess(f["background_gain_proxy"],.2)
    def test_gap(self):
        t=fixture();t["records"][1]["frame"]=2
        with self.assertRaises(ValueError):m.plan(t,scenes())
    def test_approval(self):
        with self.assertRaises(PermissionError):m.render("a","b","c",False)
    def test_blend(self):
        dst=np.zeros((192,128,3),np.uint8);layer=np.full((12,16,4),255,np.uint8)
        m.blend(dst,(layer,20,30),dx=.125,alpha=.5)
        self.assertEqual(int(dst[31,37,0]),127);self.assertEqual(int(dst[31,20,0]),0)
    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),"FFmpeg required")
    def test_real_render(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);clip=p/"bg.mp4";audio=p/"audio.wav";out=p/"out.mp4"
            subprocess.run(["ffmpeg","-v","error","-f","lavfi","-i","testsrc2=s=128x192:r=12:d=2","-c:v","libx264","-pix_fmt","yuv420p",str(clip)],check=True)
            subprocess.run(["ffmpeg","-v","error","-f","lavfi","-i","sine=frequency=330:duration=1",str(audio)],check=True)
            im=np.zeros((192,128,4),np.uint8);im[15:25,20:100]=255;cv2.imwrite(str(p/"head.png"),im)
            im[:]=0;im[80:95,32:96]=255;cv2.imwrite(str(p/"cap.png"),im)
            (p/"track.json").write_text(json.dumps(fixture()))
            (p/"job.json").write_text(json.dumps({"header":str(p/"head.png"),"audio":str(audio),"scenes":[dict(scenes()[0],clip=str(clip),clip_duration=2,caption_png=str(p/"cap.png"))]}))
            res=m.render(p/"track.json",p/"job.json",out,True)
            self.assertTrue(res["technical_qa"]["passed"]);self.assertEqual(res["frames_applied"],12);self.assertTrue(out.exists())
            with self.assertRaises(ValueError):m.render(p/"track.json",p/"job.json",out,True)
