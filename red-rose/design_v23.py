"""Red Rose V23: small, bounded, deterministic design/layout helpers (topics 13.01-13.10).

Pure standard-library Python. No file I/O, no subprocess, no network, no printing.
Every op validates its inputs strictly (ValueError on bools-as-numbers,
non-finite values, unknown parameter names, unknown record keys and
out-of-range values) and caps its work (elements, samples, grid cells) so it
cannot run away. SVG output is returned as a string built only from numbers
and escaped text: no scripts, no event handlers, no external references.

These are previz/checklist-grade models, not a replacement for a designer's
eye: each op returns the assumptions it makes and the limits it enforces next
to its result. Every op works with an empty params dict (a tiny built-in
example) so `run(op, {})` always demonstrates the method.
"""
from __future__ import annotations

import colorsys
import hashlib
import json
import math
import random
import unicodedata

MAX_PARAMS = 24
MAX_ELEMENTS = 64
MAX_SHOTS = 200
MAX_GRID_CELLS = 40_000

TOPICS = {
    '13.01': 'frame_composition',
    '13.02': 'landscape_layers',
    '13.03': 'three_point_light',
    '13.04': 'palette_harmony',
    '13.05': 'arabic_text_layout',
    '13.06': 'logo_marks',
    '13.07': 'poster_hierarchy',
    '13.08': 'interior_layout',
    '13.09': 'horizon_fov',
    '13.10': 'continuity_diff',
}

TOPIC_NAMES_AR = {
    '13.01': 'تخطيط إطار سينمائي',
    '13.02': 'توليد خلفية طبيعية',
    '13.03': 'توجيه إضاءة لشخصية',
    '13.04': 'توليف لوحات ألوان',
    '13.05': 'تصميم خط عربي متحرك',
    '13.06': 'تصميم شعارات أصلية',
    '13.07': 'تخطيط الملصقات التجارية',
    '13.08': 'توليد ديكور داخلي',
    '13.09': 'تصوير منظور بعيد',
    '13.10': 'استمرارية تفاصيل المشهد',
}

SVG_NS = 'http://www.w3.org/2000/svg'


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


def _bool(value, name):
    if not isinstance(value, bool):
        raise ValueError(f'{name} must be true or false')
    return value


def _choice(value, options, name):
    if not isinstance(value, str) or value not in options:
        raise ValueError(f'{name} must be one of {sorted(options)}')
    return value


def _str(value, name, max_len=200, *, allow_empty=False):
    if not isinstance(value, str) or len(value) > max_len or (not allow_empty and not value.strip()):
        raise ValueError(f'{name} must be a {"" if allow_empty else "non-empty "}string of at most {max_len} chars')
    return value


def _list(value, name, low, high):
    if not isinstance(value, (list, tuple)) or not low <= len(value) <= high:
        raise ValueError(f'{name} must be a list of {low} to {high} items')
    return list(value)


def _vec(value, size, name, low=-1e6, high=1e6):
    if not isinstance(value, (list, tuple)) or len(value) != size:
        raise ValueError(f'{name} must be a list of {size} numbers')
    return [_num(v, low, high, f'{name}[{i}]') for i, v in enumerate(value)]


def _record(value, name, required, optional=()):
    if not isinstance(value, dict):
        raise ValueError(f'{name} must be a dict')
    keys = set(value)
    unknown = keys - set(required) - set(optional)
    if unknown:
        raise ValueError(f'{name} has unknown key(s): ' + ', '.join(sorted(map(str, unknown))))
    missing = [k for k in required if k not in value]
    if missing:
        raise ValueError(f'{name} is missing key(s): ' + ', '.join(missing))
    return value


def _unique_ids(items, name):
    seen = set()
    for it in items:
        if it['id'] in seen:
            raise ValueError(f'{name}: duplicate id {it["id"]!r}')
        seen.add(it['id'])


def _pack(op, result, assumptions, limits):
    return {'op': op, 'result': result, 'assumptions': list(assumptions),
            'limits': list(limits)}


def _r(x, nd=4):
    return round(float(x), nd)


def _esc(text):
    return (str(text).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            .replace('"', '&quot;').replace("'", '&apos;'))


def _safe_id(text):
    out = ''.join(c if (c.isascii() and (c.isalnum() or c in '-_')) else '_' for c in str(text))
    return out[:48] or 'x'


# --------------------------------------------------------------------------- colour helpers

def _parse_hex(value, name):
    if not isinstance(value, str):
        raise ValueError(f'{name} must be a hex colour string like #3366cc')
    s = value.strip().lower()
    if s.startswith('#'):
        s = s[1:]
    if len(s) not in (3, 6) or any(c not in '0123456789abcdef' for c in s):
        raise ValueError(f'{name} must be a hex colour like #36c or #3366cc')
    if len(s) == 3:
        s = ''.join(c * 2 for c in s)
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))


def _hex(rgb):
    return '#' + ''.join(f'{max(0, min(255, int(round(c)))):02x}' for c in rgb)


def _hsl_to_rgb255(h_deg, s, l):
    r, g, b = colorsys.hls_to_rgb((h_deg % 360.0) / 360.0, max(0.0, min(1.0, l)),
                                  max(0.0, min(1.0, s)))
    return (r * 255.0, g * 255.0, b * 255.0)


def _rgb_to_hsl(rgb):
    h, l, s = colorsys.rgb_to_hls(*(c / 255.0 for c in rgb))
    return [_r(h * 360.0, 2), _r(s), _r(l)]


