"""Doctor: which tools this machine has, which station is ready. Reads data/required_tools.json; never installs.

  doctor [--json] [--tier required|recommended|all]        exit 0 when every required tool is present
  install-plan --os linux|macos|windows|ashell [--tier] [--all] [--python EXE]   prints commands, runs nothing
  fetch <tool-id> [--force]                                  model files: download + sha256 check (explicit only)
"""
from __future__ import annotations

import argparse
import functools
import glob
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from . import common as C

ROOT = C.PKG.parents[1]
MANIFEST = C.DATA / "required_tools.json"
TIERS = ("required", "recommended", "optional")
OSES = ("linux", "macos", "windows", "ashell")
TIER_AR = {"required": "لازم", "recommended": "مهمة", "optional": "إضافة"}
FONT_EXT = (".ttf", ".otf", ".ttc")


def load(path: Path = MANIFEST) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def tiers_for(tier: str) -> tuple:
    return {"required": ("required",), "recommended": ("required", "recommended")}.get(tier, TIERS)


def _fkey(s: str) -> str:
    return s.lower().replace(" ", "").replace("-", "").replace("_", "")


def _repo_venv_has(module: str) -> str | None:
    top = module.split(".")[0]
    for pattern in (".venv*/lib/python*/site-packages", ".venv*/Lib/site-packages"):
        for sp in map(Path, glob.glob(str(ROOT / pattern))):
            if (sp / top).is_dir() or any(glob.glob(str(sp / g)) for g in (f"{top}.py", f"{top}*.so", f"{top}*.pyd")):
                return sp.parents[1 if sp.parent.name == "Lib" else 2].name
    return None


@functools.lru_cache(maxsize=1)
def _node_roots() -> tuple:
    roots = [ROOT / "node_modules", Path("/opt/node-tools/node_modules")]
    roots += [Path(p) for p in os.environ.get("NODE_PATH", "").split(os.pathsep) if p]
    if os.environ.get("APPDATA"):
        roots.append(Path(os.environ["APPDATA"]) / "npm" / "node_modules")
    npm = shutil.which("npm")
    if npm:
        try:
            r = subprocess.run([npm, "root", "-g"], capture_output=True, timeout=10, **C.TEXT)
            if r.returncode == 0 and r.stdout.strip():
                roots.append(Path(r.stdout.strip()))
        except (OSError, subprocess.SubprocessError):
            pass
    return tuple(roots)


def _browser_dirs() -> list:
    home = Path.home()
    dirs = [Path(os.environ["PLAYWRIGHT_BROWSERS_PATH"])] if os.environ.get("PLAYWRIGHT_BROWSERS_PATH") else []
    dirs += [home / ".cache" / "ms-playwright", home / "Library" / "Caches" / "ms-playwright"]
    if os.environ.get("LOCALAPPDATA"):
        dirs.append(Path(os.environ["LOCALAPPDATA"]) / "ms-playwright")
    return dirs


@functools.lru_cache(maxsize=1)
def _font_families() -> str:
    parts = []
    if shutil.which("fc-list"):
        try:
            parts.append(subprocess.run(["fc-list", ":", "family"], capture_output=True, timeout=20, **C.TEXT).stdout)
        except (OSError, subprocess.SubprocessError):
            pass
    home = Path.home()
    dirs = [Path("/usr/share/fonts"), Path("/usr/local/share/fonts"), home / ".fonts", home / ".local" / "share" / "fonts",
            Path("/Library/Fonts"), Path("/System/Library/Fonts"), home / "Library" / "Fonts"]
    if os.environ.get("WINDIR"):
        dirs.append(Path(os.environ["WINDIR"]) / "Fonts")
    if os.environ.get("LOCALAPPDATA"):
        dirs.append(Path(os.environ["LOCALAPPDATA"]) / "Microsoft" / "Windows" / "Fonts")
    parts += [f.stem for d in dirs if d.is_dir() for f in d.rglob("*") if f.suffix.lower() in FONT_EXT]
    return _fkey("\n".join(parts))


def repo_font(name: str) -> Path | None:
    """A font file of family `name` shipped in the repo (libass reaches it through fontsdir)."""
    for d in C.FONT_DIRS:
        if d.is_dir():
            for f in sorted(d.iterdir()):
                if f.suffix.lower() in FONT_EXT and _fkey(f.stem).startswith(_fkey(name)):
                    return f
    return None


def expand(p: str) -> Path | None:
    """{skill} = this package, {root} = repo root; {kmm} (old kit folder) does not exist here."""
    if "{kmm}" in p:
        return None
    return Path(p.replace("{skill}", str(C.PKG)).replace("{root}", str(ROOT))).expanduser()


