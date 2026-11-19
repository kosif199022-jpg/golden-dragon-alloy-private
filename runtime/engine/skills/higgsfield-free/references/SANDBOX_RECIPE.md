> **تحديث توثيقي 2026-11-11:** هذه الصفحة تسجل قياسات تمت يوم 2026-11-10، وليست ضمان مجانية من Higgsfield أو مواصفات ثابتة لـXL. في الفحص الأحدث الذي أرسله المستخدم، Standard نحو 2 vCPU/8 GiB وXL لم يُفتح. راجع [HIGGSFIELD_AUDIT_2026-11-11.md](HIGGSFIELD_AUDIT_2026-11-11.md) وفهرس الـ14 Workflow. **ممنوع تشغيل XL أو أي استدعاء قد يكون مدفوعًا دون تأكيد التكلفة والموافقة.**

# Higgsfield ببلاش: إيه اللي ينفع من غير كريدت، وإزاي نشتغل عليه (v10.12، اتقاس 2026-11-10)

> القاعدة: **«ببلاش» = اتقاس، مش متخمّن.** اتقاس بإن الرصيد فضل 350.63 قبل وبعد ساعات شغل على الـ sandbox (رندر، تفريغ، تنزيل، رفع)، وسجل `transactions` مافيهوش أي سطر للـ sandbox أو الرفع. Higgsfield ممكن يغيّر ده: **اعمل `balance` قبل وبعد أي شغلانة كبيرة واكتب الرقمين في التقرير.**
> المدونة الرسمية بتقول إن الـ MCP «بيشتغل بالكريدت»: ده صح لأدوات التوليد، لكن الـ sandbox والرفع ماخصموش حاجة في القياس.

## 1. جدول الأدوات

| الأداة | بتعمل إيه | كريدت؟ | ملاحظة |
|---|---|---|---|
| `sandbox_exec` (عادي) | جهاز Linux فيه نت: 1 CPU، 8 GB رام، 382 GB هارد | **0 (اتقاس)** | foreground ≤120 ث؛ background ≤15 د؛ الملفات تفضل 24 س |
| `sandbox_exec size:"xl"` | 4 CPU، 16 GB رام | **0 (اتقاس)** | بيقفل بعد دقيقة من آخر شغل؛ استخدمه للرندر بس |
| `media_upload` + PUT + `media_confirm` | رفع ملف ← لينك CloudFront دايم | **0 (اتقاس)** | الـ PUT لازم يتعمل جوه الـ sandbox بهيدر `If-None-Match: *` |
| `media_import_url` | يجيب ملف من لينك HTTPS لمكتبتك (≤50 MB) | مجاني غالبًا | مااتقاسش؛ اعمل balance قبل/بعد |
| `show_medias`، `balance`، `transactions` | قراءة | 0 | |
| `models_explore`، `get_presets`، `list_voices` | استكشاف موديلات وبريسيتات وأصوات | 0 | قراءة بس |
| `get_workflow_instructions` + سكربتات `$HF_WORKFLOWS` | سكربتات جاهزة جوه الـ sandbox (تحت) | 0 | التشغيل نفسه على الـ sandbox |
| `tiktok_music_trending` | تراكات تيك توك التجارية الترند | 0 (قراءة) | محتاج حساب تيك توك متوصل (`tiktok_accounts`) |
| `generate_image/video/audio`، `upscale_*`، `remove_background`، `reframe`، `motion_control`، `outpaint_image`، `dubbing`، `voice_change`، `create_voice` | توليد/تعديل بالـ AI | **بكريدت** | سعر + «أيوه» كل مرة (OWNER.md) |
| `video_analysis_create`، `virality_predictor` | تحليل مشاهد / توقع انتشار | **مش معروف** | اعتبره مدفوع لحد ما يتقاس بـ balance قبل/بعد وبموافقته |
| Unlimited (`use_unlim`) | توليدات ببلاش لموديلات معينة | **مش متاح دلوقتي** | `models_explore unlim:true` رجّع `available:false`، والمدونة بتقول الـ unlimited على higgsfield.ai بس مش من الـ MCP |

