"""Reel hook score (0-100) on five properties: LENGTH, SPECIFICITY, STAKES, FRONTLOAD, ADDRESS.
Arabic-first (Egyptian, MSA) and English. Lexicons live in data/hook_lexicon.json. Not a view predictor: it catches
greetings, preambles, hooks with nothing concrete and hooks that take too long to say."""
from __future__ import annotations

import re
import statistics

from . import common as C

DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
TASHKEEL_RE = re.compile("[ؐ-ًؚ-ٰٟۖ-ۭـ]")
TOKEN_RE = re.compile(r"[ء-يٱ-ۓA-Za-z0-9$%'’٪٫٬.,-]+")
ARABIC_RE = re.compile(r"[ء-ي]")
NUMBER_RE = re.compile(r"\$?\s?\d[\d,٬.]*\s?(?:%|٪|k\b|x\b)?", re.IGNORECASE)
LATIN_PROPER_RE = re.compile(r"(?<!^)\b[A-Z][a-z]{2,}\b")
GREETING_RE = re.compile(r"^\s*(?:اهلا|أهلا|أهلاً|اهلاً|مرحب|السلام عليكم|ازيك|إزيك|هاي|صباح الخير|مساء الخير"
                         r"|hey\b|hi\b|hello\b|what'?s up|welcome)", re.IGNORECASE)
PREAMBLE_RE = re.compile(r"في (?:الفيديو|الريل|فيديو) (?:ده|دا|هذا|النهارده|النهاردة|اليوم)"
                         r"|(?:هوريك|هوريكم|هقولك|هقولكم|هشرحلك|هشرحلكم|خليني اوريك|خلّيني أوريك)"
                         r"|النهارد[هة] (?:هنتكلم|هتكلم|حنتكلم)"
                         r"|in (?:this|today'?s) (?:video|reel)|i'?m going to show you|i'?ll show you how", re.IGNORECASE)
SCROLL_RE = re.compile(r"^\s*(?:استني|استنى|متقلبش|ماتقلبش|متعديش|ماتعديش|وقف التقليب|stop scrolling|don'?t scroll)",
                       re.IGNORECASE)
DEALBREAKERS = [(SCROLL_RE, "بيبدأ بـ«استنى/متقلبش»."), (PREAMBLE_RE, "مقدمة فيديو («في الفيديو ده / هوريكم»)."),
                (GREETING_RE, "تحية."), (re.compile(r"(?:^|\s)#\w+"), "هاشتاج في الهوك."),
                (re.compile(r"[\U0001F300-\U0001FAFF☀-➿]"), "إيموجي في الهوك.")]
YOUR_NOUNS = ("حياتك", "شغلك", "فلوسك", "وقتك", "بيتك", "مشروعك", "زباينك", "عملاءك", "مرتبك")
NOT_YOU = {"ذلك", "كذلك", "لذلك", "هناك", "تلك", "ملك", "شك", "بنك", "سمك", "فلك", "مشترك"}


def L(name: str) -> set:
    return set(C.data("hook_lexicon.json")[name])


def norm(word: str) -> str:
    w = TASHKEEL_RE.sub("", word.translate(DIGITS)).lower()
    w = re.sub("[إأآٱ]", "ا", w)
    return w.replace("ة", "ه").replace("ى", "ي").replace("ؤ", "و").replace("ئ", "ي").strip(".,'’-")


def tokens(text: str) -> list:
    return [t for t in (t.strip(".,-") for t in TOKEN_RE.findall(text.translate(DIGITS))) if t]


def variants(word: str) -> set:
    """The word plus its forms without a leading و / ف and the article (ال، بال، لل، كال)."""
    w = norm(word)
    forms = {w} | ({w[1:]} if w[:1] in ("و", "ف") and len(w) > 3 else set())
    for f in list(forms):
        forms |= {f[len(p):] for p in ("ال", "بال", "لل", "كال") if f.startswith(p) and len(f) - len(p) >= 2}
    return forms


def in_lex(word: str, lex: set) -> bool:
    return bool(variants(word) & lex)


def is_arabic(text: str) -> bool:
    letters = re.findall(r"[A-Za-zء-ي]", text)
    return bool(letters) and sum(1 for c in letters if ARABIC_RE.match(c)) / len(letters) >= 0.5


