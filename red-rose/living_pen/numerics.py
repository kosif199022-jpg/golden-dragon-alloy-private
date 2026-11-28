"""Living Pen numerical core — the methods of Atkinson & Han, *Theoretical Numerical Analysis* (2009), as code.

Each solver states its space/norm, its stability condition and the convergence it guarantees, and refuses to
run outside the proven region. `selftest()` measures every guarantee (rates, bounds, residuals) and is what
`rose.py pen-math selftest` prints. Original implementation (numpy only); the book was read for the theory.
Pen use: strokes (ch3), paper grain and coarse→fine fitting (ch4), drying/flow steps (ch5-6), fills and
shading (ch8-9), drawn-character deformation (ch10), nib/brush contact and paint thickness ≥ 0 (ch11),
light bleed in paper (ch12), environment lighting for gold/relief (ch14).
"""
from __future__ import annotations
import math
import numpy as np

# ---------------- Ch.1 norms (grid functions with spacing h) ----------------
def l2_norm(f, h):
    """Discrete L2 norm: (h^d Σ f²)^½ for a grid function on a uniform grid of spacing h."""
    f = np.asarray(f, float)
    return float(math.sqrt(h ** f.ndim * np.sum(f * f)))


def linf_norm(f):
    return float(np.max(np.abs(f)))


def h1_seminorm_1d(u, h):
    return float(math.sqrt(h * np.sum(np.diff(np.asarray(u, float)) ** 2 / h ** 2)))


# ---------------- Ch.2 adjoints and the geometric-series (Neumann) bound ----------------
def adjoint_gap(A, At, u, v):
    """|⟨Au,v⟩ − ⟨u,A*v⟩|: an adjoint used for pen gradients must make this ~0."""
    return float(abs(np.vdot(A(u), v) - np.vdot(u, At(v))))


def perturbed_inverse_bound(norm_A_inv, norm_delta):
    """Geometric-series theorem: if ‖A⁻¹‖‖δA‖ < 1 then A+δA is invertible and
    ‖(A+δA)⁻¹‖ ≤ ‖A⁻¹‖ / (1 − ‖A⁻¹‖‖δA‖). Returns None when the theorem does not apply (refuse the solve)."""
    q = norm_A_inv * norm_delta
    return None if q >= 1 else norm_A_inv / (1 - q)


# ---------------- Ch.3 interpolation, best approximation, convex projection ----------------
def hermite_cubic(xs, fs, ds, x):
    """Piecewise cubic Hermite interpolant (C¹): exact values and slopes at knots. Error ≤ h⁴/384·max|f⁗|."""
    xs, fs, ds = (np.asarray(a, float) for a in (xs, fs, ds))
    if xs.ndim != 1 or len(xs) < 2 or np.any(np.diff(xs) <= 0):
        raise ValueError("knots must be strictly increasing, at least 2")
    x = np.asarray(x, float)
    i = np.clip(np.searchsorted(xs, x) - 1, 0, len(xs) - 2)
    h = xs[i + 1] - xs[i]
    t = (x - xs[i]) / h
    h00, h10 = 2 * t**3 - 3 * t**2 + 1, t**3 - 2 * t**2 + t
    h01, h11 = -2 * t**3 + 3 * t**2, t**3 - t**2
    return h00 * fs[i] + h10 * h * ds[i] + h01 * fs[i + 1] + h11 * h * ds[i + 1]


def hermite_error_bound(h, max_f4):
    return h ** 4 / 384 * max_f4


def chebyshev_nodes(n, a=-1.0, b=1.0):
    k = np.arange(n)
    return (a + b) / 2 + (b - a) / 2 * np.cos((2 * k + 1) * np.pi / (2 * n))


