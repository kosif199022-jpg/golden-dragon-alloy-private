# TEST REPORT — v1990.3 candidate (2026-11-11)

اتشغّل على لابتوب صاحب التنين: Windows-11-10.0.26300-SP0، بايثون `C:\Users\cinde\AppData\Local\Programs\Python\Python312\python.exe`.

## اللي اتشغّل فعلًا
| الفحص | النتيجة |
|---|---|
| `pytest app/tests` (كل اختبارات الحزمة + `test_v19903_machine.py`) | 822 ناجح، 51 فاشل، 5 متخطّى (19 د 27 ث). المقارنة مع v1990.2 الأصلية لتحديد الفاشل من قبل كانت لسه شغالة وقت التحزيم |
| `python start.py` | exit 0، بيطبع السؤال والأمرين `mode laptop` و`mode cloud` |
| `tool machine scan --write` | 97 موجود من 108، و22 مكتبة بايثون، و34 مجلد PATH |
| `tool machine doctor` | 97 مسار موجود، 0 اختفى |
| `tool machine mode laptop` على اللابتوب | وضع اللابتوب، مع ترتيب الشغل |
| `DRAGON_MODE=cloud tool machine mode laptop` | بيقول إن الدليل بيخالف الإجابة ويعرض طريقين |
| `tool machine find بلندر` · `path ffmpeg` · `path jadx` | رجّعوا المسارات الصح |
| `tool machine pc battery` | قراية فعلية من الجهاز |
| `tool machine pc kill --target notepad` من غير `--yes` | exit 3 (مارفضش غلط ومانفّذش) |
| `DRAGON_MODE=cloud tool machine pc info` | exit 3 |
| `tool machine app status` | رد التطبيق المفتوح بنسخته ومحادثاته |

## اللي ماتجربش
- **التشغيل في محادثة claude.ai حقيقية أو على لينكس:** وضع السحابة اتجرّب بمحاكاة (`DRAGON_MODE=cloud`) على ويندوز بس. الكود مكتبة قياسية ومفيهوش حاجة خاصة بويندوز في `start` و`mode` و`map`، بس ماتشغّلش هناك.
- **أفعال `pc` اللي بتغيّر** (volume، kill، shutdown، uninstall…): اتجرّبت بوابة الموافقة بس.
- **`tool machine app send|ask`** من الحزمة: اتجرّب `status` بس (الإرسال اتجرّب من خادم MCP بتاع التطبيق).

## مش موجود على الجهاز وقت الفحص
handbrake, faster-whisper, sox, audacity, gallery-dl, rg, libreoffice, vscode, uv, ollama, montage-dir

## حدود
- خريطة الجهاز سجل لحظة الفحص (2026-11-11T16:10:37). بعد تثبيت أو شيل برامج: `tool machine scan --write`.
- المسارات فيها اسم مستخدم ويندوز. مفيهاش مفاتيح ولا كود ربط التطبيق (بيتقري من إعدادات التطبيق وقت التشغيل).
