# صندوق أدوات التفكير — التنين الذهبي

22 أداة بتخلّي المساعد يفهم الطلب صح ويطلّعه صح من أول مرة. كلها مستخلصة من المهارات والكتب اللي على الجهاز (من غير ويب). النسخة اللي بتتقري بالكود: `thinking_toolkit.json` في نفس المجلد.

**إزاي تستخدمه:** اختار الأداة على حسب نوع المهمة (عمود «امتى»)، ونفّذ خطواتها، وفي الآخر اسأل «سؤال الفحص». لو إجابته «لأ» يبقى الأداة ماتطبّقتش.
**المسارات:** `~` = `%USERPROFILE%`، وكل المصادر تحت `~/.claude/skills/`.

## فهرس سريع

| # | id | الأداة | امتى |
|---|---|---|---|
| 1 | `polya-four-phases` | مراحل بوليا الأربعة | understand، plan، analyze، debug، estimate |
| 2 | `restate-and-unknowns` | أعد صياغة الطلب | understand، plan |
| 3 | `constraint-ledger` | سجل القيود والكلمات اللي بتقلب المعنى | understand، review، create |
| 4 | `ask-or-assume-gate` | بوابة: أسأل ولا أفترض؟ | understand، plan، communicate |
| 5 | `begin-with-the-end` | ابدأ من الآخر + أرخص تجربة | plan، create، understand |
| 6 | `first-principles` | المبادئ الأولى | analyze، decide، create، plan |
| 7 | `outside-view` | النظرة من برّه (المعدل الأساسي) | estimate، decide، analyze، plan |
| 8 | `fermi-estimate` | تقدير فيرمي | estimate، analyze، plan |
| 9 | `competing-hypotheses` | الفرضيات المتنافسة (ACH) | analyze، debug، decide، understand |
| 10 | `falsify-it` | التكذيب | analyze، review، decide، debug |
| 11 | `inversion` | اعكس | plan، decide، create، review |
| 12 | `premortem` | تشريح قبل الفشل | plan، decide، create، review |
| 13 | `alternatives-before-commit` | بدائل قبل الاختيار + معايير | decide، create، plan |
| 14 | `red-team-council` | الفريق الأحمر ومجلس محامي الشيطان | review، decide، create، analyze |
| 15 | `root-cause-trace` | السبب الجذري | debug، analyze |
| 16 | `minimal-repro` | إعادة إنتاج مصغّرة | debug، review، analyze |
| 17 | `verify-api-not-memory` | الـ API من المصدر مش الذاكرة | debug، create، review، analyze |
| 18 | `independent-verification` | تحقق مستقل | review، debug، analyze، estimate |
| 19 | `feynman-explain-back` | اشرحها ببساطة (Feynman) | learn، understand، review، communicate |
| 20 | `calibrate-and-update` | عاير ثقتك وحدّثها بالدليل | estimate، analyze، decide، communicate، review |
| 21 | `one-big-idea-first` | النتيجة الأول: فكرة واحدة | communicate، create، review |
| 22 | `after-action-review` | مراجعة ما بعد الفعل | learn، review |

---

## بروتوكول الصح من أول مرة

1. **افهم وصنّف:** حدّد العمق (L0 معلومة أو أمر واضح = ① و⑧ بس، L1 = ①②③⑥⑧، L2–L3 = الكل)، ولخّص الطلب بكلامك بمجهوله وشروطه وقيوده — `restate-and-unknowns`، `constraint-ledger`، `polya-four-phases`
2. **أسأل ولا أفترض:** لو الخطر 6 أو أكتر سؤال واحد باختيارات و⭐، غير كده افتراض معلن في أول الرد — `ask-or-assume-gate`
3. **ابدأ من الآخر:** اكتب سطر التسليم ومعيار «صح»، وارجع لورا لحد أول خطوة — `begin-with-the-end`
4. **ارجع خطوة لورا:** المعدل الأساسي والمبادئ الأولى قبل التفاصيل، وأي رقم بفيرمي وكود — `outside-view`، `first-principles`، `fermi-estimate`
5. **ولّد قبل ما تختار:** 2–4 طرق أو تفسيرات مختلفة فعلًا، والدليل اللي يفرّق بينهم — `alternatives-before-commit`، `competing-hypotheses`
6. **نفّذ صغير ومتأرّض:** عيّنة رخيصة الأول، كل API وأمر من المصدر، والباج: إعادة إنتاج مصغّرة ثم سبب جذري — `begin-with-the-end`، `verify-api-not-memory`، `minimal-repro`، `root-cause-trace`
7. **اكسر حلّك:** تشريح قبل الفشل، اعكس، دوّر على الملاحظة اللي تهدّه، وناقد مستقل للحاجات الغالية (L2+) — `premortem`، `inversion`، `falsify-it`، `red-team-council`
8. **اتحقق وسلّم واتعلم:** فحص بطريقة تانية، اشرحه ببساطة، النتيجة أول سطر مع اتقاس/استنتاج/افتراض، وأي تصحيح يبقى درس — `independent-verification`، `feynman-explain-back`، `calibrate-and-update`، `one-big-idea-first`، `after-action-review`

**جاي منين:** على بوليا: ①② افهم · ③④⑤ خطّط · ⑥ نفّذ · ⑦⑧ راجع. وعلى حلقة ultra-mind السبعاوية: ① = ①، ④ = ②، ⑤ = ③، ⑥ = ④، ⑦ = ⑤، ⑧ = ⑥ + ⑦. الخطوتين ② و③ زيادة من planning-mind (بوابة السؤال) وclaude-mind (ابدأ من الآخر)، وتقسيمة L1 من claude-mind.

---

## الأدوات

### 1. مراحل بوليا الأربعة: افهم، خطّط، نفّذ، راجع — `polya-four-phases`
**امتى:** understand، plan، analyze، debug، estimate
1. افهم: اكتب المجهول والمعطيات والشروط قبل أي حل؛ لو مش قادر تكتبهم يبقى لسه مافهمتش.
2. خطّط: دوّر على مسألة حلّيتها قبل كده تشبهها، أو ابدأ بجزء منها أو حالة صغيرة (n=1,2).
3. نفّذ الخطة خطوة خطوة، وافحص كل خطوة لوحدها قبل ما تبني عليها.
4. راجع: رجّع الناتج للشروط الأصلية، وجرّب توصل له بطريقة تانية أو بحالة صغيرة معروفة نتيجتها.

