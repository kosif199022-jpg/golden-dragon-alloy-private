"""Redraw every frame as vector layers (SVG), rasterize it with an independent renderer (cairosvg), and measure how far
the redraw is from the frame: mask IoU, colour-label agreement, PSNR, SSIM and ΔE inside the character's box."""
from __future__ import annotations

import gzip
import io
import json
import subprocess
from multiprocessing import Pool
from pathlib import Path

import cairosvg
import cv2
import numpy as np
from PIL import Image
from skimage.color import rgb2lab
from skimage.measure import find_contours
from skimage.metrics import structural_similarity

from . import analyze as A


def fill_unlabelled(lm, mask):
    """Antialias pixels (no palette colour within reach) take the label of the nearest labelled pixel, so the colour
    regions tile the character with no gaps and need no dilation."""
    lab = lm.copy()
    unl = (lab < 0) & mask
    if unl.any():
        _, idx = cv2.distanceTransformWithLabels((lab < 0).astype(np.uint8), cv2.DIST_L2, 5, labelType=cv2.DIST_LABEL_PIXEL)
        ys, xs = np.nonzero(lab >= 0)
        seeds = np.full(idx.max() + 1, -1, np.int16)
        seeds[idx[ys, xs]] = lab[ys, xs]
        lab[unl] = seeds[idx[unl]]
    return lab


def svg_for(lm, pal, roles, size, bg_name=None, eps=0.35, mask=None):
    """One path per colour, every region and hole (even-odd). Boundaries come from marching squares at the 0.5 level
    of each colour's indicator, so neighbouring colours share the same sub-pixel edge: no seams, no overlaps.
    (Measured on the reference: 29-30 dB against the lossless drawing, versus 22.5-23 dB for pixel contours + dilation.)"""
    W, H = size
    lab = fill_unlabelled(lm, mask if mask is not None else lm >= 0)
    paths = []
    for k in sorted(range(len(pal)), key=lambda k: -pal[k]["share"]):
        ind = lab == k
        if not ind.any():
            continue
        ys, xs = np.nonzero(ind)
        x0, y0 = max(0, xs.min() - 2), max(0, ys.min() - 2)
        sub = np.pad(ind[y0:ys.max() + 3, x0:xs.max() + 3].astype(np.float32), 1)
        d = []
        for c in find_contours(sub, 0.5):
            pts = np.stack([c[:, 1] - 1 + x0 + 0.5, c[:, 0] - 1 + y0 + 0.5], 1).astype(np.float32)
            ap = cv2.approxPolyDP(pts.reshape(-1, 1, 2), eps, True).reshape(-1, 2)
            if len(ap) >= 3:
                d.append("M" + " L".join(f"{x:.2f} {y:.2f}" for x, y in ap) + " Z")
        if d:
            paths.append(f'<path id="c{k}" fill="{pal[k]["hex"]}" fill-rule="evenodd" d="{" ".join(d)}"/>')
    bg = f'<image href="{bg_name}" x="0" y="0" width="{W}" height="{H}"/>' if bg_name else ""
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">{bg}<g id="character">{"".join(paths)}</g></svg>'


def rasterize(svg, bg):
    png = cairosvg.svg2png(bytestring=svg.encode("utf-8"), output_width=bg.shape[1], output_height=bg.shape[0])
    im = np.asarray(Image.open(io.BytesIO(png)).convert("RGBA"), np.float32) / 255.0
    a = im[..., 3:4]
    return (im[..., :3] * a * 255 + bg.astype(np.float32) * (1 - a)).clip(0, 255).astype(np.uint8)


_G = {}


def _init(work, pal, roles):
    _G.update(work=Path(work), pal=pal, roles=roles, bg=A.rgb(Path(work) / "background.png"))
    sd = Path(work) / "static_dark.png"
    A.STATIC_DARK = (A.rgb(sd)[..., 0] > 127) if sd.exists() else None


