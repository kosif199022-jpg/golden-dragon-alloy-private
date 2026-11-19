"""Helpers of power_programs/agent_orchestration.py used by data cards, copied verbatim (the extractor binds a card to them only when
their AST hash with every dependency equals the original's)."""
from __future__ import annotations

from collections import Counter
from pathlib import Path
import ast
import json
import os
import re
from ._lang_common import sha256
import subprocess
import sys
from ._lang_common import words
import yaml


SECRET = re.compile(r"(sk-[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{20,}|password\s*=\s*\S+)", re.I)


def delegate_plan(task):
    if task["est_tool_calls"] <= 15:
        return {"mode": "do it yourself", "lanes": []}
    lanes, used = [], set()
    for part in task["parts"]:
        surf = set(part["writes"])
        if surf & used:
            raise ValueError(f"lanes share write surface: {sorted(surf & used)}")
        used |= surf
        lanes.append({"lane": part["name"], "agent": "Explore" if not surf else "general-purpose"})
    writers = sum(1 for l in lanes if l["agent"] == "general-purpose")
    return {"mode": "delegate", "lanes": lanes, "one_message": True, "writers": writers, "ok": writers <= 4,
            "final": "collect, verify, merge, then answer"}


PACKET = ("goal", "artifact", "constraints", "owner", "tools_allowed", "evidence_required", "state", "next_step")


def packet_gaps(p):
    gaps = [f for f in PACKET if not p.get(f)]
    if p.get("artifact") and not os.path.isabs(p["artifact"]):
        gaps.append("artifact path not absolute")
    if not p.get("must_not"):
        gaps.append("must-not list missing")
    return gaps


def file_retrieval(files, terms, learn, max_cycles=3):
    q = set(terms)
    hist = []
    for c in range(1, max_cycles + 1):
        sc = {}
        for path, text in files.items():
            if "/tests/" in path or path.startswith("tests/"):
                continue
            ws = set(words(text))
            sc[path] = round(len(ws & q) / len(q), 2)
        keep = {p: s for p, s in sc.items() if s >= 0.2}
        strong = sorted(p for p, s in keep.items() if s >= 0.7)
        hist.append({"cycle": c, "terms": sorted(q), "strong": strong, "dropped": sorted(set(sc) - set(keep))})
        if len(strong) >= 3:
            break
        q |= set(learn.get(c, []))
    return hist


def make_agent(name, when, tools, role):
    if role == "reviewer" and set(tools) - {"Read", "Grep", "Glob"}:
        raise ValueError("reviewer gets Read, Grep, Glob only")
    fm = {"name": name, "description": f"Use {when}.", "tools": ", ".join(tools)}
    return "---\n" + yaml.safe_dump(fm, sort_keys=False) + "---\nChecklist:\n- correctness\nOutput: findings with file:line\nStop when done.\n"


EVID = {"command", "file", "ffprobe", "test", "screenshot"}


def receipt_ok(r):
    errs = []
    for f in ("status", "summary", "owner", "evidence", "artifacts", "next_actions", "retryable", "verified"):
        if f not in r:
            errs.append(f"missing {f}")
    if r.get("status") not in ("success", "warning", "error"):
        errs.append("bad status")
    if r.get("verified"):
        if r.get("status") != "success":
            errs.append("verified needs success")
        if not any(e.get("type") in EVID and e.get("ref") for e in r.get("evidence", [])):
            errs.append("verified needs typed evidence")
    return errs


DESTRUCTIVE = re.compile(r"\b(rm -rf|drop table|migrate|git push --force|truncate)\b", re.I)


def lane_matrix(lanes):
    writers = Counter(f for l in lanes for f in l["writes"])
    issues = [f"two writers on {f}" for f, n in writers.items() if n > 1]
    issues += [f"destructive lane {l['lane']} must be sequential" for l in lanes
               if DESTRUCTIVE.search(l["cmd"]) and l["mode"] == "parallel"]
    issues += [f"lane {l['lane']} has no verification" for l in lanes if not l.get("verify")]
    return issues


def workflow_collisions(lanes, outputs):
    owned = Counter(f for l in lanes for f in l["owns"])
    coll = sorted(f for f, n in owned.items() if n > 1)
    missing = [l["lane"] for l in lanes if not outputs.get(l["out"])]
    return coll, missing


