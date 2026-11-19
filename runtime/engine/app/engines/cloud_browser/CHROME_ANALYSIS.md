# تحليل Google Chrome المتسطّب على الجهاز

اتعمل في 2026-11-10 بأدوات REA (inspect-pe-imports وinspect-pe-certificates) ومعاها جرد للملفات والعمليات.
التحليل ده للفهم بس: ماحصلش أي decompile لكود جوجل، وماتنسخش منه أي حاجة.

## 1. اللي اتأكد بدليل

| البند | القيمة | المصدر |
|---|---|---|
| المسار | `C:\Program Files\Google\Chrome\Application\chrome.exe` | الملف نفسه |
| النسخة الشغالة | 156.0.8078.81 (وفيه 157.0.8103.40 متنزّلة ومستنية تتفعّل: `new_chrome.exe`) | VersionInfo وأسماء الفولدرات |
| المعمارية | PE32+ x86-64، حجمه 4.27 MB، وبصمته sha256 `314aca34…e378` | REA |
| التوقيع | Authenticode بـ SHA-256 من «Google LLC» (Mountain View)، والسلسلة DigiCert Trusted G4 Code Signing RSA4096 SHA384 2021 CA1، وعليه ختم وقت DigiCert 2026 | REA inspect-pe-certificates (فك هيكلي للتوقيع، من غير تحقق تشفيري) |
| الاستيرادات | 16 DLL و368 دالة (247 مباشرة و121 delay-load) | REA inspect-pe-imports |

### إيه اللي الاستيرادات بتقوله عن تصميم كروم
- **`chrome_elf.dll`** (`IsBrowserProcess` و`SignalInitializeCrashReporting` و`GetInstallDetailsPayload`): البرنامج بيحمّلها الأول عشان تحمي الذاكرة بدري وتشغّل الـ crash reporting.
- **دوال الـ sandbox**، زي `CreateRestrictedToken` و`CreateProcessAsUserW` و`CreateJobObjectW` و`SetProcessMitigationPolicy` و`DeriveAppContainerSidFromAppContainerName` و`CreateDesktopW` و`CreateWindowStationW`. دي آلية Chromium المعروفة: كل renderer بيشتغل في عملية متقيّدة الصلاحيات، وعلى desktop منفصل.
- **التواصل بين العمليات (IPC)** عن طريق `CreateNamedPipeW` و`ConnectNamedPipe` و`TransactNamedPipe`. ده الأساس اللي Mojo IPC مبني عليه بين العمليات.
- **`dbghelp!MiniDumpWriteDump`**: كتابة تقارير الأعطال (Crashpad).
- **`WINHTTP`**: طلبات شبكة صغيرة من الـ exe نفسه، وغالبًا دي للتحديث والإبلاغ. الشبكة الأساسية للتصفح جوه `chrome.dll`.
- الـ exe نفسه تقريبًا مجرد launcher. المحرك كله في **`chrome.dll` اللي حجمه 292 MB** (Blink وV8 والشبكة والواجهة).

### مكونات الفولدر
`chrome.dll` (292 MB)، و`resources.pak` (25 MB، موارد الواجهة)، و`dxcompiler.dll` و`d3dcompiler_47.dll` (WebGPU/DirectX)، و`vk_swiftshader.dll` (GPU برمجي احتياطي)، و`optimization_guide_internal.dll` (24 MB، موديلات ذكاء اصطناعي على الجهاز)، و`libLiteRtWebGpuAccelerator.dll` (تشغيل موديلات LiteRT على WebGPU)، و`icudtl.dat` (يونيكود)، و`v8_context_snapshot.bin`، وفولدر `WidevineCdm` (DRM)، وفولدر `Locales`، و`elevation_service.exe` (خدمة الصلاحيات المرفوعة).

### العمليات الشغالة دلوقتي
عملية browser واحدة، ومعاها renderer وgpu-process وutility وcrashpad-handler. ده نموذج Chromium متعدد العمليات.

## 2. استنتاج (مش دليل مباشر)
- كروم = Chromium مفتوح المصدر (BSD) + إضافات مقفولة من جوجل (Widevine، والمزامنة، وoptimization guide). عشان كده الطريق الشرعي والعملي لـ«متصفح زيه» إنك **تبني على Chromium نفسه**، مش إنك تنسخ كروم.
- فكرة «المتصفح السحابي» (Remote Browser Isolation) معناها إن عمليات الـ renderer المتقيّدة دي تتنقل لسيرفر، والعميل يستلم صورة الصفحة بس. ده بيدّي عزل أقوى من الـ sandbox المحلي، لأن مفيش كود من المواقع بيوصل لجهازك أصلًا.

## 3. لسه مجهول
- التحقق التشفيري من التوقيع (REA فك الهيكل بس).
- محتوى `chrome.dll` من جوه: ماتحللش، لأنه محتاج Ghidra لساعات ومش لازم للمشروع.