## 2. جوه الـ sandbox (اتجرب فعلاً)
- **النظام:** Debian 12، x86_64، **مفيش GPU** (مفيش nvidia-smi)، Python 3.12، Node 22.
- **ffmpeg 5.1:** x264، x265، SVT-AV1، VP9، ProRes، AAC، Opus. وفيه فلاتر `drawtext`، `subtitles/ass`، `xfade`، `zscale`، `libplacebo`، `lut3d`، `vidstab`، `deshake`، `minterpolate`، `chromakey`، `rubberband`، `arnndn` (تنضيف صوت)، `loudnorm`، `ebur128`.
- **بايثون:** PIL، numpy، OpenCV، faster-whisper، scipy، librosa، soundfile، onnxruntime، ctranslate2، requests، yt_dlp. **مش موجود:** torch، fontTools، moviepy، demucs، rembg، tesseract، Blender.
- **أدوات:** Playwright + Chromium (`NODE_PATH=/usr/local/lib/node_modules`)، sharp-cli، ImageMagick 6 (`convert`)، sox، rsvg-convert، ghostscript، pdftoppm، git، jq، curl.
- **التثبيت:**
  - `pip install` بيقع (`Permission denied: '/root'`). الحل اللي اشتغل: نزّل الـ wheel من PyPI بـ curl، وفكّه بـ `python3 -m zipfile -e X.whl ~/pylib`، وشغّل بـ `PYTHONPATH=~/pylib`.
  - `npm i` المحلي في فولدر شغال.
- **النت:**
  - **شغال:** Mixkit (فيديو ومزيكا وSFX)، GitHub raw (خطوط Google من `github.com/google/fonts/raw/main/ofl/...`)، fonts.google.com، archive.org، api.aladhan.com، api.alquran.cloud، huggingface.co، tiktokcdn (لينكات playUrl).
  - **مقفول:** Pexels وPixabay (403). yt-dlp على تيك توك ويوتيوب وإنستجرام بيقع (bot/sign-in).
- **مقارنة سرعة (نفس الاختبار، 2026-11-10):** 20 ث 1080×1920 فيها noise كتير (أصعب من الفوتيج العادي)، slow/CRF17:
  | الجهاز | الأنوية | الوقت | |
  |---|---|---|---|
  | مساحة شغل Claude السحابية | 2 | 586 ث | الأبطأ ومفيهاش نت |
  | Higgsfield عادي | 1 | 383 ث | أسرع 1.5× |
  | Higgsfield XL | 4 | 147 ث | **أسرع 4×**: ده الافتراضي للرندر النهائي |
  القاعدة: الرندر النهائي دايمًا على Higgsfield XL في `background:true`، ولو الشغل أطول من 15 د قسّمه segments. مساحة Claude للكود والاختبارات وتحديث المهارة بس.
- **مقارنة سرعة (نفس الاختبار، 2026-11-10):** 20 ث 1080×1920 فيها noise كتير، slow/CRF17: مساحة Claude (2 CPU) = **586 ث**، وHiggsfield عادي (1 CPU) = **383 ث**، وHiggsfield XL (4 CPU) = **147 ث**. يعني الرندر النهائي دايمًا على XL.
- **رندر الفريمات على التوازي:** `prender.sh 4 TOTAL -- …` على XL: 732 فريم HTML/SVG في **37 ث بدل ~4 د**. الشغلانة كلها بالـ encode والـ QC في 27–43 ث.
- **حجم الملف:** الجرين بيضخّم البت ريت (410 MB لـ 35 ث). التصدير: `-crf 19 -maxrate 14M -bufsize 28M`.
- **السرعة:** XL بيعمل encode لـ 27.6 ث على 1080×1920 بـ slow/CRF17 في **31 ث**. faster-whisper `medium` int8 فرّغ 25 ث صوت في أقل من دقيقة على CPU واحد.
- **عرض الصور لينا:** `image_paths` بحد أقصى 4 صور ≤512 KB مع بعض. اعمل contact sheet بـ PIL ورجّعه.

