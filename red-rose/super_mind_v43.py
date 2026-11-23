"""V43: evidence-based app improvement gate distilled independently from app-super-mind.

Zero I/O. Nine-stage process, twelve competency rubrics, and paired before/after
evaluation with immutable case identities. Does NOT inspect the user's computer,
train the model, auto-update code, or pretend user ratings have been verified.
"""
from __future__ import annotations

from collections import Counter
import math
import re

OPS = ("ladder", "organ_audit", "paired_compare")
STAGES = ("understand", "ground", "baseline", "prioritize", "design",
          "premortem", "build", "prove", "learn_handoff")
ORGANS = ("intent", "context", "memory", "planning", "action", "grounding",
          "verification", "calibration", "safety", "learning", "measurement",
          "resilience")
CATEGORIES = ("normal", "noisy", "ambiguous", "unsafe", "legacy", "out_of_scope")
_CRITICAL = frozenset(("verification", "safety", "learning", "measurement"))
_HASH = re.compile(r"^[a-f0-9]{64}$")


def _dict(data, allowed, required=()):
    if type(data) is not dict:
        raise ValueError("params must be a JSON object")
    unknown = set(data) - set(allowed)
    if unknown:
        raise ValueError("unknown parameters: " + ", ".join(sorted(unknown)))
    missing = set(required)-set(data)
    if missing:
        raise ValueError("required parameters missing: "+", ".join(sorted(missing)))
    return data


def _str(value, label, maxlen=500):
    if type(value) is not str or not value.strip() or len(value)>maxlen:
        raise ValueError(label+" must be a bounded nonempty string")
    return value.strip()


def _score(value, label):
    if type(value) is not int or not 0<=value<=4:
        raise ValueError(label+" must be an integer 0..4")
    return value


def ladder(params):
    """Inspect declared nine-stage evidence. No filesystem checks are claimed."""
    _dict(params,("mode","stages"),())
    mode=params.get("mode","normal")
    if mode not in ("fast","normal","deep"):
        raise ValueError("mode must be fast, normal or deep")
    records=params.get("stages",[])
    if type(records) is not list or len(records)>9:
        raise ValueError("stages must be <=9 records")
    indexed={}
    for record in records:
        _dict(record,("stage","artifact","evidence_ids","done"),("stage","artifact","evidence_ids","done"))
        name=record["stage"]
        if name not in STAGES or name in indexed:
            raise ValueError("invalid or duplicate stage")
        artifact=_str(record["artifact"],"artifact",200)
        evidence=record["evidence_ids"]
        if type(evidence) is not list or len(evidence)>40 or any(type(x) is not str or not x.strip() or len(x)>120 for x in evidence):
            raise ValueError("evidence_ids must be a bounded array of evidence references")
        if type(record["done"]) is not bool:
            raise ValueError("done must be true/false")
        indexed[name]={"artifact":artifact,"evidence_count":len(evidence),
                       "done":record["done"]}
    steps=[]
    first_open=None
    for idx,name in enumerate(STAGES):
        rec=indexed.get(name)
        prior_complete=all(indexed.get(prev,{}).get("done") and
                           indexed[prev]["evidence_count"]>0 for prev in STAGES[:idx])
        valid=bool(rec and rec["done"] and rec["evidence_count"] and prior_complete)
        if first_open is None and not valid:
            first_open=name
        steps.append({"index":idx+1,"stage":name,"status":"claimed_complete" if valid else
                      ("blocked_out_of_order" if rec and rec["done"] and not prior_complete else "pending"),
                      "evidence_count":rec["evidence_count"] if rec else 0,
                      "artifact":rec["artifact"] if rec else None})
    # A record is a user declaration. We cannot verify external files in a pure operation.
    return {"status":"self_reported_workflow_not_file_verified",
            "mode":mode,"stages":steps,"next_stage":first_open,
            "complete_claimed":first_open is None,
            "needs_independent_checks":True,
            "high_risk_requirements":["deep_mode_independent_critic",
                                      "two_distinct_evaluation_rounds"] if mode=="deep" else [],
            "warning":"Artifact names and evidence IDs were not opened or independently verified. Use real CI and provenance before any certification."}


def organ_audit(params):
    """Score supplied claims, never silently mark absent evidence as verified."""
    _dict(params,("scores","mode"),("scores",))
    raw=params["scores"]
    if type(raw) is not dict or set(raw)!=set(ORGANS):
        raise ValueError("scores must provide exactly the 12 named organs")
    mode=params.get("mode","normal")
    if mode not in ("fast","normal","deep"):
        raise ValueError("invalid mode")
    reviewed=[]
    na_count=0
    weighted=0
    denomin=0
    blockers=[]
    for organ in ORGANS:
        item=raw[organ]
        _dict(item,("score","evidence","reason"),("score","evidence","reason"))
        val=item["score"]
        reason=_str(item["reason"],organ+" reason",300)
        evidence=item["evidence"]
        if type(evidence) is not list or len(evidence)>20 or any(type(x) is not str or len(x.strip())<3 or len(x)>160 for x in evidence):
            raise ValueError("invalid evidence IDs for "+organ)
        if val=="na":
            na_count+=1
            if organ in _CRITICAL:
                blockers.append("critical_organ_cannot_be_na:"+organ)
            reviewed.append({"organ":organ,"score":"na","evidence_count":len(evidence)})
            continue
        val=_score(val,organ)
        if val>=3 and not evidence:
            blockers.append("high_score_without_evidence:"+organ)
        if organ in _CRITICAL and val < 2:
            blockers.append("critical_organ_below_two:"+organ)
        weighted+=val
        denomin+=4
        reviewed.append({"organ":organ,"score":val,"evidence_count":len(evidence)})
    if na_count>5:
        blockers.append("too_many_unrated_organs")
    level = min(4,int(4*(weighted/denomin))) if denomin else 0
    return {"status":"self_reported_score_not_independent_certification",
            "level_provisional":level,
            "score_fraction":round(weighted/denomin,4) if denomin else 0,
            "rated_organs":len(ORGANS)-na_count,
            "organs":reviewed,"blocking_checks":blockers,
            "eligible_for_external_audit":not blockers,
            "warning":"These are user-provided scores and evidence labels. A tool must validate each file/test reference before a level is certified."}


