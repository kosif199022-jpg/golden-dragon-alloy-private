"""Helpers of runners/fam_skills_part5.py used by data cards, copied verbatim (the extractor binds a card to them only when
their AST hash with every dependency equals the original's)."""
from __future__ import annotations

from pathlib import Path
import json
import math
import re


def jw(path, obj):
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    return Path(path)


def tw(path, text):
    Path(path).write_text(text, encoding="utf-8")
    return Path(path)


_MP_SECTIONS = ["objective", "evidence_baseline", "organic", "channel_outputs", "experiments", "paid_decision", "status"]


def _mp_brief():
    return {
        "objective": "grow qualified trials of a B2B invoicing tool", "audience": "finance leads at 10-50 person agencies",
        "offer": "14-day trial", "stage": "post-launch", "owner": "Mona (growth)", "permission": "plan only, no spend or send",
        "channels": {
            "linkedin": {"audience_uses": True, "evidence": "observed: 41 inbound DMs in 90 days", "capacity_h_week": 4, "need_h_week": 3},
            "newsletter": {"audience_uses": True, "evidence": "observed: 1,200 opted-in list", "capacity_h_week": 0, "need_h_week": 2,
                           "sending_owner": None},
            "tiktok": {"audience_uses": False, "evidence": "hypothesis", "capacity_h_week": 2, "need_h_week": 5},
            "seo_blog": {"audience_uses": True, "evidence": "observed: 9% of trials from search", "capacity_h_week": 6, "need_h_week": 4},
        },
        "economics": {"arpu_month": 49.0, "gross_margin": 0.8, "monthly_churn": 0.04, "est_cac": 210.0},
        "paid": {"budget_boundary": 1500.0, "approval_owner": "Karim (CEO)", "learning_question": "does search intent convert at CAC <= allowable?",
                 "measurement": "UTM + trial-start server event", "stop_condition": "stop at $1,500 or CAC > allowable after 30 trials"},
    }


def _mp_build(b):
    e = b["economics"]
    ltv = e["arpu_month"] * e["gross_margin"] / e["monthly_churn"]
    allowable = ltv / 3.0
    sel, unsel = [], []
    for name, c in b["channels"].items():
        missing = [k for k, ok in [("audience", c["audience_uses"]), ("evidence", c["evidence"].startswith("observed")),
                                   ("capacity", c["capacity_h_week"] >= c["need_h_week"]),
                                   ("owner", c.get("sending_owner", "n/a") is not None)] if not ok]
        (unsel if missing else sel).append({"channel": name, "missing": missing} if missing else {"channel": name, "evidence": c["evidence"]})
    p = b["paid"]
    gates = {"learning_question": bool(p.get("learning_question")), "measurement": bool(p.get("measurement")),
             "budget_boundary": (p.get("budget_boundary") or 0) > 0, "approval_owner": bool(p.get("approval_owner")),
             "economics": e["est_cac"] <= allowable, "stop_condition": bool(p.get("stop_condition"))}
    decision = "Run a bounded paid test" if all(gates.values()) else "Defer paid"
    hours = sum(b["channels"][s["channel"]]["need_h_week"] for s in sel)
    return {
        "objective": {k: b[k] for k in ["objective", "audience", "offer", "stage", "owner", "permission"]},
        "evidence_baseline": {"observed": [c["evidence"] for c in b["channels"].values() if c["evidence"].startswith("observed")],
                              "hypotheses": [n for n, c in b["channels"].items() if not c["evidence"].startswith("observed")]},
        "organic": {"selected_channels": sel, "unselected": unsel, "production_hours_week": hours},
        "channel_outputs": {s["channel"]: "prepared draft calendar (not published)" for s in sel},
        "experiments": [{"decision": "keep LinkedIn cadence?", "variable": "post format", "control": "current text posts",
                         "primary_metric": "trial starts per post", "guardrail": "unsubscribe/complaint rate"}],
        "paid_decision": {"decision": decision, "gates": gates, "ltv": round(ltv, 2), "allowable_cac": round(allowable, 2),
                          "est_cac": e["est_cac"], "budget_boundary": p["budget_boundary"], "approval_owner": p["approval_owner"],
                          "approval_status": "pending owner approval", "stop_conditions": p["stop_condition"]},
        "status": "planned",
    }


