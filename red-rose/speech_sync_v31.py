"""Time follows speech: tie cuts, effects and captions to the spoken words.

Native Red Rose rebuild of the owner's Golden Dragon `speech_sync` idea.
No Golden Dragon code is imported or called at runtime.

The script carries NO seconds, only marks on words:
    @{name} … @{/name}   a range (for a cut, a b-roll, a highlight)
    @{name!}             a moment (the start of the next word)
    ||  or a new line    a caption break
Word times come from the real recording: WhisperX JSON, faster-whisper JSON
with word_timestamps, or Red Rose words.json (a list of {word, start, end}).
A monotone alignment matches script words to spoken words with Arabic
normalisation and handles missing, extra and split words. When the recording
changes, re-run this and every cue follows.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

COST_SPLIT, COST_MISSING, COST_EXTRA = 0.055, 0.5, 0.35
MATCH_WARN = 0.8
_TOKEN = re.compile(r"\|\||\n|@\{(/?)([^}!\s]+)(!?)\}|(?:(?!@\{)[^\s|])+")
_AR_FOLD = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ة": "ه", "ى": "ي", "ؤ": "و", "ئ": "ي"})
_DIACRITICS = re.compile(r"[ً-ٰٟـ]")


def norm_word(w: str) -> str:
    w = _DIACRITICS.sub("", str(w).lower()).translate(_AR_FOLD)
    return re.sub(r"[^\w]", "", w)


def parse_script(text: str):
    """-> (words, ranges {name: [i0, i1]}, moments {name: i}, lines [[i0, i1]])."""
    words, ranges, moments, opened, lines, line_start = [], {}, {}, {}, [], 0
    for m in _TOKEN.finditer(text):
        tok = m.group(0)
        if tok in ("||", "\n"):
            if len(words) > line_start:
                lines.append([line_start, len(words) - 1])
            line_start = len(words)
        elif m.group(2):
            name = m.group(2)
            if m.group(3):
                moments[name] = len(words)
            elif m.group(1):
                if name not in opened:
                    raise ValueError(f"العلامة @{{/{name}}} مالهاش بداية")
                if len(words) == opened[name]:
                    raise ValueError(f"المدى @{{{name}}} فاضي من غير كلام")
                ranges[name] = [opened.pop(name), len(words) - 1]
            else:
                opened[name] = len(words)
        else:
            n = norm_word(tok)
            if n:
                words.append({"w": tok, "n": n})
    if len(words) > line_start:
        lines.append([line_start, len(words) - 1])
    if opened:
        raise ValueError("علامات مفتوحة من غير قفلة: " + ", ".join(opened))
    return words, ranges, moments, lines


def load_words(path) -> list[dict]:
    """[{'w','n','start','end'}] from WhisperX, faster-whisper or Red Rose words.json."""
    d = json.loads(Path(path).expanduser().read_text(encoding="utf-8-sig"))
    if isinstance(d, dict):
        raw = d.get("word_segments") or d.get("words") or [
            w for s in d.get("segments", []) for w in (s.get("words") or [])]
    else:
        raw = d
    out = []
    for w in raw or []:
        if not isinstance(w, dict):
            continue
        text = w.get("word", w.get("text", ""))
        n = norm_word(text)
        if not n:
            continue
        s, e = w.get("start"), w.get("end")
        out.append({"w": str(text).strip(), "n": n,
                    "start": float(s) if s is not None else None,
                    "end": float(e) if e is not None else None})
    if not out:
        raise ValueError("ملف الكلمات فاضي أو مش بصيغة WhisperX / faster-whisper / words.json")
    return out


def _edit_ratio(a: str, b: str) -> float:
    if a == b:
        return 0.0
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return min(1.0, prev[-1] / max(len(a), len(b)))


def align(script: list[dict], spoken: list[dict]) -> list[list[int]]:
    """Monotone DP in a band. For each script word, the spoken-word indexes it took."""
    n, m = len(script), len(spoken)
    band = max(60, abs(n - m) + 60)
    inf = float("inf")
    cost = [[inf] * (m + 1) for _ in range(n + 1)]
    back = [[None] * (m + 1) for _ in range(n + 1)]
    cost[0][0] = 0.0
    S, T = [w["n"] for w in script], [w["n"] for w in spoken]
    for i in range(n + 1):
        centre = i * m // max(n, 1)
        for j in range(max(0, centre - band), min(m, centre + band) + 1):
            c = cost[i][j]
            if c == inf:
                continue
            steps = []
            if i < n and j < m:
                steps.append((i + 1, j + 1, _edit_ratio(S[i], T[j]), "sub"))
            if i < n:
                steps.append((i + 1, j, COST_MISSING, "miss"))
            if j < m:
                steps.append((i, j + 1, COST_EXTRA, "extra"))
            if i < n and j + 1 < m and S[i] == T[j] + T[j + 1]:
                steps.append((i + 1, j + 2, COST_SPLIT, "1:2"))
            if i + 1 < n and j < m and S[i] + S[i + 1] == T[j]:
                steps.append((i + 2, j + 1, COST_SPLIT, "2:1"))
            for a, b, k, kind in steps:
                if c + k < cost[a][b]:
                    cost[a][b], back[a][b] = c + k, (i, j, kind)
    if cost[n][m] == inf:
        raise ValueError("المحاذاة فشلت: السكريبت والتسجيل مختلفين جدًا")
    took = [[] for _ in range(n)]
    i, j = n, m
    while (i, j) != (0, 0):
        pi, pj, kind = back[i][j]
        if kind == "sub" and _edit_ratio(S[pi], T[pj]) < 0.5:
            took[pi].append(pj)
        elif kind == "1:2":
            took[pi] += [pj, pj + 1]
        elif kind == "2:1":
            took[pi].append(pj)
            took[pi + 1].append(pj)
        i, j = pi, pj
    return took


def _time_words(script, spoken, took):
    for w, ids in zip(script, took):
        st = [spoken[k]["start"] for k in ids if spoken[k]["start"] is not None]
        en = [spoken[k]["end"] for k in ids if spoken[k]["end"] is not None]
        w["start"], w["end"], w["matched"] = (min(st), max(en), True) if st and en else (None, None, False)
    if not any(w["start"] is not None for w in script):
        raise ValueError("مفيش ولا كلمة اتطابقت بتوقيت")
    i = 0
    while i < len(script):
        if script[i]["start"] is not None:
            i += 1
            continue
        j = i
        while j < len(script) and script[j]["start"] is None:
            j += 1
        if i > 0:
            left = script[i - 1]["end"]
        elif j < len(script):
            left = max(0.0, script[j]["start"] - 0.4 * (j - i))
        else:
            left = 0.0
        right = script[j]["start"] if j < len(script) else left + 0.4 * (j - i)
        right = max(right, left)
        total = sum(len(script[k]["n"]) for k in range(i, j)) or 1
        t = left
        for k in range(i, j):
            d = (right - left) * len(script[k]["n"]) / total
            script[k]["start"], script[k]["end"] = round(t, 3), round(t + d, 3)
            t += d
        i = j


def _srt_time(t: float) -> str:
    ms = int(round(max(0.0, t) * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def sync(script_text: str, words_path, fps: int = 30):
    """Pure: returns (result, srt_text). Writes nothing."""
    if not 1 <= int(fps) <= 240:
        raise ValueError("fps must be 1..240")
    script, ranges, moments, lines = parse_script(script_text)
    if not script:
        raise ValueError("السكريبت مفيهوش كلام")
    spoken = load_words(words_path)
    _time_words(script, spoken, align(script, spoken))
    fr = lambda t: int(round(t * fps))
    end_all = script[-1]["end"]
    out_ranges = {k: {"start": script[a]["start"], "end": script[b]["end"],
                      "start_f": fr(script[a]["start"]), "end_f": fr(script[b]["end"]),
                      "text": " ".join(w["w"] for w in script[a:b + 1])} for k, (a, b) in ranges.items()}
    out_moments = {}
    for k, i in moments.items():
        t = script[i]["start"] if i < len(script) else end_all
        out_moments[k] = {"t": t, "f": fr(t)}
    caps, srt = [], []
    for n, (a, b) in enumerate(lines, 1):
        s, e = script[a]["start"], max(script[b]["end"], script[a]["start"] + 0.3)
        if caps and s < caps[-1]["end"]:
            s = caps[-1]["end"]
        caps.append({"start": round(s, 3), "end": round(e, 3), "text": " ".join(w["w"] for w in script[a:b + 1])})
        srt.append(f"{n}\n{_srt_time(s)} --> {_srt_time(e)}\n{caps[-1]['text']}\n")
    matched = sum(1 for w in script if w["matched"])
    ratio = round(matched / len(script), 3)
    result = {"fps": int(fps),
              "words": [{"w": w["w"], "start": w["start"], "end": w["end"], "matched": w["matched"]} for w in script],
              "ranges": out_ranges, "moments": out_moments, "captions": caps,
              "stats": {"script_words": len(script), "spoken_words": len(spoken),
                        "matched": matched, "match_ratio": ratio}}
    if ratio < MATCH_WARN:
        result["warning_ar"] = "أقل من 80% من الكلمات اتطابقت: راجع إن السكريبت هو نفس الكلام المتسجّل."
    return result, "\n".join(srt)


def run(script_path, words_path, out_dir=None, fps: int = 30, approve_write: bool = False) -> dict:
    text = Path(script_path).expanduser().read_text(encoding="utf-8-sig")
    result, srt = sync(text, words_path, fps)
    summary = {"ok": True, "stats": result["stats"], "ranges": result["ranges"],
               "moments": result["moments"], "captions": len(result["captions"])}
    if "warning_ar" in result:
        summary["warning_ar"] = result["warning_ar"]
    if not out_dir:
        summary["result"] = result
        summary["srt"] = srt
        return summary
    out = Path(out_dir).expanduser()
    targets = [str(out / "sync.json"), str(out / "captions.srt")]
    if not approve_write:
        return {"ok": False, "outcome": "approval_required", "would_write": targets,
                "hint": "rerun with --approve-write after the owner says yes", "stats": result["stats"]}
    out.mkdir(parents=True, exist_ok=True)
    (out / "sync.json").write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "captions.srt").write_text(srt, encoding="utf-8")
    summary["saved"] = targets
    return summary
