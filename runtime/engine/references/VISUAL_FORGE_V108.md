# Visual Forge — دمج الإصدار 10.8.0

## المصدر والاستفادة

المدخل: `visual-forge.zip` (27 عنصر ZIP، بينها 20 ملفًا ومجلدات). يحتوي على `scripts/forge.py` و`data/atmospheres.json` و5 أدلة ضمن `references/` وأمثلة صور وبرومبتات. **ملف البيانات يحمل 21 جوًا**، رغم أن وصف SKILL.md يقول 20. لم يحتوي على برامج Kling أو ChatGPT أو مفاتيح خدمات توليد، أو رخصة برمجية صريحة.

نسخة الكود الأصلية محفوظة في `skills/visual-forge/upstream/forge-original.py` لمراجعة الفروق. نسخة التشغيل في `skills/visual-forge/scripts/forge.py` فيها إصلاحان: حفظ قناة الشفافية للصور ونسخ الصوت المضغوط المتوافق دون إعادة ترميز في مسار الفيديو. لا نضمن توافق نسخ الصوت مع كل الحاويات؛ أداة ffmpeg تفشل بوضوح لو لم تدعم الحاوية الكودك.

## الأوامر المدمجة — محليًا دون API مدفوع

```bash
python scripts/dragon.py tool visual-forge doctor
python scripts/dragon.py tool visual-forge atmos                 # الأجواء
python scripts/dragon.py tool visual-forge atmos rain
python scripts/dragon.py tool visual-forge plan --brief "إعلان كوب قهوة تحت المطر" --kind video --shots 2 --ratio 9:16 --out out/coffee
# حرّر out/coffee/plan.json: subject/motion/look/anchors/lighting، إلخ.
python scripts/dragon.py tool visual-forge prompts out/coffee/plan.json
python scripts/dragon.py tool visual-forge verify-prompts out/coffee/prompts/prompt_receipt.json
python scripts/dragon.py tool visual-forge lint out/coffee/prompts/video_01.txt --target kling
python scripts/dragon.py tool visual-forge fx input.png output.png --fx '@rain' --seed 7
python scripts/dragon.py tool visual-forge fx input.mp4 output.mp4 --fx 'rain:0.5,fog:0.2' --seconds 3
python scripts/dragon.py tool visual-forge self-test
```

**تفاصيل مهمة:** `plan` يصنع مسودة تحتاج تعبئة بشرية، وليس فيلمًا. `prompts` يتحقق أولًا من رقم اللقطة الفريد والوصف والحركة والمدد وlint، ثم ينشئ ملفات البرومبتات بإيصال SHA-256 لا يسمح بإعادة الكتابة فوقها. `verify-prompts` يكشف تغيير البرومبت أو الـ plan الأصلي بعد تسجيل البصمة. هذا تحقق سلامة محلي، وليس توقيعًا خارجيًا أو إثبات جودة إبداعية.

`fx` يرندر مؤثرات محلية بالاعتماد على OpenCV/NumPy وffmpeg للفيديو. يرفض الكتابة فوق الأصل أو خرج موجود. يكتب إلى ملف مؤقت ثم ينشر النتيجة بعد نجاح الرندر. التجربة تدعم إبقاء alpha لصور PNG وحفظ حزم AAC الصوتية كما كانت في MP4 المدعوم؛ ينبغي إعادة التحقق مع ملفات وأكواد صوت أخرى. **ليس تصحيحًا بصريًا احترافيًا تلقائيًا**، ولا يعني أن فيديو Kling تولّد.

## متطلبات وتكامل

- Python 3.10+؛ `numpy`, `cv2` للـFX؛ `ffmpeg` و`ffprobe` للفيديو.
- تخطيط الصور والفيديو وبرومبتات ChatGPT/Kling لا يحتاج إلى أي اشتراك عند تشغيلها محليًا. **تشغيل خدمات التوليد نفسها غير موجود هنا** ويحتاج موافقة صريحة على التكلفة والاستخدام.
- لتحسين أفكار المشاهد: `tool creativity`؛ لمراجعتها: `v10 council`؛ للفيديو النهائي: بوابة `v10 gate` و`verify`.
- استخدم صورًا وملفات مرخّصة أو تملك حقوقها، ولا ترفع وسائط خاصة إلى خدمة خارجية دون موافقة.
- كود المصدر أمثلة ومراجع: لا تنقل نجاح الحالات التجريبية على أنه اختبار مشاهد مستخدم حقيقية.

## حالة التحقق

تُوثّق نتائج الاختبارات الفعلية في تقرير الإصدار 10.8؛ لا تعني فحوص الدخول أو Lint تشغيل واجهات ChatGPT/Kling المدفوعة.
