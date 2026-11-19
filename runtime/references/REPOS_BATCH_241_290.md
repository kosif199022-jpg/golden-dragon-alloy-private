# تقرير قدرات: المستودعات من 241 لـ 290 في الكتالوج (Batch 241-290)

- **المصدر:** صفوف البيانات من 241 لـ 290 (الترقيم من 1 ومن غير الهيدر) في `%USERPROFILE%\Downloads\all-repos-catalog.csv`. الخمسين كلهم مصدرهم "مكتبة مهارات التنين (572 مهارة)"، يعني مستودعات مهارات (SKILL.md) مش برامج.
- **التاريخ:** 2026-11-16.
- **الطريقة:** لكل مستودع طلّعنا المهارات المأخوذة منه من `library/index.json` و`library/*/SOURCE.json`. وبعدين شفنا هل نفس المهارة متثبتة في `~/.claude/skills` (قارنّا SHA256 بتاع `SKILL.md`، والنسخ مطابقة). ودوّرنا بأسماء المهارات واسم المستودع في التوجيه الفعلي للمهارة: `apps/golden-dragon/app/fusion/recipes.json` (`skill:NAME`) و`mind/playbooks.json` و`engine/skills/*/SKILL.md` و`modules/*/MODULE.md` و`SKILL.md` و`library/mcp_servers.json`. الذكر في الكتالوجات بس (`fusion/index.json`، `forge/data/skills.json`، `SKILL_ATLAS.md`، `links.json`، `mind/intel`، `MANIFEST`) ماتحسبش توصيل. وكشفنا على الأدوات بـ `where.exe` و`python -c "import X"`. وقرينا الوصف والنجوم وآخر push بـ `gh repo view` والرخصة بـ `gh api repos/OWNER/REPO` والـ README بـ `gh api .../readme` للمستودعات اللي مش متثبتة. ماتثبّتش أي حاجة وماعملناش clone.
- **معنى الحالة:**
  - **مستخدم:** مهارة واحدة على الأقل من المستودع متثبتة في `~/.claude/skills`، والمهارة بتوجّه ليها فعلًا (وصفة في `recipes.json`، أو playbook، أو SKILL.md بيحوّل عليها، أو وصفة تثبيت).
  - **متثبت ومش متوصّل:** المهارات متثبتة في `~/.claude/skills` (فـ Claude يقدر يحمّلها لوحده)، بس `golden-dragon` بيذكرها في الكتالوجات بس، وماحدش بيوجّه ليها.
  - **قدرة جديدة:** مش متثبتة. موجودة كنسخة مرجعية في `library/` بس ("مش متثبتة ومابتتحمّلش لوحدها" حسب `SKILL.md`)، والأداة نفسها مش على الجهاز.

## الملخص

| الحالة | العدد |
|---|---|
| مستخدم | 19 |
| متثبت ومش متوصّل | 23 |
| قدرة جديدة | 8 |
| **الإجمالي** | **50** |

## جدول الخمسين

