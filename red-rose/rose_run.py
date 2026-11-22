"""Red Rose V29 `rose.py run ADAPTER.OP key=value ...` (W01).

One safe call form for every registered capability:

    python -X utf8 rose.py run text.motion.kinetic_text text="الوردة الحمراء" style=fade_up t=0.8
    python -X utf8 rose.py run accounting.check.bank_reconcile --params-file C:/work/rows.json
    python -X utf8 rose.py run studio.render.preview_frame --params-file spec.json rasterize=true \
        --save png=C:/work/frame.png --out C:/work/step.json --approve-write

The result is ONE JSON envelope with an ``outcome`` and a matching exit code
(see references/INTERFACE.md). The approval logic of capability_runtime.execute
is not changed: write ops still need --approve-write, and --save / --out are
writes too. Nothing opens the owner's private database unless the op needs it
and that database already exists.
"""
from __future__ import annotations

import argparse
import ast
import difflib
import importlib
import importlib.util
import inspect
import os
import re
import shutil
import sqlite3
import sys
from contextlib import closing
from pathlib import Path

import rose_io as rio

ROOT = Path(__file__).resolve().parent
PRIVATE_DB = Path.home() / '.red-rose' / 'memory.sqlite3'
ROSE_CMD = 'python -X utf8 ' + (ROOT / 'rose.py').as_posix() if ' ' not in str(ROOT) else \
    'python -X utf8 "' + (ROOT / 'rose.py').as_posix() + '"'

ENVELOPE_KEYS = ('ok', 'outcome', 'id', 'adapter', 'op', 'effect', 'audit_id', 'example_data',
                 'warnings', 'saved', 'would_write', 'rerun_with', 'result', 'error', 'allowed',
                 'hint', 'next')

# Used only while rose_catalog (W02) is not importable or has no entry for the op:
# ops that silently fall back to built-in example rows when these params are absent.
FALLBACK_EXAMPLE_WHEN_ABSENT = {
    'accounting.check.bank_reconcile': ['ledger', 'bank', 'ledger_csv', 'bank_csv'],
    'accounting.check.duplicate_invoices': ['invoices'],
    'accounting.check.trial_balance': ['lines'],
    'accounting.check.payroll_check': ['payroll', 'payments'],
    'accounting.check.inventory_codes': ['items'],
    'accounting.check.cash_flow': ['sales', 'payments'],
    'accounting.check.cost_allocation': ['expenses', 'centres'],
    'accounting.check.standards_checklist': ['items'],
    'accounting.check.journal_approval': ['entries'],
}
_DEP_NEEDS = {'ffmpeg': (['ffmpeg', 'ffprobe'], []),
              'cairosvg': (['ffmpeg', 'ffprobe'], ['cairosvg']),
              'pillow_cairosvg': (['ffmpeg', 'ffprobe'], ['cairosvg', 'PIL'])}
KNOWN_PROGRAMS = {'ffmpeg', 'ffprobe', 'blender', 'piper', 'espeak', 'espeak-ng', 'yt-dlp',
                  'afterfx', 'git', 'node', 'npx', 'magick', 'inkscape', 'gh'}
OUTPUT_PARAM_NAMES = ('output', 'out', 'output_path', 'output_dir', 'dest', 'destination',
                      'target_path', 'db_path')


class IdError(rio.ParamError):
    """Unknown or malformed ADAPTER.OP id."""


# --------------------------------------------------------------------------- lazy imports

def _runtime():
    import capability_runtime
    return capability_runtime


_CATALOG = {'loaded': False, 'module': None}


def _catalog():
    """rose_catalog (W02) when importable, else None (run keeps working without it)."""
    if not _CATALOG['loaded']:
        _CATALOG['loaded'] = True
        try:
            _CATALOG['module'] = importlib.import_module('rose_catalog')
        except Exception:
            _CATALOG['module'] = None
    return _CATALOG['module']


def _entry(op_id):
    cat = _catalog()
    if cat is None or not hasattr(cat, 'get'):
        return None
    try:
        entry = cat.get(op_id)
    except Exception:
        return None
    return entry if isinstance(entry, dict) else None


def _module(adapter):
    cr = _runtime()
    return cr.IO_ADAPTERS.get(adapter) or cr.PURE_MODULES.get(adapter)


# --------------------------------------------------------------------------- ids

