"""Red Rose V29 W02: generated operation catalogue and the ops / describe / find / catalog-build commands.

Interface (used by rose_run and the tests):
  build() -> dict                  pure introspection + catalog/*.json hand tables; deterministic
  load() -> dict                   references/OPS_CATALOG.json, falling back to build()
  get(op_id) -> entry | None
  schema(op_id) -> {param: {type, required, default, choices}} | None
  find(query, limit=8) -> [{id, kind, score, name_ar, summary, matched}]
  nearest_ids(text, n=5) -> [id]
  register(subparsers) -> None     adds: ops, describe, find, catalog-build (handlers via ext_func)

No database is opened here. No dates, platforms or absolute paths go into the catalogue.
"""
from __future__ import annotations

import argparse
import difflib
import importlib
import inspect
import json
import math
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CATALOG_DIR = ROOT / 'catalog'
REF_DIR = ROOT / 'references'
CATALOG_JSON = REF_DIR / 'OPS_CATALOG.json'
OPS_MD = REF_DIR / 'OPS.md'
BRANCH_JSON = CATALOG_DIR / 'branch_signatures.json'
NAMES_JSON = CATALOG_DIR / 'names_ar.json'
META_JSON = CATALOG_DIR / 'op_meta.json'
VERSION = 'V29-W02'
TYPES = ('string', 'number', 'integer', 'bool', 'path', 'list', 'object', 'auto')

_CACHE = {}

# ----------------------------------------------------------------------------- text normalisation

_DIAC = re.compile('[ؐ-ًؚ-ٰٟـۖ-ۭ]')
_ARABIC = re.compile('[؀-ۿ]')
_TOKEN = re.compile(r'[^\W_]+')
_PREFIXES = ('وال', 'بال', 'كال', 'فال', 'لل', 'ال')
_FOLD = str.maketrans({'أ': 'ا', 'إ': 'ا', 'آ': 'ا', 'ٱ': 'ا', 'ة': 'ه', 'ى': 'ي', 'ؤ': 'و', 'ئ': 'ي'})
_STOP_RAW = (
    'a an the of to for with against in on from by into as at it this that which how and or is are be '
    'do does make use using my me i want need please from about between than '
    'من في على مع عن الى إلى و ده دي ليه عايز عايزه عاوز عاوزه اعمل اعمل لي لو او أو'
)


def fold(text):
    """Arabic folding: diacritics and tatweel out, alef variants to bare alef, ة->ه, ى->ي, ؤ->و, ئ->ي."""
    s = unicodedata.normalize('NFKC', str(text or '')).casefold()
    return _DIAC.sub('', s).translate(_FOLD)


def tokens(text):
    """Folded word tokens; the Arabic definite/conjunction prefixes (ال, وال, بال, لل...) are stripped."""
    out = []
    for raw in _TOKEN.findall(fold(text)):
        tok = raw
        if _ARABIC.search(tok):
            for prefix in _PREFIXES:
                if tok.startswith(prefix) and len(tok) - len(prefix) >= 3:
                    tok = tok[len(prefix):]
                    break
        out.append(tok)
    return out


_STOP = frozenset(tokens(_STOP_RAW))
_PATH_NAME = re.compile(
    r'^(source|output|out|dest|destination|path|file|src|input|output_path|output_dir|db_path|work_dir|'
    r'edl_json|srt_path|srt_file|video|audio|image|input_file|output_file)$|_(path|file|dir|csv|json|onnx|jsx|cube)$')
_OUTPUT_NAME = re.compile(r'^(output|out|dest|destination|output_path|output_dir|output_file|db_path|work_dir)$')


# ----------------------------------------------------------------------------- small helpers

def _read_json(path, default):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return default


def _jsonable(value):
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else repr(value)
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    return repr(value)