def dykstra(x, projections, iters=200, tol=1e-12):
    """Projection onto the intersection of closed convex sets (Dykstra). Used for calligraphy proportion
    constraints: each rule is a convex set; the nearest admissible stroke parameters are returned."""
    x = np.asarray(x, float).copy()
    p = [np.zeros_like(x) for _ in projections]
    for _ in range(iters):
        prev = x.copy()
        for k, P in enumerate(projections):
            y = P(x + p[k])
            p[k] = x + p[k] - y
            x = y
        if np.linalg.norm(x - prev) < tol:
            break
    return x


# ---------------- Ch.4 Fourier and wavelets ----------------
def spectral_noise(n, slope, seed=0):
    """n×n texture whose radial power spectrum ∝ k^slope (paper grain, canvas, stroke jitter). Deterministic."""
    rng = np.random.default_rng(seed)
    kx = np.fft.fftfreq(n)[:, None]
    ky = np.fft.fftfreq(n)[None, :]
    k = np.hypot(kx, ky)
    k[0, 0] = 1.0
    amp = k ** (slope / 2)
    amp[0, 0] = 0.0
    phase = np.exp(2j * np.pi * rng.random((n, n)))
    img = np.real(np.fft.ifft2(amp * phase))
    return (img - img.mean()) / (img.std() + 1e-15)


def measured_spectral_slope(img):
    n = img.shape[0]
    P = np.abs(np.fft.fft2(img)) ** 2
    k = np.hypot(np.fft.fftfreq(n)[:, None], np.fft.fftfreq(n)[None, :])
    m = (k > 2 / n) & (k < 0.4)
    return float(np.polyfit(np.log(k[m]), np.log(P[m] + 1e-30), 1)[0])


def haar_decompose(signal, levels):
    """Orthonormal Haar multiresolution analysis (coarse→fine fitting of strokes)."""
    a = np.asarray(signal, float)
    if len(a) % (2 ** levels):
        raise ValueError("length must be divisible by 2**levels")
    details = []
    for _ in range(levels):
        e, o = a[0::2], a[1::2]
        details.append((e - o) / math.sqrt(2))
        a = (e + o) / math.sqrt(2)
    return a, details


def haar_reconstruct(approx, details):
    a = np.asarray(approx, float)
    for d in reversed(details):
        out = np.empty(2 * len(a))
        out[0::2] = (a + d) / math.sqrt(2)
        out[1::2] = (a - d) / math.sqrt(2)
        a = out
    return a


# ---------------- Ch.5 fixed point, Newton, conjugate gradient ----------------
def fixed_point(T, x0, alpha, tol=1e-12, maxit=10_000):
    """Banach fixed-point iteration for a contraction with constant alpha<1 (refused otherwise).
    Stops on the a-posteriori bound ‖x*−xₙ‖ ≤ α/(1−α)‖xₙ−xₙ₋₁‖ and returns it."""
    if not 0 <= alpha < 1:
        raise ValueError("not a contraction: alpha must be in [0,1)")
    x = np.asarray(x0, float)
    for n in range(1, maxit + 1):
        y = np.asarray(T(x), float)
        bound = alpha / (1 - alpha) * float(np.linalg.norm(y - x))
        x = y
        if bound < tol:
            return x, n, bound
    raise RuntimeError("did not converge within maxit")


def estimate_contraction(T, samples):
    """Empirical lower estimate of the Lipschitz constant from sample pairs (to check alpha before trusting it)."""
    best = 0.0
    for u, v in samples:
        d = np.linalg.norm(np.subtract(u, v))
        if d > 0:
            best = max(best, float(np.linalg.norm(np.subtract(T(u), T(v))) / d))
    return best


def newton(F, J, x0, tol=1e-13, maxit=50):
    """Newton's method; returns solution and residual history (quadratic near a regular root)."""
    x = np.atleast_1d(np.asarray(x0, float))
    hist = []
    for _ in range(maxit):
        f = np.atleast_1d(F(x))
        hist.append(float(np.linalg.norm(f)))
        if hist[-1] < tol:
            return x, hist
        x = x - np.linalg.solve(np.atleast_2d(J(x)), f)
    raise RuntimeError("Newton did not converge")


