---
name: physics-math
description: حاسبة الرياضيات والفيزياء للمونتاج والموشن والـ 3D — أحجام ومساحات وأوزان وكثافات، تحويل وحدات، سقوط حر ومقذوفات وارتداد كورة وسبرينج بكيفريمات فريم بفريم، منحنيات Easing وcubic-bezier، حسابات الكاميرا (FOV، مسافة التصوير، عمق الميدان، Dolly Zoom/Vertigo، الشاتر والموشن بلر، البارالاكس)، تايم كود وفريمات، سلو موشن وتسريع بفلاتر ffmpeg، BPM لفريمات القطع، تحجيم وقص من 16:9 لـ 9:16 والمناطق الآمنة، dB وLUFS، سرعة جسم من البكسلات، وتصوير المجسمات المصغّرة. Use whenever a montage, motion-graphics, VFX or Blender task needs a real number: «احسب»، «حجم»، «وزن»، «مسافة»، «سرعة»، «جاذبية/سقوط»، «فيزياء واقعية»، «ارتداد»، «إيزينج»، «فريمات»، «تايم كود»، «سلو موشن»، «BPM/على الإيقاع»، «عدسة/فوكال/عمق ميدان»، «قص 9:16»، «LUFS»، volume, weight, density, unit conversion, free fall, projectile, bounce, spring, easing curve, keyframes, focal length, FOV, depth of field, dolly zoom, shutter angle, motion blur, timecode, retime, beat sync, aspect ratio, safe zones, loudness. Prefer it over mental math — never guess a physical number.
---

# الفيزياء والرياضيات للمونتاج

قاعدة واحدة: **أي رقم فيزيائي أو رياضي في المونتاج يتحسب بالأداة دي، مش من الدماغ.** الحركة اللي ماشية بقوانين الفيزياء الحقيقية هي اللي بتبان طبيعية للعين.

الأداة: `scripts/phys.py`. بايثون عادي من غير مكتبات إضافية، وكل أوامرها بتطلّع JSON.

```bash
PHYS="python C:/Users/cinde/.claude/skills/physics-math/scripts/phys.py"
$PHYS <command> --help
```

## الأوامر

| الأمر | بيعمل إيه | مثال |
|---|---|---|
| `calc` | آلة حاسبة آمنة (فيها `sqrt sin log pi g c sound deg`، و`^` معناها أُس) | `calc "sqrt(2*20/g)"` |
| `convert` | تحويل وحدات: طول، كتلة، زمن، سرعة، عجلة، مساحة (منها الفدان)، حجم، زاوية، قوة، طاقة، قدرة، ضغط، كثافة، بيانات، بت ريت، تردد، حرارة | `convert 100 km/h m/s` · `convert 2.5 GB Mbit` |
| `shape` | مساحة ومحيط وحجم وسطح لـ 16 شكل، ومع `--material` أو `--density` بيحسب الكتلة والوزن وهل الجسم بيطفو | `shape cylinder --r 5 --h 20 --unit cm --material water` |
| `material` | جدول كثافات حوالي 60 مادة (kg/m³) | `material` |
| `motion` | مسافة وسرعة وزمن: تديله اتنين ويحسب التالت، ومع `--fps` بيطلّع عدد الفريمات | `motion --distance 100 --speed 12 --fps 24` |
| `fall` | سقوط حر من ارتفاع أو لمدة زمنية، ومع `--drag` بيحسب مقاومة الهوا بالسرعة الحدّية | `fall --height 20 --fps 24 --out fall.csv` |
| `projectile` | جسم مرمي: المدى وأعلى نقطة وزمن الطيران وكيفريمات x/y | `projectile --speed 20 --angle 45 --h0 1.5 --keys` |
| `bounce` | كورة بتنط: فريم كل لمسة للأرض وارتفاع كل نطّة | `bounce --height 2 --restitution 0.75 --fps 30` |
| `spring` | سبرينج مُخمَّد (overshoot) للوجوهات والنصوص | `spring --start 0 --end 100 --damping 12 --out pop.json` |
| `ease` | قيمة كل فريم لأي منحنى Easing أو cubic-bezier | `ease easeOutBack --seconds 0.8 --fps 30 --start 0 --end 1080` |
| `camera fov` | زاوية الرؤية والكروب فاكتور، وعرض الكادر على مسافة معيّنة، والفوكال المطلوب لزاوية معيّنة | `camera fov --focal 35 --sensor s35 --distance 3` |
| `camera fit` | الكاميرا تبعد قد إيه عشان الجسم يملا الكادر | `camera fit --object 1.8 --focal 50 --fill 0.8` |
| `camera dof` | عمق الميدان والهايبرفوكال | `camera dof --focal 85 --fstop 1.8 --distance 2` |
| `camera dolly` | Vertigo/Dolly Zoom: المسافة الجديدة اللي تثبّت حجم الشخص | `camera dolly --focal 24 --focal2 85 --distance 2` |
| `camera shutter` | زمن التعريض من زاوية الشاتر، وطول الموشن بلر بالبكسل | `camera shutter --angle 180 --fps 24 --px-per-frame 40` |
| `camera parallax` | كل طبقة تتحرك كام بكسل حسب عمقها (2.5D) | `camera parallax --move 0.5 --depths 1 3 10 50` |
| `tc` | تحويل بين تايم كود وفريمات وثواني، ومن fps لـ fps تاني | `tc --timecode 00:01:02:12 --fps 24 --to-fps 30` |
| `speed` | سلو موشن من فيديو متصوّر بـ fps عالي، أو تسريع لمدة معيّنة، وبيطلّع `setpts` و`atempo` جاهزين | `speed --shot-fps 120 --timeline-fps 24` · `speed --duration 10 --target 4` |
| `beats` | BPM لتوقيت وفريم كل ضربة، عشان القطع يبقى على الإيقاع | `beats --bpm 128 --fps 30 --duration 30 --every 2 --out cuts.csv` |
| `frame` | Fit وFill وإحداثيات القص وأوامر ffmpeg، والمناطق الآمنة ومنطقة واجهة الريلز | `frame --src 1920x1080 --dst 1080x1920` |
| `audio` | dB ونسبة الصوت، والجين المطلوب لـ LUFS معيّن والذروة بعده، وتأخير الصوت مع المسافة، والطول الموجي والنوتة | `audio --from-lufs -19.3 --peak -2.1` |
| `track` | سرعة جسم حقيقية من حركته بالبكسل، بمعلومية مقياس مرجعي | `track --px 40 --ref-px 420 --ref-m 1.75 --fps 30` |
| `scale` | مجسّم مصغّر يتصوّر بكام fps عشان يبان حقيقي، وجاذبية Blender لو مقياس الوحدات متغيّر | `scale --model-scale 16 --fps 24` |

