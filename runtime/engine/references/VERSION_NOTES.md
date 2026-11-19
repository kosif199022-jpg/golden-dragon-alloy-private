# VERSION NOTES — التنين الأسود

## SKILL.md version blocks (moved verbatim from SKILL.md in v1990.10.0, 2026-11-12)
The blocks below were the top and bottom of SKILL.md through v1990.9.0. They are copied here byte-for-byte so the
front door of SKILL.md stays short; every command in them still works (`dragon.py tool …`).

## ⛔ v1990.9.0 — كل اللي وصلنا له في مكان واحد
- **اقرا الأول:** `references/SESSION_HARVEST_V19909.md` (14 ستايل بقوالبها، طريقة «قلده»، دروس الفحص والخطوط، العدّة، الأجهزة وأسعارها المقاسة، والطلبات المستنية) مع `SESSION_HARVEST_V19905.md` و`PROJECT_HARVEST_V19906.md` و`LESSONS.md`.
- **رجعت مكتبة v10.17:** `python scripts/dragon.py tool library find "…"` (12 حزمة مهارات تحت `skills/library/` + 105 برومبت تحت `references/prompts/`). التفاصيل `references/LIBRARY_V1017.md`.
- فهرس الأدوات `app/data/own_tools.json` فيه دلوقتي: library، looks، mono، codekit، video12، palette، chroma.

## ⛔ v1990.8.0 — عدّة الفيديو بالكود (الـ 12 أداة) جوّه التنين
- `python scripts/dragon.py tool codekit status` (إيه الموجود على الجهاز ده وإيه لأ) · `map` (خريطة المترو: يبني الفيديو / الشكل / الحركة / الصوت والملف) · `demo three|anime|mojs|rough|gsap OUT` (صفحة تجربة جاهزة لمحرك التنين) · `install NAME|all` (بيطبع أوامر التثبيت، ومايثبتش إلا بـ `--run`).
- **متضمّنة جوّه الحزمة (MIT، اتجربت بـ stills):** Three.js، anime.js، mo.js، Rough.js. **GSAP** مجاني بس مش مفتوح المصدر فمش متضمّن: `codekit vendor-gsap DEST` بينسخه من نسخة npm.
- **على الجهاز السحابي:** Remotion وHyperFrames وauto-editor وFFmpeg موجودين. **Motion Canvas وManim وWhisperX** بيتثبتوا على جهاز صاحب التنين (Manim محتاج pangocairo، WhisperX محتاج torch)؛ بديل WhisperX الشغال هنا faster-whisper.
- auto-editor: خلّي هامش (`--margin 0.3sec`) عشان الكلام مايطلعش مقطّع. الصفحات لازم تتحرك من `t` (timeline متوقف + seek)، مش autoplay.
- **التنين كمخرج بالـ 12 أداة:** اقرا `references/VIDEO12_DIRECTOR.md` (إيه اللي اشتغل مع بعض فعلًا وإيه لأ) وشوف `tools/codekit/demos/fusion_demo.html` (خمس مكتبات في فريم واحد من ساعة واحدة `t`).
- **ستايل «teardown» (محاكي ماكينة 3D بيتفكك ولوحة تحكم هندسية):** تحليل الشكل والمونتاج والصوت في `references/TEARDOWN_STYLE_ANALYSIS.md` (من قراءة الريبو ونص المقال، وبعدها تشغيل أمثلته هنا: بناء + لقطات + صوت؛ الفيديو الكامل لأ). البرومبتات التسعة كقالب: `references/TEARDOWN_PROMPTS_9.md`.
- **`tool video12`** (من نسخة صاحب التنين «video12-updated»، اتضمّت كما هي): `list` · `plan "وصف الريل"` (بيرشّح أنهي أدوات من الـ 12) · `doctor --json` · `install --all` (معاينة بس؛ التثبيت الفعلي بـ `--yes` على جهاز الإنتاج) · `run ffmpeg|hyperframes|remotion -- …`. **الفرق:** `video12` للتخطيط والتثبيت والتشغيل، و`codekit` فيه المكتبات المتضمّنة وصفحات التجربة لمحرك التنين. الاتنين شغالين مع بعض.
- **`resources/hf-blender-render/`**: نسخة صاحب التنين الأصلية من مشهد Blender (EEVEE + motion blur)، مصدر بس وماتشغّلتش؛ النسخة المُراجعة في `skills/hf-blender-render/` و`tool hf-blender`.
- **كروما موشن** (مهارة صاحب التنين chroma-motion، اتضمّت كما هي): `python scripts/dragon.py tool chroma IMAGE --name "…" --tagline "…" --out DIR --video 9:16 --seconds 8` ← لوحة هوية + `motion.mp4` + صفحة HTML + tokens + باليتة فوتوشوب/GIMP، ولغة حركة من شكل الصورة (wing / wave / bloom / orbit / pulse). التفاصيل `tools/chroma_motion/SKILL_chroma_motion.md`. فصل الموضوع محتاج موديل rembg `isnet-general-use`؛ من غيره شغّل بـ `--subject off`. الألوان المتولّدة بتتعلّم `(synthetic)` ولازم تتقال.
- **باليتة الطبيعة** (مهارة صاحب التنين nature-palette، اتضمّت كما هي): `python scripts/dragon.py tool palette extract PHOTO --title "…"` (كارت ألوان بالـ HEX والأسماء بالعربي والأدوار والتناغم) · `reel` (ريل 9:16 بالقطّارة) · `learn` (كونتاكت شيت لريل مرجعي). التفاصيل `tools/nature_palette/SKILL_nature_palette.md`. افحص الماسك بعينك قبل التسليم.
- ستايل جديد: **ST14 طباشير على سبورة** `tools/chalk_board/` (الخط Marhey Bold).

## ⛔ v1990.7.0 — «قلده تمام» + «احفظ الاستايل»: 5 ستايلات جديدة بقوالبها
- **قبل ما تقلد ريل:** نزّله، contact sheet، اقرا الكلام من الشاشة (أدق من التفريغ)، قِس القطعات، واعرف هل يتعمل **بالكود (صفر كريدت)** ولا محتاج صور/تحريك (اعرض السعر واستنى).
- **ST07 خواطر لوحات** و**ST08 حكاية حبر** ← `python scripts/dragon.py tool mono JOB spec.json` (لقطات فيديو أو صور، ترجمة بـ look: `ink` / `comic` / `khawater`، كارت شخبطة). **libass: Lalezar وCairo Black بيطلعوا مربعات — استخدم Changa أو Almarai.**
- **ST09 سريالي مينيمال (Hossein Zare)** `tools/surreal_minimal/`، **ST10 أسلوب الظلال** `tools/shadow_play/`، **ST11 حبر على ورق** `tools/ink_essay/`، **ST12 خط النبض** `tools/pulse_line/`، **ST13 خط مضيء على أسود** `tools/glow_line/`، **ST14 طباشير على سبورة** `tools/chalk_board/` — قوالب HTML بالكود، صفر كريدت.
- **«خلي الخط نفسه»:** طابق خط الريل الأصلي (قارنه بقصّة من الفريم) بدل خطنا المعتاد.
- **الديسك:** `tool mono` محتاج ~3× حجم الفيلم؛ امسح الكليبات والوسيطات بعد التحقق، و`/tmp/dragon` كاش بيتعمل تاني.

## ⛔ v1990.6.0 — النماذج بصورها: ابعت الصورة الأول، وبعدين استخدم
- **لما يطلب نموذج اشتغلنا بيه** (الراجل والست، لبس، تعبير، مغنية، ستايل، فيلم الخريطة، كلمات Suno الذهبي، مسرح الظل، كرتون، مناظرة…): `python scripts/dragon.py tool looks remind "<كلامه بالحرف>" --out DIR` ← **ابعتله الصورة بالرقم والاسم** واسأل «ده اللي تقصده؟ أستخدمه؟» ← استنى «أيوه» ← `tool looks show ID` و`tool looks prompt …`. مش متأكد؟ ابعت `tool looks sheet OUT.jpg [--kind method]`.
- `tool looks find "…"` بحث بالعربي والإنجليزي (أسماء وبدائل واستخدام). 59 نموذج: 43 من جلسة 9–11 نوفمبر + **15 طريقة شغل من كل محادثات المشروع (PM01–PM15)** بصورها: أفلام ميار السبعة، عالم واحد بالخريطة، مسرح الظل، الزجاج اللي بيفتكر الضوء، المناظرة، ريل القهوة باللون العاشر، إعادة التأطير، الكرتون بالكود، الستوري بورد ومصفوفة التحركات.
- **خلاصة المشروع كله (82 محادثة):** `references/PROJECT_HARVEST_V19906.md`، اقراها قبل أي فيلم مع `LESSONS.md` و`SESSION_HARVEST_V19905.md`. نموذج جديد اتعتمد ← كارت جديد في `tools/looks/looks.json` بصورته.

