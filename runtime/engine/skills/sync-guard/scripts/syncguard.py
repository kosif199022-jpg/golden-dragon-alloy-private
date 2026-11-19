#!/usr/bin/env python3
"""sync-guard (حارس التزامن): النص والموشن جرافيك لازم يطلعوا مع الكلمة وهي بتتقال، مش بعدها.

  words MEDIA [--out words.json] [--lang ar] [--model small]   توقيت كل كلمة من الصوت (faster-whisper لو متثبت)
  check MEDIA_OR_WORDS CAPTIONS [--motion cues.json] [--tol 0.12] [--json]
        يقيس كل سطر نص (SRT/ASS/VTT/JSON) وكل حركة قدام الكلمة اللي بتتقال. 0 = متزامن، 1 = فيه تأخير/تقديم، 2 = محتاج عين
  fix MEDIA_OR_WORDS CAPTIONS --out FIXED [--motion cues.json --motion-out FIXED.json] [--lead 0.0] [--hold 0.25]
        يظبط البداية والنهاية على توقيت الكلام نفسه، ويطلع ملف جديد (الأصلي ماحدش بيلمسه)
  onsets MEDIA CAPTIONS   من غير تفريغ: يقارن بدايات السطور ببدايات الكلام (فحص خشن لو مفيش whisper)
  selftest

ملف الكلمات: [{"word": "...", "start": 1.23, "end": 1.6}, ...] (أو {"words": [...]}, أو {"segments": [{"words": [...]}]}).
ملف الموشن: [{"word": "الكلمة", "t": 3.4, "occurrence": 1, "label": "زوم"}]: كل حركة مربوطة بكلمة، و t هو وقتها في المشروع.
الحد الافتراضي 0.12 ثانية (3 فريمات على 25). العين بتلاحظ التأخير من حوالي 0.1.
"""
import argparse, json, os, re, subprocess, sys, tempfile
from pathlib import Path

AR_DIAC = re.compile(r"[ؐ-ًؚ-ٰٟۖ-ۭـ]")


def norm(w):
    w = AR_DIAC.sub("", w.lower())
    w = re.sub("[إأآٱ]", "ا", w).replace("ى", "ي").replace("ة", "ه").replace("ؤ", "و").replace("ئ", "ي")
    return re.sub(r"[^\w]", "", w)


def tokens(t):
    t = re.sub(r"\{[^}]*\}", " ", t)                   # ASS override tags
    t = re.sub(r"<[^>]+>", " ", t).replace("\\N", " ").replace("\\n", " ")
    return [n for n in (norm(x) for x in t.split()) if n]


# ------------------------------------------------------------------ time formats
def ts(s):
    s = s.strip().replace(",", ".")
    p = s.split(":")
    p = [0] * (3 - len(p)) + p
    return int(p[0]) * 3600 + int(p[1]) * 60 + float(p[2])


