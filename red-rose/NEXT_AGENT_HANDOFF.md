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
اسم الفرع: red-rose/v19-shot-quality — PR #17 مفتوح على main.
HEAD commit الأساس: 5ce29c33ebf2df0c1ea9b915104f469736fc18d0
ملفات جديدة: shot_quality_v19.py, test_shot_quality_v19.py, CAPABILITY_LEDGER_V19.md, RELEASE_MANIFEST_V19.json
ملفات تغيّرت: capability_runtime.py, rose.py, test_capability_v15.py, test_qa_trace_v18.py, QA_TRACEABILITY.json, README.md, SKILL.md, START_NEXT_AGENT.md, NEXT_AGENT_HANDOFF.md
اختبارات: python -W error::ResourceWarning -m unittest discover → 185 OK (172 قبل التغيير + 13) على Windows 11 / Python 3.12.10 / FFmpeg 9.0.2
مخرجات: تقرير JSON فقط (لا ملفات وسائط)؛ الأرقام المقاسة في CAPABILITY_LEDGER_V19.md
بوابات الأمان: المحوّل read؛ يرفض المعاملات غير المعروفة والروابط؛ التصدير ما زال عبر video.recut بموافقة
CI: 3 فحوص ناجحة و0 فاشلة على PR #17 عند commit affa7e5 (أعد التحقق على آخر commit)
PR/merge state: PR #17 مفتوح وغير مدموج. تنبيه: PR #16 (فرع feature/red-rose-v18-shot-quality-20261121، محوّل باسم video.shot_quality) مفتوح بنفس الميزة ويتعارض في shot_quality_v19.py — المالك يختار واحدًا فقط
ماذا اكتمل فعلًا: المحوّل رقم 17 video.shot_score وأمر shot-score واختباراته وتوثيقه
العيوب والمتبقي: العتبات غير مُعايرة على لقطات كاميرا حقيقية؛ لا قياس تكوين/وجوه/تركيز؛ P1 (استرداد نصوص 1–1400) ما زال unresolved؛ P4 لم يبدأ
أول أمر للوكيل التالي: cd red-rose && python rose.py shot-score <فيديو محلي مصرّح به> ثم قارن الأعلام بالمشاهدة الفعلية وعاير LIMITS باختبار جديد
```

**التالي المقترح:** (1) قرار المالك بين PR #16 وPR #17 ثم الدمج بموافقته. (2) معايرة `LIMITS` على لقطات حقيقية مصرّح بها. (3) P4: اختبار رندر 9:16 وترجمات عربية RTL.

### سجل البحث عن نصوص الأسئلة 1–1400 (2026-11-21، بلا نتيجة)

طلب المالك تنفيذ «الـ1400 سؤال وإجاباتها المقترحة». بُحث عن النصوص في الأماكن التالية ولم توجد:

- شجرة `main` كاملة (8,262 ملفًا) بالاسم والمحتوى، وقائمة الفروع وطلبات الدمج 1–17.
- جهاز المالك: سطح المكتب والتنزيلات والمستندات (أسماء ملفات ونصوص)، ولا يوجد تصدير محادثات.
- ذاكرة الوردة المحلية: جدول `memories` فارغ؛ `fused_knowledge` (25,675) أوصاف مهارات لا أسئلة.

الخلاصة: النصوص موجودة فقط في المحادثة الأصلية خارج المستودع. **الحالة ما زالت `unresolved`**؛ المطلوب من المالك تصدير المحادثة أو مشاركتها، ثم تُحفظ النصوص حرفيًا بمصدرها قبل أي تنفيذ. لا تُنفَّذ ولا تُؤلَّف أسئلة غير موجودة.
## 9. V20: independent five-source media fusion

Five ZIP inputs were scanned and registered by SHA256. Native original fusion_studio_v20.py and its two tests add fusion.route, fusion.plan, fusion.frame, fusion.render and media.iphone_export, with 2 read-only storyboard/map actions, one read-only SVG frame, and 2 write-approval-gated outputs. V18 original baseline has 16 adapters; V20 branch proposes 21. Local standalone V17-source + V20 integration 174 tests passed; 2-second 24-frame synthetic clay/map video and iPhone-compatible transcode passed full decode. Verify GitHub CI and merged main before stating V20 is released. No fonts, raw source ZIPs, secrets or private SQLite were committed. Source archive fidelity is partial, not fully fused. V19 PR #16/#17 still overlap and require separate reconciliation.

## 10. خطة الـ1,400 المعتمدة من المالك — التنفيذ بالدفعات (ابدأ من هنا)

**المصدر والاعتماد:** أرسل المالك `RED_ROSE_1400_QUESTIONS_WITH_ANSWERS.zip` يوم 2026-11-21 وكتب في الشات «نفذ الاجابات موافق على الكل». الملف محفوظ بلا تعديل في `questions/owner_1400/RED_ROSE_1400.json` (sha256 `0b878ab7…` يطابق مانيفست الأرشيف). الملف نفسه يقول إنه **صياغة جديدة** وليس النصوص الحرفية القديمة. الاعتماد يشمل الإجابات كقرارات تصميم فقط، ولا يشمل الرفع أو الدمج أو التثبيت أو الخدمات المدفوعة أو حذف ملفات المالك.

**البنية:** 1,400 سؤال = 280 موضوعًا × 5 عدسات (العقد، الخوارزمية، اختبار القبول، الصلاحيات والخصوصية، الأداء). المتتبّع `roadmap_1400.py` + `ROADMAP_1400_STATUS.json` لا يرقّي موضوعًا إلا إذا وُجد الموديول والدالة وملف اختبار يستدعيها، ويُعاد التحقق عند كل تحميل.

**الحالة المقاسة (فرع `red-rose/v20-roadmap-1400`، commit `b4d784b`):**

| الدفعة | الفصول | الموديولات | المواضيع |
|---|---|---|---:|
| موجود قبلها | 02.02، 15.01–03، 16.02، 16.05، 20.01، 20.07، 21.04، 25.02، 26.01 | كود V15–V19 | 11 |
| 1 | 05، 08، 19 | geometry_v20، physics_v20، science_v20 | 30 |
| 2 | 04، 09، 11، 24 | thinking_v21، decision_v21، code_analysis_v21، accounting_v21 | 40 |
| 3 | 01، 02 (9)، 03، 26 (9)، 27 | governance_v22، architecture_v22، agents_v22، learning_v22، compose_v22 | 48 |

- **129 من 280 موضوعًا** و**632 من 1,400 سؤالًا** مُجابة في كود مختبر. المتبقي 768 سؤالًا (151 موضوعًا).
- الاختبارات: `python -X utf8 -W error::ResourceWarning -m unittest discover` → **574 OK** (Windows 11، Python 3.12.10، FFmpeg 9.0.2).
- السجل: **35 محوّلًا**؛ الموديولات الحسابية تعمل عبر `capability-run <adapter> '{"op":"…","params":{…}}'` وكلها read.
- دليل حقيقي على المستودع: فحص الاستيراد القديم على 88 ملفًا = صفر استيراد لمحركات التنين/السبيكة؛ فحص التغليف على 149 ملفًا = لا قاعدة خاصة.
- دُمج `main` (PR #18، محوّلات fusion) في الفرع، وأُصلح باج ويندوز في `fusion_studio_v20._font` (كان يبحث عن خطوط لينكس فقط فيسقط 5 اختبارات على ويندوز).
- مسودة منفصلة: `questions/G01–G30.json` = 1,500 سؤال كتبها وكيل بطلب المالك، موسومة `agent-draft-not-user-approved`، لا تُحسب ضمن الـ1,400.

**المتبقي (151 موضوعًا) بالترتيب المقترح:**
1. محض بلا ملفات: 06 الاستايلات، 13 التصميم، 14 الشخصيات، 18 ثلاثي الأبعاد، 22 الويب (أجزاء أوفلاين فقط: robots وتحليل HTML وتطبيع الأرقام)، 10 التطبيقات (توليد في الذاكرة)، 25 الأمن (9)، 07 المكتبات (بيانات الرخص)، 17 المؤثرات (مصفوفات صغيرة).
2. يحتاج ملفات وFFmpeg/SQLite (خارج `PURE_MODULES`، باختبارات مجلد مؤقت وبوابة كتابة): 12 المعرفة، 23 قواعد البيانات، 15 (7)، 16 (8)، 20 (8)، 21 (9)، ثم 28 التكامل النهائي.
3. لا يُرقّى أي موضوع إلى `e2e_verified` بدون إيصال مخرج حقيقي (sha256).

**أول أمر للوكيل التالي:**
```bash
cd red-rose && python rose.py roadmap && python -X utf8 -W error::ResourceWarning -m unittest discover
```
ثم اختر الفصل التالي من القائمة، واتبع نمط `physics_v20.py` (TOPICS/OPS/run)، وأضف المحوّل إلى `PURE_MODULES` و`REGISTRY`، وحدّث `ROADMAP_1400_STATUS.json` وعدّاد الاختبارين `test_capability_v15.py` و`test_qa_trace_v18.py`.

**حالة الرفع:** الفرع محلي فقط وغير مرفوع. PR #17 (V19) مفتوح ومتعارض مع main بعد دمج #18؛ هذا الفرع يحتوي V19 + دمج main + الدفعات 1–3. PR #16 مفتوح ومكرر لـV19.

## 11. خطة الـ1,400 — الحالة النهائية المقاسة (تحل محل أرقام القسم 10)

**الفرع:** `red-rose/v20-roadmap-1400` (محلي، غير مرفوع). **المرجع الحي:** `python rose.py roadmap` — لا تنقل أرقامًا أعلى مما يطبعه.

| المقياس | القيمة |
|---|---:|
| المواضيع (280) | 278 `unit_tested` + 2 `e2e_verified` |
| الأسئلة المُجابة في كود مختبر | **1,398 من 1,400** |
| المحوّلات في السجل | 51 (39 حسابية read، 7 ملفات/وسائط mixed، والباقي V15–V20) |
| الاختبارات | `python -X utf8 -W error::ResourceWarning -m unittest discover` → **970 OK** (Windows 11، Python 3.12.10، FFmpeg 9.0.2، حوالي 3.5 دقيقة) |

**الموضوعان المثبتان end-to-end بإيصال (sha256):**
- 28.04 فيديو متكامل: `67c7a7d8…` (H.264، yuv420p، 270×480، 24 فريمًا، 2.000 ث، فك كامل، وفُحص فريم بالعين).
- 28.09 إصدار محمول: `ec6f4a3d…` (195 ملفًا، لا قواعد خاصة، فُك وتطابقت البصمات وشُغّل الـCLI منه).
- الوسائط نفسها لا تُرفع إلى Git حسب السياسة؛ الإيصال هو الدليل.

**السؤالان الباقيان يحتاجان المالك لا الكود:**
- 1,385 (28.05، عدسة القبول): لقطات شاشة حقيقية على هاتف وحاسوب.
- 1,400 (28.08، عدسة القبول): تقييم بشري لجودة المونتاج مقابل مرجع مرخص.
الأداتان جاهزتان (`release.verify` → `device_checklist` و`edit_rubric`) وتعيدان `needs_human_*` حتى يصل الدليل.

**قيود مهمة اكتُشفت أثناء التنفيذ:**
- FFT بايثون صافٍ على 65,536 عينة يستغرق 8–30 ث؛ صار `load_test` افتراضيًا على حجم smoke والحمل الأقصى بطلب صريح.
- كل موديول يذكر حدوده في `limits` لكل نتيجة (مثلًا: لا فهم دلالي للمشاهد، لا تعرف على وجوه، لا رأي محاسبي مهني، لا اتصال بالشبكة).
- أُصلح باج ويندوز في `fusion_studio_v20._font` القادم من PR #18.

**الرفع:** لم يُرفع شيء من هذا الفرع. يحتوي V19 (PR #17) + دمج main (PR #18) + الدفعات 1–6 + الفصل 28. الرفع/PR يحتاج موافقة المالك الصريحة.

**أول أمر للوكيل التالي:**
```bash
cd red-rose && python rose.py roadmap && python rose.py roadmap-topic 28.05
```

## 12. الصهر الكامل للسبيكة والتنين — V27 (2026-11-22)

**طلب المالك:** «قم بالصهر الكامل فورا»، ثم أثناء العمل: «لا تختبر شيء، اكتفِ بالرأي المبدئي أنها تعمل، ومع تجربة الوردة الحمراء أصلحها». لذلك موديولات V27 **مكتوبة وغير مختبرة** (`coded`)؛ التحقق الوحيد: `py_compile` وتحميل `capability_runtime` بـ55 محوّلًا. أي عطل يظهر عند تجربة المالك يُصلَّح وقتها.

**مقياس الصهر:** `fusion_map_v27.py` يصنّف كل وحدة من الـ25,675 (جدول `fused_knowledge` المحلي الخاص، قراءة فقط) إلى عائلة وفئة: native / guidance / meta_catalog / network / paid / external_app / missing. النتيجة الإجمالية في `FUSION_COVERAGE.json` (أعداد فقط، بلا نصوص خاصة):

| الفئة | الوحدات |
|---|---:|
| native (محوّل أصلي موجود) | 15,180 |
| guidance (منهج/قاعدة محفوظة كمعرفة) | 3,305 |
| meta_catalog (أدوات فهرسة حلّ محلها السجل) | 1,169 |
| network (يحتاج إنترنت؛ الوردة أوفلاين بقرار) | 2,727 |
| paid (خدمة مدفوعة؛ ممنوعة بلا موافقة) | 466 |
| external_app (Blender/Adobe/محرك صوت خارجي) | 302 |
| missing | 2,526 |

- **88.6%** من الوحدات القابلة للصهر (22,180) لها مقابل أصلي. التصنيف بالكلمات المفتاحية (تقريبي)، و«native» تعني وجود محوّل للعائلة لا إعادة كل سلوك قديم.
- الناقص معظمه مهارات كتالوج عامة لمنتجات أطراف ثالثة (2,277) خارج مهمة الوردة.

**المحوّلات الجديدة (coded، غير مختبرة):**
- `motion.core` (motion_v27): 36 منحنى، 27 انتقالًا SVG، 12 حركة كاميرا، انتقالات على الإيقاع.
- `text.motion` (typemotion_v27): 15 أسلوب كتابة متحركة لا يقطّع الحروف العربية، كابشن وكاريوكي من توقيتات مُعطاة، SRT، بطاقات أسماء، مقاسات المنصات.
- `graphics.motion` (graphics_v27): تحويل أشكال، رسم الخط، نيون/خامات بالطلب فقط، جزيئات، رسوم بيانية، خرائط مسار تخطيطية، شروحات، بكسل، موك واجهات، كشف شعار.
- `studio.render` (studio_v27): تايملاين بطبقات → معاينة SVG → رندر MP4 بموافقة مع ميكس AAC مقاس بالـLUFS وducking، 13 تلوينًا لا تُطبَّق إلا بطلب المالك، فحص تسليم. خيارات FFmpeg فيه كُتبت من الذاكرة ولم تُراجع — أول مرشح للإصلاح.

**أول أمر لتجربة المالك:**
```bash
python rose.py capability-run studio.render '{"op":"example_timeline"}'
python rose.py capability-run studio.render '{"op":"preview_frame","params":{"spec":<الناتج>,"t":1.0}}'
```

## 13. V28 — إكمال الصهر: النت والجسور والمدفوع وخطط التشغيل (2026-11-22)

**طلب المالك:** «كمل كله وكل المحتوى حقوق ملكية لي حلله». أُضيفت 4 محوّلات (59 في السجل)، **مكتوبة وغير مختبرة** بطلب المالك؛ مُدرجة في `capability_runtime.CODED_UNTESTED` (8 محوّلات) ويعرضها `release.verify` منفصلة.

| المحوّل | الموديول | يغطي | البوابة |
|---|---|---|---|
| `net.fetch` | net_v28 | DL/WEB/COLLECT/GITHUB/TIKTOK/INSTAGRAM… (2,727 وحدة) | كل اتصال `--approve-write` + قائمة نطاقات + robots + بلا كوكيز/دخول |
| `app.bridge` | bridges_v28 | Blender/Adobe/NLE/Remotion/TTS (302) | تشغيل البرامج والكتابة بموافقة؛ يعيد `not_installed` بصدق |
| `prompt.prepare` | prompts_v28 | GEN/SUNO/GEMINI/PROMPT (466) | لا يتصل بأي خدمة؛ يُنتج طلب موافقة لا يمكن اعتماده من داخله |
| `playbook.library` | playbooks_v28 | مهارات الكتالوج (2,526 كانت ناقصة) | بناء الفهرس كتابة بموافقة؛ الذاكرة الخاصة تُفتح بعلم صريح فقط |

**التحليل المنفّذ فعلًا:** `build_index` على `~/.red-rose/memory.sqlite3` (قراءة فقط، بإذن المالك) → `~/.red-rose/playbooks_v28.sqlite3` محليًا (لا يُرفع): **14,890 خطة تشغيل** من 16,527 صفًا (1,637 مكررًا دُمج)، الثقة: 982 عالية، 8,326 متوسطة، 5,582 ضعيفة؛ الدروس الخاصة مستبعدة. أُصلح عطل ظهر من أول استخدام: البحث كان يرفض الفهرس المشتق لأنه داخل `~/.red-rose`.

**التغطية (`FUSION_COVERAGE.json`):** كل الـ25,675 وحدة لها طريق في الوردة، **لكن بأنواع مختلفة**: 19,654 أصلي/مُستوعب (76.5%)، 2,526 خطة تشغيل مستخلصة آليًا، 3,495 بموافقة أو جسر لبرنامج خارجي. «طريق» ≠ «مختبر».

**قيود:** الاستخراج نصّي تقريبي (أهداف تُقطع أحيانًا)؛ الشبكة والجسور لم تُشغَّل قط؛ بعض أعلام yt-dlp وخيارات FFmpeg كُتبت من الذاكرة.


## V29 — source-guided intelligence (limited independent distillation)

Read `SOURCE_INTELLIGENCE_AUDIT_V29.json`, `V29_INTELLIGENCE_GUIDE.md`, `intelligence_director_v29.py` and its two regression test files. The owner attached ten sources (one includes eight nested skills), including video/motion reference skills, an iPhone utility, a Figma binary and *Thinking, Fast and Slow*. They were reviewed, **not copied whole** or loaded as runtime engines.

`intelligence.director` is a new **read-only** native adapter with three explicit ops: `decision_review`, `storyboard_plan`, `layout_audit`. It adds evidence calibration, bias review, frame-exact storyboard allocation and overflow detection. It is deterministic and cannot understand content like a trained video model. It does not overwrite or render user files. It also cannot guarantee the user's professional/creative outcome. See the guide for commands and limitations.

The V27/V28 set of 8 `CODED_UNTESTED` adapters **remains unverified**. Do not call this full fusion of the source code or a wholesale increase in model IQ.

## V30 — completed supervised storyboard-to-video bridge

The standalone module `storyboard_pipeline_v30.py` connects V29 `storyboard_plan` to V20 `fusion_studio_v20.plan/render_video`, dispatch via `storyboard.pipeline` mixed adapter with `compile` (read) and `render` (approved write). Tests `test_storyboard_pipeline_v30.py` enforce frame exactness, Arabic captions, no silent 3D downgrade, map route validation, no overwrite, approval spoof protection and original 5s MP4 SHA/QA. Does **not** solve cinematic semantic editing or the eight V27–V28 `CODED_UNTESTED` adapters. Run full suite on main, update provenance and test count based on CI; use the V30 guide for commands. Next agent should test those older unverified adapters rather than declaring full fusion.

## V43 — independent app-intelligence and cartoon-reel source fusion

`intelligence.fusion` is a new **read-only** native adapter derived from the uploaded `app-super-mind.skill` (12 readiness dimensions, 9 evidence gates, paired dev/heldout results) and the Abu Kab cartoon RAR (22s/30fps/660-frame scene timeline, deterministic seekable beat contract, character/prop and licensed music checks). Five bounded operations: `readiness`, `ladder`, `paired_eval`, `reel_preflight`, `reel_seek`. See [V43_FUSION_GUIDE.md](V43_FUSION_GUIDE.md), [SOURCE_FUSION_AUDIT_V43.json](SOURCE_FUSION_AUDIT_V43.json) and `examples/abu_kab_reel_v43.json`.

No original archives or media/music/font assets are imported or committed. V43 adds measurable **assessment tools**, not full neural training or an actual replication of the full reel. Do not claim all archived skills are rendered or fully fused. Verify all new tests and existing routing quality gates before merge.

**V43 follow-up:** rebuild/publish `references/OPS_CATALOG.json` from the current native registry when available; `rose_catalog.load()` detects added adapters and builds missing ops in-memory. Verify the remaining pre-existing routing held-out abstention floor without lowering it. For a true visual port, produce licensed assets and independently verify a new H264 MP4, which is outside this partial source distillation.
## V44 checkpoint — 2026-11-23 (unmerged stacked feature)

Branch: `feature/red-rose-v44-quality-feedback-20261123`, branched from `feature/red-rose-v43-abu-kab-super-mind-fusion` (base PR #38 is **unmerged**). New native read-only ops `intelligence.fusion.reel_rhythm` and `intelligence.fusion.feedback_cycle` are in `intelligence_fusion_v43.py`; old five ops remain. `rose_catalog.py` now invalidates stale on-disk/in-memory operation lists, not only adapter names. Added `test_quality_feedback_v44.py` and updated two V43 assertions from 5 to 7 ops; guide: `V44_QUALITY_FEEDBACK_GUIDE.md`.

**Not claimed:** no local Python tests, full-suite CI result, catalogue regeneration, real video render, independently inspected user footage, or automatic learning in this environment. The GitHub changes were committed directly through the connected GitHub integration; the owner desktop was offline at implementation time. The pre-existing on-disk `references/OPS_CATALOG.json` and `references/OPS.md` have a strict drift test and **must be regenerated** on a Python checkout with `python rose.py catalog-build --approve-write`, committed and tested. Do not lower test thresholds or merge while red. Run the three V43/V44 tests and then the entire suite; report actual counts and failures. Memory remains local and can be written only with explicit owner approval. PR stack: V43 #38 → V44 (see open PR).

## V43 — أبو كاب + عقل التطبيق الفائق (partial source fusion)

Two uploaded sources were inspected: `ريل أبو كاب.rar` (688 members, 22s seek-based SVG/JS narrative) and `app-super-mind.skill` (22 files, nine-step improvement ladder and twelve measured organs). Native read-only engines `reel.motion` and `mind.audit` were added and tested in `test_fusion_v43.py`. Consult `FUSION_PROVENANCE_V43.json` and `V43_ABU_CAP_SUPER_MIND_GUIDE.md`. Source music/font/media are NOT committed. V43 does not automatically render the whole original reel, execute the uploaded skill scripts, or install a model. The previous V42 held-out abstention floor problem must be handled separately without weakening its gate.

## V46 checkpoint — 2026-11-24
Branch red-rose-v46-self-maintenance: rose_env.py snapshot, verify_media.py chunked digest, rose_maintenance.py and test_maintenance_v46.py, rose_ext.py registration, V46_MAINTENANCE_GUIDE.md and agent instructions. Run `python rose_maintenance.py audit`, `python -m unittest test_maintenance_v46 test_env_v29 test_verify_media`, then full suite and benchmark. Actual CI and timings pending; no main merge yet. Known auto-repair rule is deliberately limited to legacy whole-file hash allocation.

## Unified V54 checkpoint
Integrated current main e4acb37, V49-V54 (a611f1d), V47-V48 (776cd05) and alternate shot detail. 68 + 3 targeted tests passed; routing freeze and abstention floor failures remain. Read V54_UNIFIED_GUIDE.md and UNIFIED_BRANCH_LEDGER_V54.json. Inspect current HEAD for exact checkpoint; next action is full regression and a separate routing evaluation repair, not lowering the floor.

## V56 device absorption checkpoint
Merged latest main b84909c into unified branch. Source-derived procedural steps, council/hypothesis review, reference index and bounded White queue batch are native. See V56_DRAGON_ABSORPTION.md. 88 distinct focused tests passed (85 + 3); full suite pending, routing freeze mismatch not waived. No claim all source capabilities were implemented. Preserve local-only RE and studio extensions.

## V56 checkpoint — 2026-11-25: «ضيف كل القدرات وكل اللي وصلنا ليه»
```text
المهمة: إدخال ما وصلت إليه جلسة 2026-11-20 (دمج Maven Toon في التنين الذهبي، ودمج كل فروع التنين والسبيكة وkosif-tool) إلى الوردة كقدرات أصلية.
اسم الفرع: claude/golden-dragon-warehouse-restaurant-imnzph (من main b84909c)
ملفات جديدة: reel_craft_v56.py, test_reel_craft_v56.py, V56_REEL_CRAFT_GUIDE.md
ملفات تغيّرت: capability_runtime.py (reel.craft في IO_ADAPTERS وREGISTRY و7 ALIASES), media_library_v35.py (_safe_extract أقوى),
  references/OPS_CATALOG.json + OPS.md (catalog-build), عدّاد المحوّلات 64 ← 65 في 6 اختبارات, DISCOVERIES.md (11 صف), هذا الملف
