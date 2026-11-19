"""Helpers of runners/fam_skills_part9.py used by data cards, copied verbatim (the extractor binds a card to them only when
their AST hash with every dependency equals the original's)."""
from __future__ import annotations

from pathlib import Path
import ast
import json
import re
import subprocess


def write_tree(d, files: dict):
    for rel, text in files.items():
        p = Path(d) / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")


def jw(path, obj):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
    return Path(path)


def tw(path, text):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(text, encoding="utf-8")
    return Path(path)


def frontmatter(text: str) -> dict:
    m = re.match(r"---\n(.*?)\n---\n", text, flags=re.S)
    if not m:
        return {}
    import yaml
    try:
        return yaml.safe_load(m.group(1)) or {}
    except Exception:
        out = {}
        for line in m.group(1).splitlines():
            if ":" in line and not line.startswith(" "):
                k, v = line.split(":", 1)
                out[k.strip()] = v.strip().strip('"')
        return out


HOTL_SECTIONS = ["Intent Contract", "Verification Contract", "Governance Contract", "Scope", "Decisions",
                 "Surface", "Risks & Open Questions"]


def hotl_document_lint(text: str):
    """Reimplementation of the documented document-lint contract (warning-only, exit 0)."""
    fm = frontmatter(text)
    dtype = fm.get("design_type")
    if not dtype and not fm.get("hotl_managed"):
        return "SKIP", []
    if dtype not in ("feature", "phase"):
        return "OK", []
    warns = []
    heads = re.findall(r"^## (.+?)\s*$", text, flags=re.M)
    for s in HOTL_SECTIONS:
        if s not in heads:
            warns.append('category=structure severity=warning design_type=%s message="missing required section: ## %s"'
                         % (dtype, s))
    lines = text.splitlines()
    in_fence, fence_start, fence_n, quoted = False, 0, 0, False
    for i, line in enumerate(lines, 1):
        if line.startswith("```"):
            if in_fence and fence_n > 10:
                warns.append('category=implementation-leakage severity=warning design_type=%s line=%d message='
                             '"long fenced code block (%d lines)"' % (dtype, fence_start, fence_n))
            in_fence, fence_start, fence_n = not in_fence, i, 0
            continue
        if in_fence:
            fence_n += 1
            continue
        if line.startswith(">"):
            continue
        if re.search(r"\b[\w/.-]+\.(py|ts|js|go|rs|tsx|java):\d+\b", line):
            warns.append('category=implementation-leakage severity=warning design_type=%s line=%d message='
                         '"file:line reference"' % (dtype, i))
        if len(re.findall(r"(?<!\S)--[\w-]+", line)) >= 6:
            warns.append('category=implementation-leakage severity=warning design_type=%s line=%d message='
                         '"dense flag line"' % (dtype, i))
    return "OK", warns


def hotl_design(slug, date, intent, risk):
    contracts = {
        "Intent Contract": "```\nintent: %s\nconstraints: public CSV export API must not change\n"
                           "success_criteria: export of 10k rows completes under 2 s in the benchmark\n"
                           "risk_level: %s\n```" % (intent, risk),
        "Verification Contract": "```\nverify_steps:\n  - run tests: make test\n  - check: benchmark output\n"
                                 "  - confirm: p95 under 2 s\n```",
        "Governance Contract": "```\napproval_gates: [design approval, merge review]\nrollback: revert the merge "
                               "commit\nownership: data-platform team\n```",
        "Scope": "| In | Out |\n|---|---|\n| streaming CSV writer | new formats |",
        "Decisions": "| # | Decision | Choice | Rejected |\n|---|---|---|---|\n| 1 | buffering | stream rows | "
                     "build whole file in memory |",
        "Surface": "Export service streams rows to the response; storage untouched.",
        "Risks & Open Questions": "Large exports may hold a DB cursor open; confirm cursor timeout.",
    }
    body = "---\ndesign_type: feature\ncreated_at: %s\n---\n\n# %s design\n\n" % (date, slug)
    body += "\n\n".join("## %s\n\n%s" % (k, contracts[k]) for k in HOTL_SECTIONS) + "\n"
    return body


