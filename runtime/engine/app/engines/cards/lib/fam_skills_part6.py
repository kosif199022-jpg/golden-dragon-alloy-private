"""Helpers of runners/fam_skills_part6.py used by data cards, copied verbatim (the extractor binds a card to them only when
their AST hash with every dependency equals the original's)."""
from __future__ import annotations

from pathlib import Path
import ast
import ipaddress
import json
import math
import os
import re
import subprocess


def jw(path, obj):
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
    return Path(path)


def wt(path, text):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(text, encoding="utf-8")
    return Path(path)


VAGUE = ["appropriately", "as needed", "etc.", "similar to", "clean up", "handle edge cases", "best practices",
         "follow the existing pattern", "tbd", "consider", "decide whether", "might", "could"]


def lint_plan(text):
    low = text.lower()
    lines = text.splitlines()
    issues = []
    for w in VAGUE:
        for m in re.finditer(r"(?<![a-z])" + re.escape(w) + r"(?![a-z])", low):
            issues.append("vague:" + w)
    if re.search(r"\bline \d+|:\d+\b|\bL\d+\b", text):
        issues.append("line-number reference")
    if re.search(r"Docs:.*\d+\.(x|\*)", text) or re.search(r"\d+\.\d+\.x\b", text):
        issues.append("inexact docs version")
    for sec in ("## Done when", "## Report back"):
        if sec not in text:
            issues.append("missing " + sec)
    cps = len(re.findall(r"Checkpoint:", text))
    if not 2 <= cps <= 4:
        issues.append("checkpoints=%d" % cps)
    if len(lines) > 100:
        issues.append("over 100 lines")
    if re.search(r"^\s*(def |function |\{\s*$)", text, re.M):
        issues.append("function body")
    return issues


RUNG = {"native": 1, "official": 2, "third-party": 3}


def pick(problem, candidates):
    need = set(problem["requirements"]) | set(problem["plausible_future"])
    rows = []
    for c in candidates:
        miss = sorted(need - set(c["covers"]))
        coupling = None
        if c["rung"] == "third-party":
            keys = ("maintained", "license", "security", "exit_cost")
            coupling = {k: c.get(k) for k in keys}
            if not all(c.get(k) for k in keys[:3]) or c.get("license") not in ("MIT", "BSD-3-Clause", "Apache-2.0"):
                miss.append("coupling not acceptable")
        rows.append({"name": c["name"], "rung": c["rung"], "missing": miss, "coupling": coupling})
    ok = sorted([r for r in rows if not r["missing"]], key=lambda r: RUNG[r["rung"]])
    return (ok[0]["name"] if ok else None), rows


INCUMBENT = r"(that'?s how (this repo|we|it)|always been|the existing code does|it just is|we'?ve always|because it'?s there|legacy says|match(es)? the existing)"


PURPOSE = r"(so that|to prevent|in order to|required by|ensures?|because .*(fail|break|leak|cost|latency|security|spec)|guarantees?)"


def recite_audit(records):
    out = []
    for r in records:
        inc = bool(re.search(INCUMBENT, r["why"], re.I))
        pur = bool(re.search(PURPOSE, r["why"], re.I))
        out.append({"id": r["id"], "incumbency_only": inc and not pur, "names_purpose": pur,
                    "status": "candidate: re-derive from purpose (verdict stays judgment)" if inc and not pur else "live rationale or no precedent claim"})
    return out


def snake(s):
    s = re.sub(r"[-\s]+", "_", s)
    s = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", s)
    return s.lower()


def name_merge(pool, siblings, rejects, user_block, agent_block, affix="", reshape=True):
    def words(s):
        return set(snake(s).split("_"))
    keep, dropped = [], []
    seen = set()
    for c in pool:
        reason = None
        key = c.lower()
        if key in seen:
            reason = "duplicate"
        elif snake(c) in {snake(r) for r in rejects}:
            reason = "rejected incumbent"
        elif words(c) & set(user_block):
            reason = "user blocklist"
        elif snake(c) in {snake(s) for s in siblings}:
            reason = "collision"
        seen.add(key)
        (dropped if reason else keep).append({"name": c, "reason": reason})
    if reshape:
        shaped, out = set(), []
        for k in keep:
            s = snake(k["name"]) + affix
            reason = None
            if s in shaped:
                reason = "duplicate after shaping"
            elif s in {snake(r) for r in rejects}:
                reason = "rejected after shaping"
            elif s in {snake(x) for x in siblings}:
                reason = "collision after shaping"
            elif set(s.split("_")) & set(user_block):
                reason = "blocklist after shaping"
            shaped.add(s)
            if reason:
                dropped.append({"name": k["name"], "reason": reason})
            else:
                out.append({"name": k["name"], "shaped": s})
        keep = out
    for k in keep:
        k["flag"] = sorted(set(snake(k["name"]).split("_")) & set(agent_block))
    return keep, dropped