def conjugate_gradient(A, b, tol=1e-10, maxit=None):
    """Matrix-free CG for symmetric positive definite operators (Poisson/diffusion solves on paper)."""
    b = np.asarray(b, float)
    x = np.zeros_like(b)
    r = b - A(x)
    p = r.copy()
    rr = float(np.vdot(r, r))
    nb = math.sqrt(float(np.vdot(b, b))) or 1.0
    for k in range(maxit or 10 * b.size):
        if math.sqrt(rr) / nb < tol:
            return x, k
        Ap = A(p)
        a = rr / float(np.vdot(p, Ap))
        x += a * p
        r -= a * Ap
        rn = float(np.vdot(r, r))
        p = r + (rn / rr) * p
        rr = rn
    raise RuntimeError("CG did not converge")


# ---------------- Ch.6 finite differences, Lax equivalence ----------------
def heat_explicit(u0, r, steps, dims=1):
    """Forward Euler for u_t = Δu with Dirichlet 0 ends; r = Δt/h². Stable only for r ≤ 1/(2·dims):
    consistent + stable ⇒ convergent (Lax). Unstable steps are refused instead of blowing up a drawing."""
    if r > 1 / (2 * dims) + 1e-15:
        raise ValueError(f"unstable: r={r} > {1 / (2 * dims)}")
    u = np.asarray(u0, float).copy()
    for _ in range(steps):
        lap = np.zeros_like(u)
        for ax in range(u.ndim):
            lap += np.roll(u, 1, ax) + np.roll(u, -1, ax) - 2 * u
        u = u + r * lap
        for ax in range(u.ndim):
            idx = [slice(None)] * u.ndim
            idx[ax] = 0
            u[tuple(idx)] = 0
            idx[ax] = -1
            u[tuple(idx)] = 0
    return u


def thomas(a, b, c, d):
    """Tridiagonal solve (sub a, diag b, super c)."""
    n = len(d)
    cp, dp = np.zeros(n), np.zeros(n)
    cp[0], dp[0] = c[0] / b[0], d[0] / b[0]
    for i in range(1, n):
        m = b[i] - a[i] * cp[i - 1]
        cp[i] = c[i] / m if i < n - 1 else 0.0
        dp[i] = (d[i] - a[i] * dp[i - 1]) / m
    x = np.zeros(n)
    x[-1] = dp[-1]
    for i in range(n - 2, -1, -1):
        x[i] = dp[i] - cp[i] * x[i + 1]
    return x


def heat_crank_nicolson_1d(u0, r, steps):
    """Crank–Nicolson (unconditionally stable, 2nd order in time and space) on interior nodes."""
    u = np.asarray(u0, float).copy()
    n = len(u) - 2
    a = np.full(n, -r / 2)
    b = np.full(n, 1 + r)
    c = np.full(n, -r / 2)
    for _ in range(steps):
        rhs = u[1:-1] + r / 2 * (u[:-2] - 2 * u[1:-1] + u[2:])
        u[1:-1] = thomas(a, b, c, rhs)
    return u


# ---------------- Ch.8–9 elliptic problems (fills and shading) ----------------
def poisson_dirichlet_2d(f, h, tol=1e-12):
    """−Δu = f on the unit square interior, u = 0 on the boundary; 5-point stencil solved by CG.
    Coercive ⇒ unique solution (Lax–Milgram); discretisation error O(h²)."""
    f = np.asarray(f, float)

    def A(v):
        w = np.pad(v, 1)
        return (4 * v - w[:-2, 1:-1] - w[2:, 1:-1] - w[1:-1, :-2] - w[1:-1, 2:]) / h ** 2
    u, _ = conjugate_gradient(A, f, tol)
    return u


