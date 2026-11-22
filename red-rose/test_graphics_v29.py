"""W05: every graphics.motion op exercised with realistic inputs (graphics_v27)."""
import inspect
import json
import re
import unittest
import xml.etree.ElementTree as ET

import graphics_v27 as G

SVG_NS = 'http://www.w3.org/2000/svg'
STOPS = [{'name': 'القاهرة', 'lat': 30.04, 'lon': 31.24}, {'name': 'دبي', 'lat': 25.2, 'lon': 55.27},
         {'name': 'لندن', 'lat': 51.5, 'lon': -0.12}]

REALISTIC = {
    'shape_morph': {'from_shape': 'circle', 'to_shape': 'rose', 't': 1.0},
    'draw_on': {'points': [[100, 100], [400, 300], [800, 120]], 'style': 'marker', 't': 1.5},
    'neon_glow': {'text': 'OPEN', 'glow': True, 't': 1.2},
    'textures': {'overlays': ['grain', 'vignette'], 't': 0.5},
    'particles_svg': {'kind': 'confetti', 'count': 120, 't': 2.0},
    'data_viz': {'chart': 'bar', 'labels': ['القاهرة', 'الإسكندرية', 'الجيزة'], 'values': [22, 5.4, 9.1],
                 'title': 'السكان بالمليون', 't': 1.5},
    'route_map': {'stops': STOPS, 't': 2.5},
    'explainer_diagram': {'components': ['المدخل', 'المعالجة', 'المخرج'], 't': 4.0},
    'retro_pixel': {'crt': True, 't': 1.0, 'width': 1280, 'height': 720},
    'ui_mock': {'device': 'laptop', 't': 2.5},
    'brand_reveal': {'pattern': 'circle_wipe', 't': 1.2, 'fill_background': True},
}


def parse(res):
    r = res['result']
    return ET.fromstring(G.svg_document(r['svg'], r['width'], r['height']))


class OpsContract(unittest.TestCase):
    def test_ops_are_named_callables_with_effects(self):
        self.assertEqual(len(G.OPS), 13)
        self.assertEqual(set(G.EFFECTS), set(G.OPS))
        self.assertEqual(set(G.EFFECTS.values()), {'read'})
        for name, fn in G.OPS.items():
            self.assertTrue(callable(fn), name)
            for q in inspect.signature(fn).parameters.values():
                self.assertEqual(q.kind, inspect.Parameter.KEYWORD_ONLY, (name, q.name))
                self.assertIsNot(q.default, inspect.Parameter.empty, (name, q.name))
            self.assertTrue(fn.__doc__ and fn.__doc__.strip(), name)
        for name in REALISTIC:
            params = inspect.signature(G.OPS[name]).parameters
            for p in ('t', 'width', 'height', 'id_prefix'):
                self.assertIn(p, params)

    def test_zero_argument_calls_still_succeed(self):
        for name in G.OPS:
            out = G.run(name, {})
            self.assertEqual(set(out), {'op', 'result', 'assumptions', 'limits'}, name)
            json.dumps(out, allow_nan=False)

    def test_unknown_parameter_lists_allowed(self):
        for name, fn in G.OPS.items():
            with self.assertRaises(ValueError) as cm:
                G.run(name, {'zzz_unknown': 1})
            msg = str(cm.exception)
            self.assertIn('allowed:', msg, name)
            for p in inspect.signature(fn).parameters:
                self.assertIn(p, msg, name)

    def test_direct_op_call_equals_run(self):
        self.assertEqual(G.OPS['route_map'](stops=STOPS, t=1.0), G.run('route_map', {'stops': STOPS, 't': 1.0}))


