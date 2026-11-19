# تقرير قدرات: صفوف 141 لـ 190 من الكتالوج (Batch 141-190)

- **المصدر:** صفوف البيانات من 141 لـ 190 (العد من 1 ومن غير الهيدر) في `%USERPROFILE%\Downloads\all-repos-catalog.csv`. كلهم من مصدر «التنين intel (اتحمل واتفحص، 66)».
- **التاريخ:** 2026-11-16.
- **الطريقة:** نفس طريقة `REPOS_PILOT_40.md`. دوّرنا باسم الأداة أو الباكدج جوه `golden-dragon` كلها (scripts وengine وmind وreferences وmodules وlibrary وapps) واستبعدنا الكتالوجات. وراجعنا `library/*/SOURCE.json` عشان نعرف المهارات اللي اتعملها vendor من كل مستودع. وكشفنا على الجهاز بـ `where.exe` و`importlib.util.find_spec` و`npm ls -g`، وبصّينا على `%USERPROFILE%\re-tools` و`%USERPROFILE%\dragon-repos`. وجبنا الرخصة والنجوم وآخر push بـ `gh repo view` و`gh api repos/OWNER/REPO/license`. ماتثبّتش أي حاجة، وماعملناش clone، وماشغّلناش كود أي مستودع.
- **أسماء ناقصة في الكتالوج:** 11 صف مكتوب فيهم اسم الفولدر بس. جبنا المالك من `git remote` بتاع النسخة المحلية: `heygen-com/hyperframes` و`mifi/lossless-cut` و`KyaniteLabs/mcp-video` (اسمه بقى `KyaniteLabs/kinocut`) و`harry0703/MoneyPrinterTurbo` و`veedstudio/open-edit` و`facebookresearch/sam2` و`snakers4/silero-vad` و`remotion-dev/skills` و`tenfoldmarc/video-edit-skill` و`browser-use/video-use` و`m-bain/whisperX`.
- **معنى الحالة:**
  - **مستخدم:** فيه كود في المهارة بيشغّله، أو بيعمله vendor (مهارة منسوخة في `library/` أو `engine/skills/`، أو port مكتوب بكودنا)، أو بيديله وصفة تثبيت (codekit).
  - **متثبت ومش متوصّل:** موجود على الجهاز وينفع يتقرا أو يشتغل من غير تثبيت، بس ماحدش في المهارة بيستدعيه. ذكره في كتالوجات بس (`mind/intel/repos.json` و`SKILL_ATLAS.md` و`fusion/index.json` و`MONTAGE_REPOS_HUB` و`github-landscape.md`).
  - **قدرة جديدة:** مش متثبت ولا متوصّل. **ملحوظة:** كل الـ 66 متنزّلين كـ clone في `dragon-repos`. الـ clone بنعدّه «متثبت» لو المحتوى بيشتغل زي ما هو (مهارة Markdown أو مرجع أو كود importable). أما البرامج اللي محتاجة `pip`/`npm install` أو موديلات أو برنامج مضيف مش موجود (Photoshop وAfter Effects وBinary Ninja وIDA)، فالـ clone لوحده مايخلّيهاش متثبتة.

## الملخص

| الحالة | العدد |
|---|---|
| مستخدم | 29 |
| متثبت ومش متوصّل | 9 |
| قدرة جديدة | 12 |
| **الإجمالي** | **50** |

## جدول الخمسين

