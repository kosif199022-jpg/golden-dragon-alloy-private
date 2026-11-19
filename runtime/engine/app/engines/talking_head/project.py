"""Project steps before the edit: prepare the folder, transcript, pause cutting, voice mastering, clip review."""
import json, math, os, re, shutil, subprocess, wave
from pathlib import Path

from ..media import ascii_path, exe, ffmpeg, fps as rate, probe

DATA = Path(__file__).with_name("data")
CFG = json.loads((DATA / "pipeline.json").read_text(encoding="utf-8"))


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save(obj, path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(obj, indent=1, ensure_ascii=False), encoding="utf-8")
    return Path(path)


def info(path):
    """{w, h, dur, fps, audio} - width/height swapped for phone videos stored sideways."""
    p = probe(path)
    v = next((s for s in p["streams"] if s["codec_type"] == "video"), {})
    out = dict(w=int(v.get("width") or 0), h=int(v.get("height") or 0), dur=float(p["format"].get("duration") or 0),
               fps=round(rate(v.get("r_frame_rate")), 5), audio=any(s["codec_type"] == "audio" for s in p["streams"]))
    if v:
        r = subprocess.run([exe("ffprobe"), "-v", "error", "-select_streams", "v:0", "-show_entries",
                            "stream_side_data=rotation:stream_tags=rotate", "-of", "json", str(path)], capture_output=True, text=True)
        rot = re.search(r'"(?:rotation|rotate)"\s*:\s*"?(-?\d+)', r.stdout)
        if rot and abs(int(rot.group(1))) % 180 == 90:
            out["w"], out["h"] = out["h"], out["w"]
    return out


def nice_fps(f):
    """Snap a measured frame rate to the value the render should use."""
    return next((t for t in CFG["nice_fps"] if abs(f - t) < 0.02), round(f, 3) if f else 25)


def config(project):
    p = Path(project) / "project.json"
    if not p.exists():
        raise FileNotFoundError(f"no project.json in {project} - run `prepare` first")
    return load(p)


# ------------------------------------------------------------------------------------------------ prepare
def prepare(video, project=None, name=None, graded=None, lut=None):
    """Create the project folder, extract the 16 kHz analysis audio + 48 kHz source audio, write project.json."""
    src = Path(video).resolve()
    if not src.exists():
        raise FileNotFoundError(f"video not found: {src}")
    name = (name or src.stem).replace(" ", "_")
    proj = Path(project or src.parent / f"{name}_reel").resolve()
    for sub in CFG["project_dirs"]:
        (proj / sub).mkdir(parents=True, exist_ok=True)
    meta = info(src)
    if not meta["w"]:
        raise ValueError(f"no video stream in {src}")
    if not meta["audio"]:
        raise ValueError("the recording has no audio track - the edit is driven by speech")
    presenter, notes = src, []
    if graded:
        presenter = Path(graded).resolve()
        if abs(info(presenter)["dur"] - meta["dur"]) > 0.2:
            notes.append("graded file length differs from the source - cuts are computed on the source timeline")
    elif lut:
        presenter = proj / "footage" / f"{name}_graded.mov"
        cube = ascii_path(Path(lut).resolve()).as_posix().replace("'", "\\'").replace(":", "\\:")
        ffmpeg("-i", src, "-an", "-vf", f"format=rgb48le,lut3d=file='{cube}':interp=tetrahedral,format=yuv422p10le",
               "-c:v", "prores_ks", "-profile:v", 3, presenter)
    ffmpeg("-i", src, "-vn", "-ac", 1, "-ar", 16000, "-c:a", "pcm_s16le", proj / "analysis" / "audio16k.wav")
    ffmpeg("-i", src, "-vn", "-ac", 2, "-ar", 48000, "-c:a", "pcm_s24le", proj / "audio" / "source_48k.wav")
    shutil.copy(DATA / "halftone_1080x1920.png", proj / "assets")
    pm = info(presenter)
    cfg = dict(name=name, project_dir=str(proj), source=str(src), presenter=str(presenter), src_w=pm["w"], src_h=pm["h"],
               src_fps=meta["fps"], src_dur=meta["dur"], fps=nice_fps(meta["fps"]), **CFG["frame"])
    save(cfg, proj / "project.json")
    if pm["w"] > pm["h"] and pm["h"] < 1920 * 0.75:
        notes.append("horizontal source under 1440p - the 9:16 crop will be soft")
    return dict(cfg, notes=notes)


