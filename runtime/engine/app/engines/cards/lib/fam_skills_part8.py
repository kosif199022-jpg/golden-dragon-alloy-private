"""Helpers of runners/fam_skills_part8.py used by data cards, copied verbatim (the extractor binds a card to them only when
their AST hash with every dependency equals the original's)."""
from __future__ import annotations

from pathlib import Path
import json
import os
import re
import shutil
import subprocess
import sys
import time


def _w(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _j(path, obj):
    return _w(path, json.dumps(obj, indent=2, ensure_ascii=False, sort_keys=True))


def _sh(cmd, cwd=None, env=None, timeout=30, input=None):
    return subprocess.run([str(c) for c in cmd], cwd=cwd, env=env, capture_output=True, text=True,
                          timeout=timeout, input=input, stdin=None if input is not None else subprocess.DEVNULL)


def _git(repo, *args, env=None):
    e = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@e", GIT_COMMITTER_NAME="t",
             GIT_COMMITTER_EMAIL="t@e", GIT_CONFIG_NOSYSTEM="1", HOME=str(repo), **(env or {}))
    r = _sh(["git", "-c", "init.defaultBranch=main", "-c", "commit.gpgsign=false", *args], cwd=repo, env=e)
    return r


def _repo(path):
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    _git(path, "init", "-q")
    return path


def _commit(repo, msg, date=None):
    _git(repo, "add", "-A")
    env = {"GIT_AUTHOR_DATE": date, "GIT_COMMITTER_DATE": date} if date else None
    return _git(repo, "commit", "-q", "-m", msg, env=env)


def _frontmatter(text):
    import yaml
    if not text.startswith("---"):
        return None, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None, text
    try:
        meta = yaml.safe_load(parts[1])
    except Exception:
        return None, parts[2]
    return (meta if isinstance(meta, dict) else None), parts[2]


def _claude():
    return shutil.which("claude")


def _validate(path, strict=False):
    r = _sh([_claude(), "plugin", "validate", str(path)] + (["--strict"] if strict else []), timeout=40)
    return r.returncode, r.stdout + r.stderr


ASTRO_RULES = [
    ("node-version", "package.json", lambda t: bool(re.search(r'"node"\s*:\s*"[^"]*(1[0-9]|20)\b', t)), "Node 22.12+ required (v6)"),
    ("zod4-string-validators", None, lambda t: bool(re.search(r"z\.string\(\)\.(email|url|uuid)\(", t)), "use z.email()/z.url() (Zod 4)"),
    ("zod4-message-key", None, lambda t: bool(re.search(r"\bmessage\s*:", t)) and "z." in t, "error: replaces message: (Zod 4)"),
    ("astro-db-removed", None, lambda t: "@astrojs/db" in t, "@astrojs/db removed in v7"),
    ("transition-constants", None, lambda t: bool(re.search(r"\bTRANSITION_[A-Z_]+|createAnimationScope", t)), "removed in v7; use event names"),
    ("reserved-fetch-ts", "src/fetch.ts", lambda t: True, "src/fetch.ts is reserved in v7"),
    ("ssr-needs-adapter", "astro.config.mjs", lambda t: "output: 'server'" in t and "adapter" not in t, "on-demand rendering needs an adapter"),
]


def _astro_lint(root):
    found = []
    for f in sorted(p for p in root.rglob("*") if p.is_file()):
        rel = f.relative_to(root).as_posix()
        t = f.read_text(encoding="utf-8")
        for rid, only, fn, why in ASTRO_RULES:
            if (only is None or only == rel) and fn(t):
                found.append({"rule": rid, "file": rel, "why": why})
    return found


def _bump(a, b):
    a, b = [int(x) for x in a.split(".")], [int(x) for x in b.split(".")]
    return "major" if b[0] != a[0] else "minor" if b[1] != a[1] else "patch"