def netcheck(cfg, existing, mgmt_if):
    lines = [l.rstrip() for l in cfg.splitlines()]
    finds = []
    iface = None
    ips = []
    acl = {}
    for i, l in enumerate(lines, 1):
        s = l.strip()
        if s.startswith("interface "):
            iface = s.split(None, 1)[1]
        if s == "shutdown" and iface == mgmt_if:
            finds.append(("dangerous", i, "shutdown on management interface " + mgmt_if))
        if re.match(r"(write erase|erase startup-config|reload|no aaa new-model)", s):
            finds.append(("dangerous", i, s))
        m = re.match(r"ip address (\S+) (\S+)", s)
        if m:
            net = ipaddress.ip_interface("%s/%s" % m.groups())
            ips.append((i, iface, net))
        if re.match(r"switchport trunk allowed vlan all", s):
            finds.append(("template", i, "trunk allows all VLANs"))
        m = re.match(r"access-list (\d+) (permit|deny) (\S+)(?: (\S+))?", s)
        if m:
            acl.setdefault(m.group(1), []).append((i, m.group(2), m.group(3), m.group(4)))
    seen = {}
    for i, f, net in ips:
        if str(net.ip) in seen or str(net.ip) in existing["ips"]:
            finds.append(("duplicate-ip", i, str(net.ip)))
        seen[str(net.ip)] = i
        for e in existing["subnets"]:
            if net.network.overlaps(ipaddress.ip_network(e)):
                finds.append(("overlap", i, "%s overlaps %s" % (net.network, e)))
    for n, rules in acl.items():
        for k, (i, act, src, wc) in enumerate(rules):
            for (j, act2, src2, wc2) in rules[:k]:
                if src2 == "any":
                    finds.append(("acl-shadowed", i, "rule under 'access-list %s %s any' is dead" % (n, act2)))
                    break
    if not any(re.match(r"(write memory|copy run(ning-config)? start(up-config)?)", l.strip()) for l in lines):
        finds.append(("incomplete", len(lines), "no write memory / copy run start"))
    return finds


MEANINGLESS = {"common", "util", "utils", "helper", "helpers", "misc", "result", "data", "stuff"}


def naming_lint(root):
    root = Path(root)
    finds = []
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root).as_posix()
        stem = p.stem if p.is_file() else p.name
        parts = set(re.split(r"[_\-.]", stem.lower()))
        if parts & MEANINGLESS:
            finds.append(("meaningless-path", rel))
        elif p.suffix == ".py" and re.search(r"[a-z]{3,}s$", stem) and not stem.endswith(("ss", "us", "is")):
            finds.append(("plural-module", rel))
        if p.suffix == ".py":
            tree = ast.parse(p.read_text())
            for n in ast.walk(tree):
                nm = None
                if isinstance(n, ast.FunctionDef):
                    nm = n.name
                elif isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store):
                    nm = n.id
                elif isinstance(n, ast.ClassDef) and n.name.endswith("s") and not n.name.endswith("ss"):
                    finds.append(("plural-type", "%s:%s" % (rel, n.name)))
                if nm and set(nm.lower().split("_")) & MEANINGLESS:
                    finds.append(("meaningless-name", "%s:%s" % (rel, nm)))
    return sorted(set(finds))


