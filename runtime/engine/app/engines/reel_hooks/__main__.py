"""python -m engines.reel_hooks hook|beats|clean [...] [--json]

  hook --hook "LINE" [--screen "CARD"]   score one hook (exit 1 when WEAK)
  hook [FILE|-]                          rank hooks, one per line
  beats [FILE|-] [--target S] [--wpm N]  timed beat sheet (exit 1 when flagged)
  clean [FILE|-] [--fix --out OUT]       humanizer pass"""
import argparse
import json
import sys

from . import CHECK_NAMES, beat_sheet, clean_text, rank_hooks, score_hook


def bar(score, width=24):
    filled = round(score / 100 * width)
    return "#" * filled + "." * (width - filled)


def tc(sec):
    return f"{int(sec // 60)}:{sec % 60:04.1f}"


def render_hook(r, out):
    names = CHECK_NAMES
    print("\nتقييم الهوك / HOOK SCORE\n" + "=" * 62, file=out)
    print(f"  «{r['hook']}»\n", file=out)
    for k, c in r["checks"].items():
        print(f"  {k:<12} {names[k]:<9} {bar(c['score'])} {c['score']:5.1f}", file=out)
        print(f"  {'':<22} {c['detail']}", file=out)
    print("-" * 62, file=out)
    print(f"  {'HOOK SCORE':<22} {bar(r['score'])} {r['score']:5.1f}   {r['verdict']}", file=out)
    for f in r["flags"]:
        print(f"\n  ✗ {f}", file=out)
    if "screen" in r:
        print(f"\n  على الشاشة: «{r['screen']['text']}» - {r['screen']['note']}", file=out)
    if r["verdict"] != "STRONG":
        print(f"\n  أضعف نقطة: {names[r['weakest']]} ({r['weakest']}). صلّحها وأعد التقييم.", file=out)
    print("", file=out)


def render_rank(rows, out):
    print("\nترتيب الهوكات / HOOK RANKING\n" + "=" * 70, file=out)
    for i, r in enumerate(rows, 1):
        print(f"{'->' if i == 1 else '  '} {r['score']:5.1f} {r['verdict']:<7} {r['hook'][:60]}", file=out)
        print(f"        أضعف نقطة: {r['weakest']} ({r['checks'][r['weakest']]['score']:.0f})", file=out)
        for f in r["flags"]:
            print(f"        ✗ {f}", file=out)
    print("\nصوّر الأول. لو الأول تحت 50، يبقى ولا واحد فيهم هو الهوك.\n", file=out)


def render_beats(a, out):
    print(f"\nجدول البيتات / BEAT SHEET  ({a['wpm']} كلمة/دقيقة)\n" + "=" * 70, file=out)
    for r in a["beats"]:
        print(f"{'!' if r['flags'] else ' '} {tc(r['start'])}  {r['dur']:4.1f}s  {r['text'][:58]}", file=out)
    print("-" * 70, file=out)
    tgt = f" / الهدف {a['target']}s" if a.get("target") else ""
    print(f"  المدة: {a['total']}s عبر {len(a['beats'])} بيت{tgt}", file=out)
    for f in a["flags"]:
        print(f"  ✗ {f}", file=out)
    for n in a["notes"]:
        print(f"  • {n}", file=out)
    print("  " + ("نضيف. صوّر." if a.get("clean") else "صلّح العلامات وأعد التشغيل."), file=out)
    print("", file=out)


def render_clean(r, out):
    print("\nفحص البصمة الآلية / HUMANIZER\n" + "=" * 62, file=out)
    if not r["found"]:
        print("  مفيش حاجة. الكلام شكله بشري.", file=out)
    for f in r["found"]:
        print(f"  ✗ {f.get('phrase', f['kind'])} ×{f['count']}: {f['note']}", file=out)
    print("-" * 62, file=out)
    print(f"  درجة البشرية: {r['human_score']}  {r['verdict']}", file=out)
    if r["auto_fixed"]:
        print(f"  اتشال تلقائيًا: {', '.join(r['auto_fixed'])}. الباقي محتاج إعادة صياغة بإيدك.", file=out)
    print("", file=out)


def read_input(path):
    if path in (None, "-"):
        return sys.stdin.read()
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def dump(obj):
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def main(argv=None):
    for s in (sys.stdout, sys.stderr):
        s.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(prog="python -m engines.reel_hooks", description="Reel tools (Arabic-first).")
    sub = ap.add_subparsers(dest="cmd", required=True)
    h = sub.add_parser("hook", help="score or rank hooks")
    h.add_argument("input", nargs="?", default="-")
    h.add_argument("--hook")
    h.add_argument("--screen", help="the on-screen card for a single --hook")
    b = sub.add_parser("beats", help="timed beat sheet")
    b.add_argument("input", nargs="?", default="-")
    b.add_argument("--target", type=float)
    b.add_argument("--wpm", type=float)
    c = sub.add_parser("clean", help="humanizer pass")
    c.add_argument("input", nargs="?", default="-")
    c.add_argument("--fix", action="store_true")
    c.add_argument("--out")
    for p in (h, b, c):
        p.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    out = sys.stdout
    if a.cmd == "hook":
        if a.hook:
            r = score_hook(a.hook, a.screen)
            dump(r) if a.json else render_hook(r, out)
            return 0 if r["verdict"] != "WEAK" else 1
        rows = rank_hooks([line.strip() for line in read_input(a.input).splitlines() if line.strip()])
        dump(rows) if a.json else render_hook(rows[0], out) if len(rows) == 1 else render_rank(rows, out)
        return 0
    if a.cmd == "beats":
        r = beat_sheet(read_input(a.input), a.wpm, a.target)
        dump(r) if a.json else render_beats(r, out)
        return 0 if r.get("clean") else 1
    r = clean_text(read_input(a.input), fix=a.fix)
    if a.fix and a.out:
        with open(a.out, "w", encoding="utf-8") as fh:
            fh.write(r["fixed"])
    dump(r) if a.json else render_clean(r, out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