def _mk_market(root, broken):
    _j(root / ".claude-plugin/marketplace.json", {
        "name": "acme", "owner": {"name": "acme"}, "description": "Acme plugins for testing the verifier.",
        "plugins": [{"name": "alpha", "source": "./plugins/alpha", "description": "Alpha plugin", "version": "1.2.0" if broken else "1.3.0"}]
        + ([{"name": "ghost", "source": "./plugins/ghost", "description": "missing"}] if broken else [])})
    pj = {"name": "alpha", "version": "1.3.0", "description": "Alpha plugin does alpha things.", "author": {"name": "acme"},
          "license": "MIT", "homepage": "https://example.com/alpha"}
    if broken:
        pj["hooks"] = "./hooks/hooks.json"
    _j(root / "plugins/alpha/.claude-plugin/plugin.json", pj)
    _j(root / "plugins/alpha/hooks/hooks.json", {"hooks": {"SessionStart": [{"hooks": [{"type": "command", "command": "echo ok"}]}]}})
    _w(root / "plugins/alpha/README.md", "# alpha\n\n" + "Alpha adds a session start hook that prints a greeting so users can see the plugin "
       "loaded correctly; install it from the acme marketplace and start a new session to see it work as intended here.\n")
    _w(root / "README.md", "# acme\n\nInstall: `/plugin marketplace add acme/acme`\n")
    _w(root / "LICENSE", "MIT\n")


def _verify_market(root):
    findings = []
    cat = json.loads((root / ".claude-plugin/marketplace.json").read_text())
    rc, txt = _validate(root, strict=True)
    if rc:
        findings.append({"axis": "A", "what": "claude plugin validate --strict failed on marketplace"})
    for e in cat["plugins"]:
        src = (root / e["source"]).resolve()
        mf = src / ".claude-plugin/plugin.json"
        if not mf.exists():
            findings.append({"axis": "A", "what": "entry %s: source %s has no plugin manifest" % (e["name"], e["source"])})
            continue
        pj = json.loads(mf.read_text())
        if pj.get("name") != e["name"]:
            findings.append({"axis": "A", "what": "entry name %s != plugin.json name %s" % (e["name"], pj.get("name"))})
        if e.get("version") and e["version"] != pj.get("version"):
            findings.append({"axis": "A", "what": "%s: catalog version %s != plugin.json %s" % (e["name"], e["version"], pj.get("version"))})
        if pj.get("hooks") in ("./hooks/hooks.json", "hooks/hooks.json") and (src / "hooks/hooks.json").exists():
            findings.append({"axis": "B", "what": "%s: hooks pointer duplicates the auto-loaded hooks/hooks.json (plugin fails to load)" % e["name"]})
        prc, _ = _validate(src, strict=True)
        if prc:
            findings.append({"axis": "B", "what": "%s: claude plugin validate --strict failed" % e["name"]})
    if not (root / "LICENSE").exists():
        findings.append({"axis": "C", "what": "no LICENSE"})
    return findings


NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


TIMEBOUND = re.compile(r"\b(currently|as of|the latest|new in|recently)\b", re.I)


def _verify_skill(d):
    f = d / "SKILL.md"
    text = f.read_text(encoding="utf-8")
    meta, body = _frontmatter(text)
    find = []
    if meta is None:
        return [{"axis": "A", "rule": "frontmatter-parse"}]
    name, desc = str(meta.get("name") or ""), meta.get("description")
    if not name or not NAME_RE.match(name) or len(name) > 64:
        find.append({"axis": "A", "rule": "name-format", "value": name})
    if name != d.name:
        find.append({"axis": "A", "rule": "name-matches-dir", "value": [name, d.name]})
    if not desc or not str(desc).strip():
        find.append({"axis": "A", "rule": "description-missing"})
    elif len(str(desc)) > 1024 or re.search(r"[<>]", str(desc)):
        find.append({"axis": "A", "rule": "description-limits"})
    if len(body.splitlines()) > 500:
        find.append({"axis": "A", "rule": "body-size"})
    for link in re.findall(r"\]\(([^)#\s]+)\)", body):
        if not re.match(r"[a-z]+://", link) and not (d / link).exists():
            find.append({"axis": "A", "rule": "dangling-reference", "value": link})
    for m in TIMEBOUND.finditer(body):
        find.append({"axis": "C", "rule": "time-bound-phrasing", "value": m.group(0)})
    return find


