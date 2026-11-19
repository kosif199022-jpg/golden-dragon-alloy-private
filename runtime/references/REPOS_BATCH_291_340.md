# تقرير قدرات: صفوف 291 لـ 340 من الكتالوج (Batch 291-340)

- **المصدر:** صفوف البيانات 291 لـ 340 (الترقيم من 1، من غير الهيدر) في `%USERPROFILE%\Downloads\all-repos-catalog.csv`. الصفوف 291-300 مصدرها «مكتبة مهارات التنين (572 مهارة)»، والصفوف 301-340 مصدرها `links.json` (محادثات Claude Code).
- **التاريخ:** 2026-11-16.
- **الطريقة:** دوّرنا باسم الأداة أو الباكدج (مش باسم المستودع بس) جوه `golden-dragon` (engine وapps وlibrary وmind وreferences وscripts وtools)، ومنهم `library/*/SOURCE.json` و`engine/tools/repo_fusion/data/repo_fusion.json` و`engine/tools/re/re.py` و`engine/skills/montage-repos-hub/SKILL.md` و`app/golden/library.json`. وكشفنا على الجهاز بـ `where.exe` و`pip show` وبمحتوى `~/re-tools` (الصندوق اللي `re.py` و`omni.py` بيشغّلوه عن طريق `retool.py`) و`~/dragon-repos` و`~/dragon-tools/bin`. وقرينا README والرخصة والنجوم لكل مستودع بـ `gh repo view --json licenseInfo,stargazerCount,pushedAt` و`gh api repos/OWNER/REPO/license`. ماتثبّتش أي حاجة، وماعملناش clone، وماشغّلناش أي كود من المستودعات.
- **معنى الحالة:**
  - **مستخدم:** فيه كود في المهارة بيشغّله أو بيعمله vendor (منها مهارات منسوخة في `library/`) أو بيديله وصفة، أو فيه إعادة تنفيذ أصلية في `repo_fusion/scripts/fusion`، أو توجيه بمسار محدد لنسخة محلية.
  - **متثبت ومش متوصّل:** موجود على الجهاز، بس المهارة مابتستدعيهوش (ذكره في المراجع أو `doctor` بس).
  - **قدرة جديدة:** مش متثبت ولا متوصّل. لو ليه ذكر فهو في كتالوجات المراجع بس (`LINKS.md` و`links.json` و`github-landscape.md` و`RD_INTEL_REPOS.md`).

## الملخص

| الحالة | العدد |
|---|---|
| مستخدم | 38 |
| متثبت ومش متوصّل | 2 |
| قدرة جديدة | 10 |
| **الإجمالي** | **50** |

> فيه صفّين مكررين بـ commit محدد: 336 هو نفس 328 (opus-video-prompts)، و339 هو نفس 311 (pixelfx). اتحسبوا في العدد زي ما هم في الكتالوج. وكمان yt-dlp وthree.js اتغطّوا قبل كده في `REPOS_PILOT_40.md`.

## جدول الخمسين

