# تقرير قدرات: المستودعات من 191 لـ 240 في الكتالوج

- **المصدر:** صفوف البيانات من 191 لـ 240 (من غير الهيدر) في `%USERPROFILE%\Downloads\all-repos-catalog.csv`. كلهم مصدرهم «مكتبة مهارات التنين (572 مهارة)» ما عدا صف 191 (jadx-ai-mcp) اللي مصدره «التنين intel».
- **التاريخ:** 2026-11-16.
- **الطريقة:** طابقنا كل مستودع بالمهارات المنسوخة منه عن طريق `library/*/SOURCE.json`، وشفنا لو نفس المهارات موجودة في `~/.claude/skills/`. ودوّرنا باسم المستودع واسم الأداة جوه كود `golden-dragon` (scripts وengine وmind وmodules وapps وtools) من غير `library/` و`references/`. وكشفنا على الجهاز بـ `where.exe` و`npm ls -g` و`python -c "import X"`، وبصّينا على `~/dragon-repos` و`~/re-tools`. وقرينا README والرخصة والنجوم وآخر push لكل مستودع بـ `gh api repos/OWNER/REPO/readme` و`gh repo view`. ماتثبّتش أي حاجة، وماعملناش clone، وماشغّلناش كود من أي مستودع.
- **معنى الحالة:**
  - **مستخدم:** فيه كود في المهارة بيشغّله، أو نقل طريقته لكود بيشتغل، أو وصفة في `forge/recipes.py` بتنادي مهارته بالاسم.
  - **متثبت ومش متوصّل:** مهاراته منسوخة في `library/` وفي `~/.claude/skills/` (يعني Claude بيشوفها)، وساعات المستودع نفسه متحمّل في `~/dragon-repos`، بس مافيش كود في golden-dragon بيستدعيها غير البحث العام `$R skills find` والكتالوجات (`library.json` و`forge/data/skills.json` و`fusion/index.json`).
  - **قدرة جديدة:** مش متثبت ولا متوصّل. لو ليه ذكر فهو في المراجع بس.

## الملخص

| الحالة | العدد |
|---|---|
| مستخدم | 10 |
| متثبت ومش متوصّل | 39 |
| قدرة جديدة | 1 |
| **الإجمالي** | **50** |

## جدول الخمسين

