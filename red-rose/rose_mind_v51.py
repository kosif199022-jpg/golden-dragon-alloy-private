"""Evidence-gated native mind inspired by Golden Dragon's eight-stage protocol.
Planning and evidence bookkeeping, not a new LLM or autonomous code rewriting.
"""
from __future__ import annotations
import argparse, hashlib, json, re, sqlite3, time, unicodedata
from contextlib import closing
from functools import lru_cache
from pathlib import Path

PROFILE=Path(__file__).with_name("GOLDEN_MIND_PROFILE.json")
DB=Path.home()/".red-rose"/"mind-lessons.sqlite"
STAGES=("understand","ask_or_assume","delivery","ground","alternatives","small_test","critique","verify_learn")
DEPTH={0:(0,7),1:(0,1,2,5,7),2:tuple(range(8)),3:tuple(range(8))}
@lru_cache(maxsize=1)
def profile():
    return json.loads(PROFILE.read_text(encoding="utf-8"))
def string(x,label,limit=2000):
    if type(x) is not str or not x.strip() or len(x)>limit:raise ValueError("invalid "+label)
    return x.strip()
def integer(x,label,lo=0,hi=3):
    if type(x) is not int or not lo<=x<=hi:raise ValueError("invalid "+label)
    return x
def keys(p,required,optional=()):
    if type(p) is not dict or set(required)-p.keys() or p.keys()-set(required)-set(optional):
        raise ValueError("invalid parameters")
def norm(x):
    x=unicodedata.normalize("NFKD",x.casefold())
    x="".join(c for c in x if not unicodedata.combining(c))
    x=x.translate(str.maketrans("أإآىة","ااايه"))
    return " ".join(re.findall(r"\w+",x))
def select_methods(request,kind,limit):
    text=" "+norm(request)+" "
    ranked=[]
    for row in profile()["methods"]:
        matches=[t for t in row["trigger_words"] if norm(t) and " "+norm(t)+" " in text]
        score=3*len(matches)+int(kind in row["use_when"])
        if score:ranked.append((-score,row["id"],row,matches))
    ranked.sort(key=lambda x:(x[0],x[1]))
    return [{"id":r["id"],"name_ar":r["name_ar"],"matches":m,"check_ar":r["check_ar"]} for _,_,r,m in ranked[:limit]]
def plan(p):
    from rose_agent import brief
    keys(p,("request",),("previous","impact","uncertainty","irreversible","external","constraints","unknowns","deliverable","done_when"))
    request=string(p["request"],"request",10000)
    impact=integer(p.get("impact",1),"impact");uncertainty=integer(p.get("uncertainty",1),"uncertainty")
    flags=[p.get(k,False) for k in ("irreversible","external")]
    if any(type(x) is not bool for x in flags):raise ValueError("flags must be bool")
    constraints=p.get("constraints",[]);unknowns=p.get("unknowns",[])
    if type(constraints) is not list or len(constraints)>50 or type(unknowns) is not list or len(unknowns)>30:raise ValueError("invalid constraints or unknowns")
    constraints=[string(x,"constraint",300) for x in constraints]
    questions=[];assumptions=[]
    for x in unknowns:
        keys(x,("id","question","impact","uncertainty"))
        risk=integer(x["impact"],"impact")*integer(x["uncertainty"],"uncertainty")
        row={"id":string(x["id"],"id",80),"question":string(x["question"],"question",300),"risk":risk}
        (questions if risk>=6 else assumptions).append(row)
    if len({x["id"] for x in questions+assumptions})!=len(unknowns):raise ValueError("duplicate unknown")
    questions.sort(key=lambda x:(-x["risk"],x["id"]))
    previous=p.get("previous")
    if previous is not None:previous=string(previous,"previous",10000)
    base=brief(request,prev=previous,depth="auto")
    base_depth=base.get("depth","L1")
    depth=int(base_depth[-1]) if base_depth in ("L0","L1","L2","L3") else 1
    risk=impact*uncertainty
    if any(flags) or risk>=6 or questions:depth=3
    elif risk>=3:depth=max(depth,2)
    route=base.get("route",{}); approvals=base.get("approvals",[])
    blocked=bool(questions or approvals or base.get("decision") in ("ask","none") or route.get("type")=="none" or any(flags))
    deliverable=p.get("deliverable");done=p.get("done_when")
    if deliverable is not None:deliverable=string(deliverable,"deliverable",500)
    if done is not None:done=string(done,"done_when",500)
    from rose_see_native_v52 import route as see_route
    see_packet=see_route(request,mode="deep" if depth>=2 else "normal")
    return {"ok":True,"see":see_packet,"depth":"L"+str(depth),"risk":risk,"base_route":route,"base_decision":base.get("decision"),
            "approvals":approvals,"execution_allowed":False,"requires_review":blocked,
            "decision":"review_required" if blocked else "plan_only",
            "next_question":questions[0] if questions else None,"remaining_high_risk_unknowns":questions[1:],
            "assumption_candidates":assumptions,"constraints":constraints,"deliverable":deliverable,"done_when":done,
            "stages":[{"id":STAGES[i],"status":"pending","source_stage":i+1} for i in DEPTH[depth]],
            "methods":select_methods(request,base.get("kind",""),(2,5,9,12)[depth]),
            "note":"No action executed. Constraints and assumptions need human review; route is inherited, not certified. Missing evidence is not success."}
