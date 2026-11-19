#!/usr/bin/env python3
"""hypit-run: run the real Hypit (hypit-ai/hypit) from Red Dragon, locally and for free.

Hypit's code is NOT copied here (its licence is Apache-2.0 with conditions). This script only
installs the published npm package into its own folder, points it at a browser that already exists,
and fetches upstream examples at run time.

  hypit_rd.py doctor                      node / ffmpeg / browser / installed version
  hypit_rd.py setup [--version 0.3.2]     npm install @hypit/hypit into ~/.hypit-rd (no install scripts)
  hypit_rd.py example <name> <dir>        copy an upstream example into <dir> as a standalone project
  hypit_rd.py check <dir> <file.svml>
  hypit_rd.py plan <dir> <file.svrun>     shows Providers and prices BEFORE anything runs
  hypit_rd.py render <dir> <file.svrun> --to out.mp4 [--output final.video] [--allow-paid]
  hypit_rd.py cli <dir> -- <hypit args>   any other hypit command inside the project
  hypit_rd.py selftest                    offline checks (no network)
"""
import argparse, json, os, re, shutil, subprocess, sys, tempfile
from pathlib import Path
from hypit_guard import assess_plan, cli_is_inspection_only

DEFAULT_VERSION = "0.3.2"
HOME = Path(os.environ.get("HYPIT_RD_HOME", Path.home() / ".hypit-rd"))
REPO = "https://github.com/hypit-ai/hypit.git"
WIN = os.name == "nt"
NPM = "npm.cmd" if WIN else "npm"
LOCAL_PRICE = "local, no Provider charge"


def run(cmd, cwd=None, timeout=900, check=True):
    p = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, encoding="utf-8", errors="replace", timeout=timeout)
    if check and p.returncode != 0:
        sys.stderr.write(p.stdout[-3000:] + p.stderr[-3000:])
        sys.exit(p.returncode or 1)
    return p


def node_major():
    try:
        v = run(["node", "-v"], check=False).stdout.strip().lstrip("v")
        a, b = (int(x) for x in v.split(".")[:2])
        return v, (a, b) >= (22, 15)
    except Exception:
        return None, False


