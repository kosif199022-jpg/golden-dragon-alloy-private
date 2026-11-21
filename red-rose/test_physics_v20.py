"""Acceptance tests for physics_v20 (topics 08.01-08.10)."""
import json
import math
import unittest

import physics_v20 as P


class TestInterface(unittest.TestCase):
    def test_topics_and_ops(self):
        self.assertEqual(sorted(P.TOPICS), [f'08.{i:02d}' for i in range(1, 11)])
        self.assertEqual(set(P.TOPICS.values()), set(P.OPS))
        for fn in P.OPS.values():
            self.assertTrue(callable(fn))

    def test_run_all_defaults_json(self):
        for op in P.OPS:
            out = P.run(op, {})
            self.assertEqual(out['op'], op)
            self.assertEqual(set(out), {'op', 'result', 'assumptions', 'limits'})
            self.assertTrue(out['assumptions'] and out['limits'])
            self.assertTrue(all(isinstance(s, str) for s in out['assumptions'] + out['limits']))
            json.dumps(out, allow_nan=False)

    def test_run_rejects_bad_input(self):
        bad = [
            ('nope', {}), ('fall', []), ('fall', {'zzz': 1}),
            ('fall', {'dt': True}), ('fall', {'y0': float('nan')}), ('fall', {'g': float('inf')}),
            ('fall', {'dt': -1}), ('fall', {'duration': 1e9}), ('fall', {'integrator': 'euler'}),
            ('fall', {f'k{i}': 1 for i in range(25)}), ('collide', {'e': 1.5}),
            ('friction', {'mu_k': 0.9, 'mu_s': 0.5}), ('spring', {'k': 1e6, 'dt': 0.01}),
            ('cloth', {'cols': 31}), ('cloth', {'shear': 1}), ('motion_blur', {'shutter_deg': 400}),
            ('motion_blur', {'velocity': [1, 0], 'keyframes': [[0, 0, 0]]}),
            ('flow', {'field': 'swirl'}), ('shading', {'kd': 0.8, 'ks': 0.5}),
            ('shading', {'normal': [0, 0, 0]}), ('particles', {'count': 501}),
            ('particles', {'frames': 301}), ('particles', {'seed': 1.5}),
        ]
        for op, params in bad:
            with self.subTest(op=op, params=params):
                with self.assertRaises(ValueError):
                    P.run(op, params)

    def test_direct_call_unknown_kw(self):
        with self.assertRaises(ValueError):
            P.fall(bogus=1)


class TestFall(unittest.TestCase):
    def test_rk4_matches_analytic(self):
        r = P.fall(y0=50.0, v0=3.0, g=9.81, duration=3.0, dt=0.01, integrator='rk4')['result']
        self.assertLess(r['max_abs_error_y'], 1e-9)
        for t, y, _ in r['trajectory']:
            self.assertAlmostEqual(y, 50 + 3 * t - 0.5 * 9.81 * t * t, delta=1e-9)

    def test_euler_first_order(self):
        e1 = P.fall(duration=2.0, dt=0.01, integrator='semi_implicit_euler')['result']['final_abs_error_y']
        e2 = P.fall(duration=2.0, dt=0.005, integrator='semi_implicit_euler')['result']['final_abs_error_y']
        self.assertGreater(e1, 0)
        self.assertAlmostEqual(e1 / e2, 2.0, delta=0.1)


class TestCollide(unittest.TestCase):
    def test_momentum_and_energy(self):
        for e in (0.0, 0.3, 0.75, 1.0):
            r = P.collide(m1=2.0, v1=3.0, m2=5.0, v2=-1.5, e=e, drop_height=0)['result']['pair']
            self.assertAlmostEqual(r['momentum_before'], r['momentum_after'], delta=1e-12)
            self.assertAlmostEqual(r['kinetic_energy_before'] - r['kinetic_energy_after'],
                                   r['predicted_energy_loss'], delta=1e-12)
            self.assertAlmostEqual(r['v2_after'] - r['v1_after'], e * (3.0 + 1.5), delta=1e-12)
        r = P.collide(m1=2.0, v1=3.0, m2=5.0, v2=-1.5, e=1.0)['result']['pair']
        self.assertAlmostEqual(r['kinetic_energy_before'], r['kinetic_energy_after'], delta=1e-12)

    def test_bounce_apex_e_squared(self):
        b = P.collide(e=0.7, drop_height=2.0, max_bounces=100)['result']['bounce']
        apex = b['apex_heights']
        self.assertGreater(len(apex), 5)
        for a, c in zip(apex, apex[1:]):
            self.assertAlmostEqual(c / a, 0.49, delta=1e-12)
        self.assertTrue(b['at_rest'])
        self.assertLess(b['impacts'][-1]['t'], b['analytic_time_to_rest'])