**سؤال الفحص:** هل المجهول والشروط اتكتبوا قبل الحل، والناتج اترجّع عليهم في الآخر؟
**كلمات بتستدعيها:** حل، مسألة، إزاي أعمل، خطوة خطوة، اتزنقت، مش عارف أبدأ منين، لغز، solve، problem، step by step، stuck، puzzle
**المصدر:**
- George Polya — How to Solve It (1945) والمسألة المساعدة: `ultra-mind/references/books.md` §حل المشكلات بند 1 و2
- `ultra-mind/SKILL.md` §2 المرحلة ① (افهم قبل ما تحل)
- `ultra-mind/references/verification.md` §رياضيات/منطق (التعويض العكسي، الحالة الصغيرة)
- `red-dragon/engine/skills/claude-mind/references/reasoning-toolkit.md` أداة 2 و5

### 2. أعد صياغة الطلب: المقال، والمقصود، واللي ناقص — `restate-and-unknowns`
**امتى:** understand، plan
1. اكتب الطلب كجملة واحدة من صياغتك انت؛ أي كلمة فيها جت من تخمين علّم عليها.
2. افصل الكلام الحرفي عن الهدف اللي وراه، وعن اللي هيضيع لو غلطت: وقت، ملف، فلوس، سمعة.
3. في الرسايل الطويلة أو الملزوقة الطلب غالبًا الجملة القصيرة الأخيرة؛ وغلطات الصوت والكيبورد فكّها من السياق وقول فكّيتها إزاي.
4. افتح ردك بـ «فهمت إنك عايز: …» وبعدها «هعمل: …» عشان أي سوء فهم يتصحّح بدري.

**سؤال الفحص:** تقدر تكتب الطلب في جملة من غير كلماته، وتشاور على كل تخمين فيها؟
**كلمات بتستدعيها:** مش واضح، قصدي، يعني، زي ما قلتلك، حاجة كده، ظبطلي، طوّر، شوف ده، I mean، something like، unclear، vague
**المصدر:**
- `ultra-mind/SKILL.md` §2 المرحلة ① (المطلوب فعلًا مقابل المفهوم ضمنيًا)
- `red-dragon/engine/skills/claude-mind/SKILL.md` §1 ① اقرا الإنسان
- `red-dragon/engine/skills/claude-mind/references/reasoning-toolkit.md` أداة 1
- `planning-mind/SKILL.md` §1 افهم (كارت الفهم 6 بنود) و«شكل أول رد»
- `red-dragon/mind/lessons_seed.jsonl` (s01، h28) و`red-dragon/mind/OWNER_ESSENCE.md` §إزاي تقرا كلامه

### 3. سجل القيود والكلمات اللي بتقلب المعنى — `constraint-ledger`
**امتى:** understand، review، create
1. اعمل قايمة مرقّمة بكل شرط: مقاس، مدة، لغة، عدد، ميعاد، ممنوعات، ومعاها الطلب الصغير اللي في آخر الرسالة.
2. علّم كلمات النفي والاستثناء والحدود («مش»، «إلا»، «على الأقل») والوحدات؛ و«نفس» معناها مطابق حرفيًا مش قريب منه.
3. لو الطلب شبه لغز أو مهمة مشهورة، اكتب إيه المختلف هنا عن النسخة المعروفة قبل ما تحل.
4. قبل التسليم امشي على القايمة بند بند، واسأل: رديت على المطلوب ده بالظبط ولا على سؤال أسهل؟

**سؤال الفحص:** هل كل بند في القايمة عليه ✓ في الناتج، ومفيش كلمة اتفهمت حرفيًا وهي مجاز (أو العكس)؟
**كلمات بتستدعيها:** بالظبط، نفس، لازم، ممنوع، من غير، على الأقل، بس، إلا، exactly، must، only، without
**المصدر:**
- `ultra-mind/SKILL.md` §2 المرحلة ① (الكلمات اللي بتقلب المعنى)
- `ultra-mind/references/failure-modes.md` (نسيان قيد، اللغز المشهور المعدّل، استبدال السؤال)
- Daniel Kahneman — Thinking, Fast and Slow (استبدال السؤال الصعب بسؤال أسهل): `ultra-mind/references/books.md` بند 5
- Atul Gawande — The Checklist Manifesto: `ultra-mind/references/books.md` بند 26 و`ultra-mind/references/verification.md`
- `red-dragon/engine/skills/planning-mind/data/council.json` (logic_checks) و`mistakes_seed.jsonl` (M03، M08)
- `red-dragon/engine/skills/claude-mind/SKILL.md` ⑨ انقد نفسك

### 4. بوابة: أسأل ولا أفترض؟ — `ask-or-assume-gate`
**امتى:** understand، plan، communicate
1. أي حاجة تقدر تعرفها من ملف أو أمر أو المحادثة في أقل من دقيقة: اعرفها بنفسك وماتسألش.
2. لكل بند ناقص ادّي الأثر وعدم اليقين درجة من 0 لـ3؛ حاصل الضرب 6 أو أكتر يبقى اسأل، غير كده افترض وأعلن.
3. اسأل سؤال واحد باختيارات مش سؤال مفتوح، أولها مقترحك ⭐ وسببه، واشتغل في المستقل عن الإجابة وانت مستني.
4. لو قال «ناقشني» أو «ساعدني أفكر»: سؤال واحد في المرة بترتيب GROW: الهدف، الوضع واللي اتجرّب، الاختيارات، الخطوة الجاية.

