---
name: arabic-minimal-reels
description: Edit a raw Arabic talking-head clip into a 9:16 reel in a minimal style - short line, one big key word, blue lines, paintings, flat canvases, returning to the face often. Use when the user asks for a minimal reel, "ريل بستايل minimal", "اعمل ريل بهالستايل", or asks which scene a line should get. Also explains how to build your own reference library. Not for long-form YouTube.
---

# Arabic minimal reels

A method for editing Arabic talking-head reels in a minimal style. The numbers come from a frame-by-frame study of 20 short videos. This public copy has no frames and nothing from those videos, only rules and method. The look improves a lot once you add your own references, see "Build your own reference library".

## Install

Copy this folder to `~/.claude/skills/arabic-minimal-reels/` (or `.claude/skills/` in a project). Then ask Claude Code: "Use arabic-minimal-reels to edit reel.mp4".

You need: ffmpeg; Python with `numpy` and `pillow`; `faster-whisper` for transcripts; a renderer (Remotion, or HTML/GSAP captured to frames). Fonts: Cairo and Amiri from Google Fonts. For Latin words, any grotesque sans and Playfair Display Italic.

Read in this order: this file, `placement.md` to plan, `style.md` to design, `motion.md` to animate.

## The style in 10 lines

1. Face about 60% of the time. Leave for about 2.3 s, return, stay about 3.6 s, leave again. About 8 returns per minute.
2. One trip away from the face is usually one scene (72%).
3. A line that talks to the viewer stays on the face. Always.
4. A line you could film gets B-roll. B-roll is 3 times more common than any other non-face scene.
5. A name gets a portrait or painting, for about 1.3 s.
6. A list step or chart returns with the new item between face shots.
7. One key word per line, 3 to 4 times taller than the small words beside it.
8. On the face a word hits in 1 frame. On a clean canvas it fades in over 6 frames with a little blur. It never slides and never builds letter by letter.
9. Motion takes 200-700 ms, eases out and doesn't bounce. Then it holds.
10. 81% of cuts are plain cuts. Blur is the exception. One blue per video.

## Scene types

`captions`, `broll-text`, `painting-text`, `line-text`, `line-illustration`, `text-centric`, `center-illustration`, `side-illustration`, `object-text`, `graph-stats`. Recipes are in `style.md`.

## Workflow

