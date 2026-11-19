"""Helpers of runners/fam_w3_08.py used by data cards, copied verbatim (the extractor binds a card to them only when
their AST hash with every dependency equals the original's)."""
from __future__ import annotations

from PIL import Image
from PIL import ImageDraw
from PIL import ImageFilter
from PIL import ImageFont
from pathlib import Path
from .core import fx
import json
import math
import numpy as np
import shutil
import subprocess


W, H = 192, 108


def _rng(seed=7):
    return np.random.default_rng(seed)


def _u8(a):
    return np.clip(np.round(np.asarray(a, dtype=float)), 0, 255).astype(np.uint8)


def _png(path, a):
    Image.fromarray(_u8(a)).save(path)
    return Path(path)


def _load(path, mode="RGB"):
    return np.asarray(Image.open(path).convert(mode)).astype(float)


def _hex(h):
    h = h.lstrip("#")
    return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], dtype=float)


def _luma(a):
    a = np.asarray(a, dtype=float)
    return a[..., 0] * .2126 + a[..., 1] * .7152 + a[..., 2] * .0722


def _blur(a, s):
    from scipy.ndimage import gaussian_filter
    a = np.asarray(a, dtype=float)
    if a.ndim == 3:
        return gaussian_filter(a, (s, s, 0))
    return gaussian_filter(a, s)


def _hf(a):
    a = np.asarray(a, dtype=float)
    return float(np.abs(a - _blur(a, 1.5)).mean())


def _vid(path, frames, fps=30):
    """Lossless RGB H.264 (libx264rgb -qp 0) so the read-back equals what was rendered."""
    frames = [_u8(f) for f in frames]
    h, w = frames[0].shape[:2]
    p = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
                        "-s", "%dx%d" % (w, h), "-r", str(fps), "-i", "-", "-c:v", "libx264rgb", "-qp", "0",
                        "-preset", "ultrafast", str(path)], input=b"".join(f.tobytes() for f in frames),
                       capture_output=True, timeout=60)
    if p.returncode:
        raise RuntimeError(p.stderr.decode(errors="replace")[-300:])
    return Path(path)


def _rd(path):
    info = fx.probe(path)
    v = next(s for s in info["streams"] if s["codec_type"] == "video")
    return fx.frames(path, size=(int(v["width"]), int(v["height"])))


def _jw(path, obj):
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    return Path(path)


def _grid(h=H, w=W):
    yy, xx = np.mgrid[0:h, 0:w].astype(float)
    return xx, yy


def _noise(x, y, seed=1, period=256):
    """Smooth value noise in [-1, 1] (cubic-spline lattice, wraps)."""
    from scipy.ndimage import map_coordinates
    g = _rng(seed).random((period, period)) * 2 - 1
    return map_coordinates(g, [np.asarray(y) % period, np.asarray(x) % period], order=3, mode="grid-wrap")


def _fbm(x, y, octaves=4, seed=1):
    a, s, w = 0.0, 0.0, 1.0
    for i in range(octaves):
        a = a + w * _noise(x * 2 ** i, y * 2 ** i, seed + 31 * i)
        s += w
        w *= .5
    return a / s


