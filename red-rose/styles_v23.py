"""Red Rose V23: bounded, deterministic visual-style helpers (topics 06.01-06.10).

Pure standard-library Python. No file I/O, no subprocess, no network, no printing.
Every op validates its inputs strictly (ValueError on bools-as-numbers, non-finite
values, unknown parameter names and out-of-range values) and caps its work.

Outputs are SVG strings and JSON-serialisable data. Every SVG this module produces
is parsed with xml.etree before it is returned and must not contain <script>,
event-handler attributes or external references (only local url(#id) / href="#id").

These are code-drawn approximations of styles (rough lines, clay shading, washes),
not painted art and not a substitute for an illustrator; each op returns the
assumptions it makes and the limits it enforces next to its result.
Colour maths: sRGB (IEC 61966-2-1) -> linear -> CIE XYZ (D65) -> CIE Lab; dE76 is the
Euclidean Lab distance; luminance and contrast follow WCAG 2.x.
"""
from __future__ import annotations

import hashlib
import json
import math
import random
import re
import unicodedata
import xml.etree.ElementTree as ET

MAX_PARAMS = 24
MAX_SVG_CHARS = 300_000
_NS = 'http://www.w3.org/2000/svg'

TOPICS = {
    '06.01': 'palette_lock',
    '06.02': 'rough_lines',
    '06.03': 'clay_look',
    '06.04': 'flat_cartoon',
    '06.05': 'machine_drawing',
    '06.06': 'watercolor',
    '06.07': 'mono_style',
    '06.08': 'reference_character',
    '06.09': 'style_guide_check',
    '06.10': 'style_descriptor',
}

TOPIC_NAMES_AR = {
    '06.01': 'ثبات لوحة الألوان',
    '06.02': 'الرسم بالخطوط اليدوية',
    '06.03': 'ستايل الصلصال ثلاثي البعد',
    '06.04': 'أسلوب كرتوني ثنائي الأبعاد',
    '06.05': 'رسم الماكينات بدقة',
    '06.06': 'الرسم المائي والفرشاة',
    '06.07': 'أسلوب الأبيض والأسود',
    '06.08': 'تصميم شخصيات مرجعية',
    '06.09': 'الهوية البصرية للفيديو',
    '06.10': 'توليد أنساق دون تقليد محمي',
}


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


def _str(value, name, max_len=200, *, allow_empty=False):
    if not isinstance(value, str) or len(value) > max_len or (not allow_empty and not value.strip()):
        raise ValueError(f'{name} must be a {"" if allow_empty else "non-empty "}string of <= {max_len} chars')
    return value


_IDENT = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$')


def _ident(value, name):
    if not isinstance(value, str) or not _IDENT.match(value):
        raise ValueError(f'{name} must be an identifier (letters, digits, _ . -; 1..64 chars)')
    return value


def _dict(value, name, max_items=64):
    if not isinstance(value, dict) or len(value) > max_items:
        raise ValueError(f'{name} must be a dict with <= {max_items} items')
    if not all(isinstance(k, str) for k in value):
        raise ValueError(f'{name} keys must be strings')
    return value


def _list(value, name, low, high):
    if not isinstance(value, (list, tuple)) or not low <= len(value) <= high:
        raise ValueError(f'{name} must be a list of {low}..{high} items')
    return list(value)


def _keys(d, allowed, name, required=()):
    unknown = set(d) - set(allowed)
    if unknown:
        raise ValueError(f'{name}: unknown field(s): ' + ', '.join(sorted(unknown)))
    missing = [k for k in required if k not in d]
    if missing:
        raise ValueError(f'{name}: missing field(s): ' + ', '.join(missing))


def _pack(op, result, assumptions, limits):
    return {'op': op, 'result': result, 'assumptions': list(assumptions),
            'limits': list(limits)}


def _sha(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False,
                                     separators=(',', ':')).encode('utf-8')).hexdigest()


# --------------------------------------------------------------------------- colour maths

_HEX = re.compile(r'^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$')
_NAMED = {
    'black': '#000000', 'white': '#ffffff', 'red': '#ff0000', 'green': '#008000',
    'lime': '#00ff00', 'blue': '#0000ff', 'yellow': '#ffff00', 'gray': '#808080',
    'grey': '#808080', 'orange': '#ffa500', 'purple': '#800080', 'silver': '#c0c0c0',
    'navy': '#000080', 'teal': '#008080', 'maroon': '#800000', 'olive': '#808000',
}


def _hex(value, name):
    if not isinstance(value, str) or not _HEX.match(value.strip()):
        raise ValueError(f'{name} must be a #rgb or #rrggbb colour')
    h = value.strip()[1:].lower()
    if len(h) == 3:
        h = ''.join(c * 2 for c in h)
    return '#' + h


def _rgb(h):
    return [int(h[i:i + 2], 16) / 255.0 for i in (1, 3, 5)]


def _to_hex(rgb):
    return '#' + ''.join(f'{max(0, min(255, round(c * 255))):02x}' for c in rgb)


def _lin(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _enc(c):
    c = max(0.0, min(1.0, c))
    return 12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


def _luminance(h):
    r, g, b = (_lin(c) for c in _rgb(h))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _lab(h):
    r, g, b = (_lin(c) for c in _rgb(h))
    x = (0.4124564 * r + 0.3575761 * g + 0.1804375 * b) / 0.95047
    y = (0.2126729 * r + 0.7151522 * g + 0.0721750 * b) / 1.0
    z = (0.0193339 * r + 0.1191920 * g + 0.9503041 * b) / 1.08883
    d = 6 / 29

    def f(t):
        return t ** (1 / 3) if t > d ** 3 else t / (3 * d * d) + 4 / 29
    fx, fy, fz = f(x), f(y), f(z)
    return [116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)]


def _de76(a, b):
    return math.dist(_lab(a), _lab(b))


def _mix_linear(a, b, t):
    """Mix two hex colours in linear light: (1-t)*a + t*b."""
    la = [_lin(c) for c in _rgb(a)]
    lb = [_lin(c) for c in _rgb(b)]
    return _to_hex([_enc((1 - t) * x + t * y) for x, y in zip(la, lb)])


def _contrast(h1, h2):
    l1, l2 = _luminance(h1), _luminance(h2)
    hi, lo = max(l1, l2), min(l1, l2)
    return (hi + 0.05) / (lo + 0.05)


def _color_token(value):
    """Return (hex, None), (None, None) for no-paint/references, or (None, raw) if unparsed."""
    t = str(value).strip().lower()
    t = re.sub(r'\s*!important$', '', t)
    if t in ('', 'none', 'transparent', 'currentcolor', 'inherit', 'initial', 'unset') \
            or t.startswith('url('):
        return None, None
    if _HEX.match(t):
        return _hex(t, 'colour'), None
    m = re.fullmatch(r'rgb\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*\)', t)
    if m and all(int(v) <= 255 for v in m.groups()):
        return _to_hex([int(v) / 255 for v in m.groups()]), None
    if t in _NAMED:
        return _NAMED[t], None
    return None, t[:40]


# --------------------------------------------------------------------------- SVG helpers

def _f(v, nd=2):
    s = f'{v:.{nd}f}'.rstrip('0').rstrip('.')
    return '0' if s in ('-0', '', '-') else s


def _esc(s):
    return (str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            .replace('"', '&quot;'))


def _local(tag):
    return str(tag).rsplit('}', 1)[-1]


def _svg_issues(root):
    """Unsafe markup inside a parsed SVG tree (scripts, handlers, external references)."""
    issues = []
    for el in root.iter():
        tag = _local(el.tag).lower()
        if tag in ('script', 'foreignobject', 'iframe', 'object', 'embed'):
            issues.append(f'element <{tag}>')
        if tag == 'style' and el.text and re.search(r'@import|url\(\s*[\'"]?(?!#)', el.text, re.I):
            issues.append('external reference in <style>')
        for k, v in el.attrib.items():
            lk = _local(k).lower()
            if lk.startswith('on'):
                issues.append(f'event handler {lk}')
            if lk == 'href' and not str(v).strip().startswith('#'):
                issues.append('external href')
            for ref in re.findall(r'url\(\s*([^)]*)\)', str(v)):
                if not ref.strip().strip('\'"').startswith('#'):
                    issues.append('external url() reference')
    return issues


def _finish(svg):
    """Parse produced SVG and refuse to return anything unsafe (internal invariant)."""
    root = ET.fromstring(svg)
    issues = _svg_issues(root)
    if issues or _local(root.tag) != 'svg':
        raise RuntimeError('internal error: produced unsafe SVG: ' + '; '.join(issues))
    return svg


def _parse_svg_input(svg, name):
    if not isinstance(svg, str) or not svg.strip() or len(svg) > MAX_SVG_CHARS:
        raise ValueError(f'{name} must be a non-empty SVG string of <= {MAX_SVG_CHARS} chars')
    if re.search(r'<!\s*(DOCTYPE|ENTITY)', svg, re.I):
        raise ValueError(f'{name}: DOCTYPE/ENTITY declarations are not accepted')
    try:
        root = ET.fromstring(svg)
    except ET.ParseError as exc:
        raise ValueError(f'{name} is not well-formed XML: {exc}') from None
    if _local(root.tag) != 'svg':
        raise ValueError(f'{name} root element must be <svg>')
    return root


_COLOR_ATTRS = ('fill', 'stroke', 'stop-color', 'flood-color', 'lighting-color', 'color')


def _scene_colours(root):
    """All fill/stroke-like colours (attributes and inline style) -> ({hex: count}, [unparsed])."""
    found, unparsed = {}, set()
    for el in root.iter():
        values = [v for k, v in el.attrib.items() if _local(k) in _COLOR_ATTRS]
        style = el.attrib.get('style')
        if style:
            for decl in style.split(';'):
                if ':' in decl:
                    k, v = decl.split(':', 1)
                    if k.strip().lower() in _COLOR_ATTRS:
                        values.append(v)
        for v in values:
            hx, raw = _color_token(v)
            if hx:
                found[hx] = found.get(hx, 0) + 1
            elif raw:
                unparsed.add(raw)
    return found, sorted(unparsed)


