# الأجواء والمؤثرات — Atmosphere & FX

كل جو له 4 أجزاء في `data/atmospheres.json`:
**image** (جملة لبرومنت ChatGPT) · **video** (جملة حركة لـ Kling) · **light** (منطق النور اللي يخلّي الجو يبان) · **fx** (الوصفة المحلية).
`python forge.py atmos <name>` بيطبعهم.

| الاسم | الجو | الوصفة المحلية |
|---|---|---|
| rain | مطر | night_blue + rain 0.7 + fog خفيف |
| storm | عاصفة رعدية | rain 1.0 + lightning + fog |
| drizzle | رذاذ | rain 0.3 + fog 0.35 + bleach |
| snow | ثلج | cold + snow 0.7 + bloom |
| blizzard | عاصفة ثلجية | snow 1.0 + fog أبيض 0.6 |
| fog | شبورة كثيفة | fog 0.65 + godrays |
| mist | شبورة خفيفة | fog 0.35 + golden |
| haze | غبشة دافية | fog + bloom + golden |
| sandstorm | عاصفة رملية | desert + fog رملي 0.7 + رمل بالريح |
| dust | غبار في شعاع | godrays + dust |
| godrays | أشعة إلهية | godrays 0.8 |
| golden_hour | الساعة الذهبية | golden + bloom + leak |
| blue_hour | الساعة الزرقاء | night_blue + bloom |
| neon_rain_night | ليل نيون ومطر | neon + rain + bloom |
| smoke | دخان | fog دخاني + godrays |
| embers | جمر وشرر | fire + embers + vignette |
| heat_haze | سراب حراري | heat + desert |
| aurora | شفق قطبي | cold + bloom |
| underwater | تحت الماء | cold + heat خفيف + godrays + particles |
| steam | بخار | fog + bloom |
| wind_leaves | رياح وأوراق | golden + leak |

## قواعد النور للأجواء (اللي بيفرق المحترف)
- **المطر والدخان والبخار والضباب بيبانوا بالنور الخلفي.** من غير backlight هيختفوا. اكتب مصدر النور ورا الموضوع.
- **الأسطح المبلولة بتضاعف كل مصدر نور** — اطلب reflections in wet pavement.
- **الثلج عاكس ضخم**: الظلال زرقا، والوش بيتنور من تحت.
- **العمق الجوي**: كل طبقة أبعد = أفتح وأزرق/أقل تباين. ده اللي بيخلي الضباب يحس بالمسافة.
- **البرق key light لفريم واحد** — باقي المشهد يفضل مظلم وبارد.

## أمثلة تشغيل
```
python forge.py fx shot.png shot_rain.png --fx "@rain"
python forge.py fx shot.png shot_rays.png --fx "godrays:0.8,fog:0.3,bloom:0.3" --light 0.7,0.1
python forge.py fx clip.mp4 clip_storm.mp4 --fx "@storm" --seconds 4     # معاينة
python forge.py fx clip.mp4 clip_storm.mp4 --fx "@storm"                 # كامل
python forge.py fx clip.mp4 clip_look.mp4 --fx "grade:teal_orange:0.4,grain:0.25,vignette:0.3"  # توحيد لوك كل اللقطات
```
- نفس `--seed` لكل اللقطات = نفس شخصية الجريد/الجزيئات. غيّره لو عايز توزيع مختلف.
- الكثافة: ابدأ 0.4–0.6. فوق 0.8 للعواصف بس.
- فيديو 1080×1920 بياخد تقريبًا 3–10 فريم/ث حسب عدد المؤثرات؛ للفيديو الطويل شغّله في الخلفية وابدأ بـ `--seconds 3`.

## مؤثرات أعقد (برا المحرك المحلي)
- **مطر/ثلج 3D حقيقي بيتفاعل مع المشهد، أو ضباب حجمي**: `blender-pro` (particles + volume scatter).
- **فصل الموضوع عشان المطر يبقى قدامه وورا**: `rembg` على الفريم → ركّب الطبقات (خلفية + fx + موضوع + fx خفيف).
- **مؤثرات Higgsfield الجاهزة** (presets بعواصف وانفجارات وتحولات): بتصرف كريدت — بموافقة.
