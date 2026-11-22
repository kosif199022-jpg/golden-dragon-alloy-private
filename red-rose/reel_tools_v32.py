"""Reel tools learned from real work (the Sunday dua reel, 2026-11-22).

flat_check    find blank / flat frames that blackdetect misses (a grey frame inside a transition)
color_stats   mean Lab colour and chroma (saturation) of a video
color_match   build a .cube LUT that moves a clip's colour to a reference video's colour
line_times    when an on-screen text line appears and disappears in a reference video

Standard library + ffmpeg/ffprobe only. Reads never modify inputs; the one write
(color_match's .cube) needs approve_write.
"""
from __future__ import annotations

import math
import subprocess
from pathlib import Path

SW, SH = 90, 160            # sampling size
FLAT_STD = 25.0             # luma std-dev below this = flat frame (measured: real shots were 32+)
LUT_N = 33

_LIN = [(c / 255 / 12.92) if c / 255 <= 0.04045 else ((c / 255 + 0.055) / 1.055) ** 2.4 for c in range(256)]


def _duration(path) -> float:
    out = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0',
                          str(path)], capture_output=True, text=True)
    try:
        return float(out.stdout.strip())
    except ValueError:
        raise ValueError(f'cannot read duration: {path}')


def _frames(path, step, start=0.0, duration=None, vf_extra='', w=SW, h=SH, pix='rgb24'):
    """Sampled frames as a list of bytes, one ffmpeg call."""
    path = Path(path).expanduser()
    if not path.is_file():
        raise FileNotFoundError(str(path))
    cmd = ['ffmpeg', '-v', 'error']
    if start:
        cmd += ['-ss', f'{start:.3f}']
    if duration:
        cmd += ['-t', f'{duration:.3f}']
    vf = f'fps=1/{step},scale={w}:{h}' + (',' + vf_extra if vf_extra else '')
    cmd += ['-i', str(path), '-vf', vf, '-f', 'rawvideo', '-pix_fmt', pix, '-']
    raw = subprocess.run(cmd, capture_output=True).stdout
    size = w * h * (3 if pix == 'rgb24' else 1)
    return [raw[i:i + size] for i in range(0, len(raw) - size + 1, size)]


def flat_check(video, step: float = 0.3, threshold: float = FLAT_STD) -> dict:
    """Times (seconds) of frames whose luma is nearly uniform: blank, grey or black."""
    if not 0.05 <= step <= 5:
        raise ValueError('step must be 0.05..5 seconds')
    flat = []
    frames = _frames(video, step, pix='gray')
    for k, fr in enumerate(frames):
        n = len(fr)
        mean = sum(fr) / n
        std = math.sqrt(sum((v - mean) ** 2 for v in fr) / n)
        if std < threshold:
            flat.append({'t': round(k * step, 2), 'std': round(std, 1), 'mean': round(mean, 1)})
    return {'ok': not flat, 'checked_frames': len(frames), 'step': step, 'threshold': threshold,
            'flat': flat,
            'hint': None if not flat else 'look at these moments; a zoom transition into a plain wall does this'}


def _lab(r, g, b):
    rl, gl, bl = _LIN[r], _LIN[g], _LIN[b]
    x = (0.4124 * rl + 0.3576 * gl + 0.1805 * bl) / 0.95047
    y = 0.2126 * rl + 0.7152 * gl + 0.0722 * bl
    z = (0.0193 * rl + 0.1192 * gl + 0.9505 * bl) / 1.08883
    f = lambda t: t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116
    fx, fy, fz = f(x), f(y), f(z)
    return 116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)


def _rgb(L, a, b):
    fy = (L + 16) / 116
    fx, fz = fy + a / 500, fy - b / 200
    g = lambda t: t ** 3 if t ** 3 > 0.008856 else (t - 16 / 116) / 7.787
    x, y, z = g(fx) * 0.95047, g(fy), g(fz) * 1.08883
    lin = (3.2406 * x - 1.5372 * y - 0.4986 * z, -0.9689 * x + 1.8758 * y + 0.0415 * z,
           0.0557 * x - 0.2040 * y + 1.0570 * z)
    out = []
    for c in lin:
        c = min(1.0, max(0.0, c))
        out.append(12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055)
    return out


def _stats(frames):
    n = 0
    s = [0.0, 0.0, 0.0]
    s2 = [0.0, 0.0, 0.0]
    chroma = 0.0
    for fr in frames:
        for i in range(0, len(fr), 3 * 2):      # every 2nd pixel is plenty
            lab = _lab(fr[i], fr[i + 1], fr[i + 2])
            for k in range(3):
                s[k] += lab[k]
                s2[k] += lab[k] * lab[k]
            chroma += math.hypot(lab[1], lab[2])
            n += 1
    if not n:
        raise ValueError('no frames read')
    mean = [v / n for v in s]
    std = [math.sqrt(max(0.0, s2[k] / n - mean[k] ** 2)) for k in range(3)]
    return mean, std, chroma / n


