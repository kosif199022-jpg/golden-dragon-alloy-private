# أدوات التفكير وسبله (44 أداة من كتب العلماء + 7 سبل)

## السلّم
- ① افهم وصنّف: حدّد العمق (L0 معلومة أو أمر واضح = ① و⑧ بس، L1 = ①②③⑥⑧، L2–L3 = الكل)، ولخّص الطلب بكلامك بمجهوله وشروطه وقيوده — restate-and-unknowns، constraint-ledger، polya-four-phases · من الكتب: concept-mapping، question-substitution، fast-slow-switch
- ② أسأل ولا أفترض: لو الخطر 6 أو أكتر سؤال واحد باختيارات و⭐، غير كده افتراض معلن في أول الرد — ask-or-assume-gate
- ③ ابدأ من الآخر: اكتب سطر التسليم ومعيار «صح»، وارجع لورا لحد أول خطوة — begin-with-the-end
- ④ ارجع خطوة لورا: المعدل الأساسي والمبادئ الأولى قبل التفاصيل، وأي رقم بفيرمي وكود — outside-view، first-principles، fermi-estimate · من الكتب: plausibility-ledger، anchor-guard، regression-check
- ⑤ ولّد قبل ما تختار: 2–4 طرق أو تفسيرات مختلفة فعلًا، والدليل اللي يفرّق بينهم — alternatives-before-commit، competing-hypotheses · من الكتب: trigger-question-list، connect-seven-ways، analogy-three-questions، restructure-four-moves، what-if-timeline، scene-staging، concept-from-cases
- ⑥ نفّذ صغير ومتأرّض: عيّنة رخيصة الأول، كل API وأمر من المصدر، والباج: إعادة إنتاج مصغّرة ثم سبب جذري — begin-with-the-end، verify-api-not-memory، minimal-repro، root-cause-trace · من الكتب: structure-the-ideas، materiality-filter، recognize-then-measure
- ⑦ اكسر حلّك: تشريح قبل الفشل، اعكس، دوّر على الملاحظة اللي تهدّه، وناقد مستقل للحاجات الغالية (L2+) — premortem، inversion، falsify-it، red-team-council · من الكتب: wysiati-gap-list، story-vs-odds، substance-over-form، reframe-both-ways، intuition-validity-test، good-decision-five
- ⑧ اتحقق وسلّم واتعلم: فحص بطريقة تانية، اشرحه ببساطة، النتيجة أول سطر مع اتقاس/استنتاج/افتراض، وأي تصحيح يبقى درس — independent-verification، feynman-explain-back، calibrate-and-update، one-big-idea-first، after-action-review

# مراجعة ما بعد الفعل: كل تصحيح يبقى درس
- id: `after-action-review`
- إمتى: ['learn', 'review']

## الخطوات
1. اكتب التصحيح بكلام صاحب الشغل نفسه، ومعاه: كان المتوقع إيه، حصل إيه، وليه الفرق.
2. حوّله لقاعدة بتبدأ بفعل ومعاها «امتى تنطبق»، وسجّلها في ملف الدروس في نفس الدور.
3. لو الغلطة اتكررت أو النقد على أكتر من نقطة: ده نمط؛ ارجع للبنية وحوّل القاعدة لفحص آلي.
4. في أول أي مهمة شبهها: دوّر في الدروس، واللي يطلع يبقى قيود قبل ما تبدأ.

## سؤال الناقد
- آخر تصحيح من صاحب الشغل بقى قاعدة مكتوبة هتظهر لوحدها في المهمة الجاية الشبيهة؟

## المصدر
- After-Action Review؛ Matthew Syed — Black Box Thinking؛ Reflexion (Shinn et al. 2023): ~/.claude/skills/expert-council/references/learning-loop.md
- ~/.claude/skills/dragon-genius/SKILL.md ⑧ التسليم والتعلم و ~/.claude/skills/dragon-genius/references/lessons.md (append-only)
- ~/.claude/skills/data-visualization-discipline/SKILL.md §正文之外 (被批之后：退一步 و 迭代：纠正必须当场写回)
- Crucial Accountability — CPR (أول مرة محتوى، التكرار نمط): ~/.claude/skills/crucial-accountability/SKILL.md 场景一
- ~/.claude/skills/golden-dragon/mind/lessons_seed.jsonl و ~/.claude/skills/golden-dragon/engine/skills/planning-mind/data/mistakes_seed.jsonl (M01–M13)

# ولّد بدائل قبل ما تختار، واختار بمعايير
- id: `alternatives-before-commit`
- إمتى: ['decide', 'create', 'plan']

## الخطوات
1. اكتب 2–4 طرق مختلفة فعلًا (بإيدك، بأداة موجودة، أو بتغيير تعريف المشكلة)؛ وفي القرارات ضيف «ماتعملش حاجة».
2. حدّد المعايير وأوزانها، وقيّم كل بديل على كل معيار لوحده قبل الحكم الكلي، والحساب بكود.
3. اسأل: القرار يترجع فيه؟ لو أيوه خده بسرعة وجرّب؛ لو لأ بطّأ وزوّد التحقق.
4. في الإبداع: الأفكار الأولى المتوقعة اكتبها وعدّيها لحد 6–10 من فئات مختلفة، وقدّم ⭐ وبديل جريء.

## سؤال الناقد
- هل البدائل مختلفة فعلًا مش نسخ من فكرة واحدة، والاختيار متبرر بمعايير مكتوبة؟

## المصدر
- Tree of Thoughts (Yao et al. 2023): ~/.claude/skills/ultra-mind/references/research.md و ~/.claude/skills/ultra-mind/SKILL.md §2 المرحلة ③ و§3 القاعدة 1
- Kahneman, Sibony & Sunstein — Noise؛ Bezos — Type 1 / Type 2 decisions: ~/.claude/skills/ultra-mind/references/books.md بند 7 و22
- ~/.claude/skills/ultra-mind/references/creativity.md (تباعد ثم انتقاء) و ~/.claude/skills/ultra-mind/references/verification.md §قرار/خطة
- ~/.claude/skills/planning-mind/references/workflows.md §قرار / اختيار / استراتيجية
- ~/.claude/skills/golden-dragon/engine/skills/claude-mind/references/reasoning-toolkit.md أداة 11 و12

# التشبيه بثلاث أسئلة
- id: `analogy-three-questions`
- إمتى: ['create', 'analyze', 'debug']

## الخطوات
1. فيه حاجة شبه دي اتحلت قبل كده في مجال تاني؟ (نفس التركيب مش نفس الشكل)
2. النمط مطابق؟ عدد أوجه الشبه وجودتها، وهل فيه سبب حقيقي مش صدفة؟
3. الحل المنقول بيحل مشكلتنا فعلًا؟ التشبيه بيقترح بس، الدليل هو اللي يثبت.

## سؤال الناقد
- التشبيه اتبنى على سبب مشترك واتأكد بدليل، مش بس شكل شبه؟

## المصدر
- Jonathan Greetham — Smart Thinking (2016)
- المرحلة 2، الفصل 11: حل المشاكل بالتشبيه

# حارس المرساة: رقمك قبل رقمهم
- id: `anchor-guard`
- إمتى: ['estimate', 'decide']

## الخطوات
1. قبل ما تبص على أي رقم مقترح (سعر، مدة، نسبة)، اكتب تقديرك انت ومنين جبته.
2. لو شفت الرقم الأول، اعكسه: افترض رقم بعيد في الاتجاه التاني واسأل ليه ممكن يكون صح.
3. قارن تقديرك بالرقم المقترح، وأي فرق كبير اشرحه بسبب مش بإحساس.