def _summary(doc, fallback):
    para = []
    for line in (doc or '').splitlines():
        if not line.strip():
            if para:
                break
            continue
        para.append(line.strip())
    text = ' '.join(para)
    if not text:
        return fallback
    return re.split(r'(?<=\.)\s', text, maxsplit=1)[0][:220]


def _ptype(name, default, required):
    if _PATH_NAME.search(name) and (required or default is None or isinstance(default, str)):
        return 'path'
    if isinstance(default, bool):
        return 'bool'
    if isinstance(default, int):
        return 'integer'
    if isinstance(default, float):
        return 'number'
    if isinstance(default, str):
        return 'string'
    if isinstance(default, (list, tuple)):
        return 'list'
    if isinstance(default, dict):
        return 'object'
    return 'auto'


def _param(name, required, default, ptype):
    return {'name': name, 'required': bool(required), 'default': _jsonable(default),
            'type': ptype, 'role': None, 'choices': None, 'range': None, 'note': None, 'slot': None}


def _sig_params(fn):
    """-> (params, complete). Mirrors rose_run._sig_schema: only **extra (or no **) keeps the list complete."""
    try:
        sig = inspect.signature(fn)
    except (TypeError, ValueError):
        return [], False
    params, var_kw = [], None
    for p in sig.parameters.values():
        if p.kind == p.VAR_KEYWORD:
            var_kw = p.name
        elif p.kind in (p.POSITIONAL_OR_KEYWORD, p.KEYWORD_ONLY):
            if p.name in ('approve_write', 'self'):
                continue
            required = p.default is p.empty
            default = None if required else p.default
            params.append(_param(p.name, required, default, _ptype(p.name, default, required)))
    return params, var_kw in (None, 'extra')


def _flat_schemas(cr):
    """Flat adapter schemas from rose_run's execute() introspection; falls back to branch_signatures.json."""
    try:
        rr = importlib.import_module('rose_run')
        schemas = rr._flat_schemas()
        if schemas:
            return {k: dict(v) for k, v in schemas.items()}
    except Exception:
        pass
    return _read_json(BRANCH_JSON, {}).get('adapters', {})


def _flat_params(schema):
    out = []
    for name, spec in (schema or {}).items():
        required = bool(spec.get('required'))
        default = spec.get('default')
        ptype = spec.get('type') or 'auto'
        if _PATH_NAME.search(name) and ptype in ('auto', 'string'):
            ptype = 'path'
        out.append({'name': name, 'required': required, 'default': _jsonable(default), 'type': ptype,
                    'role': None, 'choices': spec.get('choices'), 'range': None, 'note': None, 'slot': None})
    return out


_DEP = {'ffmpeg': (['ffmpeg', 'ffprobe'], []),
        'cairosvg': (['ffmpeg', 'ffprobe'], ['cairosvg']),
        'pillow_cairosvg': (['ffmpeg', 'ffprobe'], ['cairosvg', 'PIL'])}


def _keywords(*parts):
    words = set()
    for part in parts:
        words.update(tokens(part))
    return sorted(w for w in words if w and w not in _STOP)


def _short_ar(value):
    text = str(value).split('؛')[0].split(';')[0].strip()
    return text[:60]


def _sub_catalogue(spec, params):
    if not spec:
        return None
    module_name, attr = spec['table'].split(':', 1)
    table = getattr(importlib.import_module(module_name), attr)
    items = [{'id': key, 'ar': _short_ar(value)} for key, value in table.items()]
    for p in params:
        if p['name'] == spec['key_param']:
            p['choices'] = [item['id'] for item in items]
    return {'table': spec['table'], 'key_param': spec['key_param'], 'items': items}


def _needs(op_id, dep, params, meta, adapter):
    programs, python = _DEP.get(dep, ([], []))
    extra = meta.get('programs', {}).get(op_id, [])
    files = [p['name'] for p in params if p['type'] == 'path' and not _OUTPUT_NAME.search(p['name'])]
    return {'files': files, 'db': dep == 'database', 'work_dir': any(p['name'] == 'work_dir' for p in params),
            'network': op_id in meta.get('network', []), 'programs': sorted(set(programs) | set(extra)),
            'python': list(python), 'pc_only': op_id in meta.get('pc_only', [])}


