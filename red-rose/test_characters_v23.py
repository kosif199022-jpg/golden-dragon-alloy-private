"""Tests for characters_v23 (topics 14.01-14.10)."""
import ast
import inspect
import json
import math
import random
import sys
import unittest

import characters_v23 as ch


class TestHygiene(unittest.TestCase):
    def test_imports_and_calls(self):
        tree = ast.parse(inspect.getsource(ch))
        banned = {'os', 'subprocess', 'socket', 'urllib', 'http', 'shutil', 'sqlite3', 'ctypes'}
        allowed_local = {'geometry_v20', 'physics_v20'}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top = alias.name.split('.')[0]
                    self.assertNotIn(top, banned)
                    self.assertTrue(top in allowed_local or top in sys.stdlib_module_names, top)
            elif isinstance(node, ast.ImportFrom):
                top = (node.module or '').split('.')[0]
                self.assertNotIn(top, banned)
                self.assertTrue(top in allowed_local or top in sys.stdlib_module_names
                                or top == '__future__', top)
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                self.assertNotIn(node.func.id, {'open', 'exec', 'eval', 'print', 'compile',
                                                '__import__'})

    def test_topics_ops_consistent(self):
        self.assertEqual(len(ch.TOPICS), 10)
        self.assertEqual(set(ch.TOPICS.values()), set(ch.OPS))
        self.assertEqual(set(ch.TOPICS), set(ch.TOPIC_NAMES_AR))

    def test_every_op_runs_with_empty_params(self):
        for op in ch.OPS:
            with self.subTest(op=op):
                out = ch.run(op, {})
                self.assertEqual(set(out), {'op', 'result', 'assumptions', 'limits'})
                self.assertEqual(out['op'], op)
                self.assertTrue(out['assumptions'] and out['limits'])
                text = json.dumps(out, allow_nan=False, sort_keys=True)
                self.assertEqual(text, json.dumps(ch.run(op, {}), allow_nan=False, sort_keys=True))

    def test_run_rejections(self):
        with self.assertRaises(ValueError):
            ch.run('nope', {})
        with self.assertRaises(ValueError):
            ch.run('skeleton', [])
        for op in ch.OPS:
            with self.subTest(op=op):
                with self.assertRaises(ValueError):
                    ch.run(op, {'bogus_param': 1})

    def test_bad_values_raise_value_error(self):
        cases = [
            ('skeleton', {'frames': 601}), ('skeleton', {'frames': True}),
            ('skeleton', {'bones': [{'name': 'a', 'parent': 'zz', 'length': 1}]}),
            ('skeleton', {'bones': [{'name': f'b{i}', 'length': 1} for i in range(41)]}),
            ('skeleton', {'bones': [{'name': 'a'}]}),
            ('walk_cycle', {'stride': float('nan')}), ('walk_cycle', {'duty_factor': 0.4}),
            ('walk_cycle', {'stride': 5.0}),
            ('run_cycle', {'duty_factor': 0.5}), ('run_cycle', {'duty_factor': 0.49, 'fps': 12}),
            ('expressions', {'keys': [[0, 'nope']]}), ('expressions', {'keys': [[5, 'happy'], [5, 'sad']]}),
            ('viseme_track', {'words': []}),
            ('viseme_track', {'words': [{'word': 'hi', 'start': 1.0}]}),
            ('viseme_track', {'words': [{'word': 'hi', 'start': 1.0, 'end': 0.5}]}),
            ('viseme_track', {'words': [{'word': 'hi', 'start': 0.0, 'end': 30.0}]}),
            ('landmark_smoothing', {'track': [[[0, 0]], [[0, 0], [1, 1]]]}),
            ('landmark_smoothing', {'filter': 'kalman'}),
            ('identity_lock', {'reference': {'palette': {'hair': 'red'}}}),
            ('identity_lock', {'reference': {'outfit': []}}),
            ('hand_grip', {'object': {'shape': 'circle', 'center': [0, 1.4], 'radius': 0.5}}),
            ('hand_grip', {'object': {'shape': 'star', 'center': [0, 0]}}),
            ('secondary_motion', {'amplitude': 0}),
            ('crowd_layers', {'characters': [{'id': f'c{i}', 'palette': {'a': '#000'}}
                                             for i in range(21)]}),
            ('crowd_layers', {'characters': [{'id': 'x'}]}),
        ]
        for op, params in cases:
            with self.subTest(op=op, params=str(params)[:60]):
                with self.assertRaises(ValueError):
                    ch.run(op, params)