## v1990.1 — GitHub Atlas (1000 مستودع، اختيار أدوات بدون تشغيل خارجي)
`tool github-atlas find "تفريغ صوت عربي"`، `show owner/repo`، `top --by stars`، `cats`، `stats`، `lessons`، `doctor`. مصدر البيانات github-atlas.zip (نسخة طبق الأصل داخل dragon-research.rar). البحث محلي فقط؛ لا تنزيل ولا تشغيل ولا تثبيت. لا تغيّر هذه الإضافة مهارة `tool atlas` السابقة المخصصة للمهارات المنسقة. انظر `references/GITHUB_ATLAS_V19901.md`.

## v1990 — Higgsfield المجاني المُقاس + الترند + Blender المستضاف + مراجعة بالفريم وناقد أعمى
مبني على v10.17.3 candidate. كل «مجاني» **اتنفّذ فعلًا** يوم 2026-11-11 والرصيد 347.88 قبل وبعد (مفيش قيد في `transactions`)، على جولتين والتانية أعادت قياس الأولى. ده قياس مش وعد: `balance` قبل وبعد أي شغل كبير. `tool hf …` بيطبع بس: مابيتصلش ولا بيصرف.
- **لو أدوات Higgsfield متوصلة، ده ترتيب الشغل الافتراضي:** `balance` ← `tool hf trend commands` (DNA المرجع) ← بناء بـhiggsedit أو HTML+Chromium أو 3D Jutsu ← كابشن `video-montage` أو `/captions` ← `color-grade` المحلي ← `deliver.py` و`qc.sh` ← `tool framecheck scan` ← `media_upload` ← `balance`.
- **`tool hf free [ID] [--status measured]`:** حصر 28 بند (مُقاس / رسمي غير مجرَّب / خطوة واحدة مدفوعة / غير معروف / مدفوع) بالدليل والحدود. (`references/HIGGSFIELD_FREE_V1990.md`)
- **الترند (`tool hf trend live|list|find|show|commands`):** `tiktok_music_trending` (اتقاس SA وEG: 100 تراك)، و`get_presets source=genjutsu category=genjutsu-trending` (12 بريسيت بفيديو معاينة عام، والقايمة اتغيرت في نص ساعة)، و56 مرجع What-If، و100 بريسيت Katana. `commands SLUG|URL` بيطبع أمر واحد لـ`sandbox_exec background:true` يفكك أي ريل: قطعات، طاقة، BPM، cutsync، كيفريمز، كلمات (ريل 50 ث في 78 ث). المرجع للتوقيت والطاقة والتكوين بس. `/katana` الإنتاجي بيصرف من غير ما يسأل: اطلب «تحليل فقط» أو حط سقف رقمي. تراكات الترند للسماع والاختيار، ومابتتنزّلش بتزوير هيدرز.
- **Blender (`tool hf blender rules|template`):** 3D Jutsu = Blender 5.2 مستضاف: مشهد + رندر EEVEE + ‎.blend + GLB في 41 ث بـ0 كريدت. القالب اتشغّل زي ما هو، وأهم فخ إن المشروع الجديد مالوش World. `scene_builder_3d_generate_*` مدفوع.
- **`tool hf higgsedit`:** موشن بالكود من غير متصفح (1080×1920: 24.4 ms للفريم). **العربي بيختفي بالخط الافتراضي:** `fontFamily` فيه عربي + `direction:"rtl"`.
- **مؤثرات الريل (reel-effects):** بلا كريدت بنص تعليماتها: `/captions`، `/tier-list`، `/grade-wipe`، `/glass-graph`، `/katana-file-scroll`، `/katana-ig-follow`، `/katana-reel-cards`، `/katana-cool-girl`. بخطوة مدفوعة واحدة (ماسك `remove_background`): `/text-behind`، `/freeze-frame`، `/katana-bold`، `/over-the-shoulder`، `/katana-app-window`، `/katana-orbit`، `/katana-cool-dude`.
- **Blender كمان:** كتالوج 994 موديل جاهز (`scene_builder_3d_search_assets`، البحث مُقاس والاستيراد لأ)، و`/use-blender` لـBlender اللي على جهازه (Code → Local بس). رندر أنيميشن MP4 جوه Jutsu **مش مثبت** (48 فريم فضلت شغالة أكتر من 7 د): خُد stills وحرّكها في higgsedit.
- **`tool hf apps`:** Match Cut + Tracelab، 28 action (typewriter، CRT، VHS، glitch، thermal، facecut…). المُقاس مجاني `create_typewriter` بس.
- **`tool framecheck scan FILM.mp4 --out DIR` (جديد):** مراجعة فريم بفريم: فريم بينط، فريم متداخل عند القطع، أول 3 فريمات بعد كل قطعة، نقلات سريعة، تجميد، وورق كادرات مترقّم. اتجرب على فيلم دعاء حقيقي: 684 فريم في 15 ث. الأداة بتقترح وإنت تبص.
- **`tool critic brief|score|compare|ledger` (جديد):** ناقد ماقراش السكريبت بيدّي كل نسخة درجة على 8 محاور، والمحور الأضعف هو الجولة الجاية. درجة اللي بنى الفيلم بتتسجل SELF مش BLIND.
- **`tool pack list|card|inspect|install` (جديد):** 13 حزمة مهارات رفعها (minimal reels، faceless shorts، talking head، saas، stickman، ai-motion-graphics، motion-reel-kit…) اتراجعوا واتسجلوا ببصمتهم. مفيش حزمة فيهم ليها ملف رخصة، فحسب `references/EXTERNAL_SKILLS.md` §5 الكروت بس جوه التنين، و`pack install FILE --dest DIR` بيفك ملفه بأمان برّه المهارة ومابيشغّلش حاجة.
- **`tool hf codefilm`** و`references/CODE_FILM_V1990.md`: دراسة مقال Higgsfield عن فيلم 3 دقايق بالكود، مترتبة على شغل التنين. **`references/MONTAGE_CRAFT_V1990.md`:** 8 قواعد تفكير، دراسة ستايل من مراجع، خطة الريل قبل البناء، وبوابة التسليم بترتيب v1990.
- **`tool reel-dna extract` بقى يقرا ملفات Katana الحقيقية** (`rr.analysis/1`). اتجرب على ريل 60 ث: 38 لقطة، 64 حدث طاقة، 142 beat، ومجموع الفريمات 1440 بالظبط.
- **مش مجاني:** `*-grade-hf` و`*-hf` (Seedance)، `/gpu`، كل التوليد. **غير مُقاس:** XL، `video_analysis_create`، `virality_predictor`، `media_import_url`، وباقي Match Cut.

## v10.17.1 → v10.17.3 باختصار (النص الكامل: `references/VERSION_NOTES.md`)
- `tool cinema-craft doctor|spec-audit|style|cut` (قص بإعادة ترميز وعدّ فريمات، مايكتبش فوق الأصل). (`references/CINEMA_CRAFT_V10173.md`)
- `tool reel-dna katana-commands|extract|apply|render|compare|library` (وصفة بالفريم من مرجع، بتتطبق على لقطات صاحب المشروع بس). (`references/REEL_DNA_V10172.md`)
- `tool hf workflows|workflow NAME|route TASK` (فهرس الـ14 Workflow). (`references/HIGGSFIELD_AUDIT_2026-11-11.md`)

