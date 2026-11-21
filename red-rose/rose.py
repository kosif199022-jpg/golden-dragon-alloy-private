#!/usr/bin/env python3
"""Independent Red Rose memory, knowledge ingestion and planning core."""
import argparse, hashlib, json, os, sqlite3, re
from contextlib import closing
from pathlib import Path
from datetime import datetime, timezone
from styles import save as save_style, load as load_style, list_styles
from render import render
from production import produce
from speech import parse_srt, apply_captions
from alloy_fusion import import_alloy, find_fused, stats_fused
from knowledge_router import route as route_knowledge
from verify_media import verify_video

def connect(path):
    p=Path(path).expanduser(); p.parent.mkdir(parents=True,exist_ok=True)
    db=sqlite3.connect(p)
    db.execute('CREATE TABLE IF NOT EXISTS memories(id INTEGER PRIMARY KEY, created TEXT, category TEXT, content TEXT)')
    db.execute('CREATE TABLE IF NOT EXISTS knowledge(id INTEGER PRIMARY KEY, source TEXT, sha256 TEXT UNIQUE, content TEXT, imported TEXT)')
    db.execute('CREATE TABLE IF NOT EXISTS source_links(source TEXT, sha256 TEXT, origin TEXT, revision TEXT, license TEXT, PRIMARY KEY(source, sha256, origin, revision))')
    db.commit(); return db

SENSITIVE_NAMES={'.env','.npmrc','.pypirc','id_rsa','id_ed25519','credentials.json','secrets.json','settings.local.json'}
SENSITIVE_PARTS={'.git','node_modules','venv','.venv','owner-memory','private','secrets','credentials','.ssh'}

def ingest(db, directory, origin="local", revision="unversioned", license_id="unverified"):
    root=Path(directory).resolve(); count=0; skipped=0
    for p in root.rglob('*'):
        if not p.is_file() or p.is_symlink() or p.suffix.lower() not in {'.md','.txt','.py','.json','.yaml','.yml'} or p.stat().st_size>2_000_000: continue
        if p.name.lower() in SENSITIVE_NAMES or any(part.lower() in SENSITIVE_PARTS for part in p.relative_to(root).parts): skipped+=1; continue
        try: data=p.read_text(encoding='utf-8')
        except (UnicodeError,OSError): skipped+=1; continue
        # Do not send potential secrets to the knowledge database even on a PRIVATE repository.
        if re.search(r'-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----', data): skipped+=1; continue
        if re.search(r'(?im)^\s*(?:api[_-]?key|access[_-]?token|password|secret[_-]?key)\s*[:=]\s*[\"\']?[^\s\"\']{8,}', data): skipped+=1; continue
        digest=hashlib.sha256(data.encode()).hexdigest()
        cur=db.execute('INSERT OR IGNORE INTO knowledge(source,sha256,content,imported) VALUES(?,?,?,?)',(str(p.relative_to(root)),digest,data,datetime.now(timezone.utc).isoformat()))
        count+=cur.rowcount
        db.execute('INSERT OR IGNORE INTO source_links(source,sha256,origin,revision,license) VALUES(?,?,?,?,?)',
                   (str(p.relative_to(root)),digest,origin,revision,license_id))
    db.commit(); return {'imported':count,'unreadable':skipped}

