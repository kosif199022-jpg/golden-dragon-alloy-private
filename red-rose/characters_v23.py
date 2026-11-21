"""Red Rose V23: bounded, deterministic 2D character-animation helpers (topics 14.01-14.10).

Pure standard-library Python plus the project's pure geometry_v20 (two-bone IK)
and physics_v20 (mass-spring-damper reference). No file I/O, no subprocess, no
network, no printing. Every op validates its inputs strictly (ValueError on
bools-as-numbers, non-finite values, unknown parameter names and out-of-range
values) and caps its work (<= 600 frames, <= 20 characters, <= 40 bones).

These are 2D code-animation building blocks for stylised characters, not motion
capture, not a renderer and not audio/vision recognition: each op returns the
assumptions it makes and the limits it enforces next to its result.
Units: lengths in caller units (metres or pixels), angles in degrees, time in
seconds or frames as named.
"""
from __future__ import annotations

import json
import math
import random
import re
import statistics

import geometry_v20
import physics_v20

MAX_PARAMS = 24
MAX_FRAMES = 600
MAX_CHARACTERS = 20
MAX_BONES = 40

TOPICS = {
    '14.01': 'skeleton',
    '14.02': 'walk_cycle',
    '14.03': 'run_cycle',
    '14.04': 'expressions',
    '14.05': 'viseme_track',
    '14.06': 'landmark_smoothing',
    '14.07': 'identity_lock',
    '14.08': 'hand_grip',
    '14.09': 'secondary_motion',
    '14.10': 'crowd_layers',
}

TOPIC_NAMES_AR = {
    '14.01': 'هيكل شخصية مفصلي',
    '14.02': 'دورة مشي بشرية مبسطة',
    '14.03': 'حركة جري متسقة',
    '14.04': 'تعبيرات الوجه المتبدلة',
    '14.05': 'تحريك الفم حسب النص',
    '14.06': 'التحريك من فيديو مرجعي مرخص',
    '14.07': 'ثبات هوية الشخصية بين اللقطات',
    '14.08': 'تحريك اليد والإمساك',
    '14.09': 'حركة شعر وملابس ثانوية',
    '14.10': 'تحريك مجموعة شخصيات',
}

_NAME_RE = re.compile(r'^[A-Za-z0-9_؀-ۿ][A-Za-z0-9_.\- ؀-ۿ]{0,63}$')
_HEX_RE = re.compile(r'^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$')


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


def _vec(value, size, name, low=-1e6, high=1e6):
    if not isinstance(value, (list, tuple)) or len(value) != size:
        raise ValueError(f'{name} must be a list of {size} numbers')
    return [_num(v, low, high, f'{name}[{i}]') for i, v in enumerate(value)]


def _name(value, name):
    if not isinstance(value, str) or not _NAME_RE.fullmatch(value):
        raise ValueError(f'{name} must be a short name (1-64 letters, digits, _ . - or space)')
    return value


def _list(value, low, high, name):
    if not isinstance(value, (list, tuple)) or not low <= len(value) <= high:
        raise ValueError(f'{name} must be a list of {low}..{high} items')
    return list(value)


def _dict(value, name, allowed=None, required=(), max_len=64):
    if not isinstance(value, dict) or len(value) > max_len:
        raise ValueError(f'{name} must be a dict with at most {max_len} keys')
    if not all(isinstance(k, str) for k in value):
        raise ValueError(f'{name} keys must be strings')
    if allowed is not None:
        bad = sorted(set(value) - set(allowed))
        if bad:
            raise ValueError(f'{name} has unknown key(s): {", ".join(bad)}')
    for key in required:
        if key not in value:
            raise ValueError(f'{name} is missing required key {key!r}')
    return value


def _color(value, name):
    if not isinstance(value, str) or not _HEX_RE.fullmatch(value):
        raise ValueError(f'{name} must be a hex colour like #a1b2c3')
    h = value[1:]
    if len(h) == 3:
        h = ''.join(c * 2 for c in h)
    return [int(h[i:i + 2], 16) for i in (0, 2, 4)]


def _hex(rgb):
    return '#' + ''.join(f'{int(c):02x}' for c in rgb)


def _rgb_dist(a, b):
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def _palette(value, name, max_roles=32):
    _dict(value, name, max_len=max_roles)
    if not value:
        raise ValueError(f'{name} must have at least one colour role')
    return {_name(role, f'{name} role'): _color(col, f'{name}[{role}]')
            for role, col in value.items()}


def _decimate(seq, max_points):
    """Evenly pick at most max_points items, always keeping first and last."""
    n = len(seq)
    if n <= max_points:
        return list(seq)
    idx = sorted({round(i * (n - 1) / (max_points - 1)) for i in range(max_points)})
    return [seq[i] for i in idx]


def _pack(op, result, assumptions, limits):
    return {'op': op, 'result': result, 'assumptions': list(assumptions),
            'limits': list(limits)}


def _minjerk(u):
    return u * u * u * (10 + u * (-15 + 6 * u))


def _minjerk_d(u):
    return 30 * u * u * (1 - u) * (1 - u)


# --------------------------------------------------------------------------- 14.01 skeleton

_DEFAULT_BONES = [
    {'name': 'spine', 'parent': None, 'length': 0.5, 'rest_deg': 90.0},
    {'name': 'neck', 'parent': 'spine', 'length': 0.12, 'rest_deg': 0.0},
    {'name': 'upper_arm', 'parent': 'spine', 'length': 0.30, 'rest_deg': -45.0},
    {'name': 'forearm', 'parent': 'upper_arm', 'length': 0.28, 'rest_deg': 60.0},
    {'name': 'hand', 'parent': 'forearm', 'length': 0.08, 'rest_deg': 0.0},
]
_DEFAULT_WAVE = {
    'upper_arm': {'amplitude_deg': 8.0, 'frequency_hz': 0.75, 'phase_deg': 0.0},
    'forearm': {'amplitude_deg': 25.0, 'frequency_hz': 1.5, 'phase_deg': 0.0},
    'hand': {'amplitude_deg': 15.0, 'frequency_hz': 1.5, 'phase_deg': 90.0},
}


def _bones(bones):
    bones = _list(bones, 1, MAX_BONES, 'bones')
    out, seen = [], {}
    for i, b in enumerate(bones):
        _dict(b, f'bones[{i}]', allowed={'name', 'parent', 'length', 'rest_deg'},
              required=('name', 'length'))
        name = _name(b['name'], f'bones[{i}].name')
        if name in seen:
            raise ValueError(f'duplicate bone name {name!r}')
        parent = b.get('parent')
        if parent is not None:
            parent = _name(parent, f'bones[{i}].parent')
            if parent not in seen:
                raise ValueError(f'bone {name!r}: parent {parent!r} must be listed before it')
        length = _num(b['length'], 0, 1e4, f'bones[{i}].length', low_open=True)
        rest = _num(b.get('rest_deg', 0.0), -360, 360, f'bones[{i}].rest_deg')
        seen[name] = len(out)
        out.append({'name': name, 'parent': parent, 'length': length, 'rest_deg': rest})
    return out, seen


def _fk(bones, local_deg, root):
    """Forward kinematics: local angles are relative to the parent bone's world angle."""
    world, heads, tails = [], [], []
    index = {b['name']: i for i, b in enumerate(bones)}
    for i, b in enumerate(bones):
        if b['parent'] is None:
            base, head = 0.0, root
        else:
            p = index[b['parent']]
            base, head = world[p], tails[p]
        ang = base + local_deg[i]
        a = math.radians(ang)
        tail = [head[0] + b['length'] * math.cos(a), head[1] + b['length'] * math.sin(a)]
        world.append(ang)
        heads.append(head)
        tails.append(tail)
    return world, heads, tails


