"""Helpers of runners/fam_w3_03.py used by data cards, copied verbatim (the extractor binds a card to them only when
their AST hash with every dependency equals the original's)."""
from __future__ import annotations

from pathlib import Path
from .core import fx
import hashlib
import json
import shutil
import subprocess
import time


def _node_root():
    for base in [Path(shutil.which("node") or "/usr/bin/node").resolve().parent.parent / "lib/node_modules",
                 Path("/opt/node22/lib/node_modules"), Path("/usr/lib/node_modules"), Path("/usr/local/lib/node_modules")]:
        if (base / "gsap").exists():
            return base
    return Path("/opt/node22/lib/node_modules")


NM = _node_root()


def jw(path, obj):
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
    return Path(path)


def nframes(path):
    out = fx.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries",
                  "stream=nb_read_frames", "-of", "csv=p=0", str(path)]).stdout.strip()
    return int(out.split(",")[0])


def write_mp4(path, frames, fps=30, lossless=True):
    import numpy as np
    arr = [np.asarray(f, dtype=np.uint8) for f in frames]
    h, w = arr[0].shape[:2]
    codec = ["-c:v", "libx264rgb", "-qp", "0", "-preset", "ultrafast"] if lossless else ["-c:v", "libx264", "-crf", "12", "-pix_fmt", "yuv420p"]
    p = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
                        "-s", "%dx%d" % (w, h), "-r", str(fps), "-i", "-", *codec, str(path)],
                       input=b"".join(a.tobytes() for a in arr), capture_output=True, timeout=60)
    if p.returncode:
        raise RuntimeError(p.stderr.decode(errors="replace")[-300:])
    return Path(path)


def _license_ok(claim, lic):
    lic = str(lic or "")
    if claim == "no-charge":
        return "no charge" in lic.lower() and "MIT" not in lic
    return lic == claim


def onsets(samples, rate, thr=0.2, gap=0.05):
    import numpy as np
    a = np.abs(np.asarray(samples, dtype=float))
    idx = np.nonzero(a > thr)[0]
    out, last = [], -1e9
    for i in idx:
        if i - last > gap * rate:
            out.append(i / rate)
        last = i
    return out


KIT_ORDER = ["lyric", "plotter", "doodle", "whiteboard", "chalkboard", "stickman", "isometric", "fake3d", "infographic", "mapjourney", "product"]


KIT_PAL = {"lyric": {"bg": (12, 12, 20), "ink": (240, 220, 160)}, "chalkboard": {"bg": (30, 50, 40), "ink": (240, 240, 240)}}


