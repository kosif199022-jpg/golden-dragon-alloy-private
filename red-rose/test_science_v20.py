import json
import math
import random
import unittest
from fractions import Fraction

import science_v20 as sci


class InterfaceTests(unittest.TestCase):
    def test_topics_and_ops(self):
        self.assertEqual(sorted(sci.TOPICS), [f'19.{i:02d}' for i in range(1, 11)])
        self.assertEqual(set(sci.TOPICS.values()), set(sci.OPS))

    def test_run_validation_and_json(self):
        out = sci.run('units', {'value': 1, 'from_unit': 'in', 'to_unit': 'mm'})
        self.assertEqual(set(out), {'op', 'result', 'assumptions', 'limits'})
        json.dumps(out, allow_nan=False)
        with self.assertRaises(ValueError):
            sci.run('nope', {})
        with self.assertRaises(ValueError):
            sci.run('units', [])
        with self.assertRaises(ValueError):
            sci.run('units', {f'k{i}': 1 for i in range(25)})
        with self.assertRaises(ValueError):
            sci.run('units', {'value': 1, 'from_unit': 'm', 'to_unit': 'mm', 'bogus': 1})
        with self.assertRaises(ValueError):
            sci.run('units', {'value': True, 'from_unit': 'm', 'to_unit': 'mm'})
        with self.assertRaises(ValueError):
            sci.run('units', {'value': float('nan'), 'from_unit': 'm', 'to_unit': 'mm'})
        with self.assertRaises(ValueError):
            sci.derivative(samples=[1, 2, float('inf')], dt=1, method='central')

    def test_all_ops_json_serialisable(self):
        calls = {
            'derivative': {'samples': [0, 1, 4, 9, 16, 25, 36, 49], 'dt': 1},
            'jacobian_ik': {'lengths': [1, 1], 'target': [1, 1]},
            'intrinsics': {'fx': 500, 'fy': 500, 'cx': 320, 'cy': 240, 'points': [[0, 0, 1]]},
            'quaternion': {'action': 'slerp', 'q': [1, 0, 0, 0], 'r': [0, 0, 0, 1], 'steps': 5},
            'spectrum': {'samples': [math.sin(i) for i in range(64)], 'sample_rate': 10},
            'zbuffer': {'triangles': [[[0, 0, 5], [1, 0, 5], [0, 1, 5]]], 'width': 8, 'height': 8,
                        'return_buffers': True},
            'rng': {'seed': 1, 'distribution': 'poisson', 'n': 10, 'lam': 3},
            'ode': {'problem': 'pendulum'},
            'model_report': {'items': [{'name': 'a', 'kind': 'assumed', 'value': 1}]},
        }
        for op, params in calls.items():
            json.dumps(sci.run(op, params), allow_nan=False)


class UnitsTests(unittest.TestCase):
    def test_inch_exact(self):
        r = sci.units(value=1, from_unit='in', to_unit='mm')['result']
        self.assertEqual(Fraction(r['value']), Fraction(254, 10))
        self.assertTrue(r['exact'])
        self.assertEqual(Fraction(sci.units(value='25.4', from_unit='mm', to_unit='in')['result']['value']), 1)

    def test_cycle_no_drift(self):
        cycle = ['mm', 'in', 'ft', 'km', 'cm', 'm']
        v = '1/3'
        for i in range(1000):
            v = sci.units(value=v, from_unit=cycle[i % 6], to_unit=cycle[(i + 1) % 6])['result']['value']
        # 1000 steps = 166 full cycles + 4 steps -> unit cycle[4]='cm'
        back = sci.units(value=v, from_unit='cm', to_unit='mm')['result']['value']
        self.assertEqual(Fraction(back), Fraction(1, 3))
        t = '7'
        for _ in range(500):
            t = sci.units(value=t, from_unit='s', to_unit='frames', fps='30000/1001')['result']['value']
            t = sci.units(value=t, from_unit='frames', to_unit='s', fps='30000/1001')['result']['value']
        self.assertEqual(Fraction(t), 7)

    def test_angle_float_and_mismatch(self):
        r = sci.units(value=180, from_unit='deg', to_unit='rad')['result']
        self.assertFalse(r['exact'])
        self.assertIsInstance(r['float'], float)
        self.assertAlmostEqual(r['float'], math.pi, places=15)
        out = sci.units(value=1, from_unit='deg', to_unit='rad')
        self.assertTrue(any('IEEE' in s for s in out['limits']))
        with self.assertRaises(ValueError):
            sci.units(value=1, from_unit='m', to_unit='kg')
        with self.assertRaises(ValueError):
            sci.units(value=1, from_unit='s', to_unit='frames')
        self.assertEqual(Fraction(sci.units(value=1, from_unit='lb', to_unit='g')['result']['value']),
                         Fraction('453.59237'))