def main(argv=None):
    a=argparse.ArgumentParser(); a.add_argument('--db',default=os.environ.get('RED_ROSE_DB',str(Path.home()/'.red-rose'/'memory.sqlite3')))
    sub=a.add_subparsers(dest='command',required=True)
    sub.add_parser('doctor')
    x=sub.add_parser('remember'); x.add_argument('content'); x.add_argument('--category',default='lesson')
    x=sub.add_parser('recall'); x.add_argument('query',nargs='?',default=''); x.add_argument('--limit',type=int,default=20)
    x=sub.add_parser('ingest'); x.add_argument('directory'); x.add_argument('--origin',default='local');x.add_argument('--revision',default='unversioned');x.add_argument('--license',default='unverified')
    x=sub.add_parser('search'); x.add_argument('query'); x.add_argument('--limit',type=int,default=10)
    x=sub.add_parser('plan'); x.add_argument('task')
    x=sub.add_parser('style-save'); x.add_argument('name'); x.add_argument('recipe_json')
    x=sub.add_parser('style-show'); x.add_argument('name')
    sub.add_parser('style-list')
    x=sub.add_parser('render'); x.add_argument('output'); x.add_argument('--style'); x.add_argument('--duration',type=float,default=10); x.add_argument('--fps',type=int,default=24); x.add_argument('--width',type=int,default=540); x.add_argument('--height',type=int,default=960); x.add_argument('--mp4',action='store_true')
    x=sub.add_parser('produce'); x.add_argument('storyboard_json'); x.add_argument('output'); x.add_argument('--fps',type=int,default=24); x.add_argument('--width',type=int,default=540); x.add_argument('--height',type=int,default=960); x.add_argument('--audio'); x.add_argument('--srt')
    sub.add_parser('sources')
    x=sub.add_parser('verify'); x.add_argument('video'); x.add_argument('--fps',type=float); x.add_argument('--width',type=int); x.add_argument('--height',type=int)
    x=sub.add_parser('fuse-alloy'); x.add_argument('source_db'); x.add_argument('--limit',type=int)
    x=sub.add_parser('fuse-search'); x.add_argument('query'); x.add_argument('--limit',type=int,default=20)
    sub.add_parser('fuse-stats')
    x=sub.add_parser('route'); x.add_argument('task'); x.add_argument('--limit',type=int,default=6)
    args=a.parse_args(argv)
    if args.command=='verify':
        print(json.dumps(verify_video(args.video,expected_fps=args.fps,width=args.width,height=args.height),ensure_ascii=False)); return
    if args.command=='produce':
        shots=json.loads(Path(args.storyboard_json).read_text(encoding='utf-8'))
        if args.srt: shots=apply_captions(shots,parse_srt(Path(args.srt).read_text(encoding='utf-8-sig')))
        result=produce(shots,args.output,args.fps,args.width,args.height,args.audio)
        result['style_save_question']='تحب تحفظ ستايل الفيديو؟ وباسم إيه؟ احفظه بأمر style-save.'
        print(json.dumps(result,ensure_ascii=False)); return
    if args.command=='plan': print(json.dumps({'task':args.task,'steps':['inspect','plan','execute','verify','learn'],'status':'planned_not_executed'},ensure_ascii=False)); return
    with closing(connect(args.db)) as db:
        if args.command=='doctor': result={'memory':'ready','knowledge_documents':db.execute('SELECT count(*) FROM knowledge').fetchone()[0],'legacy_skill_runtime_required':False}
        elif args.command=='remember':
            cur=db.execute('INSERT INTO memories(created,category,content) VALUES(?,?,?)',(datetime.now(timezone.utc).isoformat(),args.category,args.content)); db.commit();result={'saved':True,'id':cur.lastrowid}
        elif args.command=='recall':
            rows=db.execute('SELECT id,category,content FROM memories WHERE content LIKE ? ORDER BY id DESC LIMIT ?',('%'+args.query+'%',max(1,min(args.limit,100)))).fetchall();result=[{'id':r[0],'category':r[1],'content':r[2]} for r in rows]
        elif args.command=='ingest': result=ingest(db,args.directory,args.origin,args.revision,args.license)
        elif args.command=='style-save': result=save_style(db,args.name,json.loads(args.recipe_json))
        elif args.command=='style-show': result=load_style(db,args.name)
        elif args.command=='style-list': result=list_styles(db)
        elif args.command=='fuse-alloy': result=import_alloy(db,args.source_db,args.limit)
        elif args.command=='fuse-search': result=find_fused(db,args.query,args.limit)
        elif args.command=='fuse-stats': result=stats_fused(db)
        elif args.command=='route': result=route_knowledge(db,args.task,args.limit)
        elif args.command=='sources': result=[dict(zip(('source','sha256','origin','revision','license'),r)) for r in db.execute('SELECT * FROM source_links ORDER BY origin,source LIMIT 1000')]
        elif args.command=='render':
            saved=load_style(db,args.style) if args.style else None
            if args.style and not saved: raise ValueError('Unknown style: '+args.style)
            result=render(args.output,args.duration,args.fps,args.width,args.height,saved['recipe'] if saved else None,args.mp4)
        elif args.command=='search':
            rows=db.execute('SELECT source,substr(content,1,500) FROM knowledge WHERE content LIKE ? LIMIT ?',('%'+args.query+'%',max(1,min(args.limit,100)))).fetchall();result=[{'source':r[0],'excerpt':r[1]} for r in rows]
    print(json.dumps(result,ensure_ascii=False))
if __name__=='__main__':main()
