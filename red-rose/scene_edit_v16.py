"""Red Rose V16: locally inspect real video for cuts and assemble selected shots.

Independent FFprobe/FFmpeg implementation. No legacy skill runtime or cloud API.
The cut detector is a coarse RGB-change heuristic, not semantic scene understanding.
"""
from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
import tempfile
from fractions import Fraction
from pathlib import Path

from verify_media import verify_video

ALLOWED_VIDEO = {'.mp4', '.mov', '.mkv', '.webm'}
MAX_SOURCE_BYTES = 2_000_000_000
MAX_SCAN_SECONDS = 600.0
MAX_EDIT_SECONDS = 300.0
MAX_EDITS = 16


def _number(value, low, high, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f'{name} must be a finite number between {low} and {high}')
    return float(value)


def probe_source(source):
    """Read strictly bounded media metadata and reject URLs/nonlocal inputs."""
    if not isinstance(source, (str, os.PathLike)):
        raise ValueError('source must be a local media path')
    source = Path(source).expanduser().resolve()
    if (not source.is_file() or source.suffix.lower() not in ALLOWED_VIDEO or
            not 0 < source.stat().st_size <= MAX_SOURCE_BYTES):
        raise ValueError('source must be a supported local video under 2 GB')
    if not shutil.which('ffprobe') or not shutil.which('ffmpeg'):
        raise RuntimeError('FFmpeg and FFprobe must be installed')
    cmd = ['ffprobe', '-v', 'error', '-show_entries',
           'format=duration:stream=codec_type,width,height,avg_frame_rate',
           '-of', 'json', str(source)]
    completed = subprocess.run(cmd, capture_output=True, text=True,
                               timeout=30, check=True)
    result = json.loads(completed.stdout)
    streams = result.get('streams', [])
    videos = [s for s in streams if s.get('codec_type') == 'video']
    if len(videos) != 1:
        raise ValueError('exactly one video stream is required')
    duration = float(result['format']['duration'])
    if not math.isfinite(duration) or not 0 < duration <= MAX_SCAN_SECONDS:
        raise ValueError('source duration must be between 0 and 600 seconds')
    width, height = int(videos[0]['width']), int(videos[0]['height'])
    if not 16 <= width <= 3840 or not 16 <= height <= 2160:
        raise ValueError('source dimensions outside supported bounds')
    fps = float(Fraction(videos[0].get('avg_frame_rate') or '0/1'))
    if not math.isfinite(fps) or fps <= 0:
        raise ValueError('source FPS invalid')
    return {'source': str(source), 'duration': duration, 'width': width,
            'height': height, 'fps': fps,
            'audio': any(s.get('codec_type') == 'audio' for s in streams),
            'bytes': source.stat().st_size}


def analyze_cuts(source, *, threshold=.23, sample_fps=6, min_shot_seconds=.65):
    """Sample downscaled source; flag substantial whole-frame color changes.

    Timestamps are approximate to +/- 1/sample_fps; no transcript or person
    detection. Fast motion, flashes and fades can create false positives.
    """
    _number(threshold, .06, .95, 'threshold')
    if isinstance(sample_fps, bool) or type(sample_fps) is not int or not 2 <= sample_fps <= 12:
        raise ValueError('sample_fps must be an integer from 2 to 12')
    _number(min_shot_seconds, .25, 60, 'min_shot_seconds')
    metadata = probe_source(source)
    vw, vh = 80, 45
    frame_bytes = vw * vh * 3
    cmd = ['ffmpeg', '-hide_banner', '-nostdin', '-v', 'error',
           '-i', metadata['source'], '-map', '0:v:0', '-an',
           '-vf', f'fps={sample_fps},scale={vw}:{vh},format=rgb24',
           '-f', 'rawvideo', '-pix_fmt', 'rgb24', 'pipe:1']
    completed = subprocess.run(cmd, capture_output=True, timeout=180, check=True)
    raw = completed.stdout
    if not raw or len(raw) % frame_bytes:
        raise ValueError('decoder produced incomplete or empty frame data')
    count = len(raw) // frame_bytes
    if count > math.ceil(metadata['duration'] * sample_fps) + sample_fps + 2:
        raise ValueError('decoder produced unexpected frame count')
    # Sample every fourth RGB byte for predictable bounded standard-library CPU.
    prev = None
    last_cut = 0.0
    cuts = []
    scores = []
    for i in range(count):
        frame = raw[i*frame_bytes:(i+1)*frame_bytes:4]
        if prev is not None:
            delta = sum(abs(a-b) for a, b in zip(frame, prev)) / (len(frame)*255)
            t = i/sample_fps
            if delta >= threshold and (t - last_cut) >= min_shot_seconds and \
                    (metadata['duration'] - t) >= min_shot_seconds:
                cuts.append(round(t, 4))
                scores.append(round(delta, 5))
                last_cut = t
        prev = frame
    bounds = [0.] + cuts + [metadata['duration']]
    scenes = [{'index': j+1, 'start': round(bounds[j], 4),
               'end': round(bounds[j+1], 4),
               'duration': round(bounds[j+1]-bounds[j], 4)}
              for j in range(len(bounds)-1)]
    return {'status': 'analyzed_not_edited', 'method': 'sampled_mean_absolute_rgb',
            'accuracy': f'cut time approximate within {1/sample_fps:.3f}s; flashes/motion can cause false cuts',
            'source': metadata, 'threshold': threshold, 'sample_fps': sample_fps,
            'sampled_frames': count, 'cuts': cuts, 'cut_strengths': scores,
            'scenes': scenes, 'suggested_edl': [{'start': r['start'], 'end': r['end']} for r in scenes]}


