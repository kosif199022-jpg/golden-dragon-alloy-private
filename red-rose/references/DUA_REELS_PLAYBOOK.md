# Dua reels, voices and lyric motion: the playbook (what we learned, 2026-11-23)

Read this first when the owner asks for: ريل دعاء، دعاء يوم …، دعاء ليلة الجمعة، دعاء الصباح، زي حساب
oaun / dxhmen، حلل حساب دعاء، أصوات الدعاء، مكتبة الأصوات، مقاطع بنترست للدعاء، موشن جرافيك لأغنية / كلمات أغنية.

Everything here was measured on real accounts, not guessed. Numbers: `agent/dua_style/presets.json`.

## 1. What is ready to use

| Need | Where |
|---|---|
| Two measured dua styles (layout, cuts, camera, transitions, loudness, hashtags, post times) | `agent/dua_style/presets.json`, `references/STYLE_OAUN.md`, `references/STYLE_DXHMEN.md` |
| Dua texts by day and occasion (112 themes) | `rose.py duas day friday`, `rose.py duas show ramadan` |
| The dua reel maker | `rose.py dua-reel plan.json out.mp4 --approve-write` |
| 602 Pinterest clips, @oaun.11 look (roses, Quran, incense, candles) | `rose.py library fetch pins --approve-write`; links in `agent/pins_catalog.csv` |
| 152 Pinterest clips, @dxhmen look (sunset sea, mabkhara, Haramain, camels, flowers) | `rose.py library fetch dxh_pins --approve-write`; git branch `media/dxhmen-pins` |
| 2,126 dua voices sorted by day and occasion (@dxhmen + @oaun.11) | `rose.py library fetch dua_audio --approve-write`; git branch `media/dua-audio`; `agent/dua_audio/dua_audio_catalog.csv` |
| Collect the voices of any other dua account by day | `agent/dua_audio/dua_audio.py list HANDLE` then `fetch_audio.py` in the sandbox |
| Measure any account's reels (shots, camera move, transitions, loudness, words) | `agent/reel_analyzer/analyze.py` |
| Lyric motion for a song (scene per line, word reveals, petals) | `agent/lyric_motion/` |
| Seeing Instagram / TikTok / Pinterest from the cloud | `references/SOCIAL_FETCH.md`, `rose.py social …` (paid, `--approve-spend`) |

## 2. Make a dua reel (the order that works)

1. **Day and occasion.** Friday night (Thursday evening) is the strongest slot: #دعاء_ليلة_الجمعة had
   the best median views (700 k on @dxhmen). Check the real Hijri date (Umm al-Qura) for the header.
2. **Pick the style.**
   - *oaun* (lively): about 7 shots of 3 s, a gentle push-in on every shot, spin, zoom, light-leak or whip
     transitions of 0.36 s, Hijri block top left and the day name top right.
   - *dxhmen* (calm): about 6 shots of 5 s, the camera still (66 %) or a slow zoom-out (19 %), mostly plain cuts
     (79 %) with a flash or blur-move only on the strongest line, a gold calligraphy title top centre.
3. **Text.** `rose.py duas day <day>`: about 9 lines of 2 to 6 words, opening «اللهم في يوم/ليلة/صباح …».
   Never copy their exact texts.
4. **Voice.** The owner's own recording, or a generated voice after his yes. The voice starts on frame 1,
   at about 1.5 to 1.65 words a second. The voice library is for studying tone and pace, **not for publishing**.
5. **Timing.** Whisper word times on the voice; each cut lands **0.12 s before** its line starts (oaun:
   67 % of cuts within 0.4 s of a line).
6. **Footage.** One clip per line or per two lines, from the matching library, warm grade (red above blue).
   Check each clip over its whole length for logos and burnt-in text before using it.
7. **Make it:** `rose.py dua-reel plan.json out.mp4 --approve-write`, then loudness -14 LUFS, AAC, no black
   first frame.
