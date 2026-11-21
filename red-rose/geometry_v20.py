"""Red Rose V20: deterministic scene-geometry toolkit (topics 05.01-05.10).

Pure standard-library Python. Every op validates its inputs strictly (no bools
as numbers, no NaN/inf, no unknown parameters, bounded sizes) and raises
ValueError on bad input. Nothing here reads or writes files, spawns processes
or prints. Results are plain dicts/lists/floats/strings so `run()` output is
JSON-serialisable (non-finite floats such as an infinite far limit become None
in `run()` output and are explained in `limits`).

Honest scope: these are numerical building blocks, not a camera solver, a
renderer or a calibrated lens model. Each op states its own limits.
"""
from __future__ import annotations

import bisect
import inspect
import math
import random
import re
from fractions import Fraction

MAX_POINTS = 10000
MAX_PARAMS = 24

# --------------------------------------------------------------------------
# validation helpers
# --------------------------------------------------------------------------


def _num(name, v, lo=None, hi=None, lo_open=False, hi_open=False):
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise ValueError(f'{name} must be a number')
    try:
        v = float(v)
    except OverflowError:
        raise ValueError(f'{name} is too large') from None
    if not math.isfinite(v):
        raise ValueError(f'{name} must be finite')
    if lo is not None and (v < lo or (lo_open and v == lo)):
        raise ValueError(f'{name} out of range')
    if hi is not None and (v > hi or (hi_open and v == hi)):
        raise ValueError(f'{name} out of range')
    return v


def _int(name, v, lo, hi):
    if isinstance(v, bool) or not isinstance(v, int):
        raise ValueError(f'{name} must be an integer')
    if not lo <= v <= hi:
        raise ValueError(f'{name} out of range [{lo}, {hi}]')
    return v


def _choice(name, v, options):
    if not isinstance(v, str) or v not in options:
        raise ValueError(f'{name} must be one of {sorted(options)}')
    return v


def _vec(name, v, dims, lo=-1e9, hi=1e9):
    if not isinstance(v, (list, tuple)) or len(v) not in dims:
        raise ValueError(f'{name} must be a list of {sorted(dims)} numbers')
    return [_num(f'{name}[{i}]', x, lo, hi) for i, x in enumerate(v)]


def _points(name, v, dims, min_n=1, max_n=MAX_POINTS, lo=-1e9, hi=1e9):
    if not isinstance(v, (list, tuple)) or not min_n <= len(v) <= max_n:
        raise ValueError(f'{name} must be a list of {min_n}..{max_n} points')
    pts = [_vec(f'{name}[{i}]', p, dims, lo, hi) for i, p in enumerate(v)]
    if len({len(p) for p in pts}) != 1:
        raise ValueError(f'{name}: all points must have the same dimension')
    return pts


def _check_keys(name, d, allowed):
    if not isinstance(d, dict):
        raise ValueError(f'{name} must be a dict')
    extra = set(d) - set(allowed)
    if extra:
        raise ValueError(f'{name}: unknown keys {sorted(map(str, extra))}')


# --------------------------------------------------------------------------
# small linear algebra
# --------------------------------------------------------------------------


def _identity(n):
    return [[1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]


def _matmul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(len(b))) for j in range(len(b[0]))]
            for i in range(len(a))]


def _gauss(m, rhs_cols):
    """Gauss-Jordan elimination with partial pivoting on [m | rhs].

    Returns (solution columns, determinant). Raises ValueError if singular
    (pivot below 1e-12 times the largest entry of m).
    """
    n = len(m)
    a = [list(map(float, m[i])) + list(map(float, rhs_cols[i])) for i in range(n)]
    scale = max(abs(x) for row in m for x in row)
    if scale == 0:
        raise ValueError('matrix is singular')
    det = 1.0
    for c in range(n):
        p = max(range(c, n), key=lambda r: abs(a[r][c]))
        if abs(a[p][c]) <= 1e-12 * scale:
            raise ValueError('matrix is singular (or numerically singular)')
        if p != c:
            a[c], a[p] = a[p], a[c]
            det = -det
        piv = a[c][c]
        det *= piv
        inv = 1.0 / piv
        a[c] = [x * inv for x in a[c]]
        for r in range(n):
            if r != c and a[r][c] != 0.0:
                f = a[r][c]
                a[r] = [x - f * y for x, y in zip(a[r], a[c])]
    return [row[n:] for row in a], det


def invert_matrix(m):
    """Invert a square matrix (general Gaussian elimination with partial pivoting).

    Raises ValueError for singular matrices.
    """
    if not isinstance(m, (list, tuple)) or not 1 <= len(m) <= 8:
        raise ValueError('matrix must be square, size 1..8')
    m = [_vec(f'm[{i}]', row, {len(m)}) for i, row in enumerate(m)]
    inv, _ = _gauss(m, _identity(len(m)))
    return inv


def determinant(m):
    try:
        _, det = _gauss(m, [[] for _ in m])
    except ValueError:
        return 0.0
    return det


# --------------------------------------------------------------------------
# 05.01 transform
# --------------------------------------------------------------------------


def translation_matrix(offset):
    """Affine translation; len(offset) 2 -> 3x3, 3 -> 4x4."""
    off = _vec('offset', offset, {2, 3})
    m = _identity(len(off) + 1)
    for i, v in enumerate(off):
        m[i][-1] = v
    return m


def rotation_matrix(angle_deg, axis=None):
    """2D rotation (axis None, counter-clockwise) or 3D axis-angle (Rodrigues)."""
    a = math.radians(_num('angle_deg', angle_deg, -1e6, 1e6))
    c, s = math.cos(a), math.sin(a)
    if axis is None:
        return [[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]]
    ax = _vec('axis', axis, {3})
    n = math.sqrt(sum(x * x for x in ax))
    if n < 1e-12:
        raise ValueError('rotation axis must be non-zero')
    x, y, z = (v / n for v in ax)
    t = 1 - c
    return [[t * x * x + c, t * x * y - s * z, t * x * z + s * y, 0.0],
            [t * x * y + s * z, t * y * y + c, t * y * z - s * x, 0.0],
            [t * x * z - s * y, t * y * z + s * x, t * z * z + c, 0.0],
            [0.0, 0.0, 0.0, 1.0]]


def scale_matrix(factors):
    f = _vec('factors', factors, {2, 3})
    m = _identity(len(f) + 1)
    for i, v in enumerate(f):
        m[i][i] = v
    return m


def compose(*matrices):
    """Return the matrix that applies matrices[0] first, then matrices[1], ..."""
    if not 1 <= len(matrices) <= 64:
        raise ValueError('compose needs 1..64 matrices')
    out = matrices[0]
    for m in matrices[1:]:
        if len(m) != len(out):
            raise ValueError('matrix sizes differ')
        out = _matmul(m, out)
    return out


