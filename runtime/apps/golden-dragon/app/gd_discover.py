"""gd_discover.py — «التنين الذهبي» (Golden Dragon): find what THIS PC has beyond the build-time fusion index.

The fusion index (fusion\\index.json) is a snapshot made when the app was built. This module walks the folders the owner
works in and records every skill, Claude plugin, MCP server, program, shortcut, script, tool folder, git repo and skill
archive it finds, as units in the same shape as the index, so `fusion find / show / route` reach them too.

  Read-only: it lists folders, reads the first few KB of scripts / READMEs / SKILL.md, and opens the central directory
  of .zip / .skill archives. It never runs, moves, writes or deletes anything outside its own two files.
  Local-only: the folders to walk and the results live in %APPDATA%\\GoldenDragon (discover.json + local_units.json),
  never in the repo. Nothing in this file names a person or a machine.
  Private: MCP servers are recorded by name, transport and program name only (never their arguments or environment,
  where keys live); files whose names look like secrets (.env, credentials, tokens, keys) are never opened.

Config (%APPDATA%\\GoldenDragon\\discover.json, made on the first scan, edit freely):
  {"roots": [{"path": "%USERPROFILE%\\Desktop\\Tools", "depth": 4, "label": "tools"}, ...],   # added to the defaults
   "exclude": ["*\\Photos\\*", "old-*"],      # glob on the folder path or name: never walked
   "use_defaults": true,                      # false = only the roots above
   "max_age_days": 7}                         # doctor says «stale» after this

CLI:  python -X utf8 gd_discover.py scan | summary | config
Standard library only.
"""
import fnmatch
import json
import os
import re
import sys
import time
import zipfile
from pathlib import Path

HOME = Path(os.environ.get("GOLDEN_LOCAL_HOME") or (Path(os.environ.get("APPDATA") or Path.home()) / "GoldenDragon"))
CONFIG = HOME / "discover.json"
CATALOG = HOME / "local_units.json"
VERSION = 1

KINDS = ("pc-skill", "pc-plugin", "pc-mcp", "pc-app", "pc-script", "pc-tool", "pc-repo", "pc-pack")
SCRIPT_EXT = {".py": "python -X utf8", ".ps1": "powershell -ExecutionPolicy Bypass -File", ".cmd": "", ".bat": "",
              ".sh": "bash", ".js": "node", ".mjs": "node"}
PROJECT_MARKERS = ("package.json", "pyproject.toml", "setup.py", "Cargo.toml", "go.mod")
PRUNE = {"node_modules", "__pycache__", "_internal", "site-packages", "venv", ".venv", "env", "dist", "build", "re_work",
         "frames", "cache", "Cache", "logs", "$RECYCLE.BIN", "System Volume Information", "bower_components", "vendor",
         "WindowsApps", "Temp", "tmp"}
PRUNE_SUFFIX = ("_extracted", ".app", ".bak")
INSTALLER = re.compile(r"(setup|install|unins|uninstall|update|updater|redist|crash|helper|elevat|repair|\.tmp$|^\d+$)", re.I)
SECRET = re.compile(r"(^\.env|credential|secret|token|password|\.pem$|\.key$|id_rsa|cookies?)", re.I)
MAX_UNITS, MAX_ENTRIES, BUDGET_S, BIG_DIR, ZIP_CAP = 6000, 400_000, 120.0, 4000, 800 * 1024 * 1024


# ---------------------------------------------------------------- where to look
def _desktops():
    """Every place Windows may keep the Desktop: the shell folder in the registry (OneDrive moves it), then the usual two."""
    out = []
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders") as k:
            out.append(os.path.expandvars(winreg.QueryValueEx(k, "Desktop")[0]))
    except (ImportError, OSError):
        pass
    if os.environ.get("OneDrive"):
        out.append(os.path.join(os.environ["OneDrive"], "Desktop"))
    out += [str(Path.home() / "OneDrive" / "Desktop"), str(Path.home() / "Desktop")]
    return out


