"""Helpers of runners/fam_skills_part4.py used by data cards, copied verbatim (the extractor binds a card to them only when
their AST hash with every dependency equals the original's)."""
from __future__ import annotations

from pathlib import Path
import hashlib
import json
import re
import textwrap


def jw(path, obj):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
    return Path(path)


def tw(path, text):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(textwrap.dedent(text).lstrip("\n"), encoding="utf-8")
    return p


def _bbox_to_px(box, w, h):
    """Ideogram V4 describe boxes: [y_min, x_min, y_max, x_max] normalised to 0..1000 -> pixel (x0, y0, x1, y1)."""
    y0, x0, y1, x1 = box
    return (round(x0 * w / 1000), round(y0 * h / 1000), round(x1 * w / 1000), round(y1 * h / 1000))


def _lifecycle(db, rec, governed, naive=False):
    """Trace one synthetic record through every store, then run deletion. naive=True is the ungoverned pipeline."""
    c = db.cursor()
    tenant, prompt = rec["tenant"], rec["prompt"]
    gen_id = hashlib.sha256(("gen:" + rec["id"]).encode()).hexdigest()[:16]
    c.execute("insert into uploads values (?,?,?)", (rec["id"], tenant, "source.png"))
    c.execute("insert into generations values (?,?,?,?,?)",
              (gen_id, tenant, rec["id"], "passed", rec["vendor_url"] if naive else None))
    c.execute("insert into outputs values (?,?,?)",
              (tenant + "/" + hashlib.sha256(rec["png"]).hexdigest()[:24], tenant, rec["id"]))
    c.execute("insert into logs values (?,?)", (rec["id"], ("prompt=" + prompt) if naive else ("gen=" + gen_id + " safety=passed")))
    c.execute("insert into queue values (?,?)", (rec["id"], "done"))
    c.execute("insert into cache values (?,?)", (rec["id"], "thumb"))
    if rec.get("legal_hold"):
        c.execute("insert into legal_holds values (?,?)", (gen_id, "case-17"))
    db.commit()
    # deletion request for the source record
    stores = ["uploads"] if naive else governed
    for t in stores:
        col = "record" if t not in ("uploads",) else "id"
        if t == "generations":
            held = c.execute("select 1 from legal_holds where gen_id=?", (gen_id,)).fetchone()
            if held:
                continue
            c.execute("delete from generations where record=?", (rec["id"],))
            continue
        c.execute("delete from %s where %s=?" % (t, col), (rec["id"],))
    db.commit()
    return gen_id


def _env_audit(envs):
    f = []
    seen = {}
    for name, e in envs.items():
        for ref in [e["client_secret_ref"], e["webhook_secret_ref"]]:
            if ref in seen and seen[ref] != name:
                f.append(("shared-secret", name, ref))
            seen.setdefault(ref, name)
        for cb in e["callbacks"]:
            if "*" in cb:
                f.append(("wildcard-callback", name, cb))
            if not cb.startswith("https://") and not cb.startswith("http://localhost"):
                f.append(("non-https-callback", name, cb))
        if not e["webhook_url"].startswith("https://"):
            f.append(("non-https-webhook", name, e["webhook_url"]))
        if name != "production":
            for j in e.get("ci_jobs", []):
                if any("prod" in s.lower() for s in j["secrets"]):
                    f.append(("non-prod-job-resolves-prod-secret", name, j["name"]))
        if e.get("team_access") == "all-teams" and name == "production":
            f.append(("broad-team-access", name, "all-teams"))
    return f


NOTION_RULES = [
    ("database-id-to-data-source-query", re.compile(r"dataSources\.query\(\s*\{\s*data_source_id:\s*\w*database\w*", re.I)),
    ("single-page-query", re.compile(r"(?s)(dataSources\.query|search)\((?:(?!has_more|next_cursor).)*?\)\s*;(?:(?!has_more|next_cursor).)*$")),
    ("write-retry-without-idempotency", re.compile(r"retry\(\s*\(\)\s*=>\s*notion\.pages\.create")),
    ("webhook-trusts-order", re.compile(r"webhook[\s\S]{0,200}apply\(event\.data\)(?![\s\S]{0,120}retrieve)")),
    ("stale-api-version", re.compile(r"notionVersion:\s*['\"]2022-")),
]


def _notion_audit(src):
    return sorted(name for name, rx in NOTION_RULES if rx.search(src))