def apply_matrix(m, points):
    """Apply an affine 3x3 (2D) or 4x4 (3D) matrix to points."""
    n = len(m)
    pts = _points('points', points, {n - 1})
    out = []
    for p in pts:
        h = p + [1.0]
        out.append([sum(m[i][k] * h[k] for k in range(n)) for i in range(n - 1)])
    return out


def transform(steps=None, points=None, dim=2):
    """Build an affine matrix from ordered steps and optionally apply it to points.

    steps: list (1..64) of dicts, applied in order (step 0 acts first):
      {'type': 'translate', 'offset': [..dim]}
      {'type': 'rotate', 'angle_deg': a}               (2D, CCW)
      {'type': 'rotate', 'angle_deg': a, 'axis': [x,y,z]} (3D)
      {'type': 'scale', 'factors': [..dim]}
      {'type': 'matrix', 'm': affine (dim+1)x(dim+1)}
      {'type': 'invert'}  inverts everything accumulated so far; ValueError if singular.
    Returns matrix, determinant, inverse (None if singular) and transformed points.
    """
    dim = _int('dim', dim, 2, 3)
    if not isinstance(steps, (list, tuple)) or not 1 <= len(steps) <= 64:
        raise ValueError('steps must be a list of 1..64 step dicts')
    n = dim + 1
    m = _identity(n)
    for i, st in enumerate(steps):
        if not isinstance(st, dict):
            raise ValueError(f'steps[{i}] must be a dict')
        kind = _choice(f'steps[{i}].type', st.get('type'),
                       {'translate', 'rotate', 'scale', 'matrix', 'invert'})
        if kind == 'translate':
            _check_keys(f'steps[{i}]', st, {'type', 'offset'})
            s = translation_matrix(st.get('offset'))
        elif kind == 'rotate':
            if dim == 2:
                _check_keys(f'steps[{i}]', st, {'type', 'angle_deg'})
                s = rotation_matrix(st.get('angle_deg'))
            else:
                _check_keys(f'steps[{i}]', st, {'type', 'angle_deg', 'axis'})
                s = rotation_matrix(st.get('angle_deg'), st.get('axis'))
        elif kind == 'scale':
            _check_keys(f'steps[{i}]', st, {'type', 'factors'})
            s = scale_matrix(st.get('factors'))
        elif kind == 'matrix':
            _check_keys(f'steps[{i}]', st, {'type', 'm'})
            raw = st.get('m')
            if not isinstance(raw, (list, tuple)) or len(raw) != n:
                raise ValueError(f'steps[{i}].m must be {n}x{n}')
            s = [_vec(f'steps[{i}].m[{r}]', row, {n}) for r, row in enumerate(raw)]
            if any(abs(s[-1][j] - (1.0 if j == n - 1 else 0.0)) > 1e-12 for j in range(n)):
                raise ValueError(f'steps[{i}].m must be affine (last row 0..0 1)')
        else:
            _check_keys(f'steps[{i}]', st, {'type'})
            m = invert_matrix(m)
            continue
        if len(s) != n:
            raise ValueError(f'steps[{i}] dimension does not match dim={dim}')
        m = _matmul(s, m)
    try:
        inv = invert_matrix(m)
    except ValueError:
        inv = None
    out = {'matrix': m, 'determinant': determinant(m), 'invertible': inv is not None,
           'inverse': inv}
    if points is not None:
        out['points'] = apply_matrix(m, points)
    return out


# --------------------------------------------------------------------------
# 05.02 perspective
# --------------------------------------------------------------------------


def perspective(points=None, vfov_deg=50.0, width=1920, height=1080, near=0.01):
    """Pinhole projection. Camera at origin, looking down +Z, +X right, +Y up.

    Points with z <= near are flagged 'behind_camera' (no projection returned).
    Edge stretch: a small sphere at off-axis angle t images as an ellipse whose
    radial/tangential ratio is 1/cos(t); reported at the horizontal edge,
    vertical edge and corner (centre = 1.0). Area grows as 1/cos(t)^3.
    """
    vfov = _num('vfov_deg', vfov_deg, 1.0, 170.0)
    w = _int('width', width, 16, 16384)
    h = _int('height', height, 16, 16384)
    near = _num('near', near, 1e-6, 1e6)
    pts = _points('points', points, {3})
    aspect = w / h
    tv = math.tan(math.radians(vfov) / 2)
    f = 1.0 / tv
    proj = []
    for p in pts:
        x, y, z = p
        if z <= near:
            proj.append({'visible': False, 'reason': 'behind_camera', 'ndc': None,
                         'pixel': None, 'in_frame': False})
            continue
        nx, ny = f * x / (z * aspect), f * y / z
        proj.append({'visible': True, 'reason': None, 'ndc': [nx, ny],
                     'pixel': [(nx + 1) / 2 * w, (1 - ny) / 2 * h],
                     'in_frame': abs(nx) <= 1 and abs(ny) <= 1})
    th = math.atan(aspect * tv)
    tc = math.atan(math.hypot(aspect, 1.0) * tv)
    tvh = math.radians(vfov) / 2
    return {'projections': proj, 'aspect': aspect, 'focal_ndc': f,
            'hfov_deg': math.degrees(2 * th), 'vfov_deg': vfov,
            'diag_fov_deg': math.degrees(2 * tc),
            'edge_stretch': {'centre': 1.0, 'horizontal_edge': 1 / math.cos(th),
                             'vertical_edge': 1 / math.cos(tvh), 'corner': 1 / math.cos(tc),
                             'corner_area': 1 / math.cos(tc) ** 3},
            'behind_count': sum(1 for p in proj if not p['visible'])}


# --------------------------------------------------------------------------
# 05.03 curves
# --------------------------------------------------------------------------


def _bezier(pts):
    p0, p1, p2, p3 = pts

    def ev(t):
        u = 1 - t
        b = [u * u * u, 3 * u * u * t, 3 * u * t * t, t * t * t]
        d = [3 * u * u, 6 * u * t, 3 * t * t]
        pos = [b[0] * a + b[1] * bb + b[2] * c + b[3] * e for a, bb, c, e in zip(p0, p1, p2, p3)]
        der = [d[0] * (bb - a) + d[1] * (c - bb) + d[2] * (e - c) for a, bb, c, e in zip(p0, p1, p2, p3)]
        return pos, der
    return ev, 0.0, 1.0, [0.0, 1.0]


