# خريطة الطريق: اللي اتعمل في v1.2 واللي جاي

اقرا ده امتى: لما مرجع يقول «يدوي (مفيش أمر لسه، شوف ROADMAP.md)» أو «تذكرة»، وقبل ما توعد بأمر مش موجود، وقبل أي جولة تطوير أو تغليف للمهارة.

- `$D` = `python3 <skill>/scripts/dragon.py`. الأوامر الجاية مكتوبة `dragon <أمر>` من غير `$D` لأنها **لسه مش موجودة**: ماتشغّلهاش وماتوعدش بيها.
- الحالة: «✅» = شغال ومتختبر · «⚠️» = شغال بحدود مكتوبة · «لسه» = مااتعملش.
- الأرقام من تقارير المبرمجين والمجمّع يوم 2026-11-08، ومن تشغيل الاختبارات يوم 2026-11-09.

## A. اللي اتعمل في v1.2

| الأمر | بيعمل إيه | اختبار القبول | الحالة |
|---|---|---|---|
| `$D verify FILE --expect 1080x1920 --duration S [--no-black]` | بوابة التسليم: exit 1 على سواد جوه الفيلم، أو صوت مش AAC جوه MP4/MOV، أو فريمات ≠ round(S×fps) | `tests/test_v12_verify.py` (14). على أفلام حقيقية: الـ 40 ث القديم exit 1 بـ 6 جريات / 84 فريم، ونسخته v2 exit 0؛ «أجنحة من ورق» القديم exit 1 بـ 6 جريات / 62 فريم (مش 2 زي ما الخطة كانت فاكرة)؛ «شتا الرياض» exit 1 (MP3 جوه MP4)، ونسخة AAC exit 0؛ و`--no-black` بيعدّي الـ 40 ث الوحش (يعني ممنوع للتسليم) | ✅ |
| `node app/engines/render/render.cjs … --strict` | حارس السواد: كل فريم canvas بيتقاس، والأسود بيتعاد من صفحة أجدد (reload ← context ← browser)، و`--recycle 120`، و`--strict` = exit 3 | `tests/test_v12_render.py` (10): fixture بيسوّد بعد 40 seek اترجّع كله، و`--no-guard` بيسيب الجرية، و`--strict` exit 3. الناتج MD5 زي v1.1 بالظبط على صفحات 2D وWebGL وعلى محرك السينما 1080×1920 | ⚠️ الفشل الحقيقي ماتعادش (fixture بس)؛ صفحة حقيقية (`out/20261105-mapfilm/film/index.html`، 3 ث) لسه مااتجربتش |
| `$D mux VIDEO AUDIO OUT --duration S [--normalize]` | طول بالفريم، AAC يتنسخ، غيره AAC 320k 48kHz، `--normalize` = I −14 / TP −1.5، من غير `-shortest`، وverify في الآخر | `tests/test_v12_deliver.py` (9). «شتا الرياض» MP3 ← AAC، 5012 فريم، verify exit 0 | ⚠️ لسه: قياس `--normalize` على الرياض (≈ −14 LUFS، ذروة ≤ −1.5)، وMD5 النسخ على «قوم يا مصري»، والمد لـ 46 ث |
| `$D patch-black IN OUT` | آخر حل: آخر فريم سليم مكان الأسود، CRF 17 slow BT.709، وفحص تاني | نفس ملف الاختبار. مقطع 30 ث من «أجنحة من ورق»: 2 جرية / 39 فريم اتصلّحوا، و`black runs left: 0`، وverify exit 0 | ⚠️ الفيلم الـ 40 ث كامل (6 جريات) وورقة التجميد لسه |
| `$D align REF SONG --out map.json` | أنهي حتت من الأغنية في الريل، ونقط القص، واللي مش من الأغنية | `tests/test_v12_songs.py` (14). ZSpjRC5Fe على `shadia.m4a`: حتة 3:50.57–4:37.12، وفجوة 6.25 ث، وoffsets +221.350 / +215.020 | ✅ (لسه: مطابقة الرياض لنفسها، والسالب على «قوم يا مصري») |
| `$D lyrics-sheet VIDEO OUT.jpg [--band] (--times\|--every\|--transcript)` | ورقة من شريط الكلام تقرا منها الكلمات بعينك | نفس ملف الاختبار: بلاطة لكل وقت، والشريط الافتراضي 0.84–0.94، وأخطاء واضحة | ⚠️ لسه: فيديو «ليل يا ليل» الحقيقي (17 و21 ث لازم يتقروا «في شئ فينا مقوينا» و«وبنسند روحنا علينا»)، و`--transcript` بملف صفوفه `[start, end, text]` (لازم يقبله أو exit 1 برسالة، مش ورقة فاضية) |
| `$D tool tiktok-post URL --out DIR` | صور وصوت بوست الصور من JSON الصفحة (yt-dlp مابيفتحوش) | `tests/test_v12_tiktok_post.py` (24) بصفحات محفوظة وسيرفر محلي | ⚠️ بيعتمد على JSON تيك توك وممكن يتقفل من السحابة؛ الأوامر غير الخطة (أمر واحد، exit 0/1/2، مفيش fetch/parse/url) |
| `$D tool styles` | 6 ستايلات (nil، beat، wall، medal، chapters، clean) من spec واحد ← صفحة ← stills ← MP4 | `tests/test_v12_styles.py` (25) | ⚠️ فحص الممنوعات الكامل لسه (T7)، و`beat: "auto"` مااتجربش |
| اللانشر | نسخة `/tmp/dragon` بـ `.bundle_stamp` بتتجدد لوحدها، و`where` بيقول `engine_version` و`bundled_version` | `tests/test_v12_integration.py` (7)، والسلسلة كاملة: رندر فيه سواد + MP3 ← verify يقع ← patch-black ← mux ← verify يعدّي | ✅ |
| المراجع وSKILL.md | الأوامر دي كلها في SKILL.md §3، والمراجع الجديدة | `tests/test_v12_docs.py`: كل `$D <أمر>` و`$D tool <اسم>` في SKILL.md والمراجع موجود في الكود، والوصف سليم، وكل مرجع ليه مكان في جدول §12 | ✅ |

