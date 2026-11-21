"""Red Rose V25: local audio measurement, conservative audio repair and audio paperwork.

Standard library + FFmpeg/FFprobe (local binaries) + the native Red Rose helpers
scene_edit_v16.probe_source, audio_scene_v17.detect_silences and
verify_media.verify_video. No network, no shell, no printing, no third-party
packages. Same interface as physics_v20: TOPICS, OPS, run(op, params) returning
{'op', 'result', 'assumptions', 'limits'}, strict ValueError validation and
rejection of unknown parameters. EFFECTS declares every op as 'read' or 'write'.

Inputs are local audio/video files only (wav, mp3, m4a, aac, flac, mp4, mov,
mkv); URLs and network (UNC) paths are rejected and inputs are never modified.
Write ops need approve_write=True and only ever create a NEW file inside an
existing folder: FFmpeg renders into a temporary file in that folder, the
result is checked, and it is then copied into the target with an exclusive
create (an existing file is never overwritten). Audio inside MP4/M4A is AAC.

Speech/lyrics text is never produced here: word_alignment only places words
from a trusted, caller-supplied transcript onto caller-supplied timings;
unclear or unmatched words stay empty.
"""
from __future__ import annotations

import array
import difflib
import hashlib
import json
import math
import operator
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata
from fractions import Fraction
from pathlib import Path

from scene_edit_v16 import probe_source
from audio_scene_v17 import detect_silences, _SILENCE_START, _SILENCE_END, _overlap
from verify_media import verify_video

MAX_PARAMS = 24
MAX_SECONDS = 600.0
MAX_SOURCE_BYTES = 2_000_000_000
MAX_DECODE_BYTES = 400_000_000
MAX_WORDS = 20_000
MAX_TRACKS = 200
AUDIO_INPUTS = {'.wav', '.mp3', '.m4a', '.aac', '.flac', '.mp4', '.mov', '.mkv'}
VIDEO_CONTAINERS = {'.mp4', '.mov', '.mkv'}
WRITE_OUTPUTS = {'.wav', '.flac', '.m4a', '.mp4'}
_URL = re.compile(r'^[A-Za-z][A-Za-z0-9+.\-]*:(//|[^\\/])')

TOPICS = {
    '16.01': 'loudness',
    '16.03': 'denoise',
    '16.04': 'word_alignment',
    '16.06': 'extract_pcm',
    '16.07': 'cut_crossfade',
    '16.08': 'av_sync',
    '16.09': 'pause_trim',
    '16.10': 'audio_rights',
}

TOPIC_NAMES_AR = {
    '16.01': 'قياس مستوى الصوت',
    '16.03': 'تقليل الضوضاء الساكنة',
    '16.04': 'محاذاة نص مع توقيت كلمات',
    '16.06': 'فصل الصوت عن الصورة',
    '16.07': 'التلاشي عند القص',
    '16.08': 'مزامنة الصوت مع الإطارات',
    '16.09': 'تنظيف فترات التوقف',
    '16.10': 'حقوق الصوت المستخدم',
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
    if not isinstance(value, (str, int)) or isinstance(value, bool) or value not in options:
        raise ValueError(f'{name} must be one of {sorted(options, key=str)}')
    return value


def _text(value, name, *, max_len=500, required=True):
    if value is None and not required:
        return ''
    if not isinstance(value, str) or len(value) > max_len:
        raise ValueError(f'{name} must be a string of at most {max_len} characters')
    value = value.strip()
    if required and not value:
        raise ValueError(f'{name} must not be empty')
    return value


def _path_like(value, name):
    if value is None or (isinstance(value, str) and not value.strip()):
        raise ValueError(f'{name} is required')
    if not isinstance(value, (str, os.PathLike)):
        raise ValueError(f'{name} must be a local file path')
    raw = os.fspath(value)
    if not isinstance(raw, str) or '\x00' in raw:
        raise ValueError(f'{name} must be a local file path')
    if _URL.match(raw.strip()) and not re.match(r'^[A-Za-z]:[\\/]', raw.strip()):
        raise ValueError(f'{name} must be a local file path; URLs are not accepted')
    if raw.startswith(('\\\\', '//')):
        raise ValueError(f'{name} must be a local file path; network paths are not accepted')
    return Path(raw).expanduser().resolve()


def _local_file(value, name='source', allowed=AUDIO_INPUTS, max_bytes=MAX_SOURCE_BYTES):
    path = _path_like(value, name)
    if not path.is_file():
        raise ValueError(f'{name} must be an existing local file')
    if path.suffix.lower() not in allowed:
        raise ValueError(f'{name} must have one of the extensions {sorted(allowed)}')
    if not 0 < path.stat().st_size <= max_bytes:
        raise ValueError(f'{name} must be a non-empty file of at most {max_bytes} bytes')
    return path


def _output_path(value, sources, allowed=WRITE_OUTPUTS):
    path = _path_like(value, 'output')
    if path.suffix.lower() not in allowed:
        raise ValueError(f'output must have one of the extensions {sorted(allowed)}')
    if not path.parent.is_dir():
        raise ValueError('output folder must already exist')
    if path.exists() or path.is_symlink():
        raise ValueError('output already exists; refusing to overwrite')
    if any(path == s for s in sources):
        raise ValueError('output must differ from every input')
    return path


def _approved(approve_write):
    if approve_write is not True:
        raise PermissionError('this op writes a new file: pass approve_write=True after the owner approves')


def _pack(op, result, assumptions, limits):
    return {'op': op, 'result': result, 'assumptions': list(assumptions),
            'limits': list(limits)}


def _r(value, nd=4):
    if value is None or not math.isfinite(value):
        return None
    return round(value, nd)


# --------------------------------------------------------------------------- ffmpeg helpers

def _tools():
    if not shutil.which('ffmpeg') or not shutil.which('ffprobe'):
        raise RuntimeError('FFmpeg and FFprobe must be installed and on PATH')


def _run(cmd, timeout, *, text=True):
    try:
        done = subprocess.run(cmd, capture_output=True, timeout=timeout, text=text,
                              **({'encoding': 'utf-8', 'errors': 'replace'} if text else {}))
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f'{cmd[0]} timed out after {timeout} s') from exc
    if done.returncode != 0:
        err = done.stderr if text else done.stderr.decode('utf-8', 'replace')
        raise RuntimeError(f'{cmd[0]} failed: ' + ' '.join(err.strip().splitlines()[-3:])[:600])
    return done


