"""Red Rose V22: composing existing capabilities (topics 27.01-27.10).

Pure standard-library Python plus five existing pure Red Rose modules
(physics_v20, geometry_v20, thinking_v21, decision_v21, accounting_v21), which
are only called through their public `run(op, params)` / OPS tables. No file
I/O, no subprocess, no network, no printing. Every op validates its inputs
strictly (ValueError on unknown parameter or field names, wrong types,
bools-as-numbers, non-finite values, oversize lists) and caps its work.

Each op returns {'op', 'result', 'assumptions', 'limits'}. These are explicit,
deterministic rule engines and small numerical combinations: they do not render
images, play audio, call models or judge meaning. Anything they cannot verify
(licences, test evidence, human taste) is reported as such, never assumed.
"""
from __future__ import annotations

import inspect
import json
import math
import random
import re
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape as _xml_escape, quoteattr as _quoteattr

import accounting_v21
import decision_v21
import geometry_v20
import physics_v20
import thinking_v21

MAX_PARAMS = 24
MAX_ITEMS = 500
MAX_TEXT = 2000

TOPICS = {
    '27.01': 'layer_composer',
    '27.02': 'audio_scene_edl',
    '27.03': 'ik_physics',
    '27.04': 'retrieve_then_dispatch',
    '27.05': 'accounting_workflow',
    '27.06': 'variations',
    '27.07': 'critic_roles',
    '27.08': 'generic_contract',
    '27.09': 'capability_proposal',
    '27.10': 'originality_check',
}

TOPIC_NAMES_AR = {
    '27.01': 'دمج تصوير ورسم SVG',
    '27.02': 'دمج تحليل صوت مع اختيار اللقطات',
    '27.03': 'توليف تحريك مفاصل مع فيزياء',
    '27.04': 'دمج استرجاع معرفة مع تنفيذ',
    '27.05': 'تجميع مهام المحاسبة في Workflow',
    '27.06': 'توليد تجارب بصرية متعددة',
    '27.07': 'حوار نقدي بين أدوار محاكاة',
    '27.08': 'إعادة استخدام محرك موحد عبر مجالات',
    '27.09': 'اقتراح قدرة جديدة من فهرس قديم',
    '27.10': 'تطوير الجودة دون نسخ منتجات',
}

