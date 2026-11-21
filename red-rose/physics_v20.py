"""Red Rose V20: small, bounded, deterministic physics helpers for motion work.

Pure standard-library Python. No file I/O, no subprocess, no network, no printing.
Every op validates its inputs strictly (ValueError on bools-as-numbers,
non-finite values, unknown parameter names and out-of-range values) and caps
its work (steps, particles, iterations, durations) so it cannot run away.

These are teaching/previz-grade models, not engineering solvers: each op
returns the assumptions it makes and the limits it enforces next to its result.
Units are SI unless stated (metres, seconds, kilograms); motion_blur works in
whatever unit the caller's positions use (pixels or metres).
"""
from __future__ import annotations

import json
import math
import random

MAX_PARAMS = 24
MAX_STEPS = 200_000
MAX_SAMPLES = 2_001

TOPICS = {
    '08.01': 'fall',
    '08.02': 'collide',
    '08.03': 'friction',
    '08.04': 'spring',
    '08.05': 'projectile',
    '08.06': 'cloth',
    '08.07': 'motion_blur',
    '08.08': 'flow',
    '08.09': 'shading',
    '08.10': 'particles',
}

TOPIC_NAMES_AR = {
    '08.01': 'السقوط تحت الجاذبية',
    '08.02': 'التصادم وارتداد الأجسام',
    '08.03': 'الاحتكاك وانزلاق القدم',
    '08.04': 'تذبذب النوابض',
    '08.05': 'مسارات المقذوفات',
    '08.06': 'حركة القماش والرايات',
    '08.07': 'التصوير بحركة ضبابية',
    '08.08': 'ديناميكا السوائل المبسطة',
    '08.09': 'انتقال الضوء على المواد',
    '08.10': 'محاكاة الغبار والثلج',
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


def _vec(value, sizes, name, low=-1e6, high=1e6):
    if isinstance(sizes, int):
        sizes = (sizes,)
    if not isinstance(value, (list, tuple)) or len(value) not in sizes:
        raise ValueError(f'{name} must be a list of {" or ".join(map(str, sizes))} numbers')
    return [_num(v, low, high, f'{name}[{i}]') for i, v in enumerate(value)]


def _unit(value, name):
    v = _vec(value, 3, name)
    n = math.sqrt(sum(c * c for c in v))
    if n < 1e-12:
        raise ValueError(f'{name} must not be the zero vector')
    return [c / n for c in v]


def _steps(duration, dt, name='duration/dt'):
    steps = math.ceil(duration / dt - 1e-9)
    if not 1 <= steps <= MAX_STEPS:
        raise ValueError(f'{name} needs {steps} steps; allowed 1..{MAX_STEPS}')
    return steps


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


def _rk4(state, deriv, h):
    k1 = deriv(state)
    k2 = deriv([s + h / 2 * k for s, k in zip(state, k1)])
    k3 = deriv([s + h / 2 * k for s, k in zip(state, k2)])
    k4 = deriv([s + h * k for s, k in zip(state, k3)])
    return [s + h / 6 * (a + 2 * b + 2 * c + d)
            for s, a, b, c, d in zip(state, k1, k2, k3, k4)]


# --------------------------------------------------------------------------- 08.01 fall

def fall(*, y0=10.0, v0=0.0, g=9.81, duration=1.0, dt=0.01,
         integrator='rk4', max_samples=201, **extra):
    """Fixed-step 1D motion under constant downward acceleration g.

    integrator: 'semi_implicit_euler' (first order, v then y) or 'rk4'.
    The step actually used is duration/ceil(duration/dt) (<= dt, so the run
    ends exactly at `duration`). No ground: y may go negative. Returns a
    sampled trajectory [[t, y, v], ...] (<= max_samples points) and the error
    against the analytic y0 + v0 t - g t^2 / 2.
    """
    _no_extra(extra)
    y0 = _num(y0, -1e6, 1e6, 'y0')
    v0 = _num(v0, -1e4, 1e4, 'v0')
    g = _num(g, 0, 1000, 'g')
    duration = _num(duration, 0, 3600, 'duration', low_open=True)
    dt = _num(dt, 1e-6, 1.0, 'dt')
    integrator = _choice(integrator, {'semi_implicit_euler', 'rk4'}, 'integrator')
    max_samples = _int(max_samples, 2, MAX_SAMPLES, 'max_samples')
    steps = _steps(duration, dt)
    h = duration / steps
    a = -g

    def exact(t):
        return y0 + v0 * t + 0.5 * a * t * t

    y, v = y0, v0
    traj = [[0.0, y, v]]
    max_err = 0.0
    for i in range(1, steps + 1):
        if integrator == 'rk4':
            y, v = _rk4([y, v], lambda s: [s[1], a], h)
        else:
            v += a * h
            y += v * h
        t = i * h
        max_err = max(max_err, abs(y - exact(t)))
        traj.append([t, y, v])
    result = {
        'integrator': integrator, 'dt_used': h, 'steps': steps,
        'final': {'t': duration, 'y': y, 'v': v},
        'analytic_final': {'y': exact(duration), 'v': v0 + a * duration},
        'final_abs_error_y': abs(y - exact(duration)),
        'max_abs_error_y': max_err,
        'trajectory': _decimate(traj, max_samples),
    }
    return _pack('fall', result,
                 ['rigid point mass, no air drag', 'constant uniform gravity g (downward = -y)',
                  'no ground or collisions; y may become negative',
                  'semi-implicit Euler is first-order accurate; RK4 is exact (to rounding) for constant acceleration'],
                 [f'steps <= {MAX_STEPS}', 'duration <= 3600 s', 'dt in [1e-6, 1] s',
                  f'trajectory decimated to <= {max_samples} samples'])


# --------------------------------------------------------------------------- 08.02 collide

def collide(*, m1=1.0, v1=1.0, m2=1.0, v2=0.0, e=1.0, drop_height=1.0, g=9.81,
            max_bounces=50, rest_height=1e-4, **extra):
    """1D two-body collision with restitution e, plus a ball bouncing on rigid ground.

    Pair: v1' = (p + m2 e (v2 - v1)) / (m1 + m2), v2' = (p + m1 e (v1 - v2)) / (m1 + m2).
    Bounce: dropped from drop_height at rest; each impact multiplies speed by e,
    so apex heights scale by e^2. Stops when the next apex < rest_height or after
    max_bounces impacts. drop_height = 0 skips the bounce sequence.
    """
    _no_extra(extra)
    m1 = _num(m1, 0, 1e6, 'm1', low_open=True)
    m2 = _num(m2, 0, 1e6, 'm2', low_open=True)
    v1 = _num(v1, -1e4, 1e4, 'v1')
    v2 = _num(v2, -1e4, 1e4, 'v2')
    e = _num(e, 0, 1, 'e')
    drop_height = _num(drop_height, 0, 1e4, 'drop_height')
    g = _num(g, 0, 1000, 'g', low_open=True)
    max_bounces = _int(max_bounces, 1, 500, 'max_bounces')
    rest_height = _num(rest_height, 0, 1e3, 'rest_height', low_open=True)

    total = m1 + m2
    p = m1 * v1 + m2 * v2
    u1 = (p + m2 * e * (v2 - v1)) / total
    u2 = (p + m1 * e * (v1 - v2)) / total
    ke_before = 0.5 * m1 * v1 * v1 + 0.5 * m2 * v2 * v2
    ke_after = 0.5 * m1 * u1 * u1 + 0.5 * m2 * u2 * u2
    mu = m1 * m2 / total
    approaching = (v1 - v2) > 0
    pair = {
        'v1_after': u1, 'v2_after': u2,
        'momentum_before': p, 'momentum_after': m1 * u1 + m2 * u2,
        'kinetic_energy_before': ke_before, 'kinetic_energy_after': ke_after,
        'predicted_energy_loss': 0.5 * mu * (1 - e * e) * (v1 - v2) ** 2,
        'approaching': approaching,
    }

    bounce = {'apex_heights': [], 'impacts': [], 'at_rest': False}
    if drop_height > 0:
        speed = math.sqrt(2 * g * drop_height)
        t = math.sqrt(2 * drop_height / g)
        apexes = [drop_height]
        impacts = []
        at_rest = False
        for _ in range(max_bounces):
            impacts.append({'t': t, 'impact_speed': speed})
            speed *= e
            apex = speed * speed / (2 * g)
            if apex < rest_height:
                at_rest = True
                break
            apexes.append(apex)
            t += 2 * speed / g
        zeno = None
        if e < 1:
            v_first = math.sqrt(2 * g * drop_height)
            zeno = math.sqrt(2 * drop_height / g) + 2 * v_first * e / (g * (1 - e))
        bounce = {'apex_heights': apexes, 'impacts': impacts, 'at_rest': at_rest,
                  'analytic_time_to_rest': zeno}
    return _pack('collide', {'pair': pair, 'bounce': bounce},
                 ['rigid point bodies, instantaneous 1D impact', 'constant restitution e (no speed dependence)',
                  'pair formula applies only if the bodies actually approach (see approaching)',
                  'ground is rigid and infinitely heavy; no air drag'],
                 ['masses in (0, 1e6] kg, |v| <= 1e4 m/s', f'bounces <= {max_bounces} (cap 500)',
                  'bounce sequence ends when next apex < rest_height'])


# --------------------------------------------------------------------------- 08.03 friction

def friction(*, v0=5.0, mass=1.0, mu_s=0.6, mu_k=0.4, g=9.81, applied_force=0.0,
             y0=0.0, duration=5.0, dt=0.001, max_samples=201, **extra):
    """Body sliding along flat ground (x) with Coulomb friction and ground constraint y >= 0.

    While in contact, normal force = m g. At rest it stays put if
    |applied_force| <= mu_s m g; while sliding, kinetic friction mu_k m g opposes
    the velocity. Each step integrates the constant acceleration exactly and,
    if friction would reverse the motion within a step, stops the body at the
    exact zero-velocity instant (so friction never reverses direction). A body
    released above ground (y0 > 0) falls with no friction until contact,
    where its vertical velocity is zeroed (perfectly inelastic landing).
    """
    _no_extra(extra)
    v0 = _num(v0, -1e3, 1e3, 'v0')
    mass = _num(mass, 0, 1e6, 'mass', low_open=True)
    mu_s = _num(mu_s, 0, 2, 'mu_s')
    mu_k = _num(mu_k, 0, 2, 'mu_k')
    if mu_k > mu_s:
        raise ValueError('mu_k must be <= mu_s')
    g = _num(g, 0, 1000, 'g', low_open=True)
    applied_force = _num(applied_force, -1e6, 1e6, 'applied_force')
    y0 = _num(y0, 0, 1e3, 'y0')
    duration = _num(duration, 0, 600, 'duration', low_open=True)
    dt = _num(dt, 1e-5, 0.1, 'dt')
    max_samples = _int(max_samples, 2, MAX_SAMPLES, 'max_samples')
    steps = _steps(duration, dt)
    h = duration / steps

    normal = mass * g
    x, y, vx, vy = 0.0, y0, v0, 0.0
    samples = [[0.0, x, y, vx]]
    stop_time = 0.0 if v0 == 0 else None
    reversals = 0
    static_hold = False
    min_y = y
    first_sliding_accel = None
    for i in range(1, steps + 1):
        contact = y <= 0.0 and vy <= 0.0
        ax_free = applied_force / mass
        if not contact:
            x += vx * h + 0.5 * ax_free * h * h
            vx += ax_free * h
            vy -= g * h
            y += vy * h
            if y < 0.0:
                y, vy = 0.0, 0.0
        elif vx == 0.0:
            if abs(applied_force) <= mu_s * normal:
                static_hold = True
            else:
                a = (applied_force - math.copysign(mu_k * normal, applied_force)) / mass
                x += 0.5 * a * h * h
                vx = a * h
        else:
            a = (applied_force - math.copysign(mu_k * normal, vx)) / mass
            if first_sliding_accel is None:
                first_sliding_accel = a
            nv = vx + a * h
            if a != 0 and (a > 0) != (vx > 0) and (nv == 0 or (nv > 0) != (vx > 0)):
                t_stop = -vx / a
                x += vx * t_stop + 0.5 * a * t_stop * t_stop
                vx = 0.0
                if stop_time is None:
                    stop_time = (i - 1) * h + t_stop
            else:
                if nv != 0 and (nv > 0) != (vx > 0):
                    reversals += 1
                x += vx * h + 0.5 * a * h * h
                vx = nv
        min_y = min(min_y, y)
        samples.append([i * h, x, y, vx])
    analytic = None
    if applied_force == 0 and y0 == 0 and mu_k > 0:
        analytic = v0 * v0 / (2 * mu_k * g)
    result = {
        'dt_used': h, 'steps': steps,
        'final': {'t': duration, 'x': x, 'y': y, 'vx': vx},
        'stopped': vx == 0.0, 'stop_time': stop_time,
        'stop_distance': abs(x) if vx == 0.0 else None,
        'analytic_stop_distance': analytic,
        'kinetic_deceleration': mu_k * g,
        'first_sliding_acceleration': first_sliding_accel,
        'static_hold': static_hold, 'direction_reversals': reversals,
        'min_y': min_y,
        'samples': _decimate(samples, max_samples),
    }
    return _pack('friction', result,
                 ['rigid block on flat rigid ground (no rolling, no tipping)',
                  'Coulomb friction: static mu_s, kinetic mu_k, independent of speed and contact area',
                  'normal force = m g while in contact; applied force is horizontal and constant',
                  'landing from y0 > 0 is perfectly inelastic vertically; no air drag'],
                 [f'steps <= {MAX_STEPS}', 'duration <= 600 s', 'mu in [0, 2], mu_k <= mu_s',
                  f'samples decimated to <= {max_samples}'])


# --------------------------------------------------------------------------- 08.04 spring

def spring(*, m=1.0, k=100.0, c=1.0, x0=1.0, v0=0.0, duration=5.0, dt=0.001,
           max_samples=401, **extra):
    """Mass-spring-damper x'' = -(k/m) x - (c/m) x' integrated with fixed-step RK4.

    Reports damping ratio zeta = c / (2 sqrt(k m)), natural frequency
    omega_n = sqrt(k/m), regime ('undamped'/'under'/'critical'/'over'), peaks
    (parabola-refined local maxima of x), logarithmic decrements between
    successive peaks, the analytic decrement 2 pi zeta / sqrt(1 - zeta^2), and
    overshoot (largest excursion past zero opposite to the start side).
    Rejects step sizes too large for an accurate RK4 solve (h * fastest rate > 0.5).
    """
    _no_extra(extra)
    m = _num(m, 0, 1e4, 'm', low_open=True)
    k = _num(k, 0, 1e6, 'k', low_open=True)
    c = _num(c, 0, 1e6, 'c')
    x0 = _num(x0, -1e3, 1e3, 'x0')
    v0 = _num(v0, -1e4, 1e4, 'v0')
    duration = _num(duration, 0, 600, 'duration', low_open=True)
    dt = _num(dt, 1e-6, 0.1, 'dt')
    max_samples = _int(max_samples, 2, MAX_SAMPLES, 'max_samples')
    steps = _steps(duration, dt)
    h = duration / steps
    wn = math.sqrt(k / m)
    zeta = c / (2 * math.sqrt(k * m))
    fastest = wn * (zeta + math.sqrt(zeta * zeta - 1)) if zeta > 1 else wn
    if h * fastest > 0.5:
        raise ValueError(f'dt too large for this spring: need dt <= {0.5 / fastest:.3g} s')
    if zeta == 0:
        regime = 'undamped'
    elif abs(zeta - 1) < 1e-9:
        regime = 'critical'
    elif zeta < 1:
        regime = 'under'
    else:
        regime = 'over'

    km, cm = k / m, c / m
    state = [x0, v0]
    xs = [x0]
    samples = [[0.0, x0, v0]]
    for i in range(1, steps + 1):
        state = _rk4(state, lambda s: [s[1], -km * s[0] - cm * s[1]], h)
        xs.append(state[0])
        samples.append([i * h, state[0], state[1]])

    peaks = []
    for i in range(1, len(xs) - 1):
        if xs[i - 1] < xs[i] >= xs[i + 1] and xs[i] > 0:
            a, b, cc = xs[i - 1], xs[i], xs[i + 1]
            den = a - 2 * b + cc
            off = 0.5 * (a - cc) / den if den != 0 else 0.0
            peaks.append([(i + off) * h, b - 0.25 * (a - cc) * off])
        if len(peaks) >= 1000:
            break
    decrements = [math.log(peaks[j][1] / peaks[j + 1][1]) for j in range(len(peaks) - 1)
                  if peaks[j + 1][1] > 0]
    analytic_dec = (2 * math.pi * zeta / math.sqrt(1 - zeta * zeta)) if 0 < zeta < 1 else None
    if x0 != 0:
        side = math.copysign(1.0, x0)
        overshoot = max(0.0, max(-side * x for x in xs)) / abs(x0)
    else:
        overshoot = None
    result = {
        'damping_ratio': zeta, 'natural_frequency_rad_s': wn,
        'natural_frequency_hz': wn / (2 * math.pi),
        'damped_frequency_rad_s': wn * math.sqrt(1 - zeta * zeta) if zeta < 1 else None,
        'regime': regime, 'dt_used': h, 'steps': steps,
        'peaks': peaks[:200], 'log_decrements': decrements[:200],
        'mean_log_decrement': (sum(decrements) / len(decrements)) if decrements else None,
        'analytic_log_decrement': analytic_dec,
        'overshoot_ratio': overshoot,
        'final': {'t': duration, 'x': state[0], 'v': state[1]},
        'samples': _decimate(samples, max_samples),
    }
    return _pack('spring', result,
                 ['linear spring (Hooke) and linear viscous damper', 'point mass, 1D, no external force',
                  'peaks are parabola-refined sample maxima (accuracy limited by dt)'],
                 [f'steps <= {MAX_STEPS}', 'duration <= 600 s',
                  'dt must satisfy dt * fastest_rate <= 0.5 (RK4 accuracy guard)',
                  'at most 200 peaks reported', f'samples decimated to <= {max_samples}'])


# --------------------------------------------------------------------------- 08.05 projectile

def projectile(*, speed=20.0, angle_deg=45.0, x0=0.0, y0=0.0, g=9.81, drag='none',
               drag_coeff=0.1, dt=0.001, max_time=60.0, max_samples=201, **extra):
    """2D projectile integrated with fixed-step RK4, optional drag.

    drag: 'none'; 'linear' a = -k v; 'quadratic' a = -k |v| v (k = drag_coeff,
    per unit mass). Terminal speed: g/k (linear) or sqrt(g/k) (quadratic).
    Landing (y crossing 0 downward) is located inside the last step by cubic
    Hermite interpolation of y with bisection, exact for drag-free parabolas.
    Stops at landing or max_time.
    """
    _no_extra(extra)
    speed = _num(speed, 0, 1e4, 'speed')
    angle_deg = _num(angle_deg, -90, 90, 'angle_deg')
    x0 = _num(x0, -1e6, 1e6, 'x0')
    y0 = _num(y0, 0, 1e5, 'y0')
    g = _num(g, 0, 1000, 'g', low_open=True)
    drag = _choice(drag, {'none', 'linear', 'quadratic'}, 'drag')
    drag_coeff = _num(drag_coeff, 0, 100, 'drag_coeff')
    dt = _num(dt, 1e-5, 0.1, 'dt')
    max_time = _num(max_time, 0, 600, 'max_time', low_open=True)
    max_samples = _int(max_samples, 2, MAX_SAMPLES, 'max_samples')
    steps = _steps(max_time, dt, 'max_time/dt')
    h = max_time / steps
    k = 0.0 if drag == 'none' else drag_coeff
    if drag != 'none' and k > 0:
        rate = k if drag == 'linear' else k * max(speed, math.sqrt(g / k))
        if rate * h > 0.5:
            raise ValueError('dt too large for this drag; reduce dt or drag_coeff')

    def deriv(s):
        _, _, vx, vy = s
        if drag == 'linear':
            return [vx, vy, -k * vx, -g - k * vy]
        if drag == 'quadratic':
            sp = math.hypot(vx, vy)
            return [vx, vy, -k * sp * vx, -g - k * sp * vy]
        return [vx, vy, 0.0, -g]

    th = math.radians(angle_deg)
    state = [x0, y0, speed * math.cos(th), speed * math.sin(th)]
    traj = [[0.0] + state[:]]
    landed = False
    land = None
    max_y = y0
    t = 0.0
    if y0 == 0 and state[3] <= 0:
        landed, land = True, {'t': 0.0, 'x': x0, 'vx': state[2], 'vy': state[3]}
    else:
        for i in range(1, steps + 1):
            new = _rk4(state, deriv, h)
            if new[1] <= 0.0 and (state[1] > 0.0 or i > 1):
                ya, yb = state[1], new[1]
                da, db = deriv(state), deriv(new)

                def herm(s, pa, pb, va, vb):
                    s2, s3 = s * s, s * s * s
                    return ((2 * s3 - 3 * s2 + 1) * pa + (s3 - 2 * s2 + s) * h * va
                            + (-2 * s3 + 3 * s2) * pb + (s3 - s2) * h * vb)
                lo, hi = 0.0, 1.0
                for _ in range(80):
                    mid = 0.5 * (lo + hi)
                    if herm(mid, ya, yb, da[1], db[1]) > 0:
                        lo = mid
                    else:
                        hi = mid
                s = 0.5 * (lo + hi)
                land = {'t': t + s * h,
                        'x': herm(s, state[0], new[0], da[0], db[0]),
                        'vx': state[2] + s * (new[2] - state[2]),
                        'vy': state[3] + s * (new[3] - state[3])}
                landed = True
                traj.append([land['t'], land['x'], 0.0, land['vx'], land['vy']])
                break
            state = new
            t = i * h
            max_y = max(max_y, state[1])
            traj.append([t] + state[:])
    terminal = None
    if drag == 'linear' and k > 0:
        terminal = g / k
    elif drag == 'quadratic' and k > 0:
        terminal = math.sqrt(g / k)
    analytic = None
    if drag == 'none' or k == 0:
        vx0, vy0 = speed * math.cos(th), speed * math.sin(th)
        t_flight = (vy0 + math.sqrt(vy0 * vy0 + 2 * g * y0)) / g
        analytic = {'flight_time': t_flight, 'range': vx0 * t_flight,
                    'max_height': y0 + (vy0 * vy0 / (2 * g) if vy0 > 0 else 0.0)}
    last = traj[-1]
    result = {
        'landed': landed, 'dt_used': h,
        'flight_time': land['t'] if landed else None,
        'range': (land['x'] - x0) if landed else None,
        'landing_velocity': [land['vx'], land['vy']] if landed else None,
        'max_height': max_y,
        'final': {'t': last[0], 'x': last[1], 'y': last[2], 'vx': last[3], 'vy': last[4]},
        'terminal_speed': terminal, 'analytic_drag_free': analytic,
        'trajectory': _decimate(traj, max_samples),
    }
    return _pack('projectile', result,
                 ['point mass in a vertical plane, flat ground at y = 0', 'uniform gravity, still air (no wind)',
                  'drag coefficient is per unit mass and constant; no lift, spin or Magnus effect'],
                 [f'steps <= {MAX_STEPS}', 'max_time <= 600 s', 'dt rejected if too large for the drag stiffness',
                  f'trajectory decimated to <= {max_samples} samples'])


# --------------------------------------------------------------------------- 08.06 cloth

CLOTH_WORK_BUDGET = 4_000_000


def cloth(*, cols=10, rows=10, spacing=0.1, steps=120, dt=1.0 / 60.0, gravity=9.81,
          wind=(0.0, 0.0, 0.0), iterations=20, damping=0.01, shear=True, pin='top_row',
          **extra):
    """Particle-grid cloth: position Verlet + iterative distance constraints.

    Grid starts flat in the x-y plane (row 0 at y = 0, rows hang toward -y),
    z = 0. Gravity acts along -y; `wind` is a constant uniform acceleration
    vector [ax, ay, az]. Pinned particles (top row or the two top corners)
    never move. Structural (and optional shear) edges are relaxed with
    `iterations` Gauss-Seidel passes per step. No tearing, no self-collision.
    Returns final positions and stretch statistics (edge length / rest length).
    """
    _no_extra(extra)
    cols = _int(cols, 2, 30, 'cols')
    rows = _int(rows, 2, 30, 'rows')
    spacing = _num(spacing, 1e-3, 10, 'spacing')
    steps = _int(steps, 1, 2000, 'steps')
    dt = _num(dt, 1e-4, 0.1, 'dt')
    gravity = _num(gravity, 0, 100, 'gravity')
    wind = _vec(wind, 3, 'wind', -100, 100)
    iterations = _int(iterations, 1, 200, 'iterations')
    damping = _num(damping, 0, 0.5, 'damping')
    if not isinstance(shear, bool):
        raise ValueError('shear must be true or false')
    pin = _choice(pin, {'top_row', 'corners'}, 'pin')

    def idx(r, c):
        return r * cols + c
    pos = [[c * spacing, -r * spacing, 0.0] for r in range(rows) for c in range(cols)]
    prev = [p[:] for p in pos]
    inv = [1.0] * len(pos)
    pinned = list(range(cols)) if pin == 'top_row' else [0, cols - 1]
    for p in pinned:
        inv[p] = 0.0
    structural = []
    for r in range(rows):
        for c in range(cols):
            if c + 1 < cols:
                structural.append((idx(r, c), idx(r, c + 1), spacing))
            if r + 1 < rows:
                structural.append((idx(r, c), idx(r + 1, c), spacing))
    edges = list(structural)
    if shear:
        diag = spacing * math.sqrt(2)
        for r in range(rows - 1):
            for c in range(cols - 1):
                edges.append((idx(r, c), idx(r + 1, c + 1), diag))
                edges.append((idx(r, c + 1), idx(r + 1, c), diag))
    work = steps * iterations * len(edges)
    if work > CLOTH_WORK_BUDGET:
        raise ValueError(f'cloth work {work} exceeds budget {CLOTH_WORK_BUDGET}; '
                         'reduce grid, steps or iterations')
    pinned_start = [pos[p][:] for p in pinned]
    acc = [wind[0], wind[1] - gravity, wind[2]]
    keep = 1.0 - damping
    dt2 = dt * dt

    def stretch_stats():
        hi, lo = 0.0, float('inf')
        for a, b, rest in structural:
            pa, pb = pos[a], pos[b]
            ratio = math.dist(pa, pb) / rest
            hi, lo = max(hi, ratio), min(lo, ratio)
        return hi, lo

    worst = 0.0
    for _ in range(steps):
        for i, p in enumerate(pos):
            if inv[i] == 0.0:
                continue
            q = prev[i]
            nx = p[0] + (p[0] - q[0]) * keep + acc[0] * dt2
            ny = p[1] + (p[1] - q[1]) * keep + acc[1] * dt2
            nz = p[2] + (p[2] - q[2]) * keep + acc[2] * dt2
            prev[i] = p
            pos[i] = [nx, ny, nz]
        for _ in range(iterations):
            for a, b, rest in edges:
                wa, wb = inv[a], inv[b]
                wsum = wa + wb
                if wsum == 0.0:
                    continue
                pa, pb = pos[a], pos[b]
                dx, dy, dz = pb[0] - pa[0], pb[1] - pa[1], pb[2] - pa[2]
                length = math.sqrt(dx * dx + dy * dy + dz * dz)
                if length == 0.0:
                    continue
                s = (length - rest) / (length * wsum)
                if wa:
                    pa[0] += wa * s * dx
                    pa[1] += wa * s * dy
                    pa[2] += wa * s * dz
                if wb:
                    pb[0] -= wb * s * dx
                    pb[1] -= wb * s * dy
                    pb[2] -= wb * s * dz
        worst = max(worst, stretch_stats()[0])
    hi, lo = stretch_stats()
    finite = all(math.isfinite(v) for p in pos for v in p)
    if not finite:
        raise RuntimeError('cloth simulation produced non-finite values')
    result = {
        'cols': cols, 'rows': rows, 'steps': steps, 'iterations': iterations,
        'positions': [p[:] for p in pos], 'pinned_indices': pinned,
        'pinned_fixed': all(pos[p] == s for p, s in zip(pinned, pinned_start)),
        'max_stretch_ratio': hi, 'min_stretch_ratio': lo,
        'max_stretch_ratio_any_step': worst, 'finite': finite,
    }
    return _pack('cloth', result,
                 ['mass-spring-like particle grid with equal particle masses',
                  'position Verlet with velocity damping; constraints solved by Gauss-Seidel projection',
                  'wind is a uniform constant acceleration (no aerodynamic normal pressure)',
                  'no tearing, no self-collision, no collision with other objects'],
                 ['grid <= 30 x 30', 'steps <= 2000, iterations <= 200',
                  f'steps * iterations * edges <= {CLOTH_WORK_BUDGET}',
                  'stretch quality depends on iterations; check max_stretch_ratio'])


# --------------------------------------------------------------------------- 08.07 motion_blur

def motion_blur(*, fps=24.0, shutter_deg=180.0, frames=24, velocity=None, start=(0.0, 0.0),
                keyframes=None, samples=8, **extra):
    """Per-frame open-shutter sub-samples for motion blur of a moving point.

    Path: either constant `velocity` from `start` (default [100, 0] units/s),
    or `keyframes` [[t, x, y(, z)], ...] interpolated linearly (held constant
    outside the keyframe range). Frame i opens at t = i / fps and stays open
    for exposure = (shutter_deg / 360) / fps. Returns `samples` equally
    weighted (box filter) sub-sample positions at the centres of equal
    sub-intervals of the open interval; shutter 0 gives exactly one sample at
    the frame time (sharp). blur_length is the path length travelled while
    the shutter is open.
    """
    _no_extra(extra)
    fps = _num(fps, 1, 240, 'fps')
    shutter_deg = _num(shutter_deg, 0, 360, 'shutter_deg')
    frames = _int(frames, 1, 600, 'frames')
    samples = _int(samples, 1, 64, 'samples')
    if velocity is not None and keyframes is not None:
        raise ValueError('give velocity or keyframes, not both')
    if keyframes is None:
        vel = _vec([100.0, 0.0] if velocity is None else velocity, (2, 3), 'velocity')
        st = _vec(start, len(vel), 'start')

        def position(t):
            return [s + v * t for s, v in zip(st, vel)]
        spd = math.sqrt(sum(v * v for v in vel))

        def path_length(ta, tb):
            return spd * (tb - ta)
        kind = 'linear_velocity'
    else:
        if not isinstance(keyframes, (list, tuple)) or not 1 <= len(keyframes) <= 256:
            raise ValueError('keyframes must be a list of 1..256 [t, x, y(, z)] entries')
        keys = [_vec(k, (3, 4), f'keyframes[{i}]') for i, k in enumerate(keyframes)]
        if len({len(k) for k in keys}) != 1:
            raise ValueError('all keyframes must have the same dimension')
        for i, kf in enumerate(keys):
            if not 0 <= kf[0] <= 3600:
                raise ValueError('keyframe times must be in [0, 3600] s')
            if i and kf[0] <= keys[i - 1][0]:
                raise ValueError('keyframe times must be strictly increasing')

        def position(t):
            if t <= keys[0][0]:
                return keys[0][1:]
            if t >= keys[-1][0]:
                return keys[-1][1:]
            for a, b in zip(keys, keys[1:]):
                if a[0] <= t <= b[0]:
                    u = (t - a[0]) / (b[0] - a[0])
                    return [pa + u * (pb - pa) for pa, pb in zip(a[1:], b[1:])]
            return keys[-1][1:]

        def path_length(ta, tb):
            pts = [ta] + [k[0] for k in keys if ta < k[0] < tb] + [tb]
            return sum(math.dist(position(p), position(q)) for p, q in zip(pts, pts[1:]))
        kind = 'keyframes'

    exposure = (shutter_deg / 360.0) / fps
    n = 1 if exposure == 0 else samples
    out = []
    for i in range(frames):
        t0 = i / fps
        subs = []
        for j in range(n):
            ts = t0 if n == 1 and exposure == 0 else t0 + (j + 0.5) / n * exposure
            subs.append({'t': ts, 'position': position(ts), 'weight': 1.0 / n})
        dims = len(subs[0]['position'])
        centroid = [sum(s['position'][d] * s['weight'] for s in subs) for d in range(dims)]
        out.append({'frame': i, 'time': t0, 'shutter_open': t0, 'shutter_close': t0 + exposure,
                    'samples': subs, 'weighted_position': centroid,
                    'blur_length': path_length(t0, t0 + exposure)})
    result = {'path': kind, 'fps': fps, 'shutter_deg': shutter_deg, 'exposure_s': exposure,
              'samples_per_frame': n, 'frames': out}
    return _pack('motion_blur', result,
                 ['shutter opens at the start of each frame interval (not centred)',
                  'box (uniform) shutter weighting; mid-point sub-sampling',
                  'keyframed paths are piecewise linear (no easing curves); point object, no rotation'],
                 ['fps in [1, 240], frames <= 600, samples <= 64, keyframes <= 256',
                  'returns sample positions/weights only; it does not render pixels'])


# --------------------------------------------------------------------------- 08.08 flow

def _make_field(field, strength, direction, center, seed, modes, scale):
    if field == 'uniform':
        n = math.hypot(direction[0], direction[1])
        if n < 1e-12:
            raise ValueError('direction must not be zero')
        ux, uy = strength * direction[0] / n, strength * direction[1] / n

        def vel(x, y):
            return ux, uy
        return vel
    if field == 'vortex':
        cx, cy = center

        def vel(x, y):
            return -strength * (y - cy), strength * (x - cx)
        return vel
    rng = random.Random(seed)
    waves = []
    for _ in range(modes):
        ang = rng.uniform(0, 2 * math.pi)
        kmag = 2 * math.pi / scale * rng.uniform(0.5, 1.5)
        phase = rng.uniform(0, 2 * math.pi)
        amp = strength / (kmag * math.sqrt(modes))
        waves.append((kmag * math.cos(ang), kmag * math.sin(ang), phase, amp))

    def vel(x, y):
        u = v = 0.0
        for kx, ky, ph, a in waves:
            cs = math.cos(kx * x + ky * y + ph)
            u += a * ky * cs
            v -= a * kx * cs
        return u, v
    return vel


def flow(*, field='vortex', strength=1.0, direction=(1.0, 0.0), center=(0.0, 0.0), seed=0,
         modes=6, scale=1.0, particles=None, dt=0.01, steps=200, sample_points=None,
         max_path_points=201, **extra):
    """Analytic 2D incompressible velocity fields and RK4 particle advection.

    field: 'uniform' (speed `strength` along `direction`), 'vortex' (solid-body
    rotation, angular speed `strength` rad/s about `center`), or 'curl_noise'
    (velocity = curl of a seeded sum of `modes` sine waves with wavelength
    around `scale`). All fields derive from a stream function, so they are
    divergence-free analytically; the result reports a central-difference
    divergence check at `sample_points` (default 5 x 5 grid on [-1, 1]^2).
    """
    _no_extra(extra)
    field = _choice(field, {'uniform', 'vortex', 'curl_noise'}, 'field')
    strength = _num(strength, -1e3, 1e3, 'strength')
    direction = _vec(direction, 2, 'direction')
    center = _vec(center, 2, 'center')
    seed = _int(seed, 0, 2**31 - 1, 'seed')
    modes = _int(modes, 1, 16, 'modes')
    scale = _num(scale, 1e-3, 1e3, 'scale')
    dt = _num(dt, 1e-5, 1.0, 'dt')
    steps = _int(steps, 1, 5000, 'steps')
    max_path_points = _int(max_path_points, 2, MAX_SAMPLES, 'max_path_points')
    if particles is None:
        particles = [[1.0, 0.0], [0.5, 0.5], [-0.3, 0.2]]
    if not isinstance(particles, (list, tuple)) or not 1 <= len(particles) <= 200:
        raise ValueError('particles must be a list of 1..200 [x, y] points')
    parts = [_vec(p, 2, f'particles[{i}]') for i, p in enumerate(particles)]
    if len(parts) * steps > 200_000:
        raise ValueError('particles * steps must be <= 200000')
    if sample_points is None:
        sample_points = [[-1 + 0.5 * i, -1 + 0.5 * j] for i in range(5) for j in range(5)]
    if not isinstance(sample_points, (list, tuple)) or not 1 <= len(sample_points) <= 400:
        raise ValueError('sample_points must be a list of 1..400 [x, y] points')
    pts = [_vec(p, 2, f'sample_points[{i}]') for i, p in enumerate(sample_points)]
    vel = _make_field(field, strength, direction, center, seed, modes, scale)

    hd = 1e-4
    samples = []
    for x, y in pts:
        u, v = vel(x, y)
        div = ((vel(x + hd, y)[0] - vel(x - hd, y)[0]) / (2 * hd)
               + (vel(x, y + hd)[1] - vel(x, y - hd)[1]) / (2 * hd))
        samples.append({'point': [x, y], 'velocity': [u, v], 'divergence': div})

    def deriv(s):
        return list(vel(s[0], s[1]))
    paths = []
    for p in parts:
        state = p[:]
        path = [state[:]]
        for _ in range(steps):
            state = _rk4(state, deriv, dt)
            path.append(state[:])
        entry = {'start': p, 'end': state, 'path': _decimate(path, max_path_points)}
        if field == 'vortex':
            r0 = math.dist(p, center)
            r1 = math.dist(state, center)
            entry['radius_start'] = r0
            entry['radius_end'] = r1
            entry['radius_max_rel_change'] = (max(abs(math.dist(q, center) - r0) for q in path) / r0
                                              if r0 > 0 else 0.0)
        paths.append(entry)
    result = {'field': field, 'samples': samples,
              'max_abs_divergence': max(abs(s['divergence']) for s in samples),
              'particles': paths, 'dt': dt, 'steps': steps}
    return _pack('flow', result,
                 ['2D, steady (time-independent), incompressible kinematic fields from a stream function',
                  'not a Navier-Stokes solve: no pressure, viscosity, boundaries or two-way coupling',
                  'particles are massless tracers advected with RK4'],
                 ['particles <= 200, steps <= 5000, particles * steps <= 200000',
                  'curl_noise modes <= 16', 'divergence is a central-difference estimate (h = 1e-4)'])


# --------------------------------------------------------------------------- 08.09 shading

def shading(*, normal=(0.0, 0.0, 1.0), light_dir=(0.0, 0.0, 1.0), view_dir=(0.0, 0.0, 1.0),
            albedo=(0.8, 0.8, 0.8), shininess=32.0, kd=0.7, ks=0.3, light_intensity=1.0,
            **extra):
    """Lambert diffuse + normalised Blinn-Phong specular for one directional light.

    Vectors point away from the surface (light_dir toward the light, view_dir
    toward the eye) and are normalised here. Output scale: a white Lambertian
    surface lit head-on by a unit light gives 1.0, i.e.
      diffuse  = I * kd * albedo * max(0, n.l)
      specular = I * ks * (s + 8) / 8 * max(0, n.h)^s * max(0, n.l)
    Requires kd + ks <= 1 (energy budget). The normalised specular lobe can
    still peak above 1 for high shininess, so `value` is clamped to [0, 1]
    and `clipped` says whether clamping happened; `radiance` is unclamped.
    """
    _no_extra(extra)
    n = _unit(normal, 'normal')
    l = _unit(light_dir, 'light_dir')
    v = _unit(view_dir, 'view_dir')
    albedo = _vec(albedo, 3, 'albedo', 0, 1)
    shininess = _num(shininess, 1, 1024, 'shininess')
    kd = _num(kd, 0, 1, 'kd')
    ks = _num(ks, 0, 1, 'ks')
    if kd + ks > 1 + 1e-12:
        raise ValueError('kd + ks must be <= 1 (energy conservation)')
    light_intensity = _num(light_intensity, 0, 100, 'light_intensity')
    ndl = sum(a * b for a, b in zip(n, l))
    ndv = sum(a * b for a, b in zip(n, v))
    hv = [a + b for a, b in zip(l, v)]
    hn = math.sqrt(sum(c * c for c in hv))
    half = [c / hn for c in hv] if hn > 1e-12 else n[:]
    ndh = max(0.0, sum(a * b for a, b in zip(n, half)))
    cos_l = max(0.0, ndl)
    diffuse = [light_intensity * kd * a * cos_l for a in albedo]
    spec = 0.0
    if ndl > 0 and ndv > 0:
        spec = light_intensity * ks * (shininess + 8) / 8 * ndh ** shininess * cos_l
    radiance = [d + spec for d in diffuse]
    value = [min(1.0, max(0.0, r)) for r in radiance]
    result = {'diffuse': diffuse, 'specular': spec, 'radiance': radiance, 'value': value,
              'clipped': any(r > 1.0 for r in radiance), 'n_dot_l': ndl, 'n_dot_v': ndv,
              'n_dot_h': ndh, 'half_vector': half,
              'reflectance_budget': kd * max(albedo) + ks}
    return _pack('shading', result,
                 ['single directional white light, no shadows, no ambient or global illumination',
                  'Lambert diffuse + normalised Blinn-Phong ((s+8)/8 lobe); no Fresnel term',
                  'normalised Blinn-Phong is only approximately energy conserving'],
                 ['shininess in [1, 1024], kd + ks <= 1, light_intensity <= 100',
                  'value is clamped to [0, 1]; check clipped / radiance for the unclamped result'])


# --------------------------------------------------------------------------- 08.10 particles

_KIND_DEFAULTS = {
    'snow': {'gravity': 9.81, 'drag': 6.0, 'turbulence': 0.6},
    'dust': {'gravity': 0.3, 'drag': 4.0, 'turbulence': 1.0},
}


def particles(*, kind='snow', count=200, frames=100, fps=24.0, seed=0,
              box_min=(-1.0, 0.0, -1.0), box_max=(1.0, 2.0, 1.0), wind=(0.0, 0.0, 0.0),
              gravity=None, drag=None, turbulence=None, max_speed=10.0, substeps=4,
              **extra):
    """Seeded dust/snow particle system; positions for every frame.

    Particles spawn uniformly at random inside the box, at rest. Each substep:
    dv = (-gravity y_hat + drag * (wind - v) + gaussian * turbulence / sqrt(h)) * h,
    speed clamped to max_speed, then x += v h. Particles that reach the floor
    (box_min y) settle there and stop (no respawn, so no teleporting).
    Same seed -> identical output. Per-frame displacement <= max_speed / fps.
    kind sets defaults: snow (gravity 9.81, drag 6, turbulence 0.6) or
    dust (gravity 0.3, drag 4, turbulence 1.0). Positions are rounded to 1e-6.
    """
    _no_extra(extra)
    kind = _choice(kind, set(_KIND_DEFAULTS), 'kind')
    count = _int(count, 1, 500, 'count')
    frames = _int(frames, 1, 300, 'frames')
    fps = _num(fps, 1, 120, 'fps')
    seed = _int(seed, 0, 2**31 - 1, 'seed')
    bmin = _vec(box_min, 3, 'box_min', -1e3, 1e3)
    bmax = _vec(box_max, 3, 'box_max', -1e3, 1e3)
    if any(a >= b for a, b in zip(bmin, bmax)):
        raise ValueError('box_min must be < box_max on every axis')
    wind = _vec(wind, 3, 'wind', -100, 100)
    d = _KIND_DEFAULTS[kind]
    gravity = d['gravity'] if gravity is None else _num(gravity, -100, 100, 'gravity')
    drag = d['drag'] if drag is None else _num(drag, 0, 100, 'drag')
    turbulence = d['turbulence'] if turbulence is None else _num(turbulence, 0, 100, 'turbulence')
    max_speed = _num(max_speed, 0, 100, 'max_speed', low_open=True)
    substeps = _int(substeps, 1, 8, 'substeps')
    if count * frames * substeps > 600_000:
        raise ValueError('count * frames * substeps must be <= 600000')
    h = 1.0 / (fps * substeps)
    if drag * h > 0.5:
        raise ValueError('drag too large for this fps/substeps')

    rng = random.Random(seed)
    pos = [[rng.uniform(bmin[a], bmax[a]) for a in range(3)] for _ in range(count)]
    vel = [[0.0, 0.0, 0.0] for _ in range(count)]
    settled = [False] * count
    noise = turbulence / math.sqrt(h)
    floor = bmin[1]
    out = [[[round(c, 6) for c in p] for p in pos]]
    start_y = sum(p[1] for p in pos) / count
    max_frame_step = 0.0
    for _ in range(frames - 1):
        before = [p[:] for p in pos]
        for _ in range(substeps):
            for i in range(count):
                if settled[i]:
                    continue
                p, v = pos[i], vel[i]
                for a in range(3):
                    acc = drag * (wind[a] - v[a]) + noise * rng.gauss(0.0, 1.0)
                    if a == 1:
                        acc -= gravity
                    v[a] += acc * h
                sp = math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])
                if sp > max_speed:
                    f = max_speed / sp
                    v[0] *= f
                    v[1] *= f
                    v[2] *= f
                p[0] += v[0] * h
                p[1] += v[1] * h
                p[2] += v[2] * h
                if p[1] <= floor:
                    p[1] = floor
                    v[0] = v[1] = v[2] = 0.0
                    settled[i] = True
        max_frame_step = max(max_frame_step, max(math.dist(a, b) for a, b in zip(before, pos)))
        out.append([[round(c, 6) for c in p] for p in pos])
    result = {'kind': kind, 'count': count, 'frames': out, 'fps': fps, 'seed': seed,
              'gravity': gravity, 'drag': drag, 'turbulence': turbulence,
              'max_frame_step': max_frame_step, 'frame_step_bound': max_speed / fps,
              'mean_y_start': start_y, 'mean_y_end': sum(p[1] for p in pos) / count,
              'settled_count': sum(settled)}
    return _pack('particles', result,
                 ['independent point particles (no collisions between them)',
                  'linear drag toward the wind velocity; white-noise turbulence (not a coherent flow field)',
                  'particles reaching the floor settle and stop; no respawn; walls other than the floor are not enforced',
                  'deterministic for a given seed on the same Python random implementation'],
                 ['count <= 500, frames <= 300, substeps <= 8, count * frames * substeps <= 600000',
                  f'speed clamped to max_speed, so per-frame motion <= max_speed / fps'])


# --------------------------------------------------------------------------- dispatcher

OPS = {
    'fall': fall, 'collide': collide, 'friction': friction, 'spring': spring,
    'projectile': projectile, 'cloth': cloth, 'motion_blur': motion_blur,
    'flow': flow, 'shading': shading, 'particles': particles,
}


def run(op, params=None):
    """Validate and dispatch: run('fall', {'y0': 5}) -> {'op','result','assumptions','limits'}."""
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