**سؤال الفحص:** هل كل سؤال اتسأل كانت إجابته هتغيّر الناتج، وظهرت فعلًا في الناتج بعد ما اتجاوب؟
**كلمات بتستدعيها:** اسألني لو مش واضح، مش متأكد، اللي تشوفه، نفّذ، ناقشني، ساعدني أفكر، مش عارف عايز إيه، ask me، clarify، your call، help me think، not sure
**المصدر:**
- `planning-mind/SKILL.md` §2 قرّر: أسأل ولا أفترض (الخطر = الأثر × عدم اليقين)
- `planning-mind/references/asking.md` §2 (3 فلاتر قبل أي سؤال) و§6 (بعد الإجابة)
- `planning-mind/references/research-basis.md` §1 (Clarify When Necessary؛ Knowing but Not Showing)
- `red-dragon/engine/skills/claude-mind/SKILL.md` §2 إمتى أسأل وإمتى أتصرف
- John Whitmore — Coaching for Performance (GROW): `coaching-grow/SKILL.md` 场景一
- 关键跨越(新手篇) — خلّي اللي قدامك يختار من اختيارات مش يجاوب سؤال مفتوح: `first-time-manager/SKILL.md` 场景三
- `red-dragon/mind/OWNER_ESSENCE.md` §بيتضايق من إيه (أسئلة الموافقة الروتينية)

### 5. ابدأ من الآخر: التسليم ودليله، وبعدين أرخص تجربة — `begin-with-the-end`
**امتى:** plan، create، understand
1. قبل أول أداة اكتب لنفسك: «التسليم: ___ في ___، وهعرف إنه صح لما ___».
2. ارجع لورا من التسليم: كل مرحلة محتاجة إيه قبلها مباشرة؟ لحد ما توصل لأول خطوة تقدر تعملها حالًا.
3. قبل ما تبني جديد: فيه حاجة جاهزة، أداة متثبتة، أو حل ثابت بكود بسيط يعملها؟
4. جرّب على عيّنة (ثواني، صفوف قليلة، صفحة واحدة) قبل الشغل الكامل أو أي خطوة غالية.

**سؤال الفحص:** هل سطر التسليم ومعيار «صح» اتكتبوا قبل أول أداة، والعيّنة نجحت قبل الشغل الكامل؟
**كلمات بتستدعيها:** اعملي، ابنيلي، جهّزلي، عايز ملف، ريل، تقرير، تطبيق، مشروع، build، make، deliver، ship
**المصدر:**
- `red-dragon/engine/skills/claude-mind/SKILL.md` ② ابدأ من الآخر و⑥ نفّذ صغير
- Polya — اشتغل من الآخر للأول: `ultra-mind/references/books.md` بند 1 و`claude-mind/references/reasoning-toolkit.md` أداة 3
- `dragon-genius/SKILL.md` ④ الأرخص الأول و⑤ نفّذ صغير وقابل للرجوع
- `planning-mind/SKILL.md` §4 (أرخص اختبار)
- Antonio Gulli — Agentic Design Patterns (الحل الثابت قبل الوكيل): `agent-design-patterns/SKILL.md` §Core Philosophy

### 6. المبادئ الأولى: ابني من اللي صحيح أكيد — `first-principles`
**امتى:** analyze، decide، create، plan
1. افصل الحقايق المؤكدة (قيود فيزيائية، أرقام مقاسة، شروط صاحب الشغل) عن العادات والافتراضات.
2. اكتب 3–5 افتراضات محدش قالها، واسأل عن كل واحد: لو شلناه، الحل يتغيّر إزاي؟
3. اسأل: المسألة دي حالة من أنهي مبدأ أو نوع مسائل؟ وابني الحل من المبدأ مش من «المعتاد».
4. قسّم الكبيرة لأجزاء أبسط، وحلّها من الأسهل للأصعب، وكل جزء يستخدم ناتج اللي قبله.

**سؤال الفحص:** هل كل جزء في الحل يتبرر بحقيقة مكتوبة، مش بـ«ده اللي بيتعمل عادة»؟
**كلمات بتستدعيها:** من الأساس، من الصفر، ليه لازم كده، أصل المشكلة، فكّر من جديد، مبدأ، first principles، from scratch، fundamentals، rethink، why must
**المصدر:**
- `ultra-mind/SKILL.md` §2 المرحلة ② (فكّك لمبادئ أولى، least-to-most)
- `compounding-operating-system/SKILL.md` §Decision process (بند المبادئ الأولى) و§Output (First Principles)
- René Descartes — Discourse on Method: `ultra-mind/references/books.md` بند 4
- Step-Back Prompting (Zheng et al. 2023) وLeast-to-Most (Zhou et al. 2022): `ultra-mind/references/research.md`
- `red-dragon/engine/skills/claude-mind/references/reasoning-toolkit.md` أداة 14 (اكسر افتراض)

### 7. النظرة من برّه: المعدل الأساسي قبل تفاصيل الحالة — `outside-view`
**امتى:** estimate، decide، analyze، plan
1. حدّد الفئة اللي الحالة دي واحدة منها (مشاريع شبهها، تطبيقات من نوعها، طلبات زيها قبل كده).
2. هات معدل الفئة من مصدر أو سجل حقيقي؛ لو مش متاح قول «مجهول» وماتألّفش رقم.
3. ابدأ من المعدل، وحرّكه بتفاصيل الحالة تحريكات صغيرة، كل واحدة بسببها.
4. أي رقم أو ادعاء قارنه بخط أساس: أكتر من إيه؟ مقارنة بمين؟ في أنهي فترة؟

**سؤال الفحص:** هل التقدير بدأ من رقم الفئة، أو قال صراحة إنه مش متاح، قبل تفاصيل الحالة؟
**كلمات بتستدعيها:** هياخد قد إيه، احتمال، هينجح؟، متوقع، عادة، نسبة، كام في المية، how likely، chances، typically، forecast، base rate
**المصدر:**
- Daniel Kahneman — Outside View / إهمال المعدل الأساسي: `ultra-mind/references/books.md` بند 6
- Philip Tetlock & Dan Gardner — Superforecasting: `ultra-mind/references/books.md` بند 17
- `ultra-mind/SKILL.md` §2 المرحلة ② و`ultra-mind/scripts/scaffold.py` (forecast) و`ultra-mind/references/verification.md` §تنبؤ/تقدير
- `compounding-operating-system/SKILL.md` (المعدلات الأساسية لو متاحة، ومن غير دقة متألّفة)
- `deepread/SKILL.md` §5 Test the reasoning (غياب مجموعة المقارنة أو خط الأساس)

