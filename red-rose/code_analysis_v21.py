"""Red Rose V21: bounded, deterministic static code-analysis helpers.

Pure standard-library Python. No file I/O, no subprocess, no network, no printing.
Source code always arrives as strings inside the parameters (for example
{'files': {'a.py': 'import b\\n'}}); it is parsed with ast/tokenize/re only and
NEVER executed, compiled to bytecode or imported. Every op validates its inputs
strictly (ValueError on wrong types, unknown parameter names and out-of-range
values) and caps its work (file count, file size, findings, comparisons).

These are review aids, not proofs: each op returns the assumptions it makes and
the limits it enforces next to its result. Static heuristics can miss dynamic
behaviour (getattr/importlib/exec, monkey-patching, runtime-generated code).
"""
from __future__ import annotations

import ast
import copy
import difflib
import fnmatch
import hashlib
import json
import math
import re
import warnings

MAX_PARAMS = 24
MAX_FILES = 200
MAX_FILE_BYTES = 200 * 1024
MAX_FINDINGS = 1000
MAX_LOG = 5000
MAX_TEXT = 2_000_000

TOPICS = {
    '11.01': 'syntax_check',
    '11.02': 'import_cycles',
    '11.03': 'duplicate_functions',
    '11.04': 'resource_handling',
    '11.05': 'secret_scan',
    '11.06': 'race_check',
    '11.07': 'traceback_repro',
    '11.08': 'complexity',
    '11.09': 'boundary_cases',
    '11.10': 'diff_review',
}

TOPIC_NAMES_AR = {
    '11.01': 'رصد أخطاء الصياغة',
    '11.02': 'تحليل الاعتماديات الدورية',
    '11.03': 'كشف التكرار الوظيفي',
    '11.04': 'مراجعة سوء التعامل مع الموارد',
    '11.05': 'كشف تسريب الأسرار في الكود',
    '11.06': 'تصحيح أخطاء التزامن',
    '11.07': 'إصلاح استثناءات غير متوقعة',
    '11.08': 'تحليل التعقيد والأداء',
    '11.09': 'مراجعة الثغرات المنطقية',
    '11.10': 'إنشاء مراجعة Pull Request',
}

STATIC_ONLY = 'static analysis only: the supplied code is parsed, never executed or imported'


# --------------------------------------------------------------------------- validation

def _no_extra(extra):
    if extra:
        raise ValueError('unknown parameter(s): ' + ', '.join(sorted(map(str, extra))))


def _num(value, low, high, name):
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value)):
        raise ValueError(f'{name} must be a finite number')
    value = float(value)
    if value < low or value > high:
        raise ValueError(f'{name} must be in [{low}, {high}]')
    return value


def _int(value, low, high, name):
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise ValueError(f'{name} must be an integer from {low} to {high}')
    return value


def _str(value, name, max_len=MAX_TEXT, allow_empty=False):
    if not isinstance(value, str):
        raise ValueError(f'{name} must be a string')
    if not allow_empty and not value.strip():
        raise ValueError(f'{name} must not be empty')
    if len(value) > max_len:
        raise ValueError(f'{name} must be at most {max_len} characters')
    return value


def _files(files, default):
    if files is None:
        files = default
    if not isinstance(files, dict) or not files:
        raise ValueError('files must be a non-empty dict {name: source}')
    if len(files) > MAX_FILES:
        raise ValueError(f'files may hold at most {MAX_FILES} entries')
    out = {}
    for name in sorted(files, key=str):
        src = files[name]
        if not isinstance(name, str) or not name or len(name) > 260 or '\x00' in name:
            raise ValueError('file names must be non-empty strings (<= 260 chars, no NUL)')
        if not isinstance(src, str):
            raise ValueError(f'source of {name!r} must be a string')
        if len(src.encode('utf-8', 'surrogatepass')) > MAX_FILE_BYTES:
            raise ValueError(f'{name!r} exceeds {MAX_FILE_BYTES} bytes')
        out[name] = src
    return out


def _pack(op, result, assumptions, limits):
    return {'op': op, 'result': result, 'assumptions': list(assumptions),
            'limits': list(limits)}


def _parse(src, name):
    """ast.parse without executing anything; warnings are captured, not printed."""
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        return ast.parse(src, filename=name)


def _try_parse(src, name):
    try:
        return _parse(src, name), None
    except SyntaxError as exc:
        return None, {'file': name, 'line': exc.lineno, 'column': exc.offset,
                      'message': exc.msg, 'type': type(exc).__name__}
    except (ValueError, RecursionError, MemoryError) as exc:
        return None, {'file': name, 'line': None, 'column': None,
                      'message': str(exc) or type(exc).__name__, 'type': type(exc).__name__}


def _dotted(node):
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
        return '.'.join(reversed(parts))
    return None


def _functions(tree):
    """Yield (qualified_name, node) for every def, including methods and nested defs."""
    stack = [(tree, '')]
    while stack:
        node, prefix = stack.pop()
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                q = prefix + child.name
                yield q, child
                stack.append((child, q + '.<locals>.'))
            elif isinstance(child, ast.ClassDef):
                stack.append((child, prefix + child.name + '.'))
            else:
                stack.append((child, prefix))


def _sorted_functions(tree):
    return sorted(_functions(tree), key=lambda item: (item[1].lineno, item[1].col_offset, item[0]))


def _scope_nodes(scope):
    """All nodes of one scope, not descending into nested function/lambda/class bodies."""
    out = []
    stack = list(ast.iter_child_nodes(scope))
    while stack:
        node = stack.pop()
        out.append(node)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)):
            continue
        stack.extend(ast.iter_child_nodes(node))
    return out


# --------------------------------------------------------------------------- 11.01 syntax_check

_EX_SYNTAX = {'ok.py': 'def add(a, b):\n    return a + b\n',
              'broken.py': 'x = 1\ndef f(:\n    pass\n'}


def syntax_check(*, files=None, **extra):
    """ast.parse every file; report file, line, column and message of syntax errors."""
    _no_extra(extra)
    files = _files(files, _EX_SYNTAX)
    errors, valid = [], []
    for name, src in files.items():
        tree, err = _try_parse(src, name)
        if err is None:
            valid.append(name)
        else:
            lines = src.splitlines()
            if err['line'] and 1 <= err['line'] <= len(lines):
                err['source_line'] = lines[err['line'] - 1][:200]
            errors.append(err)
    result = {'files_checked': len(files), 'valid': valid, 'errors': errors,
              'ok': not errors}
    return _pack('syntax_check', result,
                 [STATIC_ONLY,
                  'grammar of the running Python version is used (newer syntax may be rejected by older versions)',
                  'only the first syntax error per file is reported (as the parser stops there)'],
                 [f'<= {MAX_FILES} files, <= {MAX_FILE_BYTES} bytes each',
                  'compile-time warnings are suppressed; name/type errors are not detected'])


# --------------------------------------------------------------------------- 11.02 import_cycles

_EX_IMPORTS = {'a.py': 'import b\n', 'b.py': 'from c import thing\n',
               'c.py': 'from . import a\nthing = 1\n', 'd.py': 'import a\n'}


def _module_name(path):
    p = path.replace('\\', '/')
    while p.startswith('./'):
        p = p[2:]
    if not p.endswith(('.py', '.pyi')):
        return None, False
    p = p.rsplit('.', 1)[0]
    parts = [x for x in p.split('/') if x]
    is_pkg = bool(parts) and parts[-1] == '__init__'
    if is_pkg:
        parts = parts[:-1]
    if not parts or not all(x.isidentifier() for x in parts):
        return None, False
    return '.'.join(parts), is_pkg