def _default_branch(repo, interleave=False):
    r = _git(repo, "symbolic-ref", "refs/remotes/origin/HEAD")
    if r.returncode == 0 and r.stdout.strip():
        return r.stdout.strip().replace("refs/remotes/origin/", "")
    names = ["master", "main", "trunk"]
    passes = ([[("refs/remotes/origin/" + n, n), ("refs/heads/" + n, n)] for n in names] if interleave else
              [[("refs/remotes/origin/" + n, n) for n in names], [("refs/heads/" + n, n) for n in names]])
    for group in passes:
        for ref, n in group:
            if _git(repo, "rev-parse", "--verify", "-q", ref).returncode == 0:
                return n
    return None


USER_FILES = re.compile(r"^(hooks|commands|skills|agents|\.claude-plugin)/")


def _flat(d, p=""):
    out = {}
    if isinstance(d, dict):
        for k, v in d.items():
            out.update(_flat(v, "%s.%s" % (p, k) if p else str(k)))
    else:
        out[p] = d
    return out


def _cli_gates(cli, wd):
    run = lambda *a, env=None: _sh([sys.executable, "-I", cli, *a], env=dict(os.environ, NO_COLOR="1", **(env or {})), timeout=5)
    g = {}
    lst = run("task", "list", "--json")
    try:
        env_ok = set(json.loads(lst.stdout)) >= {"status", "data", "error", "meta"}
        g["G1"] = True
    except ValueError:
        env_ok = False
        g["G1"] = False
    g["G2"] = env_ok
    nf = run("task", "delete", "99", "--yes", "--json")
    usage = run("bogus", "cmd", "--json")
    g["G3"] = lst.returncode == 0 and nf.returncode == 3 and usage.returncode == 2
    g["G4"] = all(run(*c.split(), "--help").returncode == 0 and "Example" in run(*c.split(), "--help").stdout
                  for c in ("task list", "task create", "task delete"))
    try:
        p = run("task", "delete", "1", "--json")
        g["G5"] = p.returncode != 0 and "--yes" in p.stdout
    except subprocess.TimeoutExpired:
        g["G5"] = False
    try:
        e = json.loads(nf.stdout)["error"]
        g["G6"] = all(e.get(k) for k in ("what", "why", "fix"))
    except (ValueError, KeyError, TypeError):
        g["G6"] = False
    state = Path(cli).parent / "state.json"
    before = state.read_text() if state.exists() else None
    dry = run("task", "create", "--title", "x", "--dry-run", "--json")
    after = state.read_text() if state.exists() else None
    try:
        g["G7"] = json.loads(dry.stdout)["data"]["planned"][0]["op"] == "create" and before == after
    except (ValueError, KeyError, TypeError):
        g["G7"] = False
    g["G8"] = not any("\x1b[" in r.stdout for r in (lst, nf, dry))
    return g


def _human_gates(cli, wd):
    env = dict(os.environ, XDG_CONFIG_HOME=str(wd / "xdg"))
    env.pop("NO_COLOR", None)
    run = lambda *a, e=None: _sh([sys.executable, "-I", cli, *a], env=dict(env, **(e or {})), timeout=6)
    g = {}
    h = run("--help")
    g["G1"] = h.returncode == 0 and all(s in h.stdout for s in ("USAGE", "EXAMPLES", "FLAGS", "default"))
    err = run("deploy")
    g["G2"] = err.returncode != 0 and "Fix:" in (err.stderr + err.stdout)
    try:
        pr = run("deploy", "production")
        g["G3"] = pr.returncode != 0 and "--yes" in pr.stderr and run("deploy", "production", "--yes").returncode == 0
    except subprocess.TimeoutExpired:
        g["G3"] = False
    piped = run("deploy", "staging")
    tty = subprocess.run(["script", "-qec", "%s -I %s deploy staging" % (sys.executable, cli), "/dev/null"], capture_output=True, text=True,
                         timeout=8, env=env, stdin=subprocess.DEVNULL)
    nocolor = subprocess.run(["script", "-qec", "%s -I %s deploy staging" % (sys.executable, cli), "/dev/null"], capture_output=True, text=True,
                             timeout=8, env=dict(env, NO_COLOR="1"), stdin=subprocess.DEVNULL)
    g["G4"] = "\x1b[" not in piped.stdout and "\x1b[3" in tty.stdout and "\x1b[3" not in nocolor.stdout
    g["G5"] = "deploying" in piped.stderr and "deploying" not in piped.stdout
    t0 = time.time()
    v = run("--version")
    g["G6"] = time.time() - t0 < 0.5
    g["G7"] = run("config-path").stdout.strip() == str(wd / "xdg/mycli/config.toml")
    g["G8"] = v.returncode == 0 and re.fullmatch(r"mycli \d+\.\d+\.\d+", v.stdout.strip()) is not None
    return g


