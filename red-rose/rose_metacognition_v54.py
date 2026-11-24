"""V54: bounded, read-only metacognitive decision support; no autonomous actions."""
from math import isfinite

def number(v, lo, hi):
    if type(v) not in (int, float) or not lo <= v <= hi or not isfinite(v):
        raise ValueError("invalid bounded number")
    return float(v)

def ident(v):
    if type(v) is not str or not v.strip() or len(v)>120:
        raise ValueError("invalid identifier")
    return v.strip()

def fields(v, required, optional=()):
    if type(v) is not dict or set(required)-v.keys() or v.keys()-set(required)-set(optional):
        raise ValueError("invalid fields")

def rows(v, lo, hi):
    if type(v) is not list or not lo <= len(v) <= hi:
        raise ValueError("invalid list size")
    return v

def protocol(depth):
    return {"enabled":depth>=2,"steps":["generate_alternatives","premortem","challenge_assumptions","compare_scenarios","test_small","reassess"] if depth>=2 else [],
            "max_attempts":3 if depth>=2 else 1,"requires_observed_evidence":True,
            "execution_allowed":False}

def review(p):
    fields(p,("alternatives",),("attempts","budget","min_margin"))
    budget=p.get("budget",3)
    if type(budget) is not int or not 1<=budget<=10: raise ValueError("invalid budget")
    margin=number(p.get("min_margin",.1),0,2)
    attempts=rows(p.get("attempts",[]),0,10)
    failed=set()
    for a in attempts:
        fields(a,("id","outcome","evidence"))
        aid=ident(a["id"])
        ident(a["evidence"])
        if a["outcome"] not in ("failed","passed","inconclusive"): raise ValueError("invalid outcome")
        if a["outcome"]=="failed": failed.add(aid)
    ranked=[]; seen=set()
    for a in rows(p["alternatives"],1,12):
        fields(a,("id","scenarios","constraints_passed","assumptions"))
        aid=ident(a["id"])
        if aid in seen: raise ValueError("duplicate alternative")
        seen.add(aid)
        if type(a["constraints_passed"]) is not bool: raise ValueError("invalid constraint flag")
        assumptions=[ident(x) for x in rows(a["assumptions"],0,20)]
        scenarios=rows(a["scenarios"],1,12)
        probs=[]; outcomes=[]; evidence=[]; names=set()
        for s in scenarios:
            fields(s,("id","probability","utility"),("evidence",))
            sid=ident(s["id"])
            if sid in names: raise ValueError("duplicate scenario")
            names.add(sid)
            probs.append(number(s["probability"],0,1)); outcomes.append(number(s["utility"],-1,1))
            if "evidence" in s: evidence.append(ident(s["evidence"]))
        if abs(sum(probs)-1)>1e-8: raise ValueError("probabilities must sum to one")
        expected=sum(x*y for x,y in zip(probs,outcomes))
        worst=min(y for x,y in zip(probs,outcomes) if x>0)
        score=.7*expected+.3*worst
        ranked.append({"id":aid,"expected":expected,"worst":worst,"score":score,
                       "assumptions":assumptions,"evidence_refs":evidence,
                       "all_scenarios_referenced":len(evidence)==len(scenarios),
                       "eligible":a["constraints_passed"] and aid not in failed,
                       "premortem_required":worst<0 or bool(assumptions) or len(evidence)!=len(scenarios)})
    if any(ident(a["id"]) not in seen for a in attempts): raise ValueError("unknown attempt")
    ranked.sort(key=lambda x:(-x["score"],x["id"]))
    eligible=[a for a in ranked if a["eligible"]]
    candidate=eligible[0] if eligible else None
    gap=candidate["score"]-eligible[1]["score"] if len(eligible)>1 else None
    decision="test_candidate"
    if len(attempts)>=budget: decision="stop_budget"
    elif not candidate: decision="stop_no_eligible"
    elif any(a["outcome"]=="passed" and ident(a["id"])==candidate["id"] for a in attempts): decision="review_observed_result"
    elif candidate["premortem_required"] or (gap is not None and gap<=margin): decision="seek_evidence"
    return {"ok":True,"decision":decision,"candidate":candidate["id"] if candidate and not decision.startswith("stop") else None,
            "ranked":ranked,"margin":gap,"remaining_attempts":max(0,budget-len(attempts)),
            "failed_strategies":sorted(failed),"execution_allowed":False,
            "independently_verified":False,"note":"Input forecasts and evidence references are supplied claims. Scores are heuristic, not proof. Validate independently."}

def calibration(p):
    fields(p,("observations",))
    obs=rows(p["observations"],1,1000)
    errors=[]; probabilities=[]; actual=[]; seen=set()
    for o in obs:
        fields(o,("id","prediction","observed","evidence"))
        oid=ident(o["id"])
        if oid in seen: raise ValueError("duplicate observation")
        seen.add(oid); ident(o["evidence"])
        q=number(o["prediction"],0,1)
        if type(o["observed"]) is not bool: raise ValueError("invalid observed outcome")
        y=int(o["observed"]); probabilities.append(q);actual.append(y);errors.append((q-y)**2)
    n=len(errors)
    return {"ok":True,"count":n,"brier_score":sum(errors)/n,
            "confidence_bias":(sum(probabilities)-sum(actual))/n,
            "small_sample":n<30,"independently_verified":False,
            "note":"Lower Brier is better. Supplied outcomes and references are not independently verified; no automatic learning or weight changes."}
