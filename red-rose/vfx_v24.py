"""Red Rose V24: small, bounded, deterministic VFX helpers (topics 17.01-17.10).

Pure standard-library Python. No file I/O, no subprocess, no network, no printing.
Every op validates its inputs strictly (ValueError on bools-as-numbers,
non-finite values, unknown parameter names and out-of-range values) and caps
its work (pixels, frames, particles, iterations) so it cannot run away.
Images are nested lists (rows of columns), at most 128 x 128: grayscale
pixels are floats in [0, 1], RGB pixels are [r, g, b] lists of floats in [0, 1].
Pixel (x, y) is column x, row y; y grows downward unless an op says otherwise.

Owner policy: effects (bloom, glow, fog, haze, rain, snow, sparks, overlays,
composites, removals) are applied to real footage only when the owner
explicitly asks for them by name. Every op takes `source` ('synthetic', 'cg'
or 'footage') and `requested_by_owner`; with source='footage' the op refuses
(ValueError) unless requested_by_owner=True. Object removal (inpaint_mask)
additionally needs owner_confirms_rights=True on footage.

These are previz/teaching-grade models, not a compositor: each op returns the
assumptions it makes and the limits it enforces next to its result. Every op
works with an empty params dict (a tiny built-in synthetic example), so
`run(op, {})` always demonstrates the method.
"""
from __future__ import annotations

import json
import math
import random

MAX_PARAMS = 24
MAX_SIDE = 128
MAX_FRAMES = 300

TOPICS = {
    '17.01': 'track_point',
    '17.02': 'rain_light',
    '17.03': 'cast_shadow',
    '17.04': 'heat_haze',
    '17.05': 'neon_bloom',
    '17.06': 'snow_vortex',
    '17.07': 'alpha_composite',
    '17.08': 'parallax_layers',
    '17.09': 'inpaint_mask',
    '17.10': 'sparks',
}

TOPIC_NAMES_AR = {
    '17.01': 'تتبع عنصر لإضافة تأثير',
    '17.02': 'إضافة مطر متفاعل مع الضوء',
    '17.03': 'ظلال واقعية للأجسام',
    '17.04': 'تشويه حراري خفيف',
    '17.05': 'إضاءة نيون متحركة',
    '17.06': 'جزيئات الثلج والإعصار',
    '17.07': 'دمج عنصر فوق فيديو',
    '17.08': 'تصميم انتقالات ثلاثية العمق',
    '17.09': 'إزالة عنصر مرخص من فيديو المستخدم',
    '17.10': 'توليد شرارات آمنة',
}

POLICY = ('owner policy: effects (bloom, glow, fog, haze, rain, snow, sparks, overlays, '
          'composites, removals) touch real footage (source="footage") only when the owner '
          'explicitly requests them by name (requested_by_owner=True); otherwise the op refuses')


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


def _vec(value, size, name, low=-1e6, high=1e6):
    if not isinstance(value, (list, tuple)) or len(value) != size:
        raise ValueError(f'{name} must be a list of {size} numbers')
    return [_num(v, low, high, f'{name}[{i}]') for i, v in enumerate(value)]


def _gate(source, requested_by_owner, effect):
    source = _choice(source, {'synthetic', 'cg', 'footage'}, 'source')
    requested_by_owner = _bool(requested_by_owner, 'requested_by_owner')
    if source == 'footage' and not requested_by_owner:
        raise ValueError(f'refused: {effect} on real footage needs requested_by_owner=True '
                         '(the owner must ask for this effect by name)')
    return source


def _gray(img, name, min_side=1):
    if not isinstance(img, (list, tuple)) or not min_side <= len(img) <= MAX_SIDE:
        raise ValueError(f'{name} must be a list of {min_side}..{MAX_SIDE} rows')
    width = None
    out = []
    for y, row in enumerate(img):
        if not isinstance(row, (list, tuple)) or not min_side <= len(row) <= MAX_SIDE:
            raise ValueError(f'{name}[{y}] must be a list of {min_side}..{MAX_SIDE} pixels')
        if width is None:
            width = len(row)
        elif len(row) != width:
            raise ValueError(f'{name} rows must all have the same width')
        out.append([_num(v, 0, 1, f'{name}[{y}][{x}]') for x, v in enumerate(row)])
    return out


def _rgb(img, name):
    if not isinstance(img, (list, tuple)) or not 1 <= len(img) <= MAX_SIDE:
        raise ValueError(f'{name} must be a list of 1..{MAX_SIDE} rows')
    width = None
    planes = [[], [], []]
    for y, row in enumerate(img):
        if not isinstance(row, (list, tuple)) or not 1 <= len(row) <= MAX_SIDE:
            raise ValueError(f'{name}[{y}] must be a list of 1..{MAX_SIDE} pixels')
        if width is None:
            width = len(row)
        elif len(row) != width:
            raise ValueError(f'{name} rows must all have the same width')
        rows = [[], [], []]
        for x, px in enumerate(row):
            c = _vec(px, 3, f'{name}[{y}][{x}]', 0, 1)
            for k in range(3):
                rows[k].append(c[k])
        for k in range(3):
            planes[k].append(rows[k])
    return planes


def _planes(img, name):
    """Gray or RGB image -> (list of planes, kind)."""
    if (isinstance(img, (list, tuple)) and img and isinstance(img[0], (list, tuple))
            and img[0] and isinstance(img[0][0], (list, tuple))):
        return _rgb(img, name), 'rgb'
    return [_gray(img, name)], 'gray'


def _from_planes(planes, kind):
    if kind == 'gray':
        return [[round(v, 6) for v in row] for row in planes[0]]
    h, w = len(planes[0]), len(planes[0][0])
    return [[[round(planes[k][y][x], 6) for k in range(3)] for x in range(w)] for y in range(h)]


def _pack(op, result, assumptions, limits):
    return {'op': op, 'result': result, 'assumptions': list(assumptions),
            'limits': list(limits) + [POLICY]}


def _clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


def _bilinear(plane, x, y, outside=None):
    """Sample a plane at float (x, y). outside=None clamps to edge, else returns it."""
    h, w = len(plane), len(plane[0])
    if outside is not None and (x < -1 or y < -1 or x > w or y > h):
        return outside
    x0, y0 = math.floor(x), math.floor(y)
    fx, fy = x - x0, y - y0

    def px(ix, iy):
        if 0 <= ix < w and 0 <= iy < h:
            return plane[iy][ix]
        if outside is not None:
            return outside
        return plane[_clamp(iy, 0, h - 1)][_clamp(ix, 0, w - 1)]

    a = px(x0, y0) * (1 - fx) + px(x0 + 1, y0) * fx
    b = px(x0, y0 + 1) * (1 - fx) + px(x0 + 1, y0 + 1) * fx
    return a * (1 - fy) + b * fy


# --------------------------------------------------------------------------- 17.01 track_point

def _soft_square(w, h, cx, cy, half, bg=0.1, fg=0.9):
    img = []
    for y in range(h):
        cov_y = _clamp(half + 0.5 - abs(y - cy), 0.0, 1.0)
        img.append([bg + (fg - bg) * cov_y * _clamp(half + 0.5 - abs(x - cx), 0.0, 1.0)
                    for x in range(w)])
    return img


