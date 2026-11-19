# كل قدرات واتصالات التنين الأسود — v1990.10.0 (2026-11-12)

اتولّد من `tools/powers/powers.json` بأمر `python scripts/dragon.py tool powers map --md`. ماتعدّلش هنا: عدّل السجل وولّد تاني.

**التكلفة:** ✅ ببلاش (توكنز بس) · 🔒 بموافقة صريحة كل مرة · 💰 مدفوع: السعر بالظبط من الأداة + «موافق» على المبلغ ده + الرصيد قبل وبعد · ⛔ ممنوع.
**المكان:** pc = لابتوب صاحب التنين (Claude Code أو التطبيق) · cloud = محادثة claude.ai أو Claude Code سحابة · both = الاتنين.
**القياس:** 2026-11-12: references/MACHINE_INVENTORY_20261112.md (helper inventory, every row run on the laptop)

**الراوتر:** `tool powers route "<الطلب>"` · **أول رد:** `tool powers first "<الطلب>"` · **الموجود هنا:** `tool powers doctor --mcp`

## claude-code — قدرات Claude Code نفسه (وكلاء، خلفية، جدولة، بحث، ذاكرة)

### وكلاء مساعدين بالتوازي (`cc-agents`) — ✅ ببلاش · both
- **إزاي:** أداة Agent: subagent_type = helper-1 … (أجزاء مستقلة) أو Explore (بحث قراية بس في ملفات كتير) أو Plan (خطة تنفيذ) أو general-purpose. المستقلين في رسالة واحدة عشان يشتغلوا مع بعض، وكل واحد برومبت كامل لأنه مش شايف المحادثة. راجع شغلهم بنفسك.
- **في السحابة:** Claude Code cloud: نفس الأداة. claude.ai: مفيش وكلاء، اشتغل بالتسلسل.

### Workflow: تنسيق عشرات الوكلاء بسكربت (`cc-workflow`) — 🔒 بموافقة · pc
- **إزاي:** أداة Workflow، بس لو المستخدم كتب «workflow» أو «وكلاء كتير» صراحة. حمّل مهارة workflow-authoring الأول.
- **في السحابة:** مش متاح في claude.ai.

### شغل طويل في الخلفية ومتابعته (`cc-background`) — ✅ ببلاش · pc
- **إزاي:** Bash/PowerShell بـ run_in_background، وMonitor لمتابعة شرط أو ملف log، وTaskStop للإيقاف. ممنوع sleep للاستنا. في التنين: `dragon.py status` و`last`.
- **في السحابة:** claude.ai: أوامر قصيرة، والطويل يتقسم أو يروح سحابة Higgsfield بـ background:true.

### جدولة مهام متكررة (`cc-schedule`) — 🔒 بموافقة · pc
- **إزاي:** CronCreate / CronList / CronDelete أو ScheduleWakeup. أي جدولة جديدة بموافقة.
- **في السحابة:** مهارة schedule (وكلاء سحابة مجدولين) بموافقة.

### الكلام مع جلسات Claude Code التانية وتطبيق التنين (`cc-sessions`) — ✅ ببلاش · pc
- **إزاي:** ListAgents ثم SendMessage. والتطبيق: أداة blackdragon_app أو `dragon.py tool machine app status|chats|read|send|ask`.
- **في السحابة:** مش متاح.

### البحث والقراية من النت (`cc-web`) — ✅ ببلاش · both
- **إزاي:** WebSearch بـ mode standard، وextended لو النتيجة ضعيفة أو الموضوع حديث جدًا أو أسعار. WebFetch لقراية صفحة. للميديا ابدأ بـ media-hunter.
- **في السحابة:** web_search / web_fetch.

### الذاكرة الدايمة والدروس (`cc-memory`) — ✅ ببلاش · both
- **إزاي:** ذاكرة Claude Code (ملف لكل حقيقة + MEMORY.md)، و`dragon.py tool brain learn "الدرس" --domain …`، و`references/LESSONS.md` بتاريخه.
- **في السحابة:** LESSONS.md جوه الحزمة + اطلب منه يحفظ.

### تحميل الأدوات المؤجّلة (`cc-toolsearch`) — ✅ ببلاش · pc
- **إزاي:** قبل ما تقول «معنديش أداة»: ToolSearch بـ `select:Name1,Name2` أو بكلمات، وحمّل كل اللي هتحتاجه في نداء واحد.
- **في السحابة:** —

