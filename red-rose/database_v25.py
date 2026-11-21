"""Red Rose V25: safe, bounded SQLite / CSV data helpers (topics 23.01-23.10).

Standard library only. No network, no subprocess, no exec/eval, no printing.
Every op validates its inputs strictly (ValueError on unknown parameter names,
bools-as-numbers, bad identifiers, oversize inputs) and returns
{'op', 'result', 'assumptions', 'limits'}.

Data rules:
- Database / CSV / work-dir paths are always supplied by the caller. With no
  db_path an op works on a throwaway in-memory example database. The owner's
  private store (~/.red-rose/...) is refused unless allow_private_db=True.
- Values are always bound as SQL parameters. Identifiers (table / column / index
  names) supplied by the caller must match ^[A-Za-z_][A-Za-z0-9_]{0,63}$ and are
  double-quoted; names read back from a database are quoted with "" escaping.
- Ops whose EFFECTS entry is 'write' change nothing unless approve_write=True;
  without it they return {'status': 'approval_required', ...} plus a read-only
  preview.
- Every connection is closed in a finally block. File contents are data only.
"""
from __future__ import annotations

import contextlib
import csv
import hashlib
import hmac
import io
import json
import math
import sqlite3
import statistics
import time
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

MAX_PARAMS = 24
MAX_FILE_BYTES = 20 * 1024 * 1024
MAX_SCAN_ROWS = 500_000
MAX_INPUT_ROWS = 100_000
MAX_RESULT_ROWS = 1_000
MAX_TABLES = 50
MAX_COLUMNS = 100
MAX_SQL_CHARS = 10_000
IDENT_PATTERN = r'^[A-Za-z_][A-Za-z0-9_]{0,63}$'

TOPICS = {
    '23.01': 'safe_schema',
    '23.02': 'tenant_query',
    '23.03': 'index_plan',
    '23.04': 'record_conflicts',
    '23.05': 'safe_migration',
    '23.06': 'import_tabular',
    '23.07': 'protect_sensitive',
    '23.08': 'backup_restore',
    '23.09': 'time_series',
    '23.10': 'lineage',
}

TOPIC_NAMES_AR = {
    '23.01': 'بناء مخطط ذاكرة آمن',
    '23.02': 'فصل بيانات الشركات',
    '23.03': 'فهرسة معرفات سريعة',
    '23.04': 'كشف التناقض بين السجلات',
    '23.05': 'ترحيل Schema بأمان',
    '23.06': 'استيراد بيانات CSV/JSON',
    '23.07': 'حماية البيانات الحساسة',
    '23.08': 'نسخ احتياطي واستعادة',
    '23.09': 'تحليل السلاسل الزمنية',
    '23.10': 'سجل نسب البيانات',
}

EFFECTS = {
    'safe_schema': 'write',
    'tenant_query': 'read',
    'index_plan': 'write',
    'record_conflicts': 'read',
    'safe_migration': 'write',
    'import_tabular': 'write',
    'protect_sensitive': 'read',
    'backup_restore': 'write',
    'time_series': 'read',
    'lineage': 'write',
}

EXAMPLE_TARGET = 'in-memory example database (discarded after the call)'

# --------------------------------------------------------------------------- validation

_IDENT_FIRST = frozenset('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_')
_IDENT_REST = _IDENT_FIRST | frozenset('0123456789')


def _no_extra(extra):
    if extra:
        raise ValueError('unknown parameter(s): ' + ', '.join(sorted(map(str, extra))))


def _is_ident(value):
    return (isinstance(value, str) and 1 <= len(value) <= 64 and value[0] in _IDENT_FIRST
            and all(ch in _IDENT_REST for ch in value)
            and not value.lower().startswith('sqlite_'))


def _ident(value, name):
    """Strict identifier check equivalent to IDENT_PATTERN (and not sqlite_*)."""
    if not _is_ident(value):
        raise ValueError(f'{name} must match {IDENT_PATTERN} and not start with sqlite_')
    return value


def _idents(value, name, *, low=1, high=MAX_COLUMNS):
    if isinstance(value, str) or not isinstance(value, (list, tuple)) or not low <= len(value) <= high:
        raise ValueError(f'{name} must be a list of {low}..{high} identifiers')
    out = [_ident(v, f'{name}[{i}]') for i, v in enumerate(value)]
    if len(set(out)) != len(out):
        raise ValueError(f'{name} must not repeat names')
    return out


def _q(ident):
    """Quote an identifier that already passed _ident()."""
    return '"' + ident + '"'


def _q_any(name):
    """Quote a name read back from the database itself (standard "" escaping)."""
    return '"' + str(name).replace('"', '""') + '"'


def _bool(value, name):
    if not isinstance(value, bool):
        raise ValueError(f'{name} must be true or false')
    return value


def _int(value, low, high, name):
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise ValueError(f'{name} must be an integer from {low} to {high}')
    return value


def _choice(value, options, name):
    if not isinstance(value, str) or value not in options:
        raise ValueError(f'{name} must be one of {sorted(options)}')
    return value


def _text(value, name, *, high=1_000, allow_empty=False):
    if not isinstance(value, str) or len(value) > high or (not allow_empty and not value.strip()):
        raise ValueError(f'{name} must be a {"" if allow_empty else "non-empty "}string of at most {high} chars')
    return value


def _scalar(value, name):
    """A value that may be bound as an SQL parameter."""
    if value is None or isinstance(value, str):
        return value
    if isinstance(value, bool):
        raise ValueError(f'{name} must not be a boolean (use 0/1)')
    if isinstance(value, int):
        if not -2 ** 63 <= value < 2 ** 63:
            raise ValueError(f'{name} is outside the SQLite integer range')
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f'{name} must be finite')
        return value
    raise ValueError(f'{name} must be null, a string, an integer or a finite number')


def _jv(value):
    """JSON-safe form of a value read from SQLite."""
    if isinstance(value, (bytes, bytearray, memoryview)):
        return 'hex:' + bytes(value).hex()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    return value


def _tag(value):
    """Type-tagged canonical form used by digests (keeps 1, 1.0 and '1' distinct)."""
    if value is None:
        return ['n']
    if isinstance(value, int):
        return ['i', value]
    if isinstance(value, float):
        return ['r', repr(value)]
    if isinstance(value, (bytes, bytearray, memoryview)):
        return ['b', bytes(value).hex()]
    return ['t', str(value)]


_DIGIT_MAP = str.maketrans('٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹٫٬', '01234567890123456789.,')


def _strip_thousands(s):
    sign = ''
    if s[:1] in ('+', '-'):
        sign, s = s[0], s[1:]
    whole, dot, frac = s.partition('.')
    groups = whole.split(',')
    if not (1 <= len(groups[0]) <= 3 and all(len(g) == 3 for g in groups[1:])
            and all(g.isascii() and g.isdigit() for g in groups)):
        raise ValueError('ambiguous thousands separator')
    return sign + ''.join(groups) + dot + frac


def _to_decimal(value, name):
    if isinstance(value, bool):
        raise ValueError(f'{name} must not be a boolean')
    if isinstance(value, Decimal):
        dec = value
    elif isinstance(value, int):
        dec = Decimal(value)
    elif isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f'{name} must be finite')
        dec = Decimal(repr(value))
    elif isinstance(value, str):
        s = value.strip().translate(_DIGIT_MAP)
        if ',' in s:
            s = _strip_thousands(s)
        if not s:
            raise ValueError(f'{name} is empty')
        try:
            dec = Decimal(s)
        except InvalidOperation:
            raise ValueError(f'{name} is not a decimal number') from None
    else:
        raise ValueError(f'{name} is not a decimal number')
    if not dec.is_finite():
        raise ValueError(f'{name} must be finite')
    return dec