def hotl_parse_workflow(text):
    steps = []
    for m in re.finditer(r"^### Step (\d+): (.+?)\n```yaml\n(.*?)```", text, flags=re.S | re.M):
        import yaml
        spec = yaml.safe_load(m.group(3))
        steps.append({"n": int(m.group(1)), "title": m.group(2), **spec})
    return steps


def hotl_verify(v, root):
    if isinstance(v, str):
        v = {"type": "shell", "command": v}
    if isinstance(v, list):
        res = [hotl_verify(x, root) for x in v]
        return ("pass" if all(r[0] == "pass" for r in res) else
                next(r for r in res if r[0] != "pass")[0]), [r[1] for r in res]
    t = v.get("type")
    if t == "shell":
        p = subprocess.run(v["command"], shell=True, cwd=root, capture_output=True, text=True, timeout=20)
        return ("pass" if p.returncode == 0 else "fail"), {"exit": p.returncode, "stdout": p.stdout[-200:]}
    if t == "human-review":
        return "blocked", {"reason": "human review required: " + v.get("check", "")}
    if t == "browser":
        return "blocked", {"reason": "human review required (browser unavailable, downgraded): " + v.get("check", "")}
    if t == "artifact":
        p = Path(root) / v["path"]
        kind = v.get("assert", {}).get("kind", "exists")
        val = v.get("assert", {}).get("value", "")
        if kind == "exists":
            return ("pass" if p.exists() else "fail"), {"path": v["path"]}
        if kind == "contains":
            return ("pass" if p.is_file() and val in p.read_text() else "fail"), {"path": v["path"]}
        if kind == "matches-glob":
            if "/" in val:
                return "invalid", {"reason": "matches-glob value must be a filename glob only: " + val}
            return ("pass" if p.is_dir() and any(p.glob(val)) else "fail"), {"path": v["path"], "glob": val}
    return "invalid", {"reason": "unknown verify type %r" % t}


def hotl_execute(steps, root, state_path, approvals=None):
    approvals = approvals or {}
    state = {"status": "running", "steps": {}, "batches": []}
    order = sorted(steps, key=lambda s: s["n"])
    for b in range(0, len(order), 3):
        batch = order[b:b + 3]
        state["batches"].append([s["n"] for s in batch])
        for s in batch:
            state["steps"][s["n"]] = {"status": "running"}
            jw(state_path, state)
            if s.get("action"):
                subprocess.run(s["action"], shell=True, cwd=root, capture_output=True, timeout=20)
            verdict, detail = hotl_verify(s["verify"], root)
            if verdict == "blocked" and approvals.get(s["n"]) == "approved":
                verdict = "pass"
                detail = {"gate": "approved", "mode": "human"}
            state["steps"][s["n"]] = {"status": {"pass": "done"}.get(verdict, verdict), "detail": detail}
            jw(state_path, state)
            if verdict != "pass":
                state["status"] = "paused" if verdict == "blocked" else "stopped"
                state["stopped_at"] = s["n"]
                jw(state_path, state)
                return state
        state.setdefault("checkpoints", []).append("review after batch %d" % len(state["batches"]))
    state["status"] = "ready_to_finish"
    jw(state_path, state)
    return state


