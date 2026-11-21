"""Red Rose V25: editing craft helpers (beat sync, story arc, pacing, safe
crossfade, stabilisation estimate, colour match, vertical reframe).

Standard library + scene_edit_v16 / verify_media only. Local files only
(validated with scene_edit_v16.probe_source; URLs and network paths rejected).
FFmpeg/FFprobe are called only as subprocess.run([...], capture_output=True,
timeout=...). No network, no shell, no printing.

Every op is listed in EFFECTS as 'read' or 'write'. The only write op
(safe_crossfade) needs approve_write=True, writes only a NEW .mp4 inside an
existing folder (never the source, never an existing file), stages to a temp
file in the same folder, copies with exclusive create ('xb') and verifies the
result with verify_media.verify_video before reporting success.

Owner rules honoured by rendered output: AAC audio inside MP4, no fade from
black / no black first frame, no overlays, bloom, fog or extra filters, no
burned-in descriptive text. Read ops never modify footage.

These are heuristics for an editor's assistant, not broadcast-grade tools; each
op returns its assumptions and limits next to its result.
"""
from __future__ import annotations

import json
import math
import operator
import os
import re
import shutil
import subprocess
import sys
import tempfile
from array import array
from pathlib import Path

from scene_edit_v16 import probe_source
from verify_media import verify_video

MAX_PARAMS = 24
MAX_BEAT_SECONDS = 300.0
MAX_CUTS = 200
MAX_SHOTS = 200
MAX_PROXY_FRAMES = 600
MAX_SVG_CHARS = 200_000

TOPICS = {
    '15.04': 'beat_sync_cuts',
    '15.05': 'story_arc',
    '15.06': 'pacing_balance',
    '15.07': 'safe_crossfade',
    '15.08': 'stabilize_estimate',
    '15.09': 'colour_match',
    '15.10': 'vertical_reframe',
}

TOPIC_NAMES_AR = {
    '15.04': 'تزامن القطع مع الإيقاع',
    '15.05': 'تدرج المشاهد السينمائي',
    '15.06': 'توازن أطوال اللقطات',
    '15.07': 'انتقالات متوافقة بصريًا',
    '15.08': 'تثبيت حركة الكاميرا',
    '15.09': 'تحسين جودة الألوان',
    '15.10': 'إخراج عمودي للموبايل',
}

EFFECTS = {
    'beat_sync_cuts': 'read',
    'story_arc': 'read',
    'pacing_balance': 'read',
    'safe_crossfade': 'write',
    'stabilize_estimate': 'read',
    'colour_match': 'read',
    'vertical_reframe': 'read',
}


# --------------------------------------------------------------------------- validation

def _no_extra(extra):
    if extra:
        raise ValueError('unknown parameter(s): ' + ', '.join(sorted(map(str, extra))))


def _num(value, low, high, name):
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value)):
        raise ValueError(f'{name} must be a finite number')
    value = float(value)
    if not low <= value <= high:
        raise ValueError(f'{name} must be in [{low}, {high}]')
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


def _list(value, low, high, name):
    if not isinstance(value, (list, tuple)) or not low <= len(value) <= high:
        raise ValueError(f'{name} must be a list of {low}..{high} items')
    return list(value)


_URL = re.compile(r'^[A-Za-z][A-Za-z0-9+.\-]*://')


def _path_text(value, name):
    if value is None:
        raise ValueError(f'{name} is required')
    if isinstance(value, bytes) or not isinstance(value, (str, os.PathLike)):
        raise ValueError(f'{name} must be a local file path')
    text = os.fspath(value)
    if not isinstance(text, str) or not text.strip():
        raise ValueError(f'{name} must be a non-empty local file path')
    if _URL.match(text) or text.startswith(('\\\\', '//')):
        raise ValueError(f'{name} must be a local file, not a URL or network path')
    return text


def _source(value, name='source'):
    meta = probe_source(_path_text(value, name))
    return meta


def _new_output(value, forbidden):
    text = _path_text(value, 'output')
    target = Path(text).expanduser().resolve()
    if target.suffix.lower() != '.mp4' or not target.parent.is_dir() or target.exists():
        raise ValueError('output must be a new .mp4 path in an existing folder')
    if any(target == Path(p).resolve() for p in forbidden):
        raise ValueError('output must not be a source path')
    return target


def _pack(op, result, assumptions, limits):
    return {'op': op, 'result': result, 'assumptions': list(assumptions),
            'limits': list(limits)}


def _r(x, nd=4):
    return round(float(x), nd)


# --------------------------------------------------------------------------- ffmpeg helpers

def _tool(cmd, timeout):
    """The module's single subprocess entry point (argument list, no shell)."""
    completed = subprocess.run([*cmd], capture_output=True, timeout=timeout)
    if completed.returncode != 0:
        tail = completed.stderr.decode('utf-8', 'replace')[-400:]
        raise RuntimeError(f'{cmd[0]} failed: {tail.strip()}')
    return completed.stdout


def _proxy_size(meta, width):
    height = max(2, int(round(width * meta['height'] / meta['width'] / 2)) * 2)
    return width, height


def _gray_frames(meta, width, height, fps, *, max_seconds, max_frames):
    cmd = ['ffmpeg', '-hide_banner', '-nostdin', '-v', 'error',
           '-i', meta['source'], '-map', '0:v:0', '-an', '-t', f'{max_seconds:.3f}',
           '-vf', f'fps={fps},scale={width}:{height}:flags=area,format=gray',
           '-frames:v', str(max_frames), '-f', 'rawvideo', '-pix_fmt', 'gray', 'pipe:1']
    raw = _tool(cmd, 180)
    size = width * height
    if not raw or len(raw) % size:
        raise ValueError('decoder produced incomplete or empty proxy frames')
    return [raw[i:i + size] for i in range(0, len(raw), size)]


def _rgb_frame(meta, t, width):
    width, height = _proxy_size(meta, width)
    cmd = ['ffmpeg', '-hide_banner', '-nostdin', '-v', 'error', '-ss', f'{t:.4f}',
           '-i', meta['source'], '-map', '0:v:0', '-an', '-frames:v', '1',
           '-vf', f'scale={width}:{height}:flags=area,format=rgb24',
           '-f', 'rawvideo', '-pix_fmt', 'rgb24', 'pipe:1']
    raw = _tool(cmd, 60)
    if len(raw) != width * height * 3:
        raise ValueError('could not decode a frame at the requested time')
    return raw, width, height


def _first_frame_luma(path):
    cmd = ['ffmpeg', '-hide_banner', '-nostdin', '-v', 'error', '-i', str(path),
           '-map', '0:v:0', '-an', '-frames:v', '1',
           '-vf', 'scale=64:-2:flags=area,format=gray',
           '-f', 'rawvideo', '-pix_fmt', 'gray', 'pipe:1']
    raw = _tool(cmd, 60)
    if not raw:
        raise ValueError('could not decode first frame')
    return {'mean': _r(sum(raw) / len(raw), 2), 'max': max(raw)}


def _is_black(luma):
    return luma['mean'] < 16 and luma['max'] < 40


def _video_stream_duration(meta):
    cmd = ['ffprobe', '-v', 'error', '-select_streams', 'v:0',
           '-show_entries', 'stream=duration', '-of', 'json', meta['source']]
    data = json.loads(_tool(cmd, 30).decode('utf-8', 'replace'))
    try:
        value = float(data['streams'][0]['duration'])
        if math.isfinite(value) and value > 0:
            return value
    except (KeyError, IndexError, TypeError, ValueError):
        pass
    return meta['duration']


