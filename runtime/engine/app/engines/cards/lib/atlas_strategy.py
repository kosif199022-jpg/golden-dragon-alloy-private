"""Helpers of power_programs/atlas_strategy.py used by data cards, copied verbatim (the extractor binds a card to them only when
their AST hash with every dependency equals the original's)."""
from __future__ import annotations

from ._mind_common import has_number
import math
from scipy.stats import norm
import numpy as np
import re
from ._mind_common import words


def crossings(flow):
    """flow: ordered actors incl. 'human' at both ends -> list of boundary crossings."""
    return [(a, b) for a, b in zip(flow, flow[1:]) if a != b]


def boundary_verdict(gains):
    return "keep" if gains else "collapse"


def ralph_loop(backlog, gate, followups):
    worked, log, new = [], [], []
    queue = list(backlog)
    while queue:
        item = queue.pop(0)
        if not gate(item):
            log.append(("rejected", item))
            continue
        worked.append(item)  # one item per cycle
        for f in followups.get(item, []):
            new.append(f)  # logged, not worked
        log.append(("validated+commit", item))
    return worked, new, log


ROLES = {"CFO": ["runway", "burn", "pricing", "fundraise"], "CMO": ["brand", "marketing", "positioning"], "CISO": ["security", "breach", "soc2"],
         "CHRO": ["hiring", "culture"], "COO": ["operations", "process"], "GC": ["contract", "legal"]}


def route(question, context_age_days):
    w = set(words(question))
    roles = sorted(r for r, kws in ROLES.items() if w & set(kws))
    return {"roles": roles, "board": len(roles) >= 2, "stale": context_age_days > 90}


def waves(waves_, gate_results):
    done = []
    for i, w in enumerate(waves_):
        done.append(w["name"])
        if not gate_results.get(w["name"], True):
            return done, f"halted after {w['name']}"
    return done, "complete"


def budget(items, per_item_agents, cost_per_agent, group_size, redrive_rate, cap):
    agents = math.ceil(items / group_size) * per_item_agents
    total = agents * cost_per_agent * (1 + redrive_rate)
    return agents, round(total, 2), total <= cap


def phase_gates(phases, evidence):
    for p in phases:
        unmet = [c for c in p["exit"] if not evidence.get(c)]
        if unmet:
            return p["name"], unmet
    return "go-live", []


def util_flags(billable, tracked, actual, planned):
    b = billable / tracked
    v = (actual - planned) / planned
    flag = "under-priced" if v > 0.5 else "scope review" if v > 0.25 else "over-planned" if v < -0.25 else "ok"
    return round(b, 4), round(v, 4), flag


