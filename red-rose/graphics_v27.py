"""Red Rose V27: native motion graphics as seekable, animated SVG fragments.

Pure standard-library Python (math, random, html, json). No file I/O, no
subprocess, no network, no printing. Original code re-implementing ideas from
the legacy families SHAPE, DRAW, GLOW, TEX, PART, DATA, MAP, EXPL, RETRO, UI
and BRAND; nothing is imported from legacy modules.

Every feature is a function ``name(params, t, width, height) -> str`` that
returns an SVG *fragment* (a ``<g>`` element, no ``<svg>`` wrapper). Each
fragment is a pure function of the time ``t`` (seconds): there is no wall
clock, no SMIL ``<animate>`` and no ``<script>``, so any frame can be rendered
directly (seekable) and the same input always gives the same bytes
(randomness is seeded and hash-based). Every SVG id is prefixed per call with
``id_prefix`` (or a deterministic prefix derived from the op and params) so
several layers can be combined in one document. No external hrefs are emitted.

``run(op, params)`` validates strictly (ValueError on unknown parameter names,
bools-as-numbers, non-finite or out-of-range values) and returns
``{'op', 'result', 'assumptions', 'limits'}`` like the other Red Rose modules;
``params`` may include ``t``, ``width``, ``height`` and ``id_prefix``.
``render_layer(op, params, t, width, height)`` dispatches for a timeline.

Owner rules honoured here: texture/vignette/scanline overlays are OFF unless
requested by name; neon glow is off unless ``glow`` is true and its strength is
capped; the route map is schematic (graticule only, no map imagery).
"""
from __future__ import annotations

import html
import json
import math
import random

MAX_PARAMS = 32
MAX_CANVAS = 16384.0
MAX_T = 86400.0
_M64 = (1 << 64) - 1

EASINGS = ('linear', 'ease_in', 'ease_out', 'ease_in_out', 'smooth', 'back_out', 'expo_out')

DEFAULT_FONT = 'Arial, Helvetica, sans-serif'


# --------------------------------------------------------------------------- validation

def _no_extra(extra):
    if extra:
        raise ValueError('unknown parameter(s): ' + ', '.join(sorted(map(str, extra))))


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


def _choice(value, options, name):
    if not isinstance(value, str) or value not in options:
        raise ValueError(f'{name} must be one of {sorted(options)}')
    return value


def _bool(value, name):
    if not isinstance(value, bool):
        raise ValueError(f'{name} must be true or false')
    return value


def _str(value, name, max_len=80, allow_empty=True):
    if not isinstance(value, str):
        raise ValueError(f'{name} must be a string')
    if len(value) > max_len:
        raise ValueError(f'{name} must be at most {max_len} characters')
    if not allow_empty and not value.strip():
        raise ValueError(f'{name} must not be empty')
    if any(ord(c) < 32 or 0x7f <= ord(c) < 0xa0 for c in value):
        raise ValueError(f'{name} must not contain control characters')
    return value


_HEX = set('0123456789abcdef')


def _color(value, name, allow_none=False):
    if allow_none and value == 'none':
        return 'none'
    if not isinstance(value, str):
        raise ValueError(f'{name} must be a hex colour like #c8102e')
    v = value.strip().lower()
    if v.startswith('#') and len(v) in (4, 7) and all(c in _HEX for c in v[1:]):
        if len(v) == 4:
            v = '#' + ''.join(c * 2 for c in v[1:])
        return v
    raise ValueError(f'{name} must be a hex colour like #c8102e' + (" or 'none'" if allow_none else ''))


def _font(value, name='font_family'):
    _str(value, name, 80, allow_empty=False)
    for c in value:
        if not (c.isalnum() or c in " ,-_'"):
            raise ValueError(f'{name} may contain only letters, digits, spaces, commas, hyphens and quotes')
    return value


def _vec(value, size, name, low=-1e6, high=1e6):
    if not isinstance(value, (list, tuple)) or len(value) != size:
        raise ValueError(f'{name} must be a list of {size} numbers')
    return [_num(v, low, high, f'{name}[{i}]') for i, v in enumerate(value)]


def _points(value, name, min_n, max_n, low=-1e6, high=1e6):
    if not isinstance(value, (list, tuple)) or not min_n <= len(value) <= max_n:
        raise ValueError(f'{name} must be a list of {min_n}..{max_n} [x, y] points')
    return [tuple(_vec(p, 2, f'{name}[{i}]', low, high)) for i, p in enumerate(value)]


def _numlist(value, name, min_n, max_n, low=-1e12, high=1e12):
    if not isinstance(value, (list, tuple)) or not min_n <= len(value) <= max_n:
        raise ValueError(f'{name} must be a list of {min_n}..{max_n} numbers')
    return [_num(v, low, high, f'{name}[{i}]') for i, v in enumerate(value)]


def _strlist(value, name, min_n, max_n, max_len=40):
    if not isinstance(value, (list, tuple)) or not min_n <= len(value) <= max_n:
        raise ValueError(f'{name} must be a list of {min_n}..{max_n} strings')
    return [_str(v, f'{name}[{i}]', max_len) for i, v in enumerate(value)]


def _seed(value):
    return _int(value, 0, 2 ** 31 - 1, 'seed')


def _easing(value, name='easing'):
    return _choice(value, set(EASINGS), name)


def _rtl_flag(value, name='rtl'):
    if value == 'auto' or isinstance(value, bool):
        return value
    raise ValueError(f"{name} must be true, false or 'auto'")


def _prefix(value, op, params):
    if value is None:
        try:
            blob = json.dumps(params, sort_keys=True, ensure_ascii=True, default=str)
        except (TypeError, ValueError):
            blob = repr(sorted(params))
        return f'rr{op[:3]}{_fnv(op + "|" + blob) & 0xffffffff:08x}'
    if (not isinstance(value, str) or not 1 <= len(value) <= 24 or not value.isascii()
            or not value[0].isalpha()
            or not all(c.isalnum() or c in '-_' for c in value)):
        raise ValueError('id_prefix must be 1..24 ASCII letters/digits/-/_ starting with a letter')
    return value


def _canvas(t, width, height):
    t = _num(t, 0, MAX_T, 't')
    width = _num(width, 16, MAX_CANVAS, 'width')
    height = _num(height, 16, MAX_CANVAS, 'height')
    return t, width, height


# --------------------------------------------------------------------------- small maths

def _clamp(v, lo=0.0, hi=1.0):
    return lo if v < lo else hi if v > hi else v


def _lerp(a, b, f):
    return a + (b - a) * f


def _progress(t, delay, duration):
    return _clamp((t - delay) / duration)


def _ease(name, u):
    u = _clamp(u)
    if name == 'linear':
        return u
    if name == 'ease_in':
        return u * u * u
    if name == 'ease_out':
        return 1 - (1 - u) ** 3
    if name == 'ease_in_out':
        return 4 * u ** 3 if u < 0.5 else 1 - (-2 * u + 2) ** 3 / 2
    if name == 'smooth':
        return u * u * (3 - 2 * u)
    if name == 'back_out':
        c1 = 1.70158
        c3 = c1 + 1
        return 1 + c3 * (u - 1) ** 3 + c1 * (u - 1) ** 2
    if name == 'expo_out':
        return 1.0 if u >= 1 else 1 - 2 ** (-10 * u)
    raise ValueError(f'unknown easing {name!r}')


def _mix64(x):
    x = (x + 0x9E3779B97F4A7C15) & _M64
    x = ((x ^ (x >> 30)) * 0xBF58476D1CE4E5B9) & _M64
    x = ((x ^ (x >> 27)) * 0x94D049BB133111EB) & _M64
    return x ^ (x >> 31)


def _h01(*keys):
    """Deterministic hash of integer keys -> float in [0, 1)."""
    h = 0x243F6A8885A308D3
    for k in keys:
        h = _mix64(h ^ (int(k) & _M64))
    return (h >> 11) / float(1 << 53)


def _fnv(s):
    h = 0xcbf29ce484222325
    for b in s.encode('utf-8'):
        h ^= b
        h = (h * 0x100000001b3) & _M64
    return h


def _vnoise(seed, chan, x):
    """Smooth 1D value noise in [-1, 1]."""
    i = math.floor(x)
    f = x - i
    s = f * f * (3 - 2 * f)
    return _lerp(_h01(seed, chan, i), _h01(seed, chan, i + 1), s) * 2 - 1


def _wrap(v, lo, hi):
    span = hi - lo
    return lo + ((v - lo) % span) if span > 0 else lo


def _dist(a, b):
    return math.hypot(b[0] - a[0], b[1] - a[1])


def _cubic(p0, c1, c2, p3, u):
    v = 1 - u
    a, b, c, d = v * v * v, 3 * v * v * u, 3 * v * u * u, u * u * u
    return (a * p0[0] + b * c1[0] + c * c2[0] + d * p3[0],
            a * p0[1] + b * c1[1] + c * c2[1] + d * p3[1])


def _poly_len(pts, closed=False):
    total = sum(_dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1))
    if closed and len(pts) > 1:
        total += _dist(pts[-1], pts[0])
    return total


def _dedupe(pts, eps=1e-9):
    out = []
    for p in pts:
        if not out or _dist(out[-1], p) > eps:
            out.append(p)
    return out


def _fmt(v):
    if abs(v) < 5e-3:
        return '0'
    s = f'{v:.2f}'.rstrip('0').rstrip('.')
    return '0' if s in ('-0', '', '-') else s


def _fo(v):
    """Opacity / small factor formatting with 3 decimals."""
    s = f'{_clamp(v):.3f}'.rstrip('0').rstrip('.')
    return s or '0'


def _esc(s):
    return html.escape(s, quote=True)


def _has_arabic(s):
    for c in s:
        o = ord(c)
        if (0x0600 <= o <= 0x06FF or 0x0750 <= o <= 0x077F or 0x08A0 <= o <= 0x08FF
                or 0xFB50 <= o <= 0xFDFF or 0xFE70 <= o <= 0xFEFF):
            return True
    return False


def _is_latin(s):
    return all(ord(c) < 0x250 for c in s)


def _hex_rgb(c):
    return int(c[1:3], 16), int(c[3:5], 16), int(c[5:7], 16)


def _mix_hex(c1, c2, f):
    a, b = _hex_rgb(c1), _hex_rgb(c2)
    return '#' + ''.join(f'{round(_lerp(x, y, _clamp(f))):02x}' for x, y in zip(a, b))


def _txt(x, y, s, size, fill, *, ff=DEFAULT_FONT, anchor='middle', weight=400,
         rtl=None, opacity=None, extra=''):
    if rtl is None:
        rtl = _has_arabic(s)
    attrs = (f'x="{_fmt(x)}" y="{_fmt(y)}" font-family="{_esc(ff)}" font-size="{_fmt(size)}" '
             f'font-weight="{weight}" fill="{fill}" text-anchor="{anchor}" dominant-baseline="central"')
    if rtl:
        attrs += ' direction="rtl" unicode-bidi="embed"'
    if opacity is not None:
        attrs += f' opacity="{_fo(opacity)}"'
    if extra:
        attrs += ' ' + extra
    return f'<text {attrs}>{_esc(s)}</text>'


def _path_d(pts, closed=False):
    if not pts:
        return ''
    d = f'M{_fmt(pts[0][0])} {_fmt(pts[0][1])}' + ''.join(
        f' L{_fmt(x)} {_fmt(y)}' for x, y in pts[1:])
    return d + (' Z' if closed else '')


def _arabic_digits(s):
    return s.translate(str.maketrans('0123456789,.', '٠١٢٣٤٥٦٧٨٩٬٫'))


def _fmt_value(v, decimals=0, digits='latin', suffix=''):
    s = f'{v:,.{decimals}f}'
    if s.startswith('-') and float(s.replace(',', '')) == 0:
        s = s[1:]
    if digits == 'arabic':
        s = _arabic_digits(s)
    return s + suffix


# --------------------------------------------------------------------------- SVG path parsing

_CMDS = set('MmLlHhVvCcSsQqTtZz')
MAX_PATH_CHARS = 20000
MAX_SEGMENTS = 4000


def _tokenize_path(d, name):
    tokens = []
    i, n = 0, len(d)
    while i < n:
        c = d[i]
        if c in _CMDS:
            tokens.append(c)
            i += 1
        elif c in ' ,\t\r\n':
            i += 1
        elif c in '+-.0123456789':
            j = i
            if d[j] in '+-':
                j += 1
            seen_dot = seen_digit = False
            while j < n and (d[j] in '0123456789' or (d[j] == '.' and not seen_dot)):
                if d[j] == '.':
                    seen_dot = True
                else:
                    seen_digit = True
                j += 1
            if j < n and d[j] in 'eE':
                k = j + 1
                if k < n and d[k] in '+-':
                    k += 1
                if k < n and d[k] in '0123456789':
                    while k < n and d[k] in '0123456789':
                        k += 1
                    j = k
            if not seen_digit:
                raise ValueError(f'{name}: malformed number at position {i}')
            val = float(d[i:j])
            if not math.isfinite(val) or abs(val) > 1e6:
                raise ValueError(f'{name}: coordinates must be finite and within +-1e6')
            tokens.append(val)
            i = j
        elif c in 'Aa':
            raise ValueError(f'{name}: arc commands (A/a) are not supported; convert arcs to cubic curves')
        else:
            raise ValueError(f'{name}: unexpected character {c!r} at position {i}')
    return tokens


def _parse_path(d, name='path'):
    """Parse M/L/H/V/C/S/Q/T/Z (absolute and relative) into subpaths.

    Each subpath: {'start': (x, y), 'segs': [('L', p0, p1) | ('C', p0, c1, c2, p3)], 'closed': bool}.
    Quadratic segments are converted exactly to cubics.
    """
    if not isinstance(d, str) or not d.strip() or len(d) > MAX_PATH_CHARS:
        raise ValueError(f'{name} must be a non-empty SVG path string of at most {MAX_PATH_CHARS} characters')
    toks = _tokenize_path(d, name)
    subs = []
    cur = None
    pos = (0.0, 0.0)
    start = (0.0, 0.0)
    cmd = None
    last_c2 = last_q = None
    i = 0
    nseg = 0

    def nums(k):
        nonlocal i
        if i + k > len(toks) or any(not isinstance(x, float) for x in toks[i:i + k]):
            raise ValueError(f'{name}: command {cmd} expects {k} numbers')
        vals = toks[i:i + k]
        i += k
        return vals

    while i < len(toks):
        tk = toks[i]
        if isinstance(tk, str):
            cmd = tk
            i += 1
            if cmd in 'Zz':
                if cur is not None:
                    if _dist(pos, start) > 1e-9:
                        cur['segs'].append(('L', pos, start))
                        nseg += 1
                    cur['closed'] = True
                    pos = start
                cur = None
                last_c2 = last_q = None
                continue
        else:
            if cmd is None:
                raise ValueError(f'{name} must start with M')
            if cmd in 'Zz':
                raise ValueError(f'{name}: numbers are not allowed after Z')
        rel = cmd.islower()
        big = cmd.upper()
        ox, oy = pos if rel else (0.0, 0.0)
        if big == 'M':
            x, y = nums(2)
            pos = (ox + x, oy + y)
            start = pos
            cur = {'start': pos, 'segs': [], 'closed': False}
            subs.append(cur)
            cmd = 'l' if rel else 'L'
            last_c2 = last_q = None
            continue
        if cur is None:
            if not subs and big != 'M':
                raise ValueError(f'{name} must start with M')
            cur = {'start': pos, 'segs': [], 'closed': False}
            subs.append(cur)
            start = pos
        new_c2 = new_q = None
        if big == 'L':
            x, y = nums(2)
            p = (ox + x, oy + y)
            seg = ('L', pos, p)
        elif big == 'H':
            (x,) = nums(1)
            p = ((pos[0] + x) if rel else x, pos[1])
            seg = ('L', pos, p)
        elif big == 'V':
            (y,) = nums(1)
            p = (pos[0], (pos[1] + y) if rel else y)
            seg = ('L', pos, p)
        elif big == 'C':
            x1, y1, x2, y2, x, y = nums(6)
            c1, c2, p = (ox + x1, oy + y1), (ox + x2, oy + y2), (ox + x, oy + y)
            seg = ('C', pos, c1, c2, p)
            new_c2 = c2
        elif big == 'S':
            x2, y2, x, y = nums(4)
            c1 = (2 * pos[0] - last_c2[0], 2 * pos[1] - last_c2[1]) if last_c2 else pos
            c2, p = (ox + x2, oy + y2), (ox + x, oy + y)
            seg = ('C', pos, c1, c2, p)
            new_c2 = c2
        elif big == 'Q':
            qx, qy, x, y = nums(4)
            q, p = (ox + qx, oy + qy), (ox + x, oy + y)
            seg = ('C', pos, (pos[0] + 2 / 3 * (q[0] - pos[0]), pos[1] + 2 / 3 * (q[1] - pos[1])),
                   (p[0] + 2 / 3 * (q[0] - p[0]), p[1] + 2 / 3 * (q[1] - p[1])), p)
            new_q = q
        elif big == 'T':
            x, y = nums(2)
            q = (2 * pos[0] - last_q[0], 2 * pos[1] - last_q[1]) if last_q else pos
            p = (ox + x, oy + y)
            seg = ('C', pos, (pos[0] + 2 / 3 * (q[0] - pos[0]), pos[1] + 2 / 3 * (q[1] - pos[1])),
                   (p[0] + 2 / 3 * (q[0] - p[0]), p[1] + 2 / 3 * (q[1] - p[1])), p)
            new_q = q
        else:  # pragma: no cover - tokenizer guarantees the command set
            raise ValueError(f'{name}: unsupported command {cmd}')
        cur['segs'].append(seg)
        nseg += 1
        if nseg > MAX_SEGMENTS:
            raise ValueError(f'{name} has more than {MAX_SEGMENTS} segments')
        pos = seg[-1]
        last_c2, last_q = new_c2, new_q
    subs = [s for s in subs if s['segs']]
    if not subs:
        raise ValueError(f'{name} contains no drawable segments')
    return subs