class TestSkeleton(unittest.TestCase):
    def test_waving_lengths_constant(self):
        r = ch.run('skeleton', {'frames': 120})['result']
        self.assertEqual(r['frames'], 120)
        self.assertLessEqual(r['max_length_error'], 1e-9)
        for err in r['per_bone_max_length_error'].values():
            self.assertLessEqual(err, 1e-9)
        self.assertTrue(r['lengths_constant'])
        # the hand actually moves (it is a wave, not a still pose)
        hands = [s['tails']['hand'] for s in r['samples']]
        self.assertGreater(max(h[0] for h in hands) - min(h[0] for h in hands), 0.05)


class TestWalk(unittest.TestCase):
    def test_planted_feet_and_loop(self):
        r = ch.run('walk_cycle', {})['result']
        self.assertLessEqual(r['max_stance_drift'], 1e-6)
        self.assertTrue(r['feet_planted'])
        self.assertLessEqual(r['loop_error'], 1e-9)
        self.assertTrue(r['loops'])
        self.assertGreater(r['double_support_frames'], 0)
        first, last = r['samples'][0], r['samples'][-1]
        for side in ('left', 'right'):
            for key in ('knee', 'foot'):
                for c in range(2):
                    self.assertAlmostEqual(first[side][key][c] - first['hip'][c],
                                           last[side][key][c] - last['hip'][c], places=9)
            self.assertEqual(first[side]['contact'], last[side]['contact'])

    def test_unreachable_stride_rejected(self):
        with self.assertRaises(ValueError):
            ch.walk_cycle(stride=3.0)


class TestRun(unittest.TestCase):
    def test_flight_and_contact_fraction(self):
        for fps, duty in ((30.0, 0.35), (60.0, 0.3), (24.0, 0.25)):
            with self.subTest(fps=fps, duty=duty):
                r = ch.run('run_cycle', {'fps': fps, 'duty_factor': duty})['result']
                self.assertTrue(r['has_flight_phase'])
                self.assertTrue(r['flight_frames'])
                n = r['frames_per_cycle']
                for side, frac in r['contact_fraction'].items():
                    self.assertLessEqual(abs(frac - duty), 1.0 / n + 1e-12, side)
                    total = sum(iv['frames'][1] - iv['frames'][0]
                                for iv in r['contact_intervals'][side])
                    self.assertAlmostEqual(total / n, frac)
                samples = {s['frame']: s for s in r['samples']}
                for f in r['flight_frames']:
                    if f in samples:
                        self.assertFalse(samples[f]['left']['contact'])
                        self.assertFalse(samples[f]['right']['contact'])
                self.assertLessEqual(r['max_stance_drift'], 1e-6)


class TestExpressions(unittest.TestCase):
    def test_every_expression_reached_and_clamped(self):
        r = ch.run('expressions', {})['result']
        names = {k['expression'] for k in r['keys']}
        self.assertTrue({'neutral', 'happy', 'sad', 'surprised', 'angry'} <= names)
        for k in r['keys']:
            self.assertEqual(k['max_error'], 0.0)
            row = r['track'][k['frame']]
            for c in r['controls']:
                self.assertEqual(row[c], r['expressions'][k['expression']][c])
        self.assertTrue(r['all_keys_reached'])
        self.assertTrue(r['values_in_range'])

    def test_out_of_range_clamped_and_flagged(self):
        r = ch.run('expressions', {'expressions': {'grin': {'smile': 3.0, 'blink': -1}},
                                   'keys': [[0, 'neutral'], [10, 'grin']], 'easing': 'linear'})['result']
        self.assertEqual(r['expressions']['grin']['smile'], 1.0)
        self.assertEqual(r['expressions']['grin']['blink'], 0.0)
        self.assertFalse(r['reachable_exactly']['grin'])
        self.assertTrue(r['values_in_range'])
        self.assertFalse(r['all_keys_reached'])
        self.assertAlmostEqual(r['track'][5]['smile'], 0.5)