def libgdx_audit(root: Path):
    out = []
    gradle = (root / "build.gradle").read_text() if (root / "build.gradle").exists() else ""
    gp = (root / "gradle.properties").read_text() if (root / "gradle.properties").exists() else ""
    m = re.search(r"gdxVersion\s*=\s*['\"]?([\d.]+)", gradle + "\n" + gp)
    if m and tuple(int(x) for x in m.group(1).split(".")) < (1, 14, 0):
        out.append(("project-setup", "libGDX version %s < 1.14.0" % m.group(1), "gradle.properties"))
    for f in sorted(root.rglob("*.java")):
        src = f.read_text()
        rel = str(f.relative_to(root))
        cls = re.search(r"class (\w+)", src)
        cname = cls.group(1) if cls else ""
        ctor = re.search(r"public %s\s*\([^)]*\)\s*\{(.*?)\n    \}" % cname, src, flags=re.S)
        if ctor and "setInputProcessor" in ctor.group(1):
            out.append(("screen-lifecycle", "setInputProcessor in constructor (belongs in show())", rel))
        if "implements Screen" in src and "setInputProcessor(null)" not in src:
            out.append(("screen-lifecycle", "no setInputProcessor(null) in hide()", rel))
        if re.search(r"static\s+(final\s+)?AssetManager", src):
            out.append(("assets", "static AssetManager", rel))
        if re.search(r"static\s+(final\s+)?(Texture|SpriteBatch|BitmapFont)\b", src):
            out.append(("disposal", "static field holding an OpenGL resource", rel))
        if re.search(r"new Texture\(", src):
            out.append(("assets", "direct new Texture() instead of AssetManager", rel))
        render = re.search(r"void render\([^)]*\)\s*\{(.*?)\n    \}", src, flags=re.S)
        if render:
            body = render.group(1)
            b0, b1 = body.find("batch.begin()"), body.find("batch.end()")
            if 0 <= b0 < b1 and "shapes.begin" in body[b0:b1]:
                out.append(("rendering", "ShapeRenderer used inside SpriteBatch begin/end", rel))
            if re.search(r"new (Texture|Pixmap|FrameBuffer|Vector2)\(", body):
                out.append(("performance", "per-frame allocation in render()", rel))
        for res in re.findall(r"(?:private|public)?\s*(?:SpriteBatch|ShapeRenderer|BitmapFont|Stage)\s+(\w+)\s*[;=]", src):
            if not re.search(r"\b%s\.dispose\(\)" % res, src):
                out.append(("disposal", "%s never disposed" % res, rel))
    return sorted(set(out))


def otel_audit(path: Path):
    tree = ast.parse(path.read_text())
    out = []
    funcs = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    for fn in funcs:
        for n in ast.walk(fn):
            if isinstance(n, ast.Call):
                name = getattr(n.func, "id", None) or getattr(n.func, "attr", None)
                if name in ("TracerProvider",):
                    out.append(("sdk", "TracerProvider created inside %s() (per call)" % fn.name, n.lineno))
                if name == "TraceContextTextMapPropagator":
                    out.append(("propagation", "per-call propagator instantiation in %s()" % fn.name, n.lineno))
                if name == "start_span":
                    out.append(("span", "raw start_span instead of start_as_current_span", n.lineno))
                if name in ("start_as_current_span", "start_span") and n.args and isinstance(n.args[0], ast.JoinedStr):
                    out.append(("span", "high-cardinality span name (f-string)", n.lineno))
                if name == "set_status" and n.args and "OK" in ast.unparse(n.args[0]):
                    out.append(("span", "status explicitly set to OK on inner span", n.lineno))
                if name == "set_attribute" and n.args and isinstance(n.args[0], ast.Constant):
                    key = n.args[0].value
                    if re.search(r"email|password|ssn|phone", key):
                        out.append(("attributes", "PII attribute %s" % key, n.lineno))
                    elif re.search(r"[A-Z]", key):
                        out.append(("attributes", "non-semconv attribute %s" % key, n.lineno))
    for n in ast.walk(tree):
        if isinstance(n, ast.Call):
            name = getattr(n.func, "id", None) or getattr(n.func, "attr", None)
            if name == "SimpleSpanProcessor":
                out.append(("exporter", "SimpleSpanProcessor in production", n.lineno))
            if name == "JaegerExporter":
                out.append(("exporter", "Jaeger exporter (removed; use OTLP)", n.lineno))
            if name == "Resource" or (name == "create" and "Resource" in ast.unparse(n.func)):
                txt = ast.unparse(n)
                if "service.version" not in txt:
                    out.append(("sdk", "resource missing service.version", n.lineno))
    src = path.read_text()
    if "TracerProvider" in src and not re.search(r"atexit\.register|signal\.signal", src):
        out.append(("sdk", "no shutdown registered to flush spans", 0))
    return sorted(set(out), key=lambda x: (x[2], x[1]))


