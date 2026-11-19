---
name: black-dragon-cinema
description: التنين الأسود — سينما الفوتيج. Turn real footage (reels, news clips, phone videos) plus a song into cinematic 9:16 motion-graphics films, not explainer videos. Arabic kinetic typography (Ruqaa/Cairo/Amiri gold), words that light up with the speaker's own voice, beat-synced cuts, shape-morph transitions, logo/burned-subtitle removal, song ducking under voice, frame-exact canvas render, measured delivery. Use for «مونتاج سينمائي»، «موشن جرافيك احترافي من فيديوهات»، «فيلم تكريم/احتفال/بطل»، «ريلز بأغنية وطنية»، tribute films, celebration films, hero/achievement reels, or any request to make several different professional films from downloaded clips and music. It is also the Black Dragon's front door to every other skill on this machine (243-skill atlas, 21 dragon modules, 5,800+ superpowers): use it whenever the user says «التنين الأسود» for any creative or media task.
---

# Black Dragon Cinema — سينما الفوتيج

A proven pipeline (first used for three films about Mayar Othman, winner of the Arab Reading Challenge 2026) that turns real clips and a song into
**cinematic** films: one story, few strong words, picture + music + motion do the telling. Never a lesson, never «الفصل الأول».

Everything runs locally: FFmpeg, faster-whisper, librosa, Chromium (Playwright) via `kosif-tool/tools/render_html.cjs`.

## ⚡ The dragon holds every skill — قدرات كل المهارات وأفكارها
This skill is a front door, not a silo. For any part of a job it may call **any** skill on the machine:
| Layer | Size | How to reach it |
|---|---|---|
| Skill atlas (installed + 21 Black Dragon modules + kosif-tool + skills inside downloaded repos) | 243 skills | `references/SKILL_ATLAS.md` (regenerate: `python scripts/skill_atlas.py`) |
| Black Dragon router + Dragon Mind + Black Dragon planner | 21 modules, 26 faculties, 7,400+ sources | `dragon.py route / cycle / think / plan` |
| Superpowers catalog | 5,800+ powers, runnable tools with commands | `hub.py find "<task>"`, `micro_index.py find "<words>"` |
| kosif-skills-atlas / kosif-superskills-library | 335 + 114 sub-skills | through `dragon.py route` (their index routes inside) |
| External montage skills (video-use, cut-as-code, hyperframes, Remotion, ffmpeg-skill, rea-video, autoclip, OpenMontage…) | in the atlas | `montage-repos-hub` skill lists task → SKILL.md |

**How to use it on a job:** (1) `dragon.py cycle "<brief>"` → read `DRAGON.md`; (2) grep `references/SKILL_ATLAS.md` for the sub-task
(e.g. "captions", "B-roll", "3D", "color", "voice", "hook") and open the 1–3 best SKILL.md files; (3) take their *ideas* and tools into this
pipeline (the spec, engine and build stay the backbone); (4) say in the report which skills were really used (opened + executed), separately
from ones only consulted. Proven ideas already merged here: shape-morph transitions, push-in-only camera, word-by-word blur rise, payoff
word in gold, one light source (saas-animation); word-lit spoken lines, ≤5-word units, 0.3 s/word, 2 s hook (Superpowers TYPE-17, ARAB-18,
QA-182); render → review stills → fix → render (kosif-web-film / dragon montage); measure before claiming done (dragon verify).
Best tool per job (from `CLAUDE.md`): Blender for 3D/product light, Upscayl/Real-ESRGAN for upscaling, RIFE for slow motion, SAM2/rembg for
masks, whisperX/faster-whisper for timing, demucs for stems, DeepFilterNet for noise, VMAF/LUFS for QA.

