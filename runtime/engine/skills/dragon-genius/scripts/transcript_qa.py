#!/usr/bin/env python3
"""Dragon Genius transcript / caption QA gate.

Input: whisperX / faster-whisper JSON ({"segments":[{"start","end","text","words":[{"word","start","end","score"?}]}]}
       or a bare list of segments), or an .srt / .vtt file.

Checks:
  noise_ratio    share of tokens that are music notes / [Music] / non-words  (FAIL > 20%)
  tiny_words     words shorter than 0.05 s (FAIL > 10%, WARN > 0)        (OpenMontage QA)
  missing_times  words without start/end (unaligned)                      (WARN)
  low_score      aligned words with score < 0.5                            (WARN > 15%)
  overlap        cues/words that overlap or go backwards in time          (FAIL)
  repetition     same 4-gram repeated >= 4 times in a row (hallucination loop) (FAIL)
  cue_speed      caption reading speed > 20 chars/s or cue < 0.7 s          (WARN)
  cue_length     caption line > 42 chars                                   (WARN)
  frame_snap     with --fps: report how many cue boundaries fall between frames (INFO)

Exit 0 = pass (warnings allowed), 1 = fail, 2 = unreadable input.
"""
import argparse
import json
import re
import sys

NOISE = re.compile(r"^(\W+|\[.*\]|\(.*\)|♪+|♫+|music|موسيقى|applause)$", re.I)


def ts(s):
    s = s.strip().replace(",", ".")
    parts = s.split(":")
    try:
        parts = [float(p) for p in parts]
    except ValueError:
        return None
    while len(parts) < 3:
        parts.insert(0, 0.0)
    return parts[0] * 3600 + parts[1] * 60 + parts[2]