def skeleton(*, bones=None, motion=None, frames=120, fps=24.0, root=(0.0, 0.0),
             tolerance=1e-9, max_samples=25, **extra):
    """2D articulated skeleton + forward kinematics over a sinusoidal pose sequence.

    bones: [{name, parent (earlier bone or None), length, rest_deg}], rest_deg is
    the angle relative to the parent (world angle for root bones). motion:
    {bone: {amplitude_deg, frequency_hz, phase_deg}} adds
    amplitude * sin(2 pi f t + phase) to that bone's local angle. Every frame the
    distance head->tail is re-measured and compared with the bone's length.
    Default: a waving arm (120 frames).
    """
    _no_extra(extra)
    if bones is None:
        bones = _DEFAULT_BONES
        if motion is None:
            motion = _DEFAULT_WAVE
    bones, index = _bones(bones)
    motion = {} if motion is None else _dict(motion, 'motion', max_len=MAX_BONES)
    waves = {}
    for bname, spec in motion.items():
        if bname not in index:
            raise ValueError(f'motion refers to unknown bone {bname!r}')
        _dict(spec, f'motion[{bname}]', allowed={'amplitude_deg', 'frequency_hz', 'phase_deg'})
        waves[index[bname]] = (
            _num(spec.get('amplitude_deg', 0.0), 0, 180, f'motion[{bname}].amplitude_deg'),
            _num(spec.get('frequency_hz', 1.0), 0, 30, f'motion[{bname}].frequency_hz'),
            _num(spec.get('phase_deg', 0.0), -360, 360, f'motion[{bname}].phase_deg'))
    frames = _int(frames, 1, MAX_FRAMES, 'frames')
    fps = _num(fps, 1, 240, 'fps')
    root = _vec(root, 2, 'root')
    tolerance = _num(tolerance, 0, 1, 'tolerance')
    max_samples = _int(max_samples, 2, MAX_FRAMES, 'max_samples')

    per_bone_err = [0.0] * len(bones)
    samples = []
    for f in range(frames):
        t = f / fps
        local = []
        for i, b in enumerate(bones):
            ang = b['rest_deg']
            if i in waves:
                amp, freq, ph = waves[i]
                ang += amp * math.sin(2 * math.pi * freq * t + math.radians(ph))
            local.append(ang)
        world, heads, tails = _fk(bones, local, root)
        for i, b in enumerate(bones):
            measured = math.hypot(tails[i][0] - heads[i][0], tails[i][1] - heads[i][1])
            per_bone_err[i] = max(per_bone_err[i], abs(measured - b['length']))
        samples.append({'frame': f, 'world_deg': {b['name']: world[i] for i, b in enumerate(bones)},
                        'tails': {b['name']: tails[i] for i, b in enumerate(bones)}})
    max_err = max(per_bone_err)
    result = {
        'bones': bones, 'frames': frames, 'fps': fps, 'root': root,
        'per_bone_max_length_error': {b['name']: per_bone_err[i] for i, b in enumerate(bones)},
        'max_length_error': max_err, 'tolerance': tolerance,
        'lengths_constant': max_err <= tolerance,
        'samples': _decimate(samples, max_samples),
    }
    return _pack('skeleton', result,
                 ['2D planar chain(s); local angles relative to the parent bone',
                  'root bones start at `root`; child bones start at the parent tail',
                  'pose sequence is a sum of per-bone sinusoids (procedural, not keyed mocap)'],
                 [f'<= {MAX_BONES} bones, <= {MAX_FRAMES} frames', 'no joint limits, no collisions, no skinning',
                  f'samples decimated to <= {max_samples} frames'])


# --------------------------------------------------------------------------- gait helper (14.02 / 14.03)

def _gait(n, duty, stride, thigh, shin, hip_height, step_height, hip_bob):
    """Frames 0..n (inclusive) of a two-leg gait; foot plants are fixed in world space."""
    rows = []
    for i in range(n + 1):
        u = i / n
        hip = [stride * u, hip_height + hip_bob * math.cos(4 * math.pi * u)]
        feet = []
        for off in (0.0, 0.5):
            p = (u + off) % 1.0
            contact = p < duty
            if contact:
                rel, y = stride * (duty / 2 - p), 0.0
            else:
                s = (p - duty) / (1 - duty)
                rel, y = stride * duty * (_minjerk(s) - 0.5), step_height * math.sin(math.pi * s)
            target = [hip[0] + rel, y]
            ik = geometry_v20.ik_two_bone(l1=thigh, l2=shin, target=target, root=hip, elbow='left')
            if ik['clamped']:
                raise ValueError(f'leg cannot reach foot target at frame {i}: lower stride or '
                                 'hip_height, or lengthen the leg')
            feet.append({'contact': contact, 'phase': p, 'target': target,
                         'knee': ik['joint'], 'foot': ik['end'], 'ik_error': ik['end_error']})
        rows.append({'frame': i, 'hip': hip, 'feet': feet})
    return rows


def _gait_report(rows, n):
    names = ('left', 'right')
    drift = 0.0
    ik_err = 0.0
    contact_counts = [0, 0]
    for i, row in enumerate(rows):
        for k in range(2):
            ft = row['feet'][k]
            ik_err = max(ik_err, ft['ik_error'])
            if i < n and ft['contact']:
                contact_counts[k] += 1
            if i > 0 and ft['contact'] and rows[i - 1]['feet'][k]['contact']:
                prev = rows[i - 1]['feet'][k]['foot']
                drift = max(drift, math.hypot(ft['foot'][0] - prev[0], ft['foot'][1] - prev[1]))
    a, b = rows[0], rows[n]
    loop = 0.0
    for k in range(2):
        for key in ('knee', 'foot'):
            for c in range(2):
                pa = a['feet'][k][key][c] - a['hip'][c]
                pb = b['feet'][k][key][c] - b['hip'][c]
                loop = max(loop, abs(pa - pb))
    loop = max(loop, abs(a['hip'][1] - b['hip'][1]))
    return names, drift, ik_err, contact_counts, loop


def _gait_samples(rows, max_samples):
    out = []
    for row in rows:
        out.append({'frame': row['frame'], 'hip': row['hip'],
                    'left': {'knee': row['feet'][0]['knee'], 'foot': row['feet'][0]['foot'],
                             'contact': row['feet'][0]['contact']},
                    'right': {'knee': row['feet'][1]['knee'], 'foot': row['feet'][1]['foot'],
                              'contact': row['feet'][1]['contact']}})
    return _decimate(out, max_samples)


# --------------------------------------------------------------------------- 14.02 walk_cycle

def walk_cycle(*, frames=32, fps=24.0, thigh=0.45, shin=0.45, hip_height=0.85, stride=0.6,
               step_height=0.08, duty_factor=0.6, hip_bob=0.015, drift_tolerance=1e-6,
               max_samples=33, **extra):
    """Procedural walk cycle: planted stance feet + geometry_v20 two-bone leg IK.

    One cycle = `frames` frames; the hip advances `stride` per cycle (root motion).
    Each foot is in contact for duty_factor of the cycle (> 0.5 for walking, so
    there is double support), planted at a fixed world point; during swing it
    follows a min-jerk path with a sine lift of step_height. Foot drift is the
    frame-to-frame world motion of the IK foot while in contact; the loop check
    compares the hip-relative pose at frame 0 with frame `frames`.
    """
    _no_extra(extra)
    frames = _int(frames, 8, MAX_FRAMES, 'frames')
    fps = _num(fps, 1, 240, 'fps')
    thigh = _num(thigh, 0, 1e3, 'thigh', low_open=True)
    shin = _num(shin, 0, 1e3, 'shin', low_open=True)
    hip_height = _num(hip_height, 0, 2e3, 'hip_height', low_open=True)
    stride = _num(stride, 0, 2e3, 'stride')
    step_height = _num(step_height, 0, 1e3, 'step_height')
    duty = _num(duty_factor, 0.5, 0.95, 'duty_factor', low_open=True)
    hip_bob = _num(hip_bob, 0, 1e3, 'hip_bob')
    drift_tolerance = _num(drift_tolerance, 0, 1, 'drift_tolerance')
    max_samples = _int(max_samples, 2, MAX_FRAMES + 1, 'max_samples')
    if hip_bob >= hip_height:
        raise ValueError('hip_bob must be smaller than hip_height')
    rows = _gait(frames, duty, stride, thigh, shin, hip_height, step_height, hip_bob)
    names, drift, ik_err, counts, loop = _gait_report(rows, frames)
    double = sum(1 for r in rows[:frames] if r['feet'][0]['contact'] and r['feet'][1]['contact'])
    result = {
        'frames_per_cycle': frames, 'fps': fps, 'cycle_seconds': frames / fps,
        'speed_per_second': stride * fps / frames, 'root_motion_per_cycle': stride,
        'duty_factor': duty,
        'contact_fraction': {names[k]: counts[k] / frames for k in range(2)},
        'double_support_frames': double,
        'max_stance_drift': drift, 'drift_tolerance': drift_tolerance,
        'feet_planted': drift <= drift_tolerance,
        'loop_error': loop, 'loops': loop <= 1e-9,
        'max_ik_end_error': ik_err,
        'samples': _gait_samples(rows, max_samples),
    }
    return _pack('walk_cycle', result,
                 ['2D side view, flat ground at y = 0, walking toward +x',
                  'feet are points; stance foot fixed in world space, hip moves at constant speed',
                  'legs solved with geometry_v20.ik_two_bone (knee forward), no ankle/toe roll',
                  'loop measured in hip-relative space (root motion removed)'],
                 [f'8..{MAX_FRAMES} frames per cycle', 'unreachable foot targets are rejected, not clamped',
                  'no balance, mass or ground-reaction physics; stylised, not motion capture',
                  f'samples decimated to <= {max_samples}'])


