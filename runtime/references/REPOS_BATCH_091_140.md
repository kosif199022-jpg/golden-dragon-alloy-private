# تقرير قدرات: المستودعات من 91 لـ 140 في الكتالوج

- **المصدر:** صفوف البيانات من 91 لـ 140 (العد بيبدأ من 1 ومن غير الهيدر) في `%USERPROFILE%\Downloads\all-repos-catalog.csv`.
- **التاريخ:** 2026-11-16.
- **الطريقة:** نفس طريقة `REPOS_PILOT_40.md`. دوّرنا باسم الأداة أو الباكدج جوه `golden-dragon` كله (engine وmind وreferences وmodules وlibrary وapps)، وفصلنا ملفات الكود (`.py` و`.js` و`.mjs` و`.ts` و`.sh` و`.ps1` و`.html`) عن الكتالوجات (`RD_TOP500_REPOS.md` و`RD_INTEL_REPOS.md` و`library.json` و`mind/intel` وداتا `github-atlas`). وربطنا المهارات المنسوخة في `library/` بمصدرها من `SOURCE.json`. وكشفنا على الجهاز بـ `where.exe` و`python -c "import X"` و`pip show` و`npm ls -g` وفولدرات `dragon-repos` و`dragon-tools` و`~/.claude.json` و`~/.claude/plugins`. وقرينا الرخصة والنجوم وآخر push بـ `gh api repos/OWNER/REPO` و`gh repo view`. ماتثبّتش أي حاجة، وماعملناش clone، وماشغّلناش كود أي مستودع.
- **أسماء ناقصة في الكتالوج:** 4 صفوف من غير owner، فحددناها كده: `auto-editor` = `WyattBlue/auto-editor` (ونفس الصف 116 بالظبط)، و`blender-mcp` = `ahujasid/blender-mcp` (اتنقل لـ `ahujasid/mcp-for-blender`)، و`cut-as-code` = `WhiteTowerAI/cut-as-code`، و`ECCV2022-RIFE` = `hzwer/ECCV2022-RIFE`. و`kyamagu/skia-python` بقى `skia-python/skia-python`.
- **معنى الحالة:**
  - **مستخدم:** فيه كود في المهارة بيشغّله أو بيعمله vendor أو بيديله وصفة تثبيت (codekit و`library/mcp_servers.json` و`setup_env.py`)، أو فيه مهارات منه متنسخة في `library/`.
  - **متثبت ومش متوصّل:** موجود على الجهاز، بس المهارة بتكتشفه في `doctor` أو بتعدّه في قايمة بس، وماحدش بيستدعيه.
  - **قدرة جديدة:** مش متثبت ولا متوصّل. لو ليه ذكر فهو في الكتالوجات والمراجع بس.

## الملخص

| الحالة | العدد |
|---|---|
| مستخدم | 26 |
| متثبت ومش متوصّل | 4 |
| قدرة جديدة | 20 |
| **الإجمالي** | **50** |

## جدول الخمسين

