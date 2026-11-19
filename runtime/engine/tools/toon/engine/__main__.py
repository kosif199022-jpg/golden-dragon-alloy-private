"""python -m engine (from tools/toon) setup | styles | image IN OUT [--style 3d] | video IN OUT [--style 3d] [--fps 12] [--max-side 720] [--seconds N]"""
import argparse, json, sys
from pathlib import Path
from . import MODELS, STYLES, image, setup, video

MODELS_VENV = MODELS / "venv"


def main(argv=None):
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(prog="toon-engine", description="cartoon / anime look for videos and photos (open-source models, CPU)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("setup")
    sub.add_parser("styles")
    for name in ("image", "video"):
        p = sub.add_parser(name)
        p.add_argument("src"); p.add_argument("dst")
        p.add_argument("--style", default="3d", choices=list(STYLES))
        p.add_argument("--max-side", type=int, default=720 if name == "video" else 1280)
        if name == "video":
            p.add_argument("--fps", type=float, default=12, help="animation frame rate; 0 keeps the source rate")
            p.add_argument("--seconds", type=float, help="only the first N seconds (quick preview)")
            p.add_argument("--no-deflicker", action="store_true")
    a = ap.parse_args(argv)
    # ai3d needs newer diffusers/transformers than the rest of the machine: they live in an isolated venv
    venv_py = MODELS_VENV / "Scripts" / "python.exe"
    if getattr(a, "style", "") == "ai3d" and venv_py.exists() and Path(sys.executable).resolve() != venv_py.resolve():
        import subprocess
        root = Path(__file__).resolve().parents[1]   # tools/toon
        sys.exit(subprocess.call([str(venv_py), "-m", "engine", *(argv if argv is not None else sys.argv[1:])], cwd=str(root)))
    if a.cmd == "setup":
        print(json.dumps(setup(), ensure_ascii=False, indent=1))
    elif a.cmd == "styles":
        for k, v in STYLES.items():
            print(f"{k:8} {v['name']}")
    elif a.cmd == "image":
        print(json.dumps(image(a.src, a.dst, a.style, a.max_side), ensure_ascii=False))
    else:
        print(json.dumps(video(a.src, a.dst, a.style, a.fps, a.max_side, a.seconds, not a.no_deflicker), ensure_ascii=False))


if __name__ == "__main__":
    main()