def fan_out(lanes, run):
    res = {}
    for l in lanes:
        ok = run(l, contract="full")
        if not ok:
            ok = run(l, contract="smaller")
            res[l] = "retried-ok" if ok else "FAILED"
        else:
            res[l] = "ok"
    failed = [l for l, v in res.items() if v == "FAILED"]
    stop = len(failed) > len(lanes) / 2
    return res, ("stop and diagnose" if stop else "merge the rest")


def worktree_plan(tasks, cap=4):
    active, queue = [], []
    for i, t in enumerate(tasks):
        (active if len(active) < cap else queue).append({"task": t, "path": f"../proj-{t}", "branch": t, "created": i})
    sweep = [w["task"] for w in sorted(active, key=lambda w: w["created"])]
    cmds = [f"git worktree add {w['path']} -b {w['branch']}" for w in active]
    return active, queue, sweep, cmds


PHASES = ("RESEARCH", "PLAN", "IMPLEMENT", "REVIEW", "VERIFY")


def size_tier(change):
    if change["files"] == 1 and not change["new_dep"]:
        return "trivial"
    if change["security"] or change["public_api"] or change["files"] > 10:
        return "large"
    return "standard" if change["files"] > 3 else "small"


def run_pipeline(done, approvals):
    for i, p in enumerate(PHASES):
        if p not in done:
            return f"next: {p}"
        if p == "PLAN" and not approvals.get("plan"):
            return "blocked: gate 1 plan approval"
    return "done" if approvals.get("commit") else "blocked: gate 2 commit approval"


def santa(rounds_verdicts, cap=3):
    log = []
    for r, (a, b) in enumerate(rounds_verdicts[:cap], 1):
        flags = sorted(set(a["flags"]) | set(b["flags"]))
        log.append({"round": r, "flags": flags})
        if a["verdict"] == "PASS" and b["verdict"] == "PASS":
            return "ship", log
    return "escalate to user", log


def council_check(rec):
    errs = []
    if rec["own_position"]["t"] >= min(v["t"] for v in rec["voices"]):
        errs.append("own position written after reading voices (anchoring)")
    if len(rec["own_position"]["reasons"]) != 3 or not rec["own_position"].get("risk"):
        errs.append("position needs 3 reasons + main risk")
    if sorted(v["role"] for v in rec["voices"]) != ["Critic", "Pragmatist", "Skeptic"]:
        errs.append("need Skeptic, Pragmatist, Critic")
    if not all(k in rec["synthesis"] for k in ("decision", "why", "dissent", "would_change_mind")):
        errs.append("synthesis incomplete")
    return errs


W13 = {"design": 0.3, "originality": 0.2, "craft": 0.3, "functionality": 0.2}


def gen_eval(scores_per_iter, threshold=7.0, cap=15):
    hist = []
    for i, s in enumerate(scores_per_iter[:cap], 1):
        w = round(sum(W13[k] * s[k] for k in W13), 2)
        hist.append(w)
        if w >= threshold:
            return i, hist
    return None, hist


def norm_snip(s):
    return re.sub(r"\s+", " ", s.strip().lower())


def adversarial(reviews, verifier):
    if any(r is None or r == [] and False for r in reviews.values()) or any(v is None for v in reviews.values()):
        return {"verdict": "CHANGES_REQUESTED", "incomplete": True, "confirmed": []}
    seen, findings = set(), []
    for dim, fs in reviews.items():
        for f in fs:
            k = norm_snip(f["evidence"])
            if k not in seen:
                seen.add(k)
                findings.append(f)
    confirmed = [f for f in findings if f["sev"] not in ("CRITICAL", "HIGH") or verifier(f) == "confirmed"]
    return {"verdict": "CHANGES_REQUESTED" if confirmed else "APPROVE (human gate)", "incomplete": False,
            "confirmed": [f["id"] for f in confirmed]}


def panel(lens_findings):
    if not 2 <= len(lens_findings) <= 5:
        raise ValueError("2-5 lenses")
    merged, conflicts = {}, []
    for lens, fs in lens_findings.items():
        for f in fs:
            k = f["where"]
            if k in merged and merged[k]["verdict"] != f["verdict"]:
                win = max(merged[k], f, key=lambda x: {"high": 3, "medium": 2, "low": 1}[x["sev"]])
                conflicts.append({"where": k, "resolved": f"kept {win['verdict']} (higher severity)"})
                merged[k] = win
            else:
                merged.setdefault(k, f)
    return merged, conflicts


