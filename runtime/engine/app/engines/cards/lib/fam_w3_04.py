"""Helpers of runners/fam_w3_04.py used by data cards, copied verbatim (the extractor binds a card to them only when
their AST hash with every dependency equals the original's)."""
from __future__ import annotations

from pathlib import Path
from contextlib import contextmanager
import json
import numpy as np
import shutil


def jw(path, obj):
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
    return Path(path)


def wt(path, text):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(text, encoding="utf-8")
    return Path(path)


def browser_path():
    for name in ("google-chrome", "chromium", "chromium-browser"):
        if shutil.which(name):
            return shutil.which(name)
    for p in sorted(Path("/opt/pw-browsers").glob("chromium-*/chrome-linux*/chrome")):
        return str(p)
    return None


def browser_page(wd, w=320, h=180):
    """A headless Chromium page (Playwright). Its profile is a temporary folder Playwright removes on close (a long
    TMPDIR breaks Chromium's socket path, so it is left at the system default)."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        b = pw.chromium.launch(executable_path=browser_path(), headless=True,
                               args=["--no-sandbox", "--allow-file-access-from-files", "--disable-gpu",
                                     "--autoplay-policy=no-user-gesture-required"])
        try:
            yield b.new_page(viewport={"width": w, "height": h})
        finally:
            b.close()


def png_rgb(data_or_path):
    from PIL import Image
    import io
    im = Image.open(io.BytesIO(data_or_path) if isinstance(data_or_path, (bytes, bytearray)) else data_or_path)
    return np.asarray(im.convert("RGB"))


MARKER_COLOURS = {"CHAPTER": "Blue", "GFX": "Green", "HOOK": "Red", "REVIEW": "Yellow"}


def place_markers(timeline):
    """Markers are stored against a clip (clip id + offset inside it) and placed on the record timeline from the cut."""
    starts, t = {}, 0.0
    for c in timeline["layers"]["V1"]:
        starts[c["id"]] = (t, c["in"], c["out"])
        t += c["out"] - c["in"]
    placed = []
    for m in timeline["anchors"]:
        rec0, cin, cout = starts[m["clip"]]
        src = m["src_t"]
        if cin <= src < cout:
            placed.append({"name": m["name"], "kind": m["kind"], "color": MARKER_COLOURS[m["kind"]], "t": round(rec0 + src - cin, 3)})
    return placed


def cpm(tasks):
    order, seen = [], set()

    def visit(n):
        if n in seen:
            return
        for d in tasks[n][1]:
            visit(d)
        seen.add(n)
        order.append(n)
    for n in tasks:
        visit(n)
    es = {}
    for n in order:
        es[n] = max([es[d] + tasks[d][0] for d in tasks[n][1]], default=0.0)
    end = max(es[n] + tasks[n][0] for n in tasks)
    lf = {n: end for n in tasks}
    for n in reversed(order):
        succ = [s for s in tasks if n in tasks[s][1]]
        if succ:
            lf[n] = min(lf[s] - tasks[s][0] for s in succ)
    slack = {n: round(lf[n] - tasks[n][0] - es[n], 6) for n in tasks}
    crit = [n for n in order if slack[n] == 0]
    return end, es, slack, crit


def lock_violations(schedule):
    """Finishing work that starts before picture lock is rework."""
    lock = schedule["picture_lock"]
    return [n for n in ("vfx", "colour", "sound", "conform") if schedule[n] < lock]


def _alias_db(y, sr, f0):
    w = np.hanning(len(y))
    P = np.abs(np.fft.rfft(y * w)) ** 2
    fr = np.fft.rfftfreq(len(y), 1 / sr)
    harm = np.zeros_like(fr, bool)
    for k in range(1, 60, 2):
        f = k * f0
        if f < sr / 2:
            harm |= np.abs(fr - f) <= 4
    sig, alias = P[harm].sum(), P[~harm & (fr > 20)].sum()
    return float(10 * np.log10(alias / sig))
