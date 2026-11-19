#!/usr/bin/env python3
"""Black Dragon v10.16: toon -- cartoon / anime look for photos and videos, local and free (open-source models, CPU).

    python scripts/dragon.py tool toon doctor
    python scripts/dragon.py tool toon styles
    python scripts/dragon.py tool toon image IN.jpg OUT.jpg --style 3d
    python scripts/dragon.py tool toon video IN.mp4 OUT.mp4 --style hayao --seconds 3     (3-second preview FIRST)
    python scripts/dragon.py tool toon video IN.mp4 OUT.mp4 --style hayao                  (then the full video)
    python scripts/dragon.py tool toon setup [--yes]     (dry run: what is missing; never downloads, never spends money)

Styles: 3d (DCT-Net + face detection), ai3d (SD-Turbo img2img, ~20 s/frame: photos and short clips only),
hayao / shinkai (AnimeGANv3, non-commercial licence), paint (portrait painting).
Never overwrites an output or an original. Separate from tools/cartoon (different tool, untouched).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
SCHEMA = "black-dragon.toon.v1"
MODELS = Path(os.environ.get("BD_TOON_MODELS", Path.home() / "dragon-models" / "toon"))
VENV_PY = MODELS / "venv" / "Scripts" / "python.exe"
STYLES = {
    "3d": ("dct3d_cartoon_bg.onnx", "cartoon 3D (DCT-Net) + faces via YuNet", ["face_detection_yunet_2023mar.onnx", "dct3d_alpha.jpg"]),
    "ai3d": ("sd-turbo/model_index.json", "3D animated-film redraw (SD-Turbo, ~20 s/frame on CPU)", []),
    "hayao": ("AnimeGANv3_Hayao_36.onnx", "hand-painted anime (AnimeGANv3 Hayao, non-commercial)", []),
    "shinkai": ("AnimeGANv3_Shinkai_37.onnx", "bright cinematic anime (AnimeGANv3 Shinkai, non-commercial)", []),
    "paint": ("face_paint_512_v2_0.onnx", "painted portrait (AnimeGANv2 face_paint_512_v2, MIT)", []),
}
VIDEO_EXT = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"}
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def out(obj):
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def have_module(name, py=None):
    """importable in the current interpreter, or (py given) installed in that venv -- checked on disk, no slow torch import."""
    if py is None:
        import importlib.util
        try:
            return importlib.util.find_spec(name) is not None
        except (ImportError, ValueError):
            return False
    site = Path(py).parent.parent / "Lib" / "site-packages"
    return site.is_dir() and ((site / name).is_dir() or (site / (name + ".py")).exists())


def model_ok(rel):
    return (MODELS / rel).is_file()


def venv_sees_system():
    """the venv was created with --system-site-packages, so torch from the main interpreter is visible inside it."""
    try:
        return "include-system-site-packages = true" in (VENV_PY.parent.parent / "pyvenv.cfg").read_text(encoding="utf-8").lower()
    except OSError:
        return False


def ai3d_python():
    if have_module("diffusers") and have_module("torch"):
        return sys.executable
    if VENV_PY.is_file() and have_module("diffusers", VENV_PY) and (have_module("torch", VENV_PY) or (venv_sees_system() and have_module("torch"))):
        return str(VENV_PY)
    return None


def doctor():
    styles = {}
    py3d = ai3d_python()
    for k, (f, desc, extra) in STYLES.items():
        missing = [x for x in [f, *extra] if not model_ok(x)]
        styles[k] = {"ready": not missing and (k != "ai3d" or py3d is not None), "missing": missing, "desc": desc}
    mods = {m: have_module(m) for m in ("onnxruntime", "cv2", "PIL", "numpy", "torch", "diffusers")}
    venv_mods = {m: have_module(m, VENV_PY) for m in ("torch", "diffusers")} if VENV_PY.is_file() else {}
    return {"schema": SCHEMA, "models_dir": str(MODELS), "venv_python": str(VENV_PY), "venv_python_present": VENV_PY.is_file(),
            "ffmpeg": shutil.which("ffmpeg"), "ffprobe": shutil.which("ffprobe"), "python_modules": mods, "venv_modules": venv_mods,
            "ai3d_python": py3d, "styles": styles, "ready_styles": [k for k, v in styles.items() if v["ready"]]}


def guard(src, dst, kind):
    src, dst = Path(src), Path(dst)
    if not src.is_file():
        sys.exit(f"input not found: {src}")
    if src.suffix.lower() not in (VIDEO_EXT if kind == "video" else IMAGE_EXT):
        sys.exit(f"unsupported {kind} input type: {src.suffix}")
    if dst.exists() or dst.is_symlink():
        sys.exit(f"refusing to overwrite existing output: {dst}")
    if dst.resolve() == src.resolve():
        sys.exit("output must differ from the input")
    if dst.suffix.lower() not in ((".mp4", ".mov", ".mkv") if kind == "video" else (".jpg", ".jpeg", ".png", ".webp")):
        sys.exit(f"unsupported output extension: {dst.suffix}")
    return src.resolve(), dst.resolve()


def probe(path):
    ff = shutil.which("ffprobe")
    if not ff:
        return None
    r = subprocess.run([ff, "-v", "error", "-show_entries", "stream=codec_type,codec_name,width,height,r_frame_rate,duration",
                        "-of", "json", str(path)], capture_output=True, text=True, encoding="utf-8")
    try:
        return json.loads(r.stdout).get("streams")
    except ValueError:
        return None


def run_engine(args, style):
    d = doctor()["styles"][style]
    if d["missing"]:
        sys.exit(f"style '{style}' not ready, missing in {MODELS}: {d['missing']} (run: tool toon doctor)")
    py = sys.executable
    if style == "ai3d":
        py = ai3d_python()
        if not py:
            sys.exit("ai3d needs torch + diffusers (current python lacks them and no venv found at " + str(VENV_PY) + ")")
    env = dict(os.environ, PYTHONIOENCODING="utf-8", BD_TOON_MODELS=str(MODELS))
    r = subprocess.run([py, "-m", "engine", *args], cwd=str(HERE), env=env, capture_output=True, text=True, encoding="utf-8")
    if r.returncode:
        sys.exit("toon engine failed:\n" + (r.stderr or r.stdout)[-1500:])
    return r.stdout.strip()


def convert(kind, a):
    src, dst = guard(a.src, a.dst, kind)
    dst.parent.mkdir(parents=True, exist_ok=True)
    args = [kind, str(src), str(dst), "--style", a.style, "--max-side", str(a.max_side)]
    if kind == "video":
        args += ["--fps", str(a.fps)]
        if a.seconds:
            args += ["--seconds", str(a.seconds)]
    stdout = run_engine(args, a.style)
    if not dst.is_file() or dst.stat().st_size == 0:
        sys.exit("engine finished but output is missing/empty")
    last = stdout.splitlines()[-1] if stdout else "{}"
    try:
        eng = json.loads(last)
    except ValueError:
        eng = {"raw": last}
    out({"schema": SCHEMA, "ok": True, "kind": kind, "style": a.style, "input": str(src), "output": str(dst),
         "bytes": dst.stat().st_size, "sha256": sha(dst), "streams": probe(dst), "engine": eng,
         "note": "original untouched" + ("; this was a preview, run without --seconds for the full video" if kind == "video" and a.seconds else "")})


def setup(a):
    plan = []
    for k, (f, desc, extra) in STYLES.items():
        for x in [f, *extra]:
            if not model_ok(x):
                plan.append({"style": k, "missing": str(MODELS / x)})
    res = {"schema": SCHEMA, "dry_run": not a.yes, "models_dir": str(MODELS), "missing": plan,
           "would_download": "nothing automatically: models are free open-source files (AnimeGANv3, DCT-Net, YuNet, face_paint_512_v2, "
                             "stabilityai/sd-turbo ~2 GB) to be placed in models_dir by the owner; this tool never downloads or spends money",
           "would_install": ("nothing (no pip installs); ai3d uses the existing venv" if VENV_PY.is_file()
                             else "ai3d needs a venv with torch+diffusers at " + str(VENV_PY))}
    if a.yes:
        sys.path.insert(0, str(HERE))
        os.environ["BD_TOON_MODELS"] = str(MODELS)
        import engine
        res["local_status"] = engine.setup()      # only converts an existing DCT-Net .pb to .onnx if tf2onnx is present; no network
    out(res)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="dragon.py tool toon", description="Cartoon / anime look for photos and videos (local, free, CPU). "
                                 "TIP: always try a 3-second preview first: video IN OUT --style hayao --seconds 3")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("doctor", help="models/venv/ffmpeg/modules status as JSON")
    sub.add_parser("styles", help="list styles as JSON")
    for name in ("image", "video"):
        p = sub.add_parser(name, help=f"stylise a {name}; refuses to overwrite", description=f"Stylise a {name}. Never overwrites an existing output or the original." + (" Preview first: --seconds 3." if name == "video" else ""))
        p.add_argument("src")
        p.add_argument("dst")
        p.add_argument("--style", default="3d", choices=list(STYLES))
        p.add_argument("--max-side", type=int, default=720 if name == "video" else 1280)
        if name == "video":
            p.add_argument("--fps", type=float, default=12, help="animation frame rate (12 = on twos); 0 keeps source")
            p.add_argument("--seconds", type=float, help="only the first N seconds: use --seconds 3 as a preview before the full video")
    s = sub.add_parser("setup", help="DRY RUN: what is missing; --yes only runs the local free .pb->.onnx conversion, never downloads or pays")
    s.add_argument("--yes", action="store_true")
    a = ap.parse_args(argv)
    if a.cmd == "doctor":
        out(doctor())
    elif a.cmd == "styles":
        d = doctor()["styles"]
        out({"schema": SCHEMA, "styles": {k: {"desc": v[1], "ready": d[k]["ready"]} for k, v in STYLES.items()}})
    elif a.cmd == "setup":
        setup(a)
    else:
        convert(a.cmd, a)


if __name__ == "__main__":
    main()
