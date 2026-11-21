# 🌹 NEXT_AGENT_HANDOFF — ابدأ من هنا دون إعادة الشغل

**تاريخ التوثيق:** 2026-11-21. **المشروع:** `kosif199022-jpg/golden-dragon-alloy-private/red-rose`. **الاسم النهائي:** الوردة الحمراء (Red Rose).

## 1. المطلوب الثابت من المستخدم

- هدف واحد نهائي: **مهارة واحدة مستقلة** تستوعب ما يمكن إعادة بنائه من السبيكة الذهبية والتنين الأسود وأي مصادر مناسبة؛ لا تعتمد على استدعاء المهارات القديمة وقت التشغيل.
- ذاكرة طويلة الأمد قابلة للاسترجاع مع تعلّم من نتائج التنفيذ الموثقة؛ لا تدريب تلقائي للنموذج ولا نشر للذاكرة الخاصة.
- قدرات فعلية للمونتاج والفيديو/الرسم/التحريك والفيزياء/الأبعاد/التفكير والإبداع والمكتبات المجانية، مع التقدم المستمر والتقارير الواضحة.
- اعتمد المستخدم رؤية نحو 1,400 سؤال/متطلب، **ولم يثبت أن 1,400 سؤال بنصوصها الحرفية وإجاباتها محفوظة أو منفذة**.
- المطلوب الحالي: حفظ الأسئلة وإجاباتها المتاحة والتعليمات بحيث يستطيع أي وكيل جديد إكمال المشروع؛ لا تعيد على المستخدم موافقاته السابقة.

للفصل بين التوجيه والحالة: `QUESTIONS_AND_ANSWERS.md` (35 جوابًا **معاد الصياغة ومُصنّف المصدر**) + `QUESTION_COVERAGE.json` (فجوات النصوص القديمة) + `AGENTS.md` (بروتوكول العمل).

## 2. آخر صورة من أدلة تنفيذ V17

| المعيار | قيمة snapshot | المرجع |
|---|---:|---|
| الإصدار الموثق قبل هذا التسليم | V17 | `RELEASE_MANIFEST_V17.json` |
| المحوّلات المسجلة داخل `REGISTRY` | 15 | `capability_runtime.py` |
| اختبارات V17 المحلية المبلغ عن نجاحها | 154 | `CAPABILITY_LEDGER_V17.md` ونتيجة PR #13 |
| المعرفة المنقولة إلى قاعدة مستقلة محلية على الجهاز وقت التنفيذ السابق | 25,675 ملخصًا/سجلًا وصفيًا | `RELEASE_V10.md`، ليست أدوات قابلة للتنفيذ |
| اكتمال الـ1,400 | **لا** | `RELEASE_MANIFEST_V17.json` |
| آخر دمج V17 على `main` وقت كتابة الملخص | `f487317b451660635c076054effa1fdf2fe5a209` | PR #13 |

**مهم:** snapshot وليس عدادًا حيًا. كل وكيل يفحص `git rev-parse HEAD` و`rose.py capabilities` والاختبارات من جديد. لا يفترض أن مصدر `alloy.db` أو قاعدة ذاكرة المالك متاحان في سحابته.

### المحولات التنفيذية المسجلة (الأسماء المعتمدة في V17)

`knowledge.search`, `knowledge.route`, `knowledge.stats`, `memory.recall`, `learning.record`, `style.list`, `audio.analyze`, `video.verify`, `video.scene_analyze`, `video.recut`, `video.timeline_analyze`, `video.edit_suggest`, `video.preview`, `video.produce`, `character.svg`.

**لا تعتبر سجل قدرة = محرك مستقل متقدم أو وكيل AI.** `video.edit_suggest` اقتراح إحصائي لا يفهم القصة، و`visemes.py` ليس تعرفًا على فونيمات الصوت، و`identity.py` تثبيت ألوان شخصية كرتونية لا ملامح شخص حقيقي.

## 3. أوامر الاستلام والتحقق

ابدأ داخل مجلد `red-rose/` على فرع ميزة نظيف:

```bash
git status --short
git rev-parse HEAD
python rose.py --help
python rose.py doctor
python rose.py capabilities
python -W error::ResourceWarning -m unittest discover -v
```

