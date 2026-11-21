"""Tests for design_v23 (topics 13.01-13.10)."""
import ast
import inspect
import json
import math
import unicodedata
import unittest
import xml.etree.ElementTree as ET

import design_v23 as D

SVG = '{http://www.w3.org/2000/svg}'


def _svg_safe(test, svg):
    root = ET.fromstring(svg)
    test.assertEqual(root.tag, SVG + 'svg')
    for el in root.iter():
        test.assertNotEqual(el.tag.split('}')[-1].lower(), 'script')
        test.assertNotEqual(el.tag.split('}')[-1].lower(), 'foreignobject')
        for k, v in el.attrib.items():
            name = k.split('}')[-1].lower()
            test.assertFalse(name.startswith('on'), k)
            if name == 'href':
                test.assertTrue(v.startswith('#'), v)
            test.assertNotIn('javascript:', v.lower())
            if 'url(' in v:
                test.assertIn('url(#', v)
    return root


def _wcag_lum(hexs):
    h = hexs.lstrip('#')
    out = []
    for i in (0, 2, 4):
        c = int(h[i:i + 2], 16) / 255
        out.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    return 0.2126 * out[0] + 0.7152 * out[1] + 0.0722 * out[2]


class TestInterface(unittest.TestCase):
    def test_topics_and_ops(self):
        self.assertEqual(len(D.TOPICS), 10)
        self.assertEqual(set(D.TOPICS.values()), set(D.OPS))
        self.assertEqual(set(D.TOPICS), set(D.TOPIC_NAMES_AR))
        self.assertEqual([D.TOPICS[k] for k in sorted(D.TOPICS)], list(D.OPS))

    def test_every_op_runs_with_empty_params_and_is_json(self):
        for op in D.OPS:
            with self.subTest(op=op):
                out = D.run(op, {})
                self.assertEqual(set(out), {'op', 'result', 'assumptions', 'limits'})
                self.assertEqual(out['op'], op)
                self.assertTrue(out['assumptions'] and out['limits'])
                json.dumps(out, allow_nan=False)
                self.assertEqual(out, D.run(op, None))

    def test_unknown_params_and_bad_ops_raise_value_error(self):
        for op in D.OPS:
            with self.subTest(op=op):
                with self.assertRaises(ValueError):
                    D.run(op, {'no_such_param': 1})
        with self.assertRaises(ValueError):
            D.run('nope', {})
        with self.assertRaises(ValueError):
            D.run('palette_harmony', [])
        with self.assertRaises(ValueError):
            D.run('logo_marks', {'count': True})
        with self.assertRaises(ValueError):
            D.run('horizon_fov', {'vfov_deg': float('nan')})
        with self.assertRaises(ValueError):
            D.run('landscape_layers', {'layers': 9})

    def test_missing_or_bad_required_inputs_raise_value_error(self):
        cases = [
            ('frame_composition', {'elements': [{'id': 'a', 'x': 0, 'y': 0}]}),
            ('frame_composition', {'elements': []}),
            ('palette_harmony', {'base': 'red'}),
            ('palette_harmony', {'pairs': [{'fg': '#000'}]}),
            ('arabic_text_layout', {'text': '   '}),
            ('logo_marks', {'references': [[1.0, 2.0]]}),
            ('poster_hierarchy', {'elements': [{'id': 't', 'role': 'title', 'x': 0, 'y': 0, 'w': 9, 'h': 9}]}),
            ('poster_hierarchy', {'elements': [{'id': 't', 'role': 'title', 'x': 0, 'y': 0, 'w': 9, 'h': 9,
                                                'font_px': 90}]}),
            ('interior_layout', {'furniture': [{'id': 'a', 'x': 0, 'y': 0, 'w': 10}]}),
            ('three_point_light', {'subject': [0, 0, 1], 'camera': [0, 0, 2]}),
            ('three_point_light', {'shadow_vector': [0, 0]}),
            ('horizon_fov', {'shots': [{'id': 'a'}]}),
            ('continuity_diff', {'bible': {'characters': {}}}),
            ('continuity_diff', {'shots': [{'id': 'a', 'scene': '1', 'characters': {}}]}),
            ('continuity_diff', {'bible': {'characters': {}},
                                 'shots': [{'id': 'a', 'characters': {}}]}),
        ]
        for op, params in cases:
            with self.subTest(op=op, params=params):
                with self.assertRaises(ValueError):
                    D.run(op, params)

    def test_module_hygiene(self):
        tree = ast.parse(inspect.getsource(D))
        banned = {'os', 'subprocess', 'socket', 'urllib', 'http', 'shutil', 'sqlite3', 'ctypes'}
        stdlib_ok = {'__future__', 'math', 'random', 'colorsys', 'unicodedata', 'hashlib', 'json'}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    root = a.name.split('.')[0]
                    self.assertNotIn(root, banned)
                    self.assertIn(root, stdlib_ok)
            elif isinstance(node, ast.ImportFrom):
                root = (node.module or '').split('.')[0]
                self.assertNotIn(root, banned)
                self.assertIn(root, stdlib_ok)
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                self.assertNotIn(node.func.id, {'open', 'exec', 'eval', 'compile', 'print', '__import__'})

    def test_all_svg_outputs_are_safe(self):
        svgs = [D.run('landscape_layers', {})['result']['svg'],
                D.run('arabic_text_layout', {'text': 'a <b> & "c" سلام'})['result']['svg']]
        svgs += [m['svg'] for m in D.run('logo_marks', {})['result']['marks']]
        for s in svgs:
            with self.subTest(svg=s[:40]):
                _svg_safe(self, s)


