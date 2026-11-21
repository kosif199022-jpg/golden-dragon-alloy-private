"""Acceptance tests for vfx_v24 (topics 17.01-17.10)."""
import ast
import inspect
import json
import math
import unittest

import vfx_v24 as V


def _square_frames(n, vx, vy, x0=8.0, y0=12.0, size=32):
    frames = [V._soft_square(size, size, x0 + vx * k, y0 + vy * k, 3) for k in range(n)]
    truth = [[x0 + vx * k, y0 + vy * k] for k in range(n)]
    return frames, truth


class TestInterface(unittest.TestCase):
    def test_topics_and_ops(self):
        self.assertEqual(sorted(V.TOPICS), [f'17.{i:02d}' for i in range(1, 11)])
        self.assertEqual(list(V.TOPICS.values()), list(V.OPS))
        self.assertEqual(set(V.TOPIC_NAMES_AR), set(V.TOPICS))

    def test_run_all_defaults_json(self):
        for op in V.OPS:
            with self.subTest(op=op):
                out = V.run(op, {})
                self.assertEqual(out['op'], op)
                self.assertEqual(set(out), {'op', 'result', 'assumptions', 'limits'})
                self.assertTrue(out['assumptions'] and out['limits'])
                self.assertTrue(all(isinstance(s, str) for s in out['assumptions'] + out['limits']))
                self.assertTrue(any('requested_by_owner' in s for s in out['limits']))
                json.dumps(out, allow_nan=False)

    def test_footage_refused_without_owner_request(self):
        for op in V.OPS:
            with self.subTest(op=op):
                with self.assertRaises(ValueError):
                    V.run(op, {'source': 'footage'})
                params = {'source': 'footage', 'requested_by_owner': True}
                if op == 'inpaint_mask':
                    params['owner_confirms_rights'] = True
                self.assertEqual(V.run(op, params)['op'], op)

    def test_run_rejects_bad_input(self):
        bad = [
            ('nope', {}), ('neon_bloom', []), ('neon_bloom', {'zzz': 1}),
            ('neon_bloom', {f'k{i}': 1 for i in range(25)}),
            ('neon_bloom', {'sigma': True}), ('neon_bloom', {'threshold': float('nan')}),
            ('neon_bloom', {'image': [[2.0]]}), ('neon_bloom', {'image': [[0.1] * 129]}),
            ('neon_bloom', {'requested_by_owner': 1}), ('neon_bloom', {'source': 'video'}),
            ('track_point', {'frames': [[[0.1] * 8] * 8] * 3}),
            ('track_point', {'start': [5, 5]}), ('track_point', {'frames': [[[0.1] * 8] * 8]}),
            ('rain_light', {'count': 501}), ('rain_light', {'frames': 301}),
            ('rain_light', {'light_dir': [0, 0]}), ('cast_shadow', {'light_elevation_deg': 0}),
            ('cast_shadow', {'depth_queries': [[0, 0, 0.5]]}),
            ('heat_haze', {'amplitude': 9}), ('heat_haze', {'protected_boxes': [[5, 5, 5, 6]]}),
            ('snow_vortex', {'seed': 1.5}), ('snow_vortex', {'count': 501}),
            ('alpha_composite', {'fg': [[[1, 1, 1]]]}), ('alpha_composite', {'shift': [3, 0]}),
            ('parallax_layers', {'layers': [{'name': 'a', 'depth': 1, 'colour': 'red'}]}),
            ('parallax_layers', {'camera_push': 50.0}),
            ('inpaint_mask', {'image': [[0.5] * 4] * 4}),
            ('inpaint_mask', {'image': [[0.5] * 4] * 4, 'mask': [[1] * 4] * 4}),
            ('sparks', {'count': 301}), ('sparks', {'life_min': 2.0, 'life_max': 1.0}),
        ]
        for op, params in bad:
            with self.subTest(op=op, params=params):
                with self.assertRaises(ValueError):
                    V.run(op, params)

    def test_direct_call_unknown_kw(self):
        for fn in V.OPS.values():
            with self.assertRaises(ValueError):
                fn(bogus=1)

    def test_module_hygiene(self):
        tree = ast.parse(inspect.getsource(V))
        banned = {'os', 'subprocess', 'socket', 'urllib', 'http', 'shutil', 'sqlite3', 'ctypes'}
        ok = {'__future__', 'json', 'math', 'random', 'physics_v20', 'geometry_v20'}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    root = a.name.split('.')[0]
                    self.assertNotIn(root, banned)
                    self.assertIn(root, ok)
            elif isinstance(node, ast.ImportFrom):
                root = (node.module or '').split('.')[0]
                self.assertNotIn(root, banned)
                self.assertIn(root, ok)
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                self.assertNotIn(node.func.id, {'open', 'exec', 'eval', 'compile', 'print', '__import__'})


