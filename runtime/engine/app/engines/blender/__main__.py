"""python -m engines.blender doctor | run SCRIPT.py [--blend f.blend] [-- args] | code "bpy code" | render f.blend OUT [opts] | demo OUT"""
import argparse, json, sys
from . import exe, version, run, run_code, render, demo


def main(argv=None):
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(prog="engines.blender")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("doctor")
    r = sub.add_parser("run"); r.add_argument("script"); r.add_argument("--blend"); r.add_argument("rest", nargs=argparse.REMAINDER)
    c = sub.add_parser("code"); c.add_argument("code"); c.add_argument("--blend")
    rd = sub.add_parser("render"); rd.add_argument("blend"); rd.add_argument("out")
    for k in ("frame", "start", "end", "samples", "fps"):
        rd.add_argument(f"--{k}", type=int)
    rd.add_argument("--engine"); rd.add_argument("--res")
    d = sub.add_parser("demo"); d.add_argument("out"); d.add_argument("--frames", type=int, default=48); d.add_argument("--res", default="540x960")
    a = ap.parse_args(argv)
    if a.cmd == "doctor":
        print(json.dumps({"blender": exe(), "version": version()}, ensure_ascii=False))
    elif a.cmd == "run":
        rest = a.rest[1:] if a.rest[:1] == ["--"] else a.rest
        print(json.dumps(run(a.script, a.blend, rest)["results"], ensure_ascii=False))
    elif a.cmd == "code":
        print(json.dumps(run_code(a.code, a.blend)["results"], ensure_ascii=False))
    elif a.cmd == "render":
        print(json.dumps(render(a.blend, a.out, a.frame, a.start, a.end, a.engine, a.samples, a.res, a.fps), ensure_ascii=False))
    elif a.cmd == "demo":
        print(json.dumps(demo(a.out, a.frames, a.res), ensure_ascii=False))


if __name__ == "__main__":
    main()
