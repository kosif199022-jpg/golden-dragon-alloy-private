"""Helpers of runners/fam_skills_part3.py used by data cards, copied verbatim (the extractor binds a card to them only when
their AST hash with every dependency equals the original's)."""
from __future__ import annotations

from pathlib import Path
import json
import re
import textwrap


def wt(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(text).lstrip("\n"), encoding="utf-8")
    return path


def jw(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
    return path


def md_table(rows, head):
    out = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def _memo(wd, name, title, sections):
    body = ["# " + title, ""]
    for h, txt in sections:
        body += ["## " + h, txt if isinstance(txt, str) else "\n".join("- " + str(x) for x in txt), ""]
    return wt(wd / name, "\n".join(body))


def _decision(wd, status="APPROVED"):
    return wt(wd / "decision.md", """
        # Decision: Move SMB tier to usage pricing
        **Status:** %s
        **Date:** 2026-04-01
        **Type:** pricing
        **Sponsor:** Dana (CEO)
        **Chosen option:** usage-based pricing for SMB
        ## Success criteria
        - SMB net revenue: >= 1.10 (index vs baseline)
        - SMB logo churn: <= 0.03
        ## Kill criteria
        - SMB logo churn: > 0.06
        ## Devil's advocate concerns
        - Billing system cannot meter usage in time
        - Support volume spikes after the change
        ## Dissent
        - CFO: revenue will dip for two quarters
        """ % status)


def _parse_decision(path):
    t = Path(path).read_text(encoding="utf-8")
    sec = {}
    cur = None
    for ln in t.splitlines():
        if ln.startswith("## "):
            cur = ln[3:].strip()
            sec[cur] = []
        elif cur and ln.startswith("- "):
            sec[cur].append(ln[2:].strip())
    head = dict(re.findall(r"\*\*(\w[\w ]*):\*\* (.+)", t))
    return head, sec


FREEZE_DAYS = {"fundraise": 30, "pricing": 60, "market": 90, "layoff": 30, "pivot": 90, "personnel": 60, "m&a": 30}


def _freeze(path, today, reason):
    import datetime as dt
    head, _ = _parse_decision(path)
    if head.get("Status") != "APPROVED":
        return None
    days = FREEZE_DAYS[head["Type"]]
    until = (dt.date.fromisoformat(today) + dt.timedelta(days=days)).isoformat()
    t = Path(path).read_text(encoding="utf-8").replace("**Status:** APPROVED", "**Status:** FROZEN\n**Frozen until:** %s\n"
                                                        "**Reason for freeze:** %s\n**Override condition:** Kill criterion "
                                                        "SMB logo churn triggers OR /cs:unfreeze with stated reason" % (until, reason))
    Path(path).write_text(t, encoding="utf-8")
    return until


def _router(path, today, kill_triggered=False):
    head, _ = _parse_decision(path)
    if head.get("Status") == "FROZEN" and today < head["Frozen until"] and not kill_triggered:
        return "refuse: frozen until " + head["Frozen until"]
    return "route to boardroom"


def _hashes(root):
    import hashlib
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(Path(root).rglob("*")) if p.is_file() and not p.is_symlink()}


CH_FIELDS = ["Purpose", "Entry state", "Exit state", "Pull", "Content", "Sets up", "Pays off", "Must not", "Length target"]


def _outline_text(chapters, approved=False):
    out = ["# Outline: Small Data, Big Decisions", "", "## Structure and rationale",
           "Nonfiction: problem -> principles -> practice -> advanced, chosen because readers arrive with a problem.", "",
           "## Pacing map", md_table([(c["n"], c["title"], c["Length target"]) for c in chapters], ["Ch", "Title", "Words"]), "",
           "## Chapter specs"]
    for c in chapters:
        out += ["### %d. %s" % (c["n"], c["title"])] + ["- **%s:** %s" % (f, c.get(f, "")) for f in CH_FIELDS if f in c] + [""]
    out += ["## Validation", "structure checked by outline_gate()"]
    if approved:
        out += ["", "## Approval", approved]
    return "\n".join(out) + "\n"