def _lin(c8):
    c = c8 / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def relative_luminance(rgb):
    """WCAG 2.x relative luminance of an 8-bit sRGB triple."""
    r, g, b = (_lin(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(rgb1, rgb2):
    """WCAG 2.x contrast ratio (L_light + 0.05) / (L_dark + 0.05), in [1, 21]."""
    a, b = relative_luminance(rgb1), relative_luminance(rgb2)
    hi, lo = max(a, b), min(a, b)
    return (hi + 0.05) / (lo + 0.05)


def _rgb_to_lab(rgb):
    r, g, b = (_lin(c) for c in rgb)
    x = (0.4124564 * r + 0.3575761 * g + 0.1804375 * b) / 0.95047
    y = (0.2126729 * r + 0.7151522 * g + 0.0721750 * b) / 1.0
    z = (0.0193339 * r + 0.1191920 * g + 0.9503041 * b) / 1.08883

    def f(t):
        return t ** (1.0 / 3.0) if t > 216.0 / 24389.0 else (24389.0 / 27.0 * t + 16.0) / 116.0

    fx, fy, fz = f(x), f(y), f(z)
    return (116.0 * fy - 16.0, 500.0 * (fx - fy), 200.0 * (fy - fz))


def _delta_e76(rgb1, rgb2):
    a, b = _rgb_to_lab(rgb1), _rgb_to_lab(rgb2)
    return math.sqrt(sum((p - q) ** 2 for p, q in zip(a, b)))


def _palette_drift(p1, p2):
    """Symmetric mean nearest-colour CIE76 delta-E between two palettes."""
    def one_way(a, b):
        return sum(min(_delta_e76(c, d) for d in b) for c in a) / len(a)
    return (one_way(p1, p2) + one_way(p2, p1)) / 2.0


def _strong_direction(text):
    """(first strong direction 'rtl'/'ltr'/None, rtl strong count, ltr strong count)."""
    first = None
    n_r = n_l = 0
    for ch in text:
        bidi = unicodedata.bidirectional(ch)
        if bidi in ('R', 'AL'):
            n_r += 1
            first = first or 'rtl'
        elif bidi == 'L':
            n_l += 1
            first = first or 'ltr'
    return first, n_r, n_l


# --------------------------------------------------------------------------- 13.01 frame_composition

_DEFAULT_SHOTS = [
    {'id': 'thirds_hero', 'elements': [
        {'id': 'hero', 'x': 560, 'y': 180, 'w': 160, 'h': 360, 'weight': 2.0, 'subject': True},
        {'id': 'lamp', 'x': 1340, 'y': 420, 'w': 120, 'h': 260, 'weight': 1.0}]},
    {'id': 'centred', 'elements': [
        {'id': 'hero', 'x': 880, 'y': 300, 'w': 160, 'h': 480, 'weight': 2.0, 'subject': True}]},
    {'id': 'corner', 'elements': [
        {'id': 'hero', 'x': 0, 'y': 0, 'w': 160, 'h': 200, 'weight': 2.0, 'subject': True}]},
    {'id': 'symmetric_pair', 'elements': [
        {'id': 'left', 'x': 400, 'y': 300, 'w': 160, 'h': 400, 'weight': 1.0, 'subject': True},
        {'id': 'right', 'x': 1360, 'y': 300, 'w': 160, 'h': 400, 'weight': 1.0, 'subject': True}]},
    {'id': 'cramped_headroom', 'elements': [
        {'id': 'hero', 'x': 1200, 'y': 0, 'w': 160, 'h': 600, 'weight': 2.0, 'subject': True}]},
]


def _parse_frame(frame):
    _record(frame, 'frame', ('w', 'h'))
    return _num(frame['w'], 1, 20000, 'frame.w'), _num(frame['h'], 1, 20000, 'frame.h')


def _parse_boxes(elements, name, fw, fh):
    out = []
    for i, e in enumerate(_list(elements, name, 1, MAX_ELEMENTS)):
        n = f'{name}[{i}]'
        _record(e, n, ('id', 'x', 'y', 'w', 'h'), ('weight', 'subject'))
        out.append({
            'id': _str(e['id'], f'{n}.id', 64),
            'x': _num(e['x'], -fw, 2 * fw, f'{n}.x'), 'y': _num(e['y'], -fh, 2 * fh, f'{n}.y'),
            'w': _num(e['w'], 0, 2 * fw, f'{n}.w', low_open=True),
            'h': _num(e['h'], 0, 2 * fh, f'{n}.h', low_open=True),
            'weight': _num(e.get('weight', 1.0), 0, 100, f'{n}.weight', low_open=True),
            'subject': _bool(e.get('subject', False), f'{n}.subject'),
        })
    _unique_ids(out, name)
    return out


def _score_shot(fw, fh, boxes, balance_tol):
    diag = math.hypot(fw, fh)
    points = [(fw * a, fh * b) for b in (1 / 3, 2 / 3) for a in (1 / 3, 2 / 3)]
    subjects = [b for b in boxes if b['subject']]
    if not subjects:
        subjects = [max(boxes, key=lambda b: b['w'] * b['h'] * b['weight'])]
    per_subject = []
    for b in subjects:
        cx, cy = b['x'] + b['w'] / 2, b['y'] + b['h'] / 2
        dists = [math.hypot(cx - px, cy - py) for px, py in points]
        k = min(range(4), key=lambda j: dists[j])
        d_norm = dists[k] / diag
        thirds = max(0.0, 1.0 - d_norm / 0.25)
        headroom = b['y'] / fh
        if headroom < 0:
            head_score = 0.0
        elif headroom < 0.03:
            head_score = headroom / 0.03
        elif headroom <= 0.20:
            head_score = 1.0
        else:
            head_score = max(0.0, 1.0 - (headroom - 0.20) / 0.30)
        per_subject.append({'id': b['id'], 'centre': [_r(cx, 2), _r(cy, 2)],
                            'nearest_power_point': [_r(points[k][0], 2), _r(points[k][1], 2)],
                            'distance_px': _r(dists[k], 2), 'distance_norm': _r(d_norm),
                            'thirds_score': _r(thirds), 'headroom_frac': _r(headroom),
                            'headroom_score': _r(head_score)})
    mass = sum(b['w'] * b['h'] * b['weight'] for b in boxes)
    gx = sum((b['x'] + b['w'] / 2) * b['w'] * b['h'] * b['weight'] for b in boxes) / mass
    gy = sum((b['y'] + b['h'] / 2) * b['w'] * b['h'] * b['weight'] for b in boxes) / mass
    off = [(gx - fw / 2) / (fw / 2), (gy - fh / 2) / (fh / 2)]
    off_mag = math.hypot(*off)
    balance = max(0.0, 1.0 - off_mag)
    thirds = sum(s['thirds_score'] for s in per_subject) / len(per_subject)
    head = sum(s['headroom_score'] for s in per_subject) / len(per_subject)
    score = 0.5 * thirds + 0.3 * balance + 0.2 * head
    explain = []
    explain.append('subject(s) near a rule-of-thirds power point' if thirds >= 0.7 else
                   'subject(s) far from the thirds power points' if thirds < 0.3 else
                   'subject(s) moderately close to a thirds power point')
    if off_mag <= balance_tol:
        explain.append('visual mass balanced around the frame centre')
    else:
        side = ('right' if off[0] > 0 else 'left') if abs(off[0]) >= abs(off[1]) else \
            ('bottom' if off[1] > 0 else 'top')
        explain.append(f'visual mass leans {side} (offset {off_mag:.2f} of half-frame)')
    for s in per_subject:
        if s['headroom_frac'] < 0.03:
            explain.append(f'{s["id"]}: cramped headroom ({s["headroom_frac"]:.3f} of frame height)')
        elif s['headroom_frac'] > 0.20:
            explain.append(f'{s["id"]}: excessive headroom ({s["headroom_frac"]:.3f} of frame height)')
    return {'score': _r(score), 'thirds_score': _r(thirds), 'balance_score': _r(balance),
            'headroom_score': _r(head), 'subjects': per_subject,
            'mass_centroid': [_r(gx, 2), _r(gy, 2)],
            'centroid_offset': [_r(off[0]), _r(off[1])], 'centroid_offset_mag': _r(off_mag),
            'balanced': off_mag <= balance_tol, 'explain': explain}


def frame_composition(*, frame=None, elements=None, shots=None, balance_tolerance=0.1, **extra):
    """Score shot layouts: thirds power points, visual-mass balance and headroom.

    Boxes are {id, x, y, w, h, weight=1, subject=False} in frame pixels (y down).
    Key subjects are the boxes marked subject=True, else the heaviest box
    (area * weight). thirds_score = max(0, 1 - d/(0.25 * diagonal)) with d the
    subject-centre distance to the nearest power point; balance_score =
    max(0, 1 - |centroid offset|) with the offset measured in half-frames;
    headroom = top gap / frame height (ideal 0.03-0.20). score = 0.5 thirds +
    0.3 balance + 0.2 headroom. Pass `elements` for one shot or `shots`
    ([{id, elements, frame?}], up to 12) for a ranked review; with neither, five
    built-in shots are reviewed.
    """
    _no_extra(extra)
    fw, fh = _parse_frame(frame if frame is not None else {'w': 1920, 'h': 1080})
    balance_tolerance = _num(balance_tolerance, 0, 1, 'balance_tolerance')
    if elements is not None and shots is not None:
        raise ValueError('pass either elements (one shot) or shots, not both')
    if elements is not None:
        shot_list = [{'id': 'shot', 'elements': elements}]
    else:
        shot_list = shots if shots is not None else _DEFAULT_SHOTS
    shot_list = _list(shot_list, 'shots', 1, 12)
    reviewed = []
    for i, s in enumerate(shot_list):
        _record(s, f'shots[{i}]', ('id', 'elements'), ('frame',))
        sid = _str(s['id'], f'shots[{i}].id', 64)
        sw, sh = (fw, fh) if 'frame' not in s else _parse_frame(s['frame'])
        boxes = _parse_boxes(s['elements'], f'shots[{i}].elements', sw, sh)
        rep = _score_shot(sw, sh, boxes, balance_tolerance)
        rep['id'] = sid
        rep['frame'] = [sw, sh]
        reviewed.append(rep)
    _unique_ids(reviewed, 'shots')
    ranking = [s['id'] for s in sorted(reviewed, key=lambda s: (-s['score'], s['id']))]
    result = {'shots': reviewed, 'ranking': ranking, 'best': ranking[0], 'worst': ranking[-1],
              'weights': {'thirds': 0.5, 'balance': 0.3, 'headroom': 0.2}}
    return _pack('frame_composition', result,
                 ['boxes are axis-aligned rectangles; visual mass = area * weight (no colour, contrast or gaze)',
                  'rule of thirds is a heuristic, not a law: centred or symmetric framing can be intentional',
                  'headroom uses the box top as the head top; ideal band 3-20 % of frame height is a convention'],
                 ['up to 12 shots, up to 64 elements per shot', 'frame sides <= 20000 px',
                  'scores are in [0, 1] and only comparable between shots scored with the same weights'])


# --------------------------------------------------------------------------- 13.02 landscape_layers

def _value_noise(rng, lattice):
    vals = [rng.random() for _ in range(lattice + 2)]

    def f(t):
        pos = t * lattice
        i = min(int(math.floor(pos)), lattice)
        fr = pos - i
        s = (1 - math.cos(math.pi * fr)) / 2
        return vals[i] * (1 - s) + vals[i + 1] * s
    return f


def landscape_layers(*, seed=0, width=800, height=450, layers=4, samples=81, clouds=3,
                     sky_hue=210.0, terrain_hue=140.0, fill_to_bottom=True, band_px=60.0,
                     **extra):
    """Seeded layered landscape SVG with atmospheric perspective and a seam check.

    Layer 0 is the farthest. Each ridge is 2-octave 1D cosine-interpolated value
    noise sampled at `samples` x positions; far layers sit higher with taller
    relief, and their colour is lighter, less saturated and mixed toward the
    hazy sky colour. With fill_to_bottom (default) every layer polygon runs down
    to the frame bottom; otherwise each layer is a band of band_px under its
    ridge (useful to see the seam check fail). The seam check verifies, at
    every sampled x, that adjacent layers overlap and that the stack reaches
    the frame bottom without gaps.
    """
    _no_extra(extra)
    seed = _int(seed, 0, 2 ** 31 - 1, 'seed')
    width = _int(width, 64, 4096, 'width')
    height = _int(height, 64, 4096, 'height')
    layers = _int(layers, 2, 5, 'layers')
    samples = _int(samples, 8, 513, 'samples')
    clouds = _int(clouds, 0, 12, 'clouds')
    sky_hue = _num(sky_hue, 0, 360, 'sky_hue')
    terrain_hue = _num(terrain_hue, 0, 360, 'terrain_hue')
    fill_to_bottom = _bool(fill_to_bottom, 'fill_to_bottom')
    band_px = _num(band_px, 1, height, 'band_px')

    xs = [width * k / (samples - 1) for k in range(samples)]
    haze_rgb = _hsl_to_rgb255(sky_hue, 0.30, 0.86)
    sky_top = _hex(_hsl_to_rgb255(sky_hue, 0.55, 0.45))
    sky_bottom = _hex(haze_rgb)
    ridges, layer_info, paths = [], [], []
    for i in range(layers):
        t = i / (layers - 1)
        rng = random.Random(seed * 1009 + i * 7919 + 17)
        n1, n2 = _value_noise(rng, 4 + 2 * i), _value_noise(rng, 11 + 3 * i)
        base = height * (0.45 + 0.35 * t)
        amp = height * (0.22 - 0.12 * t)
        ridge = []
        for x in xs:
            u = x / width
            n = (n1(u) * 0.7 + n2(u) * 0.3)
            ridge.append(min(height - 1.0, max(1.0, base - amp * n)))
        ridges.append(ridge)
        own = _hsl_to_rgb255(terrain_hue, 0.12 + 0.38 * t, 0.80 - 0.55 * t)
        haze = 0.55 * (1 - t)
        rgb = tuple(o * (1 - haze) + h * haze for o, h in zip(own, haze_rgb))
        colour = _hex(rgb)
        lum = relative_luminance(_parse_hex(colour, 'c'))
        hsl = _rgb_to_hsl(_parse_hex(colour, 'c'))
        pts = ' '.join(f'L{x:.2f},{y:.2f}' for x, y in zip(xs, ridge))
        if fill_to_bottom:
            d = f'M0,{height} {pts} L{width},{height} Z'
        else:
            back = ' '.join(f'L{x:.2f},{min(height, y + band_px):.2f}'
                            for x, y in reversed(list(zip(xs, ridge))))
            d = f'M{xs[0]:.2f},{ridge[0]:.2f} {pts} {back} Z'
        paths.append(f'<path id="layer{i}" d="{d}" fill="{colour}"/>')
        layer_info.append({'index': i, 'depth': 'far' if i == 0 else 'near' if i == layers - 1 else 'mid',
                           'colour': colour, 'hsl': hsl, 'relative_luminance': _r(lum),
                           'ridge_min_y': _r(min(ridge), 2), 'ridge_max_y': _r(max(ridge), 2)})

    gaps = []
    for k, x in enumerate(xs):
        ivs = []
        for i in range(layers):
            top = ridges[i][k]
            bottom = height if fill_to_bottom else min(height, top + band_px)
            ivs.append((top, bottom))
        for i in range(layers - 1):
            (t0, b0), (t1, b1) = ivs[i], ivs[i + 1]
            if max(t0, t1) > min(b0, b1) + 1e-9:
                gaps.append({'x': _r(x, 2), 'between': [i, i + 1],
                             'gap_px': _r(max(t0, t1) - min(b0, b1), 2)})
        cover_top = min(t for t, _ in ivs)
        reach = cover_top
        for top, bottom in sorted(ivs):
            if top > reach + 1e-9:
                break
            reach = max(reach, bottom)
        if reach < height - 1e-9:
            gaps.append({'x': _r(x, 2), 'between': ['stack', 'frame_bottom'],
                         'gap_px': _r(height - reach, 2)})
    lums = [li['relative_luminance'] for li in layer_info]
    far_lighter = all(lums[i] > lums[i + 1] for i in range(layers - 1))
    sats = [li['hsl'][1] for li in layer_info]
    far_less_saturated = all(sats[i] <= sats[i + 1] + 1e-9 for i in range(layers - 1))

    crng = random.Random(seed * 31 + 5)
    cloud_svg = []
    for c in range(clouds):
        cx = crng.uniform(0.05, 0.95) * width
        cy = crng.uniform(0.06, 0.30) * height
        rx = crng.uniform(0.05, 0.10) * width
        ry = rx * crng.uniform(0.25, 0.4)
        parts = [f'<ellipse cx="{cx:.2f}" cy="{cy:.2f}" rx="{rx:.2f}" ry="{ry:.2f}"/>',
                 f'<ellipse cx="{cx - rx * 0.5:.2f}" cy="{cy + ry * 0.2:.2f}" rx="{rx * 0.6:.2f}" ry="{ry * 0.8:.2f}"/>',
                 f'<ellipse cx="{cx + rx * 0.55:.2f}" cy="{cy + ry * 0.25:.2f}" rx="{rx * 0.55:.2f}" ry="{ry * 0.7:.2f}"/>']
        cloud_svg.append(f'<g id="cloud{c}" fill="#ffffff" fill-opacity="0.85">' + ''.join(parts) + '</g>')
    svg = (f'<svg xmlns="{SVG_NS}" width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
           f'<defs><linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">'
           f'<stop offset="0" stop-color="{sky_top}"/><stop offset="1" stop-color="{sky_bottom}"/>'
           f'</linearGradient></defs>'
           f'<rect id="skyrect" x="0" y="0" width="{width}" height="{height}" fill="url(#sky)"/>'
           + ''.join(cloud_svg) + ''.join(paths) + '</svg>')
    result = {'svg': svg, 'seed': seed, 'layers': layer_info,
              'seam_check': {'ok': not gaps, 'sampled_x': samples, 'gaps': gaps[:50],
                             'gap_count': len(gaps)},
              'atmospheric_perspective': {'far_lighter': far_lighter,
                                          'far_less_saturated': far_less_saturated,
                                          'luminance_far_to_near': lums},
              'sky': {'top': sky_top, 'horizon': sky_bottom},
              'svg_sha256': hashlib.sha256(svg.encode('utf-8')).hexdigest()}
    return _pack('landscape_layers', result,
                 ['1D cosine-interpolated value noise (2 octaves), seeded by Python random.Random: deterministic per seed',
                  'atmospheric perspective approximated by lighter, less saturated far layers mixed toward a sky haze colour',
                  'seam check is evaluated at the sampled x positions only; the SVG draws straight segments between them'],
                 ['2-5 terrain layers, 8-513 samples, 0-12 clouds, width/height 64-4096 px',
                  'no textures, lighting or vegetation; flat colour layers only'])


# --------------------------------------------------------------------------- 13.03 three_point_light

def _rot2(v, ang):
    c, s = math.cos(ang), math.sin(ang)
    return (v[0] * c - v[1] * s, v[0] * s + v[1] * c)


def three_point_light(*, subject=(0.0, 0.0, 1.0), camera=(0.0, -5.0, 1.6), key_side='camera_left',
                      key_azimuth_deg=45.0, key_elevation_deg=35.0, fill_azimuth_deg=30.0,
                      fill_elevation_deg=15.0, rim_azimuth_deg=150.0, rim_elevation_deg=40.0,
                      key_fill_ratio=4.0, rim_ratio=0.75, light_distance=3.0, shadow_vector=None,
                      tolerance_deg=15.0, **extra):
    """Key/fill/rim plan around a subject, plus ground-shadow direction check.

    World units are metres, z is up, the ground is z = 0. Azimuths are measured
    on the ground plane from the subject->camera direction toward the camera's
    left or right (key_side). The fill goes on the opposite side of the key,
    the rim behind the subject on the fill side (opposite the key). Key
    intensity is 1, fill = 1 / key_fill_ratio, rim = rim_ratio. The key's
    shadow on the ground points away from the key: direction = -(key horizontal
    direction), length = object height / tan(key elevation). A supplied
    shadow_vector [dx, dy] passes when its angle to that direction is <=
    tolerance_deg.
    """
    _no_extra(extra)
    subject = _vec(subject, 3, 'subject', -1e4, 1e4)
    camera = _vec(camera, 3, 'camera', -1e4, 1e4)
    key_side = _choice(key_side, {'camera_left', 'camera_right'}, 'key_side')
    key_az = _num(key_azimuth_deg, 0, 90, 'key_azimuth_deg')
    key_el = _num(key_elevation_deg, 5, 85, 'key_elevation_deg')
    fill_az = _num(fill_azimuth_deg, 0, 90, 'fill_azimuth_deg')
    fill_el = _num(fill_elevation_deg, 0, 85, 'fill_elevation_deg')
    rim_az = _num(rim_azimuth_deg, 90, 180, 'rim_azimuth_deg')
    rim_el = _num(rim_elevation_deg, 0, 85, 'rim_elevation_deg')
    ratio = _num(key_fill_ratio, 1, 64, 'key_fill_ratio')
    rim_ratio = _num(rim_ratio, 0, 4, 'rim_ratio')
    dist = _num(light_distance, 0.1, 1000, 'light_distance')
    tol = _num(tolerance_deg, 0.5, 90, 'tolerance_deg')
    dx, dy = subject[0] - camera[0], subject[1] - camera[1]
    hl = math.hypot(dx, dy)
    if hl < 1e-6:
        raise ValueError('camera and subject must not share the same ground position')
    fwd = (dx / hl, dy / hl)                  # camera -> subject
    to_cam = (-fwd[0], -fwd[1])               # subject -> camera
    right = (fwd[1], -fwd[0])                 # camera's right on the ground
    side = -1.0 if key_side == 'camera_left' else 1.0

    def place(az_deg, el_deg, sgn):
        a = math.radians(az_deg)
        h = (to_cam[0] * math.cos(a) + sgn * right[0] * math.sin(a),
             to_cam[1] * math.cos(a) + sgn * right[1] * math.sin(a))
        e = math.radians(el_deg)
        pos = [subject[0] + dist * math.cos(e) * h[0], subject[1] + dist * math.cos(e) * h[1],
               subject[2] + dist * math.sin(e)]
        return h, pos

    key_h, key_pos = place(key_az, key_el, side)
    fill_h, fill_pos = place(fill_az, fill_el, -side)
    rim_h, rim_pos = place(rim_az, rim_el, -side)
    shadow_dir = (-key_h[0], -key_h[1])
    lights = {
        'key': {'position': [_r(c) for c in key_pos], 'azimuth_deg': key_az, 'elevation_deg': key_el,
                'side': key_side, 'intensity': 1.0},
        'fill': {'position': [_r(c) for c in fill_pos], 'azimuth_deg': fill_az, 'elevation_deg': fill_el,
                 'side': 'camera_right' if key_side == 'camera_left' else 'camera_left',
                 'intensity': _r(1.0 / ratio, 6)},
        'rim': {'position': [_r(c) for c in rim_pos], 'azimuth_deg': rim_az, 'elevation_deg': rim_el,
                'side': 'camera_right' if key_side == 'camera_left' else 'camera_left',
                'intensity': _r(rim_ratio, 6)},
    }
    validation = None
    if shadow_vector is not None:
        sv = _vec(shadow_vector, 2, 'shadow_vector')
        n = math.hypot(*sv)
        if n < 1e-9:
            raise ValueError('shadow_vector must not be the zero vector')
        cosang = max(-1.0, min(1.0, (sv[0] * shadow_dir[0] + sv[1] * shadow_dir[1]) / n))
        ang = math.degrees(math.acos(cosang))
        validation = {'supplied': [_r(sv[0] / n, 6), _r(sv[1] / n, 6)], 'angle_error_deg': _r(ang, 3),
                      'tolerance_deg': tol, 'passes': ang <= tol, 'points_toward_key': ang > 90.0}
    result = {
        'lights': lights,
        'key_fill_ratio': ratio, 'contrast_stops': _r(math.log2(ratio)),
        'ratio_label': 'high-key/soft' if ratio <= 2 else 'standard' if ratio <= 4 else 'low-key/dramatic',
        'camera_forward': [_r(fwd[0], 6), _r(fwd[1], 6)],
        'expected_shadow': {'direction': [_r(shadow_dir[0], 6), _r(shadow_dir[1], 6)],
                            'length_per_metre_of_height': _r(1.0 / math.tan(math.radians(key_el))),
                            'from': 'key light'},
        'shadow_validation': validation,
    }
    return _pack('three_point_light', result,
                 ['key treated as a point/directional light; fill and rim cast no ground shadow of note',
                  'azimuths measured on the ground plane from the subject->camera direction',
                  'intensities are relative (key = 1); real fixtures also need distance falloff and diffusion'],
                 ['key elevation 5-85 deg so a finite ground shadow exists', 'tolerance 0.5-90 deg',
                  'positions in metres, |coord| <= 1e4'])


# --------------------------------------------------------------------------- 13.04 palette_harmony

_HARMONY = {
    'complementary': [0.0, 180.0],
    'analogous': [-30.0, 0.0, 30.0],
    'triadic': [0.0, 120.0, 240.0],
    'split': [0.0, 150.0, 210.0],
}


def _swatch(rgb):
    lum = relative_luminance(rgb)
    cw, cb = contrast_ratio(rgb, (255, 255, 255)), contrast_ratio(rgb, (0, 0, 0))
    best = '#ffffff' if cw >= cb else '#000000'
    return {'hex': _hex(rgb), 'hsl': _rgb_to_hsl(rgb), 'relative_luminance': _r(lum, 6),
            'best_text': best, 'best_text_contrast': _r(max(cw, cb), 3)}


def palette_harmony(*, base='#3366cc', rules=None, pairs=None, **extra):
    """Harmony palettes from a base colour plus WCAG 2.x contrast checks.

    Rules rotate the base hue in HSL keeping saturation and lightness:
    complementary (0, 180), analogous (-30, 0, 30), triadic (0, 120, 240),
    split-complementary (0, 150, 210). Relative luminance uses the sRGB
    transfer function and L = 0.2126 R + 0.7152 G + 0.0722 B; contrast =
    (L1 + 0.05) / (L2 + 0.05). Pairs ({fg, bg, size='normal'|'large'} or
    [fg, bg]) are flagged under 4.5:1 (normal text) or 3:1 (large text).
    """
    _no_extra(extra)
    base_rgb = _parse_hex(base, 'base')
    if rules is None:
        rules = sorted(_HARMONY)
    rules = _list(rules, 'rules', 1, len(_HARMONY))
    for r in rules:
        _choice(r, set(_HARMONY), 'rules[]')
    h, s, l = _rgb_to_hsl(base_rgb)
    palettes = {}
    for rule in rules:
        sw = []
        for off in _HARMONY[rule]:
            rgb = base_rgb if off == 0 else tuple(int(round(c)) for c in _hsl_to_rgb255(h + off, s, l))
            item = _swatch(rgb)
            item['hue_offset_deg'] = off
            sw.append(item)
        palettes[rule] = sw
    if pairs is None:
        pairs = [{'fg': base, 'bg': '#ffffff', 'size': 'normal'},
                 {'fg': '#777777', 'bg': '#ffffff', 'size': 'normal'},
                 {'fg': '#777777', 'bg': '#ffffff', 'size': 'large'},
                 {'fg': '#000000', 'bg': '#ffffff', 'size': 'normal'}]
    pairs = _list(pairs, 'pairs', 0, 200)
    checked = []
    for i, p in enumerate(pairs):
        n = f'pairs[{i}]'
        if isinstance(p, (list, tuple)):
            if len(p) != 2:
                raise ValueError(f'{n} must be [fg, bg] or {{fg, bg, size}}')
            p = {'fg': p[0], 'bg': p[1]}
        _record(p, n, ('fg', 'bg'), ('size',))
        fg, bg = _parse_hex(p['fg'], f'{n}.fg'), _parse_hex(p['bg'], f'{n}.bg')
        size = _choice(p.get('size', 'normal'), {'normal', 'large'}, f'{n}.size')
        ratio = contrast_ratio(fg, bg)
        need = 4.5 if size == 'normal' else 3.0
        checked.append({'fg': _hex(fg), 'bg': _hex(bg), 'size': size, 'contrast': _r(ratio, 4),
                        'required': need, 'passes_aa_normal': ratio >= 4.5,
                        'passes_aa_large': ratio >= 3.0, 'passes_aaa_normal': ratio >= 7.0,
                        'flagged': ratio < need})
    result = {'base': _swatch(base_rgb), 'palettes': palettes, 'pairs': checked,
              'flagged_count': sum(1 for c in checked if c['flagged'])}
    return _pack('palette_harmony', result,
                 ['hue rotations in HSL (colorsys HLS); perceptual hue spacing is not uniform',
                  'WCAG 2.x relative luminance with the IEC sRGB 0.04045 threshold (WCAG text quotes 0.03928; identical for 8-bit values)',
                  'large text = >= 24 px regular or >= 18.66 px bold (WCAG definition); size must be declared by the caller'],
                 ['up to 200 pairs', 'contrast ignores opacity, anti-aliasing, font weight and APCA-style polarity effects'])


# --------------------------------------------------------------------------- 13.05 arabic_text_layout

_SHADDA = 'ّ'
_TANWEEN = {'ً', 'ٌ', 'ٍ'}
_HARAKAT = {'َ', 'ُ', 'ِ', 'ْ', 'ٰ'} | _TANWEEN | {_SHADDA}
_ALEFS = {'ا', 'أ', 'إ', 'آ'}
_LAM = 'ل'
_LAMALEF_LIG = {chr(c) for c in range(0xFEF5, 0xFEFD)}
_BIDI_CONTROLS = {'‎', '‏', '‪', '‫', '‬', '‭', '‮',
                  '⁦', '⁧', '⁨', '⁩', '؜'}
_TATWEEL = 'ـ'


def _is_mark(ch):
    return unicodedata.combining(ch) != 0 or unicodedata.category(ch) in ('Mn', 'Me')


def _clusters(word):
    out = []
    orphan = 0
    for ch in word:
        if out and (_is_mark(ch) or ch == '‍' or (out[-1].endswith('‍'))):
            out[-1] += ch
        else:
            if _is_mark(ch):
                orphan += 1
            out.append(ch)
    return out, orphan


def arabic_text_layout(*, text='مَرْحَبًا بِالسَّلَامِ فِي كُلِّ مَكَانٍ', duration=3.0, start=0.0,
                       overlap=0.25, remove_tatweel=True, font_size=72, width=1080, height=360,
                       **extra):
    """Prepare Arabic text for motion typography (no glyph shaping here).

    Steps: NFC normalisation, removal of bidi control characters (and
    tatweel if remove_tatweel), whitespace collapse; direction from the first
    strong character (Unicode rule P2); words split on whitespace; grapheme
    clusters built so combining marks (harakat, shadda, tanween, superscript
    alef) always stay attached to their base letter. Each word gets a
    difficulty weight (shadda, tanween, lam-alef, harakat, length) that sets
    its share of `duration`; consecutive words overlap by `overlap` of their
    slot. The SVG uses <text direction="rtl" unicode-bidi="embed">; joining,
    lam-alef ligatures and mark placement are left to the renderer's shaper
    (HarfBuzz / RAQM).
    """
    _no_extra(extra)
    text = _str(text, 'text', 2000)
    duration = _num(duration, 0.1, 600, 'duration')
    start = _num(start, 0, 3600, 'start')
    overlap = _num(overlap, 0, 0.9, 'overlap')
    remove_tatweel = _bool(remove_tatweel, 'remove_tatweel')
    font_size = _num(font_size, 4, 1000, 'font_size')
    width = _int(width, 64, 8192, 'width')
    height = _int(height, 32, 8192, 'height')

    norm = unicodedata.normalize('NFC', text)
    removed = sum(1 for c in norm if c in _BIDI_CONTROLS or (remove_tatweel and c == _TATWEEL))
    norm = ''.join(c for c in norm if c not in _BIDI_CONTROLS and not (remove_tatweel and c == _TATWEEL))
    words_raw = norm.split()
    if not words_raw:
        raise ValueError('text has no words after normalisation')
    if len(words_raw) > 200:
        raise ValueError('text may have at most 200 words')
    norm = ' '.join(words_raw)
    first, n_r, n_l = _strong_direction(norm)
    direction = first or 'ltr'
    words = []
    for wi, w in enumerate(words_raw):
        cl, orphan = _clusters(w)
        bases = [c[0] for c in cl]
        shadda = w.count(_SHADDA)
        tanween = sum(1 for c in w if c in _TANWEEN)
        harakat = sum(1 for c in w if c in _HARAKAT)
        lamalef = sum(1 for c in w if c in _LAMALEF_LIG)
        for a, b in zip(bases, bases[1:]):
            if a == _LAM and b in _ALEFS:
                lamalef += 1
        difficulty = 1.0 + 0.5 * shadda + 0.5 * tanween + 0.5 * lamalef + 0.1 * harakat + 0.05 * len(cl)
        reasons = [r for r, n in (('shadda', shadda), ('tanween', tanween), ('lam_alef', lamalef)) if n]
        words.append({'index': wi, 'word': w, 'graphemes': cl, 'grapheme_count': len(cl),
                      'orphan_marks': orphan, 'shadda': shadda, 'tanween': tanween,
                      'harakat': harakat, 'lam_alef': lamalef, 'difficulty': _r(difficulty),
                      'difficult': bool(reasons), 'difficult_because': reasons})
    weights = [w['difficulty'] * max(1, w['grapheme_count']) for w in words]
    total_w = sum(weights)
    n = len(words)
    # slots s_i; starts advance by s_i * (1 - overlap); last slot ends at start + duration
    eff = sum(wt / total_w for wt in weights[:-1]) * (1 - overlap) + weights[-1] / total_w
    scale = duration / eff
    t = start
    for w, wt in zip(words, weights):
        slot = scale * wt / total_w
        w['start'] = _r(t, 4)
        w['end'] = _r(t + slot, 4)
        w['duration'] = _r(slot, 4)
        t += slot * (1 - overlap)
    anchor_x = width - font_size * 0.5 if direction == 'rtl' else font_size * 0.5
    tspans = ''.join(f'<tspan id="w{w["index"]}">{_esc(w["word"])}</tspan>' + (' ' if i < n - 1 else '')
                     for i, w in enumerate(words))
    svg = (f'<svg xmlns="{SVG_NS}" width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
           f'<text x="{anchor_x:.2f}" y="{height / 2 + font_size * 0.35:.2f}" font-size="{font_size:.2f}" '
           f'direction="{direction}" unicode-bidi="embed" text-anchor="start" xml:lang="{"ar" if direction == "rtl" else "und"}" '
           f'font-family="Noto Naskh Arabic, Amiri, sans-serif">{tspans}</text></svg>')
    result = {'normalised': norm, 'direction': direction, 'is_rtl': direction == 'rtl',
              'strong_rtl_chars': n_r, 'strong_ltr_chars': n_l, 'removed_controls': removed,
              'words': words, 'difficult_words': [w['word'] for w in words if w['difficult']],
              'lam_alef_words': [w['word'] for w in words if w['lam_alef']],
              'timeline_end': words[-1]['end'], 'svg': svg,
              'shaping': 'not performed here: contextual joining, lam-alef ligatures and mark positioning '
                         'are done by the renderer (HarfBuzz / RAQM)'}
    return _pack('arabic_text_layout', result,
                 ['direction from the first strong character (Unicode bidi rule P2); mixed text needs the full UBA in the renderer',
                  'grapheme clusters = base + following combining marks / ZWJ (a simplified UAX #29, enough for Arabic harakat)',
                  'difficulty weights are heuristic animation-pacing weights, not a reading-time model',
                  'no glyph shaping: the renderer (HarfBuzz / RAQM) must shape; per-word tspans keep each word shaped as a unit'],
                 ['text <= 2000 chars and <= 200 words', 'duration 0.1-600 s, overlap 0-0.9',
                  'fonts are named only; nothing is embedded or loaded'])


# --------------------------------------------------------------------------- 13.06 logo_marks

_SIG_ANGLE_BINS = 36
_SIG_RADIUS_BINS = 12


def _gen_mark(seed):
    rng = random.Random(seed * 2654435761 % (2 ** 32))
    prims, pts = [], []
    for _ in range(rng.randint(2, 4)):
        kind = rng.choice(['circle', 'polygon', 'arc'])
        cx, cy = rng.uniform(-0.35, 0.35), rng.uniform(-0.35, 0.35)
        if kind == 'circle':
            r = rng.uniform(0.2, 0.6)
            prims.append({'kind': 'circle', 'cx': cx, 'cy': cy, 'r': r})
            pts += [(cx + r * math.cos(2 * math.pi * k / 72), cy + r * math.sin(2 * math.pi * k / 72))
                    for k in range(72)]
        elif kind == 'polygon':
            n = rng.randint(3, 8)
            r = rng.uniform(0.25, 0.7)
            rot = rng.uniform(0, 2 * math.pi / n)
            verts = [(cx + r * math.cos(rot + 2 * math.pi * k / n), cy + r * math.sin(rot + 2 * math.pi * k / n))
                     for k in range(n)]
            prims.append({'kind': 'polygon', 'sides': n, 'cx': cx, 'cy': cy, 'r': r, 'rotation': rot,
                          'vertices': verts})
            for k in range(n):
                (x0, y0), (x1, y1) = verts[k], verts[(k + 1) % n]
                pts += [(x0 + (x1 - x0) * j / 12, y0 + (y1 - y0) * j / 12) for j in range(12)]
        else:
            r = rng.uniform(0.3, 0.8)
            a0 = rng.uniform(0, 2 * math.pi)
            sweep = rng.uniform(math.pi / 3, 1.6 * math.pi)
            prims.append({'kind': 'arc', 'cx': cx, 'cy': cy, 'r': r, 'start': a0, 'sweep': sweep})
            pts += [(cx + r * math.cos(a0 + sweep * j / 47), cy + r * math.sin(a0 + sweep * j / 47))
                    for j in range(48)]
    hue = rng.uniform(0, 360)
    return prims, pts, hue


def _signature(pts):
    gx = sum(p[0] for p in pts) / len(pts)
    gy = sum(p[1] for p in pts) / len(pts)
    polar = [(math.atan2(y - gy, x - gx) % (2 * math.pi), math.hypot(x - gx, y - gy)) for x, y in pts]
    rmax = max(r for _, r in polar) or 1.0
    radial = [0.0] * _SIG_ANGLE_BINS
    hist = [0.0] * _SIG_RADIUS_BINS
    for a, r in polar:
        k = min(_SIG_ANGLE_BINS - 1, int(a / (2 * math.pi) * _SIG_ANGLE_BINS))
        radial[k] = max(radial[k], r / rmax)
        hist[min(_SIG_RADIUS_BINS - 1, int(r / rmax * _SIG_RADIUS_BINS))] += 1.0 / len(polar)
    # centre each block (zero mean) so cosine compares shape, not the shared positive offset
    mr, mh = sum(radial) / len(radial), sum(hist) / len(hist)
    vec = [v - mr for v in radial] + [(v - mh) * 3.0 for v in hist]
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [round(v / norm, 6) for v in vec]


def _cos(a, b):
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na < 1e-12 or nb < 1e-12:
        return 0.0
    return sum(x * y for x, y in zip(a, b)) / (na * nb)


def _mark_svg(prims, hue, size, mid):
    def X(v):
        return size / 2 + v * size * 0.45
    fill = _hex(_hsl_to_rgb255(hue, 0.55, 0.45))
    accent = _hex(_hsl_to_rgb255(hue + 180, 0.5, 0.35))
    parts = []
    for k, p in enumerate(prims):
        if p['kind'] == 'circle':
            parts.append(f'<circle cx="{X(p["cx"]):.2f}" cy="{X(p["cy"]):.2f}" r="{p["r"] * size * 0.45:.2f}" '
                         f'fill="{fill}" fill-opacity="{0.55 + 0.15 * (k % 3):.2f}"/>')
        elif p['kind'] == 'polygon':
            pts = ' '.join(f'{X(x):.2f},{X(y):.2f}' for x, y in p['vertices'])
            parts.append(f'<polygon points="{pts}" fill="{fill}" fill-opacity="{0.5 + 0.15 * (k % 3):.2f}"/>')
        else:
            r = p['r'] * size * 0.45
            a0, a1 = p['start'], p['start'] + p['sweep']
            x0, y0 = X(p['cx']) + r * math.cos(a0), X(p['cy']) + r * math.sin(a0)
            x1, y1 = X(p['cx']) + r * math.cos(a1), X(p['cy']) + r * math.sin(a1)
            large = 1 if p['sweep'] > math.pi else 0
            parts.append(f'<path d="M{x0:.2f},{y0:.2f} A{r:.2f},{r:.2f} 0 {large} 1 {x1:.2f},{y1:.2f}" '
                         f'fill="none" stroke="{accent}" stroke-width="{size * 0.036:.2f}" stroke-linecap="round"/>')
    return (f'<svg xmlns="{SVG_NS}" id="{mid}" width="{size}" height="{size}" viewBox="0 0 {size} {size}">'
            + ''.join(parts) + '</svg>')


def logo_marks(*, seed=0, count=3, size=256, references=None, threshold=0.95, **extra):
    """Seeded original geometric marks with a shape signature and similarity gate.

    Each mark is 2-4 primitives (circles, regular 3-8-gons, stroked arcs)
    from random.Random(seed). Its signature is a 36-bin radial profile (max
    boundary radius per angle bin around the centroid, scale-normalised) plus a
    12-bin radius histogram (weighted x3), each block made zero-mean, then
    L2-normalised and rounded to 6 decimals, so cosine lies in [-1, 1]. A mark is
    flagged when its cosine similarity to any reference signature (list of 48
    numbers or {id, signature}) or to another generated mark is >= threshold.
    """
    _no_extra(extra)
    seed = _int(seed, 0, 2 ** 31 - 1, 'seed')
    count = _int(count, 1, 24, 'count')
    size = _int(size, 32, 2048, 'size')
    threshold = _num(threshold, 0, 1, 'threshold')
    sig_len = _SIG_ANGLE_BINS + _SIG_RADIUS_BINS
    refs = []
    if references is not None:
        for i, ref in enumerate(_list(references, 'references', 0, 500)):
            n = f'references[{i}]'
            if isinstance(ref, dict):
                _record(ref, n, ('id', 'signature'))
                rid, sig = _str(ref['id'], f'{n}.id', 64), ref['signature']
            else:
                rid, sig = f'ref{i}', ref
            refs.append((rid, _vec(sig, sig_len, f'{n}.signature', -1e3, 1e3)))
    marks = []
    for k in range(count):
        s = (seed + k) % (2 ** 31)
        prims, pts, hue = _gen_mark(s)
        sig = _signature(pts)
        mid = f'mark{s}'
        marks.append({'id': mid, 'seed': s, 'primitives': [
            {kk: (_r(v, 6) if isinstance(v, float) else v) for kk, v in p.items() if kk != 'vertices'}
            for p in prims], 'signature': sig, 'svg': _mark_svg(prims, hue, size, mid)})
    for i, m in enumerate(marks):
        sims = []
        for rid, rsig in refs:
            c = _cos(m['signature'], rsig)
            if c >= threshold:
                sims.append({'against': rid, 'kind': 'reference', 'cosine': _r(c, 6)})
        for j, o in enumerate(marks):
            if j != i:
                c = _cos(m['signature'], o['signature'])
                if c >= threshold:
                    sims.append({'against': o['id'], 'kind': 'generated', 'cosine': _r(c, 6)})
        best_ref = max((_cos(m['signature'], r) for _, r in refs), default=None)
        m['max_reference_cosine'] = None if best_ref is None else _r(best_ref, 6)
        m['too_similar'] = sims
        m['flagged'] = bool(sims)
    result = {'marks': marks, 'threshold': threshold, 'signature_length': sig_len,
              'flagged': [m['id'] for m in marks if m['flagged']],
              'signature_method': 'radial max-radius profile (36 angle bins) + radius histogram (12 bins), each block zero-mean, L2-normalised'}
    return _pack('logo_marks', result,
                 ['signature is a coarse geometric descriptor on sampled outlines; it ignores colour, fill and stroke width',
                  'signature is scale/translation invariant but NOT rotation or mirror invariant',
                  'originality is checked only against the supplied references, not against any trademark register'],
                 ['count <= 24, references <= 500, size 32-2048 px',
                  'a low cosine is not legal clearance; a human trademark search is still required'])


# --------------------------------------------------------------------------- 13.07 poster_hierarchy

_DEFAULT_POSTER = [
    {'id': 'logo', 'role': 'logo', 'x': 860, 'y': 40, 'w': 180, 'h': 90},
    {'id': 'title', 'role': 'title', 'x': 80, 'y': 160, 'w': 920, 'h': 140, 'font_px': 96,
     'text': 'عرض الصيف'},
    {'id': 'image', 'role': 'image', 'x': 140, 'y': 330, 'w': 800, 'h': 520},
    {'id': 'body', 'role': 'body', 'x': 80, 'y': 870, 'w': 920, 'h': 80, 'font_px': 34,
     'text': 'خصم على كل المنتجات لمدة أسبوع'},
    {'id': 'price', 'role': 'price', 'x': 560, 'y': 970, 'w': 440, 'h': 110, 'font_px': 72,
     'text': '٩٩ جنيه'},
    {'id': 'cta', 'role': 'cta', 'x': 300, 'y': 1120, 'w': 480, 'h': 120, 'font_px': 48,
     'text': 'اطلب الآن'},
]
_TEXT_ROLES = {'title', 'price', 'cta', 'body'}


def poster_hierarchy(*, width=1080, height=1350, direction='auto', elements=None, min_body_px=28.0,
                     thumb_zone_top=0.55, **extra):
    """Check a poster for hierarchy, reading order, phone legibility and CTA reach.

    Elements: {id, role in title|price|cta|body|image|logo, x, y, w, h,
    font_px (text roles), text?} in canvas px. Font sizes are rescaled to a
    1080 px-wide output (font_px * 1080 / width) before the minimum
    (min_body_px, default 28) is applied to every text role. Rules: title >
    price > CTA font size, CTA >= largest body font, reading order top->bottom
    then right->left (RTL) or left->right (LTR) with title before price before
    CTA, CTA centre inside the thumb zone (y >= thumb_zone_top * height), all
    boxes inside the canvas. direction 'auto' uses the first strong character
    of the texts (falls back to 'ltr').
    """
    _no_extra(extra)
    width = _num(width, 100, 10000, 'width')
    height = _num(height, 100, 20000, 'height')
    direction = _choice(direction, {'auto', 'rtl', 'ltr'}, 'direction')
    min_body_px = _num(min_body_px, 1, 500, 'min_body_px')
    thumb_zone_top = _num(thumb_zone_top, 0, 1, 'thumb_zone_top')
    els = []
    for i, e in enumerate(_list(elements if elements is not None else _DEFAULT_POSTER, 'elements', 1, MAX_ELEMENTS)):
        n = f'elements[{i}]'
        _record(e, n, ('id', 'role', 'x', 'y', 'w', 'h'), ('font_px', 'text'))
        role = _choice(e['role'], _TEXT_ROLES | {'image', 'logo'}, f'{n}.role')
        item = {'id': _str(e['id'], f'{n}.id', 64), 'role': role,
                'x': _num(e['x'], -width, 2 * width, f'{n}.x'), 'y': _num(e['y'], -height, 2 * height, f'{n}.y'),
                'w': _num(e['w'], 0, 2 * width, f'{n}.w', low_open=True),
                'h': _num(e['h'], 0, 2 * height, f'{n}.h', low_open=True),
                'text': _str(e.get('text', ''), f'{n}.text', 500, allow_empty=True)}
        if role in _TEXT_ROLES:
            if 'font_px' not in e:
                raise ValueError(f'{n}.font_px is required for role {role}')
            item['font_px'] = _num(e['font_px'], 0, 2000, f'{n}.font_px', low_open=True)
        elif 'font_px' in e:
            raise ValueError(f'{n}.font_px only applies to text roles')
        els.append(item)
    _unique_ids(els, 'elements')
    roles = [e['role'] for e in els]
    if roles.count('title') != 1:
        raise ValueError('poster needs exactly one title element')
    if 'cta' not in roles:
        raise ValueError('poster needs at least one cta element')
    if direction == 'auto':
        first = _strong_direction(' '.join(e['text'] for e in els))[0]
        direction = first or 'ltr'
    scale = 1080.0 / width
    issues = []

    def font(role):
        fs = [e['font_px'] * scale for e in els if e['role'] == role]
        return max(fs) if fs else None

    for e in els:
        if e['role'] in _TEXT_ROLES:
            e['font_px_at_1080'] = _r(e['font_px'] * scale, 2)
            if e['font_px'] * scale < min_body_px - 1e-9:
                issues.append({'rule': 'min_font', 'id': e['id'],
                               'detail': f'{e["font_px"] * scale:.1f} px at 1080 wide < {min_body_px:g} px'})
        if e['x'] < 0 or e['y'] < 0 or e['x'] + e['w'] > width or e['y'] + e['h'] > height:
            issues.append({'rule': 'outside_canvas', 'id': e['id'], 'detail': 'box extends outside the canvas'})
    f_title, f_price, f_cta, f_body = font('title'), font('price'), font('cta'), font('body')
    chain = [('title', f_title)] + ([('price', f_price)] if f_price is not None else []) + [('cta', f_cta)]
    for (ra, fa), (rb, fb) in zip(chain, chain[1:]):
        if not fa > fb:
            issues.append({'rule': 'size_hierarchy', 'id': rb,
                           'detail': f'{ra} ({fa:.1f} px) must be larger than {rb} ({fb:.1f} px)'})
    if f_body is not None and f_cta < f_body:
        issues.append({'rule': 'cta_smaller_than_body', 'id': 'cta',
                       'detail': f'cta {f_cta:.1f} px < body {f_body:.1f} px'})
    # reading order: group into rows by vertical overlap, then sort within the row
    order_src = sorted(els, key=lambda e: (e['y'], e['id']))
    rows = []
    for e in order_src:
        placed = False
        for row in rows:
            ref = row[0]
            ov = min(ref['y'] + ref['h'], e['y'] + e['h']) - max(ref['y'], e['y'])
            if ov >= 0.5 * min(ref['h'], e['h']):
                row.append(e)
                placed = True
                break
        if not placed:
            rows.append([e])
    order = []
    for row in rows:
        if direction == 'rtl':
            row.sort(key=lambda e: (-(e['x'] + e['w']), e['id']))
        else:
            row.sort(key=lambda e: (e['x'], e['id']))
        order += [e['id'] for e in row]
    pos = {}
    for idx, eid in enumerate(order):
        role = next(e['role'] for e in els if e['id'] == eid)
        pos.setdefault(role, idx)
    seq = [r for r in ('title', 'price', 'cta') if r in pos]
    for a, b in zip(seq, seq[1:]):
        if pos[a] > pos[b]:
            issues.append({'rule': 'reading_order', 'id': b,
                           'detail': f'{b} is read before {a} ({direction} order)'})
    for e in els:
        if e['role'] == 'cta':
            cy = e['y'] + e['h'] / 2
            e['in_thumb_zone'] = cy >= thumb_zone_top * height
            if not e['in_thumb_zone']:
                issues.append({'rule': 'thumb_zone', 'id': e['id'],
                               'detail': f'cta centre y={cy:.0f} above thumb zone start {thumb_zone_top * height:.0f}'})
    result = {'ok': not issues, 'issues': issues, 'direction': direction, 'reading_order': order,
              'scale_to_1080': _r(scale, 6),
              'fonts_at_1080': {k: (None if v is None else _r(v, 2)) for k, v in
                                (('title', f_title), ('price', f_price), ('cta', f_cta), ('body', f_body))},
              'elements': els}
    return _pack('poster_hierarchy', result,
                 ['hierarchy measured by font size only (weight, colour and contrast are not considered)',
                  'reading order = rows by vertical overlap (>= 50 %), then right->left for RTL or left->right for LTR',
                  'thumb zone = lower part of a portrait phone screen (one-handed reach), y >= thumb_zone_top * height'],
                 ['up to 64 elements', 'minimum font applies to every text role at a 1080 px-wide output',
                  'no text measurement: boxes are trusted to contain their text'])


# --------------------------------------------------------------------------- 13.08 interior_layout

_DEFAULT_ROOM = {'w': 500, 'h': 400}
_DEFAULT_DOOR = {'wall': 'bottom', 'offset': 40, 'width': 90, 'hinge': 'start'}
_DEFAULT_FURNITURE = [
    {'id': 'sofa', 'x': 150, 'y': 310, 'w': 220, 'h': 90},
    {'id': 'coffee_table', 'x': 200, 'y': 190, 'w': 120, 'h': 60},
    {'id': 'tv_stand', 'x': 250, 'y': 0, 'w': 180, 'h': 45},
    {'id': 'armchair', 'x': 420, 'y': 170, 'w': 80, 'h': 80},
]


def _seg_dist(px, py, ax, ay, bx, by):
    vx, vy = bx - ax, by - ay
    L = vx * vx + vy * vy
    t = 0.0 if L == 0 else max(0.0, min(1.0, ((px - ax) * vx + (py - ay) * vy) / L))
    return math.hypot(px - (ax + t * vx), py - (ay + t * vy))


def _rect_dist(px, py, r):
    dx = max(r['x'] - px, 0.0, px - (r['x'] + r['w']))
    dy = max(r['y'] - py, 0.0, py - (r['y'] + r['h']))
    return math.hypot(dx, dy)


def interior_layout(*, room=None, door=None, furniture=None, zones=None, walkway_cm=80.0, cell_cm=10.0,
                    reach_cm=60.0, **extra):
    """Furniture placement check: overlaps, door swing, 80 cm walkways, reachability.

    Room is {w, h} in cm with the origin at a corner (x along the bottom wall,
    y into the room). Door is {wall: bottom|top|left|right, offset, width,
    hinge: start|end}; it swings into the room as a quarter disc of radius
    `width` around the hinge. Free space is a grid of cell_cm cells; a cell
    centre is walkable when it is >= walkway_cm / 2 from every furniture box
    and wall (the door opening is not a wall). BFS starts just inside the door.
    A zone ({id, x, y} point, or every furniture box when zones is omitted) is
    reachable when a walked cell centre lies within reach_cm of it.
    """
    _no_extra(extra)
    room_given, door_given = room, door
    room = _record(room if room is not None else _DEFAULT_ROOM, 'room', ('w', 'h'))
    W, H = _num(room['w'], 50, 5000, 'room.w'), _num(room['h'], 50, 5000, 'room.h')
    door = _record(door if door is not None else _DEFAULT_DOOR, 'door', ('wall', 'offset', 'width'), ('hinge',))
    wall = _choice(door['wall'], {'bottom', 'top', 'left', 'right'}, 'door.wall')
    wall_len = W if wall in ('bottom', 'top') else H
    dw = _num(door['width'], 30, 400, 'door.width')
    doff = _num(door['offset'], 0, wall_len - dw if wall_len > dw else 0, 'door.offset')
    if doff + dw > wall_len + 1e-9:
        raise ValueError('door does not fit on its wall')
    hinge = _choice(door.get('hinge', 'start'), {'start', 'end'}, 'door.hinge')
    walkway = _num(walkway_cm, 20, 300, 'walkway_cm')
    cell = _num(cell_cm, 2, 50, 'cell_cm')
    reach = _num(reach_cm, 0, 500, 'reach_cm')
    nx, ny = int(math.ceil(W / cell)), int(math.ceil(H / cell))
    if nx * ny > MAX_GRID_CELLS:
        raise ValueError(f'grid would have {nx * ny} cells; max {MAX_GRID_CELLS} (raise cell_cm)')
    if furniture is None:
        furniture = _DEFAULT_FURNITURE if (room_given is None and door_given is None) else []
    furn = []
    for i, f in enumerate(_list(furniture, 'furniture', 0, 40)):
        n = f'furniture[{i}]'
        _record(f, n, ('id', 'x', 'y', 'w', 'h'))
        furn.append({'id': _str(f['id'], f'{n}.id', 64), 'x': _num(f['x'], -W, 2 * W, f'{n}.x'),
                     'y': _num(f['y'], -H, 2 * H, f'{n}.y'), 'w': _num(f['w'], 0, W * 2, f'{n}.w', low_open=True),
                     'h': _num(f['h'], 0, H * 2, f'{n}.h', low_open=True)})
    _unique_ids(furn, 'furniture')
    zone_list = []
    if zones is not None:
        for i, z in enumerate(_list(zones, 'zones', 0, 40)):
            n = f'zones[{i}]'
            _record(z, n, ('id', 'x', 'y'))
            zone_list.append({'id': _str(z['id'], f'{n}.id', 64), 'x': _num(z['x'], 0, W, f'{n}.x'),
                              'y': _num(z['y'], 0, H, f'{n}.y')})
        _unique_ids(zone_list, 'zones')

    # door geometry
    if wall == 'bottom':
        p0, p1, inward = (doff, 0.0), (doff + dw, 0.0), (0.0, 1.0)
    elif wall == 'top':
        p0, p1, inward = (doff, H), (doff + dw, H), (0.0, -1.0)
    elif wall == 'left':
        p0, p1, inward = (0.0, doff), (0.0, doff + dw), (1.0, 0.0)
    else:
        p0, p1, inward = (W, doff), (W, doff + dw), (-1.0, 0.0)
    hp, other = (p0, p1) if hinge == 'start' else (p1, p0)
    along = ((other[0] - hp[0]) / dw, (other[1] - hp[1]) / dw)

    def in_swing(px, py):
        vx, vy = px - hp[0], py - hp[1]
        return (vx * vx + vy * vy <= dw * dw and vx * inward[0] + vy * inward[1] >= 0
                and vx * along[0] + vy * along[1] >= 0)

    segs = []
    corners = [(0.0, 0.0), (W, 0.0), (W, H), (0.0, H)]
    names = ['bottom', 'right', 'top', 'left']
    for k in range(4):
        a, b = corners[k], corners[(k + 1) % 4]
        if names[k] != wall:
            segs.append((a, b))
            continue
        # split the door wall around the opening (p0 -> p1 is ordered along increasing coordinate)
        lo, hi = (p0, p1)
        if wall in ('bottom', 'top'):
            segs += [((0.0, a[1]), (lo[0], a[1])), ((hi[0], a[1]), (W, a[1]))]
        else:
            segs += [((a[0], 0.0), (a[0], lo[1])), ((a[0], hi[1]), (a[0], H))]
    segs = [s for s in segs if s[0] != s[1]]

    issues = []
    overlaps = []
    for i in range(len(furn)):
        for j in range(i + 1, len(furn)):
            a, b = furn[i], furn[j]
            ox = min(a['x'] + a['w'], b['x'] + b['w']) - max(a['x'], b['x'])
            oy = min(a['y'] + a['h'], b['y'] + b['h']) - max(a['y'], b['y'])
            if ox > 1e-9 and oy > 1e-9:
                overlaps.append({'a': a['id'], 'b': b['id'], 'area_cm2': _r(ox * oy, 2)})
    for o in overlaps:
        issues.append({'rule': 'overlap', 'ids': [o['a'], o['b']], 'detail': f'{o["area_cm2"]} cm2 overlap'})
    outside = [f['id'] for f in furn if f['x'] < -1e-9 or f['y'] < -1e-9 or f['x'] + f['w'] > W + 1e-9
               or f['y'] + f['h'] > H + 1e-9]
    for fid in outside:
        issues.append({'rule': 'outside_room', 'ids': [fid], 'detail': 'furniture extends outside the room'})
    swing_blocked = []
    step = min(5.0, dw / 10)
    for f in furn:
        hit = False
        xs = max(f['x'], min(hp[0], other[0], hp[0] + inward[0] * dw) - 1)
        x_end = min(f['x'] + f['w'], max(hp[0], other[0], hp[0] + inward[0] * dw) + 1)
        ys0 = max(f['y'], min(hp[1], other[1], hp[1] + inward[1] * dw) - 1)
        y_end = min(f['y'] + f['h'], max(hp[1], other[1], hp[1] + inward[1] * dw) + 1)
        if xs <= x_end and ys0 <= y_end:
            nxs = min(81, int((x_end - xs) / step) + 2)
            nys = min(81, int((y_end - ys0) / step) + 2)
            for a in range(nxs):
                px = xs + (x_end - xs) * a / max(1, nxs - 1)
                for b in range(nys):
                    py = ys0 + (y_end - ys0) * b / max(1, nys - 1)
                    if in_swing(px, py):
                        hit = True
                        break
                if hit:
                    break
        if hit:
            swing_blocked.append(f['id'])
            issues.append({'rule': 'door_swing', 'ids': [f['id']], 'detail': 'inside the door swing area'})

    rad = walkway / 2.0
    free = [[False] * ny for _ in range(nx)]
    for i in range(nx):
        cx = (i + 0.5) * cell
        for j in range(ny):
            cy = (j + 0.5) * cell
            if cx > W or cy > H:
                continue
            ok = all(_rect_dist(cx, cy, f) >= rad - 1e-9 for f in furn)
            if ok:
                ok = all(_seg_dist(cx, cy, a[0], a[1], b[0], b[1]) >= rad - 1e-9 for a, b in segs)
            free[i][j] = ok
    dcx, dcy = (p0[0] + p1[0]) / 2 + inward[0] * cell / 2, (p0[1] + p1[1]) / 2 + inward[1] * cell / 2
    start = None
    best = None
    for i in range(nx):
        for j in range(ny):
            if free[i][j]:
                d = math.hypot((i + 0.5) * cell - dcx, (j + 0.5) * cell - dcy)
                if d <= 1.5 * cell and (best is None or d < best):
                    best, start = d, (i, j)
    seen = [[False] * ny for _ in range(nx)]
    reached = []
    if start is not None:
        queue = [start]
        seen[start[0]][start[1]] = True
        head = 0
        while head < len(queue):
            i, j = queue[head]
            head += 1
            reached.append(((i + 0.5) * cell, (j + 0.5) * cell))
            for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                a, b = i + di, j + dj
                if 0 <= a < nx and 0 <= b < ny and free[a][b] and not seen[a][b]:
                    seen[a][b] = True
                    queue.append((a, b))
    else:
        issues.append({'rule': 'door_entry_blocked', 'ids': [],
                       'detail': f'no walkable cell just inside the door (door {dw:g} cm vs walkway {walkway:g} cm)'})
    targets = zone_list if zone_list or zones is not None else [
        {'id': f['id'], 'rect': f} for f in furn]
    zone_report = []
    for z in targets:
        if 'rect' in z:
            dist = min((_rect_dist(px, py, z['rect']) for px, py in reached), default=None)
        else:
            dist = min((math.hypot(px - z['x'], py - z['y']) for px, py in reached), default=None)
        ok = dist is not None and dist <= reach + 1e-9
        zone_report.append({'id': z['id'], 'reachable': ok,
                            'nearest_walkway_cm': None if dist is None else _r(dist, 2)})
        if not ok:
            issues.append({'rule': 'blocked_path', 'ids': [z['id']],
                           'detail': f'no {walkway:g} cm walkway from the door reaches within {reach:g} cm'})
    total_free = sum(sum(1 for v in col if v) for col in free)
    result = {'ok': not issues, 'issues': issues, 'overlaps': overlaps, 'door_swing_blocked': swing_blocked,
              'outside_room': outside, 'zones': zone_report,
              'grid': {'cell_cm': cell, 'nx': nx, 'ny': ny, 'walkable_cells': total_free,
                       'reached_cells': len(reached), 'start_cell': None if start is None else list(start)},
              'door': {'wall': wall, 'hinge_point': [_r(hp[0], 2), _r(hp[1], 2)], 'width_cm': dw}}
    return _pack('interior_layout', result,
                 ['furniture as axis-aligned rectangles in cm; no rotation, heights or wall-mounted items',
                  'walkway = a disc of diameter walkway_cm moving on a grid (4-connected BFS); diagonal squeezes are not modelled',
                  'door swing = quarter disc of radius door width around the hinge, opening into the room'],
                 [f'grid <= {MAX_GRID_CELLS} cells, <= 40 furniture items and zones',
                  'grid resolution cell_cm can misjudge gaps within one cell; 80 cm is a common guideline, not a building code'])


# --------------------------------------------------------------------------- 13.09 horizon_fov

_DEFAULT_HORIZON_SHOTS = [
    {'id': 's1', 'horizon_y': 540.0, 'tilt_deg': 0.0},
    {'id': 's2', 'horizon_y': 545.0},
    {'id': 's3', 'horizon_y': 610.0},
]


def _project_y(height_m, dist, cam_h, tilt_deg, f, H):
    ang = math.atan2(height_m - cam_h, dist) - math.radians(tilt_deg)
    return H / 2 - f * math.tan(ang)


def horizon_fov(*, camera_height=1.6, tilt_deg=0.0, vfov_deg=40.0, frame_height=1080, frame_width=1920,
                distances=(5.0, 10.0, 20.0), person_height=1.70, shots=None, tolerance_px=10.0, **extra):
    """Horizon line and apparent person height for a level-ground pinhole camera.

    Focal length in pixels f = (H/2) / tan(vfov/2). With tilt t (positive =
    camera pitched up) the horizon lies at y = H/2 + f tan(t) from the top.
    A person standing at horizontal distance d projects from feet (z = 0) to
    head (z = person_height); at zero tilt the height is exactly
    f * person_height / d, so doubling d halves it. `shots` ({id, horizon_y,
    tilt_deg?, vfov_deg?, camera_height?}) are checked against the expected
    horizon when they state a tilt, and against the median horizon otherwise.
    """
    _no_extra(extra)
    cam_h = _num(camera_height, 0, 1000, 'camera_height', low_open=True)
    tilt = _num(tilt_deg, -80, 80, 'tilt_deg')
    vfov = _num(vfov_deg, 1, 170, 'vfov_deg')
    H = _int(frame_height, 16, 16384, 'frame_height')
    Wd = _int(frame_width, 16, 16384, 'frame_width')
    ph = _num(person_height, 0.1, 5, 'person_height')
    tol = _num(tolerance_px, 0, 1000, 'tolerance_px')
    dists = [_num(d, 0.05, 1e5, f'distances[{i}]') for i, d in
             enumerate(_list(distances, 'distances', 1, 64))]
    f = (H / 2) / math.tan(math.radians(vfov) / 2)
    hy = H / 2 + f * math.tan(math.radians(tilt))
    people = []
    for d in dists:
        y_feet = _project_y(0.0, d, cam_h, tilt, f, H)
        y_head = _project_y(ph, d, cam_h, tilt, f, H)
        people.append({'distance_m': d, 'feet_y': _r(y_feet, 3), 'head_y': _r(y_head, 3),
                       'height_px': _r(y_feet - y_head, 4), 'pinhole_height_px': _r(f * ph / d, 4),
                       'height_frac': _r((y_feet - y_head) / H, 6),
                       'feet_in_frame': 0 <= y_feet <= H, 'head_in_frame': 0 <= y_head <= H})
    shot_list = _list(shots if shots is not None else _DEFAULT_HORIZON_SHOTS, 'shots', 0, MAX_SHOTS)
    checked = []
    for i, s in enumerate(shot_list):
        n = f'shots[{i}]'
        _record(s, n, ('id', 'horizon_y'), ('tilt_deg', 'vfov_deg', 'camera_height'))
        item = {'id': _str(s['id'], f'{n}.id', 64), 'horizon_y': _num(s['horizon_y'], -1e5, 1e5, f'{n}.horizon_y')}
        if 'camera_height' in s:
            _num(s['camera_height'], 0, 1000, f'{n}.camera_height', low_open=True)
        if 'tilt_deg' in s:
            st = _num(s['tilt_deg'], -80, 80, f'{n}.tilt_deg')
            sv = _num(s.get('vfov_deg', vfov), 1, 170, f'{n}.vfov_deg')
            sf = (H / 2) / math.tan(math.radians(sv) / 2)
            item['expected_y'] = _r(H / 2 + sf * math.tan(math.radians(st)), 3)
        elif 'vfov_deg' in s:
            _num(s['vfov_deg'], 1, 170, f'{n}.vfov_deg')
        checked.append(item)
    _unique_ids(checked, 'shots')
    consistency = None
    if checked:
        ys = sorted(c['horizon_y'] for c in checked)
        m = len(ys)
        median = ys[m // 2] if m % 2 else (ys[m // 2 - 1] + ys[m // 2]) / 2
        for c in checked:
            c['deviation_from_median_px'] = _r(c['horizon_y'] - median, 3)
            if 'expected_y' in c:
                c['error_px'] = _r(c['horizon_y'] - c['expected_y'], 3)
                c['consistent'] = abs(c['horizon_y'] - c['expected_y']) <= tol
            else:
                c['consistent'] = abs(c['horizon_y'] - median) <= tol
        consistency = {'median_y': _r(median, 3), 'spread_px': _r(ys[-1] - ys[0], 3), 'tolerance_px': tol,
                       'all_consistent': all(c['consistent'] for c in checked),
                       'outliers': [c['id'] for c in checked if not c['consistent']]}
    result = {'focal_px': _r(f, 4), 'hfov_deg': _r(math.degrees(2 * math.atan((Wd / 2) / f)), 4),
              'horizon_y': _r(hy, 4), 'horizon_frac': _r(hy / H, 6),
              'horizon_in_frame': 0 <= hy <= H, 'people': people, 'shots': checked,
              'consistency': consistency,
              'note': 'eye-level rule: heads of people with eyes at camera height sit on the horizon line'}
    return _pack('horizon_fov', result,
                 ['ideal pinhole camera with square pixels, no lens distortion, principal point at frame centre',
                  'flat ground plane, no earth curvature or atmospheric refraction; no roll',
                  'shots without a stated tilt are compared to the median horizon of the set'],
                 ['tilt -80..80 deg, vfov 1-170 deg, <= 64 distances, <= 200 shots',
                  'height_px at non-zero tilt uses the exact projection; pinhole_height_px is the level-camera value'])


# --------------------------------------------------------------------------- 13.10 continuity_diff

_DEFAULT_BIBLE = {
    'characters': {
        'nour': {'outfit': 'red scarf, grey coat', 'props': ['notebook', 'umbrella']},
        'adam': {'outfit': 'blue shirt', 'props': ['camera']},
    },
    'locations': {'cafe': {'description': 'corner cafe, warm light', 'palette': ['#8a4b2a', '#e0b07a', '#2e2a26']}},
    'palette': ['#8a4b2a', '#e0b07a', '#2e2a26', '#c23b22'],
}
_DEFAULT_CONT_SHOTS = [
    {'id': '1A', 'scene': '1', 'location': 'cafe', 'palette': ['#8a4b2a', '#e0b07a', '#2e2a26'],
     'characters': {'nour': {'outfit': 'red scarf, grey coat', 'props': ['notebook', 'umbrella']},
                    'adam': {'outfit': 'blue shirt', 'props': ['camera']}}},
    {'id': '1B', 'scene': '1', 'location': 'cafe', 'palette': ['#8c4d2c', '#dfb27c', '#2e2a26'],
     'characters': {'nour': {'outfit': 'red scarf, grey coat', 'props': ['notebook']},
                    'adam': {'outfit': 'blue shirt', 'props': ['camera']}}},
]


def _parse_char(value, name):
    _record(value, name, (), ('outfit', 'props'))
    outfit = _str(value.get('outfit', ''), f'{name}.outfit', 300, allow_empty=True).strip()
    props = [_str(p, f'{name}.props[]', 100).strip() for p in _list(value.get('props', []), f'{name}.props', 0, 32)]
    return {'outfit': outfit, 'props': props}


def _parse_palette(value, name):
    return [_parse_hex(c, f'{name}[{i}]') for i, c in enumerate(_list(value, name, 1, 16))]


def _parse_chars(value, name):
    if not isinstance(value, dict) or len(value) > 32:
        raise ValueError(f'{name} must be a dict of at most 32 characters')
    return {_str(k, f'{name} key', 64): _parse_char(v, f'{name}.{k}') for k, v in value.items()}


def continuity_diff(*, bible=None, shots=None, palette_tolerance=10.0, **extra):
    """Compare per-shot descriptors to a style bible and to the previous shot.

    bible = {characters: {id: {outfit, props}}, locations: {id: {description?,
    palette?}}, palette: [hex]}; shots = [{id, scene, location?, palette?,
    characters: {id: {outfit, props}}}] in edit order. Against the bible:
    unknown characters/locations, outfit mismatch, bible props not seen.
    Between consecutive shots of the same scene: outfit changed, prop missing,
    prop added, character missing, location changed, palette drift (symmetric
    mean nearest-colour CIE76 delta-E > palette_tolerance).
    """
    _no_extra(extra)
    if shots is None and bible is not None:
        raise ValueError('shots are required when a bible is given')
    if shots is not None and bible is None:
        raise ValueError('bible is required when shots are given')
    bible = _record(bible if bible is not None else _DEFAULT_BIBLE, 'bible', ('characters',),
                    ('locations', 'palette'))
    chars = _parse_chars(bible['characters'], 'bible.characters')
    locs = {}
    lraw = bible.get('locations', {})
    if not isinstance(lraw, dict) or len(lraw) > 64:
        raise ValueError('bible.locations must be a dict of at most 64 locations')
    for k, v in lraw.items():
        _record(v, f'bible.locations.{k}', (), ('description', 'palette'))
        locs[_str(k, 'bible.locations key', 64)] = {
            'palette': _parse_palette(v['palette'], f'bible.locations.{k}.palette') if 'palette' in v else None}
        if 'description' in v:
            _str(v['description'], f'bible.locations.{k}.description', 500, allow_empty=True)
    bible_pal = _parse_palette(bible['palette'], 'bible.palette') if 'palette' in bible else None
    tol = _num(palette_tolerance, 0, 200, 'palette_tolerance')
    if shots is None:
        shots = _DEFAULT_CONT_SHOTS
    parsed = []
    for i, s in enumerate(_list(shots, 'shots', 1, MAX_SHOTS)):
        n = f'shots[{i}]'
        _record(s, n, ('id', 'scene', 'characters'), ('location', 'palette'))
        scene = s['scene']
        if isinstance(scene, int) and not isinstance(scene, bool):
            scene = str(scene)
        parsed.append({'id': _str(s['id'], f'{n}.id', 64), 'scene': _str(scene, f'{n}.scene', 64),
                       'location': _str(s['location'], f'{n}.location', 64) if 'location' in s else None,
                       'palette': _parse_palette(s['palette'], f'{n}.palette') if 'palette' in s else None,
                       'characters': _parse_chars(s['characters'], f'{n}.characters')})
    _unique_ids(parsed, 'shots')
    vs_bible, between = [], []
    for s in parsed:
        for cid, c in s['characters'].items():
            if cid not in chars:
                vs_bible.append({'shot': s['id'], 'type': 'unknown_character', 'character': cid})
                continue
            b = chars[cid]
            if b['outfit'] and c['outfit'] and c['outfit'].casefold() != b['outfit'].casefold():
                vs_bible.append({'shot': s['id'], 'type': 'outfit_mismatch', 'character': cid,
                                 'expected': b['outfit'], 'found': c['outfit']})
            have = {p.casefold() for p in c['props']}
            for p in b['props']:
                if p.casefold() not in have:
                    vs_bible.append({'shot': s['id'], 'type': 'bible_prop_not_seen', 'character': cid, 'prop': p})
        if s['location'] is not None and locs and s['location'] not in locs:
            vs_bible.append({'shot': s['id'], 'type': 'unknown_location', 'location': s['location']})
        ref_pal = None
        if s['location'] in locs and locs[s['location']]['palette']:
            ref_pal = locs[s['location']]['palette']
        elif bible_pal:
            ref_pal = bible_pal
        if s['palette'] and ref_pal:
            d = _palette_drift(s['palette'], ref_pal)
            if d > tol:
                vs_bible.append({'shot': s['id'], 'type': 'palette_off_bible', 'delta_e': _r(d, 3)})
    for prev, cur in zip(parsed, parsed[1:]):
        if prev['scene'] != cur['scene']:
            continue
        pair = {'from': prev['id'], 'to': cur['id'], 'scene': cur['scene']}
        if prev['location'] and cur['location'] and prev['location'] != cur['location']:
            between.append(dict(pair, type='location_changed', before=prev['location'], after=cur['location']))
        for cid, pc in prev['characters'].items():
            if cid not in cur['characters']:
                between.append(dict(pair, type='character_missing', character=cid))
                continue
            cc = cur['characters'][cid]
            if pc['outfit'].casefold() != cc['outfit'].casefold():
                between.append(dict(pair, type='outfit_changed', character=cid, before=pc['outfit'],
                                    after=cc['outfit']))
            now = {p.casefold() for p in cc['props']}
            was = {p.casefold() for p in pc['props']}
            for p in pc['props']:
                if p.casefold() not in now:
                    between.append(dict(pair, type='prop_missing', character=cid, prop=p))
            for p in cc['props']:
                if p.casefold() not in was:
                    between.append(dict(pair, type='prop_added', character=cid, prop=p))
        for cid in cur['characters']:
            if cid not in prev['characters']:
                between.append(dict(pair, type='character_entered', character=cid))
        if prev['palette'] and cur['palette']:
            d = _palette_drift(prev['palette'], cur['palette'])
            if d > tol:
                between.append(dict(pair, type='palette_drift', delta_e=_r(d, 3)))
    errors = {'outfit_changed', 'prop_missing', 'location_changed', 'palette_drift'}
    result = {'shots_checked': len(parsed), 'vs_bible': vs_bible, 'between_shots': between,
              'error_count': sum(1 for d in between if d['type'] in errors),
              'ok': not vs_bible and not any(d['type'] in errors for d in between)}
    return _pack('continuity_diff', result,
                 ['descriptors are text labels supplied per shot; no image analysis is done',
                  'outfits and props compared case-insensitively as exact labels (no synonyms)',
                  'palette drift = symmetric mean nearest-colour CIE76 delta-E (D65, sRGB); ~2.3 is a just-noticeable difference'],
                 [f'<= {MAX_SHOTS} shots, <= 32 characters and 32 props each, <= 16 palette colours',
                  'only consecutive shots of the same scene are compared to each other'])


# --------------------------------------------------------------------------- dispatcher

OPS = {
    'frame_composition': frame_composition, 'landscape_layers': landscape_layers,
    'three_point_light': three_point_light, 'palette_harmony': palette_harmony,
    'arabic_text_layout': arabic_text_layout, 'logo_marks': logo_marks,
    'poster_hierarchy': poster_hierarchy, 'interior_layout': interior_layout,
    'horizon_fov': horizon_fov, 'continuity_diff': continuity_diff,
}


def run(op, params=None):
    """Validate and dispatch: run('palette_harmony', {'base': '#c23b22'}) -> {'op','result','assumptions','limits'}."""
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
