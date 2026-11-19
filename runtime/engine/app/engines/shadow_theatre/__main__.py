"""python -m engines.shadow_theatre <command>

  doctor                                            numpy / Pillow / ffmpeg present?
  library                                           poses, costumes, cycles, props, backdrops, iris, techniques
  analyze <video> --out <dir>                       cuts, lit-screen palette, silhouette share, contact sheet
  check <scene.json>                                timing + style grammar (exit 1 with reasons)
  stills <scene.json> --out <dir> [--times 1,4.5,9] [--preview]
  render <scene.json> --out <film.mp4> [--preview] [--no-audio] [--keep-wav] [--force]
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

import numpy as np
from PIL import Image

from . import E, TECHNIQUES, check_spec, load_spec, render_film, stills, techniques_used


def cmd_doctor(_):
    rows = {"python": sys.version.split()[0], "numpy": np.__version__, "Pillow": Image.__version__,
            "ffmpeg": shutil.which("ffmpeg") or "MISSING", "ffprobe": shutil.which("ffprobe") or "MISSING"}
    for k, v in rows.items():
        print(f"{k:15} {v}")
    ok = rows["ffmpeg"] != "MISSING"
    print("status         " + ("ready: check, stills, render, analyze" if ok else "stills/check only: install ffmpeg to render"))
    return 0 if ok else 1


def cmd_library(_):
    lib = E.LIB
    print("poses:     " + ", ".join(sorted(E.POSES)))
    print("costumes:  " + ", ".join(sorted(E.COSTUMES)))
    print("cycles:    " + ", ".join(lib["cycles"]))
    print("props:     " + ", ".join(lib["props"]))
    print("iris:      " + ", ".join(lib["iris"]))
    print("backdrops: " + ", ".join(E.BACKDROPS))
    print("easing:    " + ", ".join(E.EASES))
    print("techniques:")
    for k, v in TECHNIQUES.items():
        print(f"  {k:12} {v}")
    return 0


def cmd_analyze(a):
    from .analyze import analyze
    print(json.dumps(analyze(a.video, a.out, a.samples, a.threshold), indent=2))
    print(f"wrote {Path(a.out) / 'analysis.json'} and {Path(a.out) / 'contact.jpg'}")
    return 0


def _fail(errs):
    for e in errs:
        print("FAIL", e)
    return 1


def cmd_check(a):
    spec = load_spec(a.scene)
    errs = check_spec(spec)
    if errs:
        return _fail(errs)
    print(f"PASS {len(spec['scenes'])} scenes, {spec['duration']}s, techniques: {', '.join(techniques_used(spec))}")
    return 0


def cmd_stills(a):
    times = [float(x) for x in a.times.split(",")] if a.times else None
    for p in stills(load_spec(a.scene), a.out, times, a.preview):
        print(p)
    return 0


def cmd_render(a):
    spec = load_spec(a.scene)
    errs = check_spec(spec)
    if errs and not a.force:
        _fail(errs)
        print("fix the spec or pass --force")
        return 1
    res = render_film(spec, a.out, a.preview, not a.no_audio, a.keep_wav, progress=lambda m: print(m, flush=True))
    print(json.dumps(res))
    return 0


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(prog="python -m engines.shadow_theatre", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("doctor")
    sub.add_parser("library")
    s = sub.add_parser("analyze"); s.add_argument("video"); s.add_argument("--out", required=True)
    s.add_argument("--samples", type=int, default=60); s.add_argument("--threshold", type=float, default=0.35)
    s = sub.add_parser("check"); s.add_argument("scene")
    s = sub.add_parser("stills"); s.add_argument("scene"); s.add_argument("--out", required=True)
    s.add_argument("--times"); s.add_argument("--preview", action="store_true")
    s = sub.add_parser("render"); s.add_argument("scene"); s.add_argument("--out", required=True)
    s.add_argument("--preview", action="store_true", help="half size, 15 fps")
    s.add_argument("--no-audio", action="store_true"); s.add_argument("--keep-wav", action="store_true")
    s.add_argument("--force", action="store_true")
    a = p.parse_args(argv)
    return {"doctor": cmd_doctor, "library": cmd_library, "analyze": cmd_analyze, "check": cmd_check,
            "stills": cmd_stills, "render": cmd_render}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
