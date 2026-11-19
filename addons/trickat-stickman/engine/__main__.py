"""Trickat StickMan engine CLI.  python3 -m engine <command> <project_dir> [options]

  srt       <P> [--srt F] [--max-len 8] [--offset S]   voice.* + subtitles .srt -> P/timing.json (MAIN PATH)
            each subtitle cue = one numbered unit; long cues are split; a shifted SRT is detected and corrected
  sentences <P>                 list the numbered units (from timing.json, else script.txt) to use in story.json
  join      <P> a.mp3 b.mp3 ..  join voiceover parts into P/voice.wav (0.45 s pauses)
  align     <P>                 voice.* + script.txt -> P/timing.json (English speech model; NOT for Arabic)
  plan      <P>                 check story.json against the timing; print the shot table
  stills    <P> [--shots 0,5,9] [--fracs .3,.7] [--full]   contact sheets in P/work/sheet_*.jpg
            (--full: full-size frames P/work/still_*.jpg, to read Arabic text closely)
  render    <P> [--jobs N] [--shots ...] [--res 720]   render shot segments (resumable) + concat
            (--res 720 = fast 1280x720 draft/final; the default is 1920x1080. Use the same --res for final.)
  audio     <P> [--mood M]      music + SFX + mix + loudness -> P/work/mix.wav
  final     <P> [--title T]     mux -> P/out/<title>.mp4
  all       <P>                 srt/align (if needed), plan, render, audio, final
"""
import json, os, sys, time

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); __package__ = "engine"


def arg(name, default=None):
    if name in sys.argv:
        i = sys.argv.index(name); return sys.argv[i + 1]
    return default


def find_srt(P):
    c = sorted(f for f in os.listdir(P) if f.lower().endswith(".srt")) if os.path.isdir(P) else []
    return os.path.join(P, c[0]) if c else None


def ints(s): return [int(x) for x in s.split(",")] if s else None