### 8. تقدير فيرمي: فكّك الرقم وخمّن قبل ما تحسب — `fermi-estimate`
**امتى:** estimate، analyze، plan
1. قبل أي حساب اكتب تخمين سريع لحجم النتيجة (عشرات؟ آلاف؟ ملايين؟).
2. فكّك المجهول لحاصل ضرب عوامل تقدر تقدّرها، وادّي كل عامل نطاق (من–لحد) مش رقم واحد.
3. احسب بكود مش في دماغك، والوحدة جنب كل رقم: بت/بايت، ثانية/فريم، 1000/1024.
4. لو الناتج بعيد عن تخمينك بأكتر من 10 أضعاف: فيه وحدة أو عامل غلط، لاقيه قبل ما تسلّم.

**سؤال الفحص:** هل الرقم النهائي نطاق مبني على عوامل، ومتقارن بتخمين مبدئي، ووحداته مكتوبة؟
**كلمات بتستدعيها:** كام، تقريبًا، قدّر، حجم، هياخد وقت قد إيه، تكلفة، مساحة، estimate، how many، how much، ballpark، rough
**المصدر:**
- Fermi Estimation وDouglas Hubbard — How to Measure Anything: `ultra-mind/references/books.md` بند 15 و16
- Tetlock — فكّك السؤال (Fermi-ize): `ultra-mind/references/books.md` بند 17
- `red-dragon/engine/skills/claude-mind/references/reasoning-toolkit.md` أداة 9 و10
- Program-of-Thoughts / PAL: `ultra-mind/references/research.md` و`ultra-mind/references/failure-modes.md` (الحساب الذهني، الوحدات)

### 9. تحليل الفرضيات المتنافسة (ACH) — `competing-hypotheses`
**امتى:** analyze، debug، decide، understand
1. اكتب 2–4 تفسيرات مختلفة فعلًا؛ ولو الادعاء «X سبب Y» ضيف: عامل مُربك، سببية معكوسة، صدفة.
2. لكل تفسير: لو هو اللي صح، إيه اللي لازم يبان؟ ودوّر على الدليل اللي بيميّز بينهم بس.
3. اعمل جدول تفسيرات × أدلة، وعلّم الدليل اللي بيهدم كل تفسير؛ الأقل أدلة ضده يكسب مؤقتًا.
4. ابدأ بالأسباب العادية (مسار أو مجلد غلط، ترميز، نسخة قديمة، كاش) قبل أي تفسير غريب.

**سؤال الفحص:** هل الدليل اللي حسم كان بيفرّق بين التفسيرات، ولا كان هيتوافق مع كلهم؟
**كلمات بتستدعيها:** ليه حصل، السبب، إيه اللي عمل كده، تفسير، غريب، مش منطقي، بسبب، why did، cause، explain why، diagnose
**المصدر:**
- Richards Heuer — Psychology of Intelligence Analysis (ACH): `ultra-mind/references/books.md` بند 11
- Judea Pearl & Dana Mackenzie — The Book of Why (مُربك، سببية معكوسة): `ultra-mind/references/books.md` بند 13
- `ultra-mind/SKILL.md` §2 المرحلة ③ و`ultra-mind/scripts/scaffold.py` (analysis: ACH matrix)
- `planning-mind/SKILL.md` §4 (فرضيات متنافسة)
- `red-dragon/engine/skills/claude-mind/references/reasoning-toolkit.md` أدوات 6 و7 و8

### 10. التكذيب: الملاحظة اللي لو ظهرت تهدّ استنتاجك — `falsify-it`
**امتى:** analyze، review، decide، debug
1. قبل الحكم اكتب: «لو لقيت ___ يبقى أنا غلطان»، وخلّيها حاجة محددة تتقاس.
2. دوّر عليها فعلًا: مثال مضاد، حالة طرفية، أو بيانات جديدة ماشافهاش الحل قبل كده.
3. لو ظهرت عدّل الاستنتاج نفسه بدل ما تدوّر على مبرر يحافظ عليه؛ ولو ماظهرتش قول دوّرت فين.
4. اختبار الكشاف: لو نفس الدليل كان في صف الرأي العكسي، كنت هتصدّقه بنفس السهولة؟

**سؤال الفحص:** هل اتكتبت قبل الحكم ملاحظة محددة كانت هتهدّه، واتدوّر عليها فعلًا؟
**كلمات بتستدعيها:** متأكد؟، أكيد؟، اثبت، راجع كلامك، ده صح؟، ممكن يكون غلط، prove، are you sure، counterexample، falsify، sanity check
**المصدر:**
- Karl Popper — The Logic of Scientific Discovery: `ultra-mind/references/books.md` بند 12
- Julia Galef — The Scout Mindset: `ultra-mind/references/books.md` بند 9
- `ultra-mind/SKILL.md` §2 المرحلة ⑤ و§3 القاعدة 5
- `planning-mind/SKILL.md` §4 (كذّب نفسك)
- `compounding-operating-system/SKILL.md` (بند الـ red-team ومحاولة التكذيب قبل القبول)
- `red-dragon/mind/lessons_seed.jsonl` h09 (نجاح 100% على حالات متظبطة مش دليل)

### 11. اعكس: إيه اللي يضمن الفشل؟ — `inversion`
**امتى:** plan، decide، create، review
1. اقلب السؤال: لو عايز الشغل ده يفشل أكيد، هعمل إيه؟ اكتب 5 حاجات.
2. حوّلهم لقايمة «ماتعملش» وحطها قيود صريحة في الخطة.
3. راجع حلّك الحالي على القايمة؛ لو بيعمل أي بند منها غيّره قبل ما تكمّل.
4. للأفكار الجديدة: اقلب افتراض بديهي واسأل: لو العكس هو الصح، الحل يبقى شكله إيه؟

**سؤال الفحص:** فيه قايمة «ماتعملش» مكتوبة، والحل اتراجع عليها بند بند؟
**كلمات بتستدعيها:** إزاي منفشلش، إيه اللي ممكن يبوّظ، أتجنب إيه، غلطات، ماعملش إيه، عكس، avoid، what not to do، pitfalls، invert
**المصدر:**
- Charlie Munger — The Psychology of Human Misjudgment (Inversion): `ultra-mind/references/books.md` بند 8
- `ultra-mind/SKILL.md` §2 المرحلة ⑤ و`ultra-mind/references/creativity.md` أداة 2 (عكس الافتراضات)
- `red-dragon/engine/skills/claude-mind/SKILL.md` §3 (اعكس السؤال)
- Jim Collins — Good to Great (قايمة «بطّل تعمل» 停止做清单): `good-to-great/SKILL.md` 场景二