def all_ids():
    """Every agent-facing id: flat adapters and ADAPTER.OP for module adapters."""
    cr = _runtime()
    ids = []
    for adapter in cr.REGISTRY:
        module = _module(adapter)
        if module is None:
            ids.append(adapter)
        else:
            ids.extend(f'{adapter}.{op}' for op in module.OPS)
    return ids


def nearest_ids(text, n=5, pool=None):
    cat = _catalog()
    if pool is None and cat is not None and hasattr(cat, 'nearest_ids'):
        try:
            got = list(cat.nearest_ids(text, n))
            if got:
                return got[:n]
        except Exception:
            pass
    ids = list(pool) if pool is not None else all_ids()
    t = (text or '').strip().casefold()
    scored = []
    for i in ids:
        ratio = difflib.SequenceMatcher(None, t, i.casefold()).ratio()
        tail = i.rsplit('.', 1)[-1].casefold()
        tail_t = t.rsplit('.', 1)[-1]
        ratio = max(ratio, difflib.SequenceMatcher(None, tail_t, tail).ratio() * 0.95)
        if tail_t and tail_t in i.casefold():
            ratio += 0.3
        scored.append((-ratio, i))
    return [i for _, i in sorted(scored)[:n]]


def resolve_id(text):
    """'ADAPTER.OP' -> (adapter, op|None, call_shape 'module'|'flat'). Raises IdError."""
    cr = _runtime()
    t = (text or '').strip()
    best = None
    for adapter in cr.REGISTRY:
        if (t == adapter or t.startswith(adapter + '.')) and (best is None or len(adapter) > len(best)):
            best = adapter
    if best is None:
        raise IdError(f'unknown id: {t!r}', allowed=nearest_ids(t),
                      hint='ids are ADAPTER.OP; list them with: rose.py ops (or rose.py find "words")')
    rest = t[len(best) + 1:] if len(t) > len(best) else ''
    module = _module(best)
    if module is None:
        if rest:
            raise IdError(f'{best} is a single-call adapter and takes no op (got {rest!r})', allowed=[best],
                          hint=f'call it as: rose.py run {best} key=value ...')
        return best, None, 'flat'
    if not rest:
        raise IdError(f'{best} needs an op: rose.py run {best}.OP', allowed=[f'{best}.{o}' for o in module.OPS],
                      hint=f'list ops with: rose.py ops {best}')
    if rest not in module.OPS:
        pool = [f'{best}.{o}' for o in module.OPS]
        raise IdError(f'unknown op {rest!r} for {best}', allowed=nearest_ids(t, pool=pool),
                      hint=f'all ops of this adapter: rose.py ops {best}')
    return best, rest, 'module'


# --------------------------------------------------------------------------- schema

def _type_of_default(value):
    if isinstance(value, bool):
        return 'bool'
    if isinstance(value, int):
        return 'integer'
    if isinstance(value, float):
        return 'number'
    if isinstance(value, str):
        return 'string'
    if isinstance(value, (list, tuple)):
        return 'list'
    if isinstance(value, dict):
        return 'object'
    return 'auto'


def _sig_schema(fn):
    try:
        sig = inspect.signature(fn)
    except (TypeError, ValueError):
        return None, False
    schema, var_kw = {}, None
    for p in sig.parameters.values():
        if p.kind == p.VAR_KEYWORD:
            var_kw = p.name
        elif p.kind in (p.POSITIONAL_OR_KEYWORD, p.KEYWORD_ONLY):
            if p.name in ('approve_write',):
                continue
            required = p.default is p.empty
            schema[p.name] = {'type': 'auto' if required else _type_of_default(p.default),
                              'required': required,
                              'default': None if required else p.default, 'choices': None}
    # Module ops reject unknown keys through _no_extra(extra); any other **name accepts options.
    complete = var_kw in (None, 'extra')
    return schema, complete


_FLAT = {}


