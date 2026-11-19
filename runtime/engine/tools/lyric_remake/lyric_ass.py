#!/usr/bin/env python3
"""Lyric / kinetic-caption builder: a JSON spec of timed lines -> an .ass subtitle file that ffmpeg burns in
(subtitles=FILE.ass:fontsdir=FONTS). Arabic shapes correctly through libass + fribidi. Learnt on the TikTok remake
(«ما تلاقيناش»): measure the original's text boxes, match size/position, and add U+200F around Arabic lines that end
with punctuation so «!!» and «...» stay on the left.

    python lyric_ass.py spec.json out.ass [--force]  # build (an existing out.ass is kept unless --force)
    python lyric_ass.py --example > spec.json        # print a starter spec
    ffmpeg -i in.mp4 -vf "subtitles=out.ass:fontsdir=fonts" -c:a copy out.mp4

spec = {"width":1920,"height":1080,
        "styles":{"Title":{"font":"Arabic Typesetting","size":330,"color":"#FFFFFF","outline":0,"shadow":4}},
        "lines":[{"start":0.9,"end":3.8,"style":"Title","text":"وما تلاقيناش...","pos":[960,560],
                  "fade":[250,250],"color_words":{"تبعدناش":"#C81C2A"}}]}
"""
import json, os, sys

EXAMPLE = {"width": 1920, "height": 1080,
           "styles": {"Title": {"font": "Arabic Typesetting", "size": 330, "color": "#FFFFFF", "outline": 0, "shadow": 4},
                      "Sub": {"font": "Lalezar", "size": 122, "color": "#FFFFFF", "outline": 2, "shadow": 2}},
           "lines": [{"start": 0.9, "end": 3.8, "style": "Title", "text": "وما تلاقيناش...", "pos": [960, 560], "fade": [250, 250]},
                     {"start": 3.9, "end": 7.5, "style": "Sub", "text": "انا وانت فـ نقطه تجمع بيننا ما تبعدناش",
                      "pos": [960, 900], "color_words": {"تبعدناش": "#C81C2A"}}]}

RLM = "\u200f"


def ass_color(hexrgb, alpha=0):
    h = hexrgb.lstrip("#")
    r, g, b = h[0:2], h[2:4], h[4:6]
    return f"&H{alpha:02X}{b}{g}{r}".upper()


def ts(s):
    s = max(0.0, float(s))
    h = int(s // 3600); m = int(s % 3600 // 60); sec = s % 60
    return f"{h}:{m:02d}:{sec:05.2f}"


def is_arabic(t):
    return any("\u0600" <= c <= "\u06ff" for c in t)


def build(spec):
    W, H = int(spec.get("width", 1920)), int(spec.get("height", 1080))
    out = ["[Script Info]", "ScriptType: v4.00+", f"PlayResX: {W}", f"PlayResY: {H}", "WrapStyle: 2", "",
           "[V4+ Styles]",
           "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
           "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, "
           "MarginR, MarginV, Encoding"]
    for name, st in spec.get("styles", {}).items():
        c = ass_color(st.get("color", "#FFFFFF"))
        out.append(f"Style: {name},{st.get('font','Arial')},{st.get('size',96)},{c},{c},{ass_color(st.get('outline_color','#000000'))},"
                   f"&H9A000000,{-1 if st.get('bold', True) else 0},0,0,0,100,100,0,0,1,{st.get('outline',2)},{st.get('shadow',2)},"
                   f"{st.get('align',5)},20,20,20,1")
    out += ["", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"]
    n = 0
    for ln in spec.get("lines", []):
        text = ln["text"]
        tags = ""
        if "pos" in ln:
            tags += r"\pos(%d,%d)" % tuple(ln["pos"])
        if "fade" in ln:
            tags += r"\fad(%d,%d)" % tuple(ln["fade"])
        base = ass_color(spec["styles"].get(ln.get("style", ""), {}).get("color", "#FFFFFF"))
        bgr = lambda c: "&H" + c[4:] + "&"          # &HAABBGGRR -> &HBBGGRR& for \1c
        cw = ln.get("color_words") or {}
        if cw:
            # Split into coloured runs. libass lays override-separated runs out LEFT-to-RIGHT even in Arabic
            # (measured: an inline colour tag moved the red word to the start of the line), so Arabic runs are
            # emitted in reverse logical order; each run still shapes RTL inside itself.
            segs, rest = [], text
            while rest:
                hit = min(((rest.find(w), w) for w in cw if rest.find(w) >= 0), default=None)
                if not hit:
                    segs.append((rest, base)); break
                i, w = hit
                if i:
                    segs.append((rest[:i], base))
                segs.append((w, ass_color(cw[w]))); rest = rest[i + len(w):]
            if is_arabic(ln["text"]):
                # libass drops a run's edge spaces, so each word gap at a run boundary becomes its own " " run
                spaced = []
                for k, (s, c) in enumerate(segs):
                    if k and (segs[k - 1][0].endswith(" ") or s.startswith(" ")):
                        spaced.append((" ", base))
                    spaced.append((s.strip(" "), c))
                segs = spaced[::-1]
            text = "".join(r"{\1c%s}%s" % (bgr(c), s) for s, c in segs)
        elif is_arabic(ln["text"]):
            text = RLM + text + RLM      # keeps trailing «...» / «!!» on the left
        out.append(f"Dialogue: {ln.get('layer',0)},{ts(ln['start'])},{ts(ln['end'])},{ln.get('style','Default')},,0,0,0,,"
                   + ("{%s}" % tags if tags else "") + text)
        n += 1
    return "\n".join(out) + "\n", n


def main(argv):
    if argv[:1] in (["-h"], ["--help"]):
        print(__doc__); return 0
    if argv[:1] == ["--example"]:
        print(json.dumps(EXAMPLE, ensure_ascii=False, indent=1)); return 0
    force = "--force" in argv                       # v10.14: an existing .ass is kept unless --force
    argv = [a for a in argv if a != "--force"]
    if len(argv) < 2:
        print(__doc__); return 2
    if os.path.exists(argv[1]) and not force:
        print(json.dumps({"ok": False, "error": f"exists: {argv[1]} (use --force)"}), file=sys.stderr); return 2
    spec = json.load(open(argv[0], encoding="utf-8-sig"))
    text, n = build(spec)
    open(argv[1], "w", encoding="utf-8-sig").write(text)
    print(json.dumps({"ok": True, "out": argv[1], "events": n}))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