| # | Repo | الحالة | الدليل على الجهاز وفي المهارة | الإضافة الملموسة | التشغيل على Windows | ملاحظة الرخصة |
|---|---|---|---|---|---|---|
| 91 | anthropics/claude-plugins-official | متثبت ومش متوصّل | متسجّل كـ marketplace في `~/.claude/plugins/known_marketplaces.json` (اتحدّث 2026-11-16). في المهارة مالوش ذكر غير داتا `github-atlas` و`toolbelt.md` | دليل plugins رسمي (commands وagents وhooks وMCP) تختار منه وتثبّت بأمر واحد | `/plugin` جوه Claude Code | Apache-2.0. كل plugin ليه رخصته. 47k نجمة |
| 92 | microsoft/playwright-mcp | مستخدم (متوصّل بس مش متثبت) | وصفة في `library/mcp_servers.json` (`claude mcp add playwright npx @playwright/mcp@latest`) ومذكورة في `SKILL.md`. مش متسجّل في `~/.claude.json` (المتسجّل `black-dragon` و`rea` بس) | (موجود كوصفة) تحكم في المتصفح من Claude بـ accessibility snapshots | `claude mcp add playwright npx @playwright/mcp@latest` | Apache-2.0 |
| 93 | modelcontextprotocol/python-sdk | مستخدم | `mcp` 2.3.0 متثبت. بيتعمله import في `library/bioqc-mcp/bioqc_mcp.py` و`library/qiaomu-anything-to-notebooklm/feishu-read-mcp/src/server.py` و`library/mcp-builder/scripts/connections.py` | (موجود) بناء سيرفرات MCP بـ Python (FastMCP) | `pip install mcp` | MIT |
| 94 | anthropics/claude-agent-sdk-python | قدرة جديدة | `claude_agent_sdk` مش متثبت. ذكره في `mind/intel/repos.json` وداتا `github-atlas` بس | تشغيل لوب Claude Code من سكربت Python (دفعات رندر أو مراجعة بالليل من غير ما حد يكتب) | `pip install claude-agent-sdk` (بيحتاج Claude Code CLI، وهو موجود) | MIT |
| 95 | shadcn-ui/ui | مستخدم | `library/web-artifacts-builder/scripts/init-artifact.sh` (من anthropics/skills) بيفك `shadcn-components.tar.gz` جوه المشروع، و`ui-ux-pro-max` بيدوّر في داتا shadcn | (موجود) مكونات React جاهزة لصفحات وartifacts | السكربت بـ Git Bash، أو `npx shadcn@latest add button` | MIT. 128k نجمة |
| 96 | lucide-icons/lucide | مستخدم | `library/stack-diagram/scripts/fetch_icons.py` بيجيب أيقونات Lucide، و`ui-ux-pro-max/scripts/design_system.py` بيقترحها | (موجود) أيقونات SVG موحدة للدياجرامات والموشن | `python fetch_icons.py` أو `npm i lucide-static` | ISC (GitHub بيقول NOASSERTION). جزء من الأيقونات MIT من Feather |
| 97 | darkroomengineering/lenis | قدرة جديدة | مش موجود. `library/reanimate/scripts/capture.ts` بيكشف لو موقع بيستخدم Lenis بس | smooth scroll متحكم فيه لصفحات scroll-story | `npm i lenis` | MIT. **قيمته للفيديو قليلة**: الرندر فريم بفريم مش محتاج smooth scroll |
| 98 | shikijs/shiki | قدرة جديدة | مش موجود. ذكره في مراجع `hyperframes` (`film.md` و`discovery.md`) بس | تلوين كود بثيمات VS Code بالظبط كـ HTML أو tokens، فتعمل فيديوهات كود (typing وhighlight سطر سطر) | `npm i shiki` (ESM) والرندر بـ Playwright | MIT |
| 99 | iconify/iconify | مستخدم | `engine/tools/media_hunter_615/mh.py` و`media_hunter/mh.py` بيدوّروا في `api.iconify.design` ويرجّعوا SVG | (موجود) بحث في أكتر من 200 ألف أيقونة | من خلال media_hunter (API، مافيش تثبيت) | MIT للكود. كل مجموعة أيقونات ليها رخصتها |
| 100 | style-dictionary/style-dictionary | قدرة جديدة | مش موجود ومالوش ذكر | ملف tokens واحد للبراند (ألوان وخطوط ومسافات) يطلع منه CSS وJS لكل قوالب الموشن | `npm i -D style-dictionary` ثم `npx style-dictionary build` | Apache-2.0. ملف JSON وCSS variables يدوي بيكفّي في الغالب |
| 101 | Graphify-Labs/graphify | مستخدم (متوصّل بس مش متثبت) | مهارة `library/graphify` متنسخة (`SOURCE.json`)، و`cards/lib/knowledge_graph.py` بيرجّع `GRAPHIFY_NOT_EXECUTED` لما الـ CLI مش موجود. الـ CLI مش متثبت | (موجود كمهارة) خريطة معرفة لكود أو مستندات تتسأل | التثبيت حسب README المهارة المنسوخة | Apache-2.0 (وأجزاء MIT). 148k نجمة |
| 102 | affaan-m/ECC | قدرة جديدة | مش متنسخ. ذكره في `dragon-genius/references/sources.md` و`fusion/index.json` وكتالوجات بس | نظام skills وmemory وhooks لتحسين أداء الوكيل نفسه، مش للميديا | `npx skills add affaan-m/ECC` (أو حسب README) | MIT. 303k نجمة، وحجمه كبير جدًا |
| 103 | heygen-com/hyperframes | مستخدم (متوصّل بس مش متثبت) | 10 مهارات منه متنسخة في `library/` (hyperframes وhyperframes-cli وmedia-use وslideshow وغيرهم)، ووصفة npm في `codekit.py` (line 1). الكود متنزّل في `dragon-repos\hyperframes`، بس الـ npm مش متثبت | (موجود) HTML لفيديو deterministic بتايملاين | `codekit install hyperframes` ثم `npx hyperframes render` | Apache-2.0 |
| 104 | heygen-com/hyperframes-community-skills | قدرة جديدة | مش متنسخ ومالوش ذكر | 8 مهارات جاهزة: `vox-explainer` و`camera-3d-captions` و`day-in-my-life` و`p5-paint-animation` و`session-story` وغيرهم | انسخ الفولدر المطلوب من `skills/` لـ `library/` مع `SOURCE.json` | Apache-2.0. 260 نجمة بس، فراجع الجودة قبل الاعتماد |
| 105 | rhasspy/piper | مستخدم | `piper-tts` 1.8.0 و`piper.exe` متثبتين، و`engines/voice_studio` بيشغّله (`piper_speak`). **الصوت الافتراضي `ar_JO-kareem-medium` مش متنزّل** (`~/.cache/kosif/piper` مش موجود) | (موجود) TTS عربي أوفلاين على CPU | `python -m piper.download_voices --download-dir %USERPROFILE%\.cache\kosif\piper ar_JO-kareem-medium` | الريبو ده MIT و**archived**. الباكدج المتثبت جاي من `OHF-Voice/piper1-gpl` ورخصته **GPL-3.0** |
| 106 | microsoft/onnxruntime | مستخدم | `onnxruntime` 1.31.1، ومستخدم في `engine/tools/toon/engine/__init__.py` (stylize فريمات) | (موجود) | `import onnxruntime` | MIT |
| 107 | skia-python/skia-python | مستخدم (متوصّل بس مش متثبت) | `skia` مش متثبت. `engine/skills/library/ai-motion-graphics/scripts/flat25d_kit.py` بيرسم بيه، و`setup_env.py` بيثبّته | (موجود كوصفة) رسم 2D بـ anti-aliasing وshaders ونص مشكّل بـ HarfBuzz من غير متصفح | `pip install skia-python` | BSD-3. الريبو اتنقل من `kyamagu` |
| 108 | python-pillow/Pillow | مستخدم | `PIL` 13.0.0، وأكتر من 150 ملف كود بيستخدمه (cards و`reflock.py` و`psd.py`) | (موجود) | `from PIL import Image` | MIT-CMU (HPND) |
| 109 | tesseract-ocr/tesseract | مستخدم | `C:\Program Files\Tesseract-OCR\tesseract.exe`، و`cards/lib/fam_w3_13.py` بيشغّله بـ `-l ara`، وموجود في `machine.py` و`doctor.py` و`dragon.py` | (موجود) OCR | `tesseract in.png out -l ara` | Apache-2.0 |
| 110 | tesseract-ocr/tessdata | مستخدم | `ara.traineddata` و`eng.traineddata` موجودين في `Tesseract-OCR\tessdata` | (موجود) | | Apache-2.0. آخر push 2024، ولو الدقة قليلة جرّب `tessdata_best` للعربي |
| 111 | gl-transitions/gl-transitions | قدرة جديدة | مش موجود. ذكره في `mind/intel/repos.json` بس | أكتر من 100 transition بـ GLSL بتوقيع موحد (wipes وmorphs وglitch) لقوالب HTML-to-video، أغنى بكتير من `xfade` | `npm i gl-transitions` (كل الشيدرز في JSON واحد) مع `gl-transition` لـ WebGL، والرندر بـ Playwright | GitHub بيقول NOASSERTION: كل transition ليه رخصته (أغلبها MIT) |
| 112 | scipy/scipy | مستخدم | `scipy` 1.18.1، ومستخدم في cards كتير (`fam_w3_05.py` و`fam_light_glow_bloom.py` و`fam_transitions_cuts_a.py`) | (موجود) | `import scipy` | BSD-3 |
| 113 | csteinmetz1/pyloudnorm | متثبت ومش متوصّل | `pyloudnorm` 0.2.0 متثبت. بيتذكر في `doctor.py` و`machine.py` وقايمة `PIP_CORE` في `dragon.py` بس، وماحدش بيستدعيه | قياس LUFS وnormalize جوه Python لصوت متولّد (TTS وموسيقى) قبل ما يخش ffmpeg | `pyln.Meter(rate).integrated_loudness(data)` مع `soundfile` | MIT |
| 114 | bastibe/python-soundfile | مستخدم | `soundfile` 0.14.0، وبيتعمله import في `motion-reel/scripts/vo.py` و`music.py` | (موجود) | `import soundfile as sf` | BSD-3 |
| 115 | spotify/pedalboard | متثبت ومش متوصّل | `pedalboard` 0.9.26 متثبت. موجود في `required_tools.json` وكارت `media-image-audio.json` بس | سلسلة ماسترينج للفويس أوفر في سطرين: HighpassFilter وCompressor وEQ وLimiter وReverb، وبيستضيف VST3 | `from pedalboard import Pedalboard, Compressor, Limiter` | **GPL-3.0**. استخدامه كأداة محلية مافيهوش مشكلة، والمخرجات ملكك |
| 116 | WyattBlue/auto-editor | مستخدم | `auto-editor.exe` 29.3.1، ووصفة في `codekit.py` (line 4)، وفي `video12.py` و`capabilities.py`، و5 مهارات متنسخة في `library/auto-editor*` | (موجود) قص السكتات أوتوماتيك | `auto-editor in.mp4 --margin 0.3sec --no-open -o out.mp4` | Unlicense |
| 117 | imageio/imageio-ffmpeg | مستخدم | `imageio_ffmpeg` 0.8.1، ومستخدم في `talking-head-reels/scripts/common.py` و`motion-design/scripts/*` | (موجود) fallback لمكان ffmpeg | `imageio_ffmpeg.get_ffmpeg_exe()` | BSD-2 |
| 118 | visioncortex/vtracer | قدرة جديدة | مش متثبت ومالوش ذكر | يحوّل لوجو PNG أو اسكتش لـ SVG paths نضيفة، فتقدر تحرّكه بـ GSAP (DrawSVG وMorphSVG) أو تطلّعه 3D في Blender | `pip install vtracer` (فيه wheel لـ Windows) أو `cargo install vtracer-cli` | MIT |
| 119 | foliojs/fontkit | قدرة جديدة | مش موجود | يقرا الخط ويعمل shaping ويطلّع path لكل glyph، فتقدر تحرّك الحروف العربية حرف حرف كـ SVG وتعرف ligatures الخط | `npm i fontkit` ثم `font.layout(text)` و`glyph.path.toSVG()` | MIT. الـ shaping العربي فيه أضعف من HarfBuzz، فراجع النتيجة |
| 120 | seek-oss/capsize | قدرة جديدة | مش موجود | بيقص leading النص فيبقى الصندوق على ارتفاع الحرف بالظبط، فالمحاذاة في قوالب العناوين تبقى مظبوطة | `npm i @capsizecss/core @capsizecss/metrics` | MIT. الـ metrics فيها خطوط Google كتير، اتأكد إن خطك العربي موجود |
| 121 | LottieFiles/dotlottie-web | قدرة جديدة | مش متثبت. ذكره في مراجع `hyperframes` (`runtimes.md`) و`remotion-to-hyperframes/references/lottie.md` و`logo-animation` بس | مشغّل Lottie وملفات `.lottie` بـ WASM مع seek دقيق على الفريم وthemes | `npm i @lottiefiles/dotlottie-web` | MIT. lottie-web موجود ومستخدم بالفعل، فالإضافة بسيطة |
| 122 | dimforge/rapier | قدرة جديدة | مش متثبت. `repo_fusion/scripts/fusion/native_rapier_bake.py` كود خاص بفكرة مأخوذة من react-three-rapier (2D بس) | فيزيا 3D deterministic (أجسام وجوينتس وsnapshots) لمشاهد three.js فريم بفريم | `npm i @dimforge/rapier3d-compat` (WASM جوه ملف JS) | Apache-2.0 |
| 123 | topojson/world-atlas | مستخدم | داتا الدول مدمجة في `library/motion-globe/templates/film.html` (من `world-atlas@2.0.2`)، و`library/hyperframes/scripts/bake-basemap.mjs` بيستخدمها | (موجود) خرايط دول للجلوب والخرايط | | ISC، والداتا من Natural Earth (public domain). **الريبو archived** من 2021 |
| 124 | blader/humanizer | قدرة جديدة | مش متنسخ. ذكره في `dragon-genius/references/sources.md` وداتا `github-atlas` بس. المتنسخ `library/humanizer-zh` من `op7418/Humanizer-zh` (نسخة صيني) | مهارة تشيل علامات الكتابة بالـ AI من النص الإنجليزي | انسخ `SKILL.md` لـ `library/` | MIT. للعربي فيه humanizer في `reel_hooks` موجود |
| 125 | usebruno/bruno | قدرة جديدة | مش متثبت. ذكره في داتا `github-atlas` بس | عميل API واختبارات بملفات نص في git | `winget install Bruno.Bruno` | MIT. **مالوش علاقة بالميديا** |
| 126 | Agentchengfeng/chengfeng-videocut-skills | مستخدم | 8 مهارات متنسخة في `library/chengfeng-*` و`ian-xiaohei-svg-motion`، والريبو متنزّل في `dragon-repos\Agentchengfeng__chengfeng-videocut-skills` | (موجود) مونتاج بمهارات (قص وترجمة وexport وvisual) | حسب كل مهارة. الـ Runtime نفسه في ريبو تاني | Apache-2.0 |
| 127 | agmmnn/awesome-blender | قدرة جديدة | قايمة روابط مش كود. ذكرها في `creative-studio/SKILL.md` و`mind/intel/repos.json` بس | فهرس add-ons وأدوات AI/MCP لـ Blender تدوّر فيه لما تحتاج أداة | مافيش تثبيت، بتتقري بس | CC0-1.0 |
| 128 | alisaitteke/photoshop-mcp | مستخدم | مهارتين متنسخين (`library/photoshop-recipes` و`photoshop-remove-background`)، و`engine/tools/psd_studio/psd.py` بيشاور على فولدر الريبو. **Photoshop مش متثبت على الجهاز** | (موجود كمهارات) 118 أداة تحكم في Photoshop | محتاج Photoshop والسيرفر حسب README | MIT |
| 129 | anthropics/skills | مستخدم | 6 مهارات متنسخة (algorithmic-art وcanvas-design وfrontend-design وmcp-builder وweb-artifacts-builder وwebapp-testing)، والريبو متنزّل في `dragon-repos\anthropics__skills` | (موجود) | | مافيش رخصة على مستوى الريبو. كل مهارة ليها `LICENSE.txt`: المتنسخين Apache-2.0، و**docx وpdf وpptx وxlsx source-available (مش مفتوحين)** |
| 130 | arjun988/blender-skills | مستخدم | 9 مهارات متنسخة في `library/` (blender-director وarchviz وanimation وغيرهم) ومتسجّلة في `RD_LIBRARY.md` | (موجود) | المهارات بتفترض Blender MCP، والمهارة بتشغّل Blender headless بـ `blender-pro` بدل كده | MIT |
| 131 | auto-editor (= WyattBlue/auto-editor) | مستخدم | نفس الصف 116 بالظبط (تكرار في الكتالوج) | (موجود) | | Unlicense |
| 132 | bethington/ghidra-mcp | قدرة جديدة | Ghidra مش متثبت. ذكره في `rea-ultra/references/github-landscape.md` و`LINKS.md` بس | أكتر من 200 أداة MCP للهندسة العكسية بـ Ghidra | محتاج Ghidra وJDK 21، والبلجن حسب README | Apache-2.0. **مش ميديا**، وMCP `rea` متسجّل بالفعل |
| 133 | blender-mcp (= ahujasid/mcp-for-blender) | قدرة جديدة | الكود متنزّل في `dragon-repos\blender-mcp` بس مش متثبت: مافيش addon في `Blender 5.2` ولا MCP متسجّل. فكرة "scene info" اتنقلت بكود خاص في `native_blender_audit.py` | تحكم تفاعلي في Blender شغال قدامك من Claude | `addon.py` يتركّب في Blender، و`uvx mcp-for-blender` | MIT. 34.5k نجمة. بيكرر `blender-pro` الـ headless، فقيمته قليلة |
| 134 | charlie947/motion-graphics-skills | مستخدم | 9 مهارات متنسخة (launch-video وanimated-chart وloop-cover وmotion-effects وغيرهم) | (موجود) | | MIT |
| 135 | clearbluejar/ghidriff | قدرة جديدة | مش متثبت. ذكره في مراجع `rea-ultra` بس | diff بين نسختين من binary بـ Ghidra | `pip install ghidriff` (محتاج Ghidra وJDK) | **GPL-3.0**. مش ميديا |
| 136 | cut-as-code (= WhiteTowerAI/cut-as-code) | مستخدم | 9 مهارات متنسخة (cut-as-code وvideo-cut وvideo-add-captions وvideo-to-shorts وغيرهم)، والريبو متنزّل في `dragon-repos\cut-as-code` | (موجود) مونتاج بقرارات مكتوبة في ملفات بتتراجع | | MIT. 34 نجمة بس |
| 137 | Dakkshin/after-effects-mcp | قدرة جديدة | After Effects مش متثبت (مافيش `C:\Program Files\Adobe`). ذكره في `mind/intel` و`RD_CHATS_MEMORY.md` بس | تحكم في After Effects (comps ونص وshapes وkeyframes) من Claude | محتاج After Effects، والسيرفر بـ Node | MIT. آخر push 2026-04 |
| 138 | docsforadobe/Types-for-Adobe | قدرة جديدة | مش موجود. ذكره في `creative-studio/SKILL.md` بس | تعريفات TypeScript لـ ExtendScript (AE وPhotoshop وPremiere) عشان سكربتات أدق | `npm i -D types-for-adobe` | MIT. مالوش لازمة من غير برامج Adobe |
| 139 | ECCV2022-RIFE (= hzwer/ECCV2022-RIFE) | متثبت ومش متوصّل | `rife-ncnn-vulkan.exe` وموديلات لحد `rife-v4.6` موجودين في `dragon-tools\rife_x\rife-ncnn-vulkan-20221029-windows`، والريبو متنزّل في `dragon-repos\ECCV2022-RIFE`. في المهارة ذكره في `mind/intel` و`montage-repos-hub` بس | توليد فريمات وسطانية: 24/30 لـ 60fps، وslow-motion ناعم، وتنعيم انتقالات | `rife-ncnn-vulkan -i frames_in -o frames_out -m rife-v4.6` (Vulkan شغال على Intel Graphics) بين `ffmpeg` تقطيع وتجميع | MIT للكود، ونسخة ncnn MIT |
| 140 | EL4CTEO/blender-skills | مستخدم | 9 مهارات متنسخة (blender-core وblender-character-rigging وblender-export-pipelines وغيرهم) | (موجود) | | MIT |