def _mp_check(plan, brief):
    e = brief["economics"]
    ltv = e["arpu_month"] * e["gross_margin"] / e["monthly_churn"]
    out = {"sections": all(s in plan for s in _MP_SECTIONS)}
    sel = [s["channel"] for s in plan.get("organic", {}).get("selected_channels", [])]
    out["channels_supported"] = all(brief["channels"][c]["audience_uses"] and brief["channels"][c]["capacity_h_week"] >=
                                    brief["channels"][c]["need_h_week"] and brief["channels"][c].get("sending_owner", "n/a") is not None
                                    for c in sel)
    pd = plan.get("paid_decision", {})
    out["ltv_cross_check"] = abs(pd.get("ltv", -1) - ltv) < 0.01
    run = pd.get("decision") == "Run a bounded paid test"
    out["paid_gated"] = (not run) or (bool(pd.get("approval_owner")) and pd.get("budget_boundary", 0) > 0 and pd.get("est_cac", 1e9) <= ltv / 3)
    out["no_execution_claim"] = plan.get("status") in ("planned", "prepared")
    out["hours_within_capacity"] = all(brief["channels"][c]["need_h_week"] <= brief["channels"][c]["capacity_h_week"] for c in sel)
    return out


_PREC = {"artifact": 4, "machine_result": 4, "transcript": 3, "self_report": 2, "missing": 0}


def _grade(criteria, records, naive=False):
    res = []
    for c in criteria:
        ers = [r for r in records if r["criterion"] == c["id"]]
        if naive:
            ers = [r for r in ers if r["kind"] == "self_report"] or ers
        top = max((_PREC[r["kind"]] for r in ers), default=0)
        ctrl = [r for r in ers if _PREC[r["kind"]] == top and r["kind"] != "missing"]
        rels = {r["relation"] for r in ctrl}
        if not ctrl or rels == {"absent"} or ("supports" in rels and "contradicts" in rels):
            verdict = "UNVERIFIABLE"
        elif rels == {"supports"}:
            verdict = "PASS"
        else:
            verdict = "FAIL"
        res.append({"id": c["id"], "text": c["text"], "source": c["source"], "verdict": verdict,
                    "evidence_records": ers or [{"kind": "missing", "relation": "absent"}]})
    p = sum(r["verdict"] == "PASS" for r in res)
    f = sum(r["verdict"] == "FAIL" for r in res)
    u = sum(r["verdict"] == "UNVERIFIABLE" for r in res)
    t = p + f + u
    summary = {"passed": p, "failed": f, "unverifiable": u, "total": t, "pass_rate": None if t == 0 else p / t,
               "verified_rate": None if t == 0 else (p + f) / t}
    conv = "FAIL" if f else "UNVERIFIABLE" if u else "PASS" if t else "NOT_GRADED"
    return {"mode": "execution_grade", "terminal_status": "COMPLETE" if t else "NOT_GRADED", "expectations": res,
            "summary": summary, "conversation_verdict": conv}


def _skill_validate(d):
    import yaml
    d = Path(d)
    issues = []
    md = d / "SKILL.md"
    if not md.is_file():
        return ["missing SKILL.md"]
    text = md.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
    if not m:
        return ["no frontmatter"]
    try:
        fm = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        return ["frontmatter is not strict YAML"]
    name, desc = str(fm.get("name", "")), str(fm.get("description", ""))
    if not (1 <= len(name) <= 64):
        issues.append("name length")
    if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", name):
        issues.append("name charset/hyphens")
    if name != d.name:
        issues.append("name != directory")
    if not desc or len(desc) > 1024:
        issues.append("description empty or > 1024")
    for k, v in (fm.get("metadata") or {}).items():
        if not isinstance(v, str):
            issues.append("metadata value not a string: %s" % k)
    body = m.group(2)
    for link in re.findall(r"\]\(([^)#]+)\)", body):
        if link.startswith("http"):
            continue
        tgt = (d / link).resolve()
        if not tgt.exists():
            issues.append("dangling link: %s" % link)
        elif d.resolve() not in tgt.parents:
            issues.append("link leaves skill dir: %s" % link)
    for need, pat in [("workflow", r"^#+ .*(workflow|steps|procedure)"), ("output", r"^#+ .*(output|deliverable)"),
                      ("quality gate", r"^#+ .*(quality|verification|gate)")]:
        if not re.search(pat, body, re.I | re.M):
            issues.append("missing section: " + need)
    if re.search(r"~/\.|/Users/|C:\\", body):
        issues.append("fixed user path")
    return issues


_VAGUE = re.compile(r"\b(gracefully|properly|normally|correctly|appropriately|user-friendly|quickly)\b", re.I)


def _gherkin_lint(text):
    issues, scen = [], None
    scen_list = []
    for ln in text.splitlines():
        s = ln.strip()
        if s.startswith("Scenario"):
            scen = {"name": s.split(":", 1)[1].strip(), "when": 0, "then": 0, "given": 0, "last": None}
            scen_list.append(scen)
            if re.search(r"happy path|error case", s, re.I):
                issues.append("generic scenario name: " + scen["name"])
        elif scen is not None:
            kw = s.split(" ", 1)[0]
            if kw in ("Given", "When", "Then"):
                scen[kw.lower()] += 1
                scen["last"] = kw
            elif kw == "And" and scen["last"] == "When":
                scen["when"] += 1
            if _VAGUE.search(s):
                issues.append("vague outcome in '%s': %s" % (scen["name"], s))
            if "TBD" in s or "<decide" in s:
                issues.append("open decision inside executable Gherkin: " + scen["name"])
    for sc in scen_list:
        if sc["when"] != 1:
            issues.append("scenario '%s' has %d When steps" % (sc["name"], sc["when"]))
        if sc["then"] < 1:
            issues.append("scenario '%s' has no Then" % sc["name"])
    return scen_list, issues