| # | Repo | الحالة | الدليل على الجهاز وفي المهارة | الإضافة الملموسة | التشغيل على Windows | ملاحظة الرخصة |
|---|---|---|---|---|---|---|
| 191 | zinja-coder/jadx-ai-mcp | قدرة جديدة | المصدر بس في `dragon-repos\re\zinja-coder__jadx-ai-mcp`، ومذكور في `RD_INTEL_REPOS.md` و`rea-ultra/references/github-landscape.md`. الـ plugin مش متثبت. اللي متثبت هو `jadx` 1.5.6 و`jadx-headless-mcp` 0.7.1 (مشروع تاني، `REA_JADX_MCP_JAR`) | إعادة تسمية class وmethod ومتغيرات جوه JADX من الموديل (write-back)، وده الحاجة الوحيدة اللي REA مش بيعملها | plugin لـ JADX GUI + `uv tool install git+https://github.com/zinja-coder/jadx-mcp-server` | Apache-2.0. **الـ MCP لو اتربط على 0.0.0.0 أي حد على الشبكة يقدر يشغّل أدواته**، فاربطه على localhost بس |
| 192 | morluto/rea | مستخدم | `rea` (npm `rea-agents` 6.8.0) متثبت، و`dragon_desktop/app.py` و`mcp_dragon.py` بيشغّلوه، و4 مهارات `rea-*` في library | (موجود) هندسة عكسية لملفات وبرامج وصفحات | `rea analyze C:/path/app.exe` | MIT |
| 193 | obra/superpowers | متثبت ومش متوصّل | 10 مهارات (brainstorming وsystematic-debugging وexecuting-plans وusing-git-worktrees…) في library و`~/.claude/skills`. كلمة «Superpowers» في `app.py` تخص hub تاني (KOSIF)، مش ده | منهج شغل: خطة ثم تنفيذ ثم مراجعة، وdebugging منظم، وworktrees | Skill: `systematic-debugging` | MIT |
| 194 | harry0703/MoneyPrinterTurbo | متثبت ومش متوصّل | مهارة `moneyprinterturbo-video` والمستودع في `dragon-repos\MoneyPrinterTurbo`. `media_gate.py` واخد منه قاعدة واحدة بس (الفيديو أطول من الصوت بـ 0.1 ث) | فيديو قصير كامل من موضوع: سكربت وفوتيج ستوك وترجمة ومزيكا | Windows one-click package أو Python 3.11 + WebUI | MIT. **محتاج مفاتيح API لموديل لغة ولمصدر الفوتيج (Pexels/Pixabay)** |
| 195 | heygen-com/hyperframes | مستخدم (متوصّل بس مش متثبت) | `cards/lib/fam_*.py` بتشغّل `npx --no-install hyperframes add`، و`library/mcp_servers.json` فيه HyperFrames، و10 مهارات في library، والمستودع في `dragon-repos\hyperframes`. مش موجود في `npm -g` | (موجود) HTML إلى فيديو بـ GSAP وكومبوننتات جاهزة | `npx hyperframes render` (محتاج cache أو تثبيت قبل `--no-install`) | Apache-2.0 |
| 196 | OpenMontageInc/OpenMontage | متثبت ومش متوصّل | 10 مهارات في library (أغلبها APIs سحابية: atlas-cloud وbfl-api وazure-tts…)، والمستودع في `dragon-repos`. `media_gate.py` و`transcript_qa.py` واخدين منه قواعد QA بس | 12 pipeline إنتاج فيديو كاملة وقواعد فحص جاهزة | Python 3.10 + `npm install` في `remotion-composer` | **AGPL-3.0**: لو اتدمج في كود بيتوزّع أو خدمة، لازم الكود يتفتح. **وبيعتمد على Remotion (رخصة شركة لو 4+ موظفين)** |
| 197 | virgiliojr94/book-to-skill | متثبت ومش متوصّل | مهارة `book-to-skill` في library و`~/.claude/skills`، ومذكورة في كتالوجات بس | يحوّل كتاب PDF تقني لمهارة Claude | Skill: `book-to-skill` | MIT. انتبه لحقوق الكتاب نفسه |
| 198 | browser-use/video-use | مستخدم | `forge/recipes.py` فيها خطوة `skill:video-use` لريل 9:16، و`dragon_fusion.py` بيحلّ اسمها، ومهارتين في library، والمستودع في `dragon-repos\video-use` | (موجود) مونتاج بالـ agent: قص وتلوين وترجمة | `uv sync` ثم Skill: `video-use` | MIT. **الصوت بيحتاج مفتاح ElevenLabs** |
| 199 | alirezarezvani/claude-skills | متثبت ومش متوصّل | 10 مهارات متفرقة (hivemind وdeepread وgrade-iterate وinterview…) في library، ومافيش ذكر للمستودع في الكود | مهارات هندسة وتسويق ومنتج عامة | Skill بالاسم | MIT |
| 200 | op7418/Humanizer-zh | متثبت ومش متوصّل | مهارة `humanizer-zh` في library. `writing_humanizer.py` في الكود من مصدر تاني | يشيل بصمة الـ AI من نص **صيني** | Skill: `humanizer-zh` | MIT. قيمته قليلة لشغل عربي |
| 201 | nidhinjs/prompt-master | متثبت ومش متوصّل | مهارة `prompt-master` في library و`mind/installed_catalog.json` | يكتب برومبت دقيق لأي أداة AI (صور وفيديو وكود) | Skill: `prompt-master` | MIT |
| 202 | heydamir/unslop | مستخدم | `forge/recipes.py`: خطوة «اتجاه التصميم» بتنادي `skill:frontend-design` و`skill:unslop` | (موجود) يحوّل واجهة شكلها AI لتصميم مقصود | Skill: `unslop` | **CC-BY-4.0**: لازم نسبة للمؤلف لو اتنقل النص |
| 203 | mrexodia/ida-pro-mcp | متثبت ومش متوصّل | مهارة `idapython` في library، والمستودع في `dragon-repos\re`. **IDA Pro مش متثبت** | MCP لـ IDA: decompile وxrefs وrename من الموديل | `pip install https://github.com/mrexodia/ida-pro-mcp/archive/refs/heads/main.zip` بعد تفعيل idalib | MIT. **IDA Pro نفسه برنامج مدفوع**. Ghidra وrizin موجودين بديل |
| 204 | Jeffallan/claude-skills | متثبت ومش متوصّل | 10 مهارات أدوار مطوّرين (api-designer وcloud-architect وcpp-pro…) في library | خبرات full-stack جاهزة | Skill بالاسم | MIT |
| 205 | zhouxiaoka/autoclip | متثبت ومش متوصّل | مهارتين (`autoclip` و`product-board`) في library، والمستودع في `dragon-repos` | يقص فيديو طويل (بودكاست، محاضرة) لشورتس بترجمة وغلاف ونص نشر | Windows x64 `-setup.exe` من Releases، أو CLI/MCP بـ Python 3.11 + FFmpeg | MIT. **بيستخدم موديل لغة خارجي، فمحتاج مفتاح API** |
| 206 | Jakeschincariol/replica-skill | متثبت ومش متوصّل | 10 مهارات `replica-*` في library، ومافيش ذكر في الكود | يفكك أي تطبيق ويعيد بناءه ويختبره | Skill: `replica-recon` | MIT. استنساخ تطبيقات حد تاني فيه مخاطر حقوق وعلامات تجارية |
| 207 | SimoneAvogadro/android-reverse-engineering-skill | متثبت ومش متوصّل | مهارة `android-reverse-engineering` في library. الأدوات اللي بتستخدمها (`jadx` و`apktool`) متوصّلة أصلًا عن طريق `retool.py` | خطوات فك APK منظمة | Skill بالاسم + `~/re-tools/jadx` | Apache-2.0. بيكرر اللي retool وREA بيعملوه |
| 208 | trailofbits/skills | متثبت ومش متوصّل | 10 مهارات أمان (audit-context-building وscanners لعقود ذكية…) في library، ومذكور كمرجع في `rea-ultra/SKILL.md` | مراجعة أمان وتدقيق كود وعقود | Skill بالاسم | **CC-BY-SA-4.0**: أي نسخة معدّلة لازم بنفس الرخصة ومع النسبة |
| 209 | JuneYaooo/rea-video | متثبت ومش متوصّل | مهارة `rea-video` في library و`~/.claude/skills`، والمستودع في `dragon-repos`، ومذكور في `library.json` | يفكك أي فيديو لقطة بلقطة (متصوّر ولا AI ولا كود) ويطلّع ملف `VIDEO.md` بخطة إعادة عمله | `pip install` للـ CLI. ffmpeg وPython 3.10+ موجودين | Apache-2.0. للتعلّم بس، من غير إعادة استخدام فوتيج حد تاني |
| 210 | Jakeschincariol/day-trader-skill | متثبت ومش متوصّل | 10 مهارات `trader-*` في library | تحليل وتداول يومي | Skill بالاسم | MIT. **مالي: Claude مش مستشار مرخّص، ومش هينفّذ صفقات** |
| 211 | patch-gg/pixelfx | مستخدم | `tools/repo_fusion/scripts/fusion/native_pixelfx.py` (إعادة كتابة بـ numpy/OpenCV)، و`dragon.py` بيسجّله | (موجود) مؤثرات بكسل آرت على الفريمات | `python -m dragon` بأمر `pixelfx` | MIT. الكود اتكتب من جديد مع النسبة |
| 212 | SawyerHood/dev-browser | مستخدم (متوصّل بس مش شغال على Windows) | `forge/recipes.py` بتنادي `skill:dev-browser` جنب `engine:chrome`. `dev-browser` مش متثبت | (موجود كوصفة) تحكم في متصفح من الـ agent | `npm install -g dev-browser` | MIT. **الـ README بيقول Windows مش مدعوم لسه**، فعمليًا `engine:chrome` هو اللي بيشتغل |
| 213 | joeseesun/qiaomu-anything-to-notebooklm | متثبت ومش متوصّل | مهارة في library. باكدج `notebooklm` مش متثبت | يحوّل مقالات وفيديوهات YouTube وPDF لبودكاست وشرايح وخرائط ذهنية في NotebookLM | `pip install -r requirements.txt` + تسجيل دخول Google | MIT، بس README بيقول «للتعلّم الشخصي بس» |
| 214 | danyuchn/asd-ste100-skill | متثبت ومش متوصّل | مهارة `asd-ste100` في library | يعيد كتابة الإنجليزي التقني بقواعد Simplified Technical English | Skill: `asd-ste100` | MIT |
| 215 | Jakeschincariol/instagram-agent-skill | مستخدم | `rd.py ig` و`insta-reader/scripts/ig.py` و`engines/reel_hooks` بينفّذوا الأدوات الخمسة بمعاجم عربي. الـ 13 مهارة في library (`ig-viral` و`ig-story` و`ig-repurpose` مش في `~/.claude/skills`) | (موجود) هوكات الريل وbeat sheet وفحص الكابشن وhumanizer | `python scripts/rd.py ig hooks ...` | MIT |
| 216 | WyattBlue/auto-editor | مستخدم | `auto-editor` 29.3.1 متثبت، وفي وصفة `codekit` (line 4) و`capabilities.py` و`doctor.py`، و5 مهارات في library | (موجود) قص السكوت والأجزاء الميتة تلقائيًا | `auto-editor in.mp4 --margin 0.2s` | Unlicense (ملكية عامة) |
| 217 | sergebulaev/linkedin-skills | متثبت ومش متوصّل | 10 مهارات `linkedin-*` في library (ومتسجّلة كـ plugin `linkedin-skills` كمان) | بوستات وكومنتات LinkedIn بصوت بشري | Skill بالاسم | MIT |
| 218 | Jakeschincariol/youtube-agent-skill | متثبت ومش متوصّل | 10 مهارات `yt-*` في library | سكربت بهوك متقيّم، وعنوان وثامبنيل مع بعض، وEDL من التفريغ، وقراءة الـ retention | Skill: `yt-script` و`yt-edit` | MIT |
| 219 | kajisho5/ffmpeg-skill | متثبت ومش متوصّل | المستودع في `dragon-repos\kajisho5__ffmpeg-skill`. **الـ 10 مهارات اللي في library مهارات هندسية جانبية** (building-python-mcp-servers وshipping-build-artifacts…)، **مش محرك الـ 42 أداة FFmpeg نفسه** | 42 أداة FFmpeg بعقد مقروء للآلة وخطوة تحقق بعد كل تعديل (قص، ترجمة، reframe، loudness، تصدير منصات) + MCP | `npx ffmpeg-skill` (Node 26 وffmpeg موجودين) | MIT |
| 220 | nexu-io/html-video | متثبت ومش متوصّل | 10 مهارات `frame-*` في library، والمستودع في `dragon-repos`، ومذكور في `library.json` | 21 قالب HTML-to-MP4 (داتا، برومو منتج، كتابة حركية، انتقالات) على محرك HyperFrames | Node + Chromium headless + ffmpeg | Apache-2.0. آخر push كان 2026-06 |
| 221 | tradermonty/claude-trading-skills | متثبت ومش متوصّل | 10 مهارات تحليل أسهم في library | screeners وتحليل سوق | Skill بالاسم | MIT. **مالي: مش نصيحة استثمار** |
| 222 | glitternetwork/pinme | متثبت ومش متوصّل | 6 مهارات `pinme-*` في library. `pinme` مش متثبت | نشر صفحة frontend بأمر واحد (IPFS) | `npm install -g pinme` | MIT. **النشر محتوى عام، فمحتاج موافقة صريحة**، وربط الدومين بيحتاج رصيد محفظة |
| 223 | davepoon/buildwithclaude | متثبت ومش متوصّل | 10 مهارات workflow (feature-spec وimplement-feature وrelease-check…) في library | دورة تطوير من المواصفات للتسليم | Skill بالاسم | MIT |
| 224 | Jakeschincariol/linkedin-agent-skill | متثبت ومش متوصّل | 9 مهارات `li-*` في library | إدارة حساب LinkedIn (بوستات، ردود، تقييم بروفايل) | Skill: `li-post` | MIT. بيكرر صف 217 |
| 225 | Jakeschincariol/founder-skill | متثبت ومش متوصّل | 9 مهارات `founder-*` في library | تقييم فكرة بيزنس قبل الإطلاق | Skill: `founder-board` | MIT |
| 226 | Agentchengfeng/chengfeng-videocut-skills | متثبت ومش متوصّل | 8 مهارات `chengfeng-*` في library، والمستودع في `dragon-repos` | مونتاج من التفريغ: قص وترجمة وتصدير ومراجعة بصرية | Skills، والتثبيت بـ npx من Release | Apache-2.0. موجّه للصيني |
| 227 | dominikmartn/nothing-design-skill | متثبت ومش متوصّل | مهارة `nothing-design` في library | واجهات بأسلوب Nothing (أبيض وأسود وتايبوجرافي) | Skill: `nothing-design` | MIT |
| 228 | threerocks/hand-drawn-styles | متثبت ومش متوصّل | مهارة `hand-drawn` في library. مالوش ذكر في الكود (كلمة hand-drawn في الكود تخص كروت تانية) | برومبتات توليد صور بخمس أساليب رسم يدوي | Skill: `hand-drawn` | MIT |
| 229 | yctimlin/mcp_excalidraw | متثبت ومش متوصّل | مهارة `excalidraw-skill` في library، ومذكور في كروت `atlas-docs` | رسم دياجرامات Excalidraw بالكود وتصديرها، وMermaid لـ Excalidraw | `npx -y mcp-excalidraw-server <command>` (Node 20+) | MIT. أمر `share` بيرفع المشهد مشفّر لسيرفر excalidraw، فماتستخدموش من غير موافقة |
| 230 | arjun988/blender-skills | متثبت ومش متوصّل | 9 مهارات في library (blender-director وarchviz وanime-style…)، ومذكور في `creative-studio/SKILL.md` كفهرس | أنماط ومشاهد Blender جاهزة (أنيمي، أرشفيز، عوالم) | Skill + `blender.exe` 5.2 | MIT. محتاج Blender MCP لبعض الخطوات |
| 231 | DreambigOu/ELI5 | متثبت ومش متوصّل | مهارة `eli5` في library | شرح أي حاجة على قد مستوى السامع | Skill: `eli5` | MIT. آخر push كان 2026-03 |
| 232 | NeoLabHQ/context-engineering-kit | متثبت ومش متوصّل | 9 مهارات (actualize وadd-task وanalyse…) في library | تحسين جودة نتايج الـ agent ومراجعة كود | Skill بالاسم | **GPL-3.0**: لو اتنقل كوده لحاجة بتتوزّع لازم تبقى GPL |
| 233 | veedstudio/open-edit | متثبت ومش متوصّل | مهارة `open-edit` في library و`~/.claude/skills`، والمستودع في `dragon-repos\open-edit` | pipeline مونتاج بالـ agent: ترجمة وموشن جرافيك وشرايح ورندر | `npx skills add veedstudio/open-edit --skill open-edit` (Node 20.18.1+، وWindows مدعوم) | Apache-2.0 |
| 234 | NiazMorshed2007/reanimate | متثبت ومش متوصّل | مهارة `reanimate` في library. Bun مش متثبت | يفكك أنيميشن أي موقع فريم بفريم ويثبت إن النسخة بتتحرك زيه | محتاج Bun 1.1+، و**Windows مش متجرّب** | MIT. الأمثلة بتعيد أجزاء من مواقع شركات للدراسة بس |
| 235 | daymade/claude-code-skills | متثبت ومش متوصّل | 9 مهارات متفرقة (cli-demo-generator وcompetitors-analysis…) في library | أدوات تطوير متنوعة | Skill بالاسم | MIT |
| 236 | skills-directory/skill-codex | مستخدم | مهارة `codex` في library. و`@openai/codex` 0.167.0 متثبت، و`dragon_desktop/app.py` بيشغّله كمحرك (`codex exec --json`) | (موجود) تفويض مهمة لـ Codex | `codex exec --json "..."` | MIT. بيستخدم اشتراك ChatGPT |
| 237 | Jakeschincariol/arena-skill | مستخدم | `engine/skills/arena-gate/scripts/arena_gate.py` بينفّذ آلية المستودع ونسخته في `engine/tools/arena/` و`library/arena/` | (موجود) نسخ كتير بتتنافس على نفس المهمة لحد ما تفضل إجابة واحدة | `python arena_gate.py` | MIT. مكلف في التوكنز (91 نداء لـ 16 وكيل) |
| 238 | EL4CTEO/blender-skills | متثبت ومش متوصّل | 9 مهارات (blender-core وblender-character-rigging وblender-export-pipelines…) في library و`~/.claude/skills`، ومذكور في `creative-studio/SKILL.md` | workflows Blender كاملة: modeling وUV وPBR وbaking وrigging وexport وQA | Skill + `blender.exe` 5.2 (المهارات مكتوبة لـ 5.3) | MIT |
| 239 | alisaitteke/photoshop-mcp | متثبت ومش متوصّل | مهارتين `photoshop-*` في library، والمستودع في `dragon-repos\creative`، و`psd_studio/psd.py` بيذكر مكانه بس. **Photoshop مش متثبت** | 118 أداة تحكم في Photoshop من الموديل | `claude mcp add photoshop -- npx -y @alisaitteke/photoshop-mcp` (لازم Photoshop شغال) | MIT. Photoshop نفسه مدفوع |
| 240 | howseen-ai/claude-motion-design | متثبت ومش متوصّل | مهارة `motion-design` في library، ومذكور في `creative-studio` و`library.json` | موشن ديزاين بالكود (HTML + Playwright + ffmpeg) من غير After Effects ولا Remotion | `playwright` و`imageio-ffmpeg` و`numpy` و`Pillow` **كلهم متثبتين**، فمحتاج بس الـ Skill | MIT للكود. الميديا اللي `fetch_assets.py` بيحمّلها ليها رخصها |