## أهم 10 إضافات (حسب القيمة لشغل الفيديو والصور والموشن)

| # | الأداة | ليه | أرخص طريقة للإضافة |
|---|---|---|---|
| 1 | **RIFE (rife-ncnn-vulkan)** | 60fps وslow-motion ناعم من أي فيديو، وده مش موجود حاليًا في المهارة غير بـ `minterpolate` البطيء | **مافيش تثبيت.** الـ exe والموديلات موجودين في `dragon-tools\rife_x`. اكتب سكربت `rife_interp.py`: `ffmpeg` يقطّع فريمات، ثم `rife-ncnn-vulkan -m rife-v4.6`، ثم `ffmpeg` يجمّع بالصوت الأصلي |
| 2 | **pedalboard** | ماسترينج للفويس أوفر والـ TTS (HPF وكمبريسور وEQ وليميتر) جوه Python من غير DAW | **مافيش تثبيت** (0.9.26 موجود). سكربت `vo_master.py` بسلسلة ثابتة، وبعده بوابة `media_gate.py` |
| 3 | **pyloudnorm** | يظبط LUFS للصوت المتولّد قبل الدمج، فالمستوى يبقى ثابت بين المقاطع | **مافيش تثبيت.** خطوتين في نفس `vo_master.py`: قياس ثم `pyln.normalize.loudness(data, lufs, -16)` |
| 4 | **vtracer** | يحوّل لوجو العميل من PNG لـ SVG، فيبقى جاهز لـ DrawSVG وMorphSVG وextrude في Blender | `pip install vtracer` (wheel واحد)، ثم `vtracer.convert_image_to_svg_py(in, out)` |
| 5 | **gl-transitions** | أكتر من 100 transition بـ GLSL لقوالب HTML-to-video، أغنى من `xfade` | `npm i gl-transitions` وvendor لملف JSON الشيدرز جنب `codekit/vendor`، والرندر بنفس مسار Playwright |
| 6 | **fontkit** | يطلّع paths الحروف العربية من الخط، فتعمل أنيميشن حرف حرف وكتابة بالخط | `npm i fontkit`، وسكربت Node صغير يطلّع SVG لكل glyph |
| 7 | **shiki** | فيديوهات كود بتلوين VS Code مظبوط (typing وhighlight سطر سطر) | `npm i shiki` واستخدمه جوه قالب HTML بيترندر بـ Playwright |
| 8 | **Rapier (3D)** | فيزيا 3D deterministic لمشاهد three.js، والموجود حاليًا baker لـ 2D بس | `npm i @dimforge/rapier3d-compat` (WASM جوه JS)، وbake للمواضع فريم بفريم |
| 9 | **hyperframes-community-skills** | مهارات جاهزة فوق HyperFrames: `vox-explainer` و`camera-3d-captions` و`p5-paint-animation` | انسخ المهارات المطلوبة لـ `library/` مع `SOURCE.json` و`LICENSE` (Apache). مافيش تثبيت جديد |
| 10 | **capsize** | محاذاة عناوين مظبوطة على ارتفاع الحرف في قوالب الموشن | `npm i @capsizecss/core @capsizecss/metrics`، أو احسب القيم مرة واحدة واكتبها CSS ثابت |

