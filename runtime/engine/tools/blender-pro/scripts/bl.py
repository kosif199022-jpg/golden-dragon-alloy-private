#!/usr/bin/env python3
"""blender-pro CLI - drive Blender headless from normal Python.

  python bl.py run recipe.json [--out DIR] [--preview] [-v]
  python bl.py exec script.py [--out DIR] [--preview] [-- script args...]
  python bl.py info                  Blender version, engines, GPU, Arabic shaping, ops summary
  python bl.py ops [--module M] [--json]   full op catalog (all bpylib modules incl. draw/video)
  python bl.py inspect file.blend    scene objects/materials/frames as JSON
  python bl.py thumb file.blend [--out x.png] [--frame N] [--engine EEVEE]

Always ends with one JSON line: {"ok": true|false, "outputs": [...], ...}; exit code 0/1.
Blender is found via $BLENDER, PATH ('blender'), or the default Windows install path.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
RUNNER = os.path.join(HERE, "runner.py")
DEFAULT_PATHS = [
    r"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe",
    r"C:\Program Files\Blender Foundation\Blender 5.1\blender.exe",
    r"C:\Program Files\Blender Foundation\Blender 5.0\blender.exe",
    "/Applications/Blender.app/Contents/MacOS/Blender",
]

for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def find_blender():
    for c in (os.environ.get("BLENDER"), shutil.which("blender")):
        if c and os.path.exists(c):
            return c
    for c in DEFAULT_PATHS:
        if os.path.exists(c):
            return c
    sys.exit(json.dumps({"ok": False, "error": "Blender not found: set BLENDER env var or add blender to PATH"}))


def ffprobe(path):
    exe = shutil.which("ffprobe")
    if not exe or not os.path.exists(path):
        return None
    r = subprocess.run([exe, "-v", "error", "-select_streams", "v:0", "-show_entries",
                        "stream=codec_name,width,height,r_frame_rate,nb_frames,pix_fmt:format=duration,size",
                        "-of", "json", path], capture_output=True, text=True)
    if r.returncode != 0:
        return {"error": r.stderr.strip()[-300:]}
    d = json.loads(r.stdout)
    s = (d.get("streams") or [{}])[0]
    f = d.get("format", {})
    return {"codec": s.get("codec_name"), "size": [s.get("width"), s.get("height")], "fps": s.get("r_frame_rate"),
            "frames": s.get("nb_frames"), "pix_fmt": s.get("pix_fmt"),
            "duration": float(f.get("duration", 0) or 0), "bytes": int(f.get("size", 0) or 0)}


def run_blender(runner_args, blend=None, verbose=False, timeout=None):
    cmd = [find_blender(), "-b"]
    if blend:
        cmd.append(os.path.abspath(blend))
    cmd += ["--factory-startup", "--python-exit-code", "1", "--python", RUNNER, "--"] + runner_args
    env = dict(os.environ)
    env["BLPRO_SYSPY"] = sys.executable
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    t0 = time.time()
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env)
    result, tail, last_frame_note = None, [], 0.0
    try:
        for raw in proc.stdout:
            line = raw.decode("utf-8", errors="replace").rstrip("\r\n")
            tail.append(line)
            tail = tail[-60:]
            if line.startswith("BLPRO_RESULT "):
                try:
                    result = json.loads(line[len("BLPRO_RESULT "):])
                except json.JSONDecodeError:
                    pass
                continue
            if verbose:
                print(line, flush=True)
                continue
            if line.startswith("BLPRO_OUTPUT "):
                print("  -> " + line[len("BLPRO_OUTPUT "):], flush=True)
            elif line.startswith("[bpylib:") or "Error" in line or "Traceback" in line or line.startswith("  File "):
                print(line, flush=True)
            elif ("Fra:" in line or "| Rendering" in line or "Saved:" in line) and time.time() - last_frame_note > 5:
                print("  .. " + line.strip()[:140], flush=True)
                last_frame_note = time.time()
            if timeout and time.time() - t0 > timeout:
                proc.kill()
                break
        proc.wait()
    except KeyboardInterrupt:
        proc.kill()
        raise
    if result is None:
        result = {"ok": False, "error": {"stage": "blender", "message": f"Blender exited with code {proc.returncode} "
                                         "without a result", "log_tail": "\n".join(tail[-40:])}}
    result.setdefault("outputs", [])
    result["blender_exit"] = proc.returncode
    result["wall_seconds"] = round(time.time() - t0, 1)
    for o in result["outputs"]:
        if o.get("type") == "video":
            o["probe"] = ffprobe(o["path"])
        elif o.get("path") and os.path.exists(o["path"]):
            o["bytes"] = os.path.getsize(o["path"])
    return result


def finish(result, compact_keys=("steps",)):
    if result.get("error"):
        err = result["error"]
        print("\nFAILED: " + json.dumps({k: v for k, v in err.items() if k != "traceback"}, ensure_ascii=False,
                                        default=str)[:2000], file=sys.stderr)
        if err.get("traceback"):
            print(err["traceback"][-2500:], file=sys.stderr)
    out = {k: v for k, v in result.items() if k not in compact_keys}
    if out.get("error"):
        out["error"] = {k: v for k, v in out["error"].items() if k != "traceback"}
    print(json.dumps(out, ensure_ascii=False, default=str))
    sys.exit(0 if result.get("ok") else 1)


def main():
    argv = sys.argv[1:]
    script_args = []
    if "--" in argv:
        i = argv.index("--")
        argv, script_args = argv[:i], argv[i + 1:]
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("run", help="run a JSON recipe")
    p.add_argument("recipe")
    p.add_argument("--out")
    p.add_argument("--preview", action="store_true")
    p.add_argument("-v", "--verbose", action="store_true")
    p.add_argument("--timeout", type=float)
    p = sub.add_parser("exec", help="run a raw bpy script with bpylib importable")
    p.add_argument("script")
    p.add_argument("--out")
    p.add_argument("--preview", action="store_true")
    p.add_argument("--blend", help="open this .blend first")
    p.add_argument("-v", "--verbose", action="store_true")
    p = sub.add_parser("info")
    p = sub.add_parser("ops")
    p.add_argument("--module")
    p.add_argument("--json", action="store_true")
    p = sub.add_parser("inspect")
    p.add_argument("blend")
    p = sub.add_parser("thumb")
    p.add_argument("blend")
    p.add_argument("--out")
    p.add_argument("--frame", type=int)
    p.add_argument("--engine", default=None)
    a = ap.parse_args(argv)

    if a.cmd == "run":
        ra = ["--mode", "run", "--recipe", os.path.abspath(a.recipe)]
        if a.out:
            ra += ["--out", os.path.abspath(a.out)]
        if a.preview:
            ra.append("--preview")
        finish(run_blender(ra, verbose=a.verbose, timeout=a.timeout))
    elif a.cmd == "exec":
        ra = ["--mode", "exec", "--script", os.path.abspath(a.script), "--script-args", json.dumps(script_args)]
        if a.out:
            ra += ["--out", os.path.abspath(a.out)]
        if a.preview:
            ra.append("--preview")
        finish(run_blender(ra, blend=a.blend, verbose=a.verbose))
    elif a.cmd == "info":
        finish(run_blender(["--mode", "info"]))
    elif a.cmd == "ops":
        res = run_blender(["--mode", "ops"])
        if not res.get("ok"):
            finish(res)
        cat = res["catalog"]
        if a.module:
            cat = {a.module: cat.get(a.module, {})}
        if a.json:
            print(json.dumps({"ok": True, "catalog": cat, "modules_failed": res.get("modules_failed")},
                             ensure_ascii=False, indent=1))
            return
        for mod in sorted(cat):
            print(f"\n## {mod}  ({len(cat[mod])} ops)")
            for name, info in sorted(cat[mod].items()):
                first = (info["doc"].splitlines() or [""])[0]
                print(f"- {name}{info['signature']}\n    {first}")
        if res.get("modules_failed"):
            print(f"\n(modules failed to import: {res['modules_failed']})")
        print(json.dumps({"ok": True, "modules": sorted(cat), "ops": sum(len(v) for v in cat.values())}))
    elif a.cmd == "inspect":
        res = run_blender(["--mode", "inspect"], blend=a.blend)
        finish(res)
    elif a.cmd == "thumb":
        out = os.path.abspath(a.out or os.path.splitext(os.path.abspath(a.blend))[0] + "_thumb.png")
        ra = ["--mode", "thumb", "--out", out]
        if a.frame is not None:
            ra += ["--frame", str(a.frame)]
        if a.engine:
            ra += ["--engine", a.engine]
        finish(run_blender(ra, blend=a.blend))


if __name__ == "__main__":
    main()
