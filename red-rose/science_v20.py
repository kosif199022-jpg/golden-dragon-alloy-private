"""Red Rose V20: bounded, deterministic science helpers for topics 19.01-19.10.

Pure standard library (math, cmath, fractions, decimal, random, statistics).
No file I/O, no subprocess, no network, no printing. Every op validates its
inputs strictly (ValueError on bools-as-numbers, non-finite numbers, unknown
parameter names and out-of-range values) and caps sizes and iterations.

Each op returns ``{'op', 'result', 'assumptions', 'limits'}``; Fractions and
Decimals are returned as strings and non-finite floats as None so the dict is
JSON-serialisable. These are numerical models, not measurements: the
``model_report`` op (19.10) keeps the two apart.
"""
from __future__ import annotations

import cmath
import math
import random
import statistics
from decimal import Decimal, localcontext
from fractions import Fraction

MAX_PARAMS = 24
OPS = {}

TOPICS = {
    '19.01': 'units',
    '19.02': 'derivative',
    '19.03': 'jacobian_ik',
    '19.04': 'intrinsics',
    '19.05': 'quaternion',
    '19.06': 'spectrum',
    '19.07': 'zbuffer',
    '19.08': 'rng',
    '19.09': 'ode',
    '19.10': 'model_report',
}


class StepLimitError(ValueError):
    """Raised when an ODE solve would need more steps than ``max_steps``."""


# --------------------------------------------------------------- validation
def _num(value, name, low=-1e15, high=1e15):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f'{name} must be a finite number between {low} and {high}')
    try:
        f = float(value)
    except OverflowError:
        raise ValueError(f'{name} must be a finite number between {low} and {high}') from None
    if not math.isfinite(f) or not low <= f <= high:
        raise ValueError(f'{name} must be a finite number between {low} and {high}')
    return f


def _int(value, name, low, high):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f'{name} must be an integer from {low} to {high}')
    return value


def _vec(value, name, length=None, min_len=1, max_len=100_000, low=-1e15, high=1e15):
    if not isinstance(value, (list, tuple)):
        raise ValueError(f'{name} must be a list of numbers')
    if length is not None and len(value) != length:
        raise ValueError(f'{name} must have exactly {length} numbers')
    if not min_len <= len(value) <= max_len:
        raise ValueError(f'{name} must have {min_len}..{max_len} numbers')
    return [_num(v, f'{name}[{i}]', low, high) for i, v in enumerate(value)]


def _choice(value, name, options):
    if not isinstance(value, str) or value not in options:
        raise ValueError(f'{name} must be one of: ' + ', '.join(sorted(options)))
    return value