def _finish(entry, meta, coded):
    """Derive runs_with_defaults, example, static label and result from the entry's own facts."""
    op_id = entry['id']
    needs = entry['needs']
    no_input = not any(p['required'] for p in entry['params'])
    runs = (entry['effect'] == 'read' and no_input and not needs['files'] and not needs['programs']
            and not needs['python'] and not needs['db'] and not needs['network'] and not needs['pc_only']
            and not needs['work_dir'] and entry['example_when_absent'] is None
            and op_id not in meta.get('defaults_not_runnable', {}))
    entry['runs_with_defaults'] = runs
    entry['example'] = ({'args': [], 'params_file': None, 'placeholders': [], 'source': 'defaults'}
                        if runs else None)
    if entry['known_broken_reason'] is not None:
        label = 'known_broken'
    elif entry['example'] is None:
        label = 'needs_input'
    elif coded:
        label = 'coded_untested'
    else:
        label = 'runs_with_defaults'
    entry['static_label'] = label
    out = next((p['name'] for p in entry['params'] if _OUTPUT_NAME.search(p['name']) and p['type'] == 'path'), None)
    entry['result'] = {'artifact': 'file' if out else 'json', 'outcome_path': out}
    return entry


# ----------------------------------------------------------------------------- build

def build():
    """Generate the whole catalogue from code plus catalog/*.json. Deterministic (no dates or paths)."""
    cr = importlib.import_module('capability_runtime')
    names = _read_json(NAMES_JSON, {})
    meta = _read_json(META_JSON, {})
    flat_schemas = _flat_schemas(cr)
    coded = set(cr.CODED_UNTESTED)
    entries, adapters = {}, {}
    module_ops = 0
    for adapter in cr.REGISTRY:
        description, declared, dep = cr.REGISTRY[adapter]
        module = cr.IO_ADAPTERS.get(adapter) or cr.PURE_MODULES.get(adapter)
        pure = adapter in cr.PURE_MODULES
        if module is None:
            effect = declared if declared in ('read', 'write') else 'write'
            spec = flat_schemas.get(adapter) or meta.get('flat_params', {}).get(adapter)
            params = _flat_params(spec)
            complete = bool(spec) or adapter in meta.get('flat_complete', [])
            name_ar = names.get('flat', {}).get(adapter) or adapter
            entry = {
                'id': adapter, 'adapter': adapter, 'op': None, 'call_shape': 'flat', 'name_ar': name_ar,
                'name_en': adapter, 'summary': description, 'keywords': _keywords(adapter, name_ar),
                'effect': effect,
                'approval': {'needed': effect == 'write' or adapter in meta.get('network', []), 'read_actions': []},
                'needs': _needs(adapter, dep, params, meta, adapter), 'params': params,
                'sub_catalogue': None, 'example_when_absent': None, 'schema_complete': complete,
                'known_broken_reason': meta.get('known_broken', {}).get(adapter),
            }
            entries[adapter] = _finish(entry, meta, adapter in coded)
            adapters[adapter] = {'name_ar': name_ar, 'kind': 'flat', 'summary': description, 'effect': effect,
                                 'op_count': 1, 'read': int(effect == 'read'), 'write': int(effect == 'write')}
            continue
        topics = getattr(module, 'TOPICS', {}) or {}
        topic_names = getattr(module, 'TOPIC_NAMES_AR', {}) or {}
        topic_of = {op: code for code, op in topics.items()}
        counts = {'read': 0, 'write': 0}
        for op in sorted(module.OPS):
            # OPS is either {name: function} or a tuple of names dispatched by module.run(op, params)
            fn = module.OPS[op] if isinstance(module.OPS, dict) else (
                getattr(module, op, None) or getattr(module, 'run'))
            op_id = f'{adapter}.{op}'
            code = topic_of.get(op)
            name_ar = names.get('ops', {}).get(op_id) or topic_names.get(code) or f'{adapter} {op}'
            name_en = topics.get(code) or op.replace('_', ' ')
            params, complete = _sig_params(fn)
            effects = getattr(module, 'EFFECTS', None)
            if isinstance(effects, dict) and effects.get(op) in ('read', 'write'):
                effect = effects[op]
            else:
                effect = 'read' if pure else 'write'
            counts[effect] += 1
            sub = None
            if op_id in meta.get('sub_catalogue', {}):
                sub = _sub_catalogue(meta['sub_catalogue'][op_id], params)
            entry = {
                'id': op_id, 'adapter': adapter, 'op': op, 'call_shape': 'module', 'name_ar': name_ar,
                'name_en': name_en, 'summary': _summary(inspect.getdoc(fn), name_en),
                'keywords': _keywords(op, adapter, name_en, name_ar,
                                      *meta.get('keywords', {}).get(op_id, [])),
                'effect': effect,
                'approval': {'needed': effect == 'write' or op_id in meta.get('network', []), 'read_actions': []},
                'needs': _needs(op_id, dep, params, meta, adapter), 'params': params,
                'sub_catalogue': sub, 'example_when_absent': meta.get('example_when_absent', {}).get(op_id),
                'schema_complete': complete, 'known_broken_reason': meta.get('known_broken', {}).get(op_id),
            }
            entries[op_id] = _finish(entry, meta, adapter in coded)
            module_ops += 1
        adapters[adapter] = {'name_ar': names.get('adapters', {}).get(adapter) or adapter, 'kind': 'module',
                             'summary': description, 'effect': declared if declared in ('read', 'write', 'mixed') else 'mixed',
                             'op_count': len(module.OPS), 'read': counts['read'], 'write': counts['write']}
    entries = {k: entries[k] for k in sorted(entries)}
    return {
        'version': VERSION,
        'counts': {'adapters': len(adapters), 'module_adapters': sum(1 for a in adapters.values() if a['kind'] == 'module'),
                   'flat_adapters': sum(1 for a in adapters.values() if a['kind'] == 'flat'),
                   'module_ops': module_ops, 'entries': len(entries)},
        'adapters': {k: adapters[k] for k in sorted(adapters)},
        'entries': entries,
        'synonyms': names.get('synonyms', {}),
    }