عند توفر FFmpeg وFFprobe وCairoSVG، نفذ اختبارات فيديو مستقلة؛ لا تستخدم فيديو خاص بالمستخدم أو بياناته إلا بإذن. على النسخة الموثقة:

```bash
python rose.py capability-plan "اصنع مونتاجًا"    # تخطيط فقط
python rose.py edit-suggest INPUT.mp4              # اقتراح بدون تعديل
# بعد مراجعة EDL وموافقة المستخدم فقط:
python rose.py recut INPUT.mp4 edits.json OUT.mp4 --approve-write
python rose.py verify OUT.mp4
```

قد تختلف صيغ المعاملات حسب HEAD الحالي؛ `--help` هو المرجع الفعلي. لا تشغل التصدير بمدخل افتراضي غير موجود.

## 4. الفجوة الكبرى: الأسئلة 1–1400

- **1–400:** أُشير إلى اعتمادها في المحادثات السابقة، لكن لا يوجد أرشيف متحقق من نصوص كل سؤال وإجابة في المستودع الحالي.
- **401–450:** أُشير إلى تفصيل 50 سؤالًا إضافيًا في المحادثات السابقة؛ النصوص الحرفية غير مسترجعة هنا.
- **451–1400:** اعتمد المستخدم المحاور/المقترحات، لكن تفاصيل جميع البنود ليست موثقة في الملفات الحالية.
- توجد طلبات مؤكدة عن **50 سؤالًا لكل من**: التفكير والإبداع، الرياضيات/الأبعاد، أساليب الرسم، المكتبات المجانية، الفيزياء للمونتاج؛ وألف سؤال/قدرة إضافية. **لا تفترض** أن حدود هذه الفئات تطابق نطاقات رقمية معيّنة بلا المصدر الأصلي.
- الملف `QUESTIONS_AND_ANSWERS.md` يحفظ 35 **قرارًا عمليًا بصيغة سؤال وجواب** ولا يدّعي أنه الأرشيف الكامل للأسئلة التاريخية.

**بروتوكول استرداد السؤال الأصلي:** ابدأ بالملفات والمحادثات التي للمستخدم حق الوصول إليها؛ دوّن المصدر والوقت والنص الحرفي وقرار الموافقة/الرفض. عند غياب المصدر ضع `unresolved` أو `agent-draft-not-user-approved`؛ لا تختلق تأكيدًا ولا تُنسب إجابة آلية للمستخدم.

## 5. خطة الاستكمال مرتبة، مع معيار إغلاق كل بند

**P0 — إغلاق تسليم الوكلاء:** التأكد من وجود `AGENTS.md` في الجذر والنطاق وملف Q&A وتغطية الأسئلة؛ نجاح `test_agent_handoff.py` وباقي الاختبارات. لا تغيّر حالة V17 دون دليل.

**P1 — استرداد السجل الأصلي:** استعادة النصوص 1–450 من المصدر إن أمكن، ثم 451–1400 كما هي فعلًا، بنسب اعتماد ومستندات مؤيدة. إضافة سجل تتبع مستقل (ID، نص، مصدر، إجابة، موافقة، قدرة مرتبطة، اختبارات، مخرجات)، وعدم ملء البنود الغائبة بمحتوى مُخترع.

**P2 — تحويل المعرفة إلى قدرات مثبتة:** اختر مهمة صغيرة عالية الأثر من المراجع المرخّصة (لا تنسخ runtime)؛ اكتب محركًا أصليًا + اختبار وحدة + اختبار تنفيذ + artifact وحالة صلاحيات؛ ثم أدخلها في `capability_runtime.REGISTRY` وسجلّ الأدلة.

**P3 — مونتاج أذكى، دون وعود زائفة:** إضافة تقييم فعلي للقطات (حركة/تكوين/جودة) وربط الصوت بالصورة؛ الإخراج يجب أن يكون EDL قابلًا للمراجعة، وليس حذفًا تلقائيًا. التمييز بين قياسات الصوت والتعرف على الكلام/الأحداث.

**P4 — جودة الإنتاج:** اختبارات رندر 9:16، ثبات هوية أسلوب الرسم، ترجمات عربية RTL، توقيت الكلمات عند توفر مصدر موثوق، فحص MP4 والتزامن، ومراجعة بصرية فعلية.