class TestFrameComposition(unittest.TestCase):  # 13.01
    def one(self, elements):
        return D.run('frame_composition', {'elements': elements})['result']['shots'][0]

    def test_thirds_point_beats_corner(self):
        on = self.one([{'id': 's', 'x': 640 - 50, 'y': 360 - 100, 'w': 100, 'h': 200, 'subject': True}])
        corner = self.one([{'id': 's', 'x': 0, 'y': 0, 'w': 100, 'h': 200, 'subject': True}])
        self.assertAlmostEqual(on['subjects'][0]['distance_px'], 0.0, places=6)
        self.assertEqual(on['thirds_score'], 1.0)
        self.assertGreater(on['score'], corner['score'])
        self.assertGreater(on['thirds_score'], corner['thirds_score'])

    def test_symmetric_layout_balanced(self):
        r = self.one([{'id': 'a', 'x': 400, 'y': 340, 'w': 200, 'h': 400},
                      {'id': 'b', 'x': 1320, 'y': 340, 'w': 200, 'h': 400}])
        self.assertTrue(r['balanced'])
        self.assertAlmostEqual(r['centroid_offset'][0], 0.0, places=9)
        self.assertAlmostEqual(r['centroid_offset_mag'], 0.0, places=9)
        lop = self.one([{'id': 'a', 'x': 0, 'y': 300, 'w': 300, 'h': 400}])
        self.assertFalse(lop['balanced'])
        self.assertLess(lop['centroid_offset'][0], 0)

    def test_default_reviews_five_shots(self):
        r = D.run('frame_composition', {})['result']
        self.assertEqual(len(r['shots']), 5)
        self.assertEqual(r['best'], 'thirds_hero')
        self.assertIn(r['worst'], {'corner', 'cramped_headroom'})
        sym = next(s for s in r['shots'] if s['id'] == 'symmetric_pair')
        self.assertTrue(sym['balanced'])
        cramped = next(s for s in r['shots'] if s['id'] == 'cramped_headroom')
        self.assertTrue(any('cramped headroom' in e for e in cramped['explain']))

    def test_both_inputs_rejected(self):
        with self.assertRaises(ValueError):
            D.run('frame_composition', {'elements': [], 'shots': []})


class TestLandscape(unittest.TestCase):  # 13.02
    def test_no_gaps_deterministic_far_lighter(self):
        for layers in (2, 3, 5):
            with self.subTest(layers=layers):
                p = {'seed': 42, 'layers': layers, 'samples': 129}
                a, b = D.run('landscape_layers', p)['result'], D.run('landscape_layers', p)['result']
                self.assertEqual(a['svg'], b['svg'])
                self.assertTrue(a['seam_check']['ok'])
                self.assertEqual(a['seam_check']['gap_count'], 0)
                self.assertTrue(a['atmospheric_perspective']['far_lighter'])
                self.assertTrue(a['atmospheric_perspective']['far_less_saturated'])
                root = _svg_safe(self, a['svg'])
                self.assertEqual(len([e for e in root.iter(SVG + 'path')]), layers)
                self.assertIsNotNone(root.find(f'{SVG}defs/{SVG}linearGradient'))
        self.assertNotEqual(D.run('landscape_layers', {'seed': 1})['result']['svg'],
                            D.run('landscape_layers', {'seed': 2})['result']['svg'])

    def test_thin_bands_are_reported_as_gaps(self):
        r = D.run('landscape_layers', {'seed': 3, 'fill_to_bottom': False, 'band_px': 4.0})['result']
        self.assertFalse(r['seam_check']['ok'])
        self.assertGreater(r['seam_check']['gap_count'], 0)


