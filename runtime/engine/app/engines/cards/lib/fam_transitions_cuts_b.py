"""Helpers of runners/fam_transitions_cuts_b.py used by data cards, copied verbatim (the extractor binds a card to them only when
their AST hash with every dependency equals the original's)."""
from __future__ import annotations

from pathlib import Path
from .core import check
from .core import fx
import json
import math
import subprocess


W, H, FPS = 128, 72, 30


def _np():
    import numpy as np
    return np


def grid():
    np = _np()
    yy, xx = np.mgrid[0:H, 0:W].astype(float)
    return xx, yy


def solid(rgb):
    np = _np()
    f = np.zeros((H, W, 3))
    f[:] = rgb
    return f


def scene_a():
    """Warm textured scene: red-orange gradient with an 8 px checker (gives edges to measure blur on)."""
    np = _np()
    xx, yy = grid()
    chk = (((xx // 8) + (yy // 8)) % 2) * 2 - 1
    f = np.stack([200 + 30 * chk, 70 + 60 * xx / W + 20 * chk, 40 + 10 * chk], -1)
    return np.clip(f, 0, 255)


def scene_b():
    """Cool textured scene: blue gradient with 6 px vertical and horizontal stripes."""
    np = _np()
    xx, yy = grid()
    st = ((xx // 6) % 2) * 2 - 1
    sh = ((yy // 6) % 2) * 2 - 1
    f = np.stack([30 + 15 * st, 90 + 50 * yy / H + 25 * sh, 210 + 25 * st], -1)
    return np.clip(f, 0, 255)


def scene_c():
    np = _np()
    xx, yy = grid()
    chk = (((xx // 5) + (yy // 5)) % 2) * 2 - 1
    return np.clip(np.stack([60 + 30 * chk, 190 + 30 * chk, 70 + 0 * chk], -1), 0, 255)


def blend(a, b, m):
    np = _np()
    m = np.asarray(m, dtype=float)
    if m.ndim == 2:
        m = m[..., None]
    return a * (1 - m) + b * m


def gblur_axis(img, sigma, axis):
    """Gaussian blur along one axis with standard deviation `sigma` px (edge-extended)."""
    np = _np()
    if sigma <= 0.05:
        return img.copy()
    rad = int(math.ceil(3 * sigma))
    xs = np.arange(-rad, rad + 1)
    k = np.exp(-xs ** 2 / (2 * sigma * sigma))
    k /= k.sum()
    pad = [(0, 0)] * img.ndim
    pad[axis] = (rad, rad)
    p = np.pad(img, pad, mode="edge")
    n = img.shape[axis]
    out = np.zeros_like(img, dtype=float)
    for j, w in enumerate(k):
        out += w * np.take(p, range(j, j + n), axis=axis)
    return out


def blur_x(img, px):
    """Horizontal blur; px is the CSS/SVG stdDeviation in frame pixels."""
    return gblur_axis(img, px, 1)


def blur_y(img, px):
    return gblur_axis(img, px, 0)


def sample(img, sx, sy, fill=(0, 0, 0)):
    """Nearest-neighbour sampling of img at float coords (sx, sy); outside -> fill."""
    np = _np()
    xi, yi = np.round(sx).astype(int), np.round(sy).astype(int)
    ok = (xi >= 0) & (xi < W) & (yi >= 0) & (yi < H)
    out = solid(fill)
    out[ok] = img[yi[ok], xi[ok]]
    return out, ok.astype(float)


def scale_about(img, s, cx=W / 2, cy=H / 2, fill=(0, 0, 0)):
    xx, yy = grid()
    out, _ = sample(img, cx + (xx - cx) / s, cy + (yy - cy) / s, fill)
    return out


def lin(t):
    return min(1.0, max(0.0, t))


def pow_inout(t, n=2):
    t = lin(t)
    return (2 ** (n - 1)) * t ** n if t < 0.5 else 1 - ((-2 * t + 2) ** n) / 2


def smooth(t):
    t = lin(t)
    return t * t * (3 - 2 * t)


def mad(a, b):
    np = _np()
    return float(np.mean(np.abs(np.asarray(a, float) - np.asarray(b, float))))


def near(f, ref, tol=28):
    """Per-pixel boolean: every channel within tol of ref (frame or colour)."""
    np = _np()
    ref = np.asarray(ref, float)
    return np.max(np.abs(f - ref), axis=-1) < tol


def frac(f, ref, tol=28, mask=None):
    np = _np()
    n = near(f, ref, tol)
    if mask is not None:
        n = n[mask.astype(bool)]
    return float(np.mean(n)) if n.size else 0.0


def luma(f):
    np = _np()
    return float(np.mean(f[..., 0] * 0.2126 + f[..., 1] * 0.7152 + f[..., 2] * 0.0722))


def cut_frames(F, thr=30.0):
    """Indices i where frame i differs strongly from frame i-1 (hard cuts)."""
    return [i for i in range(1, len(F)) if mad(F[i], F[i - 1]) > thr]


def write_video(path, frames, fps=FPS):
    """Lossless RGB H.264 so the measured pixels are the rendered pixels."""
    np = _np()
    data = b"".join(np.clip(np.round(f), 0, 255).astype(np.uint8).tobytes() for f in frames)
    done = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo",
                           "-pix_fmt", "rgb24", "-s", "%dx%d" % (W, H), "-r", str(fps), "-i", "-",
                           "-c:v", "libx264rgb", "-qp", "0", "-preset", "ultrafast", str(path)],
                          input=data, capture_output=True, timeout=60)
    if done.returncode:
        raise RuntimeError(done.stderr.decode(errors="replace")[-300:])
    return Path(path)


def save_json(wd, name, obj):
    p = Path(wd) / name
    p.write_text(json.dumps(obj, indent=1, ensure_ascii=False), encoding="utf-8")
    return p


def _wav_env(x, rate, win=0.005):
    np = _np()
    n = int(rate * win)
    k = len(x) // n
    return np.sqrt(np.mean(x[:k * n].reshape(k, n) ** 2, axis=1)), n / rate


def _mux(wd, video, wav, name):
    out = Path(wd) / name
    # exact length: every video frame, the WAV padded/trimmed to the video (no -shortest)
    fx.ffmpeg("-i", video, "-i", wav, "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", *fx.fit_audio(fx.video_seconds(video)),
              "-c:a", "pcm_s16le", out)
    return out


def mix_weight(f, A, B, thr=60.0):
    """Per-pixel mix weight w with f = A + w (B - A), on pixels where A and B differ enough."""
    np = _np()
    d = B - A
    nn = np.sum(d * d, -1)
    ok = nn > thr * thr
    w = np.sum((f - A) * d, -1) / np.maximum(nn, 1)
    return np.clip(w, 0, 1), ok


XF_D, XF_OFF, XF_LEN = 0.6, 0.4, 30


def noise_scene(seed, base):
    np = _np()
    rng = np.random.default_rng(seed)
    return np.clip(np.asarray(base, float) + rng.integers(-60, 61, (H, W, 3)), 0, 255).astype(float)


def _xf_clips(wd, audio=True, noise=False):
    """Lossless 1 s fixture clips A (warm, 440 Hz) and B (cool, 660 Hz); `noise` uses per-pixel noise textures."""
    A, B = (noise_scene(1, (200, 90, 50)), noise_scene(2, (40, 100, 210))) if noise else (scene_a(), scene_b())
    wd = Path(wd)
    pa, pb = write_video(wd / "xa.mkv", [A] * XF_LEN), write_video(wd / "xb.mkv", [B] * XF_LEN)
    if audio:
        ta, tb = fx.tone(wd / "xa.wav", 440, 1.0), fx.tone(wd / "xb.wav", 660, 1.0)
        pa, pb = _mux(wd, pa, ta, "xa_av.mkv"), _mux(wd, pb, tb, "xb_av.mkv")
    return pa, pb, A, B


def _xfade(wd, pa, pb, name, dur=XF_D, off=XF_OFF, audio=True):
    out = Path(wd) / ("xf_%s.mkv" % name)
    fc = "[0:v][1:v]xfade=transition=%s:duration=%s:offset=%s[v]" % (name, dur, off)
    args = ["-i", pa, "-i", pb]
    if audio:
        fc += ";[0:a][1:a]acrossfade=d=%s[a]" % dur
        fx.ffmpeg(*args, "-filter_complex", fc, "-map", "[v]", "-map", "[a]", "-c:v", "libx264rgb", "-qp", "0",
                  "-c:a", "pcm_s16le", out)
    else:
        fx.ffmpeg(*args, "-filter_complex", fc, "-map", "[v]", "-c:v", "libx264rgb", "-qp", "0", out)
    return out, fx.frames(out, size=(W, H))


def _cls(f, A, B):
    np = _np()
    dA, dB = np.abs(f - A).sum(-1), np.abs(f - B).sum(-1)
    return dB < dA, np.minimum(dA, dB) < 20


def _cent(m):
    np = _np()
    ys, xs = np.nonzero(m)
    return (float(xs.mean() / W), float(ys.mean() / H)) if len(xs) else (None, None)


def _push_fit(f, A, B, axis, sign, mode="push"):
    """Best offset o for a slide/cover/reveal frame: push moves both, cover moves B over static A, reveal moves A
    off a static B. sign -1 = toward left/up. Returns (mean abs error, o)."""
    np = _np()
    if axis == 0:
        f, A, B = f.transpose(1, 0, 2), A.transpose(1, 0, 2), B.transpose(1, 0, 2)
    if sign > 0:
        f, A, B = f[:, ::-1], A[:, ::-1], B[:, ::-1]
    L = f.shape[1]
    tot = f.size
    best = (1e9, 0)
    for o in range(0, L + 1):
        a_src = A[:, o:] if mode in ("push", "reveal") else A[:, :L - o]
        b_src = B[:, :o] if mode in ("push", "cover") else B[:, L - o:]
        e = (float(np.abs(f[:, :L - o] - a_src).sum()) + float(np.abs(f[:, L - o:] - b_src).sum())) / tot
        if e < best[0]:
            best = (e, o)
    return best


SIDE = {"left": (0.6, None), "right": (-0.4, None), "up": (None, 0.6), "down": (None, -0.4)}


def _side_ok(c, d):
    """B centroid on the side the motion comes from: 'left' -> B on the right (x > 0.6) etc."""
    if c[0] is None:
        return False
    tx, ty = SIDE[d]
    ok = True
    if tx is not None:
        ok &= c[0] > tx if tx > 0 else c[0] < -tx
    if ty is not None:
        ok &= c[1] > ty if ty > 0 else c[1] < -ty
    return ok


def _xf_prop(name, F, A, B, ref=None):
    """Known-answer property of one named xfade, measured on its frames. Returns (ok, measured, expected)."""
    np = _np()
    f18, f21, f24 = F[18], F[21], F[24]
    isB, pure = _cls(f18, A, B)
    c = _cent(isB)
    for d in ("left", "right", "up", "down"):
        if name in ("wipe" + d, "smooth" + d, "slide" + d, "cover" + d, "reveal" + d) or \
                name in ({"left": "hlslice", "right": "hrslice", "up": "vuslice", "down": "vdslice"}[d],
                         {"left": "hlwind", "right": "hrwind", "up": "vuwind", "down": "vdwind"}[d]):
            side = _side_ok(c, d)
            axis = 1 if d in ("left", "right") else 0
            sign = -1 if d in ("left", "up") else 1
            if name.startswith("wipe"):
                return side and pure.mean() > 0.98, [c, float(pure.mean())], "B on the far side, hard edge"
            if name.startswith("smooth"):
                return side and pure.mean() < 0.7, [c, float(pure.mean())], "B on the far side, soft edge"
            if name.startswith(("slide", "cover", "reveal")):
                mode = "push" if name.startswith("slide") else name[:5] if name.startswith("cover") else "reveal"
                e, o = _push_fit(f18, A, B, axis, sign, mode)
                L = W if axis == 1 else H
                return side and e < 4 and abs(o - L / 3) <= 3, [c, round(e, 2), o], "%s fit at o = L/3" % mode
            # slices / wind: banded or ragged boundary per line
            bounds = []
            lines = range(H) if axis == 1 else range(W)
            for k in lines:
                v = isB[k, :] if axis == 1 else isB[:, k]
                bounds.append(int(v.sum()))
            spread = float(np.std(bounds))
            if "slice" in name:
                line = isB[H // 2, :] if axis == 1 else isB[:, W // 2]
                runs = int(np.sum(line[1:] != line[:-1]))
                return side and pure.mean() > 0.98 and runs >= 4, [c, runs], "sliced edge (>= 4 B/A runs along the motion)"
            return side and spread > 2, [c, spread], "ragged wind edge"
    if name in ("fade", "fadefast", "fadeslow"):
        w, ok = mix_weight(f21, A, B)
        med, sd = float(np.median(w[ok])), float(np.std(w[ok]))
        if name == "fade":
            return 0.3 < med < 0.7 and sd < 0.05, [med, sd], "uniform mix ~0.5"
        rw, rok = mix_weight(ref[0][21], A, B)
        rm = float(np.median(rw[rok]))
        ow, ook = mix_weight(ref[2 if name == "fadefast" else 1][21], A, B)
        om = float(np.median(ow[ook]))
        if name == "fadefast":
            return med > rm + 0.05 and med > om and sd < 0.05, [med, rm, om], "non-linear curve, fast > slow > linear"
        return abs(med - rm) > 0.03 and med < om and sd < 0.05, [med, rm, om], "non-linear curve, below fadefast"
    if name == "dissolve":
        diff = float(np.mean(isB[:, 1:] != isB[:, :-1]))
        return pure.mean() > 0.95 and 0.15 < isB.mean() < 0.6 and diff > 0.2, [float(pure.mean()), float(isB.mean()), diff], "grainy per-pixel"
    if name == "fadeblack":
        return luma(f18) < 0.3 * min(luma(A), luma(B)), luma(f18), "dark"
    if name == "fadewhite":
        return luma(f18) > 200, luma(f18), ">200"
    if name == "fadegrays":
        sat = float(np.mean(np.max(F[16], -1) - np.min(F[16], -1)))
        sa = float(np.mean(np.max(A, -1) - np.min(A, -1)))
        return sat < 0.6 * sa, [sat, sa], "desaturated"
    if name in ("circleopen", "vertopen", "horzopen"):
        b, _ = _cls(f21, A, B)
        inner, outer = float(b[18:54, 32:96].mean()), float((b.sum() - b[18:54, 32:96].sum()) / (W * H - 36 * 64))
        return inner > 0.9 and outer < 0.5, [inner, outer], "B opens from the centre"
    if name in ("circleclose", "vertclose", "horzclose"):
        b, _ = _cls(f21, A, B)
        inner, outer = float(b[18:54, 32:96].mean()), float((b.sum() - b[18:54, 32:96].sum()) / (W * H - 36 * 64))
        return inner < 0.1 and outer > 0.5, [inner, outer], "B closes in from the edges"
    if name in ("circlecrop", "rectcrop"):
        b, _ = _cls(F[27], A, B)
        inner, outer = float(b[18:54, 32:96].mean()), float((b.sum() - b[18:54, 32:96].sum()) / (W * H - 36 * 64))
        return luma(f21) < 5 and inner > outer, [luma(f21), inner, outer], "crops to black then opens B from the centre"
    if name == "radial":
        ws = [float(_cls(F[i], A, B)[0].mean()) for i in (15, 18, 21, 24, 27)]
        xx, yy = grid()
        ang = np.degrees(np.arctan2(yy - H / 2, xx - W / 2))[isB]
        span = float(np.ptp(ang)) if ang.size else 0
        return all(b_ >= a_ - 0.01 for a_, b_ in zip(ws, ws[1:])) and 0 < ws[1] < 0.5 and span < 200, [ws, span], "angular sweep"
    if name.startswith("diag"):
        corner = {"diagtl": (1, 1), "diagtr": (0, 1), "diagbl": (1, 0), "diagbr": (0, 0)}[name]
        b, _ = _cls(F[21], A, B)
        cc = _cent(b)
        ok = cc[0] is not None and ((cc[0] > 0.5) == bool(corner[0])) and ((cc[1] > 0.5) == bool(corner[1]))
        return ok, cc, "B from the opposite corner"
    if name.startswith("wipe") and len(name) == 6:
        corner = {"wipetl": (1, 1), "wipetr": (0, 1), "wipebl": (1, 0), "wipebr": (0, 0)}[name]
        ok = c[0] is not None and ((c[0] > 0.5) == bool(corner[0])) and ((c[1] > 0.5) == bool(corner[1])) and pure.mean() > 0.98
        return ok, c, "corner wipe"
    if name in ("squeezeh", "squeezev"):
        b, _ = _cls(f18, A, B)
        if name == "squeezeh":   # A squeezed toward the horizontal centre line: B shows above and below
            band = b[24:48].mean()
            edge = (b[:10].mean() + b[-10:].mean()) / 2
        else:                    # A squeezed toward the vertical centre line: B shows left and right
            band = b[:, 40:88].mean()
            edge = (b[:, :16].mean() + b[:, -16:].mean()) / 2
        return band < 0.05 and edge > 0.9 and mad(f18, A) > 5, [float(band), float(edge)], "A squeezed into the middle"
    if name == "zoomin":
        best = min((mad(F[18], scale_about(A, s_, fill=(0, 0, 0))), s_) for s_ in (1.0, 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.8, 2.0))
        return best[1] > 1.05 and best[0] < mad(F[18], A), best, "A zoomed in"
    if name == "pixelize":
        eqs = [float(np.mean(np.all(np.abs(F[i][:, 1:] - F[i][:, :-1]) < 0.5, -1))) for i in (18, 21, 24)]
        ea = float(np.mean(np.all(np.abs(A[:, 1:] - A[:, :-1]) < 0.5, -1)))
        return min(eqs) > 0.5 and ea < 0.05, [eqs, ea], "noise texture shown in blocks (equal neighbours)"
    if name == "hblur":
        f = F[19]
        bx = min((mad(f, blur_x(blend(A, B, w_ / 20), s_)), s_, w_ / 20) for s_ in (1, 2, 4, 6, 8, 12, 16) for w_ in range(0, 21))
        by = min((mad(f, blur_y(blend(A, B, w_ / 20), s_)), s_, w_ / 20) for s_ in (1, 2, 4, 6, 8, 12, 16) for w_ in range(0, 21))
        return bx[1] >= 2 and bx[0] < 0.6 * by[0], [round(bx[0], 2), bx[1], round(by[0], 2)], "horizontal blur explains the frame"
    if name == "distance":
        ws = [float(_cls(F[i], A, B)[0].mean()) for i in range(11, 17)]
        lin_f = blend(A, B, 1.0 / 18)
        return any(0.2 < w_ < 0.9 for w_ in ws) and all(b_ >= a_ - 0.01 for a_, b_ in zip(ws, ws[1:])) and \
            mad(F[13], lin_f) > 10, ws, "per-pixel distance switch"
    raise KeyError(name)


def _xf_family(wd, names, label):
    np = _np()
    pa, pb, A, B = _xf_clips(wd, noise=names == ["pixelize"])
    outs, checks = [], []
    ref = None
    if any(n_ in ("fadefast", "fadeslow") for n_ in names):
        ref = [_xfade(wd, pa, pb, n_, audio=False)[1] for n_ in ("fade", "fadefast", "fadeslow")]
    for nm in names:
        out, F = _xfade(wd, pa, pb, nm)
        outs.append(out)
        ok, meas, exp = _xf_prop(nm, F, A, B, ref)
        checks.append(check("%s: %s" % (nm, exp), ok, meas, exp))
        checks.append(check("%s: 1 s + 1 s - 0.6 s = 42 frames, A before, B after" % nm,
                            len(F) == 42 and mad(F[11], A) < 1 and mad(F[-1], B) < 1, len(F), 42))
    # matching audio cross-fade on the last one: both tones in the middle, only B at the end
    x, rate = fx.read_wav(_extract_wav(wd, outs[-1]))
    mid = x[int(0.6 * rate):int(0.8 * rate), 0]
    end = x[-int(0.15 * rate):, 0]

    def amp(sig, fq):
        spec = np.abs(np.fft.rfft(sig * np.hanning(len(sig))))
        fr = np.fft.rfftfreq(len(sig), 1 / rate)
        return float(spec[np.argmin(np.abs(fr - fq))])
    both = amp(mid, 440) > 0.2 * amp(mid, 660) and amp(mid, 660) > 0.2 * amp(mid, 440)
    only_b = amp(end, 440) < 0.05 * amp(end, 660)
    checks.append(check("%s: matching audio cross-fade (both tones mid, B tone at the end)" % label, both and only_b,
                        [round(amp(mid, 440)), round(amp(mid, 660)), round(amp(end, 440))], "mix then B"))
    concat = [A] * XF_LEN + [B] * XF_LEN
    neg = [_xf_prop(nm, concat, A, B, [concat] * 3)[0] for nm in names]
    checks.append(check("negative control: a plain concat fails every %s property" % label, not any(neg), neg, "all False"))
    return checks, outs


def _extract_wav(wd, video):
    out = Path(wd) / (Path(video).stem + ".wav")
    fx.ffmpeg("-i", video, "-vn", "-c:a", "pcm_s16le", out)
    return out


def _xfade_names():
    import re
    out = fx.run(["ffmpeg", "-hide_banner", "-h", "filter=xfade"]).stdout
    return [m_.group(1) for m_ in re.finditer(r"^\s{5}(\w+)\s+(-?\d+)\s", out, re.M) if m_.group(1) != "custom"]


def fit_mix(f, a, b):
    """Scalar w with f ~ a + w (b - a) (least squares over the frame)."""
    np = _np()
    d = b - a
    return float(np.sum((f - a) * d) / max(np.sum(d * d), 1e-9))


def counter_frames(n):
    """Frames whose grey level encodes the frame index (index * 4), so any cut can be read back exactly."""
    return [solid((i * 4 % 256,) * 3) for i in range(n)]


def read_index(f):
    return int(round(float(f.mean()) / 4))


def h264(path, frames, fps, gop):
    np = _np()
    data = b"".join(np.clip(f, 0, 255).astype(np.uint8).tobytes() for f in frames)
    done = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
                           "-s", "%dx%d" % (W, H), "-r", str(fps), "-i", "-", "-c:v", "libx264", "-qp", "0",
                           "-pix_fmt", "yuv444p", "-g", str(gop), "-keyint_min", str(gop), "-sc_threshold", "0",
                           "-bf", "2", str(path)], input=data, capture_output=True, timeout=60)
    if done.returncode:
        raise RuntimeError(done.stderr.decode()[-300:])
    return Path(path)


def keyframes(path):
    out = fx.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_packets", "-show_entries",
                  "packet=pts_time,flags", "-of", "json", str(path)]).stdout
    return sorted(float(p["pts_time"]) for p in json.loads(out)["packets"] if "K" in p.get("flags", ""))


def _colour_seg(path, col, sec, fps=30, size=None):
    s_ = size or "%dx%d" % (W, H)
    fx.ffmpeg("-f", "lavfi", "-i", "color=c=%s:s=%s:r=%d:d=%s" % (col, s_, fps, sec), "-f", "lavfi", "-i",
              "sine=f=440:d=%s" % sec, "-c:v", "libx264", "-qp", "0", "-pix_fmt", "yuv444p", "-frames:v", round(sec * fps),
              *fx.fit_audio(round(sec * fps) / fps), "-c:a", "aac", path)
    return Path(path)


def _tone_arr(freq, sec, rate=22050, amp=0.4):
    np = _np()
    t = np.arange(int(sec * rate)) / rate
    return amp * np.sin(2 * np.pi * freq * t)


def _band_env(x, rate, freq, win=0.05):
    """Amplitude of `freq` in consecutive windows."""
    np = _np()
    n = int(win * rate)
    out = []
    for k in range(len(x) // n):
        seg = x[k * n:(k + 1) * n]
        t = np.arange(n) / rate
        out.append(2 * abs(np.sum(seg * np.exp(-2j * np.pi * freq * t))) / n)
    return out


def _jl_edit(wd, name, lead, tail, rate=22050):
    """Video cut at 1.0 s between A and B; B's audio leads by `lead` s (J) and A's audio trails by `tail` s (L)."""
    np = _np()
    A, B = scene_a(), scene_b()
    vid = write_video(Path(wd) / (name + "_v.mkv"), [A] * 30 + [B] * 30)
    a = np.zeros(int(2 * rate))
    a[:int((1.0 + tail) * rate)] += _tone_arr(440, 1.0 + tail, rate)
    st = int((1.0 - lead) * rate)
    b = _tone_arr(660, 2.0 - (1.0 - lead), rate)
    a[st:st + len(b)] += b
    wav = fx.write_wav(Path(wd) / (name + ".wav"), a * 0.9, rate)
    out = _mux(wd, vid, wav, name + ".mkv")
    x, r = fx.read_wav(_extract_wav(wd, out))
    eb, ea = _band_env(x[:, 0], r, 660), _band_env(x[:, 0], r, 440)
    on_b = next(i for i, v in enumerate(eb) if v > 0.1) * 0.05
    off_a = next(i for i, v in enumerate(ea) if i > 2 and v < 0.1) * 0.05
    cut = cut_frames(fx.frames(out, size=(W, H)), 30)
    return out, on_b, off_a, cut


def song_switch_plan(a, b):
    """Switch at a phrase end: crossfade when keys match (or are a fifth apart) and BPM within 6 %, else tail ->
    silence -> new song."""
    fifth = {("C", "G"), ("G", "C"), ("D", "A"), ("A", "D")}
    ok_key = a["key"] == b["key"] or (a["key"], b["key"]) in fifth
    ok_bpm = abs(a["bpm"] - b["bpm"]) / a["bpm"] <= 0.06
    return {"mode": "crossfade", "dur": 1.0} if ok_key and ok_bpm else {"mode": "gap", "tail": 0.5, "silence": 0.4}


def _speech_track(wd, name, pattern, rate=16000):
    """Bursts of 300 Hz 'speech' and silences; pattern = [(speech_s, pause_s), ...]."""
    np = _np()
    parts = []
    for sp, pa in pattern:
        parts.append(_tone_arr(300, sp, rate, 0.5))
        parts.append(np.zeros(int(pa * rate)))
    return fx.write_wav(Path(wd) / (name + ".wav"), np.concatenate(parts), rate)


def silences(path, noise="-30dB", d=0.5):
    import re
    out = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-af", "silencedetect=noise=%s:d=%s" % (noise, d),
                          "-f", "null", "-"], capture_output=True, text=True, timeout=60).stderr
    st = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", out)]
    en = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", out)]
    return list(zip(st, en))


def trim_plan(sil, total, genre):
    """Pause trimming by genre: ambient keeps pauses < 15 s and cuts < 20 %; action trims pauses >= 0.5 s down to
    0.15 s and may cut up to 40 %; speech cuts only at semantic boundaries (here: pauses >= 0.8 s)."""
    keep_min = {"ambient": 15.0, "action": 0.5, "speech": 0.8}[genre]
    cap = {"ambient": 0.2, "action": 0.4, "speech": 0.3}[genre]
    cuts = []
    for s_, e in sil:
        if e - s_ >= keep_min:
            cuts.append((s_ + 0.15, e))
    removed = sum(e - s_ for s_, e in cuts)
    while cuts and removed / total > cap:
        cuts.pop()
        removed = sum(e - s_ for s_, e in cuts)
    return cuts, removed / total


def apply_cuts(src, cuts, total, out):
    keep, t = [], 0.0
    for s_, e in cuts:
        keep.append((t, s_))
        t = e
    keep.append((t, total))
    parts = ";".join("[0:a]atrim=start=%.5f:end=%.5f,asetpts=N/SR/TB[k%d]" % (a, b, i) for i, (a, b) in enumerate(keep))
    fx.ffmpeg("-i", src, "-filter_complex", parts + ";" + "".join("[k%d]" % i for i in range(len(keep))) +
              "concat=n=%d:v=0:a=1[o]" % len(keep), "-map", "[o]", out)
    return keep


def time_map(keep, t):
    acc = 0.0
    for a, b in keep:
        if a <= t <= b:
            return acc + (t - a)
        acc += b - a
    return None


def classify_genre(sil, total, motion):
    """Classify from silence share and frame-diff motion: lots of silence + low motion -> ambient; high motion ->
    action; otherwise speech."""
    share = sum(e - s_ for s_, e in sil) / total
    if motion > 20:
        return "action"
    if share > 0.4 and motion < 5:
        return "ambient"
    return "speech"


def pure_runs(F, scenes):
    """Runs of frames that are exactly one of the scenes: [(scene, first, last)]."""
    runs = []
    for i, f in enumerate(F):
        k = min(range(len(scenes)), key=lambda j: mad(f, scenes[j]))
        if mad(f, scenes[k]) >= 1.0:
            continue
        if runs and runs[-1][0] == k and runs[-1][2] == i - 1:
            runs[-1] = (k, runs[-1][1], i)
        else:
            runs.append((k, i, i))
    return runs


def classify_boundary(F, e, s_):
    """Classify the boundary between the last pure frame e of a shot and the first pure frame s_ of the next."""
    np = _np()
    if s_ - e == 1:
        return "cut"
    a, b = F[e], F[s_]
    mids = F[e + 1:s_]
    lums = [luma(f) for f in mids]
    if min(lums) < 0.4 * min(luma(a), luma(b)):
        return "fadeblack"
    if max(lums) > 200 and max(lums) > 1.3 * max(luma(a), luma(b)):
        return "fadewhite"
    m = mids[len(mids) // 2]
    slide_err = min(_push_fit(m, a, b, ax, sg, "push")[0] for ax in (0, 1) for sg in (-1, 1))
    return "slide" if slide_err < 4 else "dissolve"


def _overlap_arith(wd, durs, d, name):
    """Overlapping transitions shorten the total (sum - (n-1) d); overlays on the cut do not."""
    np = _np()
    wd = Path(wd)
    clips = [write_video(wd / ("%s%d.mkv" % (name, k)), [[scene_a(), scene_b(), scene_c()][k % 3]] * n_) for k, n_ in enumerate(durs)]
    fc, prev, t = [], "[0:v]", durs[0]
    for k in range(1, len(clips)):
        fc.append("%s[%d:v]xfade=transition=fade:duration=%.4f:offset=%.4f[v%d]" % (prev, k, d / 30, (t - d) / 30, k))
        t += durs[k] - d
        prev = "[v%d]" % k
    args = []
    for c_ in clips:
        args += ["-i", c_]
    tr = wd / (name + "_transition.mkv")
    fx.ffmpeg(*args, "-filter_complex", ";".join(fc), "-map", prev, "-c:v", "libx264rgb", "-qp", "0", tr)
    cat = "".join("[%d:v]" % k for k in range(len(clips))) + "concat=n=%d:v=1[c];[c]drawbox=x=0:y=0:w=iw:h=ih:color=white@0.5:t=fill:enable='between(n,%d,%d)'[o]" % (len(clips), durs[0] - d // 2, durs[0] + d // 2)
    ov = wd / (name + "_overlay.mkv")
    fx.ffmpeg(*args, "-filter_complex", cat, "-map", "[o]", "-c:v", "libx264rgb", "-qp", "0", ov)
    nt = len(fx.frames(tr, size=(W, H)))
    no = len(fx.frames(ov, size=(W, H)))
    return nt, no, [tr, ov]


def _loop(wd, name, seconds, xf, repeat_to=None):
    """Loop a clip by dissolving its tail into its head: out = xfade(clip[x:], clip[:x])... implemented as
    xfade of the clip with itself offset so the last frame flows into the first."""
    np = _np()
    wd = Path(wd)
    n = int(seconds * FPS)
    frames = [np.roll(scene_a(), int(i * 2), axis=1) * (0.7 + 0.3 * i / n) for i in range(n)]
    src = write_video(wd / (name + "_src.mkv"), frames)
    nx = int(round(xf * FPS))
    out = wd / (name + ".mkv")
    # body = frames[nx : n-nx], tail = frames[n-nx:], head = frames[:nx]; loop = body + xfade(tail, head)
    fx.ffmpeg("-i", src, "-filter_complex",
              "[0:v]split=3[a][b][c];[a]trim=start_frame=%d:end_frame=%d,setpts=PTS-STARTPTS[body];"
              "[b]trim=start_frame=%d,setpts=PTS-STARTPTS[tail];[c]trim=end_frame=%d,setpts=PTS-STARTPTS[head];"
              "[tail][head]xfade=transition=fade:duration=%.4f:offset=0[seam];[body][seam]concat=n=2:v=1[v]"
              % (nx, n - nx, n - nx, nx, xf - 1e-3), "-map", "[v]", "-c:v", "libx264rgb", "-qp", "0", out)
    F = fx.frames(out, size=(W, H))
    res = [out]
    if repeat_to:
        rep = wd / (name + "_long.mkv")
        fx.ffmpeg("-stream_loop", "-1", "-i", out, "-t", str(repeat_to), "-c", "copy", rep)
        res.append(rep)
    return F, frames, res


def _loop_checks(F, frames, xf):
    seam = mad(F[-1], F[0])
    orig = mad(frames[-1], frames[0])
    step = max(mad(a, b) for a, b in zip(F, F[1:]))
    return [check("loop seam (last -> first) is as small as a normal frame step", seam <= step + 0.5, [seam, step], "<= step"),
            check("length = clip - xfade", abs(len(F) - (len(frames) - round(xf * FPS))) <= 1, len(F), len(frames) - round(xf * FPS)),
            check("negative control: the raw clip jumps at its seam", orig > 3 * step, [orig, step], "> 3 x step")]


def shot_scenes():
    return [scene_a(), scene_b(), scene_c(), 255 - scene_a(), 255 - scene_b(), 255 - scene_c()]


X12_RULES = {
    "shrink_after_flythrough": lambda s_: s_.get("b_start_scale", 1) > 1 and s_.get("after_flythrough"),
    "whip_too_sharp": lambda s_: s_.get("whip_s", 1) < 0.2 and s_.get("whip_blur", 0) > 30,
    "ca_too_strong": lambda s_: s_.get("ca_coeff", 0) > 0.005,
    "fixed_subframes": lambda s_: s_.get("subframes") == 4 and not s_.get("adaptive"),
    "grain_on_ui": lambda s_: s_.get("ui") and s_.get("animated_grain"),
    "opacity_only": lambda s_: s_.get("appear") == "opacity",
    "fake_3d_tilt": lambda s_: s_.get("ui") and s_.get("tilt3d"),
}


def lint_x12(spec):
    return sorted(k for k, f in X12_RULES.items() if f(spec))


def empty_frames_whip(dist, dur, fps=FPS):
    """Frames of a whip where the subject is entirely off-screen."""
    n = int(round(dur * fps))
    obj_w = 30
    empty = 0
    for i in range(n + 1):
        x = W / 2 + dist * pow_inout(i / n, 2) * (W / 1920)
        if x - obj_w / 2 > W or x + obj_w / 2 < 0:
            empty += 1
    return empty


def rect(f, cx, cy, w, h, col, r=0.0, op=1.0):
    """Draw an anti-alias-free (rounded) rectangle centred at (cx, cy) in place, with opacity."""
    np = _np()
    xx, yy = grid()
    dx = np.maximum(np.abs(xx + 0.5 - cx) - (w / 2 - r), 0)
    dy = np.maximum(np.abs(yy + 0.5 - cy) - (h / 2 - r), 0)
    m = (np.hypot(dx, dy) <= r) & (np.abs(xx + 0.5 - cx) <= w / 2) & (np.abs(yy + 0.5 - cy) <= h / 2)
    f[m] = f[m] * (1 - op) + np.asarray(col, float) * op
    return f


def bbox(f, col, tol=12):
    np = _np()
    m = near(f, col, tol)
    if not m.any():
        return None
    ys, xs = np.nonzero(m)
    return (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1)


def _np_displace(src, dx, dy):
    np = _np()
    xx, yy = grid()
    sx = np.clip(xx + dx, 0, W - 1)
    sy = np.clip(yy + dy, 0, H - 1)
    return src[sy.astype(int), sx.astype(int)]