def _catmull(pts, alpha):
    n = len(pts)
    ext = [[2 * a - b for a, b in zip(pts[0], pts[1])]] + pts + \
          [[2 * a - b for a, b in zip(pts[-1], pts[-2])]]
    knots = [0.0]
    for i in range(len(ext) - 1):
        d = math.dist(ext[i], ext[i + 1])
        if d < 1e-12:
            raise ValueError('consecutive control points must differ')
        knots.append(knots[-1] + d ** alpha)
    tans = []
    for i in range(1, n + 1):
        a, b, c = ext[i - 1], ext[i], ext[i + 1]
        t0, t1, t2 = knots[i - 1], knots[i], knots[i + 1]
        tans.append([(y - x) / (t1 - t0) - (z - x) / (t2 - t0) + (z - y) / (t2 - t1)
                     for x, y, z in zip(a, b, c)])
    T = [knots[i + 1] - knots[1] for i in range(n)]

    def seg(j, s):
        dlt = T[j + 1] - T[j]
        s2, s3 = s * s, s * s * s
        h = (2 * s3 - 3 * s2 + 1, s3 - 2 * s2 + s, -2 * s3 + 3 * s2, s3 - s2)
        hd = (6 * s2 - 6 * s, 3 * s2 - 4 * s + 1, -6 * s2 + 6 * s, 3 * s2 - 2 * s)
        P0, P1, M0, M1 = pts[j], pts[j + 1], tans[j], tans[j + 1]
        pos = [h[0] * a + h[1] * dlt * m0 + h[2] * b + h[3] * dlt * m1
               for a, b, m0, m1 in zip(P0, P1, M0, M1)]
        der = [(hd[0] * a + hd[1] * dlt * m0 + hd[2] * b + hd[3] * dlt * m1) / dlt
               for a, b, m0, m1 in zip(P0, P1, M0, M1)]
        return pos, der

    def ev(t):
        j = min(max(bisect.bisect_right(T, t) - 1, 0), n - 2)
        return seg(j, (t - T[j]) / (T[j + 1] - T[j]))
    joins = []
    for j in range(1, n - 1):
        joins.append({'index': j, 'left_tangent': seg(j - 1, 1.0)[1],
                      'right_tangent': seg(j, 0.0)[1]})
    return ev, 0.0, T[-1], T, joins


def curves(kind='catmull_rom', points=None, alpha=0.5, samples=21, t_values=None,
           constant_speed_samples=0, table_size=1024):
    """Cubic Bezier (exactly 4 control points, t in [0,1]) or Catmull-Rom spline.

    Catmull-Rom: Barry-Goldman knot spacing |dP|**alpha (0 uniform, 0.5
    centripetal, 1 chordal), written in cubic Hermite form with knot tangents,
    so it interpolates every control point and is C1 in the global knot
    parameter t (t of control point i is reported in 'control_params').
    End tangents use reflected phantom points. Tangents are dP/dt.
    Arc length uses a chord table of `table_size` samples; constant-speed
    samples invert that table (accuracy limited by table density).
    """
    kind = _choice('kind', kind, {'bezier', 'catmull_rom'})
    if kind == 'bezier':
        pts = _points('points', points, {2, 3}, 4, 4)
        ev, t0, t1, ctrl = _bezier(pts)
        joins = []
    else:
        pts = _points('points', points, {2, 3}, 2, 256)
        a = _num('alpha', alpha, 0.0, 1.0)
        ev, t0, t1, ctrl, joins = _catmull(pts, a)
    samples = _int('samples', samples, 2, MAX_POINTS)
    cs = _int('constant_speed_samples', constant_speed_samples, 0, MAX_POINTS)
    tsz = _int('table_size', table_size, 16, 20000)
    if t_values is None:
        ts = [t0 + (t1 - t0) * k / (samples - 1) for k in range(samples)]
        ts[-1] = t1
    else:
        if not isinstance(t_values, (list, tuple)) or not 1 <= len(t_values) <= MAX_POINTS:
            raise ValueError('t_values must be a list of 1..10000 numbers')
        ts = [_num(f't_values[{i}]', v, t0, t1) for i, v in enumerate(t_values)]
    out_samples = []
    for t in ts:
        p, d = ev(t)
        out_samples.append({'t': t, 'point': p, 'tangent': d})
    tab_t = [t0 + (t1 - t0) * k / (tsz - 1) for k in range(tsz)]
    tab_t[-1] = t1
    tab_p = [ev(t)[0] for t in tab_t]
    tab_s = [0.0]
    for k in range(1, tsz):
        tab_s.append(tab_s[-1] + math.dist(tab_p[k - 1], tab_p[k]))
    length = tab_s[-1]
    result = {'kind': kind, 'domain': [t0, t1], 'control_params': ctrl,
              'samples': out_samples, 'length': length, 'joins': joins}
    if cs:
        if cs < 2:
            raise ValueError('constant_speed_samples must be 0 or >= 2')
        if length <= 0:
            raise ValueError('curve has zero length')
        cpts = []
        for k in range(cs):
            target = length * k / (cs - 1)
            i = min(max(bisect.bisect_left(tab_s, target), 1), tsz - 1)
            seg_len = tab_s[i] - tab_s[i - 1]
            f = 0.0 if seg_len <= 0 else (target - tab_s[i - 1]) / seg_len
            t = tab_t[i - 1] + f * (tab_t[i] - tab_t[i - 1])
            cpts.append({'t': t, 'arc_length': target, 'point': ev(t)[0]})
        result['constant_speed'] = cpts
    return result


# --------------------------------------------------------------------------
# 05.04 aspect_fit
# --------------------------------------------------------------------------

_ASPECTS = {'9:16': (9, 16), '16:9': (16, 9), '1:1': (1, 1), '4:5': (4, 5)}


def _even(x):
    return max(2, 2 * int(math.floor(x / 2 + 0.5)))


def _place(centre, size, total, fstart=None, flen=None):
    x = int(math.floor(centre - size / 2 + 0.5))
    x = min(max(x, 0), total - size)
    if flen is not None:
        lo, hi = math.ceil(fstart + flen - size), math.floor(fstart)
        if lo <= hi:
            x = min(max(x, lo), hi)
            x = min(max(x, 0), total - size)
    return x


def _safe(w, h, frac):
    m = (1 - frac) / 2
    return [w * m, h * m, w * frac, h * frac]