def _flat_schemas():
    """Allowed/required keys and default types of flat adapters, read from execute()'s source."""
    if _FLAT:
        return _FLAT
    cr = _runtime()
    try:
        tree = ast.parse(Path(cr.__file__).read_text(encoding='utf-8'))
    except (OSError, SyntaxError):
        return _FLAT
    execute = next((n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == 'execute'), None)
    if execute is None:
        return _FLAT

    def names_of(test):
        if isinstance(test, ast.Compare) and isinstance(test.left, ast.Name) and test.left.id == 'capability':
            comp = test.comparators[0]
            if isinstance(test.ops[0], ast.Eq) and isinstance(comp, ast.Constant):
                return [comp.value]
            if isinstance(test.ops[0], ast.In) and isinstance(comp, (ast.Tuple, ast.List)):
                return [c.value for c in comp.elts if isinstance(c, ast.Constant)]
        return []

    def strs(node):
        if isinstance(node, (ast.Tuple, ast.List)):
            return [e.value for e in node.elts if isinstance(e, ast.Constant) and isinstance(e.value, str)]
        return None

    for node in ast.walk(execute):
        if not isinstance(node, ast.If):
            continue
        ids = names_of(node.test)
        if not ids:
            continue
        allowed, required, defaults = None, [], {}
        for sub in node.body:
            for call in ast.walk(sub):
                if not isinstance(call, ast.Call):
                    continue
                f = call.func
                if allowed is None and isinstance(f, ast.Name) and f.id == '_guard_keys' and len(call.args) >= 2:
                    allowed = strs(call.args[1])
                    if len(call.args) >= 3:
                        required = strs(call.args[2]) or []
                if (isinstance(f, ast.Attribute) and f.attr == 'get' and isinstance(f.value, ast.Name)
                        and f.value.id == 'params' and call.args and isinstance(call.args[0], ast.Constant)):
                    if len(call.args) > 1 and isinstance(call.args[1], ast.Constant):
                        defaults[call.args[0].value] = call.args[1].value
        if allowed is None:
            continue
        schema = {}
        for key in allowed:
            if key in defaults:
                schema[key] = {'type': _type_of_default(defaults[key]), 'required': False,
                               'default': defaults[key], 'choices': None}
            else:
                schema[key] = {'type': 'auto', 'required': key in required, 'default': None, 'choices': None}
        for i in ids:
            _FLAT.setdefault(i, schema)
    return _FLAT


def schema_for(adapter, op):
    """-> (schema {param: {type, required, default, choices}} | None, complete: bool, source)."""
    op_id = adapter if op is None else f'{adapter}.{op}'
    cat = _catalog()
    if cat is not None and hasattr(cat, 'schema') and _entry(op_id) is not None:
        try:
            sch = cat.schema(op_id)
            if isinstance(sch, dict):
                return sch, True, 'catalogue'
        except Exception:
            pass
    if op is None:
        sch = _flat_schemas().get(adapter)
        return (dict(sch), True, 'introspection') if sch is not None else (None, False, 'none')
    module = _module(adapter)
    fn = module.OPS.get(op)
    schema, complete = _sig_schema(fn) if callable(fn) else (None, False)
    if not schema:
        alt = getattr(module, op, None)
        if callable(alt) and alt is not fn:
            schema, complete = _sig_schema(alt)
            complete = False  # the registered wrapper may add or rename options
    if not schema:
        return None, False, 'none'
    return schema, complete, 'introspection'


def effect_of(adapter, op, entry=None):
    if entry and entry.get('effect') in ('read', 'write'):
        return entry['effect']
    cr = _runtime()
    if op is not None:
        effects = getattr(_module(adapter), 'EFFECTS', None)
        if isinstance(effects, dict) and effects.get(op) in ('read', 'write'):
            return effects[op]
        return 'read' if adapter in cr.PURE_MODULES else 'write'
    eff = cr.REGISTRY[adapter][1]
    return eff if eff in ('read', 'write') else 'write'


def needs_of(adapter, op, entry=None):
    """-> {programs:[..], python:[..], db:bool, pc_only:bool} from the catalogue or REGISTRY."""
    if entry and isinstance(entry.get('needs'), dict):
        n = entry['needs']
        return {'programs': list(n.get('programs') or []), 'python': list(n.get('python') or []),
                'db': bool(n.get('db')), 'pc_only': bool(n.get('pc_only'))}
    cr = _runtime()
    if op is None:
        dep = cr.REGISTRY[adapter][2]
        progs, py = _DEP_NEEDS.get(dep, ([], []))
        return {'programs': list(progs), 'python': list(py), 'db': dep == 'database', 'pc_only': False}
    return {'programs': [], 'python': [], 'db': False, 'pc_only': False}


def missing_needs(needs):
    missing = [p for p in needs.get('programs', []) if not shutil.which(p)]
    for mod in needs.get('python', []):
        try:
            if importlib.util.find_spec(mod) is None:
                missing.append(mod)
        except (ImportError, ValueError):
            missing.append(mod)
    return missing


def example_when_absent(op_id, entry=None):
    if entry is not None and 'example_when_absent' in entry:
        value = entry.get('example_when_absent')
        return list(value) if value else None
    return FALLBACK_EXAMPLE_WHEN_ABSENT.get(op_id)