class TestThreePointLight(unittest.TestCase):  # 13.03
    def test_shadow_opposite_key_passes_and_toward_fails(self):
        base = D.run('three_point_light', {})['result']
        sd = base['expected_shadow']['direction']
        ok = D.run('three_point_light', {'shadow_vector': sd})['result']['shadow_validation']
        self.assertTrue(ok['passes'])
        self.assertLess(ok['angle_error_deg'], 1e-6)
        bad = D.run('three_point_light', {'shadow_vector': [-sd[0], -sd[1]]})['result']['shadow_validation']
        self.assertFalse(bad['passes'])
        self.assertTrue(bad['points_toward_key'])

    def test_geometry_and_ratios(self):
        r = D.run('three_point_light', {'key_fill_ratio': 4.0})['result']
        key = r['lights']['key']['position']
        # camera at -y looking +y: camera-left is -x, key is in front (toward camera) and above
        self.assertLess(key[0], 0)
        self.assertLess(key[1], 0)
        self.assertGreater(key[2], 1.0)
        self.assertGreater(r['lights']['fill']['position'][0], 0)
        self.assertGreater(r['lights']['rim']['position'][1], 0)
        self.assertAlmostEqual(r['lights']['fill']['intensity'], 0.25)
        self.assertAlmostEqual(r['contrast_stops'], 2.0)
        sd = r['expected_shadow']['direction']
        self.assertGreater(sd[0], 0)
        self.assertGreater(sd[1], 0)
        self.assertAlmostEqual(r['expected_shadow']['length_per_metre_of_height'],
                               1 / math.tan(math.radians(35)), places=4)


class TestPalette(unittest.TestCase):  # 13.04
    def test_black_on_white_and_formula(self):
        r = D.run('palette_harmony', {'pairs': [['#000000', '#ffffff'], {'fg': '#3366cc', 'bg': '#f0f0f0'},
                                               {'fg': '#777', 'bg': '#fff'}]})['result']
        self.assertAlmostEqual(r['pairs'][0]['contrast'], 21.0, places=6)
        la, lb = _wcag_lum('#3366cc'), _wcag_lum('#f0f0f0')
        expect = (max(la, lb) + 0.05) / (min(la, lb) + 0.05)
        self.assertLess(abs(r['pairs'][1]['contrast'] - expect), 0.01)
        grey = r['pairs'][2]
        self.assertTrue(grey['flagged'])
        self.assertLess(grey['contrast'], 4.5)
        self.assertTrue(grey['passes_aa_large'])
        large = D.run('palette_harmony', {'pairs': [{'fg': '#777', 'bg': '#fff', 'size': 'large'}]})['result']
        self.assertFalse(large['pairs'][0]['flagged'])

    def test_harmony_hues(self):
        r = D.run('palette_harmony', {'base': '#ff0000'})['result']['palettes']
        self.assertEqual([s['hex'] for s in r['complementary']], ['#ff0000', '#00ffff'])
        self.assertEqual([s['hex'] for s in r['triadic']], ['#ff0000', '#00ff00', '#0000ff'])
        self.assertEqual(len(r['analogous']), 3)
        self.assertEqual(len(r['split']), 3)
        self.assertAlmostEqual(r['split'][1]['hsl'][0], 150.0, places=0)


