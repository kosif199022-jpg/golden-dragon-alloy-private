import json
import math
import random
import unittest

import geometry_v20 as g


class RegistryTests(unittest.TestCase):
    def test_topics_and_ops(self):
        self.assertEqual(sorted(g.TOPICS), [f'05.{i:02d}' for i in range(1, 11)])
        self.assertEqual(set(g.TOPICS.values()), set(g.OPS))

    def test_run_envelope_json(self):
        out = g.run('depth_of_field', {'focal_mm': 50, 'f_number': 2.8, 'focus_m': 40, 'coc_mm': 0.03})
        self.assertEqual(set(out), {'op', 'result', 'assumptions', 'limits'})
        self.assertIsNone(out['result']['far_m'])
        self.assertTrue(out['result']['far_is_infinite'])
        json.dumps(out, allow_nan=False)
        self.assertTrue(out['assumptions'] and out['limits'])

    def test_run_rejections(self):
        with self.assertRaises(ValueError):
            g.run('nope', {})
        with self.assertRaises(ValueError):
            g.run('timecode', [])
        with self.assertRaises(ValueError):
            g.run('timecode', {'bogus': 1})
        with self.assertRaises(ValueError):
            g.run('timecode', {f'k{i}': 1 for i in range(25)})
        with self.assertRaises(ValueError):
            g.run('depth_of_field', {'focal_mm': True})
        with self.assertRaises(ValueError):
            g.run('depth_of_field', {'focal_mm': float('nan')})
        with self.assertRaises(ValueError):
            g.run('depth_of_field', {'f_number': 500})

    def test_all_ops_json_via_run(self):
        cases = {
            'transform': {'steps': [{'type': 'rotate', 'angle_deg': 30}], 'points': [[1, 0]]},
            'perspective': {'points': [[0, 0, 5], [1, 1, -2]]},
            'curves': {'points': [[0, 0], [1, 2], [3, 3]], 'constant_speed_samples': 5},
            'aspect_fit': {},
            'depth_of_field': {'object_m': 10},
            'ik_two_bone': {'target': [5, 0]},
            'camera_path': {'keyframes': [{'t': 0, 'value': [0]}, {'t': 1, 'value': [1]}]},
            'homography': {'src': [[0, 0], [1, 0], [1, 1], [0, 1]],
                           'dst': [[0, 0], [2, 0], [2, 2], [0, 2]]},
            'timecode': {'seconds': 1.0},
            'lens_distortion': {'k1': -0.1},
        }
        for op, p in cases.items():
            json.dumps(g.run(op, p), allow_nan=False)