PHI = [re.compile(r"\bMRN[:# ]*\d{6,}\b", re.I), re.compile(r"\b\d{3}-\d{3}-\d{4}\b"), re.compile(r"\bDOB[: ]+\d{4}-\d{2}-\d{2}\b", re.I)]


def _kappa(a, b):
    labels = sorted(set(a) | set(b))
    n = len(a)
    po = sum(x == y for x, y in zip(a, b)) / n
    pe = sum((a.count(l) / n) * (b.count(l) / n) for l in labels)
    return (po - pe) / (1 - pe)


READONLY_LABEL = re.compile(r"readonly|read-only|bi-")


def _rbac_audit(org):
    f = []
    for k in org["keys"]:
        if "*" in k["scopes"]:
            f.append(("wildcard-scope", k["label"]))
        if READONLY_LABEL.search(k["label"]) and any(not s.endswith(":read") for s in k["scopes"]):
            f.append(("write-scope-on-readonly-key", k["label"]))
        if k["label"] == "flag-service" and any(not s.startswith("feature_flag:") for s in k["scopes"]):
            f.append(("flag-key-overbroad", k["label"]))
    for m in org["members"]:
        if m["email"].split("@")[1] not in org["verified_domains"]:
            f.append(("member-outside-verified-domain", m["email"]))
        prod = m["projects"].get("production")
        if prod is not None and m["team"] == "product" and prod > 1:
            f.append(("prod-admin-for-product", m["email"]))
        if m["org_level"] >= 8 and m["team"] not in ("platform",):
            f.append(("org-admin-outside-platform", m["email"]))
    if not org["enforce_sso"]:
        f.append(("sso-not-enforced", org["name"]))
    return sorted(f)


def _effective(member, project):
    return max(member["org_level"] if member["org_level"] >= 8 else 0, member["projects"].get(project, 0))


def _shape(obj, prefix=""):
    out = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            out.update(_shape(v, prefix + k + "."))
    elif isinstance(obj, list):
        out.update(_shape(obj[0], prefix + "[]."))
    else:
        out[prefix.rstrip(".")] = type(obj).__name__
    return out


def _state_hash(rows, fields):
    canon = sorted(json.dumps({f: r.get(f) for f in fields}, sort_keys=True) for r in rows)
    return hashlib.sha256("\n".join(canon).encode()).hexdigest()


def _gql_parse(q):
    """Tiny GraphQL selection parser: returns [(name, args, children)] for the top-level selection set."""
    toks = re.findall(r"[A-Za-z_][A-Za-z0-9_]*|\d+|[{}():,]|\"[^\"]*\"", q)
    pos = [0]

    def sel():
        out = []
        assert toks[pos[0]] == "{"
        pos[0] += 1
        while toks[pos[0]] != "}":
            name = toks[pos[0]]
            pos[0] += 1
            args = {}
            if toks[pos[0]] == "(":
                pos[0] += 1
                while toks[pos[0]] != ")":
                    k = toks[pos[0]]
                    v = toks[pos[0] + 2]
                    args[k] = v
                    pos[0] += 3
                    if toks[pos[0]] == ",":
                        pos[0] += 1
                pos[0] += 1
            kids = sel() if toks[pos[0]] == "{" else None
            out.append((name, args, kids))
        pos[0] += 1
        return out
    while toks[pos[0]] != "{":
        pos[0] += 1
    return sel()


def _gql_cost(fields):
    """Shopify requested-cost rules: scalar 0, object 1, connection 2 + first x (cost of one node)."""
    total = 0
    for name, args, kids in fields:
        if kids is None:
            continue
        if "first" in args:
            node = [k for k in kids if k[0] in ("edges", "nodes")]
            inner = 0
            for n in node:
                sub = n[2]
                if n[0] == "edges":
                    sub = [s for s in sub if s[0] == "node"][0][2]
                inner += 1 + _gql_cost(sub)
            total += 2 + int(args["first"]) * inner
        elif name in ("edges", "nodes", "node"):
            total += _gql_cost(kids)
        else:
            total += 1 + _gql_cost(kids)
    return total