**P5 — حفظ الحالة:** بعد كل PR، حدث هذا الملف بسجل commit/عدد الاختبارات/ما أُنجز/ما لم يُنجز/أول أمر يستأنف به أي وكيل العمل.

## 6. قالب تسليم يستخدمه كل وكيل عند التوقف

```text
المهمة:
اسم الفرع:
HEAD commit:
ملفات تغيّرت:
اختبارات أُجريت (الأمر والعدد والنتيجة):
مخرجات موجودة فعلًا (المسار/الهاش):
بوابات الأمان والموافقات:
CI (الرابط + النتيجة):
PR/merge state:
ماذا اكتمل فعلًا:
العيوب والمتبقي:
أول أمر واضح للوكيل التالي:
```

**موانع مطلقة:** لا كتابة فوق بيانات المستخدم أو نشرها بلا موافقة؛ لا حفظ أسرار في Git؛ لا نسبة أسئلة أو أجوبة إلى المستخدم بلا مصدر؛ لا الإيحاء بتفعيل 26 ألف قدرة أو إنجاز كل 1,400؛ لا حذف مستودعات المصدر أو استدعائها في تشغيل الوردة الحمراء.


## 7. V18 traceability continuation

A new, intentionally narrow native **read-only** adapter \`qa.trace\` was added to query the documented A01–A35 paraphrases, backed by \`QA_TRACEABILITY.json\` and checked against the runtime registry. It also exposes \`question-audit\` and \`question-trace A17\` without requiring a local SQLite database. This is **not** restoration of historical question texts.

The **V17 snapshot above remains historical**: 15 native adapters and 154 local tests at that previous release. V18 changes the registry to 16 and adds regression coverage; the next agent must obtain the CI run result on the exact V18 commit before claiming it passed. New code: \`qa_trace.py\`, \`test_qa_trace_v18.py\`; main requirement is proof that a mapped ID is registered and missing verbatim sources are not fabricated.

## 8. V19 checkpoint — per-shot technical quality (P3, partial)

```text
المهمة: P3 — قياس تقني فعلي للقطات وربطه بالصوت، والناتج EDL للمراجعة فقط.
اسم الفرع: main محلي (working tree غير مرفوع) — لم يُنشأ فرع ولا PR بعد.
HEAD commit الأساس: 5ce29c33ebf2df0c1ea9b915104f469736fc18d0
ملفات جديدة: shot_quality_v19.py, test_shot_quality_v19.py, CAPABILITY_LEDGER_V19.md, RELEASE_MANIFEST_V19.json
ملفات تغيّرت: capability_runtime.py, rose.py, test_capability_v15.py, test_qa_trace_v18.py, QA_TRACEABILITY.json, README.md, SKILL.md, START_NEXT_AGENT.md, NEXT_AGENT_HANDOFF.md
اختبارات: python -W error::ResourceWarning -m unittest discover → 185 OK (172 قبل التغيير + 13) على Windows 11 / Python 3.12.10 / FFmpeg 9.0.2
مخرجات: تقرير JSON فقط (لا ملفات وسائط)؛ الأرقام المقاسة في CAPABILITY_LEDGER_V19.md
بوابات الأمان: المحوّل read؛ يرفض المعاملات غير المعروفة والروابط؛ التصدير ما زال عبر video.recut بموافقة
CI: لم يُشغَّل — التغيير غير مرفوع
PR/merge state: لا يوجد PR؛ لم يدخل main على GitHub
ماذا اكتمل فعلًا: المحوّل رقم 17 video.shot_score وأمر shot-score واختباراته وتوثيقه
العيوب والمتبقي: العتبات غير مُعايرة على لقطات كاميرا حقيقية؛ لا قياس تكوين/وجوه/تركيز؛ P1 (استرداد نصوص 1–1400) ما زال unresolved؛ P4 لم يبدأ
أول أمر للوكيل التالي: cd red-rose && python rose.py shot-score <فيديو محلي مصرّح به> ثم قارن الأعلام بالمشاهدة الفعلية وعاير LIMITS باختبار جديد
```

**التالي المقترح:** (1) رفع هذا التغيير على فرع + PR وتشغيل CI بعد موافقة المالك. (2) معايرة `LIMITS` على لقطات حقيقية مصرّح بها. (3) P4: اختبار رندر 9:16 وترجمات عربية RTL.
