"""Footage cinema: a film spec (shots + texts + audio) -> graded frames -> seekable canvas page -> MP4 -> measured.
Rebuild of the Mayar pipeline on the Black Dragon media core (engines.montage / engines.audio / dragon.verify).

Spec paths (all optional; env vars as fallback): spec["paths"] = {"refs", "audio", "deliver", "work", "luts"}.
"""
import base64, json, os, shutil, subprocess, sys
from pathlib import Path
from .. import montage, audio
from ..deliver import mux

HERE = Path(__file__).resolve().parent
ASSETS = HERE / "assets"
RENDER = HERE.parent / "render" / "render.cjs"
MONTAGE = Path(__import__("os").environ.get("DRAGON_MONTAGE_DIR") or Path.home() / "OneDrive" / "Desktop" / "المونتاج")


def _paths(spec):
    p = spec.get("paths", {})
    g = lambda k, env, default: Path(p.get(k) or os.environ.get(env) or default)
    return {"refs": g("refs", "BDC_REFS", MONTAGE / "01_raw" / "refs"),
            "audio": g("audio", "BDC_AUDIO", MONTAGE / "02_music"),
            "deliver": g("deliver", "BDC_DELIVER", MONTAGE / "05_output"),
            "work": g("work", "BDC_WORK", Path.home() / "bdc_work"),  # ASCII + outside OneDrive (frames are GBs)
            "luts": g("luts", "BDC_LUTS", MONTAGE / "_kit" / "LUTs")}


def _src(refs, cid):
    hit = next(refs.glob(f"*{cid}*.mp4"), None)
    if not hit:
        raise FileNotFoundError(f"clip '{cid}' not in {refs}")
    return hit


def _fonts_js(work):
    f = work / "fonts.js"
    if not f.exists():
        data = {t.name: base64.b64encode(t.read_bytes()).decode() for t in (ASSETS / "fonts").glob("*.ttf")}
        f.write_text("window.FONTDATA=" + json.dumps(data) + ";", encoding="utf-8")  # Chromium blocks file:// FontFace
    return f


def prepare(spec, name, reuse=False, log=print):
    P = _paths(spec)
    work = P["work"]
    for d in ("films", "shots", "out"):
        (work / d).mkdir(parents=True, exist_ok=True)
    shutil.copy2(ASSETS / "engine.js", work / "engine.js")
    _fonts_js(work)
    t = 0.0
    for i, s in enumerate(spec["shots"]):
        s["t"] = round(t, 3); t += s["d"]
        if s.get("type", "clip") != "clip":
            continue
        s["type"] = "clip"
        d = work / "shots" / f"{name}_{i:02d}"
        if not (reuse and d.exists() and any(d.glob("*.jpg"))):
            if d.exists():
                shutil.rmtree(d)
            c = s.get("crop", {})
            lut = P["luts"] / f"{s.get('lut', '01_Cinematic')}.cube"
            montage.extract_frames(_src(P["refs"], s["src"]), s["in"], s["d"] * s.get("speed", 1) + 0.4, d,
                                   c.get("z", 1.0), c.get("cx", 0.5), c.get("cy", 0.5), lut if lut.exists() else None,
                                   s.get("grade", "eq=contrast=1.06:saturation=1.05"), s.get("delogo"))
        s["dir"] = f"../../shots/{name}_{i:02d}"
        s["frames"] = len(list(d.glob("*.jpg")))
        log(f"shot {i:02d} {s['src']} @{s['in']}s {s['d']}s -> {s['frames']} frames")
    if abs(t - spec["duration"]) > 0.05:
        log(f"note: shots add up to {t:.2f}s, duration is {spec['duration']}s")
    page = work / "films" / name / "index.html"
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text("<!doctype html><meta charset=utf-8><style>html,body{margin:0;background:#000}canvas{display:block}</style>"
                    "<canvas id=c width=1080 height=1920></canvas>"
                    f"<script>window.SPEC={json.dumps(spec, ensure_ascii=False)};</script>"
                    "<script src=../../fonts.js></script><script src=../../engine.js></script>", encoding="utf-8")
    return P, page


def _node(args, log):
    r = subprocess.run(["node", str(RENDER), *map(str, args)], capture_output=True, text=True, encoding="utf-8", errors="ignore")
    for ln in (r.stdout or "").splitlines():
        log(ln)
    if r.returncode:
        raise RuntimeError("render failed: " + (r.stderr or "")[-600:])


def stills(spec_path, times, reuse=True, log=print):
    spec = json.loads(Path(spec_path).read_text(encoding="utf-8-sig"))
    name = Path(spec_path).stem
    P, page = prepare(spec, name, reuse, log)
    out = P["work"] / "out" / f"{name}_stills"
    _node(["--in", page, "--stills", times, "--stills-dir", out, "--duration", spec["duration"]], log)
    return out


def build(spec_path, reuse=False, remux=False, out_name=None, log=print):
    spec = json.loads(Path(spec_path).read_text(encoding="utf-8-sig"))
    name = Path(spec_path).stem
    P, page = prepare(spec, name, reuse or remux, log)
    dur = spec["duration"]
    a = spec["audio"]
    voices = [{**v, "src": str(_src(P["refs"], v["src"]))} for v in a.get("voices", [])]
    mixwav = P["work"] / "out" / f"{name}_mix.wav"
    audio.mix(str(P["audio"] / a["song"]), a["start"], dur, mixwav, voices,
              fade_in=a.get("fadeIn", 0.4), fade_out=a.get("fadeOut", 2.5), song_gain=a.get("songGain", 1.0))
    silent = P["work"] / "out" / f"{name}_video.mp4"
    if not remux:
        _node(["--in", page, "--out", silent, "--duration", dur, "--fps", spec.get("fps", 30)], log)
    P["deliver"].mkdir(parents=True, exist_ok=True)
    final = P["deliver"] / f"{out_name or spec['title']}.mp4"
    # exact length: round(dur * fps) frames, PCM mix -> AAC 320k of the same length (-shortest cut films 3 frames short)
    mux(silent, mixwav, final, duration=dur)
    from dragon.verify import probe_file, line
    r = probe_file(final, "1080x1920", duration=dur)  # delivery gate: black runs, MP3-in-MP4, exact frame count
    log(line(r))
    return final, r
