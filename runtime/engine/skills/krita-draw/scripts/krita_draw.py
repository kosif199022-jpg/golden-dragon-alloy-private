"""krita_draw.py - draw with code through the real Krita (headless, via kritarunner).

    python -X utf8 krita_draw.py doctor
    python -X utf8 krita_draw.py render scene.json [--out-dir DIR] [--timeout 300] [--keep]
    python -X utf8 krita_draw.py layers file.kra           # list layers of a .kra, top -> bottom (no Krita needed)
    python -X utf8 krita_draw.py info [--out FILE]         # ask Krita for filters+config keys, presets, gradients
                                                           # (default FILE: references/krita_live_info.json in the skill)

scene.json  ->  real layered .kra (+ png/jpg/...) built by Krita itself.
See references/scene_format.md for the full format. Prints one JSON summary on stdout.
Exit codes: 0 ok, 2 bad scene, 3 Krita not found, 4 Krita crashed/timed out, 5 export failed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNNER_MODULE = "claude_krita_job"


# ------------------------------------------------------------------ discovery
def find_krita():
    cands = [os.environ.get("KRITA_BIN")]
    for base in (os.environ.get("ProgramFiles", r"C:\Program Files"), os.environ.get("ProgramFiles(x86)", ""),
                 os.environ.get("LOCALAPPDATA", "") + r"\Programs"):
        if base:
            cands += [base + r"\Krita (x64)\bin", base + r"\Krita\bin"]
    for c in cands:
        if c and Path(c, "kritarunner.exe").exists():
            return Path(c)
    w = shutil.which("kritarunner")
    return Path(w).parent if w else None


def runner_dir():
    # Found by tracing kritarunner with Frida: its app name is "kritarunner", so it imports
    # scripts from %APPDATA%\kritarunner\pykrita (NOT %APPDATA%\krita\pykrita, NOT PYTHONPATH).
    return Path(os.environ["APPDATA"]) / "kritarunner" / "pykrita"


def install_runner():
    d = runner_dir()
    d.mkdir(parents=True, exist_ok=True)
    src = (HERE / "krita_job.py").read_bytes()
    dst = d / (RUNNER_MODULE + ".py")
    if not dst.exists() or hashlib.sha256(dst.read_bytes()).digest() != hashlib.sha256(src).digest():
        dst.write_bytes(src)
        shutil.rmtree(d / "__pycache__", ignore_errors=True)
    return dst


def ascii_ok(p: str) -> bool:
    try:
        p.encode("latin-1")
        return True
    except UnicodeEncodeError:
        return False


# ------------------------------------------------------------------ job prep
def prepare(scene: dict, scene_dir: Path, job: Path):
    """Resolve paths, stage inputs under the ASCII job dir, render brush layers."""
    cv = scene.setdefault("canvas", {})
    if not scene.get("base"):
        if not cv.get("width") or not cv.get("height"):
            raise ValueError("canvas.width and canvas.height are required (or give 'base')")
    staged = {}

    def stage(p):
        src = (scene_dir / p).resolve() if not os.path.isabs(p) else Path(p)
        if not src.exists():
            raise FileNotFoundError(str(src))
        if str(src) in staged:
            return staged[str(src)]
        dst = job / "in" / ("f%02d%s" % (len(staged), src.suffix.lower()))
        dst.parent.mkdir(exist_ok=True)
        shutil.copy2(src, dst)
        staged[str(src)] = str(dst)
        return str(dst)

    if scene.get("base"):
        scene["base"] = stage(scene["base"])
        if not cv.get("width"):
            cv["width"], cv["height"] = kra_size(Path(scene["base"]))

    W, H = int(cv["width"]), int(cv["height"])
    brush_n = [0]

    def walk(layers):
        for L in layers:
            t = L.get("type", "paint")
            if t == "group":
                walk(L.get("layers", []))
            elif t == "brush":
                from brush import render_strokes, save_png
                t0 = time.time()
                img = render_strokes(W, H, L.get("strokes", []), seed=int(L.get("seed", 7)))
                out = job / "in" / ("brush%02d.png" % brush_n[0])
                out.parent.mkdir(exist_ok=True)
                save_png(img, out)
                brush_n[0] += 1
                L["type"] = "image"
                L["file"] = str(out)
                L["_brush_seconds"] = round(time.time() - t0, 2)
                L.pop("strokes", None)
            elif t in ("image", "svg", "file_layer") and L.get("file"):
                L["file"] = stage(L["file"])
    walk(scene.get("layers", []))

    if scene.get("python"):
        scene["python"] = stage(scene["python"])

    # outputs: Krita writes into the job dir, we move them to the real (maybe Arabic) paths
    final = {}
    outs = scene.setdefault("output", {})
    for fmt in ("png", "jpg", "webp", "tif", "psd", "kra"):
        if outs.get(fmt):
            real = Path(outs[fmt])
            if not real.is_absolute():
                real = (scene_dir / real).resolve()
            final[fmt] = real
            outs[fmt] = str(job / ("out." + fmt))
    has_anim = any(str(L.get("name", "")).startswith("__claude_anim_f") for L in scene.get("layers", []))
    for fmt in ("mp4", "gif"):  # made on the host by ffmpeg from exported frames
        if outs.get(fmt):
            if not has_anim:
                raise ValueError("output.%s needs an 'animation' layer in the scene" % fmt)
            real = Path(outs.pop(fmt))
            final[fmt] = real if real.is_absolute() else (scene_dir / real).resolve()
    if not final:
        raise ValueError("scene.output needs at least one of png/jpg/webp/tif/psd/kra")
    for p in [scene.get("base")] + [str(v) for v in outs.values() if isinstance(v, str)]:
        if p and not ascii_ok(p):
            raise RuntimeError("internal: non-latin1 path leaked into job: " + p)
    return final


def kra_size(path: Path):
    import xml.etree.ElementTree as ET
    with zipfile.ZipFile(path) as z:
        root = ET.fromstring(z.read("maindoc.xml"))
    img = next((e for e in root.iter() if e.tag.split("}")[-1] == "IMAGE"), None)
    if img is None:
        raise ValueError("maindoc.xml has no IMAGE element")
    return int(img.get("width")), int(img.get("height"))


def kra_layers(path: Path):
    import xml.etree.ElementTree as ET
    with zipfile.ZipFile(path) as z:
        root = ET.fromstring(z.read("maindoc.xml"))
    out = []

    def walk(el, depth):
        for c in el:
            tag = c.tag.split("}")[-1]
            if tag == "layer" or tag == "mask":
                out.append({"depth": depth, "name": c.get("name"), "nodetype": c.get("nodetype"),
                            "opacity": c.get("opacity"), "blend": c.get("compositeop"), "visible": c.get("visible")})
            walk(c, depth + (1 if tag == "layer" else 0))
    walk(root, 0)
    return out


# ------------------------------------------------------------------ run
FINISH_GRACE = 15  # seconds Krita gets to quit on its own after krita_job.py wrote its final result


def _job_finished(job: Path) -> bool:
    """krita_job.py writes "seconds" into result.json only as its very last step (after export + close)."""
    try:
        return "seconds" in json.loads((job / "result.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False


def _watch(cmd, job: Path, timeout: int, env=None, flags=0, grace=FINISH_GRACE):
    """Run cmd and wait for it. Measured 2026-11-13: kritarunner sometimes stays alive after the job is
    done and every file is saved, and the host then sat out the whole --timeout (300 s for a 16 s
    render). Once the finish marker is written, Krita gets `grace` seconds, then it is closed."""
    t0 = time.time()
    log = job / "krita_stderr.txt"
    with open(log, "wb") as fe:
        p = subprocess.Popen(cmd, cwd=str(job), env=env, stdout=subprocess.DEVNULL, stderr=fe, creationflags=flags)
        done_at = None
        while True:
            try:
                code = p.wait(timeout=0.5)
                break
            except subprocess.TimeoutExpired:
                pass
            now = time.time()
            if done_at is None and _job_finished(job):
                done_at = now
            if done_at is not None and now - done_at > grace:
                p.kill()
                p.wait()
                code = "finished; closed after %ss grace" % grace
                break
            if now - t0 > timeout:
                p.kill()
                p.wait()
                code = "timeout"
                break
    err = log.read_text(encoding="utf-8", errors="replace")
    log.unlink(missing_ok=True)
    return code, err, round(time.time() - t0, 1)


def run_krita(kbin: Path, job: Path, timeout: int):
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    env.pop("PYTHONHOME", None)
    flags = 0x08000000 if os.name == "nt" else 0  # CREATE_NO_WINDOW
    code, err, secs = _watch([str(kbin / "kritarunner.exe"), "-s", RUNNER_MODULE, str(job)], job, timeout, env, flags)
    noise = ("Fontconfig error", "platform independent libraries", "added to PYTHONPATH")
    err = "\n".join(l for l in err.splitlines() if l.strip() and not any(n in l for n in noise))
    return code, err[-3000:], secs


def run_pass(kbin: Path, job: Path, payload: dict, timeout: int):
    (job / "job.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    (job / "result.json").unlink(missing_ok=True)
    code, err, secs = run_krita(kbin, job, timeout)
    res_file = job / "result.json"
    res = json.loads(res_file.read_text(encoding="utf-8")) if res_file.exists() else {"steps": []}
    return code, err, secs, res


def expand_animation(scene: dict):
    """One {"type": "animation"} layer -> N frame layers (raster) at the same stack position.
    They are merged into one animated layer with real keyframes after pass 1 (kra_animate.py)."""
    layers = scene.get("layers", [])
    idx = [i for i, L in enumerate(layers) if L.get("type") == "animation"]
    if not idx:
        return None
    if len(idx) > 1:
        raise ValueError("only one 'animation' layer per scene (put more motion inside its frames)")
    i = idx[0]
    A = layers[i]
    frames = A.get("frames") or []
    if len(frames) < 2:
        raise ValueError("animation needs at least 2 frames")
    common = {k: A[k] for k in ("opacity", "blend", "visible", "x", "y") if k in A}
    specs, names = [], []
    for j, F in enumerate(frames):
        t = F.get("type", "brush")
        if t not in ("brush", "image", "svg", "group"):
            raise ValueError("animation frame %d: type must be brush, image, svg or group" % j)
        s = dict(F)
        s["type"] = t
        s["name"] = "__claude_anim_f%03d" % j
        for k2, v in common.items():
            s.setdefault(k2, v)
        if t in ("svg", "group"):  # flattened to one raster frame inside Krita
            s["rasterize"] = True
        s.pop("filters", None)  # masks are not carried into keyframes
        specs.append(s)
        names.append(s["name"])
    layers[i:i + 1] = specs
    holds = [int(F.get("hold", A.get("hold", 1))) for F in frames]
    return {"name": A.get("name", "animation"), "frames": names, "holds": holds,
            "fps": int(A.get("fps", 12)), "poster": int(A.get("poster", 0))}


def encode_video(job: Path, fps: int, final: dict):
    """frames/fr_%04d.png -> out.mp4 / out.gif with ffmpeg (only the formats asked for)."""
    ff = shutil.which("ffmpeg")
    made = {}
    if not ff or not (job / "frames").exists():
        return {"error": "ffmpeg not found" if not ff else "no frames exported"}
    pattern = str(job / "frames" / "fr_%04d.png")
    if "mp4" in final:
        r = subprocess.run([ff, "-y", "-loglevel", "error", "-framerate", str(fps), "-i", pattern,
                            "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2,format=yuv420p", "-c:v", "libx264",
                            "-crf", "18", "-preset", "medium", "-movflags", "+faststart", str(job / "out.mp4")],
                           capture_output=True, text=True)
        made["mp4"] = r.returncode == 0 or r.stderr[-300:]
    if "gif" in final:
        r = subprocess.run([ff, "-y", "-loglevel", "error", "-framerate", str(fps), "-i", pattern, "-vf",
                            "split[a][b];[a]palettegen=reserve_transparent=1[p];[b][p]paletteuse=dither=sierra2_4a",
                            "-loop", "0", str(job / "out.gif")], capture_output=True, text=True)
        made["gif"] = r.returncode == 0 or r.stderr[-300:]
    made["frames"] = len(list((job / "frames").glob("fr_*.png")))
    return made


def cmd_render(a):
    scene_path = Path(a.scene).resolve()
    try:
        scene = json.loads(scene_path.read_text(encoding="utf-8-sig"))
    except Exception as e:  # noqa: BLE001
        print(json.dumps({"ok": False, "error": "bad scene json: %r" % e}, ensure_ascii=False))
        return 2
    kbin = find_krita()
    if not kbin:
        print(json.dumps({"ok": False, "error": "Krita not found (set KRITA_BIN to the folder with kritarunner.exe)"}))
        return 3
    root = Path(os.environ.get("TEMP", "C:\\Temp")) / "krita_draw"
    if not ascii_ok(str(root)):
        root = Path("C:/Users/Public/krita_draw")
    job = root / (time.strftime("job_%Y%m%d_%H%M%S_") + str(os.getpid()))
    job.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(HERE))
    try:
        if a.out_dir:  # redirect relative outputs
            od = Path(a.out_dir).resolve()
            for k, v in scene.get("output", {}).items():
                if isinstance(v, str) and k in ("png", "jpg", "webp", "tif", "psd", "kra", "mp4", "gif") and not os.path.isabs(v):
                    scene["output"][k] = str(od / v)
        anim = expand_animation(scene)
        final = prepare(scene, scene_path.parent, job)
    except Exception as e:  # noqa: BLE001
        print(json.dumps({"ok": False, "error": repr(e)}, ensure_ascii=False))
        return 2
    install_runner()
    secs_total = 0.0
    anim_info = None
    if anim:
        # pass 1: frames as separate paint layers -> pass1.kra
        user_out = scene["output"]
        scene["output"] = {"kra": str(job / "pass1.kra")}
        code, err, secs, res = run_pass(kbin, job, scene, a.timeout)
        secs_total += secs
        (job / "result_pass1.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
        if (job / "out.kra").exists():
            (job / "out.kra").replace(job / "pass1.kra")
        if not (job / "pass1.kra").exists():
            res.setdefault("fatal", "pass 1 (building frame layers) failed")
        else:
            # host: frame layers -> one animated layer with real keyframes
            from kra_animate import animate
            anim_info = animate(str(job / "pass1.kra"), str(job / "anim.kra"), anim["frames"], anim["name"],
                                anim["fps"], anim["holds"])
            total = anim_info["frames_total"]
            pass2 = {"base": str(job / "anim.kra"), "canvas": {"dpi": scene["canvas"].get("dpi", 72)}, "layers": [],
                     "anim_export": {"fps": anim["fps"], "end": total - 1, "dir": str(job / "frames"),
                                     "poster": anim["poster"]},
                     "output": user_out}
            code, err, secs, res2 = run_pass(kbin, job, pass2, a.timeout)
            secs_total += secs
            res2["layers"] = res.get("layers")
            res2["svg_shapes"] = res.get("svg_shapes")
            res = res2
            anim_info["video"] = encode_video(job, anim["fps"], final)
    else:
        code, err, secs, res = run_pass(kbin, job, scene, a.timeout)
        secs_total += secs
    summary = {"ok": False, "krita_exit": code, "seconds": round(secs_total, 1), "job_dir": str(job),
               "krita_version": res.get("krita_version"), "canvas": res.get("canvas"),
               "layers": res.get("layers"), "svg_shapes": res.get("svg_shapes"), "outputs": {}}
    if anim_info:
        summary["animation"] = anim_info
    if res.get("fatal"):
        summary["error"] = res["fatal"]
        summary["trace"] = res.get("fatal_trace")
    running = [s["step"] for s in res.get("steps", []) if s.get("status") == "running"]
    if running:
        summary["crashed_in_step"] = running[-1]
    if code == "timeout":
        summary["error"] = "Krita timed out after %ss" % a.timeout
    if anim and anim_info is None:
        summary["error"] = summary.get("error") or "animation pass 1 failed (see job_dir/result_pass1.json)"
    if err:
        summary["stderr_tail"] = err[-800:]
    moved = 0
    for fmt, real in final.items():
        src = job / ("out." + fmt)
        if src.exists() and src.stat().st_size > 0:
            real.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, real)
            summary["outputs"][fmt] = {"path": str(real), "bytes": real.stat().st_size}
            moved += 1
    summary["ok"] = moved == len(final) and not res.get("fatal")
    if not a.keep and summary["ok"]:
        shutil.rmtree(job, ignore_errors=True)
        summary.pop("job_dir")
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    if summary["ok"]:
        return 0
    return 4 if (running or code not in (0,)) else 5


def cmd_doctor(a):
    kbin = find_krita()
    info = {"krita_bin": str(kbin) if kbin else None, "runner_dir": str(runner_dir())}
    if kbin:
        try:  # kritarunner --version only prints its name; krita.exe prints the real version
            v = subprocess.run([str(kbin / "krita.exe"), "--version"], capture_output=True, timeout=60)
            info["krita_version"] = (v.stdout or v.stderr).decode("utf-8", "replace").strip()[-80:]
        except Exception as e:  # noqa: BLE001
            info["krita_version"] = repr(e)
        info["runner_installed"] = str(install_runner())
    try:
        import numpy, PIL  # noqa: F401
        info["numpy_pillow"] = True
    except Exception:  # noqa: BLE001
        info["numpy_pillow"] = False
    info["ok"] = bool(kbin) and info["numpy_pillow"]
    print(json.dumps(info, ensure_ascii=False, indent=1))
    return 0 if info["ok"] else 3


def cmd_info(a):
    """Ask Krita itself: filters + their config keys, brush presets, gradients, patterns."""
    kbin = find_krita()
    if not kbin:
        print(json.dumps({"ok": False, "error": "Krita not found"}))
        return 3
    job = Path(os.environ.get("TEMP", "C:\\Temp")) / "krita_draw" / ("info_" + str(os.getpid()))
    job.mkdir(parents=True, exist_ok=True)
    (job / "job.json").write_text(json.dumps({"introspect": True}), encoding="utf-8")
    install_runner()
    code, err, secs = run_krita(kbin, job, a.timeout)
    res = json.loads((job / "result.json").read_text(encoding="utf-8")) if (job / "result.json").exists() else {}
    info = res.get("info") or {}
    out = Path(a.out) if a.out else HERE.parent / "references" / "krita_live_info.json"
    if info:
        out.write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")
    shutil.rmtree(job, ignore_errors=True)
    print(json.dumps({"ok": bool(info), "seconds": secs, "saved": str(out) if info else None,
                      "filters": len(info.get("filters", {})), "brush_presets": len(info.get("brush_presets", [])),
                      "gradients": len(info.get("gradients", [])), "error": err[-400:] if not info else None},
                     ensure_ascii=False, indent=1))
    return 0 if info else 4


def cmd_layers(a):
    print(json.dumps({"size": kra_size(Path(a.kra)), "layers": kra_layers(Path(a.kra))}, ensure_ascii=False, indent=1))
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("render")
    r.add_argument("scene")
    r.add_argument("--out-dir")
    r.add_argument("--timeout", type=int, default=300)
    r.add_argument("--keep", action="store_true", help="keep the job dir for debugging")
    r.set_defaults(fn=cmd_render)
    d = sub.add_parser("doctor")
    d.set_defaults(fn=cmd_doctor)
    i = sub.add_parser("info")
    i.add_argument("--out")
    i.add_argument("--timeout", type=int, default=180)
    i.set_defaults(fn=cmd_info)
    l = sub.add_parser("layers")
    l.add_argument("kra")
    l.set_defaults(fn=cmd_layers)
    a = ap.parse_args()
    sys.exit(a.fn(a))


if __name__ == "__main__":
    main()