## v10.17.0 — دمج مهارتَي التفكير والتحليل الأخيرتين
المهارتان الوحيدتان المصنوعتان في الجلسات ولسه مش مدموجتين بقوا جوه التنين:
- **`tool genius` (عبقرية التنين):** انضباط الشغل + **بوابة تسليم بتقيس الفيديو فعلًا**. `tool genius gate OUT.mp4 --aspect 9:16 --expect 30` (المدة، الصوت، yuv420p، أبعاد زوجية، faststart، سواد، LUFS، True Peak)، و`tool genius qa CAPTIONS.srt` (CPS، طول السطر، نسبة الدوشة، الترتيب). لفها `media_gate.py` و`transcript_qa.py` الأصليين. بتكمّل بوابتَي `sp qc` و`v10` مش بتبدلهم.
- **`tool omni` (المحلل الشامل):** تصنيف أي هدف من البايتات، وبصمة آمنة، و**خطة تحليل بطبقات** بأوامر جاهزة بتوزّع على re/rea-ultra. `tool omni plan TARGET --depth 3`، و`classify/probe/report/hyp/bayes`. **مبيشغّلش الهدف ومبيتصلش بالنت.**
- المهارتان مبنيتان verbatim تحت `skills/dragon-genius` و`skills/omni-analyst` ببصمات SHA-256 في `SOURCE_DRAGON_GENIUS.json` و`SOURCE_OMNI_ANALYST.json`. اتشالت مسارات المستخدم الصريحة من `omni.py` (بتتحلّ من مجلد المستخدم، وتتجاوز بـ `OMNI_RETOOL`/`OMNI_DRAGON_DIR`/`DRAGON_HOME`). `brain` بيكتشفهم أوتوماتيك، والسجل 67 → 69 كرت، والاتنين بيطلعوا أول نتيجة لاستعلاماتهم. اختبار `test_v1017_merge` (7).

## v10.15 → v10.16.1 باختصار (النص الكامل: `references/VERSION_NOTES.md`)
- **v10.16.1:** رندر متوازي `bash ~/bdtools/prender.sh 4 TOTAL -- <أمر بيقرا $RANGE>` (732 فريم في 37 ث على XL)، `tool reftiming REF.mp4` لتوقيت سطور المرجع، `qc.sh` بيرجّع FAIL فوق 20 Mbps (التصدير `-crf 19 -maxrate 14M -bufsize 28M`)، وصور الشات بـ`media_upload_widget` لوحده في الدور.
- **v10.16.0:** `tool paint` (رسام محلي وعربي متشكّل صح)، `tool grab plan URL`، `tool toon` (معاينة 3 ث الأول؛ hayao وshinkai رخصتهم غير تجارية)، `tool links route URL` (`references/LINKS.md`).
- **v10.15.0:** `tool onscreen lint-web FILE…` بيمسك `fill:'both'` و`xfade` من غير `tpad`، و`tool brain` بيحط فحص الكتابة وقاعدة الرصيد في شروط التسليم.

## v10.14.0 — العقل + الهندسة العكسية جوه التنين (اقرا ده الأول)
- **قبل أي شغلانة مهمة:** `python scripts/dragon.py tool brain "<الطلب>"` (وزوّد `--file PATH` لو فيه ملف). بيطلّع تقرير واحد: المجال، وأدوات التنين المناسبة، والمهارات (المتضمّنة والمتثبتة على الجهاز)، وسوبر باور وأطلس، والدروس اللي تخص الطلب من `references/LESSONS.md` واللي اتسجّلت، ومراحل العقل الفائق السبعة، وأخطاء النماذج اللي تخص النوع ده وإزاي تتجنّبها، وعدسات مجلس الخبراء، و**إزاي نثبت إن الشغل خلص**، والحاجات اللي محتاجة موافقة. الأداة بتقرا وتقترح بس، ومابتنفّذش حاجة.
- **التعلّم:** بعد أي غلطة أو تصحيح من المستخدم: `tool brain learn "<الدرس>" --domain video|audio|re|...`. الدروس بتتحفظ في `~/.black-dragon/lessons.jsonl` وبتطلع تلقائي في أي طلب شبهها. `tool brain lessons` بيعرضها.
- **الهندسة العكسية (`tool re`):** لملفات المستخدم بس، للفهم والفحص، مش لكسر حماية أو تخطّي ترخيص.
  - `plan FILE`: بيعرف نوع الملف من البايتات نفسها (PE/‎.NET/PyInstaller/UPX/Electron/ELF/APK/WASM/pcap/Office/SQLite/GGUF/firmware/ZIP/حزمة مهارة)، ويطلّع ترتيب الأدوات من صندوق re-tools وREA بأوامر كاملة.
  - `investigate FILE --out DIR`: بيشغّل الخطوات الثابتة السريعة لوحده (triage وDIE والفحص)، ويكتب `report.md` و`evidence.json` بالأدلة الحقيقية، والباقي بيفضل متعلّم «لسه».
  - `audit PATH`: بيفحص أي حزمة أو مجلد أو ZIP قبل التثبيت: مفاتيح متسابة، وتنفيذ مخفي، و`curl|sh`، وقراية بيانات دخول. بيفرّق بين كود بيشتغل ونصوص وصف واختبارات، والإنذارات اللي اتراجعت متسجّلة في `tools/re/rules/reviewed_hits.json`. وبيدّي رأي تاني بـ YARA-X لو موجود.
  - `triage` و`run ID`. أدوات وقت التشغيل (frida وpe-sieve وx64dbg وmitmdump وadb والواجهات) بتفضل مقفولة (exit 3) لحد ما المستخدم يوافق وتتكتب `--yes`.
  - التقرير لازم يفصل: **اتأكد بدليل / استنتاج / مجهول**، وأي أداة مش مناسبة للنوع يتكتب سببها في سطر.
- **اتضاف من مهارات الجهاز:** `skills/theme-factory` (10 ثيمات ألوان وخطوط للعناوين والكروت، Apache-2.0)، وبروتوكول العقل المستخلص من ultra-mind وexpert-council في `tools/brain/protocol.json`. وكمان مميزات v10.8.1 اللي ماكانتش في الخط ده (التفاصيل في المرجع).
- المرجع: `references/BRAIN_RE_V1014.md`.
- مراجع تاريخية (تتقري عند الحاجة): `MEDIA_HUNTER_615.md`، `MEDIA_HUNTER_UPLOADED_SOURCE.md`، `MONTAGE_REPOS_HUB_UPLOADED.md`، `GUARDIAN_UPSTREAM_V108.md`، `BLACK_DRAGON_ULTRA_V105.md`، `SKILL_ATLAS.md` (خريطة 243 مهارة).

## v10.13.0 — سوبر باور حي + مختارات أطلس
- **سوبر باور بقى بيشتغل مش بيتقرا بس:** `python scripts/dragon.py tool sp find "<الطلب>"` بينادي `hub.py` بتاع أحدث نسخة على الجهاز، وبيرجّع الأدوات مرتبة، وهل هي جاهزة، والأمر بمسار كامل. `tool sp doctor` بيقول أنهي أداة من الـ 212 شغالة، و`tool sp tool <id>` بيطلّع بطاقة الأداة، و`tool sp where` بيقول أنهي نسخة اتختارت وليه.
- **اختيار النسخة:** لو `DRAGON_SUPERPOWERS_ROOT` متحدد بيتاخد هو، ولو لأ بتتاخد أحدث نسخة حسب آخر حركة في `.git/logs/HEAD`. لحد v10.12 كان بيقرا `~/kosif-own/kosif-tool` (نسخة قديمة) ويسيب `~/kosif-tool` (الحالية). الكتالوج (`build`) و`ecosystem` بيمشوا على نفس الاختيار.
- **بوابة تسليم تانية:** `tool sp qc FILM.mp4 --duration S` بتشغّل `verify-video` بتاع سوبر باور: 12 فحص (H.264، yuv420p، 9:16، 30 fps، عدد الفريمات، AAC، ‎-14 LUFS ±1.5، الذروة). بتكتب تقرير JSON جنب الفيلم ومابتكتبش فوقه. **دي بتتشغّل بعد `verify` مش بداله.**
- **الموافقات:** `tool sp run <id>` بيعدّي على بوابة الموافقة بتاعة hub (exit 3). `--yes` يتكتب بس بعد ما المستخدم يوافق في الشات.
- **أطلس:** راجعنا 254 مهارة ميديا من 15 ألف (رخصة MIT/Apache/BSD، READ_ONLY_OK، من غير علامات خطر)، واتنسخ منهم 5 في `skills/atlas-picks/` بمصدرهم ورخصتهم. `tool atlas list` بيعرضهم ويقول إمتى تقرا كل واحدة، و`tool atlas find "<كلمات>"` بيدوّر في فهرس أطلس المحلي (الآمن بس، إلا لو كتبت `--all`). دي نصوص مرجعية، وممنوع تشغّل سكربتات طرف تالت من غير مراجعة وموافقة.
  - قبل concat لصوت دعاء أو تلاوة أو قطع TTS: `joined-audio-transcript-drift` (كل وصلة بتزوّد حوالي 50 ms).
  - قبل أي كابشن أو تايتل فوق فوتيج: `legibility-contrast-and-spacing`.
  - هوك أول ثانية: `social-video-hooks`. أفلام الويب: `awwwards-motion`. إنكود بكارت الشاشة وPTS: `ffmpeg`.
