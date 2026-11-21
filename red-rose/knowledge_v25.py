"""Red Rose V25: auditable knowledge memory on SQLite (topics 12.01-12.10).

Standard library only (sqlite3, pathlib, json, hashlib, re, unicodedata,
datetime, contextlib). No network, no child processes, no dynamic code
evaluation, no printing.

Interface (same pattern as physics_v20): TOPICS, OPS, EFFECTS and
run(op, params) -> {'op', 'result', 'assumptions', 'limits'}.
Every parameter is validated strictly (ValueError) and unknown parameter
names are rejected.

Database rules:
- The database path is always supplied by the caller (default ':memory:',
  a throw-away example database). The module never opens the owner's real
  memory (~/.red-rose/memory.sqlite3 or anything under ~/.red-rose) unless
  allow_private_db=True is passed explicitly.
- Every write action needs approve_write=True; otherwise the op returns
  {'status': 'approval_required'} and touches nothing (the file is not even
  opened). Read actions open existing files in SQLite read-only URI mode.
- Every connection is closed with contextlib.closing.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import unicodedata
from contextlib import closing
from datetime import date, datetime, timezone
from pathlib import Path

MAX_PARAMS = 24
MAX_TEXT = 2_000_000
MAX_QUERY = 500
MAX_ROWS_CHECKSUM = 1_000_000

TOPICS = {
    '12.01': 'index_source',
    '12.02': 'search_fts',
    '12.03': 'legacy_summaries',
    '12.04': 'owner_instructions',
    '12.05': 'error_memory',
    '12.06': 'reference_conflicts',
    '12.07': 'trust_score',
    '12.08': 'search_receipt',
    '12.09': 'migrate_memory',
    '12.10': 'workspace_isolation',
}

TOPIC_NAMES_AR = {
    '12.01': 'فهرسة مصادر مرخصة',
    '12.02': 'بحث لغوي عربي وإنجليزي',
    '12.03': 'استرجاع ملخصات السبيكة',
    '12.04': 'ذاكرة تعليمات صاحب المشروع',
    '12.05': 'ذاكرة أخطاء قابلة للتصحيح',
    '12.06': 'اكتشاف تعارض المراجع',
    '12.07': 'نظام درجات الثقة',
    '12.08': 'حفظ نتائج البحث القابلة للتدقيق',
    '12.09': 'ترحيل ذاكرة بدون فقد',
    '12.10': 'عزل بيانات الشركات والمشاريع',
}

# An op is 'write' when any of its actions writes; read-only actions inside a
# write op (get / search / recall / report / replay) do not need approval.
EFFECTS = {
    'index_source': 'write',
    'search_fts': 'read',
    'legacy_summaries': 'read',
    'owner_instructions': 'write',
    'error_memory': 'write',
    'reference_conflicts': 'write',
    'trust_score': 'read',
    'search_receipt': 'write',
    'migrate_memory': 'write',
    'workspace_isolation': 'write',
}

SPDX_LICENCES = frozenset({
    '0BSD', 'AGPL-3.0-only', 'AGPL-3.0-or-later', 'Apache-2.0', 'BSD-2-Clause',
    'BSD-3-Clause', 'BSL-1.0', 'CC-BY-3.0', 'CC-BY-4.0', 'CC-BY-SA-3.0', 'CC-BY-SA-4.0',
    'CC-BY-NC-4.0', 'CC-BY-NC-SA-4.0', 'CC0-1.0', 'EPL-2.0', 'GPL-2.0-only',
    'GPL-2.0-or-later', 'GPL-3.0-only', 'GPL-3.0-or-later', 'ISC', 'LGPL-2.1-only',
    'LGPL-2.1-or-later', 'LGPL-3.0-only', 'LGPL-3.0-or-later', 'MIT', 'MIT-0',
    'MPL-2.0', 'OFL-1.1', 'PSF-2.0', 'Unlicense', 'Zlib', 'LicenseRef-Owner',
})

PRIVATE_DIR = Path.home() / '.red-rose'


# --------------------------------------------------------------------------- validation

def _no_extra(extra):
    if extra:
        raise ValueError('unknown parameter(s): ' + ', '.join(sorted(map(str, extra))))


def _bool(value, name):
    if not isinstance(value, bool):
        raise ValueError(f'{name} must be true or false')
    return value


def _str(value, name, *, max_len=200, allow_empty=False):
    if not isinstance(value, str):
        raise ValueError(f'{name} must be a string')
    if '\x00' in value:
        raise ValueError(f'{name} must not contain NUL characters')
    if not allow_empty and not value.strip():
        raise ValueError(f'{name} is required')
    if len(value) > max_len:
        raise ValueError(f'{name} must be at most {max_len} characters')
    return value


def _int(value, low, high, name):
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise ValueError(f'{name} must be an integer from {low} to {high}')
    return value


def _num(value, low, high, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f'{name} must be a number')
    value = float(value)
    if not low <= value <= high:  # also rejects NaN
        raise ValueError(f'{name} must be in [{low}, {high}]')
    return value


def _choice(value, options, name):
    if not isinstance(value, str) or value not in options:
        raise ValueError(f'{name} must be one of {sorted(options)}')
    return value


def _date(value, name):
    if not isinstance(value, str):
        raise ValueError(f'{name} must be an ISO date string YYYY-MM-DD')
    try:
        return date.fromisoformat(value[:10]) if len(value) >= 10 else date.fromisoformat(value)
    except ValueError:
        raise ValueError(f'{name} must be an ISO date string YYYY-MM-DD') from None


_WS_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$')
_IDENT_RE = re.compile(r'^[A-Za-z_][A-Za-z0-9_]{0,63}$')


def _workspace(value):
    if value is None:
        raise ValueError('workspace is required')
    if not isinstance(value, str) or not _WS_RE.match(value):
        raise ValueError('workspace must match [A-Za-z0-9][A-Za-z0-9_.-]{0,63}')
    return value


def _sha(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def _now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def _pack(op, result, assumptions, limits):
    return {'op': op, 'result': result, 'assumptions': list(assumptions),
            'limits': list(limits)}


def _approval(op, action, needs):
    return {'op': op, 'status': 'approval_required',
            'result': {'status': 'approval_required', 'action': action, 'needs': list(needs),
                       'written': False},
            'assumptions': ['nothing was opened or written'],
            'limits': ['write actions need approve_write=True' +
                       (' and consent=True' if 'consent' in needs else '')]}


# --------------------------------------------------------------------------- database access

def _db_target(db, allow_private_db):
    """Return ':memory:' or a resolved Path; refuse the owner's private memory."""
    allow_private_db = _bool(allow_private_db, 'allow_private_db')
    if isinstance(db, Path):
        db = str(db)
    db = _str(db, 'db', max_len=1000)
    if db == ':memory:':
        return ':memory:'
    if db.lower().startswith('file:'):
        raise ValueError('db must be a plain file path, not a URI')
    path = Path(db).expanduser().resolve()
    private = PRIVATE_DIR.resolve()
    p_cf, priv_cf = str(path).casefold(), str(private).casefold()
    if (p_cf == priv_cf or p_cf.startswith(priv_cf.rstrip('\\/') + '\\')
            or p_cf.startswith(priv_cf.rstrip('\\/') + '/')) and not allow_private_db:
        raise ValueError('refusing the owner\'s private memory under ~/.red-rose; '
                         'pass allow_private_db=True explicitly to use it')
    if path.is_dir():
        raise ValueError('db must be a file path, not a directory')
    return path