PWA_BAD = {
    "public/manifest.webmanifest": json.dumps({"name": "Shop", "start_url": "/", "display": "standalone",
                                               "icons": [{"src": "/i192.png", "sizes": "192x192", "type": "image/png"}]}, indent=1),
    "src/sw.js": "self.addEventListener('install', e => {\n  self.skipWaiting();\n"
                 "  e.waitUntil(caches.open('static').then(c => c.addAll(['/', '/app.js'])));\n});\n"
                 "self.addEventListener('fetch', e => {\n  e.respondWith(fetch(e.request));\n});\n",
    "src/main.js": "navigator.serviceWorker.register('/sw.js');\nlocalStorage.setItem('catalog', JSON.stringify(bigCatalog));\n",
    "index.html": "<html><head><meta name=\"viewport\" content=\"width=device-width\"></head><body></body></html>\n",
    "nginx.conf": "add_header Content-Security-Policy \"script-src 'self' 'unsafe-inline'\";\n",
    "dist/sw.js": "self.skipWaiting();\n",
}


PWA_GOOD = {
    "public/manifest.webmanifest": json.dumps({"id": "/", "name": "Shop", "short_name": "Shop", "start_url": "/?source=pwa",
                                               "display": "standalone", "theme_color": "#123456", "icons": [
        {"src": "/i192.png", "sizes": "192x192", "type": "image/png", "purpose": "any maskable"},
        {"src": "/i512.png", "sizes": "512x512", "type": "image/png", "purpose": "any maskable"}]}, indent=1),
    "src/sw.js": "const V = 'static-v3';\nself.addEventListener('install', e => {\n"
                 "  e.waitUntil(caches.open(V).then(c => c.addAll(['/', '/offline.html'])));\n});\n"
                 "self.addEventListener('message', e => { if (e.data === 'SKIP_WAITING') self.skipWaiting(); });\n"
                 "self.addEventListener('fetch', e => {\n  e.respondWith(caches.match(e.request).then(r => r || fetch(e.request)));\n});\n",
    "src/main.js": "navigator.serviceWorker.register('/sw.js');\nnavigator.serviceWorker.addEventListener('controllerchange', () => location.reload());\n",
    "index.html": "<html><head><meta name=\"viewport\" content=\"width=device-width\"><meta name=\"theme-color\" content=\"#123456\">"
                  "<meta name=\"apple-mobile-web-app-capable\" content=\"yes\"><meta name=\"apple-mobile-web-app-status-bar-style\" "
                  "content=\"default\"><meta name=\"apple-mobile-web-app-title\" content=\"Shop\"><link rel=\"apple-touch-icon\" "
                  "href=\"/a180.png\"></head><body></body></html>\n",
    "nginx.conf": "add_header Content-Security-Policy \"script-src 'self' 'nonce-abc'\";\nadd_header Strict-Transport-Security max-age=63072000;\n",
}


def _line(text, pat):
    for i, l in enumerate(text.splitlines(), 1):
        if re.search(pat, l):
            return i
    return 0