def load():
    """Load the indexed catalogue, rebuilding in memory if registry adapters changed.

    Never silently show stale operation lists after installing new native
    capabilities. Rebuilding does not write files or mutate owner memory.
    """
    if 'cat' not in _CACHE:
        cat = _read_json(CATALOG_JSON, None)
        if not isinstance(cat, dict) or 'entries' not in cat:
            cat = build()
        else:
            cr = importlib.import_module('capability_runtime')
            if set(cat.get('adapters', {})) != set(cr.REGISTRY):
                cat = build()
        _CACHE['cat'] = cat
    return _CACHE['cat']


def get(op_id):
    entry = load()['entries'].get(op_id)
    return entry if isinstance(entry, dict) else None


def schema(op_id):
    entry = get(op_id)
    if entry is None:
        return None
    return {p['name']: {'type': p['type'], 'required': p['required'], 'default': p['default'],
                        'choices': p['choices']} for p in entry['params']}


def find(query, limit=8):
    """Keyword search over the catalogue with Arabic folding and synonyms (see names_ar.json)."""
    cat = load()
    wanted = [t for t in tokens(query) if t not in _STOP]
    if not wanted:
        return []
    terms = set(wanted)
    for key, extra in cat.get('synonyms', {}).items():
        kt = tokens(key)
        if kt and kt[0] in terms:
            for value in extra:
                terms.update(tokens(value))
    scored = []
    for op_id, entry in cat['entries'].items():
        keys = set(entry.get('keywords', []))
        name = set(tokens(entry.get('name_ar', ''))) | set(tokens(entry.get('name_en', '')))
        words = set(tokens(entry.get('summary', '')))
        score, matched = 0, set()
        for term in terms:
            if term in keys or term in name:
                score += 3
                matched.add(term)
            elif term in words:
                score += 1
                matched.add(term)
        if score:
            scored.append((-score, op_id, entry, sorted(matched)))
    scored.sort(key=lambda row: (row[0], row[1]))
    return [{'id': op_id, 'kind': 'op', 'score': -neg, 'name_ar': entry['name_ar'],
             'summary': entry['summary'], 'matched': matched}
            for neg, op_id, entry, matched in scored[:max(1, int(limit))]]


