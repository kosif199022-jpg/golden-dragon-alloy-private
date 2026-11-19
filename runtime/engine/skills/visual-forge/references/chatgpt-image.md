# ChatGPT Images — دليل البرومنت الاحترافي

الموديل اللي ورا الصور في ChatGPT (سلسلة GPT Image) بيفهم **لغة طبيعية وجمل كاملة** وبيلتزم بالتعليمات حرفيًا،
وبيقدر يعدّل على صورة موجودة ويحافظ على باقيها. ده معناه: اكتب زي ما بتكلم مدير تصوير، مش قايمة tags.

## هيكل البرومنت (بالترتيب ده)

1. **النوع + الموضوع + الفعل**: `Create a cinematic photograph of an old fisherman mending a net on a wooden boat.`
2. **Anchors (الثبات)**: `Keep these details exactly: grey beard, navy wool cap, scar over the left eyebrow.`
3. **المكان والزمن**: `Setting: Alexandria harbor at dawn.`
4. **الجو**: من `forge.py atmos <name>` (مطر/شبورة/أشعة ...).
5. **النور**: مصدر + اتجاه + جودة + لون: `Low warm sun from camera left, soft fill from the sea, deep shadows on the right side of the face.`
6. **الكاميرا**: حجم اللقطة + الزاوية + العدسة: `Medium close-up, eye level, 85mm lens, f/2, shallow depth of field.`
7. **التكوين**: `Subject on the left third, negative space on the right for a title.`
8. **الستايل واللون**: `Natural film look, gentle grain, muted teal and amber palette.`
9. **النص** (لو فيه): إنجليزي بين علامات تنصيص `"..."` + مكانه + الخط. **العربي لأ** (شوف تحت).
10. **Avoid** + **المقاس**: `Avoid: plastic skin, oversaturated colors. Aspect ratio 9:16.`

`forge.py prompt plan.json` بيبني الهيكل ده أوتوماتيك من الخطة.

## المقاسات
ChatGPT بيطلع أصلًا مربع أو طولي أو عرضي (حوالي 1024×1024 / 1024×1536 / 1536×1024).
9:16 و16:9 الدقيقين: اطلب portrait/landscape وبعدين اقصّ أو كبّر محليًا (`upscayl-bin`، أو `magick -resize`). اكتب المقاس في آخر البرومنت دايمًا.

## التعديل (Edit) — أقوى حاجة في ChatGPT
- **تعديل واحد في كل رسالة**: «Change only the sky to a stormy sunset. Keep everything else exactly the same.»
- قول اللي **يفضل ثابت** صراحة: الوش، اللبس، اللوجو، التكوين.
- للتعديل الموضعي: استخدم أداة التحديد في ChatGPT وارسم على الجزء، واكتب التعديل.
- بعد 4-5 تعديلات متتالية الجودة بتقل: ابدأ من آخر نسخة كويسة في رسالة جديدة بالبرومنت الكامل المحدّث.

## الثبات بين اللقطات (شخصية / منتج)
1. ولّد **ماستر** (portrait واضح للشخصية أو packshot للمنتج على خلفية سادة).
2. كمّل في **نفس المحادثة** وارفع الماستر مع كل لقطة جديدة: «Use the attached image as the exact reference for the character's face, hair and clothes.»
3. كرّر جملة الـ Anchors حرفيًا. ماتغيرش الوصف بكلمات مرادفة.
4. للمنتج: «preserve the exact logo, label text, shape and proportions».
5. Character sheet: «A character reference sheet: front, 3/4, profile and back views, neutral grey background, same outfit» — مفيد قبل الفيديو.

## النص في الصورة
- الإنجليزي: ممتاز لو حطيته بين `"..."` وحددت الخط والمكان: `the headline "NIGHT SHIFT" in bold condensed sans-serif, top center`.
- **العربي: غالبًا بيطلع مقطّع أو الحروف مش متصلة.** الحل المعتمد: البرومنت يطلب «clean negative space for a title, no text»، والنص العربي يتعمل في البوست بخط حقيقي
  (مهارة `absolute-creativity` → معمل الخطوط العربي، أو `magick`/Blender).

## كلمات بتبوظ النتيجة (امسحها)
`8k, 4k, masterpiece, best quality, ultra realistic, hyper detailed, trending on artstation, octane render, unreal engine`
الموديل الحديث مش محتاجها، وبتطلع لوك بلاستيك لامع. بدلها: اوصف **النور والخامة والعدسة**.

## وصفات جاهزة (عدّل الأقواس)

**بورتريه سينمائي**
```
Create a cinematic portrait of [subject], [expression/action].
Setting: [place], [time].
Lighting: a single soft key light from [direction] through [window/softbox], natural falloff into deep shadow, subtle rim light separating the hair from the background.
Camera: close-up, eye level, 85mm lens at f/1.8, shallow depth of field, focus on the eyes.
Style: natural skin texture with visible pores, gentle film grain, [palette] palette.
Avoid: plastic skin, heavy retouching. Aspect ratio [ratio].
```

**إعلان منتج**
```
Create a premium product photograph of [product], preserving the exact logo, label and shape.
Setting: [surface] against [background], [props].
Lighting: hard top-back light creating a crisp rim and a long reflection, soft fill from the front, controlled specular highlights on [material].
Camera: [hero angle] , 100mm macro lens, everything in focus.
Composition: product centered, generous negative space at the top for a headline.
Color: [brand colors]. No text. Aspect ratio [ratio].
```

**مشهد جوّي واسع (للتحويل لفيديو بعدين)**
```
Create a cinematic wide shot of [subject small in frame] in [landscape].
Atmosphere: [from forge.py atmos].
Lighting: [backlight/side light] so the atmosphere is visible, layered depth from foreground to background.
Camera: wide shot, 24mm lens, low angle, foreground element in the lower third.
Style: anamorphic film look, subtle halation, muted palette. Aspect ratio 16:9.
```
نصيحة: الصورة اللي هتتحرك في Kling لازم يكون فيها **مساحة للحركة** (مش قافلة على الموضوع) وحاجة واضحة تتحرك (قماش، شعر، دخان، مية).

## مسارات التنفيذ
- **ChatGPT (اشتراك المستخدم)**: إحنا بنجهز البرومنتات في `prompts/image_NN.txt`، المستخدم يلزقها ويرجّع الصور في مجلد `images/`. ببلاش.
- **Higgsfield MCP** (`generate_image`, الموديل الافتراضي gpt_image): بيصرف كريدت ← اعرض السعر واستنى «موافق» مكتوبة.
- بعد ما الصور ترجع: افتحها بـ Read (view_image) وراجع: الأيدي، العيون، النص، اللوجو، الثبات مع الماستر.
