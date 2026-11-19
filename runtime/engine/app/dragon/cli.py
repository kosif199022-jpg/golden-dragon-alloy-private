"""python -m dragon <command>

  build [--own]          index the local ecosystem (or just bundled tools)
  find "<request>"       best tools, skills, superpowers and powers for a request (Arabic or English)
  show <id|name>         one item in full (path, command, requirements)
  stats                  what the catalog holds
  doctor                 programs and Python modules this machine really has
  probe-tools [--json]   inspect 23 bundled tool adapters without executing them
  ecosystem [--json]     report whether local Superpowers / Atlas roots are present
  plan "<task>" [--mode smart|full] [--json]  thinking + capability plan, no execution
  verify FILE... [--out evidence.json] [--expect 1080x1920] [--duration S] [--no-black]
                         measure outputs; exit 1 if any file fails: black frames inside a film, MP3 audio in MP4,
                         or (with --duration) a video that is not exactly round(S*fps) frames. --no-black skips the scan
  mux VIDEO AUDIO OUT [--duration S] [--normalize]
                         exact-length delivery mux (never -shortest): round(S*fps) frames, short video padded with
                         its last frame, audio padded/trimmed to the same length, AAC copied or AAC 320k 48 kHz
                         (--normalize: -14 LUFS, true peak -1.5); then verified (exit 1 on failure)
  patch-black IN OUT [--threshold Y]
                         clone the last good frame over black runs inside a film, re-encode, scan again
                         (exit 1 if a run is left); fades at the very start/end stay
  align REF SONG [--win 6 --hop 3] [--out map.json]
                         which pieces of SONG the audio of REF (a montage, a reel) uses, by envelope cross-correlation:
                         song time of each piece, the editor's cut points, and stretches that are not in the song
  lyrics-sheet VIDEO OUT.jpg [--band y0:y1] (--times a,b,c | --every S | --transcript words.json)
                         contact sheet of a lyric video's caption band, to read sung lyrics by eye
  cut IN START END OUT   frame-accurate smart cut (re-encode to next keyframe, copy the rest)
  beats AUDIO [--out beats.json]                              tempo + beat grid
  words AUDIO [--lang ar] [--offset s --duration s] [--out]   lines with word timings (faster-whisper)
  mix SPEC.json OUT.wav  song section + voices, song ducks under voice, exact length, -14 LUFS
  film SPEC.json [--stills 1,4.5] [--reuse] [--remux] [--name]   footage cinema: spec -> graded frames -> MP4 -> verify
  engines                list every engine (module) with its one-line purpose
  run ENGINE ARGS...     run one engine's CLI, e.g. run dragon_montage analyze clip.mp4
"""
import argparse, json, sys
from pathlib import Path
from . import __version__
from . import catalog, router, doctor

LABEL = {"tool": "أدوات للتشغيل / tools", "skill": "مهارات / skills", "superpower": "سوبر باور / superpowers", "power": "قدرات / powers"}


def _band(text):
    """'y0:y1' -> (y0, y1). Whole numbers stay int (pixel rows), others float (fractions of the frame height)."""
    parts = [p.strip() for p in text.split(":")]
    if len(parts) != 2 or not all(parts):
        raise argparse.ArgumentTypeError(f"band must be y0:y1, got {text!r}")
    try:
        return tuple(int(p) if p.lstrip("-").isdigit() else float(p) for p in parts)
    except ValueError:
        raise argparse.ArgumentTypeError(f"band must be two numbers y0:y1, got {text!r}")


def _times(text):
    """'12.5,30,47.2' -> [12.5, 30.0, 47.2]"""
    try:
        return [float(x) for x in text.split(",") if x.strip()]
    except ValueError:
        raise argparse.ArgumentTypeError(f"times must be seconds separated by commas, got {text!r}")


def _brief(x):
    """One printable line for a result row (dict -> key=value, floats to 2 decimals)."""
    if isinstance(x, dict):
        return "  ".join(f"{k}={v:.2f}" if isinstance(v, float) else f"{k}={v}" for k, v in x.items())
    return str(x)


def _mmss(t):
    return f"{'-' if t < 0 else ''}{int(abs(t) // 60)}:{abs(t) % 60:05.2f}"


def _piece(k, x):
    """One align span as a line; falls back to key=value if the songs engine renames a field."""
    try:
        return (f"piece {k}  ref {x['ref_start']:7.2f} - {x['ref_end']:7.2f}  =  song {x['song_start']:7.2f} - "
                f"{x['song_end']:7.2f} ({_mmss(x['song_start'])} - {_mmss(x['song_end'])})  offset {x['offset']:+.3f}"
                f"  score {x['score']:.2f}")
    except (KeyError, TypeError, ValueError):
        return f"piece {k}  {_brief(x)}"