def clamp(n):
    return max(0.0, min(100.0, n))


def check_length(text):
    n, chars = len(tokens(text)), len(text.strip())
    lo, hi = (4, 10) if is_arabic(text) else (5, 12)
    score = 100.0 if lo <= n <= hi else 100 - (lo - n) * 20 if n < lo else 100 - (n - hi) * 11
    return clamp(score - (12 if chars > 60 else 0)), f"{n} كلمة، {chars} حرف (المطلوب {lo}-{hi} كلمة)"


def check_specificity(text):
    hits = [m.strip() for m in NUMBER_RE.findall(text.translate(DIGITS)) if re.search(r"\d", m)]
    hits += sorted(set(LATIN_PROPER_RE.findall(text)))
    hits += [t for t in tokens(text) if in_lex(t, L("spoken_numbers") | L("money") | L("units"))]
    return (15.0 if not hits else clamp(45 + len(hits) * 30)), f"{len(hits)} علامة ملموسة"


def check_stakes(text):
    marks = {norm(t) for t in tokens(text) if in_lex(t, L("stakes"))} | {p for p in L("stake_phrases") if p in norm(text)}
    marks = sorted(marks)
    if re.search(r"\$\s?\d|\d[\d,٬]*\s*(?:جنيه|دولار|ريال|درهم)", text.translate(DIGITS)):
        marks.append("سعر")
    return {0: 20.0, 1: 70.0}.get(len(marks), 100.0), f"{len(marks)} علامة توتر"


def check_frontload(text):
    t = tokens(text)
    if not t:
        return 0.0, "فاضي"
    opener = norm(" ".join(t[:2]))
    weak = next((w for w in C.data("hook_lexicon.json")["weak_openers"]
                 if opener == w or opener.startswith(w + " ") or norm(t[0]) == w), None)
    heavy = L("stakes") | L("spoken_numbers") | L("money")
    payload = next((i for i, tok in enumerate(t) if in_lex(tok, heavy) or re.search(r"\d", tok)
                    or (i and re.fullmatch(r"[A-Z][a-z]{2,}", tok))), None)
    base = 30.0 if payload is None else 100.0 if payload <= 3 else 70.0 if payload <= 6 else 40.0
    return clamp(base - (30 if weak else 0)), f"payload at {payload}" + (f"; weak opener «{weak}»" if weak else "")


def check_address(text):
    t = tokens(text)

    def to_you(tok):
        w = norm(tok)
        return ARABIC_RE.match(w[:1] or " ") and len(w) >= 4 and w.endswith("ك") and w not in NOT_YOU
    if any(in_lex(x, L("you")) for x in t) or any(norm(x) in {norm(w) for w in YOUR_NOUNS} for x in t) \
            or any(to_you(x) for x in t):
        return 100.0, "بيكلّم المشاهد"
    first = norm(t[0]) if t else ""
    if t and (in_lex(t[0], L("imperatives")) or re.fullmatch(r"(?:ما|م)ت\w{2,}ش", first)):
        return 90.0, f"بيبدأ بأمر («{t[0]}»)"
    if any(in_lex(x, L("me")) for x in t) or (t and is_arabic(text) and first.endswith("ت") and len(first) >= 4):
        return 70.0, "بصيغة المتكلم"
    return 35.0, "بصيغة الغايب"


CHECKS = [("LENGTH", check_length), ("SPECIFICITY", check_specificity), ("STAKES", check_stakes),
          ("FRONTLOAD", check_frontload), ("ADDRESS", check_address)]


def score_hook(text: str) -> dict:
    checks = {k: dict(zip(("score", "detail"), fn(text))) for k, fn in CHECKS}
    flags = [msg for pat, msg in DEALBREAKERS if pat.search(text)]
    scores = [c["score"] for c in checks.values()]
    overall = clamp(statistics.mean(scores) * 0.6 + min(scores) * 0.4 - len(flags) * 15)   # the weakest caps it
    verdict = "STRONG" if overall >= 70 and min(scores) >= 55 and not flags else "OK" if overall >= 50 else "WEAK"
    return {"hook": text.strip(), "score": round(overall, 1), "verdict": verdict,
            "weakest": min(checks, key=lambda k: checks[k]["score"]), "checks": checks, "flags": flags}
