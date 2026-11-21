"""Red Rose V22: architecture helpers (topics 02.01, 02.03-02.10).

Pure standard-library Python. No file I/O, no subprocess, no network, no printing,
no environment access. Listings, configs, command specs, availability maps and
checkpoints all arrive as parameters; nothing is read from the machine.

Every op validates its inputs strictly (ValueError on wrong types, bools used as
numbers, unknown parameter names and out-of-range sizes), caps its work, is
deterministic and returns {'op', 'result', 'assumptions', 'limits'} where the
result is JSON-serialisable. run(op, {}) works for every op with a tiny built-in
example.
"""
from __future__ import annotations

import fnmatch
import hashlib
import json
import math
import ntpath
import posixpath
import re
import unicodedata
from pathlib import PurePosixPath, PureWindowsPath

MAX_PARAMS = 24
MAX_ITEMS = 2_000
MAX_JSON_BYTES = 256_000
MAX_STR = 4_096

TOPICS = {
    '02.01': 'cli_spec_check',
    '02.03': 'message_schema',
    '02.04': 'distribution_guard',
    '02.05': 'dependency_status',
    '02.06': 'config_redact',
    '02.07': 'cache_key',
    '02.08': 'checkpoint_resume',
    '02.09': 'path_portability',
    '02.10': 'semver_migrate',
}

TOPIC_NAMES_AR = {
    '02.01': 'نقطة دخول واحدة للواجهة',
    '02.03': 'بروتوكول تبادل بين الوحدات',
    '02.04': 'عزل الذاكرة عن الكود',
    '02.05': 'حل الاعتماديات والمكتبات',
    '02.06': 'إدارة الإعدادات دون أسرار',
    '02.07': 'مخازن مؤقتة واعية بالأذونات',
    '02.08': 'استعادة المهام بعد الفشل',
    '02.09': 'قابلية النقل بين الأنظمة',
    '02.10': 'قواعد توافق الإصدارات',
}


# --------------------------------------------------------------------------- validation

def _no_extra(extra):
    if extra:
        raise ValueError('unknown parameter(s): ' + ', '.join(sorted(map(str, extra))))


def _int(value, low, high, name):
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise ValueError(f'{name} must be an integer from {low} to {high}')
    return value


def _bool(value, name):
    if not isinstance(value, bool):
        raise ValueError(f'{name} must be true or false')
    return value


def _str(value, name, *, max_len=MAX_STR, allow_empty=False):
    if not isinstance(value, str) or (not allow_empty and not value) or len(value) > max_len:
        raise ValueError(f'{name} must be a {"" if allow_empty else "non-empty "}string '
                         f'of at most {max_len} characters')
    return value


def _list(value, name, max_items=MAX_ITEMS, *, allow_empty=True):
    if not isinstance(value, (list, tuple)) or len(value) > max_items or (not allow_empty and not value):
        raise ValueError(f'{name} must be a list of at most {max_items} items')
    return list(value)


def _dict(value, name, max_items=MAX_ITEMS):
    if not isinstance(value, dict) or len(value) > max_items:
        raise ValueError(f'{name} must be a dict of at most {max_items} entries')
    if not all(isinstance(k, str) for k in value):
        raise ValueError(f'{name} keys must be strings')
    return value


