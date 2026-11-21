import unittest
from storyboard import frame_at

class CrossfadeTests(unittest.TestCase):
    def test_two_scenes_do_not_share_gradient_ids(self):
        shots=[{'duration':1,'recipe':{'mode':'director2d','palette':{'sky':'#223344'}}},
               {'duration':1,'transition':'fade','recipe':{'mode':'director2d','palette':{'sky':'#bb5599'}}}]
        svg=frame_at(shots,1.1,320,568)
        self.assertEqual(svg.count('id="old_sky"'),1)
        self.assertEqual(svg.count('id="new_sky"'),1)
        self.assertIn('url(#old_sky)',svg)
        self.assertIn('url(#new_sky)',svg)
        self.assertIn('#223344',svg)
        self.assertIn('#bb5599',svg)

class CrossfadeTitleTests(unittest.TestCase):
    def test_outgoing_title_not_overprinted(self):
        shots=[{'duration':1,'recipe':{'mode':'director2d','title':'OLD TITLE'}},
               {'duration':1,'transition':'fade','recipe':{'mode':'director2d','title':'NEW TITLE'}}]
        mid=frame_at(shots,1.1,320,568)
        self.assertNotIn('OLD TITLE',mid)
        self.assertIn('NEW TITLE',mid)
if __name__=='__main__':unittest.main()