def loop_gate(d):
    gates = {"weekly": d["per_week"] >= 1, "auto_verify": d["verify_cmd"] is not None, "budget": d["cost"] <= d["budget"],
             "real_tools": d["tools_observe"]}
    fm = []
    if not re.search(r"\d|exit 0|==", d["goal"]):
        fm.append("platitude goal")
    if d["verify_cmd"] and "self" in d["verify_cmd"]:
        fm.append("self-judged verification")
    if d["verify_cmd"] == "pytest":
        fm.append("tests pass only")
    irreversible_auto = [a for a in d["auto_actions"] if a in ("merge", "publish", "payment")]
    return all(gates.values()) and not fm and not irreversible_auto, gates, fm, irreversible_auto


def classify_failure(ev):
    msg = ev["error"]
    if ev.get("same_command_repeats", 0) >= 3:
        return "no-exit loop", "state", "deterministic"
    if re.search(r"ECONNREFUSED|timed? ?out", msg):
        return "wrong port or service down", "environment", "transient"
    if "429" in msg:
        return "retry storm", "policy", "transient"
    if re.search(r"No such file|not found after write", msg):
        return "wrong cwd or branch", "state", "deterministic"
    if re.search(r"AssertionError|FAILED", msg):
        return "wrong hypothesis: isolate one test", "logic", "deterministic"
    return "unknown", "unknown", "unknown"


HEDGE = re.compile(r"should work|likely fine|i believe the tests pass|probably", re.I)


def delivery_gate(reqs, artifact, report):
    rows = [(r["name"], "PASS" if r["check"](artifact) else "FAIL") for r in reqs]
    hedges = HEDGE.findall(report)
    return rows, hedges


def mcp_risk(spec):
    if spec.startswith(("./", "/", "file:", "git+")):
        return "review"
    if re.search(r"@latest$", spec) or not re.search(r"@[\^~]?\d", spec):
        return "high"
    if re.search(r"@[\^~]\d", spec):
        return "medium"
    return "safe"


def surface(need):
    if need.get("every_time"):
        return "hook"
    if need["always_rule"]:
        return "CLAUDE.md line"
    if need["paid_or_auth"]:
        return "direct API call with approval + budget"
    if need["deterministic"]:
        return "local script/CLI"
    if need["stateful_external"]:
        return "MCP server (after probing)"
    return "skill on demand"


def skill_author_lint(root: Path):
    md = (root / "SKILL.md").read_text()
    fm = yaml.safe_load(md.split("---")[1])
    desc = fm["description"]
    issues = []
    if len(desc) > 1536:
        issues.append("description over 1536")
    if not (re.search(r"[A-Za-z]{4}", desc[:300]) and re.search(r"[؀-ۿ]", desc[:300])):
        issues.append("EN+AR triggers not in first 300 chars")
    if len(md.splitlines()) >= 500:
        issues.append("SKILL.md >= 500 lines")
    deep = [str(p.relative_to(root)) for p in (root / "references").rglob("*.md") if len(p.relative_to(root / "references").parts) > 1]
    if deep:
        issues.append("references deeper than one level: " + ",".join(deep))
    return issues


RISKY = re.compile(r"curl .*\|\s*(ba)?sh|requests\.post|os\.environ\[.?(AWS|TOKEN|KEY)", re.I)


def scout(skills, keywords, cap=10):
    rows = []
    for name, desc, body in skills:
        s = sum(1 for k in keywords if k.lower() in (name + " " + desc).lower())
        if s:
            rows.append({"name": name, "score": s, "risk": bool(RISKY.search(body))})
    rows.sort(key=lambda r: (-r["score"], r["risk"], r["name"]))
    best = rows[0] if rows else None
    offer = "use existing" if best and best["score"] >= 2 and not best["risk"] else "fork and extend" if best else "create fresh"
    return rows[:cap], offer


def evolve(old, new, hard_fail=()):
    reg = [k for k in old if old[k] and not new.get(k)]
    keep = not reg and not hard_fail and sum(new.values()) >= sum(old.values())
    line = f"expected: triggers {sum(old.values())}->more; actual: {sum(new.values())}/{len(new)}"
    return keep, reg, line


def load_more(open_chapters, requirement, deep=False):
    cap = 4 if deep else 2
    if not requirement:
        return False, "gap test: name the uncovered requirement first"
    if len(open_chapters) >= cap:
        return False, f"cap {cap} reached"
    return True, "open one more"


def context_action(used_frac, phase_boundary, mid_impl):
    if mid_impl:
        return "continue; write plan.md" if used_frac < 0.8 else "finish the step, then compact at the boundary"
    if used_frac > 0.8 or phase_boundary:
        return "/compact"
    return "continue"


