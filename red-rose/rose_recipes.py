"""Red Rose V29 (W08): eight validated recipes with gates and a one-command runner.

A recipe is a JSON file in ``recipes/`` (see references/RECIPES.md): ordered steps,
each calling one catalogue op through ``rose_run.run_op`` and then checking its gates.

    python -X utf8 rose.py recipes
    python -X utf8 rose.py recipe show ID
    python -X utf8 rose.py recipe validate
    python -X utf8 rose.py recipe run ID key=value ... --work DIR [--approve-write]
    python -X utf8 rose.py recipe selftest ID

Rules of the runner:
* A step that writes (effect write, or a save into a file) does nothing without
  ``--approve-write``: read steps still run, the run lists ``would_write`` and exits 3.
* A failing gate stops the run at that step (exit 1) and names the gate.
* Evidence (one envelope JSON per step) goes into the work folder only when the
  write was approved. Nothing is written under the owner's private folder.
* A missing required input is outcome ``needs_input`` (exit 6): nothing ran and nothing
  was written; ``missing`` lists each question (Arabic), its allowed values and a suggestion.
  The agent asks that one question and runs nothing else. No placeholder text.
* ``status`` in the run envelope always equals ``outcome``; the recipe's own readiness is
  ``recipe_status``.
"""
from __future__ import annotations

import html
import json
import re
import subprocess
import tempfile
from fractions import Fraction
from pathlib import Path

import rose_io as rio
import rose_run as R

ROOT = Path(__file__).resolve().parent
RECIPES_DIR = ROOT / 'recipes'
EXPECTED_IDS = ('title-frame-ar', 'title-clip-mp4', 'shot-report-recut', 'captions-from-words',
                'loudness-fix', 'bank-reconcile', 'iphone-export', 'beat-synced-cut')
STATUSES = ('ready', 'draft')
PLACES = ('any', 'needs_ffmpeg', 'pc_only')
EFFECTS = ('read', 'write')
CHECKS = ('verify_video', 'file_exists', 'json_path', 'equals_input', 'not_example')
INPUT_TYPES = ('string', 'path', 'number', 'integer', 'bool', 'json_file')
RULES = ('aac_in_mp4', 'no_black_first_frame', 'no_fade_from_black', 'no_overlays_unless_named',
         'captions_exact_words', 'arabic_shaped', 'frames_match_duration', 'even_dimensions')
BLACK_MEAN_MAX = 12.0          # mean gray value (0..255) of the first decoded frame
_ARABIC = re.compile('[؀-ۿ]')
_LATIN = re.compile('[A-Za-z]')
_WHOLE = re.compile(r'^\$\{([^}]+)\}$')
_PART = re.compile(r'\$\{([^}]+)\}')
_STEP_REF = re.compile(r'^s(\d+)\.(.+)$')
_IDENT = re.compile(r'^[a-z][a-z0-9_]*$')
_SVG_TEXT = re.compile(r'<text[^>]*>([^<]*)</text>')
_OUTPUT_NAMES = tuple(R.OUTPUT_PARAM_NAMES)


# --------------------------------------------------------------------------- loading

def load_all():
    """Every recipe JSON in recipes/, sorted by id."""
    out = []
    for path in sorted(RECIPES_DIR.glob('*.json')):
        data = json.loads(path.read_text(encoding='utf-8-sig'))
        data['_file'] = str(path)
        out.append(data)
    return sorted(out, key=lambda r: str(r.get('id')))


def get(recipe_id):
    recipes = load_all()
    for rec in recipes:
        if rec.get('id') == recipe_id:
            return rec
    raise rio.ParamError(f'unknown recipe: {recipe_id}', allowed=[r.get('id') for r in recipes],
                         hint='list them with: rose.py recipes')


def _steps(rec):
    return list(rec.get('steps') or [])


def _gates(step):
    gate = step.get('gate')
    if gate is None:
        return []
    return list(gate) if isinstance(gate, list) else [gate]


def _is_write(step):
    return step.get('effect') == 'write' or bool(step.get('save'))


def _has_writes(rec):
    return any(_is_write(s) for s in _steps(rec))


# --------------------------------------------------------------------------- validation

def _refs_in(value):
    if isinstance(value, dict):
        for v in value.values():
            yield from _refs_in(v)
    elif isinstance(value, list):
        for v in value:
            yield from _refs_in(v)
    elif isinstance(value, str):
        yield from _PART.findall(value)


