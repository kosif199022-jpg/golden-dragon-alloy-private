# -*- coding: utf-8 -*-
"""Builds the lyric .ass file that mirrors the original TikTok typography/timing (1920x1080)."""
import os, sys

USAGE = """usage: example_ma_tlaqinash.py [debug] [OUT.ass] [--force]

  debug      optional: tint the lyric red to compare over the original
  OUT.ass    output file (default: lyrics.ass in the current folder)
  --force    allow overwriting an existing OUT.ass
Writes only the .ass file; no other files are created.
"""

_args = [a for a in sys.argv[1:]]
if any(a in ("-h", "--help") for a in _args):
    print(USAGE); sys.exit(0)
_force = "--force" in _args
_args = [a for a in _args if a != "--force"]
DEBUG = len(_args) > 0 and _args[0] == "debug"   # tint red to compare over the original
OUT = _args[1] if len(_args) > 1 else "lyrics.ass"
if os.path.exists(OUT) and not _force:
    sys.exit(f"refusing to overwrite {OUT} (use --force)")

TITLE_FONT = "Arabic Typesetting"
SUB_FONT = "Lalezar"
STACK_FONT = "Tajawal Black"
RED = "&H2A1CC8&"
END = 41.93

def t(s):
    h = int(s // 3600); m = int((s % 3600) // 60); sec = s % 60
    return f"{h}:{m:02d}:{sec:05.2f}"

def kk(n):
    return "ـ" * n

head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Title,{TITLE_FONT},330,&H00FFFFFF,&H00FFFFFF,&H00FFFFFF,&H9A000000,-1,0,0,0,100,100,0,0,1,2.2,4,5,0,0,0,1
Style: Ink,{TITLE_FONT},285,&H30101214,&H30101214,&H30101214,&HFF000000,-1,0,0,0,100,100,0,0,1,1.8,0,5,0,0,0,1
Style: Sub,{SUB_FONT},125,&H00FFFFFF,&H00FFFFFF,&H00000000,&H8A000000,0,0,0,0,100,100,0,0,1,0,3,5,0,0,0,1
Style: Stack,{STACK_FONT},155,&H00FFFFFF,&H00FFFFFF,&H00000000,&H9A000000,0,0,0,0,100,100,0,0,1,0,3,5,0,0,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

ev = []
def add(st, en, style, text, tags="", layer=0):
    if DEBUG:
        tags += r"\1c&H0000FF&\1a&H60&"
    ev.append(f"Dialogue: {layer},{t(st)},{t(en)},{style},,0,0,0,,{{{tags}}}{text}")

SUB_Y = 1012
# 1) white calligraphic title
add(0.90, 3.82, "Title", "\u200fوما تلاقيناش...\u200f", r"\pos(960,590)\fad(380,300)\blur7\t(0,450,\blur1)")
# 2) bottom lyric lines — line 1 has its last word in red (done with a clipped red copy so RTL order stays right)
l1 = f"انا وانـ{kk(4)}ـت فـ{kk(5)} نقطه تجمع بيننا ما تبعدناش"
add(3.90, 10.92, "Sub", l1, rf"\pos(960,{SUB_Y})\fad(250,200)\blur0.6", 0)
add(3.90, 10.92, "Sub", l1, rf"\pos(960,{SUB_Y})\fad(250,200)\blur0.6\c{RED}\shad0\clip(0,0,611,1080)", 1)
add(11.20, 18.02, "Sub", f"\u200fولآخر لحظة قربـ{kk(4)}ـت حاولنا وما قدرناش!!\u200f", rf"\pos(960,{SUB_Y})\fad(250,250)\blur0.6")
# 3) dark ink title "written on the glass"
add(18.60, 21.66, "Ink", "\u200fوما تلاقيناش...\u200f", r"\pos(1030,596)\fad(450,300)\blur3.5")
add(21.70, 24.18, "Sub", "كان بينّا شعور", rf"\pos(960,{SUB_Y})\fad(220,150)\blur0.6")
add(24.25, 31.55, "Sub", f"لكن بالوقـ{kk(4)}ـت فضلنا نعلي ما بيننا السور", rf"\pos(960,{SUB_Y})\fad(220,300)\blur0.6")
# 4) stacked lyrics building up line by line (centred, long kashida)
stack = [
    (31.90, 307, f"ضيعنا الحـ{kk(25)}ـب"),
    (33.40, 458, "و   حولناه"),
    (34.85, 610, f"وقـ{kk(27)}ـت و مهدور"),
    (37.90, 757, f"و ما شافشـ{kk(23)}ـ النور"),
]
for st, y, txt in stack:
    add(st, END, "Stack", txt, rf"\pos(962,{y})\fad(380,0)\blur6\t(0,400,\blur0.7)")

open(OUT, "w", encoding="utf-8-sig").write(head + "\n".join(ev) + "\n")
print("wrote", OUT, len(ev), "events")