def nearest_ids(text, n=5):
    text = (text or '').strip().casefold()
    tail_t = text.rsplit('.', 1)[-1]
    scored = []
    for op_id in load()['entries']:
        ratio = difflib.SequenceMatcher(None, text, op_id.casefold()).ratio()
        tail = op_id.rsplit('.', 1)[-1].casefold()
        ratio = max(ratio, difflib.SequenceMatcher(None, tail_t, tail).ratio() * 0.95)
        if tail_t and tail_t in op_id.casefold():
            ratio += 0.3
        scored.append((-ratio, op_id))
    return [op_id for _, op_id in sorted(scored)[:n]]


# ----------------------------------------------------------------------------- rendering

def _measured_label(op_id):
    """The measured label from rose_env.readiness(op_id) when that module is importable."""
    try:
        env = importlib.import_module('rose_env')
        fn = getattr(env, 'readiness', None)
        got = fn(op_id) if callable(fn) else None
    except Exception:
        return None
    if isinstance(got, dict):
        got = got.get('label')
    return got if isinstance(got, str) and got else None


def _label(entry):
    measured = _measured_label(entry['id'])
    return (measured, 'measured') if measured else (entry['static_label'], 'static')


def _run_line(entry):
    parts = ['python -X utf8 rose.py run', entry['id']]
    example = entry.get('example')
    if example and example.get('args'):
        parts += list(example['args'])
    elif entry['static_label'] == 'needs_input':
        parts += [f"{p['name']}=VALUE" for p in entry['params'] if p['required']]
    if entry['approval']['needed']:
        parts.append('--approve-write')
    return ' '.join(parts)


def _describe_text(entry):
    label, source = _label(entry)
    needs = entry['needs']
    lines = [f"{entry['id']}  {entry['name_ar']}",
             f"  effect: {entry['effect']}   approval: {'needed' if entry['approval']['needed'] else 'no'}"
             f"   label: {label} ({source})",
             f"  {entry['summary']}",
             '  needs: programs=%s python=%s db=%s network=%s files=%s work_dir=%s pc_only=%s' % (
                 needs['programs'] or '[]', needs['python'] or '[]', 'yes' if needs['db'] else 'no',
                 'yes' if needs['network'] else 'no', needs['files'] or '[]',
                 'yes' if needs['work_dir'] else 'no', 'yes' if needs['pc_only'] else 'no'),
             '  params:']
    if not entry['params']:
        lines.append('    (none)')
    for p in entry['params']:
        choice = f" choices={p['choices']}" if p['choices'] else ''
        req = 'required' if p['required'] else f"default={json.dumps(p['default'], ensure_ascii=False)}"
        lines.append(f"    {p['name']:<22} {p['type']:<8} {req}{choice}")
    if entry.get('sub_catalogue'):
        sub = entry['sub_catalogue']
        ids = ', '.join(item['id'] for item in sub['items'])
        lines.append(f"  {sub['key_param']} ({len(sub['items'])}): {ids}")
    lines.append(f"  run: {_run_line(entry)}")
    if entry.get('known_broken_reason'):
        lines.append(f"  known broken: {entry['known_broken_reason']}")
    return '\n'.join(lines)