def _jsonify(value):
    if isinstance(value, (Fraction, Decimal)):
        return str(value)
    if isinstance(value, bool) or value is None or isinstance(value, (int, str)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {str(k): _jsonify(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonify(v) for v in value]
    raise ValueError(f'internal: unserialisable value {type(value).__name__}')


def _op(name):
    """Register an op: keyword-only params, unknown/missing names -> ValueError."""
    def deco(fn):
        code = fn.__code__
        names = code.co_varnames[code.co_argcount:code.co_argcount + code.co_kwonlyargcount]
        defaults = fn.__kwdefaults__ or {}
        required = [n for n in names if n not in defaults]

        def wrapper(**params):
            unknown = sorted(set(params) - set(names))
            if unknown:
                raise ValueError('unknown parameters: ' + ', '.join(unknown))
            missing = [n for n in required if n not in params]
            if missing:
                raise ValueError('missing parameters: ' + ', '.join(missing))
            result, assumptions, limits = fn(**params)
            return {'op': name, 'result': _jsonify(result),
                    'assumptions': [str(a) for a in assumptions],
                    'limits': [str(x) for x in limits]}

        wrapper.__name__ = fn.__name__
        wrapper.__doc__ = fn.__doc__
        wrapper.__wrapped__ = fn
        wrapper.param_names = tuple(names)
        OPS[name] = wrapper
        return wrapper
    return deco


def run(op, params):
    """Validate ``op``/``params`` and call the op with keyword params."""
    if not isinstance(op, str) or op not in OPS:
        raise ValueError('unknown op: ' + str(op)[:80])
    if not isinstance(params, dict) or len(params) > MAX_PARAMS:
        raise ValueError(f'params must be a dict with at most {MAX_PARAMS} keys')
    if not all(isinstance(k, str) for k in params):
        raise ValueError('parameter names must be strings')
    return OPS[op](**params)


# ------------------------------------------------------------ 19.01 units
_UNITS = {
    'length': {'mm': Fraction(1, 1000), 'cm': Fraction(1, 100), 'm': Fraction(1),
               'km': Fraction(1000), 'in': Fraction(254, 10000), 'ft': Fraction(3048, 10000)},
    'time': {'ms': Fraction(1, 1000), 's': Fraction(1), 'min': Fraction(60),
             'h': Fraction(3600), 'frames': None},
    'mass': {'g': Fraction(1, 1000), 'kg': Fraction(1), 'lb': Fraction(45359237, 100000000)},
    'angle': {'deg': None, 'rad': None},
}
_DIM = {u: d for d, units in _UNITS.items() for u in units}
_MAX_DEN = 10 ** 60


def _exact(value, name, low=Fraction(-10 ** 15), high=Fraction(10 ** 15)):
    if isinstance(value, bool):
        raise ValueError(f'{name} must be a number, not a bool')
    if isinstance(value, Fraction):
        f = value
    elif isinstance(value, int):
        f = Fraction(value)
    elif isinstance(value, Decimal):
        if not value.is_finite():
            raise ValueError(f'{name} must be finite')
        f = Fraction(value)
    elif isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f'{name} must be finite')
        f = Fraction(value)  # exact binary value of the float
    elif isinstance(value, str):
        if not 1 <= len(value) <= 80:
            raise ValueError(f'{name} string must be 1..80 characters')
        try:
            f = Fraction(value.strip())
        except (ValueError, ZeroDivisionError):
            raise ValueError(f'{name} must be a number or exact fraction string') from None
    else:
        raise ValueError(f'{name} must be int, float, Fraction, Decimal or numeric string')
    if not low <= f <= high or f.denominator > _MAX_DEN:
        raise ValueError(f'{name} out of range (|value| <= 1e15, denominator <= 1e60)')
    return f


def _decimal_str(f):
    with localcontext() as ctx:
        ctx.prec = 34
        return str(Decimal(f.numerator) / Decimal(f.denominator))


@_op('units')
def units(*, value, from_unit, to_unit, fps=None):
    """Convert ``value`` between units of one dimension.

    Length (mm, cm, m, km, in, ft), time (ms, s, min, h, frames@fps) and mass
    (g, kg, lb) are exact rational conversions (1 in = 25.4 mm, 1 lb =
    0.45359237 kg by definition). Angle deg<->rad goes through float pi and is
    therefore NOT exact (IEEE-754 double, ~1e-16 relative error). Mismatched
    dimensions raise ValueError. ``fps`` (int, Fraction or 'num/den' string,
    0 < fps <= 1000) is required only when 'frames' is involved.
    """
    from_unit = _choice(from_unit, 'from_unit', _DIM)
    to_unit = _choice(to_unit, 'to_unit', _DIM)
    dim = _DIM[from_unit]
    if _DIM[to_unit] != dim:
        raise ValueError(f'dimension mismatch: {from_unit} is {dim}, {to_unit} is {_DIM[to_unit]}')
    v = _exact(value, 'value')
    uses_frames = 'frames' in (from_unit, to_unit)
    if fps is not None and not uses_frames:
        raise ValueError('fps only applies to frames conversions')
    assumptions = []
    limits = ['|value| <= 1e15; denominators <= 1e60']
    if dim == 'angle':
        if from_unit == to_unit:
            out, exact = v, True
        else:
            x = float(v)
            out = x * math.pi / 180.0 if from_unit == 'deg' else x * 180.0 / math.pi
            exact = False
        limits.append('deg<->rad uses float pi: IEEE-754 double, relative error ~1e-16 per conversion')
        result = {'value': repr(float(out)) if not exact else str(out), 'float': float(out),
                  'exact': exact, 'dimension': dim, 'from_unit': from_unit, 'to_unit': to_unit}
        return result, ['angles are plane angles; 1 turn = 360 deg = 2*pi rad'], limits
    table = dict(_UNITS[dim])
    if uses_frames:
        if fps is None:
            raise ValueError('fps is required for frames conversions')
        fr = _exact(fps, 'fps', Fraction(0), Fraction(1000))
        if fr <= 0:
            raise ValueError('fps must be > 0')
        table['frames'] = 1 / fr
        assumptions.append(f'constant frame rate {fr} fps; frame count is not rounded')
    factor = table[from_unit] / table[to_unit]
    out = v * factor
    if dim == 'length':
        assumptions.append('international inch: 1 in = 25.4 mm exactly')
    if dim == 'mass':
        assumptions.append('avoirdupois pound: 1 lb = 0.45359237 kg exactly')
    result = {'value': out, 'decimal': _decimal_str(out), 'float': float(out), 'exact': True,
              'factor': factor, 'dimension': dim, 'from_unit': from_unit, 'to_unit': to_unit}
    limits.append('decimal field is rounded to 34 significant digits; value field is exact')
    return result, assumptions, limits


# ------------------------------------------------------- 19.02 derivative
def _solve_fraction(a, b):
    """Gauss-Jordan on Fractions; a: n x n, b: n x m. Returns n x m."""
    n = len(a)
    m = [row[:] + brow[:] for row, brow in zip(a, b)]
    for col in range(n):
        piv = next((r for r in range(col, n) if m[r][col] != 0), None)
        if piv is None:
            raise ValueError('singular Savitzky-Golay system')
        m[col], m[piv] = m[piv], m[col]
        p = m[col][col]
        m[col] = [x / p for x in m[col]]
        for r in range(n):
            if r != col and m[r][col] != 0:
                f = m[r][col]
                m[r] = [x - f * y for x, y in zip(m[r], m[col])]
    return [row[n:] for row in m]


_SG_CACHE = {}


def _sg_weights(window, order):
    """W[s][j]: weight of sample j for the first derivative at window position s."""
    key = (window, order)
    if key in _SG_CACHE:
        return _SG_CACHE[key]
    h = window // 2
    xs = [Fraction(j - h) for j in range(window)]
    a = [[x ** k for k in range(order + 1)] for x in xs]  # window x (order+1)
    ata = [[sum(a[j][p] * a[j][q] for j in range(window)) for q in range(order + 1)]
           for p in range(order + 1)]
    at = [[a[j][p] for j in range(window)] for p in range(order + 1)]
    m = _solve_fraction(ata, at)  # (order+1) x window: polynomial coefficients
    weights = []
    for s in range(window):
        xs_ = xs[s]
        w = [sum(k * xs_ ** (k - 1) * m[k][j] for k in range(1, order + 1)) for j in range(window)]
        weights.append([float(x) for x in w])
    if len(_SG_CACHE) < 256:
        _SG_CACHE[key] = weights
    return weights


@_op('derivative')
def derivative(*, samples, dt, method='savgol', window=7, order=2):
    """First derivative of uniformly sampled data.

    'central': (y[i+1]-y[i-1])/(2 dt) inside, 2nd-order one-sided at the ends.
    'savgol': Savitzky-Golay least-squares polynomial (odd ``window`` 3..51,
    ``order`` 1..4 < window) with coefficients computed exactly in code; the
    first/last window//2 points use the same fit evaluated off-centre.
    Exact for polynomials of degree <= order (central: degree <= 2).
    """
    method = _choice(method, 'method', {'central', 'savgol'})
    y = _vec(samples, 'samples', min_len=3, max_len=100_000)
    dt = _num(dt, 'dt', 1e-12, 1e9)
    n = len(y)
    if method == 'central':
        d = [0.0] * n
        for i in range(1, n - 1):
            d[i] = (y[i + 1] - y[i - 1]) / (2 * dt)
        d[0] = (-3 * y[0] + 4 * y[1] - y[2]) / (2 * dt)
        d[-1] = (3 * y[-1] - 4 * y[-2] + y[-3]) / (2 * dt)
        gain = math.sqrt(0.5) / dt
        info = {}
    else:
        window = _int(window, 'window', 3, 51)
        if window % 2 == 0:
            raise ValueError('window must be odd')
        order = _int(order, 'order', 1, 4)
        if order >= window:
            raise ValueError('order must be smaller than window')
        if n < window:
            raise ValueError('need at least window samples')
        w = _sg_weights(window, order)
        h = window // 2
        d = [0.0] * n
        for i in range(n):
            if i < h:
                start, s = 0, i
            elif i > n - 1 - h:
                start, s = n - window, i - (n - window)
            else:
                start, s = i - h, h
            ws = w[s]
            d[i] = math.fsum(ws[j] * y[start + j] for j in range(window)) / dt
        gain = math.sqrt(math.fsum(x * x for x in w[h])) / dt
        info = {'window': window, 'order': order, 'center_coefficients': w[h]}
    result = {'method': method, 'derivative': d, 'n': n, 'dt': dt,
              'white_noise_gain': gain, **info}
    assumptions = ['samples are uniformly spaced by dt with no gaps',
                   'savgol fits a local polynomial; signal assumed smooth over the window']
    limits = ['<= 100000 samples; savgol window <= 51, order <= 4',
              'edge points use off-centre fits and are noisier than interior points',
              'smoothing biases fast features shorter than the window']
    return result, assumptions, limits


# ------------------------------------------------------ 19.03 jacobian_ik
def _fk(lengths, angles):
    x = y = phi = 0.0
    pts = [(0.0, 0.0)]
    for length, a in zip(lengths, angles):
        phi += a
        x += length * math.cos(phi)
        y += length * math.sin(phi)
        pts.append((x, y))
    return pts


@_op('jacobian_ik')
def jacobian_ik(*, lengths, target, initial=None, limits=None, damping=0.05,
                max_iter=500, tol=1e-9, max_step=0.5):
    """Planar n-link (n <= 12) inverse kinematics by damped least squares.

    Angles are relative joint angles in radians, base at the origin. Each step
    dtheta = J^T (J J^T + damping^2 I)^-1 e, scaled to norm <= ``max_step``,
    then clamped to ``limits`` ([lo, hi] per joint). ``converged`` is True only
    if the end-effector error < ``tol``. Unreachable targets end at the
    closest pose DLS finds, with converged=False.
    """
    ls = _vec(lengths, 'lengths', min_len=1, max_len=12, low=1e-9, high=1e6)
    n = len(ls)
    tx, ty = _vec(target, 'target', length=2, low=-1e7, high=1e7)
    if limits is None:
        lim = [(-math.inf, math.inf)] * n
    else:
        if not isinstance(limits, (list, tuple)) or len(limits) != n:
            raise ValueError('limits must be a list of [lo, hi] per joint')
        lim = []
        for i, pair in enumerate(limits):
            lo, hi = _vec(pair, f'limits[{i}]', length=2, low=-4 * math.pi, high=4 * math.pi)
            if lo > hi:
                raise ValueError(f'limits[{i}] must have lo <= hi')
            lim.append((lo, hi))
    if initial is None:
        th = [0.1] * n
    else:
        th = _vec(initial, 'initial', length=n, low=-4 * math.pi, high=4 * math.pi)
    th = [min(max(a, lo), hi) for a, (lo, hi) in zip(th, lim)]
    lam = _num(damping, 'damping', 1e-6, 10.0)
    max_iter = _int(max_iter, 'max_iter', 1, 10_000)
    tol = _num(tol, 'tol', 1e-15, 1.0)
    max_step = _num(max_step, 'max_step', 1e-6, math.pi)
    converged = False
    it = 0
    pts = _fk(ls, th)
    err = math.hypot(tx - pts[-1][0], ty - pts[-1][1])
    while it < max_iter:
        if err < tol:
            converged = True
            break
        it += 1
        ex, ey = pts[-1]
        e0, e1 = tx - ex, ty - ey
        jx = [-(ey - pts[i][1]) for i in range(n)]
        jy = [(ex - pts[i][0]) for i in range(n)]
        a = math.fsum(v * v for v in jx) + lam * lam
        b = math.fsum(u * v for u, v in zip(jx, jy))
        d = math.fsum(v * v for v in jy) + lam * lam
        det = a * d - b * b
        f0 = (d * e0 - b * e1) / det
        f1 = (-b * e0 + a * e1) / det
        dth = [jx[i] * f0 + jy[i] * f1 for i in range(n)]
        norm = math.sqrt(math.fsum(v * v for v in dth))
        if norm > max_step:
            dth = [v * max_step / norm for v in dth]
        th = [min(max(t + dv, lo), hi) for t, dv, (lo, hi) in zip(th, dth, lim)]
        pts = _fk(ls, th)
        err = math.hypot(tx - pts[-1][0], ty - pts[-1][1])
    if err < tol:
        converged = True
    reach = math.fsum(ls)
    result = {'angles': th, 'end_effector': list(pts[-1]), 'joints': [list(p) for p in pts],
              'error': err, 'converged': converged, 'iterations': it,
              'target_distance': math.hypot(tx, ty), 'max_reach': reach,
              'outside_max_reach': math.hypot(tx, ty) > reach}
    assumptions = ['planar serial chain, revolute joints, relative angles in radians',
                   'joint limits enforced by clamping after each step']
    limits = ['n <= 12 links, max_iter <= 10000',
              'local method: may stop in a local minimum or at a limit; no global search',
              'reachability check uses only total length (ignores inner workspace holes and limits)']
    return result, assumptions, limits


# ------------------------------------------------------- 19.04 intrinsics
def _points(value, name, dims, max_len=10_000):
    if not isinstance(value, (list, tuple)) or not 1 <= len(value) <= max_len:
        raise ValueError(f'{name} must be a list of 1..{max_len} points')
    return [_vec(p, f'{name}[{i}]', length=dims, low=-1e9, high=1e9) for i, p in enumerate(value)]


@_op('intrinsics')
def intrinsics(*, fx, fy, cx, cy, skew=0.0, k1=0.0, k2=0.0, points=None,
               pixels=None, depths=None):
    """Pinhole camera intrinsics K with optional radial distortion (k1, k2).

    Projection of camera-space points (Z > 0): x=X/Z, y=Y/Z, d=1+k1 r^2+k2 r^4,
    u = fx*x*d + skew*y*d + cx, v = fy*y*d + cy. Back-projection of pixels with
    a positive depth Z inverts K and, if k1/k2 != 0, undistorts by 50 fixed-
    point iterations (residual reported). No tangential distortion.
    """
    fx = _num(fx, 'fx', 1e-9, 1e7)
    fy = _num(fy, 'fy', 1e-9, 1e7)
    cx = _num(cx, 'cx', -1e7, 1e7)
    cy = _num(cy, 'cy', -1e7, 1e7)
    skew = _num(skew, 'skew', -1e7, 1e7)
    k1 = _num(k1, 'k1', -10.0, 10.0)
    k2 = _num(k2, 'k2', -10.0, 10.0)
    result = {'K': [[fx, skew, cx], [0.0, fy, cy], [0.0, 0.0, 1.0]]}
    if points is not None:
        proj = []
        for i, (X, Y, Z) in enumerate(_points(points, 'points', 3)):
            if Z <= 1e-12:
                raise ValueError(f'points[{i}] must have Z > 0 (in front of the camera)')
            x, y = X / Z, Y / Z
            r2 = x * x + y * y
            d = 1 + k1 * r2 + k2 * r2 * r2
            xd, yd = x * d, y * d
            proj.append([fx * xd + skew * yd + cx, fy * yd + cy])
        result['pixels'] = proj
    if pixels is not None:
        px = _points(pixels, 'pixels', 2)
        zs = _vec(depths if depths is not None else [], 'depths', length=len(px), low=1e-12, high=1e9)
        back, worst = [], 0.0
        for (u, v), Z in zip(px, zs):
            yd = (v - cy) / fy
            xd = (u - cx - skew * yd) / fx
            x, y = xd, yd
            if k1 or k2:
                for _ in range(50):
                    r2 = x * x + y * y
                    d = 1 + k1 * r2 + k2 * r2 * r2
                    if abs(d) < 1e-12:
                        raise ValueError('distortion model degenerate at this pixel')
                    x, y = xd / d, yd / d
                r2 = x * x + y * y
                d = 1 + k1 * r2 + k2 * r2 * r2
                worst = max(worst, math.hypot(x * d - xd, y * d - yd))
            back.append([x * Z, y * Z, Z])
        result['points'] = back
        result['undistort_residual'] = worst
    elif depths is not None:
        raise ValueError('depths requires pixels')
    assumptions = ['pinhole model, camera looks down +Z, pixel origin at the top-left convention of K',
                   'radial distortion polynomial 1 + k1 r^2 + k2 r^4 in normalised coordinates']
    limits = ['<= 10000 points/pixels per call', 'no tangential/thin-prism distortion',
              'undistortion is iterative (50 steps) and can fail for strong distortion far off-axis']
    return result, assumptions, limits


# ------------------------------------------------------- 19.05 quaternion
def _quat(value, name):
    q = _vec(value, name, length=4, low=-1e6, high=1e6)
    if math.sqrt(math.fsum(c * c for c in q)) < 1e-12:
        raise ValueError(f'{name} must be non-zero')
    return q


def _qmul(a, b):
    w1, x1, y1, z1 = a
    w2, x2, y2, z2 = b
    return [w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2,
            w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
            w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2,
            w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2]


def _qconj(q):
    return [q[0], -q[1], -q[2], -q[3]]


def _qnorm(q):
    n = math.sqrt(math.fsum(c * c for c in q))
    return [c / n for c in q]


def _qangle(a, b):
    """Rotation angle (radians, 0..pi) between unit quaternions a and b."""
    r = _qmul(_qconj(a), b)
    return 2 * math.atan2(math.sqrt(r[1] ** 2 + r[2] ** 2 + r[3] ** 2), abs(r[0]))


def _qrotate(q, v):
    q = _qnorm(q)
    return _qmul(_qmul(q, [0.0] + list(v)), _qconj(q))[1:]


def _qmatrix(q):
    w, x, y, z = _qnorm(q)
    return [[1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)],
            [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)],
            [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)]]


