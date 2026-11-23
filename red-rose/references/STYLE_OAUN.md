# Style card: @oaun.11 daily dua reels (measured)

Source: the TikTok account @oaun.11 (1.3 M followers, 1,035 videos listed on the profile; 1,384 posts read
from 15 Jan to 23 Nov 2026 through ScrapeCreators). 114 reels were downloaded in the Higgsfield sandbox,
measured, and deleted again: the 60 most viewed and the 60 most recent (6 failed to download).
Only numbers, one frame per shot and the transcripts were kept, in the owner's private store.

Use this card to make **new** reels in the same style. Never reuse their footage, voice or exact texts.

## Numbers (median, min to max)

| Measure | Median | Range |
|---|---|---|
| Length | 27.3 s | 11.3 to 50.5 s |
| Shots per reel | 7 | 1 to 12 |
| Shot length | 3.0 s (quartiles 2.2 / 3.0 / 4.5) | |
| Dua lines per reel | 9 | |
| Words per line | 4 | |
| Speech pace | 1.49 words/s | 0.89 to 3.02 |
| Speech start | 0.0 s (the voice starts on frame 1) | up to 2.1 s |
| Cut to nearest line start | 0.24 s; 67 % of cuts within 0.4 s | |
| Loudness | -16.5 LUFS integrated | -32.9 to -9.8 |
| Frame size | 720 x 1280, 30 fps | |
| Colour | warm: 97 % of shot frames have red above blue; mean luma 117 of 255 | |
| Views (all 1,384) | median 171,620; best 8.4 M | |

## Layout (the same on every reel)

- **Top right:** the day name in large white calligraphy (Diwani or Ruqaa look), with the Gregorian date
  `DD.MM.YYYY` under it on a thin underline.
- **Top left:** the Hijri block: a gold or teal crescent with the month name in calligraphy, the Hijri day
  number above it.
- **Under the header, optional:** one short occasion line in yellow or cyan, e.g. «ليلة جمعة مباركة»,
  «بداية شهر جديد», «تهنئة بمناسبة شهر شعبان».
- **Centre:** one dua line at a time, white bold Naskh, soft dark shadow, 2 to 6 words, changes with the
  voice.
- **Under the line:** the handle in small white caps.
- **Bottom, optional:** a gold calligraphy sticker that matches the day («جمعة مباركة», «صباح الخير»).

## Footage

Warm home interiors filmed on a phone: roses in vases (red, pink, white), the Quran open on a stand or a
prayer mat, incense burners with smoke, candles, tea or Arabic coffee, prayer beads, lamps and orchids,
lanterns in Ramadan, mosque interiors for Fridays. One background per line or per two lines. Gentle
push-in or drift; spin, zoom and slide transitions between shots.

`rose.py library fetch pins --approve-write` downloads 602 clips in this look found on Pinterest (links in
`agent/pins_catalog.csv`). Pinterest clips belong to their makers: use them for private drafts, and for a
published reel prefer your own footage or footage with a clear licence.

## Text

- Openers by frequency: «اللهم في يوم …» (22 of 114), «اللهم في صباح …» (19), «اللهم في ليلة …» (13),
  «اللهم في أول …» (9), «اللهم في فجر …» (6).
- Most frequent words: اللهم, لنا, يوم, الخير, قلوبنا, أبواب, ورزقنا, نسألك, the salawat.
- Occasions seen: every weekday, Friday night, the first and last day of a Hijri month, Rajab, Sha'ban,
  Ramadan (each Friday, farewell), Eid al-Fitr.
- Ready lines in this tone: `rose.py duas day <day>` and `rose.py duas show shaban|eid_fitr|arafah|...`.

## Making one with Red Rose

1. Lines: `rose.py duas day friday` (or write your own; keep 2 to 6 words a line, about 9 lines).
2. Voice: the owner's own recording, or a generated voice after the owner says yes. Time the lines from
   the voice (Whisper word stamps) so each cut lands just before a line starts.
3. Plan: header with the real Hijri date for the day (check it; Umm al-Qura), the day name, the date,
   one occasion line if any.
4. `rose.py dua-reel plan.json out.mp4 --approve-write`, then check loudness near -14 LUFS for delivery.
