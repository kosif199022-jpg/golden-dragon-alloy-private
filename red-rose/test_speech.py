import unittest
from speech import parse_srt, apply_captions, seconds

class SpeechTests(unittest.TestCase):
    sample = '1\n00:00:00,000 --> 00:00:01,200\nHello\n\n2\n00:00:01,200 --> 00:00:02,000\nWorld'
    def test_parse(self):
        cues = parse_srt(self.sample)
        self.assertEqual(len(cues), 2)
        self.assertEqual(cues[1]['start'], 1.2)
    def test_split_across_shots(self):
        shots = [{'duration': 1, 'recipe': {'mode': 'character2d'}},
                 {'duration': 1, 'recipe': {'mode': 'character2d'}}]
        result = apply_captions(shots, parse_srt(self.sample))
        self.assertEqual(result[1]['recipe']['captions'][0]['start'], 0.)
        self.assertEqual(result[1]['recipe']['captions'][1]['start'], 0.2)
        self.assertNotIn('captions', shots[0]['recipe'])
    def test_bad_time(self):
        with self.assertRaises(ValueError): seconds('00:60:01,000')
    def test_overlap(self):
        with self.assertRaises(ValueError): parse_srt(self.sample.replace('00:00:01,200 --> 00:00:02,000', '00:00:00,500 --> 00:00:02,000'))

if __name__ == '__main__': unittest.main()
