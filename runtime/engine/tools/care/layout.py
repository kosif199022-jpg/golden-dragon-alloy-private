#!/usr/bin/env python3
"""Wrong keyboard layout fixer: Arabic typed while the keyboard was on English (and the reverse).

    layout.py "P'DJ TDK LIHVM HGJKDK"     ->  حطيت فين مهارة التنين
    layout.py ";LG"                       ->  كمل
    layout.py --to en "هىسفشمم"           ->  install
    layout.py --detect "hfqym ugn"        ->  {"looks_wrong_layout": true, "arabic": "..."}

Why (v10.8): the owner sent messages such as «;LG», «P'DJ TDK LIHVM HGJKDK» and «hgljwtp htjp hgj'fdr la fdtjp»
— Arabic typed on the English layout (often with Caps Lock on). The Dragon now reads them instead of guessing.
Standard Windows Arabic (101) layout. Caps Lock text is folded to lower case first (Arabic has no capitals).
"""
import argparse, json, re, sys

EN2AR = {
    "q": "ض", "w": "ص", "e": "ث", "r": "ق", "t": "ف", "y": "غ", "u": "ع", "i": "ه", "o": "خ", "p": "ح", "[": "ج",
    "]": "د", "a": "ش", "s": "س", "d": "ي", "f": "ب", "g": "ل", "h": "ا", "j": "ت", "k": "ن", "l": "م", ";": "ك",
    "'": "ط", "z": "ئ", "x": "ء", "c": "ؤ", "v": "ر", "b": "لا", "n": "ى", "m": "ة", ",": "و", ".": "ز", "/": "ظ",
    "`": "ذ", "?": "؟",
}
AR2EN = {v: k for k, v in EN2AR.items() if len(v) == 1}
AR2EN.update({"أ": "h", "إ": "y", "آ": "n", "ـ": "j", "،": "k", "؛": "p"})
COMMON_EN = set("the and you for are with this that have not but can all what your from was will is it to of in on "
                "a i ok yes no hi hello please thanks file video app".split())
COMMON_AR_HITS = ("ال", "في", "من", "على", "مش", "كمل", "عايز", "ازاي", "ايه", "فين", "خلص", "حط", "اعمل", "التطبيق",
                  "الملف", "البرنامج", "التنين", "لا", "ليه", "هل", "انا", "ده", "دي", "حمل", "طور")


def en_to_ar(text):
    t = text.lower() if text.upper() == text else text  # Caps Lock on: fold
    out, i = [], 0
    while i < len(t):
        ch = t[i]
        out.append(EN2AR.get(ch.lower(), ch) if ch.isascii() else ch)
        i += 1
    return "".join(out)


def ar_to_en(text):
    return "".join(AR2EN.get(ch, ch) for ch in text)


def looks_wrong_layout(text):
    """True when Latin text is not English but its Arabic mapping contains common Arabic words."""
    latin = re.findall(r"[A-Za-z;',\[\]`./]+", text)
    if not latin or re.search(r"[؀-ۿ]", text) and len("".join(latin)) < 4:
        return False
    words = [w.lower().strip(".,;'") for w in text.split()]
    if words and sum(w in COMMON_EN for w in words) / len(words) >= 0.3:
        return False
    ar = en_to_ar(text)
    hits = sum(1 for w in ar.split() for c in COMMON_AR_HITS if c in w)
    vowelless = sum(1 for w in words if w and not re.search(r"[aeiouy]", w))
    return hits >= 1 or vowelless >= max(1, len(words) // 2)


def main(argv=None):
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(prog="layout", description=__doc__.split("\n\n")[0])
    ap.add_argument("text", nargs="+")
    ap.add_argument("--to", choices=("ar", "en"), default="ar")
    ap.add_argument("--detect", action="store_true", help="JSON: does it look like the wrong layout, and the fix")
    a = ap.parse_args(argv)
    text = " ".join(a.text)
    if a.detect:
        print(json.dumps({"looks_wrong_layout": looks_wrong_layout(text), "arabic": en_to_ar(text)}, ensure_ascii=False))
        return 0
    print(en_to_ar(text) if a.to == "ar" else ar_to_en(text))
    return 0


if __name__ == "__main__":
    sys.exit(main())