class TestTrackPoint(unittest.TestCase):
    def test_square_one_px_per_frame(self):
        frames, truth = _square_frames(12, 1.0, 0.0)
        r = V.track_point(frames=frames, start=truth[0], ground_truth=truth)['result']
        self.assertLessEqual(r['max_error'], 0.5)
        self.assertEqual(len(r['positions']), 12)

    def test_diagonal_subpixel_with_refinement(self):
        frames, truth = _square_frames(10, 1.0, 0.5)
        r = V.track_point(frames=frames, start=truth[0], ground_truth=truth)['result']
        self.assertLessEqual(r['max_error'], 0.5)
        self.assertGreater(r['lk_refined_frames'], 0)


class TestRainLight(unittest.TestCase):
    def test_angles_and_light(self):
        r = V.rain_light(wind=80.0, fall_speed=300.0, seed=3)['result']
        expected = math.degrees(math.atan2(80.0, 300.0))
        self.assertAlmostEqual(r['fall_angle_deg'], expected, places=9)
        for frame in r['frames']:
            for x0, y0, x1, y1, _, _ in frame:
                a = math.degrees(math.atan2(x0 - x1, y0 - y1))
                self.assertAlmostEqual(a, expected, delta=0.05)  # 4-decimal rounding
        self.assertLess(r['max_angle_error_deg'], 1e-9)
        self.assertGreater(r['lit_streaks'], 0)
        self.assertGreater(r['unlit_streaks'], 0)
        self.assertGreater(r['min_lit_brightness'], r['max_unlit_brightness'])

    def test_deterministic(self):
        self.assertEqual(V.rain_light(seed=7), V.rain_light(seed=7))


class TestCastShadow(unittest.TestCase):
    def test_direction_opposite_light(self):
        for az in (0.0, 45.0, 130.0, 270.0):
            r = V.cast_shadow(light_azimuth_deg=az)['result']
            self.assertAlmostEqual(r['opposite_error_deg'], 0.0, places=6)
            self.assertAlmostEqual(r['shadow_direction_deg'], (az + 180) % 360, places=6)

    def test_point_behind_occluder(self):
        r = V.cast_shadow()['result']
        g = r['ground_queries']
        self.assertTrue(g[0]['in_shadow'])
        self.assertFalse(g[1]['in_shadow'])
        d = r['depth_queries']
        self.assertTrue(d[0]['in_shadow'])      # behind the occluder
        self.assertFalse(d[1]['in_shadow'])     # no occluder in that texel
        self.assertFalse(d[2]['in_shadow'])     # in front of the occluder
        self.assertFalse(d[3]['in_shadow'])     # the receiver itself (bias stops acne)


class TestHeatHaze(unittest.TestCase):
    def test_protected_zero_and_amplitude_bound(self):
        for seed in (0, 5):
            r = V.heat_haze(amplitude=2.0, seed=seed, t=1.3,
                            protected_boxes=[[2, 2, 12, 8], [20, 24, 30, 30]])['result']
            self.assertEqual(r['max_displacement_protected'], 0.0)
            self.assertLessEqual(r['max_displacement_outside'], 2.0 + 1e-9)
            self.assertGreater(r['max_displacement_outside'], 0.0)
            for x0, y0, x1, y1 in r['protected_boxes']:
                for y in range(y0, y1):
                    for x in range(x0, x1):
                        self.assertEqual(r['dx'][y][x], 0.0)
                        self.assertEqual(r['dy'][y][x], 0.0)

    def test_protected_pixels_unchanged(self):
        img = [[(x * 7 + y * 3) % 10 / 10 for x in range(24)] for y in range(24)]
        r = V.heat_haze(image=img, protected_boxes=[[3, 3, 10, 9]], amplitude=3.0)['result']
        for y in range(3, 9):
            for x in range(3, 10):
                self.assertAlmostEqual(r['image'][y][x], img[y][x], places=6)


class TestNeonBloom(unittest.TestCase):
    def test_never_clips_and_bounded_change(self):
        img = [[0.99 if 10 <= x <= 13 else 0.5 if x > 20 else 0.1 for x in range(24)]
               for _ in range(24)]
        r = V.neon_bloom(image=img, intensity=3.0, threshold=0.6)['result']
        out, bloom = r['image'], r['bloom']
        self.assertLessEqual(max(max(row) for row in out), 1.0)
        self.assertLessEqual(r['max_output'], 1.0)
        for y in range(24):
            for x in range(24):
                self.assertGreaterEqual(out[y][x], img[y][x] - 1e-6)
                if img[y][x] < 0.6:
                    self.assertLessEqual(out[y][x] - img[y][x], bloom[y][x] + 1e-6)

    def test_rgb_and_schedule(self):
        img = [[[0.9, 0.2, 0.8] if x == 5 else [0.0, 0.0, 0.0] for x in range(12)] for _ in range(12)]
        r = V.neon_bloom(image=img, frames=48, flicker_depth=0.5)['result']
        self.assertEqual(len(r['flicker_schedule']), 48)
        self.assertTrue(all(0.5 - 1e-9 <= v <= 1 + 1e-9 for v in r['flicker_schedule']))
        self.assertLessEqual(max(c for row in r['image'] for px in row for c in px), 1.0)

    def test_refuses_footage(self):
        with self.assertRaises(ValueError):
            V.neon_bloom(source='footage')
        self.assertEqual(V.neon_bloom(source='footage', requested_by_owner=True)['op'], 'neon_bloom')