def pwa_audit(root: Path):
    srcs = {str(p.relative_to(root)): p.read_text() for p in sorted(root.rglob("*")) if p.is_file()
            and not ({"dist", "build", ".next"} & set(p.relative_to(root).parts))}
    crit, imp = [], []
    man_path = next(k for k in srcs if k.endswith(("manifest.webmanifest", "manifest.json")))
    man = json.loads(srcs[man_path])
    sw_path = next(k for k in srcs if re.search(r"(sw|service-worker)\.js$", k))
    sw = srcs[sw_path]
    allsrc = "\n".join(srcs.values())
    if "skipWaiting()" in sw and "controllerchange" not in allsrc:
        crit.append(("skipWaiting() without coordinated client reload", sw_path, _line(sw, r"skipWaiting")))
    m = re.search(r"caches\.open\('([^']+)'\)", sw)
    if m and "addAll" in sw and not re.search(r"v\d+|[0-9a-f]{8}", m.group(1)):
        crit.append(("precache list without version suffix", sw_path, _line(sw, r"addAll")))
    icons = man.get("icons", [])
    mask = {i["sizes"] for i in icons if "maskable" in i.get("purpose", "")}
    if man.get("display") == "standalone" and not {"192x192", "512x512"} <= mask:
        crit.append(("standalone manifest without maskable 192 and 512 icons", man_path, _line(srcs[man_path], r"icons")))
    for k, t in srcs.items():
        if re.search(r"script-src[^;\"]*'unsafe-inline'", t) and "nonce-" not in t:
            crit.append(("CSP allows 'unsafe-inline' for script-src", k, _line(t, r"unsafe-inline")))
    if re.search(r"respondWith\(fetch\(e(vent)?\.request\)\)", sw):
        imp.append(("fetch handler passes every request to network", sw_path, _line(sw, r"respondWith")))
    if "source=" not in str(man.get("start_url", "")):
        imp.append(("start_url lacks a tracking parameter", man_path, _line(srcs[man_path], r"start_url")))
    for k, t in srcs.items():
        if re.search(r"localStorage\.setItem\([^)]*JSON\.stringify", t):
            imp.append(("localStorage used for large data", k, _line(t, r"localStorage")))
    html = srcs.get("index.html", "")
    missing = [t for t in ("apple-mobile-web-app-capable", "apple-mobile-web-app-title", "apple-touch-icon", "theme-color") if t not in html]
    if missing:
        imp.append(("iOS meta block incomplete: " + ", ".join(missing), "index.html", 1))
    return crit, imp


PWA_ITEMS = [
    ("Manifest", "id is explicit", lambda s: '"id"' in s["man"]),
    ("Manifest", "name and short_name present", lambda s: all(k in json.loads(s["man"]) for k in ("name", "short_name"))),
    ("Manifest", "display is not browser", lambda s: json.loads(s["man"]).get("display") not in (None, "browser")),
    ("Manifest", "192 and 512 PNG icons", lambda s: {"192x192", "512x512"} <= {i["sizes"] for i in json.loads(s["man"]).get("icons", [])}),
    ("Manifest", "maskable icon present", lambda s: any("maskable" in i.get("purpose", "") for i in json.loads(s["man"]).get("icons", []))),
    ("iOS-specific", "apple-touch-icon link", lambda s: "apple-touch-icon" in s["html"]),
    ("iOS-specific", "apple-mobile-web-app-title", lambda s: "apple-mobile-web-app-title" in s["html"]),
    ("Service Worker", "registered", lambda s: "serviceWorker.register" in s["js"]),
    ("Service Worker", "has fetch handler", lambda s: "'fetch'" in s["sw"]),
    ("Service Worker", "versioned cache name", lambda s: bool(re.search(r"v\d+", s["sw"]))),
    ("Security", "HSTS header", lambda s: "Strict-Transport-Security" in s["conf"]),
    ("Security", "CSP without unsafe-eval", lambda s: "Content-Security-Policy" in s["conf"] and "unsafe-eval" not in s["conf"]),
    ("Push", "pushsubscriptionchange handled", lambda s: None if "pushManager" not in s["js"] else "pushsubscriptionchange" in s["sw"]),
]