### 12. تشريح قبل الفشل (Pre-mortem) — `premortem`
**امتى:** plan، decide، create، review
1. افترض إن الشغل اتسلّم وصاحبه رفضه. اكتب أكتر 3 أسباب محتملة، محددة مش عامة.
2. قصاد كل سبب حط فحص أو احتياط جوه الخطة، ويفضّل في أولها قبل الخطوات الغالية.
3. حدّد الافتراض اللي لو طلع غلط كل حاجة تقع، واختبره بأرخص طريقة دلوقتي.

**سؤال الفحص:** هل كل سبب فشل متوقع ليه فحص أو احتياط باسم خطوة في الخطة؟
**كلمات بتستدعيها:** خطة، هنطلق، قبل ما نبدأ، مخاطر، ممكن يفشل، ماتغلطش، تسليم نهائي، risk، launch، what could go wrong، before we start
**المصدر:**
- Gary Klein — Pre-mortem (HBR 2007) / Sources of Power: `ultra-mind/references/books.md` بند 19
- `ultra-mind/SKILL.md` §2 المرحلة ⑤ و`ultra-mind/references/verification.md` §قرار/خطة
- `planning-mind/SKILL.md` §4 و`red-dragon/engine/skills/claude-mind/SKILL.md` ⑤ و`reasoning-toolkit.md` أداة 13
- `expert-council/references/personas.md` §2 المقعد 1 (المشكّك / الفريق الأحمر)

### 13. ولّد بدائل قبل ما تختار، واختار بمعايير — `alternatives-before-commit`
**امتى:** decide، create، plan
1. اكتب 2–4 طرق مختلفة فعلًا (بإيدك، بأداة موجودة، أو بتغيير تعريف المشكلة)؛ وفي القرارات ضيف «ماتعملش حاجة».
2. حدّد المعايير وأوزانها، وقيّم كل بديل على كل معيار لوحده قبل الحكم الكلي، والحساب بكود.
3. اسأل: القرار يترجع فيه؟ لو أيوه خده بسرعة وجرّب؛ لو لأ بطّأ وزوّد التحقق.
4. في الإبداع: الأفكار الأولى المتوقعة اكتبها وعدّيها لحد 6–10 من فئات مختلفة، وقدّم ⭐ وبديل جريء.

**سؤال الفحص:** هل البدائل مختلفة فعلًا مش نسخ من فكرة واحدة، والاختيار متبرر بمعايير مكتوبة؟
**كلمات بتستدعيها:** أختار، أنهي أحسن، ولا، قارن، بدائل، أفكار، اقترح، قرار، which، compare، options، should I
**المصدر:**
- Tree of Thoughts (Yao et al. 2023): `ultra-mind/references/research.md` و`ultra-mind/SKILL.md` §2 المرحلة ③ و§3 القاعدة 1
- Kahneman, Sibony & Sunstein — Noise؛ Bezos — Type 1 / Type 2 decisions: `ultra-mind/references/books.md` بند 7 و22
- `ultra-mind/references/creativity.md` (تباعد ثم انتقاء) و`ultra-mind/references/verification.md` §قرار/خطة
- `planning-mind/references/workflows.md` §قرار / اختيار / استراتيجية
- `red-dragon/engine/skills/claude-mind/references/reasoning-toolkit.md` أداة 11 و12

### 14. الفريق الأحمر ومجلس محامي الشيطان — `red-team-council`
**امتى:** review، decide، create، analyze
1. ابدأ بناقد واحد ياخد الناتج والطلب بس من غير رأيك، وكلّفه يصطاد الأخطاء مش يمدح ولا يلخّص.
2. للقرار الكبير: 3–5 مقاعد بمعايير مختلفة (خبير، جمهور، عملي، متشكك)، وكل مقعد يحكم لوحده الأول.
3. في أي خلاف: كل طرف يعرض أقوى نسخة من حجة التاني قبل ما يرد، والقياس أو التجربة يحسم.
4. خد الملاحظات اللي صمدت بس، ولو فيه اعتراض قوي لسه قايم اكتبه صراحة جنب الحكم.

**سؤال الفحص:** هل النقد جه من حد ماشافش استنتاجك، ولو الكل اتفق من أول جولة اتطلب هجوم أقوى؟
**كلمات بتستدعيها:** مجلس خبراء، محامي الشيطان، انقد، قيّم، رأي الخبراء، اعترض عليا، red team، devil's advocate، critique، poke holes، second opinion
**المصدر:**
- `expert-council/SKILL.md` و`expert-council/references/council-protocol.md` (جولة مستقلة، اشتباك steelman، تحقيق، حكم)
- Micah Zenko — Red Team؛ Surowiecki — The Wisdom of Crowds؛ Multi-agent Debate (Du et al. 2023): `expert-council/references/council-protocol.md` §1
- `expert-council/references/personas.md` §2 المقاعد الإلزامية و§5 الأنماط الممنوعة
- `dragon-genius/SKILL.md` ⑦ المراجعة العدائية
- `compounding-operating-system/SKILL.md` §Output (Red-Team Critique)
- Antonio Gulli — Agentic Design Patterns (مراجع واحد قبل نقاش وكلاء كتير): `agent-design-patterns/SKILL.md` 场景二

### 15. السبب الجذري: ارجع لورا لحد أول سبب — `root-cause-trace`
**امتى:** debug، analyze
1. اقرا الخطأ للآخر (الـ stack trace كامل)، وافصل العَرَض اللي اتشاف عن أي تشخيص جاهز، حتى لو من المستخدم.
2. من مكان الخطأ اسأل: مين نادى ده وبأنهي قيمة؟ وكرّر السؤال لورا لحد ما تلاقي أول مصدر للقيمة الغلط.
3. قارن بنسخة شبهها شغالة واكتب كل فرق، وبعدين فرضية واحدة مكتوبة: «السبب X لأن Y».
4. صلّح عند المصدر مش عند العَرَض؛ ولو 3 تصليحات فشلت وقّف وراجع التصميم نفسه.