def circle_audit(cfg):
    import yaml
    c = yaml.safe_load(cfg)
    f = []
    for jn, job in (c.get("jobs") or {}).items():
        for st in job.get("steps", []):
            if isinstance(st, dict):
                for k in ("save_cache", "restore_cache"):
                    if k in st:
                        keys = [st[k].get("key")] if st[k].get("key") else st[k].get("keys", [])
                        for key in keys:
                            if "{{ epoch }}" in key or "{{ .BuildNum }}" in key or "{{ .Revision }}" in key:
                                f.append((jn, "cache key rotates every run"))
                            if "checksum" in key and not re.search(r'checksum "[^"]*(lock|\.sum)', key):
                                f.append((jn, "cache key not on a lockfile"))
                if "run" in st and isinstance(st["run"], dict) and re.search(r"(retry|\|\| true|for i in)", st["run"].get("command", "")):
                    f.append((jn, "blanket retry hides failures"))
        if jn.startswith("test") and not any(isinstance(s, dict) and "store_test_results" in s for s in job.get("steps", [])):
            f.append((jn, "no store_test_results"))
    for wn, wf in (c.get("workflows") or {}).items():
        if not isinstance(wf, dict):
            continue
        names = [list(j)[0] if isinstance(j, dict) else j for j in wf.get("jobs", [])]
        for n in set(names):
            if names.count(n) > 1:
                f.append((wn, "duplicate job " + n))
        reqs = {list(j)[0]: j[list(j)[0]].get("requires", []) for j in wf.get("jobs", []) if isinstance(j, dict)}
        types = {list(j)[0]: j[list(j)[0]].get("type") for j in wf.get("jobs", []) if isinstance(j, dict)}
        if "deploy" in reqs and not any(types.get(r) == "approval" for r in reqs["deploy"]):
            f.append((wn, "deploy without approval gate"))
    return sorted(set(f))


def _tree_hash(root):
    import hashlib
    h = hashlib.sha256()
    for p in sorted(Path(root).rglob("*")):
        if p.is_file():
            h.update(p.relative_to(root).as_posix().encode())
            h.update(p.read_bytes())
    return h.hexdigest()


def recommend(root):
    root = Path(root)
    pkg = json.loads((root / "package.json").read_text()) if (root / "package.json").exists() else {}
    deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
    sig = {
        "react": "react" in deps, "frontend": bool({"react", "vue", "@angular/core", "next"} & set(deps)),
        "prisma": "prisma" in deps or "@prisma/client" in deps, "github": (root / ".github").is_dir(),
        "prettier": "prettier" in deps or (root / ".prettierrc").exists(), "eslint": "eslint" in deps,
        "typescript": (root / "tsconfig.json").exists(), "tests": (root / "tests").is_dir() or (root / "__tests__").is_dir(),
        "env": any(root.glob(".env*")), "auth": any(re.search(r"auth|payment", p.relative_to(root).as_posix()) for p in root.rglob("*.ts")),
        "claude": (root / ".claude").exists(),
    }
    rec = {"mcp": [], "skills": [], "hooks": [], "subagents": [], "plugins": []}
    if sig["react"]:
        rec["mcp"].append(("context7", "React is a popular library: live docs lookup"))
    if sig["frontend"]:
        rec["mcp"].append(("Playwright", "frontend with UI testing needs"))
    if sig["prisma"] and len(rec["mcp"]) < 2:
        rec["mcp"].append(("Database MCP", "Prisma schema"))
    if sig["prettier"]:
        rec["hooks"].append(("PostToolUse: auto-format on edit", "Prettier configured"))
    if sig["env"]:
        rec["hooks"].append(("PreToolUse: block .env edits", ".env files present"))
    elif sig["typescript"]:
        rec["hooks"].append(("PostToolUse: type-check on edit", "TypeScript project"))
    if sig["auth"]:
        rec["subagents"].append(("security-reviewer", "auth/payments code"))
    if sig["tests"]:
        rec["skills"].append(("gen-test", "test suite present"))
    if sig["frontend"]:
        rec["plugins"].append(("frontend-design", "frontend development"))
    rec = {k: v[:2] for k, v in rec.items() if v}
    return sig, rec


