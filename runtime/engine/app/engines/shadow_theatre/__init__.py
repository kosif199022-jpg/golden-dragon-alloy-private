"""Shadow Theatre (مسرح الظل): silhouette films drawn from a scene JSON — gradient skies under a projector, jointed bodies
that join into trees and boats, shadows that grow near the lamp, iris and spotlight transitions.

Pure numpy + Pillow raster (no browser), frames piped straight into ffmpeg at the KOSIF export standard.
Scene grammar: data/scene-grammar.md; demo scene: data/lantern-keeper.json; poses/props/backdrops: data/library.json.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from PIL import Image

from . import engine as E
from .engine import ShadowRenderer, BACKDROPS, COSTUMES, POSES, LIB
from .score import synth_score
from ..deliver import fit_audio
from ..media import exe, probe

DATA = Path(__file__).resolve().parent / "data"
TECHNIQUES: dict[str, str] = LIB["techniques"]
DEMO = DATA / "lantern-keeper.json"
# the KOSIF export standard, the same encode engines/render/render.cjs uses
VIDEO_ARGS = ["-vf", "scale=out_color_matrix=bt709:out_range=tv,format=yuv420p", "-c:v", "libx264", "-preset", "slow",
              "-crf", "17", "-profile:v", "high", "-pix_fmt", "yuv420p", "-colorspace", "bt709", "-color_primaries", "bt709",
              "-color_trc", "bt709", "-color_range", "tv", "-x264-params", "colorprim=bt709:transfer=bt709:colormatrix=bt709"]


def load_spec(path) -> dict:
    spec = json.loads(Path(path).read_text(encoding="utf-8"))
    for s in spec["scenes"]:
        for a in s.get("actors", []):
            a["keys"] = sorted(a.get("keys") or [{"t": 0}], key=lambda k: k["t"])
    spec.setdefault("duration", spec["scenes"][-1]["end"])
    return spec


def _actor_errors(i, s, a) -> list[str]:
    errs = []
    try:
        if a.get("type", "human") == "human":
            for k in a.get("keys", []):
                if "pose" in k:
                    E.resolve_pose(k["pose"])
            if a.get("costume", "plain") not in COSTUMES:
                errs.append(f"scene {i}: unknown costume {a.get('costume')!r}")
        else:
            E.draw_prop(Image.new("L", (64, 64)), a["shape"], 32, 32, 20, 0, 0, a.get("params", {}))
    except KeyError as e:
        errs.append(f"scene {i}: {e.args[0]}")
    ks = [k["t"] for k in a.get("keys", [])]
    if ks and (min(ks) < 0 or max(ks) > s["end"] - s["start"] + 1e-6):
        errs.append(f"scene {i}: a key time is outside the scene ({min(ks)}..{max(ks)})")
    return errs


def techniques_in(spec) -> set:
    """Declared techniques plus the ones the spec visibly uses (iris, spotlight, depth, walk cycle)."""
    used = set()
    for s in spec.get("scenes", []):
        used.update(s.get("techniques", []))
        bd = s.get("backdrop", "")
        if s.get("iris"):
            used.add("iris")
        if s.get("spot") or (isinstance(bd, str) and BACKDROPS.get(bd, {}).get("spot")):
            used.add("spotlight")
        for a in s.get("actors", []):
            if any(float(k.get("depth", 0)) > 0.3 for k in a.get("keys", [])):
                used.add("depth-scale")
            if a.get("cycle", {}).get("type") == "walk":
                used.add("walk-in")
    return used


def check_spec(spec: dict) -> list[str]:
    """Timing + style grammar; an empty list means the spec passes."""
    errs, scenes, t = [], spec.get("scenes", []), 0.0
    if len(scenes) < 3:
        errs.append("need at least 3 scenes (chapters)")
    for i, s in enumerate(scenes):
        if abs(s["start"] - t) > 1e-6:
            errs.append(f"scene {i} starts at {s['start']} but the previous ended at {t}: gap or overlap")
        if s["end"] <= s["start"]:
            errs.append(f"scene {i} has no length")
        t = s["end"]
        if not s.get("actors"):
            errs.append(f"scene {i} has no actors: a shadow scene needs a silhouette")
        if s.get("backdrop", "night-blue") not in BACKDROPS and not isinstance(s.get("backdrop"), dict):
            errs.append(f"scene {i}: unknown backdrop {s.get('backdrop')!r}")
        for a in s.get("actors", []):
            errs += _actor_errors(i, s, a)
    if scenes and abs(t - float(spec.get("duration", t))) > 1e-6:
        errs.append(f"scenes end at {t} but duration is {spec.get('duration')}")
    trans = [s.get("transition_in", "blackout") for s in scenes]
    errs += [f"scenes {i - 1} and {i} use the same transition {trans[i]!r} back to back"
             for i in range(1, len(trans)) if trans[i] == trans[i - 1] and trans[i] != "blackout"]
    if len(scenes) >= 3 and len({round(s["end"] - s["start"], 2) for s in scenes}) == 1:
        errs.append("every scene has the same length: vary the pacing")
    used = techniques_in(spec)
    if used - set(TECHNIQUES):
        errs.append(f"unknown techniques {sorted(used - set(TECHNIQUES))}")
    if len(used & set(TECHNIQUES)) < 4:
        errs.append(f"only {sorted(used)} used: the style needs at least 4 of {sorted(TECHNIQUES)}")
    if "body-build" not in used:
        errs.append("no body-build moment: the signature of the style is bodies forming one object")
    if not any(s.get("memorable") for s in scenes):
        errs.append("mark one scene memorable: the image the audience keeps")
    return errs


def techniques_used(spec) -> list[str]:
    return sorted({x for s in spec["scenes"] for x in s.get("techniques", [])})


def renderer(spec: dict, preview: bool = False):
    """Preview = half size at <= 15 fps."""
    if preview:
        spec = dict(spec, width=spec.get("width", 1080) // 2, height=spec.get("height", 1920) // 2, fps=min(15, spec.get("fps", 30)))
    if spec.get("puppetry") or any(isinstance(a, dict) and a.get("puppet") for s in spec.get("scenes", []) for a in s.get("actors", [])):
        from . import puppet  # rod puppets: real optics, rods, a puppeteer's hand, an oil lamp (opt-in, see puppet.py)
        puppet.register(E)
    return ShadowRenderer(spec), spec


def stills(spec: dict, out, times=None, preview=False) -> list[Path]:
    """PNG per time (default: the middle of every chapter) plus a side-by-side sheet when there are several."""
    rnd, spec = renderer(spec, preview)
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    times = times or [round((s["start"] + s["end"]) / 2, 2) for s in spec["scenes"]]
    paths = []
    for tt in times:
        p = out / f"still_{tt:06.2f}.png"
        Image.fromarray(rnd.render(tt).rgb).save(p)
        paths.append(p)
    if len(paths) > 1:
        ims = [Image.open(p) for p in paths]
        k = 480 / ims[0].size[0]
        tw, th = int(ims[0].size[0] * k), int(ims[0].size[1] * k)
        sheet = Image.new("RGB", (tw * len(ims), th))
        for i, im in enumerate(ims):
            sheet.paste(im.resize((tw, th)), (i * tw, 0))
        sheet.save(out / "stills_sheet.jpg", quality=88)
        paths.append(out / "stills_sheet.jpg")
    return paths


def render_film(spec: dict, out, preview=False, audio=True, keep_wav=False, progress=print) -> dict:
    """Every frame piped as raw RGB into ffmpeg (no frames on disk); the synth score is mixed in as AAC 320k."""
    rnd, spec = renderer(spec, preview)
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fps = spec.get("fps", 30)
    n = int(round(float(spec["duration"]) * fps))
    cmd = [exe("ffmpeg"), "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{rnd.W}x{rnd.H}", "-r", str(fps), "-i", "-"]
    wav = synth_score(spec, out.with_suffix(".score.wav")) if audio else None
    if wav:
        cmd += ["-i", str(wav)]
    cmd += [*VIDEO_ARGS, "-r", str(fps), "-frames:v", str(n)]
    if wav:  # exact length: n frames and the score padded/trimmed to n / fps (no -shortest)
        cmd += ["-af", fit_audio(n / fps), "-c:a", "aac", "-b:a", "320k"]
    proc = subprocess.Popen(cmd + ["-movflags", "+faststart", str(out)], stdin=subprocess.PIPE)
    try:
        for i in range(n):
            proc.stdin.write(rnd.render(i / fps).rgb.tobytes())
            if progress and i % max(1, n // 10) == 0:
                progress(f"frame {i}/{n}")
    finally:
        proc.stdin.close()
        rc = proc.wait()
        if wav and not keep_wav:
            wav.unlink(missing_ok=True)
    if rc:
        raise RuntimeError(f"ffmpeg failed ({rc})")
    info = probe(out)
    v = next(s for s in info["streams"] if s["codec_type"] == "video")
    return {"out": str(out), "width": v["width"], "height": v["height"], "fps": v["r_frame_rate"],
            "duration": round(float(info["format"]["duration"]), 2),
            "audio": any(s["codec_type"] == "audio" for s in info["streams"])}


__all__ = ["ShadowRenderer", "BACKDROPS", "COSTUMES", "POSES", "TECHNIQUES", "DEMO", "load_spec", "check_spec",
           "techniques_used", "renderer", "stills", "render_film", "synth_score"]
