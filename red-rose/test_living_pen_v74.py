import argparse
import hashlib
import io
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import numpy as np
from PIL import Image
from living_pen.strokes import Stroke
from living_pen.tools import Qalam
from living_pen.render import render_strokes, render_spec, png_bytes

ROOT = Path(__file__).resolve().parent
SPEC = {"width":128,"height":96,"strokes":[{"points":[[20,40],[105,40]],"nib":{"width":20}}]}


class LivingPenTests(unittest.TestCase):
    def test_horizontal_width(self):
        self.assertAlmostEqual(Qalam(20).effective_width(0), 20/math.sqrt(2), places=10)

    def test_parallel_perpendicular(self):
        nib = Qalam(20,45)
        self.assertAlmostEqual(nib.effective_width(45),0,places=10)
        self.assertAlmostEqual(nib.effective_width(135),20,places=10)
        self.assertAlmostEqual(nib.effective_width(225),0,places=10)

    def test_pressure_scales_width(self):
        self.assertAlmostEqual(Qalam(20,0).effective_width(90,.3),6)

    def test_circle_length(self):
        r = 100
        angles = np.arange(128)*2*np.pi/128
        p = np.c_[r*np.cos(angles),r*np.sin(angles)]
        p = np.vstack((p,p[0]))
        stroke = Stroke(p)
        self.assertLess(abs(stroke.length-2*np.pi*r)/(2*np.pi*r),1e-5)
        _, tangent, curvature, _, _ = stroke.at_distance(stroke.length*.37)
        self.assertAlmostEqual(np.linalg.norm(tangent),1)
        self.assertAlmostEqual(curvature,1/r,delta=.00003)

    def test_straight_arc_and_spacing(self):
        s = Stroke([[0,0],[10,0],[100,0]])
        self.assertAlmostEqual(s.length,100)
        xy, _, k, _, _ = s.at_distance(np.array([0.,25.,50.,75.,100.]))
        np.testing.assert_allclose(xy[:,0],[0,25,50,75,100],atol=.01)
        np.testing.assert_allclose(k,0)

    def test_minimum_jerk(self):
        s = Stroke([[0,0],[100,0]],duration=2,start_time=3)
        sample = s.at_time([3,3.5,4,5])
        np.testing.assert_allclose(sample.distance,[0,10.3515625,50,100])
        np.testing.assert_allclose(sample.speed,[0,52.734375,93.75,0])
        np.testing.assert_allclose(sample.xy[:,0],sample.distance,atol=1e-9)

    def test_profiles(self):
        s = Stroke([[0,0],[10,0]],pressure=[0,1],tilt=[15,45])
        x = s.at_time(.5)
        self.assertAlmostEqual(float(x.pressure),.5)
        self.assertAlmostEqual(float(x.tilt),30)

    def test_render_width_and_antialias(self):
        a = render_spec(SPEC)
        effective = (255-a[:,60,0].astype(float)).sum()/(255-25)
        self.assertAlmostEqual(effective,20/math.sqrt(2),delta=.6)
        self.assertTrue(np.any((a[:,:,0]>25)&(a[:,:,0]<255)))

    def test_parallel_and_zero_pressure_render_blank(self):
        for p,nib in [(1,Qalam(20,0)),(0,Qalam(20,90))]:
            a = render_strokes([(Stroke([[10,20],[80,20]],pressure=p),nib)],100,60)
            self.assertTrue(np.all(a==255))

    def test_deterministic_png(self):
        a = png_bytes(render_spec(SPEC))
        b = png_bytes(render_spec(SPEC))
        self.assertEqual(hashlib.sha256(a).digest(),hashlib.sha256(b).digest())
        with Image.open(io.BytesIO(a)) as img:
            self.assertEqual(img.size,(128,96))

    def test_invalid_pressure(self):
        for p in (-.1,1.1,float("nan"),"1"):
            with self.subTest(p=p),self.assertRaises(ValueError):
                Stroke([[0,0],[10,0]],pressure=p)

    def test_invalid_points(self):
        for points in ([],[[0,0]],[[0,0],[0,0]],[[0,0],[float("inf"),1]]):
            with self.subTest(points=points),self.assertRaises(ValueError):
                Stroke(points)

    def test_invalid_angle(self):
        for angle in ("abc","45",None,float("nan"),True):
            with self.subTest(angle=angle),self.assertRaises(ValueError):
                Qalam(angle=angle)

    def test_invalid_spec(self):
        for spec in ({},{"strokes":[]},{"strokes":[{"points":[[0,0],[2,2]],"nib":{"angle":"x"}}]}):
            with self.assertRaises(ValueError):
                render_spec(spec)

    def test_cli_utf8_approval_no_overwrite(self):
        with tempfile.TemporaryDirectory() as td:
            spec = Path(td)/"\u0642\u0644\u0645.json"
            out = Path(td)/"\u0631\u0633\u0645.png"
            spec.write_text(json.dumps(SPEC),encoding="utf-8")
            cmd = [sys.executable,"-X","utf8",str(ROOT/"rose.py"),"pen","stroke",str(spec),"--out",str(out)]
            def run(*args):
                return subprocess.run(cmd+list(args),cwd=ROOT,capture_output=True,text=True,encoding="utf-8",timeout=30)
            self.assertEqual(run().returncode,3)
            self.assertFalse(out.exists())
            result = run("--approve-write")
            self.assertEqual(result.returncode,0,result.stderr+result.stdout)
            digest = hashlib.sha256(out.read_bytes()).hexdigest()
            self.assertEqual(json.loads(result.stdout)["sha256"],digest)
            self.assertNotEqual(run("--approve-write").returncode,0)
            self.assertEqual(hashlib.sha256(out.read_bytes()).hexdigest(),digest)

    def test_registration(self):
        import rose_ext
        import rose_fast_cli
        parser = argparse.ArgumentParser()
        sub = parser.add_subparsers()
        self.assertIn("living_pen",rose_ext.EXT_MODULES)
        self.assertEqual(rose_fast_cli.FAST_COMMANDS["pen"],"living_pen")
        self.assertEqual(rose_ext.load(sub,["living_pen"])["failed"],[])
        self.assertIn("pen",sub.choices)

    def test_sample(self):
        spec = json.loads((ROOT/"living_pen"/"sample_salam.json").read_text(encoding="utf-8"))
        a = render_spec(spec)
        self.assertEqual(a.shape,(1080,1080,3))
        self.assertGreater(np.count_nonzero(a[:,:,0]<100),10000)
        with Image.open(ROOT/"living_pen"/"sample_salam.png") as img:
            np.testing.assert_array_equal(np.asarray(img),a)


if __name__ == "__main__":
    unittest.main()