class TestVisemes(unittest.TestCase):
    def test_spans_gaps_and_honesty(self):
        words = [{'word': 'مرحبا', 'start': 0.25, 'end': 0.75},
                 {'word': 'Bob', 'start': 1.0, 'end': 1.5},
                 {'word': 'وفي', 'start': 2.0, 'end': 2.4}]
        r = ch.run('viseme_track', {'words': words, 'fps': 24.0})['result']
        self.assertFalse(r['audio_phoneme_recognition'])
        self.assertEqual(r['method'], 'rule_based_letter_mapping')
        self.assertTrue(r['checks']['visemes_inside_word_spans'])
        self.assertTrue(r['checks']['gaps_closed'])
        for seg in r['segments']:
            self.assertIn(seg['viseme'], ch.VISEMES)
            if seg['word'] is not None:
                w = next(x for x in words if x['word'] == seg['word'])
                self.assertGreaterEqual(seg['start'], w['start'])
                self.assertLessEqual(seg['end'], w['end'])
        for i, v in enumerate(r['track']):
            t = i / 24.0
            if not any(w['start'] <= t < w['end'] for w in words):
                self.assertEqual(v, 'closed')
        self.assertIn('round', r['track'])          # Bob / و
        self.assertIn('teeth', r['track'])          # ف
        bob = [s for s in r['segments'] if s['word'] == 'Bob']
        self.assertEqual(bob[0]['viseme'], 'closed')


class TestLandmarks(unittest.TestCase):
    def test_example_improves_and_rejects_outlier(self):
        r = ch.run('landmark_smoothing', {})['result']
        e = r['errors']
        self.assertLess(e['rms_after_smoothing'], e['rms_raw'])
        self.assertLess(e['rms_after_outlier_rejection'], e['rms_raw'])
        self.assertIn((40, 0), {(x['frame'], x['point']) for x in r['rejected']})
        self.assertLessEqual(r['rejected_count'], 3)

    def test_supplied_jittered_track_ema(self):
        rng = random.Random(3)
        gt = [[[100.0 + 0.2 * f, 50.0], [120.0, 60.0 - 0.1 * f]] for f in range(120)]
        tr = [[[x + rng.gauss(0, 2), y + rng.gauss(0, 2)] for x, y in fr] for fr in gt]
        tr[60][1] = [tr[60][1][0] + 50, tr[60][1][1]]
        for filt in ('ema', 'one_euro'):
            with self.subTest(filter=filt):
                r = ch.run('landmark_smoothing', {'track': tr, 'ground_truth': gt,
                                                  'filter': filt})['result']
                self.assertLess(r['errors']['rms_after_smoothing'], r['errors']['rms_raw'])
                self.assertIn((60, 1), {(x['frame'], x['point']) for x in r['rejected']})
        r = ch.run('landmark_smoothing', {'track': tr})['result']
        self.assertIsNone(r['errors'])