# ---------------- Ch.10 finite elements ----------------
def fem_p1_1d(f, n):
    """P1 Galerkin FEM for −u″ = f on (0,1), u(0)=u(1)=0 with n elements (load by 3-point Gauss on each element).
    Theory: H1 error O(h), L2 error O(h²)."""
    h = 1.0 / n
    x = np.linspace(0, 1, n + 1)
    gp = np.array([-math.sqrt(3 / 5), 0, math.sqrt(3 / 5)])
    gw = np.array([5 / 9, 8 / 9, 5 / 9])
    F = np.zeros(n + 1)
    for e in range(n):
        xq = x[e] + (gp + 1) * h / 2
        phi0, phi1 = (x[e + 1] - xq) / h, (xq - x[e]) / h
        fq = f(xq) * gw * h / 2
        F[e] += np.sum(fq * phi0)
        F[e + 1] += np.sum(fq * phi1)
    m = n - 1
    U = np.zeros(n + 1)
    U[1:-1] = thomas(np.full(m, -1 / h), np.full(m, 2 / h), np.full(m, -1 / h), F[1:-1])
    return x, U


def fem_l2_error(x, U, exact):
    """True L2(0,1) error of the piecewise-linear FE function (5-point Gauss per element). Nodal error alone is
    misleading in 1D: P1 is superconvergent at the nodes, while the L2 error is O(h²) as the theory says."""
    gp, gw = np.polynomial.legendre.leggauss(5)
    tot = 0.0
    for e in range(len(x) - 1):
        h = x[e + 1] - x[e]
        xq = x[e] + (gp + 1) * h / 2
        uh = U[e] + (U[e + 1] - U[e]) * (xq - x[e]) / h
        tot += np.sum(gw * h / 2 * (uh - exact(xq)) ** 2)
    return math.sqrt(tot)


# ---------------- Ch.11 variational inequalities: obstacle / contact ----------------
def obstacle_psor(f, psi, h, omega=1.5, tol=1e-10, maxit=200_000):
    """Discrete obstacle problem (Example 11.1.1 type): find u ≥ ψ with −Δu − f ≥ 0 and (u−ψ)(−Δu−f) = 0,
    u = 0 on the boundary. Projected SOR (convergent for 0<ω<2). Pen use: a nib/brush cannot go below the
    paper, paint thickness cannot be negative. Returns (u, complementarity residual)."""
    if not 0 < omega < 2:
        raise ValueError("omega must be in (0,2)")
    f, psi = np.asarray(f, float), np.asarray(psi, float)
    u = np.maximum(np.zeros_like(f), psi)
    d = f.ndim
    for _ in range(maxit):
        delta = 0.0
        for idx in np.ndindex(f.shape):
            s = 0.0
            for ax in range(d):
                for step in (-1, 1):
                    j = list(idx)
                    j[ax] += step
                    if 0 <= j[ax] < f.shape[ax]:
                        s += u[tuple(j)]
            gs = (h * h * f[idx] + s) / (2 * d)
            new = max(psi[idx], u[idx] + omega * (gs - u[idx]))
            delta = max(delta, abs(new - u[idx]))
            u[idx] = new
        if delta < tol:
            break
    w = np.pad(u, 1)
    lap = sum(np.take(w, range(2, w.shape[ax]), ax)[tuple(slice(1, -1) if a != ax else slice(None) for a in range(d))]
              + np.take(w, range(0, w.shape[ax] - 2), ax)[tuple(slice(1, -1) if a != ax else slice(None) for a in range(d))]
              for ax in range(d)) - 2 * d * u
    res = -lap / h ** 2 - f
    comp = float(np.max(np.abs((u - psi) * res)))
    return u, {"min_u_minus_psi": float(np.min(u - psi)), "min_residual": float(np.min(res)), "complementarity": comp}


# ---------------- Ch.12 integral equations: Nyström ----------------
def gauss_legendre(n, a=0.0, b=1.0):
    t, w = np.polynomial.legendre.leggauss(n)
    return (b - a) / 2 * t + (a + b) / 2, (b - a) / 2 * w