def _file_check(c: dict) -> Path | None:
    env = c.get("env")
    if env and os.environ.get(env) and Path(os.environ[env]).expanduser().is_file():
        return Path(os.environ[env]).expanduser()
    for d in c.get("dirs", []):
        base = expand(d)
        f = base / c["name"] if base else None
        if f and f.is_file() and f.stat().st_size > 1024:     # a git-lfs pointer is ~130 bytes
            return f
    return None


def model_path(tool_id: str = "yunet-face-model", manifest: dict | None = None) -> Path | None:
    for t in (manifest or C.data("required_tools.json"))["tools"]:
        if t["id"] == tool_id:
            for c in t["check"]:
                f = _file_check(c) if c.get("kind") == "file" else None
                if f:
                    return f
    return None


def fetch(tool_id: str, force: bool = False, manifest: dict | None = None, dest: Path | None = None) -> Path:
    """Download a tool's "download" file (url, then mirrors); keep it only when the sha256 matches."""
    import tempfile
    import urllib.request
    t = next((x for x in (manifest or load())["tools"] if x["id"] == tool_id), None)
    if not t or not t.get("download"):
        raise ValueError(f"{tool_id}: no download block in the manifest")
    dl = t["download"]
    dest = Path(dest) if dest else expand(dl["dest"])
    if dest.is_file() and not force and C.sha256(dest) == dl["sha256"]:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    errors = []
    for url in [dl["url"], *dl.get("mirrors", [])]:
        fd, tmp = tempfile.mkstemp(prefix=".dl_", dir=dest.parent)
        os.close(fd)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "black-dragon-doctor"})
            with urllib.request.urlopen(req, timeout=120) as r, open(tmp, "wb") as out:
                shutil.copyfileobj(r, out)
            if C.sha256(tmp) != dl["sha256"]:
                raise ValueError(f"sha256 {C.sha256(tmp)} != {dl['sha256']}")
            os.replace(tmp, dest)
            return dest
        except Exception as e:  # noqa: BLE001 — next mirror
            errors.append(f"{url}: {e}")
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
    raise RuntimeError("download failed:\n  " + "\n  ".join(errors))


def check_one(c: dict) -> tuple[bool, str]:
    kind, name = c.get("kind"), c.get("name", "")
    if kind == "python":
        return sys.version_info[:3] >= tuple(int(x) for x in re.findall(r"\d+", c.get("min", "3"))[:3]), \
            f"python {sys.version.split()[0]}"
    if kind == "bin":
        p = shutil.which(name) or (C.have(name) and name)
        return bool(p), p or ""
    if kind == "py":
        try:
            if importlib.util.find_spec(name) is not None:
                return True, f"import {name}"
        except (ImportError, ValueError):
            pass
        venv = _repo_venv_has(name)
        return (True, f"{name} in {venv}") if venv else (False, "")
    if kind == "node":
        hit = next((r / name for r in _node_roots() if (r / name / "package.json").is_file()), None)
        return bool(hit), str(hit or "")
    if kind == "browser":
        for d in _browser_dirs():
            if d.is_dir() and any(x.name.startswith(name) for x in d.iterdir()):
                return True, str(d)
        b = next((shutil.which(b) for b in ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable")
                  if shutil.which(b)), None)
        return bool(b), b or ""
    if kind == "font":
        if name.lower().replace(" ", "") in _font_families():
            return True, f"font {name}"
        f = repo_font(name)
        return (True, f"font {name} (repo: {f.name})") if f else (False, "")
    if kind == "file":
        f = _file_check(c)
        return bool(f), str(f or "")
    return False, f"unknown check kind {kind!r}"


def check_tool(tool: dict) -> dict:
    """A module found only in a side venv counts for optional tools and is `elsewhere` for the others."""
    elsewhere = ""
    for c in tool["check"]:
        ok, where = check_one(c)
        if ok and " in .venv" in where and tool.get("tier") != "optional":
            elsewhere = elsewhere or where
        elif ok:
            return {"id": tool["id"], "present": True, "where": where}
    return {"id": tool["id"], "present": False, "where": "", "elsewhere": elsewhere}


def check_services(m: dict) -> list:
    out = []
    for s in m.get("services", []):
        env = s.get("env", [])
        found = [e for e in env if os.environ.get(e)]
        ok = len(found) == len(env) if s.get("env_all") else bool(found)
        out.append({"id": s["id"], "name": s["name"], "env": env, "configured": bool(env) and ok,
                    "connector": s.get("connector"), "stations": s["stations"], "env_all": bool(s.get("env_all"))})
    return out


