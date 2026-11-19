# التنين كمخرج بالـ 12 أداة — إيه اللي بيشتغل مع بعض فعلًا (v1990.8.0)

صاحب التنين كتب الخريطة: يحلل المهمة ← تصميم المشاهد ← التحريك ← الصوت ← التجميع ← 1080×1920.
ده اللي **اتجرّب** على الجهاز السحابي يوم 11 نوفمبر 2026، واللي **لسه ماتجربش**.

| المرحلة | في الخريطة | اللي اشتغل هنا فعلًا | ماتجربش هنا |
|---|---|---|---|
| تصميم المشاهد | Three.js + Manim | **Three.js** (3D) + **Rough.js** (رسم يد) في صفحة واحدة | Manim (محتاج pangocairo) |
| التحريك والمؤثرات | GSAP + Anime.js | **GSAP** (عناوين) + **anime.js** (كروت) + **mo.js** (انفجار) من ساعة واحدة `t` | — |
| الصوت والمزامنة | WhisperX + Auto-Editor | **faster-whisper** (توقيت الكلمات، مستخدم في كل أفلام الجلسة) + **auto-editor** (6 ث ← 4.6 ث) | WhisperX (محتاج torch) |
| التجميع والتصدير | Remotion + FFmpeg | **محرك التنين** (صفحة seek ← فريمات) + **FFmpeg** (H.264 CRF 17 + الصوت) | Remotion (ناقص `@remotion/cli`)، HyperFrames وMotion Canvas ماترندروش |

**الإثبات:** `tools/codekit/demos/fusion_demo.html` — خمس مكتبات في فريم واحد (Three.js، Rough.js، GSAP، anime.js، mo.js)، اترندرت 10 ث 1080×1920 30 fps بمحرك التنين. من غير صوت (كليب إثبات).
تشغيلها: انسخ الصفحة لـ `JOB/film/index.html` ومعاها `fonts/` والمكتبات (`codekit demo …` بينسخ كل مكتبة، و`codekit vendor-gsap JOB/film` لـ GSAP).

## القواعد اللي اتعلمناها
- **ساعة واحدة:** كل مكتبة تتوقف وتتحرك من `t`: `gsap.timeline({paused:true}).time(t)`، `anime.createTimeline({autoplay:false}).seek(t*1000)`، `mojs.Timeline().setProgress(t/D)`، وThree.js/Rough.js دوال رسم في `t`. ممنوع autoplay.
- anime.js مابيطبقش قيمة البداية قبل وقت الأنيميشن: حط `opacity:0` في CSS للعناصر اللي داخلة بعدين.
- Three.js لازم ملف كلاسيك واحد (`vendor/three/three.min.js`)؛ الـ ES modules مابتشتغلش على `file://`.
- **الأدوات مكتبات مش برامج مونتاج:** التنين هو اللي بيبني بيها المشهد. وجودها في الحزمة ≠ إنها اتثبتت على جهاز الرندر (`codekit status` / `video12 doctor` بيقولوا الحقيقة).
- التصدير القياسي عند صاحب التنين 30 fps. 60 fps ممكن (`--fps 60` في المحرك) بس ضعف وقت الرندر، ومايتعملش إلا لو طلبه.
- أقوى تركيبة لشغله السينمائي على الجهاز ده: **محرك التنين + Three.js + GSAP + faster-whisper + FFmpeg**؛ وعلى جهازه بعد التثبيت: Remotion + Three.js + GSAP + WhisperX + FFmpeg.