- الاختبارات كلها: 131 ناجح و123 متخطّي بعد التجميع، و138 ناجح و123 متخطّي (2:39 د) بعد اختبار الوثايق (2026-11-09). المتخطّي محتاج Playwright/موديلات/ميديا مش موجودة هنا.
- `engines/audio.py`: مكساج `$D mix` بقى TP −1.5 زي `mux --normalize` (كان −1.0). لسه sidechaincompress ومن غير RMS (C2).

## B. قايمة التغليف (قبل ما تبعت الـ zip)
1. `python3 quick_validate.py <skill>` = «Skill is valid!»، وSKILL.md ≤ 320 سطر.
2. `cd app && python3 -m pytest -q tests` أخضر، و`tests/test_v12_*` كلها ناجحة.
3. شيل `__pycache__` و`.pytest_cache` من الـ zip (نسخة v1.1 ماكانش فيها). `/tmp/pytest-of-root` برّه المهارة.
4. الوصف ≤ 1024 حرف، من غير `<` أو `>`، ومن غير أرقام كتالوج ولا رقم إصدار.
5. **تقييم التشغيل (مااتعملش في الجولة دي):** الملف جاهز `/home/user/kosif-tool/out/20261108-skill/evals/trigger_eval.json` (20 طلب حقيقي منه بالحرف ومقصوصين، و10 طلبات مش بتاعته). القبول: ≥ 18/20 يشغّلوا المهارة، و≤ 1/10 غلط. ليه مااتعملش: حسابه فيه مهارة black-dragon أقدم هتنافس الجديدة على نفس الكلام فالنتيجة مش هتبقى عادلة، والتقييم محتاج حوالي 30 جلسة متداخلة. يتشغّل بعد ما النسخة القديمة تتشال أو تتبدّل:
   `python3 <skill-creator>/scripts/run_eval.py --eval-set /home/user/kosif-tool/out/20261108-skill/evals/trigger_eval.json --skill-path <skill> --runs-per-query 3 --verbose`
6. العدادات: SKILL.md فيه رقم واحد بس (الكتالوج 22,319 عنصر من `$D stats`) بتاريخه. لسه: بلوك `<!-- counts:start/end -->` يكتبه `dragon build` وعليه اختبار.
7. الدروس اللي بقت بوابات في الكود: السواد ← `verify` وحارس `render.cjs`؛ MP3 جوه MP4 ← `verify` و`mux`؛ الطول القصير ← `verify --duration` و`mux`؛ كلام الأغنية الغلط من whisper ← `lyrics-sheet`؛ نقط قص الأغنية ← `align`؛ بوست الصور ← `tool tiktok-post`؛ الممنوعات ← `tool styles` (جزئي، T7).
8. مسارات kosif-tool في المراجع متعلّم عليها «(PC only)» أو «kosif-tool بس». اختبار المسارات لازم يقبل الوسمين.
9. على جهازه: ريبوه القديم (0.1.0) مافيهوش أوامر v1.2. قوله ينسخ `app/` فوقه، أو يشغّل بـ `DRAGON_MODE=cloud`.
10. حاجات ثقتها متوسطة تتأكد معاه في أول جلسة v1.2: اللينك الخاص كإذن دايم، الدفعة اللي عدّت من غير وقفة ستوري بورد (2026-11-08)، الـ dip لـ #111 بدل الأسود، جدول الأماكن التلاتة، سطر ⏱، وألفا سطر الحقوق التاني (.8 ولا .82).