def _connect(target, write):
    """Open a connection; caller must wrap it in contextlib.closing."""
    if target == ':memory:':
        return sqlite3.connect(':memory:')
    if write:
        if not target.parent.is_dir():
            raise ValueError('db parent folder does not exist (it is never created here)')
        return sqlite3.connect(str(target), timeout=5)
    if not target.is_file():
        raise ValueError('db file does not exist')
    return sqlite3.connect(target.as_uri() + '?mode=ro', uri=True, timeout=5)


def _has_table(conn, name):
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type IN ('table','view') AND name=?",
                        (name,)).fetchone() is not None


_SCHEMA = {
    'sources': [
        'CREATE TABLE IF NOT EXISTS sources(id INTEGER PRIMARY KEY, source TEXT NOT NULL, '
        'licence TEXT NOT NULL, url_or_path TEXT NOT NULL, revision TEXT NOT NULL, '
        'sha256 TEXT NOT NULL, text TEXT NOT NULL, created TEXT NOT NULL, updated TEXT NOT NULL)',
        "CREATE VIRTUAL TABLE IF NOT EXISTS sources_fts USING fts5(body, tokenize='unicode61')",
    ],
    'owner': [
        'CREATE TABLE IF NOT EXISTS owner_instructions(id INTEGER PRIMARY KEY, created TEXT NOT NULL, '
        'scope TEXT NOT NULL, instruction TEXT NOT NULL, sha256 TEXT NOT NULL, consent INTEGER NOT NULL)',
    ],
    'errors': [
        'CREATE TABLE IF NOT EXISTS error_memory(id INTEGER PRIMARY KEY, key TEXT NOT NULL, '
        'version INTEGER NOT NULL, cause TEXT NOT NULL, fix TEXT NOT NULL, evidence TEXT NOT NULL, '
        'reason TEXT, created TEXT NOT NULL, superseded_by INTEGER, UNIQUE(key, version))',
    ],
    'refs': [
        'CREATE TABLE IF NOT EXISTS reference_values(id INTEGER PRIMARY KEY, ref_key TEXT NOT NULL, '
        'value_json TEXT NOT NULL, source TEXT NOT NULL, origin TEXT NOT NULL, created TEXT NOT NULL)',
    ],
    'receipts': [
        'CREATE TABLE IF NOT EXISTS search_receipts(id INTEGER PRIMARY KEY, created TEXT NOT NULL, '
        'query TEXT NOT NULL, normalised_query TEXT NOT NULL, mode TEXT NOT NULL, lim INTEGER NOT NULL, '
        'result_ids TEXT NOT NULL, result_hashes TEXT NOT NULL, db_revision TEXT NOT NULL)',
    ],
    'migrations': [
        'CREATE TABLE IF NOT EXISTS schema_migrations(name TEXT PRIMARY KEY, applied TEXT NOT NULL, '
        'sql_sha256 TEXT NOT NULL)',
    ],
    'workspace': [
        'CREATE TABLE IF NOT EXISTS workspace_records(id INTEGER PRIMARY KEY, workspace TEXT NOT NULL, '
        'key TEXT NOT NULL, value TEXT NOT NULL, created TEXT NOT NULL)',
        'CREATE INDEX IF NOT EXISTS workspace_records_ws ON workspace_records(workspace, key)',
    ],
}


def _ensure(conn, which):
    for sql in _SCHEMA[which]:
        conn.execute(sql)


# --------------------------------------------------------------------------- normalisation

_ARABIC_MAP = str.maketrans({
    'أ': 'ا', 'إ': 'ا', 'آ': 'ا', 'ٱ': 'ا', 'ى': 'ي', 'ة': 'ه', 'ؤ': 'و', 'ئ': 'ي',
    'ـ': None,
    **{chr(0x0660 + i): str(i) for i in range(10)},
    **{chr(0x06F0 + i): str(i) for i in range(10)},
})
_TOKEN_RE = re.compile(r'\w+')


def normalise(text):
    """Light Arabic + English normalisation used for both index and query."""
    text = unicodedata.normalize('NFKC', text)
    text = ''.join(ch for ch in text if unicodedata.category(ch) != 'Mn')
    text = text.translate(_ARABIC_MAP).casefold()
    return ' '.join(_TOKEN_RE.findall(text))


def _fts_query(norm, mode):
    tokens = norm.split()
    if not tokens:
        raise ValueError('query has no searchable words')
    quoted = ['"' + t.replace('"', '""') + '"' for t in tokens[:32]]
    return (' OR ' if mode == 'any' else ' ').join(quoted)


