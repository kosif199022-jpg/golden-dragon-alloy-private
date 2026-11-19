"""Helpers of runners/fam_camera_composition_layout_a.py used by data cards, copied verbatim (the extractor binds a card to them only when
their AST hash with every dependency equals the original's)."""
from __future__ import annotations

from pathlib import Path
from .core import fx
import math
import numpy as np
import subprocess


sine_io = lambda x: -(math.cos(math.pi * x) - 1) / 2


def hex2rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def write_video(path: Path, frames, fps):
    H, W = frames[0].shape[:2]
    done = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
                           "-s", "%dx%d" % (W, H), "-r", str(fps), "-i", "-", "-c:v", "libx264rgb", "-qp", "0",
                           "-preset", "ultrafast", str(path)], input=b"".join(np.ascontiguousarray(f, np.uint8).tobytes()
                                                                              for f in frames),
                          capture_output=True, timeout=60)
    if done.returncode:
        raise RuntimeError(done.stderr.decode(errors="replace")[-300:])
    return Path(path)


def read_video(path: Path):
    p = fx.probe(path)["streams"][0]
    return fx.frames(path, size=(int(p["width"]), int(p["height"])))


_GRIDS = {}


def _grid(h, w):
    if (h, w) not in _GRIDS:
        _GRIDS[(h, w)] = np.mgrid[0:h, 0:w].astype(np.float32)
    return _GRIDS[(h, w)]


def blob(frame, rgb, tol=40, bg=None):
    """Centroid, area, orientation (deg) of one marker colour; None when absent. With bg (the known flat background)
    antialiased edge pixels count by their coverage, so centroids and areas are sub-pixel."""
    f = frame[..., :3].astype(np.float32)
    c = np.array(rgb, np.float32)
    if bg is not None:
        b = np.array(bg, np.float32)
        v = c - b
        a = np.clip(((f - b) @ v) / (v @ v), 0, 1)
        resid = np.abs(f - (b + a[..., None] * v)).max(-1)
        w = np.where((resid < 30) & (a > 0.04), a, 0.0)
    else:
        w = (np.abs(f - c).max(-1) <= tol).astype(float)
    tot = w.sum()
    if tot < 3:
        return None
    ys, xs = _grid(f.shape[0], f.shape[1])
    cx, cy = (w * xs).sum() / tot + 0.5, (w * ys).sum() / tot + 0.5          # pixel centres sit at +0.5
    mxx, myy, mxy = (w * (xs - cx) ** 2).sum() / tot, (w * (ys - cy) ** 2).sum() / tot, (w * (xs - cx) * (ys - cy)).sum() / tot
    ang = 0.5 * math.degrees(math.atan2(2 * mxy, mxx - myy))
    yy, xx = np.nonzero(w > 0.5)
    if len(xx) == 0:
        yy, xx = np.nonzero(w > 0)
    return {"cx": float(cx), "cy": float(cy), "area": float(tot), "ang": ang,
            "x0": int(xx.min()), "x1": int(xx.max()), "y0": int(yy.min()), "y1": int(yy.max())}


def track_colors(frames, cols, tol=40, bg=None):
    import hashlib
    memo, out = {}, []
    for f in frames:
        h = hashlib.md5(np.ascontiguousarray(f).tobytes()).hexdigest()   # identical frames measure identically
        if h not in memo:
            memo[h] = [blob(f, c, tol, bg) for c in cols]
        out.append(memo[h])
    return out


def times_for(dur, fps):
    return [round(i / fps, 6) for i in range(int(round(dur * fps)) + 1)]


RED, BLUE = "#ff0000", "#0000ff"


def ff(*args, timeout=40):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *map(str, args)], capture_output=True, text=True, timeout=timeout)
    if r.returncode:
        raise RuntimeError("ffmpeg: " + r.stderr[-400:])


def _caption_frames(kind, W=180, H=320, n=3):
    """3 sampled frames of a synthetic shot: a moving textured subject, flat clean areas and (optionally) a baked graphic."""
    rng = np.random.default_rng(7)
    tex = rng.integers(40, 220, (H, W, 3)).astype(np.uint8)
    frames = []
    for i in range(n):
        f = np.zeros((H, W, 3), np.uint8) + np.array([70, 90, 110], np.uint8)
        if kind == "side":                             # subject on the left, a baked logo top-right
            x0, x1, y0, y1 = 10 + 2 * i, 80 + 2 * i, 60, 300
            f[10:40, 130:170] = tex[10:40, 130:170]
        elif kind == "portrait":                       # subject fills the centre
            x0, x1, y0, y1 = 25 + i, 155 + i, 110, 320
        else:                                          # narrow centred subject looking right
            x0, x1, y0, y1 = 70 + i, 110 + i, 80, 300
        f[y0:y1, x0:x1] = tex[y0:y1, x0:x1]
        frames.append(f)
    return frames