def _outline_gate(text):
    specs = re.split(r"^### (\d+)\. .+$", text, flags=re.M)
    chs = {}
    for i in range(1, len(specs), 2):
        chs[int(specs[i])] = dict(re.findall(r"^- \*\*(.+?):\*\* (.*)$", specs[i + 1], re.M))
    issues = []
    for n, c in chs.items():
        for f in ["Purpose", "Entry state", "Exit state", "Pull", "Content"]:
            if not c.get(f):
                issues.append("ch%d missing %s" % (n, f))
    purposes = [c.get("Purpose") for c in chs.values()]
    if len(set(purposes)) != len(purposes):
        issues.append("duplicate purpose (one chapter redundant)")
    for n, c in chs.items():
        for ref in re.findall(r"ch(\d+)", c.get("Sets up", "")):
            r = int(ref)
            if r not in chs or r <= n:
                issues.append("ch%d sets up ch%d which is missing or earlier" % (n, r))
            elif "ch%d" % n not in chs[r].get("Pays off", ""):
                issues.append("ch%d setup not paid off in ch%d" % (n, r))
    return {"chapters": len(chs), "issues": issues, "score": max(0, 10 - 2 * len(issues)),
            "approved": "## Approval" in text}


EARS = re.compile(r"^(?:(?:WHEN|WHILE|IF|WHERE) .+?,?\s*)?THE SYSTEM SHALL .+$")


def _spec_check(req_md, tasks_md):
    us = re.findall(r"^### (US-\d+)", req_md, re.M)
    crit = re.findall(r"^\d+\. (.+)$", req_md, re.M)
    bad_ears = [c for c in crit if not EARS.match(c)]
    tasks = {}
    for blk in re.split(r"^### ", tasks_md, flags=re.M)[1:]:
        tid = blk.split(":")[0]
        f = dict(re.findall(r"^- \*\*(\w+)\*\*: (.+)$", blk, re.M))
        tasks[tid] = f
    covered = {u for t in tasks.values() for u in re.findall(r"US-\d+", t.get("Requirements", ""))}
    uncovered = [u for u in us if u not in covered]
    order, seen, cyc = [], set(), []

    def visit(t, stack):
        if t in stack:
            cyc.append(t)
            return
        if t in seen:
            return
        for d in re.findall(r"T-\d+", tasks.get(t, {}).get("Dependencies", "")):
            visit(d, stack | {t})
        seen.add(t)
        order.append(t)
    for t in tasks:
        visit(t, set())
    bad_status = [t for t, f in tasks.items() if f.get("Status") not in ("pending", "in_progress", "completed")]
    return {"us": us, "bad_ears": bad_ears, "uncovered": uncovered, "cycle": cyc, "order": order, "bad_status": bad_status}


SAFE_START = set("-?:,[]{}#&*!|>'\"%@`")


def _fm_lines(text):
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    return (m.group(1).split("\n"), m.group(0)) if m else ([], "")


def _fm_value_ok(v):
    if v.startswith('"'):
        try:
            return isinstance(json.loads(v), str)
        except ValueError:
            return False
    if v.startswith("'"):
        return False
    return bool(v) and v[0] not in SAFE_START and ": " not in v and " #" not in v and not v.endswith(":")


def _skill_standards(path):
    lines, block = _fm_lines(path.read_text(encoding="utf-8"))
    issues, vals = [], {}
    for ln in lines:
        m = re.match(r"^([a-z_-]+): (.+)$", ln)
        if not m:
            issues.append("not key: value -> %r" % ln)
            continue
        k, v = m.groups()
        vals[k] = v
        if not _fm_value_ok(v):
            issues.append("non-canonical value for %s" % k)
    raw_desc = vals.get("description", "")
    desc = json.loads(raw_desc) if raw_desc.startswith('"') and _fm_value_ok(raw_desc) else raw_desc
    if len(desc) > 500:
        issues.append("description %d > 500 chars" % len(desc))
    if len(block) > 1024:
        issues.append("frontmatter > 1024")
    name = vals.get("name", "")
    if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", name) or name != path.parent.name:
        issues.append("name not kebab-case or != directory")
    if "when_to_use" not in vals and not desc.startswith("Use when"):
        issues.append("description must start with 'Use when'")
    return issues