def _canon(obj, name='value', max_bytes=MAX_JSON_BYTES):
    """Canonical JSON (sorted keys, no whitespace, ASCII-escaped, no NaN)."""
    try:
        text = json.dumps(obj, sort_keys=True, separators=(',', ':'), ensure_ascii=True,
                          allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError(f'{name} must be JSON-serialisable without NaN/inf: {exc}') from None
    if len(text) > max_bytes:
        raise ValueError(f'{name} is larger than {max_bytes} bytes of canonical JSON')
    return text


def _sha(obj, name='value'):
    return hashlib.sha256(_canon(obj, name).encode('ascii')).hexdigest()


def _copy(obj, name='value'):
    return json.loads(_canon(obj, name))


def _pack(op, result, assumptions, limits):
    return {'op': op, 'result': result, 'assumptions': list(assumptions), 'limits': list(limits)}


# =========================================================================== 02.01 CLI spec

CLI_TYPES = ('bool', 'flag', 'float', 'int', 'path', 'str')
_ARG_NAME = re.compile(r'^(--)?[a-z][a-z0-9_-]{0,47}$')
_CMD_NAME = re.compile(r'^[a-z][a-z0-9_-]{0,47}$')
_NUMBER = re.compile(r'^-\d+(\.\d+)?$')
_TRUE = {'true', '1', 'yes', 'on'}
_FALSE = {'false', '0', 'no', 'off'}

DEFAULT_CLI_SPEC = {
    'commands': {
        'render': {'args': {
            'input': {'type': 'path', 'required': True},
            '--fps': {'type': 'int', 'default': 30},
            '--preset': {'type': 'str', 'choices': ['draft', 'final'], 'default': 'draft'},
            '--dry-run': {'type': 'flag'},
        }},
        'doctor': {'args': {'--verbose': {'type': 'flag'}}},
    }
}


def _convert(raw, typ, name):
    """Convert a raw argv token to typ; returns (ok, value_or_error)."""
    if typ in ('str', 'path'):
        if typ == 'path' and not raw:
            return False, f'{name}: empty path'
        return True, raw
    if typ == 'int':
        if re.fullmatch(r'[+-]?\d{1,18}', raw):
            return True, int(raw)
        return False, f'{name}: expected an integer'
    if typ == 'float':
        if re.fullmatch(r'[+-]?(\d+(\.\d*)?|\.\d+)([eE][+-]?\d{1,3})?', raw):
            val = float(raw)
            if math.isfinite(val):
                return True, val
        return False, f'{name}: expected a finite number'
    if typ == 'bool':
        low = raw.lower()
        if low in _TRUE:
            return True, True
        if low in _FALSE:
            return True, False
        return False, f'{name}: expected true/false'
    return False, f'{name}: unsupported type'


def _type_ok_cli(value, typ):
    if typ in ('str', 'path'):
        return isinstance(value, str)
    if typ == 'int':
        return isinstance(value, int) and not isinstance(value, bool)
    if typ == 'float':
        return (isinstance(value, (int, float)) and not isinstance(value, bool)
                and math.isfinite(value))
    if typ in ('bool', 'flag'):
        return isinstance(value, bool)
    return False


def validate_cli_spec(spec):
    """Return (commands, issues). Structural garbage raises ValueError."""
    spec = _dict(spec, 'spec', 8)
    unknown = set(spec) - {'commands', 'prog', 'description'}
    if unknown:
        raise ValueError('spec has unknown key(s): ' + ', '.join(sorted(unknown)))
    commands = _dict(spec.get('commands'), 'spec.commands', 64)
    if not commands:
        raise ValueError('spec.commands must not be empty')
    issues = []
    out = {}
    for cname, cspec in commands.items():
        if not _CMD_NAME.match(cname):
            issues.append(f'command {cname!r}: name must match [a-z][a-z0-9_-]*')
        cspec = _dict(cspec, f'command {cname}', 8)
        bad = set(cspec) - {'args', 'help'}
        if bad:
            issues.append(f'command {cname!r}: unknown key(s) {sorted(bad)}')
        args = _dict(cspec.get('args', {}), f'command {cname}.args', 64)
        norm = {}
        seen_optional_positional = False
        dests = set()
        for aname, aspec in args.items():
            where = f'{cname} {aname}'
            if not _ARG_NAME.match(aname):
                issues.append(f'{where}: bad argument name')
                continue
            aspec = _dict(aspec, where, 8)
            badk = set(aspec) - {'type', 'choices', 'required', 'default', 'help'}
            if badk:
                issues.append(f'{where}: unknown key(s) {sorted(badk)}')
            typ = aspec.get('type', 'str')
            if typ not in CLI_TYPES:
                issues.append(f'{where}: type must be one of {list(CLI_TYPES)}')
                continue
            positional = not aname.startswith('--')
            required = aspec.get('required', positional and 'default' not in aspec)
            if not isinstance(required, bool):
                issues.append(f'{where}: required must be a bool')
                required = False
            choices = aspec.get('choices')
            if choices is not None:
                if (not isinstance(choices, list) or not choices or len(choices) > 64
                        or not all(_type_ok_cli(c, typ) for c in choices)):
                    issues.append(f'{where}: choices must be a non-empty list of {typ} values')
                    choices = None
                elif typ in ('flag', 'bool'):
                    issues.append(f'{where}: choices make no sense for {typ}')
            if typ == 'flag':
                if positional:
                    issues.append(f'{where}: a positional argument cannot be a flag')
                if required:
                    issues.append(f'{where}: a flag cannot be required')
            has_default = 'default' in aspec
            default = aspec.get('default', False if typ == 'flag' else None)
            if has_default:
                if not _type_ok_cli(default, typ):
                    issues.append(f'{where}: default does not match type {typ}')
                elif choices and default not in choices:
                    issues.append(f'{where}: default is not one of the choices')
                if required:
                    issues.append(f'{where}: a required argument should not have a default')
            if positional:
                if required and seen_optional_positional:
                    issues.append(f'{where}: required positional after an optional one')
                if not required:
                    seen_optional_positional = True
            dest = aname.lstrip('-').replace('-', '_')
            if dest in dests:
                issues.append(f'{where}: duplicate destination {dest!r}')
            dests.add(dest)
            norm[aname] = {'type': typ, 'required': required, 'choices': choices,
                           'default': default, 'dest': dest, 'positional': positional}
        out[cname] = norm
    return out, issues


def parse_argv(commands, argv):
    """Parse argv (list of str, command first) against validated commands. Never exits."""
    def fail(msg):
        return {'ok': False, 'command': None, 'values': None, 'error': msg}

    if not argv:
        return fail('no command given')
    cmd = argv[0]
    if cmd not in commands:
        return fail(f'unknown command {cmd!r}')
    args = commands[cmd]
    positional = [n for n, a in args.items() if a['positional']]
    values, given = {}, set()
    pos_i, i, only_positional = 0, 1, False
    while i < len(argv):
        tok = argv[i]
        if not only_positional and tok == '--':
            only_positional = True
        elif (not only_positional and tok.startswith('-') and tok != '-'
              and not _NUMBER.match(tok)):
            name, eq, raw = tok.partition('=')
            if name not in args or args[name]['positional']:
                return fail(f'unknown flag {name!r} for command {cmd!r}')
            if name in given:
                return fail(f'flag {name!r} given more than once')
            a = args[name]
            given.add(name)
            if a['type'] == 'flag':
                if eq:
                    return fail(f'flag {name!r} takes no value')
                values[a['dest']] = True
            else:
                if not eq:
                    i += 1
                    if i >= len(argv):
                        return fail(f'flag {name!r} needs a value')
                    raw = argv[i]
                ok, val = _convert(raw, a['type'], name)
                if not ok:
                    return fail(val)
                if a['choices'] and val not in a['choices']:
                    return fail(f'{name}: value not one of {a["choices"]}')
                values[a['dest']] = val
        else:
            if pos_i >= len(positional):
                return fail(f'unexpected positional argument #{pos_i + 1}')
            pname = positional[pos_i]
            a = args[pname]
            ok, val = _convert(tok, a['type'], pname)
            if not ok:
                return fail(val)
            if a['choices'] and val not in a['choices']:
                return fail(f'{pname}: value not one of {a["choices"]}')
            values[a['dest']] = val
            given.add(pname)
            pos_i += 1
        i += 1
    for name, a in args.items():
        if a['dest'] not in values:
            if a['required']:
                return fail(f'missing required argument {name!r}')
            values[a['dest']] = a['default']
    return {'ok': True, 'command': cmd, 'values': values, 'error': None}


def _example_argv(cmd, args):
    samples = {'str': 'x', 'path': 'example.txt', 'int': '1', 'float': '1.5', 'bool': 'true'}
    argv, tail = [cmd], []
    for name, a in args.items():
        if a['type'] == 'flag':
            tail.append(name)
            continue
        raw = str(a['choices'][0]) if a['choices'] else samples[a['type']]
        if a['type'] == 'bool' and a['choices']:
            raw = 'true' if a['choices'][0] else 'false'
        if a['positional']:
            argv.append(raw)
        else:
            tail += [name, raw]
    return argv + tail


def cli_spec_check(*, spec=None, argv=None, **extra):
    """Validate a CLI spec, parse a synthesised example per command, and parse argv."""
    _no_extra(extra)
    spec = DEFAULT_CLI_SPEC if spec is None else spec
    if argv is None:
        argv = ['render', 'in.mp4', '--fps', '25', '--preset=final']
    argv = _list(argv, 'argv', 256)
    if not all(isinstance(t, str) and len(t) <= MAX_STR for t in argv):
        raise ValueError('argv must be a list of strings')
    commands, issues = validate_cli_spec(spec)
    result = {'spec_valid': not issues, 'spec_issues': issues,
              'commands': sorted(commands), 'examples': {}, 'parsed': None}
    if not issues:
        for cname, args in commands.items():
            ex = _example_argv(cname, args)
            result['examples'][cname] = {'argv': ex, 'parse': parse_argv(commands, ex)}
        result['parsed'] = parse_argv(commands, argv)
    result['all_examples_parse'] = bool(result['examples']) and all(
        e['parse']['ok'] for e in result['examples'].values())
    return _pack('cli_spec_check', result,
                 ['argv[0] is the command; positional args are names without a leading "--"',
                  'long flags only ("--name value" or "--name=value"); "--" ends flag parsing',
                  'tokens like -5 or -1.5 are treated as values, not flags',
                  'parsing has no side effects: no sys.exit, no printing, errors are returned'],
                 ['<= 64 commands, <= 64 args per command, argv <= 256 tokens',
                  'no short (-x) aliases, no repeated/append args, no subcommand nesting',
                  'spec problems are listed in spec_issues and parsing is skipped while any remain'])


# =========================================================================== 02.03 messages

MSG_TYPES = ('any', 'bool', 'dict', 'float', 'int', 'list', 'str')


def _msg_type_ok(value, typ):
    if typ == 'any':
        return True
    if typ == 'bool':
        return isinstance(value, bool)
    if typ == 'int':
        return isinstance(value, int) and not isinstance(value, bool)
    if typ == 'float':
        return (isinstance(value, (int, float)) and not isinstance(value, bool)
                and math.isfinite(value))
    if typ == 'str':
        return isinstance(value, str)
    if typ == 'list':
        return isinstance(value, list)
    return isinstance(value, dict)


def _norm_schemas(schemas):
    schemas = _list(schemas, 'schemas', 128, allow_empty=False)
    out = {}
    for i, s in enumerate(schemas):
        s = _dict(s, f'schemas[{i}]', 4)
        if set(s) - {'name', 'version', 'fields'}:
            raise ValueError(f'schemas[{i}] keys must be name, version, fields')
        name = _str(s.get('name'), f'schemas[{i}].name', max_len=128)
        ver = _int(s.get('version'), 1, 10_000, f'schemas[{i}].version')
        fields = _dict(s.get('fields'), f'schemas[{i}].fields', 256)
        nf = {}
        for fname, fs in fields.items():
            if isinstance(fs, str):
                fs = {'type': fs, 'required': True}
            fs = _dict(fs, f'schemas[{i}].fields.{fname}', 2)
            if set(fs) - {'type', 'required'}:
                raise ValueError(f'field {fname}: keys must be type, required')
            typ = fs.get('type')
            if typ not in MSG_TYPES:
                raise ValueError(f'field {fname}: type must be one of {list(MSG_TYPES)}')
            nf[fname] = {'type': typ, 'required': _bool(fs.get('required', True),
                                                          f'field {fname}.required')}
        if (name, ver) in out:
            raise ValueError(f'duplicate schema {name} v{ver}')
        out[(name, ver)] = nf
    return out


def _norm_migrations(migrations):
    migrations = _list(migrations, 'migrations', 128)
    out = []
    for i, m in enumerate(migrations):
        m = _dict(m, f'migrations[{i}]', 6)
        if set(m) - {'name', 'from', 'to', 'rename', 'add', 'drop'}:
            raise ValueError(f'migrations[{i}] keys must be name, from, to, rename, add, drop')
        name = _str(m.get('name'), f'migrations[{i}].name', max_len=128)
        frm = _int(m.get('from'), 1, 10_000, f'migrations[{i}].from')
        to = _int(m.get('to'), 1, 10_000, f'migrations[{i}].to')
        if to <= frm:
            raise ValueError(f'migrations[{i}]: to must be greater than from')
        rename = _dict(m.get('rename', {}), f'migrations[{i}].rename', 256)
        if not all(isinstance(v, str) for v in rename.values()):
            raise ValueError(f'migrations[{i}].rename values must be field names')
        add = _dict(m.get('add', {}), f'migrations[{i}].add', 256)
        _canon(add, f'migrations[{i}].add')
        drop = _list(m.get('drop', []), f'migrations[{i}].drop', 256)
        if not all(isinstance(d, str) for d in drop):
            raise ValueError(f'migrations[{i}].drop must list field names')
        out.append({'name': name, 'from': frm, 'to': to, 'rename': dict(rename),
                    'add': dict(add), 'drop': list(drop)})
    return out


def _validate_message(msg, schemas):
    errors = []
    if not isinstance(msg, dict):
        return ['message must be a dict {name, version, data}']
    extra_keys = set(msg) - {'name', 'version', 'data'}
    if extra_keys:
        errors.append(f'unknown envelope key(s): {sorted(map(str, extra_keys))}')
    name, ver, data = msg.get('name'), msg.get('version'), msg.get('data')
    if not isinstance(name, str) or isinstance(ver, bool) or not isinstance(ver, int):
        return errors + ['message needs a string name and an integer version']
    if (name, ver) not in schemas:
        known = sorted(v for (n, v) in schemas if n == name)
        return errors + [f'unknown version {ver} for {name!r} (known: {known})']
    if not isinstance(data, dict):
        return errors + ['message data must be a dict']
    fields = schemas[(name, ver)]
    for key in sorted(map(str, data)):
        if key not in fields:
            errors.append(f'unknown field {key!r}')
    for fname, fs in fields.items():
        if fname not in data:
            if fs['required']:
                errors.append(f'missing required field {fname!r}')
        elif not _msg_type_ok(data[fname], fs['type']):
            errors.append(f'field {fname!r} must be {fs["type"]}')
    return errors


def _upgrade_message(msg, migrations, target):
    name, cur = msg['name'], msg['version']
    data = _copy(msg['data'], 'message.data')
    path = []
    for _ in range(len(migrations) + 1):
        if cur == target:
            return {'name': name, 'version': cur, 'data': data}, path, None
        step = next((m for m in migrations if m['name'] == name and m['from'] == cur), None)
        if step is None:
            return None, path, f'no declared migration from v{cur} for {name!r}'
        for old, new in step['rename'].items():
            if old in data:
                if new in data:
                    return None, path, f'rename {old}->{new} would overwrite {new}'
                data[new] = data.pop(old)
        for f in step['drop']:
            data.pop(f, None)
        for f, default in step['add'].items():
            data.setdefault(f, _copy(default))
        path.append([cur, step['to']])
        cur = step['to']
        if cur > target:
            return None, path, f'migration overshoots target v{target}'
    return None, path, 'migration chain did not converge'


def message_schema(*, schemas=None, message=None, migrations=None, target_version=None, **extra):
    """Validate a versioned message; optionally upgrade it along declared migrations."""
    _no_extra(extra)
    if schemas is None:
        schemas = [
            {'name': 'job.request', 'version': 1,
             'fields': {'path': 'str', 'fps': {'type': 'int', 'required': False}}},
            {'name': 'job.request', 'version': 2,
             'fields': {'input_path': 'str', 'fps': {'type': 'int', 'required': False},
                        'priority': 'int'}},
        ]
        if migrations is None:
            migrations = [{'name': 'job.request', 'from': 1, 'to': 2,
                           'rename': {'path': 'input_path'}, 'add': {'priority': 5}}]
        if message is None:
            message = {'name': 'job.request', 'version': 1, 'data': {'path': 'a.mp4', 'fps': 30}}
        if target_version is None:
            target_version = 2
    if message is None:
        raise ValueError('message is required when schemas are given')
    nschemas = _norm_schemas(schemas)
    nmig = _norm_migrations(migrations or [])
    _canon(message, 'message')
    if target_version is not None:
        target_version = _int(target_version, 1, 10_000, 'target_version')
    errors = _validate_message(message, nschemas)
    result = {'valid': not errors, 'errors': errors, 'upgraded': None, 'upgrade_path': [],
              'upgrade_errors': []}
    if not errors and target_version is not None and target_version != message['version']:
        if target_version < message['version']:
            result['upgrade_errors'] = ['downgrade is not supported']
        elif (message['name'], target_version) not in nschemas:
            result['upgrade_errors'] = [f'no schema for target v{target_version}']
        else:
            up, path, err = _upgrade_message(message, nmig, target_version)
            result['upgrade_path'] = path
            if err:
                result['upgrade_errors'] = [err]
            else:
                uerr = _validate_message(up, nschemas)
                result['upgrade_errors'] = uerr
                result['upgraded'] = None if uerr else up
    return _pack('message_schema', result,
                 ['message envelope is {name, version, data}; versions are positive integers',
                  'unknown fields and unknown versions are errors (closed schemas)',
                  'a field given as a plain type string is required; "float" accepts ints',
                  'migrations are upward only: rename, then drop, then add defaults'],
                 ['<= 128 schemas, <= 256 fields each, <= 128 migrations',
                  'flat field mapping only (no nested-path renames, no value transforms)',
                  'no downgrade path; upgraded result is re-validated against the target schema'])


# =========================================================================== 02.04 packaging

PRIVATE_NAME_PATTERNS = ('*.sqlite*', '*.db', 'memory*', '.env*')
PRIVATE_DIRS = ('owner-memory', 'credentials', 'private')


def _norm_rel(p):
    return re.sub(r'/+', '/', p.replace('\\', '/'))


def _ignored(path_l, patterns):
    parts = path_l.strip('/').split('/')
    for pat in patterns:
        pl = _norm_rel(pat).lower()
        if pl.endswith('/'):
            dpat = pl.rstrip('/')
            for k in range(1, len(parts)):
                prefix = '/'.join(parts[:k])
                if fnmatch.fnmatchcase(parts[k - 1], dpat) or fnmatch.fnmatchcase(prefix, dpat):
                    return pat
        elif fnmatch.fnmatchcase(path_l, pl) or fnmatch.fnmatchcase(parts[-1], pl):
            return pat
    return None


def distribution_guard(*, paths=None, ignore=None, max_bytes=50_000_000, **extra):
    """Flag private stores and oversize files in a packaging listing."""
    _no_extra(extra)
    if paths is None:
        paths = ['rose.py', 'README.md', {'path': 'data/memory.sqlite3', 'size': 4096},
                 '.env.local', 'owner-memory/notes.json', 'cache/big.bin',
                 {'path': 'assets/intro.mp4', 'size': 80_000_000}]
        if ignore is None:
            ignore = ['cache/']
    paths = _list(paths, 'paths', 20_000)
    ignore = _list(ignore or [], 'ignore', 256)
    if not all(isinstance(p, str) and 0 < len(p) <= 512 for p in ignore):
        raise ValueError('ignore must be a list of non-empty pattern strings')
    max_bytes = _int(max_bytes, 1, 10**13, 'max_bytes')
    included, ignored, flagged = [], [], []
    for i, entry in enumerate(paths):
        size = None
        if isinstance(entry, dict):
            entry = _dict(entry, f'paths[{i}]', 2)
            if set(entry) - {'path', 'size'}:
                raise ValueError(f'paths[{i}] keys must be path, size')
            p = _str(entry.get('path'), f'paths[{i}].path', max_len=1024)
            if 'size' in entry:
                size = _int(entry['size'], 0, 10**15, f'paths[{i}].size')
        else:
            p = _str(entry, f'paths[{i}]', max_len=1024)
        norm = _norm_rel(p)
        low = norm.lower()
        hit = _ignored(low, ignore)
        if hit is not None:
            ignored.append({'path': p, 'pattern': hit})
            continue
        parts = [x for x in low.split('/') if x]
        reasons = []
        name = parts[-1] if parts else ''
        for pat in PRIVATE_NAME_PATTERNS:
            if any(fnmatch.fnmatchcase(x, pat) for x in parts):
                reasons.append(f'private store pattern {pat}')
        for d in PRIVATE_DIRS:
            if d in parts[:-1] or (d == name and norm.endswith('/')):
                reasons.append(f'private directory {d}/')
        if size is not None and size > max_bytes:
            reasons.append(f'size {size} > cap {max_bytes}')
        if norm.startswith('/') or re.match(r'^[a-z]:', low) or '..' in parts:
            reasons.append('path escapes the package root (absolute or ..)')
        included.append(p)
        if reasons:
            flagged.append({'path': p, 'reasons': reasons})
    result = {'safe_to_package': not flagged, 'flagged': flagged, 'included_count': len(included),
              'ignored': ignored, 'unknown_size_count': sum(
                  1 for e in paths if not (isinstance(e, dict) and 'size' in e))}
    return _pack('distribution_guard', result,
                 ['paths are package-relative; backslashes are treated as separators; matching is case-insensitive',
                  'ignored paths (fnmatch on full path or basename; "dir/" matches a directory) are excluded and never flagged',
                  'private patterns apply to every path component: *.sqlite*, *.db, memory*, .env*, '
                  'and directories owner-memory/, credentials/, private/',
                  'conservative: memory* also blocks innocent names such as memory_notes.py'],
                 ['<= 20000 paths, <= 256 ignore patterns',
                  'size is only checked when the caller supplies it; file contents are never inspected',
                  'does not read the disk: the listing must be complete and truthful'])


# =========================================================================== 02.05 deps

_DEP_SPEC = re.compile(r'^\s*([A-Za-z0-9][A-Za-z0-9_.+-]{0,63}?)\s*(?:(>=|==)\s*(\d+(?:\.\d+){0,3}))?\s*$')
_VERSION_IN = re.compile(r'(\d+(?:\.\d+){0,3})')


def _vtuple(text):
    m = _VERSION_IN.search(text)
    if not m:
        return None
    t = [int(x) for x in m.group(1).split('.')]
    return tuple(t + [0] * (4 - len(t)))


def dependency_status(*, tasks=None, available=None, **extra):
    """Decide per task ready|blocked from declared deps and a caller-supplied availability map."""
    _no_extra(extra)
    if tasks is None:
        tasks = {'render_video': ['ffmpeg>=6.0', 'ffprobe'], 'transcribe': ['python>=3.10', 'whisper'],
                 'svg_frames': ['cairosvg>=2.5']}
        if available is None:
            available = {'ffmpeg': '6.1.1-full_build', 'ffprobe': '6.1.1', 'python': '3.12.4',
                         'whisper': None, 'cairosvg': '2.4.2'}
    tasks = _dict(tasks, 'tasks', 512)
    available = _dict(available or {}, 'available', 2048)
    for k, v in available.items():
        if v is not None and not (isinstance(v, str) and len(v) <= 256):
            raise ValueError(f'available[{k}] must be a version string or null')
    out = {}
    for task, deps in tasks.items():
        deps = _list(deps, f'tasks[{task}]', 128)
        missing, too_old, reasons = [], [], []
        for d in deps:
            if not isinstance(d, str):
                raise ValueError(f'tasks[{task}] entries must be strings like "ffmpeg>=6.0"')
            m = _DEP_SPEC.match(d)
            if not m:
                raise ValueError(f'bad dependency spec {d!r}')
            name, opr, need = m.groups()
            have = available.get(name)
            if have is None:
                missing.append(name)
                reasons.append(f'{name} is not available')
                continue
            if need:
                hv, nv = _vtuple(have), _vtuple(need)
                if hv is None:
                    too_old.append({'dep': name, 'have': have, 'need': f'{opr}{need}'})
                    reasons.append(f'{name} version unknown ({have!r}); need {opr}{need}')
                elif (opr == '>=' and hv < nv) or (opr == '==' and hv != nv):
                    too_old.append({'dep': name, 'have': have, 'need': f'{opr}{need}'})
                    reasons.append(f'{name} {have} does not satisfy {opr}{need}')
        out[task] = {'status': 'blocked' if reasons else 'ready', 'missing': missing,
                     'version_mismatch': too_old, 'reasons': reasons}
    result = {'tasks': out, 'ready': sorted(t for t, r in out.items() if r['status'] == 'ready'),
              'blocked': sorted(t for t, r in out.items() if r['status'] == 'blocked')}
    return _pack('dependency_status', result,
                 ['availability is supplied by the caller (e.g. from shutil.which and --version elsewhere)',
                  'a dep absent from the map or mapped to null is missing',
                  'versions compare numerically on the first dotted number found (6.1.1-full_build -> 6.1.1)',
                  'a minimum version with an unparseable installed version blocks the task'],
                 ['<= 512 tasks, <= 128 deps per task; operators >= and == only',
                  'up to 4 numeric components; pre-release tags and git-date builds (N-112345-g...) are not understood',
                  'no transitive dependency resolution'])


# =========================================================================== 02.06 config

REDACTED = '***REDACTED***'
_SECRET_TOKENS = {'password', 'passwd', 'pwd', 'passphrase', 'token', 'secret', 'key', 'apikey',
                  'credential', 'credentials', 'auth', 'cookie', 'session'}
_TOKEN_PATTERNS = [re.compile(p) for p in (
    r'^sk-[A-Za-z0-9_-]{16,}', r'^(?:sk|pk|rk)_(?:live|test)_[A-Za-z0-9]{10,}',
    r'^gh[pousr]_[A-Za-z0-9]{20,}', r'^github_pat_[A-Za-z0-9_]{20,}', r'^xox[abprs]-[A-Za-z0-9-]{10,}',
    r'^AKIA[0-9A-Z]{16}$', r'^AIza[0-9A-Za-z_-]{30,}', r'^eyJ[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\.',
    r'^(?i:bearer|basic)\s+\S{10,}', r'-----BEGIN [A-Z ]*PRIVATE KEY-----',
    r'^[a-z][a-z0-9+.-]*://[^/\s:@]+:[^/\s@]+@')]


def _key_is_secret(key):
    k = key.lower()
    if 'api_key' in k or 'apikey' in k or 'api-key' in k or 'private_key' in k:
        return True
    words = re.split(r'[_\-.\s]+', re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', key).lower())
    return any(w in _SECRET_TOKENS for w in words)


def _entropy(s):
    counts = {}
    for c in s:
        counts[c] = counts.get(c, 0) + 1
    n = len(s)
    return -sum(c / n * math.log2(c / n) for c in counts.values())


def looks_like_token(value):
    """Heuristic: known credential prefixes, or long high-entropy letter+digit strings."""
    if not isinstance(value, str) or len(value) < 12:
        return False
    if any(p.search(value) for p in _TOKEN_PATTERNS):
        return True
    return (len(value) >= 24 and re.fullmatch(r'[A-Za-z0-9_\-+/=.]+', value) is not None
            and not value.startswith(('/', '.')) and re.search(r'\d', value) is not None
            and re.search(r'[A-Za-z]', value) is not None and _entropy(value) >= 3.5)


def _cfg_type(value):
    if isinstance(value, bool):
        return 'bool'
    if isinstance(value, int):
        return 'int'
    if isinstance(value, float):
        return 'float'
    if isinstance(value, str):
        return 'str'
    if isinstance(value, list):
        return 'list'
    if isinstance(value, dict):
        return 'dict'
    if value is None:
        return 'null'
    raise ValueError('config values must be JSON types')


def _coerce_env(raw, want, path):
    if not isinstance(raw, str):
        if want == 'float' and _cfg_type(raw) == 'int':
            return float(raw)
        if _cfg_type(raw) != want and want != 'null':
            raise ValueError(f'override {path}: expected {want}')
        return raw
    if want in ('str', 'null'):
        return raw
    if want == 'int':
        if re.fullmatch(r'[+-]?\d{1,18}', raw.strip()):
            return int(raw)
    elif want == 'float':
        try:
            v = float(raw)
        except ValueError:
            v = None
        if v is not None and math.isfinite(v):
            return v
    elif want == 'bool':
        if raw.strip().lower() in _TRUE:
            return True
        if raw.strip().lower() in _FALSE:
            return False
    elif want in ('list', 'dict'):
        try:
            v = json.loads(raw)
        except ValueError:
            v = None
        if _cfg_type(v) == want if v is not None else False:
            return v
    raise ValueError(f'override {path}: cannot convert to {want}')  # value deliberately omitted


def _merge_layer(base, layer, sources, layer_name, prefix=''):
    for key, value in layer.items():
        if not isinstance(key, str):
            raise ValueError(f'{layer_name}: keys must be strings')
        path = prefix + key
        if key not in base:
            raise ValueError(f'{layer_name}: unknown key {path!r}')
        want = _cfg_type(base[key])
        if want == 'dict':
            if not isinstance(value, dict):
                raise ValueError(f'{layer_name}: {path} must be a dict')
            _merge_layer(base[key], value, sources, layer_name, path + '.')
            continue
        got = _cfg_type(value)
        if want == 'float' and got == 'int':
            value = float(value)
        elif want != 'null' and got != want:
            raise ValueError(f'{layer_name}: {path} must be {want}, got {got}')
        base[key] = _copy(value, path)
        sources[path] = layer_name


def merge_config(defaults, file_config=None, env=None):
    """Return (merged, sources). In-process use only: merged may contain secrets."""
    defaults = _copy(_dict(defaults, 'defaults'), 'defaults')
    file_config = _dict(file_config or {}, 'file_config')
    env = _dict(env or {}, 'env', 512)
    sources = {}

    def walk(d, prefix=''):
        for k, v in d.items():
            if isinstance(v, dict):
                walk(v, prefix + k + '.')
            else:
                sources[prefix + k] = 'defaults'
    walk(defaults)
    _merge_layer(defaults, file_config, sources, 'file_config')
    for dotted in sorted(env):
        parts = [p for p in re.split(r'\.|__', dotted.lower()) if p]
        node, real = defaults, []
        for p in parts[:-1]:
            nxt = next((k for k in node if k.lower() == p and isinstance(node[k], dict)), None)
            if nxt is None:
                raise ValueError(f'env: unknown key {dotted!r}')
            node = node[nxt]
            real.append(nxt)
        leaf = next((k for k in node if parts and k.lower() == parts[-1]), None)
        if leaf is None or isinstance(node[leaf], dict):
            raise ValueError(f'env: unknown key {dotted!r}')
        node[leaf] = _coerce_env(env[dotted], _cfg_type(node[leaf]), dotted)
        sources['.'.join(real + [leaf])] = 'env'
    return defaults, sources


def redact_config(cfg, prefix=''):
    """Return (printable_copy, redacted_paths)."""
    paths = []

    def walk(v, path, secret_key):
        if isinstance(v, dict):
            return {k: walk(x, f'{path}.{k}' if path else k, secret_key or _key_is_secret(k))
                    for k, x in v.items()}
        if isinstance(v, list):
            return [walk(x, f'{path}[{i}]', secret_key) for i, x in enumerate(v)]
        if (secret_key and v not in (None, '', False)) or looks_like_token(v):
            paths.append(path)
            return REDACTED
        if isinstance(v, str):
            # also scrub token-looking words embedded in longer strings
            def scrub(m):
                return REDACTED if looks_like_token(m.group(0)) else m.group(0)
            nv = re.sub(r'\S{12,}', scrub, v)
            if nv != v:
                paths.append(path)
            return nv
        return v
    return walk(cfg, prefix, False), paths


def config_redact(*, defaults=None, file_config=None, env=None, **extra):
    """Merge defaults < file_config < env, validate types, return a redacted printable view."""
    _no_extra(extra)
    if defaults is None:
        defaults = {'render': {'fps': 30, 'scale': 1.0, 'preset': 'draft'},
                    'upload': {'api_key': '', 'endpoint': 'https://example.invalid/api'},
                    'debug': False}
        if file_config is None:
            file_config = {'render': {'fps': 25}, 'upload': {'api_key': 'sk-DEMO0000placeholder0000'}}
        if env is None:
            env = {'render.scale': '0.5', 'debug': 'true'}
    merged, sources = merge_config(defaults, file_config, env)
    printable, paths = redact_config(merged)
    text = json.dumps(printable, sort_keys=True, ensure_ascii=False, indent=2)
    result = {'printable': printable, 'printable_text': text, 'redacted_paths': sorted(paths),
              'sources': dict(sorted(sources.items()))}
    return _pack('config_redact', result,
                 ['precedence: defaults < file_config < env; types come from the defaults '
                  '(int is accepted for float; a null default accepts anything)',
                  'unknown keys in file_config or env are errors; env keys are dotted or "__" separated, case-insensitive',
                  'env string values are coerced (int, float, true/false/1/0/yes/no, JSON for list/dict)',
                  'keys whose words include password/token/secret/key/api_key/credential/auth/cookie/session are redacted, '
                  'and token-looking values are redacted wherever they appear',
                  'the merged unredacted config is not returned; use merge_config() in-process'],
                 ['value heuristics: known prefixes (sk-, ghp_, xoxb-, AKIA, JWT, bearer, URL credentials) '
                  'or >= 24 chars of letters+digits with entropy >= 3.5; short or dictionary-like secrets '
                  'under an innocent key name can slip through',
                  'error messages name the key path but never echo values',
                  '<= 2000 entries per mapping, <= 256 KB of JSON'])


# =========================================================================== 02.07 cache

_CAP_NAME = re.compile(r'^[A-Za-z0-9_.:-]{1,128}$')
_HEX64 = re.compile(r'^[0-9a-f]{64}$')


def cache_components(capability, params, input_hashes, code_version, permission_scope):
    """Validate and canonicalise the five cache-key components."""
    if not isinstance(capability, str) or not _CAP_NAME.match(capability):
        raise ValueError('capability must match [A-Za-z0-9_.:-]{1,128}')
    params = _copy(_dict(params, 'params', 512), 'params')
    input_hashes = _dict(input_hashes, 'input_hashes', 256)
    for k, v in input_hashes.items():
        if not isinstance(v, str) or not _HEX64.match(v):
            raise ValueError(f'input_hashes[{k}] must be a lowercase sha256 hex digest')
    code_version = _str(code_version, 'code_version', max_len=64)
    scope = _list(permission_scope, 'permission_scope', 64)
    if not all(isinstance(s, str) and 0 < len(s) <= 64 for s in scope):
        raise ValueError('permission_scope must be a list of non-empty strings')
    return {'capability': capability, 'params': params, 'input_hashes': dict(sorted(input_hashes.items())),
            'code_version': code_version, 'permission_scope': sorted(set(scope))}


_COMPONENT_NAMES = {'capability', 'params', 'input_hashes', 'code_version', 'permission_scope'}


def make_cache_key(**components):
    if set(components) != _COMPONENT_NAMES:
        raise ValueError(f'cache key needs exactly {sorted(_COMPONENT_NAMES)}')
    comp = cache_components(**components)
    canon = _canon(comp, 'cache components')
    return hashlib.sha256(canon.encode('ascii')).hexdigest(), canon, comp


class PermissionAwareCache:
    """In-memory cache keyed by every component, including permission scope.

    put() supersedes older entries of the same capability+params slot whose other
    components (inputs, code version, scope) differ, so a changed component never
    returns stale data. Values are deep-copied as JSON.
    """

    def __init__(self, max_entries=256):
        self.max_entries = _int(max_entries, 1, 100_000, 'max_entries')
        self._entries = {}

    @staticmethod
    def _slot(comp):
        return _sha({'capability': comp['capability'], 'params': comp['params']})

    def put(self, value, **components):
        key, _, comp = make_cache_key(**components)
        slot = self._slot(comp)
        for k in [k for k, e in self._entries.items() if e['slot'] == slot and k != key]:
            del self._entries[k]
        self._entries.pop(key, None)
        self._entries[key] = {'slot': slot, 'capability': comp['capability'],
                              'value': _copy(value, 'cache value')}
        while len(self._entries) > self.max_entries:
            del self._entries[next(iter(self._entries))]
        return key

    def get(self, **components):
        key, _, _ = make_cache_key(**components)
        entry = self._entries.get(key)
        if entry is None:
            return {'hit': False, 'key': key, 'value': None}
        return {'hit': True, 'key': key, 'value': _copy(entry['value'])}

    def invalidate(self, *, key=None, capability=None):
        if (key is None) == (capability is None):
            raise ValueError('invalidate needs exactly one of key or capability')
        doomed = [k for k, e in self._entries.items()
                  if (key is not None and k == key) or e['capability'] == capability]
        for k in doomed:
            del self._entries[k]
        return len(doomed)

    def __len__(self):
        return len(self._entries)


def cache_key(*, capability='render.preview', params=None, input_hashes=None,
              code_version='22.0.0', permission_scope=None, **extra):
    """Compute the canonical cache key and show which component changes cause a miss."""
    _no_extra(extra)
    params = {'width': 1280, 'fps': 24} if params is None else params
    if input_hashes is None:
        input_hashes = {'clip.mp4': hashlib.sha256(b'demo clip').hexdigest()}
    permission_scope = ['read'] if permission_scope is None else permission_scope
    comp = dict(capability=capability, params=params, input_hashes=input_hashes,
                code_version=code_version, permission_scope=permission_scope)
    key, canon, norm = make_cache_key(**comp)
    cache = PermissionAwareCache()
    cache.put({'demo': True}, **comp)
    variants = {
        'same': {},
        'params_changed': {'params': dict(norm['params'], __probe__=1)},
        'input_changed': {'input_hashes': dict(norm['input_hashes'],
                                               __probe__=hashlib.sha256(b'x').hexdigest())},
        'code_version_changed': {'code_version': code_version + '+probe'},
        'permission_scope_changed': {'permission_scope': norm['permission_scope'] + ['__probe__']},
    }
    checks = {name: cache.get(**dict(comp, **change))['hit'] for name, change in variants.items()}
    result = {'key': key, 'canonical': canon, 'components': norm, 'hit_checks': checks}
    return _pack('cache_key', result,
                 ['key = sha256 of canonical JSON (sorted keys, ASCII, no whitespace) of '
                  'capability, params, input file hashes, code version and permission scope',
                  'permission_scope is a set: order and duplicates do not change the key',
                  'input files are identified by caller-supplied sha256 digests (no file reading)',
                  'PermissionAwareCache supersedes same-slot entries when any other component changes'],
                 ['params <= 512 keys and 256 KB canonical JSON; <= 256 input hashes; scope <= 64 entries',
                  'cache is in-memory and per-process, FIFO-evicted at max_entries; not thread-safe',
                  'floats in params hash by their JSON repr, so 1 and 1.0 give different keys'])


# =========================================================================== 02.08 checkpoints

BUILTIN_STAGES = {
    'strip': lambda d: d.strip(),
    'lower': lambda d: d.lower(),
    'upper': lambda d: d.upper(),
    'split_words': lambda d: d.split(),
    'dedupe': lambda d: list(dict.fromkeys(d)),
    'sort': lambda d: sorted(d),
    'reverse': lambda d: d[::-1],
    'count': lambda d: len(d),
    'join': lambda d: ' '.join(d),
}
MAX_STAGES = 32


def _check_records(checkpoint):
    recs = _list(checkpoint or [], 'checkpoint', MAX_STAGES)
    out = []
    for i, r in enumerate(recs):
        r = _dict(r, f'checkpoint[{i}]', 8)
        need = {'index', 'stage', 'inputs_hash', 'output_hash', 'done', 'output'}
        if set(r) != need:
            raise ValueError(f'checkpoint[{i}] keys must be {sorted(need)}')
        if r['index'] != i or not isinstance(r['done'], bool):
            raise ValueError(f'checkpoint[{i}] has a bad index or done flag')
        out.append(_copy(r, f'checkpoint[{i}]'))
    return out


def run_pipeline(stages, data, checkpoint=None, stop_after=None):
    """Run atomic stages [(name, fn), ...] with checkpointing.

    A stage is skipped when its checkpoint record is done, its inputs hash matches
    and its stored output still hashes to output_hash. Otherwise it reruns, and a
    downstream record is reused only if its inputs hash still matches the new
    upstream output (so changed inputs invalidate downstream). Records after an
    interruption or failure are dropped. stop_after=k simulates an
    interruption before stage index k would run (stages 0..k-1 may complete).
    A stage raising an exception stops the run with status 'failed'.
    """
    stages = _list(stages, 'stages', MAX_STAGES, allow_empty=False)
    for i, s in enumerate(stages):
        if (not isinstance(s, (list, tuple)) or len(s) != 2 or not isinstance(s[0], str)
                or not callable(s[1])):
            raise ValueError(f'stages[{i}] must be (name, callable)')
    if stop_after is not None:
        stop_after = _int(stop_after, 0, len(stages), 'stop_after')
    old = _check_records(checkpoint)
    records = []
    cur = _copy(data, 'data')
    ran, skipped, invalidated = [], [], []
    status, error = 'complete', None
    for i, (name, fn) in enumerate(stages):
        ih = _sha({'stage': name, 'index': i, 'input': cur})
        rec = old[i] if i < len(old) else None
        if (rec and rec['done'] and rec['stage'] == name and rec['inputs_hash'] == ih
                and _sha(rec['output']) == rec['output_hash']):
            records.append(rec)
            cur = rec['output']
            skipped.append(name)
            continue
        if rec and rec['done']:
            invalidated.append(rec['stage'])
        if stop_after is not None and i >= stop_after:
            status = 'interrupted'
            break
        try:
            out = _copy(fn(_copy(cur)), f'output of stage {name}')
        except Exception as exc:  # stage code is caller-supplied; any failure is a stage failure
            records.append({'index': i, 'stage': name, 'inputs_hash': ih, 'output_hash': None,
                            'done': False, 'output': None})
            status, error = 'failed', f'{name}: {type(exc).__name__}: {exc}'[:500]
            break
        records.append({'index': i, 'stage': name, 'inputs_hash': ih, 'output_hash': _sha(out),
                        'done': True, 'output': out})
        ran.append(name)
        cur = out
    return {'status': status, 'output': cur if status == 'complete' else None, 'ran': ran,
            'skipped': skipped, 'invalidated': invalidated, 'error': error, 'checkpoint': records}


def checkpoint_resume(*, stages=None, data='  The cat the DOG cat  ', interrupt_at=2,
                      changed_data=None, **extra):
    """Interrupt a built-in pipeline at stage k, resume it, and compare with an uninterrupted run."""
    _no_extra(extra)
    stages = ['strip', 'lower', 'split_words', 'dedupe', 'sort'] if stages is None else stages
    stages = _list(stages, 'stages', MAX_STAGES, allow_empty=False)
    for s in stages:
        if s not in BUILTIN_STAGES:
            raise ValueError(f'stages must be names from {sorted(BUILTIN_STAGES)}')
    _canon(data, 'data', 64_000)
    interrupt_at = _int(interrupt_at, 0, len(stages), 'interrupt_at')
    if changed_data is not None:
        _canon(changed_data, 'changed_data', 64_000)
    counts = {}

    def counted(name):
        def fn(d):
            counts[name] = counts.get(name, 0) + 1
            return BUILTIN_STAGES[name.split(':', 1)[1]](d)
        return fn
    pipeline = [(f'{i}:{n}', counted(f'{i}:{n}')) for i, n in enumerate(stages)]
    reference = run_pipeline([(n, BUILTIN_STAGES[n.split(':', 1)[1]]) for n, _ in pipeline], data)
    first = run_pipeline(pipeline, data, stop_after=interrupt_at)
    second = run_pipeline(pipeline, data, checkpoint=first['checkpoint'])
    result = {
        'stages': [n for n, _ in pipeline], 'interrupt_at': interrupt_at,
        'first_run': {k: first[k] for k in ('status', 'ran', 'error')},
        'resumed_run': {k: second[k] for k in ('status', 'ran', 'skipped', 'invalidated', 'error')},
        'output': second['output'], 'uninterrupted_output': reference['output'],
        'matches_uninterrupted': second['status'] == 'complete' and second['output'] == reference['output'],
        'run_counts': dict(sorted(counts.items())),
        'each_stage_ran_once': all(counts.get(n, 0) == 1 for n, _ in pipeline)
        if reference['status'] == 'complete' else False,
        'checkpoint': second['checkpoint'], 'changed_input': None,
    }
    if changed_data is not None:
        third = run_pipeline(pipeline, changed_data, checkpoint=second['checkpoint'])
        result['changed_input'] = {k: third[k] for k in ('status', 'ran', 'skipped', 'invalidated', 'output')}
    return _pack('checkpoint_resume', result,
                 ['stages are deterministic pure functions of JSON data; each stage is atomic '
                  '(its record is written only after it returns)',
                  'inputs hash = sha256(canonical JSON of stage name, index, input data); '
                  'stored outputs are re-hashed before reuse',
                  'a changed input invalidates that stage and everything downstream',
                  'run() uses built-in stages; run_pipeline() accepts caller functions'],
                 [f'<= {MAX_STAGES} stages; data and each output <= 64-256 KB canonical JSON',
                  'a stage whose code changes under the same name is not detected: version it in the name',
                  'checkpoints live in the returned dict; persisting them is the caller\'s job'])


# =========================================================================== 02.09 paths

WINDOWS_RESERVED = ({'CON', 'PRN', 'AUX', 'NUL'} | {f'COM{i}' for i in range(1, 10)}
                    | {f'LPT{i}' for i in range(1, 10)})
WINDOWS_MAX_PATH = 260


def path_problems(p):
    """List portability problems for one path string."""
    probs = []
    if any(0xD800 <= ord(c) <= 0xDFFF for c in p):
        probs.append('non_utf8_surrogate')
    if any(ord(c) < 32 for c in p):
        probs.append('control_character')
    win = PureWindowsPath(p)
    comps = list(win.parts[1:] if win.anchor else win.parts)
    for comp in comps:
        if comp in ('.', '..'):
            continue
        stem = comp.split('.')[0].rstrip(' ').upper()
        if stem in WINDOWS_RESERVED and 'reserved_windows_name' not in probs:
            probs.append('reserved_windows_name')
        if comp.endswith(('.', ' ')) and 'trailing_dot_or_space' not in probs:
            probs.append('trailing_dot_or_space')
        if re.search(r'[<>:"|?*]', comp) and 'invalid_windows_character' not in probs:
            probs.append('invalid_windows_character')
    if len(p) >= WINDOWS_MAX_PATH:
        probs.append('windows_max_path')
    if '\\' in p:
        probs.append('backslash_in_posix')
    if 'non_utf8_surrogate' not in probs and unicodedata.normalize('NFC', p) != p:
        probs.append('not_nfc')
    return probs


def _win_key(p):
    return ntpath.normcase(ntpath.normpath(p)).casefold()


def path_portability(*, paths=None, compare=None, **extra):
    """Normalise paths for Windows and POSIX, detect problems and case-only collisions."""
    _no_extra(extra)
    if paths is None:
        paths = ['docs/تقارير/ملخص.txt', 'src/main.py', 'CON.txt', 'notes/draft. ',
                 'a\\b.txt', 'Readme.md', 'README.md', 'x/' + 'n' * 270]
        if compare is None:
            compare = [['src/./main.py', 'src/main.py'], ['Readme.md', 'README.md']]
    paths = _list(paths, 'paths', 5_000)
    compare = _list(compare or [], 'compare', 500)
    items, groups = [], {}
    for i, p in enumerate(paths):
        p = _str(p, f'paths[{i}]', max_len=32_768)
        win, pos = PureWindowsPath(p), PurePosixPath(p)
        wparts, pparts = list(win.parts), list(pos.parts)
        round_trip = (PurePosixPath(PureWindowsPath(pos.as_posix()).as_posix()).parts == pos.parts)
        items.append({'path': p, 'windows': ntpath.normpath(p), 'posix': posixpath.normpath(p),
                      'parts_windows': wparts, 'parts_posix': pparts,
                      'same_parts': wparts == pparts, 'name_windows': win.name, 'name_posix': pos.name,
                      'round_trip': round_trip, 'problems': path_problems(p)})
        groups.setdefault(_win_key(p), []).append(p)
    collisions = [sorted(set(g)) for g in groups.values() if len(set(g)) > 1]
    collided = {p for g in collisions for p in g}
    for it in items:
        if it['path'] in collided:
            it['problems'].append('case_collision')
        it['portable'] = not it['problems'] and it['same_parts'] and it['round_trip']
    pairs = []
    for j, pair in enumerate(compare):
        if (not isinstance(pair, (list, tuple)) or len(pair) != 2
                or not all(isinstance(x, str) and 0 < len(x) <= 32_768 for x in pair)):
            raise ValueError(f'compare[{j}] must be a pair of path strings')
        a, b = pair
        pairs.append({'a': a, 'b': b, 'same_on_windows': _win_key(a) == _win_key(b),
                      'same_on_posix': posixpath.normpath(a) == posixpath.normpath(b)})
    result = {'paths': items, 'case_collisions': sorted(collisions), 'compare': pairs,
              'portable_count': sum(it['portable'] for it in items)}
    return _pack('path_portability', result,
                 ['Windows behaviour is simulated with ntpath/PureWindowsPath, POSIX with posixpath/PurePosixPath',
                  'Windows names are case-insensitive (approximated with str.casefold); POSIX names are case-sensitive',
                  'a backslash is a separator on Windows but a literal character on POSIX',
                  f'Windows MAX_PATH {WINDOWS_MAX_PATH} includes the terminating NUL, so >= 260 characters is flagged',
                  'not_nfc flags names that macOS-style NFD normalisation could change'],
                 ['<= 5000 paths, <= 500 comparison pairs; no filesystem access (existence and long-path '
                  'registry settings are unknown)',
                  'reserved names cover CON PRN AUX NUL COM1-9 LPT1-9 (not superscript COM¹ variants)',
                  'casefold differs from NTFS upcase tables for a few non-ASCII letters'])


# =========================================================================== 02.10 semver

_SEMVER = re.compile(
    r'^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)'
    r'(?:-((?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*)(?:\.(?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*))*))?'
    r'(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$')


def parse_semver(text):
    if not isinstance(text, str) or len(text) > 256:
        raise ValueError('version must be a string')
    m = _SEMVER.match(text)
    if not m:
        raise ValueError(f'not a SemVer 2.0.0 version: {text!r}')
    major, minor, patch, pre, build = m.groups()
    return {'major': int(major), 'minor': int(minor), 'patch': int(patch),
            'prerelease': pre.split('.') if pre else [], 'build': build.split('.') if build else []}


def semver_key(text):
    v = parse_semver(text)
    pre = tuple((0, int(x), '') if x.isdigit() else (1, 0, x) for x in v['prerelease'])
    return (v['major'], v['minor'], v['patch'], 0 if pre else 1, pre)


def semver_compare(a, b):
    ka, kb = semver_key(a), semver_key(b)
    return (ka > kb) - (ka < kb)


def is_compatible(current, target):
    a, b = parse_semver(current), parse_semver(target)
    if a['major'] != b['major']:
        return False
    return not (a['major'] == 0 and a['minor'] != b['minor'])


_MIG_OPS = {'rename': {'from', 'to'}, 'add': {'field', 'default'}, 'remove': {'field', 'default'},
            'map': {'field', 'mapping'}, 'copy': {'from', 'to'}}


class _Lossy(Exception):
    pass


def _check_op(i, j, op):
    op = _dict(op, f'migrations[{i}].ops[{j}]', 4)
    kind = op.get('op')
    if kind not in _MIG_OPS or set(op) != _MIG_OPS[kind] | {'op'}:
        raise ValueError(f'migrations[{i}].ops[{j}]: op must be one of {sorted(_MIG_OPS)} with keys '
                         f'{sorted(_MIG_OPS.get(kind, set()) | {"op"})}')
    for k in ('from', 'to', 'field'):
        if k in op:
            _str(op[k], f'migrations[{i}].ops[{j}].{k}', max_len=128)
    if kind == 'map':
        _dict(op['mapping'], f'migrations[{i}].ops[{j}].mapping', 512)
    _canon(op, f'migrations[{i}].ops[{j}]')
    return op


def _apply(ops, data, direction):
    d = _copy(data)
    seq = ops if direction == 'up' else list(reversed(ops))
    for op in seq:
        kind = op['op']
        if kind in ('rename', 'copy'):
            src, dst = (op['from'], op['to']) if direction == 'up' else (op['to'], op['from'])
            if kind == 'copy' and direction == 'down':
                d.pop(op['to'], None)
                continue
            if src in d:
                if dst in d:
                    raise _Lossy(f'{kind} {src}->{dst} would overwrite {dst}')
                d[dst] = d.pop(src) if kind == 'rename' else _copy(d[src])
        elif kind == 'add' or (kind == 'remove' and direction == 'down'):
            if (kind == 'add') == (direction == 'up'):
                if op['field'] in d:
                    raise _Lossy(f'add {op["field"]}: field already exists')
                d[op['field']] = _copy(op['default'])
            else:
                d.pop(op['field'], None)
        elif kind == 'remove':
            d.pop(op['field'], None)
        elif kind == 'map':
            mapping = op['mapping']
            if direction == 'down':
                inv = {}
                for k, v in mapping.items():
                    if not isinstance(v, str) or v in inv:
                        raise _Lossy(f'map {op["field"]}: mapping is not invertible')
                    inv[v] = k
                mapping = inv
            f = op['field']
            if f in d and isinstance(d[f], str) and d[f] in mapping:
                d[f] = _copy(mapping[d[f]])
    return d


def check_migration(up, down, samples):
    """Python-level check for callable migrations: down(up(x)) == x for every sample."""
    samples = _list(samples, 'samples', 1_000, allow_empty=False)
    for i, s in enumerate(samples):
        x = _copy(s, f'samples[{i}]')
        if _copy(down(up(_copy(x)))) != x:
            return False, f'sample {i}: down(up(x)) != x'
    return True, None


def semver_migrate(*, current='1.4.2', target='2.0.0', data=None, migrations=None,
                   versions=None, **extra):
    """Compare versions, decide compatibility, run migrations up then down and verify reversibility."""
    _no_extra(extra)
    if data is None:
        data = {'title': 'Intro', 'res': 'hd', 'fps': 30}
        if migrations is None:
            migrations = [{'from': '1.4.2', 'to': '2.0.0', 'ops': [
                {'op': 'rename', 'from': 'res', 'to': 'resolution'},
                {'op': 'map', 'field': 'resolution', 'mapping': {'hd': '1280x720', 'fhd': '1920x1080'}},
                {'op': 'add', 'field': 'schema', 'default': 2}]}]
        if versions is None:
            versions = ['1.0.0', '1.0.0-rc.1', '1.0.0-alpha', '1.0.0-beta.11', '1.0.0-alpha.1',
                        '1.0.0-beta.2', '1.0.0-alpha.beta', '1.0.0-beta', '0.9.9+build.7']
    parse_semver(current)
    parse_semver(target)
    data = _dict(data, 'data')
    _canon(data, 'data', 64_000)
    migrations = _list(migrations or [], 'migrations', 64)
    versions = _list(versions or [], 'versions', 1_000)
    for v in versions:
        parse_semver(v)
    steps = []
    for i, m in enumerate(migrations):
        m = _dict(m, f'migrations[{i}]', 3)
        if set(m) != {'from', 'to', 'ops'}:
            raise ValueError(f'migrations[{i}] keys must be from, to, ops')
        if semver_compare(m['from'], m['to']) >= 0:
            raise ValueError(f'migrations[{i}]: to must be newer than from')
        ops = [_check_op(i, j, op) for j, op in enumerate(_list(m['ops'], f'migrations[{i}].ops', 64))]
        steps.append({'from': m['from'], 'to': m['to'], 'ops': ops})
    cmp = semver_compare(current, target)
    result = {'compare': cmp, 'compatible': is_compatible(current, target),
              'breaking': not is_compatible(current, target),
              'sorted_versions': sorted(versions, key=semver_key),
              'path': [], 'accepted': None, 'upgraded': None, 'rolled_back': None,
              'round_trip_equal': None, 'rejected_reason': None}
    if cmp < 0:
        chain, cur = [], current
        for _ in range(len(steps) + 1):
            if semver_compare(cur, target) == 0:
                break
            step = next((s for s in steps if semver_compare(s['from'], cur) == 0), None)
            if step is None or semver_compare(step['to'], target) > 0:
                chain = None
                break
            chain.append(step)
            cur = step['to']
        if chain is None or semver_compare(cur, target) != 0:
            result['accepted'] = False
            result['rejected_reason'] = f'no declared migration path {current} -> {target}'
        else:
            result['path'] = [[s['from'], s['to']] for s in chain]
            try:
                up = data
                for s in chain:
                    up = _apply(s['ops'], up, 'up')
                down = up
                for s in reversed(chain):
                    down = _apply(s['ops'], down, 'down')
                equal = down == _copy(data)
                result['round_trip_equal'] = equal
                if equal:
                    result.update(accepted=True, upgraded=up, rolled_back=down)
                else:
                    result.update(accepted=False, rejected_reason='lossy: down(up(x)) != x')
            except _Lossy as exc:
                result.update(accepted=False, round_trip_equal=False, rejected_reason=f'lossy: {exc}')
    return _pack('semver_migrate', result,
                 ['SemVer 2.0.0 precedence: build metadata ignored, pre-release < release, numeric '
                  'identifiers < alphanumeric, numeric compared as integers',
                  'compatible = same major; for 0.y.z a minor change is also breaking',
                  'migrations are declarative ops (rename, add, remove, map, copy) on top-level keys; '
                  'down is derived as the exact inverse',
                  'a migration is accepted only if down(up(data)) == data on the supplied data; '
                  'the input dict is never modified'],
                 ['reversibility is verified on the given data only, not proven for all inputs '
                  '(check_migration() can test more samples, also for callables)',
                  'top-level fields only; map only rewrites string values; <= 64 migrations x 64 ops',
                  'downgrades (current > target) are compared but not migrated'])


# --------------------------------------------------------------------------- dispatcher

OPS = {
    'cli_spec_check': cli_spec_check, 'message_schema': message_schema,
    'distribution_guard': distribution_guard, 'dependency_status': dependency_status,
    'config_redact': config_redact, 'cache_key': cache_key,
    'checkpoint_resume': checkpoint_resume, 'path_portability': path_portability,
    'semver_migrate': semver_migrate,
}


def run(op, params=None):
    """Validate and dispatch: run('cache_key', {...}) -> {'op','result','assumptions','limits'}."""
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