## C. ثغرات الكود اللي لسه
1. **`-shortest` لسه في** `app/engines/matrices/scene.py:92`، `app/engines/talking_head/render.py:265`، `app/engines/shadow_theatre/__init__.py:158`، `app/engines/dragon_montage/common.py:194` (ده `make_test_clip` للاختبارات، مش تسليم)، وفي `app/engines/cards/lib/`: `fam_w3_05`، `fam_w3_06`، `fam_w3_09`، `fam_music_beat_sound`، `formats_platforms`، `photo_video_footage`، `fam_transitions_cuts_a`، `fam_transitions_cuts_b`. لحد ما تتحوّل لـ `deliver.mux`: خلّص أي فيلم منهم بـ `$D mux … --duration D` و`$D verify --duration D`. القبول: `grep -rn -- -shortest app/engines --include=*.py` مايرجّعش غير التعليقات.
2. **`engines/audio.py`:** `words()` على موديل small وVAD شغال ← medium افتراضي، و`--sung`/`--recited` من غير VAD، ودخل numpy، و`initial_prompt`، وشكل كلمات يقراه `quran_text align`. `mix()` ← RMS، وducking بالـ dB بماسك وcumsum ramps، وAAC 320k في الـ mux، ومفتاح «من غير مزيكا تحت الصوت». `beats()` ← spectral flux بـ numpy وشبكة بالفيز. القبول: `words()` على `out/20261106-tilawa/quran.m4a` يرجّع عدد كلمات medium من غير VAD على الأقل، و`mix()` يوطّي المزيكا بالـ dB المطلوب ±0.5 تحت الأصوات.
3. **القرآن:** نقل `quran_text` (fetch، pauses، align) جوه التنين كبوابة، وضم ScheherazadeNew-Bold (OFL) لـ `tools/styles/fonts`، و`chapters` يرسم الآيات بيه والأقواس برّه السطر الـ RTL. القبول: fetch لـ 35:34 يطابق sha256 بتاع الـ API.
4. **text-lint:** تغطية الخط للحروف، الأرقام جنب «·»، نصين في نفس الوقت، كلمات ممنوعة («الفصل»، «الشوربجي»)، الـ baseline ≤ y 1700، والنص فوق وش.
5. **kosif-tool لسه بيسمح بنسخ MP3 جوه MP4:** `.claude/skills/kosif-superpowers/scripts/export_profile.py:41` (`MP4_COPY_AUDIO`)، و`tools/render_html.cjs:693`، واستثناء MP3 في `verify_video.py`، و`playbooks/export-standard.md:15`. ده PR لوحده في kosif-tool، وبإذنه بس.
6. **حدود اتقالت ولسه مفتوحة:**
   - حارس الرندر مابيفحصش حاجة في فيلم ≤ 2.1 ث بالشبابيك الافتراضية، ولا في صفحة مافيهاش `<canvas>`.
   - سواد مقصود في نص الفيلم مش متعلّم بـ `allowBlack` بيوقّع `verify`، والحل الوحيد `--no-black`. محتاج `verify --allow-black a-b` أو قراية `allowBlack` من الصفحة.
   - `verify` بيفك كل فريم: حوالي 2.5 د لـ 10 د فيلم هنا.
   - `qa.audio_check` بيرفض PCM جوه `.mov`، فماستر ProRes/PCM بيقع.
   - `patch_black` بيرفض أكتر من 1000 جرية (حد سطر الأوامر في ويندوز).
   - `$D engines` و`$D run` مابيعرضوش `engines.songs` (اوصله بـ `align`/`lyrics-sheet` أو `python -m engines.songs`).
   - رسالة تحذير العلو بتقول (−16..−12) والكود بيحذّر برّه −16.5..−11.5.
   - `$D run web_film render` و`$D run matrices` بيخبّوا سطور RECOVERED/SUMMARY ومابيبعتوش `--strict`، و`web_film render --audio` بيعمل mux بـ `-t` على stream copy.
   - `talking_head`: فريمات RGB متعلّم عليها BT.709 من غير تحويل ماتريكس صريح.
   - `tool styles`: `--recycle` افتراضيه 90 (الرندر 120)، و`numbers` افتراضيه true، وألفا السطر التاني .82، والسطر لحد 1000 px (المرجع 960)، و`--check` بيطلع exit 0 مع MISSING، و`--render` بيعمل patch-black لوحده قبل إعادة الرندر.
   - `tool motion match` بيرجّع `[]` لطلب عربي.
   - `required_tools.json` (نسختين) لسه فيه مسارات `.kosif-node` و`dm_doctor.py` القديمة.
   - `web_film plan --require` بيحط كل الطلبات على لقطة 0، فـ `check` بيعدّي؛ و`spec.json` و`edl.json` مافيهمش فحص تغطية.
   - مفيش قالب ستوري بورد مدمج ولا أمر يصوّره PNG.

