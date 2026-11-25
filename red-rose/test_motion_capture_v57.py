import unittest,tempfile,json,subprocess,sys
from pathlib import Path
import rose_motion_capture_v57 as m
cv2,np=m.cv2,m.np
@unittest.skipUnless(cv2 is not None and np is not None,"OpenCV/numpy optional")
class MotionCaptureV57(unittest.TestCase):
    def texture(self):
        return np.random.default_rng(42).integers(0,256,(320,240),dtype=np.uint8)
    def test_translation(self):
        a=self.texture();mat=np.float32([[1,0,7],[0,1,-4]])
        b=cv2.warpAffine(a,mat,(240,320));r=m.pair(a,b)
        self.assertIsNotNone(r);self.assertLess(np.max(np.abs(r[0]-mat)),.8)
    def test_zoom_rotation(self):
        a=self.texture();mat=cv2.getRotationMatrix2D((120,160),3,1.04)
        b=cv2.warpAffine(a,mat,(240,320));r=m.pair(a,b)
        self.assertIsNotNone(r);self.assertLess(np.max(np.abs(r[0]-mat)),1.2)
        self.assertAlmostEqual(m.describe_matrix(np.vstack([r[0],[0,0,1]]),240,320)["scale"],1.04,places=2)
    def test_flat_is_not_motion(self):
        a=np.zeros((240,320),np.uint8);self.assertIsNone(m.pair(a,a))
    def test_masked_text(self):
        a=self.texture();b=a.copy();mask=np.full(a.shape,255,np.uint8);mask[90:230]=0
        b[90:230]=0;r=m.pair(a,b,mask)
        self.assertIsNotNone(r);self.assertLess(abs(r[0][0,2]),.5)
    def test_overlay(self):
        a=np.zeros((200,100,3),np.uint8);a[60:80,20:50]=255
        q=m.overlay(a,[.1,.2,.9,.6],"white");self.assertEqual(q["bbox"],[.2,.3,.5,.4])
        self.assertFalse(m.overlay(a,[.1,.2,.9,.6],"yellow")["visible"])
    def test_invalid_region(self):
        with self.assertRaises(ValueError):m.validate_regions([{"id":"x","box":[0,0,2,1],"kind":"white"}])
    def test_replay_lost(self):
        d={"proxy_geometry":[320,480],"records":[{"t":0,"transform":{}},{"t":1,"transform":None}]}
        self.assertFalse(m.replay(d,1)["ok"])
        with self.assertRaises(ValueError):m.replay(d,2)
    def test_real_encoded_tracking(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"motion.avi";a=self.texture();v=cv2.VideoWriter(str(p),cv2.VideoWriter_fourcc(*"MJPG"),12,(240,320))
            if not v.isOpened():self.skipTest("MJPG unavailable")
            for i in range(18):
                q=cv2.warpAffine(a,np.float32([[1,0,i],[0,1,0]]),(240,320))
                v.write(cv2.cvtColor(q,cv2.COLOR_GRAY2BGR))
            v.release();d=m.analyze(p,sample_fps=12,max_seconds=4)
            self.assertEqual(d["sample_count"],18);self.assertGreater(d["pair_coverage"],.9)
            self.assertAlmostEqual(d["records"][-1]["transform"]["x"],17/240,delta=.012)
            self.assertFalse(d["final_style_verified"])
    def test_approval(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"out.json";r=subprocess.run([sys.executable,str(Path(__file__).with_name("rose.py")),"motion-capture","analyze","missing.mp4","--output",str(p)],capture_output=True,text=True)
            self.assertEqual(r.returncode,3);self.assertFalse(p.exists())
