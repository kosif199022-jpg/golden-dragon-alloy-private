"""Red Rose V29 shell-proof I/O (W01).

Every extension command reads its parameters and writes its files through this
module so that nothing depends on how PowerShell 5.1, cmd or Git Bash quote
arguments or redirect output:

* parameters come as ``key=value`` tokens, ``--params-file FILE`` (JSON object),
  ``--stdin`` (JSON object) or ``--file-param key=FILE`` (the file's text);
* files are decoded from bytes (UTF-8, UTF-8 BOM, UTF-16/32 BOM, cp1256 fallback);
* JSON and binary results are written by Python itself (UTF-8, no BOM), never by
  shell redirection;
* errors are one JSON line on stdout with ``allowed`` values and a ``hint``.

Standard library only. Nothing here opens a database or touches the network.
"""
from __future__ import annotations

import base64
import binascii
import json
import os
import re
import sys
from pathlib import Path

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_USAGE = 2
EXIT_APPROVAL = 3
EXIT_UNAVAILABLE = 4
EXIT_EXAMPLE_ONLY = 5

OUTCOMES = ('ok', 'example_only', 'approval_required', 'unavailable_here', 'error')
OUTCOME_EXIT = {'ok': EXIT_OK, 'error': EXIT_ERROR, 'approval_required': EXIT_APPROVAL,
                'unavailable_here': EXIT_UNAVAILABLE, 'example_only': EXIT_EXAMPLE_ONLY}

PARAM_TYPES = ('string', 'number', 'integer', 'bool', 'path', 'list', 'object', 'auto')
MAX_PARAM_FILE_BYTES = 64 * 1024 * 1024

HINT_INLINE_JSON = ('do not put JSON on the command line (PowerShell 5.1 strips the inner quotes): '
                    'write the object to a .json file with the file tool and pass --params-file FILE')


class ParamError(ValueError):
    """A caller mistake in parameters or output options (maps to exit 1 with allowed/hint)."""

    def __init__(self, message, allowed=None, hint=None):
        super().__init__(message)
        self.allowed = list(allowed) if allowed is not None else None
        self.hint = hint


# --------------------------------------------------------------------------- decoding

def decode_bytes(data):
    """bytes -> (text, warning|None). BOM first, then strict UTF-8, then cp1256."""
    if data.startswith(b'\xef\xbb\xbf'):
        return data[3:].decode('utf-8'), None
    if data.startswith(b'\xff\xfe\x00\x00') or data.startswith(b'\x00\x00\xfe\xff'):
        return data.decode('utf-32'), None
    if data.startswith(b'\xff\xfe') or data.startswith(b'\xfe\xff'):
        return data.decode('utf-16'), None
    try:
        return data.decode('utf-8'), None
    except UnicodeDecodeError:
        pass
    # UTF-16 without BOM (rare): many NUL bytes in odd or even positions.
    if len(data) >= 4 and data.count(b'\x00') * 3 >= len(data):
        enc = 'utf-16-le' if data[1:2] == b'\x00' else 'utf-16-be'
        try:
            return data.decode(enc), f'decoded as {enc} without BOM'
        except UnicodeDecodeError:
            pass
    return data.decode('cp1256', errors='replace'), 'not UTF-8: decoded as cp1256 (Windows Arabic); save files as UTF-8'


def read_text_bytes(path, warnings=None):
    """Read a text file from bytes whatever the shell or editor used to save it."""
    p = Path(path).expanduser()
    if not p.is_file():
        raise ParamError(f'file not found: {p}', hint='give an existing file path (absolute is safest)')
    if p.stat().st_size > MAX_PARAM_FILE_BYTES:
        raise ParamError(f'file too large (> {MAX_PARAM_FILE_BYTES} bytes): {p}')
    text, warning = decode_bytes(p.read_bytes())
    if warning and warnings is not None:
        warnings.append(f'{p.name}: {warning}')
    return text


