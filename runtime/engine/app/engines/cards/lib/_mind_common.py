"""Helpers of power_programs/_mind_common.py used by data cards, copied verbatim (the extractor binds a card to them only when
their AST hash with every dependency equals the original's)."""
from __future__ import annotations

from pathlib import Path
import json
import math
from itertools import product
import random
import re


def save(work: Path, name: str, obj) -> Path:
    p = Path(work) / name
    if isinstance(obj, (dict, list)):
        p.write_text(json.dumps(obj, ensure_ascii=False, indent=1, default=str) + "\n", encoding="utf-8")
    else:
        p.write_text(str(obj), encoding="utf-8")
    return p


def eq(name, got, want, tol=None):
    if tol is None:
        ok = got == want
    else:
        ok = abs(float(got) - float(want)) <= tol
    return (name, bool(ok), f"got={got!r} want={want!r}")


def truth(name, cond, observed=""):
    return (name, bool(cond), str(observed))


def topo_order(deps: dict) -> list:
    """deps: node -> list of prerequisites. Kahn's algorithm; raises on a cycle."""
    indeg = {n: 0 for n in deps}
    for n, ps in deps.items():
        for p in ps:
            indeg.setdefault(p, 0)
    for n, ps in deps.items():
        indeg[n] = len(ps)
    users = {n: [] for n in indeg}
    for n, ps in deps.items():
        for p in ps:
            users[p].append(n)
    ready = sorted(n for n, d in indeg.items() if d == 0)
    order = []
    while ready:
        n = ready.pop(0)
        order.append(n)
        for u in sorted(users[n]):
            indeg[u] -= 1
            if indeg[u] == 0:
                ready.append(u)
        ready.sort()
    if len(order) != len(indeg):
        raise ValueError("cycle")
    return order


def critical_path(durations: dict, deps: dict):
    """Longest path through a DAG of tasks. Returns (length, path, earliest_finish, slack)."""
    order = topo_order({k: deps.get(k, []) for k in durations})
    ef, prev = {}, {}
    for n in order:
        start = 0
        prev[n] = None
        for p in deps.get(n, []):
            if ef[p] > start:
                start, prev[n] = ef[p], p
        ef[n] = start + durations[n]
    end = max(ef, key=lambda k: (ef[k], k))
    total = ef[end]
    path = []
    cur = end
    while cur is not None:
        path.append(cur)
        cur = prev[cur]
    path.reverse()
    # latest finish for slack
    succ = {n: [m for m in durations if n in deps.get(m, [])] for n in durations}
    lf = {}
    for n in reversed(order):
        lf[n] = min([lf[s] - durations[s] for s in succ[n]] or [total])
    slack = {n: lf[n] - ef[n] for n in durations}
    return total, path, ef, slack


def find_cycles_signs(edges: dict):
    """edges: (a,b)->sign(+1/-1). Return simple cycles with their polarity (R or B)."""
    nodes = sorted({a for a, _ in edges} | {b for _, b in edges})
    adj = {n: [b for (a, b) in edges if a == n] for n in nodes}
    cycles = []

    def dfs(start, cur, path):
        for nxt in adj[cur]:
            if nxt == start:
                cycles.append(list(path))
            elif nxt not in path and nxt > start:
                dfs(start, nxt, path + [nxt])
    for s in nodes:
        dfs(s, s, [s])
    out = []
    for c in cycles:
        sign = 1
        for i, a in enumerate(c):
            sign *= edges[(a, c[(i + 1) % len(c)])]
        out.append((c, "R" if sign > 0 else "B"))
    return out


def weighted_scores(options: dict, weights: dict) -> dict:
    return {o: round(sum(weights[c] * s[c] for c in weights), 6) for o, s in options.items()}


def rank(scores: dict) -> list:
    return sorted(scores, key=lambda k: (-scores[k], k))


def expected_value(outcomes):
    return sum(p * v for p, v in outcomes)


def bayes(prior, p_e_true, p_e_false):
    num = prior * p_e_true
    return num / (num + (1 - prior) * p_e_false)


def ice(impact, confidence, effort):
    return impact * confidence / effort


def monte_carlo(fn, n, seed):
    rng = random.Random(seed)
    return [fn(rng) for _ in range(n)]


def percentile(xs, q):
    s = sorted(xs)
    k = (len(s) - 1) * q / 100.0
    f = math.floor(k)
    c = min(f + 1, len(s) - 1)
    return s[f] + (s[c] - s[f]) * (k - f)


def brier(probs, outcomes):
    return sum((p - o) ** 2 for p, o in zip(probs, outcomes)) / len(probs)


def pareto_front(points: dict, maximize=("a", "b")):
    """points: name -> dict; returns names not dominated on all maximize keys."""
    front = []
    for n, p in points.items():
        dom = False
        for m, q in points.items():
            if m == n:
                continue
            if all(q[k] >= p[k] for k in maximize) and any(q[k] > p[k] for k in maximize):
                dom = True
                break
        if not dom:
            front.append(n)
    return sorted(front)


WORD = re.compile(r"[\w؀-ۿ']+", re.UNICODE)


def words(text: str) -> list:
    return WORD.findall(text.lower())


def mece(items: dict, buckets: dict):
    """items: item -> set of features; buckets: name -> predicate(features). Returns (overlaps, gaps)."""
    overlaps, gaps = [], []
    for it, f in items.items():
        hits = [b for b, pred in buckets.items() if pred(f)]
        if len(hits) > 1:
            overlaps.append((it, hits))
        if not hits:
            gaps.append(it)
    return overlaps, gaps


def jaccard(a, b):
    a, b = set(a), set(b)
    return len(a & b) / len(a | b) if a | b else 1.0


def require_fields(obj: dict, fields) -> list:
    return [f for f in fields if not str(obj.get(f, "")).strip()]


def has_number(text: str) -> bool:
    return bool(re.search(r"\d", text))


def grid(*axes):
    return list(product(*axes))


def stock_flow(stock0, inflow, outflow_rate, steps):
    s, hist = stock0, [stock0]
    for _ in range(steps):
        s = s + inflow - outflow_rate * s
        hist.append(round(s, 9))
    return hist