class TransformTests(unittest.TestCase):
    def test_rotate_inverse_roundtrip(self):
        r = g.transform(steps=[{'type': 'rotate', 'angle_deg': 37.5}, {'type': 'translate', 'offset': [3, -2]}])
        p = [[1.25, -7.5], [0.0, 0.0], [100.0, 3.0]]
        q = g.apply_matrix(r['matrix'], p)
        back = g.apply_matrix(r['inverse'], q)
        for a, b in zip(p, back):
            for x, y in zip(a, b):
                self.assertAlmostEqual(x, y, delta=1e-12)
        r3 = g.transform(dim=3, steps=[{'type': 'rotate', 'angle_deg': 71, 'axis': [1, 2, 3]}, {'type': 'invert'}],
                         points=[[1, 2, 3]])
        rot = g.rotation_matrix(71, [1, 2, 3])
        back = g.apply_matrix(rot, r3['points'])[0]
        for x, y in zip(back, [1, 2, 3]):
            self.assertAlmostEqual(x, y, delta=1e-12)

    def test_order_matters(self):
        a = g.transform(steps=[{'type': 'translate', 'offset': [1, 0]}, {'type': 'rotate', 'angle_deg': 90}], points=[[0, 0]])
        b = g.transform(steps=[{'type': 'rotate', 'angle_deg': 90}, {'type': 'translate', 'offset': [1, 0]}], points=[[0, 0]])
        self.assertAlmostEqual(a['points'][0][1], 1.0, delta=1e-12)
        self.assertAlmostEqual(b['points'][0][0], 1.0, delta=1e-12)
        self.assertGreater(math.dist(a['points'][0], b['points'][0]), 1.0)
        m1 = g.compose(g.translation_matrix([1, 0]), g.rotation_matrix(90))
        self.assertAlmostEqual(g.apply_matrix(m1, [[0, 0]])[0][1], 1.0, delta=1e-12)

    def test_singular_rejected(self):
        with self.assertRaises(ValueError):
            g.transform(steps=[{'type': 'scale', 'factors': [0, 1]}, {'type': 'invert'}])
        with self.assertRaises(ValueError):
            g.invert_matrix([[1, 2, 0], [2, 4, 0], [0, 0, 1]])
        r = g.transform(steps=[{'type': 'scale', 'factors': [0, 1]}])
        self.assertFalse(r['invertible'])
        self.assertIsNone(r['inverse'])

    def test_bad_steps(self):
        with self.assertRaises(ValueError):
            g.transform(steps=[{'type': 'rotate', 'angle_deg': 10, 'oops': 1}])
        with self.assertRaises(ValueError):
            g.transform(steps=[{'type': 'matrix', 'm': [[1, 0, 0], [0, 1, 0], [1, 0, 1]]}])
        with self.assertRaises(ValueError):
            g.transform(dim=3, steps=[{'type': 'rotate', 'angle_deg': 10, 'axis': [0, 0, 0]}])


class PerspectiveTests(unittest.TestCase):
    def test_axis_centre_and_behind(self):
        r = g.perspective(points=[[0, 0, 4], [0, 0, -1], [1, 0, 0]], width=1920, height=1080)
        self.assertEqual(r['projections'][0]['pixel'], [960.0, 540.0])
        self.assertFalse(r['projections'][1]['visible'])
        self.assertEqual(r['projections'][1]['reason'], 'behind_camera')
        self.assertFalse(r['projections'][2]['visible'])
        self.assertEqual(r['behind_count'], 2)

    def test_wider_fov_more_stretch(self):
        a = g.perspective(points=[[0, 0, 1]], vfov_deg=40)['edge_stretch']
        b = g.perspective(points=[[0, 0, 1]], vfov_deg=90)['edge_stretch']
        self.assertGreater(b['horizontal_edge'], a['horizontal_edge'])
        self.assertGreater(b['corner'], a['corner'])
        self.assertEqual(a['centre'], 1.0)

    def test_stretch_matches_projection(self):
        r = g.perspective(points=[[0, 0, 1]], vfov_deg=60)
        th = math.radians(r['hfov_deg'] / 2)
        eps = 1e-5
        c = [math.sin(th), 0, math.cos(th)]
        rad = [math.cos(th), 0, -math.sin(th)]
        tan = [0, 1, 0]
        pts = [[c[i] + s * d[i] for i in range(3)] for d in (rad, tan) for s in (-eps, eps)]
        pr = g.perspective(points=pts, vfov_deg=60)['projections']
        lr = math.dist(pr[0]['pixel'], pr[1]['pixel'])
        lt = math.dist(pr[2]['pixel'], pr[3]['pixel'])
        self.assertAlmostEqual(lr / lt, r['edge_stretch']['horizontal_edge'], delta=1e-4)


