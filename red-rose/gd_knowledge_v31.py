"""Import the Golden Dragon knowledge base («قاعدة المعرفة») into Red Rose.

Source: the Golden Dragon app's knowledge runtime, a SQLite file with
`knowledge(id, status, text, payload)` where payload is JSON with `sources`.
It ships as apps/golden-dragon/knowledge/golden-dragon-runtime.zip and is
cached by the app under %APPDATA%/GoldenDragon/knowledge/golden_dragon.sqlite.

This is an offline data migration, not a runtime call into Golden Dragon.
Only `active` records are copied; `quality_review` and `conflict_review`
stay behind. Records that look like secrets or private paths are skipped.
Imported text is reference data, never instructions.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import tempfile
import zipfile
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from alloy_fusion import SECRET, BLOCKED_PARTS, MAX_SUMMARY, init

KIND = 'gd-knowledge'
ORIGIN = 'golden-dragon-knowledge'
DB_NAME = 'golden_dragon.sqlite'
TITLE_MAX = 140


def default_sources() -> list[Path]:
    """Places the knowledge base is known to live on the owner's PC, best first."""
    out = []
    appdata = os.environ.get('APPDATA')
    if appdata:
        out.append(Path(appdata) / 'GoldenDragon' / 'knowledge' / DB_NAME)
    out.append(Path.home() / '.claude' / 'skills' / 'golden-dragon' / 'apps' / 'golden-dragon'
               / 'knowledge' / 'golden-dragon-runtime.zip')
    return out


def find_source() -> Path | None:
    for p in default_sources():
        if p.is_file():
            return p
    return None


def _title(text: str) -> str:
    line = text.strip().splitlines()[0] if text.strip() else ''
    line = line.lstrip('-*# ').strip()
    return (line[:TITLE_MAX - 1] + '…') if len(line) > TITLE_MAX else line


def _first_source(payload: dict) -> str:
    for s in payload.get('sources') or []:
        path = str(s.get('path') or '')
        if path:
            return path.replace('\\', '/')
    return ''


def _blocked(text: str, source: str) -> bool:
    low = source.lower()
    if any(part in low for part in BLOCKED_PARTS):
        return True
    return bool(SECRET.search(text))


def _open_source(source: Path):
    """Return (sqlite_path, cleanup_dir). A zip is unpacked to a temp folder."""
    if source.suffix.lower() == '.zip':
        tmp = Path(tempfile.mkdtemp(prefix='rr_gdk_'))
        with zipfile.ZipFile(source) as z:
            if DB_NAME not in z.namelist():
                shutil.rmtree(tmp, ignore_errors=True)
                raise ValueError(f'{DB_NAME} not found inside {source.name}')
            z.extract(DB_NAME, tmp)
        return tmp / DB_NAME, tmp
    return source, None


def import_gd_knowledge(db: sqlite3.Connection, source: str | Path | None = None,
                        limit: int | None = None) -> dict:
    src = Path(source).expanduser().resolve() if source else find_source()
    if src is None or not src.is_file():
        raise FileNotFoundError('Golden Dragon knowledge base not found; pass its path')
    if limit is not None and not 1 <= limit <= 1_000_000:
        raise ValueError('limit must be 1..1000000')
    init(db)
    stats = {'source': str(src), 'seen': 0, 'imported': 0, 'updated': 0, 'unchanged': 0,
             'skipped_not_active': 0, 'skipped_blocked': 0, 'skipped_empty': 0}
    path, tmp = _open_source(src)
    try:
        with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)) as old:
            cols = {r[1] for r in old.execute('PRAGMA table_info(knowledge)')}
            if not {'id', 'status', 'text', 'payload'}.issubset(cols):
                raise ValueError('unsupported knowledge schema (need id, status, text, payload)')
            sql = 'SELECT id, status, text, payload FROM knowledge ORDER BY id'
            if limit is not None:
                sql += f' LIMIT {int(limit)}'
            now = datetime.now(timezone.utc).isoformat()
            for rid, status, text, payload in old.execute(sql):
                stats['seen'] += 1
                if str(status) != 'active':
                    stats['skipped_not_active'] += 1
                    continue
                text = str(text or '').strip()
                if not text:
                    stats['skipped_empty'] += 1
                    continue
                try:
                    meta = json.loads(payload or '{}')
                except json.JSONDecodeError:
                    meta = {}
                spath = _first_source(meta)
                if _blocked(text, spath):
                    stats['skipped_blocked'] += 1
                    continue
                key = f'gdk:{rid}'
                summary = text[:MAX_SUMMARY]
                digest = hashlib.sha256((key + '\x00' + summary).encode('utf-8')).hexdigest()
                row = db.execute('SELECT sha256 FROM fused_knowledge WHERE id=?', (key,)).fetchone()
                if row and row[0] == digest:
                    stats['unchanged'] += 1
                    continue
                db.execute('''INSERT INTO fused_knowledge
                    (id,kind,title,summary,origin,license,source_path,status,sha256,imported)
                    VALUES(?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(id) DO UPDATE SET kind=excluded.kind, title=excluded.title,
                    summary=excluded.summary, origin=excluded.origin, license=excluded.license,
                    source_path=excluded.source_path, status=excluded.status,
                    sha256=excluded.sha256, imported=excluded.imported''',
                           (key, KIND, _title(text) or key, summary, ORIGIN, 'owner',
                            spath, 'active', digest, now))
                stats['updated' if row else 'imported'] += 1
        db.commit()
    finally:
        if tmp is not None:
            shutil.rmtree(tmp, ignore_errors=True)
    stats['gd_knowledge_total'] = db.execute(
        'SELECT COUNT(*) FROM fused_knowledge WHERE kind=?', (KIND,)).fetchone()[0]
    stats['fused_total'] = db.execute('SELECT COUNT(*) FROM fused_knowledge').fetchone()[0]
    return stats
