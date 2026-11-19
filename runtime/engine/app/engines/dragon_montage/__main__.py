"""python -m engines.dragon_montage <subcommand>

  plan "<task>" --clip a.mp4 … [--animatic]       stations 1-5 + preview; stops for the owner's yes
  go --job DIR [--preview] [--rounds 3]           after the owner says yes: render, review, fix
  edit "<task>" --clip a.mp4 [--clip b.mp4] [--music m.mp3] [--job DIR] [--platform reel] [--seconds 45]
       [--style ID] [--invent] [--reference ref.mp4] [--rounds 3] [--preview] [--no-transcribe] [--stock "query"]
  doctor [--json] | doctor install-plan --os windows | doctor fetch <tool-id>
  station <name> [args…]    one station: analyze brief concepts taste direct render review generate mimic
                            stock-search stock-fetch storyboard doctor
  tool <module> [args…]     a module's full CLI: analyze think taste edl direct render review storyboard generate
                            mimic stock doctor
"""
from __future__ import annotations

import argparse
import importlib
import json
import sys

from . import common as C

STATIONS = {"doctor": ("doctor", ["doctor"]), "analyze": ("analyze", []), "brief": ("think", ["brief"]),
            "concepts": ("think", ["concepts"]), "taste": ("taste", ["pick"]), "direct": ("direct", ["direct"]),
            "render": ("render", ["render"]), "review": ("review", ["review"]), "generate": ("generate", ["gaps"]),
            "mimic": ("mimic", ["mimic"]), "stock-search": ("stock", ["search"]), "stock-fetch": ("stock", ["fetch"]),
            "storyboard": ("storyboard", ["storyboard"])}
TOOLS = ("analyze", "think", "taste", "edl", "direct", "render", "review", "storyboard", "generate", "mimic", "stock", "doctor")


def _module_main(name: str, argv: list) -> int:
    return importlib.import_module(f".{name}", __package__).main(argv) or 0


def _edit_args(p) -> None:
    p.add_argument("task")
    p.add_argument("--clip", action="append")
    p.add_argument("--stock", help="search open-licence sites for this (English) query and add the best clips")
    p.add_argument("--stock-top", type=int, default=0, help=argparse.SUPPRESS)
    p.add_argument("--stock-ids", help="site:id,... picked after looking at the stock search results")
    p.add_argument("--stock-commercial", action="store_true")
    p.add_argument("--music")
    p.add_argument("--job")
    p.add_argument("--platform")
    p.add_argument("--seconds", type=float)
    p.add_argument("--style")
    p.add_argument("--invent", action="store_true")
    p.add_argument("--reference", help="copy a reference video's pace (mean shot length) and transitions; its colours only "
                                        "when the request says «نفس الألوان»")
    p.add_argument("--reference-exact", action="store_true", help="cut at the reference's own cut times")
    p.add_argument("--rounds", type=int, default=3)
    p.add_argument("--preview", action="store_true")
    p.add_argument("--no-transcribe", action="store_true")


def _kw(a) -> dict:
    return {"music": a.music, "job": a.job, "platform": a.platform, "seconds": a.seconds, "style": a.style, "invent": a.invent,
            "reference": a.reference, "rounds": a.rounds, "preview": a.preview, "no_transcribe": a.no_transcribe, "stock": a.stock,
            "stock_top": a.stock_top, "stock_commercial": a.stock_commercial, "stock_ids": a.stock_ids,
            "reference_exact": a.reference_exact}


def main(argv=None) -> int:
    C.utf8_stdio()
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ["station"] and len(argv) > 1 and argv[1] in STATIONS:
        mod, sub = STATIONS[argv[1]]
        return _module_main(mod, sub + argv[2:])
    if argv[:1] == ["tool"] and len(argv) > 1 and argv[1] in TOOLS:
        return _module_main(argv[1], argv[2:])
    if argv[:1] == ["doctor"]:
        return _module_main("doctor", argv[1:])
    p = argparse.ArgumentParser(prog="python -m engines.dragon_montage", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("edit", help="all stations in one go, no approval stop («نفّذ مباشرة»)")
    pl = sub.add_parser("plan", help="stations 1-5 + preview; stops for the owner's yes")
    pl.add_argument("--animatic", action="store_true", help="also a fast low-res draft video of the plan")
    for x in (e, pl):
        _edit_args(x)
    g = sub.add_parser("go", help="the owner approved the preview: render, review, fix")
    g.add_argument("--job", required=True)
    g.add_argument("--rounds", type=int)
    g.add_argument("--preview", action="store_true", default=None)
    sub.add_parser("doctor", help="which tools are installed / missing")
    sub.add_parser("station", help="run one station").add_argument("name", choices=sorted(STATIONS))
    sub.add_parser("tool", help="a module's full CLI").add_argument("module", choices=TOOLS)
    a = p.parse_args(argv)
    from . import pipeline
    if a.cmd == "go":
        out = pipeline.go(a.job, a.rounds, a.preview)
    elif a.cmd == "plan":
        out = pipeline.plan(a.task, a.clip, animatic=a.animatic, **_kw(a))
    else:
        out = pipeline.edit(a.task, a.clip, **_kw(a))
    print(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
