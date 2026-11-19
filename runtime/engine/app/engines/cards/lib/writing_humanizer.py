"""Helpers of power_programs/writing_humanizer.py used by data cards, copied verbatim (the extractor binds a card to them only when
their AST hash with every dependency equals the original's)."""
from __future__ import annotations

from ._lang_common import jaccard
import re
from ._lang_common import sentences
from ._lang_common import words


STOP = set("the a an of to and in is it that this for on with as are was be by at or from we our you your".split())


def content(ws):
    return {w for w in ws if w not in STOP and len(w) > 2}


def keep_informative(context, draft, thresh=0.8):
    seen = set()
    for c in context:
        seen |= content(words(c))
    kept, dropped = [], []
    for s in sentences(draft):
        cw = content(words(s))
        new = cw - seen
        if cw and len(new) / len(cw) < 1 - thresh:
            dropped.append(s)
        else:
            kept.append(s)
            seen |= cw
    return kept, dropped


def act_on(hits):
    """hits: list of (family, strength). strong -> act on one sighting; weak needs another family nearby."""
    if any(s == "strong" for _, s in hits):
        return True
    fams = {f for f, _ in hits}
    return len(fams) >= 2


def voice_stats(text):
    ss = sentences(text)
    n = max(len(words(text)), 1)
    return {"avg_len": sum(len(words(s)) for s in ss) / max(len(ss), 1), "dash_per_100": 100 * text.count("—") / n,
            "allee": text.count("اللى"), "alli": text.count("اللي")}


def voice_distance(a, b):
    return abs(a["avg_len"] - b["avg_len"]) / 10 + abs(a["dash_per_100"] - b["dash_per_100"]) + \
        (1 if (a["allee"] > 0) != (b["allee"] > 0) else 0)


PASSIVE = re.compile(r"\b(is|are|was|were|be|been|being)\s+\w+ed\b(\s+by\b)?", re.I)


OPINION = re.compile(r"\b(I think|I love|I hate|honestly|in my view)\b", re.I)


def genre_check(text, genre, max_len=22):
    issues = []
    if genre in ("technical", "legal", "factual"):
        for s in sentences(text):
            if PASSIVE.search(s):
                issues.append(("passive", s))
            if len(words(s)) > max_len:
                issues.append(("long", s))
            if OPINION.search(s):
                issues.append(("opinion in neutral genre", s))
    return issues


MASK = re.compile(r"```.*?```|`[^`]+`|^---\n.*?\n---\n|\]\([^)]+\)", re.S | re.M)


def file_mode(text, edit):
    out, last = [], 0
    for m in MASK.finditer(text):
        out.append(edit(text[last:m.start()]))
        out.append(m.group(0))
        last = m.end()
    out.append(edit(text[last:]))
    return "".join(out)


def utilize(s):
    return re.sub(r"\butilize\b", "use", s)


def reply_first(convo, draft, reader_known=True):
    if not reader_known:
        return draft, []
    said = set()
    for m in convo:
        said |= content(words(m))
    out, removed = [], []
    for s in sentences(draft):
        cw = content(words(s))
        diag = re.match(r"(first i|then i|after that i|i checked|i looked)", s, re.I)
        restated = cw and len(cw & said) / len(cw) >= 0.7
        if (diag or restated) and "http" not in s:
            removed.append(s)
        else:
            out.append(s)
    return " ".join(out), removed


def self_edit(answer, user_msg):
    ss = sentences(answer)
    fails = []
    if re.match(r"(great question|sure|certainly|absolutely)", ss[0], re.I):
        fails.append(1)
    if re.search(r"\bnot (just|only|merely)? ?\w+[^.]*, but\b|isn't \w+[^.]*; it's", answer, re.I):
        fails.append(2)
    if any(re.search(r"(in short|in summary|ultimately)[,:]", x, re.I) for x in ss[-2:]):
        fails.append(3)
    if re.search(r"hope this helps|let me know if you('d| would) like|i can also", answer, re.I):
        fails.append(4)
    items = [l for l in answer.splitlines() if l.lstrip().startswith(("-", "*"))]
    if items and all(re.match(r"\s*[-*]\s+\*\*[^*]+\*\*", l) for l in items):
        fails.append(5)
    if jaccard(content(words(ss[0])), content(words(user_msg))) > 0.6:
        fails.append(6)
    return fails


