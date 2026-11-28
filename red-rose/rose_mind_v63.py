"""V63 native dependency scheduling, robust decisions and risk register.
Deterministic read-only calculations on user-supplied plans, not autonomous execution.
"""
import math, json
from collections import defaultdict
from fractions import Fraction

def text(v,n=300):
    if type(v) is not str or not v.strip() or len(v)>n:raise ValueError("invalid text")
    return v.strip()
def ident(v):
    if text(v,80)!=v:raise ValueError("noncanonical identifier")
    return v
def seq(v,a,b):
    if type(v) is not list or not a<=len(v)<=b:raise ValueError("invalid list")
    return v
def integer(v,a,b):
    if type(v) is not int or not a<=v<=b:raise ValueError("invalid integer")
    return v
def number(v,a,b):
    if type(v) not in (int,float) or not math.isfinite(v) or not a<=v<=b:raise ValueError("invalid number")
    return Fraction(str(v))
def ids(rows):
    a=[ident(r["id"]) for r in rows]
    if len(a)!=len(set(a)):raise ValueError("duplicate identifier")
    return a

def schedule(j):
    """Critical path with precedence only; no assumed unlimited execution permission."""
    rows=seq(j["tasks"],1,200);names=ids(rows);lookup=dict(zip(names,rows))
    deps={};successors=defaultdict(list);duration={}
    for k,r in lookup.items():
        duration[k]=integer(r["duration"],1,1000000)
        text(r["deliverable"]);text(r["acceptance"])
        a=seq(r.get("depends_on",[]),0,199)
        if any(type(x) is not str or x not in lookup or x==k for x in a) or len(set(a))!=len(a):raise ValueError("invalid dependency")
        deps[k]=set(a)
        for x in a:successors[x].append(k)
    order=[];layers=[];remaining=set(names)
    while remaining:
        ready=sorted(k for k in remaining if deps[k]<=set(order))
        if not ready:raise ValueError("cyclic dependency")
        layers.append(ready);order.extend(ready);remaining.difference_update(ready)
    es={};ef={}
    for k in order:
        es[k]=max((ef[x] for x in deps[k]),default=0);ef[k]=es[k]+duration[k]
    end=max(ef.values());ls={};lf={}
    for k in reversed(order):
        lf[k]=min((ls[x] for x in successors[k]),default=end);ls[k]=lf[k]-duration[k]
    critical=sorted(k for k in names if ls[k]==es[k]);current=next(k for k in sorted(names) if ef[k]==end)
    path=[current]
    while deps[current]:
        current=min((x for x in deps[current] if ef[x]==es[current]),default=None)
        if current is None:break
        path.append(current)
    return {"ok":True,"duration_lower_bound":end,"total_work":sum(duration.values()),"critical_path":path[::-1],"critical_tasks":critical,"dependency_layers":layers,"tasks":[{"id":k,"earliest_start":es[k],"earliest_finish":ef[k],"latest_start":ls[k],"slack":ls[k]-es[k]} for k in order],"resources_accounted_for":False,"execution_allowed":False,"note":"Precedence-only schedule; durations and acceptance conditions are supplied, not verified. Parallel groups are not worker assignments."}

def decision(j):
    """Weighted alternatives with interval scores; hard constraints cannot be averaged away."""
    criteria=seq(j["criteria"],1,30);cn=ids(criteria)
    weights={r["id"]:number(r["weight"],.001,10000) for r in criteria};total=sum(weights.values())
    alts=seq(j["alternatives"],2,50);ids(alts)
    required=seq(j.get("required",[]),0,50)
    if any(ident(x)!=x for x in required) or len(set(required))!=len(required):raise ValueError("invalid hard constraints")
    ranked=[];excluded=[]
    for a in alts:
        gates=a.get("gates",{})
        if type(gates) is not dict or set(gates)!=set(required) or any(type(v) is not bool and v is not None for v in gates.values()):raise ValueError("explicit constraint outcomes required")
        scores=a["scores"]
        if type(scores) is not dict or set(scores)!=set(cn):raise ValueError("complete criteria required")
        intervals={}
        for c,v in scores.items():
            if v is None:intervals[c]=(Fraction(0),Fraction(100))
            elif type(v) is list and len(v)==2:
                lo=number(v[0],0,100);hi=number(v[1],0,100)
                if lo>hi:raise ValueError("inverted bounds")
                intervals[c]=(lo,hi)
            else:
                q=number(v,0,100);intervals[c]=(q,q)
        bad=sorted(k for k,v in gates.items() if v is not True)
        if bad:excluded.append({"id":a["id"],"blocked_gates":bad});continue
        lo=sum(weights[c]*v[0] for c,v in intervals.items())/total
        hi=sum(weights[c]*v[1] for c,v in intervals.items())/total
        ranked.append((a["id"],lo,hi))
    ranked.sort(key=lambda r:(-r[1],-r[2],r[0]))
    winner=next((a for a,lo,hi in ranked if all(lo>h for b,l,h in ranked if b!=a)),None)
    return {"ok":True,"robust_winner":winner,"status":"robust_on_supplied_bounds" if winner is not None else "review_required","ranked":[{"id":a,"lower":round(float(lo),6),"upper":round(float(hi),6)} for a,lo,hi in ranked],"excluded":excluded,"semantic_verified":False,"execution_allowed":False,"note":"Higher scores are better. Unknown scores span 0–100. Winner only if lower bound strictly exceeds every eligible competitor upper bound. Supplied constraints and weights are not verified."}

def risks(j):
    rows=seq(j["risks"],1,100);ids(rows);out=[];block=[]
    for r in rows:
        probability=integer(r["likelihood"],1,5);impact=integer(r["impact"],1,5)
        text(r["failure"]);text(r["trigger"]);text(r["owner"])
        state=r["status"]
        if state not in ("open","mitigated","accepted","unknown"):raise ValueError("risk state")
        mitigation=r.get("mitigation")
        if mitigation is not None:text(mitigation)
        evidence=r.get("evidence")
        if evidence is not None:text(evidence)
        # Unverified mitigation/acceptance remains unresolved; critical impact never disappears in an average.
        resolved=state in ("mitigated","accepted") and bool(evidence)
        score=probability*impact
        if not resolved and (impact==5 or score>=15):block.append(r["id"])
        out.append({"id":r["id"],"score":score,"status":state,"evidence_supplied":bool(evidence),"needs_action":not resolved})
    out.sort(key=lambda r:(-r["score"],r["id"]))
    return {"ok":not block,"blocking_risks":sorted(block),"ranked":out,"semantic_verified":False,"execution_allowed":False}

def run(action,j):
    return {"schedule":schedule,"decision":decision,"risks":risks}[action](j)