# --------------------------------------------------------------------------- 14.03 run_cycle

def run_cycle(*, cadence_spm=170.0, duty_factor=0.35, fps=30.0, stride=1.2, thigh=0.45,
              shin=0.45, hip_height=0.82, step_height=0.18, hip_bob=0.03, max_samples=61,
              **extra):
    """Run cycle from cadence (steps per minute) and duty factor (< 0.5 => flight phases).

    Cycle (two steps) lasts 120 / cadence seconds = round(fps * 120 / cadence)
    frames. A foot is in contact while its phase < duty_factor; feet are half a
    cycle apart, so both are off the ground for (1 - 2 duty) of the cycle.
    Reports contact intervals per foot (frames [start, end) and seconds) and the
    flight frames. Rejects settings whose flight phase is shorter than one frame.
    """
    _no_extra(extra)
    cadence = _num(cadence_spm, 60, 260, 'cadence_spm')
    duty = _num(duty_factor, 0.05, 0.5, 'duty_factor')
    if duty >= 0.5:
        raise ValueError('duty_factor must be < 0.5 for a run (otherwise there is no flight phase)')
    fps = _num(fps, 6, 240, 'fps')
    stride = _num(stride, 0, 2e3, 'stride')
    thigh = _num(thigh, 0, 1e3, 'thigh', low_open=True)
    shin = _num(shin, 0, 1e3, 'shin', low_open=True)
    hip_height = _num(hip_height, 0, 2e3, 'hip_height', low_open=True)
    step_height = _num(step_height, 0, 1e3, 'step_height')
    hip_bob = _num(hip_bob, 0, 1e3, 'hip_bob')
    max_samples = _int(max_samples, 2, MAX_FRAMES + 1, 'max_samples')
    if hip_bob >= hip_height:
        raise ValueError('hip_bob must be smaller than hip_height')
    cycle_s = 120.0 / cadence
    n = round(cycle_s * fps)
    if not 8 <= n <= MAX_FRAMES:
        raise ValueError(f'cycle would be {n} frames; need 8..{MAX_FRAMES} (adjust fps or cadence)')
    if (1 - 2 * duty) * n < 1:
        raise ValueError('flight phase is shorter than one frame at this fps; lower duty_factor or raise fps')
    rows = _gait(n, duty, stride, thigh, shin, hip_height, step_height, hip_bob)
    names, drift, ik_err, counts, loop = _gait_report(rows, n)
    intervals = {}
    for k in range(2):
        flags = [rows[i]['feet'][k]['contact'] for i in range(n)]
        runs, start = [], None
        for i, c in enumerate(flags + [False]):
            if c and start is None:
                start = i
            elif not c and start is not None:
                runs.append([start, i])
                start = None
        if len(runs) > 1 and runs[0][0] == 0 and runs[-1][1] == n:
            runs = runs[1:-1] + [[runs[-1][0], n + runs[0][1]]]   # wraps around the loop
        intervals[names[k]] = [{'frames': r, 'seconds': [r[0] / fps, r[1] / fps]} for r in runs]
    flight = [i for i in range(n) if not rows[i]['feet'][0]['contact']
              and not rows[i]['feet'][1]['contact']]
    fraction = {names[k]: counts[k] / n for k in range(2)}
    frac_err = max(abs(v - duty) for v in fraction.values())
    result = {
        'cadence_spm': cadence, 'cycle_seconds_requested': cycle_s,
        'frames_per_cycle': n, 'cycle_seconds_used': n / fps, 'fps': fps,
        'duty_factor': duty, 'contact_fraction': fraction,
        'contact_fraction_error': frac_err, 'frame_tolerance': 1.0 / n,
        'contact_fraction_within_one_frame': frac_err <= 1.0 / n + 1e-12,
        'contact_intervals': intervals,
        'flight_frames': flight, 'has_flight_phase': bool(flight),
        'expected_flight_fraction': 1 - 2 * duty,
        'speed_per_second': stride / (n / fps),
        'max_stance_drift': drift, 'loop_error': loop, 'max_ik_end_error': ik_err,
        'samples': _gait_samples(rows, max_samples),
    }
    return _pack('run_cycle', result,
                 ['2D side view, flat ground y = 0, feet half a cycle apart',
                  'cadence counts steps (one foot contact each); a cycle is two steps',
                  'cycle length rounded to whole frames, so timing may differ from the request by < 0.5 frame',
                  'legs solved with geometry_v20.ik_two_bone; stance feet planted in world space'],
                 ['contact is a frame-sampled phase test: fractions are exact only to 1/frames_per_cycle',
                  'no ballistic centre-of-mass solve for flight; hip height is a stylised bob',
                  f'cycle 8..{MAX_FRAMES} frames; cadence 60..260 spm',
                  f'samples decimated to <= {max_samples}'])


# --------------------------------------------------------------------------- 14.04 expressions

_CONTROLS = {'blink': (0.0, 1.0), 'mouth_open': (0.0, 1.0), 'smile': (-1.0, 1.0),
             'brow': (-1.0, 1.0)}
_DEFAULT_EXPR = {
    'neutral': {'blink': 0.0, 'mouth_open': 0.0, 'smile': 0.0, 'brow': 0.0},
    'happy': {'blink': 0.1, 'mouth_open': 0.3, 'smile': 0.9, 'brow': 0.2},
    'sad': {'blink': 0.35, 'mouth_open': 0.05, 'smile': -0.7, 'brow': -0.2},
    'surprised': {'blink': 0.0, 'mouth_open': 0.9, 'smile': 0.0, 'brow': 1.0},
    'angry': {'blink': 0.2, 'mouth_open': 0.2, 'smile': -0.4, 'brow': -1.0},
}
_DEFAULT_KEYS = [[0, 'neutral'], [12, 'happy'], [24, 'sad'], [36, 'surprised'],
                 [48, 'angry'], [60, 'neutral']]