## سؤال الناقد
- التقدير اتكتب من مصدر مستقل قبل ما يتأثر برقم مقترح؟

## المصدر
- Daniel Kahneman — Thinking, Fast and Slow (2011)
- الفصل 11: المراسي (Anchoring)

# بوابة: أسأل ولا أفترض؟
- id: `ask-or-assume-gate`
- إمتى: ['understand', 'plan', 'communicate']

## الخطوات
1. أي حاجة تقدر تعرفها من ملف أو أمر أو المحادثة في أقل من دقيقة: اعرفها بنفسك وماتسألش.
2. لكل بند ناقص ادّي الأثر وعدم اليقين درجة من 0 لـ3؛ حاصل الضرب 6 أو أكتر يبقى اسأل، غير كده افترض وأعلن.
3. اسأل سؤال واحد باختيارات مش سؤال مفتوح، أولها مقترحك ⭐ وسببه، واشتغل في المستقل عن الإجابة وانت مستني.
4. لو قال «ناقشني» أو «ساعدني أفكر»: سؤال واحد في المرة بترتيب GROW: الهدف، الوضع واللي اتجرّب، الاختيارات، الخطوة الجاية.

## سؤال الناقد
- هل كل سؤال اتسأل كانت إجابته هتغيّر الناتج، وظهرت فعلًا في الناتج بعد ما اتجاوب؟

## المصدر
- ~/.claude/skills/planning-mind/SKILL.md §2 قرّر: أسأل ولا أفترض (الخطر = الأثر × عدم اليقين)
- ~/.claude/skills/planning-mind/references/asking.md §2 (3 فلاتر قبل أي سؤال) و§6 (بعد الإجابة)
- ~/.claude/skills/planning-mind/references/research-basis.md §1 (Clarify When Necessary؛ Knowing but Not Showing)
- ~/.claude/skills/golden-dragon/engine/skills/claude-mind/SKILL.md §2 إمتى أسأل وإمتى أتصرف
- John Whitmore — Coaching for Performance (GROW): ~/.claude/skills/coaching-grow/SKILL.md 场景一
- 关键跨越(新手篇) — خلّي اللي قدامك يختار من اختيارات مش يجاوب سؤال مفتوح: ~/.claude/skills/first-time-manager/SKILL.md 场景三
- ~/.claude/skills/golden-dragon/mind/OWNER_ESSENCE.md §بيتضايق من إيه (أسئلة الموافقة الروتينية)

# ابدأ من الآخر: التسليم ودليله، وبعدين أرخص تجربة
- id: `begin-with-the-end`
- إمتى: ['plan', 'create', 'understand']

## الخطوات
1. قبل أول أداة اكتب لنفسك: «التسليم: ___ في ___، وهعرف إنه صح لما ___».
2. ارجع لورا من التسليم: كل مرحلة محتاجة إيه قبلها مباشرة؟ لحد ما توصل لأول خطوة تقدر تعملها حالًا.
3. قبل ما تبني جديد: فيه حاجة جاهزة، أداة متثبتة، أو حل ثابت بكود بسيط يعملها؟
4. جرّب على عيّنة (ثواني، صفوف قليلة، صفحة واحدة) قبل الشغل الكامل أو أي خطوة غالية.

## سؤال الناقد
- هل سطر التسليم ومعيار «صح» اتكتبوا قبل أول أداة، والعيّنة نجحت قبل الشغل الكامل؟

## المصدر
- ~/.claude/skills/golden-dragon/engine/skills/claude-mind/SKILL.md ② ابدأ من الآخر و⑥ نفّذ صغير
- Polya — اشتغل من الآخر للأول: ~/.claude/skills/ultra-mind/references/books.md بند 1 و ~/.claude/skills/golden-dragon/engine/skills/claude-mind/references/reasoning-toolkit.md أداة 3
- ~/.claude/skills/dragon-genius/SKILL.md ④ الأرخص الأول و⑤ نفّذ صغير وقابل للرجوع
- ~/.claude/skills/planning-mind/SKILL.md §4 (أرخص اختبار)
- Antonio Gulli — Agentic Design Patterns (الحل الثابت قبل الوكيل): ~/.claude/skills/agent-design-patterns/SKILL.md §Core Philosophy

# عاير ثقتك وحدّثها بالدليل بس
- id: `calibrate-and-update`
- إمتى: ['estimate', 'analyze', 'decide', 'communicate', 'review']

## الخطوات
1. صنّف كل ادعاء مهم: اتقاس، اتستنتج من دليل، ولا مفترض؛ والثقة بكلام محدد زي «مرجّح ~70% لأن…».
2. سمّي الإشارة اللي هتحرّك تقديرك، ولما تظهر حدّث بخطوة صغيرة مش بقفزة.
3. لو صاحب الشغل اعترض: غيّر رأيك لو فيه دليل أو حجة جديدة بس، وإلا وضّح بأدب ليه.
4. ماتعمّمش أبعد من اللي قسته: الادعاء على قد المستوى والنطاق اللي اتفحص فعلًا.

## سؤال الناقد
- هل كل جملة مهمة في الرد واضح هي اتقاست ولا اتستنتجت ولا اتفترضت؟

## المصدر
- Philip Tetlock & Dan Gardner — Superforecasting (تحديث بخطوات صغيرة، فرّق بين 60% و70%): ~/.claude/skills/ultra-mind/references/books.md بند 17 و ~/.claude/skills/ultra-mind/SKILL.md §2 المرحلة ⑦
- Sharma et al. 2023 (Sycophancy) و Kadavath et al. 2022: ~/.claude/skills/ultra-mind/references/research.md
- ~/.claude/skills/golden-dragon/engine/skills/claude-mind/references/reasoning-toolkit.md §معايرة الثقة
- ~/.claude/skills/deepread/SKILL.md §4 (labels الثقة الأربعة، ومن غير دقة رقمية مزيفة)
- ~/.claude/skills/dragon-genius/SKILL.md ⑧ التسليم (اتأكد بدليل / استنتاج / مجهول / ماتفحصش)
- ~/.claude/skills/writing-defect-reports/SKILL.md (القاعدة الأساسية: publish the claim you actually measured, at the layer you measured it)

# تحليل الفرضيات المتنافسة (ACH)
- id: `competing-hypotheses`
- إمتى: ['analyze', 'debug', 'decide', 'understand']

## الخطوات
1. اكتب 2–4 تفسيرات مختلفة فعلًا؛ ولو الادعاء «X سبب Y» ضيف: عامل مُربك، سببية معكوسة، صدفة.
2. لكل تفسير: لو هو اللي صح، إيه اللي لازم يبان؟ ودوّر على الدليل اللي بيميّز بينهم بس.
3. اعمل جدول تفسيرات × أدلة، وعلّم الدليل اللي بيهدم كل تفسير؛ الأقل أدلة ضده يكسب مؤقتًا.
4. ابدأ بالأسباب العادية (مسار أو مجلد غلط، ترميز، نسخة قديمة، كاش) قبل أي تفسير غريب.

## سؤال الناقد
- هل الدليل اللي حسم كان بيفرّق بين التفسيرات، ولا كان هيتوافق مع كلهم؟

