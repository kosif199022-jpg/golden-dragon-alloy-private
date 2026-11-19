# الترقية لـ v1990.10.0 (2026-11-12)
فك الضغط فوق النسخة القديمة أو في فولدر جديد. مفيش خطوات تثبيت إجبارية. الجديد: 9 ستايلات بقوالبها (ST06–ST14)، أدوات `mono` / `codekit` / `video12` / `palette` / `chroma` / `library`، وخلاصة الجلسة في `references/SESSION_HARVEST_V19909.md`.
للتأكد: `python scripts/dragon.py tool looks list --kind style` و`python scripts/dragon.py tool codekit status`.

> **1990.6.0:** خلاصة كل محادثات المشروع (`references/PROJECT_HARVEST_V19906.md`)، و15 طريقة شغل جديدة بصورها في `tool looks` (PM01–PM15)، و`tool looks find|remind`: صورة النموذج تتبعت لصاحب التنين قبل ما يتستخدم.
> **1990.5.0:** مكتبة النماذج بصورها (`tool looks`)، عدّة فيلم الكلام (`tool lyric` + `render.sh --from`)، بوابة المؤثرات الذكية (`fx`)، وخلاصة جلسة 9–11 نوفمبر في `references/SESSION_HARVEST_V19905.md`.

## v1990.1 candidate — GitHub Atlas integration

The user-uploaded GitHub Atlas catalogue is accessible offline via `python scripts/dragon.py tool github-atlas find "مونتاج فيديو"`. Search/metadata only: NO third-party install, no network, and no credits. Read `references/GITHUB_ATLAS_V19901.md` and `TEST_REPORT_V19901.md`.

# v10.10.0 Guardian selective fusion

Use `python scripts/dragon.py play-check VIDEO.mp4 --fix`, `status`, `last`, `resources`, `tool layout` or `tool hunter615 sites` for offline browsing. No installation or network by default. See references/GUARDIAN_MERGE_V1010.md.

# Black Dragon v10.9.0 — Physics & Math

## الإضافة
أُضيفت مهارة Physics & Math من الأرشيف المرفق فوق **Black Dragon v10.8.0**، دون حذف محركات Visual Forge وREA Ultra وBlender Pro وMedia Hunter وUltra Mind ومجلس الخبراء والإبداع.

السكريبت الأصلي يحسب وحدات ومساحات وأحجام وكثافات، جاذبية وسقوطًا ومقذوفات وارتدادًا وسبرينج، منحنيات easing، FOV وعمق الميدان وDolly Zoom، فريمات وتايم كود وسلو موشن، توقيت القطع حسب BPM، قص 9:16، حسابات dB/LUFS النظرية، وتتبع السرعة من البكسلات.

## التشغيل
فك الأرشيف إلى مجلد جديد، وداخل `black-dragon` شغّل:

```bash
python scripts/dragon.py tool physics doctor
python scripts/dragon.py tool physics calc "sqrt(2*20/g)"
python scripts/dragon.py tool physics fall --height 20 --fps 30 --keys
python scripts/dragon.py tool physics camera fov --focal 35 --sensor s35 --distance 3
python scripts/dragon.py tool physics camera dolly --focal 24 --focal2 85 --distance 2
python scripts/dragon.py tool physics beats --bpm 128 --fps 30 --duration 12
python scripts/dragon.py tool physics frame --src 1920x1080 --dst 1080x1920
python scripts/dragon.py tool physics convert 72 km/h m/s
```

لإنشاء ملف كيفريمات وإيصال يفحصان بعد التصدير:

```bash
mkdir -p out
python scripts/dragon.py tool physics beats --bpm 128 --duration 12 --fps 30 --out out/beat-cuts.csv --receipt out/beat-cuts.receipt.json
python scripts/dragon.py tool physics verify out/beat-cuts.receipt.json
```

لو الملف موجود بالفعل، اختر اسمًا جديدًا. لا يوجد استبدال تلقائي أو تنزيل مكتبات أو تشغيل خدمات مدفوعة. `setup` يظل وضع معاينة افتراضيًا.