def _fail(a, e):
    """Bad input or a failed ffmpeg run: one clear line on stderr and exit 1, no traceback."""
    sys.exit(f"dragon {a.cmd}: {type(e).__name__}: {e}")


def _save_json(obj, path):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o)),
                 encoding="utf-8")
    return p


def main(argv=None):
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(prog="dragon", description=f"Black Dragon {__version__}\n\n{__doc__}",
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    bd = sub.add_parser("build"); bd.add_argument("--own", action="store_true", help="only refresh the bundled Dragon tools")
    f = sub.add_parser("find"); f.add_argument("query"); f.add_argument("--limit", type=int, default=6)
    f.add_argument("--kind", choices=router.KIND_ORDER, action="append"); f.add_argument("--json", action="store_true")
    s = sub.add_parser("show"); s.add_argument("id")
    sub.add_parser("stats")
    sub.add_parser("doctor")
    pr = sub.add_parser("probe-tools", help="read-only inspection of bundled adapter availability")
    pr.add_argument("--json", action="store_true")
    eco = sub.add_parser("ecosystem", help="inspect local ecosystem paths (no network requests)")
    eco.add_argument("--json", action="store_true")
    pl = sub.add_parser("plan", help="think and route; does NOT execute or spend anything")
    pl.add_argument("query"); pl.add_argument("--mode", choices=("smart", "full"), default="smart")
    pl.add_argument("--limit", type=int, default=6); pl.add_argument("--json", action="store_true")
    v = sub.add_parser("verify"); v.add_argument("files", nargs="+")
    v.add_argument("--out", help="write the evidence JSON here")
    v.add_argument("--expect", help="frame size such as 1080x1920 (another size is a warning)")
    v.add_argument("--duration", type=float, help="intended length in seconds: the video must have exactly round(S*fps) frames")
    v.add_argument("--no-black", action="store_true", help="skip the black-frame scan (faster)")
    v.add_argument("--expect-audio", action="store_true", help="fail a video missing an audio stream")
    v.add_argument("--silent-ok", action="store_true", help="allow a deliberately silent film without audio")
    mx = sub.add_parser("mux", description="Exact-length mux: video + audio -> OUT with round(duration*fps) frames and audio "
                                           "of the same length. Exit 1 when the output fails verify.")
    mx.add_argument("video"); mx.add_argument("audio"); mx.add_argument("out")
    mx.add_argument("--duration", type=float, help="film length in seconds (default: the video's own frame count)")
    mx.add_argument("--normalize", action="store_true", help="re-encode the audio with loudnorm I=-14:TP=-1.5:LRA=11")
    mx.add_argument("--bitrate", default="320k", help="AAC bitrate when the audio is re-encoded (default 320k)")
    mx.add_argument("--allow-pad", action="store_true", help="allow more than 0.5 seconds of held final frame")
    pb = sub.add_parser("patch-black", description="Clone the last good frame over black runs inside a film, re-encode "
                                                   "(CRF 17 slow, BT.709), copy the audio (MP3/PCM inside MP4 becomes AAC 320k), "
                                                   "scan again. Exit 1 if any run is left.")
    pb.add_argument("src", metavar="IN"); pb.add_argument("dst", metavar="OUT")
    pb.add_argument("--threshold", type=float, help="mean luma below this counts as black (default 17.5; pure black is 16)")
    al = sub.add_parser("align", description="Which pieces of SONG the audio of REF uses (envelope cross-correlation per "
                                             "window): the song time of each piece, the editor's cut points and the "
                                             "stretches of REF that are not in the song.")
    al.add_argument("ref"); al.add_argument("song")
    al.add_argument("--win", type=float, default=6.0, help="window length in seconds (default 6)")
    al.add_argument("--hop", type=float, default=3.0, help="step between windows in seconds (default 3)")
    al.add_argument("--out", help="write pieces, gaps and every window to this JSON file")
    ls = sub.add_parser("lyrics-sheet", description="Contact sheet of a lyric video's caption band (whisper garbles sung "
                                                    "Arabic: read the captions instead).")
    ls.add_argument("video"); ls.add_argument("out")
    ls.add_argument("--band", type=_band, help="caption band y0:y1: pixel rows (925:1010) or fractions of the height "
                                               "(0.84:0.94, the default)")
    when = ls.add_mutually_exclusive_group(required=True)
    when.add_argument("--times", type=_times, help="seconds to grab, comma-separated: 12.5,30,47.2")
    when.add_argument("--every", type=float, help="one frame from the middle of every S-second slot (S/2, 3S/2, ...)")
    when.add_argument("--transcript", help="words.json: one frame at the middle of each timed line")
    ls.add_argument("--per-sheet", type=int, default=20)
    ls.add_argument("--width", type=int, default=460)
    ls.add_argument("--cols", type=int, default=2)
    ls.add_argument("--xband", type=_band)
    c = sub.add_parser("cut"); [c.add_argument(x) for x in ("src", "start", "end", "dst")]
    b = sub.add_parser("beats"); b.add_argument("audio"); b.add_argument("--out")
    w = sub.add_parser("words"); w.add_argument("audio"); w.add_argument("--lang", default="ar"); w.add_argument("--out")
    w.add_argument("--offset", type=float, default=0.0); w.add_argument("--duration", type=float); w.add_argument("--model", default="small")
    w.add_argument("--threads", type=int, default=0)
    w.add_argument("--download", action="store_true", help="permit model download with explicit approval")
    m = sub.add_parser("mix"); m.add_argument("spec"); m.add_argument("out")
    fl = sub.add_parser("film"); fl.add_argument("spec"); fl.add_argument("--stills"); fl.add_argument("--reuse", action="store_true")
    fl.add_argument("--remux", action="store_true"); fl.add_argument("--name")
    sub.add_parser("engines")
    r = sub.add_parser("run"); r.add_argument("engine"); r.add_argument("rest", nargs=argparse.REMAINDER)
    fx = sub.add_parser("fx", help="smart-effects gate (v1990.5): rules / new / check MANIFEST [--html PAGE]; exit 1 = effect without a job")
    fx.add_argument("rest", nargs=argparse.REMAINDER)
    v10 = sub.add_parser("v10", help="v10 cognitive, catalog, video, Kling and 7-stage delivery gates")
    v10.add_argument("rest", nargs=argparse.REMAINDER)
    a = ap.parse_args(argv)

    if a.cmd == "fx":
        from .effects import main as fx_main
        return fx_main(a.rest)
    if a.cmd == "v10":
        from .v10_cli import main as v10_main
        return v10_main(a.rest)
    if a.cmd == "build":
        if a.own:
            print("bundled tools:", catalog.register_own())
        else:
            sources = catalog.load_sources()
            available = any(catalog._p(r["path"]).exists() for r in sources.get("skill_roots", []))
            available |= any(catalog._p(sources.get(k, "")).is_file() for k in ("tools_json", "micro_index"))
            if not available:
                sys.exit("No local source repositories found; refusing to overwrite the bundled catalog. "
                         "Use `build --own` to refresh Dragon adapters only.")
            catalog.build()
    elif a.cmd == "probe-tools":
        from .capabilities import probe_tools
        r = probe_tools()
        if a.json:
            print(json.dumps(r, ensure_ascii=False, indent=2))
        else:
            print(f"Inspected {r['total']} adapters: {r['discoverable']} discoverable, "
                  f"{r['missing_dependencies']} missing dependencies, "
                  f"{r['unverified_entrypoint']} unverified entrypoints (none executed).")
            for t in r["tools"]:
                print(f"{t['id']}: {t['status']}" + (f" — {', '.join(t['missing'])}" if t['missing'] else ""))
    elif a.cmd == "ecosystem":
        from .capabilities import ecosystem
        r = ecosystem()
        if a.json:
            print(json.dumps(r, ensure_ascii=False, indent=2))
        else:
            for x in r["roots"]:
                print(f"{'LOCAL' if x['present'] else 'NOT_LOCAL'} {x['source']}: {x['path']}"
                      + ("  <- used" if x.get("chosen") else ""))
    elif a.cmd == "plan":
        from .capabilities import plan
        try:
            r = plan(a.query, mode=a.mode, limit=a.limit)
        except ValueError as e:
            _fail(a, e)
        if a.json:
            print(json.dumps(r, ensure_ascii=False, indent=2))
        else:
            print(f"Black Dragon · {a.mode} plan for {a.query} (NO execution)")
            print("Tools:")
            for t in r["selected_tools"]:
                print(f"  {t['id']} [{t['status']}]" + (f" missing: {t['missing']}" if t['missing'] else ""))
            print("Indexed skills:", ", ".join(x["name"] for x in r["relevant_skills"]))
            print("Review gates:", ", ".join(r["approval_gates"]))
            print(r["notice"])
    elif a.cmd == "find":
        res = router.find(a.query, tuple(a.kind) if a.kind else router.KIND_ORDER, a.limit)
        if a.json:
            print(json.dumps(res, ensure_ascii=False, indent=1)); return
        print(f"التنين · find: {a.query}")
        for k, rows in res.items():
            if not rows:
                continue
            print(f"\n▶ {LABEL[k]}")
            for i, r in enumerate(rows, 1):
                title = r["title_ar"] or r["title_en"] or ""
                print(f"  {i}. {r['name']}  [{r['source']}{' · ' + r['status'] if r['status'] else ''}]  {title}")
                if r["summary"]:
                    print(f"     {r['summary'][:180]}")
                if r["command"]:
                    print(f"     $ {r['command'][:200]}")
                if k == "skill":
                    print(f"     read: {r['path']}")
    elif a.cmd == "show":
        r = router.show(a.id)
        print(json.dumps(r, ensure_ascii=False, indent=1) if r else f"not found: {a.id}")
    elif a.cmd == "stats":
        con = catalog.connect()
        meta = dict(con.execute("SELECT key, value FROM meta").fetchall())
        print("built:", meta.get("built"))
        for k, v in sorted(json.loads(meta.get("counts", "{}")).items(), key=lambda kv: -kv[1]):
            print(f"  {k:32} {v}")
    elif a.cmd == "doctor":
        progs, mods = doctor.check()
        print("programs:")
        for n, p in progs.items():
            print(f"  {'OK' if p else '--'} {n:10} {doctor.PROGRAMS[n]:22} {p or ''}")
        print("python modules:")
        for n, ok in mods.items():
            print(f"  {'OK' if ok else '--'} {n:16} {doctor.MODULES[n]}")
        print(f"\nready: {sum(map(bool, progs.values()))}/{len(progs)} programs, {sum(mods.values())}/{len(mods)} modules")
    elif a.cmd == "verify":
        from . import verify as V
        want_audio = (a.expect_audio or a.duration is not None) and not a.silent_ok
        rows = V.verify(a.files, a.out, a.expect, duration=a.duration, black=not a.no_black, expect_audio=want_audio)
        for r in rows:
            print(V.line(r))
        if a.out:
            print(f"evidence -> {a.out}")
        sys.exit(0 if all(r.get("ok") for r in rows) else 1)
    elif a.cmd == "mux":
        from engines import deliver
        from . import verify as V
        try:
            r = deliver.mux(a.video, a.audio, a.out, duration=a.duration, normalize=a.normalize, bitrate=a.bitrate)
        except (ValueError, RuntimeError, OSError) as e:
            _fail(a, e)
        print(f"mux -> {r['out']}  {r['frames']} frames at {r['fps']:g} fps = {r['duration_s']:g} s  "
              f"video {r['video_mode']} ({r['source_frames']} frames in)  "
              f"audio {r['audio_source_codec']} -> {r['audio_codec']} {r['audio_mode']} ({r['audio_s']} s)")
        print(V.line(r["verify"]))
        pad = float(r.get("padded_s") or 0)
        if pad > 0.5:
            print(f"WARN mux: video is {pad:.2f}s short; final frame frozen (pass --allow-pad only if intended)", file=sys.stderr)
            if not a.allow_pad:
                sys.exit(1)
        sys.exit(0 if r["ok"] else 1)
    elif a.cmd == "patch-black":
        from engines import deliver
        try:
            r = deliver.patch_black(a.src, a.dst, **({} if a.threshold is None else {"threshold": a.threshold}))
        except (ValueError, RuntimeError, OSError) as e:
            _fail(a, e)
        runs = ", ".join(f"{x['start']:.2f}-{x['end']:.2f} ({x['frames']})" for x in r["patched"]) or "none"
        print(f"patch-black -> {r['out']}  {r['mode']}: {len(r['patched'])} run(s), {r['patched_frames']} frames [{runs}]")
        print(f"  frames {r['source_frames']} -> {r['frames']}  audio {r.get('audio_mode')}  "
              f"black runs left inside the film: {len(r['remaining'])}")
        sys.exit(0 if r["ok"] else 1)
    elif a.cmd == "align":
        from engines import songs
        from engines.songs import align, spans
        try:
            rows = align(a.ref, a.song, win=a.win, hop=a.hop)
            sp = spans(rows)
        except (ValueError, RuntimeError, OSError) as e:
            _fail(a, e)
        ref_s = getattr(rows, "ref_s", None)
        holes = songs.gaps(sp, ref_s) if ref_s and hasattr(songs, "gaps") else []
        print(f"align: {a.ref} -> {a.song}  (windows {a.win:g} s every {a.hop:g} s)  {len(sp)} piece(s)")
        lines = [(x.get("ref_start", 0), _piece(k, x)) for k, x in enumerate(sp, 1)]
        lines += [(g["ref_start"], f"not in the song: ref {g['ref_start']:.2f} - {g['ref_end']:.2f}  "
                                   f"({g['ref_end'] - g['ref_start']:.2f} s)") for g in holes]
        for _, text in sorted(lines, key=lambda x: x[0]):
            print("  " + text)
        if not sp:
            print("  no piece of the song found (every window scored under the match threshold)")
        if a.out:
            _save_json({"ref": str(a.ref), "song": str(a.song), "ref_s": ref_s, "song_s": getattr(rows, "song_s", None),
                        "win": a.win, "hop": a.hop, "spans": sp, "gaps": holes, "windows": list(rows)}, a.out)
            print(f"map -> {a.out}")
    elif a.cmd == "lyrics-sheet":
        from engines.songs import lyrics_sheet
        try:
            r = lyrics_sheet(a.video, a.out, band=a.band, times=a.times, every=a.every, transcript=a.transcript, per_sheet=a.per_sheet, width=a.width, cols=a.cols, xband=a.xband)
        except (ValueError, RuntimeError, OSError) as e:
            _fail(a, e)
        if isinstance(r, list):
            for x in r: print(f"lyrics sheet -> {x}")
        else: print(f"lyrics sheet -> {r if isinstance(r, (str, Path)) else a.out}")
        if isinstance(r, dict):
            print("  " + _brief(r))
    elif a.cmd == "cut":
        from engines.montage import smart_cut
        print(json.dumps(smart_cut(a.src, a.start, a.end, a.dst)))
    elif a.cmd == "beats":
        from engines import audio
        r = audio.beats(a.audio)
        print(f"tempo {r['tempo']} bpm · {len(r['beats'])} beats · {r['duration']}s")
        if a.out:
            audio.save(r, a.out)
    elif a.cmd == "words":
        from engines import audio
        try:
            lines = audio.words(a.audio, a.lang, a.model, a.offset, a.duration, threads=a.threads, download=a.download)
        except (audio.ModelNotCached, ImportError, RuntimeError, OSError, ValueError) as e:
            print(f"dragon words: {type(e).__name__}: {e}", file=sys.stderr)
            return 2
        for ln in lines:
            print(f"{ln['start']:7.2f}-{ln['end']:7.2f}  {ln['text']}")
        if a.out:
            audio.save(lines, a.out)
    elif a.cmd == "mix":
        from engines import audio
        s = json.loads(open(a.spec, encoding="utf-8-sig").read())
        audio.mix(s["song"], s["start"], s["duration"], a.out, s.get("voices", []),
                  fade_in=s.get("fadeIn", 0.4), fade_out=s.get("fadeOut", 2.5), song_gain=s.get("songGain", 1.0))
        print("mix ->", a.out)
    elif a.cmd == "film":
        from engines import cinema
        if a.stills:
            print("stills ->", cinema.stills(a.spec, a.stills))
        else:
            final, r = cinema.build(a.spec, reuse=a.reuse, remux=a.remux, out_name=a.name)
            print("DONE", final)
            sys.exit(0 if r.get("ok") else 1)
    elif a.cmd == "engines":
        for name, doc in list_engines():
            print(f"  {name:18} {doc}")
    elif a.cmd == "run":
        import runpy
        names = [n for n, _ in list_engines()]
        if a.engine not in names:
            sys.exit(f"unknown engine {a.engine}; choose from: {', '.join(names)}")
        sys.argv = [f"engines.{a.engine}", *a.rest]
        runpy.run_module(f"engines.{a.engine}", run_name="__main__", alter_sys=True)


def list_engines():
    """Engines are packages under engines/ that ship a __main__.py (their own CLI)."""
    import ast
    root = Path(__file__).resolve().parent.parent / "engines"
    out = []
    for d in sorted(root.iterdir()):
        if (d / "__main__.py").exists():
            init = d / "__init__.py"
            doc = ast.get_docstring(ast.parse(init.read_text(encoding="utf-8"))) if init.exists() else ""
            out.append((d.name, (doc or "").strip().splitlines()[0] if doc else ""))
    return out


if __name__ == "__main__":
    main()