def validate_recipe(rec):
    errors = []
    rid = rec.get('id', '?')

    def bad(msg):
        errors.append(f'{rid}: {msg}')
    if rid not in EXPECTED_IDS:
        bad('id is not one of the fixed recipe ids')
    if rec.get('_file') and Path(rec['_file']).stem != rid:
        bad('file name must equal the id')
    for key in ('title_ar', 'title_en', 'deliver_ar'):
        if not isinstance(rec.get(key), str) or not rec.get(key).strip():
            bad(f'{key} is required')
    if rec.get('status') not in STATUSES:
        bad('status must be ready or draft')
    if rec.get('place') not in PLACES:
        bad('place must be any, needs_ffmpeg or pc_only')
    when = rec.get('when') or []
    if sum(1 for w in when if _ARABIC.search(w)) < 2:
        bad('when needs at least 2 Arabic example requests')
    if not any(_LATIN.search(w) and not _ARABIC.search(w) for w in when):
        bad('when needs at least 1 English example request')
    if not isinstance(rec.get('tags'), list) or not rec.get('tags'):
        bad('tags must be a non-empty list')
    input_specs = {}
    for spec in rec.get('inputs') or []:
        key = spec.get('key', '')
        if not _IDENT.match(key or ''):
            bad(f'input key {key!r} must be snake_case')
        if key in input_specs:
            bad(f'duplicate input {key}')
        if spec.get('type', 'string') not in INPUT_TYPES:
            bad(f'input {key}: bad type')
        if spec.get('required') and (not spec.get('question_ar') or not spec.get('suggest_ar')):
            bad(f'input {key}: required inputs need question_ar and suggest_ar')
        input_specs[key] = spec
    for rule in rec.get('rules') or []:
        if rule not in RULES:
            bad(f'unknown rule {rule}')
    steps = _steps(rec)
    if not steps:
        bad('at least one step is required')
    approval_steps = {a.get('step') for a in rec.get('approvals') or []}
    seen = set()
    for idx, step in enumerate(steps, 1):
        n = step.get('n')
        if n != idx:
            bad(f'step numbers must be 1..N in order (found {n} at {idx})')
        if not step.get('do_ar'):
            bad(f'step {n}: do_ar missing')
        if step.get('effect') not in EFFECTS:
            bad(f'step {n}: effect must be read or write')
        if _is_write(step) and not step.get('approval'):
            bad(f'step {n}: write or save steps must have approval true')
        if _is_write(step) and n not in approval_steps:
            bad(f'step {n}: write step is not listed in approvals')
        if step.get('effect') == 'read' and step.get('approval') and not step.get('save'):
            bad(f'step {n}: approval true on a read step without save is not allowed')
        try:
            adapter, op_name, _shape = R.resolve_id(step.get('op', ''))
        except rio.ParamError as exc:
            bad(f'step {n}: unknown op {step.get("op")}: {exc}')
            seen.add(n)
            continue
        full_id = adapter if op_name is None else f'{adapter}.{op_name}'
        schema, complete, _src = R.schema_for(adapter, op_name)
        args = step.get('args') or {}
        for key in args:
            if schema and complete and key not in schema:
                bad(f'step {n}: {key} is not a parameter of {full_id} (allowed: {", ".join(sorted(schema))})')
        refs = list(_refs_in(args)) + [r for v in (step.get('save') or {}).values() for r in _PART.findall(v)]
        for ref in refs:
            head = ref.split('|')[0].strip()
            if head == 'work':
                continue
            m = _STEP_REF.match(head)
            if m:
                if int(m.group(1)) not in seen:
                    bad(f'step {n}: reference {head} points at a later or missing step')
            elif head not in input_specs:
                bad(f'step {n}: reference {head} is not an input')
        gates = _gates(step)
        if not gates:
            bad(f'step {n}: every step needs a gate')
        for gate in gates:
            if gate.get('check') not in CHECKS:
                bad(f'step {n}: gate check must be one of {", ".join(CHECKS)}')
            if not gate.get('text_ar'):
                bad(f'step {n}: gate text_ar missing')
            if not isinstance(gate.get('expect'), dict):
                bad(f'step {n}: gate expect must be an object')
        seen.add(n)
    if not any(s.get('deliver') for s in steps):
        bad('at least one step must be marked deliver')
    st = rec.get('selftest')
    if not isinstance(st, dict) or not isinstance(st.get('inputs'), dict):
        bad('selftest needs inputs')
    return errors


def validate(recipes=None):
    """-> list of error strings (empty when every recipe is valid)."""
    recipes = load_all() if recipes is None else recipes
    errors = []
    ids = [r.get('id') for r in recipes]
    for missing in sorted(set(EXPECTED_IDS) - set(ids)):
        errors.append(f'{missing}: recipe file is missing')
    if len(set(ids)) != len(ids):
        errors.append('duplicate recipe ids')
    for rec in recipes:
        errors.extend(validate_recipe(rec))
    return errors


# --------------------------------------------------------------------------- inputs