| # | Repo | الحالة | الدليل على الجهاز وفي المهارة | الإضافة الملموسة | التشغيل على Windows | ملاحظة الرخصة |
|---|---|---|---|---|---|---|
| 141 | elvarofficial/teardown | مستخدم | vendored في `engine/skills/teardown`، ومتثبت كمهارة في `~/.claude/skills/teardown`، ومتربط في `mind/playbooks.json` | (موجود) محاكي 3D لأي ماكينة، وتفكيك وقطاعات، وفيلم 60 فريم | مهارة `teardown` | MIT. الكيت نفسه بيقول إن الرندر والـ sfx جايين من `whaleyxbt/claude-motion` (MIT) |
| 142 | feitangyuan/onetake | متثبت ومش متوصّل | clone في `dragon-repos\feitangyuan__onetake`، وذكره في `SKILL_ATLAS.md` و`mind/intel/repos.json` بس، ومش متسجّل كمهارة | أفلام موشن للإطلاق والتيزر بلقطة واحدة متصلة (من غير قطع لسلايد) | انسخ فولدر المهارة لـ `~/.claude/skills` (Markdown + HTML/Playwright) | **PolyForm Noncommercial 1.0.0: ممنوع تجاري** (gh بيقول NOASSERTION) |
| 143 | fosdickio/binary_ninja_mcp | قدرة جديدة | clone في `dragon-repos\re` بس، وBinary Ninja مش متثبت. ذكره في `github-landscape.md` بس | MCP يربط Binary Ninja بالوكيل (decompile وrename) | محتاج Binary Ninja (مدفوع) + تثبيت البلجن | GPL-3.0. REA وGhidra بيغطوه |
| 144 | frida/frida-tools | مستخدم | `frida.exe` و`frida-ps.exe` و`frida-trace` في `re-tools\frida\venv`، ومتربطين في `retool.py` و`engine/tools/re/re.py` (RUNTIME، محتاجين `--yes`) | (موجود) تتبّع البرامج وقت التشغيل | `dragon.py tool re run frida-trace --yes ...` | wxWindows Library Licence 3.1 (gh بيقول NOASSERTION) |
| 145 | HKUDS/ViMax | قدرة جديدة | clone بس، ومالوش ذكر غير في الكتالوجات (`MONTAGE_REPOS_HUB`) | من فكرة لفيديو بوكلاء: سيناريو وستوريبورد وشخصيات ثابتة وتوليد لقطات | `pip install` + `configs/agent.local.yaml` بمفاتيح LLM ومولّد صور وفيديو (API مدفوعة) | MIT. التكلفة في الـ APIs |
| 146 | howseen-ai/claude-motion-design | مستخدم | vendored كـ `library/motion-design` (`SOURCE.json`) | (موجود) موشن بالكود: HTML + Playwright + ffmpeg | مهارة `motion-design` | MIT |
| 147 | Huanshere/VideoLingo | قدرة جديدة | clone بس. `whisperx` متثبت بس VideoLingo نفسه لا | خط كامل: تفريغ، وتقسيم جمل نتفليكس، وترجمة على 3 مراحل، ودبلجة TTS، وواجهة Streamlit | `pip install -r requirements.txt` + مفتاح LLM. نسخة Docker محتاجة NVIDIA | Apache-2.0 |
| 148 | heygen-com/hyperframes | مستخدم | 10 مهارات vendored (`hyperframes` و`hyperframes-cli` و`captions-overlay`...) ومذكور 57 مرة في `engines-render-pipeline.json` | (موجود) HTML لـ MP4 حتمي | `npx hyperframes render` | Apache-2.0 |
| 149 | iart-ai/motion-design-skills | مستخدم | 9 مهارات vendored (`after-effects` و`animation-principles` و`beat-sync-editing`...) | (موجود) أساسيات الموشن والتايمنج والألوان | مهارات Markdown | MIT |
| 150 | JuneYaooo/rea-video | مستخدم | vendored كـ `library/rea-video` ومعاه `references/setup.md` | (موجود) تفكيك أي فيديو لقطة بلقطة وإعادة بنائه | مهارة `rea-video` | Apache-2.0 |
| 151 | kajisho5/ffmpeg-skill | مستخدم | 10 مهارات vendored، بس كلها مهارات هندسة (`reviewing-ffmpeg-skill-changes` و`shipping-build-artifacts`...) | (موجود) جزئيًا. مهارة ffmpeg الأساسية نفسها مش من ضمن العشرة | مهارات Markdown | MIT |
| 152 | kumoproductions/mcp-aftereffects | قدرة جديدة | clone في `dragon-repos\creative`، ومتسجّل في جدول `creative-studio`، بس After Effects مش متثبت (مافيش `C:\Program Files\Adobe`) | تحكم في After Effects بـ MCP (comps وkeyframes وrender queue) | محتاج AE 2024+ وNode 24+ و`npm install` | MIT. قيمته صفر من غير AE |
| 153 | LaurieWired/GhidraMCP | قدرة جديدة | clone بس. Ghidra 12.1.4 موجود في `re-tools\ghidra`، بس البلجن مش متثبت | MCP جوه Ghidra (decompile وrename وxrefs) | تثبيت extension في Ghidra + bridge بايثون | Apache-2.0. REA (`rea analyze/decompile`) بيغطيه |
| 154 | leandromoreira/digital_video_introduction | متثبت ومش متوصّل | clone (مرجع)، وذكره في `MONTAGE_REPOS_HUB` بس | شرح الكودك والـ chroma subsampling والـ GOP والـ bitrate، ويفيد قواعد بوابة التسليم | قراية بس | BSD-3-Clause |
| 155 | lemomo-ai/lemo-opuscar | مستخدم | port بكودنا: `engine/tools/repo_fusion/scripts/fusion/native_opuscar.py` + `repo_fusion.json` | (موجود) ستايلات أفلام بالكود | `python native_opuscar.py` | MIT (ملف LICENSE، وgh بيقول NOASSERTION) |
| 156 | Leonxlnx/taste-skill | متثبت ومش متوصّل | clone بس. `dragon-genius/SKILL.md` بيقتبس فكرته (التصنيف حسب نوع الموضوع). مهارة `taste` المتثبتة حاجة تانية (origin ECC) | بناء مواقع شركات بمستوى احترافي | `install.sh` أو نسخ الفولدر | MIT. قيمته قليلة لشغل الفيديو |
| 157 | LobzyJay/motion-design-with-claude-and-codex | مستخدم | 3 مهارات vendored (`aftereffects-motion` و`blender-motion` و`motion-design-critique`) | (موجود) | مهارات Markdown | MIT. 41 نجمة بس |
| 158 | loonghao/photoshop-python-api-mcp-server | قدرة جديدة | clone في `creative`. `psd_studio/psd.py` بيقول إنه ينفع «بس لما Photoshop يتثبت». Photoshop وباكدج `photoshop` مش موجودين | تحكم في Photoshop عن طريق COM | محتاج Photoshop + `pip install` | MIT. Windows بس |
| 159 | mifi/lossless-cut | متثبت ومش متوصّل | `LosslessCut.exe` متثبت بـ winget. ذكره في كتالوجات ودراسة حالة `rea-ultra` (هندسة عكسية لـ Electron) بس، وماحدش بيشغّله | قص من غير re-encode بواجهة للمستخدم، ودمج، وتقسيم على الكيفريمات | `LosslessCut.exe` (فيه CLI محدود) | GPL-2.0. ffmpeg المباشر بيغطي الأوتوميشن |
| 160 | majidmanzarpour/blender-game-skills | مستخدم | vendored كـ `library/blender-image-to-3d` | (موجود) صورة لـ asset 3D جاهز للعبة | مهارة Markdown | MIT |
| 161 | mandiant/capa | مستخدم | `re-tools\capa\capa.exe`، وبيشتغل من `retool.py triage --deep` اللي بيستدعيه `app.py` | (موجود) قدرات أي exe | `retool triage FILE --deep` | Apache-2.0 |
| 162 | mandiant/capa-rules | مستخدم | `re-tools\capa-rules`، و`retool.py` (سطر 116) بيدّيه لـ capa | (موجود) | | Apache-2.0 |
| 163 | mandiant/flare-floss | مستخدم | `re-tools\floss\floss.exe` في `retool.py triage --deep` | (موجود) النصوص المخفية في الـ exe | | Apache-2.0 |
| 164 | MastroMimmo/claude-photoshop-skill | قدرة جديدة | clone بس، ومحتاج Photoshop وadb-mcp، والاتنين مش موجودين | تحكم في Photoshop من الترمينال | محتاج Photoshop + adb-mcp | MIT. 10 نجوم، وآخر push 2026-06 |
| 165 | KyaniteLabs/mcp-video (Kinocut) | مستخدم (المهارات بس) | 3 مهارات vendored (`kinocut` و`kinocut-repurpose` و`mcp-video`)، بس السيرفر و`kino` CLI مش متثبتين | (موجود كمهارة) مونتاج بـ MCP | `pip install` للسيرفر لو احتجناه | Apache-2.0. المستودع اتنقل لـ `KyaniteLabs/kinocut` |
| 166 | mifi/editly | قدرة جديدة | مش متثبت. كارت `ENG-238` في `engines-render-pipeline.json` حالته `gap` | مونتاج declarative بـ JSON على Node + ffmpeg (transitions وطبقات) | `npm i -g editly` | MIT. آخر push 2025-05، وHyperFrames بيغطيه |
| 167 | harry0703/MoneyPrinterTurbo | مستخدم | vendored كـ `library/moneyprinterturbo-video` ومعاه `mpt_agent.py`، والـ clone موجود | (موجود) فيديو قصير من موضوع | مهارة `moneyprinterturbo-video` | MIT |
| 168 | morluto/rea | مستخدم | `rea-agents@6.8.0` متثبت global، وسيرفر MCP `rea` متوصّل، و`app.py` بيستدعي `rea analyze`، و4 مهارات vendored | (موجود) المحلل العكسي الشامل | `rea analyze FILE` | MIT |
| 169 | mrexodia/ida-pro-mcp | مستخدم (المهارة بس) | vendored كـ `library/idapython`. IDA Pro مش متثبت، والسيرفر مش متثبت | (موجود كمهارة) كتابة سكربتات IDAPython | محتاج IDA Pro (مدفوع) | MIT. صاحبه بينصح بـ MCP الرسمي بتاع Hex-Rays |
| 170 | NationalSecurityAgency/ghidra | مستخدم | `re-tools\ghidra\ghidra_12.1.4_PUBLIC`، ومتسجّل في `retool.py` (analyzeHeadless)، وREA بيستخدمه للـ decompile | (موجود) | `rea decompile` أو `retool run ghidra` | Apache-2.0 |
| 171 | nexu-io/html-video | مستخدم | 10 مهارات `frame-*` vendored | (موجود) قوالب HTML لفيديو | مهارات | Apache-2.0 |
| 172 | veedstudio/open-edit | مستخدم | vendored كـ `library/open-edit` بوصفة `npx @veedstudio/openedit-cli` | (موجود كوصفة) | `npx --yes @veedstudio/openedit-cli init` | Apache-2.0. مربوط بـ VEED (سحابي) |
| 173 | OpenMontageInc/OpenMontage | مستخدم | 10 مهارات vendored، و375 ذكر في `SKILL_ATLAS.md` | (موجود) | مهارات | **AGPL-3.0**: لو اتعرض كخدمة لازم الكود يتنشر |
| 174 | PeterL1n/RobustVideoMatting | قدرة جديدة | clone بس ومن غير موديلات. `onnxruntime` 1.31.1 (CPU) موجود | فصل الشخص عن الخلفية في الفيديو من غير جرين سكرين، وبثبات زمني (alpha لكل فريم) | نزّل `rvm_mobilenetv3_fp32.onnx` من الريليس، وسكربت onnxruntime صغير، وبعدين `ffmpeg alphamerge` | GPL-3.0 (المخرجات ملكك). آخر push 2024 |
| 175 | rizinorg/cutter | قدرة جديدة | واجهة Cutter مش متثبتة. المحرك `rizin.exe` موجود ومستخدم في `retool.py` | واجهة رسومية للـ disassembly والجراف | `winget`/zip | GPL-3.0. rizin وREA بيغطوه |
| 176 | RobLe3/cc-blender-skill | مستخدم | 9 مهارات vendored (`blender-modeling` و`blender-lighting`...) | (موجود) | مهارات | MIT |
| 177 | facebookresearch/sam2 | متثبت ومش متوصّل | `import sam2` شغال من `dragon-repos\sam2`. موجود في `doctor` وفي `golden-bird/forge/build_catalog.py` (كتالوج). مافيش سكربت بيستدعي `build_sam2_video_predictor` | تتبّع ماسك عنصر على الفيديو كله (روتو) | سكربت Python + `ffmpeg alphamerge` | Apache-2.0. نفس حالته في Pilot 40 |
| 178 | snakers4/silero-vad | مستخدم (من خلال faster-whisper) | `silero_vad_v6.onnx` جوه `faster_whisper/assets`، و`engine/app/engines/audio.py` و`voice.py` بيشغّلوه بـ `vad_filter=True`. باكدج `silero_vad` نفسه مش متثبت | (موجود) كشف الكلام والسكوت قبل التفريغ | | MIT |
| 179 | remotion-dev/skills | متثبت ومش متوصّل | clone في `dragon-repos\skills` فيه `remotion-best-practices` و`remotion-captions` و`remotion-render`... بس مش متثبتين كمهارات. ذكرهم في `SKILL_ATLAS.md` بس | أفضل الممارسات الرسمية لـ Remotion (كابشن وصوت ورندر) | انسخ الفولدرات لـ `~/.claude/skills` | **مافيش ملف رخصة** (يعني كل الحقوق محفوظة). وRemotion نفسه محتاج رخصة شركة لو 4 موظفين أو أكتر |
| 180 | sunxiayi/make-blender-education-video-skill | مستخدم | vendored كـ `library/make-blender-education-video` | (موجود) | مهارة | MIT |
| 181 | trailofbits/skills | مستخدم | 10 مهارات أمان vendored (`secure-workflow-guide` و`audit-prep-assistant`...) | (موجود) | مهارات | CC-BY-SA-4.0 (لازم تنسب وتشارك بنفس الرخصة) |
| 182 | tenfoldmarc/video-edit-skill | متثبت ومش متوصّل | clone بس، وذكره في `SKILL_ATLAS.md` و`MONTAGE_REPOS_HUB` | لقطات talking-head من الموبايل تتحوّل لريل إنستجرام بأمر واحد | نسخ المهارة | **مافيش ملف رخصة** (كل الحقوق محفوظة)، فاقرا الأفكار بس. `autoclip` و`video-use` بيغطوه |
| 183 | browser-use/video-use | مستخدم | vendored كـ `library/video-use` ومعاه `install.md` | (موجود كوصفة) مونتاج بـ Claude | `uv sync` + `ELEVENLABS_API_KEY` | MIT |
| 184 | viettranx/3dviz-pro-max | متثبت ومش متوصّل | clone في `creative`، ومتسجّل في جدول `creative-studio` بس | فكرة لمشهد 3D تفاعلي (Three.js/Blender) وبعدها فحص اللي ظاهر فعلًا | نسخ المهارة | MIT |
| 185 | Vincentwei1021/video-shotcraft | مستخدم | port بكودنا: `native_shotcraft.py` (beat grid وav-offset وsfx-peak وخطة JianYing) | (موجود) | `python native_shotcraft.py self-test` | Apache-2.0 |
| 186 | m-bain/whisperX | مستخدم | `whisperx.exe` والموديول متثبتين، ووصفة في `codekit.py` (سطر 109)، ومستخدم في `golden_tools.py` | (موجود) تفريغ بتوقيت الكلمة | `whisperx in.wav --language ar` | BSD-2-Clause |
| 187 | wtsxDev/reverse-engineering | متثبت ومش متوصّل | clone (قايمة awesome)، وفي `github-landscape.md` بس | قايمة كتب وأدوات للهندسة العكسية | قراية بس | مافيش ملف رخصة. آخر push 2023 |
| 188 | YaoFANGUK/video-subtitle-remover | قدرة جديدة | clone بس ومن غير موديلات | يشيل الترجمة المحروقة والعلامات المائية من الفيديو بـ inpainting من غير ما يقلّل الدقة | فيه بيلد Windows جاهز: `vsr-windows-cpu.7z` أو `vsr-windows-directml.7z` (لكروت غير NVIDIA) | Apache-2.0 |
| 189 | zhouxiaoka/autoclip | مستخدم | vendored كـ `library/autoclip` (و`product-board`) | (موجود) من لينك لكليبات وغلاف ونص نشر | `uvx autoclip-mcp` | MIT. الموديلات السحابية بفلوس حسب الاستخدام |
| 190 | zinja-coder/apktool-mcp-server | قدرة جديدة | السيرفر مش متثبت. `apktool.bat` نفسه موجود ومستخدم في `retool.py` و`recipes.py` | apktool كـ MCP للوكيل | `pip`/`uv` + Java | Apache-2.0. `android-reverse-engineering` وREA بيغطوه |

