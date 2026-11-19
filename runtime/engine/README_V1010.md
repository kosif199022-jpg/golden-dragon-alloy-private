# Black Dragon v10.10.0 — Guardian Fusion

## ما الذي تغير؟

تم تطوير نسخة **10.9.0** الحالية باستخدام الأرشيفات الثلاثة المرفقة (10.6 و10.7 و«الحارس» 10.8) دون خفض الإصدار أو استبدال محركات 10.9. أضيفت واجهة الحارس لفحص تشغيل ملفات الفيديو وتتبع المهام، ومحرك **Media Hunter 615** الحقيقي إلى جانب محرك البحث القديم، وفهرس Repo Fusion وأدواته المستقلة، وآلية استخدام نموذج Whisper مخزّن بديلًا إن توفّر.

**الفرق بين فهرس مكتشف وتنفيذ فعلي:** 615 موقعًا موجودون في CSV؛ 352 لهم قالب بحث خاص وفق بناء الفهرس المحلي، أما البقية فتعرض بحثًا داخل الموقع. هذا لا يعني وجود 615 API نشطة، ولا يمنح حق إعادة استخدام الوسائط. لا توجد اختبارات بحث شبكي حي موثقة لهذا الإصدار.

## أوامر جاهزة

```bash
# من داخل مجلد black-dragon بعد فك الضغط:
python scripts/dragon.py where
python scripts/dragon.py play-check FILM.mp4
python scripts/dragon.py play-check FILM.mp4 --fix          # نسخة _phone.mp4 مستقلة؛ لا يغير الأصل
python scripts/dragon.py play-check FILM.mp4 --fix --normalize
python scripts/dragon.py status --json
python scripts/dragon.py last --json
python scripts/dragon.py resources --json
python scripts/dragon.py tool layout ';LG'
python scripts/dragon.py tool hunter615 sites 'camel desert sunset' --type video --json
python scripts/dragon.py tool hunter615 keys
python scripts/dragon.py tool fusion list
python scripts/dragon.py tool physics doctor
```

ملاحظة: `tool hunter615 get 1` يرفض التنزيل افتراضيًا حتى يستخدم المستخدم `--acknowledge-license` بعد التحقق من حقوق المصدر؛ كما يرفض استبدال ملف سبق تنزيله. الاتصال بالشبكة اختياري ومرتبط بالمصادر ومفاتيح API المتاحة. `setup` يعرض خطة فقط دون `--yes`.

## ملاحظات أمان ودقة

- `play-check` يعتمد على ffprobe/ffmpeg وبنية MP4، وليس تجربة فعلية على أجهزة iPhone أو WhatsApp؛ توافق جميع الأجهزة غير مضمون.
- ملف MP4 ناقص أو بلا `moov` لا يصلح بإعادة التغليف، وقد يحتاج إعادة الرندر.
- `status` و`last` يتابعان الأعمال التي يسجلها هذا المشغّل **محليًا فقط**، لا كل العمليات أو محادثات ChatGPT. الحالة يمكن أن تكون `running` أو `done` أو `failed` أو `stopped`.
- تم الاحتفاظ بـPhysics & Math وBlender Pro وREA Ultra وVisual Forge وUltra Mind وExpert Council وMedia Hunter القديم دون الكتابة فوق شفراتها.
- استُبعدت من الدمج المباشر إضافات Chrome وCloud Browser وثنائي APK لأنها تحتاج تفويضًا/بيئة منفصلة وفحوصًا إضافية، وتبقى موجودة في الأرشيف الأصلي الذي رفعه المستخدم.
- لم تُجرَ عمليات تثبيت أو نشر أو ربط مستودع GitHub أو صرف أرصدة، ولم تتغير ملفات المستخدم الأصلية.

## النتائج

- **322 اختبارًا ناجحًا** في مجموعات متباينة: 24 لاختبارات Guardian/Repo Fusion الأصلية، و12 للتحقق الجديد للإصدار 10.10، و150 لتوافق 10.9/10.8 Visual/10.7 REA/10.6 Creativity، و136 لتوافق Blender/Council/Ultra Mind/Media Hunter وبوابة 10.
- اختبارات الرندر اعتمدت على وسائط **اصطناعية**؛ تشغيل واجهات خارجية أو البحث الشبكي غير مدرجين.
- تحقق من `black-dragon/MANIFEST_SHA256.json` ومن `SHA256SUMS.txt` لأي فحص سلامة محلي. هذه بصمات **سلامة** وليست توقيعًا من طرف ثالث.

للتفاصيل والقيود راجع: `references/GUARDIAN_MERGE_V1010.md` و`TEST_REPORT.md`.