| # | Repo | الحالة | الدليل على الجهاز وفي المهارة | الإضافة الملموسة | التشغيل على Windows | ملاحظة الرخصة |
|---|---|---|---|---|---|---|
| 291 | mattpocock/skills | مستخدم | 14 مهارة منسوخة في `library/` (`grill-me` و`to-spec` و`to-tickets` و`handoff` و`diagnosing-bugs` و`teach`...)، وكل واحدة ليها `SOURCE.json` | (موجود) مهارات هندسة: استجواب المتطلبات، وspec، وتذاكر، وhandoff | مهارات نصية، مافيش تشغيل | MIT. 325k نجمة |
| 292 | phone-harness/phone-harness | مستخدم (متوصّل بس مش متثبت) | `library/phone-harness/` منسوخة، ومتسجّل في `library/mcp_servers.json`. الأداة نفسها مش متثبتة | (موجود كمهارة) تحكم الوكيل في موبايل (adb أو iPhone Mirroring أو موبايل سحابي) | `uv tool install --python 3.12 phone-harness` ثم `phone-harness skill` | MIT. الموبايلات السحابية بفلوس |
| 293 | oil-oil/oil-ui | مستخدم | `library/oil-ui/` (SKILL.md وreferences) | (موجود) استكشاف اتجاهات تصميم UI ومقارنتها جنب بعض | مهارة نصية | MIT |
| 294 | oil-oil/oil-motion | مستخدم | `library/oil-motion/`، ومتسجّل في `app/golden/library.json` | (موجود) أنيميشن ويب بيتبع السكرول والماوس | مهارة نصية | MIT |
| 295 | alchaincyf/huashu-motion | مستخدم | `library/huashu-motion/` ومعاه `bin/om` وreferences | (موجود) أفلام دعاية منتجات بالكود مع موسيقى وتعديل بالإشارة على الفريم | `library/huashu-motion/bin/om` (راجعه قبل التشغيل) | MIT |
| 296 | caru-ini/stack-diagram | مستخدم | `library/stack-diagram/` ومعاه `scripts/fetch_icons.py` و`share.py` و`assets/template.html` | (موجود) دياجرام معمارية بلوجوهات رسمية من جملة واحدة | `python library\stack-diagram\scripts\fetch_icons.py` | MIT |
| 297 | QingYunA/answer-me-with-html | مستخدم | `library/answer-me-with-html/` ومعاه `scripts/am.mjs` | (موجود) إجابة الأسئلة الصعبة بصفحة HTML واحدة | `node library\answer-me-with-html\scripts\am.mjs` | MIT |
| 298 | DIYgod/pinky | مستخدم (متوصّل بس مش متثبت) | `library/pinky/` منسوخة، وفي `mcp_servers.json`. تطبيق Pinky نفسه مش متثبت | (موجود كمهارة) تحكم في الموبايل والإنسان في الحلقة | تطبيق desktop من الـ Releases، وبعدين Settings > Agents > Connect | Apache-2.0 |
| 299 | google/elephant-goldfish-model | مستخدم | 7 مهارات `egm-*` في `library/` (bootstrap وbrainstorm وdraft وreview وreview-loop وresolve وdrift-report) | (موجود) تصميم ومراجعة سوفتوير بوكيلين (ذاكرة طويلة وذاكرة قصيرة) | مهارات نصية | Apache-2.0 |
| 300 | Ryze-AI-Adgent/open-seo-mcp-skills | مستخدم (المهارات بس) | 5 مهارات في `library/` (seo-audit وkeyword-research وcompetitor-gap وcontent-brief وai-visibility). خادم MCP مش متثبت | (موجود) SEO وGEO: كلمات مفتاحية وتدقيق وفجوة منافسين | مهارات نصية. الـ MCP بيحتاج تثبيت منفصل | MIT |
| 301 | morluto/rea | مستخدم | `rea` متثبت من npm (`AppData\Roaming\npm\rea`)، و`re.py` بيبني خطوات `rea:*`، ومهارة `rea-ultra`، و`doctor.txt` بيقول REA 6.8.0 healthy | (موجود) هندسة عكسية لأي حاجة: exe و.NET وElectron وAPK وWASM ومواقع | `dragon.py tool re plan FILE` أو أدوات MCP `rea` | MIT. 462k نجمة |
| 302 | google/fonts | مستخدم | `higgsfield-cloud/cloud/fonts.sh` و`higgsfield-free/scripts/bootstrap.sh` بيحمّلوا خطوط OFL من `github.com/google/fonts/raw/main/ofl` | (موجود) خطوط عربي ولاتيني للكابشن والموشن | `bash fonts.sh` (على السحابة) | كل خط برخصته: OFL غالبًا، وشوية Apache/UFL |
| 303 | NationalSecurityAgency/ghidra | مستخدم | `~/re-tools/ghidra/ghidra_12.1.4_PUBLIC` و`analyzeHeadless.bat`، وهو provider بتاع REA، و`retool.py` فيه id `ghidra` | (موجود) ديكومبايل وتحليل كامل headless | `rea analyze/decompile` أو `retool run ghidra ...` | Apache-2.0 |
| 304 | yt-dlp/yt-dlp | مستخدم | `yt-dlp.exe` موجود (مغطّى في Pilot 40 صف 1) | (موجود) | `yt-dlp -f ...` | Unlicense |
| 305 | 1013503897/jadx-headless-mcp | متثبت ومش متوصّل | `~/re-tools/jadx-headless-mcp/jadx-headless-mcp-0.7.1-all.jar` موجود، بس كروت `software-investigation.json` (REA-131 وREA-134) لسه مكتوب فيها gap و«none present» | بحث في كلاسات APK وجرد الباكدجات عن طريق MCP من غير JADX GUI، ويقفل فجوتين في REA engine:android | `java -jar jadx-headless-mcp-0.7.1-all.jar` من `jdk-21` اللي في re-tools | Apache-2.0. 174 نجمة |
| 306 | iBotPeaches/Apktool | مستخدم | `~/re-tools/apktool/apktool.bat`، و`re.py` (خطة `apk`) و`omni.py` (L3) | (موجود) فك Manifest والموارد والـ smali | `retool run apktool d app.apk -o out` | Apache-2.0 |
| 307 | LaurieWired/GhidraMCP | قدرة جديدة | مش متثبت (مافيش Extensions في Ghidra)، ذكره في `rea-ultra/SKILL.md` و`RD_INTEL_REPOS.md` بس | Ghidra GUI تفاعلي يتحكم فيه الوكيل (تسمية دوال وتعليقات لايف) | إضافة Ghidra من الـ Releases + `bridge_mcp_ghidra.py` | Apache-2.0. 12k نجمة. REA بيغطي الـ headless |
| 308 | lemomo-ai/lemo-opuscar | مستخدم (إعادة تنفيذ أصلية) | `repo_fusion/scripts/fusion/native_opuscar.py` (native-implemented)، ونسخة في `dragon-repos\lemomo-ai__lemo-opuscar`، وفي `library.json` و`taste_index.json` | (موجود) تقرير إيقاع الفيلم (قطعات، سرعة، سكتات)، وفحص وقت قراية الترجمة (عربي 12 حرف/ث)، وlint لقواعد الإخراج | `python native_opuscar.py rhythm film.mp4 --json` | **مختلطة (REUSE):** الدوكس والبرومنتات CC BY-NC-4.0، والأفلام CC BY-4.0. ماننسخش نصوصها في شغل تجاري |
| 309 | Rikorose/DeepFilterNet | مستخدم | `deep-filter.exe` في `dragon-tools\bin`، ومتسجّل في `capabilities.py` و`doctor.py` و`dragon.py`، ووصفتين في `forge/recipes.py` (`program:deep-filter`) | (موجود) تنضيف الصوت من الضوضا | `deep-filter in.wav -o outdir` | MIT أو Apache-2.0 (dual) |
| 310 | mrdoob/three.js | مستخدم | vendored في codekit و`native_three.py` في repo_fusion (مغطّى في Pilot 40 صف 35) | (موجود) + ساعة افتراضية لرندر TSL/WebGPU ثابت | | MIT |
| 311 | patch-gg/pixelfx | مستخدم (إعادة تنفيذ أصلية) | `native_pixelfx.py` في repo_fusion، والمهارة `pixelfx` متثبتة في `~/.claude/skills/pixelfx` | (موجود) مؤثرات بكسل آرت فوق فيديو حقيقي (انفجار، شرار، نار)، وhit-stop وimpact frame | `python native_pixelfx.py hitstop clip.mp4 hit.mp4 --hits 2.35 --impact` | MIT |
| 312 | Vincentwei1021/video-shotcraft | مستخدم (إعادة تنفيذ أصلية) | `native_shotcraft.py` في repo_fusion، ونسخة في `dragon-repos`، وفي `library.json` | (موجود) beat grid، ومنحنى طاقة الدعاية، ومخطط مشروع CapCut/JianYing | `python native_shotcraft.py beatgrid --audio song.wav --json` | Apache-2.0. 20k نجمة |
| 313 | upx/upx | مستخدم | `~/re-tools/upx`، و`re.py` (خطة `pe-upx`: `upx -t` و`upx -d` على نسخة) و`omni.py` | (موجود) فك ضغط UPX قبل التحليل | `retool run upx -d -o unpacked.exe packed.exe` | GPL-2.0+ مع استثناء UPX |
| 314 | WerWolv/ImHex | مستخدم | `~/re-tools/imhex`، و`re.py` (runtime، بيحتاج `--yes`) | (موجود) محرر هيكس بأنماط وإنتروبي | `retool run imhex file.bin --yes` | GPL-2.0 |
| 315 | clearbluejar/ghidriff | قدرة جديدة | `pip show ghidriff` مش لاقيه، وذكره في `rea-ultra/references` بس | patch diff بين نسختين من نفس البرنامج (دوال اتضافت أو اتشالت أو اتغيّرت) بتقرير Markdown/JSON، فوق Ghidra الموجود | `pip install ghidriff` ثم `ghidriff old.exe new.exe` مع `GHIDRA_INSTALL_DIR` | GPL-3.0. 824 نجمة. REA فيه `compare_application_versions` كبديل جزئي |
| 316 | librosa/librosa | مستخدم | `librosa` 1.0.0 متثبت، ومستخدم في `engine/app/engines/audio.py`، و`native_musicmap.py` في repo_fusion | (موجود) خريطة موسيقى للمونتاج: تيمبو وبيتس وأقسام ودروب ونقط قطع | `python native_musicmap.py song.wav --json` | ISC |
| 317 | mandiant/flare-floss | مستخدم | `~/re-tools/floss/floss.exe`، وبيشتغل في `triage --deep` جوه `retool.py` و`omni.py` | (موجود) النصوص المخفية والمتشفرة | `retool run floss --no static file.exe` | Apache-2.0 |
| 318 | skylot/jadx | مستخدم | `~/re-tools/jadx/bin/jadx.bat`، و`re.py` (خطة `apk`) و`omni.py` | (موجود) Java من APK/DEX | `retool run jadx -d out app.apk` | Apache-2.0. 52k نجمة |
| 319 | JohnHeibel/ClaudeAnimationBase | مستخدم (إعادة تنفيذ أصلية) | `native_cab.py` في repo_fusion، وذكره في `ai-motion-graphics/music-video` | (موجود) lint لستوري بورد الكرتون، وفحص رعشة الخط (boil)، وفحص ثبات الرندر | `python native_cab.py reads-lint board.json --json` | MIT |
| 320 | WebAssembly/wabt | مستخدم | `~/re-tools/wabt/wabt-1.0.42`، و`re.py` (خطة `wasm`: `wasm-objdump` و`wasm2wat`) و`omni.py` | (موجود) WASM لنص مقروء | `retool run wasm2wat mod.wasm -o mod.wat` | Apache-2.0 |
| 321 | hasherezade/pe-sieve | مستخدم | `~/re-tools/pe-sieve`، و`re.py` (runtime) و`omni.py` (L2 ذاكرة) | (موجود) فحص عملية شغالة واستخراج كود محقون | `retool run pe-sieve /pid N /dir out --yes` | BSD-2 |
| 322 | mandiant/capa | مستخدم | `~/re-tools/capa/capa.exe`، وفي `triage --deep` و`re.py` و`omni.py` | (موجود) قدرات البرنامج مع ATT&CK | `retool run capa file.exe` | Apache-2.0 |
| 323 | mrexodia/ida-pro-mcp | مستخدم (المهارة بس، IDA مش متثبت) | `library/idapython/` منسوخة منه (`SOURCE.json`). `ida64` و`idat64` مش موجودين | (موجود كمهارة) سكربتات IDAPython وجسر MCP لـ IDA | بيحتاج IDA Pro (أو IDA Free 9 بقيود) + `pip install ida-pro-mcp` | MIT. 13k نجمة. IDA نفسه بفلوس |
| 324 | x64dbg/x64dbg | مستخدم | `~/re-tools/x64dbg/release/x96dbg.exe`، و`re.py` (runtime، بيحتاج `--yes`) و`brain.py` | (موجود) ديباجر ويندوز بواجهة | `retool run x64dbg --yes` | GPL-3.0 |
| 325 | PeterL1n/RobustVideoMatting | قدرة جديدة | المصدر متنسخ في `dragon-repos\PeterL1n__RobustVideoMatting` بس من غير أوزان (`.pth`/`.onnx`)، ومافيش كود في المهارة بيستدعيه، وذكره في `REPOS.md` وتحذير GPL بس | عزل الشخص من الخلفية في فيديو كامل من غير جرين سكرين (alpha ثابت بين الفريمات)، لاستبدال الخلفية والكابشن ورا الشخص | نزّل `rvm_mobilenetv3.pth` (أو ONNX)، وسكربت منفصل بـ `torch` (موجود) يطلّع alpha PNG، وبعدين `ffmpeg alphamerge` | **GPL-3.0:** يتشغّل كبرنامج منفصل، ماتدمجش كوده. آخر push 2024-04 |
| 326 | WhiteTowerAI/cut-as-code | مستخدم (توجيه لنسخة محلية) | `montage-repos-hub/SKILL.md` بيوجّه لـ `dragon-repos\cut-as-code\skills\*\SKILL.md` بالمسار، والمهارة متثبتة كمان في `~/.claude/skills/cut-as-code` | (موجود) مونتاج بقرارات محفوظة كملفات قبل الرندر: قص وترجمة وB-roll وتلوين وshorts | مهارات Claude | MIT. 34 نجمة |
| 327 | bethington/ghidra-mcp | قدرة جديدة | مش متثبت، ذكره في `github-landscape.md` و`RD_INTEL_REPOS.md` بس | أكتر من 200 أداة MCP على Ghidra (GUI أو headless) بتحميل كسول | من الـ Releases (إضافة Ghidra + سيرفر) | Apache-2.0. 6k نجمة. بيكرر جزء كبير من REA |
| 328 | joeseesun/opus-video-prompts | قدرة جديدة | مش متنسخ، و`repo_fusion.json` بيسجّله `source-linked` بس (module = None)، ودروسه متلخّصة بكلامنا في `references/repo-fusion/opus-video-prompts.md` | 18 برومنت و54 حالة فيديو بالكود (`cases.json`). الدروس نفسها اتاخدت خلاص، فالباقي قليل | قراية بس | **مافيش رخصة:** روابط ودروس بصياغتنا بس، ماننسخش نصوص |
| 329 | mandiant/capa-rules | مستخدم | `~/re-tools/capa-rules/rules-v10.0.0`، و`retool.py` بيضيفه أوتوماتيك كـ `-r` لما capa يشتغل | (موجود) قواعد capa | تلقائي مع capa | Apache-2.0 |
| 330 | mifi/lossless-cut | متثبت ومش متوصّل | `LosslessCut.exe` متثبت بـ winget، والمصدر في `dragon-repos\lossless-cut`. في المهارة ذكره في `github-atlas/atlas.py` (اسم في قاموس) وتحذير GPL في `montage-repos-hub` بس | قص من غير re-encode بواجهة، ودمج، وتقسيم بالمشاهد، وتصدير قطع كتير مرة واحدة | تطبيق واجهة من قايمة Start. المهارة ممكن توجّه ليه للشغل اليدوي | GPL-2.0: برنامج منفصل. 46k نجمة |
| 331 | tenfoldmarc/video-edit-skill | مستخدم (توجيه لنسخة محلية) | `montage-repos-hub/SKILL.md` بيوجّه لـ `dragon-repos\video-edit-skill\SKILL.md` و`WINDOWS_TEST.md` | (موجود) كليبات موبايل لريل إنستجرام جاهز | مهارة Claude (فيها scripts، راجعها قبل التشغيل) | **مافيش رخصة** على الريبو. 147 نجمة |
| 332 | yihui-dev/awesome-opus5-5-videos | مستخدم (إعادة تنفيذ أصلية) | `native_promptlib.py` و`data/opus_video_cases_index.json` في repo_fusion | (موجود) فهرس بحث لـ 703 حالة فيديو بالكود + lint للبرومنت بـ 12 قاعدة | `python native_promptlib.py search ...` | MIT. 15k نجمة |
| 333 | HexRaysSA/ida-mcp | قدرة جديدة | مش متثبت، و IDA مش موجود. ذكره في `github-landscape.md` بس | سيرفر MCP رسمي من Hex-Rays لـ IDA | بيحتاج IDA Pro 9.x | MIT للسيرفر، وIDA نفسه بفلوس |
| 334 | SamboyCoding/Cpp2IL | قدرة جديدة | مش موجود على الجهاز ومالوش ذكر في الكود | يرجّع ألعاب Unity المبنية بـ IL2CPP لـ DLLs managed تتفتح في ILSpy (الموجود في re-tools) | تحميل `Cpp2IL-Win.exe` من الـ Releases، ثم `Cpp2IL --game-path <dir> --output-as dummydll` | MIT. REA فيه `inspect_il2cpp_metadata` للميتاداتا بس |
| 335 | ahujasid/mcp-for-blender | مستخدم (إعادة تنفيذ أصلية) | `native_blender_audit.py` في repo_fusion، ونسخة في `dragon-repos\blender-mcp`. الإضافة نفسها مش متثبتة (عن قصد) | (موجود) فحص مشهد Blender headless (مقاس، ملامسة أرض، صحة mesh، textures ناقصة) + بحث Poly Haven CC0 | `blender -b scene.blend --python native_blender_audit.py` | MIT. فيه telemetry اختياري في الإضافة، ماتثبّتهاش |
| 336 | joeseesun/opus-video-prompts@7977c80 | قدرة جديدة (مكرر 328) | نفس 328، والـ commit ده هو اللي في `verified_from` | زي 328 | | زي 328 |
| 337 | lordhoell/davinci-resolve-mcp | قدرة جديدة | مش متثبت، وDaVinci Resolve نفسه مش متثبت (مافيش `Blackmagic Design` في Program Files). ذكره في `LINKS.md` و`RD_CHATS_MEMORY.md` بس | أكتر من 440 أداة على Resolve scripting API: تايملاين وتلوين وFairlight ورندر | ثبّت Resolve (المجاني) + `pip` للسيرفر حسب الـ README | MIT. 27 نجمة بس، وآخر push 2026-04. Resolve المجاني بيدعم السكربتات من جوه بس |
| 338 | mrexodia/mcp-reversing-dataset | قدرة جديدة | مش موجود، ذكره في `sources-github.txt` بس | داتا مهام هندسة عكسية اتعملت بـ LLM، تنفع كـ eval لـ REA و`rea-ultra` | `gh repo view` وقراية بس | **مافيش رخصة.** 85 نجمة، آخر push 2025-04 |
| 339 | patch-gg/pixelfx@044e12a | مستخدم (مكرر 311) | نفس 311، والـ commit ده هو اللي في `verified_from` | زي 311 | | MIT |
| 340 | pmndrs/react-three-rapier | مستخدم (إعادة تنفيذ أصلية) | `native_rapier_bake.py` في repo_fusion | (موجود) فيزيا أجسام صلبة 2D بخطوة ثابتة 120Hz تطلّع transforms لكل فريم وأرقام فريمات التصادم للمؤثرات الصوتية | `python native_rapier_bake.py ...` | MIT |