## أهم 10 إضافات (حسب القيمة لشغل الفيديو والصور والموشن)

| # | الأداة | ليه | أرخص طريقة للإضافة |
|---|---|---|---|
| 1 | **SAM 2** | روتوسكوب وعزل أي عنصر في الفيديو كله بضغطة. لسه مش متوصّل من Pilot 40 | **مافيش تثبيت.** الكود و`sam2.1_hiera_tiny.pt` موجودين. اكتب `sam2_track.py` (فيديو + نقطة أو مربع → PNG masks) وبعدين `ffmpeg alphamerge` |
| 2 | **RobustVideoMatting** | فصل الشخص عن الخلفية من غير جرين سكرين، وثابت بين الفريمات. ده مطلوب جدًا في الريلز والتيتلز ورا الشخص | `onnxruntime` موجود. نزّل ملف `rvm_mobilenetv3_fp32.onnx` (بموافقة)، واكتب سكربت يطلّع alpha، و`ffmpeg alphamerge`. على CPU استخدم downsample 0.25 ومقاطع قصيرة |
| 3 | **video-subtitle-remover** | يشيل الترجمة المحروقة واللوجوهات من فيديو جاهز قبل ما نحط ترجمتنا العربي | بيلد `vsr-windows-directml.7z` أو `cpu` جاهز (بموافقة على التنزيل)، ويتشغّل كـ exe منفصل من غير ما يلمس بايثون المهارة |
| 4 | **VideoLingo** | تقسيم الجمل على طريقة نتفليكس وترجمة على 3 مراحل ودبلجة. ده بيكمّل whisperX الموجود | الأرخص: ناخد منطق التقسيم والترجمة كـ port بكودنا (زي shotcraft) فوق `whisperx` الموجود، بدل ما نثبّت Streamlit كله |
| 5 | **remotion-dev/skills** | ممارسات Remotion الرسمية للكابشن والصوت والرندر، وcodekit عنده وصفة Remotion أصلًا | الـ clone موجود. انسخ `remotion-best-practices` و`remotion-captions` لـ `~/.claude/skills`. خلي بالك إن مافيش ملف رخصة |
| 6 | **onetake** | أفلام إطلاق منتج بلقطة واحدة متصلة، ودي ستايل مش موجود في المهارة | الـ clone موجود، انسخ فولدر المهارة. **استخدام شخصي بس** (PolyForm Noncommercial) |
| 7 | **3dviz-pro-max** | مشاهد 3D تفاعلية بفحص اللي ظاهر فعلًا، وده بيكمّل teardown وthree.js | الـ clone موجود (MIT). انسخ المهارة لـ `~/.claude/skills` |
| 8 | **digital_video_introduction** | مرجع للكودك والـ GOP والـ chroma. يفيد قواعد `media_gate.py` وقرارات الترميز | الـ clone موجود. اربطه كمرجع في `references` أو لخّص منه قواعد |
| 9 | **LosslessCut** | قص ودمج من غير re-encode بواجهة، لما المستخدم يحب يقص بإيده | متثبت بالفعل. سجّله في كتالوج الأدوات اللي بتتفتح للمستخدم (زي x64dbg وimhex) |
| 10 | **video-edit-skill** | talking-head من الموبايل لريل كامل بأمر واحد | اقرا الأفكار بس (مافيش رخصة)، وظبّطها جوه `autoclip` أو `video-use` الموجودين |