def import_cycles(*, files=None, **extra):
    """Import graph between the supplied modules and its cycles (Tarjan SCC)."""
    _no_extra(extra)
    files = _files(files, _EX_IMPORTS)
    modules, is_pkg, skipped, parse_errors = {}, {}, [], []
    for name in files:
        mod, pkg = _module_name(name)
        if mod is None:
            skipped.append(name)
        elif mod in modules:
            raise ValueError(f'{name!r} and {modules[mod]!r} map to the same module {mod!r}')
        else:
            modules[mod], is_pkg[mod] = name, pkg
    by_base = {}
    for mod in modules:
        by_base.setdefault(mod.rsplit('.', 1)[-1], []).append(mod)

    def resolve(target):
        parts = target.split('.')
        for i in range(len(parts), 0, -1):
            cand = '.'.join(parts[:i])
            if cand in modules:
                return cand, 'exact' if i == len(parts) else 'parent_package'
        base = by_base.get(parts[-1], [])
        if len(base) == 1:
            return base[0], 'file_name'
        return None, None

    edges, unresolved = {}, []
    for mod in sorted(modules):
        fname = modules[mod]
        tree, err = _try_parse(files[fname], fname)
        if err:
            parse_errors.append(err)
            continue
        deferred_lines = set()
        for _, fn in _functions(tree):
            for n in ast.walk(fn):
                if isinstance(n, (ast.Import, ast.ImportFrom)):
                    deferred_lines.add((n.lineno, n.col_offset))
        pkg_parts = mod.split('.') if is_pkg[mod] else mod.split('.')[:-1]
        for node in ast.walk(tree):
            targets = []
            if isinstance(node, ast.Import):
                targets = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    if node.level - 1 > len(pkg_parts):
                        unresolved.append({'file': fname, 'line': node.lineno,
                                           'import': '.' * node.level + (node.module or '')})
                        continue
                    base_parts = pkg_parts[:len(pkg_parts) - (node.level - 1)]
                    base = '.'.join(base_parts + (node.module.split('.') if node.module else []))
                else:
                    base = node.module or ''
                for alias in node.names:
                    sub = f'{base}.{alias.name}' if base else alias.name
                    targets.append(sub if (alias.name != '*' and sub in modules) or not base else base)
            else:
                continue
            for target in targets:
                if not target:
                    continue
                dest, how = resolve(target)
                if dest is None:
                    continue  # third-party or stdlib import: outside the supplied set
                key = (mod, dest)
                deferred = (node.lineno, node.col_offset) in deferred_lines
                if key not in edges:
                    edges[key] = {'from': mod, 'to': dest, 'file': fname, 'line': node.lineno,
                                  'resolved_by': how, 'deferred': deferred}
                elif not deferred:
                    edges[key]['deferred'] = False
    adj = {m: sorted({b for (a, b) in edges if a == m}) for m in sorted(modules)}

    sccs = _tarjan(sorted(modules), adj)
    cycles = []
    for comp in sccs:
        if len(comp) == 1 and comp[0] not in adj[comp[0]]:
            continue
        members = sorted(comp)
        path = _cycle_path(members, adj)
        involved = [edges[(path[i], path[i + 1])] for i in range(len(path) - 1)]
        cycles.append({'modules': members, 'files': [modules[m] for m in members],
                       'example_path': path,
                       'edges': involved,
                       'only_via_deferred_imports': all(e['deferred'] for e in involved)})
    result = {'modules': {m: modules[m] for m in sorted(modules)},
              'edges': [edges[k] for k in sorted(edges)],
              'cycles': cycles, 'has_cycles': bool(cycles),
              'skipped_files': skipped, 'parse_errors': parse_errors,
              'unresolved_relative_imports': unresolved}
    return _pack('import_cycles', result,
                 [STATIC_ONLY,
                  'module names come from file paths (pkg/a.py -> pkg.a, pkg/__init__.py -> pkg)',
                  'imports of modules outside the supplied files (stdlib, third-party) are ignored',
                  'an unmatched absolute import falls back to a unique file with the same base name',
                  'imports inside functions are kept but marked deferred (they run at call time, not import time)'],
                 [f'<= {MAX_FILES} files, <= {MAX_FILE_BYTES} bytes each',
                  'dynamic imports (importlib, __import__) and TYPE_CHECKING guards are not distinguished',
                  'one representative (shortest) path is reported per strongly connected component'])


def _tarjan(nodes, adj):
    index, low, onstack, stack, sccs = {}, {}, set(), [], []
    counter = 0
    for root in nodes:
        if root in index:
            continue
        index[root] = low[root] = counter
        counter += 1
        stack.append(root)
        onstack.add(root)
        work = [(root, iter(adj[root]))]
        while work:
            node, it = work[-1]
            advanced = False
            for w in it:
                if w not in index:
                    index[w] = low[w] = counter
                    counter += 1
                    stack.append(w)
                    onstack.add(w)
                    work.append((w, iter(adj[w])))
                    advanced = True
                    break
                if w in onstack:
                    low[node] = min(low[node], index[w])
            if advanced:
                continue
            work.pop()
            if work:
                parent = work[-1][0]
                low[parent] = min(low[parent], low[node])
            if low[node] == index[node]:
                comp = []
                while True:
                    w = stack.pop()
                    onstack.discard(w)
                    comp.append(w)
                    if w == node:
                        break
                sccs.append(comp)
    return sccs


def _cycle_path(members, adj):
    start = members[0]
    inside = set(members)
    if start in adj[start]:
        return [start, start]
    parent = {start: None}
    queue = [start]
    while queue:
        nxt = []
        for u in queue:
            for v in adj[u]:
                if v == start:
                    path = [u]
                    while parent[path[-1]] is not None:
                        path.append(parent[path[-1]])
                    return list(reversed(path)) + [start]
                if v in inside and v not in parent:
                    parent[v] = u
                    nxt.append(v)
        queue = nxt
    return members + [start]


# --------------------------------------------------------------------------- 11.03 duplicate_functions

_EX_DUPES = {
    'a.py': ('def total_price(items, tax):\n    """Sum with tax."""\n    s = 0\n'
             '    for it in items:\n        s += it * (1 + tax)\n    return s\n'),
    'b.py': ('def sum_with_tax(values, rate):\n    acc = 0\n    for v in values:\n'
             '        acc += v * (1 + rate)\n    return acc\n'),
}


class _Renamer(ast.NodeTransformer):
    def __init__(self, mapping):
        self.mapping = mapping

    def _ph(self, name):
        return self.mapping.get(name, name)

    def visit_Name(self, node):
        node.id = self._ph(node.id)
        return node

    def visit_arg(self, node):
        node.arg = self._ph(node.arg)
        self.generic_visit(node)
        return node

    def visit_FunctionDef(self, node):
        node.name = self._ph(node.name)
        self.generic_visit(node)
        return node

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ExceptHandler(self, node):
        if node.name:
            node.name = self._ph(node.name)
        self.generic_visit(node)
        return node


def _arg_nodes(args):
    out = list(args.posonlyargs) + list(args.args)
    if args.vararg:
        out.append(args.vararg)
    out += list(args.kwonlyargs)
    if args.kwarg:
        out.append(args.kwarg)
    return out


def _normalise(fn):
    node = copy.deepcopy(fn)
    body = node.body
    if (body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)):
        body = body[1:] or [ast.Pass()]
    node.body = body
    node.name = '_fn'
    declared_global = set()
    for n in ast.walk(node):
        if isinstance(n, (ast.Global, ast.Nonlocal)):
            declared_global.update(n.names)
    order = [a.arg for a in _arg_nodes(node.args)]
    for n in ast.walk(node):
        if isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del)):
            order.append(n.id)
        elif isinstance(n, ast.ExceptHandler) and n.name:
            order.append(n.name)
        elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n is not node:
            order.append(n.name)
        elif isinstance(n, ast.arg):
            order.append(n.arg)
    mapping = {}
    for name in order:
        if name not in mapping and name not in declared_global and name != '_fn':
            mapping[name] = f'_v{len(mapping)}'
    node = _Renamer(mapping).visit(node)
    return ast.dump(node, annotate_fields=True, include_attributes=False)


def _signature(fn):
    a = fn.args
    return {'positional': [x.arg for x in list(a.posonlyargs) + list(a.args)],
            'vararg': a.vararg.arg if a.vararg else None,
            'kwonly': [x.arg for x in a.kwonlyargs],
            'kwarg': a.kwarg.arg if a.kwarg else None,
            'defaults': len(a.defaults) + sum(d is not None for d in a.kw_defaults)}


_TOKEN = re.compile(r"\w+|'[^']*'|[^\w\s]")