def main():
    if len(sys.argv) < 3: print(__doc__); return
    cmd, P = sys.argv[1], os.path.abspath(sys.argv[2])
    if arg("--res"): os.environ["RM_RES"] = arg("--res")  # must be set before the kit is imported (workers inherit it)
    from .timing import sentences, align, from_srt
    if cmd == "join":  # join numbered voice parts into P/voice.wav with 0.45 s pauses
        import subprocess
        parts = sys.argv[3:]; lst = os.path.join(P, "parts.txt"); gap = os.path.join(P, "gap.wav")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono", "-t", "0.45", gap], check=True)
        norm_ = []
        for i, p in enumerate(parts):
            q = os.path.join(P, f"part{i:02d}.wav"); subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", p, "-ac", "1", "-ar", "48000", q], check=True); norm_.append(q)
        with open(lst, "w") as fh:
            for i, q in enumerate(norm_): fh.write(("" if i == 0 else f"file '{gap}'\n") + f"file '{q}'\n")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, os.path.join(P, "voice.wav")], check=True)
        for q in norm_ + [gap, lst]: os.remove(q)
        print("joined", len(parts), "parts ->", os.path.join(P, "voice.wav")); return
    tj = os.path.join(P, "timing.json")
    if cmd == "srt" or (cmd == "all" and not os.path.exists(tj) and find_srt(P)):
        from .render import voice_path
        src = arg("--srt") or find_srt(P)
        if not src: raise SystemExit(f"no .srt file in {P}: copy the subtitles there (e.g. {P}/subs.srt) or pass --srt FILE")
        off = arg("--offset"); T, notes = from_srt(src, voice_path(P), float(arg("--max-len", 8)), None if off is None else float(off))
        json.dump(T, open(tj, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
        with open(os.path.join(P, "script.txt"), "w", encoding="utf-8") as fh: fh.write("\n".join(s["text"] for s in T["sentences"]) + "\n")
        for n in notes: print(n)
        print(f"srt: {T['cues']} cues -> {len(T['sentences'])} units, {T['duration']:.1f} s of voice, offset {T['offset']:+.2f}s"
              + (f", speech inside subtitle time {T['speech_cover']:.0%}" if T.get('speech_cover') is not None else ""))
        if T.get("speech_cover") is not None and T["speech_cover"] < .6: print("WARNING: little speech inside the subtitle times: check that the SRT belongs to this voiceover")
        long_ = [s["i"] for s in T["sentences"] if s["end"] - s["start"] > 9]; short_ = [s["i"] for s in T["sentences"] if s["end"] - s["start"] < .3]
        if long_: print("long units (>9 s):", long_)
        if short_: print("very short units (<0.3 s):", short_)
        if cmd == "srt": cmd = "sentences"
    if cmd == "sentences" and os.path.exists(tj):
        T = json.load(open(tj, encoding="utf-8"))
        for s in T["sentences"]: print(f"{s['i']:3d}  {s['start']:7.2f}-{s['end']:7.2f}  {s['text']}")
        print(f"\n{len(T['sentences'])} units, {T['duration'] / 60:.2f} min of voice (method={T['method']})"); return
    if cmd == "sentences":
        ss = sentences(open(os.path.join(P, "script.txt"), encoding="utf-8").read()); nw = sum(len(s.split()) for s in ss)
        for i, s in enumerate(ss): print(f"{i:3d}  {s}")
        print(f"\n{len(ss)} sentences, {nw} words, about {nw / 130:.1f} min at about 130 Arabic words per minute ({nw / 115:.1f}-{nw / 145:.1f} min)"); return
    if cmd in ("align", "all") and (cmd == "align" or not os.path.exists(tj)):
        from .render import voice_path
        ss = sentences(open(os.path.join(P, "script.txt"), encoding="utf-8").read()); t = time.time()
        T = align(ss, voice_path(P)); json.dump(T, open(os.path.join(P, "timing.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
        print(f"aligned {len(T['sentences'])} sentences, {T['duration']:.1f} s of voice, method={T['method']} matched={T['matched']:.0%} ({time.time() - t:.0f}s)")
        if T["method"] == "fallback": print("WARNING: no speech model; timing is estimated from pauses. Check the plan carefully.")
        bad = [s for s in T["sentences"] if s["end"] - s["start"] < .25]
        if bad: print("very short sentences (check):", [s["i"] for s in bad])
        if cmd == "align": return
    if cmd in ("plan", "all"):
        from .render import load_project, whip_flags
        story, tl, cast = load_project(P); wh = whip_flags(tl)
        for s, w in zip(tl.shots, wh):
            sp = s["spec"]; rng_ = f"{s['sents'][0]}-{s['sents'][-1]}" if s["sents"] else "silent"
            print(f"#{s['k']:3d} {sp.get('kind', 'wide'):9s} {sp.get('set', ''):8s} {s['t0']:7.2f}-{s['t1']:7.2f} ({s['t1'] - s['t0']:4.1f}s) sents {rng_:9s}{' whip' if w else ''}")
        print(f"\n{len(tl.shots)} shots, {tl.duration / 60:.2f} min, {tl.total_frames} frames")
        for w in tl.warn: print("WARNING:", w)
        # build every shot once so cue warnings and bad params surface before rendering
        from .render import setup, _G
        from .shots import build
        setup(P); n0 = len(tl.warn)
        for s in _G["tl"].shots: build(s, _G["tl"], _G["cast"], _G["env"])
        for w in _G["tl"].warn[n0:]: print("WARNING:", w)
        if cmd == "plan": return
    if cmd == "stills":
        from .render import stills
        fr = [float(x) for x in arg("--fracs", ".5").split(",")]; stills(P, ints(arg("--shots")), fr, full="--full" in sys.argv); return
    if cmd in ("render", "all"):
        from .render import render_all
        j = arg("--jobs"); render_all(P, int(j) if j else None, ints(arg("--shots")))
        if cmd == "render": return
    if cmd in ("audio", "all"):
        from .audio import build, loudness
        raw = build(P, arg("--mood"), float(arg("--music-db", -17)), float(arg("--sfx-db", -9)))
        loudness(raw, os.path.join(P, "work", "mix.wav"))
        if cmd == "audio": return
    if cmd in ("final", "all"):
        from .audio import mux
        story = json.load(open(os.path.join(P, "story.json"), encoding="utf-8"))
        mux(P, arg("--title", story.get("title", "final"))); return
    if cmd not in ("all",): print(__doc__)


if __name__ == "__main__":
    main()