def _probe(path):
    """FFprobe facts for the first audio stream (+ video presence); bounded duration."""
    _tools()
    data = json.loads(_run(['ffprobe', '-v', 'error', '-show_entries',
                            'format=duration:stream=index,codec_type,codec_name,sample_rate,'
                            'channels,duration,start_time,avg_frame_rate',
                            '-of', 'json', str(path)], 30).stdout or '{}')
    streams = data.get('streams', [])
    audio = [s for s in streams if s.get('codec_type') == 'audio']
    video = [s for s in streams if s.get('codec_type') == 'video'
             and s.get('codec_name') not in ('mjpeg', 'png')]
    if not audio:
        raise ValueError('source has no audio stream')
    a = audio[0]

    def f(v):
        try:
            v = float(v)
        except (TypeError, ValueError):
            return None
        return v if math.isfinite(v) else None
    duration = f(data.get('format', {}).get('duration')) or f(a.get('duration'))
    if duration is None or not 0 < duration <= MAX_SECONDS:
        raise ValueError(f'media duration must be between 0 and {MAX_SECONDS:g} seconds')
    rate = int(a.get('sample_rate') or 0)
    channels = int(a.get('channels') or 0)
    if not 1000 <= rate <= 384000 or not 1 <= channels <= 16:
        raise ValueError('audio stream has an unsupported sample rate or channel count')
    fps = None
    if video:
        try:
            fps = float(Fraction(video[0].get('avg_frame_rate') or '0/1'))
        except (ValueError, ZeroDivisionError):
            fps = None
        if fps is not None and (not math.isfinite(fps) or fps <= 0):
            fps = None
    return {'path': str(path), 'duration': duration, 'audio_duration': f(a.get('duration')),
            'audio_start': f(a.get('start_time')) or 0.0, 'codec': a.get('codec_name'),
            'sample_rate': rate, 'channels': channels, 'has_video': bool(video), 'fps': fps,
            'bytes': path.stat().st_size}


def _pcm(path, *, rate, channels=1, start=None, duration=None, timeout=240):
    """Decode the first audio stream to interleaved float32 samples (array 'f')."""
    seconds = duration if duration is not None else MAX_SECONDS
    if seconds * rate * channels * 4 > MAX_DECODE_BYTES:
        raise ValueError('decode would exceed the in-memory analysis budget')
    cmd = ['ffmpeg', '-hide_banner', '-nostdin', '-v', 'error']
    if start is not None:
        cmd += ['-ss', f'{start:.6f}']
    cmd += ['-i', str(path)]
    if duration is not None:
        cmd += ['-t', f'{duration:.6f}']
    cmd += ['-map', '0:a:0', '-vn', '-ac', str(channels), '-ar', str(rate),
            '-f', 'f32le', '-acodec', 'pcm_f32le', '-']
    raw = _run(cmd, timeout, text=False).stdout
    samples = array.array('f')
    samples.frombytes(raw[:len(raw) - len(raw) % 4])
    if sys.byteorder == 'big':
        samples.byteswap()
    return samples


def _sumsq(seq):
    return sum(map(operator.mul, seq, seq))


def _db(rms):
    return 20 * math.log10(rms) if rms > 0 else None


_EBU_I = re.compile(r'\bI:\s*(-?inf|-?\d+(?:\.\d+)?)\s*LUFS')
_EBU_LRA = re.compile(r'\bLRA:\s*(-?inf|-?\d+(?:\.\d+)?)\s*LU\b')
_EBU_PEAK = re.compile(r'\bPeak:\s*(-?inf|-?\d+(?:\.\d+)?)\s*dBFS')


def _ebur128(path):
    """Integrated loudness, loudness range and true peak from FFmpeg ebur128's summary."""
    err = _run(['ffmpeg', '-hide_banner', '-nostdin', '-nostats', '-v', 'info', '-i', str(path),
                '-map', '0:a:0', '-vn', '-af', 'ebur128=peak=true', '-f', 'null', '-'], 300).stderr
    pos = err.rfind('Summary:')
    if pos < 0:
        raise RuntimeError('ebur128 summary not found in FFmpeg output')
    summary = err[pos:]

    def grab(rx):
        m = rx.search(summary)
        if not m:
            raise RuntimeError('could not parse ebur128 summary')
        return None if 'inf' in m.group(1) else float(m.group(1))
    return {'integrated_lufs': grab(_EBU_I), 'loudness_range_lu': grab(_EBU_LRA),
            'true_peak_dbtp': grab(_EBU_PEAK)}


def _segment_rms(path, info, segment_seconds):
    rate = min(info['sample_rate'], 48000)
    samples = _pcm(path, rate=rate, channels=1, duration=info['duration'] + 1)
    step = max(1, int(round(segment_seconds * rate)))
    segments = []
    for i in range(0, len(samples), step):
        seg = samples[i:i + step]
        if len(seg) < step * 0.25 and segments:
            break
        rms = math.sqrt(_sumsq(seg) / len(seg)) if len(seg) else 0.0
        segments.append({'start': _r(i / rate), 'end': _r(min(len(samples), i + step) / rate),
                         'rms_dbfs': _r(_db(rms), 2)})
    return segments, len(samples) / rate


def _variation(segments, silence_floor):
    vals = [s['rms_dbfs'] for s in segments
            if s['rms_dbfs'] is not None and s['rms_dbfs'] > silence_floor]
    if not vals:
        return {'segments_counted': 0, 'min_dbfs': None, 'max_dbfs': None, 'range_db': None,
                'mean_dbfs': None, 'stdev_db': None}
    mean = sum(vals) / len(vals)
    sd = math.sqrt(sum((v - mean) ** 2 for v in vals) / len(vals))
    return {'segments_counted': len(vals), 'min_dbfs': _r(min(vals), 2), 'max_dbfs': _r(max(vals), 2),
            'range_db': _r(max(vals) - min(vals), 2), 'mean_dbfs': _r(mean, 2), 'stdev_db': _r(sd, 2)}


def _measure(path, segment_seconds, silence_floor):
    info = _probe(path)
    ebu = _ebur128(path)
    segments, decoded = _segment_rms(path, info, segment_seconds)
    return info, ebu, segments, _variation(segments, silence_floor), decoded


def _codec_args(suffix, bit_depth=16):
    suffix = suffix.lower()
    if suffix == '.wav':
        return ['-c:a', {16: 'pcm_s16le', 24: 'pcm_s24le'}[bit_depth]]
    if suffix == '.flac':
        return ['-c:a', 'flac']
    return ['-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart']


def _render_new(output, build_cmd, check):
    """Render to a temp file beside output, check it, then exclusive-create output."""
    _tools()
    fd, tmp_name = tempfile.mkstemp(prefix='.audio_v25_', suffix=output.suffix, dir=output.parent)
    os.close(fd)
    tmp = Path(tmp_name)
    created = False
    try:
        _run(build_cmd(tmp), 600)
        facts = check(tmp)
        try:
            with output.open('xb') as dst, tmp.open('rb') as src:
                created = True
                shutil.copyfileobj(src, dst, 1024 * 1024)
        except FileExistsError as exc:
            raise ValueError('output appeared while rendering; refusing to overwrite') from exc
        return facts
    except BaseException:
        if created:
            try:
                output.unlink()
            except OSError:
                pass
        raise
    finally:
        try:
            tmp.unlink()
        except OSError:
            pass


def _check_codec(path, suffix):
    info = _probe(path)
    if suffix.lower() in ('.m4a', '.mp4') and info['codec'] != 'aac':
        raise RuntimeError('audio inside MP4/M4A must be AAC')
    return info


def _sha256(path):
    h = hashlib.sha256()
    with path.open('rb') as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


# --------------------------------------------------------------------------- 16.01 loudness