def _font(size, bold=True, mono=False):
    for p in (["/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"] if mono else
              ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else
               "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]):
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def _text_mask(text, size, shape=(H, W), xy=None, font=None, **kw):
    im = Image.new("L", (shape[1], shape[0]), 0)
    d = ImageDraw.Draw(im)
    f = font or _font(size)
    bb = d.textbbox((0, 0), text, font=f, **kw)
    if xy is None:
        xy = ((shape[1] - (bb[2] - bb[0])) / 2 - bb[0], (shape[0] - (bb[3] - bb[1])) / 2 - bb[1])
    d.text(xy, text, fill=255, font=f, **kw)
    return np.asarray(im).astype(float) / 255.0


def _phase(a, b):
    import cv2
    (dx, dy), _ = cv2.phaseCorrelate(np.asarray(a, np.float32), np.asarray(b, np.float32))
    return float(dx), float(dy)


def _orient(img, mask=None):
    """Dominant line orientation in degrees (0 = horizontal lines), image y axis pointing down."""
    import cv2
    g = np.asarray(img, np.float32)
    gx = cv2.Sobel(g, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(g, cv2.CV_32F, 0, 1, ksize=3)
    if mask is not None:
        gx, gy = gx[mask], gy[mask]
    jxx, jyy, jxy = float((gx * gx).sum()), float((gy * gy).sum()), float((gx * gy).sum())
    theta = 0.5 * math.degrees(math.atan2(2 * jxy, jxx - jyy))  # gradient direction
    return (theta + 90.0 + 180.0) % 180.0


def _softlight(b, s):
    b, s = b / 255.0, s / 255.0
    return ((1 - 2 * s) * b * b + 2 * s * b) * 255.0


def _vignette(h, w, strength, power=2.0):
    xx, yy = _grid(h, w)
    r = np.hypot((xx - (w - 1) / 2) / ((w - 1) / 2), (yy - (h - 1) / 2) / ((h - 1) / 2)) / math.sqrt(2)
    return 1 - strength * np.clip(r, 0, 1) ** power


def _ease_io_cubic(u):
    u = np.clip(u, 0, 1)
    return np.where(u < .5, 4 * u ** 3, 1 - (-2 * u + 2) ** 3 / 2)


def _ease_out_cubic(u):
    u = np.clip(u, 0, 1)
    return 1 - (1 - u) ** 3


def _bez(x1, y1, x2, y2):
    def f(x):
        if x <= 0:
            return 0.0
        if x >= 1:
            return 1.0
        lo, hi = 0.0, 1.0
        for _ in range(50):
            m = (lo + hi) / 2
            cx = 3 * x1 * m * (1 - m) ** 2 + 3 * x2 * m * m * (1 - m) + m ** 3
            lo, hi = (m, hi) if cx < x else (lo, m)
        m = (lo + hi) / 2
        return 3 * y1 * m * (1 - m) ** 2 + 3 * y2 * m * m * (1 - m) + m ** 3
    return f


def _disc_mask(h, w, cx, cy, r, ss=4):
    xx, yy = np.mgrid[0:h * ss, 0:w * ss].astype(float)[::-1]
    yy, xx = np.mgrid[0:h * ss, 0:w * ss].astype(float)
    m = (((xx + .5) / ss - cx) ** 2 + ((yy + .5) / ss - cy) ** 2 <= r * r).astype(float)
    return m.reshape(h, ss, w, ss).mean((1, 3))


def _photo(h=H, w=W, seed=3):
    """Deterministic 'photo': smooth colour field + shapes + texture."""
    xx, yy = _grid(h, w)
    n = _fbm(xx / 18, yy / 18, 3, seed)
    img = np.stack([120 + 80 * np.sin(xx / w * 3 + n), 110 + 70 * np.cos(yy / h * 2.5 - n), 140 + 60 * n], -1)
    img[(xx - w * .33) ** 2 + (yy - h * .5) ** 2 < (h * .22) ** 2] = [235, 200, 60]
    img[int(h * .2):int(h * .8), int(w * .62):int(w * .78)] = [40, 60, 150]
    img += _rng(seed).normal(0, 6, img.shape)
    return np.clip(img, 0, 255)


def _grain_tile(seed=7, n=192):
    return np.clip(128 + 46 * _rng(seed).normal(0, 1, (n, n)), 0, 255)


def _grain_frame(base, t, tile, opacity=.08, fps_seed=24):
    seed = 1 + int(math.floor(t * fps_seed)) % 97
    dx, dy = (seed * 73856093) % tile.shape[1], (seed * 19349663) % tile.shape[0]
    g = np.roll(tile, (dy, dx), (0, 1))
    reps = (math.ceil(base.shape[0] / g.shape[0]), math.ceil(base.shape[1] / g.shape[1]))
    g = np.tile(g, reps)[:base.shape[0], :base.shape[1]][..., None]
    return base * (1 - opacity) + _softlight(base, g) * opacity


def _grain_std(F, region):
    y0, y1, x0, x1 = region
    return float(np.mean([_luma(f[y0:y1, x0:x1]).std() for f in F]))


def _hud(h, w, k, n):
    m = np.zeros((h, w), bool)
    L = 14
    for (x, y, sx, sy) in [(6, 6, 1, 1), (w - 7, 6, -1, 1), (6, h - 7, 1, -1), (w - 7, h - 7, -1, -1)]:
        xs = sorted([x, x + sx * L])
        ys = sorted([y, y + sy * L])
        m[y, xs[0]:xs[1] + 1] = True
        m[ys[0]:ys[1] + 1, x] = True
    lab = _text_mask("REC 01", 9, (h, w), xy=(24, 8), font=_font(9, mono=True)) > .5
    m |= lab
    mw = 100
    fill = int(round(mw * k / (n - 1)))
    m[h - 14:h - 11, 46:46 + fill] = True
    return m, fill


def _pip(x, y, poly):
    """Even-odd ray casting point-in-polygon on arrays."""
    inside = np.zeros(np.shape(x), bool)
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        cond = ((y1 > y) != (y2 > y)) & (x < (x2 - x1) * (y - y1) / ((y2 - y1) + 1e-12) + x1)
        inside ^= cond
    return inside


def _scan(h=120, w=120):
    """A 'scanned' hand drawing: dark blob + inner detail on a flat off-white ground."""
    im = Image.new("RGB", (w, h), (238, 236, 228))
    d = ImageDraw.Draw(im)
    d.ellipse([28, 30, 92, 90], fill=(60, 90, 160))
    d.polygon([(60, 12), (75, 34), (45, 34)], fill=(200, 70, 50))
    d.line([(40, 60), (80, 60)], fill=(20, 20, 20), width=3)
    return np.asarray(im).astype(float)


def _sticker(scan, outline=6, shadow_off=2, shadow_a=.2, shadow_blur=4, ground_tol=18):
    corner = scan[0, 0]
    art = (np.abs(scan - corner).max(-1) > ground_tol)
    a = Image.fromarray((art * 255).astype(np.uint8))
    ring = np.asarray(a.filter(ImageFilter.MaxFilter(2 * outline + 1))).astype(float) / 255
    sh = np.roll(np.roll(ring, shadow_off, 0), shadow_off, 1)
    sh = np.asarray(Image.fromarray((sh * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(shadow_blur))).astype(float) / 255 * shadow_a
    rgba = np.zeros(scan.shape[:2] + (4,))
    rgba[..., :3] = 0
    rgba[..., 3] = sh * 255
    white = ring[..., None]
    rgba[..., :3] = rgba[..., :3] * (1 - white) + 255 * .9 * white + 0
    rgba[..., 3] = np.maximum(rgba[..., 3], ring * 255)
    rgba[art, :3] = scan[art]
    rgba[art, 3] = 255
    return rgba, art, ring


def _sphere(h, w, cx, cy, R):
    xx, yy = _grid(h, w)
    dx, dy = (xx - cx) / R, (yy - cy) / R
    r2 = dx * dx + dy * dy
    inside = r2 <= 1
    nz = np.sqrt(np.clip(1 - r2, 0, 1))
    return inside, np.stack([dx, dy, nz], -1)


def _ggx_shade(nrm, inside, rough, light=(-.5, -.6, .62), base=(200, 120, 90), spec=.04):
    L = np.array(light) / np.linalg.norm(light)
    V = np.array([0, 0, 1.0])
    Hh = (L + V) / np.linalg.norm(L + V)
    ndl = np.clip(nrm @ L, 0, 1)
    ndh = np.clip(nrm @ Hh, 0, 1)
    a2 = rough ** 4
    D = a2 / (math.pi * (ndh ** 2 * (a2 - 1) + 1) ** 2)
    specular = D * spec * ndl
    col = np.array(base) * (.12 + .88 * ndl)[..., None] + 255 * np.clip(specular, 0, 4)[..., None] * .25
    return np.where(inside[..., None], col, 20.0)


def _screen(h, w, pitch, angle_deg, radius_fn, ss=3):
    """Render a rotated dot screen; radius_fn(x, y) gives each dot radius. Returns coverage in 0..1 and dot list."""
    im = Image.new("L", (w * ss, h * ss), 0)
    d = ImageDraw.Draw(im)
    a = math.radians(angle_deg)
    ca, sa = math.cos(a), math.sin(a)
    dots = []
    span = int(max(w, h) * 1.5 / pitch) + 2
    for i in range(-span, span):
        for j in range(-span, span):
            x = w / 2 + (i * ca - j * sa) * pitch
            y = h / 2 + (i * sa + j * ca) * pitch
            if -pitch < x < w + pitch and -pitch < y < h + pitch:
                r = radius_fn(x, y)
                dots.append((x, y, r))
                if r > .05:
                    d.ellipse([(x - r) * ss, (y - r) * ss, (x + r) * ss, (y + r) * ss], fill=255)
    return np.asarray(im.resize((w, h), Image.BOX)).astype(float) / 255, dots


BAYER = np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]])


