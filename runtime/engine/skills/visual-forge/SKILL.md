---
name: visual-forge
description: >-
  مصنع الصورة — بيعمل صور احترافية بـ ChatGPT وفيديوهات حركة بـ Kling بطريقة مبنية على خطة وخطوات:
  بريف ← 3 كونسبتات ← كتاب لوك ← قايمة لقطات ← برومنتات متفحوصة (lint) ← توليد ← مؤثرات جوية محلية ← فحص.
  فيه مولّد خطة (plan.md + plan.json)، وباني برومنت لـ ChatGPT Images ولـ Kling image-to-video، وفاحص برومنت
  بيمسك الأخطاء قبل صرف أي كريدت، و20 جو جاهز (مطر، عاصفة، ثلج، شبورة، عاصفة رملية، أشعة، ساعة ذهبية، نيون، جمر، دخان، سراب...)،
  ومحرك مؤثرات محلي ببلاش بيطبّق مطر/ثلج/ضباب/غبار/جمر/أشعة/برق/سراب/بلوم/تسريب ضوء/فينيت/جريد/تلوين على الصور والفيديو مع الحفاظ على الصوت.
  Use for «صورة بشات جيبتي»، «برومنت صورة»، «برومنت كلينج»، «حوّل الصورة لفيديو»، «مؤثرات جوية»، «مطر/ثلج/ضباب/شبورة على الفيديو»،
  «لوك سينمائي»، «حملة صور»، «ثبات الشخصية»، ChatGPT image prompt, GPT image, DALL-E style prompt, Kling prompt, image-to-video,
  weather effects, atmosphere FX, rain/snow/fog overlay, god rays, film grain, color grade, shot list, look bible.
---

# Visual Forge — مصنع الصورة

**المبدأ:** الخطة الأول، البرومنت تاني، والكريدت آخر حاجة. كل خطوة ليها مُخرج مكتوب وبوابة لازم تعدّيها.

```
S=C:\Users\cinde\.claude\skills\visual-forge\scripts\forge.py
python $S plan --brief "<كلام المستخدم>" --kind image|video|campaign --shots 4 --ratio 9:16 --out <مجلد الشغل>\<job>
python $S atmos                 # قايمة الأجواء الـ20 — و: python $S atmos storm
python $S prompt <job>\plan.json   # يكتب prompts\image_NN.txt + video_NN.txt + fx_NN.txt ويعمل lint
python $S lint file.txt --target gpt|kling
python $S fx in.png out.png --fx "@storm"                  # أو وصفة: "rain:0.7,fog:0.4,grade:night_blue:0.5,grain:0.3"
python $S fx in.mp4 out.mp4 --fx "@snow" --seconds 3      # معاينة أول 3 ث؛ الصوت بيتحفظ
python $S self-test             # لازم PASS قبل أول استخدام في الجلسة
```
Exit: 0 تمام، 1 فيه برومنت FAIL، 2 خطأ استخدام. `fx` بيرفض يكتب فوق الملف الأصلي.

## سير العمل (8 مراحل — التفاصيل في references/plan-protocol.md)

0. **البريف** — اقرا طلب المستخدم، شغّل `plan`، واملأ قسم 0 في `plan.md`. اللي ناقص وأثره صغير: افترضه واكتبه. اللي أثره كبير: سؤال واحد.
1. **الكونسبت** — 3 اتجاهات متباعدة فعلًا في الجدول، واختار واحد بسبب. (للأفكار الأصلية استعين بـ `absolute-creativity`.)
2. **كتاب اللوك** — املأ `look` في `plan.json`: lighting, lens, atmosphere (اسم من `atmos`), style, color, **anchors** (وصف الشخصية/المنتج حرفيًا). كل قيمة جملة إنجليزي جاهزة.
3. **اللقطات** (لقطة مفيهاش الشخصية/المنتج؟ حط فيها `"anchors": ""`؛ و`atmosphere` بتقبل اسم جو أو جملة حرة أو الاتنين بفاصلة) — لكل shot: purpose, subject, action, setting, time, camera{framing,angle,lens}, composition, text, avoid، وللفيديو: motion (فعل واحد + كلمة سرعة)، camera_move (واحدة)، duration 5/10.
4. **البرومنتات** — `prompt plan.json`. أي FAIL يتصلح في `plan.json` ويتعاد البناء (ماتعدلش ملف txt بإيدك وتنسى الخطة). اقرا الـ warnings وقرر.
5. **الصور (ChatGPT)** — المستخدم يلزق `image_01.txt` (الماستر) الأول. لما ترجع الصورة: Read عليها وراجع (أيدي، عيون، نص، لوجو، نور). بعدين باقي اللقطات في نفس المحادثة مع الماستر كمرجع. تعديل واحد في كل رسالة. (references/chatgpt-image.md)
6. **الحركة (Kling)** — `video_NN.txt` مع الصورة كـ start frame، 5 ث تجربة ثم 10 ث. (references/kling-video.md)
7. **البوست والفحص** — الطبقة الجوية الموحّدة `fx` (الوصفة جاهزة في `fx_NN.txt`)، النص العربي بخط حقيقي في البوست، `verify_media`، فريمات بالعين، `sources.txt`، وتشيك ليست قسم 7.