def _input_specs(rec):
    return {spec['key']: spec for spec in rec.get('inputs') or []}


def _coerce_input(key, spec, value):
    kind = spec.get('type', 'string')
    if kind == 'json_file':
        if isinstance(value, (list, dict)):
            data = value
        else:
            path = Path(str(value)).expanduser()
            if not path.is_file():
                raise rio.ParamError(f'{key}: file not found: {path}', hint=spec.get('question_ar'))
            try:
                data = json.loads(rio.read_text_bytes(path))
            except json.JSONDecodeError as exc:
                raise rio.ParamError(f'{key}: not valid JSON ({exc.msg})', hint=spec.get('question_ar'))
        if isinstance(data, dict) and 'words' in data:
            data = data['words']
        return data
    if kind in ('number', 'integer'):
        if isinstance(value, bool):
            raise rio.ParamError(f'{key} expects a number')
        if isinstance(value, (int, float)):
            return value
        return rio.coerce(key, str(value), 'integer' if kind == 'integer' else 'number')
    if kind == 'bool':
        if isinstance(value, bool):
            return value
        return rio.coerce(key, str(value), 'bool')
    return value


def _resolve_inputs(rec, given):
    specs = _input_specs(rec)
    unknown = sorted(k for k in given if k not in specs)
    if unknown:
        raise rio.ParamError('unknown input(s): ' + ', '.join(unknown), allowed=sorted(specs),
                             hint='rose.py recipe show ' + rec['id'])
    resolved, missing = {}, []
    for key, spec in specs.items():
        if key in given and given[key] not in (None, ''):
            resolved[key] = _coerce_input(key, spec, given[key])
        elif spec.get('default') is not None:
            resolved[key] = _coerce_input(key, spec, spec['default'])
        elif spec.get('required'):
            missing.append({'key': key, 'question_ar': spec.get('question_ar'),
                            'suggest_ar': spec.get('suggest_ar')})
    return resolved, missing


# --------------------------------------------------------------------------- references

def _transform(name, value):
    if name.startswith('keep:'):
        keys = [k for k in name[5:].split(',') if k]
        if not isinstance(value, list):
            raise rio.ParamError(f'keep needs a list, got {type(value).__name__}')
        return [{k: item[k] for k in keys if k in item} for item in value if isinstance(item, dict)]
    if name.startswith('first:'):
        return list(value)[:int(name[6:])]
    if name.startswith('consecutive:'):
        pts = list(value)
        count = int(name[12:])
        return [{'start': pts[i], 'end': pts[i + 1]} for i in range(min(count, len(pts) - 1))]
    raise rio.ParamError(f'unknown transform {name!r}', allowed=['keep:a,b', 'first:N', 'consecutive:N'])


def _ref(expr, ctx):
    parts = [p.strip() for p in expr.split('|')]
    head, transforms = parts[0], parts[1:]
    if head == 'work':
        value = ctx['work']
    elif head in ctx['inputs']:
        value = ctx['inputs'][head]
    else:
        m = _STEP_REF.match(head)
        if not m:
            raise rio.ParamError(f'unknown reference ${{{head}}}', allowed=sorted(ctx['inputs']) + ['work'])
        n = int(m.group(1))
        if n not in ctx['results']:
            raise rio.ParamError(f'reference ${{{head}}} needs the result of step {n}, which did not run')
        value = rio.find_field(ctx['results'][n], m.group(2))
        if value is None:
            raise rio.ParamError(f'step {n} result has no field {m.group(2)!r}')
    for t in transforms:
        value = _transform(t, value)
    return value


def _subst(value, ctx):
    if isinstance(value, dict):
        return {k: _subst(v, ctx) for k, v in value.items()}
    if isinstance(value, list):
        return [_subst(v, ctx) for v in value]
    if isinstance(value, str):
        whole = _WHOLE.match(value)
        if whole:
            return _ref(whole.group(1), ctx)
        return _PART.sub(lambda m: str(_ref(m.group(1), ctx)), value)
    return value


def _work_posix(work):
    return str(Path(work).expanduser().resolve()).replace('\\', '/')


# --------------------------------------------------------------------------- gates

def _probe(path):
    cmd = ['ffprobe', '-v', 'error', '-count_frames', '-show_entries',
           'format=duration:stream=index,codec_type,codec_name,pix_fmt,width,height,avg_frame_rate,nb_read_frames',
           '-of', 'json', str(path)]
    done = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    if done.returncode != 0:
        raise RuntimeError('ffprobe failed: ' + (done.stderr or '').strip()[-200:])
    return json.loads(done.stdout)


