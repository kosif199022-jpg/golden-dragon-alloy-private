import math, unittest
import numpy as np
from living_pen import numerics as n


class PenNumerics75(unittest.TestCase):
    def test_selftest_all_guarantees(self):
        r = n.selftest()
        self.assertTrue(r["all_ok"], r)
        self.assertAlmostEqual(r["ch8_poisson_order"], 2, delta=0.2)
        self.assertAlmostEqual(r["ch10_fem_l2_order"], 2, delta=0.2)

    def test_ch1_norms(self):
        h = 0.01
        x = np.arange(0, 1, h)
        self.assertAlmostEqual(n.l2_norm(np.ones_like(x), h), 1.0, places=6)
        self.assertAlmostEqual(n.h1_seminorm_1d(x, h), math.sqrt(1 - h), places=6)

    def test_ch2_adjoint_and_perturbation(self):
        A = np.array([[2.0, 1.0], [0.0, 3.0]])
        u, v = np.array([1.0, -2.0]), np.array([0.5, 4.0])
        self.assertLess(n.adjoint_gap(lambda w: A @ w, lambda w: A.T @ w, u, v), 1e-12)
        self.assertIsNone(n.perturbed_inverse_bound(2.0, 0.5))
        self.assertAlmostEqual(n.perturbed_inverse_bound(2.0, 0.25), 4.0)

    def test_ch3_hermite_exact_on_cubics_and_dykstra(self):
        xs = np.array([0.0, 0.5, 2.0])
        f, df = (lambda t: t**3 - t), (lambda t: 3 * t**2 - 1)
        t = np.linspace(0, 2, 41)
        self.assertLess(n.linf_norm(n.hermite_cubic(xs, f(xs), df(xs), t) - f(t)), 1e-12)
        with self.assertRaises(ValueError):
            n.hermite_cubic([0, 0], [0, 0], [0, 0], [0])
        box = lambda p: np.clip(p, 0, 1)
        half = lambda p: p - max(0.0, p.sum() - 1.0) / 2 * np.ones(2)
        x = n.dykstra(np.array([2.0, 2.0]), [box, half])
        self.assertTrue(np.all(x >= -1e-9) and np.all(x <= 1 + 1e-9) and x.sum() <= 1 + 1e-9)
        self.assertTrue(np.allclose(x, [0.5, 0.5], atol=1e-6))

    def test_ch4_deterministic_noise(self):
        self.assertTrue(np.array_equal(n.spectral_noise(32, -2, 3), n.spectral_noise(32, -2, 3)))
        with self.assertRaises(ValueError):
            n.haar_decompose(np.ones(10), 2)

    def test_ch5_refuses_non_contraction(self):
        with self.assertRaises(ValueError):
            n.fixed_point(lambda v: 2 * v, 1.0, alpha=1.0)
        self.assertGreater(n.estimate_contraction(lambda v: 2 * v, [(1.0, 0.0)]), 1.5)
        A = np.array([[4.0, 1.0], [1.0, 3.0]])
        x, _ = n.conjugate_gradient(lambda v: A @ v, np.array([1.0, 2.0]))
        self.assertTrue(np.allclose(A @ x, [1, 2], atol=1e-9))

    def test_ch6_stability_limits(self):
        with self.assertRaises(ValueError):
            n.heat_explicit(np.zeros((5, 5)), 0.3, 1, dims=2)
        u = n.heat_explicit(np.sin(np.pi * np.linspace(0, 1, 21)), 0.5, 50)
        self.assertLessEqual(n.linf_norm(u), 1.0)

    def test_ch11_obstacle_inactive_equals_free_solution(self):
        m, h = 20, 1 / 20
        g = np.linspace(h, 1 - h, m - 1)
        u, info = n.obstacle_psor(np.full(m - 1, 2.0), np.full(m - 1, -5.0), h)
        self.assertTrue(np.allclose(u, g * (1 - g), atol=1e-8))  # -u''=2 → x(1-x), obstacle never touched
        with self.assertRaises(ValueError):
            n.obstacle_psor(np.zeros(3), np.zeros(3), h, omega=2.0)

    def test_ch12_ch14(self):
        sol = n.nystrom(lambda x, t: x * t, lambda x: 2 * x / 3, 1.0, 4)
        self.assertAlmostEqual(float(sol(0.9)), 0.9, places=12)
        c = n.sh_project(lambda x, y, z: np.ones_like(x))
        self.assertAlmostEqual(c[0], 2 * math.sqrt(math.pi), places=10)
        self.assertTrue(np.allclose(c[1:], 0, atol=1e-12))


if __name__ == "__main__":
    unittest.main()