# --------------------------------------------------------------------------- outcome rule

_APPROVAL = 'approval_required'
_FAIL_WORDS = {'blocked', 'fail', 'failed', 'error'}
_STATUS_KEYS = ('status', 'verdict', 'decision', 'outcome')


def _walk(obj, path='', depth=0):
    yield path, obj
    if depth > 30:
        return
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, (dict, list)):
                yield from _walk(v, f'{path}.{k}' if path else str(k), depth + 1)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            if isinstance(v, (dict, list)):
                yield from _walk(v, f'{path}[{i}]', depth + 1)


def _allowed_from_message(msg):
    m = re.search(r'allowed:\s*(.+)$', msg)
    if m:
        return [x.strip() for x in m.group(1).split(',') if x.strip()]
    m = re.search(r'must be one of \[(.*?)\]', msg)
    if m:
        return [x.strip().strip('\'"') for x in m.group(1).split(',') if x.strip()]
    return None


def _from_exception(exc):
    msg = f'{exc}'
    name = type(exc).__name__
    base = {'ok': False, 'warnings': [], 'example_data': False, 'allowed': None, 'signals': [name]}
    if isinstance(exc, (PermissionError, ValueError)) and 'approve_write' in msg:
        return dict(base, outcome=_APPROVAL, error=f'{name}: {msg}',
                    hint='nothing was written: show would_write to the owner and rerun with '
                         '--approve-write only after an explicit yes')
    if isinstance(exc, ValueError) and msg.startswith('pc_only:'):
        return dict(base, outcome='unavailable_here', error=msg,
                    hint='this op needs the owner PC (private index or memory); other ops still work here')
    if isinstance(exc, ImportError):
        missing = getattr(exc, 'name', None) or msg
        return dict(base, outcome='unavailable_here', error=f'{name}: {msg}',
                    hint=f'missing Python module: {missing}; install nothing without the owner\'s yes; '
                         'ops that do not need it still work (rose.py start)')
    if isinstance(exc, FileNotFoundError):
        prog = Path(str(getattr(exc, 'filename', '') or '')).name.lower()
        prog = prog[:-4] if prog.endswith('.exe') else prog
        if prog in KNOWN_PROGRAMS:
            return dict(base, outcome='unavailable_here', error=f'{name}: {msg}',
                        hint=f'missing program: {prog}; install nothing without the owner\'s yes')
    if re.search(r'\b(ffmpeg|ffprobe|blender|cairosvg|piper|espeak|yt-dlp)\b.{0,40}'
                 r'(not found|not installed|missing|unavailable)', msg, re.I):
        return dict(base, outcome='unavailable_here', error=f'{name}: {msg}',
                    hint='a needed program is missing here; install nothing without the owner\'s yes')
    return dict(base, outcome='error', error=f'{name}: {msg}'[:2000], allowed=_allowed_from_message(msg),
                hint='fix the call from allowed / rose.py describe ID')