class TestArabicText(unittest.TestCase):  # 13.05
    def test_marks_stay_attached_and_lam_alef_detected(self):
        text = 'مَرْحَبًا بِالسَّلَامِ فِي كُلِّ مَكَانٍ لَا'
        r = D.run('arabic_text_layout', {'text': text})['result']
        self.assertEqual(r['direction'], 'rtl')
        for w in r['words']:
            self.assertEqual(''.join(w['graphemes']), w['word'])
            self.assertEqual(w['orphan_marks'], 0)
            for g in w['graphemes']:
                self.assertEqual(unicodedata.combining(g[0]), 0, g)
                self.assertTrue(all(unicodedata.combining(c) for c in g[1:]), g)
        self.assertIn('بِالسَّلَامِ', r['lam_alef_words'])
        self.assertIn('لَا', r['lam_alef_words'])
        self.assertNotIn('فِي', r['lam_alef_words'])
        kull = next(w for w in r['words'] if w['word'] == 'كُلِّ')
        self.assertEqual(kull['shadda'], 1)
        self.assertEqual(next(w for w in r['words'] if w['word'] == 'مَكَانٍ')['tanween'], 1)
        sh = next(g for g in kull['graphemes'] if 'ّ' in g)
        self.assertEqual(sh[0], 'ل')

    def test_svg_rtl_and_timings(self):
        r = D.run('arabic_text_layout', {'duration': 4.0, 'start': 1.0})['result']
        root = _svg_safe(self, r['svg'])
        t = root.find(SVG + 'text')
        self.assertEqual(t.get('direction'), 'rtl')
        self.assertEqual(t.get('unicode-bidi'), 'embed')
        self.assertIn('HarfBuzz', r['shaping'])
        self.assertAlmostEqual(r['words'][0]['start'], 1.0)
        self.assertAlmostEqual(r['timeline_end'], 5.0, places=3)
        starts = [w['start'] for w in r['words']]
        self.assertEqual(starts, sorted(starts))

    def test_normalisation_and_ltr(self):
        r = D.run('arabic_text_layout', {'text': '‏سـلام  عليكم'})['result']
        self.assertEqual(r['normalised'], 'سلام عليكم')
        self.assertEqual(r['removed_controls'], 2)
        self.assertEqual(D.run('arabic_text_layout', {'text': 'Hello عالم'})['result']['direction'], 'ltr')


class TestLogoMarks(unittest.TestCase):  # 13.06
    def test_self_flagged_and_deterministic(self):
        a = D.run('logo_marks', {'seed': 7, 'count': 1})['result']['marks'][0]
        b = D.run('logo_marks', {'seed': 7, 'count': 1})['result']['marks'][0]
        self.assertEqual(a['signature'], b['signature'])
        self.assertEqual(a['svg'], b['svg'])
        r = D.run('logo_marks', {'seed': 7, 'count': 1,
                                 'references': [{'id': 'mine', 'signature': a['signature']}]})['result']
        self.assertTrue(r['marks'][0]['flagged'])
        self.assertAlmostEqual(r['marks'][0]['max_reference_cosine'], 1.0, places=5)

    def test_different_seeds_usually_differ(self):
        sigs = [m['signature'] for m in D.run('logo_marks', {'seed': 100, 'count': 12})['result']['marks']]
        distinct = sum(1 for i in range(len(sigs)) for j in range(i + 1, len(sigs))
                       if D._cos(sigs[i], sigs[j]) < 0.95)
        total = len(sigs) * (len(sigs) - 1) // 2
        self.assertGreater(distinct / total, 0.7)
        r = D.run('logo_marks', {'seed': 1, 'count': 1, 'references': [sigs[5]]})['result']
        self.assertEqual(len(r['marks'][0]['signature']), r['signature_length'])


class TestPoster(unittest.TestCase):  # 13.07
    def test_default_layout_passes(self):
        r = D.run('poster_hierarchy', {})['result']
        self.assertTrue(r['ok'], r['issues'])
        self.assertEqual(r['direction'], 'rtl')
        self.assertLess(r['reading_order'].index('title'), r['reading_order'].index('price'))
        self.assertLess(r['reading_order'].index('price'), r['reading_order'].index('cta'))
        self.assertEqual(r['reading_order'][0], 'logo')

    def test_cta_smaller_than_body_flagged(self):
        els = [dict(e) for e in D._DEFAULT_POSTER]
        next(e for e in els if e['id'] == 'cta')['font_px'] = 30
        r = D.run('poster_hierarchy', {'elements': els})['result']
        self.assertFalse(r['ok'])
        self.assertIn('cta_smaller_than_body', {i['rule'] for i in r['issues']})

    def test_small_fonts_order_and_thumb_zone(self):
        els = [dict(e) for e in D._DEFAULT_POSTER]
        cta = next(e for e in els if e['id'] == 'cta')
        cta['y'] = 20
        r = D.run('poster_hierarchy', {'elements': els})['result']
        rules = {i['rule'] for i in r['issues']}
        self.assertIn('thumb_zone', rules)
        self.assertIn('reading_order', rules)
        # same layout drawn on a 2160 px canvas with unchanged px sizes -> halved at 1080
        r2 = D.run('poster_hierarchy', {'width': 2160, 'height': 2700})['result']
        self.assertIn('min_font', {i['rule'] for i in r2['issues']})