اكتب كل قرار في «سجل القرارات» آخر `plan.md`.

## المؤثرات المحلية (ببلاش، مفيش API)
| المؤثر | وصفه | ملاحظات |
|---|---|---|
| `grade:<preset>:v` | تلوين: teal_orange, golden, night_blue, cold, bleach, desert, neon, fire | دايمًا الأول |
| `rain:v` `snow:v` | جزيئات متحركة بعمق (قريب/بعيد) | المطر بيبان أكتر في المناطق المنورة |
| `fog:v[:tint]` | ضباب متحرك أكثف تحت؛ tint: sand, smoke, blue, warm, white, green | |
| `dust:v` | ذرات في الضوء؛ v≥0.7 = رمل بتدفعه ريح | |
| `embers:v` | جمر طالع لفوق بيلمع | |
| `godrays:v` + `--light x,y` | أشعة من مصدر النور (كسور 0..1) | محتاج منطقة منورة في الكادر |
| `lightning:v` | ومضات برق (فيديو بس) | |
| `heat:v` | سراب/تموج حراري | تحت الماء: heat خفيف + godrays |
| `bloom:v` `leak:v` | توهج الهايلايت، تسريب ضوء فيلم | |
| `vignette:v` `grain:v` | فينيت وجريد فيلم | دايمًا الآخر |
`@اسم` بيجيب وصفة الجو الجاهزة، وتقدر تخلطهم: `"@fog,grain:0.4"`. الترتيب ثابت جوه المحرك مهما كتبت. (references/atmosphere-fx.md)

## قواعد مش بتتكسر
- **فلوس**: ChatGPT وKling (أو Higgsfield `generate_image`/`generate_video`) بيصرفوا اشتراك/كريدت. الافتراضي: إحنا نجهز البرومنتات والمستخدم يولّد. التوليد من هنا بس بعد عرض العدد × السعر وموافقة مكتوبة صريحة.
- **عربي جوه الصورة = لأ**. البرومنت إنجليزي، والعنوان العربي يتحط في البوست. الحوار العربي = voice-over.
- **مفيش حشو** (8k, masterpiece...). اوصف نور وخامة وعدسة.
- **الثبات**: نفس جملة الـ anchors في كل برومنت، نفس المحادثة، الماستر كمرجع.
- **ماتقولش اتعمل** غير لما تشوف الصورة بـ Read أو تقيس الفيديو بـ ffprobe/verify_media.
- الملفات الأصلية ماتتكتبش فوقها؛ النواتج في `<job>\output`.

## المراجع
- `references/plan-protocol.md` — التفكير بالخطة، شجرة «المؤثر في البرومنت ولا في البوست»، علاج المشاكل.
- `references/chatgpt-image.md` — هيكل البرومنت، التعديل، الثبات، النص، وصفات جاهزة.
- `references/kling-video.md` — هيكل برومنت الحركة، قاموس الكاميرا، الإعدادات، الفحص.
- `references/prompt-lexicon.md` — النور، العدسات، التكوين، الألوان، الخامات، المشاعر ← قرارات.
- `references/atmosphere-fx.md` — الأجواء الـ20 ووصفات المؤثرات وأمثلة.
- `data/atmospheres.json` — مصدر واحد للأجواء (عبارة الصورة + عبارة الحركة + منطق النور + وصفة fx).
- مهارات جارة: `kosif-kling-director` (أفلام Kling متعددة البلوكات)، `absolute-creativity` (أفكار + خط عربي)، `blender-pro` (3D)، `media-hunter` (فوتيج ومراجع).
