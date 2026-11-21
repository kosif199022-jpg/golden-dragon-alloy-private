import unittest
from camera import camera_frame
from storyboard import frame_at
R={'mode':'camera2_5d','background':'#121927','camera':{'pan':.5,'zoom':.2},'layers':[{'depth':5,'shape':'circle','color':'#ffcc00','x':.2,'y':.5},{'depth':0,'shape':'rect','color':'#e35b79','x':.8,'y':.7}]}
class CameraTests(unittest.TestCase):
 def test_deterministic(self): self.assertEqual(camera_frame(.5,2,320,568,R),camera_frame(.5,2,320,568,R))
 def test_parallax_changes(self): self.assertNotEqual(camera_frame(0,2,320,568,R),camera_frame(1,2,320,568,R))
 def test_storyboard(self): self.assertIn('<svg',frame_at([{'duration':2,'recipe':R}],.5,320,568))
 def test_invalid_color(self):
  with self.assertRaises(ValueError): camera_frame(0,2,320,568,dict(R,background='bad'))
 def test_invalid_depth(self):
  with self.assertRaises(ValueError): camera_frame(0,2,320,568,dict(R,layers=[{'depth':-1}]))
