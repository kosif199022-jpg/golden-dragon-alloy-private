# Style card: @dxhmen daily dua reels (measured)

Source: the TikTok account @dxhmen. All 757 posts from Dec 2024 to Nov 2026 were read through
ScrapeCreators (captions, hashtags, region, post time, numbers). A sample of the most viewed and the
most recent reels was downloaded in the Higgsfield sandbox, measured (shots, camera moves, transitions,
loudness, speech) and deleted again. Only numbers and one frame per shot were kept.

Use this card to make **new** reels in the same style. Never reuse their footage, voice or exact texts.

## The account in numbers (all 757 posts)

| Measure | Value |
|---|---|
| Views | median 336,644; best 10.8 M («أصبحنا وأصبح الملك لله», a morning dua) |
| Length | median 26.6 s |
| Audience region (TikTok `region`) | France 663, Algeria 54, Morocco 28, Spain 12: a North-African diaspora audience |
| Posting hour (UTC) | 19, 18, 16, then 10 and 12: evening in Europe, and a late-morning slot |
| Posting day | Thursday 261 of 757 (the «ليلة الجمعة» post), then the other days evenly |
| Sound | 754 of 757 are the creator's own voice («original sound») |
| Places (POI) | none tagged |
| Saves / shares per view | 0.6 % / 1.7 % (median) |

## Captions and hashtags

- Caption opens with the day: «دعاء يوم الجمعة» (126), «دعاء ليلة الجمعة» (116), then every weekday; occasions:
  المولد النبوي، رمضان، عيد، شعبان، رجب، الفجر، سورة.
- Then one short line in the voice of the dua («اللَّهُمَّ في ليلة جمعة من الشهر الجديد يارب 🤲»).
- Emoji: 🌷🌹🌺🌸 together on almost every post, then 🤲 ❤️ 🕋 💓 📿.
- Five hashtags a post (median). Most used: #اللهم_امين, #اللهم_صلي_على_نبينا_محمد💓🕋📿,
  #اللهم_لك_الحمد_ولك_الشكر, #جمعة_مباركة, #يارب❤️, #دعاء, #صباح_الخير, #دعاء_جميل, then the day tag
  (#دعاء_يوم_الجمعه, #دعاء_ليلة_الجمعة, #دعاء_يوم_الاحد …) and #dxhmen.
- Best day tag by median views: #دعاء_ليلة_الجمعة (700 k), #دعاء (465 k), #دعاء_يوم_الجمعه (400 k);
  the other weekdays sit at 190 k to 270 k.

## Edit (85 reels measured: the most viewed and the most recent)

| Measure | @dxhmen | @oaun.11 for comparison |
|---|---|---|
| Length | 27 s | 27 s |
| Shots per reel | 6 | 7 |
| Shot length | 5.2 s | 3.0 s |
| Camera in a shot | mostly still (66 %), slow zoom-out (19 %), zoom-in 5 %, pan 5 %, rotate 4 % | gentle push-in |
| Transitions | plain cut 79 %, blur-move 9 %, white flash 6 %, dip to black 6 % | spin, zoom, slide |
| Speech | starts on frame 1, 1.65 words/s | 1.5 words/s |
| Loudness | -16.3 LUFS (raise to -14 for delivery) | -16.5 LUFS |
| Frame | 1080 x 1920 in 36 of 85, 576 x 1026 in 32 | 720 x 1280 |

So the look is calmer than @oaun.11: fewer, longer shots, almost no camera move, and mostly hard cuts,
with a flash or a blurred move only on the strong lines.

## Layout

- **Top centre:** a gold calligraphy title for the day or occasion («جمعة مباركة»، «دعاء الفجر»،
  «صباح الخير»، «ليلة المولد»), sometimes with the Gregorian date `DD/MM/YYYY` and the Hijri month
  name in a small white Ruqaa line.
- **Centre:** one dua line in white Naskh with a soft shadow, sometimes a small heart between words.
- **Under it:** the handle `@DXHMEN` in very small letters.

## Footage

Sunset over the sea and waves, gold incense burners (mabkhara) with roses, the Quran on a stand with
candles and prayer beads, the Prophet's Mosque and the Kaaba (Fridays and the Mawlid), camels in the
desert at sunset, flower fields, a swing or chair facing the sea, clouds, dawn sky, Ramadan lanterns.

`rose.py library fetch dxh_pins --approve-write` downloads 152 clips in this look found on Pinterest
(links in `agent/dxh_pins_catalog.csv`; also on the git branch `media/dxhmen-pins`). They belong to their
makers: private drafts only.

## Voices by day

`agent/dua_audio/dua_audio.py` lists any TikTok dua account, labels each reel by day or occasion and,
in the sandbox, keeps only the audio sorted by label. The @dxhmen and @oaun.11 voices were collected
this way for private study (see SOCIAL_FETCH.md). Do not publish them; use the owner's own voice or
TikTok's in-app sound.