def _drift_audit(root, today):
    import datetime as dt
    root = Path(root)
    f = []
    q = (root / "TASK_QUEUE.md").read_text()
    active = re.findall(r"^- \[~\] (.+?)(?: \(last_active: (\d{4}-\d{2}-\d{2})\))?$", q, re.M)
    if len(active) > 1:
        f.append(("warning", "multiple-active-tasks", [a[0] for a in active]))
    for name, last in active:
        if last and (today - dt.date.fromisoformat(last)).days > 3:
            f.append(("info", "task-stale-over-3-days", name))
    dec = (root / "DECISIONS.md").read_text()
    for d, when in re.findall(r"^- (.+?) \(decided_at: (\d{4}-\d{2}-\d{2})\)$", dec, re.M):
        if (today - dt.date.fromisoformat(when)).days > 7 and active:
            f.append(("info", "decision-may-be-stale", d))
    conv = re.search(r"naming: (\w+)", dec)
    code = "\n".join(p.read_text() for p in sorted((root / "src").glob("*.py")))
    if conv and conv.group(1) == "snake_case":
        bad = sorted(set(re.findall(r"^def ([a-z]+[A-Z]\w*)", code, re.M)))
        if bad:
            f.append(("warning", "naming-inconsistent", bad))
    if re.search(r"(api_key|password|secret)\s*=\s*['\"][^'\"]{6,}['\"]", code, re.I):
        f.append(("critical", "hardcoded-secret", "src"))
    lines = [l.strip() for l in code.splitlines() if l.strip()]
    blocks = {}
    for i in range(len(lines) - 3):
        blocks.setdefault(tuple(lines[i:i + 4]), []).append(i)
    if any(len(v) > 1 for v in blocks.values()):
        f.append(("warning", "duplicate-code-over-3-lines", "src"))
    scope = re.findall(r"^- (.+)$", (root / "PROJECT.md").read_text().split("## Out of scope")[1], re.M)
    for s in scope:
        if s.lower() in q.lower():
            f.append(("critical", "scope-creep", s))
    sev = [x[0] for x in f]
    level = 0 if not f else (3 if sev.count("critical") >= 2 else 2 if "critical" in sev else 1)
    advice = {0: "继续", 1: "继续", 2: "暂停", 3: "决策闸门"}[level]
    return sorted(f), level, advice


def sha_tree(root):
    h = hashlib.sha256()
    for p in sorted(Path(root).rglob("*")):
        if p.is_file():
            h.update(str(p.relative_to(root)).encode() + p.read_bytes())
    return h.hexdigest()


def _ai_review_cause(log, duration_s=60, pr_comments=0):
    """The skill's decision table: read subtype and is_error together, then the finding count."""
    if duration_s <= 6:
        return "skipped-not-a-control"
    sub = re.search(r'"subtype":\s*"(\w+)"', log)
    err = re.search(r'"is_error":\s*(true|false)', log)
    sub, err = (sub.group(1) if sub else None), (err.group(1) == "true" if err else None)
    found = re.search(r"Found (\d+)", log)
    if sub == "error_max_turns":
        return "1-budget-exhaustion"
    if sub == "success" and err is False and found and pr_comments == 0:
        return "3-unpublished-finding"
    if sub == "success" and err is False and not found and "exceeding the configured maximum" in log:
        return "2-turn-ceiling-overrun"
    if sub == "success" and err is True and not found:
        return "4-errored-despite-completing"
    return "unclassified"


def _yaml():
    import yaml
    return yaml


def _ha_validate(root):
    yaml = _yaml()

    class L(yaml.SafeLoader):
        pass
    used, dups, errors = set(), [], []

    def secret(loader, node):
        used.add(node.value)
        return "<secret:%s>" % node.value

    def include(loader, node):
        return "<include:%s>" % node.value

    def mapping(loader, node, deep=False):
        keys = [k.value for k, _ in node.value if isinstance(k, yaml.ScalarNode)]
        for k in sorted({k for k in keys if keys.count(k) > 1}):
            dups.append((Path(node.start_mark.name).name, node.start_mark.line + 1, k))
        return yaml.SafeLoader.construct_mapping(loader, node, deep)
    L.add_constructor("!secret", secret)
    for t in ("!include", "!include_dir_merge_named", "!include_dir_list", "!input", "!env_var"):
        L.add_constructor(t, include)
    L.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, mapping)
    for p in sorted(Path(root).glob("*.yaml")):
        if p.name == "secrets.yaml":
            continue
        try:
            with open(p) as fh:
                yaml.load(fh, Loader=L)
        except yaml.YAMLError as e:
            m = getattr(e, "problem_mark", None)
            errors.append((p.name, (m.line + 1) if m else None, str(getattr(e, "problem", e))))
    sec = Path(root) / "secrets.yaml"
    defined = set(yaml.safe_load(sec.read_text()) or {}) if sec.exists() else set()
    return {"syntax_errors": errors, "duplicate_keys": dups, "undefined_secrets": sorted(used - defined)}


