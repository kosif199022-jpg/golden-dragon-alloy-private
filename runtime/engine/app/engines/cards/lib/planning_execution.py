"""Helpers of power_programs/planning_execution.py used by data cards, copied verbatim (the extractor binds a card to them only when
their AST hash with every dependency equals the original's)."""
from __future__ import annotations

import re
from ._mind_common import topo_order


def backcast_plan(end_state, precedes, today):
    chain = [end_state]
    while chain[-1] != today:
        nxt = precedes.get(chain[-1])
        if nxt is None:
            raise ValueError("chain does not reach today")
        chain.append(nxt)
    plan = list(reversed(chain))
    return [{"milestone": m, "done_test": f"evidence that '{m}' holds"} for m in plan]


ACTIVITY = re.compile(r"^(work on|research|look into|think about|explore)\b", re.I)


def wbs_check(tasks, max_hours=4):
    bad = []
    for t in tasks:
        if t["hours"] > max_hours:
            bad.append((t["name"], "over 4 h"))
        if ACTIVITY.match(t["name"]):
            bad.append((t["name"], "activity not deliverable"))
        if not t.get("done"):
            bad.append((t["name"], "no done-test"))
    return bad


def thin_slice(spec):
    """Cut a request to the 2 s, one-screen, one-record slice."""
    return {"duration_s": min(2, spec["duration_s"]), "screens": spec["screens"][:1], "records": spec["records"][:1]}


DEFAULT_CAUSES = ["scope creep", "missing dependency", "underestimated effort", "unclear owner", "late feedback"]


def premortem(plan_causes):
    causes = list(dict.fromkeys(DEFAULT_CAUSES + plan_causes))
    return [{"cause": c, "warning": f"watch: {c}", "mitigation": f"guard: {c}"} for c in causes]


def kill_eval(criteria, observed):
    out = []
    for c in criteria:
        v = observed[c["metric"]]
        hit = v < c["min"] if "min" in c else v > c["max"]
        out.append((c["metric"], "kill" if hit and c["action"] == "kill" else "pivot" if hit else "continue"))
    return out


def lanes(tasks):
    """Group tasks into parallel lanes by dependency depth (independent tasks share a lane)."""
    order = topo_order(tasks)
    depth = {}
    for t in order:
        depth[t] = 1 + max([depth[d] for d in tasks[t]] or [-1])
    out = {}
    for t, d in depth.items():
        out.setdefault(d, []).append(t)
    return [sorted(v) for _, v in sorted(out.items())]


META = ["goal still right?", "evidence for each claim?", "what was skipped?", "simpler path?", "coverage ledger complete?"]


def phase_review(ledger):
    missing = [k for k, v in ledger.items() if v is None]
    return {"questions": META, "uncovered": missing, "pass": not missing}


def receipt(measured, spec):
    return {k: (measured.get(k), v, measured.get(k) == v) for k, v in spec.items()}


def spec_trace(spec):
    problems = []
    if not 5 <= len(spec["constitution"]) <= 9:
        problems.append("constitution size")
    for s in spec["stories"]:
        if "[NEEDS CLARIFICATION]" in s["text"]:
            problems.append(f"unclarified: {s['id']}")
    crit = {c for s in spec["stories"] for c in s["criteria"]}
    tasks = spec["tasks"]
    for c in sorted(crit):
        if not any(c in t["covers"] and t["kind"] == "test" for t in tasks):
            problems.append(f"no test for {c}")
    ids = [t["id"] for t in tasks]
    for t in tasks:
        if t["kind"] == "code":
            test = [x for x in tasks if x["kind"] == "test" and set(x["covers"]) & set(t["covers"])]
            if test and ids.index(test[0]["id"]) > ids.index(t["id"]):
                problems.append(f"code before test: {t['id']}")
        if not t["covers"]:
            problems.append(f"untraced task: {t['id']}")
    return problems


def tdd_cycle(task_minutes, steps):
    ok_size = all(2 <= m <= 5 for m in task_minutes)
    ok_order = all(s == ["red", "green", "refactor", "review"] for s in steps)
    return ok_size, ok_order