class DerivativeTests(unittest.TestCase):
    def test_noisy_sine(self):
        dt = 0.01
        rnd = random.Random(42)
        ts = [i * dt for i in range(700)]
        y = [math.sin(t) + rnd.gauss(0, 0.01) for t in ts]
        sg = sci.derivative(samples=y, dt=dt, method='savgol', window=31, order=3)['result']['derivative']
        cd = sci.derivative(samples=y, dt=dt, method='central')['result']['derivative']

        def rms(d):
            sl = range(20, len(ts) - 20)
            return math.sqrt(sum((d[i] - math.cos(ts[i])) ** 2 for i in sl) / len(sl))
        self.assertLess(rms(sg), rms(cd) / 5)

    def test_quadratic_exact(self):
        dt = 0.5
        ts = [i * dt for i in range(30)]
        y = [3 * t * t - 2 * t + 1 for t in ts]
        for method in ('central', 'savgol'):
            d = sci.derivative(samples=y, dt=dt, method=method, window=7, order=2)['result']['derivative']
            for i in range(3, len(ts) - 3):
                self.assertAlmostEqual(d[i], 6 * ts[i] - 2, delta=1e-9)

    def test_bad_window(self):
        with self.assertRaises(ValueError):
            sci.derivative(samples=[1.0] * 20, dt=1, window=6)
        with self.assertRaises(ValueError):
            sci.derivative(samples=[1.0] * 20, dt=1, window=5, order=5)


class IKTests(unittest.TestCase):
    def test_reachable(self):
        r = sci.jacobian_ik(lengths=[1, 0.8, 0.6], target=[1.2, 0.9])['result']
        self.assertTrue(r['converged'])
        self.assertLess(r['error'], 1e-6)

    def test_limits(self):
        lim = [[-0.3, 0.3]] * 4
        r = sci.jacobian_ik(lengths=[1, 1, 1, 1], target=[0, 3.5], limits=lim, max_iter=300)['result']
        for a in r['angles']:
            self.assertTrue(-0.3 <= a <= 0.3)

    def test_unreachable(self):
        r = sci.jacobian_ik(lengths=[1, 1], target=[5, 0], max_iter=200)['result']
        self.assertFalse(r['converged'])
        self.assertTrue(r['outside_max_reach'])
        self.assertTrue(all(math.isfinite(v) for v in r['angles'] + [r['error']]))
        self.assertAlmostEqual(r['error'], 3.0, places=3)