## mcp — خوادم MCP المربوطة بحساب Claude (Higgsfield، Suno، REA، كروم، التحكم في الجهاز، Claude Docs، التنين)

### توليد Higgsfield المدفوع (صور، فيديو، صوت، تكبير، شيل خلفية، بريسيت، GPU) (`hf-generate`) — 💰 مدفوع · both
- **إزاي:** قبل أي أداة: `dragon.py tool hf check TOOL` (exit 3 = مدفوعة) ثم `tool hf ask TOOL --price N --balance B`، وبعدين «موافق» على السعر ده بالظبط. balance قبل وبعد. البديل المجاني الأول: الكود (HTML/Blender/ffmpeg)، أو upscayl-bin وrembg على الجهاز.
- **في السحابة:** نفس القاعدة.

### بناء ونشر موقع أو لعبة متصفح على Higgsfield (`hf-website`) — 🔒 بموافقة · both
- **إزاي:** get_workflow_instructions {workflow:"website-builder-flow"} الأول. البناء في sandbox_exec مجاني، والنشر (deploy/publish) بموافقة صريحة.
- **في السحابة:** نفسه.

### الترند وتفكيك أي ريل (`hf-trend`) — ✅ ببلاش · both
- **إزاي:** `dragon.py tool hf trend live|list|find|commands SLUG_OR_URL` + `tiktok_music_trending` و`get_presets source=genjutsu category=genjutsu-trending`. `/katana` الإنتاجي بيصرف: اطلب «تحليل فقط».
- **في السحابة:** نفسه.

### Suno: أغاني وأصوات (مدفوع) (`suno`) — 💰 مدفوع · both
- **إزاي:** mcp__claude_ai_suno__*: audio-create / audio-full-song / stems / covers مدفوعين: السعر + «أيوه» وكل تحميل بسؤال لوحده. القراية مجانية: library-list / library-search / account-usage / voices-list. (Suno MCP: 41 أداة.)
- **في السحابة:** نفسه لو مربوط.

### REA: هندسة عكسية لأي ملف أو برنامج أو موقع (`rea-mcp`) — ✅ ببلاش · pc
- **إزاي:** mcp__rea__* (inspect_artifact، inspect_pe_imports، analyze_javascript_application، analyze_web_bundle، inspect_android_package، compare_*…) أو `rea <command> … --format md`. ابدأ بالسريع، وGhidra (`rea analyze`) لما تحتاج الكود. حمّل rea-ultra. لملفات المستخدم بس، مش لكسر حماية. (229 أداة MCP). (اتقاس 2026-11-12: 229 أداة MCP، rea 6.8.0، Ghidra 12.1.4 وJADX سليمين؛ `rea doctor` بيقول healthy:false بس عشان Hopper/IDA مش متثبتين، ودول اختياريين.)
- **مهارات:** rea-ultra, reverse-engineer-anything
- **في السحابة:** `dragon.py tool rea-ultra` (خطط بس) أو اطلب الملف على اللابتوب.

### التنين كأدوات MCP من أي جلسة Claude Code (`black-dragon-mcp`) — ✅ ببلاش · pc
- **إزاي:** mcp__black-dragon__blackdragon_find / show / run / engines / verify / omni / rea / retool / skill / superpowers / ultra (حمّلهم بـ ToolSearch). (11 أداة.)
- **في السحابة:** `python3 scripts/dragon.py find|show|engines`.

### التحكم في الكمبيوتر كله (شاشة، ماوس، كيبورد، نوافذ، برامج، صوت، إعدادات) (`pc-control`) — 🔒 بموافقة · pc
- **إزاي:** mcp__blackdragon__system للحاجات اللي ليها أمر (تشغيل وقفل برامج، عمليات، صوت، سطوع، حافظة، شبكة)، وmcp__blackdragon__computer لأي برنامج ملوش أمر (صورة ← فعل ← تأكيد). من غير التطبيق: `dragon.py tool machine pc ACTION`. القفل والإطفاء والإزالة والخدمات بموافقة. الماوس في الركن الشمال اللي فوق = وقف فورًا. (3 أدوات: computer وbrowser وsystem، والتطبيق هو اللي بيضيفهم.)
- **في السحابة:** مش متاح من السحابة.

