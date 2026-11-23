# 🌹 Red Rose V44 — reviewable reel rhythm and evidence-linked learning

**Branch:** `feature/red-rose-v44-quality-feedback-20261123` (stacked on the unmerged V43 source-fusion branch). These are independent original stdlib operations inside the **existing** `intelligence.fusion` native Red Rose adapter; no legacy Golden Dragon runtime is imported, and no second skill is required at runtime.

## What is implemented

### `intelligence.fusion.reel_rhythm` — read-only
Input: `{"project": <V43 reel_preflight project>, "caption_cps_limit": 22, "minimum_cta_frames": 30}`.

Calls the existing strict V43 `reel_preflight` contract; reports frame-derived start/duration timestamps, codepoint caption density, CTA hold review and actor re-entry review flags. Checks are **heuristics for editorial review**, not pixel inspection, dialogue comprehension, or proof of 3D rendering. Gaps, wrong aspect ratio, missing music credit and unknown source scripts remain rejected/warned by V43.

### `intelligence.fusion.feedback_cycle` — read-only
Input:
```json
{
  "task": "Improve Arabic reel export",
  "observations": [
    {
      "id": "audio-sync-01", "category": "audio", "severity": "high",
      "recurrences": 2, "summary": "The output drifts from the supplied audio",
      "reproduced": true, "evidence_sha": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    }
  ],
  "max_proposals": 10
}
```

Accepted categories: `routing`, `timing`, `caption`, `identity`, `audio`, `export`, `safety`, `general`. Output ranks a bounded correction queue deterministically and proposes regression targets. Each `reproduced=true` item must provide a 64-hex SHA256 evidence identifier; the user-provided hash and claimed reproduction are **not independently verified**.

**The module never saves, retrains, changes production rules, edits video, runs external commands, or contacts the network.** After independent validation and explicit owner approval, the pre-existing **local-only** `learning.record` operation may persist a reviewed lesson on the owner PC. Private memory is never committed to GitHub.

## CLI

```powershell
cd red-rose
python -X utf8 rose.py ops intelligence.fusion
python -X utf8 rose.py describe intelligence.fusion.reel_rhythm
python -X utf8 rose.py run intelligence.fusion.reel_rhythm --params-file .\v44_rhythm_input.json
python -X utf8 rose.py run intelligence.fusion.feedback_cycle --params-file .\v44_feedback_input.json
python -W error::ResourceWarning -m unittest test_intelligence_fusion_v43 test_intelligence_bridge_v43 test_quality_feedback_v44 -v
python -W error::ResourceWarning -m unittest discover -v
```

`v44_rhythm_input.json` and `v44_feedback_input.json` are illustrative filenames; the first file should wrap the existing V43 project JSON under `project`. Do not pass an arbitrary untrusted script or private credential.

## Catalogue repair

`rose_catalog.load()` now compares **live operation IDs** as well as adapter IDs to the generated JSON and the in-process cache. A new operation within an unchanged adapter is visible immediately without a persistent write.

The **on-disk** `references/OPS_CATALOG.json` and `references/OPS.md` still require regeneration on a checkout with Python installed:

```powershell
python -X utf8 rose.py catalog-build --approve-write
```

Because `test_catalog_v29.py` checks that those checked-in generated files byte-match `build()`, the full suite must not be declared green until regenerated, committed, and CI has passed on the same SHA. Do not weaken that drift guard or fabricate a passing result.

## Next quality gate

1. Regenerate the generated catalogue and Markdown in the local checkout.
2. Run V44 and full suite; resolve any failing legacy tests without lowering quality thresholds.
3. Verify real owner-authorized videos with FFprobe + full decode + visual/audio review before asserting media-quality improvement.
4. Review and merge the V43 base PR first; only merge V44 after its independent review and green CI.

**No raw video/music/font, private memory or source archive has been added.**
