#!/usr/bin/env python3
"""onscreen — enforce the owner's v10.12.1 rule: NO description on screen.

    dragon.py tool onscreen check CAPTIONS.ass --words words.json            # his own words (Whisper/WhisperX JSON)
    dragon.py tool onscreen check spec.json --lyrics lyrics.txt              # confirmed song lyrics
    dragon.py tool onscreen check CAPTIONS.srt --words w.json --lyrics l.txt --json
    dragon.py tool onscreen lint-web film.html render.sh                      # fill:'both' exits, xfade without tpad

Rule (SKILL.md, 2026-11-10): what is written on the video is ONLY his words verbatim, confirmed lyrics, or nothing.
No narration of what happens («وقهوتها الدافية»، «الجو برد»، «حكاية حب»). The mandatory credit (©، إخراج، فيسبوك…)
is not a description and stays. If no source was given, ask him first: «أكتب كلامك؟ كلمات الأغنية؟ ولا من غير كتابة؟»

check reads .ass (Dialogue text), .srt, lyric_ass spec .json (lines[].text) or .txt (one line each).
Each line is PASS when at least --threshold (default 0.8) of its words appear in the sources (Arabic normalised:
tashkeel, alef forms, ة/ه, ى/ي, a leading و/ف/ب/ل) AND, for 3+ words, in the same order inside one stretch of the
source (verbatim); ORDER when his words are there but reordered; CREDIT when it matches --allow; else DESCRIPTION.
Exit: 0 pass · 1 description found · 3 no source given (ask him) · 2 input error.
"""
import argparse, json, re, sys
from pathlib import Path

TASHKEEL = re.compile(r"[ؐ-ًؚ-ٰٟۖ-ۭـ]")
CREDIT_DEFAULT = r"©|\(c\)|إخراج|اخراج|مونتاج|تصميم|فيسبوك|facebook|instagram|انستجرام|tiktok|تيك ?توك|@\w+|www\.|\.com"
ASK = "اسأله قبل التصميم: «أكتب كلامك؟ كلمات الأغنية؟ ولا من غير كتابة؟»"


def norm(s):
    s = TASHKEEL.sub("", s)
    s = s.replace("‏", "").replace("‎", "")
    s = re.sub("[إأآٱا]", "ا", s).replace("ة", "ه").replace("ى", "ي").replace("ؤ", "و").replace("ئ", "ي")
    return s.lower()


def words(s):
    return [w for w in re.findall(r"[\w؀-ۿ]+", norm(s)) if w]


# ------------------------------------------------------------------ reading on-screen text
def ass_lines(text):
    out = []
    for line in text.splitlines():
        if line.startswith("Dialogue:"):
            body = line.split(",", 9)[-1]
            body = re.sub(r"\{[^}]*\}", "", body).replace("\\N", " ").replace("\\n", " ").replace("\\h", " ")
            if body.strip():
                out.append(body.strip())
    return out


def srt_lines(text):
    out, buf = [], []
    for line in text.splitlines() + [""]:
        s = line.strip()
        if not s:
            if buf:
                out.append(" ".join(buf)); buf = []
        elif s.isdigit() or "-->" in s:
            continue
        else:
            buf.append(re.sub(r"<[^>]+>", "", s))
    return out


def json_lines(data):
    if isinstance(data, dict):
        items = data.get("lines") or data.get("captions") or data.get("texts") or []
    else:
        items = data
    out = []
    for it in items:
        t = it.get("text") if isinstance(it, dict) else it
        if isinstance(t, str) and t.strip():
            out.append(t.strip())
    return out


def read_onscreen(path):
    p = Path(path)
    text = p.read_text(encoding="utf-8-sig")
    ext = p.suffix.lower()
    if ext == ".ass":
        return ass_lines(text)
    if ext == ".srt":
        return srt_lines(text)
    if ext == ".json":
        return json_lines(json.loads(text))
    return [l.strip() for l in text.splitlines() if l.strip()]


# ------------------------------------------------------------------ reading sources
def words_json(data):
    """Whisper / WhisperX / faster-whisper / kosif-words JSON -> list of words."""
    out = []

    def take(w):
        if isinstance(w, dict):
            v = w.get("word") or w.get("text") or w.get("w")
            if isinstance(v, str):
                out.append(v)
        elif isinstance(w, str):
            out.append(w)

    if isinstance(data, list):
        for w in data:
            take(w)
    elif isinstance(data, dict):
        for w in data.get("words", []) or []:
            take(w)
        for seg in data.get("segments", []) or []:
            if seg.get("words"):
                for w in seg["words"]:
                    take(w)
            elif isinstance(seg.get("text"), str):
                out.append(seg["text"])
        if not out and isinstance(data.get("text"), str):
            out.append(data["text"])
    return out


def source_sequence(words_files, lyrics_files):
    """All source words in their spoken/sung order (one list)."""
    seq = []
    for f in words_files:
        for w in words_json(json.loads(Path(f).read_text(encoding="utf-8-sig"))):
            seq += words(w)
    for f in lyrics_files:
        seq += words(Path(f).read_text(encoding="utf-8-sig"))
    return seq


def source_vocab(words_files, lyrics_files):
    return set(source_sequence(words_files, lyrics_files))


def order_ratio(tokens, seq):
    """Share of the line's words that appear in the SAME ORDER inside one stretch of the source (verbatim check).
    Greedy subsequence match from every start, inside a window of 3x the line length."""
    if not tokens or not seq:
        return 1.0
    best, win = 0, max(6, 3 * len(tokens))
    for i, w in enumerate(seq):
        if w != tokens[0]:
            continue
        k, j = 0, i
        while j < min(len(seq), i + win) and k < len(tokens):
            if seq[j] == tokens[k]:
                k += 1
            j += 1
        best = max(best, k)
        if best == len(tokens):
            break
    return best / len(tokens)