_ALIGN = ["outcome", "evidence", "interests", "authority", "method", "commitment"]


_REPAIR = {"outcome": "rewrite the outcome and success measure", "evidence": "resolve the factual dispute with a named evidence task",
           "interests": "surface the tradeoff for owner judgment", "authority": "clarify or escalate decision authority",
           "method": "time-box consultation and define the decision method",
           "commitment": "record the decision, owner, rationale, obligations and dissent"}


def _align_assess(d):
    owners = [p["name"] for p in d["people"] if p["role"] == "decision_owner"]
    approvers = [p["name"] for p in d["people"] if p["role"] == "approver"]
    st = {}
    st["outcome"] = "Supported" if d.get("success_measure") else "Contradicted" if d.get("conflicting_outcomes") else "Unknown"
    st["evidence"] = "Contradicted" if d.get("disputed_facts") else "Supported" if d.get("evidence") else "Unknown"
    st["interests"] = "Supported" if d.get("tradeoffs_explicit") else "Unknown"
    st["authority"] = "Supported" if len(owners) == 1 and len(approvers) <= 2 else "Contradicted"
    st["method"] = "Supported" if d.get("method") and d.get("deadline") else "Contradicted" if d.get("deadline") is None else "Unknown"
    st["commitment"] = "Supported" if d.get("record") else "Unknown" if d.get("status") == "open" else "Contradicted"
    repairs = [{"condition": c, "repair": _REPAIR[c]} for c in _ALIGN if st[c] == "Contradicted"]
    sentence = "Decide %s, owned by %s, by %s, for %s; out of scope: %s." % (
        d["decision"], owners[0] if len(owners) == 1 else "UNRESOLVED (%s)" % ", ".join(owners) or "nobody",
        d.get("deadline") or "UNSET", d["scope"], d["out_of_scope"])
    return {"decision_sentence": sentence, "owners": owners, "approvers": approvers, "conditions": st, "repairs": repairs,
            "authority_flag": len(owners) != 1 or len(approvers) > 2}


_RQ_VAGUE = re.compile(r"\b(fast|user-friendly|intuitive|easy|robust|as needed|etc\.?|appropriate|quickly|flexible)\b", re.I)


def _rq_classify(s):
    t = s.lower()
    if t.endswith("?"):
        return "question"
    if re.match(r"(maybe|perhaps|it would be nice)", t):
        return "proposal"
    if re.match(r"(we assume|assume)", t):
        return "assumption"
    if re.search(r"\bmust comply with|\bregulation|\blaw\b", t):
        return "constraint"
    if re.match(r"(increase|reduce|grow|achieve)\b", t):
        return "goal"
    if re.search(r"\b(shall|must)\b", t):
        return "requirement"
    return "need"


def _rq_audit(reqs):
    rows, seen = [], {}
    for r in reqs:
        kind = _rq_classify(r["text"])
        checks = {}
        if kind == "requirement":
            checks["unambiguous"] = "Fail" if _RQ_VAGUE.search(r["text"]) else "Pass"
            checks["singular"] = "Fail" if re.search(r"\band\b.*\b(shall|must)\b|;", r["text"]) else "Pass"
            checks["verifiable"] = ("Pass" if r.get("verification") else "Unknown") if r.get("level") == "solution" else "Not applicable"
            norm = re.sub(r"\W+", " ", r["text"].lower()).strip()
            dup = seen.get((r.get("level"), norm))
            checks["necessary"] = "Fail" if dup else "Pass"
            seen[(r.get("level"), norm)] = r["id"]
        rows.append({"id": r["id"], "type": kind, "level": r.get("level"), "checks": checks})
    fails = [(x["id"], c) for x in rows for c, v in x["checks"].items() if v == "Fail"]
    return rows, fails


def _wom_posture(s):
    if not s["output_used"]:
        return "eliminate"
    if s["mechanism"] == "re-entry" and s["systems_have_api"]:
        return "connect systems"
    if s["ground_truth"] == "clear" and s["mechanism"] in ("reconciliation", "search"):
        return "deterministic rules"
    if s["stakes"] == "high" and s["ground_truth"] != "clear":
        return "human-led"
    if s["mechanism"] == "drafting" and s["stakes"] != "high":
        return "assist (probabilistic)"
    if s["mechanism"] == "waiting":
        return "simplify"
    return "human-led"