def track_point(*, frames=None, start=None, ground_truth=None, patch_radius=4,
                search_radius=4, refine=True, source='synthetic', requested_by_owner=False,
                **extra):
    """Track a small patch through grayscale frames.

    The template is the (2r+1)^2 patch of frame 0 centred on `start` (rounded to
    the nearest pixel). In every later frame the integer position minimising the
    sum of squared differences (SSD) inside a +/- search_radius window around the
    previous (rounded) position wins; with refine=True one Lucas-Kanade step
    (gradient least squares, |step| <= 1 px) adds a sub-pixel correction.
    Reports per-frame [x, y] and, when ground_truth is given, per-frame error and
    drift. Default: a 32x32 soft-edged square moving +1 px/frame in x for 10 frames.
    """
    _no_extra(extra)
    _gate(source, requested_by_owner, 'tracking for an effect')
    r = _int(patch_radius, 1, 8, 'patch_radius')
    s = _int(search_radius, 1, 16, 'search_radius')
    refine = _bool(refine, 'refine')
    if frames is None:
        if start is not None or ground_truth is not None:
            raise ValueError('start/ground_truth given without frames')
        frames = [_soft_square(32, 32, 8 + k, 14, 3) for k in range(10)]
        start = [8, 14]
        ground_truth = [[8 + k, 14] for k in range(10)]
    if not isinstance(frames, (list, tuple)) or not 2 <= len(frames) <= MAX_FRAMES:
        raise ValueError(f'frames must be a list of 2..{MAX_FRAMES} grayscale images')
    imgs = [_gray(f, f'frames[{i}]', min_side=3) for i, f in enumerate(frames)]
    h, w = len(imgs[0]), len(imgs[0][0])
    if any(len(im) != h or len(im[0]) != w for im in imgs):
        raise ValueError('all frames must have the same size')
    if start is None:
        raise ValueError('start [x, y] is required when frames are given')
    sx, sy = _vec(start, 2, 'start', 0, MAX_SIDE)
    cx, cy = round(sx), round(sy)
    if not (r <= cx <= w - 1 - r and r <= cy <= h - 1 - r):
        raise ValueError('the template around start must fit inside the frame')
    truth = None
    if ground_truth is not None:
        if not isinstance(ground_truth, (list, tuple)) or len(ground_truth) != len(imgs):
            raise ValueError('ground_truth must have one [x, y] per frame')
        truth = [_vec(p, 2, f'ground_truth[{i}]', -1e4, 1e4) for i, p in enumerate(ground_truth)]
    work = (len(imgs) - 1) * (2 * s + 1) ** 2 * (2 * r + 1) ** 2
    if work > 3_000_000:
        raise ValueError('frames * window * patch work must be <= 3000000')

    offs = [(i, j) for j in range(-r, r + 1) for i in range(-r, r + 1)]
    f0 = imgs[0]
    tmpl = [f0[cy + j][cx + i] for i, j in offs]
    positions = [[float(cx), float(cy)]]
    ssd_scores = [0.0]
    lk_used = 0
    px, py = cx, cy
    for im in imgs[1:]:
        best = None
        for qy in range(max(r, py - s), min(h - 1 - r, py + s) + 1):
            for qx in range(max(r, px - s), min(w - 1 - r, px + s) + 1):
                ssd = 0.0
                for (i, j), t in zip(offs, tmpl):
                    d = im[qy + j][qx + i] - t
                    ssd += d * d
                if best is None or ssd < best[0] - 1e-12:
                    best = (ssd, qx, qy)
        if best is None:
            raise ValueError('search window left the frame')
        ssd, qx, qy = best
        fx, fy = float(qx), float(qy)
        if refine and r + 1 <= qx <= w - 2 - r and r + 1 <= qy <= h - 2 - r:
            gxx = gxy = gyy = bx = by = 0.0
            for (i, j), t in zip(offs, tmpl):
                x, y = qx + i, qy + j
                ix = (im[y][x + 1] - im[y][x - 1]) / 2
                iy = (im[y + 1][x] - im[y - 1][x]) / 2
                e = im[y][x] - t
                gxx += ix * ix
                gxy += ix * iy
                gyy += iy * iy
                bx -= ix * e
                by -= iy * e
            det = gxx * gyy - gxy * gxy
            if det > 1e-9:
                dx = (gyy * bx - gxy * by) / det
                dy = (gxx * by - gxy * bx) / det
                if abs(dx) <= 1 and abs(dy) <= 1:
                    fx, fy = qx + dx, qy + dy
                    lk_used += 1
        positions.append([round(fx, 6), round(fy, 6)])
        ssd_scores.append(round(ssd, 6))
        px, py = round(fx), round(fy)
    result = {'positions': positions, 'ssd': ssd_scores, 'lk_refined_frames': lk_used,
              'patch_radius': r, 'search_radius': s}
    if truth is not None:
        errs = [math.dist(p, t) for p, t in zip(positions, truth)]
        result.update({'errors': [round(e, 6) for e in errs], 'max_error': max(errs),
                       'mean_error': sum(errs) / len(errs), 'drift': errs[-1]})
    return _pack('track_point', result,
                 ['translation-only motion of a rigid patch; no rotation, scale or lighting change',
                  'template fixed from frame 0 (no template update), so appearance change causes drift',
                  'one Lucas-Kanade step with central-difference gradients; refinement skipped near borders',
                  'positions are patch centres in pixel coordinates (x = column, y = row)'],
                 [f'frames <= {MAX_FRAMES}, images <= {MAX_SIDE}x{MAX_SIDE}, patch_radius <= 8, search_radius <= 16',
                  'work (frames x window x patch) <= 3000000; motion faster than search_radius per frame is lost'])


# --------------------------------------------------------------------------- 17.02 rain_light

def rain_light(*, width=64, height=64, count=120, frames=24, fps=24.0, seed=0,
               wind=60.0, fall_speed=400.0, speed_jitter=0.1, exposure=0.5,
               light_pos=(8.0, -10.0), light_dir=(1.0, 1.5), light_half_angle_deg=15.0,
               light_gain=0.6, base_min=0.25, base_max=0.45,
               source='synthetic', requested_by_owner=False, **extra):
    """Seeded rain streaks lit by a directional light cone (2D screen space).

    Every drop falls with velocity (wind, fall_speed) * (1 + jitter_i), so all
    drops share one fall direction: angle = atan2(wind, fall_speed) from vertical
    (positive toward +x). A streak spans the distance travelled during the
    shutter (exposure * |v| / fps). Drops leaving the frame wrap to the top/side.
    Streaks whose midpoint is inside the cone (apex light_pos, axis light_dir,
    half-angle) get brightness base + light_gain * (1 - base). Every frame lists
    [x_head, y_head, x_tail, y_tail, brightness, lit].
    """
    _no_extra(extra)
    _gate(source, requested_by_owner, 'rain')
    width = _int(width, 4, 1024, 'width')
    height = _int(height, 4, 1024, 'height')
    count = _int(count, 1, 500, 'count')
    frames = _int(frames, 1, MAX_FRAMES, 'frames')
    if count * frames > 30_000:
        raise ValueError('count * frames must be <= 30000')
    fps = _num(fps, 1, 120, 'fps')
    seed = _int(seed, 0, 2**31 - 1, 'seed')
    wind = _num(wind, -2000, 2000, 'wind')
    fall_speed = _num(fall_speed, 1, 5000, 'fall_speed')
    speed_jitter = _num(speed_jitter, 0, 0.5, 'speed_jitter')
    exposure = _num(exposure, 0.01, 1, 'exposure')
    lpos = _vec(light_pos, 2, 'light_pos', -1e4, 1e4)
    ldir = _vec(light_dir, 2, 'light_dir', -1e4, 1e4)
    ln = math.hypot(*ldir)
    if ln < 1e-12:
        raise ValueError('light_dir must not be the zero vector')
    ldir = [ldir[0] / ln, ldir[1] / ln]
    half = _num(light_half_angle_deg, 0.5, 89, 'light_half_angle_deg')
    gain = _num(light_gain, 0, 1, 'light_gain', low_open=True)
    bmin = _num(base_min, 0, 0.99, 'base_min')
    bmax = _num(base_max, 0, 0.99, 'base_max')
    if bmin > bmax:
        raise ValueError('base_min must be <= base_max')

    angle = math.degrees(math.atan2(wind, fall_speed))
    cos_half = math.cos(math.radians(half))
    rng = random.Random(seed)
    drops = []
    for _ in range(count):
        k = 1 + rng.uniform(-speed_jitter, speed_jitter)
        drops.append({'x': rng.uniform(0, width), 'y': rng.uniform(0, height),
                      'vx': wind * k, 'vy': fall_speed * k, 'base': rng.uniform(bmin, bmax)})
    out_frames, angle_err, lit_b, unlit_b = [], 0.0, [], []
    for f in range(frames):
        streaks = []
        for d in drops:
            if f:
                d['x'] = (d['x'] + d['vx'] / fps) % width
                d['y'] += d['vy'] / fps
                if d['y'] > height:
                    d['y'] %= height
            tx = d['x'] - d['vx'] * exposure / fps
            ty = d['y'] - d['vy'] * exposure / fps
            a = math.degrees(math.atan2(d['x'] - tx, d['y'] - ty))
            angle_err = max(angle_err, abs(a - angle))
            mx, my = (d['x'] + tx) / 2 - lpos[0], (d['y'] + ty) / 2 - lpos[1]
            mn = math.hypot(mx, my)
            lit = mn > 1e-9 and (mx * ldir[0] + my * ldir[1]) / mn >= cos_half
            b = d['base'] + gain * (1 - d['base']) if lit else d['base']
            (lit_b if lit else unlit_b).append(b)
            streaks.append([round(d['x'], 4), round(d['y'], 4), round(tx, 4), round(ty, 4),
                            round(b, 6), lit])
        out_frames.append(streaks)
    result = {'frames': out_frames, 'fall_angle_deg': angle, 'max_angle_error_deg': angle_err,
              'streak_length_px': [round(math.hypot(wind, fall_speed) * (1 + j * speed_jitter)
                                         * exposure / fps, 6) for j in (-1, 1)],
              'lit_streaks': len(lit_b), 'unlit_streaks': len(unlit_b),
              'min_lit_brightness': min(lit_b) if lit_b else None,
              'max_unlit_brightness': max(unlit_b) if unlit_b else None,
              'width': width, 'height': height, 'fps': fps, 'seed': seed}
    return _pack('rain_light', result,
                 ['drops already at terminal velocity: constant (wind, fall_speed) per drop, one shared direction',
                  'streak = straight segment covered during the shutter; no lens or depth-of-field model',
                  'light cone tested at the streak midpoint; inside brightness is a fixed gain, no falloff with distance',
                  'drops wrap at the frame edges (rain is a continuous curtain), deterministic for a seed'],
                 ['count <= 500, frames <= 300, count * frames <= 30000, width/height <= 1024',
                  'returns streak geometry only; rasterising and compositing onto a plate is a separate step'])