def kit_build(o, cache, wd):
    """KIT.build: parse -> speedTimings (or align to voice) -> 'motionkit' scene (cached per signature) -> sfx stem -> music bed."""
    import numpy as np
    if o["style"] not in KIT_ORDER:
        raise ValueError("unknown style %s" % o["style"])
    lines = [ln.strip() for ln in o["script"].split("\n") if ln.strip()]
    if o.get("voice_onsets"):
        starts = list(o["voice_onsets"])
        ends = starts[1:] + [o["duration"]]
    else:
        words = [len(ln.split()) for ln in lines]
        per = [w / (2.5 * o.get("speed", 1.0)) for w in words]
        scale = o["duration"] / sum(per)
        starts, t = [], 0.0
        for d in per:
            starts.append(round(t, 4))
            t += d * scale
        ends = starts[1:] + [o["duration"]]
    pal = dict(KIT_PAL.get(o["style"], KIT_PAL["lyric"]))
    if o.get("brand"):
        pal["ink"] = o["brand"]
    params = {"style": o["style"], "lines": lines, "title": o.get("title", ""), "pal": pal, "fonts": o.get("fonts", ["DejaVu Sans"]), "seed": o.get("seed", 1)}
    sig = hashlib.sha256(json.dumps(params, sort_keys=True, default=list).encode()).hexdigest()[:16]
    hit = sig in cache
    if not hit:
        cache[sig] = {"type": "motionkit", "params": params}
    rate = 22050
    n = int(o["duration"] * rate)
    stem = np.zeros(n)
    click = np.sin(2 * np.pi * 1800 * np.arange(int(0.03 * rate)) / rate) * np.hanning(int(0.03 * rate)) * 0.8
    for s in starts:
        i = int(s * rate)
        stem[i:i + len(click)] += click[: max(0, n - i)]
    t = np.arange(n) / rate
    bed = 0.08 * (np.sin(2 * np.pi * 220 * t) + np.sin(2 * np.pi * 277.2 * t) + np.sin(2 * np.pi * 329.6 * t)) / 3
    fx.write_wav(wd / "sfx_stem.wav", stem, rate)
    fx.write_wav(wd / "music_bed.wav", bed, rate)
    from PIL import Image, ImageDraw
    fps, W, H = 10, 160, 90
    frames = []
    for k in range(int(o["duration"] * fps)):
        tt = k / fps
        cur = max(i for i, s in enumerate(starts) if s <= tt + 1e-9)
        im = Image.new("RGB", (W, H), pal["bg"])
        d = ImageDraw.Draw(im)
        prog = (tt - starts[cur]) / max(1e-6, ends[cur] - starts[cur])
        d.rectangle((10, 40, 10 + int(140 * prog), 50), fill=pal["ink"])
        d.text((10, 10), "%d/%d" % (cur + 1, len(lines)), fill=pal["ink"])
        frames.append(np.asarray(im))
    film = write_mp4(wd / ("film_%s.mp4" % o["style"]), frames, fps=fps)
    return {"sig": sig, "cache_hit": hit, "starts": starts, "ends": ends, "lines": lines, "film": film, "pal": pal}


AIR_TASKS = {"code": ("top", "high", 20000), "film": ("top", "high", 14000), "imitate": ("top", "high", 12000),
             "plan": ("mid", "medium", 12000), "agent": ("mid", "medium", 6000), "script": ("mid", "medium", 6000), "vision": ("mid", "medium", 6000),
             "review": ("mid", "medium", 8000), "highlights": ("mid", "medium", 4000),
             "quick": ("small", "low", 3000), "post": ("small", "low", 3000), "captions": ("small", "low", 4000), "default": ("mid", "medium", 16000)}


def air_route(task, model="auto", effort="auto"):
    m, e, mx = AIR_TASKS.get(task, AIR_TASKS["default"])
    m = m if model == "auto" else model
    e = e if effort == "auto" else effort
    return {"model": m, "effort": e, "max_tokens": mx, "thinking": "adaptive" if e in ("high", "max") else None}


def air_call(req, backend):
    """400 -> retry once without effort; 404 -> fall back to the mid tier."""
    tries = []
    r = dict(req)
    for _ in range(3):
        code = backend(r)
        tries.append((r["model"], r.get("effort"), code))
        if code == 200:
            return {"ok": True, "tries": tries}
        if code == 400 and r.get("effort"):
            r = dict(r, effort=None)
        elif code == 404 and r["model"] != "mid":
            r = dict(r, model="mid")
        else:
            break
    return {"ok": False, "tries": tries}


def gem_chain(chosen, models, sick, now, call, hedge_after=0.05):
    """[chosen, flash, flash-lite] skipping models marked sick in the last 3 minutes; hedge: start the next when one fails or is silent."""
    import concurrent.futures as cf
    chain = [m for m in [chosen] + models if not (m in sick and now - sick[m] < 180)]
    started = []
    with cf.ThreadPoolExecutor(max_workers=len(chain)) as ex:
        futs = {}
        for m in chain:
            started.append(m)
            futs[ex.submit(call, m)] = m
            done, _ = cf.wait(list(futs), timeout=hedge_after, return_when=cf.FIRST_COMPLETED)
            for f in done:
                if f.result() == "ok":
                    return {"winner": futs[f], "started": started, "chain": chain}
        for f in cf.as_completed(list(futs)):
            if f.result() == "ok":
                return {"winner": futs[f], "started": started, "chain": chain}
    return {"winner": None, "started": started, "chain": chain}