def duplicate_functions(*, files=None, threshold=0.9, min_nodes=8, max_compare=300, **extra):
    """Identical (normalised-AST hash) and near-duplicate (difflib ratio) functions."""
    _no_extra(extra)
    files = _files(files, _EX_DUPES)
    threshold = _num(threshold, 0.5, 1.0, 'threshold')
    min_nodes = _int(min_nodes, 1, 10_000, 'min_nodes')
    max_compare = _int(max_compare, 2, 500, 'max_compare')
    funcs, parse_errors, small = [], [], 0
    for name, src in files.items():
        tree, err = _try_parse(src, name)
        if err:
            parse_errors.append(err)
            continue
        for qual, fn in _sorted_functions(tree):
            size = sum(1 for _ in ast.walk(fn))
            if size < min_nodes:
                small += 1
                continue
            try:
                dump = _normalise(fn)
            except RecursionError:
                continue
            funcs.append({'file': name, 'function': qual, 'line': fn.lineno,
                          'nodes': size, 'hash': hashlib.sha256(dump.encode()).hexdigest()[:16],
                          '_tokens': _TOKEN.findall(dump)[:5000], '_sig': _signature(fn)})
    groups = {}
    for f in funcs:
        groups.setdefault(f['hash'], []).append(f)

    def pub(f):
        return {k: f[k] for k in ('file', 'function', 'line', 'nodes')}

    identical = []
    for h in sorted(groups):
        g = groups[h]
        if len(g) > 1:
            sigs = {json.dumps(x['_sig'], sort_keys=True) for x in g}
            entry = {'hash': h, 'functions': [pub(x) for x in g],
                     'signatures_differ': len(sigs) > 1}
            if len(sigs) > 1:
                entry['note'] = 'bodies are identical after renaming, but the signatures differ'
            identical.append(entry)
    reps = [groups[h][0] for h in sorted(groups, key=lambda h: (groups[h][0]['file'], groups[h][0]['line']))]
    truncated = len(reps) > max_compare
    reps = reps[:max_compare]
    near = []
    for i in range(len(reps)):
        a = reps[i]['_tokens']
        sm = difflib.SequenceMatcher(None, autojunk=False)
        sm.set_seq2(a)
        for j in range(i + 1, len(reps)):
            b = reps[j]['_tokens']
            if 2 * min(len(a), len(b)) / max(1, len(a) + len(b)) < threshold:
                continue
            sm.set_seq1(b)
            if sm.real_quick_ratio() < threshold or sm.quick_ratio() < threshold:
                continue
            ratio = sm.ratio()
            if ratio >= threshold:
                entry = {'a': pub(reps[i]), 'b': pub(reps[j]), 'ratio': round(ratio, 4),
                         'identical': False,
                         'signatures_differ': reps[i]['_sig'] != reps[j]['_sig'],
                         'note': 'similar structure but different behaviour is possible: review the differing tokens'}
                if entry['signatures_differ']:
                    entry['note'] += '; the signatures differ'
                near.append(entry)
                if len(near) >= MAX_FINDINGS:
                    break
    result = {'functions_analysed': len(funcs), 'skipped_small_functions': small,
              'identical': identical, 'near_duplicates': near,
              'near_duplicate_scan_truncated': truncated, 'parse_errors': parse_errors}
    return _pack('duplicate_functions', result,
                 [STATIC_ONLY,
                  'normalisation: docstring dropped, function name and local/argument names replaced by placeholders',
                  'globals, attributes, constants and called function names are kept, so they still distinguish bodies',
                  'identical = same normalised AST hash; near-duplicate = difflib ratio over AST-dump tokens >= threshold'],
                 [f'<= {MAX_FILES} files; functions with fewer than min_nodes AST nodes are skipped',
                  f'near-duplicate comparison limited to max_compare (<= 500) distinct bodies, <= 5000 tokens each',
                  'textual similarity does not prove equivalent behaviour (e.g. + vs - differ in one token)'])


# --------------------------------------------------------------------------- 11.04 resource_handling

_RESOURCE_CALLS = {
    'open', 'io.open', 'codecs.open', 'gzip.open', 'bz2.open', 'lzma.open', 'tarfile.open',
    'zipfile.ZipFile', 'ZipFile', 'sqlite3.connect', 'socket.socket', 'socket',
    'socket.create_connection', 'create_connection', 'subprocess.Popen', 'Popen',
    'urllib.request.urlopen', 'urlopen', 'tempfile.TemporaryFile',
    'tempfile.NamedTemporaryFile', 'os.fdopen', 'os.popen',
}
_CLOSERS = {'close', 'shutdown', 'terminate', 'kill', 'wait', 'communicate', 'release'}

_EX_RESOURCES = {'io_demo.py': (
    'import sqlite3\n\n'
    'def leaky(p):\n    f = open(p)\n    data = f.read()\n    return data\n\n'
    'def safe(p):\n    with open(p) as f:\n        return f.read()\n\n'
    'def closed(p):\n    f = open(p)\n    try:\n        return f.read()\n    finally:\n        f.close()\n\n'
    'def inline(p):\n    return open(p).read()\n\n'
    'def db(path):\n    con = sqlite3.connect(path)\n    return con.execute("select 1").fetchall()\n')}


def resource_handling(*, files=None, **extra):
    """Flag open()/connect()/socket()/Popen() results not managed by `with` or closed."""
    _no_extra(extra)
    files = _files(files, _EX_RESOURCES)
    findings, parse_errors, ok_count = [], [], 0
    for name, src in files.items():
        tree, err = _try_parse(src, name)
        if err:
            parse_errors.append(err)
            continue
        parents = {}
        for n in ast.walk(tree):
            for c in ast.iter_child_nodes(n):
                parents[c] = n
        scopes = [('<module>', tree)] + _sorted_functions(tree)
        for scope_name, scope in scopes:
            nodes = _scope_nodes(scope)
            closed, with_names, returned = set(), set(), set()
            for n in nodes:
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) \
                        and n.func.attr in _CLOSERS and isinstance(n.func.value, ast.Name):
                    closed.add(n.func.value.id)
                if isinstance(n, ast.Call) and (_dotted(n.func) or '').rsplit('.', 1)[-1] in (
                        'closing', 'enter_context', 'callback', 'register'):
                    for a in n.args:
                        if isinstance(a, ast.Name):
                            closed.add(a.id)
                        elif isinstance(a, ast.Attribute) and isinstance(a.value, ast.Name) \
                                and a.attr in _CLOSERS:
                            closed.add(a.value.id)
                if isinstance(n, ast.withitem) and isinstance(n.context_expr, ast.Name):
                    with_names.add(n.context_expr.id)
                if isinstance(n, (ast.Return, ast.Yield, ast.YieldFrom)) and isinstance(n.value, ast.Name):
                    returned.add(n.value.id)
            for n in nodes:
                if not isinstance(n, ast.Call):
                    continue
                callee = _dotted(n.func)
                if callee not in _RESOURCE_CALLS:
                    continue
                status, var = _resource_status(n, parents, closed, with_names, returned)
                rec = {'file': name, 'scope': scope_name, 'line': n.lineno, 'column': n.col_offset,
                       'call': callee, 'variable': var, 'status': status}
                if status in ('with', 'closed'):
                    ok_count += 1
                    continue
                rec['severity'] = {'unclosed': 'warning', 'inline_unclosed': 'warning',
                                   'returned': 'info', 'stored_on_object': 'info',
                                   'untracked': 'info'}[status]
                rec['message'] = {
                    'unclosed': 'result is never closed in this function and not used in a with statement',
                    'inline_unclosed': 'temporary resource is used inline and left for the garbage collector',
                    'returned': 'ownership is returned to the caller; the caller must close it',
                    'stored_on_object': 'stored on an object; its lifetime is not tracked statically',
                    'untracked': 'result flows somewhere this heuristic cannot follow'}[status]
                findings.append(rec)
                if len(findings) >= MAX_FINDINGS:
                    break
    findings.sort(key=lambda r: (r['file'], r['line'], r['column']))
    result = {'findings': findings,
              'warnings': sum(1 for f in findings if f['severity'] == 'warning'),
              'managed_calls': ok_count, 'parse_errors': parse_errors}
    return _pack('resource_handling', result,
                 [STATIC_ONLY,
                  'a resource is managed when its call is a with-item (possibly wrapped) or its variable is used '
                  'in a with statement, closed (close/shutdown/terminate/wait/communicate) or registered '
                  '(contextlib.closing, ExitStack.enter_context/callback) in the same function',
                  'close() anywhere in the function counts, even if an exception could skip it'],
                 [f'<= {MAX_FILES} files, <= {MAX_FINDINGS} findings',
                  'only well-known constructors are recognised (open, sqlite3.connect, socket, Popen, urlopen, ...); '
                  'aliases, Path.open() and custom factories are missed',
                  'no inter-procedural tracking: resources passed to helpers or stored on objects are reported as info'])