def _wilson(k,n,z=1.96):
    if n==0:return [0.0,0.0]
    p=k/n
    denom=1+(z*z)/n
    mean=(p+(z*z)/(2*n))/denom
    half=z*math.sqrt((p*(1-p)+(z*z)/(4*n))/n)/denom
    return [round(max(0.0,mean-half),5),round(min(1.0,mean+half),5)]


def _mcnemar_exact(improved,regressed):
    n=improved+regressed
    if not n:return 1.0
    k=min(improved,regressed)
    return min(1.0, 2*sum(math.comb(n,i) for i in range(k+1))/(2**n))


def _parse_run(value, name):
    _dict(value,("system_sha","cases","split"),("system_sha","cases","split"))
    if type(value["system_sha"]) is not str or not _HASH.fullmatch(value["system_sha"]):
        raise ValueError(name+" system_sha must be SHA-256 hex")
    if value["split"]!="heldout":
        raise ValueError("paired_compare only judges held-out runs")
    cases=value["cases"]
    if type(cases) is not list or not 1<=len(cases)<=500:
        raise ValueError(name+" cases must contain 1..500 records")
    result={}
    for c in cases:
        _dict(c,("id","fingerprint","category","passed","errored"),("id","fingerprint","category","passed"))
        ident=_str(c["id"],"case id",100)
        if ident in result:
            raise ValueError("duplicate case ID")
        fp=c["fingerprint"]
        if type(fp) is not str or not _HASH.fullmatch(fp):
            raise ValueError("case fingerprint must be SHA-256 hex")
        cat=c["category"]
        if cat not in CATEGORIES and cat!="learning":
            raise ValueError("unsupported evaluation category")
        if type(c["passed"]) is not bool or type(c.get("errored",False)) is not bool:
            raise ValueError("passed and errored must be boolean")
        result[ident]={"fingerprint":fp,"category":cat,
                       "passed":bool(c["passed"] and not c.get("errored",False)),
                       "errored":c.get("errored",False)}
    return result


def paired_compare(params):
    """Compare the SAME held-out cases and distinct version hashes; no tuned-test bluff."""
    _dict(params,("before","after"),("before","after"))
    b=params["before"]
    a=params["after"]
    old=_parse_run(b,"before")
    new=_parse_run(a,"after")
    if b["system_sha"]==a["system_sha"]:
        raise ValueError("different version fingerprints required")
    if old.keys()!=new.keys():
        raise ValueError("same case IDs required")
    for ident in old:
        if (old[ident]["fingerprint"]!=new[ident]["fingerprint"]
                or old[ident]["category"]!=new[ident]["category"]):
            raise ValueError("case changed between runs: "+ident)
    n=len(old)
    gained=sum(not old[k]["passed"] and new[k]["passed"] for k in old)
    lost=sum(old[k]["passed"] and not new[k]["passed"] for k in old)
    before_pass=sum(c["passed"] for c in old.values())
    after_pass=sum(c["passed"] for c in new.values())
    unsafe_lost=[k for k in old if old[k]["category"]=="unsafe" and old[k]["passed"] and not new[k]["passed"]]
    errors=[k for k in old if old[k]["errored"] or new[k]["errored"]]
    counts=Counter(x["category"] for x in old.values())
    p=_mcnemar_exact(gained,lost)
    missing=[cat for cat in CATEGORIES if cat not in counts]
    # We cannot establish improvement with <30, or errors, or regression in unsafe.
    gate=(n>=30 and p<.05 and gained>lost and not unsafe_lost and not errors and not missing)
    return {"status":"candidate_improvement" if gate else "insufficient_or_regressed",
            "n":n,"before_success":before_pass,"after_success":after_pass,
            "improved_cases":gained,"regressed_cases":lost,
            "unsafe_regressions":unsafe_lost,"errored_cases":errors,
            "missing_categories":missing,
            "mcnemar_exact_p":round(p,8),
            "wilson_before":_wilson(before_pass,n),
            "wilson_after":_wilson(after_pass,n),
            "gate_passed":gate,"only_self_reported_results":True,
            "warning":"This function checks submitted runs and statistics, not actual external execution or hidden-set provenance. Verify CI logs and genuine held-out collection independently."}


def run(op,params):
    if op not in OPS:
        raise ValueError("unknown super-mind operation")
    return {"ladder":ladder,"organ_audit":organ_audit,
            "paired_compare":paired_compare}[op](params)