## المصدر
- Richards Heuer — Psychology of Intelligence Analysis (ACH): ~/.claude/skills/ultra-mind/references/books.md بند 11
- Judea Pearl & Dana Mackenzie — The Book of Why (مُربك، سببية معكوسة): ~/.claude/skills/ultra-mind/references/books.md بند 13
- ~/.claude/skills/ultra-mind/SKILL.md §2 المرحلة ③ و ~/.claude/skills/ultra-mind/scripts/scaffold.py (analysis: ACH matrix)
- ~/.claude/skills/planning-mind/SKILL.md §4 (فرضيات متنافسة)
- ~/.claude/skills/golden-dragon/engine/skills/claude-mind/references/reasoning-toolkit.md أدوات 6 و7 و8

# من الحالات للفكرة: اعمل مفهوم جديد
- id: `concept-from-cases`
- إمتى: ['create', 'learn', 'analyze']

## الخطوات
1. اجمع الحالات أو الأمثلة المتفرقة جنب بعض.
2. دوّر على اللي بيجمعهم (التقارب) واللي بيفرقهم (التباعد).
3. سمّي الفئة الجديدة اسم قصير وعرّفها في جملة، وبعدين جرّبها على حالة جديدة: بتشرحها؟

## سؤال الناقد
- المفهوم الجديد ليه اسم وتعريف في جملة واتجرّب على حالة ماكانتش في الأمثلة؟

## المصدر
- Jonathan Greetham — Smart Thinking (2016)
- المرحلة 1، الفصل 4: إزاي تبني مفاهيم

# «نقصد إيه بـ…؟»: حلّل المفهوم
- id: `concept-mapping`
- إمتى: ['understand', 'analyze', 'learn']

## الخطوات
1. خد الكلمة المفتاحية في الطلب («أحسن»، «احترافي»، «نجاح») واسأل سؤال ساذج: نقصد بيها إيه هنا بالظبط؟
2. هات 3 أمثلة أكيدة ليها، ومثال أكيد عكسها، وحالة على الحدود.
3. استخرج الصفات المشتركة بين الأمثلة: دي تعريف الشغل، واكتبه في جملة واحدة قبل التنفيذ.

## سؤال الناقد
- الكلمة الغامضة في الطلب بقى ليها تعريف تشغيلي بأمثلة؟

## المصدر
- Jonathan Greetham — Smart Thinking (2016)
- المرحلة 1، الفصل 5: إزاي تحلل المفاهيم (أسئلة سقراط)

# اربط بسبع طرق: التوليف
- id: `connect-seven-ways`
- إمتى: ['create', 'plan', 'analyze']

## الخطوات
1. حط فكرتين أو مجالين جنب بعض، ودوّر بينهم بالترتيب على: تضاد، تناقض، سبب، تشابه، الجزء جوه الكل، الكل من الأجزاء، امتداد منطقي.
2. كل وصلة لقيتها اكتبها لمحة في سطر، واختار أقواها كفرضية.
3. اختبر الفرضية بأرخص طريقة، وعدّلها على النتيجة (ربط ← لمحة ← فرضية ← اختبار ← تعديل).

## سؤال الناقد
- الفكرة الجديدة طلعت من وصلة مكتوبة بين حاجتين، واتختبرت مش بس اتقالت؟

## المصدر
- Jonathan Greetham — Smart Thinking (2016)
- المرحلة 1، الفصل 6: إزاي توصّل الأفكار ببعض

# سجل القيود والكلمات اللي بتقلب المعنى
- id: `constraint-ledger`
- إمتى: ['understand', 'review', 'create']

## الخطوات
1. اعمل قايمة مرقّمة بكل شرط: مقاس، مدة، لغة، عدد، ميعاد، ممنوعات، ومعاها الطلب الصغير اللي في آخر الرسالة.
2. علّم كلمات النفي والاستثناء والحدود («مش»، «إلا»، «على الأقل») والوحدات؛ و«نفس» معناها مطابق حرفيًا مش قريب منه.
3. لو الطلب شبه لغز أو مهمة مشهورة، اكتب إيه المختلف هنا عن النسخة المعروفة قبل ما تحل.
4. قبل التسليم امشي على القايمة بند بند، واسأل: رديت على المطلوب ده بالظبط ولا على سؤال أسهل؟

## سؤال الناقد
- هل كل بند في القايمة عليه ✓ في الناتج، ومفيش كلمة اتفهمت حرفيًا وهي مجاز (أو العكس)؟

## المصدر
- ~/.claude/skills/ultra-mind/SKILL.md §2 المرحلة ① (الكلمات اللي بتقلب المعنى)
- ~/.claude/skills/ultra-mind/references/failure-modes.md (نسيان قيد، اللغز المشهور المعدّل، استبدال السؤال)
- Daniel Kahneman — Thinking, Fast and Slow (استبدال السؤال الصعب بسؤال أسهل): ~/.claude/skills/ultra-mind/references/books.md بند 5
- Atul Gawande — The Checklist Manifesto: ~/.claude/skills/ultra-mind/references/books.md بند 26 و ~/.claude/skills/ultra-mind/references/verification.md
- ~/.claude/skills/golden-dragon/engine/skills/planning-mind/data/council.json (logic_checks) و mistakes_seed.jsonl (M03، M08)
- ~/.claude/skills/golden-dragon/engine/skills/claude-mind/SKILL.md ⑨ انقد نفسك

# التكذيب: الملاحظة اللي لو ظهرت تهدّ استنتاجك
- id: `falsify-it`
- إمتى: ['analyze', 'review', 'decide', 'debug']

## الخطوات
1. قبل الحكم اكتب: «لو لقيت ___ يبقى أنا غلطان»، وخلّيها حاجة محددة تتقاس.
2. دوّر عليها فعلًا: مثال مضاد، حالة طرفية، أو بيانات جديدة ماشافهاش الحل قبل كده.
3. لو ظهرت عدّل الاستنتاج نفسه بدل ما تدوّر على مبرر يحافظ عليه؛ ولو ماظهرتش قول دوّرت فين.
4. اختبار الكشاف: لو نفس الدليل كان في صف الرأي العكسي، كنت هتصدّقه بنفس السهولة؟

## سؤال الناقد
- هل اتكتبت قبل الحكم ملاحظة محددة كانت هتهدّه، واتدوّر عليها فعلًا؟

## المصدر
- Karl Popper — The Logic of Scientific Discovery: ~/.claude/skills/ultra-mind/references/books.md بند 12
- Julia Galef — The Scout Mindset: ~/.claude/skills/ultra-mind/references/books.md بند 9
- ~/.claude/skills/ultra-mind/SKILL.md §2 المرحلة ⑤ و§3 القاعدة 5
- ~/.claude/skills/planning-mind/SKILL.md §4 (كذّب نفسك)
- ~/.claude/skills/compounding-operating-system/SKILL.md (بند الـ red-team ومحاولة التكذيب قبل القبول)
- ~/.claude/skills/golden-dragon/mind/lessons_seed.jsonl h09 (نجاح 100% على حالات متظبطة مش دليل)

# السريع والبطيء: اعرف إمتى تبطّأ
- id: `fast-slow-switch`
- إمتى: ['understand', 'decide', 'review']

## الخطوات
1. أول إجابة بتيجي لوحدها (السريع). اكتبها، بس ماتسلّمهاش لسه.
2. اسأل: فيه أرقام؟ حاجة جديدة عليا؟ تمن الغلط كبير؟ لو أيوه لأي واحد، شغّل البطيء: احسب واكتب الخطوات.
3. قارن الإجابة الأولى باللي طلع من الحساب. الفرق بينهم هو الخطأ اللي كنت هتقع فيه.