def _db_revision(conn):
    h = hashlib.sha256()
    if _has_table(conn, 'sources'):
        for doc_id, sha in conn.execute('SELECT id, sha256 FROM sources ORDER BY id'):
            h.update(f'{doc_id}:{sha}\n'.encode())
    return h.hexdigest()


def _search(conn, norm, mode, limit):
    if not (_has_table(conn, 'sources') and _has_table(conn, 'sources_fts')):
        return []
    rows = conn.execute(
        'SELECT s.id, s.source, s.licence, s.url_or_path, s.revision, s.sha256, s.text, '
        'bm25(sources_fts) FROM sources_fts JOIN sources s ON s.id = sources_fts.rowid '
        'WHERE sources_fts MATCH ? ORDER BY bm25(sources_fts), s.id LIMIT ?',
        (_fts_query(norm, mode), limit)).fetchall()
    return [{'id': r[0], 'source': r[1], 'licence': r[2], 'url_or_path': r[3], 'revision': r[4],
             'sha256': r[5], 'snippet': r[6][:200], 'score': round(-r[7], 6)} for r in rows]


# --------------------------------------------------------------------------- 12.01 index_source

def index_source(*, db=':memory:', action='add', source=None, licence=None, url_or_path=None,
                 revision=None, text=None, doc_id=None, approve_write=False,
                 allow_private_db=False, **extra):
    """Store licensed documents with provenance and retrieve them hash-verified.

    action 'add' (write): source, licence (SPDX id), url_or_path, revision, text.
    action 'revise' (write): doc_id, text, revision -> replaces the stored text.
    action 'get' (read): doc_id -> original text, stored and recomputed sha256.
    """
    _no_extra(extra)
    action = _choice(action, {'add', 'revise', 'get'}, 'action')
    approve_write = _bool(approve_write, 'approve_write')
    target = _db_target(db, allow_private_db)
    if action in ('revise', 'get'):
        doc_id = _int(doc_id, 1, 2**62, 'doc_id')
    if action in ('add', 'revise'):
        text = _str(text, 'text', max_len=MAX_TEXT)
        revision = _str(revision, 'revision')
    if action == 'add':
        source = _str(source, 'source')
        if not isinstance(licence, str) or licence not in SPDX_LICENCES:
            raise ValueError('licence must be a known SPDX identifier, e.g. MIT, Apache-2.0, '
                             'CC-BY-4.0 (or LicenseRef-Owner for the owner\'s own text)')
        url_or_path = _str(url_or_path, 'url_or_path', max_len=2000)
    assumptions = ['sha256 is computed over the UTF-8 encoding of the exact text supplied',
                   'licence is checked against a fixed SPDX allow-list, not against the source itself']
    limits = [f'text <= {MAX_TEXT} characters', 'the text is stored verbatim inside the database file']
    if action == 'get':
        with closing(_connect(target, write=False)) as conn:
            row = (conn.execute('SELECT id, source, licence, url_or_path, revision, sha256, text, '
                                'created, updated FROM sources WHERE id=?', (doc_id,)).fetchone()
                   if _has_table(conn, 'sources') else None)
        if row is None:
            return _pack('index_source', {'action': 'get', 'found': False, 'id': doc_id},
                         assumptions, limits)
        actual = _sha(row[6])
        return _pack('index_source', {
            'action': 'get', 'found': True, 'id': row[0], 'source': row[1], 'licence': row[2],
            'url_or_path': row[3], 'revision': row[4], 'sha256': row[5], 'text': row[6],
            'recomputed_sha256': actual, 'hash_ok': actual == row[5],
            'created': row[7], 'updated': row[8]}, assumptions, limits)
    if not approve_write:
        return _approval('index_source', action, ['approve_write'])
    sha = _sha(text)
    with closing(_connect(target, write=True)) as conn:
        with conn:
            _ensure(conn, 'sources')
            if action == 'add':
                dup = conn.execute('SELECT id FROM sources WHERE source=? AND revision=? AND sha256=?',
                                   (source, revision, sha)).fetchone()
                if dup:
                    return _pack('index_source', {'action': 'add', 'id': dup[0], 'sha256': sha,
                                                  'duplicate': True, 'written': False},
                                 assumptions, limits)
                ts = _now()
                cur = conn.execute('INSERT INTO sources(source, licence, url_or_path, revision, sha256, '
                                   'text, created, updated) VALUES(?,?,?,?,?,?,?,?)',
                                   (source, licence, url_or_path, revision, sha, text, ts, ts))
                new_id = cur.lastrowid
                conn.execute('INSERT INTO sources_fts(rowid, body) VALUES(?, ?)',
                             (new_id, normalise(text)))
                result = {'action': 'add', 'id': new_id, 'sha256': sha, 'duplicate': False,
                          'written': True}
            else:
                old = conn.execute('SELECT sha256 FROM sources WHERE id=?', (doc_id,)).fetchone()
                if old is None:
                    raise ValueError(f'doc_id {doc_id} does not exist')
                conn.execute('UPDATE sources SET text=?, sha256=?, revision=?, updated=? WHERE id=?',
                             (text, sha, revision, _now(), doc_id))
                conn.execute('DELETE FROM sources_fts WHERE rowid=?', (doc_id,))
                conn.execute('INSERT INTO sources_fts(rowid, body) VALUES(?, ?)',
                             (doc_id, normalise(text)))
                result = {'action': 'revise', 'id': doc_id, 'old_sha256': old[0], 'sha256': sha,
                          'written': True}
    return _pack('index_source', result, assumptions,
                 limits + ['revise overwrites the stored text; keep older revisions as separate add rows '
                           'if history matters'])


# --------------------------------------------------------------------------- 12.02 search_fts

