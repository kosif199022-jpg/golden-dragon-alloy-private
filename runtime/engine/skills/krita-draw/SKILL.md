---
name: krita-draw
description: Draw and paint with code through the real Krita installed on this PC, with no GUI. A JSON scene becomes a layered .kra file that opens and stays editable in Krita, plus a PNG/JPG. Layer types are SVG vector shapes and text (Arabic shaped RTL works), pressure brush strokes (ink, pencil, chalk, airbrush, marker), fill layers, images, groups with blend modes, and Krita's 52 filters as non-destructive masks. It also makes frame-by-frame animation as a real Krita timeline (.kra keyframes) plus MP4/GIF. Use it whenever the user wants Claude to draw, paint, illustrate or design an image «بالكود» or «في كريتا», for example «ارسم في كريتا», «ارسم بالكود», «اعمل لوحة/رسمة/بوستر/بطاقة/خلفية/شخصية كرتون/لوجو بطبقات», «عايز ملف kra», «طبقات أعدّلها في كريتا», «رسم إجرائي/generative art», «أنيميشن/رسوم متحركة فريم بفريم في كريتا», «gif متحرك مرسوم», «krita», «.kra», «paint with code», «procedural illustration», or to add layers to an existing .kra. Prefer it over plain PIL/matplotlib drawing when the user wants an editable layered artwork or mentions Krita. Not for photo retouching of an existing JPG (use photoshop-recipes/paint-studio) or for 3D (blender-pro).
---

# krita-draw — الرسم بالكود جوه Krita

Claude بيكتب **مشهد JSON**، و`krita_draw.py` بيخلّي Krita الحقيقي (5.3.4، من غير واجهة) يبني منه ملف `.kra` بطبقات منفصلة، ويصدّر PNG. الطريقة دي اتبنت على هندسة عكسية لـ Krita نفسه، والتفاصيل والأدلة في `references/re_findings.md`.

## ليه بالطريقة دي (اقرا قبل ما تغيّر حاجة)
- `kritarunner.exe` بيشغّل سكربت بايثون واحد جوه Krita ويقفل في ثواني (شوف «الوقت المتوقع» تحت)، ومش بيتخانق مع Krita المفتوح عند المستخدم لأن له بروفايل منفصل.
- **فُرش Krita الأصلية** (`Node.paintLine/paintPath`) **بتوقّع** Krita من غير واجهة، لأنها محتاجة View وقوائم أكشنز. فالفرشاة هنا محرك numpy (`scripts/brush.py`) بيرسم ضربات بالضغط والتدبيب والملمس، وبتدخل Krita كطبقة رسم عادية يقدر المستخدم يكمّل عليها بفُرشه.
- كل ده مخبّي جوه السكربت: المسارات العربي، وتشغيل أحداث Qt عشان الفيكتور يترسم، وإعادة محاولة حفظ ‎.kra. فاستخدم السكربت ومتناديش `kritarunner` بإيدك.

## الخطوات
1. **افهم الرسمة وخطّطها كطبقات**، زي ما رسام بيشتغل: خلفية ← أشكال كبيرة ← ظلال ونور ← تفاصيل ← خطوط (line art) ← إضاءة (مجموعة `screen`/`overlay`) ← ملمس (`noise` بماسك أو `multiply`).
2. **اختار المقاس:** بوست 1080×1350، ستوري 1080×1920، مربع 2048×2048، A4 طباعة 2480×3508 و`"dpi": 300`. إحداثيات SVG والفرشاة دايمًا **بالبكسل** مهما كانت الـ dpi.
3. **اكتب `scene.json`** في مجلد الشغل (الصيغة كاملة في `references/scene_format.md`). لو الرسمة إجرائية (مئات الضربات، نجوم، شجر، باترن) اكتب سكربت بايثون صغير **يولّد** الـ JSON، بدل ما تكتب كل نقطة بإيدك. فيه قالب جاهز اتجرّب في `examples/night_desert/make_scene.py`: سما بتدرّج، و260 نجمة، وهلال بتوهج (blur + screen)، وكثبان بملمس noise، ونخيل بفرشاة الحبر، وعنوان عربي، وvignette بكود `python`. وفيه `preview.jpg` يوريك الناتج.
   - أشكال مركّبة زي هلال أو حلقة: احسبها كـ `polygon` من نقط، أو بقواسات (arcs) صريحة. `fill-rule=evenodd` بدايرتين متداخلتين بيطلّع حلقة زيادة.
4. **ارسم:**
   ```bash
   python -X utf8 "%USERPROFILE%\.claude\skills\krita-draw\scripts\krita_draw.py" render scene.json
   ```
   من مستودع التنين الأحمر: `python -X utf8 "$D/engine/skills/krita-draw/scripts/krita_draw.py" render scene.json`، أو `rd.py krita render scene.json`.
   بيطبع JSON فيه: `ok`، و`outputs` (المسارات والأحجام)، و`layers` (النوع الفعلي والـ blend والشفافية لكل طبقة)، و`svg_shapes` (عدد الأشكال اللي Krita قراها). لو `svg_shapes` لطبقة = 0 يبقى الـ SVG بايظ.
