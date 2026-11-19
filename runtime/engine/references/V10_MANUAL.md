# Black Dragon 10.0.0 — دليل التثبيت والتشغيل والتحقق

## 0) التثبيت

افك ضغط ZIP بحيث ينتج فولدر `black-dragon/` بكل ملفاته. احفظه مثلًا في `.claude/skills/black-dragon/` أو فولدر مشروع منفصل. لا تستبدل مجلد Superpowers ولا تدمج مباشرة في GitHub `main`. تحتاج Python 3.10+؛ للأفلام `ffmpeg` و`ffprobe`، ولقياس اللون `Pillow`. بعض المحركات الإضافية تحتاج Node/Playwright أو Blender أو GPU ولا يُضمن توفرها.

```bash
cd black-dragon
python3 scripts/dragon.py where
python3 scripts/dragon.py probe-tools --json
python3 scripts/dragon.py v10 catalog-audit --limit 0
python3 scripts/dragon.py v10 think "ريل 24 ثانية لأغنام الوادي" --domain video
python3 scripts/dragon.py v10 links --keyword "ميار" --limit 4
python3 scripts/dragon.py v10 kling-pack examples/v10-kling-spec.json --out out/kling-pack.json
```

## 1) إعداد المراحل السبع

1. نسخ `examples/v10-brief.json` إلى فولدر مشروع وتغييره بما يلائم المقطع. تستطيع تعديل brief فقط قبل `init`؛ بعد التوثيق، أي تغيير يتطلب Job جديدًا أو نسخة مراجعة خارج المجلد.
2. `python3 scripts/dragon.py v10 gate init --job out/demo --brief examples/v10-brief.json`
3. `python3 scripts/dragon.py v10 gate record --job out/demo --stage brief --data examples/v10-brief.json`
4. أنشئ `concept.json` بهذه المفاتيح: `options` (≥3، لكل منها `id`, `approach`, `evidence`, `risk`)، `selected` من IDs، `falsifier`, `baseline`, `hook`. سجّله بـ `record --stage concept`.
5. أنشئ `color.json` بالمثال: `{"palette":["#1B1B1B","#F7F1D8","#E1B431"],"ratios":[60,30,10],"accent_on":"product title","enforce_pixel_ratio":false}`. سجّله بـ `record --stage color-design`.
6. أنشئ EDL `shots.json` وفيه `shots` عناصر كل منها `start_s`, `end_s`, `what`, `reason`، والحقول `storyboard` (مسار **ملف موجود**) و`preview_approved:true` بعد اعتماد معاينة المستخدم. الأزمنة متصلة وتغطي المدة. سجّله بـ `record --stage shots`.
7. أنتج الفيديو باستخدام محررك أو الرندر المحلي. ملفات المصدر لا تتغير. اختياريًا: لتوثيق **تشغيل FFmpeg فعلًا** استخدم `gate render --job out/demo --output ... --receipt receipt.json --execute -- ffmpeg ...`؛ *من دون* `--execute` يعطي خطة تشغيل فقط. الأمر يرفض الشبكات والكتابة فوق الناتج افتراضيًا، ويمنع التنفيذ قبل تسجيل ستوري بورد مُعتمد ضمن نفس الـJob. استخدام البرامج الأخرى يتم خارج هذا wrapper مع إظهار الحالة كغير مثبتة محليًا ما لم تقدّم إيصالًا موثوقًا.
8. أنشئ `produce.json`: `{"video_file":"/path/to/final.mp4","renderer":"ffmpeg or actual editor","paid":false,"render_receipt":"/path/to/receipt.json"}`. `render_receipt` اختياري؛ إذا حُذف يتضح أن مصدر التنفيذ **غير مثبت**. سجّله بـ `record --stage produce`.
9. شغّل `python3 scripts/dragon.py v10 gate qa --job out/demo`. يقوم بفحص الملف المنتج والسواد والإطارات والمدة مع قياس لون التمييز في 7 كادرات. إذا فشل لا يتم تسجيل المرحلة.
10. `deliver.json`: `{"summary":"...","executed":["..."],"not_executed":["..."],"rights_reviewed":true}`. سجّله `record --stage deliver`.
11. `python3 scripts/dragon.py v10 gate check --job out/demo`. **exit 0** عندما كل المراحل مكتملة والإيصالات والملفات سليمة؛ **exit 5** عندما تنقص مرحلة أو يُكتشف تلاعب. هذا لا يغني عن معاينة بشرية للإخراج والنصوص والحقوق.

لا يجوز استخدام `preview_approved:true` من غير موافقة فعلية؛ إذا قال المستخدم «نفّذ مباشرة» يمكن ضبط `execute_directly:true` في brief مسبقًا. لا نكتب فوق الملفات الأصلية أو ننفذ أي دفع أو تحميل أو نشر.

## 2) catalog / receipts — الفرق بين الفهرسة والتشغيل

`v10 catalog-audit` يعدّ سجلات SQLite وأنواعها ويعرض **فقط** عدد 30 موصلًا محليًا مفحوصًا فحصًا ساكنًا. لا يحوّل آلاف الأوصاف والمهارات إلى برامج. حقل `full_coverage` يظل false حتى لو كانت كل سجلات الفهرس موجودة.

بصمات الملفات تثبت أن ملفًا لم يتغير **داخل هذه الجلسة المحلية**. لا تشكّل توقيعًا مستقلًا؛ ويجب حفظ الإيصالات مع المشروع وفي مكان مؤمّن مناسب إذا كانت مطلوبة لأغراض مراجعة خارجية.

## 3) فحوص خاصة للتقرير التاريخي

`التنين الأسود المشكلة والحل (للمبرمج).pdf` يذكر أربعة عيوب في أدوات لم تُرفق جميع أكوادها هنا. لا نقول إننا أصلحنا تلك المستودعات عن بعد. عند فتح `kosif-tool` على جهاز تطوير يملكها، نفّذ اختبارات ثوابت المعادلات وpixel-studio ومدخلات motion-cut وعدد BPM معروف. في كل حالة يجب أن ينشأ إخراج قابل للمقارنة، لا مجرد `exit_code:0`.

## 4) استخدم مواد المرفقات دون نسخها في التسليم

`v10 audit-media FILE... --out audit.json` يصدر `ffprobe` وSHA-256. أضف `--deep` لتشغيل فاحص السواد والإطارات والـLUFS عند توفر الاعتماديات. جرّب على عينات حقيقية مرخصة. ملف ميار تحول إلى `app/data/v10_media_links.json` للبحث فقط، وليس روابط مرخّصة بالضرورة. لا تتضمن الحزمة فيديوهات الإعلان الستة أو نص كتاب Kahneman أو خطوط خاصة.

## 5) اختبار النسخة

```bash
cd black-dragon
PYTHONPATH=app python3 -m pytest -q app/tests/test_v10.py app/tests/test_v13_capabilities.py app/tests/test_v12_docs.py
PYTHONPATH=app python3 -m dragon v10 catalog-audit --limit 0
PYTHONPATH=app python3 -m dragon v10 kling-pack examples/v10-kling-spec.json
```

نتائج اختبارات الإصدار موجودة في `TEST_REPORT.md`، وحدود الاختبارات موثقة بوضوح.