def _json_object(text, where):
    try:
        obj = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ParamError(f'{where} is not valid JSON: {exc.msg} (line {exc.lineno} column {exc.colno})',
                         hint='write the parameters as one JSON object, e.g. {"text": "..."}') from None
    if not isinstance(obj, dict):
        raise ParamError(f'{where} must hold a JSON object {{...}}, not {type(obj).__name__}')
    return obj


# --------------------------------------------------------------------------- typing

_INT_RE = re.compile(r'[+-]?\d+\Z')
_NUM_RE = re.compile(r'[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?\Z')
_TRUE = {'true', '1', 'yes', 'on'}
_FALSE = {'false', '0', 'no', 'off'}


def coerce(key, value, ptype):
    """Type one key=value string by its declared schema type."""
    if ptype in (None, 'string', 'path'):
        return value
    v = value.strip()
    if ptype == 'integer':
        if _INT_RE.match(v):
            return int(v)
        if _NUM_RE.match(v):
            return float(v)
        raise ParamError(f'{key} expects an integer, got {value!r}')
    if ptype == 'number':
        if _INT_RE.match(v):
            return int(v)
        if _NUM_RE.match(v):
            return float(v)
        raise ParamError(f'{key} expects a number, got {value!r}')
    if ptype == 'bool':
        if v.lower() in _TRUE:
            return True
        if v.lower() in _FALSE:
            return False
        raise ParamError(f'{key} expects true or false, got {value!r}', allowed=['true', 'false'])
    if ptype in ('list', 'object'):
        try:
            obj = json.loads(v)
        except json.JSONDecodeError:
            raise ParamError(f'{key} expects a JSON {ptype}', hint=HINT_INLINE_JSON) from None
        if ptype == 'list' and not isinstance(obj, list) or ptype == 'object' and not isinstance(obj, dict):
            raise ParamError(f'{key} expects a JSON {ptype}', hint=HINT_INLINE_JSON)
        return obj
    # 'auto': unknown declared type (introspection fallback). Numbers, booleans,
    # null and JSON containers are parsed; anything else stays a string.
    if v in ('true', 'false', 'null') or _NUM_RE.match(v) or v[:1] in ('{', '['):
        try:
            return json.loads(v)
        except json.JSONDecodeError:
            return value
    return value


def _ptype(schema, key):
    if not schema:
        return None
    spec = schema.get(key)
    if isinstance(spec, dict):
        return spec.get('type') or 'auto'
    return 'auto' if spec is not None else None


def parse_pairs(tokens, schema=None):
    """['k=v', 'k:=RAW', ...] -> dict. Declared string stays string; no schema -> string."""
    out = {}
    for tok in tokens or ():
        if not isinstance(tok, str):
            raise ParamError('parameters must be key=value strings')
        if '=' not in tok:
            hint = HINT_INLINE_JSON if tok.lstrip()[:1] in ('{', '[') else 'write parameters as key=value (e.g. text="..." t=0.8)'
            raise ParamError(f'not a key=value parameter: {tok[:80]!r}', hint=hint)
        key, value = tok.split('=', 1)
        raw = key.endswith(':')
        if raw:
            key = key[:-1]
        key = key.strip()
        if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', key):
            raise ParamError(f'bad parameter name: {key[:60]!r}', hint='names are letters, digits and _ (e.g. png_width=540)')
        if raw:
            try:
                out[key] = json.loads(value)
            except json.JSONDecodeError as exc:
                raise ParamError(f'{key}:= value is not JSON: {exc.msg}', hint=HINT_INLINE_JSON) from None
        else:
            out[key] = coerce(key, value, _ptype(schema, key))
    return out


