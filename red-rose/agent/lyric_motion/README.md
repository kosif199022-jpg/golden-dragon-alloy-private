# Lyric motion reel (موشن جرافيك لكلمات أغنية)

Made and checked on 2026-11-23 for an Elissa song (44.9 s, 16 lines): one Pinterest scene per sung line,
Aref Ruqaa words that rise in with a blur and glow gold while sung, falling rose petals with bursts on the
strong lines, soft cinema bars on the chorus, a warm soft-light grade, light-leak, whip, spin, zoom and
slide transitions placed 0.12 s before each line, -14 LUFS master.

## Steps
1. **Lyrics and times.** Whisper garbles singing. Take one frame per caption change from the reference
   video and read the words; take only the line start/end times from Whisper or by ear. Put them in
   `song.json` (see `song.example.json`).
2. **One scene per line.** Search Pinterest per idea of the line (`rose.py social` or SOCIAL_FETCH.md:
   «rain window aesthetic video», «old door closing», «vintage key», «couple dancing silhouette sunset»…),
   make a labelled contact sheet with `../reel_analyzer/label_sheets.py`, choose by meaning and keep one
   palette (warm sunset/candle worked).
3. **Check every chosen clip across its full length for logos, watermarks and burnt-in text** (one frame
   every 0.7 s on a strip). A clip that looked clean at the start ended on a bakery logo in the first cut.
4. `python3 build.py song.json` (needs network to the clip links; run it in the Higgsfield sandbox).
5. Copy `ArefRuqaa-Bold.ttf` and `Montserrat.ttf` to `web/fonts/` (Red Rose font library).
6. `bash make.sh song.json out.mp4 4` — Playwright renders 1080x1920 frames (about 1 s a frame on 4 CPUs),
   resumable after the 15-minute sandbox limit; then ffmpeg encodes with the song.
7. Verify: one frame every 0.5 s on a sheet (meaning per line, no logos), loudness -14 LUFS, then deliver
   with `tools/video-page/video_page.py` of the Golden Dragon.

To swap one scene later: change that clip in song.json, run build.py, delete only the frames from
(line start - 0.3 s) to (next line start + 0.3 s) and run make.sh again: only those frames are rendered.

The song and the Pinterest clips belong to their owners: private drafts, or publish with TikTok's own
sound and footage you may use.
