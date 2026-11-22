# 🌹 V30 — Approved storyboard-to-MP4 integration

New native capability **storyboard.pipeline** connects V29 frame-exact creative planning to V20 original illustrated video production. It has only two effects:

| op | effect | result |
|---|---|---|
| compile | read | Validated storyboard + native clay/schematic-map project and exact frames, *no media written* |
| render | write | Original **silent** H264 MP4, FFprobe/full-decode QA, hash receipt; only after explicit owner approval |

## CLI use

From the red-rose directory:

\`\`\`bash
python rose.py capability-run storyboard.pipeline '{"op":"compile","params":{"story":{"goal":"قصة قصيرة","seconds":5,"fps":12,"style":"clay","language":"ar"}}}'
# Inspect the story, captions, visual fidelity, timing and the output destination first.
python rose.py capability-run storyboard.pipeline '{"op":"render","params":{"story":{"goal":"قصة قصيرة","seconds":5,"fps":12,"style":"clay","language":"ar"},"output":"my_new_video.mp4"}}' --approve-write
\`\`\`

The approval flag must be supplied on the **CLI**. Placing \`approve_write\` inside JSON never grants permission. The destination must be a *new* MP4 under an existing directory; the renderer stages the video in a temporary directory, verifies full MP4 decode, and hard-links it to the final path without overwriting. The project JSON is regenerable from the input and the video file itself is **not** a native editable timeline.

### Supported visual fidelity

- \`clay\`: original illustrated 2D clay-style cat, existing V20 renderer.
- \`map\`: original **schematic** map; each beat must have a route key \`"1": {"from":[lon,lat],"to":[lon,lat]}\`. Never mistake it for road navigation or satellite imagery.
- \`toon/reel/faceless/saas/editorial\`: **rejected by default**; only produces a clay illustration if \`allow_illustrative_fallback: true\` is explicitly supplied and the output reports the downgrade.
- \`3d\`: **always rejected**. There is no real 3D renderer behind this adapter.
- Aspect: \`9:16\` (540×960) or \`1:1\` (720×720) only; widescreen \`16:9\` rejected until a native supported renderer is added.
- 5–90 s planning possible in V29, but V30 native render is limited to **360 frames total** and **12 s per scene**, with the underlying V20 budget enforced. No real-audio alignment, external video/images, faceless stock footage, film color grading or TTS here.

### Verification

\`\`\`bash
python -W error::ResourceWarning -m unittest test_storyboard_pipeline_v30 -v
python -W error::ResourceWarning -m unittest discover -q
\`\`\`

**Evidence target:** one 5s 12fps/540×960 original silent H264 MP4, 60 real frames, a verified SHA-256, no source archive calls and no overwrite; original Arabic caption strings preserved across storyboard compilation. GitHub Actions checks must complete successfully on the exact feature head before merge.

This is a **real working bridge**, not a universal integration of the user's uploaded Remotion/Maven/Figma sources or all V27–V28 adapters. Those 8 historically marked \`CODED_UNTESTED\` stay unresolved.