## إرشادات دمج المونتاج
- مرّر مخرجات `fall` أو `bounce` أو `spring` أو `ease` إلى محرك الحركة في Blender/Remotion بعد فحص التوقيت يدويًا.
- استخدم `beats` لتوقيت القطع مع BPM محدد وراجع نقطة بدء النبض يدويًا.
- استخدم `camera` للزوايا والمسافات النموذجية، ثم تأكد من قياسات العدسة والمستشعر الحقيقية.
- استخدم `audio` لحساب gain اعتمادًا على LUFS *مقاس خارج هذه الأداة*؛ لا تدّعِ أن الأداة استمعت إلى الصوت أو قاست مستوى الصوت.

## الحدود
- الحسابات فيزيائية مثالية؛ مقاومة الهواء في المصدر نموذج تقريبي وليست محاكاة CFD. فحص الاحتكاك والتصادمات المعقدة غير موجود.
- التايم كود non-drop؛ لا تدعمه للمشاريع التي تتطلب drop-frame بدقة SMPTE.
- قيم المناطق الآمنة لتطبيقات الريلز تقريبية ويمكن أن تتغير مع واجهة المنصة.
- `--receipt` يؤكد تطابق الملفات ببصمات محلية لا صحة الفيزياء في الواقع ولا توقيعًا رقميًا خارجيًا.
- الملف المرفق لا يضم ترخيصًا مستقلًا واضحًا للشفرة؛ احفظه للاستخدام المصرّح به وتحقق من حقوق إعادة التوزيع.

## الاختبارات
**50** اختبارًا ناجحًا للرياضيات والإدخال والكيفريمات والبصمات والتكامل؛ و**223** اختبارًا ناجحًا في مجموعات توافق مختارة للإصدارات السابقة. الإجمالي **273 اختبارًا ناجحًا**، و**24 اختبارًا مستبعدًا من مجموعات التوافق المختارة**؛ لا يوجد ادعاء بتمرير كل الاختبارات الثقيلة. راجع `TEST_REPORT.md` و`references/PHYSICS_MATH_V109.md`.

لم تتم أي كتابة إلى GitHub أو تحديث لفرع main.

---

# Black Dragon v10.8.0 — Visual Forge / مصنع الصورة

## ما الجديد؟

تم دمج مهارة Visual Forge الواردة في `visual-forge.zip` مع نسخة 10.7، مع الحفاظ على محركاتها القديمة. المهارة الجديدة تربط **تخطيط الصورة/الفيديو** ببناء برومبتات ChatGPT/Kling، وتضيف مؤثرات جوية يمكن تطبيقها محليًا على الصور والفيديو.

المصدر المرفق يشمل **21 إعدادًا** للأجواء في ملف JSON (الوصف الأصلي ذكر 20)، وخمس مراجع للبرومبتات والإضاءة/العدسات والـFX والتخطيط. لم نثبّت خدمة توليد خارجية، ولم نستهلك كريدت.

## الاستخدام

```bash
cd black-dragon
python scripts/dragon.py tool visual-forge doctor
python scripts/dragon.py tool visual-forge atmos
python scripts/dragon.py tool visual-forge plan --brief "إعلان منتج تحت المطر" --kind video --shots 3 --ratio 9:16 --out out/campaign
# عدّل out/campaign/plan.json لكتابة الكونسبت واللقطات واللوك والحركة
python scripts/dragon.py tool visual-forge prompts out/campaign/plan.json
python scripts/dragon.py tool visual-forge verify-prompts out/campaign/prompts/prompt_receipt.json
python scripts/dragon.py tool visual-forge fx input.png output.png --fx '@rain' --seed 7
python scripts/dragon.py tool visual-forge fx input.mp4 output.mp4 --fx 'rain:0.6,fog:0.2' --seconds 3
```

**التنبيه:** `plan` ينتج مسودة غير مكتملة، و`prompts` يرفض اللقطات الناقصة. توليد ChatGPT/Kling لا يحدث في هذه الأوامر؛ هي تنتج نصوصًا معدّة للتوليد لاحقًا. `fx` هو المحرك الذي ينشئ صورة/فيديو محليًا، ولا يكتب فوق الملفات الموجودة.

