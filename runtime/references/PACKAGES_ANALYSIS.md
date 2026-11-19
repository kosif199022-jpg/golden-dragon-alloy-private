# تحليل الحزم اللي في مجلد «هام» (2026-11-12)

فحص ثابت من غير فك: هوية كل حزمة من SKILL.md، نسخة المحرك، مقارنة الشجر بالـ CRC ملف بملف، فحص مفاتيح، وعدّ ملفات الكود اللي فيها أنماط تنفيذ أو شبكة أو مسح. الأداة: `analyze_ham.py` (بايثون، zipfile).

| الحزمة | الحجم | ملفات | الاسم | المحرك | مهارات | أدوات | سلامة zip | مفاتيح | exec / network / delete / download-run |
|---|---|---|---|---|---|---|---|---|---|
| `black-dragon-v10.17.0.zip` | 35.8 MB | 1240 | black-dragon | 10.17.0 | 12 | 34 | سليم | 1* | 210 / 54 / 27 / 3 |
| `black-dragon-v1990.4-all-powers.zip` | 41.9 MB | 1171 | black-dragon | 1990.4 | 29 | 42 | سليم | 1* | 231 / 37 / 33 / 4 |
| `black-dragon-v1990.9.0.zip` | 44.3 MB | 1569 | black-dragon | 1990.9.0 | 17 | 58 | سليم | 1* | 260 / 61 / 36 / 4 |
| `black-dragon-v1990.10.0.zip` | 64.6 MB | 1852 | black-dragon | 1990.10.0 | 30 | 60 | سليم | 1* | 289 / 63 / 41 / 5 |
| `white-dragon-v1.0.0.zip` | 64.9 MB | 1864 | white-dragon | 1990.10.0 | 30 | 60 | سليم | 1* | 290 / 64 / 42 / 6 |

\* النتيجة الوحيدة في كل الحزم هي `tools/re/rules/dragon_audit.yar`: قاعدة YARA بتدوّر على المفاتيح الخاصة (نمط، مش مفتاح). اتراجعت بالعين.

## البصمات

- `black-dragon-v10.17.0.zip`: sha256 `8b7c4245da0022272baa32f9144361271994daa1684729b31ed7d31f6c19cf28`
- `black-dragon-v1990.4-all-powers.zip`: sha256 `9b9c1de66efed52f6caca398bbb1dfe9475c2448f2e6caa8f30d8c483c230d13`
- `black-dragon-v1990.9.0.zip`: sha256 `2363648288235f757dfaeb9a8107c4b55f4a129508f132ad94b68d736e30d7c5`
- `black-dragon-v1990.10.0.zip`: sha256 `1972a8372fc2c2b553a03fdd4df2b3677ba16ee53ceca253662962fafa20c19b`
- `white-dragon-v1.0.0.zip`: sha256 `c2f9ad0b379d131c6b75a696fd7f48a7dc69faf803624720d9044137fb61169d`

## مين جوّه مين (ملفات في الأولى ومش في التانية / اتغيّرت / متطابقة)

- black-dragon-v10.17.0.zip → black-dragon-v1990.10.0.zip: 0 / 22 / 1218
- black-dragon-v10.17.0.zip → white-dragon-v1.0.0.zip: 0 / 22 / 1218
- black-dragon-v1990.4-all-powers.zip → black-dragon-v1990.10.0.zip: 0 / 27 / 1144
- black-dragon-v1990.4-all-powers.zip → white-dragon-v1.0.0.zip: 0 / 26 / 1145
- black-dragon-v1990.9.0.zip → black-dragon-v1990.10.0.zip: 0 / 26 / 1543
- black-dragon-v1990.9.0.zip → white-dragon-v1.0.0.zip: 0 / 20 / 1549
- black-dragon-v1990.10.0.zip → white-dragon-v1.0.0.zip: 5 / 10 / 1837
- white-dragon-v1.0.0.zip → black-dragon-v1990.10.0.zip: 14 / 10 / 1837

## الخلاصة
- `v10.17.0` و`v1990.9.0` و`v1990.4-all-powers` كلهم جوه `v1990.10.0` بالكامل (صفر ملف ناقص)؛ اللي «اتغيّر» نسخ أحدث من نفس الملفات.
- `white-dragon-v1.0.0` = محرك v1990.10.0 (لقطة أقدم بشوية: 5 ملفات ناقصة و10 مختلفة) + عقل `wd.py` و14 ملف جديد.
- التنين الأحمر اتبنى على `black-dragon-v1990.10.0.zip` النهائي مباشرة، فمفيهوش النقص ده.
- أنماط exec والشبكة طبيعية في حزمة مونتاج (ffmpeg، تحميل خامات). ملفات download-run الـ 5 موجودة في مهارات السحابة (تثبيت أدوات في sandbox) ومحكومة بموافقة.