def _entry_json(entry):
    label, source = _label(entry)
    out = dict(entry)
    out['label'] = label
    out['label_source'] = source
    out['run'] = _run_line(entry)
    return out


def _md_text(cat):
    lines = ['# Red Rose operation catalogue', '',
             f"Generated by `rose.py catalog-build --approve-write` ({VERSION}). Do not edit by hand.", '',
             f"Entries: {cat['counts']['entries']} (module ops {cat['counts']['module_ops']}, "
             f"branch adapters {cat['counts']['flat_adapters']}).", '']
    for adapter, info in cat['adapters'].items():
        lines += [f"## {adapter} - {info['name_ar']}", '', info['summary'], '',
                  '| id | name | effect | label | summary |', '|---|---|---|---|---|']
        for entry in cat['entries'].values():
            if entry['adapter'] != adapter:
                continue
            lines.append(f"| `{entry['id']}` | {entry['name_ar']} | {entry['effect']} | "
                         f"{entry['static_label']} | {entry['summary'].replace('|', '/')} |")
        lines.append('')
        for entry in cat['entries'].values():
            if entry['adapter'] != adapter:
                continue
            params = ', '.join(f"{p['name']}:{p['type']}" + ('*' if p['required'] else '')
                               for p in entry['params']) or '-'
            lines.append(f"- `{entry['id']}` params: {params}")
        lines.append('')
    return '\n'.join(lines) + '\n'


# ----------------------------------------------------------------------------- command handlers

def _emit(obj, code=0):
    import rose_io as rio
    rio.emit(obj)
    return code


def _fail(error, allowed=None, hint=None, next_=None, code=1):
    import rose_io as rio
    return rio.fail(error, allowed=allowed, hint=hint, next=next_, code=code)


def _out(text):
    sys.stdout.write(text + '\n')
    return 0


def _h_ops(args):
    cat = load()
    if args.adapter:
        if args.adapter not in cat['adapters']:
            return _fail(f'unknown adapter: {args.adapter}', allowed=sorted(cat['adapters']),
                         hint='rose.py ops lists the adapters', next_=['python -X utf8 rose.py ops'])
        rows = [e for e in cat['entries'].values() if e['adapter'] == args.adapter]
        ops = [{'id': e['id'], 'effect': e['effect'], 'label': _label(e)[0], 'name_ar': e['name_ar'],
                'summary': e['summary']} for e in rows]
        if args.json:
            return _emit({'ok': True, 'outcome': 'ok', 'adapter': args.adapter, 'ops': ops})
        lines = [f"{r['id']} | {r['effect']} | {r['label']} | {r['name_ar']} | {r['summary']}" for r in ops]
        return _out('\n'.join(lines))
    rows = [{'adapter': name, 'ops': info['op_count'], 'read': info['read'], 'write': info['write'],
             'name_ar': info['name_ar']} for name, info in cat['adapters'].items()]
    if args.json:
        return _emit({'ok': True, 'outcome': 'ok', 'counts': cat['counts'], 'adapters': rows})
    lines = [f"{r['adapter']} | {r['ops']} ops | {r['read']} read / {r['write']} write | {r['name_ar']}"
             for r in rows]
    return _out('\n'.join(lines))


def _h_describe(args):
    entry = get(args.op_id)
    if entry is None:
        near = nearest_ids(args.op_id, 5)
        return _fail(f'unknown op: {args.op_id}', allowed=near,
                     hint='use one of the allowed ids; rose.py find "words" searches by meaning',
                     next_=[f'python -X utf8 rose.py describe {near[0]}'] if near else None, code=1)
    if args.json:
        return _emit({'ok': True, 'outcome': 'ok', 'entry': _entry_json(entry)})
    return _out(_describe_text(entry))