def _reqs(md, header="## Requirements"):
    """Return ordered {name: block} under a header; block includes its scenarios."""
    m = re.search(r"(?ms)^%s\s*\n(.*?)(?=^## |\Z)" % re.escape(header), md)
    if not m:
        return None
    out = {}
    for part in re.split(r"(?m)^(?=### Requirement: )", m.group(1)):
        h = re.match(r"### Requirement: (.+)", part)
        if h:
            out[h.group(1).strip()] = part.strip()
    return out


def _render_main(purpose, reqs):
    return "# Spec\n\n## Purpose\n%s\n\n## Requirements\n\n%s\n" % (purpose, "\n\n".join(reqs.values()))


def _merge(main_md, delta_md):
    """Apply ADDED/MODIFIED/REMOVED/RENAMED; validate before writing; idempotent no-ops; near matches fail."""
    errors, ops = [], {"ADDED": 0, "MODIFIED": 0, "REMOVED": 0, "RENAMED": 0, "noop": 0}
    if main_md is None:
        purpose = (re.search(r"(?ms)^## Purpose\s*\n(.*?)(?=^## |\Z)", delta_md) or [None, ""])[1].strip() or "Default purpose."
        reqs = {}
    else:
        if re.search(r"(?m)^## (ADDED|MODIFIED|REMOVED|RENAMED) Requirements", main_md):
            return None, ops, ["baseline contains delta headers: rejected"]
        purpose = re.search(r"(?ms)^## Purpose\s*\n(.*?)(?=^## |\Z)", main_md).group(1).strip()
        reqs = _reqs(main_md) or {}

    def near(name):
        return [k for k in reqs if k != name and re.sub(r"\s+", " ", k).lower() == re.sub(r"\s+", " ", name).lower()]
    for name, block in (_reqs(delta_md, "## ADDED Requirements") or {}).items():
        if name in reqs:
            if reqs[name] == block:
                ops["noop"] += 1
            else:
                errors.append("ADDED %s already exists with different content" % name)
            continue
        reqs[name] = block
        ops["ADDED"] += 1
    for name, block in (_reqs(delta_md, "## MODIFIED Requirements") or {}).items():
        if name not in reqs:
            errors.append(("MODIFIED near-match %r" % near(name)) if near(name) else "MODIFIED missing %s" % name)
            continue
        if reqs[name] == block:
            ops["noop"] += 1
        else:
            reqs[name] = block
            ops["MODIFIED"] += 1
    rem = re.search(r"(?ms)^## REMOVED Requirements\s*\n(.*?)(?=^## |\Z)", delta_md)
    for name in (re.findall(r"### Requirement: (.+)", rem.group(1)) if rem else []):
        name = name.strip()
        if name in reqs:
            del reqs[name]
            ops["REMOVED"] += 1
        elif near(name):
            errors.append("REMOVED near-match %r" % near(name))
        else:
            ops["noop"] += 1
    ren = re.search(r"(?ms)^## RENAMED Requirements\s*\n(.*?)(?=^## |\Z)", delta_md)
    for old, new in (re.findall(r"- FROM: `?(.+?)`?\s*\n\s*- TO: `?(.+?)`?\s*$", ren.group(1), re.M) if ren else []):
        if new in reqs and old not in reqs:
            ops["noop"] += 1
            continue
        if new in reqs:
            errors.append("RENAMED target %s collides" % new)
            continue
        if old not in reqs:
            errors.append("RENAMED missing %s" % old)
            continue
        reqs = {(new if k == old else k): (v.replace("### Requirement: " + old, "### Requirement: " + new, 1) if k == old else v)
                for k, v in reqs.items()}
        ops["RENAMED"] += 1
    if errors:
        return None, ops, errors
    out = _render_main(purpose, reqs)
    if re.search(r"(?m)^## (ADDED|MODIFIED|REMOVED|RENAMED)", out) or "## Requirements" not in out:
        return None, ops, ["candidate failed validation"]
    return out, ops, []


