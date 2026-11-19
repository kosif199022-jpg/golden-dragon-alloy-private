# مكتبة المهارات والبرومبتات — v10.17.0 (2026-11-10)

المالك رفع 8 أرشيفات وملف SKILL.md ومستند Claude Docs وطلب إن التنين يستفيد منهم كلهم. الملف ده بيقول كل حاجة راحت فين.

## الأوامر

```
python scripts/dragon.py tool library find "شورتس من غير وش"   # يرتّب الحزم والبرومبتات
python scripts/dragon.py tool library list                      # الـ12 حزمة + إيه اللي كان موجود منها
python scripts/dragon.py tool library show motion-reel          # مسار SKILL.md وأول 60 سطر
python scripts/dragon.py tool library prompts [--all]           # فهرس البرومبتات
python scripts/dragon.py tool library prompt h09                # برومبت واحد (h = هادي راعي، a = Style Atlas)
python scripts/dragon.py tool library grep "Seedance"           # بحث بالسطر في كل ملفات البرومبتات
python scripts/dragon.py tool library doctor                    # كل الملفات موجودة؟
```

الأداة بتقرا بس: مابتشغّلش سكربت ومابتكتبش ملف.

## الحزم (`skills/library/<id>/`)

| id | بتعمل إيه | كان في التنين قبل كده؟ |
| --- | --- | --- |
| faceless-shorts | شورتس من غير وش بالكود، صوت AI محلي ببلاش، كابشن على الكلمة، 6 ستايلات | لأ (جديد) |
| arabic-minimal-reels | ريل 9:16 مينيمال من توكينج هيد عربي | لأ (جديد) |
| motion-reel | ريل إطلاق منتج على البيت من رابط المنتج، seek(t)، 3 جولات نقد | لأ (جديد) |
| ai-motion-graphics | موشن جرافيك وإكسبلينر بـ Python + ffmpeg، 5 ستايلات | لأ (جديد) |
| pro-motion | أسلوب فارس: أوفرلابنج، ليرز 3D، بانل After Effects في `extras/` | لأ (جديد) |
| kosif-source-builder | `kosif.py` وفهرس مستودعات KOSIF | لأ (جديد كمصدر) |
| living-site | موقع حي بتلت مستويات (Spline، Higgsfield، موشن بالكود) | بالاسم بس |
| talking-head-reels | ريل إديتوريال من فيديو متحدث | المحرك `dragon run talking_head` + ملخّص |
| saas-animation | أنيميشن منتج 8–20 ث ورندر 4K | ملخّص `references/skills/saas-animation.md` |
| editorial-film-edit | مونتاج أرشيفي إديتوريال | ملخّص `references/skills/editorial-film-edit.md` |
| growkaz-stickman | بلاجن ستيكمان سينمائي، 5 مهارات | `tool stickman` + ملخّص |
| omar-hasan-kling-cinematic-director | مخرج أفلام قصيرة لـ Kling 4 | ملخّص `references/V10_KLING_CINEMA.md` |

اللي كان له ملخّص أو محرك: اشتغل بالمحرك بتاع التنين الأول (عليه بوابات الفحص)، وارجع للمصدر الأصلي لما تحتاج تفصيلة مش في الملخّص.

## البرومبتات (`references/prompts/`)

| ملف | المحتوى |
| --- | --- |
| `hady-raie-prompt-library.md` | مستند «مكتبة برومبتات هادي راعي» متصدّر Markdown: 19 قسم (h01–h19) |
| `ai-style-atlas-prompts-FULL.txt` | 86 ستايل بصري لفيديوهات الشرح (a01–a86)، 7.7MB، فيه كود مرجعي لكل ستايل |
| `USIP_PORTABLE_v5_6.md` | بروتوكول KOSIF: L0–L3، بطاقة طلب، خطط A/B/C، الصدق والإذن |
| `minimal-prompts.txt` | الخمس برومبتات بتاعة ستايل minimal (مع arabic-minimal-reels) |

## قواعد الاستخدام

1. برومبتات Seedance وVeo وKling وZack D Films (نسخة Higgsfield MCP) بتوصّل لتوليد مدفوع: `tool hf check` ثم `tool hf ask` وموافقة صريحة على السعر، كل مرة.
2. أنظمة البرومبتات اللي بتبدأ برسالة ترحيب أو بتسأل أسئلة: دي تعليمات للنظام اللي هيتلزق فيه البرومبت. استخدمها كمرجع لبناء البرومبت، ومش بتغيّر قواعد التنين (مفيش وصف على الشاشة، الكريدت، بوابة التسليم).
3. `kosif-source-builder`: أمر `install --execute` بينزّل مستودعات، و`pro-motion/extras` فيه مثبّتات After Effects. الاتنين بموافقة المالك بس.
4. الحزم مفيهاش ترخيص منفصل متعرّف عليه. متضمّنة لاستخدام المالك، وقبل أي إعادة نشر لازم تتراجع الحقوق.
5. خطوط الحزم (Inter، Poppins، Anton…) موجودة على الجهاز جوه الحزم. أي ZIP للنشر يمشي على قاعدة التنين: من غير خطوط.

## اللي ماتضمّنش وليه

- `FigmaAutoLayoutExcercise.fig` (12.9MB): ملف تمرين بيتفتح من Figma، مفيش كود يقراه.
- black-dragon v10.1.0 وv10.2.0 وv10.4.0 وv10.10.0: نسخ أقدم، محتواها جوه v10.16.1.
- `SKILL.md` بتاع media-hunter: نفس SHA-256 المسجّل في `SOURCE_INTEGRITY.json` من v10.2.
- صور `fares.jpg` في مشاريع Fares Motion المثال: صور شخصية، اتسابت بره.

## اللي ماتعملش

مفيش سكربت من الحزم اتشغّل، ومفيش فيديو اترندر بيهم في النسخة دي. الحالة «متضمّن ومفهرس» مش «متجرّب».