5. **شوف الناتج بعينك** بأداة Read على الـ PNG قبل ما تقول خلصت. عدّل الـ JSON وأعد، كل دورة بتاخد ثواني.
6. **سلّم:** مسار PNG ومسار `.kra`، وقايمة الطبقات (`krita_draw.py layers file.kra` بيقراها من الملف نفسه من غير Krita).

## أهم الطبقات (التفاصيل في scene_format.md)
| النوع | للإيه | ملاحظة |
|---|---|---|
| `svg` | أشكال، تدرّجات، نصوص، لوجو | دقيق وبيفضل فيكتور قابل للتعديل في Krita. `viewBox` = مقاس الكانفس |
| `brush` | خطوط إيد، اسكتش، حبر، رصاص، طباشير، هوائي | `points` فيها `[x, y, pressure]`، و`tip` واحد من: ink، pencil، soft، chalk، marker، round |
| `fill` | ورق، لون أساسي | طبقة Fill حقيقية في Krita |
| `image` | صورة جاهزة أو رسم من مكتبة تانية | PNG/JPG، بـ `x`/`y` |
| `group` | تجميع + `blend` + `opacity` | `pass_through` اختياري |
| `filters` (على أي طبقة) | blur، oilpaint، noise، halftone، pixelize… | ماسك غير مدمّر. أسامي الإعدادات في `references/krita_live_info.json` |
| `animation` | حركة فريم بفريم | تايملاين حقيقي في ‎.kra، وMP4/GIF (شوف قسم الأنيميشن) |
| `python` (على مستوى المشهد) | أي حاجة الـ JSON مايعرفهاش | كود بيتنفّذ جوه Krita ومتاح فيه `doc` و`root` و`k`. شوف `references/krita_api.md` |

## أنيميشن (تايملاين حقيقي في Krita + MP4/GIF)
طبقة واحدة من نوع `animation` في أي مكان في المشهد. الطبقات اللي تحتها وفوقها بتفضل ثابتة:
```json
{"type": "animation", "name": "قلب بينبض", "fps": 12, "frames": [
   {"type": "group", "layers": [{"type": "svg", "svg": "..."}, {"type": "brush", "strokes": [...]}]},
   {"type": "svg", "svg": "...", "hold": 2}, ...]}
```
و`"output": {"kra": ..., "png": ..., "mp4": ..., "gif": ...}`.
- كل فريم ممكن يبقى `svg` أو `brush` أو `image` أو `group` (كذا طبقة مع بعض في نفس الفريم). وكل فريم بيبقى **keyframe حقيقي** على طبقة رسم واحدة في التايملاين.
- `hold` بيمدّ الفريم لأكتر من فريم، و`poster` بيحدد رقم الفريم اللي يطلع في الـ PNG.
- **ليه مرورين؟** Krita من غير واجهة مابيعرفش يعمل keyframes: `importAnimation` بيوقع، و`setPixelData` على طبقة متحركة مابيضيفش keyframe. فالمرور الأول بيرسم الفريمات كطبقات، و`scripts/kra_animate.py` بيربطهم بملف `keyframes.xml` (نفس الصيغة اللي Krita بيكتبها بنفسه)، والمرور التاني بيفتح الملف ويضبط الـ fps ويصدّر الفريمات، وبعدين ffmpeg بيعمل MP4 (yuv420p) وGIF.
- اكتب سكربت يولّد الفريمات بالحساب (sin/cos للحركة). القالب الجاهز في `examples/heart_beat/make_scene.py`، والمعاينة في `preview_frames.png`.
- **الوقت:** حوالي 3 ثواني لكل فريم `group`، وحوالي 1.5 ثانية لكل فريم svg. يعني 16 فريم مركّب ≈ 47 ث (مقاس). الفيديو لازم خلفيته معتمة، لأن الشفاف بيطلع أسود في MP4.

## نصوص وعربي
- النص العربي بيتشكّل صح، والإنجليزي والأرقام جواه في مكانهم، وبيفضل **نص Krita قابل للتعديل** جوه ‎.kra.
- **المحاذاة:** مع `direction="rtl"` حط **x عند الحافة اليمين** واستخدم `text-anchor="start"`، أو `middle` للتوسيط. `end` بيطلّع الجملة برة الكانفس من اليمين.
- **اتجرّب وشغال:** `font-weight="bold"`، وتدرّج على النص (`fill="url(#g)"`)، وإطار ورا الحروف (`stroke` + `paint-order="stroke"`).
- **الخطوط اللي اتجرّبت:**
  - Arial، وTahoma، وSegoe UI، وSakkal Majalla، وTraditional Arabic، وArabic Typesetting.
  - **Aldhabi** خط خطّاطي ممتاز للأسماء، بس بيطلع أصغر من مقاسه، فكبّره حوالي 1.6×.
  - لعرض الخطوط العربي المتثبتة: `powershell "Get-ChildItem C:\Windows\Fonts | ? Name -match 'arab|naskh|kufi|majalla|aldhabi|typesetting|sakkal|amiri|cairo|tajawal' | select Name"`.