def sv_review(path):
    src = Path(path).read_text().splitlines()
    finds = []
    block = None
    depth = 0
    for i, line in enumerate(src, 1):
        s = re.sub(r"//.*", "", line).strip()
        if re.match(r"`define\s", s):
            finds.append(("P2", i, "`define for a constant: use localparam/parameter in a package"))
        if re.search(r"\b(reg|wire)\b", s) and not s.startswith("//"):
            finds.append(("P2", i, "legacy reg/wire: use logic"))
        m = re.match(r"always\s*@\s*\((posedge|negedge)", s)
        if m:
            finds.append(("P1", i, "always @(edge): use always_ff"))
            block = "ff"
        elif re.match(r"always\s*@\s*(\(\*\)|\*)", s):
            finds.append(("P1", i, "always @*: use always_comb"))
            block = "comb"
        elif s.startswith("always_ff"):
            block = "ff"
        elif s.startswith("always_comb"):
            block = "comb"
        if block == "ff" and re.search(r"(?<![<=!>])=(?!=)", s) and "<=" not in s and not s.startswith(("always", "case")):
            finds.append(("P0", i, "blocking assignment in a sequential block: use <="))
        if block == "comb" and re.match(r"if\s*\(", s):
            rest = "\n".join(src[i:i + 4])
            if not re.search(r"\belse\b", rest):
                finds.append(("P0", i, "if without else in combinational logic infers a latch"))
        if re.match(r"case\s*\(", s):
            finds.append(("P1", i, "bare case: use unique case / priority case"))
        if re.match(r"\w+\s+\w+\s*\(\s*\w+\s*,", s) and not s.startswith(("module", "function", "task")):
            finds.append(("P1", i, "positional port connection: use .port(signal)"))
        if s.startswith("end") and s in ("end", "endcase"):
            depth = 0
        if s.startswith(("endmodule", "assign")):
            block = None
    return finds