def loudness(*, source=None, segment_seconds=1.0, silence_floor_dbfs=-70.0, compare_to=None,
             **extra):
    """Measure integrated LUFS, loudness range and true peak (FFmpeg ebur128 summary)
    plus per-segment RMS (dBFS, mono downmix, from decoded PCM) and a variation
    report (spread of segment RMS). compare_to: a second local file (e.g. an
    approved loudness_normalise render) -> before/after deltas.
    """
    _no_extra(extra)
    src = _local_file(source)
    segment_seconds = _num(segment_seconds, 0.1, 60, 'segment_seconds')
    silence_floor_dbfs = _num(silence_floor_dbfs, -120, -20, 'silence_floor_dbfs')
    other = _local_file(compare_to, 'compare_to') if compare_to is not None else None
    info, ebu, segments, variation, decoded = _measure(src, segment_seconds, silence_floor_dbfs)
    if len(segments) > 6000:
        raise ValueError('too many segments; use a larger segment_seconds')
    result = {'source': {k: info[k] for k in ('path', 'duration', 'sample_rate', 'channels', 'codec')},
              **ebu, 'segment_seconds': segment_seconds, 'segments': segments,
              'variation': variation, 'decoded_seconds': _r(decoded)}
    if other is not None:
        o_info, o_ebu, o_segments, o_var, _ = _measure(other, segment_seconds, silence_floor_dbfs)

        def delta(a, b):
            return _r(b - a, 2) if a is not None and b is not None else None
        result['comparison'] = {
            'other': {k: o_info[k] for k in ('path', 'duration', 'sample_rate', 'channels', 'codec')},
            'other_integrated_lufs': o_ebu['integrated_lufs'],
            'other_true_peak_dbtp': o_ebu['true_peak_dbtp'],
            'other_variation': o_var,
            'delta_integrated_lu': delta(ebu['integrated_lufs'], o_ebu['integrated_lufs']),
            'delta_true_peak_db': delta(ebu['true_peak_dbtp'], o_ebu['true_peak_dbtp']),
            'delta_variation_range_db': delta(variation['range_db'], o_var['range_db']),
        }
    return _pack('loudness', result,
                 ['integrated loudness / LRA / true peak are FFmpeg ebur128 (EBU R128, BS.1770) summary values',
                  'segment RMS is computed on a mono downmix of decoded PCM (dBFS, full-scale sine = -3 dBFS); '
                  'it is not K-weighted and not gated',
                  'segments quieter than silence_floor_dbfs are excluded from the variation statistics',
                  'compare_to deltas are other minus source'],
                 [f'local files only, duration <= {MAX_SECONDS:g} s', 'segment_seconds in [0.1, 60]',
                  'ebur128 values are printed by FFmpeg with 0.1 dB resolution',
                  'silent input gives null LUFS / peak'])


def loudness_normalise(*, source=None, output=None, approve_write=False, target_lufs=-16.0,
                       true_peak_dbtp=-1.5, loudness_range_lu=11.0, segment_seconds=1.0,
                       **extra):
    """Two-pass FFmpeg loudnorm (linear when possible) into a NEW file, then re-measure.
    Reports before/after integrated loudness, true peak and segment-RMS variation.
    """
    _no_extra(extra)
    src = _local_file(source)
    out = _output_path(output, [src])
    target_lufs = _num(target_lufs, -40, -5, 'target_lufs')
    true_peak_dbtp = _num(true_peak_dbtp, -9, 0, 'true_peak_dbtp')
    loudness_range_lu = _num(loudness_range_lu, 1, 20, 'loudness_range_lu')
    segment_seconds = _num(segment_seconds, 0.1, 60, 'segment_seconds')
    _approved(approve_write)
    info, ebu, _segs, var_before, _ = _measure(src, segment_seconds, -70.0)
    base = f'loudnorm=I={target_lufs}:TP={true_peak_dbtp}:LRA={loudness_range_lu}'
    err = _run(['ffmpeg', '-hide_banner', '-nostdin', '-nostats', '-v', 'info', '-i', str(src),
                '-map', '0:a:0', '-vn', '-af', base + ':print_format=json', '-f', 'null', '-'], 300).stderr
    start, end = err.rfind('{'), err.rfind('}')
    if start < 0 or end < start:
        raise RuntimeError('loudnorm measurement not found')
    m = json.loads(err[start:end + 1])
    keys = ('input_i', 'input_tp', 'input_lra', 'input_thresh', 'target_offset')
    if any('inf' in str(m.get(k, 'inf')) for k in keys):
        raise ValueError('source is silent or too short to normalise')
    filt = (f"{base}:measured_I={m['input_i']}:measured_TP={m['input_tp']}:"
            f"measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:"
            f"offset={m['target_offset']}:linear=true")

    def build(tmp):
        return (['ffmpeg', '-hide_banner', '-nostdin', '-v', 'error', '-y', '-i', str(src),
                 '-map', '0:a:0', '-vn', '-af', filt, '-ar', str(info['sample_rate'])]
                + _codec_args(out.suffix) + [str(tmp)])
    facts = _render_new(out, build, lambda p: _check_codec(p, out.suffix))
    o_info, o_ebu, _o_segs, var_after, _ = _measure(out, segment_seconds, -70.0)
    result = {'output': str(out), 'codec': facts['codec'], 'sample_rate': facts['sample_rate'],
              'channels': facts['channels'],
              'before': {**ebu, 'variation': var_before}, 'after': {**o_ebu, 'variation': var_after},
              'target': {'integrated_lufs': target_lufs, 'true_peak_dbtp': true_peak_dbtp,
                         'loudness_range_lu': loudness_range_lu},
              'output_sha256': _sha256(out)}
    return _pack('loudness_normalise', result,
                 ['FFmpeg loudnorm two-pass; linear gain is used when the measured input allows it, '
                  'otherwise loudnorm falls back to dynamic mode (which changes dynamics)',
                  'first audio stream only; video is not copied'],
                 ['writes only a NEW .wav/.flac/.m4a/.mp4 file in an existing folder (approve_write=True)',
                  'audio in .m4a/.mp4 is AAC 192 kb/s (lossy)', f'duration <= {MAX_SECONDS:g} s'])


# --------------------------------------------------------------------------- 16.03 denoise

def _snr(signal, reference):
    n = min(len(signal), len(reference))
    if n == 0:
        return None
    sig = _sumsq(reference[:n])
    diff = array.array('f', map(operator.sub, signal[:n], reference[:n]))
    err = _sumsq(diff)
    if sig <= 0:
        return None
    return 10 * math.log10(sig / err) if err > 0 else None