## سؤال الناقد
- لو فيه أرقام أو مخاطرة، هل الإجابة اتحسبت خطوة بخطوة مش اتحسّت؟

## المصدر
- Daniel Kahneman — Thinking, Fast and Slow (2011)
- الجزء الأول: النظامين، والعقل الكسلان

# تقدير فيرمي: فكّك الرقم وخمّن قبل ما تحسب
- id: `fermi-estimate`
- إمتى: ['estimate', 'analyze', 'plan']

## الخطوات
1. قبل أي حساب اكتب تخمين سريع لحجم النتيجة (عشرات؟ آلاف؟ ملايين؟).
2. فكّك المجهول لحاصل ضرب عوامل تقدر تقدّرها، وادّي كل عامل نطاق (من–لحد) مش رقم واحد.
3. احسب بكود مش في دماغك، والوحدة جنب كل رقم: بت/بايت، ثانية/فريم، 1000/1024.
4. لو الناتج بعيد عن تخمينك بأكتر من 10 أضعاف: فيه وحدة أو عامل غلط، لاقيه قبل ما تسلّم.

## سؤال الناقد
- هل الرقم النهائي نطاق مبني على عوامل، ومتقارن بتخمين مبدئي، ووحداته مكتوبة؟

## المصدر
- Fermi Estimation و Douglas Hubbard — How to Measure Anything: ~/.claude/skills/ultra-mind/references/books.md بند 15 و16
- Tetlock — فكّك السؤال (Fermi-ize): ~/.claude/skills/ultra-mind/references/books.md بند 17
- ~/.claude/skills/golden-dragon/engine/skills/claude-mind/references/reasoning-toolkit.md أداة 9 و10
- Program-of-Thoughts / PAL: ~/.claude/skills/ultra-mind/references/research.md و ~/.claude/skills/ultra-mind/references/failure-modes.md (الحساب الذهني، الوحدات)

# اشرحها ببساطة عشان تتأكد إنك فاهم (Feynman)
- id: `feynman-explain-back`
- إمتى: ['learn', 'understand', 'review', 'communicate']

## الخطوات
1. من غير ما تبص على المصدر، اشرح الفكرة أو الحل بكلام بسيط من غير ما تشيل «ليه» و«عشان كده».
2. علّم أي جملة مبهمة أو مصطلح من غير شرح أو خطوة متنطّة، وحدّد أول حلقة مكسورة.
3. ارجع للمصدر في الحتة دي بس، وصلّحها بآلية أو مثال ملموس مش بمصطلح تاني.
4. اختبر: طبّق الفكرة على حالة جديدة، وقول حالة ماتنطبقش فيها.

## سؤال الناقد
- تقدر تشرحها من الذاكرة لحد مش متخصص، وتقول إمتى ماتنفعش؟

## المصدر
- Richard Feynman — اشرحها ببساطة / Cargo Cult Science (1974): ~/.claude/skills/ultra-mind/references/books.md بند 3
- ~/.claude/skills/deepread/references/feynman.md (Procedure؛ Gap Types؛ Quality Rules)
- ~/.claude/skills/deepread/SKILL.md §7 Close the learning loop

# المبادئ الأولى: ابني من اللي صحيح أكيد
- id: `first-principles`
- إمتى: ['analyze', 'decide', 'create', 'plan']

## الخطوات
1. افصل الحقايق المؤكدة (قيود فيزيائية، أرقام مقاسة، شروط صاحب الشغل) عن العادات والافتراضات.
2. اكتب 3–5 افتراضات محدش قالها، واسأل عن كل واحد: لو شلناه، الحل يتغيّر إزاي؟
3. اسأل: المسألة دي حالة من أنهي مبدأ أو نوع مسائل؟ وابني الحل من المبدأ مش من «المعتاد».
4. قسّم الكبيرة لأجزاء أبسط، وحلّها من الأسهل للأصعب، وكل جزء يستخدم ناتج اللي قبله.

## سؤال الناقد
- هل كل جزء في الحل يتبرر بحقيقة مكتوبة، مش بـ«ده اللي بيتعمل عادة»؟

## المصدر
- ~/.claude/skills/ultra-mind/SKILL.md §2 المرحلة ② (فكّك لمبادئ أولى، least-to-most)
- ~/.claude/skills/compounding-operating-system/SKILL.md §Decision process (بند المبادئ الأولى) و§Output (First Principles)
- René Descartes — Discourse on Method: ~/.claude/skills/ultra-mind/references/books.md بند 4
- Step-Back Prompting (Zheng et al. 2023) و Least-to-Most (Zhou et al. 2022): ~/.claude/skills/ultra-mind/references/research.md
- ~/.claude/skills/golden-dragon/engine/skills/claude-mind/references/reasoning-toolkit.md أداة 14 (اكسر افتراض)

# القرار الكويس: خمس شروط
- id: `good-decision-five`
- إمتى: ['decide', 'plan', 'review']

## الخطوات
1. مبني على كل المعلومات المتاحة؟ اكتب الناقص.
2. واقعي؟ ويحقق كل الأهداف، مش هدف واحد على حساب الباقي؟ وبأقل تكلفة؟
3. مقبول من اللي هيتأثروا بيه؟ اكتب أصحاب المصلحة واعتراض كل واحد.

## سؤال الناقد
- القرار عدّى الخمسة: معلومات، واقعية، كل الأهداف، كفاءة، قبول؟

## المصدر
- Jonathan Greetham — Smart Thinking (2016)
- المرحلة 3، الفصول 14–17: إزاي تاخد قرار كويس

# تحقق مستقل: عين غير اللي عملت
- id: `independent-verification`
- إمتى: ['review', 'debug', 'analyze', 'estimate']

## الخطوات
1. حضّر 3–5 أسئلة فحص محددة، وجاوبها من الصفر كأنك ماشفتش مسودتك.
2. افحص بطريقة غير اللي طلّعت الناتج: شغّل الكود، عوّض في المعادلة، قيس بأداة، اقرا الملف بعد كتابته.
3. اكتب نطاق الفحص (فحصت كام من كام) وحالته: اتأكد، فشل، أو ماتعملش.
4. لو طريقتين طلّعوا نتيجتين مختلفتين ماتختارش واحدة: افهم سبب الاختلاف الأول.

## سؤال الناقد
- هل فيه فحص واحد على الأقل اتعمل بأداة أو طريقة غير اللي طلّعت الناتج؟

## المصدر
- Chain-of-Verification (Dhuliawala et al. 2023) و Huang et al. 2023: ~/.claude/skills/ultra-mind/references/research.md و ~/.claude/skills/ultra-mind/SKILL.md §2 المرحلة ⑥
- ~/.claude/skills/dragon-genius/SKILL.md ⑥ سلّم التحقق (VERIFIED / FAILED / NOT PERFORMED)
- ~/.claude/skills/golden-dragon/engine/skills/claude-mind/SKILL.md ⑧ و reasoning-toolkit.md أداة 16
- ~/.claude/skills/golden-dragon/mind/lessons_seed.jsonl (h15، h16، s48)
- ~/.claude/skills/writing-defect-reports/SKILL.md §A red gate is not an aside

# امتى تصدّق إحساسك
- id: `intuition-validity-test`
- إمتى: ['decide', 'review']

