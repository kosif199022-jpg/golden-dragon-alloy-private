# حرفة البرومبت — صورة / فيديو / صوت (Prompt Craft)

> البرومبت بيتكتب مجانًا. التوليد نفسه بيصرف فلوس، فمفيش توليد قبل موافقة المستخدم الصريحة. اكتب البرومبت، اعرضه، واستنى «اتفضل ولّد».
> أي معلومة عن أسماء موديلات أو باراميترات: **راجع الدوكيومنتيشن الحالي** — الإصدارات بتتغير بسرعة.

## الفهرس
1. [تشريح البرومبت الشامل](#1-تشريح-البرومبت-الشامل)
2. [صورة vs فيديو](#2-صورة-vs-فيديو)
3. [ثبات الشخصية والمنتج](#3-ثبات-الشخصية-والمنتج)
4. [ملاحظات حسب الموديل](#4-ملاحظات-حسب-الموديل)
5. [بنوك المفردات](#5-بنوك-المفردات)
6. [النص العربي جوه الصور](#6-النص-العربي-جوه-الصور)
7. [12 برومبت كامل](#7-اتنين-عشر-برومبت-كامل)
8. [حلقة التحسين](#8-حلقة-التحسين-iteration-loop)
9. [قائمة نقد البرومبت](#9-قائمة-نقد-البرومبت)

---

## 1. تشريح البرومبت الشامل

الترتيب (من الأهم للأقل):

| # | الطبقة | بتجاوب على | مثال |
|---|---|---|---|
| 1 | Subject | مين/إيه؟ | «a 60-year-old Egyptian tea seller with deep laugh lines» |
| 2 | Action | بيعمل إيه؟ | «pouring tea from a height into a glass» |
| 3 | Setting | فين/إمتى؟ | «narrow Islamic Cairo alley, 1am, wet asphalt» |
| 4 | Composition / shot | الكادر | «medium close-up, rule of thirds, subject left» |
| 5 | Camera & lens | العدسة | «85mm f/1.8, shallow depth of field» |
| 6 | Lighting | الإضاءة | «warm tungsten practicals, cyan rim light» |
| 7 | Color / grade | الألوان | «teal and amber, crushed blacks» |
| 8 | Texture / film stock | الملمس | «Kodak Portra 400 grain, halation» |
| 9 | Mood | الإحساس | «nostalgic, quiet, intimate» |
| 10 | Style refs | المرجعية بالصفات | «1970s Egyptian cinema look, painterly realism» |
| 11 | Technical | تقني | «--ar 16:9» / «5 seconds, 24fps» |

### مبادئ الترتيب والوزن
- **الأول بياخد وزن أكبر.** الموديل بيدّي الكلمات الأولى أهمية أعلى. ابدأ بالسوبجكت مش بـ«beautiful, 8k, masterpiece».
- **اسم محسوس يغلب صفة مجردة.** «brass tea kettle with dented spout» أحسن من «beautiful old kettle». الصفة بتتفسّر بمليون شكل، الاسم المحسوس بيتفسّر بشكل واحد تقريبًا.
- **صفة واحدة قوية لكل اسم**، مش خمسة. «weathered» كفاية، مش «old worn aged ancient weathered».
- **قول الموجود، مش اللي مش موجود.** «empty street» أحسن من «no people» (بعض الموديلات بتشوف «people» وترسمهم). استخدم negative prompt بس لو الموديل بيدعمه.
- **ما تتناقضش:** «dark moody» + «bright high-key» = ناتج مشوّش.
- **الطول:** Flux/GPT-image/Imagen بيستحملوا فقرات طويلة. Midjourney أحسن مع جمل مركّزة قصيرة-متوسطة. الفيديو: 2 إلى 4 جمل واضحة.
- **المرجعية بالصفات:** ما تكتبش اسم فنان حي. اوصف السمات: «flat pastel palette, symmetrical framing, whimsical dollhouse sets» بدل اسم مخرج. مسموح بحقب وحركات (Art Deco, Bauhaus, 90s documentary, Fayum portrait).
- **إجيبت الحقيقية:** حدّد التفاصيل: طراز العمارة (مملوكي/خديوي)، الملابس (جلابية، ملس، طرحة)، الخامات (طوب أحمر، مشربية خشب). من غير تحديد الموديل بيرسم «شرق أوسط عام».

قالب سريع:
```
[Subject + key detail], [action], in [setting + time], [shot type], [camera/lens],
[lighting], [color grade], [texture/film], [mood], [style traits], [technical]
```

---

## 2. صورة vs فيديو

| البند | صورة | فيديو |
|---|---|---|
| الزمن | لحظة واحدة متجمّدة | حركة عبر ثواني |
| الأكشن | ممكن وصف pose | **حركة واحدة واضحة** بس |
| الكاميرا | عدسة وزاوية ثابتة | **حركة كاميرا واحدة** + سرعتها |
| الطول المناسب | فقرة طويلة تمام | 2–4 جمل، مباشرة |
| التفاصيل الدقيقة | بتتحمّل | بتتهز (flicker) لو كتير |
| النص | صعب | أصعب — ضيفه بعدين |

### قواعد الفيديو
1. **حركة واحدة للسوبجكت + حركة واحدة للكاميرا.** «she turns her head and smiles while camera slowly dollies in» تمام. ثلاث أكشنز في 5 ثواني = فوضى.
2. **اكتب توقيت:** «at 0s … , by 2s … , ends on …». الموديلات الحديثة بتفهم تقسيم زمني خفيف.
3. **حدّد الكادر الأول والأخير:** «starts on a wide shot of the dunes, ends on a close-up of her eyes».
4. **السرعة:** slow / steady / gentle. من غير سرعة الكاميرا بتجري.
5. **الفيزياء:** وصّف السبب والنتيجة («wind lifts the scarf», مش «scarf floats»).
6. **كاميرا ثابتة لو عايز ثبات:** «static tripod shot, locked-off» — بتقلل التشوّه.
7. **الصوت:** الموديلات اللي بتولّد صوت (Veo-class وغيره) — اكتب الصوت صراحة: «ambient: distant call to prayer, soft traffic hum». الحوار بين علامتي تنصيص.

### Image-to-video (I2V)
- ابدأ بصورة قوية (الصورة هي 80% من النتيجة). صلّح العيوب في الصورة قبل التحريك.
- البرومبت يوصف **اللي يتحرك بس**، مش اللي في الصورة أصلًا. ما تعيدش وصف الشخصية.
- كادر الصورة = أول فريم. لو عايز آخر فريم حدّده (end frame) لو الموديل بيدعم.
- ابدأ بحركة صغيرة (subtle). الحركة الكبيرة بتكسر الوش.
- جرّب 3 حركات كاميرا مختلفة على نفس الصورة (A/B) قبل ما تقرر.

---

## 3. ثبات الشخصية والمنتج

| الأداة | الاستخدام |
|---|---|
| **Character bible** | فقرة وصف ثابتة بتتنسخ حرفيًا في كل برومبت (سن، ملامح، شعر، لبس، علامات مميزة) |
| **صور مرجعية** | 2–4 زوايا (front, 3/4, profile) في الموديلات اللي بتقبل references |
| **Seed** | ثبّت الـ seed واتغيّر متغير واحد بس (لو الموديل بيدعمه) |
| **Elements / Subject reference** | ميزات في Kling/Higgsfield/Runway-class لتثبيت وش أو منتج |
| **نفس الموديل** | تغيير الموديل في نص السلسلة بيغيّر الوش. خلّيك على موديل واحد للسلسلة |
| **Lock على المنتج** | صورة منتج نظيفة خلفية بيضا + «preserve exact logo, shape, and label» في الإيديتور |

Character bible مثال:
```
CHARACTER: Nour, 28, Egyptian woman, oval face, defined arched eyebrows, small mole
above left lip, shoulder-length wavy dark-brown hair, olive skin, wearing a mustard
linen jacket over a white tee, thin gold hoop earrings.
```
ألصقه في أول كل برومبت، وما تعدّلش فيه كلمة.

نصايح:
- ما تغيّرش الإضاءة والشخصية في نفس الخطوة. غيّر واحد.
- الفيديو: ولّد من نفس الصورة المرجعية كل مرة، ما تسلسلش من آخر فريم لفريم (الوش بيتراجع تدريجيًا).
- المنتج: التفاصيل الصغيرة (لوجو، كلام) أضفها بعدين في برنامج تصميم.

---

## 4. ملاحظات حسب الموديل

> عامة ومش مرتبطة بإصدار. **راجع الدوكيومنتيشن الحالي** قبل ما تعتمد على باراميتر.

| الموديل | الأسلوب |
|---|---|
| **Midjourney** | جمل مركّزة + باراميترات في الآخر. `--ar 16:9` (النسبة)، `--stylize/--s` (قد إيه الجمالية الخاصة بالموديل تتدخل: قليل = حرفي، كتير = فنّي)، `--chaos` (تنوّع النتائج الأربعة)، `--sref` (مرجع ستايل من صورة/كود)، `--cref/--oref`-style للشخصية (حسب الإصدار)، `--no` للاستبعاد، `--seed`. الأوزان بـ `::`. |
| **Flux** | لغة طبيعية. فقرات طويلة تمام. بيحب الوصف المحسوس والإضاءة. غالبًا مفيش negative prompt (قول اللي عايزه). نص إنجليزي قصير بيطلع كويس نسبيًا. |
| **GPT-image / Imagen / Seedream** | تعليمات بلغة طبيعية، بيفهموا «حط كذا على اليسار». كويسين في النص اللاتيني والتركيبات المعقدة. الإيديت بالمحادثة. |
| **Nano Banana-class editors** | إيديت بالتعليمات: «change only X, keep everything else identical». ارفع صورة + جملة تغيير واحدة. ممتازين في الثبات. |
| **Kling / Hailuo / Seedance** | سوبجكت + حركة + كاميرا. بيحبوا وصف حركة واضح. بعضهم بيدعم negative prompt وstart/end frame وelements. |
| **Veo-class / Sora-class** | فهم سينمائي ومشاهد أطول، وبعضها بصوت. اكتب الصوت والحوار صراحة. تحكّم زمني بالثواني. |
| **Runway-class** | حركة كاميرا بعبارات مباشرة، ومعاها أدوات motion brush/camera control (حسب الإصدار). |
| **Higgsfield presets** | Presets جاهزة لحركات كاميرا/إفيكتس. الـ preset بيحدد الحركة، فالبرومبت يوصف السوبجكت بس. الدخول من أدوات Higgsfield + موافقة التكلفة قبل التنفيذ. |
| **ElevenLabs** | نص مشكّل للعربي بيحسّن النطق. علامات ترقيم وتوقفات للإيقاع. اختار صوت مناسب للهجة (مصري ≠ فصحى). جرّب مقطع قصير الأول. |

### Negative prompts (لو مدعومة)
قصيرة ومحددة: `blurry, extra fingers, warped face, text, watermark, jitter, morphing`. ما تكتبش 50 كلمة.

### Suno (موسيقى)
- **حقل Style:** النوع + المود + الآلات + الإيقاع + نوع الصوت. مثال: `Egyptian shaabi, 98 BPM, darbuka and accordion, male raspy vocals, gritty street energy`.
- **حقل Lyrics:** علامات هيكل بين أقواس مربعة: `[Intro] [Verse] [Pre-Chorus] [Chorus] [Bridge] [Outro]`، وتعليمات `[Instrumental break: oud solo]`، `[Male vocal]`، `[Spoken]`.
- **العربي:** اكتب الكلمات بالعامية المصرية بحروف عربي. جمل قصيرة، قافية واضحة، تجنّب الكلمات المركبة الطويلة. التشكيل الخفيف بيساعد في الكلمات الملتبسة. لو النطق غلط، جرّب كتابة صوتية (transliteration) للكلمة المشكلة. وولّد كذا نسخة.
- حاجة واحدة أساسية في الستايل: ما تحشرش 10 أنواع. نوعين-تلاتة.
- اسم فنان حي: ما تكتبهوش. اوصف الصوت.

| المفردات | معناها / الاستخدام |
|---|---|
| oud (عود) | وتري، دفء وطرب، تقاسيم |
| qanun (قانون) | وتري منقور، لمعان وزخرفة |
| ney (ناي) | نفخي حزين، روحاني |
| darbuka (درابكة) | إيقاع، مقسوم/ملفوف/سعيدي |
| mizmar (مزمار) | نفخي حاد، بلدي وصعيدي |
| rebab (ربابة) | سيرة شعبية، صعيد، حكي |
| accordion (أكورديون) | شعبي، أفراح، شعبي حضري |
| tarab (طرب) | غناء عاطفي مُطوَّل، آهات، ارتجال |
| maqam (مقام) | Hijaz (حجاز) درامي شرقي، Bayati (بياتي) دافئ، Rast (راست) مفتوح ووقور، Saba (صبا) حزن، Nahawand (نهاوند) رومانسي |
| mahraganat (مهرجانات) | 808s، ترنّم أوتوتيون، إيقاع 100–130، غناء سريع |
| shaabi (شعبي) | أوصاف بلدي، أورج وأكورديون، كلمات شارع |
| sha'bi-tarab fusion | قانون/عود + إيقاع حديث |
| mawwal (موال) | ارتجال صوتي حر بلا إيقاع في أول الأغنية |

---

## 5. بنوك المفردات

### حركات الكاميرا
| العبارة | الأثر |
|---|---|
| static / locked-off | ثبات، رسمية |
| slow push-in / dolly in | تركيز عاطفي |
| pull-out / dolly out | كشف السياق، وحدة |
| tracking shot (side) | مرافقة السوبجكت |
| pan left/right | دوران أفقي من نقطة ثابتة |
| tilt up/down | كشف طول (عمارة، بطل) |
| orbit / arc shot | دوران حول السوبجكت، فخامة |
| crane up / jib | كشف مقياس |
| handheld | واقعية، توتر |
| steadicam follow | مرافقة سلسة |
| whip pan | انتقال سريع |
| rack focus | نقل التركيز بين عنصرين |
| dolly zoom (vertigo) | إحساس غريب/صدمة |
| FPV drone dive | سرعة ومغامرة |
| aerial establishing | افتتاحية مكان |
| time-lapse / slow motion | ضغط/إطالة زمن |

### أنواع اللقطات
| اللقطة | الاستخدام |
|---|---|
| extreme wide / establishing | المكان والمقياس |
| wide / long | الجسم كله مع البيئة |
| medium | من الوسط، حوار |
| medium close-up | صدر وفوق، بورتريه |
| close-up | الوش، عاطفة |
| extreme close-up | عين/تفصيلة |
| over-the-shoulder | حوار |
| POV | عين الشخصية |
| low angle | قوة وهيبة |
| high angle | ضعف أو نظرة شاملة |
| dutch angle | قلق |
| top-down / flat lay | أكل ومنتجات |
| two-shot / group shot | علاقة |
| insert shot | تفصيلة (يد، ساعة) |

### العدسات
| العدسة | الشكل |
|---|---|
| 14–24mm ultra-wide | تشويه حواف، مساحات واسعة |
| 35mm | قريب من عين الإنسان، ريبورتاج |
| 50mm | طبيعي |
| 85mm | بورتريه، ضغط جميل |
| 135mm / 200mm telephoto | ضغط خلفية، عزل |
| macro 100mm | تفاصيل صغيرة جدًا |
| anamorphic | لمعة أفقية، bokeh بيضاوي |
| tilt-shift | شكل مجسّم مصغّر |
| fisheye | تشويه كروي |
| vintage lens / soft focus | حنين |
| f/1.4–f/2 | خلفية ضبابية |
| f/8–f/11 | حدة من الأمام للخلف |

### الإضاءة
| المصطلح | الأثر |
|---|---|
| golden hour | دفء ناعم |
| blue hour | أزرق هادئ |
| overcast soft light | ظلال خفيفة |
| harsh midday sun | ظلال حادة، صحراوي |
| Rembrandt lighting | مثلث ضوء على الخد |
| rim / back light | حواف مضيئة |
| chiaroscuro | تباين درامي |
| low-key / high-key | غامق / ناصع |
| neon practicals | أضواء المحلات والإعلانات |
| tungsten / sodium vapor | أصفر الشارع |
| volumetric light / god rays | أشعة في الغبار |
| softbox / beauty dish | استوديو |
| window light | طبيعي جانبي |
| candlelight / lantern | دفء وحنين (فانوس رمضان) |
| silhouette / contre-jour | ظل في مواجهة الضوء |

### درجات الألوان
| الدرجة | الإحساس |
|---|---|
| teal and orange | سينمائي كلاسيك |
| teal and amber | ليل المدينة |
| desaturated / bleach bypass | قاسي وواقعي |
| warm sepia | تاريخي |
| monochrome / black and white high contrast | وثائقي |
| pastel palette | ناعم، أزياء |
| muted earth tones | طبيعي |
| neon magenta/cyan | سايبربانك |
| gold and deep emerald | فخامة |
| lifted blacks, faded | شكل فيلم قديم |

### الأفلام والملمس
| العبارة | الشكل |
|---|---|
| Kodak Portra 400 | ألوان بشرة ناعمة |
| Kodak Vision3 500T | سينمائي ليلي دافئ |
| Fuji Velvia | ألوان مشبعة |
| Cinestill 800T | هالة حمراء حول الأنوار |
| Super 8 / 16mm | حبيبات، حنين |
| Polaroid / instant | إطار وكسر ألوان |
| VHS / CRT | خطوط، تشويش |
| 35mm film grain | حبيبة خفيفة |
| halation, light bloom | توهج حول الضوء |
| digital clean / 8K sharp | نظيف جدًا (احترس: شكل CGI) |

### الخامات
`brushed brass`, `hammered copper`, `weathered plaster`, `chipped paint`, `rough linen`, `polished marble`, `cracked leather`, `rust and patina`, `dewy skin with visible pores`, `condensation droplets`, `glossy lacquer`, `matte clay`, `woven palm fronds`, `carved mashrabiya wood`.

### الأجواء
| كلمة | أثر |
|---|---|
| misty / foggy | عمق وغموض |
| dusty haze | صحراء/قديم |
| steam rising | أكل/شارع |
| rain-slicked | انعكاسات |
| smoky | درامي |
| golden dust motes | سحر |
| humid heat shimmer | صيف مصر |
| quiet, still | هدوء |
| bustling, chaotic | زحمة |
| ethereal, dreamlike | فانتازيا |

### التكوين
`rule of thirds`, `centered symmetrical`, `leading lines`, `negative space`, `frame within a frame`, `foreground blur layer`, `layered depth (fore/mid/background)`, `golden spiral`, `diagonal composition`, `low horizon`, `high horizon`, `subject small in vast scene`, `tight crop`.

---

## 6. النص العربي جوه الصور

**المشكلة:** معظم الموديلات بتكسّر الحروف العربية: بتفصل الحروف المتصلة، بتعكس الاتجاه (RTL)، بتغلط في التشكيل، وبترسم «شبه حروف». حتى لو نجحت مرة، التكرار مش مضمون.

**الـ workflow الصح:**
1. **ولّد من غير نص** وسيب مساحة فاضية: `"large clean negative space in the upper third for a title"`, وفي البرومبت: `no text, no letters, no signage`.
2. لو في لافتات في المشهد: خليها `blurred out-of-focus shop signs` أو فاضية.
3. **ضيف التايبوجرافي بعدين** بخطوط حقيقية في Photoshop/Figma/Canva/Remotion/After Effects أو HTML/CSS: Cairo، Tajawal، Amiri، Reem Kufi، Aref Ruqaa، Noto Naskh Arabic.
4. تأكد من: اتجاه RTL، اتصال الحروف، التشكيل، الـ kerning، الـ contrast مع الخلفية (ظل خفيف أو طبقة تدرج).
5. في الفيديو: ركّب النص في المونتاج (مش جوه التوليد)، حتى يفضل ثابت.
6. استثناء: نص إنجليزي قصير (1–3 كلمات) ممكن يتولّد في موديلات قوية، لكن افحصه.

---

## 7. اتنين عشر برومبت كامل

### 1) بورتريه سينمائي
```
Close-up portrait of a 70-year-old Egyptian fisherman from Alexandria, deeply sun-creased skin, white stubble, knitted wool cap, salt crystals on his eyebrows, looking slightly off-camera with a calm half-smile. Shot on 85mm at f/1.8, shallow depth of field, blurred blue fishing boats behind him. Soft overcast sea light with a warm bounce from the left, gentle rim light on the cap. Muted teal and sand color grade, Kodak Portra 400 grain, visible skin pores. Quiet, dignified mood. --ar 4:5
```
> ليه ناجح: تفاصيل محسوسة (ملح على الحواجب) بدل «وش جميل»، وعدسة وإضاءة بتحدد الإحساس.

### 2) إعلان منتج
```
Studio hero shot of a frosted glass perfume bottle with a brushed gold cap, standing on a wet black basalt slab, a single curved ribbon of water splashing behind it frozen mid-air. Low-angle three-quarter view, 100mm macro lens, crisp focus on the label area. Strong softbox from top-left, thin cool rim light tracing the glass edges, deep black gradient background. Gold and deep emerald palette, glossy reflections, condensation droplets on the glass. Luxury, minimal, premium. Clean negative space on the right for copy. --ar 4:5
```
> ليه ناجح: خامات محسوسة + مساحة للنص بدل ما نطلب كتابة جوه الصورة.

### 3) شارع مصري بالليل
```
A narrow Cairo alley at 1 a.m. after rain, wet asphalt reflecting a glowing green pharmacy cross and warm tungsten shop bulbs, a street cat crossing in the foreground, a man on a balcony smoking, laundry lines overhead, stacked plastic chairs outside a closed ahwa. Wide shot from low angle, 35mm lens, slight handheld feel. Teal and amber grade, soft halation around the lights, Cinestill 800T look, light drizzle and rising steam from a manhole. Lived-in, quiet, cinematic. Signs are blurred and unreadable. --ar 16:9
```
> ليه ناجح: عناصر مصرية حقيقية (القهوة، الصيدلية، الغسيل) والإضاءة بتحدد المود، واللافتات مطموسة لتفادي العربي المكسور.

### 4) إعادة بناء تاريخية
```
Reconstruction of a bustling Fatimid-era Cairo market in the 11th century: stone gateway of Bab Zuweila in the background, spice merchants in long woolen robes and turbans, camels loaded with sacks, hanging brass lanterns, stalls with piles of saffron and dried hibiscus, dust in the air. Wide establishing shot from an elevated viewpoint, 28mm lens, deep focus. Warm late-afternoon sun with long shadows and floating dust motes. Earthy sepia-gold palette, painterly realism, subtle film grain. Respectful, documentary tone, historically plausible clothing and architecture. --ar 16:9
```
> ليه ناجح: حقبة ومعلم محدد (باب زويلة) وملابس وخامات، فبيقلل «الشرق الأسطوري» العام.

### 5) تصوير أزياء (Editorial)
```
Fashion editorial: a tall model in a sculptural ivory linen cape with exaggerated sleeves, standing on the edge of a salt flat at dawn, hand lifting the fabric into the wind. Full-body shot, 50mm lens, low horizon, subject small against a vast pastel sky. Soft diffused pre-sunrise light, pink and pale-blue gradient, high-fashion magazine finish, fine fabric texture visible, subtle film grain. Calm, otherworldly, elegant. --ar 3:4
```
> ليه ناجح: موضوع واحد وحركة واحدة (القماش في الهوا)، وتكوين فيه مساحة سلبية.

### 6) لوجو ثلاثي الأبعاد
```
3D logo mark of an abstract dragon head made from a single continuous ribbon of polished black obsidian with thin gold inlay lines, centered on a seamless dark charcoal background. Front view with slight 15-degree rotation, 85mm product lens, sharp focus. Soft studio lighting with a gold rim light and a gentle floor reflection, subtle ambient occlusion. Black and gold, high-end, minimal, clean geometry, no text. --ar 1:1
```
> ليه ناجح: خامتين واضحتين وخلفية بسيطة؛ «no text» عشان الاسم يتضاف بعدين بخط حقيقي.

### 7) لقطة فيديو كليب (فيديو + حركة كاميرا)
```
Night rooftop in Cairo, a young singer in a black bomber jacket stands at the edge facing the city lights, a darbuka player behind him. Camera starts on a wide shot and performs one slow orbit around the singer to a close-up of his face by 5 seconds. He slowly turns his head to the camera on the beat and exhales smoke into the cold air. Neon pink and cyan city bokeh, anamorphic lens flares, light wind moving the jacket. Cinematic music-video look, teal and magenta grade. Ambient sound: distant traffic, low drum groove. 5 seconds, 24fps, 16:9.
```
> ليه ناجح: حركة سوبجكت واحدة + حركة كاميرا واحدة (orbit) + توقيت صريح + بداية ونهاية للكادر.

### 8) B-roll لفيلم تكريم
```
Slow-motion close-up of a worn leather military boot stepping onto a sunlit sand dune, sand grains kicking up and drifting in the wind, a folded Egyptian flag visible blurred in the background. Camera static at ground level, then a gentle tilt up to the horizon by 4 seconds. Golden hour backlight with dust particles glowing, warm gold and deep-blue grade, 135mm telephoto compression, subtle film grain. Solemn, proud, emotional. 5 seconds, 24fps, 16:9.
```
> ليه ناجح: لقطة رمزية بسيطة بحركة واحدة، وتصلح قطع مونتاج مع نص بعدين.

### 9) أكل
```
Overhead shot of a Cairo koshary bowl: rice, brown lentils, macaroni, chickpeas, crispy fried onions on top, bright red tomato sauce dripping from a ladle, small side of garlic vinegar. Rustic hammered-copper bowl on a worn blue wooden table, steam rising, a few scattered onion crumbs. Soft window light from the left, 50mm lens at f/4, shallow depth of field on the nearest onions. Warm earthy palette with a pop of red, glossy sauce highlights, appetizing and comforting. --ar 4:5
```
> ليه ناجح: مكونات بالاسم، وبخار وإضاءة ناعمة؛ تفاصيل بتخلي الأكل شهي.

### 10) عمارة
```
Exterior of a contemporary cultural center in New Cairo inspired by mashrabiya: a faceted facade of perforated pale-sandstone panels casting geometric shadows over a shallow reflecting pool at dusk. Wide symmetrical frontal shot, 24mm tilt-shift lens, vertical lines straight. Blue-hour sky, warm interior glow through the screens, soft reflections on still water. Clean architectural photography, crisp detail, muted warm-grey palette with amber accents, calm monumental mood. --ar 16:9
```
> ليه ناجح: ربط مرجع ثقافي بعنصر معماري محسوس + عدسة tilt-shift تحافظ على الخطوط الرأسية.

### 11) فانتازيا
```
A lone traveler in a long indigo cloak crossing a bridge of floating stone slabs above a sea of glowing clouds, giant crescent moon half-risen behind a ruined sandstone temple with towering columns, fireflies of gold light drifting upward. Wide cinematic shot from behind the traveler, 24mm lens, deep atmospheric perspective with layered mist. Moonlit cool blue with gold accents, soft volumetric rays, painterly concept-art finish with fine detail. Awe, solitude, quiet wonder. --ar 21:9
```
> ليه ناجح: سوبجكت صغير في عالم كبير وطبقات عمق، وألوان محدودة (أزرق + دهبي).

### 12) خلفية بوستر
```
Abstract poster background: sweeping dunes of dark-red sand under a night sky, a thin bright crescent moon in the upper right, soft drifting golden dust, subtle star field. Large clean empty area in the upper left and center for title typography. Minimal composition, low horizon, cinematic gradient from deep indigo to burnt orange, fine film grain. Calm, mystical, elegant. No text, no letters, no logos. --ar 2:3
```
> ليه ناجح: مساحة فاضية مقصودة للتايبوجرافي، وتدرج لوني بسيط ثابت.

---

## 8. حلقة التحسين (Iteration Loop)

### تشخيص العيوب
| العيب | التعديل |
|---|---|
| شكل بلاستيكي / CGI | شيل «8K, ultra detailed, perfect»؛ ضيف film grain وpores وعيوب واقعية؛ حط عدسة وفيلم |
| وش مشوّه / أيدي غلط | كادر أبعد أو أقرب، شيل إيدين من الكادر، pose بسيط، موديل أحدث |
| مفيش شخصية في الصورة | ارجع لأول الجملة؛ السوبجكت لازم يتقدم |
| ألوان باهتة | حدّد grade وإضاءة صريحة |
| تكوين عشوائي | حدد shot type وrule of thirds وموقع السوبجكت |
| خلفية مزدحمة | «simple background», negative space, f/1.8 |
| ستايل مش اللي عايزه | استبدل المرجعية بصفات (ألوان، خامة، حقبة) |
| الفيديو بيتهز / flicker | قلل الأكشن، ثبّت الكاميرا، نص أقصر، سرعة slow |
| الفيديو الوش بيتغير | I2V من صورة مرجعية، شيل حركة كبيرة، character bible |
| الكاميرا مش بتتحرك | اكتب الحركة بصيغة فعل مباشر وسرعتها («slow dolly in») |
| نص عربي مكسور | ارجع للقسم 6: ولّد بدون نص |
| الأجواء غلط | غيّر كلمة المود + الإضاءة (تأثير أكبر من أي صفة) |
| تشابه كل النتائج | زوّد chaos/stylize أو غيّر سوبجكت وإضاءة |

### A/B متغير واحد
1. ولّد baseline (3–4 نتايج).
2. غيّر **متغير واحد** (إضاءة، أو عدسة، أو كاميرا).
3. قارن جنب بعض، سجّل الفرق.
4. ثبّت الفائز وانتقل للمتغير التالي.
5. ما تولّدش 20 نتيجة من غير ما يوافق المستخدم على التكلفة. ابدأ بـ 2–4 وبعدين زوّد.

### سجل البرومبت (Prompt Log)
```
## [اسم المشروع] — Prompt #N
- التاريخ: 
- الموديل / الإصدار: 
- النوع: image | video | audio
- البرومبت الكامل: 
- الباراميترات (ar, seed, duration, refs): 
- المتغير اللي اتغيّر عن النسخة السابقة: 
- النتيجة: (ملف/رابط)
- التقييم: 1–5
- الملاحظات (إيه نجح/فشل): 
- الخطوة الجاية: 
- التكلفة التقريبية: 
```

---

## 9. قائمة نقد البرومبت

قبل ما تعرض البرومبت على المستخدم، اسأل:

- [ ] السوبجكت أول جملة وواضح (مين/إيه) بتفصيلة محسوسة؟
- [ ] فيه أسماء محسوسة بدل صفات مجردة (beautiful, amazing)؟
- [ ] أكشن واحد واضح (فيديو: حركة سوبجكت واحدة + حركة كاميرا واحدة)؟
- [ ] المكان والوقت محددين؟
- [ ] نوع اللقطة والعدسة مذكورين؟
- [ ] الإضاءة محددة (مصدر، اتجاه، جودة)؟
- [ ] الألوان / grade محددين، ومفيش تناقض («dark» و«bright»)؟
- [ ] ملمس / فيلم / خامات؟
- [ ] المود وكلمة أو اتنين عن الأسلوب بالصفات (مش أسماء فنانين أحياء)؟
- [ ] النسبة والمدة (`--ar`, seconds, fps)؟
- [ ] مفيش نص عربي مطلوب توليده جوه الصورة؟ (لو في: خُطة تايبوجرافي لاحقة)
- [ ] مساحة فاضية للعنوان/النص لو محتاجينها؟
- [ ] التفاصيل المصرية صحيحة وخاصة (مش «شرق أوسط عام»)؟
- [ ] الطول مناسب للموديل؟ والباراميترات متوافقة مع الإصدار الحالي (راجع الدوكيومنتيشن)؟
- [ ] character bible / refs لو فيه استمرارية؟
- [ ] المحتوى آمن ومحترم (مفيش شخصيات حقيقية بدون إذن، ولا استخدام يضلل)؟
- [ ] المستخدم عارف التكلفة التقريبية ووافق قبل أي توليد؟
