# 🌹 V29 — evidence & media intelligence director

## What the 10 uploaded sources contributed

The 10 latest attachments were inspected locally and their SHA-256 fingerprints, inventory sizes, intended contribution and exclusions recorded in `SOURCE_INTELLIGENCE_AUDIT_V29.json`. The nested `skills-library(2).zip` contains eight more skill bundles, overlapping some of the standalone attachments. The Figma .fig is a binary container, not automatically converted into editable layers; the 468-page `Thinking, Fast and Slow` book contributed general decision-science concepts only, not its protected prose.

**New native self-contained module:** `intelligence_director_v29.py`, exposed as `intelligence.director` (read-only), with three whitelisted, original-code operations:

1. **`decision_review`**: compare 2–8 declared choices, shrink high success claims toward declared base rates where evidence is weak, flag missing baselines, reversibility, high downside, overconfidence; expose results as assumptions-based estimates with human review for high stakes or irreversible choices. It is not a statistical model, a new LLM or an automated authorization.
2. **`storyboard_plan`**: editable 2–12 beat reel/short/product/storyboard with exact frame budgets and contiguous shot boundaries; styles `faceless/reel/saas/toon/3d/clay/editorial/map`, aspect presets, captions preserved as complete Arabic words, missing voice-alignment evidence and rights review flags. Does **not** produce MP4 or claim to align phonemes.
3. **`layout_audit`**: deterministic row/column allocation, RTL placement and overflow warnings. It does **not** parse Figma binary nodes or export Figma editable layers.

## Commands (read-only by default)

```bash
cd red-rose
python rose.py capability-run intelligence.director '{"op":"decision_review","params":{"goal":"Select reel production pipeline","options":[{"id":"unverified","benefit":10,"risk":5,"cost":2,"reversible":0.5,"estimated_success":0.95,"base_rate":0.3,"evidence":[]},{"id":"tested","benefit":8,"risk":1,"cost":2,"reversible":0.9,"estimated_success":0.8,"base_rate":0.75,"evidence":["verified","reviewed"]}]}}'
python rose.py capability-run intelligence.director '{"op":"storyboard_plan","params":{"goal":"إعلان قصير","seconds":12,"fps":24,"style":"saas","aspect":"9:16","language":"ar"}}'
python rose.py capability-run intelligence.director '{"op":"layout_audit","params":{"width":1080,"height":1920,"direction":"column","rtl":true,"items":[{"id":"title","min_size":150},{"id":"hero","min_size":800,"weight":3},{"id":"cta","min_size":180}]}}'
python -W error::ResourceWarning -m unittest discover -q
```

## Actual status and boundaries

- New adapter target: **60**, up from 59 on V28 `main`.
- Tests: `test_intelligence_director_v29.py` (14 tests) + `test_intelligence_adapter_v29.py` (4 integration tests). Run CI and report actual results on this feature commit, do not treat numbers here as results.
- Previous V27–V28 eight adapters stay `CODED_UNTESTED`; V29 does not certify them.
- The V26 claim of 1,398/1,400 relates to limited tested roadmap operations, **not** broad equivalence with all source engines or semantic video intelligence.
- No source archive, copyrighted prose, fonts, proprietary keys or private memory data uploaded to GitHub; only original function code, tests and SHA-level source ledger.
- Next meaningful work: use the existing renderer with an **approved** storyboard to produce a verified sample; test and repair the 8 older `CODED_UNTESTED` adapters on real inputs; add human scorecard and regression samples before claiming improvement in artistic quality.