class TestFriction(unittest.TestCase):
    def test_slide_and_stop(self):
        v0, mu_k, g = 6.0, 0.4, 9.81
        r = P.friction(v0=v0, mu_s=0.6, mu_k=mu_k, g=g, duration=3.0, dt=0.001,
                       max_samples=2001)['result']
        self.assertTrue(r['stopped'])
        self.assertAlmostEqual(r['stop_distance'], v0 * v0 / (2 * mu_k * g), delta=1e-9)
        self.assertAlmostEqual(-r['first_sliding_acceleration'], mu_k * g, delta=1e-12)
        self.assertEqual(r['direction_reversals'], 0)
        s = r['samples']
        moving = [(a, b) for a, b in zip(s, s[1:]) if b[3] > 0]
        decel = [(a[3] - b[3]) / (b[0] - a[0]) for a, b in moving]
        for d in decel:
            self.assertAlmostEqual(d, mu_k * g, delta=1e-6)
        xs = [p[1] for p in s]
        self.assertEqual(xs, sorted(xs))
        self.assertTrue(all(p[3] >= 0 for p in s))
        self.assertTrue(all(p[2] >= 0 for p in s))

    def test_static_hold(self):
        r = P.friction(v0=0.0, applied_force=2.0, mass=1.0, mu_s=0.6, mu_k=0.4)['result']
        self.assertTrue(r['static_hold'])
        self.assertEqual(r['final']['x'], 0.0)
        r2 = P.friction(v0=0.0, applied_force=10.0, mass=1.0, mu_s=0.6, mu_k=0.4, duration=1.0)['result']
        self.assertGreater(r2['final']['x'], 0.0)

    def test_drop_never_below_ground(self):
        r = P.friction(v0=2.0, y0=1.0, duration=2.0, max_samples=2001)['result']
        self.assertGreaterEqual(r['min_y'], 0.0)
        self.assertTrue(all(p[2] >= 0 for p in r['samples']))


class TestSpring(unittest.TestCase):
    def test_log_decrement(self):
        r = P.spring(m=1.0, k=100.0, c=1.0, duration=5.0, dt=0.001)['result']
        self.assertEqual(r['regime'], 'under')
        self.assertAlmostEqual(r['damping_ratio'], 0.05, delta=1e-12)
        self.assertGreaterEqual(len(r['log_decrements']), 3)
        for d in r['log_decrements']:
            self.assertLess(abs(d - r['analytic_log_decrement']) / r['analytic_log_decrement'], 0.02)

    def test_critical_no_overshoot(self):
        r = P.spring(m=1.0, k=100.0, c=20.0, x0=1.0, v0=0.0, duration=3.0)['result']
        self.assertEqual(r['regime'], 'critical')
        self.assertEqual(r['overshoot_ratio'], 0.0)
        self.assertEqual(P.spring(c=50.0)['result']['regime'], 'over')


