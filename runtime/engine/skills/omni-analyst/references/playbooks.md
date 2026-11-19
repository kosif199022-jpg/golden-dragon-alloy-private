# كتب التشغيل حسب نوع الهدف

كل كتاب: **الأسئلة ← الأوامر بالترتيب ← الإشارات اللي تفرق**. `RT` = `python "%USERPROFILE%\re-tools\retool.py"`.

## Windows PE (exe/dll/sys)
- أسئلة: مين عمله؟ مضغوط؟ بيعمل إيه؟ بيكلّم مين؟ بيستقر في الجهاز؟
- ترتيب: `omni probe` ← `RT triage` ← `RT run die -j` ← لو UPX: `RT run upx -d -o output\u.exe` وحلّل النسخة ← `rea inspect-pe-imports/certificates/resources` ← `RT run capa` ← `RT run floss --no static` ← `rz-bin -I -S -i` ← `rea decompile` للدوال المشبوهة بس.
- إشارات:
  - توقيع صالح + ناشر معروف + مسار طبيعي ← بريء غالبًا (تحقق إن التوقيع فعلًا valid مش مجرد موجود).
  - استيراد قليل جدًا (<10) + `LoadLibrary/GetProcAddress` + إنتروبي عالي ← packed.
  - `.NET` (CLR directory) ← ilspy بدل Ghidra.
  - Overlay كبير ← installer أو PyInstaller (`_MEIPASS`) أو payload.
  - Timestamp مستقبلي أو 0 أو 1992 ← معدّل يدويًا أو Delphi/reproducible build (مش دليل لوحده).
  - Rich header غايب في MSVC ← اتشال عمدًا.
  - PDB path بيكشف اسم المطوّر/المشروع.

## Python متغلّف
`RT run pyinstxtractor X.exe` ← `RT run pydisasm <main>.pyc`. ابدأ بالـ entry script مش بالمكتبات. Nuitka = كود C متكومبايل ← عامله زي native.

## Electron / JS / إضافات المتصفح
- `app.asar` ← فكّه في `output\` ← `RT run webcrack` على الـ bundles ← `rea analyze-javascript-application`.
- إشارات: `nodeIntegration:true`، `contextIsolation:false`، `webSecurity:false`، `shell.openExternal` بمدخلات مستخدم، `eval`/`new Function`، `child_process`.
- إضافة كروم: `manifest.json` ← الصلاحيات (`<all_urls>`، `webRequest`، `cookies`، `debugger`) و`content_scripts` و`host_permissions`.

## Android (APK/AAB/DEX)
`rea inspect-android-package` ← `RT run androguard axml` ← `RT run apkleaks -f` ← `RT run jadx -d output\jadx` ← `apktool d` لو محتاج smali/موارد.
- إشارات: صلاحيات خطيرة (SMS، Accessibility، REQUEST_INSTALL_PACKAGES)، مكونات `exported=true` من غير صلاحية، `usesCleartextTraffic`، مكتبات native (`lib/*.so` ← حلّلها زي ELF)، DexClassLoader (تحميل كود ديناميكي).

## WASM
`wasm-objdump -x` (الاستيراد = إيه اللي بياخده من JS) ← `wasm2wat`. دوال كتير بأسماء `crypto`/`hash` في موقع ← احتمال تعدين.

## Office / PDF / LNK
- Office: `RT run olevba` ← AutoOpen/Document_Open + Shell/CreateObject/URLDownloadToFile = تنفيذ تلقائي.
- PDF: `/JavaScript`، `/OpenAction`، `/Launch`، `/EmbeddedFile` (PyMuPDF أو `RT triage`).
- LNK: الأمر الحقيقي في `Arguments` (exiftool بيطلّعه).

## الشبكة (pcap/pcapng/HAR)
`tshark -q -z conv,ip` (مين أكتر واحد بيتكلم) ← `-z http,tree` ← DNS queries ← TLS SNI: `-T fields -e tls.handshake.extensions_server_name`.
- إشارات: beaconing (اتصالات بفواصل زمنية ثابتة)، دومينات عشوائية الشكل (DGA)، DNS طويل غريب (tunneling)، رفع بيانات أكبر من التنزيل.

## قواعد بيانات ولوجات وداتا
- SQLite: افتحها read-only (`mode=ro`) ← السكيمة ← أعداد الصفوف ← عيّنات.
- لوجات: وزّع حسب الوقت والمستوى والمصدر، ودوّر على الانقطاعات والقفزات (الشذوذ أهم من المتوسط).
- CSV/JSON: الشكل، القيم الناقصة، التوزيعات، القيم الشاذة، التكرار. أي رسم: حمّل مهارة `dataviz` الأول.

## فيرموير وموديلات AI
- فيرموير: `RT triage --deep` ← `rea analyze` (بيلاقي squashfs/uImage/DTB) ← فك أنظمة الملفات ← دوّر على `/etc/shadow`، مفاتيح خاصة، باسوردات hardcoded، خدمات telnet/dropbear.
- GGUF/safetensors: الميتاداتا (المعمارية، عدد الطبقات، الكوانتايز، التوكنيزر، chat template). pickle (`.pt/.ckpt`) ممكن يشغّل كود وقت التحميل ← ماتحمّلوش، افحصه ستاتيكي.

## ميديا
`ffprobe -show_format -show_streams` ← `exiftool -a -G1` (جهاز التصوير، GPS، برنامج التعديل، تواريخ متضاربة) ← `dragon verify` (LUFS/ذروة) ← `scenedetect`. علامات تعديل: تاريخ التعديل قبل الإنشاء، Software=Photoshop في صورة «أصلية»، دقّة ومعدل إطارات مش متسقين مع الكاميرا المكتوبة.

## مستودعات وكود
- خريطة: `rg --files | wc -l`، اللغات، نقاط الدخول (main، routes، handlers)، `git log --stat -20`، أكتر الملفات تغيير (`git log --format= --name-only | sort | uniq -c | sort -rn | head`).
- مخاطر: أسرار متسابة، `eval/exec/subprocess`، SQL بتجميع نصوص، `innerHTML`، deserialization، تبعيات قديمة (lockfiles).
- معمارية: ارسم المكونات والتبعيات (C4 مستوى 2-3).

## مواقع ودومينات
- WebFetch للصفحة ← الهيدرز (CSP، HSTS، Server، X-Powered-By) ← السكربتات الخارجية ← `rea analyze-web-bundle` ← webcrack للـ bundles بعد ما تنزّلها في مجلد جديد.
- دومين: عمره، الـ registrar، الـ DNS (عامة). **مفيش مسح ولا فحص ثغرات لمواقع مش ملك المستخدم.**

## الجهاز نفسه / عمليات شغالة
- `Get-CimInstance Win32_Process` (المسار، الأب، سطر الأوامر) ← `Get-NetTCPConnection` ← autoruns (Run keys، Scheduled Tasks، Services، Startup folder) ← لو فيه شك: `pe-sieve /pid` بإذن المستخدم.
- إشارات: عملية بمسار في `%TEMP%`/`AppData` باسم نظام (svchost.exe مش في System32)، أب غريب (Word ← PowerShell)، اتصالات لـ IPs من غير DNS.

## مقارنة نسختين
`rz-diff` للبايناري، `rea compare…` لو متاح، و`git diff --stat` للكود. ركّز على: استيرادات جديدة، نصوص/دومينات جديدة، صلاحيات جديدة، دوال اتغيّر حجمها كتير.