def _qfrom_matrix(m):
    tr = m[0][0] + m[1][1] + m[2][2]
    if tr > 0:
        s = math.sqrt(tr + 1.0) * 2
        q = [0.25 * s, (m[2][1] - m[1][2]) / s, (m[0][2] - m[2][0]) / s, (m[1][0] - m[0][1]) / s]
    elif m[0][0] > m[1][1] and m[0][0] > m[2][2]:
        s = math.sqrt(1.0 + m[0][0] - m[1][1] - m[2][2]) * 2
        q = [(m[2][1] - m[1][2]) / s, 0.25 * s, (m[0][1] + m[1][0]) / s, (m[0][2] + m[2][0]) / s]
    elif m[1][1] > m[2][2]:
        s = math.sqrt(1.0 + m[1][1] - m[0][0] - m[2][2]) * 2
        q = [(m[0][2] - m[2][0]) / s, (m[0][1] + m[1][0]) / s, 0.25 * s, (m[1][2] + m[2][1]) / s]
    else:
        s = math.sqrt(1.0 + m[2][2] - m[0][0] - m[1][1]) * 2
        q = [(m[1][0] - m[0][1]) / s, (m[0][2] + m[2][0]) / s, (m[1][2] + m[2][1]) / s, 0.25 * s]
    q = _qnorm(q)
    return [-c for c in q] if q[0] < 0 else q


