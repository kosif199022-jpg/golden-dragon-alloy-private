# ربط التنين الأحمر بتطبيق التنين على ويندوز

- `brain.py`: بيتحط جنب `app.py`. قبل كل رسالة بيسأل `~/.claude/skills/red-dragon/scripts/rd.py` عن ملخص المهمة (الطلب بعد فك الكتابة، الطريق، الموافقات، بوابة التسليم، الدروس) ويحطه قدام النموذج. أي فشل = من غير ملخص، والشات يكمل عادي.
- `patch_app_brain.py APP_DIR`: بيعدّل `app.py` (استيراد brain، الحقن في `start()`، قسم في برومبت النظام، `brain_status` / `set_brain` / `understand` للواجهة) و`ui/index.html` (سطر 🧠 قابل للفتح). كل استبدال عليه assert إن النص موجود مرة واحدة.
- الإيقاف: `set_brain(False)` أو `"brain": false` في `%APPDATA%/BlackDragon/settings.json`. محادثات «بدون ذاكرة» مابيتحقنش فيها حاجة.
- بعد التعديل: `python -m py_compile app.py brain.py` ثم `powershell -File build.ps1` (الرام الفاضية ≥ 4 جيجا) ثم التثبيت والتطبيق مش مشغول.