**الأشكال:** `square(a) rect(a,b) circle(r) ellipse(a,b) triangle(a,b,c) cube(a) box(a,b,c) sphere(r) hemisphere(r) cylinder(r,h) tube(r,r2,h) cone(r,h) frustum(r,r2,h) pyramid(a,h) torus(r,r2) ellipsoid(a,b,c)`، و`--fill 0.6` معناها إن الإناء مليان 60%.

**الإيزينج:** `linear` و`ease{In,Out,InOut}{Sine,Quad,Cubic,Quart,Quint,Expo,Circ,Back,Elastic,Bounce}` و`cubic-bezier(x1,y1,x2,y2)`، وهي نفس صيغة CSS وAfter Effects.

**السنسورات:** `ff` و`aps-c` و`canon-apsc` و`s35` و`mft` و`1in` و`iphone` و`blender` و`65mm`، أو `--sensor-w/--sensor-h` بالمللي.

**الكيفريمات:** `--keys` بتحطها جوه الـ JSON، و`--out file.csv|json` بتحفظها في ملف. الملف ده ينفع يتقرا في Blender (`fcurve.keyframe_points`)، أو في Remotion/HyperFrames، أو يتحوّل لتعبير ffmpeg.

## إمتى تستخدم إيه في المونتاج

- **حاجة بتقع أو بتترمي أو بتنط في موشن جرافيك أو 3D:** استخدم `fall` أو `projectile` أو `bounce` بالـ fps بتاع التايملاين، واعمل الكيفريمات من الملف. ماتعملهاش بالإيزينج بالعين.
- **نص أو لوجو بيدخل بـ pop:** استخدم `spring`. نسبة تخميد 0.3 لـ 0.5 حركتها مرحة، و0.7 ناعمة زي حركة واجهات التطبيقات.
- **القطع على الموسيقى:** `beats` بالـ BPM (هاته من librosa أو `audio-analysis`)، وظبّط `--offset` على أول ضربة.
- **سلو موشن:** `speed --shot-fps` لو الفيديو متصوّر بـ fps عالي. ولو مش كده، الأداة هتنبّهك إنك محتاج RIFE أو minterpolate.
- **تحويل لريلز 9:16:** `frame` بيقولك هتحتفظ بكام في المية من الصورة، وفين تحط النص بعيد عن واجهة التطبيق.
- **كاميرا Blender:** `camera fit` و`camera dolly` و`camera dof`. وخلّي المشهد بالمتر وبالحجم الحقيقي عشان الفيزياء تطلع صح.
- **الصوت:** `audio --from-lufs` بعد ما تقيس بـ `verify_media` أو `loudnorm`. الهدف للسوشيال -14 LUFS، والذروة ماتعديش -1 dBTP.
- **سؤال فيزيا أو رياضة عام** (حجم أو وزن أو مسافة): `shape` أو `convert` أو `calc`.

## تنبيهات

- السقوط من غير `--drag` معناه سقوط في فراغ. للكورة استخدم `--drag 20`، ولمظلّي قبل ما يفتح البراشوت `--drag 55`.
- `camera fit` و`dolly` مبنيين على تقريب العدسة الرفيعة، وده دقيق كفاية لما الجسم يكون أبعد من حوالي 10 أضعاف الفوكال.
- التايم كود هنا non-drop. لو الفيديو 29.97 والتايم كود drop-frame، نبّه المستخدم إن ممكن يكون في فرق.
- `track` بيكون صح بس للحركة العرضية في نفس عمق الجسم المرجعي.
