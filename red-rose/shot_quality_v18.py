"""Red Rose V18: measured per-shot technical quality + reviewable EDL ranking.

Native standard-library implementation over FFmpeg-decoded grayscale samples.
It measures *technical* image properties only: fine detail (Laplacian energy),
exposure/clipping, contrast and inter-frame motion. It does NOT judge story,
emotion, faces, composition rules or aesthetic value, and it never edits media.
Low detail can mean optical blur OR a genuinely flat subject (sky, wall, title
card); the flag says "low_detail", not "blurry", for that reason.
"""
from __future__ import annotations

import math
import subprocess

from scene_edit_v16 import probe_source, analyze_cuts, validate_edl, _number, MAX_EDIT_SECONDS

GRID_W, GRID_H = 96, 54

# Fixed, documented thresholds (0..1 scale of 8-bit luma). Tuned on synthetic
# FFmpeg test sources in test_shot_quality_v18.py; NOT calibrated on real footage.
THRESHOLDS = {
    'low_detail': .012,      # mean |Laplacian| / 255
    'dark_mean': .16,        # mean luma below this -> underexposed
    'bright_mean': .88,      # mean luma above this -> overexposed
    'clip_fraction': .45,    # >45% of pixels crushed (<=16) or blown (>=239)
    'low_contrast': .045,    # luma standard deviation / 255
    'static': .002,          # mean |frame difference| / 255
    'high_motion': .16,
}


def _decode_gray(source_path, sample_fps, duration):
    cmd = ['ffmpeg', '-hide_banner', '-nostdin', '-v', 'error',
           '-i', source_path, '-map', '0:v:0', '-an',
           '-vf', f'fps={sample_fps},scale={GRID_W}:{GRID_H},format=gray',
           '-f', 'rawvideo', '-pix_fmt', 'gray', 'pipe:1']
    raw = subprocess.run(cmd, capture_output=True, timeout=180, check=True).stdout
    size = GRID_W * GRID_H
    if not raw or len(raw) % size:
        raise ValueError('decoder produced incomplete or empty frame data')
    count = len(raw) // size
    if count > math.ceil(duration * sample_fps) + sample_fps + 2:
        raise ValueError('decoder produced unexpected frame count')
    return [raw[i*size:(i+1)*size] for i in range(count)]


def frame_metrics(frame):
    """Return detail/exposure/contrast for one GRID_W x GRID_H gray frame."""
    w, h = GRID_W, GRID_H
    if len(frame) != w * h:
        raise ValueError('frame has wrong size')
    n = len(frame)
    mean = sum(frame) / n
    var = sum((p - mean) ** 2 for p in frame) / n
    crushed = sum(1 for p in frame if p <= 16) / n
    blown = sum(1 for p in frame if p >= 239) / n
    lap = 0
    for y in range(1, h - 1):
        row = y * w
        up, down = row - w, row + w
        for x in range(1, w - 1):
            i = row + x
            lap += abs(4 * frame[i] - frame[i-1] - frame[i+1] - frame[up+x] - frame[down+x])
    lap_mean = lap / ((w - 2) * (h - 2) * 255)
    return {'detail': lap_mean, 'luma_mean': mean / 255,
            'contrast': math.sqrt(var) / 255, 'crushed': crushed, 'blown': blown}


def _motion(a, b):
    # Every second pixel keeps CPU bounded; enough for a whole-frame average.
    pa, pb = a[::2], b[::2]
    return sum(abs(x - y) for x, y in zip(pa, pb)) / (len(pa) * 255)


def _flags(m):
    t = THRESHOLDS
    flags = []
    if m['detail'] < t['low_detail']:
        flags.append('low_detail')
    if m['luma_mean'] < t['dark_mean'] or m['crushed'] > t['clip_fraction']:
        flags.append('underexposed')
    if m['luma_mean'] > t['bright_mean'] or m['blown'] > t['clip_fraction']:
        flags.append('overexposed')
    if m['contrast'] < t['low_contrast']:
        flags.append('low_contrast')
    if m['motion'] is not None:
        if m['motion'] < t['static']:
            flags.append('static')
        elif m['motion'] > t['high_motion']:
            flags.append('high_motion')
    return flags


