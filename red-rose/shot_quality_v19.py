"""V19: measured per-shot technical quality (exposure, clipping, detail, motion).

Read-only, independent FFmpeg + standard-library implementation. It joins the
V16 cut heuristic and the V17 acoustic-silence timeline with luma measurements
taken from a small grayscale proxy of the source, then ranks shots and proposes
a reviewable EDL. Nothing is rendered, deleted or reordered.

These are TECHNICAL measurements on a 64x36 proxy. They are not composition,
focus, face, story or aesthetic judgement, and a high score is not proof that a
shot is the right one to keep.
"""
from __future__ import annotations

import math
import subprocess

from scene_edit_v16 import validate_edl, _number, MAX_EDIT_SECONDS
from audio_scene_v17 import timeline_analyze

PROXY_W, PROXY_H = 64, 36
_PIXELS = PROXY_W * PROXY_H
# Luma below 16 / above 239 on the 0..255 proxy counts as crushed / blown out.
_DARK = bytes(1 if v < 16 else 0 for v in range(256))
_BRIGHT = bytes(1 if v > 239 else 0 for v in range(256))

WEIGHTS = {'exposure': .35, 'detail': .25, 'motion': .15, 'audio': .25}
WEIGHTS_SILENT_SOURCE = {'exposure': .45, 'detail': .35, 'motion': .20, 'audio': 0.}
# Thresholds are explicit so a reviewer can see exactly why a flag was raised.
LIMITS = {'too_dark_mean_luma': .12, 'too_bright_mean_luma': .90,
          'clipped_fraction': .35, 'low_detail': .008,
          'static_motion': .002, 'high_motion': .12}
REJECT_FLAGS = ('too_dark', 'too_bright', 'clipped')


def _decode_proxy(metadata, sample_fps):
    """Decode the whole source once to bounded 64x36 gray frames."""
    cmd = ['ffmpeg', '-hide_banner', '-nostdin', '-v', 'error',
           '-i', metadata['source'], '-map', '0:v:0', '-an',
           '-vf', f'fps={sample_fps},scale={PROXY_W}:{PROXY_H},format=gray',
           '-f', 'rawvideo', '-pix_fmt', 'gray', 'pipe:1']
    raw = subprocess.run(cmd, capture_output=True, timeout=180, check=True).stdout
    if not raw or len(raw) % _PIXELS:
        raise ValueError('decoder produced incomplete or empty frame data')
    count = len(raw) // _PIXELS
    if count > math.ceil(metadata['duration'] * sample_fps) + sample_fps + 2:
        raise ValueError('decoder produced unexpected frame count')
    return raw, count


def _frame_stats(frame):
    """Mean luma, crushed/blown fractions and gradient detail of one frame."""
    mean = sum(frame) / (_PIXELS * 255)
    dark = frame.translate(_DARK).count(1) / _PIXELS
    bright = frame.translate(_BRIGHT).count(1) / _PIXELS
    # Vertical neighbours never wrap; horizontal pairs skip each row boundary.
    vertical = sum(abs(a - b) for a, b in zip(frame[PROXY_W:], frame))
    horizontal = 0
    for row in range(PROXY_H):
        line = frame[row * PROXY_W:(row + 1) * PROXY_W]
        horizontal += sum(abs(a - b) for a, b in zip(line[1:], line))
    pairs = (PROXY_H - 1) * PROXY_W + PROXY_H * (PROXY_W - 1)
    return mean, dark, bright, (vertical + horizontal) / (pairs * 255)


def _exposure_score(mean, clipped):
    """1.0 for mid-range luma with no clipping, falling to 0 at the extremes."""
    centred = max(0., 1. - abs(mean - .5) / .5)
    return max(0., min(1., centred * (1. - min(1., clipped / LIMITS['clipped_fraction']) * .7)))


def _motion_score(motion):
    """Favour visible but not chaotic change; static and shaky both score low."""
    if motion <= 0:
        return 0.
    if motion < .02:
        return motion / .02
    if motion <= .08:
        return 1.
    return max(0., 1. - (motion - .08) / .12)


