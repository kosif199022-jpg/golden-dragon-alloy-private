"""Blender engine: run Blender 5.x headless from the Black Dragon — scripts, renders, turntables — with no MCP server.

Any bpy code written by a Blender skill (the creative repos in ~/dragon-repos/creative, which normally send code
through an MCP "execute_blender_code" tool) can be saved as a .py file and run here with `run`.
"""
import json, os, shutil, subprocess, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPTS = HERE / "scripts"


def exe() -> str:
    """blender.exe: $BLENDER, PATH, then the newest folder under Program Files\\Blender Foundation."""
    for c in (os.environ.get("BLENDER"), shutil.which("blender")):
        if c and Path(c).exists():
            return c
    base = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Blender Foundation"
    hits = sorted(base.glob("Blender */blender.exe"), key=lambda p: [int(x) for x in p.parent.name.split()[-1].split(".") if x.isdigit()])
    if hits:
        return str(hits[-1])
    raise FileNotFoundError("Blender not found: winget install -e --id BlenderFoundation.Blender, or set BLENDER")


def version() -> str:
    out = subprocess.run([exe(), "-b", "--factory-startup", "--version"], capture_output=True, text=True, encoding="utf-8", errors="replace")
    return next((l.strip() for l in out.stdout.splitlines() if l.startswith("Blender")), "unknown")


def run(script, blend=None, args=(), timeout=3600, factory=True):
    """Run a bpy script headless. Script args come after `--` (read them with sys.argv[sys.argv.index('--')+1:]).
    Lines the script prints as `@@{json}` are collected and returned as `results`."""
    cmd = [exe(), "-b"]
    if factory and not blend:
        cmd.append("--factory-startup")
    if blend:
        cmd.append(str(blend))
    cmd += ["--python-exit-code", "1", "--python", str(script), "--", *map(str, args)]
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout, env=env)
    results = [json.loads(l[2:]) for l in p.stdout.splitlines() if l.startswith("@@")]
    if p.returncode:
        raise RuntimeError(f"blender failed ({p.returncode}):\n{(p.stderr or p.stdout)[-1500:]}")
    return {"ok": True, "results": results, "log": p.stdout[-2000:]}


def run_code(code: str, blend=None, args=(), timeout=3600):
    """Run bpy code given as text (what an MCP skill would have sent to execute_blender_code)."""
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write(code)
    try:
        return run(f.name, blend, args, timeout)
    finally:
        os.unlink(f.name)


def render(blend, out, frame=None, start=None, end=None, engine=None, samples=None, res=None, fps=None, timeout=7200):
    """Render a .blend: one frame -> PNG, or a frame range -> MP4 (H.264, via the engines ffmpeg standard)."""
    a = ["--out", out]
    for k, v in (("frame", frame), ("start", start), ("end", end), ("engine", engine), ("samples", samples), ("res", res), ("fps", fps)):
        if v is not None:
            a += [f"--{k}", v]
    r = run(SCRIPTS / "render.py", blend, a, timeout, factory=False)
    return r["results"][-1] if r["results"] else r


def demo(out, frames=48, res="540x960", engine="BLENDER_EEVEE_NEXT"):
    """Self-contained proof scene (no .blend needed): bevelled gold cube, three-point light, push-in camera."""
    r = run(SCRIPTS / "demo_scene.py", None, ["--out", out, "--frames", frames, "--res", res, "--engine", engine])
    return r["results"][-1] if r["results"] else r
