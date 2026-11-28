"""V62: native bounded experiment selection and evidence-aware debugging.
No commands from inputs are run; no model calls, learning writes, or permissions granted.
"""
import itertools, math, json, hashlib
from pathlib import Path
def label(v,limit=240):
    if not isinstance(v,str) or not v.strip() or len(v)>limit:raise ValueError("invalid text")
    return v.strip()
def number(v,lo,hi):
    if type(v) not in (int,float) or not math.isfinite(v) or not lo<=v<=hi:raise ValueError("invalid number")
    return v
def items(v,lo,hi):
    if not isinstance(v,list) or not lo<=len(v)<=hi:raise ValueError("invalid list")
    return v
def distinct(rows):
    ids=[label(x["id"],80) for x in rows]
    if any(x["id"]!=i for x,i in zip(rows,ids)):raise ValueError("noncanonical id")
    if len(ids)!=len(set(ids)):raise ValueError("duplicate id")
    return ids
def experiments(j):
    """Rank tests by weighted discriminating pairs per cost, not confidence in hypotheses."""
    hypotheses=items(j["hypotheses"],2,20);ids=distinct(hypotheses)
    weights={x["id"]:number(x.get("weight",1),.01,100) for x in hypotheses}
    for h in hypotheses:label(h["mechanism"]);label(h["falsifier"])
    tests=items(j["tests"],1,60);distinct(tests)
    budget=number(j.get("budget",10),.01,10000)
    pairs=list(itertools.combinations(ids,2))
    total=sum(weights[a]*weights[b] for a,b in pairs)
    ranked=[];excluded=[]
    for t in tests:
        label(t["method"]);label(t["controlled_variable"])
        cost=number(t["cost"],.01,10000)
        pred=t["predictions"]
        if not isinstance(pred,dict) or set(pred)!=set(ids):raise ValueError("predictions must cover all hypotheses")
        for v in pred.values():
            if v is not None:label(v,80)
        if type(t.get("safe")) is not bool:raise ValueError("explicit safe flag")
        if not t["safe"] or cost>budget:
            excluded.append({"id":t["id"],"reason":"unsafe_or_over_budget"});continue
        separated={(a,b) for a,b in pairs if pred[a] is not None and pred[b] is not None and pred[a]!=pred[b]}
        coverage=sum(weights[a]*weights[b] for a,b in separated)/total
        ranked.append({"id":t["id"],"cost":cost,"pair_coverage":round(coverage,8),"score":round(coverage/cost,8),"pairs":len(separated)})
    ranked.sort(key=lambda t:(-t["score"],-t["pair_coverage"],t["cost"],t["id"]))
    choice=next((r["id"] for r in ranked if r["pairs"]>0),None)
    return {"ok":True,"recommended_test":choice,"ranked":ranked,"excluded":excluded,"hypotheses_proven":False,"safety_verified":False,"execution_allowed":False,"note":"Predictions and safety are supplied assumptions; a rank suggests a test, not proof or permission."}
def diagnose(j):
    """Prevent stacking changes on an unlocated or unverified failure."""
    label(j["symptom"],800);boundaries=items(j["boundaries"],1,40);ids=distinct(boundaries)
    for row in boundaries:
        if row["status"] not in ("pass","fail","unknown"):raise ValueError("invalid boundary status")
        if row["status"]!="unknown":label(row["evidence"],500)
    tries=items(j.get("attempts",[]),0,30);distinct(tries)
    for a in tries:
        if a["result"] not in ("failed","passed","unknown"):raise ValueError("invalid attempt")
        label(a["change"]);label(a["evidence"])
    failing=[i for i,b in enumerate(boundaries) if b["status"]=="fail"]
    first=boundaries[failing[0]]["id"] if failing else None
    earlier_unknown=bool(failing and any(b["status"]=="unknown" for b in boundaries[:failing[0]]))
    flags=[j.get(k,False) for k in ("reproduced","root_cause_evidenced","regression_test_fails_before","regression_test_passes_after")]
    if any(type(x) is not bool for x in flags):raise ValueError("boolean required")
    if sum(a["result"]=="failed" for a in tries)>=3:
        action="review_architecture"
    elif not flags[0] or not first or earlier_unknown or not flags[1]:
        action="collect_diagnostic_evidence"
    elif not flags[2]:action="create_failing_regression"
    elif not flags[3]:action="propose_single_fix_and_retest"
    else:action="review_fresh_verification"
    return {"ok":True,"first_observed_failure":first,"earlier_unknown":earlier_unknown,"next_action":action,"root_cause_independently_verified":False,"execution_allowed":False}
def acceptance(j):
    """Verify exact artifact digests and fresh task-bound verification receipts, not semantic correctness."""
    root=Path(j["workspace"]).resolve(strict=True)
    if not root.is_dir():raise ValueError("workspace directory required")
    run=label(j["run_id"],100);req=items(j["required"],1,80)
    if any(not isinstance(x,str) or not x.strip() for x in req) or len(req)!=len(set(req)):raise ValueError("invalid requirements")
    rows=items(j["receipts"],0,80);distinct(rows);seen=set();problems=[]
    for r in rows:
        ident=r["id"]
        if ident not in req:raise ValueError("unknown requirement")
        seen.add(ident)
        if r["status"] not in ("pass","fail","not_tested"):raise ValueError("invalid status")
        if r["status"]!="pass" or r.get("run_id")!=run:
            problems.append(ident+":failed_missing_or_wrong_run");continue
        name=label(r["file"],1024);p=Path(name)
        if p.is_absolute() or ".." in p.parts:raise ValueError("unsafe evidence path")
        p=(root/p).resolve(strict=True)
        if not p.is_relative_to(root) or not p.is_file() or p.stat().st_size>2*1024**3:raise ValueError("invalid evidence file")
        with p.open("rb") as f:actual=hashlib.file_digest(f,"sha256").hexdigest()
        if actual!=r.get("sha256"):problems.append(ident+":digest_mismatch")
    problems.extend(x+":missing" for x in req if x not in seen)
    return {"ok":not problems,"blockers":problems,"receipt_integrity_passed":not problems,"semantic_verified":False,"freshness_independently_verified":False,"execution_allowed":False}
def run(action,obj):
    return {"experiments":experiments,"diagnose":diagnose,"acceptance":acceptance}[action](obj)
def profile(depth):
    return {"enabled":depth>=2,"operations":["experiments","diagnose","acceptance"] if depth>=2 else [],"note":"Choose discriminating tests, locate failure boundaries, verify task-bound artifacts. No automatic execution."}