| # | Repo | الحالة | الدليل على الجهاز وفي المهارة | الإضافة الملموسة | التشغيل على Windows | ملاحظة الرخصة |
|---|---|---|---|---|---|---|
| 241 | charlie947/motion-graphics-skills | مستخدم | 9 مهارات متثبتة، و`animated-chart` و`brand-intake` في `recipes.json`، والمستودع متذكر في `creative-studio` | (موجود) موشن جرافيك بالكود: شارت متحرك، launch film، loop cover | Skill: `animated-chart`، `launch-video` | MIT. ★689 |
| 242 | KyaniteLabs/mcp-video | مستخدم (متوصّل بس مش متثبت) | 3 مهارات متثبتة (`kinocut`، `kinocut-repurpose`، `mcp-video`)، و`montage-repos-hub` فيه وصفة تثبيت. الباكدج `kinocut` مش متثبت (`import kinocut` فشل) | (موجود كوصفة) MCP فيه أكتر من 200 أداة ffmpeg بحواجز أمان | `pip install kinocut` ثم `claude mcp add mcp-video -- ...` | Apache-2.0. ★267. المستودع اتغير اسمه لـ `KyaniteLabs/kinocut` |
| 243 | iart-ai/motion-design-skills | مستخدم | 9 متثبتة، و`beat-sync-editing` و`logo-animation` و`motion-art-direction` في `recipes.json`، و`animation-principles` في `playbooks.json` | (موجود) أساسيات الموشن: توقيت، تايبوجرافي، قطع على البيت | Skill | MIT. ★236 |
| 244 | ferdinandobons/AWSBedrockAgentCoreSkill | متثبت ومش متوصّل | `aws-bedrock-agentcore-skill` متثبتة، ومتذكرة في `fusion/index.json` و`skills.json` بس | بناء وكلاء على AWS Bedrock AgentCore | Skill، وبتحتاج حساب AWS | MIT. ★207. مالهاش علاقة بشغل الميديا |
| 245 | TerminalSkills/skills | مستخدم | 9 متثبتة (`3proxy`، `3dsmax-*`، `a2a-protocol`، `a2ui`، `ably`، `accessibility-auditor`، `aceternity-ui`، `activepieces`)، و`accessibility-auditor` بس في `recipes.json` | (موجود) فحص accessibility. الباقي مرجع | Skill | Apache-2.0. ★205. التسعة متاخدين بالترتيب الأبجدي من مكتبة كبيرة، فاختيارهم عشوائي |
| 246 | majidmanzarpour/blender-game-skills | متثبت ومش متوصّل | `blender-image-to-3d` متثبتة، ومتذكرة في `SKILL_ATLAS.md` و`fusion/index.json` بس | يحوّل concept art أو صور لأصل 3D جاهز للعبة في Blender، على مراحل وببوابات رندر | Skill مع `blender.exe` 5.2 الموجود | MIT. ★184 |
| 247 | RobLe3/cc-blender-skill | مستخدم | 9 متثبتة، و5 في `recipes.json` (`blender-cameras` و`blender-lighting` و`blender-materials` و`blender-modeling` و`animation-quality-gate`) | (موجود) | Skill مع blender | MIT. ★165 |
| 248 | skillmds/SkillMD | متثبت ومش متوصّل | 8 متثبتة (`ads-math`، `agent-recall`، `aihot`، `b0`، `bioqc-mcp`، `bmw-design-analysis`، `civitai-mcp-ultimate`، `find-a-skill`)، و`hello-world` في `library/` بس. متذكرة في `mind/installed_catalog.json` و`fusion/index.json` | خليط مهارات من فهرس المستودع. الأداة نفسها (CLI وMCP لعمل lint وبحث وتثبيت للمهارات) مش متاخدة | Skill | MIT. ★146. `hello-world` مثال ومالوش لازمة |
| 249 | DylXBT/claude-orchestrator-skills | مستخدم | 7 متثبتة، و`prompt-architect` و`skill-author` في `recipes.json` | (موجود) | Skill | MIT. ★114 |
| 250 | Helpercraft/helpercraft | مستخدم | 9 متثبتة (شخصيات مساعدة)، و`hazel-bookkeeping-helper` بس في `recipes.json` | (موجود) | Skill | MIT. ★109. الباقي (طبخ، تمريض، رحلات) بعيد عن المهارة |
| 251 | midasmatterhorn/artcraft-skills | متثبت ومش متوصّل | 9 متثبتة (`*craft`)، ومتذكرة في `fusion/index.json` بس | واجهات لـ ArtCraft (حزمة إبداع مكتوبة بـ Rust) | بتحتاج ArtCraft نفسه، ومش لاقيينه على الجهاز | MIT. ★83 |
| 252 | tmchow/agent-skills | مستخدم | 4 متثبتة، و`yt-dlp-cli` في `recipes.json` | (موجود) yt-dlp. وفيه كمان تسجيل terminal بـ VHS | Skill. `vhs-terminal-recorder` محتاج VHS | MIT. ★68. `camofox-cloaked-browser` متصفح بيستخبى من bot-detection، فماينفعش يتستخدم لتخطي الحماية |
| 253 | sunxiayi/make-blender-education-video-skill | متثبت ومش متوصّل | متثبتة، ومتذكرة في فهرس `creative-studio` و`fusion/index.json` بس، ومش موجودة في `recipes.json` | فيديوهات شرح علمي سينمائية بـ Blender مع fact-check | Skill مع blender 5.2 | MIT. ★70. بتطلّع إنجليزي، والعربي محتاج تعديل |
| 254 | ishwarjha/claude-marketing-research-skill | متثبت ومش متوصّل | `marketing-research` متثبتة، وفي الكتالوجات بس | بحث تسويق منظّم: منافسين وavatar وpositioning | Skill | Apache-2.0. ★63 |
| 255 | Lethe044/agentskill-kit | مستخدم | 9 متثبتة، و`csv-profiler` في `recipes.json` | (موجود) أدوات dev صغيرة (json-diff، log-analyzer...) | Skill | MIT. ★51. أداة المستودع الأساسية (lint وsecurity scan للمهارات) مش متاخدة |
| 256 | FlorianBruniaux/claude-code-plugins | مستخدم | 9 متثبتة، و`audit-agents-skills` في `recipes.json` | (موجود) audit وeval للمهارات والهوكس | Skill | MIT. ★46 |
| 257 | LobzyJay/motion-design-with-claude-and-codex | مستخدم | 3 متثبتة، و`motion-design-critique` في `recipes.json`، والتلاتة متذكرين في `creative-studio` | (موجود) | Skill | MIT. ★41 |
| 258 | WhiteTowerAI/cut-as-code | مستخدم | 9 متثبتة، و`video-cut` و`video-color-grade` و`video-understand` في `recipes.json`، والتسعة في `black-dragon-cinema` و`montage-repos-hub` | (موجود) مونتاج agentic: shorts، كابشن، b-roll، تلوين | Skill | MIT. ★34 |
| 259 | ESJavadex/claude-homeassistant-plugins | متثبت ومش متوصّل | 4 متثبتة، وفي الكتالوجات بس | إدارة إعدادات Home Assistant | محتاج سيرفر HA | MIT. ★28. بعيد عن المهارة |
| 260 | alexex1993/mcu-skills | متثبت ومش متوصّل | 8 متثبتة لبوردات ESP32 وAVR، و`replace-with-skill-name` (قالب فاضي من `templates/`) في `library/` بس | مراجع pinout وبرمجة لبوردات microcontroller | Skill. أدوات Arduino مااتفحصتش | MIT. ★29. القالب مالوش لازمة في المكتبة |
| 261 | cagatayuncu/marketing-machine | متثبت ومش متوصّل | متثبتة، وفي الكتالوجات بس | يراجع ادعاءات المحتوى التسويقي على الكود الحقيقي ويفحص التزامها بالبراند | Skill | MIT. ★21 |
| 262 | jrjsmrtn/project-orchestration-skills | متثبت ومش متوصّل | 9 متثبتة، وفي الكتالوجات بس | ADRs، وتأمين GitHub Actions، وsprints | Skill | MIT. ★17 |
| 263 | himself65/skill-lint | قدرة جديدة | الـ 9 مجلدات اللي في `library/` (`angle-brackets`، `empty-body`...) **fixtures اختبار** من `test/fixtures`، مش مهارات. مش متثبتة، و`skill-lint` مش موجود على الجهاز | linter لـ SKILL.md (صيغة الاسم، وطول الوصف، والـ frontmatter) يتشغّل على الـ 572 مهارة قبل الرفع | `npx skill-lint <dir> --claude-code` | MIT. ★16. الـ fixtures لازم تتشال من `library/` |
| 264 | OpenGHz/embodied-ai-paper-writer | متثبت ومش متوصّل | متثبتة، وفي الكتالوجات بس | كتابة أبحاث embodied AI | Skill | MIT. ★17. بعيد |
| 265 | HariFatherKR/claude-qwen-tts | مستخدم | `tts-narrator` متثبتة وموجودة في `recipes.json` | (موجود) تحويل سكريبت لصوت narration | Skill، وبتعتمد على خدمة Qwen TTS | MIT. ★16. آخر push كان 2026-02 |
| 266 | wei18/Upkeep | متثبت ومش متوصّل | `upkeep-audit` متثبتة، وفي الكتالوجات بس | audit للريبو يمسك اختلاف الـ docs والـ spec والـ assets عن الكود، بأدلة ومن غير تعديل | Skill `upkeep-audit` على مسار الريبو | MIT. ★17 |
| 267 | DKeken/codex-skills-alternative | مستخدم | 9 متثبتة، و`creative-explore` و`creative-polish` في `recipes.json` | (موجود) | Skill | MIT. ★15 |
| 268 | Rinne414/lora-training-skill | متثبت ومش متوصّل | 3 متثبتة (`dataset-doctor`، `lora-pipeline`، `lora-trainer`)، وفي الكتالوجات بس | فحص وإصلاح داتاسيت LoRA (تكرار، أبعاد، كابشن، ميزانية steps)، وتدريب LoRA لثبات الشخصية | `dataset-doctor` يشتغل على CPU. التدريب محتاج GPU، وtorch عندنا CPU | MIT. ★14 |
| 269 | Kimeur/motion-launch-videos | مستخدم | 9 متثبتة، و4 في `recipes.json` (`motion-launch-videos` و`motion-cartoon` و`motion-charts` و`motion-overlays`)، و`motion-cartoon` في `playbooks.json` | (موجود) | Skill | MIT. ★13 |
| 270 | kuhung/weread-book-skills | مستخدم | 9 متثبتة، و`data-storytelling` في `recipes.json` | (موجود) | Skill | MIT. ★12. الباقي ملخصات كتب إدارة |
| 271 | renanlido/tia-harness | متثبت ومش متوصّل | 8 متثبتة، وفي الكتالوجات بس | أتمتة Siemens TIA Portal V21 | محتاج TIA Portal | MIT. ★12. بعيد |
| 272 | aegntic/cldcde | متثبت ومش متوصّل | 9 متثبتة (`ae-ltd-*` وغيرها)، وفي الكتالوجات بس | أدوات mutation testing وvisual regression وworktrees | Skill | MIT. ★11 |
| 273 | bolvein-firex/scraping-skills | متثبت ومش متوصّل | 9 متثبتة، وفي الكتالوجات بس. **المستودع مش موجود على GitHub دلوقتي (404)** | سكرابرز Amazon وAirbnb وBooking وCoursera | Skill | الرخصة MIT حسب الكتالوج بس، ومانقدرش نتأكد منها دلوقتي. السكرابرز ممكن تخالف شروط المواقع |
| 274 | smk-labs/claude-plugins | مستخدم | 9 متثبتة، و`mini-research` و`mkprompt-goal` في `recipes.json` | (موجود) | Skill | MIT. ★11 |
| 275 | yimeng-YM/minecraft-build-design | متثبت ومش متوصّل | متثبتة، وفي الكتالوجات بس | تصميم مباني Minecraft | Skill | MIT. ★14. بعيد |
| 276 | jiutuhky/my-super-capsule | متثبت ومش متوصّل | 3 متثبتة، وفي الكتالوجات بس | كتابة براءات اختراع ورسوماتها | Skill | MIT. ★11 |
| 277 | seilk/claude-teleport | متثبت ومش متوصّل | 7 متثبتة، وفي الكتالوجات بس | مزامنة مهارات وإعدادات Claude Code بين الأجهزة من خلال ريبو خاص | Skill، ومحتاج `gh` | MIT. ★10. بيرفع الإعدادات، فلازم مراجعة قبل الاستخدام |
| 278 | TikHub/tikhub-plugin | مستخدم | 9 متثبتة، و`comments-analysis` و`creator-analytics` و`hashtag-research` في `recipes.json` | (موجود) تحليلات سوشيال وتحميل ميديا | Skill، ومحتاج حساب TikHub API | MIT. ★11 |
| 279 | 5hyuns/ad-copy-agency-skill | متثبت ومش متوصّل | `copy-masters` متثبتة، وفي الكتالوجات بس | عناوين إعلانات بنفس خطوات الوكالة (planner وCD وcreative) | Skill | MIT. ★9 |
| 280 | PAIR-Systems-Inc/goodmem-claude-code-plugin | متثبت ومش متوصّل | 4 متثبتة، وفي الكتالوجات بس | ذاكرة GoodMem من خلال MCP | محتاج سيرفر GoodMem | MIT. ★9 |
| 281 | ClickHouse/clickhouse-claude-code-plugin | متثبت ومش متوصّل | `clickhouse-best-practices` متثبتة، وفي الكتالوجات بس | أحسن ممارسات ClickHouse | Skill | Apache-2.0. ★7 |
| 282 | kotsmiltos/mk-cc-resources | متثبت ومش متوصّل | 9 متثبتة (`verify`، `triage`، `context`، `heal`...). أساميها بتظهر في الملفات ككلمات عادية بس، مش كتوجيه | فحص SPEC قبل التسليم، وأصوات تنبيه | Skill | MIT. ★4. الأسامي عامة وممكن تتلخبط مع مهارات تانية |
| 283 | anthropics/skills | مستخدم | 6 متثبتة، و4 في `recipes.json`، والستة في `playbooks.json` و`app.py` | (موجود) frontend-design وcanvas-design وwebapp-testing وغيرها | Skill | مافيش LICENSE على مستوى الريبو. كل مهارة ليها `LICENSE.txt`، والستة المأخوذين Apache-2.0. ★195k |
| 284 | vercel-labs/skills | قدرة جديدة | `find-skills` في `library/` بس، و`skills` مش موجود على الجهاز | تثبيت مهارات من أي ريبو لأكتر من 75 agent، والبحث بـ `npx skills find` | `npx skills find <q>` و`npx skills add owner/repo --skill X -a claude-code` | MIT. ★39.5k. بيكرر `$R skills find`، ومحتاج Node 22.20 أو أحدث |
| 285 | nextlevelbuilder/ui-ux-pro-max-skill | قدرة جديدة | في `library/` بس (فيها `scripts/` و`data/`)، ومش متثبتة. متذكرة في `dragon-genius/references` كمصدر | محرك بحث تصميم (ستايلات وباليتات وخطوط وقواعد UX)، وفيه `--rtl` للعربي | `python library\ui-ux-pro-max\scripts\search.py "<q>" --domain style` (Python بس ومن غير dependencies) | MIT. ★150k |
| 286 | upstash/context7 | قدرة جديدة | 3 مهارات في `library/` بس. `library/mcp_servers.json` مرجع إعداد بس. `ctx7` مش موجود، ومافيش MCP متسجّل في `~/.claude.json` | توثيق محدّث على حسب النسخة للمكتبات (Remotion وthree.js وGSAP) بدل الاعتماد على الذاكرة | `npx ctx7 setup` أو MCP `@upstash/context7-mcp` | MIT. ★64.9k. خدمة سحابية، ومفتاح API المجاني مُستحسن |
| 287 | DietrichGebert/ponytail | قدرة جديدة | 6 مهارات في `library/` بس. `dragon-genius/SKILL.md` بياخد منهجه (السلّم والفوتر) كنص بس | يقلّل الكود والتوكنز ويمنع الحلول المبالغ فيها | انسخ `library\ponytail*` لـ `~/.claude/skills` | MIT. ★191k. أرقام الـ README (-45% توكنز) ماتفحصتش |
| 288 | usestrix/strix | قدرة جديدة | المهارتين الدفاعيتين بس في `library/`، وأداة `strix` مش موجودة | دوّر على ثغرات الكود وصلّحها | المهارتين نص. أداة Strix نفسها agents بتعمل pentest وبتشغّل exploits | Apache-2.0. ★75.8k. الأداة الكاملة هجومية، فماتشتغلش غير على تطبيقك وبموافقة |
| 289 | addyosmani/agent-skills | قدرة جديدة | 14 مهارة في `library/` بس | دورة هندسة كاملة: spec وplanning وTDD وdebugging وcode review وsecurity | انسخ المهارات اللي محتاجها لـ `~/.claude/skills` | MIT. ★118k. فيه تداخل مع `systematic-debugging` و`brainstorming` المتثبتين |
| 290 | Graphify-Labs/graphify | قدرة جديدة | `graphify` في `library/` بس، و`import graphify` فشل | يحوّل الكود والمستندات لـ knowledge graph تقدر تسأله، ودا مفيد لريبو `golden-dragon` الكبير | `uv tool install graphifyy` ثم `graphify install` | Apache-2.0 أو MIT. ★148k. اسم الباكدج `graphifyy` (بـ y زيادة) |

