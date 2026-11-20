#!/usr/bin/env python3
"""Red Rose: independent standard-library memory and task CLI."""
import argparse, json, sqlite3, os
from pathlib import Path
from datetime import datetime, timezone
def connect(path):
    p=Path(path).expanduser(); p.parent.mkdir(parents=True,exist_ok=True)
    db=sqlite3.connect(p)
    db.execute('CREATE TABLE IF NOT EXISTS memories (id INTEGER PRIMARY KEY, created TEXT NOT NULL, category TEXT NOT NULL, content TEXT NOT NULL)')
    db.commit(); return db
def main(argv=None):
    a=argparse.ArgumentParser(description='Red Rose independent core')
    a.add_argument('--db',default=os.environ.get('RED_ROSE_DB',str(Path.home()/'.red-rose'/'memory.sqlite3')))
    sub=a.add_subparsers(dest='command',required=True)
    sub.add_parser('doctor')
    s=sub.add_parser('remember'); s.add_argument('content'); s.add_argument('--category',default='lesson')
    s=sub.add_parser('recall'); s.add_argument('query',nargs='?',default=''); s.add_argument('--limit',type=int,default=20)
    s=sub.add_parser('plan'); s.add_argument('task')
    args=a.parse_args(argv)
    if args.command=='plan':
        print(json.dumps({'task':args.task,'steps':['define output','check inputs','execute','independent verification','record outcome'],'status':'planned_not_executed'},ensure_ascii=False)); return
    with connect(args.db) as db:
        if args.command=='doctor':
            print(json.dumps({'name':'red-rose','database':str(Path(args.db).expanduser()),'memory':'ready','legacy_runtime_dependency':False})); return
        if args.command=='remember':
            db.execute('INSERT INTO memories(created,category,content) VALUES (?,?,?)',(datetime.now(timezone.utc).isoformat(),args.category,args.content));db.commit()
            print(json.dumps({'saved':True,'id':db.execute('SELECT last_insert_rowid()').fetchone()[0]}));return
        rows=db.execute('SELECT id,created,category,content FROM memories WHERE content LIKE ? ORDER BY id DESC LIMIT ?',('%'+args.query+'%',max(1,min(args.limit,100)))).fetchall()
        print(json.dumps([dict(zip(('id','created','category','content'),r)) for r in rows],ensure_ascii=False))
if __name__=='__main__': main()