def _resource_status(call, parents, closed, with_names, returned):
    child, node = call, parents.get(call)
    while node is not None:
        if isinstance(node, ast.withitem):
            return ('with' if child is node.context_expr else 'untracked'), None
        if isinstance(node, (ast.Assign, ast.AnnAssign, ast.NamedExpr)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if child is not node.value:
                return 'untracked', None
            if child is not call:
                return 'untracked', None
            if len(targets) == 1 and isinstance(targets[0], ast.Name):
                var = targets[0].id
                if var in closed or var in with_names:
                    return 'closed', var
                if var in returned:
                    return 'returned', var
                return 'unclosed', var
            if len(targets) == 1 and isinstance(targets[0], ast.Attribute):
                return 'stored_on_object', _dotted(targets[0])
            return 'untracked', None
        if isinstance(node, (ast.Return, ast.Yield, ast.YieldFrom)):
            return ('returned' if child is call else 'inline_unclosed'), None
        if isinstance(node, ast.Attribute) and child is node.value and child is call:
            return 'inline_unclosed', None
        if isinstance(node, ast.Call) and child is call:
            name = (_dotted(node.func) or '').rsplit('.', 1)[-1]
            if name in ('closing', 'enter_context'):
                child, node = node, parents.get(node)
                continue
            return 'inline_unclosed', None
        if isinstance(node, ast.Expr):
            return 'inline_unclosed', None
        if isinstance(node, ast.stmt):
            return 'untracked', None
        child, node = node, parents.get(node)
    return 'untracked', None


# --------------------------------------------------------------------------- 11.05 secret_scan

_SECRET_PATTERNS = [
    ('aws_access_key_id', re.compile(r'\b((?:AKIA|ASIA)[0-9A-Z]{16})\b')),
    ('sk_token', re.compile(r'\b(sk-[A-Za-z0-9_\-]{20,})')),
    ('github_token', re.compile(r'\b(gh[pousr]_[A-Za-z0-9]{36,})\b')),
    ('slack_token', re.compile(r'\b(xox[abprs]-[A-Za-z0-9\-]{10,})')),
    ('private_key_header', re.compile(r'(-----BEGIN (?:[A-Z0-9]+ )*PRIVATE KEY-----)')),
    ('password_assignment', re.compile(
        r'(?i)\b(?:[a-z0-9_]*?(?:password|passwd|pwd|secret|api_?key|access_?token|auth_?token))\b'
        r'["\']?\s*[:=]\s*[rbu]?(["\'])([^"\'\n]{4,})\1')),
]
_HIGH_ENTROPY = re.compile(r'(["\'])([A-Za-z0-9+/=_\-]{32,})\1')
_PLACEHOLDERS = {'changeme', 'password', 'xxxx', 'xxxxxxxx', '****', 'none', 'null', 'example',
                 'your_password', 'your-password', 'secret', 'dummy', 'placeholder', 'redacted'}

# Documented AWS example key, assembled so this source holds no contiguous key literal.
_FAKE_KEY = 'AKIA' + 'IOSFODNN7' + 'EXAMPLE'
_EX_SECRETS = {'settings.py': f'AWS_KEY = "{_FAKE_KEY}"\nDEBUG = True\npassword = "hunter2-demo"\n',
               'tests/fixtures/sample.py': f'TOKEN = "{_FAKE_KEY}"\n'}
_EX_SECRET_IGNORE = ['tests/fixtures/*']


def _entropy(s):
    counts = {}
    for ch in s:
        counts[ch] = counts.get(ch, 0) + 1
    n = len(s)
    return -sum(c / n * math.log2(c / n) for c in counts.values())


def secret_scan(*, files=None, ignore_files=None, ignore_hashes=None, min_entropy=4.0,
                min_length=32, **extra):
    """Regex + entropy scan for likely secrets; values are always masked."""
    _no_extra(extra)
    use_default = files is None
    files = _files(files, _EX_SECRETS)
    if ignore_files is None:
        ignore_files = _EX_SECRET_IGNORE if use_default else []
    if not isinstance(ignore_files, list) or len(ignore_files) > 100 or \
            not all(isinstance(p, str) and p for p in ignore_files):
        raise ValueError('ignore_files must be a list of up to 100 glob patterns')
    if ignore_hashes is None:
        ignore_hashes = []
    if not isinstance(ignore_hashes, list) or len(ignore_hashes) > 1000 or not all(
            isinstance(h, str) and re.fullmatch(r'[0-9a-f]{12,64}', h) for h in ignore_hashes):
        raise ValueError('ignore_hashes must be a list of lowercase hex sha256 prefixes (12-64 chars)')
    min_entropy = _num(min_entropy, 0.0, 8.0, 'min_entropy')
    min_length = _int(min_length, 16, 4096, 'min_length')

    findings, ignored_files, ignored_hits = [], [], 0
    for name, src in files.items():
        norm = name.replace('\\', '/')
        if any(fnmatch.fnmatchcase(norm, p) for p in ignore_files):
            ignored_files.append(name)
            continue
        for lineno, line in enumerate(src.splitlines(), 1):
            if len(findings) >= MAX_FINDINGS:
                break
            spans = []
            hits = []
            for kind, rx in _SECRET_PATTERNS:
                for m in rx.finditer(line):
                    g = m.lastindex
                    value, start = m.group(g), m.start(g)
                    if kind == 'password_assignment' and value.strip().lower() in _PLACEHOLDERS:
                        continue
                    hits.append((start, start + len(value), kind, value))
            for m in _HIGH_ENTROPY.finditer(line):
                value = m.group(2)
                if len(value) >= min_length and _entropy(value) >= min_entropy:
                    hits.append((m.start(2), m.end(2), 'high_entropy_string', value))
            for start, end, kind, value in sorted(hits, key=lambda h: (h[0], -(h[1] - h[0]))):
                if any(start < e and s < end for s, e in spans):
                    continue
                spans.append((start, end))
                digest = hashlib.sha256(value.encode('utf-8', 'surrogatepass')).hexdigest()
                if any(digest.startswith(h) for h in ignore_hashes):
                    ignored_hits += 1
                    continue
                findings.append({'file': name, 'line': lineno, 'column': start + 1, 'kind': kind,
                                 'preview': value[:4], 'length': len(value),
                                 'fingerprint': digest[:16],
                                 'entropy': round(_entropy(value), 3)})
    result = {'findings': findings, 'count': len(findings), 'ignored_files': ignored_files,
              'ignored_by_hash': ignored_hits, 'files_scanned': len(files) - len(ignored_files)}
    return _pack('secret_scan', result,
                 [STATIC_ONLY,
                  'values are masked: only the first 4 characters, the length and a sha256 fingerprint prefix '
                  'are returned; the line text is never echoed',
                  'patterns: AWS key ids, sk- tokens, GitHub/Slack tokens, private-key headers, '
                  'password/secret/api_key assignments, quoted strings >= min_length with Shannon entropy >= min_entropy',
                  'ignore_files (glob) skips fixtures; ignore_hashes skips known fake values by fingerprint'],
                 [f'<= {MAX_FILES} files, <= {MAX_FINDINGS} findings',
                  'heuristic: false positives (hashes, UUID-like ids) and false negatives (split, encoded or '
                  'runtime-built secrets) are expected',
                  'a finding is not verified against any provider; nothing leaves this process'])


# --------------------------------------------------------------------------- 11.06 race_check

_EX_LOG = [
    {'actor': 'A', 'op': 'write', 'path': 'out.json', 't_start': 0.0, 't_end': 1.0},
    {'actor': 'B', 'op': 'write', 'path': 'out.json', 't_start': 0.5, 't_end': 1.5},
    {'actor': 'A', 'op': 'lock', 'path': 'db', 't_start': 0.0, 't_end': 0.1},
    {'actor': 'A', 'op': 'write', 'path': 'db', 't_start': 0.1, 't_end': 1.0},
    {'actor': 'A', 'op': 'unlock', 'path': 'db', 't_start': 1.0, 't_end': 1.0},
    {'actor': 'B', 'op': 'lock', 'path': 'db', 't_start': 0.05, 't_end': 1.05},
    {'actor': 'B', 'op': 'write', 'path': 'db', 't_start': 1.05, 't_end': 2.0},
    {'actor': 'B', 'op': 'unlock', 'path': 'db', 't_start': 2.0, 't_end': 2.0},
]


def race_check(*, log=None, **extra):
    """Overlapping write/write or write/read on one path by different actors without a held lock."""
    _no_extra(extra)
    if log is None:
        log = _EX_LOG
    if not isinstance(log, list) or not log or len(log) > MAX_LOG:
        raise ValueError(f'log must be a non-empty list of at most {MAX_LOG} entries')
    events = []
    for i, e in enumerate(log):
        if not isinstance(e, dict) or set(e) - {'actor', 'op', 'path', 't_start', 't_end', 'id'} \
                or not {'actor', 'op', 'path', 't_start', 't_end'} <= set(e):
            raise ValueError(f'log[{i}] must have exactly actor, op, path, t_start, t_end (optional id)')
        actor = _str(e['actor'], f'log[{i}].actor', 200)
        path = _str(e['path'], f'log[{i}].path', 1000)
        if e['op'] not in ('read', 'write', 'lock', 'unlock'):
            raise ValueError(f'log[{i}].op must be read, write, lock or unlock')
        t0 = _num(e['t_start'], -1e12, 1e12, f'log[{i}].t_start')
        t1 = _num(e['t_end'], -1e12, 1e12, f'log[{i}].t_end')
        if t1 < t0:
            raise ValueError(f'log[{i}].t_end must be >= t_start')
        events.append({'i': i, 'actor': actor, 'op': e['op'], 'path': path, 't0': t0, 't1': t1})

    held, open_locks, warnings_ = {}, {}, []
    for ev in sorted(events, key=lambda x: (x['t0'], x['i'])):
        key = (ev['actor'], ev['path'])
        if ev['op'] == 'lock':
            if key in open_locks:
                warnings_.append({'entry': ev['i'], 'message': 're-lock while already held (ignored)'})
            else:
                open_locks[key] = ev['t1']  # acquired when the lock call returns
        elif ev['op'] == 'unlock':
            if key not in open_locks:
                warnings_.append({'entry': ev['i'], 'message': 'unlock without a held lock'})
            else:
                held.setdefault(key, []).append((open_locks.pop(key), ev['t0']))
    for key, t in sorted(open_locks.items()):
        held.setdefault(key, []).append((t, math.inf))
        warnings_.append({'entry': None, 'message': f'lock on {key[1]!r} by {key[0]!r} never released'})

    def protected(ev):
        return any(a <= ev['t0'] and ev['t1'] <= b for a, b in held.get((ev['actor'], ev['path']), []))

    races = []
    by_path = {}
    for ev in events:
        if ev['op'] in ('read', 'write'):
            by_path.setdefault(ev['path'], []).append(ev)
    for path in sorted(by_path):
        acc = sorted(by_path[path], key=lambda x: (x['t0'], x['i']))
        for a_i, a in enumerate(acc):
            for b in acc[a_i + 1:]:
                if b['t0'] >= a['t1'] and not (a['t0'] == a['t1'] == b['t0']):
                    break
                if a['actor'] == b['actor'] or 'write' not in (a['op'], b['op']):
                    continue
                if not (a['t0'] < b['t1'] and b['t0'] < a['t1']):
                    continue
                pa, pb = protected(a), protected(b)
                if pa and pb:
                    continue
                races.append({'path': path, 'kind': f"{a['op']}/{b['op']}",
                              'entries': [a['i'], b['i']], 'actors': [a['actor'], b['actor']],
                              'overlap': [max(a['t0'], b['t0']), min(a['t1'], b['t1'])],
                              'locked': [pa, pb]})
                if len(races) >= MAX_FINDINGS:
                    break
    lock_overlaps = []
    by_lock_path = {}
    for (actor, path), ivs in held.items():
        for a, b in ivs:
            by_lock_path.setdefault(path, []).append((a, b, actor))
    for path in sorted(by_lock_path):
        ivs = sorted(by_lock_path[path], key=lambda x: (x[0], x[2]))
        for k, (a0, a1, aa) in enumerate(ivs):
            for b0, b1, ba in ivs[k + 1:]:
                if b0 >= a1:
                    break
                if aa != ba:
                    lock_overlaps.append({'path': path, 'actors': [aa, ba],
                                          'overlap': [b0, min(a1, b1) if math.isfinite(min(a1, b1)) else None]})
    result = {'races': races, 'race_count': len(races), 'lock_overlaps': lock_overlaps,
              'warnings': warnings_, 'entries': len(events)}
    return _pack('race_check', result,
                 ['the log is data supplied by the caller; nothing is run or timed here',
                  'a lock is held from the t_end of its lock entry (acquired) to the t_start of the matching unlock',
                  'an access is protected when it lies entirely inside a lock interval held by the same actor on the same path',
                  'a race = different actors, at least one write, overlapping [t_start, t_end], not both protected',
                  'lock_overlaps lists times two actors held the same lock at once (a broken lock or a bad log)'],
                 [f'<= {MAX_LOG} log entries, <= {MAX_FINDINGS} races',
                  'paths are compared as exact strings (no normalisation, no directory/parent locks)',
                  'only races visible in this log are found; other interleavings are not explored'])


# --------------------------------------------------------------------------- 11.07 traceback_repro

_EX_TB = '''Traceback (most recent call last):
  File "/app/main.py", line 42, in <module>
    main()
  File "/app/main.py", line 38, in main
    total = compute(rows)
  File "/app/stats.py", line 12, in compute
    return sum(r["value"] for r in rows) / len(rows)
           ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~^~~~~~~~~~~
ZeroDivisionError: division by zero
'''

_FRAME = re.compile(r'^\s*File "(?P<file>[^"]+)", line (?P<line>\d+)(?:, in (?P<func>.+?))?\s*$')
_CARET = re.compile(r'^\s*[\^~]+\s*$')
_EXC = re.compile(r'^(?P<type>[A-Za-z_][\w.]*)(?::\s?(?P<msg>.*))?$')
_CHAIN = ('During handling of the above exception, another exception occurred:',
          'The above exception was the direct cause of the following exception:')


def _parse_tb(text):
    blocks, cur = [], []
    for raw in text.splitlines():
        if raw.strip() in _CHAIN:
            blocks.append((cur, None))
            cur = []
            blocks[-1] = (blocks[-1][0], raw.strip())
            continue
        cur.append(raw)
    blocks.append((cur, None))
    chain = []
    for lines, link in blocks:
        frames, exc_type, exc_msg, i = [], None, None, 0
        while i < len(lines):
            line = lines[i]
            m = _FRAME.match(line)
            if m:
                frame = {'file': m.group('file'), 'line': int(m.group('line')),
                         'function': (m.group('func') or '').strip() or None, 'code': None}
                j = i + 1
                if j < len(lines) and lines[j].startswith((' ', '\t')) and not _FRAME.match(lines[j]) \
                        and not _CARET.match(lines[j]) and lines[j].strip():
                    frame['code'] = lines[j].strip()[:300]
                    j += 1
                while j < len(lines) and _CARET.match(lines[j]):
                    j += 1
                frames.append(frame)
                i = j
                continue
            s = line.rstrip()
            if s and not s.startswith((' ', '\t')) and not s.startswith('Traceback (most recent call last)'):
                em = _EXC.match(s)
                if em and exc_type is None:
                    exc_type, exc_msg = em.group('type'), (em.group('msg') or '')
                elif exc_type is not None:
                    exc_msg = (exc_msg + '\n' + s)[:2000]
            elif s.strip().startswith('[Previous line repeated') and frames:
                frames[-1]['repeated'] = s.strip()
            i += 1
        if frames or exc_type:
            chain.append({'frames': frames, 'exception_type': exc_type,
                          'message': exc_msg, 'link_to_next': link})
    return chain


def _is_library(path):
    p = path.replace('\\', '/').lower()
    return (p.startswith('<') or 'site-packages' in p or 'dist-packages' in p
            or re.search(r'/lib/python\d', p) is not None or '/lib/python/' in p
            or re.search(r'/python\d*/lib/', p) is not None)


def _outcome(value, name):
    if isinstance(value, str):
        v = value.strip()
        if 'Traceback (most recent call last)' in v:
            chain = _parse_tb(_str(v, name))
            last = chain[-1] if chain else {}
            frames = last.get('frames') or []
            return {'status': 'error', 'exception_type': last.get('exception_type'),
                    'failing_frame': [frames[-1]['file'], frames[-1]['function']] if frames else None,
                    'output': None}
        low = v.lower()
        if low in ('ok', 'pass', 'passed', 'success'):
            return {'status': 'ok', 'exception_type': None, 'failing_frame': None, 'output': None}
        if low in ('error', 'fail', 'failed', 'exception'):
            return {'status': 'error', 'exception_type': None, 'failing_frame': None, 'output': None}
        raise ValueError(f'{name} must be ok/error, a traceback text or a dict')
    if isinstance(value, dict):
        if set(value) - {'status', 'exception_type', 'message', 'output', 'failing_frame'}:
            raise ValueError(f'{name} has unknown keys')
        status = value.get('status')
        if status not in ('ok', 'error'):
            raise ValueError(f'{name}.status must be "ok" or "error"')
        out = value.get('output')
        try:
            json.dumps(out, allow_nan=False)
        except (TypeError, ValueError):
            raise ValueError(f'{name}.output must be JSON data') from None
        et = value.get('exception_type')
        if et is not None and not isinstance(et, str):
            raise ValueError(f'{name}.exception_type must be a string')
        ff = value.get('failing_frame')
        if ff is not None and (not isinstance(ff, list) or not all(isinstance(x, (str, type(None))) for x in ff)):
            raise ValueError(f'{name}.failing_frame must be a list of strings')
        return {'status': status, 'exception_type': et, 'failing_frame': ff, 'output': out}
    raise ValueError(f'{name} must be a string or a dict')


def compare_runs(before, after):
    """Verdict for two run outcomes supplied as data (no code is run)."""
    b, a = _outcome(before, 'before'), _outcome(after, 'after')
    if b['status'] == 'error' and a['status'] == 'ok':
        verdict = 'fixed'
    elif b['status'] == 'ok' and a['status'] == 'error':
        verdict = 'regressed'
    elif b['status'] == 'error':
        same = b['exception_type'] == a['exception_type'] and (
            b['failing_frame'] is None or a['failing_frame'] is None or b['failing_frame'] == a['failing_frame'])
        verdict = 'still_failing' if same else 'changed_error'
    else:
        verdict = 'ok_output_changed' if (b['output'] is not None and a['output'] is not None
                                          and b['output'] != a['output']) else 'unchanged_ok'
    return {'verdict': verdict, 'before': b, 'after': a}


def traceback_repro(*, traceback=None, before=None, after=None, seed=0, **extra):
    """Parse a traceback into frames + exception and build a reproduction record."""
    _no_extra(extra)
    text = _str(_EX_TB if traceback is None else traceback, 'traceback')
    seed = _int(seed, 0, 2 ** 32 - 1, 'seed')
    if (before is None) != (after is None):
        raise ValueError('give both before and after, or neither')
    chain = _parse_tb(text)
    if not chain or not any(c['frames'] for c in chain):
        raise ValueError('no traceback frames found')
    main = chain[-1]
    frames = main['frames'] or next(c['frames'] for c in reversed(chain) if c['frames'])
    project = [f for f in frames if not _is_library(f['file'])]
    fp_src = json.dumps([main['exception_type'], [[f['file'], f['function']] for f in frames]])
    repro = {
        'entry_frame': frames[0], 'failing_frame': frames[-1],
        'failing_project_frame': project[-1] if project else None,
        'exception': {'type': main['exception_type'], 'message': main['message']},
        'inputs': {'args': [], 'kwargs': {},
                   'note': 'placeholder: fill with the values that reached the failing frame'},
        'seed': seed,
        'fingerprint': hashlib.sha256(fp_src.encode()).hexdigest()[:16],
        'steps': [f"call {frames[-1]['function'] or '<unknown>'} in {frames[-1]['file']} "
                  f"(line {frames[-1]['line']}) with the captured inputs and seed {seed}",
                  f"expect {main['exception_type'] or 'the error'} before the fix and no error after it",
                  'record both outcomes and pass them as before/after to get a verdict'],
    }
    result = {'exception_type': main['exception_type'], 'message': main['message'],
              'frames': frames, 'chain': chain, 'repro': repro,
              'check': compare_runs(before, after) if before is not None else None}
    return _pack('traceback_repro', result,
                 ['the traceback is parsed as text; no code is run, imported or re-executed',
                  'the last exception in a chained traceback is the main one; earlier ones are kept in chain',
                  'library frames = paths under site-packages/dist-packages/lib/pythonX or <frozen ...>',
                  'verdict: error->ok fixed, ok->error regressed, same type+frame still_failing, else changed_error'],
                 [f'traceback text <= {MAX_TEXT} characters',
                  'ExceptionGroup (| prefixed) and non-CPython formats are not parsed specially',
                  'inputs are a placeholder: the actual failing values are not recoverable from a traceback'])


# --------------------------------------------------------------------------- 11.08 complexity

_EX_COMPLEXITY = {'perf.py': (
    'def simple(x):\n    return x + 1\n\n'
    'def classify(x):\n    if x > 0 and x < 10:\n        return "small"\n    elif x >= 10:\n'
    '        return "big"\n    return "neg"\n\n'
    'def triple(m):\n    t = 0\n    for a in m:\n        for b in a:\n            for c in b:\n'
    '                t += c\n    return t\n')}

_LOOPS = (ast.For, ast.AsyncFor, ast.While)
_COMPS = (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)
_NESTED = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)