def expressions(*, expressions=None, keys=None, frames=None, easing='smooth', **extra):
    """Face-rig keys (blink, mouth_open, smile, brow) with named expressions.

    Built-in expressions: neutral, happy, sad, surprised, angry; `expressions`
    adds or overrides by name (missing controls default to neutral). Control
    ranges: blink/mouth_open 0..1, smile/brow -1..1 (brow < 0 = frown); values
    outside the range are clamped and that expression is reported as not exactly
    reachable. keys: [[frame, name], ...] with strictly increasing frames;
    in-between frames interpolate (linear or smoothstep), the ends hold.
    """
    _no_extra(extra)
    table = {k: dict(v) for k, v in _DEFAULT_EXPR.items()}
    if expressions is not None:
        _dict(expressions, 'expressions', max_len=32)
        for ename, vals in expressions.items():
            _name(ename, 'expression name')
            _dict(vals, f'expressions[{ename}]', allowed=set(_CONTROLS))
            base = dict(table.get(ename, _DEFAULT_EXPR['neutral']))
            for c, v in vals.items():
                base[c] = _num(v, -1e3, 1e3, f'expressions[{ename}].{c}')
            table[ename] = base
    if len(table) > 40:
        raise ValueError('at most 40 expressions in total')
    clamped, reach = [], {}
    for ename, vals in table.items():
        ok = True
        for c, (lo, hi) in _CONTROLS.items():
            v = vals[c]
            cv = min(hi, max(lo, v))
            if cv != v:
                clamped.append({'expression': ename, 'control': c, 'requested': v, 'used': cv})
                ok = False
            vals[c] = cv
        reach[ename] = ok
    keys = _DEFAULT_KEYS if keys is None else keys
    keys = _list(keys, 1, MAX_FRAMES, 'keys')
    parsed = []
    for i, k in enumerate(keys):
        if not isinstance(k, (list, tuple)) or len(k) != 2:
            raise ValueError(f'keys[{i}] must be [frame, expression]')
        f = _int(k[0], 0, MAX_FRAMES - 1, f'keys[{i}] frame')
        if not isinstance(k[1], str) or k[1] not in table:
            raise ValueError(f'keys[{i}] names unknown expression; choose from {sorted(table)}')
        if parsed and f <= parsed[-1][0]:
            raise ValueError('key frames must be strictly increasing')
        parsed.append((f, k[1]))
    if frames is None:
        frames = parsed[-1][0] + 1
    frames = _int(frames, 1, MAX_FRAMES, 'frames')
    if frames <= parsed[-1][0]:
        raise ValueError('frames must exceed the last key frame')
    easing = _choice(easing, {'linear', 'smooth'}, 'easing')

    track = []
    j = 0
    for f in range(frames):
        while j + 1 < len(parsed) and parsed[j + 1][0] <= f:
            j += 1
        fa, ea = parsed[j]
        if f <= fa or j + 1 >= len(parsed):
            vals = dict(table[ea])   # on a key, before the first key, or after the last key
        else:
            fb, eb = parsed[j + 1]
            u = (f - fa) / (fb - fa)
            w = u if easing == 'linear' else u * u * (3 - 2 * u)
            vals = {}
            for c, (lo, hi) in _CONTROLS.items():
                va, vb = table[ea][c], table[eb][c]
                vals[c] = min(hi, max(lo, va + (vb - va) * w))
        track.append({'frame': f, **{c: vals[c] for c in _CONTROLS}})
    key_err = []
    for f, ename in parsed:
        err = max(abs(track[f][c] - table[ename][c]) for c in _CONTROLS)
        key_err.append({'frame': f, 'expression': ename, 'max_error': err,
                        'reached': err == 0.0 and reach[ename]})
    in_range = all(_CONTROLS[c][0] <= row[c] <= _CONTROLS[c][1] for row in track for c in _CONTROLS)
    result = {
        'controls': {c: list(r) for c, r in _CONTROLS.items()},
        'expressions': table, 'reachable_exactly': reach, 'clamped': clamped,
        'keys': key_err, 'all_keys_reached': all(k['reached'] for k in key_err),
        'values_in_range': in_range, 'easing': easing, 'frames': frames, 'track': track,
    }
    return _pack('expressions', result,
                 ['abstract 2D face-rig controls, not muscle or FACS simulation',
                  'expressions are hand-authored control sets; sad/angry/etc. are stylised defaults',
                  'interpolation is per control between consecutive keys; the ends hold'],
                 [f'<= {MAX_FRAMES} frames, <= 40 expressions', 'out-of-range values are clamped and flagged',
                  'no emotion recognition and no rendering'])


# --------------------------------------------------------------------------- 14.05 viseme_track

VISEMES = ('closed', 'open', 'wide', 'round', 'teeth')
_LETTER_RULES = (
    ('closed', set('bmpبم')),
    ('teeth', set('fvszفثذسزصش')),
    ('round', set('ouwqوؤضظ')),
    ('wide', set('eiyjيىئجچ')),
)
_DEFAULT_WORDS = [{'word': 'مرحبا', 'start': 0.20, 'end': 0.70},
                  {'word': 'hello', 'start': 0.90, 'end': 1.30}]


def _viseme_of(ch):
    c = ch.casefold()
    for vis, letters in _LETTER_RULES:
        if c in letters:
            return vis
    return 'open'


def viseme_track(*, words=None, fps=24.0, duration=None, **extra):
    """Rule-based mouth track from manually supplied word timings.

    words: [{word, start, end}] (Arabic or English), ordered and non-overlapping.
    Letters (diacritics and non-letters ignored) are mapped to one of
    closed/open/wide/round/teeth by simple written-letter rules, spread evenly
    over the word's span, and repeated visemes merged. Everything outside a word
    is 'closed'. Frame i samples time i / fps. This is NOT audio phoneme recognition.
    """
    _no_extra(extra)
    words = _DEFAULT_WORDS if words is None else words
    words = _list(words, 1, 200, 'words')
    parsed, last = [], 0.0
    for i, w in enumerate(words):
        _dict(w, f'words[{i}]', allowed={'word', 'start', 'end'}, required=('word', 'start', 'end'))
        if not isinstance(w['word'], str) or not 1 <= len(w['word']) <= 64:
            raise ValueError(f'words[{i}].word must be a 1..64 character string')
        start = _num(w['start'], 0, 3600, f'words[{i}].start')
        end = _num(w['end'], 0, 3600, f'words[{i}].end')
        if end <= start:
            raise ValueError(f'words[{i}] must have end > start')
        if start < last - 1e-12:
            raise ValueError('words must be ordered and non-overlapping')
        letters = [c for c in w['word'] if c.isalpha()]
        if not letters:
            raise ValueError(f'words[{i}] has no letters')
        parsed.append((w['word'], start, end, letters))
        last = end
    fps = _num(fps, 1, 240, 'fps')
    if duration is None:
        duration = last + 0.25
    duration = _num(duration, 0, 3600, 'duration', low_open=True)
    if duration < last:
        raise ValueError('duration must cover the last word')
    n = math.ceil(duration * fps - 1e-9)
    if not 1 <= n <= MAX_FRAMES:
        raise ValueError(f'duration * fps gives {n} frames; allowed 1..{MAX_FRAMES}')

    segments, cursor = [], 0.0
    word_ok = True
    for word, start, end, letters in parsed:
        if start > cursor:
            segments.append({'start': cursor, 'end': start, 'viseme': 'closed', 'word': None})
        step = (end - start) / len(letters)
        wsegs = []
        for k, ch in enumerate(letters):
            a = start + k * step
            b = end if k == len(letters) - 1 else start + (k + 1) * step
            v = _viseme_of(ch)
            if wsegs and wsegs[-1]['viseme'] == v:
                wsegs[-1]['end'] = b
                wsegs[-1]['letters'] += ch
            else:
                wsegs.append({'start': a, 'end': b, 'viseme': v, 'word': word, 'letters': ch})
        word_ok = word_ok and all(start <= s['start'] < s['end'] <= end for s in wsegs)
        segments.extend(wsegs)
        cursor = end
    if duration > cursor:
        segments.append({'start': cursor, 'end': duration, 'viseme': 'closed', 'word': None})

    track, gaps_closed = [], True
    j = 0
    for i in range(n):
        t = i / fps
        while j + 1 < len(segments) and segments[j]['end'] <= t:
            j += 1
        seg = segments[j]
        v = seg['viseme'] if seg['start'] <= t < seg['end'] or j == len(segments) - 1 else 'closed'
        in_word = any(s <= t < e for _, s, e, _ in parsed)
        if not in_word and v != 'closed':
            gaps_closed = False
        track.append(v)
    result = {
        'method': 'rule_based_letter_mapping', 'audio_phoneme_recognition': False,
        'note': 'mouth shapes come from written letters and supplied timings, not from audio',
        'viseme_set': list(VISEMES), 'fps': fps, 'duration': duration, 'frames': n,
        'segments': segments, 'track': track,
        'checks': {'visemes_inside_word_spans': word_ok, 'gaps_closed': gaps_closed},
    }
    return _pack('viseme_track', result,
                 ['word timings are supplied by the caller (manual or from an aligner) and trusted',
                  'letters map to 5 visible mouth shapes by spelling rules; letters share the word span evenly',
                  'silence between/around words is closed'],
                 ['NOT audio phoneme recognition; spelling is a rough proxy for pronunciation',
                  'no coarticulation, stress or speech-rate modelling; Arabic short vowels (harakat) ignored',
                  f'<= 200 words, <= {MAX_FRAMES} frames'])


# --------------------------------------------------------------------------- 14.06 landmark_smoothing

def _example_landmarks(seed):
    rng = random.Random(seed)
    base = [[300.0, 200.0], [340.0, 200.0], [320.0, 230.0], [305.0, 255.0], [335.0, 255.0]]
    fps = 30.0
    truth, track = [], []
    for f in range(90):
        t = f / fps
        dx = 10.0 * math.sin(2 * math.pi * 0.2 * t)
        dy = 5.0 * math.sin(2 * math.pi * 0.15 * t)
        gt = [[bx + dx, by + dy] for bx, by in base]
        noisy = [[x + rng.gauss(0, 3.0), y + rng.gauss(0, 3.0)] for x, y in gt]
        truth.append(gt)
        track.append(noisy)
    track[40][0] = [track[40][0][0] + 80.0, track[40][0][1] - 60.0]   # obvious outlier
    return track, truth