## الخطوات
1. الإحساس يتصدّق بس لو الثلاثة: بيئة منتظمة ليها قواعد، وممارسة طويلة فيها، ورد فعل سريع بيقولك صح ولا غلط.
2. لو واحد منهم ناقص (سوق، توقع بعيد، حاجة جديدة) عامل الإحساس كفرضية واختبرها.
3. سجّل الإحساس والنتيجة عشان تعرف دقتك بعدين.

## سؤال الناقد
- الحدس اللي اتبنى عليه القرار عدّى الشروط الثلاثة، ولا اتعامل كفرضية؟

## المصدر
- Daniel Kahneman — Thinking, Fast and Slow (2011)
- الفصل 22: حدس الخبير (مع Gary Klein)

# اعكس: إيه اللي يضمن الفشل؟
- id: `inversion`
- إمتى: ['plan', 'decide', 'create', 'review']

## الخطوات
1. اقلب السؤال: لو عايز الشغل ده يفشل أكيد، هعمل إيه؟ اكتب 5 حاجات.
2. حوّلهم لقايمة «ماتعملش» وحطها قيود صريحة في الخطة.
3. راجع حلّك الحالي على القايمة؛ لو بيعمل أي بند منها غيّره قبل ما تكمّل.
4. للأفكار الجديدة: اقلب افتراض بديهي واسأل: لو العكس هو الصح، الحل يبقى شكله إيه؟

## سؤال الناقد
- فيه قايمة «ماتعملش» مكتوبة، والحل اتراجع عليها بند بند؟

## المصدر
- Charlie Munger — The Psychology of Human Misjudgment (Inversion): ~/.claude/skills/ultra-mind/references/books.md بند 8
- ~/.claude/skills/ultra-mind/SKILL.md §2 المرحلة ⑤ و ~/.claude/skills/ultra-mind/references/creativity.md أداة 2 (عكس الافتراضات)
- ~/.claude/skills/golden-dragon/engine/skills/claude-mind/SKILL.md §3 (اعكس السؤال)
- Jim Collins — Good to Great (قايمة «بطّل تعمل» 停止做清单): ~/.claude/skills/good-to-great/SKILL.md 场景二

# فلتر الأهمية النسبية
- id: `materiality-filter`
- إمتى: ['analyze', 'communicate', 'review']

## الخطوات
1. قبل ما تحلل كل حاجة، اسأل: لو المعلومة دي اتشالت أو غلطت، القرار هيتغير؟
2. المهم بالحجم (نسبة كبيرة) أو بالطبيعة (حتى لو صغير: غش، طرف قريب، مخالفة).
3. ركّز الوقت والتقرير على المهم، والباقي سطر واحد.

## سؤال الناقد
- التقرير بيبدأ باللي يغيّر القرار، والتفاصيل اللي مالهاش أثر اتقصّرت؟

## المصدر
- ACCA DipIFR Exam Kit 2025 — الإطار المفاهيمي للتقارير المالية
- الأهمية النسبية: حجمًا وطبيعةً

# إعادة إنتاج مصغّرة (Minimal Reproducible Example)
- id: `minimal-repro`
- إمتى: ['debug', 'review', 'analyze']

## الخطوات
1. اكتب خطوات دقيقة تطلّع المشكلة كل مرة؛ لو مابتتكررش اجمع دليل زيادة بدل التخمين.
2. صغّر: شيل أي حاجة والمشكلة لسه موجودة، لحد أصغر ملف أو أمر أو صف بيطلّعها.
3. حوّل الإعادة لاختبار بيفشل دلوقتي قبل التصليح، وغيّر حاجة واحدة بس في كل مرة.
4. اكسر أضيق نقطة تطلّع الفشل، واتأكد إنه فشل في المكان المقصود وعلى المستوى اللي المستخدم شافه.

## سؤال الناقد
- فيه أمر أو ملف صغير بيطلّع المشكلة كل مرة، وبقى بيعدّي بعد التصليح بس؟

## المصدر
- ~/.claude/skills/systematic-debugging/SKILL.md Phase 1 (Reproduce Consistently) و Phase 4 (Create Failing Test Case)
- ~/.claude/skills/writing-defect-reports/SKILL.md §Pick the narrowest injection point و§The anomaly is real; the headline may not be
- ~/.claude/skills/ultra-mind/SKILL.md §2 المرحلة ④ و ~/.claude/skills/ultra-mind/references/verification.md §كود/باجات
- ~/.claude/skills/golden-dragon/engine/skills/claude-mind/references/reasoning-toolkit.md أداة 5 (صغّر المسألة)

# النتيجة الأول: فكرة واحدة لقارئ محدد
- id: `one-big-idea-first`
- إمتى: ['communicate', 'create', 'review']

## الخطوات
1. حدّد مين هيقرا وهيعمل إيه بعدها، واكتب الفكرة الأساسية في جملة واحدة.
2. أول سطر: النتيجة أو مسار الملف كامل أو نعم/لأ؛ بعدها السبب في سطرين، والتفاصيل لو لازمة.
3. أي جدول أو رسمة أو فقرة: اكتب «القارئ هيطلع منها بـ ___»؛ لو ماعرفتش احذفها.
4. اشطب الحشو وإعادة السؤال، وأي كود أو قيمة هتتنسخ حطها في بلوك لوحدها.

## سؤال الناقد
- لو القارئ قرا أول سطر بس، هيعرف النتيجة والخطوة الجاية؟

## المصدر
- Cole Nussbaumer Knaflic — Storytelling with Data (الجمهور، الفكرة الكبيرة في جملة، الفعل المطلوب): ~/.claude/skills/data-storytelling/SKILL.md 场景一
- ~/.claude/skills/data-visualization-discipline/SKILL.md 阶段 1 (كل رسمة ليها جملة استنتاج وإلا تتشال)
- ~/.claude/skills/ultra-mind/SKILL.md §2 المرحلة ⑦ و ~/.claude/skills/ultra-mind/references/verification.md §كتابة/شرح
- ~/.claude/skills/golden-dragon/engine/skills/claude-mind/SKILL.md §4 الكلام: شكل الرد
- ~/.claude/skills/golden-dragon/mind/OWNER_ESSENCE.md §بيحب إيه (المسار ونعم/لأ في أول سطر، والقيم في بلوك يتنسخ)

# النظرة من برّه: المعدل الأساسي قبل تفاصيل الحالة
- id: `outside-view`
- إمتى: ['estimate', 'decide', 'analyze', 'plan']

## الخطوات
1. حدّد الفئة اللي الحالة دي واحدة منها (مشاريع شبهها، تطبيقات من نوعها، طلبات زيها قبل كده).
2. هات معدل الفئة من مصدر أو سجل حقيقي؛ لو مش متاح قول «مجهول» وماتألّفش رقم.
3. ابدأ من المعدل، وحرّكه بتفاصيل الحالة تحريكات صغيرة، كل واحدة بسببها.
4. أي رقم أو ادعاء قارنه بخط أساس: أكتر من إيه؟ مقارنة بمين؟ في أنهي فترة؟

## سؤال الناقد
- هل التقدير بدأ من رقم الفئة، أو قال صراحة إنه مش متاح، قبل تفاصيل الحالة؟