def _decisions(fn):
    total = 0
    for n in _scope_nodes(fn):
        if isinstance(n, (ast.If, ast.IfExp, ast.ExceptHandler) + _LOOPS):
            total += 1
        elif isinstance(n, ast.comprehension):
            total += 1 + len(n.ifs)
        elif isinstance(n, ast.BoolOp):
            total += len(n.values) - 1
        elif isinstance(n, ast.match_case):
            total += 1
    return total


def _loop_depth(node, depth=0):
    best = depth
    for child in ast.iter_child_nodes(node):
        if isinstance(child, _NESTED):
            continue
        if isinstance(child, _LOOPS):
            best = max(best, _loop_depth(child, depth + 1))
        elif isinstance(child, _COMPS):
            best = max(best, depth + len(child.generators), _loop_depth(child, depth + len(child.generators)))
        else:
            best = max(best, _loop_depth(child, depth))
    return best


def complexity(*, files=None, nested_threshold=3, complexity_threshold=10, **extra):
    """Cyclomatic complexity, loop nesting depth and a growth hint per function."""
    _no_extra(extra)
    files = _files(files, _EX_COMPLEXITY)
    nested_threshold = _int(nested_threshold, 1, 50, 'nested_threshold')
    complexity_threshold = _int(complexity_threshold, 1, 1000, 'complexity_threshold')
    rows, parse_errors = [], []
    for name, src in files.items():
        tree, err = _try_parse(src, name)
        if err:
            parse_errors.append(err)
            continue
        for qual, fn in _sorted_functions(tree):
            try:
                cc = _decisions(fn) + 1
                depth = _loop_depth(fn)
            except RecursionError:
                continue
            flags = []
            if depth >= nested_threshold:
                flags.append(f'nested_loops>={nested_threshold}')
            if cc >= complexity_threshold:
                flags.append(f'complexity>={complexity_threshold}')
            rows.append({'file': name, 'function': qual, 'line': fn.lineno,
                         'cyclomatic': cc, 'max_loop_depth': depth,
                         'growth_hint': 'O(1)' if depth == 0 else ('O(n)' if depth == 1 else f'O(n^{depth})'),
                         'flags': flags})
            if len(rows) >= 5000:
                break
    worst = None
    if rows:
        w = max(rows, key=lambda r: (r['max_loop_depth'], r['cyclomatic'], -r['line'], r['file']))
        worst = {k: w[k] for k in ('file', 'function', 'line', 'cyclomatic', 'max_loop_depth', 'growth_hint')}
    result = {'functions': rows, 'worst_case': worst,
              'flagged': [r for r in rows if r['flags']], 'parse_errors': parse_errors}
    return _pack('complexity', result,
                 [STATIC_ONLY,
                  'cyclomatic = 1 + if/elif/ternary/for/while/except/case + comprehension for/if clauses '
                  '+ (operands - 1) of each and/or chain; nested defs are measured separately',
                  'growth hint = O(n^loop_depth), assuming every loop runs over an input of size n'],
                 [f'<= {MAX_FILES} files, <= 5000 functions reported',
                  'the growth hint ignores early exits, recursion, called functions and costly built-ins '
                  '(e.g. list.index inside a loop), so it is a hint, not a bound'])


