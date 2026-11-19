"""Helpers of power_programs/arabic_language.py used by data cards, copied verbatim (the extractor binds a card to them only when
their AST hash with every dependency equals the original's)."""
from __future__ import annotations

from ._lang_common import HARAKAT
from ._lang_common import norm_ar
import re


SACRED = {"quran", "hadith", "poetry"}


AMBIGUOUS = {"علم", "عقد", "حمل"}


COMMON = {"في", "من", "على", "الى", "هذا", "التي", "الذي", "كان", "مع", "عن"}


def tashkeel_for(text, kind, purpose):
    if purpose == "match":
        return HARAKAT.sub("", text)                  # keys only
    if kind in SACRED:
        return text                                   # never fix or strip
    return text


def tashkeel_tells(text):
    """Partial tashkeel on common words is a style tell; on ambiguous words it is justified."""
    tells, justified = [], []
    for w in text.split():
        if HARAKAT.search(w):
            bare = norm_ar(w)
            if bare in COMMON:
                tells.append(w)
            elif bare in AMBIGUOUS:
                justified.append(w)
    return tells, justified


MARKERS = {"egyptian": ["مش", "اللي", "ده", "دي", "دول", "ازاي", "دلوقتي", "هيعمل", "حيعمل"],
           "levantine": ["شو", "هلق", "كتير", "منيح", "هيك"],
           "gulf": ["وايد", "شلون", "زين", "الحين"],
           "maghrebi": ["برشا", "بزاف", "واش"]}


def dialect_scores(text):
    toks = [norm_ar(t) for t in re.findall(r"[ء-يً-ْ]+", text)]
    sc = {d: sum(1 for m in ms for t in toks if norm_ar(m) in (t, t[1:] if t[:1] in "وفب" else t))
          for d, ms in MARKERS.items()}
    hits = {d: s for d, s in sc.items() if s}
    if not hits:
        return "msa", hits, False
    top = max(hits, key=hits.get)
    return top, hits, len(hits) > 1


MASC = {"يوم": "ايام", "كتاب": "كتب", "طالب": "طلاب", "رجل": "رجال"}


FEM = {"ساعه": "ساعات", "سياره": "سيارات", "ورقه": "اوراق", "طالبه": "طالبات"}


NUM_M = {"ثلاثه": 3, "اربعه": 4, "خمسه": 5, "سته": 6, "سبعه": 7, "ثمانيه": 8, "تسعه": 9, "عشره": 10}


NUM_F = {"ثلاث": 3, "اربع": 4, "خمس": 5, "ست": 6, "سبع": 7, "ثماني": 8, "تسع": 9, "عشر": 10}


PLURAL_SUBJ = {"الطلاب", "الرجال", "المهندسون", "الاطباء"}


FEM_SUBJ = {"اللجنه", "الحكومه", "الشركه"}


def agreement_errors(sentence):
    t = [norm_ar(x) for x in sentence.split()]
    errs = []
    for i in range(len(t) - 1):
        a, b = t[i], t[i + 1]
        # 3-10: reversed gender with a plural noun
        if a in NUM_M or a in NUM_F:
            sing = {v: k for k, v in {**MASC, **FEM}.items()}.get(b)
            if sing:
                masc_noun = sing in MASC
                if masc_noun and a in NUM_F:
                    errs.append(f"{a} {b}: masculine noun needs feminine-form numeral (ثلاثة)")
                if not masc_noun and a in NUM_M:
                    errs.append(f"{a} {b}: feminine noun needs masculine-form numeral (ثلاث)")
        # 11-99: singular accusative noun after the compound
        if a in ("عشر", "عشره") and i > 0 and (t[i - 1] in NUM_M or t[i - 1] in NUM_F or t[i - 1] in ("احد", "اثنا")):
            bare = b[:-1] if b.endswith("ا") else b      # drop accusative tanween alif
            if bare in MASC.values() or bare in FEM.values():
                errs.append(f"{t[i-1]} {a} {b}: 11-99 take a singular noun")
        # verb before plural subject stays singular
        if b in PLURAL_SUBJ and re.fullmatch(r"\w+وا", a):
            errs.append(f"{a} {b}: verb before a plural subject stays singular")
        if b in FEM_SUBJ and i == 0 and not a.endswith("ت") and a.startswith(("ا", "ق", "ر", "ح")):
            errs.append(f"{a} {b}: feminine subject takes a feminine verb")
    return errs
