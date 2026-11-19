# تقرير قدرات: أول 40 مستودع من الكتالوج (Pilot 40)

- **المصدر:** أول 40 صف بيانات في `%USERPROFILE%\Downloads\all-repos-catalog.csv`.
- **التاريخ:** 2026-11-16.
- **الطريقة:** دوّرنا باسم الأداة أو الباكدج (مش باسم المستودع بس) جوه `golden-dragon` (scripts وengine وmind وreferences وmodules) وفي `app/golden/library.json`. وكشفنا على الجهاز بـ `where.exe` و`python -c "import X"` وبالـ `node_modules` و`npm -g`. وقرينا README والرخصة لكل مستودع بـ `gh api repos/OWNER/REPO/readme` و`gh repo view --json licenseInfo,stargazerCount,pushedAt`. ماتثبّتش أي حاجة وماعملناش clone.
- **معنى الحالة:**
  - **مستخدم:** فيه كود في المهارة بيشغّله أو بيعمله vendor أو بيديله وصفة تثبيت (codekit).
  - **متثبت ومش متوصّل:** موجود على الجهاز، بس المهارة بتكتشفه في `doctor` بس، وماحدش بيستدعيه.
  - **قدرة جديدة:** مش متثبت ولا متوصّل. لو ليه ذكر فهو في كتالوجات المراجع بس (`RD_TOP500_REPOS.md` و`library.json`).

## الملخص

| الحالة | العدد |
|---|---|
| مستخدم | 16 |
| متثبت ومش متوصّل | 4 |
| قدرة جديدة | 20 |
| **الإجمالي** | **40** |

## جدول الأربعين