def aspect_fit(src_width=1920, src_height=1080, target='9:16', mode='cover', focus=None,
               output_long_edge=1920):
    """Fit a source frame into a target aspect.

    target: '9:16', '16:9', '1:1', '4:5' or custom 'W:H' (integers 1..10000).
    mode 'cover': crop the source (even integer size, largest that fits) and
      scale to fill the output; the crop is centred on the focus box (or frame
      centre) and shifted so the focus box [x, y, w, h] (source px) stays fully
      inside the crop when it is small enough; otherwise reported clearly.
    mode 'contain': scale the whole source inside the output with bars.
    Output size is even integers with the long edge = output_long_edge.
    Safe areas: title-safe 90 % and action-safe 93 % of the output, centred.
    Even rounding means the crop aspect can differ slightly; see crop_aspect_error.
    """
    sw = _int('src_width', src_width, 16, 100000)
    sh = _int('src_height', src_height, 16, 100000)
    mode = _choice('mode', mode, {'cover', 'contain'})
    long_edge = _int('output_long_edge', output_long_edge, 16, 16384)
    if not isinstance(target, str):
        raise ValueError('target must be a string like "9:16"')
    if target in _ASPECTS:
        rw, rh = _ASPECTS[target]
    else:
        mt = re.fullmatch(r'(\d{1,5}):(\d{1,5})', target)
        if not mt:
            raise ValueError('target must be 9:16, 16:9, 1:1, 4:5 or W:H')
        rw, rh = int(mt.group(1)), int(mt.group(2))
        if not (1 <= rw <= 10000 and 1 <= rh <= 10000):
            raise ValueError('target ratio out of range')
    ratio = rw / rh
    if ratio >= 1:
        ow, oh = _even(long_edge), _even(long_edge / ratio)
    else:
        ow, oh = _even(long_edge * ratio), _even(long_edge)
    fb = None
    if focus is not None:
        fb = _vec('focus', focus, {4}, 0, 1e6)
        if fb[2] <= 0 or fb[3] <= 0 or fb[0] + fb[2] > sw or fb[1] + fb[3] > sh:
            raise ValueError('focus box must have positive size and lie inside the source')
    result = {'mode': mode, 'target': f'{rw}:{rh}', 'output_size': [ow, oh],
              'title_safe': _safe(ow, oh, 0.90), 'action_safe': _safe(ow, oh, 0.93)}
    if mode == 'cover':
        if sw / sh > ratio:
            ch = sh - (sh % 2)
            cw = min(sw - (sw % 2), _even(ch * ratio))
        else:
            cw = sw - (sw % 2)
            ch = min(sh - (sh % 2), _even(cw / ratio))
        cx, cy = (fb[0] + fb[2] / 2, fb[1] + fb[3] / 2) if fb else (sw / 2, sh / 2)
        x = _place(cx, cw, sw, *( (fb[0], fb[2]) if fb else (None, None)))
        y = _place(cy, ch, sh, *( (fb[1], fb[3]) if fb else (None, None)))
        scale = ow / cw
        result.update({'crop': [x, y, cw, ch], 'scale': scale,
                       'crop_aspect_error': (cw / ch) / ratio - 1})
        if fb:
            visible = x <= fb[0] and fb[0] + fb[2] <= x + cw and y <= fb[1] and fb[1] + fb[3] <= y + ch
            result['focus_fully_visible'] = visible
            if visible:
                ofb = [(fb[0] - x) * scale, (fb[1] - y) * (oh / ch), fb[2] * scale, fb[3] * (oh / ch)]
                ts = result['title_safe']
                result['focus_in_output'] = ofb
                result['focus_in_title_safe'] = (ofb[0] >= ts[0] and ofb[1] >= ts[1] and
                                                 ofb[0] + ofb[2] <= ts[0] + ts[2] and
                                                 ofb[1] + ofb[3] <= ts[1] + ts[3])
                result['focus_note'] = 'focus box fully inside crop'
            else:
                result['focus_note'] = (f'focus box {fb[2]:g}x{fb[3]:g} does not fit the '
                                        f'{cw}x{ch} crop; crop centred on focus, edges cut')
    else:
        scale = min(ow / sw, oh / sh)
        cw = min(ow, _even(sw * scale))
        ch = min(oh, _even(sh * scale))
        result.update({'content': [(ow - cw) // 2, (oh - ch) // 2, cw, ch], 'scale': scale,
                       'bars': 'left/right' if cw < ow else ('top/bottom' if ch < oh else 'none')})
        if fb:
            result['focus_fully_visible'] = True
            result['focus_note'] = 'contain mode never crops'
    return result


# --------------------------------------------------------------------------
# 05.05 depth_of_field
# --------------------------------------------------------------------------


def depth_of_field(focal_mm=50.0, f_number=2.8, focus_m=3.0, coc_mm=0.03, object_m=None):
    """Thin-lens depth of field.

    H = f^2/(N c) + f; near = s(H-f)/(H+s-2f); far = s(H-f)/(H-s) for s < H,
    else infinite (math.inf; None in run() output). Blur circle on the sensor
    for an object at distance d: b = f^2 |d-s| / (N d (s-f)).
    Ignores pupil magnification, focus breathing and diffraction.
    """
    f = _num('focal_mm', focal_mm, 1.0, 2000.0)
    n = _num('f_number', f_number, 0.5, 128.0)
    s_m = _num('focus_m', focus_m, 0.0, 1e6, lo_open=True)
    c = _num('coc_mm', coc_mm, 0.001, 1.0)
    s = s_m * 1000.0
    if s <= f:
        raise ValueError('focus distance must exceed the focal length')
    H = f * f / (n * c) + f
    near = s * (H - f) / (H + s - 2 * f)
    far = math.inf if s >= H else s * (H - f) / (H - s)
    out = {'hyperfocal_m': H / 1000, 'near_m': near / 1000,
           'far_m': far if far == math.inf else far / 1000,
           'far_is_infinite': far == math.inf,
           'total_dof_m': math.inf if far == math.inf else (far - near) / 1000}
    if object_m is not None:
        d = _num('object_m', object_m, 0.0, 1e9, lo_open=True) * 1000
        if d <= f:
            raise ValueError('object distance must exceed the focal length')
        b = f * f * abs(d - s) / (n * d * (s - f))
        out.update({'blur_mm': b, 'blur_over_coc': b / c, 'object_in_focus': b <= c})
    return out


# --------------------------------------------------------------------------
# 05.06 ik_two_bone
# --------------------------------------------------------------------------


def ik_two_bone(l1=1.0, l2=1.0, target=(1.0, 1.0), root=(0.0, 0.0), elbow='left'):
    """Analytic 2D two-bone IK.

    elbow 'left' puts the joint on the left of the root->target direction
    (counter-clockwise side), 'right' on the other. Targets beyond l1+l2 or
    inside |l1-l2| are clamped along the same direction and flagged. A target
    exactly at the root uses +X as an arbitrary direction (flagged).
    Angles: theta1 is bone 1 world angle, theta2 is bone 2 angle relative to bone 1.
    """
    l1 = _num('l1', l1, 0.0, 1e6, lo_open=True)
    l2 = _num('l2', l2, 0.0, 1e6, lo_open=True)
    tx, ty = _vec('target', target, {2})
    rx, ry = _vec('root', root, {2})
    side = 1.0 if _choice('elbow', elbow, {'left', 'right'}) == 'left' else -1.0
    dx, dy = tx - rx, ty - ry
    d = math.hypot(dx, dy)
    notes = []
    if d <= 1e-12 * (l1 + l2):
        ux, uy = 1.0, 0.0
        notes.append('target at root: direction +X chosen arbitrarily')
    else:
        ux, uy = dx / d, dy / d
    maxr, minr = l1 + l2, abs(l1 - l2)
    reach = min(max(d, minr), maxr)
    clamped = reach != d
    if d > maxr:
        notes.append('target beyond max reach: clamped to l1+l2 along target direction')
    elif d < minr:
        notes.append('target inside min reach: clamped to |l1-l2| along target direction')
    if clamped:
        ex, ey = rx + ux * reach, ry + uy * reach
    else:
        ex, ey = tx, ty
    if reach == 0.0:
        x, hgt = 0.0, l1
    else:
        x = (l1 * l1 - l2 * l2 + reach * reach) / (2 * reach)
        x = min(max(x, -l1), l1)
        hgt = math.sqrt(max(0.0, (l1 - x) * (l1 + x)))
    jx = rx + ux * x - side * uy * hgt
    jy = ry + uy * x + side * ux * hgt
    vx, vy = ex - jx, ey - jy
    vn = math.hypot(vx, vy)
    if vn == 0:
        vx, vy, vn = -ux, -uy, 1.0
    endx, endy = jx + l2 * vx / vn, jy + l2 * vy / vn
    th1 = math.atan2(jy - ry, jx - rx)
    th2 = math.atan2(endy - jy, endx - jx) - th1
    th2 = (th2 + math.pi) % (2 * math.pi) - math.pi
    return {'joint': [jx, jy], 'end': [endx, endy], 'theta1_rad': th1, 'theta2_rad': th2,
            'theta1_deg': math.degrees(th1), 'theta2_deg': math.degrees(th2),
            'reachable': not clamped, 'clamped': clamped, 'target_distance': d,
            'reach_used': reach, 'max_reach': maxr, 'min_reach': minr,
            'end_error': math.hypot(endx - tx, endy - ty), 'notes': notes}


# --------------------------------------------------------------------------
# 05.07 camera_path
# --------------------------------------------------------------------------


def _minjerk(u):
    return u * u * u * (10 + u * (-15 + 6 * u))


def camera_path(keyframes=None, fps=30, easing='min_jerk', shake_amplitude=0.0,
                shake_frequency_hz=6.0, shake_seed=0):
    """Keyframed camera path sampled at fps.

    keyframes: 2..64 dicts {'t': seconds, 'value': [1..4 numbers]} with strictly
    increasing t. easing 'min_jerk' uses the quintic 10u^3-15u^4+6u^5 per
    segment (zero velocity AND acceleration at every keyframe: the camera
    settles at each key; it is not a through-key spline). 'linear' is
    constant speed per segment, for comparison.
    Optional seeded handheld shake (sum of 3 sinusoids per axis, peak <=
    amplitude) is windowed by (4u(1-u))^3 over the whole path so endpoints and
    end velocities stay exact; intermediate keys are NOT exact when shaking.
    Metrics use finite differences on a 1/fps grid padded with 3 rest samples
    each side (camera at rest before/after): max speed, max acceleration and
    RMS jerk (the shake metric).
    """
    if not isinstance(keyframes, (list, tuple)) or not 2 <= len(keyframes) <= 64:
        raise ValueError('keyframes must be a list of 2..64 dicts')
    ts, vals = [], []
    for i, k in enumerate(keyframes):
        _check_keys(f'keyframes[{i}]', k, {'t', 'value'})
        ts.append(_num(f'keyframes[{i}].t', k.get('t'), -1e6, 1e6))
        vals.append(_vec(f'keyframes[{i}].value', k.get('value'), {1, 2, 3, 4}))
    if len({len(v) for v in vals}) != 1:
        raise ValueError('all keyframe values must have the same length')
    if any(b - a <= 1e-9 for a, b in zip(ts, ts[1:])):
        raise ValueError('keyframe times must be strictly increasing')
    fps = _num('fps', fps, 1.0, 240.0)
    easing = _choice('easing', easing, {'min_jerk', 'linear'})
    amp = _num('shake_amplitude', shake_amplitude, 0.0, 1e6)
    freq = _num('shake_frequency_hz', shake_frequency_hz, 0.01, 60.0)
    seed = _int('shake_seed', shake_seed, 0, 2 ** 32 - 1)
    dim = len(vals[0])
    t0, t1 = ts[0], ts[-1]
    dur = t1 - t0
    nframes = int(math.floor(dur * fps + 1e-9))
    if nframes + 2 > 20000:
        raise ValueError('too many samples (max 20000): shorten the path or lower fps')
    rng = random.Random(seed)
    waves = [[(freq * (0.6 + 0.8 * rng.random()), 2 * math.pi * rng.random(), w)
              for w in (0.5, 0.3, 0.2)] for _ in range(dim)]
    ease = _minjerk if easing == 'min_jerk' else (lambda u: u)

    def pos(t):
        if t <= t0:
            return list(vals[0])
        if t >= t1:
            return list(vals[-1])
        j = min(bisect.bisect_right(ts, t) - 1, len(ts) - 2)
        s = ease((t - ts[j]) / (ts[j + 1] - ts[j]))
        p = [(1 - s) * a + s * b for a, b in zip(vals[j], vals[j + 1])]
        if amp > 0:
            u = (t - t0) / dur
            win = (4 * u * (1 - u)) ** 3
            p = [c + amp * win * sum(w * math.sin(2 * math.pi * f * (t - t0) + ph)
                                     for f, ph, w in waves[i]) for i, c in enumerate(p)]
        return p

    times = [t0 + k / fps for k in range(nframes + 1)]
    if abs(times[-1] - t1) <= 1e-9:
        times[-1] = t1
    else:
        times.append(t1)
    samples = [{'t': t, 'value': pos(t)} for t in times]
    h = 1 / fps
    grid = [pos(t0 + k * h) for k in range(-3, nframes + 5)]

    def diff(seq):
        return [[(b - a) / h for a, b in zip(p, q)] for p, q in zip(seq, seq[1:])]
    v = diff(grid)
    a = diff(v)
    j = diff(a)
    norm = lambda vec: math.sqrt(sum(x * x for x in vec))
    d0 = ts[1] - ts[0]
    dN = ts[-1] - ts[-2]
    if easing == 'min_jerk':
        sv = [0.0] * dim
        ev = [0.0] * dim
    else:
        sv = [(b - a_) / d0 for a_, b in zip(vals[0], vals[1])]
        ev = [(b - a_) / dN for a_, b in zip(vals[-2], vals[-1])]
    return {'samples': samples, 'sample_count': len(samples), 'duration': dur,
            'start_velocity': sv, 'end_velocity': ev,
            'max_speed': max(norm(x) for x in v), 'max_acceleration': max(norm(x) for x in a),
            'rms_jerk': math.sqrt(sum(norm(x) ** 2 for x in j) / len(j)),
            'easing': easing, 'shake': {'amplitude': amp, 'frequency_hz': freq, 'seed': seed}}


# --------------------------------------------------------------------------
# 05.08 homography
# --------------------------------------------------------------------------


def _jacobi_eigen(S, max_sweeps=100):
    n = len(S)
    A = [row[:] for row in S]
    V = _identity(n)
    total = sum(x * x for row in A for x in row) or 1.0
    for _ in range(max_sweeps):
        off = sum(A[p][q] ** 2 for p in range(n) for q in range(n) if p != q)
        if off <= 1e-30 * total:
            break
        for p in range(n - 1):
            for q in range(p + 1, n):
                apq = A[p][q]
                if abs(apq) <= 1e-300:
                    continue
                theta = (A[q][q] - A[p][p]) / (2 * apq)
                t = (1.0 if theta >= 0 else -1.0) / (abs(theta) + math.sqrt(theta * theta + 1))
                c = 1 / math.sqrt(t * t + 1)
                s = t * c
                for k in range(n):
                    akp, akq = A[k][p], A[k][q]
                    A[k][p] = c * akp - s * akq
                    A[k][q] = s * akp + c * akq
                for k in range(n):
                    apk, aqk = A[p][k], A[q][k]
                    A[p][k] = c * apk - s * aqk
                    A[q][k] = s * apk + c * aqk
                for k in range(n):
                    vkp, vkq = V[k][p], V[k][q]
                    V[k][p] = c * vkp - s * vkq
                    V[k][q] = s * vkp + c * vkq
    vals = [A[i][i] for i in range(n)]
    order = sorted(range(n), key=lambda i: vals[i])
    return [vals[i] for i in order], [[V[k][i] for k in range(n)] for i in order]


def _normaliser(pts):
    cx = sum(p[0] for p in pts) / len(pts)
    cy = sum(p[1] for p in pts) / len(pts)
    md = sum(math.hypot(p[0] - cx, p[1] - cy) for p in pts) / len(pts)
    if md < 1e-12:
        raise ValueError('degenerate point set: all points coincide')
    s = math.sqrt(2) / md
    T = [[s, 0.0, -s * cx], [0.0, s, -s * cy], [0.0, 0.0, 1.0]]
    Tinv = [[1 / s, 0.0, cx], [0.0, 1 / s, cy], [0.0, 0.0, 1.0]]
    return T, Tinv, [[s * (p[0] - cx), s * (p[1] - cy)] for p in pts]


def _collinear_check(name, npts):
    m = len(npts)
    sxx = sum(p[0] * p[0] for p in npts) / m
    syy = sum(p[1] * p[1] for p in npts) / m
    sxy = sum(p[0] * p[1] for p in npts) / m
    tr, det = sxx + syy, sxx * syy - sxy * sxy
    lam_min = tr / 2 - math.sqrt(max(0.0, tr * tr / 4 - det))
    if lam_min <= 1e-10 * tr:
        raise ValueError(f'degenerate {name} points: all collinear')
    if m == 4:
        for i in range(4):
            for j in range(i + 1, 4):
                for k in range(j + 1, 4):
                    a, b, c = npts[i], npts[j], npts[k]
                    area = abs((b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]))
                    if area <= 1e-9:
                        raise ValueError(f'degenerate {name} points: three of four are collinear')