### ملاحظات جانبية

- **Piper:** الباكدج متثبت ومتوصّل في `voice_studio`، بس الصوت الافتراضي `ar_JO-kareem-medium` مش متنزّل، فأول تشغيل هيفشل. وكمان الباكدج المتثبت من `piper1-gpl` ورخصته GPL-3.0، مش MIT زي الريبو القديم الـ archived.
- **Photoshop وAfter Effects:** مهارات `photoshop-mcp` متنسخة، و`after-effects-mcp` و`Types-for-Adobe` في المراجع، بس برامج Adobe مش متثبتة، فكلهم مايشتغلوش دلوقتي.
- **blender-mcp ومهارات arjun988:** بيفترضوا Blender MCP تفاعلي. المهارة بتشغّل Blender headless بـ `blender-pro`، فمافيش داعي لتركيب الـ addon.
- **hyperframes وgraphify وskia-python وplaywright-mcp:** متوصّلين كوصفات أو مهارات، بس مش متثبتين. لازم تثبيت (بموافقة) قبل أول استخدام.
- **anthropics/skills:** مهارات docx وpdf وpptx وxlsx رخصتها source-available، فماتتنسخش لـ `library/` (المتنسخ حاليًا كله Apache).
- **ghidra-mcp وghidriff وbruno وECC وclaude-agent-sdk وlenis وstyle-dictionary وhumanizer:** مالهمش علاقة مباشرة بالفيديو والموشن، أو بيكرروا حاجة موجودة (`rea`).
- **dotlottie-web:** lottie-web مستخدم بالفعل، فالإضافة صغيرة إلا لو احتجت ملفات `.lottie`.
- **تكرار في الكتالوج:** الصف 131 (`auto-editor`) هو نفس الصف 116.