def _track(value, name):
    value = _list(value, 2, MAX_FRAMES, name)
    npts = None
    out = []
    for f, frame in enumerate(value):
        frame = _list(frame, 1, 100, f'{name}[{f}]')
        if npts is None:
            npts = len(frame)
        elif len(frame) != npts:
            raise ValueError(f'{name}: every frame must have the same number of points')
        out.append([_vec(p, 2, f'{name}[{f}][{j}]') for j, p in enumerate(frame)])
    return out


def _rms(a, b):
    tot, cnt = 0.0, 0
    for fa, fb in zip(a, b):
        for pa, pb in zip(fa, fb):
            tot += (pa[0] - pb[0]) ** 2 + (pa[1] - pb[1]) ** 2
            cnt += 1
    return math.sqrt(tot / cnt)


def landmark_smoothing(*, track=None, ground_truth=None, fps=30.0, filter='one_euro',
                       min_cutoff=1.0, beta=0.02, d_cutoff=1.0, alpha=0.3, window=2,
                       outlier_k=6.0, min_outlier_px=1.0, seed=7, **extra):
    """Outlier rejection + One-Euro or EMA smoothing of supplied 2D landmark tracks.

    track: [frame][point] = [x, y] (e.g. exported from a licensed reference
    clip's tracker). Outliers: a sample whose distance to the median of its
    +-window neighbours exceeds max(min_outlier_px, outlier_k * median residual
    of that point) is replaced by that median. Then each coordinate is filtered
    causally (One-Euro: cutoff = min_cutoff + beta * |filtered speed|; or EMA
    with `alpha`). If ground_truth (same shape) is given, RMS point error is
    reported before and after. With no track, a seeded synthetic example is used.
    """
    _no_extra(extra)
    example = track is None
    if example:
        track, gt_example = _example_landmarks(_int(seed, 0, 2 ** 31 - 1, 'seed'))
        if ground_truth is None:
            ground_truth = gt_example
    track = _track(track, 'track')
    if sum(len(f) for f in track) > 60000:
        raise ValueError('track may hold at most 60000 points in total')
    if ground_truth is not None:
        ground_truth = _track(ground_truth, 'ground_truth')
        if len(ground_truth) != len(track) or len(ground_truth[0]) != len(track[0]):
            raise ValueError('ground_truth must have the same shape as track')
    fps = _num(fps, 1, 1000, 'fps')
    filt = _choice(filter, {'one_euro', 'ema'}, 'filter')
    min_cutoff = _num(min_cutoff, 0, 100, 'min_cutoff', low_open=True)
    beta = _num(beta, 0, 100, 'beta')
    d_cutoff = _num(d_cutoff, 0, 100, 'd_cutoff', low_open=True)
    alpha = _num(alpha, 0, 1, 'alpha', low_open=True)
    window = _int(window, 1, 10, 'window')
    outlier_k = _num(outlier_k, 1, 100, 'outlier_k')
    min_outlier_px = _num(min_outlier_px, 0, 1e6, 'min_outlier_px')

    n, npts = len(track), len(track[0])
    cleaned = [[list(p) for p in frame] for frame in track]
    rejected = []
    for j in range(npts):
        meds, res = [], []
        for i in range(n):
            nb = [track[k][j] for k in range(max(0, i - window), min(n, i + window + 1)) if k != i]
            mx = statistics.median(p[0] for p in nb)
            my = statistics.median(p[1] for p in nb)
            meds.append((mx, my))
            res.append(math.hypot(track[i][j][0] - mx, track[i][j][1] - my))
        scale = statistics.median(res)
        thr = max(min_outlier_px, outlier_k * scale)
        for i in range(n):
            if res[i] > thr:
                cleaned[i][j] = [meds[i][0], meds[i][1]]
                rejected.append({'frame': i, 'point': j, 'residual_px': res[i], 'threshold_px': thr})

    te = 1.0 / fps

    def _a(cut):
        tau = 1.0 / (2 * math.pi * cut)
        return 1.0 / (1.0 + tau / te)

    smoothed = [[[0.0, 0.0] for _ in range(npts)] for _ in range(n)]
    for j in range(npts):
        for c in range(2):
            prev = cleaned[0][j][c]
            dprev = 0.0
            smoothed[0][j][c] = prev
            for i in range(1, n):
                x = cleaned[i][j][c]
                if filt == 'ema':
                    prev = alpha * x + (1 - alpha) * prev
                else:
                    dx = (x - prev) / te
                    ad = _a(d_cutoff)
                    dprev = ad * dx + (1 - ad) * dprev
                    cut = min_cutoff + beta * abs(dprev)
                    a = _a(cut)
                    prev = a * x + (1 - a) * prev
                smoothed[i][j][c] = prev
    errors = None
    if ground_truth is not None:
        before = _rms(track, ground_truth)
        mid = _rms(cleaned, ground_truth)
        after = _rms(smoothed, ground_truth)
        errors = {'rms_raw': before, 'rms_after_outlier_rejection': mid,
                  'rms_after_smoothing': after, 'improved': after < before,
                  'improvement_ratio': (before / after) if after > 0 else None}
    result = {
        'source': 'built-in synthetic example (seeded)' if example else 'caller-supplied track',
        'frames': n, 'points': npts, 'fps': fps, 'filter': filt,
        'filter_params': ({'min_cutoff': min_cutoff, 'beta': beta, 'd_cutoff': d_cutoff}
                          if filt == 'one_euro' else {'alpha': alpha}),
        'rejected': rejected[:500], 'rejected_count': len(rejected),
        'errors': errors, 'smoothed_track': smoothed,
    }
    return _pack('landmark_smoothing', result,
                 ['landmarks are supplied data (e.g. tracked from a reference clip the caller is licensed to use)',
                  'point identities are consistent across frames; no occlusion handling',
                  'causal filters (One-Euro / EMA) add some lag on fast motion',
                  'outlier test is a robust local-median residual per point'],
                 ['this op does not track video or detect faces; it only cleans given points',
                  'genuine fast motion can be mistaken for an outlier if outlier_k is too low',
                  f'<= {MAX_FRAMES} frames, <= 100 points per frame, <= 60000 points total',
                  'error figures need a caller-supplied ground truth (only the example has one built in)'])


# --------------------------------------------------------------------------- 14.07 identity_lock

_DEFAULT_REFERENCE = {
    'name': 'rose',
    'palette': {'hair': '#2b1d14', 'skin': '#e0ac69', 'coat': '#c14f64', 'eyes': '#3a5f8a'},
    'outfit': ['red coat', 'dark trousers', 'scarf'],
    'proportions': {'head_to_height': 0.2, 'shoulder_to_height': 0.26, 'leg_to_height': 0.48},
}
_DEFAULT_SHOTS = [
    {'shot': 's01', 'palette': {'hair': '#2b1d14', 'skin': '#e0ac69', 'coat': '#c14f64',
                                'eyes': '#3a5f8a'},
     'outfit': ['red coat', 'dark trousers', 'scarf'],
     'proportions': {'head_to_height': 0.2, 'shoulder_to_height': 0.26, 'leg_to_height': 0.48}},
    {'shot': 's02', 'palette': {'hair': '#2d1e15', 'skin': '#e2ab6a', 'coat': '#c25065',
                                'eyes': '#3b5e8b'},
     'outfit': ['scarf', 'red coat', 'dark trousers'],
     'proportions': {'head_to_height': 0.201, 'shoulder_to_height': 0.259, 'leg_to_height': 0.482}},
    {'shot': 's03', 'palette': {'hair': '#d4b04c', 'skin': '#e0ac69', 'coat': '#c14f64',
                                'eyes': '#3a5f8a'},
     'outfit': ['red coat', 'dark trousers', 'scarf'],
     'proportions': {'head_to_height': 0.2, 'shoulder_to_height': 0.26, 'leg_to_height': 0.48}},
]


def _attrs(d, name):
    pal = _palette(d['palette'], f'{name}.palette') if 'palette' in d else None
    outfit = None
    if 'outfit' in d:
        outfit = [_name(x, f'{name}.outfit item') for x in _list(d['outfit'], 0, 32, f'{name}.outfit')]
    props = None
    if 'proportions' in d:
        _dict(d['proportions'], f'{name}.proportions', max_len=32)
        props = {_name(k, f'{name}.proportions key'): _num(v, 0, 1e6, f'{name}.proportions[{k}]',
                                                            low_open=True)
                 for k, v in d['proportions'].items()}
    return pal, outfit, props


