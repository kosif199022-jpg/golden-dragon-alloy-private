"""Editorial film edit: an EDL (shots, splits, fx, captions, type layers) -> one seekable page -> MP4 via render.cjs.

The look (grain, bloom, grade, archive age, captions, emphasis type, presenter splits) comes from the layer modules in
assets/ (engine.js, picture.js, captions.js, typeLayers.js, split-layout.js, fonts.js, reel.css); assets/player.js wires
them to the EDL. build() inlines everything into one classic script, so the page also opens from file:// without a server.
"""
from __future__ import annotations

import html
import json
import re
import shutil
from pathlib import Path

from ..media import ffmpeg, probe
from ..web_film.page import fill
from ..web_film.render import render_page

PKG = Path(__file__).resolve().parent
ASSETS, DATA = PKG / "assets", PKG / "data"
EXAMPLE = DATA / "example.edl.json"
MODULES = ["engine.js", "fonts.js", "split-layout.js", "captions.js", "typeLayers.js", "picture.js"]  # dependency order
GRADES = {"clean", "film", "bw", "doc", "bw_hard"}
STYLES = {"display_sans", "display_serif", "serif_ink", "sans_ink", "credit", "heavy", "number", "number_ink", "label_box",
          "typewriter", "typewriter_ink"}
ENTERS = {"soft", "blur", "rise", "cut", "type", "wipe", "slam", "pop", "blurpop", "draw", "flicker"}
EXITS = {"cut", "blur", "fade", "drift"}
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}