def srt_ts(t):
    t = max(0, t)
    h, r = divmod(round(t * 1000), 3600000)
    m, r = divmod(r, 60000)
    s, ms = divmod(r, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def ass_ts(t):
    t = max(0, t)
    cs = round(t * 100)
    h, r = divmod(cs, 360000)
    m, r = divmod(r, 6000)
    s, c = divmod(r, 100)
    return f"{h}:{m:02d}:{s:02d}.{c:02d}"


# ------------------------------------------------------------------ readers
def read_words(p):
    p = Path(p)
    if p.suffix.lower() == ".json":
        d = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(d, dict):
            d = d.get("words") or [w for s in d.get("segments", []) for w in s.get("words", [])]
        return [{"word": w.get("word", w.get("text", "")).strip(), "start": float(w["start"]), "end": float(w["end"])} for w in d]
    return transcribe(p)


def transcribe(media, lang="ar", model="small"):
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        sys.exit("مفيش faster-whisper هنا. اعمل: pip install faster-whisper، أو هات ملف الكلمات من library/video-understand/scripts/transcribe.py، "
                 "أو استخدم `onsets` للفحص الخشن.")
    m = WhisperModel(model, compute_type="int8")
    segs, _ = m.transcribe(str(media), language=None if lang == "auto" else lang, word_timestamps=True, vad_filter=True)
    return [{"word": w.word.strip(), "start": round(w.start, 3), "end": round(w.end, 3)} for s in segs for w in (s.words or [])]


def read_cues(p):
    p = Path(p)
    t = p.read_text(encoding="utf-8-sig", errors="replace")
    ext = p.suffix.lower()
    cues = []
    if ext in (".ass", ".ssa"):
        fmt = None
        for i, line in enumerate(t.splitlines()):
            if line.startswith("Format:") and fmt is None and "Start" in line:
                fmt = [x.strip() for x in line[7:].split(",")]
            if line.startswith("Dialogue:"):
                f = fmt or ["Layer", "Start", "End", "Style", "Name", "MarginL", "MarginR", "MarginV", "Effect", "Text"]
                parts = line[9:].split(",", len(f) - 1)
                d = dict(zip(f, parts))
                cues.append({"start": ts(d["Start"]), "end": ts(d["End"]), "text": d.get("Text", ""), "line": i})
    elif ext == ".json":
        d = json.loads(t)
        for c in (d if isinstance(d, list) else d.get("cues", [])):
            cues.append({"start": float(c["start"]), "end": float(c["end"]), "text": c.get("text", "")})
    else:                                                   # SRT / VTT
        for m in re.finditer(r"(\d[\d:.,]*)\s*-->\s*(\d[\d:.,]*)[^\n]*\n(.*?)(?:\n\s*\n|\Z)", t, re.S):
            cues.append({"start": ts(m.group(1)), "end": ts(m.group(2)), "text": m.group(3).strip()})
    return cues


# ------------------------------------------------------------------ alignment
def align(cues, words):
    """Walk the cues in order and find each cue's words in the speech, never going backwards."""
    nw = [norm(w["word"]) for w in words]
    pos = 0
    out = []
    for c in cues:
        tk = tokens(c["text"])
        best = None
        if tk:
            lo = pos
            # search forward from the last match; allow skipping ad-libs. Score = matched tokens, then closeness in time.
            for i in range(lo, len(words)):
                if not _same(nw[i], tk[0]) and not (len(tk) > 1 and _same(nw[i], tk[1])):
                    continue
                j, k, hit, last = i, 0, 0, i
                while j < len(words) and k < len(tk) and j < i + len(tk) + 4:
                    if _same(nw[j], tk[k]):
                        hit, last, k, j = hit + 1, j, k + 1, j + 1
                    elif k + 1 < len(tk) and _same(nw[j], tk[k + 1]):
                        k += 1
                    else:
                        j += 1
                sc = (hit / len(tk), -abs(words[i]["start"] - c["start"]))
                if hit / len(tk) >= 0.5 and (best is None or sc > best[0]):
                    best = (sc, i, last)
                if best and words[i]["start"] - c["start"] > 8:
                    break
        if best:
            _, i, last = best
            pos = last + 1
            out.append(dict(c, said_start=words[i]["start"], said_end=words[last]["end"], match=round(best[0][0], 2), wi=(i, last)))
        else:
            out.append(dict(c, said_start=None, said_end=None, match=0.0, wi=None))
    return out


def _same(a, b):
    if a == b:
        return True
    if len(a) >= 3 and len(b) >= 3 and (a.startswith(b) or b.startswith(a)):       # «والكلام» vs «الكلام»
        return True
    for p in ("و", "ف", "ب", "ل", "ال", "وال", "بال", "فال", "لل"):
        if a.startswith(p) and a[len(p):] == b or b.startswith(p) and b[len(p):] == a:
            return True
    return False


def find_word(words, w, occ=1, after=0.0):
    n, seen = norm(w), 0
    for x in words:
        if x["start"] + 1e-6 >= after and _same(norm(x["word"]), n):
            seen += 1
            if seen == occ:
                return x
    return None


def check(words, cues, motion=(), tol=0.12, end_tol=0.6):
    rows, fails, warns = [], [], []
    for c in align(cues, words):
        if c["said_start"] is None:
            warns.append(f"«{c['text'][:40]}» ({srt_ts(c['start'])}): النص ده مش متقال في الصوت. لو مكتوب من عندك، ده ممنوع (النص بالحرف أو مفيش).")
            continue
        off = c["start"] - c["said_start"]
        eo = c["end"] - c["said_end"]
        r = {"text": c["text"][:50], "start": c["start"], "said": c["said_start"], "offset": round(off, 3), "end_offset": round(eo, 3), "match": c["match"]}
        rows.append(r)
        if abs(off) > tol:
            fails.append(f"«{c['text'][:40]}»: بيظهر {'متأخر' if off > 0 else 'بدري'} {abs(off):.2f} ث (الكلام بيبدأ {srt_ts(c['said_start'])}، النص {srt_ts(c['start'])})")
        if eo < -tol:
            fails.append(f"«{c['text'][:40]}»: بيختفي قبل ما الكلام يخلص بـ {-eo:.2f} ث")
        elif eo > end_tol:
            warns.append(f"«{c['text'][:40]}»: فاضل على الشاشة {eo:.2f} ث بعد الكلام")
    for i in range(len(cues) - 1):
        if cues[i]["end"] > cues[i + 1]["start"] + 0.01:
            warns.append(f"سطرين فوق بعض: «{cues[i]['text'][:25]}» و«{cues[i + 1]['text'][:25]}»")
    mrows = []
    for m in motion:
        w = find_word(words, m["word"], int(m.get("occurrence", 1)))
        if not w:
            warns.append(f"الحركة «{m.get('label', '')}» مربوطة بكلمة «{m['word']}» مش موجودة في الكلام")
            continue
        off = float(m["t"]) - w["start"]
        mrows.append({"label": m.get("label", ""), "word": m["word"], "t": m["t"], "said": w["start"], "offset": round(off, 3)})
        if abs(off) > tol:
            fails.append(f"الحركة «{m.get('label', m['word'])}»: {'متأخرة' if off > 0 else 'بدري'} {abs(off):.2f} ث عن كلمة «{m['word']}» ({srt_ts(w['start'])})")
    offs = [abs(r["offset"]) for r in rows] + [abs(r["offset"]) for r in mrows]
    code = 1 if fails else (2 if warns else 0)
    return {"ok": code == 0, "code": code, "max_offset": round(max(offs), 3) if offs else None,
            "mean_offset": round(sum(offs) / len(offs), 3) if offs else None, "cues": rows, "motion": mrows, "fails": fails, "warns": warns}


def fixed_times(words, cues, lead=0.0, hold=0.25):
    al = align(cues, words)
    out = []
    for k, c in enumerate(al):
        if c["said_start"] is None:
            out.append((c["start"], c["end"]))
            continue
        s = c["said_start"] - lead
        e = c["said_end"] + hold
        nxt = next((x["said_start"] - lead for x in al[k + 1:] if x["said_start"] is not None), None)
        if nxt is not None:
            e = min(e, nxt - 0.01)
        out.append((round(s, 3), round(max(e, c["said_end"]), 3)))
    return out


def write_fixed(src, cues, times, dst):
    src, dst = Path(src), Path(dst)
    ext = src.suffix.lower()
    if ext in (".ass", ".ssa"):
        lines = src.read_text(encoding="utf-8-sig").splitlines()
        for c, (s, e) in zip(cues, times):
            l = lines[c["line"]]
            head, rest = l.split(":", 1)
            p = rest.split(",", 3)
            p[1], p[2] = ass_ts(s), ass_ts(e)
            lines[c["line"]] = head + ":" + ",".join(p)
        dst.write_text("\n".join(lines) + "\n", encoding="utf-8")
    elif ext == ".json":
        dst.write_text(json.dumps([dict(text=c["text"], start=s, end=e) for c, (s, e) in zip(cues, times)], ensure_ascii=False, indent=1), encoding="utf-8")
    else:
        vtt = ext == ".vtt"
        L = ["WEBVTT", ""] if vtt else []
        for i, (c, (s, e)) in enumerate(zip(cues, times), 1):
            a, b = srt_ts(s), srt_ts(e)
            if vtt:
                a, b = a.replace(",", "."), b.replace(",", ".")
            L += ([] if vtt else [str(i)]) + [f"{a} --> {b}", c["text"], ""]
        dst.write_text("\n".join(L), encoding="utf-8")


def fixed_motion(words, motion, lead=0.0):
    out = []
    for m in motion:
        w = find_word(words, m["word"], int(m.get("occurrence", 1)))
        out.append(dict(m, t=round(w["start"] - lead, 3)) if w else dict(m))
    return out


# ------------------------------------------------------------------ coarse: speech onsets without ASR
def speech_onsets(media, noise="-35dB", d=0.25):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(media), "-af", f"silencedetect=noise={noise}:d={d}", "-f", "null", "-"],
                       capture_output=True, text=True)
    ends = [float(x) for x in re.findall(r"silence_end:\s*([\d.]+)", r.stderr)]
    starts = [float(x) for x in re.findall(r"silence_start:\s*([\d.]+)", r.stderr)]
    first = [0.0] if (not starts or starts[0] > 0.05) else []
    return sorted(first + ends)