def search_fts(*, db=':memory:', query=None, mode='all', limit=10, allow_private_db=False,
               **extra):
    """BM25-ranked FTS5 search over documents stored by index_source (read-only)."""
    _no_extra(extra)
    query = _str(query, 'query', max_len=MAX_QUERY)
    mode = _choice(mode, {'all', 'any'}, 'mode')
    limit = _int(limit, 1, 100, 'limit')
    target = _db_target(db, allow_private_db)
    norm = normalise(query)
    fts = _fts_query(norm, mode)
    with closing(_connect(target, write=False)) as conn:
        hits = _search(conn, norm, mode, limit)
        rev = _db_revision(conn)
    return _pack('search_fts', {'query': query, 'normalised_query': norm, 'fts_expression': fts,
                                'mode': mode, 'hits': hits, 'count': len(hits),
                                'db_revision': rev},
                 ['Arabic: diacritics (Mn) and tatweel removed; أ/إ/آ/ٱ->ا, ى->ي, ة->ه, ؤ->و, ئ->ي; '
                  'Arabic-Indic digits -> ASCII. English: Unicode casefold. Same rules for index and query',
                  'score = -bm25 (higher is better); ties broken by document id',
                  'no stemming, no root extraction, no synonym or dialect dictionary'],
                 ['query <= 500 characters, first 32 words used, limit <= 100',
                  'mode all = every word must appear; any = at least one word',
                  'prefix/clitic forms (e.g. وال، بال) are not split, so they do not match the bare word'])


# --------------------------------------------------------------------------- 12.03 legacy_summaries

_CODE_HINT = re.compile(r'\b(import\s+\w+|from\s+\S+\s+import|os\.system|popen|__import__)\b')
_LEGACY_COLS = ('id', 'title', 'summary', 'origin', 'licence')


def legacy_summaries(*, db=None, table='summaries', contains=None, limit=50, offset=0,
                     allow_private_db=False, **extra):
    """Read-only listing of a legacy summaries table (id,title,summary,origin,licence)."""
    _no_extra(extra)
    if db is None:
        raise ValueError('db is required (path to the legacy summaries database)')
    target = _db_target(db, allow_private_db)
    if not isinstance(table, str) or not _IDENT_RE.match(table):
        raise ValueError('table must be a plain SQL identifier')
    if contains is not None:
        contains = _str(contains, 'contains', max_len=200)
    limit = _int(limit, 1, 500, 'limit')
    offset = _int(offset, 0, 10**9, 'offset')
    with closing(_connect(target, write=False)) as conn:
        if not _has_table(conn, table):
            raise ValueError(f'table {table!r} not found in db')
        cols = {r[1] for r in conn.execute(f'PRAGMA table_info("{table}")')}
        missing = [c for c in _LEGACY_COLS if c not in cols]
        if missing:
            raise ValueError('legacy table is missing column(s): ' + ', '.join(missing))
        sql = f'SELECT id, title, summary, origin, licence FROM "{table}"'
        args = []
        if contains is not None:
            sql += ' WHERE title LIKE ? OR summary LIKE ?'
            args += [f'%{contains}%', f'%{contains}%']
        sql += ' ORDER BY id LIMIT ? OFFSET ?'
        rows = conn.execute(sql, args + [limit, offset]).fetchall()
        total = conn.execute(f'SELECT count(*) FROM "{table}"').fetchone()[0]
    items = []
    for r in rows:
        vals = ['' if v is None else (v if isinstance(v, (int, float)) and not isinstance(v, bool)
                                      else str(v)) for v in r]
        items.append({'id': vals[0], 'title': vals[1], 'summary': vals[2], 'origin': vals[3],
                      'licence': vals[4], 'executable': False,
                      'mentions_code': bool(_CODE_HINT.search(f'{vals[1]} {vals[2]}'))})
    return _pack('legacy_summaries', {'table': table, 'total_rows': total, 'items': items,
                                      'count': len(items), 'opened_read_only': target != ':memory:'},
                 ['rows are knowledge descriptions (metadata), never executable skills',
                  'nothing referenced by a row (modules, paths, commands) is imported, opened or run',
                  'mentions_code is a regex hint only'],
                 ['the database is opened with SQLite URI mode=ro', 'limit <= 500 rows per call',
                  'BLOB values are returned as their str() representation'])


# --------------------------------------------------------------------------- 12.04 owner_instructions

def owner_instructions(*, db=':memory:', action='save', instruction=None, scope='general',
                       contains=None, limit=50, consent=False, approve_write=False,
                       allow_private_db=False, **extra):
    """Private store of owner instructions: save (needs approve_write AND consent) / recall."""
    _no_extra(extra)
    action = _choice(action, {'save', 'recall'}, 'action')
    approve_write = _bool(approve_write, 'approve_write')
    consent = _bool(consent, 'consent')
    target = _db_target(db, allow_private_db)
    scope = _str(scope, 'scope', max_len=100)
    limit = _int(limit, 1, 500, 'limit')
    assumptions = ['instructions are stored verbatim in the caller-chosen SQLite file',
                   'consent=True records that the owner explicitly agreed to keep this instruction']
    limits = ['no encryption at rest; protect the database file itself',
              'never commit this database to version control']
    if action == 'recall':
        if contains is not None:
            contains = _str(contains, 'contains', max_len=200)
        with closing(_connect(target, write=False)) as conn:
            rows = []
            if _has_table(conn, 'owner_instructions'):
                sql = 'SELECT id, created, scope, instruction, sha256 FROM owner_instructions WHERE scope=?'
                args = [scope]
                if contains is not None:
                    sql += ' AND instruction LIKE ?'
                    args.append(f'%{contains}%')
                rows = conn.execute(sql + ' ORDER BY id DESC LIMIT ?', args + [limit]).fetchall()
        items = [{'id': r[0], 'created': r[1], 'scope': r[2], 'instruction': r[3], 'sha256': r[4],
                  'hash_ok': _sha(r[3]) == r[4]} for r in rows]
        return _pack('owner_instructions', {'action': 'recall', 'items': items, 'count': len(items)},
                     assumptions, limits)
    instruction = _str(instruction, 'instruction', max_len=20_000)
    needs = [n for n, ok in (('approve_write', approve_write), ('consent', consent)) if not ok]
    if needs:
        return _approval('owner_instructions', 'save', needs)
    sha = _sha(instruction)
    with closing(_connect(target, write=True)) as conn:
        with conn:
            _ensure(conn, 'owner')
            cur = conn.execute('INSERT INTO owner_instructions(created, scope, instruction, sha256, consent) '
                               'VALUES(?,?,?,?,1)', (_now(), scope, instruction, sha))
    return _pack('owner_instructions', {'action': 'save', 'id': cur.lastrowid, 'sha256': sha,
                                        'written': True}, assumptions, limits)


