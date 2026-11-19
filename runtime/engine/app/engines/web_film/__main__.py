"""python -m engines.web_film <command>

Page film (one HTML page per film, a scene per shot):
  plan "<prompt>" --out film.plan.json [--duration 15] [--ratio 9:16] [--require "..."]...
  scaffold film.plan.json --out film.html
  check film.plan.json [--html film.html] [--json]               exits 1 on any failure
  render film.html --out film.mp4 [--plan film.plan.json | --width W --height H] [--fps 30] [--audio a.m4a] [--stills 0.5,2]

World film (one world, one continuous camera):
  world example --out JOB/world.plan.json
  world beats PLAN.json [--out beats.md]
  world check PLAN.json [--json]
  world build PLAN.json --out JOB/film.html
  world review PLAN.json
  world render PLAN.json --out film.mp4 [--audio voice.m4a]      build + render at the plan's format
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import page, world
from .render import render_page


def _write(path, text):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(text, encoding="utf-8")


def cmd_plan(a):
    _write(a.out, json.dumps(page.default_plan(a.prompt, a.duration, a.ratio, a.require), ensure_ascii=False, indent=2))
    print(f"plan written: {a.out} (fill concept, visual_language, shot text, motion, covers)")
    return 0


def cmd_scaffold(a):
    print(f"page written: {page.write_scaffold(a.plan, a.out)}")
    return 0


def cmd_check(a):
    plan = world.load(a.plan)
    res = page.check(plan, Path(a.html).read_text(encoding="utf-8") if a.html else None)
    if a.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
    else:
        print("\n".join(res["errors"]) if res["errors"] else "PASS")
    return 0 if res["ok"] else 1


def cmd_render(a):
    w, h, fps = a.width, a.height, a.fps
    if a.plan:
        p = world.load(a.plan)
        w, h, fps = w or p["width"], h or p["height"], fps or p.get("fps", 30)
    if not (w and h):
        raise SystemExit("give --plan or --width and --height")
    stills = [float(x) for x in a.stills.split(",")] if a.stills else None
    print(render_page(a.html, a.out, width=w, height=h, fps=fps or 30, audio=a.audio, stills=stills, stills_dir=a.stills_dir))
    return 0


def cmd_world(a):
    if a.wcmd == "example":
        _write(a.out, json.dumps(world.example_plan(), ensure_ascii=False, indent=1))
        print(a.out)
        return 0
    plan = world.load(a.plan)
    if a.wcmd == "beats":
        md = world.beats_md(plan)
        if a.out:
            Path(a.out).write_text(md, encoding="utf-8")
        print(md)
    elif a.wcmd == "check":
        errs, stats = world.check(plan, Path(a.plan))
        if a.json:
            print(json.dumps({"ok": not errs, "errors": errs, "stats": stats}, ensure_ascii=False, indent=1))
        else:
            for e in errs:
                print("FAIL", e)
            print(json.dumps(stats, ensure_ascii=False))
            print("OK" if not errs else f"{len(errs)} problem(s)")
        return 1 if errs else 0
    elif a.wcmd == "build":
        print(world.build(a.plan, a.out))
    elif a.wcmd == "review":
        print(json.dumps(world.review_times(plan)))
    elif a.wcmd == "render":
        html = world.build(a.plan, Path(a.out).with_suffix(".html"))
        f = plan["format"]
        print(render_page(html, a.out, width=f["width"], height=f["height"], fps=f.get("fps", 30), audio=a.audio))
    return 0


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(prog="python -m engines.web_film", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("plan"); p.add_argument("prompt"); p.add_argument("--out", required=True)
    p.add_argument("--duration", type=float, default=15.0); p.add_argument("--ratio", default="9:16")
    p.add_argument("--require", action="append", default=[])
    p = sub.add_parser("scaffold"); p.add_argument("plan"); p.add_argument("--out", required=True)
    p = sub.add_parser("check"); p.add_argument("plan"); p.add_argument("--html"); p.add_argument("--json", action="store_true")
    p = sub.add_parser("render"); p.add_argument("html"); p.add_argument("--out"); p.add_argument("--plan")
    p.add_argument("--width", type=int); p.add_argument("--height", type=int); p.add_argument("--fps", type=float)
    p.add_argument("--audio"); p.add_argument("--stills"); p.add_argument("--stills-dir")
    w = sub.add_parser("world").add_subparsers(dest="wcmd", required=True)
    p = w.add_parser("example"); p.add_argument("--out", required=True)
    p = w.add_parser("beats"); p.add_argument("plan"); p.add_argument("--out")
    p = w.add_parser("check"); p.add_argument("plan"); p.add_argument("--json", action="store_true")
    p = w.add_parser("build"); p.add_argument("plan"); p.add_argument("--out", required=True)
    p = w.add_parser("review"); p.add_argument("plan")
    p = w.add_parser("render"); p.add_argument("plan"); p.add_argument("--out", required=True); p.add_argument("--audio")
    a = ap.parse_args(argv)
    if a.cmd == "render" and not (a.out or a.stills):
        ap.error("render needs --out or --stills")
    return {"plan": cmd_plan, "scaffold": cmd_scaffold, "check": cmd_check, "render": cmd_render, "world": cmd_world}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
