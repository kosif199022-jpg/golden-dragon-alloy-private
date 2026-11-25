"""White Bird-inspired native orchestration. No external application or model calls."""
from __future__ import annotations
import argparse, hashlib, json, math, re, sqlite3, sys, time, uuid
from pathlib import Path
from contextlib import closing

DEFAULT_DB=Path.home()/".red-rose"/"white-native.sqlite"
# Retryable pure computations only. No media writes, shell, network, or device actions.
OPS=frozenset(("motion-ease","motion-beats","decision-matrix","plan-gaps","agent-rigor"))
MAX_JSON=256*1024
def encode(x):
    s=json.dumps(x,ensure_ascii=False,allow_nan=False,separators=(",",":"))
    if len(s.encode("utf-8"))>MAX_JSON:raise ValueError("JSON exceeds limit")
    return s
def connect(path):
    c=sqlite3.connect(path,timeout=5)
    c.row_factory=sqlite3.Row
    c.execute("PRAGMA busy_timeout=5000")
    return c
def init(path):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    with closing(connect(p)) as c,c:
        c.execute("""CREATE TABLE IF NOT EXISTS jobs(
          id TEXT PRIMARY KEY, op TEXT NOT NULL, params TEXT NOT NULL,
          state TEXT NOT NULL, created REAL NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
          token TEXT, lease REAL, result TEXT, error TEXT)""")
        c.execute("CREATE INDEX IF NOT EXISTS jobs_state_created ON jobs(state,created,id)")
def enqueue(path,op,params):
    if op not in OPS or not isinstance(params,dict):raise ValueError("operation not allowed")
    data=encode(params); init(path); jid=uuid.uuid4().hex
    with closing(connect(path)) as c,c:
        c.execute("BEGIN IMMEDIATE")
        if c.execute("SELECT count(*) FROM jobs WHERE state IN ('queued','running')").fetchone()[0]>=1000:
            raise ValueError("queue full")
        c.execute("INSERT INTO jobs(id,op,params,state,created) VALUES(?,?,?,'queued',?)",(jid,op,data,time.time()))
    return {"ok":True,"id":jid,"state":"queued"}
def claim(path,now=None):
    init(path);now=time.time() if now is None else now;token=uuid.uuid4().hex
    with closing(connect(path)) as c,c:
        c.execute("BEGIN IMMEDIATE")
        row=c.execute("SELECT id,op,params FROM jobs WHERE state='queued' ORDER BY created,id LIMIT 1").fetchone()
        if row is None:return None
        c.execute("UPDATE jobs SET state='running',attempts=attempts+1,token=?,lease=? WHERE id=?",(token,now+300,row["id"]))
        return dict(row,token=token)
def finish(path,jid,token,result=None,error=None):
    with closing(connect(path)) as c,c:
        r=c.execute("UPDATE jobs SET state=?,result=?,error=?,token=NULL,lease=NULL WHERE id=? AND state='running' AND token=?",
                    ("failed" if error else "done",None if error else encode(result),error,jid,token))
        return r.rowcount==1
def recover(path,now=None):
    init(path);now=time.time() if now is None else now
    with closing(connect(path)) as c,c:
        c.execute("BEGIN IMMEDIATE")
        failed=c.execute("UPDATE jobs SET state='failed',error='retry limit',token=NULL,lease=NULL WHERE state='running' AND lease<=? AND attempts>=3",(now,)).rowcount
        queued=c.execute("UPDATE jobs SET state='queued',token=NULL,lease=NULL WHERE state='running' AND lease<=? AND attempts<3",(now,)).rowcount
    return {"ok":True,"requeued":queued,"failed":failed}
def work_one(path):
    from rose_golden_native import execute
    job=claim(path)
    if job is None:return {"ok":True,"state":"empty"}
    try:
        if job["op"] not in OPS:raise ValueError("operation not allowed")
        r=execute(job["op"],json.loads(job["params"]))
        if isinstance(r,dict) and (r.get("ok") is False or r.get("passed") is False):raise ValueError("engine reported failure")
        accepted=finish(path,job["id"],job["token"],result=r)
        return {"ok":accepted,"id":job["id"],"state":"done" if accepted else "stale_claim"}
    except Exception as e:
        accepted=finish(path,job["id"],job["token"],error=type(e).__name__+": "+str(e)[:300])
        return {"ok":False,"id":job["id"],"state":"failed" if accepted else "stale_claim"}
def work_batch(path, limit=8, workers=2):
    """Explicit bounded batch of pure jobs, using the existing fenced claims."""
    if type(limit) is not int or not 1<=limit<=20 or type(workers) is not int or not 1<=workers<=4:
        raise ValueError("limit 1..20; workers 1..4 required")
    if not Path(path).is_file():
        return {"ok":True,"results":[],"remaining":0,"processed":0,"workers":workers}
    from concurrent.futures import ThreadPoolExecutor
    results=[]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for start in range(0,limit,workers):
            wave=list(pool.map(lambda _:work_one(path),range(min(workers,limit-start))))
            results.extend(x for x in wave if x["state"]!="empty")
            if any(x["state"]=="empty" for x in wave):break
    return {"ok":all(x["ok"] for x in results),"results":results,"processed":len(results),
            "remaining":listing(path)["counts"].get("queued",0),"workers":workers}

