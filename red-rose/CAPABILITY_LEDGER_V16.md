# 🌹 Red Rose V16 — implemented vs reference knowledge

## New independently tested native adapters

| ID | Effect | Executable behavior | Evidence |
|---|---|---|---|
| `video.scene_analyze` | read | Inspect original local source with FFprobe + sampled RGB frame-change cut heuristic | `test_scene_edit_v16.py`, synthetic input proof; cuts at 1.5s and 3.0s |
| `video.recut` | approved write | Reorder user-selected start/end clips via FFmpeg trim + concat; preserve audio | `test_scene_edit_v16.py`; H264/AAC 3-second 72-frame output verified |

The original 11 V15 native adapters remain registered and tested, for 13 total. Existing `CAPABILITY_LEDGER_V15.md` retains its historical accounting.

## Clear limits

- Scene change detection is not semantic; a camera flash may look like a cut. A gentle dissolve may not register. The timestamp resolution is limited by sample FPS.
- `video.recut` performs hard cuts only. It is not an advanced timeline editor or an AI automatic montage generator.
- No legacy runtime engines are invoked. The private 25,675 record summary catalog remains **reference data** and is not included in this repository.
- V16 is a small, verified step in the 1,400-requirement roadmap, **not** complete skill fusion.
