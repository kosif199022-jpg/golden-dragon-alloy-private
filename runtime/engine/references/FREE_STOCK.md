# صور وفيديو مجانية للمونتاج

> **متى تقرأه / when to read:** أي طلب لقطات أو صور مجانية أو «بدون حقوق» أو مفتوحة الترخيص، خلفيات أو B-roll لمونتاج أو ريلز، أو سؤال «أي موقع مجاني يسمح بالاستخدام التجاري؟» · المنصات واللينكات المقفولة ومكان الـ stock وسجلات الحقوق: SOURCES.md

الفكرة: من أي محادثة، ندوّر في المواقع المجانية عن فيديو وصور تخدم المونتاج، ونحمّل كل ملف **ومعاه ترخيصه وسطر النسب**، بدل ما نجيب ملفات مجهولة الحقوق.

## 1. الأداة (مدمجة في المهارة: `$D tool stock`)

`$D` = `python3 <skill>/scripts/dragon.py`. العميل مدمج في `tools/stock/` (من v1.3، تذكرة T5): `stock.py` الباب، و`free_footage.py` للفيديو (17 موقعًا في `tools/stock/data/free_footage_sources.json`)، و`free_photos.py` للصور (7 مصادر)، و`stock_fetch.py` لروابط Pexels/Mixkit/Pixabay، وقاري الأسرار `_secrets.py`. مكتبة بايثون القياسية بس (ffprobe/ffmpeg لو موجودين للقياس وورقة اللقطات)، فبيشتغل في claude.ai وClaude Code وعلى جهازه من غير تثبيت.

| النوع | ابدأ بـ |
|---|---|
| فيديو (لقطات، B-roll) | `$D tool stock search "night city" --orientation portrait --limit 6` |
| صور (خلفيات، لوحات، مخطوطات، فضاء) | `$D tool stock search "desert dunes" --kind photo --orientation portrait --commercial` |
| لينك Pexels/Mixkit/Pixabay بعينه | `$D tool stock pexels ID1 ID2 -o <الشغلانة>/clips --dry-run` (بعدين من غير `--dry-run`) |
| أي أمر كامل للعميل | `$D tool stock video <أمر>` (preview، probe، sources --find …) و`$D tool stock photo <أمر>` (sheet …) |

نفس المسار للاثنين: **search ← معاينة ← download ← ATTRIBUTION.md**.

1. `search "<كلمات إنجليزي>"`: النتائج تتجمّع في `out/free-footage/last_search.json` أو `out/free-photos/last_search.json` **في الفولدر اللي شغّلت منه** (بحث جديد لا يمسح القديم). شغّله من فولدر الشغلانة.
2. معاينة قبل التحميل: `$D tool stock video preview out/free-footage/last_search.json` (ورقة لقطات) أو `$D tool stock photo sheet` (صفحة صور)، واستبعد ما فيه وجوه أو كتابة أو شعارات لا تريدها.
3. `$D tool stock download <id>... --out <مجلد المهمة>/stock`: كل ملف ومعه `<الملف>.json` فيه الترخيص وسطر النسب والبصمة (sha256). نوع الـ id (فيديو أو صورة) بيتعرف من ملفات النتائج، أو حدده بـ `--kind photo`.
4. `ATTRIBUTION.md` في نفس المجلد يتحدّث تلقائيًا: انسخ منه أسطر النسب للوصف أو آخر الفيديو. بعد ما تمسح ملف: `$D tool stock credits <المجلد>`.
5. **من غير شبكة** (أو الموقع مقفول من السحابة أو البروكسي رفض): الأمر يخلص بسطر واضح وexit غير صفر (البحث 3، التحميل 1)، وسطر `hint: no network reached the site …`، ومفيش traceback ولا تجاوز. وقتها §4.
6. محطة المونتاج (`$D run dragon_montage edit … --stock "query"`) بتستخدم نفس `free_footage.py` لوحدها (اللانشر بيحط `DRAGON_FREE_FOOTAGE`).

في kosif-tool نفس الأدوات في `.claude/skills/kosif-superpowers/scripts/` (المصدر)، والنسخة المدمجة فيها تصليح واحد: `download pexels:1` (رقم قصير) بقى رسالة بدل AttributeError. الاختبار: `app/tests/test_v13_stock.py` بردود NASA متسجلة من غير شبكة.

## 2. المصادر

**فيديو** (التفاصيل الكاملة: `$D tool stock sources`):