def identity_lock(*, reference=None, shots=None, color_tolerance=10.0,
                  proportion_tolerance=0.03, **extra):
    """Detect character attribute drift between a reference sheet and per-shot dumps.

    reference: {name?, palette {role: hex}, outfit [items], proportions {name: >0}}.
    shots: [{shot, palette?, outfit?, proportions?}] - attribute dumps from each
    render. Palette roles differing by more than color_tolerance (Euclidean RGB
    distance, 0..441.7) are flagged, as are missing/extra roles, missing/extra
    outfit items, and proportions whose relative error exceeds proportion_tolerance.
    """
    _no_extra(extra)
    if reference is None:
        reference = _DEFAULT_REFERENCE
        if shots is None:
            shots = _DEFAULT_SHOTS
    _dict(reference, 'reference', allowed={'name', 'palette', 'outfit', 'proportions'},
          required=('palette',))
    rpal, rout, rprop = _attrs(reference, 'reference')
    rout, rprop = rout or [], rprop or {}
    shots = _list([] if shots is None else shots, 0, 100, 'shots')
    color_tolerance = _num(color_tolerance, 0, 442, 'color_tolerance')
    proportion_tolerance = _num(proportion_tolerance, 0, 10, 'proportion_tolerance')
    reports, ids = [], set()
    for i, s in enumerate(shots):
        _dict(s, f'shots[{i}]', allowed={'shot', 'palette', 'outfit', 'proportions'},
              required=('shot',))
        sid = _name(s['shot'], f'shots[{i}].shot')
        if sid in ids:
            raise ValueError(f'duplicate shot id {sid!r}')
        ids.add(sid)
        pal, out, prop = _attrs(s, f'shots[{i}]')
        issues = []
        if pal is None:
            issues.append({'kind': 'palette', 'key': None, 'change': 'missing_section'})
        else:
            for role, rgb in rpal.items():
                if role not in pal:
                    issues.append({'kind': 'palette', 'key': role, 'change': 'missing',
                                   'expected': _hex(rgb)})
                    continue
                d = _rgb_dist(rgb, pal[role])
                if d > color_tolerance:
                    issues.append({'kind': 'palette', 'key': role, 'change': 'colour',
                                   'expected': _hex(rgb), 'found': _hex(pal[role]),
                                   'delta': d, 'tolerance': color_tolerance})
            for role in sorted(set(pal) - set(rpal)):
                issues.append({'kind': 'palette', 'key': role, 'change': 'extra',
                               'found': _hex(pal[role])})
        if rout:
            if out is None:
                issues.append({'kind': 'outfit', 'key': None, 'change': 'missing_section'})
            else:
                for item in sorted(set(rout) - set(out)):
                    issues.append({'kind': 'outfit', 'key': item, 'change': 'missing'})
                for item in sorted(set(out) - set(rout)):
                    issues.append({'kind': 'outfit', 'key': item, 'change': 'extra'})
        if rprop:
            if prop is None:
                issues.append({'kind': 'proportion', 'key': None, 'change': 'missing_section'})
            else:
                for k, v in rprop.items():
                    if k not in prop:
                        issues.append({'kind': 'proportion', 'key': k, 'change': 'missing'})
                        continue
                    rel = abs(prop[k] - v) / v
                    if rel > proportion_tolerance:
                        issues.append({'kind': 'proportion', 'key': k, 'change': 'value',
                                       'expected': v, 'found': prop[k], 'relative_error': rel,
                                       'tolerance': proportion_tolerance})
        reports.append({'shot': sid, 'consistent': not issues, 'issues': issues})
    result = {
        'character': reference.get('name') if isinstance(reference.get('name'), str) else None,
        'reference': {'palette': {k: _hex(v) for k, v in rpal.items()}, 'outfit': rout,
                      'proportions': rprop},
        'color_tolerance': color_tolerance, 'proportion_tolerance': proportion_tolerance,
        'shots': reports,
        'drifted_shots': [r['shot'] for r in reports if not r['consistent']],
        'all_consistent': all(r['consistent'] for r in reports),
    }
    return _pack('identity_lock', result,
                 ['attribute dumps are supplied per shot (from the renderer/scene data), not measured from pixels',
                  'colour difference is Euclidean distance in sRGB 0..255 (not perceptual Delta E)',
                  'proportions compared by relative error; outfit items compared as exact names'],
                 ['art-direction consistency check, not face recognition or photoreal identity',
                  '<= 32 palette roles / outfit items / proportions, <= 100 shots'])


# --------------------------------------------------------------------------- 14.08 hand_grip

_DEFAULT_OBJECT = {'shape': 'circle', 'center': [0.42, 1.12], 'radius': 0.06}


def _object(obj):
    _dict(obj, 'object', allowed={'shape', 'center', 'radius', 'size'}, required=('shape', 'center'))
    shape = _choice(obj['shape'], {'circle', 'box'}, 'object.shape')
    center = _vec(obj['center'], 2, 'object.center')
    if shape == 'circle':
        if 'size' in obj:
            raise ValueError('circle objects take radius, not size')
        return {'shape': shape, 'center': center,
                'radius': _num(obj.get('radius', 0.05), 0, 1e4, 'object.radius', low_open=True)}
    if 'radius' in obj:
        raise ValueError('box objects take size [w, h], not radius')
    size = _vec(obj.get('size', [0.1, 0.1]), 2, 'object.size', low=0, high=1e4)
    if min(size) <= 0:
        raise ValueError('object.size entries must be > 0')
    return {'shape': shape, 'center': center, 'size': size}


def _sdf(obj, p):
    cx, cy = obj['center']
    if obj['shape'] == 'circle':
        return math.hypot(p[0] - cx, p[1] - cy) - obj['radius']
    hx, hy = obj['size'][0] / 2, obj['size'][1] / 2
    qx, qy = abs(p[0] - cx) - hx, abs(p[1] - cy) - hy
    return math.hypot(max(qx, 0.0), max(qy, 0.0)) + min(max(qx, qy), 0.0)


def _contact(obj, shoulder, angle):
    cx, cy = obj['center']
    if obj['shape'] == 'circle':
        if angle is None:
            dx, dy = shoulder[0] - cx, shoulder[1] - cy
            d = math.hypot(dx, dy)
            if d <= obj['radius']:
                raise ValueError('shoulder is inside the object')
            nx, ny = dx / d, dy / d
        else:
            a = math.radians(angle)
            nx, ny = math.cos(a), math.sin(a)
        r = obj['radius']
        return [cx + r * nx, cy + r * ny], [nx, ny]
    if angle is not None:
        raise ValueError('contact_angle_deg applies to circle objects only')
    hx, hy = obj['size'][0] / 2, obj['size'][1] / 2
    px, py = shoulder[0] - cx, shoulder[1] - cy
    if abs(px) <= hx and abs(py) <= hy:
        raise ValueError('shoulder is inside the object')
    # face of the box most facing the shoulder (by normalised coordinate)
    if abs(px) / hx >= abs(py) / hy:
        nx, ny = math.copysign(1.0, px), 0.0
        return [cx + nx * hx, cy + min(max(py, -hy), hy)], [nx, ny]
    nx, ny = 0.0, math.copysign(1.0, py)
    return [cx + min(max(px, -hx), hx), cy + ny * hy], [nx, ny]