## المصدر
- Daniel Kahneman — Outside View / إهمال المعدل الأساسي: ~/.claude/skills/ultra-mind/references/books.md بند 6
- Philip Tetlock & Dan Gardner — Superforecasting: ~/.claude/skills/ultra-mind/references/books.md بند 17
- ~/.claude/skills/ultra-mind/SKILL.md §2 المرحلة ② و ~/.claude/skills/ultra-mind/scripts/scaffold.py (forecast) و ~/.claude/skills/ultra-mind/references/verification.md §تنبؤ/تقدير
- ~/.claude/skills/compounding-operating-system/SKILL.md (المعدلات الأساسية لو متاحة، ومن غير دقة متألّفة)
- ~/.claude/skills/deepread/SKILL.md §5 Test the reasoning (غياب مجموعة المقارنة أو خط الأساس)

# دفتر المعقولية: درجة تصديق بالأرقام
- id: `plausibility-ledger`
- إمتى: ['analyze', 'decide', 'estimate', 'debug']

## الخطوات
1. لكل فرضية اكتب درجة تصديق بالأرقام (مجموعهم 100%)، ومفيش 0 ولا 100 إلا لو مستحيل أو مؤكد منطقيًا.
2. مع كل دليل جديد اسأل: الدليل ده أرجح كام مرة لو الفرضية أ صح عن لو ب صح؟ (نسبة الأرجحية).
3. حدّث الأرقام على قد النسبة دي: دليل بيحصل في الحالتين مايحركش حاجة مهما كان مقنع.

## سؤال الناقد
- كل فرضية ليها رقم، والأرقام اتحركت بنسبة أرجحية الدليل مش بقوة انطباعه؟

## المصدر
- E. T. Jaynes — Probability Theory: The Logic of Science (2003)
- الاحتمال كمنطق: القاعدة الحاصلية والجمعية وتحديث بايز

# مراحل بوليا الأربعة: افهم، خطّط، نفّذ، راجع
- id: `polya-four-phases`
- إمتى: ['understand', 'plan', 'analyze', 'debug', 'estimate']

## الخطوات
1. افهم: اكتب المجهول والمعطيات والشروط قبل أي حل؛ لو مش قادر تكتبهم يبقى لسه مافهمتش.
2. خطّط: دوّر على مسألة حلّيتها قبل كده تشبهها، أو ابدأ بجزء منها أو حالة صغيرة (n=1,2).
3. نفّذ الخطة خطوة خطوة، وافحص كل خطوة لوحدها قبل ما تبني عليها.
4. راجع: رجّع الناتج للشروط الأصلية، وجرّب توصل له بطريقة تانية أو بحالة صغيرة معروفة نتيجتها.

## سؤال الناقد
- هل المجهول والشروط اتكتبوا قبل الحل، والناتج اترجّع عليهم في الآخر؟

## المصدر
- George Polya — How to Solve It (1945) والمسألة المساعدة: ~/.claude/skills/ultra-mind/references/books.md §حل المشكلات بند 1 و2
- ~/.claude/skills/ultra-mind/SKILL.md §2 المرحلة ① (افهم قبل ما تحل)
- ~/.claude/skills/ultra-mind/references/verification.md §رياضيات/منطق (التعويض العكسي، الحالة الصغيرة)
- ~/.claude/skills/golden-dragon/engine/skills/claude-mind/references/reasoning-toolkit.md أداة 2 و5

# تشريح قبل الفشل (Pre-mortem)
- id: `premortem`
- إمتى: ['plan', 'decide', 'create', 'review']

## الخطوات
1. افترض إن الشغل اتسلّم وصاحبه رفضه. اكتب أكتر 3 أسباب محتملة، محددة مش عامة.
2. قصاد كل سبب حط فحص أو احتياط جوه الخطة، ويفضّل في أولها قبل الخطوات الغالية.
3. حدّد الافتراض اللي لو طلع غلط كل حاجة تقع، واختبره بأرخص طريقة دلوقتي.

## سؤال الناقد
- هل كل سبب فشل متوقع ليه فحص أو احتياط باسم خطوة في الخطة؟

## المصدر
- Gary Klein — Pre-mortem (HBR 2007) / Sources of Power: ~/.claude/skills/ultra-mind/references/books.md بند 19
- ~/.claude/skills/ultra-mind/SKILL.md §2 المرحلة ⑤ و ~/.claude/skills/ultra-mind/references/verification.md §قرار/خطة
- ~/.claude/skills/planning-mind/SKILL.md §4 و ~/.claude/skills/golden-dragon/engine/skills/claude-mind/SKILL.md ⑤ و reasoning-toolkit.md أداة 13
- ~/.claude/skills/expert-council/references/personas.md §2 المقعد 1 (المشكّك / الفريق الأحمر)

# هل جاوبت سؤال أسهل؟
- id: `question-substitution`
- إمتى: ['understand', 'analyze', 'decide', 'review']

## الخطوات
1. اكتب السؤال الأصلي حرفيًا في سطر.
2. اكتب السؤال اللي إجابتك بتجاوبه فعلًا (مثلًا «هل عاجبني؟» بدل «هل هينجح؟»).
3. لو الاتنين مختلفين، ارجع للأصلي وهات له دليله هو.

## سؤال الناقد
- إجابتك بتجاوب السؤال الأصلي نفسه، ولا سؤال أسهل شبهه؟

## المصدر
- Daniel Kahneman — Thinking, Fast and Slow (2011)
- الفصل 9: الإجابة على سؤال أسهل (الاستبدال)

# اعترف الأول وبعدين قيس
- id: `recognize-then-measure`
- إمتى: ['analyze', 'estimate', 'review']

## الخطوات
1. قبل أي رقم: الحاجة دي ينطبق عليها التعريف أصلًا؟ (متحكم فيها، والأثر محتمل، وتتقاس بشكل موثوق)
2. لو أيوه، اختار طريقة قياس وقولها صراحة (تكلفة، قيمة حالية، قيمة عادلة).
3. عدم اليقين يتكتب جنب الرقم بحياد: من غير تفاؤل ولا تشاؤم مقصود.

## سؤال الناقد
- اتحسم إن الحاجة تتحسب قبل ما تتقاس، وطريقة القياس وعدم اليقين مكتوبين؟

## المصدر
- ACCA DipIFR Exam Kit 2025 — الإطار المفاهيمي للتقارير المالية
- الاعتراف والقياس: ينطبق عليه التعريف؟ وبعدين يتقاس إزاي

# الفريق الأحمر ومجلس محامي الشيطان
- id: `red-team-council`
- إمتى: ['review', 'decide', 'create', 'analyze']

## الخطوات
1. ابدأ بناقد واحد ياخد الناتج والطلب بس من غير رأيك، وكلّفه يصطاد الأخطاء مش يمدح ولا يلخّص.
2. للقرار الكبير: 3–5 مقاعد بمعايير مختلفة (خبير، جمهور، عملي، متشكك)، وكل مقعد يحكم لوحده الأول.
3. في أي خلاف: كل طرف يعرض أقوى نسخة من حجة التاني قبل ما يرد، والقياس أو التجربة يحسم.
4. خد الملاحظات اللي صمدت بس، ولو فيه اعتراض قوي لسه قايم اكتبه صراحة جنب الحكم.

## سؤال الناقد
- هل النقد جه من حد ماشافش استنتاجك، ولو الكل اتفق من أول جولة اتطلب هجوم أقوى؟