def _rounded(h, w, box, rad, ss=4):
    im = Image.new("L", (w * ss, h * ss), 0)
    x0, y0, x1, y1 = box
    ImageDraw.Draw(im).rounded_rectangle([x0 * ss, y0 * ss, x1 * ss, y1 * ss], radius=rad * ss, fill=255)
    return np.asarray(im.resize((w, h), Image.BOX)).astype(float) / 255


def _saturate(img, s):
    l = _luma(img)[..., None]
    return np.clip(l + (img - l) * s, 0, 255)


def _starfield(h, w, seed=29):
    xx, yy = _grid(h, w)
    bg = np.stack([40 + 60 * xx / w, 20 + 30 * yy / h, 90 + 80 * (1 - xx / w)], -1)
    bg += 50 * np.exp(-((xx - w * .3) ** 2 + (yy - h * .4) ** 2) / (2 * (h * .3) ** 2))[..., None] * np.array([1, .3, .6])
    rng = _rng(seed)
    for _ in range(int(h * w / 60)):
        x, y = int(rng.integers(0, w)), int(rng.integers(0, h))
        bg[y, x] = 250
    return np.clip(bg, 0, 255)


GOLD = [("#fff4d6", 0), ("#f0d793", 16), ("#c9a24a", 40), ("#8a6424", 56), ("#b88d3a", 68), ("#f2dc9c", 86), ("#fff4d6", 100)]