def normalise(raw):
    """Fail-closed outcome of a raw execute() result (dict) or of the exception it raised.

    -> {outcome, ok, warnings, example_data, error, hint, allowed, signals:[paths]}
    approval_required anywhere > failure words / ok:false / qa.passed:false on the
    result spine > arabic_unshaped warning > built-in example data > ok.
    """
    if isinstance(raw, BaseException):
        return _from_exception(raw)
    if not isinstance(raw, dict):
        return {'outcome': 'error' if raw is None else 'ok', 'ok': raw is not None, 'warnings': [],
                'example_data': False, 'error': 'no result' if raw is None else None, 'hint': None,
                'allowed': None, 'signals': []}
    approval, failure, example, warnings = [], [], [], []
    for path, node in _walk(raw):
        if not isinstance(node, dict):
            continue
        for key in _STATUS_KEYS:
            val = node.get(key)
            if isinstance(val, str) and val.strip().lower() == _APPROVAL:
                approval.append(f'{path}.{key}' if path else key)
        if node.get('input') == 'built_in_example' or node.get('example_data') is True:
            example.append(path or '.')
        ws = node.get('warnings')
        if isinstance(ws, list):
            for w in ws:
                if isinstance(w, str) and w not in warnings:
                    warnings.append(w)
        qa = node.get('qa')
        if isinstance(qa, dict) and qa.get('passed') is False:
            failure.append(f'{path}.qa.passed' if path else 'qa.passed')
    # The result spine: execute dict -> result -> result -> ...
    node, path = raw, ''
    for _ in range(6):
        if not isinstance(node, dict):
            break
        for key in _STATUS_KEYS:
            val = node.get(key)
            if isinstance(val, str) and val.strip().lower() in _FAIL_WORDS:
                failure.append(f'{path}{key}={val}')
        if node.get('ok') is False:
            failure.append(f'{path}ok=false')
        if node.get('passed') is False:
            failure.append(f'{path}passed=false')
        err = node.get('error')
        if isinstance(err, str) and err.strip():
            failure.append(f'{path}error')
        node, path = node.get('result'), path + 'result.'
    out = {'outcome': 'ok', 'ok': True, 'warnings': warnings, 'example_data': bool(example),
           'error': None, 'hint': None, 'allowed': None, 'signals': []}
    unshaped = [w for w in warnings if w.startswith('arabic_unshaped')]
    if approval:
        out.update(outcome=_APPROVAL, ok=False, signals=approval,
                   error='approval required: nothing was executed or written',
                   hint='show would_write / the target to the owner; rerun with --approve-write only after an explicit yes')
    elif failure:
        detail = _first_error_text(raw)
        out.update(outcome='error', ok=False, signals=failure,
                   error='result reports failure at ' + ', '.join(failure[:4]) + (f': {detail}' if detail else ''),
                   hint='read result for the reason; do not deliver this output')
    elif unshaped:
        out.update(outcome='error', ok=False, signals=['warnings:arabic_unshaped'],
                   error=unshaped[0], hint='do not deliver this raster: deliver the SVG or fix the Arabic shaping')
    elif example:
        out.update(outcome='example_only', ok=False, signals=example,
                   error='built-in example data was used, not the owner\'s data',
                   hint='pass the real input parameters; never deliver example output')
    return out


def _first_error_text(raw):
    for _, node in _walk(raw):
        if isinstance(node, dict):
            for key in ('error', 'reason', 'detail'):
                val = node.get(key)
                if isinstance(val, str) and val.strip():
                    return val.strip()[:300]
            rs = node.get('reasons')
            if isinstance(rs, list) and rs and isinstance(rs[0], str):
                return rs[0][:300]
    return None


# --------------------------------------------------------------------------- envelope

def envelope(**kw):
    env = {'ok': False, 'outcome': 'error', 'id': None, 'adapter': None, 'op': None, 'effect': None,
           'audit_id': None, 'example_data': False, 'warnings': [], 'saved': {}, 'would_write': None,
           'rerun_with': None, 'result': None, 'error': None, 'allowed': None, 'hint': None, 'next': []}
    env.update({k: v for k, v in kw.items() if k in env})
    return env


def exit_code(env, example_ok=False):
    if env.get('outcome') == 'example_only' and example_ok:
        return rio.EXIT_OK
    return rio.OUTCOME_EXIT.get(env.get('outcome'), rio.EXIT_ERROR)


def _quote(tok):
    if tok == '' or re.search(r'[\s"\'&|<>;^`$(){}]', tok):
        if '=' in tok and not tok.startswith('-'):
            key, val = tok.split('=', 1)
            return f'{key}="{val}"'
        return f'"{tok}"'
    return tok


def command_line(op_id, tokens=(), approve=True):
    parts = [ROSE_CMD, 'run', op_id] + [_quote(t) for t in tokens]
    if approve:
        parts.append('--approve-write')
    return ' '.join(parts)


def _param_tokens(params):
    toks = []
    for k, v in params.items():
        if isinstance(v, bool):
            toks.append(f'{k}={str(v).lower()}')
        elif v is None:
            toks.append(f'{k}:=null')
        elif isinstance(v, (int, float)):
            toks.append(f'{k}={v}')
        elif isinstance(v, str) and '"' not in v and '\n' not in v and len(v) < 300:
            toks.append(f'{k}={v}')
        else:
            return ['--params-file', 'PARAMS.json']
    return toks


def _db_for(needs, db_path):
    """-> (path or ':memory:', error_env_fields|None). Never creates the private default."""
    if db_path:
        return str(db_path), None
    if needs.get('db'):
        env_db = os.environ.get('RED_ROSE_DB')
        if env_db:
            return env_db, None
        if PRIVATE_DB.exists():
            return str(PRIVATE_DB), None
        return None, {'outcome': 'unavailable_here',
                      'error': 'this op reads the Red Rose memory database and none exists here',
                      'hint': 'pass --db FILE or set RED_ROSE_DB to a database file; the private default is never created'}
    return ':memory:', None


