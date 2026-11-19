"""Reel hooks: score a Reel's opening line on five properties, time a spoken script as a beat sheet, and find
(optionally strip) the AI fingerprint in a draft. Arabic first (Egyptian, MSA), English and mixed lines; offline.

Word lists, patterns, scores and messages live in data/*.json; data/hooks_ar.json is the hook-formula library.
The five checks, beat sheet and humanizer follow the idea of instagram-agent-skill (MIT), with Arabic lexicons.
The score is not a view predictor: it catches greetings, preambles, vague hooks and hooks too long to say."""
import json
import re
import statistics
import unicodedata
from pathlib import Path

DATA = Path(__file__).resolve().parent / "data"
_D = json.loads((DATA / "lexicons.json").read_text(encoding="utf-8"))
T = json.loads((DATA / "scoring.json").read_text(encoding="utf-8"))
P = {k: re.compile(v, re.IGNORECASE if k in ("greeting", "preamble", "scroll", "number") else 0)
     for k, v in _D["patterns"].items()}
DIGITS = str.maketrans(*_D["digits"])
LEX = {k: set(v) for k, v in _D["lexicons"].items()}
CONCRETE = LEX["spoken_numbers"] | LEX["money"] | LEX["units"]
PAYLOAD = LEX["stakes"] | LEX["spoken_numbers"] | LEX["money"]
STAKE_PHRASES = set(_D["stake_phrases"])
WEAK_OPENERS = _D["weak_openers"]
YOUR_NOUNS, NOT_YOU = set(_D["your_nouns"]), set(_D["not_you"])
DEALBREAKERS = [(P[k], msg) for k, msg in _D["dealbreakers"]]
SLOP = [tuple(x) for x in _D["slop"]]
CHECK_NAMES = dict(T["checks"])


def library() -> dict:
    """The Egyptian hook-formula library (template, example, on-screen card, best use, trap)."""
    return json.loads((DATA / "hooks_ar.json").read_text(encoding="utf-8"))


# ---------------------------------------------------------------- text basics
def norm(word):
    """Fold the spellings Egyptian writers mix: hamza seats, ta marbuta, ya; strip marks; Arabic digits -> ASCII."""
    w = P["tashkeel"].sub("", word.translate(DIGITS)).lower()
    w = re.sub("[إأآٱ]", "ا", w)
    w = w.replace("ة", "ه").replace("ى", "ي").replace("ؤ", "و").replace("ئ", "ي")
    return w.strip(".,'’-")


def tokens(text):
    return [t for t in (t.strip(".,-") for t in P["token"].findall(text.translate(DIGITS))) if t]


def variants(word):
    """The word plus its forms without a leading و/ف and the article (ال، بال، لل، كال); bare ب/ل stay."""
    w = norm(word)
    forms = {w} | {w[1:] for pre in ("و", "ف") if w.startswith(pre) and len(w) > 3}
    for f in list(forms):
        forms |= {f[len(pre):] for pre in ("ال", "بال", "لل", "كال") if f.startswith(pre) and len(f) - len(pre) >= 2}
    return forms


def in_lex(word, lex):
    return bool(variants(word) & lex)


def is_arabic(text):
    letters = re.findall(r"[A-Za-zء-ي]", text)
    return bool(letters) and sum(1 for c in letters if P["arabic"].match(c)) / len(letters) >= 0.5


def clamp(n):
    return max(0.0, min(100.0, n))


def _lang(text):
    return "ar" if is_arabic(text) else "en"


# ---------------------------------------------------------------- hook checks
def check_length(text):
    c = T["length"]
    n, chars = len(tokens(text)), len(text.strip())
    secs = n / (T["wpm"][_lang(text)] / 60)
    lo, hi = c["window"][_lang(text)]
    score = c["in_window"] if lo <= n <= hi else 100 - (lo - n) * c["short_step"] if n < lo else 100 - (n - hi) * c["long_step"]
    if chars > c["max_chars"]:
        score -= c["chars_penalty"]
    return clamp(score), c["detail"].format(n=n, chars=chars, secs=secs, lo=lo, hi=hi)


def concrete_markers(text):
    nums = [m.strip() for m in P["number"].findall(text.translate(DIGITS)) if re.search(r"\d", m)]
    names = sorted(set(P["latin_proper"].findall(text)))
    return nums + names + [t for t in tokens(text) if in_lex(t, CONCRETE)]