## 3. سكربتات Higgsfield الجاهزة (ببلاش، جوه الـ sandbox)
`$HF_WORKFLOWS=/home/user/.higgsfield/workflows`. اقرا تعليمات أي واحد بـ `get_workflow_instructions` قبل تشغيله.
- **video-montage:** تفريغ كلمات (`transcribe_words.py`)، كابشن كلمة بكلمة وحرقه على الفيديو (`make_captions.py`، `burn_caps_clean.sh`)، مكان الكابشن بعيد عن الوش (`caption_placement.py`)، وخطوط Metropolis/Montserrat.
- **color-grade:** 20 لوك سينمائي (matrix، dune، la-la-land، blade-runner-2049، drive…). `grade.py --list`، `--look`، `--ref` (لون من صورة مرجع)، `--lut` لتصدير LUT، و`video.py` للفيديو.
- **reel-effects:** 17 قالب HTML (text-behind، grade-wipe، freeze-frame، tier-list، captions، katana-*) بيترندروا فريم فريم في Chromium، ومكتبة SFX **CC0** (whoosh، hit، riser، flash، type، ui_blip…) من غير ما نحتاج كريدت.
- **shorts-studio:** `engine.js` و`render.py` لرندر صفحات HTML لفيديو.
- **narration:** `speech_metrics.sh` لقياس الكلام والسكتات.
- **faceless-video:** سكربتات تجميع الفيديو النهائي والتحقق منه.
- مسموح نستخدمها من غير كريدت، **إلا الخطوات اللي جواها بتنادي `generate_*`**: دي بكريدت.

## 4. الوصفة الثابتة (التنين على Higgsfield)
1. `balance` (اكتب الرقم).
2. `sandbox_exec`: لصق `tools/hf_sandbox/bootstrap.sh` (فولدر الشغلانة، الخطوط العربية، فحص الأدوات).
3. الخامات: Mixkit (`-1080.mp4`، ولو 403 يبقى `-720.mp4`؛ والطولي 1080×1920 الأول)، وCC0 SFX من reel-effects، وخطوط Google.
4. النص العربي: صفحة HTML + Playwright بـ `page.goto('file://…')` (مش `setContent`)، وبعدين PNG شفاف و`overlay` في ffmpeg.
5. الرندر: segments بـ `veryfast CRF16`، وبعدين `xfade` + overlays، والتصدير النهائي `slow CRF17` على XL، و`background:true`، والـ polling كل ≤60 ث.
6. QC: لصق `tools/hf_sandbox/qc.sh FILE DURATION` (فك كامل، فريمات، سواد، LUFS/TP). لو TP > −1.5: اعمل pass للصوت بس بـ `-c:v copy`.
7. التسليم: `media_upload` ← PUT جوه نفس الـ sandbox ← `media_confirm` ← لينك CloudFront. مساحة شغل Claude مابتقدرش تنزّله، فاللينك هو التسليم.
8. `balance` تاني، والفرق يتكتب في التقرير.
9. الكابشن والهاشتاجات: `$D tool tags` ← بلوك كود.

## 5. قدرات نقدر نعملها ببلاش دلوقتي
- ريلز/مونتاج كامل 1080×1920 بنقلات xfade وزوم وتدريج لوني وخطوط عربية من Google.
- تفريغ صوت/دعاء بتوقيت الكلمة، وظبط الكلام على الشاشة على الصوت بالظبط.
- كابشن متحرك كلمة بكلمة (video-montage) وتأثيرات reel-effects الجاهزة.
- لوكات لون سينمائية من صورة مرجع أو من الـ 20 لوك.
- تنضيف صوت (`arnndn`/`afftdn`)، وloudness −14، وbeats بـ librosa، وتمديد/ضغط زمن بـ rubberband.
- تثبيت فيديو مهزوز (vidstab)، وslow-mo بـ minterpolate، وchroma key.
- نص القرآن من api.alquran.cloud، والهجري من aladhan.
- مواقع/ألعاب: `website-builder-flow` موجود، **بس النشر والـ deploy ممكن يكون ليهم تكلفة: اتأكد قبلها.**

## 6. اللي مش ببلاش أو مش ممكن
- مفيش GPU: مفيش demucs/SAM/rembg تقيل (rembg ممكن بـ onnxruntime على CPU لو جبنا الموديل من huggingface، بس ببطء).
- أي صورة أو فيديو أو صوت متولّد بالـ AI بكريدت، وكمان upscale وremove_background.
- تحميل مباشر من تيك توك/يوتيوب/إنستجرام بـ yt-dlp مقفول من الـ sandbox. **تصحيح v1990 (2026-11-11):** السطر القديم كان بيقترح `curl` من الـCDN بهيدر `Referer` بتاع تيك توك. ده اتشال: تزوير Referer أو User-Agent تحايل على فحص البوتات واترفض يوم القياس، وضد قاعدته في OWNER.md §7. البديل: يبعت الملف هو، أو `tool tiktok-post` لبوستات الصور، أو صفحة الرفع.
