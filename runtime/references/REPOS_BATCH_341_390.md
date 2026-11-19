# تقرير قدرات: صفوف 341 لـ 390 من الكتالوج (Batch 341-390)

- **المصدر:** صفوف البيانات من 341 لـ 390 (العد بيبدأ من 1 من غير الهيدر) في `%USERPROFILE%\Downloads\all-repos-catalog.csv`. كلهم مصدرهم `links.json` (محادثات Claude Code على الجهاز). الصف 342 والصف 390 هما نفس الريبو (`yihui-dev/awesome-opus5-5-videos`) بـ commit مختلف.
- **التاريخ:** 2026-11-16.
- **الطريقة:** دوّرنا باسم الأداة أو الباكدج (مش باسم المستودع بس) جوه `golden-dragon` (scripts وengine وmind وreferences وmodules وapps وlibrary)، وفصلنا ملفات الكود (`.py` و`.js` و`.ps1`) عن ملفات الكتالوج (`links.json` و`LINKS.md` و`sources-*.txt`). وراجعنا سجل أدوات الهندسة العكسية `%USERPROFILE%\re-tools\retool.py` اللي `engine/tools/re/re.py` بيشغّله، والـ clones في `%USERPROFILE%\dragon-repos`، والـ MCP servers المتسجّلة في `~/.claude.json` (`rea` و`black-dragon` بس). وكشفنا على الجهاز بـ `where.exe` و`python -c "import X"` وبالـ venvs اللي جوه `re-tools` وبمجلد إضافات Blender 5.2 (فاضي). وقرينا README والرخصة والنجوم لكل مستودع بـ `gh api repos/OWNER/REPO` و`gh api repos/OWNER/REPO/readme`. ماتثبّتش أي حاجة وماعملناش clone وماشغّلناش كود أي ريبو.
- **معنى الحالة:**
  - **مستخدم:** فيه كود في المهارة بيشغّله أو بيعمله vendor أو بيديله وصفة تثبيت، أو نقل فكرته بكود خاص بينا (native port).
  - **متثبت ومش متوصّل:** موجود على الجهاز، بس ماحدش في المهارة بيستدعيه.
  - **قدرة جديدة:** مش متثبت ولا متوصّل. لو ليه ذكر فهو في كتالوجات المراجع بس (`links.json` و`LINKS.md` ومراجع `rea-ultra`).

## الملخص

| الحالة | العدد |
|---|---|
| مستخدم | 20 |
| متثبت ومش متوصّل | 2 |
| قدرة جديدة | 28 |
| **الإجمالي** | **50** |

## جدول الخمسين