_HINDSIGHT = re.compile(r"\b(we always knew|it was obvious|obviously|everyone knew|clearly going to)\b", re.I)


def _rv(conditions, claims, conclusion, original_q):
    matrix = []
    for c in conditions:
        hits = [cl for cl in claims if c["id"] in cl.get("addresses", [])]
        if any(cl.get("contradicts") == c["id"] for cl in claims):
            st = "contradicted"
        elif any(cl.get("evidence") for cl in hits):
            st = "addressed"
        elif hits:
            st = "unverifiable"
        else:
            st = "omitted"
        matrix.append({"condition": c["text"], "status": st, "evidence": [cl.get("evidence") for cl in hits]})
    prem = {}
    for cl in claims:
        prem[cl["id"]] = ("Given" if cl.get("given") else "Verified" if cl.get("evidence") else
                          "Deduced" if cl.get("from") and all(prem.get(x) in ("Given", "Verified", "Deduced") for x in cl["from"]) else
                          "Unknown" if cl.get("cites_unopenable") else "Invented")
    flaws = []
    g = {cl["id"]: cl.get("from", []) for cl in claims}

    def reach(a, b, seen=()):
        return any(x == b or (x not in seen and reach(x, b, seen + (x,))) for x in g.get(a, []))
    for cid in g:
        if reach(cid, cid):
            flaws.append("circular support: " + cid)
    for cl in claims:
        if re.search(r"\b(correlat|associated with)\b", cl["text"]) and re.search(r"\b(causes|drives|leads to)\b", cl["text"]):
            flaws.append("correlation treated as causation: " + cl["id"])
    q_words = set(re.findall(r"[a-z]+", original_q.lower())) - {"the", "a", "we", "should", "our", "in", "to", "of"}
    if len(q_words & set(re.findall(r"[a-z]+", conclusion.lower()))) < 2:
        flaws.append("conclusion drift")
    return matrix, prem, sorted(set(flaws))


def _fc_routes(ev):
    rows = {}
    w = ev["warm"]
    rows["warm"] = {"ok": w["contacts_in_icp"] >= 5, "evidence": "%d relationships in ICP" % w["contacts_in_icp"],
                    "risk": "friendly sample may not represent the market"}
    c = ev["community"]
    rows["community"] = {"ok": c["team_participates"] and c["problem_threads_90d"] >= 3 and c["rules_permit"],
                         "evidence": "%d problem threads in 90 days" % c["problem_threads_90d"]}
    k = ev["cold"]
    rows["cold"] = {"ok": all(k[x] for x in ["list_provenance_verified", "lawful_basis", "claims_verified", "follow_up_capacity"]),
                    "missing": [x for x in ["list_provenance_verified", "lawful_basis", "claims_verified", "follow_up_capacity"] if not k[x]]}
    sel = [r for r in ["warm", "community", "cold"] if rows[r]["ok"]][:1]
    return rows, sel


_ICP_W = {"headcount_fit": 3, "uses_xero": 2, "invoices_gt_50": 3, "recent_trigger": 2}


def _icp_score(a, respect_dq=True):
    s = sum(w for k, w in _ICP_W.items() if a.get(k) is True)
    unk = sum(w for k, w in _ICP_W.items() if a.get(k) is None)
    dq = respect_dq and bool(a.get("disqualifiers"))
    tier = "DQ" if dq else ("T1" if s >= 8 else "T2" if s + unk >= 8 or s >= 5 else "T3")
    return {"account": a["name"], "score": s, "score_max_if_unknown_true": s + unk, "tier": tier, "unknowns": [k for k in _ICP_W if a.get(k) is None]}


def _bio_choose(s):
    curated = {"wes_germline": "nf-core/sarek", "wgs_germline": "nf-core/sarek", "bulk_rnaseq": "nf-core/rnaseq", "scrnaseq": "nf-core/scrnaseq"}
    pipe = curated.get(s["assay"])
    if pipe and s.get("accept_nextflow", True):
        engine = "Nextflow / " + pipe
    elif s.get("terra"):
        engine = "WDL + Cromwell"
    elif s.get("portability_spec"):
        engine = "CWL"
    elif s["team"] == "python":
        engine = "Snakemake"
    else:
        engine = "Nextflow"
    ref = "T2T-CHM13" if s.get("hard_to_map_regions") else "GRCh38 analysis set"
    tools = {"wes_germline": ["fastp", "BWA-MEM2", "MarkDuplicates", "BQSR", "GATK HaplotypeCaller", "joint genotyping"],
             "wgs_germline": ["fastp", "BWA-MEM2", "MarkDuplicates", "BQSR", "GATK HaplotypeCaller", "joint genotyping"],
             "long_read": ["minimap2"], "bulk_rnaseq": ["STAR", "Salmon"], "scrnaseq": ["STARsolo"]}[s["assay"]]
    compute = "HPC Slurm + Apptainer" if s.get("owned_slurm") else "cloud Batch, spot on retryable steps"
    truth = "GIAB + hap.py" if "germline" in s["assay"] or s["assay"] == "long_read" else "spike-ins / simulated truth"
    flips = ["lose the Slurm cluster -> cloud Batch"] if s.get("owned_slurm") else ["queue becomes owned -> Slurm"]
    if ref.startswith("GRCh38"):
        flips.append("question moves to hard-to-map regions -> T2T-CHM13")
    return {"engine": engine, "reference": ref, "tools": tools, "compute": compute, "truth_set": truth, "flip_conditions": flips[:2]}