## 0. Before anything
1. Read the montage folder's `CLAUDE.md` (quality-first rules, best tool per job, cinematic not educational).
2. `python "C:\Users\cinde\.claude\skills\kosif-black-dragon-ultra\scripts\dragon.py" doctor` once per session; for a big brief run
   `dragon.py cycle "<brief>"` and harvest its powers (TYPE-17 word-lit lines, ARAB-18 ≤5-word meaning units, QA-182 ~0.3 s/word, hook in 2 s).
3. **Check for other Claude sessions** (`ListAgents`) and files changed in the last hours in `05_output`. If another session works on the same job,
   message it, split folders, never write into its folder. (A peer once built code-drawn films in `05_output\mayar` while this pipeline used `mayar_cinema`.)
4. Ask only what changes the result: who/what the film is about, where the music comes from (rights!), publish vs personal, aspect ratio.
   Personal/gift use allows the subject's real news clips and famous songs; for publishing use licensed/original music (Suno with the user's yes).

## 1. Intake (know every second of the footage)
| Step | Command | Why |
|---|---|---|
| Download clips (best quality, resumable, IDM-style parallel) | `python scripts/fast_dl.py URL ... --out <refs>` or `yt-dlp -a links.txt --write-info-json -o "%(extractor)s_%(id)s.%(ext)s"` | `.info.json` gives uploader + caption = what each clip is |
| Probe | `ffprobe` duration / size / fps per clip | 16:9 vs 9:16 decides the crop |
| Timestamped contact sheets | `python scripts/sheets.py <id> <id> ...` (24 tiles, time on each) | look before choosing; then 0.5 s sheets on the key moments |
| Cleanest source first | prefer official 1080p (e.g. a presidency upload) with no channel bugs or burned captions | quality rule |

Write down the **hero moments with exact seconds** (e.g. the name is called at 2.5 s, she prostrates 3.5–6 s, kneels crying 6.5–12 s).

## 2. Music map
- Convert to WAV first (`ffmpeg -i song.m4a -ac 2 -ar 48000 song.wav`): librosa/soundfile cannot read m4a.
- `python scripts/song_map.py song.wav` → tempo, beat list (`.beats.json`), loudness per 5 s.
- `python scripts/lyrics.py song.wav` → sung lines with times (faster-whisper `small`). Find where the vocal/chorus starts.
- **Align the song so a meaningful line lands on the hero moment**: `start = line_time - film_time_of_moment`
  (e.g. «أحلف بسماها» at 33.4 s → start 22.4 so it hits the name reveal at 11.0 s; chorus «مصر هي أمي» on the announcement flash).
- Live recordings have long intros: never assume the first seconds are singing.
- Cut points: take them from the beat list; fast films cut every 2 beats, emotional ones every 4–8.

## 3. Three films must really differ
Different story spine, rhythm and music per film, e.g.:
| | A «واحدة من ٤٠ مليون» | B «بنت النيل» | C «لحظة الإعلان» |
|---|---|---|---|
| Spine | sea of 40M gold points converges to one light → her | her own voice reciting, words light up gold | suspense → name called → explosion of joy |
| Rhythm | slow funnel then release | breathing, voice-led | beat cuts every 2 beats |
| Hook (≤2 s) | Arabic counter to ٤٠٬٠٠٠٬٠٠٠ | her face + first spoken words | stage waiting, «٤٠ مليون حلم» |
Only verified facts on screen (from news). Quote a person only when they are heard saying it in the footage.

