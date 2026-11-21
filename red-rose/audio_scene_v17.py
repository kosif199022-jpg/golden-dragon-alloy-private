"""V17: local soundtrack silence + visual-cut timeline and explainable edit suggestions.

No transcript, semantic understanding, cloud services, old skill imports or writes.
Output is an EDL proposal. An explicit user-approved video.recut is required
for any actual editing or output files.
"""
from __future__ import annotations

import math
import re
import subprocess
from pathlib import Path

from scene_edit_v16 import probe_source, analyze_cuts, validate_edl, _number, MAX_EDIT_SECONDS

_SILENCE_START = re.compile(r'\bsilence_start:\s*(-?\d+(?:\.\d+)?)')
_SILENCE_END = re.compile(r'\bsilence_end:\s*(-?\d+(?:\.\d+)?)')


def detect_silences(source, *, noise_db=-35, min_silence=.30):
    """Detect acoustically quiet intervals using FFmpeg silencedetect.

    Quiet audio is not equivalent to an absence of speech. Low-level music and
    background noise may fool this algorithm; all times are approximate.
    """
    _number(noise_db, -90, -10, 'noise_db')
    _number(min_silence, .10, 10, 'min_silence')
    info = probe_source(source)
    if not info['audio']:
        return {'source': info, 'method': 'ffmpeg_silencedetect',
                'silences': [], 'audio_available': False,
                'limitations': 'No audio stream; speech/quietness not assessed.'}
    cmd = ['ffmpeg', '-hide_banner', '-nostdin', '-v', 'info', '-i', info['source'],
           '-map', '0:a:0', '-vn', '-af',
           f'silencedetect=noise={noise_db}dB:d={min_silence}', '-f', 'null', '-']
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=180,
                            check=True)
    intervals = []
    start = None
    for line in result.stderr.splitlines():
        found_start = _SILENCE_START.search(line)
        if found_start:
            start = max(0., min(float(found_start.group(1)), info['duration']))
        found_end = _SILENCE_END.search(line)
        if found_end and start is not None:
            end = max(start, min(float(found_end.group(1)), info['duration']))
            if end > start:
                intervals.append({'start': round(start, 4), 'end': round(end, 4)})
            start = None
    if start is not None and info['duration'] > start:
        intervals.append({'start': round(start, 4), 'end': round(info['duration'], 4)})
    return {'source': info, 'method': 'ffmpeg_silencedetect',
            'silences': intervals, 'audio_available': True,
            'noise_db': noise_db, 'min_silence': min_silence,
            'limitations': 'Acoustic silence only; not speech detection or transcription.'}


def _overlap(a, b, c, d):
    return max(0., min(b, d) - max(a, c))


def timeline_analyze(source, *, threshold=.23, sample_fps=6, noise_db=-35,
                     min_silence=.30, min_shot_seconds=.65):
    visual = analyze_cuts(source, threshold=threshold, sample_fps=sample_fps,
                          min_shot_seconds=min_shot_seconds)
    audio = detect_silences(source, noise_db=noise_db, min_silence=min_silence)
    shots = []
    for scene in visual['scenes']:
        duration = scene['duration']
        quiet = sum(_overlap(scene['start'], scene['end'], s['start'], s['end'])
                    for s in audio['silences'])
        ratio = round(min(1., max(0., quiet / duration)), 4) if audio['audio_available'] else None
        shots.append({**scene, 'quiet_fraction': ratio,
                      'audible_fraction': (round(1.-ratio, 4) if ratio is not None else None)})
    return {'status': 'analyzed_not_edited', 'source': visual['source'],
            'visual_method': visual['method'], 'audio_method': audio['method'],
            'visual_cuts': visual['cuts'], 'silences': audio['silences'],
            'audio_available': audio['audio_available'], 'scenes': shots,
            'limitations': 'No scene semantics, speaker detection or true speech alignment; cuts and quietness are heuristics.'}


def suggest_edit(source, *, max_clips=3, max_duration=30., min_audible_ratio=.20,
                 threshold=.23, sample_fps=6, noise_db=-35, min_silence=.30):
    """Suggest bounded EDL clips emphasizing acoustically active full scenes.

    Never writes/executes a recut. Tie-breaks are deterministic; selected shots
    are returned in source order, not arbitrary reordering or creative editing.
    """
    if type(max_clips) is not int or not 1 <= max_clips <= 16:
        raise ValueError('max_clips must be 1..16')
    _number(max_duration, .25, MAX_EDIT_SECONDS, 'max_duration')
    _number(min_audible_ratio, 0, 1, 'min_audible_ratio')
    report = timeline_analyze(source, threshold=threshold, sample_fps=sample_fps,
                              noise_db=noise_db, min_silence=min_silence)
    options = []
    for scene in report['scenes']:
        d = scene['duration']
        audible = scene['audible_fraction']
        # If the source is silent, rank visually discovered scenes by duration.
        if d < .25 or d > max_duration + .00001:
            continue
        if audible is not None and audible < min_audible_ratio:
            continue
        score = round((audible if audible is not None else .5) * .8 +
                      min(d, 4.) / 4. * .2, 5)
        options.append((score,scene))
    chosen = []
    total = 0.
    for score, scene in sorted(options, key=lambda x: (-x[0],x[1]['start'])):
        if len(chosen) >= max_clips:
            break
        if total + scene['duration'] <= max_duration + 1e-4:
            chosen.append((score,scene))
            total += scene['duration']
    chosen.sort(key=lambda x:x[1]['start'])
    edl = [{'start': s['start'], 'end': s['end']} for _,s in chosen]
    if edl:
        validate_edl(report['source'], edl)
    return {'status': 'proposal_only_not_rendered', 'method': 'audible_fraction_and_scene_duration',
            'source': report['source'], 'timeline': report,
            'suggested_edl': edl,
            'selected_clips': [{'score':sc,**shot} for sc,shot in chosen],
            'selected_seconds': round(total,4),
            'reason': 'Quiet scenes are deprioritized when audio exists; no meaning or dialogue was inferred.',
            'requires_explicit_approved_video_recut': True,
            'warning': 'A lack of noise is not proof of unimportant content. Review the proposed EDL before export.'}
