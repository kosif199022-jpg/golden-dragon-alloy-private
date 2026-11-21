"""Red Rose V10: independent, offline metadata-only Alloy knowledge importer.

No legacy skill is imported or executed; raw body blobs are never copied.
"""
from __future__ import annotations
import hashlib, re, sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
NEEDED={'id','kind','title','summary','path','origin','license','status'}
SECRET=re.compile(r"(?i)(?:-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----|(?:api[_-]?key|access[_-]?token|password|secret[_-]?key)\s*[:=]\s*\S{8,}|(?:ghp_|github_pat_|sk-proj-|sk-)[A-Za-z0-9_-]{12,})")
BLOCKED=('owner-memory','.ssh','credentials','secrets','private-memory','.env')
def setup(db):
    db.execute("""CREATE TABLE IF NOT EXISTS fused_knowledge(
    id TEXT PRIMARY KEY,kind TEXT,title TEXT,summary TEXT,origin TEXT,license TEXT,
    source_path TEXT,status TEXT,sha256 TEXT,imported TEXT)""")
    db.execute("CREATE INDEX IF NOT EXISTS fused_kind_idx ON fused_knowledge(kind)")
    db.commit()
def migrate(db, old_path):
    source=Path(old_path).expanduser().resolve()
    if not source.is_file(): raise FileNotFoundError(source)
    setup(db)
    counts={'seen':0,'imported':0,'updated':0,'excluded':0,'mode':'descriptions_only'}
    with closing(sqlite3.connect(source.as_uri()+'?mode=ro',uri=True)) as old:
        old.row_factory=sqlite3.Row
        cols={r['name'] for r in old.execute('PRAGMA table_info(units)')}
        if not NEEDED.issubset(cols): raise ValueError('unsupported source schema')
        for r in old.execute("SELECT id,kind,title,summary,path,license,status,origin FROM units ORDER BY id"):
            counts['seen']+=1
            kind=str(r['kind'] or '').lower()
            status=str(r['status'] or '').lower()
            path=str(r['path'] or '').lower().replace('\\','/')
            origin=str(r['origin'] or '').lower()
            title=str(r['title'] or '')
            summary=str(r['summary'] or '')[:1200]
            if (kind in ('memory','conversation','chat') or
                status in ('private','quarantined','staged','review-before-run') or
                any(term in path or term in origin for term in BLOCKED) or
                not title.strip() or SECRET.search(summary)):
                counts['excluded']+=1
                continue
            ident=str(r['id'])
            digest=hashlib.sha256((ident+'\0'+summary).encode()).hexdigest()
            previous=db.execute('SELECT sha256 FROM fused_knowledge WHERE id=?',(ident,)).fetchone()
            if previous and previous[0]==digest:continue
            db.execute("""INSERT INTO fused_knowledge VALUES (?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(id) DO UPDATE SET
            kind=excluded.kind,title=excluded.title,summary=excluded.summary,
            origin=excluded.origin,license=excluded.license,source_path=excluded.source_path,
            status=excluded.status,sha256=excluded.sha256,imported=excluded.imported""",
            (ident,str(r['kind'] or ''),title,summary,str(r['origin'] or ''),
            str(r['license'] or ''),str(r['path'] or ''),str(r['status'] or ''),
            digest,datetime.now(timezone.utc).isoformat()))
            counts['updated' if previous else 'imported']+=1
    db.commit()
    counts['total']=db.execute('SELECT count(*) FROM fused_knowledge').fetchone()[0]
    counts['private_copied']=db.execute("SELECT count(*) FROM fused_knowledge WHERE kind='memory' OR status='private'").fetchone()[0]
    return counts
def search(db, query, limit=20):
    setup(db)
    if not query.strip():raise ValueError('nonempty query required')
    q=query.replace('\\','\\\\').replace('%','\\%').replace('_','\\_')
    rows=db.execute("""SELECT id,kind,title,summary,origin,license FROM fused_knowledge
       WHERE title LIKE ? ESCAPE '\\' OR summary LIKE ? ESCAPE '\\'
       ORDER BY id LIMIT ?""",('%'+q+'%','%'+q+'%',min(max(limit,1),100))).fetchall()
    return [dict(zip(('id','kind','title','summary','origin','license'),r)) for r in rows]
if __name__=='__main__':
    import argparse,json
    ap=argparse.ArgumentParser()
    ap.add_argument('source')
    ap.add_argument('--db',default=str(Path.home()/'.red-rose'/'memory.sqlite3'))
    a=ap.parse_args()
    out=Path(a.db).expanduser();out.parent.mkdir(parents=True,exist_ok=True)
    with closing(sqlite3.connect(out)) as db: print(json.dumps(migrate(db,a.source),ensure_ascii=False))
