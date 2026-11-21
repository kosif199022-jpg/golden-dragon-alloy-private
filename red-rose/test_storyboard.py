import unittest
from storyboard import validate_shots, frame_at
class StoryboardTests(unittest.TestCase):
 def setUp(self): self.shots=[{'duration':1,'recipe':{'title':'FIRST'}},{'duration':2,'transition':'fade','recipe':{'title':'SECOND'}}]
 def test_total(self): self.assertEqual(validate_shots(self.shots),3)
 def test_cut_to_next(self): self.assertIn('SECOND',frame_at(self.shots,1.5))
 def test_fade(self): self.assertIn('opacity=',frame_at(self.shots,1.1))
 def test_invalid_transition(self):
  with self.assertRaises(ValueError):validate_shots([{'duration':1,'transition':'warp'}])
 def test_html_escaped(self):self.assertIn('&lt;script&gt;',frame_at([{'duration':1,'recipe':{'title':'<script>'}}],.5))
if __name__=='__main__':unittest.main()