def _connect(path):
    if path != ':memory:':
        Path(path).expanduser().parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(Path(path).expanduser())
    else:
        db = sqlite3.connect(':memory:')
    # Same tables as rose.connect so memory/knowledge adapters find them.
    db.execute('CREATE TABLE IF NOT EXISTS memories(id INTEGER PRIMARY KEY, created TEXT, category TEXT, content TEXT)')
    db.execute('CREATE TABLE IF NOT EXISTS knowledge(id INTEGER PRIMARY KEY, source TEXT, sha256 TEXT UNIQUE, content TEXT, imported TEXT)')
    db.execute('CREATE TABLE IF NOT EXISTS source_links(source TEXT, sha256 TEXT, origin TEXT, revision TEXT, license TEXT, PRIMARY KEY(source, sha256, origin, revision))')
    db.commit()
    return db


def check_params(adapter, op, params, schema=None, complete=None):
    """Raise ParamError for unknown / missing params when the schema is complete."""
    if schema is None:
        schema, complete, _ = schema_for(adapter, op)
    if not schema or not complete:
        return
    unknown = sorted(set(params) - set(schema))
    if unknown:
        op_id = adapter if op is None else f'{adapter}.{op}'
        raise rio.ParamError('unknown parameter(s): ' + ', '.join(unknown), allowed=sorted(schema),
                             hint=f'see rose.py describe {op_id}')
    missing = sorted(k for k, s in schema.items() if isinstance(s, dict) and s.get('required') and k not in params)
    if missing:
        raise rio.ParamError('missing parameter(s): ' + ', '.join(missing), allowed=sorted(schema),
                             hint='give them as key=value or in --params-file')


def run_op(op_id, params, approve_write=False, db_path=None, example_ok=False, _tokens=None):
    """Execute one op and return the envelope dict (never prints, never raises)."""
    params = dict(params or {})
    try:
        adapter, op, shape = resolve_id(op_id)
    except rio.ParamError as exc:
        return envelope(id=op_id, error=str(exc), allowed=exc.allowed, hint=exc.hint,
                        next=[f'{ROSE_CMD} find "<words>"'])
    full_id = adapter if op is None else f'{adapter}.{op}'
    entry = _entry(full_id)
    effect = effect_of(adapter, op, entry)
    base = dict(id=full_id, adapter=adapter, op=op, effect=effect)
    describe = f'{ROSE_CMD} describe {full_id}'
    schema, complete, _ = schema_for(adapter, op)
    try:
        check_params(adapter, op, params, schema, complete)
    except rio.ParamError as exc:
        return envelope(**base, error=str(exc), allowed=exc.allowed, hint=exc.hint, next=[describe])
    needs = needs_of(adapter, op, entry)
    missing = missing_needs(needs)
    if missing:
        return envelope(**base, outcome='unavailable_here', error='missing here: ' + ', '.join(missing),
                        hint='this op needs ' + ', '.join(missing) + '; install nothing without the owner\'s yes. '
                             'Ops that do not need them still work (rose.py start shows counts).',
                        next=[f'{ROSE_CMD} start'])
    path, db_err = _db_for(needs, db_path)
    if db_err:
        return envelope(**base, **db_err, next=[f'{ROSE_CMD} start'])
    payload = params if shape == 'flat' else {'op': op, 'params': params}
    cr = _runtime()
    try:
        with closing(_connect(path)) as db:
            raw = cr.execute(db, adapter, payload, approve_write=bool(approve_write))
    except Exception as exc:  # adapters raise ValueError/PermissionError/RuntimeError/OSError
        raw = exc
    norm = normalise(raw)
    result = None if isinstance(raw, BaseException) else raw
    warnings = list(norm['warnings'])
    outcome, ok = norm['outcome'], norm['ok']
    error, hint, allowed = norm['error'], norm['hint'], norm['allowed']
    if outcome == 'error' and error and 'unknown param' in error and schema:
        allowed = sorted(schema)
    example_data = norm['example_data']
    absent = example_when_absent(full_id, entry)
    if outcome == 'ok' and absent and not any(k in params for k in absent):
        outcome, ok, example_data = 'example_only', False, True
        error = 'built-in example data was used (none of ' + ', '.join(absent) + ' was given)'
        hint = 'pass the real input (' + ', '.join(absent) + '); never deliver example output'
    if outcome == 'example_only':
        example_data = True
        if example_ok:
            warnings.append('NOT REAL DATA: built-in example rows were used (--example-ok)')
    would_write, rerun = None, None
    nxt = []
    if outcome == _APPROVAL:
        would_write = [str(Path(str(params[k])).expanduser()) for k in OUTPUT_PARAM_NAMES
                       if isinstance(params.get(k), str) and params.get(k)]
        rerun = command_line(full_id, _tokens if _tokens is not None else _param_tokens(params))
        nxt = [rerun]
    elif outcome == 'unavailable_here':
        nxt = [f'{ROSE_CMD} start']
    elif outcome in ('error', 'example_only'):
        nxt = [describe]
    audit_id = result.get('audit_id') if isinstance(result, dict) and path != ':memory:' else None
    return envelope(**base, ok=ok, outcome=outcome, audit_id=audit_id, example_data=example_data,
                    warnings=warnings, would_write=would_write, rerun_with=rerun, result=result,
                    error=error, allowed=allowed, hint=hint, next=nxt)


