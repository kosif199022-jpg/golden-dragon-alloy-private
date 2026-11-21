import unittest
from motion_tracks import sample, scalar
class Tests(unittest.TestCase):
 def test_ease_endpoints(self):
  k=[{'t':0,'value':0},{'t':1,'value':1}]
  self.assertEqual(sample(k,0),0)
  self.assertEqual(sample(k,1),1)
  self.assertAlmostEqual(sample(k,.5),.5)
 def test_hold(self):
  k=[{'t':0,'value':3},{'t':1,'value':9,'ease':'hold'}]
  self.assertEqual(sample(k,.7),3)
  self.assertEqual(sample(k,1),9)
 def test_invalid_order(self):
  with self.assertRaises(ValueError):sample([{'t':.8,'value':1},{'t':.2,'value':2}],.5)
 def test_reject_infinite(self):
  with self.assertRaises(ValueError):sample([{'t':0,'value':float('nan')}],.1)
 def test_range_enforced(self):
  with self.assertRaises(ValueError):scalar([{'t':0,'value':9}],0,0,-1,1)