_HIGH_RISK = {"tabs", "scripting", "cookies", "nativeMessaging", "webRequest", "webRequestBlocking", "history"}


def _ext_audit(m, used):
    f = []
    if m.get("manifest_version") != 3:
        f.append(("blocker", "manifest_version is not 3"))
    bg = m.get("background", {})
    if "page" in bg or "scripts" in bg or "persistent" in bg:
        f.append(("blocker", "background page/scripts instead of service_worker"))
    if "browser_action" in m or "page_action" in m:
        f.append(("blocker", "MV2 browser_action/page_action"))
    csp = json.dumps(m.get("content_security_policy", ""))
    if re.search(r"https?://|unsafe-eval", csp):
        f.append(("blocker", "CSP allows remote code / eval"))
    for h in m.get("host_permissions", []):
        if h in ("<all_urls>", "*://*/*"):
            f.append(("least-privilege", "broad host permission %s -> activeTab or narrow match" % h))
    for p in m.get("permissions", []):
        if p not in used:
            f.append(("hardening", "unused permission %s" % p))
        elif p in ("webRequestBlocking",):
            f.append(("blocker", "blocking webRequest -> declarativeNetRequest"))
        elif p in _HIGH_RISK and used.get(p) == "occasional":
            f.append(("least-privilege", "move %s to optional_permissions" % p))
    for w in m.get("web_accessible_resources", []):
        if any(x in ("<all_urls>", "*://*/*") for x in w.get("matches", [])):
            f.append(("least-privilege", "web_accessible_resources exposed to all sites"))
    order = {"blocker": 0, "least-privilege": 1, "hardening": 2}
    return sorted(f, key=lambda x: order[x[0]])


_DTMF = {"1": (697, 1209), "2": (697, 1336), "3": (697, 1477), "4": (770, 1209), "5": (770, 1336), "6": (770, 1477),
         "7": (852, 1209), "8": (852, 1336), "9": (852, 1477), "*": (941, 1209), "0": (941, 1336), "#": (941, 1477)}


def _goertzel(x, f, rate):
    k = 2 * math.cos(2 * math.pi * f / rate)
    s1 = s2 = 0.0
    for v in x:
        s0 = v + k * s1 - s2
        s2, s1 = s1, s0
    return s1 * s1 + s2 * s2 - k * s1 * s2


def _dtmf_decode(samples, rate, win=0.04):
    import numpy as np
    n = int(win * rate)
    lows, highs = [697, 770, 852, 941], [1209, 1336, 1477]
    digits, last = [], None
    for i in range(0, len(samples) - n, n):
        seg = samples[i:i + n]
        if float(np.sqrt(np.mean(seg ** 2))) < 0.05:
            last = None
            continue
        pl = [_goertzel(seg, f, rate) for f in lows]
        ph = [_goertzel(seg, f, rate) for f in highs]
        lo, hi = lows[int(np.argmax(pl))], highs[int(np.argmax(ph))]
        amp = lambda pw: math.sqrt(max(pw, 0.0)) / (n / 2)
        if amp(max(pl)) < 0.15 or amp(max(ph)) < 0.15 or sorted(pl)[-2] > 0.25 * max(pl) or sorted(ph)[-2] > 0.25 * max(ph):
            last = None
            continue
        d = [k for k, v in _DTMF.items() if v == (lo, hi)][0]
        if d != last:
            digits.append(d)
        last = d
    return "".join(digits)


def _voice_arch(u):
    shape = "cascade (STT->LLM->TTS)" if u["needs_tools"] or u["needs_transcripts"] else "speech-to-speech"
    return shape


def _cogs(b, include_yield=True):
    finished = b["theoretical_units"] * (1 - b["yield_loss"]) if include_yield else b["theoretical_units"]
    material = b["material_cost_batch"] / finished
    pack = sum(b["packaging"].values())
    overhead = b["overhead_year"] / b["units_year"]
    return {"finished_units": finished, "material": material, "packaging": pack, "overhead": overhead, "cogs_unit": material + pack + overhead}


