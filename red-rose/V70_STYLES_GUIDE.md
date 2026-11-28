# V70 motion-graphics style catalogue (2026-11-28)

## What it is
`rose.py styles` turns every motion style Red Rose can reach into one menu, so a request like
«اعمل موشن جرافيك للمقطع ده» starts with the full list of options and lets the owner mix them.
- `styles menu [CLIP] [--need characters,places]`: all styles grouped by family; for a clip it probes size and
  duration (ffprobe, read-only) and marks which styles fit its aspect.
- `styles show ID`: engine, inputs, layers, credit, rights files, doc path, install hash check.
- `styles cocktail a+b+c --seconds S [--fps 30 --aspect 9:16]`: segment cocktail. Whole-frame split, one
  output per segment, then join with `montage-code` and verify with `media-contract verify`.
- `styles cocktail characters=a,places=a,captions=b`: layer cocktail. Characters/places/camera must come from
  one engine (they share one scene); other roles become overlays, which need an alpha render (untested).
Registry: `agent/style_registry_v70.json` (descriptions written by Red Rose). Render evidence:
`agent/style_tests_v70.json`. A style counts as `rendered_ok` only with measured output recorded there.

## Library
`~/.red-rose/libraries/style-packs/` — 16 owner-supplied packs, 1,406 files, 71 MB, `MANIFEST.json` holds a
tree hash per pack (`styles show` re-checks it). Sources: the Telegram export (10 packs inside
`Telegram Desktop.rar`), `ChatExport_2026-11-28 (2)/files` (5 khaam packs) and `maven-3d-v2-skill.zip`.
Scan at intake: no executables or install hooks; three `setup.ps1` (npm install, Playwright Chromium, pip)
and khaam `get-tools.mjs` (fetches ffmpeg-static only when ffmpeg is missing) were read, not run.

## Rights (from each pack's own licence)
Maven packs (@maven.iqq) and Khaam packs (@khaam.hq, Rashed Al-Hazmi): free use on your own devices,
including commercial videos; the videos are yours. Not allowed without the author's written permission:
selling or re-publishing the packs, uploading them to a public place, or presenting them as your own.
So the packs stay in the local library with their rights files untouched and are never published.
`vox-motion` is a prompt guide for paid generators: blocked until the owner approves the tool and price.

## Native Red Rose styles in the same menu
الراجل والست (`agent/couple_motion`), أبو كاب (`agent/abu_cap`), دعاء الترند (`agent/trend`),
ريل الدعاء السريع (`agent/fast_reel`), موشن كلمات الأغنية (`agent/lyric_motion`), mimic (`agent/mimic`).

## Not done yet (honest status)
- No pack engine has been render-tested on this PC: running pack code needs the owner's explicit permission
  (the session's safety check blocked it). Every style shows `not_tested_here` until a sample is rendered.
- Overlay (alpha) compositing between different engines is unverified.
Tests: `test_styles_v70.py` (8).