def strip1(w):
    """Drop one attached و/ف/ب/ل (والليل = الليل). Applied to BOTH sides, so a real first letter never mismatches."""
    return w[1:] if len(w) > 2 and w[0] in "وفبل" else w


def check(lines, vocab, allow=CREDIT_DEFAULT, threshold=0.8, seq=None):
    rx = re.compile(allow, re.I)
    rows = []
    svocab = {strip1(v) for v in vocab}
    sseq = [strip1(w) for w in (seq or [])]
    for ln in lines:
        ws = words(ln)
        if rx.search(ln):
            rows.append({"text": ln, "verdict": "CREDIT", "coverage": None}); continue
        if not ws:
            rows.append({"text": ln, "verdict": "PASS", "coverage": 1.0, "note": "punctuation/symbols only"}); continue
        if not vocab:
            rows.append({"text": ln, "verdict": "UNSOURCED", "coverage": None}); continue
        known = lambda w: w in vocab or strip1(w) in svocab          # وحبيبي = حبيبي ، الليل = والليل
        hit = sum(known(w) for w in ws) / len(ws)
        missing = [w for w in ws if not known(w)]
        verdict = "PASS" if hit >= threshold else "DESCRIPTION"
        row = {"text": ln, "coverage": round(hit, 2), "verdict": verdict, "not_in_source": missing[:8]}
        if verdict == "PASS" and sseq and len(ws) >= 3:
            row["order"] = round(order_ratio([strip1(w) for w in ws], sseq), 2)
            if row["order"] < threshold:
                row["verdict"] = "ORDER"        # his words, but not in his order: not verbatim
        rows.append(row)
    return rows


# ------------------------------------------------------------------ web / render lint (lessons 2026-11-10)
LINTS = [
    (re.compile(r"""fill\s*:\s*['"]both['"]"""), "fill:'both' بيرجّع النص باين قبل وقته (أشباح). انيميشن الخروج: fill:'forwards'"),
]


def lint(paths):
    found = []
    for p in paths:
        try:
            text = Path(p).read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            found.append({"file": p, "line": 0, "issue": f"unreadable: {e}"}); continue
        for i, line in enumerate(text.splitlines(), 1):
            for rx, msg in LINTS:
                if rx.search(line):
                    found.append({"file": p, "line": i, "issue": msg})
        if "xfade" in text and "tpad" not in text:
            found.append({"file": p, "line": 0, "issue": "xfade بيقصّر الطول (34.83 بدل 35 ث). حط tpad=stop_mode=clone:stop_duration=1 "
                                                           "على الخلفية قبل الـ overlays، و-t بالمدة"})
    return found


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(prog="dragon.py tool onscreen", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check", help="every on-screen line must be his words, confirmed lyrics or the credit")
    c.add_argument("file"); c.add_argument("--words", action="append", default=[], help="Whisper/WhisperX words JSON (repeatable)")
    c.add_argument("--lyrics", action="append", default=[], help="confirmed lyrics text file (repeatable)")
    c.add_argument("--allow", default=CREDIT_DEFAULT, help="regex for credit lines that are allowed")
    c.add_argument("--threshold", type=float, default=0.8); c.add_argument("--json", action="store_true")
    l = sub.add_parser("lint-web", help="fill:'both' in exit animations, xfade without tpad")
    l.add_argument("files", nargs="+"); l.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)

    if a.cmd == "lint-web":
        f = lint(a.files)
        if a.json:
            print(json.dumps(f, ensure_ascii=False, indent=1))
        else:
            for x in f:
                print(f"{x['file']}:{x['line']}  {x['issue']}")
            print("نضيف" if not f else f"{len(f)} ملاحظة")
        return 1 if f else 0

    try:
        lines = read_onscreen(a.file)
        seq = source_sequence(a.words, a.lyrics)
        vocab = set(seq)
    except (OSError, ValueError) as e:
        print(f"خطأ في القراية: {e}", file=sys.stderr); return 2
    if not 0 < a.threshold <= 1:
        print("--threshold بين 0 و 1", file=sys.stderr); return 2
    rows = check(lines, vocab, a.allow, a.threshold, seq)
    bad = [r for r in rows if r["verdict"] in ("DESCRIPTION", "ORDER")]
    unsourced = [r for r in rows if r["verdict"] == "UNSOURCED"]
    verdict = "FAIL" if bad else ("ASK" if unsourced else "PASS")
    if a.json:
        print(json.dumps({"verdict": verdict, "lines": rows, "ask": ASK if unsourced else None}, ensure_ascii=False, indent=1))
    else:
        for r in rows:
            mark = {"PASS": "✓", "CREDIT": "©", "DESCRIPTION": "✗ وصف", "ORDER": "✗ ترتيب مختلف عن المصدر",
                    "UNSOURCED": "?"}[r["verdict"]]
            extra = f"  (مش في المصدر: {' '.join(r['not_in_source'])})" if r.get("not_in_source") and r["verdict"] == "DESCRIPTION" else ""
            print(f"  {mark}  {r['text']}{extra}")
        print(f"الحكم: {verdict} · {len(rows)} سطر · وصف {len(bad)} · من غير مصدر {len(unsourced)}")
        if bad:
            print("امسح سطور الوصف أو بدّلها بكلامه/كلمات الأغنية بالحرف وبنفس الترتيب. ممنوع شرح اللي بيحصل.")
        if unsourced:
            print(ASK)
    return 1 if bad else (3 if unsourced else 0)


if __name__ == "__main__":
    sys.exit(main())
