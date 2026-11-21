"""Red Rose keyframe interpolation: time-normalized and independently testable.

A track is a list of points {t:0..1, value:number, ease: linear|smooth|hold}.
The easing value belongs to the *arriving* keyframe.
"""
import math


def sample(track, phase, default=0.0):
    """Interpolate a validated scalar track at a normalized phase 0..1."""
    if not isinstance(phase,(int,float)) or not math.isfinite(phase):
        raise ValueError('phase must be finite')
    if track is None:
        return float(default)
    if not isinstance(track,list) or not 1 <= len(track) <= 64:
        raise ValueError('track requires 1..64 keyframes')
    keys=[]
    prev=-1.0
    for key in track:
        if not isinstance(key,dict): raise ValueError('keyframe must be an object')
        t=key.get('t');v=key.get('value');ease=key.get('ease','smooth')
        if not isinstance(t,(int,float)) or not isinstance(v,(int,float)) or not math.isfinite(t) or not math.isfinite(v):
            raise ValueError('time and value must be finite numbers')
        if not 0 <= t <= 1 or t <= prev: raise ValueError('keyframe times must increase in 0..1')
        if ease not in ('linear','smooth','hold'): raise ValueError('unsupported easing')
        keys.append((float(t),float(v),ease))
        prev=t
    phase=max(0.0,min(1.0,phase))
    if phase <= keys[0][0]:return keys[0][1]
    if phase >= keys[-1][0]:return keys[-1][1]
    for left,right in zip(keys,keys[1:]):
        if left[0] <= phase <= right[0]:
            u=(phase-left[0])/(right[0]-left[0])
            if right[2]=='hold': u=0
            elif right[2]=='smooth':u=u*u*(3-2*u)
            return left[1]+(right[1]-left[1])*u
    raise AssertionError('no segment')


def scalar(spec, phase, fallback, minimum, maximum):
    val=sample(spec,phase,fallback)
    if not minimum <= val <= maximum:
        raise ValueError(f'interpolated value {val} exceeds [{minimum}, {maximum}]')
    return val