def listing(path):
    if not Path(path).is_file():return {"ok":True,"counts":{},"jobs":[]}
    with closing(connect(path)) as c:
        counts=dict(c.execute("SELECT state,count(*) FROM jobs GROUP BY state"))
        jobs=[dict(r) for r in c.execute("SELECT id,op,state,attempts,created FROM jobs ORDER BY created DESC LIMIT 100")]
    return {"ok":True,"counts":counts,"jobs":jobs}
def result(path,jid):
    if not re.fullmatch("[a-f0-9]{32}",jid):raise ValueError("invalid job id")
    if not Path(path).is_file():raise ValueError("queue not found")
    with closing(connect(path)) as c:
        r=c.execute("SELECT id,op,state,result,error FROM jobs WHERE id=?",(jid,)).fetchone()
    if not r:raise ValueError("job not found")
    d=dict(r);d["result"]=json.loads(d["result"]) if d["result"] else None
    return d
def verify_outputs(root,names):
    root=Path(root).resolve(strict=True)
    if not root.is_dir() or not isinstance(names,list) or not 1<=len(names)<=100:raise ValueError("invalid workspace or file list")
    rows=[];seen=set()
    for name in names:
        if not isinstance(name,str):raise ValueError("path must be text")
        rel=Path(name)
        if rel.is_absolute() or rel.drive or ".." in rel.parts:raise ValueError("relative paths only")
        p=(root/rel).resolve(strict=True)
        if not p.is_relative_to(root) or not p.is_file() or p in seen:raise ValueError("outside workspace, duplicate, or not file")
        seen.add(p)
        with p.open("rb") as f:
            h=hashlib.file_digest(f,"sha256").hexdigest()
        rows.append({"path":p.relative_to(root).as_posix(),"bytes":p.stat().st_size,"sha256":h})
    return {"ok":True,"files":rows,"note":"Integrity only, not visual or semantic QA; use a trusted local workspace."}
def check_pairs(events):
    if not isinstance(events,list) or len(events)>1000:raise ValueError("invalid events")
    pending=set();seen=set();issues=[]
    for i,e in enumerate(events):
        if not isinstance(e,dict) or e.get("type") not in ("call","result") or not isinstance(e.get("id"),str) or not 1<=len(e["id"])<=128:raise ValueError("invalid event")
        key=e["id"]
        if e["type"]=="call":
            if key in seen:issues.append({"index":i,"issue":"duplicate_call","id":key})
            else:seen.add(key);pending.add(key)
        elif key not in pending:issues.append({"index":i,"issue":"unmatched_result","id":key})
        else:pending.remove(key)
    issues.extend({"issue":"missing_result","id":key} for key in sorted(pending))
    return {"ok":not issues,"issues":issues,"events":len(events)}
def compare(rows):
    if not isinstance(rows,list) or not 2<=len(rows)<=50:raise ValueError("2..50 results required")
    out=[];seen=set()
    for r in rows:
        if not isinstance(r,dict):raise ValueError("invalid row")
        name=r.get("id");score=r.get("score")
        if not isinstance(name,str) or not name or name in seen or isinstance(score,bool) or not isinstance(score,(int,float)) or not math.isfinite(score):raise ValueError("invalid result")
        seen.add(name);out.append({"id":name,"score":score})
    out.sort(key=lambda r:(-r["score"],r["id"]))
    return {"ok":True,"ranking":out,"winners":[r["id"] for r in out if r["score"]==out[0]["score"]],"note":"Caller-supplied scores, not independent model evaluation."}
def handle(a):
    try:
        action=a.action;db=a.queue_db
        if action in ("enqueue","work-one","work-batch","recover") and not a.approve_write:
            r={"ok":False,"outcome":"approval_required","would_write":str(db)}
        elif action=="status":r=listing(db)
        elif action=="result":r=result(db,a.arg or "")
        elif action=="work-one":r=work_one(db)
        elif action=="work-batch":r=work_batch(db,a.limit,a.workers)
        elif action=="recover":r=recover(db)
        else:
            p=Path(a.arg or "")
            if not p.is_file() or p.stat().st_size>MAX_JSON:raise ValueError("bounded JSON input file required")
            x=json.loads(p.read_text(encoding="utf-8-sig"))
            if action=="enqueue":r=enqueue(db,x["op"],x["params"])
            elif action=="verify-outputs":r=verify_outputs(x["workspace"],x["files"])
            elif action=="check-pairs":r=check_pairs(x)
            else:r=compare(x)
        print(json.dumps(r,ensure_ascii=False,indent=2))
        return 3 if r.get("outcome")=="approval_required" else 1 if r.get("ok") is False else 0
    except (ValueError,TypeError,KeyError,OSError,sqlite3.Error) as e:
        print(json.dumps({"ok":False,"error":str(e)},ensure_ascii=False));return 1
def register(sub):
    p=sub.add_parser("white-native",help="persistent local queue, recovery and delivery validation")
    p.add_argument("action",choices=["enqueue","work-one","work-batch","recover","status","result","verify-outputs","check-pairs","compare"])
    p.add_argument("arg",nargs="?")
    p.add_argument("--queue-db",type=Path,default=DEFAULT_DB)
    p.add_argument("--limit",type=int,default=8)
    p.add_argument("--workers",type=int,default=2)
    p.add_argument("--approve-write",action="store_true")
    p.set_defaults(ext_func=handle)
if __name__=="__main__":
    p=argparse.ArgumentParser();s=p.add_subparsers(required=True);register(s)
    raise SystemExit(handle(p.parse_args(["white-native",*sys.argv[1:]])))