def _slerp(q, r, t):
    q, r = _qnorm(q), _qnorm(r)
    dot = math.fsum(a * b for a, b in zip(q, r))
    flipped = dot < 0
    if flipped:
        r, dot = [-c for c in r], -dot
    if t == 0:
        return q, flipped, False
    if t == 1:
        return r, flipped, False
    if dot > 0.9995:
        return _qnorm([a + t * (b - a) for a, b in zip(q, r)]), flipped, True
    theta = math.acos(min(1.0, dot))
    s = math.sin(theta)
    wa, wb = math.sin((1 - t) * theta) / s, math.sin(t * theta) / s
    return [wa * a + wb * b for a, b in zip(q, r)], flipped, False


_QACTIONS = {'from_axis_angle', 'multiply', 'conjugate', 'normalize', 'rotate',
             'to_matrix', 'from_matrix', 'slerp', 'angle_between'}


@_op('quaternion')
def quaternion(*, action, q=None, r=None, axis=None, angle=None, vector=None,
               matrix=None, t=None, steps=None):
    """Quaternion toolkit; quaternions are [w, x, y, z].

    Actions: from_axis_angle(axis, angle rad), multiply(q, r) = q*r,
    conjugate(q), normalize(q), rotate(q, vector) (q normalised first),
    to_matrix(q), from_matrix(matrix: proper rotation, tolerance 1e-6),
    angle_between(q, r), slerp(q, r, t in [0,1] or steps 2..1000).
    SLERP takes the shortest path (negates r when dot < 0), falls back to
    normalised lerp when dot > 0.9995, and returns q / (possibly negated) r
    exactly at t = 0 / t = 1.
    """
    action = _choice(action, 'action', _QACTIONS)
    needs = {'from_axis_angle': {'axis', 'angle'}, 'multiply': {'q', 'r'}, 'conjugate': {'q'},
             'normalize': {'q'}, 'rotate': {'q', 'vector'}, 'to_matrix': {'q'},
             'from_matrix': {'matrix'}, 'angle_between': {'q', 'r'}, 'slerp': {'q', 'r'}}[action]
    given = {k for k, v in {'q': q, 'r': r, 'axis': axis, 'angle': angle, 'vector': vector,
                            'matrix': matrix, 't': t, 'steps': steps}.items() if v is not None}
    allowed = needs | ({'t', 'steps'} if action == 'slerp' else set())
    if given - allowed:
        raise ValueError(f'parameters not used by {action}: ' + ', '.join(sorted(given - allowed)))
    if needs - given:
        raise ValueError(f'{action} needs: ' + ', '.join(sorted(needs - given)))
    assumptions = ['Hamilton convention, [w, x, y, z], active rotation v -> q v q*']
    limits = ['float64 arithmetic; unit-norm drift is not corrected unless normalised']
    if action == 'from_axis_angle':
        ax = _vec(axis, 'axis', length=3, low=-1e6, high=1e6)
        n = math.sqrt(math.fsum(c * c for c in ax))
        if n < 1e-12:
            raise ValueError('axis must be non-zero')
        ang = _num(angle, 'angle', -1e4, 1e4)
        s = math.sin(ang / 2) / n
        res = {'q': [math.cos(ang / 2), ax[0] * s, ax[1] * s, ax[2] * s]}
    elif action == 'multiply':
        res = {'q': _qmul(_quat(q, 'q'), _quat(r, 'r'))}
    elif action == 'conjugate':
        res = {'q': _qconj(_quat(q, 'q'))}
    elif action == 'normalize':
        res = {'q': _qnorm(_quat(q, 'q'))}
    elif action == 'rotate':
        res = {'vector': _qrotate(_quat(q, 'q'), _vec(vector, 'vector', length=3))}
    elif action == 'to_matrix':
        res = {'matrix': _qmatrix(_quat(q, 'q'))}
    elif action == 'angle_between':
        res = {'angle': _qangle(_qnorm(_quat(q, 'q')), _qnorm(_quat(r, 'r')))}
    elif action == 'from_matrix':
        if not isinstance(matrix, (list, tuple)) or len(matrix) != 3:
            raise ValueError('matrix must be 3x3')
        m = [_vec(row, f'matrix[{i}]', length=3, low=-2.0, high=2.0) for i, row in enumerate(matrix)]
        for i in range(3):
            for j in range(3):
                dotp = math.fsum(m[i][k] * m[j][k] for k in range(3))
                if abs(dotp - (1.0 if i == j else 0.0)) > 1e-6:
                    raise ValueError('matrix must be orthonormal (tolerance 1e-6)')
        det = (m[0][0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1])
               - m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0])
               + m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0]))
        if det <= 0:
            raise ValueError('matrix must be a proper rotation (det = +1)')
        res = {'q': _qfrom_matrix(m)}
        limits.append('returned quaternion has w >= 0 (q and -q are the same rotation)')
    else:
        qa, qb = _quat(q, 'q'), _quat(r, 'r')
        if (t is None) == (steps is None):
            raise ValueError('slerp needs exactly one of t or steps')
        if t is not None:
            ts = [_num(t, 't', 0.0, 1.0)]
        else:
            k = _int(steps, 'steps', 2, 1000)
            ts = [i / (k - 1) for i in range(k)]
        out, fallback_used, flipped = [], False, False
        for tv in ts:
            qq, flipped, fb = _slerp(qa, qb, tv)
            fallback_used |= fb
            out.append(qq)
        step_angles = [_qangle(a, b) for a, b in zip(out, out[1:])]
        res = {'q': out[0]} if t is not None else {'path': out, 'step_angles': step_angles,
                                                   'max_step_angle': max(step_angles)}
        res.update({'flipped_for_shortest_path': flipped, 'nlerp_fallback': fallback_used,
                    'total_angle': _qangle(_qnorm(qa), _qnorm(qb))})
        limits.append('near-parallel inputs (dot > 0.9995) use normalised lerp: angular speed '
                      'is then only approximately constant')
    return res, assumptions, limits


