"""Tracking accuracy against ground truth (only possible because the reference character was drawn from code):
joint error, occlusion detection, and jitter (frame-to-frame shake the truth does not have)."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np


def joints_vs_gt(track, gt):
    names = sorted(set(gt["frames"][0]["joints"]) & {j for f in track["frames"] for j in f["joints"]})
    out = {}
    for jn in names:
        T = np.array([f["joints"].get(jn, [np.nan, np.nan]) for f in track["frames"]], float)
        G = np.array([g["joints"][jn] for g in gt["frames"]], float)
        src = [f.get("joint_src", {}).get(jn, "measured") for f in track["frames"]]
        e = np.hypot(*(T - G).T)
        ok = ~np.isnan(e)
        meas = ok & np.array([s == "measured" for s in src])
        acc_t = np.diff(T[ok], 2, axis=0)
        acc_g = np.diff(G[ok], 2, axis=0)
        jit = float(np.sqrt(np.mean(np.sum((acc_t - acc_g) ** 2, 1)))) if len(acc_t) else float("nan")
        out[jn] = {"median_px": round(float(np.median(e[ok])), 2), "p95_px": round(float(np.percentile(e[ok], 95)), 2),
                   "max_px": round(float(e[ok].max()), 2), "measured_frames": int(meas.sum()), "interpolated_frames": int((ok & ~meas).sum()),
                   "jitter_rms_px": round(jit, 3)}
    return out


def occlusion(track, gt, part="glove.R", hidden_below=0.1):
    truth = np.array([g["visible"][part] < hidden_below for g in gt["frames"]])
    said = np.array([not f["parts"][part]["visible"] for f in track["frames"]])
    tp, fp, fn = int((truth & said).sum()), int((~truth & said).sum()), int((truth & ~said).sum())
    return {"part": part, "hidden_truth": int(truth.sum()), "hidden_said": int(said.sum()), "tp": tp, "fp": fp, "fn": fn,
            "precision": round(tp / max(1, tp + fp), 3), "recall": round(tp / max(1, tp + fn), 3)}


def report(work_dir, gt_path):
    track = json.loads((Path(work_dir) / "track.json").read_text(encoding="utf-8"))
    gt = json.loads(Path(gt_path).read_text(encoding="utf-8"))
    hu = gt["head_unit_px"]
    J = joints_vs_gt(track, gt)
    allmed = float(np.median([v["median_px"] for v in J.values()]))
    return {"head_unit_px": hu, "joints": J, "all_joints_median_px": round(allmed, 2), "all_joints_median_head_units": round(allmed / hu, 4),
            "occlusion": [occlusion(track, gt, p) for p in ("glove.R", "glove.L")]}