class TestIdentity(unittest.TestCase):
    def test_hair_change_detected_noise_passes(self):
        r = ch.run('identity_lock', {})['result']
        by = {s['shot']: s for s in r['shots']}
        self.assertTrue(by['s01']['consistent'])
        self.assertTrue(by['s02']['consistent'])          # small numeric noise
        self.assertFalse(by['s03']['consistent'])
        self.assertEqual([(i['kind'], i['key']) for i in by['s03']['issues']], [('palette', 'hair')])
        self.assertEqual(r['drifted_shots'], ['s03'])

    def test_outfit_and_proportion_drift(self):
        ref = {'palette': {'hair': '#000000'}, 'outfit': ['hat'], 'proportions': {'head': 0.2}}
        shots = [{'shot': 'a', 'palette': {'hair': '#000000'}, 'outfit': ['cap'],
                  'proportions': {'head': 0.25}}]
        r = ch.run('identity_lock', {'reference': ref, 'shots': shots})['result']
        kinds = sorted((i['kind'], i['change']) for i in r['shots'][0]['issues'])
        self.assertEqual(kinds, [('outfit', 'extra'), ('outfit', 'missing'), ('proportion', 'value')])


class TestHandGrip(unittest.TestCase):
    def test_circle_and_box(self):
        objs = [None, {'shape': 'box', 'center': [0.45, 1.05], 'size': [0.1, 0.16]}]
        for obj in objs:
            with self.subTest(obj=obj):
                params = {} if obj is None else {'object': obj}
                r = ch.run('hand_grip', params)['result']
                self.assertLessEqual(r['contact_error'], 1e-6)
                self.assertTrue(r['reached'])
                self.assertGreaterEqual(r['min_signed_distance'], -1e-9)
                self.assertFalse(r['penetrates'])
                self.assertTrue(r['grip_ok'])
                for path in r['fingers']:
                    for p in path:
                        self.assertGreaterEqual(ch._sdf(r['object'], p), 0.0)

    def test_unreachable_reported(self):
        r = ch.run('hand_grip', {'object': {'shape': 'circle', 'center': [3.0, 1.0],
                                            'radius': 0.1}})['result']
        self.assertFalse(r['reached'])
        self.assertFalse(r['grip_ok'])


class TestSecondary(unittest.TestCase):
    def test_settles_with_bounded_lag(self):
        r = ch.run('secondary_motion', {})['result']
        self.assertTrue(r['settled'])
        self.assertGreater(r['settle_frame'], r['parent_stop_frame'] - 1)
        self.assertLessEqual(r['tip_lag_frames'], r['max_lag_frames'])
        self.assertGreater(r['tip_lag_frames'], 0.0)
        self.assertGreaterEqual(r['tip_overshoot_ratio'], 0.0)
        self.assertLess(r['final_max_speed'], 1e-3)
        self.assertEqual(r['single_link_reference']['source'], 'physics_v20.spring')
        last = r['samples'][-1]['nodes']
        for a, b in zip(last, last[1:]):
            self.assertAlmostEqual(math.hypot(b[0] - a[0], b[1] - a[1]), r['segment_length'])

    def test_unphysical_lag_rejected(self):
        with self.assertRaises(ValueError):
            ch.run('secondary_motion', {'frequency_hz': 0.3, 'damping_ratio': 2.5,
                                        'max_lag_frames': 10})


class TestCrowd(unittest.TestCase):
    def test_valid_crowd(self):
        r = ch.run('crowd_layers', {})['result']
        self.assertTrue(r['valid'])
        order = [x['id'] for x in r['layers']['market']]
        self.assertEqual(order, ['baker', 'kid', 'rose'])   # farthest drawn first

    def test_id_and_palette_collisions(self):
        pal = {'hair': '#111111', 'coat': '#aa0000'}
        chars = [{'id': 'a', 'palette': pal, 'z': 1}, {'id': 'a', 'palette': {'hair': '#ffffff'}, 'z': 2},
                 {'id': 'b', 'palette': dict(pal), 'z': 3},
                 {'id': 'c', 'palette': dict(pal), 'shot': 'other'}]
        r = ch.run('crowd_layers', {'characters': chars})['result']
        self.assertFalse(r['valid'])
        self.assertEqual([c['id'] for c in r['id_collisions']], ['a'])
        pairs = {(c['a'], c['b']) for c in r['colour_collisions']}
        self.assertEqual(pairs, {('a', 'b')})            # 'c' is in another shot


if __name__ == '__main__':
    unittest.main()