# --------------------------------------------------------- 19.06 spectrum
def _fft(a):
    n = len(a)
    j = 0
    for i in range(1, n):
        bit = n >> 1
        while j & bit:
            j ^= bit
            bit >>= 1
        j |= bit
        if i < j:
            a[i], a[j] = a[j], a[i]
    size = 2
    while size <= n:
        half = size // 2
        step = n // size
        tw = [cmath.exp(-2j * math.pi * k / n) for k in range(0, n // 2, step)]
        for start in range(0, n, size):
            for k in range(half):
                u = a[start + k]
                v = a[start + k + half] * tw[k]
                a[start + k] = u + v
                a[start + k + half] = u - v
        size *= 2
    return a


@_op('spectrum')
def spectrum(*, samples, sample_rate, window='hann', peaks=1, detrend=True,
             min_relative_magnitude=0.01, return_magnitude=False):
    """Single-sided amplitude spectrum via an in-code radix-2 FFT.

    Samples (8..65536) are optionally mean-removed, windowed ('hann',
    'hamming', 'rect' over the original length) and zero-padded to the next
    power of two. Peaks are local maxima >= ``min_relative_magnitude`` x max,
    separated by >= 2 (rect) or 4 (hann/hamming) bins, refined by parabolic
    interpolation on log magnitude. ``leakage_ratio`` = power more than 6 bins
    from every reported peak / total power.
    """
    x = _vec(samples, 'samples', min_len=8, max_len=65536)
    fs = _num(sample_rate, 'sample_rate', 1e-6, 1e9)
    window = _choice(window, 'window', {'hann', 'hamming', 'rect'})
    peaks = _int(peaks, 'peaks', 1, 16)
    if not isinstance(detrend, bool) or not isinstance(return_magnitude, bool):
        raise ValueError('detrend and return_magnitude must be booleans')
    rel = _num(min_relative_magnitude, 'min_relative_magnitude', 0.0, 1.0)
    n_in = len(x)
    if detrend:
        mean = math.fsum(x) / n_in
        x = [v - mean for v in x]
    if window == 'rect':
        w = [1.0] * n_in
    else:
        a0, a1 = (0.5, 0.5) if window == 'hann' else (0.54, 0.46)
        w = [a0 - a1 * math.cos(2 * math.pi * i / (n_in - 1)) for i in range(n_in)]
    nfft = 1
    while nfft < n_in:
        nfft *= 2
    buf = [complex(v * wi) for v, wi in zip(x, w)] + [0j] * (nfft - n_in)
    spec = _fft(buf)
    half = nfft // 2
    scale = 2.0 / math.fsum(w)
    mag = [abs(spec[k]) * scale for k in range(half + 1)]
    mag[0] /= 2
    mag[half] /= 2
    top = max(mag)
    sep = 2 if window == 'rect' else 4
    cands = [k for k in range(1, half) if mag[k] > mag[k - 1] and mag[k] >= mag[k + 1]
             and top > 0 and mag[k] >= rel * top]
    cands.sort(key=lambda k: -mag[k])
    chosen = []
    for k in cands:
        if all(abs(k - c) >= sep for c in chosen):
            chosen.append(k)
        if len(chosen) == peaks:
            break
    found = []
    for k in chosen:
        la, lb, lc = (math.log(max(mag[k + d], 1e-300)) for d in (-1, 0, 1))
        den = la - 2 * lb + lc
        delta = 0.5 * (la - lc) / den if den != 0 else 0.0
        delta = max(-0.5, min(0.5, delta))
        amp = math.exp(lb - 0.25 * (la - lc) * delta)
        found.append({'frequency': (k + delta) * fs / nfft, 'bin': k, 'magnitude': amp})
    found.sort(key=lambda p: p['frequency'])
    power = [m * m for m in mag]
    total = math.fsum(power)
    guard = 6
    near = set()
    for k in chosen:
        near.update(range(max(0, k - guard), min(half, k + guard) + 1))
    leak = math.fsum(power[k] for k in range(half + 1) if k not in near) / total if total > 0 else 0.0
    result = {'peaks': found, 'fft_size': nfft, 'input_length': n_in,
              'resolution_hz': fs / nfft, 'window': window, 'leakage_ratio': leak,
              'nyquist_hz': fs / 2}
    if return_magnitude:
        result['magnitude'] = mag
    assumptions = ['uniform sampling at sample_rate; signal stationary over the record',
                   'magnitudes are amplitude estimates scaled by the window sum (coherent gain)']
    limits = ['<= 65536 samples; zero padding interpolates the spectrum but adds no resolution',
              'frequencies above Nyquist alias and cannot be detected',
              'peak interpolation bias is a small fraction of a bin; close tones (< ~2 bins) merge']
    return result, assumptions, limits


# ---------------------------------------------------------- 19.07 zbuffer
MAX_RASTER_TESTS = 4_000_000


def _triangles(value):
    if not isinstance(value, (list, tuple)) or not 1 <= len(value) <= 2000:
        raise ValueError('triangles must be a list of 1..2000 items')
    out = []
    for i, tri in enumerate(value):
        if isinstance(tri, dict):
            extra = set(tri) - {'id', 'vertices'}
            if extra:
                raise ValueError(f'triangles[{i}] has unknown keys: ' + ', '.join(sorted(map(str, extra))))
            tid = _int(tri.get('id', i), f'triangles[{i}].id', 0, 10 ** 9)
            verts = tri.get('vertices')
        else:
            tid, verts = i, tri
        if not isinstance(verts, (list, tuple)) or len(verts) != 3:
            raise ValueError(f'triangles[{i}] needs 3 vertices')
        out.append((tid, [_vec(v, f'triangles[{i}].vertices[{j}]', length=3, low=-1e6, high=1e6)
                          for j, v in enumerate(verts)]))
    return out


def rasterize_depth(triangles, width=64, height=64, focal=None, near=0.01):
    """Return (depth, ids, stats): row-major lists, empty depth = +inf, id = -1.

    Camera at origin looking down +Z, y up. Screen u = f x/z + W/2,
    v = H/2 - f y/z, pixel centres at +0.5. 1/z is interpolated with screen-
    space barycentrics (perspective-correct depth). Triangles with any vertex
    z < near are skipped (no clipping). Ties keep the earlier triangle.
    """
    tris = _triangles(triangles)
    width = _int(width, 'width', 1, 512)
    height = _int(height, 'height', 1, 512)
    f = float(width) if focal is None else _num(focal, 'focal', 1e-6, 1e7)
    near = _num(near, 'near', 1e-9, 1e6)
    depth = [math.inf] * (width * height)
    ids = [-1] * (width * height)
    prepared, skipped_near, skipped_degenerate, budget = [], 0, 0, 0
    for tid, verts in tris:
        if any(v[2] < near for v in verts):
            skipped_near += 1
            continue
        p = [(f * x / z + width / 2, height / 2 - f * y / z, 1.0 / z) for x, y, z in verts]
        area = (p[1][0] - p[0][0]) * (p[2][1] - p[0][1]) - (p[1][1] - p[0][1]) * (p[2][0] - p[0][0])
        if abs(area) < 1e-12:
            skipped_degenerate += 1
            continue
        x0 = max(0, int(math.floor(min(q[0] for q in p) - 0.5)))
        x1 = min(width - 1, int(math.ceil(max(q[0] for q in p) - 0.5)))
        y0 = max(0, int(math.floor(min(q[1] for q in p) - 0.5)))
        y1 = min(height - 1, int(math.ceil(max(q[1] for q in p) - 0.5)))
        if x1 < x0 or y1 < y0:
            continue
        budget += (x1 - x0 + 1) * (y1 - y0 + 1)
        prepared.append((tid, p, area, x0, x1, y0, y1))
    if budget > MAX_RASTER_TESTS:
        raise ValueError(f'raster work {budget} pixel tests exceeds cap {MAX_RASTER_TESTS}')
    for tid, p, area, x0, x1, y0, y1 in prepared:
        (ax, ay, az), (bx, by, bz), (cx, cy, cz) = p
        for py in range(y0, y1 + 1):
            sy = py + 0.5
            row = py * width
            for px in range(x0, x1 + 1):
                sx = px + 0.5
                w0 = ((bx - sx) * (cy - sy) - (by - sy) * (cx - sx)) / area
                w1 = ((cx - sx) * (ay - sy) - (cy - sy) * (ax - sx)) / area
                w2 = 1.0 - w0 - w1
                if w0 < 0 or w1 < 0 or w2 < 0:
                    continue
                inv = w0 * az + w1 * bz + w2 * cz
                if inv <= 0:
                    continue
                z = 1.0 / inv
                if z < depth[row + px]:
                    depth[row + px] = z
                    ids[row + px] = tid
    stats = {'skipped_near': skipped_near, 'skipped_degenerate': skipped_degenerate,
             'pixel_tests': budget, 'focal': f}
    return depth, ids, stats


@_op('zbuffer')
def zbuffer(*, triangles, width=64, height=64, focal=None, near=0.01, return_buffers=False):
    """Rasterise camera-space triangles into a depth + id buffer (<= 512x512).

    See ``rasterize_depth``. Returns coverage, depth statistics and per-id
    pixel counts; with ``return_buffers`` (only for <= 65536 pixels) also the
    rows, where an empty depth pixel (+inf) is serialised as None and id -1.
    """
    if not isinstance(return_buffers, bool):
        raise ValueError('return_buffers must be a boolean')
    depth, ids, stats = rasterize_depth(triangles, width, height, focal, near)
    covered = [d for d in depth if d != math.inf]
    counts = {}
    for i in ids:
        if i >= 0:
            counts[i] = counts.get(i, 0) + 1
    result = {'width': width, 'height': height, 'covered_pixels': len(covered),
              'empty_pixels': len(depth) - len(covered),
              'depth_min': min(covered) if covered else None,
              'depth_max': max(covered) if covered else None,
              'depth_mean': math.fsum(covered) / len(covered) if covered else None,
              'id_pixel_counts': {str(k): v for k, v in sorted(counts.items())}, **stats}
    if return_buffers:
        if width * height > 65536:
            raise ValueError('return_buffers only for width*height <= 65536')
        result['depth_rows'] = [[None if d == math.inf else d for d in depth[r * width:(r + 1) * width]]
                                for r in range(height)]
        result['id_rows'] = [ids[r * width:(r + 1) * width] for r in range(height)]
    assumptions = ['pinhole camera at origin looking down +Z, y up; focal defaults to width (px)',
                   'depth is camera-space z, perspective-correct via interpolated 1/z']
    limits = ['<= 2000 triangles, <= 512x512, <= 4,000,000 pixel tests',
              'no near-plane clipping: triangles crossing z=near are skipped',
              'one sample per pixel centre (no anti-aliasing); no back-face culling']
    return result, assumptions, limits


# -------------------------------------------------------------- 19.08 rng
def _poisson(rng, lam):
    total = 0
    remaining = lam
    while remaining > 0:
        chunk = min(remaining, 30.0)
        remaining -= chunk
        limit, k, p = math.exp(-chunk), 0, rng.random()
        while p > limit:
            k += 1
            p *= rng.random()
        total += k
    return total


@_op('rng')
def rng(*, seed, distribution, n=None, low=None, high=None, mu=None, sigma=None,
        lam=None, items=None, weights=None):
    """Seeded sampling with ``random.Random(seed)`` (Mersenne Twister).

    distributions: uniform(low=0, high=1), normal(mu=0, sigma=1),
    poisson(lam=1; Knuth's method in exact chunks of <= 30), choice(items,
    weights optional; with replacement), shuffle(items; returns a shuffled
    copy). n: 1..100000 (default 1; not used by shuffle). The seed is echoed.
    """
    seed = _int(seed, 'seed', 0, 2 ** 64 - 1)
    distribution = _choice(distribution, 'distribution', {'uniform', 'normal', 'poisson', 'choice', 'shuffle'})
    given = {k for k, v in {'n': n, 'low': low, 'high': high, 'mu': mu, 'sigma': sigma,
                            'lam': lam, 'items': items, 'weights': weights}.items() if v is not None}
    allowed = {'uniform': {'n', 'low', 'high'}, 'normal': {'n', 'mu', 'sigma'},
               'poisson': {'n', 'lam'}, 'choice': {'n', 'items', 'weights'},
               'shuffle': {'items'}}[distribution]
    if given - allowed:
        raise ValueError(f'parameters not used by {distribution}: ' + ', '.join(sorted(given - allowed)))
    count = 1 if n is None else _int(n, 'n', 1, 100_000)
    r = random.Random(seed)
    if distribution == 'uniform':
        lo = 0.0 if low is None else _num(low, 'low')
        hi = 1.0 if high is None else _num(high, 'high')
        if not lo < hi:
            raise ValueError('low must be < high')
        samples = [r.uniform(lo, hi) for _ in range(count)]
    elif distribution == 'normal':
        m = 0.0 if mu is None else _num(mu, 'mu')
        s = 1.0 if sigma is None else _num(sigma, 'sigma', 0.0, 1e12)
        samples = [r.normalvariate(m, s) for _ in range(count)]
    elif distribution == 'poisson':
        lv = 1.0 if lam is None else _num(lam, 'lam', 0.0, 1000.0)
        if count * max(lv, 1.0) > 5_000_000:
            raise ValueError('n * lam must be <= 5,000,000')
        samples = [_poisson(r, lv) for _ in range(count)]
    else:
        if items is None:
            raise ValueError(f'{distribution} needs items')
        if not isinstance(items, (list, tuple)) or not 1 <= len(items) <= 100_000:
            raise ValueError('items must be a list of 1..100000 scalars')
        for i, it in enumerate(items):
            if isinstance(it, str):
                if len(it) > 200:
                    raise ValueError(f'items[{i}] string longer than 200')
            elif isinstance(it, bool) or not isinstance(it, (int, float)):
                raise ValueError(f'items[{i}] must be a string or number')
            else:
                _num(it, f'items[{i}]')
        if distribution == 'shuffle':
            samples = list(items)
            r.shuffle(samples)
        else:
            ws = None
            if weights is not None:
                ws = _vec(weights, 'weights', length=len(items), low=0.0, high=1e15)
                if math.fsum(ws) <= 0:
                    raise ValueError('weights must sum to > 0')
            samples = r.choices(list(items), weights=ws, k=count)
    result = {'seed': seed, 'distribution': distribution, 'count': len(samples), 'samples': samples}
    if distribution in ('uniform', 'normal', 'poisson'):
        result['mean'] = statistics.fmean(samples)
        result['stdev'] = statistics.stdev(samples) if len(samples) > 1 else None
    assumptions = ['pseudo-random (Mersenne Twister), reproducible for the same seed and Python version',
                   'not suitable for cryptography']
    limits = ['n <= 100000; poisson n*lam <= 5e6, lam <= 1000',
              'sample statistics fluctuate around the true values (~1/sqrt(n))']
    return result, assumptions, limits


# -------------------------------------------------------------- 19.09 ode
_DP_C = [0, 1 / 5, 3 / 10, 4 / 5, 8 / 9, 1, 1]
_DP_A = [[],
         [1 / 5],
         [3 / 40, 9 / 40],
         [44 / 45, -56 / 15, 32 / 9],
         [19372 / 6561, -25360 / 2187, 64448 / 6561, -212 / 729],
         [9017 / 3168, -355 / 33, 46732 / 5247, 49 / 176, -5103 / 18656],
         [35 / 384, 0, 500 / 1113, 125 / 192, -2187 / 6784, 11 / 84]]
_DP_B5 = [35 / 384, 0, 500 / 1113, 125 / 192, -2187 / 6784, 11 / 84, 0]
_DP_B4 = [5179 / 57600, 0, 7571 / 16695, 393 / 640, -92097 / 339200, 187 / 2100, 1 / 40]


def _check_state(y):
    if not all(math.isfinite(v) and abs(v) < 1e100 for v in y):
        raise ValueError('solution diverged (non-finite or > 1e100)')


@_op('ode')
def ode(*, problem, method='rk45', t0=0.0, t1=1.0, y0=None, h=None, rtol=1e-6,
        atol=1e-9, max_steps=100_000, k=None, omega=None, g=None, length=None, damping=None):
    """Integrate a built-in ODE system forward from t0 to t1.

    problems: 'exp_decay' y' = -k y (k=1, y0=[1]); 'harmonic' x'' = -omega^2 x
    - damping x' (omega=1, damping=0, y0=[1, 0]); 'pendulum' th'' = -(g/length)
    sin th - damping th' (g=9.81, length=1, damping=0, y0=[0.5, 0]).
    methods: 'rk4' fixed step h (default (t1-t0)/100, steps = ceil((t1-t0)/h)),
    'rk45' adaptive Dormand-Prince 5(4) with RMS error norm atol + rtol*|y|.
    ``max_steps`` counts attempted steps; exceeding it raises StepLimitError.
    """
    problem = _choice(problem, 'problem', {'exp_decay', 'harmonic', 'pendulum'})
    method = _choice(method, 'method', {'rk4', 'rk45'})
    coeffs = {'k': k, 'omega': omega, 'g': g, 'length': length, 'damping': damping}
    allowed = {'exp_decay': {'k'}, 'harmonic': {'omega', 'damping'},
               'pendulum': {'g', 'length', 'damping'}}[problem]
    bad = {n for n, v in coeffs.items() if v is not None} - allowed
    if bad:
        raise ValueError(f'parameters not used by {problem}: ' + ', '.join(sorted(bad)))
    t0 = _num(t0, 't0', -1e6, 1e6)
    t1 = _num(t1, 't1', -1e6, 1e6)
    if not 0 < t1 - t0 <= 1e6:
        raise ValueError('need t0 < t1 and t1 - t0 <= 1e6 (forward integration only)')
    rtol = _num(rtol, 'rtol', 1e-13, 1.0)
    atol = _num(atol, 'atol', 1e-15, 1.0)
    max_steps = _int(max_steps, 'max_steps', 1, 200_000)
    if problem == 'exp_decay':
        kk = 1.0 if k is None else _num(k, 'k', -100.0, 1e4)
        y = _vec([1.0] if y0 is None else y0, 'y0', length=1, low=-1e9, high=1e9)
        f = lambda t, s: [-kk * s[0]]  # noqa: E731
        y_start = y[0]
        exact = lambda t: [y_start * math.exp(-kk * (t - t0))]  # noqa: E731
    elif problem == 'harmonic':
        w = 1.0 if omega is None else _num(omega, 'omega', 1e-6, 1e4)
        c = 0.0 if damping is None else _num(damping, 'damping', 0.0, 1e4)
        y = _vec([1.0, 0.0] if y0 is None else y0, 'y0', length=2, low=-1e9, high=1e9)
        f = lambda t, s: [s[1], -w * w * s[0] - c * s[1]]  # noqa: E731
        x0, v0 = y

        def exact(t):
            tt = t - t0
            return [x0 * math.cos(w * tt) + v0 / w * math.sin(w * tt),
                    -x0 * w * math.sin(w * tt) + v0 * math.cos(w * tt)]
        if c != 0:
            exact = None
    else:
        gg = 9.81 if g is None else _num(g, 'g', 0.0, 1e4)
        ll = 1.0 if length is None else _num(length, 'length', 1e-6, 1e6)
        c = 0.0 if damping is None else _num(damping, 'damping', 0.0, 1e4)
        y = _vec([0.5, 0.0] if y0 is None else y0, 'y0', length=2, low=-1e3, high=1e3)
        f = lambda t, s: [s[1], -(gg / ll) * math.sin(s[0]) - c * s[1]]  # noqa: E731
        exact = None
    y_initial = list(y)
    span = t1 - t0
    hh = span / 100 if h is None else _num(h, 'h', 1e-12, 1e6)
    t, steps, rejected, nfev = t0, 0, 0, 0
    if method == 'rk4':
        nsteps = max(1, math.ceil(span / hh - 1e-9))
        if nsteps > max_steps:
            raise StepLimitError(f'step cap exceeded: rk4 needs {nsteps} steps > max_steps={max_steps}')
        hs = span / nsteps
        for i in range(nsteps):
            k1 = f(t, y)
            k2 = f(t + hs / 2, [a + hs / 2 * b for a, b in zip(y, k1)])
            k3 = f(t + hs / 2, [a + hs / 2 * b for a, b in zip(y, k2)])
            k4 = f(t + hs, [a + hs * b for a, b in zip(y, k3)])
            y = [a + hs / 6 * (p + 2 * q + 2 * r_ + s) for a, p, q, r_, s in zip(y, k1, k2, k3, k4)]
            t = t0 + (i + 1) * hs
            _check_state(y)
        steps, nfev = nsteps, 4 * nsteps
        t = t1
    else:
        attempts = 0
        while t < t1:
            if attempts >= max_steps:
                raise StepLimitError(f'step cap exceeded: max_steps={max_steps} reached at t={t:.6g} '
                                     f'before t1={t1:.6g}; loosen rtol/atol or raise max_steps')
            attempts += 1
            last = t + hh >= t1
            if last:
                hh = t1 - t
            ks = []
            for st in range(7):
                yi = [y[d] + hh * math.fsum(_DP_A[st][j] * ks[j][d] for j in range(st))
                      for d in range(len(y))]
                ks.append(f(t + _DP_C[st] * hh, yi))
                if st == 6:
                    y5 = yi
            nfev += 7
            errs = []
            for d in range(len(y)):
                e = hh * math.fsum((_DP_B5[j] - _DP_B4[j]) * ks[j][d] for j in range(7))
                sc = atol + rtol * max(abs(y[d]), abs(y5[d]))
                errs.append((e / sc) ** 2)
            err = math.sqrt(math.fsum(errs) / len(errs))
            if not math.isfinite(err):
                raise ValueError('solution diverged (non-finite error estimate)')
            if err <= 1.0:
                t = t1 if last else t + hh
                y = y5
                _check_state(y)
                steps += 1
            else:
                rejected += 1
            fac = 5.0 if err == 0 else min(5.0, max(0.2, 0.9 * err ** -0.2))
            hh *= fac
            if hh < 1e-14 * max(1.0, abs(t)):
                raise ValueError(f'step size underflow at t={t:.6g}; problem may be stiff or singular')
    result = {'problem': problem, 'method': method, 't_final': t, 'y_final': y,
              'steps': steps, 'rejected_steps': rejected, 'f_evals': nfev}
    if exact is not None:
        ya = exact(t1)
        result['analytic'] = ya
        result['max_abs_error'] = max(abs(a - b) for a, b in zip(y, ya))
    if problem == 'pendulum' and (damping is None or damping == 0):
        gg_l = (9.81 if g is None else float(g)) / (1.0 if length is None else float(length))
        energy = lambda s: 0.5 * s[1] ** 2 + gg_l * (1 - math.cos(s[0]))  # noqa: E731
        e0 = energy(y_initial)
        result['energy_drift'] = (energy(y) - e0) / e0 if e0 else energy(y)
    assumptions = ['built-in model equations with the given coefficients; SI-like units implied',
                   'rk45 tolerances control local error per step, not the global error']
    limits = ['max_steps <= 200000 attempted steps; forward integration only',
              'explicit methods: stiff problems need tiny steps and may hit the cap',
              'analytic comparison only for exp_decay and undamped harmonic']
    return result, assumptions, limits


# ----------------------------------------------------- 19.10 model_report
_KINDS = ('measured', 'modelled', 'assumed')
_LABELS = {'measured': 'مقاس', 'modelled': 'نموذج محسوب', 'assumed': 'مفترض'}


def _plain(value, name, budget, depth=0):
    budget[0] += 1
    if budget[0] > 200_000 or depth > 8:
        raise ValueError(f'{name}: input too large or too deeply nested')
    if value is None or isinstance(value, (bool, str)):
        if isinstance(value, str) and len(value) > 10_000:
            raise ValueError(f'{name}: string longer than 10000')
        return
    if isinstance(value, (int, float)):
        _num(value, name, -1e300, 1e300)
        return
    if isinstance(value, (list, tuple)):
        for i, v in enumerate(value):
            _plain(v, f'{name}[{i}]', budget, depth + 1)
        return
    if isinstance(value, dict):
        for kk, v in value.items():
            if not isinstance(kk, str):
                raise ValueError(f'{name}: keys must be strings')
            _plain(v, f'{name}.{kk}', budget, depth + 1)
        return
    raise ValueError(f'{name}: unsupported type {type(value).__name__}')


def _str_list(value, name):
    if value is None:
        return []
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, (list, tuple)) or not all(isinstance(v, str) for v in value):
        raise ValueError(f'{name} must be a list of strings')
    return [v.strip() for v in value if v.strip()]


def _nonempty(v):
    if isinstance(v, str):
        return bool(v.strip())
    if isinstance(v, (list, tuple, dict)):
        return len(v) > 0
    return v is not None


@_op('model_report')
def model_report(*, items):
    """Separate measured, modelled and assumed values; list model assumptions.

    Each item is either an op output of this module ({'op', 'result',
    'assumptions', 'limits'}, always classified 'modelled') or a dict with
    'name', 'kind' ('measured' | 'modelled' | 'assumed'), optional 'value',
    'unit', 'method', 'evidence', 'assumptions', 'limits'. A 'measured' claim
    needs a non-empty 'method' AND 'evidence'; otherwise it is downgraded
    (to 'modelled' if a method exists, else 'assumed') with a warning. A
    measured claim whose method is one of this module's ops, or that has a
    'model' key, is relabelled 'modelled': a model output is never measured.
    """
    if not isinstance(items, (list, tuple)) or not 1 <= len(items) <= 500:
        raise ValueError('items must be a list of 1..500 dicts')
    budget = [0]
    report = {k: [] for k in _KINDS}
    warnings, model_assumptions, all_limits = [], [], []
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            raise ValueError(f'items[{i}] must be a dict')
        _plain(item, f'items[{i}]', budget)
        assumptions = _str_list(item.get('assumptions'), f'items[{i}].assumptions')
        lims = _str_list(item.get('limits'), f'items[{i}].limits')
        if 'op' in item and 'result' in item:
            name = str(item.get('name') or item['op'])
            claimed = item.get('kind', 'modelled')
            kind = 'modelled'
            if claimed == 'measured':
                warnings.append(f'{name}: op output claimed as measured; kept as modelled')
            entry = {'name': name, 'value': item['result'], 'method': 'op:' + str(item['op']),
                     'evidence': None}
        else:
            name = item.get('name')
            if not isinstance(name, str) or not 1 <= len(name) <= 200:
                raise ValueError(f'items[{i}].name must be 1..200 characters')
            claimed = item.get('kind')
            if claimed not in _KINDS:
                raise ValueError(f'items[{i}].kind must be one of: ' + ', '.join(_KINDS))
            method, evidence = item.get('method'), item.get('evidence')
            kind = claimed
            if claimed == 'measured':
                if not (_nonempty(method) and _nonempty(evidence)):
                    kind = 'modelled' if _nonempty(method) else 'assumed'
                    missing = [k for k, v in (('method', method), ('evidence', evidence)) if not _nonempty(v)]
                    warnings.append(f'{name}: claimed measured without {"/".join(missing)}; '
                                    f'downgraded to {kind}')
                elif 'model' in item or (isinstance(method, str) and method.strip() in OPS):
                    kind = 'modelled'
                    warnings.append(f'{name}: value comes from a model ({method}); '
                                    'refused label measured, relabelled modelled')
            entry = {'name': name, 'value': item.get('value'), 'method': method, 'evidence': evidence}
            if 'unit' in item:
                entry['unit'] = item['unit']
        entry.update({'kind': kind, 'claimed_kind': claimed, 'label': _LABELS[kind]})
        report[kind].append(entry)
        if kind in ('modelled', 'assumed'):
            for a in assumptions:
                if a not in model_assumptions:
                    model_assumptions.append(a)
        for x in lims:
            if x not in all_limits:
                all_limits.append(x)
    result = {**report, 'model_assumptions': model_assumptions, 'limits': all_limits,
              'warnings': warnings, 'counts': {k: len(report[k]) for k in _KINDS},
              'labels': dict(_LABELS)}
    assumptions = ['classification relies on the method/evidence fields supplied; '
                   'evidence content is not verified, only its presence']
    limits = ['<= 500 items', 'cannot detect a fabricated evidence string']
    return result, assumptions, limits