# --------------------------------------------------------------------------- 12.05 error_memory

def error_memory(*, db=':memory:', action='record', key=None, cause=None, fix=None, evidence=None,
                 reason=None, history=False, approve_write=False, allow_private_db=False, **extra):
    """Versioned error records: record / correct (new version supersedes old) / get."""
    _no_extra(extra)
    action = _choice(action, {'record', 'correct', 'get'}, 'action')
    approve_write = _bool(approve_write, 'approve_write')
    history = _bool(history, 'history')
    target = _db_target(db, allow_private_db)
    key = _str(key, 'key')
    assumptions = ['a correction never deletes: the old version stays, marked superseded_by',
                   'the latest (unsuperseded) version is the current truth']
    limits = ['cause/fix/evidence <= 20000 characters each', 'no automatic verification of evidence']

    def rows_for(conn):
        if not _has_table(conn, 'error_memory'):
            return []
        return conn.execute('SELECT id, key, version, cause, fix, evidence, reason, created, superseded_by '
                            'FROM error_memory WHERE key=? ORDER BY version', (key,)).fetchall()

    def as_dict(r):
        return {'id': r[0], 'key': r[1], 'version': r[2], 'cause': r[3], 'fix': r[4],
                'evidence': r[5], 'reason': r[6], 'created': r[7], 'superseded_by': r[8],
                'current': r[8] is None}

    if action == 'get':
        with closing(_connect(target, write=False)) as conn:
            rows = rows_for(conn)
        if not rows:
            return _pack('error_memory', {'action': 'get', 'found': False, 'key': key},
                         assumptions, limits)
        res = {'action': 'get', 'found': True, 'key': key, 'latest': as_dict(rows[-1]),
               'versions': len(rows)}
        if history:
            res['history'] = [as_dict(r) for r in rows]
        return _pack('error_memory', res, assumptions, limits)
    cause = _str(cause, 'cause', max_len=20_000)
    fix = _str(fix, 'fix', max_len=20_000)
    evidence = _str(evidence, 'evidence', max_len=20_000)
    if action == 'correct':
        reason = _str(reason, 'reason', max_len=2000)
    elif reason is not None:
        raise ValueError('reason is only used with action=correct')
    if not approve_write:
        return _approval('error_memory', action, ['approve_write'])
    with closing(_connect(target, write=True)) as conn:
        with conn:
            _ensure(conn, 'errors')
            rows = rows_for(conn)
            if action == 'record' and rows:
                raise ValueError(f'key {key!r} already exists; use action=correct')
            if action == 'correct' and not rows:
                raise ValueError(f'key {key!r} does not exist; use action=record')
            version = rows[-1][2] + 1 if rows else 1
            cur = conn.execute('INSERT INTO error_memory(key, version, cause, fix, evidence, reason, created) '
                               'VALUES(?,?,?,?,?,?,?)', (key, version, cause, fix, evidence, reason, _now()))
            if rows:
                conn.execute('UPDATE error_memory SET superseded_by=? WHERE id=?', (cur.lastrowid, rows[-1][0]))
    return _pack('error_memory', {'action': action, 'key': key, 'id': cur.lastrowid, 'version': version,
                                  'supersedes': rows[-1][0] if rows else None, 'written': True},
                 assumptions, limits)


# --------------------------------------------------------------------------- 12.06 reference_conflicts

def reference_conflicts(*, db=':memory:', action='add', ref_key=None, value=None, source=None,
                        origin=None, approve_write=False, allow_private_db=False, **extra):
    """Store per-source values of a reference key; report keys whose sources disagree."""
    _no_extra(extra)
    action = _choice(action, {'add', 'report'}, 'action')
    approve_write = _bool(approve_write, 'approve_write')
    target = _db_target(db, allow_private_db)
    assumptions = ['values are compared by canonical JSON (sorted keys); 3 and 3.0 count as equal',
                   'a conflict means two or more distinct values for the same ref_key',
                   'no source is preferred here; use trust_score to rank them']
    limits = ['value must be JSON (string, number, bool, null, list, dict) <= 10000 characters',
              'report returns at most 200 keys']
    if action == 'report':
        if ref_key is not None:
            ref_key = _str(ref_key, 'ref_key')
        with closing(_connect(target, write=False)) as conn:
            rows = []
            if _has_table(conn, 'reference_values'):
                sql = 'SELECT ref_key, value_json, source, origin, created, id FROM reference_values'
                args = []
                if ref_key is not None:
                    sql += ' WHERE ref_key=?'
                    args.append(ref_key)
                rows = conn.execute(sql + ' ORDER BY ref_key, id', args).fetchall()
        keys = {}
        for k, vj, src, org, created, rid in rows:
            keys.setdefault(k, {}).setdefault(vj, []).append(
                {'id': rid, 'source': src, 'origin': org, 'created': created})
        conflicts, consistent = [], []
        for k, by_val in keys.items():
            entry = {'ref_key': k, 'values': [{'value': json.loads(vj), 'sources': srcs}
                                              for vj, srcs in by_val.items()]}
            (conflicts if len(by_val) > 1 else consistent).append(entry)
        return _pack('reference_conflicts', {'action': 'report', 'conflicts': conflicts[:200],
                                             'consistent': consistent[:200],
                                             'conflict_count': len(conflicts)}, assumptions, limits)
    ref_key = _str(ref_key, 'ref_key')
    source = _str(source, 'source')
    origin = _str(origin, 'origin', max_len=2000)
    try:
        value_json = json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError):
        raise ValueError('value must be JSON-serialisable (no NaN/Infinity)') from None
    if value is None:
        raise ValueError('value is required')
    if isinstance(value, float) and value.is_integer():
        value_json = json.dumps(int(value))
    if len(value_json) > 10_000:
        raise ValueError('value is too large')
    if not approve_write:
        return _approval('reference_conflicts', 'add', ['approve_write'])
    with closing(_connect(target, write=True)) as conn:
        with conn:
            _ensure(conn, 'refs')
            cur = conn.execute('INSERT INTO reference_values(ref_key, value_json, source, origin, created) '
                               'VALUES(?,?,?,?,?)', (ref_key, value_json, source, origin, _now()))
    return _pack('reference_conflicts', {'action': 'add', 'id': cur.lastrowid, 'ref_key': ref_key,
                                         'written': True}, assumptions, limits)


