---
name: sync-guard
description: >-
  حارس التزامن: أي نص أو كابشن أو موشن جرافيك على فيديو فيه كلام أو أغنية لازم يطلع مع الكلمة وهي بتتقال. بيجيب توقيت كل كلمة من الصوت (faster-whisper)، ويقيس كل سطر SRT/ASS/VTT/JSON وكل حركة قدامها، ويصلّح التوقيت أوتوماتيك في ملف جديد. Use whenever captions, subtitles, lyrics, karaoke, kinetic text or motion graphics go on a video with speech or a song, or the user says: الكلام متأخر، النص سابق، تزامن، مع الكلام، sync, captions late, lip sync.
---

# حارس التزامن (sync-guard)

**القاعدة:** النص والحركة يتبنوا على توقيت الكلام نفسه، مش بالعين. الحد 0.12 ث (3 فريمات على 25).

```bash
R="python3 -X utf8 scripts/rd.py"
$R sync words video.mp4 --out words.json            # توقيت كل كلمة (محتاج faster-whisper، أو هات ملف كلمات جاهز)
$R sync check words.json subs.srt --motion cues.json # 0 ✅ · 1 ❌ متأخر/بدري/بيختفي بدري · 2 ⚠ نص مش متقال أو فاضل كتير
$R sync fix words.json subs.srt --out subs.synced.srt --motion cues.json   # بيظبط ويقيس تاني
$R sync onsets video.mp4 subs.srt                     # فحص خشن من غير تفريغ (بدايات الكلام من الصمت)
```

- ملف الموشن: `[{"word": "الكلمة", "t": 3.4, "occurrence": 1, "label": "زوم"}]`، كل حركة مربوطة بكلمة.
- بيفهم العربي من غير تشكيل وبالهمزات المختلفة (انا = أنا، الكلام ≈ والكلام).
- سطر نصه مش متقال في الصوت بيطلع ⚠: ده غالبًا نص اتألف (ممنوع، الخطأ M03).
- `fix` مابيلمسش الملف الأصلي، وبيحافظ على تاجات ASS زي `{\fad}`.
- كل فشل بيتسجل في `~/.red-dragon/sync/misses.jsonl`.

## الوقت مربوط بالكلام، مش بالثواني (v2.12، فكرة من hypit-ai/hypit)
اكتب السكربت مرة واحدة بعلامات، والتوقيت كله بيتحسب من الصوت. لو الصوت اتغيّر أو اتسجّل تاني، كل حاجة بتتحرك معاه لوحدها.

```text
@{hook!}انا بحبك @{love}يا قلبي@{/love} || والكلام ده [ليكي|ليكي]
@{big!}انتِ الدنيا كلها
```
- `@{اسم!}` **Moment**: لحظة أول كلمة بعدها (كشف، زوم، صوت مؤثر).
- `@{اسم}…@{/اسم}` **Selection**: مدة الكلام ده (B-roll يغطيه، لوحة تفضل ظاهرة).
- `||` أو سطر جديد: الكابشن اللي بعده يبدأ هنا. `[مكتوب|متقال]`: اللي على الشاشة غير اللي بيتنطق.

```bash
$R sync script script.txt words.json --out timeline.json --events events.json --srt subs.srt --ass karaoke.ass [--lock brand]
$R sync grid ref.mp4 --words words.json --out grid.jpg --every 1   # فهم المرجع: كل فريم عليه وقته والكلام اللي بيتقال
```
- `events.json`: `[{"label":"زوم","at":"big"}, {"label":"broll","span":"love"}, {"label":"pop","word":"الدنيا","dur":0.5}]` ← بيطلع بأوقات مطلقة.
- `--ass` بيطلّع كابشن كاريوكي: كل كلمة بتنور وهي بتتقال (`\kf`). و`--lock` بياخد الخط والألوان من قفل المرجع.
- أي علامة مربوطة بكلمة ماتقالتش بتطلع ❌، مش بتتحط في مكان متخمّن.
- `selftest`: 17 فحص.
