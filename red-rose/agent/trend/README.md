# «ستايل دعاء الترند» / «دعاء الترند»

The owner's trending dua reel (Facebook, posted 2026-11-23: 151K views, 5.3K reactions, 254 comments, 1.7K shares)
as a reusable style. When he says «ستايل دعاء الترند» or «دعاء الترند», every new dua reel uses this engine
unchanged: same header, fonts, colours, word-by-word lines, transitions, dust, vignette and handle.

What is fixed (from that reel's own engine, `work/dua-tue`):
- Header: day name in Aref Ruqaa Bold 118 px with an ivory-to-gold gradient (x 820, y 232); the date
  `DD . MM . YYYY` in Montserrat 600 40 px (y 312); Hijri day Aref Ruqaa 86 px gold `#e9c77b` and the month
  96 px with a teal-gold-teal gradient (x 255); the Latin line `MONTH · YEAR` Montserrat 600 25 px; a gold
  rule with a diamond at y 360. Fades and drops in over 0.05-0.8 s.
- Lines: Noto Naskh Arabic 700 98 px white, centred at y 1180, words rise 26 px and fade in on their voice
  time, the spoken word glows gold `#ffd98a` then settles, small gold rule under the line.
- One clip per line, cut 0.12 s before the voice; 0.36 s motion-matched transitions cycling
  spin, zoom, light leak, whip, blur-zoom, slide-up; slow push-in per clip; warm soft-light tint per clip.
- Warm dust specks, top and centre vignette, `@elkosif` at the bottom, fade from black at the start.

What changes per reel: `spec.json`:
`{dur, handle, header:{day, date, hday, hmonth, latin}, lines:[[[word, t], ...], ...]}` (word times from Whisper),
and `sel.txt` (one clip per line, absolute paths; warm home footage like the trend: Quran, roses, tea, candles,
tasbih, coffee, living rooms, Madinah).

Make one:
1. `python3 build.py WORKDIR` (cuts the clips into `web/fx`, writes `web/clips.json`).
2. Copy `web/index.html`, `web/main.js`, `spec.json` and the fonts (ArefRuqaa-Bold, NotoNaskhArabic, Montserrat
   variable) into `WORKDIR/web`, then `node ../fast_reel/render.mjs web frames 0-N 4` and mux the voice at -14 LUFS.
First use (2026-11-24): a 19.8 s Tuesday dua from TikTok in this style, built and rendered locally in 34 s.
