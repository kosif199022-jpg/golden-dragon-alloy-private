"""Red Rose V27: native timeline renderer, audio mix, colour grades and delivery QA.

Original code re-implementing ideas from the legacy ENG (timeline engine), BEAT
(loudness-aware mix with ducking), COLOR (named grades, .cube LUTs), QA
(delivery checks) and FMT (H.264/yuv420p/faststart/AAC delivery) families.

Standard library + project modules (verify_media.verify_video,
scene_edit_v16.probe_source) + the sibling layer modules motion_v27,
typemotion_v27 and graphics_v27 (imported lazily, each exposing
render_layer(op, params, t, width, height) -> SVG fragment) + CairoSVG for
rasterising. FFmpeg/FFprobe are called only as subprocess.run([...list...],
capture_output=True, timeout=...) or, for piping PNG frames to FFmpeg stdin,
subprocess.Popen([...list...]) with a wall-clock deadline. No shell, no
network imports, no exec/eval, no printing.

Same interface as physics_v20: OPS, EFFECTS ({op: 'read'|'write'}),
run(op, params) -> {'op', 'result', 'assumptions', 'limits'}, strict ValueError
validation and rejection of unknown parameters.

Write ops need approve_write=True and only create a NEW file inside an existing
caller-supplied folder: FFmpeg renders to a temporary file in that folder, the
result is verified with verify_video, then copied with an exclusive create
('xb'); an existing file or a source path is never overwritten.

Owner rules honoured by every render: audio inside MP4 is AAC; no fade from
black and no black first frame (checked before and after rendering); no
overlays/bloom/fog/filters on real footage unless the owner names them (grades
on footage need requested_by_owner=True); no descriptive text is generated -
only words supplied in the timeline are drawn; the output is verified before
it is reported.
"""
from __future__ import annotations

import base64
import copy
import hashlib
import importlib
import importlib.util
import json
import math
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import time
import zlib
from fractions import Fraction
from pathlib import Path

import arabic_shape
from scene_edit_v16 import probe_source
from verify_media import verify_video

MAX_PARAMS = 24
MAX_SECONDS = 600.0
MAX_LONG_SIDE = 3840
MAX_SHORT_SIDE = 2160
MIN_SIDE = 16
MAX_LAYERS = 64
MAX_AUDIO = 16
MAX_SPEC_CHARS = 2_000_000
MAX_LAYER_PARAM_CHARS = 200_000
MAX_FRAGMENT_CHARS = 2_000_000
MAX_SOURCE_BYTES = 2_000_000_000
MAX_LUT_CHARS = 12_000_000
MAX_LUT_SIZE = 65
MAX_LUT_EXPORT_SIZE = 33
BLACK_MEAN = 16.0
BLACK_MAX = 40.0

LAYER_MODULES = {'motion': 'motion_v27', 'typemotion': 'typemotion_v27',
                 'graphics': 'graphics_v27'}
MODULE_WHITELIST = frozenset(LAYER_MODULES.values())
_MODULE_ATTRS = ('LAYER_OPS', 'RENDER_OPS', 'OPS')
SVG_OPS = frozenset({'fragment'})
ROLES = ('voice', 'music', 'sfx')
AUDIO_INPUTS = {'.wav', '.mp3', '.m4a', '.aac', '.flac', '.ogg', '.opus',
                '.mp4', '.mov', '.mkv'}
DELIVERY_INPUTS = {'.mp4', '.mov', '.m4v'}
AAC_RATES = (8000, 11025, 12000, 16000, 22050, 24000, 32000, 44100, 48000,
             64000, 88200, 96000)
PRESETS = ('ultrafast', 'superfast', 'veryfast', 'faster', 'fast', 'medium',
           'slow', 'slower', 'veryslow')
_URL = re.compile(r'^[A-Za-z][A-Za-z0-9+.\-]*:(//|[^\\/])')
_EBU_I = re.compile(r'\bI:\s*(-?inf|-?\d+(?:\.\d+)?)\s*LUFS')
_EBU_LRA = re.compile(r'\bLRA:\s*(-?inf|-?\d+(?:\.\d+)?)\s*LU\b')
_EBU_PEAK = re.compile(r'\bPeak:\s*(-?inf|-?\d+(?:\.\d+)?)\s*dBFS')