def _first_frame_mean(path):
    cmd = ['ffmpeg', '-v', 'error', '-nostdin', '-i', str(path), '-frames:v', '1',
           '-f', 'rawvideo', '-pix_fmt', 'gray', '-']
    done = subprocess.run(cmd, capture_output=True, timeout=180)
    if done.returncode != 0 or not done.stdout:
        raise RuntimeError('could not decode the first frame')
    return sum(done.stdout) / len(done.stdout)


def check_video(path, audio='aac_or_none', frames_match=True, no_black_first_frame=True,
                even_dims=True, mp4_codec=True):
    """Gate for a finished video, independent of the op that wrote it. -> (passed, reason)."""
    p = Path(path)
    if not p.is_file() or p.stat().st_size == 0:
        return False, f'file missing or empty: {p.name}'
    try:
        data = _probe(p)
    except (RuntimeError, OSError, json.JSONDecodeError) as exc:
        return False, f'not a readable video: {exc}'
    streams = data.get('streams', [])
    videos = [s for s in streams if s.get('codec_type') == 'video']
    audios = [s for s in streams if s.get('codec_type') == 'audio']
    if len(videos) != 1:
        return False, f'expected exactly one video stream, found {len(videos)}'
    v = videos[0]
    if mp4_codec and (v.get('codec_name') != 'h264' or v.get('pix_fmt') != 'yuv420p'):
        return False, f'video must be h264 yuv420p (got {v.get("codec_name")} {v.get("pix_fmt")})'
    if audio == 'aac' and not audios:
        return False, 'audio missing: AAC expected'
    if audio == 'none' and audios:
        return False, 'unexpected audio stream'
    if audios and any(a.get('codec_name') != 'aac' for a in audios):
        return False, f'audio codec must be aac (got {audios[0].get("codec_name")})'
    if even_dims:
        w, h = int(v.get('width') or 0), int(v.get('height') or 0)
        if not w or not h or w % 2 or h % 2:
            return False, f'dimensions must be even (got {w}x{h})'
    if frames_match:
        duration = float(data.get('format', {}).get('duration') or 0)
        fps = float(Fraction(v.get('avg_frame_rate') or '0/1'))
        frames = v.get('nb_read_frames')
        expected = round(duration * fps)
        if frames in (None, 'N/A') or int(frames) != expected:
            return False, f'frames {frames} != round(duration x fps) = {expected}'
    if no_black_first_frame:
        try:
            mean = _first_frame_mean(p)
        except (RuntimeError, OSError) as exc:
            return False, str(exc)
        if mean < BLACK_MEAN_MAX:
            return False, f'first frame is black (mean luma {mean:.1f})'
    return True, 'video checks passed'


def _svg_texts(svg):
    texts = [html.unescape(t) for t in _SVG_TEXT.findall(svg or '')]
    pairs = len(texts) % 2 == 0 and all(texts[i] == texts[i + 1] for i in range(0, len(texts), 2))
    if texts and pairs:
        texts = texts[0::2]          # the karaoke layer draws every word twice (stroke + fill)
    return texts


def _dotted(obj, path):
    cur = obj
    for part in path.split('.'):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur


def _gate(gate, ctx):
    """-> (status, reason); status is pass, fail or skip."""
    check = gate['check']
    expect = _subst(gate.get('expect') or {}, ctx)
    if check == 'not_example':
        env = ctx['envelope']
        if env.get('outcome') == 'ok' and not env.get('example_data'):
            return 'pass', 'real data (not built-in example rows)'
        return 'fail', 'outcome is not ok or built-in example data was used'
    if check == 'file_exists':
        if not ctx['approved']:
            return 'skip', 'written only after --approve-write'
        path = Path(expect.get('path', ''))
        min_bytes = int(expect.get('min_bytes', 1))
        if path.is_file() and path.stat().st_size >= min_bytes:
            return 'pass', f'{path.name} exists ({path.stat().st_size} bytes)'
        return 'fail', f'{path.name} missing or smaller than {min_bytes} bytes'
    if check == 'verify_video':
        if not ctx['approved']:
            return 'skip', 'written only after --approve-write'
        ok, reason = check_video(expect.get('path', ''), audio=expect.get('audio', 'aac_or_none'),
                                 frames_match=bool(expect.get('frames_match', True)),
                                 no_black_first_frame=bool(expect.get('no_black_first_frame', True)),
                                 even_dims=bool(expect.get('even_dims', True)))
        return ('pass' if ok else 'fail'), reason
    if check == 'json_path':
        result = ctx['result']
        if 'path' in expect:
            value = _dotted(result, expect['path'])
        else:
            value = rio.find_field(result, expect.get('field', ''))
        if 'equals' in expect:
            ok = value == expect['equals']
        elif 'min_len' in expect:
            ok = isinstance(value, (list, str, dict)) and len(value) >= int(expect['min_len'])
        elif expect.get('not_empty'):
            ok = value not in (None, '', [], {})
        elif 'near' in expect:
            ok = isinstance(value, (int, float)) and abs(value - float(expect['near'])) <= float(expect.get('tol', 0.5))
        else:
            return 'fail', 'json_path gate has no test (equals, min_len, not_empty or near)'
        return ('pass' if ok else 'fail'), f'{expect.get("field") or expect.get("path")} = {str(value)[:120]}'
    if check == 'equals_input':
        svg = rio.find_field(ctx['result'], expect.get('field', 'svg')) or ''
        texts = _svg_texts(svg)
        words_value = ctx['inputs'].get(expect.get('input', ''))
        if not isinstance(words_value, list):
            return 'fail', 'equals_input needs a list input'
        words = [w.get('word') if isinstance(w, dict) else w for w in words_value]
        if texts == words:
            return 'pass', f'{len(texts)} caption strings equal the supplied words'
        return 'fail', f'caption strings differ from the supplied words ({texts[:3]} vs {words[:3]})'
    return 'fail', f'unknown check {check}'