# --------------------------------------------------------------------------- CLI

def _add_run_flags(p):
    p.add_argument('--params-file', metavar='FILE', help='JSON object with the parameters (large or nested input)')
    p.add_argument('--stdin', action='store_true', help='read a JSON object of parameters from stdin')
    p.add_argument('--file-param', action='append', default=[], metavar='key=FILE',
                   help='use the text of FILE as the value of key (repeatable)')
    p.add_argument('--save', action='append', default=[], metavar='FIELD=FILE',
                   help='write a result field to FILE (png from png_base64); repeat the flag, never comma-separated; a write')
    p.add_argument('--out', metavar='FILE', help='write the whole envelope as UTF-8 JSON (a write)')
    p.add_argument('--approve-write', action='store_true',
                   help='the owner approved the writes (op writes, --save, --out); without it nothing is written, exit 3')
    p.add_argument('--example-ok', action='store_true',
                   help='accept built-in example data (exit 0, ok stays false, NOT REAL DATA warning)')
    p.add_argument('--pretty', action='store_true', help='indent the JSON')
    return p


def register(subparsers):
    p = subparsers.add_parser(
        'run', help='run one op: run ADAPTER.OP key=value ... (one JSON envelope, exit 0/1/2/3/4/5)',
        description='Run one capability op. Exit codes: 0 ok, 1 error, 2 usage, 3 approval_required '
                    '(nothing written), 4 unavailable_here, 5 example_only. Opens no database unless the op needs one.')
    p.add_argument('op_id', metavar='ADAPTER.OP', help='e.g. text.motion.kinetic_text (list: rose.py ops)')
    p.add_argument('rest', nargs=argparse.REMAINDER, metavar='key=value ... [flags]',
                   help='parameters (key=value, key:=JSON) and the flags below, in any order')
    _add_run_flags(p)
    rio.json_usage_errors(p)
    p.set_defaults(ext_func=handler)
    return p


def _parse_rest(args):
    inner = argparse.ArgumentParser(prog='rose.py run', add_help=False)
    inner.add_argument('params', nargs='*')
    _add_run_flags(inner)
    rio.json_usage_errors(inner)
    extra = inner.parse_intermixed_args(list(getattr(args, 'rest', None) or []))
    merged = argparse.Namespace(**vars(args))
    merged.params = list(extra.params)
    for flag in ('stdin', 'approve_write', 'example_ok', 'pretty'):
        setattr(merged, flag, bool(getattr(args, flag, False) or getattr(extra, flag, False)))
    for flag in ('file_param', 'save'):
        setattr(merged, flag, list(getattr(args, flag, None) or []) + list(getattr(extra, flag, None) or []))
    for flag in ('params_file', 'out'):
        setattr(merged, flag, getattr(extra, flag, None) or getattr(args, flag, None))
    return merged


def _explicit_db(args):
    if os.environ.get('RED_ROSE_DB'):
        return os.environ['RED_ROSE_DB']
    db = getattr(args, 'db', None)
    if db and Path(db).expanduser().resolve() != PRIVATE_DB.resolve():
        return db
    return None


def _p(path):
    """Forward slashes: valid on Windows and safe in Git Bash (backslashes are eaten there)."""
    return path.replace('\\', '/') if os.name == 'nt' else path


