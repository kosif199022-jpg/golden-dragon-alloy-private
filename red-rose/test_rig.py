import math
import unittest
from rig import two_bone, rig_character
from director import director_frame

class IKTests(unittest.TestCase):
    def test_reachable_lengths(self):
        a,b=two_bone((0,0),(20,50),35,32)
        self.assertAlmostEqual(math.dist((0,0),a),35,places=5)
        self.assertAlmostEqual(math.dist(a,b),32,places=5)
        self.assertAlmostEqual(math.dist(b,(20,50)),0,places=5)
    def test_unreachable_clamped(self):
        a,b=two_bone((0,0),(300,0),35,32)
        self.assertAlmostEqual(math.dist((0,0),a),35,places=5)
        self.assertAlmostEqual(math.dist(a,b),32,places=5)
        self.assertLess(math.dist((0,0),b),67)
    def test_bad_input(self):
        with self.assertRaises(ValueError): two_bone((0,0),(1,2),0,32)
        with self.assertRaises(ValueError): two_bone((0,0),(float('nan'),2),35,32)
    def test_rig_changes_between_frames(self):
        a=rig_character(100,200,1,0,{'rig':'ik2d'})
        b=rig_character(100,200,1,.25,{'rig':'ik2d'})
        self.assertNotEqual(a,b)
        self.assertIn('<ellipse',a)
    def test_face_keys(self):
        a=rig_character(100,200,1,.5,{'blink_keys':[{'t':0,'value':0},{'t':.5,'value':1},{'t':1,'value':0}], 'mouth_keys':[{'t':0,'value':0},{'t':1,'value':1}]})
        self.assertIn('ry="0.60"',a)
    def test_bad_expression_and_scale(self):
        with self.assertRaises(ValueError): rig_character(100,200,1,0,{'expression':'X'})
        with self.assertRaises(ValueError): rig_character(100,200,0,0,{})
    def test_director_wires_ik(self):
        svg=director_frame(.1,1,320,568,{'actor':{'rig':'ik2d','gait':1.0}})
        self.assertIn('stroke-linejoin="round"',svg)
    def test_director_default_backward_compatible(self):
        svg=director_frame(.1,1,320,568,{})
        self.assertNotIn('stroke-linejoin="round"',svg)

if __name__=='__main__':unittest.main()
