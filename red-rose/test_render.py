import json, tempfile, unittest
from pathlib import Path
from render import svg_frame, render
class RenderTests(unittest.TestCase):
 def test_determinism(self):
  self.assertEqual(svg_frame(1),svg_frame(1))
 def test_escaping(self):
  self.assertIn('&lt;script&gt;',svg_frame(1,recipe={'title':'<script>'}))
 def test_color_validation(self):
  with self.assertRaises(ValueError): svg_frame(1,recipe={'accent':'red;bad'})
 def test_render_frames(self):
  with tempfile.TemporaryDirectory() as d:
   result=render(d,duration=1,fps=3,width=100,height=200)
   self.assertEqual(result['frames'],3)
   self.assertEqual(len(list(Path(d).glob('frame_*.svg'))),3)
   self.assertEqual(json.loads((Path(d)/'manifest.json').read_text())['fps'],3)