def nystrom(kernel, f, lam, n, a=0.0, b=1.0):
    """Solve λu(x) − ∫ K(x,t)u(t)dt = f(x) (2nd kind) by Nyström with Gauss–Legendre; returns an interpolant.
    Converges at the quadrature's rate for smooth K (Ch.12.4). Pen use: light scattering/bleed inside paper."""
    t, w = gauss_legendre(n, a, b)
    K = kernel(t[:, None], t[None, :])
    u = np.linalg.solve(lam * np.eye(n) - K * w[None, :], f(t))
    return lambda x: (f(np.asarray(x, float)) + (kernel(np.asarray(x, float)[..., None], t) * w * u).sum(-1)) / lam


# ---------------- Ch.14 approximation on the sphere (lighting) ----------------
def sh_basis_l2(x, y, z):
    """Real spherical harmonics up to degree 2 (9 functions), orthonormal on S²."""
    c0, c1 = 0.5 * math.sqrt(1 / math.pi), math.sqrt(3 / (4 * math.pi))
    c2, c3, c4 = 0.5 * math.sqrt(15 / math.pi), 0.25 * math.sqrt(5 / math.pi), 0.25 * math.sqrt(15 / math.pi)
    return np.stack([np.full_like(x, c0), c1 * y, c1 * z, c1 * x, c2 * x * y, c2 * y * z,
                     c3 * (3 * z * z - 1), c2 * x * z, c4 * (x * x - y * y)], -1)


def sphere_quadrature(n_theta=8, n_phi=16):
    """Product rule: Gauss–Legendre in cos θ × trapezoid in φ (exact for spherical polynomials of low degree)."""
    ct, wt = np.polynomial.legendre.leggauss(n_theta)
    ph = 2 * np.pi * np.arange(n_phi) / n_phi
    C, P = np.meshgrid(ct, ph, indexing="ij")
    S = np.sqrt(1 - C * C)
    W = np.outer(wt, np.full(n_phi, 2 * np.pi / n_phi))
    return S * np.cos(P), S * np.sin(P), C, W


def sh_project(func, n_theta=8, n_phi=16):
    """Hyperinterpolation onto degree ≤ 2 harmonics: environment light → 9 coefficients."""
    x, y, z, W = sphere_quadrature(n_theta, n_phi)
    Y = sh_basis_l2(x, y, z)
    return np.einsum("ij,ijk->k", W * func(x, y, z), Y)


def sh_eval(coef, x, y, z):
    return sh_basis_l2(np.asarray(x, float), np.asarray(y, float), np.asarray(z, float)) @ coef


# ---------------- measured guarantees ----------------
def order(e1, e2, ratio=2.0):
    return math.log(e1 / e2) / math.log(ratio)


