# أبحاث الاستدلال عند النماذج اللغوية — إيه اللي بيشتغل فعلًا

المرجع: أوراق arXiv المذكورة بأسمائها وسنينها. الخلاصة العملية تحت كل بند هي اللي اتنقلت للبروتوكول في SKILL.md.

## تقنيات أثبتت فايدة
| التقنية | الورقة | الفكرة | الدرس العملي |
|---|---|---|---|
| Chain-of-Thought | Wei et al. 2022 | خطوات وسيطة قبل الإجابة | فكّر بخطوات في المسائل متعددة الخطوات؛ مالهاش لازمة في السهل |
| Zero-shot CoT | Kojima et al. 2022 | «Let's think step by step» لوحدها بتحسّن | التفكير المكتوب بيفرق حتى من غير أمثلة |
| Self-Consistency | Wang et al. 2022 | عيّنات استدلال متعددة + تصويت الأغلبية | مسارين مستقلين متفقين = ثقة أعلى؛ اختلافهم = إشارة خطر |
| Least-to-Most | Zhou et al. 2022 | فكّك لمسائل فرعية من الأسهل للأصعب | حل الأجزاء الصغيرة الأول واستخدم نتايجها |
| Plan-and-Solve | Wang et al. 2023 | اعمل خطة الأول بعدين نفّذ | بيقلل خطوات ناقصة وأخطاء حساب |
| Program-of-Thoughts / PAL | Chen et al. 2022؛ Gao et al. 2022 | خلي الكود يعمل الحساب | **أي حساب مهم = كود** |
| Tree of Thoughts | Yao et al. 2023 | استكشاف فروع، تقييم، رجوع للخلف | ولّد بدائل وقيّمها قبل الالتزام (repo: princeton-nlp/tree-of-thought-llm) |
| Graph of Thoughts | Besta et al. 2023 | دمج وتجميع أفكار من فروع مختلفة | أحسن حل أحيانًا تركيبة من فرعين |
| Step-Back Prompting | Zheng et al. 2023 | اسأل عن المبدأ العام الأول | حدد "فئة المسألة" وقانونها قبل التفاصيل |
| Analogical Prompting | Yasunaga et al. 2023 | النموذج يولّد أمثلة مشابهة بنفسه ويحلها | «افتكر 2-3 مسائل شبهها وحلولها» |
| Self-Discover | Zhou et al. 2024 | النموذج يختار ويركّب وحدات استدلال مناسبة للمهمة | اختار الأدوات المناسبة لنوع المهمة (جدول الوحدات في SKILL.md) |
| Chain-of-Verification | Dhuliawala et al. 2023 | أسئلة تحقق تتجاوب **مستقلة** عن المسودة | بيقلل الهلوسة في الحقائق والقوايم |
| ReAct | Yao et al. 2022 | تفكير ↔ فعل بأدوات ↔ ملاحظة | استخدم الأدوات لجمع دليل بدل التخمين |
| Self-Refine | Madaan et al. 2023 | مسودة ← نقد ← تحسين | مفيد للكتابة والكود لما النقد بمعايير محددة |
| Reflexion | Shinn et al. 2023 | تأمل لفظي في الفشل بعد تغذية راجعة | اتعلم من خطأ **ملموس** (اختبار فشل، رسالة خطأ) |
| Multi-agent Debate | Du et al. 2023 | نماذج متعددة تتناقش | آراء مستقلة + نقاش بيحسّن الحقائق والاستدلال |
| Process supervision | Lightman et al. 2023 (Let's Verify Step by Step) | فحص كل خطوة أحسن من فحص النتيجة بس | تحقق من الخطوات الحرجة، مش الرقم النهائي بس |

## تحذيرات (برضه من الأبحاث)
- **Huang et al. 2023 — LLMs Cannot Self-Correct Reasoning Yet**: "راجع إجابتك" من غير معلومة جديدة ممكن **تخرّب** إجابة صحيحة. ← التحقق لازم يكون بأداة أو مسار مستقل أو دليل خارجي.
- **Sharma et al. 2023 (Anthropic) — Towards Understanding Sycophancy**: النماذج بتميل توافق المستخدم حتى لو غلطان. ← ماتغيّرش موقف صحيح من غير حجة جديدة.
- **Kadavath et al. 2022 (Anthropic) — LMs (Mostly) Know What They Know**: النموذج عنده إحساس معقول بثقته. ← استخدمه: لو حاسس بشك، قوله وحدد مصدره.
- **Turpin et al. 2023 — Language Models Don't Always Say What They Think**: التفكير المكتوب ممكن مايبقاش هو السبب الحقيقي للإجابة. ← اختبر النتيجة نفسها، ماتعتمدش إن "الخطوات شكلها سليم".
- أمثلة "الألغاز المشهورة المعدّلة" (مثل نسخ معدّلة من مسألة مونتي هول أو عبور النهر): النماذج بترد بحل النسخة المشهورة. ← اقرا الشروط حرفيًا.

## مستودعات GitHub مفيدة للتعمق
- `anthropics/skills` — هيكل المهارات الرسمي وأمثلة.
- `obra/superpowers` — مهارات عملية زي brainstorming وsystematic-debugging وtest-driven-development وverification-before-completion؛ نفس روح البروتوكول ده: "دليل قبل ادعاء".
- `princeton-nlp/tree-of-thought-llm` — تنفيذ Tree of Thoughts الرسمي.
- `spcl/graph-of-thoughts` — تنفيذ Graph of Thoughts.
- `noahshinn/reflexion` — تنفيذ Reflexion.
- محليًا: `kosif-superpowers/scripts/think.py` — سقالات L0–L6، فيرمي مونت كارلو، تحديث بايزي، قرار موزون.