RELIGIOUS = ("إن شاء الله", "رحمه الله", "ﷺ", "بسم الله")


LETTER = ("let me know if", "تحية طيبة وبعد", "وتفضلوا بقبول فائق الاحترام", "يسعدني")


def should_skip(passage, written_on, inside_quote=False, discussing_phrase=False):
    if inside_quote or discussing_phrase:
        return "quote or discussion of the phrase"
    if written_on < "2022-11-30":
        return "written before 30 Nov 2022"
    if any(r in passage for r in RELIGIOUS):
        return "religious formula"
    if any(l in passage.lower() for l in LETTER):
        return "human letter formula"
    return None


DETAILS = [re.compile(p, re.I) for p in (r"\([^)]+\)", r"\b(I mean|or rather|أقصد|يعني)\b", r"\bI (chose|picked|decided)\b")]


INVENTED = re.compile(r"\bwhen I (visited|was there|tried)\b|لما زرت", re.I)


def detail_guard(src, new):
    lost = [m.group(0) for rx in DETAILS for m in rx.finditer(src) if m.group(0) not in new]
    invented = bool(INVENTED.search(new) and not INVENTED.search(src))
    return lost, invented


def ar_paragraph_tells(text):
    paras = [p for p in text.split("\n\n") if p.strip()]
    t = {"labels": len(re.findall(r"(^|\s)(أولًا|أولا|ثانيًا|ثانيا|ثالثًا|ثالثا)", text)),
         "tamma": len(re.findall(r"(^|\s)تمّ?\s", text)),
         "chains": len(re.findall(r"القيام بعملية|عملية تطوير|مستوى جودة", text))}
    lens = [len(p.split()) for p in paras]
    t["uniform_paragraphs"] = len(paras) >= 3 and max(lens) - min(lens) <= 2
    return t


DIG = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")


def caption_normalise(text, digits="western"):
    t = re.sub(r"(?<=[؀-ۿ])\s*,", "،", text)
    t = re.sub(r"(?<=[؀-ۿ])\s*\?", "؟", t)
    t = re.sub(r"(?<=[؀-ۿ])\s*;", "؛", t)
    return t.translate(DIG) if digits == "western" else t


def edit_words(words_json, new_texts):
    if words_json.get("source") == "user":
        raise PermissionError("words.json from the user's own voice is read-only")
    return dict(words_json, words=[dict(w, text=t) for w, t in zip(words_json["words"], new_texts)])


EVASION = re.compile(r"undetectable|bypass|turnitin|gptzero|pass (the|an) ai detector|اجعله غير قابل للكشف", re.I)


FORBIDDEN = re.compile(r"(fake|write) (a )?(review|testimonial)s?|sworn statement|peer review|in (his|her) name without", re.I)


def honesty_route(req):
    if FORBIDDEN.search(req):
        return {"action": "decline", "note": "cannot write this as authored by someone else"}
    if EVASION.search(req):
        return {"action": "readability edit", "note": "This is a readability tool; no detector promise. "
                "If your course or venue requires AI disclosure, disclose it."}
    return {"action": "edit", "note": ""}


def invented_terms(src, new):
    s, n = content(words(src)), content(words(new))
    allowed = {"source", "does", "say", "not"}
    return sorted(n - s - allowed)


def house_lint(doc):
    issues = []
    for line in doc.splitlines():
        if line.startswith("#"):
            title = line.lstrip("# ")
            ws = title.split()
            if len(ws) > 1 and all(w[0].isupper() for w in ws if w[0].isalpha()):
                issues.append(("title case heading", title))
        elif re.search(r"\bnot (un|in)\w+|\bnever not\b|\bnot without\b", line, re.I):
            issues.append(("double negative", line))
        elif re.search(r"\b(should|ought to)\b", line) and re.search(r"\brequire|requirement\b", line, re.I):
            issues.append(("use must for requirements", line))
    terms = [t for t in ("token", "key", "credential") if re.search(rf"\b{t}s?\b", doc, re.I)]
    if len(terms) > 1:
        issues.append(("synonym cycling", ",".join(terms)))
    return issues
