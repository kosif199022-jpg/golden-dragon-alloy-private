"""Red Rose V27: native motion core (easing, keyframe tracks, transitions, camera moves).

Original Red Rose code that re-implements *ideas* from legacy motion families
(EASE, TRANS, CAM); nothing is imported or copied from legacy engines.

Pure standard-library Python. No file I/O, no subprocess, no network, no printing.
Deterministic: every random choice is seeded. Every op validates its inputs
strictly (ValueError on bools-as-numbers, non-finite values, unknown parameter
names and out-of-range values) and returns JSON-serialisable data.

Conventions
-----------
* Easing input t and transition progress p are clamped to [0, 1].
* Transition translate values are fractions of the frame (1.0 = full width or
  height); clip geometry is in frame fractions; blur values are Gaussian
  standard deviations in px at a 1080 px high reference frame and are scaled by
  height / 1080 when SVG is composed.
* Camera tx/ty/blur are px at the camera's own width/height. The camera maps a
  point x to rotate(rotate_deg about frame centre)(scale * x + (tx, ty)).
* SVG output approximates editing-app effects with <clipPath>, <mask>,
  transform, opacity and SVG filters; there is no GPU path.
"""
from __future__ import annotations

import bisect
import json
import math
import random
import re

MAX_PARAMS = 24
MAX_SAMPLES = 10_001
MAX_KEYS = 1_000
MAX_SVG_CHARS = 4_000_000
MAX_DIM = 16_384

# --------------------------------------------------------------------------- validation


def _no_extra(extra, where=''):
    if extra:
        prefix = f'{where}: ' if where else ''
        raise ValueError(prefix + 'unknown parameter(s): ' + ', '.join(sorted(map(str, extra))))


def _num(value, low, high, name, *, low_open=False):
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value)):
        raise ValueError(f'{name} must be a finite number')
    value = float(value)
    if value < low or value > high or (low_open and value <= low):
        bracket = '(' if low_open else '['
        raise ValueError(f'{name} must be in {bracket}{low}, {high}]')
    return value


def _int(value, low, high, name):
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise ValueError(f'{name} must be an integer from {low} to {high}')
    return value


def _bool(value, name):
    if not isinstance(value, bool):
        raise ValueError(f'{name} must be true or false')
    return value


def _choice(value, options, name):
    if not isinstance(value, str) or value not in options:
        raise ValueError(f'{name} must be one of {sorted(options)}')
    return value


def _str(value, name, max_len=MAX_SVG_CHARS):
    if not isinstance(value, str) or len(value) > max_len:
        raise ValueError(f'{name} must be a string of at most {max_len} characters')
    return value


_HEX_RE = re.compile(r'^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$')
_ID_RE = re.compile(r'^[A-Za-z][A-Za-z0-9_-]{0,40}$')
_NAME_RE = re.compile(r'^[A-Za-z0-9_-]{1,40}$')


def _colour(value, name):
    if not isinstance(value, str) or not _HEX_RE.match(value):
        raise ValueError(f'{name} must be a hex colour like #rrggbb or #rgb')
    h = value[1:].lower()
    if len(h) == 3:
        h = ''.join(c * 2 for c in h)
    return '#' + h


def _pack(op, result, assumptions, limits):
    return {'op': op, 'result': result, 'assumptions': list(assumptions),
            'limits': list(limits)}


def _clamp(x, lo=0.0, hi=1.0):
    return lo if x < lo else hi if x > hi else x


def _lerp(a, b, t):
    return a + (b - a) * t


def _f(v):
    """Compact SVG number formatting."""
    if abs(v) < 1e-9:
        return '0'
    s = f'{v:.4f}'.rstrip('0').rstrip('.')
    return '0' if s in ('-0', '') else s


# Option specs: name -> tuple(kind, default, *args)
#   ('num', default, low, high)       ('int', default, low, high)
#   ('bool', default)                 ('colour', default)
#   ('choice', default, options)      ('nums', default, low, high, min_len, max_len)
#   ('names', default, min_len, max_len)   ('ease', default)

def _opt(spec, value, name):
    kind = spec[0]
    if kind == 'num':
        return _num(value, spec[2], spec[3], name)
    if kind == 'int':
        return _int(value, spec[2], spec[3], name)
    if kind == 'bool':
        return _bool(value, name)
    if kind == 'colour':
        return _colour(value, name)
    if kind == 'choice':
        return _choice(value, spec[2], name)
    if kind == 'nums':
        low, high, nmin, nmax = spec[2], spec[3], spec[4], spec[5]
        if not isinstance(value, (list, tuple)) or not nmin <= len(value) <= nmax:
            raise ValueError(f'{name} must be a list of {nmin}..{nmax} numbers')
        return [_num(v, low, high, f'{name}[{i}]') for i, v in enumerate(value)]
    if kind == 'names':
        nmin, nmax = spec[2], spec[3]
        if not isinstance(value, (list, tuple)) or not nmin <= len(value) <= nmax:
            raise ValueError(f'{name} must be a list of {nmin}..{nmax} names')
        out = []
        for i, v in enumerate(value):
            if not isinstance(v, str) or not _NAME_RE.match(v):
                raise ValueError(f'{name}[{i}] must match [A-Za-z0-9_-]{{1,40}}')
            out.append(v)
        if len(set(out)) != len(out):
            raise ValueError(f'{name} must not contain duplicates')
        return out
    if kind == 'ease':
        return _easer(value, name)
    raise AssertionError(kind)


def _opts(spec, given, where):
    if not isinstance(given, dict):
        raise ValueError(f'{where}: options must be a dict')
    unknown = [k for k in given if k not in spec]
    _no_extra(unknown, where)
    out = {}
    for key, s in spec.items():
        value = given[key] if key in given else s[1]
        if isinstance(value, list):
            value = list(value)
        out[key] = _opt(s, value, f'{where}.{key}' if where else key)
    return out


# --------------------------------------------------------------------------- easing


def _expo_in(t, **_):
    return 0.0 if t <= 0 else 2.0 ** (10.0 * t - 10.0)


def _circ_in(t, **_):
    return 1.0 - math.sqrt(max(0.0, 1.0 - t * t))


def _back_in(t, overshoot=1.70158, **_):
    s = overshoot
    return t * t * ((s + 1.0) * t - s)


def _elastic_in(t, amplitude=1.0, period=0.3, **_):
    if t <= 0:
        return 0.0
    if t >= 1:
        return 1.0
    a = max(1.0, amplitude)
    s = period / (2.0 * math.pi) * math.asin(1.0 / a)
    return -(a * 2.0 ** (10.0 * (t - 1.0)) * math.sin((t - 1.0 - s) * 2.0 * math.pi / period))


def _bounce_out(t):
    n1, d1 = 7.5625, 2.75
    if t < 1.0 / d1:
        return n1 * t * t
    if t < 2.0 / d1:
        t -= 1.5 / d1
        return n1 * t * t + 0.75
    if t < 2.5 / d1:
        t -= 2.25 / d1
        return n1 * t * t + 0.9375
    t -= 2.625 / d1
    return n1 * t * t + 0.984375


def _bounce_in(t, **_):
    return 1.0 - _bounce_out(1.0 - t)


def _bezier(t, x1=0.25, y1=0.1, x2=0.25, y2=1.0, **_):
    """CSS-style cubic-bezier: solve x(u) = t by Newton, fall back to bisection."""
    if t <= 0:
        return 0.0
    if t >= 1:
        return 1.0
    cx = 3.0 * x1
    bx = 3.0 * (x2 - x1) - cx
    ax = 1.0 - cx - bx
    cy = 3.0 * y1
    by = 3.0 * (y2 - y1) - cy
    ay = 1.0 - cy - by

    def sx(u):
        return ((ax * u + bx) * u + cx) * u

    def sy(u):
        return ((ay * u + by) * u + cy) * u

    def dsx(u):
        return (3.0 * ax * u + 2.0 * bx) * u + cx

    u = t
    for _ in range(8):
        err = sx(u) - t
        if abs(err) < 1e-7 and 0.0 <= u <= 1.0:
            return sy(u)
        d = dsx(u)
        if abs(d) < 1e-6:
            break
        u -= err / d
    lo, hi, u = 0.0, 1.0, t
    for _ in range(64):
        x = sx(u)
        if abs(x - t) < 1e-9:
            break
        if x < t:
            lo = u
        else:
            hi = u
        u = 0.5 * (lo + hi)
    return sy(u)


def _spring_x(T, k, c, m):
    """Analytic displacement of a unit step response: x(0)=1, v(0)=0, target 0."""
    if T <= 0:
        return 1.0
    wn = math.sqrt(k / m)
    zeta = c / (2.0 * math.sqrt(k * m))
    if zeta < 1.0 - 1e-6:
        wd = wn * math.sqrt(1.0 - zeta * zeta)
        return math.exp(-zeta * wn * T) * (math.cos(wd * T) + zeta * wn / wd * math.sin(wd * T))
    if zeta <= 1.0 + 1e-6:
        return (1.0 + wn * T) * math.exp(-wn * T)
    root = math.sqrt(zeta * zeta - 1.0)
    r1 = -wn * (zeta - root)
    r2 = -wn * (zeta + root)
    return (r2 * math.exp(r1 * T) - r1 * math.exp(r2 * T)) / (r2 - r1)


def _spring_ease(t, stiffness=100.0, damping=10.0, mass=1.0, duration=1.0, **_):
    return 1.0 - _spring_x(t * duration, stiffness, damping, mass)


def _step(t, n=5, **_):
    return 1.0 if t >= 1 else math.floor(t * n) / n