def _to_date(value, name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{name} is not an ISO date')
    s = value.strip().translate(_DIGIT_MAP)
    try:
        return date.fromisoformat(s)
    except ValueError:
        try:
            return datetime.fromisoformat(s).date()
        except ValueError:
            raise ValueError(f'{name} is not an ISO date (YYYY-MM-DD)') from None


def _pack(op, result, assumptions, limits):
    return {'op': op, 'result': result, 'assumptions': list(assumptions), 'limits': list(limits)}


def _approval(op, target, preview, assumptions, limits):
    result = {'status': 'approval_required', 'effect': 'write', 'changed': False,
              'target': target, 'preview': preview,
              'how_to_apply': 'call again with approve_write=True'}
    return _pack(op, result, assumptions, limits)


# --------------------------------------------------------------------------- paths & connections

def _private_root():
    return Path.home() / '.red-rose'


def _is_private(path):
    try:
        root = _private_root().resolve()
    except OSError:
        root = _private_root()
    p = str(path).casefold()
    r = str(root).casefold()
    return p == r or p.startswith(r.rstrip('\\/') + '\\') or p.startswith(r.rstrip('\\/') + '/')


def _path(value, name, allow_private_db):
    if isinstance(value, Path):
        value = str(value)
    _text(value, name, high=1_000)
    if '\x00' in value:
        raise ValueError(f'{name} must not contain NUL')
    path = Path(value).expanduser().resolve()
    if _is_private(path) and not _bool(allow_private_db, 'allow_private_db'):
        raise ValueError(f'{name} points into the owner\'s private ~/.red-rose store; '
                         'pass allow_private_db=True only with the owner\'s consent')
    return path


def _db_path(value, allow_private_db):
    _bool(allow_private_db, 'allow_private_db')
    if value is None or value == ':memory:':
        return None
    return _path(value, 'db_path', allow_private_db)


@contextlib.contextmanager
def _db(path, mode):
    """Open SQLite (None = fresh in-memory DB). mode: ro | rw | rwc. Always closed."""
    if path is None:
        conn = sqlite3.connect(':memory:', isolation_level=None)
    else:
        if mode in ('ro', 'rw') and not path.is_file():
            raise ValueError(f'database file does not exist: {path.name}')
        if mode == 'rwc' and not path.parent.is_dir():
            raise ValueError('db_path parent directory does not exist')
        conn = sqlite3.connect(path.as_uri() + '?mode=' + mode, uri=True, isolation_level=None)
    try:
        conn.execute('PRAGMA foreign_keys = ON')
        yield conn
    finally:
        conn.close()


def _target(path):
    return EXAMPLE_TARGET if path is None else str(path)


def _table_exists(conn, table):
    row = conn.execute("SELECT 1 FROM main.sqlite_master WHERE type = 'table' AND name = ?",
                       (table,)).fetchone()
    return row is not None


def _columns(conn, table):
    return [r[1] for r in conn.execute(f'PRAGMA main.table_info({_q_any(table)})')]


def _require_table(conn, table, needed=()):
    if not _table_exists(conn, table):
        raise ValueError(f'table {table} does not exist')
    cols = _columns(conn, table)
    missing = [c for c in needed if c not in cols]
    if missing:
        raise ValueError(f'table {table} has no column(s): ' + ', '.join(missing))
    return cols


def _read_file(path, name):
    if not path.is_file():
        raise ValueError(f'{name} does not exist or is not a file')
    size = path.stat().st_size
    if size > MAX_FILE_BYTES:
        raise ValueError(f'{name} is {size} bytes; limit {MAX_FILE_BYTES}')
    return path.read_bytes()


def _decode(raw, encodings):
    """Try encodings strictly; report every attempt."""
    attempts = []
    has_bom = raw.startswith(b'\xef\xbb\xbf')
    for enc in encodings:
        if enc == 'utf-8-sig' and not has_bom:
            attempts.append({'encoding': enc, 'ok': False, 'reason': 'no UTF-8 BOM'})
            continue
        try:
            text = raw.decode(enc, errors='strict')
        except (UnicodeDecodeError, LookupError) as exc:
            attempts.append({'encoding': enc, 'ok': False, 'reason': type(exc).__name__})
            continue
        attempts.append({'encoding': enc, 'ok': True})
        return text, enc, attempts
    raise ValueError('could not decode input with any of: ' + ', '.join(encodings))


def _encodings(value):
    if value is None:
        return ['utf-8-sig', 'utf-8', 'cp1256']
    if not isinstance(value, (list, tuple)) or not 1 <= len(value) <= 6:
        raise ValueError('encodings must be a list of 1..6 codec names')
    out = []
    for i, enc in enumerate(value):
        _text(enc, f'encodings[{i}]', high=32)
        try:
            ''.encode(enc)
        except LookupError:
            raise ValueError(f'encodings[{i}] is not a known codec') from None
        out.append(enc)
    return out


def _sha256(raw):
    return hashlib.sha256(raw).hexdigest()


# --------------------------------------------------------------------------- 23.01 safe_schema

_SQL_TYPES = {'INTEGER', 'TEXT', 'REAL', 'NUMERIC', 'BLOB'}
_COL_KEYS = {'name', 'type', 'not_null', 'unique', 'primary_key', 'references'}
_TABLE_KEYS = {'name', 'columns', 'unique'}


def _example_schema():
    spec = {'tables': [
        {'name': 'owners', 'columns': [
            {'name': 'id', 'type': 'INTEGER', 'primary_key': True},
            {'name': 'national_id', 'type': 'TEXT', 'not_null': True, 'unique': True},
            {'name': 'name', 'type': 'TEXT', 'not_null': True}]},
        {'name': 'accounts', 'columns': [
            {'name': 'id', 'type': 'INTEGER', 'primary_key': True},
            {'name': 'account_no', 'type': 'TEXT', 'not_null': True, 'unique': True},
            {'name': 'owner_id', 'type': 'INTEGER', 'not_null': True, 'references': 'owners.id'}]},
    ]}
    rows = [
        {'table': 'owners', 'values': {'id': 1, 'national_id': '1000000001', 'name': 'Ahmed'}},
        {'table': 'owners', 'values': {'id': 2, 'national_id': '1000000002', 'name': 'Sara'}},
        {'table': 'owners', 'values': {'id': 3, 'national_id': '1000000001', 'name': 'Duplicate'}},
        {'table': 'accounts', 'values': {'id': 1, 'account_no': 'AC-1', 'owner_id': 1}},
        {'table': 'accounts', 'values': {'id': 2, 'account_no': 'AC-2', 'owner_id': 99}},
        {'table': 'accounts', 'values': {'id': 3, 'account_no': None, 'owner_id': 2}},
    ]
    return spec, rows


def _parse_spec(spec):
    if not isinstance(spec, dict) or set(spec) != {'tables'}:
        raise ValueError("spec must be {'tables': [...]}")
    tables = spec['tables']
    if not isinstance(tables, list) or not 1 <= len(tables) <= MAX_TABLES:
        raise ValueError(f'spec.tables must be a list of 1..{MAX_TABLES} tables')
    out, seen = [], set()
    for i, t in enumerate(tables):
        where = f'spec.tables[{i}]'
        if not isinstance(t, dict) or not set(t) <= _TABLE_KEYS or 'name' not in t or 'columns' not in t:
            raise ValueError(f'{where} must have name, columns and optional unique only')
        name = _ident(t['name'], f'{where}.name')
        if name in seen:
            raise ValueError(f'{where}.name repeats {name}')
        seen.add(name)
        cols = t['columns']
        if not isinstance(cols, list) or not 1 <= len(cols) <= MAX_COLUMNS:
            raise ValueError(f'{where}.columns must be a list of 1..{MAX_COLUMNS} columns')
        parsed, names = [], []
        for j, c in enumerate(cols):
            cw = f'{where}.columns[{j}]'
            if not isinstance(c, dict) or not set(c) <= _COL_KEYS or 'name' not in c or 'type' not in c:
                raise ValueError(f'{cw} must have name and type; allowed keys {sorted(_COL_KEYS)}')
            col = {'name': _ident(c['name'], f'{cw}.name'),
                   'type': _choice(c['type'], _SQL_TYPES, f'{cw}.type'),
                   'not_null': _bool(c.get('not_null', False), f'{cw}.not_null'),
                   'unique': _bool(c.get('unique', False), f'{cw}.unique'),
                   'primary_key': _bool(c.get('primary_key', False), f'{cw}.primary_key'),
                   'references': None}
            ref = c.get('references')
            if ref is not None:
                if not isinstance(ref, str) or ref.count('.') != 1:
                    raise ValueError(f"{cw}.references must be 'table.column'")
                rt, rc = ref.split('.')
                col['references'] = (_ident(rt, f'{cw}.references table'), _ident(rc, f'{cw}.references column'))
            parsed.append(col)
            names.append(col['name'])
        if len(set(names)) != len(names):
            raise ValueError(f'{where}.columns repeat a name')
        uniques = []
        for k, group in enumerate(t.get('unique', []) or []):
            group = _idents(group, f'{where}.unique[{k}]', high=16)
            unknown = [g for g in group if g not in names]
            if unknown:
                raise ValueError(f'{where}.unique[{k}] names unknown column(s): ' + ', '.join(unknown))
            uniques.append(group)
        out.append({'name': name, 'columns': parsed, 'unique': uniques})
    return out


def _table_ddl(t):
    pk = [c['name'] for c in t['columns'] if c['primary_key']]
    parts = []
    for c in t['columns']:
        s = f"{_q(c['name'])} {c['type']}"
        if len(pk) == 1 and c['name'] == pk[0]:
            s += ' PRIMARY KEY'
        if c['not_null']:
            s += ' NOT NULL'
        if c['unique']:
            s += ' UNIQUE'
        if c['references']:
            rt, rc = c['references']
            s += f' REFERENCES {_q(rt)}({_q(rc)})'
        parts.append(s)
    if len(pk) > 1:
        parts.append('PRIMARY KEY (' + ', '.join(_q(n) for n in pk) + ')')
    for group in t['unique']:
        parts.append('UNIQUE (' + ', '.join(_q(n) for n in group) + ')')
    return f"CREATE TABLE {_q(t['name'])} (" + ', '.join(parts) + ')'


def _parse_rows(rows):
    if not isinstance(rows, list) or len(rows) > 10_000:
        raise ValueError('rows must be a list of at most 10000 {table, values} items')
    out = []
    for i, r in enumerate(rows):
        if not isinstance(r, dict) or set(r) != {'table', 'values'}:
            raise ValueError(f'rows[{i}] must be {{"table": ..., "values": {{...}}}}')
        table = _ident(r['table'], f'rows[{i}].table')
        values = r['values']
        if not isinstance(values, dict) or not 1 <= len(values) <= MAX_COLUMNS:
            raise ValueError(f'rows[{i}].values must be a non-empty dict')
        cols = [_ident(k, f'rows[{i}].values key') for k in values]
        vals = [_scalar(values[k], f'rows[{i}].values.{k}') for k in values]
        out.append((table, cols, vals))
    return out


def _constraint_kind(exc):
    code = getattr(exc, 'sqlite_errorname', '') or ''
    for key, label in (('UNIQUE', 'UNIQUE'), ('PRIMARYKEY', 'PRIMARY KEY'), ('FOREIGNKEY', 'FOREIGN KEY'),
                       ('NOTNULL', 'NOT NULL'), ('CHECK', 'CHECK')):
        if code.endswith(key):
            return label
    msg = str(exc).upper()
    for label in ('UNIQUE', 'FOREIGN KEY', 'NOT NULL', 'CHECK', 'PRIMARY KEY'):
        if label in msg:
            return label
    return 'CONSTRAINT'


def safe_schema(*, spec=None, rows=None, db_path=None, approve_write=False, allow_private_db=False,
                **extra):
    """23.01 Declarative schema with FK enforcement; constraint violations reported per row."""
    _no_extra(extra)
    _bool(approve_write, 'approve_write')
    path = _db_path(db_path, allow_private_db)
    if spec is None and rows is None and path is None:
        spec, rows = _example_schema()
    if spec is None:
        raise ValueError('spec is required')
    tables = _parse_spec(spec)
    parsed_rows = _parse_rows([] if rows is None else rows)
    ddl = [_table_ddl(t) for t in tables]
    assumptions = ['PRAGMA foreign_keys=ON is set on the connection before any statement',
                   'each row is inserted inside its own SAVEPOINT, so one rejected row does not undo the others',
                   'the whole DDL + inserts run in one transaction; any non-constraint error rolls everything back',
                   'rejections report the constraint kind and SQLite message, never the rejected values']
    limits = [f'<= {MAX_TABLES} tables, <= {MAX_COLUMNS} columns per table, <= 10000 rows',
              f'types limited to {sorted(_SQL_TYPES)}; no DEFAULT/CHECK clauses (literals would bypass binding)',
              'refuses to create a table that already exists (no silent IF NOT EXISTS)']
    if not approve_write:
        return _approval('safe_schema', _target(path), {'ddl': ddl, 'rows_to_insert': len(parsed_rows)},
                         assumptions, limits)
    inserted, rejected = [], []
    with _db(path, 'rwc') as conn:
        fk = conn.execute('PRAGMA foreign_keys').fetchone()[0]
        clash = [t['name'] for t in tables if _table_exists(conn, t['name'])]
        if clash:
            raise ValueError('table(s) already exist: ' + ', '.join(clash))
        conn.execute('BEGIN IMMEDIATE')
        try:
            for stmt in ddl:
                conn.execute(stmt)
            for i, (table, cols, vals) in enumerate(parsed_rows):
                sql = (f'INSERT INTO {_q(table)} (' + ', '.join(_q(c) for c in cols) + ') VALUES ('
                       + ', '.join('?' for _ in cols) + ')')
                conn.execute('SAVEPOINT rr_row')
                try:
                    cur = conn.execute(sql, vals)
                    inserted.append({'index': i, 'table': table, 'rowid': cur.lastrowid})
                except sqlite3.IntegrityError as exc:
                    conn.execute('ROLLBACK TO rr_row')
                    rejected.append({'index': i, 'table': table, 'constraint': _constraint_kind(exc),
                                     'message': str(exc)})
                finally:
                    conn.execute('RELEASE rr_row')
            conn.execute('COMMIT')
        except sqlite3.Error as exc:
            conn.execute('ROLLBACK')
            raise ValueError(f'schema build rolled back: {exc}') from None
        counts = {t['name']: conn.execute(f"SELECT COUNT(*) FROM {_q(t['name'])}").fetchone()[0]
                  for t in tables}
    result = {'status': 'applied', 'changed': True, 'target': _target(path), 'foreign_keys': bool(fk),
              'ddl': ddl, 'inserted': inserted, 'rejected': rejected, 'row_counts': counts}
    return _pack('safe_schema', result, assumptions, limits)


# --------------------------------------------------------------------------- 23.02 tenant_query

def _seed_tenants(conn):
    conn.executescript('''
        CREATE TABLE customers (id INTEGER PRIMARY KEY, tenant_id TEXT NOT NULL, name TEXT NOT NULL);
        CREATE TABLE invoices (id INTEGER PRIMARY KEY, tenant_id TEXT NOT NULL,
                               customer_id INTEGER NOT NULL, amount TEXT NOT NULL);
        CREATE TABLE audit_log (id INTEGER PRIMARY KEY, note TEXT);
    ''')
    conn.executemany('INSERT INTO customers VALUES (?, ?, ?)',
                     [(1, 'A', 'Alpha Trading'), (2, 'A', 'Alpha Retail'), (3, 'B', 'Beta Foods')])
    conn.executemany('INSERT INTO invoices VALUES (?, ?, ?, ?)',
                     [(1, 'A', 1, '100.00'), (2, 'A', 2, '50.00'), (3, 'B', 3, '900.00')])
    conn.execute('INSERT INTO audit_log VALUES (1, ?)', ('global note',))


def tenant_query(*, sql=None, sql_params=None, tenant_id=None, tenant_column='tenant_id', db_path=None,
                 max_rows=500, allow_private_db=False, **extra):
    """23.02 Run one SELECT where every table is replaced by a tenant-filtered view."""
    _no_extra(extra)
    path = _db_path(db_path, allow_private_db)
    tenant_column = _ident(tenant_column, 'tenant_column')
    _int(max_rows, 1, MAX_RESULT_ROWS, 'max_rows')
    if path is None and sql is None and tenant_id is None:
        tenant_id = 'A'
        sql = 'SELECT id, tenant_id, name FROM customers WHERE id = :id'
        sql_params = {'id': 3}          # a tenant-B row: must stay invisible to tenant A
    if tenant_id is None:
        raise ValueError('tenant_id is required')
    if isinstance(tenant_id, bool) or not isinstance(tenant_id, (str, int)) or tenant_id == '':
        raise ValueError('tenant_id must be a non-empty string or an integer')
    if sql is None:
        raise ValueError('sql is required')
    _text(sql, 'sql', high=MAX_SQL_CHARS)
    if sql_params is None:
        sql_params = {}
    if not isinstance(sql_params, dict) or len(sql_params) > 50:
        raise ValueError('sql_params must be a dict of at most 50 named parameters')
    bound = {_ident(k, 'sql_params key'): _scalar(v, f'sql_params.{k}') for k, v in sql_params.items()}
    assumptions = [f'every main table that has a {tenant_column} column is shadowed by a TEMP view '
                   f'filtered on {tenant_column} = the bound tenant id; the query only ever sees those views',
                   'an SQLite authorizer allows only SELECT/READ/FUNCTION; reading a main table directly '
                   '(main.x, or a table without the tenant column) is refused',
                   'the tenant id is bound as a parameter (stored in a temp table), never spliced into SQL']
    limits = [f'one statement, <= {MAX_SQL_CHARS} chars, <= {MAX_RESULT_ROWS} rows returned',
              'file databases are opened read-only (mode=ro)',
              'tables with a non-identifier name are never exposed']

    def refused(reason, scoped=()):
        return _pack('tenant_query', {'status': 'refused', 'reason': reason, 'tenant_id': tenant_id,
                                      'tables_scoped': list(scoped), 'rows': []}, assumptions, limits)

    head = sql.lstrip().split(None, 1)[0].lower() if sql.strip() else ''
    if head not in ('select', 'with'):
        return refused('only a single SELECT (or WITH ... SELECT) statement is allowed')
    with _db(path, 'ro') as conn:
        if path is None:
            _seed_tenants(conn)
        scoped, unscoped = [], []
        for (name,) in conn.execute("SELECT name FROM main.sqlite_master WHERE type = 'table' ORDER BY name"):
            if _is_ident(name) and tenant_column in _columns(conn, name):
                scoped.append(name)
            else:
                unscoped.append(name)
        if not scoped:
            return refused(f'no table carries the {tenant_column} column')
        conn.execute('CREATE TEMP TABLE _rr_tenant (id)')
        conn.execute('INSERT INTO temp._rr_tenant (id) VALUES (?)', (tenant_id,))
        for name in scoped:
            conn.execute(f'CREATE TEMP VIEW {_q(name)} AS SELECT * FROM main.{_q(name)} '
                         f'WHERE {_q(tenant_column)} = (SELECT id FROM temp._rr_tenant)')
        views = set(scoped)

        def authorizer(action, arg1, arg2, dbname, source):
            if action in (sqlite3.SQLITE_SELECT, sqlite3.SQLITE_FUNCTION, sqlite3.SQLITE_RECURSIVE):
                return sqlite3.SQLITE_OK
            if action == sqlite3.SQLITE_READ:
                if dbname == 'temp':
                    return sqlite3.SQLITE_OK
                if dbname == 'main' and source in views and arg1 == source:
                    return sqlite3.SQLITE_OK
            return sqlite3.SQLITE_DENY

        conn.set_authorizer(authorizer)
        try:
            cur = conn.execute(sql, bound)
            columns = [d[0] for d in cur.description or []]
            fetched = cur.fetchmany(max_rows + 1)
        except (sqlite3.DatabaseError, sqlite3.ProgrammingError, sqlite3.Warning) as exc:
            return refused(f'statement refused or failed: {exc}', scoped)
        finally:
            conn.set_authorizer(None)
    truncated = len(fetched) > max_rows
    rows = [{c: _jv(v) for c, v in zip(columns, r)} for r in fetched[:max_rows]]
    result = {'status': 'ok', 'tenant_id': tenant_id, 'columns': columns, 'rows': rows,
              'row_count': len(rows), 'truncated': truncated, 'tables_scoped': scoped,
              'tables_unreadable': unscoped}
    return _pack('tenant_query', result, assumptions, limits)


# --------------------------------------------------------------------------- 23.03 index_plan

def _plan(conn, query, probe):
    return [r[3] for r in conn.execute('EXPLAIN QUERY PLAN ' + query, probe)]


def _access(plan):
    if any(d.startswith('SEARCH') and 'INDEX' in d for d in plan):
        return 'SEARCH USING INDEX'
    if any(d.startswith('SEARCH') for d in plan):
        return 'SEARCH'
    if any(d.startswith('SCAN') for d in plan):
        return 'SCAN'
    return 'OTHER'


def _timing(conn, query, probe, repeat):
    times = []
    hits = 0
    for _ in range(repeat):
        t0 = time.perf_counter()
        hits = len(conn.execute(query, probe).fetchall())
        times.append((time.perf_counter() - t0) * 1000.0)
    return round(statistics.median(times), 4), hits


def index_plan(*, db_path=None, table=None, columns=None, probe=None, rows=20_000, repeat=15,
               approve_write=False, allow_private_db=False, **extra):
    """23.03 Index lookup columns; compare EXPLAIN QUERY PLAN and median timings before/after."""
    _no_extra(extra)
    _bool(approve_write, 'approve_write')
    path = _db_path(db_path, allow_private_db)
    _int(rows, 100, 200_000, 'rows')
    _int(repeat, 1, 200, 'repeat')
    if path is None:
        table = 'items' if table is None else table
        columns = ['sku'] if columns is None else columns
    if table is None or columns is None:
        raise ValueError('table and columns are required for a caller database')
    table = _ident(table, 'table')
    columns = _idents(columns, 'columns', high=8)
    if probe is not None:
        if not isinstance(probe, list) or len(probe) != len(columns):
            raise ValueError('probe must be a list with one value per column')
        probe = [_scalar(v, f'probe[{i}]') for i, v in enumerate(probe)]
    name = 'idx_' + table + '_' + '_'.join(columns)
    if len(name) > 64:
        name = 'idx_' + hashlib.sha256(name.encode()).hexdigest()[:16]
    _ident(name, 'index name')
    query = f'SELECT * FROM {_q(table)} WHERE ' + ' AND '.join(f'{_q(c)} = ?' for c in columns)
    ddl = f'CREATE INDEX IF NOT EXISTS {_q(name)} ON {_q(table)} (' + ', '.join(_q(c) for c in columns) + ')'
    assumptions = ['lookup query is an equality match on all the given columns',
                   'timings are the median of `repeat` runs in this process; they vary by machine and cache state',
                   'the plan text is SQLite\'s EXPLAIN QUERY PLAN detail column',
                   'with no db_path the example table is filled with `rows` synthetic rows'
                   + (' (only for the example)' if path is not None else '')]
    limits = ['<= 8 index columns, rows 100..200000 (example), repeat 1..200',
              'no ANALYZE is run; the planner uses default statistics',
              'index name is derived from table/columns (hashed when longer than 64 chars)']
    with _db(path, 'rw' if (approve_write and path is not None) else 'ro') as conn:
        if path is None:
            conn.execute('CREATE TABLE items (id INTEGER PRIMARY KEY, sku TEXT NOT NULL, qty INTEGER)')
            conn.executemany('INSERT INTO items (sku, qty) VALUES (?, ?)',
                             ((f'SKU-{i:06d}', i % 97) for i in range(rows)))
        _require_table(conn, table, columns)
        n_rows = conn.execute(f'SELECT COUNT(*) FROM {_q(table)}').fetchone()[0]
        if probe is None:
            first = conn.execute('SELECT ' + ', '.join(_q(c) for c in columns) + f' FROM {_q(table)} '
                                 f'ORDER BY rowid LIMIT 1 OFFSET ?', (n_rows // 2,)).fetchone()
            probe = list(first) if first else [None] * len(columns)
        existed = conn.execute("SELECT 1 FROM main.sqlite_master WHERE type = 'index' AND name = ?",
                               (name,)).fetchone() is not None
        plan_before = _plan(conn, query, probe)
        ms_before, hits = _timing(conn, query, probe, repeat)
        before = {'plan': plan_before, 'access': _access(plan_before), 'median_ms': ms_before}
        if not approve_write:
            return _approval('index_plan', _target(path),
                             {'rows': n_rows, 'query': query, 'index_ddl': ddl, 'index_existed': existed,
                              'before': before}, assumptions, limits)
        conn.execute(ddl)
        plan_after = _plan(conn, query, probe)
        ms_after, hits_after = _timing(conn, query, probe, repeat)
    after = {'plan': plan_after, 'access': _access(plan_after), 'median_ms': ms_after}
    result = {'status': 'applied', 'changed': not existed, 'target': _target(path), 'rows': n_rows,
              'query': query, 'index_ddl': ddl, 'index_name': name, 'index_existed': existed,
              'before': before, 'after': after, 'same_result_count': hits == hits_after,
              'speedup': round(ms_before / ms_after, 2) if ms_after > 0 else None,
              'switched_scan_to_search': before['access'] == 'SCAN' and after['access'] == 'SEARCH USING INDEX'}
    return _pack('index_plan', result, assumptions, limits)


# --------------------------------------------------------------------------- 23.04 record_conflicts

def _seed_conflicts(conn):
    conn.executescript('''
        CREATE TABLE accounts (id INTEGER PRIMARY KEY, account_id TEXT, owner_name TEXT, balance TEXT);
        CREATE TABLE entries (id INTEGER PRIMARY KEY, account_id TEXT, amount TEXT);
    ''')
    conn.executemany('INSERT INTO accounts VALUES (?, ?, ?, ?)', [
        (1, 'ACC-100', 'Ahmed Ali', '150.00'),
        (2, 'ACC-200', 'Sara Omar', '75.00'),
        (3, 'ACC-100', 'Mohamed Hassan', '150.00'),
        (4, 'ACC-300', 'Nour  Adel', '10.00'),
        (5, 'ACC-300', 'nour adel', '10.00'),
    ])
    conn.executemany('INSERT INTO entries VALUES (?, ?, ?)', [
        (1, 'ACC-100', '100.00'), (2, 'ACC-100', '50.00'),
        (3, 'ACC-200', '70.00'), (4, 'ACC-300', '10.00'),
    ])


_BALANCE_KEYS = {'table', 'key', 'balance', 'entries_table', 'entries_key', 'amount'}


def record_conflicts(*, db_path=None, table='accounts', key='account_id', compare=None, normalize=True,
                     balance_check=None, tolerance='0', max_violations=200, allow_private_db=False, **extra):
    """23.04 Explainable contradiction rules with evidence rows (rowids + values)."""
    _no_extra(extra)
    path = _db_path(db_path, allow_private_db)
    table = _ident(table, 'table')
    key = _ident(key, 'key')
    compare = _idents(['owner_name'] if compare is None else compare, 'compare', low=0, high=20)
    _bool(normalize, 'normalize')
    tol = _to_decimal(tolerance, 'tolerance')
    if tol < 0:
        raise ValueError('tolerance must be >= 0')
    _int(max_violations, 1, 5_000, 'max_violations')
    if balance_check is None and path is None:
        balance_check = {'table': 'accounts', 'key': 'account_id', 'balance': 'balance',
                         'entries_table': 'entries', 'entries_key': 'account_id', 'amount': 'amount'}
    if balance_check is not None:
        if not isinstance(balance_check, dict) or set(balance_check) != _BALANCE_KEYS:
            raise ValueError(f'balance_check must have exactly the keys {sorted(_BALANCE_KEYS)}')
        balance_check = {k: _ident(v, f'balance_check.{k}') for k, v in balance_check.items()}

    def norm(v):
        if v is None:
            return None
        s = str(v)
        return ' '.join(s.split()).casefold() if normalize else s

    violations = []
    with _db(path, 'ro') as conn:
        if path is None:
            _seed_conflicts(conn)
        _require_table(conn, table, [key] + compare)
        n = conn.execute(f'SELECT COUNT(*) FROM {_q(table)}').fetchone()[0]
        if n > MAX_SCAN_ROWS:
            raise ValueError(f'{table} has {n} rows; limit {MAX_SCAN_ROWS}')
        sel = ', '.join([_q(key)] + [_q(c) for c in compare])
        groups = {}
        for row in conn.execute(f'SELECT rowid, {sel} FROM {_q(table)} WHERE {_q(key)} IS NOT NULL ORDER BY rowid'):
            groups.setdefault(row[1], []).append(row)
        for k in sorted(groups, key=str):
            rows = groups[k]
            for ci, col in enumerate(compare):
                distinct = sorted({norm(r[2 + ci]) for r in rows if r[2 + ci] is not None})
                if len(distinct) > 1:
                    violations.append({
                        'rule': 'same_key_different_value', 'key': _jv(k), 'column': col,
                        'explanation': f'{key}={k!s} appears in {len(rows)} rows with {len(distinct)} different '
                                       f'{col} values' + (' (after trimming spaces and case-folding)' if normalize else ''),
                        'evidence': [{'table': table, 'rowid': r[0], key: _jv(r[1]), col: _jv(r[2 + ci])}
                                     for r in rows]})
        if balance_check:
            b = balance_check
            _require_table(conn, b['table'], [b['key'], b['balance']])
            _require_table(conn, b['entries_table'], [b['entries_key'], b['amount']])
            entries = {}
            for rid, k, amt in conn.execute(f"SELECT rowid, {_q(b['entries_key'])}, {_q(b['amount'])} "
                                            f"FROM {_q(b['entries_table'])} ORDER BY rowid"):
                entries.setdefault(k, []).append((rid, amt))
            for rid, k, bal in conn.execute(f"SELECT rowid, {_q(b['key'])}, {_q(b['balance'])} "
                                            f"FROM {_q(b['table'])} ORDER BY rowid"):
                ev = [{'table': b['table'], 'rowid': rid, b['key']: _jv(k), b['balance']: _jv(bal)}]
                ev += [{'table': b['entries_table'], 'rowid': e, b['amount']: _jv(a)} for e, a in entries.get(k, [])]
                try:
                    balance = _to_decimal(bal, 'balance')
                    total = sum((_to_decimal(a, 'amount') for _, a in entries.get(k, [])), Decimal(0))
                except ValueError as exc:
                    violations.append({'rule': 'unparseable_amount', 'key': _jv(k), 'explanation': str(exc),
                                       'evidence': ev})
                    continue
                if abs(balance - total) > tol:
                    violations.append({
                        'rule': 'balance_not_sum_of_entries', 'key': _jv(k),
                        'explanation': f'balance {balance} != sum of {len(ev) - 1} entries {total} '
                                       f'(difference {balance - total})',
                        'evidence': ev})
    truncated = len(violations) > max_violations
    result = {'rows_checked': n, 'violation_count': len(violations), 'truncated': truncated,
              'rules': ['same_key_different_value'] + (['balance_not_sum_of_entries'] if balance_check else []),
              'violations': violations[:max_violations]}
    assumptions = ['a key that maps to more than one distinct value of a compared column is a contradiction',
                   'normalize=True ignores repeated spaces and letter case; it does not equate spelling variants',
                   'balances and entries are summed exactly with Decimal (floats go through repr)',
                   'evidence lists the SQLite rowid of every row that takes part in the contradiction']
    limits = [f'<= {MAX_SCAN_ROWS} rows scanned, <= 20 compared columns, <= 5000 violations returned',
              'rules are explicit and deterministic; no fuzzy matching or probabilistic record linkage',
              'tables WITHOUT ROWID are not supported (evidence needs rowid)']
    return _pack('record_conflicts', result, assumptions, limits)


# --------------------------------------------------------------------------- 23.05 safe_migration

def _digest(conn, table_q, cols, rowid_expr='rowid'):
    sel = ', '.join(_q_any(c) for c in cols)
    h = hashlib.sha256()
    n = 0
    for row in conn.execute(f'SELECT {rowid_expr}, {sel} FROM {table_q} ORDER BY {rowid_expr}'):
        h.update(json.dumps([_tag(v) for v in row], ensure_ascii=False).encode('utf-8') + b'\n')
        n += 1
    return n, h.hexdigest()


def _sample(conn, table, cols, k):
    sel = ', '.join(_q_any(c) for c in cols)
    return [[_jv(v) for v in r] for r in conn.execute(
        f'SELECT rowid, {sel} FROM {_q(table)} ORDER BY rowid LIMIT ?', (k,))]


def _seed_migration(conn):
    conn.execute('CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT NOT NULL, city TEXT)')
    conn.executemany('INSERT INTO customers (name, city) VALUES (?, ?)',
                     [(f'customer {i}', ('Cairo', 'Riyadh', 'Dubai')[i % 3]) for i in range(1, 51)])


def _mig_up(conn, table, cols, adds, version, bak):
    n0, h0 = _digest(conn, _q(table), cols)
    conn.execute('BEGIN IMMEDIATE')
    try:
        conn.execute(f'CREATE TABLE {_q(bak)} AS SELECT rowid AS "_rr_rowid", '
                     + ', '.join(_q_any(c) for c in cols) + f' FROM {_q(table)}')
        for a in adds:
            conn.execute(f"ALTER TABLE {_q(table)} ADD COLUMN {_q(a['name'])} {a['type']}")
            if a['default'] is not None:
                conn.execute(f"UPDATE {_q(table)} SET {_q(a['name'])} = ?", (a['default'],))
        n1, h1 = _digest(conn, _q(table), cols)
        nb, hb = _digest(conn, _q(bak), cols, '"_rr_rowid"')
        if not (n0 == n1 == nb and h0 == h1 == hb):
            raise RuntimeError('verification failed: row count or original values changed')
        for a in adds:
            bad = conn.execute(f"SELECT COUNT(*) FROM {_q(table)} WHERE {_q(a['name'])} IS NOT ?",
                               (a['default'],)).fetchone()[0]
            if bad:
                raise RuntimeError(f"verification failed: {bad} rows of {a['name']} lack the default")
        conn.execute('CREATE TABLE IF NOT EXISTS "_rr_migrations" (table_name TEXT NOT NULL, '
                     'version TEXT NOT NULL, added_columns TEXT NOT NULL, backup_table TEXT NOT NULL, '
                     'applied_at TEXT NOT NULL, PRIMARY KEY (table_name, version))')
        conn.execute('INSERT INTO "_rr_migrations" VALUES (?, ?, ?, ?, ?)',
                     (table, version, json.dumps([a['name'] for a in adds]), bak,
                      datetime.now(timezone.utc).isoformat(timespec='seconds')))
        conn.execute('COMMIT')
    except (sqlite3.Error, RuntimeError) as exc:
        conn.execute('ROLLBACK')
        return {'step': 'up', 'ok': False, 'error': str(exc)}
    return {'step': 'up', 'ok': True, 'rows': n1, 'verified_sha256': h1, 'backup_table': bak}


def _mig_down(conn, table, version):
    if not _table_exists(conn, '_rr_migrations'):
        return {'step': 'down', 'ok': False, 'error': 'no migration record found'}
    rec = conn.execute('SELECT added_columns, backup_table FROM "_rr_migrations" '
                       'WHERE table_name = ? AND version = ?', (table, version)).fetchone()
    if rec is None:
        return {'step': 'down', 'ok': False, 'error': f'no migration {version} recorded for {table}'}
    added = json.loads(rec[0])
    bak = _ident(rec[1], 'backup table')
    conn.execute('BEGIN IMMEDIATE')
    try:
        for c in added:
            conn.execute(f'ALTER TABLE {_q(table)} DROP COLUMN {_q(_ident(c, "added column"))}')
        cols = _columns(conn, table)
        bak_cols = [c for c in _columns(conn, bak) if c != '_rr_rowid']
        if cols != bak_cols:
            raise RuntimeError('verification failed: column list differs from the backup')
        n1, h1 = _digest(conn, _q(table), cols)
        nb, hb = _digest(conn, _q(bak), cols, '"_rr_rowid"')
        if (n1, h1) != (nb, hb):
            raise RuntimeError('verification failed: restored values differ from the backup copy')
        conn.execute(f'DROP TABLE {_q(bak)}')
        conn.execute('DELETE FROM "_rr_migrations" WHERE table_name = ? AND version = ?', (table, version))
        if conn.execute('SELECT COUNT(*) FROM "_rr_migrations"').fetchone()[0] == 0:
            conn.execute('DROP TABLE "_rr_migrations"')
        conn.execute('COMMIT')
    except (sqlite3.Error, RuntimeError) as exc:
        conn.execute('ROLLBACK')
        return {'step': 'down', 'ok': False, 'error': str(exc)}
    return {'step': 'down', 'ok': True, 'rows': n1, 'verified_sha256': h1}


def safe_migration(*, db_path=None, table=None, add_columns=None, version='v2', direction='cycle', sample=5,
                   approve_write=False, allow_private_db=False, **extra):
    """23.05 Transactional add-column migration with backup copy, verification and down-migration."""
    _no_extra(extra)
    _bool(approve_write, 'approve_write')
    path = _db_path(db_path, allow_private_db)
    _choice(direction, {'up', 'down', 'cycle'}, 'direction')
    _int(sample, 1, 100, 'sample')
    if path is None and table is None:
        table = 'customers'
        if add_columns is None:
            add_columns = [{'name': 'segment', 'type': 'TEXT', 'default': 'retail'}]
    if table is None:
        raise ValueError('table is required')
    table = _ident(table, 'table')
    if not isinstance(version, str) or not version or len(version) > 16 or not all(ch in _IDENT_REST for ch in version):
        raise ValueError('version must be 1..16 letters, digits or _')
    adds = []
    if direction != 'down':
        if not isinstance(add_columns, list) or not 1 <= len(add_columns) <= 20:
            raise ValueError('add_columns must be a list of 1..20 {name, type, default} items')
        for i, a in enumerate(add_columns):
            if not isinstance(a, dict) or not {'name', 'type'} <= set(a) <= {'name', 'type', 'default'}:
                raise ValueError(f'add_columns[{i}] must have name, type and optional default')
            adds.append({'name': _ident(a['name'], f'add_columns[{i}].name'),
                         'type': _choice(a['type'], _SQL_TYPES, f'add_columns[{i}].type'),
                         'default': _scalar(a.get('default'), f'add_columns[{i}].default')})
    bak = _ident(f'_bak_{table}_{version}'[:64], 'backup table name')
    assumptions = ['up: BEGIN IMMEDIATE -> copy table to a backup table (with rowid) -> ADD COLUMN -> set '
                   'defaults with a bound UPDATE -> verify counts and a sha256 of every original value -> record '
                   'in _rr_migrations -> COMMIT; any failure rolls the whole step back',
                   'down: DROP COLUMN for the recorded columns, verify against the backup, drop the backup',
                   'cycle runs up then down and compares count, digest and sampled rows before/after']
    limits = ['only additive column migrations (ADD/DROP COLUMN); renames and type changes are not handled',
              'added columns are nullable: NOT NULL/DEFAULT clauses would need SQL literals, so defaults are '
              'written by a bound UPDATE instead',
              'DROP COLUMN needs SQLite >= 3.35 and fails if the column is indexed or used by a view/trigger',
              f'sample <= 100 rows; SQLite {sqlite3.sqlite_version} in this runtime']
    with _db(path, 'rw' if (approve_write and path is not None) else 'ro') as conn:
        if path is None:
            _seed_migration(conn)
        cols = _require_table(conn, table)
        if '_rr_rowid' in cols:
            raise ValueError('table already has a _rr_rowid column')
        clash = [a['name'] for a in adds if a['name'] in cols]
        stable = list(cols)
        if direction == 'down' and _table_exists(conn, '_rr_migrations'):
            rec = conn.execute('SELECT added_columns FROM "_rr_migrations" WHERE table_name = ? AND version = ?',
                               (table, version)).fetchone()
            if rec is not None:
                stable = [c for c in cols if c not in json.loads(rec[0])]
        ns, hs = _digest(conn, _q(table), stable)
        n0, h0 = _digest(conn, _q(table), cols)
        before = {'rows': n0, 'sha256': h0, 'columns': cols, 'sample': _sample(conn, table, cols, sample)}
        if not approve_write:
            return _approval('safe_migration', _target(path),
                             {'direction': direction, 'backup_table': bak, 'add_columns': adds,
                              'columns_already_present': clash, 'before': before}, assumptions, limits)
        steps = []
        if direction in ('up', 'cycle'):
            steps.append(_mig_up(conn, table, cols, adds, version, bak))
        if direction == 'down' or (direction == 'cycle' and steps[-1]['ok']):
            steps.append(_mig_down(conn, table, version))
        now_cols = _columns(conn, table)
        kept = [c for c in stable if c in now_cols]
        n1, h1 = _digest(conn, _q(table), kept)
        after = {'rows': n1, 'sha256': h1, 'columns': now_cols,
                 'sample': _sample(conn, table, kept, sample),
                 'backup_table_exists': _table_exists(conn, bak)}
    ok = all(s['ok'] for s in steps)
    status = 'applied' if ok else 'rolled_back'
    result = {'status': status, 'changed': ok and direction != 'cycle', 'target': _target(path),
              'direction': direction, 'steps': steps, 'before': before, 'after': after,
              'stable_columns': stable,
              'original_values_identical': (ns, hs) == (n1, h1) and stable == kept,
              'schema_restored': direction == 'cycle' and ok and now_cols == cols}
    return _pack('safe_migration', result, assumptions, limits)


# --------------------------------------------------------------------------- 23.06 import_tabular

_IMPORT_TYPES = {'text': 'TEXT', 'int': 'INTEGER', 'decimal': 'TEXT', 'date': 'TEXT'}
_EXAMPLE_CSV = ('الاسم,المبلغ,التاريخ,ملاحظة\n'
                'أحمد علي,"1,250.50",2026-01-05,دفعة أولى\n'
                'سارة عمر,٣٠٠٫٢٥,2026-01-09,\n')
_EXAMPLE_MAPPING = {'الاسم': {'to': 'name', 'type': 'text', 'required': True},
                    'المبلغ': {'to': 'amount', 'type': 'decimal', 'required': True},
                    'التاريخ': {'to': 'paid_on', 'type': 'date', 'required': True}}


def _parse_mapping(mapping):
    if not isinstance(mapping, dict) or not 1 <= len(mapping) <= MAX_COLUMNS:
        raise ValueError(f'mapping must be a dict of 1..{MAX_COLUMNS} source columns')
    out = {}
    for src, spec in mapping.items():
        _text(src, 'mapping source column', high=200)
        if not isinstance(spec, dict) or not {'to', 'type'} <= set(spec) <= {'to', 'type', 'required'}:
            raise ValueError(f'mapping[{src!r}] must have to, type and optional required')
        out[src] = {'to': _ident(spec['to'], f'mapping[{src!r}].to'),
                    'type': _choice(spec['type'], set(_IMPORT_TYPES), f'mapping[{src!r}].type'),
                    'required': _bool(spec.get('required', True), f'mapping[{src!r}].required')}
    dsts = [s['to'] for s in out.values()]
    if len(set(dsts)) != len(dsts):
        raise ValueError('mapping targets must be unique')
    return out


def _coerce(value, kind, name):
    if value is None or (isinstance(value, str) and value.strip() == ''):
        return None
    if kind == 'text':
        if not isinstance(value, (str, int, float)) or isinstance(value, bool):
            raise ValueError(f'{name} is not text')
        return str(value).strip()
    if kind == 'int':
        if isinstance(value, bool):
            raise ValueError(f'{name} is not an integer')
        dec = _to_decimal(value, name)
        if dec != dec.to_integral_value():
            raise ValueError(f'{name} is not a whole number')
        return int(dec)
    if kind == 'decimal':
        return str(_to_decimal(value, name))
    return _to_date(value, name).isoformat()


def import_tabular(*, path=None, content=None, fmt='csv', mapping=None, table='imported', db_path=None,
                   encodings=None, delimiter=',', extra_policy='report', max_errors=50, approve_write=False,
                   allow_private_db=False, **extra):
    """23.06 Strict CSV/JSON import: encoding detection, column mapping, Decimal money, gated write."""
    _no_extra(extra)
    _bool(approve_write, 'approve_write')
    _bool(allow_private_db, 'allow_private_db')
    _choice(fmt, {'csv', 'json'}, 'fmt')
    _choice(extra_policy, {'report', 'reject'}, 'extra_policy')
    _choice(delimiter, {',', ';', '\t', '|'}, 'delimiter')
    _int(max_errors, 1, 1_000, 'max_errors')
    table = _ident(table, 'table')
    encs = _encodings(encodings)
    dbp = _db_path(db_path, allow_private_db)
    if path is None and content is None:
        if mapping is not None:
            raise ValueError('path or content is required')
        content, mapping, fmt = _EXAMPLE_CSV, _EXAMPLE_MAPPING, 'csv'
    if (path is None) == (content is None):
        raise ValueError('give exactly one of path or content')
    if mapping is None:
        raise ValueError('mapping is required')
    cmap = _parse_mapping(mapping)
    if path is not None:
        src = _path(path, 'path', allow_private_db)
        raw = _read_file(src, 'path')
        text, encoding, attempts = _decode(raw, encs)
        source = {'kind': 'file', 'name': src.name, 'sha256': _sha256(raw), 'bytes': len(raw)}
    else:
        _text(content, 'content', high=MAX_FILE_BYTES, allow_empty=True)
        text, encoding, attempts = content, 'str (already decoded by caller)', []
        source = {'kind': 'content', 'sha256': _sha256(content.encode('utf-8')), 'chars': len(content)}
    assumptions = ['encodings are tried strictly in order (default utf-8-sig only when a BOM is present, then '
                   'utf-8, then cp1256); the first clean decode wins and every attempt is reported',
                   'money columns become Decimal and are stored as canonical TEXT (no float rounding); '
                   'Arabic-Indic digits and the Arabic decimal mark are accepted; "," only as 3-digit grouping',
                   'empty cells are NULL; a required column must exist in the header, its cells may be empty '
                   'only if the value is optional',
                   'any row error rejects the whole import: nothing is written']
    limits = [f'<= {MAX_FILE_BYTES} bytes, <= {MAX_INPUT_ROWS} rows, <= {MAX_COLUMNS} mapped columns',
              'cp1256 decodes almost any byte string, so it is a last resort and can mis-read other 8-bit encodings',
              'dates must be ISO (YYYY-MM-DD or ISO datetime)']
    if fmt == 'csv':
        reader = csv.reader(io.StringIO(text, newline=''), delimiter=delimiter, strict=True)
        try:
            all_rows = list(reader)
        except csv.Error as exc:
            raise ValueError(f'CSV is malformed: {exc}') from None
        if not all_rows:
            raise ValueError('CSV has no header row')
        header = [h.strip() for h in all_rows[0]]
        records = []
        bad_width = []
        for i, r in enumerate(all_rows[1:], start=1):
            if not any(cell.strip() for cell in r):
                continue
            if len(r) != len(header):
                bad_width.append(i)
            records.append((i, dict(zip(header, r))))
    else:
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f'JSON is malformed: {exc.msg}') from None
        if not isinstance(data, list) or not all(isinstance(o, dict) for o in data):
            raise ValueError('JSON input must be a list of objects')
        header = list(data[0]) if data else []
        records = [(i, o) for i, o in enumerate(data, start=1)]
        bad_width = [i for i, o in records if list(o) != header]
    if len(records) > MAX_INPUT_ROWS:
        raise ValueError(f'{len(records)} rows; limit {MAX_INPUT_ROWS}')
    if len(set(header)) != len(header):
        raise ValueError('header repeats a column name')
    missing = [s for s, m in cmap.items() if m['required'] and s not in header]
    absent_optional = [s for s, m in cmap.items() if not m['required'] and s not in header]
    extra_cols = [h for h in header if h not in cmap]
    base = {'source': source, 'encoding': encoding, 'encoding_attempts': attempts, 'header': header,
            'missing_columns': missing, 'absent_optional_columns': absent_optional,
            'extra_columns': extra_cols, 'rows_read': len(records)}
    if missing:
        base.update(status='rejected', changed=False,
                    reason='missing required column(s): ' + ', '.join(missing))
        return _pack('import_tabular', base, assumptions, limits)
    if extra_cols and extra_policy == 'reject':
        base.update(status='rejected', changed=False, reason='unexpected column(s): ' + ', '.join(extra_cols))
        return _pack('import_tabular', base, assumptions, limits)
    errors = [{'row': i, 'column': None, 'reason': 'row has a different number of fields than the header'}
              for i in bad_width]
    clean = []
    for i, rec in records:
        out = {}
        for s, m in cmap.items():
            try:
                val = _coerce(rec.get(s), m['type'], s)
            except ValueError as exc:
                errors.append({'row': i, 'column': s, 'reason': str(exc)})
                continue
            if val is None and m['required']:
                errors.append({'row': i, 'column': s, 'reason': 'required value is empty'})
            out[m['to']] = val
        clean.append(out)
    if errors:
        base.update(status='rejected', changed=False, reason=f'{len(errors)} value error(s)',
                    errors=errors[:max_errors], errors_truncated=len(errors) > max_errors)
        return _pack('import_tabular', base, assumptions, limits)
    dst = [m['to'] for m in cmap.values()]
    base['preview'] = clean[:3]
    base['rows_valid'] = len(clean)
    if not approve_write:
        return _approval('import_tabular', _target(dbp) + f' table {table}', base, assumptions, limits)
    ddl = (f'CREATE TABLE IF NOT EXISTS {_q(table)} ("_rr_id" INTEGER PRIMARY KEY, '
           + ', '.join(f"{_q(m['to'])} {_IMPORT_TYPES[m['type']]}" for m in cmap.values()) + ')')
    with _db(dbp, 'rwc') as conn:
        if _table_exists(conn, table):
            _require_table(conn, table, dst)
        conn.execute('BEGIN IMMEDIATE')
        try:
            conn.execute(ddl)
            conn.executemany(f'INSERT INTO {_q(table)} (' + ', '.join(_q(c) for c in dst) + ') VALUES ('
                             + ', '.join('?' for _ in dst) + ')', [[r[c] for c in dst] for r in clean])
            conn.execute('COMMIT')
        except sqlite3.Error as exc:
            conn.execute('ROLLBACK')
            raise ValueError(f'import rolled back: {exc}') from None
        total = conn.execute(f'SELECT COUNT(*) FROM {_q(table)}').fetchone()[0]
    base.update(status='imported', changed=True, target=_target(dbp), table=table, written=len(clean),
                table_row_count=total)
    return _pack('import_tabular', base, assumptions, limits)


# --------------------------------------------------------------------------- 23.07 protect_sensitive

_KIND_BY_NAME = (('iban', 'iban'), ('phone', 'phone'), ('mobile', 'phone'), ('national', 'national_id'),
                 ('nid', 'national_id'), ('ssn', 'national_id'), ('passport', 'national_id'),
                 ('id_number', 'national_id'))
_KINDS = {'iban', 'phone', 'national_id', 'generic'}


def _kind_for(col):
    low = col.lower()
    for needle, kind in _KIND_BY_NAME:
        if needle in low:
            return kind
    return None


def _looks_like_iban(value):
    if not isinstance(value, str):
        return False
    s = ''.join(value.split()).upper()
    return (15 <= len(s) <= 34 and s[:2].isascii() and s[:2].isalpha() and s[2:4].isascii()
            and s[2:4].isdigit() and s.isascii() and s.isalnum())


def _mask(value, kind):
    if value is None:
        return None
    s = ''.join(str(value).split())
    if kind == 'iban':
        return s[:2] + '*' * (len(s) - 6) + s[-4:] if len(s) >= 10 else '*' * len(s)
    if kind == 'phone':
        return '*' * (len(s) - 3) + s[-3:] if len(s) >= 7 else '*' * len(s)
    if kind == 'national_id':
        return '*' * (len(s) - 2) + s[-2:] if len(s) >= 8 else '*' * len(s)
    return '****'


def _normal_for_hmac(value, kind):
    s = ''.join(str(value).split())
    if kind == 'iban':
        return s.upper()
    if kind == 'phone':
        return ''.join(ch for ch in s if ch.isdigit())
    return s


def _seed_sensitive(conn):
    conn.execute('CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT, iban TEXT, phone TEXT, '
                 'national_id TEXT, city TEXT, note TEXT)')
    conn.executemany('INSERT INTO customers VALUES (?, ?, ?, ?, ?, ?, ?)', [
        (1, 'Ahmed', 'SA0380000000608010167519', '+966500000001', '1012345678', 'Riyadh', 'vip'),
        (2, 'Sara', 'EG380019000500000000263180002', '+201000000002', '29001011234567', 'Cairo',
         'alt EG800002000156789012345180002'),
        (3, 'Ahmed (2nd row)', 'SA0380000000608010167519', '+966500000001', '1012345678', 'Jeddah', None),
    ])


def protect_sensitive(*, db_path=None, table='customers', columns=None, sensitive=None, pseudonymise=None,
                      pseudonym_key=None, detect_by_value=True, max_rows=200, allow_private_db=False, **extra):
    """23.07 Mask sensitive columns on read; optional keyed HMAC pseudonyms (key never stored)."""
    _no_extra(extra)
    path = _db_path(db_path, allow_private_db)
    table = _ident(table, 'table')
    _bool(detect_by_value, 'detect_by_value')
    _int(max_rows, 1, MAX_RESULT_ROWS, 'max_rows')
    if sensitive is None:
        sensitive = {}
    if not isinstance(sensitive, dict):
        raise ValueError('sensitive must be a dict {column: kind}')
    sensitive = {_ident(k, 'sensitive column'): _choice(v, _KINDS, f'sensitive.{k}') for k, v in sensitive.items()}
    pseudonymise = _idents([] if pseudonymise is None else pseudonymise, 'pseudonymise', low=0, high=20)
    key = None
    if pseudonymise:
        if isinstance(pseudonym_key, str):
            key = pseudonym_key.encode('utf-8')
        elif isinstance(pseudonym_key, (bytes, bytearray)):
            key = bytes(pseudonym_key)
        if key is None or len(key) < 16:
            raise ValueError('pseudonymise needs pseudonym_key (str/bytes, >= 16 bytes) supplied by the caller')
    elif pseudonym_key is not None:
        raise ValueError('pseudonym_key given without pseudonymise columns')
    with _db(path, 'ro') as conn:
        if path is None:
            _seed_sensitive(conn)
        all_cols = _require_table(conn, table)
        cols = all_cols if columns is None else _idents(columns, 'columns')
        _require_table(conn, table, cols + [c for c in sensitive if c not in cols])
        unknown = [c for c in pseudonymise if c not in cols]
        if unknown:
            raise ValueError('pseudonymise names column(s) not selected: ' + ', '.join(unknown))
        raw_rows = conn.execute('SELECT ' + ', '.join(_q(c) for c in cols) + f' FROM {_q(table)} '
                                'ORDER BY rowid LIMIT ?', (max_rows + 1,)).fetchall()
    truncated = len(raw_rows) > max_rows
    raw_rows = raw_rows[:max_rows]
    kinds = {}
    reasons = {}
    for c in cols:
        if c in sensitive:
            kinds[c], reasons[c] = sensitive[c], 'caller'
        elif _kind_for(c):
            kinds[c], reasons[c] = _kind_for(c), 'column name'
    for c in pseudonymise:
        if c not in kinds:
            kinds[c], reasons[c] = 'generic', 'pseudonymised'
    value_hits = {}
    out_rows = []
    for r in raw_rows:
        row = {}
        for c, v in zip(cols, r):
            if c in kinds:
                row[c] = _mask(v, kinds[c])
            elif detect_by_value and isinstance(v, str) and any(_looks_like_iban(tok) for tok in [v] + v.split()):
                parts = [_mask(tok, 'iban') if _looks_like_iban(tok) else tok for tok in v.split()]
                row[c] = _mask(v, 'iban') if _looks_like_iban(v) else ' '.join(parts)
                value_hits[c] = value_hits.get(c, 0) + 1
            else:
                row[c] = _jv(v)
            if c in pseudonymise:
                if v is None:
                    row[c + '_pseudonym'] = None
                else:
                    digest = hmac.new(key, f'{kinds[c]}:{_normal_for_hmac(v, kinds[c])}'.encode('utf-8'),
                                      hashlib.sha256).hexdigest()
                    row[c + '_pseudonym'] = 'ps_' + digest[:24]
        out_rows.append(row)
    key = None
    result = {'table': table, 'columns': cols, 'rows': out_rows, 'row_count': len(out_rows),
              'truncated': truncated,
              'protected_columns': {c: {'kind': kinds[c], 'detected_by': reasons[c]} for c in kinds},
              'value_detections': value_hits, 'pseudonymised': pseudonymise,
              'pseudonym_scheme': 'HMAC-SHA256(caller key, kind:normalised value), first 96 bits' if pseudonymise else None,
              'key_stored': False}
    assumptions = ['columns are protected when named by the caller or when their name contains iban/phone/'
                   'mobile/national/nid/ssn/passport/id_number',
                   'IBAN-shaped values (2 letters, 2 digits, 15-34 alphanumerics) are also masked in other text columns',
                   'masks keep only the country code + last 4 (IBAN), last 3 (phone), last 2 (national id)',
                   'pseudonyms are deterministic for one key, so equal values join; without the key they cannot '
                   'be recomputed; the key is used in memory only and never returned or written']
    limits = [f'<= {MAX_RESULT_ROWS} rows per call; read-only connection',
              'detection is rule-based: sensitive values in free text other than IBAN-shaped tokens are not found',
              'a 96-bit truncated HMAC is a pseudonym, not encryption; anyone holding the key can test guesses']
    return _pack('protect_sensitive', result, assumptions, limits)


# --------------------------------------------------------------------------- 23.08 backup_restore

def canonical_dump_sha256(conn):
    """sha256 over schema objects (sorted) and every table's rows (type-tagged, rowid order)."""
    h = hashlib.sha256()
    counts = {}
    objs = conn.execute("SELECT type, name, tbl_name, sql FROM main.sqlite_master "
                        "WHERE name NOT LIKE 'sqlite_%' ORDER BY type, name").fetchall()
    for obj in objs:
        h.update(json.dumps(list(obj), ensure_ascii=False).encode('utf-8') + b'\n')
    for typ, name, _, _ in objs:
        if typ != 'table':
            continue
        cols = _columns(conn, name)
        try:
            cur = conn.execute(f'SELECT * FROM main.{_q_any(name)} ORDER BY rowid')
        except sqlite3.OperationalError:
            order = ', '.join(_q_any(c) for c in cols)
            cur = conn.execute(f'SELECT * FROM main.{_q_any(name)} ORDER BY {order}')
        n = 0
        for row in cur:
            h.update(json.dumps([name, [_tag(v) for v in row]], ensure_ascii=False).encode('utf-8') + b'\n')
            n += 1
        counts[name] = n
    return h.hexdigest(), counts


def _seed_backup(conn):
    conn.executescript('''
        CREATE TABLE notes (id INTEGER PRIMARY KEY, title TEXT NOT NULL, body TEXT, score REAL, blob BLOB);
        CREATE INDEX idx_notes_title ON notes (title);
    ''')
    conn.executemany('INSERT INTO notes (title, body, score, blob) VALUES (?, ?, ?, ?)',
                     [(f'ملاحظة {i}', 'نص' * (i % 5), i / 3, bytes([i % 256])) for i in range(200)])


def _safe_name(value, name):
    _text(value, name, high=100)
    if any(ch in value for ch in '/\\:*?"<>|\x00') or value.startswith('.') or '..' in value:
        raise ValueError(f'{name} must be a plain file name')
    if not value.lower().endswith(('.sqlite3', '.sqlite', '.db')):
        raise ValueError(f'{name} must end with .sqlite3, .sqlite or .db')
    return value


def _file_sha256(path):
    h = hashlib.sha256()
    with path.open('rb') as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def backup_restore(*, db_path=None, work_dir=None, backup_name='backup.sqlite3', restore_name=None,
                   approve_write=False, allow_private_db=False, **extra):
    """23.08 Connection.backup to the caller's work dir, sha256 manifest, restore and compare dumps."""
    _no_extra(extra)
    _bool(approve_write, 'approve_write')
    path = _db_path(db_path, allow_private_db)
    _safe_name(backup_name, 'backup_name')
    if restore_name is not None:
        _safe_name(restore_name, 'restore_name')
        if restore_name == backup_name:
            raise ValueError('restore_name must differ from backup_name')
    wd = None
    if work_dir is not None:
        wd = _path(work_dir, 'work_dir', allow_private_db)
        if not wd.is_dir():
            raise ValueError('work_dir must be an existing directory')
    elif restore_name is not None:
        raise ValueError('restore_name needs work_dir')
    dest = wd / backup_name if wd else None
    manifest_path = wd / (backup_name + '.manifest.json') if wd else None
    restore_path = wd / restore_name if (wd and restore_name) else None
    if path is not None and dest is not None and dest == path:
        raise ValueError('backup destination must differ from db_path')
    for p in (dest, manifest_path, restore_path):
        if p is not None and p.exists():
            raise ValueError(f'{p.name} already exists in work_dir; refusing to overwrite')
    assumptions = ['sqlite3 Connection.backup copies a consistent snapshot page by page',
                   'the canonical dump hashes schema SQL (sorted) and every row in rowid order with type tags, '
                   'so equal hashes mean equal schema and values (not equal file bytes)',
                   'restore copies the backup into a fresh database and recomputes the canonical dump',
                   'with no work_dir the backup and restore stay in memory and no manifest file is written']
    limits = ['never overwrites an existing file; names must be plain *.sqlite3/*.sqlite/*.db file names',
              f'SQLite {sqlite3.sqlite_version}; sqlite_* internal tables are excluded from the dump',
              'the manifest is integrity evidence, not a signature: anyone can rewrite file + manifest together']
    with _db(path, 'ro') as src:
        if path is None:
            _seed_backup(src)
        src_hash, counts = canonical_dump_sha256(src)
        if not approve_write:
            return _approval('backup_restore', str(dest) if dest else 'in-memory backup copy',
                             {'source': _target(path), 'source_dump_sha256': src_hash, 'tables': counts,
                              'files_to_create': [str(p) for p in (dest, manifest_path, restore_path) if p]},
                             assumptions, limits)
        with _db(dest, 'rwc') as dst:
            src.backup(dst)
            backup_hash, _ = canonical_dump_sha256(dst)
            integrity = dst.execute('PRAGMA integrity_check').fetchone()[0]
            if dest is None:
                with _db(restore_path, 'rwc') as fresh:
                    dst.backup(fresh)
                    restored_hash, restored_counts = canonical_dump_sha256(fresh)
    manifest = {'format': 'red-rose-backup-manifest/1', 'source': _target(path),
                'backup_file': backup_name if dest else None,
                'backup_bytes': dest.stat().st_size if dest else None,
                'backup_file_sha256': _file_sha256(dest) if dest else None,
                'dump_sha256': src_hash, 'tables': counts, 'integrity_check': integrity,
                'sqlite_version': sqlite3.sqlite_version,
                'created_at': datetime.now(timezone.utc).isoformat(timespec='seconds')}
    if dest is not None:
        with _db(dest, 'ro') as bk, _db(restore_path, 'rwc') as fresh:
            bk.backup(fresh)
            restored_hash, restored_counts = canonical_dump_sha256(fresh)
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    result = {'status': 'applied', 'changed': dest is not None, 'manifest': manifest,
              'manifest_file': str(manifest_path) if manifest_path else None,
              'backup_path': str(dest) if dest else None,
              'restore_path': str(restore_path) if restore_path else 'in-memory',
              'backup_dump_sha256': backup_hash, 'restored_dump_sha256': restored_hash,
              'restored_tables': restored_counts,
              'match': src_hash == backup_hash == restored_hash and integrity == 'ok'}
    return _pack('backup_restore', result, assumptions, limits)


# --------------------------------------------------------------------------- 23.09 time_series

def _month(value, name):
    if not isinstance(value, str) or len(value) != 7 or value[4] != '-':
        raise ValueError(f'{name} must be YYYY-MM')
    try:
        y, m = int(value[:4]), int(value[5:])
    except ValueError:
        raise ValueError(f'{name} must be YYYY-MM') from None
    if not (1 <= m <= 12 and 1900 <= y <= 9999):
        raise ValueError(f'{name} must be YYYY-MM')
    return y, m


def _seed_series(conn):
    conn.execute('CREATE TABLE sales (id INTEGER PRIMARY KEY, sold_on TEXT, amount TEXT)')
    rows = []
    for y in (2024, 2025):
        for m in range(1, 13):
            if (y, m) == (2025, 3):
                continue                          # an empty month that must stay visible
            base = Decimal('100.00') + Decimal(m * 10) + (Decimal('25.50') if y == 2025 else 0)
            rows.append((f'{y}-{m:02d}-05', str(base)))
            rows.append((f'{y}-{m:02d}-20', '10.25'))
    conn.executemany('INSERT INTO sales (sold_on, amount) VALUES (?, ?)', rows)


def time_series(*, db_path=None, table='sales', date_column='sold_on', amount_column='amount', start=None,
                end=None, allow_private_db=False, **extra):
    """23.09 Monthly Decimal totals with explicit empty months, YoY change and seasonal index."""
    _no_extra(extra)
    path = _db_path(db_path, allow_private_db)
    table = _ident(table, 'table')
    date_column = _ident(date_column, 'date_column')
    amount_column = _ident(amount_column, 'amount_column')
    rng = [None if v is None else _month(v, n) for v, n in ((start, 'start'), (end, 'end'))]
    totals, counts, rejected = {}, {}, []
    with _db(path, 'ro') as conn:
        if path is None:
            _seed_series(conn)
        _require_table(conn, table, [date_column, amount_column])
        n = conn.execute(f'SELECT COUNT(*) FROM {_q(table)}').fetchone()[0]
        if n > MAX_SCAN_ROWS:
            raise ValueError(f'{table} has {n} rows; limit {MAX_SCAN_ROWS}')
        for rid, d, a in conn.execute(f'SELECT rowid, {_q(date_column)}, {_q(amount_column)} '
                                      f'FROM {_q(table)} ORDER BY rowid'):
            try:
                day = _to_date(d, 'date')
                amt = _to_decimal(a, 'amount')
            except ValueError as exc:
                rejected.append({'rowid': rid, 'reason': str(exc)})
                continue
            key = (day.year, day.month)
            totals[key] = totals.get(key, Decimal(0)) + amt
            counts[key] = counts.get(key, 0) + 1
    if not totals and (rng[0] is None or rng[1] is None):
        raise ValueError('no valid rows; give start and end to build an empty calendar')
    lo = rng[0] or min(totals)
    hi = rng[1] or max(totals)
    if lo > hi:
        raise ValueError('start must not be after end')
    span = (hi[0] - lo[0]) * 12 + hi[1] - lo[1] + 1
    if span > 600:
        raise ValueError(f'{span} months requested; limit 600')
    months, cur = [], lo
    for _ in range(span):
        months.append(cur)
        cur = (cur[0] + (cur[1] == 12), cur[1] % 12 + 1)
    inside = set(months)
    outside = sum(c for k, c in counts.items() if k not in inside)
    q4 = Decimal('0.0001')
    series = [{'month': f'{y}-{m:02d}', 'total': str(totals.get((y, m), Decimal('0'))),
               'count': counts.get((y, m), 0), 'empty': (y, m) not in totals} for y, m in months]
    yoy = []
    for y, m in months:
        prev = (y - 1, m)
        if prev in inside:
            c, p = totals.get((y, m), Decimal(0)), totals.get(prev, Decimal(0))
            yoy.append({'month': f'{y}-{m:02d}', 'total': str(c), 'previous': str(p), 'change': str(c - p),
                        'change_pct': str(((c - p) / p * 100).quantize(q4)) if p != 0 else None})
    seasonal = None
    if span >= 24:
        overall = sum((totals.get(k, Decimal(0)) for k in months), Decimal(0)) / span
        seasonal = {}
        for mm in range(1, 13):
            vals = [totals.get(k, Decimal(0)) for k in months if k[1] == mm]
            avg = sum(vals, Decimal(0)) / len(vals)
            seasonal[f'{mm:02d}'] = str((avg / overall).quantize(q4)) if overall != 0 else None
    result = {'start': f'{lo[0]}-{lo[1]:02d}', 'end': f'{hi[0]}-{hi[1]:02d}', 'months': series,
              'empty_months': [s['month'] for s in series if s['empty']],
              'rows_used': sum(counts.get(k, 0) for k in months), 'rows_outside_range': outside,
              'rejected_rows': rejected[:200], 'rejected_count': len(rejected),
              'yoy': yoy, 'seasonal_index': seasonal}
    assumptions = ['months with no rows are kept with total 0 and empty=true (never skipped)',
                   'sums are exact Decimal; percentages are quantised to 4 decimal places',
                   'YoY compares a month with the same month one year earlier inside the range',
                   'seasonal index = average total of that calendar month / average of all months '
                   '(needs >= 24 months; empty months count as 0)',
                   'rows with an unparseable date or amount are listed by rowid, not silently dropped']
    limits = [f'<= {MAX_SCAN_ROWS} rows, <= 600 months', 'dates must be ISO; time zones are ignored',
              'the seasonal index is a naive ratio with no trend removal']
    return _pack('time_series', result, assumptions, limits)


# --------------------------------------------------------------------------- 23.10 lineage

_EXAMPLE_SOURCES = [
    {'name': 'branch_cairo.csv', 'revision': 'r1',
     'content': 'region,amount,ref\nnorth,100.50,INV-1\nsouth,40.00,INV-2\nnorth,9.50,INV-3\n'},
    {'name': 'branch_giza.csv', 'revision': 'r7',
     'content': 'region,amount,ref\nsouth,60.00,INV-9\nnorth,25.00,INV-10\n'},
]


def lineage(*, sources=None, group_by='region', sum_column='amount', db_path=None, imported_at=None,
            trace=None, approve_write=False, allow_private_db=False, **extra):
    """23.10 Import rows with source hash/revision/row number/time; trace report rows back to sources."""
    _no_extra(extra)
    _bool(approve_write, 'approve_write')
    _bool(allow_private_db, 'allow_private_db')
    path = _db_path(db_path, allow_private_db)
    if sources is None:
        if path is not None:
            raise ValueError('sources are required')
        sources = _EXAMPLE_SOURCES
    if not isinstance(sources, list) or not 1 <= len(sources) <= 50:
        raise ValueError('sources must be a list of 1..50 {name, revision, content|path}')
    _text(group_by, 'group_by', high=200)
    _text(sum_column, 'sum_column', high=200)
    if imported_at is None:
        imported_at = datetime.now(timezone.utc).isoformat(timespec='seconds')
    else:
        _text(imported_at, 'imported_at', high=40)
        try:
            datetime.fromisoformat(imported_at)
        except ValueError:
            raise ValueError('imported_at must be an ISO datetime') from None
    if trace is not None:
        trace = _scalar(trace, 'trace')
    loaded = []
    for i, s in enumerate(sources):
        if not isinstance(s, dict) or not {'name', 'revision'} <= set(s) <= {'name', 'revision', 'content', 'path'} \
                or (('content' in s) == ('path' in s)):
            raise ValueError(f'sources[{i}] needs name, revision and exactly one of content/path')
        name = _text(s['name'], f'sources[{i}].name', high=200)
        rev = _text(s['revision'], f'sources[{i}].revision', high=100)
        if 'path' in s:
            raw = _read_file(_path(s['path'], f'sources[{i}].path', allow_private_db), f'sources[{i}].path')
            text, enc, _ = _decode(raw, ['utf-8-sig', 'utf-8', 'cp1256'])
        else:
            text = _text(s['content'], f'sources[{i}].content', high=MAX_FILE_BYTES)
            raw, enc = text.encode('utf-8'), 'utf-8'
        try:
            table = list(csv.reader(io.StringIO(text, newline=''), strict=True))
        except csv.Error as exc:
            raise ValueError(f'sources[{i}] CSV is malformed: {exc}') from None
        if not table:
            raise ValueError(f'sources[{i}] has no header')
        header = [h.strip() for h in table[0]]
        for need in (group_by, sum_column):
            if need not in header:
                raise ValueError(f'sources[{i}] lacks column {need}')
        rows = []
        for n, r in enumerate(table[1:], start=1):
            if not any(c.strip() for c in r):
                continue
            if len(r) != len(header):
                raise ValueError(f'sources[{i}] data row {n} has a different number of fields')
            rec = dict(zip(header, r))
            _to_decimal(rec[sum_column], f'sources[{i}] row {n} {sum_column}')
            rows.append((n, rec))
        if len(rows) > MAX_INPUT_ROWS:
            raise ValueError(f'sources[{i}] has more than {MAX_INPUT_ROWS} rows')
        loaded.append({'name': name, 'revision': rev, 'sha256': _sha256(raw), 'encoding': enc, 'rows': rows})
    assumptions = ['row_number is the 1-based data row (header excluded) inside the source file',
                   'source identity is sha256 of the exact bytes plus the caller revision label',
                   'importing the same (sha256, revision, row_number) twice is skipped, not duplicated',
                   'report totals are exact Decimal sums and each report row lists its lineage row ids; '
                   'trace_verified re-sums the traced source rows']
    limits = [f'<= 50 sources, <= {MAX_INPUT_ROWS} rows each, <= {MAX_FILE_BYTES} bytes each',
              'lineage tables are _rr_lineage_sources and _rr_lineage_rows in the target database',
              'imported_at is the caller clock (UTC) unless given; it is a label, not a trusted timestamp']
    if not approve_write:
        return _approval('lineage', _target(path), {
            'sources': [{'name': s['name'], 'revision': s['revision'], 'sha256': s['sha256'],
                         'rows': len(s['rows'])} for s in loaded]}, assumptions, limits)
    with _db(path, 'rwc') as conn:
        conn.execute('BEGIN IMMEDIATE')
        try:
            conn.execute('CREATE TABLE IF NOT EXISTS "_rr_lineage_sources" (sha256 TEXT NOT NULL, '
                         'revision TEXT NOT NULL, name TEXT NOT NULL, encoding TEXT NOT NULL, '
                         'imported_at TEXT NOT NULL, PRIMARY KEY (sha256, revision))')
            conn.execute('CREATE TABLE IF NOT EXISTS "_rr_lineage_rows" (id INTEGER PRIMARY KEY, '
                         'source_sha256 TEXT NOT NULL, revision TEXT NOT NULL, source_name TEXT NOT NULL, '
                         'row_number INTEGER NOT NULL, imported_at TEXT NOT NULL, payload TEXT NOT NULL, '
                         'UNIQUE (source_sha256, revision, row_number), '
                         'FOREIGN KEY (source_sha256, revision) REFERENCES "_rr_lineage_sources" (sha256, revision))')
            inserted = skipped = 0
            for s in loaded:
                conn.execute('INSERT INTO "_rr_lineage_sources" VALUES (?, ?, ?, ?, ?) '
                             'ON CONFLICT (sha256, revision) DO NOTHING',
                             (s['sha256'], s['revision'], s['name'], s['encoding'], imported_at))
                for n, rec in s['rows']:
                    cur = conn.execute('INSERT INTO "_rr_lineage_rows" (source_sha256, revision, source_name, '
                                       'row_number, imported_at, payload) VALUES (?, ?, ?, ?, ?, ?) '
                                       'ON CONFLICT (source_sha256, revision, row_number) DO NOTHING',
                                       (s['sha256'], s['revision'], s['name'], n, imported_at,
                                        json.dumps(rec, ensure_ascii=False, sort_keys=True)))
                    if cur.rowcount == 1:
                        inserted += 1
                    else:
                        skipped += 1
            conn.execute('COMMIT')
        except sqlite3.Error as exc:
            conn.execute('ROLLBACK')
            raise ValueError(f'lineage import rolled back: {exc}') from None
        groups = {}
        for lid, payload in conn.execute('SELECT id, payload FROM "_rr_lineage_rows" ORDER BY id'):
            rec = json.loads(payload)
            if group_by not in rec or sum_column not in rec:
                continue
            g = groups.setdefault(rec[group_by], {'total': Decimal(0), 'ids': []})
            g['total'] += _to_decimal(rec[sum_column], sum_column)
            g['ids'].append(lid)
        report = []
        for gk in sorted(groups):
            if trace is not None and gk != str(trace):
                continue
            ids = groups[gk]['ids']
            traced = []
            check = Decimal(0)
            for chunk in range(0, len(ids), 500):
                part = ids[chunk:chunk + 500]
                for row in conn.execute('SELECT id, source_name, source_sha256, revision, row_number, imported_at, '
                                        f'payload FROM "_rr_lineage_rows" WHERE id IN ({", ".join("?" * len(part))}) '
                                        'ORDER BY id', part):
                    rec = json.loads(row[6])
                    check += _to_decimal(rec[sum_column], sum_column)
                    traced.append({'lineage_id': row[0], 'source_name': row[1], 'source_sha256': row[2],
                                   'revision': row[3], 'row_number': row[4], 'imported_at': row[5]})
            report.append({group_by: gk, 'total': str(groups[gk]['total']), 'row_count': len(ids),
                           'sources': traced, 'trace_verified': check == groups[gk]['total']})
    result = {'status': 'applied', 'changed': inserted > 0, 'target': _target(path),
              'sources': [{'name': s['name'], 'revision': s['revision'], 'sha256': s['sha256'],
                           'rows': len(s['rows'])} for s in loaded],
              'rows_inserted': inserted, 'rows_skipped_duplicate': skipped, 'imported_at': imported_at,
              'report': report}
    return _pack('lineage', result, assumptions, limits)


# --------------------------------------------------------------------------- dispatcher

OPS = {
    'safe_schema': safe_schema, 'tenant_query': tenant_query, 'index_plan': index_plan,
    'record_conflicts': record_conflicts, 'safe_migration': safe_migration,
    'import_tabular': import_tabular, 'protect_sensitive': protect_sensitive,
    'backup_restore': backup_restore, 'time_series': time_series, 'lineage': lineage,
}


def run(op, params=None):
    """Validate and dispatch: run('time_series', {}) -> {'op','result','assumptions','limits'}."""
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