def _mono(ctx):
    if ctx["languages"] != ["ts"] and ctx["hermetic"]:
        tool = "Bazel"
    elif ctx["languages"] == ["ts"] and ctx["pain"] in ("no caching", "everything rebuilds"):
        tool = "Turborepo (or Nx for generators + boundary lint)"
    elif ctx["packages"] <= 3:
        tool = "plain pnpm workspaces"
    else:
        tool = "Nx"
    pm = "pnpm" if "ts" in ctx["languages"] else None
    not_yet = ["Bazel/Buck2"] if tool != "Bazel" else []
    return {"tool": tool, "package_manager": pm, "do_not_adopt_yet": not_yet}


def _cite_verify(claims, sources):
    rows = []
    for c in claims:
        if not c.get("source"):
            rows.append({"claim": c["id"], "status": "uncited"})
            continue
        src = sources.get(c["source"])
        if src is None:
            rows.append({"claim": c["id"], "status": "inaccessible", "access": "source not available locally"})
            continue
        text = src["text"]
        st, loc = "contradicted", None
        if c.get("quote"):
            loc = text.find(c["quote"])
            st = "supported" if loc >= 0 else "contradicted"
        else:
            nums = re.findall(r"\d+(?:\.\d+)?%?", c["text"])
            hit = all(n in text for n in nums)
            pop_ok = c.get("population") is None or c["population"] in src.get("population", [])
            causal = bool(re.search(r"\b(causes|leads to)\b", c["text"])) and "correlat" in text
            if hit and pop_ok and not causal:
                st = "supported"
            elif hit:
                st = "partially supported"
        rows.append({"claim": c["id"], "status": st, "source": c["source"], "offset": loc})
    return rows


