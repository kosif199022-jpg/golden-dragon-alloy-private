# 🌹 V43 — Abu Cap Reel + App Super Mind (measured, independent distillation)

## Sources actually inspected

- **ريل أبو كاب.rar**, SHA256 `4e44d032…`, 162,010,677 bytes, **688 entries**. The source contains a 22-second 30-fps SVG/JS scene with named characters, two lions, a ladder, tree, motion keyframes, original video/image frame outputs, a caption and a music credit. The source's `work/render.py` used Chromium/Playwright to seek exact time and capture 660 frames. Its actual JPGs/MP4s/music/font are **not** uploaded in this commit.
- **app-super-mind.skill**, SHA256 `0007ab74…`, 102,446 bytes, **22 ZIP entries**. Actual `SKILL.md`, ladder, organ definitions, original brain/eval scripts and reference guides were inspected. This is the nine-stage **افهم → أرّض → قِس → اختار → صمّم → اكسر → ابنِ → أثبت → علّم وسلّم** approach, with a 12-organ rubric and before/after held-out tests. Original executable scripts are not imported or called.
- Full filenames, source hashes, selected methods and excluded media are listed in `FUSION_PROVENANCE_V43.json`.

## New native read-only adapter: `reel.motion`

```bash
cd red-rose
python rose.py capability-run reel.motion '{"op":"story","params":{}}'
python rose.py capability-run reel.motion '{"op":"pose","params":{"seconds":11.5}}'
python rose.py capability-run reel.motion '{"op":"svg","params":{"seconds":14.8,"caption":"الذكاء أفضل من الارتفاع"}}'
```

Returns the story's **eight contiguous narrative beats**, exact 22s/30fps/660-frame count, interpolated positions and lion/ladder states at a requested time, or a **new original simplified SVG frame**. Full video/audio are **not** rendered by this adapter. The frame is not a pixel copy of the owner's original frame or a full recreation of the 22s reel. Frames from the uploaded RAR are reference data, not bundled runtime dependencies.

## New native read-only adapter: `mind.audit`

```bash
python rose.py capability-run mind.audit '{"op":"ladder","params":{"mode":"normal"}}'
```

- `ladder`: checks sequential nine-step **declared** artifacts/evidence and stops claimed completion if earlier gates are missing. `fast/normal/deep` modes; deep flags need an independent critic and repeat evaluation. No external disk/file validation is implied.
- `organ_audit`: expects scores and evidence metadata for exactly 12 organs: `intent,context,memory,planning,action,grounding,verification,calibration,safety,learning,measurement,resilience`. Scores 0–4 or bounded `na`; four critical organs can't be `na`, and scores 3+ without evidence are flagged.
- `paired_compare`: accepts **the same held-out case IDs, immutable SHA256 case fingerprints, and distinct system SHAs** from before/after measurements. Computes Wilson 95% success intervals, exact paired McNemar p and unsafe regressions; requires 30+ cases, all six categories, no unsafe regression, no run errors, and p below .05 for a positive **candidate**. This is NOT a measured test unless the caller's run logs are genuine and separately verified.

The app-super-mind concept of learning from corrections would need a **verified persistent feedback adapter** and before/after replay. V43 doesn't automatically modify Claude, train models, enable autonomous actions or overwrite source code. It can integrate with existing `learning.record` only when a real verified execution receipt and approval are supplied; that connection is outside the new adapter's scope.

## Test and safety contract

```bash
python -W error::ResourceWarning -m unittest test_fusion_v43 -v
python -W error::ResourceWarning -m unittest discover -q
```

Expected: 15 targeted tests plus 2 native registry actions, no imports from original RAR/SKILL, no network, personal memory and uploads excluded from Git. Source assets including third-party music credit are not relicensed; the original caption credits **Happy Ukulele** / Jason Shaw (CC BY 3.0). This release provides new original code and audit evidence, **not full feature equivalence** with either imported source.

**Known outstanding baseline:** On V42 `main`, the held-out router abstention recall fell below its existing floor; do not lower the threshold, relabel held-out data or claim that V43 resolves this unrelated failure. Need fresh hidden-set evidence to fix routing correctly.