## D. التذاكر للجولة الجاية
كل تذكرة بتتقفل باختبار، وعلى ملف حقيقي من `out/` لو موجود.

| # | التذكرة | بوابة القبول |
|---|---|---|
| T1 | إثبات الصوت والحاوية: `dragon verify --source-audio A` (MD5 حزم الصوت = A)، وفحص h264 High وyuv420p وbt709 التلاتة وmoov قبل mdat وستريم صوت واحد و≥ 44.1 kHz، ومفاتيح جديدة في الـ evidence | أفلام ميار المنسوخة صوتها: MD5 مطابق؛ «شتا الرياض» يقع (mp3)؛ remux بـ `-shortest` يطلع MD5 مش مطابق؛ ffprobe/ffmpeg بس ومن غير شبكة |
| T2 | رندر بحتت يكمل لوحده: `render.cjs --start S`، و`dragon render page.html --chunk 2 --out film.mp4 --resume` (حتت `job/chunks/p%03d.mp4`، يعدّي اللي موجود ونضيف، متصفح واحد في المرة، TMPDIR للشغلانة، concat بقايمة جوه فولدر الحتت، وبعدها mux بالمدة) | تقتل الشغلانة في النص وتعيد: الحتت الناقصة بس تترندر؛ النهائي round(D×30) فريم و0 جريات سواد |
| T3 | `dragon job start\|wait\|status\|stop` (نقل `tools/job.py`: الإيقاف بالـ pid أو مجموعة العمليات المتسجلة، عمره ما يبقى `pkill -f`) | `wait` يطبع PROGRESS وبعدها DONE أو FAILED بالـ exit code؛ شغال على ويندوز ولينكس |
| T4 | فحص اللقطات: `dragon shots audit spec.json` ← `audit.jpg` (أول ونص وآخر كل لقطة) و`audit.json` (وشوش YuNet، نسبة نص PPOCR، متوسط الإضاءة)؛ بيعلّم نص > 0.003 (b-roll) / > 0.004 (pool)، وإضاءة < 48، و0 وشوش في لقطات البطل، و`$D film` يرفض لحد ما يتحل أو يتعلّم reviewed. و`dragon sheet final.mp4 --every 7 --cols 8` لورقة QC | بيعلّم J2 11–16 ث والـ b-roll الغامق في مادة `out/20261105-ten`؛ CPU بس بالموديلين بتوع الجلسة |
| T5 | ضم عميل الـ stock (`free_footage.py` وقاري الرخص) جنب `tools/stock/free_photos.py`، و`dragon tool stock video search\|download`، ومحطة الـ stock في المونتاج تستخدمه | `tools/stock/free_photos.py sources` يطلع exit 0 من غير شبكة (النهارده ModuleNotFoundError)؛ الاختبارات بردود متسجلة |
| T6 | وسم المكان: الـ sidecar فيه query وtitle وlocation_claim وverified_location (null لحد ما حد يبص على شريط 3 كادرات)، و`$D film` والمونتاج يرفضوا كليب مكانه مش متأكد لما الطلب فيه مكان | على `out/20261108-riyadh`: 12 كليب ← 12 شريط، والكليب اللي طلع برج مكة مايدخلش فيلم الرياض لحد ما يتعلّم |
| T7 | فحص الستايل: `tools/styles/bans.json`، والفحص exit 1 على أي حاجة ممنوعة من غير استثناء متسجّل (`allowed_by_owner`: تاريخ + كلامه): تسريب نور، أشعة شمس، دواير على الوش، دوتون أحمر، فيلم ستريب أو كلاكيت، «الفصل»، أرقام جنب «·»، «…» بخط Lalezar | يعلّم `out/20261108-trio/A/nil.js` (leak)، و`out/20261106-words/film/honor.js` («الفصل »)، و`out/20261106-bint/build.py` («سورة فاطر · ٣٤»)؛ و`out/20261106-forty/film/clean.js` يعدّي |
| T8 | بوابة النص: `dragon text-gate page.html --times …` يرندر stills عادي وNOTEXT (`window.__kosif.notext=true`)، ويعمل ماسك للفرق > 40، ويقع على mean > 95 أو p95 > 140 أو نص فوق وش | كلمة أغنية فوق وش (حالة S13) تقع |
| T9 | `dragon deliver final.mp4 [--max-part-mb 450] [--zip]`: verify الأول (يرفض لو exit ≠ 0)، ونسخة موبايل CRF 23 (26 لو أكبر من الحد)، وتقسيم عند الـ keyframes، وzip بـ `-0` لو طلب، و`LINKS.md`/`CREDITS.md` | فيلم 2462 ث يطلع حتت ≤ 450 MB وكل حتة تعدّي verify |
| T10 | `where` يزوّد disk_free_gb وram_gb وcpus وmode (chat-cloud \| code-cloud \| pc) وuploads_dir وقناة التسليم وkosif-tool في أعلى ريبو git ونصيحة workers=1، والرندر يرفض تحت 3 GB فاضي | في Claude Code يقول code-cloud، وkosif-tool موجود، والهارد الفاضي الحقيقي، ويرفض رندر تحت الحد |
| T11 | مسارات السينما في السحابة: `_paths` نسبية للشغلانة (refs/audio/out/work) وتقع بسرعة بـ «set spec.paths or BDC_REFS»؛ وتوثيق BDC_REFS وBDC_AUDIO وBDC_DELIVER وBDC_WORK وBDC_LUTS | `$D film templates/example_beat_cut.json --stills 1` يشتغل في فولدر شغلانة فيه refs/ من غير متغيرات |
| T12 | `dragon ledger`: `ledger add --film F --verdict praised\|rejected\|fixed --quote '…'` و`ledger used --moment <src:t0-t1> --film F` (SQLite في `data/`)، و`$D film` يحذّر من لحظة اتستخدمت في نفس السلسلة، وكروت الستايل تترتب بأحكامه | استيراد `out/20261105-ten/pool.json` و`bans.txt` يعيد نفس التوزيع من غير تكرار، و`ledger list --praised` يرجّع فيلم «بلادي اسلمي» |
| T13 | `setup` بموافقة: يطبع خطة pip/winget ويثبّت بس بـ `--yes` (و`DRAGON_ASSUME_YES=1` للـ CI)، و`setup --help` يطبع مساعدة بدل ما يثبّت، وSKILL.md §0 يشغّل `where` و`doctor` الأول | على جهاز من غير `--yes` pip عمره ما يتنده؛ `setup --help` exit 0 من غير تثبيت |