def tier(task, failed_before=False, gap_shown=False):
    light = {"search", "classification", "boilerplate", "docs lookup"}
    strong = {"architecture", "security review", "root-cause debugging", "multi-file invariants"}
    if task in strong or (failed_before and gap_shown):
        return "strongest"
    if task in light:
        return "light"
    return "default"


HANDOFF = ("Goal", "What worked", "Tried and failed", "Left to do", "Next command")


def handoff_check(text, max_bytes=4000):
    heads = re.findall(r"^## (.+)$", text, re.M)
    errs = [h for h in HANDOFF if h not in heads]
    if len(text.encode()) > max_bytes:
        errs.append("too long to load bounded")
    if "What worked" in heads and not re.search(r"(/|\.json|\.log|\.mp4)", text.split("## What worked")[1].split("##")[0]):
        errs.append("what worked needs evidence paths")
    return errs


def memory_layer(item):
    k = item["kind"]
    return {"always rule": "CLAUDE.md", "personal note": "auto memory", "team knowledge": "project docs",
            "shared code fact": "hosted Graphify remember (ask)", "repo lesson": "graphify save-result + reflect",
            "api app memory": "memory tool", "whenever behaviour": "hook"}[k]


ROSTER = [("complex feature", "planner"), ("code just written", "code-reviewer"), ("bug or feature", "tdd-guide"),
          ("build broken", "build-error-resolver"), ("security-sensitive change", "security-reviewer"),
          ("brownfield spec", "spec-miner"), ("loop stalls", "loop-operator"), ("harness cost", "harness-optimizer"),
          ("quality score", "agent-evaluator")]


def pick_agent(situation):
    for k, v in ROSTER:
        if all(w in situation.lower() for w in k.split()[:2]):
            return v
    return None


def nearest_instruction(root: Path, file: Path):
    d = file.parent
    while True:
        for n in ("AGENTS.md", "CLAUDE.md"):
            if (d / n).exists():
                return str((d / n).relative_to(root))
        if d == root:
            return None
        d = d.parent


COMPACT = ("progress", "constraints", "next_steps", "critical_data")


def can_continue(summary, needed_facts):
    blob = json.dumps(summary, ensure_ascii=False)
    return all(summary.get(f) for f in COMPACT) and all(n in blob for n in needed_facts)


ALLOWED = re.compile(r"^(cat|ls|grep|rg|find|git (status|log|diff)|pytest|python3 -m pyflakes|.*--dry-run)\b")


MUTATE = re.compile(r"\b(sed -i|apply|patch|migrate|black|prettier --write|>|rm |mv |git (commit|push))\b")


def plan_mode_allows(cmd):
    if cmd.rstrip().endswith("--dry-run") and ">" not in cmd:
        return True
    return bool(ALLOWED.match(cmd)) and not MUTATE.search(cmd)


def checklist_ok(plan, task_steps):
    errs = []
    if task_steps == 1 and plan:
        errs.append("no plan for single-step work")
    active = [s for s in plan if s["state"] == "in_progress"]
    if len(active) > 1:
        errs.append("mark a step done before starting the next")
    errs += [f"step without visible result: {s['text']}" for s in plan if not s.get("result")]
    errs += [f"filler step: {s['text']}" for s in plan if re.match(r"(think|review everything|be careful)", s["text"], re.I)]
    return errs


def turn_kind(t):
    if t.get("state_changed") or t.get("evidence_changed"):
        return "progress"
    if t.get("polled_live_handle"):
        return "verified wait"
    return "no progress"


def blocked_now(turns):
    b = [t.get("blocker") for t in turns[-3:]]
    return len(b) == 3 and b[0] is not None and len(set(b)) == 1


def audit(reqs):
    return {r["req"]: ("done" if r["evidence"] == "proves" else "not done") for r in reqs}


def envelope(id_, out, exit_code, wall, limit=200):
    b = out.encode()
    body = out
    header = ""
    if len(b) > limit:
        body = b[:limit].decode("utf-8", "ignore")
        header = f"[truncated: showing {limit} of {len(b)} bytes]\n"
    return {"schema": "kosif.tool-envelope.v1", "id": id_, "wall_s": wall, "exit_code": exit_code, "original_bytes": len(b),
            "output": header + body}