def _svg_open(w, h, extra=''):
    return (f'<svg xmlns="{_NS}" viewBox="0 0 {_f(w)} {_f(h)}" width="{_f(w)}" '
            f'height="{_f(h)}"{extra}>')


# --------------------------------------------------------------------------- 06.01 palette_lock

_EX_IDENTITY = {'name': 'rose_courier',
                'palette': {'background': '#f6f1e7', 'skin': '#f2c9a0', 'hair': '#3b2a20',
                            'coat': '#b23a48', 'trousers': '#2e4057', 'outline': '#1b1b1b'}}


def _example_scene(p, coat, dx):
    return (_svg_open(200, 200) + f'<rect width="200" height="200" fill="{p["background"]}"/>'
            f'<g stroke="{p["outline"]}" stroke-width="2">'
            f'<rect x="{70 + dx}" y="80" width="60" height="60" rx="8" fill="{coat}"/>'
            f'<rect x="{74 + dx}" y="140" width="20" height="45" fill="{p["trousers"]}"/>'
            f'<rect x="{106 + dx}" y="140" width="20" height="45" fill="{p["trousers"]}"/>'
            f'<circle cx="{100 + dx}" cy="55" r="24" fill="{p["skin"]}"/>'
            f'<path d="M{78 + dx} 50 Q{100 + dx} 20 {122 + dx} 50 Z" style="fill:{p["hair"]}"/>'
            '</g></svg>')


def _identity(identity):
    _dict(identity, 'identity', 4)
    _keys(identity, ('name', 'palette'), 'identity', ('name', 'palette'))
    name = _str(identity['name'], 'identity.name', 64)
    pal = _dict(identity['palette'], 'identity.palette', 32)
    if not pal:
        raise ValueError('identity.palette must contain at least one role')
    palette = {_ident(r, 'palette role'): _hex(c, f'palette.{r}') for r, c in pal.items()}
    return name, palette


def palette_lock(*, identity=None, scenes=None, tolerance=2.0, **extra):
    """Fingerprint an identity palette and check SVG scenes use only its colours.

    identity: {name, palette: {role: hex}}. palette_fingerprint = sha256 of the sorted
    unique normalised colours joined by ',' (role names and order do not matter);
    roles_fingerprint also binds roles. Each scene (SVG string or {name, svg}) has its
    fill/stroke/stop-color/flood-color colours extracted from attributes and inline
    style; a colour passes if its CIE76 dE to the nearest palette colour <= tolerance.
    Unparsable colour values (hsl(), unknown names) are reported and fail the scene.
    """
    _no_extra(extra)
    name, palette = _identity(_EX_IDENTITY if identity is None else identity)
    tolerance = _num(tolerance, 0, 50, 'tolerance')
    if scenes is None:
        if identity is not None:
            raise ValueError('scenes are required when an identity is given')
        p = palette
        scenes = [{'name': 'scene_a', 'svg': _example_scene(p, p['coat'], 0)},
                  {'name': 'scene_b', 'svg': _example_scene(p, '#b33a48', 30)}]
    scenes = _list(scenes, 'scenes', 1, 8)
    colours = sorted(set(palette.values()))
    report, all_ok = [], True
    for i, sc in enumerate(scenes):
        if isinstance(sc, str):
            sname, svg = f'scene_{i + 1}', sc
        else:
            _dict(sc, f'scenes[{i}]', 2)
            _keys(sc, ('name', 'svg'), f'scenes[{i}]', ('svg',))
            sname, svg = _str(sc.get('name', f'scene_{i + 1}'), 'scene name', 64), sc['svg']
        root = _parse_svg_input(svg, f'scenes[{i}]')
        found, unparsed = _scene_colours(root)
        used, off = [], []
        for hx in sorted(found):
            best_role, best, best_de = None, None, float('inf')
            for role, pc in sorted(palette.items()):
                de = _de76(hx, pc)
                if de < best_de:
                    best_role, best, best_de = role, pc, de
            entry = {'colour': hx, 'count': found[hx], 'nearest_role': best_role,
                     'nearest': best, 'delta_e': round(best_de, 4), 'ok': best_de <= tolerance}
            used.append(entry)
            if not entry['ok']:
                off.append(entry)
        ok = not off and not unparsed
        all_ok = all_ok and ok
        report.append({'name': sname, 'colours_used': used, 'off_palette': off,
                       'unparsed': unparsed, 'unsafe_markup': _svg_issues(root), 'passed': ok})
    result = {'identity': name, 'palette': palette, 'palette_sorted': colours,
              'palette_fingerprint': hashlib.sha256(','.join(colours).encode()).hexdigest(),
              'roles_fingerprint': _sha(palette), 'tolerance_delta_e76': tolerance,
              'scenes': report, 'all_passed': all_ok}
    return _pack('palette_lock', result,
                 ['colours compared in CIE Lab (D65) with CIE76 dE; dE ~2.3 is about one just-noticeable difference',
                  'only fill/stroke/stop-color/flood-color/lighting-color/color attributes and inline style are read; '
                  'CSS in <style> blocks, gradients referenced by url() and raster images are not inspected',
                  'opacity/blending is ignored: a 50 % opaque palette colour still counts as on-palette'],
                 ['<= 8 scenes, <= 300000 chars each, DOCTYPE/ENTITY rejected', '<= 32 palette roles',
                  'tolerance in [0, 50] dE76'])


# --------------------------------------------------------------------------- 06.02 rough_lines

