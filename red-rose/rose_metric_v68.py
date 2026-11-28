"""V68 cross-source metric comparison: exact arithmetic, explicit definitions, no remote reads or audit opinion."""
from decimal import Decimal,localcontext,InvalidOperation
from datetime import datetime
from pathlib import Path
import json,re
FIELDS=("entity","population","inclusion","period_start","period_end","currency","basis","aggregation")
def txt(x,n=500):
    if type(x)!=str or not x.strip() or len(x)>n:raise ValueError("invalid text")
    return x.strip()
def amount(x):
    if type(x) not in (str,int) or not re.fullmatch(r"-?\d{1,24}(?:\.\d{1,8})?",str(x)):raise ValueError("decimal string or integer required")
    return Decimal(str(x))
def stamp(x):
    t=datetime.fromisoformat(txt(x,80).replace("Z","+00:00"))
    if t.utcoffset() is None:raise ValueError("timezone required")
    return t
def dec(x):return format(x,"f")
def reconcile(j):
    with localcontext() as ctx:
        ctx.prec=64
        metric=txt(j["metric"]);primary=txt(j["primary_id"],80)
        txt(j["authority_basis"]);tol=amount(j["tolerance"])
        if tol<0:raise ValueError("negative tolerance")
        sources=j["sources"]
        if type(sources)!=list or not 2<=len(sources)<=30:raise ValueError("2-30 sources")
        rows={}
        for s in sources:
            sid=txt(s["id"],80)
            if sid in rows:raise ValueError("duplicate source")
            definition=s["definition"]
            if set(definition)!=set(FIELDS):raise ValueError("complete definition required")
            definition={k:txt(definition[k]) for k in FIELDS}
            start,end=stamp(definition["period_start"]),stamp(definition["period_end"])
            if end<=start:raise ValueError("invalid period")
            definition.update(period_start=start.isoformat(),period_end=end.isoformat())
            asof=stamp(s["as_of"])
            if asof<end and j.get("provisional") is not True:raise ValueError("pre-period-end export requires provisional declaration")
            rows[sid]=(amount(s["value"]),definition,asof.isoformat(),s)
        if primary not in rows:raise ValueError("primary missing")
        value,definition,asof,source=rows[primary]
        verify=source.get("recompute")
        reproduced=False
        if verify is not None:
            reproduced=amount(verify["value"])==value and txt(verify["method"])!=txt(source["method"])
            txt(verify["evidence"])
        txt(source["method"]);txt(source["evidence"])
        comparisons=[];unresolved=[]
        for sid,(v,d,a,s) in rows.items():
            if sid==primary:continue
            txt(s["method"]);txt(s["evidence"])
            diff=[k for k in FIELDS if d[k]!=definition[k]]
            delta=value-v
            parts=s.get("components",[])
            if type(parts)!=list or len(parts)>100:raise ValueError("invalid components")
            total=Decimal(0);kinds=set();seen=set()
            for p in parts:
                label=txt(p["label"]);kind=p["kind"]
                if label in seen:raise ValueError("duplicate component")
                seen.add(label)
                if kind not in ("composition","period_boundary"):raise ValueError("unknown component kind")
                txt(p["evidence"]);total+=amount(p["amount"]);kinds.add(kind)
            residual=delta-total
            if "currency" in diff:
                classification="incompatible_currency";residual_out=None;delta_out=None
            else:
                delta_out=dec(delta);residual_out=dec(residual)
                if not diff and abs(delta)<=tol and not parts:classification="within_tolerance"
                elif parts and residual==0 and len(kinds)==1 and kinds=={"period_boundary"} and set(diff)<= {"period_start","period_end"}:classification="period_boundary_claimed"
                elif parts and residual==0 and kinds=={"composition"} and not set(diff)&{"currency","period_start","period_end","entity"}:classification="composition_claimed"
                else:classification="unexplained"
            if classification!="within_tolerance":unresolved.append(sid)
            comparisons.append({"id":sid,"value":dec(v),"as_of":a,"definition_differences":diff,"delta_primary_minus_comparison":delta_out,"component_total":dec(total) if delta_out is not None else None,"residual":residual_out,"classification":classification,"evidence_independently_verified":False})
        return {"metric":metric,"primary_id":primary,"primary_value":dec(value),"primary_as_of":asof,"primary_definition":definition,"tolerance":dec(tol),"primary_recomputed_from_supplied_values":reproduced,"comparisons":comparisons,"review_required":bool(unresolved or not reproduced or j.get("provisional") is True),"unresolved_sources":unresolved,"final_certified_value":None,"no_average":True,"source_evidence_verified":False,"execution_allowed":False,"note":"Supplied definitions and evidence references are claims. Matching arithmetic is not source verification or an audit opinion. Review evidence before choosing a final figure."}
def handle(a):
    try:
        p=Path(a.spec)
        if p.stat().st_size>256*1024:raise ValueError("input too large")
        print(json.dumps(reconcile(json.loads(p.read_text(encoding="utf-8"))),ensure_ascii=False));return 0
    except (ValueError,KeyError,TypeError,OSError,InvalidOperation) as e:print(json.dumps({"error":str(e)[:300]}));return 1
def register(sub):
    p=sub.add_parser("metric-reconcile",help="read-only cross-source metric reconciliation")
    p.add_argument("spec");p.set_defaults(ext_func=handle)