def _smooth(values, radius):
    n = len(values)
    if radius <= 0 or n < 3:
        return list(values)
    out = []
    for i in range(n):
        acc = 0.0
        for j in range(i - radius, i + radius + 1):
            acc += values[min(max(j, 0), n - 1)]
        out.append(acc / (2 * radius + 1))
    return out


def _stats(values):
    n = len(values)
    mean = sum(values) / n
    var = sum((v - mean) ** 2 for v in values) / n
    std = math.sqrt(var)
    srt = sorted(values)
    median = srt[n // 2] if n % 2 else (srt[n // 2 - 1] + srt[n // 2]) / 2
    return {'count': n, 'total': _r(sum(values)), 'mean': _r(mean), 'asl': _r(mean),
            'median': _r(median), 'std': _r(std), 'cv': _r(std / mean if mean else 0.0),
            'min': _r(srt[0]), 'max': _r(srt[-1])}


# --------------------------------------------------------------------------- 15.04 beat_sync_cuts

def _decode_audio(meta, sr, max_seconds):
    cmd = ['ffmpeg', '-hide_banner', '-nostdin', '-v', 'error', '-i', meta['source'],
           '-map', '0:a:0', '-vn', '-ac', '1', '-ar', str(sr), '-t', f'{max_seconds:.3f}',
           '-acodec', 'pcm_s16le', '-f', 's16le', 'pipe:1']
    raw = _tool(cmd, 180)
    if len(raw) % 2:
        raw = raw[:-1]
    samples = array('h')
    samples.frombytes(raw)
    if sys.byteorder == 'big':
        samples.byteswap()
    if not samples:
        raise ValueError('audio stream decoded to no samples')
    return samples


def beat_sync_cuts(*, source=None, audio_rights_confirmed=False, cut_times=None,
                   min_bpm=60.0, max_bpm=200.0, max_snap_ms=250.0,
                   onset_sensitivity=1.0, **extra):
    """Detect onsets/beats from the source's audio energy and snap cuts to beats.

    Audio is analysed only when audio_rights_confirmed=True (the caller states
    they may use this music). Pipeline: FFmpeg decodes mono 8 kHz PCM via a
    pipe -> 5 ms energy envelope -> log-compressed positive energy flux ->
    peak picking -> tempo from flux autocorrelation with a log-normal prior
    around 120 BPM -> phase-aligned beat grid, each grid beat snapped to the
    nearest onset within min(70 ms, period/6) -> cuts snapped to nearest beat.
    """
    _no_extra(extra)
    meta = _source(source)
    _bool(audio_rights_confirmed, 'audio_rights_confirmed')
    cuts = [] if cut_times is None else [
        _num(c, 0, meta['duration'], f'cut_times[{i}]')
        for i, c in enumerate(_list(cut_times, 0, MAX_CUTS, 'cut_times'))]
    min_bpm = _num(min_bpm, 30, 300, 'min_bpm')
    max_bpm = _num(max_bpm, 30, 300, 'max_bpm')
    if max_bpm < min_bpm * 1.2:
        raise ValueError('max_bpm must be at least 1.2 x min_bpm')
    max_snap_ms = _num(max_snap_ms, 1, 5000, 'max_snap_ms')
    sens = _num(onset_sensitivity, 0.2, 5.0, 'onset_sensitivity')
    assumptions = ['Constant tempo over the analysed span; beat grid is global, then locally snapped to onsets.',
                   'Onsets = rises in short-time energy (5 ms hops); percussive material works best.',
                   'Tempo prior centred on 120 BPM resolves half/double-tempo ambiguity.']
    limits = [f'Analyses at most {MAX_BEAT_SECONDS:.0f} s of audio at 8 kHz mono.',
              'Onset times are quantised to 5 ms; expect ~+-10 ms on clean clicks, worse on soft or legato music.',
              'No downbeat/bar detection, no tempo changes, no genre or meaning inference.',
              'Proposal only: nothing is cut or written.']
    if not audio_rights_confirmed:
        return _pack('beat_sync_cuts', {
            'status': 'audio_rights_confirmation_required',
            'source': meta['source'],
            'message': 'Set audio_rights_confirmed=True only if you have the right to use this audio; it was not decoded.'},
            assumptions, limits)
    if not meta['audio']:
        raise ValueError('source has no audio stream')
    sr, hop = 8000, 40
    hop_s = hop / sr
    samples = _decode_audio(meta, sr, min(meta['duration'], MAX_BEAT_SECONDS))
    n_hops = len(samples) // hop
    if n_hops < 40:
        raise ValueError('audio too short for beat analysis (needs >= 0.2 s)')
    energy = []
    for i in range(n_hops):
        seg = samples[i * hop:(i + 1) * hop]
        energy.append(sum(map(operator.mul, seg, seg)) / hop)
    emax = max(energy) or 1.0
    env = [math.log1p(1000.0 * e / emax) for e in energy]
    flux = [0.0] + [max(0.0, env[i] - env[i - 1]) for i in range(1, n_hops)]
    fmax = max(flux)
    if fmax <= 0:
        return _pack('beat_sync_cuts', {'status': 'no_onsets_found', 'source': meta['source'],
                                        'onsets': [], 'beats': [], 'tempo_bpm': None,
                                        'snapped_cuts': []}, assumptions, limits)
    mean = sum(flux) / n_hops
    std = math.sqrt(sum((f - mean) ** 2 for f in flux) / n_hops)
    thr = max(mean + std / sens, 0.1 * fmax / sens)
    win = 10  # +-50 ms local maximum
    min_gap = int(round(0.1 / hop_s))
    onsets_idx = []
    for i in range(1, n_hops):
        f = flux[i]
        if f < thr:
            continue
        lo, hi = max(0, i - win), min(n_hops, i + win + 1)
        if f < max(flux[lo:hi]) or (onsets_idx and i - onsets_idx[-1] < min_gap):
            continue
        onsets_idx.append(i)
    onsets = [i * hop_s for i in onsets_idx]
    # Tempo via unbiased autocorrelation of the flux envelope + log-normal prior.
    lag_lo = max(1, int(round(60.0 / max_bpm / hop_s)))
    lag_hi = min(n_hops - 2, int(round(60.0 / min_bpm / hop_s)))
    best = None
    for lag in range(lag_lo, lag_hi + 1):
        acf = sum(map(operator.mul, flux, flux[lag:])) / (n_hops - lag)
        bpm = 60.0 / (lag * hop_s)
        score = acf * math.exp(-0.5 * (math.log2(bpm / 120.0)) ** 2)
        if best is None or score > best[0]:
            best = (score, lag)
    if best is None or best[0] <= 0:
        tempo = None
        beats = list(onsets)
    else:
        lag = best[1]
        phase = max(range(lag), key=lambda p: sum(flux[p::lag]))
        period = lag * hop_s
        tol = min(0.07, period / 6)
        grid = []
        t = phase * hop_s
        while t <= meta['duration'] + 1e-9 and t <= n_hops * hop_s:
            grid.append(t)
            t += period
        snapped = []
        for k, g in enumerate(grid):
            near = min(onsets, key=lambda o: abs(o - g)) if onsets else None
            snapped.append((k, near if near is not None and abs(near - g) <= tol else None))
        fit = [(k, o) for k, o in snapped if o is not None]
        if len(fit) >= 2:
            mk = sum(k for k, _ in fit) / len(fit)
            mo = sum(o for _, o in fit) / len(fit)
            den = sum((k - mk) ** 2 for k, _ in fit)
            period = sum((k - mk) * (o - mo) for k, o in fit) / den if den else period
            t0 = mo - period * mk
        else:
            t0 = phase * hop_s
        beats = [o if o is not None else t0 + k * period for k, o in snapped]
        beats = [b for b in beats if 0 <= b <= meta['duration']]
        tempo = 60.0 / period if period > 0 else None
    snapped_cuts = []
    for c in cuts:
        if not beats:
            snapped_cuts.append({'cut': _r(c), 'beat': None, 'distance_ms': None,
                                 'snapped_to': _r(c), 'snapped': False})
            continue
        b = min(beats, key=lambda x: abs(x - c))
        dist = (b - c) * 1000.0
        ok = abs(dist) <= max_snap_ms
        snapped_cuts.append({'cut': _r(c), 'beat': _r(b), 'distance_ms': _r(dist, 1),
                             'snapped_to': _r(b if ok else c), 'snapped': ok})
    intervals = [beats[i + 1] - beats[i] for i in range(len(beats) - 1)]
    return _pack('beat_sync_cuts', {
        'status': 'analyzed_not_edited', 'source': meta['source'],
        'method': 'energy_flux_onsets+autocorrelation_tempo',
        'tempo_bpm': _r(tempo, 2) if tempo else None,
        'onsets': [_r(o) for o in onsets[:2000]],
        'beats': [_r(b) for b in beats[:2000]],
        'beat_interval_stats': _stats(intervals) if intervals else None,
        'snapped_cuts': snapped_cuts,
        'analysed_seconds': _r(len(samples) / sr)}, assumptions, limits)


# --------------------------------------------------------------------------- 15.05 story_arc

_ROLE_RANK = {'opening': 0, 'setup': 0, 'rising': 1, 'climax': 2, 'falling': 3, 'resolution': 4}
_ROLE_DEFAULT_INTENSITY = {'opening': 0.2, 'setup': 0.3, 'rising': 0.55, 'climax': 1.0,
                           'falling': 0.5, 'resolution': 0.25}
_STAGE = {0: 'opening', 1: 'rising', 2: 'climax', 3: 'resolution', 4: 'resolution'}


def story_arc(*, shots=None, **extra):
    """Check and arrange tagged shots on an opening/rising/climax/resolution arc.

    shots: [{'id': str, 'role': opening|setup|rising|climax|falling|resolution,
             'intensity': 0..1 (optional), 'duration': seconds (optional)}]
    in the order the editor currently has them.
    """
    _no_extra(extra)
    if shots is None:
        raise ValueError('shots is required')
    items = _list(shots, 1, MAX_SHOTS, 'shots')
    norm = []
    seen = set()
    for i, s in enumerate(items):
        if not isinstance(s, dict) or not {'id', 'role'} <= set(s) or \
                not set(s) <= {'id', 'role', 'intensity', 'duration'}:
            raise ValueError(f'shots[{i}] needs id and role (optional intensity, duration) only')
        sid = s['id']
        if not isinstance(sid, str) or not 1 <= len(sid) <= 64 or sid in seen:
            raise ValueError(f'shots[{i}].id must be a unique string of 1..64 chars')
        seen.add(sid)
        role = _choice(s['role'], set(_ROLE_RANK), f'shots[{i}].role')
        inten = _num(s['intensity'], 0, 1, f'shots[{i}].intensity') if 'intensity' in s \
            else _ROLE_DEFAULT_INTENSITY[role]
        dur = _num(s['duration'], 0.04, 3600, f'shots[{i}].duration') if 'duration' in s else None
        norm.append({'index': i, 'id': sid, 'role': role, 'intensity': inten, 'duration': dur})
    problems = []

    def add(code, severity, ids, message):
        problems.append({'code': code, 'severity': severity, 'shots': ids, 'message': message})

    setup_idx = [s['index'] for s in norm if _ROLE_RANK[s['role']] == 0]
    climax_idx = [s['index'] for s in norm if s['role'] == 'climax']
    resolution_idx = [s['index'] for s in norm if s['role'] == 'resolution']
    if not climax_idx:
        add('no_climax', 'error', [], 'No shot is tagged climax.')
    else:
        early = [norm[i]['id'] for i in climax_idx if not setup_idx or i < setup_idx[0]]
        if early:
            add('climax_before_setup', 'error', early,
                'Climax appears before any opening/setup shot establishes the situation.')
        if len(climax_idx) > 1:
            add('multiple_climaxes', 'warning', [norm[i]['id'] for i in climax_idx],
                'More than one climax shot; confirm they form one continuous peak.')
        peak = max(s['intensity'] for s in norm)
        if max(norm[i]['intensity'] for i in climax_idx) < peak - 1e-9:
            add('climax_not_peak', 'warning', [s['id'] for s in norm if s['intensity'] >= peak - 1e-9],
                'A non-climax shot is more intense than the climax.')
        last_climax = climax_idx[-1]
        early_res = [norm[i]['id'] for i in resolution_idx if i < last_climax]
        if early_res:
            add('resolution_before_climax', 'error', early_res,
                'Resolution shot placed before the (last) climax.')
    if norm[-1]['role'] != 'resolution':
        add('ending_without_resolution', 'error', [norm[-1]['id']],
            'The sequence ends on a shot that is not tagged resolution.')
    if not setup_idx:
        add('no_setup', 'warning', [], 'No opening/setup shot.')
    regress = []
    max_rank = -1
    for s in norm:
        rank = _ROLE_RANK[s['role']]
        if rank < max_rank:
            regress.append(s['id'])
        max_rank = max(max_rank, rank)
    if regress:
        add('stage_regression', 'warning', regress,
            'Shot returns to an earlier story stage after a later one.')
    rising = [s for s in norm if s['role'] == 'rising']
    drops = [rising[k]['id'] for k in range(1, len(rising))
             if rising[k]['intensity'] < rising[k - 1]['intensity'] - 1e-9]
    if drops:
        add('rising_intensity_drops', 'warning', drops,
            'Intensity falls inside the rising stretch.')

    def key(s):
        rank = _ROLE_RANK[s['role']]
        if rank in (0, 1):
            return (rank, s['intensity'], s['index'])
        if rank in (3, 4):
            return (rank, -s['intensity'], s['index'])
        return (rank, 0.0, s['index'])

    suggested = sorted(norm, key=key)
    stages = {name: [] for name in ('opening', 'rising', 'climax', 'resolution')}
    for s in suggested:
        stages[_STAGE[_ROLE_RANK[s['role']]]].append(s['id'])
    errors = [p for p in problems if p['severity'] == 'error']
    return _pack('story_arc', {
        'valid': not errors,
        'problems': problems,
        'error_count': len(errors),
        'given_order': [s['id'] for s in norm],
        'intensity_curve': [_r(s['intensity'], 3) for s in norm],
        'suggested_order': [s['id'] for s in suggested],
        'suggested_intensity_curve': [_r(s['intensity'], 3) for s in suggested],
        'stages': stages,
        'total_duration': _r(sum(s['duration'] for s in norm if s['duration'])),
    }, ['Roles are declared by the editor; no footage is analysed.',
        'Arc model: opening/setup -> rising (intensity non-decreasing) -> climax (peak) -> falling -> resolution.',
        'Missing intensities default per role.'],
       ['Structural check only: it cannot judge whether the story is good or emotionally earned.',
        'Non-linear structures (cold opens, flashbacks) are flagged and need human sign-off.',
        f'At most {MAX_SHOTS} shots.'])


# --------------------------------------------------------------------------- 15.06 pacing_balance

_PRESETS = {
    'flat': lambda x: 1.0,
    'accelerate': lambda x: 1.6 - 1.2 * x,
    'decelerate': lambda x: 0.4 + 1.2 * x,
    'arc': lambda x: 0.5 + abs(2 * x - 1),
    'valley': lambda x: 1.5 - abs(2 * x - 1),
}


def _resample(weights, n):
    if n == 1:
        return [weights[0]]
    m = len(weights)
    out = []
    for i in range(n):
        pos = i * (m - 1) / (n - 1)
        lo = int(math.floor(pos))
        hi = min(lo + 1, m - 1)
        frac = pos - lo
        out.append(weights[lo] * (1 - frac) + weights[hi] * frac)
    return out


def _fit_total(values, lo, hi, total):
    vals = [min(max(v, lo), hi) for v in values]
    for _ in range(100):
        diff = total - sum(vals)
        if abs(diff) < 1e-9:
            break
        free = [i for i, v in enumerate(vals)
                if (diff > 0 and v < hi - 1e-12) or (diff < 0 and v > lo + 1e-12)]
        if not free:
            break
        share = diff / len(free)
        for i in free:
            vals[i] = min(max(vals[i] + share, lo), hi)
    return vals


def pacing_balance(*, edl=None, durations=None, target='flat', strength=0.6,
                   min_duration=0.5, max_duration=12.0, preserve_total=True, **extra):
    """Shot-length statistics and a bounded adjustment toward a target pacing curve.

    Give either edl=[{'start','end'}, ...] or durations=[seconds, ...].
    target: preset ('flat','accelerate','decelerate','arc','valley') or a list
    of >=2 positive relative weights (resampled to the shot count). Each new
    duration = old + strength*(target - old), clamped to [min, max]; the total
    runtime is kept when preserve_total and feasible.
    """
    _no_extra(extra)
    if (edl is None) == (durations is None):
        raise ValueError('give exactly one of edl or durations')
    starts = None
    if edl is not None:
        rows = _list(edl, 1, MAX_SHOTS, 'edl')
        starts, old = [], []
        for i, row in enumerate(rows):
            if not isinstance(row, dict) or set(row) != {'start', 'end'}:
                raise ValueError(f'edl[{i}] must contain only start and end')
            s = _num(row['start'], 0, 86400, f'edl[{i}].start')
            e = _num(row['end'], 0, 86400, f'edl[{i}].end')
            if e - s < 0.04:
                raise ValueError(f'edl[{i}] must be at least 0.04 s long')
            starts.append(s)
            old.append(e - s)
    else:
        old = [_num(d, 0.04, 3600, f'durations[{i}]')
               for i, d in enumerate(_list(durations, 1, MAX_SHOTS, 'durations'))]
    strength = _num(strength, 0, 1, 'strength')
    lo = _num(min_duration, 0.04, 3600, 'min_duration')
    hi = _num(max_duration, 0.04, 3600, 'max_duration')
    if hi <= lo:
        raise ValueError('max_duration must exceed min_duration')
    _bool(preserve_total, 'preserve_total')
    n = len(old)
    if isinstance(target, str):
        fn = _PRESETS.get(target)
        if fn is None:
            raise ValueError(f'target must be one of {sorted(_PRESETS)} or a list of weights')
        weights = [fn(i / (n - 1) if n > 1 else 0.5) for i in range(n)]
        target_name = target
    else:
        weights = _resample([_num(w, 1e-3, 1e3, f'target[{i}]')
                             for i, w in enumerate(_list(target, 2, 1000, 'target'))], n)
        target_name = 'custom'
    total = sum(old)
    warnings = []
    keep_total = preserve_total
    if keep_total and not n * lo - 1e-9 <= total <= n * hi + 1e-9:
        warnings.append('total runtime cannot fit within min/max bounds; total not preserved')
        keep_total = False
    wsum = sum(weights)
    tgt = [total * w / wsum for w in weights]
    tgt = _fit_total(tgt, lo, hi, total) if keep_total else [min(max(t, lo), hi) for t in tgt]
    new = [min(max(d + strength * (t - d), lo), hi) for d, t in zip(old, tgt)]
    if keep_total:
        new = _fit_total(new, lo, hi, total)

    def rms_dev(vals):
        return math.sqrt(sum((v - t) ** 2 for v, t in zip(vals, tgt)) / n)

    before, after, target_stats = _stats(old), _stats(new), _stats(tgt)
    result = {
        'target': target_name,
        'durations_before': [_r(d) for d in old],
        'durations_after': [_r(d) for d in new],
        'target_durations': [_r(t) for t in tgt],
        'stats_before': before, 'stats_after': after, 'stats_target': target_stats,
        'dispersion': {'cv_before': before['cv'], 'cv_after': after['cv'],
                       'cv_target': target_stats['cv'],
                       'rms_to_target_before': _r(rms_dev(old)),
                       'rms_to_target_after': _r(rms_dev(new))},
        'bounds': [lo, hi], 'total_preserved': keep_total, 'warnings': warnings,
    }
    if starts is not None:
        result['edl_after'] = [{'start': _r(s), 'end': _r(s + d)} for s, d in zip(starts, new)]
        result['needs_handles'] = [i for i, (a, b) in enumerate(zip(old, new)) if b > a + 1e-6]
    return _pack('pacing_balance', result,
                 ['Shot order is kept; only lengths change (ends are trimmed/extended).',
                  'Target curve expresses relative shot length; totals are distributed proportionally.',
                  'ASL = mean shot length; CV = std/mean is the dispersion measure.'],
                 ['Purely numeric: it does not know where actions, dialogue or beats fall inside a shot.',
                  'Extended shots (needs_handles) require source material beyond the current out-point.',
                  f'At most {MAX_SHOTS} shots.'])


# --------------------------------------------------------------------------- 15.07 safe_crossfade

_ID_ATTR = re.compile(r'(\bid\s*=\s*)(["\'])([^"\']+)\2')
_SAFE_ID = re.compile(r'^[A-Za-z_][\w.\-]*$')


def namespace_svg_ids(fragments, prefixes=None):
    """Prefix every id (and its url(#..)/href="#.." references) per fragment.

    Returns namespaced fragments plus collision reports before/after.
    """
    frags = _list(fragments, 1, 8, 'svg_titles')
    if prefixes is None:
        prefixes = [f'clip{i + 1}-' for i in range(len(frags))]
    out, id_maps, all_before, unresolved = [], [], [], []
    for i, frag in enumerate(frags):
        if not isinstance(frag, str) or not 0 < len(frag) <= MAX_SVG_CHARS:
            raise ValueError(f'svg_titles[{i}] must be a string of 1..{MAX_SVG_CHARS} chars')
        low = frag.lower()
        if '<script' in low or 'javascript:' in low or '<!entity' in low or '<!doctype' in low:
            raise ValueError(f'svg_titles[{i}] contains script, entity or doctype content')
        ids = [m.group(3) for m in _ID_ATTR.finditer(frag)]
        for v in ids:
            if not _SAFE_ID.match(v):
                raise ValueError(f'svg_titles[{i}] has an unsupported id value')
        all_before.extend((v, i) for v in ids)
        mapping = {v: prefixes[i] + v for v in ids}

        def repl_id(m, mapping=mapping):
            return m.group(1) + m.group(2) + mapping[m.group(3)] + m.group(2)

        text = _ID_ATTR.sub(repl_id, frag)

        def repl_url(m, mapping=mapping):
            return 'url(#' + mapping.get(m.group(1), m.group(1)) + ')'

        text = re.sub(r'url\(\s*#([A-Za-z_][\w.\-]*)\s*\)', repl_url, text)

        def repl_href(m, mapping=mapping):
            return m.group(1) + m.group(2) + '#' + mapping.get(m.group(3), m.group(3)) + m.group(2)

        text = re.sub(r'((?:xlink:)?href\s*=\s*)(["\'])#([A-Za-z_][\w.\-]*)\2', repl_href, text)
        refs = set(re.findall(r'url\(\s*#([A-Za-z_][\w.\-]*)\s*\)', frag)) | \
            {m[2] for m in re.findall(r'((?:xlink:)?href\s*=\s*)(["\'])#([A-Za-z_][\w.\-]*)\2', frag)}
        unresolved.extend({'fragment': i, 'ref': r} for r in sorted(refs - set(ids)))
        out.append(text)
        id_maps.append(mapping)

    def collisions(pairs):
        seen, dup = {}, set()
        for v, _ in pairs:
            if v in seen:
                dup.add(v)
            seen[v] = True
        return sorted(dup)

    after_pairs = [(m.group(3), i) for i, t in enumerate(out) for m in _ID_ATTR.finditer(t)]
    after = collisions(after_pairs)
    return {'fragments': out, 'id_maps': id_maps,
            'collisions_before': collisions(all_before), 'collisions_after': after,
            'unresolved_refs': unresolved, 'ok': not after}


_TRANSITIONS = {'fade', 'dissolve', 'wipeleft', 'wiperight', 'slideleft', 'slideright',
                'smoothleft', 'smoothright'}


def safe_crossfade(*, source=None, source_b=None, output=None, overlap=0.5,
                   transition='fade', fps=None, svg_titles=None, approve_write=False,
                   **extra):
    """Render clip A -> clip B with FFmpeg xfade + acrossfade into a new MP4 (AAC).

    Expected length = len(A) + len(B) - overlap (all quantised to whole frames).
    Optional svg_titles=[svg_a, svg_b, ...] are returned with per-clip
    namespaced ids so title layers cannot collide; SVGs are NOT burned in.
    """
    _no_extra(extra)
    a = _source(source)
    b = _source(source_b, 'source_b')
    overlap = _num(overlap, 0.04, 5.0, 'overlap')
    transition = _choice(transition, _TRANSITIONS, 'transition')
    _bool(approve_write, 'approve_write')
    if fps is None:
        fps = int(min(60, max(6, round(a['fps']))))
    fps = _int(fps, 6, 60, 'fps')
    svg = namespace_svg_ids(svg_titles) if svg_titles is not None else None
    if (a['width'], a['height']) != (b['width'], b['height']):
        raise ValueError('both clips must have the same width and height (no letterbox padding is added)')
    if a['width'] % 2 or a['height'] % 2:
        raise ValueError('yuv420p output requires even dimensions')
    target = _new_output(output, [a['source'], b['source']])
    na = int(round(_video_stream_duration(a) * fps))
    nb = int(round(_video_stream_duration(b) * fps))
    no = max(1, int(round(overlap * fps)))
    if no >= min(na, nb):
        raise ValueError('overlap must be shorter than both clips')
    da, db, do = na / fps, nb / fps, no / fps
    expected_frames = na + nb - no
    expected = expected_frames / fps
    first = _first_frame_luma(a['source'])
    if _is_black(first):
        raise ValueError('clip A starts on a black frame; trim it first (owner rule: no black start)')
    has_audio = a['audio'] or b['audio']
    plan = {'source': a['source'], 'source_b': b['source'], 'output': str(target),
            'transition': transition, 'fps': fps, 'overlap_requested': overlap,
            'overlap_used': _r(do), 'clip_a_seconds': _r(da), 'clip_b_seconds': _r(db),
            'expected_seconds': _r(expected), 'expected_frames': expected_frames,
            'audio': 'aac' if has_audio else None, 'svg_titles': svg}
    assumptions = ['Both clips share resolution; frame rate is unified with the fps filter.',
                   'Clip lengths come from the video stream and are rounded to whole frames.',
                   'A missing audio track is replaced by digital silence so the audio crossfade stays aligned.']
    limits = ['Only xfade transitions that keep picture on screen (no fadeblack/fadewhite).',
              'No grading, overlays, text or effects are added; SVG titles are only namespaced, not rendered.',
              'Refuses clips that start on black or differ in size; output must be a new .mp4.',
              'Video length verified to +-1 frame; container length may exceed it by one AAC frame.']
    if approve_write is not True:
        return _pack('safe_crossfade', {'status': 'approval_required', 'written': False,
                                        'plan': plan}, assumptions, limits)
    inputs = ['-i', a['source'], '-i', b['source']]
    graph = []
    for idx, n_dur in ((0, da), (1, db)):
        lab = 'va' if idx == 0 else 'vb'
        graph.append(f'[{idx}:v]settb=AVTB,setpts=PTS-STARTPTS,fps={fps},format=yuv420p,'
                     f'tpad=stop_mode=clone:stop_duration=1,trim=duration={n_dur:.6f},'
                     f'setpts=PTS-STARTPTS[{lab}]')
    graph.append(f'[va][vb]xfade=transition={transition}:duration={do:.6f}:'
                 f'offset={da - do:.6f},format=yuv420p[v]')
    if has_audio:
        next_input = 2
        for idx, meta, n_dur in ((0, a, da), (1, b, db)):
            lab = 'aa' if idx == 0 else 'ab'
            if meta['audio']:
                src = f'[{idx}:a]'
            else:
                inputs += ['-f', 'lavfi', '-t', f'{n_dur + 1:.3f}', '-i',
                           'anullsrc=r=48000:cl=stereo']
                src = f'[{next_input}:a]'
                next_input += 1
            graph.append(f'{src}aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,'
                         f'apad,atrim=duration={n_dur:.6f},asetpts=PTS-STARTPTS[{lab}]')
        graph.append(f'[aa][ab]acrossfade=d={do:.6f}:c1=tri:c2=tri[a]')
    with tempfile.NamedTemporaryFile(suffix='.mp4', prefix='.rose-xfade-', dir=target.parent,
                                     delete=False) as tmp:
        stage = Path(tmp.name)
    try:
        cmd = ['ffmpeg', '-hide_banner', '-nostdin', '-v', 'error', '-y', *inputs,
               '-filter_complex', ';'.join(graph), '-map', '[v]',
               '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20',
               '-pix_fmt', 'yuv420p', '-r', str(fps)]
        if has_audio:
            cmd += ['-map', '[a]', '-c:a', 'aac', '-b:a', '160k', '-ar', '48000']
        else:
            cmd += ['-an']
        cmd += ['-movflags', '+faststart', str(stage)]
        _tool(cmd, 300)
        qa = verify_video(stage, expected_fps=fps, width=a['width'], height=a['height'],
                          expected_audio=has_audio)
        if has_audio and qa['audio_codec'] != 'aac':
            raise ValueError('rendered audio is not AAC')
        frames = qa['frames']
        if frames is None or abs(frames - expected_frames) > 1:
            raise ValueError(f'rendered {frames} frames, expected {expected_frames} (+-1)')
        out_first = _first_frame_luma(stage)
        if _is_black(out_first):
            raise ValueError('rendered output starts with a black frame')
        created = False
        try:
            with target.open('xb') as dest:
                created = True
                with stage.open('rb') as src_file:
                    shutil.copyfileobj(src_file, dest, length=1024 * 1024)
        except BaseException:
            if created:
                target.unlink(missing_ok=True)
            raise
        video_seconds = frames / fps
        return _pack('safe_crossfade', {
            'status': 'rendered_and_verified', 'written': True, 'output': str(target),
            'plan': plan, 'frames': frames, 'video_seconds': _r(video_seconds),
            'container_seconds': _r(qa['duration']),
            'duration_error_frames': frames - expected_frames,
            'first_frame_luma': out_first, 'qa': qa,
            'method': 'FFmpeg xfade + acrossfade (tri), libx264 yuv420p, AAC 48 kHz'},
            assumptions, limits)
    finally:
        stage.unlink(missing_ok=True)


# --------------------------------------------------------------------------- 15.08 stabilize_estimate

def _sad(a, b, w, h, dx, dy, margin):
    total = 0
    count = 0
    sub = operator.sub
    for y in range(margin, h - margin):
        ra = y * w
        rb = (y + dy) * w + dx
        sa = a[ra + margin:ra + w - margin]
        sb = b[rb + margin:rb + w - margin]
        total += sum(map(abs, map(sub, sa, sb)))
        count += len(sa)
    return total / count


def _block_match(a, b, w, h, radius):
    costs = {}
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            costs[(dx, dy)] = _sad(a, b, w, h, dx, dy, radius)
    (bx, by), best = min(costs.items(), key=lambda kv: (kv[1], abs(kv[0][0]) + abs(kv[0][1])))

    def refine(c_m, c_0, c_p):
        den = c_m - 2 * c_0 + c_p
        return 0.0 if den <= 0 else max(-0.5, min(0.5, 0.5 * (c_m - c_p) / den))

    fx = refine(costs[(bx - 1, by)], best, costs[(bx + 1, by)]) if abs(bx) < radius else 0.0
    fy = refine(costs[(bx, by - 1)], best, costs[(bx, by + 1)]) if abs(by) < radius else 0.0
    return bx + fx, by + fy, best, abs(bx) == radius or abs(by) == radius


def _accel_rms(xs, ys):
    n = len(xs)
    if n < 3:
        return 0.0
    acc = [(xs[i + 1] - 2 * xs[i] + xs[i - 1]) ** 2 + (ys[i + 1] - 2 * ys[i] + ys[i - 1]) ** 2
           for i in range(1, n - 1)]
    return math.sqrt(sum(acc) / len(acc))


def stabilize_estimate(*, source=None, proxy_width=96, sample_fps=None, search_radius=8,
                       smoothing_seconds=0.5, max_seconds=20.0, **extra):
    """Estimate global camera shake and the crop needed to stabilise it (no render).

    Exhaustive block matching (mean absolute difference over the frame
    interior, +-search_radius proxy pixels, parabolic sub-pixel refinement)
    between consecutive grey proxy frames -> cumulative trajectory -> moving
    average -> correction = smoothed - raw. Jitter = RMS of the trajectory's
    second difference (px/frame^2, source pixels) before and after smoothing.
    """
    _no_extra(extra)
    meta = _source(source)
    pw = _int(proxy_width, 32, 192, 'proxy_width')
    if sample_fps is None:
        sample_fps = int(min(30, max(1, round(meta['fps']))))
    sample_fps = _int(sample_fps, 1, 60, 'sample_fps')
    radius = _int(search_radius, 1, 16, 'search_radius')
    smooth_s = _num(smoothing_seconds, 0, 5, 'smoothing_seconds')
    max_seconds = _num(max_seconds, 0.5, 120, 'max_seconds')
    pw, ph = _proxy_size(meta, pw)
    if ph <= 2 * radius + 4 or pw <= 2 * radius + 4:
        raise ValueError('proxy too small for the search radius')
    frames = _gray_frames(meta, pw, ph, sample_fps, max_seconds=max_seconds,
                          max_frames=MAX_PROXY_FRAMES)
    if len(frames) < 3:
        raise ValueError('need at least 3 proxy frames')
    scale_x, scale_y = meta['width'] / pw, meta['height'] / ph
    xs, ys = [0.0], [0.0]
    saturated = 0
    residual = []
    for i in range(1, len(frames)):
        dx, dy, cost, sat = _block_match(frames[i - 1], frames[i], pw, ph, radius)
        saturated += sat
        residual.append(cost)
        xs.append(xs[-1] + dx * scale_x)
        ys.append(ys[-1] + dy * scale_y)
    r = int(round(smooth_s * sample_fps))
    sx, sy = _smooth(xs, r), _smooth(ys, r)
    cx = [s - x for s, x in zip(sx, xs)]
    cy = [s - y for s, y in zip(sy, ys)]
    mx = math.ceil(max(abs(v) for v in cx))
    my = math.ceil(max(abs(v) for v in cy))
    crop_w = max(2, (meta['width'] - 2 * mx) // 2 * 2)
    crop_h = max(2, (meta['height'] - 2 * my) // 2 * 2)
    before = _accel_rms(xs, ys)
    after = _accel_rms(sx, sy)
    return _pack('stabilize_estimate', {
        'status': 'estimated_not_rendered', 'source': meta['source'],
        'method': 'exhaustive_block_matching+moving_average',
        'proxy': [pw, ph], 'sample_fps': sample_fps, 'frames': len(frames),
        'smoothing_radius_frames': r,
        'trajectory': [[_r(i / sample_fps), _r(x, 2), _r(y, 2)] for i, (x, y) in enumerate(zip(xs, ys))],
        'smoothed': [[_r(i / sample_fps), _r(x, 2), _r(y, 2)] for i, (x, y) in enumerate(zip(sx, sy))],
        'correction': [[_r(i / sample_fps), _r(x, 2), _r(y, 2)] for i, (x, y) in enumerate(zip(cx, cy))],
        'jitter_before': _r(before, 3), 'jitter_after': _r(after, 3),
        'jitter_reduction': _r(1 - after / before, 3) if before > 0 else 0.0,
        'crop_margin_px': [mx, my],
        'crop_margin_percent': [_r(100 * mx / meta['width'], 2), _r(100 * my / meta['height'], 2)],
        'suggested_crop': [crop_w, crop_h],
        'search_saturated_pairs': saturated,
        'mean_match_error': _r(sum(residual) / len(residual), 3),
    }, ['Global 2D translation only (no rotation, zoom or rolling shutter).',
        'Motion of the whole frame interior is treated as camera motion; large moving subjects bias it.',
        'Intended camera moves are the moving-average trajectory; the rest is shake.'],
       [f'Per-frame motion beyond +-search_radius proxy px is clipped (search_saturated_pairs counts these).',
        f'Analyses at most {MAX_PROXY_FRAMES} frames / max_seconds; precision ~0.25 proxy px.',
        'Estimate only: no stabilised render is produced by this module.',
        'Edges of the clip are smoothed with edge padding, so corrections there are less reliable.'])


# --------------------------------------------------------------------------- 15.09 colour_match

def _srgb_to_lin(c):
    c = c / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _lin_to_srgb(c):
    c = min(max(c, 0.0), 1.0)
    v = 12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055
    return min(max(v * 255.0, 0.0), 255.0)


_LIN = [_srgb_to_lin(i) for i in range(256)]
_WHITE = (0.95047, 1.0, 1.08883)


def _f(t):
    return t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116


def _finv(t):
    return t ** 3 if t > 0.206893 else (t - 16 / 116) / 7.787


def _rgb_to_lab(r, g, b):
    rl, gl, bl = _LIN[r], _LIN[g], _LIN[b]
    x = (0.4124564 * rl + 0.3575761 * gl + 0.1804375 * bl) / _WHITE[0]
    y = (0.2126729 * rl + 0.7151522 * gl + 0.0721750 * bl) / _WHITE[1]
    z = (0.0193339 * rl + 0.1191920 * gl + 0.9503041 * bl) / _WHITE[2]
    fx, fy, fz = _f(x), _f(y), _f(z)
    return (116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz))


def _lab_to_rgb(L, a, b):
    fy = (L + 16) / 116
    fx, fz = fy + a / 500, fy - b / 200
    x, y, z = _finv(fx) * _WHITE[0], _finv(fy) * _WHITE[1], _finv(fz) * _WHITE[2]
    rl = 3.2404542 * x - 1.5371385 * y - 0.4985314 * z
    gl = -0.9692660 * x + 1.8760108 * y + 0.0415560 * z
    bl = 0.0556434 * x - 0.2040259 * y + 1.0572252 * z
    return (_lin_to_srgb(rl), _lin_to_srgb(gl), _lin_to_srgb(bl))


def _lab_pixels(raw):
    return [_rgb_to_lab(raw[i], raw[i + 1], raw[i + 2]) for i in range(0, len(raw), 3)]


def _lab_stats(pixels):
    n = len(pixels)
    means = [sum(p[c] for p in pixels) / n for c in range(3)]
    stds = [math.sqrt(sum((p[c] - means[c]) ** 2 for p in pixels) / n) for c in range(3)]
    return means, stds


def _hue(a, b):
    return math.degrees(math.atan2(b, a)) % 360


def _hue_diff(h1, h2):
    d = (h2 - h1 + 180) % 360 - 180
    return d


def _is_skin(lab):
    L, a, b = lab
    c = math.hypot(a, b)
    return 20 <= L <= 95 and 8 <= c <= 60 and 15 <= _hue(a, b) <= 75


def colour_match(*, source=None, reference=None, target_time=None, reference_time=None,
                 strength=0.8, max_mean_shift=30.0, skin_protect=True,
                 skin_hue_limit_deg=4.0, proxy_width=64, **extra):
    """Reinhard-style mean/std transfer in CIELAB from a reference shot to a target shot.

    source = target shot, reference = look to match. One proxy frame each.
    Correction per channel: out = (x - mu_t) * k + mu_t + shift, where
    k = 1 + strength*(sigma_r/sigma_t - 1) (ratio clamped to 0.5..2) and the
    mean shift = strength*(mu_r - mu_t), its Lab length capped at
    max_mean_shift. Skin-like pixels (Lab hue 15..75 deg, chroma 8..60) keep
    their hue within skin_hue_limit_deg. Reports mean-colour Delta E76 before/after.
    """
    _no_extra(extra)
    tgt = _source(source)
    ref = _source(reference, 'reference')
    strength = _num(strength, 0, 1, 'strength')
    max_shift = _num(max_mean_shift, 0, 100, 'max_mean_shift')
    _bool(skin_protect, 'skin_protect')
    hue_limit = _num(skin_hue_limit_deg, 0, 45, 'skin_hue_limit_deg')
    pw = _int(proxy_width, 16, 160, 'proxy_width')
    tt = tgt['duration'] / 2 if target_time is None else \
        _num(target_time, 0, max(0.0, tgt['duration'] - 0.05), 'target_time')
    rt = ref['duration'] / 2 if reference_time is None else \
        _num(reference_time, 0, max(0.0, ref['duration'] - 0.05), 'reference_time')
    traw, _, _ = _rgb_frame(tgt, tt, pw)
    rraw, _, _ = _rgb_frame(ref, rt, pw)
    tpix, rpix = _lab_pixels(traw), _lab_pixels(rraw)
    mt, st = _lab_stats(tpix)
    mr, sr = _lab_stats(rpix)
    shift = [strength * (mr[c] - mt[c]) for c in range(3)]
    length = math.sqrt(sum(s * s for s in shift))
    capped = length > max_shift
    if capped and length > 0:
        shift = [s * max_shift / length for s in shift]
    gains = []
    for c in range(3):
        ratio = sr[c] / st[c] if st[c] > 1e-6 else 1.0
        ratio = min(2.0, max(0.5, ratio))
        gains.append(1 + strength * (ratio - 1))
    out = []
    skin_total = skin_reverted = 0
    max_skin_shift = 0.0
    for p in tpix:
        q = [(p[c] - mt[c]) * gains[c] + mt[c] + shift[c] for c in range(3)]
        skin = skin_protect and _is_skin(p)
        if skin:
            h0, h1 = _hue(p[1], p[2]), _hue(q[1], q[2])
            d = _hue_diff(h0, h1)
            if abs(d) > hue_limit:
                chroma = math.hypot(q[1], q[2])
                h = math.radians(h0 + math.copysign(hue_limit, d))
                q[1], q[2] = chroma * math.cos(h), chroma * math.sin(h)
        q = list(_rgb_to_lab(*(int(round(v)) for v in _lab_to_rgb(*q))))  # back into sRGB gamut
        if skin:
            skin_total += 1
            d = abs(_hue_diff(_hue(p[1], p[2]), _hue(q[1], q[2])))
            if d > hue_limit:
                q = list(p)
                skin_reverted += 1
                d = 0.0
            max_skin_shift = max(max_skin_shift, d)
        out.append(q)
    mo, so = _lab_stats(out)

    def de(m1, m2):
        return math.sqrt(sum((x - y) ** 2 for x, y in zip(m1, m2)))

    de_before, de_after = de(mt, mr), de(mo, mr)
    return _pack('colour_match', {
        'status': 'analyzed_not_applied', 'source': tgt['source'], 'reference': ref['source'],
        'frame_times': {'target': _r(tt), 'reference': _r(rt)},
        'delta_e76_mean_before': _r(de_before, 3), 'delta_e76_mean_after': _r(de_after, 3),
        'std_gap_before': [_r(abs(st[c] - sr[c]), 3) for c in range(3)],
        'std_gap_after': [_r(abs(so[c] - sr[c]), 3) for c in range(3)],
        'lab_mean_target': [_r(v, 3) for v in mt], 'lab_mean_reference': [_r(v, 3) for v in mr],
        'lab_mean_after': [_r(v, 3) for v in mo],
        'transform': {'space': 'CIELAB D65', 'mean_shift': [_r(v, 3) for v in shift],
                      'gain': [_r(v, 4) for v in gains], 'pivot': [_r(v, 3) for v in mt],
                      'shift_capped': capped},
        'skin': {'protected': skin_protect, 'pixels': skin_total,
                 'max_hue_shift_deg': _r(max_skin_shift, 3), 'limit_deg': hue_limit,
                 'reverted_pixels': skin_reverted},
        'applied_to_footage': False,
    }, ['One representative frame per shot stands for the whole shot.',
        'Global statistics transfer (Reinhard) in CIELAB; no spatial or semantic segmentation.',
        'Skin is approximated by a Lab hue/chroma window, not face detection.'],
       ['Analysis and proposed transform only: no filter is applied to footage by this module.',
        'Delta E is CIE76 on frame means, computed on a small proxy after sRGB gamut clipping.',
        'Large mean shifts are capped by max_mean_shift, so very different shots will not fully match.',
        'Non-skin objects inside the skin hue window are also protected.'])


# --------------------------------------------------------------------------- 15.10 vertical_reframe

_ASPECTS = {'9:16': (9, 16), '4:5': (4, 5), '1:1': (1, 1)}


def _box_list(value, duration):
    boxes = []
    for i, bx in enumerate(_list(value, 0, 16, 'protected_boxes')):
        if not isinstance(bx, dict) or not {'x', 'y', 'w', 'h'} <= set(bx) or \
                not set(bx) <= {'x', 'y', 'w', 'h', 't0', 't1', 'label'}:
            raise ValueError(f'protected_boxes[{i}] needs x,y,w,h (0..1) and optional t0,t1,label')
        x, y = _num(bx['x'], 0, 1, f'box{i}.x'), _num(bx['y'], 0, 1, f'box{i}.y')
        w, h = _num(bx['w'], 0.001, 1, f'box{i}.w'), _num(bx['h'], 0.001, 1, f'box{i}.h')
        if x + w > 1 + 1e-9 or y + h > 1 + 1e-9:
            raise ValueError(f'protected_boxes[{i}] extends outside the frame')
        t0 = _num(bx.get('t0', 0.0), 0, duration + 1, f'box{i}.t0')
        t1 = _num(bx.get('t1', duration + 1), 0, duration + 1, f'box{i}.t1')
        if t1 < t0:
            raise ValueError(f'protected_boxes[{i}] t1 must be >= t0')
        label = bx.get('label', f'box{i}')
        if not isinstance(label, str) or len(label) > 40:
            raise ValueError(f'protected_boxes[{i}].label must be a short string')
        boxes.append({'x': x, 'y': y, 'w': w, 'h': h, 't0': t0, 't1': t1, 'label': label})
    return boxes


def _place(desired, size, frame, ranges):
    """Pick an integer offset (even when possible) keeping every range inside."""
    lo_f, hi_f = 0, frame - size
    lo, hi = lo_f, hi_f
    for r0, r1 in ranges:
        lo = max(lo, math.ceil(r1 - size - 1e-9))
        hi = min(hi, math.floor(r0 + 1e-9))
    feasible = lo <= hi
    if not feasible:
        r0 = min(r[0] for r in ranges)
        r1 = max(r[1] for r in ranges)
        x = int(round(min(max((r0 + r1) / 2 - size / 2, lo_f), hi_f)))
        return x, False
    x = int(round(min(max(desired, lo), hi)))
    if x % 2:
        if x + 1 <= hi:
            x += 1
        elif x - 1 >= lo:
            x -= 1
    return x, True


def _bright_centroid(frame, w, h):
    hist = [0] * 256
    for v in frame:
        hist[v] += 1
    cut = len(frame) * 0.9
    acc, thr = 0, 255
    for v in range(256):
        acc += hist[v]
        if acc >= cut:
            thr = v
            break
    peak = max(frame)
    if peak <= thr:  # flat top decile: fall back to the brightest pixels themselves
        thr = peak - 1
    sx = sy = sw = 0.0
    for idx, v in enumerate(frame):
        if v > thr:
            wgt = v - thr
            sx += wgt * (idx % w + 0.5)
            sy += wgt * (idx // w + 0.5)
            sw += wgt
    if sw <= 0:
        return 0.5, 0.5
    return sx / sw / w, sy / sw / h


def vertical_reframe(*, source=None, aspect='9:16', poi=None, protected_boxes=None,
                     sample_fps=5, smoothing_seconds=0.6, proxy_width=96,
                     max_seconds=120.0, **extra):
    """Compute a smoothed vertical crop track that follows a point of interest.

    poi: optional [{'t': s, 'x': 0..1, 'y': 0..1}] keyframes (linear interp);
    otherwise the point of interest is the centroid of the brightest 10% of
    each grey proxy frame. Smoothing = moving average; then each sample is
    clamped so every active protected box (normalised x,y,w,h, optional t0,t1)
    stays fully inside the crop. Crop width/height are even integers.
    """
    _no_extra(extra)
    meta = _source(source)
    num, den = _ASPECTS[_choice(aspect, set(_ASPECTS), 'aspect')]
    fps = _int(sample_fps, 1, 30, 'sample_fps')
    smooth_s = _num(smoothing_seconds, 0, 5, 'smoothing_seconds')
    pw = _int(proxy_width, 32, 192, 'proxy_width')
    max_seconds = _num(max_seconds, 0.5, 600, 'max_seconds')
    boxes = _box_list([] if protected_boxes is None else protected_boxes, meta['duration'])
    W, H = meta['width'], meta['height']
    ch = H - H % 2
    cw = int(ch * num / den) // 2 * 2
    if cw > W:
        cw = W - W % 2
        ch = min(H - H % 2, int(cw * den / num) // 2 * 2)
    if cw < 2 or ch < 2:
        raise ValueError('source too small for this aspect')
    span = min(meta['duration'], max_seconds)
    n = max(1, min(MAX_PROXY_FRAMES, int(math.floor(span * fps + 1e-9))))
    times = [k / fps for k in range(n)]
    if poi is not None:
        keys = []
        for i, k in enumerate(_list(poi, 1, 2000, 'poi')):
            if not isinstance(k, dict) or set(k) != {'t', 'x', 'y'}:
                raise ValueError(f'poi[{i}] must contain only t, x, y')
            keys.append((_num(k['t'], 0, meta['duration'] + 1, f'poi[{i}].t'),
                         _num(k['x'], 0, 1, f'poi[{i}].x'), _num(k['y'], 0, 1, f'poi[{i}].y')))
        keys.sort()

        def interp(t):
            if t <= keys[0][0]:
                return keys[0][1], keys[0][2]
            for (t0, x0, y0), (t1, x1, y1) in zip(keys, keys[1:]):
                if t <= t1:
                    f = (t - t0) / (t1 - t0) if t1 > t0 else 1.0
                    return x0 + f * (x1 - x0), y0 + f * (y1 - y0)
            return keys[-1][1], keys[-1][2]

        points = [interp(t) for t in times]
        poi_method = 'supplied_keyframes'
    else:
        pw, ph = _proxy_size(meta, pw)
        frames = _gray_frames(meta, pw, ph, fps, max_seconds=span, max_frames=n)
        points = [_bright_centroid(f, pw, ph) for f in frames]
        times = times[:len(points)]
        poi_method = 'brightest_10_percent_centroid'
    if not points:
        raise ValueError('no frames to reframe')
    r = int(round(smooth_s * fps))
    px = _smooth([p[0] * W for p in points], r)
    py = _smooth([p[1] * H for p in points], r)
    track = []
    infeasible = []
    all_inside = True
    for t, cx, cy in zip(times, px, py):
        active = [b for b in boxes if b['t0'] <= t <= b['t1']]
        xr = [(b['x'] * W, (b['x'] + b['w']) * W) for b in active]
        yr = [(b['y'] * H, (b['y'] + b['h']) * H) for b in active]
        x, okx = _place(cx - cw / 2, cw, W, xr)
        y, oky = _place(cy - ch / 2, ch, H, yr)
        inside = all(x <= b['x'] * W + 1e-6 and x + cw >= (b['x'] + b['w']) * W - 1e-6 and
                     y <= b['y'] * H + 1e-6 and y + ch >= (b['y'] + b['h']) * H - 1e-6
                     for b in active)
        if not (okx and oky and inside):
            infeasible.append(_r(t))
            all_inside = False
        track.append({'t': _r(t), 'x': x, 'y': y, 'w': cw, 'h': ch,
                      'poi': [_r(cx, 1), _r(cy, 1)], 'protected_inside': inside})
    xs = [s['x'] for s in track]
    moves = [abs(xs[i + 1] - xs[i]) for i in range(len(xs) - 1)]
    return _pack('vertical_reframe', {
        'status': 'track_computed_not_rendered', 'source': meta['source'],
        'aspect': aspect, 'crop_size': [cw, ch], 'source_size': [W, H],
        'even_dimensions': cw % 2 == 0 and ch % 2 == 0,
        'poi_method': poi_method, 'sample_fps': fps, 'smoothing_radius_samples': r,
        'track': track, 'protected_boxes': boxes,
        'all_protected_inside': all_inside, 'infeasible_times': infeasible,
        'max_step_px': max(moves) if moves else 0,
    }, ['Crop keeps full height for landscape sources (or full width when the source is narrower).',
        'Point of interest = supplied keyframes or brightest-region centroid (a crude saliency proxy).',
        'Protected boxes are supplied by the caller in normalised source coordinates.'],
       ['No face, text or object detection; bright backgrounds can attract the crop.',
        'Protection is enforced after smoothing, so the crop can step abruptly when a box appears.',
        'A box wider/taller than the crop cannot be protected (reported in infeasible_times).',
        'Track only: no render is produced by this module.'])


# --------------------------------------------------------------------------- dispatcher

OPS = {
    'beat_sync_cuts': beat_sync_cuts,
    'story_arc': story_arc,
    'pacing_balance': pacing_balance,
    'safe_crossfade': safe_crossfade,
    'stabilize_estimate': stabilize_estimate,
    'colour_match': colour_match,
    'vertical_reframe': vertical_reframe,
}


def run(op, params=None):
    """Validate and dispatch: run('story_arc', {...}) -> {'op','result','assumptions','limits'}."""
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