| # | Repo | الحالة | الدليل على الجهاز وفي المهارة | الإضافة الملموسة | التشغيل على Windows | ملاحظة الرخصة |
|---|---|---|---|---|---|---|
| 341 | tooflex/davinci-resolve-mcp | قدرة جديدة | DaVinci Resolve مش متثبت، والريبو مذكور في `links.json` و`kosif-black-dragon-ultra/TOOLS.md` بس | MCP يتحكم في Resolve (تايملاين، ميديا، رندر، تلوين) من Claude | بيحتاج **Resolve Studio 18+** (مدفوع) مع تفعيل External scripting، وCPython 3.10 أو 3.11 (مش 3.12) | **مافيش رخصة** (all rights reserved)، و22 نجمة بس |
| 342 | yihui-dev/awesome-opus5-5-videos@92aee2f5 | مستخدم | فهرس متحوّل لـ `engine/tools/repo_fusion/data/opus_video_cases_index.json`، وبيقراه `native_promptlib.py` | (موجود) فهرس حالات فيديو اتعملت بـ Opus 5.5 بالتصنيف والتاجات، لاختيار مرجع لأي فكرة | `python -I native_promptlib.py ...` | MIT للفهرس. نصوص البرومبتات ملك أصحابها ومش متخزنة عندنا |
| 343 | zinja-coder/apktool-mcp-server | قدرة جديدة | مش متثبت. Apktool نفسه موجود (`re-tools\apktool\apktool.bat`) ومتوصّل في `re.py`، والـ MCP مذكور في `mind/intel/repos.json` و`rea-ultra/references/github-landscape.md` بس | أدوات MCP لفك APK وتعديل smali وإعادة البناء من المحادثة | Python + `uv` جنب apktool الموجود | Apache-2.0. قيمته قليلة لأن `re.py run apktool` بيغطيه |
| 344 | zinja-coder/jadx-mcp-server | قدرة جديدة | مش متثبت. JADX موجود ومتوصّل، والموجود في `re-tools` هو `jadx-headless-mcp-0.7.1-all.jar` (مشروع تاني) ومش متسجّل في `~/.claude.json` | MCP يسأل JADX عن الكلاسات والميثودز والـ xrefs | `uv` + plugin `jadx-ai-mcp` جوه JADX (لازم الاتنين مع بعض) | Apache-2.0 |
| 345 | AssetRipper/AssetRipper | قدرة جديدة | مش موجود، ومذكور في `rea-ultra/references/mobile-web-methodology.md` بس | يطلّع موديلات وخامات وصوت ومشاهد من ألعاب Unity لمشروع قابل للفتح (موديلات FBX/GLB تروح Blender) | إصدار Windows جاهز (GUI بواجهة ويب محلية) | GPL-3.0. الأصول المستخرجة ملك أصحاب اللعبة |
| 346 | Impact-I/reFlutter | قدرة جديدة | مش موجود، ومذكور في مراجع `rea-ultra` بس. REA فيه `identify_flutter_build` و`inspect_dart_aot` | يعيد بناء `libflutter.so` بحيث ترافيك تطبيق Flutter يعدّي على البروكسي، ويطبع offsets الدوال | `pip install reflutter` ثم `reflutter app.apk`، وبعدها توقيع وتثبيت على جهاز | GPL-3.0 |
| 347 | MobSF/Mobile-Security-Framework-MobSF | قدرة جديدة | مش موجود، ومذكور في مراجع `rea-ultra` بس | فحص أمني شامل لـ APK/IPA (static وdynamic) بتقرير جاهز | Docker هو الأسهل: `docker run -p 8000:8000 opensecurity/mobile-security-framework-mobsf` | GPL-3.0. تقيل، وأغلب أجزاءه الـ static عندنا بـ jadx وapktool وandroguard |
| 348 | OWASP/owasp-mastg | قدرة جديدة | مذكور في `rea-ultra/references/sources-mobile-web.txt` بس | دليل منهجية اختبار تطبيقات الموبايل بخطوات وأدوات لكل نقطة ضعف (MASWE) | مستند، يتقرا أونلاين | CC-BY-SA-4.0 |
| 349 | OWASP/owasp-masvs | قدرة جديدة | مذكور في `sources-mobile-web.txt` بس | قايمة متطلبات أمان الموبايل المعيارية، تنفع checklist لتقرير | مستند | CC-BY-SA-4.0. MASTG بيغطيه وبيزيد عليه |
| 350 | OWASP/wstg | قدرة جديدة | مذكور في `sources-mobile-web.txt` بس | دليل اختبار أمان تطبيقات الويب | مستند | CC-BY-SA-4.0. بعيد عن شغل الميديا |
| 351 | P1sec/hermes-dec | قدرة جديدة | مش موجود، ومذكور في مراجع `rea-ultra` بس | يفك ويعمل decompile لبايت كود Hermes في تطبيقات React Native (`index.android.bundle`)، وده مش موجود حاليًا | `uv tool install hermes-dec` أو `pipx install hermes-dec` (stdlib بس) | **AGPL-3.0** (استخدام كأداة تمام، بس ماتدمجش الكود) |
| 352 | Perfare/Il2CppDumper | قدرة جديدة | مش موجود. REA فيه `inspect_il2cpp_metadata` | يطلّع أسماء الكلاسات والدوال من `global-metadata.dat` ويديها لـ Ghidra/IDA بسكربت | exe لـ .NET على Windows | MIT. آخر push كان 2024-08 |
| 353 | Poly-Haven/Poly-Haven-Asset-Browser | قدرة جديدة | **الريبو بيرجّع 404** (اتشال أو بقى خاص). المهارة بتستخدم Poly Haven API مباشرة في `engine/tools/media_hunter/mh.py` (`s_polyhaven`) | (القيمة موجودة بالـ API) تصفّح أصول Poly Haven جوه Blender | مش متاح | مش معروفة. أصول Poly Haven نفسها CC0 |
| 354 | Vincentwei1021/video-shotcraft@3ac67b75 | مستخدم | منقول بكود خاص في `engine/tools/repo_fusion/scripts/fusion/native_shotcraft.py` (energy arc وbeat grid وav-offset وخطة JianYing)، والـ clone موجود في `dragon-repos` | (موجود) تزامن القطع مع البيت وقياس تأخير الصوت | `python -I native_shotcraft.py beatgrid ...` | Apache-2.0 |
| 355 | adoptium/temurin21-binaries | مستخدم (بشكل غير مباشر) | `re-tools\jdk\jdk-21.0.13+9` (Temurin)، و`retool.py` بيضبط `JAVA_HOME` عليه لـ jadx وapktool وGhidra | (موجود) Java اللي أدوات الهندسة العكسية محتاجاها | تلقائي من retool | GPLv2 + Classpath Exception (مافيش رخصة متسجّلة على الريبو نفسه) |
| 356 | ahujasid/mcp-for-blender@2e4b0bc2 | متثبت ومش متوصّل | الـ clone موجود في `dragon-repos\blender-mcp`، بس الـ addon مش متركّب في Blender 5.2 (مجلد extensions فاضي) ومش متسجّل كـ MCP. المهارة بتشغّل Blender headless بـ `blender-pro/runner.py` | تحكم حي في Blender مفتوح، واستيراد أصول من Poly Haven وSketchfab وPoly Pizza وموديلات AI (Hyper3D وHunyuan3D) | ركّب `addon.py` في Blender، وضيف MCP بـ `uvx blender-mcp` | MIT (34.5k نجمة). خدمات توليد الموديلات ليها شروطها |
| 357 | androguard/androguard | مستخدم | `re-tools\pylibs\venv` فيه androguard، ومتسجّل في `retool.py`، و`re.py` بيقترحه لملفات APK | (موجود) تحليل APK/DEX من Python | `retool.py run androguard axml app.apk` | Apache-2.0 |
| 358 | anthropics/anthropic-sdk-python | مستخدم | `anthropic` 2.6.0 متثبت، و`apps/golden-dragon/app/app.py` بيعمل `anthropic.Anthropic(...)` | (موجود) | `import anthropic` | Apache-2.0 |
| 359 | bongtrop/hbctool | قدرة جديدة | مش موجود، ومذكور في مراجع `rea-ultra` بس | تفكيك وإعادة تجميع بايت كود Hermes (patch) | `pip install hbctool` | MIT. **آخر push كان 2023-12** ونسخ HBC الجديدة مش مدعومة، وhermes-dec أحدث |
| 360 | danielgatis/rembg | مستخدم | `rembg.exe` و2.0.87، ومستخدم في `chroma_identity.py` (ومتغطي في Pilot 40) | (موجود) | `rembg i in.png out.png` | MIT. موديل BRIA RMBG رخصته غير تجارية |
| 361 | dnSpyEx/dnSpy | قدرة جديدة | مش موجود. ILSpy موجود وx64dbg موجود | debugging لتطبيقات .NET وتعديل IL مباشرة (ILSpy بيقرا بس) | zip جاهز لـ Windows (GUI) | GPL-3.0. GUI بس، فمش مناسب للتشغيل الآلي |
| 362 | fosdickio/binary_ninja_mcp | قدرة جديدة | Binary Ninja مش متثبت | MCP لـ Binary Ninja | Plugin Manager جوه Binary Ninja | GPL-3.0. **بيحتاج رخصة Binary Ninja مدفوعة**، وGhidra وrizin وREA بيغطّوه |
| 363 | frida/frida | مستخدم | `re-tools\frida\venv` فيه frida 17.26.2، ومتسجّل في `retool.py` كأداة runtime، و`re.py` بيطلب `--yes` قبل تشغيله | (موجود) hooks وقت التشغيل | `retool.py run frida-ps` | wxWindows Library Licence (متسجّلة NOASSERTION) |
| 364 | frida/frida-tools | مستخدم | frida-tools 14.13.0 في نفس الـ venv (هي اللي بتدّي `frida.exe` و`frida-ps.exe` و`frida-trace.exe`) | (موجود) | `retool.py run frida-trace -i "recv*" -p PID` | wxWindows Library Licence |
| 365 | google/bindiff | قدرة جديدة | مش موجود. REA فيه `compare_functions` و`match_native_functions` | مقارنة نسختين من نفس البرنامج دالة بدالة (patch diffing) | msi لـ Windows + BinExport لـ Ghidra | Apache-2.0. تقيل وREA بيغطي أغلبه |
| 366 | icsharpcode/ILSpy | مستخدم | `re-tools\ilspycmd\ilspycmd.cmd` و`re-tools\ilspy`، ومستخدم في `re.py` و`rea_ultra/bridge.py` | (موجود) كود C# من ملفات .NET | `retool.py run ilspy app.dll` | MIT |
| 367 | j4k0xb/webcrack | مستخدم | `re-tools\webcrack\node_modules\webcrack` (^2.15.1)، ومستخدم في `re.py` لملفات JS وElectron وasar | (موجود) فك تشويش JS وتفكيك bundles | `retool.py run webcrack in.js` | MIT |
| 368 | jakev/pyxamstore | قدرة جديدة | مش موجود | يفك ملفات `assemblies.blob` في تطبيقات Xamarin عشان ILSpy يقراها | `python setup.py install` | **مافيش رخصة**، وآخر push كان 2024-05. حالة نادرة |
| 369 | mozilla/source-map | قدرة جديدة | مش متثبت (الموجود `convert-source-map` بس كاعتمادية). REA فيه `recover_javascript_sources` | قراية `.map` ورجوع المصادر الأصلية لكود JS متصغّر | `npm i source-map` | BSD-3 (متسجّلة NOASSERTION). REA بيغطيه |
| 370 | mrdoob/three.js@3f7edc3d | مستخدم | vendored في `codekit/vendor/three` و`cartoon/vendor/three.module.js` (متغطي في Pilot 40) | (موجود) | | MIT |
| 371 | nabla-c0d3/sslyze | قدرة جديدة | مش موجود | فحص إعدادات TLS لسيرفر | `pip install sslyze` | **AGPL-3.0**. بعيد عن شغل الميديا |
| 372 | nesrak1/UABEA | قدرة جديدة | مش موجود | تعديل وتصدير أصول Unity (textures وmeshes وTextAsset) جوه bundles | exe لـ Windows (GUI) | MIT. AssetRipper بيغطي الاستخراج بشكل أشمل |
| 373 | rizinorg/cutter | قدرة جديدة | مش موجود. rizin نفسه موجود ومتوصّل | واجهة رسومية لـ rizin (graph view وdecompiler) | zip أو installer لـ Windows | GPL-3.0. GUI، فقيمته للوكيل قليلة |
| 374 | sensepost/objection | قدرة جديدة | مش موجود (مش في venv الـ frida ولا في `retool.py`) | أوامر جاهزة فوق Frida: تعطيل SSL pinning وكشف الروت، واستكشاف الملفات والـ keychain وقت التشغيل | `pip install objection` في نفس venv الـ frida، ومحتاج جهاز أندرويد أو emulator | GPL-3.0 |
| 375 | sketchfab/blender-plugin | قدرة جديدة | مش متركّب في Blender. `media_hunter_615/mh.py` بيدوّر في Sketchfab API (`s_sketchfab`) بس مابينزّلش | تنزيل موديلات Sketchfab القابلة للتحميل جوه Blender بالخامات | zip addon في Blender، ومحتاج حساب وتوكن Sketchfab | Apache-2.0. كل موديل ليه رخصته (CC-BY وغيرها) |
| 376 | testssl/testssl.sh | قدرة جديدة | مش موجود | فحص TLS من الترمنال | سكربت bash، على Windows عن طريق Git Bash أو WSL أو Docker | GPL-2.0. بعيد عن شغل الميديا |
| 377 | trailofbits/skills | مستخدم | مهاراتهم موجودة vendored في `golden-dragon/library` (`solana-vulnerability-scanner` و`secure-workflow-guide` و`audit-context-building` وغيرهم) | (موجود) مهارات مراجعة أمنية | كمهارات | CC-BY-SA-4.0 |
| 378 | worawit/blutter | قدرة جديدة | مش موجود. REA فيه `inspect_dart_aot` | يرجّع أسماء دوال وكلاسات Dart من `libapp.so` في تطبيقات Flutter (release) | بيتبني على Windows بـ Visual Studio (C++20) + capstone وicu، وبيحمّل SDK Dart المطابق | MIT. البناء تقيل |
| 379 | wtsxDev/reverse-engineering | قدرة جديدة | مذكور في `mind/intel/repos.json` و`RD_INTEL_REPOS.md` بس | قايمة awesome لأدوات وكتب الهندسة العكسية | مستند | **مافيش رخصة**، وآخر push كان 2023-07 |
| 380 | zinja-coder/jadx-ai-mcp | قدرة جديدة | مش متثبت، ومذكور في `github-landscape.md` وفي محادثة في `mind/chats` | plugin جوه JADX يفتح الكود للوكيل (الكلاس المختار والـ xrefs والـ manifest) | `jadx plugins --install "github:zinja-coder:jadx-ai-mcp"` + `jadx-mcp-server` بـ `uv` | Apache-2.0 |
| 381 | JohnHeibel/ClaudeAnimationBase@0ac8bf2b | مستخدم | منقول بكود خاص في `engine/tools/repo_fusion/scripts/fusion/native_cab.py` (`reads-lint` للستوريبورد و`boil-audit` لرعشة الخط) | (موجود) فحص توقيت القراءة في الستوريبورد وثبات الـ boil في الكرتون المرسوم | `python -I native_cab.py boil-audit FRAMES_DIR` | MIT |
| 382 | VirusTotal/yara | مستخدم | `re-tools\yara\yara64.exe` و`yarac64.exe`، ومتسجّل في `retool.py` كـ `yara`. الفرز التلقائي في `re.py` بيستخدم yara-x | (موجود) قواعد أنماط | `retool.py run yara rules.yar file` | BSD-3 |
| 383 | harry0703/MoneyPrinterTurbo | مستخدم (متوصّل بس مش متثبت) | الـ clone موجود في `dragon-repos\MoneyPrinterTurbo` من غير venv، ومهارة `library/moneyprinterturbo-video` بتديله وصفة تثبيت وتشغيل بـ `uv`، و`media_gate.py` واخد منه قواعد | (موجود كوصفة) فيديو قصير كامل من موضوع (سكربت وصوت ولقطات stock وترجمة) | `uv sync` ثم `uv run python main.py` أو WebUI | MIT. محتاج مفاتيح LLM وPexels/Pixabay |
| 384 | letmaik/rawpy | متثبت ومش متوصّل | `rawpy` 0.28.0 متثبت، ومذكور في `modules/ultra/tools.json` و`links.json` بس، ومافيش كود بيعمله import | يفك صور RAW (CR2 وNEF وARW وDNG) لـ 16-bit مع تحكم في white balance والـ demosaic والجاما، قبل التلوين أو التكبير | `rawpy.imread(p).postprocess(output_bps=16)` | MIT (LibRaw نفسها LGPL-2.1 أو CDDL) |
| 385 | librosa/librosa@9fd51bee | مستخدم | `librosa` 1.0.0، ومستخدم في `engines/audio.py` و`dragon_montage/analyze.py` و`native_shotcraft.py` | (موجود) تحليل البيت والطاقة | `import librosa` | ISC |
| 386 | pmndrs/react-three-rapier@ae5c3fed | مستخدم | منقول بكود خاص في `engine/tools/repo_fusion/scripts/fusion/native_rapier_bake.py` (fixed timestep وinterpolation وأحداث التصادم على ساعة الفريم) | (موجود) فيزيا 2D محددة تطلع نفس النتيجة في كل رندر | `python native_rapier_bake.py bake ...` | MIT |
| 387 | rizinorg/rizin | مستخدم | `rizin.exe` و`rz-bin.exe` في `re-tools\rizin`، ومستخدمين في `re.py` لملفات PE وELF وMach-O | (موجود) | `retool.py run rz-bin -I file` | LGPL-3.0 |
| 388 | tesseract-ocr/tessdata_best | قدرة جديدة | مش موجود. الموجود في `C:\Program Files\Tesseract-OCR\tessdata\ara.traineddata` حجمه 1,432,056 بايت، وده بالظبط حجم نسخة fast. نسخة best (12,603,724 بايت) متذكرة كتوصية بس | OCR عربي أدق للترجمات المحروقة والفريمات | نزّل `ara.traineddata` من tessdata_best في مجلد منفصل، وشغّل `tesseract img out -l ara --tessdata-dir DIR` | Apache-2.0. آخر push كان 2024 (الموديلات ثابتة) |
| 389 | tesseract-ocr/tessdata_fast | مستخدم | `ara.traineddata` المتثبت حجمه مطابق لنسخة fast، وtesseract بيتنادى في `cards/lib/fam_w3_13.py` و`doctor.py` | (موجود) | `tesseract img out -l ara` | Apache-2.0 |
| 390 | yihui-dev/awesome-opus5-5-videos@92aee2f | مستخدم | تكرار للصف 342 (نفس الريبو، والـ commit مكتوب مختصر). ده نفس الـ pin اللي في `opus_video_cases_index.json` | (موجود) | | MIT |