# --------------------------------------------------------------------------- 11.09 boundary_cases

_EX_SPEC = {'age': {'type': 'int', 'min': 0, 'max': 120},
            'ratio': {'type': 'float', 'min': 0.0, 'max': 1.0},
            'mode': {'type': 'str', 'allowed': ['fast', 'safe']}}
_EX_RESULTS = {'age:min': True, 'age:max': True, 'age:below_min': False, 'age:above_max': True,
               'ratio:nan': True}
_TYPES = ('int', 'float', 'str', 'bool')


def _case(cases, name, label, value, expected, repr_=None):
    c = {'id': f'{name}:{label}', 'param': name, 'value': value, 'expected': expected}
    if repr_:
        c['value_repr'] = repr_
    cases.append(c)


def boundary_cases(*, spec=None, results=None, **extra):
    """Generate boundary/invalid cases from a spec and report validation bypasses."""
    _no_extra(extra)
    if spec is None:
        spec = _EX_SPEC
        if results is None:
            results = _EX_RESULTS
    if not isinstance(spec, dict) or not spec or len(spec) > 100:
        raise ValueError('spec must be a non-empty dict of at most 100 parameters')
    cases = []
    for name in sorted(spec, key=str):
        s = spec[name]
        if not isinstance(name, str) or not name or len(name) > 100:
            raise ValueError('spec names must be non-empty strings')
        if not isinstance(s, dict) or set(s) - {'type', 'min', 'max', 'allowed', 'required'}:
            raise ValueError(f'spec[{name!r}] may only have type, min, max, allowed, required')
        typ = s.get('type')
        if typ not in _TYPES:
            raise ValueError(f'spec[{name!r}].type must be one of {list(_TYPES)}')
        required = s.get('required', True)
        if not isinstance(required, bool):
            raise ValueError(f'spec[{name!r}].required must be a bool')
        lo, hi = s.get('min'), s.get('max')
        lim = 1e15
        if typ == 'int':
            lo = None if lo is None else _int(lo, -10 ** 15, 10 ** 15, f'{name}.min')
            hi = None if hi is None else _int(hi, -10 ** 15, 10 ** 15, f'{name}.max')
        elif typ == 'float':
            lo = None if lo is None else _num(lo, -lim, lim, f'{name}.min')
            hi = None if hi is None else _num(hi, -lim, lim, f'{name}.max')
        elif typ == 'str':
            lo = None if lo is None else _int(lo, 0, 100_000, f'{name}.min (length)')
            hi = None if hi is None else _int(hi, 0, 100_000, f'{name}.max (length)')
        elif lo is not None or hi is not None:
            raise ValueError(f'spec[{name!r}]: bool takes no min/max')
        if lo is not None and hi is not None and lo > hi:
            raise ValueError(f'spec[{name!r}]: min > max')
        allowed = s.get('allowed')
        if allowed is not None:
            if not isinstance(allowed, list) or not allowed or len(allowed) > 50:
                raise ValueError(f'spec[{name!r}].allowed must be a non-empty list (<= 50)')
            for v in allowed:
                ok = {'int': isinstance(v, int) and not isinstance(v, bool),
                      'float': isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v),
                      'str': isinstance(v, str) and len(v) <= 1000,
                      'bool': isinstance(v, bool)}[typ]
                if not ok:
                    raise ValueError(f'spec[{name!r}].allowed values must match type {typ}')
        if typ in ('int', 'float'):
            step = 1 if typ == 'int' else 1.0
            if lo is not None:
                _case(cases, name, 'min', lo, 'valid')
                _case(cases, name, 'below_min', lo - step, 'invalid')
            if hi is not None:
                _case(cases, name, 'max', hi, 'valid')
                _case(cases, name, 'above_max', hi + step, 'invalid')
            _case(cases, name, 'wrong_type', 'not-a-number', 'invalid')
            _case(cases, name, 'bool_as_number', True, 'invalid')
            if typ == 'float':
                _case(cases, name, 'nan', None, 'invalid', 'nan')
                _case(cases, name, 'inf', None, 'invalid', 'inf')
        elif typ == 'str':
            if lo is not None:
                _case(cases, name, 'min_length', 'a' * lo, 'valid')
                if lo > 0:
                    _case(cases, name, 'below_min_length', 'a' * (lo - 1), 'invalid')
            if hi is not None:
                _case(cases, name, 'max_length', 'a' * min(hi, 10_000), 'valid',
                      None if hi <= 10_000 else f"'a' * {hi}")
                _case(cases, name, 'above_max_length', 'a' * min(hi + 1, 10_001), 'invalid',
                      None if hi < 10_000 else f"'a' * {hi + 1}")
            _case(cases, name, 'wrong_type', 12345, 'invalid')
            if not allowed:
                _case(cases, name, 'empty', '', 'invalid' if (lo or 0) > 0 else 'valid')
        else:
            _case(cases, name, 'true', True, 'valid')
            _case(cases, name, 'false', False, 'valid')
            _case(cases, name, 'string_true', 'true', 'invalid')
            _case(cases, name, 'int_one', 1, 'invalid')
        if allowed:
            for k, v in enumerate(allowed[:20]):
                _case(cases, name, f'allowed_{k}', v, 'valid')
            if typ == 'str':
                bad = '__not_allowed__'
                while bad in allowed:
                    bad += '_'
                _case(cases, name, 'not_allowed', bad, 'invalid')
                _case(cases, name, 'empty', '', 'invalid' if '' not in allowed else 'valid')
            elif typ in ('int', 'float'):
                _case(cases, name, 'not_allowed', max(allowed) + 1, 'invalid')
        _case(cases, name, 'missing', None, 'invalid' if required else 'valid', 'missing/None')
    ids = {c['id'] for c in cases}
    bypasses, false_rejections, untested = [], [], []
    if results is not None:
        if not isinstance(results, dict):
            raise ValueError('results must be a dict {case_id: accepted_bool}')
        unknown = sorted(set(results) - ids, key=str)
        if unknown:
            raise ValueError(f'results has unknown case ids: {unknown[:5]}')
        for k, v in results.items():
            if not isinstance(v, bool):
                raise ValueError(f'results[{k!r}] must be true/false (accepted?)')
        for c in cases:
            if c['id'] not in results:
                untested.append(c['id'])
            elif c['expected'] == 'invalid' and results[c['id']]:
                bypasses.append({'id': c['id'], 'param': c['param'],
                                 'value': c.get('value_repr', c['value']),
                                 'message': 'invalid input was accepted'})
            elif c['expected'] == 'valid' and not results[c['id']]:
                false_rejections.append({'id': c['id'], 'param': c['param'],
                                         'message': 'valid boundary value was rejected'})
    result = {'cases': cases, 'case_count': len(cases), 'evaluated': results is not None,
              'bypasses': bypasses, 'false_rejections': false_rejections, 'untested': untested}
    return _pack('boundary_cases', result,
                 ['cases are generated from the spec only; the validator is never called here',
                  'min/max are inclusive; for str they bound the length; numeric step outside the range is 1',
                  'NaN/inf are given as value null + value_repr (JSON has no NaN)',
                  'results map case id -> accepted? as observed by the caller; invalid+accepted = bypass'],
                 ['<= 100 parameters, <= 20 allowed values expanded each, string cases capped at 10001 chars',
                  'cross-field rules, formats (email, dates) and injection payloads are not generated'])


