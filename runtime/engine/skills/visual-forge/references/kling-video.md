# Kling — دليل فيديو الحركة من الصورة

Kling أقوى ما يكون في **image-to-video**: صورة ChatGPT هي الـ start frame، والبرومنت يوصف **الحركة بس**.
للأفلام الطويلة متعددة البلوكات (30 ث+) استخدم مهارة `kosif-kling-director`. المهارة دي للّقطة الواحدة 5-10 ث.

## هيكل برومنت الحركة

```
[Subject + anchor] [one clear action with a speed word]. [Scene detail that moves: hair, cloth, smoke, water].
[Atmosphere motion]. Camera: [ONE move, maybe two]. [Light change if any]. [Style].
NEGATIVE: morphing, warped hands, extra fingers, flicker, distorted face, text, watermark, jitter
```

مثال:
```
PROMPT:
An old fisherman (grey beard, navy wool cap) slowly pulls the net out of the water, droplets falling from the mesh.
Fog rolls slowly across the harbor behind him. Camera: slow push in. Warm dawn light grows on his face.
NEGATIVE:
morphing, warped hands, extra fingers, flicker, distorted face, text, watermark
SETTINGS: image-to-video, start frame image_01.png, 5s, 9:16, pro/master, cfg 0.5
```

## قواعد الذهب
1. **فعل واحد لكل لقطة** (أقصى حاجة 2 مترابطين). «then» أكتر من مرتين = قسّم اللقطة.
2. **حركة كاميرا واحدة** (أقصى 2). أكتر من كده = تشوّه.
3. **كلمة سرعة**: slowly, gently, suddenly, in slow motion — من غيرها Kling بيختار سرعة عشوائية.
4. **اوصف اللي في الصورة بس**: ماتطلبش حاجة مش موجودة في الـ start frame تظهر فجأة إلا لو ده المقصود.
5. **النفي في خانة NEGATIVE** مش جوه البرومنت.
6. **إنجليزي فقط** — الحوار العربي يتسجل voice-over في المونتاج (مفيش lip-sync عربي مضمون).
7. **بلاش أسماء كاميرات/ماركات**؛ اوصف اللوك.
8. ابدأ بـ **5 ث** للاختبار؛ لما الحركة تظبط اعمل 10 ث.

## قاموس حركات الكاميرا (اكتبها كده بالظبط)
| الحركة | العبارة | إمتى |
|---|---|---|
| دخول بطيء | `slow push in` / `slow dolly in` | توتر، اكتشاف، تركيز على مشاعر |
| خروج | `slow pull back` | كشف المكان، وحدة، نهاية |
| لف حوالين | `slow orbit around the subject` | بطل، منتج، لحظة ذروة |
| رفع | `crane up revealing the city` | ختام ملحمي، كشف |
| متابعة | `tracking shot following the subject from behind` | رحلة، مطاردة |
| جانبي | `truck left` / `truck right` | باراللاكس مع foreground |
| يد | `subtle handheld` | واقعية، وثائقي |
| ثابت | `static locked-off camera` | الحركة كلها من الموضوع/الجو |
| درون | `aerial drone shot slowly flying forward` | مناظر واسعة |
| فوكس | `rack focus from the foreground to the subject` | ربط عنصرين |

## الجو المتحرك (بيتولد من `forge.py atmos`)
- مطر: `rain falls continuously, droplets splash in the puddles` (الموديل بيعمل مطر حلو لو الصورة أصلًا مبلولة).
- ضباب: `fog rolls slowly across the ground`.
- ثلج: `snowflakes drift down slowly and sway in a light wind`.
- جمر: `embers rise and swirl upward on the heat`.
- أشعة: `light shafts slowly sweep across the scene`.

## الإعدادات
- **Mode**: Professional/Master للنهائي، Standard للتجربة.
- **Duration**: 5 أو 10 ث (بعض الإصدارات 15).
- **cfg / Creativity vs Relevance**: 0.5 متوازن؛ ارفع (0.7) لو الموديل بيتجاهل البرومنت، وقلّل لو الحركة متخشبة.
- **Start + End frame**: صورتين من ChatGPT بنفس اللوك (مثلًا قبل/بعد العاصفة) = انتقال متحكم فيه.
- **Elements / reference**: لثبات الشخصية عبر لقطات كتير.
- **Motion brush** (لو متاح): حدد الجزء اللي يتحرك واتجاهه.

## بعد التوليد
1. استخرج 3 فريمات (بداية/نص/آخر) وشوفهم بعينك: `ffmpeg -i v.mp4 -vf "select='eq(n,0)+eq(n,60)+eq(n,119)',tile=3x1" -frames:v 1 check.png`
2. ابحث عن: تشوه الأيدي/الوش، وميض، عناصر بتذوب.
3. الطبقة الجوية الموحّدة + الجريد: `forge.py fx v.mp4 v_fx.mp4 --fx @<atmos>`.
4. `verify_media` على الناتج.

## التكلفة
Kling (مباشر أو عبر Higgsfield `generate_video`) **بيصرف كريدت**. ممنوع التوليد قبل:
عرض البرومنتات + عدد اللقطات × المحاولات + السعر، وموافقة مكتوبة من المستخدم. الافتراضي: نجهز البرومنتات والمستخدم يولّد بنفسه.