# --------------------------------------------------------------------------- planning

def _missing_for(step):
    adapter, op, _shape = R.resolve_id(step['op'])
    full_id = adapter if op is None else f'{adapter}.{op}'
    return R.missing_needs(R.needs_of(adapter, op, R._entry(full_id)))


def usable_here(rec):
    """-> (usable, missing programs or modules)."""
    missing = []
    for step in _steps(rec):
        try:
            items = _missing_for(step)
        except rio.ParamError:
            items = [step.get('op')]
        for item in items:
            if item not in missing:
                missing.append(item)
    return (not missing), missing


def plan(recipe_id, inputs=None, work='<work>'):
    """Preview only: per step the command, effect and params file content. Runs nothing."""
    rec = get(recipe_id)
    resolved, missing = _resolve_inputs(rec, dict(inputs or {}))
    ctx = {'inputs': resolved, 'work': _work_posix(work) if work != '<work>' else '<work>', 'results': {}}
    out = []
    for step in _steps(rec):
        try:
            args = _subst(step.get('args') or {}, ctx)
        except rio.ParamError:
            args = {k: '<from an earlier step>' for k in (step.get('args') or {})}
        cmd = f'{R.ROSE_CMD} run {step["op"]} --params-file "{ctx["work"]}/step{step["n"]}.params.json"'
        if _is_write(step):
            cmd += ' --approve-write'
        out.append({'n': step['n'], 'command': cmd,
                    'params_file_content': json.dumps(args, ensure_ascii=False, indent=2),
                    'effect': 'write' if _is_write(step) else 'read',
                    'missing_inputs': [m['key'] for m in missing]})
    return out


# --------------------------------------------------------------------------- run

_ALLOWED_BY_TYPE = {
    'path': 'مسار كامل لملف موجود (absolute path)',
    'json_file': 'ملف JSON: قايمة من {"word": "...", "start": ثانية, "end": ثانية}',
    'number': 'رقم',
    'integer': 'رقم صحيح',
    'bool': 'true أو false',
    'string': 'نص',
}


def _needs_input(out, rec, missing):
    """outcome needs_input (exit 6): one question per missing input, nothing ran, nothing written."""
    specs = _input_specs(rec)
    items = []
    for m in missing:
        spec = specs.get(m['key'], {})
        allowed = _ALLOWED_BY_TYPE.get(spec.get('type', 'string'), 'نص')
        if spec.get('type') == 'path' and m['key'].endswith('_csv'):
            allowed = 'مسار كامل لملف .csv موجود (header: id,date,amount[,ref])'
        items.append({'key': m['key'], 'question_ar': m.get('question_ar'), 'allowed': allowed,
                      'suggested': spec.get('suggest_ar'), 'default': spec.get('default')})
    question = items[0]['question_ar'] or f'محتاج {items[0]["key"]} من صاحب الشغل'
    names = ', '.join(i['key'] for i in items)
    rerun = [f'{R.ROSE_CMD} recipe run {rec["id"]} {i["key"]}="<الجواب>" --work "<folder>"' for i in items]
    return _finish(out, 'needs_input', error=f'needs one answer from the owner: {names}', missing=items,
                   question_ar=question,
                   hint='ask the owner this one question (Arabic), suggestion first; run nothing else and never '
                        'invent or transcribe the value',
                   next=rerun)


def _summary(result):
    if isinstance(result, dict):
        return {k: _summary(v) for k, v in result.items() if not k.endswith('_base64')}
    if isinstance(result, list):
        return [_summary(v) for v in result[:200]]
    if isinstance(result, str) and len(result) > 600:
        return f'<{len(result)} chars>'
    return result