def pwa_checklist(root: Path):
    s = {"man": (root / "public/manifest.webmanifest").read_text(), "html": (root / "index.html").read_text(),
         "js": (root / "src/main.js").read_text(), "sw": (root / "src/sw.js").read_text(), "conf": (root / "nginx.conf").read_text()}
    rows = []
    for cat, item, fn in PWA_ITEMS:
        r = fn(s)
        rows.append((cat, item, "N/A" if r is None else ("PASS" if r else "FAIL")))
    cats = []
    for cat in dict.fromkeys(c for c, _, _ in rows):
        p = sum(1 for c, _, r in rows if c == cat and r == "PASS")
        f = sum(1 for c, _, r in rows if c == cat and r == "FAIL")
        n = sum(1 for c, _, r in rows if c == cat and r == "N/A")
        cats.append((cat, p, f, n))
    P, F, N = (sum(x[i] for x in cats) for i in (1, 2, 3))
    md = ["# Production Checklist Report", "**Target:** %s" % root.name, "**Date:** 2026-11-03", "", "## Summary", "",
          "| Category | Pass | Fail | N/A | Score |", "|---|---|---|---|---|"]
    md += ["| %s | %d | %d | %d | %d / %d |" % (c, p, f, n, p, p + f) for c, p, f, n in cats]
    md += ["| **Overall** | %d | %d | %d | %d / %d |" % (P, F, N, P, P + F), ""]
    for cat in dict.fromkeys(c for c, _, _ in rows):
        md += ["## " + cat] + ["- [%s] %s" % (r, i) + ("" if r != "FAIL" else ". See references/manifest.md" if cat in
                               ("Manifest", "iOS-specific") else ". See references/%s.md" % cat.lower().replace(" ", "-"))
                               for c, i, r in rows if c == cat] + [""]
    return "\n".join(md), (P, F, N)


def detect_project_type(root: Path):
    has = lambda p: (root / p).exists()
    files = [str(p.relative_to(root)) for p in root.rglob("*") if p.is_file()
             and not ({"node_modules", "vendor", ".lake", ".yarn"} & set(p.relative_to(root).parts))]
    types = []
    if has("go.mod"):
        types.append("Go CLI" if has("main.go") or has("cmd") else "Go library")
    if has("package.json") and any(f.endswith((".js", ".ts", ".tsx", ".jsx")) for f in files):
        types.append("JavaScript/TypeScript")
    if any(has(p) for p in ("pyproject.toml", "setup.py", "requirements.txt")):
        types.append("Python")
    if has("Cargo.toml"):
        cargo = (root / "Cargo.toml").read_text()
        types.append("Rust CLI" if has("src/main.rs") or list(root.glob("src/bin/*.rs")) or "[[bin]]" in cargo else "Rust library")
    if has("build.zig"):
        types.append("Zig CLI")
    return types or ["New/empty repo"]


BOOT_ORDER = ["scaffold-new-repo", "scaffold-go-cli", "scaffold-go-library", "scaffold-rust-cli", "set-up-ci", "set-up-linters",
              "set-up-secret-scanning", "add-goreleaser-homebrew", "add-community-files", "set-up-installers",
              "add-scrut-cli-tests", "set-up-review-config", "pin-everything"]