def _one(args):
    i, fname = args
    W = _G["work"]
    ref = A.rgb(W / "frames" / fname)
    m = A.char_mask(ref, _G["bg"])
    lm = A.label_map(ref, m, _G["pal"])
    svg = svg_for(lm, _G["pal"], _G["roles"], (ref.shape[1], ref.shape[0]), mask=m)
    (W.parent / "03_redraw" / "svg" / f"{i:05d}.svgz").write_bytes(gzip.compress(svg.encode("utf-8"), 9))
    red = rasterize(svg, _G["bg"])
    m2 = A.char_mask(red, _G["bg"])
    lm2 = A.label_map(red, m2, _G["pal"])
    ys, xs = np.nonzero(m | m2)
    x0, y0, x1, y1 = max(0, xs.min() - 8), max(0, ys.min() - 8), xs.max() + 9, ys.max() + 9
    a, b = ref[y0:y1, x0:x1], red[y0:y1, x0:x1]
    mse = float(((a.astype(np.float64) - b) ** 2).mean())
    u = m | m2
    met = {"i": i, "mask_iou": float((m & m2).sum() / max(1, u.sum())),
           "label_agree": float(((lm == lm2) & u).sum() / max(1, u.sum())),
           "psnr_db": float(10 * np.log10(255 ** 2 / max(mse, 1e-9))),
           "ssim": float(structural_similarity(a, b, channel_axis=2, data_range=255)),
           "delta_e_mean": float(np.sqrt(((rgb2lab(a) - rgb2lab(b)) ** 2).sum(-1))[u[y0:y1, x0:x1]].mean()),
           "svg_bytes": len(svg)}
    diff = np.abs(ref.astype(np.int16) - red.astype(np.int16)).max(2)
    heat = cv2.applyColorMap(np.clip(diff * 4, 0, 255).astype(np.uint8), cv2.COLORMAP_INFERNO)[..., ::-1]
    trio = np.concatenate([ref, red, heat], axis=1)
    return i, met, cv2.resize(trio, (trio.shape[1] // 2, trio.shape[0] // 2), interpolation=cv2.INTER_AREA), red


def redraw(work_dir, workers=8, progress=print):
    work = Path(work_dir)
    out = work.parent / "03_redraw"
    (out / "svg").mkdir(parents=True, exist_ok=True)
    track = json.loads((work / "track.json").read_text(encoding="utf-8"))
    timing = json.loads((work / "timing.json").read_text(encoding="utf-8"))
    fps = timing["fps"]
    jobs = [(f["i"], f["file"]) for f in timing["frames"]]
    W, H = timing["width"], timing["height"]
    enc = lambda path, w, h: subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}", "-r", str(fps), "-i", "-",  # noqa: E731
                                               "-c:v", "libx264", "-preset", "slow", "-crf", "18", "-pix_fmt", "yuv420p", "-color_primaries", "bt709",
                                               "-color_trc", "bt709", "-colorspace", "bt709", "-movflags", "+faststart", str(path)], stdin=subprocess.PIPE)
    p_red = enc(out / "redraw.mp4", W, H)
    p_cmp = enc(out / "compare_ref_redraw_diff.mp4", W * 3 // 2, H // 2)
    mets = []
    with Pool(workers, initializer=_init, initargs=(str(work), track["palette"], track["roles"])) as pool:
        for i, met, trio, red in pool.imap(_one, jobs, chunksize=2):
            mets.append(met)
            p_red.stdin.write(red.tobytes())
            p_cmp.stdin.write(np.ascontiguousarray(trio).tobytes())
            if i % 60 == 0:
                progress(f"redraw {i}/{len(jobs)}")
            if i in (0, 57, 90, 126, 175, 208):
                A.save_rgb(out / f"compare_{i:03d}.png", trio)
    for p in (p_red, p_cmp):
        p.stdin.close()
        p.wait()
    keys = ["mask_iou", "label_agree", "psnr_db", "ssim", "delta_e_mean"]
    summ = {k: {"mean": round(float(np.mean([m[k] for m in mets])), 4), "min": round(float(np.min([m[k] for m in mets])), 4),
                "worst_frame": int(min(mets, key=lambda m: m[k] if k != "delta_e_mean" else -m[k])["i"])} for k in keys}
    res = {"frames": len(mets), "summary": summ, "per_frame": sorted(mets, key=lambda m: m["i"])}
    (out / "redraw_metrics.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    return res