class IntrinsicsTests(unittest.TestCase):
    def test_roundtrip(self):
        pts = [[0.3, -0.2, 2.5], [-1.0, 0.7, 4.0], [0.0, 0.0, 1.0]]
        p = sci.intrinsics(fx=800, fy=780, cx=320, cy=240, skew=1.5, points=pts)['result']['pixels']
        back = sci.intrinsics(fx=800, fy=780, cx=320, cy=240, skew=1.5, pixels=p,
                              depths=[q[2] for q in pts])['result']['points']
        for a, b in zip(pts, back):
            for u, v in zip(a, b):
                self.assertAlmostEqual(u, v, delta=1e-9)

    @staticmethod
    def _row_bend(pix):
        (x0, y0), (x1, y1) = pix[0], pix[-1]
        n = math.hypot(x1 - x0, y1 - y0)
        return max(abs((x1 - x0) * (y0 - y) - (x0 - x) * (y1 - y0)) / n for x, y in pix)

    def test_straight_rows(self):
        grid = [[x * 0.2, y * 0.2, 2.0] for y in range(-3, 4) for x in range(-3, 4)]
        for k1, expect_straight in ((0.0, True), (-0.3, False)):
            pix = sci.intrinsics(fx=600, fy=600, cx=320, cy=240, k1=k1, points=grid)['result']['pixels']
            worst = max(self._row_bend(pix[r * 7:(r + 1) * 7]) for r in range(7))
            if expect_straight:
                self.assertLess(worst, 1e-9)
            else:
                self.assertGreater(worst, 1.0)

    def test_distorted_roundtrip_and_validation(self):
        out = sci.intrinsics(fx=600, fy=600, cx=320, cy=240, k1=-0.1, k2=0.01, points=[[0.3, 0.2, 2]])
        back = sci.intrinsics(fx=600, fy=600, cx=320, cy=240, k1=-0.1, k2=0.01,
                              pixels=out['result']['pixels'], depths=[2])['result']['points'][0]
        self.assertAlmostEqual(back[0], 0.3, delta=1e-9)
        with self.assertRaises(ValueError):
            sci.intrinsics(fx=600, fy=600, cx=0, cy=0, points=[[0, 0, -1]])


class QuaternionTests(unittest.TestCase):
    def q(self, axis, ang):
        return sci.quaternion(action='from_axis_angle', axis=axis, angle=ang)['result']['q']

    def test_rotate_roundtrip(self):
        q = self.q([1, 2, 3], 1.1)
        v = [0.4, -2.0, 5.0]
        w = sci.quaternion(action='rotate', q=q, vector=v)['result']['vector']
        qc = sci.quaternion(action='conjugate', q=q)['result']['q']
        back = sci.quaternion(action='rotate', q=qc, vector=w)['result']['vector']
        for a, b in zip(v, back):
            self.assertAlmostEqual(a, b, delta=1e-12)
        m = sci.quaternion(action='to_matrix', q=q)['result']['matrix']
        q2 = sci.quaternion(action='from_matrix', matrix=m)['result']['q']
        self.assertLess(sci.quaternion(action='angle_between', q=q, r=q2)['result']['angle'], 1e-7)

    def test_slerp_endpoints_and_speed(self):
        a, b = self.q([0, 0, 1], 0.2), self.q([1, 1, 0], 2.0)
        r = sci.quaternion(action='slerp', q=a, r=b, steps=51)['result']
        self.assertEqual(r['path'][0], a)
        self.assertEqual(r['path'][-1], b)
        steps = r['step_angles']
        self.assertLess(max(steps) - min(steps), 1e-9)
        self.assertAlmostEqual(sum(steps), r['total_angle'], delta=1e-9)

    def test_no_flip_with_negated(self):
        a, b = self.q([0, 0, 1], 0.2), self.q([0, 1, 0], 1.0)
        neg = [-c for c in b]
        r = sci.quaternion(action='slerp', q=a, r=neg, steps=41)['result']
        self.assertTrue(r['flipped_for_shortest_path'])
        total = r['total_angle']
        self.assertLess(total, math.pi)
        self.assertLess(r['max_step_angle'], total / 40 + 1e-9)
        ref = sci.quaternion(action='slerp', q=a, r=b, steps=41)['result']['path']
        for p, s in zip(r['path'], ref):
            self.assertLess(sci.quaternion(action='angle_between', q=p, r=s)['result']['angle'], 1e-7)
        near = sci.quaternion(action='slerp', q=a, r=self.q([0, 0, 1], 0.2001), steps=5)['result']
        self.assertTrue(near['nlerp_fallback'])
        with self.assertRaises(ValueError):
            sci.quaternion(action='rotate', q=a)
        with self.assertRaises(ValueError):
            sci.quaternion(action='conjugate', q=a, vector=[1, 2, 3])


