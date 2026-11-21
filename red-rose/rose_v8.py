"""Red Rose V8: standalone integrated CLI. No legacy skill imports."""
import argparse, json, sqlite3, hashlib, re
from pathlib import Path
from datetime import datetime, timezone
from xml.sax.saxutils import escape
from math import sin, pi
SKIP={"node_modules",".git",".venv","__pycache__"}
EXT={".md",".txt",".py",".json",".yaml",".yml"}
def dbopen(path):
 p=Path(path).expanduser();p.parent.mkdir(parents=True,exist_ok=True)
 db=sqlite3.connect(p)
 db.execute("CREATE TABLE IF NOT EXISTS memories(id INTEGER PRIMARY KEY,created TEXT,category TEXT,content TEXT)")
 db.execute("CREATE TABLE IF NOT EXISTS knowledge(id INTEGER PRIMARY KEY,source TEXT,sha256 TEXT UNIQUE,content TEXT,imported TEXT)")
 return db
def ingest(db,folder):
 root=Path(folder).resolve(); count=0
 for p in root.rglob("*"):
  if not p.is_file() or p.suffix.lower() not in EXT or any(x in SKIP for x in p.relative_to(root).parts):continue
  if p.stat().st_size>2000000:continue
  if re.search(r"(^|[._-])(secret|credential|password|token|private|\.env)([._-]|$)",p.name,re.I):continue
  try: data=p.read_text(encoding="utf-8")
  except (UnicodeError,OSError):continue
  if re.search(r"-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----",data):continue
  digest=hashlib.sha256(data.encode()).hexdigest()
  cur=db.execute("INSERT OR IGNORE INTO knowledge(source,sha256,content,imported) VALUES(?,?,?,?)",(str(p.relative_to(root)),digest, data,datetime.now(timezone.utc).isoformat()))
  count+=cur.rowcount
 db.commit();return count
def figure(phase,width=320,height=568):
 if width<1 or height<1:raise ValueError("dimensions must be positive")
 arm=sin(phase*2*pi)*20;leg=sin(phase*2*pi)*17
 return f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}"><rect width="100%" height="100%" fill="#101827"/><g transform="translate({width/2} {height/2})" stroke="#f5d8c1" stroke-width="9" stroke-linecap="round" fill="none"><circle cy="-86" r="18" fill="#f5d8c1" stroke="none"/><path d="M 0 -64 L 0 12 M 0 -43 L {-36+arm:.2f} 2 M 0 -43 L {36+arm:.2f} 2 M 0 12 L {-21+leg:.2f} 78 M 0 12 L {21-leg:.2f} 78"/></g></svg>'
def storyboard(out,scenes,fps=12):
 if not 1<=fps<=60:raise ValueError("fps out of range")
 out=Path(out);out.mkdir(parents=True,exist_ok=True);index=0
 for scene in scenes:
  frames=int(scene["seconds"]*fps)
  if not 1<=frames<=fps*120:raise ValueError("scene duration out of range")
  for j in range(frames):
   svg=figure(j/frames)
   (out/f"frame_{index:06}.svg").write_text(svg,encoding="utf-8")
   index+=1
 return index
def main(argv=None):
 ap=argparse.ArgumentParser();ap.add_argument("--db",default=str(Path.home()/".red-rose"/"memory.sqlite3"))
 sub=ap.add_subparsers(dest="cmd",required=True)
 sub.add_parser("doctor")
 p=sub.add_parser("remember");p.add_argument("text")
 p=sub.add_parser("recall");p.add_argument("query",nargs="?",default="")
 p=sub.add_parser("ingest");p.add_argument("folder")
 p=sub.add_parser("search");p.add_argument("query")
 p=sub.add_parser("plan");p.add_argument("task")
 p=sub.add_parser("render");p.add_argument("output");p.add_argument("--seconds",type=int,default=2);p.add_argument("--fps",type=int,default=12)
 a=ap.parse_args(argv)
 if a.cmd=="plan":result={"task":a.task,"status":"planned_not_executed","steps":["inspect","plan","execute","test","record"]}
 elif a.cmd=="render":result={"frames":storyboard(a.output,[{"seconds":a.seconds}],a.fps),"output":a.output,"format":"SVG frames, not MP4"}
 else:
  with dbopen(a.db) as db:
   if a.cmd=="doctor":result={"status":"ready","independent":True}
   elif a.cmd=="remember":
    db.execute("INSERT INTO memories(created,category,content) VALUES(?,?,?)",(datetime.now(timezone.utc).isoformat(),"lesson",a.text));db.commit();result={"saved":True}
   elif a.cmd=="recall":result=db.execute("SELECT content FROM memories WHERE content LIKE ? ORDER BY id DESC LIMIT 20",("%"+a.query+"%",)).fetchall()
   elif a.cmd=="ingest":result={"imported":ingest(db,a.folder)}
   else:result=db.execute("SELECT source,substr(content,1,300) FROM knowledge WHERE content LIKE ? LIMIT 20",("%"+a.query+"%",)).fetchall()
 print(json.dumps(result,ensure_ascii=False))
if __name__=="__main__":main()