# --------------------------------------------------------------------------- 12.07 trust_score

_TIER_WEIGHT = {'primary': 0.5, 'secondary': 0.3, 'tertiary': 0.15, 'unknown': 0.05}
_TEST_STATES = {'passed', 'failed', 'none'}
_REF_KEYS = {'id', 'source_tier', 'date', 'original_text', 'summary', 'test'}


def trust_score(*, references=None, as_of=None, half_life_years=3.0, **extra):
    """Score references by tier, age and test evidence; refuse summary-only references.

    score = tier (primary .5, secondary .3, tertiary .15, unknown .05)
          + 0.3 * 0.5 ** (age_years / half_life_years)
          + 0.2 if test == 'passed'; a failed test multiplies the total by 0.25.
    """
    _no_extra(extra)
    if not isinstance(references, list) or not 1 <= len(references) <= 200:
        raise ValueError('references must be a list of 1..200 objects')
    as_of_date = datetime.now(timezone.utc).date() if as_of is None else _date(as_of, 'as_of')
    half_life = _num(half_life_years, 0.25, 50, 'half_life_years')
    admitted, rejected, seen = [], [], set()
    for i, ref in enumerate(references):
        if not isinstance(ref, dict):
            raise ValueError(f'references[{i}] must be an object')
        unknown = set(ref) - _REF_KEYS
        if unknown:
            raise ValueError(f'references[{i}] has unknown key(s): {", ".join(sorted(map(str, unknown)))}')
        rid = _str(ref.get('id'), f'references[{i}].id')
        if rid in seen:
            raise ValueError(f'duplicate reference id {rid!r}')
        seen.add(rid)
        tier = _choice(ref.get('source_tier', 'unknown'), set(_TIER_WEIGHT), f'references[{i}].source_tier')
        test = _choice(ref.get('test', 'none'), _TEST_STATES, f'references[{i}].test')
        when = _date(ref.get('date'), f'references[{i}].date')
        text = ref.get('original_text')
        if text is not None:
            text = _str(text, f'references[{i}].original_text', max_len=MAX_TEXT, allow_empty=True)
        if 'summary' in ref and ref['summary'] is not None:
            _str(ref['summary'], f'references[{i}].summary', max_len=MAX_TEXT, allow_empty=True)
        if not text or not text.strip():
            rejected.append({'id': rid, 'reason': 'original text missing (summary only) - not admitted'})
            continue
        age_days = (as_of_date - when).days
        future = age_days < 0
        age_years = max(0, age_days) / 365.25
        recency = 0.3 * 0.5 ** (age_years / half_life)
        test_part = 0.2 if test == 'passed' else 0.0
        score = _TIER_WEIGHT[tier] + recency + test_part
        if test == 'failed':
            score *= 0.25
        admitted.append({'id': rid, 'score': round(score, 6), 'tier': tier, 'tier_part': _TIER_WEIGHT[tier],
                         'recency_part': round(recency, 6), 'test': test, 'test_part': test_part,
                         'age_days': age_days, 'future_dated': future,
                         'original_text_sha256': _sha(text)})
    admitted.sort(key=lambda r: (-r['score'], r['id']))
    return _pack('trust_score', {'as_of': as_of_date.isoformat(), 'half_life_years': half_life,
                                 'admitted': admitted, 'rejected': rejected},
                 ['weights are a fixed editorial heuristic, not a calibrated probability',
                  'test evidence is taken as declared by the caller; it is not re-run here',
                  'future-dated references are treated as age 0 and flagged'],
                 ['score in [0, 1]', '<= 200 references per call',
                  'a reference without non-empty original_text is never admitted'])


# --------------------------------------------------------------------------- 12.08 search_receipt