def _score(m):
    """0..1 technical score; explainable weighted sum, not an aesthetic grade."""
    detail = min(1., m['detail'] / .06)
    exposure = max(0., 1. - abs(m['luma_mean'] - .5) / .5)
    clipping = max(0., 1. - (m['crushed'] + m['blown']) / .5)
    contrast = min(1., m['contrast'] / .2)
    if m['motion'] is None:
        motion = .5
    else:
        # Prefer some movement; penalize frozen and chaotic shots.
        motion = min(1., m['motion'] / .02) if m['motion'] < .02 else \
            max(0., 1. - max(0., m['motion'] - .12) / .2)
    return round(.35*detail + .2*exposure + .15*clipping + .15*contrast + .15*motion, 5)


def shot_quality(source, *, threshold=.23, sample_fps=4, min_shot_seconds=.65,
                 max_clips=3, max_duration=30., min_score=.5):
    """Measure every detected shot and propose the technically strongest ones.

    Read-only. Returns status 'analyzed_not_edited'; any export still needs an
    explicit, approval-gated video.recut with the returned (or edited) EDL.
    """
    if isinstance(sample_fps, bool) or type(sample_fps) is not int or not 2 <= sample_fps <= 8:
        raise ValueError('sample_fps must be an integer from 2 to 8')
    if isinstance(max_clips, bool) or type(max_clips) is not int or not 1 <= max_clips <= 16:
        raise ValueError('max_clips must be 1..16')
    _number(max_duration, .25, MAX_EDIT_SECONDS, 'max_duration')
    _number(min_score, 0, 1, 'min_score')
    cuts = analyze_cuts(source, threshold=threshold, sample_fps=sample_fps,
                        min_shot_seconds=min_shot_seconds)
    meta = cuts['source']
    frames = _decode_gray(meta['source'], sample_fps, meta['duration'])
    per_frame = [frame_metrics(f) for f in frames]
    shots = []
    for scene in cuts['scenes']:
        first = max(0, int(math.floor(scene['start'] * sample_fps + 1e-6)))
        last = min(len(frames), int(math.ceil(scene['end'] * sample_fps - 1e-6)))
        # Skip the boundary sample on each side so a cut never counts as motion/blur.
        inner = list(range(first + 1, last - 1)) if last - first >= 4 else list(range(first, last))
        if not inner:
            inner = [min(first, len(frames) - 1)]
        sel = [per_frame[i] for i in inner]
        avg = {k: sum(s[k] for s in sel) / len(sel) for k in sel[0]}
        motions = [_motion(frames[i-1], frames[i]) for i in inner if i - 1 in inner]
        avg['motion'] = (sum(motions) / len(motions)) if motions else None
        metrics = {k: (round(v, 5) if v is not None else None) for k, v in avg.items()}
        shots.append({**scene, 'samples': len(sel), 'metrics': metrics,
                      'flags': _flags(avg), 'score': _score(avg)})
    ranked = sorted((s for s in shots
                     if s['score'] >= min_score and s['duration'] <= max_duration + 1e-5),
                    key=lambda s: (-s['score'], s['start']))
    chosen, total = [], 0.
    for s in ranked:
        if len(chosen) >= max_clips:
            break
        if total + s['duration'] <= max_duration + 1e-4:
            chosen.append(s)
            total += s['duration']
    chosen.sort(key=lambda s: s['start'])
    edl = [{'start': s['start'], 'end': s['end']} for s in chosen]
    if edl:
        validate_edl(meta, edl)
    return {'status': 'analyzed_not_edited',
            'method': 'gray_laplacian_exposure_contrast_motion',
            'source': meta, 'sample_fps': sample_fps, 'grid': [GRID_W, GRID_H],
            'thresholds': dict(THRESHOLDS), 'shots': shots,
            'suggested_edl': edl, 'selected_seconds': round(total, 4),
            'requires_explicit_approved_video_recut': True,
            'limitations': ('Technical measurements on a 96x54 downscale only. low_detail cannot '
                            'separate optical blur from flat subjects; no faces, composition, story '
                            'or aesthetics are judged. Thresholds are not calibrated on real footage.')}
