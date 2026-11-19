# التنين الأسود — تطوير أدوات فيديو ريل إنستجرام (12)

**مصدر الأسماء:** https://www.instagram.com/reel/Dfmun_Fjap1/ — من وصف الفيديو، وليس من تفريغ صوتي مستقل.

| الإنتاج | Remotion · HyperFrames · Motion Canvas |
| الرسم والمؤثرات | Three.js · Manim · Rough.js |
| تحريك العناصر | GSAP · Anime.js · Mo.js |
| الصوت والتسليم | WhisperX · Auto-Editor · FFmpeg |

## تشغيلها من التنين نفسه

نفّذ من جذر حزمة `black-dragon/`:

```bash
python scripts/dragon.py tool video12 list
python scripts/dragon.py tool video12 plan "ريل 9:16 فيه تعليق صوتي وموشن و3D"
python scripts/dragon.py tool video12 doctor --json
python scripts/dragon.py tool video12 install --all  # معاينة الأوامر فقط، من غير تثبيت
python scripts/dragon.py tool video12 install --all --yes  # على جهاز الإنتاج فقط، بعد مراجعة وتحميل التبعيات
python scripts/dragon.py tool video12 run ffmpeg -- -version
python scripts/dragon.py tool video12 run hyperframes -- --help
python scripts/dragon.py tool video12 run remotion -- --help
```

تثبيت Node يتطلب Node.js 22+ خصوصًا HyperFrames وFFmpeg؛ Python يتطلب 3.10+ والمتطلبات النظامية المختلفة لـ Manim وWhisperX. ملف `package.json` يحتوي على مكتبات JS، و`requirements.txt` يحتوي على أدوات Python الثقيلة. تُنشئ عملية التثبيت `node_modules/` و`.venv/` داخل هذه المساحة المنفصلة؛ **الملفات الثنائية ليست مرفقة بالحزمة**.

## الاستخدام الحقيقي

- `plan` يختار الأدوات الملائمة (قائمة اختيار، وليس تنفيذًا).
- `doctor` يكشف التبعيات المتاحة؛ لا يعتبر إثبات رندر أو محاذاة صوت.
- `run` ينفّذ فقط واجهة CLI المتاحة في البيئة. `Motion Canvas` و`Three.js` و`Rough.js` و`GSAP` و`Anime.js` و`Mo.js` مكتبات برمجية تُستدعى داخل مشروع مشاهد، وليست أوامر CLI مباشرة.
- مشروع الفيديو يُخضع لمراحل التنين الحالية والفحص البصري/الصوتي المستقل قبل التسليم.
- وحدتا `hf-blender` و`cinema-craft` (عند وجودهما في الإصدار) **محتفظ بهما** ويُفضَّل استخدامهما لمهامهما المتخصصة، ولا يُستبدلان بهذه الإضافة.
- `auto-editor`: حافظ على فواصل صمت طبيعية؛ القص الآلي قد يُفسد إيقاع التعليق.

ترخيص Remotion يختلف حسب الاستخدام التجاري وحجم الفريق. تُراجع شروط GSAP وترخيص إصدار FFmpeg وتراخيص النماذج المستخدمة مع WhisperX قبل توزيع منتج تجاري. لا يُشغّل أي تثبيت أو برنامج مدفوع تلقائيًا.

## اختبارات بلا شبكة

```bash
python -m unittest discover -s tools/video12/tests -v
python scripts/dragon.py tool video12 doctor
```

**مستوى التحقق:** صحة ملفات الربط والاختبارات المحلية. تنزيل 12 برنامجًا وتشغيل مشروع فيديو كامل يتطلب جهاز إنتاج بمكتباته وموارده، وهو إجراء مستقل عن إنشاء الحزمة.
