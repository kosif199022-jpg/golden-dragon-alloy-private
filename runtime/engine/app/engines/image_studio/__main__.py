"""python -m engines.image_studio <command> ...   (every command prints a measured JSON line)

  title OUT "النص" [--src img] [--size 1080x1920] [--font cairo] [--px N] [--color #fff] [--stroke 0] [--pos center|top|bottom|lower-third] [--glow #F5C04A] [--bg #0B0B0F]
  reframe SRC OUT [--size 1080x1920] [--mode blur|cover|contain] [--focus 0.5,0.4]
  grade SRC OUT [--look teal_orange] [--strength 1]
  cover SRC OUT "العنوان" [--sub "سطر صغير"] [--look warm_gold] [--size 1080x1920] [--font cairo]
  upscale SRC OUT [--scale 4] [--model ultrasharp-4x]
  cutout SRC OUT.png [--model isnet-general-use]
  sheet VIDEO OUT.jpg [--n 12] [--cols 4] [--width 360]
  looks | fonts | measure FILE
"""
import argparse, json, sys
from . import FONTS, RAQM, UPSCAYL_MODELS, cover, cutout, grade, looks, measure, reframe, sheet, title, upscale, upscayl_bin


def main(argv=None):
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(prog="engines.image_studio", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("title"); t.add_argument("out"); t.add_argument("text"); t.add_argument("--src"); t.add_argument("--size", default="1080x1920")
    t.add_argument("--font", default="cairo"); t.add_argument("--px", type=int); t.add_argument("--color", default="#FFFFFF")
    t.add_argument("--stroke", type=int, default=0); t.add_argument("--stroke-color", default="#000000"); t.add_argument("--pos", default="center")
    t.add_argument("--align", default="center"); t.add_argument("--glow"); t.add_argument("--bg", default="#0B0B0F"); t.add_argument("--no-shadow", action="store_true")
    r = sub.add_parser("reframe"); r.add_argument("src"); r.add_argument("out"); r.add_argument("--size", default="1080x1920")
    r.add_argument("--mode", default="blur", choices=["blur", "cover", "contain"]); r.add_argument("--focus", default="0.5,0.5")
    g = sub.add_parser("grade"); g.add_argument("src"); g.add_argument("out"); g.add_argument("--look", default="teal_orange"); g.add_argument("--strength", type=float, default=1.0)
    c = sub.add_parser("cover"); c.add_argument("src"); c.add_argument("out"); c.add_argument("text"); c.add_argument("--sub")
    c.add_argument("--look", default="teal_orange"); c.add_argument("--size", default="1080x1920"); c.add_argument("--font", default="cairo")
    c.add_argument("--color", default="#FFFFFF"); c.add_argument("--accent", default="#F5C04A")
    u = sub.add_parser("upscale"); u.add_argument("src"); u.add_argument("out"); u.add_argument("--scale", type=int, default=4); u.add_argument("--model", default="ultrasharp-4x")
    k = sub.add_parser("cutout"); k.add_argument("src"); k.add_argument("out"); k.add_argument("--model", default="isnet-general-use")
    s = sub.add_parser("sheet"); s.add_argument("video"); s.add_argument("out"); s.add_argument("--n", type=int, default=12)
    s.add_argument("--cols", type=int, default=4); s.add_argument("--width", type=int, default=360)
    sub.add_parser("looks"); sub.add_parser("fonts"); m = sub.add_parser("measure"); m.add_argument("file")
    a = ap.parse_args(argv)

    if a.cmd == "title":
        res = title(a.out, a.text, a.src, a.size, a.bg, font=a.font, px=a.px, color=a.color, stroke=a.stroke, stroke_color=a.stroke_color,
                    pos=a.pos, align=a.align, glow=a.glow, shadow=not a.no_shadow)
    elif a.cmd == "reframe":
        res = reframe(a.src, a.out, a.size, a.mode, tuple(map(float, a.focus.split(","))))
    elif a.cmd == "grade":
        res = grade(a.src, a.out, a.look, a.strength)
    elif a.cmd == "cover":
        res = cover(a.src, a.out, a.text, a.sub, a.size, a.look, a.font, color=a.color, accent=a.accent)
    elif a.cmd == "upscale":
        res = upscale(a.src, a.out, a.scale, a.model)
    elif a.cmd == "cutout":
        res = cutout(a.src, a.out, a.model)
    elif a.cmd == "sheet":
        res = sheet(a.video, a.out, a.n, a.cols, a.width)
    elif a.cmd == "looks":
        res = looks()
    elif a.cmd == "fonts":
        res = {"fonts": list(FONTS), "arabic_shaper": "raqm" if RAQM else "arabic_reshaper+bidi",
               "upscayl": upscayl_bin(), "upscayl_models": UPSCAYL_MODELS}
    else:
        res = measure(a.file)
    print(json.dumps(res, ensure_ascii=False))


if __name__ == "__main__":
    main()