def _flatten(sub):
    pts = [sub['start']]
    for seg in sub['segs']:
        if seg[0] == 'L':
            pts.append(seg[2])
        else:
            p0, c1, c2, p3 = seg[1:]
            ctrl = _dist(p0, c1) + _dist(c1, c2) + _dist(c2, p3)
            k = max(8, min(96, int(ctrl / 3) + 1))
            for j in range(1, k + 1):
                pts.append(_cubic(p0, c1, c2, p3, j / k))
    return _dedupe(pts)


def _sub_d(sub):
    sx, sy = sub['start']
    parts = [f'M{_fmt(sx)} {_fmt(sy)}']
    for seg in sub['segs']:
        if seg[0] == 'L':
            parts.append(f'L{_fmt(seg[2][0])} {_fmt(seg[2][1])}')
        else:
            _, _, c1, c2, p = seg
            parts.append(f'C{_fmt(c1[0])} {_fmt(c1[1])} {_fmt(c2[0])} {_fmt(c2[1])} '
                         f'{_fmt(p[0])} {_fmt(p[1])}')
    if sub['closed']:
        parts.append('Z')
    return ' '.join(parts)


# --------------------------------------------------------------------------- 1. shape_morph

SHAPE_PRESETS = ('circle', 'square', 'triangle', 'star', 'hexagon', 'heart', 'rose', 'diamond')


def _preset_points(name):
    if name == 'circle':
        return [(math.cos(2 * math.pi * k / 72), math.sin(2 * math.pi * k / 72)) for k in range(72)]
    if name == 'square':
        return [(-1, -1), (1, -1), (1, 1), (-1, 1)]
    if name == 'diamond':
        return [(0, -1), (1, 0), (0, 1), (-1, 0)]
    if name == 'triangle':
        return [(0, -1), (0.866, 0.5), (-0.866, 0.5)]
    if name == 'star':
        return [((1 if k % 2 == 0 else 0.45) * math.cos(-math.pi / 2 + k * math.pi / 5),
                 (1 if k % 2 == 0 else 0.45) * math.sin(-math.pi / 2 + k * math.pi / 5)) for k in range(10)]
    if name == 'hexagon':
        return [(math.cos(-math.pi / 2 + k * math.pi / 3), math.sin(-math.pi / 2 + k * math.pi / 3))
                for k in range(6)]
    if name == 'heart':
        out = []
        for k in range(96):
            a = 2 * math.pi * k / 96
            out.append((16 * math.sin(a) ** 3 / 17,
                        -(13 * math.cos(a) - 5 * math.cos(2 * a) - 2 * math.cos(3 * a) - math.cos(4 * a)) / 17))
        return out
    if name == 'rose':
        out = []
        for k in range(120):
            a = 2 * math.pi * k / 120
            r = 0.62 + 0.38 * math.cos(5 * a)
            out.append((r * math.cos(a - math.pi / 2), r * math.sin(a - math.pi / 2)))
        return out
    raise ValueError(f'unknown shape preset {name!r}')


def _shape_input(value, name):
    """-> (points, closed, is_preset)."""
    if isinstance(value, str):
        if value in SHAPE_PRESETS:
            return [tuple(map(float, p)) for p in _preset_points(value)], True, True
        if value.lstrip()[:1] in ('M', 'm'):
            sub = _parse_path(value, name)[0]
            pts = _flatten(sub)
            if sub['closed'] and len(pts) > 1 and _dist(pts[0], pts[-1]) < 1e-9:
                pts = pts[:-1]
            if len(pts) < 2:
                raise ValueError(f'{name} needs at least 2 distinct points')
            return pts, sub['closed'], False
        raise ValueError(f'{name} must be a preset {list(SHAPE_PRESETS)}, an SVG path or a point list')
    pts = _dedupe(_points(value, name, 3, 2000))
    if len(pts) < 3:
        raise ValueError(f'{name} needs at least 3 distinct points')
    return pts, True, False


def _resample(pts, n, closed):
    ring = pts + [pts[0]] if closed else list(pts)
    cum = [0.0]
    for i in range(len(ring) - 1):
        cum.append(cum[-1] + _dist(ring[i], ring[i + 1]))
    total = cum[-1]
    if total < 1e-12:
        return [pts[0]] * n
    out = []
    j = 0
    for k in range(n):
        s = total * k / n if closed else total * k / max(1, n - 1)
        while j < len(ring) - 2 and cum[j + 1] < s:
            j += 1
        seg = cum[j + 1] - cum[j]
        f = 0.0 if seg < 1e-12 else _clamp((s - cum[j]) / seg)
        out.append((_lerp(ring[j][0], ring[j + 1][0], f), _lerp(ring[j][1], ring[j + 1][1], f)))
    return out


def _fit(pts, cx, cy, size):
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    bw, bh = max(xs) - min(xs), max(ys) - min(ys)
    m = max(bw, bh)
    if m < 1e-12:
        raise ValueError('shape has zero size')
    sc = size / m
    mx, my = (max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2
    return [(cx + (x - mx) * sc, cy + (y - my) * sc) for x, y in pts]


def _signed_area(pts):
    return sum(pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1]
               for i in range(len(pts))) / 2


