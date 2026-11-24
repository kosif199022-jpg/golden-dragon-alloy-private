# Fast lane: a cloned dua reel in about 10 minutes

Measured 2026-11-24: the machine part is ~4 min a minute of video on the Higgsfield XL sandbox; the rest
of the old hour was manual measuring and session restarts. This folder removes the manual part.

| Step | Where | Time |
|---|---|---|
| 1. `bash prep.sh URL ~/job` (download, scenes with light/warmth, Whisper words, sheet + captions strip) | sandbox, background | ~2 min |
| 2. Look at `caps.jpg` once, write `spec.json` (lines with Whisper start times, style, header) and `hints.json` (themes per scene) | Claude | ~2 min |
| 3. `python3 pick.py ~/fast/library.json scenes.json hints.json > sel.txt` (library index built once with `index_lib.py`) | sandbox | seconds |
| 4. Render 1 test frame per style element; check | sandbox | ~30 s |
| 5. `bash make.sh ~/job out.mp4 UPLOAD_URL` (frames in parallel, render, veryfast encode, upload in one job) | sandbox XL, background | ~4 min |
| 6. Page with `tools/video-page/video_page.py` and publish | local | ~1 min |

Styles in `web/main.js` (measured to the pixel): `dxh` (Amiri line 498x93 at y 910, «صباح الخير» sticker,
spaced caps handle) and `day` (day / date / Hijri header, Sultan line 699x94 at y 914, italic handle).
`blacklist.txt` lists clips that failed a check; add to it whenever a clip is replaced.
Poll the sandbox with `sleep 30` at most (60 s tool limit). Fonts come from the Red Rose font library.
