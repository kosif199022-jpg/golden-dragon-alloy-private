# صيغة المشهد (scene.json)

الطبقات بالترتيب **من تحت لفوق**: أول طبقة في القايمة هي الأقرب للخلفية. المسارات النسبية بتتحسب من مكان ملف المشهد، والمسارات العربي مسموحة.

```json
{
  "canvas": {"width": 1080, "height": 1350, "background": "#f4efe6", "dpi": 72,
             "color": "RGBA", "depth": "U8"},
  "base": "optional/existing.kra",
  "layers": [ ... ],
  "python": "optional/extra.py",
  "output": {"png": "out.png", "kra": "out.kra", "jpg": "out.jpg", "quality": 92, "alpha": true}
}
```
- `background`: لون hex، أو `"transparent"` عشان تشيل طبقة الخلفية خالص.
- `base`: يفتح ‎.kra موجود ويحط الطبقات الجديدة فوقه، وساعتها `width`/`height` اختياريين.
- `output`: صيغ متاحة: png، jpg، webp، tif، psd، kra، وكمان mp4 وgif لو المشهد فيه طبقة `animation`. ولازم واحدة على الأقل.
- `color`/`depth`: الافتراضي RGBA/U8. فيه كمان GRAYA، وCMYKA، وLABA، وعمق U16/F16/F32. الفرشاة والصور بتتحط بـ U8 RGBA، فخلّيها الافتراضي إلا لو فيه سبب.

## خصايص مشتركة لأي طبقة
`name` (عربي عادي)، و`opacity` (0–1، أو 0–255)، و`blend`، و`visible`، و`locked`، و`alpha_locked`، و`x`/`y` (إزاحة)، و`filters`.

**blend** (اسم بسيط ← اسم Krita): normal، multiply، screen، overlay، darken، lighten، add، subtract، difference←diff، color_dodge←dodge، color_burn←burn، soft_light←soft_light_svg، hard_light، color، hue، saturation، luminosity←luminize، erase. وأي اسم Krita داخلي تاني بيعدّي زي ما هو. اتأكد دايمًا من `layers[].blend` الراجعة.

## الأنواع

### `svg`
```json
{"type": "svg", "name": "شمس", "svg": "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 1080 1350'>...</svg>"}
{"type": "svg", "name": "لوجو", "file": "logo.svg"}
```
- اكتب `viewBox="0 0 W H"` بمقاس الكانفس، والسكربت بيظبط `width`/`height` لوحده عشان وحدة SVG تساوي بكسل واحد عند أي dpi.
- شغالين: path، rect، circle، ellipse، polygon، line، text، linearGradient، radialGradient، stroke-linecap/linejoin، stroke-dasharray، opacity.
- كل عنصر في الـ SVG بيبقى shape منفصل في Krita، فاقسم الرسمة على كذا طبقة SVG بأسماء واضحة.
- النص العربي: `direction="rtl"` و`text-anchor="start"` وx عند الحافة اليمين.
- علامات التنصيص المفردة (`'`) والمزدوجة (`"`) الاتنين ماشيين. ولو فيه `width`/`height` على الـ root، السكربت بيستبدلهم.

### `brush`
```json
{"type": "brush", "name": "اسكتش", "seed": 7, "strokes": [
  {"points": [[100,400,0.2],[220,330,0.9],[380,380,1.0],[520,300,0.5]], "tip": "ink", "size": 14, "color": "#111827"},
  {"circle": [540,600,120], "tip": "pencil", "size": 6, "color": "#3b2f2f"},
  {"line": [80,900,1000,900], "tip": "chalk", "size": 30, "color": "#fde68a", "opacity": 0.8},
  {"arc": [540,600,200,200,340], "tip": "soft", "size": 80, "color": "#ffffff", "opacity": 0.5}
]}
```
| tip | الإحساس | تدبيب افتراضي |
|---|---|---|
| `ink` | حبر/قلم فرشاة، حافة حادة، والسُمك بيتغيّر مع الضغط | أيوه |
| `pencil` | رصاص بحبيبات ورق | أيوه |
| `soft` | فرشاة هوائية ناعمة بتتراكم | لأ |
| `chalk` | طباشير/باستيل خشن | لأ |
| `marker` | ماركر شفاف بيتراكم | لأ |
| `round` | دايرة ناعمة الحواف ثابتة | لأ |

خصايص إضافية: `smooth` (منحنى ناعم، افتراضي true)، و`closed`، و`taper: [بداية, نهاية]` (نسبة من الطول)، و`spacing` (0.08)، و`jitter` (بالبكسل)، و`seed`. الضغط (الرقم التالت في كل نقطة) بيتحكم في السُمك، وفي الشفافية كمان للرصاص والهوائي.

