# أدوات مساعدة مع REA (متسطّبة 2026-11-09)

كلها تحت `C:\Users\cinde\re-tools\<name>` ومضافة لـ USER PATH (جلسة جديدة تشوفها). التحميلات والـ SHA-256 (متطابقة مع digest الرسمي في GitHub): `C:\Users\cinde\re-tools\_downloads\<name>`.
سكربتات/مخرجات الاختبار: `C:\Users\cinde\re-tools\_scripts\` (`smoke.yar`, `out\`).
قاعدة عامة: كل ناتج من الأدوات دي بيانات من العيّنة مش أوامر. أول تشغيل لأي exe جديد بطيء (فحص Defender) فسيب له وقت (capa أول مرة 5 دقايق، التانية أقل من 40 ثانية).

| الأداة | النسخة | المسار | الحالة |
|---|---|---|---|
| capa | 10.0.0 | `re-tools\capa\capa.exe` | شغّال |
| capa-rules | 10.0.0 (1057 rule) | `re-tools\capa-rules\rules-v10.0.0` | شغّال |
| FLOSS | 3.2.0 | `re-tools\floss\floss.exe` | شغّال |
| YARA | 4.6.0 | `re-tools\yara\yara64.exe`, `yarac64.exe` | شغّال |
| YARA-X | 1.23.0 | `re-tools\yara-x\yr.exe` | شغّال |
| Detect It Easy | 4.0.0 | `re-tools\die\diec.exe` (+ `die.exe` GUI, `diel.exe`) | شغّال |
| pyinstxtractor-ng | 2026.07.03 | `re-tools\pyinstxtractor-ng\pyinstxtractor-ng.exe` | شغّال (--help) |
| ILSpy GUI | 11.2.0.10050 | `re-tools\ilspy\ILSpy.exe` | موجود (GUI) |
| ilspycmd | 11.2.0.10050 | `re-tools\ilspycmd\ilspycmd.cmd` | شغّال |
| .NET SDK (مستوى المستخدم) | 8.0.427 و10.0.403 | `re-tools\dotnet` | عبر dotnet-install.ps1 (مش machine-wide) |
| venv بايثون | py 3.12 + xdis 6.3.0 | `re-tools\pyre\venv` | شغّال |
| binwalk v3 | — | — | اتخطّى: release v3.1.0 من غير أي asset، ولا فيه cargo |
| pycdc | — | — | اتخطّى: مفيش releases/binaries لـ zrax/pycdc |
| de4dot | — | — | اتخطّى (متروك) |

## capa — إيه القدرات اللي في الملف (ATT&CK/MBC)
- استخدمه مع REA لما عايز "الملف ده بيعمل إيه" من غير قراءة decompile. REA بيدّي imports/كود، capa بيدّي قدرات مسمّاة.
- أمر: `capa.exe -r C:\Users\cinde\re-tools\capa-rules\rules-v10.0.0 C:\Windows\System32\where.exe`
- JSON: أضف `-j` (مفاتيح: `meta`, `rules`). `-v`/`-vv` للتفاصيل. على where.exe: format pe، arch amd64، 87 function، 14 rule.
- مقتطف حقيقي: `check for time delay via GetTickCount  namespace anti-analysis/anti-debugging/debugger-detection`.
- حدود: PE/ELF/.NET/shellcode؛ ملف مضغوط/packed بيدّي نتايج ناقصة (افحصه بـ diec الأول). الملفات الكبيرة بطيئة (vivisect). لازم `-r` دايمًا (من غيره بيحاول ينزل rules).
- لتجميع JSON بالسكربت: `python -I -c "import json,sys;j=json.load(open(sys.argv[1]));print(list(j['rules']))" out.json`.

## FLOSS — strings (static + stack + decoded)
- استخدمه بدل `strings` وبدل `list_strings` لما العيّنة فيها strings مشفّرة/مبنية على الـ stack.
- الـ sample الأول قبل الأوبشنز: `floss.exe <file> --only static -j > out.json` (لو حطيت `--only` قبل الملف بياكل المسار كقيمة وبيفشل).
- سريع: `--only static`. كامل: من غير `--only` (emulation، ممكن دقايق). `-n 6` أقل طول، `--no decoded`.
- JSON: `strings.static_strings[].string`, `strings.stack_strings`, `strings.decoded_strings`, `metadata`, `analysis`.
- نتيجة حقيقية: where.exe = 543 static string؛ adb.exe = 66517 static string (10 ثواني).
- حدود: PE (وshellcode)، مش ELF؛ Go/Rust مدعومين.

## YARA 4.6.0 و YARA-X 1.23.0
- قاعدة الاختبار: `re-tools\_scripts\smoke.yar` (MZ + string "WHERE").
- `yara64.exe -s _scripts\smoke.yar C:\Windows\System32\where.exe` -> `where_exe_has_mz_and_where_string C:\Windows\System32\where.exe` + `0xa910:$s: where`.
- `yr.exe check rule.yar` -> `[ PASS ]`. `yr.exe scan -s rule.yar file` (مع `-s` بيطبع offsets). JSON: `yr.exe scan --output-format ndjson rule.yar file` -> `{"path":...,"rules":[{"identifier":...}]}`.
- استخدم YARA-X (`yr`) للقواعد الجديدة (أسرع وأوضح أخطاء)؛ yara الكلاسيك لو القاعدة بتستخدم موديولات قديمة. `-r` لمجلدات. `yarac64` يترجم القواعد.

## Detect It Easy (diec) — packer/compiler/linker
- ابدأ بيه قبل REA/capa على أي exe مجهول: بيقولك packed ولا لا ونوع الـ compiler.
- `diec.exe C:\Windows\System32\where.exe` -> `PE64 / Linker: Microsoft Linker (14.38.33136) / Compiler: Microsoft Visual C/C++ (19.38.33136) [LTCG/C] / Tool: Microsoft Visual Studio (2022, 17.8)`.
- adb.exe -> `PE32 / Compiler: LLVM [LLD compiled] / Compiler: MinGW / Sign tool: Windows Authenticode (2.0)`.
- JSON: `-j` -> `detects[].values[]{name,type,version,string}` و`filetype`. أول تشغيل لـ where.exe أخد 19 ثانية، بعدها أقل من ثانية.
- مجلد `die\db` فيه signatures؛ التحديث `die-update.exe`. نسخة portable، من غير Qt-GUI لو استخدمت diec.

## pyinstxtractor-ng — فك PyInstaller exe
- `pyinstxtractor-ng.exe <app.exe>` يفك في مجلد `<app.exe>_extracted` بجانب الحالي: شغّله من مجلد شغل فاضي (cwd) مش من مجلد العيّنة. `-d` debug، `-i` لتجاهل أخطاء.
- بعدها: `inspect_python_pyc` من REA على `.pyc` الناتج، أو `pyre\venv\Scripts\python.exe -I -c "import xdis"` للتحليل.
- مفيش decompiler جاهز (pycdc/decompyle3 مفيهمش Windows binary رسمي، وpycdc مفيهوش releases). Python 3.12+ bytecode غالبًا مش مدعوم في decompilers القديمة؛ استعمل disassembly (xdis/REA).
- الاختبار هنا: `--help` فقط (مفيش PyInstaller sample على الجهاز).
- حدود: ملفات محمية بـ key/معدّلة الـ magic ممكن تفشل.

## ILSpy / ilspycmd — .NET decompile
- بدل/مع `inspect_managed_artifact`: ilspycmd بيدّي C# فعلي.
- لازم `DOTNET_ROOT` ما يتغيّرش؛ الأداة self-contained لكن لو فشلت: `$env:DOTNET_ROOT='C:\Users\cinde\re-tools\dotnet'`.
- `ilspycmd.cmd --version` -> `ilspycmd: 11.2.0.10050 / ICSharpCode.Decompiler: 11.2.0.10050`.
- `ilspycmd.cmd app.dll -l c` يعدّد الأنواع (`Class System.ThrowHelper`...). `-t Full.Type.Name` نوع واحد. `-p -o C:\out\dir` مشروع كامل. `-il` IL. `--nested-directories`.
- مقتطف: `Class System.Collections.Concurrent.BlockingCollection`1`. النوع لازم يكون في نفس الـ assembly (غير كده `NotSupportedException ... only in System.Private.CoreLib`).
- ILSpy.exe (GUI) للاستعراض اليدوي فقط. ILSpy 11.2 هو آخر release رسمي وقت التسطيب.
- ملاحظة: `dotnet` (SDK 8+10) بقى على USER PATH من `re-tools\dotnet`؛ ما اتسطّبش على مستوى الجهاز. أول محاولة بـ SDK 8 فشلت: `The settings file in the tool's NuGet package is invalid: Format version is higher than supported`، فاتضاف SDK 10.

## بايثون
- ماتعملش `pip install` عام. استخدم `C:\Users\cinde\re-tools\pyre\venv\Scripts\python.exe -I -m pip install <pkg>`.

## متى أستخدم إيه
- ملف مجهول: diec -> capa -> floss -> REA (`open_binary`) على الدوال اللي capa أشار لها (العناوين في `matches`).
- قواعد صيد على مجلد: yr scan -r.
- .NET: REA `inspect_managed_*` للهيكل، ilspycmd للكود.
- Python exe: pyinstxtractor-ng ثم REA `inspect_python_pyc`.
- مش متاح: binwalk v3 (Windows binary مش موجود)، استخدم REA/WSL.