**سؤال الفحص:** تقدر تشاور على السطر أو القيمة اللي بدأت المشكلة، وتشرح ليه التصليح هناك مش عند العَرَض؟
**كلمات بتستدعيها:** مش شغال، باج، خطأ، بيضرب، وقف فجأة، اتكسر، error، crash، bug، failing، broken، exception
**المصدر:**
- `systematic-debugging/SKILL.md` (The Iron Law؛ The Four Phases)
- `systematic-debugging/root-cause-tracing.md` (The Tracing Process؛ Key Principle)
- `dragon-genius/references/agent-ops.md` §5 تشخيص الفشل (أول فشل سبّب الباقي، حد 3 محاولات)
- `red-dragon/engine/skills/claude-mind/SKILL.md` ⑦ اقرا النتيجة و§5 (تصديق تشخيص المستخدم من غير تأكد)

### 16. إعادة إنتاج مصغّرة (Minimal Reproducible Example) — `minimal-repro`
**امتى:** debug، review، analyze
1. اكتب خطوات دقيقة تطلّع المشكلة كل مرة؛ لو مابتتكررش اجمع دليل زيادة بدل التخمين.
2. صغّر: شيل أي حاجة والمشكلة لسه موجودة، لحد أصغر ملف أو أمر أو صف بيطلّعها.
3. حوّل الإعادة لاختبار بيفشل دلوقتي قبل التصليح، وغيّر حاجة واحدة بس في كل مرة.
4. اكسر أضيق نقطة تطلّع الفشل، واتأكد إنه فشل في المكان المقصود وعلى المستوى اللي المستخدم شافه.

**سؤال الفحص:** فيه أمر أو ملف صغير بيطلّع المشكلة كل مرة، وبقى بيعدّي بعد التصليح بس؟
**كلمات بتستدعيها:** بيحصل ساعات، مش بيتكرر، عندي بس، اختبار، جرّب كده، reproduce، repro، flaky، intermittent، test case، minimal example
**المصدر:**
- `systematic-debugging/SKILL.md` Phase 1 (Reproduce Consistently) وPhase 4 (Create Failing Test Case)
- `writing-defect-reports/SKILL.md` §Pick the narrowest injection point و§The anomaly is real; the headline may not be
- `ultra-mind/SKILL.md` §2 المرحلة ④ و`ultra-mind/references/verification.md` §كود/باجات
- `red-dragon/engine/skills/claude-mind/references/reasoning-toolkit.md` أداة 5 (صغّر المسألة)

### 17. الـ API والأوامر من المصدر، مش من الذاكرة — `verify-api-not-memory`
**امتى:** debug، create، review، analyze
1. اعمل قايمة بكل import ودالة وخيار أمر هتستخدمه، واعرف إصدار البرنامج المتثبت فعلًا.
2. اتأكد من كل واحد: --help على النسخة المتثبتة، أو كود المكتبة، أو توثيق الإصدار ده.
3. اللي مش متأكد منه علّم عليه بتعليق «اتأكد إنه موجود في إصدارك»، وماتكتبوش كأنه أكيد.
4. نفس القاعدة للأرقام والأسعار والتواريخ والمسارات: من قياس أو مصدر، والناقص يتعلّم [ناقص] ومايتألّفش.

**سؤال الفحص:** هل كل دالة وخيار في الكود ليهم دليل وجود في الإصدار المتثبت، أو عليهم علامة شك واضحة؟
**كلمات بتستدعيها:** كود، مكتبة، أمر، فلاج، إصدار، سكربت، API، import، function، version، flag، CLI
**المصدر:**
- `strict-api/SKILL.md` (The Only Rule؛ Workflow؛ Anti-Patterns)
- `dragon-genius/SKILL.md` ② أرّض: الحقيقة قبل الكلام
- `red-dragon/engine/skills/claude-mind/SKILL.md` ④ أرّض و§2 (المعلومة الناقصة ماتتألّفش)
- `planning-mind/SKILL.md` §4 (قيس مش افترض)
- `ultra-mind/references/failure-modes.md` (معرفة قديمة، اختراع مصادر)

### 18. تحقق مستقل: عين غير اللي عملت — `independent-verification`
**امتى:** review، debug، analyze، estimate
1. حضّر 3–5 أسئلة فحص محددة، وجاوبها من الصفر كأنك ماشفتش مسودتك.
2. افحص بطريقة غير اللي طلّعت الناتج: شغّل الكود، عوّض في المعادلة، قيس بأداة، اقرا الملف بعد كتابته.
3. اكتب نطاق الفحص (فحصت كام من كام) وحالته: اتأكد، فشل، أو ماتعملش.
4. لو طريقتين طلّعوا نتيجتين مختلفتين ماتختارش واحدة: افهم سبب الاختلاف الأول.

**سؤال الفحص:** هل فيه فحص واحد على الأقل اتعمل بأداة أو طريقة غير اللي طلّعت الناتج؟
**كلمات بتستدعيها:** اتأكد، شغّال؟، خلصت؟، افحص، قيس، تمام؟، جرّبته؟، verify، check، test، confirm، does it work
**المصدر:**
- Chain-of-Verification (Dhuliawala et al. 2023) وHuang et al. 2023: `ultra-mind/references/research.md` و`ultra-mind/SKILL.md` §2 المرحلة ⑥
- `dragon-genius/SKILL.md` ⑥ سلّم التحقق (VERIFIED / FAILED / NOT PERFORMED)
- `red-dragon/engine/skills/claude-mind/SKILL.md` ⑧ و`reasoning-toolkit.md` أداة 16
- `red-dragon/mind/lessons_seed.jsonl` (h15، h16، s48)
- `writing-defect-reports/SKILL.md` §A red gate is not an aside