## أهم 10 إضافات (حسب القيمة لشغل الفيديو والصور والموشن، وبعدها سد ثغرات الهندسة العكسية)

| # | الأداة | ليه | أرخص طريقة للإضافة |
|---|---|---|---|
| 1 | **rawpy** | صور RAW من الكاميرات بتتفك 16-bit بتحكم كامل قبل التلوين أو التكبير، بدل JPEG مضغوط | **مافيش تثبيت** (0.28.0 موجود). سكربت صغير `raw_develop.py` يطلّع TIFF 16-bit، ويتسجّل في كتالوج الصور |
| 2 | **tessdata_best (ara)** | OCR عربي أدق بشكل واضح للترجمات المحروقة واللافتات من نسخة fast الموجودة | ملف واحد (12.6MB) في مجلد منفصل، وتمرير `--tessdata-dir` بس لما الدقة تهم. من غير ما نلمس نسخة fast |
| 3 | **blender-mcp** | استيراد أصول من Poly Haven وSketchfab وPoly Pizza وموديلات AI لـ Blender مفتوح، وده مش موجود في مسار headless | **مافيش clone.** الكود في `dragon-repos\blender-mcp`. ركّب `addon.py` في Blender 5.2 وسجّل `uvx blender-mcp` كـ MCP بعد موافقة المستخدم |
| 4 | **AssetRipper** | يطلّع موديلات وخامات وصوت من ألعاب Unity (لملفات المستخدم أو المسموح بيها) ويوديهم Blender | إصدار Windows جاهز، ويتسجّل في `retool.py` كأداة جديدة |
| 5 | **Sketchfab blender-plugin** | `mh.py` بيلاقي موديلات Sketchfab بس مابينزّلهاش. الـ plugin بيكمّل السكة لحد الاستيراد بالخامات | zip addon + توكن Sketchfab من المستخدم. أو يتغطّى من خلال blender-mcp (رقم 3) |
| 6 | **hermes-dec** | تطبيقات React Native (Hermes) مالهاش decompiler عندنا خالص | `uv tool install hermes-dec` (stdlib بس)، ويتسجّل في `retool.py` ويتربط بنوع `apk` في `re.py` |
| 7 | **jadx-ai-mcp (مع jadx-mcp-server)** | الوكيل يسأل JADX مباشرة عن الكلاسات والـ xrefs بدل ما يقرا مخرجات decompile كاملة | `jadx plugins --install "github:zinja-coder:jadx-ai-mcp"` على JADX الموجود، و`jadx-mcp-server` بـ `uv` |
| 8 | **objection** | تعطيل SSL pinning واستكشاف تطبيق أندرويد وهو شغال بأوامر جاهزة فوق Frida الموجود | `pip install objection` جوه `re-tools\frida\venv`، ويتسجّل كأداة runtime محتاجة `--yes` |
| 9 | **reFlutter** | ترافيك تطبيقات Flutter مابيعدّيش على البروكسي من غير patch، وREA بيعرّف الـ build بس | `pip install reflutter` في venv منفصل. blutter أقوى في الأسماء بس بناءه تقيل |
| 10 | **OWASP MASTG** | منهجية جاهزة خطوة بخطوة لتقارير الموبايل في `rea-ultra` | مافيش تثبيت. يتربط كمرجع بروابط لأقسام MASWE جوه `mobile-web-methodology.md` |