def search_receipt(*, db=':memory:', action='save', query=None, mode='all', limit=10,
                   receipt_id=None, approve_write=False, allow_private_db=False, **extra):
    """Save an auditable search receipt, or replay one and explain any difference."""
    _no_extra(extra)
    action = _choice(action, {'save', 'replay'}, 'action')
    approve_write = _bool(approve_write, 'approve_write')
    target = _db_target(db, allow_private_db)
    assumptions = ['a receipt stores query, normalised query, ordered result ids, their sha256 '
                   'and a database revision (sha256 over all document ids and hashes)',
                   'replay re-runs the same normalised query with the same mode and limit']
    limits = ['replay is only as strong as the stored document hashes; scores are not compared',
              'documents changed outside index_source are still detected through their sha256 only if '
              'the stored sha256 column was updated too']
    if action == 'replay':
        receipt_id = _int(receipt_id, 1, 2**62, 'receipt_id')
        with closing(_connect(target, write=False)) as conn:
            row = (conn.execute('SELECT query, normalised_query, mode, lim, result_ids, result_hashes, '
                                'db_revision, created FROM search_receipts WHERE id=?',
                                (receipt_id,)).fetchone()
                   if _has_table(conn, 'search_receipts') else None)
            if row is None:
                raise ValueError(f'receipt {receipt_id} not found')
            hits = _search(conn, row[1], row[2], row[3])
            rev = _db_revision(conn)
            live_text_hash = {}
            for h in hits:
                t = conn.execute('SELECT text FROM sources WHERE id=?', (h['id'],)).fetchone()
                live_text_hash[h['id']] = _sha(t[0]) if t else None
        old_ids, old_hashes = json.loads(row[4]), json.loads(row[5])
        new_ids = [h['id'] for h in hits]
        new_hashes = [h['sha256'] for h in hits]
        reasons = []
        if rev != row[6]:
            reasons.append(f'database revision changed ({row[6][:12]} -> {rev[:12]})')
        if new_ids != old_ids:
            reasons.append(f'result ids differ: {old_ids} -> {new_ids}')
        new_map = dict(zip(new_ids, new_hashes))
        for did, old_h in zip(old_ids, old_hashes):
            if did not in new_map:
                reasons.append(f'document {did} is no longer in the results')
            elif new_map[did] != old_h:
                reasons.append(f'document {did} text changed: sha256 {old_h[:12]} -> {new_map[did][:12]}')
        for did, h in new_map.items():
            if live_text_hash.get(did) != h:
                reasons.append(f'document {did} stored text does not match its stored sha256')
        return _pack('search_receipt', {
            'action': 'replay', 'receipt_id': receipt_id, 'query': row[0], 'normalised_query': row[1],
            'replay_ok': not reasons, 'reasons': reasons, 'recorded_ids': old_ids,
            'recorded_hashes': old_hashes, 'replayed_ids': new_ids, 'replayed_hashes': new_hashes,
            'recorded_db_revision': row[6], 'current_db_revision': rev, 'recorded_at': row[7]},
            assumptions, limits)
    query = _str(query, 'query', max_len=MAX_QUERY)
    mode = _choice(mode, {'all', 'any'}, 'mode')
    limit = _int(limit, 1, 100, 'limit')
    norm = normalise(query)
    _fts_query(norm, mode)
    if receipt_id is not None:
        raise ValueError('receipt_id is only used with action=replay')
    if not approve_write:
        return _approval('search_receipt', 'save', ['approve_write'])
    with closing(_connect(target, write=True)) as conn:
        with conn:
            hits = _search(conn, norm, mode, limit)
            rev = _db_revision(conn)
            ids = [h['id'] for h in hits]
            hashes = [h['sha256'] for h in hits]
            _ensure(conn, 'receipts')
            cur = conn.execute('INSERT INTO search_receipts(created, query, normalised_query, mode, lim, '
                               'result_ids, result_hashes, db_revision) VALUES(?,?,?,?,?,?,?,?)',
                               (_now(), query, norm, mode, limit, json.dumps(ids), json.dumps(hashes), rev))
    return _pack('search_receipt', {'action': 'save', 'receipt_id': cur.lastrowid, 'query': query,
                                    'normalised_query': norm, 'result_ids': ids, 'result_hashes': hashes,
                                    'db_revision': rev, 'written': True}, assumptions, limits)


# --------------------------------------------------------------------------- 12.09 migrate_memory

_ALLOWED_SQL = re.compile(r'^\s*(CREATE\s+(TABLE|INDEX|UNIQUE\s+INDEX|VIEW)|ALTER\s+TABLE|INSERT\s+INTO|UPDATE)\b',
                          re.IGNORECASE)
_FORBIDDEN_SQL = re.compile(r'\b(ATTACH|DETACH|PRAGMA|VACUUM|DROP|DELETE|load_extension|RENAME)\b',
                            re.IGNORECASE)


def _canon(v):
    if isinstance(v, bytes):
        return {'blob': v.hex()}
    return v


def _snapshot(conn):
    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' "
        "AND sql NOT LIKE 'CREATE VIRTUAL TABLE%' ORDER BY name")]
    out, total = {}, 0
    for t in tables:
        rows = conn.execute(f'SELECT * FROM "{t}"').fetchall()
        total += len(rows)
        if total > MAX_ROWS_CHECKSUM:
            raise ValueError(f'database has more than {MAX_ROWS_CHECKSUM} rows; too large to checksum')
        lines = sorted(json.dumps([_canon(v) for v in r], ensure_ascii=False, sort_keys=True) for r in rows)
        h = hashlib.sha256()
        for line in lines:
            h.update(line.encode('utf-8') + b'\n')
        out[t] = {'rows': len(rows), 'sha256': h.hexdigest()}
    return out