def default_roots():
    h = Path.home()
    la = os.environ.get("LOCALAPPDATA") or str(h / "AppData" / "Local")
    ra = os.environ.get("APPDATA") or str(h / "AppData" / "Roaming")
    pd = os.environ.get("ProgramData") or r"C:\ProgramData"
    roots = [{"path": str(h / ".claude" / "skills"), "depth": 1, "label": "claude-skills"},
             {"path": str(h / ".claude" / "plugins"), "depth": 6, "label": "claude-plugins"},
             {"path": str(h / "Downloads"), "depth": 2, "label": "downloads"},
             {"path": str(h / "Documents"), "depth": 2, "label": "documents"},
             {"path": os.path.join(la, "BlackDragon"), "depth": 2, "label": "black-dragon"},
             {"path": str(h / "GoldenDragon" / "studio"), "depth": 3, "label": "golden-studio"},
             {"path": os.path.join(ra, r"Microsoft\Windows\Start Menu\Programs"), "depth": 3, "label": "start-menu"},
             {"path": os.path.join(pd, r"Microsoft\Windows\Start Menu\Programs"), "depth": 3, "label": "start-menu"}]
    roots += [{"path": d, "depth": 4, "label": "desktop"} for d in _desktops()]
    return roots


def mcp_configs():
    h = Path.home()
    ra = os.environ.get("APPDATA") or str(h / "AppData" / "Roaming")
    return [Path(ra) / "Claude" / "claude_desktop_config.json", h / ".claude.json", h / ".claude" / "settings.json",
            h / ".mcp.json"]


