# الهندسة العكسية لـ Krita 5.3.4: إزاي Claude يرسم بيه بالكود

**النتيجة:** `Krita.lnk` بيشغّل `C:\Program Files\Krita (x64)\bin\krita.exe`، وده مُشغّل صغير بيحمّل `krita.dll`. باب التحكم البرمجي الحقيقي هو `kritarunner.exe`، اللي بيشغّل بايثون 3.13 جوه Krita من غير واجهة، ومعاه موديول `krita.pyd` (غلاف SIP فوق `libkritalibkis.dll`). الرسم بالفيكتور والبكسلات والطبقات والفلاتر والتصدير لـ ‎.kra/PNG كله شغال من غير واجهة. أما فُرش Krita الأصلية (`paintLine`/`paintPath`) فبتوقّع البرنامج من غير نافذة، واتثبت ده بـ Frida وGhidra. على الأساس ده اتبنت مهارة `krita-draw`.

## الفرضيات (اتكتبت قبل التحليل)
| # | الفرضية | الحكم |
|---|---|---|
| ف1 | `krita.exe` مُشغّل صغير والشغل في DLLs | ✅ اتأكدت: ‎.text حجمه 6 كيلو، وبيستورد دالة واحدة من krita.dll |
| ف2 | بايثون بيكلّم Krita عن طريق `krita.pyd` (SIP) فوق libkis، و`kritarunner` بيشغّل من غير واجهة | ✅ اتأكدت: 867 import من libkritalibkis.dll، و`PyInit_krita`، و`kritarunner --help` |
| ف3 | فُرش الرسم (`paintLine`) محتاجة View، فبتوقع من غير واجهة | ✅ اتأكدت بدليلين: Frida (وقت التشغيل) وGhidra (الكود) |
| ف4 | برنامج مفتوح المصدر موقّع وسليم | ✅ موقّع Authenticode، ومفيش باكر، وFLOSS صفر نصوص مخفية، وcapa عادي |

## الاكتشافات اللي بنيت عليها المهارة
1. **مكان السكربتات:** `kritarunner` اسمه الداخلي «kritarunner»، فبيدوّر في `%APPDATA%\kritarunner\pykrita`، **مش** في `%APPDATA%\krita\pykrita` ولا في `PYTHONPATH`. اتعرف بتتبّع `GetFileAttributesExW` بـ Frida. أول تجربتين فشلوا بصمت (exit 0 من غير ما يعمل حاجة) لحد ما اتعرف ده.
2. **بروفايل منفصل:** نتيجة لـ (1)، الإعدادات والموارد بتاعته منفصلة عن Krita العادي، فبيشتغل وKrita المستخدم مفتوح من غير ما يتخانقوا.
3. **وقعة الفرشاة:** `Node::paintLine` ← `PaintingResources::createHelper`، وجواها السلسلة دي **من غير أي فحص null**:
   `KisPart::instance()->currentMainwindow()->activeView()->viewManager()->canvasResourceProvider()->resourceManager()`
   من غير نافذة، `currentMainwindow()` بترجّع null فيحصل Access Violation (0xC0000005).
4. **حتى النافذة المخفية بتوقع:** `openWindow()+addView()` بيوقعوا في `KisMainWindow::setMainWindowLayoutForCurrentMainWidget` ← `QAction::menu()` (قراية من عنوان null + 0x8)، لأن kritarunner مابيحمّلش أكشنز الواجهة. وبيحصل كده كمان مع `show()` من `showEvent`.
5. **الفيكتور غير متزامن:** طبقة SVG فاضية لحد ما أحداث Qt تشتغل (قبل: alpha=0، بعد ~1 ث: 255). ومن غير كده، `saveAs(.kra)` بيرجّع False لأن الصورة «مشغولة».
6. **ترتيب البكسلات:** RGBA/U8 = بايتات B,G,R,A، وده نفس `QImage.Format_ARGB32`. اتأكد بمربعات أحمر/أخضر/أزرق.
7. **المسارات العربي** بتبوظ جوه kritarunner (Latin-1)، والمجلد الحالي بيتضاف لـ `sys.path`، و`excepthook` بيفتح نافذة خطأ بتعلّق التشغيل الخفي.
8. **SVG:** الوحدات بتتقري كـ pt، فلازم width/height بالـ pt = البكسل × 72/dpi. واتأكد ده على dpi 72 و300.
9. **النص العربي** بيتشكّل صح (5 خطوط اتجرّبت)، و`direction=rtl` مع `text-anchor=start` عند الحافة اليمين.

10. **الأنيميشن من غير واجهة:**
    - `importAnimation` بيوقع.
    - `enableAnimation` + `setPixelData` بيعمل 0 keyframes.
    - **الحل:** صيغة ‎.kra. فكّيت ملف حفظه Krita، وطلّعت أسماء الدوال من `libkritalibkra.dll` (`KisRasterKeyframeChannel::frameFilename`، و`KisKraLoadVisitor::loadNodeKeyframes`)، وكتبت `keyframes.xml` بيشاور على ملفات بيانات طبقات موجودة.
    - Krita فتحه بـ 8 من 8 keyframes، والبكسلات صح في كل فريم.
    - لما Krita أعاد الحفظ بنفسه كتب نفس الصيغة بالظبط (`channel name="content"` / `keyframe time frame color-label` / `offset type="point"`)، وده تأكيد مستقل.
11. **الجسر الحي:** إضافات بايثون بتتعرّف من `pykrita/*desktop` وبتتفعّل بـ `enable_<name>` تحت `[python]` في kritarc (نصوص `kritapykrita.dll`). الإضافة اتبنت، بس **ماتركّبتش**: التركيب اترفض كـ «تثبيت دائم» لحد ما تيجي موافقة صريحة.

## ✅ / 🟡 / ❓
- ✅ **اتأكد بدليل:** مسار سكربتات kritarunner (Frida + تشغيل ناجح)، ووقعة الفرشاة وسببها (Frida + Ghidra)، والفيكتور غير المتزامن (قياس البكسل قبل وبعد)، وترتيب BGRA (مربعات RGB)، وحفظ ‎.kra بكل الطبقات (`krita_draw.py layers`)، والعربي المتشكّل (صورة)، والملفات مش مضغوطة (UPX، والإنتروبي، وFLOSS).
- 🟡 **استنتاج:** «Windhawk» في DIE إنذار غلط (~85%)، و«analysis tools strings» في capa من الـ crash handler (~80%)، وإن بلجن جوه Krita الحقيقي (بنافذة) هيخلّي `paintLine` يشتغل بالفُرش الأصلية (~85%، لأن نفس السلسلة هتلاقي نافذة).
- ❓ **مجهول:** الرسم بفُرش Krita الأصلية من غير ما Krita المستخدم يتقفل. اللي يحسمه: بلجن `%APPDATA%\krita\pykrita` بيراقب مجلد أوامر، وده محتاج إعادة تشغيل Krita بموافقتك. والأنيميشن (طبقات بفريمات) مااتجرّبش.