# --------------------------------------------------------------------------- 17.03 cast_shadow

def _hull(points):
    pts = sorted(set((round(x, 9), round(y, 9)) for x, y in points))
    if len(pts) <= 2:
        return [list(p) for p in pts]

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower, upper = [], []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return [list(p) for p in lower[:-1] + upper[:-1]]


def _inside_convex(poly, p, eps=1e-9):
    if len(poly) < 3:
        return False
    for i in range(len(poly)):
        a, b = poly[i], poly[(i + 1) % len(poly)]
        if (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0]) < -eps:
            return False
    return True


def cast_shadow(*, footprint=None, height=3.0, light_azimuth_deg=45.0, light_elevation_deg=30.0,
                ground_queries=None, depth_map=None, depth_queries=None, bias=0.05,
                source='synthetic', requested_by_owner=False, **extra):
    """Shadow of a 2.5D prism on the ground plane from a directional light.

    footprint: convex-or-not polygon [[x, y], ...] on the ground (z = 0), extruded
    to `height`. The light comes FROM azimuth (degrees CCW from +x on the ground)
    at elevation above the horizon; a point at height z is projected to the
    ground at offset -z / tan(elevation) * (cos az, sin az). The shadow polygon is
    the convex hull of the footprint and its projected top. ground_queries are
    tested against that hull. Optional shadow-map test: a query [u, v, depth] is
    in shadow when depth > depth_map[v][u] + bias (depth measured from the light).
    """
    _no_extra(extra)
    _gate(source, requested_by_owner, 'cast shadows')
    if footprint is None:
        footprint = [[0, 0], [2, 0], [2, 2], [0, 2]]
    if not isinstance(footprint, (list, tuple)) or not 1 <= len(footprint) <= 64:
        raise ValueError('footprint must be a list of 1..64 [x, y] points')
    fp = [_vec(p, 2, f'footprint[{i}]', -1e4, 1e4) for i, p in enumerate(footprint)]
    height = _num(height, 0, 1e4, 'height')
    az = _num(light_azimuth_deg, -360, 360, 'light_azimuth_deg')
    el = _num(light_elevation_deg, 1, 89, 'light_elevation_deg')
    bias = _num(bias, 0, 1e3, 'bias')
    length = height / math.tan(math.radians(el))
    off = [-length * math.cos(math.radians(az)), -length * math.sin(math.radians(az))]
    hull = _hull(fp + [[x + off[0], y + off[1]] for x, y in fp])
    shadow_dir = math.degrees(math.atan2(off[1], off[0])) % 360 if length > 0 else None
    opposite_err = None
    if shadow_dir is not None:
        diff = (shadow_dir - (az % 360) - 180) % 360
        opposite_err = min(diff, 360 - diff)
    cxy = [sum(p[0] for p in fp) / len(fp), sum(p[1] for p in fp) / len(fp)]
    if ground_queries is None:
        reach = max(math.dist(cxy, p) for p in fp) + 1.0  # beyond the footprint, toward the light
        ground_queries = [[cxy[0] + 0.9 * off[0], cxy[1] + 0.9 * off[1]],
                          [cxy[0] + reach * math.cos(math.radians(az)),
                           cxy[1] + reach * math.sin(math.radians(az))]]
    if not isinstance(ground_queries, (list, tuple)) or len(ground_queries) > 256:
        raise ValueError('ground_queries must be a list of at most 256 [x, y] points')
    gq = [_vec(p, 2, f'ground_queries[{i}]', -1e5, 1e5) for i, p in enumerate(ground_queries)]
    ground = [{'point': p, 'in_shadow': _inside_convex(hull, p)} for p in gq]

    if depth_map is None:
        if depth_queries is not None:
            raise ValueError('depth_queries need a depth_map')
        depth_map = [[0.2 if 6 <= x <= 9 and 6 <= y <= 9 else 1.0 for x in range(16)]
                     for y in range(16)]
        depth_queries = [[7, 7, 0.5], [2, 2, 0.5], [7, 7, 0.15], [2, 2, 1.0]]
    dm = _gray(depth_map, 'depth_map')
    if depth_queries is None:
        depth_queries = []
    if not isinstance(depth_queries, (list, tuple)) or len(depth_queries) > 256:
        raise ValueError('depth_queries must be a list of at most 256 [u, v, depth]')
    depth_out = []
    for i, q in enumerate(depth_queries):
        if not isinstance(q, (list, tuple)) or len(q) != 3:
            raise ValueError(f'depth_queries[{i}] must be [u, v, depth]')
        u = _int(q[0], 0, len(dm[0]) - 1, f'depth_queries[{i}][0]')
        v = _int(q[1], 0, len(dm) - 1, f'depth_queries[{i}][1]')
        d = _num(q[2], 0, 1, f'depth_queries[{i}][2]')
        depth_out.append({'uv': [u, v], 'depth': d, 'map_depth': dm[v][u],
                          'in_shadow': d > dm[v][u] + bias})
    result = {'shadow_polygon': [[round(x, 6), round(y, 6)] for x, y in hull],
              'shadow_offset': [round(off[0], 6), round(off[1], 6)],
              'shadow_length': length, 'shadow_direction_deg': shadow_dir,
              'light_azimuth_deg': az % 360, 'opposite_error_deg': opposite_err,
              'ground_queries': ground, 'depth_queries': depth_out, 'bias': bias}
    return _pack('cast_shadow', result,
                 ['directional (sun-like) light: parallel rays, hard shadow edge (no penumbra)',
                  'flat ground plane at z = 0; object is a vertical prism over its footprint',
                  'shadow polygon is the convex hull of footprint and projected top (exact for convex footprints)',
                  'depth-map test uses normalised light-space depths in [0, 1] and a constant bias against acne'],
                 ['footprint <= 64 points, queries <= 256 each, depth map <= 128x128',
                  'light elevation in [1, 89] degrees; no contact-shadow softening or ambient occlusion'])