8. **Publish pack:** caption «دعاء يوم <اليوم>» + one dua line + 🌷🌹🌺🌸🤲, five hashtags (the list for the
   style in presets.json), posted 18:00-20:00 UTC (evening in Europe/North Africa, where @dxhmen's
   audience is: France 663 of 757, Algeria 54, Morocco 28).

## 3. Analyse a new account (any platform)

1. List all posts: `rose.py social` or ScrapeCreators `/v3/tiktok/profile/videos` (1 credit per 10) or
   `/v2/instagram/user/posts` (1 per 12). Keep caption, hashtags, region, post time, views, music.
2. Pick the 60 most viewed plus the 60 latest; run `agent/reel_analyzer/analyze.py` in the Higgsfield
   sandbox (XL for Whisper `small`; `base` on 1 CPU). 85 to 114 reels give stable medians.
3. Make a contact sheet of one frame per shot (`label_sheets.py`) and look at it: write the footage themes.
4. Search Pinterest for each theme (`/v1/pinterest/search`, 2 pages = 16 to 20 video pins), download the
   HLS links with ffmpeg `-c copy` in the sandbox, dedupe by md5, write a catalogue CSV with the pin links.
5. Write a style card like `STYLE_DXHMEN.md` and add the numbers to `presets.json`.

## 4. Store big media on GitHub (what worked)

Media goes on its own orphan branch of the private repo (`media/<name>`), never on main: files under
100 MB each, one commit per folder, then push (the proxy's push negotiation warning is harmless). Fetch one
branch alone: `git clone --single-branch -b media/<name> <repo>`. Keep a CDN copy too and register it in
`media_library_v35.py` `KNOWN` with a catalogue CSV, so `rose.py library fetch` works anywhere.

## 5. Song lyric motion

See `agent/lyric_motion/README.md`. Short version: lyrics from the reference's burnt-in captions (Whisper
garbles singing), one Pinterest scene per line chosen by meaning, Aref Ruqaa words that rise in with a blur
and glow gold while sung, falling petals with bursts on strong lines, cinema bars on the chorus, transitions
0.12 s before each line, -14 LUFS.

## 6. Mistakes not to repeat

- A clip chosen from its first frame ended on a **bakery logo**: scan every chosen clip over its full length.
- Shop branding hides on **ribbons, boxes and bags** (a rose bouquet carried «TOGETHER A.R» on its ribbon):
  look at the bottom third of every bouquet/gift clip at full size before using it.
- The first frame must show the picture: no opening fade from black (owner rule 3). Measure it: mean luma of
  frame 0 well above 0.
- A reel «زي المقطع ده» from a dua account: read the exact text from the burnt-in captions (fix their spelling:
  «اجعل» not «أجعل»), take the word times from Whisper on the voice, check the Hijri date in their header.
- Higgsfield sandbox background jobs stop after **15 minutes** (exit 124): make every job resumable and
  restart it; check `nproc`: a replaced sandbox can fall back to **1 CPU** (move heavy work to `size: xl`,
  which needs no other background job running).
- `pkill -f <pattern>` matched the shell that ran it; kill by PID from `ps -eo pid,args` + awk.
- A signed upload URL takes **one** PUT; a 400 or 412 means ask for a new URL.
- Plain yt-dlp fails on TikTok: `yt-dlp[default,curl-cffi]` and `--impersonate chrome`.
- Re-encoding Pinterest clips to 720p did not make them smaller: keep the originals.
- Downloaded reels of other accounts: keep numbers, frames, transcripts; delete the videos.

## V47 — Learning from the owner's VN prayer projects
Use `python rose.py vn-dua-analyze <folder-or-vn-file> --sha256` before selecting an owner reference style. This reads ZIP metadata or known JSON/plist, skips media extraction, counts field candidates and reports explicitly labelled time units. It does not infer unlabelled timing units, store prayer text, confirm final visual quality or change a rendering preset.
Next gate: map real project track schema, identify captions and shots, verify timing on an exported reference video, compare Sunday/Monday/Wednesday separately, then add evidence-backed style entries to presets.json. Preserve the owner's supplied exact words. Do not replace existing measured account styles with unsupported claims.