class TestInterior(unittest.TestCase):  # 13.08
    def test_valid_layout_passes(self):
        r = D.run('interior_layout', {})['result']
        self.assertTrue(r['ok'], r['issues'])
        self.assertTrue(all(z['reachable'] for z in r['zones']))

    def test_overlap_reported(self):
        furn = [dict(f) for f in D._DEFAULT_FURNITURE] + [{'id': 'lamp', 'x': 210, 'y': 200, 'w': 30, 'h': 30}]
        r = D.run('interior_layout', {'room': dict(D._DEFAULT_ROOM), 'furniture': furn})['result']
        self.assertFalse(r['ok'])
        self.assertIn({'a': 'coffee_table', 'b': 'lamp', 'area_cm2': 900.0}, r['overlaps'])

    def test_blocked_walkway_detected(self):
        furn = [dict(f) for f in D._DEFAULT_FURNITURE] + [{'id': 'shelf', 'x': 0, 'y': 120, 'w': 450, 'h': 40}]
        r = D.run('interior_layout', {'room': dict(D._DEFAULT_ROOM), 'door': dict(D._DEFAULT_DOOR),
                                      'furniture': furn})['result']
        blocked = {z['id'] for z in r['zones'] if not z['reachable']}
        self.assertIn('sofa', blocked)
        self.assertIn('blocked_path', {i['rule'] for i in r['issues']})

    def test_door_swing_and_zones(self):
        furn = [{'id': 'plant', 'x': 50, 'y': 10, 'w': 30, 'h': 30}]
        r = D.run('interior_layout', {'room': {'w': 400, 'h': 300}, 'furniture': furn,
                                      'zones': [{'id': 'window', 'x': 350, 'y': 250}]})['result']
        self.assertEqual(r['door_swing_blocked'], ['plant'])
        self.assertEqual(r['zones'][0]['id'], 'window')


class TestHorizon(unittest.TestCase):  # 13.09
    def test_zero_tilt_centre_and_halving(self):
        r = D.run('horizon_fov', {'tilt_deg': 0.0, 'frame_height': 1080, 'distances': [5.0, 10.0, 20.0]})['result']
        self.assertAlmostEqual(r['horizon_y'], 540.0, places=9)
        h = [p['height_px'] for p in r['people']]
        self.assertAlmostEqual(h[1], h[0] / 2, places=3)
        self.assertAlmostEqual(h[2], h[1] / 2, places=3)
        self.assertAlmostEqual(h[0], r['people'][0]['pinhole_height_px'], places=3)
        up = D.run('horizon_fov', {'tilt_deg': 10.0})['result']
        self.assertGreater(up['horizon_y'], 540.0)

    def test_shot_consistency(self):
        r = D.run('horizon_fov', {})['result']
        self.assertEqual(r['consistency']['outliers'], ['s3'])
        ok = D.run('horizon_fov', {'shots': [{'id': 'a', 'horizon_y': 540}, {'id': 'b', 'horizon_y': 544},
                                             {'id': 'c', 'horizon_y': 538, 'tilt_deg': 0}]})['result']
        self.assertTrue(ok['consistency']['all_consistent'])


class TestContinuity(unittest.TestCase):  # 13.10
    def test_missing_prop_between_shots(self):
        r = D.run('continuity_diff', {})['result']
        self.assertIn({'from': '1A', 'to': '1B', 'scene': '1', 'type': 'prop_missing',
                       'character': 'nour', 'prop': 'umbrella'}, r['between_shots'])
        self.assertFalse(r['ok'])
        self.assertFalse(any(d['type'] == 'palette_drift' for d in r['between_shots']))

    def test_outfit_palette_and_scene_boundary(self):
        bible = {'characters': {'a': {'outfit': 'red', 'props': ['hat']}}, 'palette': ['#ff0000', '#000000']}
        shots = [{'id': '1', 'scene': 1, 'palette': ['#ff0000', '#000000'],
                  'characters': {'a': {'outfit': 'red', 'props': ['hat']}}},
                 {'id': '2', 'scene': 1, 'palette': ['#0000ff', '#ffffff'],
                  'characters': {'a': {'outfit': 'green', 'props': ['hat']}}},
                 {'id': '3', 'scene': 2, 'characters': {'a': {'outfit': 'blue', 'props': []}}}]
        r = D.run('continuity_diff', {'bible': bible, 'shots': shots})['result']
        types = [d['type'] for d in r['between_shots']]
        self.assertIn('outfit_changed', types)
        self.assertIn('palette_drift', types)
        self.assertFalse(any(d['to'] == '3' for d in r['between_shots']))
        self.assertTrue(any(d['type'] == 'outfit_mismatch' and d['shot'] == '2' for d in r['vs_bible']))


if __name__ == '__main__':
    unittest.main()