| # | Repo | الحالة | الدليل على الجهاز وفي المهارة | الإضافة الملموسة | التشغيل على Windows | ملاحظة الرخصة |
|---|---|---|---|---|---|---|
| 1 | yt-dlp/yt-dlp | مستخدم | `yt-dlp.exe` موجود، و`yt_dlp` بيتعمله import، ومستخدم في `modules/cinema/scripts/fast_dl.py` | (موجود) تحميل فيديو وصوت وترجمات | `yt-dlp -f ...` | Unlicense |
| 2 | PaddlePaddle/PaddleOCR | قدرة جديدة | مش متثبت، ومالوش ذكر في الكود | يقرا النص العربي من الصور وفريمات الفيديو (ترجمة محروقة، لافتات) أدق من Tesseract، ويطلّع bbox | `pip install paddlepaddle paddleocr` ثم `paddleocr ocr -i frame.png --lang ar` | Apache-2.0. الموديلات بتتحمّل من HF/ModelScope |
| 3 | opencv/opencv | مستخدم | `cv2` 5.0.0، ومستخدم في `character-memory` و`chroma_identity.py` | (موجود) | `import cv2` | Apache-2.0 |
| 4 | google-ai-edge/mediapipe | متثبت ومش متوصّل | `mediapipe` 1.2.2 (فيه Tasks API بس، ومافيهوش `solutions`)، وبيتذكر في `doctor.py` و`machine.py` بس | تتبّع الوش والجسم والإيد لعمل auto-reframe لـ 9:16، وقص بيتبع الوش، وتغبيش الوشوش | Python: `mp.tasks.vision.FaceDetector/PoseLandmarker` مع ملف موديل `.task` | Apache-2.0 |
| 5 | xinntao/Real-ESRGAN | مستخدم (من خلال Upscayl) | `image_studio` بيشغّل `upscayl-bin` (محرك Real-ESRGAN ncnn) من `C:\Program Files\Upscayl\resources\bin`، والباكدج `realesrgan` مش متثبت | (موجود) تكبير 4× | `upscayl-bin -i in -o out -s 4` | BSD-3. موديلات Upscayl ليها رخصها الخاصة |
| 6 | danielgatis/rembg | مستخدم | `rembg.exe` و2.0.87، ومستخدم في `chroma_identity.py` | (موجود) | `rembg i in.png out.png` | MIT. موديل BRIA RMBG رخصته غير تجارية |
| 7 | facebookresearch/sam2 | متثبت ومش متوصّل | `import sam2` شغال من `%USERPROFILE%\dragon-repos\sam2`، و`sam2.1_hiera_tiny.pt` موجود. موجود في `doctor.py` و`library.json` (needs-install) بس | تضغط على عنصر أو تحدده بمربع في فريم واحد، فيتتبّع الماسك على الفيديو كله (روتو، عزل عنصر، تلوين انتقائي) | سكربت Python بـ `build_sam2_video_predictor` يطلّع PNG alpha، وبعدين `ffmpeg alphamerge` | Apache-2.0. torch عندنا CPU، فهيبقى بطيء: استخدم tiny ومقاطع قصيرة |
| 8 | ImageMagick/ImageMagick | مستخدم | `magick.exe` 7.1.2، وفي كتالوج `machine.py` وتعليمات `dragon_desktop` | (موجود) | `magick in.png -resize ...` | ImageMagick License (شبه Apache) |
| 9 | lokesh/color-thief | قدرة جديدة | مش موجود | يستخرج اللون الغالب وباليتة من لوجو أو فريم ويبني بيها ثيم الموشن تلقائيًا | `npx colorthief-cli photo.jpg` (بيطلّع JSON/CSS) | MIT |
| 10 | DepthAnything/Depth-Anything-V2 | قدرة جديدة | مش متثبت كموديول، بس `transformers` 4.57.6 و`torch` موجودين، ومتسجّل في `library.json` (needs-install) | خريطة عمق من صورة واحدة تعمل منها parallax 2.5D وحركة كاميرا من صورة ثابتة وDOF وفصل أرضية | `transformers.pipeline("depth-estimation", model="depth-anything/Depth-Anything-V2-Small-hf")` | **Small بس Apache-2.0. Base وLarge وGiant رخصتها CC-BY-NC-4.0 (ممنوع تجاري)** |
| 11 | Breakthrough/PySceneDetect | مستخدم | `scenedetect` 0.7.2، ومستخدم في `dragon_montage/analyze.py` | (موجود) | `scenedetect -i in.mp4 detect-adaptive` | BSD-3 |
| 12 | gpac/gpac | قدرة جديدة | `MP4Box` مش موجود | فحص MP4 بعمق (`-info`)، وتغليف DASH/HLS، وfragment، وإصلاح وتعديل tracks ومدد من غير re-encode | `winget install GPAC.GPAC` ثم `MP4Box -info f.mp4` | LGPL-2.1. فيه رخصة تجارية بديلة |
| 13 | juliangarnier/anime | مستخدم | vendored: `engine/tools/codekit/vendor/animejs` (4.5.0) | (موجود) | vendored | MIT |
| 14 | pixijs/pixijs | قدرة جديدة | مش متثبت، وفي `library.json` حالته needs-build | رندر 2D على WebGL لآلاف الجزيئات والفلاتر (blur وdisplacement) والماسكات في صفحات HTML-to-video | `npm i pixi.js` أو vendor لملف `pixi.min.js`، والرندر بـ Playwright | MIT |
| 15 | motiondivision/motion | قدرة جديدة | مش موجود | أنيميشن spring وlayout لـ React وJS عادي، ومفيد جوه قوالب Remotion/React | `npm i motion` | MIT. فيه إضافات Motion+ مدفوعة |
| 16 | airbnb/lottie-web | مستخدم | `library.json` (ready-offline)، و`lottie_errors` في `cards/lib/engines_render_pipeline.py` | (موجود) | vendored/clone | MIT |
| 17 | greensock/GSAP | مستخدم | `codekit` (line 3) وفيه أمر `vendor-gsap`، و`library.json` ready-offline | (موجود). MorphSVG وSplitText بقوا مجانًا | `npm i gsap` | GSAP Standard No-Charge License: مجاني وتجاري، بس **مش مفتوح المصدر** |
| 18 | motion-canvas/motion-canvas | مستخدم (متوصّل بس مش متثبت) | `codekit.py` فيه وصفة npm، و`video12` بيختاره. الـ npm مش متثبت | (موجود كوصفة) | `codekit install motion-canvas` | MIT |
| 19 | liabru/matter-js | قدرة جديدة | مش موجود | فيزيا 2D لكتابة حركية: حروف ولوجوهات بتقع وتخبط وتتكوّم، وتترندر فريم بفريم | vendor لملف `matter.min.js` (UMD) مع الرندر الحالي بـ Playwright | MIT |
| 20 | maxwellito/vivus | قدرة جديدة | مش موجود | رسم SVG بالخط (hand-drawn reveal) لشعارات وأيقونات | vendor لملف `vivus.min.js` | MIT. آخر push كان 2022، وGSAP DrawSVG بيغطيه |
| 21 | theatre-js/theatre | قدرة جديدة | مش موجود، و`library.json` reference-only | sequencer للكيفريمات بيحفظ التايملاين JSON لمشاهد three.js وDOM | `npm i @theatre/core` (و`@theatre/studio` للتحرير) | core Apache-2.0، و**studio رخصته AGPL-3.0**. التطوير اتنقل لريبو خاص، وآخر push عام 2024-08 |
| 22 | gka/chroma.js | قدرة جديدة | مش موجود | سلالم ألوان بـ Lab/Lch وباليتات Brewer وتدرّجات ناعمة وفحص تباين للجرافيك والشارتات | vendor لملف `chroma.min.js` أو `npm i chroma-js` | BSD-3 (النسخ قبل 0.4 كانت GPL) |
| 23 | veltman/flubber | قدرة جديدة | مش موجود | morph بين شكلين SVG عدد نقطهم مختلف | `npm i flubber` | MIT. GSAP MorphSVG المجاني بيغطيه، وآخر push كان 2022 |
| 24 | toji/gl-matrix | قدرة جديدة | مش موجود | رياضيات vec وmat وquat لشيدرز WebGL خام | `npm i gl-matrix` | MIT. three.js بيغطيه |
| 25 | jwagner/simplex-noise.js | قدرة جديدة | مش موجود | noise ثابت بـ seed لحركة عضوية (wobble، ودخان، وتموّج خلفيات) قابلة للتكرار | `npm i simplex-noise` + `alea` | MIT |
| 26 | gre/bezier-easing | قدرة جديدة | مش موجود | يحوّل cubic-bezier لدالة easing تتطابق مع CSS وAE | `npm i bezier-easing` | MIT. GSAP CustomEase بيغطيه |
| 27 | microsoft/playwright | مستخدم | `playwright.exe` والموديول، ومستخدم في `render_frames.js` و`cartoon/tools/render.mjs` | (موجود) | | Apache-2.0 |
| 28 | FFmpeg/FFmpeg | مستخدم | `ffmpeg.exe` و`ffprobe.exe` موجودين، وهو العمود الفقري للمحركات | (موجود) | | LGPL/GPL حسب البيلد (بيلد winget غالبًا GPL) |
| 29 | remotion-dev/remotion | مستخدم (متوصّل بس مش متثبت) | `codekit.py` و`video12.py` وفيه 151 ذكر في `library.json` (needs-install). مافيش `node_modules` | (موجود كوصفة) | `codekit install remotion` | **Remotion License: لازم رخصة شركة لو الشركة 4 موظفين أو أكتر** |
| 30 | ManimCommunity/manim | مستخدم | `manim.exe` 0.22.1، ومستخدم في `cards/lib/fam_w3_13.py` و`codekit` | (موجود) | | MIT |
| 31 | lovell/sharp | قدرة جديدة | مش موجود (الإشارة الوحيدة اسم دالة Python ملهاش علاقة) | resize وcrop وتحويل WebP/AVIF بسرعة جدًا لدفعات صور جوه سكربتات Node | `npm i sharp` | Apache-2.0 (libvips فيها LGPL). ImageMagick بيغطي أغلبه |
| 32 | ffmpegwasm/ffmpeg.wasm | قدرة جديدة | مش موجود | FFmpeg جوه المتصفح لصفحات وتطبيقات أوفلاين من غير exe | `npm i @ffmpeg/ffmpeg @ffmpeg/util` | MIT للغلاف، والـ core نفسه LGPL/GPL. قيمته قليلة عندنا لأن ffmpeg الأصلي موجود |
| 33 | Zulko/moviepy | متثبت ومش متوصّل | `moviepy` **0.2.3.1 (قديمة جدًا، من 2017)**، وبيتذكر في قوايم `machine.py` بس | مونتاج بالكود بـ Python (overlay، ونص، وcomposite) | `pip install -U moviepy` (v2 كسرت الـ API) | MIT. ffmpeg المباشر أسرع وأدق |
| 34 | kkroening/ffmpeg-python | متثبت ومش متوصّل | `ffmpeg-python` 0.2.0 متثبت. المحركات بتستخدم غلاف خاص `engines.media.ffmpeg`، مش الباكدج ده | بناء filter graphs كسلاسل Python | `import ffmpeg` | Apache-2.0. آخر push كان 2024، وماحدش بيصونه |
| 35 | mrdoob/three.js | مستخدم | vendored في `codekit/vendor/three` و`cartoon/vendor/three.module.js` | (موجود) | | MIT |
| 36 | pmndrs/react-three-fiber | قدرة جديدة | مش متثبت، و`library.json` reference-only | three.js كـ JSX جوه Remotion (`@remotion/three`) لمشاهد 3D متزامنة مع الفريم | `npm i three @react-three/fiber` | MIT |
| 37 | BabylonJS/Babylon.js | قدرة جديدة | مش موجود | محرك 3D ويب بديل فيه animation groups وnode materials وفيزيا | `npm i @babylonjs/core` | Apache-2.0. بيكرر three.js |
| 38 | blender/blender | مستخدم | `blender.exe` 5.2، و`blender-pro/runner.py` بيشتغل headless | (موجود) | | GPL-3.0 (المخرجات ملكك) |
| 39 | pmndrs/drei | قدرة جديدة | مش متثبت، و`library.json` reference-only | مكونات جاهزة لـ R3F: Text SDF وEnvironment وContactShadows وكاميرات | `npm i @react-three/drei` | MIT. بيحتاج R3F |
| 40 | pmndrs/postprocessing | قدرة جديدة | مش موجود | bloom وDOF وchromatic aberration وvignette وnoise وSMAA لرندرات three.js بشكل سينمائي | vendor للـ ESM build جنب three في `codekit/vendor` أو `npm i postprocessing` | Zlib |

