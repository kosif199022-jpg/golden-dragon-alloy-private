# 🌹 Prompt — انسخه لأي وكيل جديد ليكمل الوردة الحمراء

> أنت الوكيل التالي المسؤول عن تطوير مهارة «الوردة الحمراء» المستقلة في `kosif199022-jpg/golden-dragon-alloy-private/red-rose`. لا تبدأ من الصفر ولا تفتح أسئلة سبق حسمها بلا سبب.
>
> **اقرأ قبل أن تكتب أي كود:** `AGENTS.md` في الجذر، ثم `red-rose/AGENTS.md`، `red-rose/NEXT_AGENT_HANDOFF.md`، `red-rose/QUESTIONS_AND_ANSWERS.md`، `red-rose/QUESTION_COVERAGE.json`، `red-rose/SKILL.md`، `red-rose/README.md`، ثم افحص `capability_runtime.REGISTRY` والـHEAD الحالي.
>
> **احترم قراراتي السابقة:** هدف واحد: مهارة واحدة مستقلة، لا استدعاء وقت التشغيل لمهارات التنين أو السبيكة. ذاكرة محلية مستمرة، تعلم من نتائج موثقة، مونتاج/رسم/تحريك احترافي بالتدرج، استخدام الأدوات والوكلاء المتاحين فقط، وإبلاغي بما تم إثباته.
>
> **عن الأسئلة:** ملف Q&A الحالي يحتوي على 35 قرارًا مُعاد صياغتها ومُصنّفة، **وليس** نصوص الأسئلة 1–1400؛ بعض النصوص الأصلية لم تُسترد بعد. لا تختلق أسئلة أو إجابات باسم المستخدم، ولا تعتبر موافقة سابقة إذنًا ماليًا/تدميريًا/لنشر البيانات، ولا تعتبر الأوصاف المفهرسة محركات تنفيذ.
>
> **ابدأ التنفيذ دون انتظار موافقتي على كل خطوة برمجية آمنة:** شغّل الاختبارات على نسخة نظيفة، اختر أول مهمة قابلة للإنجاز من `NEXT_AGENT_HANDOFF.md`، أضف الكود الأصلي واختبارات الأمن والجودة والمخرج القابل للفحص، ثم ارفع التغيير على فرع وPR. اطلب موافقتي فقط للأفعال التي تحتاجها فعليًا.
>
> **سلمّ تسليمًا موثقًا:** ماذا استلمت، ما الملفات/الكود الذي غيّرته، عدد الاختبارات بنتيجتها، أثر التغيير في سجل القدرات، رابط PR، هل دخل `main` بالفعل، ما بقي، وأول أمر مباشر للوكيل التالي. لا تكتفِ بعبارات «كملت» أو «خلص الصهر» بلا دليل.

**ملاحظات:** قد تختلف أدوات الوكلاء بحسب بيئة ChatGPT أو Claude أو Codex أو Gemini. إذا لم تتوفر صلاحية الوصول أو الرندر أو GitHub، احفظ تقرير العائق ولا تدّعِ التنفيذ. اتبع تعليمات السلامة والخصوصية المعمول بها في بيئتك.


## V18 first commands

\`\`\`bash
cd red-rose
python rose.py question-audit
python rose.py question-trace A17
python rose.py capabilities
python -W error::ResourceWarning -m unittest discover -v
\`\`\`

Use \`QA_TRACEABILITY.json\` to choose a missing documented goal and match it to actual code. Historical 1–1400 questions **remain unavailable verbatim** and must be recovered from original sources, not invented. The QA link module is metadata tooling, not all 1,400 implemented.

## V19 first commands

```bash
cd red-rose
python rose.py capabilities            # expect 17 adapters incl. video.shot_score
python rose.py shot-score VIDEO.mp4    # read-only measurements + reviewable EDL
python -W error::ResourceWarning -m unittest discover -v
```

Read section 8 of `NEXT_AGENT_HANDOFF.md` and `CAPABILITY_LEDGER_V19.md` first. Verify whether V19 has actually been pushed and merged before assuming it is on `main`.
