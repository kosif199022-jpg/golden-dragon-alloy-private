"""SEE-inspired native routing and verification for Red Rose; no remote execution."""
from __future__ import annotations
import argparse, json, re, unicodedata, hashlib
from decimal import Decimal, localcontext
from pathlib import Path
from functools import lru_cache

@lru_cache(maxsize=1)
def profile():
    return json.loads(Path(__file__).with_name("SEE_NATIVE_PROFILE.json").read_text(encoding="utf-8"))

def norm(text):
    text=unicodedata.normalize("NFKD",text.casefold())
    text="".join(c for c in text if not unicodedata.combining(c))
    return " ".join(re.findall(r"\w+",text.translate(str.maketrans("أإآىة","ااايه"))))

def route(request, *, artifact="auto", mode="normal", side_effect=None, gap=None):
    if type(request) is not str or not request.strip() or len(request)>10000:
        raise ValueError("bounded request required")
    if mode not in ("normal","deep","full_pro"):raise ValueError("invalid mode")
    if artifact not in ("auto","image","lyrics","video","code","document","numeric","plugin"):raise ValueError("invalid artifact")
    data=profile()
    if side_effect is not None and side_effect not in data["owners"]:raise ValueError("unknown owner")
    if gap is not None and (type(gap) is not str or not gap.strip() or len(gap)>300):raise ValueError("bounded specialist gap required")
    t=" "+norm(request)+" "
    def has(*terms):return any(" "+norm(x)+" " in t for x in terms)
    branch="standard";forced=[]
    if artifact=="image" or (artifact=="auto" and has("image prompt","ارسم صورة","برومبت صورة","صورة ثابتة")):
        branch="visual_prompt"
    elif artifact=="lyrics" or (artifact=="auto" and has("suno","سونو","كلمات أغنية","كتابة أغاني","lyrics")):
        branch="suno_songwriting";forced=["kosif-media-motion"]
    elif artifact=="video" or (artifact=="auto" and has("مونتاج","فيديو","ريل","موشن","storyboard","video editing")):
        branch="reference_video_imitation" if has("محاكاة فيديو","تقليد الفيديو","نفس المونتاج","نفس الانتقالات","reference video") else "cinematic_motion"
        forced=["kosif-media-motion"]
    elif artifact=="plugin" or has("طور مهارة","ادمج مهارة","تطوير مهارة","plugin self improvement"):
        branch="self_evolution";forced=["kosif-skill-orchestrator","kosif-eval-trust"]
    elif has("هندسة عكسية","reverse engineering","decompile","فك ترجمة الملفات التنفيذية"):
        branch="rea";forced=["kosif-engineering-reliability"]
    elif has("graphify","خريطة الاعتماديات","تحليل تأثير التعديل"):
        branch="graphify";forced=["kosif-engineering-reliability"]
    elif request.lstrip().casefold().startswith(("/optimize","optimize:")) or has("حسن البرومبت","optimize prompt"):
        branch="prompt_optimizer";forced=["kosif-prompt-architecture"]
    elif has("humanizer","صياغة بشرية","خلي الكلام طبيعي","humanize"):
        branch="humanizer";forced=["kosif-research-evidence"]
    elif artifact=="numeric":
        forced=["kosif-finance-data"]
    cap=2 if mode=="normal" else 4
    packs={p["id"]:p for p in data["packs"]}
    scores=[]
    for k,p in packs.items():
        hits=[x for x in p["triggers"] if has(x)]
        if hits:scores.append((-len(hits),k,hits))
    chosen=list(forced)
    # Explicit artifact branches take precedence; add only distinct relevant methods.
    if branch=="standard":
        for _,k,_ in sorted(scores):
            if k not in chosen and len(chosen)<cap:chosen.append(k)
    elif branch=="self_evolution" and mode!="normal":
        for _,k,_ in sorted(scores):
            if k in ("kosif-engineering-reliability","kosif-agent-contracts") and k not in chosen and len(chosen)<cap:chosen.append(k)
    exact=artifact=="numeric" or "kosif-finance-data" in chosen or has("reconciliation","مطابقة","احسب")
    owner_key=side_effect
    if mode=="full_pro" and side_effect is None:owner_key="full_pro"
    if branch=="reference_video_imitation" and owner_key is None:owner_key="reference_video_imitation"
    if branch=="cinematic_motion" and owner_key is None:owner_key="cinematic_motion"
    if branch=="rea" and owner_key is None:owner_key="computer"
    if branch=="graphify" and owner_key is None:owner_key="graphify_knowledge_graph"
    if branch=="prompt_optimizer":owner_key=None
    return {"ok":True,"branch":branch,"stage0":data["stage0"],"packs":[{"id":k,"method":packs[k]["method"],"gate":packs[k]["gate"]} for k in chosen],
            "pack_cap":cap,"exact_numeric_lock_required":exact,"canonical_owner":data["owners"].get(owner_key),
            "dynamic_gap":gap,"dynamic_slots":min(cap-len(chosen),1 if mode=="normal" else 2) if gap else 0,
            "dynamic_status":"discovery_required" if gap else "not_needed","dynamic_loaded":0,
            "runtime_status":"FULL_PRO_BLOCKED" if mode=="full_pro" else "not_probed",
            "executed":False,"verified":False,"approval_granted":False,"output_only":branch=="prompt_optimizer"}