def _finish(out, outcome, **extra):
    out.update(extra)
    out['outcome'] = outcome
    out['status'] = outcome  # one meaning: status and outcome always agree
    out['ok'] = outcome == 'ok'
    out['exit'] = rio.OUTCOME_EXIT.get(outcome, rio.EXIT_ERROR)
    return out


def _quote_value(value):
    text = str(value)
    if re.search(r'[\s"\'&|<>;^`$(){}]', text):
        return '"' + text.replace('"', '\\"') + '"'
    return text


def run(recipe_id, inputs=None, work=None, approve_write=False):
    """Run one recipe -> outcome document (see module docstring)."""
    rec = get(recipe_id)
    out = {'ok': False, 'outcome': None, 'status': None, 'recipe': rec['id'],
           'recipe_status': rec.get('status'),
           'work': None, 'inputs': {}, 'steps': [], 'failed_gate': None, 'would_write': [],
           'deliverables': [], 'evidence': [], 'rerun_with': None, 'missing': [], 'warnings': [],
           'error': None, 'hint': None, 'next': []}
    if rec.get('status') != 'ready':
        out['warnings'].append(f'recipe status is {rec.get("status")}: not verified on this PC yet')
    try:
        resolved, missing = _resolve_inputs(rec, dict(inputs or {}))
    except rio.ParamError as exc:
        return _finish(out, 'error', error=str(exc), allowed=exc.allowed, hint=exc.hint)
    if missing:
        return _needs_input(out, rec, missing)
    if not work:
        return _finish(out, 'error', error='--work DIR is required (the folder for evidence and outputs)',
                       hint=f'{R.ROSE_CMD} recipe run {rec["id"]} key=value ... --work <folder>')
    work_path = Path(work).expanduser().resolve()
    if work_path.exists() and not work_path.is_dir():
        return _finish(out, 'error', error=f'work is not a folder: {work_path}')
    out['work'] = str(work_path)
    out['inputs'] = {k: (v if not isinstance(v, list) else f'<{len(v)} items>') for k, v in resolved.items()}
    for step in _steps(rec):
        try:
            missing_programs = _missing_for(step)
        except rio.ParamError as exc:
            return _finish(out, 'error', error=f'step {step.get("n")}: {exc}')
        if missing_programs:
            return _finish(out, 'unavailable_here',
                           error=f'step {step["n"]} needs {", ".join(missing_programs)} (missing here)',
                           hint='the other recipes still work; rose.py start shows what is missing',
                           next=[f'{R.ROSE_CMD} start'])
    if approve_write:
        work_path.mkdir(parents=True, exist_ok=True)
    ctx = {'inputs': resolved, 'work': _work_posix(work_path), 'results': {}, 'approved': approve_write}
    pending = False
    for step in _steps(rec):
        n = step['n']
        try:
            args = _subst(step.get('args') or {}, ctx)
            save_pairs = [(field, str(_subst(path, ctx))) for field, path in (step.get('save') or {}).items()]
        except rio.ParamError as exc:
            return _finish(out, 'error', error=f'step {n}: {exc}', hint=exc.hint, allowed=exc.allowed)
        env = R.run_op(step['op'], args, approve_write=approve_write)
        rec_step = {'n': n, 'op': step['op'], 'effect': step.get('effect'), 'do_ar': step.get('do_ar'),
                    'outcome': env['outcome'], 'error': env.get('error'), 'warnings': env.get('warnings', []),
                    'would_write': [], 'saved': {}, 'gates': []}
        out['steps'].append(rec_step)
        if env['outcome'] == 'approval_required':
            rec_step['would_write'] = list(env.get('would_write') or []) + [p for _f, p in save_pairs]
            out['would_write'].extend(p for p in rec_step['would_write'] if p not in out['would_write'])
            pending = True
            break
        if env['outcome'] != 'ok':
            return _finish(out, env['outcome'], error=f'step {n} ({step["op"]}): {env.get("error")}',
                           hint=env.get('hint'), next=env.get('next') or [])
        ctx['results'][n] = env.get('result')
        rec_step['result'] = _summary(env.get('result'))
        if save_pairs:
            if approve_write:
                try:
                    rec_step['saved'] = rio.save_fields(env['result'], [f'{f}={p}' for f, p in save_pairs])
                except (rio.ParamError, OSError) as exc:
                    return _finish(out, 'error', error=f'step {n}: save failed, nothing saved: {exc}')
            else:
                rec_step['would_write'] = [p for _f, p in save_pairs]
                out['would_write'].extend(p for p in rec_step['would_write'] if p not in out['would_write'])
                pending = True
        if approve_write:
            ev = work_path / f'evidence-step{n}.json'
            try:
                rio.write_json(str(ev), env, overwrite=True)
                out['evidence'].append(str(ev))
            except OSError as exc:
                return _finish(out, 'error', error=f'evidence not written: {exc}')
        gate_ctx = dict(ctx, envelope=env, result=env.get('result'))
        for gate in _gates(step):
            status, reason = _gate(gate, gate_ctx)
            rec_step['gates'].append({'check': gate['check'], 'text_ar': gate.get('text_ar'),
                                      'status': status, 'reason': reason})
            if status == 'fail':
                out['failed_gate'] = {'step': n, 'check': gate['check'], 'text_ar': gate.get('text_ar'),
                                      'reason': reason}
                return _finish(out, 'error', error=f'gate failed at step {n}: {reason}',
                               hint=gate.get('text_ar'))
        if step.get('deliver') and approve_write:
            outs = list(rec_step['saved'].values()) + [args[k] for k in _OUTPUT_NAMES
                                                       if isinstance(args.get(k), str)]
            for value in outs:
                if value not in out['deliverables']:
                    out['deliverables'].append(value)
    if pending and not approve_write:
        rerun = (f'{R.ROSE_CMD} recipe run {rec["id"]} '
                 + ' '.join(f'{k}={_quote_value(v)}' for k, v in resolved.items() if not isinstance(v, list))
                 + f' --work "{out["work"]}" --approve-write')
        return _finish(out, 'approval_required', error='writes need --approve-write: nothing was written',
                       hint='show would_write to the owner; rerun with --approve-write only after a clear yes',
                       rerun_with=rerun, next=[rerun])
    return _finish(out, 'ok', error=None)