def read_params(args, schema=None, warnings=None, stdin=None):
    """Merge, in this order (later wins): --params-file, --stdin, key=value, --file-param.

    ``args`` is an argparse Namespace (or any object) with optional attributes
    params_file, stdin, params (list of tokens) and file_param (list of key=FILE).
    """
    merged = {}
    pfile = getattr(args, 'params_file', None)
    if pfile:
        merged.update(_json_object(read_text_bytes(pfile, warnings), f'params file {pfile}'))
    if getattr(args, 'stdin', False):
        stream = stdin if stdin is not None else sys.stdin
        data = stream.buffer.read() if hasattr(stream, 'buffer') else stream.read()
        text = decode_bytes(data)[0] if isinstance(data, bytes) else data
        merged.update(_json_object(text, 'stdin'))
    merged.update(parse_pairs(getattr(args, 'params', None) or [], schema))
    for item in getattr(args, 'file_param', None) or []:
        if '=' not in item:
            raise ParamError(f'--file-param needs key=FILE, got {item[:80]!r}')
        key, path = item.split('=', 1)
        key = key.strip()
        if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', key):
            raise ParamError(f'bad parameter name: {key[:60]!r}')
        merged[key] = read_text_bytes(path, warnings)
    return merged


def add_param_arguments(parser):
    """Add the shared input flags (positional key=value, --params-file, --stdin, --file-param)."""
    parser.add_argument('params', nargs='*', metavar='key=value',
                        help='parameters; key:=JSON forces JSON; values are typed from the op schema')
    parser.add_argument('--params-file', metavar='FILE',
                        help='JSON object file with parameters (safe for large or nested input)')
    parser.add_argument('--stdin', action='store_true', help='read a JSON object of parameters from stdin')
    parser.add_argument('--file-param', action='append', default=[], metavar='key=FILE',
                        help='use the text of FILE as the value of key (repeatable)')
    return parser


# --------------------------------------------------------------------------- writing

def write_json(path, obj, overwrite=True):
    """UTF-8, no BOM, indented, newline at end. overwrite=False refuses an existing file."""
    p = Path(path).expanduser()
    data = (json.dumps(obj, ensure_ascii=False, indent=2, default=str) + '\n').encode('utf-8')
    p.parent.mkdir(parents=True, exist_ok=True)
    if overwrite:
        tmp = p.with_name(p.name + '.tmp-rose')
        tmp.write_bytes(data)
        os.replace(tmp, p)
    else:
        with open(p, 'xb') as fh:
            fh.write(data)
    return str(p.resolve())


def parse_save_pairs(items):
    """['svg=a.svg', 'png=b.png'] -> [(field, path)]. Comma lists are refused."""
    pairs = []
    for item in items or ():
        if isinstance(item, (tuple, list)) and len(item) == 2:
            pairs.append((str(item[0]), str(item[1])))
            continue
        if not isinstance(item, str) or '=' not in item:
            raise ParamError(f'--save needs FIELD=FILE, got {str(item)[:80]!r}', hint='e.g. --save png=C:/work/frame.png')
        field, path = item.split('=', 1)
        if re.search(r',\s*[A-Za-z_][A-Za-z0-9_]*=', path):
            raise ParamError('--save takes one FIELD=FILE; it is never comma-separated',
                             hint='repeat the flag: --save svg=a.svg --save png=b.png')
        field = field.strip()
        if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', field) or not path.strip():
            raise ParamError(f'--save needs FIELD=FILE, got {item[:80]!r}')
        pairs.append((field, path.strip()))
    return pairs


def find_field(obj, field, depth=0):
    """First value for key ``field`` (breadth-first) in a nested dict/list, else None."""
    queue = [obj]
    seen = 0
    while queue and seen < 200_000:
        node = queue.pop(0)
        seen += 1
        if isinstance(node, dict):
            if field in node and node[field] is not None:
                return node[field]
            queue.extend(v for v in node.values() if isinstance(v, (dict, list)))
        elif isinstance(node, list):
            queue.extend(v for v in node if isinstance(v, (dict, list)))
    return None