class CurveTests(unittest.TestCase):
    PTS = [[0, 0], [1, 2], [3, 3], [4, 1], [6, 0]]

    def test_passes_through_controls(self):
        for alpha in (0.0, 0.5):
            r = g.curves(points=self.PTS, alpha=alpha)
            s = g.curves(points=self.PTS, alpha=alpha, t_values=r['control_params'])['samples']
            for p, q in zip(s, self.PTS):
                self.assertAlmostEqual(math.dist(p['point'], q), 0.0, delta=1e-12)

    def test_c1_at_joins(self):
        r = g.curves(points=self.PTS, alpha=0.5)
        self.assertEqual(len(r['joins']), 3)
        for j in r['joins']:
            for a, b in zip(j['left_tangent'], j['right_tangent']):
                self.assertAlmostEqual(a, b, delta=1e-9)
        k = r['control_params'][2]
        h = 1e-7
        s = g.curves(points=self.PTS, t_values=[k - h, k + h])['samples']
        for a, b in zip(s[0]['tangent'], s[1]['tangent']):
            self.assertAlmostEqual(a, b, delta=1e-5)

    def test_constant_speed(self):
        r = g.curves(points=self.PTS, constant_speed_samples=25, table_size=4096)
        cs = r['constant_speed']
        cp = [p['point'] for p in cs]
        gaps = []
        for a, b in zip(cs, cs[1:]):
            # independent arc length between consecutive samples (fine chord sum)
            ts = [a['t'] + (b['t'] - a['t']) * k / 400 for k in range(401)]
            pts = [s['point'] for s in g.curves(points=self.PTS, t_values=ts)['samples']]
            gaps.append(sum(math.dist(p, q) for p, q in zip(pts, pts[1:])))
        mean = sum(gaps) / len(gaps)
        self.assertLess(max(abs(x - mean) for x in gaps) / mean, 0.01)
        self.assertAlmostEqual(math.dist(cp[0], self.PTS[0]), 0, delta=1e-12)
        self.assertAlmostEqual(math.dist(cp[-1], self.PTS[-1]), 0, delta=1e-9)

    def test_bezier(self):
        r = g.curves(kind='bezier', points=[[0, 0], [1, 2], [3, 2], [4, 0]], t_values=[0, 0.5, 1])
        s = r['samples']
        self.assertEqual(s[0]['point'], [0.0, 0.0])
        self.assertEqual(s[2]['point'], [4.0, 0.0])
        self.assertAlmostEqual(s[1]['point'][1], 1.5)
        self.assertEqual(s[0]['tangent'], [3.0, 6.0])
        with self.assertRaises(ValueError):
            g.curves(kind='bezier', points=[[0, 0], [1, 1], [2, 2]])
        with self.assertRaises(ValueError):
            g.curves(points=[[0, 0], [0, 0], [1, 1]])


class AspectFitTests(unittest.TestCase):
    def test_cover_keeps_focus(self):
        r = g.aspect_fit(1920, 1080, '9:16', 'cover', focus=[1500, 300, 400, 500])
        x, y, w, h = r['crop']
        self.assertTrue(r['focus_fully_visible'])
        self.assertTrue(x <= 1500 and 1900 <= x + w and y <= 300 and 800 <= y + h)
        self.assertTrue(0 <= x and x + w <= 1920)
        for v in r['output_size'] + [w, h]:
            self.assertIsInstance(v, int)
            self.assertEqual(v % 2, 0)
        self.assertEqual(r['output_size'], [1080, 1920])
        self.assertLess(abs(r['crop_aspect_error']), 0.01)

    def test_cover_reports_unfit_focus(self):
        r = g.aspect_fit(1920, 1080, '9:16', 'cover', focus=[100, 100, 900, 500])
        self.assertFalse(r['focus_fully_visible'])
        self.assertIn('does not fit', r['focus_note'])

    def test_contain_and_safe(self):
        r = g.aspect_fit(1920, 1080, '4:5', 'contain', output_long_edge=1350)
        ow, oh = r['output_size']
        self.assertEqual((ow % 2, oh % 2), (0, 0))
        x, y, w, h = r['content']
        self.assertEqual(w, ow)
        self.assertEqual(r['bars'], 'top/bottom')
        ts = r['title_safe']
        self.assertAlmostEqual(ts[2], ow * 0.9)
        self.assertAlmostEqual(r['action_safe'][3], oh * 0.93)
        with self.assertRaises(ValueError):
            g.aspect_fit(target='9x16')
        with self.assertRaises(ValueError):
            g.aspect_fit(focus=[1900, 0, 100, 10])