class Features(unittest.TestCase):
    def test_realistic_runs_parse_and_are_deterministic(self):
        for name, params in REALISTIC.items():
            a = G.run(name, dict(params))
            b = G.run(name, dict(params))
            self.assertEqual(a, b, name)
            root = parse(a)
            self.assertGreater(len(list(root.iter())), 2, name)
            self.assertNotIn('<script', a['result']['svg'])
            self.assertNotIn('href="http', a['result']['svg'])

    def test_overlays_and_glow_only_when_requested(self):
        self.assertNotIn('<filter', G.run('textures', {})['result']['svg'])
        self.assertNotIn('glow', G.run('neon_glow', {'t': 2.0})['result']['svg'])
        self.assertIn('-glow', G.run('neon_glow', {'t': 2.0, 'glow': True})['result']['svg'])

    def test_neon_broken_letter_anchor_is_renderer_neutral(self):
        r = G.run('neon_glow', {'text': 'BAR', 'broken_letter': 1, 't': 2.0})['result']
        root = parse({'result': r})
        lit = root.findall('.//{%s}text' % SVG_NS)[-1]
        self.assertEqual(lit.get('text-anchor'), 'start')
        self.assertLess(float(lit.get('x')), 960)
        self.assertEqual(''.join(t.text for t in lit), 'BAR')
        with self.assertRaises(ValueError):
            G.run('neon_glow', {'text': 'باب', 'broken_letter': 1})

    def test_rtl_labels_use_physical_anchor(self):
        r = G.run('data_viz', REALISTIC['data_viz'])['result']
        for el in parse({'result': r}).iter('{%s}text' % SVG_NS):
            if el.get('text-anchor') in ('start', 'end'):
                self.assertNotEqual(el.get('direction'), 'rtl', el.text)

    def test_bar_values_and_arabic_direction(self):
        r = G.run('data_viz', REALISTIC['data_viz'])['result']
        self.assertTrue(r['info'].get('rtl'))
        svg = r['svg']
        for lab in ('القاهرة', 'الإسكندرية', 'الجيزة'):
            self.assertIn(lab, svg)

    def test_route_fills_frame_and_stays_inside(self):
        r = G.run('route_map', {'stops': STOPS, 't': 4.0, 'padding': 0.1})['result']
        circles = [(float(c.get('cx')), float(c.get('cy')))
                   for c in parse({'result': r}).iter('{%s}circle' % SVG_NS)]
        xs = [x for x, _ in circles]
        ys = [y for _, y in circles]
        self.assertTrue(all(0 <= x <= 1920 for x in xs) and all(0 <= y <= 1080 for y in ys))
        # longitude span dominates, so the route must use most of the padded width
        self.assertGreater(max(xs) - min(xs), 0.7 * 1920 * 0.8)
        self.assertTrue(r['info']['schematic'])

    def test_particles_count_and_bounds(self):
        r = G.run('particles_svg', {'kind': 'snow', 'count': 50, 't': 3.0, 'width': 640, 'height': 360})['result']
        circles = list(parse({'result': r}).iter('{%s}circle' % SVG_NS))
        self.assertEqual(len(circles), 50)

    def test_shape_morph_reaches_target(self):
        a = G.run('shape_morph', {'t': 2.0, 'to_shape': 'square'})['result']['svg']
        b = G.run('shape_morph', {'t': 5.0, 'to_shape': 'square'})['result']['svg']
        self.assertEqual(re.sub(r'id="[^"]+"', '', a), re.sub(r'id="[^"]+"', '', b))

    def test_choose_chart_and_catalogue(self):
        self.assertEqual(G.run('choose_chart', {'relationship': 'composition', 'n_parts': 7})['result']['chart'],
                         'stacked')
        self.assertEqual(G.run('choose_chart', {'relationship': 'trend'})['result']['chart'], 'line')
        self.assertEqual(G.run('list_catalogue')['result']['count'], 12)

    def test_render_layer_rejects_unknown_with_allowed(self):
        with self.assertRaises(ValueError) as cm:
            G.render_layer('draw_on', {'bogus': 1}, 1.0, 640, 360)
        self.assertIn('allowed:', str(cm.exception))


if __name__ == '__main__':
    unittest.main()