class TestProjectile(unittest.TestCase):
    def test_drag_free_analytic(self):
        v, th, g = 25.0, 37.0, 9.81
        r = P.projectile(speed=v, angle_deg=th, g=g, drag='none', dt=0.01)['result']
        rad = math.radians(th)
        rng = v * v * math.sin(2 * rad) / g
        tf = 2 * v * math.sin(rad) / g
        self.assertTrue(r['landed'])
        self.assertLess(abs(r['range'] - rng) / rng, 1e-6)
        self.assertLess(abs(r['flight_time'] - tf) / tf, 1e-6)
        self.assertAlmostEqual(r['trajectory'][-1][2], 0.0)

    def test_quadratic_drag_terminal_and_shorter(self):
        free = P.projectile(speed=20.0, angle_deg=45.0, drag='none')['result']['range']
        dragged = P.projectile(speed=20.0, angle_deg=45.0, drag='quadratic', drag_coeff=0.05)['result']
        self.assertLess(dragged['range'], free)
        r = P.projectile(speed=10.0, angle_deg=0.0, y0=200.0, drag='quadratic',
                         drag_coeff=0.5, dt=0.005, max_time=120.0)['result']
        vt = math.sqrt(9.81 / 0.5)
        self.assertTrue(r['landed'])
        self.assertLess(abs(-r['landing_velocity'][1] - vt) / vt, 0.01)

    def test_linear_drag_terminal(self):
        r = P.projectile(speed=5.0, angle_deg=0.0, y0=300.0, drag='linear',
                         drag_coeff=2.0, dt=0.005, max_time=120.0)['result']
        vt = 9.81 / 2.0
        self.assertLess(abs(-r['landing_velocity'][1] - vt) / vt, 0.01)


class TestCloth(unittest.TestCase):
    PARAMS = dict(cols=8, rows=8, spacing=0.1, steps=90, iterations=20, wind=[0.5, 0.0, 2.0])

    def test_stretch_pins_finite(self):
        r = P.cloth(**self.PARAMS)['result']
        self.assertLessEqual(r['max_stretch_ratio'], 1.10)
        self.assertLessEqual(r['max_stretch_ratio_any_step'], 1.10)
        self.assertTrue(r['pinned_fixed'])
        self.assertTrue(all(math.isfinite(v) for p in r['positions'] for v in p))
        for i in r['pinned_indices']:
            self.assertEqual(r['positions'][i], [i * 0.1, 0.0, 0.0])
        self.assertLess(min(p[1] for p in r['positions']), -0.5)

    def test_deterministic(self):
        a = P.cloth(**self.PARAMS)
        b = P.cloth(**self.PARAMS)
        self.assertEqual(a, b)

    def test_budget(self):
        with self.assertRaises(ValueError):
            P.cloth(cols=30, rows=30, steps=2000, iterations=200)


class TestMotionBlur(unittest.TestCase):
    def test_blur_length_and_weights(self):
        vel, fps, sh = [300.0, 400.0], 24.0, 180.0
        r = P.motion_blur(velocity=vel, fps=fps, shutter_deg=sh, frames=10, samples=7)['result']
        expected = 500.0 * (sh / 360.0) / fps
        for f in r['frames']:
            self.assertAlmostEqual(f['blur_length'], expected, delta=1e-9)
            self.assertAlmostEqual(sum(s['weight'] for s in f['samples']), 1.0, delta=1e-12)
            self.assertEqual(len(f['samples']), 7)
            first, last = f['samples'][0]['position'], f['samples'][-1]['position']
            self.assertLessEqual(math.dist(first, last), expected + 1e-9)

    def test_shutter_zero_sharp(self):
        r = P.motion_blur(velocity=[100.0, 0.0], shutter_deg=0.0, frames=5, samples=16)['result']
        for f in r['frames']:
            self.assertEqual(len(f['samples']), 1)
            self.assertEqual(f['samples'][0]['weight'], 1.0)
            self.assertEqual(f['blur_length'], 0.0)
            self.assertAlmostEqual(f['samples'][0]['position'][0], 100.0 * f['time'])

    def test_keyframes(self):
        r = P.motion_blur(keyframes=[[0, 0, 0], [1, 24, 0], [2, 24, 48]], fps=24.0,
                          shutter_deg=360.0, frames=48)['result']
        self.assertAlmostEqual(r['frames'][0]['blur_length'], 1.0, delta=1e-9)
        self.assertAlmostEqual(r['frames'][30]['blur_length'], 2.0, delta=1e-9)