# ------------------------------------------------------------------------------------------------ transcript
def asr_from_words(words, gap=CFG["asr"]["gap"]):
    """[{word|w, start|s, end|e}] -> asr segments [{start, end, text, words:[{s, e, w, p}]}];
    a new segment starts after sentence punctuation or a silence longer than `gap`."""
    ends = tuple(CFG["asr"]["sentence_end"])
    rows = []
    for w in words:
        text = str(w.get("word", w.get("w", ""))).strip()
        s, e = float(w.get("start", w.get("s"))), float(w.get("end", w.get("e")))
        if not text or e < s:
            raise ValueError(f"bad word entry: {w!r}")
        rows.append(dict(s=round(s, 3), e=round(e, 3), w=" " + text, p=float(w.get("p", 1.0))))
    rows.sort(key=lambda r: r["s"])
    segs, cur = [], []
    for r in rows:
        if cur and (r["s"] - cur[-1]["e"] > gap or cur[-1]["w"].rstrip().endswith(ends)):
            segs.append(cur)
            cur = []
        cur.append(r)
    if cur:
        segs.append(cur)
    return [dict(start=c[0]["s"], end=c[-1]["e"], text="".join(r["w"] for r in c), words=c) for c in segs]


def import_words(project, words, gap=CFG["asr"]["gap"], language=None):
    """A word-timed transcript from elsewhere (voice studio words.json) -> analysis/asr.json."""
    cfg = config(project)
    data = load(words) if isinstance(words, (str, Path)) else words
    data = data.get("words") or [] if isinstance(data, dict) else data
    if not data:
        raise ValueError("no words")
    segs = asr_from_words(data, gap)
    save(segs, Path(cfg["project_dir"]) / "analysis" / "asr.json")
    if language:
        save(dict(cfg, language=language), Path(cfg["project_dir"]) / "project.json")
    return segs


def transcribe(project, language=None, model=None):
    """faster-whisper word timings (engines.audio.words) -> analysis/asr.json."""
    from ..audio import words as asr
    cfg = config(project)
    model = model or (CFG["asr"]["model_en"] if language == "en" else CFG["asr"]["model"])
    lines = asr(Path(cfg["project_dir"]) / "analysis" / "audio16k.wav", language=language, model=model, vad=False)
    segs = [dict(start=l["start"], end=l["end"], text=" " + l["text"],
                 words=[dict(s=w["s"], e=w["e"], w=" " + w["w"], p=1.0) for w in l["words"]]) for l in lines]
    save(segs, Path(cfg["project_dir"]) / "analysis" / "asr.json")
    if language:
        save(dict(cfg, language=language), Path(cfg["project_dir"]) / "project.json")
    return segs


# ------------------------------------------------------------------------------------------------ pause cutting
def energy_db(path):
    """Loudness (dBFS) of 10 ms windows of a 16 kHz mono WAV, and its duration."""
    import numpy as np
    with wave.open(str(path), "rb") as w:
        a = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
    n = len(a) // 160
    rms = np.sqrt(np.mean(a[:n * 160].reshape(n, 160) ** 2, axis=1) + 1e-12)
    return 20 * np.log10(rms), len(a) / 16000.0


def speech_regions(db, words, threshold=None):
    """Energy regions above the threshold (halfway between room tone and loud speech) that touch the transcript."""
    import numpy as np
    c = CFG["cut"]
    p5, p95 = float(np.percentile(db, 5)), float(np.percentile(db, 95))
    thr = threshold if threshold is not None else p5 + 0.5 * (p95 - p5)
    sp = np.concatenate([[False], db > thr, [False]]).astype(np.int8)
    edges = np.flatnonzero(np.diff(sp))
    merged = []
    for a, b in zip(edges[::2] / 100.0, edges[1::2] / 100.0):
        if merged and a - merged[-1][1] < c["merge_gap"]:
            merged[-1][1] = b
        else:
            merged.append([a, b])
    w0, w1 = words[0]["s"], words[-1]["e"]
    regs = [r for r in merged if r[1] - r[0] >= c["min_region"] and r[1] >= w0 - c["touch_words"] and r[0] <= w1 + c["touch_words"]]
    return regs, thr, p5, p95