class SpectrumTests(unittest.TestCase):
    fs = 8000

    def tone(self, freqs, n=4096):
        return [sum(math.sin(2 * math.pi * f * i / self.fs) for f in freqs) for i in range(n)]

    def test_440(self):
        r = sci.spectrum(samples=self.tone([440]), sample_rate=self.fs)['result']
        self.assertLess(abs(r['peaks'][0]['frequency'] - 440), 0.5)

    def test_two_tones(self):
        r = sci.spectrum(samples=self.tone([440, 1250]), sample_rate=self.fs, peaks=2)['result']
        f = [p['frequency'] for p in r['peaks']]
        self.assertLess(abs(f[0] - 440), 0.5)
        self.assertLess(abs(f[1] - 1250), 0.5)

    def test_hann_less_leakage(self):
        x = self.tone([440])
        hann = sci.spectrum(samples=x, sample_rate=self.fs, window='hann')['result']['leakage_ratio']
        rect = sci.spectrum(samples=x, sample_rate=self.fs, window='rect')['result']['leakage_ratio']
        self.assertLess(hann * 100, rect)

    def test_limits(self):
        with self.assertRaises(ValueError):
            sci.spectrum(samples=[0.0] * 65537, sample_rate=1)
        with self.assertRaises(ValueError):
            sci.spectrum(samples=[0.0] * 16, sample_rate=1, window='blackman')


class ZBufferTests(unittest.TestCase):
    near = {'id': 1, 'vertices': [[-1, -1, 2], [1, -1, 2], [0, 1, 2]]}
    far = {'id': 2, 'vertices': [[-6, -5, 6], [6, -5, 6], [0, 5, 6]]}

    def test_occlusion_and_empty(self):
        for order in ([self.far, self.near], [self.near, self.far]):
            depth, ids, _ = sci.rasterize_depth(order, 32, 32)
            centre = 16 * 32 + 16
            self.assertEqual(ids[centre], 1)
            self.assertAlmostEqual(depth[centre], 2.0, delta=1e-9)
            self.assertEqual(depth[0], math.inf)
            self.assertEqual(ids[0], -1)
            self.assertTrue(all((d == math.inf) == (i == -1) for d, i in zip(depth, ids)))
        out = sci.zbuffer(triangles=[self.near, self.far], width=32, height=32, return_buffers=True)
        res = out['result']
        self.assertIsNone(res['depth_rows'][0][0])
        self.assertGreater(res['id_pixel_counts']['2'], 0)

    def test_depth_within_vertices(self):
        tri = {'id': 7, 'vertices': [[-1, -1, 2], [1, -1, 5], [0, 1.5, 9]]}
        depth, ids, _ = sci.rasterize_depth([tri], 48, 48)
        vals = [d for d in depth if d != math.inf]
        self.assertGreater(len(vals), 10)
        self.assertTrue(all(2 - 1e-12 <= d <= 9 + 1e-12 for d in vals))

    def test_caps(self):
        with self.assertRaises(ValueError):
            sci.zbuffer(triangles=[self.near], width=513)
        with self.assertRaises(ValueError):
            sci.zbuffer(triangles=[self.near] * 2001)


class RNGTests(unittest.TestCase):
    def test_reproducible(self):
        a = sci.rng(seed=5, distribution='uniform', n=50)['result']
        b = sci.rng(seed=5, distribution='uniform', n=50)['result']
        c = sci.rng(seed=6, distribution='uniform', n=50)['result']
        self.assertEqual(a['samples'], b['samples'])
        self.assertNotEqual(a['samples'], c['samples'])
        self.assertEqual(a['seed'], 5)
        s1 = sci.rng(seed=9, distribution='shuffle', items=list(range(20)))['result']['samples']
        self.assertEqual(sorted(s1), list(range(20)))
        ch = sci.rng(seed=9, distribution='choice', items=['a', 'b'], weights=[0, 1], n=20)['result']
        self.assertEqual(set(ch['samples']), {'b'})

    def test_chi_square(self):
        s = sci.rng(seed=2026, distribution='uniform', n=10_000)['result']['samples']
        bins = [0] * 10
        for v in s:
            bins[min(9, int(v * 10))] += 1
        chi = sum((b - 1000) ** 2 / 1000 for b in bins)
        self.assertLess(chi, 27.88)

    def test_normal_and_poisson(self):
        r = sci.rng(seed=3, distribution='normal', n=10_000, mu=2.0, sigma=0.5)['result']
        self.assertLess(abs(r['mean'] - 2.0), 0.03)
        self.assertLess(abs(r['stdev'] - 0.5), 0.03)
        p = sci.rng(seed=3, distribution='poisson', n=5000, lam=75)['result']
        self.assertLess(abs(p['mean'] - 75), 1.0)
        with self.assertRaises(ValueError):
            sci.rng(seed=1, distribution='uniform', lam=3)
        with self.assertRaises(ValueError):
            sci.rng(seed=-1, distribution='uniform')