def apply_homography(H, pts):
    out = []
    for x, y in pts:
        w = H[2][0] * x + H[2][1] * y + H[2][2]
        if abs(w) < 1e-12:
            out.append(None)
        else:
            out.append([(H[0][0] * x + H[0][1] * y + H[0][2]) / w,
                        (H[1][0] * x + H[1][1] * y + H[1][2]) / w])
    return out


def homography(src=None, dst=None):
    """DLT homography mapping src -> dst from 4..500 point pairs.

    Hartley normalisation (centroid to origin, mean distance sqrt 2) on both
    sets, then the total-least-squares solution: eigenvector of the smallest
    eigenvalue of A^T A (9x9, cyclic Jacobi, pure Python). Rejects coincident
    or collinear sets (any collinear triple when n == 4) and solutions whose two
    smallest eigenvalues are both ~0 (non-unique). Minimises algebraic, not
    geometric, error; no RANSAC, so outliers are not rejected.
    """
    s = _points('src', src, {2}, 4, 500)
    d = _points('dst', dst, {2}, 4, 500)
    if len(s) != len(d):
        raise ValueError('src and dst must have the same number of points')
    Ts, _, ns = _normaliser(s)
    Td, Tdinv, nd = _normaliser(d)
    _collinear_check('src', ns)
    _collinear_check('dst', nd)
    ata = [[0.0] * 9 for _ in range(9)]
    for (x, y), (u, v) in zip(ns, nd):
        for row in ([-x, -y, -1.0, 0.0, 0.0, 0.0, u * x, u * y, u],
                    [0.0, 0.0, 0.0, -x, -y, -1.0, v * x, v * y, v]):
            for i in range(9):
                ri = row[i]
                if ri:
                    for j in range(9):
                        ata[i][j] += ri * row[j]
    vals, vecs = _jacobi_eigen(ata)
    if vals[1] <= 1e-10 * max(vals[-1], 1e-300):
        raise ValueError('degenerate configuration: homography not unique')
    h = vecs[0]
    Hn = [h[0:3], h[3:6], h[6:9]]
    H = _matmul(Tdinv, _matmul(Hn, Ts))
    if abs(H[2][2]) > 1e-12:
        k = 1 / H[2][2]
    else:
        k = 1 / math.sqrt(sum(x * x for row in H for x in row))
    H = [[x * k for x in row] for row in H]
    if abs(determinant(H)) < 1e-15:
        raise ValueError('degenerate configuration: singular homography')
    proj = apply_homography(H, s)
    errs = [math.inf if p is None else math.dist(p, q) for p, q in zip(proj, d)]
    return {'H': H, 'mean_reprojection_error': sum(errs) / len(errs),
            'max_reprojection_error': max(errs),
            'rms_reprojection_error': math.sqrt(sum(e * e for e in errs) / len(errs)),
            'errors': errs, 'pairs': len(s), 'exact_fit': len(s) == 4,
            'eigen_ratio': vals[0] / vals[1] if vals[1] else None}


