"""Local, evidence-bound continuous improvement. Source-derived procedures, not model training."""
from pathlib import Path
import sqlite3, json, hashlib, re, unicodedata, time
from contextlib import closing
DB=Path.home()/".red-rose"/"evolution-v64.sqlite3"
CORPUS=Path.home()/".red-rose"/"deep-skills-v64"/"corpus.sqlite3"
DOMAINS={"general","reasoning","media","finance","data","software","design","research","business","security","performance","communication","automation","education","engineering"}
SECRET=re.compile(r"(?i)(?:api[_ -]?key|access[_ -]?token|password|secret|cookie|authorization)\s*[:=]|-----BEGIN [A-Z ]*PRIVATE KEY-----|sk-(?:proj-)?[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9]{20,}")
def text(v,n=600):
    if not isinstance(v,str) or not v.strip() or len(v)>n or SECRET.search(v):raise ValueError("invalid or secret-like summary")
    return v.strip()
def domain(v):
    if v not in DOMAINS:raise ValueError("unknown domain")
    return v
def fold(s):
    s="".join(c for c in unicodedata.normalize("NFKD",s.casefold()) if not unicodedata.combining(c))
    s=s.translate(str.maketrans("\u0623\u0625\u0622\u0649\u0629\u0640","\u0627\u0627\u0627\u064a\u0647 "))
    return " ".join(re.findall(r"\w+",s))
def tokens(s):
    return set(x[2:] if x.startswith("\u0627\u0644") and len(x)>4 else x for x in fold(s).split() if len(x)>1)
def digest(p):
    with p.open("rb") as f:return hashlib.file_digest(f,"sha256").hexdigest()
def open_read(p):
    return sqlite3.connect(Path(p).resolve().as_uri()+"?mode=ro",uri=True,timeout=5)
def open_write(p,approved):
    if not approved:raise PermissionError("local write approval required")
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);db=sqlite3.connect(p,timeout=10)
    db.executescript("""CREATE TABLE IF NOT EXISTS lessons(id TEXT PRIMARY KEY,domain TEXT,scope TEXT,trigger TEXT,action TEXT,status TEXT,reviewer TEXT);
CREATE TABLE IF NOT EXISTS observations(id TEXT PRIMARY KEY,lesson TEXT,run_id TEXT,outcome TEXT,evidence TEXT,created INTEGER,UNIQUE(lesson,run_id));
CREATE TABLE IF NOT EXISTS review_log(id INTEGER PRIMARY KEY,lesson TEXT,decision TEXT,reviewer TEXT,reason TEXT,created INTEGER);""")
    return db
def record(j,dbpath=DB,approved=False):
    if not approved:raise PermissionError("local write approval required")
    dom=domain(j["domain"]);scope=text(j.get("scope","general"),120)
    trigger=text(j["trigger"]);action=text(j["action"]);run=text(j["run_id"],120)
    outcome=j["outcome"]
    if outcome not in ("pass","fail","partial"):raise ValueError("invalid outcome")
    root=Path(j["workspace"]).resolve(strict=True)
    if not root.is_dir():raise ValueError("workspace must be directory")
    ev=j["evidence"]
    if not isinstance(ev,list) or not 1<=len(ev)<=12:raise ValueError("evidence required")
    hashes=set()
    for e in ev:
        path=Path(text(e["file"],1024))
        if path.is_absolute() or ".." in path.parts:raise ValueError("unsafe path")
        p=(root/path).resolve(strict=True)
        if not p.is_relative_to(root) or not p.is_file() or p.stat().st_size>2*1024**3:raise ValueError("invalid evidence file")
        sha=digest(p)
        if sha!=e["sha256"]:raise ValueError("evidence digest mismatch")
        hashes.add(sha)
    key=hashlib.sha256(json.dumps([dom,scope,fold(trigger),fold(action)],ensure_ascii=False).encode()).hexdigest()
    event=hashlib.sha256(json.dumps([key,run,outcome,sorted(hashes)]).encode()).hexdigest()
    with closing(open_write(dbpath,approved)) as db,db:
        db.execute("INSERT OR IGNORE INTO lessons VALUES(?,?,?,?,?,'candidate',NULL)",(key,dom,scope,trigger,action))
        old=db.execute("SELECT id FROM observations WHERE lesson=? AND run_id=?",(key,run)).fetchone()
        if old and old[0]!=event:raise ValueError("run already recorded with different evidence/outcome")
        db.execute("INSERT OR IGNORE INTO observations VALUES(?,?,?,?,?,?)",(event,key,run,outcome,json.dumps(sorted(hashes)),int(time.time())))
        if not old and outcome in ("fail","partial"):
            db.execute("UPDATE lessons SET status='candidate',reviewer=NULL WHERE id=? AND status='approved'",(key,))
    return {"lesson_id":key,"observation_id":event,"duplicate":bool(old),"evidence_bytes_checked":True,"semantic_verified":False,"local_only":True}