def station_verdicts(m: dict | None = None, present: dict | None = None) -> dict:
    m = m or load()
    present = present if present is not None else {t["id"]: check_tool(t)["present"] for t in m["tools"]}
    services, out = check_services(m), {}
    for sid, label in m["stations"].items():
        ids = {tier: [t["id"] for t in m["tools"] if sid in t["stations"] and t["tier"] == tier] for tier in TIERS}
        miss_req = [i for i in ids["required"] if not present.get(i)]
        miss_rec = [i for i in ids["recommended"] if not present.get(i)]
        out[sid] = {"ar": label["ar"], "ready": not miss_req,
                    "level": "not-ready" if miss_req else ("full" if not miss_rec else "basic"),
                    "required": ids["required"], "missing_required": miss_req, "missing_recommended": miss_rec,
                    "optional_present": [i for i in ids["optional"] if present.get(i)],
                    "services_configured": [s["id"] for s in services if sid in s["stations"] and s["configured"]]}
    return out


def check_all(tier: str = "all", manifest: dict | None = None) -> dict:
    m = manifest or load()
    results = {t["id"]: check_tool(t) for t in m["tools"]}
    tools = [{**results[t["id"]], "name": t["name"], "tier": t["tier"], "stations": t["stations"],
              "purpose_ar": t["purpose"]["ar"], "breaks_without": t.get("breaks_without", "")}
             for t in m["tools"] if t["tier"] in tiers_for(tier)]
    present = {i: r["present"] for i, r in results.items()}
    missing = [t["id"] for t in m["tools"] if t["tier"] == "required" and not present[t["id"]]]
    return {"schema": "kosif.dm.doctor.v1", "tier": tier, "tools": tools, "services": check_services(m),
            "stations": station_verdicts(m, present), "missing_required": missing, "ready": not missing,
            "python": sys.executable, "platform": sys.platform}


def _needs_closure(m: dict, ids: list) -> list:
    by, seen, visiting = {t["id"]: t for t in m["tools"]}, [], set()

    def add(i):
        if i in seen or i in visiting or i not in by:
            return
        visiting.add(i)
        for d in by[i].get("needs", []):
            add(d)
        seen.append(i)
    for i in ids:
        add(i)
    return seen


def install_plan(os_name: str, tier: str = "recommended", everything: bool = False, manifest: dict | None = None,
                 python: str | None = None) -> list:
    if os_name not in OSES:
        raise ValueError(f"--os must be one of {OSES}")
    m = manifest or load()
    by = {t["id"]: t for t in m["tools"]}
    want = [t["id"] for t in m["tools"] if t["tier"] in tiers_for(tier) and (everything or not check_tool(t)["present"])]
    ids = [i for i in _needs_closure(m, want) if everything or not check_tool(by[i])["present"]]
    py_cmd = {"linux": "python3", "macos": "python3", "windows": "py", "ashell": "python3"}[os_name]
    if python and os_name != "ashell":
        py_cmd = f'& "{python}"' if os_name == "windows" else f'"{python}"'
    pip_cmd = "pip install" if os_name == "ashell" else f"{py_cmd} -m pip install"
    sysp = {"apt": [], "brew": [], "cask": [], "winget": [], "choco": []}
    pips, npms, pre, post, notes, fetches = [], [], [], [], [], []
    for i in ids:
        t, ins = by[i], by[i].get("install", {})
        osd = ins.get(os_name, {})
        if t.get("download"):
            fetches.append(f"{py_cmd} -m engines.dragon_montage tool doctor fetch {t['id']}")
        if os_name == "ashell":
            if osd.get("builtin"):
                notes.append(f"# {t['name']}: موجود في a-Shell")
            elif osd.get("cmd"):
                pre += osd["cmd"]
            else:
                notes.append(f"# {t['name']}: {osd.get('note') or 'مش متاح على a-Shell (اشتغل بيه على الكمبيوتر)'}")
            continue
        for k in sysp:
            sysp[k] += [x for x in osd.get(k, []) if x not in sysp[k]]
        pips += [x for x in ins.get("pip", []) if x not in pips]
        npms += [x for x in ins.get("npm", []) if x not in npms]
        pre += osd.get("cmd", [])
        post += ins.get("post", {}).get(os_name, [])
    lines = [f"# Dragon Montage install plan — {os_name} — tier={tier}" + (" (all)" if everything else " (missing only)"),
             "# شغّل الأوامر دي من فولدر الريبو. الـ doctor نفسه مبيثبتش حاجة."]
    if not ids:
        return lines + ["# كل حاجة متثبتة ✅"]
    if os_name == "linux" and sysp["apt"]:
        lines.append("sudo apt-get update && sudo apt-get install -y " + " ".join(sysp["apt"]))
    if os_name == "macos":
        lines += ["brew install " + " ".join(sysp["brew"])] if sysp["brew"] else []
        lines += ["brew install --cask " + " ".join(sysp["cask"])] if sysp["cask"] else []
    if os_name == "windows":
        lines += [f"winget install -e --id {w}" for w in sysp["winget"]]
        lines += ["# أو بـ Chocolatey: choco install -y " + " ".join(sysp["choco"])] if sysp["choco"] else []
    lines += pre
    if pips:
        lines.append(f"{pip_cmd} " + " ".join(f'"{p}"' if any(ch in p for ch in "<>=") else p for p in pips))
    if npms:
        lines.append("npm install " + " ".join(npms))
    return lines + post + fetches + notes


