# 🌹 Capability ledger — V19

| Adapter | Effect | Local implementation | Test evidence |
|---|---|---|---|
| `video.shot_quality` | read | FFmpeg gray 96×54 samples → per-shot Laplacian detail, luma mean, crushed/blown fractions, luma std-dev, inter-frame motion; explainable weighted score; bounded EDL proposal | `test_shot_quality_v19.py` (10 tests) |
| `video.recut` (V16) | approved write | unchanged; consumes the V19 EDL only with `--approve-write` | `test_shot_quality_v19.test_proposal_feeds_approval_gated_recut` |

Total: **17 registered native adapters** (V18 added `qa.trace`, V19 adds `video.shot_quality`), not 17 autonomous agents. Imported knowledge summaries are still not executable capabilities.

## Measured evidence (exact commit in PR)

- Full suite: **182/182** passed, `python -W error::ResourceWarning -m unittest discover` (Windows 11, Python 3.12.10, FFmpeg 9.0.2). Baseline: 164 on `fbf22d2`, plus 8 V18 `qa.trace` tests from PR #15; this change adds 10.
- Synthetic fixture with 4 one-second shots: moving `testsrc2` → score 0.954, no flags; near-black → `underexposed, low_detail, low_contrast, static`, score 0.036; Gaussian-blurred bars → `low_detail, static`, score 0.464; white → `overexposed …`, score 0.0. Default proposal (`min_score` 0.5) = only shot 1 (0–1 s).
- Same content sharp vs. `gblur=sigma=6`: Laplacian detail differs by more than 3×.
- End-to-end CLI: `shot-quality` → EDL `[{"start":0.0,"end":1.0}]` → `recut` refused without approval → with `--approve-write` produced H.264 160×96, 12 fps, 12 frames, 1.0 s, QA passed; extracted frame visually inspected and shows the detailed test pattern, not the black/white/blurred shots.
- Runtime: 120 s 1280×720 source analyzed in 8.4 s → roughly 42 s at the 600 s source limit.

## Not claimed

No blur-vs-flat-subject separation, no face/subject detection, no composition or aesthetic grading, no camera-shake estimate, no semantic or story understanding, no automatic edit. Thresholds were not calibrated on real footage. The full 1,400 requirements are not implemented.