## أهم 10 إضافات (حسب القيمة للمهارة ولشغل الفيديو والصور والموشن)

| # | الأداة | ليه | أرخص طريقة للإضافة |
|---|---|---|---|
| 1 | **ui-ux-pro-max** | قرارات تصميم مبنية على داتا (باليتة وخطوط وستايل) لصفحات HTML-to-video والكروت والأرتيفاكتس، وفيه دعم RTL للعربي | **مافيش تثبيت.** الملفات موجودة في `library/ui-ux-pro-max`: شغّل `scripts/search.py` بـ Python العادي، أو انسخ المجلد لـ `~/.claude/skills` |
| 2 | **make-blender-education-video** | فيديو شرح سينمائي بـ Blender مع fact-check، وBlender 5.2 موجود | **متثبتة.** ضيف وصفة في `recipes.json` بتوجّه ليها مع `blender-pro` |
| 3 | **blender-image-to-3d** | صورة أو concept art يتحوّل لأصل 3D جاهز، ببوابات رندر | **متثبتة.** ضيفها لوصفة الـ 3D في `recipes.json` جنب `blender-modeling` |
| 4 | **lora-training (dataset-doctor)** | فحص داتاسيت الشخصيات قبل التدريب، علشان ثبات الشخصية في الصور والفيديو | **متثبتة.** وصّل `dataset-doctor` (شغال على CPU). التدريب نفسه يتأجل لحد ما يبقى فيه GPU أو يتعمل على السحابة |
| 5 | **Context7** | توثيق Remotion وthree.js وGSAP وPlaywright بالنسخة الصح، فالأخطاء في الـ API تقل | `npx ctx7 setup` (CLI ومهارات، من غير MCP)، ومعاه مفتاح مجاني |
| 6 | **Ponytail** | أقل كود وأقل توكنز في كل شغل الكود، ومنهجه أصلًا متاخد في `dragon-genius` | انسخ `library\ponytail*` (6 مجلدات) لـ `~/.claude/skills` |
| 7 | **addyosmani/agent-skills** | spec وTDD وreview بشكل منظم لتطوير محركات التنين نفسها | انسخ `spec-driven-development` و`test-driven-development` و`code-review-and-quality` بس، علشان مايحصلش تداخل |
| 8 | **skill-lint** | فحص الـ 572 مهارة والمهارات الجديدة قبل الرفع، ويكشف الـ fixtures والقوالب اللي دخلت المكتبة غلط | `npx skill-lint library --claude-code --json` من غير تثبيت دائم |
| 9 | **graphify** | خريطة معرفة لريبو `golden-dragon` (محركات وتطبيقات ومراجع)، فالبحث فيه يبقى أسرع من grep | `uv tool install graphifyy` |
| 10 | **upkeep-audit** | يمسك اختلاف الـ docs (`SKILL.md` والمراجع) عن الكود الحقيقي، ومن غير ما يعدّل حاجة | **متثبتة.** شغّلها على مجلد المهارة، وضيفها لخطوة المراجعة قبل الإصدار |