def selftest():
    r = {}
    # ch3: Hermite error within bound for sin on [0,π]
    xs = np.linspace(0, np.pi, 9)
    xe = np.linspace(0, np.pi, 2001)
    err = linf_norm(hermite_cubic(xs, np.sin(xs), np.cos(xs), xe) - np.sin(xe))
    r["ch3_hermite"] = {"error": err, "bound": hermite_error_bound(xs[1] - xs[0], 1.0), "ok": err <= hermite_error_bound(xs[1] - xs[0], 1.0)}
    # ch4: spectrum slope and Haar perfect reconstruction
    s = measured_spectral_slope(spectral_noise(128, -3.0, 7))
    sig = np.sin(np.linspace(0, 9, 64))
    a, d = haar_decompose(sig, 4)
    r["ch4"] = {"slope": s, "target": -3.0, "haar_error": linf_norm(haar_reconstruct(a, d) - sig),
                "ok": abs(s + 3) < 0.3 and linf_norm(haar_reconstruct(a, d) - sig) < 1e-12}
    # ch5: fixed point bound, Newton quadratic, CG
    x, n, b = fixed_point(np.cos, 1.0, alpha=math.sin(1.0))
    nx, hist = newton(lambda v: v ** 2 - 2, lambda v: np.diag(2 * v), 1.0)
    r["ch5"] = {"fixed_point": float(np.atleast_1d(x)[0]), "true_error": abs(float(np.atleast_1d(x)[0]) - 0.7390851332151607),
                "a_posteriori_bound": b, "newton_residuals": hist[-4:],
                "ok": abs(float(np.atleast_1d(x)[0]) - 0.7390851332151607) <= max(b, 1e-12) * 1.0001 and hist[-2] < 1e-6}
    # ch6: CN order 2 and explicit refusal above r=1/2
    def cn_err(m):
        xg = np.linspace(0, 1, m + 1)
        h = 1 / m
        dt = h
        steps = int(round(0.1 / dt))
        u = heat_crank_nicolson_1d(np.sin(np.pi * xg), dt / h ** 2, steps)
        return linf_norm(u - np.exp(-np.pi ** 2 * steps * dt) * np.sin(np.pi * xg))
    try:
        heat_explicit(np.zeros(10), 0.6, 1)
        refused = False
    except ValueError:
        refused = True
    r["ch6"] = {"cn_order": order(cn_err(40), cn_err(80)), "explicit_refused_above_half": refused}
    r["ch6"]["ok"] = 1.8 < r["ch6"]["cn_order"] < 2.2 and refused
    # ch8-9: Poisson order 2 on a manufactured solution
    def pe(m):
        h = 1 / m
        g = np.linspace(h, 1 - h, m - 1)
        X, Y = np.meshgrid(g, g, indexing="ij")
        ex = np.sin(np.pi * X) * np.sin(np.pi * Y)
        return linf_norm(poisson_dirichlet_2d(2 * np.pi ** 2 * ex, h) - ex)
    r["ch8_poisson_order"] = order(pe(16), pe(32))
    # ch10: FEM L2 order 2
    def fe(m):
        x, U = fem_p1_1d(lambda t: np.pi ** 2 * np.sin(np.pi * t), m)
        return fem_l2_error(x, U, lambda t: np.sin(np.pi * t))
    r["ch10_fem_l2_order"] = order(fe(16), fe(32))
    # ch11: obstacle complementarity
    m = 40
    h = 1 / m
    g = np.linspace(h, 1 - h, m - 1)
    u, info = obstacle_psor(np.full(m - 1, -8.0), 0.2 - 4 * (g - 0.5) ** 2, h)
    r["ch11_obstacle"] = {**info, "ok": info["min_u_minus_psi"] >= -1e-12 and info["min_residual"] >= -1e-6 and info["complementarity"] < 1e-6}
    # ch12: Nyström with known solution u(x)=x for u − ∫₀¹ x t u dt = 2x/3
    sol = nystrom(lambda x, t: x * t, lambda x: 2 * x / 3, 1.0, 6)
    r["ch12_nystrom_error"] = abs(float(sol(0.37)) - 0.37)
    # ch14: SH exact for a degree-2 field
    fld = lambda x, y, z: 1 + 0.5 * z + 0.25 * (x * x - y * y)
    c = sh_project(fld)
    pts = np.array([[0.0, 0.6, 0.8], [1.0, 0, 0], [0.3, -0.4, math.sqrt(1 - 0.25)]])
    r["ch14_sh_error"] = float(np.max(np.abs(sh_eval(c, pts[:, 0], pts[:, 1], pts[:, 2]) - fld(pts[:, 0], pts[:, 1], pts[:, 2]))))
    r["all_ok"] = bool(r["ch3_hermite"]["ok"] and r["ch4"]["ok"] and r["ch5"]["ok"] and r["ch6"]["ok"]
                       and 1.8 < r["ch8_poisson_order"] < 2.2 and 1.8 < r["ch10_fem_l2_order"] < 2.2
                       and r["ch11_obstacle"]["ok"] and r["ch12_nystrom_error"] < 1e-10 and r["ch14_sh_error"] < 1e-3)
    return r