class DofTests(unittest.TestCase):
    def test_hyperfocal(self):
        r = g.depth_of_field(50, 2.8, 3, 0.03)
        self.assertLess(abs(r['hyperfocal_m'] - 29.8) / 29.8, 0.005)
        H = r['hyperfocal_m']
        r2 = g.depth_of_field(50, 2.8, H, 0.03)
        self.assertAlmostEqual(r2['near_m'], H / 2, delta=1e-9)
        self.assertTrue(math.isinf(r2['far_m']))
        self.assertTrue(r['near_m'] < 3 < r['far_m'])

    def test_blur(self):
        r = g.depth_of_field(50, 2.8, 3, 0.03, object_m=3)
        self.assertEqual(r['blur_mm'], 0.0)
        near = g.depth_of_field(50, 2.8, 3, 0.03)['near_m']
        r = g.depth_of_field(50, 2.8, 3, 0.03, object_m=near)
        self.assertAlmostEqual(r['blur_mm'], 0.03, delta=1e-9)
        with self.assertRaises(ValueError):
            g.depth_of_field(focus_m=0.01)


class IkTests(unittest.TestCase):
    def test_reachable(self):
        for side in ('left', 'right'):
            for tgt in ([1.2, 0.7], [-0.3, 1.5], [1.999999, 0.0], [0.5, -0.1]):
                r = g.ik_two_bone(1.0, 1.0, tgt, elbow=side)
                self.assertTrue(r['reachable'])
                self.assertLess(math.dist(r['end'], tgt), 1e-9)
                self.assertAlmostEqual(math.dist([0, 0], r['joint']), 1.0, delta=1e-12)
                self.assertAlmostEqual(math.dist(r['joint'], r['end']), 1.0, delta=1e-12)
                # forward kinematics from the returned angles
                t1, t2 = r['theta1_rad'], r['theta2_rad']
                fk = [math.cos(t1) + math.cos(t1 + t2), math.sin(t1) + math.sin(t1 + t2)]
                self.assertLess(math.dist(fk, tgt), 1e-9)

    def test_elbow_side(self):
        tgt = [1.0, 0.5]
        cross = lambda j: tgt[0] * j[1] - tgt[1] * j[0]
        self.assertGreater(cross(g.ik_two_bone(1, 1, tgt, elbow='left')['joint']), 0)
        self.assertLess(cross(g.ik_two_bone(1, 1, tgt, elbow='right')['joint']), 0)

    def test_unreachable_clamped(self):
        r = g.ik_two_bone(1.5, 0.75, [3, 4], root=[0, 0])
        self.assertTrue(r['clamped'])
        self.assertFalse(r['reachable'])
        self.assertAlmostEqual(math.hypot(*r['end']), 2.25, delta=1e-12)
        self.assertAlmostEqual(r['end'][0] / 2.25, 0.6, delta=1e-12)
        self.assertAlmostEqual(r['end'][1] / 2.25, 0.8, delta=1e-12)
        self.assertAlmostEqual(math.dist(r['joint'], r['end']), 0.75, delta=1e-12)
        r = g.ik_two_bone(2, 0.5, [0.5, 0])
        self.assertTrue(r['clamped'])
        self.assertAlmostEqual(r['end'][0], 1.5, delta=1e-12)