def keep_segments(regs, words, total, fps, remove=(), pause_sentence=None, pause_mid=None, lead=None, trail=None):
    """Speech regions -> frame-aligned keep list [{src_t0, src_t1, prog_t0}]: every gap > 0.22 s becomes a natural
    pause (longer after a sentence end), `remove` ranges (source seconds) are cut out."""
    c = CFG["cut"]
    ps, pm = pause_sentence if pause_sentence is not None else c["pause_sentence"], pause_mid if pause_mid is not None else c["pause_mid"]
    lead, trail = lead if lead is not None else c["lead"], trail if trail is not None else c["trail"]

    def punct_before(t):
        prev = [w for w in words if w["e"] <= t + 0.15]
        return prev[-1]["w"].strip()[-1:] if prev else ""

    keeps, cur = [], [max(0.0, regs[0][0] - lead), None]
    for (_, g0), (g1, _) in zip(regs, regs[1:]):
        gap = g1 - g0
        if gap <= c["min_gap"]:
            continue
        target = ps if punct_before(g0) in c["sentence_end"] else pm
        if gap - target < c["min_saving"]:
            continue
        tail = min(c["max_tail"], target / 2)
        cur[1] = g0 + tail
        keeps.append(cur)
        cur = [g1 - (target - tail), None]
    cur[1] = min(total, regs[-1][1] + trail)
    keeps.append(cur)
    out = []
    for seg in keeps:
        segs = [seg]
        for x, y in remove:
            segs = [p for u0, u1 in segs for p in ([[u0, u1]] if y <= u0 or x >= u1 else
                                                   ([[u0, x]] if x > u0 else []) + ([[y, u1]] if y < u1 else []))]
        out += segs
    q = []
    for s0, s1 in out:
        f0, f1 = math.floor(s0 * fps + 1e-6), math.ceil(s1 * fps - 1e-6)
        if f1 - f0 >= 2:
            if q and f0 <= q[-1][1]:
                q[-1][1] = max(q[-1][1], f1)
            else:
                q.append([f0, f1])
    cuts, prog = [], 0
    for f0, f1 in q:
        cuts.append(dict(src_t0=round(f0 / fps, 5), src_t1=round(f1 / fps, 5), prog_t0=round(prog / fps, 5)))
        prog += f1 - f0
    return cuts


def retime(words, cuts):
    """Transcript words (source seconds) -> program timeline (words cut away are dropped)."""
    pw = []
    for w in words:
        mid = (w["s"] + w["e"]) / 2
        c = next((c for c in cuts if c["src_t0"] - 0.02 <= mid < c["src_t1"]), None)
        if c:
            off = c["prog_t0"] - c["src_t0"]
            pw.append(dict(s=round(max(c["prog_t0"], w["s"] + off), 3),
                           e=round(min(c["prog_t0"] + c["src_t1"] - c["src_t0"], w["e"] + off), 3), w=w["w"], p=w.get("p", 1)))
    return pw


def cut_audio(src, cuts, dst, fade):
    parts = [f"[0:a]atrim={c['src_t0']:.5f}:{c['src_t1']:.5f},asetpts=PTS-STARTPTS,afade=t=in:d={fade},"
             f"afade=t=out:st={max(0, c['src_t1'] - c['src_t0'] - fade):.5f}:d={fade}[a{k}]" for k, c in enumerate(cuts)]
    graph = ";".join(parts) + ";" + "".join(f"[a{k}]" for k in range(len(cuts))) + f"concat=n={len(cuts)}:v=0:a=1[out]"
    script = Path(dst).with_suffix(".ffscript")
    script.write_text(graph, encoding="utf-8")
    ffmpeg("-i", src, "-/filter_complex", script, "-map", "[out]", "-c:a", "pcm_s24le", "-ar", 48000, dst)


def cut_pauses(project, remove=(), threshold=None, **pauses):
    """Tighten the pauses: analysis/cuts.json, analysis/program_words.json, audio/program_raw.wav."""
    cfg = config(project)
    P = Path(cfg["project_dir"])
    fps = cfg["src_fps"] or cfg["fps"]
    db, total = energy_db(P / "analysis" / "audio16k.wav")
    words = [w for s in load(P / "analysis" / "asr.json") for w in s["words"]]
    if not words:
        raise ValueError("empty transcript - run transcribe first")
    regs, thr, p5, p95 = speech_regions(db, words, threshold)
    if not regs:
        raise ValueError(f"no speech found above {thr:.1f} dB - pass a threshold")
    remove = [tuple(float(v) for v in r.split("-")) if isinstance(r, str) else tuple(r) for r in remove]
    cuts = keep_segments(regs, words, total, fps, remove, **pauses)
    save(cuts, P / "analysis" / "cuts.json")
    save(retime(words, cuts), P / "analysis" / "program_words.json")
    cut_audio(P / "audio" / "source_48k.wav", cuts, P / "audio" / "program_raw.wav", CFG["cut"]["join_fade"])
    prog = sum(round((c["src_t1"] - c["src_t0"]) * fps) for c in cuts) / fps
    save(dict(cfg, program_dur=round(prog, 4)), P / "project.json")
    lines = [(c, " ".join(w["w"].strip() for w in words if c["src_t0"] - 0.05 <= w["s"] < c["src_t1"] - 0.05)) for c in cuts]
    return dict(cuts=cuts, threshold=thr, room=p5, speech=p95, program=prog, source=total, lines=lines)


# ------------------------------------------------------------------------------------------------ master
def loudness(path, pre=""):
    err = subprocess.run([exe("ffmpeg"), "-hide_banner", "-nostats", "-i", str(path), "-af", pre + "loudnorm=print_format=json",
                          "-f", "null", "-"], capture_output=True, text=True, encoding="utf-8", errors="ignore").stderr
    return json.loads(re.search(r'\{[^{}]*"input_i"[^{}]*\}', err, re.S).group(0))


