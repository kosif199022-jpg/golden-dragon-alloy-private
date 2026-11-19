#!/usr/bin/env python3
"""Maven Reels: word times from a voice file. (c) 2026 Maven.
usage: python timestamps.py vo.mp3 words.json [--lang ar] [--model medium]
Writes words.json  {"words": [["word", start], ...], "ends": [...]}
and    words.js    (the same data as window.VOICE, so reel.html can load it with a <script> tag)."""
import argparse
import json
import os


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("audio")
    ap.add_argument("out")
    ap.add_argument("--lang", default="ar")
    ap.add_argument("--model", default="medium")
    a = ap.parse_args()
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        raise SystemExit("faster-whisper is missing. Run: pip install -r requirements.txt")
    model = WhisperModel(a.model, compute_type="int8")
    parts, _ = model.transcribe(a.audio, language=a.lang, word_timestamps=True, vad_filter=True)
    said = [w for p in parts for w in (p.words or [])]
    data = {"words": [[w.word.strip(), round(w.start, 2)] for w in said], "ends": [round(w.end, 2) for w in said]}
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=0)
    js = os.path.splitext(a.out)[0] + ".js"
    with open(js, "w", encoding="utf-8") as f:
        f.write("window.VOICE = " + json.dumps(data, ensure_ascii=False) + ";\n")
    print(f"{a.out} + {os.path.basename(js)}: {len(said)} words, {data['ends'][-1] if said else 0} s")


if __name__ == "__main__":
    main()