def reconcile(rows):
    """Exact decimal strings, not floats; hash result as a deterministic lock."""
    if type(rows) is not list or not 1<=len(rows)<=10000:raise ValueError("bounded rows required")
    def amount(s):
        if type(s) is not str or not re.fullmatch(r"-?\d{1,24}(?:\.\d{1,8})?",s):raise ValueError("use decimal strings")
        return Decimal(s)
    with localcontext() as ctx:
        ctx.prec=50
        left=Decimal(0);right=Decimal(0)
        for r in rows:
            if type(r) is not dict or set(r)!={"left","right"}:raise ValueError("left/right required")
            left+=amount(r["left"]);right+=amount(r["right"])
        out={"left":format(left,"f"),"right":format(right,"f"),"difference":format(left-right,"f"),"balanced":left==right,"rows":len(rows)}
    out["sha256"]=hashlib.sha256(json.dumps(out,sort_keys=True,separators=(",",":")).encode()).hexdigest()
    return out

def receipt_gate(p):
    """Validate reported progression; never promote a supplied receipt to independent proof."""
    stages=("candidate","selected","method_loaded","executor_exposed","authorized","available","executed","verified")
    if type(p) is not dict or set(p)!={"owner","stages","evidence"}:raise ValueError("owner/stages/evidence required")
    if p["owner"] not in profile()["owners"].values():raise ValueError("unknown owner")
    s=p["stages"];e=p["evidence"]
    if type(s) is not list or s!=list(stages[:len(s)]) or type(e) is not list or len(e)>100:raise ValueError("invalid progression")
    if any(type(x) is not str or not x.strip() or len(x)>300 for x in e):raise ValueError("invalid evidence references")
    return {"ok":bool(s) and len(s)==8 and bool(e),"reported_stage":s[-1] if s else None,"independently_verified":False,
            "note":"Reported state only; actual owner receipts and observed postcondition required."}

def native_gate(action,p):
    """Data-only operations; no new external authority, network or subprocess."""
    if action=="fact-check":
        from rose_see_fact_gate import compare
        if type(p) is not dict or set(p)!={"before","after"} or any(type(x) is not str or len(x)>500000 for x in p.values()):
            raise ValueError("bounded before/after strings required")
        r=compare(p["before"],p["after"])
        return {"ok":r["status"]=="PASS",**r,"semantic_verification":False}
    if action=="graph-impact":
        from rose_see_graph_gate import scan
        if type(p) is not dict or set(p)!={"graph","path","depth"} or type(p["path"]) is not str or not p["path"].strip() or len(p["path"])>500 or type(p["depth"]) is not int or p["depth"] not in (1,2,3):
            raise ValueError("graph, path and depth 1..3 required")
        r=scan(p["graph"],p["path"],p["depth"])
        return {"ok":r["match_count"]>0,**r,"runtime_verified":False}
    if action=="contract":
        from rose_see_contract_gate import validate_receipt
        r=validate_receipt(p)
        return {"ok":r["status"]=="success",**r,"independently_verified":False}
    if action=="lesson-proposal":
        from rose_see_contract_gate import plan_learning
        if type(p) is not dict or set(p)!={"record","consent"} or type(p["consent"]) is not bool:
            raise ValueError("record and explicit consent boolean required")
        r=plan_learning(p["record"],p["consent"])
        return {"ok":r["status"]=="success",**r,"saved":False,"applied":False}
    raise ValueError("unknown native gate")

def handle(a):
    try:
        if a.action=="status":
            p=profile();r={"ok":True,"version":p["version"],"packs":len(p["packs"]),"stage0":len(p["stage0"]),"owner_domains":len(p["owners"]),"scope":p["scope"]}
        else:
            path=Path(a.params or "")
            if not path.is_file() or path.stat().st_size>1024*1024:raise ValueError("bounded input JSON required")
            p=json.loads(path.read_text(encoding="utf-8-sig"))
            r=route(**p) if a.action=="route" else reconcile(p) if a.action=="reconcile" else receipt_gate(p) if a.action=="receipt" else native_gate(a.action,p)
        print(json.dumps(r,ensure_ascii=False,indent=2));return 1 if r.get("ok") is False else 0
    except (ValueError,TypeError,KeyError,OSError) as e:
        print(json.dumps({"ok":False,"error":str(e)},ensure_ascii=False));return 1
def register(sub):
    p=sub.add_parser("see",help="native Stage-0 routing, deterministic locks and reported receipt gates")
    p.add_argument("action",choices=["status","route","reconcile","receipt","fact-check","graph-impact","contract","lesson-proposal"])
    p.add_argument("params",nargs="?")
    p.set_defaults(ext_func=handle)