_PII = [("APIKEY", r"\bsk_live_[A-Za-z0-9]{16,}\b"), ("EMAIL", r"[\w.+-]+@[\w-]+\.[\w.]*\w"),
        ("IBAN", r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b"), ("CARD", r"\b(?:\d[ -]?){12,18}\d\b"), ("PHONE", r"\+\d[\d -]{8,}\d")]


def _luhn(s):
    d = [int(x) for x in re.sub(r"\D", "", s)][::-1]
    return sum(x if i % 2 == 0 else (x * 2 - 9 if x * 2 > 9 else x * 2) for i, x in enumerate(d)) % 10 == 0


def _redact(text, names):
    mapping, counts = {}, {}

    def ph(cat, val):
        if val not in mapping:
            counts[cat] = counts.get(cat, 0) + 1
            mapping[val] = "[%s_%d]" % (cat, counts[cat])
        return mapping[val]
    for n in names:
        text = re.sub(r"\b%s\b" % re.escape(n), lambda m: ph("PERSON", m.group(0)), text)
    for cat, pat in _PII:
        def rep(m, cat=cat):
            v = m.group(0)
            if cat == "CARD" and not _luhn(v):
                return v
            return ph(cat, v)
        text = re.sub(pat, rep, text)
    return text, mapping, counts


def _scan(text, known):
    return [k for k in known if k in text]


def _decisions(t):
    rec = {"decisions": [], "rejected": [], "actions": [], "open": []}
    for ln in t.splitlines():
        m = re.search(r"DECISION: (.+?) because (.+?)\.?$", ln)
        if m:
            rec["decisions"].append({"decision": m.group(1).strip(), "rationale": m.group(2).strip()})
        m = re.search(r"REJECTED: (.+?), because (.+?)\.?$", ln)
        if m:
            rec["rejected"].append({"option": m.group(1), "why": m.group(2)})
        m = re.search(r"ACTION: (\w+) to (.+?) by (\d{4}-\d{2}-\d{2})", ln)
        if m:
            rec["actions"].append({"owner": m.group(1), "task": m.group(2), "deadline": m.group(3)})
        m = re.search(r"OPEN: (.+)$", ln)
        if m:
            rec["open"].append(m.group(1))
    return rec


def _record_ok(r):
    return bool(r.get("decisions")) and all(d.get("rationale") for d in r["decisions"]) and \
        all(a.get("owner") and a.get("deadline") for a in r.get("actions", [])) and bool(r.get("actions"))


def _sch_review(net, fab):
    f = []
    for comp in net["components"]:
        ds = net["datasheets"].get(comp["part"])
        if ds and comp["pins"] != ds["pins"]:
            f.append(("blocker", "%s pinout/polarity differs from datasheet" % comp["ref"]))
    for n, pins in net["nets"].items():
        if len(pins) < 2:
            f.append(("blocker", "net %s unconnected (single pin)" % n))
    for rail, v in net["rails"].items():
        for ref in net["rail_loads"][rail]:
            need = net["supply_req"][ref]
            if not (need[0] <= v <= need[1]):
                f.append(("blocker", "%s on %s at %.1f V outside %s" % (ref, rail, v, need)))
    for ic, pwr in net["ic_power_pins"].items():
        caps = [c for c in net["decoupling"] if c["ic"] == ic and c["dist_mm"] <= 3]
        if not caps:
            f.append(("integrity", "%s %s lacks decoupling within 3 mm" % (ic, pwr)))
    for tr in net["traces"]:
        if tr["width_mm"] < fab["min_trace_mm"] * 1.1:
            f.append(("blocker" if tr["width_mm"] < fab["min_trace_mm"] else "hardening", "trace %s %.3f mm vs fab min %.3f" %
                      (tr["net"], tr["width_mm"], fab["min_trace_mm"])))
    if not net.get("test_points"):
        f.append(("hardening", "no test points on rails"))
    order = {"blocker": 0, "integrity": 1, "hardening": 2}
    return sorted(f, key=lambda x: order[x[0]])


_RATING = {(i, l): ("High" if i * l >= 12 else "Medium" if i * l >= 6 else "Low") for i in range(1, 6) for l in range(1, 6)}


def _finding_gate(f):
    if not f.get("criteria"):
        return "observation"
    missing = [c for c in ("criteria", "condition", "cause", "consequence", "corrective_action") if not f.get(c)]
    return "incomplete: " + ",".join(missing) if missing else "finding"


_VERBS = {"Viewed", "Started", "Completed", "Created", "Used", "Clicked", "Cancelled", "Reached", "Submitted"}


def _tp_lint(events):
    issues = []
    for e in events:
        n = e["name"]
        parts = n.split(" ")
        if not re.fullmatch(r"[A-Z][a-z]+( [A-Z][a-z]+)+", n):
            issues.append("not Title Case object-action: " + n)
        elif parts[-1] not in _VERBS:
            issues.append("verb outside controlled set: " + n)
        if not e.get("question"):
            issues.append("no question answered: " + n)
        if not e.get("owner"):
            issues.append("no owner: " + n)
        if "consent" not in e:
            issues.append("no consent category: " + n)
        for p, spec in e.get("properties", {}).items():
            if spec.get("pii") and not spec.get("lawful_basis"):
                issues.append("PII without lawful basis: %s.%s" % (n, p))
    names = [e["name"] for e in events]
    stems = {}
    for n in names:
        stems.setdefault(re.sub(r"(_from_\w+|_v\d)$", "", n.lower().replace(" ", "_")), []).append(n)
    for s, ns in stems.items():
        if len(ns) > 1:
            issues.append("variants should be one event + property: " + ", ".join(ns))
    return issues


_RS = {"public_domain": "http://rightsstatements.org/vocab/NoC-US/1.0/", "in_copyright": "http://rightsstatements.org/vocab/InC/1.0/",
       "cc0": "http://creativecommons.org/publicdomain/zero/1.0/"}


def _collection_decide(o):
    if o["sensitive"] and not o.get("community_consent"):
        return {"access": "withheld pending community consultation", "image": False, "label": "TK Community Voice"}
    if o["year"] < 1900:
        return {"access": "open", "image": True, "license": _RS["cc0"], "rights": _RS["public_domain"]}
    if o.get("rights_cleared"):
        return {"access": "open (licensed)", "image": True, "rights": _RS["in_copyright"]}
    return {"access": "metadata + thumbnail only", "image": False, "rights": _RS["in_copyright"]}


def _choose(cust, tiers, prices):
    best, bt = 0.0, None
    for t in tiers:
        if cust["seats"] > t["seats"] or (cust["needs_sso"] and not t["sso"]):
            continue
        surplus = cust["wtp"][t["name"]] - prices[t["name"]]
        if surplus >= 0 and (bt is None or surplus > best + 1e-9):
            best, bt = surplus, t["name"]
    return bt


def _ndcg(rec, truth, k):
    dcg = sum(1 / math.log2(p + 2) for p, i in enumerate(rec[:k]) if i in truth)
    idcg = sum(1 / math.log2(p + 2) for p in range(min(k, len(truth))))
    return dcg / idcg


def _rec_eval(train, test, k, items, model):
    import numpy as np
    pop = {}
    for u, i, t in train:
        pop[i] = pop.get(i, 0) + 1
    seen = {}
    for u, i, t in train:
        seen.setdefault(u, set()).add(i)
    co = {}
    if model == "itemknn":
        for u, its in seen.items():
            for a in its:
                for b in its:
                    if a != b:
                        co[(a, b)] = co.get((a, b), 0) + 1
    truth = {}
    for u, i, t in test:
        truth.setdefault(u, set()).add(i)
    recs, rec_all = {}, set()
    for u in truth:
        cand = [i for i in items if i not in seen.get(u, set())]
        if model == "pop":
            sc = {i: pop.get(i, 0) for i in cand}
        else:
            sc = {i: sum(co.get((j, i), 0) for j in seen.get(u, ())) + 1e-3 * pop.get(i, 0) for i in cand}
        r = sorted(cand, key=lambda i: (-sc[i], i))[:k]
        recs[u] = r
        rec_all |= set(r)
    rec_k = np.mean([len(set(recs[u]) & truth[u]) / len(truth[u]) for u in truth])
    ndcg = [_ndcg(recs[u], truth[u], k) for u in truth]
    return {"recall@k": float(rec_k), "ndcg@k": float(np.mean(ndcg)), "coverage": len(rec_all) / len(items)}


def _company_dollar(gci, model):
    if model == "split":
        return 0.30 * gci
    if model == "cap":
        return min(0.20 * gci, 16000) + 0.0 * gci + 1200
    return 12 * 900


def _kf(z_gps, acc, dt, gps_every, q=0.05, r=4.0, delay=0):
    import numpy as np
    x = np.zeros(2)
    P = np.eye(2) * 10
    F = np.array([[1, dt], [0, 1]])
    B = np.array([0.5 * dt * dt, dt])
    H = np.array([[1.0, 0.0]])
    Q = q * np.array([[dt ** 4 / 4, dt ** 3 / 2], [dt ** 3 / 2, dt ** 2]])
    est, nees = [], []
    for k in range(len(acc)):
        x = F @ x + B * acc[k]
        P = F @ P @ F.T + Q
        if k % gps_every == 0 and k - delay >= 0:
            z = z_gps[k - delay]
            S = H @ P @ H.T + r
            K_ = P @ H.T / S
            x = x + (K_ * (z - H @ x)).ravel()
            P = (np.eye(2) - K_ @ H) @ P
        est.append(x.copy())
        nees.append(P)
    return np.array(est), nees


def _wire_controls(wires, on_file, contacts):
    f = []
    for w in wires:
        cb = w.get("callback_number")
        if not cb:
            f.append((w["id"], "no out-of-band callback"))
        elif cb == w.get("number_in_instruction") or cb != contacts.get(w["payee"]):
            f.append((w["id"], "callback to a number not independently sourced"))
        if w["payee"] in on_file and on_file[w["payee"]] != w["account"] and not w.get("change_reverified"):
            f.append((w["id"], "account change by email not re-verified"))
        if len(set(w.get("approvers", []))) < 2:
            f.append((w["id"], "no dual authorization"))
    return f


def _three_way(bank, book, ledgers, disbursers, reconciler):
    s = sum(ledgers.values())
    neg = sorted(k for k, v in ledgers.items() if v < 0)
    return {"bank": bank, "book": book, "ledger_sum": s, "balanced": abs(bank - book) < 0.005 and abs(book - s) < 0.005,
            "negative_ledgers": neg, "segregated": reconciler not in disbursers}


def _study_plan(ask):
    theater = ask.get("decision_made") and re.search(r"\b(prove|confirm|validate that)\b", ask["text"], re.I)
    q = ask["text"]
    if re.search(r"\b(like|love|good)\b", q, re.I):
        q = "Where do target users fail or hesitate on the top %d tasks, and how severe is each issue?" % ask.get("tasks", 3)
    method = "moderated usability test" if re.search(r"fail|hesitate|severe|work", q) else "interviews" if re.search(r"\bwhy\b", q, re.I) else "survey"
    if ask.get("claim") == "statistic":
        z, p, e = 1.96, 0.5, ask.get("margin", 0.05)
        n = math.ceil(z * z * p * (1 - p) / (e * e))
    else:
        n = 5
        while 1 - (1 - 0.31) ** n < 0.84:
            n += 1
    return {"theater": bool(theater), "question": q, "method": method, "sample": n, "decision": ask.get("decision", "which issues block launch"),
            "consent": ["purpose", "screen+audio recording", "withdrawal"], "minimize": ["task performance", "role"], "deidentify": "P1..Pn",
            "retention": "delete recordings 30 days after synthesis", "ethics_before_collection": True}


def _instrument_lint(items, tasks, script):
    issues = []
    for i in items:
        if re.search(r"\b(love|enjoy|excellent|amazing|great)\b", i, re.I):
            issues.append(("leading", i))
        if re.search(r"\b(\w+) and (\w+)\b", i) and re.search(r"\b(fast|easy|intuitive|clear|quick)\b.*\band\b.*\b(fast|easy|intuitive|clear|quick)\b", i, re.I):
            issues.append(("double-barreled", i))
        if re.search(r"\b(most people|everyone|like other)\b", i, re.I):
            issues.append(("social desirability", i))
    for t in tasks:
        if re.search(r"\b(click|tap|press|select the)\b", t, re.I):
            issues.append(("instruction-based task", t))
    for s in script:
        if re.search(r"\b(was that easy|you liked|right\?|isn't it)\b", s, re.I):
            issues.append(("leading probe", s))
    return issues