def pay_run(bills, today, balance):
    inc, exc = [], []
    for b in bills:
        reason = ("held" if b["hold"] else "disputed" if b["dispute"] else "unapproved" if not b["approved"] else "zero" if b["amount"] <= 0
                  else "outside-window" if b["due_in"] > 7 else None)
        if reason:
            exc.append((b["id"], reason))
            continue
        score = (10 if b.get("discount") else 0) + 5 * max(0, -b["due_in"] // 7) + (5 if b.get("critical") else 0) - (5 if b.get("terms", 30) >= 60 else 0)
        inc.append((b["id"], score, b["amount"]))
    total = sum(x[2] for x in inc)
    cash = "stop" if total > balance else "warn" if total > 0.8 * balance else "ok"
    return sorted(inc, key=lambda x: -x[1]), exc, total, cash


LIMITS = {"apple_name": 30, "apple_subtitle": 30, "apple_keywords": 100, "play_title": 30, "play_short": 80}


def aso_lint(meta):
    errs = [f"{k} over {LIMITS[k]}" for k, v in meta.items() if k in LIMITS and len(v) > LIMITS[k]]
    kws = [k.strip() for k in meta.get("apple_keywords", "").split(",")]
    dups = sorted({k for k in kws if kws.count(k) > 1})
    errs += [f"duplicate {d}" for d in dups]
    name_words = set(words(meta.get("apple_name", "")))
    errs += [f"keyword repeats name: {k}" for k in kws if k in name_words]
    return errs, (1 if errs else 0)


def risk_review(scores, narrow=False):
    if narrow:
        return None
    worst = min(scores, key=scores.get)
    avg = sum(scores.values()) / len(scores)
    verdict = "high" if avg < 2.5 else "medium" if avg < 3.5 else "low"
    return {"verdict": verdict, "breaks_first": worst}


def backtest(prices, fast, slow, fee):
    p = np.asarray(prices, float)
    ma = lambda n: np.convolve(p, np.ones(n) / n, "valid")
    f, s = ma(fast)[slow - fast:], ma(slow)
    sig = (f > s).astype(float)
    pos = np.concatenate([[0], sig[:-1]])  # next-bar execution
    rets = np.diff(p[slow - 1:]) / p[slow - 1:-1]
    trades = np.abs(np.diff(np.concatenate([[0], pos])))[:len(rets)]
    strat = pos[:len(rets)] * rets - trades * fee
    eq_ = np.cumprod(1 + strat)
    dd = 1 - eq_ / np.maximum.accumulate(eq_)
    return strat, eq_, dd


def dcf(fcf, wacc, g, exit_mult, ebitda_n, net_debt):
    pv = sum(c / (1 + wacc) ** (t + 1) for t, c in enumerate(fcf))
    n = len(fcf)
    tv_g = fcf[-1] * (1 + g) / (wacc - g)
    tv_m = ebitda_n * exit_mult
    pv_tv = tv_g / (1 + wacc) ** n
    ev = pv + pv_tv
    return {"pv_fcf": pv, "tv_gordon": tv_g, "tv_multiple": tv_m, "ev": ev, "tv_share": pv_tv / ev, "equity": ev - net_debt}


RISK_RE = re.compile(r"^In .+ exposed to .+ caused by .+ leading to .+$")


def runway(cash, burn, growth, months=36):
    m, c, b = 0, cash, burn
    while c > 0 and m < months:
        c -= b
        b *= 1 + growth
        m += 1
    return m


def rd_budget(direct, excluded, fa_rate):
    base = direct - excluded
    fa = base * fa_rate
    return direct, fa, direct + fa


def capitalise(item):
    crit = ["technical feasibility", "intent to complete", "ability to use", "future benefit", "resources", "measurable cost"]
    met = [c for c in crit if c in item["met"]]
    if len(met) == 6:
        return "CAPITALIZE-CANDIDATE"
    if not met:
        return "EXPENSE"
    return "FINANCE-OWNER-REVIEW"


def priced_round(table, pre_money, new_money, pool_target):
    shares = sum(table.values())
    price0 = pre_money / shares
    post = pre_money + new_money
    # pool top-up in the pre-money: solve pool such that pool / post_shares = target
    inv_pct = new_money / post
    existing_pool = table.get("pool", 0)
    total_post = shares / (1 - inv_pct - 0)  # placeholder overwritten below
    # iterate: new pool shares p so that (existing_pool + p)/(shares + p + inv) = pool_target, inv = inv_pct * total
    p = 0.0
    for _ in range(200):
        tot = (shares + p) / (1 - inv_pct)
        p = pool_target * tot - existing_pool
    tot = (shares + p) / (1 - inv_pct)
    inv = inv_pct * tot
    out = dict(table)
    out["pool"] = existing_pool + p
    out["investor"] = inv
    return {k: v / tot for k, v in out.items()}, (pre_money / (shares + p))


def safe_price(cap, discount, round_price, shares_pre):
    cap_price = cap / shares_pre
    return min(cap_price, round_price * (1 - discount))


def cash13(opening, receipts, disb):
    bal, out = opening, []
    for r, d in zip(receipts, disb):
        bal += r - d
        out.append(bal)
    return out


def sample_size(p, mde, alpha=0.05, power=0.8):
    p2 = p + mde
    za, zb = norm.ppf(1 - alpha / 2), norm.ppf(power)
    return math.ceil((za + zb) ** 2 * (p * (1 - p) + p2 * (1 - p2)) / mde ** 2)


def action_priority(s, o, d):
    if s >= 9 and (o >= 4 or d >= 7):
        return "H"
    if s >= 7 and o >= 4:
        return "H"
    if s >= 5 and o >= 6:
        return "M"
    return "L"


def psm(ranges):
    """Van Westendorp: find where 'too cheap' share equals 'too expensive' share (optimal price point)."""
    grid = np.arange(1, 101)
    cheap = np.array([np.mean([r["too_cheap"] >= p for r in ranges]) for p in grid])
    exp = np.array([np.mean([r["too_expensive"] <= p for r in ranges]) for p in grid])
    return int(grid[np.argmin(np.abs(cheap - exp))])


def mode_for(latency_s):
    return "streaming" if latency_s < 60 else "batch ELT"


def why_chain_valid(chain):
    for link in chain:
        if not link.get("evidence"):
            return False, f"no evidence: {link['why']}"
        if "human error" in link["why"].lower() and link is chain[-1]:
            return False, "stopped at human error"
    whys = [l["why"] for l in chain]
    if len(set(whys)) != len(whys):
        return False, "circular"
    return True, "ok"


def severity(users_pct):
    return "SEV1" if users_pct >= 50 else "SEV2" if users_pct >= 10 else "SEV3"


def compute_pick(w):
    if w["duration_s"] <= 900 and w["bursty"]:
        return "Lambda"
    if w["containers"]:
        return "Fargate"
    return "EC2"


def burn_rate(err_rate, slo):
    return err_rate / (1 - slo)


def ai_act(use):
    if use in ("social scoring", "subliminal manipulation"):
        return "prohibited"
    if use in ("hiring", "credit scoring", "education grading"):
        return "high-risk"
    if use in ("chatbot", "deepfake"):
        return "limited"
    return "minimal"


def dora(deploys_per_week, lead_h, cfr, mttr_h):
    def lvl(v, elite, high, med, lower_better=True):
        if lower_better:
            return "elite" if v <= elite else "high" if v <= high else "medium" if v <= med else "low"
        return "elite" if v >= elite else "high" if v >= high else "medium" if v >= med else "low"
    r = {"deploy": lvl(deploys_per_week, 7, 1, 0.25, False), "lead": lvl(lead_h, 24, 168, 720), "cfr": lvl(cfr, 0.05, 0.10, 0.15), "mttr": lvl(mttr_h, 1, 24, 168)}
    order = ["low", "medium", "high", "elite"]
    weakest = min(r, key=lambda k: order.index(r[k]))
    return r, weakest


def size_task(hours):
    return "small" if hours <= 4 else "medium" if hours <= 16 else "large" if hours <= 40 else "split"


SEC_STEPS = ["private advisory", "private fix+test", "request CVE", "backport", "release+publish advisory", "notify downstream"]


def sec_release_check(log):
    idx = {s: i for i, s in enumerate(log)}
    errs = [s for s in SEC_STEPS if s not in idx]
    if "public commit" in idx and idx["public commit"] < idx.get("release+publish advisory", 10**9):
        errs.append("public trace before release")
    for a, b in zip(SEC_STEPS, SEC_STEPS[1:]):
        if a in idx and b in idx and idx[a] > idx[b]:
            errs.append(f"{a} after {b}")
    return errs


def tutor_step(state, answer, correct):
    if answer is None:
        return state, "wait"
    if answer == correct:
        state["status"] = "independent" if not state["hinted"] else "hinted"
        return state, "new-conditions question"
    state["hinted"] = True
    return state, "minimal hint"


def answer_first(md):
    out = []
    for block in re.split(r"^## ", md, flags=re.M)[1:]:
        head, _, body = block.partition("\n")
        first = body.strip().split(". ")[0]
        out.append((head.strip(), head.strip().endswith("?"), has_number(first) or " is " in first))
    return out


def diag_score(passed):
    return {7: 10, 6: 9, 5: 7, 4: 6}.get(passed, max(0, passed))


def cover_lint(text):
    paras = [p for p in text.split("\n\n") if p.strip()]
    n = len(words(text))
    errs = []
    if len(paras) != 4:
        errs.append("paragraphs")
    if not 250 <= n <= 380:
        errs.append("length")
    if re.match(r"\s*(dear [^\n]*\n+)?i am (so )?excited", text, re.I):
        errs.append("weak opener")
    if not has_number(paras[0] if paras else ""):
        errs.append("no number in opening result")
    return errs


def mirror(utterance, k=3):
    w = re.findall(r"[\w']+", utterance)
    return " ".join(w[-k:]) + "?"


def label(emotion):
    return f"It seems like {emotion}."


def containment_ok(text):
    return bool(re.search(r"\b(sorted|quarantined|stopped|segregated|blocked)\b", text, re.I)) and bool(re.search(r"\d{4}-\d{2}-\d{2}", text)) and "careful" not in text.lower()


ALL_LINEAR = {"q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"}


def lora_lint(cfg):
    errs = []
    if set(cfg["target_modules"]) != ALL_LINEAR:
        errs.append(f"missing modules {sorted(ALL_LINEAR - set(cfg['target_modules']))}")
    if cfg["lora_alpha"] != 2 * cfg["r"]:
        errs.append("alpha != 2r")
    if not 1 <= cfg["r"] <= 256:
        errs.append("rank range")
    if cfg["batch"] * cfg["grad_accum"] >= 32:
        errs.append("effective batch >= 32")
    if cfg.get("qlora") and cfg["lr"] != 2e-4:
        errs.append("QLoRA lr start 2e-4")
    return errs


def support_rung(daily):
    return "scripted menu" if daily < 50 else "AI self-service + human fallback" if daily <= 500 else "skills-based routing + analytics"


def adhd_lint(reply):
    lines = [l for l in reply.splitlines() if l.strip()]
    errs = []
    if not re.match(r"^(run|open|`|cd |python|git|1\.)", lines[0], re.I):
        errs.append("first line not an action")
    items = [l for l in lines if re.match(r"^\d+\.", l)]
    if len(items) > 5:
        errs.append("list over 5")
    if not any(re.search(r"step \d+ of \d+", l) for l in lines):
        errs.append("no state line")
    return errs


def change_stage(c):
    s = "edited"
    if c.get("commit"):
        s = "committed"
    if c.get("pushed"):
        s = "pushed/merged"
    if c.get("observed_live"):
        s = "live and observed"
    return s


def is_finding(item):
    return bool(item.get("criteria")) and item.get("condition_breaches", False)


def wire_check(req, directory):
    issues = []
    if req["changed_destination"] and not req.get("callback_number_from") == "contract":
        issues.append("callback not to independently sourced number")
    if req["channel"] == "email" and req["changed_destination"]:
        issues.append("email change treated as fraud until verified")
    if len(set(req["approvers"])) < 2:
        issues.append("second approver missing")
    return issues


def method_choice(p):
    if p["single_complaint"]:
        return "8D"
    if p["cause_known"] and p["small"]:
        return "PDCA"
    return "DMAIC"


def pdca_pilot(plan, results):
    if "success" not in plan or "scope" not in plan:
        return "invalid: pilot not fixed before start"
    return "adopt" if results[plan["success"][0]] <= plan["success"][1] else "rework"


def company_rev(model, gci):
    if model == "split":
        return 0.3 * gci
    if model == "cap":
        return min(0.3 * gci, 20000) + 0.05 * max(0, gci - 20000 / 0.3)
    return 12000.0


LEADING = re.compile(r"^(don't you|wouldn't you|isn't it|click|tap|do you like)", re.I)


def paid_test_ok(q, budget_ok, approval):
    return bool(q) and budget_ok and approval


def grr(data):
    """data: parts x appraisers x trials. Average-and-range method (AIAG)."""
    d = np.asarray(data, float)
    p, a, r = d.shape
    K1 = {2: 0.8862, 3: 0.5908}[r]
    K2 = {2: 0.7071, 3: 0.5231}[a]
    K3 = {10: 0.3146}[p]
    rbar = np.mean(d.max(2) - d.min(2))
    ev = rbar * K1
    xdiff = d.mean((0, 2)).max() - d.mean((0, 2)).min()
    av = math.sqrt(max(0, (xdiff * K2) ** 2 - ev ** 2 / (p * r)))
    grr_ = math.sqrt(ev ** 2 + av ** 2)
    rp = d.mean((1, 2)).max() - d.mean((1, 2)).min()
    pv = rp * K3
    tv = math.sqrt(grr_ ** 2 + pv ** 2)
    ndc = int(1.41 * pv / grr_)
    return 100 * grr_ / tv, ndc


def opp_score(importance, satisfaction):
    return importance + max(0, importance - satisfaction)