_FAMILIES = {
    'sine': (lambda t, **_: 1.0 - math.cos(t * math.pi / 2.0), {}, 'جيبية ناعمة'),
    'quad': (lambda t, **_: t * t, {}, 'تربيعية'),
    'cubic': (lambda t, **_: t * t * t, {}, 'تكعيبية'),
    'quart': (lambda t, **_: t ** 4, {}, 'من الدرجة الرابعة'),
    'quint': (lambda t, **_: t ** 5, {}, 'من الدرجة الخامسة'),
    'expo': (_expo_in, {}, 'أُسّية حادة'),
    'circ': (_circ_in, {}, 'دائرية'),
    'back': (_back_in, {'overshoot': ('num', 1.70158, 0.0, 10.0)}, 'بتراجع وتجاوز للهدف'),
    'elastic': (_elastic_in, {'amplitude': ('num', 1.0, 1.0, 10.0),
                              'period': ('num', 0.3, 0.05, 2.0)}, 'مطاطية متذبذبة'),
    'bounce': (_bounce_in, {}, 'بنطّات ارتداد'),
}

_DIR_AR = {
    'in': 'تبدأ ببطء وتتسارع',
    'out': 'تبدأ بسرعة وتهدأ في النهاية',
    'in_out': 'هادئة في البداية والنهاية وسريعة في المنتصف',
}


def _dir_fn(fin, direction):
    if direction == 'in':
        return fin
    if direction == 'out':
        return lambda t, **o: 1.0 - fin(1.0 - t, **o)
    return lambda t, **o: (fin(2.0 * t, **o) / 2.0 if t < 0.5
                           else 1.0 - fin(2.0 - 2.0 * t, **o) / 2.0)


EASINGS = {
    'linear': {'fn': lambda t, **_: t, 'opts': {}, 'ar': 'حركة بسرعة ثابتة من غير تسارع'},
    'step': {'fn': _step, 'opts': {'n': ('int', 5, 1, 1000)},
             'ar': 'قفزات متقطعة بعدد n من الدرجات'},
    'smoothstep': {'fn': lambda t, **_: t * t * (3.0 - 2.0 * t), 'opts': {},
                   'ar': 'منحنى ناعم كلاسيكي بداية ونهاية هادئة'},
    'smootherstep': {'fn': lambda t, **_: t * t * t * (t * (6.0 * t - 15.0) + 10.0), 'opts': {},
                     'ar': 'منحنى أنعم من smoothstep بتسارع متصل'},
}
for _fam, (_fin, _fopts, _far) in _FAMILIES.items():
    for _d in ('in', 'out', 'in_out'):
        EASINGS[f'{_fam}_{_d}'] = {'fn': _dir_fn(_fin, _d), 'opts': dict(_fopts),
                                   'ar': f'حركة {_far} {_DIR_AR[_d]}'}
EASINGS['cubic_bezier'] = {
    'fn': _bezier,
    'opts': {'x1': ('num', 0.25, 0.0, 1.0), 'y1': ('num', 0.1, -2.0, 3.0),
             'x2': ('num', 0.25, 0.0, 1.0), 'y2': ('num', 1.0, -2.0, 3.0)},
    'ar': 'منحنى بيزييه مكعب مخصص بنقطتين تحكم زي CSS',
}
EASINGS['spring'] = {
    'fn': _spring_ease,
    'opts': {'stiffness': ('num', 100.0, 0.01, 1e5), 'damping': ('num', 10.0, 0.0, 1e4),
             'mass': ('num', 1.0, 0.001, 1e3), 'duration': ('num', 1.0, 0.01, 60.0)},
    'ar': 'زنبرك فيزيائي محسوب تحليليًا بصلابة وتخميد وكتلة',
}
del _fam, _fin, _fopts, _far, _d


def _easer(spec, name='ease', allow_hold=False):
    """Validate an ease spec (name or {'name': ..., **opts}) and return t -> value."""
    if isinstance(spec, str):
        ename, eopts = spec, {}
    elif isinstance(spec, dict):
        eopts = dict(spec)
        ename = eopts.pop('name', None)
    else:
        raise ValueError(f'{name} must be an easing name or {{"name": ..., options}}')
    if allow_hold and ename == 'hold':
        if eopts:
            raise ValueError(f'{name}: hold takes no options')
        return None
    _choice(ename, EASINGS, name)
    o = _opts(EASINGS[ename]['opts'], eopts, f'{name}:{ename}')
    fn = EASINGS[ename]['fn']
    return lambda t: float(fn(_clamp(t), **o))


def ease(name, t, **opts):
    """Evaluate easing `name` at t (clamped to [0, 1]) with its options."""
    _choice(name, EASINGS, 'name')
    t = _num(t, -1e9, 1e9, 't')
    o = _opts(EASINGS[name]['opts'], opts, name)
    return float(EASINGS[name]['fn'](_clamp(t), **o))


# --------------------------------------------------------------------------- colour + tracks