| الموقع | بلا مفتاح؟ | الترخيص | النسب | تجاري |
|---|---|---|---|---|
| Mixkit | نعم | Free أو Restricted حسب اللقطة | غير لازم | Free نعم، Restricted لا |
| Coverr | نعم | Coverr License | غير لازم | نعم |
| Wikimedia Commons | نعم | لكل ملف (CC0، ملك عام، CC BY/BY-SA) | غالبًا لازم | حسب الملف |
| Internet Archive | نعم | ادعاء الرافع (يُعلَّم المشكوك فيه) | لازم | حسب الملف |
| NASA | نعم | إرشادات ناسا | اذكر ناسا | نعم بلا إيحاء بالتأييد |
| Pexels / Pixabay | مفتاح مجاني | Pexels License / Pixabay Content License | غير لازم | نعم |

**صور** (`$D tool stock sources --kind photo`):

| المصدر | بلا مفتاح؟ | الترخيص | النسب | ملاحظة |
|---|---|---|---|---|
| Openverse | نعم | لكل صورة: CC BY، BY-SA، CC0، PDM | لازم لـ BY | محرك فوق 800 مليون صورة، الترخيص كما يعلنه الموقع الأصلي |
| Wikimedia Commons | نعم | لكل ملف | غالبًا لازم | أماكن وتاريخ وطبيعة |
| NASA Images | نعم | إرشادات ناسا | اذكر ناسا | فضاء والأرض من المدار |
| The Met Open Access | نعم | CC0 | غير لازم | فن إسلامي ومخطوطات وخط وآثار (الملك العام فقط) |
| Pexels | `PEXELS_API_KEY` | Pexels License | غير لازم | صور حديثة وطولية كثيرة |
| Pixabay | `PIXABAY_API_KEY` | Pixabay Content License | غير لازم | حتى 1280 بكسل عبر الـ API |
| Unsplash | `UNSPLASH_ACCESS_KEY` | Unsplash License | شروط الـ API تطلبه | الأداة تبلّغ Unsplash بكل تحميل كما تشترط، وتتخطى Unsplash+ المدفوع |

المفاتيح مجانية من صفحات المطورين (pexels.com/api، pixabay.com/api/docs، unsplash.com/developers) وتوضع في متغيرات بيئة الجلسة، **ولا تُلصق في المحادثة أبدًا**. بدونها تعمل المصادر المجانية بلا مفتاح.

## 3. قواعد الترخيص (إلزامية)

1. **الأداة تسجّل الترخيص ولا تمنحه.** ما في الـ sidecar هو ما يعلنه الموقع؛ في عمل مدفوع افتح `page_url` وتأكد.
2. **ND مرفوض افتراضيًا:** المونتاج تعديل، فالترخيص الذي يمنع التعديل لا يصلح (`--allow-nd` للمرجع فقط).
3. **عمل تجاري أو إعلان ← `--commercial`:** يستبعد NC وMixkit Restricted والتراخيص غير المؤكدة.
4. **الناس والعلامات التجارية:** ترخيص الصورة لا يعني موافقة الشخص الظاهر أو صاحب الشعار؛ في الإعلانات تجنّب الوجوه الواضحة والشعارات أو اطلب إذنًا.
5. **النسب:** كل سطر «required» في `ATTRIBUTION.md` يُكتب في وصف الفيديو أو نهايته؛ «optional» مستحب.
6. **Pinterest وإنستغرام ويوتيوب ليست مصادر ترخيص:** مرجع إلهام ورابط فقط.
7. **لا تجاوز:** صفحة تحقق Cloudflare أو 403 أو 429 تُبلَّغ كما هي ويُترك الموقع، ولا تغيير هوية المتصفح. اقترح جهاز المستخدم أو رفع الملف.

## 4. بلا مستودع أو بلا شبكة

ابحث بنفسك في روابط البحث (`https://mixkit.co/free-stock-video/discover/<كلمة>/`، `https://coverr.co/s?q=<كلمة>`، `https://www.pexels.com/search/videos/<كلمة>/`، `https://pixabay.com/videos/search/<كلمة>/`، `https://openverse.org/search/?q=<كلمة>`، `https://unsplash.com/s/photos/<كلمة>`، `https://commons.wikimedia.org/w/index.php?search=<كلمة>&title=Special:MediaSearch`) وأعطِ المستخدم جدولًا: الرابط، الترخيص، النسب، تجاري؟ ولا تقل «حمّلت» بلا ملف فعلي.

## 5. حالة الوصول المقاسة (30-10-2026 من الجلسة السحابية)

ناسا أجابت وحُمّلت صورة بترخيصها؛ ويكيميديا أجابت ثم حدّت المعدل (429)؛ واجهة متحف المتروبوليتان رفضت أحيانًا بجدار حماية (403)؛ وOpenverse لم تُجب (504). هذه المحوّلات مختبرة بلا شبكة في `.claude/skills/kosif-superpowers/evals/test_free_photos.py` (kosif-tool)، والنسخة المدمجة في `app/tests/test_v13_stock.py`، وتعمل عادة من جهاز منزلي. أعد القياس قبل الادعاء (`$D tool stock video probe` يكتب تقرير الوصول).