def bootstrap_plan(root: Path):
    types = detect_project_type(root)
    has = lambda p: (root / p).exists()
    plan = {}
    plan["scaffold-new-repo"] = "full" if not (has("LICENSE") and has("README.md")) else "skip (exists)"
    lang = {"Go CLI": "scaffold-go-cli", "Go library": "scaffold-go-library", "Rust CLI": "scaffold-rust-cli"}
    scaff = next((lang[t] for t in types if t in lang), None)
    if scaff and not has(".github/workflows/ci.yml"):
        plan[scaff] = "run"
        plan["scaffold-new-repo"] = "scoped: agent config only"
    ci_covered = scaff in ("scaffold-go-cli", "scaffold-go-library", "scaffold-rust-cli") and plan.get(scaff) == "run"
    plan["set-up-ci"] = "skip (included in %s)" % scaff if ci_covered else ("skip (exists)" if has(".github/workflows/ci.yml") else "run")
    plan["set-up-linters"] = {"scaffold-go-library": "scoped: cross-language only", "scaffold-rust-cli": "scoped: cross-language only",
                              "scaffold-go-cli": "scoped: .golangci.yml + cross-language"}.get(scaff if ci_covered else None, "run")
    plan["set-up-secret-scanning"] = "run"
    is_cli = any(t.endswith("CLI") for t in types)
    if "Go CLI" in types:
        plan["add-goreleaser-homebrew"] = "skip (included in scaffold-go-cli)" if ci_covered else "run"
    else:
        plan["add-goreleaser-homebrew"] = "n/a"
    plan["add-community-files"] = "skip (exists)" if has("CONTRIBUTING.md") else "run"
    plan["set-up-installers"] = "run" if is_cli else "n/a (not a CLI)"
    plan["add-scrut-cli-tests"] = "run" if is_cli else "n/a (not a CLI)"
    plan["set-up-review-config"] = "run"
    plan["pin-everything"] = "scoped: --scope dependabot"
    order = [t for t in BOOT_ORDER if t in plan]
    return types, order, plan


ACTION_TARGET = {"actions/checkout": "v6", "actions/setup-go": "v6", "actions/setup-node": "v6",
                 "actions/upload-artifact": "v7", "golangci/golangci-lint-action": "v9", "goreleaser/goreleaser-action": "v7"}


def refresh_audit(root: Path):
    import yaml
    has = lambda p: (root / p).exists()
    tools = []
    if has("LICENSE") and has("README.md") and has(".gitignore"):
        tools.append("scaffold-new-repo")
    if has(".github/workflows/ci.yml"):
        tools.append("set-up-ci")
    if has(".editorconfig") or has(".prettierrc.json") or has(".golangci.yml"):
        tools.append("set-up-linters")
    out = []
    if "set-up-ci" in tools:
        raw = (root / ".github/workflows/ci.yml").read_text()
        ci = yaml.safe_load(raw)
        for i, line in enumerate(raw.splitlines(), 1):
            m = re.search(r"uses:\s*([\w./-]+)@([\w.]+)", line)
            if m and m.group(1) in ACTION_TARGET and not re.fullmatch(r"[0-9a-f]{40}", m.group(2)):
                want = ACTION_TARGET[m.group(1)]
                if int(re.sub(r"\D", "", m.group(2)) or 0) < int(want[1:]):
                    out.append(("set-up-ci", "ci.yml:%d" % i, "%s@%s -> %s" % (m.group(1), m.group(2), want)))
        if "permissions" not in ci:
            out.append(("set-up-ci", "ci.yml", "missing top-level permissions"))
        if "concurrency" not in ci:
            out.append(("set-up-ci", "ci.yml", "missing concurrency block"))
        for j, spec in (ci.get("jobs") or {}).items():
            if "timeout-minutes" not in spec:
                out.append(("set-up-ci", "ci.yml", "job %s missing timeout-minutes" % j))
    if has("Makefile"):
        mk = (root / "Makefile").read_text()
        if ".PHONY" not in mk:
            out.append(("set-up-ci", "Makefile", "no .PHONY declarations"))
        if not re.search(r"^help:", mk, flags=re.M):
            out.append(("set-up-ci", "Makefile", "no help target"))
    if "scaffold-new-repo" in tools:
        gi = (root / ".gitignore").read_text().split()
        for pat in ("*.exe", "*.test", "*.out", "bin/", "dist/"):
            if has("go.mod") and pat not in gi:
                out.append(("scaffold-new-repo", ".gitignore", "missing Go pattern " + pat))
    if not has(".github/dependabot.yml") and not has(".github/dependabot.yaml"):
        out.append(("pin-everything", ".github/dependabot.yml", "missing Dependabot config (SHA pins go stale)"))
    return tools, out