def validate_edl(metadata, segments):
    """User-approved cut list only; reject hidden/unbounded operations."""
    if not isinstance(segments, list) or not 1 <= len(segments) <= MAX_EDITS:
        raise ValueError(f'segments must contain 1..{MAX_EDITS} shots')
    normalized = []
    total = 0.
    for item in segments:
        if not isinstance(item, dict) or set(item) != {'start', 'end'}:
            raise ValueError('each segment must contain only start and end')
        start = _number(item['start'], 0, MAX_SCAN_SECONDS, 'start')
        end = _number(item['end'], 0, MAX_SCAN_SECONDS, 'end')
        if end - start < .18 or end > metadata['duration'] + .025:
            raise ValueError('segment is too short or exceeds source duration')
        total += end-start
        if total > MAX_EDIT_SECONDS:
            raise ValueError('total selected duration exceeds 300-second budget')
        normalized.append({'start': round(start, 4), 'end': round(end, 4)})
    return normalized, total


def recut(source, segments, output, *, fps=24):
    """Produce original-media hard-cut compilation preserving existing audio.

    Output is new only; never replaces a source or preexisting target.
    Each segment is individually re-timestamped before FFmpeg concat.
    """
    if type(fps) is not int or not 6 <= fps <= 60:
        raise ValueError('fps must be an integer 6..60')
    meta = probe_source(source)
    edit, selected_seconds = validate_edl(meta, segments)
    target = Path(output).expanduser().resolve()
    if target.suffix.lower() != '.mp4' or not target.parent.is_dir() or target.exists():
        raise ValueError('output must be a new .mp4 in an existing folder')
    if target == Path(meta['source']):
        raise ValueError('cannot overwrite source video')
    if meta['width'] % 2 or meta['height'] % 2:
        raise ValueError('yuv420p requires even input dimensions')
    graph = []
    pieces = []
    for i, shot in enumerate(edit):
        start, end = shot['start'], shot['end']
        graph.append(f'[0:v]trim=start={start:.4f}:end={end:.4f},setpts=PTS-STARTPTS,'
                     f'fps={fps},format=yuv420p[v{i}]')
        pieces.append(f'[v{i}]')
        if meta['audio']:
            graph.append(f'[0:a]atrim=start={start:.4f}:end={end:.4f},'
                         f'asetpts=PTS-STARTPTS,aresample=async=1:first_pts=0[a{i}]')
            pieces.append(f'[a{i}]')
    a = 1 if meta['audio'] else 0
    graph.append(''.join(pieces) + f'concat=n={len(edit)}:v=1:a={a}[v]'+('[a]' if a else ''))
    with tempfile.NamedTemporaryFile(suffix='.mp4', prefix='.rose-recut-', dir=target.parent, delete=False) as tmp:
        stage = Path(tmp.name)
    try:
        cmd = ['ffmpeg', '-hide_banner', '-nostdin', '-v', 'error', '-y',
               '-i', meta['source'], '-filter_complex', ';'.join(graph),
               '-map', '[v]', '-c:v', 'libx264', '-preset', 'veryfast',
               '-crf', '23', '-pix_fmt', 'yuv420p', '-r', str(fps)]
        if meta['audio']:
            cmd += ['-map', '[a]', '-c:a', 'aac', '-b:a', '128k']
        else:
            cmd += ['-an']
        cmd += ['-movflags', '+faststart', str(stage)]
        subprocess.run(cmd, capture_output=True, timeout=180, check=True)
        qa = verify_video(stage, expected_fps=fps, width=meta['width'],
                          height=meta['height'], expected_audio=meta['audio'])
        if abs(qa['duration'] - selected_seconds) > max(.22, 2 / fps):
            raise ValueError('rendered duration differs unexpectedly from edit plan')
        # Exclusive creation avoids accidental overwrite if a path appears during render.
        created = False
        try:
            with target.open('xb') as dest:
                created = True
                with stage.open('rb') as src:
                    shutil.copyfileobj(src, dest, length=1024*1024)
        except BaseException:
            if created:
                target.unlink(missing_ok=True)
            raise
        return {'status': 'rendered_and_verified', 'output': str(target),
                'edl': edit, 'segments': len(edit),
                'selected_seconds': round(selected_seconds, 4),
                'audio_preserved': meta['audio'], 'qa': qa,
                'method': 'FFmpeg trim+concat with timestamp reset'}
    finally:
        stage.unlink(missing_ok=True)
