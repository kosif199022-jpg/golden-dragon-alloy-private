"""Seekable page -> MP4 (or PNG stills) through the shared engines/render/render.cjs, plus optional audio mux."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from ..media import probe

RENDER_CJS = Path(__file__).resolve().parents[1] / "render" / "render.cjs"
# v1.2: no "mp3" here. MP3 stream-copied into MP4 played silent on the owner's iPhone (twice, Oct and Nov 2026),
# so an MP3 track is re-encoded to AAC 320k like any other non-AAC source.
MP4_COPY_AUDIO = ("aac", "alac")


def _node() -> str:
    node = shutil.which("node")
    if not node:
        raise FileNotFoundError("node not found: the HTML renderer needs Node.js and Playwright")
    return node


def render_page(html, out=None, *, width: int, height: int, fps: float = 30, duration: float | None = None,
                crf: int = 17, audio=None, stills=None, stills_dir=None) -> Path:
    """Render `html` (window.__kosif = {duration, seek(t)}) with render.cjs. `stills` = iterable of times -> PNGs only.
    With `audio` the track is stream-copied when MP4 can carry it (else AAC 320k) and cut to the film length."""
    cmd = [_node(), str(RENDER_CJS), "--in", str(html), "--width", str(width), "--height", str(height), "--fps", str(fps)]
    if duration:
        cmd += ["--duration", str(duration)]
    if stills is not None:
        d = Path(stills_dir or Path(html).parent / "stills")
        cmd += ["--stills", ",".join(str(float(t)) for t in stills), "--stills-dir", str(d)]
        _run(cmd)
        return d
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    video = out.with_name(out.stem + ".video.mp4") if audio else out
    _run(cmd + ["--out", str(video), "--crf", str(crf), "--strict"], guard=True)
    if audio:
        a = next((s for s in probe(audio)["streams"] if s["codec_type"] == "audio"), None)
        if a is None:
            raise ValueError(f"{audio} has no audio stream")
        from ..deliver import mux          # v1.3: exact-length mux (frames and samples), never -t on a stream copy
        r = mux(video, audio, out, duration=duration or None)
        if not r.get("ok"):
            raise RuntimeError(f"mux failed verify: {r['verify'].get('errors')}")
        video.unlink(missing_ok=True)
    return out


GUARD_LINES = ("RECOVERED", "BLACK_UNRECOVERED", "SUMMARY")


def _run(cmd, guard=False):
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    text = (r.stdout or "") + (r.stderr or "")
    if guard:                       # the black-run guard's lines reach the session, they are not swallowed
        for ln in text.splitlines():
            if ln.startswith(GUARD_LINES):
                print(ln, flush=True)
    if r.returncode == 3:
        times = [ln.split("t=", 1)[1].split()[0] for ln in text.splitlines() if ln.startswith("BLACK_UNRECOVERED")]
        raise RuntimeError(f"render.cjs: {len(times)} frame(s) stayed black at t={', '.join(times[:12])}"
                           f"{' …' if len(times) > 12 else ''}: render those seconds again (render.cjs --start), then "
                           f"`dragon verify`")
    if r.returncode:
        raise RuntimeError(f"render.cjs failed ({r.returncode}): {(r.stderr or r.stdout)[-1200:]}")
    return r
