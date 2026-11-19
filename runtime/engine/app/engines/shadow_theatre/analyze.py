"""Measure a reference shadow-theatre video: camera cuts, lit-screen palette, silhouette share, edge softness."""
from __future__ import annotations

import json
import math
import subprocess
from pathlib import Path

import numpy as np

from ..media import exe, probe


def _frame(src, t, w=320, h=180):
    raw = subprocess.run([exe("ffmpeg"), "-v", "error", "-ss", str(t), "-i", str(src), "-frames:v", "1", "-vf", f"scale={w}:{h}",
                          "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(h, w, 3).astype(np.float32) if len(raw) >= w * h * 3 else None


def _sample(f, t) -> dict:
    lum = f.mean(2)
    lit = lum > 60  # the projected screen
    dark_inside = (lum < 35)[30:150, 50:270]
    bright = f[lit]
    gy, gx = np.gradient(lum)
    g = np.hypot(gx, gy)
    edges = g[g > 25]
    return {  # a silhouette shot = a large bright screen whose middle has hard dark regions
        "t": t, "shadow_shot": bool(lit.mean() > 0.25 and 0.04 < dark_inside.mean() < 0.75),
        "lit_share": round(float(lit.mean()), 3), "silhouette_share": round(float(dark_inside.mean()), 3),
        "screen_rgb_top": [int(v) for v in f[20:60, 120:200].reshape(-1, 3).mean(0)],
        "screen_rgb_mid": [int(v) for v in f[80:110, 120:200].reshape(-1, 3).mean(0)],
        "screen_mean_rgb": [int(v) for v in bright.mean(0)] if bright.size else None,
        "edge_strength": round(float(edges.mean()), 1) if edges.size else 0.0,
    }


def analyze(video, out, samples: int = 60, threshold: float = 0.35) -> dict:
    src, out = Path(video), Path(out)
    out.mkdir(parents=True, exist_ok=True)
    dur = float(probe(src)["format"]["duration"])
    r = subprocess.run([exe("ffmpeg"), "-hide_banner", "-i", str(src), "-an", "-vf",
                        f"scale=320:-2,select='gt(scene,{threshold})',showinfo", "-f", "null", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    cuts = [round(float(x.split("pts_time:")[1].split()[0]), 2) for x in r.stderr.splitlines() if "pts_time:" in x]
    step = max(0.5, dur / samples)
    times = [round(i * step, 2) for i in range(int(dur / step))]
    rows = [_sample(f, t) for t in times if (f := _frame(src, t)) is not None]
    shadow = [s for s in rows if s["shadow_shot"]]
    summary = {
        "schema": "kosif.shadow-theatre.analysis.v1", "source": src.name, "duration_s": round(dur, 2),
        "camera_cuts": cuts, "samples": len(rows), "shadow_shot_share": round(len(shadow) / max(1, len(rows)), 3),
        "mean_silhouette_share": round(float(np.mean([s["silhouette_share"] for s in shadow])), 3) if shadow else None,
        "palette_top": [s["screen_rgb_top"] for s in shadow][:: max(1, len(shadow) // 8)],
        "notes": "cuts are camera/edit cuts; inside the act the picture changes by morph, blackout and iris, not by cuts",
    }
    (out / "analysis.json").write_text(json.dumps({"summary": summary, "samples": rows}, indent=2), encoding="utf-8")
    cols = 6
    rows_n = math.ceil(min(36, len(times)) / cols)
    every = max(1.0, dur / (cols * rows_n))
    subprocess.run([exe("ffmpeg"), "-v", "error", "-y", "-i", str(src), "-vf", f"fps=1/{every:.3f},scale=320:-2,tile={cols}x{rows_n}",
                    "-frames:v", "1", str(out / "contact.jpg")], check=False)
    return summary
