"""Scene + render: engine numbers -> self-contained seekable HTML (assets/scene.html) -> stills, pixel A/B/C diff, MP4.

Page contract: window.__kosif = {duration, fps, seek} (engines/render/render.cjs), plus window.seek / __ready /
kmxPixelDiff(t) / scoreSound for assets/capture.cjs. Views: ?view=grid | A_full | B_no_coupling | C_no_memory, ?storyboard=1.
"""
import base64, json, os, shutil, subprocess, tempfile
from pathlib import Path
from . import engine as E

HERE = Path(__file__).resolve().parent
ASSETS = HERE / "assets"
RENDER = HERE.parent / "render" / "render.cjs"


def _b64(data):
    return base64.b64encode(bytes(data)).decode("ascii")


def encode_run(run, rec):
    W, H, cap = rec["grid"]["w"], rec["grid"]["h"], rec["memory"]["cap"]
    mem = bytearray(min(255, int(round(v / cap * 255))) for M in run["memory"] for v in M)
    parts = bytearray()
    for pts in run["particles"]:
        for x, y in pts:
            for v, hi in ((x, W), (y, H)):
                q = max(0, min(65535, int(round(v / hi * 65535))))
                parts.extend((q & 255, q >> 8))
    return {"memory": _b64(mem), "particles": _b64(parts)}


def scene_data(rec, runs, metrics, verdict=None):
    n, fps = len(next(iter(runs.values()))["memory"]), rec["fps"]
    beam = [[round(c, 3) for c in E.beam_position(rec, f / fps)] if E.beam_on(rec, f / fps) else None for f in range(n)]
    tile, absorb = next(iter(runs.values()))["tiles"]
    sites, absorb_of = E.tile_sites(rec)
    peak = max(max(M) for run in runs.values() for M in run["memory"]) or 1.0
    return {"recipe": {k: rec[k] for k in ("id", "slug", "title_ar", "title_en", "fps", "duration", "particles", "grid", "finish", "stimulus")},
            "frames": n,
            "conditions": [{"key": k, "label_ar": rec["conditions"][k]["label_ar"], "label_en": rec["conditions"][k]["label_en"],
                            **encode_run(runs[k], rec)} for k in rec["conditions"]],
            "tile": tile, "absorb": [round(a, 3) for a in absorb], "beam": beam,
            "sites": [[round(x, 3), round(y, 3)] for x, y in sites], "site_absorb": [round(a, 3) for a in absorb_of],
            "display_peak": round(peak / rec["memory"]["cap"], 4),
            "curves": {k: v["capture_curve"] for k, v in metrics.items() if isinstance(v, dict) and "capture_curve" in v},
            "chance": metrics.get("_chance_level"), "off_frame": metrics.get("_light_off_frame"), "verdict": verdict}


def write_scene(path, rec, runs, metrics, verdict=None):
    data = scene_data(rec, runs, metrics, verdict)
    js = lambda name: (ASSETS / name).read_text(encoding="utf-8").replace("</script", "<\\/script")
    html = ((ASSETS / "scene.html").read_text(encoding="utf-8").replace("__TITLE__", "KOSIF Matrices · " + rec["title_en"])
            .replace("__FONT__", _b64((ASSETS / "KOSIFJumuah-Bold.woff2").read_bytes()))
            .replace("__HARNESS__", js("atlas_harness.js")).replace("__SOUND__", js("atlas_sound.js"))
            .replace("__DATA__", json.dumps(data, separators=(",", ":"))))
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(html, encoding="utf-8")
    return {"out": str(p), "bytes": p.stat().st_size, "frames": data["frames"], "conditions": [c["key"] for c in data["conditions"]]}


# ------------------------------------------------------------------ browser side
def node_playwright():
    if not shutil.which("node"):
        return False
    code = ("const p=require('path');const r=[process.env.KOSIF_ROOT,p.join(process.env.USERPROFILE||process.env.HOME||'','kosif-tool'),"
            "process.cwd()].filter(Boolean).map(x=>p.join(x,'node_modules'));try{require(require.resolve('playwright',{paths:r})).chromium;"
            "process.exit(0)}catch(e){process.exit(1)}")
    return subprocess.run(["node", "-e", code], capture_output=True).returncode == 0


def capture(scene, out_dir, times, views=("grid", "A_full"), wav=None):
    """Stills (<view>_<t>.jpg), pixel A/B/C differences, determinism probe, optional offline WAV of the score."""
    cmd = ["node", str(ASSETS / "capture.cjs"), "--in", str(scene), "--out-dir", str(out_dir), "--times", ",".join(map(str, times)),
           "--views", ",".join(views)] + (["--wav", str(wav)] if wav else [])
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode:
        raise RuntimeError("capture failed: " + r.stderr[-2000:])
    return json.loads(r.stdout.strip().splitlines()[-1])


def render_mp4(scene, mp4, fps, duration, wav=None, width=1280, height=720):
    """Seekable scene -> MP4 with the shared renderer, then mux the offline score (AAC) when given."""
    mp4 = Path(mp4)
    silent = mp4.with_name(mp4.stem + ".video.mp4") if wav else mp4
    r = subprocess.run(["node", str(RENDER), "--in", str(scene), "--out", str(silent), "--width", str(width), "--height", str(height),
                        "--fps", str(fps), "--duration", str(duration)], capture_output=True, text=True, encoding="utf-8", errors="replace")
    log = [l for l in (r.stdout + r.stderr).splitlines() if l.startswith("VIDEO") or "failed" in l][-1:]
    if r.returncode:
        return None, log
    if wav:  # exact length: round(duration * fps) frames, the score as AAC 320k of the same length (no -shortest)
        from ..deliver import mux
        mux(silent, wav, mp4, duration=duration)
        silent.unlink()
    return mp4, [l.replace(str(mp4.parent) + os.sep, "") for l in log]


def render_experiment(rec, out, mp4=False):
    """Stills at four moments around the beam switch-off + pixel diff; optional MP4. Returns the report's render block."""
    off = rec["stimulus"]["on"][1]
    times = [round(off * 0.6, 2), round(off - 0.1, 2), round(off + 2.0, 2), round(rec["duration"] - 0.1, 2)]
    wav = Path(tempfile.gettempdir()) / ("kmx-%s.wav" % rec["slug"]) if mp4 else None
    rd = capture(out / "scene.html", out / "stills", times, wav=wav)
    rd["stills"] = [str(Path(p).relative_to(out)) for p in rd["stills"]]
    rd.pop("wav", None)
    after = [d for t, d in rd["pixel_diff"].items() if float(t) > off]
    rd["visible_difference_after_off"] = all(d["A_full|B_no_coupling"]["changed_pixel_share"] > 0.01 for d in after) if after else False
    if mp4:
        path, log = render_mp4(out / "scene.html", out / (rec["slug"] + ".mp4"), rec["fps"], rec["duration"], wav)
        rd.update(mp4=path.name if path else None, mp4_log=log)
        wav.unlink(missing_ok=True)
    return rd