## أهم 10 إضافات (حسب القيمة لشغل الفيديو والصور والموشن، وبعدها الهندسة العكسية)

| # | الأداة | ليه | أرخص طريقة للإضافة |
|---|---|---|---|
| 1 | **RobustVideoMatting** | عزل الشخص من الخلفية في فيديو كامل من غير جرين سكرين، وبيكمّل SAM 2 (SAM للعناصر، RVM للناس بسرعة) | **المصدر موجود** في `dragon-repos`. نزّل `rvm_mobilenetv3.pth` بس، واكتب سكربت منفصل `rvm_matte.py` (torch موجود) يطلّع alpha، و`ffmpeg alphamerge`. يفضل برنامج منفصل بسبب GPL-3 |
| 2 | **LosslessCut** | قص ودمج وتقسيم من غير re-encode بواجهة، للمستخدم لما يحب يقص بإيده | **مافيش تثبيت** (winget موجود). ضيف سطر في `montage-repos-hub` يوجّه ليه للشغل اليدوي، وسيب القص الآلي لـ ffmpeg |
| 3 | **jadx-headless-mcp** | يقفل فجوتين مكتوبين في كروت REA (REA-131 وREA-134) لتحليل APK من غير GUI | **مافيش تحميل.** الـ JAR و JDK 21 موجودين في `re-tools`. سجّله في `retool.py` و`re.py` (خطة `apk`)، وحدّث الكروت من gap |
| 4 | **ghidriff** | patch diff بين نسختين بأمر واحد وتقرير Markdown، فوق Ghidra المتثبت | `pip install ghidriff` في venv منفصل، و`GHIDRA_INSTALL_DIR` على `re-tools\ghidra\ghidra_12.1.4_PUBLIC` |
| 5 | **Cpp2IL** | يفتح ألعاب Unity (IL2CPP) لـ DLLs تتقري في ILSpy الموجود | exe واحد من الـ Releases في `re-tools\cpp2il`، وid جديد في `retool.py` |
| 6 | **bethington/ghidra-mcp** | تحكم تفاعلي في Ghidra GUI (تسمية وتعليقات لايف) لما REA headless مايكفيش | إضافة Ghidra + السيرفر من الـ Releases، وبس عند الحاجة لجلسة تفاعلية |
| 7 | **davinci-resolve-mcp** | تلوين ومونتاج وFairlight من Resolve بالأوامر | بيحتاج تثبيت Resolve المجاني الأول، والمشروع لسه صغير (27 نجمة)، فجرّبه على مشروع تجريبي بس |
| 8 | **LaurieWired/GhidraMCP** | نفس فكرة 6 بأدوات أقل وأشهر (12k نجمة) | إضافة واحدة + `bridge_mcp_ghidra.py`. اختار واحد بس من 6 و8 |
| 9 | **mcp-reversing-dataset** | مهام حقيقية تتقاس عليها `rea-ultra` (eval) | قراية بس بـ `gh api`، مافيش رخصة فماننسخش محتواه |
| 10 | **HexRaysSA/ida-mcp** | السيرفر الرسمي لـ IDA لو اتشترى IDA | استناه لحد ما يبقى فيه IDA Pro. لحد دلوقتي Ghidra وREA بيغطّوا |