def hand_grip(*, shoulder=(0.0, 1.4), upper_arm=0.30, forearm=0.28, hand=0.08,
              object=None, contact_angle_deg=None, elbow='right', fingers=3,
              finger_length=0.05, skin_margin=0.002, contact_tolerance=1e-6,
              penetration_tolerance=1e-9, **extra):
    """Arm IK to a grip contact on a circle or box, with a non-penetration check.

    Contact point: for a circle, the surface point facing the shoulder (or at
    contact_angle_deg); for a box, the closest point on the face that faces the
    shoulder. The palm (hand bone end) sits on the contact point; the wrist is
    `hand` out along the outward normal, and the arm reaches the wrist with
    geometry_v20.ik_two_bone. Fingers wrap along the surface offset by
    skin_margin. Signed distance (> 0 outside) is sampled along every bone and
    finger; penetration is any sample below -penetration_tolerance.
    """
    _no_extra(extra)
    shoulder = _vec(shoulder, 2, 'shoulder')
    upper_arm = _num(upper_arm, 0, 1e4, 'upper_arm', low_open=True)
    forearm = _num(forearm, 0, 1e4, 'forearm', low_open=True)
    hand = _num(hand, 0, 1e4, 'hand', low_open=True)
    obj = _object(_DEFAULT_OBJECT if object is None else object)
    if contact_angle_deg is not None:
        contact_angle_deg = _num(contact_angle_deg, -360, 360, 'contact_angle_deg')
    elbow = _choice(elbow, {'left', 'right'}, 'elbow')
    fingers = _int(fingers, 1, 5, 'fingers')
    finger_length = _num(finger_length, 0, 1e4, 'finger_length', low_open=True)
    skin_margin = _num(skin_margin, 0, 1e3, 'skin_margin')
    contact_tolerance = _num(contact_tolerance, 0, 1, 'contact_tolerance')
    penetration_tolerance = _num(penetration_tolerance, 0, 1, 'penetration_tolerance')

    contact, normal = _contact(obj, shoulder, contact_angle_deg)
    wrist_target = [contact[0] + hand * normal[0], contact[1] + hand * normal[1]]
    ik = geometry_v20.ik_two_bone(l1=upper_arm, l2=forearm, target=wrist_target,
                                  root=shoulder, elbow=elbow)
    wrist = ik['end']
    hx, hy = contact[0] - wrist[0], contact[1] - wrist[1]
    hn = math.hypot(hx, hy) or 1.0
    palm = [wrist[0] + hand * hx / hn, wrist[1] + hand * hy / hn]
    contact_error = math.hypot(palm[0] - contact[0], palm[1] - contact[1])

    finger_paths = []
    spread = [0.0] if fingers == 1 else [-1 + 2 * k / (fingers - 1) for k in range(fingers)]
    for k, sgn in enumerate(spread):
        path = []
        for s in range(9):
            frac = s / 8
            if obj['shape'] == 'circle':
                rr = obj['radius'] + skin_margin
                base = math.atan2(normal[1], normal[0])
                # each finger wraps over the surface, fanning out to either side
                ang = base - (1 if sgn >= 0 else -1) * frac * finger_length / rr
                ang += sgn * 0.15 * finger_length / rr
                path.append([obj['center'][0] + rr * math.cos(ang), obj['center'][1] + rr * math.sin(ang)])
            else:
                tx, ty = -normal[1], normal[0]
                side = 1 if sgn >= 0 else -1
                along = side * frac * finger_length + sgn * 0.15 * finger_length
                path.append([contact[0] + normal[0] * skin_margin + tx * along,
                             contact[1] + normal[1] * skin_margin + ty * along])
        finger_paths.append(path)

    def seg_samples(a, b, n=24):
        return [[a[0] + (b[0] - a[0]) * t / n, a[1] + (b[1] - a[1]) * t / n] for t in range(n + 1)]

    parts = {'upper_arm': seg_samples(shoulder, ik['joint']),
             'forearm': seg_samples(ik['joint'], wrist),
             'hand': seg_samples(wrist, palm)}
    for k, path in enumerate(finger_paths):
        parts[f'finger_{k}'] = path
    min_sd = {name: min(_sdf(obj, p) for p in pts) for name, pts in parts.items()}
    overall = min(min_sd.values())
    penetrates = overall < -penetration_tolerance
    result = {
        'object': obj, 'contact_point': contact, 'surface_normal': normal,
        'shoulder': shoulder, 'elbow': ik['joint'], 'wrist': wrist, 'palm': palm,
        'arm_reachable': ik['reachable'], 'arm_notes': ik['notes'],
        'contact_error': contact_error, 'contact_tolerance': contact_tolerance,
        'reached': contact_error <= contact_tolerance,
        'fingers': finger_paths,
        'min_signed_distance_by_part': min_sd, 'min_signed_distance': overall,
        'penetration_tolerance': penetration_tolerance, 'penetrates': penetrates,
        'grip_ok': contact_error <= contact_tolerance and not penetrates,
    }
    return _pack('hand_grip', result,
                 ['2D; arm = two bones solved by geometry_v20.ik_two_bone, hand = rigid bone along the surface normal',
                  'bones and fingers are zero-thickness curves sampled for the signed-distance test',
                  'fingers are placed on the surface offset by skin_margin, not simulated'],
                 ['no grip forces, friction or object dynamics; object is static',
                  'unreachable contact is reported (reached = false), arm is clamped by the IK',
                  'penetration tested at sample points only (25 per bone, 9 per finger)'])


# --------------------------------------------------------------------------- 14.09 secondary_motion

def secondary_motion(*, segments=4, segment_length=0.12, frequency_hz=6.0, damping_ratio=0.9,
                     amplitude=0.3, move_frames=15, frames=180, fps=60.0, substeps=8,
                     max_lag_frames=15.0, settle_tolerance=0.01, max_samples=61, **extra):
    """Hair/cloth chain of spring-damper links following a parent that moves then stops.

    Parent (root) moves horizontally by `amplitude` over move_frames with a
    min-jerk ease, then holds. Each link i obeys
    x_i'' = w^2 (x_{i-1} - x_i) + 2 zeta w (x_{i-1}' - x_i'), w = 2 pi frequency_hz,
    integrated with RK4 substeps. Displayed node positions keep segment lengths
    (link angle from the horizontal offset). Reports tip lag (frames between the
    parent and the tip crossing 50 % of the move), overshoot, and when the chain
    settles within settle_tolerance * |amplitude| after the parent stops. A lag
    above max_lag_frames is rejected as unphysical for a secondary layer.
    A single link is cross-checked with physics_v20.spring.
    """
    _no_extra(extra)
    nseg = _int(segments, 1, 20, 'segments')
    seg_len = _num(segment_length, 0, 1e4, 'segment_length', low_open=True)
    freq = _num(frequency_hz, 0.2, 20, 'frequency_hz')
    zeta = _num(damping_ratio, 0.05, 3, 'damping_ratio')
    amp = _num(amplitude, -10, 10, 'amplitude')
    if amp == 0:
        raise ValueError('amplitude must be non-zero')
    frames = _int(frames, 4, MAX_FRAMES, 'frames')
    move_frames = _int(move_frames, 1, frames - 2, 'move_frames')
    fps = _num(fps, 1, 240, 'fps')
    substeps = _int(substeps, 1, 64, 'substeps')
    max_lag = _num(max_lag_frames, 0, MAX_FRAMES, 'max_lag_frames', low_open=True)
    tol = _num(settle_tolerance, 1e-6, 1, 'settle_tolerance')
    max_samples = _int(max_samples, 2, MAX_FRAMES + 1, 'max_samples')
    w = 2 * math.pi * freq
    h = 1.0 / (fps * substeps)
    fastest = 2 * w * max(1.0, 2 * zeta)
    if h * fastest > 0.5:
        raise ValueError(f'step too large for this stiffness: raise substeps or fps '
                         f'(need 1/(fps*substeps) <= {0.5 / fastest:.3g} s)')
    t_move = move_frames / fps

    def parent(t):
        if t >= t_move:
            return amp, 0.0
        u = max(t, 0.0) / t_move
        return amp * _minjerk(u), amp * _minjerk_d(u) / t_move

    w2, c = w * w, 2 * zeta * w

    def deriv(t, s):
        px, pv = parent(t)
        out = [0.0] * (2 * nseg)
        for i in range(nseg):
            x, v = s[2 * i], s[2 * i + 1]
            ux, uv = (px, pv) if i == 0 else (s[2 * i - 2], s[2 * i - 1])
            out[2 * i] = v
            out[2 * i + 1] = w2 * (ux - x) + c * (uv - v)
        return out

    state = [0.0] * (2 * nseg)
    xs = [[0.0] * (nseg + 1)]
    vel = [[0.0] * nseg]
    t = 0.0
    for f in range(1, frames + 1):
        for _ in range(substeps):
            k1 = deriv(t, state)
            k2 = deriv(t + h / 2, [a + h / 2 * b for a, b in zip(state, k1)])
            k3 = deriv(t + h / 2, [a + h / 2 * b for a, b in zip(state, k2)])
            k4 = deriv(t + h, [a + h * b for a, b in zip(state, k3)])
            state = [a + h / 6 * (p + 2 * q + 2 * r + z) for a, p, q, r, z in zip(state, k1, k2, k3, k4)]
            t += h
        t = f / fps
        xs.append([parent(t)[0]] + [state[2 * i] for i in range(nseg)])
        vel.append([state[2 * i + 1] for i in range(nseg)])

    def cross(col):
        for f in range(1, len(xs)):
            a, b = xs[f - 1][col] / amp, xs[f][col] / amp
            if a < 0.5 <= b:
                return f - 1 + (0.5 - a) / (b - a)
        return None

    fp, ft = cross(0), cross(nseg)
    if ft is None:
        raise ValueError('tip never reached half of the parent move within the clip: '
                         'lag is unphysically long; stiffen the chain or lengthen frames')
    lag = ft - fp
    if lag > max_lag:
        raise ValueError(f'tip lag {lag:.2f} frames exceeds max_lag_frames={max_lag}: '
                         'raise frequency_hz or lower damping_ratio')
    overshoot = max(0.0, max(row[nseg] / amp for row in xs) - 1.0)
    band = tol * abs(amp)
    settle_frame = None
    for f in range(frames, move_frames - 1, -1):
        if all(abs(x - amp) <= band for x in xs[f]):
            settle_frame = f
        else:
            break
    settled = settle_frame is not None and settle_frame < frames
    disp = []
    for f, row in enumerate(xs):
        pts = [[row[0], 0.0]]
        for i in range(1, nseg + 1):
            sx = min(1.0, max(-1.0, (row[i] - row[i - 1]) / seg_len))
            pts.append([pts[-1][0] + seg_len * sx, pts[-1][1] - seg_len * math.sqrt(1 - sx * sx)])
        disp.append({'frame': f, 'nodes': pts})
    ref_fastest = w * (zeta + math.sqrt(zeta * zeta - 1)) if zeta > 1 else w
    ref = physics_v20.spring(m=1.0, k=w2, c=c, x0=1.0, v0=0.0, duration=min(5.0, 20.0 / freq),
                             dt=min(0.001, 0.4 / ref_fastest), max_samples=2)['result']
    result = {
        'segments': nseg, 'segment_length': seg_len, 'frequency_hz': freq,
        'damping_ratio': zeta, 'fps': fps, 'frames': frames, 'move_frames': move_frames,
        'tip_lag_frames': lag, 'max_lag_frames': max_lag,
        'tip_overshoot_ratio': overshoot,
        'parent_stop_frame': move_frames,
        'settle_frame': settle_frame if settled else None,
        'settle_frames_after_stop': (settle_frame - move_frames) if settled else None,
        'settled': settled, 'settle_band': band,
        'final_max_speed': max(abs(v) for v in vel[-1]),
        'single_link_reference': {'damping_ratio': ref['damping_ratio'], 'regime': ref['regime'],
                                  'overshoot_ratio': ref['overshoot_ratio'],
                                  'source': 'physics_v20.spring'},
        'samples': _decimate(disp, max_samples),
    }
    return _pack('secondary_motion', result,
                 ['linear spring-damper links acting on horizontal offsets (small-angle sway)',
                  'parent motion is prescribed (min-jerk move then hold); chain has no gravity or collisions',
                  'display positions convert offsets to link angles so segment lengths are kept'],
                 ['not a cloth/hair solver: no strand collisions, wind or twisting',
                  f'<= 20 segments, <= {MAX_FRAMES} frames, RK4 step guard (1/(fps*substeps) * 2w * max(1, 2 zeta) <= 0.5)',
                  'tip lag above max_lag_frames is rejected with ValueError',
                  f'samples decimated to <= {max_samples}'])