## E. حاجات المراجع بتعملها بالإيد ومالهاش تذكرة لسه
- قاموس الكتابة بالصوت جوه `$D find` (OWNER.md §3).
- `PENDING.md` و`DELIVERED.md` وتقدّم الشغلانة (OWNER.md §5)، وسجل الكريدت `ledger.tsv` (OWNER.md §6): ممكن يدخلوا T12.
- سجل اللينكات بالـ id (SOURCES.md §4)، وضم حتت الرفع من غير kosif-tool، وملاحظات المكان في الـ manifest (تدخل T6).
- إعادة رندر 1–2 ث (محتاجة `--start` من T2)، وفحص التجمّد، والقفزات عند الوصلات، وورقة هوية بـ 3 كادرات (QA.md).
- فحوصات الستايل: وسيط اللقطات وأقصر نقلة، عدّ أنواع النقلات، نسبة الدهبي، مدة الاقتباس ومقاسه، الأوضاع الأفقية في الكيت، كروت الستايل كـ JSON بحكمه وستيل، ومونتاج stock بـ ffmpeg كأمر (STYLE_RECIPES.md؛ جزء منها في T7 وC4).
- إثبات MD5 الصوت (T1)، وقالب المكساج بـ numpy وشبكة البيت (C2)، وتفريغ من غير VAD (C2)، ومتكلمين المناظرة، ومؤثرات النقلات، وفواصل التلاوة (C3) (AUDIO_SONGS_QURAN.md).
- فلتر الرسم بدل وش ميار، وفحص البرومبت من الأسامي والوشوش، وكل رقم على الشاشة في `sources.md` (PROTOCOL.md).
- جدول إصدارات البرامج في `$D doctor` (ENVIRONMENTS.md §10).