# --------------------------------------------------------------------------- selftest

def _skip_reason(rec):
    missing = []
    for step in _steps(rec):
        try:
            items = _missing_for(step)
        except rio.ParamError as exc:
            items = [str(exc)]
        for item in items:
            if item not in missing:
                missing.append(item)
    return ('missing here: ' + ', '.join(missing)) if missing else None


def _listing(folder):
    if not folder.is_dir():
        return []
    return sorted((str(p.relative_to(folder)), p.stat().st_size) for p in folder.rglob('*'))


def selftest(recipe_id, base=None):
    """Run the recipe on rose_fixtures media in a temp folder.

    Dry run first: the work folder listing must not change, and the outcome must be
    approval_required (the recipe writes) or ok (read only). When it writes, the approved
    run must be ok and every deliverable must exist with bytes.
    -> {id, passed (True/False/None), skipped, checks}
    """
    import rose_fixtures as fixtures
    rec = get(recipe_id)
    reason = _skip_reason(rec)
    if reason:
        return {'id': recipe_id, 'passed': None, 'skipped': reason, 'checks': []}
    root = Path(base) if base else Path(tempfile.mkdtemp(prefix='rose-recipe-'))
    made = fixtures.make(str(root / 'fixtures'))
    inputs = {}
    for key, value in (rec.get('selftest') or {}).get('inputs', {}).items():
        if isinstance(value, str) and value.startswith('@'):
            if not made.get(value[1:]):
                return {'id': recipe_id, 'passed': None, 'skipped': f'fixture {value[1:]} not available here',
                        'checks': []}
            inputs[key] = made[value[1:]]
        else:
            inputs[key] = value
    work = root / 'work'
    checks = []
    before = _listing(work)
    dry = run(recipe_id, inputs, work=str(work), approve_write=False)
    expected_dry = 'approval_required' if _has_writes(rec) else 'ok'
    checks.append({'check': 'dry_run_outcome', 'expect': expected_dry, 'got': dry['outcome'],
                   'passed': dry['outcome'] == expected_dry, 'error': dry.get('error')})
    checks.append({'check': 'dry_run_wrote_nothing', 'passed': _listing(work) == before})
    if _has_writes(rec):
        real = run(recipe_id, inputs, work=str(work), approve_write=True)
        checks.append({'check': 'approved_run_outcome', 'expect': 'ok', 'got': real['outcome'],
                       'passed': real['outcome'] == 'ok', 'error': real.get('error'),
                       'failed_gate': real.get('failed_gate')})
        for path in real.get('deliverables', []):
            size = Path(path).stat().st_size if Path(path).is_file() else 0
            checks.append({'check': 'deliverable', 'path': path, 'bytes': size, 'passed': size > 0})
    passed = all(c.get('passed') for c in checks)
    return {'id': recipe_id, 'passed': passed, 'skipped': None, 'work': str(work), 'checks': checks}


# --------------------------------------------------------------------------- CLI