## أهم 10 إضافات (حسب القيمة لشغل الفيديو والصور والموشن)

| # | الأداة | ليه | أرخص طريقة للإضافة |
|---|---|---|---|
| 1 | **kajisho5/ffmpeg-skill** | 42 عملية FFmpeg جاهزة بعقد ثابت وخطوة تحقق بعد كل تعديل (reframe وloudness وتصدير منصات). المحرك نفسه مش موجود عندنا لأن library خدت المهارات الجانبية بس | المستودع موجود في `dragon-repos`. انسخ `SKILL.md` الأصلي بتاعه لـ `library/ffmpeg-skill` واستخدم `npx ffmpeg-skill` (Node وffmpeg موجودين) |
| 2 | **JuneYaooo/rea-video** | يفكك أي ريل مرجعي لقطة بلقطة ويطلّع خطة إعادة عمل (`VIDEO.md`)، وده بيكمّل `reverse-any-video` و`video-understand` | المهارة متثبتة. فاضل CLI بـ pip بس (Python وffmpeg موجودين)، وبعدين وصفة في `forge/recipes.py` |
| 3 | **howseen-ai/claude-motion-design** | موشن ديزاين بالكود ببلاش ومن غير رخص، وكل اعتمادياته موجودة على الجهاز | **مافيش تثبيت.** ضيف خطوة `skill:motion-design` في recipes الموشن |
| 4 | **nexu-io/html-video** | 21 قالب فيديو جاهز على HyperFrames، اللي متوصّل أصلًا في الكروت | المستودع والمهارات موجودين. وصّل قوالبه بمسار `npx hyperframes` الموجود |
| 5 | **veedstudio/open-edit** | ترجمة وموشن جرافيك وشرايح ورندر في pipeline واحدة، وWindows مدعوم رسميًا | المهارة متثبتة. أول تشغيل بيجهّز نفسه (Node 26 موجود) |
| 6 | **zhouxiaoka/autoclip** | فيديو طويل لشورتس فيها ترجمة وغلاف ونص نشر، وده شغل مطلوب جدًا | installer لـ Windows x64 من Releases، أو CLI/MCP بـ Python 3.11. محتاج مفتاح موديل لغة |
| 7 | **EL4CTEO/blender-skills** | يكمّل `blender-pro` بالحاجات اللي ناقصاه: rigging وUV وbaking وexport وQA | **مافيش تثبيت.** المهارات متثبتة. وجّه ليها من `creative-studio` وراجع الفرق بين 5.3 و5.2 |
| 8 | **OpenMontageInc/OpenMontage** | 12 pipeline إنتاج وقواعد QA مجرّبة (اتاخد منها شوية في `media_gate`) | اقرا الـ pipelines كمرجع وانقل القواعد بس. **ماتدمجش الكود (AGPL)** |
| 9 | **Agentchengfeng/chengfeng-videocut-skills** | مونتاج من التفريغ بخطوات قص وترجمة وتصدير ومراجعة بصرية | المهارات متثبتة. خد طريقة الـ workbench وطبّقها على التفريغ العربي من faster-whisper |
| 10 | **yctimlin/mcp_excalidraw** | دياجرامات وسبورة مرسومة لفيديوهات الشرح، وتتصدّر صور | `npx -y mcp-excalidraw-server` من غير تثبيت دائم. ماتستخدمش `share` |