## حماية الجودة

- التحقق من خطط الصور والفيديو، هوية اللقطة، وضوح الحركة، وقواعد برومبتات GPT/Kling.
- حفظ بصمة SHA-256 للخطة وبرومبتات اللقطات، وإرجاع فشل عند تغيرها.
- الصور ذات الخلفية الشفافة تحتفظ بقناة alpha؛ الصوت المضغوط المتوافق يُنسخ كما هو بدل إعادة ترميزه، كما ثبت في تجربة AAC/MP4 قصيرة.
- دعم `numpy` و`opencv-python` و`ffmpeg`/`ffprobe` للمؤثرات، وهي متاحة في بيئة الاختبار الحالية. حالة جهازك تُقاس بالأمر `doctor`.
- 37 مدخل أداة في الكتالوج، مع أمانة التمييز بين 'مسجل' و'مدخله موجود' و'عمل بالفعل'.

دليل تفصيلي: `references/VISUAL_FORGE_V108.md`. التقرير: `TEST_REPORT.md`.

## الاختبارات

**232 اختبارًا ناجحًا** في أربع مجموعات مكتملة مع 15 حالة مستبعدة من هذه المجموعات. ليست شهادة نجاح لكل المحركات الثقيلة. انظر `TEST_REPORT.md` للأوامر والأدلة والقيود.

## طريقة التثبيت

فُك ZIP في مجلد منفصل عن 10.7. لا تكتب فوق ملفاتك القديمة مباشرة. أمر `setup` يعرض خطة فقط افتراضيًا؛ أي تثبيت أو اتصال بالخدمات المدفوعة يحتاج موافقة صريحة. لم تُرفع النسخة إلى GitHub.

---


## v10.8.0 — Visual Forge

Copy this version to its own directory instead of replacing 10.7 in-place. Visual Forge is an optional new `tool visual-forge` adapter with no generation API calls or installation. It includes the upstream files and a documented patched render copy, plus QA tests. See `references/VISUAL_FORGE_V108.md`.

# Black Dragon v10.7.0 — REA Ultra Bridge

الإصدار 10.7 يضيف مهارة `rea-ultra` (المرجع، والمراجع الفرعية، والسكربتات المصدرية) إلى الإصدار 10.6.0، مع جسر **تحليل ساكن محلي فقط**؛ لا يستبدل محركات الإنتاج السابقة.

## ما الذي أضيف فعليًا
- `tool rea-ultra doctor`: الكشف عن أدوات REA/Ghidra/JADX/ADB وغيرها الموجودة على PATH، دون استدعائها.
- `triage`: فحص ملف عادي، نوعه حسب magic bytes، SHA-256، قياس entropy لعينة محددة، معاينة فهرس ZIP دون استخراج أو تنفيذ، وإيصال Evidence فيه observed/inferred/unknown.
- `plan`: إعداد مسار التحليل المناسب للنوع (PE/APK/WASM/ELF/JS/SQLite) وفق دورة 7 مراحل من المرجع، دون تشغيل المحركات الموصى بها.
- `compare`: مقارنة ملفين بفحص SHA-256 وحقول النوع والحجم؛ **ليست** مقارنة لسلوكهما.
- `verify`: إعادة فحص بصمة الملف الأصلي وحجم الملف مقابل إيصال JSON، وإرجاع exit 1 عند اختلافهما.
- `digest`: تلخيص نتائج JSON كبيرة (حتى 16 MB)، واستعراض مسار أو البحث عن نص فيها دون تشغيل أي تعليمات بداخلها.
- نسخ وثائق REA Ultra والمراجع تحت `skills/rea-ultra/`، مع الاحتفاظ بملف ترخيص REA MIT المرفق للمراجع المصدرية المنقولة.