# --------------------------------------------------------------------------
# 05.09 timecode
# --------------------------------------------------------------------------

_DF_RATES = {Fraction(30000, 1001): 2, Fraction(60000, 1001): 4}
_EPS_FRAMES = Fraction(1, 10 ** 6)


def _fps(v):
    if isinstance(v, bool) or isinstance(v, float):
        raise ValueError('fps must be an int or a string like "30000/1001" (no floats)')
    if isinstance(v, int):
        f = Fraction(v)
    elif isinstance(v, str) and re.fullmatch(r'\d{1,6}(/\d{1,6}|\.\d{1,6})?', v.strip()):
        f = Fraction(v.strip())
    else:
        raise ValueError('fps must be an int or a string like "30000/1001"')
    if not 0 < f <= 240 or f.denominator > 10000:
        raise ValueError('fps out of range (0, 240]')
    return f


def _seconds(v):
    if isinstance(v, str):
        if not re.fullmatch(r'\d{1,9}(/\d{1,9}|\.\d{1,12})?', v.strip()):
            raise ValueError('seconds string must be like "1001/30000" or "1.5"')
        sec = Fraction(v.strip())
    else:
        sec = Fraction(_num('seconds', v, 0.0, 864000.0))
    if not 0 <= sec <= 864000:
        raise ValueError('seconds out of range [0, 864000]')
    return sec


def _df_info(fps):
    nominal = math.ceil(fps)
    drop = _DF_RATES.get(fps)
    return nominal, drop