def master(project, lufs=None, true_peak=None):
    """Two-pass loudnorm of audio/program_raw.wav (70 Hz high-pass, 16 kHz low-pass) -> audio/program_master.wav."""
    m = CFG["master"]
    lufs, tp = m["lufs"] if lufs is None else lufs, m["true_peak"] if true_peak is None else true_peak
    cfg = config(project)
    P = Path(cfg["project_dir"])
    src, dst = P / "audio" / "program_raw.wav", P / "audio" / "program_master.wav"
    a = loudness(src, m["pre"])
    ln = (f"loudnorm=I={lufs:.1f}:TP={tp:.1f}:LRA={m['lra']}:measured_I={a['input_i']}:measured_TP={a['input_tp']}:"
          f"measured_LRA={a['input_lra']}:measured_thresh={a['input_thresh']}:offset={a['target_offset']}:linear=true")
    ffmpeg("-i", src, "-af", m["pre"] + ln, "-ar", 48000, "-c:a", "pcm_s24le", dst)
    b = loudness(dst)
    miss = lufs - float(b["input_i"])
    if abs(miss) > m["retry_miss"]:     # loud peaks kept loudnorm short: trim gain, then a soft peak limiter
        tmp = dst.with_name("program_master_tmp.wav")
        os.replace(dst, tmp)
        ffmpeg("-i", tmp, "-af", f"volume={miss:.2f}dB,alimiter=limit={10 ** (tp / 20.0):.4f}:attack=3:release=60:level=disabled",
               "-ar", 48000, "-c:a", "pcm_s24le", dst)
        tmp.unlink()
        b = loudness(dst)
    save(dict(cfg, audio="audio/program_master.wav"), P / "project.json")
    return dict(before=(a["input_i"], a["input_tp"]), after=(b["input_i"], b["input_tp"]), path=str(dst))


# ------------------------------------------------------------------------------------------------ clip review + setup
def clip_sheet(out_dir, clips):
    """Size, length, fps, hard cuts and a 6-frame strip per candidate B-roll clip."""
    s = CFG["sheet"]
    os.makedirs(out_dir, exist_ok=True)
    rows = []
    for f in clips:
        m = info(f)
        err = subprocess.run([exe("ffmpeg"), "-hide_banner", "-i", str(f), "-vf", f"scale=320:-2,select='gt(scene,{s['scene']})',showinfo",
                              "-an", "-f", "null", "-"], capture_output=True, text=True, encoding="utf-8", errors="ignore").stderr
        sheet = Path(out_dir) / f"{Path(f).stem}_sheet.jpg"
        n, c = s["clip_frames"], s["clip_cell"]
        ffmpeg("-i", f, "-vf", f"fps={n / max(m['dur'], 0.1):f},scale={c}:{c}:force_original_aspect_ratio=decrease,"
               f"pad={c}:{c}:(ow-iw)/2:(oh-ih)/2,tile={n}x1", "-frames:v", 1, sheet, check=False)
        rows.append(dict(clip=str(f), w=m["w"], h=m["h"], dur=m["dur"], fps=m["fps"], sheet=str(sheet),
                         cuts=[round(float(x), 2) for x in re.findall(r"pts_time:([\d.]+)", err)]))
    return rows


def check():
    """(state, what) rows: numpy, faster-whisper, ffmpeg with libass, fonts."""
    import importlib.util, sys
    rows = [("ok" if sys.version_info >= (3, 9) else "MISS", f"Python {sys.version.split()[0]}")]
    for mod, why in (("numpy", "compositing"), ("faster_whisper", "word timings (or import a words.json)")):
        rows.append(("ok" if importlib.util.find_spec(mod) else ("MISS" if mod == "numpy" else "warn"), f"{mod} ({why})"))
    try:
        filters = subprocess.run([exe("ffmpeg"), "-hide_banner", "-filters"], capture_output=True, text=True).stdout
        rows.append(("ok" if re.search(r"^\s*\S*\s+ass\s", filters, re.M) else "MISS", f"ffmpeg with libass ({exe('ffmpeg')})"))
    except FileNotFoundError as e:
        rows.append(("MISS", str(e)))
    style = load(DATA / "style.json")
    for f in style["font_files"]:
        p = DATA / f if not os.path.isabs(f) else Path(f)
        rows.append(("ok" if p.exists() else "warn", f"font {p.name}" + ("" if p.exists() else " (macOS face; map the EDL 'fonts' to faces you have)")))
    rows.append(("warn", "Apple Vision mattes (presenter_mattes / clip_matte) are macOS-only and not part of this engine; "
                         "existing matte files are still used by the renderer"))
    return rows