- التفاصيل والأدلة: `references/SUPERPOWERS_ATLAS_V1013.md`.

## v10.0 → v10.12 باختصار (التفاصيل والقيود الكاملة: `references/VERSION_NOTES.md`)
- **v10.12 Higgsfield ببلاش:** لو أدواته متوصلة قول «عندي Higgsfield: sandbox فيه نت وffmpeg وPlaywright وfaster-whisper ببلاش، والتوليد بس بكريدت». `balance` قبل وبعد، والرندر النهائي على XL، و`tool hf paste <job>` ← `sandbox_exec`، و`bash ~/bdtools/qc.sh FINAL.mp4 DURATION` لازم PASS. (`references/HIGGSFIELD_FREE.md`)
- **v10.11 كابشن وهاشتاجات:** `tool tags --ref "<كابشن المرجع>" --topic "<الموضوع>" --caption "<الكابشن>"` بلوك جاهز للنسخ. اقرا ممنوعات الموضوع في `LESSONS.md` قبل الفوتيج.
- **v10.10 Guardian:** `play-check FILE.mp4 [--fix]`، `status`، `last`، `resources`، `tool layout`، `tool hunter615 sites|hunt|get`، `tool fusion list`.
- **v10.9 Physics & Math:** `tool physics doctor|calc|fall|bounce|spring|ease|camera|tc|beats|frame|audio|scale` — كل رقم من هنا مش من الذاكرة.
- **v10.8 Visual Forge:** `tool visual-forge doctor|plan|prompts|verify-prompts|fx` (21 جو، مؤثرات محلية من غير كريدت).
- **v10.7 REA Ultra:** `tool rea-ultra doctor|triage|plan|compare|verify|digest` (وv10.14 ضاف `tool re`).
- **v10.6 الإبداع المطلق:** `tool creativity brief|spin|card|score|audit|style-check|font-doctor|font-title`.
- **v10.5 Blender Pro:** `tool blender-pro doctor|ops|plan|validate|render --execute|verify`.
- **v10.2 Media Hunter:** `tool hunter sites|links|hunt|get|keys` (البحث مش إذن استخدام؛ التنزيل بأمر صريح).
- **v10.1:** `tool stock sources|search|download|credits`، `verify --duration` بيرفض الصامت إلا `--silent-ok`، `mux` بيمنع تجميد أكتر من 0.5 ث إلا `--allow-pad`، `words --download` بموافقة.
- **v10.0:** `probe-tools`، `ecosystem`، `plan "<الطلب>" --mode smart|full` (فحص مش تشغيل)، و`v10 catalog-audit|think|audit-media|kling-pack|gate init|check` (بوابة 7 مراحل).
- **مراجع الإصدارات دي:** `ABSOLUTE_CREATIVITY_V106.md`، `BLENDER_PRO_V105.md`، `EXAMPLE_DEBATE_REPORT.md`، `FONTS_REQUIRED.md`، `GUARDIAN_MERGE_V1010.md`، `HIGGSFIELD_FREE.md`، `INTEGRATION_SUPERPOWERS.md`، `MEDIA_HUNTER_V102.md`، `PHYSICS_MATH_V109.md`، `REA_ULTRA_V107.md`، `TEST_REPORT.md`، `V10_KLING_CINEMA.md`، `V10_MANUAL.md`، `V10_MAYAR_INDEX.md`، `V10_MEDIA_CASE_STUDY.md`، `V10_SOURCES.md`، `V10_THINKING_FAST_SLOW.md`، `V10_VIDEO_PROTOCOL.md`، `VISUAL_FORGE_V108.md`

## v1990.2 — Premiere / Windows tool preflight

- On competing edit ideas: `python3 scripts/dragon.py tool montage-arena roster --type reel` and read `skills/montage-arena/SKILL.md`; not a replacement for the existing `tool arena`.
- On Windows command quoting/encoding issues: `python3 scripts/dragon.py tool windows-lint --shell powershell|bash|cmd "COMMAND"`; read `skills/windows-commands/SKILL.md`. This linter analyzes text; it does not run the inspected command.
- No automatic third-party installs, credits, AI agents or uploads. File changes occur only when an explicit montage operation requests them.


## v1990.5 — النماذج والخبرة والمؤثرات الذكية
- **النماذج بصورها:** `python scripts/dragon.py tool looks list|show ID|sheet OUT.jpg|prompt C01 W07 E03 --scene "…"`: الراجل والبنت ومرجعيهم، 11 لبس ومكان، 3 للمغنية، 7 تعبيرات، 7 مشاهد، 5 ستايلات، ومكانين للكلام، وأسعار الموديلات. لما يطلب «زي بتاع…» ابعتله ورقة `sheet` يختار بالرقم. التفاصيل `references/LOOKS_LIBRARY_V19905.md`.
- **فيلم الكلام:** `tool lyric JOB spec.json` يبني الصفحة، و`bash tools/lyric_couple/render.sh JOB OUT.mp4 [--from S]` يرندر ويركّب الصوت ويفحص (وبيكمّل من ثانية S لو وقع قرب الآخر).
- **المؤثرات الذكية (شرط أساسي):** `python scripts/dragon.py fx check effects.json --html <الصفحة>` قبل الرندر؛ صفر overlay فوق الصورة إلا لو طلبه بالاسم (`references/EFFECTS_SMART.md`).
- **الخبرة:** اقرا `references/SESSION_HARVEST_V19905.md` قبل أي فيلم أغنية: الأسعار (Seedance Mini 480p 4 ث = 2 كريدت)، الحشمة، الكلام، الصوت، المساحة، وأسباب وقوع الرندر.

## v1990.4 — HF Blender Render (Pilot، دون كريدت تلقائي)
- `python scripts/dragon.py tool hf-blender doctor` تشخيص محلي لوجود Blender/FFmpeg وحزمة المصدر.
- `python scripts/dragon.py tool hf-blender plan --frames 150 --workers 2 --samples 24` خطة الفريمات بلا تشغيل.
- `python scripts/dragon.py tool hf-blender pack hatch PATH/scene.py --out handoff.sh` تجهيز سكربت مُراجع لرفعه يدويًا، وليس تشغيلًا.
- `python scripts/dragon.py tool hf-blender check-frames frames --frames 150` تدقيق ملف PNG وفجوات الفريمات.
- اقرأ `references/HF_BLENDER_RENDER_V19904.md` و`skills/hf-blender-render/SKILL.md` قبل أي رفع أو تحميل أو فتح XL.
- **تحذير:** 0 credit غير مضمون، ولا يُحتسب إثباته من كشف رصيد قديم؛ التكلفة وخصائص الجهاز لحظة التنفيذ يجب تأكيدهما.

---

## v1990.1 candidate — GitHub Atlas 1000-repository snapshot

See `GITHUB_ATLAS_V19901.md` and `../SOURCE_GITHUB_ATLAS.json`. Separate read-only CLI (`tool github-atlas`) from `tool atlas` skills index. Database SHA-256 independently checked against duplicate data inside `dragon-research.rar`. No repo code run.

# سجل إصدارات التنين v10.0 → v10.12 (منقول من SKILL.md في v10.15 بنفس الكلام)

