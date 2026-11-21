"""V13 identity locking unit and project tests."""
import copy
import unittest
from identity import apply_profiles,validate_profiles
from storyboard import frame_at

COLORS={'skin':'#e6b393','hair':'#29202f','coat':'#bd4763','trousers':'#1a2b47'}

def shots():
    return [{'duration':1,'recipe':{'mode':'director2d','actor':{'character_id':'hero','gait':1}}},
            {'duration':1,'transition':'fade','recipe':{'mode':'director2d','actor':{'character_id':'hero','expression':'serious'}}}]

class IdentityTests(unittest.TestCase):
    def test_profile_is_deterministic(self):
        self.assertEqual(validate_profiles({'hero':COLORS}),validate_profiles({'hero':dict(reversed(list(COLORS.items())))}))
    def test_stable_identity_across_scenes(self):
        source=shots();snapshot=copy.deepcopy(source)
        updated,hashes=apply_profiles(source,{'hero':COLORS})
        self.assertEqual(source,snapshot,'must not mutate original scenes')
        self.assertEqual(len(hashes['hero']),64)
        self.assertEqual(updated[0]['recipe']['actor']['profile_sha256'],updated[1]['recipe']['actor']['profile_sha256'])
        self.assertEqual(updated[0]['recipe']['actor']['coat'],COLORS['coat'])
        self.assertIn(COLORS['hair'],frame_at(updated,0.2,320,568))
        self.assertIn(COLORS['hair'],frame_at(updated,1.7,320,568))
    def test_reject_color_drift(self):
        s=shots();s[1]['recipe']['actor']['hair']='#ffffff'
        with self.assertRaisesRegex(ValueError,'identity drift'):apply_profiles(s,{'hero':COLORS})
    def test_reject_missing_profile(self):
        with self.assertRaisesRegex(ValueError,'missing character profile'):apply_profiles(shots(),{'other':COLORS})
    def test_reject_wrong_rig(self):
        s=shots();s[0]['recipe']['actor']['rig']='standard'
        with self.assertRaises(ValueError):apply_profiles(s,{'hero':COLORS})
    def test_reject_incomplete_or_unknown_attributes(self):
        for p in [{},dict(COLORS,birthdate='2000'),{'skin':'#fff'}]:
            with self.assertRaises(ValueError):validate_profiles({'hero':p})
    def test_reject_bad_identifier_and_color(self):
        with self.assertRaises(ValueError):validate_profiles({'../hidden':COLORS})
        with self.assertRaises(ValueError):validate_profiles({'hero':dict(COLORS,coat='<script>')})

if __name__=='__main__':unittest.main()