### ملاحظات جانبية

- **فضلات في `library/`:** التسع مجلدات بتوع `himself65/skill-lint` (angle-brackets وempty-body وغيرهم) fixtures اختبار، و`hello-world` (SkillMD) و`replace-with-skill-name` (mcu-skills) قوالب. دول مش مهارات حقيقية، والأحسن يتشالوا.
- **bolvein-firex/scraping-skills:** المستودع بيرجّع 404، فالرخصة مانقدرش نتأكد منها، والمهارات المتثبتة نسخة يتيمة.
- **KyaniteLabs/mcp-video:** اتغير اسمه لـ `kinocut`. المهارات متثبتة، بس باكدج `kinocut` والـ MCP مش متثبتين.
- **Strix:** اتاخدت المهارتين الدفاعيتين بس. الأداة الكاملة بتعمل pentest فعلي، فمش في التوب 10.
- **vercel-labs/skills:** بيكرر `$R skills find` و`lib_install`، فقيمته قليلة.
- **TerminalSkills وHelpercraft وweread:** التسع مهارات اتاخدوا بالترتيب مش بالقيمة. اللي متوصّل منهم واحد بس من كل مستودع، والباقي بعيد عن المهارة.
- **anthropics/skills:** مافيش رخصة على مستوى الريبو، فلازم نراجع `LICENSE.txt` بتاع كل مهارة. مهارات docx وpdf وpptx وxlsx هناك source-available ومش Apache.
