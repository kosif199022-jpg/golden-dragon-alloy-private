# Higgsfield Blender — KOSIF v1990.4 (تجربة لا تشغيل سحابي)

## مصدر الدمج
- `hf-blender-render.rar`: سبعة ملفات أصلية (مشهد Python، صوت Python، ثلاث سكربتات Bash، pack.py، SKILL.md).
- الحزمة الأساسية: `black-dragon-v1990.3.1-desktop-safety-candidate.zip`.
- النسخ `1990(1).zip` و`black-dragon-v10.17.0(1).zip` و`black-dragon-v10.16.1(1).zip` تطابق محتوى نظائرها الموجودة سابقًا (ZIP محتوى، لا بالضرورة ضغط/بايت).
- `skills-library(1).zip`، `skills-library-3(1).zip`، `faceless-shorts-skill(1).zip` تطابق الإصدارات السابقة بالبايت.
- `black-dragon-v10.1.0(1).zip`، `10.2.0(1)`، `10.10.0(1)` إصدارات تاريخية أقدم؛ لم تُستبدل بها الأدوات الأحدث.

## الأدوات الجديدة
`python scripts/dragon.py tool hf-blender doctor|source|policy` لعرض مصدر الأداة/وضعها

`python scripts/dragon.py tool hf-blender plan --frames 150 --workers 2 --samples 24 --resolution 100` لتقسيم الفريمات

`python scripts/dragon.py tool hf-blender pack hatch skills/hf-blender-render/scenes/hatch_scene.py skills/hf-blender-render/scenes/hatch_sound.py --out /tmp/hf_handoff.sh` لإنتاج سكربت تسليم **لا يُشغّل ولا يُرفع تلقائيًا**

`python scripts/dragon.py tool hf-blender check-frames frames --frames 150` لفحص الفريمات المتتالية وPNG signature/IEND وأبعاد الإطارات

## قيود وأذونات
- **لا يوجد إثبات رسمي أن Higgsfield XL مجاني**. أي تجربة حقيقية تحتاج موافقة المستخدم على تشغيل XL، تنزيل Blender، رفع الملفات، والتحقق من التكلفة.
- `Cycles CPU` هو الافتراضي للسيناريو، و`EEVEE` يحتاج smoke test لبيئة الرسومات.
- رندر مقطع 5 ثوان / 150 فريم بمواصفات 1080×1920 في الملف المصدر **لم يُنفذ على XL هنا**.
- تنزيل Blender الرسمي متوقف افتراضيًا: يجب الموافقة وضبط `HF_BLENDER_ALLOW_DOWNLOAD=YES`، ولم نتأكد من صلاحية رابط نسخة 5.2.3.
- قد يحتاج المشهد تحديثات لإصدار Blender الفعلي. غياب runtime GPU/Blender في الجلسة يمنع اعتبار المشروع مكتمل التنفيذ.
- سكربت finish يفشل بصراحة عند نقص فريم أو خطأ مقاس/FPS/فك الفيديو أو فشل QC sheet.
- تحذير: فحص PNG هنا سريع ولا يغني عن فك الصورة بالكامل أو مراجعة المشهد بالعين.
- لا تضمّن مفاتيح، أو توكنات، أو ملفات مستخدم خاصة في handoff.
