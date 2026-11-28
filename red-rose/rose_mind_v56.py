"""V56: source-distilled reasoning procedures, evidence comparison and council.
No model calls, external commands, automatic permissions or private memory import.
"""
from __future__ import annotations
import json, re
from functools import lru_cache
from pathlib import Path
from rose_metacognition_v54 import fields, ident, rows

@lru_cache(maxsize=1)
def profile():
    return json.loads(Path(__file__).with_name("DRAGON_MIND_V56_PROFILE.json").read_text(encoding="utf-8"))

def enrich(request, depth, selected):
    if depth<2:return {"enabled":False}
    from rose_mind_v51 import norm
    p=profile(); text=" "+norm(request)+" "
    hits=lambda words:sum(bool(norm(w) and " "+norm(w)+" " in text) for w in words)
    chosen=sorted(p["paths"],key=lambda x:(-hits(x["trigger_words"]),x["id"]))
    paths=[x for x in chosen if hits(x["trigger_words"])][:2 if depth==3 else 1]
    methods={x["id"]:x for x in p["methods"]}
    ids=list(dict.fromkeys([x["id"] for x in selected]+[i for x in paths for i in x["tools"]]))
    ids=[i for i in ids if i in methods][:12 if depth==3 else 9]
    if not ids:ids=["polya-four-phases"]
    # Preserve existing approval and execution decisions. Only add review procedures.
    return {"enabled":True,"paths":[{"id":x["id"],"name_ar":x["name_ar"],"hint_ar":x["hint_ar"]} for x in paths],
            "procedures":[{"id":i,"steps_ar":methods[i]["steps_ar"],"check_ar":methods[i]["check_ar"]} for i in ids],
            "bias_checks":[{"id":x["id"],"question_ar":x["question_ar"],"test":x["test"]} for x in p["bias_checks"]],
            "minimum_alternatives":3 if depth==3 else 2,
            "verification_required":True,"executed":False}

def council(p):
    fields(p,("domain",),("size",))
    domain=ident(p["domain"]); size=p.get("size",5)
    lenses=profile()["council_lenses"]
    if domain not in lenses or type(size) is not int or size not in (3,5,7):raise ValueError("unknown domain or size")
    positions={3:(0,3,4),5:(0,1,3,4,5),7:tuple(range(7))}[size]
    seats=[{"id":"seat-"+str(i+1),"lens":lenses[domain][j]} for i,j in enumerate(positions)]
    return {"ok":True,"domain":domain,"size":size,"seats":seats,
            "required":["position","counterargument","evidence"],"agents_called":False,"opinions_generated":False}

def evidence_files(root,names):
    from rose_white_native import verify_outputs
    names=[ident(x) for x in rows(names,1,40)]
    if len(set(names))!=len(names):raise ValueError("duplicate evidence path")
    # Bound total work before hashing; trusted local workspace only.
    root=Path(root).resolve(strict=True); total=0
    for name in names:
        f=(root/name).resolve(strict=True)
        if not f.is_relative_to(root) or not f.is_file():raise ValueError("invalid evidence path")
        total+=f.stat().st_size
        if total>100*1024*1024:raise ValueError("evidence exceeds 100 MiB")
    actual=verify_outputs(str(root),names)["files"]
    return {r["path"]:r["sha256"] for r in actual}

def council_review(p):
    fields(p,("domain","size","workspace","files","submissions","dissent"))
    seats=council({"domain":p["domain"],"size":p["size"]})["seats"]
    actual=evidence_files(p["workspace"],p["files"])
    expected={x["id"]:x["lens"] for x in seats};seen=set();positions=set();blockers=[];used=set()
    for x in rows(p["submissions"],0,7):
        fields(x,("id","lens","position","counterargument","file","sha256"))
        i=ident(x["id"]);lens=ident(x["lens"])
        if i in seen or expected.get(i)!=lens:raise ValueError("duplicate or unexpected council seat")
        seen.add(i)
        position=ident(x["position"]);ident(x["counterargument"])
        normalized=" ".join(position.casefold().split())
        if normalized in positions:blockers.append("duplicate_position:"+i)
        positions.add(normalized)
        if not isinstance(x["sha256"],str) or actual.get(ident(x["file"]))!=x["sha256"]:blockers.append("evidence_mismatch:"+i)
        else:used.add(x["sha256"])
    blockers.extend("missing_seat:"+x for x in expected if x not in seen)
    if len(used)<2:blockers.append("need_distinct_evidence")
    ident(p["dissent"])
    return {"ok":not blockers,"blockers":blockers,"submitted":len(seen),"distinct_evidence_files":len(used),
            "independent_agents_verified":False,"semantic_verification":False,"execution_allowed":False}

def hypothesis_compare(p):
    """ACH-style contradiction tally: not Bayesian inference or factual validation."""
    fields(p,("hypotheses","workspace","files","evidence"))
    ids=[ident(x) for x in rows(p["hypotheses"],2,12)]
    if len(set(ids))!=len(ids):raise ValueError("duplicate hypothesis")
    actual=evidence_files(p["workspace"],p["files"])
    result={i:{"id":i,"contradiction":0,"support":0,"unknown":0} for i in ids}
    used=set()
    for x in rows(p["evidence"],1,40):
        fields(x,("file","sha256","weight","ratings"))
        digest=x["sha256"]
        if not isinstance(digest,str) or actual.get(x["file"])!=digest:raise ValueError("evidence hash mismatch")
        if digest in used:raise ValueError("duplicate evidence bytes")
        used.add(digest)
        w=x["weight"];ratings=x["ratings"]
        if type(w) is not int or not 1<=w<=3 or type(ratings) is not dict or set(ratings)!=set(ids):raise ValueError("invalid weight or incomplete ratings")
        for i,v in ratings.items():
            if v not in ("contradiction","support","unknown"):raise ValueError("invalid rating")
            result[i][v]+=w
    ranking=sorted(result.values(),key=lambda x:(x["contradiction"],x["unknown"],-x["support"],x["id"]))
    a,b=ranking[:2]
    decisive=a["contradiction"]<b["contradiction"] and a["unknown"]==0 and len(used)>=2
    return {"ok":True,"ranking":ranking,"candidate_for_review":a["id"] if decisive else None,"distinct_evidence":len(used),
            "decision":"review_candidate" if decisive else "seek_discriminating_evidence","semantic_verification":False,"execution_allowed":False}

def reference_find(p):
    fields(p,("query",),("limit",))
    q=ident(p["query"]).casefold();limit=p.get("limit",20)
    if type(limit) is not int or not 1<=limit<=50:raise ValueError("invalid limit")
    data=json.loads(Path(__file__).with_name("DRAGON_REFERENCE_V56.json").read_text(encoding="utf-8"))
    matches=[x for x in data["entries"] if q in x["id"].casefold() or q==x["kind"].casefold()]
    return {"ok":True,"count":len(matches),"matches":matches[:limit],"execution_allowed":False}

def run(action,p):
    return {"council":council,"council-review":council_review,"hypotheses":hypothesis_compare,"references":reference_find}[action](p)
