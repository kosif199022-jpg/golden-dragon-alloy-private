"""Regressions for text-guided mouth shapes: explicit/estimated timing, safety and rendering."""
import copy
import unittest
from director import director_frame
from rig import rig_character
from visemes import (classify_letter, validate_words, estimate_words_from_srt,
                     apply_visemes, sample_viseme)


def shots():
    return [
        {'duration':1, 'recipe':{'mode':'director2d','actor':{'rig':'ik2d',
           'mouth_keys':[{'t':0,'value':1},{'t':1,'value':1}]}}},
        {'duration':1, 'recipe':{'mode':'director2d','actor':{'rig':'ik2d',
           'mouth_keys':[{'t':0,'value':1},{'t':1,'value':1}]}}},
    ]

class VisemeTests(unittest.TestCase):
    def test_shapes_for_english_and_arabic_letters(self):
        self.assertEqual(classify_letter('m'),'closed')
        self.assertEqual(classify_letter('b'),'closed')
        self.assertEqual(classify_letter('f'),'teeth')
        self.assertEqual(classify_letter('o'),'round')
        self.assertEqual(classify_letter('a'),'open')
        self.assertEqual(classify_letter('م'),'closed')
        self.assertEqual(classify_letter('ف'),'teeth')
        self.assertEqual(classify_letter('و'),'round')
        self.assertEqual(classify_letter('ا'),'open')
    def test_explicit_timing_and_no_mutation(self):
        original=shots();clone=copy.deepcopy(original)
        words=[{'start':.1,'end':.5,'text':'mom'},
               {'start':1.05,'end':1.7,'text':'voice'}]
        updated,report=apply_visemes(original,words)
        self.assertEqual(original,clone)
        self.assertEqual(report['words'],2)
        self.assertFalse(report['timing_is_acoustic_alignment'])
        self.assertEqual(report['processed_shots'],2)
        a=updated[0]['recipe']['actor']['viseme_keys'];b=updated[1]['recipe']['actor']['viseme_keys']
        self.assertEqual(sample_viseme(a,.1),'closed')
        self.assertEqual(sample_viseme(a,.3),'round')
        self.assertEqual(sample_viseme(a,.8),'neutral')
        self.assertEqual(sample_viseme(b,.06),'teeth')
    def test_srt_cues_estimated_not_claimed_word_timing(self):
        cues=[{'start':0,'end':1,'text':'Go home'},
              {'start':1.2,'end':2,'text':'مرحبا يا عالم'}]
        w=estimate_words_from_srt(cues,2)
        self.assertEqual(len(w),5)
        self.assertAlmostEqual(w[0]['start'],0)
        self.assertAlmostEqual(w[1]['end'],1)
        self.assertAlmostEqual(w[-1]['end'],2)
    def test_rig_four_distinct_mouth_shapes(self):
        seen=[]
        for pose in ('wide','teeth','round','open'):
            svg=rig_character(100,200,1,.5,{
                'viseme_keys':[{'t':0,'shape':pose}],
                'mouth_keys':[{'t':0,'value':1},{'t':1,'value':1}]})
            seen.append(svg)
        self.assertEqual(len(set(seen)),4)
    def test_silence_has_closed_mouth_even_if_open_pose(self):
        open_pose=rig_character(0,0,1,.4,{'viseme_keys':[{'t':0,'shape':'open'}],
                     'mouth_keys':[{'t':0,'value':0}]})
        closed_pose=rig_character(0,0,1,.4,{'viseme_keys':[{'t':0,'shape':'closed'}],
                     'mouth_keys':[{'t':0,'value':1}]})
        self.assertEqual(open_pose,closed_pose)
    def test_director_renders_mouth_pose(self):
        s=director_frame(.4,1,320,568,{'actor':{'rig':'ik2d','viseme_keys':[{'t':0,'shape':'teeth'}],
                  'mouth_keys':[{'t':0,'value':1}]}})
        self.assertIn('width="16" height="5.00"',s)
    def test_cross_scene_keys_not_leaking(self):
        updated,_=apply_visemes(shots(),[{'start':.1,'end':.9,'text':'mom'},
                                        {'start':1.1,'end':1.9,'text':'fan'}])
        a=updated[0]['recipe']['actor']['viseme_keys']
        b=updated[1]['recipe']['actor']['viseme_keys']
        self.assertEqual(a[-1]['shape'],'neutral')
        self.assertEqual(b[0]['shape'],'neutral')
    def test_rejects_bad_word_timeline(self):
        bad=[
            [{'start':0,'end':2.3,'text':'hi'}],
            [{'start':.5,'end':.4,'text':'hi'}],
            [{'start':float('nan'),'end':.4,'text':'hi'}],
            [{'start':0,'end':1,'text':'good'}, {'start':.4,'end':1.6,'text':'bad'}],
            [{'start':0,'end':.5,'text':''}],
            [{'start':0,'end':.5,'text':'*'}],
        ]
        for x in bad:
            with self.subTest(case=x):
                with self.assertRaises(ValueError): validate_words(x,2)
    def test_rejects_existing_viseme_track(self):
        s=shots();s[0]['recipe']['actor']['viseme_keys']=[{'t':0,'shape':'open'}]
        with self.assertRaisesRegex(ValueError,'must not be overwritten'):
            apply_visemes(s,[{'start':0,'end':.8,'text':'hello'}])
    def test_rejects_malformed_viseme_keys(self):
        for keys in ([{'t':0,'shape':'evil'}],
                     [{'t':.3,'shape':'open'},{'t':.2,'shape':'wide'}],
                     [{'t':float('nan'),'shape':'open'}]):
            with self.assertRaises(ValueError):sample_viseme(keys,.4)
    def test_long_dialogue_respects_keyframe_budget(self):
        words=[{'start':i*.01,'end':(i+1)*.01,'text':'mafi'} for i in range(180)]
        out,_=apply_visemes([{'duration':2,'recipe':{'mode':'director2d','actor':{'rig':'ik2d'}}}],words)
        keys=out[0]['recipe']['actor']['viseme_keys']
        self.assertLessEqual(len(keys),256)
        self.assertEqual(keys[0]['t'],0)
        self.assertTrue(all(keys[i]['t']<keys[i+1]['t'] for i in range(len(keys)-1)))

if __name__=='__main__':unittest.main()
