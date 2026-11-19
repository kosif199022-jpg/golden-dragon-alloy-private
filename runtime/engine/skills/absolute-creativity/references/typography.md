# التيبوجرافي العربي — مرجع «الإبداع المطلق»

> مرجع للتنين الأسود في الريلز والبوسترات والعناوين واللوجوهات والكابشنز. الشرح بالمصري البسيط، والمصطلحات التقنية بالإنجليزي.

## الفهرس
1. [الخطوط الموجودة على الجهاز + أدوات الاكتشاف](#1-الخطوط-الموجودة-على-الجهاز--أدوات-الاكتشاف)
2. [أنماط الخط العربي واستخدامها العاطفي](#2-أنماط-الخط-العربي-واستخدامها)
3. [خطوط مجانية بتقرّب كل نمط](#3-خطوط-مجانية-بتقرّب-كل-نمط)
4. [الجمع بين العربي واللاتيني (12 زوج)](#4-الجمع-بين-العربي-واللاتيني)
5. [الهيراركي، الحجم، الوزن، التباعد، الحركات، الأرقام، Bidi](#5-الهيراركي-والمقاسات-والتباعد)
6. [مطبّات تقنية (ffmpeg, ImageMagick, Blender, AE)](#6-مطبّات-تقنية)
7. [Kinetic Typography عربي: 20 فكرة](#7-kinetic-typography-عربي-20-فكرة)
8. [Lettering واللوجوتايب](#8-lettering-واللوجوتايب)
9. [كود Pillow-raqm + أمر ffmpeg](#9-كود-pillow-raqm--أمر-ffmpeg)
10. [قائمة نقد التيبوجرافي (10 نقاط)](#10-قائمة-نقد-التيبوجرافي)

---

## 1. الخطوط الموجودة على الجهاز + أدوات الاكتشاف

الجذر: `C:\Users\cinde\OneDrive\Desktop\التنين الأسود\engines\`

| الملف | المسار | الشخصية | استخدامه |
|---|---|---|---|
| Amiri-Bold.ttf | `cinema\assets\fonts\` | Naskh كلاسيكي بتباين عالي | اقتباسات، شعر، تكريم |
| ArefRuqaa-Bold.ttf | `cinema\assets\fonts\` | Ruqaa دافي ومتصل | عناوين عاطفية، ذهبي |
| Cairo-400/700/900.ttf | `cinema\assets\fonts\` | Sans هندسي حديث | كابشنز، UI، عناوين نظيفة |
| ElMessiri-700.ttf | `cinema\assets\fonts\` | Display بطابع قديم ملكي | بوسترات تاريخية، لوجوهات |
| ReemKufi-700.ttf | `cinema\assets\fonts\` | Kufi حديث | عناوين قوية، تك/جيمنج |
| Tajawal-Black.ttf | `cinema\assets\fonts\` | Sans ثقيل جدًا | Hooks، أرقام، impact |
| InstrumentSerif-Italic.ttf | `cinema\assets\fonts\` | Latin serif italic | زوج مع Ruqaa/Naskh |
| Anton-Regular.ttf | `talking_head\data\fonts\` | Latin condensed | زوج مع Kufi/Tajawal |
| arabtype.ttf (Arabic Typesetting) | نظام ويندوز | Naskh رفيع رسمي | كتب، شهادات |
| Calibri / Candara / Garamond Arabic | نظام ويندوز | Humanist | نصوص صغيرة |

### أدوات الاكتشاف (كتالوج KOSIF)
المسار: `C:\Users\cinde\kosif-tool\.claude\skills\kosif-superpowers\scripts\` (ممكن كمان تحت `C:\Users\cinde\kosif-own\kosif-tool\...`).

| الأداة | بتعمل إيه |
|---|---|
| `telegram_typography_atlas.py` | فهرس 5,514 خط، بحث بالستايل: «رقعة»، «كوفي»، «ديواني»، «ثلث» |
| `font_fidelity_lab.py` | فحص OpenType (features, glyph coverage)، ومطابقة خط مع قصاصة مرجعية |

اتشغّل دايمًا بـ `--help` الأول، وماتخمّنش الـ arguments:
```
python telegram_typography_atlas.py --help
python font_fidelity_lab.py --help
```

### الـ helper بتاع السكيل
```
python scripts/font_lab.py list
python scripts/font_lab.py specimen "النص" --out sheet.png
```
`list` بيعرض الخطوط اللي بتدعم العربي، و`specimen` بيرسم ورقة عينات بالنص بتاعك على كل الخطوط، فتختار بعينك مش بالاسم.

> قاعدة: ماتختارش خط من اسمه. اعمل specimen بالنص الحقيقي (فيه ياء وعين وهاء ولام-ألف) وبعدين قرّر.

---

## 2. أنماط الخط العربي واستخدامها

| النمط | الشكل | الإحساس | يتستخدم في | تجنّبه في |
|---|---|---|---|---|
| **Kufi** (كوفي) | زوايا حادة، أفقية قوية، بدون نقاط تقريبًا قديمًا | قوة، أصالة، صلابة، تقنية | عناوين أفلام، لوجوهات، آثار | فقرات طويلة |
| **Square Kufi** (كوفي مربع/هندسي) | حروف مبنية على شبكة مربعة، بتتلوّن كبلوكات | رمزية، دينية، معمارية، متاهة | شعارات مربعة، صور مصغّرة، tiles | نص يتقرا بسرعة (الجمهور العام مش هيفك الحروف) |
| **Naskh** (نسخ) | واضح، متوازن، حروف دايرية | وضوح، ثقة، رسمي | نصوص، كابشنز، كتب | عناوين درامية (محايد زيادة) |
| **Thuluth** (ثلث) | منحنيات كبيرة، تراكب حروف، فخم | جلال، مساجد، شهادات، مهابة | عناوين ضخمة، تكريم، دين | حجم صغير (بيتبهدل) |
| **Ruqaa** (رقعة) | سريع، مائل، مضغوط، بدون تشكيل غالبًا | دفء، حياة يومية، حميمية، مصري جدًا | كابشنز عاطفية، إعلانات، توقيعات | نص طويل جدًا، أرقام كتير |
| **Diwani** (ديواني) | منحني متشابك، مائل لفوق | أرستقراطية، عثماني، ملكي | دعوات، تكريم، مطاعم فخمة | وضوح تحت ضغط |
| **Diwani Jali** (ديواني جلي) | ديواني محشو بنقاط وزخارف بين الحروف | زخرفة، احتفال | ختم، غلاف، لوجو كبير | أي حاجة صغيرة |
| **Farsi / Nastaliq** (فارسي/نستعليق) | معلّق بميل هابط، شعري جدًا | رومانسية، شعر، أردو/فارسي | شعر، أردو، إحساس هادي | عربي مصري عادي (الحروف شكلها غريب لقارئ عربي) |
| **Maghribi** (مغربي) | حروف مدوّرة، الفاء والقاف بنقطة واحدة تحت/فوق مختلفة | شمال أفريقيا، دفء، خصوصية | مشاريع مغاربية، مطبخ، سفر | جمهور مصري ممكن يلبس عليه الترتيب |
| **Modern geometric / display** | هندسي، تباين منخفض، أوزان كتير | عصري، تك، Gen-Z | ريلز، UI، بوسترات حديثة | ما فيش عيب غير الإحساس العام «بارد» |

### إزاي تختار بالعاطفة
- **فخر/تكريم/وطني:** Thuluth أو Amiri Bold بلون ذهبي، تباعد تنفس واسع.
- **دفء/حنين/حب:** Ruqaa (Aref Ruqaa).
- **قوة/أكشن/تك:** Kufi (Reem Kufi) أو Tajawal Black.
- **ثقة/خبر/معلومة:** Naskh أو Cairo.
- **رومانسية/شعر:** Nastaliq لو الجمهور أردو/فارسي، وإلا Amiri أو Lateef.
- **فن شعبي/هزار:** Lalezar، Rakkas، Marhey، Changa.

---

## 3. خطوط مجانية بتقرّب كل نمط

الرخصة: الأغلبية SIL OFL على Google Fonts. اللي مش متأكد منه مكتوب «OFL (verify)». راجع صفحة الخط قبل أي استخدام تجاري.

| الخط | أقرب نمط | الأوزان | الرخصة | ملاحظات |
|---|---|---|---|---|
| Amiri | Naskh كلاسيكي (Bulaq) | 400/700 + italic | OFL | ممتاز للشعر والتشكيل |
| Aref Ruqaa | Ruqaa | 400/700 | OFL | بيدعم تشكيل كويس |
| Cairo | Sans هندسي | 200–1000 variable | OFL | الاختيار الآمن للمصري |
| Tajawal | Sans نظيف | 200–900 | OFL | Black ممتاز للـ hooks |
| Reem Kufi (+ Fun, Ink) | Kufi حديث | 400–700 | OFL | Ink للـ distressed |
| El Messiri | Display قديم/ملكي | 400–700 | OFL | بيتماشى مع ذهبي |
| Lalezar | Display ثقيل | 400 | OFL | عناوين مرحة، بوسترات |
| Rakkas | Display حاد الشكل | 400 | OFL | impact + شخصية |
| Marhey | Display مرح مدوّر | 300–700 | OFL | أطفال، ألعاب |
| Lateef | Naskh/Nastaliq-ish ناعم | 200–800 | OFL | بيستخدم كتير للأردو والسندي |
| Scheherazade New | Naskh تقليدي (SIL) | 400–700 | OFL | قراءة نصوص طويلة، مصاحف |
| Noto Naskh Arabic | Naskh شامل | 400–700 | OFL | fallback آمن |
| Noto Kufi Arabic | Kufi مبسّط | 100–900 | OFL | واجهات ومحتوى |
| Noto Sans Arabic | Sans محايد | 100–900 | OFL | fallback |
| IBM Plex Sans Arabic | Sans تقني | 100–700 | OFL | UI، تقارير، داشبورد |
| Readex Pro | Sans سهل القراءة | 160–700 | OFL | لوحات، شاشات صغيرة |
| Almarai | Sans عصري | 300–800 | OFL | تطبيقات |
| Changa | Sans مدوّر وحركي | 200–800 | OFL | عناوين شبابية |
| Blaka (+ Ink, Hollow) | Display مدوّر عريض | 400 | OFL (verify) | عناوين impact |
| Katibeh | Calligraphic ناعم (قريب Ruqaa/Diwani) | 400 | OFL | دعوات، شعر |
| Jomhuria | Display ضيّق جدًا | 400 | OFL | ملصقات طويلة وضيقة |
| Mada | Sans هندسي خفيف | 200–900 | OFL | نصوص |
| Harmattan | Naskh لغات أفريقية/عربي | 400–700 | OFL (verify) | بديل نص |
| Alkalami | Naskh لغات غرب أفريقيا | 400 | OFL (verify) | تغطية حروف ممتدة |
| Gulzar | Nastaliq | 400 | OFL (verify) | شعر أردو |
| Noto Nastaliq Urdu | Nastaliq | 400–700 | OFL | محتاج line-height ضخم |
| Vibes | Display زخرفي (كتابة بالفرشاة) | 400 | OFL | شكل «كاليجرافي» سريع |
| Qahiri | Display عصري دافي | 400 | OFL (verify) | عناوين شخصية |
| Baloo Bhaijaan 2 | Display مدوّر ودود | 400–800 | OFL | أطفال، ستيكرز |

**ملاحظة:** مفيش خط مجاني فيه Thuluth أو Diwani Jali حقيقيين بجودة الخطاط. الأحسن: لو الشغل كبير، استخدم لوحة خطاط مرخّصة أو اعمل Lettering بإيدك (القسم 8). البحث عن «ثلث» أو «ديواني» في `telegram_typography_atlas.py` ممكن يطلّع مرشحين، والرخصة تتراجع يدوي.

---

## 4. الجمع بين العربي واللاتيني

### القواعد
| القاعدة | الشرح |
|---|---|
| **x-height مقابل ارتفاع السن** | الأسنان (ب ت ن ي في النصف الأول من الكلمة) بترتفع قد x-height اللاتيني تقريبًا. لو اللاتيني x-height صغير (Garamond) والعربي كبير، هتحس بفرق. طابق بصريًا: اضبط حجم اللاتيني ±5–15% بعد ما ترصّ الاتنين على نفس baseline. |
| **Baseline** | العربي بينزل تحت الـ baseline (ج ع ق ي). اتأكد إن الـ baseline المشتركة منطقية، مش الـ bounding box. |
| **تباين الخط** | عربي بتباين عالي (Amiri) مع لاتيني serif بتباين عالي. عربي monoline مع لاتيني sans monoline. ماتخلطش تباين عالي بمنخفض. |
| **الوزن** | الحروف العربية بتبان أخف بصريًا من اللاتينية بنفس الوزن الاسمي. ارفع العربي درجة وزن (400 مقابل 350 مثلًا). |
| **المزاج** | قديم مع قديم، تقني مع تقني. الاستثناء الواعي: ضدّية متعمدة (Ruqaa مع condensed sans). |
| **الحجم** | العربي غالبًا محتاج حجم أكبر 10–20% عشان نفس المقروئية. |
| **الاتجاه** | العربي يمين، اللاتيني يسار: ماتكتبش سطر مختلط اتجاهه مش واضح. اعمل سطرين منفصلين لكل لغة. |

### 12 زوج موصى بيهم
| # | عربي | لاتيني | المزاج / الاستخدام |
|---|---|---|---|
| 1 | Aref Ruqaa Bold | Instrument Serif Italic | دفء أدبي، ذهبي، تكريم (موجودين على الجهاز) |
| 2 | Amiri Bold | Cormorant Garamond / EB Garamond | شعر، كتب، رسمية |
| 3 | Reem Kufi 700 | Anton | قوة، أكشن، عناوين ريلز (موجودين) |
| 4 | Tajawal Black | Inter / Archivo Black | hooks، أرقام، impact |
| 5 | Cairo 700/900 | Montserrat / Poppins | براندات حديثة نظيفة |
| 6 | El Messiri 700 | Playfair Display | فخامة قديمة، مطاعم، بوسترات تاريخية |
| 7 | IBM Plex Sans Arabic | IBM Plex Sans / Plex Mono | تك، داشبورد |
| 8 | Readex Pro | Space Grotesk | تطبيقات، startups |
| 9 | Lalezar | Bebas Neue / Oswald | بوسترات مرحة جريئة |
| 10 | Katibeh / Vibes | Great Vibes / Pinyon Script | دعوات، أفراح |
| 11 | Scheherazade New / Noto Naskh | Source Serif / Lora | نصوص طويلة، ديني، تعليمي |
| 12 | Noto Kufi Arabic | DM Sans / Manrope | محتوى محايد، corporate |

عشان تجرّب: `python scripts/font_lab.py specimen "عنوان Title" --out pairs.png` وشوف بعينك. وكل الأزواج الأخرى اللاتينية (Inter, Playfair...) مش بالضرورة منزلة — اتأكد من وجودها أو نزّلها (OFL).

---

## 5. الهيراركي والمقاسات والتباعد

### الهيراركي (فيديو 1080×1920)
| المستوى | الحجم | الوزن | ملاحظة |
|---|---|---|---|
| Hook / عنوان | 110–180 px | Black/Bold | 1–5 كلمات بس، سطرين max |
| عنوان فرعي | 60–80 px | Bold | |
| Caption | 56–72 px | Bold/Medium | 2 سطر max، قريب من 40–50% من الارتفاع، مش في أسفل الشاشة (بتغطّيها واجهة المنصة) |
| تفصيلة / credit | 32–40 px | Regular | الحد الأدنى للموبايل ~32 px |

نسبة بين المستويات: 1.5× إلى 2× على الأقل. لو الفرق صغير الهيراركي بتضيع.

### التباعد (tracking)
**ماتعملش letter-spacing للعربي.** الحروف متصلة؛ التباعد بيقطع الربط ويخلي الكلمة تتفكك وتتقرا حروف مش كلمة. كمان ده بيعطّل كل الـ contextual forms.

بدائل لو عاوز تمدّ الكلمة:
| الطريقة | الشرح | تحذير |
|---|---|---|
| **Kashida / Tatweel (ـ U+0640)** | بيمد الوصلة بين حرفين متصلين | حطه بس في المواضع المسموحة (قبل/بعد ب ت ث ن ي س ش ص ض وغيرها المتصلة)، وبعد الحروف اللي ممكن تتمد. ماتحطوش بعد حروف مش بتتصل (د ذ ر ز و ا). وماتزودش كشيدة أكتر من واحدة-اتنين في الكلمة |
| خط variable بمحور width | Cairo variable فيه wght بس. بعض الخطوط فيها wdth | لو موجود استخدمه بدل الكشيدة |
| تباعد الكلمات (word-spacing) | آمن | مش بيأثر على الحروف |
| تكبير الخط | | الأبسط |

اللاتيني: tracking موجب +2–8% للـ all-caps، سالب -1 لـ -3% للعناوين الكبيرة.

### Line height
- العربي أطول: **1.5–1.8×** للنص، **1.2–1.35×** للعناوين الكبيرة (فيه أسفل ج ع ق وأعلى ك ط ظ ل ا وتشكيل).
- مع التشكيل: 1.8–2.0.
- Nastaliq: 2.0+ (المنحدر بياكل المساحة).
- عنوان من سطرين: قصّر المسافة لحد ما الحركات ماتلمسش سطر تاني.

### الحركات (Harakat)
- فعّلها في الشعر والقرآن والتعليم والأسماء الملتبسة فقط. في الكابشنز العادية بتزحم.
- اتأكد إن الخط بيدعم mark positioning (GPOS). Amiri وScheherazade New ممتازين. Cairo/Tajawal مقبولين. Calibri Arabic وخطوط display ممكن تحط الفتحة في مكان غلط.
- زوّد line-height، وماتقصّش (crop) الصورة قريب من الحرف.
- لو بتعمل ستروك: الحركات الصغيرة بتغرق في ستروك سميك، قلّل السمك.

### الأرقام
| النوع | شكلها | استخدام |
|---|---|---|
| Western (0-9) | 1 2 3 | الأرقام المصرية العادية: أسعار، تواريخ، هواتف، سوشيال. **الافتراضي** لجمهور مصري على الإنترنت |
| Arabic-Indic (٠-٩) | ١ ٢ ٣ | رسمي، ديني، كلاسيكي، شهادات، شعر. تمنح إحساس ثقافي |
| Persian/Urdu (۰-۹) | ۴ ۵ ۶ | فارسي/أردو فقط (٤٥٦ العربية ≠ ۴۵۶) |

- ماتخلطش النوعين في نفس الجملة.
- راجع إن الخط عنده glyphs للأرقام الهندية (Cairo, Amiri فيها).
- للتحويل: `str.translate(str.maketrans("0123456789","٠١٢٣٤٥٦٧٨٩"))`.
- ماتنساش الفاصلة العربية «،» والفاصلة المنقوطة «؛» وعلامة الاستفهام «؟» بدل , ; ?

### RTL / Bidi
| المشكلة | العرض | الحل |
|---|---|---|
| علامة ترقيم في آخر الجملة بتطلع في الأول | `مرحبا!` ممكن تظهر `!مرحبا` لو الاتجاه LTR | اضبط direction="rtl" أو ضيف RLM (U+200F) في الآخر |
| كلمة إنجليزي وسط عربي بتقلب ترتيب | `استخدم iPhone 15 Pro الآن` | لف الجزء اللاتيني بـ LRI/PDI (U+2066 ... U+2069) أو LRM |
| رقم + وحدة | `20% خصم` أو `50 جنيه` | بيتحرك الـ % ; ضيف LRM أو رتّب الجملة يدويًا |
| أقواس ( ) معكوسة | الأقواس mirrored تلقائيًا في bidi المضبوط، ومش مضبوطة في ffmpeg قديم | استخدم الرندر عبر Pillow-raqm |
| URL / إيميل | بتتكسر | حطه في سطر لوحده LTR |
| نص على 2 سطر ومحاذاة | align="right" مش `left` | في Pillow: `anchor="ra"` أو احسب الـ bbox |

حروف التحكم المفيدة: RLM `\u200f`، LRM `\u200e`، RLI `\u2067`، LRI `\u2066`، PDI `\u2069`.

---

## 6. مطبّات تقنية

| الأداة | المشكلة | الحل |
|---|---|---|
| **ffmpeg drawtext** | حروف مفكوكة أو معكوسة لو ffmpeg اتبنى من غير `libharfbuzz` و`libfribidi` | شوف `ffmpeg -buildconf` أو `ffmpeg -version`، دوّر على `--enable-libharfbuzz --enable-libfribidi`. الأأمن: ارسم النص كـ PNG شفاف بـ Pillow-raqm (القسم 9) وبعدين `overlay`. ده كمان بيدّيك ستروك وظل وأي تأثير |
| **ffmpeg subtitles/ass** | ASS/libass بيستخدم harfbuzz لو متبني معاه؛ ممكن يشتغل | جرّب أولًا على سطر واحد؛ للضمان ارندر الكابشن PNG sequence |
| **ImageMagick** | `-annotate`/`label:` من غير raqm بيرسم عربي مفكوك | `magick -version` شوف `Features` و`Delegates`، ولازم raqm. وإلا Pillow |
| **Pillow** | من غير libraqm بيرسم عربي مفكوك ومعكوس | افحص `from PIL import features; features.check("raqm")`. على الجهاز ده موجود. لازم `layout_engine=ImageFont.Layout.RAQM` |
| **Blender text object** | مش بيعمل shaping للعربي (حروف مفصولة ومعكوسة) | ارندر النص صورة/SVG: Inkscape (Text → Object to Path → Save SVG) وبعدين File → Import → SVG كـ curve واعمله extrude. أو استخدم الـ PNG كـ texture على plane. السكيل `blender-pro` فيه الطريق للـ logo reveals |
| **After Effects** | العربي مفكوك لو الـ text engine مش مضبوط | Preferences → Type → Text Engine = **Middle Eastern and South Asian**، وفعّل Paragraph panel RTL. الخط لازم يدعم الحروف |
| **Premiere / CapCut** | CapCut بيتعامل كويس مع العربي، Premiere محتاج Middle Eastern تفعيل | ابدأ من Essential Graphics وجرّب |
| **Fonts variable** | بعض البرامج ما بتقراش variable axes | حوّل لـ static instances |
| **Emoji + عربي** | الإيموجي بيكسر الـ bidi | افصل الإيموجي كطبقة |
| **PNG حدود مقصوصة** | الـ ستروك والظل بيتقصوا | ضيف padding حوالي (stroke + blur radius)×2 |
| **OneDrive** | مسارات `OneDrive\Desktop\التنين الأسود` فيها عربي ومسافات | استخدم `pathlib` ودايمًا quote في ffmpeg |

---

## 7. Kinetic Typography عربي: 20 فكرة

مبدأ أساسي: **الكتابة العربية بتتحرك من اليمين للشمال، وبتتكوّن بوصلات متصلة، والنقط جزء من الحرف.** أي حركة بتكسر الاتصال أو بتبدأ من الشمال بتحس غريبة إلا لو مقصودة.

| # | الفكرة | الطريقة |
|---|---|---|
| 1 | **Stroke reveal من اليمين للشمال** | mask مستطيل أو gradient wipe بيتحرك من يمين لشمال فوق النص، أو ارسم المسار (SVG path) بـ stroke-dashoffset |
| 2 | **Word-by-word مع الصوت** | استخرج word timestamps بـ whisperx (`--language ar --align_model ...`)، وكل كلمة تظهر في `start` وتنطفي أو تخفت عند `end`. الكلمة المنطوقة تتضوّى (ذهبي) والباقي رمادي |
| 3 | **النقط تنزل (nuqat drop)** | افصل النقط كطبقة. الحروف تظهر الأول وبعدين النقط تنزل بـ ease-out bounce |
| 4 | **تمطيط كشيدة على البيت** | ولّد صورة بكشيدة متفاوتة لكل frame (tatweel count 0..4) وناعم بين الاتنين على الـ kick |
| 5 | **Mask reveal بشكل الخط** | كلمة تتكشف من جوّه شكل (دايرة/خنجر/موج) بدل wipe مستطيل |
| 6 | **3D extrude** | ارندر النص SVG→curve في Blender (القسم 6) وسلّط كاميرا بتتحرك على العمق |
| 7 | **Calligraphy-as-image morph** | حوّل لوحة خط (Thuluth) لصورة، واعمل morph بين النص العادي واللوحة (displacement/optical flow/RIFE) |
| 8 | **Letter-by-letter handwriting** | استخدم SVG محوّل لـ skeleton وارسمه بترتيب الكتابة الصحيح (النقط في الآخر) |
| 9 | **Hooks بـ scale pop** | أول كلمة من الـ hook تكبر 120% وترجع 100% في 6–8 frames (overshoot خفيف) |
| 10 | **Karaoke gold sweep** | تدرج ذهبي بيكتسح الكلمة من يمين لشمال بنفس مدة نطقها |
| 11 | **Vertical stack** | الكلمات فوق بعض بحجم يتناسب مع الأهمية (Tajawal Black) مع الكلمة المحورية أكبر |
| 12 | **Word-as-image** | الكلمة نفسها تتحول لشكلها: «موج» تتموج، «نار» تتلوّن (القسم 8) |
| 13 | **Parallax layers** | النص على طبقتين (ظل خلفي + أمامي) بحركة مختلفة السرعة مع حركة الكاميرا |
| 14 | **Glitch على الكلمة الصادمة** | RGB split ± 4 px و1–3 frames بس. ماتزودش وإلا يضيع الاتصال |
| 15 | **Slide-in من اليمين** | السطر يدخل من يمين الشاشة بسرعة وينزلق ويقف (اتجاه القراءة) |
| 16 | **Fade-per-word مع blur** | blur 20→0 مع opacity 0→1، بتدّي إحساس سينمائي |
| 17 | **Ink bleed / نشر الحبر** | ماسك noise بيتوسع من نقطة، مناسب لـ Ruqaa |
| 18 | **Mirror + shadow loop** | ظل للنص بيتحرك عكس الحركة (للـ end cards) |
| 19 | **Underline calligraphic** | خط كشيدة طويل بيتمدّ تحت العنوان في 12 frame |
| 20 | **Counter / أرقام بتعد** | ارقام (Western أو Arabic-Indic) بتعد لفوق بسرعة وتثبت على الرقم. اتأكد من monospace/tabular numerals عشان العرض ما يتغيرش |

نصايح التنفيذ:
- صور النص كلها PNGs شفافة من Pillow-raqm، والحركة كلها transform في ffmpeg/Remotion/HyperFrames. ده بيحل مشكلة الـ shaping مرة واحدة.
- ماتحرّكش حرف حرف في كلمة متصلة إلا لو الغرض الفكك نفسه.
- توقيت: 24–30 fps، تأخير بين الكلمات 2–4 frames لو من غير صوت، ومزامنة مع الصوت لو فيه.
- قدّر 0.4 ثانية على الأقل لكل كلمة على الشاشة، والسطر الكامل 1.2–2.5 ثانية قبل ما يتشال.

---

## 8. Lettering واللوجوتايب

| التقنية | الفكرة | مثال |
|---|---|---|
| **Word-as-image** | شكل الكلمة بيعبّر عن معناها | «قمر»: الميم تتحول لهلال. «نار»: الراء بتاخد لهب. «ماء»: الألف تتحول لقطرة |
| **Calligram (خط تصويري)** | الكلمات ترصّ بشكل صورة (أسد، جمل، قلب) | اسم بطل على شكل صقر |
| **Negative space** | الحرف بيتكوّن من الفراغ حواليه | حرف «ع» فراغ في دايرة، «ه» جوّه مربع |
| **Ligature مخترعة** | دمج حرفين بتصميم واحد | «لا» المعروفة. ممكن تدمج حرفين من الاسم بنفس الطريقة |
| **Monogram كوفي مربع** | الاسم بالكوفي المربع في شبكة 4×4 | لوجو دقيق وبسيط |
| **Dot play** | النقطة تتحوّل لعنصر (شمس، نجمة، قلب) | نقطة الياء = نجمة |
| **Stroke contrast** | غلظة مختلفة داخل نفس الكلمة | أول حرف أغلظ كـ drop cap |
| **Hybrid** | عربي في كلمة ولاتيني في كلمة بنفس البنية | لوجو ثنائي اللغة بنفس الـ weight والزاوية |

خطوات عملية للوجو:
1. اكتب الاسم بـ 5–8 خطوط مختلفة (`font_lab.py specimen`).
2. اختار 2 أقرب لروح البراند.
3. حوّلهم Outlines (Inkscape: Path → Object to Path).
4. عدّل الوصلات والنقط يدويًا (Node tool): وحّد سُمك الأسنان، ظبّط المسافات الداخلية للحروف.
5. جرّبه كبير وصغير (favicon 32 px)، أبيض/أسود، معكوس.
6. اختبار «العين نص مقفولة»: الشكل العام لازم يتقرا.
7. سلّم SVG + PNG شفاف، وسجّل الخط الأصلي ورخصته.

> ملاحظة رخصة: تعديل خط OFL وتحويله outlines في لوجو مسموح عادة، لكن راجع الرخصة. خطوط ويندوز (Arabic Typesetting وغيره) رخصتها مختلفة وقد ماتسمحش بالتحويل لشعار تجاري.

---

## 9. كود Pillow-raqm + أمر ffmpeg

### رسم عنوان عربي PNG شفاف (ستروك + ظل)
```python
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageFont, features

assert features.check("raqm"), "Pillow من غير libraqm: العربي هيطلع مفكوك"

FONT = r"C:\Users\cinde\OneDrive\Desktop\التنين الأسود\engines\cinema\assets\fonts\ArefRuqaa-Bold.ttf"

def render_title(text, out, font_path=FONT, size=160,
                 fill=(244, 196, 48, 255), stroke_w=6, stroke_fill=(20, 12, 4, 255),
                 shadow_off=(8, 10), shadow_blur=14, shadow_alpha=170,
                 line_gap=1.5, align="center"):
    font = ImageFont.truetype(font_path, size, layout_engine=ImageFont.Layout.RAQM)
    lines = text.split("\n")
    kw = dict(font=font, direction="rtl", language="ar")

    # قياس: bbox لكل سطر
    probe = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    boxes = [probe.textbbox((0, 0), ln, stroke_width=stroke_w, **kw) for ln in lines]
    widths = [b[2] - b[0] for b in boxes]
    line_h = int(size * line_gap)
    pad = stroke_w + shadow_blur * 2 + max(abs(shadow_off[0]), abs(shadow_off[1])) + 10
    W = max(widths) + pad * 2
    H = line_h * len(lines) + pad * 2

    text_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(text_layer)
    for i, (ln, b, w) in enumerate(zip(lines, boxes, widths)):
        if align == "center":
            x = (W - w) // 2 - b[0]
        else:  # right (RTL)
            x = W - pad - w - b[0]
        y = pad + i * line_h - b[1] + (line_h - (b[3] - b[1])) // 2
        d.text((x, y), ln, fill=fill, stroke_width=stroke_w,
               stroke_fill=stroke_fill, **kw)

    # الظل: ألفا الطبقة، يتلوّن أسود، يتبلّر، يتزحزح
    alpha = text_layer.getchannel("A")
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    shadow.putalpha(alpha.point(lambda v: v * shadow_alpha // 255))
    shadow = shadow.filter(ImageFilter.GaussianBlur(shadow_blur))
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    canvas.alpha_composite(shadow, dest=shadow_off) if shadow_off[0] >= 0 and shadow_off[1] >= 0 \
        else canvas.alpha_composite(shadow)
    canvas.alpha_composite(text_layer)

    Path(out).parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out)      # PNG بخلفية شفافة
    return canvas.size

if __name__ == "__main__":
    print(render_title("الإبداع المطلق\nبقلم التنين الأسود", "title.png"))
```

ملاحظات الكود:
- `direction="rtl"` و`language="ar"` لازم في `textbbox` و`text` كليهما.
- الـ padding لازم يغطي الستروك والبلور وإلا الحواف تتقص.
- للإنجليزي وسط الجملة: لف الجزء اللاتيني بـ `\u2066 ... \u2069`.
- لو مفيش `ar` language tag بيشتغل: شيله؛ المهم `direction`.
- لو عاوز نص بتدرّج: ارسم النص على mask وخليه يتلصق على gradient.

### ffmpeg overlay
```bash
# ظهور ثابت من ثانية 1 لـ 4، في نص الشاشة
ffmpeg -y -i bg.mp4 -i title.png -filter_complex \
"[0:v][1:v]overlay=x=(W-w)/2:y=(H-h)/2:enable='between(t,1,4)'" \
-c:v libx264 -crf 18 -pix_fmt yuv420p -c:a copy out.mp4

# fade in/out بدون كتابة فريمات: تدوّر الصورة كـ loop
ffmpeg -y -i bg.mp4 -loop 1 -t 5 -i title.png -filter_complex \
"[1:v]format=rgba,fade=t=in:st=1:d=0.5:alpha=1,fade=t=out:st=4:d=0.5:alpha=1[t];\
[0:v][t]overlay=(W-w)/2:(H-h)/2:shortest=1" \
-c:v libx264 -crf 18 -pix_fmt yuv420p -c:a copy out.mp4

# دخول من اليمين (slide) ثم وقوف
ffmpeg -y -i bg.mp4 -i title.png -filter_complex \
"[0:v][1:v]overlay=x='if(lt(t,1.5),W-(W-(W-w)/2)*(t/1.5),(W-w)/2)':y=(H-h)/2" \
-c:v libx264 -crf 18 -pix_fmt yuv420p out.mp4
```
- في Windows PowerShell، استخدم سطر واحد أو علامة backtick للتكملة، لأن `\` مش بتشتغل.
- عشان تتأكد من النتيجة: استخرج frame: `ffmpeg -ss 2 -i out.mp4 -frames:v 1 check.png` وبص عليه بعينك (الحروف متصلة؟ الترتيب صح؟).

---

## 10. قائمة نقد التيبوجرافي

| # | السؤال | علامة الفشل |
|---|---|---|
| 1 | **الاتصال:** الحروف متصلة وبترتيبها الصح؟ | حروف مفكوكة أو معكوسة (shaping مكسور) |
| 2 | **القراءة في 1–2 ثانية:** الجمهور بيقرا العنوان بدون جهد؟ | خط زخرفي زيادة أو سطر طويل |
| 3 | **الهيراركي:** مستوى واحد واضح هو الأول؟ | كل حاجة بنفس الحجم والوزن |
| 4 | **التباين مع الخلفية:** النص مقروء فوق الصورة المتحركة؟ | محتاج ستروك/ظل/overlay غامق، أو لون أقرب للخلفية |
| 5 | **المقاس على الموبايل:** أصغر نص ≥ 32 px في 1080 عرض؟ | تفاصيل بتختفي |
| 6 | **Line height والحركات:** السطور مريحة والتشكيل مش بيتلامس؟ | سطور متراصة، حركات بتتداخل |
| 7 | **الأرقام والـ bidi:** نوع الأرقام واحد، والإنجليزي/الرموز في مكانهم؟ | % أو علامة ترقيم في الجنب الغلط |
| 8 | **الزوج:** العربي واللاتيني بنفس المزاج والوزن والـ x-height؟ | لاتيني أصغر/أخف، أو خطين متنافرين |
| 9 | **المزاج:** النمط يخدم المشاعر (Kufi قوة، Ruqaa دفء...)؟ | Thuluth لإعلان تك، أو Kufi لقصة حنين |
| 10 | **الحركة والمسافات:** الحركة بتحترم اتجاه القراءة، والهوامش/safe-zone سليمة؟ | نص في منطقة واجهة المنصة، تمدد بتباعد حروف، حركة من الشمال |

قاعدة ذهبية للتنين: ابعت 3 خيارات خط مختلفة الشخصية (من `font_lab.py specimen`)، اختار واحد وبرّر الاختيار بجملة، وافحص frame نهائي قبل التسليم.
