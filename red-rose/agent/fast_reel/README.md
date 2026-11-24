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
spaced caps handle), `day` (day / date / Hijri header, Sultan line 699x94 at y 914, italic handle) and `adeiat`
(measured 2026-11-24 on the @adeiat129 Tuesday reel: gold Panorama Hijri date between two drawn arabesque medallions,
Amiri sub-line and year; Panorama day 350 wide at x 580-930 over a Tajawal Medium date 24|11|2026; Almarai ExtraBold
line 458x54 at y 943 that pops in (scale 0.72 to 1) and is erased from its end; single words marked `"big"` drawn
1.75x; a hatched blue brush ribbon at y 1065-1133 with «دعاء يوم ...» in Kufam with a navy edge; 0.6 s crossfades
via `"xf"` on a scene). Fonts for it: Almarai-ExtraBold, Tajawal-Medium and Kufam (Google Fonts, OFL) beside the others.
`ONLY="30,165,660" bash make.sh ...` renders just those test frames into WORKDIR/test (about 10 s) before the full run.
`blacklist.txt` lists clips that failed a check; add to it whenever a clip is replaced.
Poll the sandbox with `sleep 30` at most (60 s tool limit). Fonts come from the Red Rose font library.