def _h_recipes(args):
    rows = []
    for rec in load_all():
        usable, missing = usable_here(rec)
        rows.append({'id': rec['id'], 'title_ar': rec['title_ar'], 'title_en': rec['title_en'],
                     'steps': len(_steps(rec)), 'recipe_status': rec.get('status'),
                     'usable_here': usable, 'missing': missing})
    if getattr(args, 'text', False):
        for r in rows:
            print(f"{r['id']}\t{r['title_ar']}\tsteps={r['steps']}\t{r['recipe_status']}\tusable_here={r['usable_here']}")
        return rio.EXIT_OK
    rio.emit({'ok': True, 'outcome': 'ok', 'count': len(rows), 'recipes': rows})
    return rio.EXIT_OK


def _h_show(args):
    try:
        rec = get(args.recipe_id)
    except rio.ParamError as exc:
        return rio.fail(str(exc), allowed=exc.allowed, hint=exc.hint)
    doc = {k: v for k, v in rec.items() if not k.startswith('_')}
    doc['plan'] = plan(args.recipe_id)
    rio.emit({'ok': True, 'outcome': 'ok', 'recipe': doc}, pretty=True)
    return rio.EXIT_OK


def _h_validate(args):
    errors = validate()
    rio.emit({'ok': not errors, 'outcome': 'ok' if not errors else 'error', 'errors': errors,
              'count': len(load_all())}, pretty=True)
    return rio.EXIT_OK if not errors else rio.EXIT_ERROR


def _h_run(args):
    try:
        rec = get(args.recipe_id)
        schema = {}
        for spec in rec.get('inputs') or []:
            kind = spec.get('type', 'string')
            schema[spec['key']] = {'type': {'string': 'string', 'path': 'string', 'json_file': 'auto'}.get(kind, kind)}
        warnings = []
        values = rio.read_params(args, schema, warnings)
    except rio.ParamError as exc:
        return rio.fail(str(exc), allowed=exc.allowed, hint=exc.hint)
    except rio.ParamError:
        return rio.fail('bad input')
    try:
        out = run(args.recipe_id, values, work=args.work, approve_write=args.approve_write)
    except rio.ParamError as exc:
        return rio.fail(str(exc), allowed=exc.allowed, hint=exc.hint)
    out['warnings'] = warnings + [w for w in out.get('warnings', []) if w not in warnings]
    rio.emit(out, pretty=args.pretty)
    return out['exit']


def _h_selftest(args):
    try:
        get(args.recipe_id)
    except rio.ParamError as exc:
        return rio.fail(str(exc), allowed=exc.allowed, hint=exc.hint)
    res = selftest(args.recipe_id, base=args.base)
    passed = res['passed'] is not False
    rio.emit({'ok': passed, 'outcome': 'ok' if passed else 'error', **res}, pretty=True)
    return rio.EXIT_OK if passed else rio.EXIT_ERROR


def _h_no_sub(args):
    return rio.fail('choose a recipe command: show, validate, run, selftest',
                    allowed=['show', 'validate', 'run', 'selftest'])


def register(subparsers):
    p = subparsers.add_parser('recipes', help='list the eight validated recipes (JSON; --text for lines)',
                              description='Recipes: id, Arabic and English title, steps, status and whether they run here.')
    p.add_argument('--json', action='store_true', help='JSON output (the default)')
    p.add_argument('--text', action='store_true', help='one line per recipe')
    p.set_defaults(ext_func=_h_recipes)
    rio.json_usage_errors(p)

    rp = subparsers.add_parser('recipe', help='recipe commands: show, validate, run, selftest',
                               description='One job per call: rose.py recipe run ID key=value ... --work DIR')
    rp.set_defaults(ext_func=_h_no_sub)
    rsub = rp.add_subparsers(dest='recipe_cmd')
    s = rsub.add_parser('show', help='print one recipe with its plan')
    s.add_argument('recipe_id', metavar='ID')
    s.set_defaults(ext_func=_h_show)
    v = rsub.add_parser('validate', help='check every recipe file against the schema and the catalogue')
    v.set_defaults(ext_func=_h_validate)
    r = rsub.add_parser('run', help='run a recipe: recipe run ID key=value ... --work DIR [--approve-write]')
    r.add_argument('recipe_id', metavar='ID')
    rio.add_param_arguments(r)
    r.add_argument('--work', metavar='DIR', help='folder for evidence and outputs (required)')
    r.add_argument('--approve-write', action='store_true',
                   help='the owner said yes to the writes listed in would_write')
    r.add_argument('--pretty', action='store_true', help='indent the JSON')
    r.set_defaults(ext_func=_h_run)
    rio.json_usage_errors(r)
    st = rsub.add_parser('selftest', help='run one recipe on fixtures in a temp folder')
    st.add_argument('recipe_id', metavar='ID')
    st.add_argument('--base', metavar='DIR', help='folder to use for the fixtures (default: a new temp folder)')
    st.set_defaults(ext_func=_h_selftest)
    return rp