def _h_find(args):
    query = ' '.join(args.query).strip()
    if not query:
        return _fail('empty query', hint='python -X utf8 rose.py find "words" [--limit 8]')
    results = find(query, args.limit)
    if args.json:
        return _emit({'ok': True, 'outcome': 'ok', 'query': query, 'results': results})
    if not results:
        return _out('no match; try other words or rose.py ops')
    lines = [f"{r['score']:>3}  {r['id']}  {r['name_ar']}  [{', '.join(r['matched'])}]" for r in results]
    return _out('\n'.join(lines))


def _h_catalog_build(args):
    if not args.approve_write:
        return _emit({'ok': False, 'outcome': 'approval_required', 'error': None, 'allowed': None,
                      'hint': 'catalog-build writes references/OPS_CATALOG.json and OPS.md',
                      'would_write': ['references/OPS_CATALOG.json', 'references/OPS.md',
                                      'catalog/branch_signatures.json'],
                      'rerun_with': 'python -X utf8 rose.py catalog-build --approve-write'}, code=3)
    cat = build()
    REF_DIR.mkdir(parents=True, exist_ok=True)
    CATALOG_DIR.mkdir(parents=True, exist_ok=True)
    CATALOG_JSON.write_bytes((json.dumps(cat, sort_keys=True, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
    OPS_MD.write_bytes(_md_text(cat).encode('utf-8'))
    flats = {k: v for k, v in cat['entries'].items() if v['call_shape'] == 'flat'}
    branch = {'version': VERSION, 'adapters': {k: {p['name']: {'type': p['type'], 'required': p['required'],
                                                                'default': p['default'], 'choices': p['choices']}
                                                    for p in v['params']} for k, v in flats.items()}}
    BRANCH_JSON.write_bytes((json.dumps(branch, sort_keys=True, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
    _CACHE.pop('cat', None)
    return _emit({'ok': True, 'outcome': 'ok', 'written': ['references/OPS_CATALOG.json', 'references/OPS.md',
                                                          'catalog/branch_signatures.json'],
                  'counts': cat['counts']})


def register(subparsers):
    """Adds ops, describe, find and catalog-build; each parser gets ext_func (see references/INTERFACE.md)."""
    import rose_io as rio
    p = subparsers.add_parser('ops', help='list adapters, or the ops of one adapter (ops ADAPTER)')
    p.add_argument('adapter', nargs='?', default=None)
    p.add_argument('--json', action='store_true', help='one JSON document instead of text')
    rio.json_usage_errors(p)
    p.set_defaults(ext_func=_h_ops)

    p = subparsers.add_parser('describe', help='one op: params, effect, needs and a copy-paste run line')
    p.add_argument('op_id', metavar='ADAPTER.OP')
    p.add_argument('--json', action='store_true', help='one JSON document instead of text')
    rio.json_usage_errors(p)
    p.set_defaults(ext_func=_h_describe)

    p = subparsers.add_parser('find', help='find ops by meaning (Arabic or English words)')
    p.add_argument('query', nargs='+')
    p.add_argument('--limit', type=int, default=8)
    p.add_argument('--json', action='store_true', help='one JSON document instead of text')
    rio.json_usage_errors(p)
    p.set_defaults(ext_func=_h_find)

    p = subparsers.add_parser('catalog-build', help='regenerate references/OPS_CATALOG.json and OPS.md')
    p.add_argument('--approve-write', action='store_true')
    rio.json_usage_errors(p)
    p.set_defaults(ext_func=_h_catalog_build)


def main(argv=None):
    """Standalone entry: python rose_catalog.py ops|describe|find|catalog-build ..."""
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(prog='rose_catalog')
    sub = parser.add_subparsers(dest='command', required=True)
    register(sub)
    args = parser.parse_args(argv)
    return args.ext_func(args)


if __name__ == '__main__':
    raise SystemExit(main())