# --------------------------------------------------------------------------- 11.10 diff_review

_EX_DIFF = '''diff --git a/app/util.py b/app/util.py
--- a/app/util.py
+++ b/app/util.py
@@ -1,6 +1,3 @@
 import math
-def legacy_round(x):
-    return math.floor(x + 0.5)
-
 def area(r):
     return math.pi * r * r
diff --git a/tests/test_util.py b/tests/test_util.py
deleted file mode 100644
--- a/tests/test_util.py
+++ /dev/null
@@ -1,3 +0,0 @@
-from app.util import legacy_round
-def test_legacy_round():
-    assert legacy_round(1.5) == 2
'''

_DEF = re.compile(r'^\s*(async\s+def|def|class)\s+([A-Za-z_]\w*)')
_HUNK = re.compile(r'^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@')


def _strip_prefix(p):
    p = p.split('\t', 1)[0].strip()
    if p.startswith('"') and p.endswith('"'):
        p = p[1:-1]
    if p.startswith(('a/', 'b/')):
        p = p[2:]
    return p


def _is_test_path(p):
    base = p.replace('\\', '/').rsplit('/', 1)[-1]
    return base.startswith('test_') or base.endswith('_test.py') or '/tests/' in '/' + p.replace('\\', '/')


def diff_review(*, diff=None, **extra):
    """Summarise a unified diff and flag removed defs/classes/tests and deleted files."""
    _no_extra(extra)
    text = _str(_EX_DIFF if diff is None else diff, 'diff')
    files, cur = [], None
    old_rem = new_rem = 0
    old_no = new_no = 0

    def new_file(old=None, new=None):
        f = {'old_path': old, 'new_path': new, 'status': 'modified', 'added': 0, 'removed': 0,
             'binary': False, '_removed_defs': [], '_added_defs': []}
        files.append(f)
        return f

    for line in text.splitlines():
        if cur is not None and (old_rem > 0 or new_rem > 0):
            if line.startswith('\\'):
                continue
            tag = line[:1]
            if tag == '+':
                cur['added'] += 1
                new_rem -= 1
                m = _DEF.match(line[1:])
                if m:
                    cur['_added_defs'].append((m.group(1).split()[-1], m.group(2), new_no))
                new_no += 1
                continue
            if tag == '-':
                cur['removed'] += 1
                old_rem -= 1
                m = _DEF.match(line[1:])
                if m:
                    cur['_removed_defs'].append((m.group(1).split()[-1], m.group(2), old_no))
                old_no += 1
                continue
            if tag == ' ' or line == '':
                old_rem -= 1
                new_rem -= 1
                old_no += 1
                new_no += 1
                continue
            old_rem = new_rem = 0  # malformed hunk: fall through to header parsing
        if line.startswith('diff --git '):
            m = re.match(r'^diff --git (?:"?a/)?(.+?)"? (?:"?b/)?(.+?)"?$', line)
            cur = new_file(*(m.groups() if m else (None, None)))
        elif line.startswith('--- '):
            path = line[4:]
            if cur is None or cur['added'] or cur['removed']:
                cur = new_file()
            cur['old_path'] = None if path.strip().startswith('/dev/null') else _strip_prefix(path)
            if cur['old_path'] is None:
                cur['status'] = 'added'
        elif line.startswith('+++ ') and cur is not None:
            path = line[4:]
            cur['new_path'] = None if path.strip().startswith('/dev/null') else _strip_prefix(path)
            if cur['new_path'] is None:
                cur['status'] = 'deleted'
        elif cur is not None and line.startswith('new file mode'):
            cur['status'] = 'added'
        elif cur is not None and line.startswith('deleted file mode'):
            cur['status'] = 'deleted'
        elif cur is not None and line.startswith('rename from '):
            cur['old_path'], cur['status'] = line[12:].strip(), 'renamed'
        elif cur is not None and line.startswith('rename to '):
            cur['new_path'], cur['status'] = line[10:].strip(), 'renamed'
        elif cur is not None and line.startswith('Binary files'):
            cur['binary'] = True
        elif line.startswith('@@'):
            m = _HUNK.match(line)
            if m is None or cur is None:
                raise ValueError(f'malformed hunk header: {line[:80]!r}')
            old_no, new_no = int(m.group(1)), int(m.group(3))
            old_rem = int(m.group(2)) if m.group(2) is not None else 1
            new_rem = int(m.group(4)) if m.group(4) is not None else 1
        if len(files) > 5000:
            raise ValueError('diff touches more than 5000 files')
    if not files:
        raise ValueError('no file sections found in diff')
    for f in files:
        if f['status'] == 'deleted':
            f['new_path'] = None
        if f['status'] == 'added':
            f['old_path'] = None
        f['path'] = f['new_path'] or f['old_path']

    added_names = {(k if k == 'class' else 'def', n) for f in files for k, n, _ in f['_added_defs']}
    flags, changed = [], []
    for f in files:
        if f['status'] == 'deleted':
            flags.append({'kind': 'deleted_test_file' if _is_test_path(f['path']) else 'deleted_file',
                          'file': f['path'], 'severity': 'high' if _is_test_path(f['path']) else 'medium',
                          'message': 'file deleted'})
        for kind, nm, ln in f['_removed_defs']:
            key = ('class' if kind == 'class' else 'def', nm)
            if key in added_names:
                changed.append({'file': f['path'], 'name': nm, 'kind': key[0], 'old_line': ln})
                continue
            is_test = (key[0] == 'def' and nm.startswith('test')) or (key[0] == 'class' and nm.startswith('Test'))
            flags.append({'kind': 'removed_test' if is_test else 'removed_definition',
                          'file': f['path'], 'name': nm, 'definition': key[0], 'old_line': ln,
                          'severity': 'high' if is_test else 'medium',
                          'message': f'{key[0]} {nm} removed and not re-added anywhere in this diff'})
    summary = [{k: f[k] for k in ('path', 'old_path', 'new_path', 'status', 'added', 'removed', 'binary')}
               for f in files]
    result = {'files': summary, 'files_changed': len(files),
              'lines_added': sum(f['added'] for f in files),
              'lines_removed': sum(f['removed'] for f in files),
              'flags': flags[:MAX_FINDINGS], 'moved_or_modified_definitions': changed[:MAX_FINDINGS],
              'verdict': 'needs_attention' if flags else 'no_structural_flags'}
    return _pack('diff_review', result,
                 ['the diff is parsed as text (git/unified format); the code is not checked out or run',
                  'a removed def/class is cleared when a def/class with the same name is added anywhere in the diff '
                  '(treated as move/rename/edit)',
                  'tests = def test*/class Test*; test files = test_*.py, *_test.py or under tests/'],
                 [f'diff text <= {MAX_TEXT} characters, <= 5000 files',
                  'definitions are matched by name with a regex, not by AST; decorators, nesting and other '
                  'languages are not understood',
                  'renamed functions (new name) are reported as removed; behaviour changes inside bodies are not judged'])


# --------------------------------------------------------------------------- dispatcher

OPS = {
    'syntax_check': syntax_check, 'import_cycles': import_cycles,
    'duplicate_functions': duplicate_functions, 'resource_handling': resource_handling,
    'secret_scan': secret_scan, 'race_check': race_check, 'traceback_repro': traceback_repro,
    'complexity': complexity, 'boundary_cases': boundary_cases, 'diff_review': diff_review,
}


def run(op, params=None):
    """Validate and dispatch: run('syntax_check', {'files': {...}}) -> {'op','result','assumptions','limits'}."""
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
