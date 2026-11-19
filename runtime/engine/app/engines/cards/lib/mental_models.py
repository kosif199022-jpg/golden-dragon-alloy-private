"""Helpers of power_programs/mental_models.py used by data cards, copied verbatim (the extractor binds a card to them only when
their AST hash with every dependency equals the original's)."""
from __future__ import annotations




def first_principles(assumptions):
    """Keep only assumptions tagged as law (physics, contract, measurement); strike conventions."""
    return [a for a in assumptions if a["kind"] == "law"]


def inversion(recipe, damage):
    guards = [{"guard": "prevent: " + r, "damage": damage[r]} for r in recipe]
    return sorted(guards, key=lambda g: -g["damage"])[:3]


def second_order(effects):
    """effects: stakeholder -> [first, then1, then2] values (signed). Flag reversals."""
    out = {}
    for s, chain in effects.items():
        total = sum(chain)
        out[s] = {"first": chain[0], "net": total, "reverses": chain[0] > 0 and total < 0}
    return out


def occam(cands):
    return sorted(cands, key=lambda c: (len(c["assumptions"]), c["name"]))


def hanlon(evidence_count, repeated):
    if evidence_count >= 2 and repeated:
        return "escalate"
    return "assume mistake; ask one question"


def fermi(factors):
    lo = hi = mid = 1.0
    for a, b in factors:
        lo *= a
        hi *= b
        mid *= (a * b) ** 0.5
    return lo, mid, hi


def door(reversible_cost_days):
    return "two-way: decide fast at 70% info" if reversible_cost_days <= 7 else "one-way: slow down, evidence, consent"


def safety_margin(expected, sigma, z=1.645):
    return expected + z * sigma


def bottleneck(steps):
    return max(steps, key=lambda s: steps[s]["queue"])


def cynefin(cause_effect_known, repeatable, stable):
    if not stable:
        return ("chaotic", "act to stabilise")
    if cause_effect_known and repeatable:
        return ("clear", "apply best practice")
    if cause_effect_known:
        return ("complicated", "analyse")
    return ("complex", "probe-sense-respond")


def premortem(causes, signals):
    return [{"cause": c, "signal": signals.get(c), "kept": bool(signals.get(c))} for c in causes]


def backcast(end, precedes):
    chain = [end]
    while chain[-1] in precedes:
        chain.append(precedes[chain[-1]])
    return list(reversed(chain))


def five_whys(chain, controllable):
    deepest = None
    for link in chain:
        if link["evidence"] and link["cause"] in controllable:
            deepest = link["cause"]
        if not link["evidence"]:
            break
    return deepest


def struct_sig(edges):
    return tuple(sorted(edges.values()))


def jtbd(s):
    import re
    return bool(re.match(r"^When .+, I want .+, so I can .+\.$", s))


def sunk(spent, future_cost, future_value):
    return future_value > future_cost


def unit_econ(price, var_cost, cac):
    cm = price - var_cost
    return cm, cm / price, cac / cm


def explore_rate(remaining, total):
    return remaining / total