MANIFEST_ECO = {"package-lock.json": "npm", "yarn.lock": "npm", "pnpm-lock.yaml": "npm", "uv.lock": "uv",
                "requirements.txt": "pip", "go.mod": "gomod", "Cargo.toml": "cargo", "Gemfile": "bundler", "Dockerfile": "docker"}


EXCL = {".git", "node_modules", "vendor", "dist", "build", "target", ".venv", ".yarn", "testdata"}


def dependabot_review(root: Path):
    import yaml
    inv = {}
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root)
        if not p.is_file() or EXCL & set(rel.parts):
            continue
        d = "/" if str(rel.parent) == "." else "/" + str(rel.parent)
        if p.name in MANIFEST_ECO:
            inv.setdefault(MANIFEST_ECO[p.name], set()).add(d)
        if (rel.parts[:2] == (".github", "workflows") and p.suffix in (".yml", ".yaml")) or p.name in ("action.yml", "action.yaml"):
            if "uses:" in p.read_text():
                inv.setdefault("github-actions", set()).add("/" if rel.parts[:2] == (".github", "workflows") else d)
    cfgp = next((root / ".github" / n for n in ("dependabot.yml", "dependabot.yaml") if (root / ".github" / n).exists()), None)
    cfg = yaml.safe_load(cfgp.read_text()) if cfgp else {"updates": []}
    conf = {}
    for u in cfg.get("updates", []):
        dirs = u.get("directories") or [u.get("directory", "/")]
        conf.setdefault(u["package-ecosystem"], set()).update(dirs)
    findings, matrix = [], []
    for eco in sorted(set(inv) | set(conf)):
        found, have = inv.get(eco, set()), conf.get(eco, set())
        status = "covered" if found and found <= have else ("missing" if not have else ("stale" if not found else "partial"))
        matrix.append({"ecosystem": eco, "found": sorted(found), "configured": sorted(have), "status": status})
        if status == "missing":
            findings.append(("Errors", "Coverage", "%s not configured; manifests at %s" % (eco, ", ".join(sorted(found)))))
        elif status == "partial":
            findings.append(("Errors", "Coverage", "%s directories not listed: %s" % (eco, ", ".join(sorted(found - have)))))
        elif status == "stale":
            findings.append(("Errors", "Coverage", "%s entry targets %s but no manifest exists" % (eco, ", ".join(sorted(have)))))
    for u in cfg.get("updates", []):
        if "reviewers" in u:
            findings.append(("Warnings", "Validity", "%s uses deprecated reviewers; use CODEOWNERS" % u["package-ecosystem"]))
        if not u.get("groups"):
            findings.append(("Suggestions", "Grouping", "%s has no groups" % u["package-ecosystem"]))
    untracked = [str(p.relative_to(root)) for n in (".tool-versions", ".nvmrc", ".python-version") for p in root.glob(n)]
    return matrix, findings, untracked


def verify_claims(root, claims):
    out = []
    for c in claims:
        if not c.get("command"):
            out.append({**c, "allowed": False, "status": "no verification command identified"})
            continue
        p = subprocess.run(c["command"], cwd=root, shell=True, capture_output=True, text=True, timeout=30)
        txt = p.stdout + p.stderr
        ok = p.returncode == 0 and re.search(c["success"], txt) is not None
        fails = re.search(r"failures=(\d+)|(\d+) failed", txt)
        out.append({**c, "exit": p.returncode, "allowed": ok,
                    "status": ("claim confirmed: " if ok else "actual status: ") + txt.strip().splitlines()[-1][:120],
                    "failures": int(next(g for g in fails.groups() if g)) if fails else 0})
    return out
