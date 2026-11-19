# تقرير اختبارات Black Dragon v1990 — 2026-11-11

## محلي (pytest، بيئة Claude السحابية)
- `test_v1990_hf_free.py` (10) + `test_v1990_review_tools.py` (7) = **17 اختبار جديد**.
- مع الانحدار المختار (hf workflows، reel-dna، cinema-craft، v1017 merge، onscreen/hf، v10161 merge، v12 docs): **66 passed, 0 failed**.
- الاختبار الجديد مسك عطل حقيقي واتصلّح: `tool pack inspect/install` كان بيقع بـKeyError على ملف مش أرشيف.
- `test_v12_docs` مسك إن `references/LINKS.md` اتشال اسمه من SKILL.md وقت الاختصار: رجع.
- **السويت الكاملة ماتشغّلتش** في الجولة دي، فمفيش ادعاء عنها.

## على Higgsfield (اتنفّذ فعلًا، الرصيد 347.88 قبل وبعد، مفيش قيد جديد في transactions)
- Sandbox Standard: 2 vCPU / 8 GiB / من غير GPU. تحليل Katana (ريل 50 ث في 78 ث، وريل 60 ث ink-gold)، faster-whisper، color-grade، higgsedit (عربي بـfontFamily)، 3D Jutsu (still في 41 ث)، Match Cut `create_typewriter`، `media_upload`، `get_cost`.
- اتعاد في الجولة التالتة: `tiktok_accounts` = active، `tiktok_music_trending` EG/7DAY = 100 تراك، `scene_builder_3d_search_assets` = 994 موديل، وقراية نص المقال من الصفحة المرسومة ومطابقته بـ`CODE_FILM_V1990.md`.
- تصنيف 15 أمر reel-effects من نص تعليماتهم (8 بلا كريدت، 7 بخطوة ماسك مدفوعة): **قراية مش تشغيل**.

## اللي مااتثبتش
- رندر أنيميشن MP4 جوه 3D Jutsu: 48 فريم فضلت running أكتر من 7 دقايق من غير نتيجة.
- `scene_builder_3d_import_asset`، Sandbox XL، `video_analysis_create`، `virality_predictor`، `media_import_url`، وباقي الـ27 action في Match Cut.
- `/captions` وباقي مؤثرات الريل على مقطع حقيقي، و`/use-blender` على جهازه.
- مفيش فيلم إنتاج كامل اتعمل بالنسخة دي.
- بصمات MANIFEST = سلامة ملفات محلية، مش توقيع طرف تالت.