def _fm_fix(path):
    text = path.read_text(encoding="utf-8")
    lines, block = _fm_lines(text)
    out = []
    for ln in lines:
        m = re.match(r"^([a-z_-]+):\s*(.+)$", ln)
        k, v = m.groups()
        if _fm_value_ok(v):
            out.append(ln)
            continue
        if v.startswith("'") and v.endswith("'"):
            v = v[1:-1].replace("''", "'")
        elif v.startswith('"'):
            v = v.strip('"')
        out.append("%s: %s" % (k, json.dumps(v, ensure_ascii=False)))
    path.write_text("---\n" + "\n".join(out) + "\n---\n" + text[len(block):], encoding="utf-8")
    return out


IRS = {"Instructions": r"shall follow company'?s procedures", "Training": r"mandatory onboarding", "Integration": r"exclusive",
       "Personal services": r"may not subcontract|personally perform", "Hiring assistants": r"no subcontractors",
       "Continuing relationship": r"renews automatically|indefinite", "Set hours": r"core hours|9:00", "Full-time required": r"exclusive|best efforts",
       "Work on premises": r"on-site|company offices", "Order of work": r"step-by-step", "Reports required": r"daily standup|timesheets",
       "Payment method": r"hourly", "Expenses": r"company will reimburse|equipment provided", "Tools/materials": r"company laptop|company systems",
       "Investment": r"company laptop", "Profit/loss": r"guaranteed minimum", "Multiple clients": r"non-compete|exclusive",
       "Public availability": r"may not market", "Right to fire": r"at any time without cause", "Right to quit": r"no termination fee for contractor"}


def _freelancer(text):
    t = text.lower()
    hits = sorted(k for k, p in IRS.items() if re.search(p, t))
    n = len(hits)
    risk = "LOW" if n <= 5 else "MODERATE" if n <= 10 else "HIGH" if n <= 15 else "CRITICAL"
    net = int(re.search(r"net[- ](\d+)", t).group(1)) if re.search(r"net[- ](\d+)", t) else 90
    lens = {
        "Misclassification Risk": {"LOW": 9, "MODERATE": 5, "HIGH": 3, "CRITICAL": 1}[risk],
        "IP Ownership": 8 if "background ip" in t else 2,
        "Payment Terms": 9 if net <= 15 else 7 if net <= 30 else 3,
        "Payment Amount": 6, "Kill Fee / Cancellation": 8 if "kill fee" in t else 1,
        "Scope Definition": 8 if "statement of work" in t else 4, "Scope Creep Protection": 8 if "change order" in t else 3,
        "Non-Compete Clause": 2 if "non-compete" in t else 9, "Non-Solicitation": 5, "Confidentiality Burden": 7 if "mutual" in t else 4,
        "Termination Rights": 7 if "either party may terminate" in t else 3, "Liability Exposure": 7 if "capped" in t else 2,
        "Dispute Resolution": 4 if "arbitration" in t else 7, "Credit and Portfolio": 8 if "portfolio" in t else 3}
    rights = ["own schedule" in t, "other clients" in t, "subcontract with notice" in t, "own location" in t, "own tools" in t,
              "background ip" in t, "portfolio" in t, net <= 30, "late payment" in t, "kill fee" in t, "change order" in t,
              "out-of-scope" in t, "revision" in t, "either party may terminate" in t, "mutual" in t, "non-compete" not in t,
              "capped" in t, "arbitration" not in t, "in writing" in t, "credit" in t]
    pay = (lens["Payment Terms"] + lens["Kill Fee / Cancellation"] + (8 if "late payment" in t else 2)) / 30 * 10
    score = round(sum(lens.values()) / 14 / 10 * 50 + {"LOW": 20, "MODERATE": 12, "HIGH": 6, "CRITICAL": 0}[risk]
                  + sum(rights) / 20 * 20 + pay)
    grade = "A" if score >= 90 else "B" if score >= 80 else "C" if score >= 70 else "D" if score >= 60 else "F"
    return {"irs_hits": hits, "risk": risk, "lens": lens, "rights": sum(rights), "pay": round(pay, 2), "score": score, "grade": grade,
            "playbook": sorted(k for k, v in lens.items() if v <= 5)}


def _flatten(d, pre=""):
    out = {}
    for k, v in d.items():
        if isinstance(v, dict):
            out.update(_flatten(v, pre + k + "."))
        else:
            out[pre + k] = v
    return out


def _unflatten(f):
    out = {}
    for k, v in f.items():
        cur = out
        parts = k.split(".")
        for p in parts[:-1]:
            cur = cur.setdefault(p, {})
        cur[parts[-1]] = v
    return out