def print_report(rep: dict) -> None:
    mark = {True: "✅", False: "❌"}
    print("🐉 دكتور مونتاج التنين — الأدوات اللي على الجهاز ده\n")
    for tier in TIERS:
        for t in (t for t in rep["tools"] if t["tier"] == tier):
            print(f"{mark[t['present']]} {t['name'][:34]:<34} {TIER_AR[tier]:<7} {t['purpose_ar']}")
            if not t["present"] and t.get("elsewhere"):
                print(f"   ↳ متثبتة في venv تاني ({t['elsewhere']}) — شغّل المونتاج بالـ python بتاعه")
            elif not t["present"] and tier != "optional":
                print(f"   ↳ من غيرها: {t['breaks_without']}")
    print("\n🔑 خدمات مدفوعة/مفاتيح (مش تثبيت):")
    for s in rep["services"]:
        st = ("✅ متظبط" if s["configured"] else f"🔌 بيشتغل من {s['connector']}" if s["connector"] and not s["env"]
              else "➖ مش متظبط: " + (" و " if s["env_all"] else " أو ").join(s["env"]))
        print(f"  {s['name']:<18} {st}")
    lvl = {"full": "🟢 جاهزة كاملة", "basic": "🟡 جاهزة (ناقصها حاجات مهمة)", "not-ready": "🔴 مش جاهزة"}
    print("\n🎬 المحطات:")
    for sid, v in rep["stations"].items():
        extra = (" — ناقص: " + ", ".join(v["missing_required"]) if v["missing_required"] else
                 " — يفضّل: " + ", ".join(v["missing_recommended"]) if v["missing_recommended"] else "")
        print(f"  {sid:<9} {v['ar']:<24} {lvl[v['level']]}{extra}")
    print("\n" + ("✅ الحكم: النظام جاهز يشتغل." if rep["ready"] else "❌ الحكم: مش جاهز. ناقص: " + ", ".join(rep["missing_required"])))


def main(argv=None) -> int:
    C.utf8_stdio()
    ap = argparse.ArgumentParser(prog="dragon_montage doctor", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd")
    d = sub.add_parser("doctor")
    d.add_argument("--json", action="store_true")
    d.add_argument("--tier", choices=["required", "recommended", "all"], default="all")
    p = sub.add_parser("install-plan")
    p.add_argument("--os", dest="os_name", choices=OSES, required=True)
    p.add_argument("--tier", choices=["required", "recommended", "all"], default="recommended")
    p.add_argument("--all", action="store_true")
    p.add_argument("--python")
    f = sub.add_parser("fetch")
    f.add_argument("tool_id")
    f.add_argument("--force", action="store_true")
    for x in (d, p, f):
        x.add_argument("--manifest", type=Path, default=MANIFEST)
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0].startswith("-"):
        argv = ["doctor", *argv]
    a = ap.parse_args(argv)
    m = load(a.manifest)
    if a.cmd == "fetch":
        try:
            print(f"✅ {a.tool_id} → {fetch(a.tool_id, a.force, m)}")
            return 0
        except (ValueError, RuntimeError) as e:
            print(f"❌ {e}", file=sys.stderr)
            return 1
    if a.cmd == "install-plan":
        print("\n".join(install_plan(a.os_name, a.tier, a.all, m, a.python)))
        return 0
    rep = check_all(a.tier, m)
    print(json.dumps(rep, ensure_ascii=False, indent=2)) if a.json else print_report(rep)
    return 0 if rep["ready"] else 1
