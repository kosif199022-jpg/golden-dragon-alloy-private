"""W05: every motion.core op exercised with realistic inputs (motion_v27)."""
import inspect
import json
import re
import unittest
import xml.etree.ElementTree as ET

import motion_v27 as M

SVG_NS = 'http://www.w3.org/2000/svg'


def parse_fragment(frag, w, h):
    return ET.fromstring(f'<svg xmlns="{SVG_NS}" width="{w}" height="{h}">{frag}</svg>')


class OpsContract(unittest.TestCase):
    def test_ops_are_named_callables_with_docstrings(self):
        self.assertEqual(len(M.OPS), 6)
        for name, fn in M.OPS.items():
            self.assertTrue(callable(fn), name)
            sig = inspect.signature(fn)
            for q in sig.parameters.values():
                self.assertEqual(q.kind, inspect.Parameter.KEYWORD_ONLY, (name, q.name))
                self.assertIsNot(q.default, inspect.Parameter.empty, (name, q.name))
            self.assertTrue(fn.__doc__ and fn.__doc__.strip().splitlines()[0], name)

    def test_zero_argument_calls_still_succeed(self):
        for name in M.OPS:
            out = M.run(name, {})
            self.assertEqual(set(out), {'op', 'result', 'assumptions', 'limits'}, name)
            json.dumps(out, allow_nan=False)

    def test_unknown_parameter_lists_allowed(self):
        for name, fn in M.OPS.items():
            with self.assertRaises(ValueError) as cm:
                M.run(name, {'zzz_unknown': 1})
            msg = str(cm.exception)
            self.assertIn('zzz_unknown', msg)
            self.assertIn('allowed:', msg)
            for p in inspect.signature(fn).parameters:
                self.assertIn(p, msg)

    def test_nested_option_errors_list_allowed(self):
        with self.assertRaises(ValueError) as cm:
            M.run('ease', {'name': 'back_out', 'opts': {'bogus': 1}})
        self.assertIn('allowed: overshoot', str(cm.exception))
        with self.assertRaises(ValueError) as cm:
            M.run('track', {'keys': [{'t': 0, 'value': 1, 'x': 2}]})
        self.assertIn('allowed:', str(cm.exception))


class Ease(unittest.TestCase):
    def test_monotone_and_endpoints(self):
        r = M.run('ease', {'name': 'cubic_in_out', 'samples': 51})['result']
        vals = [v for _, v in r['samples']]
        self.assertTrue(all(b >= a - 1e-12 for a, b in zip(vals, vals[1:])))
        self.assertAlmostEqual(vals[0], 0.0)
        self.assertAlmostEqual(vals[-1], 1.0)
        self.assertFalse(r['overshoots'])

    def test_back_out_overshoots_and_spring_at_t(self):
        self.assertTrue(M.run('ease', {'name': 'back_out', 'samples': 41})['result']['overshoots'])
        r = M.run('ease', {'name': 'spring', 't': 0.4, 'opts': {'stiffness': 200, 'damping': 8}})['result']
        self.assertGreater(r['value'], 0.5)

    def test_bezier_matches_css_ease_in_out_symmetry(self):
        r = M.run('ease', {'name': 'cubic_bezier', 'samples': 11,
                           'opts': {'x1': 0.42, 'y1': 0, 'x2': 0.58, 'y2': 1}})['result']
        self.assertAlmostEqual(r['samples'][5][1], 0.5, places=4)


class Track(unittest.TestCase):
    def test_point_track_value_at_t(self):
        r = M.run('track', {'keys': [{'t': 0, 'value': [0, 0]}, {'t': 2, 'value': [100, 50]}],
                            't': 1.0})['result']
        self.assertEqual(r['kind'], 'point')
        self.assertEqual(r['value'], [50.0, 25.0])

    def test_hold_and_times(self):
        keys = [{'t': 0, 'value': 0, 'hold': True}, {'t': 1, 'value': 10}, {'t': 2, 'value': 0}]
        r = M.run('track', {'keys': keys, 'times': [0.5, 1.5, 3]})['result']
        self.assertEqual([v for _, v in r['samples']], [0.0, 5.0, 0.0])

    def test_colour_frames_count(self):
        r = M.run('track', {'duration': 1.5, 'fps': 20})['result']
        self.assertEqual(r['frames'], 30)
        self.assertTrue(all(re.match(r'^#[0-9a-f]{6}$', v) for _, v in r['samples']))