def _detail(c, hits, n):
    return c["detail"].format(n=n) + (c["found"].format(found="، ".join(hits[:c["show"]])) if hits else c["empty"])


def check_specificity(text):
    c, hits = T["specificity"], concrete_markers(text)
    return (c["none"] if not hits else clamp(c["base"] + len(hits) * c["per_hit"])), _detail(c, hits, len(hits))


def check_stakes(text):
    c = T["stakes"]
    marks = {norm(t) for t in tokens(text) if in_lex(t, LEX["stakes"])}
    marks = sorted(marks | {p for p in STAKE_PHRASES if p in norm(text)})  # two-word stakes match as a phrase
    if re.search(c["price_re"], text.translate(DIGITS)):
        marks.append(c["price_mark"])
    n = len(marks)
    return (c["by_count"][n] if n < len(c["by_count"]) else c["more"]), _detail(c, marks, n)


def check_frontload(text):
    c, t = T["frontload"], tokens(text)
    if not t:
        return tuple(c["empty"])
    opener = norm(" ".join(t[:2]))
    weak = next((w for w in WEAK_OPENERS if opener == w or opener.startswith(w + " ") or norm(t[0]) == w), None)
    payload = next((i for i, tok in enumerate(t) if in_lex(tok, PAYLOAD) or re.search(r"\d", tok)
                    or (i and re.fullmatch(r"[A-Z][a-z]{2,}", tok))), None)
    if payload is None:
        base, where = c["none"]
    else:
        base, where = next(((s, m) for top, s, m in c["tiers"] if payload <= top), c["late"])
        where = where.format(pos=payload + 1)
    return clamp(base - (c["weak_penalty"] if weak else 0)), where + (c["weak_note"].format(weak=weak) if weak else "")


def check_address(text):
    c, t = T["address"], tokens(text)
    nouns = {norm(w) for w in YOUR_NOUNS}

    def to_you(tok):
        w = norm(tok)
        return P["arabic"].match(w[:1] or " ") and len(w) >= c["you_min_len"] and w.endswith(c["you_suffix"]) and w not in NOT_YOU

    if any(in_lex(x, LEX["you"]) or norm(x) in nouns or to_you(x) for x in t):
        return tuple(c["you"])
    first = norm(t[0]) if t else ""
    if t and (in_lex(t[0], LEX["imperatives"]) or re.fullmatch(c["negative_command_re"], first)):
        return c["command"][0], c["command"][1].format(first=t[0])
    if any(in_lex(x, LEX["me"]) for x in t) or (t and is_arabic(text) and first.endswith(c["me_suffix"])
                                                and len(first) >= c["me_min_len"]):
        return tuple(c["me"])
    return tuple(c["none"])


CHECKS = {"LENGTH": check_length, "SPECIFICITY": check_specificity, "STAKES": check_stakes,
          "FRONTLOAD": check_frontload, "ADDRESS": check_address}


def score_hook(text, screen=None):
    """Five checks, dealbreaker flags, an overall score capped by the weakest property, and a verdict."""
    o = T["overall"]
    checks = {k: dict(zip(("score", "detail"), CHECKS[k](text))) for k in CHECK_NAMES}
    flags = [msg for pat, msg in DEALBREAKERS if pat.search(text)]
    scores = [c["score"] for c in checks.values()]
    overall = clamp(statistics.mean(scores) * o["mean_weight"] + min(scores) * o["min_weight"] - len(flags) * o["flag_penalty"])
    verdict = ("STRONG" if overall >= o["strong"] and min(scores) >= o["strong_min"] and not flags
               else "OK" if overall >= o["ok"] else "WEAK")
    result = {"hook": text.strip(), "score": round(overall, 1), "verdict": verdict,
              "weakest": min(checks, key=lambda k: checks[k]["score"]), "checks": checks, "flags": flags,
              "language": _lang(text)}
    if screen is not None:
        s, n = T["screen"], len(tokens(screen))
        result["screen"] = {"text": screen, "words": n, "ok": n <= s["max_words"],
                            "note": s["ok"] if n <= s["max_words"] else s["too_long"].format(n=n, max=s["max_words"])}
    return result