CRITICAL = {"inputs", "montage", "motion_film", "launch_film", "reels", "imitate"}


def agent_plan(prompt):
    """Rule-based local plan (no AI): 1-9 steps, render only when asked."""
    steps = ["inputs"]
    if "مونتاج" in prompt or "montage" in prompt:
        steps.append("montage")
    if "ترجمة" in prompt or "captions" in prompt:
        steps.append("smart_captions")
    if "موسيقى" in prompt or "music" in prompt:
        steps.append("music")
    if "صدّر" in prompt or "render" in prompt or "صدر" in prompt:
        steps.append("render")
    steps.append("review")
    return {"reply": "خطة محلية", "title": prompt[:30], "steps": steps[:9], "next": ["post", "export_fingerprint"]}


def agent_tools(wd):
    def inputs(st):
        clips = sorted(Path(st["media"]).glob("*.mp4"))
        if not clips:
            raise RuntimeError("no input media")
        st["clips"] = clips
        return "%d clips" % len(clips)

    def montage(st):
        lst = wd / "list.txt"
        lst.write_text("".join("file '%s'\n" % c for c in st["clips"]))
        out = wd / "montage.mp4"
        fx.ffmpeg("-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(out))
        st["film"] = out
        return str(out.name)

    def smart_captions(st):
        srt = wd / "captions.srt"
        srt.write_text("1\n00:00:00,000 --> 00:00:01,000\nمرحبا\n")
        return srt.name

    def music(st):
        fx.tone(wd / "music.wav", seconds=1.0)
        return "music.wav"

    def render(st):
        out = wd / "final.mp4"
        fx.ffmpeg("-i", str(st["film"]), "-c:v", "libx264", "-pix_fmt", "yuv420p", str(out))
        st["final"] = out
        return out.name

    def review(st):
        return "ok" if st.get("film") else "nothing to review"
    return {"inputs": inputs, "montage": montage, "smart_captions": smart_captions, "music": music, "render": render, "review": review}


def agent_run(plan, tools, st):
    log, stopped = [], False
    for name in plan["steps"]:
        if stopped:
            log.append({"step": name, "status": "skipped"})
            continue
        t0 = time.time()
        try:
            out = tools[name](st)
            log.append({"step": name, "status": "done", "engine": "local", "ms": round((time.time() - t0) * 1000, 1), "out": out})
        except Exception as e:  # noqa: BLE001
            log.append({"step": name, "status": "failed", "engine": "local", "ms": round((time.time() - t0) * 1000, 1), "error": str(e)[:100]})
            if name in CRITICAL:
                stopped = True
    return log


def tc(frames, fps):
    f = int(round(frames))
    return "%02d:%02d:%02d:%02d" % (f // (3600 * fps), f // (60 * fps) % 60, f // fps % 60, f % fps)


def trim_render(segs, out):
    """Frame-exact cut list render: trim=start_frame/end_frame per segment, then the concat filter."""
    args, fc = [], ""
    for i, (f, a, b) in enumerate(segs):
        args += ["-i", str(f)]
        fc += "[%d:v]trim=start_frame=%d:end_frame=%d,setpts=PTS-STARTPTS[v%d];" % (i, a, b, i)
    fc += "".join("[v%d]" % i for i in range(len(segs))) + "concat=n=%d:v=1:a=0[o]" % len(segs)
    fx.ffmpeg(*args, "-filter_complex", fc, "-map", "[o]", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(out))
    return out


def fc_family(name):
    out = fx.run(["fc-match", "-f", "%{family}", name]).stdout
    return out.split(",")[0].strip()