def timecode(action='seconds_to_frame', fps='30000/1001', seconds=None, frame=None, tc=None,
             rounding='floor', drop_frame=None):
    """Exact rational timeline maths.

    actions: seconds_to_frame, frame_to_seconds, frame_to_tc, tc_to_frame.
    fps: int or exact string ('24', '25', '30000/1001', '60000/1001'); floats
    are rejected to avoid 29.97 != 30000/1001 mistakes.
    rounding: 'floor' = frame containing the instant, with a 1e-6-frame guard
      so float seconds that land a hair below a boundary snap up; 'round' =
      nearest frame, halves round up.
    drop_frame: only for 30000/1001 (drops 2) and 60000/1001 (drops 4). For
      frame_to_tc None means non-drop; for tc_to_frame None means infer from
      separator (';' or '.' = drop-frame). Timecode is limited to < 24 h, no wrap.
    """
    action = _choice('action', action, {'seconds_to_frame', 'frame_to_seconds',
                                        'frame_to_tc', 'tc_to_frame'})
    f = _fps(fps)
    rounding = _choice('rounding', rounding, {'floor', 'round'})
    if drop_frame is not None and not isinstance(drop_frame, bool):
        raise ValueError('drop_frame must be true, false or null')
    nominal, drop = _df_info(f)
    fps_s = f'{f.numerator}/{f.denominator}'

    def frames_per_day(df):
        if df:
            return 24 * 6 * (nominal * 600 - drop * 9)
        return nominal * 86400

    def need_frame():
        if frame is None:
            raise ValueError('frame is required')
        return _int('frame', frame, 0, 10 ** 9)

    if action == 'seconds_to_frame':
        if seconds is None:
            raise ValueError('seconds is required')
        x = _seconds(seconds) * f
        if rounding == 'floor':
            n = math.floor(x)
            if x - n >= 1 - _EPS_FRAMES:
                n += 1
        else:
            n = math.floor(x + Fraction(1, 2))
        return {'frame': n, 'fps': fps_s, 'rounding': rounding, 'exact_frames': str(x)}
    if action == 'frame_to_seconds':
        n = need_frame()
        sec = Fraction(n) / f
        return {'seconds': float(sec), 'seconds_exact': f'{sec.numerator}/{sec.denominator}',
                'fps': fps_s, 'frame_start': True}
    if action == 'frame_to_tc':
        n = need_frame()
        df = bool(drop_frame)
        if df and drop is None:
            raise ValueError('drop-frame only exists for 30000/1001 and 60000/1001')
        if n >= frames_per_day(df):
            raise ValueError('frame beyond 24 h of timecode (no wrap)')
        fn = n
        if df:
            per10 = nominal * 600 - drop * 9
            permin = nominal * 60 - drop
            dd, m = divmod(n, per10)
            if m > drop:
                fn = n + drop * 9 * dd + drop * ((m - drop) // permin)
            else:
                fn = n + drop * 9 * dd
        ff = fn % nominal
        ss = (fn // nominal) % 60
        mm = (fn // (nominal * 60)) % 60
        hh = fn // (nominal * 3600)
        width = 3 if nominal > 100 else 2
        return {'tc': f'{hh:02d}:{mm:02d}:{ss:02d}{";" if df else ":"}{ff:0{width}d}',
                'drop_frame': df, 'fps': fps_s, 'nominal_fps': nominal}
    # tc_to_frame
    if not isinstance(tc, str):
        raise ValueError('tc must be a string HH:MM:SS:FF (or ;FF for drop-frame)')
    mt = re.fullmatch(r'(\d{2}):(\d{2}):(\d{2})([:;.,])(\d{2,3})', tc.strip())
    if not mt:
        raise ValueError('tc must look like HH:MM:SS:FF or HH:MM:SS;FF')
    hh, mm, ss, sep, ff = int(mt.group(1)), int(mt.group(2)), int(mt.group(3)), mt.group(4), int(mt.group(5))
    df = sep in ';.' if drop_frame is None else drop_frame
    if df and drop is None:
        raise ValueError('drop-frame only exists for 30000/1001 and 60000/1001')
    if hh >= 24 or mm >= 60 or ss >= 60 or ff >= nominal:
        raise ValueError('timecode field out of range')
    if df and ss == 0 and ff < drop and mm % 10 != 0:
        raise ValueError('timecode does not exist in drop-frame (dropped number)')
    total_min = 60 * hh + mm
    n = ((hh * 3600 + mm * 60 + ss) * nominal + ff)
    if df:
        n -= drop * (total_min - total_min // 10)
    return {'frame': n, 'drop_frame': df, 'fps': fps_s, 'nominal_fps': nominal}


# --------------------------------------------------------------------------
# 05.10 lens_distortion
# --------------------------------------------------------------------------


def _distort(x, y, k1, k2, k3, p1, p2):
    r2 = x * x + y * y
    R = 1 + r2 * (k1 + r2 * (k2 + r2 * k3))
    return (x * R + 2 * p1 * x * y + p2 * (r2 + 2 * x * x),
            y * R + p1 * (r2 + 2 * y * y) + 2 * p2 * x * y)


def _jac(x, y, k1, k2, k3, p1, p2):
    r2 = x * x + y * y
    R = 1 + r2 * (k1 + r2 * (k2 + r2 * k3))
    Rp = k1 + 2 * k2 * r2 + 3 * k3 * r2 * r2
    a = R + 2 * x * x * Rp + 2 * p1 * y + 6 * p2 * x
    b = 2 * x * y * Rp + 2 * p1 * x + 2 * p2 * y
    d = R + 2 * y * y * Rp + 6 * p1 * y + 2 * p2 * x
    return a, b, b, d, R


def _undistort(xd, yd, co, max_iter, tol):
    x, y = xd, yd
    thr = tol * (1 + math.hypot(xd, yd))
    for it in range(1, max_iter + 1):
        fx, fy = _distort(x, y, *co)
        rx, ry = fx - xd, fy - yd
        res = math.hypot(rx, ry)
        a, b, c, d, R = _jac(x, y, *co)
        if res <= thr:
            if R <= 0 or a * d - b * c <= 0:
                return None, it, 'converged to a folded root (lens map not invertible there)'
            return [x, y], it, None
        det = a * d - b * c
        if abs(det) < 1e-14:
            return None, it, 'singular Jacobian'
        sx = (d * rx - b * ry) / det
        sy = (-c * rx + a * ry) / det
        lam = 1.0
        for _ in range(30):
            nx, ny = x - lam * sx, y - lam * sy
            gx, gy = _distort(nx, ny, *co)
            if math.hypot(gx - xd, gy - yd) < res:
                break
            lam *= 0.5
        else:
            return None, it, 'no descent step (no solution nearby)'
        x, y = nx, ny
        if not (math.isfinite(x) and math.isfinite(y)) or math.hypot(x, y) > 100:
            return None, it, 'diverged'
    return None, max_iter, 'max_iter reached without convergence'


def lens_distortion(action='roundtrip', points=None, grid_size=9, grid_extent=1.0,
                    k1=0.0, k2=0.0, k3=0.0, p1=0.0, p2=0.0, max_iter=50, tol=1e-12):
    """Brown-Conrady (OpenCV convention) in normalised image coordinates.

    distort: xd = x R + 2 p1 x y + p2 (r^2 + 2x^2), yd = y R + p1 (r^2 + 2y^2) + 2 p2 x y,
    R = 1 + k1 r^2 + k2 r^4 + k3 r^6. undistort: damped Newton per point;
    a point is reported non-converged (point None, with reason) if the
    residual does not fall below tol*(1+|pd|) within max_iter, or if the root
    lies in a folded region (R <= 0 or det J <= 0). roundtrip: distort then
    undistort the given points (or a grid_size^2 grid over [-extent, extent]^2)
    and report max/mean error. Coordinates are normalised (x/z), not pixels.
    """
    action = _choice('action', action, {'distort', 'undistort', 'roundtrip'})
    co = (_num('k1', k1, -10, 10), _num('k2', k2, -10, 10), _num('k3', k3, -10, 10),
          _num('p1', p1, -1, 1), _num('p2', p2, -1, 1))
    max_iter = _int('max_iter', max_iter, 1, 200)
    tol = _num('tol', tol, 1e-15, 1e-3)
    gs = _int('grid_size', grid_size, 2, 101)
    ext = _num('grid_extent', grid_extent, 1e-6, 10.0)
    if points is None:
        pts = [[-ext + 2 * ext * i / (gs - 1), -ext + 2 * ext * j / (gs - 1)]
               for j in range(gs) for i in range(gs)]
    else:
        pts = _points('points', points, {2}, 1, MAX_POINTS, -10, 10)
    if action == 'distort':
        return {'points': [list(_distort(x, y, *co)) for x, y in pts], 'count': len(pts)}
    if action == 'undistort':
        res = [_undistort(x, y, co, max_iter, tol) for x, y in pts]
        return {'points': [r[0] for r in res], 'converged': [r[0] is not None for r in res],
                'reasons': [r[2] for r in res], 'iterations_max': max(r[1] for r in res),
                'non_converged': sum(1 for r in res if r[0] is None), 'count': len(pts)}
    errs, bad = [], 0
    for x, y in pts:
        xd, yd = _distort(x, y, *co)
        u, _, _ = _undistort(xd, yd, co, max_iter, tol)
        if u is None:
            bad += 1
        else:
            errs.append(math.hypot(u[0] - x, u[1] - y))
    return {'count': len(pts), 'non_converged': bad,
            'max_error': max(errs) if errs else None,
            'mean_error': sum(errs) / len(errs) if errs else None}


# --------------------------------------------------------------------------
# registry
# --------------------------------------------------------------------------

TOPICS = {'05.01': 'transform', '05.02': 'perspective', '05.03': 'curves',
          '05.04': 'aspect_fit', '05.05': 'depth_of_field', '05.06': 'ik_two_bone',
          '05.07': 'camera_path', '05.08': 'homography', '05.09': 'timecode',
          '05.10': 'lens_distortion'}

OPS = {'transform': transform, 'perspective': perspective, 'curves': curves,
       'aspect_fit': aspect_fit, 'depth_of_field': depth_of_field,
       'ik_two_bone': ik_two_bone, 'camera_path': camera_path, 'homography': homography,
       'timecode': timecode, 'lens_distortion': lens_distortion}

_NOTES = {
    'transform': (['row-major matrices acting on column vectors', 'steps apply in list order',
                   'angles in degrees, 2D rotation counter-clockwise'],
                  ['affine only (projective matrices rejected)', 'singular threshold 1e-12 relative',
                   'max 64 steps, 10000 points']),
    'perspective': (['camera at origin looking +Z, +Y up', 'square pixels, aspect = width/height',
                     'ideal pinhole, no lens distortion'],
                    ['points with z <= near are flagged, not projected',
                     'edge stretch is the small-object radial/tangential ratio 1/cos(theta)']),
    'curves': (['Catmull-Rom tangents are derivatives w.r.t. the global knot parameter',
                'end tangents from reflected phantom points'],
               ['arc length from a chord table (table_size samples)',
                'constant speed accurate to table resolution', 'max 256 control points']),
    'aspect_fit': (['focus box in source pixels [x, y, w, h]', 'safe areas centred on the output frame'],
                   ['even-integer rounding can change crop aspect slightly (crop_aspect_error)',
                    'no upscaling quality judgement']),
    'depth_of_field': (['thin-lens model, distances from the lens', 'CoC chosen by the caller'],
                       ['ignores pupil magnification, focus breathing and diffraction',
                        'infinite far limit is null in JSON output (far_is_infinite = true)']),
    'ik_two_bone': (['2D only', 'elbow side relative to root->target direction'],
                    ['no joint angle limits', 'unreachable targets clamped and flagged']),
    'camera_path': (['min-jerk segments stop at every keyframe', 'metrics from finite differences at fps'],
                    ['shake windowed over whole path; intermediate keys not exact with shake',
                     'max 20000 samples, 64 keyframes']),
    'homography': (['pinhole views of a plane or pure rotation', 'point pairs correspond correctly'],
                   ['algebraic least squares, no RANSAC/outlier rejection',
                    'collinear or non-unique sets rejected', 'max 500 pairs']),
    'timecode': (['exact rational fps', 'frame n starts at n/fps seconds'],
                 ['drop-frame only for 30000/1001 and 60000/1001', 'timecode limited to < 24 h, no wrap',
                  'floats rejected for fps']),
    'lens_distortion': (['Brown-Conrady, OpenCV coefficient convention', 'normalised coordinates, not pixels'],
                        ['undistort may fail for strong distortion; reported per point, never guessed',
                         'max 10000 points, max 200 iterations']),
}


def _jsonable(v):
    if isinstance(v, float):
        return v if math.isfinite(v) else None
    if isinstance(v, Fraction):
        return f'{v.numerator}/{v.denominator}'
    if isinstance(v, dict):
        return {str(k): _jsonable(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_jsonable(x) for x in v]
    return v


def run(op, params=None):
    """Validate and dispatch an op by name; return a JSON-serialisable envelope."""
    if not isinstance(op, str) or op not in OPS:
        raise ValueError(f'unknown op; choose one of {sorted(OPS)}')
    if params is None:
        params = {}
    if not isinstance(params, dict) or len(params) > MAX_PARAMS:
        raise ValueError(f'params must be a dict with at most {MAX_PARAMS} keys')
    fn = OPS[op]
    allowed = set(inspect.signature(fn).parameters)
    bad = [k for k in params if not isinstance(k, str) or k not in allowed]
    if bad:
        raise ValueError(f'unknown parameter(s) for {op}: {sorted(map(str, bad))}')
    result = fn(**params)
    assumptions, limits = _NOTES[op]
    return {'op': op, 'result': _jsonable(result), 'assumptions': list(assumptions),
            'limits': list(limits)}