def gate(p):
    """Require actual workspace file hashes, explicit constraint results, no unreviewed critical stage."""
    from rose_white_native import verify_outputs
    keys(p,("workspace","files","constraints","checks"),("depth",))
    depth=integer(p.get("depth",2),"depth")
    files=p["files"]
    if type(files) is not list or not files:raise ValueError("evidence files required")
    actual=verify_outputs(p["workspace"],files)["files"]
    lookup={r["path"]:r["sha256"] for r in actual}
    blockers=[];checked=set()
    rows=p["checks"]
    if type(rows) is not list or len(rows)>8:raise ValueError("invalid checks")
    for r in rows:
        keys(r,("stage","passed","file","sha256"))
        stage=r["stage"]
        if stage not in STAGES or stage in checked or type(r["passed"]) is not bool:raise ValueError("invalid stage check")
        checked.add(stage)
        if not r["passed"] or lookup.get(r["file"])!=r["sha256"]:blockers.append("failed_or_unmatched:"+stage)
    for i in DEPTH[depth]:
        if STAGES[i] not in checked:blockers.append("missing:"+STAGES[i])
    constraints=p["constraints"]
    if type(constraints) is not list or len(constraints)>50:raise ValueError("invalid constraints")
    for r in constraints:
        keys(r,("id","passed"))
        ident=string(r["id"],"constraint id",100)
        if type(r["passed"]) is not bool:raise ValueError("invalid constraint result")
        if not r["passed"]:blockers.append("constraint:"+ident)
    if len({r["id"] for r in constraints})!=len(constraints):raise ValueError("duplicate constraint")
    return {"ok":not blockers,"blockers":blockers,"files":actual,"depth":"L"+str(depth),
            "semantic_verification":False,"note":"File hashes verified; check outcomes are supplied claims, not independent semantic review."}
def learn(p,db,approve):
    from rose_white_native import verify_outputs
    from intelligence_fusion_v43 import feedback_cycle
    keys(p,("task","observation","workspace","file"))
    o=p["observation"]
    if type(o) is not dict or o.get("reproduced") is not True:raise ValueError("reproduced observation required")
    # Revalidate actual file bytes; only store bounded summary and proposal, not source contents.
    a=verify_outputs(p["workspace"],[p["file"]])["files"][0]
    if o.get("evidence_sha")!=a["sha256"]:raise ValueError("evidence hash mismatch")
    r=feedback_cycle({"task":p["task"],"observations":[o]})
    prop=r["proposals"][0]
    if not approve:return {"ok":False,"outcome":"approval_required","proposal":prop}
    payload=json.dumps({"task":p["task"],"observation":o,"proposal":prop},ensure_ascii=False,allow_nan=False)
    identity=hashlib.sha256(json.dumps({"id":o["id"],"evidence_sha":a["sha256"]},sort_keys=True).encode()).hexdigest()
    db=Path(db);db.parent.mkdir(parents=True,exist_ok=True)
    with closing(sqlite3.connect(db,timeout=5)) as c,c:
        c.execute("CREATE TABLE IF NOT EXISTS lessons(id TEXT PRIMARY KEY, created REAL, payload TEXT)")
        added=c.execute("INSERT OR IGNORE INTO lessons VALUES(?,?,?)",(identity,time.time(),payload)).rowcount
    return {"ok":True,"saved":bool(added),"id":identity,"proposal":prop,"applied":False,"note":"Review candidate saved; no code, model or routing weights modified."}
def lessons(db):
    if not Path(db).is_file():return {"ok":True,"lessons":[]}
    with closing(sqlite3.connect(db,timeout=5)) as c:
        rows=[{"id":i,"proposal":json.loads(p)["proposal"]} for i,p in c.execute("SELECT id,payload FROM lessons ORDER BY created DESC LIMIT 100")]
    return {"ok":True,"lessons":rows}
def handle(a):
    try:
        if a.action=="status":
            data=profile();r={"ok":True,"source_sha256":data["source_sha256"],"methods":len(data["methods"]),"stages":list(STAGES),"depth_policy":DEPTH,"mode":"native deterministic gates"}
        elif a.action=="lessons":r=lessons(a.mind_db)
        else:
            p=Path(a.params or "")
            if not p.is_file() or p.stat().st_size>256*1024:raise ValueError("bounded JSON input required")
            obj=json.loads(p.read_text(encoding="utf-8-sig"))
            r=plan(obj) if a.action=="plan" else gate(obj) if a.action=="gate" else learn(obj,a.mind_db,a.approve_write)
        print(json.dumps(r,ensure_ascii=False,indent=2))
        return 3 if r.get("outcome")=="approval_required" else 1 if not r.get("ok") else 0
    except (ValueError,TypeError,KeyError,OSError,sqlite3.Error) as e:
        print(json.dumps({"ok":False,"error":str(e)},ensure_ascii=False));return 1
def register(sub):
    p=sub.add_parser("mind",help="adaptive planning, evidence gate and reviewed learning")
    p.add_argument("action",choices=["status","plan","gate","learn","lessons"])
    p.add_argument("params",nargs="?")
    p.add_argument("--mind-db",type=Path,default=DB)
    p.add_argument("--approve-write",action="store_true")
    p.set_defaults(ext_func=handle)