def rank_hooks(lines):
    return sorted((score_hook(line) for line in lines), key=lambda r: -r["score"])


# ---------------------------------------------------------------- beat sheet
def content_words(text):
    out = set()
    for t in tokens(text):
        v = variants(t)
        if not (v & LEX["stop"]) and len(norm(t)) > 2:
            out |= v
    return out


def beat_sheet(raw, wpm=None, target=None):
    """Timed beats (one per sentence) with flags: long hook, long beat, abstract runs, missing loop, off target."""
    c = T["beats"]
    lines = [s.strip() for s in P["split"].findall(raw) if s.strip() and tokens(s)]
    wpm = T["wpm"][_lang(raw)] if wpm is None else wpm
    rows, t = [], 0.0
    for i, line in enumerate(lines):
        n = len(tokens(line))
        dur = n / (wpm / 60) + c["breath"]
        rows.append({"n": i + 1, "start": round(t, 2), "dur": round(dur, 2), "words": n,
                     "text": line, "concrete": bool(concrete_markers(line)), "flags": []})
        t += dur
    if not rows:
        return {"beats": [], "total": 0, "wpm": wpm, "flags": [c["empty"]], "notes": []}
    flags, notes = [], []
    if rows[0]["dur"] > c["hook_window"]:
        rows[0]["flags"].append(c["long_hook"].format(dur=rows[0]["dur"], win=c["hook_window"]))
    run = 0
    for r in rows:
        if r["dur"] > c["max_beat"]:
            r["flags"].append(c["long_beat"].format(dur=r["dur"]))
    for r in rows:
        run = 0 if r["concrete"] else run + 1
        if run == c["concrete_run"]:
            r["flags"].append(c["abstract_run"])
    hook_words = set()
    for r in rows[:-1] or rows:
        if r["start"] < c["hook_window"]:
            hook_words |= content_words(r["text"])
    loop = sorted(hook_words & content_words(rows[-1]["text"]))
    if len(rows) > 1 and loop:
        notes.append(c["loop"].format(words="، ".join(loop[:3])))
    elif len(rows) > 1:
        flags.append(c["no_loop"])
    total = round(t, 1)
    if target:
        if total > target * c["too_long_factor"]:
            flags.append(c["too_long"].format(total=total, target=target))
        elif total < target * c["too_short_factor"]:
            flags.append(c["too_short"].format(total=total, target=target))
    if total > c["max_total"]:
        notes.append(c["over_max"])
    flags += [c["beat_flag"].format(n=r["n"], flag=f) for r in rows for f in r["flags"]]
    return {"beats": rows, "total": total, "wpm": wpm, "target": target, "flags": flags, "notes": notes, "clean": not flags}


# ---------------------------------------------------------------- clean (humanizer)
def clean_text(text, fix=False):
    """Hidden characters, long dashes, written-Arabic slop and flat rhythm; --fix strips the first two."""
    c, found = T["clean"], []
    for kind in ("invisible", "dash"):
        hits = P[kind].findall(text)
        if hits:
            found.append({"kind": kind, "count": len(hits), "note": c[kind]})
    low = norm(text)
    for phrase, why in SLOP:
        n = low.count(norm(phrase))
        if n:
            found.append({"kind": "slop", "phrase": phrase, "count": n, "note": why})
    fixed = text
    if fix:
        fixed = P["dash"].sub(c["dash_fix"][_lang(text)], P["invisible"].sub("", fixed))
        fixed = unicodedata.normalize("NFC", fixed)
    lens = [len(tokens(s)) for s in P["split"].findall(text) if tokens(s)]
    spread = statistics.pstdev(lens) if len(lens) > 1 else 0.0
    if len(lens) >= c["rhythm_min"] and spread < c["rhythm_spread"]:
        found.append({"kind": "rhythm", "count": len(lens), "note": c["rhythm"].format(spread=spread)})
    penalty = sum(min(f["count"], c["cap"]) * (c["slop_penalty"] if f["kind"] == "slop" else c["other_penalty"]) for f in found)
    human = clamp(100 - penalty)
    return {"human_score": round(human, 1), "verdict": "PASS" if human >= c["pass"] else "FIX",
            "found": found, "fixed": fixed if fix else None,
            "auto_fixed": [f["kind"] for f in found if f["kind"] in ("invisible", "dash")] if fix else []}
