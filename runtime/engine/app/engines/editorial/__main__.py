"""python -m engines.editorial <command>

  doctor                                     ffmpeg / node / renderer present?
  example --out DIR                          example EDL + generated stand-in media
  check EDL.json [--json]                    timeline, sources, fx and type names, caption order (exit 1 on errors)
  build EDL.json --out page.html             self-contained seekable page (media copied / frames extracted next to it)
  render EDL.json --out film.mp4 [--audio a.m4a] [--stills 0.5,1.2]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import edit


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(prog="python -m engines.editorial", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("doctor")
    p = sub.add_parser("example"); p.add_argument("--out", required=True)
    p = sub.add_parser("check"); p.add_argument("edl"); p.add_argument("--json", action="store_true")
    p = sub.add_parser("build"); p.add_argument("edl"); p.add_argument("--out", required=True)
    p = sub.add_parser("render"); p.add_argument("edl"); p.add_argument("--out", required=True)
    p.add_argument("--audio"); p.add_argument("--stills")
    a = ap.parse_args(argv)
    if a.cmd == "doctor":
        rows = edit.doctor()
        for k, v in rows.items():
            print(f"{k:11} {v}")
        return 1 if "MISSING" in rows.values() else 0
    if a.cmd == "example":
        print(edit.example(a.out))
        return 0
    edl = edit.load(a.edl)
    if a.cmd == "check":
        res = edit.check(edl, Path(a.edl).parent)
        if a.json:
            print(json.dumps(res, ensure_ascii=False, indent=1))
        else:
            for e in res["errors"]:
                print("FAIL", e)
            print(json.dumps(res["stats"]))
            print("PASS" if res["ok"] else f"{len(res['errors'])} problem(s)")
        return 0 if res["ok"] else 1
    if a.cmd == "build":
        print(edit.build(a.edl, a.out))
        return 0
    res = edit.check(edl, Path(a.edl).parent)
    if not res["ok"]:
        for e in res["errors"]:
            print("FAIL", e)
        return 1
    stills = [float(x) for x in a.stills.split(",")] if a.stills else None
    out = edit.render(a.edl, a.out, stills=stills, audio=a.audio)
    print(json.dumps(edit.verify(out, edl)) if not stills else out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
