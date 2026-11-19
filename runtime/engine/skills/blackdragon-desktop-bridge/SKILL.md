---
name: blackdragon-desktop-bridge
description: "جسر اختياري آمن لتشخيص القدرات الموجودة في تطبيق BlackDragon على ويندوز وقراءة معلومات أو التقاط صورة للشاشة بموافقة صريحة. لا ينفذ أوامر نظام أو ينقل بيانات المتصفح."
---

# BlackDragon Desktop Bridge (Red Dragon)

المصدر: `BlackDragon(2).rar` مملوك لصاحب المشروع. الفحص الثابت كشف أداة تطبيق ويندوز `BlackDragon.exe` ومكوّنات `_internal/mcp_control.py`, `_internal/voice.py`, `_internal/chrome_extension/`, `_internal/ui/index.html` وبيانات Chrome خاصة. **لا تتطلب هذه المهارة استخراج بيانات Chrome أو تشغيل البرنامج من الأرشيف.**

## النتائج
- `mcp_control.py` و`voice.py` وملفات إضافة Chrome **متطابقة SHA-256** مع المكونات الموجودة في Red Dragon v2.7؛ لا داعي لنسخها ثانيةً.
- واجهة `index.html` مختلفة/أحدث، وتعرض مكتبة مهارات وحالة الحساب وآلية تحديث. لا تستبدلها مباشرة: وظائف backend الموافقة ليست جميعها موجودة في تطبيق v2.7 المرفق.
- يوجد مسار أصلي يتحكم في PC وChrome والنظام عبر localhost+token مع توقف طوارئ وموافقات التطبيق؛ **لا تدّعِ أن الأوامر تعمل هنا ما لم تُجرّب على جهاز ويندوز فعلي**.

## الاستخدام
```bash
python scripts/rd.py desktop catalog
python scripts/rd.py desktop doctor
# اختياري: من جلسة محلية فتحها تطبيق BlackDragon نفسه؛ يتطلب BD_TOKEN + BD_SID
python scripts/rd.py desktop snapshot --source computer --out screenshot.jpg --confirm-local-read
python scripts/rd.py desktop read system info --confirm-local-read
```

## حدود الأمان
- لا نشر ولا نسخ لحسابات/متصفحات/ملفات الجلسات/قواعد التاريخ أو الكوكيز. لا طباعات لرمز التوثيق أو نص صفحات الويب. أي لقطة شاشة تخص المستخدم وتُحفظ محليًا فقط بإذنه.
- `desktop` هنا *قراءة فقط*: رُفضت عمليات الكتابة، النقر، تشغيل البرامج، تبديل الحسابات، تثبيت المهارات وتحديث التطبيق.
- تنفيذ أي مهارة على جهاز المستخدم يستلزم اتصالًا حيًا واختبارات وموافقات منفصلة؛ الأرشيف نفسه ليس دليلًا على تشغيله الحالي.
- لا تُخلط واجهة v2.7 بالواجهة المستخرجة من EXE دون ترقيع backend واختبارات توافق شاملة.