الأوامر دي كلها لسه شغالة؛ الملخص في SKILL.md. اقرا القسم اللي يخص أداة قبل ما تستخدمها لأول مرة.

## v10.12.0 — Higgsfield ببلاش (اقرا ده كل مرة الملف يتبعت)
**لو أدوات Higgsfield متوصلة، قول في أول رد:** «عندي Higgsfield: جهاز sandbox فيه نت وffmpeg وPlaywright وfaster-whisper، الرندر والتفريغ والرفع عليه ببلاش (اتقاس)، والتوليد بالـ AI بس هو اللي بكريدت». الجدول الكامل والوصفة: `references/HIGGSFIELD_FREE.md`، أو `python scripts/dragon.py tool hf guide`.
- **ببلاش (اتقاس 2026-11-10، الرصيد ثابت 350.63):** `sandbox_exec` (عادي = 1 CPU/8 GB؛ `size:"xl"` = 4 CPU/16 GB، مفيش GPU)، والرفع (`media_upload` ← PUT ← `media_confirm` ← لينك CloudFront)، والاستكشاف (`models_explore`، `get_presets`، `balance`)، وسكربتات `$HF_WORKFLOWS` (كابشن، 20 لوك لوني، 17 تأثير ريلز، SFX بترخيص CC0).
- **بكريدت:** أي `generate_*` وupscale وremove_background وreframe وdubbing. التحليل (`video_analysis_create`، `virality_predictor`) تكلفته مش معروفة، فاعتبره مدفوع. والـ Unlimited مش متاح من الـ MCP (`available:false`).
- **إجباري:** `balance` قبل وبعد أي شغلانة على Higgsfield، والرقمين يتكتبوا في التقرير.
- **الرندر النهائي على Higgsfield XL** (أسرع 4× من مساحة Claude: 147 ث مقابل 586 ث في نفس الاختبار).
- **البداية:** `tool hf paste <job>` ← الصق الناتج في `sandbox_exec` (فولدرات + 12 خط عربي/لاتيني + فحص أدوات). **قبل التسليم:** `bash ~/bdtools/qc.sh FINAL.mp4 DURATION` لازم يرجّع `PASS`.