def score_shots(source, *, max_clips=3, max_duration=30., threshold=.23,
                sample_fps=6, noise_db=-35, min_silence=.30):
    """Measure each detected shot and propose (never perform) a ranked edit.

    Detail is ranked relative to the most detailed shot of the SAME source, so
    scores are not comparable between different videos.
    """
    if type(max_clips) is not int or not 1 <= max_clips <= 16:
        raise ValueError('max_clips must be 1..16')
    _number(max_duration, .25, MAX_EDIT_SECONDS, 'max_duration')
    timeline = timeline_analyze(source, threshold=threshold, sample_fps=sample_fps,
                                noise_db=noise_db, min_silence=min_silence)
    metadata = timeline['source']
    raw, count = _decode_proxy(metadata, sample_fps)
    scenes = timeline['scenes']
    buckets = [{'n': 0, 'mean': 0., 'dark': 0., 'bright': 0., 'detail': 0.,
                'motion': [], } for _ in scenes]
    index = 0
    previous = None
    previous_index = None
    for i in range(count):
        t = i / sample_fps
        while index < len(scenes) - 1 and t >= scenes[index]['end']:
            index += 1
        frame = raw[i * _PIXELS:(i + 1) * _PIXELS]
        mean, dark, bright, detail = _frame_stats(frame)
        bucket = buckets[index]
        bucket['n'] += 1
        bucket['mean'] += mean
        bucket['dark'] += dark
        bucket['bright'] += bright
        bucket['detail'] += detail
        # Inter-frame change is only meaningful inside one shot, not across a cut.
        if previous is not None and previous_index == index:
            bucket['motion'].append(sum(abs(a - b) for a, b in zip(frame, previous)) / (_PIXELS * 255))
        previous, previous_index = frame, index
    measured = []
    for scene, bucket in zip(scenes, buckets):
        n = bucket['n']
        if not n:
            measured.append({**scene, 'sampled_frames': 0, 'measured': False,
                             'flags': ['not_sampled'], 'reject': True})
            continue
        motions = bucket['motion']
        motion = sum(motions) / len(motions) if motions else 0.
        jitter = (math.sqrt(sum((m - motion) ** 2 for m in motions) / len(motions))
                  if motions else 0.)
        mean, dark, bright = bucket['mean'] / n, bucket['dark'] / n, bucket['bright'] / n
        detail = bucket['detail'] / n
        flags = []
        if mean < LIMITS['too_dark_mean_luma']:
            flags.append('too_dark')
        if mean > LIMITS['too_bright_mean_luma']:
            flags.append('too_bright')
        if dark + bright > LIMITS['clipped_fraction']:
            flags.append('clipped')
        if detail < LIMITS['low_detail']:
            flags.append('low_detail')
        if len(motions) and motion < LIMITS['static_motion']:
            flags.append('static')
        if motion > LIMITS['high_motion']:
            flags.append('high_motion')
        measured.append({**scene, 'sampled_frames': n, 'measured': True,
                         'mean_luma': round(mean, 5),
                         'crushed_black_fraction': round(dark, 5),
                         'blown_white_fraction': round(bright, 5),
                         'detail': round(detail, 5),
                         'motion': round(motion, 5), 'motion_jitter': round(jitter, 5),
                         'flags': flags,
                         'reject': any(f in REJECT_FLAGS for f in flags)})
    best_detail = max((m['detail'] for m in measured if m['measured']), default=0.)
    weights = WEIGHTS if timeline['audio_available'] else WEIGHTS_SILENT_SOURCE
    for shot in measured:
        if not shot['measured']:
            shot['score'] = 0.
            continue
        parts = {'exposure': _exposure_score(shot['mean_luma'],
                                             shot['crushed_black_fraction'] + shot['blown_white_fraction']),
                 'detail': (shot['detail'] / best_detail) if best_detail > 0 else 0.,
                 'motion': _motion_score(shot['motion']),
                 'audio': shot['audible_fraction'] if shot['audible_fraction'] is not None else 0.}
        shot['score_parts'] = {k: round(v, 5) for k, v in parts.items()}
        shot['score'] = round(sum(parts[k] * weights[k] for k in weights), 5)
    ranked = sorted(measured, key=lambda s: (-s['score'], s['start']))
    for position, shot in enumerate(ranked, 1):
        shot['rank'] = position
    chosen = []
    total = 0.
    for shot in ranked:
        if len(chosen) >= max_clips:
            break
        if shot['reject'] or shot['duration'] < .25:
            continue
        if total + shot['duration'] <= max_duration + 1e-4:
            chosen.append(shot)
            total += shot['duration']
    chosen.sort(key=lambda s: s['start'])
    edl = [{'start': s['start'], 'end': s['end']} for s in chosen]
    if edl:
        validate_edl(metadata, edl)
    return {'status': 'proposal_only_not_rendered',
            'method': 'gray_proxy_luma_gradient_interframe_plus_acoustic_silence',
            'proxy': {'width': PROXY_W, 'height': PROXY_H, 'sample_fps': sample_fps,
                      'sampled_frames': count},
            'source': metadata, 'audio_available': timeline['audio_available'],
            'weights': weights, 'limits': LIMITS,
            'shots': sorted(measured, key=lambda s: s['start']),
            'ranking': [s['index'] for s in ranked],
            'rejected_shots': [{'index': s['index'], 'flags': s['flags']}
                               for s in measured if s['reject']],
            'suggested_edl': edl, 'selected_seconds': round(total, 4),
            'requires_explicit_approved_video_recut': True,
            'limitations': ('Technical proxy measurements only: no focus, face, composition, '
                            'story or dialogue understanding. Detail is relative to this source. '
                            'Cuts and quietness are heuristics; review the EDL before any export.')}