def _lum(hexc):
    r, g, b = (int(hexc[i:i + 2], 16) / 255 for i in (1, 3, 5))
    f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def _contrast(a, b):
    la, lb = sorted((_lum(a), _lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def _site_audit(html):
    css = dict(re.findall(r"--([\w-]+):\s*([^;]+);", html))
    fs = float(css["body-size"].replace("px", ""))
    measure = float(css["measure"].replace("ch", ""))
    lh = float(css["line-height"])
    ratio = _contrast(css["text"].strip(), css["bg"].strip())
    ctas = len(re.findall(r'class="[^"]*\bcta-primary\b', html))
    blocking = len(re.findall(r"<script(?![^>]*\b(defer|async)\b)[^>]*src=", html))
    fields = len(re.findall(r"<input\b", html))
    h1 = re.search(r"<h1>(.*?)</h1>", html, re.S).group(1)
    f = []
    if fs < 16: f.append(("web-typography", "body text %.0fpx < 16px" % fs, 6, 9, 9))
    if not 45 <= measure <= 75: f.append(("web-typography", "measure %.0fch outside 45-75" % measure, 5, 8, 9))
    if not 1.4 <= lh <= 1.6: f.append(("web-typography", "line-height %.2f outside 1.4-1.6" % lh, 4, 8, 9))
    if ratio < 4.5: f.append(("refactoring-ui", "text contrast %.2f < 4.5" % ratio, 7, 9, 9))
    if ctas != 1: f.append(("cro-methodology", "%d primary CTAs (want exactly 1)" % ctas, 8, 7, 7))
    if blocking: f.append(("high-perf-browser", "%d render-blocking scripts" % blocking, 6, 8, 8))
    if fields > 3: f.append(("design-everyday-things", "%d form fields before value" % fields, 7, 6, 7))
    if len(h1.split()) > 12 or "solutions" in h1.lower(): f.append(("storybrand-messaging", "headline is vague: %r" % h1[:40], 9, 6, 8))
    return [{"phase": p, "finding": w, "impact": i, "confidence": c, "ease": e, "ice": i * c * e} for p, w, i, c, e in f], ratio


def _slerp(q1, q2, t, shortest=True):
    import math
    d = sum(a * b for a, b in zip(q1, q2))
    if shortest and d < 0:
        q2, d = tuple(-x for x in q2), -d
    d = max(-1.0, min(1.0, d))
    th = math.acos(d)
    if th < 1e-6:
        return q1
    s1, s2 = math.sin((1 - t) * th) / math.sin(th), math.sin(t * th) / math.sin(th)
    return tuple(s1 * a + s2 * b for a, b in zip(q1, q2))


def _lint_skill(d):
    text = (d / "SKILL.md").read_text()
    meta, body = _frontmatter(text)
    issues = []
    desc = str((meta or {}).get("description") or "")
    if not re.search(r"\bUse (when|for)\b", desc):
        issues.append("description names no trigger situations")
    if len(body.splitlines()) > 80:
        issues.append("main file too long for progressive disclosure (%d lines)" % len(body.splitlines()))
    if not re.search(r"^\s*1\. ", body, re.M):
        issues.append("no imperative procedure")
    for para in re.split(r"\n\s*\n", body):
        if not para.lstrip().startswith(("#", "-", "1", "|", "`")) and len(re.findall(r"[.!?](\s|$)", para)) > 3:
            issues.append("essay paragraph")
            break
    for link in re.findall(r"\]\(((?:references|scripts)/[^)]+)\)", body):
        if not (d / link).exists():
            issues.append("dangling pointer " + link)
    for s in (d / "scripts").glob("*.py") if (d / "scripts").exists() else []:
        if _sh([sys.executable, "-I", s, "--self-test"]).returncode:
            issues.append("script fails self-test: " + s.name)
    return issues