## أوامر سريعة
```bash
cd black-dragon
python scripts/dragon.py tool rea-ultra doctor
python scripts/dragon.py tool rea-ultra triage /path/to/your/authorized/sample.exe --out out/sample-evidence.json
python scripts/dragon.py tool rea-ultra plan /path/to/your/authorized/sample.exe
python scripts/dragon.py tool rea-ultra compare old.dll new.dll
python scripts/dragon.py tool rea-ultra verify out/sample-evidence.json
python scripts/dragon.py tool rea-ultra digest result.json --path result.imports --limit 10
python scripts/dragon.py find "هندسة عكسية برنامج" --json
```

## مهم: حدود التنفيذ
- الأرشيف REA Ultra يحمل **مهارة ومراجع وسكربت تلخيص وباورشيل فقط**؛ لا يحمل توزيعة REA CLI ولا Ghidra/JADX أو ملفات برامج لتنفيذها على جهازك.
- المسارات والنجاحات المذكورة في المصدر تخص بيئة Windows مؤلفة الملف؛ لا تثبت جاهزية الجهاز الحالي.
- `doctor` يرصد البرامج على PATH فقط، وليس إثبات عملها. لم نفتح Binary داخل Ghidra، ولم ننفذ Frida أو ADB أو نفك تطبيقًا تلقائيًا.
- الفحص المحلي لا يثبت أن العينة آمنة ولا خالية من برمجيات ضارة. لا تشغّل عيّنات غير موثوقة.
- حلّل فقط ما تملكه أو لديك تفويض واضح لتحليله. لا رفع بيانات، ولا شبكات، ولا تثبيت، ولا تجارب ديناميكية دون إذن.
- `sha256` بصمة سلامة محلية وليست توقيعًا مشفرًا على صحة التحليل.

## التثبيت
ضع المجلد `black-dragon` بجوار نسخة 10.6 السابقة، وليس فوقها. تشغيل `setup` افتراضيًا يعرض خطة فقط، ولا يثبّت REA أو Ghidra أبدًا. أي إضافة برامج تتم يدويًا بعد الموافقة.

الوثيقة المفصلة: `references/REA_ULTRA_V107.md`. الاختبارات: `TEST_REPORT.md`.

---

## 10.6.0 — Absolute Creativity

Copy alongside, not over, the 10.5.0 release. Nine reference guides plus the creative-idea generator and Arabic font laboratory were adopted. The new `tool creativity` wrapper offers reproducible ideation with a fixed seed, audited creative proposals and optional RTL image title generation. No font binaries or another PC's font cache are bundled. See `references/ABSOLUTE_CREATIVITY_V106.md` and `TEST_REPORT.md`. All other bundled engines are retained.

## 10.5.0 — Upgrade

Copy this `black-dragon` directory as a separate version, keep old 10.4 backup. For the new Blender Pro tool run `python scripts/dragon.py tool blender-pro doctor`. Nothing is installed automatically; the current `dragon run blender` engine remains unchanged. See `references/BLENDER_PRO_V105.md` and `TEST_REPORT.md`.

> **10.4.0:** أضيف مجلس الخبراء من `expert-council.rar`: تخطيط 3/5/7 مقاعد، تدقيق أدلة واختلافات حقيقيّة، وسجل تصحيحات خاص. يوجد كود تنفيذي للأوامر والفحوص، لكن الشخصيات تمثّل عدسات تقييم وليست خبراء أو وكلاء تم الاتصال بهم. راجع `references/EXPERT_COUNCIL_V104.md`.

> **10.3.0:** دمج Ultra Mind من أرشيف المستخدم (8 ملفات)، وإضافة تخطيط مستويات التفكير L0–L3، وتدقيق بنيوي مع فحص أدلة SHA-256 الحقيقي، وحساب Brier لمعايرة التوقعات. هذه ليست إعادة تدريب للنموذج؛ النتائج لا تثبت صحة استدلاله. راجع `references/ULTRA_MIND_V103.md`.

> **10.2.0:** إضافة مهارة Media Hunter وواجهة للبحث والاكتشاف والتنزيل بأرقام النتائج، مع توثيق الحقوق ومفاتيح API الآمنة. اقرأ `references/MEDIA_HUNTER_V102.md`. فهرس الـ615 موقع والمحرك الأصلي غير مرفقين، ولذلك غير مدّعى دمجهما.