class TestFlow(unittest.TestCase):
    def test_divergence_free(self):
        for field in ('uniform', 'vortex', 'curl_noise'):
            for seed in (0, 7):
                r = P.flow(field=field, seed=seed, steps=5)['result']
                self.assertLess(r['max_abs_divergence'], 1e-6, (field, seed))

    def test_uniform_direction(self):
        r = P.flow(field='uniform', direction=[3.0, 4.0], strength=2.0, particles=[[0, 0]],
                   steps=100, dt=0.01)['result']
        end = r['particles'][0]['end']
        self.assertAlmostEqual(end[0], 2.0 * 0.6, delta=1e-9)
        self.assertAlmostEqual(end[1], 2.0 * 0.8, delta=1e-9)

    def test_vortex_radius(self):
        r = P.flow(field='vortex', strength=1.0, particles=[[1.0, 0.0], [0.0, 2.0]],
                   steps=1000, dt=0.01)['result']
        for p in r['particles']:
            self.assertLess(p['radius_max_rel_change'], 0.01)

    def test_curl_noise_seeded(self):
        a = P.flow(field='curl_noise', seed=3, steps=50)
        b = P.flow(field='curl_noise', seed=3, steps=50)
        c = P.flow(field='curl_noise', seed=4, steps=50)
        self.assertEqual(a, b)
        self.assertNotEqual(a['result']['particles'][0]['end'], c['result']['particles'][0]['end'])


class TestShading(unittest.TestCase):
    def test_cos_law_and_behind(self):
        base = P.shading(light_dir=[0, 0, 1], ks=0.0, kd=1.0)['result']['diffuse'][0]
        for deg in (0, 30, 60, 85):
            a = math.radians(deg)
            d = P.shading(light_dir=[math.sin(a), 0, math.cos(a)], ks=0.0, kd=1.0)['result']['diffuse'][0]
            self.assertAlmostEqual(d, base * math.cos(a), delta=1e-12)
        r = P.shading(light_dir=[0.3, 0, -1])['result']
        self.assertEqual(r['diffuse'], [0.0, 0.0, 0.0])
        self.assertEqual(r['specular'], 0.0)

    def test_highlight_max_at_half_equals_normal(self):
        a = math.radians(40)
        l = [math.sin(a), 0, math.cos(a)]
        refl = [-math.sin(a), 0, math.cos(a)]
        peak = P.shading(light_dir=l, view_dir=refl)['result']
        self.assertAlmostEqual(peak['n_dot_h'], 1.0, delta=1e-12)
        for db in (-10, -3, 3, 10):
            b = math.radians(40 + db)
            other = P.shading(light_dir=l, view_dir=[-math.sin(b), 0, math.cos(b)])['result']
            self.assertLess(other['specular'], peak['specular'])

    def test_never_exceeds_one(self):
        for s in (1, 8, 32, 256, 1024):
            for ks in (0.0, 0.3, 1.0):
                for ang in range(-80, 81, 20):
                    a = math.radians(ang)
                    r = P.shading(shininess=s, ks=ks, kd=1 - ks, albedo=[1, 1, 1],
                                  light_dir=[math.sin(a), 0, math.cos(a)],
                                  view_dir=[-math.sin(a), 0, math.cos(a)])['result']
                    self.assertTrue(all(0.0 <= v <= 1.0 for v in r['value']))
                    self.assertLessEqual(r['reflectance_budget'], 1.0 + 1e-12)


class TestParticles(unittest.TestCase):
    def test_seed_determinism(self):
        a = P.particles(seed=11, count=60, frames=40)
        b = P.particles(seed=11, count=60, frames=40)
        c = P.particles(seed=12, count=60, frames=40)
        self.assertEqual(a, b)
        self.assertNotEqual(a['result']['frames'], c['result']['frames'])

    def test_no_teleport_and_snow_falls(self):
        r = P.particles(kind='snow', count=150, frames=100, fps=24.0, wind=[0.5, 0.0, 0.0],
                        box_min=[-1, 0, -1], box_max=[1, 3, 1])['result']
        frames = r['frames']
        self.assertEqual(len(frames), 100)
        bound = r['frame_step_bound'] + 1e-5
        for f0, f1 in zip(frames, frames[1:]):
            for p, q in zip(f0, f1):
                self.assertLessEqual(math.dist(p, q), bound)
        self.assertLessEqual(r['max_frame_step'], r['frame_step_bound'] + 1e-12)
        self.assertLess(r['mean_y_end'], r['mean_y_start'])
        self.assertTrue(all(p[1] >= 0 for p in frames[-1]))

    def test_dust(self):
        r = P.particles(kind='dust', count=50, frames=50, seed=2)['result']
        self.assertTrue(all(math.isfinite(v) for f in r['frames'] for p in f for v in p))


if __name__ == '__main__':
    unittest.main()