## 4. Film spec → `<work>/films/<name>.json`
Start from `templates/` (epic counter / voice karaoke / beat cut). Shot fields:
`src` (clip id substring), `in` (s), `d` (s), `speed`, `crop {z, cx, cy}` (9:16 window: zoom and position 0–1, works for 16:9 and 9:16 sources),
`lut` (from `_kit/LUTs`, e.g. `01_Cinematic`, `03_GoldenHour` for palace interiors), `grade` (ffmpeg eq), `kb {s0,s1,x0,x1,y0,y1}` (camera),
`delogo [[x,y,w,h], ...]` (source fractions: channel bugs, burned subtitles), `tr {type: cut|iris|zoom|flag, d, flood}`.
Generated scenes: `{"type":"stars","converge":true,...}`, `{"type":"end"}`, `{"type":"black"}`.
Texts: `anim` = `rise` (word by word blur→sharp, small rise, leaves the same way) · `stamp` (quick rise on a beat) · `big` (payoff word, slow settle) ·
`counter` (Arabic-Indic digits) · `karaoke` (`words:[{w,s}]` light up gold at the exact spoken times) · `wipe`; plus `font` (ruqaa, cairo, cairo7,
amiri, messiri, tajawal, kufi, serif), `size`, `y`, `gold`, `glow`, `scrim`, `out:false` for end cards.
Audio: `{"song","start","fadeIn","fadeOut","voices":[{"src","in","d","at","gain"}]}` → the song **ducks under the voice** (sidechain) and the mix is
loudness-normalised to −14 LUFS. Keep `voice.at` == the shot's start and `voice.in` == the shot's `in` for lip sync.

## 5. Style rules (from saas-animation + this job)
- No cross-dissolves, no light-leak packs: **iris shape-morph** (disc grows from the centre carrying the next shot), beat cuts, flag wipe, cross-zoom.
  `python scripts/apply_style.py <name>` converts a draft spec automatically.
- Camera **always pushes in** across consecutive shots; never in-then-out. Subject dead centre.
- Text ≤5 words per unit, one payoff word in gold Ruqaa per moment; white Cairo/Messiri for facts; scrim behind text on bright footage.
- **Reels safe zone**: no text below y≈0.74 (TikTok/Reels UI); top band 0.18–0.3 is safe.
- Glow only on gold payoff words. Grain 0.05, vignette 0.5, film edges fade from/to black.
- End card: centred, still, name + one short line in the person's own words.

## 6. Review, then render
```
set BDC_WORK=C:\Users\cinde\bdc_work            (ASCII path, outside OneDrive)
python scripts/build.py <name> --stills 1.5,4.2,7.5,12,...   → <work>/out/<name>_stills/stills_grid.png  (LOOK at it)
python scripts/build.py <name> --skip-extract                 → <deliver>/<title>.mp4
python "...\dragon.py" verify "<deliver>/<title>.mp4"           → duration, 1080x1920 h264, LUFS
```
Fix what the stills show (bad crop, overlap, low contrast, logos) before the full render. Delete only the changed shot folders
(`shots/<name>_NN`) and rerun with `--skip-extract`. Render ≈1–2 fps on CPU: ~20 min for 46 s; wait with background tasks, never sleep-loops.
Final check: a 2-second contact sheet of the MP4 and `dragon.py verify`. Then `dragon.py learn "<brief>" --modules black-dragon-cinema --result passed|failed`.

## 7. Lessons (do not repeat)
- Chromium blocks `FontFace(url(file://...))` → fonts are embedded as base64 (`fonts.js`, generated once).
- faster-whisper + this PyAV build fails on file paths (`metadata_errors`) → pass a 16 kHz numpy array (`lyrics.py` does).
- `python -I` ignores `PYTHONIOENCODING` → scripts call `sys.stdout.reconfigure(encoding="utf-8")` (Arabic paths).
- Stars converging to one point summed into a white block → fade points with (1−converge)² and skip invisible ones.
- Wrong crops are the #1 defect: always check people's positions per second in 16:9 sources before choosing `cx`.
- Rapid repeated downloads from Wikimedia → HTTP 429; many-connection downloads get refused → `fast_dl.py` retries gently and restarts the file.
- A stopped background render can leave Node/Chrome alive → kill only the process tree whose command line names your film.
- Keep frames out of OneDrive; never touch another session's folders or music files.
- `winget` sometimes fails with a generic error in batches → retry one by one later; do not block the creative work on it.