def _align(a, b, closed):
    """Return (b_aligned, shift, reversed, mean_sq_distance)."""
    n = len(a)
    reversed_ = False
    if closed:
        if _signed_area(a) * _signed_area(b) < 0:
            b = [b[0]] + b[:0:-1]
            reversed_ = True
        best_d, best_s = None, 0
        for s in range(n):
            d = 0.0
            for k in range(n):
                bx, by = b[(k + s) % n]
                ax, ay = a[k]
                d += (ax - bx) ** 2 + (ay - by) ** 2
                if best_d is not None and d >= best_d:
                    break
            if best_d is None or d < best_d:
                best_d, best_s = d, s
        return [b[(k + best_s) % n] for k in range(n)], best_s, reversed_, best_d / n
    fwd = sum((p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2 for p, q in zip(a, b))
    rb = b[::-1]
    rev = sum((p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2 for p, q in zip(a, rb))
    if rev < fwd:
        return rb, 0, True, rev / n
    return b, 0, False, fwd / n


def _cfg_shape_morph(*, from_shape='circle', to_shape='star', points=96, easing='ease_in_out',
                     duration=2.0, delay=0.0, yoyo=False, fit=True, center=None, size=None,
                     fill='#c8102e', stroke='none', stroke_width=0.0, opacity=1.0, **extra):
    _no_extra(extra)
    a = _shape_input(from_shape, 'from_shape')
    b = _shape_input(to_shape, 'to_shape')
    return {
        'a': a, 'b': b, 'n': _int(points, 8, 512, 'points'), 'easing': _easing(easing),
        'duration': _num(duration, 0.01, 3600, 'duration'), 'delay': _num(delay, 0, MAX_T, 'delay'),
        'yoyo': _bool(yoyo, 'yoyo'), 'fit': _bool(fit, 'fit'),
        'center': None if center is None else _vec(center, 2, 'center', -MAX_CANVAS, 2 * MAX_CANVAS),
        'size': None if size is None else _num(size, 1, MAX_CANVAS, 'size'),
        'fill': _color(fill, 'fill', True), 'stroke': _color(stroke, 'stroke', True),
        'stroke_width': _num(stroke_width, 0, 200, 'stroke_width'),
        'opacity': _num(opacity, 0, 1, 'opacity'),
    }


def _render_shape_morph(c, t, w, h, pid):
    cx, cy = c['center'] if c['center'] else (w / 2, h / 2)
    size = c['size'] or 0.6 * min(w, h)
    shapes = []
    for pts, closed, preset in (c['a'], c['b']):
        if preset or c['fit']:
            pts = _fit(pts, cx, cy, size)
        shapes.append((pts, closed))
    closed = shapes[0][1] and shapes[1][1]
    n = c['n']
    a = _resample(shapes[0][0], n, closed)
    b = _resample(shapes[1][0], n, closed)
    b, shift, rev, msd = _align(a, b, closed)
    p = _progress(t, c['delay'], c['duration'])
    if c['yoyo']:
        p = p * 2 if p < 0.5 else 2 - 2 * p
    e = _ease(c['easing'], p)
    pts = [(_lerp(pa[0], pb[0], e), _lerp(pa[1], pb[1], e)) for pa, pb in zip(a, b)]
    sw = f' stroke-width="{_fmt(c["stroke_width"])}" stroke-linejoin="round"' if c['stroke'] != 'none' else ''
    svg = (f'<g id="{pid}-morph" opacity="{_fo(c["opacity"])}"><path d="{_path_d(pts, closed)}" '
           f'fill="{c["fill"]}" stroke="{c["stroke"]}"{sw}/></g>')
    return svg, {'progress': p, 'eased': e, 'points': n, 'closed': closed,
                 'start_shift': shift, 'reversed_target': rev,
                 'mean_sq_alignment_distance': msd}


# --------------------------------------------------------------------------- 2. draw_on

def _cfg_draw_on(*, path=None, points=None, closed=False, duration=2.0, delay=0.0,
                 easing='ease_in_out', stroke='#ffffff', stroke_width=6.0, style='clean',
                 jitter=2.0, seed=7, passes=2, fill='none', opacity=1.0, **extra):
    _no_extra(extra)
    if path is not None and points is not None:
        raise ValueError('give either path or points, not both')
    closed = _bool(closed, 'closed')
    subs = None
    if path is not None:
        subs = _parse_path(path, 'path')
    elif points is not None:
        pts = _dedupe(_points(points, 'points', 2, 4000))
        if len(pts) < 2:
            raise ValueError('points needs at least 2 distinct points')
        segs = [('L', pts[i], pts[i + 1]) for i in range(len(pts) - 1)]
        if closed:
            segs.append(('L', pts[-1], pts[0]))
        subs = [{'start': pts[0], 'segs': segs, 'closed': closed}]
    return {
        'subs': subs, 'duration': _num(duration, 0.01, 3600, 'duration'),
        'delay': _num(delay, 0, MAX_T, 'delay'), 'easing': _easing(easing),
        'stroke': _color(stroke, 'stroke'), 'stroke_width': _num(stroke_width, 0.1, 200, 'stroke_width'),
        'style': _choice(style, {'clean', 'marker'}, 'style'),
        'jitter': _num(jitter, 0, 20, 'jitter'), 'seed': _seed(seed),
        'passes': _int(passes, 1, 3, 'passes'), 'fill': _color(fill, 'fill', True),
        'opacity': _num(opacity, 0, 1, 'opacity'),
    }


def _default_draw_path(w, h):
    return (f'M{_fmt(0.14 * w)} {_fmt(0.58 * h)} C{_fmt(0.26 * w)} {_fmt(0.22 * h)} '
            f'{_fmt(0.40 * w)} {_fmt(0.88 * h)} {_fmt(0.52 * w)} {_fmt(0.52 * h)} '
            f'S{_fmt(0.76 * w)} {_fmt(0.22 * h)} {_fmt(0.86 * w)} {_fmt(0.46 * h)} '
            f'M{_fmt(0.22 * w)} {_fmt(0.72 * h)} L{_fmt(0.78 * w)} {_fmt(0.70 * h)}')


def _densify(pts, closed, max_pts=6000):
    ring = pts + [pts[0]] if closed else pts
    total = _poly_len(ring)
    spacing = max(4.0, total / max_pts)
    out = [ring[0]]
    for i in range(len(ring) - 1):
        a, b = ring[i], ring[i + 1]
        L = _dist(a, b)
        k = max(1, int(math.ceil(L / spacing)))
        for j in range(1, k + 1):
            out.append((_lerp(a[0], b[0], j / k), _lerp(a[1], b[1], j / k)))
    return out


def _jitter_poly(pts, amount, seed, chan):
    out = []
    s = 0.0
    n = len(pts)
    for k in range(n):
        if k:
            s += _dist(pts[k - 1], pts[k])
        a = pts[max(0, k - 1)]
        b = pts[min(n - 1, k + 1)]
        dx, dy = b[0] - a[0], b[1] - a[1]
        L = math.hypot(dx, dy) or 1.0
        nx, ny = -dy / L, dx / L
        off = amount * (0.75 * _vnoise(seed, chan, s / 45.0) + 0.25 * _vnoise(seed, chan + 50, s / 9.0))
        out.append((pts[k][0] + nx * off, pts[k][1] + ny * off))
    return out


def _dash_attrs(length, drawn):
    dl = length + 1.0
    return f'stroke-dasharray="{_fmt(dl)} {_fmt(dl)}" stroke-dashoffset="{_fmt(dl - drawn)}"'


def _render_draw_on(c, t, w, h, pid):
    subs = c['subs'] if c['subs'] is not None else _parse_path(_default_draw_path(w, h), 'path')
    polys = [_flatten(s) for s in subs]
    lens = [_poly_len(p) for p in polys]
    total = sum(lens)
    if total < 1e-9:
        raise ValueError('path has zero length')
    p = _progress(t, c['delay'], c['duration'])
    e = _ease(c['easing'], p)
    s_drawn = e * total
    parts = [f'<g id="{pid}-draw" opacity="{_fo(c["opacity"])}" fill="none" stroke-linecap="round" '
             f'stroke-linejoin="round">']
    if c['fill'] != 'none' and p > 0.85:
        fill_d = ' '.join(_sub_d(s) for s in subs)
        parts.append(f'<path d="{fill_d}" fill="{c["fill"]}" stroke="none" '
                     f'opacity="{_fo((p - 0.85) / 0.15)}"/>')
    offset = 0.0
    for idx, (sub, poly, L) in enumerate(zip(subs, polys, lens)):
        drawn = _clamp(s_drawn - offset, 0.0, L)
        offset += L
        if drawn <= 0.01:
            continue
        frac = drawn / L if L > 0 else 1.0
        if c['style'] == 'clean':
            parts.append(f'<path d="{_sub_d(sub)}" stroke="{c["stroke"]}" '
                         f'stroke-width="{_fmt(c["stroke_width"])}" {_dash_attrs(L, drawn)}/>')
        else:
            dense = _densify(poly, False)  # closing segment is already part of the flattened polyline
            for j in range(c['passes']):
                jp = _jitter_poly(dense, c['jitter'] * (1 + 0.6 * j), c['seed'], idx * 7 + j)
                Lj = _poly_len(jp)
                op = (0.95, 0.55, 0.35)[j]
                sw = c['stroke_width'] * (1 - 0.12 * j)
                parts.append(f'<path d="{_path_d(jp)}" stroke="{c["stroke"]}" stroke-width="{_fmt(sw)}" '
                             f'opacity="{_fo(op)}" {_dash_attrs(Lj, frac * Lj)}/>')
    parts.append('</g>')
    return ''.join(parts), {'progress': p, 'eased': e, 'total_length': total,
                            'subpath_lengths': lens, 'drawn_length': s_drawn, 'style': c['style']}


# --------------------------------------------------------------------------- 3. neon_glow

def _cfg_neon_glow(*, text='ROSE', color='#ff2d55', font_size=None, font_family=DEFAULT_FONT,
                   font_weight=700, x=None, y=None, glow=False, glow_strength=0.5,
                   flicker_rate=0.06, flicker_hz=12.0, power_on=0.6, broken_letter=-1, seed=3,
                   show_tube=True, tube_color='#2a2a2e', **extra):
    _no_extra(extra)
    text = _str(text, 'text', 60, allow_empty=False)
    broken_letter = _int(broken_letter, -1, len(text) - 1, 'broken_letter')
    if broken_letter >= 0:
        if not _is_latin(text) or _has_arabic(text):
            raise ValueError('broken_letter works only for Latin text (per-letter split would break Arabic shaping)')
        if text[broken_letter].isspace():
            raise ValueError('broken_letter must point at a visible letter, not a space')
    return {
        'text': text, 'color': _color(color, 'color'),
        'font_size': None if font_size is None else _num(font_size, 4, 2000, 'font_size'),
        'font_family': _font(font_family), 'font_weight': _int(font_weight, 100, 900, 'font_weight'),
        'x': None if x is None else _num(x, -MAX_CANVAS, 2 * MAX_CANVAS, 'x'),
        'y': None if y is None else _num(y, -MAX_CANVAS, 2 * MAX_CANVAS, 'y'),
        'glow': _bool(glow, 'glow'), 'glow_strength': _num(glow_strength, 0, 1, 'glow_strength'),
        'flicker_rate': _num(flicker_rate, 0, 0.5, 'flicker_rate'),
        'flicker_hz': _num(flicker_hz, 4, 30, 'flicker_hz'),
        'power_on': _num(power_on, 0, 10, 'power_on'), 'broken_letter': broken_letter,
        'seed': _seed(seed), 'show_tube': _bool(show_tube, 'show_tube'),
        'tube_color': _color(tube_color, 'tube_color'),
    }


def _neon_level(c, t):
    slot = math.floor(t * c['flicker_hz'])
    if c['power_on'] > 0 and t < c['power_on']:
        return 1.0 if _h01(c['seed'], 3, slot) < (t / c['power_on']) ** 0.7 else 0.08
    if _h01(c['seed'], 1, slot) < c['flicker_rate']:
        return 0.25 + 0.35 * _h01(c['seed'], 2, slot)
    return 1.0


def _render_neon_glow(c, t, w, h, pid):
    fs = c['font_size'] or 0.18 * h
    x = w / 2 if c['x'] is None else c['x']
    y = h / 2 if c['y'] is None else c['y']
    level = _neon_level(c, t)
    rtl = _has_arabic(c['text'])
    core = _mix_hex(c['color'], '#ffffff', 0.55)
    sw = fs * 0.05
    common = (f'x="{_fmt(x)}" y="{_fmt(y)}" font-family="{_esc(c["font_family"])}" '
              f'font-size="{_fmt(fs)}" font-weight="{c["font_weight"]}" text-anchor="middle" '
              f'dominant-baseline="central"' + (' direction="rtl" unicode-bidi="embed"' if rtl else ''))
    parts = [f'<g id="{pid}-neon">']
    if c['glow'] and c['glow_strength'] > 0:
        k = 0.4 + 0.6 * c['glow_strength']
        sds = (fs * 0.03 * k, fs * 0.08 * k, fs * 0.18 * k)
        slopes = [min(0.85, (0.85, 0.6, 0.4)[i] * c['glow_strength'] + 0.05) for i in range(3)]
        prim = ''.join(f'<feGaussianBlur in="SourceGraphic" stdDeviation="{_fmt(max(sd, 0.01))}" result="b{i}"/>'
                       for i, sd in enumerate(sds))
        prim += ''.join(f'<feComponentTransfer in="b{i}" result="c{i}"><feFuncA type="linear" '
                        f'slope="{_fo(sl)}"/></feComponentTransfer>' for i, sl in enumerate(slopes))
        prim += ('<feMerge><feMergeNode in="c2"/><feMergeNode in="c1"/><feMergeNode in="c0"/>'
                 '<feMergeNode in="SourceGraphic"/></feMerge>')
        parts.append(f'<defs><filter id="{pid}-glow" x="-50%" y="-80%" width="200%" height="260%" '
                     f'color-interpolation-filters="sRGB">{prim}</filter></defs>')
    if c['show_tube']:
        parts.append(f'<text {common} fill="none" stroke="{c["tube_color"]}" '
                     f'stroke-width="{_fmt(sw)}">{_esc(c["text"])}</text>')
    filt = f' filter="url(#{pid}-glow)"' if c['glow'] and c['glow_strength'] > 0 else ''
    broken_level = None
    if c['broken_letter'] >= 0:
        slot = math.floor(t * c['flicker_hz'] * 1.5)
        broken_level = (0.05 + 0.25 * _h01(c['seed'], 5, slot)) if _h01(c['seed'], 4, slot) < 0.55 else 0.9
        spans = []
        for i, ch in enumerate(c['text']):
            if i == c['broken_letter']:
                spans.append(f'<tspan fill-opacity="{_fo(broken_level)}" stroke-opacity="{_fo(broken_level)}">'
                             f'{_esc(ch)}</tspan>')
            else:
                spans.append(f'<tspan>{_esc(ch)}</tspan>')
        content = ''.join(spans)
    else:
        content = _esc(c['text'])
    parts.append(f'<text {common} fill="{core}" stroke="{c["color"]}" stroke-width="{_fmt(sw)}" '
                 f'stroke-linejoin="round" opacity="{_fo(level)}"{filt}>{content}</text>')
    parts.append('</g>')
    return ''.join(parts), {'level': level, 'glow': bool(filt), 'broken_letter_level': broken_level,
                            'flicker_slot': math.floor(t * c['flicker_hz']), 'rtl': rtl,
                            'font_size': fs}


# --------------------------------------------------------------------------- 4. textures

TEXTURE_OVERLAYS = ('grain', 'paper', 'halftone', 'scanlines', 'vignette')


def _cfg_textures(*, overlays=(), grain_amount=0.08, grain_fps=12.0, grain_scale=0.9,
                  paper_amount=0.12, halftone_spacing=8.0, halftone_angle=45.0,
                  halftone_amount=0.15, halftone_color='#000000', scanline_spacing=3.0,
                  scanline_amount=0.12, vignette_amount=0.18, seed=11, **extra):
    _no_extra(extra)
    if not isinstance(overlays, (list, tuple)) or len(overlays) > len(TEXTURE_OVERLAYS):
        raise ValueError(f'overlays must be a list drawn from {list(TEXTURE_OVERLAYS)}')
    chosen = []
    for i, o in enumerate(overlays):
        _choice(o, set(TEXTURE_OVERLAYS), f'overlays[{i}]')
        if o in chosen:
            raise ValueError(f'overlay {o!r} listed twice')
        chosen.append(o)
    return {
        'overlays': chosen, 'grain_amount': _num(grain_amount, 0, 0.3, 'grain_amount'),
        'grain_fps': _num(grain_fps, 1, 30, 'grain_fps'), 'grain_scale': _num(grain_scale, 0.2, 2, 'grain_scale'),
        'paper_amount': _num(paper_amount, 0, 0.4, 'paper_amount'),
        'halftone_spacing': _num(halftone_spacing, 3, 64, 'halftone_spacing'),
        'halftone_angle': _num(halftone_angle, -90, 90, 'halftone_angle'),
        'halftone_amount': _num(halftone_amount, 0, 0.5, 'halftone_amount'),
        'halftone_color': _color(halftone_color, 'halftone_color'),
        'scanline_spacing': _num(scanline_spacing, 2, 16, 'scanline_spacing'),
        'scanline_amount': _num(scanline_amount, 0, 0.4, 'scanline_amount'),
        'vignette_amount': _num(vignette_amount, 0, 0.35, 'vignette_amount'), 'seed': _seed(seed),
    }


def _render_textures(c, t, w, h, pid):
    if not c['overlays']:
        return '', {'overlays': [], 'note': 'no overlay requested; overlays are off unless named in overlays'}
    W, H = _fmt(w), _fmt(h)
    defs, layers = [], []
    meta = {'overlays': list(c['overlays'])}
    for o in c['overlays']:
        if o == 'grain':
            step = math.floor(t * c['grain_fps'])
            gseed = (c['seed'] * 7919 + step) % 100000
            defs.append(f'<filter id="{pid}-grain" filterUnits="userSpaceOnUse" x="0" y="0" width="{W}" '
                        f'height="{H}"><feTurbulence type="fractalNoise" baseFrequency="{_fo(c["grain_scale"]) if c["grain_scale"] <= 1 else _fmt(c["grain_scale"])}" '
                        f'numOctaves="2" seed="{gseed}" stitchTiles="stitch" result="n"/>'
                        f'<feColorMatrix in="n" type="saturate" values="0"/></filter>')
            layers.append(f'<rect x="0" y="0" width="{W}" height="{H}" filter="url(#{pid}-grain)" '
                          f'opacity="{_fo(c["grain_amount"])}" style="mix-blend-mode:overlay"/>')
            meta['grain_seed'] = gseed
            meta['grain_step'] = step
        elif o == 'paper':
            defs.append(f'<filter id="{pid}-paper" filterUnits="userSpaceOnUse" x="0" y="0" width="{W}" '
                        f'height="{H}"><feTurbulence type="fractalNoise" baseFrequency="0.04" numOctaves="4" '
                        f'seed="{c["seed"] % 100000}" result="n"/><feDiffuseLighting in="n" surfaceScale="2" '
                        f'lighting-color="#ffffff"><feDistantLight azimuth="45" elevation="60"/>'
                        f'</feDiffuseLighting></filter>')
            layers.append(f'<rect x="0" y="0" width="{W}" height="{H}" filter="url(#{pid}-paper)" '
                          f'opacity="{_fo(c["paper_amount"])}" style="mix-blend-mode:multiply"/>')
        elif o == 'halftone':
            sp = c['halftone_spacing']
            defs.append(f'<pattern id="{pid}-dots" patternUnits="userSpaceOnUse" width="{_fmt(sp)}" '
                        f'height="{_fmt(sp)}" patternTransform="rotate({_fmt(c["halftone_angle"])})">'
                        f'<circle cx="{_fmt(sp / 2)}" cy="{_fmt(sp / 2)}" r="{_fmt(sp * 0.3)}" '
                        f'fill="{c["halftone_color"]}"/></pattern>')
            layers.append(f'<rect x="0" y="0" width="{W}" height="{H}" fill="url(#{pid}-dots)" '
                          f'opacity="{_fo(c["halftone_amount"])}" style="mix-blend-mode:multiply"/>')
        elif o == 'scanlines':
            sp = c['scanline_spacing']
            defs.append(f'<pattern id="{pid}-scan" patternUnits="userSpaceOnUse" width="{_fmt(sp)}" '
                        f'height="{_fmt(sp)}"><rect x="0" y="{_fmt(sp / 2)}" width="{_fmt(sp)}" '
                        f'height="{_fmt(sp / 2)}" fill="#000000"/></pattern>')
            layers.append(f'<rect x="0" y="0" width="{W}" height="{H}" fill="url(#{pid}-scan)" '
                          f'opacity="{_fo(c["scanline_amount"])}"/>')
        elif o == 'vignette':
            defs.append(f'<radialGradient id="{pid}-vig" cx="50%" cy="50%" r="75%">'
                        f'<stop offset="0.55" stop-color="#000000" stop-opacity="0"/>'
                        f'<stop offset="1" stop-color="#000000" stop-opacity="{_fo(c["vignette_amount"])}"/>'
                        f'</radialGradient>')
            layers.append(f'<rect x="0" y="0" width="{W}" height="{H}" fill="url(#{pid}-vig)"/>')
    svg = f'<g id="{pid}-tex" pointer-events="none"><defs>{"".join(defs)}</defs>{"".join(layers)}</g>'
    return svg, meta


# --------------------------------------------------------------------------- 5. particles_svg

PARTICLE_KINDS = ('dust', 'confetti', 'rain', 'snow', 'sparks')
_CONFETTI = ('#ff3b5c', '#ffd166', '#06d6a0', '#4cc9f0', '#b388ff', '#ffffff')


def _cfg_particles(*, kind='snow', count=160, seed=5, wind=0.0, speed_scale=1.0, size_scale=1.0,
                   color=None, palette=None, rain_angle=12.0, emitter=None, opacity=1.0, **extra):
    _no_extra(extra)
    kind = _choice(kind, set(PARTICLE_KINDS), 'kind')
    pal = None
    if palette is not None:
        if not isinstance(palette, (list, tuple)) or not 1 <= len(palette) <= 12:
            raise ValueError('palette must be a list of 1..12 hex colours')
        pal = [_color(p, f'palette[{i}]') for i, p in enumerate(palette)]
    return {
        'kind': kind, 'count': _int(count, 1, 800, 'count'), 'seed': _seed(seed),
        'wind': _num(wind, -400, 400, 'wind'), 'speed': _num(speed_scale, 0.1, 5, 'speed_scale'),
        'size': _num(size_scale, 0.2, 5, 'size_scale'),
        'color': None if color is None else _color(color, 'color'), 'palette': pal,
        'rain_angle': _num(rain_angle, 10, 15, 'rain_angle'),
        'emitter': None if emitter is None else _vec(emitter, 2, 'emitter', -MAX_CANVAS, 2 * MAX_CANVAS),
        'opacity': _num(opacity, 0, 1, 'opacity'),
    }


def _render_particles(c, t, w, h, pid):
    k, sd, n = c['kind'], c['seed'], c['count']
    out = []
    for i in range(n):
        r = [_h01(sd, i, j) for j in range(8)]
        if k == 'snow':
            rad = (1.2 + 2.8 * r[0]) * c['size']
            vy = (30 + 50 * r[1]) * c['speed']
            amp = 10 + 20 * r[2]
            y = _wrap(r[3] * (h + 20) - 10 + vy * t, -10, h + 10)
            x = _wrap(r[4] * (w + 20) - 10 + c['wind'] * t * (0.5 + 0.5 * r[0])
                      + amp * math.sin(2 * math.pi * (0.2 + 0.5 * r[5]) * t + 6.283 * r[6]), -10, w + 10)
            out.append(f'<circle cx="{_fmt(x)}" cy="{_fmt(y)}" r="{_fmt(rad)}" '
                       f'fill="{c["color"] or "#ffffff"}" opacity="{_fo(0.55 + 0.45 * r[7])}"/>')
        elif k == 'dust':
            rad = (0.6 + 1.4 * r[0]) * c['size']
            ang = 2 * math.pi * r[1]
            sp = (4 + 12 * r[2]) * c['speed']
            x = _wrap(r[3] * w + (math.cos(ang) * sp + c['wind'] * 0.3) * t, -4, w + 4)
            y = _wrap(r[4] * h + math.sin(ang) * sp * t, -4, h + 4)
            tw = 0.5 + 0.5 * math.sin(2 * math.pi * (0.3 + 0.6 * r[5]) * t + 6.283 * r[6])
            out.append(f'<circle cx="{_fmt(x)}" cy="{_fmt(y)}" r="{_fmt(rad)}" '
                       f'fill="{c["color"] or "#f5e6c8"}" opacity="{_fo(0.12 + 0.38 * tw)}"/>')
        elif k == 'rain':
            sign = -1.0 if c['wind'] < 0 else 1.0
            tan_a = math.tan(math.radians(c['rain_angle']))
            ln = (18 + 20 * r[0]) * c['size']
            v = (900 + 500 * r[1]) * c['speed']
            span = h + 2 * ln
            d = (r[2] * span + v * t) % span
            yh = d - ln
            x0 = (r[3] * (w + span * tan_a)) - (span * tan_a if sign > 0 else 0)
            xh = x0 + sign * d * tan_a
            ux, uy = sign * math.sin(math.radians(c['rain_angle'])), math.cos(math.radians(c['rain_angle']))
            out.append(f'<line x1="{_fmt(xh - ux * ln)}" y1="{_fmt(yh - uy * ln)}" x2="{_fmt(xh)}" '
                       f'y2="{_fmt(yh)}" stroke="{c["color"] or "#a9c4e8"}" '
                       f'stroke-width="{_fmt(1.2 * c["size"])}" opacity="{_fo(0.35 + 0.4 * r[4])}"/>')
        elif k == 'confetti':
            pal = c['palette'] or ([c['color']] if c['color'] else list(_CONFETTI))
            col = pal[int(r[0] * len(pal)) % len(pal)]
            vy = (80 + 100 * r[1]) * c['speed']
            pw, ph = (6 + 6 * r[2]) * c['size'], (4 + 4 * r[3]) * c['size']
            y = _wrap(r[4] * (h + 40) - 20 + vy * t, -20, h + 20)
            x = _wrap(r[5] * w + c['wind'] * t + 18 * math.sin(2 * math.pi * 0.6 * t + 6.283 * r[6]), -20, w + 20)
            rot = 360 * r[7] + (120 + 240 * r[1]) * t * (1 if r[2] > 0.5 else -1)
            flip = abs(math.cos(2 * math.pi * (0.8 + 1.2 * r[3]) * t + 6.283 * r[0]))
            out.append(f'<rect x="{_fmt(-pw / 2)}" y="{_fmt(-ph / 2)}" width="{_fmt(pw)}" '
                       f'height="{_fmt(max(0.4, ph * flip))}" fill="{col}" '
                       f'transform="translate({_fmt(x)} {_fmt(y)}) rotate({_fmt(rot % 360)})"/>')
        else:  # sparks
            ex, ey = c['emitter'] if c['emitter'] else (w / 2, h * 0.75)
            life = 0.6 + 0.8 * r[0]
            tt = t + r[1] * life
            cycle = math.floor(tt / life)
            age = tt - cycle * life
            q = [_h01(sd, i, cycle, j) for j in range(4)]
            ang = math.radians(-90 + (q[0] - 0.5) * 100)
            sp = (150 + 300 * q[1]) * c['speed']
            vx, vy = math.cos(ang) * sp + c['wind'] * 0.5, math.sin(ang) * sp
            g = 600.0
            x = ex + vx * age
            y = ey + vy * age + 0.5 * g * age * age
            cvx, cvy = vx, vy + g * age
            fade = (1 - age / life) ** 1.5
            col = c['color'] or _mix_hex('#fff3b0', '#ff6a00', age / life)
            out.append(f'<line x1="{_fmt(x - cvx * 0.03)}" y1="{_fmt(y - cvy * 0.03)}" x2="{_fmt(x)}" '
                       f'y2="{_fmt(y)}" stroke="{col}" stroke-width="{_fmt((1 + 1.5 * q[2]) * c["size"])}" '
                       f'stroke-linecap="round" opacity="{_fo(fade)}"/>')
    svg = f'<g id="{pid}-particles" opacity="{_fo(c["opacity"])}">{"".join(out)}</g>'
    return svg, {'kind': k, 'count': n, 'seed': sd}


# --------------------------------------------------------------------------- 6. data_viz

CHART_TYPES = ('bar', 'bar_race', 'line', 'donut', 'ring', 'stacked', 'counter', 'histogram', 'scatter')

_RELATIONSHIPS = {
    'trend': ('line', 'التغيّر عبر الزمن يُقرأ أوضح كخط متصل'),
    'ranking': ('bar', 'الترتيب يُقرأ أوضح كأعمدة أفقية مرتبة'),
    'ranking_over_time': ('bar_race', 'تغيّر الترتيب عبر الزمن يُعرض كسباق أعمدة'),
    'composition': ('donut', 'أجزاء من كل (حتى 5 أجزاء) تُعرض كحلقة'),
    'distribution': ('histogram', 'توزيع القيم يُعرض كمدرج تكراري'),
    'correlation': ('scatter', 'العلاقة بين متغيرين تُعرض كنقاط مبعثرة'),
    'progress': ('ring', 'نسبة الإنجاز تُعرض كحلقة تقدم'),
    'kpi': ('counter', 'الأرقام المفردة المهمة تُعرض كبطاقات عدّاد'),
}

_REL_SYNONYMS = {
    'time': 'trend', 'over_time': 'trend', 'timeline': 'trend', 'اتجاه': 'trend', 'زمن': 'trend',
    'rank': 'ranking', 'comparison': 'ranking', 'compare': 'ranking', 'ترتيب': 'ranking', 'مقارنة': 'ranking',
    'race': 'ranking_over_time', 'سباق': 'ranking_over_time',
    'part_to_whole': 'composition', 'share': 'composition', 'تركيب': 'composition', 'نسب': 'composition',
    'spread': 'distribution', 'توزيع': 'distribution',
    'relationship': 'correlation', 'ارتباط': 'correlation', 'علاقة': 'correlation',
    'تقدم': 'progress', 'إنجاز': 'progress', 'counter': 'kpi', 'عداد': 'kpi', 'مؤشر': 'kpi',
}


def choose_chart(relationship, n_parts=None):
    """Pick the chart type from the data relationship.

    trend -> line, ranking -> bar, ranking_over_time -> bar_race,
    composition -> donut (<= 5 parts) or stacked (> 5 parts), distribution -> histogram,
    correlation -> scatter, progress -> ring, kpi -> counter. Arabic synonyms accepted.
    """
    if not isinstance(relationship, str):
        raise ValueError('relationship must be a string')
    key = relationship.strip().lower().replace(' ', '_').replace('-', '_')
    key = _REL_SYNONYMS.get(key, key)
    if key not in _RELATIONSHIPS:
        raise ValueError(f'relationship must be one of {sorted(_RELATIONSHIPS)} (or a known synonym)')
    if n_parts is not None:
        n_parts = _int(n_parts, 1, 1000, 'n_parts')
    if key == 'composition' and n_parts is not None and n_parts > 5:
        return 'stacked'
    return _RELATIONSHIPS[key][0]


_DV_PALETTE = ('#ff3b5c', '#ffd166', '#06d6a0', '#4cc9f0', '#b388ff', '#ff8c42', '#9aa3b2', '#f72585')


def _cfg_data_viz(*, chart='auto', relationship='ranking', labels=None, values=None, timeline=None,
                  periods=None, points=None, title='', duration=2.0, delay=0.0, easing='ease_out',
                  palette=None, rtl='auto', digits='latin', decimals=0, suffix='', bins=8, top_n=None,
                  font_family=DEFAULT_FONT, text_color='#ffffff', grid_color='#5b6270', seed=9, **extra):
    _no_extra(extra)
    chart = _choice(chart, set(CHART_TYPES) | {'auto'}, 'chart')
    if chart == 'auto':
        n_parts = len(values) if isinstance(values, (list, tuple)) and values else None
        chart = choose_chart(relationship, n_parts)
    c = {
        'chart': chart, 'title': _str(title, 'title', 80), 'duration': _num(duration, 0.01, 3600, 'duration'),
        'delay': _num(delay, 0, MAX_T, 'delay'), 'easing': _easing(easing), 'rtl': _rtl_flag(rtl),
        'digits': _choice(digits, {'latin', 'arabic'}, 'digits'), 'decimals': _int(decimals, 0, 3, 'decimals'),
        'suffix': _str(suffix, 'suffix', 8), 'bins': _int(bins, 2, 40, 'bins'),
        'font_family': _font(font_family), 'text_color': _color(text_color, 'text_color'),
        'grid_color': _color(grid_color, 'grid_color'), 'seed': _seed(seed),
    }
    if palette is not None:
        if not isinstance(palette, (list, tuple)) or not 1 <= len(palette) <= 12:
            raise ValueError('palette must be a list of 1..12 hex colours')
        c['palette'] = [_color(p, f'palette[{i}]') for i, p in enumerate(palette)]
    else:
        c['palette'] = list(_DV_PALETTE)
    if chart == 'scatter':
        if points is None:
            rnd = random.Random(c['seed'])
            pts = []
            for _ in range(40):
                x = rnd.uniform(0, 100)
                pts.append((x, 0.7 * x + rnd.gauss(0, 12)))
        else:
            pts = _points(points, 'points', 2, 500)
        c['points'] = pts
        if labels is not None or values is not None or timeline is not None:
            raise ValueError('scatter uses points only')
    elif chart == 'bar_race':
        if values is not None or points is not None:
            raise ValueError('bar_race uses labels + timeline (rows of values), not values/points')
        if timeline is None:
            labels = labels or ['Alpha', 'Beta', 'Gamma', 'Delta', 'Epsilon']
            timeline = [[10, 8, 6, 4, 2], [12, 15, 7, 9, 3], [14, 18, 16, 10, 9], [15, 20, 26, 12, 19]]
        if not isinstance(timeline, (list, tuple)) or not 2 <= len(timeline) <= 60:
            raise ValueError('timeline must be a list of 2..60 rows')
        labels = _strlist(labels if labels is not None else [str(i + 1) for i in range(len(timeline[0]) if isinstance(timeline[0], (list, tuple)) else 0)],
                          'labels', 2, 24)
        c['timeline'] = [_numlist(row, f'timeline[{k}]', len(labels), len(labels), 0, 1e12)
                         for k, row in enumerate(timeline)]
        c['labels'] = labels
        if periods is None:
            periods = [str(k + 1) for k in range(len(timeline))]
        c['periods'] = _strlist(periods, 'periods', len(timeline), len(timeline), 24)
        c['top_n'] = len(labels) if top_n is None else _int(top_n, 1, len(labels), 'top_n')
    else:
        if points is not None or timeline is not None:
            raise ValueError(f'{chart} uses labels/values only')
        defaults = {
            'bar': (['القاهرة', 'الإسكندرية', 'الجيزة', 'أسوان'], [42, 31, 27, 12]),
            'line': (['يناير', 'فبراير', 'مارس', 'أبريل', 'مايو', 'يونيو', 'يوليو'], [3, 5, 4, 7, 9, 8, 12]),
            'donut': (['فيديو', 'صوت', 'تصميم'], [50, 30, 20]),
            'stacked': (['فيديو', 'صوت', 'تصميم', 'نص', 'أخرى', 'إضاءة'], [30, 20, 18, 14, 10, 8]),
            'ring': (['الإنجاز'], [0.72]),
            'counter': (['مشاهدات', 'متابعون', 'إعجابات'], [125000, 8400, 23100]),
        }
        if chart == 'histogram':
            if values is None:
                rnd = random.Random(c['seed'])
                values = [rnd.gauss(50, 15) for _ in range(120)]
            c['values'] = _numlist(values, 'values', 2, 5000)
            c['labels'] = []
        else:
            if values is None:
                dl, dv = defaults[chart]
                values = dv
                if labels is None:
                    labels = dl
            limits = {'bar': (1, 24), 'line': (2, 500), 'donut': (1, 12), 'stacked': (1, 12),
                      'ring': (1, 1), 'counter': (1, 6)}[chart]
            low = -1e12 if chart == 'line' else 0
            high = 1 if chart == 'ring' else 1e12
            c['values'] = _numlist(values, 'values', limits[0], limits[1], low, high)
            if labels is None:
                labels = [str(i + 1) for i in range(len(c['values']))]
            c['labels'] = _strlist(labels, 'labels', len(c['values']), len(c['values']))
            if chart in ('donut', 'stacked') and sum(c['values']) <= 0:
                raise ValueError('values must sum to more than 0')
    return c


def _dv_rtl(c):
    if c['rtl'] == 'auto':
        return any(_has_arabic(s) for s in c.get('labels', []) + [c['title']])
    return c['rtl']


def _render_data_viz(c, t, w, h, pid):
    p = _progress(t, c['delay'], c['duration'])
    e = _ease(c['easing'], p)
    rtl = _dv_rtl(c)
    fs = min(w, h) * 0.034
    ff = c['font_family']
    tc = c['text_color']
    top = h * (0.17 if c['title'] else 0.09)
    x0, x1, y0, y1 = w * 0.08, w * 0.92, top, h * 0.9
    parts = [f'<g id="{pid}-chart">']
    if c['title']:
        parts.append(_txt(w / 2, h * 0.08, c['title'], fs * 1.5, tc, ff=ff, weight=700))
    fv = lambda v: _fmt_value(v, c['decimals'], c['digits'], c['suffix'])
    chart = c['chart']
    pal = c['palette']
    meta = {'chart': chart, 'progress': p, 'rtl': rtl}

    if chart in ('bar', 'bar_race'):
        if chart == 'bar':
            order = sorted(range(len(c['values'])), key=lambda i: (-c['values'][i], i))
            n = len(order)
            vals = {i: c['values'][i] for i in order}
            ranks = {i: float(r) for r, i in enumerate(order)}
            vmax = max(vals.values()) or 1.0
            rows = n
            stagger = min(0.08, 0.5 / max(1, n - 1)) if n > 1 else 0.0
            grow = {i: _ease(c['easing'], _clamp((p - ranks[i] * stagger) / max(1e-9, 1 - stagger * (n - 1))))
                    for i in order}
            visible = {i: 1.0 for i in order}
        else:
            tl = c['timeline']
            K = len(tl)
            pos = p * (K - 1)
            seg = min(K - 2, int(math.floor(pos)))
            loc = _ease('ease_in_out', pos - seg)
            n = len(c['labels'])

            def rank_of(row):
                o = sorted(range(n), key=lambda i: (-row[i], i))
                return {i: float(r) for r, i in enumerate(o)}
            ra, rb = rank_of(tl[seg]), rank_of(tl[seg + 1])
            vals = {i: _lerp(tl[seg][i], tl[seg + 1][i], loc) for i in range(n)}
            ranks = {i: _lerp(ra[i], rb[i], loc) for i in range(n)}
            vmax = max(vals.values()) or 1.0
            rows = c['top_n']
            order = sorted(range(n), key=lambda i: ranks[i])
            grow = {i: 1.0 for i in order}
            visible = {i: _clamp(rows - 0.5 - ranks[i] + 0.5) for i in order}
            period = c['periods'][seg if loc < 0.5 else seg + 1]
            parts.append(_txt(x1 if not rtl else x0, y1 - fs * 1.2, period, fs * 2.4, tc, ff=ff,
                              anchor='end' if not rtl else 'start', weight=800, opacity=0.35, rtl=False))
            meta.update({'segment': seg, 'local': loc, 'period': period})
        row_h = (y1 - y0) / rows
        bh = row_h * 0.7
        lab_w = (x1 - x0) * 0.22
        val_m = (x1 - x0) * 0.1
        maxlen = (x1 - x0) - lab_w - val_m
        lfs = min(fs, bh * 0.6)
        axis = x0 + lab_w if not rtl else x1 - lab_w
        for i in order:
            if visible[i] <= 0.001:
                continue
            yy = y0 + ranks[i] * row_h + (row_h - bh) / 2
            L = grow[i] * vals[i] / vmax * maxlen
            col = pal[i % len(pal)]
            bx = axis if not rtl else axis - L
            op = _fo(visible[i])
            parts.append(f'<g opacity="{op}"><rect x="{_fmt(bx)}" y="{_fmt(yy)}" width="{_fmt(max(0, L))}" '
                         f'height="{_fmt(bh)}" rx="{_fmt(bh * 0.12)}" fill="{col}"/>')
            lab = c['labels'][i]
            if not rtl:
                parts.append(_txt(axis - fs * 0.5, yy + bh / 2, lab, lfs, tc, ff=ff, anchor='end'))
                parts.append(_txt(axis + L + fs * 0.4, yy + bh / 2, fv(vals[i] * grow[i]), lfs, tc, ff=ff,
                                  anchor='start', weight=700, rtl=False))
            else:
                parts.append(_txt(axis + fs * 0.5, yy + bh / 2, lab, lfs, tc, ff=ff, anchor='end', rtl=True))
                parts.append(_txt(axis - L - fs * 0.4, yy + bh / 2, fv(vals[i] * grow[i]), lfs, tc, ff=ff,
                                  anchor='end', weight=700, rtl=False))
            parts.append('</g>')

    elif chart == 'line':
        vals = c['values']
        n = len(vals)
        lo, hi = min(vals), max(vals)
        if hi - lo < 1e-12:
            lo, hi = lo - 1, hi + 1
        pad = (hi - lo) * 0.1
        lo, hi = lo - pad, hi + pad
        px0 = x0 + fs * 3
        X = lambda i: px0 + (x1 - px0) * i / (n - 1)
        Y = lambda v: y1 - (y1 - y0) * (v - lo) / (hi - lo)
        for g in range(5):
            gv = lo + (hi - lo) * g / 4
            gy = Y(gv)
            parts.append(f'<line x1="{_fmt(px0)}" y1="{_fmt(gy)}" x2="{_fmt(x1)}" y2="{_fmt(gy)}" '
                         f'stroke="{c["grid_color"]}" stroke-width="1" opacity="0.5"/>')
            parts.append(_txt(px0 - fs * 0.4, gy, fv(gv), fs * 0.8, tc, ff=ff, anchor='end', rtl=False,
                              opacity=0.8))
        step = max(1, int(math.ceil(n / 8)))
        for i in range(0, n, step):
            parts.append(_txt(X(i), y1 + fs * 1.1, c['labels'][i], fs * 0.85, tc, ff=ff, opacity=0.85))
        pts = [(X(i), Y(v)) for i, v in enumerate(vals)]
        cum = [0.0]
        for i in range(n - 1):
            cum.append(cum[-1] + _dist(pts[i], pts[i + 1]))
        L = cum[-1]
        drawn = e * L
        col = pal[0]
        if drawn > 0.01:
            parts.append(f'<path d="{_path_d(pts)}" fill="none" stroke="{col}" stroke-width="{_fmt(fs * 0.18)}" '
                         f'stroke-linecap="round" stroke-linejoin="round" {_dash_attrs(L, drawn)}/>')
        for i, pt in enumerate(pts):
            if cum[i] <= drawn + 1e-6:
                parts.append(f'<circle cx="{_fmt(pt[0])}" cy="{_fmt(pt[1])}" r="{_fmt(fs * 0.22)}" fill="{col}"/>')
        j = 0
        while j < n - 2 and cum[j + 1] < drawn:
            j += 1
        seg = cum[j + 1] - cum[j]
        f = 0 if seg < 1e-12 else _clamp((drawn - cum[j]) / seg)
        hx, hy = _lerp(pts[j][0], pts[j + 1][0], f), _lerp(pts[j][1], pts[j + 1][1], f)
        if 0 < e < 1:
            parts.append(f'<circle cx="{_fmt(hx)}" cy="{_fmt(hy)}" r="{_fmt(fs * 0.35)}" fill="#ffffff"/>')
        meta['drawn_length'] = drawn
        meta['total_length'] = L

    elif chart in ('donut', 'ring'):
        cx, cy = (w * 0.38 if not rtl else w * 0.62), (y0 + y1) / 2
        if chart == 'ring':
            cx = w / 2
        R = min(y1 - y0, w * 0.5) * 0.36
        sw = R * 0.32
        C = 2 * math.pi * R
        parts.append(f'<circle cx="{_fmt(cx)}" cy="{_fmt(cy)}" r="{_fmt(R)}" fill="none" '
                     f'stroke="{c["grid_color"]}" stroke-width="{_fmt(sw)}" opacity="0.35"/>')
        if chart == 'ring':
            frac = c['values'][0] * e
            if frac > 0:
                parts.append(f'<circle cx="{_fmt(cx)}" cy="{_fmt(cy)}" r="{_fmt(R)}" fill="none" stroke="{pal[0]}" '
                             f'stroke-width="{_fmt(sw)}" stroke-linecap="round" stroke-dasharray="{_fmt(frac * C)} '
                             f'{_fmt(C)}" transform="rotate(-90 {_fmt(cx)} {_fmt(cy)})"/>')
            pct = _fmt_value(frac * 100, c['decimals'], c['digits'], '%')
            parts.append(_txt(cx, cy, pct, R * 0.45, tc, ff=ff, weight=800, rtl=False))
            parts.append(_txt(cx, cy + R + sw, c['labels'][0], fs * 1.1, tc, ff=ff))
            meta['fraction'] = frac
        else:
            total = sum(c['values'])
            sweep = e * C
            start = 0.0
            for i, v in enumerate(c['values']):
                seg_len = v / total * C
                vis = _clamp(sweep - start, 0, seg_len)
                if vis > 0.01:
                    parts.append(f'<circle cx="{_fmt(cx)}" cy="{_fmt(cy)}" r="{_fmt(R)}" fill="none" '
                                 f'stroke="{pal[i % len(pal)]}" stroke-width="{_fmt(sw)}" '
                                 f'stroke-dasharray="{_fmt(vis)} {_fmt(C)}" stroke-dashoffset="{_fmt(-start)}" '
                                 f'transform="rotate(-90 {_fmt(cx)} {_fmt(cy)})"/>')
                start += seg_len
            big = max(range(len(c['values'])), key=lambda i: c['values'][i])
            parts.append(_txt(cx, cy, _fmt_value(c['values'][big] / total * 100 * e, 0, c['digits'], '%'),
                              R * 0.4, tc, ff=ff, weight=800, rtl=False))
            lx = w * 0.7 if not rtl else w * 0.3
            lh = min(fs * 2, (y1 - y0) / max(1, len(c['values'])))
            ly0 = cy - lh * (len(c['values']) - 1) / 2
            for i, (lab, v) in enumerate(zip(c['labels'], c['values'])):
                ly = ly0 + i * lh
                op = _clamp((p - 0.1 * i) * 3)
                sq = fs * 0.8
                if not rtl:
                    parts.append(f'<rect x="{_fmt(lx)}" y="{_fmt(ly - sq / 2)}" width="{_fmt(sq)}" height="{_fmt(sq)}" '
                                 f'fill="{pal[i % len(pal)]}" opacity="{_fo(op)}"/>')
                    parts.append(_txt(lx + sq * 1.6, ly, f'{lab}  {_fmt_value(v / total * 100, 0, c["digits"], "%")}',
                                      fs, tc, ff=ff, anchor='start', opacity=op))
                else:
                    parts.append(f'<rect x="{_fmt(lx - sq)}" y="{_fmt(ly - sq / 2)}" width="{_fmt(sq)}" '
                                 f'height="{_fmt(sq)}" fill="{pal[i % len(pal)]}" opacity="{_fo(op)}"/>')
                    parts.append(_txt(lx - sq * 1.6, ly, f'{lab}  {_fmt_value(v / total * 100, 0, c["digits"], "%")}',
                                      fs, tc, ff=ff, anchor='start', opacity=op, rtl=True))

    elif chart == 'stacked':
        total = sum(c['values'])
        bh = (y1 - y0) * 0.22
        by = y0 + (y1 - y0) * 0.25
        W = x1 - x0
        start = 0.0
        sweep = e * W
        for i, v in enumerate(c['values']):
            seg = v / total * W
            vis = _clamp(sweep - start, 0, seg)
            if vis > 0.01:
                sx = x0 + start if not rtl else x1 - start - vis
                parts.append(f'<rect x="{_fmt(sx)}" y="{_fmt(by)}" width="{_fmt(vis)}" height="{_fmt(bh)}" '
                             f'fill="{pal[i % len(pal)]}"/>')
                if vis > fs * 2.5 and vis >= seg - 0.01:
                    parts.append(_txt(sx + vis / 2, by + bh / 2, _fmt_value(v / total * 100, 0, c['digits'], '%'),
                                      fs * 0.9, '#000000', ff=ff, weight=700, rtl=False))
            start += seg
        cols = min(len(c['values']), 4)
        cw = W / cols
        for i, lab in enumerate(c['labels']):
            r_, k_ = divmod(i, cols)
            if rtl:
                k_ = cols - 1 - k_
            lx = x0 + k_ * cw + cw / 2
            ly = by + bh + fs * 2 + r_ * fs * 1.8
            op = _clamp((p - 0.08 * i) * 3)
            parts.append(f'<circle cx="{_fmt(lx - cw * 0.3 if not rtl else lx + cw * 0.3)}" cy="{_fmt(ly)}" '
                         f'r="{_fmt(fs * 0.35)}" fill="{pal[i % len(pal)]}" opacity="{_fo(op)}"/>')
            parts.append(_txt(lx, ly, lab, fs * 0.95, tc, ff=ff, opacity=op))

    elif chart == 'counter':
        n = len(c['values'])
        gap = (x1 - x0) * 0.03
        cw = ((x1 - x0) - gap * (n - 1)) / n
        ch = (y1 - y0) * 0.5
        cy0 = (y0 + y1) / 2 - ch / 2
        for i, (lab, v) in enumerate(zip(c['labels'], c['values'])):
            k_ = n - 1 - i if rtl else i
            cx0 = x0 + k_ * (cw + gap)
            ui = _ease(c['easing'], _clamp((p - 0.1 * i) / max(1e-9, 1 - 0.1 * (n - 1))))
            parts.append(f'<rect x="{_fmt(cx0)}" y="{_fmt(cy0)}" width="{_fmt(cw)}" height="{_fmt(ch)}" '
                         f'rx="{_fmt(ch * 0.08)}" fill="#ffffff" fill-opacity="0.06" stroke="{pal[i % len(pal)]}" '
                         f'stroke-width="{_fmt(fs * 0.08)}"/>')
            vfs = min(ch * 0.32, cw / max(4, len(fv(v))) * 1.6)
            parts.append(_txt(cx0 + cw / 2, cy0 + ch * 0.42, fv(v * ui), vfs, pal[i % len(pal)], ff=ff,
                              weight=800, rtl=False))
            parts.append(_txt(cx0 + cw / 2, cy0 + ch * 0.75, lab, fs * 1.05, tc, ff=ff, opacity=0.9))

    elif chart == 'histogram':
        vals = c['values']
        lo, hi = min(vals), max(vals)
        if hi - lo < 1e-12:
            hi = lo + 1
        nb = c['bins']
        counts = [0] * nb
        for v in vals:
            counts[min(nb - 1, int((v - lo) / (hi - lo) * nb))] += 1
        cmax = max(counts) or 1
        bw = (x1 - x0) / nb
        for b, cnt in enumerate(counts):
            ub = _ease(c['easing'], _clamp((p - b * 0.04) / max(1e-9, 1 - 0.04 * (nb - 1))))
            bhh = (y1 - y0 - fs * 2) * cnt / cmax * ub
            bx = x0 + b * bw if not rtl else x1 - (b + 1) * bw
            parts.append(f'<rect x="{_fmt(bx + bw * 0.06)}" y="{_fmt(y1 - fs * 1.5 - bhh)}" width="{_fmt(bw * 0.88)}" '
                         f'height="{_fmt(bhh)}" fill="{pal[0]}"/>')
        parts.append(_txt(x0 if not rtl else x1, y1 - fs * 0.5, fv(lo), fs * 0.85, tc, ff=ff,
                          anchor='start' if not rtl else 'end', rtl=False))
        parts.append(_txt(x1 if not rtl else x0, y1 - fs * 0.5, fv(hi), fs * 0.85, tc, ff=ff,
                          anchor='end' if not rtl else 'start', rtl=False))
        meta['counts'] = counts

    else:  # scatter
        pts = c['points']
        xs = [q[0] for q in pts]
        ys = [q[1] for q in pts]
        xl, xh = min(xs), max(xs)
        yl, yh = min(ys), max(ys)
        if xh - xl < 1e-12:
            xh = xl + 1
        if yh - yl < 1e-12:
            yh = yl + 1
        X = lambda v: x0 + (x1 - x0) * (v - xl) / (xh - xl)
        Y = lambda v: y1 - (y1 - y0) * (v - yl) / (yh - yl)
        parts.append(f'<line x1="{_fmt(x0)}" y1="{_fmt(y1)}" x2="{_fmt(x1)}" y2="{_fmt(y1)}" '
                     f'stroke="{c["grid_color"]}" stroke-width="1"/>')
        parts.append(f'<line x1="{_fmt(x0)}" y1="{_fmt(y0)}" x2="{_fmt(x0)}" y2="{_fmt(y1)}" '
                     f'stroke="{c["grid_color"]}" stroke-width="1"/>')
        n = len(pts)
        for i, (px, py) in enumerate(pts):
            pi = i / n * 0.75
            s = _ease('back_out', _clamp((p - pi) / 0.12))
            if s > 0:
                parts.append(f'<circle cx="{_fmt(X(px))}" cy="{_fmt(Y(py))}" r="{_fmt(fs * 0.28 * max(0.0, s))}" '
                             f'fill="{pal[0]}" opacity="0.85"/>')
        mx, my = sum(xs) / n, sum(ys) / n
        sxx = sum((x - mx) ** 2 for x in xs)
        syy = sum((y - my) ** 2 for y in ys)
        sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
        r_corr = sxy / math.sqrt(sxx * syy) if sxx > 0 and syy > 0 else 0.0
        if sxx > 0 and p > 0.85:
            slope = sxy / sxx
            icpt = my - slope * mx
            f = _clamp((p - 0.85) / 0.15)
            xa, xb = xl, _lerp(xl, xh, f)
            parts.append(f'<line x1="{_fmt(X(xa))}" y1="{_fmt(Y(icpt + slope * xa))}" x2="{_fmt(X(xb))}" '
                         f'y2="{_fmt(Y(icpt + slope * xb))}" stroke="{pal[1 % len(pal)]}" '
                         f'stroke-width="{_fmt(fs * 0.12)}" stroke-dasharray="{_fmt(fs * 0.5)} {_fmt(fs * 0.3)}"/>')
        meta['pearson_r'] = r_corr
    parts.append('</g>')
    return ''.join(parts), meta


# --------------------------------------------------------------------------- 7. route_map

_EARTH_R = 6371.0088


def _ll_vec(lat, lon):
    la, lo = math.radians(lat), math.radians(lon)
    return (math.cos(la) * math.cos(lo), math.cos(la) * math.sin(lo), math.sin(la))


def _vec_ll(v):
    x, y, z = v
    return math.degrees(math.atan2(z, math.hypot(x, y))), math.degrees(math.atan2(y, x))


def great_circle(a, b, samples=64):
    """Points (lat, lon) along the great circle from a=(lat, lon) to b; plus distance km."""
    va, vb = _ll_vec(*a), _ll_vec(*b)
    dot = _clamp(sum(x * y for x, y in zip(va, vb)), -1.0, 1.0)
    om = math.acos(dot)
    if om < 1e-9:
        raise ValueError('consecutive stops must be different places')
    if math.pi - om < 1e-6:
        raise ValueError('antipodal stops have no unique great circle; add an intermediate stop')
    so = math.sin(om)
    pts = []
    for k in range(samples + 1):
        f = k / samples
        s1, s2 = math.sin((1 - f) * om) / so, math.sin(f * om) / so
        pts.append(_vec_ll(tuple(s1 * x + s2 * y for x, y in zip(va, vb))))
    return pts, om * _EARTH_R


def _cfg_route_map(*, stops=None, samples_per_leg=64, duration=4.0, delay=0.0, easing='ease_in_out',
                   extent='route', padding=0.12, graticule_step=None, background='#0e1a2b',
                   graticule_color='#2c4466', route_color='#ff3b5c', marker_color='#ffffff',
                   city_color='#ffd166', label_color='#e8eef7', font_family=DEFAULT_FONT,
                   show_labels=True, show_preview=True, show_note=True,
                   note_text='مخطط تخطيطي — ليس خريطة دقيقة', **extra):
    _no_extra(extra)
    if stops is None:
        stops = [['القاهرة', 30.04, 31.24], ['إسطنبول', 41.01, 28.98], ['لندن', 51.51, -0.13]]
    if not isinstance(stops, (list, tuple)) or not 2 <= len(stops) <= 12:
        raise ValueError('stops must be a list of 2..12 [name, lat, lon] entries')
    parsed = []
    for i, s in enumerate(stops):
        if isinstance(s, dict):
            if set(s) - {'name', 'lat', 'lon'} or not {'lat', 'lon'} <= set(s):
                raise ValueError(f'stops[{i}] must have keys name, lat, lon')
            nm, la, lo = s.get('name', ''), s['lat'], s['lon']
        elif isinstance(s, (list, tuple)) and len(s) == 3:
            nm, la, lo = s
        else:
            raise ValueError(f'stops[{i}] must be [name, lat, lon] or a dict')
        parsed.append((_str(nm, f'stops[{i}].name', 40), _num(la, -89, 89, f'stops[{i}].lat'),
                       _num(lo, -180, 180, f'stops[{i}].lon')))
    gs = None if graticule_step is None else _num(graticule_step, 1, 90, 'graticule_step')
    return {
        'stops': parsed, 'samples': _int(samples_per_leg, 8, 256, 'samples_per_leg'),
        'duration': _num(duration, 0.01, 3600, 'duration'), 'delay': _num(delay, 0, MAX_T, 'delay'),
        'easing': _easing(easing), 'extent': _choice(extent, {'route', 'world'}, 'extent'),
        'padding': _num(padding, 0, 0.4, 'padding'), 'graticule_step': gs,
        'background': _color(background, 'background', True),
        'graticule_color': _color(graticule_color, 'graticule_color'),
        'route_color': _color(route_color, 'route_color'), 'marker_color': _color(marker_color, 'marker_color'),
        'city_color': _color(city_color, 'city_color'), 'label_color': _color(label_color, 'label_color'),
        'font_family': _font(font_family), 'show_labels': _bool(show_labels, 'show_labels'),
        'show_preview': _bool(show_preview, 'show_preview'), 'show_note': _bool(show_note, 'show_note'),
        'note_text': _str(note_text, 'note_text', 80),
    }


def _render_route_map(c, t, w, h, pid):
    stops = c['stops']
    pts_ll = []
    stop_idx = [0]
    leg_km = []
    for i in range(len(stops) - 1):
        seg, km = great_circle(stops[i][1:], stops[i + 1][1:], c['samples'])
        leg_km.append(km)
        pts_ll.extend(seg if i == 0 else seg[1:])
        stop_idx.append(len(pts_ll) - 1)
    # unwrap longitudes so the route is continuous across the antimeridian
    un = [pts_ll[0]]
    for la, lo in pts_ll[1:]:
        prev = un[-1][1]
        while lo - prev > 180:
            lo -= 360
        while lo - prev < -180:
            lo += 360
        un.append((la, lo))
    if c['extent'] == 'world':
        lo_min, lo_max, la_min, la_max = -180.0, 180.0, -85.0, 85.0
        lo_min, lo_max = min(lo_min, min(p[1] for p in un)), max(lo_max, max(p[1] for p in un))
    else:
        lo_min, lo_max = min(p[1] for p in un), max(p[1] for p in un)
        la_min, la_max = min(p[0] for p in un), max(p[0] for p in un)
        span = max(lo_max - lo_min, la_max - la_min, 4.0)
        mlo, mla = (lo_min + lo_max) / 2, (la_min + la_max) / 2
        lo_min, lo_max = mlo - span / 2, mlo + span / 2
        la_min, la_max = mla - span / 2, mla + span / 2
    pw, ph = w * (1 - 2 * c['padding']), h * (1 - 2 * c['padding'])
    sc = min(pw / (lo_max - lo_min), ph / (la_max - la_min))
    mlo, mla = (lo_min + lo_max) / 2, (la_min + la_max) / 2
    P = lambda la, lo: (w / 2 + (lo - mlo) * sc, h / 2 - (la - mla) * sc)
    xy = [P(la, lo) for la, lo in un]
    # cumulative geodesic distance
    cum = [0.0]
    for i in range(len(pts_ll) - 1):
        va, vb = _ll_vec(*pts_ll[i]), _ll_vec(*pts_ll[i + 1])
        cum.append(cum[-1] + math.acos(_clamp(sum(x * y for x, y in zip(va, vb)), -1, 1)) * _EARTH_R)
    total = cum[-1]
    p = _progress(t, c['delay'], c['duration'])
    e = _ease(c['easing'], p)
    s = e * total
    j = 0
    while j < len(cum) - 2 and cum[j + 1] < s:
        j += 1
    seg = cum[j + 1] - cum[j]
    f = 0.0 if seg < 1e-12 else _clamp((s - cum[j]) / seg)
    head = (_lerp(xy[j][0], xy[j + 1][0], f), _lerp(xy[j][1], xy[j + 1][1], f))
    ff = c['font_family']
    fs = min(w, h) * 0.03
    parts = [f'<g id="{pid}-map">']
    if c['background'] != 'none':
        parts.append(f'<rect x="0" y="0" width="{_fmt(w)}" height="{_fmt(h)}" fill="{c["background"]}"/>')
    # visible lon/lat window
    v_lo0, v_lo1 = mlo - (w / 2) / sc, mlo + (w / 2) / sc
    v_la0, v_la1 = mla - (h / 2) / sc, mla + (h / 2) / sc
    step = c['graticule_step']
    if step is None:
        sp = max(v_lo1 - v_lo0, v_la1 - v_la0)
        step = 5.0 if sp <= 40 else 10.0 if sp <= 100 else 15.0 if sp <= 200 else 30.0
    grat = []
    k0 = math.ceil(v_lo0 / step)
    for k in range(k0, k0 + 400):
        lo = k * step
        if lo > v_lo1:
            break
        x = P(0, lo)[0]
        grat.append(f'M{_fmt(x)} 0 L{_fmt(x)} {_fmt(h)}')
    k0 = math.ceil(max(-90.0, v_la0) / step)
    for k in range(k0, k0 + 400):
        la = k * step
        if la > min(90.0, v_la1):
            break
        y = P(la, 0)[1]
        grat.append(f'M0 {_fmt(y)} L{_fmt(w)} {_fmt(y)}')
    if grat:
        parts.append(f'<path d="{" ".join(grat)}" fill="none" stroke="{c["graticule_color"]}" '
                     f'stroke-width="1" opacity="0.7"/>')
    lw = max(1.5, fs * 0.16)
    if c['show_preview']:
        parts.append(f'<path d="{_path_d(xy)}" fill="none" stroke="{c["route_color"]}" stroke-width="{_fmt(lw * 0.6)}" '
                     f'stroke-dasharray="{_fmt(lw * 2)} {_fmt(lw * 3)}" opacity="0.3"/>')
    drawn = xy[:j + 1] + [head]
    if s > 0:
        parts.append(f'<path d="{_path_d(drawn)}" fill="none" stroke="{c["route_color"]}" '
                     f'stroke-width="{_fmt(lw)}" stroke-linecap="round" stroke-linejoin="round"/>')
    reached = []
    for i, (nm, la, lo) in enumerate(stops):
        pr = cum[stop_idx[i]] / total
        if i and e < pr - 0.06:
            continue
        if i == 0 or e >= pr - 1e-9:
            reached.append(nm)
        local = 1.0 if i == 0 else _clamp((e - pr + 0.06) / 0.06)
        sc_ = _ease('back_out', local)
        x, y = xy[stop_idx[i]]
        parts.append(f'<circle cx="{_fmt(x)}" cy="{_fmt(y)}" r="{_fmt(fs * 0.32 * max(0.0, sc_))}" '
                     f'fill="{c["city_color"]}"/>')
        if c['show_labels'] and nm:
            parts.append(_txt(x, y - fs * 1.1, nm, fs, c['label_color'], ff=ff, weight=600,
                              opacity=_clamp(local * 1.5)))
    pulse = (t * 1.2) % 1.0
    parts.append(f'<circle cx="{_fmt(head[0])}" cy="{_fmt(head[1])}" r="{_fmt(fs * (0.4 + 0.9 * pulse))}" '
                 f'fill="none" stroke="{c["marker_color"]}" stroke-width="1.5" opacity="{_fo(0.7 * (1 - pulse))}"/>')
    parts.append(f'<circle cx="{_fmt(head[0])}" cy="{_fmt(head[1])}" r="{_fmt(fs * 0.38)}" fill="{c["marker_color"]}"/>')
    if c['show_note'] and c['note_text']:
        rtl = _has_arabic(c['note_text'])
        parts.append(_txt(w - fs if rtl else fs, h - fs, c['note_text'], fs * 0.7, c['label_color'], ff=ff,
                          anchor='start' if rtl else 'start', opacity=0.6))
    parts.append('</g>')
    return ''.join(parts), {'schematic': True, 'projection': 'equirectangular',
                            'total_km': total, 'legs_km': leg_km, 'progress': p,
                            'travelled_km': s, 'reached': reached, 'graticule_step_deg': step}


# --------------------------------------------------------------------------- 8. explainer_diagram

def _seg_cross(a, b, c, d):
    def orient(p, q, r):
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
    o1, o2, o3, o4 = orient(a, b, c), orient(a, b, d), orient(c, d, a), orient(c, d, b)
    return (o1 * o2 < -1e-9) and (o3 * o4 < -1e-9)


def _cfg_explainer(*, components=None, edges=None, steps=None, direction='auto', step_duration=1.2,
                   delay=0.0, box_fill='#1c1f26', box_stroke='#5b6270', active_color='#ff3b5c',
                   text_color='#ffffff', arrow_color='#9aa3b2', font_family=DEFAULT_FONT, **extra):
    _no_extra(extra)
    if components is None:
        components = ['الفكرة', 'السيناريو', 'التصوير', 'المونتاج', 'النشر']
    comps = _strlist(components, 'components', 3, 7, 40)
    if any(not s.strip() for s in comps):
        raise ValueError('component labels must not be empty')
    n = len(comps)
    if edges is None:
        edges = [[i, i + 1] for i in range(n - 1)]
    if not isinstance(edges, (list, tuple)) or len(edges) > 12:
        raise ValueError('edges must be a list of at most 12 [from, to] pairs')
    E = []
    for k, ed in enumerate(edges):
        if not isinstance(ed, (list, tuple)) or len(ed) != 2:
            raise ValueError(f'edges[{k}] must be [from, to]')
        a, b = _int(ed[0], 0, n - 1, f'edges[{k}][0]'), _int(ed[1], 0, n - 1, f'edges[{k}][1]')
        if a == b:
            raise ValueError(f'edges[{k}] must connect two different components')
        if (a, b) in E:
            raise ValueError(f'edges[{k}] is a duplicate')
        E.append((a, b))
    # topological order (Kahn, smallest index first); fall back to given order on cycles
    indeg = [0] * n
    for a, b in E:
        indeg[b] += 1
    avail = sorted(i for i in range(n) if indeg[i] == 0)
    topo = []
    deg = indeg[:]
    while avail:
        v = avail.pop(0)
        topo.append(v)
        for a, b in E:
            if a == v:
                deg[b] -= 1
                if deg[b] == 0:
                    avail.append(b)
                    avail.sort()
    cyclic = len(topo) < n
    if cyclic:
        topo = list(range(n))
    if steps is None:
        k = min(5, n)
        base, more = divmod(n, k)
        S, pos = [], 0
        for s in range(k):
            size = base + (1 if s < more else 0)
            S.append(topo[pos:pos + size])
            pos += size
    else:
        if not isinstance(steps, (list, tuple)) or not 1 <= len(steps) <= 5:
            raise ValueError('steps must be a list of 1..5 steps (max 5 steps)')
        S, seen = [], set()
        for si, st in enumerate(steps):
            if not isinstance(st, (list, tuple)) or not st:
                raise ValueError(f'steps[{si}] must be a non-empty list of component indices')
            row = []
            for v in st:
                v = _int(v, 0, n - 1, f'steps[{si}] item')
                if v in seen:
                    raise ValueError(f'component {v} appears in more than one step')
                seen.add(v)
                row.append(v)
            S.append(row)
        if len(seen) != n:
            raise ValueError('every component must appear in exactly one step')
    if direction == 'auto':
        direction = 'rtl' if any(_has_arabic(s) for s in comps) else 'ltr'
    direction = _choice(direction, {'ltr', 'rtl', 'ttb'}, 'direction')
    return {
        'components': comps, 'edges': E, 'steps': S, 'direction': direction, 'cyclic': cyclic,
        'step_duration': _num(step_duration, 0.3, 10, 'step_duration'), 'delay': _num(delay, 0, MAX_T, 'delay'),
        'box_fill': _color(box_fill, 'box_fill'), 'box_stroke': _color(box_stroke, 'box_stroke'),
        'active_color': _color(active_color, 'active_color'), 'text_color': _color(text_color, 'text_color'),
        'arrow_color': _color(arrow_color, 'arrow_color'), 'font_family': _font(font_family),
    }


def _render_explainer(c, t, w, h, pid):
    comps, S = c['components'], c['steps']
    n = len(comps)
    order = [v for st in S for v in st]
    step_of = {v: si for si, st in enumerate(S) for v in st}
    d = c['direction']
    if d == 'ttb':
        cols, rows = 1, n
    elif n <= 5:
        cols, rows = n, 1
    else:
        cols, rows = int(math.ceil(n / 2)), 2
    ax0, ay0, aw, ah = w * 0.07, h * 0.12, w * 0.86, h * 0.76
    cw, chh = aw / cols, ah / rows
    if d == 'ttb':
        bw = min(cw * 0.5, w * 0.4)
        bh = min(chh * 0.62, h * 0.11)
    else:
        bw = cw * 0.74
        bh = min(chh * 0.5, bw * 0.55, h * 0.2)
    centers = {}
    for k, v in enumerate(order):
        r, col = divmod(k, cols)
        if d == 'rtl':
            col = cols - 1 - col
        centers[v] = (ax0 + (col + 0.5) * cw, ay0 + (r + 0.5) * chh)
    sd = c['step_duration']
    rel = t - c['delay']
    nsteps = len(S)
    active = -1 if rel < 0 else min(nsteps - 1, int(math.floor(rel / sd)))
    ff = c['font_family']

    def clip(cen, other, gap):
        dx, dy = other[0] - cen[0], other[1] - cen[1]
        L = math.hypot(dx, dy) or 1.0
        ux, uy = dx / L, dy / L
        tt = min(bw / 2 / abs(ux) if abs(ux) > 1e-9 else 1e18, bh / 2 / abs(uy) if abs(uy) > 1e-9 else 1e18)
        return cen[0] + ux * (tt + gap), cen[1] + uy * (tt + gap)

    segs = []
    arrows = []
    for a, b in c['edges']:
        p0 = clip(centers[a], centers[b], 6)
        p1 = clip(centers[b], centers[a], 6)
        segs.append((p0, p1))
        st = max(step_of[a], step_of[b])
        local = _clamp(((rel - st * sd) / sd - 0.3) / 0.5) if rel >= 0 else 0.0
        if active < st:
            local = 0.0
        if local <= 0:
            continue
        L = _dist(p0, p1)
        ux, uy = (p1[0] - p0[0]) / (L or 1), (p1[1] - p0[1]) / (L or 1)
        hs = min(w, h) * 0.014
        arrows.append(f'<path d="M{_fmt(p0[0])} {_fmt(p0[1])} L{_fmt(p1[0] - ux * hs)} {_fmt(p1[1] - uy * hs)}" '
                      f'fill="none" stroke="{c["arrow_color"]}" stroke-width="{_fmt(hs * 0.28)}" '
                      f'stroke-linecap="round" {_dash_attrs(max(0.0, L - hs), local * max(0.0, L - hs))}/>')
        if local >= 0.98:
            tip = p1
            bl = (p1[0] - ux * hs * 1.6 - uy * hs * 0.8, p1[1] - uy * hs * 1.6 + ux * hs * 0.8)
            br = (p1[0] - ux * hs * 1.6 + uy * hs * 0.8, p1[1] - uy * hs * 1.6 - ux * hs * 0.8)
            arrows.append(f'<path d="{_path_d([tip, bl, br], True)}" fill="{c["arrow_color"]}"/>')
    crossings = sum(1 for i in range(len(segs)) for j in range(i + 1, len(segs))
                    if _seg_cross(segs[i][0], segs[i][1], segs[j][0], segs[j][1]))
    boxes = []
    for v in order:
        st = step_of[v]
        if active < st:
            continue
        local = _clamp((rel - st * sd) / (sd * 0.4))
        e = _ease('back_out', local)
        cx, cy = centers[v]
        is_active = st == active
        stroke = c['active_color'] if is_active else c['box_stroke']
        swd = min(w, h) * (0.005 if is_active else 0.0025)
        label = comps[v]
        lfs = min(bh * 0.32, bw * 1.7 / max(4, len(label)))
        boxes.append(f'<g opacity="{_fo(_clamp(local * 2))}" transform="translate({_fmt(cx)} {_fmt(cy)}) '
                     f'scale({max(0.0, 0.85 + 0.15 * e):.3f})">'
                     f'<rect x="{_fmt(-bw / 2)}" y="{_fmt(-bh / 2)}" width="{_fmt(bw)}" height="{_fmt(bh)}" '
                     f'rx="{_fmt(bh * 0.18)}" fill="{c["box_fill"]}" stroke="{stroke}" stroke-width="{_fmt(swd)}"/>'
                     + _txt(0, 0, label, lfs, c['text_color'], ff=ff, weight=700 if is_active else 500) + '</g>')
        if is_active:
            bx = -bw / 2 if d != 'rtl' else bw / 2
            boxes.append(f'<circle cx="{_fmt(cx + bx)}" cy="{_fmt(cy - bh / 2)}" r="{_fmt(bh * 0.17)}" '
                         f'fill="{c["active_color"]}"/>'
                         + _txt(cx + bx, cy - bh / 2, str(st + 1), bh * 0.2, '#ffffff', ff=ff, weight=800,
                                rtl=False))
    svg = f'<g id="{pid}-diagram">{"".join(arrows)}{"".join(boxes)}</g>'
    return svg, {'active_step': active, 'steps': S, 'direction': d, 'layout_order': order,
                 'crossings': crossings, 'cyclic_edges': c['cyclic'],
                 'total_duration': nsteps * sd}


# --------------------------------------------------------------------------- 9. retro_pixel

_RETRO_PALETTES = {
    'red_rose': {'sky0': '#1a0b1e', 'sky1': '#3b0f2e', 'sky2': '#7a1d3a', 'sun0': '#ffb000', 'sun1': '#ff5a36',
                 'far': '#2b1840', 'near': '#160c24', 'ground': '#0d0614', 'line': '#ff2d55',
                 'body': '#ff2d55', 'dark': '#1b1b1f', 'skin': '#f2c6a0', 'cloud': '#f4e9f0'},
    'gameboy': {'sky0': '#9bbc0f', 'sky1': '#9bbc0f', 'sky2': '#8bac0f', 'sun0': '#e0f8d0', 'sun1': '#c4e4a0',
                'far': '#306230', 'near': '#0f380f', 'ground': '#0f380f', 'line': '#306230',
                'body': '#306230', 'dark': '#0f380f', 'skin': '#8bac0f', 'cloud': '#e0f8d0'},
    'pico': {'sky0': '#1d2b53', 'sky1': '#7e2553', 'sky2': '#ff77a8', 'sun0': '#ffec27', 'sun1': '#ffa300',
             'far': '#5f574f', 'near': '#000000', 'ground': '#1d2b53', 'line': '#29adff',
             'body': '#ff004d', 'dark': '#000000', 'skin': '#ffccaa', 'cloud': '#fff1e8'},
}


def _cfg_retro(*, grid=(64, 36), scale=None, crt=False, scanline_amount=0.25, sprite=True,
               sprite_frames=8, sprite_fps=10.0, walk_speed=12.0, seed=21, palette='red_rose',
               art=None, art_palette=None, **extra):
    _no_extra(extra)
    if not isinstance(grid, (list, tuple)) or len(grid) != 2:
        raise ValueError('grid must be [columns, rows]')
    gw, gh = _int(grid[0], 16, 160, 'grid[0]'), _int(grid[1], 16, 120, 'grid[1]')
    art_rows = amap = None
    if art is not None:
        if not isinstance(art, (list, tuple)) or not 1 <= len(art) <= 120:
            raise ValueError('art must be a list of 1..120 equal-length strings')
        art_rows = [_str(r, f'art[{i}]', 160, allow_empty=False) for i, r in enumerate(art)]
        if len({len(r) for r in art_rows}) != 1:
            raise ValueError('art rows must all have the same length')
        if not isinstance(art_palette, dict) or not 1 <= len(art_palette) <= 32:
            raise ValueError('art_palette must map 1..32 single characters to hex colours')
        amap = {}
        for k, v in art_palette.items():
            if not isinstance(k, str) or len(k) != 1 or k in '. ':
                raise ValueError("art_palette keys must be single characters other than '.' and space")
            amap[k] = _color(v, f'art_palette[{k!r}]')
        for i, r in enumerate(art_rows):
            for ch in r:
                if ch not in amap and ch not in '. ':
                    raise ValueError(f'art[{i}] uses {ch!r} which is not in art_palette')
        gw, gh = len(art_rows[0]), len(art_rows)
    elif art_palette is not None:
        raise ValueError('art_palette needs art')
    return {
        'gw': gw, 'gh': gh, 'scale': None if scale is None else _int(scale, 1, 64, 'scale'),
        'crt': _bool(crt, 'crt'), 'scan': _num(scanline_amount, 0, 0.5, 'scanline_amount'),
        'sprite': _bool(sprite, 'sprite'), 'frames': _int(sprite_frames, 8, 12, 'sprite_frames'),
        'fps': _num(sprite_fps, 4, 24, 'sprite_fps'), 'walk': _num(walk_speed, 0, 200, 'walk_speed'),
        'seed': _seed(seed), 'palette': _choice(palette, set(_RETRO_PALETTES), 'palette'),
        'art': art_rows, 'art_map': amap,
    }


def _sprite_pixels(frame, frames):
    """8x10 walking character for frame index -> list of (x, y, token)."""
    ph = 2 * math.pi * frame / frames
    s = math.sin(ph)
    bob = 1 if abs(s) > 0.6 else 0
    top = ["..DDDD..",
           ".DSSSSD.",
           ".SDSSDS.",
           "..SSSS..",
           ".BBBBBB.",
           "..BBBB..",
           "..BBBB.."]
    px = []
    for y, row in enumerate(top):
        for x, ch in enumerate(row):
            if ch != '.':
                px.append((x, y + bob, {'D': 'dark', 'S': 'skin', 'B': 'body'}[ch]))
    arm = 1 if s > 0 else 0
    px.append((0, 4 + bob + arm, 'skin'))
    px.append((7, 5 + bob - arm, 'skin'))
    for row, amp in ((7, 0.5), (8, 1.0), (9, 1.5)):
        o = int(round(amp * s))
        px.append((_clamp(2 + o, 0, 7), row, 'dark'))
        px.append((_clamp(5 - o, 0, 7), row, 'dark'))
    o = int(round(1.5 * s))
    px.append((_clamp(3 + o, 0, 7), 9, 'dark'))
    px.append((_clamp(6 - o, 0, 7), 9, 'dark'))
    return [(int(x), int(y), tk) for x, y, tk in px], frame


def _render_retro(c, t, w, h, pid):
    gw, gh = c['gw'], c['gh']
    s = c['scale'] if c['scale'] else max(1, min(int(w // gw), int(h // gh)))
    if gw * s > w + 1e-9 or gh * s > h + 1e-9:
        raise ValueError(f'grid {gw}x{gh} at scale {s} does not fit {w:g}x{h:g}')
    ox, oy = math.floor((w - gw * s) / 2), math.floor((h - gh * s) / 2)
    pal = _RETRO_PALETTES[c['palette']]
    grid = [[None] * gw for _ in range(gh)]
    horizon = int(gh * 0.62)
    if c['art'] is not None:
        for y, row in enumerate(c['art']):
            for x, ch in enumerate(row):
                if ch not in '. ':
                    grid[y][x] = c['art_map'][ch]
    else:
        for y in range(gh):
            for x in range(gw):
                if y < horizon:
                    f = y / max(1, horizon)
                    if f < 0.4:
                        col = 'sky0' if not (f > 0.36 and (x + y) % 2) else 'sky1'
                    elif f < 0.75:
                        col = 'sky1' if not (f > 0.71 and (x + y) % 2) else 'sky2'
                    else:
                        col = 'sky2'
                    grid[y][x] = pal[col]
        scx, scy = int(gw * 0.7), int(horizon * 0.62)
        sr = max(3.0, gh * 0.14)
        for y in range(max(0, int(scy - sr)), min(horizon, int(scy + sr) + 1)):
            for x in range(max(0, int(scx - sr)), min(gw, int(scx + sr) + 1)):
                if (x - scx) ** 2 + (y - scy) ** 2 <= sr * sr:
                    if y > scy and (y % 3 == 0):
                        continue
                    grid[y][x] = pal['sun0'] if y <= scy else pal['sun1']
        cshift = math.floor(t * 3)
        for k in range(3):
            cx0 = int(_h01(c['seed'], 40, k) * gw)
            cy0 = 2 + int(_h01(c['seed'], 41, k) * horizon * 0.35)
            x = int((cx0 + cshift * (1 + k % 2)) % (gw + 12)) - 6
            for dy, row in enumerate(('.XXX..', 'XXXXXX')):
                for dx, ch in enumerate(row):
                    if ch == 'X' and 0 <= x + dx < gw and 0 <= cy0 + dy < horizon:
                        grid[cy0 + dy][x + dx] = pal['cloud']
        for x in range(gw):
            hf = 4 + 6 * (0.5 + 0.5 * _vnoise(c['seed'], 1, x / 7.0))
            hn = 2 + 4 * (0.5 + 0.5 * _vnoise(c['seed'], 2, x / 4.0))
            for y in range(max(0, int(horizon - hf)), horizon):
                grid[y][x] = pal['far']
            for y in range(max(0, int(horizon - hn)), horizon):
                grid[y][x] = pal['near']
        for y in range(horizon, gh):
            for x in range(gw):
                grid[y][x] = pal['ground']
        phase = (t * 2) % 1.0
        for k in range(40):
            yy = horizon + 1 + int((k + phase) ** 2 * 0.9)
            if yy >= gh:
                break
            for x in range(gw):
                grid[yy][x] = pal['line']
        vx = gw / 2
        for jj in range(-12, 13):
            for y in range(horizon, gh):
                x = int(round(vx + jj * (y - horizon) * 1.4))
                if 0 <= x < gw:
                    grid[y][x] = pal['line']
    frame = None
    if c['sprite']:
        frame = math.floor(t * c['fps']) % c['frames']
        pxs, _ = _sprite_pixels(frame, c['frames'])
        sx = int(math.floor(c['walk'] * t) % (gw + 8)) - 8
        ground = horizon + int((gh - horizon) * 0.5) if c['art'] is None else gh - 1
        sy = min(gh - 10, ground - 9)
        for x, y, tk in pxs:
            gx, gy = sx + x, sy + y
            if 0 <= gx < gw and 0 <= gy < gh:
                grid[gy][gx] = pal[tk]
    rects = []
    for y in range(gh):
        x = 0
        while x < gw:
            col = grid[y][x]
            x2 = x + 1
            while x2 < gw and grid[y][x2] == col:
                x2 += 1
            if col is not None:
                rects.append(f'<rect x="{ox + x * s}" y="{oy + y * s}" width="{(x2 - x) * s}" height="{s}" fill="{col}"/>')
            x = x2
    parts = [f'<g id="{pid}-retro" shape-rendering="crispEdges">', ''.join(rects)]
    if c['crt'] and c['scan'] > 0:
        lh = max(1, s // 3)
        parts.append(f'<defs><pattern id="{pid}-crt" patternUnits="userSpaceOnUse" x="{ox}" y="{oy}" width="{gw * s}" '
                     f'height="{s}"><rect x="0" y="{s - lh}" width="{gw * s}" height="{lh}" fill="#000000"/></pattern></defs>'
                     f'<rect x="{ox}" y="{oy}" width="{gw * s}" height="{gh * s}" fill="url(#{pid}-crt)" '
                     f'opacity="{_fo(c["scan"])}"/>')
    parts.append('</g>')
    return ''.join(parts), {'grid': [gw, gh], 'scale': s, 'offset': [ox, oy], 'rects': len(rects),
                            'sprite_frame': frame, 'sprite_frames': c['frames'], 'crt': c['crt']}


# --------------------------------------------------------------------------- 10. ui_mock

def _cfg_ui_mock(*, device='phone', tilt_deg=10.0, min_tilt=3.0, tilt_period=6.0, tilt_direction='left',
                 screen_color='#f4f5f7', frame_color='#16171b', accent='#ff3b5c', title='Red Rose',
                 button_label='Start', cursor_path=None, move_time=0.8, dwell=0.4, ripple_duration=0.6,
                 font_family=DEFAULT_FONT, scale=1.0, **extra):
    _no_extra(extra)
    min_tilt = _num(min_tilt, 1, 15, 'min_tilt')
    tilt_deg = _num(tilt_deg, 1, 30, 'tilt_deg')
    if tilt_deg < min_tilt:
        raise ValueError('tilt_deg must be >= min_tilt (the tilt never rests at 0 degrees)')
    if cursor_path is None:
        cursor_path = [[0.5, 0.95, False], [0.3, 0.38, True], [0.7, 0.58, True], [0.5, 0.86, True]]
    if not isinstance(cursor_path, (list, tuple)) or not 1 <= len(cursor_path) <= 20:
        raise ValueError('cursor_path must be a list of 1..20 [u, v, click] waypoints')
    cp = []
    for i, wp in enumerate(cursor_path):
        if not isinstance(wp, (list, tuple)) or len(wp) not in (2, 3):
            raise ValueError(f'cursor_path[{i}] must be [u, v] or [u, v, click]')
        u, v = _num(wp[0], 0, 1, f'cursor_path[{i}][0]'), _num(wp[1], 0, 1, f'cursor_path[{i}][1]')
        cl = _bool(wp[2], f'cursor_path[{i}][2]') if len(wp) == 3 else False
        cp.append((u, v, cl))
    return {
        'device': _choice(device, {'phone', 'laptop'}, 'device'), 'tilt_deg': tilt_deg, 'min_tilt': min_tilt,
        'period': _num(tilt_period, 1, 60, 'tilt_period'),
        'dir': 1.0 if _choice(tilt_direction, {'left', 'right'}, 'tilt_direction') == 'left' else -1.0,
        'screen': _color(screen_color, 'screen_color'), 'frame': _color(frame_color, 'frame_color'),
        'accent': _color(accent, 'accent'), 'title': _str(title, 'title', 30),
        'button': _str(button_label, 'button_label', 20), 'path': cp,
        'move': _num(move_time, 0.1, 10, 'move_time'), 'dwell': _num(dwell, 0, 10, 'dwell'),
        'ripple': _num(ripple_duration, 0.1, 3, 'ripple_duration'), 'font_family': _font(font_family),
        'scale': _num(scale, 0.3, 1.2, 'scale'),
    }


def _rrect(x, y, w, h, r, seg=5):
    r = min(r, w / 2, h / 2)
    pts = []
    for cx, cy, a0 in ((x + w - r, y + r, -90), (x + w - r, y + h - r, 0), (x + r, y + h - r, 90), (x + r, y + r, 180)):
        for k in range(seg + 1):
            a = math.radians(a0 + 90 * k / seg)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def _cursor_state(c, t):
    """-> (u, v, list of click times)."""
    path = c['path']
    clicks = []
    tt = 0.0
    u, v = path[0][0], path[0][1]
    if path[0][2]:
        clicks.append(0.0)
    pos = (u, v)
    for k in range(1, len(path)):
        a, b = path[k - 1], path[k]
        if t >= tt and t < tt + c['move']:
            e = _ease('ease_in_out', (t - tt) / c['move'])
            pos = (_lerp(a[0], b[0], e), _lerp(a[1], b[1], e))
        tt += c['move']
        if b[2]:
            clicks.append(tt)
        if t >= tt:
            pos = (b[0], b[1])
        tt += c['dwell']
    return pos, clicks


def _render_ui_mock(c, t, w, h, pid):
    phase = 0.5 + 0.5 * math.sin(2 * math.pi * t / c['period'])
    tilt = c['dir'] * (c['min_tilt'] + (c['tilt_deg'] - c['min_tilt']) * phase)
    phone = c['device'] == 'phone'
    if phone:
        dh = 0.78 * h * c['scale']
        dw = dh * 0.49
        bz = dw * 0.05
        sx0, sy0, sw_, sh_ = -dw / 2 + bz, -dh / 2 + bz * 1.8, dw - 2 * bz, dh - 3.6 * bz
        pitch = math.radians(6)
    else:
        dw = 0.62 * w * c['scale']
        dh = dw * 0.64
        bz = dw * 0.03
        sx0, sy0, sw_, sh_ = -dw / 2 + bz, -dh / 2 - dh * 0.12 + bz, dw - 2 * bz, dh - 2 * bz
        pitch = math.radians(16)
    yaw = math.radians(tilt)
    D = 2.8 * max(dw, dh)
    cx, cy = w / 2, h / 2
    cyw, syw, cp_, sp_ = math.cos(yaw), math.sin(yaw), math.cos(pitch), math.sin(pitch)

    def P(x, y, z=0.0):
        X = x * cyw + z * syw
        Z = -x * syw + z * cyw
        Y = y * cp_ - Z * sp_
        Z2 = y * sp_ + Z * cp_
        f = D / (D + Z2)
        return (cx + X * f, cy + Y * f)

    def poly(pts, fill, extra=''):
        return f'<path d="{_path_d([P(*q) for q in pts], True)}" fill="{fill}"{extra}/>'

    def text_at(x, y, s, size, fill, weight=600):
        p0, px, py = P(x, y), P(x + 1, y), P(x, y + 1)
        m = (f'matrix({px[0] - p0[0]:.4f} {px[1] - p0[1]:.4f} {py[0] - p0[0]:.4f} {py[1] - p0[1]:.4f} '
             f'{p0[0]:.2f} {p0[1]:.2f})')
        return _txt(0, 0, s, size, fill, ff=c['font_family'], weight=weight, extra=f'transform="{m}"')

    parts = [f'<g id="{pid}-ui">']
    parts.append(f'<ellipse cx="{_fmt(cx)}" cy="{_fmt(cy + dh * 0.56)}" rx="{_fmt(dw * 0.55)}" '
                 f'ry="{_fmt(dh * 0.04)}" fill="#000000" opacity="0.25"/>')
    if phone:
        parts.append(poly(_rrect(-dw / 2, -dh / 2, dw, dh, dw * 0.13), c['frame']))
        parts.append(poly(_rrect(sx0, sy0, sw_, sh_, dw * 0.09), c['screen']))
    else:
        parts.append(poly(_rrect(-dw / 2, -dh / 2 - dh * 0.12, dw, dh, dw * 0.02), c['frame']))
        parts.append(poly([(sx0, sy0), (sx0 + sw_, sy0), (sx0 + sw_, sy0 + sh_), (sx0, sy0 + sh_)], c['screen']))
    # screen content in screen-local coordinates
    S = lambda u, v: (sx0 + u * sw_, sy0 + v * sh_)
    hdr = [S(0, 0.04), S(1, 0.04), S(1, 0.16), S(0, 0.16)] if phone else [S(0, 0), S(1, 0), S(1, 0.1), S(0, 0.1)]
    parts.append(poly(hdr, c['accent']))
    tx, ty = S(0.5, 0.10 if phone else 0.05)
    parts.append(text_at(tx, ty, c['title'], sh_ * (0.04 if phone else 0.05), '#ffffff', 700))
    cards = ((0.08, 0.24, 0.84, 0.18), (0.08, 0.46, 0.84, 0.18), (0.08, 0.68, 0.84, 0.08)) if phone else \
        ((0.04, 0.16, 0.44, 0.34), (0.52, 0.16, 0.44, 0.34), (0.04, 0.56, 0.92, 0.2))
    for i, (u, v, cw, ch) in enumerate(cards):
        x0, y0 = S(u, v)
        parts.append(poly(_rrect(x0, y0, cw * sw_, ch * sh_, sw_ * 0.03, 3), '#ffffff',
                          ' stroke="#d9dbe0" stroke-width="1"'))
        for li in range(2 if ch > 0.1 else 1):
            lx, ly = S(u + 0.05, v + ch * (0.3 + 0.3 * li))
            lw = cw * sw_ * (0.7 - 0.25 * li)
            parts.append(poly([(lx, ly), (lx + lw, ly), (lx + lw, ly + sh_ * 0.012), (lx, ly + sh_ * 0.012)],
                              '#c9ccd3'))
    (cu, cv), clicks = _cursor_state(c, t)
    pressed = any(0 <= t - tc < 0.15 for tc in clicks)
    bu, bv, bw_, bh_ = (0.2, 0.82, 0.6, 0.08) if phone else (0.38, 0.82, 0.24, 0.1)
    bx0, by0 = S(bu, bv)
    btn_col = _mix_hex(c['accent'], '#000000', 0.25) if pressed else c['accent']
    parts.append(poly(_rrect(bx0, by0, bw_ * sw_, bh_ * sh_, bh_ * sh_ / 2, 4), btn_col))
    btx, bty = S(bu + bw_ / 2, bv + bh_ / 2)
    parts.append(text_at(btx, bty, c['button'], sh_ * 0.035, '#ffffff', 700))
    if not phone:
        yb = sy0 + sh_ + bz + dh * 0.0
        depth = dh * 0.62
        bwid = dw * 1.06
        parts.append(poly([(-bwid / 2, yb, 0), (bwid / 2, yb, 0), (bwid / 2, yb, -depth), (-bwid / 2, yb, -depth)],
                          _mix_hex(c['frame'], '#ffffff', 0.18)))
        parts.append(poly([(-bwid * 0.42, yb, -depth * 0.08), (bwid * 0.42, yb, -depth * 0.08),
                           (bwid * 0.42, yb, -depth * 0.55), (-bwid * 0.42, yb, -depth * 0.55)],
                          _mix_hex(c['frame'], '#ffffff', 0.08)))
        parts.append(poly([(-bwid * 0.12, yb, -depth * 0.62), (bwid * 0.12, yb, -depth * 0.62),
                           (bwid * 0.12, yb, -depth * 0.9), (-bwid * 0.12, yb, -depth * 0.9)],
                          _mix_hex(c['frame'], '#ffffff', 0.12)))
    ripples = 0
    for tc in clicks:
        age = t - tc
        if 0 <= age < c['ripple']:
            ripples += 1
            e = _ease('ease_out', age / c['ripple'])
            r = (0.02 + 0.12 * e) * sw_
            ccx, ccy = S(*_click_pos(c, tc))
            circ = [(ccx + r * math.cos(2 * math.pi * k / 28), ccy + r * math.sin(2 * math.pi * k / 28))
                    for k in range(28)]
            parts.append(poly(circ, 'none', f' stroke="{c["accent"]}" stroke-width="{_fmt(sw_ * 0.008)}" '
                                            f'opacity="{_fo(0.8 * (1 - age / c["ripple"]))}"'))
    px_, py_ = S(cu, cv)
    if phone:
        r = sw_ * (0.045 if pressed else 0.055)
        circ = [(px_ + r * math.cos(2 * math.pi * k / 24), py_ + r * math.sin(2 * math.pi * k / 24)) for k in range(24)]
        parts.append(poly(circ, '#000000', f' opacity="{_fo(0.45 if pressed else 0.28)}"'))
    else:
        a = sh_ * 0.05
        arrow = [(px_, py_), (px_, py_ + a), (px_ + a * 0.28, py_ + a * 0.75), (px_ + a * 0.5, py_ + a * 1.15),
                 (px_ + a * 0.62, py_ + a * 1.08), (px_ + a * 0.42, py_ + a * 0.7), (px_ + a * 0.75, py_ + a * 0.7)]
        parts.append(poly(arrow, '#111111', ' stroke="#ffffff" stroke-width="1.2" stroke-linejoin="round"'))
    parts.append('</g>')
    return ''.join(parts), {'tilt_deg': tilt, 'never_zero': abs(tilt) >= c['min_tilt'] - 1e-9,
                            'cursor_uv': [cu, cv], 'clicks': clicks, 'active_ripples': ripples,
                            'pressed': pressed, 'device': c['device']}


def _click_pos(c, tc):
    (u, v), _ = _cursor_state(c, tc + 1e-6)
    return u, v


# --------------------------------------------------------------------------- 11. brand_reveal

BRAND_TOKENS = ('primary', 'secondary', 'accent', 'background', 'text')
BRAND_PALETTES = {
    'red_rose': {'primary': '#c8102e', 'secondary': '#3a0d17', 'accent': '#f2c14e', 'background': '#0e0e10',
                 'text': '#ffffff'},
    'mono': {'primary': '#f5f5f5', 'secondary': '#6b6b6b', 'accent': '#bdbdbd', 'background': '#111111',
             'text': '#ffffff'},
    'midnight': {'primary': '#4cc9f0', 'secondary': '#3a0ca3', 'accent': '#f72585', 'background': '#0b0b1f',
                 'text': '#e8eef7'},
    'sand': {'primary': '#b5651d', 'secondary': '#e9c46a', 'accent': '#2a9d8f', 'background': '#f4ede2',
             'text': '#264653'},
}


def _cfg_brand(*, pattern='squares', palette='red_rose', wordmark='RED ROSE', tagline='',
               duration=2.4, delay=0.0, font_family=DEFAULT_FONT, mark_size=None,
               fill_background=False, **extra):
    _no_extra(extra)
    if isinstance(palette, str):
        pal = dict(BRAND_PALETTES[_choice(palette, set(BRAND_PALETTES), 'palette')])
    elif isinstance(palette, dict):
        unknown = set(palette) - set(BRAND_TOKENS)
        if unknown:
            raise ValueError(f'unknown palette token(s): {sorted(map(str, unknown))}; tokens are {list(BRAND_TOKENS)}')
        pal = dict(BRAND_PALETTES['red_rose'])
        for k, v in palette.items():
            pal[k] = _color(v, f'palette.{k}')
    else:
        raise ValueError('palette must be a preset name or a dict of tokens')
    return {
        'pattern': _choice(pattern, {'squares', 'circle_wipe', 'line_build'}, 'pattern'), 'pal': pal,
        'wordmark': _str(wordmark, 'wordmark', 40), 'tagline': _str(tagline, 'tagline', 80),
        'duration': _num(duration, 0.2, 60, 'duration'), 'delay': _num(delay, 0, MAX_T, 'delay'),
        'font_family': _font(font_family),
        'mark_size': None if mark_size is None else _num(mark_size, 8, MAX_CANVAS, 'mark_size'),
        'fill_background': _bool(fill_background, 'fill_background'),
    }


def _render_brand(c, t, w, h, pid):
    pal = c['pal']
    u = _progress(t, c['delay'], c['duration'])
    m = c['mark_size'] or 0.22 * min(w, h)
    mcx, mcy = w / 2, h / 2 - m * 0.35
    wy = mcy + m * 0.5 + m * 0.42
    fs = m * 0.32
    ff = c['font_family']
    parts = [f'<g id="{pid}-brand">']
    if c['fill_background']:
        parts.append(f'<rect x="0" y="0" width="{_fmt(w)}" height="{_fmt(h)}" fill="{pal["background"]}"/>')

    def wordmark(uw, letter_spacing=None):
        out = []
        if c['wordmark'] and uw > 0:
            e = _ease('ease_out', uw)
            ls = '' if letter_spacing is None or _has_arabic(c['wordmark']) else \
                f'letter-spacing="{_fmt(letter_spacing * fs)}"'
            out.append(_txt(mcx, wy + (1 - e) * fs * 0.6, c['wordmark'], fs, pal['text'], ff=ff, weight=800,
                            opacity=e, extra=ls))
        if c['tagline']:
            ut = _clamp((u - 0.78) / 0.22)
            if ut > 0:
                out.append(_txt(mcx, wy + fs * 1.1, c['tagline'], fs * 0.42, pal['accent'], ff=ff,
                                opacity=_ease('ease_out', ut)))
        return ''.join(out)

    meta = {'pattern': c['pattern'], 'progress': u, 'palette': pal}
    if c['pattern'] == 'squares':
        q = m * 0.46
        g = m * 0.08
        off = (q + g) / 2
        cols = (pal['primary'], pal['accent'], pal['secondary'], pal['primary'])
        ua = _clamp(u / 0.6)
        lock = 1.0
        if 0.6 <= u < 0.72:
            lock = 1 + 0.06 * math.sin(math.pi * (u - 0.6) / 0.12)
        for i, (dx, dy) in enumerate(((-1, -1), (1, -1), (-1, 1), (1, 1))):
            em = _ease('ease_out', ua)
            travel = (1 - em) * m * 1.4
            x = mcx + dx * off * lock + dx * travel
            y = mcy + dy * off * lock + dy * travel
            rot = (180 + 45 * i) * (1 - _ease('back_out', ua)) * (1 if i % 2 == 0 else -1)
            sc = 0.3 + 0.7 * em
            parts.append(f'<rect x="{_fmt(-q / 2)}" y="{_fmt(-q / 2)}" width="{_fmt(q)}" height="{_fmt(q)}" '
                         f'rx="{_fmt(q * 0.08)}" fill="{cols[i]}" opacity="{_fo(min(1.0, ua * 3))}" '
                         f'transform="translate({_fmt(x)} {_fmt(y)}) rotate({_fmt(rot)}) scale({_fo(sc)})"/>')
        meta['locked'] = u >= 0.6
        parts.append(wordmark(_clamp((u - 0.55) / 0.3)))
    elif c['pattern'] == 'circle_wipe':
        tw = fs * 0.6 * max(1, len(c['wordmark']))
        ext_x = max(m / 2, tw / 2)
        ext_y = max(wy + fs - mcy, m / 2)
        rmax = math.hypot(ext_x, ext_y) * 1.05
        uc = _clamp(u / 0.7)
        R = _ease('ease_in_out', uc) * rmax
        parts.append(f'<defs><clipPath id="{pid}-wipe"><circle cx="{_fmt(mcx)}" cy="{_fmt(mcy)}" '
                     f'r="{_fmt(R)}"/></clipPath></defs>')
        inner = [f'<circle cx="{_fmt(mcx)}" cy="{_fmt(mcy)}" r="{_fmt(m / 2)}" fill="{pal["primary"]}"/>']
        for k in range(4):
            inner.append(f'<ellipse cx="{_fmt(mcx)}" cy="{_fmt(mcy)}" rx="{_fmt(m * 0.3)}" ry="{_fmt(m * 0.1)}" '
                         f'fill="{pal["accent"]}" opacity="0.85" transform="rotate({45 * k} {_fmt(mcx)} {_fmt(mcy)})"/>')
        inner.append(f'<circle cx="{_fmt(mcx)}" cy="{_fmt(mcy)}" r="{_fmt(m * 0.08)}" fill="{pal["secondary"]}"/>')
        inner.append(wordmark(1.0 if uc >= 1 else _clamp((u - 0.3) / 0.4)))
        parts.append(f'<g clip-path="url(#{pid}-wipe)">{"".join(inner)}</g>')
        if 0 < uc < 1:
            parts.append(f'<circle cx="{_fmt(mcx)}" cy="{_fmt(mcy)}" r="{_fmt(R)}" fill="none" stroke="{pal["accent"]}" '
                         f'stroke-width="{_fmt(min(w, h) * 0.012)}" opacity="{_fo(1 - uc)}"/>')
        meta['wipe_radius'] = R
    else:  # line_build
        s = m
        sq = [(mcx - s / 2, mcy - s / 2), (mcx + s / 2, mcy - s / 2), (mcx + s / 2, mcy + s / 2), (mcx - s / 2, mcy + s / 2)]
        di = [(mcx, mcy - s / 2), (mcx + s / 2, mcy), (mcx, mcy + s / 2), (mcx - s / 2, mcy)]
        r = s / (2 * math.sqrt(2))
        lw = max(1.5, s * 0.03)
        uf = _clamp((u - 0.5) / 0.2)
        if uf > 0:
            parts.append(f'<path d="{_path_d(sq, True)}" fill="{pal["primary"]}" opacity="{_fo(uf)}"/>')
            parts.append(f'<path d="{_path_d(di, True)}" fill="{pal["secondary"]}" opacity="{_fo(uf)}"/>')
            parts.append(f'<circle cx="{_fmt(mcx)}" cy="{_fmt(mcy)}" r="{_fmt(r)}" fill="{pal["accent"]}" '
                         f'opacity="{_fo(uf)}"/>')
        for (a0, a1), shape in (((0.0, 0.25), 'sq'), ((0.15, 0.4), 'di'), ((0.3, 0.55), 'ci')):
            ul = _ease('ease_in_out', _clamp((u - a0) / (a1 - a0)))
            if ul <= 0:
                continue
            if shape == 'ci':
                L = 2 * math.pi * r
                parts.append(f'<circle cx="{_fmt(mcx)}" cy="{_fmt(mcy)}" r="{_fmt(r)}" fill="none" '
                             f'stroke="{pal["text"]}" stroke-width="{_fmt(lw)}" {_dash_attrs(L, ul * L)} '
                             f'transform="rotate(-90 {_fmt(mcx)} {_fmt(mcy)})"/>')
            else:
                pts = sq if shape == 'sq' else di
                L = _poly_len(pts, True)
                parts.append(f'<path d="{_path_d(pts, True)}" fill="none" stroke="{pal["text"]}" '
                             f'stroke-width="{_fmt(lw)}" stroke-linejoin="round" {_dash_attrs(L, ul * L)}/>')
        uw = _clamp((u - 0.55) / 0.35)
        parts.append(wordmark(uw, letter_spacing=_lerp(0.4, 0.08, _ease('ease_out', uw))))
    parts.append('</g>')
    return ''.join(parts), meta


# --------------------------------------------------------------------------- registry & dispatch

_FEATURES = {
    'shape_morph': (_cfg_shape_morph, _render_shape_morph, 1.0,
                    ['both shapes resampled to N points by arc length (first subpath only for SVG paths)',
                     'closed shapes: orientation matched by signed area, start point chosen by minimum summed squared distance',
                     'presets are fitted to center/size; custom shapes are fitted unless fit is false'],
                    ['points 8..512', 'path commands M L H V C S Q T Z only (no arcs)',
                     f'path <= {MAX_PATH_CHARS} characters and {MAX_SEGMENTS} segments']),
    'draw_on': (_cfg_draw_on, _render_draw_on, 1.0,
                ['length measured on a flattened polyline (cubics split into 8..96 segments)',
                 'subpaths draw one after another in document order',
                 'marker style: seeded smooth jitter along the normal; same seed -> same strokes'],
                ['jitter <= 20 px, passes 1..3', 'dasharray padded by 1 px to avoid end dots']),
    'neon_glow': (_cfg_neon_glow, _render_neon_glow, 1.0,
                  ['flicker is a seeded schedule of time slots (flicker_hz), not random per render',
                   'glow is drawn only when glow is true',
                   'text metrics are not measured; the font is resolved by the renderer'],
                  ['glow_strength <= 1 and each halo layer alpha <= 0.85, so the glow is limited and does not clip highlights',
                   'broken_letter only for Latin text', 'flicker_rate <= 0.5']),
    'textures': (_cfg_textures, _render_textures, 0.0,
                 ['overlays are OFF by default and drawn only when named in overlays',
                  'grain changes its feTurbulence seed in steps of 1/grain_fps seconds',
                  'halftone is a uniform dot screen, not modulated by underlying image tones'],
                 ['grain_amount <= 0.3, paper_amount <= 0.4, vignette_amount <= 0.35 (subtle)',
                  'filter appearance depends on the SVG renderer']),
    'particles_svg': (_cfg_particles, _render_particles, 1.0,
                      ['positions are closed-form functions of t with wrap-around (seekable)',
                       'randomness is hash-based per particle (and per spawn cycle for sparks)',
                       'no collisions between particles'],
                      ['count <= 800', 'rain angle 10..15 degrees from vertical']),
    'data_viz': (_cfg_data_viz, _render_data_viz, 1.0,
                 ['chart chosen from the relationship when chart is auto (see choose_chart)',
                  'Arabic labels are drawn RTL (direction=rtl); bar charts mirror to grow right-to-left',
                  'time axes (line chart) stay left-to-right'],
                 ['bar <= 24 bars, line <= 500 points, donut/stacked <= 12 parts, counter <= 6 cards',
                  'scatter <= 500 points, histogram <= 5000 values, bar_race timeline <= 60 rows']),
    'route_map': (_cfg_route_map, _render_route_map, 2.0,
                  ['the map is SCHEMATIC: graticule only, no coastlines or map imagery',
                   'route legs follow great circles on a sphere (R = 6371 km), drawn in equirectangular projection',
                   'marker speed is constant in kilometres along the route'],
                  ['2..12 stops, latitude within +-89 degrees', 'antipodal consecutive stops rejected']),
    'explainer_diagram': (_cfg_explainer, _render_explainer, 3.0,
                          ['one reading direction (ltr, rtl or ttb); order follows steps, then topological order',
                           'edges are straight arrows; crossings are counted and reported'],
                          ['3..7 components, max 5 steps, max 12 edges', 'label size is estimated, not measured']),
    'retro_pixel': (_cfg_retro, _render_retro, 1.0,
                    ['pixels rendered as run-length merged <rect>s at an integer scale',
                     'sprite cycles through 8..12 frames at sprite_fps', 'CRT scanlines only when crt is true'],
                    ['grid <= 160x120', 'scale must fit the canvas']),
    'ui_mock': (_cfg_ui_mock, _render_ui_mock, 1.5,
                ['perspective is a true 3D yaw/pitch projection of every point; text uses the local affine Jacobian',
                 'tilt oscillates between min_tilt and tilt_deg and never rests at 0 degrees',
                 'device art is a generic mock, not a real product'],
                ['tilt 1..30 degrees', 'cursor path <= 20 waypoints']),
    'brand_reveal': (_cfg_brand, _render_brand, 1.6,
                     ['palette tokens: primary, secondary, accent, background, text',
                      'background is transparent unless fill_background is true'],
                     ['duration 0.2..60 s', 'wordmark <= 40 characters']),
}

CATALOGUE = [
    ('shape_morph', 'تحويل أي شكل إلى شكل آخر بنقاط متساوية على طول المحيط وتنعيم الحركة'),
    ('draw_on', 'رسم الخط تدريجيًا من طوله الحقيقي مع أسلوب قلم يدوي اختياري'),
    ('neon_glow', 'لافتة نيون بوميض محسوب وتوهج متدرج يُضاف عند الطلب فقط'),
    ('textures', 'حبيبات فيلم وورق ونقاط طباعة وخطوط مسح وتظليل أطراف — مطفأة إلا بالاسم'),
    ('particles_svg', 'جسيمات غبار وقصاصات ومطر مائل وثلج وشرر محسوبة لكل لحظة'),
    ('data_viz', 'رسوم بيانية متحركة يُختار نوعها من العلاقة مع دعم العربي من اليمين'),
    ('route_map', 'مسار متحرك بين مدن على خريطة تخطيطية بخطوط الطول والعرض'),
    ('explainer_diagram', 'مخطط شرح بصناديق وأسهم يظهر خطوة بخطوة مع إبراز الخطوة الحالية'),
    ('retro_pixel', 'مشهد بكسل قديم بمقياس صحيح وشخصية تمشي وخطوط شاشة CRT اختيارية'),
    ('ui_mock', 'نموذج هاتف أو لابتوب بميل منظوري لا يصل للصفر ومؤشر ونقرات متموجة'),
    ('brand_reveal', 'ظهور الشعار بمربعات تدور وتتثبت أو دائرة كاشفة أو بناء بالخطوط'),
    ('choose_chart', 'اختيار نوع الرسم البياني المناسب من نوع العلاقة بين البيانات'),
]


def _check_params(params):
    if params is None:
        return {}
    if not isinstance(params, dict):
        raise ValueError('params must be a dict')
    if len(params) > MAX_PARAMS:
        raise ValueError(f'params may have at most {MAX_PARAMS} keys')
    if not all(isinstance(k, str) for k in params):
        raise ValueError('param names must be strings')
    return dict(params)


def _render(op, params, t, width, height):
    if not isinstance(op, str) or op not in _FEATURES:
        raise ValueError(f'op must be one of {sorted(_FEATURES)}')
    p = _check_params(params)
    for key in ('t', 'width', 'height'):
        if key in p:
            raise ValueError(f'{key} is passed as an argument, not inside params')
    given = p.pop('id_prefix', None)
    pid = _prefix(given, op, p)
    t, width, height = _canvas(t, width, height)
    cfg_fn, render_fn = _FEATURES[op][0], _FEATURES[op][1]
    cfg = cfg_fn(**p)
    svg, meta = render_fn(cfg, t, width, height, pid)
    return svg, meta, pid


def shape_morph(params, t, width, height):
    """Morph between two shapes (presets, SVG paths or point lists) at time t."""
    return _render('shape_morph', params, t, width, height)[0]


def draw_on(params, t, width, height):
    """Stroke draw-on via dasharray/dashoffset from the measured path length."""
    return _render('draw_on', params, t, width, height)[0]


def neon_glow(params, t, width, height):
    """Neon sign with deterministic flicker; blur-stack glow only when glow=True."""
    return _render('neon_glow', params, t, width, height)[0]


def textures(params, t, width, height):
    """Grain / paper / halftone / scanlines / vignette overlays (off unless named)."""
    return _render('textures', params, t, width, height)[0]


def particles_svg(params, t, width, height):
    """Seeded dust, confetti, rain, snow or sparks at time t."""
    return _render('particles_svg', params, t, width, height)[0]


def data_viz(params, t, width, height):
    """Animated charts (bar, bar_race, line, donut, ring, stacked, counter, histogram, scatter)."""
    return _render('data_viz', params, t, width, height)[0]


def route_map(params, t, width, height):
    """Schematic great-circle route with moving marker on a graticule."""
    return _render('route_map', params, t, width, height)[0]


def explainer_diagram(params, t, width, height):
    """Boxes and arrows revealed step by step with the active step highlighted."""
    return _render('explainer_diagram', params, t, width, height)[0]


def retro_pixel(params, t, width, height):
    """Low-res pixel scene at an integer scale with a walking sprite cycle."""
    return _render('retro_pixel', params, t, width, height)[0]


def ui_mock(params, t, width, height):
    """Phone/laptop mock with perspective tilt, cursor path and click ripples."""
    return _render('ui_mock', params, t, width, height)[0]


def brand_reveal(params, t, width, height):
    """Logo reveal: squares locking, circle wipe or line build, with palette tokens."""
    return _render('brand_reveal', params, t, width, height)[0]


def render_layer(op, params, t, width, height):
    """Timeline entry point: dispatch a feature op to its SVG fragment at time t."""
    return _render(op, params, t, width, height)[0]


def svg_document(fragment, width, height, background=None):
    """Wrap one or more fragments in a standalone <svg> document (for previews)."""
    width = _num(width, 16, MAX_CANVAS, 'width')
    height = _num(height, 16, MAX_CANVAS, 'height')
    if not isinstance(fragment, str):
        raise ValueError('fragment must be a string')
    bg = '' if background is None else \
        f'<rect x="0" y="0" width="{_fmt(width)}" height="{_fmt(height)}" fill="{_color(background, "background")}"/>'
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{_fmt(width)}" height="{_fmt(height)}" '
            f'viewBox="0 0 {_fmt(width)} {_fmt(height)}">{bg}{fragment}</svg>')


def list_catalogue():
    return [{'name': n, 'description_ar': d} for n, d in CATALOGUE]


def _pack(op, result, assumptions, limits):
    return {'op': op, 'result': result, 'assumptions': list(assumptions), 'limits': list(limits)}


def _op_feature(op, params):
    p = _check_params(params)
    t = p.pop('t', _FEATURES[op][2])
    width = p.pop('width', 1920)
    height = p.pop('height', 1080)
    svg, meta, pid = _render(op, p, t, width, height)
    result = {'svg': svg, 't': float(t), 'width': float(width), 'height': float(height),
              'id_prefix': pid, 'bytes': len(svg.encode('utf-8')), 'info': meta}
    return _pack(op, result, _FEATURES[op][3],
                 list(_FEATURES[op][4]) + ['output is a pure function of t: no wall clock, no SMIL, no script',
                                           'all ids prefixed with id_prefix; no external hrefs'])


def _op_choose_chart(*, relationship='trend', n_parts=None, **extra):
    _no_extra(extra)
    chart = choose_chart(relationship, n_parts)
    key = relationship.strip().lower().replace(' ', '_').replace('-', '_')
    key = _REL_SYNONYMS.get(key, key)
    return _pack('choose_chart', {'relationship': key, 'chart': chart, 'reason_ar': _RELATIONSHIPS[key][1],
                                  'rules': {k: v[0] for k, v in _RELATIONSHIPS.items()}},
                 ['composition with more than 5 parts switches from donut to stacked'],
                 ['rule-based mapping, not a statistical test of the data'])


def _op_list_catalogue(**extra):
    _no_extra(extra)
    return _pack('list_catalogue', {'catalogue': list_catalogue(), 'count': len(CATALOGUE)},
                 ['descriptions are one-line Arabic summaries'], ['catalogue is static'])


OPS = {name: name for name in _FEATURES}
OPS.update({'choose_chart': 'choose_chart', 'list_catalogue': 'list_catalogue'})


def run(op, params=None):
    """Validate and dispatch: run('shape_morph', {'t': 0.5}) -> {'op','result','assumptions','limits'}."""
    if not isinstance(op, str) or op not in OPS:
        raise ValueError(f'op must be one of {sorted(OPS)}')
    params = _check_params(params)
    if op in _FEATURES:
        out = _op_feature(op, params)
    elif op == 'choose_chart':
        out = _op_choose_chart(**params)
    else:
        out = _op_list_catalogue(**params)
    try:
        json.dumps(out, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f'{op} produced a non-JSON-serialisable result: {exc}') from exc
    return out