### ملاحظات جانبية

- **مهارات المكتبة (291-300 و323):** كلها منسوخة من غير تعديل، و`SOURCE.json` بيقول إنها مرجع لحد ما المالك يقرر يستخدمها. phone-harness وpinky وopen-seo وida-pro-mcp متوصّلين كمهارات بس، والأدوات أو السيرفرات نفسها مش متثبتة.
- **repo_fusion:** المستودعات 308 و311 و312 و316 و319 و332 و335 و340 (وthree.js) اتحلّلوا بـ REA واتعاد تنفيذ أهم قدراتهم بكود أصلي في `engine/tools/repo_fusion/scripts/fusion/`، وكود المصدر نفسه ماتنسخش.
- **lemo-opuscar:** الرخصة مختلطة. الدوكس والبرومنتات CC BY-NC-4.0 (ممنوع تجاري)، فماتنسخش نصوص STYLE.md في شغل لعميل.
- **GPL:** RobustVideoMatting (GPL-3) وLosslessCut (GPL-2) وghidriff (GPL-3) وx64dbg (GPL-3) وImHex (GPL-2) تفضل برامج منفصلة، ماتدمجش كودها.
- **مافيش رخصة:** opus-video-prompts وvideo-edit-skill وmcp-reversing-dataset. نستخدم أفكار ودروس بصياغتنا بس.
- **المكرر:** 336 = 328، و339 = 311، و304 (yt-dlp) و310 (three.js) اتغطوا في Pilot 40.
