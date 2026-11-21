import unittest
from director import director_frame
from storyboard import frame_at
class DirectorTests(unittest.TestCase):
 def test_original_svg(self):
  v=director_frame(.5,1,320,568,{'title':'Rose','actor':{}})
  self.assertIn('linearGradient',v)
  self.assertIn('translate(',v)
  self.assertIn('Rose',v)
 def test_keyframe_camera(self):
  recipe={'camera':{'pan_keys':[{'t':0,'value':-.2},{'t':1,'value':.2}]},'actor':{'x_keys':[{'t':0,'value':.4},{'t':1,'value':.7}]}}
  self.assertNotEqual(director_frame(0,1,320,568,recipe),director_frame(1,1,320,568,recipe))
 def test_caption_escaped(self):
  recipe={'captions':[{'start':0,'end':1,'text':'<script>test</script>'}]}
  v=director_frame(.5,1,320,568,recipe)
  self.assertIn('&lt;script&gt;',v)
  self.assertNotIn('<script>',v)
 def test_invalid_hex(self):
  with self.assertRaises(ValueError):director_frame(0,1,320,568,{'palette':{'sky':'<x>'}})
 def test_storyboard_transition(self):
  shots=[{'duration':1,'recipe':{'mode':'director2d'}},{'duration':1,'transition':'fade','recipe':{'mode':'director2d','title':'Scene2'}}]
  v=frame_at(shots,1.1,320,568)
  self.assertIn('opacity=',v)
  self.assertIn('Scene2',v)