def _gold_grad(t):
    t = np.clip(t, 0, 1) * 100
    stops = [(p, _hex(c)) for c, p in GOLD]
    out = np.zeros(np.shape(t) + (3,))
    for (p0, c0), (p1, c1) in zip(stops, stops[1:]):
        sel = (t >= p0) & (t <= p1)
        u = ((t - p0) / (p1 - p0))[..., None]
        out[sel] = (c0 * (1 - u) + c1 * u)[sel]
    return out


def _AB(h=H, w=W):
    xx, yy = _grid(h, w)
    A = np.clip(np.stack([xx * 1.3 + 20, yy * 2.2, 60 + 0 * xx], -1) + 40 * (((xx // 10 + yy // 10) % 2) == 0)[..., None] * np.array([1, 0, 0]), 0, 255)
    B = np.stack([30 + 0 * xx, 255 - yy * 2, 100 + xx * .8], -1)
    B[(xx - w / 2) ** 2 + (yy - h / 2) ** 2 < (h * .2) ** 2] = [250, 250, 20]
    return A.astype(np.float32), np.clip(B, 0, 255).astype(np.float32)


def _disc_img(h=H, w=W, r=16, fg=255, bg=10, cx=None, cy=None):
    m = _disc_mask(h, w, w / 2 if cx is None else cx, h / 2 if cy is None else cy, r)
    return (bg + (fg - bg) * m)[..., None].repeat(3, -1).astype(np.float32)


def _radius(f, thr=128):
    return math.sqrt(float((_luma(f) > thr).sum()) / math.pi)


def _seq_out(wd, name, frames, fps=30):
    out = _vid(wd / (name + ".mp4"), frames, fps)
    return out, _rd(out)


_CURVES = {"linear": lambda u: float(np.clip(u, 0, 1)), "easeInOutCubic": lambda u: float(_ease_io_cubic(u)),
           "easeOutCubic": lambda u: float(_ease_out_cubic(u))}


def _frames_for(ms, fps=30):
    return max(1, int(round(ms / 1000 * fps)))


def _hero_box(f, col):
    m = np.abs(f - col).max(-1) < 3
    if not m.any():
        return None
    ys, xs = np.nonzero(m)
    return (int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max()))


_DRIVER = r"""
const {chromium} = require(%(pw)s);
const fs = require('fs');
(async () => {
  const b = await chromium.launch({args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist',
                                           '--allow-file-access-from-files']});
  const pg = await b.newPage({viewport: {width: %(w)d, height: %(h)d}, deviceScaleFactor: 1});
  const errs = [];
  pg.on('pageerror', e => errs.push(String(e)));
  await pg.exposeFunction('__shot', async (name) => { await pg.screenshot({path: %(wd)s + '/' + name + '.png'}); return true; });
  await pg.goto(%(url)s);
  let r;
  try { r = await pg.evaluate(async () => await window.__run()); } catch (e) { r = {error: String(e)}; }
  r.page_errors = errs;
  fs.writeFileSync(%(out)s, JSON.stringify(r));
  await b.close();
})();
"""


def _pw_path():
    for base in [Path(shutil.which("node") or "/usr/bin/node").resolve().parent.parent / "lib/node_modules",
                 Path("/opt/node22/lib/node_modules"), Path("/usr/lib/node_modules"), Path("/usr/local/lib/node_modules")]:
        if (base / "playwright").exists():
            return base / "playwright"
    raise RuntimeError("node playwright not installed")


def _browser(wd, name, html_body, size=(320, 180), timeout=60):
    """Load a page in Chromium (SwiftShader WebGL); window.__run() returns JSON; data:image/png values are saved."""
    import base64
    page = Path(wd) / (name + ".html")
    page.write_text(html_body, encoding="utf-8")
    res = Path(wd) / (name + "_result.json")
    drv = Path(wd) / (name + "_drive.js")
    drv.write_text(_DRIVER % {"pw": json.dumps(str(_pw_path())), "w": size[0], "h": size[1], "wd": json.dumps(str(wd)),
                              "url": json.dumps(page.as_uri()), "out": json.dumps(str(res))}, encoding="utf-8")
    fx.run(["node", drv], timeout=timeout)
    r = json.loads(res.read_text(encoding="utf-8"))
    if r.get("error"):
        raise RuntimeError("page: %s %s" % (r["error"], r.get("page_errors")))
    for k, v in list(r.items()):
        if isinstance(v, str) and v.startswith("data:image/png;base64,"):
            p = Path(wd) / ("%s_%s.png" % (name, k))
            p.write_bytes(base64.b64decode(v.split(",", 1)[1]))
            r[k] = str(p)
    res.write_text(json.dumps(r), encoding="utf-8")
    return r, res


_VT_CSS = """
body{margin:0;background:#fff;font:14px sans-serif}
#box{position:absolute;width:60px;height:40px}
.a #box{left:20px;top:20px;background:#ff0000}
.b #box{left:20px;top:100px;background:#0000ff}
::view-transition-old(root){animation:150ms linear both vt-fade-out}
::view-transition-new(root){animation:210ms cubic-bezier(0,0,.58,1) both vt-slide-in}
@keyframes vt-fade-out{to{opacity:0}}
@keyframes vt-slide-in{from{transform:translateX(60px)}}
"""


def _vt_measure(wd, name, use_vt, hero=False):
    if hero:
        css = """body{margin:0;background:#fff}#hero{position:absolute;background:#00a000;view-transition-name:hero}
.a #hero{left:20px;top:40px;width:40px;height:40px}.b #hero{left:200px;top:30px;width:120px;height:80px}
::view-transition-group(hero){animation-duration:400ms;animation-timing-function:linear}
::view-transition-old(root),::view-transition-new(root){animation:none}"""
        inner = "<div id='hero'></div>"
    else:
        css, inner = _VT_CSS, "<div id='box'></div>"
    page = """<!doctype html><html><head><style>%s</style></head><body class='a'>%s<script>
window.__run = async () => {
  const flip = () => { document.body.className = 'b'; };
  const out = {supported: !!document.startViewTransition};
  if (%s && document.startViewTransition) {
    const vt = document.startViewTransition(flip); await vt.ready;
    const an = document.getAnimations().filter(a => a.effect && a.effect.pseudoElement);
    out.anims = an.map(a => ({name: a.animationName, pe: a.effect.pseudoElement, dur: a.effect.getTiming().duration}));
    an.forEach(a => a.pause());
    for (const [k, t] of %s) { an.forEach(a => { a.currentTime = t; }); await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r))); await window.__shot('%s_' + k); out[k] = '%s_' + k + '.png';
      const de = document.documentElement, go = getComputedStyle(de, '::view-transition-old(root)'), gg = getComputedStyle(de, '::view-transition-group(hero)');
      out[k + '_old_opacity'] = parseFloat(go.opacity); out[k + '_group'] = [gg.width, gg.height]; }
    an.forEach(a => a.finish()); await vt.finished;
  } else {
    flip(); await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));
    out.anims = document.getAnimations().map(a => ({name: a.animationName}));
    for (const [k, t] of %s) { await window.__shot('%s_' + k); out[k] = '%s_' + k + '.png'; }
  }
  return out;
};</script></body></html>""" % (css, inner, "true" if use_vt else "false",
                                  json.dumps([["mid", 200]] if hero else [["mid", 75], ["new105", 105]]), name, name,
                                  json.dumps([["mid", 200]] if hero else [["mid", 75], ["new105", 105]]), name, name)
    r, res = _browser(wd, name, page, (360, 180))
    return r, res


def _box_of(img, col, tol=40):
    m = np.abs(img - np.array(col)).max(-1) < tol
    if not m.any():
        return None
    ys, xs = np.nonzero(m)
    return [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]
