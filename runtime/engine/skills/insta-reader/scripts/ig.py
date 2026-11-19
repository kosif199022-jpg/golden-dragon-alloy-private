#!/usr/bin/env python3
"""rd.py ig: the five offline tools of instagram-agent-skill (MIT, library/ig-*), plus the 13 skills list.

  list                                 the 13 ig-* skills and what each does
  hooks FILE                           rank hook options (ig-reel/hookscore.py)
  beats FILE [--target 30]             timed beat sheet for a reel script (ig-reel/beats.py)
  caption FILE [--keywords "a,b"]      what the feed shows before "... more" + lint (ig-caption/caption.py)
  humanize FILE [--report]             strip AI slop (ig-human/humanize.py)   · English-tuned
  detect FILE [FILE2]                  five-check AI-text score (ig-human/detect.py) · English-tuned
  swipe FILE.tsv [--out swipe.md]      rank reels by multiple over their account's median (ig-viral/swipe.py)
                                       make FILE.tsv with: rd.py insta swipe USER [USER…] --out FILE.tsv
  voice                                copy the voice.md template to ~/.claude/instagram/voice.md (every ig skill reads it)
No network, stdlib only. Nothing gets posted: these write, the owner posts.
"""
import json, re, shutil, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
LIB = ROOT / "library"
TOOLS = {"hooks": ("ig-reel", "hookscore.py"), "beats": ("ig-reel", "beats.py"), "caption": ("ig-caption", "caption.py"),
         "humanize": ("ig-human", "humanize.py"), "detect": ("ig-human", "detect.py"), "swipe": ("ig-viral", "swipe.py")}


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    cmd, rest = argv[0], argv[1:]
    if cmd == "list":
        idx = {r["name"]: r for r in json.loads((LIB / "index.json").read_text(encoding="utf-8")).get("skills", [])}
        for d in sorted(LIB.glob("ig-*/SKILL.md")):
            print(f"{d.parent.name:14} {idx.get(d.parent.name, {}).get('description', '')[:150]}")
        return 0
    if cmd == "voice":
        dst = Path.home() / ".claude" / "instagram" / "voice.md"
        if dst.exists():
            print(f"موجود بالفعل، ماتلمسش: {dst}")
            return 0
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(LIB / "ig-plan" / "voice.md", dst)
        print(f"اتعمل: {dst} ← املاه بصوتك، أو ابعت 3 ريلز من بتوعك وقول «اكتب voice.md منهم»")
        return 0
    if cmd not in TOOLS:
        print(f"أمر مش معروف: {cmd}\n{__doc__}")
        return 2
    sk, sc = TOOLS[cmd]
    return subprocess.call([sys.executable, "-I", "-X", "utf8", str(LIB / sk / sc)] + rest)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