class ODETests(unittest.TestCase):
    def test_exp_decay_and_harmonic(self):
        r = sci.ode(problem='exp_decay', method='rk45', t1=5.0, rtol=1e-9, atol=1e-12)['result']
        self.assertLess(r['max_abs_error'], 1e-8)
        h = sci.ode(problem='harmonic', method='rk45', t1=10.0, rtol=1e-9, atol=1e-12)['result']
        self.assertLess(h['max_abs_error'], 1e-6)
        h4 = sci.ode(problem='harmonic', method='rk4', t1=10.0, h=0.01)['result']
        self.assertLess(h4['max_abs_error'], 1e-8)
        p = sci.ode(problem='pendulum', t1=5.0, rtol=1e-9, atol=1e-12)['result']
        self.assertLess(abs(p['energy_drift']), 1e-6)

    def test_adaptive_fewer_steps(self):
        a = sci.ode(problem='exp_decay', method='rk45', t1=10.0, rtol=1e-10, atol=1e-13)['result']
        target = a['max_abs_error']
        steps = 10
        while True:
            r = sci.ode(problem='exp_decay', method='rk4', t1=10.0, h=10.0 / steps)['result']
            if r['max_abs_error'] <= target or steps > 100_000:
                break
            steps *= 2
        self.assertLessEqual(r['max_abs_error'], target)
        self.assertLess(a['steps'], r['steps'])

    def test_step_cap(self):
        with self.assertRaises(sci.StepLimitError) as ctx:
            sci.ode(problem='harmonic', method='rk45', t1=100.0, rtol=1e-10, atol=1e-12, max_steps=20)
        self.assertIn('step cap', str(ctx.exception))
        with self.assertRaises(ValueError):
            sci.ode(problem='exp_decay', method='rk4', h=1e-6, t1=10.0, max_steps=1000)
        with self.assertRaises(ValueError):
            sci.ode(problem='exp_decay', omega=2.0)


class ModelReportTests(unittest.TestCase):
    def test_split_and_downgrade(self):
        ode_out = sci.run('ode', {'problem': 'exp_decay'})
        items = [
            {'name': 'cable length', 'kind': 'measured', 'value': 2.31, 'unit': 'm',
             'method': 'tape measure', 'evidence': 'photo IMG_0042'},
            {'name': 'drag coeff', 'kind': 'assumed', 'value': 0.47,
             'assumptions': ['sphere in turbulent flow']},
            ode_out,
            {'name': 'peak hz', 'kind': 'measured', 'value': 440.1},
            {'name': 'sim speed', 'kind': 'measured', 'value': 3.0, 'method': 'ode',
             'evidence': 'run log'},
            {'name': 'fit', 'kind': 'measured', 'value': 1.0, 'method': 'least squares'},
        ]
        r = sci.model_report(items=items)['result']
        self.assertEqual([e['name'] for e in r['measured']], ['cable length'])
        self.assertEqual([e['name'] for e in r['assumed']], ['drag coeff', 'peak hz'])
        self.assertEqual([e['name'] for e in r['modelled']], ['ode', 'sim speed', 'fit'])
        self.assertEqual(len(r['warnings']), 3)
        self.assertTrue(any('peak hz' in w and 'downgraded' in w for w in r['warnings']))
        self.assertIn('sphere in turbulent flow', r['model_assumptions'])
        for a in ode_out['assumptions']:
            self.assertIn(a, r['model_assumptions'])
        with self.assertRaises(ValueError):
            sci.model_report(items=[{'name': 'x', 'kind': 'guess'}])


if __name__ == '__main__':
    unittest.main()
