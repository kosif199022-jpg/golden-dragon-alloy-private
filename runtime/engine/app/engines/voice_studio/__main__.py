"""python -m engines.voice_studio [--json] [--url URL] doctor|voices|speak|transcribe|clone|design|verify   |   --self-test

  doctor                                  what can run here, and the install line for the rest
  voices [--engine E] [--lang ar]         voices of one engine
  speak "TEXT" | --file F --out OUT [--engine E] [--voice V] [--rate +0%] [--words words.json]
  transcribe AUDIO --out OUT.(json|srt|vtt|txt) [--engine E] [--model small] [--lang ar] [--words W]
  clone REF --name NAME --i-own-this-voice [--ref-text T] [--lang L]       (VoiceStudio only)
  design "DESCRIPTION" --name NAME [--save]                                 (VoiceStudio only)
  verify AUDIO                            measured duration, codec, sample rate, loudness
Bad input: exit 2."""
import argparse
import json
import sys
from pathlib import Path

from . import (Fail, VoiceStudio, clone, design, doctor, edge_words, fmt_ts, lang_of, speak,
               to_subtitles, transcribe, verify_audio, voices)


OPT, REQ, FLAG = {}, {"required": True}, {"action": "store_true"}
SPEC = {"doctor": [],
        "voices": [("--engine", {"default": "edge", "choices": ["voicestudio", "edge", "piper"]}), ("--lang", OPT)],
        "speak": [("text", {"nargs": "?"}), ("--file", OPT), ("--out", REQ), ("--voice", OPT), ("--words", OPT),
                  ("--engine", {"default": "auto", "choices": ["auto", "voicestudio", "edge", "piper"]}),
                  ("--rate", {"default": "+0%"})],
        "transcribe": [("audio", OPT), ("--out", REQ), ("--model", {"default": "small"}), ("--lang", OPT), ("--words", OPT),
                       ("--engine", {"default": "auto", "choices": ["auto", "voicestudio", "whisper"]})],
        "clone": [("ref", OPT), ("--name", REQ), ("--ref-text", {"default": ""}), ("--lang", {"default": "Auto"}),
                  ("--i-own-this-voice", {**FLAG, "dest": "consent"})],
        "design": [("description", OPT), ("--name", REQ),
                   ("--save", {**FLAG, "help": "create the profile (default: only show the mapping)"})],
        "verify": [("audio", OPT)]}


def self_test() -> int:
    ev = [{"type": "WordBoundary", "offset": 1_000_000, "duration": 5_875_000, "text": "أهلاً"},
          {"type": "WordBoundary", "offset": 5_000_000, "duration": 2_000_000, "text": "دي"},
          {"type": "SentenceBoundary", "offset": 0, "duration": 1, "text": "x"}]
    w = edge_words(ev)
    assert [x["word"] for x in w] == ["أهلاً", "دي"], w
    assert w[0]["start"] == 0.1 and w[0]["end"] == 0.5, w  # overlap clipped to the next start
    assert fmt_ts(3725.5, ",") == "01:02:05,500"
    srt = to_subtitles([{"start": 0, "end": 1.25, "text": "سلام"}], "srt")
    assert srt.startswith("1\n00:00:00,000 --> 00:00:01,250\nسلام"), srt
    assert to_subtitles([{"start": 0, "end": 1, "text": "x"}], "vtt").startswith("WEBVTT")
    assert lang_of("hello") == "en" and lang_of("ازيك") == "ar"
    print("voice_studio self-test: ok")
    return 0


def parser():
    ap = argparse.ArgumentParser(prog="python -m engines.voice_studio", description=__doc__.split("\n")[0])
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--url", help="VoiceStudio backend (default $VOICESTUDIO_URL or http://localhost:3900)")
    ap.add_argument("--json", action="store_true")
    sub = ap.add_subparsers(dest="cmd")
    for cmd, args in SPEC.items():
        p = sub.add_parser(cmd)
        for flag, kw in args:
            p.add_argument(flag, **kw)
    return ap


def main(argv=None) -> int:
    for s in (sys.stdout, sys.stderr):
        s.reconfigure(encoding="utf-8")
    ap = parser()
    a = ap.parse_args(argv)
    if a.self_test:
        return self_test()
    if not a.cmd:
        ap.print_help()
        return 2
    vs = VoiceStudio(a.url)
    try:
        text = Path(a.file).read_text(encoding="utf-8") if a.cmd == "speak" and a.file else getattr(a, "text", None)
        res = {"doctor": lambda: doctor(vs), "voices": lambda: voices(a.engine, a.lang, vs),
               "speak": lambda: speak(text, a.out, a.engine, a.voice, a.rate, a.words, vs),
               "transcribe": lambda: transcribe(a.audio, a.out, a.engine, a.model, a.lang, a.words, vs),
               "clone": lambda: clone(a.ref, a.name, a.ref_text, a.lang, a.consent, vs),
               "design": lambda: design(a.description, a.name, a.save, vs),
               "verify": lambda: verify_audio(Path(a.audio))}[a.cmd]()
    except Fail as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False) if a.json else f"error: {e}", file=sys.stderr)
        return e.code
    except FileNotFoundError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    print(json.dumps(res, ensure_ascii=False, indent=None if a.json else 2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