### ملاحظات جانبية

- **ffmpeg-skill:** الـ 10 مهارات اللي اتنسخوا منه مش مهارات FFmpeg خالص، فاسمه في الكتالوج بيوحي بقدرة مش موجودة فعلًا. نفس الكلام على OpenMontage: مهاراته المنسوخة أغلبها APIs سحابية مدفوعة.
- **`SKILL.md` سطر 213** بيقول إن مهارات `library/` «مش متثبتة». بس 495 من 570 مجلد فيها موجودين دلوقتي في `~/.claude/skills/` وClaude بيحمّلهم. يعني الجملة دي محتاجة تتحدّث.
- **dev-browser:** متوصّل في recipes بس مش مدعوم على Windows، فالخطوة بتعتمد عمليًا على `engine:chrome`.
- **jadx-ai-mcp:** إضافته الوحيدة إعادة التسمية جوه JADX. التحليل نفسه بيغطيه REA مع `jadx-headless-mcp`، فمش في التوب 10.
- **ida-pro-mcp وphotoshop-mcp:** محتاجين برامج مدفوعة مش متثبتة (IDA Pro وPhotoshop). Ghidra وrizin وGIMP وKrita بدايل موجودة.
- **MoneyPrinterTurbo:** بيكرر pipelines موجودة وبيحتاج مفاتيح API، فاتأجل.
- **reanimate:** محتاج Bun وWindows مش متجرّب، فاتأجل.
- **المهارات المالية (day-trader وclaude-trading-skills):** للتحليل بس. Claude مش مستشار مالي مرخّص ومش هينفّذ صفقات.
- **رخص لازم تاخد بالك منها:** OpenMontage (AGPL-3.0)، وcontext-engineering-kit (GPL-3.0)، وtrailofbits (CC-BY-SA-4.0)، وunslop (CC-BY-4.0).