## أهم 10 إضافات (حسب القيمة لشغل الفيديو والصور والموشن)

| # | الأداة | ليه | أرخص طريقة للإضافة |
|---|---|---|---|
| 1 | **SAM 2** | روتوسكوب وعزل عنصر في فيديو كامل بضغطة واحدة، وده مش موجود حاليًا في المهارة | **مافيش تثبيت.** الكود و`sam2.1_hiera_tiny.pt` موجودين في `dragon-repos\sam2`. اكتب سكربت `sam2_track.py` ياخد (فيديو + نقطة أو مربع) ويطلّع PNG masks، وبعدين `ffmpeg alphamerge`. على CPU استخدم tiny ومقاطع قصيرة |
| 2 | **MediaPipe** | auto-reframe لـ 9:16 بيتبع الوش، وتغبيش الوشوش، ونقط الجسم للموشن | **مافيش تثبيت** (1.2.2 موجود). نزّل `face_detector.task` أو `pose_landmarker.task` (ملف واحد)، واكتب سكربت يطلّع مسار crop ويدّيه لـ `ffmpeg crop/sendcmd` |
| 3 | **Depth-Anything-V2 (Small)** | parallax 2.5D وحركة كاميرا من صورة ثابتة، وDOF، وفصل طبقات | **مافيش pip.** `transformers` موجود: `pipeline("depth-estimation", "depth-anything/Depth-Anything-V2-Small-hf")`. التزم بـ Small بس (Apache) |
| 4 | **PaddleOCR** | OCR عربي قوي لفريمات الفيديو والترجمات المحروقة والصور | `pip install paddlepaddle paddleocr` (تقيلة شوية)، وCLI `paddleocr ocr --lang ar`. لحد ما يتثبت، Tesseract موجود كبديل |
| 5 | **pmndrs/postprocessing** | يرفع رندرات three.js لمستوى سينمائي (bloom وDOF وgrain) | vendor لملف ESM واحد جنب `codekit/vendor/three`، وزوّده في قايمة codekit |
| 6 | **chroma.js** | ألوان متسقة للبراند (Lab/Lch وتدرّجات وفحص تباين) في كل قوالب الموشن والشارتات | vendor لملف `chroma.min.js` واحد (BSD) |
| 7 | **color-thief** | يستخرج الباليتة من اللوجو أو الفريم ويغذّي chroma.js بيها، فيطلع ثيم تلقائي | `npx colorthief-cli logo.png` من غير تثبيت دائم |
| 8 | **matter-js** | كتابة حركية فيزيائية (حروف بتقع وتخبط)، وده شكل مطلوب في الريلز | vendor لملف `matter.min.js` واحد، ويترندر بـ `render_frames.js` الموجود |
| 9 | **PixiJS** | جزيئات وفلاتر GPU بأعداد كبيرة في صفحات HTML-to-video | vendor لملف `pixi.min.js`، ويترندر بنفس مسار Playwright |
| 10 | **simplex-noise** | حركة عضوية بـ seed ثابت فتتكرر بالظبط في كل رندر | vendor لملف ESM صغير (MIT) |

### ملاحظات جانبية

- **moviepy:** النسخة المتثبتة 0.2.3.1 قديمة جدًا. لو حد هيعتمد عليها لازم `pip install -U moviepy` (v2)، بس الأفضل نفضل على ffmpeg المباشر.
- **Remotion:** متوصّل في codekit بس مش متثبت. قبل أي شغل تجاري راجع الرخصة (رخصة شركة لو 4 موظفين أو أكتر).
- **Theatre.js:** الـ studio رخصته AGPL والتطوير العام واقف، فمش في التوب 10.
- **flubber وbezier-easing وgl-matrix وvivus:** بيغطيهم GSAP (MorphSVG وCustomEase وDrawSVG مجانًا دلوقتي) وthree.js الموجودين.
- **Babylon.js وffmpeg.wasm:** بيكرروا قدرات موجودة (three.js وffmpeg الأصلي)، فقيمتهم قليلة.
- **GPAC:** مفيد للتغليف (DASH/HLS) والفحص العميق، بس ffmpeg بيغطي أغلب الاحتياج، فاتأجل.