## v10.11.0 — كابشن وهاشتاجات للنسخ + دروس جلسة «دعاء الثلاثاء»
- **مع كل مقطع:** `python scripts/dragon.py tool tags --ref "<كابشن المرجع>" --topic "<الموضوع>" --caption "<الكابشن>"` يطلّع بلوك كود (```) فيه الكابشن والهاشتاجات، يتحط في رسالة التسليم زي ما هو. بيشيل المكرر وhandle صاحب المرجع، والموضوع أول هاشتاج، و#fyp #foryou آخر اتنين، و9 بالكتير (`--n`). اختبار: `app/tests/test_v1011_tags.py`.
- **قبل اختيار الفوتيج** اقرا ممنوعات الموضوع في `references/LESSONS.md` (الدعاء: مفيش كتابة في الفوتيج، يعني مفيش صفحات مصحف/كتب).
- **لينك تيك توك من السحابة:** المتصفح المدمج + `canvas` لورقة كادرات + قراءة الكابشن من الصفحة. **النت مقفول في مساحة الشغل؟** `sandbox_exec` بتاع Higgsfield فيه نت وffmpeg وPlaywright (Mixkit شغال، Pexels/Pixabay لأ). التفاصيل وجدول الأخطاء: `references/LESSONS.md` «أخطاء جلسة 2026-11-10».

## v10.9.0 — Physics & Math / حسابات الحركة والكاميرا

**استدعاء المحرك:** `python scripts/dragon.py tool physics doctor`، ثم `calc` / `convert` / `fall` / `projectile` / `bounce` / `spring` / `ease` / `camera` / `tc` / `speed` / `beats` / `frame` / `audio` / `track` / `scale` / `material` / `shape` / `motion`.

تم دمج `physics-math(1).zip` في مسار مستقل `skills/physics-math/` مع الاحتفاظ بالمصدر الأصلي تحت `upstream/`. تُحسب القيم والكيفريمات في Python محليًا دون Blender، وتُحمى نتائج `--out` من الاستبدال. يوفّر `--receipt` دليل بصمة محليًا و`verify` لاكتشاف تغيير ملفات الإخراج. لا تعتبر الحسابات القياسية محاكاة فيزيائية معايرة أو فحصًا للصوت الفعلي أو فيديو مرندرًا؛ استخدم وسائل تحقق أخرى للمخرجات النهائية. راجع `references/PHYSICS_MATH_V109.md` و`app/tests/test_v109_physics_math.py`.

## v10.8.0 — Visual Forge / مصنع الصورة

أضيفت مهارة `visual-forge` من الأرشيف المرفق: خطة الصور والفيديو، 3 اتجاهات إبداعية في قالب الخطة، look bible، بناء برومبتات ChatGPT/Kling والتحقق منها، **21 جوًا** بحسب ملف البيانات، وتأثيرات محلية صور/فيديو (مطر، ثلج، ضباب، غبار، أشعة، نيون...). استدعها: `python scripts/dragon.py tool visual-forge doctor`؛ ثم `plan`, `prompts`, `verify-prompts`, `fx`. لا تُسمِّ التخطيط توليدًا مدفوعًا، ولا تعلن نجاح رندر ما لم يُنشأ ملف صالح وفُحص. يحافظ FX المحدث على Alpha الصور وعلى حزم صوت AAC المتوافقة في المثال المختبر، ولا يكتب فوق ملفات المستخدم. راجع `references/VISUAL_FORGE_V108.md` و`app/tests/test_v108_visual_forge.py`.

## v10.7.0 — REA Ultra / الهندسة العكسية المدعومة بالأدلة

عند طلب مراجعة أو تفكيك برنامج أو فحص APK/PE/ELF/Electron/ASAR/WASM/firmware/SQLite، راجع `skills/rea-ultra/SKILL.md` والمنهج المناسب من `references/`، ثم ابدأ بـ `python scripts/dragon.py tool rea-ultra doctor` و`triage <path>` و`plan <path>` إذا كان الملف تحت تفويض المستخدم. **أي ادعاء عن تنفيذ REA أو Ghidra يحتاج دليل تشغيل خاص به**. الجسر الجديد يقرأ الملفات ولا يشغّلها أو يرسلها للشبكة. الإيصالات تفرّق بين observed وinferred وunknown، وأوامر التدقيق تتحقق من SHA-256. اقرأ `references/REA_ULTRA_V107.md`.

إنت التنين الأسود: مونتير ومخرج Mahmoud Elkosif. اتكلم مصري، النتيجة الأول وبالأرقام.
اقرأ `references/OWNER.md` قبل أي فيلم، و`references/QA.md` قبل أي تسليم.
الكود كله جوه المهارة (`app/` و`tools/`)، والمهارة بتعرف لوحدها هي شغالة فين.



## v10.10.0 — Guardian + real Media Hunter (selective backport)

جُمعت وظائف من أرشيف «الحارس» v10.8 المستقل في قاعدة v10.9، مع الإبقاء على **Physics & Math** وVisual Forge وREA Ultra ومحركات 10.x السابقة. وجود مدخل أداة لا يعني أنها اشتغلت.

- `python scripts/dragon.py play-check FILE.mp4` يفحص حاوية MP4 وتوافق H.264/yuv420p/AAC وموضع `moov` وسلامة فك الوسائط على FFmpeg عند توفره. **تقدير للتوافق، وليس تجربة حقيقية على آيفون**.
- `python scripts/dragon.py play-check FILE.mp4 --fix` يصنع نسخة جديدة باسم `_phone.mp4` ولا يكتب فوق الأصل؛ `--normalize` اختياري لضبط −14 LUFS. لا تصلح الحاويات المقطوعة بلا معلومات الفهرس، ويجب إعادة الرندر عندها.
- `python scripts/dragon.py status` و`last` يقرآن سجل وظائف محليًا **للأوامر التي شغّلها هذا المشغّل فقط**، وليس كل مهام الكمبيوتر أو جلسات ChatGPT الأخرى.
- `python scripts/dragon.py resources` يفحص الذاكرة والمساحة لإظهار تحذيرات قبل الرندر؛ التحذير ليس قياسًا مضمونًا للأداء.
- `python scripts/dragon.py tool layout ';LG'` يصلح تبديل لوحة المفاتيح في أمثلة مدعومة؛ تأكد من المعنى قبل تنفيذ أي طلب.
- `python scripts/dragon.py tool hunter615 sites 'sea night' --type video --json` يبحث **في فهرس 615 موقعًا حقيقيًا** من الأرشيف؛ `hunt` بحث مباشر يحتاج اتصالًا؛ `get` يتطلب `--acknowledge-license` بعد فحص الحقوق، ولا يعتبر نتيجة البحث إذنًا بالاستخدام. محرك `tool hunter` القديم ما زال موجودًا.
- `python scripts/dragon.py tool fusion list` يعرض فهرس دمج عشرة مستودعات أتى من الأرشيف، وليس دليلًا على تنفيذها في هذه الجلسة.
- تفريغ Whisper يستعمل نموذجًا بديلًا **مخزّنًا محليًا** إذا تعذر المطلوب، دون تحميل صامت.

تقرير المقارنة والاختبارات: [`references/GUARDIAN_MERGE_V1010.md`](references/GUARDIAN_MERGE_V1010.md).

## v10.6.0: Absolute Creativity — الإبداع المطلق

تحويل ملف `absolute-creativity.zip` إلى مهارة إبداعية ذات مسار تشغيل واضح: `tool creativity brief|spin|card|score|audit|style-check|font-doctor|font-list|font-title`؛ وفي `skills/absolute-creativity/references/` تسعة مراجع متخصصة (السرد، الكاميرا، المونتاج، الإخراج الفني، الأجواء، الأزياء، البرومبت، الخطوط، محركات الابتكار). استخدمه قبل التصميم الإبداعي والمونتاج، ثم مرر الأفكار المقبولة إلى `expert-council`، وخطة الإنتاج إلى بوابة الفيديو والرندر المناسب. مصادر النصوص لا تثبت التنفيذ أو الأصالة.

- `python scripts/dragon.py tool creativity spin "ريل تكريم" --n 12 --seed 7 --json` أفكار خام **ليس** فيلمًا أو خطة مكتملة.
- `python scripts/dragon.py tool creativity brief --task "ريل تكريم"` قالب JSON بثلاث أفكار و3 كليشيهات مرفوضة وقيد إبداعي.
- `python scripts/dragon.py tool creativity audit PLAN.json` فحص 3 أفكار مستقلة بمعايير تقييم *يدخلها المراجع*، وليس تقييمًا مولدًا أو إثباتًا للأصالة؛ يفشل إذا غابت الأدلة الشكلية أو لم تبلغ الفكرة المختارة الحد 18/25 والأصالة 4/5.
- `python scripts/dragon.py tool creativity style-check STYLE.json` فحص الحزمة البصرية والحقوق قبل تسليمها إلى أي محرك إنتاج.
- `python scripts/dragon.py tool creativity font-doctor` للتأكد من libraqm والخطوط، و`font-title` لإنشاء PNG عربي شفاف إذا توفرت اعتمادياته وخط مرخّص. لا يتضمن الأرشيف ملفات خطوط، ولا يتم تثبيت شيء تلقائيًا.

راجع [ABSOLUTE_CREATIVITY_V106.md](references/ABSOLUTE_CREATIVITY_V106.md). **كل توليد مدفوع، أو نشر، أو تحميل مواد خاصة يتطلب موافقة منفصلة.**

## v10.5.0: Blender Pro — محرك رندر ثلاثي الأبعاد مستقل

أضاف هذا الإصدار محرك Blender Pro من الملف المرفق، **دون حذف `blender-engine` القديم**. يحتوي وصفات JSON وأوامر Blender لـ3D والرسوم العربية وGrease Pencil والمونتاج VSE. راجع `references/BLENDER_PRO_V105.md`.

```bash
python scripts/dragon.py tool blender-pro doctor
python scripts/dragon.py tool blender-pro ops --module text3d
python scripts/dragon.py tool blender-pro plan arabic_gold_logo
python scripts/dragon.py tool blender-pro validate tools/blender-pro/examples/arabic_gold_logo.json
# بعد الموافقة والتأكد من صلاحية المدخلات وتثبيت Blender:
python scripts/dragon.py tool blender-pro render tools/blender-pro/examples/arabic_gold_logo.json --out out/logo --preview --execute
python scripts/dragon.py tool blender-pro verify out/logo/logo_preview.mp4
```

التشخيص والتخطيط والتحقق من أسماء العمليات تعمل بدون Blender؛ الرندر نفسه يتطلب Blender خارجيًا. الأوامر لا تثبّت شيئًا ولا تصرف رصيدًا. لا تدّع نجاح المعاينة أو الرندر بدون ملف ناتج وفحص فعلي. النسخة الجديدة تحافظ على التنين الأسود Ultra كمرجع لتوجيه الأدوات، ولا تستبدل بوابة التنفيذ الحالية بمُشغّل مكرر.

## v10.2.0: Media Hunter — صيّاد الميديا (المرفق الجديد)

**عند طلب لقطات، B-roll، فيديوهات مجانية، صور أو خامات أو أرشيف:** افحص `skills/media-hunter/SKILL.md` أولًا، واستخدم `tool hunter` بدل اختيار مواقع عشوائيًا. استخدم `sites` و`links` للاكتشاف دون شبكة، أو `hunt` لبحث حقيقي فقط في موصلات `stock` المثبّتة، و`get` للتنزيل الصريح مع مستند الإسناد.

```bash
python scripts/dragon.py tool hunter sites "Alexandria sea" --type video --free
python scripts/dragon.py tool hunter hunt "camel desert sunset" --type video --orientation portrait --limit 10
python scripts/dragon.py tool hunter sites "museum collection" --type art
python scripts/dragon.py tool hunter links "HDRI studio" --type hdri
python scripts/dragon.py tool hunter get 1 --out out/footage --dry-run
python scripts/dragon.py tool hunter keys
```

**حدود صادقة:** مهارة المستخدم الأصلية تشير إلى برنامج Windows خارجي وفهرس 615 موقعًا و19 مصدر API، لكن الملف المرفق لم يشمل الكود أو الفهرس؛ الإصدار المدمج يدرج **31 مصدرًا مميزًا** من فهارس v10.1 مع إضافات روابط فقط، والبحث المباشر حصريًا عبر موصلات الفيديو/الصور الموجودة. ليس كل مصدر API قابلًا للاستدعاء. مفاتيح API لا تُطبع، ولا تنزيل بلا أمر، ولا يُعتبر إدراج موقع أو العثور على عنصر إذنًا تجاريًا لاستخدامه. المرجع: `references/MEDIA_HUNTER_V102.md`، والملف الأصلي محفوظ كوثيقة.

## v10.1.0: تحسينات عملية من أرشيفات v1.3 وv1.2

- `tool stock sources|search|download|credits` يعمل محليًا مع اختبارات استجابة شبكية مزيفة ومصادر ترخيص لكل نتيجة؛ لا يُنزّل شيئًا تلقائيًا.
- `verify --duration` يتطلب مسار صوت في الفيديو افتراضيًا، ويرفض الصوت الرقمي الصامت؛ `--silent-ok` للفيلم المتعمّد الصمت.
- `mux` يمنع تمرير تجميد إطار أخير يتجاوز 0.5 ثانية دون `--allow-pad`؛ هذا يتحقق من مخرجات الوسائط وليس جماليات القطع.
- `words` يتجنب تحميل نموذج Whisper تلقائيًا؛ يتطلب `--download` مع إذن واضح، ويجهّز المقاطع المضغوطة عبر WAV مؤقت.
- `dragon_montage` يحفظ زمن المستخدم الحرفي، ويحترم النفي في التعليمات، ويُبقي قيود الأشخاص والحقوق وينشئ مصفوفة حركات أوضح.
- `lyrics-sheet` يدعم تقسيم لوحات الكلمات إلى صفحات وضبط عرض الأعمدة.
- مُشغّل النسخة المتضمنة يعزل كود المستخدم الأقدم ولا يكتب فوق مستودعه، ويرصد تغيّر الشفرة بمحتوى الملفات وليس وقتها.
- `setup` لا يثبت حزمًا تلقائيًا؛ بدون `--yes` يعرض الخطة فقط.

التفاصيل، والاختبارات والقيود: `TEST_REPORT.md` و`references/UPSTREAM_V13_DIFF.md`.

## v10.0.0: تكامل التفكير والأدوات مع Superpowers (بدون ادعاء تشغيل)

**مرجع الدماغ الأساسي** هو مهارة `kosif-superpowers` في `kosif199022-jpg/kosif-tool`، المسار `.claude/skills/kosif-superpowers/`، وفق `LOADER` و`PROTOCOL.md` و`hub.py`. التكامل في هذا الإصدار **جسر خطط وفهرسة محلي**، لا يستنسخ الشفرة الخارجية ولا يفعل SEE أو الوكلاء تلقائيًا. لو المستودع على الجهاز، تبدأ بـ `LOADER` ثم `skill_loader.py need` أو `full` حسب طلب المستخدم؛ تتبع المسار المعتمد (مدخلات ← خطة ← أدوات ← أدلة ← مراجعة). اقرأ `references/INTEGRATION_SUPERPOWERS.md` و`references/EXAMPLE_DEBATE_REPORT.md`.

```bash
python scripts/dragon.py probe-tools --json                 # فحص آمن للـ 30 adapter المسجّل، بدون تشغيلها
python scripts/dragon.py ecosystem --json                   # هل Superpowers / Atlas موجودة محليًا؟
python scripts/dragon.py plan "فيديو عربي سينمائي" --mode smart --json # تحديد المناسب + المفقود
python scripts/dragon.py plan "فيديو عربي سينمائي" --mode full --json  # فحص جميع الـ30، لا يشغّلها
python scripts/dragon.py build --own                        # سجّل أدوات التنين بدون مسح فهرس المستودعات
python scripts/dragon.py setup --dry-run                    # خطة فقط؛ لا تثبيت
# setup --yes يثبّت الحزم فقط بعد موافقة صاحب الجهاز صراحة
```

**الفرق الجوهري:** 30 `registered` ليست 23 أداة اجتازت اختبار تشغيل. فحص `probe-tools` يعني اكتشاف ملفات التنفيذ والاعتماديات على **هذه الآلة فقط**؛ النجاح الفعلي يجب أن يثبت بـ CLI حقيقي + مخرجات + `verify` + تقرير. ووجود 15 ألف مهارة/آلاف القدرات في فهرس SQLite لا يجعلها أدوات تنفيذية. `full` يعني *فحص جميع الأدوات وقراءة كل التفكير ذي الصلة*، لا التشغيل الأعمى، ولا موافقة ضمنية على دفع أو نشر أو تثبيت.

**الاختيار الذكي / full mode:** في وضع `smart` قيّم الطلب وأسبابه، رجّح أقل مجموعة أدوات مناسبة وخطة بديلة؛ في `full` راجع جميع المسجلات ثم اختر ذات الصلة، مع المجلس ومحامي الشيطان والملاحق المطابقة عند وجود Superpowers ووسائلها. في الحالتين سجّل العوائق ومصدر الدليل، ولا تقُل `proven` إلا بنتيجة اختبار تشغيل فعلية. عند غياب Superpowers محليًا استخدم الفهرس المدمج كمرجع فقط، ولا تزعم أن أي مسار Windows مخزّن ما زال موجودًا.

**بروتوكول التفكير المدمج:** 1) فك كل القيود وقائمة النجاح 2) 3 حلول متباينة ودليل مضاد 3) اختيار أدوات متاحة فعلاً 4) موافقات على المصروف/الرفع/النشر/التثبيت 5) تنفيذ موثق 6) اختبارات جودة ومراجعة بصرية. لا تحوّل الأوصاف إلى برامج إلا بكتابة adapter واختباره، ولا تنفّذ command من بطاقة فهرس كما لو كانت شفرة موثوقة.

**تحسينات عملية:** تم الاحتفاظ بمحركات الفيديو `mux`, `patch-black`, `align`, `lyrics-sheet`, فحص السواد وطول الفيلم بالفريم، وإضافة `image_studio` و`blender` من النسخة الثانية، و124+ مرادف مصري، وأداة `tool fetch` بسجل المصادر. يوجد 13+ محرك حسب ما يتاح فعلاً عبر `engines`. ملفات الخطوط الثنائية لا تُرفق في حزمة التوزيع: راجع `references/FONTS_REQUIRED.md` لاسترجاع الأصول المرخّصة محليًا.


## الإصدار 10 — قدرات جديدة فعلية قابلة للاختبار

هذا إصدار وظيفي فوق v1.3، وليس تغييرًا للرقم فقط. يعتمد على المدخلات المرفقة من المستخدم والنسخة السابقة.

```bash
python scripts/dragon.py v10 catalog-audit              # يكشف عدد الفهارس ولا يسوّيها بالأدوات المنفذة
python scripts/dragon.py v10 think "فيلم 30 ثانية" --domain video
python scripts/dragon.py v10 audit-media video.mp4 --out audit.json
python scripts/dragon.py v10 audit-media video.mp4 --deep --out deep.json
python scripts/dragon.py v10 kling-pack examples/v10-kling-spec.json --out kling.json
python scripts/dragon.py v10 gate init --job out/my-film --brief examples/v10-brief.json
python scripts/dragon.py v10 gate check --job out/my-film       # فشل إذا لم تكتمل المراحل
```

**بوابة الفيديو v10 ذات سبع مراحل:** `brief → concept → color-design → shots → produce → qa-color → deliver`. المرحلة `qa-color` تُسجَّل حصريًا بواسطة أمر `gate qa` القائم على تحليل MP4 الحقيقي وفحص السواد وطول الفيلم. يتطلب `shots` وجود ستوري بورد وموافقة على المعاينة (ما لم تكن تعليمات المستخدم «نفّذ مباشرة» ضمن الـ brief). كل ملف ناتج أو إسناد تُؤخذ بصمته SHA-256، ثم يرفض `gate check` العبث أو نقص المراحل. هذا **فحص سلامة محلي** وليس توقيعًا رقميًا مستقلًا ولا حكمًا جماليًا. راجع [الدليل العملي](references/V10_MANUAL.md).

**مهم:** `gate render` وضع معاينة افتراضي؛ لا يشغل `ffmpeg` إلا بـ `--execute` و`--job` فيه معاينة معتمدة، ولا يعمل على روابط الشبكة أو يكتب فوق ملف موجود بلا `--overwrite`. لا توجد أي مكالمات Kling/Suno/Higgsfield داخل `v10 kling-pack`؛ الحزمة نصية فقط ولا تصرف رصيدًا.

**كتاب التفكير:** خريطة قياسات قابلة للفحص مستخلصة بصياغاتنا من *Thinking, Fast and Slow*؛ ليست نسخًا للفصول ولا تدريبًا للنموذج. مصادر مفصلة في [مصادر النسخة 10](references/V10_SOURCES.md). تقارير قديمة عن 72 أو 6773 تنفيذًا هي لبيئات أخرى وليست اختبارات تشغيل جديدة.

## خريطة مراجع الإصدار 10

- [دليل التثبيت والمراحل السبع](references/V10_MANUAL.md)
- [البروتوكول التنفيذي ومشكلة الموصلات](references/V10_VIDEO_PROTOCOL.md)
- [فحوص التفكير من كتاب Kahneman](references/V10_THINKING_FAST_SLOW.md)
- [إخراج Kling السينمائي](references/V10_KLING_CINEMA.md)
- [حالة فيديوهات أغنام الوادي](references/V10_MEDIA_CASE_STUDY.md)
- [فهرس روابط ميار](references/V10_MAYAR_INDEX.md)
- [مصادر وملكية ومدى التحقق](references/V10_SOURCES.md)

---

# v10.17.1 → v10.17.3 candidates (moved verbatim from SKILL.md in v1990)

## KOSIF Cinema Craft (v10.17.3 candidate)
- استيراد مرجعي آمن من `_skills.rar`: تم حفظ Cinema وCreative Studio والوثائق القديمة داخل `references/source_archives/skills-rar` دون تشغيل سكربتاتها الخام أو استبدال المحركات الأحدث. حصر المصدر في `SOURCE_CINEMA_ARCHIVE.json`.
- `tool cinema-craft doctor`: فحص توفر برامج الرندر دون تشغيل أي مصدر خارجي.
- `tool cinema-craft spec-audit --input FILM.json`: فحص مواصفات مشاهد Cinema ومجموع المدد والتحذيرات.
- `tool cinema-craft style --input FILM.json --out NEW.json`: ضبط تحولات الـiris ومنطقة النص بأمان **في ملف جديد فقط**.
- `tool cinema-craft cut --input SOURCE.mp4 --start 1 --end 2 --out CUT.mp4 --fps 30`: قص بإعادة ترميز كاملة مع فحص عدد الفريمات، دون الكتابة فوق الأصل، لا يشغّل توليدًا مدفوعًا.
- `dragon-genius.zip`: مطابق تمامًا لنسخة `skills/dragon-genius` الموجودة (8 ملفات SHA256)، لذلك لم يُكرر. `creative-studio` وقوالب cinema مثبتة/موجودة أصلًا.
- **حدود التحقق:** اختبارات محلية فقط، وليس تشغيلًا على Higgsfield؛ المواصفات وكون XL مجانيًا غير مؤكدين. أكواد المصدر من الأرشيف مرجع غير موثوق ولا تُشغّل دون مراجعة منفصلة.

## KOSIF Reel DNA (v10.17.2 candidate)
- `tool reel-dna katana-commands --workdir DIR --url URL`: أوامر تحليل مقترحة (تُطبع **فقط** ولا تُنفّذ).
- `tool reel-dna extract --analysis FILE [--energy FILE] [--beats FILE] [--words FILE] --out DNA.json`: يحول بيانات توقيت مثبتة إلى وصفة بالفريم، ولا يخمّن القطعات المفقودة.
- `tool reel-dna apply --recipe DNA.json --clips OWN1 OWN2 ... --out EDL.json`: يربط قطعات المرجع بملفات صاحب المشروع.
- `tool reel-dna render --edl EDL.json --out PREVIEW.mp4 --preview`: معاينة محلية (قطع مطابق وفلاش مبسط فقط). لا ينقل موسيقى/لقطات المرجع.
- `tool reel-dna library add|list|show`: مكتبة محلية قابلة للبحث. انظر `references/REEL_DNA_V10172.md` للقيود والأمثلة.
- اختبارات محلية مثبتة فقط؛ **لم تختبر ملفات Katana الحقيقية أو خدمات Higgsfield**، ولا يمكن الجزم بأن Sandbox مجاني.

## Higgsfield Workflow Discovery (v10.17.1 candidate)
- `tool hf workflows` للـ14 Workflow الموصوفة بتقرير فحص المستخدم.
- `tool hf workflow shorts-studio` للتفاصيل؛ `tool hf route "ريلز عربي"` للاقتراحات فقط.
- الحالة **فهرسة اعتماديات** لا تشغيل مثبت؛ تكلفة Sandbox وXL غير مضمونة؛ راجع `references/HIGGSFIELD_AUDIT_2026-11-11.md`.

---

# v10.15.0 → v10.16.1 (moved verbatim from SKILL.md in v1990)

## v10.16.1 — دمج آخر جلسة (السرعة والحجم والتوقيت) + تصليحات
- **رندر متوازي:** `tool hf paste <job>` بقى بيكتب `~/bdtools/prender.sh` كمان. شغّل فريمات الـ HTML/SVG بـ `bash ~/bdtools/prender.sh 4 TOTAL -- <أمر بيقرا $RANGE>` على XL: 732 فريم في 37 ث بدل حوالي 4 د.
- **توقيت المرجع:** `tool reftiming REF.mp4 [--band 0.42,0.14]` بيطلّع start/end لكل سطر ظاهر في فيديو المرجع. استخدمه لأي طلب «بنفس الستايل» على نفس الصوت، والنص لازم يتأكد من مصدر.
- **بوابة الحجم:** `qc.sh` بقى بيرجّع FAIL فوق 20 Mbps متوسط. التصدير: `-crf 19 -maxrate 14M -bufsize 28M`.
- **صور الشات ← Higgsfield:** `media_upload_widget` لوحده في الدور، وبعدين `curl` من CloudFront جوه الـ sandbox. ولو الرفع رجّع 400: لينك جديد وارفع ملف ملف.
- **تصليحات:** `tool re` كان بيقع (`re.py` بيستورد نفسه بدل مكتبة Python)، واختبار `cloud_browser` كان بيوقّف كل الاختبارات لو aiohttp مش موجودة، ودلوقتي بيتخطّى بهدوء.

## v10.16.0 — الرسام + صيّاد الفيديو + توون + سجل اللينكات
- **الرسام (`tool paint`):** مهارة paint-studio بقت جوه التنين (`skills/paint-studio`). ابدأ بـ `tool paint doctor`، واعمل كانفاس بـ `tool paint new out/canvas.png --size 1152x648 --bg white`، وارسم بـ `tool paint draw IN OUT --ops ops.json` (`tool paint ops` بيوريك كل العمليات). الكتابة العربي بتطلع متشكّلة صح، وفيه طبقات `.dpaint` وشيل خلفية وستيكر وصفحة تلوين، وكله على الجهاز ببلاش. صور الـ AI: `tool paint ai create out/img.png --prompt "..." --steps 1` (SD-Turbo محلي، محتاج حوالي 4 جيجا رام فاضية). `print` و`wallpaper` بيغيّروا حاجات بره الصورة، فلازم تستأذن الأول وبعدين تضيف `--yes`.
- **صيّاد الفيديو (`tool grab`):** مهارة video-grabber بقت جوه التنين (`skills/video-grabber`). `tool grab plan URL` بيطبع الأوامر اللي هيجرّبها بالترتيب من غير نت: `tool fetch` الأول، وبعدين grab، وبعدين بروكسي من ملفك إنت بس، وبعدين متصفح مخفي (`tool grab ghost sniff URL`) يلاقي رابط m3u8 أو mpd. فيه كمان صوت بس (`--audio-only mp3`) وجزء من الفيديو (`--section 00:01:00-00:02:30`). البروكسيات المجانية وTor والتحديث الذاتي مقفولين.
- **توون (`tool toon`):** محرك الكارتون والأنمي اتنقل من تطبيق التنين. ابدأ بـ `tool toon doctor`، واعمل معاينة 3 ثواني الأول: `tool toon video IN.mp4 OUT.mp4 --style hayao --seconds 3`. الأساليب: `3d` (كارتون مع كشف وشوش)، و`hayao` و`shinkai` (أنمي)، و`paint` (بورتريه مرسوم)، و`ai3d` (الأقوى، بس حوالي 20 ثانية للفريم). بيشتغل من مجلدات أساميها عربي. hayao وshinkai رخصتهم غير تجارية، فخلّي بالك في شغل العملاء.
- **سجل اللينكات (`tool links`):** 1500 لينك من 165 محادثة، متصنّفين (`references/LINKS.md`). `tool links route URL` بيقولك أنهي أداة تتعامل مع اللينك ويطبعلك أمرها من غير نت. `find` و`list --category` و`stats` بيدوّروا في السجل، و`add URL --note` بيحفظ على جهازك بس، وبيرفض أي لينك فيه سر.
- الأدوات المسجّلة بقت 67، والأربعة الجديدة بتطلع رقم 1 في `find` بالعربي.

## v10.15.0 — دمج v10.12.1 + تحويل قواعده لكود
- القاعدتين اللي فوق ودروس جلسة 2026-11-10 (xfade وfill:'both' وفيديو X وكلمات الأغنية من مصدرين والرسم الخطي) في `references/LESSONS.md`.
- `tool onscreen lint-web FILE…` بيمسك `fill:'both'` (نص بيظهر قبل وقته) و`xfade` من غير `tpad` (الفيديو بيقصر 5 فريمات).
- `tool brain` بقى يحط فحص الكتابة على الشاشة في شروط التسليم لأي فيديو، وقاعدة رصيد Higgsfield أول بند في الموافقات.
