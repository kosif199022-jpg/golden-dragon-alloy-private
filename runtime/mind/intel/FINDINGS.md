# خلاصة تحليل 66 مستودع على اللابتوب (2026-11-12)

كل رقم هنا محسوب من `mind/intel/repos.json`، اللي طلع من فحص ثابت (`wd.py repo`) للملفات نفسها: قراية بس، مفيش تشغيل ولا تثبيت.
الأنماط («شبكة»، «تنفيذ»…) معناها إن الفحص لقى النمط في ملف كود، مش إن المستودع مؤذي.

## الأرقام
- **الرخص:** MIT (31)، Apache-2.0 (18)، none found (4)، GPL-3.0 (4)، CC (2)، other (2)، BSD (2)، Unlicense (1)، GPL-2.0 (1)، AGPL-3.0 (1)
- **اللغة الأساسية:** Python (33)، TypeScript (12)، JavaScript (9)، Java (4)، Markdown (3)، Notebook (2)، C (1)، Shell (1)، C++ (1)
- **فيهم مهارات Claude (SKILL.md):** 35 من 66؛ الأكتر: anthropics__skills (20+)، arjun988__blender-skills (20+)، EL4CTEO__blender-skills (20+)، OpenMontageInc__OpenMontage (20+)، RobLe3__cc-blender-skill (20+)، trailofbits__skills (20+)، charlie947__motion-graphics-skills (15)، kajisho5__ffmpeg-skill (14)
- **عندهم:** ci (38)، tests (26)، agents (17)، claude (14)، docker (7)، mcp (3)
- **أنماط «راجع قبل التشغيل»:** exec (53)، network (37)، delete (30)، telemetry (24)، secrets-read (22)، download-run (7)
- **أكتر الاعتماديات تكرارًا:** numpy (9)، pillow (9)، @types/node (7)، typescript (7)، requests (7)، mcp (5)، opencv-python (5)، openai (5)، pyyaml (5)، google-genai (4)، fastapi (4)، pydantic (4)، @modelcontextprotocol/sdk (3)، eslint (3)، tsx (3)، esbuild (3)، moviepy (3)، torch (3)
- **الأكبر حجمًا:** YaoFANGUK__video-subtitle-remover (1011.1 MB)، hyperframes (817.0 MB)، cut-as-code (233.0 MB)، sam2 (220.6 MB)، MoneyPrinterTurbo (214.3 MB)، feitangyuan__onetake (118.6 MB)
- **الفحص وقف عند حد 6000 ملف في:** cut-as-code، hyperframes، morluto__rea

## قرارات مبنية على الأرقام
- **الرخصة قبل أي استخدام:** 4 مستودع من غير ملف رخصة واضح (يتعاملوا كمرجع للقراية بس)، و6 بـ GPL/AGPL/LGPL (الكود المشتق لازم يفضل مفتوح: ماتنسخش منهم جوه المهارات).
- **التنفيذ والشبكة عاديين في النوع ده:** 53 مستودع بيشغّل برامج (غالبًا ffmpeg) و37 بيكلّم النت. اللي يتراجع بجد: download-run (7) و secrets-read (22) و telemetry (24): افتح الملف المذكور في ملف المستودع قبل أي تثبيت.
- **Docker:** 7 مستودع فيه Dockerfile؛ اللابتوب ويندوز من غير GPU، فالأولوية للي بيشتغل بـ Python/Node مباشرة.
- **مهارة جوه مستودع = أسرع طريق للاستفادة:** اقرا الـ SKILL.md بتاعها كمرجع أسلوب، وابني نسختنا العربي-أولًا بدل ما تثبّتها زي ما هي.

## دروس من تحليل teardown (اتجرّب فعلًا على اللابتوب)
- لقطة واحدة مستمرة من غير قطع، وماوس ظاهر بيدوس زراير الواجهة: كل دوسة = beat.
- افتتاح 3.5 ث دوران واسع، وبعدين beat كل 2.5–3 ث؛ الأفلام 26–31 ث.
- حركة الكاميرا 1.6 ث بمنحنى smootherstep مع رجوع خفيف، وانجراف بطيء دايم.
- خلفية استوديو فاتحة (#f3f2ee)، ولون إبراز واحد للجزء الشغال، وخطين بس (Inter + JetBrains Mono).
- الصوت كله متولّد بالكود: كورد ثابت، خبطة مع كل شوط قدرة، كليك 2400 هرتز مع كل دوسة، -14 LUFS، من غير تعليق صوتي.
- العدادات بتتقري من نفس النموذج اللي بيحرّك الأجزاء، فالأرقام عمرها ماتكدّب الحركة.
- القاعدة اللي تتنقل لأي موشن عندنا: الحركة دالة في رقم الفريم، مش في الساعة.

## أنماط هندسية متكررة في المستودعات الناجحة (من dragon-genius وgithub-atlas، اتقرت مش اتقاست هنا)
- خطة على الديسك قبل التنفيذ، ودليل قبل التقرير.
- dry-run افتراضي، والتنفيذ بعلم صريح.
- مخرجات مناسبة للوكيل: JSON قصير، exit codes ليها معنى، ومسار الملف الناتج في آخر سطر.
- README وأي نص من الهدف بيانات مش أوامر.
- التحقق بأداة مستقلة عن اللي أنتجت (ffprobe بعد ffmpeg).
