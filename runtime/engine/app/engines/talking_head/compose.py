"""Frame compositor: numpy draws every frame of the reel from the resolved plan (presenter, inserts, transitions, look)."""
import math, subprocess
from pathlib import Path
import json

import numpy as np

from ..media import exe
from .project import info
from .text import bez, ramp

STYLE = json.loads((Path(__file__).with_name("data") / "style.json").read_text(encoding="utf-8"))
TD = STYLE["transitions"]["whip"]
SHUTTER = STYLE["shutter"]
DIVIDER = np.array([0.06, 0.05, 0.06], np.float32)
WHITE = np.ones(3, np.float32)


def hexrgb(h):
    return np.array([int(h[i:i + 2], 16) for i in (1, 3, 5)], np.float32) / 255.0


# ------------------------------------------------------------------------------------------------ media
class Reader:
    """Sequential frame reader with re-seek; float32 frames (H, W[, 3]) in 0..1."""

    def __init__(self, path, fps, w, h, crop=None, gray=False):
        self.path, self.fps, self.gray, self.crop = path, fps, gray, crop
        self.w, self.h = (crop[0], crop[1]) if crop else (w, h)
        self.p, self.k, self.cur = None, -10, None

    def _open(self, k):
        self.close()
        vf = ["-vf", "crop=%d:%d:%d:%d" % tuple(self.crop)] if self.crop else []
        self.p = subprocess.Popen([exe("ffmpeg"), "-v", "error", "-ss", "%.4f" % (k / self.fps), "-i", self.path, "-an", *vf,
                                   "-f", "rawvideo", "-pix_fmt", "gray" if self.gray else "rgb24", "-"],
                                  stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)
        self.k = k - 1

    def frame(self, t):
        k = max(0, int(round(t * self.fps + 1e-6)))
        if self.p is None or k < self.k or k - self.k > 50:
            self._open(k)
        shape = (self.h, self.w) + (() if self.gray else (3,))
        nb = int(np.prod(shape))
        while self.k < k:
            buf = self.p.stdout.read(nb)
            if len(buf) < nb:
                break                                   # past the end: keep the last frame
            self.cur = np.frombuffer(buf, np.uint8).reshape(shape)
            self.k += 1
        if self.cur is None:
            return np.zeros(shape, np.float32)
        self.k = k
        return self.cur.astype(np.float32) / 255.0

    def close(self):
        if self.p:
            self.p.kill()


def src_time(spec, tau, cdur):
    """Source time of a clip at local time tau; a clip too short for its slot is slowed down (up to 4x)."""
    sp = float(spec.get("speed") or 1.0)
    t_in = spec.get("t_in") or 0
    avail, need = (spec.get("srcdur") or 99) - t_in - 0.04, cdur * sp
    st = min(400.0, need / avail * 100) if avail < need else 100.0
    return t_in + tau * sp * 100.0 / st


def load_rgba(path, max_side=None):
    m = info(path)
    w, h, vf = m["w"], m["h"], []
    if max_side and max(w, h) > max_side:
        f = max_side / float(max(w, h))
        w, h = max(2, int(w * f)), max(2, int(h * f))
        vf = ["-vf", "scale=%d:%d:flags=area" % (w, h)]
    out = subprocess.run([exe("ffmpeg"), "-v", "error", "-i", path, *vf, "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgba", "-"],
                         capture_output=True, stdin=subprocess.DEVNULL).stdout
    return np.frombuffer(out, np.uint8).reshape(h, w, 4).astype(np.float32) / 255.0


