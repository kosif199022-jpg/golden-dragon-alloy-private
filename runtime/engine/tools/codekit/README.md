# codekit — عدّة فيديو الكود

الـ 12 أداة اللي بتخلّي Claude يعمل فيديو كامل من الكود، متجمّعين في باب واحد جوه التنين الأسود.

## خريطة المترو (4 خطوط)

| الخط | الشغلانة | الأدوات |
|---|---|---|
| 1 | بيبني الفيديو | Remotion · HyperFrames · Motion Canvas |
| 2 | الأشكال | Three.js · Manim · Rough.js |
| 3 | الحركة | GSAP · anime.js · mo.js |
| 4 | الصوت والملف | WhisperX · auto-editor · FFmpeg |

## الأوامر

```
python3 tools/codekit/codekit.py status            # إيه الموجود، فين، أنهي نسخة، أنهي رخصة
python3 tools/codekit/codekit.py status --json
python3 tools/codekit/codekit.py map               # الخريطة + "استخدمه لما..." لكل أداة
python3 tools/codekit/codekit.py install all       # بيطبع أوامر التسطيب للناقص بس (مش بينفّذ)
python3 tools/codekit/codekit.py install motion-canvas --dest DIR --run   # التنفيذ الفعلي
python3 tools/codekit/codekit.py demo three OUT    # صفحة تجربة صغيرة (three / anime / mojs / rough / gsap)
python3 tools/codekit/codekit.py demo manim OUT    # مشهد .py + أمر الرندر
python3 tools/codekit/codekit.py demo auto-editor OUT   # الأمر الآمن بالهامش
python3 tools/codekit/codekit.py vendor-gsap DEST  # ينسخ gsap.min.js من نسختك المتسطّبة
```

## إيه المرفق وإيه لأ

- **مرفق في `vendor/` (MIT، ومعاه نص الرخصة):** Three.js 0.187.0، anime.js 4.5.0، mo.js 1.3.0، Rough.js 4.6.6.
- **GSAP مش مرفق:** مجاني للكل، بس رخصته "قياسية بدون مقابل" مش مفتوحة المصدر. `vendor-gsap` بينسخه من `node_modules` عندك وقت ما تحتاجه.
- **من الريبو / الجهاز:** Remotion و HyperFrames (في `node_modules`)، auto-editor (pip)، FFmpeg.
- **يتسطّبوا على جهازك:** Manim (محتاج pango و cairo)، WhisperX (بينزّل torch، كام جيجا)، Motion Canvas (npm).
  بديل WhisperX الشغال: `faster-whisper` بـ `word_timestamps=True`.

## صفحات التجربة

كل صفحة 1080×1920 ومدتها 3 ثواني، والمكتبة منسوخة جنبها (من غير نت). ماشية بعقد التنين:

```js
window.__kosif = {duration: 3, seek: async t => { /* ارسم الفريم عند الوقت t */ }};
window.__kosifReady = true;
```

كل فريم دالة في `t` بس: مفيش `Date.now` ولا عشوائي ولا تايمر. الخط الزمني متوقّف دايمًا وإحنا اللي بنحرّكه:
anime.js بـ `tl.seek(t*1000)`، GSAP بـ `tl.time(t)`، mo.js بـ `tl.setProgress(t/D)`، و Rough.js بـ `seed` ثابت.

تجربة صورتين:

```
node tools/render_html.cjs --in OUT/three_demo.html --out OUT/three --stills 0.5,1.5
```

## خد بالك

- **auto-editor:** لو قصّيت كل سكتة الكلام بيطلع متقطّع. سيب هامش:
  `auto-editor in.mp4 --margin 0.3sec --edit audio:threshold=0.04 --no-open -o out.mp4`
- **Remotion:** مجاني للأفراد وللشركات لحد 3 أشخاص بس.
- **GSAP:** مجاني للكل، مش مفتوح المصدر: https://gsap.com/standard-license
- الباقي مفتوح المصدر.
- `install` مش بينفّذ حاجة من غير `--run`، و WhisperX كمان محتاج `--allow-large`. ولو المساحة الفاضية أقل من 250 ميجا بيرفض.