1. **Cut first.** Get a word-level transcript with a Whisper model that handles Arabic (`medium` or `large-v3`; the `.en` models won't work). Remove silences, breaths and bad takes. Review the cut before making any graphics.
2. **Write a plan** with one row per spoken beat, and have the person approve it:

   | Time | Line | Line kind | Scene | Reference | Key word | Asset needed |
   |---|---|---|---|---|---|---|

   Use the line-kind table in `placement.md`. Check totals: about 60% face, about 8 returns per minute, end on the face.
3. **Choose references** from your own library, if you've built one.
4. **Build scene by scene** at 1080x1920 at the clip's frame rate. Build the kit first: caption component, block wipe, line with dot, canvases.
5. **Check frames.** Render a still at every key word. Run the Arabic checklist.
6. **Sound last.** About one cue per idea. Never one per move.

Expect the first draft to need notes. Assets should be ones you have the rights to use.

## Build your own reference library

Rules teach the logic; references teach the eye. Choose videos you like and are allowed to study. Keep the result private: the frames belong to whoever made the videos, so never publish or redistribute them, and don't put them in your edit. If a site asks you to sign in or prove you're human, stop and use another source, such as your own files.

1. **Collect** 10 to 20 short videos as `.mp4` in one folder. Scan more than you need. In my scan only 30 of 220 videos from one channel actually had the animated style. Simple dark-frame scores misled badly: only 5 of the 45 highest-scoring were real matches, the rest were speakers on black sets. Look at the frames.
2. **Find the shots and transcribe:**

   ```
   python scripts/build_library.py shots --videos refs --out work --whisper small.en
   ```

   Use `--whisper medium` for non-English. This writes one numbered contact sheet per video to `work/sheets/`.
3. **Label by eye.** Ask Claude Code to open every sheet and fill in `work/labels.json`:

   ```json
   {"video1": {"3": "line-text", "4": "broll-text", "7": "object-text"}}
   ```

   Anything unlisted counts as the face. To keep captions as references too, label those shots `captions`.
4. **Build the folders:**

   ```
   python scripts/build_library.py build --videos refs --out work --library library
   ```

   Each moment gets `library/<scene-type>/<nnn>/` with `keyframes.jpg`, `first.jpg`, `peak.jpg`, `last.jpg` and `info.json` (source, start, end, spoken words, scene type).
5. **Code the lines.** For each moment, have Claude Code read `spoken` and tag the line kind from `placement.md`. Then count: which kinds go to which scene in your references, and how long each stays. If you code knowing the scene, you'll bias the result, so tag from the text alone where you can.
6. **Step through the moves.** For each kind of move, export a frame strip and count frames:

   ```
   ffmpeg -i refs/video1.mp4 -vf "select='between(n,120,150)',scale=180:-2,tile=16x2" -fps_mode passthrough -frames:v 1 strip.jpg
   ```

   Don't guess at frame counts. Record frame rate with each number.
7. **Make a board.** Pick about 130 of the best stills, sort them into the 10 scene types, and write one sentence on why each type works. The references teach the logic; the board teaches the design.
8. **Update the rules.** Add your numbers next to the ones in these files, and add a line to this file pointing at the library: "Before designing a scene, open 1-3 `keyframes.jpg` of that type."

Download at the highest resolution you can. At 360p you can't measure paper grain or blur radius, and sizes are only good to about 3 px at 1080.

## Arabic: قواعد النص بالعربي

المراجع كانت إنجليزي، فهاي القواعد ترجمة لمنطق الستايل للعربي، مع قياسات للخطوط. لو تعارضت مع إشي فوق، هاي بتمشي.

### الاتجاه
- كل إشي من اليمين لليسار: السطر، ومكان الكلمة الصغيرة، وترتيب ظهور الكلمات.
- البلوك الأزرق بيمسح من اليمين للشمال: الحافة اليمين ثابتة، 12 فريم، بتباطؤ بالآخر.
- الخط الأزرق والكاميرا بيمشوا من اليمين للشمال.
- رسمة عالجنب: الرسمة طالعة من الحافة اليمين والنص عالشمال.
- الرسم البياني: الزمن من اليمين للشمال لما يكون قصة تطور. الشارت الرسمي بيضل زي ما هو.

### ما في italic
- ممنوع أي خط مائل عالعربي، حتى لو الخط فيه نسخة مائلة.
- اللي بيعمله المائل (يفرّق الكلمة المهمة) بنعمله بـ: Amiri Bold بدل Cairo، وحجم أكبر، ولون أزرق أو بلوك.
- المائل مسموح بس لكلمة لاتينية جوا السطر.

### الكلمة بتدخل كاملة
- الكلمة العربية بتدخل كلها مرة وحدة، مش حرف حرف. الحروف موصولة، وأي حركة على حرف بتكسر الوصل.
- ممنوع letter-spacing، وممنوع أي animator بيقسم الكلمة لحروف.
- مسح البلوك بيكشف الكلمة بماسك، وهاد مسموح لأنه الكلمة نفسها ما بتتقطع.
- التوقيت: على الوجه فريم واحد. على الكانفس واللوحة 5 إلى 6 فريم، مع blur خفيف بالبداية، بدون انزلاق.
- الكلمة بتطلع بس لما تنحكى.

### الخطوط والأحجام على 1080x1920
- السطر: Cairo. الكلمة المهمة: Amiri Bold.
- ارتفاع الألف قريب من H اللاتيني: Cairo 0.705 وAmiri 0.715 وInter 0.73 من حجم الخط.
- بس جسم الحرف (ه) مختلف: Inter x هو 0.55، وCairo 0.505، وAmiri 0.385. يعني Amiri بيبان أصغر بكتير بنفس الحجم.
- لهيك: Cairo أكبر بـ1.1 مرة من الرقم اللاتيني. Amiri أكبر بـ1.25 مرة كبداية، وصحّح بالعين. (1.1 مقاس، 1.25 تقدير.)

| الموقع | السطر الصغير (Cairo) | الكلمة المهمة (Amiri Bold) | أقصى عرض |
|---|---|---|---|
| الوجه | 38 px | 125 px | 860 px |
| فيديو أو لوحة | 38 px | 185 px | 860 px |
| كانفس | 44 px | 185 px | 900 px |

- لو الكلمة أعرض من الحد، صغّر الحجم. ما تكسر الكلمة على سطرين.
- line-height بين 1.2 و1.3، لأن النقاط والحروف النازلة (ن، ي، ع) بدها مكان.
- لا تحط stroke على Amiri: بيسكّر الفتحات.

### عنوان البداية (hook)
- Amiri Bold، 3 سطور، محاذاة يمين، بيبدأ من 75 px عن الحافة اليمين و177 px من فوق. الراس مقصوص وقاعد قدام آخر العنوان. مدته 2.9 ثانية تقريباً.
- عبارة وحدة بالأزرق (مش مائلة)، والكابشن ماشي على الصدر.

### علامات وأرقام
- الفاصلة «،». بالاقتباس الكبير، علامة الفتح عاليمين.
- الأرقام: نوع واحد بالفيديو، يا 123 يا ١٢٣.
- كلمة لاتينية جوا سطر عربي: `direction: ltr` للكلمة بس، و`unicode-bidi: isolate`. افحص الترتيب بالعين.
- اختار الكلمة المهمة من المعنى، مش آخر كلمة.

### فحص قبل التسليم
- [ ] ولا حرف مقطوع بأي فريم، خصوصاً أثناء الدخول.
- [ ] كل الحروف موصولة، والنص مش مقلوب.
- [ ] ولا كلمة مائلة بالعربي.
- [ ] البلوك والخطوط ماشيين من اليمين.
- [ ] كل كلمة بتطلع وقت ما تنحكى.
- [ ] جملة بتحكي مع المشاهد مش مغطاية.
- [ ] ولا كلمة أقرب من 60 px للطرف، إلا كلمة خلفية مقصودة.
- [ ] حرف «و» منفصل بحجم كبير: بعض الخطوط بتخليه يشبه g. افحصه.