# --------------------------------------------------------------------------- 14.10 crowd_layers

_DEFAULT_CROWD = [
    {'id': 'rose', 'shot': 'market', 'z': 1.0, 'time': [0.0, 6.0],
     'palette': {'hair': '#2b1d14', 'coat': '#c14f64', 'skin': '#e0ac69'}},
    {'id': 'baker', 'shot': 'market', 'z': 3.0, 'time': [0.0, 6.0],
     'palette': {'hair': '#5a4632', 'coat': '#f2e6c9', 'skin': '#c68642'}},
    {'id': 'kid', 'shot': 'market', 'z': 2.0, 'time': [2.0, 5.0],
     'palette': {'hair': '#111111', 'coat': '#2f7d5b', 'skin': '#8d5524'}},
]


def crowd_layers(*, characters=None, palette_tolerance=6.0, **extra):
    """Manage a crowd: unique ids, palette sets, z/time layers and depth order.

    characters: [{id, palette {role: hex}, shot?='main', z?=0 (larger = farther),
    time?=[start, end] seconds}]. Flags duplicate ids (anywhere), and colour
    collisions: two characters in the same shot whose palettes have the same roles
    with every role within palette_tolerance (Euclidean RGB). Draw order per
    shot is back to front (descending z, ties broken by id); equal z with
    overlapping time is reported as a tie warning.
    """
    _no_extra(extra)
    chars = _DEFAULT_CROWD if characters is None else characters
    chars = _list(chars, 1, MAX_CHARACTERS, 'characters')
    tol = _num(palette_tolerance, 0, 442, 'palette_tolerance')
    parsed = []
    for i, ch in enumerate(chars):
        _dict(ch, f'characters[{i}]', allowed={'id', 'palette', 'shot', 'z', 'time'},
              required=('id', 'palette'))
        cid = _name(ch['id'], f'characters[{i}].id')
        pal = _palette(ch['palette'], f'characters[{i}].palette')
        shot = _name(ch.get('shot', 'main'), f'characters[{i}].shot')
        z = _num(ch.get('z', 0.0), -1e6, 1e6, f'characters[{i}].z')
        tm = ch.get('time')
        if tm is not None:
            tm = _vec(tm, 2, f'characters[{i}].time', low=0, high=1e6)
            if tm[1] <= tm[0]:
                raise ValueError(f'characters[{i}].time must have end > start')
        parsed.append({'index': i, 'id': cid, 'shot': shot, 'z': z, 'time': tm, 'palette': pal})

    def overlap(a, b):
        if a is None or b is None:
            return True
        return a[0] < b[1] and b[0] < a[1]

    id_coll = {}
    for p in parsed:
        id_coll.setdefault(p['id'], []).append(p['index'])
    id_collisions = [{'id': k, 'indices': v, 'shots': sorted({parsed[i]['shot'] for i in v})}
                     for k, v in id_coll.items() if len(v) > 1]
    colour_collisions, ties = [], []
    for a in range(len(parsed)):
        for b in range(a + 1, len(parsed)):
            pa, pb = parsed[a], parsed[b]
            if pa['shot'] != pb['shot']:
                continue
            if set(pa['palette']) == set(pb['palette']):
                worst = max(_rgb_dist(pa['palette'][r], pb['palette'][r]) for r in pa['palette'])
                if worst <= tol:
                    colour_collisions.append({'shot': pa['shot'], 'a': pa['id'], 'b': pb['id'],
                                              'indices': [pa['index'], pb['index']],
                                              'max_role_distance': worst})
            if pa['z'] == pb['z'] and overlap(pa['time'], pb['time']):
                ties.append({'shot': pa['shot'], 'a': pa['id'], 'b': pb['id'], 'z': pa['z']})
    layers = {}
    for shot in sorted({p['shot'] for p in parsed}):
        members = sorted((p for p in parsed if p['shot'] == shot),
                         key=lambda p: (-p['z'], p['id'], p['index']))
        layers[shot] = [{'draw_index': k, 'id': p['id'], 'z': p['z'], 'time': p['time'],
                         'palette': {r: _hex(c) for r, c in p['palette'].items()}}
                        for k, p in enumerate(members)]
    result = {
        'count': len(parsed), 'palette_tolerance': tol,
        'id_collisions': id_collisions, 'colour_collisions': colour_collisions,
        'z_ties': ties, 'layers': layers,
        'valid': not id_collisions and not colour_collisions,
    }
    return _pack('crowd_layers', result,
                 ['z is depth from camera (larger = farther, drawn first); time ranges in seconds',
                  'colour collision = same palette roles, every role within palette_tolerance (Euclidean sRGB)',
                  'ids must be unique across the whole crowd, not only per shot'],
                 [f'<= {MAX_CHARACTERS} characters, <= 32 palette roles each',
                  'no crowd simulation, path planning or occlusion rendering; z ties are warnings only'])


# --------------------------------------------------------------------------- dispatcher

OPS = {
    'skeleton': skeleton, 'walk_cycle': walk_cycle, 'run_cycle': run_cycle,
    'expressions': expressions, 'viseme_track': viseme_track,
    'landmark_smoothing': landmark_smoothing, 'identity_lock': identity_lock,
    'hand_grip': hand_grip, 'secondary_motion': secondary_motion, 'crowd_layers': crowd_layers,
}


def run(op, params=None):
    """Validate and dispatch: run('walk_cycle', {'frames': 24}) -> {'op','result','assumptions','limits'}."""
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