# The only modules this chapter may combine. Looked up at call time (module.run),
# so callers and tests see exactly which module was asked to execute.
MODULES = {
    'physics_v20': physics_v20,
    'geometry_v20': geometry_v20,
    'thinking_v21': thinking_v21,
    'decision_v21': decision_v21,
    'accounting_v21': accounting_v21,
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


def _text(value, name, *, max_len=200, allow_empty=False):
    if not isinstance(value, str):
        raise ValueError(f'{name} must be a string')
    s = value.strip()
    if not s and not allow_empty:
        raise ValueError(f'{name} must not be empty')
    if len(s) > max_len:
        raise ValueError(f'{name} is longer than {max_len} characters')
    return s


def _list(value, name, *, min_len=0, max_len=MAX_ITEMS):
    if not isinstance(value, (list, tuple)) or not min_len <= len(value) <= max_len:
        raise ValueError(f'{name} must be a list of {min_len}..{max_len} items')
    return list(value)


def _dict(value, name, *, allowed=None, required=(), max_keys=64):
    if not isinstance(value, dict) or len(value) > max_keys:
        raise ValueError(f'{name} must be a dict with at most {max_keys} keys')
    if not all(isinstance(k, str) for k in value):
        raise ValueError(f'{name} keys must be strings')
    if allowed is not None:
        bad = sorted(set(value) - set(allowed))
        if bad:
            raise ValueError(f'{name} has unknown field(s): {", ".join(bad)}')
    for key in required:
        if key not in value or value[key] is None:
            raise ValueError(f'{name} is missing {key!r}')
    return value


def _vec2(value, name, low=-1e6, high=1e6):
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError(f'{name} must be a list of 2 numbers')
    return [_num(v, low, high, f'{name}[{i}]') for i, v in enumerate(value)]


_WORD_RE = re.compile(r'\w+', re.UNICODE)


def _tokens(text):
    return [t.casefold() for t in _WORD_RE.findall(text)]


def _pack(op, result, assumptions, limits):
    return {'op': op, 'result': result, 'assumptions': list(assumptions),
            'limits': list(limits)}


# --------------------------------------------------------------------------- 27.01 layer_composer

_ID_RE = re.compile(r'^[A-Za-z][A-Za-z0-9_-]{0,63}$')
_FRAG_ID_RE = re.compile(r'(\sid\s*=\s*)(["\'])([^"\']*)\2')
_FRAG_REF_RE = re.compile(r'(url\(\s*#|(?:xlink:)?href\s*=\s*["\']#)([A-Za-z_][\w.\-]*)')
_FRAG_BANNED = re.compile(r'<\s*script|<\s*foreignObject|<!\s*(?:DOCTYPE|ENTITY)|\son\w+\s*=|'
                          r'javascript\s*:|<\?', re.IGNORECASE)
_SVG_NS = 'http://www.w3.org/2000/svg'
_XLINK_NS = 'http://www.w3.org/1999/xlink'
MAX_LAYERS = 64
MAX_FRAGMENT = 20_000

_EX_LAYERS = [
    {'id': 'title', 'kind': 'text', 'z': 30, 'opacity': 1.4, 'blend': 'normal',
     'text': 'Rose & <Co> "V22"', 'x': 80, 'y': 120, 'font_size': 64},
    {'id': 'plate', 'kind': 'photo_ref', 'z': 0, 'opacity': 1.0, 'blend': 'normal',
     'href': 'plates/shot_010.png'},
    {'id': 'glowA', 'kind': 'vector', 'z': 10, 'opacity': 0.6, 'blend': 'screen',
     'svg': '<defs><radialGradient id="g"><stop offset="0" stop-color="#fff"/>'
            '<stop offset="1" stop-color="#f00"/></radialGradient></defs>'
            '<circle id="c" cx="400" cy="300" r="200" fill="url(#g)"/>'},
    {'id': 'glowB', 'kind': 'vector', 'z': 20, 'opacity': 0.5, 'blend': 'multiply',
     'svg': '<defs><radialGradient id="g"><stop offset="0" stop-color="#00f"/>'
            '<stop offset="1" stop-color="#000"/></radialGradient></defs>'
            '<rect id="c" x="900" y="200" width="300" height="300" fill="url(#g)"/>'},
]


def _fmt(x):
    s = f'{x:.6g}'
    return '0' if s == '-0' else s


def _prefix_fragment(frag, prefix, name):
    """Rename every id="X" to prefix__X and rewrite local #X references to match."""
    if _FRAG_BANNED.search(frag):
        raise ValueError(f'{name} contains scripts, event handlers, foreignObject, '
                         'DOCTYPE/ENTITY or processing instructions; refused')
    ids = [m.group(3) for m in _FRAG_ID_RE.finditer(frag)]
    seen = set()
    for i in ids:
        if not re.match(r'^[A-Za-z_][\w.\-]*$', i):
            raise ValueError(f'{name} has an invalid id {i!r}')
        if i in seen:
            raise ValueError(f'{name} declares id {i!r} twice')
        seen.add(i)
    mapping = {i: f'{prefix}__{i}' for i in ids}
    out = _FRAG_ID_RE.sub(lambda m: f'{m.group(1)}{m.group(2)}{mapping[m.group(3)]}{m.group(2)}', frag)
    out = _FRAG_REF_RE.sub(lambda m: m.group(1) + mapping.get(m.group(2), m.group(2)), out)
    try:
        ET.fromstring(f'<g xmlns="{_SVG_NS}" xmlns:xlink="{_XLINK_NS}">{out}</g>')
    except ET.ParseError as exc:
        raise ValueError(f'{name} is not well-formed SVG/XML: {exc}') from None
    dangling = sorted({m.group(2) for m in _FRAG_REF_RE.finditer(frag)} - set(ids))
    return out, mapping, dangling


def layer_composer(*, layers=None, width=1920, height=1080, **extra):
    """Compose one SVG document from layers drawn in ascending z (ties keep input order).

    Layer fields: id, kind ('photo_ref' | 'vector' | 'text'), z, opacity (clamped
    to [0, 1] and reported), blend ('normal' | 'multiply' | 'screen'), plus
    href (photo_ref), svg fragment (vector) or text with optional x, y, font_size.
    Every id inside a vector fragment is prefixed with its layer id, and local
    url(#id)/href="#id" references are rewritten, so two fragments may both use
    id="g". Text is XML-escaped; scripts and event handlers are refused.
    """
    _no_extra(extra)
    width = _num(width, 1, 20000, 'width')
    height = _num(height, 1, 20000, 'height')
    if layers is None:
        layers = _EX_LAYERS
    layers = _list(layers, 'layers', min_len=1, max_len=MAX_LAYERS)
    parsed = []
    seen = set()
    for i, raw in enumerate(layers):
        name = f'layers[{i}]'
        _dict(raw, name, allowed={'id', 'kind', 'z', 'opacity', 'blend', 'href', 'svg', 'text',
                                  'x', 'y', 'font_size'}, required=('id', 'kind'))
        lid = raw['id']
        if not isinstance(lid, str) or not _ID_RE.match(lid):
            raise ValueError(f'{name}.id must match {_ID_RE.pattern}')
        if lid in seen:
            raise ValueError(f'layer id {lid!r} is used twice')
        seen.add(lid)
        kind = _choice(raw['kind'], {'photo_ref', 'vector', 'text'}, f'{name}.kind')
        z = _num(raw.get('z', 0), -1e6, 1e6, f'{name}.z')
        op_in = _num(raw.get('opacity', 1.0), -1e6, 1e6, f'{name}.opacity')
        opacity = min(1.0, max(0.0, op_in))
        blend = _choice(raw.get('blend', 'normal'), {'normal', 'multiply', 'screen'}, f'{name}.blend')
        need = {'photo_ref': 'href', 'vector': 'svg', 'text': 'text'}[kind]
        for other in ('href', 'svg', 'text'):
            if other != need and other in raw:
                raise ValueError(f'{name}: field {other!r} is not valid for kind {kind!r}')
        if kind != 'text':
            for other in ('x', 'y', 'font_size'):
                if other in raw:
                    raise ValueError(f'{name}: field {other!r} is only valid for kind "text"')
        if need not in raw:
            raise ValueError(f'{name} (kind {kind}) is missing {need!r}')
        entry = {'id': lid, 'kind': kind, 'z': z, 'index': i, 'opacity': opacity,
                 'opacity_requested': op_in, 'blend': blend}
        if kind == 'photo_ref':
            href = _text(raw['href'], f'{name}.href', max_len=1000)
            if re.match(r'^\s*(javascript|vbscript|data:text/html)', href, re.IGNORECASE):
                raise ValueError(f'{name}.href uses a refused scheme')
            entry['body'] = (f'<image href={_quoteattr(href)} x="0" y="0" width="{_fmt(width)}" '
                             f'height="{_fmt(height)}" preserveAspectRatio="xMidYMid slice"/>')
            entry['href'] = href
        elif kind == 'vector':
            frag = raw['svg']
            if not isinstance(frag, str) or not frag.strip() or len(frag) > MAX_FRAGMENT:
                raise ValueError(f'{name}.svg must be a non-empty string of <= {MAX_FRAGMENT} characters')
            body, mapping, dangling = _prefix_fragment(frag, lid, f'{name}.svg')
            entry['body'] = body
            entry['ids_renamed'] = mapping
            entry['dangling_refs'] = dangling
        else:
            txt = _text(raw['text'], f'{name}.text', max_len=MAX_TEXT, allow_empty=True)
            x = _num(raw.get('x', 0), -1e5, 1e5, f'{name}.x')
            y = _num(raw.get('y', 0), -1e5, 1e5, f'{name}.y')
            fs = _num(raw.get('font_size', 32), 1, 2000, f'{name}.font_size')
            entry['body'] = (f'<text x="{_fmt(x)}" y="{_fmt(y)}" font-size="{_fmt(fs)}">'
                             f'{_xml_escape(txt)}</text>')
        parsed.append(entry)

    ordered = sorted(parsed, key=lambda e: (e['z'], e['index']))
    parts = [f'<svg xmlns="{_SVG_NS}" xmlns:xlink="{_XLINK_NS}" width="{_fmt(width)}" '
             f'height="{_fmt(height)}" viewBox="0 0 {_fmt(width)} {_fmt(height)}">']
    report = []
    for order, e in enumerate(ordered):
        style = '' if e['blend'] == 'normal' else f' style="mix-blend-mode:{e["blend"]}"'
        parts.append(f'<g id="layer__{e["id"]}" data-kind="{e["kind"]}" '
                     f'opacity="{_fmt(e["opacity"])}"{style}>{e["body"]}</g>')
        row = {'id': e['id'], 'group_id': f'layer__{e["id"]}', 'kind': e['kind'], 'z': e['z'],
               'order': order, 'opacity': e['opacity'],
               'opacity_clamped': e['opacity'] != e['opacity_requested'], 'blend': e['blend']}
        if e['kind'] == 'vector':
            row['ids_renamed'] = e['ids_renamed']
            row['dangling_refs'] = e['dangling_refs']
        if e['kind'] == 'photo_ref':
            row['href'] = e['href']
        report.append(row)
    parts.append('</svg>')
    svg = ''.join(parts)
    try:
        ET.fromstring(svg)  # whole document must be well-formed
    except ET.ParseError as exc:
        raise ValueError(f'composed SVG is not well-formed: {exc}') from None
    all_ids = re.findall(r'\sid="([^"]*)"', svg)
    result = {'svg': svg, 'layers': report, 'order': [r['id'] for r in report],
              'ids_unique': len(all_ids) == len(set(all_ids)),
              'size_chars': len(svg)}
    return _pack('layer_composer', result,
                 ['photo layers are references (href) only; pixels are not read or embedded',
                  'blend modes are expressed as CSS mix-blend-mode; renderer support varies',
                  'ids are renamed by regex over id="..." and url(#..)/href="#.." references; '
                  'references inside CSS <style> blocks are not rewritten'],
                 [f'<= {MAX_LAYERS} layers', f'<= {MAX_FRAGMENT} characters per fragment',
                  'opacity clamped to [0, 1]', 'scripts, event handlers, foreignObject and DOCTYPE refused',
                  'output is SVG text; no rasterisation or visual check is done here'])


# --------------------------------------------------------------------------- 27.02 audio_scene_edl

_EX_SCENES = [{'start': 0.0, 'end': 4.2}, {'start': 4.2, 'end': 9.0}, {'start': 9.0, 'end': 12.0}]
_EX_SILENCES = [{'start': 3.6, 'end': 4.0}, {'start': 8.5, 'end': 8.8}, {'start': 11.0, 'end': 12.0}]
_EX_CUTS = [6.4]
MAX_INTERVALS = 2000


def _intervals(rows, name, duration_cap=86400.0):
    rows = _list(rows, name, max_len=MAX_INTERVALS)
    out = []
    for i, r in enumerate(rows):
        _dict(r, f'{name}[{i}]', required=('start', 'end'))
        s = _num(r['start'], 0, duration_cap, f'{name}[{i}].start')
        e = _num(r['end'], 0, duration_cap, f'{name}[{i}].end')
        if e <= s:
            raise ValueError(f'{name}[{i}] must have end > start')
        out.append([s, e])
    return out


def _merge(iv):
    out = []
    for s, e in sorted(iv):
        if out and s <= out[-1][1]:
            out[-1][1] = max(out[-1][1], e)
        else:
            out.append([s, e])
    return out


def audio_scene_edl(*, scenes=None, silences=None, cuts=None, tolerance=0.5, duration=None,
                    min_silence=0.0, guard=0.02, **extra):
    """Snap cut points to silence so no cut lands inside audible sound.

    scenes / silences use the timeline shape [{'start', 'end'}, ...] (seconds;
    extra keys on scenes are ignored). Audible spans are the complement of the
    (merged, >= min_silence) silences over [0, duration]. Candidate cuts are the
    internal scene boundaries plus any requested `cuts`. A cut already inside a
    silence is kept; an audible cut moves to the nearest point of the nearest
    silence within `tolerance` (kept `guard` seconds inside it when the silence
    is long enough); otherwise it is dropped, never forced into speech.
    """
    _no_extra(extra)
    if scenes is None and silences is None and cuts is None:
        scenes, silences, cuts = _EX_SCENES, _EX_SILENCES, _EX_CUTS
    if scenes is None or silences is None:
        raise ValueError('scenes and silences are both required (or give neither for the example)')
    sc = _intervals(scenes, 'scenes')
    if not sc:
        raise ValueError('scenes must not be empty')
    si = _intervals(silences, 'silences')
    req = [] if cuts is None else [_num(c, 0, 86400, f'cuts[{i}]')
                                   for i, c in enumerate(_list(cuts, 'cuts', max_len=MAX_INTERVALS))]
    tol = _num(tolerance, 0, 60, 'tolerance')
    min_sil = _num(min_silence, 0, 60, 'min_silence')
    guard = _num(guard, 0, 1, 'guard')
    end_all = max([e for _, e in sc] + [e for _, e in si])
    dur = end_all if duration is None else _num(duration, 0, 86400, 'duration', low_open=True)
    if end_all > dur + 1e-9:
        raise ValueError('scenes/silences extend past duration')
    sil = [iv for iv in _merge(si) if iv[1] - iv[0] >= min_sil]
    audible = []
    cursor = 0.0
    for s, e in sil:
        if s > cursor:
            audible.append([cursor, s])
        cursor = max(cursor, e)
    if cursor < dur:
        audible.append([cursor, dur])

    def overlap(a, b, c, d):
        return max(0.0, min(b, d) - max(a, c))

    scene_rows = []
    for i, (s, e) in enumerate(sc):
        quiet = sum(overlap(s, e, a, b) for a, b in sil)
        frac = min(1.0, max(0.0, 1.0 - quiet / (e - s)))
        scene_rows.append({'index': i, 'start': s, 'end': e, 'audible_fraction': round(frac, 6)})

    candidates = []
    for i, (s, e) in enumerate(sorted(sc)):
        for t in (s, e):
            if 1e-9 < t < dur - 1e-9:
                candidates.append((t, 'scene_boundary'))
    candidates += [(t, 'requested') for t in req if 1e-9 < t < dur - 1e-9]
    candidates.sort()

    decisions = []
    kept = []
    for t, source in candidates:
        inside = next((iv for iv in sil if iv[0] <= t <= iv[1]), None)
        if inside is not None:
            decisions.append({'requested': t, 'source': source, 'cut': t, 'moved_by': 0.0,
                              'action': 'kept', 'reason': 'already inside silence'})
            kept.append(t)
            continue
        best = None
        for a, b in sil:
            d = min(abs(t - a), abs(t - b))
            if d <= tol + 1e-12 and (best is None or (d, a) < (best[0], best[1][0])):
                best = (d, (a, b))
        if best is None:
            decisions.append({'requested': t, 'source': source, 'cut': None, 'moved_by': None,
                              'action': 'dropped',
                              'reason': f'audible and no silence within {tol} s: dropped rather than split speech'})
            continue
        a, b = best[1]
        g = min(guard, (b - a) / 2)
        target = min(max(t, a + g), b - g)
        decisions.append({'requested': t, 'source': source, 'cut': target,
                          'moved_by': round(target - t, 9), 'action': 'snapped',
                          'reason': f'audible at {t:g} s: moved to silence [{a:g}, {b:g}]'})
        kept.append(target)

    cut_points = []
    for t in sorted(kept):
        if not cut_points or t - cut_points[-1] > 1e-9:
            cut_points.append(t)
    bounds = [0.0] + cut_points + [dur]
    edl = []
    for i in range(len(bounds) - 1):
        a, b = bounds[i], bounds[i + 1]
        if b - a <= 1e-9:
            continue
        src = [r['index'] for r in scene_rows if overlap(a, b, r['start'], r['end']) > 1e-9]
        edl.append({'event': len(edl) + 1, 'start': a, 'end': b, 'duration': b - a,
                    'source_scenes': src})
    violations = [t for t in cut_points if any(a < t < b for a, b in audible)]
    result = {'scenes': scene_rows, 'audible_spans': audible, 'silences_used': sil,
              'decisions': decisions, 'cut_points': cut_points, 'edl': edl,
              'cuts_inside_audible': violations, 'duration': dur,
              'counts': {'candidates': len(candidates), 'kept': sum(d['action'] == 'kept' for d in decisions),
                         'snapped': sum(d['action'] == 'snapped' for d in decisions),
                         'dropped': sum(d['action'] == 'dropped' for d in decisions),
                         'events': len(edl)}}
    return _pack('audio_scene_edl', result,
                 ['silence intervals are given data (e.g. from ffmpeg silencedetect); '
                  'acoustic silence is not speech detection',
                  'audible = not silent; a cut on a silence edge is not inside an audible span',
                  'nearest silence measured to its closest edge; ties go to the earlier silence'],
                 [f'<= {MAX_INTERVALS} scenes, silences and requested cuts each',
                  'times in seconds within [0, 86400]', 'tolerance <= 60 s',
                  'EDL is a plan (start/end/source scenes); no media is cut here'])


# --------------------------------------------------------------------------- 27.03 ik_physics

_EX_CONTACTS = [{'start_frame': 0, 'end_frame': 13, 'plant': [0.15, 0.0]},
                {'start_frame': 20, 'end_frame': 23, 'plant': [0.45, 0.0]}]


def ik_physics(*, l1=0.5, l2=0.5, frames=24, fps=24.0, hip_start=(0.0, 0.85), hip_speed=0.6,
               bob_amplitude=0.02, bob_hz=2.0, contacts=None, swing_height=0.08, elbow='left',
               torso=0.6, spring_m=1.0, spring_k=60.0, spring_c=2.0, offset0=0.05,
               offset_v0=0.0, spring_dt=0.001, **extra):
    """Two-bone leg IK (geometry_v20.ik_two_bone) with planted-foot contacts and a
    spring-driven head offset (physics_v20.spring).

    Hip moves at hip_speed (units/s) with a vertical sine bob. During each contact
    range [start_frame, end_frame] the foot target is the plant point; between
    contacts the target is interpolated between plants with an arc of
    swing_height. Foot slide per frame = distance the solved foot moved since the
    previous frame when both frames are in the same contact (else None).
    A target out of reach is clamped by the IK and therefore reported as slide.
    The head is hip + (offset, torso) where offset follows the damped spring.
    """
    _no_extra(extra)
    l1 = _num(l1, 0, 100, 'l1', low_open=True)
    l2 = _num(l2, 0, 100, 'l2', low_open=True)
    frames = _int(frames, 2, 1000, 'frames')
    fps = _num(fps, 1, 240, 'fps')
    hip0 = _vec2(hip_start, 'hip_start', -1e4, 1e4)
    speed = _num(hip_speed, -100, 100, 'hip_speed')
    bob = _num(bob_amplitude, 0, 10, 'bob_amplitude')
    bob_hz = _num(bob_hz, 0, 60, 'bob_hz')
    swing_h = _num(swing_height, 0, 10, 'swing_height')
    elbow = _choice(elbow, {'left', 'right'}, 'elbow')
    torso = _num(torso, 0, 100, 'torso')
    if contacts is None:
        contacts = _EX_CONTACTS
    contacts = _list(contacts, 'contacts', max_len=100)
    cons = []
    for i, c in enumerate(contacts):
        _dict(c, f'contacts[{i}]', allowed={'start_frame', 'end_frame', 'plant'},
              required=('start_frame', 'end_frame', 'plant'))
        a = _int(c['start_frame'], 0, frames - 1, f'contacts[{i}].start_frame')
        b = _int(c['end_frame'], a, frames - 1, f'contacts[{i}].end_frame')
        cons.append((a, b, _vec2(c['plant'], f'contacts[{i}].plant', -1e4, 1e4)))
    cons.sort(key=lambda x: x[0])
    for i in range(1, len(cons)):
        if cons[i][0] <= cons[i - 1][1]:
            raise ValueError('contacts must not overlap')
    duration = (frames - 1) / fps
    spring_out = physics_v20.run('spring', {
        'm': spring_m, 'k': spring_k, 'c': spring_c, 'x0': offset0, 'v0': offset_v0,
        'duration': duration, 'dt': spring_dt, 'max_samples': physics_v20.MAX_SAMPLES})
    samples = spring_out['result']['samples']
    times = [s[0] for s in samples]

    def offset_at(t):
        if t <= times[0]:
            return samples[0][1]
        if t >= times[-1]:
            return samples[-1][1]
        lo, hi = 0, len(times) - 1
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if times[mid] <= t:
                lo = mid
            else:
                hi = mid
        u = (t - times[lo]) / (times[hi] - times[lo])
        return samples[lo][1] + u * (samples[hi][1] - samples[lo][1])

    def contact_of(f):
        for k, (a, b, p) in enumerate(cons):
            if a <= f <= b:
                return k
        return None

    def target_of(f):
        k = contact_of(f)
        if k is not None:
            return list(cons[k][2]), k
        if not cons:
            return [hip0[0] + speed * f / fps, hip0[1] - (l1 + l2) * 0.9 + swing_h], None
        prev = max((c for c in cons if c[1] < f), key=lambda c: c[1], default=None)
        nxt = min((c for c in cons if c[0] > f), key=lambda c: c[0], default=None)
        if prev is None or nxt is None:
            p = (prev or nxt)[2]
            return [p[0], p[1] + swing_h], None
        u = (f - prev[1]) / (nxt[0] - prev[1])
        return [prev[2][0] + u * (nxt[2][0] - prev[2][0]),
                prev[2][1] + u * (nxt[2][1] - prev[2][1]) + swing_h * math.sin(math.pi * u)], None

    rows = []
    prev_foot, prev_contact = None, None
    max_slide = 0.0
    unreachable = []
    for f in range(frames):
        t = f / fps
        hip = [hip0[0] + speed * t, hip0[1] + bob * math.sin(2 * math.pi * bob_hz * t)]
        target, k = target_of(f)
        ik = geometry_v20.run('ik_two_bone', {'l1': l1, 'l2': l2, 'target': target,
                                              'root': hip, 'elbow': elbow})['result']
        foot = ik['end']
        if k is not None and ik['clamped']:
            unreachable.append(f)
        if k is not None and prev_contact == k and prev_foot is not None:
            slide = math.hypot(foot[0] - prev_foot[0], foot[1] - prev_foot[1])
            max_slide = max(max_slide, slide)
        else:
            slide = None
        off = offset_at(t)
        rows.append({'frame': f, 't': t, 'hip': hip, 'knee': ik['joint'], 'foot': foot,
                     'foot_target': target, 'contact': k, 'foot_slide': slide,
                     'ik_clamped': ik['clamped'], 'head_offset': off,
                     'head': [hip[0] + off, hip[1] + torso]})
        prev_foot, prev_contact = foot, k
    half = frames // 2
    first_peak = max(abs(r['head_offset']) for r in rows[:half])
    second_peak = max(abs(r['head_offset']) for r in rows[half:])
    sp = spring_out['result']
    result = {'frames': rows, 'max_contact_foot_slide': max_slide,
              'contact_frames_unreachable': unreachable,
              'spring': {'damping_ratio': sp['damping_ratio'], 'regime': sp['regime'],
                         'natural_frequency_hz': sp['natural_frequency_hz'],
                         'first_half_peak_offset': first_peak, 'second_half_peak_offset': second_peak,
                         'decays': second_peak < first_peak},
              'modules_used': ['geometry_v20.ik_two_bone', 'physics_v20.spring']}
    return _pack('ik_physics', result,
                 ['2D sagittal leg; hip path is prescribed (not simulated)',
                  'foot slide is measured on the solved foot; it is 0 only while the plant is reachable',
                  'head offset is a linear damped spring sampled by linear interpolation; it does not feed back into the leg'],
                 ['frames <= 1000, fps <= 240', '<= 100 contact ranges',
                  'spring step guard and limits from physics_v20.spring apply',
                  'no self-collision, joint limits or ground penetration checks'])


# --------------------------------------------------------------------------- 27.04 retrieve_then_dispatch

_EX_TASK = 'simulate a ball dropped from two metres falling under gravity'
_EX_REFERENCES = [
    {'id': 'ref.fall', 'description': 'point mass falling under constant gravity, drop height and velocity'},
    {'id': 'ref.bounce_tutorial', 'description': 'tutorial article: how a ball bounces in animation'},
    {'id': 'ref.spring', 'description': 'damped spring oscillation for secondary motion'},
]
_EX_REGISTRY = {
    'ref.fall': {'module': 'physics_v20', 'op': 'fall', 'params': {'y0': 2.0, 'duration': 0.5}},
    'ref.spring': {'module': 'physics_v20', 'op': 'spring', 'params': {}},
}
_STOP = frozenset('a an the of to in on for and or with from by is are be as at this that it its'.split())


def _check_call(module, op, params, name):
    """Return a list of problems with one {module, op, params} call (empty = valid)."""
    problems = []
    if not isinstance(module, str) or module not in MODULES:
        return [f'{name}: module must be one of {sorted(MODULES)}']
    mod = MODULES[module]
    if not isinstance(op, str) or op not in mod.OPS:
        return [f'{name}: op must be one of {module}.OPS {sorted(mod.OPS)}']
    if not isinstance(params, dict):
        return [f'{name}: params must be a dict']
    if len(params) > getattr(mod, 'MAX_PARAMS', MAX_PARAMS):
        problems.append(f'{name}: too many params')
    sig = inspect.signature(mod.OPS[op])
    named = {p.name: p for p in sig.parameters.values()
             if p.kind not in (inspect.Parameter.VAR_KEYWORD, inspect.Parameter.VAR_POSITIONAL)}
    for key in params:
        if not isinstance(key, str):
            problems.append(f'{name}: parameter names must be strings')
        elif key not in named:
            problems.append(f'{name}: unknown parameter {key!r} for {module}.{op}; '
                            f'allowed {sorted(named)}')
    for pname, p in named.items():
        if p.default is inspect.Parameter.empty and pname not in params:
            problems.append(f'{name}: missing required parameter {pname!r}')
    return problems


def retrieve_then_dispatch(*, task=None, references=None, registry=None, top_k=3, **extra):
    """Rank references for a task by word overlap, then dispatch ONLY the top one,
    and ONLY if its id has an adapter in the supplied registry.

    Score = |task words ∩ reference words| / |task words| (stop words removed;
    ties broken by id). Registry: {ref_id: {'module', 'op', 'params'}} restricted
    to the five allowed modules; the adapter is contract-checked against the op
    signature before running module.run(op, params). A top reference without an
    adapter returns status 'reference_only_not_executed'.
    """
    _no_extra(extra)
    if task is None and references is None and registry is None:
        task, references, registry = _EX_TASK, _EX_REFERENCES, _EX_REGISTRY
    if task is None or references is None:
        raise ValueError('task and references are required')
    task = _text(task, 'task', max_len=MAX_TEXT)
    refs = _list(references, 'references', min_len=1, max_len=MAX_ITEMS)
    registry = {} if registry is None else _dict(registry, 'registry', max_keys=MAX_ITEMS)
    top_k = _int(top_k, 1, 50, 'top_k')
    task_tokens = {t for t in _tokens(task) if t not in _STOP}
    if not task_tokens:
        raise ValueError('task has no content words')
    ranked = []
    ids = set()
    for i, r in enumerate(refs):
        _dict(r, f'references[{i}]', allowed={'id', 'description', 'tags'}, required=('id', 'description'))
        rid = _text(r['id'], f'references[{i}].id', max_len=100)
        if rid in ids:
            raise ValueError(f'reference id {rid!r} is used twice')
        ids.add(rid)
        desc = _text(r['description'], f'references[{i}].description', max_len=MAX_TEXT)
        tags = [_text(t, f'references[{i}].tags[]', max_len=50)
                for t in _list(r.get('tags', []), f'references[{i}].tags', max_len=50)]
        words = {t for t in _tokens(desc + ' ' + ' '.join(tags)) if t not in _STOP}
        shared = sorted(task_tokens & words)
        ranked.append({'id': rid, 'score': round(len(shared) / len(task_tokens), 6),
                       'shared_words': shared, 'has_adapter': rid in registry})
    ranked.sort(key=lambda x: (-x['score'], x['id']))
    top = ranked[0]
    out = {'ranking': ranked[:top_k], 'chosen': top['id'], 'executed': False,
           'execution': None, 'adapter': None, 'problems': []}
    if top['score'] == 0:
        out['status'] = 'no_relevant_reference'
    elif top['id'] not in registry:
        out['status'] = 'reference_only_not_executed'
    else:
        adapter = _dict(registry[top['id']], f'registry[{top["id"]!r}]',
                        allowed={'module', 'op', 'params'}, required=('module', 'op'))
        params = adapter.get('params', {})
        problems = _check_call(adapter['module'], adapter['op'], params, f'adapter {top["id"]}')
        out['adapter'] = {'module': adapter['module'], 'op': adapter['op']}
        if problems:
            out['status'] = 'adapter_invalid_not_executed'
            out['problems'] = problems
        else:
            out['execution'] = MODULES[adapter['module']].run(adapter['op'], dict(params))
            out['executed'] = True
            out['status'] = 'executed'
    return _pack('retrieve_then_dispatch', out,
                 ['retrieval is bag-of-words overlap, not semantic understanding',
                  'only the single top-ranked reference is ever considered for execution',
                  'a reference description is knowledge, not an executable skill'],
                 ['adapters may only target physics_v20, geometry_v20, thinking_v21, decision_v21, accounting_v21',
                  f'<= {MAX_ITEMS} references', 'adapter params are name-checked here; values are validated by the target op'])


# --------------------------------------------------------------------------- 27.05 accounting_workflow

_EX_TENANT = 'rose-trading'
_EX_WF = {
    'invoices': [
        {'tenant': 'rose-trading', 'id': 1, 'supplier': 'Nile Paper', 'invoice_no': 'A-17',
         'amount': '900.00', 'date': '2026-03-01'},
        {'tenant': 'rose-trading', 'id': 2, 'supplier': 'nile paper', 'invoice_no': 'A17',
         'amount': '900.00', 'date': '2026-03-02'},
    ],
    'ledger': [
        {'tenant': 'rose-trading', 'id': 'L1', 'date': '2026-03-03', 'amount': '-900.00', 'ref': 'A-17'},
    ],
    'bank': [
        {'tenant': 'rose-trading', 'id': 'B1', 'date': '2026-03-04', 'amount': '-900.00', 'ref': 'A17'},
    ],
    'journal': [
        {'tenant': 'rose-trading', 'entry_id': 'J1', 'account': '5000', 'debit': '900.00'},
        {'tenant': 'rose-trading', 'entry_id': 'J1', 'account': '1010', 'credit': '900.00'},
    ],
}


def accounting_workflow(*, tenant=None, invoices=None, ledger=None, bank=None, journal=None,
                        currency_places=2, on_cross_tenant='block', **extra):
    """Chain accounting_v21 duplicate_invoices -> bank_reconcile -> trial_balance
    for ONE tenant. Every record must carry 'tenant' equal to the workflow
    tenant; any other (or missing) tenant blocks the whole run before any step
    is processed ('block' returns status 'blocked', 'raise' raises ValueError).
    The 'tenant' field is stripped before records reach accounting_v21.
    """
    _no_extra(extra)
    mode = _choice(on_cross_tenant, {'block', 'raise'}, 'on_cross_tenant')
    if tenant is None and all(x is None for x in (invoices, ledger, bank, journal)):
        tenant, invoices, ledger, bank, journal = (_EX_TENANT, _EX_WF['invoices'], _EX_WF['ledger'],
                                                   _EX_WF['bank'], _EX_WF['journal'])
    if tenant is None:
        raise ValueError('tenant is required')
    tenant = _text(tenant, 'tenant', max_len=100)
    _int(currency_places, 0, 4, 'currency_places')
    if (ledger is None) != (bank is None):
        raise ValueError('ledger and bank must be given together')
    if invoices is None and ledger is None and journal is None:
        raise ValueError('give at least one of invoices, ledger+bank or journal')
    sets = {'invoices': invoices, 'ledger': ledger, 'bank': bank, 'journal': journal}
    rejected = []
    clean = {}
    for key, rows in sets.items():
        if rows is None:
            continue
        rows = _list(rows, key, min_len=1, max_len=50_000)
        out = []
        for i, r in enumerate(rows):
            if not isinstance(r, dict):
                raise ValueError(f'{key}[{i}] must be a dict')
            owner = r.get('tenant')
            if owner != tenant:
                rejected.append({'set': key, 'index': i,
                                 'record_tenant': owner if isinstance(owner, str) else None,
                                 'reason': 'missing tenant' if owner is None else 'cross-tenant record'})
                continue
            out.append({k: v for k, v in r.items() if k != 'tenant'})
        clean[key] = out
    if rejected:
        if mode == 'raise':
            raise ValueError(f'{len(rejected)} record(s) do not belong to tenant {tenant!r}; '
                             f'first: {rejected[0]["set"]}[{rejected[0]["index"]}]')
        result = {'tenant': tenant, 'status': 'blocked', 'rejected': rejected[:200],
                  'rejected_count': len(rejected), 'steps': [], 'processed': False}
    else:
        steps = []
        if 'invoices' in clean:
            out = accounting_v21.run('duplicate_invoices', {'invoices': clean['invoices'],
                                                             'currency_places': currency_places})
            steps.append({'step': 'duplicate_invoices', 'counts': out['result']['counts'],
                          'output': out})
        if 'ledger' in clean:
            out = accounting_v21.run('bank_reconcile', {'ledger': clean['ledger'], 'bank': clean['bank'],
                                                         'currency_places': currency_places})
            steps.append({'step': 'bank_reconcile', 'counts': out['result']['counts'], 'output': out})
        if 'journal' in clean:
            out = accounting_v21.run('trial_balance', {'lines': clean['journal'],
                                                        'currency_places': currency_places})
            steps.append({'step': 'trial_balance', 'counts': out['result']['counts'],
                          'balanced': out['result']['balanced'], 'output': out})
        result = {'tenant': tenant, 'status': 'completed', 'rejected': [], 'rejected_count': 0,
                  'steps': steps, 'processed': True,
                  'record_counts': {k: len(v) for k, v in clean.items()}}
    return _pack('accounting_workflow', result,
                 ['tenant isolation is by the exact tenant string on each record',
                  'steps run in fixed order: duplicate_invoices, bank_reconcile, trial_balance',
                  'step results come unchanged from accounting_v21'],
                 ['one tenant per run; a single foreign or untagged record blocks the whole run',
                  'row limits and work budgets of accounting_v21 apply',
                  'checking aid only: no professional, audit, tax or legal opinion; nothing is filed or paid'])


# --------------------------------------------------------------------------- 27.06 variations

_EX_BASE = {'exposure': 0.0, 'contrast': 1.0, 'saturation': 1.0, 'grain': 0.1}
_EX_RANGES = {'exposure': [-1.0, 1.0], 'contrast': [0.8, 1.4], 'saturation': [0.6, 1.3]}
_EX_METRICS = {'natural_skin': {'param': 'saturation', 'target': 0.95},
               'punch': {'param': 'contrast', 'target': 1.2},
               'safe_exposure': {'param': 'exposure', 'target': 0.0}}
_EX_WEIGHTS = {'natural_skin': 0.5, 'punch': 0.3, 'safe_exposure': 0.2}


def variations(*, base=None, ranges=None, n=8, seed=0, metrics=None, weights=None, **extra):
    """Generate n variations of a numeric base spec with random.Random(seed), score
    each with explicit caller metrics and weights, rank them, and stop at
    'awaiting_human_pick' (no automatic final choice).

    ranges: {param: [low, high]} for the parameters to vary (uniform draw).
    metrics: {name: {'param', 'target'}}; metric value = 1 - |v - target| /
    (range width) clipped to [0, 1]. weights: {metric name: weight >= 0}.
    Score = weighted mean. Same seed and inputs -> identical output.
    """
    _no_extra(extra)
    if all(x is None for x in (base, ranges, metrics, weights)):
        base, ranges, metrics, weights = _EX_BASE, _EX_RANGES, _EX_METRICS, _EX_WEIGHTS
    if base is None or ranges is None or metrics is None or weights is None:
        raise ValueError('base, ranges, metrics and weights are all required')
    _dict(base, 'base', max_keys=64)
    b = {k: _num(v, -1e6, 1e6, f'base[{k!r}]') for k, v in base.items()}
    _dict(ranges, 'ranges', max_keys=64)
    if not ranges:
        raise ValueError('ranges must vary at least one parameter')
    rng_spec = {}
    for k, v in ranges.items():
        if k not in b:
            raise ValueError(f'ranges[{k!r}] is not a base parameter')
        lo, hi = _vec2(v, f'ranges[{k!r}]')
        if hi <= lo:
            raise ValueError(f'ranges[{k!r}] must have high > low')
        rng_spec[k] = (lo, hi)
    n = _int(n, 1, 200, 'n')
    seed = _int(seed, 0, 2 ** 63 - 1, 'seed')
    _dict(metrics, 'metrics', max_keys=64)
    if not metrics:
        raise ValueError('metrics must not be empty: scoring must be explicit')
    mspec = {}
    for name, m in metrics.items():
        _dict(m, f'metrics[{name!r}]', allowed={'param', 'target'}, required=('param', 'target'))
        if m['param'] not in b:
            raise ValueError(f'metrics[{name!r}].param is not a base parameter')
        mspec[name] = (m['param'], _num(m['target'], -1e6, 1e6, f'metrics[{name!r}].target'))
    _dict(weights, 'weights', max_keys=64)
    if set(weights) != set(mspec):
        raise ValueError('weights must name exactly the metrics')
    w = {k: _num(v, 0, 1e6, f'weights[{k!r}]') for k, v in weights.items()}
    wsum = sum(w.values())
    if wsum <= 0:
        raise ValueError('weights must not all be zero')
    rnd = random.Random(seed)
    out = []
    for i in range(n):
        params = dict(b)
        for k in sorted(rng_spec):
            lo, hi = rng_spec[k]
            params[k] = round(rnd.uniform(lo, hi), 6)
        scores = {}
        for name in sorted(mspec):
            p, target = mspec[name]
            width = (rng_spec[p][1] - rng_spec[p][0]) if p in rng_spec else max(1.0, abs(target))
            scores[name] = round(max(0.0, min(1.0, 1 - abs(params[p] - target) / width)), 6)
        total = round(sum(w[k] * scores[k] for k in scores) / wsum, 6)
        out.append({'id': f'var-{i + 1:03d}', 'params': params, 'metric_scores': scores, 'score': total})
    ranking = sorted(out, key=lambda v: (-v['score'], v['id']))
    for r, v in enumerate(ranking, 1):
        v['rank'] = r
    result = {'seed': seed, 'variations': out, 'ranking': [v['id'] for v in ranking],
              'status': 'awaiting_human_pick', 'final_choice': None,
              'note': 'ranking is a suggestion from the supplied metrics; a human must pick'}
    return _pack('variations', result,
                 ['metrics measure distance of a parameter to a caller target, not visual quality',
                  'uniform independent draws per varied parameter',
                  'the same seed and inputs reproduce the same variations and ranking (random.Random)'],
                 ['n <= 200, <= 64 parameters and metrics', 'no image is rendered or inspected',
                  'final_choice is always None: selection requires a human'])


# --------------------------------------------------------------------------- 27.07 critic_roles

_EX_PROPOSAL = {
    'title': 'Add spring-based head bob to the walk cycle',
    'claims': [{'text': 'reduces stiffness of the walk', 'evidence': 'side-by-side preview frames 1-48'},
               {'text': 'always looks natural for every character'}],
    'tests': [],
    'limits': ['2D only'],
    'assumptions': [],
}
_ABSOLUTE = re.compile(r'\b(always|never|guaranteed|perfect|flawless|100\s*%|zero risk)\b', re.IGNORECASE)
_TESTED = re.compile(r'\b(tested|verified|proven|validated)\b', re.IGNORECASE)


def critic_roles(*, proposal=None, **extra):
    """Run deterministic rule checks under four simulated role templates.

    proposer restates the proposal; critic checks completeness (missing tests
    -> blocking, missing limits -> major, missing assumptions -> minor); skeptic
    checks claims (no evidence -> major, absolute wording -> minor, 'tested'
    claimed with no tests -> blocking); judge folds issues into a verdict
    (blocked / revise / accept_with_notes / accept). All roles are rules inside
    this one system, not separate models.
    """
    _no_extra(extra)
    if proposal is None:
        proposal = _EX_PROPOSAL
    _dict(proposal, 'proposal', allowed={'title', 'claims', 'tests', 'limits', 'assumptions', 'risks'},
          required=('title',))
    title = _text(proposal['title'], 'proposal.title', max_len=500)
    claims = []
    for i, c in enumerate(_list(proposal.get('claims', []), 'proposal.claims', max_len=200)):
        if isinstance(c, str):
            c = {'text': c}
        _dict(c, f'proposal.claims[{i}]', allowed={'text', 'evidence'}, required=('text',))
        ev = c.get('evidence')
        claims.append({'text': _text(c['text'], f'proposal.claims[{i}].text', max_len=MAX_TEXT),
                       'evidence': None if ev is None else _text(ev, f'proposal.claims[{i}].evidence',
                                                                 max_len=MAX_TEXT, allow_empty=True)})
    lists = {}
    for key in ('tests', 'limits', 'assumptions', 'risks'):
        lists[key] = [_text(x, f'proposal.{key}[{i}]', max_len=MAX_TEXT)
                      for i, x in enumerate(_list(proposal.get(key, []), f'proposal.{key}', max_len=200))]
    issues = []

    def add(role, severity, code, message):
        issues.append({'role': role, 'severity': severity, 'code': code, 'message': message})

    if not lists['tests']:
        add('critic', 'blocking', 'missing_tests', 'no tests listed: the proposal cannot be evaluated')
    if not lists['limits']:
        add('critic', 'major', 'missing_limits', 'no limits stated')
    if not lists['assumptions']:
        add('critic', 'minor', 'missing_assumptions', 'no assumptions stated')
    if not claims:
        add('critic', 'minor', 'no_claims', 'no claims: the benefit is not stated')
    for i, c in enumerate(claims):
        if not c['evidence']:
            add('skeptic', 'major', 'unsupported_claim', f'claim {i}: "{c["text"][:120]}" has no evidence')
        if _ABSOLUTE.search(c['text']):
            add('skeptic', 'minor', 'absolute_wording', f'claim {i} uses absolute wording')
        if _TESTED.search(c['text']) and not lists['tests']:
            add('skeptic', 'blocking', 'tested_claim_without_tests',
                f'claim {i} says tested/verified but no tests are listed')
    sev = [x['severity'] for x in issues]
    if 'blocking' in sev:
        verdict = 'blocked'
    elif 'major' in sev:
        verdict = 'revise'
    elif sev:
        verdict = 'accept_with_notes'
    else:
        verdict = 'accept'
    roles = [
        {'role': 'proposer', 'template': 'restate', 'statement':
            f'{title}: {len(claims)} claim(s), {len(lists["tests"])} test(s), '
            f'{len(lists["limits"])} limit(s), {len(lists["assumptions"])} assumption(s)'},
        {'role': 'critic', 'template': 'completeness_rules',
         'issues': sum(x['role'] == 'critic' for x in issues)},
        {'role': 'skeptic', 'template': 'claim_evidence_rules',
         'issues': sum(x['role'] == 'skeptic' for x in issues)},
        {'role': 'judge', 'template': 'severity_fold', 'verdict': verdict},
    ]
    result = {'single_system_simulated_roles': True,
              'disclosure': 'these roles are deterministic rule templates run by one system, '
                            'not independent models or people',
              'roles': roles, 'issues': issues, 'verdict': verdict,
              'counts': {s: sev.count(s) for s in ('blocking', 'major', 'minor')}}
    return _pack('critic_roles', result,
                 ['checks are structural rules (presence, wording), not understanding of the content',
                  'evidence strings are accepted as given; their truth is not verified'],
                 ['<= 200 claims and items per list', 'no independent model, person or tool is consulted'])


# --------------------------------------------------------------------------- 27.08 generic_contract

_EX_PIPELINE = [
    {'module': 'physics_v20', 'op': 'spring', 'params': {'k': 80.0}},
    {'module': 'geometry_v20', 'op': 'ik_two_bone', 'params': {'target': [1.2, 0.5]}},
]


def generic_contract(*, pipeline=None, declared_modules=None, execute=False, **extra):
    """Check every {module, op, params} call against that op's Python signature
    (inspect.signature) for the five allowed modules, before anything runs.

    Unknown parameter names, missing required parameters, unknown modules or ops
    are reported per call. With execute=True the pipeline runs (via module.run)
    ONLY if every call is valid. The dependency footprint lists the modules the
    pipeline touches; with declared_modules it also reports declared-but-unused
    (bloat) and used-but-undeclared modules.
    """
    _no_extra(extra)
    if pipeline is None:
        pipeline = _EX_PIPELINE
    calls = _list(pipeline, 'pipeline', min_len=1, max_len=100)
    execute = _bool(execute, 'execute')
    checks = []
    used = []
    for i, c in enumerate(calls):
        _dict(c, f'pipeline[{i}]', allowed={'module', 'op', 'params'}, required=('module', 'op'))
        problems = _check_call(c['module'], c['op'], c.get('params', {}), f'pipeline[{i}]')
        checks.append({'index': i, 'module': c['module'] if isinstance(c['module'], str) else None,
                       'op': c['op'] if isinstance(c['op'], str) else None,
                       'valid': not problems, 'problems': problems})
        if isinstance(c['module'], str) and c['module'] in MODULES and c['module'] not in used:
            used.append(c['module'])
    all_valid = all(x['valid'] for x in checks)
    footprint = sorted(used)
    result = {'calls': checks, 'all_valid': all_valid, 'footprint': footprint,
              'footprint_size': len(footprint),
              'allowed_but_unused': sorted(set(MODULES) - set(footprint)),
              'executed': False, 'outputs': None}
    if declared_modules is not None:
        decl = [_choice(m, set(MODULES), f'declared_modules[{i}]')
                for i, m in enumerate(_list(declared_modules, 'declared_modules', max_len=len(MODULES)))]
        result['declared_but_unused'] = sorted(set(decl) - set(footprint))
        result['used_but_undeclared'] = sorted(set(footprint) - set(decl))
        result['bloat'] = bool(result['declared_but_unused'])
    if execute:
        if all_valid:
            result['outputs'] = [MODULES[c['module']].run(c['op'], dict(c.get('params', {})))
                                 for c in calls]
            result['executed'] = True
        else:
            result['execution_refused'] = 'contract violations found; nothing was executed'
    return _pack('generic_contract', result,
                 ['the contract is the op function signature (parameter names and required ones)',
                  'parameter VALUES are validated by each target op when it runs, not here'],
                 ['<= 100 calls per pipeline', 'only physics_v20, geometry_v20, thinking_v21, '
                  'decision_v21 and accounting_v21 are allowed',
                  'execution is opt-in and all-or-nothing on contract validity'])


# --------------------------------------------------------------------------- 27.09 capability_proposal

PERMISSIVE_LICENCES = frozenset({'mit', 'bsd-2-clause', 'bsd-3-clause', 'apache-2.0', 'isc', 'zlib',
                                 'unlicense', 'cc0-1.0', '0bsd', 'psf-2.0', 'bsl-1.0'})
_EX_ENTRY = {'title': 'Verlet rope solver for hanging props', 'source': 'catalogue entry R-0412',
             'licence': 'MIT'}
_TEST_FILE_RE = re.compile(r'^test_[A-Za-z0-9_]{1,80}\.py$')


def capability_proposal(*, entry=None, status='proposed', test_evidence=None,
                        needs_owner_review=False, target_module=None, **extra):
    """Turn a reference entry {title, source, licence} into an implementation-plan
    record. status 'proposed' is the default; 'registered' is refused unless
    test_evidence {test_file, passing, failing} shows >= 1 passing and 0 failing
    tests, and is never allowed while the licence is under owner review.
    Licences outside a permissive allow-list (GPL, unknown, missing...) are
    refused unless needs_owner_review=True, which marks the record.
    """
    _no_extra(extra)
    if entry is None:
        entry = _EX_ENTRY
    _dict(entry, 'entry', allowed={'title', 'source', 'licence', 'notes'}, required=('title', 'source'))
    title = _text(entry['title'], 'entry.title', max_len=300)
    source = _text(entry['source'], 'entry.source', max_len=500)
    licence_raw = entry.get('licence')
    licence = '' if licence_raw is None else _text(licence_raw, 'entry.licence', max_len=100, allow_empty=True)
    status = _choice(status, {'proposed', 'registered'}, 'status')
    review = _bool(needs_owner_review, 'needs_owner_review')
    norm = licence.casefold().replace(' ', '-')
    if norm in PERMISSIVE_LICENCES:
        lic_class = 'permissive'
    elif not norm or norm in {'unknown', 'none', 'proprietary', 'n/a'}:
        lic_class = 'unknown'
    elif re.search(r'gpl|agpl|lgpl|mpl|epl|sa|nc|cddl|eupl|sspl|commons-clause', norm):
        lic_class = 'restrictive_or_copyleft'
    else:
        lic_class = 'unrecognised'
    if lic_class != 'permissive' and not review:
        raise ValueError(f'licence {licence or "(missing)"!r} is {lic_class}: refused unless '
                         'needs_owner_review=True')
    licence_review = 'needs_owner_review' if lic_class != 'permissive' else 'permissive_allow_list'
    evidence = None
    if test_evidence is not None:
        _dict(test_evidence, 'test_evidence', allowed={'test_file', 'passing', 'failing'},
              required=('test_file', 'passing'))
        tf = test_evidence['test_file']
        if not isinstance(tf, str) or not _TEST_FILE_RE.match(tf):
            raise ValueError('test_evidence.test_file must look like test_<name>.py')
        evidence = {'test_file': tf, 'passing': _int(test_evidence['passing'], 0, 1_000_000,
                                                     'test_evidence.passing'),
                    'failing': _int(test_evidence.get('failing', 0), 0, 1_000_000, 'test_evidence.failing'),
                    'verified_by_this_op': False}
    if status == 'registered':
        if evidence is None or evidence['passing'] < 1 or evidence['failing'] != 0:
            raise ValueError("status 'registered' refused: needs test_evidence with >= 1 passing "
                             'and 0 failing tests')
        if licence_review == 'needs_owner_review':
            raise ValueError("status 'registered' refused while the licence needs owner review")
    tm = None if target_module is None else _text(target_module, 'target_module', max_len=100)
    slug = re.sub(r'[^a-z0-9]+', '_', title.casefold()).strip('_')[:60] or 'capability'
    record = {'capability_id': slug, 'title': title, 'source': source, 'licence': licence or None,
              'licence_class': lic_class, 'licence_review': licence_review, 'status': status,
              'target_module': tm, 'test_evidence': evidence,
              'plan_steps': ['read the reference and restate the algorithm in own words',
                             'write a native pure-Python module with strict validation',
                             'write unittest acceptance tests before registering',
                             'record assumptions and limits honestly',
                             'register only with passing test evidence'],
              'note': 'plan record only: nothing was implemented, copied or executed'}
    return _pack('capability_proposal', {'record': record},
                 ['licence classification is by name against a small allow-list, not legal review',
                  'test evidence is caller-supplied and not re-run here'],
                 ['only proposed and registered statuses', 'registration needs >= 1 passing and 0 failing tests',
                  'non-permissive or unknown licences need an explicit owner-review mark'])


# --------------------------------------------------------------------------- 27.10 originality_check

_EX_DELIVERABLE = {
    'title': 'Cola Rush summer promo',
    'assets': [
        {'name': 'hero_shot.png', 'origin': 'original', 'licence': 'owner-original'},
        {'name': 'music_bed.wav', 'origin': 'licensed', 'licence': 'CC-BY-4.0'},
        {'name': 'logo.svg', 'origin': 'owner_supplied'},
    ],
}
_EX_PROTECTED = ['Cola Rush', 'MegaSoft']


def originality_check(*, deliverable=None, protected_names=None, **extra):
    """Rights check for a deliverable spec {title, assets: [{name, origin, licence,
    attribution, attribution_required}]}: origin must be original | licensed |
    owner_supplied, licence must be present, attribution must be present when
    required (explicitly, or by a CC-BY* licence). Protected brand/product names
    (caller list, case-insensitive whole words) in the title or asset names are
    flagged.
    """
    _no_extra(extra)
    if deliverable is None and protected_names is None:
        deliverable, protected_names = _EX_DELIVERABLE, _EX_PROTECTED
    if deliverable is None:
        raise ValueError('deliverable is required')
    _dict(deliverable, 'deliverable', allowed={'title', 'assets'}, required=('title', 'assets'))
    title = _text(deliverable['title'], 'deliverable.title', max_len=500)
    assets = _list(deliverable['assets'], 'deliverable.assets', max_len=MAX_ITEMS)
    names = [_text(p, f'protected_names[{i}]', max_len=100)
             for i, p in enumerate(_list(protected_names or [], 'protected_names', max_len=MAX_ITEMS))]
    issues = []
    rows = []
    for i, a in enumerate(assets):
        _dict(a, f'assets[{i}]', allowed={'name', 'origin', 'licence', 'attribution', 'attribution_required'},
              required=('name',))
        name = _text(a['name'], f'assets[{i}].name', max_len=300)
        origin = a.get('origin')
        lic = a.get('licence')
        lic = lic.strip() if isinstance(lic, str) else None
        attr = a.get('attribution')
        attr = attr.strip() if isinstance(attr, str) else None
        req = a.get('attribution_required', False)
        req = _bool(req, f'assets[{i}].attribution_required')
        if lic and re.match(r'^cc-by', lic, re.IGNORECASE):
            req = True
        if origin not in ('original', 'licensed', 'owner_supplied'):
            issues.append({'asset': name, 'severity': 'blocking', 'code': 'missing_or_invalid_origin',
                           'message': 'origin must be original, licensed or owner_supplied'})
        if not lic:
            issues.append({'asset': name, 'severity': 'blocking', 'code': 'missing_licence',
                           'message': 'licence is missing'})
        if req and not attr:
            issues.append({'asset': name, 'severity': 'blocking', 'code': 'missing_attribution',
                           'message': 'attribution required but not given'})
        rows.append({'name': name, 'origin': origin if isinstance(origin, str) else None,
                     'licence': lic, 'attribution_required': req, 'attribution': attr})
    brand_hits = []
    for p in names:
        pat = re.compile(r'(?<!\w)' + re.escape(p) + r'(?!\w)', re.IGNORECASE)
        if pat.search(title):
            brand_hits.append({'name': p, 'where': 'title'})
        for r in rows:
            if pat.search(r['name']):
                brand_hits.append({'name': p, 'where': f'asset:{r["name"]}'})
    for h in brand_hits:
        issues.append({'asset': None if h['where'] == 'title' else h['where'][6:], 'severity': 'major',
                       'code': 'protected_name', 'message': f'protected name {h["name"]!r} in {h["where"]}'})
    result = {'assets': rows, 'issues': issues, 'protected_name_hits': brand_hits,
              'verdict': 'clear' if not issues else 'needs_fix'}
    return _pack('originality_check', result,
                 ['origin, licence and attribution are taken as declared; documents are not inspected',
                  'protected names come only from the caller list; matching is literal whole-word'],
                 [f'<= {MAX_ITEMS} assets and protected names', 'no image, audio or trademark-database search',
                  'not legal advice'])


# --------------------------------------------------------------------------- dispatch

OPS = {
    'layer_composer': layer_composer, 'audio_scene_edl': audio_scene_edl, 'ik_physics': ik_physics,
    'retrieve_then_dispatch': retrieve_then_dispatch, 'accounting_workflow': accounting_workflow,
    'variations': variations, 'critic_roles': critic_roles, 'generic_contract': generic_contract,
    'capability_proposal': capability_proposal, 'originality_check': originality_check,
}


def run(op, params=None):
    """Validate and dispatch: run('variations', {'seed': 3}) -> {'op','result','assumptions','limits'}."""
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
