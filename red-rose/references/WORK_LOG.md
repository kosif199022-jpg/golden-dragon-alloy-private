# Red Rose work log (what was built with the owner, newest first)

## 2026-11-25
### «وضيئة الوجه» poem with الراجل والست (`characters/el-ragel-wel-sit/lyric_engine`)
Facebook reel audio (1.15M views); 4 verses word-timed, diacritics from the original captions; the 5 saved images reused (no credits); render 34 s locally.

## 2026-11-24
### Red Rose V54 integrated into main
V54 branch (mind v51, SEE native v52/v53, metacognition v54, golden and white native engines) merged with main; router out-of-scope cues for publishing, calls/complaints and certified translation: test abstention recall 0.5 -> 1.0, top-1 0.3625 -> 0.40, top-3 0.5625 -> 0.60 (floors raised, never lowered; held-out rows were inspected, so confirm on fresh requests). Full suite 1,497 passed.
### Abu Cap «طائر الريح الجنوبي» (`agent/abu_cap/stories/south_wind_bird.js`)
Action rescue with no on-screen text (owner's ask): tornado, whales, cliff dive, flight lessons; 38 s, rendered locally in 44 s.
### «ستايل دعاء الترند» saved (`agent/trend`) and used
The owner's trending Facebook dua reel (151K views, 1.7K shares) turned into a fixed style; a TikTok Tuesday dua (@1qwi_a2) remade in it: 13 lines, 13 library clips, render 34 s locally.
### @alrihanii Wednesday «صباح» dua (2026-11-25), copied to the pixel
New layout (big yellow «صباح», green «الأربعاء», Hijri top, white date, «صباح خير وبركة» at the bottom): traced per colour with `mimic trace --colour` (one trace per colour of the header), the six lines with `--tmin` (per-pixel minimum over the shot: the page/footage behind darkens, the still text stays, dots and hamzas kept). Engine: `whip` transitions (horizontal motion blur peaking on the cut) and `pop` entrances for traced lines. Six library clips (tulips + Quran, roses + Quran, incense, tasbih, wooden burner, roses), rendered locally in 36 s. Example: `agent/fast_reel/example_rihanii_sabah_spec.json`.
### @alrihanii Wednesday dua «دعاء يريح النفوس», copied to the pixel
Header (day, date, Hijri, subtitle, hearts) and all 7 lines traced from the original with `agent/mimic` (no library font scored above 0.61 for the line), our library footage (7 shots, fades to black on the measured dips), shadow + gain 0.82 for reading; render 50 s locally.
### Restyle of a @youma.design reel («بكبر في معادي») (`agent/restyle`)
Same footage and sound, burned-in text removed by inpainting, light regraded (teal/warm, bloom, grain), new Ruqaa lettering with gold key words and glint; render 27 s + clean 6.4 min, all local.
### Red Rose v47: dragon memory
`rose.py dragon-sync` / `rose.py dragon` hold every Black/Golden Dragon memory and capability.
### «الحب وبس» lyric motion graphic with الراجل والست
5 Higgsfield images (GPT Image 2.6, both characters as elements), canvas motion: slow camera, beat breathing (librosa beats), bokeh, rain, word-by-word Ruqaa lyrics with gold key words, beating heart; rendered locally in 42 s. Characters saved: `characters/el-ragel-wel-sit`.
### Mimic tool (`agent/mimic`)
«قلّده بالظبط / بالملي»: detect still text, measure box/colours/outline, rank ~1,400 fonts by pixel overlap, trace words when no font fits, verify element by element. First run on the @oaun.11 Wednesday reel: header 89-100 % overlap, line font found = Sultan Display.
### oaun style + local rendering
Wednesday dua reel cloned from @oaun.11 in the fast lane; rendered locally in 33 s.
### Speed audit
65 of 336 Higgsfield sandbox calls hung (3 min to 4 h, ~33 h), 39 session restarts. Rule since then: render locally, sandbox only for blocked downloads (`references/SPEED_AUDIT_2026-11-24.md`).
### Abu Cap cartoon «كبّر نفسك» (`agent/abu_cap`)
Cap and Nadara meet a mountain lion; stickman engine measured on @elkosif1 reels; Happy Ukulele (CC BY 3.0).
### Analyses
YouTube Short by @drfawwaraai (ScrapeCreators): 563 K views, AI-made, 11 s pharmacy joke.
### adeiat Tuesday style (fast lane)
Gold Hijri medallions, Panorama day, pop-in/erase lines, big words, blue brush ribbon, crossfades.
### Fast lane (`agent/fast_reel`)
prep → spec/hints → pick → make; ~10 min a reel; styles dxh, day, adeiat, oaun.

## 2026-11-21 to 2026-11-23
- Instagram/TikTok analyses of @chrishenry, @oaun.11 and @dxhmen; Pinterest clip libraries; dua voices library by weekday.
- Clones: Tuesday dua (@alihadkc2ok), cinema photo with retyped text, @dxhmen morning dua.
- Higgsfield API set up in kosif-audit-pro (Seedance example).
