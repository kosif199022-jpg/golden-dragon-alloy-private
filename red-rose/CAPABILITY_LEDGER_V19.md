# 🌹 V19 — measured per-shot technical quality (read only)

Handoff item addressed: **P3** in `NEXT_AGENT_HANDOFF.md` ("تقييم فعلي للقطات وربط الصوت بالصورة؛ الإخراج EDL قابل للمراجعة").

## Adapter record

| Field | Value |
|---|---|
| name | `video.shot_score` |
| effect | `read` (no file is created, changed or deleted) |
| dependency | `ffmpeg` + `ffprobe`; standard library only, no new Python package |
| module / entry | `shot_quality_v19.score_shots` |
| CLI | `python rose.py shot-score VIDEO [--max-clips N] [--max-duration S] [--sample-fps F]` |
| parameters | `source` (required), `max_clips`, `max_duration`, `threshold`, `sample_fps`, `noise_db`, `min_silence`; anything else is rejected |
| permissions | local file under 2 GB and 600 s, one video stream; URLs rejected (inherited from `probe_source`) |
| test file | `test_shot_quality_v19.py` (13 tests) |
| output | JSON: per-shot measurements, flags, score parts, ranking, rejected shots, `suggested_edl` |

## What is measured

The source is decoded once to a 64x36 grayscale proxy at `sample_fps`. For each shot found by the V16 cut heuristic:

- `mean_luma`, `crushed_black_fraction` (luma < 16), `blown_white_fraction` (luma > 239)
- `detail`: mean absolute luma difference between neighbouring proxy pixels
- `motion` and `motion_jitter`: mean and spread of frame-to-frame change inside the shot
- `audible_fraction`: joined from the V17 acoustic-silence timeline

Flags: `too_dark`, `too_bright`, `clipped`, `low_detail`, `static`, `high_motion`. Only the first three exclude a shot from the proposal. The score is a published weighted sum (exposure .35, detail .25, motion .15, audio .25; picture-only weights when the source has no audio) and every part is returned so the ranking can be audited.

## Measured evidence (local working tree on base `5ce29c3`)

- Full suite: **185 tests passed** (172 before this change + 13 new), Windows 11, Python 3.12.10, FFmpeg 9.0.2.
- Synthetic 6 s source, four 1.5 s shots (test pattern with tone, near black, flat gray with tone, white):

| shot | mean_luma | detail | motion | audible | score | flags |
|---|---:|---:|---:|---:|---:|---|
| 1 pattern | 0.420 | 0.0427 | 0.0363 | 0.975 | 0.920 | none |
| 2 black | 0.019 | 0.0011 | 0 | 0 | 0.010 | too_dark, clipped, low_detail, static |
| 3 gray | 0.502 | 0 | 0 | 0.929 | 0.581 | low_detail, static |
| 4 white | 1.000 | 0 | 0 | 0 | 0 | too_bright, clipped, low_detail, static |

  Ranking `[1, 3, 2, 4]`; proposal with `--max-clips 2` = `0–1.5 s` and `3–4.5 s` (3.0 s). The proposal was then exported through `recut` in a test and verified by FFprobe/full decode; `video.recut` without approval returned `approval_required`.
- Timing: a 60 s 1280x720 30 fps source was analysed in about 4 s wall time (360 proxy frames).
- Read-only check: source SHA-256 and directory listing identical before and after analysis.

## Known limitations

- A 64x36 proxy cannot measure focus or fine sharpness; `detail` is coarse edge energy and is ranked **relative to the same source**, so scores are not comparable between videos.
- No composition, face, subject, story or dialogue understanding. A flat title card with speech can outrank a good-looking silent shot.
- Shot boundaries inherit V16 false positives (flashes, fast motion) and V17 limits (quiet is not "no speech").
- Thresholds are fixed constants in `LIMITS`; they were chosen by reasoning and synthetic footage, **not tuned on real camera footage**. No real user footage was used.
- Not yet run in GitHub CI and not merged; see `RELEASE_MANIFEST_V19.json`.
