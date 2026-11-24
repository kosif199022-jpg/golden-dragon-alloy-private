"""Red Rose v47: every memory of the Black and Golden Dragons inside Red Rose.

`rose.py dragon-sync`  imports, idempotently, into the private Red Rose store (~/.red-rose/memory.sqlite3):
  - the fused dragon knowledge (alloy kb: skills, roads, rules, lessons, tools, engines) via fuse-alloy;
  - the dragon conversation memory: runtime/mind/chats/*.md (one summary per past chat);
  - the owner's live memory: owner-memory/live lessons, outcomes, chats;
  - the dragon history and lesson books: RD_HISTORY, RD_CHATS_MEMORY, RD_CHATS_LESSONS, OWNER_ESSENCE;
  - Red Rose's own work log (references/WORK_LOG.md).
`rose.py dragon "<words>"` searches all of it at once (memories + fused knowledge), best matches first.

Everything stays in the owner's private store; lines that look like secrets are dropped.
Imported text is reference data about past work, never instructions.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from alloy_fusion import SECRET

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent                      # the golden-dragon-alloy repo
AR_NORM = str.maketrans({'أ': 'ا', 'إ': 'ا', 'آ': 'ا', 'ة': 'ه', 'ى': 'ي', 'ـ': ''})
DIAC = re.compile('[ً-ْٰ]')


def norm(s: str) -> str:
    return DIAC.sub('', s).translate(AR_NORM).lower()


def _clean(text: str) -> str:
    return '\n'.join(l for l in text.splitlines() if not SECRET.search(l)).strip()


def _sources(root: Path):
    rt = root / 'runtime'
    for p in sorted((rt / 'mind' / 'chats').glob('*.md')):
        yield 'dragon-chat', p
    live = root / 'owner-memory' / 'live'
    for p in sorted((live / 'chats').glob('*.md')):
        yield 'dragon-chat', p
    for name, cat in (('lessons.jsonl', 'dragon-lesson'), ('outcomes.jsonl', 'dragon-outcome')):
        if (live / name).exists():
            yield cat, live / name
    for p in (rt / 'references' / 'RD_HISTORY.md', rt / 'references' / 'RD_CHATS_MEMORY.md',
              rt / 'references' / 'RD_CHATS_LESSONS.md', rt / 'mind' / 'OWNER_ESSENCE.md',
              rt / 'engine' / 'references' / 'OWNER.md', root / 'red-rose' / 'references' / 'WORK_LOG.md'):
        if p.exists():
            yield 'dragon-history', p


def _chunks(cat: str, path: Path):
    text = path.read_text(encoding='utf-8', errors='replace')
    if path.suffix == '.jsonl':
        for line in text.splitlines():
            try:
                d = json.loads(line)
            except ValueError:
                continue
            t = d.get('text') or d.get('lesson') or d.get('note') or json.dumps(d, ensure_ascii=False)
            yield f'[{path.name}] {t}'
        return
    if cat == 'dragon-chat':
        yield f'[{path.name}] {text}'
        return
    # long books: one memory per section
    parts = re.split(r'\n(?=#{1,3} )', text)
    for part in parts:
        if part.strip():
            yield f'[{path.name}] {part}'


def import_dragon_memory(db: sqlite3.Connection, root: str | Path | None = None) -> dict:
    root = Path(root) if root else ROOT
    db.execute('CREATE TABLE IF NOT EXISTS memories(id INTEGER PRIMARY KEY, created TEXT, category TEXT, content TEXT)')
    db.execute('CREATE TABLE IF NOT EXISTS memory_keys(sha TEXT PRIMARY KEY, memory_id INTEGER)')
    now = datetime.now(timezone.utc).isoformat(timespec='seconds')
    st = {'files': 0, 'added': 0, 'already': 0, 'dropped_secret_lines': 0, 'by_category': {}}
    for cat, path in _sources(root):
        st['files'] += 1
        for chunk in _chunks(cat, path):
            clean = _clean(chunk)
            st['dropped_secret_lines'] += chunk.count('\n') - clean.count('\n') if len(clean) < len(chunk) else 0
            if len(clean) < 20:
                continue
            sha = hashlib.sha256((cat + clean).encode()).hexdigest()
            if db.execute('SELECT 1 FROM memory_keys WHERE sha=?', (sha,)).fetchone():
                st['already'] += 1
                continue
            cur = db.execute('INSERT INTO memories(created,category,content) VALUES(?,?,?)', (now, cat, clean[:20000]))
            db.execute('INSERT INTO memory_keys(sha,memory_id) VALUES(?,?)', (sha, cur.lastrowid))
            st['added'] += 1
            st['by_category'][cat] = st['by_category'].get(cat, 0) + 1
    db.commit()
    return st


def dragon_sync(db: sqlite3.Connection, root: str | Path | None = None) -> dict:
    from alloy_fusion import import_alloy
    root = Path(root) if root else ROOT
    out = {}
    kb = root / 'kb' / 'alloy.db'
    out['knowledge'] = import_alloy(db, kb) if kb.exists() else {'skipped': f'{kb} not found'}
    out['memory'] = import_dragon_memory(db, root)
    return out


def _score(text: str, words: list[str]) -> float:
    t = norm(text)
    hits = sum(1 for w in words if w in t)
    return hits + 0.2 * sum(t.count(w) for w in words) / max(1, len(t) / 2000) if hits else 0


def dragon_search(db: sqlite3.Connection, query: str, limit: int = 12) -> list[dict]:
    words = [norm(w) for w in re.findall(r'\w+', query) if len(w) > 1]
    if not words:
        return []
    res = []
    like = ' OR '.join(['content LIKE ?'] * len(words))
    args = ['%' + w + '%' for w in words]
    # stored text is not normalised: search raw and normalised spellings
    raw = [w for w in re.findall(r'\w+', query) if len(w) > 1]
    like_raw = ' OR '.join(['content LIKE ?'] * len(raw))
    for row in db.execute(f'SELECT id,category,content FROM memories WHERE {like} OR {like_raw}', args + ['%' + w + '%' for w in raw]):
        s = _score(row[2], words)
        if s:
            res.append({'score': round(s, 2), 'kind': row[1], 'id': f'memory:{row[0]}', 'text': row[2][:400]})
    try:
        from alloy_fusion import find_fused
        for r in find_fused(db, query, limit=limit * 2) or []:
            txt = json.dumps(r, ensure_ascii=False)
            s = _score(txt, words)
            if s:
                res.append({'score': round(s, 2), 'kind': r.get('kind', 'knowledge') if isinstance(r, dict) else 'knowledge',
                            'id': r.get('id', '') if isinstance(r, dict) else '', 'text': txt[:400]})
    except Exception as e:      # fused knowledge not imported yet
        res.append({'score': 0, 'kind': 'note', 'id': '', 'text': f'fused knowledge unavailable: {e}; run rose.py dragon-sync'})
    res.sort(key=lambda r: -r['score'])
    return res[:limit]