> **10.1.0:** استيراد تحسينات v1.3 لا سيما stock، الصوت والصمت، وتطابق المدة وإدارة النسخة القديمة. اقرأ SKILL.md وTEST_REPORT.md.

# التنين الأسود — الإصدار 10.3.0

هذه **نسخة وظيفية جديدة** مبنية على `black-dragon-v1.3-superpowers-merged(1).zip` والمواد التي أرسلها المستخدم بتاريخ 2026-11-09. لم تُغيَّر الملفات المرفقة الأصلية، ولم يُرفع شيء إلى GitHub، ولم يتم تشغيل أي API مدفوع.

## ماذا يعمل في النسخة 10؟

- الحفاظ على المحركات الحالية (مونتاج، سينما، صوت، صور، Blender اختياري، كرتون، ستوري بورد، Kling text lint)، مع سبعة مدخلات CLI جديدة وفهرس متجدد.
- `v10 think`: تسع اختبارات تفكير وتحيز مستوحاة من الكتاب المرفق، مع اختيار ثلاث خطط ومراجعة أدلة مضادة من غير اختلاق درجات.
- `v10 catalog-audit`: قراءة 22,349 سجلًا من قاعدة SQLite (حسب هذا الأرشيف) وفصل السجلات الوصفية عن 32 مدخلًا محليًا مسجلًا؛ الفحص ليس تنفيذًا.
- `v10 audit-media`: ffprobe فعلي، SHA-256، اختياريًا فحص السواد/الإطارات/الصوت.
- `v10 kling-pack`: تقسيم زمني دقيق للأفلام حتى 600 ثانية إلى بلوكات 3–30 ثانية (Flash 3–20 حسب مرجع المستخدم) مع قالب story engine / 3×3 storyboard وختم فاحص النص المحلي؛ **لا يولد أي صورة أو فيديو ولا يصرف Credits**.
- `v10 gate`: بوابة إنتاج 7 مراحل، ستوري بورد قبل التنفيذ، اعتماد المعاينة، رندر FFmpeg اختياري بأمر صريح `--execute` داخل Job معتمد، وإيصالات SHA-256، وفحص الفيديو نفسه وقياس لون التمييز من 7 كادرات.
- `v10 links`: فهرسة 115 رابطًا أساسيًا و12 إضافيًا من الملف المرفق، مع حقوق غير مؤكدة ودون أي تحميل آلي.
- دراسة عملية للنسخ الست من إعلان أغنام الوادي: metadata وقواعد المقارنة، وفحص تقني عميق للنسخة الأولى بالموسيقى. **الفيديوهات وكتاب Kahneman وخطوط المستخدم غير مرفقة في الناتج.**

## التشغيل

```bash
cd black-dragon
python3 scripts/dragon.py where
python3 scripts/dragon.py v10 catalog-audit --limit 0
python3 scripts/dragon.py v10 think "مونتاج إعلان" --domain video
python3 scripts/dragon.py v10 kling-pack examples/v10-kling-spec.json --out out/kling.json
python3 scripts/dragon.py v10 audit-media /path/to/clip.mp4 --deep --out out/media-qa.json
```

دليل المشروع كاملًا: `references/V10_MANUAL.md`. مرجع المعلومات: `references/V10_SOURCES.md`. الاختبارات وحدودها: `TEST_REPORT.md`.

## متطلبات وحقوق

Python 3.10+ (بحسب تبعيات المحركات الأصلية)، ffmpeg/ffprobe للوسائط وPillow لتحليل الألوان، Node + Playwright لبعض محركات الويب، Blender لبعض مهام 3D. **وجود ملف محرك لا يعني عمله عندك**. لا تثبت برامج أو تدفع أو ترفع وسائط خاصة أو تنشر بدون موافقة صريحة.

## v1990 (2026-11-11)
ارفع `black-dragon-v1990.zip` مكان النسخة القديمة. أول أمر: `python scripts/dragon.py tool hf free` ثم `tool hf trend live` و`tool hf blender rules`. التفاصيل: `CHANGELOG.md` و`TEST_REPORT_V1990.md` و`references/HIGGSFIELD_FREE_V1990.md`.
