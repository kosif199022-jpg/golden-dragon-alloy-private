"""Import searchable knowledge descriptions from Golden Dragon Alloy SQLite.

This is an offline data migration, not a runtime call to any earlier skill.
Private entries, credentials and raw binary/skill bodies are NEVER copied.
Descriptions are imported as research data, NOT claimed as executable abilities.
"""
from __future__ import annotations
import hashlib
import re
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

REQUIRED = frozenset({'id','kind','title','summary','license','status','origin','path'})
SECRET = re.compile(
    r"(?i)(?:-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----|"
    r"(?:api[_-]?key|access[_-]?token|password|secret[_-]?key)\s*[:=]\s*\S{8,}|"
    r"(?:ghp_|github_pat_|sk-proj-|sk-)[A-Za-z0-9_-]{12,})"
)
BLOCKED_PARTS = ('owner-memory', '.ssh', 'credentials', 'secrets', 'private-memory', '.env')
BLOCKED_KINDS = {'memory', 'conversation', 'chat'}
BLOCKED_STATUSES = {'private', 'quarantined', 'staged', 'review-before-run'}
MAX_SUMMARY = 1200


def init(db: sqlite3.Connection) -> None:
    db.execute('''CREATE TABLE IF NOT EXISTS fused_knowledge (
        id TEXT PRIMARY KEY, kind TEXT NOT NULL, title TEXT NOT NULL,
        summary TEXT NOT NULL, origin TEXT NOT NULL, license TEXT NOT NULL,
        source_path TEXT NOT NULL, status TEXT NOT NULL,
        sha256 TEXT NOT NULL, imported TEXT NOT NULL)''')
    db.execute('CREATE INDEX IF NOT EXISTS fused_kind_idx ON fused_knowledge(kind)')
    db.commit()


def _eligible(record: sqlite3.Row) -> bool:
    kind = str(record['kind'] or '').lower()
    status = str(record['status'] or '').lower()
    path = str(record['path'] or '').lower().replace('\\', '/')
    origin = str(record['origin'] or '').lower()
    if kind in BLOCKED_KINDS or status in BLOCKED_STATUSES:
        return False
    if any(word in path or word in origin for word in BLOCKED_PARTS):
        return False
    if not str(record['title'] or '').strip():
        return False
    summary = str(record['summary'] or '')
    return not SECRET.search(summary)


def import_alloy(db: sqlite3.Connection, source_db: str | Path, limit: int | None = None) -> dict:
    """Migrate safe descriptions. Does not decompress or run original body blobs."""
    source = Path(source_db).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    if limit is not None and not 1 <= limit <= 100000:
        raise ValueError('limit must be 1..100000')
    init(db)
    stats = {'seen': 0, 'imported': 0, 'updated': 0, 'excluded': 0, 'mode': 'descriptions_only',
             'private_copied': 0, 'source': str(source)}
    with closing(sqlite3.connect(source.as_uri() + '?mode=ro', uri=True)) as old:
        old.row_factory = sqlite3.Row
        columns = {r['name'] for r in old.execute('PRAGMA table_info(units)')}
        if not REQUIRED.issubset(columns):
            raise ValueError('unsupported Alloy schema')
        sql = 'SELECT id,kind,title,summary,path,license,status,origin FROM units ORDER BY id'
        if limit is not None:
            sql += f' LIMIT {int(limit)}'
        for row in old.execute(sql):
            stats['seen'] += 1
            if not _eligible(row):
                stats['excluded'] += 1
                continue
            values = tuple(str(row[k] or '') for k in ('kind','title','summary','origin','license','path','status'))
            kind, title, summary, origin, lic, path, status = values
            summary = summary[:MAX_SUMMARY]
            digest = hashlib.sha256((str(row['id']) + '\x00' + summary).encode('utf-8')).hexdigest()
            existing = db.execute('SELECT sha256 FROM fused_knowledge WHERE id=?', (row['id'],)).fetchone()
            if existing and existing[0] == digest:
                continue
            db.execute('''INSERT INTO fused_knowledge
                (id,kind,title,summary,origin,license,source_path,status,sha256,imported)
                VALUES(?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET
                kind=excluded.kind,title=excluded.title,summary=excluded.summary,
                origin=excluded.origin,license=excluded.license,
                source_path=excluded.source_path,status=excluded.status,
                sha256=excluded.sha256,imported=excluded.imported''',
                (str(row['id']),kind,title,summary,origin,lic,path,status,digest,
                 datetime.now(timezone.utc).isoformat()))
            stats['updated' if existing else 'imported'] += 1
    db.commit()
    stats['total_available'] = db.execute('SELECT COUNT(*) FROM fused_knowledge').fetchone()[0]
    return stats


def find_fused(db: sqlite3.Connection, query: str, limit: int = 20) -> list[dict]:
    init(db)
    if not query.strip():
        raise ValueError('search query required')
    safe = query.replace('\\','\\\\').replace('%','\\%').replace('_','\\_')
    rows = db.execute('''SELECT id, kind, title, summary, origin, license, status FROM fused_knowledge
        WHERE title LIKE ? ESCAPE '\\' OR summary LIKE ? ESCAPE '\\'
        ORDER BY CASE WHEN title LIKE ? ESCAPE '\\' THEN 0 ELSE 1 END, id LIMIT ?''',
        ('%' + safe + '%','%' + safe + '%','%' + safe + '%',max(1,min(int(limit),100)))).fetchall()
    return [dict(zip(('id','kind','title','summary','origin','license','status'),r)) for r in rows]


def stats_fused(db: sqlite3.Connection) -> dict:
    init(db)
    return {'total': db.execute('SELECT COUNT(*) FROM fused_knowledge').fetchone()[0],
            'by_kind': dict(db.execute('SELECT kind, COUNT(*) FROM fused_knowledge GROUP BY kind ORDER BY COUNT(*) DESC')),
            'executable_capabilities_proven': 0}