### 19. اشرحها ببساطة عشان تتأكد إنك فاهم (Feynman) — `feynman-explain-back`
**امتى:** learn، understand، review، communicate
1. من غير ما تبص على المصدر، اشرح الفكرة أو الحل بكلام بسيط من غير ما تشيل «ليه» و«عشان كده».
2. علّم أي جملة مبهمة أو مصطلح من غير شرح أو خطوة متنطّة، وحدّد أول حلقة مكسورة.
3. ارجع للمصدر في الحتة دي بس، وصلّحها بآلية أو مثال ملموس مش بمصطلح تاني.
4. اختبر: طبّق الفكرة على حالة جديدة، وقول حالة ماتنطبقش فيها.

**سؤال الفحص:** تقدر تشرحها من الذاكرة لحد مش متخصص، وتقول إمتى ماتنفعش؟
**كلمات بتستدعيها:** اشرحلي، فهّمني، ببساطة، يعني إيه، إزاي بيشتغل، علّمني، explain، ELI5، how does it work، teach me، in simple terms
**المصدر:**
- Richard Feynman — اشرحها ببساطة / Cargo Cult Science (1974): `ultra-mind/references/books.md` بند 3
- `deepread/references/feynman.md` (Procedure؛ Gap Types؛ Quality Rules)
- `deepread/SKILL.md` §7 Close the learning loop

### 20. عاير ثقتك وحدّثها بالدليل بس — `calibrate-and-update`
**امتى:** estimate، analyze، decide، communicate، review
1. صنّف كل ادعاء مهم: اتقاس، اتستنتج من دليل، ولا مفترض؛ والثقة بكلام محدد زي «مرجّح ~70% لأن…».
2. سمّي الإشارة اللي هتحرّك تقديرك، ولما تظهر حدّث بخطوة صغيرة مش بقفزة.
3. لو صاحب الشغل اعترض: غيّر رأيك لو فيه دليل أو حجة جديدة بس، وإلا وضّح بأدب ليه.
4. ماتعمّمش أبعد من اللي قسته: الادعاء على قد المستوى والنطاق اللي اتفحص فعلًا.

**سؤال الفحص:** هل كل جملة مهمة في الرد واضح هي اتقاست ولا اتستنتجت ولا اتفترضت؟
**كلمات بتستدعيها:** متأكد قد إيه، احتمال، توقعك، رأيك، إنت غلطان، لأ مش كده، how sure، confidence، probability، you're wrong، update
**المصدر:**
- Philip Tetlock & Dan Gardner — Superforecasting (تحديث بخطوات صغيرة، فرّق بين 60% و70%): `ultra-mind/references/books.md` بند 17 و`ultra-mind/SKILL.md` §2 المرحلة ⑦
- Sharma et al. 2023 (Sycophancy) وKadavath et al. 2022: `ultra-mind/references/research.md`
- `red-dragon/engine/skills/claude-mind/references/reasoning-toolkit.md` §معايرة الثقة
- `deepread/SKILL.md` §4 (labels الثقة الأربعة، ومن غير دقة رقمية مزيفة)
- `dragon-genius/SKILL.md` ⑧ التسليم (اتأكد بدليل / استنتاج / مجهول / ماتفحصش)
- `writing-defect-reports/SKILL.md` — القاعدة الأساسية: «publish the claim you actually measured, at the layer you measured it»

### 21. النتيجة الأول: فكرة واحدة لقارئ محدد — `one-big-idea-first`
**امتى:** communicate، create، review
1. حدّد مين هيقرا وهيعمل إيه بعدها، واكتب الفكرة الأساسية في جملة واحدة.
2. أول سطر: النتيجة أو مسار الملف كامل أو نعم/لأ؛ بعدها السبب في سطرين، والتفاصيل لو لازمة.
3. أي جدول أو رسمة أو فقرة: اكتب «القارئ هيطلع منها بـ ___»؛ لو ماعرفتش احذفها.
4. اشطب الحشو وإعادة السؤال، وأي كود أو قيمة هتتنسخ حطها في بلوك لوحدها.

**سؤال الفحص:** لو القارئ قرا أول سطر بس، هيعرف النتيجة والخطوة الجاية؟
**كلمات بتستدعيها:** لخّص، اكتب، تقرير، اعرض، قدّم، رسمة، شرايح، summary، report، present، chart، slides
**المصدر:**
- Cole Nussbaumer Knaflic — Storytelling with Data (الجمهور، الفكرة الكبيرة في جملة، الفعل المطلوب): `data-storytelling/SKILL.md` 场景一
- `data-visualization-discipline/SKILL.md` 阶段 1 (كل رسمة ليها جملة استنتاج وإلا تتشال)
- `ultra-mind/SKILL.md` §2 المرحلة ⑦ و`ultra-mind/references/verification.md` §كتابة/شرح
- `red-dragon/engine/skills/claude-mind/SKILL.md` §4 الكلام: شكل الرد
- `red-dragon/mind/OWNER_ESSENCE.md` §بيحب إيه (المسار ونعم/لأ في أول سطر، والقيم في بلوك يتنسخ)

### 22. مراجعة ما بعد الفعل: كل تصحيح يبقى درس — `after-action-review`
**امتى:** learn، review
1. اكتب التصحيح بكلام صاحب الشغل نفسه، ومعاه: كان المتوقع إيه، حصل إيه، وليه الفرق.
2. حوّله لقاعدة بتبدأ بفعل ومعاها «امتى تنطبق»، وسجّلها في ملف الدروس في نفس الدور.
3. لو الغلطة اتكررت أو النقد على أكتر من نقطة: ده نمط؛ ارجع للبنية وحوّل القاعدة لفحص آلي.
4. في أول أي مهمة شبهها: دوّر في الدروس، واللي يطلع يبقى قيود قبل ما تبدأ.

**سؤال الفحص:** آخر تصحيح من صاحب الشغل بقى قاعدة مكتوبة هتظهر لوحدها في المهمة الجاية الشبيهة؟
**كلمات بتستدعيها:** اتعلم من غلطك، ماتكررش، سجّل الدرس، قلتلك قبل كده، غلط تاني، مش كده، learn from، don't repeat، lesson، mistake again
**المصدر:**
- After-Action Review؛ Matthew Syed — Black Box Thinking؛ Reflexion (Shinn et al. 2023): `expert-council/references/learning-loop.md`
- `dragon-genius/SKILL.md` ⑧ التسليم والتعلم و`dragon-genius/references/lessons.md` (append-only)
- `data-visualization-discipline/SKILL.md` §正文之外 (被批之后：退一步 و迭代：纠正必须当场写回)
- Crucial Accountability — CPR (أول مرة محتوى، التكرار نمط): `crucial-accountability/SKILL.md` 场景一
- `red-dragon/mind/lessons_seed.jsonl` و`red-dragon/engine/skills/planning-mind/data/mistakes_seed.jsonl` (M01–M13)