def run_graph(nodes, state, ckdir: Path, fail_at=None, approve=False):
    ckdir.mkdir(exist_ok=True)
    done = sorted(ckdir.glob("*.json"))
    step0 = 0
    if done:
        last = json.loads(done[-1].read_text())
        state, step0 = last["state"], last["step"] + 1
    for i in range(step0, len(nodes)):
        name, fn = nodes[i]
        if name == "publish" and not approve:
            return state, f"interrupt before publish (pending: {sorted(state)})"
        if name == fail_at:
            return state, f"failed at {name}"
        state = {**state, **fn(state)}
        (ckdir / f"{i:03d}.json").write_text(json.dumps({"thread": "t1", "step": i, "node": name, "state": state,
                                                         "hash": sha256(json.dumps(state, sort_keys=True))}))
    return state, "complete"


def crew(tasks, outputs):
    log, results = [], {}
    for t in tasks:
        missing_ctx = [c for c in t["context"] if c not in results]
        if missing_ctx:
            raise ValueError(f"{t['id']} reads unknown outputs {missing_ctx}")
        out = outputs[t["id"]][0]
        if not t["accept"](out):
            log.append(f"{t['id']}: returned once, gap: {t['expected_output']}")
            out = outputs[t["id"]][1] if len(outputs[t["id"]]) > 1 else None
            if out is None or not t["accept"](out):
                log.append(f"{t['id']}: rejected")
                continue
        results[t["id"]] = out
    return results, log


TEMPLATES = {"requirements": ("goals", "user_stories", "non_goals"), "design": ("components", "interfaces", "data"),
             "tasks": ("files", "order", "owner")}


SUBS = {"designer": ["requirements"], "planner": ["design"], "qa": ["requirements", "tasks"]}


def handoff(doc_type, doc):
    empty = [f for f in TEMPLATES[doc_type] if not doc.get(f)]
    return not empty, empty


def retrigger(changed):
    return sorted(r for r, docs in SUBS.items() if changed in docs)


def capture(events):
    obs = [{"tool": e["tool"], "target": e["target"], "outcome": e["outcome"]} for e in events
           if not e.get("private") and not SECRET.search(json.dumps(e))]
    summary = {"done": [o["target"] for o in obs if o["outcome"] == "ok"], "decisions": [], "open": [o["target"] for o in obs if o["outcome"] != "ok"],
               "files_touched": sorted({o["target"] for o in obs if o["tool"] in ("Write", "Edit")})}
    return obs, summary


WHITELIST = {"math", "json", "statistics"}


def safe_snippet(code):
    tree = ast.parse(code)
    for n in ast.walk(tree):
        if isinstance(n, (ast.Import, ast.ImportFrom)):
            mods = [a.name for a in n.names] if isinstance(n, ast.Import) else [n.module]
            bad = [m for m in mods if m.split(".")[0] not in WHITELIST]
            if bad:
                return False, f"import not allowed: {bad}"
        if isinstance(n, ast.Call) and getattr(n.func, "id", "") in ("open", "exec", "eval", "__import__"):
            return False, f"call not allowed: {n.func.id}"
    return True, ""


def agent_loop(snippets, work, max_steps=10):
    obs, plans = [], []
    for i, code in enumerate(snippets[:max_steps], 1):
        if i % 3 == 0:
            plans.append(f"step {i}: restate plan")
        ok, why = safe_snippet(code)
        if not ok:
            obs.append(f"refused: {why}")
            continue
        r = subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, text=True, timeout=5, cwd=str(work),
                           env={"PATH": os.environ.get("PATH", "")})
        obs.append(r.stdout.strip())
    return obs, plans


def tripwire(inp):
    if SECRET.search(inp):
        return "secret-bearing input"
    if re.search(r"\b(bomb|malware|credit card dump)\b", inp, re.I):
        return "unsafe"
    if not re.search(r"video|reel|caption|فيديو|ترجمة", inp, re.I):
        return "out of scope"
    return None


def run_turn(inp, trace):
    trace.append({"span": "guardrail", "name": "input"})
    trip = tripwire(inp)
    if trip:
        trace.append({"span": "guardrail", "tripped": trip})
        return f"stopped: {trip}"
    trace.append({"span": "handoff", "to": "transfer_to_captions", "turns": 1})
    out = {"captions": 12}
    trace.append({"span": "guardrail", "name": "output", "ok": isinstance(out["captions"], int)})
    return out


def reduce(events):
    state = {}
    for e in events:
        if e["kind"] == "observation" and e["payload"].get("set"):
            state.update(e["payload"]["set"])
    return state


def view(events, recent=3):
    old = events[:-recent]
    summary = f"{len(old)} older events: " + ", ".join(sorted({e['source'] for e in old}))
    return {"summary": summary, "recent": events[-recent:]}