### ملاحظات جانبية

- **الصفين 342 و390:** نفس الريبو بـ commit مكتوب بشكلين (كامل ومختصر). اتعدّوا مرتين في الإجمالي عشان العد يفضل مطابق للكتالوج.
- **Poly-Haven-Asset-Browser:** الريبو بيرجّع 404. Poly Haven API متوصّل أصلًا في `media_hunter`، فمافيش حاجة ضايعة.
- **davinci-resolve-mcp:** محتاج Resolve Studio المدفوع وPython 3.10 أو 3.11، ومالوش رخصة، وعليه 22 نجمة بس، فمش في التوب 10.
- **binary_ninja_mcp:** محتاج رخصة Binary Ninja مدفوعة، وGhidra وrizin وREA بيغطّوه.
- **sslyze وtestssl.sh وOWASP WSTG:** فحص أمان ويب وTLS، بعيد عن الميديا وعن RE الملفات. sslyze رخصته AGPL.
- **hbctool:** متوقف من 2023 ونسخ Hermes الجديدة مش مدعومة. hermes-dec بديله.
- **dnSpy وCutter وUABEA:** أدوات GUI، فقيمتها للوكيل قليلة. ILSpy وrizin وAssetRipper بيغطّوا الجزء اللي ينفع يتشغّل آليًا.
- **Il2CppDumper وbindiff وsource-map:** REA بيغطّيهم (`inspect_il2cpp_metadata` و`compare_functions` و`recover_javascript_sources`).
- **MobSF:** مفيد كتقرير شامل بس تقيل (Docker)، والجزء الـ static عندنا بـ jadx وapktool وandroguard.
- **YARA:** الكلاسيكي متسجّل في `retool.py`، بس الفرز التلقائي في `re.py` بيستخدم yara-x. الاتنين موجودين.