---

## اللي اتشال أو اندمج

- **«5 Whys» باسمه (Toyota):** المصادر المحددة ماعلّمتهوش كطريقة؛ book-to-skill ذكر اسمه بس كمثال على دقة التسمية. مكانه اتحط التتبّع لورا من `systematic-debugging/root-cause-tracing.md` (نفس الفكرة: اسأل «إيه اللي سبّب ده؟» لحد أول مصدر). الاسم موجود في `~/.claude/skills/analyse-problem` وkosif-superpowers، بس دول برّه نطاق المصادر وماقريتهمش.
- **Pearl (سلّم السببية):** مش أداة لوحده؛ اندمج في `competing-hypotheses`.
- **دمج تاني:** Noise وBezos Type 1/2 في `alternatives-before-commit`؛ Hubbard وProgram-of-Thoughts في `fermi-estimate`؛ Self-Consistency في `independent-verification`؛ Gawande في `constraint-ledger`؛ Galef في `falsify-it`؛ Step-Back وDescartes في `first-principles`.
- **أدوات الإبداع** (TRIZ، SCAMPER، Bisociation، المصفوفة المورفولوجية، القبعات الست، Po): مااتعملتش أدوات منفصلة عشان سقف الـ 22؛ مرجعها `ultra-mind/references/creativity.md`، وخطوة الإبداع في `alternatives-before-commit` بتنادي عليها.
- **Meadows، Toulmin، Taleb، Rumelt، Boyd OODA، Gall's Law، Sagan، Duke:** موجودين في books.md بس مش في صميم «فهم الطلب صح من أول مرة».
- **behavior-design** (B=MAP والعادات): لتصميم سلوك الناس مش لفهم طلب.
- **brain-efficiency** (المسرح، SCARF، FPC): فكرة «طلّع الذاكرة العاملة برّه دماغك» موجودة أصلًا في dragon-genius ③؛ الباقي لإدارة الناس.
- **devops-three-ways** (WIP، نقطة الاختناق، blameless): لخطوط التسليم والفرق؛ أداة «نقطة الاختناق / 80-20» اتشالت عشان سقف العدد.
- **good-to-great وfirst-time-manager وcoaching-grow وcrucial-accountability:** اتاخد منهم حتة صغيرة بس (قايمة «بطّل تعمل»، أسئلة الاختيارات، ترتيب GROW، CPR) واندمجت؛ الباقي قيادة وإدارة فرق.
- **data-visualization-discipline:** قواعد الرسوم نفسها اتسابت؛ اتاخد جملة الاستنتاج والتراجع بعد النقد الهيكلي.
- **deepread** (شجرة الحجة وخريطة المعرفة): لقراية الكتب؛ اتاخد منها Feynman وlabels الثقة وفحص خط الأساس.
- **agent-design-patterns:** هندسة وكلاء؛ اتاخد منه «الحل الثابت قبل الوكيل» و«مراجع واحد قبل نقاش وكلاء».
- **book-to-skill:** طريقة لتحويل كتاب لمهارة؛ اتاخد منها شكل الصندوق ده بس.

## المصادر اللي اتقرت

كل المسارات تحت `%USERPROFILE%\.claude\skills\`:

- `ultra-mind\SKILL.md`، و`references\books.md`، `creativity.md`، `failure-modes.md`، `research.md`، `verification.md`، و`scripts\scaffold.py`
- `planning-mind\SKILL.md`، و`references\asking.md`، `research-basis.md`، و`examples.md` (جزئي: الأمثلة 2–5)، و`workflows.md` (جزئي: قرار، كتابة، عام)
- `expert-council\SKILL.md`، و`references\council-protocol.md`، `learning-loop.md`، و`personas.md` (جزئي: السطور 1–301 من 425 + العناوين)
- `dragon-genius\SKILL.md`، و`references\agent-ops.md`، `lessons.md`، و`sources.md` و`montage-craft.md` (العناوين بس)
- `agent-design-patterns\SKILL.md` · `systematic-debugging\SKILL.md` و`root-cause-tracing.md` · `strict-api\SKILL.md` · `writing-defect-reports\SKILL.md`
- `deepread\SKILL.md`، و`references\feynman.md`، `knowledge-map.md`
- `red-dragon\SKILL.md` (جزئي: أقسام v2.8 لـ v2.14) · `red-dragon\mind\OWNER_ESSENCE.md` · `red-dragon\mind\lessons_seed.jsonl` (42 درس من 130: owner/meta/test/report) · `red-dragon\mind\understand_tests.json`
- `red-dragon\engine\skills\claude-mind\SKILL.md` و`references\reasoning-toolkit.md` (ملحوظة: claude-mind مش جوه `mind\`، هو في `engine\skills\`)
- `red-dragon\engine\skills\planning-mind\data\council.json` (logic_checks) و`mistakes_seed.jsonl`
- مهارات الكتب: `good-to-great`، `behavior-design`، `brain-efficiency`، `coaching-grow`، `crucial-accountability`، `data-storytelling`، `devops-three-ways`، `first-time-manager`، `compounding-operating-system` (SKILL.md كامل)، و`data-visualization-discipline\SKILL.md` (جزئي: السطور 1–130 و640–747 + العناوين)، و`book-to-skill\SKILL.md` (جزئي: Philosophy وStep 3 وQuality Rules)

**ماتقرتش:** ملفات المجالات في `expert-council\references\domains\`، و`defense-in-depth.md` و`condition-based-waiting.md` في systematic-debugging، وباقي مراجع claude-mind (judgment، failure-modes، playbooks، communication، worked-examples)، ومحادثات `red-dragon\mind\chats\` (200 ملف)، ومراجع data-visualization-discipline، وملفات evals والسكربتات (ماتشغّلش أي سكربت من المهارات).