def _rerun_tokens(a):
    toks = list(a.params)
    if a.params_file:
        toks += ['--params-file', _p(a.params_file)]
    for fp in a.file_param:
        toks += ['--file-param', _p(fp)]
    for s in a.save:
        toks += ['--save', _p(s)]
    if a.out:
        toks += ['--out', _p(a.out)]
    if a.example_ok:
        toks.append('--example-ok')
    return toks


def handler(args):
    try:
        a = _parse_rest(args)
    except SystemExit as exc:  # JSON usage error already printed
        return exc.code if isinstance(exc.code, int) else rio.EXIT_USAGE
    env = execute_cli(a)
    out_err = None
    if a.out and a.approve_write and not Path(a.out).expanduser().exists():
        try:
            rio.write_json(a.out, env, overwrite=False)
        except (OSError, FileExistsError) as exc:
            out_err = f'--out not written: {exc}'
    if out_err:
        env.update(ok=False, outcome='error', error=out_err, hint='choose a new --out file name')
    code = exit_code(env, a.example_ok)
    if env['outcome'] in ('error',) and env.get('result') is None:
        rio.emit(env)  # errors are always one line
    else:
        rio.emit(env, pretty=a.pretty)
    return code


def execute_cli(a):
    """Parse params, run the op, apply --save/--out approval rules -> envelope."""
    warnings = []
    try:
        adapter, op, _shape = resolve_id(a.op_id)
    except rio.ParamError as exc:
        return envelope(id=a.op_id, error=str(exc), allowed=exc.allowed, hint=exc.hint,
                        next=[f'{ROSE_CMD} find "<words>"'])
    full_id = adapter if op is None else f'{adapter}.{op}'
    schema, _complete, _src = schema_for(adapter, op)
    try:
        params = rio.read_params(a, schema, warnings)
        pairs = rio.parse_save_pairs(a.save)
        targets = [str(Path(p).expanduser().resolve()) for _, p in pairs]
        if a.out:
            targets.append(str(Path(a.out).expanduser().resolve()))
        existing = [t for t in targets if Path(t).exists()]
        if existing:
            raise rio.ParamError('refusing to overwrite existing file(s): ' + ', '.join(existing),
                                 hint='choose new file names for --save / --out')
        if len(set(targets)) != len(targets):
            raise rio.ParamError('the same file is named twice in --save / --out')
    except rio.ParamError as exc:
        return envelope(id=full_id, adapter=adapter, op=op, error=str(exc), allowed=exc.allowed,
                        hint=exc.hint, warnings=warnings, next=[f'{ROSE_CMD} describe {full_id}'])
    tokens = _rerun_tokens(a)
    env = run_op(full_id, params, approve_write=a.approve_write, db_path=_explicit_db(a),
                 example_ok=a.example_ok, _tokens=tokens)
    env['warnings'] = warnings + [w for w in env['warnings'] if w not in warnings]
    if not targets:
        return env
    usable = env['outcome'] == 'ok' or (env['outcome'] == 'example_only' and a.example_ok)
    if not a.approve_write:
        ww = list(env.get('would_write') or [])
        env['would_write'] = ww + [t for t in targets if t not in ww]
        if env['outcome'] in ('ok', 'example_only'):
            env.update(ok=False, outcome='approval_required',
                       error='--save/--out are writes: nothing was written',
                       hint='the op ran (read only); show would_write to the owner and rerun with '
                            '--approve-write only after an explicit yes')
        if env['outcome'] == 'approval_required':
            env['rerun_with'] = command_line(full_id, tokens)
            env['next'] = [env['rerun_with']]
        return env
    if usable and pairs:
        try:
            env['saved'] = rio.save_fields(env['result'], pairs)
        except (rio.ParamError, OSError) as exc:
            env.update(ok=False, outcome='error', error=f'--save failed, nothing saved: {exc}',
                       allowed=getattr(exc, 'allowed', None), hint=getattr(exc, 'hint', None))
    return env


def main(argv=None):
    """Standalone entry (before rose.py wires rose_ext): python -X utf8 rose_run.py run ID ..."""
    parser = argparse.ArgumentParser(prog='rose_run.py')
    parser.add_argument('--db', default=os.environ.get('RED_ROSE_DB', str(PRIVATE_DB)),
                        help='default: $RED_ROSE_DB or ~/.red-rose/memory.sqlite3 (run opens it only when an op needs it)')
    sub = parser.add_subparsers(dest='command', required=True)
    register(sub)
    args = parser.parse_args(argv)
    return args.ext_func(args)


if __name__ == '__main__':
    raise SystemExit(main())