# --------------------------------------------------------------------------- 17.04 heat_haze

_MASK64 = 0xFFFFFFFFFFFFFFFF


def _hash01(seed, ix, iy, ch):
    z = (seed * 0x9E3779B97F4A7C15 + ix * 0xBF58476D1CE4E5B9 + iy * 0x94D049BB133111EB
         + ch * 0xD6E8FEB86659FD93 + 0x632BE59BD9B4E019) & _MASK64
    z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & _MASK64
    z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & _MASK64
    z ^= z >> 31
    return z / 2.0**64


def _value_noise(seed, x, y, ch):
    ix, iy = math.floor(x), math.floor(y)
    fx, fy = x - ix, y - iy
    sx, sy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
    a = _hash01(seed, ix, iy, ch)
    b = _hash01(seed, ix + 1, iy, ch)
    c = _hash01(seed, ix, iy + 1, ch)
    d = _hash01(seed, ix + 1, iy + 1, ch)
    return (a + (b - a) * sx) * (1 - sy) + (c + (d - c) * sx) * sy


def _boxes(boxes, w, h, name):
    if not isinstance(boxes, (list, tuple)) or len(boxes) > 32:
        raise ValueError(f'{name} must be a list of at most 32 [x0, y0, x1, y1] boxes')
    out = []
    for i, b in enumerate(boxes):
        if not isinstance(b, (list, tuple)) or len(b) != 4:
            raise ValueError(f'{name}[{i}] must be [x0, y0, x1, y1]')
        x0 = _int(b[0], 0, w - 1, f'{name}[{i}][0]')
        y0 = _int(b[1], 0, h - 1, f'{name}[{i}][1]')
        x1 = _int(b[2], x0 + 1, w, f'{name}[{i}][2]')
        y1 = _int(b[3], y0 + 1, h, f'{name}[{i}][3]')
        out.append([x0, y0, x1, y1])
    return out


