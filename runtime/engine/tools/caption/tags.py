#!/usr/bin/env python3
"""tags — كابشن وهاشتاجات جاهزة للنسخ مع كل مقطع (v10.11).

  dragon.py tool tags --ref "نص كابشن المرجع من تيك توك (فيه #هاشتاجات)" \
      --topic "دعاء يوم الثلاثاء" --caption "دعاء يوم الثلاثاء 🤲 10.11.2026" \
      [--extra "#ادعية #دعاء_الصباح"] [--sound "@handle"] [--n 9] [--no-reach] \
      [--drop "#alihadkc2ok"] [--json] [--out caption.md]

بيعمل:
  1) يطلّع كل هاشتاج من نص المرجع (عربي/إنجليزي/أرقام/_) ويشيل المكرر بالترتيب.
  2) يشيل هاشتاجات أسماء الحسابات (handle) بتاعة صاحب المرجع تلقائيًا لو اتطابقت مع --drop
     أو لو شكلها handle لاتيني بأرقام (زي #alihadkc2ok) — مانحطش اسم حساب حد تاني على مقطعنا.
  3) يحوّل --topic لهاشتاج (المسافات = _) ويحطه الأول.
  4) يضيف --extra، وبعدين اتنين للانتشار (#fyp #foryou) إلا لو --no-reach.
  5) يقص للعدد --n (افتراضي 9، حسب PROTOCOL.md: 5–9).
  6) يطبع بلوك ``` جاهز للنسخ بضغطة واحدة: سطر الكابشن، سطر الصوت (لو فيه)، سطر الهاشتاجات.

مكتبة بايثون القياسية بس. مابينشرش ولا بيتصل بالنت.
"""
from __future__ import annotations

import argparse
import json
import re
import sys

TAG_RE = re.compile(r"#([0-9A-Za-z_؀-ۿݐ-ݿࢠ-ࣿ]+)")
REACH = ["fyp", "foryou"]


def extract(text: str) -> list[str]:
    seen, out = set(), []
    for m in TAG_RE.finditer(text or ""):
        t = m.group(1).strip("_")
        k = t.lower()
        if t and k not in seen:
            seen.add(k)
            out.append(t)
    return out


def looks_like_handle(tag: str) -> bool:
    """Latin-only tag mixing letters and digits (e.g. alihadkc2ok) = probably an account handle."""
    return bool(re.fullmatch(r"[A-Za-z_.]*[A-Za-z][A-Za-z_.]*\d[A-Za-z0-9_.]*", tag)) and tag.lower() not in REACH


def topic_tag(topic: str) -> str:
    t = re.sub(r"[^\w؀-ۿ]+", "_", topic.strip()).strip("_")
    return re.sub(r"_+", "_", t)


def build(ref: str = "", topic: str = "", extra: str = "", drop: str = "", n: int = 9,
          reach: bool = True, keep_handles: bool = False) -> list[str]:
    drops = {d.lower() for d in extract(drop)} | {d.lstrip("#").lower() for d in drop.split() if d}
    tags: list[str] = []
    if topic:
        tags.append(topic_tag(topic))
    for t in extract(ref) + extract(extra):
        if t.lower() in drops or (not keep_handles and looks_like_handle(t)):
            continue
        tags.append(t)
    uniq, seen = [], set()
    for t in tags:
        if t.lower() not in seen and t.lower() not in REACH:
            seen.add(t.lower())
            uniq.append(t)
    room = max(0, n - (len(REACH) if reach else 0))
    final = uniq[:room] + (REACH if reach else [])
    return ["#" + t for t in final[:n]]


def block(caption: str, tags: list[str], sound: str = "") -> str:
    lines = [caption.strip()] if caption.strip() else []
    if sound:
        lines.append(f"الصوت: {sound}")
    lines.append(" ".join(tags))
    return "```\n" + "\n".join(lines) + "\n```"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="dragon.py tool tags", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ref", default="", help="نص كابشن المرجع (أو مسار ملف نصي)")
    ap.add_argument("--topic", default="")
    ap.add_argument("--caption", default="")
    ap.add_argument("--extra", default="")
    ap.add_argument("--drop", default="", help="هاشتاجات تتشال (زي handle صاحب المرجع)")
    ap.add_argument("--sound", default="")
    ap.add_argument("--n", type=int, default=9)
    ap.add_argument("--no-reach", action="store_true")
    ap.add_argument("--keep-handles", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--out", default="")
    a = ap.parse_args(argv)
    if a.n < 1:
        print("--n لازم 1 أو أكتر", file=sys.stderr)
        return 2
    ref = a.ref
    if ref and len(ref) < 400 and not ref.strip().startswith("#"):
        try:
            with open(ref, encoding="utf-8") as fh:
                ref = fh.read()
        except OSError:
            pass
    tags = build(ref, a.topic, a.extra, a.drop, a.n, not a.no_reach, a.keep_handles)
    if not tags:
        print("مفيش هاشتاجات: ادّي --ref أو --topic أو --extra", file=sys.stderr)
        return 1
    md = block(a.caption, tags, a.sound)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as fh:
            fh.write(md + "\n")
    if a.json:
        print(json.dumps({"caption": a.caption, "sound": a.sound, "hashtags": tags, "block": md},
                         ensure_ascii=False, indent=1))
    else:
        print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
