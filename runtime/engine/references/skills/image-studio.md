# image_studio — استوديو الصور (التنين الأسود v1.2)

محرك صور سريع ومقاس، بيكمّل المونتاج: الغلاف، والعنوان، واللوك، والتكبير، وشيل الخلفية، والمراجعة بالعين.
كل أمر بيطبع سطر JSON فيه المسار والأبعاد والحجم ومتوسط الإضاءة (و`alpha_coverage` للـ PNG الشفاف)، فالتقرير يبقى أرقام مقاسة.

## الأوامر
```
dragon run image_studio title OUT "النص" [--src img] [--size 1080x1920] [--font cairo] [--px N] [--color #fff]
                                     [--stroke 0] [--pos center|top|bottom|lower-third] [--align center|right|left] [--glow #F5C04A] [--bg #0B0B0F]
dragon run image_studio reframe SRC OUT [--size 1080x1920] [--mode blur|cover|contain] [--focus 0.5,0.4]
dragon run image_studio grade SRC OUT [--look teal_orange] [--strength 1]
dragon run image_studio cover SRC OUT "العنوان" [--sub "سطر صغير"] [--look warm_gold] [--size 1080x1920] [--font cairo] [--accent #F5C04A]
dragon run image_studio upscale SRC OUT [--scale 4] [--model ultrasharp-4x|high-fidelity-4x|remacri-4x|digital-art-4x]
dragon run image_studio cutout SRC OUT.png [--model isnet-general-use]
dragon run image_studio sheet VIDEO OUT.jpg [--n 12] [--cols 4] [--width 360]
dragon run image_studio looks | fonts | measure FILE
```

## قرارات الذوق (ليه كده)
- **العربي:** Pillow بـ libraqm (تشكيل حقيقي واتجاه RTL). لو raqm مش موجود بيرجع لـ arabic_reshaper + bidi. الاختبار بيثبت إن «سلام» متوصلة (أعرض بـ 10% على الأقل أقل من الحروف المنفصلة).
- **حجم الخط بيتظبط لوحده** على 86% من عرض الكادر، فمفيش سطر بيخرج برّه الشاشة.
- **الريفريم `blur`:** الصورة كاملة فوق نسخة منها مغبشة ومعتمة (55%). ده الحل السينمائي للصور الأفقي في ريل رأسي، بدل القص اللي بيقطع الوشوش. لو النسبة قريبة من 9:16 الغلاف بيستخدم `cover` لوحده.
- **الغلاف:** ريفريم ← لوك ← تدرّج غامق تحت (عشان العنوان يتقري على أي صورة) ← عنوان Cairo 900 ← سطر فرعي ذهبي Tajawal.
- **اللوكات** في `engines/image_studio/data/grades.json` (lift/gamma/gain لكل قناة، تباين، تشبع، فينيت، حبيبات). تقدر تضيف لوك جديد بسطر JSON.
- **التكبير:** Upscayl (Real-ESRGAN على Vulkan، شغال من غير NVIDIA). `ultrasharp-4x` للصور الحقيقية، `digital-art-4x` للرسم والكرتون، `high-fidelity-4x` للوشوش. لو مش متثبت: Lanczos + Unsharp ومكتوب ده في `method`.
- **شيل الخلفية:** rembg بموديل `isnet-general-use` (أول مرة بينزّل الموديل مجانًا).
- **الشيت:** 12 فريم متوزعين بالتساوي وعليهم التوقيت. افتحه بـ view_image قبل ما تقول «خلص».

## الحدود
- مش بديل لـ Photoshop في الريتاتش الدقيق؛ ده للإنتاج السريع المتكرر. للريتاتش استخدم GIMP (`gimp-console-3.2`) أو Krita.
- الخطوط المدمجة كلها OFL؛ أي خط تاني مرره كمسار `.ttf`.
