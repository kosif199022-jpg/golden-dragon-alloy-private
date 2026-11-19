# سريالي مينيمال أبيض وأسود (ST09) — على طريقة Hossein Zare — v1990.5.0

بطلب صاحب التنين: «ادرس فديوهات هذا الشخص وابني اسلوب ديزاين يشبهه» (instagram: hosseinzare.art) و«قلد الفديو تمام» (ريل «Hope fed no one»).
إنستجرام بيقفل صفحة البروفايل على الجهاز السحابي، فالدراسة اتعملت من الريل نفسه + مقالات عنه (SLR Lounge، Bored Panda، Designer Daily، Ignant).

## لغة التصميم (اللي بتخلي الشغل «زاري»)
1. **أبيض وأسود بس**، تباين عالي، فراغ أبيض كبير (negative space) — أفق واطي أو فراغ أبيض لانهائي (سبخة ملح مشقّقة، صحرا، بحر ساكن).
2. **التكرار لحد الأفق**: صفوف ناس/كراسي/أطباق بنفس الشكل بتصغر بالمنظور لحد نقطة التلاشي.
3. **الواحد اللي بيكسر النمط**: شخص واحد بيعمل حاجة مختلفة (بيقوم، بيمشي عكس، لونه مختلف) = الفكرة كلها.
4. **ناس من غير ملامح**: بدل سودا وقبعة فيدورا/بولر، ظهر أو جنب، ماحدش باصص للكاميرا.
5. **شمس حادة** وضلال طويلة واضحة مايلة لجهة واحدة.
6. **كاميرا ثابتة** (أو push بطيء جدًا)، والحركة الوحيدة هي الحدث.
7. **تعليق اجتماعي في جملة واحدة** (Hope fed no one / الأمل ماأكّلش حد) — بيتكتب في الكابشن مش على الفيديو.
8. موسيقى هادية / بيانو؛ مفيش كلام على الشاشة غير التوقيع.

## القالب
`template.html` = منظور حقيقي (world → screen): `P(X,Y,z)`, ترابيزة لانهائية، صفوف رجالة، أطباق وكاسات، شقوق ملح، ضل الشمس `SUN`، وواحد بيقوم ويمشي.
غيّر `ROWS/DZ/SX` للتكرار، و`leaver()` للحدث (بيقوم/بيمشي/بيقعد عكس)، و`DUR`. صفر كريدت.
**نسخة فوتوغرافية** (لو عايز شكل صورة حقيقية): `gpt_image_2_6` بالـ prompt:
`Surreal minimalist black and white fine-art photograph, vast white salt flat, [repeated element to the horizon], men in black suits and fedoras seen from behind, hard sunlight, long crisp shadows, huge negative space, 9:16` + تحريك Seedance Mini.

مراجع: https://www.slrlounge.com/inspiration-minimalist-black-and-white-photography-by-hossein-zare/ ، https://boredpanda.com/minimal-black-and-white-digital-art-hossein-zare