## المصدر
- ~/.claude/skills/expert-council/SKILL.md و ~/.claude/skills/expert-council/references/council-protocol.md (جولة مستقلة، اشتباك steelman، تحقيق، حكم)
- Micah Zenko — Red Team؛ Surowiecki — The Wisdom of Crowds؛ Multi-agent Debate (Du et al. 2023): ~/.claude/skills/expert-council/references/council-protocol.md §1
- ~/.claude/skills/expert-council/references/personas.md §2 المقاعد الإلزامية و§5 الأنماط الممنوعة
- ~/.claude/skills/dragon-genius/SKILL.md ⑦ المراجعة العدائية
- ~/.claude/skills/compounding-operating-system/SKILL.md §Output (Red-Team Critique)
- Antonio Gulli — Agentic Design Patterns (مراجع واحد قبل نقاش وكلاء كتير): ~/.claude/skills/agent-design-patterns/SKILL.md 场景二

# اقلب الإطار: مكسب وخسارة، وصورة واسعة
- id: `reframe-both-ways`
- إمتى: ['decide', 'plan']

## الخطوات
1. اكتب الاختيار مرة كمكسب ومرة كخسارة. لو رأيك اتغير يبقى الإطار هو اللي بيقرر مش الحقائق.
2. بص له كواحد من قرارات كتير شبهه (إطار واسع) مش قرار لوحده.
3. اسأل: لو بادئ من الصفر النهارده، هختار نفس الحاجة؟ (عشان التكلفة الغارقة ماتقررش).

## سؤال الناقد
- القرار ثابت لما اتصاغ كمكسب وكخسارة، ومن غير التكلفة اللي راحت؟

## المصدر
- Daniel Kahneman — Thinking, Fast and Slow (2011)
- الجزء الرابع: الاختيارات، النفور من الخسارة والتأطير

# الرجوع للمتوسط: النتيجة الشاذة بترجع
- id: `regression-check`
- إمتى: ['analyze', 'estimate', 'debug']

## الخطوات
1. نتيجة عالية أو واطية جدًا؟ جزء منها حظ، والمرة الجاية غالبًا هتقرّب للمتوسط من غير أي سبب.
2. قبل ما تقول «التغيير ده هو السبب»، اسأل: كانت هترجع لوحدها؟ قارن بحاجة ماتغيّرتش.
3. التوقع = المتوسط + جزء من الانحراف بس، على قد قوة العلاقة.

## سؤال الناقد
- التحسن أو التدهور اتفرّق عن الرجوع الطبيعي للمتوسط بمقارنة؟

## المصدر
- Daniel Kahneman — Thinking, Fast and Slow (2011)
- الفصل 17: الانحدار نحو المتوسط

# أعد صياغة الطلب: المقال، والمقصود، واللي ناقص
- id: `restate-and-unknowns`
- إمتى: ['understand', 'plan']

## الخطوات
1. اكتب الطلب كجملة واحدة من صياغتك انت؛ أي كلمة فيها جت من تخمين علّم عليها.
2. افصل الكلام الحرفي عن الهدف اللي وراه، وعن اللي هيضيع لو غلطت: وقت، ملف، فلوس، سمعة.
3. في الرسايل الطويلة أو الملزوقة الطلب غالبًا الجملة القصيرة الأخيرة؛ وغلطات الصوت والكيبورد فكّها من السياق وقول فكّيتها إزاي.
4. افتح ردك بـ «فهمت إنك عايز: …» وبعدها «هعمل: …» عشان أي سوء فهم يتصحّح بدري.

## سؤال الناقد
- تقدر تكتب الطلب في جملة من غير كلماته، وتشاور على كل تخمين فيها؟

## المصدر
- ~/.claude/skills/ultra-mind/SKILL.md §2 المرحلة ① (المطلوب فعلًا مقابل المفهوم ضمنيًا)
- ~/.claude/skills/golden-dragon/engine/skills/claude-mind/SKILL.md §1 ① اقرا الإنسان
- ~/.claude/skills/golden-dragon/engine/skills/claude-mind/references/reasoning-toolkit.md أداة 1 (أعد صياغة الطلب)
- ~/.claude/skills/planning-mind/SKILL.md §1 افهم (كارت الفهم 6 بنود) و«شكل أول رد»
- ~/.claude/skills/golden-dragon/mind/lessons_seed.jsonl (s01، h28) و ~/.claude/skills/golden-dragon/mind/OWNER_ESSENCE.md §إزاي تقرا كلامه

# اكسر القالب: أربع حركات
- id: `restructure-four-moves`
- إمتى: ['create', 'debug', 'plan']

## الخطوات
1. لو بتعيد نفس الحل اللي نفع قبل كده واتزنقت: غيّر تركيب المشكلة (فكّها أو اقلب ترتيبها).
2. ادخلها من اتجاه تاني (من عند المستخدم، من النهاية، من التكلفة)، أو ابدأ من نقطة تانية.
3. اعمل تركيب جديد: استورد نظرية من مجال تاني، أو غيّر المفهوم الأساسي نفسه.

## سؤال الناقد
- اتجرّبت على الأقل حركة من الأربعة قبل ما تقول مفيش حل؟

## المصدر
- Jonathan Greetham — Smart Thinking (2016)
- المرحلة 2، الفصل 12: كسر أثر الخبرة السابقة (Einstellung)

# السبب الجذري: ارجع لورا لحد أول سبب
- id: `root-cause-trace`
- إمتى: ['debug', 'analyze']

## الخطوات
1. اقرا الخطأ للآخر (الـ stack trace كامل)، وافصل العَرَض اللي اتشاف عن أي تشخيص جاهز، حتى لو من المستخدم.
2. من مكان الخطأ اسأل: مين نادى ده وبأنهي قيمة؟ وكرّر السؤال لورا لحد ما تلاقي أول مصدر للقيمة الغلط.
3. قارن بنسخة شبهها شغالة واكتب كل فرق، وبعدين فرضية واحدة مكتوبة: «السبب X لأن Y».
4. صلّح عند المصدر مش عند العَرَض؛ ولو 3 تصليحات فشلت وقّف وراجع التصميم نفسه.

## سؤال الناقد
- تقدر تشاور على السطر أو القيمة اللي بدأت المشكلة، وتشرح ليه التصليح هناك مش عند العَرَض؟

## المصدر
- ~/.claude/skills/systematic-debugging/SKILL.md (The Iron Law؛ The Four Phases)
- ~/.claude/skills/systematic-debugging/root-cause-tracing.md (The Tracing Process؛ Key Principle)
- ~/.claude/skills/dragon-genius/references/agent-ops.md §5 تشخيص الفشل (أول فشل سبّب الباقي، حد 3 محاولات)
- ~/.claude/skills/golden-dragon/engine/skills/claude-mind/SKILL.md ⑦ اقرا النتيجة و§5 (تصديق تشخيص المستخدم من غير تأكد)

# مسرح الخيال: حوّل الفكرة لمشهد
- id: `scene-staging`
- إمتى: ['create', 'communicate']

## الخطوات
1. حط الفكرة على مسرح: المكان، ومين موجود، وكل واحد عايز إيه.
2. حط عقبة واحدة بتمنع حد من اللي عايزه، وحوار قصير بيكشفها بدل ما تشرحها.
3. اختم المشهد بقلبة (معلومة أو قرار) تخلّي المشهد الجاي لازم يحصل.

## سؤال الناقد
- المشهد فيه رغبة وعقبة وقلبة، والفكرة ظاهرة في الفعل مش في الشرح؟

## المصدر
- Rowling, Thorne & Tiffany — Harry Potter and the Cursed Child (مسرحية)
- بناء المشاهد القصيرة في المسرحية (مين على المسرح، عايز إيه، إيه اللي يقف قدامه)