def _req(name, shall, when, then):
    return "### Requirement: %s\nThe system SHALL %s.\n\n#### Scenario: %s\n- **WHEN** %s\n- **THEN** %s" % (name, shall, name.lower(), when, then)


VAGUE = re.compile(r"\b(TBD|TODO|better|robust|efficient)\b", re.I)


def _validate_pack(d):
    d = Path(d)
    f = []
    prop = (d / "proposal.md").read_text()
    why = re.search(r"(?ms)^## Why\s*\n(.*?)(?=^## |\Z)", prop)
    if not why or len(why.group(1).strip()) <= 50:
        f.append("proposal: Why <= 50 chars")
    for h in ("## What Changes", "## Scope", "## Impact"):
        if h not in prop:
            f.append("proposal: missing " + h)
    if not re.search(r"(?i)\bIn:", prop) or not re.search(r"(?i)\bOut:", prop):
        f.append("proposal: scope lacks In/Out")
    req_names = []
    for sp in sorted((d / "specs").rglob("spec.md")):
        t = sp.read_text()
        if not re.search(r"(?m)^## (ADDED|MODIFIED|REMOVED) Requirements", t):
            f.append("specs: no delta header")
        for name, block in (_reqs(t, "## ADDED Requirements") or {}).items():
            req_names.append(name)
            if not re.search(r"\b(SHALL|MUST)\b", block):
                f.append("specs: %s lacks SHALL/MUST" % name)
            if "#### Scenario:" not in block or "WHEN" not in block or "THEN" not in block:
                f.append("specs: %s lacks WHEN/THEN scenario" % name)
    des = (d / "design.md").read_text()
    if "## Decisions" not in des or not all(k in des for k in ("Choice", "Rationale", "Alternatives", "Consequences")):
        f.append("design: decision lacks Choice/Rationale/Alternatives/Consequences")
    if "## Goals" not in des or "Non-goals" not in des:
        f.append("design: goals/non-goals")
    tasks = (d / "tasks.md").read_text()
    boxes = re.findall(r"(?m)^- \[ \] (\d+)\. (.+)$", tasks)
    if not boxes:
        f.append("tasks: no checkbox tasks")
    for n, t in boxes:
        if "`" not in t or "->" not in t or "evidence:" not in t:
            f.append("tasks: %s lacks path/outcome/evidence" % n)
    for r in req_names:
        if r not in tasks:
            f.append("tasks: requirement %s unmapped" % r)
    for name in ("proposal.md", "design.md", "tasks.md"):
        if VAGUE.search((d / name).read_text()):
            f.append("%s: placeholder or empty adjective" % name)
    return f


def _write_pack(d, cfg):
    d = Path(d)
    if not cfg.get("dp_0_confirmed"):
        return None
    reqs = cfg["requirements"]
    tw(d / "proposal.md", "# Proposal: %s\n\n## Why\n%s\n\n## What Changes\n%s\n\n## Scope\nIn: %s\nOut: %s\n\n## Impact\n%s\n\n"
       "## Proof of completion\n%s\n" % (cfg["title"], cfg["problem"], cfg["change"], cfg["in"], cfg["out"], cfg["impact"], cfg["proof"]))
    tw(d / "specs" / cfg["capability"] / "spec.md", "## ADDED Requirements\n\n" + "\n\n".join(
        _req(r["name"], r["shall"], r["when"], r["then"]) for r in reqs) + "\n")
    tw(d / "design.md", "# Design\n\n## Facts and constraints\n%s\n\n## Goals\n%s\n\nNon-goals: %s\n\n## Decisions\n"
       "- Choice: %s\n- Rationale: %s\n- Alternatives: %s\n- Consequences: %s\n\n## Risks and verification\n%s\n" % (
           cfg["facts"], cfg["goal"], cfg["out"], *cfg["decision"], cfg["risk"]))
    tw(d / "tasks.md", "# Tasks\n\n## Delivery / proof map\n%s\n\n%s\n" % (
        "\n".join("- %s -> task %d" % (r["name"], i + 1) for i, r in enumerate(reqs)),
        "\n".join("- [ ] %d. %s: `%s` -> %s (evidence: `%s`)%s" % (i + 1, r["name"], r["path"], r["then"], r["evidence"],
                                                                     "" if i == 0 else " depends on %d" % i) for i, r in enumerate(reqs))))
    return d
