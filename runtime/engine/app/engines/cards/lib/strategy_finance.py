"""Helpers of power_programs/strategy_finance.py used by data cards, copied verbatim (the extractor binds a card to them only when
their AST hash with every dependency equals the original's)."""
from __future__ import annotations

import json


def options_table(opts):
    problems = []
    if "do-nothing" not in opts:
        problems.append("no do-nothing")
    cols = ("cost", "benefit", "reversibility", "time_to_signal", "risk")
    for k, v in opts.items():
        miss = [c for c in cols if c not in v]
        if miss:
            problems.append(f"{k} missing {miss}")
    ideas = [v["idea"] for k, v in opts.items() if k != "do-nothing"]
    if len(set(ideas)) < len(ideas):
        problems.append("same idea in different sizes")
    return problems


def profit_a(x):
    return 50 * x - 20000


def profit_b(x):
    return 30 * x - 8000


def premortem_scores(stories):
    for s in stories:
        s["score"] = s["likelihood"] * s["impact"]
    return sorted(stories, key=lambda s: -s["score"])


def council(own, voices):
    """own position recorded before reading voices; dissent kept."""
    record = {"own": own, "voices": voices}
    votes = [v["plan"] for v in voices.values()] + [own["plan"]]
    majority = max(set(votes), key=votes.count)
    record["synthesis"] = majority
    record["dissent"] = sorted(k for k, v in voices.items() if v["plan"] != majority)
    return record


LEDGER_KEYS = ["date", "decision", "options", "evidence", "mark", "review_if"]


def ledger_append(path, entry):
    miss = [k for k in LEDGER_KEYS if k not in entry]
    if miss:
        raise ValueError(f"missing {miss}")
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def rollout_eval(stages, metrics):
    res = []
    for s in stages:
        m = metrics[s["stage"]]
        killed = m[s["metric"]] > s["kill_above"]
        res.append((s["stage"], "stop" if killed else "advance"))
        if killed:
            break
    return res


VAGUE = {"fast", "quick", "easy", "intuitive", "robust", "scalable", "nice", "simple", "soon"}


def prd_lint(prd):
    import re
    problems = []
    if not 3 <= len(prd["criteria"]) <= 7:
        problems.append("criteria count")
    for c in prd["criteria"]:
        v = [w for w in re.findall(r"[a-z]+", c.lower()) if w in VAGUE]
        if v and not re.search(r"\d", c):
            problems.append(f"vague: {c}")
    for k in ("goal", "in_scope", "out_scope", "assumptions", "blockers"):
        if k not in prd:
            problems.append(f"missing {k}")
    return problems


def journal_check(entries):
    return [e["id"] for e in entries if round(sum(l["dr"] for l in e["lines"]), 2) != round(sum(l["cr"] for l in e["lines"]), 2)]


def reconcile(bank, ledger):
    key = lambda r: (r["date"], r["amount"], r["ref"])
    bk, lk = {key(r) for r in bank}, {key(r) for r in ledger}
    only_bank, only_ledger = sorted(bk - lk), sorted(lk - bk)
    residual = round(sum(r["amount"] for r in bank) - sum(r["amount"] for r in ledger), 2)
    explained = round(sum(k[1] for k in only_bank) - sum(k[1] for k in only_ledger), 2)
    return only_bank, only_ledger, residual, round(residual - explained, 2)


def model(inputs):
    rev = inputs["units"] * inputs["price"]
    cogs = inputs["units"] * inputs["unit_cost"]
    opex = inputs["opex"]
    ni = rev - cogs - opex
    cash = inputs["cash0"] + ni - inputs["capex"]
    assets = cash + inputs["ppe0"] + inputs["capex"]
    equity = inputs["equity0"] + ni
    return {"revenue": rev, "net_income": ni, "cash": cash, "assets": assets, "equity": equity,
            "balance_check": round(assets - equity, 6), "cash_bridge": round(cash - (inputs["cash0"] + ni - inputs["capex"]), 6)}
