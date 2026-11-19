"""python -m engines.talking_head <subcommand> ...

  check                                      what the pipeline needs
  prepare VIDEO [--project DIR] [--name N] [--graded F | --lut CUBE]
  transcribe PROJECT [--language en] [--model small]
  words PROJECT words.json [--gap 0.6] [--language ar]      a word-timed transcript from elsewhere
  cut PROJECT [--remove 2.40-2.72 ...] [--threshold DB] [--pause-sentence 0.22] [--pause-mid 0.14] [--lead] [--trail]
  master PROJECT [--lufs -14] [--true-peak -1.5]
  validate EDL                               exit 1 on errors
  stills EDL T [T ...] [--out-dir DIR] [--workers N]
  render EDL [--out FILE.mp4] [--workers N]
  sheet OUT_DIR CLIP [CLIP ...]              B-roll review: size, length, hard cuts, 6-frame strip
"""
import argparse, sys

from . import project as pj
from .edl import validate
from .render import default_workers, render, stills


def main(argv=None):
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(prog="python -m engines.talking_head", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check")
    p = sub.add_parser("prepare")
    p.add_argument("video"); p.add_argument("--project"); p.add_argument("--name"); p.add_argument("--graded"); p.add_argument("--lut")
    p = sub.add_parser("transcribe")
    p.add_argument("project"); p.add_argument("--language"); p.add_argument("--model")
    p = sub.add_parser("words")
    p.add_argument("project"); p.add_argument("words"); p.add_argument("--gap", type=float, default=pj.CFG["asr"]["gap"]); p.add_argument("--language")
    p = sub.add_parser("cut")
    p.add_argument("project"); p.add_argument("--remove", action="append", default=[]); p.add_argument("--threshold", type=float)
    for k in ("pause-sentence", "pause-mid", "lead", "trail"):
        p.add_argument("--" + k, type=float)
    p = sub.add_parser("master")
    p.add_argument("project"); p.add_argument("--lufs", type=float); p.add_argument("--true-peak", type=float)
    p = sub.add_parser("validate")
    p.add_argument("edl")
    p = sub.add_parser("stills")
    p.add_argument("edl"); p.add_argument("times", nargs="+", type=float); p.add_argument("--out-dir")
    p.add_argument("--workers", type=int, default=default_workers())
    p = sub.add_parser("render")
    p.add_argument("edl"); p.add_argument("--out"); p.add_argument("--workers", type=int, default=default_workers())
    p = sub.add_parser("sheet")
    p.add_argument("out_dir"); p.add_argument("clips", nargs="+")
    a = ap.parse_args(argv)

    if a.cmd == "check":
        rows = pj.check()
        for state, what in rows:
            print("[%-4s] %s" % (state, what))
        return 2 if any(s == "MISS" for s, _ in rows) else 0
    if a.cmd == "prepare":
        r = pj.prepare(a.video, a.project, a.name, a.graded, a.lut)
        print("project ready: %s\n  presenter %dx%d @ %.3f fps, %.2f s" % (r["project_dir"], r["src_w"], r["src_h"], r["src_fps"], r["src_dur"]))
        for n in r["notes"]:
            print("  NOTE: " + n)
    elif a.cmd in ("transcribe", "words"):
        segs = pj.transcribe(a.project, a.language, a.model) if a.cmd == "transcribe" else pj.import_words(a.project, a.words, a.gap, a.language)
        for s in segs:
            print("%6.2f-%6.2f %s" % (s["start"], s["end"], s["text"]))
        print("\nsegments: %d   words: %d" % (len(segs), sum(len(s["words"]) for s in segs)))
    elif a.cmd == "cut":
        pauses = {k: getattr(a, k) for k in ("pause_sentence", "pause_mid", "lead", "trail") if getattr(a, k) is not None}
        r = pj.cut_pauses(a.project, a.remove, a.threshold, **pauses)
        print("threshold %.1f dB (room %.1f, speech %.1f)" % (r["threshold"], r["room"], r["speech"]))
        print("segments %d   program %.2f s   (source %.2f s, removed %.2f s)\n" % (len(r["cuts"]), r["program"], r["source"], r["source"] - r["program"]))
        for c, txt in r["lines"]:
            print("%6.2f-%6.2f -> %6.2f  %s" % (c["src_t0"], c["src_t1"], c["prog_t0"], txt[:90]))
    elif a.cmd == "master":
        r = pj.master(a.project, a.lufs, a.true_peak)
        print("before: %s LUFS, peak %s dBTP\nafter : %s LUFS, peak %s dBTP  -> %s" % (*r["before"], *r["after"], r["path"]))
    elif a.cmd == "validate":
        err, warn, summary = validate(a.edl)
        for e in err:
            print("ERROR  " + e)
        for w in warn:
            print("warn   " + w)
        print("\n" + summary)
        return 1 if err else 0
    elif a.cmd == "stills":
        r = stills(a.edl, a.times, a.out_dir, a.workers)
        for n in r["notes"]:
            print("note: " + n)
        print("stills -> " + r["sheet"])
    elif a.cmd == "render":
        r = render(a.edl, a.out, a.workers)
        for n in r["notes"]:
            print("note: " + n)
        print("done: %s  %dx%d  %.3g fps  %.2f s  audio %s  loudness %s  (%d frames, %.0f s)" % (
            r["out"], r["w"], r["h"], r["fps"], r["dur"], "yes" if r["audio"] else "NO",
            "%.1f LUFS" % r["lufs"] if r["lufs"] is not None else "?", r["frames"], r["seconds"]))
    elif a.cmd == "sheet":
        for r in pj.clip_sheet(a.out_dir, a.clips):
            print("%s | %dx%d | %.2f s | %.2f fps | hard cuts at: %s | %s" % (r["clip"], r["w"], r["h"], r["dur"], r["fps"], r["cuts"] or "none", r["sheet"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