### ملاحظات جانبية

- **Photoshop وAfter Effects:** مش متثبتين، فـ `mcp-aftereffects` و`photoshop-python-api-mcp-server` و`claude-photoshop-skill` قيمتهم صفر دلوقتي حتى لو الـ clone موجود.
- **Binary Ninja وIDA:** برامج مدفوعة ومش متثبتة. `binary_ninja_mcp` و`ida-pro-mcp` (غير مهارة `idapython`) مالهمش لازمة طالما REA وGhidra شغالين.
- **GhidraMCP وCutter وapktool-mcp-server:** المحركات اللي تحتهم (Ghidra وrizin وapktool) متوصّلة بالفعل عن طريق `retool.py` وREA، فالإضافة صغيرة.
- **OpenMontage:** رخصته AGPL-3.0. المهارات الـ vendored تمام للاستخدام المحلي، بس أي خدمة منشورة مبنية عليه لازم الكود بتاعها يتنشر.
- **trailofbits/skills:** رخصته CC-BY-SA-4.0، يعني لازم تنسب أي تعديل وتشاركه بنفس الرخصة.
- **ffmpeg-skill:** اللي اتعمله vendor 10 مهارات هندسة عامة. مهارة ffmpeg الأساسية نفسها مش في `library/`. لو محتاجينها، انسخها من الـ clone.
- **ViMax:** فكرته قوية (شخصيات ثابتة على كذا لقطة)، بس محتاج مفاتيح API لـ LLM ومولّد صور وفيديو بفلوس، فمش في التوب 10.
- **editly:** آخر push كان 2025-05، وHyperFrames الموجود بيعمل نفس الشغل.
- **teardown:** الكيت بتاعه جاي من `whaleyxbt/claude-motion` (MIT). اتأكد إن الرخصتين متذكورين لو اتوزّع.
- **mcp-video:** المستودع اتنقل لـ `KyaniteLabs/kinocut`.