# ------------------------------------------------------------------------------------------------ pixels
def sample(img, ow, oh, ax, ay, sx, sy, px, py):
    """Bilinear: img pixel (ax, ay) lands at (px, py), scaled (sx, sy). Returns (x0, y0, patch) or None."""
    h, w = img.shape[:2]
    X0, X1, Y0, Y1 = px - ax * sx, px + (w - ax) * sx, py - ay * sy, py + (h - ay) * sy
    x0, x1 = max(0, int(math.floor(min(X0, X1)))), min(ow, int(math.ceil(max(X0, X1))))
    y0, y1 = max(0, int(math.floor(min(Y0, Y1)))), min(oh, int(math.ceil(max(Y0, Y1))))
    if x1 <= x0 or y1 <= y0:
        return None
    if sx < 0.6 or sy < 0.6:                            # strong downscale: pre-shrink against aliasing
        f = max(1, int(1.0 / max(sx, sy, 0.05)))
        if f > 1:
            hh, ww = (h // f) * f, (w // f) * f
            small = img[:hh, :ww].reshape(hh // f, f, ww // f, f, *img.shape[2:]).mean(axis=(1, 3))
            return sample(small, ow, oh, ax / f, ay / f, sx * f, sy * f, px, py)
    xs = ax + (np.arange(x0, x1, dtype=np.float32) + 0.5 - px) / sx - 0.5
    ys = ay + (np.arange(y0, y1, dtype=np.float32) + 0.5 - py) / sy - 0.5
    xi, yi = np.floor(xs).astype(np.int32), np.floor(ys).astype(np.int32)
    fx, fy = xs - xi, ys - yi
    xa, xb = np.clip(xi, 0, w - 1), np.clip(xi + 1, 0, w - 1)
    ya, yb = np.clip(yi, 0, h - 1), np.clip(yi + 1, 0, h - 1)
    r0, r1 = img[ya], img[yb]
    fx3, fy3 = (fx[None, :, None], fy[:, None, None]) if img.ndim == 3 else (fx[None, :], fy[:, None])
    top = r0[:, xa] * (1 - fx3) + r0[:, xb] * fx3
    bot = r1[:, xa] * (1 - fx3) + r1[:, xb] * fx3
    return x0, y0, top * (1 - fy3) + bot * fy3


def paste(canvas, img, ax, ay, s, px, py):
    """Sample img onto an empty canvas (no blending)."""
    r = sample(img, canvas.shape[1], canvas.shape[0], ax, ay, s, s, px, py)
    if r:
        x0, y0, patch = r
        canvas[y0:y0 + patch.shape[0], x0:x0 + patch.shape[1]] = patch
    return canvas


def over(canvas, patch, x0, y0, opacity=1.0):
    h, w = patch.shape[:2]
    reg = canvas[y0:y0 + h, x0:x0 + w]
    a = patch[:, :, 3:4] * opacity if patch.shape[2] == 4 else np.ones((h, w, 1), np.float32) * opacity
    reg *= (1 - a)
    reg += patch[:, :, :3] * a


def hblur(a, n):
    n = max(1, min(n, a.shape[1] - 1))
    c = np.cumsum(np.pad(a, ((0, 0), (n // 2 + 1, n - n // 2), (0, 0)), mode="edge"), axis=1)
    return (c[:, n:n + a.shape[1]] - c[:, :a.shape[1]]) / n


def put(canvas, img, ax, ay, s, px, py, opacity=1.0, mblur=0.0):
    r = sample(img, canvas.shape[1], canvas.shape[0], ax, ay, s, s, px, py)
    if r:
        x0, y0, patch = r
        over(canvas, hblur(patch, int(mblur)) if mblur > 1.5 else patch, x0, y0, opacity)


def opaque(img):
    return np.dstack([img, np.ones(img.shape[:2], np.float32)])


def blur(a, r):
    """Separable box blur, 3 passes (~gaussian)."""
    r = int(max(0, r))
    for _ in range(3 if r >= 1 else 0):
        for ax in (0, 1):
            c = np.cumsum(np.pad(a, [(r + 1, r) if i == ax else (0, 0) for i in range(a.ndim)], mode="edge"), axis=ax)
            n = a.shape[ax]
            a = (np.take(c, range(2 * r + 1, 2 * r + 1 + n), axis=ax) - np.take(c, range(0, n), axis=ax)) / (2 * r + 1)
    return a


def contrast(x, c):
    return np.clip((x - 0.5) * (1 + c / 100.0) + 0.5, 0, 1)


def luma(rgb):
    return rgb[:, :, 0] * 0.299 + rgb[:, :, 1] * 0.587 + rgb[:, :, 2] * 0.114


def treat_bw(rgb, black, white):
    return black + (white - black) * contrast(luma(rgb), 42)[:, :, None]


def treat_color(rgb, c=22, sat=-18):
    rgb = contrast(rgb, c)
    y = luma(rgb)[:, :, None]
    return np.clip(y + (rgb - y) * (1 + sat / 100.0), 0, 1)


def noise(canvas, amt, rng):
    canvas += ((rng.random(canvas.shape[:2], dtype=np.float32) * 2 - 1) * (amt / 100.0))[:, :, None]
    np.clip(canvas, 0, 1, out=canvas)


def _grid(W, H, cx, cy):
    return np.arange(W, dtype=np.float32)[None, :] + 0.5 - cx, np.arange(H, dtype=np.float32)[:, None] + 0.5 - cy


def _paint(canvas, a, col):
    canvas *= (1 - a[:, :, None])
    canvas += col * a[:, :, None]


def draw_rect(canvas, cx, cy, w, h, col, stroke=None, round_=0.0, scale=1.0):
    w, h, r = w * scale, h * scale, round_ * scale
    xs, ys = _grid(canvas.shape[1], canvas.shape[0], cx, cy)
    qx, qy = np.abs(xs) - w / 2 + r, np.abs(ys) - h / 2 + r
    d = np.sqrt(np.maximum(qx, 0) ** 2 + np.maximum(qy, 0) ** 2) + np.minimum(np.maximum(qx, qy), 0) - r
    _paint(canvas, np.clip(stroke * scale / 2 + 0.5 - np.abs(d), 0, 1) if stroke else np.clip(0.5 - d, 0, 1), col)


def draw_ring(canvas, cx, cy, rad, sw, col, end):
    xs, ys = _grid(canvas.shape[1], canvas.shape[0], cx, cy)
    a = np.clip(sw / 2 + 0.5 - np.abs(np.sqrt(xs * xs + ys * ys) - rad), 0, 1)
    ang = (np.degrees(np.arctan2(xs, -ys)) + 360) % 360           # 0 at 12 o'clock, clockwise
    _paint(canvas, a * (ang <= end * 3.6), col)


def bulge(img, fov):
    h, w = img.shape[:2]
    k = fov / 70.0 * 0.35
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    nx, ny = (xx - w / 2) / (w / 2), (yy - h / 2) / (h / 2)
    f = 1 - k * (1 - np.clip(nx * nx + ny * ny, 0, 1)) * 0.5
    xi = np.clip((w / 2 + nx * f * (w / 2)).astype(np.int32), 0, w - 1)
    yi = np.clip((h / 2 + ny * f * (h / 2)).astype(np.int32), 0, h - 1)
    return img[yi, xi]


def slide(t, t0, d, a, b):
    """Eased position and its speed (px/s) - the speed drives the horizontal motion blur."""
    f = lambda u: ramp(u, t0, t0 + d, a, b, 0.85)
    return f(t), abs(f(t + 0.02) - f(t - 0.02)) / 0.04


# ------------------------------------------------------------------------------------------------ renderer
class Renderer:
    def __init__(self, plan):
        self.p = plan
        self.W, self.H, self.fps = plan["W"], plan["H"], plan["fps"]
        self.black, self.white = hexrgb(plan["bw_black"]), hexrgb(plan["bw_white"])
        self.accent, self.uibg = hexrgb(plan["accent"]), hexrgb(plan["ui_bg"])
        self.readers, self.stills, self.ins_text = {}, {}, {}
        self.rng = np.random.default_rng(7)
        pr = plan["presenter"]
        self.crop = cw, ch, cx, cy = self._presenter_crop()
        self.pres = Reader(pr["src"], pr["fps"], pr["w"], pr["h"], crop=self.crop)
        self.mattes = {}
        for k, m in plan["mattes"].items():
            d = m["div"]
            mc = (int(round(cw / d)) // 2 * 2, int(round(ch / d)) // 2 * 2, int(round(cx / d)), int(round(cy / d)))
            mc = (min(mc[0], m["w"] - mc[2]), min(mc[1], m["h"] - mc[3]), mc[2], mc[3])
            self.mattes[k] = (Reader(m["src"], m["fps"], m["w"], m["h"], crop=mc, gray=True), d)
        yy, xx = np.mgrid[0:self.H, 0:self.W].astype(np.float32)
        e = np.sqrt(((xx - self.W / 2) / (self.W * 0.44)) ** 2 + ((yy - self.H / 2) / (self.H * 0.48)) ** 2)
        dist = (e - 1) * min(self.W * 0.44, self.H * 0.48)
        self.vignette = np.clip((dist + 130) / 260.0, 0, 1) * (plan["look"].get("vignette", 0) / 100.0)
        self.halftone = None
        if plan["look"].get("halftone"):
            ht = load_rgba(plan["look"]["halftone"])
            if ht.shape[:2] != (self.H, self.W):
                ht = sample(ht, self.W, self.H, 0, 0, self.W / ht.shape[1], self.H / ht.shape[0], 0, 0)[2]
            self.halftone = ht
        self.text_frames = None                          # callback (insert, w, h) -> {'back': [...], 'front': [...]}

    def close(self):
        for r in [*self.readers.values(), self.pres, *(m[0] for m in self.mattes.values())]:
            r.close()

    # --- presenter
    def _presenter_crop(self):
        """The smallest source window any piece ever shows (decoding less is faster)."""
        p, pr = self.p, self.p["presenter"]
        xs0, xs1, ys0, ys1 = [], [], [], []
        for pcs, h in ((p["pieces"], self.H), (p["pieces_half"], self.H // 2)):
            for pc in pcs:
                s = pc["s0"] / 1.004
                xs0.append(pc["ax"] - (self.W / 2) / s)
                xs1.append(pc["ax"] + (self.W / 2) / s)
                ys0.append(pc["ay"] - pc["y0"] / s)
                ys1.append(pc["ay"] + (h - pc["y0"]) / s)
        x0, x1 = max(0, int(min(xs0)) - 8), min(pr["w"], int(max(xs1)) + 8)
        y0, y1 = max(0, int(min(ys0)) - 8), min(pr["h"], int(max(ys1)) + 8)
        return ((x1 - x0) // 2 * 2, (y1 - y0) // 2 * 2, x0, y0)

    def presenter(self, t, half=False, base=100.0, matte=None):
        """Presenter (or a matte of it) at program time t, full or half height; base = punch-in scale %."""
        pcs = self.p["pieces_half"] if half else self.p["pieces"]
        h = self.H // 2 if half else self.H
        pc = next((pc for pc in pcs if pc["t0"] - 1e-6 <= t < pc["t1"] - 1e-6), pcs[-1] if t >= pcs[-1]["t1"] else pcs[0])
        u = (t - pc["t0"]) / max(pc["t1"] - pc["t0"] - 1.0 / self.fps, 1e-3)
        s = pc["s0"] + (pc["s1"] - pc["s0"]) * min(1.0, max(0.0, u))
        k = base / 100.0
        cw, ch, cx, cy = self.crop
        if matte:
            rd, d = self.mattes[matte]
            img, ax, ay, S = rd.frame(t + pc["off"]), (pc["ax"] - cx) / d, (pc["ay"] - cy) / d, s * d * k
        else:
            img, ax, ay, S = self.pres.frame(t + pc["off"]), pc["ax"] - cx, pc["ay"] - cy, s * k
        canvas = np.zeros((h, self.W) if matte else (h, self.W, 3), np.float32)
        return paste(canvas, img, ax, ay, S, self.W / 2, h / 2 + k * (pc["y0"] - h / 2))

    def base_scale(self, t):
        keys, v = self.p["base_keys"], 100.0
        if keys:
            if t <= keys[0][0]:
                v = keys[0][1]
            elif t >= keys[-1][0]:
                v = keys[-1][1]
            else:
                for (ta, va), (tb, vb) in zip(keys, keys[1:]):
                    if ta <= t < tb:
                        v = va + (vb - va) * bez((t - ta) / max(tb - ta, 1e-6), 0.8, 0.8)
                        break
        return max(v, 100.4)

    # --- clips
    def _reader(self, path, fps, w, h, gray=False):
        key = path + ("#g" if gray else "")
        if key not in self.readers:
            self.readers[key] = Reader(path, fps, w, h, gray=gray)
        return self.readers[key]

    def still(self, path, max_side=2400):
        if path not in self.stills:
            self.stills[path] = load_rgba(path, max_side)
        return self.stills[path]

    def _cover(self, spec, img, sw, sh, w, h, tau, cdur):
        """img covering w x h with the clip's slow push and horizontal focus."""
        z0, z1 = spec.get("zoom") or [1.0, 1.08]
        z = z0 + (z1 - z0) * min(1.0, max(0.0, tau / max(cdur, 1e-3)))
        s = max(w / sw, h / sh)
        offx = (0.5 - spec["fx"]) * max(0, sw * s - w) if spec.get("fx") is not None else 0
        return paste(np.zeros((h, w) + img.shape[2:], np.float32), img, sw / 2, sh / 2, s * z, w / 2 + offx, h / 2)

    def clip(self, spec, w, h, tau, cdur):
        """A clip precomp at local time tau: covers w x h, B&W treatment (or colour), optional coloured figures."""
        src = self.still(spec["abs"])[:, :, :3] if spec.get("still") else \
            self._reader(spec["abs"], spec["fps"], spec["w"], spec["h"]).frame(src_time(spec, tau, cdur))
        img = self._cover(spec, src, spec["w"], spec["h"], w, h, tau, cdur)
        if spec.get("color"):
            return treat_color(img)
        out = treat_bw(img, self.black, self.white)
        if spec.get("color_figures_matte_abs"):
            mw, mh = spec["color_figures_matte_w"], spec["color_figures_matte_h"]
            m = self._reader(spec["color_figures_matte_abs"], spec["color_figures_matte_fps"], mw, mh, gray=True).frame(src_time(spec, tau, cdur))
            mm = self._cover(spec, m, mw, mh, w, h, tau, cdur)[:, :, None]
            out = out * (1 - mm) + contrast(img, 15) * mm
        return out

    def cut_matte(self, spec, w, h, tau, cdur):
        sw, sh = spec["cutout_matte_w"], spec["cutout_matte_h"]
        m = self._reader(spec["cutout_matte_abs"], spec["cutout_matte_fps"], sw, sh, gray=True).frame(src_time(spec, tau, cdur))
        return self._cover(spec, m, sw, sh, w, h, tau, cdur)

    def logo(self, c, key, x, y, size, t0, tau):
        lg = self.p["logos"].get(key)
        if not lg or tau < t0:
            return
        img = self.still(lg["src"], max_side=int(size * 1.4) + 8)
        k = ramp(tau, t0, t0 + 0.12, 0.0, 1.15) if tau < t0 + 0.12 else ramp(tau, t0 + 0.12, t0 + 0.22, 1.15, 1.0)
        if k > 0.01:
            put(c, img, img.shape[1] / 2, img.shape[0] / 2, size / max(img.shape[:2]) * k, x, y)

    def faint(self, c, spec, tau, dur, op):
        if spec:
            img = blur(self.clip(spec, c.shape[1], c.shape[0], tau, dur), 4)
            c *= (1 - op)
            c += img * op

    def draw_text_group(self, c, I, grp, tau):
        fr = self.text_frames(I, c.shape[1], c.shape[0]).get(grp) or []
        k = int(round(tau * self.fps))
        if 0 <= k < len(fr) and fr[k]:
            over(c, fr[k][2], fr[k][0], fr[k][1])

    # --- inserts
    def seq_clips(self, c, clips, w, h, x, y, vis, tau, collapse=False):
        """Clips one after another; later clips land like photos laid on top (with a soft shadow) unless full frame."""
        t, full = 0.0, (w == c.shape[1] and h == c.shape[0])
        OX, OY = [0, 26, -22, 30], [0, 18, 32, 44]
        for k, spec in enumerate(clips):
            d = vis - t if k == len(clips) - 1 else (spec.get("dur") or vis / len(clips))
            if tau >= t:
                lt = tau - t
                img = self.clip(spec, w, h, lt, vis + 0.55 - t + 0.05)
                if k == 0 and collapse and not full:            # opens from a thin line
                    hh = ramp(lt + t, 0.04, 0.36, 4.0, float(h), 0.85)
                    m0, m1 = int(round(h / 2 - hh / 2)), int(round(h / 2 + hh / 2))
                    img2 = np.zeros((h, w, 4), np.float32)
                    img2[m0:m1, :, :3] = img[m0:m1]
                    img2[m0:m1, :, 3] = 1
                    put(c, img2, w / 2, h / 2, 1.0, x, y)
                elif k == 0:
                    put(c, img, w / 2, h / 2, 1.0, x, y)
                else:
                    ox, oy = (0, 0) if full else (OX[k % 4], OY[min(k, 3)])
                    px = ramp(tau, t, t + 0.2, x + ox * 2.4, x + ox, 0.8)
                    py = ramp(tau, t, t + 0.2, y + oy * 2.4 - 40, y + oy, 0.8)
                    sc = ramp(tau, t, t + 0.2, 1.14, 1.0, 0.8)
                    op = ramp(tau, t, t + 0.05, 0.0, 1.0)
                    if not full:
                        sh = np.zeros((h + 120, w + 120, 4), np.float32)
                        sh[60:60 + h, 60:60 + w, 3] = 0.7
                        sh[:, :, 3] = blur(sh[:, :, 3], 15)
                        put(c, sh, (w + 120) / 2 - 7, (h + 120) / 2 - 7, sc, px, py, opacity=op)
                    put(c, opaque(img), w / 2, h / 2, sc, px, py, opacity=op)
            t += d

    def insert(self, I, tau):
        """The insert comp (W x H, or W x H/2 in split layout) at its local time tau."""
        W, h = self.W, self.H // 2 if I["layout"] == "split" else self.H
        vis, dur, kind = I["vis"], I["dur"], I["kind"]
        c = np.zeros((h, W, 3), np.float32)
        if kind == "logo_flash":
            sd = vis / len(I["slots"])
            k = min(len(I["slots"]) - 1, int(tau / sd))
            c[:] = hexrgb(I["slots"][k][1])
            self.logo(c, I["slots"][k][0], W / 2, h * 0.4, min(W, h) * 0.28, k * sd, tau)
        elif kind == "frame":
            c[:] = hexrgb(I.get("bg") or "#0B0B0B")
            r = I["rect"]
            self.seq_clips(c, I["clips"], int(r[2]), int(r[3]), r[0], r[1], vis, tau, collapse=not I.get("noframeanim"))
            if I.get("logo"):
                self.logo(c, *I["logo"][:4], 0.15, tau)
        elif kind == "full":
            self.seq_clips(c, I["clips"], W, h, W / 2, h / 2, vis, tau)
            c *= 0.9
            if I.get("logo"):
                self.logo(c, *I["logo"][:4], 0.15, tau)
            for q, lg in enumerate(I.get("logos") or []):
                self.logo(c, *lg[:4], 0.1 + q * 0.2, tau)
        elif kind == "solid":
            c[:] = hexrgb(I.get("bg") or self.p["ui_bg"])
            self.faint(c, I.get("bgclip"), tau, dur, 0.20)
        elif kind == "band":
            c[:] = 0.043
            spec = I["clips"][0]
            img = self.clip(spec, W, h, tau, dur)
            cy, bh = h / 2 + 20, round(h * 0.176)
            y0, y1 = (cy - bh, cy + bh) if I.get("staticband") else \
                (ramp(tau, 0.18, 0.42, 0, cy - bh, 0.85), ramp(tau, 0.18, 0.42, h, cy + bh, 0.85))
            c[int(y0):int(y1)] = img[int(y0):int(y1)]
            self.draw_text_group(c, I, "back", tau)
            if spec.get("cutout_matte_abs"):              # subject cut out in front of the band words
                m = self.cut_matte(spec, W, h, tau, dur)[:, :, None]
                c[:] = c * (1 - m) + img * m
                self.draw_text_group(c, I, "front", tau)
                if 0.42 <= tau < 0.50:
                    c[:] = c * (1 - m) + m
            else:
                self.draw_text_group(c, I, "front", tau)
        elif kind == "vsplit":
            ts2 = I.get("tsplit") or vis / 2
            c[:] = self.clip(I["clips"][0], W, h, tau, dur)
            if tau >= ts2:
                b = self.clip(I["clips"][1], W, h // 2, tau - ts2, dur - ts2)
                x, v = slide(tau, ts2, 0.4, W * 1.5, W / 2)
                put(c, opaque(b), W / 2, h / 4, 1.0, x, h * 0.75, mblur=v * SHUTTER / self.fps)
                if tau >= ts2 + 0.36:
                    c[int(h / 2 - 3):int(h / 2 + 3)] = DIVIDER
        elif kind == "cards":
            c[:] = self.uibg
            self.faint(c, I.get("bgclip"), tau, dur, 0.20)
            cs = I.get("cards") or []
            cw = W * 0.84 / max(len(cs), 1)
            chh, cyy = cw * 1.4, h * 0.55
            if I.get("title"):
                draw_rect(c, W / 2, h * 0.16, W * 0.8, 2, WHITE)
            for a, cd in enumerate(cs):
                at, xa = cd.get("t") or 0, W * 0.08 + cw * (a + 0.5)
                if tau >= at:
                    draw_rect(c, xa, cyy, cw * 0.92, chh, WHITE, stroke=2, round_=6, scale=ramp(tau, at, at + 0.16, 0.92, 1.0, 0.75))
                    if cd.get("logo"):
                        self.logo(c, cd["logo"], xa, cyy - chh * 0.17, cw * 0.5, at, tau)
            self.draw_text_group(c, I, "back", tau)
        elif kind == "bar":
            c[:] = self.uibg
            self.faint(c, I.get("bgclip"), tau, dur, 0.22)
            E, d0, d1 = bar_box(I)
            vf, vt = I.get("from", 100), I.get("to", 0)
            smax = max(abs(vf), abs(vt), 1)
            draw_rect(c, E["bx"] + E["bw"] / 2, E["by"] + E["bh"] / 2, E["bw"] + 24, E["bh"] + 24, WHITE, stroke=4)
            frac = ramp(tau, d0, d1, vf / smax, vt / smax)
            if frac > 0:
                c[int(E["by"]):int(E["by"] + E["bh"]), int(E["bx"]):int(E["bx"] + E["bw"] * frac)] = self.accent
            self.draw_text_group(c, I, "back", tau)
        elif kind == "number":
            c[:] = self.uibg
            self.faint(c, I.get("bgclip"), tau, dur, 0.22)
            draw_rect(c, W / 2, I.get("y") or h * 0.5, 760, 330, WHITE, stroke=3, round_=12, scale=ramp(tau, 0, 0.15, 0.9, 1.0, 0.75))
            self.draw_text_group(c, I, "back", tau)
        elif kind == "converge":
            c[:] = self.uibg
            self.faint(c, I.get("bgclip"), tau, dur, 0.22)
            g0 = [(W * 0.22, h * 0.28), (W * 0.78, h * 0.28), (W * 0.22, h * 0.72), (W * 0.78, h * 0.72)]
            for (gx, gy), key in zip(g0, I.get("logos") or []):
                tx, ty = W / 2 + (gx - W / 2) * 0.22, h / 2 + (gy - h / 2) * 0.22
                self.logo(c, key, ramp(tau, 0.25, 1.3, gx, tx, 0.85), ramp(tau, 0.25, 1.3, gy, ty, 0.85), min(W, h) * 0.16, 0.0, tau)
            end = ramp(tau, 1.3, 1.8, 0, 100, 0.75)
            if end > 0:
                draw_ring(c, W / 2, h / 2, min(W, h) * 0.21, 5, self.accent, end)
        elif kind == "cutout":
            c[:] = self.clip(I["bgclip"], W, h, tau, dur) * 0.85
            if "matte_body" in self.p["mattes"]:
                t = I["t0"] + tau
                sc = ramp(tau, 0, 0.3, 0.9, 1.0, 0.8) if tau < 0.3 else ramp(tau, 0.3, dur, 1.0, 1.03, 0.8)
                img = np.dstack([self.presenter(t), self.presenter(t, matte="matte_body")])
                put(c, img, W / 2, h / 2, 0.86 * sc, W / 2, h / 2 + h * (1 - 0.86) / 2)
        elif kind == "pframe":
            if I.get("bgclip"):
                c[:] = blur(self.clip(I["bgclip"], W, h, tau, dur), 5) * 0.7
            sc = ramp(tau, 0, 0.28, 0.86, 1.0, 0.8) * 0.58
            draw_rect(c, W / 2, h / 2 + 20, W * 0.58 + 16, h * 0.58 + 16, WHITE, scale=sc / 0.58)
            put(c, self.presenter(I["t0"] + tau), W / 2, h / 2, sc, W / 2, h / 2 + 20)
        noise(c, 5, self.rng)
        return c

    # --- main comp
    def entry(self, I, t):
        """x, scale and bulge of a full insert layer at time t."""
        W, a4, b4, tr = self.W, I["in"], I["out"], I["trans"]
        endS = 100.0 if I.get("norelease") else 104.0
        x, s, bul = W / 2, 100.0, 0.0
        if tr in ("whip", "whipL"):
            x = ramp(t, a4, a4 + TD, W / 2 + (-1 if tr == "whipL" else 1) * W, W / 2, 0.85)
            s = ramp(t, a4 + TD, b4, 100, endS)
        elif tr in ("zoom", "zoomrot"):
            s = ramp(t, a4, a4 + TD, 165, 100, 0.85) if t < a4 + TD else ramp(t, a4 + TD, b4, 100, 104, 0.85)
        elif tr == "bulge":
            s = ramp(t, a4, a4 + 0.26, 175, 100, 0.85) if t < a4 + 0.26 else ramp(t, a4 + 0.26, b4, 100, 104, 0.85)
            bul = ramp(t, a4, a4 + 0.26, 70, 0, 0.85)
        else:
            s = ramp(t, a4, b4, 100, endS)
        if t >= a4 + I.get("entry", 0):
            s = max(s, 100.4)
        return x, s, bul

    def split_half(self, c, blk, t):
        W, H = self.W, self.H
        if blk["t0"] <= t < blk["t1"]:
            y = ramp(t, blk["t0"], blk["t0"] + 0.35, H * 1.25, H * 0.75, 0.85)
            put(c, opaque(self.presenter(t, half=True)), W / 2, H / 4, 1.0, W / 2, y)
            if blk["divider"][0] <= t < blk["divider"][1]:
                c[int(H / 2 - 3):int(H / 2 + 3)] = DIVIDER

    def frame(self, t, front=None, behind=None):
        W, H = self.W, self.H
        base = self.base_scale(t)
        c = self.presenter(t, base=base)
        if behind is not None and behind[:, :, 3].max() > 0:            # words behind the head
            pres = c.copy()
            over(c, behind, 0, 0)
            if "matte_head" in self.p["mattes"]:
                m = self.presenter(t, base=base, matte="matte_head")[:, :, None]
                c = c * (1 - m) + pres * m
        for I in self.p["inserts"]:
            if I["layout"] == "split":
                blk = next((b for b in self.p["split_blocks"] if b["t0"] - 1e-6 <= I["t0"] < b["t1"]), None)
                if not (I["in"] - 1e-6 <= t < I["out"] - 1e-6):
                    if I.get("groupStart") and blk:
                        self.split_half(c, blk, t)
                    continue
                img = self.insert(I, t - I["t0"])
                if I.get("groupStart"):
                    put(c, img, W / 2, H / 4, 1.0, W / 2, ramp(t, I["t0"], I["t0"] + 0.35, -H / 4, H / 4, 0.85))
                    if blk:
                        self.split_half(c, blk, t)
                else:
                    x, v = slide(t, I["t0"], 0.3, W * 1.5, W / 2)
                    put(c, opaque(img), W / 2, H / 4, 1.0, x, H / 4, mblur=v * SHUTTER / self.fps)
            else:
                if not (I["in"] - 1e-6 <= t < I["out"] - 1e-6):
                    continue
                img = self.insert(I, t - I["t0"])
                x, s, bul = self.entry(I, t)
                if bul > 0.5:
                    img = bulge(img, bul)
                v = abs(self.entry(I, t + 0.02)[0] - self.entry(I, t - 0.02)[0]) / 0.04
                put(c, opaque(img), W / 2, H / 2, s / 100.0, x, H / 2, mblur=v * SHUTTER / self.fps)
            if I.get("flash") == "invert" and I["t0"] <= t < I["t0"] + 2.0 / self.fps:
                c[:] = 1 - c
            if I.get("flash") == "silhouette" and I["t0"] <= t < I["t0"] + 3.0 / self.fps and "matte_body" in self.p["mattes"]:
                c[:] = self.presenter(t, matte="matte_body")[:, :, None]
        if front is not None:
            over(c, front, 0, 0)
        if self.halftone is not None:                    # look: halftone (overlay blend), vignette, grain
            o = self.p["look"].get("halftone_opacity", 24) / 100.0 * self.halftone[:, :, 3:4]
            s = self.halftone[:, :, :3]
            c += (np.where(c < 0.5, 2 * c * s, 1 - 2 * (1 - c) * (1 - s)) - c) * o
        c *= (1 - self.vignette[:, :, None])
        noise(c, self.p["look"].get("grain", 4), self.rng)
        return np.clip(c, 0, 1)


def bar_box(I):
    E = I.get("box") or dict(bx=90, by=380 if I["layout"] == "split" else 860, bw=900, bh=70 if I["layout"] == "split" else 84)
    d0 = I.get("d0") or 0.5
    return E, d0, I.get("d1") or max(d0 + 0.5, I["vis"] - 0.4)