def cmd_onsets(a):
    on = speech_onsets(a.media)
    cues = read_cues(a.captions)
    bad = []
    for c in cues:
        near = min(on, key=lambda o: abs(o - c["start"]), default=None)
        if near is not None and abs(c["start"] - near) > a.tol and abs(c["start"] - near) < 1.5:
            bad.append(f"«{c['text'][:40]}» {srt_ts(c['start'])}: أقرب بداية كلام {srt_ts(near)} (فرق {c['start'] - near:+.2f})")
    print("⚠ فحص خشن (من غير تفريغ): " + ("ماحدش بعيد عن بدايات الكلام" if not bad else f"{len(bad)} سطر بعيد عن بداية كلام"))
    for b in bad:
        print("  ❌", b)
    sys.exit(1 if bad else 2)


def load_motion(p):
    if not p:
        return []
    d = json.loads(Path(p).read_text(encoding="utf-8"))
    return d if isinstance(d, list) else d.get("cues", [])


def cmd_words(a):
    w = transcribe(a.media, a.lang, a.model)
    out = Path(a.out or Path(a.media).with_suffix(".words.json"))
    out.write_text(json.dumps(w, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(w)} كلمة ← {out}")


def report(r):
    print({0: "✅ متزامن", 1: "❌ مش متزامن: صلّح قبل التسليم (`fix`)", 2: "⚠ محتاج عين"}[r["code"]]
          + (f" · أكبر فرق {r['max_offset']} ث · المتوسط {r['mean_offset']} ث" if r["max_offset"] is not None else ""))
    for x in r["fails"]:
        print("  ❌", x)
    for x in r["warns"]:
        print("  ⚠", x)


def log_miss(r, a):
    if r["fails"]:
        home = Path(os.environ.get("RED_DRAGON_HOME") or Path.home() / ".red-dragon") / "sync"
        home.mkdir(parents=True, exist_ok=True)
        with open(home / "misses.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps({"captions": str(a.captions), "max_offset": r["max_offset"], "fails": r["fails"][:10]}, ensure_ascii=False) + "\n")


def cmd_check(a):
    r = check(read_words(a.source), read_cues(a.captions), load_motion(a.motion), a.tol)
    print(json.dumps(r, ensure_ascii=False, indent=1)) if a.json else report(r)
    log_miss(r, a)
    sys.exit(r["code"])


def cmd_fix(a):
    words, cues = read_words(a.source), read_cues(a.captions)
    before = check(words, cues, load_motion(a.motion), a.tol)
    write_fixed(a.captions, cues, fixed_times(words, cues, a.lead, a.hold), a.out)
    mo = []
    if a.motion:
        mo = fixed_motion(words, load_motion(a.motion), a.lead)
        Path(a.motion_out or Path(a.motion).with_suffix(".synced.json")).write_text(json.dumps(mo, ensure_ascii=False, indent=1), encoding="utf-8")
    after = check(words, read_cues(a.out), mo, a.tol + a.lead)
    print(f"قبل: أكبر فرق {before['max_offset']} ث ({len(before['fails'])} مشكلة) ← بعد: {after['max_offset']} ث ({len(after['fails'])} مشكلة) ← {a.out}")
    report(after)
    sys.exit(after["code"])


# ------------------------------------------------------------------ v2.12: time anchored to words (ideas studied from hypit-ai/hypit, own code)
SCRIPT_TOK = re.compile(r"@\{(/?)([\w\u0600-\u06FF-]+)(!?)\}|\|\||\[([^\]|]+)\|([^\]]+)\]|\n|[^\s@\[\|]+")


def parse_script(text):
    """Mini script syntax:
       @{name!}            a Moment: the instant the next spoken word starts (a reveal, a punchline, a zoom)
       @{name} … @{/name}  a Selection: the span of those words (B-roll covers it, a board stays while it is said)
       ||                  a caption break: the next caption starts here
       [display|spoken]    what is written on screen vs what is said (ميار مكتوبة، «مايار» متقالة)
       a blank line or a new line also breaks captions."""
    units, marks, breaks = [], [], set()
    open_sel = {}
    for m in SCRIPT_TOK.finditer(text):
        g = m.group(0)
        if m.group(2):
            name = m.group(2)
            if m.group(3):
                marks.append(("moment", name, len(units)))
            elif m.group(1):
                if name not in open_sel:
                    raise ValueError(f"@{{/{name}}} من غير @{{{name}}}")
                marks.append(("selection", name, (open_sel.pop(name), len(units) - 1)))
            else:
                open_sel[name] = len(units)
        elif g in ("||", "\n"):
            breaks.add(len(units))
        elif m.group(4):
            units.append({"display": m.group(4).strip(), "spoken": tokens(m.group(5))})
        else:
            sp = tokens(g)
            if sp:
                units.append({"display": g, "spoken": sp})
    if open_sel:
        raise ValueError("Selection مفتوحة من غير قفلة: " + ", ".join(open_sel))
    return units, marks, breaks


def _edit_ratio(a, b):
    """Levenshtein distance / longer length (0 = same, 1 = nothing in common)."""
    if a == b:
        return 0.0
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return min(1.0, prev[-1] / max(len(a), len(b), 1))


COST_MISS, COST_EXTRA, COST_SPLIT, NEAR = 0.5, 0.35, 0.055, 0.5


def align_units(units, words):
    """Each script unit (one or more spoken tokens) gets the start of its first word and the end of its last.
    v2.13 (from the Golden Bird's speech_sync): one monotone DP over the whole script instead of a greedy 6-word look-ahead,
    so an unsaid word costs a «miss» and no longer makes the next tokens jump to a later repeat. Steps: same/near word
    (edit ratio < 0.5 counts as said: مبسوط/مبصوط, مسؤول/مسئول), miss, extra spoken word, one script token said as two
    (عبدالله ← عبد الله) and two said as one (ما فيش ← مافيش: the spoken word's time is split by letter count)."""
    S = [(ui, tk) for ui, u in enumerate(units) for tk in u["spoken"]]
    T = [norm(w["word"]) for w in words]
    n, m = len(S), len(T)
    out = [dict(u, start=None, end=None) for u in units]
    if not n or not m:
        return out
    INF = float("inf")
    band = max(60, abs(n - m) + 60)
    cost = [[INF] * (m + 1) for _ in range(n + 1)]
    back = [[None] * (m + 1) for _ in range(n + 1)]
    cost[0][0] = 0.0
    for i in range(n + 1):
        centre = i * m // n
        for j in range(max(0, centre - band), min(m, centre + band) + 1):
            c = cost[i][j]
            if c == INF:
                continue
            steps = []
            if i < n and j < m:
                steps.append((i + 1, j + 1, 0.0 if _same(T[j], S[i][1]) else _edit_ratio(S[i][1], T[j]), "sub"))
            if i < n:
                steps.append((i + 1, j, COST_MISS, "miss"))
            if j < m:
                steps.append((i, j + 1, COST_EXTRA, "extra"))
            if i < n and j + 1 < m and S[i][1] == T[j] + T[j + 1]:
                steps.append((i + 1, j + 2, COST_SPLIT, "1:2"))
            if i + 1 < n and j < m and S[i][1] + S[i + 1][1] == T[j]:
                steps.append((i + 2, j + 1, COST_SPLIT, "2:1"))
            for a, b, k, kind in steps:
                if c + k < cost[a][b]:
                    cost[a][b], back[a][b] = c + k, (i, j, kind)
    took = [[] for _ in range(n)]          # per script token: (spoken index, from, to) as fractions of that word's time
    i, j = n, m
    while (i, j) != (0, 0):
        pi, pj, kind = back[i][j]
        if kind == "sub" and (_same(T[pj], S[pi][1]) or _edit_ratio(S[pi][1], T[pj]) < NEAR):
            took[pi].append((pj, 0.0, 1.0))
        elif kind == "1:2":
            took[pi] += [(pj, 0.0, 1.0), (pj + 1, 0.0, 1.0)]
        elif kind == "2:1":
            f = len(S[pi][1]) / max(1, len(S[pi][1]) + len(S[pi + 1][1]))
            took[pi].append((pj, 0.0, f))
            took[pi + 1].append((pj, f, 1.0))
        i, j = pi, pj
    for ti, (ui, _) in enumerate(S):
        for k, f0, f1 in took[ti]:
            w = words[k]
            d = w["end"] - w["start"]
            s, e = round(w["start"] + f0 * d, 3), round(w["start"] + f1 * d, 3)
            o = out[ui]
            o["start"] = s if o["start"] is None else min(o["start"], s)
            o["end"] = e if o["end"] is None else max(o["end"], e)
    return out


def compile_script(text, words, max_words=4, gap=0.45):
    units, marks, breaks = parse_script(text)
    al = align_units(units, words)
    missing = [u["display"] for u in al if u["start"] is None]
    cues, cur = [], []
    for i, u in enumerate(al):
        if u["start"] is None:
            continue
        if cur and (i in breaks or len(cur) >= max_words or u["start"] - cur[-1]["end"] > gap):
            cues.append(cur)
            cur = []
        cur.append(u)
    if cur:
        cues.append(cur)
    cue_objs = [{"start": c[0]["start"], "end": c[-1]["end"], "text": " ".join(x["display"] for x in c),
                 "words": [{"w": x["display"], "start": x["start"], "end": x["end"]} for x in c]} for c in cues]
    moments, selections = {}, {}
    for kind, name, at in marks:
        if kind == "moment":
            nxt = next((u for u in al[at:] if u["start"] is not None), None)
            moments[name] = nxt["start"] if nxt else None
        else:
            seg = [u for u in al[at[0]:at[1] + 1] if u["start"] is not None]
            selections[name] = [round(seg[0]["start"], 3), round(seg[-1]["end"], 3)] if seg else None
    return {"cues": cue_objs, "moments": moments, "selections": selections, "missing": missing}


def resolve_events(events, comp, words):
    """events: [{"label": "zoom", "at": "claim"}, {"label": "broll", "span": "proof"}, {"label": "pop", "word": "الدنيا", "occurrence": 1}]
       optional "offset" (s), "dur" (s). Output gets absolute t / start / end, so changing the voice re-flows everything."""
    out, errs = [], []
    for e in events:
        off = float(e.get("offset", 0))
        r = dict(e)
        if "at" in e:
            t = comp["moments"].get(e["at"])
            if t is None:
                errs.append(f"«{e.get('label', '')}»: الـ Moment «{e['at']}» مش موجودة أو كلمتها ماتقالتش")
                continue
            r["t"] = round(t + off, 3)
        elif "span" in e:
            s = comp["selections"].get(e["span"])
            if not s:
                errs.append(f"«{e.get('label', '')}»: الـ Selection «{e['span']}» مش موجودة")
                continue
            r["start"], r["end"] = round(s[0] + off, 3), round(s[1] + float(e.get("tail", 0)), 3)
        elif "word" in e:
            w = find_word(words, e["word"], int(e.get("occurrence", 1)))
            if not w:
                errs.append(f"«{e.get('label', '')}»: الكلمة «{e['word']}» ماتقالتش")
                continue
            r["t"] = round(w["start"] + off, 3)
        if "dur" in e and "t" in r:
            r["end"] = round(r["t"] + float(e["dur"]), 3)
        out.append(r)
    return out, errs


def ass_color(h):
    h = h.lstrip("#")
    return f"&H00{h[4:6]}{h[2:4]}{h[0:2]}&".upper()


def karaoke_ass(cues, font="Arial", size=72, base="#FFFFFF", hi="#FFD60A", outline="#000000", w=1080, h=1920, margin_v=420):
    L = ["[Script Info]", "ScriptType: v4.00+", f"PlayResX: {w}", f"PlayResY: {h}", "WrapStyle: 2", "",
         "[V4+ Styles]",
         "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
         f"Style: Karaoke,{font},{size},{ass_color(hi)},{ass_color(base)},{ass_color(outline)},&H64000000&,-1,0,0,0,100,100,0,0,1,5,0,2,60,60,{margin_v},1",
         "", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"]
    for c in cues:
        parts, t = [], c["start"]
        for x in c["words"]:
            pre = max(0, round((x["start"] - t) * 100))
            if pre:
                parts.append(f"{{\\k{pre}}}")
            parts.append(f"{{\\kf{max(1, round((x['end'] - x['start']) * 100))}}}{x['w']} ")
            t = x["end"]
        L.append(f"Dialogue: 0,{ass_ts(c['start'])},{ass_ts(c['end'] + 0.15)},Karaoke,,0,0,0,,{''.join(parts).rstrip()}")
    return "\n".join(L) + "\n"


def lock_style(name):
    """Take font and colours from a reference-lock (rd.py ref lock NAME …) so captions use the reference's exact look."""
    home = Path(os.environ.get("RED_DRAGON_HOME") or Path.home() / ".red-dragon") / "refs" / name / "lock.json"
    if not home.is_file():
        sys.exit(f"مفيش قفل مرجع باسم {name}")
    lk = json.loads(home.read_text(encoding="utf-8"))
    cols = [c["hex"] for c in lk.get("colors", [])]
    return {"font": (lk.get("fonts") or [{}])[0].get("family"), "colors": cols}


def cmd_script(a):
    words = read_words(a.source)
    comp = compile_script(Path(a.script).read_text(encoding="utf-8"), words, a.max_words, a.gap)
    if a.events:
        ev, errs = resolve_events(json.loads(Path(a.events).read_text(encoding="utf-8")), comp, words)
        comp["events"], comp["event_errors"] = ev, errs
    out = Path(a.out)
    out.write_text(json.dumps(comp, ensure_ascii=False, indent=1), encoding="utf-8")
    if a.srt:
        write_fixed(Path("x.json"), [{"text": c["text"]} for c in comp["cues"]], [(c["start"], c["end"]) for c in comp["cues"]], Path(a.srt))
    if a.ass:
        st = {"font": a.font, "hi": a.hi, "base": a.base}
        if a.lock:
            ls = lock_style(a.lock)
            st["font"] = ls["font"] or st["font"]
            if len(ls["colors"]) >= 2 and not a.keep_colors:
                st["base"], st["hi"] = ls["colors"][0], ls["colors"][1]
        Path(a.ass).write_text(karaoke_ass(comp["cues"], st["font"] or "Arial", a.size, st["base"], st["hi"]), encoding="utf-8")
    print(f"{len(comp['cues'])} كابشن · {len(comp['moments'])} Moment · {len(comp['selections'])} Selection"
          + (f" · {len(comp.get('events', []))} حدث" if a.events else "") + f" ← {out}")
    for m in comp["missing"]:
        print(f"  ⚠ «{m}» في السكربت بس ماتقالتش في الصوت")
    for e in comp.get("event_errors", []):
        print("  ❌", e)
    sys.exit(1 if comp.get("event_errors") else (2 if comp["missing"] else 0))


def word_grid(video, words, out, every=1.0, start=0.0, end=None, cols=4, width=360):
    from PIL import Image, ImageDraw, ImageFont
    if end is None:
        try:
            end = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(video)],
                                       capture_output=True, text=True).stdout.strip())
        except Exception:
            end = (words[-1]["end"] if words else 10.0)
    ts_ = []
    t = start
    while t < end and len(ts_) < 120:
        ts_.append(round(t, 2))
        t += every
    tmp = Path(tempfile.mkdtemp(prefix="grid-"))
    cells = []
    fontp = None
    for cand in ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "C:/Windows/Fonts/arial.ttf", "/System/Library/Fonts/Supplemental/Arial.ttf"):
        if Path(cand).is_file():
            fontp = cand
            break
    font = ImageFont.truetype(fontp, 20) if fontp else ImageFont.load_default()
    kw = {}
    try:
        from PIL import features
        if features.check("raqm"):
            kw = {"direction": "rtl", "language": "ar"}
    except Exception:
        pass
    for i, t in enumerate(ts_):
        f = tmp / f"{i}.png"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", str(video), "-frames:v", "1", "-vf", f"scale={width}:-2", str(f)], capture_output=True)
        im = Image.open(f).convert("RGB") if f.is_file() else Image.new("RGB", (width, int(width * 16 / 9)), "#222")
        said = " ".join(w["word"] for w in words if w["end"] > t - every / 2 and w["start"] < t + every / 2)
        cell = Image.new("RGB", (im.width, im.height + 64), "#111")
        cell.paste(im, (0, 0))
        d = ImageDraw.Draw(cell)
        d.text((8, im.height + 4), f"{t:.1f}s", fill="#FFD60A", font=font)
        if said:
            txt = said if len(said) < 40 else said[:38] + "…"
            try:
                d.text((cell.width - 8, im.height + 32), txt, fill="#FFFFFF", font=font, anchor="ra", **(kw if re.search(r"[\u0600-\u06FF]", txt) else {}))
            except Exception:
                d.text((8, im.height + 32), txt, fill="#FFFFFF", font=font)
        cells.append(cell)
    cw, ch = cells[0].size
    rows = (len(cells) + cols - 1) // cols
    sheet = Image.new("RGB", (cw * cols, ch * rows), "#000")
    for i, c in enumerate(cells):
        sheet.paste(c.resize((cw, ch)), ((i % cols) * cw, (i // cols) * ch))
    sheet.save(out, quality=88)
    return len(cells)


def cmd_grid(a):
    words = read_words(a.words) if a.words else []
    n = word_grid(a.video, words, a.out, a.every, a.start, a.end, a.cols)
    print(f"{n} فريم، كل واحد عليه وقته والكلام اللي بيتقال فيه ← {a.out}")


def cmd_selftest(a):
    tmp = Path(tempfile.mkdtemp(prefix="sync-st-"))
    ok, bad = 0, []

    def t(name, cond):
        nonlocal ok
        ok, _ = (ok + 1, bad) if cond else (ok, bad.append(name))
    words = [{"word": w, "start": s, "end": s + 0.35} for w, s in
             [("أنا", 0.5), ("بحبك", 0.9), ("يا", 1.4), ("قلبي", 1.6), ("والكلام", 2.6), ("ده", 3.1), ("ليكي", 3.3), ("إنتِ", 4.5), ("الدنيا", 4.9), ("كلها", 5.4)]]
    wj = tmp / "w.json"
    wj.write_text(json.dumps(words, ensure_ascii=False), encoding="utf-8")
    srt = tmp / "late.srt"
    srt.write_text("1\n00:00:00,900 --> 00:00:02,000\nانا بحبك يا قلبي\n\n2\n00:00:03,000 --> 00:00:03,300\nالكلام ده ليكي\n\n3\n00:00:04,500 --> 00:00:05,800\nانت الدنيا كلها\n", encoding="utf-8")
    r = check(read_words(wj), read_cues(srt))
    t("late cue caught (0.4s)", r["code"] == 1 and any("متأخر" in f for f in r["fails"]))
    t("early-ending cue caught", any("بيختفي" in f for f in r["fails"]))
    t("arabic normalisation (انا=أنا, انت=إنتِ, الكلام≈والكلام)", all(c["match"] >= 0.99 for c in r["cues"]))
    out = tmp / "fixed.srt"
    write_fixed(srt, read_cues(srt), fixed_times(words, read_cues(srt)), out)
    r2 = check(words, read_cues(out))
    t("fix makes it pass", r2["code"] == 0 and r2["max_offset"] <= 0.01)
    ass = tmp / "a.ass"
    ass.write_text("[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
                   "Dialogue: 0,0:00:01.00,0:00:02.00,Default,,0,0,0,,{\\fad(80,80)}انا بحبك يا قلبي\n"
                   "Dialogue: 0,0:00:02.60,0:00:03.70,Default,,0,0,0,,الكلام ده ليكي\n", encoding="utf-8")
    t("ass late caught", check(words, read_cues(ass))["code"] == 1)
    ao = tmp / "a2.ass"
    write_fixed(ass, read_cues(ass), fixed_times(words, read_cues(ass)), ao)
    t("ass fixed keeps tags + passes", "{\\fad(80,80)}" in ao.read_text(encoding="utf-8") and check(words, read_cues(ao))["code"] == 0)
    mo = [{"word": "قلبي", "t": 2.0, "label": "قلب ينبض"}, {"word": "الدنيا", "t": 4.9, "label": "زوم"}]
    rm = check(words, read_cues(out), mo)
    t("late motion caught, on-time motion ok", rm["code"] == 1 and len([f for f in rm["fails"] if "الحركة" in f]) == 1)
    t("motion fix", check(words, read_cues(out), fixed_motion(words, mo))["code"] == 0)
    inv = tmp / "inv.srt"
    inv.write_text("1\n00:00:00,500 --> 00:00:02,000\nانا بحبك يا قلبي\n\n2\n00:00:06,000 --> 00:00:07,000\nفيديو رومانسي جميل\n", encoding="utf-8")
    t("invented text flagged", any("مش متقال" in w for w in check(words, read_cues(inv))["warns"]))
    au = tmp / "s.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "sine=f=300:d=1", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
                    "-filter_complex", "[1]atrim=0:1[s0];[0]aresample=44100[t];[1]atrim=0:1[s1];[s0][t][s1]concat=n=3:v=0:a=1", str(au)], capture_output=True)
    on = speech_onsets(au) if au.is_file() else []
    t("speech onset ~1.0s", any(abs(o - 1.0) < 0.06 for o in on))
    sc = "@{hook!}انا بحبك @{love}يا قلبي@{/love} || والكلام ده [ليكي|ليكي]\n@{big!}انتِ الدنيا كلها"
    comp = compile_script(sc, words)
    t("script: moment on its word", comp["moments"].get("hook") == 0.5 and comp["moments"].get("big") == 4.5)
    t("script: selection span", comp["selections"].get("love") == [1.4, 1.95])
    t("script: caption breaks (|| and newline)", [c["text"] for c in comp["cues"]] == ["انا بحبك يا قلبي", "والكلام ده ليكي", "انتِ الدنيا كلها"])
    ev, errs = resolve_events([{"label": "zoom", "at": "big"}, {"label": "broll", "span": "love"}, {"label": "pop", "word": "الدنيا", "dur": 0.5},
                               {"label": "x", "at": "nope"}], comp, words)
    t("events resolve + bad anchor reported", len(ev) == 3 and ev[0]["t"] == 4.5 and ev[2]["end"] == 5.4 and len(errs) == 1)
    slow = [dict(w, start=w["start"] * 1.3 + 0.2, end=w["end"] * 1.3 + 0.2) for w in words]
    t("re-flow: slower voice moves the moment", abs(compile_script(sc, slow)["moments"]["big"] - (4.5 * 1.3 + 0.2)) < 1e-6)
    # v2.13 (DP from the Golden Bird): an unsaid word that repeats later must not drag the next words to the repeat
    w2 = [{"word": w, "start": s, "end": e} for w, s, e in [("انا", 0.3, 0.5), ("رايح", 0.6, 0.9), ("البيت", 1.0, 1.4), ("في", 1.5, 1.6),
          ("الاخر", 1.7, 2.1), ("مع", 2.2, 2.3), ("عبد", 2.4, 2.6), ("الله", 2.62, 2.95)]]
    c2 = compile_script("انا رايح في @{h!}البيت || في الاخر مع @{n}عبدالله@{/n}", w2)
    t("script: unsaid repeated word stays missing (DP)", c2["moments"].get("h") == 1.0 and c2["missing"] == ["في"])
    t("script: one word said as two (عبد الله)", c2["selections"].get("n") == [2.4, 2.95])
    c3 = compile_script("ده @{z}ما فيش@{/z} حد", [{"word": "ده", "start": 0.2, "end": 0.4}, {"word": "مافيش", "start": 0.5, "end": 1.1},
                                                {"word": "حد", "start": 1.2, "end": 1.5}])
    t("script: two words said as one (مافيش), time split by letters", c3["selections"].get("z") == [0.5, 1.1]
      and [c["words"][1]["end"] for c in c3["cues"]] == [0.74])
    ka = karaoke_ass(comp["cues"])
    t("karaoke ass has \\kf per word", ka.count("\\kf") == 10 and "Dialogue:" in ka)
    vid = tmp / "v.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc=s=320x568:d=3:r=10", str(vid)], capture_output=True)
    if vid.is_file():
        g = tmp / "g.jpg"
        t("word grid", word_grid(vid, words, g, every=1.0, cols=3) == 3 and g.is_file())
    total = ok + len(bad)
    print(f"{ok}/{total} sync-guard checks" + (f" · فشل: {', '.join(bad)}" if bad else ""))
    sys.exit(0 if not bad else 1)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("words"); s.add_argument("media"); s.add_argument("--out"); s.add_argument("--lang", default="ar"); s.add_argument("--model", default="small")
    s.set_defaults(f=cmd_words)
    for name, fn in (("check", cmd_check), ("fix", cmd_fix)):
        s = sub.add_parser(name); s.add_argument("source", help="ملف الكلمات .json أو الفيديو/الصوت نفسه"); s.add_argument("captions")
        s.add_argument("--motion"); s.add_argument("--tol", type=float, default=0.12); s.add_argument("--json", action="store_true")
        if name == "fix":
            s.add_argument("--out", required=True); s.add_argument("--motion-out"); s.add_argument("--lead", type=float, default=0.0); s.add_argument("--hold", type=float, default=0.25)
        s.set_defaults(f=fn)
    s = sub.add_parser("onsets"); s.add_argument("media"); s.add_argument("captions"); s.add_argument("--tol", type=float, default=0.15); s.set_defaults(f=cmd_onsets)
    s = sub.add_parser("script", help="سكربت بعلامات (@{moment!} و@{sel}…@{/sel} و|| و[مكتوب|متقال]) + كلمات ← كابشن وأحداث مربوطة بالكلام")
    s.add_argument("script"); s.add_argument("source", help="words.json أو الفيديو"); s.add_argument("--out", required=True); s.add_argument("--events")
    s.add_argument("--srt"); s.add_argument("--ass"); s.add_argument("--lock", help="اسم قفل مرجع: الخط والألوان منه"); s.add_argument("--keep-colors", action="store_true")
    s.add_argument("--font", default="Arial"); s.add_argument("--size", type=int, default=72); s.add_argument("--hi", default="#FFD60A"); s.add_argument("--base", default="#FFFFFF")
    s.add_argument("--max-words", type=int, default=4); s.add_argument("--gap", type=float, default=0.45); s.set_defaults(f=cmd_script)
    s = sub.add_parser("grid", help="شبكة فريمات من فيديو، كل فريم عليه وقته والكلام اللي بيتقال فيه (لفهم المرجع)")
    s.add_argument("video"); s.add_argument("--words"); s.add_argument("--out", required=True); s.add_argument("--every", type=float, default=1.0)
    s.add_argument("--start", type=float, default=0.0); s.add_argument("--end", type=float); s.add_argument("--cols", type=int, default=4); s.set_defaults(f=cmd_grid)
    s = sub.add_parser("selftest"); s.set_defaults(f=cmd_selftest)
    a = p.parse_args()
    a.f(a)


if __name__ == "__main__":
    main()