class Transitions(unittest.TestCase):
    def test_every_transition_svg_parses_and_has_background(self):
        for name in M.TRANSITIONS:
            for p in (0.0, 0.45, 1.0):
                r = M.run('transition_frame', {'name': name, 'p': p, 'width': 320, 'height': 180})['result']
                root = parse_fragment(r['svg'], 320, 180)
                self.assertEqual(r['width'], 320)
                self.assertGreaterEqual(len(root.findall('.//{%s}rect' % SVG_NS)), 1, (name, p))

    def test_wipe_left_clip_width_matches_eased_progress(self):
        r = M.run('transition_frame', {'name': 'wipe_left', 'p': 0.3, 'render_svg': False,
                                       'opts': {'ease': 'linear'}})['result']
        clip = r['b']['clip']
        self.assertAlmostEqual(clip['w'], 0.3)
        self.assertAlmostEqual(clip['x'] + clip['w'], 1.0)

    def test_dip_refuses_film_start(self):
        with self.assertRaises(ValueError):
            M.run('transition_frame', {'name': 'dip_to_colour', 'opts': {'at_film_start': True}})


class Camera(unittest.TestCase):
    def test_camera_with_svg_reports_canvas_and_keeps_frame_covered(self):
        svg = '<rect x="0" y="0" width="640" height="360" fill="#246"/>'
        for move in ('push_in', 'pan', 'tilt', 'handheld', 'orbit_2_5d'):
            r = M.run('camera', {'move': move, 't': 1.2, 'svg': svg,
                                 'opts': {'width': 640, 'height': 360}})['result']
            self.assertEqual((r['width'], r['height']), (640, 360))
            parse_fragment(r['svg'], 640, 360)
            cam = r['camera']
            self.assertGreaterEqual(cam['scale'], 1.0, move)

    def test_push_in_scale_grows_monotonically(self):
        r = M.run('camera', {'move': 'push_in', 'samples': 9})['result']
        scales = [c['scale'] for c in r['samples']]
        self.assertTrue(all(b >= a for a, b in zip(scales, scales[1:])))
        self.assertAlmostEqual(scales[-1], 1.25)

    def test_layered_parallax_moves_near_layers_more(self):
        layers = [{'svg': '<rect width="10" height="10"/>', 'layer': 'near'},
                  {'svg': '<rect width="10" height="10"/>', 'layer': 'far'}]
        r = M.run('camera', {'move': 'parallax', 't': 3.0, 'svg': layers,
                             'opts': {'depths': [1.0, 4.0]}})['result']
        ls = r['camera']['layers']
        self.assertGreater(abs(ls[0]['tx']), abs(ls[1]['tx']))
        self.assertEqual(r['svg'].count('data-rr-layer'), 2)


class BeatsAndCatalogue(unittest.TestCase):
    def test_cuts_land_on_beats(self):
        r = M.run('beat_transitions', {'bpm': 120, 'beats_per_transition': 4, 'duration': 10})['result']
        cuts = [x['cut_s'] for x in r['transitions']]
        self.assertEqual(cuts, [2.0, 4.0, 6.0, 8.0])

    def test_dip_not_used_at_frame_zero(self):
        r = M.run('beat_transitions', {'bpm': 60, 'beats_per_transition': 1, 'transition_beats': 1,
                                       'duration': 3, 'names': ['dip_to_colour']})['result']
        self.assertTrue(all(x['start_s'] > 0 or x['name'] != 'dip_to_colour' for x in r['transitions']))

    def test_catalogue_counts(self):
        r = M.run('list_catalogue')['result']
        self.assertEqual(r['counts']['transitions'], len(M.TRANSITIONS))
        self.assertEqual(r['counts']['camera_moves'], 12)


if __name__ == '__main__':
    unittest.main()