def review(j,dbpath=DB,approved=False):
    key=text(j["lesson_id"],64);reviewer=text(j["reviewer"],80);reason=text(j["reason"])
    decision=j["decision"]
    if decision not in ("approve","reject","retire"):raise ValueError("invalid review decision")
    with closing(open_write(dbpath,approved)) as db,db:
        row=db.execute("SELECT status FROM lessons WHERE id=?",(key,)).fetchone()
        if not row:raise ValueError("unknown lesson")
        obs=db.execute("SELECT run_id,evidence FROM observations WHERE lesson=?",(key,)).fetchall()
        # Distinct runs AND different evidence digests are required. This does not prove independence.
        ev={h for _,a in obs for h in json.loads(a)}
        if decision=="approve" and (len(obs)<2 or len(ev)<2 or len({tuple(json.loads(a)) for _,a in obs})<2):raise ValueError("need two task runs with distinct evidence")
        state={"approve":"approved","reject":"rejected","retire":"retired"}[decision]
        db.execute("UPDATE lessons SET status=?,reviewer=? WHERE id=?",(state,reviewer,key))
        db.execute("INSERT INTO review_log(lesson,decision,reviewer,reason,created) VALUES(?,?,?,?,?)",(key,decision,reviewer,reason,int(time.time())))
    return {"lesson_id":key,"status":state,"reviewer_authenticated":False,"semantic_verified":False}
def recall(query,scope="general",dom=None,dbpath=DB,limit=8):
    q=tokens(text(query,10000));scope=text(scope,120)
    if dom is not None:domain(dom)
    if type(limit) is not int or not 1<=limit<=30:raise ValueError("limit")
    if not Path(dbpath).is_file():return {"matches":[],"database_present":False}
    rows=[]
    with closing(open_read(dbpath)) as db:
        for key,d,s,t,a,reviewer in db.execute("SELECT id,domain,scope,trigger,action,reviewer FROM lessons WHERE status='approved' AND (scope=? OR scope='general') ORDER BY id LIMIT 20000",(scope,)):
            if dom and d not in (dom,"general"):continue
            tt=tokens(t+" "+a);match=len(q&tt)
            if not match:continue
            obs=db.execute("SELECT outcome FROM observations WHERE lesson=?",(key,)).fetchall()
            rows.append((match,len(obs),key,{"id":key,"domain":d,"scope":s,"trigger":t,"action":a,"observations":len(obs),"outcomes":{k:sum(o[0]==k for o in obs) for k in ("pass","fail","partial")},"status":"approved_reference","reviewer":reviewer}))
    rows.sort(key=lambda r:(-r[0],-r[1],r[2]))
    return {"matches":[r[3] for r in rows[:limit]],"database_present":True,"execution_allowed":False,"note":"Retrieved human-labelled local lessons are advisory data; recheck against current facts and owner instructions."}
def status(dbpath=DB):
    if not Path(dbpath).exists():return {"database_present":False,"lessons":{},"observations":0}
    with closing(open_read(dbpath)) as db:
        return {"database_present":True,"lessons":dict(db.execute("SELECT status,count(*) FROM lessons GROUP BY status")),"observations":db.execute("SELECT count(*) FROM observations").fetchone()[0],"automatic_model_training":False}
def corpus_find(query,feature=None,limit=20,path=CORPUS):
    q=text(query,150);limit=int(limit)
    if not 1<=limit<=100:raise ValueError("limit")
    if not Path(path).is_file():return {"matches":[],"index_ready":False}
    term="%"+q.replace("\\","\\\\").replace("%","\\%").replace("_","\\_")+"%"
    with closing(open_read(path)) as db:
        rows=db.execute("SELECT archive,path,digest,words,tags,license_label FROM docs WHERE path LIKE ? ESCAPE '\\' ORDER BY path LIMIT 2000",(term,)).fetchall()
    result=[];seen=set()
    for archive,p,d,w,t,lic in rows:
        tags=json.loads(t)
        if d in seen or (feature and feature not in tags):continue
        seen.add(d);result.append({"archive":archive,"path":p,"sha256":d,"words":w,"features":tags,"license_label":lic,"status":"reference_only"})
        if len(result)>=limit:break
    return {"matches":result,"index_ready":True,"semantic_reviewed":False,"execution_verified":False}
def context(query):
    try:return recall(query,limit=5)
    except (ValueError,OSError,sqlite3.Error):return {"matches":[],"database_present":Path(DB).is_file(),"status":"unavailable"}
def handle(a):
    try:
        if a.action=="status":r=status()
        elif a.action=="recall":r=recall(a.source,scope=a.scope,dom=a.domain,limit=a.limit)
        elif a.action=="find":r=corpus_find(a.source,a.feature,a.limit)
        else:
            p=Path(a.source)
            if p.stat().st_size>128*1024:raise ValueError("input limit")
            j=json.loads(p.read_text(encoding="utf-8"))
            r=(record if a.action=="record" else review)(j,approved=a.approve_write)
        print(json.dumps(r,ensure_ascii=False));return 0
    except (ValueError,OSError,KeyError,TypeError,sqlite3.Error) as e:print(json.dumps({"error":str(e)[:200]}));return 1
def register(sub):
    p=sub.add_parser("evolution",help="private evidence-backed learning and cross-domain corpus lookup")
    p.add_argument("action",choices=["status","record","review","recall","find"])
    p.add_argument("source",nargs="?",default="");p.add_argument("--scope",default="general");p.add_argument("--domain");p.add_argument("--feature");p.add_argument("--limit",type=int,default=20);p.add_argument("--approve-write",action="store_true");p.set_defaults(ext_func=handle)