TOPICS = {
    'ENG': 'validate_timeline / preview_frame / render_timeline',
    'BEAT': 'plan_mix',
    'COLOR': 'grades / grade_preview_filter / apply_grade / lut_parse / lut_export',
    'QA': 'delivery_check',
    'FMT': 'H.264 yuv420p faststart MP4 with AAC audio',
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


def _path_like(value, name):
    if value is None or (isinstance(value, str) and not value.strip()):
        raise ValueError(f'{name} is required')
    if isinstance(value, bytes) or not isinstance(value, (str, os.PathLike)):
        raise ValueError(f'{name} must be a local file path')
    raw = os.fspath(value)
    if not isinstance(raw, str) or '\x00' in raw:
        raise ValueError(f'{name} must be a local file path')
    stripped = raw.strip()
    if _URL.match(stripped) and not re.match(r'^[A-Za-z]:[\\/]', stripped):
        raise ValueError(f'{name} must be a local file path; URLs are not accepted')
    if stripped.startswith(('\\\\', '//')):
        raise ValueError(f'{name} must be a local file path; network paths are not accepted')
    return Path(stripped).expanduser().resolve()


def _local_file(value, name, allowed, max_bytes=MAX_SOURCE_BYTES):
    path = _path_like(value, name)
    if not path.is_file():
        raise ValueError(f'{name} must be an existing local file')
    if path.suffix.lower() not in allowed:
        raise ValueError(f'{name} must have one of the extensions {sorted(allowed)}')
    if not 0 < path.stat().st_size <= max_bytes:
        raise ValueError(f'{name} must be a non-empty file of at most {max_bytes} bytes')
    return path


def _new_output(value, forbidden):
    path = _path_like(value, 'output')
    if path.suffix.lower() != '.mp4':
        raise ValueError('output must be a .mp4 path')
    if not path.parent.is_dir():
        raise ValueError('output folder must already exist')
    if path.exists() or path.is_symlink():
        raise ValueError('output already exists; refusing to overwrite')
    for item in forbidden:
        if path == Path(item).resolve():
            raise ValueError('output must differ from every source path')
    return path


def _approved(approve_write):
    if approve_write is not True:
        raise PermissionError('this op writes a new file: pass approve_write=True after the owner approves')


def _pack(op, result, assumptions, limits):
    return {'op': op, 'result': result, 'assumptions': list(assumptions),
            'limits': list(limits)}


def _r(value, nd=4):
    if value is None:
        return None
    value = float(value)
    if not math.isfinite(value):
        return None
    return round(value, nd)


def _sha256(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


# --------------------------------------------------------------------------- ffmpeg helpers

def _tools():
    if not shutil.which('ffmpeg') or not shutil.which('ffprobe'):
        raise RuntimeError('FFmpeg and FFprobe must be installed and on PATH')


def _run(cmd, timeout):
    """The single subprocess.run entry point (argument list, no shell)."""
    try:
        done = subprocess.run([*cmd], capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f'{cmd[0]} timed out after {timeout} s') from exc
    if done.returncode != 0:
        tail = done.stderr.decode('utf-8', 'replace').strip().splitlines()[-4:]
        raise RuntimeError(f'{cmd[0]} failed: ' + ' '.join(tail)[:800])
    return done


def _ffprobe_json(path, entries, timeout=30):
    out = _run(['ffprobe', '-v', 'error', '-show_entries', entries, '-of', 'json',
                str(path)], timeout).stdout
    try:
        return json.loads(out.decode('utf-8', 'replace') or '{}')
    except ValueError as exc:
        raise RuntimeError('ffprobe returned invalid JSON') from exc


def _f(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def _probe_audio(path):
    data = _ffprobe_json(path, 'format=duration:stream=index,codec_type,codec_name,'
                               'sample_rate,channels,duration')
    audio = [s for s in data.get('streams', []) if s.get('codec_type') == 'audio']
    if not audio:
        raise ValueError(f'{path.name}: no audio stream')
    a = audio[0]
    duration = _f(a.get('duration')) or _f(data.get('format', {}).get('duration'))
    if duration is None or not 0 < duration <= MAX_SECONDS:
        raise ValueError(f'{path.name}: audio duration must be between 0 and {MAX_SECONDS:g} s')
    try:
        rate = int(a.get('sample_rate') or 0)
        channels = int(a.get('channels') or 0)
    except (TypeError, ValueError):
        rate = channels = 0
    if not 1000 <= rate <= 384000 or not 1 <= channels <= 16:
        raise ValueError(f'{path.name}: unsupported sample rate or channel count')
    return {'duration': duration, 'sample_rate': rate, 'channels': channels,
            'codec': a.get('codec_name')}


def _ebur128(path, timeout=300):
    """Integrated loudness, loudness range and true peak from FFmpeg ebur128's summary."""
    err = _run(['ffmpeg', '-hide_banner', '-nostdin', '-nostats', '-v', 'info', '-i', str(path),
                '-map', '0:a:0', '-vn', '-af', 'ebur128=peak=true', '-f', 'null', '-'],
               timeout).stderr.decode('utf-8', 'replace')
    pos = err.rfind('Summary:')
    if pos < 0:
        raise RuntimeError('ebur128 summary not found in FFmpeg output')
    summary = err[pos:]

    def grab(rx):
        m = rx.search(summary)
        if not m:
            return None
        return None if 'inf' in m.group(1) else float(m.group(1))
    return {'integrated_lufs': grab(_EBU_I), 'loudness_range_lu': grab(_EBU_LRA),
            'true_peak_dbtp': grab(_EBU_PEAK)}


def _first_frame_luma(path):
    raw = _run(['ffmpeg', '-hide_banner', '-nostdin', '-v', 'error', '-i', str(path),
                '-map', '0:v:0', '-an', '-frames:v', '1',
                '-vf', 'scale=64:-2:flags=area,format=gray',
                '-f', 'rawvideo', '-pix_fmt', 'gray', 'pipe:1'], 60).stdout
    if not raw:
        raise ValueError('could not decode the first frame')
    return {'mean': _r(sum(raw) / len(raw), 2), 'max': float(max(raw))}


def _is_black(luma):
    return luma is not None and luma['mean'] < BLACK_MEAN and luma['max'] < BLACK_MAX


def _copy_exclusive(stage, target):
    created = False
    try:
        with target.open('xb') as dst:
            created = True
            with stage.open('rb') as src:
                shutil.copyfileobj(src, dst, 1024 * 1024)
    except FileExistsError as exc:
        raise ValueError('output appeared while rendering; refusing to overwrite') from exc
    except BaseException:
        if created:
            try:
                target.unlink()
            except OSError:
                pass
        raise


def _stage(folder, suffix, tag):
    fd, name = tempfile.mkstemp(prefix=f'.studio_v27_{tag}_', suffix=suffix, dir=folder)
    os.close(fd)
    return Path(name)


def _unlink(path):
    if path is None:
        return
    try:
        Path(path).unlink()
    except OSError:
        pass


# --------------------------------------------------------------------------- colours

def _color(value, name='background'):
    if not isinstance(value, str):
        raise ValueError(f'{name} must be a colour string like "#rrggbb"')
    text = value.strip().lower()
    m = re.fullmatch(r'#([0-9a-f]{3})', text)
    if m:
        rgb = tuple(int(c * 2, 16) for c in m.group(1))
    else:
        m = re.fullmatch(r'#([0-9a-f]{6})', text)
        if m:
            rgb = tuple(int(m.group(1)[i:i + 2], 16) for i in (0, 2, 4))
        else:
            m = re.fullmatch(r'rgb\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*\)', text)
            if not m:
                raise ValueError(f'{name} must be "#rgb", "#rrggbb" or "rgb(r,g,b)"')
            rgb = tuple(int(v) for v in m.groups())
            if any(v > 255 for v in rgb):
                raise ValueError(f'{name} channels must be 0..255')
    return rgb, '#%02x%02x%02x' % rgb


def _luma709(rgb):
    r, g, b = rgb
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


# --------------------------------------------------------------------------- SVG safety

_BAD_SVG = re.compile(
    r'<\s*(script|foreignObject|iframe|object|embed|audio|video|handler|listener)\b'
    r'|<!\s*(DOCTYPE|ENTITY)|<\?xml|\bon[a-zA-Z]+\s*=|@import|javascript\s*:|<\s*xi:include',
    re.I)
_HREF = re.compile(r'(?:xlink:)?href\s*=\s*(["\'])(.*?)\1', re.I | re.S)
_HREF_ANY = re.compile(r'href\s*=', re.I)
_URL_FN = re.compile(r'url\(\s*(["\']?)(.*?)\1\s*\)', re.I | re.S)
_DATA_IMG = re.compile(r'data:image/(png|jpeg|jpg|gif|webp);base64,', re.I)


def _safe_fragment(fragment, where):
    """Reject fragments that could run code, fetch files/URLs or define entities."""
    if not isinstance(fragment, str):
        raise ValueError(f'{where}: render_layer must return an SVG fragment string')
    if len(fragment) > MAX_FRAGMENT_CHARS:
        raise ValueError(f'{where}: SVG fragment exceeds {MAX_FRAGMENT_CHARS} characters')
    if '\x00' in fragment or _BAD_SVG.search(fragment):
        raise ValueError(f'{where}: SVG fragment contains a forbidden element or attribute')
    hrefs = list(_HREF.finditer(fragment))
    if len(hrefs) != len(_HREF_ANY.findall(fragment)):
        raise ValueError(f'{where}: unquoted href attributes are not accepted')
    for m in hrefs:
        target = m.group(2).strip()
        if not (target.startswith('#') or _DATA_IMG.match(target)):
            raise ValueError(f'{where}: only "#id" or embedded raster data: hrefs are allowed')
    for m in _URL_FN.finditer(fragment):
        if not m.group(2).strip().startswith('#'):
            raise ValueError(f'{where}: only url(#id) references are allowed')
    return fragment


# --------------------------------------------------------------------------- layer modules

_MODULE_CACHE = {}


def _load_module(name):
    if name not in MODULE_WHITELIST:
        raise ValueError(f'module {name!r} is not in the whitelist {sorted(MODULE_WHITELIST)}')
    if name in _MODULE_CACHE:
        return _MODULE_CACHE[name]
    try:
        mod = importlib.import_module(name)
    except ModuleNotFoundError as exc:
        if exc.name != name:
            raise ValueError(f'module {name} failed to import: {exc}') from exc
        local = Path(__file__).resolve().with_name(name + '.py')
        if not local.is_file():
            raise ValueError(f'module {name} is not available') from exc
        spec = importlib.util.spec_from_file_location(name, local)
        if spec is None or spec.loader is None:
            raise ValueError(f'module {name} could not be loaded') from exc
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        try:
            spec.loader.exec_module(mod)
        except Exception as inner:
            sys.modules.pop(name, None)
            raise ValueError(f'module {name} failed to import: {inner}') from inner
    except Exception as exc:
        raise ValueError(f'module {name} failed to import: {exc}') from exc
    if not callable(getattr(mod, 'render_layer', None)):
        raise ValueError(f'module {name} has no render_layer(op, params, t, width, height)')
    _MODULE_CACHE[name] = mod
    return mod


def _module_ops(name):
    mod = _load_module(name)
    for attr in _MODULE_ATTRS:
        value = getattr(mod, attr, None)
        if isinstance(value, (dict, set, frozenset, list, tuple)):
            ops = {str(k) for k in value if isinstance(k, str)}
            if ops:
                return ops
    raise ValueError(f'module {name} exposes no op whitelist ({", ".join(_MODULE_ATTRS)})')


def _module_name(value):
    if not isinstance(value, str):
        raise ValueError('module must be one of motion, typemotion, graphics, svg')
    if value == 'svg':
        return 'svg'
    if value in LAYER_MODULES:
        return LAYER_MODULES[value]
    if value in MODULE_WHITELIST:
        return value
    raise ValueError('module must be one of motion, typemotion, graphics, svg')


# --------------------------------------------------------------------------- timeline spec

_SPEC_KEYS = {'width', 'height', 'fps', 'duration', 'background', 'layers', 'audio'}
_LAYER_KEYS = {'module', 'op', 'params', 'start', 'end', 'z', 'opacity'}
_AUDIO_KEYS = {'path', 'start', 'gain_db', 'role'}


def _load_spec(spec):
    if isinstance(spec, str):
        if len(spec) > MAX_SPEC_CHARS:
            raise ValueError(f'spec JSON must be at most {MAX_SPEC_CHARS} characters')
        try:
            spec = json.loads(spec)
        except ValueError as exc:
            raise ValueError(f'spec is not valid JSON: {exc}') from exc
    if not isinstance(spec, dict):
        raise ValueError('spec must be a timeline dict (or its JSON text)')
    try:
        text = json.dumps(spec, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError(f'spec must be JSON-serialisable: {exc}') from exc
    if len(text) > MAX_SPEC_CHARS:
        raise ValueError(f'spec must be at most {MAX_SPEC_CHARS} characters as JSON')
    return json.loads(text)


def _norm_layer(raw, i, duration, fps):
    where = f'layers[{i}]'
    if not isinstance(raw, dict):
        raise ValueError(f'{where} must be a dict')
    unknown = set(raw) - _LAYER_KEYS
    if unknown:
        raise ValueError(f'{where}: unknown key(s) {sorted(unknown)}')
    module = _module_name(raw.get('module'))
    params = raw.get('params', {})
    if not isinstance(params, dict):
        raise ValueError(f'{where}.params must be a dict')
    if len(json.dumps(params, ensure_ascii=False)) > MAX_LAYER_PARAM_CHARS:
        raise ValueError(f'{where}.params is larger than {MAX_LAYER_PARAM_CHARS} characters')
    op = raw.get('op', 'fragment' if module == 'svg' else None)
    if not isinstance(op, str) or not op.strip():
        raise ValueError(f'{where}.op must be a non-empty string')
    if module == 'svg':
        if op not in SVG_OPS:
            raise ValueError(f'{where}: svg layers use op "fragment"')
        if set(params) != {'svg'}:
            raise ValueError(f'{where}: svg layers need params {{"svg": "<g>...</g>"}} only')
        _safe_fragment(params['svg'], where)
    else:
        ops = _module_ops(module)
        if op not in ops:
            raise ValueError(f'{where}: op {op!r} is not offered by {module} ({sorted(ops)[:40]})')
    start = _num(raw.get('start', 0.0), 0.0, duration, f'{where}.start')
    end = _num(raw.get('end', duration), 0.0, duration, f'{where}.end')
    if end <= start:
        raise ValueError(f'{where}: end must be after start')
    z = _int(raw.get('z', 0), -1000, 1000, f'{where}.z')
    opacity = _num(raw.get('opacity', 1.0), 0.0, 1.0, f'{where}.opacity')
    warnings = []
    if (end - start) * fps < 1:
        warnings.append(f'{where} is shorter than one frame and may never be drawn')
    if (op in _DURATION_OPS.get(module, ()) and 'duration' not in params
            and end - start >= 0.2):
        # a text layer animates over its own span unless the caller says otherwise
        params = dict(params, duration=round(end - start, 6))
    return {'module': module, 'op': op, 'params': params, 'start': start, 'end': end,
            'z': z, 'opacity': opacity}, warnings


def _norm_audio(raw, i, duration, probe=True):
    where = f'audio[{i}]'
    if not isinstance(raw, dict):
        raise ValueError(f'{where} must be a dict')
    unknown = set(raw) - _AUDIO_KEYS
    if unknown:
        raise ValueError(f'{where}: unknown key(s) {sorted(unknown)}')
    path = _local_file(raw.get('path'), f'{where}.path', AUDIO_INPUTS)
    start = _num(raw.get('start', 0.0), 0.0, duration, f'{where}.start')
    if start >= duration:
        raise ValueError(f'{where}.start must be before the timeline end')
    gain = _num(raw.get('gain_db', 0.0), -30.0, 12.0, f'{where}.gain_db')
    role = _choice(raw.get('role', 'music'), set(ROLES), f'{where}.role')
    item = {'path': str(path), 'start': start, 'gain_db': gain, 'role': role}
    if probe:
        item['probe'] = _probe_audio(path)
    return item


def _normalize(spec, *, probe_audio=True):
    """Return (normalized, errors, warnings); never raises for content errors."""
    errors, warnings = [], []
    spec = _load_spec(spec)
    unknown = set(spec) - _SPEC_KEYS
    if unknown:
        errors.append(f'unknown top-level key(s) {sorted(unknown)}')
    out = {}
    try:
        w = _int(spec.get('width'), MIN_SIDE, MAX_LONG_SIDE, 'width')
        h = _int(spec.get('height'), MIN_SIDE, MAX_LONG_SIDE, 'height')
        if w % 2 or h % 2:
            raise ValueError('width and height must be even (yuv420p)')
        if max(w, h) > MAX_LONG_SIDE or min(w, h) > MAX_SHORT_SIDE:
            raise ValueError('frame must fit 3840x2160 (either orientation)')
        out['width'], out['height'] = w, h
    except ValueError as exc:
        errors.append(str(exc))
    try:
        out['fps'] = _int(spec.get('fps'), 6, 60, 'fps')
    except ValueError as exc:
        errors.append(str(exc))
    try:
        d = _num(spec.get('duration'), 0.0, MAX_SECONDS, 'duration')
        if d <= 0:
            raise ValueError('duration must be > 0')
        out['duration'] = d
    except ValueError as exc:
        errors.append(str(exc))
    try:
        rgb, hex_ = _color(spec.get('background', '#202020'))
        out['background'] = hex_
        out['_bg_rgb'] = rgb
    except ValueError as exc:
        errors.append(str(exc))
    if errors:
        return None, errors, warnings
    fps, duration = out['fps'], out['duration']
    frames = max(1, int(round(duration * fps)))
    out['frames'] = frames
    out['render_duration'] = frames / fps
    layers = spec.get('layers', [])
    if not isinstance(layers, list) or len(layers) > MAX_LAYERS:
        errors.append(f'layers must be a list of at most {MAX_LAYERS} items')
        layers = []
    out['layers'] = []
    for i, raw in enumerate(layers):
        try:
            layer, warn = _norm_layer(raw, i, duration, fps)
            out['layers'].append(layer)
            warnings.extend(warn)
        except ValueError as exc:
            errors.append(str(exc) if str(exc).startswith('layers[') else f'layers[{i}]: {exc}')
    audio = spec.get('audio', [])
    if not isinstance(audio, list) or len(audio) > MAX_AUDIO:
        errors.append(f'audio must be a list of at most {MAX_AUDIO} items')
        audio = []
    out['audio'] = []
    can_probe = probe_audio and bool(shutil.which('ffprobe'))
    if audio and probe_audio and not can_probe:
        warnings.append('ffprobe not on PATH: audio files were not probed')
    for i, raw in enumerate(audio):
        try:
            out['audio'].append(_norm_audio(raw, i, duration, probe=can_probe))
        except (ValueError, RuntimeError) as exc:
            errors.append(str(exc) if str(exc).startswith('audio[') else f'audio[{i}]: {exc}')
    if not out['layers']:
        warnings.append('timeline has no layers: every frame is the plain background')
    return out, errors, warnings


def _public(spec):
    return {k: v for k, v in spec.items() if not k.startswith('_')}


# --------------------------------------------------------------------------- compose + raster

def _compose(spec, t):
    w, h = spec['width'], spec['height']
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
             f'width="{w}" height="{h}" viewBox="0 0 {w} {h}">',
             f'<rect x="0" y="0" width="{w}" height="{h}" fill="{spec["background"]}"/>']
    active = []
    order = sorted(enumerate(spec['layers']), key=lambda p: (p[1]['z'], p[0]))
    for idx, layer in order:
        if not layer['start'] <= t < layer['end'] or layer['opacity'] <= 0:
            continue
        where = f'layers[{idx}]'
        if layer['module'] == 'svg':
            frag = layer['params']['svg']
        else:
            mod = _load_module(layer['module'])
            try:
                frag = mod.render_layer(layer['op'], copy.deepcopy(layer['params']),
                                        t - layer['start'], w, h)
            except ValueError as exc:
                raise ValueError(f'{where} ({layer["module"]}.{layer["op"]}): {exc}') from exc
            except Exception as exc:
                raise RuntimeError(f'{where} ({layer["module"]}.{layer["op"]}) failed: {exc}') from exc
        frag = _safe_fragment(frag, where)
        if layer['opacity'] < 1:
            parts.append(f'<g opacity="{layer["opacity"]:.4f}">{frag}</g>')
        else:
            parts.append(f'<g>{frag}</g>')
        active.append(idx)
    parts.append('</svg>')
    return ''.join(parts), active


def _check_xml(svg):
    import xml.etree.ElementTree as ET
    try:
        ET.fromstring(svg)
    except ET.ParseError as exc:
        raise ValueError(f'composed SVG is not well-formed: {exc}') from exc


def _cairosvg():
    try:
        return importlib.import_module('cairosvg')
    except ImportError as exc:
        raise RuntimeError('CairoSVG is required for rasterising frames') from exc


def _shape(svg):
    """Raster copy of a logical SVG: Arabic shaped, rtl anchors fixed, stroke under fill.

    CairoSVG has no text shaper, so this runs before EVERY rasterisation; the
    logical SVG returned to callers is never modified. Never shapes twice."""
    return arabic_shape.shape_svg_for_raster(svg)


def _svg2png(shaped_svg, width, height):
    return _cairosvg().svg2png(bytestring=shaped_svg.encode('utf-8'), output_width=width,
                               output_height=height, unsafe=False)


def _raster(svg, width, height, reports=None):
    shaped, rep = _shape(svg)
    if reports is not None:
        reports.append(rep)
    return _svg2png(shaped, width, height)


def _shaping_summary(reports):
    return arabic_shape.summarize(reports)


def _png_luma(data):
    """Mean/max Rec.709 luma (0..255) of an 8-bit RGB/RGBA non-interlaced PNG."""
    if not data or data[:8] != b'\x89PNG\r\n\x1a\n':
        return None
    pos, idat, ihdr = 8, [], None
    while pos + 8 <= len(data):
        length = int.from_bytes(data[pos:pos + 4], 'big')
        ctype = data[pos + 4:pos + 8]
        body = data[pos + 8:pos + 8 + length]
        pos += 12 + length
        if ctype == b'IHDR':
            ihdr = struct.unpack('>IIBBBBB', body[:13])
        elif ctype == b'IDAT':
            idat.append(body)
        elif ctype == b'IEND':
            break
    if not ihdr:
        return None
    w, h, depth, ctype, _, _, interlace = ihdr
    if depth != 8 or ctype not in (2, 6) or interlace != 0 or w * h > 400_000:
        return None
    bpp = 4 if ctype == 6 else 3
    raw = zlib.decompress(b''.join(idat))
    stride = w * bpp
    if len(raw) < h * (stride + 1):
        return None
    prev = bytearray(stride)
    total, peak = 0.0, 0.0
    for y in range(h):
        base = y * (stride + 1)
        f = raw[base]
        line = bytearray(raw[base + 1:base + 1 + stride])
        if f == 1:
            for i in range(bpp, stride):
                line[i] = (line[i] + line[i - bpp]) & 255
        elif f == 2:
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 255
        elif f == 3:
            for i in range(stride):
                left = line[i - bpp] if i >= bpp else 0
                line[i] = (line[i] + ((left + prev[i]) >> 1)) & 255
        elif f == 4:
            for i in range(stride):
                a = line[i - bpp] if i >= bpp else 0
                b = prev[i]
                c = prev[i - bpp] if i >= bpp else 0
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pred = a if pa <= pb and pa <= pc else (b if pb <= pc else c)
                line[i] = (line[i] + pred) & 255
        for x in range(0, stride, bpp):
            alpha = line[x + 3] / 255.0 if bpp == 4 else 1.0
            luma = (0.2126 * line[x] + 0.7152 * line[x + 1] + 0.0722 * line[x + 2]) * alpha
            total += luma
            if luma > peak:
                peak = luma
        prev = line
    return {'mean': _r(total / (w * h), 2), 'max': _r(peak, 2)}


def _small_size(w, h, target=160):
    sw = max(16, min(target, w))
    sh = max(2, int(round(sw * h / w / 2)) * 2)
    return sw, sh


def _first_frame_estimate(spec):
    """Estimate whether frame 0 is black: raster if possible, else background colour."""
    bg_luma = _luma709(spec['_bg_rgb'])
    active0 = [i for i, l in enumerate(spec['layers'])
               if l['start'] <= 0 < l['end'] and l['opacity'] > 0]
    result = {'background_luma': _r(bg_luma, 2), 'layers_at_t0': active0,
              'method': None, 'luma': None, 'black': None}
    try:
        svg, _ = _compose(spec, 0.0)
        sw, sh = _small_size(spec['width'], spec['height'])
        reps = []
        luma = _png_luma(_raster(svg, sw, sh, reps))
        result['shaping_warnings'] = _shaping_summary(reps)['warnings']
        if luma is not None:
            result.update(method='raster_t0', luma=luma, black=_is_black(luma))
            return result
    except Exception as exc:  # estimate only: fall back to the background colour
        result['raster_error'] = str(exc)[:300]
    result['method'] = 'background_colour'
    if bg_luma >= BLACK_MEAN:
        result['black'] = False
    elif not active0:
        result['black'] = True
    else:
        result['black'] = None  # uncertain: dark background, layers at t=0 not rasterised
    return result


# --------------------------------------------------------------------------- ENG ops

def validate_timeline(*, spec=None, **extra):
    """Check a timeline spec: modules/ops whitelist, times, sizes, audio, first frame."""
    _no_extra(extra)
    if spec is None:
        raise ValueError('spec is required')
    norm, errors, warnings = _normalize(spec)
    first = None
    dry = []
    if norm is not None and not errors:
        dry = _dry_run(norm)
        errors.extend(e['error'] for e in dry if e['error'])
    if norm is not None and not errors:
        first = _first_frame_estimate(norm)
        if first['black'] is True:
            errors.append('first frame would be black (owner rule: no black frames / fade from black '
                          'at the very start); use a non-black background or a visible layer at t=0')
        elif first['black'] is None:
            warnings.append('first frame could not be rasterised and the background is dark: '
                            'cannot confirm it is not black')
        for w in first.get('shaping_warnings') or []:
            if w not in warnings:
                warnings.append(w)
    result = {'valid': not errors, 'errors': errors, 'warnings': warnings,
              'first_frame': first,
              'layers_checked': [{k: v for k, v in e.items() if k != 'error'} for e in dry],
              'invalid_layers': [e['layer'] for e in dry if e['error']],
              'normalized': _public(norm) if norm is not None else None}
    return _pack('validate_timeline', result,
                 ['layer times are seconds; a layer is drawn for start <= t < end',
                  'render_layer receives layer-local time (t - start) in seconds',
                  'black = mean Rec.709 luma < 16 and max < 40 on a 0..255 scale',
                  'ops are taken from each sibling module\'s LAYER_OPS / RENDER_OPS / OPS'],
                 [f'<= {MAX_LAYERS} layers, <= {MAX_AUDIO} audio clips, fps 6..60, '
                  f'duration <= {MAX_SECONDS:g} s, even dims fitting 3840x2160',
                  'each layer is dry-run once (render_layer at its local midpoint); a param that '
                  'only fails at other times is caught at render time',
                  'first-frame check rasterises a small proxy of t=0 only'])


_DURATION_OPS = {'typemotion_v27': ('kinetic_text', 'lower_third', 'caption')}


def _dry_run(norm):
    """Render every non-svg layer once at its local midpoint; report the first failure."""
    out = []
    w, h = norm['width'], norm['height']
    for i, layer in enumerate(norm['layers']):
        where = f'layers[{i}]'
        entry = {'layer': i, 'module': layer['module'], 'op': layer['op'], 'ok': True,
                 'error': None}
        if layer['module'] != 'svg':
            local = (layer['end'] - layer['start']) / 2.0
            try:
                mod = _load_module(layer['module'])
                frag = mod.render_layer(layer['op'], copy.deepcopy(layer['params']), local, w, h)
                _safe_fragment(frag, where)
                entry['chars'] = len(frag)
            except Exception as exc:  # any failure makes the timeline invalid
                msg = str(exc)
                if not msg.startswith(where):
                    msg = f'{where} ({layer["module"]}.{layer["op"]}): {msg}'
                entry.update(ok=False, error=msg[:600])
        out.append(entry)
    return out


def preview_frame(*, spec=None, t=0.0, rasterize=False, png_width=None, **extra):
    """Compose all active layers at time t into one SVG; optional PNG (base64, no file)."""
    _no_extra(extra)
    if spec is None:
        raise ValueError('spec is required')
    _bool(rasterize, 'rasterize')
    norm, errors, warnings = _normalize(spec, probe_audio=False)
    if errors:
        raise ValueError('invalid timeline: ' + '; '.join(errors[:8]))
    t = _num(t, 0.0, norm['duration'], 't')
    if t >= norm['duration']:
        t = max(0.0, norm['duration'] - 1.0 / norm['fps'])
    svg, active = _compose(norm, t)
    _check_xml(svg)
    result = {'t': _r(t, 6), 'frame_index': int(math.floor(t * norm['fps'] + 1e-9)),
              'active_layers': active, 'svg': svg, 'svg_chars': len(svg),
              'warnings': warnings}
    if rasterize:
        pw = norm['width'] if png_width is None else _int(png_width, 16, MAX_LONG_SIDE, 'png_width')
        _raster_into(result, svg, norm, pw)
    elif png_width is not None:
        raise ValueError('png_width needs rasterize=true')
    return _pack('preview_frame', result,
                 ['layers sorted by z (ties keep list order); opacity wraps each fragment in <g>',
                  'fragments are sanitised: no scripts, foreignObject, entities or external hrefs',
                  'the returned svg keeps logical text; the PNG is drawn from a shaped copy '
                  '(arabic_shape: joined presentation forms, visual order, stroke under fill)'],
                 ['PNG is returned in memory as base64; no file is written',
                  'Arabic in the PNG uses presentation forms + an installed font that has them; '
                  'qa.passed is false and warnings name arabic_unshaped/arabic_font_missing_forms '
                  'when that could not be guaranteed'])


def _raster_into(result, svg, norm, pw):
    """Shape once, rasterise the full PNG and a luma proxy, and record fail-closed QA."""
    ph = max(2, int(round(pw * norm['height'] / norm['width'])))
    shaped, rep = _shape(svg)
    png = _svg2png(shaped, pw, ph)
    sw, sh = _small_size(norm['width'], norm['height'])
    luma = _png_luma(_svg2png(shaped, sw, sh))
    shaping = _shaping_summary([rep])
    for w in shaping['warnings']:
        if w not in result['warnings']:
            result['warnings'].append(w)
    black = _is_black(luma) if luma else None
    result.update(png_base64=base64.b64encode(png).decode('ascii'), png_width=pw,
                  png_height=ph, png_bytes=len(png), luma=luma, black=black,
                  shaping=shaping,
                  qa={'passed': shaping['ok'] and black is False,
                      'text_shaping_ok': shaping['ok'], 'black': black})
    return result


def _encode_frames(spec, stage, crf, preset, deadline, reports=None):
    """Pipe CairoSVG PNG frames into FFmpeg (image2pipe) -> H.264 yuv420p MP4.

    Each composed frame is shaped (arabic_shape) before rasterising; shaping
    reports with warnings (and the first one) are appended to `reports`."""
    _cairosvg()
    w, h, fps, n = spec['width'], spec['height'], spec['fps'], spec['frames']
    cmd = ['ffmpeg', '-hide_banner', '-v', 'error', '-f', 'image2pipe',
           '-framerate', str(fps), '-c:v', 'png', '-i', 'pipe:0', '-frames:v', str(n),
           '-vf', 'scale=out_color_matrix=bt709:out_range=tv,format=yuv420p',
           '-c:v', 'libx264', '-preset', preset, '-crf', str(crf), '-pix_fmt', 'yuv420p',
           '-colorspace', 'bt709', '-color_primaries', 'bt709', '-color_trc', 'bt709',
           '-r', str(fps), '-movflags', '+faststart', '-an', '-y', str(stage)]
    log = _stage(stage.parent, '.log', 'log')
    proc = None
    try:
        with log.open('wb') as logfh:
            proc = subprocess.Popen([*cmd], stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                                    stderr=logfh)
            try:
                for i in range(n):
                    if time.monotonic() > deadline:
                        raise RuntimeError('render exceeded its time budget')
                    svg, _ = _compose(spec, i / fps)
                    shaped, rep = _shape(svg)
                    if reports is not None and (rep['warnings'] or rep['nodes_shaped']
                                                or rep['stroke_split']):
                        if rep['warnings'] or len(reports) < 4:
                            reports.append(rep)
                    png = _svg2png(shaped, w, h)
                    try:
                        proc.stdin.write(png)
                    except (BrokenPipeError, OSError) as exc:
                        raise RuntimeError('ffmpeg stopped reading frames') from exc
                proc.stdin.close()
                remaining = max(30.0, deadline - time.monotonic())
                try:
                    code = proc.wait(timeout=remaining)
                except subprocess.TimeoutExpired as exc:
                    raise RuntimeError('ffmpeg encode timed out') from exc
            except BaseException:
                if proc.poll() is None:
                    proc.kill()
                    try:
                        proc.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        pass
                raise
        if code != 0:
            tail = log.read_bytes().decode('utf-8', 'replace').strip().splitlines()[-4:]
            raise RuntimeError('ffmpeg encode failed: ' + ' '.join(tail)[:800])
    finally:
        if proc is not None and proc.stdin and not proc.stdin.closed:
            try:
                proc.stdin.close()
            except OSError:
                pass
        _unlink(log)


def render_timeline(*, spec=None, output=None, approve_write=False, crf=18, preset='medium',
                    **extra):
    """Render a timeline to a NEW H.264/yuv420p faststart MP4 (+AAC mix), verified."""
    _no_extra(extra)
    if spec is None:
        raise ValueError('spec is required')
    crf = _int(crf, 12, 30, 'crf')
    preset = _choice(preset, set(PRESETS), 'preset')
    _tools()
    norm, errors, warnings = _normalize(spec)
    if not errors:
        errors = [e['error'] for e in _dry_run(norm) if e['error']]
    if errors:
        raise ValueError('invalid timeline: ' + '; '.join(errors[:8]))
    target = _new_output(output, [a['path'] for a in norm['audio']])
    _approved(approve_write)
    first = _first_frame_estimate(norm)
    if first['black'] is True:
        raise ValueError('first frame would be black (owner rule); refusing to render')
    _cairosvg()
    mix = _plan_mix_core(norm['audio'], norm['render_duration']) if norm['audio'] else None
    frames = norm['frames']
    deadline = time.monotonic() + 120 + frames * 2.5
    video = _stage(target.parent, '.mp4', 'video')
    final = None
    shaping_reports = []
    try:
        _encode_frames(norm, video, crf, preset, deadline, shaping_reports)
        if mix is not None and mix['clips']:
            final = _stage(target.parent, '.mp4', 'mux')
            cmd = ['ffmpeg', '-hide_banner', '-nostdin', '-v', 'error', '-y', '-i', str(video)]
            for clip in mix['clips']:
                cmd += ['-i', clip['path']]
            cmd += ['-filter_complex', mix['filter_complex'], '-map', '0:v:0', '-map', '[aout]',
                    '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k',
                    '-ar', str(mix['sample_rate']), '-movflags', '+faststart', str(final)]
            remaining = max(60, int(deadline - time.monotonic()))
            _run(cmd, remaining)
            has_audio = True
        else:
            final, video = video, None
            has_audio = False
        qa = verify_video(final, expected_fps=norm['fps'], width=norm['width'],
                          height=norm['height'], expected_frames=frames,
                          expected_audio=has_audio)
        if qa['codec'] != 'h264':
            raise RuntimeError('rendered video is not H.264')
        if has_audio and qa['audio_codec'] != 'aac':
            raise RuntimeError('audio inside MP4 must be AAC')
        luma = _first_frame_luma(final)
        if _is_black(luma):
            raise RuntimeError('rendered first frame is black (owner rule); output not delivered')
        _copy_exclusive(final, target)
    finally:
        _unlink(video)
        _unlink(final)
    shaping = _shaping_summary(shaping_reports)
    if not shaping['ok']:
        # fail closed: text that may be unreadable is never reported as verified
        qa = dict(qa, passed=False, text_shaping='failed')
        warnings = list(warnings) + [w for w in shaping['warnings'] if w not in warnings]
    else:
        qa = dict(qa, text_shaping='ok' if shaping['applied'] else 'no_rtl_text')
    receipt = {'status': 'rendered_and_verified' if shaping['ok'] else 'rendered_with_warnings',
               'output': str(target), 'shaping': shaping,
               'sha256': _sha256(target), 'bytes': target.stat().st_size,
               'duration': _r(qa['duration'], 4), 'frames': qa['frames'], 'fps': norm['fps'],
               'width': norm['width'], 'height': norm['height'], 'video_codec': qa['codec'],
               'audio_codec': qa['audio_codec'], 'first_frame_luma': luma,
               'layers': len(norm['layers']), 'audio_clips': len(norm['audio']),
               'mix': ({k: v for k, v in mix.items() if k != 'filter_complex'}
                       if mix else None),
               'warnings': warnings, 'qa': qa}
    return _pack('render_timeline', receipt,
                 ['each frame: compose SVG -> CairoSVG PNG -> FFmpeg image2pipe -> libx264 yuv420p',
                  'BT.709 matrix, limited range; faststart; audio mixed per plan_mix into AAC 192k',
                  'no fade from black is added; the first frame is measured after encoding'],
                 ['CPU-only, frame-by-frame rasterising: long or 4K timelines are slow',
                  f'time budget ~120 s + 2.5 s per frame; stage files live beside the output',
                  'visual quality of each layer depends on the sibling layer module'])


# --------------------------------------------------------------------------- BEAT: audio mix

def _fade_lengths(role, start, avail):
    if role == 'voice':
        fin, fout = 0.012, 0.02
    elif role == 'sfx':
        fin, fout = 0.004, 0.01
    else:
        fin, fout = (0.25 if start > 0 else 0.02), 0.8
    cap = max(0.002, avail / 3)
    return min(fin, cap), min(fout, cap)


def _plan_mix_core(audio, duration, voice_target=-16.0, music_target=-28.0):
    """Measure each clip, compute gains/fades and the FFmpeg filter graph."""
    _tools()
    voices = [a for a in audio if a['role'] == 'voice']
    warnings = []
    if voices:
        rate = voices[0]['probe']['sample_rate']
        if rate not in AAC_RATES:
            warnings.append(f'voice sample rate {rate} Hz cannot be carried by AAC; '
                            'mix runs at 48000 Hz')
            rate = 48000
    else:
        rate = 48000
    music_goal = music_target if voices else max(music_target, -18.0)
    clips = []
    for idx, a in enumerate(audio):
        p = a.get('probe') or _probe_audio(Path(a['path']))
        avail = min(p['duration'], duration - a['start'])
        if avail <= 0.02:
            warnings.append(f'audio[{idx}] starts too late to be heard; skipped')
            continue
        ebu = _ebur128(a['path'])
        measured = ebu['integrated_lufs']
        target = {'voice': voice_target, 'music': music_goal, 'sfx': -20.0}[a['role']]
        if measured is None:
            norm_gain = 0.0
            warnings.append(f'audio[{idx}] integrated loudness unmeasurable (too short or silent); '
                            'only gain_db applied')
        else:
            norm_gain = max(-24.0, min(24.0, target - measured))
        gain = norm_gain + a['gain_db']
        fin, fout = _fade_lengths(a['role'], a['start'], avail)
        resample = p['sample_rate'] != rate
        if a['role'] == 'voice' and resample:
            warnings.append(f'audio[{idx}] voice at {p["sample_rate"]} Hz is resampled to {rate} Hz '
                            '(sample-rate only; never time-stretched)')
        clips.append({'index': idx, 'path': a['path'], 'role': a['role'], 'start': _r(a['start'], 6),
                      'used_seconds': _r(avail, 6), 'measured_lufs': _r(measured, 2),
                      'true_peak_dbtp': _r(ebu['true_peak_dbtp'], 2), 'target_lufs': target,
                      'normalise_gain_db': _r(norm_gain, 2), 'trim_db': _r(a['gain_db'], 2),
                      'total_gain_db': _r(gain, 2), 'fade_in': _r(fin, 4), 'fade_out': _r(fout, 4),
                      'resampled': resample, 'source_rate': p['sample_rate']})
    graph, D = [], f'{duration:.6f}'
    groups = {'voice': [], 'music': [], 'sfx': []}
    for k, c in enumerate(clips):
        avail = c['used_seconds']
        chain = [f'atrim=start=0:duration={avail:.6f}', 'asetpts=PTS-STARTPTS']
        if c['resampled']:
            chain.append(f'aresample={rate}')
        chain += [f'aformat=sample_fmts=fltp:sample_rates={rate}:channel_layouts=stereo',
                  f'volume={c["total_gain_db"]:.3f}dB',
                  f'afade=t=in:st=0:d={c["fade_in"]:.4f}',
                  f'afade=t=out:st={max(0.0, avail - c["fade_out"]):.6f}:d={c["fade_out"]:.4f}',
                  f'adelay=delays={int(round(c["start"] * rate))}S:all=1']
        label = f'c{k}'
        graph.append(f'[{k + 1}:a:0]' + ','.join(chain) + f'[{label}]')
        groups[c['role']].append(label)

    def merge(labels, name):
        if not labels:
            return None
        if len(labels) == 1:
            graph.append(f'[{labels[0]}]apad=whole_dur={D}[{name}]')
        else:
            graph.append(''.join(f'[{x}]' for x in labels) +
                         f'amix=inputs={len(labels)}:duration=longest:dropout_transition=0:'
                         f'normalize=0,apad=whole_dur={D}[{name}]')
        return name
    vox = merge(groups['voice'], 'vox')
    mus = merge(groups['music'], 'mus')
    ducked = False
    final = []
    if vox and mus:
        graph.append('[vox]asplit=2[voxm][voxsc]')
        graph.append('[mus][voxsc]sidechaincompress=threshold=0.02:ratio=8:attack=15:'
                     'release=400:makeup=1:knee=2.5[mduck]')
        final += ['voxm', 'mduck']
        ducked = True
    else:
        final += [x for x in (vox, mus) if x]
    final += groups['sfx']
    tail = f'apad=whole_dur={D},atrim=duration={D},alimiter=limit=0.891:level=false[aout]'
    if not final:
        return {'clips': [], 'filter_complex': None, 'sample_rate': rate, 'ducking': False,
                'duration': _r(duration, 6), 'warnings': warnings}
    if len(final) == 1:
        graph.append(f'[{final[0]}]{tail}')
    else:
        graph.append(''.join(f'[{x}]' for x in final) +
                     f'amix=inputs={len(final)}:duration=longest:dropout_transition=0:normalize=0,'
                     + tail)
    return {'clips': clips, 'filter_complex': ';'.join(graph), 'sample_rate': rate,
            'ducking': ducked, 'duration': _r(duration, 6), 'input_order': [c['path'] for c in clips],
            'warnings': warnings}


def plan_mix(*, audio=None, duration=None, voice_target_lufs=-16.0, music_target_lufs=-28.0,
             **extra):
    """Measure inputs (ebur128) and plan gains, fades, ducking and the AAC mix graph."""
    _no_extra(extra)
    duration = _num(duration, 0.0, MAX_SECONDS, 'duration')
    if duration <= 0:
        raise ValueError('duration must be > 0')
    vt = _num(voice_target_lufs, -30.0, -10.0, 'voice_target_lufs')
    mt = _num(music_target_lufs, -40.0, -14.0, 'music_target_lufs')
    if not isinstance(audio, list) or not 1 <= len(audio) <= MAX_AUDIO:
        raise ValueError(f'audio must be a list of 1..{MAX_AUDIO} clips')
    _tools()
    items = [_norm_audio(a, i, duration) for i, a in enumerate(audio)]
    plan = _plan_mix_core(items, duration, vt, mt)
    plan['ffmpeg_inputs_note'] = 'input 0 is the rendered picture; clip k is FFmpeg input k+1'
    return _pack('plan_mix', plan,
                 ['integrated loudness measured per input with FFmpeg ebur128 before gains',
                  'voice -> voice target; music bed -> music target under voice (-18 LUFS without voice); '
                  'sfx -> -20 LUFS; gain_db is a trim on top; gains capped to +/-24 dB',
                  'music is ducked under voice with sidechaincompress; fades only at clip edges',
                  'voice is never time-stretched; mix runs at the voice sample rate when AAC allows',
                  'final alimiter at ~-1 dBFS sample peak (level=false, no auto-gain)'],
                 ['short clips (< 0.4 s) may have no gated integrated loudness',
                  'ducking amount is fixed (ratio 8, threshold 0.02), not tuned per programme',
                  'the limiter is sample-peak, not oversampled true-peak'])


# --------------------------------------------------------------------------- COLOR: grades + LUTs

GRADES = {
    'neutral_clean': {'chain': 'eq=contrast=1.04:saturation=1.03',
                      'note': 'gentle contrast and saturation lift', 'lifts_blacks': False},
    'warm_golden': {'chain': 'colortemperature=temperature=5000:mix=0.55,eq=saturation=1.06:gamma=1.02',
                    'note': 'golden-hour warmth', 'lifts_blacks': False},
    'teal_orange': {'chain': 'colorbalance=rs=-0.06:bs=0.08:rh=0.08:gh=0.02:bh=-0.07,'
                             'eq=contrast=1.06:saturation=1.08',
                    'note': 'teal shadows, warm highlights', 'lifts_blacks': False},
    'cool_night': {'chain': 'colortemperature=temperature=9000:mix=0.5,'
                            'eq=contrast=1.06:brightness=-0.02:saturation=0.9',
                   'note': 'cool blue night look', 'lifts_blacks': False},
    'filmic_soft': {'chain': "curves=all='0/0 0.25/0.22 0.5/0.5 0.75/0.79 1/0.97',eq=saturation=0.94",
                    'note': 'soft S-curve, rolled-off highlights, black point kept', 'lifts_blacks': False},
    'mono_silver': {'chain': 'eq=saturation=0:contrast=1.12:gamma=0.98',
                    'note': 'black and white with punch', 'lifts_blacks': False},
    'bleach_bypass': {'chain': 'eq=saturation=0.55:contrast=1.22',
                      'note': 'desaturated high-contrast', 'lifts_blacks': False},
    'desert_sun': {'chain': 'colortemperature=temperature=4300:mix=0.5,colorbalance=rm=0.04:bm=-0.04,'
                            'eq=saturation=1.05',
                   'note': 'hot amber daylight', 'lifts_blacks': False},
    'emerald': {'chain': 'colorbalance=gs=0.04:gm=0.05:rm=-0.02,eq=saturation=1.04',
                'note': 'green-leaning mids and shadows', 'lifts_blacks': False},
    'red_rose': {'chain': "colorbalance=rm=0.05:rh=0.03:gm=-0.02:bm=0.01,curves=r='0/0 0.5/0.53 1/1',"
                          'eq=saturation=1.07',
                 'note': 'rose-red mids, skin kept natural', 'lifts_blacks': False},
    'cairo_dusk': {'chain': 'colortemperature=temperature=5600:mix=0.4,colorbalance=bs=0.05:rh=0.05,'
                            'eq=contrast=1.05',
                   'note': 'blue shadows with warm sky highlights', 'lifts_blacks': False},
    'punchy_social': {'chain': 'eq=contrast=1.1:saturation=1.15:gamma=0.98',
                      'note': 'bright saturated phone look', 'lifts_blacks': False},
    'vintage_print': {'chain': "curves=all='0/0.05 0.5/0.5 1/0.95',colorbalance=rs=0.03:bs=-0.03,"
                               'eq=saturation=0.85',
                      'note': 'faded print look - LIFTS BLACKS (owner rejected lifted blacks before)',
                      'lifts_blacks': True},
}


def grades(**extra):
    """List the named grades with their FFmpeg filter chains."""
    _no_extra(extra)
    rows = [{'name': k, 'chain': v['chain'], 'note': v['note'], 'lifts_blacks': v['lifts_blacks']}
            for k, v in GRADES.items()]
    return _pack('grades', {'count': len(rows), 'grades': rows},
                 ['chains use only FFmpeg curves / eq / colorbalance / colortemperature'],
                 ['looks are generic starting points, not matched to a camera or log profile',
                  'grading real footage needs the owner to request it (apply_grade requested_by_owner)'])


def grade_preview_filter(*, name=None, **extra):
    """Return the FFmpeg -vf chain for a named grade (no file touched)."""
    _no_extra(extra)
    name = _choice(name, set(GRADES), 'name')
    g = GRADES[name]
    return _pack('grade_preview_filter',
                 {'name': name, 'vf': g['chain'] + ',format=yuv420p',
                  'components': g['chain'].split(','), 'note': g['note'],
                  'lifts_blacks': g['lifts_blacks']},
                 ['append to an existing -vf with a comma; format=yuv420p keeps delivery format'],
                 ['preview by applying to a short copy; this op does not render'])


def _video_audio_codec(path):
    data = _ffprobe_json(path, 'stream=codec_type,codec_name')
    audio = [s for s in data.get('streams', []) if s.get('codec_type') == 'audio']
    return audio[0].get('codec_name') if audio else None


def apply_grade(*, source=None, name=None, output=None, approve_write=False,
                requested_by_owner=False, **extra):
    """Apply a named grade to real footage -> NEW MP4. Refused unless the owner asked."""
    _no_extra(extra)
    name = _choice(name, set(GRADES), 'name')
    if requested_by_owner is not True:
        raise PermissionError('owner rule: no filters on real footage unless the owner requests the '
                              'grade by name; pass requested_by_owner=True only in that case')
    _approved(approve_write)
    _tools()
    src = _path_like(source, 'source')
    meta = probe_source(src)
    if meta['width'] % 2 or meta['height'] % 2:
        raise ValueError('yuv420p delivery needs even source dimensions')
    target = _new_output(output, [meta['source']])
    acodec = _video_audio_codec(meta['source']) if meta['audio'] else None
    stage = _stage(target.parent, '.mp4', 'grade')
    try:
        cmd = ['ffmpeg', '-hide_banner', '-nostdin', '-v', 'error', '-y', '-i', meta['source'],
               '-map', '0:v:0', '-vf', GRADES[name]['chain'] + ',format=yuv420p',
               '-c:v', 'libx264', '-preset', 'medium', '-crf', '18', '-pix_fmt', 'yuv420p']
        if meta['audio']:
            cmd += ['-map', '0:a:0'] + (['-c:a', 'copy'] if acodec == 'aac'
                                        else ['-c:a', 'aac', '-b:a', '192k'])
        else:
            cmd += ['-an']
        cmd += ['-movflags', '+faststart', str(stage)]
        _run(cmd, max(180, int(meta['duration'] * 6)))
        qa = verify_video(stage, width=meta['width'], height=meta['height'],
                          expected_audio=meta['audio'])
        if abs(qa['duration'] - meta['duration']) > max(0.15, 2 / meta['fps']):
            raise RuntimeError('graded duration differs from the source')
        if meta['audio'] and qa['audio_codec'] != 'aac':
            raise RuntimeError('audio inside MP4 must be AAC')
        src_luma = _first_frame_luma(meta['source'])
        out_luma = _first_frame_luma(stage)
        if _is_black(out_luma) and not _is_black(src_luma):
            raise RuntimeError('grade made the first frame black; output not delivered')
        _copy_exclusive(stage, target)
    finally:
        _unlink(stage)
    result = {'status': 'graded_and_verified', 'output': str(target), 'grade': name,
              'vf': GRADES[name]['chain'], 'sha256': _sha256(target),
              'bytes': target.stat().st_size, 'audio': ('copied (AAC)' if acodec == 'aac' else
                                                        'encoded to AAC' if meta['audio'] else None),
              'first_frame_luma': {'source': src_luma, 'output': out_luma},
              'lifts_blacks': GRADES[name]['lifts_blacks'], 'qa': qa}
    return _pack('apply_grade', result,
                 ['the grade was requested by the owner (requested_by_owner=True)',
                  'video re-encoded libx264 CRF 18 yuv420p; frame rate and timing kept; '
                  'AAC audio copied, other audio encoded to AAC without time changes'],
                 ['generic look, not shot-matched', 'source must be <= 600 s and <= 3840x2160'])


_CUBE_KEYS = ('TITLE', 'LUT_3D_SIZE', 'LUT_1D_SIZE', 'DOMAIN_MIN', 'DOMAIN_MAX',
              'LUT_3D_INPUT_RANGE', 'LUT_1D_INPUT_RANGE')


def _cube_sample(table, n, dmin, dmax, rgb):
    """Trilinear lookup in a 3D LUT (red varies fastest)."""
    coords = []
    for c in range(3):
        span = (dmax[c] - dmin[c]) or 1.0
        x = (rgb[c] - dmin[c]) / span * (n - 1)
        coords.append(min(max(x, 0.0), n - 1))
    i0 = [int(math.floor(x)) for x in coords]
    i1 = [min(i + 1, n - 1) for i in i0]
    fr = [coords[c] - i0[c] for c in range(3)]
    out = [0.0, 0.0, 0.0]
    for dr in (0, 1):
        for dg in (0, 1):
            for db in (0, 1):
                w = ((fr[0] if dr else 1 - fr[0]) * (fr[1] if dg else 1 - fr[1])
                     * (fr[2] if db else 1 - fr[2]))
                if w == 0:
                    continue
                r = i1[0] if dr else i0[0]
                g = i1[1] if dg else i0[1]
                b = i1[2] if db else i0[2]
                v = table[r + g * n + b * n * n]
                for c in range(3):
                    out[c] += w * v[c]
    return [_r(v, 5) for v in out]


def lut_parse(*, text=None, **extra):
    """Parse .cube LUT text (data in a string) and summarise it."""
    _no_extra(extra)
    if not isinstance(text, str) or not text.strip() or len(text) > MAX_LUT_CHARS:
        raise ValueError(f'text must be non-empty .cube content of at most {MAX_LUT_CHARS} characters')
    title, size3, size1 = None, None, None
    dmin, dmax = [0.0, 0.0, 0.0], [1.0, 1.0, 1.0]
    table = []
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.split('#', 1)[0].strip()
        if not line:
            continue
        head = line.split(None, 1)[0].upper()
        if head == 'TITLE':
            m = re.match(r'TITLE\s+"?(.*?)"?\s*$', line, re.I)
            title = (m.group(1) if m else '')[:200]
            continue
        if head in _CUBE_KEYS:
            vals = line.split()[1:]
            try:
                if head == 'LUT_3D_SIZE':
                    size3 = int(vals[0])
                elif head == 'LUT_1D_SIZE':
                    size1 = int(vals[0])
                elif head == 'DOMAIN_MIN':
                    dmin = [float(v) for v in vals[:3]]
                elif head == 'DOMAIN_MAX':
                    dmax = [float(v) for v in vals[:3]]
                else:
                    lo, hi = float(vals[0]), float(vals[1])
                    dmin, dmax = [lo] * 3, [hi] * 3
            except (IndexError, ValueError) as exc:
                raise ValueError(f'line {lineno}: malformed {head}') from exc
            continue
        parts = line.split()
        if len(parts) != 3:
            raise ValueError(f'line {lineno}: expected three numbers')
        try:
            vals = [float(p) for p in parts]
        except ValueError as exc:
            raise ValueError(f'line {lineno}: expected three numbers') from exc
        if not all(math.isfinite(v) for v in vals):
            raise ValueError(f'line {lineno}: non-finite value')
        table.append(vals)
    if (size3 is None) == (size1 is None):
        raise ValueError('exactly one of LUT_3D_SIZE or LUT_1D_SIZE is required')
    if len(dmin) != 3 or len(dmax) != 3 or any(a >= b for a, b in zip(dmin, dmax)):
        raise ValueError('DOMAIN_MIN must be below DOMAIN_MAX on every channel')
    kind = '3d' if size3 is not None else '1d'
    n = size3 if size3 is not None else size1
    if kind == '3d' and not 2 <= n <= MAX_LUT_SIZE:
        raise ValueError(f'LUT_3D_SIZE must be 2..{MAX_LUT_SIZE}')
    if kind == '1d' and not 2 <= n <= 65536:
        raise ValueError('LUT_1D_SIZE must be 2..65536')
    expected = n ** 3 if kind == '3d' else n
    if len(table) != expected:
        raise ValueError(f'expected {expected} table rows, found {len(table)}')
    mins = [_r(min(row[c] for row in table), 5) for c in range(3)]
    maxs = [_r(max(row[c] for row in table), 5) for c in range(3)]
    result = {'kind': kind, 'size': n, 'title': title, 'domain_min': dmin, 'domain_max': dmax,
              'rows': len(table), 'output_min': mins, 'output_max': maxs}
    if kind == '3d':
        dev = 0.0
        for b in range(n):
            for g in range(n):
                for r in range(n):
                    row = table[r + g * n + b * n * n]
                    ident = (r / (n - 1), g / (n - 1), b / (n - 1))
                    ident = [dmin[c] + ident[c] * (dmax[c] - dmin[c]) for c in range(3)]
                    dev = max(dev, max(abs(row[c] - ident[c]) for c in range(3)))
        samples = {k: _cube_sample(table, n, dmin, dmax, v) for k, v in (
            ('black', (0, 0, 0)), ('mid_grey', (0.5, 0.5, 0.5)), ('white', (1, 1, 1)),
            ('red', (1, 0, 0)), ('green', (0, 1, 0)), ('blue', (0, 0, 1)),
            ('skin', (0.8, 0.6, 0.5)))}
        black = samples['black']
        result.update(max_identity_deviation=_r(dev, 5), samples=samples,
                      black_out_luma=_r(0.2126 * black[0] + 0.7152 * black[1] + 0.0722 * black[2], 5))
        result['lifts_blacks'] = result['black_out_luma'] > 0.02
    return _pack('lut_parse', result,
                 ['Adobe/Resolve .cube layout: red index varies fastest',
                  'samples use trilinear interpolation on 0..1 inputs'],
                 ['1D LUTs are summarised but not sampled', 'shaper LUTs / mixed 1D+3D files are refused'])


def lut_export(*, size=17, title='Red Rose look', lift=None, gamma=None, gain=None,
               saturation=1.0, **extra):
    """Export a .cube 3D LUT (as text) from lift/gamma/gain per channel and saturation."""
    _no_extra(extra)
    n = _int(size, 2, MAX_LUT_EXPORT_SIZE, 'size')
    if not isinstance(title, str) or len(title) > 120 or '"' in title or '\n' in title:
        raise ValueError('title must be a short single-line string without quotes')

    def triple(value, default, low, high, name):
        if value is None:
            return [default] * 3
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return [_num(value, low, high, name)] * 3
        if not isinstance(value, (list, tuple)) or len(value) != 3:
            raise ValueError(f'{name} must be a number or three numbers [r, g, b]')
        return [_num(v, low, high, name) for v in value]
    lift = triple(lift, 0.0, -0.2, 0.2, 'lift')
    gamma = triple(gamma, 1.0, 0.4, 2.5, 'gamma')
    gain = triple(gain, 1.0, 0.5, 1.6, 'gain')
    sat = _num(saturation, 0.0, 2.0, 'saturation')
    lines = [f'TITLE "{title}"', '# generated by Red Rose studio_v27 (lift/gamma/gain/saturation)',
             f'LUT_3D_SIZE {n}', 'DOMAIN_MIN 0.0 0.0 0.0', 'DOMAIN_MAX 1.0 1.0 1.0']
    for b in range(n):
        for g in range(n):
            for r in range(n):
                rgb = (r / (n - 1), g / (n - 1), b / (n - 1))
                out = []
                for c in range(3):
                    v = gain[c] * rgb[c] + lift[c] * (1 - rgb[c])
                    v = min(max(v, 0.0), 1.0) ** (1.0 / gamma[c])
                    out.append(v)
                y = 0.2126 * out[0] + 0.7152 * out[1] + 0.0722 * out[2]
                out = [min(max(y + (v - y) * sat, 0.0), 1.0) for v in out]
                lines.append(' '.join(f'{v:.6f}' for v in out))
    text = '\n'.join(lines) + '\n'
    return _pack('lut_export', {'size': n, 'title': title, 'rows': n ** 3, 'chars': len(text),
                                'lifts_blacks': any(v > 0.005 for v in lift), 'cube': text},
                 ['out = (gain*x + lift*(1-x)) ** (1/gamma) per channel, then saturation about Rec.709 luma',
                  'the LUT is returned as text; no file is written'],
                 [f'size <= {MAX_LUT_EXPORT_SIZE}', 'display-referred 0..1 domain only'])


# --------------------------------------------------------------------------- QA: delivery

def _faststart(path):
    """Return True if 'moov' precedes 'mdat' among top-level MP4 boxes, None if unknown."""
    order = []
    size_total = path.stat().st_size
    with path.open('rb') as fh:
        pos = 0
        for _ in range(4096):
            if pos + 8 > size_total:
                break
            fh.seek(pos)
            head = fh.read(8)
            if len(head) < 8:
                break
            size = int.from_bytes(head[:4], 'big')
            kind = head[4:8].decode('latin-1')
            header = 8
            if size == 1:
                big = fh.read(8)
                if len(big) < 8:
                    break
                size, header = int.from_bytes(big, 'big'), 16
            elif size == 0:
                size = size_total - pos
            if size < header:
                return None
            if kind in ('moov', 'mdat'):
                order.append(kind)
                if len(set(order)) == 2:
                    break
            pos += size
    if 'moov' not in order or 'mdat' not in order:
        return None
    return order.index('moov') < order.index('mdat')


def delivery_check(*, path=None, **extra):
    """Delivery QA: codecs, pixel format, dims, faststart, loudness, black/frozen, first frame."""
    _no_extra(extra)
    _tools()
    p = _local_file(path, 'path', DELIVERY_INPUTS)
    data = _ffprobe_json(p, 'format=duration:stream=index,codec_type,codec_name,pix_fmt,width,'
                            'height,avg_frame_rate,sample_rate,channels')
    streams = data.get('streams', [])
    videos = [s for s in streams if s.get('codec_type') == 'video'
              and s.get('codec_name') not in ('mjpeg', 'png')]
    audios = [s for s in streams if s.get('codec_type') == 'audio']
    duration = _f(data.get('format', {}).get('duration'))
    if not videos:
        raise ValueError('no video stream')
    if duration is None or not 0 < duration <= MAX_SECONDS:
        raise ValueError(f'duration must be between 0 and {MAX_SECONDS:g} s')
    v = videos[0]
    checks = []

    def add(name, level, detail):
        checks.append({'check': name, 'level': level, 'detail': detail})
    add('video_codec_h264', 'pass' if v.get('codec_name') == 'h264' else 'fail', v.get('codec_name'))
    add('pix_fmt_yuv420p', 'pass' if v.get('pix_fmt') == 'yuv420p' else 'fail', v.get('pix_fmt'))
    w, h = int(v.get('width') or 0), int(v.get('height') or 0)
    add('even_dimensions', 'pass' if w and h and not w % 2 and not h % 2 else 'fail', f'{w}x{h}')
    add('single_video_stream', 'pass' if len(videos) == 1 else 'fail', len(videos))
    fs = _faststart(p)
    add('faststart_moov_first', 'pass' if fs else ('warn' if fs is None else 'fail'),
        {True: 'moov before mdat', False: 'moov after mdat', None: 'not determined'}[fs])
    try:
        fps = float(Fraction(v.get('avg_frame_rate') or '0/1'))
    except (ValueError, ZeroDivisionError):
        fps = 0.0
    loud = None
    if audios:
        a = audios[0]
        add('audio_codec_aac', 'pass' if a.get('codec_name') == 'aac' else 'fail', a.get('codec_name'))
        loud = _ebur128(p, timeout=600)
        tp = loud['true_peak_dbtp']
        add('true_peak_le_-1dBTP', 'pass' if tp is not None and tp <= -1.0 else 'warn', tp)
        il = loud['integrated_lufs']
        add('integrated_loudness_-16+/-2', 'pass' if il is not None and -18.0 <= il <= -14.0
            else 'warn', il)
    else:
        add('audio_present', 'warn', 'no audio stream')
    err = _run(['ffmpeg', '-hide_banner', '-nostdin', '-nostats', '-v', 'info', '-i', str(p),
                '-map', '0:v:0', '-an', '-vf',
                'blackdetect=d=0.1:pix_th=0.10,freezedetect=n=-60dB:d=2',
                '-f', 'null', '-'], 900).stderr.decode('utf-8', 'replace')
    blacks = [{'start': _r(float(a), 3), 'end': _r(float(b), 3)} for a, b in
              re.findall(r'black_start:\s*([\d.]+)\s+black_end:\s*([\d.]+)', err)]
    fstarts = [float(x) for x in re.findall(r'freeze_start:\s*([\d.]+)', err)]
    fends = [float(x) for x in re.findall(r'freeze_end:\s*([\d.]+)', err)]
    freezes = [{'start': _r(s, 3), 'end': _r(fends[i] if i < len(fends) else duration, 3)}
               for i, s in enumerate(fstarts)]
    starts_black = any(b['start'] is not None and b['start'] <= 0.05 for b in blacks)
    add('no_black_at_start', 'fail' if starts_black else 'pass', blacks[:1] if starts_black else None)
    add('black_stretches', 'warn' if blacks else 'pass', blacks[:20])
    add('frozen_stretches', 'warn' if freezes else 'pass', freezes[:20])
    luma = _first_frame_luma(p)
    add('first_frame_not_black', 'fail' if _is_black(luma) else 'pass', luma)
    try:
        qa = verify_video(p)
        add('full_decode', 'pass', 'ffmpeg -xerror decode ok')
    except Exception as exc:  # report, do not crash the QA
        qa = None
        add('full_decode', 'fail', str(exc)[:300])
    fails = [c['check'] for c in checks if c['level'] == 'fail']
    warns = [c['check'] for c in checks if c['level'] == 'warn']
    result = {'path': str(p), 'passed': not fails, 'fails': fails, 'warnings': warns,
              'checks': checks, 'duration': _r(duration, 4), 'fps': _r(fps, 4),
              'width': w, 'height': h, 'loudness': loud, 'black': blacks, 'frozen': freezes,
              'first_frame_luma': luma, 'sha256': qa['sha256'] if qa else _sha256(p)}
    return _pack('delivery_check', result,
                 ['black: blackdetect pix_th=0.10 for >= 0.1 s; frozen: freezedetect -60 dB for >= 2 s',
                  'loudness target -16 LUFS +/-2 and true peak <= -1 dBTP are warnings, not failures',
                  'first frame black = mean luma < 16 and max < 40'],
                 ['read-only; the file is decoded fully (slow for long 4K files)',
                  'still graphics held on purpose are reported as frozen stretches'])


# --------------------------------------------------------------------------- example

_EXAMPLE_KEYS = {'typemotion_v27': ('kinetic', 'type', 'text'),
                 'motion_v27': ('transition', 'wipe', 'slide'),
                 'graphics_v27': ('route', 'map', 'path')}
_EXAMPLE_DEFAULTS = {'typemotion_v27': 'kinetic_text', 'motion_v27': 'transition',
                     'graphics_v27': 'route_map'}


def _example_op(module, notes):
    try:
        ops = sorted(_module_ops(module))
    except ValueError as exc:
        notes.append(f'{module}: {exc}; used the default op name')
        return _EXAMPLE_DEFAULTS[module], None
    for key in _EXAMPLE_KEYS[module]:
        for op in ops:
            if key in op.lower():
                break
        else:
            continue
        break
    else:
        op = _EXAMPLE_DEFAULTS[module]
        notes.append(f'{module}: no op matching {_EXAMPLE_KEYS[module]}; used {op!r}')
    params = None
    mod = _MODULE_CACHE.get(module)
    for attr in ('EXAMPLES', 'DEFAULTS', 'EXAMPLE_PARAMS'):
        table = getattr(mod, attr, None) if mod else None
        if isinstance(table, dict) and isinstance(table.get(op), dict):
            try:
                params = json.loads(json.dumps(table[op], ensure_ascii=False))
            except (TypeError, ValueError):
                params = None
            if params is not None:
                break
    return op, params


_EXAMPLE_LAYERS = (
    {'module': 'motion', 'op': 'camera', 'z': 0, 'opacity': 1.0, 'start': 0.0, 'end': 4.0,
     'params': {'move': 'push_in',
                'svg': '<circle cx="540" cy="960" r="430" fill="#7a1a30"/>'}},
    {'module': 'typemotion', 'op': 'kinetic_text', 'z': 2, 'opacity': 1.0, 'start': 0.0,
     'end': 2.4, 'params': {'text': 'الوردة الحمراء', 'style': 'fade_up'}},
    {'module': 'graphics', 'op': 'route_map', 'z': 1, 'opacity': 1.0, 'start': 2.0, 'end': 4.0,
     'params': {'stops': [['القاهرة', 30.04, 31.24], ['الإسكندرية', 31.2, 29.92]],
                'duration': 2.0, 'show_note': False}},
)


def example_timeline(**extra):
    """A small Arabic example (1080x1920, 4 s, 24 fps): camera push-in, kinetic title, route map.

    Every layer is dry-run before it is returned; a layer whose sibling module
    rejects it is dropped and named in notes, so the spec always validates."""
    _no_extra(extra)
    notes = []
    base = {'width': 1080, 'height': 1920, 'fps': 24, 'duration': 4.0,
            'background': '#5a1020', 'audio': []}
    kept = []
    for raw in _EXAMPLE_LAYERS:
        trial = dict(base, layers=[copy.deepcopy(raw)])
        norm, errors, _ = _normalize(trial, probe_audio=False)
        if not errors:
            errors = [e['error'] for e in _dry_run(norm) if e['error']]
        if errors:
            notes.append(f'dropped {raw["module"]}.{raw["op"]}: {errors[0][:300]}')
        else:
            kept.append(copy.deepcopy(raw))
    spec = dict(base, layers=kept)
    return _pack('example_timeline', {'spec': spec, 'notes': notes,
                                      'layers_kept': len(kept),
                                      'layers_offered': len(_EXAMPLE_LAYERS)},
                 ['words "الوردة الحمراء" and the city names are placeholders: replace them with the '
                  "owner's own words before rendering (no descriptive text is invented)",
                  'only layers that pass a dry-run of their sibling module are returned',
                  'a text layer without duration animates over its own start..end span',
                  'background #5a1020 (luma ~33) keeps the first frame from being black'],
                 ['run validate_timeline before render_timeline; audio list is empty (add voice/music clips)'])


# --------------------------------------------------------------------------- one-call title frame

_TITLE_PLATFORMS = {'reel': (1080, 1920), 'wide': (1920, 1080)}
_TITLE_STAGGER = {  # style -> (reveal fraction of duration, window fraction, window max s)
    'stagger_words': (0.4, 0.5, 0.35), 'bounce_words': (0.65, 0.45, 0.8),
    'fade_up': (0.6, 0.4, 0.6), 'slide_in': (0.6, 0.4, 0.6), 'pop_scale': (0.6, 0.4, 0.6),
    'blur_in': (0.6, 0.4, 0.6), 'glitch_words': (0.6, 0.4, 0.6),
    'underline_draw': (0.35, 0.5, 0.4)}
MAX_TITLE_CHARS = 300


def _word_timings(words, style, duration):
    """Per-word appear windows [start, end] in seconds (stagger model of the text styles)."""
    n = len(words)
    if style == 'word_typewriter':
        step = 0.7 * duration / n
        return [{'word': w, 'start': _r(i * step, 4), 'end': _r(i * step + max(step * 0.9, 1e-3), 4)}
                for i, w in enumerate(words)], 'typewriter_step'
    if style in _TITLE_STAGGER:
        frac, wfrac, wmax = _TITLE_STAGGER[style]
        reveal = frac * duration
        if n <= 1:
            win = max(1e-3, min(reveal, wmax))
            starts = [0.0]
        else:
            win = max(min(wmax, max(0.12, reveal * wfrac), reveal), 1e-3)
            step = max(0.0, (reveal - win) / (n - 1))
            starts = [i * step for i in range(n)]
        return [{'word': w, 'start': _r(s, 4), 'end': _r(s + win, 4)}
                for w, s in zip(words, starts)], 'stagger'
    return [{'word': w, 'start': 0.0, 'end': _r(duration, 4)} for w in words], 'whole_text'


def title_frame(*, text=None, style='fade_up', at='mid', duration=2.0, platform='reel',
                width=None, height=None, background=None, rasterize=True, **extra):
    """One call: a complete title frame (SVG + optional PNG) of `text` animated with `style`.

    at: 'mid' (every word has fully appeared, before the exit) or seconds in [0, duration].
    platform 'reel' = 1080x1920, 'wide' = 1920x1080; width/height override it.
    Returns {svg, png_base64?, width, height, t, word_timings, shaping, warnings, qa}."""
    _no_extra(extra)
    if not isinstance(text, str) or not text.strip():
        raise ValueError('text is required (the owner\'s own words; nothing is invented)')
    if len(text) > MAX_TITLE_CHARS:
        raise ValueError(f'text must be at most {MAX_TITLE_CHARS} characters')
    if not isinstance(style, str) or not style.strip():
        raise ValueError('style must be a text style name (typemotion_v27 STYLES)')
    duration = _num(duration, 0.2, 60.0, 'duration')
    platform = _choice(platform, set(_TITLE_PLATFORMS), 'platform')
    w, h = _TITLE_PLATFORMS[platform]
    if width is not None:
        w = _int(width, 64, MAX_LONG_SIDE, 'width')
    if height is not None:
        h = _int(height, 64, MAX_LONG_SIDE, 'height')
    _bool(rasterize, 'rasterize')
    words = ' '.join(text.split()).split(' ')
    timings, model = _word_timings(words, style, duration)
    if at == 'mid':
        last_end = max(item['end'] for item in timings)
        exit_start = duration - min(0.35, duration / 2)
        t = min(max(duration / 2.0, last_end + 1e-3), max(0.0, exit_start - 1e-3))
        if t < last_end:
            t = last_end
    elif isinstance(at, str):
        raise ValueError("at must be 'mid' or a number of seconds")
    else:
        t = _num(at, 0.0, duration, 'at')
    spec = {'width': w, 'height': h, 'fps': 30, 'duration': duration,
            'background': background if background is not None else '#5a1020',
            'layers': [{'module': 'typemotion', 'op': 'kinetic_text', 'start': 0.0,
                        'end': duration, 'params': {'text': text, 'style': style,
                                                    'duration': duration}}],
            'audio': []}
    norm, errors, warnings = _normalize(spec, probe_audio=False)
    if not errors:
        errors = [e['error'] for e in _dry_run(norm) if e['error']]
    if errors:
        raise ValueError('title_frame: ' + '; '.join(errors[:4]))
    tt = min(t, norm['duration'] - 1e-6)
    svg, active = _compose(norm, tt)
    _check_xml(svg)
    visible = [item['word'] for item in timings if item['start'] <= t]
    result = {'svg': svg, 'width': w, 'height': h, 't': _r(t, 6), 'duration': duration,
              'style': style, 'platform': platform, 'background': norm['background'],
              'word_timings': timings, 'timing_model': model, 'words_started_at_t': visible,
              'warnings': list(warnings)}
    if rasterize:
        _raster_into(result, svg, norm, w)
    else:
        shaped, rep = _shape(svg)
        result['shaping'] = _shaping_summary([rep])
        result['warnings'] += [x for x in result['shaping']['warnings'] if x not in result['warnings']]
        result['qa'] = {'passed': result['shaping']['ok'], 'text_shaping_ok': result['shaping']['ok'],
                        'black': None}
    return _pack('title_frame', result,
                 ['the frame is a one-layer timeline: typemotion kinetic_text from 0 to duration',
                  "at='mid' picks a time after every word's appear window and before the exit fade",
                  'word_timings follow the stagger model of the text styles (computed here)',
                  'svg keeps logical text; the PNG is rasterised from an Arabic-shaped copy'],
                 ['PNG is in memory (base64); no file is written',
                  'word_timings are a model of the style, not measured from pixels'])


# --------------------------------------------------------------------------- dispatcher

OPS = {
    'validate_timeline': validate_timeline, 'preview_frame': preview_frame,
    'render_timeline': render_timeline, 'plan_mix': plan_mix, 'grades': grades,
    'grade_preview_filter': grade_preview_filter, 'apply_grade': apply_grade,
    'lut_parse': lut_parse, 'lut_export': lut_export, 'delivery_check': delivery_check,
    'example_timeline': example_timeline, 'title_frame': title_frame,
}

EFFECTS = {
    'validate_timeline': 'read', 'preview_frame': 'read', 'render_timeline': 'write',
    'plan_mix': 'read', 'grades': 'read', 'grade_preview_filter': 'read',
    'apply_grade': 'write', 'lut_parse': 'read', 'lut_export': 'read',
    'delivery_check': 'read', 'example_timeline': 'read', 'title_frame': 'read',
}


def run(op, params=None):
    """Validate and dispatch: run('grades', {}) -> {'op','result','assumptions','limits'}."""
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