def rough_lines(*, shape='rectangle', points=None, closed=False, rect=None, circle=None,
                seed=7, roughness=1.5, bowing=1.0, strokes=2, circle_segments=24,
                stroke='#222222', stroke_width=1.5, **extra):
    """Hand-drawn look: jitter a polyline / rectangle / circle into rough cubic paths.

    Each source segment a->b becomes 'M a' C c1 c2 b'' where a', b' are a and b moved by
    uniform(-roughness, roughness) per axis (so every drawn endpoint lies within
    roughness*sqrt(2) of its source vertex, plus 1e-3 rounding) and the control points
    bow sideways by bowing * roughness * |ab| / 50 * uniform(-1, 1). strokes > 1 draws
    extra independently jittered passes (the multi-stroke sketch look). A circle is
    first approximated by circle_segments chords. Same seed -> identical SVG.
    """
    _no_extra(extra)
    shape = _choice(shape, {'polyline', 'rectangle', 'circle'}, 'shape')
    seed = _int(seed, 0, 2**31 - 1, 'seed')
    roughness = _num(roughness, 0, 50, 'roughness')
    bowing = _num(bowing, 0, 10, 'bowing')
    strokes = _int(strokes, 1, 4, 'strokes')
    circle_segments = _int(circle_segments, 6, 128, 'circle_segments')
    stroke = _hex(stroke, 'stroke')
    stroke_width = _num(stroke_width, 0.1, 50, 'stroke_width')
    if not isinstance(closed, bool):
        raise ValueError('closed must be true or false')
    if shape == 'polyline':
        pts = [[20.0, 120.0], [80.0, 40.0], [140.0, 110.0], [190.0, 30.0]] if points is None else points
        pts = [[_num(c, -1e5, 1e5, f'points[{i}]') for c in _list(p, f'points[{i}]', 2, 2)]
               for i, p in enumerate(_list(pts, 'points', 2, 200))]
    elif shape == 'rectangle':
        x, y, w, h = ([20.0, 20.0, 160.0, 100.0] if rect is None else
                      [_num(v, -1e5, 1e5, 'rect') for v in _list(rect, 'rect', 4, 4)])
        if w <= 0 or h <= 0:
            raise ValueError('rect width and height must be > 0')
        pts, closed = [[x, y], [x + w, y], [x + w, y + h], [x, y + h]], True
    else:
        cx, cy, r = ([100.0, 80.0, 50.0] if circle is None else
                     [_num(v, -1e5, 1e5, 'circle') for v in _list(circle, 'circle', 3, 3)])
        if r <= 0:
            raise ValueError('circle radius must be > 0')
        pts = [[cx + r * math.cos(2 * math.pi * i / circle_segments),
                cy + r * math.sin(2 * math.pi * i / circle_segments)]
               for i in range(circle_segments)]
        closed = True
    segs = [(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]
    if closed and len(pts) > 2:
        segs.append((pts[-1], pts[0]))
    if len(segs) * strokes > 2000:
        raise ValueError('segments * strokes must be <= 2000')

    rng = random.Random(seed)

    def jit(v):
        return round(v + rng.uniform(-roughness, roughness), 3)
    paths, max_dev = [], 0.0
    for _ in range(strokes):
        parts = []
        for a, b in segs:
            a2 = [jit(a[0]), jit(a[1])]
            b2 = [jit(b[0]), jit(b[1])]
            max_dev = max(max_dev, math.dist(a, a2), math.dist(b, b2))
            dx, dy = b2[0] - a2[0], b2[1] - a2[1]
            length = math.hypot(dx, dy) or 1.0
            nx, ny = -dy / length, dx / length
            bow = bowing * roughness * math.dist(a, b) / 50 * rng.uniform(-1, 1)
            ctrl = []
            for t in (1 / 3, 2 / 3):
                ctrl.append([round(a2[0] + dx * t + nx * bow + rng.uniform(-roughness, roughness) / 2, 3),
                             round(a2[1] + dy * t + ny * bow + rng.uniform(-roughness, roughness) / 2, 3)])
            parts.append(f'M{_f(a2[0], 3)} {_f(a2[1], 3)} C{_f(ctrl[0][0], 3)} {_f(ctrl[0][1], 3)} '
                         f'{_f(ctrl[1][0], 3)} {_f(ctrl[1][1], 3)} {_f(b2[0], 3)} {_f(b2[1], 3)}')
        paths.append(' '.join(parts))
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    pad = 3 * roughness + stroke_width + 4 + bowing * roughness * 3
    vx, vy = min(xs) - pad, min(ys) - pad
    vw, vh = max(xs) - min(xs) + 2 * pad, max(ys) - min(ys) + 2 * pad
    body = ''.join(f'<path d="{d}" fill="none" stroke="{stroke}" stroke-width="{_f(stroke_width)}" '
                   f'stroke-linecap="round" stroke-linejoin="round" opacity="{_f(1 if i == 0 else 0.75)}"/>'
                   for i, d in enumerate(paths))
    svg = _finish(f'<svg xmlns="{_NS}" viewBox="{_f(vx)} {_f(vy)} {_f(vw)} {_f(vh)}" '
                  f'width="{_f(vw)}" height="{_f(vh)}">{body}</svg>')
    bound = roughness * math.sqrt(2) + 1e-3
    result = {'shape': shape, 'seed': seed, 'roughness': roughness, 'bowing': bowing,
              'strokes': strokes, 'source_points': pts, 'segments': len(segs), 'paths': paths,
              'endpoint_max_deviation': max_dev, 'endpoint_bound': bound,
              'within_bound': max_dev <= bound, 'svg': svg}
    return _pack('rough_lines', result,
                 ['rough.js-like idea re-implemented from scratch: per-segment endpoint jitter + bowed cubic',
                  'segments are drawn as separate sub-paths, so corners overlap like a pen sketch',
                  'a circle is a chord polygon before roughening, not a true arc'],
                 ['<= 200 polyline points, segments * strokes <= 2000, strokes <= 4',
                  'roughness <= 50, bowing <= 10, coordinates rounded to 1e-3'])


# --------------------------------------------------------------------------- 06.03 clay_look

def _gloss_audit(root, base, max_specular):
    stops = []
    for el in root.iter():
        if _local(el.tag) == 'stop':
            v = el.attrib.get('stop-color')
            if v is None and 'style' in el.attrib:
                m = re.search(r'stop-color\s*:\s*([^;]+)', el.attrib['style'])
                v = m.group(1) if m else None
            hx, _ = _color_token(v or '')
            if hx:
                stops.append(hx)
    if not stops:
        raise ValueError('audited SVG has no gradient stop colours to audit')
    brightest = max(stops, key=_luminance)
    yb, yh = _luminance(base), _luminance(brightest)
    gloss = 0.0 if yb >= 1.0 else max(0.0, (yh - yb) / (1.0 - yb))
    return {'stop_colours': stops, 'brightest': brightest, 'base_luminance': yb,
            'highlight_luminance': yh, 'gloss_ratio': gloss,
            'lightness_lift_L': _lab(brightest)[0] - _lab(base)[0],
            'max_specular': max_specular, 'passed': gloss <= max_specular + 1e-12}


def clay_look(*, base='#d9825b', specular=0.12, max_specular=0.25, shade=0.35,
              shadow_blur=6.0, shape='sphere', size=240, audit_svg=None, **extra):
    """Soft clay material: radial gradient body + blurred contact shadow + low specular.

    Highlight = base mixed toward white by `specular` in linear light, core shadow = base
    mixed toward black by `shade`. Gloss audit: gloss_ratio = (Y_brightest - Y_base) /
    (1 - Y_base) over all gradient stops (Y = relative luminance); for this generator it
    equals `specular` up to 8-bit rounding. Passes iff gloss_ratio <= max_specular
    (no artificial shine). audit_svg audits a supplied SVG instead of generating one.
    """
    _no_extra(extra)
    base = _hex(base, 'base')
    specular = _num(specular, 0, 1, 'specular')
    max_specular = _num(max_specular, 0, 1, 'max_specular')
    shade = _num(shade, 0, 0.9, 'shade')
    shadow_blur = _num(shadow_blur, 0, 50, 'shadow_blur')
    shape = _choice(shape, {'sphere', 'pill'}, 'shape')
    size = _int(size, 64, 1024, 'size')
    if audit_svg is not None:
        root = _parse_svg_input(audit_svg, 'audit_svg')
        audit = _gloss_audit(root, base, max_specular)
        audit['unsafe_markup'] = _svg_issues(root)
        return _pack('clay_look', {'mode': 'audit', 'base': base, 'audit': audit},
                     ['audit reads gradient <stop> colours only; flat fills and filters are not measured',
                      'gloss is a luminance lift toward white, not a BRDF measurement'],
                     ['<= 300000 chars, DOCTYPE/ENTITY rejected'])
    high = _mix_linear(base, '#ffffff', specular)
    dark = _mix_linear(base, '#000000', shade)
    s = size
    c = s / 2
    body = (f'<circle cx="{_f(c)}" cy="{_f(c * 0.92)}" r="{_f(s * 0.32)}" fill="url(#clayBody)"/>'
            if shape == 'sphere' else
            f'<rect x="{_f(s * 0.18)}" y="{_f(s * 0.36)}" width="{_f(s * 0.64)}" height="{_f(s * 0.3)}" '
            f'rx="{_f(s * 0.15)}" fill="url(#clayBody)"/>')
    svg = _finish(
        _svg_open(s, s) +
        '<defs>'
        f'<radialGradient id="clayBody" cx="0.4" cy="0.36" r="0.72" fx="0.34" fy="0.28">'
        f'<stop offset="0" stop-color="{high}"/><stop offset="0.42" stop-color="{base}"/>'
        f'<stop offset="1" stop-color="{dark}"/></radialGradient>'
        f'<filter id="claySoftShadow" x="-50%" y="-50%" width="200%" height="200%">'
        f'<feGaussianBlur stdDeviation="{_f(shadow_blur)}"/></filter>'
        '</defs>'
        f'<rect width="{s}" height="{s}" fill="#efe8de"/>'
        f'<ellipse cx="{_f(c)}" cy="{_f(s * 0.86)}" rx="{_f(s * 0.3)}" ry="{_f(s * 0.06)}" '
        f'fill="#000000" fill-opacity="0.22" filter="url(#claySoftShadow)"/>'
        + body + '</svg>')
    audit = _gloss_audit(ET.fromstring(svg), base, max_specular)
    result = {'mode': 'generate', 'base': base, 'highlight': high, 'core_shadow': dark,
              'specular': specular, 'audit': audit, 'svg': svg}
    return _pack('clay_look', result,
                 ['one light from the upper left; shading is a 3-stop radial gradient, not a 3D render',
                  'colour mixing is done in linear light then re-encoded to 8-bit sRGB',
                  'no subsurface scattering, fingerprints or surface texture: a code-drawn approximation of clay'],
                 ['size 64..1024 px, shadow_blur <= 50, shade <= 0.9',
                  'gloss_ratio carries about +/-0.005 8-bit quantisation error near the limit'])


# --------------------------------------------------------------------------- 06.04 flat_cartoon

_PROPS = ('head_r', 'neck', 'torso', 'shoulder_w', 'hip_w', 'upper_arm', 'forearm', 'thigh', 'shin')
_EX_PROPS = {'head_r': 18.0, 'neck': 8.0, 'torso': 60.0, 'shoulder_w': 17.0, 'hip_w': 10.0,
             'upper_arm': 32.0, 'forearm': 28.0, 'thigh': 40.0, 'shin': 38.0}
_ANGLES = ('torso', 'head', 'l_shoulder', 'l_elbow', 'r_shoulder', 'r_elbow',
           'l_hip', 'l_knee', 'r_hip', 'r_knee')
_EX_POSES = [
    {'name': 'stand', 'angles': {'l_shoulder': -8, 'r_shoulder': 8, 'l_hip': -3, 'r_hip': 3}},
    {'name': 'wave', 'angles': {'l_shoulder': -10, 'r_shoulder': 150, 'r_elbow': 25, 'head': -8,
                                'l_hip': -3, 'r_hip': 3}},
    {'name': 'walk', 'angles': {'torso': 4, 'l_shoulder': 22, 'r_shoulder': -20, 'r_elbow': 15,
                                'l_hip': -22, 'l_knee': 18, 'r_hip': 20, 'r_knee': 4}},
]
_CARTOON_COLOURS = {'skin': '#f2c9a0', 'shirt': '#b23a48', 'pants': '#2e4057',
                    'hair': '#3b2a20', 'outline': '#1b1b1b'}


def _dir(deg):
    a = math.radians(deg)
    return math.sin(a), math.cos(a)  # 0 deg points down (+y in SVG)


def _add(p, d, length):
    return [p[0] + d[0] * length, p[1] + d[1] * length]


def _fk(pr, ang, root):
    lean = ang['torso']
    up = 180.0 + lean
    u = _dir(up)
    perp = (u[1], -u[0])
    j = {'root': list(root)}
    j['neck_base'] = _add(root, u, pr['torso'])
    j['head_center'] = _add(j['neck_base'], _dir(up + ang['head']), pr['neck'] + pr['head_r'])
    for side, sgn in (('l', 1), ('r', -1)):
        sh = _add(j['neck_base'], perp, sgn * pr['shoulder_w'])
        a_abs = lean + ang[f'{side}_shoulder']
        el = _add(sh, _dir(a_abs), pr['upper_arm'])
        wr = _add(el, _dir(a_abs + ang[f'{side}_elbow']), pr['forearm'])
        hp = _add(root, perp, sgn * pr['hip_w'])
        l_abs = lean + ang[f'{side}_hip']
        kn = _add(hp, _dir(l_abs), pr['thigh'])
        an = _add(kn, _dir(l_abs + ang[f'{side}_knee']), pr['shin'])
        j.update({f'{side}_shoulder': sh, f'{side}_elbow': el, f'{side}_wrist': wr,
                  f'{side}_hip': hp, f'{side}_knee': kn, f'{side}_ankle': an})
        j[f'_{side}_arm'] = a_abs
        j[f'_{side}_fore'] = a_abs + ang[f'{side}_elbow']
        j[f'_{side}_thigh'] = l_abs
        j[f'_{side}_shin'] = l_abs + ang[f'{side}_knee']
    j['_up'] = up
    j['_head'] = up + ang['head']
    return j


def _bone_lengths(j):
    d = math.dist
    out = {'torso': d(j['root'], j['neck_base']),
           'neck_plus_head_r': d(j['neck_base'], j['head_center'])}
    for s in ('l', 'r'):
        out[f'{s}_shoulder_offset'] = d(j['neck_base'], j[f'{s}_shoulder'])
        out[f'{s}_upper_arm'] = d(j[f'{s}_shoulder'], j[f'{s}_elbow'])
        out[f'{s}_forearm'] = d(j[f'{s}_elbow'], j[f'{s}_wrist'])
        out[f'{s}_hip_offset'] = d(j['root'], j[f'{s}_hip'])
        out[f'{s}_thigh'] = d(j[f'{s}_hip'], j[f'{s}_knee'])
        out[f'{s}_shin'] = d(j[f'{s}_knee'], j[f'{s}_ankle'])
    return out


def _part(name, pivot, deg, length, width, colour, outline):
    return (f'<g id="part-{name}" data-pivot="{_f(pivot[0], 3)} {_f(pivot[1], 3)}" '
            f'transform="translate({_f(pivot[0], 3)} {_f(pivot[1], 3)}) rotate({_f(-deg, 3)})">'
            f'<rect x="{_f(-width / 2)}" y="{_f(-width / 4)}" width="{_f(width)}" '
            f'height="{_f(length + width / 2)}" rx="{_f(width / 2)}" fill="{colour}" '
            f'stroke="{outline}" stroke-width="1.5"/></g>')


def _figure_svg(j, pr, col, idx):
    o = col['outline']
    hr = pr['head_r']
    parts = []
    for s in ('r', 'l'):  # far side first
        parts.append(_part(f'{s}_thigh', j[f'{s}_hip'], j[f'_{s}_thigh'], pr['thigh'], 13, col['pants'], o))
        parts.append(_part(f'{s}_shin', j[f'{s}_knee'], j[f'_{s}_shin'], pr['shin'], 11, col['pants'], o))
        if s == 'r':
            parts.append(_part('r_upper_arm', j['r_shoulder'], j['_r_arm'], pr['upper_arm'], 10, col['shirt'], o))
            parts.append(_part('r_forearm', j['r_elbow'], j['_r_fore'], pr['forearm'], 9, col['skin'], o))
    parts.append(_part('torso', j['root'], j['_up'], pr['torso'], 2 * pr['shoulder_w'] - 4, col['shirt'], o))
    parts.append(_part('neck', j['neck_base'], j['_head'], pr['neck'], 8, col['skin'], o))
    hc = j['head_center']
    parts.append(f'<g id="part-head" data-pivot="{_f(j["neck_base"][0], 3)} {_f(j["neck_base"][1], 3)}" '
                 f'transform="translate({_f(hc[0], 3)} {_f(hc[1], 3)}) rotate({_f(-(j["_head"] - 180), 3)})">'
                 f'<circle r="{_f(hr)}" fill="{col["skin"]}" stroke="{o}" stroke-width="1.5"/>'
                 f'<path d="M{_f(-hr)} {_f(-2)} Q0 {_f(-hr * 1.6)} {_f(hr)} {_f(-2)} Q0 {_f(-hr * 0.6)} '
                 f'{_f(-hr)} {_f(-2)} Z" fill="{col["hair"]}"/>'
                 f'<circle cx="{_f(-hr * 0.35)}" cy="{_f(hr * 0.1)}" r="2" fill="{o}"/>'
                 f'<circle cx="{_f(hr * 0.35)}" cy="{_f(hr * 0.1)}" r="2" fill="{o}"/></g>')
    parts.append(_part('l_upper_arm', j['l_shoulder'], j['_l_arm'], pr['upper_arm'], 10, col['shirt'], o))
    parts.append(_part('l_forearm', j['l_elbow'], j['_l_fore'], pr['forearm'], 9, col['skin'], o))
    return f'<g id="pose-{idx}">' + ''.join(parts) + '</g>'


def flat_cartoon(*, proportions=None, poses=None, palette=None, **extra):
    """Flat 2D cut-out character: independent SVG part groups with joint pivots, posed by FK.

    Angles in degrees; 0 = hanging straight down; torso/hip/shoulder angles are relative
    to the torso lean, elbow/knee relative to their parent bone, head relative to the
    torso. Every part is drawn in its own local frame with a fixed length and placed by
    translate(pivot) rotate(angle), so bone lengths and the head/body ratio are locked
    by construction; the result re-measures them from the solved joints.
    head_ratio = 2*head_r / (head_r + |neck_base->head_center| + |torso| + |l_thigh| + |l_shin|).
    """
    _no_extra(extra)
    pr = dict(_EX_PROPS)
    if proportions is not None:
        _dict(proportions, 'proportions', len(_PROPS))
        _keys(proportions, _PROPS, 'proportions')
        for k, v in proportions.items():
            pr[k] = _num(v, 1, 500, f'proportions.{k}')
    col = dict(_CARTOON_COLOURS)
    if palette is not None:
        _dict(palette, 'palette', len(col))
        _keys(palette, tuple(col), 'palette')
        col.update({k: _hex(v, f'palette.{k}') for k, v in palette.items()})
    poses = _list(_EX_POSES if poses is None else poses, 'poses', 1, 12)
    nominal = {'torso': pr['torso'], 'neck_plus_head_r': pr['neck'] + pr['head_r']}
    for s in ('l', 'r'):
        nominal.update({f'{s}_shoulder_offset': pr['shoulder_w'], f'{s}_upper_arm': pr['upper_arm'],
                        f'{s}_forearm': pr['forearm'], f'{s}_hip_offset': pr['hip_w'],
                        f'{s}_thigh': pr['thigh'], f'{s}_shin': pr['shin']})
    out, figures, ratios, max_dev = [], [], [], 0.0
    reach = pr['torso'] + pr['neck'] + 2 * pr['head_r'] + pr['upper_arm'] + pr['forearm'] + \
        pr['thigh'] + pr['shin'] + 20
    cell = 2 * reach
    for i, pose in enumerate(poses):
        _dict(pose, f'poses[{i}]', 2)
        _keys(pose, ('name', 'angles'), f'poses[{i}]', ('angles',))
        pname = _ident(pose.get('name', f'pose{i + 1}'), f'poses[{i}].name')
        ang_in = _dict(pose['angles'], f'poses[{i}].angles', len(_ANGLES))
        _keys(ang_in, _ANGLES, f'poses[{i}].angles')
        ang = {k: _num(ang_in.get(k, 0.0), -180, 180, f'poses[{i}].angles.{k}') for k in _ANGLES}
        j = _fk(pr, ang, (reach, reach))
        bones = _bone_lengths(j)
        dev = max(abs(bones[k] - nominal[k]) for k in nominal)
        max_dev = max(max_dev, dev)
        ratio = 2 * pr['head_r'] / (pr['head_r'] + bones['neck_plus_head_r'] + bones['torso']
                                    + bones['l_thigh'] + bones['l_shin'])
        ratios.append(ratio)
        fig = _figure_svg(j, pr, col, i)
        figures.append(f'<g transform="translate({_f(i * cell)} 0)">{fig}</g>')
        svg = _finish(_svg_open(cell, cell) + fig + '</svg>')
        out.append({'name': pname, 'angles': ang,
                    'joints': {k: [round(v[0], 6), round(v[1], 6)] for k, v in j.items()
                               if not k.startswith('_')},
                    'bone_lengths': bones, 'max_bone_deviation': dev, 'head_ratio': ratio, 'svg': svg})
    spread = max(ratios) - min(ratios)
    sheet = _finish(_svg_open(cell * len(poses), cell) + ''.join(figures) + '</svg>')
    result = {'proportions': pr, 'nominal_bone_lengths': nominal, 'palette': col, 'poses': out,
              'proportion_lock': {'max_bone_deviation': max_dev, 'head_ratio_spread': spread,
                                  'tolerance': 1e-9, 'locked': max_dev <= 1e-9 and spread <= 1e-9},
              'sheet_svg': sheet}
    return _pack('flat_cartoon', result,
                 ['planar forward kinematics with rigid bones; no squash-and-stretch, no IK, no overlap solving',
                  'parts are simple rounded rectangles and a circle head: a rig template, not finished character art',
                  'SVG coordinates are rounded to 1e-3; locked lengths are measured on the unrounded joints'],
                 ['<= 12 poses, angles in [-180, 180] deg, proportions in [1, 500] units'])


# --------------------------------------------------------------------------- 06.05 machine_drawing

def _fit(clearance, cmin, cmax, what):
    if clearance < 0:
        return {'code': 'interference', 'what': what, 'clearance': clearance,
                'message': f'{what}: shaft is larger than the hole by {-clearance:.4f} mm'}
    if clearance < cmin:
        return {'code': 'too_tight', 'what': what, 'clearance': clearance,
                'message': f'{what}: clearance {clearance:.4f} mm < minimum {cmin} mm'}
    if clearance > cmax:
        return {'code': 'too_loose', 'what': what, 'clearance': clearance,
                'message': f'{what}: clearance {clearance:.4f} mm > maximum {cmax} mm'}
    return None


def machine_drawing(*, module=2.0, teeth=20, pressure_angle=20.0, bore=10.0, shaft_diameter=9.95,
                    shaft_length=60.0, link_length=80.0, link_hole=10.05, clearance_min=0.01,
                    clearance_max=0.2, **extra):
    """Dimensioned drawing of a spur gear, a shaft and a two-hole link (millimetres).

    Gear (ISO 21771 / standard full-depth): pitch d = m*z, tip da = m*(z+2),
    root df = m*(z-2.5), base db = d*cos(alpha), circular pitch p = pi*m.
    Connection check: clearance = hole - shaft for the gear bore and the link hole;
    negative -> interference, below clearance_min -> too_tight, above clearance_max ->
    too_loose. A bore that leaves less than one module of rim under the root circle is
    reported as rim_too_thin.
    """
    _no_extra(extra)
    m = _num(module, 0.1, 50, 'module')
    z = _int(teeth, 6, 300, 'teeth')
    pa = _num(pressure_angle, 14.5, 30, 'pressure_angle')
    bore = _num(bore, 0.1, 1e4, 'bore', low_open=True)
    shaft = _num(shaft_diameter, 0.1, 1e4, 'shaft_diameter')
    slen = _num(shaft_length, 1, 1e5, 'shaft_length')
    llen = _num(link_length, 1, 1e5, 'link_length')
    lhole = _num(link_hole, 0.1, 1e4, 'link_hole')
    cmin = _num(clearance_min, 0, 10, 'clearance_min')
    cmax = _num(clearance_max, 0, 10, 'clearance_max')
    if cmin > cmax:
        raise ValueError('clearance_min must be <= clearance_max')
    if 2 * lhole >= llen:
        raise ValueError('link_length must exceed twice link_hole (bosses would overlap)')
    d = m * z
    da = m * (z + 2)
    df = m * (z - 2.5)
    db = d * math.cos(math.radians(pa))
    issues = []
    if bore > df - 2 * m:
        issues.append({'code': 'rim_too_thin', 'what': 'gear bore',
                       'message': f'bore {bore} mm leaves < 1 module of rim under root diameter {df:.3f} mm'})
    for clr, what in ((bore - shaft, 'gear bore / shaft'), (lhole - shaft, 'link hole / shaft')):
        f = _fit(clr, cmin, cmax, what)
        if f:
            issues.append(f)
    # ---- drawing (one common scale)
    k = min(250 / da, 280 / slen, 280 / (llen + 2 * lhole))
    gx, gy = 190.0, 210.0
    hz = math.pi / (2 * z)
    poly = []
    for i in range(z):
        th = 2 * math.pi * i / z
        for ang, rad in ((th - 1.2 * hz, df / 2), (th - 0.55 * hz, da / 2),
                         (th + 0.55 * hz, da / 2), (th + 1.2 * hz, df / 2)):
            poly.append(f'{_f(gx + rad * k * math.cos(ang), 3)},{_f(gy + rad * k * math.sin(ang), 3)}')
    ln = 'stroke="#111111" stroke-width="1.2" fill="none"'
    thin = 'stroke="#555555" stroke-width="0.7" fill="none"'
    txt = 'font-family="monospace" font-size="11" fill="#111111"'
    rp = d / 2 * k
    sx, sy = 420.0, 80.0
    sw, sh = slen * k, shaft * k
    lx, ly = 420.0, 300.0
    ro = lhole * k
    h1, h2 = lx + ro, lx + ro + llen * k
    parts = [
        f'<rect width="760" height="420" fill="#ffffff"/>',
        f'<polygon points="{" ".join(poly)}" {ln}/>',
        f'<circle cx="{_f(gx)}" cy="{_f(gy)}" r="{_f(rp, 3)}" {thin} stroke-dasharray="8 3 2 3"/>',
        f'<circle cx="{_f(gx)}" cy="{_f(gy)}" r="{_f(bore / 2 * k, 3)}" {ln}/>',
        f'<line x1="{_f(gx - rp)}" y1="{_f(gy - da / 2 * k - 18)}" x2="{_f(gx + rp)}" '
        f'y2="{_f(gy - da / 2 * k - 18)}" {thin}/>',
        f'<line x1="{_f(gx - rp)}" y1="{_f(gy)}" x2="{_f(gx - rp)}" y2="{_f(gy - da / 2 * k - 24)}" {thin}/>',
        f'<line x1="{_f(gx + rp)}" y1="{_f(gy)}" x2="{_f(gx + rp)}" y2="{_f(gy - da / 2 * k - 24)}" {thin}/>',
        f'<text x="{_f(gx)}" y="{_f(gy - da / 2 * k - 24)}" text-anchor="middle" {txt}>'
        f'PCD &#216;{d:.2f} = m&#183;z = {_f(m, 3)}&#215;{z}</text>',
        f'<text x="{_f(gx)}" y="{_f(gy + da / 2 * k + 22)}" text-anchor="middle" {txt}>'
        f'&#216;a {da:.2f}  &#216;f {df:.2f}  &#216;b {db:.2f}  bore &#216;{bore:.3f}</text>',
        f'<rect x="{_f(sx)}" y="{_f(sy)}" width="{_f(sw, 3)}" height="{_f(sh, 3)}" {ln}/>',
        f'<line x1="{_f(sx - 8)}" y1="{_f(sy + sh / 2, 3)}" x2="{_f(sx + sw + 8, 3)}" y2="{_f(sy + sh / 2, 3)}" '
        f'{thin} stroke-dasharray="10 3 2 3"/>',
        f'<text x="{_f(sx)}" y="{_f(sy - 10)}" {txt}>shaft &#216;{shaft:.3f} &#215; {slen:.2f}</text>',
        f'<line x1="{_f(sx)}" y1="{_f(sy + sh + 14, 3)}" x2="{_f(sx + sw, 3)}" y2="{_f(sy + sh + 14, 3)}" {thin}/>',
        f'<text x="{_f(sx + sw / 2, 3)}" y="{_f(sy + sh + 28, 3)}" text-anchor="middle" {txt}>{slen:.2f}</text>',
        f'<path d="M{_f(h1, 3)} {_f(ly - ro, 3)} L{_f(h2, 3)} {_f(ly - ro, 3)} A{_f(ro, 3)} {_f(ro, 3)} 0 0 1 '
        f'{_f(h2, 3)} {_f(ly + ro, 3)} L{_f(h1, 3)} {_f(ly + ro, 3)} A{_f(ro, 3)} {_f(ro, 3)} 0 0 1 '
        f'{_f(h1, 3)} {_f(ly - ro, 3)} Z" {ln}/>',
        f'<circle cx="{_f(h1, 3)}" cy="{_f(ly)}" r="{_f(ro / 2, 3)}" {ln}/>',
        f'<circle cx="{_f(h2, 3)}" cy="{_f(ly)}" r="{_f(ro / 2, 3)}" {ln}/>',
        f'<line x1="{_f(h1, 3)}" y1="{_f(ly + ro + 14, 3)}" x2="{_f(h2, 3)}" y2="{_f(ly + ro + 14, 3)}" {thin}/>',
        f'<text x="{_f((h1 + h2) / 2, 3)}" y="{_f(ly + ro + 28, 3)}" text-anchor="middle" {txt}>'
        f'{llen:.2f} c-c, holes &#216;{lhole:.3f}</text>',
        f'<text x="20" y="408" {txt}>scale {k:.4f} px/mm  |  fit: '
        f'{"OK" if not issues else _esc("; ".join(i["code"] for i in issues))}</text>',
    ]
    svg = _finish(_svg_open(760, 420) + ''.join(parts) + '</svg>')
    result = {'gear': {'module': m, 'teeth': z, 'pressure_angle_deg': pa, 'pitch_diameter': d,
                       'tip_diameter': da, 'root_diameter': df, 'base_diameter': db,
                       'circular_pitch': math.pi * m, 'bore': bore},
              'shaft': {'diameter': shaft, 'length': slen},
              'link': {'center_distance': llen, 'hole': lhole},
              'clearances': {'gear_bore': bore - shaft, 'link_hole': lhole - shaft,
                             'allowed': [cmin, cmax]},
              'issues': issues, 'connection_ok': not issues, 'scale_px_per_mm': k, 'svg': svg}
    return _pack('machine_drawing', result,
                 ['standard full-depth spur gear proportions (addendum m, dedendum 1.25 m)',
                  'teeth are drawn as straight-sided trapezoids, not true involute flanks: a schematic, '
                  'not a manufacturing drawing',
                  'fit check is a simple diametral clearance window, not an ISO 286 tolerance class'],
                 ['module 0.1..50 mm, teeth 6..300, pressure angle 14.5..30 deg',
                  'single orthographic view per part on one common scale'])


# --------------------------------------------------------------------------- 06.06 watercolor

def _wc_factor(s):
    """E[sqrt(1 + 4 s^2 Z^2)], Z ~ N(0,1): expected length growth per midpoint split."""
    if s == 0:
        return 1.0
    n, a, b = 2000, -8.0, 8.0
    h = (b - a) / n
    tot = 0.0
    for i in range(n + 1):
        zz = a + i * h
        w = 1 if i in (0, n) else (4 if i % 2 else 2)
        tot += w * math.sqrt(1 + 4 * s * s * zz * zz) * math.exp(-zz * zz / 2)
    return tot * h / 3 / math.sqrt(2 * math.pi)


def _perimeter(poly):
    return sum(math.dist(poly[i], poly[(i + 1) % len(poly)]) for i in range(len(poly)))


def watercolor(*, color='#3a7bd5', spread=0.12, layers=12, depth=4, sides=10, radius=70.0,
               opacity=0.06, edge_darkening=0.4, seed=11, size=240, **extra):
    """Watercolour-like wash: many translucent, independently deformed copies of a polygon.

    Each layer starts from a regular polygon and applies `depth` rounds of recursive
    midpoint displacement: every edge a->b gets a new midpoint pushed along the edge
    normal by N(0, 1) * spread * |ab|. Edge darkening: each layer is stroked with a
    darker tone at low opacity, which piles up where edges overlap.
    edge_roughness (per layer) = perimeter / base perimeter - 1. Its expectation is
    exactly E[sqrt(1 + 4 spread^2 Z^2)]^depth - 1; expected_range is +/-40 % of that.
    """
    _no_extra(extra)
    color = _hex(color, 'color')
    spread = _num(spread, 0, 0.5, 'spread')
    layers = _int(layers, 1, 40, 'layers')
    depth = _int(depth, 1, 6, 'depth')
    sides = _int(sides, 3, 32, 'sides')
    radius = _num(radius, 1, 1000, 'radius')
    opacity = _num(opacity, 0.005, 1, 'opacity')
    edge_darkening = _num(edge_darkening, 0, 1, 'edge_darkening')
    seed = _int(seed, 0, 2**31 - 1, 'seed')
    size = _int(size, 32, 2048, 'size')
    if layers * sides * 2 ** depth > 60_000:
        raise ValueError('layers * sides * 2**depth must be <= 60000')
    rng = random.Random(seed)
    c = size / 2
    base = [[c + radius * math.cos(2 * math.pi * i / sides), c + radius * math.sin(2 * math.pi * i / sides)]
            for i in range(sides)]
    base_p = _perimeter(base)
    edge = _mix_linear(color, '#000000', 0.35)
    s_op = min(1.0, opacity * (1 + 6 * edge_darkening))
    rough, polys = [], []
    for _ in range(layers):
        poly = [p[:] for p in base]
        for _ in range(depth):
            new = []
            for i, a in enumerate(poly):
                b = poly[(i + 1) % len(poly)]
                dx, dy = b[0] - a[0], b[1] - a[1]
                length = math.hypot(dx, dy)
                disp = rng.gauss(0.0, 1.0) * spread * length
                nx, ny = (dy / length, -dx / length) if length > 0 else (0.0, 0.0)
                new.append(a)
                new.append([(a[0] + b[0]) / 2 + nx * disp, (a[1] + b[1]) / 2 + ny * disp])
            poly = new
        rough.append(_perimeter(poly) / base_p - 1)
        pts = ' '.join(f'{_f(x)},{_f(y)}' for x, y in poly)
        polys.append(f'<polygon points="{pts}" fill="{color}" fill-opacity="{_f(opacity, 4)}" '
                     f'stroke="{edge}" stroke-opacity="{_f(s_op, 4)}" stroke-width="1.2" '
                     f'stroke-linejoin="round"/>')
    svg = _finish(_svg_open(size, size) + f'<rect width="{size}" height="{size}" fill="#fbf8f2"/>'
                  + '<g id="wash">' + ''.join(polys) + '</g></svg>')
    expected = _wc_factor(spread) ** depth - 1
    lo, hi = (0.6 * expected, 1.4 * expected) if expected > 0 else (0.0, 1e-12)
    mean = sum(rough) / len(rough)
    result = {'color': color, 'edge_color': edge, 'spread': spread, 'layers': layers, 'depth': depth,
              'vertices_per_layer': sides * 2 ** depth, 'seed': seed,
              'edge_roughness': mean, 'edge_roughness_min': min(rough), 'edge_roughness_max': max(rough),
              'expected_roughness': expected, 'expected_range': [lo, hi],
              'within_expected': lo <= mean <= hi, 'svg': svg}
    return _pack('watercolor', result,
                 ['layered translucent polygons approximate pigment pooling; there is no fluid or paper simulation',
                  'each layer is deformed independently from the same base shape (Gaussian midpoint displacement)',
                  'edge darkening is a darker low-opacity stroke, not real pigment migration'],
                 ['spread <= 0.5, depth <= 6, layers <= 40, sides <= 32, layers * sides * 2**depth <= 60000',
                  'coordinates rounded to 0.01 in the SVG; the metric uses unrounded points'])


# --------------------------------------------------------------------------- 06.07 mono_style

_EX_MONO_SCENE = (_svg_open(160, 100) + '<rect width="160" height="100" fill="#ffffff"/>'
                  '<circle cx="50" cy="50" r="30" fill="#b23a48" stroke="#1b1b1b" stroke-width="2"/>'
                  '<rect x="95" y="25" width="45" height="50" style="fill:#2e4057;stroke:#555555"/></svg>')
_ATTR_RE = re.compile(r'(\b(?:stop-color|flood-color|lighting-color|fill|stroke|color)\s*=\s*)(["\'])(.*?)\2')
_STYLE_RE = re.compile(r'(\bstyle\s*=\s*)(["\'])(.*?)\2', re.S)


def _gray_of(h):
    g = _enc(_luminance(h))
    return _to_hex([g, g, g])


def _gray_token(v):
    hx, _ = _color_token(v)
    return _gray_of(hx) if hx else v


def mono_style(*, colors=None, line_colors=None, background='#ffffff', min_contrast=4.5,
               min_weight=1.0, max_weight=4.0, svg=None, **extra):
    """Black-and-white conversion by WCAG relative luminance, with line-weight mapping.

    Y = 0.2126 R + 0.7152 G + 0.0722 B on linearised sRGB; the grey is Y re-encoded to
    sRGB, so a colour and its grey have the same luminance. Line weight =
    min_weight + (max_weight - min_weight) * (1 - Y): darker lines draw heavier.
    Each line colour's grey must reach WCAG contrast (L1+0.05)/(L2+0.05) >= min_contrast
    against `background`. svg (optional) is converted colour-by-colour to greys.
    """
    _no_extra(extra)
    colors = {'coat': '#b23a48', 'trousers': '#2e4057', 'skin': '#f2c9a0',
              'red': '#ff0000', 'green': '#00ff00', 'blue': '#0000ff'} if colors is None else colors
    if isinstance(colors, dict):
        _dict(colors, 'colors', 64)
        if not colors:
            raise ValueError('colors must not be empty')
        items = [(_ident(k, 'colour role'), _hex(v, f'colors.{k}')) for k, v in colors.items()]
    else:
        items = [(f'c{i + 1}', _hex(v, f'colors[{i}]')) for i, v in enumerate(_list(colors, 'colors', 1, 64))]
    line_colors = ['#1b1b1b', '#555555'] if line_colors is None else line_colors
    lines = [_hex(v, f'line_colors[{i}]') for i, v in enumerate(_list(line_colors, 'line_colors', 0, 64))]
    background = _hex(background, 'background')
    min_contrast = _num(min_contrast, 1, 21, 'min_contrast')
    min_weight = _num(min_weight, 0.1, 50, 'min_weight')
    max_weight = _num(max_weight, 0.1, 50, 'max_weight')
    if min_weight > max_weight:
        raise ValueError('min_weight must be <= max_weight')
    svg = _EX_MONO_SCENE if svg is None else svg
    root = _parse_svg_input(svg, 'svg')
    issues = _svg_issues(root)
    if issues:
        raise ValueError('svg contains unsafe markup: ' + '; '.join(issues))

    def weight(y):
        return min_weight + (max_weight - min_weight) * (1 - y)
    palette = []
    for role, hx in items:
        y = _luminance(hx)
        palette.append({'role': role, 'colour': hx, 'luminance': y, 'gray': _gray_of(hx),
                        'gray_luminance': _luminance(_gray_of(hx)), 'line_weight': weight(y)})
    checks = []
    for hx in lines:
        g = _gray_of(hx)
        cr = _contrast(g, background)
        checks.append({'colour': hx, 'gray': g, 'contrast': cr, 'line_weight': weight(_luminance(hx)),
                       'passed': cr >= min_contrast})
    out_svg = _ATTR_RE.sub(lambda m: m.group(1) + m.group(2) + _gray_token(m.group(3)) + m.group(2), svg)
    out_svg = _STYLE_RE.sub(lambda m: m.group(1) + m.group(2) + ';'.join(
        (d.split(':', 1)[0] + ':' + _gray_token(d.split(':', 1)[1]))
        if ':' in d and d.split(':', 1)[0].strip().lower() in _COLOR_ATTRS else d
        for d in m.group(3).split(';')) + m.group(2), out_svg)
    out_svg = _finish(out_svg)
    left = [c for c, _ in _scene_colours(ET.fromstring(out_svg))[0].items()
            if len({c[1:3], c[3:5], c[5:7]}) != 1]
    sw = 40
    swatches = _finish(_svg_open(sw * len(palette), sw + 16) + ''.join(
        f'<rect x="{i * sw}" y="0" width="{sw}" height="{sw}" fill="{p["gray"]}"/>'
        f'<text x="{i * sw + 2}" y="{sw + 12}" font-size="9" font-family="monospace">{_esc(p["role"][:7])}</text>'
        for i, p in enumerate(palette)) + '</svg>')
    result = {'background': background, 'background_luminance': _luminance(background),
              'palette': palette, 'line_checks': checks,
              'lines_ok': all(c['passed'] for c in checks), 'min_contrast': min_contrast,
              'svg': out_svg, 'non_gray_left': left, 'swatches_svg': swatches}
    return _pack('mono_style', result,
                 ['WCAG 2.x relative luminance on sRGB with the 0.04045 linearisation threshold',
                  'greys are luminance-preserving to 8-bit precision; hue differences of equal luminance collapse',
                  'only fill/stroke-like attributes and inline style are converted; CSS blocks and images are untouched'],
                 ['<= 64 colours and 64 line colours', 'svg <= 300000 chars; unsafe markup is rejected'])


# --------------------------------------------------------------------------- 06.08 reference_character

_SENSITIVE = {
    'ethnicity', 'ethnic', 'race', 'racial', 'religion', 'religious', 'faith', 'belief', 'beliefs',
    'health', 'medical', 'diagnosis', 'disability', 'illness', 'pregnancy',
    'sexual_orientation', 'sexuality', 'gender_identity', 'political', 'politics',
    'political_views', 'union_membership', 'biometric', 'biometrics', 'genetic', 'genetics',
    'dna', 'criminal_record', 'immigration_status', 'caste', 'nationality',
}
_EX_SHEET = {'id': 'courier_rose',
             'attributes': {'outfit': {'jacket': '#b23a48', 'trousers': '#2e4057', 'scarf': '#e9c46a'},
                            'accessories': ['satchel', 'round_glasses'],
                            'silhouette': 'tall_slim'}}
_EX_SCENE = {'shot': 'sc01_sh03',
             'characters': [{'id': 'courier_rose',
                             'outfit': {'jacket': '#b23a48', 'trousers': '#2e4057', 'scarf': '#e9c46a'},
                             'accessories': ['satchel', 'round_glasses'], 'silhouette': 'tall_slim'}]}


def _norm_key(k):
    return re.sub(r'[\s\-]+', '_', unicodedata.normalize('NFKC', str(k)).casefold().strip())


def _reject_sensitive(obj, path, depth=0):
    if depth > 6:
        raise ValueError(f'{path}: nesting too deep')
    if isinstance(obj, dict):
        for k, v in obj.items():
            nk = _norm_key(k)
            if nk in _SENSITIVE or any(part in _SENSITIVE for part in nk.split('_')):
                raise ValueError(f'sensitive field not allowed in character data: {path}.{k}')
            _reject_sensitive(v, f'{path}.{k}', depth + 1)
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            _reject_sensitive(v, f'{path}[{i}]', depth + 1)


def _char_attrs(d, name):
    _dict(d, name, 8)
    outfit = {_ident(k, f'{name}.outfit key'): _hex(v, f'{name}.outfit.{k}')
              for k, v in _dict(d.get('outfit', {}), f'{name}.outfit', 24).items()}
    acc = sorted({_ident(a, f'{name}.accessories item')
                  for a in _list(d.get('accessories', []), f'{name}.accessories', 0, 24)})
    sil = d.get('silhouette')
    sil = None if sil is None else _ident(sil, f'{name}.silhouette')
    return {'outfit': outfit, 'accessories': acc, 'silhouette': sil}


def reference_character(*, sheet=None, scene=None, tolerance=3.0, **extra):
    """Character reference sheet (non-sensitive visual attributes) + scene consistency check.

    sheet: {id, attributes: {outfit: {part: hex}, accessories: [name], silhouette: name}}.
    Any key naming a sensitive trait (ethnicity, religion, health, sexual orientation,
    political views, biometrics ...) anywhere in sheet or scene raises ValueError: it is
    never stored or echoed. scene: {shot, characters: [{id, outfit, accessories,
    silhouette}]}. For the sheet's character every outfit part whose colour moved more
    than `tolerance` dE76, every missing/added accessory and a silhouette change is
    reported as an unplanned change.
    """
    _no_extra(extra)
    sheet = _EX_SHEET if sheet is None else sheet
    scene = _EX_SCENE if scene is None else scene
    _reject_sensitive(sheet, 'sheet')
    _reject_sensitive(scene, 'scene')
    tolerance = _num(tolerance, 0, 50, 'tolerance')
    _dict(sheet, 'sheet', 3)
    _keys(sheet, ('id', 'name', 'attributes'), 'sheet', ('id', 'attributes'))
    cid = _ident(sheet['id'], 'sheet.id')
    attrs_in = _dict(sheet['attributes'], 'sheet.attributes', 3)
    _keys(attrs_in, ('outfit', 'accessories', 'silhouette'), 'sheet.attributes', ('outfit',))
    ref = _char_attrs(attrs_in, 'sheet.attributes')
    if not ref['outfit']:
        raise ValueError('sheet.attributes.outfit must name at least one part')
    _dict(scene, 'scene', 2)
    _keys(scene, ('shot', 'characters'), 'scene', ('characters',))
    shot = _str(scene.get('shot', 'shot'), 'scene.shot', 64)
    reports, consistent = [], True
    for i, ch in enumerate(_list(scene['characters'], 'scene.characters', 0, 32)):
        _dict(ch, f'scene.characters[{i}]', 4)
        _keys(ch, ('id', 'outfit', 'accessories', 'silhouette'), f'scene.characters[{i}]', ('id',))
        sid = _ident(ch['id'], f'scene.characters[{i}].id')
        if sid != cid:
            reports.append({'id': sid, 'status': 'not_on_sheet', 'changes': []})
            continue
        got = _char_attrs({k: v for k, v in ch.items() if k != 'id'}, f'scene.characters[{i}]')
        changes = []
        for part, want in sorted(ref['outfit'].items()):
            have = got['outfit'].get(part)
            if have is None:
                changes.append({'field': f'outfit.{part}', 'kind': 'missing', 'expected': want, 'found': None})
            else:
                de = _de76(want, have)
                if de > tolerance:
                    changes.append({'field': f'outfit.{part}', 'kind': 'colour_changed', 'expected': want,
                                    'found': have, 'delta_e': round(de, 4)})
        for part in sorted(set(got['outfit']) - set(ref['outfit'])):
            changes.append({'field': f'outfit.{part}', 'kind': 'added', 'expected': None,
                            'found': got['outfit'][part]})
        for a in sorted(set(ref['accessories']) - set(got['accessories'])):
            changes.append({'field': f'accessories.{a}', 'kind': 'missing', 'expected': a, 'found': None})
        for a in sorted(set(got['accessories']) - set(ref['accessories'])):
            changes.append({'field': f'accessories.{a}', 'kind': 'added', 'expected': None, 'found': a})
        if ref['silhouette'] and got['silhouette'] and got['silhouette'] != ref['silhouette']:
            changes.append({'field': 'silhouette', 'kind': 'changed', 'expected': ref['silhouette'],
                            'found': got['silhouette']})
        consistent = consistent and not changes
        reports.append({'id': sid, 'status': 'consistent' if not changes else 'changed', 'changes': changes})
    parts = sorted(ref['outfit'].items())
    sw = 70
    sheet_svg = _finish(
        _svg_open(max(220, sw * len(parts) + 20), 150) + '<rect width="100%" height="100%" fill="#ffffff"/>'
        f'<text x="10" y="18" font-family="monospace" font-size="12">{_esc(cid)}  '
        f'silhouette: {_esc(ref["silhouette"] or "-")}</text>'
        + ''.join(f'<rect x="{10 + i * sw}" y="30" width="{sw - 10}" height="50" fill="{c}" stroke="#111111"/>'
                  f'<text x="{10 + i * sw}" y="94" font-family="monospace" font-size="10">{_esc(p[:10])}</text>'
                  f'<text x="{10 + i * sw}" y="106" font-family="monospace" font-size="9">{c}</text>'
                  for i, (p, c) in enumerate(parts))
        + f'<text x="10" y="135" font-family="monospace" font-size="10">accessories: '
          f'{_esc(", ".join(ref["accessories"]) or "-")}</text></svg>')
    stored = {'id': cid, 'attributes': ref}
    result = {'sheet': stored, 'sheet_fingerprint': _sha(stored), 'shot': shot,
              'tolerance_delta_e76': tolerance, 'characters': reports, 'consistent': consistent,
              'reference_sheet_svg': sheet_svg}
    return _pack('reference_character', result,
                 ['the sheet stores only visual, non-sensitive design attributes (outfit colours, accessories, '
                  'silhouette label); it does not identify real people',
                  'sensitive-trait detection is a key-name blocklist, not semantic understanding of free text',
                  'scene attributes are declared data from the shot spec, not detected from pixels'],
                 ['<= 24 outfit parts and 24 accessories, <= 32 characters per scene, nesting depth <= 6',
                  'colour change threshold in dE76 (default 3)'])


# --------------------------------------------------------------------------- 06.09 style_guide_check

_ZONES = [['top_left', 'top', 'top_right'], ['left', 'center', 'right'],
          ['bottom_left', 'bottom', 'bottom_right']]
_ZONE_SET = {z for row in _ZONES for z in row}
_EX_GUIDE = {'colours': ['#0f172a', '#f8fafc', '#e11d48'], 'title_font': 'Inter',
             'title_zone': 'bottom_left', 'text_order': ['title', 'subtitle', 'credit']}
_EX_SHOTS = [
    {'id': 'sh01', 'colours': ['#0f172a', '#f8fafc'], 'title': {'font': 'Inter', 'zone': 'bottom_left'},
     'text_order': ['title', 'subtitle']},
    {'id': 'sh02', 'colours': ['#0f172a', '#e11d48'], 'title': {'font': 'Inter', 'position': [0.1, 0.85]},
     'text_order': ['title', 'credit']},
]


def _zone(title, name):
    if 'zone' in title:
        return _choice(title['zone'], _ZONE_SET, f'{name}.zone')
    if 'position' in title:
        x, y = [_num(v, 0, 1, f'{name}.position') for v in _list(title['position'], f'{name}.position', 2, 2)]
        return _ZONES[min(2, int(y * 3))][min(2, int(x * 3))]
    return None


def style_guide_check(*, guide=None, shots=None, tolerance=3.0, **extra):
    """Check shot specs against a video style guide; report per-shot violations.

    guide: {colours: [hex], title_font: family name, title_zone: one of a 3x3 grid
    (top_left .. bottom_right), text_order: [item, ...]}. shot: {id, colours: [hex],
    title: {font, zone | position [x, y] normalised 0..1}, text_order: [item, ...]}.
    Violations: one 'foreign_colour' per colour farther than `tolerance` dE76 from every
    guide colour, 'title_zone', 'title_font' (case-insensitive compare), 'text_order'
    (known items appearing out of guide order). Unknown text items are ignored.
    """
    _no_extra(extra)
    guide = _EX_GUIDE if guide is None else guide
    shots = _EX_SHOTS if shots is None else shots
    tolerance = _num(tolerance, 0, 50, 'tolerance')
    _dict(guide, 'guide', 4)
    _keys(guide, ('colours', 'title_font', 'title_zone', 'text_order'), 'guide',
          ('colours', 'title_font', 'title_zone'))
    gcol = [_hex(c, f'guide.colours[{i}]') for i, c in enumerate(_list(guide['colours'], 'guide.colours', 1, 32))]
    gfont = _str(guide['title_font'], 'guide.title_font', 80).strip()
    gzone = _choice(guide['title_zone'], _ZONE_SET, 'guide.title_zone')
    gorder = [_ident(t, 'guide.text_order item')
              for t in _list(guide.get('text_order', []), 'guide.text_order', 0, 16)]
    if len(set(gorder)) != len(gorder):
        raise ValueError('guide.text_order items must be unique')
    rank = {t: i for i, t in enumerate(gorder)}
    out, total = [], 0
    seen = set()
    for i, sh in enumerate(_list(shots, 'shots', 1, 200)):
        _dict(sh, f'shots[{i}]', 4)
        _keys(sh, ('id', 'colours', 'title', 'text_order'), f'shots[{i}]', ('id',))
        sid = _ident(sh['id'], f'shots[{i}].id')
        if sid in seen:
            raise ValueError(f'duplicate shot id {sid}')
        seen.add(sid)
        v = []
        for j, c in enumerate(_list(sh.get('colours', []), f'shots[{i}].colours', 0, 32)):
            hx = _hex(c, f'shots[{i}].colours[{j}]')
            de = min(_de76(hx, g) for g in gcol)
            if de > tolerance:
                v.append({'code': 'foreign_colour', 'detail': hx, 'delta_e': round(de, 4)})
        if 'title' in sh:
            t = _dict(sh['title'], f'shots[{i}].title', 3)
            _keys(t, ('font', 'zone', 'position'), f'shots[{i}].title')
            if 'zone' in t and 'position' in t:
                raise ValueError(f'shots[{i}].title: give zone or position, not both')
            z = _zone(t, f'shots[{i}].title')
            if z is not None and z != gzone:
                v.append({'code': 'title_zone', 'detail': f'{z} (guide: {gzone})'})
            if 'font' in t:
                f = _str(t['font'], f'shots[{i}].title.font', 80).strip()
                if f.casefold() != gfont.casefold():
                    v.append({'code': 'title_font', 'detail': f'{f} (guide: {gfont})'})
        order = [_ident(x, f'shots[{i}].text_order item')
                 for x in _list(sh.get('text_order', []), f'shots[{i}].text_order', 0, 16)]
        known = [rank[x] for x in order if x in rank]
        if any(b < a for a, b in zip(known, known[1:])):
            v.append({'code': 'text_order', 'detail': ' > '.join(order)})
        total += len(v)
        out.append({'id': sid, 'violations': v, 'count': len(v), 'passed': not v})
    result = {'guide': {'colours': gcol, 'title_font': gfont, 'title_zone': gzone, 'text_order': gorder},
              'guide_fingerprint': _sha({'c': sorted(gcol), 'f': gfont.casefold(), 'z': gzone, 'o': gorder}),
              'shots': out, 'total_violations': total, 'all_passed': total == 0}
    return _pack('style_guide_check', result,
                 ['shot specs are declared metadata (colours, font, title placement), not measured from frames',
                  'title placement is judged on a 3x3 grid of the frame; position uses the title anchor point',
                  'font comparison is by family name only (no weight, size or fallback checks)'],
                 ['<= 200 shots, <= 32 colours per shot and guide, <= 16 text items',
                  'colour tolerance in dE76 (default 3)'])


# --------------------------------------------------------------------------- 06.10 style_descriptor

DEFAULT_BLOCKLIST = (
    'studio ghibli', 'ghibli', 'miyazaki', 'pixar', 'disney', 'dreamworks', 'marvel', 'dc comics',
    'pokemon', 'nintendo', 'looney tunes', 'simpsons', 'studio trigger', 'illumination entertainment',
    'جيبلي', 'ديزني', 'بيكسار', 'مارفل', 'بوكيمون',
)
_LINE_WEIGHTS = {'hairline', 'thin', 'medium', 'bold', 'heavy', 'varied'}
_MOODS = {'warm', 'cool', 'muted', 'vivid', 'pastel', 'monochrome', 'earthy', 'neon'}
_SHADING = {'flat', 'cel', 'soft', 'hatching', 'clay', 'watercolor', 'none'}
_TEXTURE = {'none', 'paper', 'grain', 'canvas', 'brush', 'halftone'}
_SOURCES = {'original', 'licensed', 'commissioned', 'public_domain', 'own_reference'}
_IMITATION = re.compile(r'in the style of|style of|\bà la\b|\blike\b.*\b(film|movie|studio)|بأسلوب|على طريقة|ستايل',
                        re.I)
_EX_DESCRIPTOR = {'line_weight': 'medium', 'palette_mood': 'warm', 'shading': 'soft', 'texture': 'paper',
                  'notes': 'rounded shapes, gentle evening light',
                  'provenance': {'source': 'original', 'author': 'red-rose example'}}


def _norm_text(s):
    s = unicodedata.normalize('NFKD', unicodedata.normalize('NFKC', s).casefold())
    s = ''.join(ch for ch in s if not unicodedata.combining(ch))
    return ' ' + ' '.join(re.findall(r'\w+', s)) + ' '


def style_descriptor(*, descriptor=None, blocklist=None, extra_blocklist=None, **extra):
    """Generic, neutral style descriptor with a protected-name screen and required provenance.

    descriptor: {line_weight, palette_mood, shading, texture, notes?, provenance:
    {source in original|licensed|commissioned|public_domain|own_reference, author, license?, note?}}.
    Missing provenance raises ValueError. Text fields (notes) are normalised (NFKC,
    casefold, accents stripped, punctuation -> spaces) and any whole-word match of a
    blocklisted studio / artist / franchise name rejects the descriptor
    (status 'rejected'). An imitation phrase without a blocked name is only a warning.
    blocklist replaces DEFAULT_BLOCKLIST; extra_blocklist extends it.
    """
    _no_extra(extra)
    d = _EX_DESCRIPTOR if descriptor is None else descriptor
    _dict(d, 'descriptor', 6)
    _keys(d, ('line_weight', 'palette_mood', 'shading', 'texture', 'notes', 'provenance'), 'descriptor')
    if 'provenance' not in d:
        raise ValueError('descriptor.provenance is required')
    names = list(DEFAULT_BLOCKLIST) if blocklist is None else [
        _str(b, 'blocklist item', 80) for b in _list(blocklist, 'blocklist', 0, 500)]
    if extra_blocklist is not None:
        names += [_str(b, 'extra_blocklist item', 80) for b in _list(extra_blocklist, 'extra_blocklist', 0, 500)]
    lw = d.get('line_weight', 'medium')
    if isinstance(lw, str):
        lw = _choice(lw, _LINE_WEIGHTS, 'line_weight')
    else:
        lw = _num(lw, 0.1, 50, 'line_weight')
    norm = {'line_weight': lw,
            'palette_mood': _choice(d.get('palette_mood', 'muted'), _MOODS, 'palette_mood'),
            'shading': _choice(d.get('shading', 'flat'), _SHADING, 'shading'),
            'texture': _choice(d.get('texture', 'none'), _TEXTURE, 'texture'),
            'notes': _str(d.get('notes', ''), 'notes', 500, allow_empty=True).strip()}
    prov = _dict(d['provenance'], 'provenance', 4)
    _keys(prov, ('source', 'author', 'license', 'note'), 'provenance', ('source', 'author'))
    prov = {'source': _choice(prov['source'], _SOURCES, 'provenance.source'),
            'author': _str(prov['author'], 'provenance.author', 120).strip(),
            **({'license': _str(prov['license'], 'provenance.license', 120).strip()} if 'license' in prov else {}),
            **({'note': _str(prov['note'], 'provenance.note', 300).strip()} if 'note' in prov else {})}
    if prov['source'] == 'licensed' and 'license' not in prov:
        raise ValueError('provenance.license is required when source is licensed')
    text = _norm_text(norm['notes'])
    matches = sorted({n for n in names if _norm_text(n).strip() and _norm_text(n) in text})
    reasons = [f'names protected studio/artist/franchise: {m}' for m in matches]
    warnings = []
    if _IMITATION.search(norm['notes']) and not matches:
        warnings.append('imitation phrasing found; describe neutral attributes instead of naming a source')
    lw_txt = f'{_f(lw)} px' if isinstance(lw, float) else lw
    prompt = (f'{lw_txt} line weight, {norm["palette_mood"]} palette, {norm["shading"]} shading, '
              f'{norm["texture"]} texture' + (f'; {norm["notes"]}' if norm['notes'] and not matches else ''))
    status = 'rejected' if matches else 'accepted'
    result = {'status': status, 'reasons': reasons, 'warnings': warnings, 'blocked_matches': matches,
              'descriptor': norm if not matches else None, 'prompt': prompt if not matches else None,
              'provenance': prov,
              'descriptor_id': _sha({'d': norm, 'p': prov}) if not matches else None,
              'blocklist_size': len(names)}
    return _pack('style_descriptor', result,
                 ['descriptors are built only from neutral, generic attributes (line, palette mood, shading, texture)',
                  'blocklist matching is whole-word after normalisation; misspellings, transliterations not in '
                  'the list and attached Arabic prefixes (e.g. و/ب) are not caught',
                  'this screens wording only; it is not a legal clearance of the resulting artwork'],
                 ['notes <= 500 chars, blocklist <= 1000 names', 'provenance is required on every descriptor'])


# --------------------------------------------------------------------------- dispatcher

OPS = {
    'palette_lock': palette_lock, 'rough_lines': rough_lines, 'clay_look': clay_look,
    'flat_cartoon': flat_cartoon, 'machine_drawing': machine_drawing, 'watercolor': watercolor,
    'mono_style': mono_style, 'reference_character': reference_character,
    'style_guide_check': style_guide_check, 'style_descriptor': style_descriptor,
}


def run(op, params=None):
    """Validate and dispatch: run('rough_lines', {'seed': 3}) -> {'op','result','assumptions','limits'}."""
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