def caption_place(frames, gaze=None, cw=0.42, ch=0.12):
    """layout heuristics: detail + motion map over 3 frames -> clean cells; scene type; bigger clean zone; crown; validate."""
    a = np.stack([f.astype(float).mean(-1) for f in frames])
    H, W = a.shape[1:]
    grad = np.abs(np.diff(a, axis=2, prepend=a[:, :, :1])).mean(0) + np.abs(np.diff(a, axis=1, prepend=a[:, :1])).mean(0)
    busy = (grad + a.std(0)) > 4
    cell = 10
    bc = busy[:H // cell * cell, :W // cell * cell].reshape(H // cell, cell, W // cell, cell).any((1, 3))
    cols = bc.any(0)
    subj = a.std(0) > 2                                # the moving subject
    sx = np.nonzero(subj.any(0))[0]
    sw = (sx.max() - sx.min() + 1) / W if len(sx) else 0
    zones = {"left": (0, 0, int(sx.min()) if len(sx) else W // 2, H), "right": (int(sx.max()) + 1 if len(sx) else W // 2, 0, W, H),
             "top": (0, 0, W, int(np.nonzero(subj.any(1))[0].min()) if len(sx) else H // 4)}

    def clean_area(z):
        x0, y0, x1, y1 = z
        return float((~busy[y0:y1, x0:x1]).sum())
    if sw > 0.55:
        kind, side = "portrait-header", "top"
    else:
        kind = "corner-column-crown"
        l, r = clean_area(zones["left"]), clean_area(zones["right"])
        side = ("right" if r >= l else "left") if abs(l - r) > 0.1 * max(l, r) or gaze is None else gaze
    x0, y0, x1, y1 = zones[side]
    # crown: the first clean band of caption height inside the zone, from the top
    hh, ww = int(ch * H), min(int(cw * W), x1 - x0)
    rect = None
    for yy in range(y0, y1 - hh, 2):
        for xx in ([x0 + (x1 - x0 - ww) // 2] if side == "top" else [x0, x1 - ww]):
            if not busy[yy:yy + hh, xx:xx + ww].any():
                rect = (xx, yy, ww, hh)
                break
        if rect:
            break
    return {"type": kind, "side": side, "rect": rect, "busy": busy, "subject_w": sw}


def caption_valid(rect, busy):
    if rect is None:
        return False
    x, y, w, h = rect
    return not busy[y:y + h, x:x + w].any()


GREY = (119, 119, 119)


def marker_png(path, W, H, marks, bg=GREY):
    """A 'screenshot' plate: flat grey with coloured markers (x, y, w, h, hex) whose centroids are measured later."""
    from PIL import Image, ImageDraw
    im = Image.new("RGB", (W, H), bg)
    d = ImageDraw.Draw(im)
    for x, y, w, h, c in marks:
        d.rectangle([x, y, x + w - 1, y + h - 1], fill=hex2rgb(c))
    im.save(path)
    return Path(path)


def ff_zoom(wd, name, src, W, H, dur, fps, zexpr, ss=4, post=""):
    """Centre zoom with a per-frame scale expression in t (scale eval=frame on a ss-x supersampled plate, centre crop,
    area downscale)."""
    out = wd / ("%s.mp4" % name)
    vf = ("scale=%d:%d:flags=bicubic,scale=w='trunc(%d*(%s)/2)*2':h=-2:eval=frame:flags=bicubic,crop=%d:%d,scale=%d:%d:flags=area%s"
          % (W * ss, H * ss, W * ss, zexpr, W * ss, H * ss, W, H, post))
    ff("-loop", "1", "-framerate", fps, "-i", src, "-t", dur, "-vf", vf, "-r", fps, "-c:v", "libx264rgb", "-qp", "0", "-preset", "ultrafast", out)
    return out


ZMARKS = [(40, 30, 14, 14, RED), (266, 136, 14, 14, BLUE)]


def zoom_series(video, cols=(RED, BLUE), bg=GREY, tol=None):
    fr = read_video(video)
    m = track_colors(fr, [hex2rgb(c) for c in cols], tol=tol or 40, bg=None if tol else bg)
    d = [math.hypot(a["cx"] - b["cx"], a["cy"] - b["cy"]) if a and b else float("nan") for a, b in m]
    return np.array(d) / d[0], fr, m


def chaikin(pts, passes):
    p = np.asarray(pts, float)
    for _ in range(passes):
        q = [p[0]]
        for a, b in zip(p[:-1], p[1:]):
            q += [.75 * a + .25 * b, .25 * a + .75 * b]
        q.append(p[-1])
        p = np.array(q)
    return p


def flyover(route, passes=3, travel=13.0, secs=24.0, fps=10, look=1.5, gain=.6, roll_max=.13, alt=(4600, 4300), pitch_nadir=76):
    """The card's flyover camera: Chaikin-rounded path walked by arc length at constant ground speed, heading = bearing
    to the point LOOK_AHEAD further, constant pitch, roll = clamp(dHeading x gain) between the aim and 2x look-ahead."""
    p = chaikin(route, passes)
    seg = np.hypot(*np.diff(p, axis=0).T)
    s = np.r_[0, np.cumsum(seg)]
    at = lambda d: np.array([np.interp(d, s, p[:, 0]), np.interp(d, s, p[:, 1])])
    bearing = lambda a, b: math.atan2(b[0] - a[0], b[1] - a[1])
    n = int(secs * fps) + 1
    out = []
    for i in range(n):
        t = i / fps
        d = travel * t / secs
        c = at(d)
        h1 = bearing(c, at(d + look))
        h2 = bearing(c, at(d + 2 * look))
        dh = (h2 - h1 + math.pi) % (2 * math.pi) - math.pi
        out.append({"t": t, "x": float(c[0]), "y": float(c[1]), "heading": h1, "pitch": -(90 - pitch_nadir), "roll": float(np.clip(dh * gain, -roll_max, roll_max)),
                    "alt": alt[0] + (alt[1] - alt[0]) * t / secs})
    return out, p, float(s[-1])


def reserve_space(prompt, side="left"):
    return prompt.rstrip(". ") + ", subject on the %s third, generous empty space on the %s for text overlay, no text" % ("right" if side == "left" else "left", side)


def zone_clean(img, side="left", thr=6.0):
    a = img.astype(float).mean(-1)
    w = a.shape[1]
    z = a[:, :w // 3] if side == "left" else a[:, 2 * w // 3:]
    g = np.abs(np.diff(z, axis=1)).mean() + np.abs(np.diff(z, axis=0)).mean()
    return float(g) < thr, float(g)


def smooth_subject(samples, conf_min=.3, still=.08):
    """The card's smoothSubject: keep samples with confidence > 0.3, two-way exponential smoothing with weight 0.3 x conf,
    a still shot (travel < 0.08) takes the median; returns smoothed x (fraction of width)."""
    s = [(t, x, c) for t, x, c in samples if c > conf_min]
    if not s:
        return None
    xs = np.array([x for _, x, _ in s])
    if xs.max() - xs.min() < still:
        return [(t, float(np.median(xs))) for t, _, _ in s]
    f, b = [xs[0]], [xs[-1]]
    for i in range(1, len(s)):
        w = .3 * s[i][2]
        f.append(f[-1] + w * (xs[i] - f[-1]))
    for i in range(len(s) - 2, -1, -1):
        w = .3 * s[i][2]
        b.append(b[-1] + w * (xs[i] - b[-1]))
    b = b[::-1]
    return [(t, float((a + c) / 2)) for (t, _, _), a, c in zip(s, f, b)]


def subject_pan(cx, src_w, crop_w):
    return float(np.clip(cx * src_w - crop_w / 2, 0, src_w - crop_w))


def _oblique(yaw=20, pitch=10, f=300, W=320, H=200, cam=(0, 1.4, 6)):
    cy, sy = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    cp, sp = math.cos(math.radians(pitch)), math.sin(math.radians(pitch))

    def proj(p):
        x, y, z = p[0] - cam[0], p[1] - cam[1], p[2] - cam[2]
        x, z = cy * x - sy * z, sy * x + cy * z           # yaw
        y, z = cp * y + sp * z, -sp * y + cp * z          # pitch
        return (W / 2 + f * x / -z, H / 2 - f * y / -z)
    return proj