def color_stats(video, start: float = 0.0, duration: float | None = None, samples: int = 12) -> dict:
    """Mean Lab colour. L = brightness, a = green..red, b = blue..yellow, chroma = saturation."""
    dur = duration or (_duration(video) - start)
    step = max(0.1, dur / max(1, samples))
    mean, std, chroma = _stats(_frames(video, step, start, dur))
    return {'ok': True, 'L': round(mean[0], 1), 'a': round(mean[1], 1), 'b': round(mean[2], 1),
            'chroma': round(chroma, 1), 'std': [round(v, 1) for v in std], '_mean': mean, '_std': std}


def color_match(reference, clip, out_cube=None, start: float = 0.0, duration: float | None = None,
                strength: float = 0.9, lift: float = 0.0, approve_write: bool = False, target: dict | None = None) -> dict:
    """LUT that moves `clip` (its start..start+duration window) to the reference's colour.

    Lab mean/std transfer, blended by `strength`. `lift` adds brightness to the target
    (measured on real work: output came ~5 L darker than the target after crop and zoom).
    Use in ffmpeg as lut3d=file=<relative path> (a drive colon breaks the filter text).
    """
    if not 0 < strength <= 1:
        raise ValueError('strength must be in (0, 1]')
    if target:   # a measured style preset instead of a reference video: {'mean': [L,a,b], 'std': [L,a,b]}
        ref = {'ok': True, 'L': target['mean'][0], 'a': target['mean'][1], 'b': target['mean'][2],
               'chroma': target.get('chroma'), 'std': target['std'], '_mean': list(target['mean']),
               '_std': list(target['std'])}
    else:
        ref = color_stats(reference)
    src = color_stats(clip, start, duration, samples=6)
    mu_r = [ref['_mean'][0] + lift, ref['_mean'][1], ref['_mean'][2]]
    ratio = [min(2.2, max(0.5, ref['_std'][k] / max(src['_std'][k], 1e-3))) for k in range(3)]
    public = lambda d: {k: v for k, v in d.items() if not k.startswith('_')}
    res = {'reference': public(ref), 'clip_before': public(src), 'strength': strength, 'lift': lift}
    if not out_cube:
        res.update(ok=True, note='pass an output .cube path to write the LUT')
        return res
    out = Path(out_cube).expanduser()
    if not approve_write:
        return {'ok': False, 'outcome': 'approval_required', 'would_write': [str(out)],
                'hint': 'rerun with --approve-write after the owner says yes', **res}
    lines = [f'LUT_3D_SIZE {LUT_N}', 'DOMAIN_MIN 0 0 0', 'DOMAIN_MAX 1 1 1']
    grid = [round(i * 255 / (LUT_N - 1)) for i in range(LUT_N)]
    for b in grid:                      # .cube order: red changes fastest
        for g in grid:
            for r in grid:
                lab = _lab(r, g, b)
                moved = [(lab[k] - src['_mean'][k]) * ratio[k] + mu_r[k] for k in range(3)]
                rgb = _rgb(*[lab[k] + strength * (moved[k] - lab[k]) for k in range(3)])
                lines.append(f'{rgb[0]:.6f} {rgb[1]:.6f} {rgb[2]:.6f}')
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text('\n'.join(lines) + '\n', encoding='ascii')
    res.update(ok=True, saved=[str(out)], use='lut3d=file=<path relative to ffmpeg cwd>')
    return res


def line_times(video, x: int, y: int, w: int, h: int, bright: int = 238, min_frames: int = 6) -> dict:
    """On/off times of white on-screen text inside a crop box (pixels of the source video).

    Reads every frame; a line is 'on' while the share of bright pixels stays above a
    quarter of its peak. Use it to copy a reference's caption rhythm exactly.
    """
    path = Path(video).expanduser()
    if not path.is_file():
        raise FileNotFoundError(str(path))
    probe = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v', '-show_entries',
                            'stream=r_frame_rate', '-of', 'csv=p=0', str(path)], capture_output=True, text=True)
    num, _, den = probe.stdout.strip().partition('/')
    fps = float(num) / float(den or 1)
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(path), '-vf', f'crop={w}:{h}:{x}:{y},format=gray',
                          '-f', 'rawvideo', '-'], capture_output=True).stdout
    size = w * h
    share = [sum(1 for v in raw[i:i + size] if v > bright) / size for i in range(0, len(raw) - size + 1, size)]
    if not share:
        raise ValueError('no frames read (check the crop box)')
    thr = max(share) * 0.25
    segs, s = [], None
    for i, v in enumerate(share + [0.0]):
        if v > thr and s is None:
            s = i
        elif v <= thr and s is not None:
            if i - 1 - s > min_frames:
                segs.append({'t0': round(s / fps, 2), 't1': round((i - 1) / fps, 2)})
            s = None
    cuts = [round((segs[k]['t1'] + segs[k + 1]['t0']) / 2, 3) for k in range(len(segs) - 1)]
    return {'ok': True, 'fps': fps, 'lines': segs, 'count': len(segs), 'cuts_between_lines': cuts}