def conformance(plan, repo):
    rows = []
    for it in plan["items"]:
        done = subprocess.run(it["check"], shell=True, capture_output=True, text=True, cwd=str(repo), timeout=30,
                              stdin=subprocess.DEVNULL, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
        got = done.stdout.strip()
        rows.append({"id": it["id"], "spec": it["spec"], "command": it["check"], "observed": got, "expected": it["expect"],
                     "status": "conforms" if done.returncode == 0 and got == it["expect"] else "gap"})
    actual = sorted(p.relative_to(repo).as_posix() for p in repo.rglob("*") if p.is_file())
    drift = sorted(set(actual) - set(plan["only_files"]))
    return rows, drift


PLAN_SECTIONS = ["The ask", "Summary", "The problem", "The solution", "Technical context", "Tickets", "Decisions",
                 "Gotchas and caveats", "Out of scope", "Open questions"]


HISTORY = r"\b(previously|earlier version|we changed|was changed|in the last revision|v\d of (this|the) plan|updated:|no longer|now we)\b"


def plan_contract(md):
    issues = []
    heads = re.findall(r"^## (.+)$", md, re.M)
    top = [h for h in heads if h in PLAN_SECTIONS]
    if top != PLAN_SECTIONS:
        issues.append("sections missing or out of order")
    secs = re.split(r"^## ", md, flags=re.M)
    for s in secs[1:]:
        name, _, body = s.partition("\n")
        if name in PLAN_SECTIONS and not body.strip():
            issues.append("empty section without a one-line note: " + name)
        if name == "Summary" and re.search(r"`|\b\w+_\w+\b|\w+\(\)", body):
            issues.append("identifier in Summary")
    for m in re.finditer(HISTORY, md, re.I):
        issues.append("history narration: " + m.group(0))
    if not md.startswith("# "):
        issues.append("no imperative title")
    tickets = re.findall(r"^### Ticket: (.+?) \(depends on: (.*?)\)$", md, re.M)
    seen = set()
    for t, dep in tickets:
        for d in [x.strip() for x in dep.split(",") if x.strip() and x.strip() != "none"]:
            if d not in seen:
                issues.append("ticket before its dependency: " + t)
        seen.add(t)
    return issues


def parse_usage(text):
    out = {}
    for line in text.splitlines():
        m = re.search(r"(Current session|Current week \(all models\)|Current week \(Opus\))\D*(\d+(?:\.\d+)?)%.*?[Rr]esets? (?:at |in )?(.+)$", line)
        if m:
            out[m.group(1)] = {"pct": float(m.group(2)), "reset": m.group(3).strip()}
    return out


def limits_decision(usage, now_s, reset_s, threshold=95.0, wave=3):
    over = sorted(k for k, v in usage.items() if v["pct"] >= threshold)
    if not over:
        return {"action": "launch next wave", "max_parallel": wave, "over": []}
    secs = max(0, reset_s - now_s)
    chain = []
    left = secs
    while left > 0:
        step = min(3600, left)
        chain.append(step)
        left -= step
    return {"action": "pause", "over": over, "wake_in_s": chain[0], "chain": chain, "max_parallel": 0}


def intent_audit(docs_md, app_src):
    claims = {}
    for m in re.finditer(r"^\|\s*`(\w+)\s+(/[^`]*)`\s*\|\s*([\w-]+)\s*\|\s*(\w+)\s*\|", docs_md, re.M):
        claims[(m.group(1), m.group(2))] = {"role": m.group(3), "tenant_scoped": m.group(4) == "yes"}
    tree = ast.parse(app_src)
    impl = {}
    for fn in [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]:
        route, role = None, None
        for d in fn.decorator_list:
            if isinstance(d, ast.Call) and getattr(d.func, "attr", getattr(d.func, "id", "")) in ("get", "post", "delete"):
                route = (d.func.attr.upper(), d.args[0].value)
            if isinstance(d, ast.Call) and getattr(d.func, "id", "") == "require_role":
                role = d.args[0].value
        if route:
            src = ast.get_source_segment(app_src, fn)
            impl[route] = {"role": role, "tenant_filter": "tenant_id" in src and "query(" in src
                           and bool(re.search(r"tenant_id\s*=\s*user\.tenant_id", src)), "line": fn.lineno, "name": fn.name}
    finds = []
    for r, c in claims.items():
        i = impl.get(r)
        if not i:
            finds.append({"route": " ".join(r), "kind": "documented route missing in code"})
            continue
        if c["role"] != "public" and i["role"] != c["role"]:
            finds.append({"route": " ".join(r), "kind": "documented-but-unenforced role", "intent": c["role"], "implemented": i["role"],
                          "evidence": "app.py:%d %s" % (i["line"], i["name"]), "fix": "add @require_role(%r)" % c["role"]})
        if c["tenant_scoped"] and not i["tenant_filter"]:
            finds.append({"route": " ".join(r), "kind": "tenant boundary not enforced", "evidence": "app.py:%d %s" % (i["line"], i["name"]),
                          "fix": "filter query by tenant_id=user.tenant_id"})
    for r, i in impl.items():
        if r not in claims:
            finds.append({"route": " ".join(r), "kind": "undocumented (docs stale)"})
    return claims, impl, finds


VAGUE_AC = r"\b(fast|easy|user-friendly|intuitive|properly|appropriately|etc|nice|good)\b"


def story_lint(s):
    issues = []
    if not re.fullmatch(r"As an? [^,]+, I want to [^,]+, so that .+\.", s.get("description", "")):
        issues.append("description not 'As a…, I want to…, so that…'")
    n = len(s.get("ac", []))
    if not 4 <= n <= 6:
        issues.append("acceptance criteria count %d" % n)
    for a in s.get("ac", []):
        if re.search(VAGUE_AC, a, re.I):
            issues.append("untestable criterion: " + a)
    if re.search(r"\b(after|depends on|requires) story\b", json.dumps(s), re.I):
        issues.append("not independent")
    if not s.get("design", "").startswith("http"):
        issues.append("no design link")
    return issues


def wwa_lint(it):
    issues = []
    why = [x for x in re.split(r"(?<=\.)\s+", it.get("why", "").strip()) if x]
    if not 1 <= len(why) <= 2:
        issues.append("why must be 1-2 sentences")
    if not re.search(r"\b(goal|objective|OKR|strategy|supports)\b", it.get("why", ""), re.I):
        issues.append("why not tied to an objective")
    if len([p for p in it.get("what", "").split("\n\n") if p.strip()]) > 2 or "http" not in it.get("what", ""):
        issues.append("what over 2 paragraphs or no design link")
    acs = it.get("ac", [])
    if not 3 <= len(acs) <= 6:
        issues.append("acceptance count %d" % len(acs))
    for a in acs:
        if re.search(VAGUE_AC, a, re.I) or not re.search(r"\d|visible|shown|displays|can |updates|rejects|handles", a, re.I):
            issues.append("not observable: " + a)
    return issues


def size_market(m):
    td = m["industry_revenue"] * m["segment_share"]
    bu = m["target_customers"] * m["price"] * m["purchases_per_year"]
    gap = abs(td - bu) / max(td, bu)
    tam = (td + bu) / 2
    sam = tam * m["serviceable_share"]
    som = sam * m["obtainable_share"]
    proj = {k: v * (1 + m["cagr"]) ** m["years"] for k, v in (("TAM", tam), ("SAM", sam), ("SOM", som))}
    return {"top_down": td, "bottom_up": bu, "divergence": gap, "reconciled_TAM": tam, "SAM": sam, "SOM": som,
            "projection": proj, "wide_interval": gap > 0.25}


def two_prop_z(x1, n1, x2, n2):
    p1, p2 = x1 / n1, x2 / n2
    p = (x1 + x2) / (n1 + n2)
    se = math.sqrt(p * (1 - p) * (1 / n1 + 1 / n2))
    z = (p2 - p1) / se
    pval = 2 * (1 - 0.5 * (1 + math.erf(abs(z) / math.sqrt(2))))
    return z, pval


def wilson(x, n, z=1.96):
    p = x / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return c - h, c + h


def classify(f):
    if f["element_exists"] is False:
        cls = "Major NC" if f.get("systemic") or f.get("affects_qms_results") else "Major NC"
    elif f.get("partial"):
        cls = "Major NC" if f.get("systemic") else "Minor NC"
    elif f.get("risk"):
        cls = "OFI"
    else:
        cls = "Conforming"
    return cls


def audit_report(meta, findings):
    problems = []
    if meta["auditor_area"] == meta["audited_area"]:
        problems.append("auditor not independent")
    by_clause = {}
    for f in findings:
        f["class"] = classify(f)
        by_clause.setdefault((f["clause"], f["class"]), []).append(f)
        if f["class"] != "Conforming" and (f.get("records_sampled", 0) < 2 or f.get("people", 0) < 2):
            problems.append("sampling below 2-3 records/people: " + f["id"])
        if re.search(r"\b(not good|some|bad|poor|they said)\b", f["observation"], re.I) or not re.search(r"\d", f["observation"]):
            problems.append("observation not specific/factual: " + f["id"])
        if f.get("evidence_type") == "verbal":
            problems.append("verbal confirmation is not objective evidence: " + f["id"])
    for (clause, cls), fs in by_clause.items():  # the same minor NC in several records → systemic → Major
        if cls == "Minor NC" and len(fs) >= 2:
            for f in fs:
                f["class"] = "Major NC"
                f["reclassified"] = "repeated minor NC on §%s indicates systemic failure" % clause
    actions = [{"ref": f["id"], "class": f["class"], "owner": f.get("owner"), "target": f.get("target"), "car": f.get("car")}
               for f in findings if f["class"] == "Major NC"]
    for a in actions:
        if not (a["owner"] and a["target"] and a["car"]):
            problems.append("Major NC without CAR owner/date: " + a["ref"])
    counts = {c: sum(1 for f in findings if f["class"] == c) for c in ("Major NC", "Minor NC", "OFI")}
    return counts, actions, problems


def cp_validate(rows, pfmea):
    gaps = []
    for r in rows:
        rid = "%s/%s" % (r["step"], r["characteristic"])
        if not re.fullmatch(r"\d+( pcs)?", str(r["sample_size"])):
            gaps.append(rid + ": sample size must be a number")
        if re.search(r"as required", r["frequency"], re.I):
            gaps.append(rid + ": frequency 'as required'")
        if re.fullmatch(r"\s*(notify supervisor|quarantine parts)\.?\s*", r["reaction"], re.I):
            gaps.append(rid + ": reaction plan stops before the next step")
        if r.get("special") in ("SC", "CC") and r["method"] == "visual" and r["type"] == "variable":
            gaps.append(rid + ": visual-only control for a variable special characteristic")
        if r.get("special") in ("SC", "CC") and r["type"] == "variable" and (r.get("grr") is None or r["grr"] > 30):
            gaps.append(rid + ": MSA missing or %GRR > 30")
        if r.get("special") in ("SC", "CC") and r["frequency"] != "100%" and (r.get("cpk") or 0) < 1.67:
            gaps.append(rid + ": special characteristic without 100% or Cpk >= 1.67")
    covered = {(r["step"], r["characteristic"]) for r in rows}
    for fm in pfmea:
        if fm["ap"] == "H":
            if (fm["step"], fm["characteristic"]) not in covered:
                gaps.append("PFMEA %s: H-AP failure mode has no Control Plan row" % fm["id"])
            elif fm.get("controls") == "inspection" and not any(r.get("poka_yoke") for r in rows if (r["step"], r["characteristic"]) == (fm["step"], fm["characteristic"])):
                gaps.append("PFMEA %s: H-AP controlled by inspection only, add poka-yoke" % fm["id"])
    return gaps