اختبارات: test_reel_craft_v56 = 12 OK (لينكس، Python 3.13، FFmpeg)؛ الحزمة كاملة: انظر PR (مقارنة مع main على نفس الجهاز)
مخرجات: فيديو اختبار مُركّب 6 ث بالكريدت: 180/180 فريم، صوت MD5 مطابق، gate ✓، فريم بالعين (الكريدت أول وآخر، الكارت آخر 3 ث، العربي متوصّل)
بوابات الأمان: credit_overlay كتابة بـ --approve-write فقط، لا كتابة فوق ملف، staging داخل مجلد الناتج؛ باقي العمليات قراءة
ماذا اكتمل فعلًا: المحوّل 65 reel.craft بخمس عمليات، وفك zip الآمن
العيوب والمتبقي: لم يُعَد بناء محرك Maven Toon نفسه (مرجع فقط)؛ story_plan خطة بلا رندر؛ اختبار الكريدت يتخطّى لو مفيش خط عربي (RED_ROSE_TEST_ARABIC_FONT)
أول أمر للوكيل التالي: cd red-rose && python -m unittest test_reel_craft_v56 -v && python rose.py describe reel.craft.credit_overlay
```

## V62 integration checkpoint
Merged the main media and character changes into the experimental mind candidate. Read V62_MIND_GUIDE.md; fresh regression results required before release. No claim of complete corpus absorption.

## V69 runtime dua gate and ranked search
Read V69_RUNTIME_GUIDE.md. Runtime enforcement is now present at the named entrypoints; old generic dua plans without an explicit hashed asset/word timing contract fail before writes. VN remains analysis only and montage-code remains general-only. V69 search uses bilingual grouped lexical terms and path/title weighting; fixture results in V69_KNOWLEDGE_EVAL.json, not a private-corpus accuracy claim. Keep independent visual/audio, licensing and write gates. Never use alternate paths to evade a failed gate.