### كروم الحقيقي بتاع المستخدم (تابات، قراية، ضغط، فورم، سكرينشوت، كونسول، شبكة، GIF) (`chrome`) — ✅ ببلاش · pc
- **إزاي:** mcp__claude-in-chrome__*: tabs_context_mcp الأول، وتاب جديد بـ tabs_create_mcp، وبعدين navigate / read_page / find / computer / form_input / javascript_tool / read_console_messages / read_network_requests / gif_creator. حمّلهم كلهم في نداء ToolSearch واحد، وماتدوسش على حاجة بتفتح alert. بديل: mcp__blackdragon__browser أو محرك chrome. (20 أداة.) (20 أداة، ومش بتظهر في `claude mcp list`.)
- **مهارات:** claude-in-chrome
- **في السحابة:** محرك cloud_browser («سحاب») أو Playwright في سحابة Higgsfield.

### Claude Docs: مستند حي (`claude-docs`) — ✅ ببلاش · both
- **إزاي:** بس لو المستخدم طلب مستند: batch بهيكل المستند أول نداء، وبعدين guide topic.index.
- **في السحابة:** نفسه.

### خدمات محتاجة تسجيل دخول (`mcp-auth`) — 🔒 بموافقة · both
- **إزاي:** Remote Desktop Commander وgraphify محتاجين تسجيل من صفحة الربط في claude.ai (https://claude.ai/settings/connectors) أو `/mcp`. لحد ما يتسجّلوا، القدرة دي مش متاحة. ماتطلبش أكواد أو توكن.
- **في السحابة:** نفسه.

## cloud — سحابة Higgsfield المجانية (جهاز لينكس جنب اللابتوب)

### سحابة Higgsfield المجانية: رندر وترميز وتفريغ على لينكس (`hf-sandbox`) — ✅ ببلاش · both
- **إزاي:** mcp__claude_ai_Higgsfield__sandbox_exec {command, size:"xl", background:true}. اتقاس 2026-11-11: العادي 1 معالج/8 جيجا قد الجهاز، وXL 4 معالجات/16 جيجا أسرع 2.2–2.7× في x264. مفيش GPU ولا Blender جاهز. الأمر العادي 120 ث، والخلفية 15 د، والملفات 24 ساعة. الدخول: media_upload ثم PUT ثم media_confirm. الخروج: رابط رفع قبل الأمر و`curl -f -X PUT --upload-file`. balance قبل وبعد. حمّل higgsfield-free وhiggsfield-cloud. (Higgsfield فيه 169 أداة MCP، أغلبها مدفوع.) (Higgsfield MCP: 169 أداة.)
- **مهارات:** higgsfield-free, higgsfield-cloud
- **في السحابة:** نفس الأداة لو Higgsfield مربوط في claude.ai.

### رندر Blender (Cycles) على السحابة (`hf-blender`) — ✅ ببلاش · both
- **إزاي:** مهارة hf-blender-render (`skills/hf-blender-render`) + `dragon.py tool hf-blender plan|pack|check-frames`. تنزيل Blender بموافقة (`HF_BLENDER_ALLOW_DOWNLOAD=YES`).
- **مهارات:** hf-blender-render
- **في السحابة:** نفسه.

### 3D Jutsu: Blender 5.2 مستضاف في Higgsfield (`hf-3d-jutsu`) — ✅ ببلاش · both
- **إزاي:** scene_builder_3d_create_project / run_python / query_python / get_glb / get_blend / search_assets (اتقاسوا 0 كريدت). `scene_builder_3d_generate_*` مدفوع. القالب: `dragon.py tool hf blender template`.
- **في السحابة:** نفسه.

## engine — محركات التنين (python -m dragon run …)

### مونتاج التنين الكامل (`eng-montage`) — ✅ ببلاش · both
- **إزاي:** `dragon.py run dragon_montage plan "…" --clip a.mp4 [--music m.mp3]` ← ستوري بورد واستنى «موافق» ← `go --job DIR --rounds 3` ← `verify`.
- **في السحابة:** نفسه (النسخة المدمجة).

### سينما الفوتيج: فيلم تكريم بأغنية (`eng-cinema`) — ✅ ببلاش · both
- **إزاي:** `dragon.py film spec.json --stills 1.5,7.5` ثم `dragon.py film spec.json`. مهارة black-dragon-cinema.
- **مهارات:** black-dragon-cinema
- **في السحابة:** نفسه.

### toon: فيديو أو صورة لأسلوب أفلام الأنيميشن (`eng-toon`) — ✅ ببلاش · pc
- **إزاي:** `python -m dragon run toon image IN OUT --style S [--max-side N]` أو `video IN.mp4 OUT.mp4 --style S [--fps N] [--seconds 3] [--max-side N] [--no-deflicker]`. الأساليب (`run toon styles`): 3d (DCT-Net)، hayao، shinkai، paint، ai3d (SD-Turbo، الأقوى وأبطأ ~20 ث للصورة). كله على المعالج (مفيش GPU NVIDIA): معاينة `--seconds 3` الأول. `setup` بينزّل موديلات (بموافقة). hayao وshinkai رخصتهم غير تجارية. وجوه الحزمة: `dragon.py tool toon doctor|styles`.
- **في السحابة:** `tool toon` بالأساليب اللي مش محتاجة موديلات تقيلة، أو ffmpeg/OpenCV في سحابة Higgsfield.

### ريل متحدث (`eng-talking-head`) — ✅ ببلاش · both
- **إزاي:** `dragon.py run talking_head --help`.
- **في السحابة:** نفسه.

### فيلم موشن كصفحة ويب (`eng-web-film`) — ✅ ببلاش · both
- **إزاي:** `dragon.py run web_film …` و`node app/engines/render/render.cjs --in page.html --out film.mp4 --duration S --strict`. التقيل منه على سحابة Higgsfield (Chromium موجود).
- **في السحابة:** نفسه.

### استوديو الصوت: كلام بتوقيت الكلمات وSRT (`eng-voice`) — ✅ ببلاش · both
- **إزاي:** `dragon.py run voice_studio --help`، وedge-tts على الجهاز.
- **في السحابة:** نفسه.

### محركات تانية: editorial، shadow_theatre، reel_hooks، kling_director، matrices، cards (`eng-other`) — ✅ ببلاش · both
- **إزاي:** `dragon.py engines` للقايمة الحية (15 محرك على اللابتوب)، و`dragon.py run <engine> --help`. استثناء: `cards` مابيقبلش `--help` (exit 2): استخدم `run cards stats` (5,361 كارت، 2,901 جاهزين) أو `run cards list`. kling_director بيكتب برومبت بس ومابيصرفش.
- **في السحابة:** نفسه.

### KOSIF: تحميل مسرّع بتعدد اتصالات واستكمال (`eng-kosif`) — ✅ ببلاش · pc
- **إزاي:** `dragon.py kosif …` (= run kosif)، أو `python ~/dragon-tools/fast_dl.py URL`، أو aria2c. فيديوهات المنصات: yt-dlp. مهارة kosif-downloads.
- **مهارات:** kosif-downloads, video-grabber
- **في السحابة:** curl/aria2 في سحابة Higgsfield (نت مركز بيانات).

### محرك chrome و«سحاب» (متصفح بيتبث لايف) (`eng-chrome`) — ✅ ببلاش · pc
- **إزاي:** `dragon.py chrome launch|tabs|snapshot|click|type|shot|pdf …` و`dragon.py sahab start [--open]|status|url|stop`.
- **في السحابة:** Playwright في سحابة Higgsfield.

### Blender في الخلفية على الجهاز (`eng-blender`) — ✅ ببلاش · pc
- **إزاي:** `blender -b` (Blender 5.2) أو `dragon.py run blender …` أو `dragon.py tool blender-pro doctor|plan|validate|render --execute`. مهارة blender-pro. الطويل ممكن يروح hf-blender.
- **مهارات:** blender-pro, creative-studio
- **في السحابة:** hf-blender أو 3D Jutsu.

### محاكي 3D لأي ماكينة + فيلم 60 فريم (`teardown`) — ✅ ببلاش · both
- **إزاي:** مهارة `skills/teardown` (اقرا STYLE_AR.md الأول، واطلب صورة مرجع). أول مرة `npm install` جوه فولدرها. النشر بموافقة.
- **مهارات:** teardown
- **في السحابة:** نفسه (node في سحابة Higgsfield).

## re — الهندسة العكسية والتحليل (retool 34 أداة، omni، REA)

### retool: فرز سريع لأي ملف + 34 أداة (`re-triage`) — ✅ ببلاش · pc
- **إزاي:** `python ~/re-tools/retool.py triage FILE [--deep] [--out DIR]` ← `retool.py list` ← `retool.py run ID …`. أدوات وقت التشغيل (frida، pe-sieve، x64dbg، mitmdump، adb) بموافقة. أو `dragon.py tool re plan|investigate|audit`. اتقاس: 34/34 أداة متثبتة. `rea` 6.8.0، و`rea doctor` بيقول healthy:false عشان Hopper/IDA مش متثبتين (اختياري)؛ Ghidra 12.1.4 وJADX سليمين. (اتقاس: 34 من 34 أداة متثبتة.)
- **مهارات:** rea-ultra
- **في السحابة:** `dragon.py tool re plan FILE` و`tool omni`.

### omni: تصنيف وخطة تحليل لأي هدف (`re-omni`) — ✅ ببلاش · both
- **إزاي:** `dragon.py tool omni classify|probe|plan TARGET --depth 3|report|hyp|bayes`. مبيشغّلش الهدف ومبيتصلش بالنت.
- **مهارات:** omni-analyst
- **في السحابة:** نفسه.

### فحص حزمة أو مجلد قبل التثبيت (`re-audit`) — ✅ ببلاش · both
- **إزاي:** `dragon.py tool re audit PATH` (+ YARA-X لو موجود) و`dragon.py tool pack inspect FILE`.
- **في السحابة:** نفسه.

## program — برامج الجهاز على الـ PATH

### برامج الفيديو: ffmpeg، melt، Natron، mkvmerge، scenedetect، auto-editor (`prog-video`) — ✅ ببلاش · pc
- **إزاي:** على الـ PATH بالاسم. ffmpeg 9: `-/filter_complex FILE` بدل `-filter_complex_script`، وscale بـ force_original_aspect_ratio=decrease قبل pad. auto-editor بـ `--margin 0.3sec`.
- **في السحابة:** ffmpeg في الحزمة وفي سحابة Higgsfield.

### برامج الصور: magick، gimp، inkscape، upscayl، krita، darktable، rawtherapee، rembg، exiftool (`prog-image`) — ✅ ببلاش · pc
- **إزاي:** `upscayl-bin` (تكبير 4×)، `rembg` (شيل الخلفية، بدل remove_background المدفوع)، `magick`، `gimp-console-3.2`، `inkscape`، `kritarunner`، `darktable-cli`، `rawtherapee-cli`، `exiftool`. وPSD من غير فوتوشوب: `dragon.py tool psd`.
- **في السحابة:** ImageMagick وPillow في سحابة Higgsfield.

### برامج الصوت: whisperx، faster-whisper، demucs، deep-filter، edge-tts (`prog-audio`) — ✅ ببلاش · pc
- **إزاي:** `whisperx` (3.8.6) للتفريغ وتوقيت الكلمات، و`demucs` (فصل)، و`deep-filter` (تنضيف)، و`edge-tts`. faster-whisper مكتبة بايثون بس (مفيش أمر بالاسم ده): `from faster_whisper import WhisperModel`. كله على المعالج. التقيل على سحابة Higgsfield XL (faster-whisper موجود هناك).
- **في السحابة:** faster-whisper في سحابة Higgsfield.

### تحميل: yt-dlp، aria2c، fast_dl (`prog-download`) — ✅ ببلاش · pc
- **إزاي:** `yt-dlp` (بكوكيز المتصفح على الجهاز)، `aria2c`، `python ~/dragon-tools/fast_dl.py URL`. سجّل المصدر في sources.txt.
- **في السحابة:** يوتيوب غالبًا مقفول من السحابة: اطلب الملف.

### مستندات وأرشيف: pandoc، 7z، jq، rg، gh (`prog-docs`) — ✅ ببلاش · pc
- **إزاي:** `pandoc` و`7z` و`jq` و`gh` (مسجّل: push ونشر وissues بموافقة). مفيش `rg` على الـ PATH: استخدم أداة Grep. بايثون: python-docx وpython-pptx وopenpyxl و`import pymupdf` (مش fitz). من بايثون نادي `npm.cmd` مش `npm`. مهارات docx/pptx/xlsx/pdf.
- **في السحابة:** مكتبات بايثون في الحزمة أو السحابة.

### موديلات محلية على المعالج (torch CPU، mediapipe، opencv) (`prog-gpu`) — ✅ ببلاش · pc
- **إزاي:** اللابتوب (Core 5 120U، 16 جيجا) **مفيهوش كارت NVIDIA**: torch 2.8.0+cpu وcuda=False، فكل موديل بيشتغل على المعالج وأبطأ. mediapipe أول import ~35 ث. moviepy قديم 0.2.3 (`from moviepy.editor import`). الديسك C فيه 204 جيجا وD فيه 0.9 جيجا بس. الحاجة اللي محتاجة GPU بجد: اعرض `gpu_*` في Higgsfield (مدفوع) أو قول إنها هتاخد وقت على المعالج.
- **في السحابة:** CPU بس.

## skill — مهارات متثبتة على الجهاز برّه الحزمة

### مهارات الويب والتصميم: frontend-design، web-artifacts-builder، webapp-testing، canvas-design، algorithmic-art، theme-factory (`skill-web`) — ✅ ببلاش · both
- **إزاي:** أداة Skill بالاسم (متثبتة في ~/.claude/skills)، وtheme-factory متضمّنة كمان في skills/.
- **في السحابة:** مهارات claude.ai المدمجة.

### مستندات Office وPDF (`skill-office`) — ✅ ببلاش · both
- **إزاي:** مهارات anthropic-skills:docx / pptx / xlsx / pdf بأداة Skill.
- **في السحابة:** نفسه.

### بناء مهارات وخوادم MCP (`skill-build`) — ✅ ببلاش · both
- **إزاي:** anthropic-skills:skill-creator (بناء وقياس مهارة)، وmcp-builder (خادم MCP). التحزيم: `dragon.py tool package`.
- **في السحابة:** نفسه.

### التفكير والجودة: ultra-mind، dragon-genius، expert-council، montage-arena (`skill-mind`) — ✅ ببلاش · both
- **إزاي:** `dragon.py tool brain "الطلب"` أول حاجة، وبعدين skills/ultra-mind وexpert-council وdragon-genius (بوابة `tool genius gate`) وmontage-arena.
- **في السحابة:** نفسه (متضمّنين).

### أوامر ويندوز من غير مفاجآت (`skill-windows`) — ✅ ببلاش · pc
- **إزاي:** `dragon.py tool windows-lint --shell powershell|bash "COMMAND"` قبل الأوامر المعقدة. بايثون: `python -X utf8`.
- **في السحابة:** —

## hub — كتالوجات وسوبر باور

### سوبر باور: 212 أداة و5,900 قدرة (`hub-superpowers`) — ✅ ببلاش · pc
- **إزاي:** `dragon.py tool sp find "…"` (بينادي hub.py الأحدث)، `tool sp doctor`، `tool sp qc FILM.mp4`. تشغيل أداة: `tool sp run ID` (بوابة موافقة). اتقاس: 212 أداة في 12 مجال، 205 جاهزين (7 محتاجين chromium أو typescript). (اتقاس: 212 أداة في 12 مجال، 205 جاهزين؛ 6 محتاجين chromium وواحدة typescript.)
- **في السحابة:** الكتالوج من `dragon.py find`.

### كتالوج التنين (22 ألف عنصر) وأطلس GitHub (`hub-catalog`) — ✅ ببلاش · both
- **إزاي:** `dragon.py find "…"` و`show ID`، و`tool github-atlas find "…"` (1000 مستودع، أوفلاين)، و`tool library find "…"` (12 حزمة + 105 برومبت).
- **مهارات:** github-atlas
- **في السحابة:** نفسه.

### صيّاد الميديا: 615 موقع + 19 مصدر API (`hub-media`) — ✅ ببلاش · both
- **إزاي:** `dragon.py tool hunter hunt|search|sites|get` و`tool hunter615`. على الجهاز كمان المحرك الخارجي `python -I ~/OneDrive/Desktop/تحليل/media_hunter/mh.py`.
- **مهارات:** media-hunter
- **في السحابة:** `tool hunter` (المصادر اللي من غير مفتاح).

## desktop — تطبيق التنين الأسود على ويندوز

### تطبيق التنين الأسود: تعديل وبناء (`desktop-app`) — 🔒 بموافقة · pc
- **إزاي:** الكود في ~/OneDrive/Desktop/التنين الأسود/apps/dragon_desktop (نسخة منه في app/apps/dragon_desktop). نسخة احتياطية في %APPDATA%/BlackDragon/source_backups/<التاريخ> ← تعديل صغير ← `python -m py_compile app.py control.py mcp_control.py voice.py` ← `powershell -ExecutionPolicy Bypass -File build.ps1`. المستخدم بيحدّث بزرار «حدّث دلوقتي».
- **في السحابة:** عدّل النسخة اللي في الحزمة وسلّمها.