class CameraPathTests(unittest.TestCase):
    KEYS = [{'t': 0, 'value': [0, 0, 5]}, {'t': 2, 'value': [4, 1, 3]}, {'t': 3.5, 'value': [5, 5, 5]}]

    def test_endpoints_and_rest(self):
        r = g.camera_path(self.KEYS, fps=24)
        self.assertEqual(r['samples'][0]['value'], [0.0, 0.0, 5.0])
        self.assertEqual(r['samples'][-1]['value'], [5.0, 5.0, 5.0])
        self.assertEqual(r['samples'][-1]['t'], 3.5)
        self.assertEqual(r['start_velocity'], [0.0, 0.0, 0.0])
        self.assertEqual(r['end_velocity'], [0.0, 0.0, 0.0])
        s = g.camera_path(self.KEYS, fps=24, shake_amplitude=0.05, shake_seed=3)
        self.assertEqual(s['samples'][0]['value'], [0.0, 0.0, 5.0])
        self.assertEqual(s['samples'][-1]['value'], [5.0, 5.0, 5.0])

    def test_min_jerk_beats_linear(self):
        mj = g.camera_path(self.KEYS, fps=30)
        lin = g.camera_path(self.KEYS, fps=30, easing='linear')
        self.assertLess(mj['rms_jerk'], lin['rms_jerk'])
        self.assertLess(mj['max_acceleration'], lin['max_acceleration'])

    def test_seeded_shake(self):
        a = g.camera_path(self.KEYS, shake_amplitude=0.1, shake_seed=7)
        b = g.camera_path(self.KEYS, shake_amplitude=0.1, shake_seed=7)
        c = g.camera_path(self.KEYS, shake_amplitude=0.1, shake_seed=8)
        self.assertEqual(a['samples'], b['samples'])
        self.assertNotEqual(a['samples'], c['samples'])
        self.assertGreater(a['rms_jerk'], g.camera_path(self.KEYS)['rms_jerk'])

    def test_bad_keys(self):
        with self.assertRaises(ValueError):
            g.camera_path([{'t': 1, 'value': [0]}, {'t': 1, 'value': [1]}])
        with self.assertRaises(ValueError):
            g.camera_path([{'t': 0, 'value': [0]}, {'t': 1000, 'value': [1]}], fps=240)


class HomographyTests(unittest.TestCase):
    H = [[1.2, 0.1, 30.0], [-0.05, 0.9, 12.0], [0.0004, -0.0002, 1.0]]

    def _map(self, pts):
        return g.apply_homography(self.H, pts)

    def test_exact_four(self):
        src = [[0, 0], [640, 0], [640, 480], [0, 480]]
        r = g.homography(src, self._map(src))
        self.assertLess(r['max_reprojection_error'], 1e-9)
        for a, b in zip(r['H'], self.H):
            for x, y in zip(a, b):
                self.assertAlmostEqual(x, y, delta=1e-9 * max(1, abs(y)))

    def test_noisy_twelve(self):
        rng = random.Random(5)
        src = [[rng.uniform(0, 640), rng.uniform(0, 480)] for _ in range(12)]
        dst = [[x + rng.gauss(0, 0.3), y + rng.gauss(0, 0.3)] for x, y in self._map(src)]
        r = g.homography(src, dst)
        self.assertGreater(r['mean_reprojection_error'], 0)
        self.assertLess(r['mean_reprojection_error'], 1.0)
        test = [[100, 100], [500, 400], [320, 240]]
        for p, q in zip(g.apply_homography(r['H'], test), self._map(test)):
            self.assertLess(math.dist(p, q), 1.5)

    def test_degenerate(self):
        with self.assertRaises(ValueError):
            g.homography([[0, 0], [1, 1], [2, 2], [3, 3]], [[0, 0], [1, 0], [1, 1], [0, 1]])
        with self.assertRaises(ValueError):
            g.homography([[0, 0], [1, 0], [2, 0], [0, 1]], [[0, 0], [1, 0], [1, 1], [0, 1]])
        with self.assertRaises(ValueError):
            g.homography([[0, 0], [1, 0], [1, 1]], [[0, 0], [1, 0], [1, 1]])


