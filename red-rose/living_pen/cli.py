"""Approved, non-overwriting PNG export with a machine-readable receipt."""
import hashlib
import json
from pathlib import Path


def handle(args):
    if not args.approve_write:
        print(json.dumps({"ok":False,"error":"--approve-write required"}))
        return 3
    try:
        from .render import render_spec, png_bytes
        source, out = Path(args.spec), Path(args.out)
        if out.suffix.lower() != ".png":
            raise ValueError("output extension must be .png")
        if out.exists():
            raise FileExistsError(str(out))
        if source.stat().st_size > 2_000_000:
            raise ValueError("spec exceeds 2 MB")
        spec = json.loads(source.read_text(encoding="utf-8-sig"))
        image = render_spec(spec)
        data = png_bytes(image)
        with out.open("xb") as f:
            f.write(data)
        print(json.dumps({"ok":True,"output":str(out),"width":image.shape[1],
                          "height":image.shape[0],"sha256":hashlib.sha256(data).hexdigest()},
                         ensure_ascii=False))
        return 0
    except (ValueError, OSError, ImportError, TypeError) as exc:
        print(json.dumps({"ok":False,"error":str(exc)},ensure_ascii=False))
        return 1


def register(sub):
    p = sub.add_parser("pen", help="Living Pen Stage 1: deterministic reed nib drawing")
    actions = p.add_subparsers(dest="pen_action", required=True)
    stroke = actions.add_parser("stroke", help="render stroke JSON to PNG")
    stroke.add_argument("spec")
    stroke.add_argument("--out", required=True)
    stroke.add_argument("--approve-write", action="store_true")
    stroke.set_defaults(ext_func=handle)