class TestSnowVortex(unittest.TestCase):
    def test_deterministic_and_bounded(self):
        a = V.run('snow_vortex', {'seed': 11, 'frames': 30})
        b = V.run('snow_vortex', {'seed': 11, 'frames': 30})
        self.assertEqual(a, b)
        c = V.run('snow_vortex', {'seed': 12, 'frames': 30})
        self.assertNotEqual(a['result']['frames'], c['result']['frames'])
        r = a['result']
        bound = r['frame_step_bound']
        self.assertLessEqual(r['max_frame_step'], bound + 1e-9)
        fr = r['frames']
        for f0, f1 in zip(fr, fr[1:]):
            for p, q in zip(f0, f1):
                self.assertLessEqual(math.dist(p, q), bound + 1e-3)

    def test_vortex_swirls(self):
        r = V.snow_vortex(wind=[0, 0], fall_speed=0.0, turbulence=0.0, circulation=8000.0)['result']
        self.assertGreater(r['mean_swirl_deg_per_particle'], 10.0)


class TestAlphaComposite(unittest.TestCase):
    def test_no_dark_halo_premultiplied_linear(self):
        r = V.alpha_composite()['result']
        self.assertGreater(r['edge_pixels'], 0)
        self.assertEqual(r['halo_pixels_premultiplied_linear'], 0)
        self.assertGreater(r['halo_pixels_naive_straight_srgb'], 0)
        self.assertGreater(r['max_darkening_naive'], 0.05)

    def test_opaque_and_clear_regions(self):
        r = V.alpha_composite(shift=[0.0, 0.0])['result']
        self.assertEqual(r['image'][15][15], [1.0, 1.0, 1.0])
        self.assertAlmostEqual(r['image'][0][0][0], 0.6, places=5)


class TestParallax(unittest.TestCase):
    def test_nearer_moves_more_and_order_stable(self):
        r = V.parallax_layers()['result']
        offs = r['max_offset_px']
        self.assertTrue(all(a < b for a, b in zip(offs, offs[1:])))
        self.assertTrue(r['order_stable'])
        self.assertEqual(r['inversions'], [])
        # offset proportional to 1/depth
        self.assertAlmostEqual(offs[0] * 100.0, offs[3] * 4.0, places=4)

    def test_order_flip_detected(self):
        layers = [{'name': 'far', 'depth': 10.0}, {'name': 'card', 'depth': 5.0, 'depth_end': 20.0}]
        r = V.parallax_layers(layers=layers)['result']
        self.assertFalse(r['order_stable'])
        self.assertTrue(r['inversions'])


class TestInpaint(unittest.TestCase):
    def test_gradient_hole_filled(self):
        r = V.inpaint_mask()['result']
        self.assertTrue(r['converged'])
        self.assertLess(r['max_error_vs_ground_truth'], 0.01)
        self.assertGreater(r['consistency_score'], 0.9)

    def test_rights_required_for_footage(self):
        with self.assertRaises(ValueError):
            V.inpaint_mask(source='footage', requested_by_owner=True)
        with self.assertRaises(ValueError):
            V.inpaint_mask(source='footage', owner_confirms_rights=True)
        r = V.inpaint_mask(source='footage', requested_by_owner=True, owner_confirms_rights=True)
        self.assertEqual(r['op'], 'inpaint_mask')


class TestSparks(unittest.TestCase):
    def test_fade_and_arcs(self):
        r = V.sparks(count=60, seed=4)['result']
        self.assertTrue(r['all_fade_monotonic'])
        self.assertTrue(r['all_reach_zero_alpha'])
        self.assertTrue(r['all_vertical_velocity_decreasing'])
        for s in r['sparks']:
            al = [x[4] for x in s['samples']]
            vy = [x[3] for x in s['samples']]
            self.assertEqual(al[-1], 0.0)
            self.assertTrue(all(b < a for a, b in zip(al, al[1:])))
            self.assertTrue(all(b < a for a, b in zip(vy, vy[1:])))

    def test_deterministic_no_drag(self):
        self.assertEqual(V.sparks(seed=2, drag=0.0), V.sparks(seed=2, drag=0.0))
        r = V.sparks(seed=2, drag=0.0)['result']
        self.assertTrue(r['all_vertical_velocity_decreasing'])


if __name__ == '__main__':
    unittest.main()
