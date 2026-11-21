"""Red Rose V28: bridges to outside programs (Blender/Cycles, After Effects, NLEs,
Remotion, local voice).

Original code re-implementing the ideas of the legacy BLENDER, CYCLES, CREATE,
ADOBE, NLE, REMOTION, VOICE, LOCAL and GRAPH families. Nothing legacy is imported.

Standard library + verify_media.verify_video. Same interface as physics_v20:
OPS, EFFECTS ({op: 'read'|'write'}), run(op, params) returning
{'op', 'result', 'assumptions', 'limits'}, strict ValueError validation and
rejection of unknown parameters.

Safety rules honoured by every op:
* outside programs are only the allow-list {blender, ffmpeg, ffprobe, piper,
  espeak-ng, espeak}, located with shutil.which and started only as
  subprocess.run([...list...], capture_output=True, timeout=...) - never a
  shell, os.system or popen. On Windows only real .exe files are started (a
  .bat/.cmd launcher would be run through cmd.exe, so it is refused);
* a missing program is reported as status 'not_installed' - nothing is faked;
* no network, no exec/eval, no printing;
* generated Blender/ExtendScript/TypeScript code never contains owner text
  spliced into source: every owner value travels inside one JSON literal
  (json.dumps), which is valid Python/JS/TS;
* files are written only by 'write' ops, only with approve_write=True, only into
  a caller-supplied existing work_dir, and only as NEW files (exclusive create;
  an existing file is never overwritten);
* speech text is never invented: tts_local speaks only the owner's text.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import tempfile
import unicodedata
import wave
from fractions import Fraction
from pathlib import Path
from xml.sax.saxutils import escape as _xml_escape, quoteattr as _xml_attr

from verify_media import verify_video

MAX_PARAMS = 32
MAX_SECONDS = 600.0
MAX_SPEC_CHARS = 2_000_000
MAX_GLTF_CHARS = 50_000_000
MAX_SOURCE_BYTES = 2_000_000_000
MAX_FRAMES = 3000
MAX_TTS_CHARS = 5000
MAX_LOG = 4000
ALLOWED_PROGRAMS = ('blender', 'ffmpeg', 'ffprobe', 'piper', 'espeak-ng', 'espeak')
_VERSION_ARGS = {'blender': ['--version'], 'ffmpeg': ['-version'], 'ffprobe': ['-version'],
                 'piper': ['--version'], 'espeak-ng': ['--version'], 'espeak': ['--version']}
_URL = re.compile(r'^[A-Za-z][A-Za-z0-9+.\-]*:(//|[^\\/])')
_ARABIC = re.compile('[֐-ࣿיִ-﷿ﹰ-﻿]')
_HEX = re.compile(r'^#([0-9A-Fa-f]{3}|[0-9A-Fa-f]{6})$')
_BASENAME = re.compile(r'^[\w][\w .\-]{0,79}$')
_WIN_RESERVED = {'CON', 'PRN', 'AUX', 'NUL', *(f'COM{i}' for i in range(1, 10)),
                 *(f'LPT{i}' for i in range(1, 10))}
RESULT_MARK = 'RED_ROSE_RESULT '

TOPICS = {
    'BLENDER': 'blender_script / blender_render (bpy scene from glTF or primitives)',
    'CYCLES': 'blender_script engine="cycles" (CPU or GPU) / "eevee"',
    'CREATE': 'blender_render -> PNG frames or verified H.264 MP4',
    'ADOBE': 'ae_jsx (After Effects ExtendScript, run by the owner)',
    'NLE': 'nle_export (CMX3600 EDL + FCPXML 1.9)',
    'REMOTION': 'remotion_project (file map, nothing installed)',
    'VOICE': 'tts_local (piper / espeak-ng, owner text only, WAV + AAC M4A)',
    'LOCAL': 'detect (allow-listed local programs and versions)',
    'GRAPH': 'studio_v27 timeline -> AE / NLE / Remotion graphs',
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


def _bool(value, name):
    if not isinstance(value, bool):
        raise ValueError(f'{name} must be true or false')
    return value


def _choice(value, options, name):
    if not isinstance(value, str) or value not in options:
        raise ValueError(f'{name} must be one of {sorted(options)}')
    return value


def _vec(value, size, name, low=-1e4, high=1e4):
    if not isinstance(value, (list, tuple)) or len(value) != size:
        raise ValueError(f'{name} must be a list of {size} numbers')
    return [_num(v, low, high, f'{name}[{i}]') for i, v in enumerate(value)]


def _clean_text(value, name, *, max_len=500, required=True, multiline=True):
    """Owner text: drop control characters (keep newline/tab) and lone surrogates."""
    if value is None and not required:
        return ''
    if not isinstance(value, str) or len(value) > max_len:
        raise ValueError(f'{name} must be a string of at most {max_len} characters')
    keep = []
    for ch in value:
        if '\ud800' <= ch <= '\udfff' or ch in '￾￿':
            continue
        if ch in '\n\t':
            keep.append(ch if multiline else ' ')
            continue
        if unicodedata.category(ch) == 'Cc':
            continue
        keep.append(ch)
    value = ''.join(keep).strip()
    if required and not value:
        raise ValueError(f'{name} must not be empty')
    return value


def _path_like(value, name):
    if value is None or (isinstance(value, str) and not value.strip()):
        raise ValueError(f'{name} is required')
    if isinstance(value, bytes) or not isinstance(value, (str, os.PathLike)):
        raise ValueError(f'{name} must be a local path')
    raw = os.fspath(value)
    if not isinstance(raw, str) or '\x00' in raw:
        raise ValueError(f'{name} must be a local path')
    stripped = raw.strip()
    if _URL.match(stripped) and not re.match(r'^[A-Za-z]:[\\/]', stripped):
        raise ValueError(f'{name} must be a local path; URLs are not accepted')
    if stripped.startswith(('\\\\', '//')):
        raise ValueError(f'{name} must be a local path; network paths are not accepted')
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


def _work_dir(value):
    path = _path_like(value, 'work_dir')
    if not path.is_dir():
        raise ValueError('work_dir must be an existing folder')
    return path


def _basename(value):
    if not isinstance(value, str) or not _BASENAME.match(value):
        raise ValueError('basename must be 1-80 letters/digits/space/_/./- with no path separators')
    if value.endswith(('.', ' ')) or '..' in value:
        raise ValueError('basename must not end with a dot/space or contain ".."')
    if value.split('.')[0].upper() in _WIN_RESERVED:
        raise ValueError('basename is a reserved Windows device name')
    return value


def _new_target(work_dir, name):
    path = work_dir / name
    if path.parent != work_dir:
        raise ValueError('target must stay inside work_dir')
    if path.exists() or path.is_symlink():
        raise ValueError(f'{path.name} already exists in work_dir; refusing to overwrite')
    return path


def _approved(approve_write):
    if approve_write is not True:
        raise PermissionError('this op runs a program or writes a file: pass approve_write=True '
                              'after the owner approves')


def _hex(value, name):
    if not isinstance(value, str) or not _HEX.match(value.strip()):
        raise ValueError(f'{name} must be a colour like "#rrggbb"')
    h = value.strip()[1:]
    if len(h) == 3:
        h = ''.join(c * 2 for c in h)
    rgb = [int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]
    return [round(c, 6) for c in rgb], '#' + h.lower()


def _pack(op, result, assumptions, limits):
    return {'op': op, 'result': result, 'assumptions': list(assumptions),
            'limits': list(limits)}


def _sha256(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def _json_literal(obj):
    """A JSON text usable verbatim as a Python/JS/TS literal (ASCII only, no NaN)."""
    return json.dumps(obj, ensure_ascii=True, allow_nan=False, sort_keys=True)


def _write_new_text(path, text):
    with path.open('x', encoding='utf-8', newline='\n') as fh:
        fh.write(text)
    return {'path': str(path), 'bytes': path.stat().st_size, 'sha256': _sha256(path)}


def _copy_new(src, dst):
    created = False
    try:
        with dst.open('xb') as out, src.open('rb') as inp:
            created = True
            shutil.copyfileobj(inp, out, 1024 * 1024)
    except FileExistsError as exc:
        raise ValueError(f'{dst.name} appeared while working; refusing to overwrite') from exc
    except BaseException:
        if created:
            try:
                dst.unlink()
            except OSError:
                pass
        raise


def _unlink(path):
    if path is None:
        return
    try:
        Path(path).unlink()
    except OSError:
        pass


# --------------------------------------------------------------------------- programs

def _exe(name):
    """Return (path or None, status) for an allow-listed program."""
    if name not in ALLOWED_PROGRAMS:
        raise ValueError(f'program {name!r} is not in the allow-list {list(ALLOWED_PROGRAMS)}')
    found = shutil.which(name)
    if not found:
        return None, 'not_installed'
    path = Path(found)
    if os.name == 'nt' and path.suffix.lower() != '.exe':
        return None, 'launcher_refused'
    return str(path), 'installed'


def _tail(data, limit=MAX_LOG):
    if data is None:
        return ''
    text = data.decode('utf-8', 'replace') if isinstance(data, bytes) else str(data)
    text = text.replace('\r\n', '\n').strip()
    return text[-limit:]


def _run(argv, timeout, *, input_bytes=None):
    """subprocess.run with a list argv, captured output and a timeout.

    Returns (CompletedProcess or None, error text or None)."""
    kwargs = {'capture_output': True, 'timeout': timeout}
    if input_bytes is None:
        kwargs['stdin'] = subprocess.DEVNULL
    else:
        kwargs['input'] = input_bytes
    try:
        done = subprocess.run(argv, **kwargs)
    except subprocess.TimeoutExpired:
        return None, f'{Path(argv[0]).name} timed out after {timeout} s'
    except OSError as exc:
        return None, f'{Path(argv[0]).name} could not start: {exc}'
    if done.returncode != 0:
        return done, (f'{Path(argv[0]).name} exited with code {done.returncode}: '
                      + _tail(done.stderr, 800))
    return done, None


def _not_installed(op, programs, assumptions=(), limits=()):
    status = {p: _exe(p)[1] for p in programs}
    return _pack(op, {'status': 'not_installed', 'programs': status, 'files': [],
                      'message': 'required program(s) not available: ' + ', '.join(
                          f'{p} ({s})' for p, s in status.items() if s != 'installed')},
                 list(assumptions) + ['nothing was run and nothing was written'], list(limits))


def detect(*, programs=None, versions=True, timeout_s=30, **extra):
    """Which allow-listed programs exist on PATH and their (bounded) version banner.

    Only the version flag is run (-version for FFmpeg/FFprobe, --version otherwise)."""
    _no_extra(extra)
    if programs is None:
        programs = list(ALLOWED_PROGRAMS)
    if not isinstance(programs, (list, tuple)) or not 1 <= len(programs) <= len(ALLOWED_PROGRAMS):
        raise ValueError('programs must be a non-empty list of allow-listed names')
    names = []
    for p in programs:
        _choice(p, set(ALLOWED_PROGRAMS), 'programs[]')
        if p not in names:
            names.append(p)
    versions = _bool(versions, 'versions')
    timeout_s = _int(timeout_s, 1, 120, 'timeout_s')
    found = {}
    for name in names:
        path, status = _exe(name)
        item = {'status': status, 'path': path}
        if status == 'launcher_refused':
            item['path'] = shutil.which(name)
            item['note'] = 'found a launcher script, not an .exe; it is never started'
        if path and versions:
            done, err = _run([path] + _VERSION_ARGS[name], timeout_s)
            out = ''
            if done is not None:
                out = _tail(done.stdout, 2000) or _tail(done.stderr, 2000)
            lines = [ln.strip() for ln in out.splitlines() if ln.strip()][:3]
            item['version'] = ' | '.join(lines)[:300] or None
            if err:
                item['version_error'] = err[:300]
        found[name] = item
    return _pack('detect', {'programs': found,
                            'installed': [n for n in names if found[n]['status'] == 'installed']},
                 ['programs are looked up with shutil.which on the current PATH only',
                  'the version banner is the first lines of the program output, truncated'],
                 ['allow-list: ' + ', '.join(ALLOWED_PROGRAMS),
                  'on Windows only .exe files are started (.bat/.cmd launchers are refused)'])


# --------------------------------------------------------------------------- Blender

_PRIM_TYPES = {'cube', 'uv_sphere', 'cylinder', 'cone', 'plane', 'torus'}
_PRIM_KEYS = {'type', 'name', 'size', 'location', 'rotation_deg', 'scale', 'color',
              'metallic', 'roughness', 'smooth'}
_LIGHT_TYPES = {'sun': 'SUN', 'point': 'POINT', 'area': 'AREA', 'spot': 'SPOT'}
_LIGHT_KEYS = {'type', 'name', 'location', 'target', 'energy', 'color', 'size'}
_CAM_KEYS = {'location', 'target', 'lens_mm', 'direction', 'turntable', 'turns'}
_BLENDER_KEYS = {'gltf', 'gltf_path', 'primitives', 'engine', 'samples', 'cycles_device',
                 'width', 'height', 'fps', 'frame_start', 'frame_end', 'camera', 'lights',
                 'world_color', 'world_strength', 'output'}


def _default_primitives():
    return [
        {'type': 'plane', 'name': 'ground', 'size': 6.0, 'location': [0.0, 0.0, 0.0],
         'color': [0.55, 0.52, 0.5, 1.0], 'roughness': 0.8},
        {'type': 'cube', 'name': 'block', 'size': 1.0, 'location': [-0.7, 0.0, 0.5],
         'rotation_deg': [0.0, 0.0, 20.0], 'color': [0.55, 0.06, 0.12, 1.0], 'roughness': 0.4},
        {'type': 'uv_sphere', 'name': 'ball', 'size': 0.9, 'location': [0.8, 0.2, 0.45],
         'color': [0.85, 0.7, 0.3, 1.0], 'metallic': 1.0, 'roughness': 0.25},
    ]


def _primitive(raw, i):
    where = f'primitives[{i}]'
    if not isinstance(raw, dict):
        raise ValueError(f'{where} must be a dict')
    unknown = set(raw) - _PRIM_KEYS
    if unknown:
        raise ValueError(f'{where}: unknown key(s) {sorted(unknown)}')
    kind = _choice(raw.get('type'), _PRIM_TYPES, f'{where}.type')
    name = _clean_text(raw.get('name', f'{kind}_{i}'), f'{where}.name', max_len=60,
                       multiline=False)
    color = raw.get('color', [0.8, 0.8, 0.8, 1.0])
    if isinstance(color, (list, tuple)) and len(color) == 3:
        color = list(color) + [1.0]
    return {
        'type': kind, 'name': name,
        'size': _num(raw.get('size', 1.0), 0.001, 1000.0, f'{where}.size'),
        'location': _vec(raw.get('location', [0.0, 0.0, 0.0]), 3, f'{where}.location'),
        'rotation_deg': _vec(raw.get('rotation_deg', [0.0, 0.0, 0.0]), 3,
                             f'{where}.rotation_deg', -720.0, 720.0),
        'scale': _vec(raw.get('scale', [1.0, 1.0, 1.0]), 3, f'{where}.scale', 0.001, 1000.0),
        'color': _vec(color, 4, f'{where}.color', 0.0, 1.0),
        'metallic': _num(raw.get('metallic', 0.0), 0.0, 1.0, f'{where}.metallic'),
        'roughness': _num(raw.get('roughness', 0.5), 0.0, 1.0, f'{where}.roughness'),
        'smooth': _bool(raw.get('smooth', kind in ('uv_sphere', 'cylinder', 'cone', 'torus')),
                        f'{where}.smooth'),
    }


def _light(raw, i):
    where = f'lights[{i}]'
    if not isinstance(raw, dict):
        raise ValueError(f'{where} must be a dict')
    unknown = set(raw) - _LIGHT_KEYS
    if unknown:
        raise ValueError(f'{where}: unknown key(s) {sorted(unknown)}')
    kind = _LIGHT_TYPES[_choice(raw.get('type', 'area'), set(_LIGHT_TYPES), f'{where}.type')]
    target = raw.get('target')
    return {
        'type': kind,
        'name': _clean_text(raw.get('name', f'light_{i}'), f'{where}.name', max_len=60,
                            multiline=False),
        'location': _vec(raw.get('location'), 3, f'{where}.location'),
        'target': None if target is None else _vec(target, 3, f'{where}.target'),
        'energy': _num(raw.get('energy', 3.0 if kind == 'SUN' else 1000.0), 0.0, 1e6,
                       f'{where}.energy'),
        'color': _vec(raw.get('color', [1.0, 1.0, 1.0]), 3, f'{where}.color', 0.0, 1.0),
        'size': _num(raw.get('size', 1.0), 0.0, 100.0, f'{where}.size'),
    }


def _camera(raw):
    raw = {} if raw is None else raw
    if not isinstance(raw, dict):
        raise ValueError('camera must be a dict')
    unknown = set(raw) - _CAM_KEYS
    if unknown:
        raise ValueError(f'camera: unknown key(s) {sorted(unknown)}')
    loc, target = raw.get('location'), raw.get('target')
    direction = _vec(raw.get('direction', [1.0, -1.2, 0.7]), 3, 'camera.direction')
    if math.sqrt(sum(c * c for c in direction)) < 1e-6:
        raise ValueError('camera.direction must not be the zero vector')
    turns = _int(raw.get('turns', 1), -4, 4, 'camera.turns')
    if turns == 0:
        raise ValueError('camera.turns must not be 0')
    return {
        'location': None if loc is None else _vec(loc, 3, 'camera.location'),
        'target': None if target is None else _vec(target, 3, 'camera.target'),
        'lens_mm': _num(raw.get('lens_mm', 50.0), 8.0, 300.0, 'camera.lens_mm'),
        'direction': direction,
        'turntable': _bool(raw.get('turntable', False), 'camera.turntable'),
        'turns': turns,
    }


def _gltf_text(gltf):
    if isinstance(gltf, dict):
        try:
            text = json.dumps(gltf, allow_nan=False, separators=(',', ':'))
        except (TypeError, ValueError) as exc:
            raise ValueError(f'gltf must be JSON-serialisable: {exc}') from exc
    elif isinstance(gltf, str):
        text = gltf
    else:
        raise ValueError('gltf must be a glTF 2.0 dict or its JSON text (modeling3d_v23 export_mesh)')
    if len(text) > MAX_GLTF_CHARS:
        raise ValueError(f'gltf must be at most {MAX_GLTF_CHARS} characters')
    try:
        data = json.loads(text)
    except ValueError as exc:
        raise ValueError(f'gltf is not valid JSON: {exc}') from exc
    if not isinstance(data, dict) or not str(data.get('asset', {}).get('version', '')).startswith('2.'):
        raise ValueError('gltf must be a glTF 2.x document (asset.version "2.0")')
    for key in ('buffers', 'images'):
        for i, item in enumerate(data.get(key, []) or []):
            uri = item.get('uri') if isinstance(item, dict) else None
            if uri is not None and not (isinstance(uri, str) and uri.startswith('data:')):
                raise ValueError(f'gltf {key}[{i}] must be an embedded data: URI '
                                 '(use gltf_path for files with external resources)')
    return text


def _blender_cfg(params):
    p = dict(params)
    unknown = set(p) - _BLENDER_KEYS
    if unknown:
        raise ValueError('unknown parameter(s): ' + ', '.join(sorted(unknown)))
    notes = []
    gltf, gltf_path, prims = p.get('gltf'), p.get('gltf_path'), p.get('primitives')
    if gltf is not None and gltf_path is not None:
        raise ValueError('give gltf or gltf_path, not both')
    gltf_text = _gltf_text(gltf) if gltf is not None else None
    gltf_file = (str(_local_file(gltf_path, 'gltf_path', {'.gltf', '.glb'}))
                 if gltf_path is not None else None)
    if prims is None and gltf_text is None and gltf_file is None:
        prims = _default_primitives()
        notes.append('no gltf/primitives given: a small demo scene (ground, block, ball) is used')
    if prims is None:
        prims = []
    if not isinstance(prims, list) or len(prims) > 100:
        raise ValueError('primitives must be a list of at most 100 dicts')
    prims = [_primitive(raw, i) for i, raw in enumerate(prims)]
    engine = _choice(p.get('engine', 'cycles'), {'cycles', 'eevee'}, 'engine')
    width = _int(p.get('width', 1280), 16, 7680, 'width')
    height = _int(p.get('height', 720), 16, 7680, 'height')
    if width % 2 or height % 2:
        raise ValueError('width and height must be even (H.264 yuv420p)')
    fs = _int(p.get('frame_start', 1), 0, 9999, 'frame_start')
    fe = _int(p.get('frame_end', fs + 47), fs, 9999, 'frame_end')
    if fe - fs + 1 > MAX_FRAMES:
        raise ValueError(f'at most {MAX_FRAMES} frames per render')
    lights = p.get('lights')
    if lights is not None:
        if not isinstance(lights, list) or not 1 <= len(lights) <= 16:
            raise ValueError('lights must be a list of 1 to 16 dicts (or omitted for 3-point lighting)')
        lights = [_light(raw, i) for i, raw in enumerate(lights)]
    else:
        notes.append('lights omitted: key/fill/rim area lights are placed around the scene bounds')
    cfg = {
        'gltf_text': gltf_text, 'gltf_path': gltf_file, 'primitives': prims,
        'engine': engine,
        'samples': _int(p.get('samples', 64), 1, 4096, 'samples'),
        'device': _choice(p.get('cycles_device', 'cpu'), {'cpu', 'gpu'}, 'cycles_device'),
        'width': width, 'height': height,
        'fps': _int(p.get('fps', 24), 1, 120, 'fps'),
        'frame_start': fs, 'frame_end': fe,
        'camera': _camera(p.get('camera')),
        'lights': lights,
        'world_color': _vec(p.get('world_color', [0.2, 0.2, 0.22]), 3, 'world_color', 0.0, 1.0),
        'world_strength': _num(p.get('world_strength', 1.0), 0.0, 100.0, 'world_strength'),
        'output': _choice(p.get('output', 'png'), {'png', 'mp4'}, 'output'),
        'output_dir': None,
    }
    if cfg['camera']['location'] is None:
        notes.append('camera location omitted: it is placed along camera.direction to frame '
                     'the scene bounds')
    if cfg['world_strength'] * max(cfg['world_color']) < 0.02 and not lights:
        notes.append('very dark world: frames may come out nearly black')
    return cfg, notes


BLENDER_TEMPLATE = r'''# Generated by Red Rose bridges_v28 (blender_script).
# Run headless:  blender -b --factory-startup --python-exit-code 1 --python THIS_FILE
# Every owner-supplied value is inside CONFIG (decoded from JSON); the code below
# never splices owner text into Python source.
import json
import math
import os
import shutil
import tempfile

import bpy
import mathutils

CONFIG = json.loads(__RR_CONFIG__)
Vector = mathutils.Vector


def engine_id(kind):
    items = {i.identifier for i in bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items}
    if kind == 'cycles':
        return 'CYCLES'
    for name in ('BLENDER_EEVEE', 'BLENDER_EEVEE_NEXT'):
        if name in items:
            return name
    raise RuntimeError('this Blender build has no EEVEE engine')


def make_material(name, color, metallic, roughness):
    mat = bpy.data.materials.new(name)
    try:
        mat.use_nodes = True
    except Exception:
        pass
    mat.diffuse_color = color
    tree = getattr(mat, 'node_tree', None)
    if tree is not None:
        bsdf = next((n for n in tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
        if bsdf is not None:
            bsdf.inputs['Base Color'].default_value = color
            bsdf.inputs['Metallic'].default_value = metallic
            bsdf.inputs['Roughness'].default_value = roughness
    return mat


def add_primitive(p):
    loc = p['location']
    rot = [math.radians(a) for a in p['rotation_deg']]
    size = p['size']
    kind = p['type']
    if kind == 'cube':
        bpy.ops.mesh.primitive_cube_add(size=size, location=loc, rotation=rot)
    elif kind == 'uv_sphere':
        bpy.ops.mesh.primitive_uv_sphere_add(radius=size / 2, segments=48, ring_count=24,
                                             location=loc, rotation=rot)
    elif kind == 'cylinder':
        bpy.ops.mesh.primitive_cylinder_add(radius=size / 2, depth=size, vertices=48,
                                            location=loc, rotation=rot)
    elif kind == 'cone':
        bpy.ops.mesh.primitive_cone_add(radius1=size / 2, radius2=0.0, depth=size, vertices=48,
                                        location=loc, rotation=rot)
    elif kind == 'plane':
        bpy.ops.mesh.primitive_plane_add(size=size, location=loc, rotation=rot)
    elif kind == 'torus':
        bpy.ops.mesh.primitive_torus_add(major_radius=size / 2, minor_radius=size / 8,
                                         location=loc, rotation=rot)
    else:
        raise ValueError('unknown primitive type')
    obj = bpy.context.view_layer.objects.active
    obj.name = p['name']
    obj.scale = p['scale']
    if p['smooth']:
        for poly in obj.data.polygons:
            poly.use_smooth = True
    obj.data.materials.append(make_material(p['name'] + '_mat', p['color'], p['metallic'],
                                            p['roughness']))
    return obj


def import_gltf():
    before = {o.name for o in bpy.data.objects}
    tmp = None
    path = CONFIG.get('gltf_path')
    try:
        if CONFIG.get('gltf_text'):
            tmp = tempfile.mkdtemp(prefix='red_rose_gltf_')
            path = os.path.join(tmp, 'scene.gltf')
            with open(path, 'w', encoding='utf-8') as fh:
                fh.write(CONFIG['gltf_text'])
        if path:
            bpy.ops.import_scene.gltf(filepath=path)
    finally:
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)
    return [o.name for o in bpy.data.objects if o.name not in before]


def aim(obj, target):
    d = Vector(target) - obj.location
    if d.length > 1e-9:
        obj.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()


def bounds(scene):
    bpy.context.view_layer.update()
    pts = []
    for o in scene.objects:
        if o.type == 'MESH':
            pts.extend(o.matrix_world @ Vector(c) for c in o.bound_box)
    if not pts:
        return Vector((0.0, 0.0, 0.0)), 1.0
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    center = (lo + hi) / 2
    return center, max(max((p - center).length for p in pts), 1e-3)


def add_light(scene, spec, center):
    data = bpy.data.lights.new(spec['name'], spec['type'])
    data.energy = spec['energy']
    data.color = spec['color']
    try:
        if spec['type'] == 'AREA':
            data.size = spec['size']
        elif spec['type'] in ('POINT', 'SPOT'):
            data.shadow_soft_size = spec['size']
    except Exception:
        pass
    obj = bpy.data.objects.new(spec['name'], data)
    scene.collection.objects.link(obj)
    obj.location = spec['location']
    aim(obj, spec['target'] if spec['target'] is not None else center)
    return obj


bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
created = [add_primitive(p).name for p in CONFIG['primitives']]
imported = import_gltf()
center, radius = bounds(scene)

world = bpy.data.worlds.new('RedRoseWorld')
scene.world = world
wc = CONFIG['world_color']
world.color = wc
try:
    world.use_nodes = True
except Exception:
    pass
wtree = getattr(world, 'node_tree', None)
if wtree is not None:
    bg = next((n for n in wtree.nodes if n.type == 'BACKGROUND'), None)
    if bg is not None:
        bg.inputs['Color'].default_value = (wc[0], wc[1], wc[2], 1.0)
        bg.inputs['Strength'].default_value = CONFIG['world_strength']

cam_cfg = CONFIG['camera']
cam_data = bpy.data.cameras.new('RedRoseCamera')
cam_data.lens = cam_cfg['lens_mm']
cam_data.clip_start = max(0.001, radius * 0.001)
cam_data.clip_end = max(1000.0, radius * 100.0)
cam = bpy.data.objects.new('RedRoseCamera', cam_data)
scene.collection.objects.link(cam)
scene.camera = cam
target = Vector(cam_cfg['target']) if cam_cfg['target'] is not None else center.copy()
if cam_cfg['location'] is not None:
    cam_loc = Vector(cam_cfg['location'])
else:
    w, h = CONFIG['width'], CONFIG['height']
    half = math.atan(18.0 * min(w, h) / max(w, h) / cam_cfg['lens_mm'])
    cam_loc = target + Vector(cam_cfg['direction']).normalized() * (radius / math.sin(half) * 1.08)
fs, fe = CONFIG['frame_start'], CONFIG['frame_end']
if cam_cfg['turntable']:
    pivot = bpy.data.objects.new('RedRoseOrbit', None)
    scene.collection.objects.link(pivot)
    pivot.location = target
    cam.parent = pivot
    cam.location = cam_loc - target
    look = target - cam_loc
    if look.length > 1e-9:
        cam.rotation_euler = look.to_track_quat('-Z', 'Y').to_euler()
    try:
        bpy.context.preferences.edit.keyframe_new_interpolation_type = 'LINEAR'
    except Exception:
        pass
    pivot.rotation_euler = (0.0, 0.0, 0.0)
    pivot.keyframe_insert(data_path='rotation_euler', index=2, frame=fs)
    pivot.rotation_euler = (0.0, 0.0, 2.0 * math.pi * cam_cfg['turns'])
    pivot.keyframe_insert(data_path='rotation_euler', index=2, frame=fe + 1)
else:
    cam.location = cam_loc
    aim(cam, target)

if CONFIG['lights'] is None:
    dist = radius * 3.0
    gain = max(1.0, (dist / 5.0) ** 2)
    for name, off, energy in (('RedRoseKey', (1.0, -1.0, 1.2), 800.0),
                              ('RedRoseFill', (-1.2, -0.6, 0.6), 300.0),
                              ('RedRoseRim', (0.0, 1.3, 1.0), 500.0)):
        loc = center + Vector(off).normalized() * dist
        add_light(scene, {'type': 'AREA', 'name': name, 'location': list(loc), 'target': None,
                          'energy': energy * gain, 'color': [1.0, 1.0, 1.0],
                          'size': radius * 1.5}, center)
else:
    for spec in CONFIG['lights']:
        add_light(scene, spec, center)

scene.render.engine = engine_id(CONFIG['engine'])
device = None
if CONFIG['engine'] == 'cycles':
    scene.cycles.samples = CONFIG['samples']
    device = 'CPU'
    if CONFIG['device'] == 'gpu':
        try:
            prefs = bpy.context.preferences.addons['cycles'].preferences
            for kind in ('OPTIX', 'CUDA', 'HIP', 'ONEAPI', 'METAL'):
                try:
                    prefs.compute_device_type = kind
                except Exception:
                    continue
                prefs.get_devices()
                if any(d.type != 'CPU' for d in prefs.devices):
                    for d in prefs.devices:
                        d.use = d.type != 'CPU'
                    device = 'GPU'
                    break
        except Exception:
            device = 'CPU'
    scene.cycles.device = device
else:
    try:
        scene.eevee.taa_render_samples = CONFIG['samples']
    except Exception:
        pass

render = scene.render
render.resolution_x = CONFIG['width']
render.resolution_y = CONFIG['height']
render.resolution_percentage = 100
render.fps = CONFIG['fps']
render.fps_base = 1.0
scene.frame_start = fs
scene.frame_end = fe
render.film_transparent = False
render.image_settings.file_format = 'PNG'
render.image_settings.color_mode = 'RGB'
out_dir = CONFIG['output_dir']
if not out_dir:
    here = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.getcwd()
    out_dir = os.path.join(here, 'renders')
os.makedirs(out_dir, exist_ok=True)
render.filepath = os.path.join(out_dir, 'frame_####')
render.use_file_extension = True
bpy.ops.render.render(animation=True)

written = sorted(f for f in os.listdir(out_dir) if f.startswith('frame_') and f.endswith('.png'))
print('RED_ROSE_RESULT ' + json.dumps({
    'blender_version': bpy.app.version_string, 'engine': scene.render.engine, 'device': device,
    'objects': len(scene.objects), 'primitives': created, 'imported_objects': len(imported),
    'center': [round(c, 6) for c in center], 'radius': round(radius, 6),
    'frames_written': len(written), 'output_dir': out_dir,
}))
'''


def _blender_script_text(cfg):
    literal = json.dumps(_json_literal(cfg), ensure_ascii=True)
    return BLENDER_TEMPLATE.replace('__RR_CONFIG__', literal, 1)


_BLENDER_ASSUMPTIONS = [
    'scene is rebuilt from factory settings (empty scene) every run',
    'glTF import uses Blender\'s bundled glTF importer (Y-up glTF is converted to Z-up)',
    'frames are 8-bit RGB PNG named frame_####.png; MP4 is assembled afterwards by FFmpeg '
    '(H.264, yuv420p, faststart, no audio), not by Blender\'s own video writer',
    'EEVEE is picked by whichever identifier this Blender offers (BLENDER_EEVEE or BLENDER_EEVEE_NEXT)',
    'cycles_device="gpu" falls back to CPU when no OptiX/CUDA/HIP/oneAPI/Metal device is found',
]
_BLENDER_LIMITS = [
    f'<= 100 primitives, <= 16 lights, <= {MAX_FRAMES} frames, frame numbers <= 9999',
    'embedded gltf must carry its buffers/images as data: URIs (else use gltf_path)',
    'materials are Principled BSDF factors only (no textures for primitives)',
    'written for Blender 4.x/5.x bpy; not every Blender version was tried',
]


def blender_script(*, output_dir=None, **params):
    """Generate (do not run) a bpy script that builds a scene from a modeling3d_v23 glTF export,
    a .gltf/.glb file and/or simple primitives, sets camera, lights, engine (Cycles/EEVEE),
    frame range and output folder, then renders PNG frames."""
    cfg, notes = _blender_cfg(params)
    if output_dir is not None:
        cfg['output_dir'] = str(_path_like(output_dir, 'output_dir'))
    else:
        notes.append('output_dir omitted: frames go to a "renders" folder next to the script')
    script = _blender_script_text(cfg)
    run_args = ['blender', '-b', '--factory-startup', '--python-exit-code', '1',
                '--python', '<script.py>']
    result = {'script': script, 'script_sha256': hashlib.sha256(script.encode('utf-8')).hexdigest(),
              'run_args': run_args, 'engine': cfg['engine'], 'frames': cfg['frame_end'] - cfg['frame_start'] + 1,
              'output': cfg['output'], 'output_dir': cfg['output_dir'], 'notes': notes,
              'executed': False}
    if cfg['output'] == 'mp4':
        result['mp4_note'] = ('the script renders PNG frames; blender_render (or the owner) encodes '
                              'them with FFmpeg: -framerate FPS -start_number START -i frame_%04d.png '
                              '-c:v libx264 -pix_fmt yuv420p -movflags +faststart')
    return _pack('blender_script', result,
                 _BLENDER_ASSUMPTIONS + ['the script is returned as text only; nothing was run or written'],
                 _BLENDER_LIMITS)


def _first_frame_luma(ffmpeg, png):
    done, err = _run([ffmpeg, '-hide_banner', '-nostdin', '-v', 'error', '-i', str(png),
                      '-vf', 'scale=1:1:flags=area,format=gray', '-frames:v', '1',
                      '-f', 'rawvideo', '-'], 60)
    if err or done is None or not done.stdout:
        return None
    return int(done.stdout[0])


def blender_render(*, work_dir=None, basename='red_rose_blender', timeout_s=900,
                   approve_write=False, **params):
    """Write the blender_script into work_dir and run
    blender -b --factory-startup --python-exit-code 1 --python SCRIPT; collect PNG frames and,
    for output='mp4', encode and verify an H.264 MP4 with verify_video."""
    cfg, notes = _blender_cfg(params)
    wd = _work_dir(work_dir)
    base = _basename(basename)
    timeout_s = _int(timeout_s, 30, 7200, 'timeout_s')
    script_path = _new_target(wd, base + '.py')
    frames_dir = _new_target(wd, base + '_frames')
    mp4_path = _new_target(wd, base + '.mp4') if cfg['output'] == 'mp4' else None
    if mp4_path is not None and '%' in str(frames_dir):
        raise ValueError('work_dir/basename must not contain "%" when output="mp4" '
                         '(FFmpeg image-sequence pattern)')
    _approved(approve_write)
    needed = ['blender'] + (['ffmpeg', 'ffprobe'] if mp4_path is not None else [])
    exes = {n: _exe(n)[0] for n in needed}
    if not all(exes.values()):
        return _not_installed('blender_render', needed, _BLENDER_ASSUMPTIONS, _BLENDER_LIMITS)
    cfg['output_dir'] = str(frames_dir)
    script = _blender_script_text(cfg)
    files = [_write_new_text(script_path, script)]
    frames_dir.mkdir()
    argv = [exes['blender'], '-b', '--factory-startup', '--python-exit-code', '1',
            '--python', str(script_path)]
    done, err = _run(argv, timeout_s)
    stdout = _tail(done.stdout, 200_000) if done is not None else ''
    summary = None
    for line in stdout.splitlines():
        if line.startswith(RESULT_MARK):
            try:
                summary = json.loads(line[len(RESULT_MARK):])
            except ValueError:
                summary = None
    frames = sorted(frames_dir.glob('frame_*.png'))
    expected = cfg['frame_end'] - cfg['frame_start'] + 1
    result = {'status': 'ok', 'script': files[0], 'frames_dir': str(frames_dir),
              'frames_written': len(frames), 'frames_expected': expected,
              'blender_summary': summary, 'notes': notes, 'files': files,
              'log_tail': _tail(stdout + '\n' + (_tail(done.stderr) if done is not None else ''),
                                MAX_LOG)}
    if err or len(frames) != expected:
        result['status'] = 'failed'
        result['error'] = err or f'Blender wrote {len(frames)} of {expected} frames'
        return _pack('blender_render', result,
                     _BLENDER_ASSUMPTIONS + ['the script and any frames already written are kept'],
                     _BLENDER_LIMITS)
    ffmpeg = _exe('ffmpeg')[0]
    if ffmpeg:
        luma = _first_frame_luma(ffmpeg, frames[0])
        result['first_frame_mean_luma'] = luma
        if luma is not None and luma < 16:
            result['warnings'] = ['first frame is nearly black (mean luma < 16): add light or '
                                  'brighten the world before delivery']
    if mp4_path is not None:
        fd, tmp_name = tempfile.mkstemp(prefix='.bridges_v28_', suffix='.mp4', dir=wd)
        os.close(fd)
        tmp = Path(tmp_name)
        try:
            enc, err = _run([exes['ffmpeg'], '-hide_banner', '-nostdin', '-v', 'error', '-y',
                             '-framerate', str(cfg['fps']), '-start_number', str(cfg['frame_start']),
                             '-i', str(frames_dir / 'frame_%04d.png'),
                             '-frames:v', str(expected), '-c:v', 'libx264', '-preset', 'medium',
                             '-crf', '18', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', '-an',
                             str(tmp)], max(120, expected))
            if err:
                result['status'] = 'failed'
                result['error'] = err
            else:
                try:
                    qa = verify_video(tmp, expected_fps=cfg['fps'], width=cfg['width'],
                                      height=cfg['height'], expected_frames=expected,
                                      expected_audio=False)
                except (ValueError, RuntimeError, OSError, KeyError, TypeError,
                        subprocess.CalledProcessError) as exc:
                    result['status'] = 'failed'
                    result['error'] = f'MP4 verification failed: {exc}'
                else:
                    _copy_new(tmp, mp4_path)
                    qa = dict(qa, path=str(mp4_path))
                    result['mp4'] = qa
                    files.append({'path': str(mp4_path), 'bytes': qa['bytes'], 'sha256': qa['sha256']})
        finally:
            _unlink(tmp)
    return _pack('blender_render', result,
                 _BLENDER_ASSUMPTIONS + ['outputs are new files inside work_dir; nothing is overwritten'],
                 _BLENDER_LIMITS + [f'Blender wall-clock limit {timeout_s} s'])


# --------------------------------------------------------------------------- timeline (studio_v27)

_TL_KEYS = {'width', 'height', 'fps', 'duration', 'background', 'layers', 'audio'}
_TL_LAYER_KEYS = {'module', 'op', 'params', 'start', 'end', 'z', 'opacity'}
_TL_AUDIO_KEYS = {'path', 'start', 'gain_db', 'role'}
_KF_TRACKS = {'position', 'opacity', 'scale'}


def _load_json_dict(spec, name, max_chars=MAX_SPEC_CHARS):
    if isinstance(spec, str):
        if len(spec) > max_chars:
            raise ValueError(f'{name} JSON must be at most {max_chars} characters')
        try:
            spec = json.loads(spec)
        except ValueError as exc:
            raise ValueError(f'{name} is not valid JSON: {exc}') from exc
    if not isinstance(spec, dict):
        raise ValueError(f'{name} must be a dict (or its JSON text)')
    try:
        text = json.dumps(spec, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError(f'{name} must be JSON-serialisable: {exc}') from exc
    if len(text) > max_chars:
        raise ValueError(f'{name} must be at most {max_chars} characters as JSON')
    return json.loads(text)


def _keyframes(raw, n_layers, duration, width, height):
    out = {}
    if raw is None:
        return out
    if not isinstance(raw, dict) or len(raw) > n_layers:
        raise ValueError('keyframes must be a dict {layer index: {track: [[t, value], ...]}}')
    span = 10.0 * max(width, height)
    for key, tracks in raw.items():
        try:
            idx = int(key)
        except (TypeError, ValueError):
            raise ValueError(f'keyframes key {key!r} must be a layer index') from None
        if isinstance(key, bool) or not 0 <= idx < n_layers or str(idx) != str(key).strip():
            raise ValueError(f'keyframes key {key!r} is not a layer index 0..{n_layers - 1}')
        if not isinstance(tracks, dict) or set(tracks) - _KF_TRACKS:
            raise ValueError(f'keyframes[{key}] tracks must be among {sorted(_KF_TRACKS)}')
        layer = {}
        for track, keys in tracks.items():
            where = f'keyframes[{key}].{track}'
            if not isinstance(keys, list) or not 1 <= len(keys) <= 200:
                raise ValueError(f'{where} must be a list of 1 to 200 [t, value] pairs')
            norm, last = [], -1.0
            for j, pair in enumerate(keys):
                if not isinstance(pair, (list, tuple)) or len(pair) != 2:
                    raise ValueError(f'{where}[{j}] must be [t, value]')
                t = _num(pair[0], 0.0, duration, f'{where}[{j}].t')
                if t <= last:
                    raise ValueError(f'{where} times must increase strictly')
                last = t
                if track == 'position':
                    v = _vec(pair[1], 2, f'{where}[{j}].value', -span, span)
                elif track == 'scale':
                    v = _vec(pair[1], 2, f'{where}[{j}].value', 0.0, 20.0)
                else:
                    v = _num(pair[1], 0.0, 1.0, f'{where}[{j}].value')
                norm.append([round(t, 6), v])
            layer[track] = norm
        out[idx] = layer
    return out


def _timeline(spec, keyframes=None, *, allow_missing_audio=True):
    spec = _load_json_dict(spec, 'timeline')
    unknown = set(spec) - _TL_KEYS
    if unknown:
        raise ValueError(f'timeline: unknown top-level key(s) {sorted(unknown)}')
    w = _int(spec.get('width'), 16, 7680, 'timeline.width')
    h = _int(spec.get('height'), 16, 7680, 'timeline.height')
    if w % 2 or h % 2:
        raise ValueError('timeline width and height must be even')
    fps = _int(spec.get('fps'), 1, 120, 'timeline.fps')
    duration = _num(spec.get('duration'), 0.0, MAX_SECONDS, 'timeline.duration', low_open=True)
    bg_rgb, bg_hex = _hex(spec.get('background', '#202020'), 'timeline.background')
    layers_raw = spec.get('layers', [])
    if not isinstance(layers_raw, list) or len(layers_raw) > 64:
        raise ValueError('timeline.layers must be a list of at most 64 items')
    warnings, layers = [], []
    for i, raw in enumerate(layers_raw):
        where = f'layers[{i}]'
        if not isinstance(raw, dict):
            raise ValueError(f'{where} must be a dict')
        bad = set(raw) - _TL_LAYER_KEYS
        if bad:
            raise ValueError(f'{where}: unknown key(s) {sorted(bad)}')
        module = _clean_text(raw.get('module', 'svg'), f'{where}.module', max_len=64, multiline=False)
        op = _clean_text(raw.get('op', 'fragment'), f'{where}.op', max_len=120, multiline=False)
        params = raw.get('params', {})
        if not isinstance(params, dict):
            raise ValueError(f'{where}.params must be a dict')
        start = _num(raw.get('start', 0.0), 0.0, duration, f'{where}.start')
        end = _num(raw.get('end', duration), 0.0, duration, f'{where}.end')
        if end <= start:
            raise ValueError(f'{where}: end must be after start')
        z = _int(raw.get('z', 0), -1000, 1000, f'{where}.z')
        opacity = _num(raw.get('opacity', 1.0), 0.0, 1.0, f'{where}.opacity')
        text = params.get('text')
        text = (_clean_text(text, f'{where}.params.text', max_len=2000, required=False)
                if isinstance(text, str) else '')
        kind = 'text' if text and module != 'svg' else 'placeholder'
        default_color = '#ffffff' if kind == 'text' else '#808080'
        try:
            color, color_hex = _hex(params.get('color', default_color), f'{where}.params.color')
        except ValueError:
            color, color_hex = _hex(default_color, 'default')
            warnings.append(f'{where}: params.color is not "#rrggbb"; {default_color} used')
        size = params.get('size', 96)
        if isinstance(size, bool) or not isinstance(size, (int, float)) or not 4 <= size <= 2000:
            size = 96
        font = params.get('font', params.get('font_family', ''))
        font = _clean_text(font, f'{where}.params.font', max_len=100, multiline=False,
                           required=False) if isinstance(font, str) else ''
        direction = params.get('direction')
        rtl = (direction == 'rtl' if direction in ('rtl', 'ltr')
               else bool(_ARABIC.search(text)))
        if kind == 'placeholder':
            warnings.append(f'{where} ({module}/{op}) has no portable equivalent: exported as a '
                            'named placeholder')
        layers.append({'index': i, 'kind': kind, 'module': module, 'op': op,
                       'name': f'{i:02d} {module}/{op}', 'text': text, 'rtl': rtl,
                       'color': color, 'hex': color_hex, 'size': float(size), 'font': font,
                       'start': round(start, 6), 'end': round(end, 6), 'z': z,
                       'opacity': opacity, 'keyframes': {}})
    for idx, tracks in _keyframes(keyframes, len(layers), duration, w, h).items():
        layers[idx]['keyframes'] = tracks
    audio_raw = spec.get('audio', [])
    if not isinstance(audio_raw, list) or len(audio_raw) > 16:
        raise ValueError('timeline.audio must be a list of at most 16 items')
    audio = []
    for i, raw in enumerate(audio_raw):
        where = f'audio[{i}]'
        if not isinstance(raw, dict):
            raise ValueError(f'{where} must be a dict')
        bad = set(raw) - _TL_AUDIO_KEYS
        if bad:
            raise ValueError(f'{where}: unknown key(s) {sorted(bad)}')
        path = _path_like(raw.get('path'), f'{where}.path')
        if not path.is_file():
            if not allow_missing_audio:
                raise ValueError(f'{where}.path must be an existing file')
            warnings.append(f'{where}.path was not found on this machine')
        start = _num(raw.get('start', 0.0), 0.0, duration, f'{where}.start')
        if start >= duration:
            raise ValueError(f'{where}.start must be before the timeline end')
        audio.append({'path': str(path), 'start': round(start, 6),
                      'gain_db': _num(raw.get('gain_db', 0.0), -30.0, 12.0, f'{where}.gain_db'),
                      'role': _choice(raw.get('role', 'music'), {'voice', 'music', 'sfx'},
                                      f'{where}.role')})
    return {'width': w, 'height': h, 'fps': fps, 'duration': duration,
            'frames': max(1, int(round(duration * fps))), 'background': bg_hex,
            'background_rgb': bg_rgb, 'layers': layers, 'audio': audio}, warnings


# --------------------------------------------------------------------------- After Effects

AE_TEMPLATE = r'''// Red Rose bridges_v28 ae_jsx: After Effects ExtendScript built from a studio_v27 timeline.
// NOT executed by Red Rose. The owner runs it inside After Effects:
//   File > Scripts > Run Script File... (choose this .jsx)
// Arabic / right-to-left text: before running, enable the "South Asian and Middle Eastern"
// text engine (Preferences > Type) and restart After Effects; the script also tries to set
// right-to-left paragraph direction, which only newer After Effects versions support.
// Layers with no After Effects equivalent are added as named guide solids (not rendered).
// All owner text lives in CFG (JSON); the code below never splices text into source.
(function () {
    var CFG = __RR_CFG__;
    function rgb(c) { return [c[0], c[1], c[2]]; }
    function track(prop, keys, mul) {
        if (!keys || !keys.length) { return; }
        for (var i = 0; i < keys.length; i++) {
            var v = keys[i][1];
            var val;
            if (v instanceof Array) {
                val = [];
                for (var j = 0; j < v.length; j++) { val.push(v[j] * mul); }
            } else {
                val = v * mul;
            }
            prop.setValueAtTime(keys[i][0], val);
        }
    }
    app.beginUndoGroup('Red Rose timeline');
    try {
        var comp = app.project.items.addComp(CFG.name, CFG.width, CFG.height, 1.0,
                                             CFG.duration, CFG.fps);
        comp.bgColor = rgb(CFG.background);
        for (var i = 0; i < CFG.layers.length; i++) {
            var L = CFG.layers[i];
            var layer;
            if (L.kind === 'text') {
                layer = comp.layers.addText(L.text);
                var st = layer.property('ADBE Text Properties').property('ADBE Text Document');
                var doc = st.value;
                doc.fontSize = L.size;
                doc.applyFill = true;
                doc.fillColor = rgb(L.color);
                doc.justification = ParagraphJustification.CENTER_JUSTIFY;
                if (L.font) { try { doc.font = L.font; } catch (e1) {} }
                if (L.rtl) {
                    try { doc.direction = ParagraphDirection.DIRECTION_RIGHT_TO_LEFT; } catch (e2) {}
                }
                st.setValue(doc);
            } else {
                layer = comp.layers.addSolid(rgb(L.color), L.name, CFG.width, CFG.height, 1.0,
                                             CFG.duration);
                layer.guideLayer = true;
            }
            layer.name = L.name;
            layer.startTime = 0;
            layer.inPoint = L.start;
            layer.outPoint = L.end;
            var tr = layer.property('ADBE Transform Group');
            tr.property('ADBE Opacity').setValue(L.opacity * 100);
            track(tr.property('ADBE Position'), L.keyframes.position, 1);
            track(tr.property('ADBE Opacity'), L.keyframes.opacity, 100);
            track(tr.property('ADBE Scale'), L.keyframes.scale, 100);
        }
        var missing = [];
        for (var a = 0; a < CFG.audio.length; a++) {
            var A = CFG.audio[a];
            var f = new File(A.path);
            if (!f.exists) { missing.push(A.path); continue; }
            var item = app.project.importFile(new ImportOptions(f));
            var al = comp.layers.add(item);
            al.name = 'audio ' + A.role + ' ' + a;
            al.startTime = A.start;
            if (A.gain_db) {
                try {
                    al.property('ADBE Audio Group').property('ADBE Audio Levels')
                        .setValue([A.gain_db, A.gain_db]);
                } catch (e3) {}
            }
        }
        comp.openInViewer();
        if (missing.length) {
            alert('Red Rose: audio files not found:\n' + missing.join('\n'));
        }
    } finally {
        app.endUndoGroup();
    }
})();
'''


def ae_jsx(*, timeline=None, comp_name='Red Rose', keyframes=None, **extra):
    """Generate an After Effects ExtendScript (.jsx) text that builds a composition from a
    studio_v27 timeline: text layers (with RTL handling), guide solids for other layers, audio
    footage, and position/opacity/scale keyframes. The owner runs it inside After Effects."""
    _no_extra(extra)
    if timeline is None:
        raise ValueError('timeline is required (studio_v27 timeline dict or JSON)')
    tl, warnings = _timeline(timeline, keyframes)
    name = _clean_text(comp_name, 'comp_name', max_len=200, multiline=False)
    layers = sorted(tl['layers'], key=lambda l: (l['z'], l['index']))
    cfg = {'name': name, 'width': tl['width'], 'height': tl['height'], 'fps': tl['fps'],
           'duration': tl['duration'], 'background': tl['background_rgb'],
           'layers': [{k: l[k] for k in ('kind', 'name', 'text', 'rtl', 'color', 'size', 'font',
                                         'start', 'end', 'opacity', 'keyframes')} for l in layers],
           'audio': tl['audio']}
    jsx = AE_TEMPLATE.replace('__RR_CFG__', _json_literal(cfg), 1)
    return _pack('ae_jsx', {
        'jsx': jsx, 'jsx_sha256': hashlib.sha256(jsx.encode('utf-8')).hexdigest(),
        'run_by': 'owner inside After Effects (File > Scripts > Run Script File); not executed here',
        'text_layers': sum(1 for l in layers if l['kind'] == 'text'),
        'placeholder_layers': sum(1 for l in layers if l['kind'] == 'placeholder'),
        'audio_layers': len(tl['audio']), 'warnings': warnings, 'executed': False},
        ['only text supplied in the timeline (params.text) is used; nothing is written for the owner',
         'layer stacking follows z (higher z on top); keyframe times are composition seconds, '
         'position in pixels, scale as factors (1 = 100%), opacity 0..1',
         'text layers keep After Effects\' default centred position unless position keyframes are given',
         'RTL: needs the Middle Eastern text engine; ParagraphDirection is set only where the '
         'After Effects version supports it'],
        ['motion/graphics/svg layers cannot be translated: they become guide solids to re-create',
         'audio paths must exist on the After Effects machine; missing ones are listed in an alert',
         'ExtendScript (ES3); not run or checked inside After Effects here'])


# --------------------------------------------------------------------------- NLE (EDL + FCPXML)

_CLIP_KEYS = {'path', 'name', 'src_in', 'src_out', 'record_in', 'track'}
_TRACKS = {'V', 'A', 'A2', 'AA', 'B'}


def _tc(frames, fps):
    hh, rest = divmod(frames, 3600 * fps)
    mm, rest = divmod(rest, 60 * fps)
    ss, ff = divmod(rest, fps)
    return f'{hh:02d}:{mm:02d}:{ss:02d}:{ff:02d}'


def _ftime(frames, fps):
    if frames == 0:
        return '0s'
    f = Fraction(frames, fps)
    return f'{f.numerator}s' if f.denominator == 1 else f'{f.numerator}/{f.denominator}s'


def _clips(raw, fps):
    if not isinstance(raw, list) or not 1 <= len(raw) <= 999:
        raise ValueError('clips must be a list of 1 to 999 dicts')
    out, cursor, warnings = [], {}, []
    for i, c in enumerate(raw):
        where = f'clips[{i}]'
        if not isinstance(c, dict):
            raise ValueError(f'{where} must be a dict')
        bad = set(c) - _CLIP_KEYS
        if bad:
            raise ValueError(f'{where}: unknown key(s) {sorted(bad)}')
        path = _path_like(c.get('path'), f'{where}.path')
        if not path.is_file():
            warnings.append(f'{where}.path was not found on this machine')
        track = _choice(c.get('track', 'V'), _TRACKS, f'{where}.track')
        name = _clean_text(c.get('name', path.stem), f'{where}.name', max_len=120, multiline=False)
        src_in = _num(c.get('src_in', 0.0), 0.0, 86400.0, f'{where}.src_in')
        src_out = _num(c.get('src_out'), 0.0, 86400.0, f'{where}.src_out')
        si, so = int(round(src_in * fps)), int(round(src_out * fps))
        if so <= si:
            raise ValueError(f'{where}: src_out must be at least one frame after src_in')
        group = 'V' if track in ('V', 'B') else track
        if c.get('record_in') is None:
            rec = cursor.get(group, 0)
        else:
            rec = int(round(_num(c['record_in'], 0.0, 86400.0, f'{where}.record_in') * fps))
        length = so - si
        cursor[group] = max(cursor.get(group, 0), rec + length)
        out.append({'order': i, 'path': str(path), 'name': name, 'track': track,
                    'src_in': si, 'src_out': so, 'rec': rec, 'len': length})
    return out, warnings


def _assign_lanes(items, sign, first):
    ends = []
    for it in sorted(items, key=lambda x: (x['rec'], x['order'])):
        for k, end in enumerate(ends):
            if end <= it['rec']:
                ends[k] = it['rec'] + it['len']
                it['lane'] = sign * (first + k)
                break
        else:
            ends.append(it['rec'] + it['len'])
            it['lane'] = sign * (first + len(ends) - 1)
    return len(ends)


def _edl_text(title, clips, fps, hour):
    off = hour * 3600 * fps
    lines = [f'TITLE: {title[:70]}', 'FCM: NON-DROP FRAME', '']
    for n, c in enumerate(sorted(clips, key=lambda x: (x['rec'], x['order'])), 1):
        lines.append(f'{n:03d}  {"AX":<8} {c["track"]:<5} C        '
                     f'{_tc(c["src_in"], fps)} {_tc(c["src_out"], fps)} '
                     f'{_tc(c["rec"] + off, fps)} {_tc(c["rec"] + c["len"] + off, fps)}')
        lines.append(f'* FROM CLIP NAME: {c["name"]}')
        lines.append(f'* SOURCE FILE: {c["path"]}')
        lines.append('')
    return '\n'.join(lines)


_BASIC_TITLE_UID = ('.../Titles.localized/Bumper:Opener.localized/Basic Title.localized/'
                    'Basic Title.moti')


def _fcpxml_text(title, clips, titles, fps, width, height):
    fd = _ftime(1, fps)
    res = [f'    <format id="r1" frameDuration={_xml_attr(fd)} width="{width}" height="{height}"/>']
    if titles:
        res.append(f'    <effect id="r2" name="Basic Title" uid={_xml_attr(_BASIC_TITLE_UID)}/>')
    assets, next_id = {}, 3
    for c in clips:
        a = assets.setdefault(c['path'], {'video': False, 'audio': False, 'len': 0,
                                          'name': Path(c['path']).stem})
        a['video'] |= c['track'] in ('V', 'B')
        a['audio'] |= c['track'] != 'V'
        a['len'] = max(a['len'], c['src_out'])
    for path, a in assets.items():
        a['id'] = f'r{next_id}'
        next_id += 1
        attrs = (f'id="{a["id"]}" name={_xml_attr(a["name"])} start="0s" '
                 f'duration={_xml_attr(_ftime(a["len"], fps))} '
                 f'hasVideo="{1 if a["video"] else 0}" hasAudio="{1 if a["audio"] else 0}"')
        if a['video']:
            attrs += ' format="r1"'
        if a['audio']:
            attrs += ' audioSources="1" audioChannels="2" audioRate="48000"'
        res.append(f'    <asset {attrs}>')
        res.append(f'      <media-rep kind="original-media" src={_xml_attr(Path(path).as_uri())}/>')
        res.append('    </asset>')
    vid = [c for c in clips if c['track'] in ('V', 'B')]
    aud = [c for c in clips if c['track'] not in ('V', 'B')]
    n_v = _assign_lanes(vid, 1, 1)
    _assign_lanes(aud, -1, 1)
    _assign_lanes(titles, 1, n_v + 1)
    total = max([c['rec'] + c['len'] for c in clips] + [t['rec'] + t['len'] for t in titles] + [1])
    body = []
    for c in sorted(clips, key=lambda x: (x['rec'], x['order'])):
        enable = 'video' if c['track'] == 'V' else 'all' if c['track'] == 'B' else 'audio'
        body.append(f'              <asset-clip ref="{assets[c["path"]]["id"]}" lane="{c["lane"]}" '
                    f'offset={_xml_attr(_ftime(c["rec"], fps))} name={_xml_attr(c["name"])} '
                    f'start={_xml_attr(_ftime(c["src_in"], fps))} '
                    f'duration={_xml_attr(_ftime(c["len"], fps))} srcEnable="{enable}"/>')
    for k, t in enumerate(sorted(titles, key=lambda x: (x['rec'], x['order'])), 1):
        r, g, b = t['color']
        body.append(f'              <title ref="r2" lane="{t["lane"]}" '
                    f'offset={_xml_attr(_ftime(t["rec"], fps))} name={_xml_attr(t["name"])} '
                    f'start="0s" duration={_xml_attr(_ftime(t["len"], fps))}>')
        body.append(f'                <text><text-style ref="ts{k}">{_xml_escape(t["text"])}'
                    '</text-style></text>')
        style = (f'font={_xml_attr(t["font"] or "Helvetica")} fontSize="{t["size"]:g}" '
                 f'fontColor="{r:.4f} {g:.4f} {b:.4f} 1" alignment="center"')
        body.append(f'                <text-style-def id="ts{k}"><text-style {style}/>'
                    '</text-style-def>')
        body.append('              </title>')
    name_attr = _xml_attr(title)
    out = ['<?xml version="1.0" encoding="UTF-8"?>', '<!DOCTYPE fcpxml>', '',
           '<fcpxml version="1.9">', '  <resources>'] + res + [
        '  </resources>', '  <library>', f'    <event name={name_attr}>',
        f'      <project name={name_attr}>',
        f'        <sequence format="r1" duration={_xml_attr(_ftime(total, fps))} tcStart="0s" '
        'tcFormat="NDF" audioLayout="stereo" audioRate="48k">',
        '          <spine>',
        f'            <gap name="Red Rose base" offset="0s" start="0s" '
        f'duration={_xml_attr(_ftime(total, fps))}>'] + body + [
        '            </gap>', '          </spine>', '        </sequence>', '      </project>',
        '    </event>', '  </library>', '</fcpxml>', '']
    return '\n'.join(out)


def nle_export(*, clips=None, timeline=None, fps=None, width=None, height=None,
               title='Red Rose', format='both', record_start_hour=0, keyframes=None,
               work_dir=None, basename='red_rose_edit', approve_write=False, **extra):
    """Export a CMX3600 EDL and an FCPXML 1.9 from a clip list or a studio_v27 timeline.

    clips: [{'path', 'name', 'src_in', 'src_out', 'record_in' (default: after the previous clip
    on the same track), 'track': V|A|A2|AA|B}] in seconds. A timeline contributes its audio as
    clips (voice -> A, music/sfx -> A2) and its text layers as FCPXML titles.
    Text is returned; with work_dir (and approve_write=True) new files are also saved."""
    _no_extra(extra)
    if (clips is None) == (timeline is None):
        raise ValueError('give exactly one of clips or timeline')
    fmt = _choice(format, {'both', 'edl', 'fcpxml'}, 'format')
    title = _clean_text(title, 'title', max_len=120, multiline=False)
    hour = _int(record_start_hour, 0, 23, 'record_start_hour')
    assumptions, warnings, titles = [], [], []
    if timeline is not None:
        if fps is not None or width is not None or height is not None:
            raise ValueError('fps/width/height come from the timeline; do not pass them too')
        tl, warnings = _timeline(timeline, keyframes)
        fps, width, height = tl['fps'], tl['width'], tl['height']
        if fps > 60:
            raise ValueError('EDL/FCPXML export supports fps up to 60')
        raw = [{'path': a['path'], 'src_in': 0.0, 'src_out': tl['duration'] - a['start'],
                'record_in': a['start'], 'track': 'A' if a['role'] == 'voice' else 'A2',
                'name': f'{a["role"]} {i}'} for i, a in enumerate(tl['audio'])]
        clip_list, w2 = _clips(raw, fps) if raw else ([], [])
        warnings += w2
        for l in tl['layers']:
            if l['kind'] != 'text':
                continue
            rec = int(round(l['start'] * fps))
            length = max(1, int(round(l['end'] * fps)) - rec)
            titles.append({'order': l['index'], 'rec': rec, 'len': length, 'text': l['text'],
                           'name': l['name'], 'color': l['color'], 'size': l['size'],
                           'font': l['font']})
        assumptions.append('timeline audio clips are assumed to run from their start to the '
                           'timeline end (file lengths are not probed)')
        if not clip_list and not titles:
            raise ValueError('timeline has no audio clips and no text layers to export')
    else:
        fps = 25 if fps is None else _int(fps, 6, 60, 'fps')
        width = 1920 if width is None else _int(width, 16, 7680, 'width')
        height = 1080 if height is None else _int(height, 16, 7680, 'height')
        if keyframes is not None:
            raise ValueError('keyframes apply only to a timeline')
        clip_list, warnings = _clips(clips, fps)
    if any(c['track'] in ('V', 'B') for c in clip_list):
        vs = sorted((c for c in clip_list if c['track'] in ('V', 'B')), key=lambda c: c['rec'])
        if any(a['rec'] + a['len'] > b['rec'] for a, b in zip(vs, vs[1:])):
            warnings.append('overlapping video clips: the EDL lists them as successive events; '
                            'FCPXML puts them on separate lanes')
    result = {'fps': fps, 'width': width, 'height': height, 'events': len(clip_list),
              'titles': len(titles), 'warnings': warnings}
    edl = _edl_text(title, clip_list, fps, hour) if fmt in ('both', 'edl') and clip_list else None
    if fmt in ('both', 'edl') and not clip_list:
        warnings.append('no clips: EDL skipped (titles exist only in FCPXML)')
    fcpxml = (_fcpxml_text(title, clip_list, titles, fps, width, height)
              if fmt in ('both', 'fcpxml') else None)
    result['edl'], result['fcpxml'] = edl, fcpxml
    result['files'] = []
    if work_dir is not None:
        wd = _work_dir(work_dir)
        base = _basename(basename)
        targets = []
        if edl is not None:
            targets.append((_new_target(wd, base + '.edl'), edl))
        if fcpxml is not None:
            targets.append((_new_target(wd, base + '.fcpxml'), fcpxml))
        _approved(approve_write)
        written = []
        try:
            for path, text in targets:
                written.append(_write_new_text(path, text))
        except BaseException:
            for item in written:
                _unlink(item['path'])
            raise
        result['files'] = written
    return _pack('nle_export', result,
                 assumptions + ['times are snapped to whole frames at the given integer fps (NDF)',
                                'every EDL event uses reel "AX" with FROM CLIP NAME / SOURCE FILE '
                                'comments; record timecode starts at the given hour',
                                'FCPXML: one gap holds every clip as a connected clip on its own '
                                'lane; asset durations are the furthest source out-point used',
                                'saving needs work_dir + approve_write=True; otherwise nothing is written'],
                 ['CMX3600: <= 999 events, cuts only (no transitions/effects), ASCII is safest for '
                  'clip names', 'titles (text layers) are exported to FCPXML only',
                  'motion/graphics layers and keyframes are not exported to NLE formats',
                  'not imported into Final Cut Pro, Resolve or Premiere here'])


# --------------------------------------------------------------------------- local TTS

def _wav_facts(path):
    try:
        with wave.open(str(path), 'rb') as wf:
            rate, ch, width, n = wf.getframerate(), wf.getnchannels(), wf.getsampwidth(), wf.getnframes()
    except (wave.Error, EOFError):
        return None
    size_frames = max(0, (path.stat().st_size - 44) // max(1, width * ch))
    n = min(n, size_frames) if n > size_frames else n
    return {'sample_rate': rate, 'channels': ch, 'sample_width_bytes': width, 'frames': n,
            'duration': round(n / rate, 4) if rate else None}


def _probe_audio(ffprobe, path):
    done, err = _run([ffprobe, '-v', 'error', '-show_entries',
                      'format=duration:stream=codec_type,codec_name,sample_rate,channels',
                      '-of', 'json', str(path)], 30)
    if err or done is None:
        raise RuntimeError(err or 'ffprobe failed')
    data = json.loads(done.stdout.decode('utf-8', 'replace') or '{}')
    audio = [s for s in data.get('streams', []) if s.get('codec_type') == 'audio']
    if not audio:
        raise RuntimeError('no audio stream in the converted file')
    try:
        duration = float(data.get('format', {}).get('duration'))
    except (TypeError, ValueError):
        duration = None
    return {'codec': audio[0].get('codec_name'), 'sample_rate': int(audio[0].get('sample_rate') or 0),
            'channels': int(audio[0].get('channels') or 0),
            'duration': round(duration, 4) if duration and math.isfinite(duration) else None}


_VOICE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_+\-]{0,39}$')


def tts_local(*, text=None, engine='auto', model=None, voice='ar', rate=160, work_dir=None,
              basename='red_rose_voice', m4a=False, timeout_s=300, approve_write=False, **extra):
    """Offline text-to-speech of the owner's own text with piper (owner-supplied .onnx model with
    its .onnx.json beside it) or espeak-ng/espeak. Writes a new WAV (and optionally an AAC .m4a
    converted by FFmpeg) into work_dir."""
    _no_extra(extra)
    text = _clean_text(text, 'text', max_len=MAX_TTS_CHARS)
    engine = _choice(engine, {'auto', 'piper', 'espeak-ng', 'espeak'}, 'engine')
    model_path = None
    if model is not None:
        model_path = _local_file(model, 'model', {'.onnx'})
        if not Path(str(model_path) + '.json').is_file():
            raise ValueError('piper needs the model config "<model>.onnx.json" next to the model')
    if engine == 'piper' and model_path is None:
        raise ValueError('engine="piper" needs model (path to the owner\'s .onnx voice)')
    if not isinstance(voice, str) or not _VOICE.match(voice):
        raise ValueError('voice must be an espeak voice name such as "ar" or "en-us"')
    rate = _int(rate, 80, 450, 'rate')
    m4a = _bool(m4a, 'm4a')
    timeout_s = _int(timeout_s, 10, 1800, 'timeout_s')
    wd = _work_dir(work_dir)
    base = _basename(basename)
    wav_path = _new_target(wd, base + '.wav')
    m4a_path = _new_target(wd, base + '.m4a') if m4a else None
    _approved(approve_write)
    assumptions = ['the spoken text is exactly the owner-supplied text (control characters removed)',
                   'output WAV keeps the engine\'s native sample rate']
    limits = [f'<= {MAX_TTS_CHARS} characters', 'offline engines only; no cloud voices',
              'pronunciation of Arabic depends on the engine/voice; listen before use']
    if engine == 'auto':
        order = (['piper'] if model_path is not None else []) + ['espeak-ng', 'espeak']
        chosen = next((e for e in order if _exe(e)[0]), None)
        if chosen is None:
            return _not_installed('tts_local', order, assumptions, limits)
    else:
        chosen = engine
    needed = [chosen] + (['ffmpeg', 'ffprobe'] if m4a else [])
    exes = {n: _exe(n)[0] for n in needed}
    if not all(exes.values()):
        return _not_installed('tts_local', needed, assumptions, limits)
    data = text.encode('utf-8')
    fd, tmp_name = tempfile.mkstemp(prefix='.bridges_v28_', suffix='.wav', dir=wd)
    os.close(fd)
    tmp_wav, tmp_m4a = Path(tmp_name), None
    files = []
    try:
        if chosen == 'piper':
            argv = [exes['piper'], '--model', str(model_path), '--output_file', str(tmp_wav)]
        else:
            argv = [exes[chosen], '-v', voice, '-s', str(rate), '-b', '1', '-w', str(tmp_wav),
                    '--stdin']
        done, err = _run(argv, timeout_s, input_bytes=data)
        facts = _wav_facts(tmp_wav) if err is None else None
        if err or not facts or not facts['frames']:
            return _pack('tts_local', {
                'status': 'failed', 'engine': chosen, 'files': [],
                'error': err or 'the engine produced no readable WAV audio',
                'log_tail': _tail(done.stderr if done is not None else b'', 1500)},
                assumptions + ['nothing was kept in work_dir'], limits)
        _copy_new(tmp_wav, wav_path)
        files.append({'path': str(wav_path), 'bytes': wav_path.stat().st_size,
                      'sha256': _sha256(wav_path), **facts})
        result = {'status': 'ok', 'engine': chosen, 'voice': None if chosen == 'piper' else voice,
                  'model': str(model_path) if chosen == 'piper' else None,
                  'characters': len(text), 'files': files}
        if m4a_path is not None:
            fd, tmp_name = tempfile.mkstemp(prefix='.bridges_v28_', suffix='.m4a', dir=wd)
            os.close(fd)
            tmp_m4a = Path(tmp_name)
            enc, err = _run([exes['ffmpeg'], '-hide_banner', '-nostdin', '-v', 'error', '-y',
                             '-i', str(wav_path), '-vn', '-c:a', 'aac', '-b:a', '192k',
                             '-movflags', '+faststart', str(tmp_m4a)], max(60, timeout_s))
            if err:
                result['status'] = 'partial'
                result['m4a_error'] = err
            else:
                try:
                    info = _probe_audio(exes['ffprobe'], tmp_m4a)
                except (RuntimeError, ValueError) as exc:
                    info = {'codec': None, 'error': str(exc)}
                if info['codec'] != 'aac':
                    result['status'] = 'partial'
                    result['m4a_error'] = f'converted audio codec is {info["codec"]}, not AAC'
                else:
                    _copy_new(tmp_m4a, m4a_path)
                    files.append({'path': str(m4a_path), 'bytes': m4a_path.stat().st_size,
                                  'sha256': _sha256(m4a_path), **info})
        return _pack('tts_local', result,
                     assumptions + ['files are new and inside work_dir; nothing is overwritten'],
                     limits + ['M4A is AAC 192 kb/s with faststart'])
    finally:
        _unlink(tmp_wav)
        _unlink(tmp_m4a)


# --------------------------------------------------------------------------- Remotion

_REMOTION_TIMELINE_TS = r'''// Generated by Red Rose bridges_v28 from a studio_v27 timeline. Data only.
export type Key = [number, number | number[]];

export interface TLayer {
  index: number;
  kind: 'text' | 'placeholder';
  name: string;
  text: string;
  rtl: boolean;
  hex: string;
  size: number;
  font: string;
  start: number;
  end: number;
  z: number;
  opacity: number;
  keyframes: {position?: Key[]; opacity?: Key[]; scale?: Key[]};
}

export interface TAudio {
  file: string;
  start: number;
  gain_db: number;
  role: string;
}

export interface Timeline {
  id: string;
  width: number;
  height: number;
  fps: number;
  duration: number;
  frames: number;
  background: string;
  layers: TLayer[];
  audio: TAudio[];
}

export const TIMELINE: Timeline = __RR_DATA__;
'''

_REMOTION_MAIN_TSX = r'''import React from 'react';
import {AbsoluteFill, Audio, Sequence, interpolate, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {Key, TIMELINE, TLayer} from './timeline';

const sample = (keys: Key[] | undefined, t: number, fallback: number[]): number[] => {
  if (!keys || keys.length === 0) {
    return fallback;
  }
  const values = keys.map((k) => (Array.isArray(k[1]) ? k[1] : [k[1]]));
  if (keys.length === 1) {
    return values[0];
  }
  const times = keys.map((k) => k[0]);
  return values[0].map((_, i) =>
    interpolate(t, times, values.map((v) => v[i]), {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}),
  );
};

const Layer: React.FC<{layer: TLayer}> = ({layer}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  if (layer.kind !== 'text') {
    // Placeholder for a motion/graphics/svg layer: re-create it with Remotion components.
    return null;
  }
  const t = layer.start + frame / fps;
  const pos = sample(layer.keyframes.position, t, [TIMELINE.width / 2, TIMELINE.height / 2]);
  const opacity = sample(layer.keyframes.opacity, t, [layer.opacity])[0];
  const scale = sample(layer.keyframes.scale, t, [1, 1]);
  return (
    <div
      dir={layer.rtl ? 'rtl' : 'ltr'}
      lang={layer.rtl ? 'ar' : undefined}
      style={{
        position: 'absolute',
        left: pos[0],
        top: pos[1],
        transform: `translate(-50%, -50%) scale(${scale[0]}, ${scale[1]})`,
        opacity,
        color: layer.hex,
        fontSize: layer.size,
        fontFamily: layer.font || 'sans-serif',
        whiteSpace: 'pre',
        textAlign: 'center',
        direction: layer.rtl ? 'rtl' : 'ltr',
      }}
    >
      {layer.text}
    </div>
  );
};

export const Main: React.FC = () => {
  const {fps} = useVideoConfig();
  const ordered = [...TIMELINE.layers].sort((a, b) => a.z - b.z || a.index - b.index);
  return (
    <AbsoluteFill style={{backgroundColor: TIMELINE.background}}>
      {ordered.map((layer) => (
        <Sequence
          key={`layer-${layer.index}`}
          from={Math.round(layer.start * fps)}
          durationInFrames={Math.max(1, Math.round((layer.end - layer.start) * fps))}
          layout="none"
        >
          <Layer layer={layer} />
        </Sequence>
      ))}
      {TIMELINE.audio.map((a, i) => (
        <Sequence key={`audio-${i}`} from={Math.round(a.start * fps)} layout="none">
          <Audio src={staticFile(a.file)} volume={Math.pow(10, a.gain_db / 20)} />
        </Sequence>
      ))}
    </AbsoluteFill>
  );
};
'''

_REMOTION_ROOT_TSX = r'''import React from 'react';
import {Composition} from 'remotion';
import {Main} from './Main';
import {TIMELINE} from './timeline';

export const RemotionRoot: React.FC = () => (
  <Composition
    id={TIMELINE.id}
    component={Main}
    durationInFrames={TIMELINE.frames}
    fps={TIMELINE.fps}
    width={TIMELINE.width}
    height={TIMELINE.height}
  />
);
'''

_REMOTION_INDEX_TS = r'''import {registerRoot} from 'remotion';
import {RemotionRoot} from './Root';

registerRoot(RemotionRoot);
'''

_PROJECT = re.compile(r'^[a-z0-9][a-z0-9\-]{0,63}$')
_COMP_ID = re.compile(r'^[A-Za-z0-9\-]{1,64}$')


def remotion_project(*, timeline=None, project_name='red-rose-remotion', composition_id='RedRose',
                     keyframes=None, **extra):
    """Generate (as text, nothing installed or written) a minimal Remotion project file map from
    a studio_v27 timeline: package.json, tsconfig.json, src/index.ts, src/Root.tsx, src/Main.tsx
    and src/timeline.ts (the data)."""
    _no_extra(extra)
    if timeline is None:
        raise ValueError('timeline is required (studio_v27 timeline dict or JSON)')
    if not isinstance(project_name, str) or not _PROJECT.match(project_name):
        raise ValueError('project_name must be lowercase letters/digits/- (npm package name)')
    if not isinstance(composition_id, str) or not _COMP_ID.match(composition_id):
        raise ValueError('composition_id must be 1-64 letters, digits or -')
    tl, warnings = _timeline(timeline, keyframes)
    public, used = [], set()
    audio = []
    for i, a in enumerate(tl['audio']):
        name = Path(a['path']).name
        safe = re.sub(r'[^\w.\-]', '_', name) or f'audio_{i}'
        if safe in used:
            safe = f'{i:02d}_{safe}'
        used.add(safe)
        public.append({'from': a['path'], 'to': f'public/{safe}'})
        audio.append({'file': safe, 'start': a['start'], 'gain_db': a['gain_db'], 'role': a['role']})
    data = {'id': composition_id, 'width': tl['width'], 'height': tl['height'], 'fps': tl['fps'],
            'duration': tl['duration'], 'frames': tl['frames'], 'background': tl['background'],
            'layers': [{k: l[k] for k in ('index', 'kind', 'name', 'text', 'rtl', 'hex', 'size',
                                          'font', 'start', 'end', 'z', 'opacity', 'keyframes')}
                       for l in tl['layers']],
            'audio': audio}
    package = {
        'name': project_name, 'version': '0.1.0', 'private': True,
        'scripts': {'studio': 'remotion studio src/index.ts',
                    'render': f'remotion render src/index.ts {composition_id} out/video.mp4'},
        'dependencies': {'@remotion/cli': '^4.0.0', 'remotion': '^4.0.0',
                         'react': '^18.3.1', 'react-dom': '^18.3.1'},
        'devDependencies': {'@types/react': '^18.3.0', 'typescript': '^5.4.0'},
    }
    tsconfig = {'compilerOptions': {'target': 'ES2018', 'module': 'ES2020',
                                    'moduleResolution': 'node', 'jsx': 'react-jsx', 'strict': True,
                                    'esModuleInterop': True, 'skipLibCheck': True,
                                    'lib': ['DOM', 'ES2018']},
                'include': ['src']}
    files = {
        'package.json': json.dumps(package, indent=2) + '\n',
        'tsconfig.json': json.dumps(tsconfig, indent=2) + '\n',
        'src/index.ts': _REMOTION_INDEX_TS,
        'src/Root.tsx': _REMOTION_ROOT_TSX,
        'src/Main.tsx': _REMOTION_MAIN_TSX,
        'src/timeline.ts': _REMOTION_TIMELINE_TS.replace('__RR_DATA__', _json_literal(data), 1),
    }
    return _pack('remotion_project', {
        'files': files, 'public_copies': public, 'composition_id': composition_id,
        'frames': tl['frames'], 'warnings': warnings, 'installed': False, 'written': False,
        'next_steps': ['save the files into a new folder', 'copy each public_copies "from" file to its "to" path',
                       'npm install', 'npm run studio  (or npm run render)']},
        ['only text supplied in the timeline is drawn (React escapes it); RTL layers get dir="rtl"',
         'keyframes: composition seconds, position in pixels (element centre), scale factors, '
         'opacity 0..1; without keyframes text is centred',
         'dependency ranges are "^4.0.0" (Remotion) and "^18.3.1" (React); npm resolves exact versions'],
        ['motion/graphics/svg layers are placeholders that render nothing until re-created',
         'nothing is installed, written or rendered here; Remotion\'s licence terms apply to '
         'company use', 'audio files must be copied into public/ by the owner'])


# --------------------------------------------------------------------------- dispatcher

OPS = {
    'detect': detect, 'blender_script': blender_script, 'blender_render': blender_render,
    'ae_jsx': ae_jsx, 'nle_export': nle_export, 'tts_local': tts_local,
    'remotion_project': remotion_project,
}

EFFECTS = {
    'detect': 'read', 'blender_script': 'read', 'blender_render': 'write',
    'ae_jsx': 'read', 'nle_export': 'write', 'tts_local': 'write',
    'remotion_project': 'read',
}

# nle_export is declared 'write' conservatively: it only writes (and only then needs
# approve_write=True) when work_dir is given; without work_dir it just returns text.
EFFECT_NOTES = {
    'detect': 'runs only the allow-listed programs\' version flag; writes nothing',
    'nle_export': 'read unless work_dir is given (then writes new .edl/.fcpxml files)',
}


def run(op, params=None):
    """Validate and dispatch: run('detect', {}) -> {'op','result','assumptions','limits'}."""
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