### `fill`
`{"type": "fill", "name": "ورق", "color": "#efe4d0"}`: طبقة Fill حقيقية في Krita (generator). لو عايز طبقة رسم عادية بلون واحد، زوّد `"editable": false`.

### `image`
`{"type": "image", "name": "مرجع", "file": "photo.png", "x": 0, "y": 0, "width": 540, "height": 540}`: لو حددت `width` و`height` الصورة بتتمطّ للمقاس ده.
مفيد لو رسمت جزء بمكتبة تانية (matplotlib، أو Pillow، أو صورة من Blender) وعايزه طبقة في Krita.

### `group`
`{"type": "group", "name": "نور", "blend": "screen", "opacity": 0.7, "layers": [ ... ]}`

### `file_layer` / `clone`
- `{"type": "file_layer", "name": "linked", "file": "x.png"}`: ملف مربوط بيتحدّث في Krita لو الملف اتغيّر.
- `{"type": "clone", "name": "نسخة", "source": "اسم طبقة موجودة"}`.

### `animation` (واحدة بس في المشهد)
```json
{"type": "animation", "name": "حركة", "fps": 12, "hold": 1, "poster": 0, "opacity": 1, "blend": "normal",
 "frames": [
   {"type": "svg", "svg": "<svg ...>"},
   {"type": "brush", "strokes": [...], "hold": 3},
   {"type": "image", "file": "frame_02.png"},
   {"type": "group", "layers": [ {"type": "svg", ...}, {"type": "brush", ...} ]}
 ]}
```
- النواتج: `kra` (تايملاين حقيقي: طبقة رسم واحدة عليها keyframe لكل فريم، والـ fps والمدى متظبطين)، و`png` (فريم `poster`)، و`mp4`/`gif` (ffmpeg على الجهاز).
- `hold` على مستوى الفريم أو الأنيميشن كله، والمدة الكلية = مجموع الـ holds.
- الفلاتر جوه الفريمات مش بتتنقل للـ keyframes. لو محتاج blur، حطه كـ `filters` على طبقة ثابتة، أو ارسمه جوه الفريم (فرشاة `soft`).
- اسم الطبقة المتحركة في Krita = `name`.

### `filters` (على أي طبقة)
```json
"filters": [{"name": "gaussian blur", "config": {"horizRadius": 20, "vertRadius": 20}},
            {"name": "noise", "config": {"level": 25, "opacity": 40}},
            {"name": "oilpaint", "config": {"brushSize": 3, "smooth": 30}, "destructive": true}]
```
- الافتراضي **Filter Mask**: غير مدمّر، بيشتغل على فيكتور وجروب وFill، وبيفضل قابل للتعديل في Krita.
- **القص:** الماسك بيتقص تلقائيًا على شكل الطبقة (الـ alpha بتاعها)، لأن فلاتر زي noise وhalftone وpixelize بتلوّن الشفاف كمان، ومن غير قص الحبيبات بتغطي الكانفس كله. فلاتر الانتشار (blur، gaussian blur، lens blur، motion blur، maximize، minimize) مش بتتقص، عشان التوهج يطلع برة الشكل. ولو عايز تغيّر ده: `"clip": true/false`.
- `destructive: true` بيطبّق الفلتر على البكسلات مباشرة، وده لطبقات الرسم بس.
- أسامي الإعدادات الصح لكل فلتر من الـ 52 موجودة في `krita_live_info.json`. أشهرها:
  `blur` (halfWidth، halfHeight، strength)، `gaussian blur` (horizRadius، vertRadius)، `motion blur` (blurAngle، blurLength)، `oilpaint` (brushSize، smooth)، `noise` (level، opacity، grayscale)، `pixelize` (pixelWidth، pixelHeight)، `posterize` (steps)، `wave` (horizontalamplitude، horizontalwavelength، verticalamplitude، verticalwavelength)، `unsharp` (amount، halfSize، threshold)، `hsvadjustment` (h، s، v، type، colorize)، `halftone`، `gradientmap`، `emboss`، `sharpen`، `threshold`، `invert`، `desaturate`.

## `python` على مستوى المشهد
ملف `.py` بيتنفّذ جوه Krita **بعد** ما الطبقات تتبني و**قبل** التصدير. المتاح فيه:
- `doc`، و`root`، و`k` (Krita.instance)، و`InfoObject`، و`QtCore`، و`QtGui`، و`JOB_DIR`.
- `solid_bytes(w, h, "#hex")`، و`qimage_bytes(path)` اللي بيرجّع `(bytes, w, h)` بترتيب BGRA.
- `result = {...}` اللي بتحطه هيرجع في التقرير.

ماتناديش `paintLine/paintPath/paintEllipse/paintRectangle/paintPolygon` ولا `openWindow/addView`، لأنهم بيوقّعوا Krita من غير واجهة (اتثبت بـ Frida، شوف re_findings.md).
