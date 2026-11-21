"""Acceptance tests for styles_v23 (topics 06.01-06.10)."""
import ast
import inspect
import json
import math
import time
import unittest
import xml.etree.ElementTree as ET

import styles_v23 as S

FORBIDDEN_IMPORTS = {'subprocess', 'socket', 'urllib', 'http', 'shutil', 'os', 'sqlite3', 'ctypes'}

try:  # optional rasterisation check
    import cairosvg
except Exception:  # pragma: no cover - depends on environment
    cairosvg = None


def walk_svgs(obj):
    if isinstance(obj, dict):
        for v in obj.values():
            yield from walk_svgs(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from walk_svgs(v)
    elif isinstance(obj, str) and obj.lstrip().startswith('<svg'):
        yield obj


def assert_safe_svg(tc, svg):
    root = ET.fromstring(svg)
    tc.assertTrue(root.tag.endswith('svg'))
    for el in root.iter():
        tag = el.tag.rsplit('}', 1)[-1].lower()
        tc.assertNotIn(tag, ('script', 'foreignobject', 'iframe'))
        for k, v in el.attrib.items():
            lk = k.rsplit('}', 1)[-1].lower()
            tc.assertFalse(lk.startswith('on'), lk)
            if lk == 'href':
                tc.assertTrue(v.startswith('#'))
            if 'url(' in v:
                tc.assertIn('url(#', v)
    tc.assertNotIn('http://', svg.replace('xmlns="http://www.w3.org/2000/svg"', ''))


class TestInterface(unittest.TestCase):
    def test_static_rules(self):
        tree = ast.parse(inspect.getsource(S))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported |= {a.name.split('.')[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split('.')[0])
            elif isinstance(node, ast.Call):
                self.assertNotIn(getattr(node.func, 'id', None),
                                 ('open', 'exec', 'eval', 'compile', 'print', '__import__'))
        self.assertFalse(imported & FORBIDDEN_IMPORTS)
        self.assertNotIn('cairosvg', imported)
        self.assertEqual(list(S.TOPICS), [f'06.{i:02d}' for i in range(1, 11)])
        self.assertEqual(set(S.TOPICS.values()), set(S.OPS))
        self.assertEqual(set(S.TOPIC_NAMES_AR), set(S.TOPICS))

    def test_every_op_runs_with_defaults_and_svg_is_safe(self):
        for op in S.TOPICS.values():
            with self.subTest(op=op):
                start = time.perf_counter()
                out = S.run(op, {})
                self.assertLess(time.perf_counter() - start, 1.0)
                self.assertEqual(set(out), {'op', 'result', 'assumptions', 'limits'})
                self.assertEqual(out['op'], op)
                self.assertTrue(out['assumptions'] and out['limits'])
                self.assertEqual(json.loads(json.dumps(out, allow_nan=False)), out)
                self.assertEqual(S.run(op, {}), out)  # deterministic
                for svg in walk_svgs(out['result']):
                    assert_safe_svg(self, svg)

    def test_svgs_rasterise_when_cairosvg_available(self):
        if cairosvg is None:
            self.skipTest('cairosvg not installed')
        for op in ('rough_lines', 'clay_look', 'flat_cartoon', 'machine_drawing', 'watercolor',
                   'mono_style', 'reference_character'):
            with self.subTest(op=op):
                svgs = list(walk_svgs(S.run(op, {})['result']))
                self.assertTrue(svgs)
                png = cairosvg.svg2png(bytestring=svgs[0].encode('utf-8'))
                self.assertTrue(png.startswith(b'\x89PNG') and len(png) > 200)

    def test_dispatch_rejections_are_value_errors(self):
        with self.assertRaises(ValueError):
            S.run('nope', {})
        with self.assertRaises(ValueError):
            S.run('rough_lines', [])
        for op in S.OPS:
            with self.subTest(op=op), self.assertRaises(ValueError):
                S.run(op, {'shell': 'rm -rf /'})
        bad = [('rough_lines', {'seed': True}), ('rough_lines', {'roughness': float('nan')}),
               ('rough_lines', {'shape': 'polyline', 'points': [[0, 0]]}),
               ('clay_look', {'base': 'red'}), ('flat_cartoon', {'poses': [{'angles': {'tail': 3}}]}),
               ('machine_drawing', {'teeth': 2}), ('watercolor', {'depth': 9}),
               ('mono_style', {'svg': '<svg xmlns="http://www.w3.org/2000/svg"><script>x</script></svg>'}),
               ('mono_style', {'svg': '<!DOCTYPE x [<!ENTITY a "b">]><svg/>'}),
               ('palette_lock', {'identity': {'name': 'x', 'palette': {'a': '#fff'}}}),
               ('style_guide_check', {'shots': 'abc'}),
               ('style_descriptor', {'descriptor': {'shading': 'flat'}})]
        for op, params in bad:
            with self.subTest(op=op, params=params), self.assertRaises(ValueError):
                S.run(op, params)


class TestPaletteLock(unittest.TestCase):  # 06.01
    ID = {'name': 'hero', 'palette': {'bg': '#FFFFFF', 'ink': '#111111', 'coat': '#b23a48'}}

    def scene(self, coat):
        return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10">'
                '<rect width="10" height="10" fill="#fff"/>'
                f'<circle cx="5" cy="5" r="3" style="fill:{coat};stroke:#111111"/></svg>')

    def test_same_identity_scenes_pass_and_fingerprint_is_canonical(self):
        r = S.run('palette_lock', {'identity': self.ID,
                                   'scenes': [self.scene('#b23a48'), {'name': 'b', 'svg': self.scene('#B23A48')}]})
        self.assertTrue(r['result']['all_passed'])
        swapped = {'name': 'other', 'palette': {'z': '#b23a48', 'a': '#ffffff', 'm': '#111'}}
        r2 = S.run('palette_lock', {'identity': swapped, 'scenes': [self.scene('#b23a48')]})
        self.assertEqual(r['result']['palette_fingerprint'], r2['result']['palette_fingerprint'])
        self.assertNotEqual(r['result']['roles_fingerprint'], r2['result']['roles_fingerprint'])

    def test_off_palette_colour_is_reported_and_tint_tolerated(self):
        r = S.run('palette_lock', {'identity': self.ID,
                                   'scenes': [self.scene('#b33a48'), self.scene('#22c55e')]})['result']
        self.assertTrue(r['scenes'][0]['passed'])  # tint within dE76 <= 2
        self.assertFalse(r['scenes'][1]['passed'])
        self.assertEqual([o['colour'] for o in r['scenes'][1]['off_palette']], ['#22c55e'])
        self.assertFalse(r['all_passed'])

    def test_unparsed_colour_fails(self):
        svg = '<svg xmlns="http://www.w3.org/2000/svg"><rect fill="hsl(10,50%,50%)"/></svg>'
        r = S.run('palette_lock', {'identity': self.ID, 'scenes': [svg]})['result']
        self.assertFalse(r['scenes'][0]['passed'])
        self.assertTrue(r['scenes'][0]['unparsed'])


class TestRoughLines(unittest.TestCase):  # 06.02
    def test_seed_determinism_and_variation(self):
        for shape in ('rectangle', 'circle', 'polyline'):
            with self.subTest(shape=shape):
                a = S.run('rough_lines', {'shape': shape, 'seed': 5})['result']
                b = S.run('rough_lines', {'shape': shape, 'seed': 5})['result']
                c = S.run('rough_lines', {'shape': shape, 'seed': 6})['result']
                self.assertEqual(a['svg'], b['svg'])
                self.assertNotEqual(a['paths'], c['paths'])

    def test_endpoints_within_roughness_bound(self):
        for rough in (0.0, 0.5, 3.0):
            r = S.run('rough_lines', {'shape': 'polyline', 'points': [[0, 0], [50, 10], [90, 60]],
                                      'roughness': rough, 'strokes': 3, 'seed': 2})['result']
            self.assertTrue(r['within_bound'])
            self.assertLessEqual(r['endpoint_max_deviation'], rough * math.sqrt(2) + 1e-3)
            self.assertEqual(len(r['paths']), 3)
            # parse first M of each subpath and compare with source vertices
            for sub in r['paths'][0].split('M')[1:]:
                x, y = map(float, sub.split('C')[0].split())
                self.assertLessEqual(min(math.dist((x, y), p) for p in r['source_points']),
                                     rough * math.sqrt(2) + 1e-3)


class TestClay(unittest.TestCase):  # 06.03
    def test_default_passes_and_high_specular_fails(self):
        r = S.run('clay_look', {})['result']
        self.assertTrue(r['audit']['passed'])
        self.assertIn('feGaussianBlur', r['svg'])
        self.assertIn('radialGradient', r['svg'])
        self.assertAlmostEqual(r['audit']['gloss_ratio'], 0.12, delta=0.01)
        bad = S.run('clay_look', {'specular': 0.6})['result']
        self.assertFalse(bad['audit']['passed'])

    def test_audit_external_svg(self):
        glossy = S.run('clay_look', {'specular': 0.6})['result']['svg']
        r = S.run('clay_look', {'audit_svg': glossy})['result']
        self.assertEqual(r['mode'], 'audit')
        self.assertFalse(r['audit']['passed'])


class TestFlatCartoon(unittest.TestCase):  # 06.04
    def test_three_poses_keep_proportions(self):
        r = S.run('flat_cartoon', {})['result']
        self.assertEqual(len(r['poses']), 3)
        nominal = r['nominal_bone_lengths']
        ratios = [p['head_ratio'] for p in r['poses']]
        for p in r['poses']:
            for k, v in p['bone_lengths'].items():
                self.assertLess(abs(v - nominal[k]), 1e-9, k)
        self.assertLess(max(ratios) - min(ratios), 1e-9)
        self.assertTrue(r['proportion_lock']['locked'])
        # poses actually differ
        self.assertNotEqual(r['poses'][0]['joints']['r_wrist'], r['poses'][1]['joints']['r_wrist'])
        root = ET.fromstring(r['poses'][0]['svg'])
        ids = {el.get('id') for el in root.iter() if el.get('data-pivot')}
        self.assertTrue({'part-head', 'part-torso', 'part-l_upper_arm', 'part-r_shin'} <= ids)


class TestMachineDrawing(unittest.TestCase):  # 06.05
    def test_pitch_diameter_and_fit(self):
        r = S.run('machine_drawing', {'module': 2.5, 'teeth': 24})['result']
        self.assertEqual(r['gear']['pitch_diameter'], 2.5 * 24)
        self.assertAlmostEqual(r['gear']['tip_diameter'], 2.5 * 26)
        self.assertTrue(r['connection_ok'])
        self.assertIn('PCD', r['svg'])

    def test_mismatched_shaft_reported(self):
        r = S.run('machine_drawing', {'bore': 10.0, 'shaft_diameter': 10.5, 'link_hole': 10.6})['result']
        self.assertFalse(r['connection_ok'])
        self.assertIn('interference', [i['code'] for i in r['issues']])
        loose = S.run('machine_drawing', {'bore': 12.0, 'shaft_diameter': 10.0, 'link_hole': 10.05})['result']
        self.assertIn('too_loose', [i['code'] for i in loose['issues']])


class TestWatercolor(unittest.TestCase):  # 06.06
    def test_roughness_in_expected_range_and_deterministic(self):
        prev = -1.0
        for spread in (0.0, 0.05, 0.12, 0.25):
            r = S.run('watercolor', {'spread': spread, 'seed': 3})['result']
            lo, hi = r['expected_range']
            self.assertTrue(lo <= r['edge_roughness'] <= hi, (spread, r['edge_roughness'], lo, hi))
            self.assertGreater(r['edge_roughness'], prev)
            prev = r['edge_roughness']
        self.assertEqual(S.run('watercolor', {'seed': 9})['result']['svg'],
                         S.run('watercolor', {'seed': 9})['result']['svg'])
        self.assertNotEqual(S.run('watercolor', {'seed': 9})['result']['svg'],
                            S.run('watercolor', {'seed': 10})['result']['svg'])


class TestMono(unittest.TestCase):  # 06.07
    def test_luminance_formula_and_contrast(self):
        r = S.run('mono_style', {'colors': ['#ff0000', '#00ff00', '#0000ff', '#ffffff'],
                                 'line_colors': ['#cccccc', '#000000']})['result']
        ys = [p['luminance'] for p in r['palette']]
        for y, want in zip(ys, (0.2126, 0.7152, 0.0722, 1.0)):
            self.assertAlmostEqual(y, want, places=12)
        mid = ((0x80 / 255 + 0.055) / 1.055) ** 2.4
        self.assertAlmostEqual(S.run('mono_style', {'colors': ['#808080']})['result']['palette'][0]['luminance'],
                               mid, places=12)
        self.assertFalse(r['line_checks'][0]['passed'])  # light gray on white
        self.assertTrue(r['line_checks'][1]['passed'])
        self.assertAlmostEqual(r['line_checks'][1]['contrast'], 21.0, places=6)
        self.assertGreater(r['line_checks'][1]['line_weight'], r['line_checks'][0]['line_weight'])

    def test_scene_converted_to_gray(self):
        r = S.run('mono_style', {})['result']
        self.assertEqual(r['non_gray_left'], [])
        self.assertNotIn('#b23a48', r['svg'])


class TestReferenceCharacter(unittest.TestCase):  # 06.08
    SHEET = {'id': 'mira', 'attributes': {'outfit': {'jacket': '#2a9d8f', 'boots': '#3d2b1f'},
                                          'accessories': ['backpack'], 'silhouette': 'short_round'}}

    def test_changed_jacket_flagged(self):
        scene = {'shot': 's2', 'characters': [{'id': 'mira', 'outfit': {'jacket': '#e76f51', 'boots': '#3d2b1f'},
                                               'accessories': ['backpack']}]}
        r = S.run('reference_character', {'sheet': self.SHEET, 'scene': scene})['result']
        self.assertFalse(r['consistent'])
        self.assertEqual([c['field'] for c in r['characters'][0]['changes']], ['outfit.jacket'])
        same = {'characters': [{'id': 'mira', 'outfit': {'jacket': '#2a9d8f', 'boots': '#3d2b1f'},
                                'accessories': ['backpack'], 'silhouette': 'short_round'}]}
        self.assertTrue(S.run('reference_character', {'sheet': self.SHEET, 'scene': same})['result']['consistent'])

    def test_sensitive_fields_rejected(self):
        for key in ('ethnicity', 'Religion', 'health_notes'):
            bad = {'id': 'mira', 'attributes': {'outfit': {'jacket': '#2a9d8f'}, key: 'x'}}
            with self.subTest(key=key), self.assertRaises(ValueError):
                S.run('reference_character', {'sheet': bad})
        scene = {'characters': [{'id': 'mira', 'outfit': {'jacket': '#2a9d8f'}, 'religion': 'x'}]}
        with self.assertRaises(ValueError):
            S.run('reference_character', {'sheet': self.SHEET, 'scene': scene})


class TestStyleGuide(unittest.TestCase):  # 06.09
    def test_two_violations(self):
        shots = [{'id': 'ok', 'colours': ['#0f172a'], 'title': {'font': 'inter', 'zone': 'bottom_left'},
                  'text_order': ['title', 'credit']},
                 {'id': 'bad', 'colours': ['#0f172a', '#22c55e'], 'title': {'font': 'Inter', 'position': [0.5, 0.1]},
                  'text_order': ['title', 'subtitle']}]
        r = S.run('style_guide_check', {'shots': shots})['result']
        self.assertTrue(r['shots'][0]['passed'])
        self.assertEqual(r['shots'][1]['count'], 2)
        self.assertEqual(sorted(v['code'] for v in r['shots'][1]['violations']), ['foreign_colour', 'title_zone'])
        order = S.run('style_guide_check', {'shots': [{'id': 'x', 'text_order': ['credit', 'title']}]})['result']
        self.assertEqual(order['shots'][0]['violations'][0]['code'], 'text_order')


class TestStyleDescriptor(unittest.TestCase):  # 06.10
    PROV = {'source': 'original', 'author': 'team'}

    def test_blocked_name_rejected(self):
        for notes in ('in the style of Studio Ghibli', 'like PIXAR films', 'بأسلوب ديزني', 'Pokémon vibes'):
            d = {'shading': 'cel', 'notes': notes, 'provenance': self.PROV}
            r = S.run('style_descriptor', {'descriptor': d})['result']
            with self.subTest(notes=notes):
                self.assertEqual(r['status'], 'rejected')
                self.assertIsNone(r['prompt'])
        custom = S.run('style_descriptor', {'descriptor': {'notes': 'like acme toons', 'provenance': self.PROV},
                                            'extra_blocklist': ['Acme Toons']})['result']
        self.assertEqual(custom['status'], 'rejected')

    def test_neutral_accepted_with_provenance(self):
        d = {'line_weight': 2.5, 'palette_mood': 'cool', 'shading': 'flat', 'texture': 'grain',
             'notes': 'geometric shapes, marvellous dusk sky', 'provenance': self.PROV}
        r = S.run('style_descriptor', {'descriptor': d})['result']
        self.assertEqual(r['status'], 'accepted')
        self.assertEqual(r['provenance']['source'], 'original')
        self.assertEqual(len(r['descriptor_id']), 64)
        self.assertIn('cool palette', r['prompt'])
        with self.assertRaises(ValueError):
            S.run('style_descriptor', {'descriptor': {'shading': 'flat', 'notes': 'x'}})
        with self.assertRaises(ValueError):
            S.run('style_descriptor', {'descriptor': {'provenance': {'source': 'licensed', 'author': 'a'}}})


if __name__ == '__main__':
    unittest.main()