class TimecodeTests(unittest.TestCase):
    def test_floor_ntsc(self):
        self.assertEqual(g.timecode('seconds_to_frame', '30000/1001', seconds=1.0)['frame'], 29)
        self.assertEqual(g.timecode('seconds_to_frame', '30000/1001', seconds=1.0, rounding='round')['frame'], 30)
        self.assertEqual(g.timecode('seconds_to_frame', 25, seconds=0.04)['frame'], 1)
        self.assertEqual(g.timecode('seconds_to_frame', '30000/1001', seconds='1001/30000')['frame'], 1)
        with self.assertRaises(ValueError):
            g.timecode('seconds_to_frame', 29.97, seconds=1)

    def test_drop_frame(self):
        self.assertEqual(g.timecode('tc_to_frame', '30000/1001', tc='00:01:00;02')['frame'], 1800)
        self.assertEqual(g.timecode('frame_to_tc', '30000/1001', frame=1800, drop_frame=True)['tc'], '00:01:00;02')
        self.assertEqual(g.timecode('frame_to_tc', '30000/1001', frame=17982, drop_frame=True)['tc'], '00:10:00;00')
        self.assertEqual(g.timecode('frame_to_tc', '30000/1001', frame=107892, drop_frame=True)['tc'], '01:00:00;00')
        self.assertEqual(g.timecode('frame_to_tc', '60000/1001', frame=215784, drop_frame=True)['tc'], '01:00:00;00')
        with self.assertRaises(ValueError):
            g.timecode('tc_to_frame', '30000/1001', tc='00:01:00;01')
        with self.assertRaises(ValueError):
            g.timecode('frame_to_tc', 25, frame=10, drop_frame=True)

    def test_round_trip(self):
        for fps, df in (('30000/1001', True), ('30000/1001', False), ('60000/1001', True), (25, False), ('24000/1001', False)):
            for n in list(range(0, 200001, 37)) + [200000]:
                tc = g.timecode('frame_to_tc', fps, frame=n, drop_frame=df)['tc']
                self.assertEqual(g.timecode('tc_to_frame', fps, tc=tc)['frame'], n, (fps, n, tc))

    def test_no_drift_one_hour(self):
        for n in list(range(0, 107893, 11)) + [107892]:
            s = g.timecode('frame_to_seconds', '30000/1001', frame=n)
            self.assertEqual(g.timecode('seconds_to_frame', '30000/1001', seconds=s['seconds_exact'])['frame'], n)
            self.assertEqual(g.timecode('seconds_to_frame', '30000/1001', seconds=s['seconds'])['frame'], n)
        self.assertEqual(g.timecode('frame_to_seconds', '30000/1001', frame=107892)['seconds_exact'], '8999991/2500')  # 3599.9964 s


class LensTests(unittest.TestCase):
    CO = dict(k1=-0.2, k2=0.05, k3=-0.01, p1=0.001, p2=-0.0005)

    def test_roundtrip(self):
        r = g.lens_distortion('roundtrip', grid_size=21, grid_extent=1.0, **self.CO)
        self.assertEqual(r['non_converged'], 0)
        self.assertLess(r['max_error'], 1e-6)

    def test_identity(self):
        pts = [[0.3, -0.4], [0.9, 0.9]]
        self.assertEqual(g.lens_distortion('distort', points=pts)['points'], pts)
        u = g.lens_distortion('undistort', points=pts)
        self.assertEqual(u['points'], pts)

    def test_non_convergence_reported(self):
        r = g.lens_distortion('undistort', points=[[0.9, 0.0], [0.1, 0.1]], k1=-0.5)
        self.assertFalse(r['converged'][0])
        self.assertIsNone(r['points'][0])
        self.assertTrue(r['reasons'][0])
        self.assertTrue(r['converged'][1])
        self.assertEqual(r['non_converged'], 1)


if __name__ == '__main__':
    unittest.main()