def _srgb_to_lin(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _lin_to_srgb(c):
    c = _clamp(c)
    return c * 12.92 if c <= 0.0031308 else 1.055 * c ** (1.0 / 2.4) - 0.055


def _hex_to_lin(hexstr):
    h = hexstr[1:]
    return [_srgb_to_lin(int(h[i:i + 2], 16) / 255.0) for i in (0, 2, 4)]


def _lin_to_hex(rgb):
    return '#' + ''.join(f'{int(round(_lin_to_srgb(c) * 255.0)):02x}' for c in rgb)


def _key_value(v, name):
    if isinstance(v, str):
        return 'colour', _hex_to_lin(_colour(v, name))
    if isinstance(v, (list, tuple)):
        if len(v) != 2:
            raise ValueError(f'{name} point must have 2 numbers')
        return 'point', [_num(c, -1e9, 1e9, f'{name}[{i}]') for i, c in enumerate(v)]
    return 'number', _num(v, -1e12, 1e12, name)


def _prepare_track(keys):
    if not isinstance(keys, (list, tuple)) or not 1 <= len(keys) <= MAX_KEYS:
        raise ValueError(f'keys must be a list of 1..{MAX_KEYS} key dicts')
    kind, ts, vals, easers, holds = None, [], [], [], []
    for i, k in enumerate(keys):
        where = f'keys[{i}]'
        if not isinstance(k, dict):
            raise ValueError(f'{where} must be a dict')
        _no_extra([x for x in k if x not in ('t', 'value', 'ease', 'hold')], where)
        if 't' not in k or 'value' not in k:
            raise ValueError(f'{where} needs t and value')
        t = _num(k['t'], -1e9, 1e9, f'{where}.t')
        if ts and t <= ts[-1]:
            raise ValueError('key times must be strictly increasing')
        kk, v = _key_value(k['value'], f'{where}.value')
        if kind is None:
            kind = kk
        elif kk != kind:
            raise ValueError(f'{where}.value is a {kk} but earlier keys are {kind}s')
        ez = _easer(k.get('ease', 'linear'), f'{where}.ease', allow_hold=True)
        hold = _bool(k.get('hold', False), f'{where}.hold') or ez is None
        ts.append(t)
        vals.append(v)
        easers.append(ez)
        holds.append(hold)
    return kind, ts, vals, easers, holds


def _sample_prepared(prep, t):
    kind, ts, vals, easers, holds = prep
    if t <= ts[0]:
        v = vals[0]
    elif t >= ts[-1]:
        v = vals[-1]
    else:
        i = bisect.bisect_right(ts, t) - 1
        if holds[i]:
            v = vals[i]
        else:
            u = (t - ts[i]) / (ts[i + 1] - ts[i])
            e = easers[i](u)
            a, b = vals[i], vals[i + 1]
            v = _lerp(a, b, e) if kind == 'number' else [_lerp(x, y, e) for x, y in zip(a, b)]
    if kind == 'colour':
        return _lin_to_hex(v)
    if kind == 'point':
        return [float(c) for c in v]
    return float(v)


def sample_track(keys, t):
    """Sample a keyframe track at time t.

    keys: [{'t': seconds, 'value': number | [x, y] | '#rrggbb', 'ease': spec, 'hold': bool}]
    The ease/hold of key i governs the segment from key i to key i+1. Colours
    are interpolated in linear RGB and returned as hex; values before the first
    key / after the last key hold the end values.
    """
    prep = _prepare_track(keys)
    return _sample_prepared(prep, _num(t, -1e9, 1e9, 't'))


def frames_for(duration_s, fps):
    """Frame start times i / fps for round(duration_s * fps) frames (at least 1)."""
    duration_s = _num(duration_s, 0, 86_400, 'duration_s', low_open=True)
    fps = _num(fps, 1, 240, 'fps')
    n = max(1, int(round(duration_s * fps)))
    if n > MAX_SAMPLES * 10:
        raise ValueError(f'too many frames ({n}); limit {MAX_SAMPLES * 10}')
    return [i / fps for i in range(n)]


# --------------------------------------------------------------------------- transitions


def _cs(opacity=1.0, tx=0.0, ty=0.0, scale=1.0, rotate=0.0, clip=None, blur=0.0,
        mbx=0.0, mby=0.0, brightness=1.0):
    return {'opacity': float(_clamp(opacity)),
            'transform': {'translate': [float(tx), float(ty)], 'scale': float(max(0.0, scale)),
                          'rotate': float(rotate), 'origin': [0.5, 0.5]},
            'clip': clip,
            'filter': {'blur': float(max(0.0, blur)),
                       'motion_blur': [float(abs(mbx)), float(abs(mby))],
                       'brightness': float(max(0.0, brightness))}}


_DIRS = {'left': (-1.0, 0.0), 'right': (1.0, 0.0), 'up': (0.0, -1.0), 'down': (0.0, 1.0)}


def _rect(x, y, w, h):
    return {'type': 'rect', 'x': float(x), 'y': float(y), 'w': float(max(0.0, w)),
            'h': float(max(0.0, h))}


def _halfplane_square(a, b, c):
    """Clip the unit square to a*x + b*y <= c (Sutherland-Hodgman)."""
    pts = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
    out = []
    for i, cur in enumerate(pts):
        prev = pts[i - 1]
        dc = a * cur[0] + b * cur[1] - c
        dp = a * prev[0] + b * prev[1] - c
        if dc <= 0:
            if dp > 0:
                s = dp / (dp - dc)
                out.append((prev[0] + s * (cur[0] - prev[0]), prev[1] + s * (cur[1] - prev[1])))
            out.append(cur)
        elif dp <= 0:
            s = dp / (dp - dc)
            out.append((prev[0] + s * (cur[0] - prev[0]), prev[1] + s * (cur[1] - prev[1])))
    return [[float(x), float(y)] for x, y in out]


def _t_crossfade(p, ez, o):
    return {'a': _cs(1.0), 'b': _cs(ez(p))}


def _t_dip(p, ez, o):
    if o['at_film_start']:
        raise ValueError('dip_to_colour is not allowed at the very first frame of a film '
                         '(at_film_start=True); start on picture instead')
    if p < 0.5:
        a, b = _cs(1.0 - ez(2.0 * p)), _cs(0.0)
    else:
        a, b = _cs(0.0), _cs(ez(2.0 * p - 1.0))
    return {'a': a, 'b': b, 'background': o['colour']}


def _wipe(direction):
    def fn(p, ez, o):
        e = _clamp(ez(p))
        clip = {'left': _rect(1.0 - e, 0, e, 1), 'right': _rect(0, 0, e, 1),
                'up': _rect(0, 1.0 - e, 1, e), 'down': _rect(0, 0, 1, e)}[direction]
        return {'a': _cs(1.0), 'b': _cs(1.0, clip=clip)}
    return fn


def _t_diagonal(p, ez, o):
    e = ez(p)
    pts = _halfplane_square(1.0, 1.0, 2.0 * e)
    clip = None if e >= 1.0 else {'type': 'polygon', 'points': pts}
    return {'a': _cs(1.0), 'b': _cs(1.0, clip=clip)}


def _t_iris_open(p, ez, o):
    r = max(0.0, ez(p))
    clip = None if r >= 1.0 else {'type': 'circle', 'cx': o['cx'], 'cy': o['cy'],
                                  'r': float(r * (1.0 + 2.0 * max(abs(o['cx'] - 0.5),
                                                                  abs(o['cy'] - 0.5))))}
    return {'a': _cs(1.0), 'b': _cs(1.0, clip=clip)}


def _t_iris_close(p, ez, o):
    r = max(0.0, 1.0 - ez(p))
    clip = {'type': 'circle', 'cx': o['cx'], 'cy': o['cy'],
            'r': float(r * (1.0 + 2.0 * max(abs(o['cx'] - 0.5), abs(o['cy'] - 0.5))))}
    return {'a': _cs(1.0 if r > 0 else 0.0, clip=clip), 'b': _cs(1.0), 'order': ['b', 'a']}


def _t_clock(p, ez, o):
    e = ez(p)
    if e >= 1.0:
        clip = None
    elif e <= 0.0:
        clip = {'type': 'polygon', 'points': []}
    else:
        theta = 360.0 * e
        n = max(2, int(math.ceil(theta / 5.0)))
        pts = [[0.5, 0.5]]
        for k in range(n + 1):
            ang = math.radians(-90.0 + theta * k / n)
            pts.append([0.5 + math.cos(ang), 0.5 + math.sin(ang)])
        clip = {'type': 'polygon', 'points': [[float(x), float(y)] for x, y in pts]}
    return {'a': _cs(1.0), 'b': _cs(1.0, clip=clip)}


def _push(direction):
    dx, dy = _DIRS[direction]

    def fn(p, ez, o):
        e = ez(p)
        return {'a': _cs(1.0, tx=dx * e, ty=dy * e), 'b': _cs(1.0, tx=dx * (e - 1.0), ty=dy * (e - 1.0))}
    return fn


def _t_zoom_in(p, ez, o):
    e = ez(p)
    z, blur = o['zoom'], o['max_blur'] * math.sin(math.pi * _clamp(e))
    return {'a': _cs(1.0 - e, scale=_lerp(1.0, z, e), blur=blur),
            'b': _cs(e, scale=_lerp(1.0 / z, 1.0, e), blur=blur)}


def _t_zoom_out(p, ez, o):
    e = ez(p)
    z, blur = o['zoom'], o['max_blur'] * math.sin(math.pi * _clamp(e))
    return {'a': _cs(1.0, scale=_lerp(1.0, 1.0 / z, e), blur=blur),
            'b': _cs(e, scale=_lerp(z, 1.0, e), blur=blur)}


def _t_whip(p, ez, o):
    dx, dy = _DIRS[o['direction']]
    e = ez(p)
    mb = o['max_blur'] * math.sin(math.pi * _clamp(e))
    mbx, mby = abs(dx) * mb, abs(dy) * mb
    return {'a': _cs(1.0, tx=dx * e, ty=dy * e, mbx=mbx, mby=mby),
            'b': _cs(1.0, tx=dx * (e - 1.0), ty=dy * (e - 1.0), mbx=mbx, mby=mby),
            'hints': {'motion_blur_axis': 'x' if dx else 'y', 'motion_blur_px_1080': float(mb)}}


def _t_spin(p, ez, o):
    e = ez(p)
    ang, ms = o['angle'], o['min_scale']
    return {'a': _cs(1.0 - e, rotate=ang * e, scale=_lerp(1.0, ms, e)),
            'b': _cs(e, rotate=-ang * (1.0 - e), scale=_lerp(ms, 1.0, e))}


def _t_glitch(p, ez, o):
    n = o['slices']
    rng = random.Random(o['seed'] * 7_919 + 17)
    heights = [0.3 + rng.random() for _ in range(n)]
    total = sum(heights)
    order = list(range(n))
    rng.shuffle(order)
    thresholds = [0.0] * n
    for rank, idx in enumerate(order):
        thresholds[idx] = (rank + rng.random()) / n
    bucket = int(_clamp(p) * o['jitter_steps'])
    jr = random.Random(o['seed'] * 104_729 + bucket * 1_299_709 + 3)
    env = math.sin(math.pi * _clamp(p))
    e = ez(p)
    rects, a_off, b_rects, b_off = [], [], [], []
    y = 0.0
    for i in range(n):
        h = heights[i] / total
        rect = [0.0, float(y), 1.0, float(h)]
        y += h
        dx_a = o['amplitude'] * env * (jr.random() * 2.0 - 1.0)
        dx_b = o['amplitude'] * env * (jr.random() * 2.0 - 1.0)
        rects.append(rect)
        a_off.append([float(dx_a), 0.0])
        if e >= thresholds[i]:
            b_rects.append(rect)
            b_off.append([float(dx_b), 0.0])
    flick = 1.0 + 0.4 * env * jr.random()
    return {'a': _cs(1.0, clip={'type': 'stripes', 'rects': rects, 'offsets': a_off},
                     brightness=flick),
            'b': _cs(1.0, clip={'type': 'stripes', 'rects': b_rects, 'offsets': b_off},
                     brightness=flick),
            'hints': {'jitter_bucket': bucket}}


def _t_blinds(p, ez, o):
    n = o['slats']
    e = _clamp(ez(p))
    rects = []
    for i in range(n):
        if o['orientation'] == 'horizontal':
            rects.append([0.0, i / n, 1.0, e / n])
        else:
            rects.append([i / n, 0.0, e / n, 1.0])
    return {'a': _cs(1.0), 'b': _cs(1.0, clip={'type': 'stripes', 'rects': rects,
                                               'offsets': [[0.0, 0.0]] * n})}


def _t_checker(p, ez, o):
    cols, rows, stagger = o['cols'], o['rows'], o['stagger']
    e = _clamp(ez(p))
    span = max(1, cols + rows - 2)
    rects = []
    for j in range(rows):
        for i in range(cols):
            delay = stagger * (i + j) / span
            local = _clamp((e - delay) / (1.0 - stagger))
            if local <= 0:
                continue
            w, h = local / cols, local / rows
            rects.append([(i + 0.5) / cols - w / 2.0, (j + 0.5) / rows - h / 2.0, w, h])
    return {'a': _cs(1.0), 'b': _cs(1.0, clip={'type': 'rects', 'rects': rects,
                                               'offsets': [[0.0, 0.0]] * len(rects)})}


def _t_luma(p, ez, o):
    e = _clamp(ez(p))
    soft = o['softness']
    return {'a': _cs(1.0), 'b': _cs(1.0, clip={'type': 'luma', 'source': 'a',
                                               'threshold': float(e * (1.0 + soft)),
                                               'softness': soft, 'invert': o['invert']})}


def _t_morph(p, ez, o):
    e = ez(p)
    size = _clamp(_lerp(o['start_size'], 1.0, e))
    clip = None if size >= 1.0 else _rect(0.5 - size / 2.0, 0.5 - size / 2.0, size, size)
    return {'a': _cs(1.0, scale=_lerp(1.0, 1.08, e), brightness=_lerp(1.0, 0.7, _clamp(e))),
            'b': _cs(_clamp(e / 0.25), scale=_lerp(1.15, 1.0, e), clip=clip)}


def _t_flash(p, ez, o):
    cut, width = o['cut_at'], o['width']
    x = _clamp(1.0 - abs(p - cut) / width)
    env = x * x * (3.0 - 2.0 * x)
    br = 1.0 + o['strength'] * env
    before = p < cut
    return {'a': _cs(1.0 if before else 0.0, brightness=br),
            'b': _cs(0.0 if before else 1.0, brightness=br),
            'background': '#ffffff', 'hints': {'cut_at': cut}}


def _t_split(p, ez, o):
    e = ez(p)
    if o['orientation'] == 'vertical':
        rects = [[0.0, 0.0, 0.5, 1.0], [0.5, 0.0, 0.5, 1.0]]
        offs = [[-0.5 * e, 0.0], [0.5 * e, 0.0]]
    else:
        rects = [[0.0, 0.0, 1.0, 0.5], [0.0, 0.5, 1.0, 0.5]]
        offs = [[0.0, -0.5 * e], [0.0, 0.5 * e]]
    offs = [[float(a), float(b)] for a, b in offs]
    return {'a': _cs(1.0 if e < 1.0 else 0.0, clip={'type': 'stripes', 'rects': rects,
                                                    'offsets': offs}),
            'b': _cs(1.0, scale=_lerp(1.12, 1.0, e), brightness=_lerp(0.7, 1.0, _clamp(e))),
            'order': ['b', 'a']}


def _t_page(p, ez, o):
    dx, dy = _DIRS[o['direction']]
    e = ez(p)
    return {'a': _cs(1.0, tx=dx * e * 0.25, ty=dy * e * 0.25, scale=_lerp(1.0, 0.92, e),
                     brightness=_lerp(1.0, 0.55, _clamp(e))),
            'b': _cs(1.0, tx=dx * (e - 1.0), ty=dy * (e - 1.0)),
            'hints': {'shadow_on': 'b'}}


_DIR_CHOICE = ('left', 'right', 'up', 'down')

TRANSITIONS = {
    'crossfade': {'fn': _t_crossfade, 'ease': 'sine_in_out', 'opts': {},
                  'ar': 'مزج ناعم بين اللقطتين'},
    'dip_to_colour': {'fn': _t_dip, 'ease': 'sine_in_out',
                      'opts': {'colour': ('colour', '#000000')},
                      'ar': 'تغميق للون ثم ظهور اللقطة الجديدة (ممنوع في أول فريم من الفيلم)'},
    'wipe_left': {'fn': _wipe('left'), 'ease': 'cubic_in_out', 'opts': {},
                  'ar': 'مسح من اليمين لليسار يكشف اللقطة الجديدة'},
    'wipe_right': {'fn': _wipe('right'), 'ease': 'cubic_in_out', 'opts': {},
                   'ar': 'مسح من اليسار لليمين يكشف اللقطة الجديدة'},
    'wipe_up': {'fn': _wipe('up'), 'ease': 'cubic_in_out', 'opts': {},
                'ar': 'مسح من تحت لفوق'},
    'wipe_down': {'fn': _wipe('down'), 'ease': 'cubic_in_out', 'opts': {},
                  'ar': 'مسح من فوق لتحت'},
    'diagonal_wipe': {'fn': _t_diagonal, 'ease': 'cubic_in_out', 'opts': {},
                      'ar': 'مسح قطري من الركن العلوي للركن السفلي'},
    'iris_open': {'fn': _t_iris_open, 'ease': 'quad_out',
                  'opts': {'cx': ('num', 0.5, 0.0, 1.0), 'cy': ('num', 0.5, 0.0, 1.0)},
                  'ar': 'دائرة بتتفتح من المركز تكشف اللقطة الجديدة'},
    'iris_close': {'fn': _t_iris_close, 'ease': 'quad_in',
                   'opts': {'cx': ('num', 0.5, 0.0, 1.0), 'cy': ('num', 0.5, 0.0, 1.0)},
                   'ar': 'دائرة بتقفل على اللقطة القديمة'},
    'clock_wipe': {'fn': _t_clock, 'ease': 'linear', 'opts': {},
                   'ar': 'مسح دائري زي عقرب الساعة'},
    'slide_push_left': {'fn': _push('left'), 'ease': 'cubic_in_out', 'opts': {},
                        'ar': 'اللقطة الجديدة بتزق القديمة لليسار'},
    'slide_push_right': {'fn': _push('right'), 'ease': 'cubic_in_out', 'opts': {},
                         'ar': 'اللقطة الجديدة بتزق القديمة لليمين'},
    'slide_push_up': {'fn': _push('up'), 'ease': 'cubic_in_out', 'opts': {},
                      'ar': 'اللقطة الجديدة بتزق القديمة لفوق'},
    'slide_push_down': {'fn': _push('down'), 'ease': 'cubic_in_out', 'opts': {},
                        'ar': 'اللقطة الجديدة بتزق القديمة لتحت'},
    'zoom_in': {'fn': _t_zoom_in, 'ease': 'expo_in_out',
                'opts': {'zoom': ('num', 1.6, 1.01, 8.0), 'max_blur': ('num', 10.0, 0.0, 80.0)},
                'ar': 'زووم لجوه مع ضباب حركة وظهور اللقطة الجديدة'},
    'zoom_out': {'fn': _t_zoom_out, 'ease': 'expo_in_out',
                 'opts': {'zoom': ('num', 1.6, 1.01, 8.0), 'max_blur': ('num', 10.0, 0.0, 80.0)},
                 'ar': 'زووم لبرّه واللقطة الجديدة بتصغر لمكانها'},
    'whip_pan': {'fn': _t_whip, 'ease': 'expo_in_out',
                 'opts': {'direction': ('choice', 'left', _DIR_CHOICE),
                          'max_blur': ('num', 40.0, 0.0, 200.0)},
                 'ar': 'حركة كاميرا خاطفة بضباب اتجاهي بين اللقطتين'},
    'spin': {'fn': _t_spin, 'ease': 'cubic_in_out',
             'opts': {'angle': ('num', 180.0, -1080.0, 1080.0),
                      'min_scale': ('num', 0.6, 0.05, 1.0)},
             'ar': 'دوران مع تصغير وتبديل اللقطتين'},
    'glitch_slices': {'fn': _t_glitch, 'ease': 'linear',
                      'opts': {'slices': ('int', 12, 2, 64), 'amplitude': ('num', 0.08, 0.0, 0.5),
                               'seed': ('int', 7, 0, 2 ** 31 - 1),
                               'jitter_steps': ('int', 12, 1, 240)},
                      'ar': 'شرائح جليتش متزحزحة بشكل عشوائي ثابت البذرة'},
    'blinds': {'fn': _t_blinds, 'ease': 'cubic_in_out',
               'opts': {'slats': ('int', 8, 2, 64),
                        'orientation': ('choice', 'horizontal', ('horizontal', 'vertical'))},
               'ar': 'ستارة شرائح بتتفتح'},
    'checker': {'fn': _t_checker, 'ease': 'quad_in_out',
                'opts': {'cols': ('int', 8, 2, 24), 'rows': ('int', 6, 2, 16),
                         'stagger': ('num', 0.6, 0.0, 0.95)},
                'ar': 'مربعات شطرنج بتظهر بالتتابع القطري'},
    'luma_fade': {'fn': _t_luma, 'ease': 'sine_in_out',
                  'opts': {'softness': ('num', 0.2, 0.01, 1.0), 'invert': ('bool', False)},
                  'ar': 'ظهور حسب إضاءة اللقطة القديمة: الغامق الأول'},
    'morph_scale': {'fn': _t_morph, 'ease': 'cubic_in_out',
                    'opts': {'start_size': ('num', 0.0, 0.0, 0.9)},
                    'ar': 'مستطيل بيكبر من المركز مع تكبير وتغميق اللقطة القديمة'},
    'flash_cut': {'fn': _t_flash, 'ease': 'linear',
                  'opts': {'cut_at': ('num', 0.5, 0.05, 0.95), 'width': ('num', 0.15, 0.01, 0.5),
                           'strength': ('num', 1.5, 0.0, 5.0)},
                  'ar': 'قطع مع وميض إضاءة قصير'},
    'split_open': {'fn': _t_split, 'ease': 'cubic_in_out',
                   'opts': {'orientation': ('choice', 'vertical', ('vertical', 'horizontal'))},
                   'ar': 'اللقطة القديمة بتتقسم نصين وتتفتح زي باب'},
    'page_slide': {'fn': _t_page, 'ease': 'quart_out',
                   'opts': {'direction': ('choice', 'left', _DIR_CHOICE)},
                   'ar': 'اللقطة الجديدة بتنزلق فوق القديمة زي صفحة'},
}

_COMMON_T_OPTS = {'at_film_start': ('bool', False)}


def transition_frame(name, p, **opts):
    """Per-clip render params for transition `name` at progress p in [0, 1]."""
    _choice(name, TRANSITIONS, 'name')
    p = _clamp(_num(p, -1e9, 1e9, 'p'))
    entry = TRANSITIONS[name]
    spec = dict(_COMMON_T_OPTS)
    spec['ease'] = ('ease', entry['ease'])
    spec.update(entry['opts'])
    o = _opts(spec, opts, name)
    ez = o['ease']
    out = entry['fn'](p, ez, o)
    return {
        'name': name, 'p': p, 'eased': ez(p),
        'ease': opts.get('ease', entry['ease']),
        'order': out.get('order', ['a', 'b']),
        'background': out.get('background', '#000000'),
        'a': out['a'], 'b': out['b'],
        'hints': out.get('hints', {}),
    }


_ID_COUNTER = [0]


def _fnv(text):
    h = 0x811C9DC5
    for byte in text.encode('utf-8'):
        h = ((h ^ byte) * 0x01000193) & 0xFFFFFFFF
    return h


def _prefix(id_prefix, seed_text):
    if id_prefix is not None:
        if not isinstance(id_prefix, str) or not _ID_RE.match(id_prefix):
            raise ValueError('id_prefix must match [A-Za-z][A-Za-z0-9_-]{0,40}')
        return id_prefix
    _ID_COUNTER[0] += 1
    return f'rr{_fnv(seed_text):08x}n{_ID_COUNTER[0]}'


def _filter_def(fid, sx, sy, brightness, defs):
    prims = []
    if sx > 0.01 or sy > 0.01:
        prims.append(f'<feGaussianBlur stdDeviation="{_f(sx)} {_f(sy)}"/>')
    if abs(brightness - 1.0) > 1e-4:
        b = _f(brightness)
        prims.append('<feComponentTransfer>'
                     f'<feFuncR type="linear" slope="{b}"/><feFuncG type="linear" slope="{b}"/>'
                     f'<feFuncB type="linear" slope="{b}"/></feComponentTransfer>')
    if not prims:
        return None
    defs.append(f'<filter id="{fid}" x="-20%" y="-20%" width="140%" height="140%" '
                f'color-interpolation-filters="sRGB">{"".join(prims)}</filter>')
    return fid


def _render_state(st, content, W, H, pfx, defs, luma_src):
    if st['opacity'] <= 1e-4:
        return ''
    tr = st['transform']
    tx, ty = tr['translate'][0] * W, tr['translate'][1] * H
    s, r = tr['scale'], tr['rotate']
    ox, oy = tr['origin'][0] * W, tr['origin'][1] * H
    parts = []
    if abs(tx) > 1e-9 or abs(ty) > 1e-9:
        parts.append(f'translate({_f(tx)} {_f(ty)})')
    if abs(s - 1.0) > 1e-9 or abs(r) > 1e-9:
        parts.append(f'translate({_f(ox)} {_f(oy)})')
        if abs(r) > 1e-9:
            parts.append(f'rotate({_f(r)})')
        if abs(s - 1.0) > 1e-9:
            parts.append(f'scale({_f(s)})')
        parts.append(f'translate({_f(-ox)} {_f(-oy)})')
    g = content
    if parts:
        g = f'<g transform="{" ".join(parts)}">{g}</g>'
    flt = st['filter']
    k = H / 1080.0
    sb = flt['blur'] * k
    sx = math.hypot(sb, flt['motion_blur'][0] * k)
    sy = math.hypot(sb, flt['motion_blur'][1] * k)
    fid = _filter_def(f'{pfx}-f', sx, sy, flt['brightness'], defs)
    if fid:
        g = f'<g filter="url(#{fid})">{g}</g>'
    clip = st['clip']
    if clip:
        ctype = clip['type']
        if ctype == 'rect':
            cid = f'{pfx}-c'
            defs.append(f'<clipPath id="{cid}" clipPathUnits="userSpaceOnUse">'
                        f'<rect x="{_f(clip["x"] * W)}" y="{_f(clip["y"] * H)}" '
                        f'width="{_f(clip["w"] * W)}" height="{_f(clip["h"] * H)}"/></clipPath>')
            g = f'<g clip-path="url(#{cid})">{g}</g>'
        elif ctype == 'circle':
            cid = f'{pfx}-c'
            rad = clip['r'] * math.hypot(W, H) / 2.0
            defs.append(f'<clipPath id="{cid}" clipPathUnits="userSpaceOnUse">'
                        f'<circle cx="{_f(clip["cx"] * W)}" cy="{_f(clip["cy"] * H)}" '
                        f'r="{_f(rad)}"/></clipPath>')
            g = f'<g clip-path="url(#{cid})">{g}</g>'
        elif ctype == 'polygon':
            if not clip['points']:
                return ''
            cid = f'{pfx}-c'
            pts = ' '.join(f'{_f(x * W)},{_f(y * H)}' for x, y in clip['points'])
            defs.append(f'<clipPath id="{cid}" clipPathUnits="userSpaceOnUse">'
                        f'<polygon points="{pts}"/></clipPath>')
            g = f'<g clip-path="url(#{cid})">{g}</g>'
        elif ctype in ('stripes', 'rects'):
            if not clip['rects']:
                return ''
            pieces = []
            for i, (rect, off) in enumerate(zip(clip['rects'], clip['offsets'])):
                cid = f'{pfx}-c{i}'
                x, y, w, h = rect
                defs.append(f'<clipPath id="{cid}" clipPathUnits="userSpaceOnUse">'
                            f'<rect x="{_f(x * W)}" y="{_f(y * H)}" width="{_f(max(0.0, w) * W)}" '
                            f'height="{_f(max(0.0, h) * H)}"/></clipPath>')
                piece = f'<g clip-path="url(#{cid})">{g}</g>'
                if abs(off[0]) > 1e-9 or abs(off[1]) > 1e-9:
                    piece = f'<g transform="translate({_f(off[0] * W)} {_f(off[1] * H)})">{piece}</g>'
                pieces.append(piece)
            g = ''.join(pieces)
        elif ctype == 'luma':
            soft = clip['softness']
            slope = 1.0 / soft
            thr = clip['threshold']
            if clip['invert']:
                fs, fi = slope, -slope * (1.0 - thr)
            else:
                fs, fi = -slope, slope * thr
            lf, mid = f'{pfx}-lf', f'{pfx}-m'
            funcs = ''.join(f'<feFunc{ch} type="linear" slope="{_f(fs)}" intercept="{_f(fi)}"/>'
                            for ch in 'RGB')
            defs.append(f'<filter id="{lf}" filterUnits="userSpaceOnUse" x="0" y="0" '
                        f'width="{W}" height="{H}" color-interpolation-filters="sRGB">'
                        '<feColorMatrix type="matrix" values="0.2126 0.7152 0.0722 0 0 '
                        '0.2126 0.7152 0.0722 0 0 0.2126 0.7152 0.0722 0 0 0 0 0 0 1"/>'
                        f'<feComponentTransfer>{funcs}</feComponentTransfer></filter>')
            defs.append(f'<mask id="{mid}" maskUnits="userSpaceOnUse" x="0" y="0" '
                        f'width="{W}" height="{H}"><g filter="url(#{lf})">{luma_src}</g></mask>')
            g = f'<g mask="url(#{mid})">{g}</g>'
        else:
            raise AssertionError(ctype)
    if st['opacity'] < 1.0 - 1e-6:
        g = f'<g opacity="{_f(st["opacity"])}">{g}</g>'
    return g


def transition_svg(name, p, width, height, svg_a, svg_b, *, id_prefix=None, **opts):
    """Compose two SVG fragments into one transition frame (a <g> fragment).

    ids inside the composed frame are prefixed per call so several frames can
    live in one document. The fragments themselves are inserted verbatim.
    """
    frame = transition_frame(name, p, **opts)
    W = _int(width, 1, MAX_DIM, 'width')
    H = _int(height, 1, MAX_DIM, 'height')
    svg_a = _str(svg_a, 'svg_a')
    svg_b = _str(svg_b, 'svg_b')
    pfx = _prefix(id_prefix, f'{name}|{frame["p"]!r}|{W}x{H}|{len(svg_a)}|{len(svg_b)}')
    defs, body = [], []
    for key in frame['order']:
        body.append(_render_state(frame[key], svg_a if key == 'a' else svg_b, W, H,
                                  f'{pfx}-{key}', defs, svg_a))
    bg = f'<rect x="0" y="0" width="{W}" height="{H}" fill="{frame["background"]}"/>'
    return (f'<g data-rr-transition="{name}" data-rr-p="{_f(frame["p"])}">'
            f'<defs>{"".join(defs)}</defs>{bg}{"".join(body)}</g>')


def beat_transitions(bpm, beats_per_transition, duration, *, transition_beats=1.0,
                     names=None, offset_s=0.0):
    """Schedule transitions centred on musical beats.

    A cut happens every `beats_per_transition` beats (never at t = 0); each
    transition lasts `transition_beats` beats centred on its cut, clamped to the
    film. dip_to_colour is swapped for crossfade if it would start at frame 0.
    """
    bpm = _num(bpm, 20, 400, 'bpm')
    bpt = _num(beats_per_transition, 0.25, 256, 'beats_per_transition')
    duration = _num(duration, 0, 86_400, 'duration', low_open=True)
    tb = _num(transition_beats, 0.0, 64, 'transition_beats', low_open=True)
    offset_s = _num(offset_s, 0, 86_400, 'offset_s')
    if names is None:
        names = ['crossfade', 'slide_push_left', 'zoom_in', 'whip_pan', 'glitch_slices',
                 'iris_open']
    if not isinstance(names, (list, tuple)) or not 1 <= len(names) <= 64:
        raise ValueError('names must be a list of 1..64 transition names')
    names = [_choice(n, TRANSITIONS, f'names[{i}]') for i, n in enumerate(names)]
    period = 60.0 / bpm
    interval = period * bpt
    td = period * tb
    if td > interval + 1e-12:
        raise ValueError('transition_beats must not exceed beats_per_transition (overlap)')
    out = []
    k = 1
    while len(out) < 1000:
        cut = offset_s + k * interval
        if cut >= duration - 1e-9:
            break
        start = max(0.0, cut - td / 2.0)
        end = min(duration, cut + td / 2.0)
        name = names[(k - 1) % len(names)]
        if name == 'dip_to_colour' and start <= 1e-9:
            name = 'crossfade'
        out.append({'index': k - 1, 'cut_s': cut, 'start_s': start, 'end_s': end,
                    'duration_s': end - start, 'beat': k * bpt, 'name': name})
        k += 1
    return out


# --------------------------------------------------------------------------- camera


def _value_noise(seed, channel, x):
    i = math.floor(x)
    f = x - i

    def lat(n):
        return random.Random((seed * 1_000_003 + channel * 7_919 + n * 104_729)
                             % (2 ** 61 - 1)).random() * 2.0 - 1.0
    a, b = lat(i), lat(i + 1)
    w = f * f * f * (f * (6.0 * f - 15.0) + 10.0)
    return a + (b - a) * w


def _fbm(seed, channel, x, octaves):
    total, norm, amp, freq = 0.0, 0.0, 1.0, 1.0
    for _ in range(octaves):
        total += amp * _value_noise(seed, channel, x * freq)
        norm += amp
        amp *= 0.5
        freq *= 2.0
    return total / norm


def _zoom_about(s, fx, fy, W, H):
    return fx * W * (1.0 - s), fy * H * (1.0 - s)


def _cam(tx=0.0, ty=0.0, scale=1.0, rotate=0.0, blur=None, layers=None):
    return {'tx': float(tx), 'ty': float(ty), 'scale': float(scale), 'rotate_deg': float(rotate),
            'blur_by_layer': dict(blur or {}), 'layers': list(layers or [])}


def _layer(name, depth, tx=0.0, ty=0.0, scale=1.0):
    return {'name': name, 'depth': float(depth), 'tx': float(tx), 'ty': float(ty),
            'scale': float(scale)}


def _c_push_in(t, u, e, o, W, H):
    s = _lerp(1.0, o['end_scale'], e)
    return _cam(*_zoom_about(s, o['focus_x'], o['focus_y'], W, H), scale=s)


def _c_pull_out(t, u, e, o, W, H):
    s = _lerp(o['start_scale'], 1.0, e)
    return _cam(*_zoom_about(s, o['focus_x'], o['focus_y'], W, H), scale=s)


def _dolly(sign):
    def fn(t, u, e, o, W, H):
        d = o['distance']
        s = 1.0 + d + o['push'] * e
        bx, by = _zoom_about(s, 0.5, 0.5, W, H)
        shift = sign * d * W * (e - 0.5)
        layers = [_layer(f'layer{i}', dep, tx=shift / dep, scale=1.0 + d / dep)
                  for i, dep in enumerate(o['depths'])]
        return _cam(bx + shift, by, s, layers=layers)
    return fn


def _c_pan(t, u, e, o, W, H):
    d = o['distance']
    s = 1.0 + d
    bx, by = _zoom_about(s, 0.5, 0.5, W, H)
    sign = 1.0 if o['direction'] == 'left' else -1.0  # camera left -> picture moves right
    return _cam(bx + sign * d * W * (e - 0.5), by, s)


def _c_tilt(t, u, e, o, W, H):
    d = o['distance']
    s = 1.0 + d  # vertical margin (s - 1) * H / 2 covers the +/- d * H / 2 shift
    bx, by = _zoom_about(s, 0.5, 0.5, W, H)
    sign = 1.0 if o['direction'] == 'up' else -1.0
    return _cam(bx, by + sign * d * H * (e - 0.5), s)


def _c_orbit(t, u, e, o, W, H):
    theta = math.radians(o['degrees']) * (e - 0.5)
    rad = o['radius']
    s = 1.0 + 2.0 * rad + 0.02
    bx, by = _zoom_about(s, 0.5, 0.5, W, H)
    sx = math.sin(theta)
    layers = [_layer(f'layer{i}', dep, tx=-rad * W * sx / dep,
                     scale=1.0 + 0.03 * (1.0 - math.cos(theta)) / dep)
              for i, dep in enumerate(o['depths'])]
    return _cam(bx - rad * W * sx * 0.25, by, s, rotate=o['bank_deg'] * (2.0 * e - 1.0),
                layers=layers)


def _c_parallax(t, u, e, o, W, H):
    dx, dy = _DIRS[o['direction']]
    tr = o['travel']
    layers = []
    for i, dep in enumerate(o['depths']):
        shift = tr * (e - 0.5) / dep
        layers.append(_layer(f'layer{i}', dep, tx=dx * shift * W, ty=dy * shift * H,
                             scale=1.0 + tr / dep))
    return _cam(layers=layers)


def _c_spring_zoom(t, u, e, o, W, H):
    targets = o['targets']
    times = o['times']
    if times is None:
        times = [o['duration'] * i / len(targets) for i in range(len(targets))]
    if len(times) != len(targets):
        raise ValueError('spring_zoom: times must have the same length as targets')
    if any(b <= a for a, b in zip(times, times[1:])):
        raise ValueError('spring_zoom: times must be strictly increasing')
    logs = math.log(targets[0])
    for i in range(1, len(targets)):
        if t >= times[i]:
            step = math.log(targets[i]) - math.log(targets[i - 1])
            logs += step * (1.0 - _spring_x(t - times[i], o['stiffness'], o['damping'], o['mass']))
    s = math.exp(logs)
    return _cam(*_zoom_about(s, o['focus_x'], o['focus_y'], W, H), scale=s)


def _c_handheld(t, u, e, o, W, H):
    amp, rot, fq = o['amplitude_px'] * o['intensity'], o['rotation_deg'] * o['intensity'], o['frequency_hz']
    x = t * fq
    nx = _fbm(o['seed'], 0, x, o['octaves'])
    ny = _fbm(o['seed'], 1, x + 17.31, o['octaves'])
    nr = _fbm(o['seed'], 2, x * 0.7 + 41.7, o['octaves'])
    m = min(W, H)
    s = 1.0 + 2.0 * amp / m + abs(math.sin(math.radians(rot))) * max(W, H) / m
    bx, by = _zoom_about(s, 0.5, 0.5, W, H)
    return _cam(bx + amp * nx, by + amp * ny, s, rotate=rot * nr)


def _c_focus_pull(t, u, e, o, W, H):
    names, depths = o['layer_names'], o['depths']
    if len(names) != len(depths):
        raise ValueError('focus_pull: layer_names and depths must have the same length')
    inv = _lerp(1.0 / o['from_depth'], 1.0 / o['to_depth'], e)
    span = max(1e-9, 1.0 / min(depths) - 1.0 / max(depths))
    blur = {}
    for n, d in zip(names, depths):
        blur[n] = float(min(o['max_blur'], o['max_blur'] * abs(inv - 1.0 / d) / span))
    s = 1.0 + o['breathing'] * e
    bx, by = _zoom_about(s, 0.5, 0.5, W, H)
    return _cam(bx, by, s, blur=blur, layers=[_layer(n, d) for n, d in zip(names, depths)])


def _c_whip(t, u, e, o, W, H):
    dx, dy = _DIRS[o['direction']]
    d = o['distance']
    return _cam(dx * d * W * e, dy * d * H * e)


_COMMON_C_OPTS = {
    'duration': ('num', 3.0, 0.05, 3600.0),
    'width': ('int', 1920, 1, MAX_DIM),
    'height': ('int', 1080, 1, MAX_DIM),
    'fps': ('num', 30.0, 1.0, 240.0),
    'shutter_deg': ('num', 180.0, 0.0, 360.0),
}
_FOCUS = {'focus_x': ('num', 0.5, 0.0, 1.0), 'focus_y': ('num', 0.5, 0.0, 1.0)}
_DEPTHS = ('nums', [1.0, 2.0, 4.0], 0.1, 100.0, 1, 8)

CAMERA_MOVES = {
    'push_in': {'fn': _c_push_in, 'ease': 'sine_in_out',
                'opts': dict(_FOCUS, end_scale=('num', 1.25, 1.0, 8.0)),
                'ar': 'دخول بطيء بالكاميرا ناحية نقطة التركيز'},
    'pull_out': {'fn': _c_pull_out, 'ease': 'sine_in_out',
                 'opts': dict(_FOCUS, start_scale=('num', 1.25, 1.0, 8.0)),
                 'ar': 'رجوع بالكاميرا يكشف الكادر كله'},
    'dolly_left': {'fn': _dolly(1.0), 'ease': 'sine_in_out',
                   'opts': {'distance': ('num', 0.08, 0.0, 1.0), 'push': ('num', 0.03, 0.0, 1.0),
                            'depths': _DEPTHS},
                   'ar': 'ترافلينج جانبي لليسار مع اختلاف حركة الطبقات'},
    'dolly_right': {'fn': _dolly(-1.0), 'ease': 'sine_in_out',
                    'opts': {'distance': ('num', 0.08, 0.0, 1.0), 'push': ('num', 0.03, 0.0, 1.0),
                             'depths': _DEPTHS},
                    'ar': 'ترافلينج جانبي لليمين مع اختلاف حركة الطبقات'},
    'pan': {'fn': _c_pan, 'ease': 'sine_in_out',
            'opts': {'direction': ('choice', 'right', ('left', 'right')),
                     'distance': ('num', 0.15, 0.0, 1.0)},
            'ar': 'بان أفقي للكاميرا من غير اختلاف عمق'},
    'tilt': {'fn': _c_tilt, 'ease': 'sine_in_out',
             'opts': {'direction': ('choice', 'up', ('up', 'down')),
                      'distance': ('num', 0.15, 0.0, 1.0)},
             'ar': 'تيلت رأسي للكاميرا لفوق أو لتحت'},
    'orbit_2_5d': {'fn': _c_orbit, 'ease': 'sine_in_out',
                   'opts': {'degrees': ('num', 30.0, 0.0, 180.0), 'radius': ('num', 0.06, 0.0, 0.5),
                            'depths': _DEPTHS, 'bank_deg': ('num', 2.0, -30.0, 30.0)},
                   'ar': 'دوران وهمي حوالين الموضوع بطبقات عمق (2.5D)'},
    'parallax': {'fn': _c_parallax, 'ease': 'sine_in_out',
                 'opts': {'depths': _DEPTHS, 'travel': ('num', 0.12, 0.0, 1.0),
                          'direction': ('choice', 'left', _DIR_CHOICE)},
                 'ar': 'طبقات بتتحرك بسرعات مختلفة حسب عمقها'},
    'spring_zoom': {'fn': _c_spring_zoom, 'ease': 'linear',
                    'opts': dict(_FOCUS, targets=('nums', [1.0, 1.5, 1.2], 0.05, 20.0, 1, 32),
                                 times=('times', None),
                                 stiffness=('num', 120.0, 0.01, 1e5),
                                 damping=('num', 14.0, 0.0, 1e4), mass=('num', 1.0, 0.001, 1e3)),
                    'ar': 'زووم بزنبرك على مقياس لوغاريتمي بين أكتر من هدف'},
    'handheld': {'fn': _c_handheld, 'ease': 'linear',
                 'opts': {'amplitude_px': ('num', 6.0, 0.0, 500.0),
                          'rotation_deg': ('num', 0.35, 0.0, 15.0),
                          'frequency_hz': ('num', 1.1, 0.01, 30.0), 'seed': ('int', 3, 0, 2 ** 31 - 1),
                          'octaves': ('int', 3, 1, 6), 'intensity': ('num', 1.0, 0.0, 10.0)},
                 'ar': 'اهتزاز كاميرا محمولة بضوضاء ناعمة ثابتة البذرة'},
    'focus_pull': {'fn': _c_focus_pull, 'ease': 'sine_in_out',
                   'opts': {'layer_names': ('names', ['foreground', 'subject', 'background'], 1, 8),
                            'depths': ('nums', [1.0, 2.5, 8.0], 0.1, 1000.0, 1, 8),
                            'from_depth': ('num', 1.0, 0.1, 1000.0),
                            'to_depth': ('num', 8.0, 0.1, 1000.0),
                            'max_blur': ('num', 14.0, 0.0, 200.0),
                            'breathing': ('num', 0.01, 0.0, 0.2)},
                   'ar': 'نقل البؤرة من طبقة لطبقة مع ضباب لكل طبقة'},
    'whip': {'fn': _c_whip, 'ease': 'expo_in_out',
             'opts': {'direction': ('choice', 'left', _DIR_CHOICE),
                      'distance': ('num', 0.6, 0.0, 4.0)},
             'ar': 'حركة كاميرا خاطفة سريعة بضباب حركة'},
}


def _camera_opts(move, opts):
    entry = CAMERA_MOVES[move]
    spec = dict(_COMMON_C_OPTS)
    spec['ease'] = ('ease', entry['ease'])
    spec.update({k: v for k, v in entry['opts'].items() if v[0] != 'times'})
    times_given = opts.get('times') if 'times' in entry['opts'] else None
    rest = {k: v for k, v in opts.items() if not (k == 'times' and 'times' in entry['opts'])}
    o = _opts(spec, rest, move)
    if 'times' in entry['opts']:
        o['times'] = (None if times_given is None
                      else _opt(('nums', None, 0.0, 86_400.0, 1, 32), times_given, f'{move}.times'))
    return o


def camera_at(move, t, **opts):
    """Camera state at time t (seconds) for `move`.

    Returns {tx, ty, scale, rotate_deg, blur_by_layer, layers, motion_blur_px, ...}.
    motion_blur_px is the screen travel of the frame origin during the shutter
    interval (shutter_deg / 360 / fps), a hint for directional blur.
    """
    _choice(move, CAMERA_MOVES, 'move')
    t = _num(t, -86_400, 86_400, 't')
    o = _camera_opts(move, opts)
    W, H = o['width'], o['height']
    fn = CAMERA_MOVES[move]['fn']

    def at(tt):
        u = _clamp(tt / o['duration'])
        return u, fn(tt, u, o['ease'](u), o, W, H)

    u, cam = at(t)
    dt = o['shutter_deg'] / 360.0 / o['fps']
    if dt > 0:
        _, prev = at(t - dt)
        mb = [abs(cam['tx'] - prev['tx']), abs(cam['ty'] - prev['ty'])]
    else:
        mb = [0.0, 0.0]
    cam.update({'move': move, 't': t, 'progress': u, 'width': W, 'height': H,
                'motion_blur_px': [float(mb[0]), float(mb[1])]})
    return cam


def apply_camera_svg(camera, svg_fragment, width, height, *, id_prefix=None):
    """Wrap an SVG fragment (or a list of {'svg', 'layer'} layers) in the camera transform."""
    if not isinstance(camera, dict):
        raise ValueError('camera must be a dict from camera_at')
    tx = _num(camera.get('tx', 0.0), -1e7, 1e7, 'camera.tx')
    ty = _num(camera.get('ty', 0.0), -1e7, 1e7, 'camera.ty')
    s = _num(camera.get('scale', 1.0), 0.0, 1e4, 'camera.scale')
    r = _num(camera.get('rotate_deg', 0.0), -1e5, 1e5, 'camera.rotate_deg')
    W = _int(width, 1, MAX_DIM, 'width')
    H = _int(height, 1, MAX_DIM, 'height')
    blur = camera.get('blur_by_layer') or {}
    layers = camera.get('layers') or []
    mbv = camera.get('motion_blur_px') or [0.0, 0.0]
    if not isinstance(blur, dict) or not isinstance(layers, list):
        raise ValueError('camera.blur_by_layer must be a dict and camera.layers a list')
    blur = {str(k): _num(v, 0.0, 1e4, f'blur_by_layer[{k}]') for k, v in blur.items()}
    if not isinstance(mbv, (list, tuple)) or len(mbv) != 2:
        raise ValueError('camera.motion_blur_px must be [x, y]')
    mbx = 0.29 * _num(mbv[0], 0.0, 1e6, 'motion_blur_px[0]')
    mby = 0.29 * _num(mbv[1], 0.0, 1e6, 'motion_blur_px[1]')
    pfx = _prefix(id_prefix, f'cam|{tx!r}|{ty!r}|{s!r}|{r!r}|{W}x{H}')
    defs = []
    cx, cy = W / 2.0, H / 2.0

    def blurred(content, extra, fid):
        extra = _num(extra, 0.0, 1e4, 'blur')
        got = _filter_def(fid, math.hypot(extra, mbx), math.hypot(extra, mby), 1.0, defs)
        return f'<g filter="url(#{got})">{content}</g>' if got else content

    if isinstance(svg_fragment, str):
        _str(svg_fragment, 'svg')
        inner = blurred(svg_fragment, blur.get('all', 0.0), f'{pfx}-f')
    elif isinstance(svg_fragment, (list, tuple)) and 1 <= len(svg_fragment) <= 16:
        parts = []
        for i, item in enumerate(svg_fragment):
            if not isinstance(item, dict):
                raise ValueError(f'svg[{i}] must be a dict {{"svg": ..., "layer": name}}')
            _no_extra([k for k in item if k not in ('svg', 'layer')], f'svg[{i}]')
            content = _str(item.get('svg'), f'svg[{i}].svg')
            info = layers[i] if i < len(layers) and isinstance(layers[i], dict) else None
            lname = item.get('layer') or (info.get('name') if info else None) or f'layer{i}'
            if not isinstance(lname, str):
                raise ValueError(f'svg[{i}].layer must be a string')
            g = content
            if info:
                ls = _num(info.get('scale', 1.0), 0.0, 1e4, f'layers[{i}].scale')
                ltx = _num(info.get('tx', 0.0), -1e7, 1e7, f'layers[{i}].tx') + cx * (1.0 - ls)
                lty = _num(info.get('ty', 0.0), -1e7, 1e7, f'layers[{i}].ty') + cy * (1.0 - ls)
                g = f'<g transform="translate({_f(ltx)} {_f(lty)}) scale({_f(ls)})">{g}</g>'
            g = blurred(g, blur.get(lname, 0.0) + blur.get('all', 0.0), f'{pfx}-f{i}')
            parts.append(f'<g data-rr-layer="{lname if _NAME_RE.match(lname) else i}">{g}</g>')
        inner = ''.join(parts)
    else:
        raise ValueError('svg must be a string or a list of 1..16 layer dicts')
    transform = (f'rotate({_f(r)} {_f(cx)} {_f(cy)}) translate({_f(tx)} {_f(ty)}) '
                 f'scale({_f(s)})')
    move = camera.get('move')
    label = move if isinstance(move, str) and _NAME_RE.match(move) else 'custom'
    return (f'<g data-rr-camera="{label}">'
            f'<defs>{"".join(defs)}</defs><g transform="{transform}">{inner}</g></g>')


# --------------------------------------------------------------------------- timeline layer


def render_layer(op, params, t, width, height):
    """SVG fragment for a timeline renderer at time t (seconds).

    op 'transition': params {name, duration, svg_a, svg_b, start=0, ...transition options}
    op 'camera':     params {move, svg, start=0, ...camera options except width/height}
    """
    _choice(op, ('transition', 'camera'), 'op')
    if not isinstance(params, dict):
        raise ValueError('params must be a dict')
    t = _num(t, -86_400, 86_400, 't')
    W = _int(width, 1, MAX_DIM, 'width')
    H = _int(height, 1, MAX_DIM, 'height')
    rest = dict(params)
    start = _num(rest.pop('start', 0.0), -86_400, 86_400, 'start')
    if op == 'transition':
        for key in ('name', 'duration', 'svg_a', 'svg_b'):
            if key not in rest:
                raise ValueError(f'transition layer needs {key}')
        name = rest.pop('name')
        dur = _num(rest.pop('duration'), 0.0, 3600.0, 'duration', low_open=True)
        svg_a, svg_b = rest.pop('svg_a'), rest.pop('svg_b')
        p = _clamp((t - start) / dur)
        return transition_svg(name, p, W, H, svg_a, svg_b, **rest)
    if 'move' not in rest or 'svg' not in rest:
        raise ValueError('camera layer needs move and svg')
    if 'width' in rest or 'height' in rest:
        raise ValueError('camera layer takes width/height from render_layer arguments')
    move = rest.pop('move')
    svg = rest.pop('svg')
    cam = camera_at(move, t - start, width=W, height=H, **rest)
    return apply_camera_svg(cam, svg, W, H)


# --------------------------------------------------------------------------- ops

_EXAMPLE_KEYS = [
    {'t': 0.0, 'value': '#c0392b', 'ease': 'sine_in_out'},
    {'t': 1.0, 'value': '#2e86de', 'hold': True},
    {'t': 1.5, 'value': '#27ae60'},
]


def _example_svg(W, H, colour, label):
    return (f'<rect x="0" y="0" width="{W}" height="{H}" fill="{colour}"/>'
            f'<circle cx="{_f(W * 0.5)}" cy="{_f(H * 0.5)}" r="{_f(min(W, H) * 0.25)}" '
            f'fill="#ffffff" fill-opacity="0.85"/>'
            f'<text x="{_f(W * 0.5)}" y="{_f(H * 0.52)}" text-anchor="middle" '
            f'font-size="{_f(H * 0.12)}" fill="#222222">{label}</text>')


_SVG_LIMITS = ['SVG output approximates editing-app effects (clipPath, mask, transform, opacity, '
               'feGaussianBlur, feComponentTransfer); renderers differ slightly',
               'no GPU path; blur, motion blur, glitch and luma keying are approximations',
               'svg fragments are inserted verbatim: ids inside them are not rewritten, so '
               'fragments duplicated by stripes/luma masks may repeat their own ids']


def _op_ease(*, name='cubic_in_out', t=None, samples=11, opts=None, **extra):
    _no_extra(extra)
    _choice(name, EASINGS, 'name')
    opts = {} if opts is None else opts
    if not isinstance(opts, dict):
        raise ValueError('opts must be a dict')
    if t is not None:
        value = ease(name, t, **opts)
        result = {'name': name, 't': _clamp(float(t)), 'value': value}
    else:
        n = _int(samples, 2, MAX_SAMPLES, 'samples')
        pts = [[i / (n - 1), ease(name, i / (n - 1), **opts)] for i in range(n)]
        vals = [v for _, v in pts]
        result = {'name': name, 'samples': pts, 'min': min(vals), 'max': max(vals),
                  'overshoots': min(vals) < -1e-9 or max(vals) > 1 + 1e-9,
                  'end_value': vals[-1]}
    return _pack('ease', result,
                 ['t is normalised progress clamped to [0, 1]',
                  'cubic_bezier is solved by Newton iterations with a bisection fallback',
                  'spring is the analytic step response of m x\'\' + c x\' + k x = 0 with t=1 '
                  'mapped to `duration` seconds; it need not equal exactly 1 at t=1'],
                 [f'samples <= {MAX_SAMPLES}', 'easing options are range-checked per easing'])


def _op_track(*, keys=None, t=None, times=None, duration=2.0, fps=10.0, **extra):
    _no_extra(extra)
    prep = _prepare_track(_EXAMPLE_KEYS if keys is None else keys)
    if t is not None:
        result = {'kind': prep[0], 't': float(_num(t, -1e9, 1e9, 't')),
                  'value': _sample_prepared(prep, float(t))}
    else:
        if times is not None:
            if not isinstance(times, (list, tuple)) or not 1 <= len(times) <= MAX_SAMPLES:
                raise ValueError(f'times must be a list of 1..{MAX_SAMPLES} numbers')
            ts = [_num(x, -1e9, 1e9, f'times[{i}]') for i, x in enumerate(times)]
        else:
            ts = frames_for(duration, fps)
            if len(ts) > MAX_SAMPLES:
                raise ValueError(f'duration * fps gives more than {MAX_SAMPLES} frames')
        result = {'kind': prep[0], 'frames': len(ts),
                  'samples': [[x, _sample_prepared(prep, x)] for x in ts]}
    return _pack('track', result,
                 ['ease/hold on key i governs the segment to key i+1',
                  'colours are interpolated in linear RGB (sRGB transfer decoded) and re-encoded',
                  'values hold before the first and after the last key',
                  'frame times are i / fps for round(duration * fps) frames'],
                 [f'keys <= {MAX_KEYS}', f'samples <= {MAX_SAMPLES}',
                  'overshooting eases (back/elastic) may push colours past the key colours; '
                  'colour channels are clamped'])


def _op_transition_frame(*, name='crossfade', p=0.5, width=640, height=360, svg_a=None,
                         svg_b=None, render_svg=True, opts=None, **extra):
    _no_extra(extra)
    opts = {} if opts is None else opts
    if not isinstance(opts, dict):
        raise ValueError('opts must be a dict')
    W = _int(width, 1, MAX_DIM, 'width')
    H = _int(height, 1, MAX_DIM, 'height')
    frame = transition_frame(name, p, **opts)
    result = dict(frame)
    if _bool(render_svg, 'render_svg'):
        a = _example_svg(W, H, '#c0392b', 'A') if svg_a is None else svg_a
        b = _example_svg(W, H, '#2e86de', 'B') if svg_b is None else svg_b
        result['svg'] = transition_svg(name, p, W, H, a, b, id_prefix=f'rrop-{name}', **opts)
        result['width'], result['height'] = W, H
    return _pack('transition_frame', result,
                 ['clip A is outgoing, clip B incoming; order lists draw order (last on top)',
                  'translate and clip geometry are fractions of the frame; circle r is a fraction '
                  'of the half-diagonal; blur is Gaussian std-dev px at 1080 px height',
                  'clips are assumed opaque (crossfade keeps A at full opacity under B)'],
                 _SVG_LIMITS + ['dip_to_colour refuses at_film_start=True'])


def _op_camera(*, move='push_in', t=None, samples=5, opts=None, svg=None, **extra):
    _no_extra(extra)
    opts = {} if opts is None else opts
    if not isinstance(opts, dict):
        raise ValueError('opts must be a dict')
    _choice(move, CAMERA_MOVES, 'move')
    if t is not None:
        cam = camera_at(move, t, **opts)
        result = {'camera': cam}
        if svg is not None:
            result['svg'] = apply_camera_svg(cam, svg, cam['width'], cam['height'],
                                             id_prefix=f'rrcam-{move}')
    else:
        n = _int(samples, 2, 1001, 'samples')
        dur = _camera_opts(move, opts)['duration']
        result = {'samples': [camera_at(move, dur * i / (n - 1), **opts) for i in range(n)]}
    return _pack('camera', result,
                 ['camera maps x -> rotate(rotate_deg about centre)(scale * x + (tx, ty))',
                  'tx/ty/blur are px at the camera width/height; t is seconds, progress = t/duration',
                  'overscan scale hides frame edges for dolly/pan/tilt/orbit/handheld only',
                  'handheld uses seeded smooth value noise; spring_zoom superposes analytic spring '
                  'step responses on log(scale)', 'focus_pull blur follows |1/focus - 1/depth|'],
                 ['2.5D only: layers are flat planes, no true 3D projection',
                  'motion_blur_px is a translation-only hint; scale/rotation blur is ignored',
                  'no GPU; SVG blur is an approximation'])


def _op_beats(*, bpm=120.0, beats_per_transition=4.0, duration=10.0, transition_beats=1.0,
              names=None, offset_s=0.0, **extra):
    _no_extra(extra)
    sched = beat_transitions(bpm, beats_per_transition, duration,
                             transition_beats=transition_beats, names=names, offset_s=offset_s)
    return _pack('beat_transitions', {'bpm': float(bpm), 'transitions': sched},
                 ['cuts land exactly on beats offset_s + k * beats_per_transition * 60 / bpm, k >= 1',
                  'each transition is centred on its cut and clamped to [0, duration]'],
                 ['at most 1000 transitions', 'transition_beats <= beats_per_transition',
                  'no beat detection: bpm is given, not measured'])


def _op_list(**extra):
    _no_extra(extra)
    result = {
        'easings': [{'name': n, 'ar': e['ar'], 'options': sorted(e['opts'])}
                    for n, e in EASINGS.items()],
        'transitions': [{'name': n, 'ar': e['ar'], 'default_ease': e['ease'],
                         'options': sorted(e['opts'])} for n, e in TRANSITIONS.items()],
        'camera_moves': [{'name': n, 'ar': e['ar'], 'default_ease': e['ease'],
                          'options': sorted(e['opts'])} for n, e in CAMERA_MOVES.items()],
        'counts': {'easings': len(EASINGS), 'transitions': len(TRANSITIONS),
                   'camera_moves': len(CAMERA_MOVES)},
    }
    return _pack('list_catalogue', result,
                 ['descriptions are one-line Arabic summaries of native Red Rose implementations'],
                 _SVG_LIMITS)


OPS = {
    'ease': _op_ease, 'track': _op_track, 'transition_frame': _op_transition_frame,
    'camera': _op_camera, 'list_catalogue': _op_list, 'beat_transitions': _op_beats,
}


def run(op, params=None):
    """Validate and dispatch: run('ease', {'name': 'back_out'}) -> {'op','result','assumptions','limits'}."""
    if not isinstance(op, str) or op not in OPS:
        raise ValueError(f'op must be one of {sorted(OPS)}')
    if params is None:
        params = {}
    if not isinstance(params, dict):
        raise ValueError('params must be a dict')
    if len(params) > MAX_PARAMS:
        raise ValueError(f'params may have at most {MAX_PARAMS} keys')
    if not all(isinstance(key, str) for key in params):
        raise ValueError('param names must be strings')
    out = OPS[op](**params)
    try:
        json.dumps(out, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f'{op} produced a non-JSON-serialisable result: {exc}') from exc
    return out
