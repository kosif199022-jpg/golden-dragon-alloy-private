# KOSIF — حقيبة أدوات الإخراج والتصوير والمونتاج

**نسخة 2026-10-25** — حزمة فعلية تحتوي على برنامج KOSIF صغير قابل للتشغيل، ملفات سيناريو، أدوات فحص وتشغيل الفيديو، مفهرس المستودعات، وتثبيت/استنساخ الأدوات الأخرى.

## مهم جدًا: ما الموجود داخل ZIP وما ليس موجودًا؟

- **موجود بالفعل:** برنامج `kosif.py` مكتوب ببايثون (أوامر الفهرس، فحص البيئة، تجهيز Storyboard، الرندر بواسطة FFmpeg، تجميع مقاطع الفيديو، تقارير التنفيذ)، بيانات المستودعات، قوائم التثبيت، أمثلة واختبارات.
- **غير موجود داخل ZIP:** الأكواد الكاملة للمستودعات الكبيرة على GitHub، برامج Blender وFFmpeg الجاهزة للتثبيت، أوزان نماذج Wan/Hunyuan، ملفات الفيديو الأصلية، أو المستودعات الخاصة التي تحتاج تسجيل دخول. لاستلام تلك المكونات على جهازك، استخدم أمر `install --execute` الموضح أدناه.
- **المستودعات المعروفة باسم KOSIF:** `kosif-tool`, `kosif-studio`, `kosif-one`, `kosif-omni`, `kosif-render-lab`, `fastify-motion-bro`, وأخرى. لا نقوم بتسمية كود الأطراف الأخرى باسمنا أو تغيير تراخيصه.

## التشغيل السريع — Windows

1. فك الضغط، وادخل مجلد `KOSIF`.
2. انقر `START_KOSIF.cmd` أو افتح Terminal/PowerShell في المجلد.
3. نفّذ `python kosif.py doctor` للتأكد من وجود Git وPython وFFmpeg.
4. نفّذ `python kosif.py catalog` لاستعراض جميع الأدوات.
5. نفّذ `python kosif.py install --group own-video --execute` لجلب أدوات KOSIF الخاصة بالفيديو.
6. نفّذ `python kosif.py install --group all --execute` لاستنساخ **جميع** المستودعات (قد يحتاج مساحة ضخمة وتسجيل دخول؛ لا ينزّل أوزان AI أو البرامج التنفيذية).

## التشغيل — macOS / Linux

```
python3 kosif.py doctor
python3 kosif.py catalog
python3 kosif.py install --group own-video --execute
```

## تجربة فعلية على نظام يعمل عليه FFmpeg

```
python kosif.py storyboard --output project/my_film.json --title "My Film" --duration 15 --shots 3
python kosif.py render --storyboard project/my_film.json --output output/demo.mp4 --width 720 --height 1280 --fps 24
```

يُنتج الأمر الثاني فيديو تجريبي من مشاهد ملوّنة **دون لقطات خارجية**؛ عدّل قيمة `source` لكل مشهد إلى مسار فيديو/صورة حقيقية لتحصل على مونتاج لقطات حقيقي. يدعم أيضًا `--audio /path/song.mp3` لجعل طول الصوت هو المرجع وتوزيع مدد المشاهد عليه.

## المعمارية

`KOSIF` = وحدة تنسيق مستقلة لا تتجاوز صلاحياتك. الكود الفعلي للمشروعات الخارجية يُجلب لاحقًا إلى `workspace/sources/`. يمكن فحص كل مشروع وتثبيته طبقًا لتعليماته الرسمية.

ابدأ بـ `docs/GUIDE_AR.md` للاستخدام بالتفصيل، و`docs/RIGHTS_AND_LIMITS_AR.md` لفهم أحجام الملفات والتراخيص والمتطلبات.
