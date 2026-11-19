---
name: media-hunter
description: صيّاد الميديا — بحث فائق السرعة في 615 موقع فيديو وصور وخامات وأيقونات للمونتاج، مع بحث حي متوازي في 19 مصدر API (15 منهم من غير مفتاح) يرجّع روابط ملفات حقيقية (عالية الدقة، برخصها) وتحميل بأمر واحد مع تسجيل المصدر. Use whenever the user wants footage, b-roll, stock video, photos, archive/historical media, museum art, HDRIs, textures, wallpapers, icons or GIFs for a montage or design — «دوّر على فيديو/صور»، «هاتلي لقطات»، «فوتيج»، «خلفية»، «HDRI»، «صور أرشيفية»، «مواقع ستوك» — or asks which site has a kind of media. Use it BEFORE generic WebSearch for media.
---

# Media Hunter

المحرك: `C:\Users\cinde\OneDrive\Desktop\تحليل\media_hunter\mh.py` (شغّله دايمًا بـ `python -I`).

## الأمر الأساسي (استدعاء واحد)
```
python -I "C:\Users\cinde\OneDrive\Desktop\تحليل\media_hunter\mh.py" hunt "<english query>" --type video
```
- بيرجّع JSON فيه:
  - `results`: ملفات حقيقية فيها `media_url` و`page_url` و`width`/`height` و`duration` و`license` و`source`، ورقم `n` تستخدمه في التحميل.
  - `more_sites`: أنسب المواقع من الكتالوج (615 موقع) بروابط بحث جاهزة فيها الطلب نفسه.
- الوقت: 1–4 ثواني من غير كاش، وأقل من ثانية لو الطلب اتعمل قبل كده (الكاش 24 ساعة).
- **ترجم طلب المستخدم لإنجليزي قصير ومحدد قبل ما تبعته** (مثال: «جمل في الصحرا وقت الغروب» تبقى `camel desert sunset`). فيه قاموس عربي احتياطي، بس الإنجليزي بيجيب نتايج أحسن بكتير.
- `--type`: `any` (فيديو+صور، وده الافتراضي) | `video` | `image` | `art` (متاحف CC0) | `hdri` | `texture` | `3d` | `icon` | `gif` | `wallpaper`
- فلاتر: `--min-width 3840` (4K)، `--orientation portrait` (ريلز 9:16)، `--free` (للمواقع)، `--limit 30`، `--per-source 15`.

## أوامر تانية
| الأمر | بيعمل إيه |
|---|---|
| `search "q" --type video` | زي hunt بس جدول مقروء للبني آدم |
| `sites "q" [--type] [--free] [--json]` | أنسب المواقع من الكتالوج، وبيرد في حوالي 40ms من غير نت |
| `links "q" [--type]` | صفحة HTML في `تحليل\output` فيها روابط البحث في كل المواقع المناسبة (عشان المستخدم يفتحها في المتصفح) |
| `get 1 4 7 -o "<مجلد الشغل>\footage"` | يحمّل نتايج من آخر hunt/search بالرقم، وبيكتب `sources.txt` (المصدر والرابط والرخصة والمؤلف). Poly Haven بيتحمّل بدقة `--res 4k`، وأرشيف الإنترنت بيتحمّل بـ yt-dlp |
| `keys` | يعرض المصادر المفعّلة والمقفولة |
| `build` | يعيد بناء الفهرس بعد تعديل الكتالوج أو القوالب |

## المصادر الحية (من غير مفتاح)
- فيديو: Wikimedia Commons، NASA، Internet Archive، Europeana
- صور: Openverse (فيها Flickr وrawpixel وغيرهم)، Wikimedia، NASA، Europeana، Smithsonian، Wellcome
- فن ومتاحف CC0: Art Institute Chicago، Cleveland، V&A، SMK
- خامات وHDRI و3D: Poly Haven، ambientCG
- تانيين: Iconify (أيقونات)، Wallhaven (خلفيات)

**مقفولة لحد ما يتحط مفتاح مجاني في `media_hunter\keys.json`** (شوف `keys.example.json`): Pexels وPixabay، ودول أهم مصدرين لفوتيج ستوك 4K حديث، وكمان Unsplash وGIPHY. لو المستخدم عايز فوتيج ستوك حديث والمفاتيح مش موجودة، قوله إن المفتاح مجاني ودقيقة واحدة يطلعه. ولحد ما يتحط، استخدم روابط `more_sites`.

## طريقة الشغل
1. نفّذ `hunt` بطلب إنجليزي والنوع المناسب. لو الطلب ريلز ضيف `--orientation portrait`، ولو عايز أعلى جودة ضيف `--min-width 3840`.
2. اعرض على المستخدم أحسن النتايج (المصدر والدقة والرخصة)، ومعاها 3–5 مواقع من `more_sites` بروابطها.
3. حمّل بـ `get` في مجلد الشغل، واتأكد من الملفات بـ verify_media أو ffprobe قبل ما تقول إنها اتحملت.
4. نبّه على الرخص المقيدة: CC BY-NC، وBY-SA، و«حقوق محفوظة»، ومحتوى Wallhaven حقوقه لأصحابه.
5. لو مصدر رجع «فشل» في `sources`، كمّل بالباقي. المصادر بتشتغل بالتوازي، ومهلة كل مصدر 8 ثواني.