def heat_haze(*, image=None, heat_mask=None, protected_boxes=None, amplitude=1.5, scale=8.0,
              t=0.0, rise_speed=6.0, seed=0, source='synthetic', requested_by_owner=False,
              **extra):
    """Subtle heat-shimmer displacement field and the warped image.

    Two seeded smooth value-noise fields (lattice spacing `scale` px, smoothstep
    interpolation, sampled at y + t * rise_speed so the shimmer rises) give a
    vector of length <= 1, scaled by amplitude * heat_mask. Pixels inside
    protected_boxes ([x0, y0, x1, y1), e.g. titles) get exactly zero
    displacement, so they are copied unchanged. The image (gray or RGB) is
    warped by bilinear sampling at (x + dx, y + dy). Default: a 32x32
    checker-gradient plate, heat rising from the bottom, one protected text box.
    """
    _no_extra(extra)
    _gate(source, requested_by_owner, 'heat haze')
    if image is None:
        image = [[round(0.2 + 0.5 * x / 31 + (0.15 if (x // 4 + y // 4) % 2 else 0.0), 6)
                  for x in range(32)] for y in range(32)]
        if protected_boxes is None:
            protected_boxes = [[4, 4, 20, 10]]
    planes, kind = _planes(image, 'image')
    h, w = len(planes[0]), len(planes[0][0])
    if heat_mask is None:
        mask = [[y / (h - 1) if h > 1 else 1.0] * w for y in range(h)]
    else:
        mask = _gray(heat_mask, 'heat_mask')
        if len(mask) != h or len(mask[0]) != w:
            raise ValueError('heat_mask must match the image size')
    boxes = _boxes(protected_boxes or [], w, h, 'protected_boxes')
    amp = _num(amplitude, 0, 8, 'amplitude')
    scale = _num(scale, 2, 64, 'scale')
    t = _num(t, 0, 3600, 't')
    rise = _num(rise_speed, -100, 100, 'rise_speed')
    seed = _int(seed, 0, 2**31 - 1, 'seed')
    protected = [[False] * w for _ in range(h)]
    for x0, y0, x1, y1 in boxes:
        for y in range(y0, y1):
            for x in range(x0, x1):
                protected[y][x] = True
    dxf, dyf = [], []
    max_in = max_out = 0.0
    for y in range(h):
        rx, ry = [], []
        for x in range(w):
            if protected[y][x]:
                dx = dy = 0.0
            else:
                u, v = x / scale, (y + t * rise) / scale
                nx = 2 * _value_noise(seed, u, v, 0) - 1
                ny = 2 * _value_noise(seed, u, v, 1) - 1
                n = math.hypot(nx, ny)
                if n > 1:
                    nx, ny = nx / n, ny / n
                k = amp * mask[y][x]
                dx, dy = k * nx, k * ny
            mag = math.hypot(dx, dy)
            if protected[y][x]:
                max_in = max(max_in, mag)
            else:
                max_out = max(max_out, mag)
            rx.append(dx)
            ry.append(dy)
        dxf.append(rx)
        dyf.append(ry)
    warped = [[[_bilinear(p, x + dxf[y][x], y + dyf[y][x]) for x in range(w)] for y in range(h)]
              for p in planes]
    result = {'image': _from_planes(warped, kind),
              'dx': [[round(v, 6) for v in row] for row in dxf],
              'dy': [[round(v, 6) for v in row] for row in dyf],
              'max_displacement_protected': max_in, 'max_displacement_outside': max_out,
              'amplitude': amp, 'protected_boxes': boxes, 'width': w, 'height': h}
    return _pack('heat_haze', result,
                 ['smooth seeded value noise, not a refraction simulation of real air',
                  'displacement length <= amplitude * heat_mask; zero inside protected boxes (hard edge)',
                  'bilinear resampling with clamp-to-edge; animate by changing t'],
                 [f'images <= {MAX_SIDE}x{MAX_SIDE}, amplitude <= 8 px, scale 2..64 px, <= 32 protected boxes',
                  'pixels just outside a protected box may sample from inside it (text stays sharp, not its halo)'])


# --------------------------------------------------------------------------- 17.05 neon_bloom

def _gauss_blur(plane, sigma):
    r = max(1, math.ceil(3 * sigma))
    k = [math.exp(-(i * i) / (2 * sigma * sigma)) for i in range(-r, r + 1)]
    s = sum(k)
    k = [v / s for v in k]
    h, w = len(plane), len(plane[0])
    tmp = [[sum(k[i + r] * row[_clamp(x + i, 0, w - 1)] for i in range(-r, r + 1))
            for x in range(w)] for row in plane]
    return [[sum(k[i + r] * tmp[_clamp(y + i, 0, h - 1)][x] for i in range(-r, r + 1))
             for x in range(w)] for y in range(h)]


def neon_bloom(*, image=None, threshold=0.7, knee=0.1, sigma=1.5, intensity=0.6,
               flicker_hz=2.0, flicker_depth=0.2, fps=24.0, frames=24, frame=0, seed=0,
               source='synthetic', requested_by_owner=False, **extra):
    """Limited neon bloom with a flicker schedule; output never exceeds 1.0.

    bright = max(x - threshold, soft) with the quadratic soft knee
    soft = clamp(x - threshold + knee, 0, 2 knee)^2 / (4 knee); bright is blurred
    by a separable Gaussian and scaled by intensity * flicker[frame] to give the
    bloom b. Highlight-preserving additive combine:
    out = x + (1 - x) * (1 - exp(-b / (1 - x))), so x <= out < 1 for x < 1,
    out - x <= b, and white stays white (nothing clips). flicker[k] =
    1 - depth * (0.5 + 0.5 sin(2 pi f k / fps + phase)), phase from seed.
    """
    _no_extra(extra)
    _gate(source, requested_by_owner, 'neon bloom/glow')
    if image is None:
        image = [[0.95 if (y == 16 and 4 <= x <= 27) or (x == 6 and 8 <= y <= 24)
                  else 0.6 if 20 <= x <= 26 and 20 <= y <= 26 else 0.05
                  for x in range(32)] for y in range(32)]
    planes, kind = _planes(image, 'image')
    thr = _num(threshold, 0, 1, 'threshold')
    knee = _num(knee, 0, 0.5, 'knee')
    sigma = _num(sigma, 0.3, 4, 'sigma')
    inten = _num(intensity, 0, 4, 'intensity')
    fhz = _num(flicker_hz, 0, 30, 'flicker_hz')
    depth = _num(flicker_depth, 0, 1, 'flicker_depth')
    fps = _num(fps, 1, 120, 'fps')
    frames = _int(frames, 1, MAX_FRAMES, 'frames')
    frame = _int(frame, 0, frames - 1, 'frame')
    seed = _int(seed, 0, 2**31 - 1, 'seed')
    phase = random.Random(seed).uniform(0, 2 * math.pi)
    sched = [1 - depth * (0.5 + 0.5 * math.sin(2 * math.pi * fhz * k / fps + phase))
             for k in range(frames)]
    gain = inten * sched[frame]
    out_planes, bloom_planes = [], []
    over = 0
    max_out = 0.0
    for p in planes:
        bright = []
        for row in p:
            br = []
            for x in row:
                soft = 0.0
                if knee > 0:
                    soft = _clamp(x - thr + knee, 0.0, 2 * knee) ** 2 / (4 * knee)
                br.append(max(x - thr, soft, 0.0))
            bright.append(br)
        blur = _gauss_blur(bright, sigma)
        bloom = [[gain * v for v in row] for row in blur]
        out = []
        for row, brow in zip(p, bloom):
            orow = []
            for x, b in zip(row, brow):
                o = 1.0 if x >= 1.0 else x + (1 - x) * (1 - math.exp(-b / (1 - x)))
                o = min(o, 1.0)
                if x + b > 1.0:
                    over += 1
                max_out = max(max_out, o)
                orow.append(o)
            out.append(orow)
        out_planes.append(out)
        bloom_planes.append(bloom)
    result = {'image': _from_planes(out_planes, kind),
              'bloom': _from_planes(bloom_planes, kind) if kind == 'gray' else None,
              'max_output': max_out, 'pixels_compressed_instead_of_clipped': over,
              'flicker_schedule': [round(v, 6) for v in sched], 'frame': frame,
              'effective_intensity': gain, 'threshold': thr, 'knee': knee, 'sigma': sigma}
    return _pack('neon_bloom', result,
                 ['bloom on display-referred values in [0, 1] (no HDR scene data); per-channel for RGB',
                  'single-scale separable Gaussian, clamp-to-edge; not a multi-scale lens glow',
                  'highlight-preserving shoulder: out = x + (1 - x)(1 - exp(-b/(1 - x))), never above 1',
                  'flicker is a deterministic sine schedule with a seeded phase'],
                 [f'images <= {MAX_SIDE}x{MAX_SIDE}, sigma <= 4 px, intensity <= 4, frames <= {MAX_FRAMES}',
                  'pixels below threshold change by at most their bloom contribution b'])


# --------------------------------------------------------------------------- 17.06 snow_vortex

def snow_vortex(*, width=64.0, height=64.0, count=150, frames=48, fps=24.0, seed=0,
                wind=(20.0, 0.0), fall_speed=30.0, vortex_center=(32.0, 32.0),
                circulation=4000.0, core_radius=8.0, drag=3.0, turbulence=5.0,
                max_speed=120.0, substeps=4, source='synthetic', requested_by_owner=False,
                **extra):
    """Seeded snow particles in wind + a Lamb-Oseen vortex (2D, pixels, y down).

    Target velocity u(p) = wind + (0, fall_speed) + vortex, with tangential
    vortex speed circulation / (2 pi r) * (1 - exp(-r^2 / core_radius^2)) (finite
    at the centre). Each substep: v += (drag (u - v) + turbulence * gaussian) h,
    speed clamped to max_speed, p += v h. Particles start at rest-relative-to-flow
    (v = u) and are never respawned or wrapped, so motion accumulates with no
    teleporting: per-frame displacement <= max_speed / fps.
    """
    _no_extra(extra)
    _gate(source, requested_by_owner, 'snow')
    width = _num(width, 1, 4096, 'width')
    height = _num(height, 1, 4096, 'height')
    count = _int(count, 1, 500, 'count')
    frames = _int(frames, 1, MAX_FRAMES, 'frames')
    fps = _num(fps, 1, 120, 'fps')
    seed = _int(seed, 0, 2**31 - 1, 'seed')
    wind = _vec(wind, 2, 'wind', -1000, 1000)
    fall = _num(fall_speed, -1000, 1000, 'fall_speed')
    vc = _vec(vortex_center, 2, 'vortex_center', -1e4, 1e4)
    gam = _num(circulation, -1e6, 1e6, 'circulation')
    rc = _num(core_radius, 0.5, 1e3, 'core_radius')
    drag = _num(drag, 0, 100, 'drag')
    turb = _num(turbulence, 0, 1000, 'turbulence')
    vmax = _num(max_speed, 0, 5000, 'max_speed', low_open=True)
    substeps = _int(substeps, 1, 8, 'substeps')
    if count * frames * substeps > 400_000:
        raise ValueError('count * frames * substeps must be <= 400000')
    h = 1.0 / (fps * substeps)
    if drag * h > 0.5:
        raise ValueError('drag too large for this fps/substeps')

    def field(x, y):
        rx, ry = x - vc[0], y - vc[1]
        r2 = rx * rx + ry * ry
        ux, uy = wind[0], wind[1] + fall
        if r2 > 1e-12:
            vt = gam / (2 * math.pi * r2) * (1 - math.exp(-r2 / (rc * rc)))
            ux += -ry * vt
            uy += rx * vt
        return ux, uy

    rng = random.Random(seed)
    pos = [[rng.uniform(0, width), rng.uniform(0, height)] for _ in range(count)]
    vel = []
    for p in pos:
        ux, uy = field(*p)
        sp = math.hypot(ux, uy)
        f = vmax / sp if sp > vmax else 1.0
        vel.append([ux * f, uy * f])
    noise = turb / math.sqrt(h)
    out = [[[round(c, 4) for c in p] for p in pos]]
    max_step = 0.0
    swirl = 0.0
    for _ in range(frames - 1):
        before = [p[:] for p in pos]
        for _ in range(substeps):
            for p, v in zip(pos, vel):
                ux, uy = field(p[0], p[1])
                v[0] += (drag * (ux - v[0]) + noise * rng.gauss(0, 1)) * h
                v[1] += (drag * (uy - v[1]) + noise * rng.gauss(0, 1)) * h
                sp = math.hypot(v[0], v[1])
                if sp > vmax:
                    v[0] *= vmax / sp
                    v[1] *= vmax / sp
                p[0] += v[0] * h
                p[1] += v[1] * h
        for a, b in zip(before, pos):
            max_step = max(max_step, math.dist(a, b))
            a0 = math.atan2(a[1] - vc[1], a[0] - vc[0])
            a1 = math.atan2(b[1] - vc[1], b[0] - vc[0])
            swirl += (a1 - a0 + math.pi) % (2 * math.pi) - math.pi
        out.append([[round(c, 4) for c in p] for p in pos])
    inside = sum(1 for x, y in pos if 0 <= x <= width and 0 <= y <= height)
    result = {'frames': out, 'count': count, 'fps': fps, 'seed': seed,
              'max_frame_step': max_step, 'frame_step_bound': vmax / fps,
              'mean_swirl_deg_per_particle': math.degrees(swirl / count),
              'inside_frame_at_end': inside, 'core_radius': core_radius}
    return _pack('snow_vortex', result,
                 ['independent point flakes, linear drag toward a steady analytic flow (wind + fall + vortex)',
                  'Lamb-Oseen vortex profile (finite speed at the core); white-noise turbulence',
                  'no respawn or wrapping: flakes that leave the frame keep moving off-screen',
                  'deterministic for a given seed on the same Python random implementation'],
                 ['count <= 500, frames <= 300, substeps <= 8, count * frames * substeps <= 400000',
                  'speed clamped to max_speed, so per-frame motion <= max_speed / fps (no teleporting)'])


# --------------------------------------------------------------------------- 17.07 alpha_composite

def _dec(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _enc(c):
    c = _clamp(c, 0.0, 1.0)
    return c * 12.92 if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


def alpha_composite(*, fg=None, alpha=None, bg=None, shift=(0.5, 0.5), tolerance=1e-3,
                    source='synthetic', requested_by_owner=False, **extra):
    """Composite an RGB element over a plate with premultiplied alpha in linear light.

    The element (straight-alpha sRGB fg + alpha) is moved by a sub-pixel `shift`
    with bilinear resampling, as when it rides a track. Correct path: decode sRGB
    to linear, premultiply, resample, out = P + bg (1 - a), encode. Naive path:
    resample straight sRGB colour and alpha separately, out = c a + bg (1 - a).
    A dark halo is a partly transparent pixel darker than both the true element
    colour (P / a) and the plate; both paths are counted. Default: a 32x32
    hard-edged white sprite (black where transparent) over a light gradient.
    """
    _no_extra(extra)
    _gate(source, requested_by_owner, 'composite overlay')
    if fg is None and alpha is None and bg is None:
        alpha = [[1.0 if 10 <= x <= 21 and 10 <= y <= 21 else 0.0 for x in range(32)]
                 for y in range(32)]
        fg = [[[a] * 3 for a in row] for row in alpha]
        bg = [[[round(0.6 + 0.3 * x / 31, 6)] * 3 for x in range(32)] for _ in range(32)]
    if fg is None or alpha is None or bg is None:
        raise ValueError('fg, alpha and bg are all required (or none, for the built-in example)')
    fgp = _rgb(fg, 'fg')
    al = _gray(alpha, 'alpha')
    bgp = _rgb(bg, 'bg')
    h, w = len(al), len(al[0])
    if len(fgp[0]) != h or len(fgp[0][0]) != w or len(bgp[0]) != h or len(bgp[0][0]) != w:
        raise ValueError('fg, alpha and bg must have the same size')
    sx, sy = _vec(shift, 2, 'shift', -2, 2)
    tol = _num(tolerance, 0, 0.1, 'tolerance')
    prem = [[[_dec(fgp[k][y][x]) * al[y][x] for x in range(w)] for y in range(h)] for k in range(3)]
    out_c, out_n = [], []
    halo_c = halo_n = 0
    dark_c = dark_n = 0.0
    edge = 0
    for y in range(h):
        rc, rn = [], []
        for x in range(w):
            u, v = x - sx, y - sy
            a = _bilinear(al, u, v, outside=0.0)
            pc, pn = [], []
            partial = 1e-6 < a < 1 - 1e-6
            edge += partial
            hc = hn = False
            for k in range(3):
                bgv = bgp[k][y][x]
                P = _bilinear(prem[k], u, v, outside=0.0)
                oc = _enc(P + _dec(bgv) * (1 - a))
                cs = _bilinear(fgp[k], u, v, outside=0.0)
                on = cs * a + bgv * (1 - a)
                pc.append(round(oc, 6))
                pn.append(round(on, 6))
                if partial:
                    ref = min(_enc(P / a), bgv)
                    if oc < ref - tol:
                        hc = True
                        dark_c = max(dark_c, ref - oc)
                    if on < ref - tol:
                        hn = True
                        dark_n = max(dark_n, ref - on)
            halo_c += hc
            halo_n += hn
            rc.append(pc)
            rn.append(pn)
        out_c.append(rc)
        out_n.append(rn)
    result = {'image': out_c, 'naive_image': out_n, 'edge_pixels': edge,
              'halo_pixels_premultiplied_linear': halo_c, 'halo_pixels_naive_straight_srgb': halo_n,
              'max_darkening_premultiplied_linear': dark_c, 'max_darkening_naive': dark_n,
              'shift': [sx, sy]}
    return _pack('alpha_composite', result,
                 ['Porter-Duff "over" with premultiplied colour, computed in linear light (sRGB transfer curve)',
                  'element resampled bilinearly (transparent outside its frame); plate is not resampled',
                  'halo = partly covered pixel darker than both the true element colour and the plate',
                  'input fg is straight (unpremultiplied) sRGB; alpha is linear coverage'],
                 [f'images <= {MAX_SIDE}x{MAX_SIDE}, shift within +/- 2 px',
                  'no colour management beyond sRGB; no motion blur, grain or light-wrap matching'])


# --------------------------------------------------------------------------- 17.08 parallax_layers

_LAYER_KEYS = {'name', 'depth', 'depth_end', 'x', 'width'}


def parallax_layers(*, layers=None, camera_shift=2.0, camera_push=0.0, focal=100.0, frames=24,
                    near_clip=0.1, source='synthetic', requested_by_owner=False, **extra):
    """2.5D parallax move for depth layers, with z-order and overlap checks.

    Layers are listed back-to-front (draw order) as {'name', 'depth', 'x', 'width'}
    with optional 'depth_end' (layer moving in z). The camera trucks by
    camera_shift and pushes by camera_push (world units) with smoothstep easing.
    Screen x = (x - cam_x) * focal / (depth - cam_z), so the screen offset of a
    layer is proportional to 1 / depth. A z-order inversion is any frame where a
    layer drawn later (in front) is farther than one drawn earlier. Overlaps list
    which pairs share screen columns and which layer occludes.
    """
    _no_extra(extra)
    _gate(source, requested_by_owner, 'parallax transition')
    if layers is None:
        layers = [{'name': 'sky', 'depth': 100.0, 'x': -50.0, 'width': 100.0},
                  {'name': 'mountains', 'depth': 40.0, 'x': -20.0, 'width': 40.0},
                  {'name': 'trees', 'depth': 10.0, 'x': -3.0, 'width': 4.0},
                  {'name': 'hero', 'depth': 4.0, 'x': -0.5, 'width': 1.0}]
    if not isinstance(layers, (list, tuple)) or not 1 <= len(layers) <= 16:
        raise ValueError('layers must be a list of 1..16 layer dicts')
    lay = []
    for i, L in enumerate(layers):
        if not isinstance(L, dict):
            raise ValueError(f'layers[{i}] must be a dict')
        bad = set(L) - _LAYER_KEYS
        if bad:
            raise ValueError(f'layers[{i}] has unknown key(s): {sorted(map(str, bad))}')
        if 'name' not in L or 'depth' not in L:
            raise ValueError(f'layers[{i}] needs name and depth')
        name = L['name']
        if not isinstance(name, str) or not 1 <= len(name) <= 64:
            raise ValueError(f'layers[{i}].name must be a 1..64 character string')
        d0 = _num(L['depth'], 0.01, 1e6, f'layers[{i}].depth')
        d1 = _num(L.get('depth_end', d0), 0.01, 1e6, f'layers[{i}].depth_end')
        lay.append({'name': name, 'd0': d0, 'd1': d1,
                    'x': _num(L.get('x', 0.0), -1e6, 1e6, f'layers[{i}].x'),
                    'w': _num(L.get('width', 1.0), 0, 1e6, f'layers[{i}].width')})
    if len({L['name'] for L in lay}) != len(lay):
        raise ValueError('layer names must be unique')
    shift = _num(camera_shift, -1e4, 1e4, 'camera_shift')
    push = _num(camera_push, -1e4, 1e4, 'camera_push')
    focal = _num(focal, 1, 1e5, 'focal')
    frames = _int(frames, 2, MAX_FRAMES, 'frames')
    near = _num(near_clip, 1e-3, 100, 'near_clip')
    per_frame, inversions, overlaps = [], [], {}
    start_sx = None
    max_off = [0.0] * len(lay)
    for f in range(frames):
        s = f / (frames - 1)
        e = s * s * (3 - 2 * s)
        cx, cz = shift * e, push * e
        deff = []
        for i, L in enumerate(lay):
            d = L['d0'] + (L['d1'] - L['d0']) * e - cz
            if d <= near:
                raise ValueError(f'layer {L["name"]} crosses the near clip at frame {f}')
            deff.append(d)
        sx = [(L['x'] - cx) * focal / d for L, d in zip(lay, deff)]
        if start_sx is None:
            start_sx = sx[:]
        offs = [a - b for a, b in zip(sx, start_sx)]
        for i, o in enumerate(offs):
            max_off[i] = max(max_off[i], abs(o))
        for i in range(len(lay)):
            for j in range(i + 1, len(lay)):
                if deff[j] > deff[i] + 1e-12:
                    inversions.append({'frame': f, 'behind': lay[i]['name'],
                                       'drawn_in_front': lay[j]['name']})
                ai, bi = sx[i], sx[i] + lay[i]['w'] * focal / deff[i]
                aj, bj = sx[j], sx[j] + lay[j]['w'] * focal / deff[j]
                if min(bi, bj) > max(ai, aj):
                    key = (lay[i]['name'], lay[j]['name'])
                    rec = overlaps.setdefault(key, {'a': key[0], 'b': key[1], 'frames': 0,
                                                    'occluder': None})
                    rec['frames'] += 1
                    rec['occluder'] = lay[i]['name'] if deff[i] < deff[j] else lay[j]['name']
        per_frame.append({'frame': f, 'camera': [round(cx, 6), round(cz, 6)],
                          'offsets_px': [round(o, 6) for o in offs],
                          'depths': [round(d, 6) for d in deff]})
    result = {'layers': [L['name'] for L in lay], 'frames': per_frame,
              'max_offset_px': [round(v, 6) for v in max_off],
              'order_stable': not inversions, 'inversions': inversions[:200],
              'overlaps': list(overlaps.values()), 'focal': focal}
    return _pack('parallax_layers', result,
                 ['pinhole camera, flat cards facing the camera; horizontal truck and dolly only',
                  'screen offset proportional to camera_shift * focal / depth (1/depth parallax)',
                  'layers listed back-to-front; smoothstep ease on the camera move',
                  'overlap is tested on screen-space horizontal extents only'],
                 ['<= 16 layers, frames 2..300, depths > near_clip throughout the move',
                  'inversions list capped at 200 entries; no vertical parallax or rotation'])


# --------------------------------------------------------------------------- 17.09 inpaint_mask

def inpaint_mask(*, image=None, mask=None, ground_truth=None, max_iter=2000, tol=1e-6,
                 omega=1.6, source='synthetic', requested_by_owner=False,
                 owner_confirms_rights=False, **extra):
    """Fill small masked holes by harmonic (Laplace) diffusion from the boundary.

    mask: same size as image, 1 (or true) = remove/fill, 0 = keep. Hole pixels
    start at the mean of their known neighbours and are relaxed by SOR
    Gauss-Seidel toward the 4-neighbour average until the largest update is
    below tol. consistency_score compares the seam step (filled vs adjacent
    known pixels) to the typical step between known pixels near the hole:
    1.0 = seam as smooth as the background. On footage this needs
    requested_by_owner=True AND owner_confirms_rights=True.
    """
    _no_extra(extra)
    _gate(source, requested_by_owner, 'object removal')
    rights = _bool(owner_confirms_rights, 'owner_confirms_rights')
    if source == 'footage' and not rights:
        raise ValueError('refused: removing an element from footage needs '
                         'owner_confirms_rights=True (owner holds the rights to edit it)')
    if image is None and mask is None:
        ground_truth = [[0.2 + 0.6 * (x + y) / 62 for x in range(32)] for y in range(32)]
        mask = [[1 if 13 <= x <= 18 and 13 <= y <= 18 else 0 for x in range(32)] for y in range(32)]
        image = [[1.0 if mask[y][x] else ground_truth[y][x] for x in range(32)] for y in range(32)]
    if image is None or mask is None:
        raise ValueError('image and mask are both required (or neither, for the built-in example)')
    planes, kind = _planes(image, 'image')
    h, w = len(planes[0]), len(planes[0][0])
    if not isinstance(mask, (list, tuple)) or len(mask) != h:
        raise ValueError('mask must match the image size')
    hole = []
    for y, row in enumerate(mask):
        if not isinstance(row, (list, tuple)) or len(row) != w:
            raise ValueError('mask must match the image size')
        for x, m in enumerate(row):
            if m is True or (not isinstance(m, bool) and m == 1):
                hole.append((x, y))
            elif not (m is False or (not isinstance(m, bool) and m == 0)):
                raise ValueError(f'mask[{y}][{x}] must be 0/1 or false/true')
    if not hole:
        raise ValueError('mask selects no pixels')
    if len(hole) > 4096 or len(hole) > 0.25 * w * h:
        raise ValueError('hole too large: at most 4096 pixels and 25% of the image')
    max_iter = _int(max_iter, 1, 20000, 'max_iter')
    tol = _num(tol, 1e-9, 0.1, 'tol')
    omega = _num(omega, 1.0, 1.95, 'omega')
    if max_iter * len(hole) > 10_000_000:
        raise ValueError('max_iter * hole pixels must be <= 10000000')
    gt = None
    if ground_truth is not None:
        gt_planes, gt_kind = _planes(ground_truth, 'ground_truth')
        if gt_kind != kind or len(gt_planes[0]) != h or len(gt_planes[0][0]) != w:
            raise ValueError('ground_truth must match the image size and type')
        gt = gt_planes
    in_hole = [[False] * w for _ in range(h)]
    for x, y in hole:
        in_hole[y][x] = True
    nbrs = {}
    for x, y in hole:
        nbrs[(x, y)] = [(x + dx, y + dy) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
                        if 0 <= x + dx < w and 0 <= y + dy < h]
    # every hole component must touch at least one known pixel
    seen = set()
    for p in hole:
        if p in seen:
            continue
        stack, comp_known = [p], False
        seen.add(p)
        while stack:
            q = stack.pop()
            for n in nbrs[q]:
                if in_hole[n[1]][n[0]]:
                    if n not in seen:
                        seen.add(n)
                        stack.append(n)
                else:
                    comp_known = True
        if not comp_known:
            raise ValueError('a masked region has no known boundary pixels to fill from')
    out_planes, iters_used, residual = [], 0, 0.0
    for p in planes:
        img = [row[:] for row in p]
        for x, y in hole:
            img[y][x] = None
        changed = True
        while changed:  # initial guess: grow inward from known pixels
            changed = False
            for x, y in hole:
                if img[y][x] is None:
                    vals = [img[ny][nx] for nx, ny in nbrs[(x, y)] if img[ny][nx] is not None]
                    if vals:
                        img[y][x] = sum(vals) / len(vals)
                        changed = True
        it = 0
        delta = 0.0
        for it in range(1, max_iter + 1):
            delta = 0.0
            for x, y in hole:
                nb = nbrs[(x, y)]
                avg = sum(img[ny][nx] for nx, ny in nb) / len(nb)
                new = img[y][x] + omega * (avg - img[y][x])
                delta = max(delta, abs(new - img[y][x]))
                img[y][x] = new
            if delta < tol:
                break
        iters_used = max(iters_used, it)
        residual = max(residual, delta)
        for x, y in hole:
            img[y][x] = _clamp(img[y][x], 0.0, 1.0)
        out_planes.append(img)
    # consistency: seam step vs background step in a ring around the hole
    ring = set()
    for x, y in hole:
        for dy in range(-3, 4):
            for dx in range(-3, 4):
                nx, ny = x + dx, y + dy
                if 0 <= nx < w and 0 <= ny < h and not in_hole[ny][nx]:
                    ring.add((nx, ny))
    seam, bgd = [], []
    for img in out_planes:
        for x, y in hole:
            for nx, ny in nbrs[(x, y)]:
                if not in_hole[ny][nx]:
                    seam.append(abs(img[y][x] - img[ny][nx]))
        for x, y in ring:
            for nx, ny in ((x + 1, y), (x, y + 1)):
                if (nx, ny) in ring:
                    bgd.append(abs(img[y][x] - img[ny][nx]))
    seam_m = sum(seam) / len(seam)
    bg_m = sum(bgd) / len(bgd) if bgd else 0.0
    score = math.exp(-abs(seam_m - bg_m) / (bg_m + 0.01))
    result = {'image': _from_planes(out_planes, kind), 'hole_pixels': len(hole),
              'iterations': iters_used, 'final_update': residual, 'converged': residual < tol,
              'seam_step': seam_m, 'background_step': bg_m, 'consistency_score': score}
    if gt is not None:
        errs = [abs(out_planes[k][y][x] - gt[k][y][x]) for k in range(len(gt)) for x, y in hole]
        result['max_error_vs_ground_truth'] = max(errs)
        result['mean_error_vs_ground_truth'] = sum(errs) / len(errs)
    return _pack('inpaint_mask', result,
                 ['harmonic (membrane) fill: exact for linear gradients, smooths away texture and edges',
                  'single frame, no temporal propagation or patch synthesis; holes must touch known pixels',
                  'consistency_score compares seam step with the nearby background step (1 = seamless)'],
                 ['hole <= 4096 pixels and <= 25% of the image; images <= 128x128; max_iter <= 20000',
                  'footage additionally requires owner_confirms_rights=True (removal of a licensed/owned element only)'])


# --------------------------------------------------------------------------- 17.10 sparks

def sparks(*, emitter=(0.0, 0.0), count=40, frames=48, fps=24.0, seed=0, speed_min=2.0,
           speed_max=5.0, angle_deg=90.0, spread_deg=40.0, gravity=9.81, drag=0.5,
           life_min=0.5, life_max=1.5, emit_window=0.5, fade_power=1.5,
           source='synthetic', requested_by_owner=False, **extra):
    """Seeded spark emitter: ballistic arcs with linear drag and a fade to zero.

    World units, y UP. Spark i is born at a seeded time in [0, emit_window] with
    speed in [speed_min, speed_max] at angle_deg +/- spread_deg/2 (90 = straight
    up). Exact solution with linear drag k: v(t) = v_inf + (v0 - v_inf) e^{-kt},
    v_inf = (0, -g/k) (pure ballistic when k = 0). alpha = (1 - age/life)^fade_power,
    strictly decreasing, 0 at end of life. Each spark lists samples
    [t, x, y, vy, alpha] at frame times while alive plus one at its death.
    No fire, smoke or heat simulation.
    """
    _no_extra(extra)
    _gate(source, requested_by_owner, 'sparks')
    ex, ey = _vec(emitter, 2, 'emitter', -1e4, 1e4)
    count = _int(count, 1, 300, 'count')
    frames = _int(frames, 1, MAX_FRAMES, 'frames')
    if count * frames > 30_000:
        raise ValueError('count * frames must be <= 30000')
    fps = _num(fps, 1, 120, 'fps')
    seed = _int(seed, 0, 2**31 - 1, 'seed')
    smin = _num(speed_min, 0, 1000, 'speed_min')
    smax = _num(speed_max, 0, 1000, 'speed_max')
    if smin > smax:
        raise ValueError('speed_min must be <= speed_max')
    ang = _num(angle_deg, -360, 360, 'angle_deg')
    spread = _num(spread_deg, 0, 360, 'spread_deg')
    g = _num(gravity, 0.01, 1000, 'gravity')
    k = _num(drag, 0, 50, 'drag')
    lmin = _num(life_min, 0.01, 60, 'life_min')
    lmax = _num(life_max, 0.01, 60, 'life_max')
    if lmin > lmax:
        raise ValueError('life_min must be <= life_max')
    win = _num(emit_window, 0, 60, 'emit_window')
    fp = _num(fade_power, 0.1, 10, 'fade_power')

    def state(t, vx0, vy0):
        if k == 0:
            return vx0 * t, vy0 * t - 0.5 * g * t * t, vy0 - g * t
        vinf = -g / k
        e = math.exp(-k * t)
        x = vx0 * (1 - e) / k
        y = vinf * t + (vy0 - vinf) * (1 - e) / k
        return x, y, vinf + (vy0 - vinf) * e

    rng = random.Random(seed)
    out = []
    fade_ok = zero_ok = vy_ok = True
    for _ in range(count):
        birth = rng.uniform(0, win)
        life = rng.uniform(lmin, lmax)
        sp = rng.uniform(smin, smax)
        a = math.radians(ang + rng.uniform(-spread / 2, spread / 2))
        vx0, vy0 = sp * math.cos(a), sp * math.sin(a)
        times = [f / fps for f in range(frames) if birth <= f / fps < birth + life]
        times.append(birth + life)
        samples = []
        for t in times:
            age = min(t - birth, life)
            x, y, vy = state(age, vx0, vy0)
            alpha = max(0.0, 1 - age / life) ** fp
            samples.append([round(t, 6), round(ex + x, 6), round(ey + y, 6), round(vy, 6),
                            round(alpha, 6)])
        al = [s[4] for s in samples]
        vys = [s[3] for s in samples]
        if any(b >= a2 for a2, b in zip(al, al[1:])):
            fade_ok = False
        if al[-1] != 0.0:
            zero_ok = False
        if any(b >= a2 for a2, b in zip(vys, vys[1:])):
            vy_ok = False
        out.append({'birth': round(birth, 6), 'life': round(life, 6), 'samples': samples})
    result = {'sparks': out, 'count': count, 'fps': fps, 'seed': seed,
              'all_fade_monotonic': fade_ok, 'all_reach_zero_alpha': zero_ok,
              'all_vertical_velocity_decreasing': vy_ok, 'gravity': g, 'drag': k}
    return _pack('sparks', result,
                 ['point sparks on exact ballistic arcs with linear drag; y is up, world units',
                  'no collisions, bounces, fire, smoke or heat; purely a visual overlay element',
                  'alpha fades as a power of remaining life and is exactly 0 at death',
                  'deterministic for a given seed on the same Python random implementation'],
                 ['count <= 300, frames <= 300, count * frames <= 30000',
                  'samples land on frame times plus one death sample, which may fall after the last frame'])


# --------------------------------------------------------------------------- dispatcher

OPS = {
    'track_point': track_point, 'rain_light': rain_light, 'cast_shadow': cast_shadow,
    'heat_haze': heat_haze, 'neon_bloom': neon_bloom, 'snow_vortex': snow_vortex,
    'alpha_composite': alpha_composite, 'parallax_layers': parallax_layers,
    'inpaint_mask': inpaint_mask, 'sparks': sparks,
}


def run(op, params=None):
    """Validate and dispatch: run('neon_bloom', {}) -> {'op','result','assumptions','limits'}."""
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
