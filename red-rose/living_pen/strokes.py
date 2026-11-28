"""Original centripetal Catmull-Rom geometry and scalar minimum-jerk timing."""
from dataclasses import dataclass
import math
import numpy as np


def number(value, name):
    if isinstance(value, (bool, str, bytes)):
        raise ValueError(f"{name} must be numeric")
    try:
        value = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{name} must be numeric") from exc
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite")
    return value


def profile(value, n, name, low, high):
    values = [value] * n if np.ndim(value) == 0 else list(value)
    if len(values) != n:
        raise ValueError(f"{name} requires one value per control point")
    a = np.array([number(v, name) for v in values])
    if np.any((a < low) | (a > high)):
        raise ValueError(f"{name} outside [{low}, {high}]")
    a.setflags(write=False)
    return a


@dataclass(frozen=True)
class StrokeSample:
    xy: np.ndarray
    tangent: np.ndarray
    curvature: np.ndarray
    pressure: np.ndarray
    tilt: np.ndarray
    distance: np.ndarray
    time: np.ndarray
    speed: np.ndarray


class Stroke:
    """Coordinates in pixels (y down), tilt in degrees, time in seconds.

    Pressure [0,1]. Tilt [0,90] stored for future contact models.
    Closed strokes repeat the first point; seam profiles must match.
    """
    def __init__(self, points, pressure=1.0, tilt=0.0, duration=1.0,
                 start_time=0.0, tool="qalam", pigment=(25, 20, 18)):
        try:
            p = np.asarray(points)
            if p.ndim != 2 or p.shape[1] != 2 or not 2 <= len(p) <= 4096:
                raise ValueError("points must be 2..4096 XY pairs")
            p = np.array([[number(v, "point") for v in row] for row in p])
        except (TypeError, ValueError) as exc:
            raise ValueError("invalid stroke points") from exc
        if np.max(np.abs(p)) > 1e6 or np.any(np.linalg.norm(np.diff(p, axis=0), axis=1) < 1e-9):
            raise ValueError("coordinates out of bounds or consecutive identical points")
        p.setflags(write=False)
        self.points = p
        self.pressure = profile(pressure, len(p), "pressure", 0, 1)
        self.tilt = profile(tilt, len(p), "tilt", 0, 90)
        self.duration = number(duration, "duration")
        self.start_time = number(start_time, "start_time")
        if self.duration <= 0 or self.start_time < 0:
            raise ValueError("duration must be positive; start_time nonnegative")
        self.tool = tool
        self.pigment = tuple(pigment)
        self.closed = len(p) >= 4 and np.array_equal(p[0], p[-1])
        if self.closed and (self.pressure[0] != self.pressure[-1] or self.tilt[0] != self.tilt[-1]):
            raise ValueError("closed stroke seam profiles must match")
        # Centripetal knots: sqrt(chord length), and weighted secant tangents.
        h = np.sqrt(np.linalg.norm(np.diff(p,axis=0),axis=1))
        sec = np.diff(p,axis=0)/h[:,None]
        m = np.empty_like(p)
        m[1:-1] = (sec[:-1]*h[1:,None]+sec[1:]*h[:-1,None])/(h[:-1]+h[1:])[:,None]
        m[0], m[-1] = sec[0],sec[-1]
        if self.closed:
            m[0] = m[-1] = (sec[-1]*h[0]+sec[0]*h[-1])/(h[0]+h[-1])
        a,b = m[:-1]*h[:,None],m[1:]*h[:,None]
        self._coef = np.stack((p[:-1], a,
                              3*(p[1:]-p[:-1])-2*a-b,
                              2*(p[:-1]-p[1:])+a+b), axis=1)
        self._u = np.linspace(0, len(p)-1, 128*(len(p)-1)+1)
        xy, _, _ = self._eval(self._u)
        self._s = np.r_[0., np.cumsum(np.linalg.norm(np.diff(xy, axis=0), axis=1))]
        self.length = float(self._s[-1])

    def _eval(self, u):
        i = np.minimum(np.floor(u).astype(int), len(self.points)-2)
        t = (u-i)[..., None]
        a,b,c,d = np.moveaxis(self._coef[i], -2, 0)
        return a+t*(b+t*(c+t*d)), b+t*(2*c+3*t*d), 2*c+6*t*d

    def at_distance(self, distance):
        s = np.asarray(distance, dtype=float)
        if np.any(~np.isfinite(s)) or np.any((s < 0) | (s > self.length)):
            raise ValueError("distance outside stroke")
        u = np.interp(s, self._s, self._u)
        xy, v, a = self._eval(u)
        norm = np.linalg.norm(v, axis=-1)
        # At a stationary cusp use the local chord; curvature is undefined there.
        bad = norm < 1e-10
        if np.any(bad):
            left = self._eval(np.maximum(0, u-1e-4))[0]
            right = self._eval(np.minimum(len(self.points)-1, u+1e-4))[0]
            chord = right-left
            chordnorm = np.linalg.norm(chord, axis=-1)
            fallback = np.where((chordnorm > 1e-12)[...,None],
                                chord / np.maximum(chordnorm, 1e-12)[...,None], [1.,0.])
        else:
            fallback = np.zeros_like(v)
        tangent = np.where(bad[...,None], fallback, v/np.maximum(norm, 1e-10)[...,None])
        curvature = np.where(bad, np.nan, (v[...,0]*a[...,1]-v[...,1]*a[...,0]) / np.maximum(norm,1e-10)**3)
        knots = np.arange(len(self.points))
        return xy, tangent, curvature, np.interp(u, knots, self.pressure), np.interp(u, knots, self.tilt)

    def at_time(self, time):
        t = np.asarray(time, dtype=float)
        q = (t-self.start_time)/self.duration
        if np.any(~np.isfinite(q)) or np.any((q < -1e-12) | (q > 1+1e-12)):
            raise ValueError("time outside stroke")
        q = np.clip(q, 0, 1)
        s = self.length*q**3*(10+q*(-15+6*q))
        s = np.clip(s, 0, self.length)
        speed = self.length/self.duration*30*q**2*(1-q)**2
        return StrokeSample(*self.at_distance(s), s, t, speed)