- **الخط لو مش متثبت** Krita بيرجع لخط serif افتراضي **من غير أي رسالة خطأ**، فبُص على الـ PNG بعينك دايمًا.

## وصفات جاهزة
- **ملمس ورق:** `{"type":"fill","name":"ملمس ورق","color":"#808080","blend":"overlay","opacity":0.12,"filters":[{"name":"noise","config":{"level":40,"opacity":60,"grayscale":true}}]}` فوق كل الطبقات.
- **توهج:** جروب `blend:"screen"` جواه شكل فاتح عليه `gaussian blur` بـ `horizRadius`/`vertRadius` حوالي 40–60.
- **ظل ناعم:** نسخة سودة من الشكل بـ `opacity` حوالي 0.3، وعليها `gaussian blur`، وتحت الشكل الأصلي ومزاحة شوية بـ x/y.

## الوقت المتوقع
- **أول تشغيل بعد فتح الجهاز** ممكن ياخد حوالي دقيقتين (اتقاس 131 ث)، غالبًا لأن Krita بيتحمّل لأول مرة (ماتقاسش السبب). التشغيلات اللي بعده بترجع للأرقام اللي تحت.
- لو Krita خلّص وحفظ وماقفلش لوحده (حصلت مرة واتقاست)، السكربت بيقفله بعد 15 ث من علامة النهاية بدل ما يستنى `--timeout`، و`krita_exit` بيبقى `finished; closed after 15s grace` والناتج سليم.
- تقريبًا 3 ثواني ثابتة، وحوالي 0.25 ثانية لكل طبقة فيكتور أو جروب أو Fill، وحوالي 0.4 ثانية لكل فلتر مقصوص. يعني مشهد بسيط ~4–8 ث، وبطاقة كاملة بـ 25 طبقة فيكتور ~18–21 ث (مقاس). والفرشاة بتاخد ثواني على الجهاز قبل Krita لو فيها مئات الضربات الكبيرة.

## ترتيب الطبقات في التقارير
- المشهد و`layers[]` في ناتج `render` الاتنين **من تحت لفوق**، والجروب بييجي بعد أولاده، وخانة `parent` بتقول كل طبقة جوه أنهي جروب.
- `krita_draw.py layers file.kra` بيقرا الملف نفسه **من فوق لتحت** مع `depth`، زي لوحة الطبقات في Krita.

## لما حاجة تبوظ
- `crashed_in_step` في الناتج بيقول Krita وقع في أنهي طبقة. شغّل بـ `--keep` وافتح `job_dir/result.json` (فيه trace).
- `filter ... unknown`: الاسم لازم يبقى من `references/krita_live_info.json`. لو Krita اتحدّث، شغّل `krita_draw.py info` عشان يكتب الملف ده من جديد، أو `info --out ملف.json` لو مش عايز تكتب جوه مجلد المهارة.
- شغّل `krita_draw.py doctor` عشان يتأكد إن Krita متثبت وnumpy وPillow موجودين، ويركّب سكربت Krita.
- blend mode غلط: قارن `layers[].blend` الراجع باللي طلبته. Krita بيرجع `normal` بهدوء لو الاسم مش معروف.

## حاجات تتعرف
- السكربت بيكتب ملف واحد بس برة مجلد الشغل: `%APPDATA%\kritarunner\pykrita\claude_krita_job.py` (نسخة من `scripts/krita_job.py`، وبتتحدّث لوحدها لو اتغيّرت). وده مالوش أي تأثير على Krita العادي.
- **الرسم الحي بفُرش Krita الأصلية الـ 137** (وإنت شايف): الإضافة جاهزة في `live_plugin/claude_bridge`، والتحكم من `scripts/krita_live.py` (status، install، start، run job.py، quit، uninstall)، وطريقة الاستخدام مشروحة في أول ملف الإضافة.
  - **مش متركّبة.** التركيب بيضيف إضافة دايمة جوه Krita بتنفّذ أي سكربت يتحط في `%APPDATA%\krita\claude_bridge\inbox`، فلازم موافقة صريحة من المستخدم الأول، وKrita يبقى مقفول.
  - `quit` بيقفل Krita **من غير ما يسيّف**، فاسأل الأول.
  - ❓ لسه مااتجربتش جوه Krita الحقيقي.