def available_fields(obj, limit=40):
    """Keys present anywhere in the result (for the `allowed` list of a failed --save)."""
    keys, queue = [], [obj]
    while queue and len(keys) < limit:
        node = queue.pop(0)
        if isinstance(node, dict):
            for k, v in node.items():
                if isinstance(v, (str, bytes)) or isinstance(v, (dict, list)) and v:
                    name = k[:-7] if k.endswith('_base64') else k
                    if name not in keys:
                        keys.append(name)
                if isinstance(v, (dict, list)):
                    queue.append(v)
        elif isinstance(node, list):
            queue.extend(v for v in node[:50] if isinstance(v, (dict, list)))
    return keys[:limit]


def _field_bytes(result, field):
    if field.endswith('_base64'):
        val = find_field(result, field)
        b64 = True
    else:
        val = find_field(result, field)
        b64 = False
        if val is None:
            val = find_field(result, field + '_base64')
            b64 = val is not None
    if val is None:
        raise ParamError(f'field {field!r} is not in the result', allowed=available_fields(result),
                         hint='pick a field from allowed (png comes from png_base64)')
    if b64:
        if not isinstance(val, str):
            raise ParamError(f'field {field!r} is not base64 text')
        try:
            return base64.b64decode(val, validate=False)
        except (binascii.Error, ValueError):
            raise ParamError(f'field {field!r} is not valid base64') from None
    if isinstance(val, str):
        return val.encode('utf-8')
    if isinstance(val, bytes):
        return val
    return (json.dumps(val, ensure_ascii=False, indent=2, default=str) + '\n').encode('utf-8')


def save_fields(result, pairs, overwrite=False):
    """Write result fields to files -> {field: abs_path}. Refuses existing files.

    All fields are resolved first, so a bad field name writes nothing at all.
    """
    plan = []
    for field, path in parse_save_pairs(pairs):
        p = Path(path).expanduser().resolve()
        if p.exists() and not overwrite:
            raise ParamError(f'refusing to overwrite an existing file: {p}', hint='choose a new file name')
        plan.append((field, p, _field_bytes(result, field)))
    saved = {}
    for field, p, data in plan:
        p.parent.mkdir(parents=True, exist_ok=True)
        if overwrite:
            p.write_bytes(data)
        else:
            with open(p, 'xb') as fh:
                fh.write(data)
        saved[field] = str(p)
    return saved


# --------------------------------------------------------------------------- printing

def emit(obj, pretty=False, stream=None):
    """Print exactly one JSON document as UTF-8 (independent of the console code page)."""
    text = json.dumps(obj, ensure_ascii=False, indent=2 if pretty else None, default=str) + '\n'
    out = stream if stream is not None else sys.stdout
    buf = getattr(out, 'buffer', None)
    if buf is not None:
        try:
            out.flush()
        except (OSError, ValueError):
            pass
        buf.write(text.encode('utf-8'))
        buf.flush()
    else:
        out.write(text)
        try:
            out.flush()
        except (OSError, ValueError):
            pass


def error_doc(error, allowed=None, hint=None, next=None, **extra):
    doc = {'ok': False, 'outcome': 'error', 'error': str(error),
           'allowed': list(allowed) if allowed is not None else None,
           'hint': hint, 'next': list(next or [])}
    doc.update(extra)
    return doc


def fail(error, allowed=None, hint=None, next=None, code=EXIT_ERROR, stream=None, **extra):
    """Print a one-line JSON error and return the exit code (never raises)."""
    emit(error_doc(error, allowed, hint, next, **extra), stream=stream)
    return code


def json_usage_errors(parser):
    """Make an argparse parser report usage errors as one JSON line with exit 2."""
    def _error(message, _parser=parser):
        fail('usage: ' + message, hint=_parser.format_usage().strip(), code=EXIT_USAGE)
        raise SystemExit(EXIT_USAGE)
    parser.error = _error
    return parser