def find_chrome():
    """A Chromium that already exists, so Hypit does not download its own."""
    env = os.environ.get("HYPIT_CHROME")
    if env and Path(env).exists():
        return env
    cands = []
    for root in ("/opt/pw-browsers", str(Path.home() / ".cache/ms-playwright"),
                 str(Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright")):
        r = Path(root)
        if r.is_dir():
            cands += sorted(r.glob("chromium_headless_shell-*/chrome-headless-shell-*/chrome-headless-shell*"), reverse=True)
            cands += sorted(r.glob("chromium-*/chrome-*/chrome*"), reverse=True)
    cands += [Path(p) for p in (r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                                "/usr/bin/chromium", "/usr/bin/google-chrome", "/usr/bin/chromium-browser") ]
    for c in cands:
        if c.is_file() and os.access(c, os.X_OK) and not c.name.endswith((".real", ".pak", "_handler", "_sandbox", "-wrapper")):
            return str(c)
    return None


def hypit_bin(project=None):
    for base in ([Path(project)] if project else []) + [HOME]:
        b = base / "node_modules" / ".bin" / ("hypit.cmd" if WIN else "hypit")
        if b.exists():
            return str(b)
    return None


def cmd_doctor(_):
    v, ok = node_major()
    out = {"node": v, "node_ok": ok, "npm": bool(shutil.which(NPM)), "ffmpeg": shutil.which("ffmpeg"),
           "chrome": find_chrome(), "hypit": hypit_bin(), "home": str(HOME)}
    if out["hypit"]:
        out["hypit_version"] = run([out["hypit"], "--version"], check=False).stdout.strip()
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0 if ok and out["ffmpeg"] and out["chrome"] else 1


def cmd_setup(a):
    v, ok = node_major()
    if not ok:
        sys.exit(f"محتاج Node 22.15+ (الموجود: {v})")
    HOME.mkdir(parents=True, exist_ok=True)
    run([NPM, "install", "--prefix", str(HOME), "--ignore-scripts", "--no-fund", "--no-audit", f"@hypit/hypit@{a.version}"])
    b = hypit_bin()
    print("✅", run([b, "--version"]).stdout.strip(), "→", b)


def _patch_example(dst, version):
    """Turn a monorepo example into a standalone project: workspace:* → published versions."""
    pkgs = []
    for pj in sorted((dst / "packages").glob("*/package.json")) if (dst / "packages").is_dir() else []:
        d = json.loads(pj.read_text(encoding="utf-8"))
        for sec in ("dependencies", "devDependencies"):
            for k, val in list(d.get(sec, {}).items()):
                if isinstance(val, str) and val.startswith("workspace:"):
                    d[sec][k] = version if k == "@hypit/hypit" else (_npm_latest(k) or val.replace("workspace:", ""))
        pj.write_text(json.dumps(d, indent=2) + "\n", encoding="utf-8")
        pkgs.append((d["name"], pj.parent))
    root = dst / "package.json"
    d = json.loads(root.read_text(encoding="utf-8")) if root.exists() else {"name": dst.name, "private": True, "type": "module"}
    d.setdefault("hypit", {})["project"] = True
    deps = d.setdefault("dependencies", {})
    deps["@hypit/hypit"] = version
    used = " ".join(p.read_text(encoding="utf-8", errors="replace") for p in dst.glob("*.svml"))
    if "@hypit/fontsource" in used:
        deps.setdefault("@hypit/fontsource", _npm_latest("@hypit/fontsource") or "*")
    for fam in set(re.findall(r'package="(@fontsource[^"]+)"', used)):
        deps.setdefault(fam, "*")
    for name, path in pkgs:
        deps[name] = "file:./" + path.relative_to(dst).as_posix()
    for sec in ("dependencies", "devDependencies"):
        for k, val in list(d.get(sec, {}).items()):
            if isinstance(val, str) and val.startswith("workspace:"):
                d[sec][k] = version if k == "@hypit/hypit" else (_npm_latest(k) or "*")
    root.write_text(json.dumps(d, indent=2) + "\n", encoding="utf-8")
    return pkgs


_LATEST = {}
def _npm_latest(name):
    if name not in _LATEST:
        p = run([NPM, "view", name, "version"], check=False, timeout=60)
        _LATEST[name] = ("^" + p.stdout.strip().splitlines()[-1]) if p.returncode == 0 and p.stdout.strip() else None
    return _LATEST[name]


def _set_chrome(dst):
    rt = dst / "hypit.runtime.json"
    chrome = find_chrome()
    if not rt.exists() or not chrome:
        return None
    d = json.loads(rt.read_text(encoding="utf-8"))
    for ep in d.get("endpoints", {}).values():
        if ep.get("use") == "@hypit/provider-html-local":
            ep.setdefault("config", {})["chromePath"] = chrome
    rt.write_text(json.dumps(d, indent=2) + "\n", encoding="utf-8")
    return chrome


def cmd_example(a):
    dst = Path(a.dir).resolve()
    if dst.exists() and any(dst.iterdir()):
        sys.exit(f"{dst} مش فاضي")
    with tempfile.TemporaryDirectory() as t:
        run(["git", "clone", "--depth", "1", "--filter=blob:none", "--sparse", REPO, t + "/h"], timeout=300)
        run(["git", "-C", t + "/h", "sparse-checkout", "set", f"examples/{a.name}"], timeout=300)
        src = Path(t) / "h" / "examples" / a.name
        if not src.is_dir():
            sys.exit(f"مفيش مثال اسمه {a.name}")
        commit = run(["git", "-C", t + "/h", "rev-parse", "HEAD"]).stdout.strip()
        shutil.copytree(src, dst, dirs_exist_ok=True)
    pkgs = _patch_example(dst, a.version)
    for _, p in pkgs:   # build project components (plain tsc, no install scripts)
        run([NPM, "install", "--ignore-scripts", "--no-fund", "--no-audit"], cwd=p)
        if (p / "tsconfig.json").exists():
            run([str(p / "node_modules" / ".bin" / ("tsc.cmd" if WIN else "tsc")), "-p", "tsconfig.json"], cwd=p)
        shutil.rmtree(p / "node_modules", ignore_errors=True)
    run([NPM, "install", "--ignore-scripts", "--install-links", "--no-fund", "--no-audit"], cwd=dst)
    chrome = _set_chrome(dst)
    (dst / "HYPIT_SOURCE.json").write_text(json.dumps({"repo": REPO, "example": a.name, "commit": commit,
        "license": "Apache-2.0 with conditions (see upstream LICENSE)", "chromePath": chrome}, indent=1), encoding="utf-8")
    print(f"✅ {a.name} → {dst} (commit {commit[:7]}, chrome: {chrome or 'مش لاقي'})")


def _hy(project, args, timeout=1800, check=True):
    b = hypit_bin(project) or sys.exit("hypit مش متثبت: hypit_rd.py setup")
    extra = ["--runtime", "hypit.runtime.json"] if (Path(project) / "hypit.runtime.json").exists() and args and args[0] in ("plan", "build", "pricing") else []
    return run([b] + args + extra + ["--project", str(Path(project).resolve())], cwd=project, timeout=timeout, check=check)


def paid_lines(plan_text):
    return assess_plan(plan_text).bad

def cmd_check(a):
    print(_hy(a.dir, ["check", a.file]).stdout)


def cmd_plan(a):
    p=_hy(a.dir,["plan",a.file],check=False)
    gate=assess_plan(p.stdout,p.returncode)
    print(p.stdout+p.stderr)
    if gate.errors:
        print("⛔ plan invalid: "+"; ".join(gate.errors))
        return 2
    if gate.bad:
        print("⛔ paid providers:\n  "+"\n  ".join(gate.bad))
        return 3
    print("✅ Local-only plan verified")
    return 0

def cmd_render(a):
    p=_hy(a.dir,["plan",a.file],check=False)
    gate=assess_plan(p.stdout,p.returncode)
    if gate.errors:
        print("⛔ plan failed/unknown; no build: "+"; ".join(gate.errors))
        return 2
    if gate.bad and not a.allow_paid:
        print("⛔ approval of these prices required first:\n  "+"\n  ".join(gate.bad))
        return 3
    out=str(Path(a.to).resolve())
    if Path(out).exists():
        print("⛔ refusing to overwrite "+out)
        return 2
    if gate.bad: print("⚠ --allow-paid specified; use only after user approved quoted prices.")
    b=_hy(a.dir,["build",a.file,"--follow"])
    m=re.search(r"Build\s+(bld_\S+)",b.stdout) or sys.exit(b.stdout)
    _hy(a.dir,["get",m.group(1),"--output",a.output,"--to",out])
    probe=run(["ffprobe","-v","error","-show_entries","stream=codec_name,width,height,r_frame_rate:format=duration",
              "-of","json",out],check=False).stdout if shutil.which("ffprobe") else "{}"
    print(json.dumps({"build":m.group(1),"out":out,"probe":json.loads(probe or "{}")},ensure_ascii=False,indent=1))

def cmd_cli(a):
    args=a.rest[1:] if a.rest[:1]==["--"] else a.rest
    if not cli_is_inspection_only(args):
        print("⛔ direct CLI is inspection-only; use gated hypit render for builds")
        return 3
    p=_hy(a.dir,args,check=False)
    print(p.stdout+p.stderr)
    return p.returncode

def cmd_selftest(_):
    ok = []
    sample = ("  @hypit/html-program#rasterize-visual\n    html.local (@hypit/provider-html-local)  ·  local, no Provider charge\n"
              "      ×1  width 540\n    hypihub (@hypit/provider-hypihub)  ·  $0.40 per request\n")
    ok.append(("paid_detect", paid_lines(sample) == ["hypihub (@hypit/provider-hypihub)  ·  $0.40 per request"]))
    ok.append(("free_plan", paid_lines(sample.split("    hypihub")[0]) == []))
    ok.append(("empty_plan_blocks", not assess_plan("").safe))
    ok.append(("build_cli_blocks", not cli_is_inspection_only(["build","x.svrun"])))
    with tempfile.TemporaryDirectory() as t:
        d = Path(t); (d / "packages/x").mkdir(parents=True)
        (d / "packages/x/package.json").write_text(json.dumps({"name": "@ex/x", "devDependencies": {"@hypit/hypit": "workspace:*"}}))
        (d / "a.svml").write_text('<fonts:Face package="@fontsource-variable/inter"/>')
        _LATEST["@hypit/fontsource"] = "^0.2.0"
        _patch_example(d, "0.3.2")
        r = json.loads((d / "package.json").read_text()); x = json.loads((d / "packages/x/package.json").read_text())
        ok.append(("patch_root", r["hypit"]["project"] is True and r["dependencies"]["@ex/x"] == "file:./packages/x"
                   and "@fontsource-variable/inter" in r["dependencies"]))
        ok.append(("patch_pkg", x["devDependencies"]["@hypit/hypit"] == "0.3.2"))
    good = all(v for _, v in ok)
    print(json.dumps({"ok": good, "checks": dict(ok)}, indent=1))
    return 0 if good else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("doctor"); sub.add_parser("selftest")
    s = sub.add_parser("setup"); s.add_argument("--version", default=DEFAULT_VERSION)
    s = sub.add_parser("example"); s.add_argument("name"); s.add_argument("dir"); s.add_argument("--version", default=DEFAULT_VERSION)
    for n in ("check", "plan"):
        s = sub.add_parser(n); s.add_argument("dir"); s.add_argument("file")
    s = sub.add_parser("render"); s.add_argument("dir"); s.add_argument("file"); s.add_argument("--to", required=True)
    s.add_argument("--output", default="final.video"); s.add_argument("--allow-paid", action="store_true")
    s = sub.add_parser("cli"); s.add_argument("dir"); s.add_argument("rest", nargs=argparse.REMAINDER)
    a = ap.parse_args()
    return globals()["cmd_" + a.cmd](a) or 0


if __name__ == "__main__":
    sys.exit(main())