def denoise(*, source=None, output=None, approve_write=False, strength_db=12.0,
            noise_floor_db=None, noise_region=None, reference=None, **extra):
    """Conservative stationary-noise reduction with FFmpeg afftdn into a NEW file.

    strength_db (afftdn noise_reduction) is bounded to [1, 30] dB. The noise
    floor comes from noise_floor_db, else from the RMS of noise_region
    [start, end] (seconds, noise only), else from the 5th percentile of 50 ms
    frame RMS (the quietest part of the file). With a clean `reference` file
    (synthetic tests) SNR before/after is measured sample-by-sample.
    """
    _no_extra(extra)
    src = _local_file(source)
    out = _output_path(output, [src])
    strength_db = _num(strength_db, 1, 30, 'strength_db')
    if noise_floor_db is not None:
        noise_floor_db = _num(noise_floor_db, -80, -20, 'noise_floor_db')
    if noise_region is not None:
        if not isinstance(noise_region, (list, tuple)) or len(noise_region) != 2:
            raise ValueError('noise_region must be [start, end] in seconds')
        a = _num(noise_region[0], 0, MAX_SECONDS, 'noise_region[0]')
        b = _num(noise_region[1], 0, MAX_SECONDS, 'noise_region[1]')
        if b - a < 0.05:
            raise ValueError('noise_region must be at least 0.05 s long')
        noise_region = [a, b]
    ref = _local_file(reference, 'reference') if reference is not None else None
    _approved(approve_write)
    info = _probe(src)
    rate = min(info['sample_rate'], 48000)
    noisy = _pcm(src, rate=rate, channels=1, duration=info['duration'] + 1)
    if noise_floor_db is not None:
        floor, floor_from = noise_floor_db, 'noise_floor_db'
    elif noise_region is not None:
        seg = noisy[int(noise_region[0] * rate):int(noise_region[1] * rate)]
        if len(seg) < int(0.05 * rate):
            raise ValueError('noise_region lies outside the decoded audio')
        floor, floor_from = _db(math.sqrt(_sumsq(seg) / len(seg))), 'noise_region'
    else:
        hop = max(1, int(0.05 * rate))
        frames = sorted(math.sqrt(_sumsq(noisy[i:i + hop]) / hop)
                        for i in range(0, len(noisy) - hop + 1, hop))
        if not frames:
            raise ValueError('source too short to estimate a noise floor')
        floor, floor_from = _db(frames[int(0.05 * (len(frames) - 1))]), 'quietest_5_percent_frames'
    if floor is None:
        floor = -80.0
    clamped = min(-20.0, max(-80.0, floor))
    # tn (noise tracking) stays off: measured on synthetic tone+noise it let the
    # floor drift up under the signal and lowered SNR; a fixed floor is more conservative.
    filt = f'afftdn=nr={strength_db:g}:nf={clamped:.2f}:tn=0'

    def build(tmp):
        return (['ffmpeg', '-hide_banner', '-nostdin', '-v', 'error', '-y', '-i', str(src),
                 '-map', '0:a:0', '-vn', '-af', filt, '-ar', str(info['sample_rate'])]
                + _codec_args(out.suffix) + [str(tmp)])
    facts = _render_new(out, build, lambda p: _check_codec(p, out.suffix))
    result = {'output': str(out), 'codec': facts['codec'], 'filter': filt,
              'noise_floor_db': _r(floor, 2), 'noise_floor_used_db': _r(clamped, 2),
              'noise_floor_source': floor_from, 'noise_floor_clamped': clamped != floor,
              'strength_db': strength_db, 'snr': None, 'output_sha256': _sha256(out)}
    if ref is not None:
        clean = _pcm(ref, rate=rate, channels=1, duration=info['duration'] + 1)
        cleaned = _pcm(out, rate=rate, channels=1, duration=info['duration'] + 1)
        before, after = _snr(noisy, clean), _snr(cleaned, clean)
        result['snr'] = {'reference': str(ref), 'before_db': _r(before, 2), 'after_db': _r(after, 2),
                         'improvement_db': _r(after - before, 2)
                         if before is not None and after is not None else None}
    return _pack('denoise', result,
                 ['noise is stationary (hiss-like); afftdn runs with a fixed noise floor (no tracking) and '
                  'does not remove transient noises (clicks, voices, music)',
                  'the noise floor estimate assumes the quietest 5 % of 50 ms frames are noise only, '
                  'unless noise_floor_db or noise_region is given',
                  'SNR is sample-aligned against the supplied clean reference (mono downmix, no lag search)'],
                 ['strength_db in [1, 30] dB (FFmpeg allows up to 97; capped for conservative repair)',
                  'noise floor clamped to afftdn range [-80, -20] dB',
                  'writes only a NEW file (approve_write=True); AAC in .m4a/.mp4',
                  'SNR needs a clean reference, so it is only meaningful for synthetic/test material'])


# --------------------------------------------------------------------------- 16.04 word_alignment

_DIACRITICS = re.compile('[ؐ-ًؚ-ٰٟۖ-ۭـ]')
_UNCLEAR = {'', '?', '??', '...', '…', '[unclear]', '(unclear)', '[inaudible]', '<unk>', '؟'}


def _norm(word):
    w = unicodedata.normalize('NFKC', word).casefold()
    w = _DIACRITICS.sub('', w)
    w = w.translate(str.maketrans({'أ': 'ا', 'إ': 'ا', 'آ': 'ا', 'ى': 'ي'}))
    return ''.join(ch for ch in w if ch.isalnum())


def _timing_list(value, name):
    if not isinstance(value, (list, tuple)) or len(value) > MAX_WORDS:
        raise ValueError(f'{name} must be a list of at most {MAX_WORDS} entries')
    out = []
    for i, item in enumerate(value):
        if not isinstance(item, dict):
            raise ValueError(f'{name}[{i}] must be an object with word/start/end')
        word = item.get('word', item.get('text'))
        if word is not None and not isinstance(word, str):
            raise ValueError(f'{name}[{i}].word must be a string')
        start, end = item.get('start'), item.get('end')
        if start is None or end is None:
            start = end = None
        else:
            start = _num(start, 0, 86400, f'{name}[{i}].start')
            end = _num(end, 0, 86400, f'{name}[{i}].end')
            if end < start:
                raise ValueError(f'{name}[{i}]: end must be >= start')
        out.append({'word': (word or '').strip(), 'start': start, 'end': end})
    return out


def _load_timings_file(value):
    path = _local_file(value, 'timings_file', {'.json'}, 20_000_000)
    data = json.loads(path.read_text(encoding='utf-8-sig'))
    if isinstance(data, dict) and isinstance(data.get('segments'), list):
        words = []
        for seg in data['segments']:
            if isinstance(seg, dict) and isinstance(seg.get('words'), list):
                words.extend(seg['words'])
        return words, str(path)
    if isinstance(data, dict) and isinstance(data.get('words'), list):
        return data['words'], str(path)
    if isinstance(data, list):
        return data, str(path)
    raise ValueError('timings_file must hold a word list, {"words": [...]} or {"segments": [{"words": [...]}]}')