def migrate_memory(*, db=':memory:', migrations=None, simulate_failure_after=None,
                   approve_write=False, allow_private_db=False, **extra):
    """Apply named SQL migrations in one BEGIN IMMEDIATE transaction; roll back on any error.

    migrations: [{'name': str, 'sql': [statement, ...]}]. Allowed statements:
    CREATE TABLE/INDEX/VIEW, ALTER TABLE ... ADD, INSERT INTO, UPDATE.
    Destructive statements (DROP, DELETE, RENAME, ATTACH, PRAGMA, VACUUM) are refused.
    After applying, any pre-existing table that lost rows triggers a rollback.
    simulate_failure_after=N raises an injected error after N migrations (for testing).
    """
    _no_extra(extra)
    approve_write = _bool(approve_write, 'approve_write')
    target = _db_target(db, allow_private_db)
    if not isinstance(migrations, list) or not 1 <= len(migrations) <= 50:
        raise ValueError('migrations must be a list of 1..50 objects')
    plan, names = [], set()
    for i, m in enumerate(migrations):
        if not isinstance(m, dict) or set(m) != {'name', 'sql'}:
            raise ValueError(f'migrations[{i}] must be {{"name": str, "sql": [str, ...]}}')
        name = _str(m['name'], f'migrations[{i}].name')
        if name in names:
            raise ValueError(f'duplicate migration name {name!r}')
        names.add(name)
        stmts = m['sql']
        if isinstance(stmts, str):
            stmts = [stmts]
        if not isinstance(stmts, list) or not 1 <= len(stmts) <= 50:
            raise ValueError(f'migrations[{i}].sql must be 1..50 statements')
        clean = []
        for j, s in enumerate(stmts):
            s = _str(s, f'migrations[{i}].sql[{j}]', max_len=20_000).strip().rstrip(';').strip()
            if ';' in s:
                raise ValueError(f'migrations[{i}].sql[{j}] must be a single statement')
            if not _ALLOWED_SQL.match(s) or _FORBIDDEN_SQL.search(s):
                raise ValueError(f'migrations[{i}].sql[{j}] is not an allowed non-destructive statement')
            clean.append(s)
        plan.append((name, clean, _sha('\n'.join(clean))))
    if simulate_failure_after is not None:
        simulate_failure_after = _int(simulate_failure_after, 0, len(plan), 'simulate_failure_after')
    if not approve_write:
        return _approval('migrate_memory', 'migrate', ['approve_write'])
    assumptions = ['all migrations run inside one BEGIN IMMEDIATE transaction (all or nothing)',
                   'checksums: sha256 over each table\'s rows, sorted, as canonical JSON',
                   'migrations already recorded in schema_migrations are skipped']
    limits = ['virtual (FTS) tables are excluded from counts/checksums; their shadow tables are included',
              f'checksumming reads every row (<= {MAX_ROWS_CHECKSUM} rows total)',
              'statement filtering is a keyword allow-list, not a full SQL parser']
    conn = _connect(target, write=True)
    conn.isolation_level = None
    with closing(conn):
        before = _snapshot(conn)
        applied, skipped = [], []
        conn.execute('BEGIN IMMEDIATE')
        try:
            _ensure(conn, 'migrations')
            for k, (name, stmts, digest) in enumerate(plan):
                if simulate_failure_after is not None and k == simulate_failure_after:
                    raise RuntimeError(f'injected failure before migration {name!r}')
                if conn.execute('SELECT 1 FROM schema_migrations WHERE name=?', (name,)).fetchone():
                    skipped.append(name)
                    continue
                for s in stmts:
                    conn.execute(s)
                conn.execute('INSERT INTO schema_migrations(name, applied, sql_sha256) VALUES(?,?,?)',
                             (name, _now(), digest))
                applied.append(name)
            if simulate_failure_after is not None and simulate_failure_after == len(plan):
                raise RuntimeError('injected failure after the last migration')
            mid = _snapshot(conn)
            lost = [t for t, info in before.items() if t not in mid or mid[t]['rows'] < info['rows']]
            if lost:
                raise RuntimeError('row loss detected in: ' + ', '.join(lost))
            conn.execute('COMMIT')
            status, error = 'committed', None
        except (sqlite3.Error, RuntimeError) as exc:
            conn.execute('ROLLBACK')
            status, error = 'rolled_back', f'{type(exc).__name__}: {exc}'
            applied = []
        after = _snapshot(conn)
    unchanged = before == after
    return _pack('migrate_memory', {'status': status, 'error': error, 'applied': applied,
                                    'skipped': skipped if status == 'committed' else [],
                                    'before': before, 'after': after,
                                    'unchanged': unchanged, 'written': status == 'committed'},
                 assumptions, limits)


# --------------------------------------------------------------------------- 12.10 workspace_isolation

def workspace_isolation(*, db=':memory:', action='put', workspace=None, key=None, value=None,
                        record_id=None, limit=100, approve_write=False, allow_private_db=False, **extra):
    """Records scoped by workspace: put (write) / get / list; every query filters by workspace."""
    _no_extra(extra)
    action = _choice(action, {'put', 'get', 'list'}, 'action')
    approve_write = _bool(approve_write, 'approve_write')
    workspace = _workspace(workspace)
    target = _db_target(db, allow_private_db)
    limit = _int(limit, 1, 1000, 'limit')
    assumptions = ['every SQL statement includes WHERE workspace = ? (no unscoped query path exists)',
                   'a record of another workspace is reported as not found, without revealing that it exists']
    limits = ['isolation is logical inside one SQLite file, not separate files or encryption',
              'workspace ids are caller-asserted; authentication is out of scope']
    if action == 'put':
        key = _str(key, 'key')
        value = _str(value, 'value', max_len=100_000)
        if record_id is not None:
            raise ValueError('record_id is not used with action=put')
        if not approve_write:
            return _approval('workspace_isolation', 'put', ['approve_write'])
        with closing(_connect(target, write=True)) as conn:
            with conn:
                _ensure(conn, 'workspace')
                cur = conn.execute('INSERT INTO workspace_records(workspace, key, value, created) '
                                   'VALUES(?,?,?,?)', (workspace, key, value, _now()))
        return _pack('workspace_isolation', {'action': 'put', 'workspace': workspace, 'id': cur.lastrowid,
                                             'written': True}, assumptions, limits)
    if action == 'get':
        if record_id is None and key is None:
            raise ValueError('get needs record_id or key')
        if record_id is not None:
            record_id = _int(record_id, 1, 2**62, 'record_id')
        if key is not None:
            key = _str(key, 'key')
    with closing(_connect(target, write=False)) as conn:
        rows = []
        if _has_table(conn, 'workspace_records'):
            sql = 'SELECT id, workspace, key, value, created FROM workspace_records WHERE workspace=?'
            args = [workspace]
            if action == 'get' and record_id is not None:
                sql += ' AND id=?'
                args.append(record_id)
            if action == 'get' and key is not None:
                sql += ' AND key=?'
                args.append(key)
            rows = conn.execute(sql + ' ORDER BY id LIMIT ?', args + [limit]).fetchall()
    records = [{'id': r[0], 'workspace': r[1], 'key': r[2], 'value': r[3], 'created': r[4]} for r in rows]
    return _pack('workspace_isolation', {'action': action, 'workspace': workspace, 'found': bool(records),
                                         'records': records, 'count': len(records)}, assumptions, limits)


# --------------------------------------------------------------------------- dispatcher

OPS = {
    'index_source': index_source, 'search_fts': search_fts, 'legacy_summaries': legacy_summaries,
    'owner_instructions': owner_instructions, 'error_memory': error_memory,
    'reference_conflicts': reference_conflicts, 'trust_score': trust_score,
    'search_receipt': search_receipt, 'migrate_memory': migrate_memory,
    'workspace_isolation': workspace_isolation,
}


def run(op, params=None):
    """Validate and dispatch: run('search_fts', {'db': path, 'query': 'x'})."""
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