# القصة ضد الاحتمال: كل تفصيلة بتقلّل
- id: `story-vs-odds`
- إمتى: ['analyze', 'estimate', 'review', 'plan']

## الخطوات
1. فكّ القصة أو الخطة لحلقات لازم كلها تحصل.
2. حط احتمال لكل حلقة واضربهم: 5 حلقات كل واحدة 90% = 59% بس.
3. كل تفصيلة زيادة بتخلّي القصة مقنعة أكتر وأقل احتمالًا؛ قوّي أضعف حلقة أو اختصر السلسلة.

## سؤال الناقد
- احتمال السلسلة كلها اتحسب بالضرب، وأضعف حلقة معروفة؟

## المصدر
- E. T. Jaynes — Probability Theory: The Logic of Science (2003)
- قاعدة الضرب (مع مغالطة «ليندا» عند Kahneman الفصل 15)

# رتّب الأفكار: علاقات المعنى والسبب
- id: `structure-the-ideas`
- إمتى: ['analyze', 'plan', 'understand']

## الخطوات
1. اكتب الصورة كاملة: كل العناصر من غير فلترة.
2. رتّبها هرم: إيه الرئيسي وإيه الفرعي (علاقة معنى)، وإيه اللي بيسبب إيه (علاقة سبب).
3. اختبر واشطب الوصلات الضعيفة، وعلّم فين بتتقابل الأفكار وفين بتتعارض، ومنها اطلع بفرضية.

## سؤال الناقد
- فيه خريطة مكتوبة (هرم أو سلسلة أسباب) قبل الاستنتاج؟

## المصدر
- Jonathan Greetham — Smart Thinking (2016)
- المرحلة 2، الفصل 10: إزاي ترتب أفكارك

# الجوهر قبل الشكل
- id: `substance-over-form`
- إمتى: ['analyze', 'review', 'understand']

## الخطوات
1. انسى اسم الحاجة أو عنوانها، واسأل: إيه اللي اتغيّر فعلًا؟
2. مين شايل المخاطرة ومين واخد المكسب ومين متحكم؟ الإجابة دي هي الحقيقة.
3. لو الشكل والجوهر مختلفين، اكتب الجوهر وعلّم على الفرق.

## سؤال الناقد
- الحكم مبني على اللي حصل فعلًا (مين متحكم وشايل المخاطرة) مش على الاسم؟

## المصدر
- ACCA DipIFR Exam Kit 2025 — الإطار المفاهيمي للتقارير المالية
- التمثيل الصادق: سجّل الحقيقة الاقتصادية مش الاسم القانوني

# قايمة الأسئلة المحفّزة: ولّد قبل ما تحكم
- id: `trigger-question-list`
- إمتى: ['create', 'understand', 'plan', 'learn']

## الخطوات
1. اكتب 8–10 أسئلة روتينية للمجال (مين؟ إيه التكلفة؟ مين المستفيد؟ إيه البدائل؟ إيه اللي يحصل لو…؟).
2. جاوب كل سؤال بأفكار من غير ما تحكم عليها؛ التقييم في مرحلة بعدها.
3. زوّد سؤال واحد ماحدش بيسأله في المجال ده؛ ده غالبًا مكان الفكرة الأصلية.

## سؤال الناقد
- الأفكار اتولّدت من قايمة أسئلة كاملة قبل أي حكم، وفيها سؤال غير معتاد؟

## المصدر
- Jonathan Greetham — Smart Thinking (2016)
- المرحلة 2، الفصل 9: إزاي تولّد أفكارك

# الـ API والأوامر من المصدر، مش من الذاكرة
- id: `verify-api-not-memory`
- إمتى: ['debug', 'create', 'review', 'analyze']

## الخطوات
1. اعمل قايمة بكل import ودالة وخيار أمر هتستخدمه، واعرف إصدار البرنامج المتثبت فعلًا.
2. اتأكد من كل واحد: --help على النسخة المتثبتة، أو كود المكتبة، أو توثيق الإصدار ده.
3. اللي مش متأكد منه علّم عليه بتعليق «اتأكد إنه موجود في إصدارك»، وماتكتبوش كأنه أكيد.
4. نفس القاعدة للأرقام والأسعار والتواريخ والمسارات: من قياس أو مصدر، والناقص يتعلّم [ناقص] ومايتألّفش.

## سؤال الناقد
- هل كل دالة وخيار في الكود ليهم دليل وجود في الإصدار المتثبت، أو عليهم علامة شك واضحة؟

## المصدر
- ~/.claude/skills/strict-api/SKILL.md (The Only Rule؛ Workflow؛ Anti-Patterns)
- ~/.claude/skills/dragon-genius/SKILL.md ② أرّض: الحقيقة قبل الكلام
- ~/.claude/skills/golden-dragon/engine/skills/claude-mind/SKILL.md ④ أرّض و§2 (المعلومة الناقصة ماتتألّفش)
- ~/.claude/skills/planning-mind/SKILL.md §4 (قيس مش افترض)
- ~/.claude/skills/ultra-mind/references/failure-modes.md (معرفة قديمة، اختراع مصادر)

# مُحوّل الزمن: لو اتغيّرت حاجة واحدة
- id: `what-if-timeline`
- إمتى: ['create', 'plan', 'decide']

## الخطوات
1. اختار حدث واحد بس وغيّره (لو ماحصلش، لو حصل بدري، لو حصل لحد تاني).
2. تابع الأثر 3 موجات: اللي يتغير على طول، وبعده، وبعده؛ في كل موجة اكتب مين اتأثر.
3. دوّر على النتيجة اللي محدش كان متوقعها، حلوة أو وحشة؛ هي الفكرة أو الخطر المخفي.

## سؤال الناقد
- التخيل اتبنى على تغيير واحد وتتبّع لـ 3 موجات، وطلع منه حاجة مش متوقعة؟

## المصدر
- Rowling, Thorne & Tiffany — Harry Potter and the Cursed Child (مسرحية)
- فكرة المسرحية: تغيير لحظة في الماضي ومتابعة أثرها

# اللي مش قدامك: قايمة الناقص
- id: `wysiati-gap-list`
- إمتى: ['analyze', 'learn', 'review', 'understand']

## الخطوات
1. القصة اللي في دماغك متماسكة؟ ده مش دليل إنها صح؛ التماسك بييجي من قلة المعلومات.
2. اكتب 3 معلومات لو عرفتها ممكن تقلب الاستنتاج، وهل تقدر تجيبها دلوقتي.
3. اعرض الثقة على قد جودة الدليل وكميته، مش على قد حلاوة القصة.

## سؤال الناقد
- اتكتب إيه الناقص اللي ممكن يقلب الاستنتاج، والثقة على قد الدليل؟

## المصدر
- Daniel Kahneman — Thinking, Fast and Slow (2011)
- الفصل 7: «اللي تشوفه هو كل اللي فيه» (WYSIATI)

## السبل السبعة (`alloy fusion think <السبيل>`)
- سبيل الخيال: `thinking:path-imagination`
- سبيل التفكير العميق: `thinking:path-deep`
- سبيل التفكير الإبداعي: `thinking:path-creative`
- سبيل المنطق والاحتمال: `thinking:path-logic`
- سبيل خطوة بخطوة: `thinking:path-steps`
- سبيل التحليل: `thinking:path-analysis`
- سبيل القرار: `thinking:path-decision`