def _stats(values):
    if not values:
        return {'count': 0, 'mean_signed': None, 'mean_abs': None, 'median_abs': None,
                'max_abs': None, 'rms': None}
    absv = sorted(abs(v) for v in values)
    n = len(values)
    med = absv[n // 2] if n % 2 else 0.5 * (absv[n // 2 - 1] + absv[n // 2])
    return {'count': n, 'mean_signed': _r(sum(values) / n, 6), 'mean_abs': _r(sum(absv) / n, 6),
            'median_abs': _r(med, 6), 'max_abs': _r(absv[-1], 6),
            'rms': _r(math.sqrt(sum(v * v for v in values) / n), 6)}


def word_alignment(*, words=None, timings=None, timings_file=None, reference=None,
                   tolerance=0.1, **extra):
    """Place a trusted transcript's words onto supplied word timings and measure deviation.

    words: the trusted transcript as a list of strings (None / '' / '?' /
    '[unclear]' mark an unclear word). timings (or timings_file, e.g. an
    external aligner's JSON): [{'word', 'start', 'end'}, ...]. Words are matched
    in order after normalisation (case, punctuation, Arabic diacritics and alef
    forms); only exact normalised matches receive times. Unclear or unmatched
    words keep empty times; words are never taken from the timings source.
    reference: optional list (same length as words) of {'start','end'} or None.
    """
    _no_extra(extra)
    if words is None or (timings is None and timings_file is None):
        raise ValueError('words and timings (or timings_file) are required')
    if timings is not None and timings_file is not None:
        raise ValueError('give timings or timings_file, not both')
    if not isinstance(words, (list, tuple)) or not 1 <= len(words) <= MAX_WORDS:
        raise ValueError(f'words must be a list of 1..{MAX_WORDS} strings')
    for i, w in enumerate(words):
        if w is not None and (not isinstance(w, str) or len(w) > 200):
            raise ValueError(f'words[{i}] must be a string (<= 200 chars) or null')
    tolerance = _num(tolerance, 0, 10, 'tolerance')
    timing_source = 'timings'
    if timings_file is not None:
        timings, timing_source = _load_timings_file(timings_file)
    times = _timing_list(timings, 'timings')
    if reference is not None:
        if not isinstance(reference, (list, tuple)) or len(reference) != len(words):
            raise ValueError('reference must be a list with one entry (or null) per transcript word')
        refs = []
        for i, item in enumerate(reference):
            if item is None:
                refs.append(None)
                continue
            if not isinstance(item, dict):
                raise ValueError(f'reference[{i}] must be {{start, end}} or null')
            s = _num(item.get('start'), 0, 86400, f'reference[{i}].start')
            e = _num(item.get('end'), 0, 86400, f'reference[{i}].end')
            if e < s:
                raise ValueError(f'reference[{i}]: end must be >= start')
            refs.append({'start': s, 'end': e})
    else:
        refs = None

    unclear_idx = [i for i, w in enumerate(words)
                   if w is None or w.strip() in _UNCLEAR or not _norm(w)]
    unclear_set = set(unclear_idx)
    t_usable = [j for j, t in enumerate(times) if t['start'] is not None and _norm(t['word'])]
    a_keys = [(i, _norm(words[i])) for i in range(len(words)) if i not in unclear_set]
    b_keys = [(j, _norm(times[j]['word'])) for j in t_usable]
    matcher = difflib.SequenceMatcher(None, [k for _, k in a_keys], [k for _, k in b_keys],
                                      autojunk=False)
    assigned = {}
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == 'equal':
            for di in range(i2 - i1):
                assigned[a_keys[i1 + di][0]] = b_keys[j1 + di][0]
    used = set(assigned.values())
    aligned, missing = [], []
    for i, w in enumerate(words):
        text = '' if i in unclear_set else w.strip()
        j = assigned.get(i)
        if j is None:
            aligned.append({'index': i, 'word': text, 'start': None, 'end': None,
                            'status': 'unclear' if i in unclear_set else 'missing'})
            if i not in unclear_set:
                missing.append({'index': i, 'word': text})
        else:
            aligned.append({'index': i, 'word': text, 'start': times[j]['start'],
                            'end': times[j]['end'], 'status': 'aligned', 'timing_index': j})
    extra_words = [{'timing_index': j, 'word': times[j]['word']}
                   for j in range(len(times)) if j not in used]
    deviation = None
    if refs is not None:
        ds, de, per = [], [], []
        for a, ref in zip(aligned, refs):
            if ref is None or a['start'] is None:
                continue
            s, e = a['start'] - ref['start'], a['end'] - ref['end']
            ds.append(s)
            de.append(e)
            per.append({'index': a['index'], 'start_dev': _r(s, 6), 'end_dev': _r(e, 6)})
        within = sum(1 for s, e in zip(ds, de) if abs(s) <= tolerance and abs(e) <= tolerance)
        deviation = {'start': _stats(ds), 'end': _stats(de), 'per_word': per,
                     'tolerance': tolerance,
                     'within_tolerance_ratio': _r(within / len(ds), 4) if ds else None,
                     'words_without_reference_or_timing':
                         [a['index'] for a, r in zip(aligned, refs) if r is None or a['start'] is None]}
    result = {'timing_source': timing_source, 'words': aligned,
              'aligned_count': len(assigned), 'word_count': len(words),
              'unclear': unclear_idx, 'missing': missing,
              'timings_not_in_transcript': extra_words, 'deviation': deviation}
    return _pack('word_alignment', result,
                 ['the transcript is the trusted text; timings only supply start/end times',
                  'matching is in order, on normalised tokens (case, punctuation, Arabic diacritics/alef forms); '
                  'a timing word must equal the transcript word to be used',
                  'unclear and unmatched words stay empty (null times) and are listed; nothing is invented',
                  'deviation = aligned time - reference time, in seconds'],
                 [f'at most {MAX_WORDS} words / timings', 'timings_file: local .json up to 20 MB',
                  'no acoustic alignment is performed here; accuracy is that of the supplied timings'])


# --------------------------------------------------------------------------- 16.06 extract_pcm

def extract_pcm(*, source=None, output=None, approve_write=False, bit_depth=16, **extra):
    """Extract the first audio stream to a NEW WAV keeping channel count and sample rate;
    verify duration (within one video frame, or 40 ms for audio-only sources),
    channels and sample rate with FFprobe.
    """
    _no_extra(extra)
    src = _local_file(source)
    out = _output_path(output, [src], {'.wav'})
    bit_depth = _choice(bit_depth, {16, 24}, 'bit_depth')
    _approved(approve_write)
    info = _probe(src)
    frame = 1.0 / info['fps'] if info['fps'] else 0.04
    src_dur = info['audio_duration'] or info['duration']

    def build(tmp):
        return ['ffmpeg', '-hide_banner', '-nostdin', '-v', 'error', '-y', '-i', str(src),
                '-map', '0:a:0', '-vn', '-ac', str(info['channels']), '-ar', str(info['sample_rate']),
                '-c:a', f'pcm_s{bit_depth}le', str(tmp)]

    def check(tmp):
        o = _probe(tmp)
        dur = o['audio_duration'] or o['duration']
        problems = []
        if o['channels'] != info['channels']:
            problems.append('channel count changed')
        if o['sample_rate'] != info['sample_rate']:
            problems.append('sample rate changed')
        if abs(dur - src_dur) > frame:
            problems.append(f'duration differs by {abs(dur - src_dur):.4f} s (> one frame {frame:.4f} s)')
        if problems:
            raise RuntimeError('extracted WAV failed verification: ' + '; '.join(problems))
        return o
    o = _render_new(out, build, check)
    o_dur = o['audio_duration'] or o['duration']
    result = {'output': str(out), 'codec': o['codec'], 'channels': o['channels'],
              'sample_rate': o['sample_rate'], 'source_channels': info['channels'],
              'source_sample_rate': info['sample_rate'], 'source_audio_duration': _r(src_dur, 6),
              'output_duration': _r(o_dur, 6), 'duration_difference': _r(o_dur - src_dur, 6),
              'frame_tolerance': _r(frame, 6), 'source_has_video': info['has_video'],
              'output_sha256': _sha256(out)}
    return _pack('extract_pcm', result,
                 ['first audio stream only; lossy sources (AAC/MP3) are decoded, not restored',
                  'sample rate and channel count are kept; samples are written as PCM s16/s24'],
                 ['writes only a NEW .wav in an existing folder (approve_write=True)',
                  'duration tolerance = one video frame (or 40 ms without video)',
                  'WAV with > 4 GB data is not supported (duration <= 600 s keeps far below)'])


# --------------------------------------------------------------------------- 16.07 cut_crossfade

def _max_jump(samples, channels, lo, hi):
    """Largest |x[n] - x[n-1]| (any channel) for frame indices n in [lo, hi)."""
    best, at = 0.0, None
    frames = len(samples) // channels
    lo, hi = max(1, lo), min(frames, hi)
    for c in range(channels):
        for n in range(lo, hi):
            d = abs(samples[n * channels + c] - samples[(n - 1) * channels + c])
            if d > best:
                best, at = d, n
    return best, at


def cut_crossfade(*, source=None, next_source=None, output=None, approve_write=False,
                  crossfade_ms=20.0, **extra):
    """Join two audio segments (source then next_source) with an equal-power
    (quarter-sine) crossfade into a NEW file, and compare the sample jump at the
    joint against a hard cut computed in memory (click detector).
    """
    _no_extra(extra)
    a_path = _local_file(source)
    b_path = _local_file(next_source, 'next_source')
    out = _output_path(output, [a_path, b_path])
    crossfade_ms = _num(crossfade_ms, 2, 500, 'crossfade_ms')
    _approved(approve_write)
    a_info, b_info = _probe(a_path), _probe(b_path)
    for name, inf in (('source', a_info), ('next_source', b_info)):
        if inf['duration'] > 120:
            raise ValueError(f'{name} must be at most 120 s for cut_crossfade')
    rate, ch = a_info['sample_rate'], min(a_info['channels'], 2)
    if b_info['channels'] > 2 or a_info['channels'] > 2:
        raise ValueError('cut_crossfade supports mono or stereo segments only')
    layout = 'mono' if ch == 1 else 'stereo'
    a = _pcm(a_path, rate=rate, channels=ch, duration=a_info['duration'] + 1)
    b = _pcm(b_path, rate=rate, channels=ch, duration=b_info['duration'] + 1)
    la, lb = len(a) // ch, len(b) // ch
    xf = int(round(crossfade_ms / 1000 * rate))
    if xf * 2 > min(la, lb):
        raise ValueError('crossfade must be shorter than half of each segment')
    w = max(2, int(0.005 * rate))
    hard = a + b
    hard_jump, hard_at = _max_jump(hard, ch, la - w, la + w + 1)
    base_a, _ = _max_jump(a, ch, max(1, la - w - rate), la - w)
    base_b, _ = _max_jump(b, ch, w, min(lb, w + rate))
    baseline = max(base_a, base_b)
    fmt = f'aformat=sample_fmts=fltp:sample_rates={rate}:channel_layouts={layout}'
    graph = (f'[0:a:0]{fmt}[a0];[1:a:0]aresample={rate},{fmt}[a1];'
             f'[a0][a1]acrossfade=d={xf / rate:.6f}:c1=qsin:c2=qsin[out]')

    def build(tmp):
        return (['ffmpeg', '-hide_banner', '-nostdin', '-v', 'error', '-y', '-i', str(a_path),
                 '-i', str(b_path), '-filter_complex', graph, '-map', '[out]', '-ar', str(rate)]
                + _codec_args(out.suffix) + [str(tmp)])

    measured = {}

    def check(tmp):
        info = _check_codec(tmp, out.suffix)
        joined = _pcm(tmp, rate=rate, channels=ch, duration=info['duration'] + 1)
        measured['frames'] = len(joined) // ch
        measured['jump'], measured['at'] = _max_jump(joined, ch, la - xf - w, la + w + 1)
        return info
    info = _render_new(out, build, check)
    expected = la + lb - xf
    xf_jump = measured['jump']
    result = {
        'output': str(out), 'codec': info['codec'], 'sample_rate': rate, 'channels': ch,
        'crossfade_samples': xf, 'crossfade_seconds': _r(xf / rate, 6), 'curve': 'equal-power (qsin)',
        'source_frames': la, 'next_source_frames': lb, 'output_frames': measured['frames'],
        'expected_output_frames': expected,
        'clicks': {
            'hard_cut_joint_max_jump': _r(hard_jump, 6), 'hard_cut_joint_at_frame': hard_at,
            'crossfade_joint_max_jump': _r(xf_jump, 6),
            'signal_baseline_max_jump': _r(baseline, 6),
            'hard_cut_ratio_to_baseline': _r(hard_jump / baseline, 3) if baseline > 0 else None,
            'crossfade_ratio_to_baseline': _r(xf_jump / baseline, 3) if baseline > 0 else None,
            'improvement_ratio': _r(hard_jump / xf_jump, 3) if xf_jump > 0 else None,
            'hard_cut_click_suspected': baseline > 0 and hard_jump > 3 * baseline,
            'crossfade_click_suspected': baseline > 0 and xf_jump > 3 * baseline,
        },
        'output_sha256': _sha256(out)}
    return _pack('cut_crossfade', result,
                 ['segments are joined end-to-start; the crossfade overlaps the last crossfade_ms of source '
                  'with the first crossfade_ms of next_source (output is shorter by that overlap)',
                  'equal-power quarter-sine gains (sin^2 + cos^2 = 1): constant power for uncorrelated material',
                  'click detector = largest sample-to-sample jump near the joint vs the largest jump elsewhere; '
                  'the hard cut is simulated in memory, never written; the baseline uses the last 1 s of '
                  'source and the first 1 s of next_source (outside the joint window)',
                  'next_source is resampled to the first segment\'s sample rate and channel layout'],
                 ['each segment <= 120 s, mono or stereo', 'crossfade_ms in [2, 500] and < half of each segment',
                  'writes only a NEW file (approve_write=True); AAC in .m4a/.mp4 (encoder priming may '
                  'shift the measured joint slightly)'])


# --------------------------------------------------------------------------- 16.08 av_sync

def av_sync(*, source=None, checkpoint_seconds=1.0, onset_threshold_dbfs=-40.0,
            decode_check=False, **extra):
    """Read packet PTS of the first video and audio streams (FFprobe) and report the
    start offset (audio first PTS - video first PTS), the audio content onset
    (first 5 ms frame above onset_threshold_dbfs, on the video timeline), the
    timestamp drift of each stream versus its own packet-duration clock, and the
    end/duration mismatch between streams.
    """
    _no_extra(extra)
    path = _local_file(source, allowed=VIDEO_CONTAINERS)
    checkpoint_seconds = _num(checkpoint_seconds, 0.1, 60, 'checkpoint_seconds')
    onset_threshold_dbfs = _num(onset_threshold_dbfs, -90, -10, 'onset_threshold_dbfs')
    if not isinstance(decode_check, bool):
        raise ValueError('decode_check must be true or false')
    meta = probe_source(path)
    if not meta['audio']:
        raise ValueError('source has no audio stream')
    streams = json.loads(_run(['ffprobe', '-v', 'error', '-show_entries',
                               'stream=index,codec_type', '-of', 'json', str(path)], 30).stdout)
    v_idx = next(int(s['index']) for s in streams['streams'] if s.get('codec_type') == 'video')
    a_idx = next(int(s['index']) for s in streams['streams'] if s.get('codec_type') == 'audio')
    raw = _run(['ffprobe', '-v', 'error', '-show_entries', 'packet=stream_index,pts_time,duration_time',
                '-of', 'csv=p=0', str(path)], 120).stdout
    packets = {v_idx: [], a_idx: []}
    count = 0
    for line in raw.splitlines():
        parts = line.strip().split(',')
        if len(parts) < 3:
            continue
        count += 1
        if count > 400_000:
            raise ValueError('too many packets to analyse')
        try:
            idx, pts = int(parts[0]), float(parts[1])
        except ValueError:
            continue
        try:
            dur = float(parts[2])
        except ValueError:
            dur = None
        if idx in packets and math.isfinite(pts):
            packets[idx].append((pts, dur if dur is not None and math.isfinite(dur) else None))
    vp, ap = sorted(packets[v_idx]), sorted(packets[a_idx])
    if not vp or not ap:
        raise ValueError('no timestamped packets found for both streams')

    def clock(pk, nominal):
        out, expected, drifts = [], pk[0][0], []
        next_check = pk[0][0]
        for pts, dur in pk:
            d = pts - expected
            drifts.append(d)
            if pts >= next_check:
                out.append({'t': _r(pts, 4), 'drift': _r(d, 6)})
                next_check += checkpoint_seconds
            expected += dur if dur is not None else nominal
        return out, drifts
    v_nominal = 1.0 / meta['fps']
    a_nominal = (ap[-1][0] - ap[0][0]) / max(1, len(ap) - 1)
    v_line, v_drift = clock(vp, v_nominal)
    a_line, a_drift = clock(ap, a_nominal)
    v_start, a_start = vp[0][0], ap[0][0]
    v_end = vp[-1][0] + (vp[-1][1] or v_nominal)
    a_end = ap[-1][0] + (ap[-1][1] or a_nominal)
    start_offset = a_start - v_start
    end_offset = a_end - v_end
    # content onset on the video timeline
    rate = 16000
    pcm = _pcm(path, rate=rate, channels=1, duration=min(30.0, meta['duration'] + 1))
    hop = int(0.005 * rate)
    thr = 10 ** (onset_threshold_dbfs / 20)
    onset = None
    for i in range(0, len(pcm) - hop + 1, hop):
        if math.sqrt(_sumsq(pcm[i:i + hop]) / hop) > thr:
            onset = i / rate
            break
    decode = None
    if decode_check:
        try:
            vr = verify_video(path)
            decode = {'passed': True, 'fps': vr['fps'], 'frames': vr['frames'],
                      'audio_codec': vr['audio_codec']}
        except (ValueError, RuntimeError, OSError, subprocess.CalledProcessError) as exc:
            decode = {'passed': False, 'error': str(exc)[:300]}
    result = {
        'source': {k: meta[k] for k in ('source', 'duration', 'fps', 'width', 'height')},
        'video_packets': len(vp), 'audio_packets': len(ap),
        'video_start_pts': _r(v_start, 6), 'audio_start_pts': _r(a_start, 6),
        'start_offset': _r(start_offset, 6),
        'audio_content_onset': _r(a_start + onset - v_start, 4) if onset is not None else None,
        'video_end': _r(v_end, 6), 'audio_end': _r(a_end, 6), 'end_offset': _r(end_offset, 6),
        'cumulative_drift': _r(end_offset - start_offset, 6),
        'video_timestamp_drift_max_abs': _r(max(abs(d) for d in v_drift), 6),
        'audio_timestamp_drift_max_abs': _r(max(abs(d) for d in a_drift), 6),
        'video_timeline': v_line[:2000], 'audio_timeline': a_line[:2000],
        'decode_check': decode,
    }
    return _pack('av_sync', result,
                 ['start_offset = first audio PTS - first video PTS (positive = audio starts later)',
                  'audio_content_onset = first 5 ms frame above the threshold, on the video timeline; '
                  'it catches delays baked into the samples (e.g. adelay padding) that PTS cannot show',
                  'timestamp drift compares each packet PTS with the running sum of packet durations',
                  'cumulative_drift = end offset - start offset (stream length mismatch)'],
                 ['local .mp4/.mov/.mkv with exactly one video stream, <= 600 s (probe_source)',
                  'resolution limited to packet/audio-frame granularity (AAC frame ~21 ms at 48 kHz)',
                  'content onset needs an audible first sound; it is not lip/visual-event sync',
                  'only the first 30 s are decoded for the onset'])


# --------------------------------------------------------------------------- 16.09 pause_trim

def _silences_audio(path, info, noise_db, min_silence):
    """Same FFmpeg silencedetect parsing as audio_scene_v17, for audio-only files."""
    err = _run(['ffmpeg', '-hide_banner', '-nostdin', '-v', 'info', '-i', str(path), '-map', '0:a:0',
                '-vn', '-af', f'silencedetect=noise={noise_db}dB:d={min_silence}', '-f', 'null', '-'],
               180).stderr
    intervals, start = [], None
    for line in err.splitlines():
        m = _SILENCE_START.search(line)
        if m:
            start = max(0., min(float(m.group(1)), info['duration']))
        m = _SILENCE_END.search(line)
        if m and start is not None:
            end = max(start, min(float(m.group(1)), info['duration']))
            if end > start:
                intervals.append({'start': round(start, 4), 'end': round(end, 4)})
            start = None
    if start is not None and info['duration'] > start:
        intervals.append({'start': round(start, 4), 'end': round(info['duration'], 4)})
    return intervals


def pause_trim(*, source=None, min_pause=0.6, pad_before=0.15, pad_after=0.15,
               max_removal_per_gap=2.0, min_cut=0.05, noise_db=-35.0, **extra):
    """Propose (never apply) cuts that shorten long pauses.

    Silences come from audio_scene_v17.detect_silences (video sources) or the
    same silencedetect parsing (audio-only). For each silence longer than
    min_pause, the removable part is [silence_start + pad_after, silence_end -
    pad_before] (pad_after keeps the tail of the preceding sound, pad_before the
    lead-in of the next); at most max_removal_per_gap is removed, centred in that
    span. Output: cuts, the kept EDL and checks that no cut touches audible audio.
    """
    _no_extra(extra)
    path = _local_file(source)
    min_pause = _num(min_pause, 0.1, 60, 'min_pause')
    pad_before = _num(pad_before, 0, 5, 'pad_before')
    pad_after = _num(pad_after, 0, 5, 'pad_after')
    max_removal_per_gap = _num(max_removal_per_gap, 0.05, 60, 'max_removal_per_gap')
    min_cut = _num(min_cut, 0.01, 5, 'min_cut')
    noise_db = _num(noise_db, -90, -10, 'noise_db')
    info = _probe(path)
    min_sil = max(0.10, min(min_pause, 10.0))
    if info['has_video'] and path.suffix.lower() in VIDEO_CONTAINERS:
        det = detect_silences(path, noise_db=noise_db, min_silence=min_sil)
        silences, method = det['silences'], 'audio_scene_v17.detect_silences'
        duration = det['source']['duration']
    else:
        silences, method = _silences_audio(path, info, noise_db, min_sil), 'ffmpeg_silencedetect'
        duration = info['duration']
    silences = sorted(silences, key=lambda s: s['start'])
    audible, cursor = [], 0.0
    for s in silences:
        if s['start'] > cursor:
            audible.append({'start': round(cursor, 4), 'end': s['start']})
        cursor = max(cursor, s['end'])
    if cursor < duration:
        audible.append({'start': round(cursor, 4), 'end': round(duration, 4)})
    cuts = []
    for s in silences:
        length = s['end'] - s['start']
        if length <= min_pause:
            continue
        lo, hi = s['start'] + pad_after, s['end'] - pad_before
        span = hi - lo
        if span < min_cut:
            continue
        remove = min(span, max_removal_per_gap)
        mid = (lo + hi) / 2
        c0, c1 = mid - remove / 2, mid + remove / 2
        cuts.append({'start': round(c0, 4), 'end': round(c1, 4), 'removed': round(c1 - c0, 4),
                     'silence': s, 'kept_before': round(c0 - s['start'], 4),
                     'kept_after': round(s['end'] - c1, 4)})
    keep, cursor = [], 0.0
    for c in cuts:
        if c['start'] > cursor:
            keep.append({'start': round(cursor, 4), 'end': c['start']})
        cursor = c['end']
    if cursor < duration:
        keep.append({'start': round(cursor, 4), 'end': round(duration, 4)})
    overlap = max((_overlap(c['start'], c['end'], a['start'], a['end'])
                   for c in cuts for a in audible), default=0.0)
    removed = sum(c['removed'] for c in cuts)
    result = {'source': {'path': info['path'], 'duration': _r(duration)}, 'silence_method': method,
              'silences': silences, 'audible': audible, 'cuts': cuts, 'edl': keep,
              'removed_seconds': _r(removed), 'new_duration': _r(duration - removed),
              'max_cut_overlap_with_audible': _r(overlap, 6),
              'checks': {'no_cut_inside_audible': overlap == 0.0,
                         'pads_kept': all(c['kept_before'] >= pad_after - 1e-6
                                          and c['kept_after'] >= pad_before - 1e-6 for c in cuts),
                         'max_removal_respected': all(c['removed'] <= max_removal_per_gap + 1e-6
                                                      for c in cuts)},
              'settings': {'min_pause': min_pause, 'pad_before': pad_before, 'pad_after': pad_after,
                           'max_removal_per_gap': max_removal_per_gap, 'noise_db': noise_db}}
    return _pack('pause_trim', result,
                 ['acoustic silence (below noise_db) is treated as a pause; quiet speech, breaths or music '
                  'below the threshold may be classed as silence',
                  'cuts lie strictly inside detected silences, keeping pad_after after the preceding sound '
                  'and pad_before before the next one',
                  'this is a proposal (EDL); nothing is rendered or written'],
                 [f'local files, duration <= {MAX_SECONDS:g} s', 'silencedetect timing is approximate (~10 ms)',
                  'min silence passed to the detector is clamped to [0.1, 10] s'])


# --------------------------------------------------------------------------- 16.10 audio_rights

_HEX64 = re.compile(r'^[0-9a-fA-F]{64}$')


def audio_rights(*, tracks=None, **extra):
    """Check audio usage records and refuse tracks that lack a licence or permission record.

    tracks: [{'file', 'sha256', 'source', 'licence', 'permission_ref'}, ...].
    A track is included only if the file exists locally, its SHA-256 equals the
    record, and source, licence and permission_ref (written permission or the
    licence deed / document reference) are all filled in. Everything else is
    refused with reasons. Non-commercial (NC) / no-derivatives (ND) licences are
    included with a warning.
    """
    _no_extra(extra)
    if tracks is None:
        raise ValueError('source is required')
    if isinstance(tracks, dict):
        tracks = [tracks]
    if not isinstance(tracks, (list, tuple)) or not 1 <= len(tracks) <= MAX_TRACKS:
        raise ValueError(f'tracks must be a list of 1..{MAX_TRACKS} usage records')
    allowed = {'file', 'sha256', 'source', 'licence', 'license', 'permission_ref', 'title'}
    included, refused, records = [], [], []
    for i, rec in enumerate(tracks):
        if not isinstance(rec, dict):
            raise ValueError(f'tracks[{i}] must be an object')
        unknown = set(rec) - allowed
        if unknown:
            raise ValueError(f'tracks[{i}]: unknown field(s) ' + ', '.join(sorted(map(str, unknown))))
        path = _local_file(rec.get('file'), f'tracks[{i}].file')
        reasons, warnings = [], []
        declared = rec.get('sha256')
        actual = _sha256(path)
        if declared is None or not isinstance(declared, str) or not _HEX64.match(declared.strip()):
            reasons.append('missing or malformed sha256 in the record')
        elif declared.strip().lower() != actual:
            reasons.append('sha256 does not match the file')
        licence = rec.get('licence', rec.get('license'))
        src = _text(rec.get('source'), f'tracks[{i}].source', required=False)
        lic = _text(licence, f'tracks[{i}].licence', required=False)
        perm = _text(rec.get('permission_ref'), f'tracks[{i}].permission_ref', required=False)
        title = _text(rec.get('title'), f'tracks[{i}].title', required=False)
        if not src:
            reasons.append('missing source')
        if not lic or lic.lower() in {'unknown', 'none', 'n/a', '?'}:
            reasons.append('missing licence')
        if not perm or perm.lower() in {'unknown', 'none', 'n/a', '?'}:
            reasons.append('missing written permission / licence reference')
        if lic and re.search(r'(^|[-\s])(nc|nd)($|[-\s])|non.?commercial|no.?deriv', lic, re.I):
            warnings.append('licence restricts commercial use or derivatives; check before commercial work')
        entry = {'index': i, 'file': str(path), 'title': title, 'sha256': actual, 'source': src,
                 'licence': lic, 'permission_ref': perm,
                 'status': 'refused' if reasons else 'included', 'reasons': reasons, 'warnings': warnings}
        records.append(entry)
        (refused if reasons else included).append(i)
    return _pack('audio_rights', {'tracks': records, 'included': included, 'refused': refused,
                                  'all_cleared': not refused},
                 ['the record is supplied by the owner; this op checks completeness and the file hash, '
                  'it does not verify that the licence or permission is genuine or legally sufficient',
                  'a track needs source + licence + permission_ref and a matching sha256 to be included'],
                 [f'at most {MAX_TRACKS} tracks', 'local audio/video files only; files are hashed, not modified',
                  'not legal advice'])


# --------------------------------------------------------------------------- dispatcher

OPS = {
    'loudness': loudness, 'loudness_normalise': loudness_normalise, 'denoise': denoise,
    'word_alignment': word_alignment, 'extract_pcm': extract_pcm, 'cut_crossfade': cut_crossfade,
    'av_sync': av_sync, 'pause_trim': pause_trim, 'audio_rights': audio_rights,
}

EFFECTS = {
    'loudness': 'read', 'loudness_normalise': 'write', 'denoise': 'write',
    'word_alignment': 'read', 'extract_pcm': 'write', 'cut_crossfade': 'write',
    'av_sync': 'read', 'pause_trim': 'read', 'audio_rights': 'read',
}


def run(op, params=None):
    """Validate and dispatch: run('loudness', {'source': 'a.wav'}) -> {'op','result','assumptions','limits'}."""
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