def load_config():
    try:
        return json.loads(CONFIG.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return {}


def write_config_if_missing():
    if CONFIG.is_file():
        return False
    HOME.mkdir(parents=True, exist_ok=True)
    CONFIG.write_text(json.dumps({
        "_help": "Golden Dragon discovery: extra folders to walk (path, depth, label), globs to skip, and whether the "
                 "built-in places (Desktop, Downloads, Documents, Start menu, ~/.claude) are walked too.",
        "roots": [], "exclude": [], "use_defaults": True, "max_age_days": 7}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    return True


def roots_from(cfg):
    out, seen = [], set()
    extra = [r for r in cfg.get("roots") or [] if isinstance(r, dict) and r.get("path")]
    for r in extra + (default_roots() if cfg.get("use_defaults", True) else []):
        p = Path(os.path.expandvars(os.path.expanduser(str(r["path"]))))
        try:
            key = os.path.normcase(str(p.resolve()))
        except OSError:
            continue
        if key in seen or not p.is_dir():
            continue
        seen.add(key)
        out.append({"path": p, "key": key, "depth": max(0, min(int(r.get("depth", 3)), 8)), "label": str(r.get("label") or p.name),
                    "archives": bool(r.get("archives"))})
    # the most specific folder first: a deep root inside the Desktop is walked with its own depth, then the Desktop
    # walk skips what was already seen
    out.sort(key=lambda r: -len(r["key"]))
    return out


# ---------------------------------------------------------------- reading a little of a file
def _head(p, n=4096):
    if SECRET.search(p.name):
        return ""
    try:
        with open(p, "rb") as f:
            return f.read(n).decode("utf-8", "replace")
    except OSError:
        return ""


def _front(text):
    m = re.match(r"^\ufeff?---\s*\n(.*?)\n---", text, re.S)
    meta = {}
    if m:
        cur = None
        for line in m.group(1).splitlines():
            if re.match(r"^[A-Za-z_-]+\s*:", line):
                k, v = line.split(":", 1)
                cur = k.strip()
                meta[cur] = v.strip().strip('"').strip("'")
            elif cur and line.startswith(" "):
                meta[cur] = (meta[cur] + " " + line.strip()).strip()
    return meta


def _script_desc(p):
    t = _head(p, 3000)
    m = re.match(r'^\ufeff?(?:#![^\n]*\n)?(?:#[^\n]*coding[^\n]*\n)?\s*(?:[rubRUB]{0,2})("""|\'\'\')(.*?)(\1|$)', t, re.S)
    if m and p.suffix == ".py":
        return " ".join(m.group(2).split())[:240]
    lines = []
    for ln in t.splitlines()[:25]:
        s = ln.strip()
        if not s or s.startswith("#!") or s.lower().startswith("@echo") or s.lower() in ("setlocal", "param()"):
            if lines:
                break
            continue
        c = re.match(r"^(?:#+|//+|rem\b|::|<#|\*)\s?(.*)$", s, re.I)
        if not c:
            break
        if c.group(1).strip() and not c.group(1).strip().startswith(("-*-", "requires", "eslint")):
            lines.append(c.group(1).strip())
    return " ".join(lines)[:240]


def _readme_desc(d):
    for name in ("README.md", "readme.md", "README.txt", "README", "README.adoc", "ANALYSIS.md"):
        p = d / name
        if p.is_file():
            for ln in _head(p, 6000).splitlines():
                s = ln.strip().lstrip("#").strip()
                if s and not s.startswith(("[!", "<", "![", "---", "```", "|")) and len(s) > 3:
                    return s[:240]
    return ""


# ---------------------------------------------------------------- units
def _slug(s):
    s = re.sub(r"[^\w\u0600-\u06FF]+", "-", s.lower()).strip("-")
    return s[:60] or "x"


_SPLIT = re.compile(r"[\s_\-.()\[\]{}+,]+|(?<=[a-z])(?=[A-Z])")


def _kw(*parts):
    words = []
    for p in parts:
        for w in _SPLIT.split(str(p or "")):
            w = w.strip().lower()
            if len(w) > 1 and not w.isdigit() and w not in words:
                words.append(w)
    return words[:24]


class Catalog:
    def __init__(self, indexed_skills=()):
        self.units, self.ids, self.paths = [], set(), set()
        self.indexed = {s.lower() for s in indexed_skills}
        self.entries, self.t0, self.cut = 0, time.monotonic(), ""
        self.per_root = {}

    def full(self):
        if len(self.units) >= MAX_UNITS:
            self.cut = "units"
        elif self.entries >= MAX_ENTRIES:
            self.cut = "entries"
        elif time.monotonic() - self.t0 > BUDGET_S:
            self.cut = "time"
        return bool(self.cut)

    def add(self, kind, name, path, what="", how="", status="local", cost="free", label="", rel="", extra=None, warn=None):
        key = os.path.normcase(str(path))
        if key in self.paths:
            return None
        self.paths.add(key)
        base = f"{kind}:{_slug(name)}"
        uid, n = base, 2
        while uid in self.ids:
            uid, n = f"{base}-{n}", n + 1
        self.ids.add(uid)
        u = {"id": uid, "kind": kind, "name": name, "what": what or "", "what_ar": "", "how": how, "status": status,
             "cost": cost, "family": "pc:" + label if label else "pc", "keywords": _kw(name, rel, label),
             "path": str(path), "origin": "pc"}
        if extra:
            u["extra"] = extra
        if warn:
            u["warn_ar"] = warn
        self.units.append(u)
        self.per_root[label] = self.per_root.get(label, 0) + 1
        return u


def _skill(cat, d, label, rel, plugin=""):
    sk = d / "SKILL.md"
    meta = _front(_head(sk, 8000))
    name = meta.get("name") or d.name
    full = f"{plugin}:{name}" if plugin else name
    installed = label == "claude-skills"
    if installed and name.lower() in cat.indexed:
        return                                   # already in the fusion index with its full static scan
    status = "local" if installed or plugin else "copy"
    warn = None if installed or plugin else ["نسخة برّه مجلد المهارات المتثبتة: ممكن تكون أقدم أو مختلفة. اقراها بالمسار، أو ثبّتها الأول"]
    cat.add("pc-skill", full, sk, meta.get("description", ""),
            f"skill read {full}" if installed or plugin else f"اقرا {sk}", status, "free", label, rel,
            {"in_index": name.lower() in cat.indexed, "plugin": plugin} if (plugin or name.lower() in cat.indexed) else None, warn)


def _plugin(cat, d, label, rel):
    pj = d / ".claude-plugin" / "plugin.json"
    try:
        meta = json.loads(_head(pj, 65536) or "{}")
    except ValueError:
        meta = {}
    name = str(meta.get("name") or d.name)
    skills = [p.parent for p in d.rglob("SKILL.md") if len(p.relative_to(d).parts) <= 4]
    cmds = [p for p in (d / "commands").glob("*.md")] if (d / "commands").is_dir() else []
    cat.add("pc-plugin", name, d, str(meta.get("description") or ""), f"/plugin (enabled as {name})", "local", "free", label, rel,
            {"skills": len(skills), "commands": len(cmds), "version": meta.get("version", "")})
    for s in skills:
        _skill(cat, s, label, rel, plugin=name)


def _pack(cat, p, label, rel):
    """A .skill / .zip that holds a SKILL.md: a skill that is not installed."""
    try:
        if p.stat().st_size > ZIP_CAP:
            return
        with zipfile.ZipFile(p) as z:
            names = [n for n in z.namelist() if n.endswith("SKILL.md")]
    except (OSError, zipfile.BadZipFile, RuntimeError, ValueError):
        return
    if not names and p.suffix.lower() != ".skill":
        return None
    return cat.add("pc-pack", p.stem, p, f"أرشيف فيه {len(names)} مهارة: " + ", ".join(Path(n).parent.name or p.stem for n in names[:6]),
            f"فكّه في فولدر جديد واقرا SKILL.md (ماتشغّلش حاجة منه قبل ما تقراها)", "archive", "approval", label, rel,
            {"skills": len(names)}, ["أرشيف مش متثبّت: التثبيت محتاج موافقة"])


def _extension(cat, d, label, rel):
    try:
        meta = json.loads(_head(d / "manifest.json", 65536) or "{}")
    except ValueError:
        meta = {}
    if "manifest_version" not in meta:
        _project(cat, d, label, rel, "pc-tool")
        return
    nm = str(meta.get("name") or d.name)
    cat.add("pc-tool", nm if not nm.startswith("__MSG_") else d.name, d,
            "إضافة متصفح (unpacked) " + str(meta.get("version", "")) + ": " + str(meta.get("description") or ""),
            "chrome://extensions ← وضع المطوّر ← تحميل غير مضغوط على الفولدر ده", "local", "approval", label, rel,
            {"extension": True}, ["تثبيت إضافة متصفح: صاحب الجهاز بيعملها بإيده"])


def _archive(cat, p, label, rel):
    """A program that is still packed (a root with "archives": true, e.g. a folder of downloaded studio programs)."""
    name = p.parent.name if p.parent.name.lower() not in ("downloads", "programs") and rel else p.stem
    cat.add("pc-app", name, p, f"برنامج لسه مضغوط ({p.suffix.lower()}): {p.name}",
            "فكّه في فولدر جديد (بعد موافقة)، وبعدين show تاني بعد discover", "archive", "approval", label, rel,
            {"archive": p.name, "mb": round(_size(p) / 1048576, 1)}, ["برنامج مش متفك: الفك والتشغيل محتاجين موافقة"])


def _app(cat, p, label, rel, how=None):
    cat.add("pc-app", p.stem, p, _readme_desc(p.parent) if p.suffix.lower() == ".exe" else "",
            how or f'"{p}"', "local", "approval", label, rel, None, ["تشغيل برنامج: محتاج موافقة"])


def _script(cat, p, label, rel):
    runner = SCRIPT_EXT[p.suffix.lower()]
    cat.add("pc-script", p.name, p, _script_desc(p), f'{runner} "{p}"'.strip(), "local", "approval", label, rel, None,
            ["سكربت محلي: اقراه قبل التشغيل، والتشغيل محتاج موافقة"])


def _project(cat, d, label, rel, kind):
    what, how = _readme_desc(d), ""
    pj = d / "package.json"
    if pj.is_file():
        try:
            meta = json.loads(_head(pj, 65536) or "{}")
            what = what or str(meta.get("description") or "")
            sc = list((meta.get("scripts") or {}).keys())[:6]
            how = f'cd "{d}" && npm run ' + "|".join(sc) if sc else ""
        except ValueError:
            pass
    exes = sorted((x for x in d.glob("*.exe") if not INSTALLER.search(x.stem)), key=lambda x: -x.stat().st_size)
    if not how and exes:
        how = f'"{exes[0]}"'
    if not how:
        pys = [x for x in d.glob("*.py")]
        how = f'python -X utf8 "{pys[0]}"' if len(pys) == 1 else f"اقرا README في {d}"
    cat.add(kind, d.name, d, what, how, "local", "approval", label, rel, None,
            ["فولدر مشروع: اقرا الـ README قبل التشغيل"] if kind == "pc-tool" else None)


# ---------------------------------------------------------------- the walk
def _excluded(p, excl):
    s = str(p)
    return any(fnmatch.fnmatch(s, g) or fnmatch.fnmatch(p.name, g) for g in excl)


def walk(cat, root, visited, excl):
    label, top = root["label"], root["path"]
    stack = [(top, 0)]
    while stack and not cat.full():
        d, depth = stack.pop()
        key = os.path.normcase(str(d))
        if key in visited:
            continue
        visited.add(key)
        try:
            entries = list(os.scandir(d))
        except OSError:
            continue
        cat.entries += len(entries)
        rel = str(d.relative_to(top)) if d != top else ""
        names = {e.name for e in entries}
        if d != top:                 # a stray SKILL.md lying on the Desktop does not make the Desktop a skill
            if "SKILL.md" in names:
                _skill(cat, d, label, rel)
                continue
            if ".claude-plugin" in names and (d / ".claude-plugin" / "plugin.json").is_file():
                _plugin(cat, d, label, rel)
                continue
        if d != top and ".git" in names:
            _project(cat, d, label, rel, "pc-repo")
            continue
        if d != top and any(m in names for m in PROJECT_MARKERS):
            _project(cat, d, label, rel, "pc-tool")
            continue
        if d != top and "manifest.json" in names and any(n.endswith(".js") for n in names):
            _extension(cat, d, label, rel)           # a browser extension (unpacked)
            continue
        if d != top and "index.html" in names and any(n.endswith((".js", ".css")) for n in names):
            _project(cat, d, label, rel, "pc-tool")  # a small offline web app
            continue
        if ".mcp.json" in names:
            _mcp_file(cat, d / ".mcp.json", label)
        files = [e for e in entries if _is_file(e)]
        exes = [Path(e.path) for e in files if e.name.lower().endswith(".exe") and not INSTALLER.search(e.name[:-4])]
        loose = d == top
        subdirs = sum(1 for e in entries if _is_dir(e) and e.name not in PRUNE and not e.name.startswith("."))
        if exes and not loose and subdirs <= 6:
            # a program folder: up to 3 exes, else its main one (named like the folder, else the biggest); nothing deeper
            best = sorted(exes, key=lambda x: (_slug(x.stem) not in _slug(d.name) and _slug(d.name) not in _slug(x.stem),
                                               -_size(x)))
            for x in (best if len(best) <= 3 else best[:1]):
                _app(cat, x, label, rel)
            continue
        if exes and not loose:                       # a work folder that also holds a program: list both, keep walking
            loose = True
        scripts = [Path(e.path) for e in files if Path(e.name).suffix.lower() in SCRIPT_EXT and not SECRET.search(e.name)]
        has_readme = any(n.lower().startswith("readme") for n in names)
        if not loose and (len(scripts) > 12 or (has_readme and len(scripts) >= 4)):
            # a code folder (an app's own modules), not a set of separate tools: one unit for the folder
            _project(cat, d, label, rel, "pc-tool")
            continue
        for e in files:
            p = Path(e.path)
            ext = p.suffix.lower()
            if ext == ".exe" and p in exes:
                _app(cat, p, label, rel)
            elif ext == ".lnk" and not INSTALLER.search(p.stem):
                _app(cat, p, label, rel, how=f'start "" "{p}"')
            elif ext in (".skill", ".zip"):
                if not _pack(cat, p, label, rel) and root.get("archives"):
                    _archive(cat, p, label, rel)
            elif ext in (".7z", ".rar", ".msi") and root.get("archives"):
                _archive(cat, p, label, rel)
            elif p in scripts:
                _script(cat, p, label, rel)
        if depth >= root["depth"] or len(entries) > BIG_DIR:
            continue
        for e in entries:
            if not _is_dir(e) or e.name.startswith(".") or e.name in PRUNE or e.name.endswith(PRUNE_SUFFIX):
                continue
            sub = Path(e.path)
            if _excluded(sub, excl):
                continue
            stack.append((sub, depth + 1))


def _is_file(e):
    try:
        return e.is_file()
    except OSError:
        return False


def _is_dir(e):
    try:
        return e.is_dir(follow_symlinks=False) or (e.is_dir() and not e.is_symlink())
    except OSError:
        return False


def _size(p):
    try:
        return p.stat().st_size
    except OSError:
        return 0


# ---------------------------------------------------------------- MCP servers (names only)
def _mcp_entries(obj):
    out = []
    if isinstance(obj, dict):
        for name, v in (obj.get("mcpServers") or {}).items():
            if isinstance(v, dict):
                out.append((name, v))
        for proj in (obj.get("projects") or {}).values():
            if isinstance(proj, dict):
                for name, v in (proj.get("mcpServers") or {}).items():
                    if isinstance(v, dict):
                        out.append((name, v))
    return out


def _mcp_file(cat, p, label):
    try:
        obj = json.loads(p.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return
    for name, v in _mcp_entries(obj):
        same = [u for u in cat.units if u["kind"] == "pc-mcp" and u["name"] == name]
        if same:
            cfgs = same[0]["extra"].setdefault("also_in", [])
            if p.name not in cfgs and p.name != same[0]["extra"]["config"]:
                cfgs.append(p.name)
            continue
        transport = v.get("type") or ("http" if v.get("url") else "stdio")
        prog = Path(str(v.get("command") or "")).name
        host = re.sub(r"^\w+://([^/:@]*@)?([^/:]+).*$", r"\2", str(v.get("url") or "")) if v.get("url") else ""
        cat.add("pc-mcp", name, f"{p}#{name}", f"MCP server «{name}» ({transport}" + (f", {prog}" if prog else "")
                + (f", {host}" if host else "") + ")", f"mcp__{name}__…", "local", "free", label or "mcp", "",
                {"transport": transport, "program": prog, "config": p.name})


# ---------------------------------------------------------------- scan / load
def scan(indexed_skills=(), cfg=None):
    write_config_if_missing()
    cfg = load_config() if cfg is None else cfg
    cat = Catalog(indexed_skills)
    excl = [str(x) for x in cfg.get("exclude") or []]
    for p in mcp_configs():
        if p.is_file():
            _mcp_file(cat, p, "mcp")
    visited = set()
    roots = roots_from(cfg)
    for r in roots:
        if cat.full():
            break
        walk(cat, r, visited, excl)
    data = {"version": VERSION, "generated": time.strftime("%Y-%m-%d %H:%M:%S"), "seconds": round(time.monotonic() - cat.t0, 1),
            "cut": cat.cut, "roots": [{"path": str(r["path"]), "label": r["label"], "depth": r["depth"]} for r in roots],
            "per_root": cat.per_root, "units": cat.units}
    HOME.mkdir(parents=True, exist_ok=True)
    tmp = CATALOG.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=0), encoding="utf-8")
    os.replace(tmp, CATALOG)
    return data


def load(indexed_skills=(), auto=True):
    """The local catalog; on the very first use (no file yet) it scans once. Never raises: no catalog = no local units."""
    try:
        if CATALOG.is_file():
            data = json.loads(CATALOG.read_text(encoding="utf-8"))
            if data.get("version") == VERSION:
                return data
        if auto:
            return scan(indexed_skills)
    except (OSError, ValueError):
        pass
    return {"units": [], "generated": "", "roots": [], "per_root": {}}


def age_days(data):
    try:
        return (time.time() - time.mktime(time.strptime(data["generated"], "%Y-%m-%d %H:%M:%S"))) / 86400
    except (KeyError, ValueError, TypeError, OverflowError):
        return None


def summary(data):
    by = {}
    for u in data.get("units") or []:
        by[u["kind"]] = by.get(u["kind"], 0) + 1
    return by


def main(argv):
    act = argv[0] if argv else ""
    if act == "scan":
        idx = Path(__file__).resolve().parent / "fusion" / "index.json"
        names = []
        if idx.is_file():
            names = [u["name"] for u in json.loads(idx.read_text(encoding="utf-8"))["units"] if u["kind"] == "skill"]
        d = scan(names)
        print(json.dumps({"units": len(d["units"]), "kinds": summary(d), "per_root": d["per_root"], "seconds": d["seconds"],
                          "cut": d["cut"], "catalog": str(CATALOG)}, ensure_ascii=False, indent=1))
    elif act == "summary":
        d = load(auto=False)
        print(json.dumps({"units": len(d["units"]), "kinds": summary(d), "generated": d.get("generated")}, ensure_ascii=False))
    elif act == "config":
        write_config_if_missing()
        print(CONFIG)
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