def load(path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def bundle(modules_dir=ASSETS) -> str:
    """The ES modules as one script: import lines dropped, `export` keywords removed, all inside one strict IIFE."""
    parts = []
    for name in MODULES + ["player.js"]:
        src = ((ASSETS if name == "player.js" else Path(modules_dir)) / name).read_text(encoding="utf-8")
        src = re.sub(r"^import\s[^;]*;[ \t]*$", "", src, flags=re.M)
        src = re.sub(r"^export\s+(?=(?:const|let|function|class|async)\b)", "", src, flags=re.M)
        parts.append(f"// ---- {name}\n{src}")
    return "(() => {\n'use strict';\n" + "\n".join(parts) + "\n})();"


# --------------------------------------------------------------------------- media


def _sources(edl):
    for s in edl.get("shots", []):
        if s.get("split"):
            yield s, s["split"].get("a", {}).get("source"), "split.a"
            yield s, s["split"].get("b", {}).get("source"), "split.b"
        else:
            yield s, s.get("source"), "source"


def generate_media(edl: dict, base) -> list[Path]:
    """Media entries with a `generate` lavfi graph (the example's stand-in footage) are rendered with ffmpeg."""
    made = []
    for mid, m in (edl.get("media") or {}).items():
        if m.get("generate"):
            dst = Path(base) / m["path"]
            dst.parent.mkdir(parents=True, exist_ok=True)
            if dst.suffix.lower() in IMAGE_EXT:
                ffmpeg("-f", "lavfi", "-i", m["generate"], "-frames:v", "1", "-update", "1", dst)
            else:
                ffmpeg("-f", "lavfi", "-i", m["generate"], "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "16", dst)
            made.append(dst)
    return made


def _extract_frames(src: Path, dst: Path, fps: float) -> int:
    """Video -> numbered JPEGs at the programme fps (a browser never has to decode or seek the codec)."""
    stamp = dst / ".source"
    key = f"{src.resolve()}|{src.stat().st_size}|{src.stat().st_mtime_ns}|{fps}"
    if not (stamp.is_file() and stamp.read_text(encoding="utf-8") == key):
        shutil.rmtree(dst, ignore_errors=True)
        dst.mkdir(parents=True)
        ffmpeg("-i", src, "-vf", f"fps={fps}", "-q:v", "2", dst / "%05d.jpg")
        stamp.write_text(key, encoding="utf-8")
    return len(list(dst.glob("*.jpg")))


def resolve_media(edl: dict, base: Path, out_dir: Path) -> dict:
    """A copy of the EDL whose sources point at files next to the page: images copied, videos as frame folders."""
    edl = json.loads(json.dumps(edl))
    media, fps, done = edl.get("media") or {}, edl["meta"].get("fps", 25), {}
    for shot, src, _ in _sources(edl):
        if not src or src.get("type") == "color":
            continue
        mid = src.pop("media", None)
        path = Path(media[mid]["path"]) if mid else Path(src.get("src") or src.get("path"))
        path = path if path.is_absolute() else base / path
        name = mid or path.stem
        if path not in done:
            if src["type"] == "image":
                dst = out_dir / "media" / f"{name}{path.suffix.lower()}"
                dst.parent.mkdir(parents=True, exist_ok=True)
                if path.resolve() != dst.resolve():
                    shutil.copy2(path, dst)
                done[path] = {"type": "image", "src": dst.relative_to(out_dir).as_posix()}
            else:
                dst = out_dir / "media" / name
                done[path] = {"type": "frames", "dir": dst.relative_to(out_dir).as_posix(),
                              "count": _extract_frames(path, dst, fps), "fps": fps}
        src.pop("src", None)
        src.pop("path", None)
        src.update({**done[path], **({"in": src["in"]} if "in" in src else {})})
    edl.pop("media", None)
    return edl


# --------------------------------------------------------------------------- check


def _num(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def check(edl: dict, base=None) -> dict:
    """Structure of an edit: timeline tiles the duration, sources exist, fx/type names are known, captions are in order."""
    errs, m = [], edl.get("meta") or {}
    W, H, fps, dur = m.get("width"), m.get("height"), m.get("fps", 25), m.get("duration")
    if not (isinstance(W, int) and isinstance(H, int) and W > 0 and H > 0):
        errs.append("meta.width/height must be positive whole numbers")
    if not _num(fps) or fps <= 0:
        errs.append("meta.fps must be positive")
    if not _num(dur) or dur <= 0:
        return {"ok": False, "errors": errs + ["meta.duration must be a positive number"], "stats": {}}
    shots, t = edl.get("shots") or [], 0.0
    if not shots:
        errs.append("no shots")
    for i, s in enumerate(shots):
        a, b = s.get("t0"), s.get("t1")
        if not (_num(a) and _num(b) and b > a):
            errs.append(f"shot {i}: t0/t1 invalid")
            continue
        if abs(a - t) > 1e-3:
            errs.append(f"shot {i} starts at {a}, expected {round(t, 3)}: no gaps or overlaps (a gap shows black)")
        t = b
        grade = (s.get("fx") or {}).get("grade", "clean")
        if grade not in GRADES:
            errs.append(f"shot {i}: grade {grade!r} is not one of {', '.join(sorted(GRADES))}")
        if s.get("split"):
            sp = s["split"]
            if not (sp.get("a") and sp.get("b")):
                errs.append(f"shot {i}: a split needs panels a and b")
            if sp.get("dir", "h" if W and H and W > H else "v") == "h" and sum(sp.get(k, {}).get("kind") == "presenter" for k in "ab") == 2:
                errs.append(f"shot {i}: a split holds one presenter at most")
    if shots and abs(t - dur) > 1e-3:
        errs.append(f"shots end at {round(t, 3)} but the edit is {dur} s")
    media = edl.get("media") or {}
    for shot, src, where in _sources(edl):
        i = shots.index(shot)
        if not src:
            errs.append(f"shot {i}: {where} is missing")
            continue
        if src.get("type") not in ("color", "image", "video", "frames"):
            errs.append(f"shot {i}: {where} type must be color, image or video")
        elif src.get("type") in ("image", "video"):
            mid = src.get("media")
            if mid is not None and mid not in media:
                errs.append(f"shot {i}: {where} media {mid!r} is not in the media list")
            elif base is not None:
                p = Path(media[mid]["path"] if mid else src.get("src", ""))
                p = p if p.is_absolute() else Path(base) / p
                if not p.is_file() and not (mid and media[mid].get("generate")):
                    errs.append(f"shot {i}: {where} file not found: {p}")
    words = 0
    last = -1.0
    for k, c in enumerate((edl.get("captions") or {}).get("chunks", [])):
        if not (_num(c.get("t0")) and _num(c.get("t1")) and c["t1"] > c["t0"]):
            errs.append(f"caption {k}: t0/t1 invalid")
            continue
        if c["t0"] < last - 1e-6:
            errs.append(f"caption {k} starts before caption {k - 1} ends: one caption on screen at a time")
        last = c["t1"]
        ws = c.get("words") or []
        words += len(ws)
        idx = sorted(i for line in c.get("lines") or [] for i in line)
        if idx != list(range(len(ws))):
            errs.append(f"caption {k}: lines must use every word index once, in order")
        prev = c["t0"] - 1e-6
        for w in ws:
            if not (_num(w.get("t0")) and c["t0"] - 1e-6 <= w["t0"] <= c["t1"]):
                errs.append(f"caption {k}: word {w.get('w')!r} at {w.get('t0')} is outside its caption {c['t0']}-{c['t1']}")
            elif w["t0"] < prev:
                errs.append(f"caption {k}: word {w.get('w')!r} appears before the word spoken ahead of it")
            else:
                prev = w["t0"]
    for L in edl.get("type") or []:
        name = L.get("id") or L.get("text")
        if L.get("style") not in STYLES:
            errs.append(f"type {name!r}: style must be one of {', '.join(sorted(STYLES))}")
        if L.get("enter", "blur") not in ENTERS:
            errs.append(f"type {name!r}: enter must be one of {', '.join(sorted(ENTERS))}")
        if L.get("exit", "cut") not in EXITS:
            errs.append(f"type {name!r}: exit must be one of {', '.join(sorted(EXITS))}")
        if not (_num(L.get("t0")) and _num(L.get("t1")) and 0 <= L["t0"] < L["t1"] <= dur + 1e-6):
            errs.append(f"type {name!r}: t0/t1 must lie inside the edit")
        if _num(L.get("x")) and _num(L.get("y")) and W and H and not (0 <= L["x"] <= W and 0 <= L["y"] <= H):
            errs.append(f"type {name!r}: anchor ({L['x']}, {L['y']}) is outside the {W}x{H} frame")
    stats = {"shots": len(shots), "splits": sum(bool(s.get("split")) for s in shots), "caption_words": words,
             "type_layers": len(edl.get("type") or []), "frames": round(dur * fps)}
    return {"ok": not errs, "errors": errs, "stats": stats}


# --------------------------------------------------------------------------- build / render


def build(edl_path, out, modules_dir=ASSETS, css=None) -> Path:
    """EDL -> self-contained page (media copied or extracted next to it). `modules_dir`/`css` swap in other layer modules."""
    edl_path, out = Path(edl_path), Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    edl = resolve_media(load(edl_path), edl_path.parent, out.parent)
    page = fill((ASSETS / "page.html").read_text(encoding="utf-8"),
                TITLE=html.escape(str(edl.get("title", "editorial film"))),
                CSS=Path(css or Path(modules_dir) / "reel.css").read_text(encoding="utf-8"),
                EDL=json.dumps(edl, ensure_ascii=False).replace("</", "<\\/"), JS=bundle(modules_dir))
    out.write_text(page, encoding="utf-8")
    return out


def render(edl_path, out, stills=None, audio=None) -> Path:
    """build + render.cjs. `audio` = a track to lay under the picture (e.g. the presenter's original sound)."""
    edl = load(edl_path)
    m = edl["meta"]
    page = build(edl_path, Path(out).with_suffix(".html"))
    if audio is None and m.get("audio"):
        audio = Path(m["audio"]) if Path(m["audio"]).is_absolute() else Path(edl_path).parent / m["audio"]
    return render_page(page, out, width=m["width"], height=m["height"], fps=m.get("fps", 25), duration=m["duration"],
                       audio=audio, stills=stills, stills_dir=Path(out).parent / "stills" if stills else None)


def example(out_dir) -> Path:
    """The example EDL plus its generated stand-in media (a test pattern 'presenter' and a fractal 'insert')."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    dst = out_dir / "edit.edl.json"
    shutil.copy2(EXAMPLE, dst)
    generate_media(load(dst), out_dir)
    return dst


def doctor() -> dict:
    from ..web_film.render import RENDER_CJS
    return {"ffmpeg": shutil.which("ffmpeg") or "MISSING", "node": shutil.which("node") or "MISSING",
            "render.cjs": str(RENDER_CJS) if RENDER_CJS.is_file() else "MISSING"}


def verify(path, edl: dict) -> dict:
    """The export itself: frame count, fps, size, duration against the EDL."""
    info = probe(path)
    v = next(s for s in info["streams"] if s["codec_type"] == "video")
    m = edl["meta"]
    want = round(m["duration"] * m.get("fps", 25))
    got = int(v.get("nb_frames") or 0)
    ok = (v["width"], v["height"]) == (m["width"], m["height"]) and (not got or got == want)
    return {"ok": ok, "width": v["width"], "height": v["height"], "frames": got, "expected_frames": want,
            "duration": round(float(info["format"]["duration"]), 3), "fps": v["r_frame_rate"],
            "audio": any(s["codec_type"] == "audio" for s in info["streams"])}