def load(path):
    if path.lower().endswith((".srt", ".vtt")):
        txt = open(path, encoding="utf-8-sig", errors="replace").read()
        cues = []
        for block in re.split(r"\n\s*\n", txt):
            m = re.search(r"([\d:.,]+)\s*-->\s*([\d:.,]+)", block)
            if not m:
                continue
            lines = block.split("\n")
            idx = next(i for i, l in enumerate(lines) if "-->" in l)
            text = " ".join(l.strip() for l in lines[idx + 1:] if l.strip())
            text = re.sub(r"<[^>]+>", "", text)
            cues.append({"start": ts(m.group(1)), "end": ts(m.group(2)), "text": text,
                         "lines": [re.sub(r"<[^>]+>", "", l) for l in lines[idx + 1:] if l.strip()]})
        return cues, []
    data = json.load(open(path, encoding="utf-8"))
    segs = data.get("segments", data) if isinstance(data, dict) else data
    words = []
    for s in segs:
        for w in s.get("words", []) or []:
            words.append(w)
        s.setdefault("lines", [s.get("text", "").strip()])
    return segs, words


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file")
    ap.add_argument("--fps", type=float)
    ap.add_argument("--max-cps", type=float, default=20.0)
    ap.add_argument("--max-line", type=int, default=42)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    try:
        cues, words = load(a.file)
    except (OSError, ValueError, StopIteration) as e:
        print(f"ERROR: cannot read {a.file}: {e}", file=sys.stderr)
        return 2
    if not cues:
        print("ERROR: no segments/cues found", file=sys.stderr)
        return 2

    res = []

    def add(n, st, v, note=""):
        res.append({"check": n, "status": st, "value": v, "note": note})

    tokens = [t for c in cues for t in str(c.get("text", "")).split()]
    noise = [t for t in tokens if NOISE.match(t.strip())]
    nr = len(noise) / len(tokens) if tokens else 1.0
    add("noise_ratio", "FAIL" if nr > 0.20 else ("WARN" if nr > 0.05 else "PASS"),
        f"{nr:.0%} of {len(tokens)} tokens",
        "retry bigger model / VAD / ask user for lyrics SRT; never a .en model on non-English" if nr > 0.20 else "")

    if words:
        timed = [w for w in words if w.get("start") is not None and w.get("end") is not None]
        miss = len(words) - len(timed)
        tiny = [w for w in timed if w["end"] - w["start"] < 0.05]
        tr = len(tiny) / len(timed) if timed else 0
        add("tiny_words", "FAIL" if tr > 0.10 else ("WARN" if tiny else "PASS"),
            f"{len(tiny)}/{len(timed)} (<0.05s)", "clamp before word-highlight sync" if tiny else "")
        add("missing_times", "WARN" if miss else "PASS", f"{miss}/{len(words)} unaligned",
            "digits/symbols? use --suppress_numerals or spell out" if miss else "")
        scored = [w for w in timed if "score" in w]
        if scored:
            low = [w for w in scored if w["score"] < 0.5]
            lr = len(low) / len(scored)
            add("low_score", "WARN" if lr > 0.15 else "PASS", f"{lr:.0%} score<0.5",
                "spot-check these words at the exact frame" if lr > 0.15 else "")
        back = sum(1 for p, n in zip(timed, timed[1:]) if n["start"] < p["start"] - 0.01)
        if back:
            add("word_order", "FAIL", f"{back} words go backwards in time")

    ov = [(i, c["start"], cues[i + 1]["start"]) for i, c in enumerate(cues[:-1])
          if c.get("end") is not None and cues[i + 1].get("start") is not None
          and cues[i + 1]["start"] < c["end"] - 0.01]
    bad_cue = [c for c in cues if c.get("start") is None or c.get("end") is None
               or c["end"] <= c["start"]]
    add("overlap", "FAIL" if ov or bad_cue else "PASS",
        f"{len(ov)} overlaps, {len(bad_cue)} zero/negative cues",
        ("cue %d starts at %.2fs before previous ends" % (ov[0][0] + 2, ov[0][2])) if ov else "")

    toks = [re.sub(r"\W", "", t.lower()) for t in tokens]
    rep = 0
    for n in (4,):
        for i in range(len(toks) - n * 4 + 1):
            g = toks[i:i + n]
            if all(toks[i + k * n:i + (k + 1) * n] == g for k in range(4)) and any(g):
                rep += 1
                break
    add("repetition", "FAIL" if rep else "PASS", "loop detected" if rep else "none",
        "hallucination loop: condition_on_previous_text=False, VAD on" if rep else "")

    fast, short, long_lines = 0, 0, 0
    for c in cues:
        if c.get("start") is None or c.get("end") is None:
            continue
        d = c["end"] - c["start"]
        if d <= 0:
            continue
        chars = len(re.sub(r"\s+", "", c.get("text", "")))
        if chars / d > a.max_cps:
            fast += 1
        if d < 0.7:
            short += 1
        long_lines += sum(1 for l in c.get("lines", []) if len(l) > a.max_line)
    add("cue_speed", "WARN" if fast or short else "PASS",
        f"{fast} too fast (>{a.max_cps:.0f} cps), {short} shorter than 0.7s")
    add("cue_length", "WARN" if long_lines else "PASS", f"{long_lines} lines > {a.max_line} chars")

    if a.fps:
        off = sum(1 for c in cues for t in (c.get("start"), c.get("end"))
                  if t is not None and abs(t * a.fps - round(t * a.fps)) > 0.01)
        add("frame_snap", "INFO", f"{off} boundaries not on a frame at {a.fps:g} fps",
            "renderers round: startFrame = round(start*fps)")

    fails = [r for r in res if r["status"] == "FAIL"]
    verdict = "FAIL" if fails else "PASS"
    if a.json:
        print(json.dumps({"file": a.file, "cues": len(cues), "words": len(words),
                          "verdict": verdict, "checks": res}, ensure_ascii=False, indent=1))
    else:
        print(f"transcript_qa: {a.file}  ({len(cues)} cues, {len(words)} words)")
        for r in res:
            print(f"  [{r['status']:<4}] {r['check']:<13} {r['value']}"
                  + (f"  -> {r['note']}" if r["note"] else ""))
        print(f"VERDICT: {verdict}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
