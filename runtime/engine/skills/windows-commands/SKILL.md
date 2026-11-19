---
name: windows-commands
description: فهم ويندوز للأوامر — إزاي PowerShell 5.1 وcmd وGit Bash (MSYS2) والبرنامج نفسه بيقروا الأمر فعلًا، مقاس على الجهاز بالتجربة والهندسة العكسية (ILSpy وGhidra وFrida) ومن 4,246 أمر حقيقي. فيه فاحص قبل التنفيذ (wincmd_lint.py — 73% من الفشل الحقيقي و0.8% إنذار غلط)، وInvoke-NativeExact لتمرير المعاملات بالظبط من PowerShell 5.1، واختبار ذاتي. Use BEFORE running any non-trivial command on Windows and when a command fails strangely — quotes inside python -c, empty args to an .exe, Arabic text or paths, mojibake, cp1252 UnicodeEncodeError, ParserError, «unexpected EOF while looking for matching», exit 255 or 1 with good output, robocopy exit 1, «is not recognized», /c becoming C:/, long heredocs, Get-Content/Out-File encoding, && in PowerShell, Bash vs PowerShell tool. Triggers — «الأمر مش شغال»، «ويندوز فاهم غلط»، «علامات التنصيص»، «العربي باظ»، «exit code».
---

# فهم ويندوز للأوامر (windows-commands)

كل اللي هنا اتقاس على الجهاز ده يوم 2026-11-11: Windows 11 10.0.26300، وWindows PowerShell **5.1** (pwsh 7 مش متثبت)، وcmd 10.0.26100، وGit Bash (MSYS2 3.6.10)، وPython 3.12. الأدلة كاملة في `references/evidence.md`.

## النموذج: الأمر بيتقري مرتين

1. **الشيل بيعيد كتابة السطر.**
   - **PowerShell:** بيجمع المعاملات من غير escaping.
   - **cmd:** بيوسّع `%`، ويشيل `^`، ويقسّم السطر عند `& | < >`.
   - **Git Bash:** بيشيل علامات التنصيص، ويحوّل أي معامل شكله مسار لينكس.
2. **الشيل بيسلّم السطر كله نص واحد لـ `CreateProcessW`.**
3. **البرنامج نفسه بيفك النص بقواعد الـ C runtime:** `\"` يعني علامة تنصيص، و`2n` من `\` قبل `"` بتبقى `n`. cmd **مابيستخدمش** `CommandLineToArgvW`، فكل برنامج بيفك السطر بنفسه.

**أي فشل سببه ويندوز هو خلاف بين المرحلة 1 والمرحلة 3.** الطريقة الوحيدة اللي نجحت في الـ 26 حالة كلها: `subprocess.run([...list...])` في بايثون، أو `Invoke-NativeExact` في PowerShell.

## أنهي أداة أستخدم

| الشغل | الأداة |
|---|---|
| أوامر عادية، وffmpeg، وgit، وبايثون، وسلاسل أوامر | **Bash tool**: فشله 5.9% مقابل 16.9% لـ PowerShell |
| حاجات ويندوز نفسها: الريجستري، وCOM، و`Get-CimInstance`، والاختصارات، وwinget، وrobocopy | PowerShell tool |
| كود أطول من سطرين، أو فيه علامات تنصيص، أو عربي | **ملف `.py` بأداة Write** وبعدين `python -X utf8 file.py` |
| محتوى ملف | **أداة Write**، مش heredoc ولا `echo >` |
| cmd.exe | بس لو مفيش غيره، وفي PowerShell الأحسن `cmd /c '...'` لأن cmd بيعيد التحليل بنفسه |

## قبل التنفيذ: الفاحص

```
python -X utf8 "%USERPROFILE%\.claude\skills\windows-commands\scripts\wincmd_lint.py" --shell powershell|bash|cmd "COMMAND"
python -X utf8 ...\wincmd_lint.py --shell bash --file cmd.txt      # للأوامر الطويلة
```

شغّله لو الأمر فيه واحدة من دول:
- كود بعد `-c` أو `-e`.
- علامات تنصيص جوه علامات تنصيص.
- عربي.
- `''`.
- مسار آخره `\`.
- أداة ويندوز بـ `/switch` من Bash.
- heredoc.
- `Select-Object -First`.
- `Get-Content` أو `Out-File`.
- طول أكتر من 5000 حرف.

مستويات الفاحص:
- **error:** ويندوز هيفهمه غلط، وده اتقاس على الجهاز.
- **warn:** غالبًا مشكلة.
- **info:** اعرفها قبل ما تحكم على النتيجة.

## القواعد، مترتبة حسب عدد الأوامر الحقيقية اللي فشلت بسببها

### 1. اقرا exit code صح (94 فشل)
- `برنامج | Select-Object -First N` بيرجّع `$LASTEXITCODE=-1`، والأداة بتعرضه 255، رغم إن الخرج سليم. **استخدم** `-Last` أو `Out-String`، أو وجّه الخرج لملف.
- `-ErrorAction SilentlyContinue` و`2>$null` و`Out-Null` بيخفوا الرسالة، لكن الأداة برضه بتطلّع exit 1. **الحل:** `try { ... -ErrorAction Stop } catch {}`.
- **robocopy:** من 0 لـ 7 نجاح، و1 معناها اتنسخ. **الفشل من 8 وفوق بس.**
- **Bash:** الـ exit code بيبقى بتاع **آخر** أمر، فـ `grep` اللي مالقاش حاجة بيخلّي السلسلة كلها 1.
- `2>&1` على برنامج خارجي في PS 5.1 بيحوّل الـ stderr لـ ErrorRecord. **ماتوجّهوش**، والأداة أصلًا بتلم الـ stderr.
- **احكم من الخرج نفسه** قبل ما تقول «فشل».

### 2. الترميز والعربي (89 فشل)
- **بايثون:** دايمًا `python -X utf8`. الـ `-I` بيتجاهل `PYTHONUTF8` اللي متظبط على الجهاز، فبيقع بـ cp1252.
- **`Get-Content`:** دايمًا معاه `-Encoding UTF8`. من غيره بيقرا UTF-8 اللي من غير BOM بترميز 1252، فالكلمة اللي 5 حروف بتطلع 10 حروف بايظة.
- **في PS 5.1:** `>` و`Out-File` بيكتبوا **UTF-16LE**، و`Set-Content` بيكتب ANSI فالعربي بيبقى `?`. **استخدم** `-Encoding UTF8`، أو `[IO.File]::WriteAllText(p, t)` عشان UTF-8 من غير BOM، ودي اللي ffmpeg وjq بيحبوها.
- **سكربت `.ps1` فيه عربي لازم يتحفظ UTF-8 بـ BOM**، وإلا PS 5.1 بيقراه 1252. القاعدة PS022 في الفاحص بتفتح الملف وتتأكد.
- **أول سطر في أي سكربت `.ps1` بيتعامل مع برامج خارجية**، لأن نتيجة القراية بتتحدد من صفحة الترميز اللي العملية ورثتها: 437 بتبوّظ، و65001 بتصح، واتقاس الاتنين:
  ```powershell
  $OutputEncoding = [Console]::InputEncoding = [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding $false
  ```

### 3. طول الأمر في أداة Bash (39 فشل، و35 من 35 فوق الحد)
- **MSYS2 bash بيقص سكربت `-c` عند 8,186 حرف.** أداة Bash بتلف الأمر في `eval '...'`، فكل `'` بتبقى 4 حروف. **الحد العملي حوالي 7,500 حرف «فعلي».**
- **فوق الحد:**
  - لو فيه علامة تنصيص مفتوحة، بيطلع `unexpected EOF while looking for matching`.
  - **ولو مفيش، الباقي بيتقص من غير أي خطأ.** heredoc طوله 12,000 حرف كتب 8,167 بايت بس، ورجّع exit 0.
- **أي محتوى ملف أو سكربت كبير يتكتب بأداة Write.**

### 4. الأداة موجودة في الشيل ده؟ (32 فشل)
- **`rg` في Bash دالة** بيضيفها Claude Code، ومش موجودة في PowerShell ولا بايثون. **استخدم أداة Grep.**
- **PowerShell مابيشغّلش برنامج من المجلد الحالي** غير لو كتبت `.\x.exe`. **cmd بيدوّر في المجلد الحالي قبل PATH** (`NeedCurrentDirectoryForExePathW`، اتأكد بـ Ghidra).
- **لو مش متأكد:** `Get-Command x` في PowerShell، أو `command -v x` في Bash، أو اكتب المسار الكامل.
- **الـ aliases في PowerShell بتاخد أسماء برامج:**
  - `curl` و`wget` معناهم Invoke-WebRequest، **استخدم** `curl.exe`.
  - `where` معناها Where-Object، **استخدم** `where.exe`.
  - `sc` معناها Set-Content.
  - `ls -la` و`rm -rf` و`mkdir -p` مش شغالين.

### 5. المسارات بين Bash وويندوز (13 فشل، و6 تانيين اتشافوا وقت التحليل)
- **Git Bash بيحوّل أي معامل شكله مسار:** `/c` بيبقى `C:/`، و`/tmp/x` بيبقى `%TEMP%\x`، و`--out=/tmp/y` بيتحوّل هو كمان. يعني `cmd /c` بيفتح cmd تفاعلي، و`taskkill /F` بيبوظ.
  - **الحل:** `MSYS_NO_PATHCONV=1 cmd /c ...`، أو `//c`، أو شغّل الأمر من أداة PowerShell.
- **التحويل بيحصل على المعاملات بس، مش جوه الكود.** `python -c "open('/c/Users/..')"` بيفشل، **فاستخدم** `C:/Users/...` جوه الكود.
- **`C:\Users\x` من غير علامات تنصيص في Bash بيبقى `C:Usersx`.** حط علامات تنصيص أو استخدم `/`.
- **`printf` و`echo -e` بيفهموا الـ `\U` و`\r` و`\a` اللي جوه المسارات على إنها رموز.** الحالة دي حصلت فعلًا وقت التحليل.
- **جوه كود بايثون، `"C:\Users"` بيعمل SyntaxError**، لأن `\U` بيتفهم escape. **استخدم** `r"..."` أو `/`.

### 6. علامات التنصيص للبرامج الخارجية من PowerShell 5.1 (24 فشل، والسبب اتأكد من الكود)
الكود اللي ILSpy فكّه من `NativeCommandParameterBinder` بيعمل الحاجات دي:

| اللي كتبته | البرنامج استلم | ليه | الحل اللي اتجرّب |
|---|---|---|---|
| `'print("ok")'` | `print(ok)` | `"` بتعدّي زي ما هي والـ CRT بيشيلها | `'print(\"ok\")'` أو `"print('ok')"` |
| `''` | (اختفى) | `IsNullOrEmpty`، فبيعمل `continue` | `'""'` |
| `'C:\dir with space\'` | بيلزق في المعامل اللي بعده | `\"` في الآخر | `'C:\dir with space\\'` |
| `'--%'` أو `$a='--%'` | (اختفى) | الشرط بيبص على **القيمة** نفسها، `Equals("--%")` | `Invoke-NativeExact` بس |
| `"...\"..."` جوه `"..."` | النص بيتقفل | `\` مش escape في PowerShell | `` `" `` أو `""`، أو `'...\"...'` |
| `& $dir\tool.ps1` | `$dir` لوحده | من غير علامات تنصيص | `& "$dir\tool.ps1"` |
| `a && b` | ParserError | 5.1 مفيهوش `&&` | `a; if ($?) { b }` |
| “ ” ‘ ’ | ParserError | PowerShell بيعتبرها علامات تنصيص | علامات تنصيص عادية |

**الحل المضمون:**
```powershell
. "$env:USERPROFILE\.claude\skills\windows-commands\scripts\NativeExact.ps1"
$r = Invoke-NativeExact python @('-c', 'print("ok")', '', 'C:\dir with space\', '--%', 'مرحبا')
$r.ExitCode; $r.StdOut; $r.StdErr; $r.CommandLine
```
بتطبّق نفس خوارزمية `list2cmdline` بتاعة بايثون، ونجحت في 27 من 27 حالة، وبتقرا الخرج UTF-8.

**في cmd وملفات batch:**
- `%` لوحدها بتتمسح، و`%NAME%` بتتوسّع، واكتب `%%` لو عايزها حرفيًا.
- `^&` بره علامات التنصيص.
- `\"` جوه علامات التنصيص للبرامج اللي بتستخدم الـ CRT.
- حد السطر 8191 حرف، وده الشرط `0x1fff` جوه cmd.exe.

## لما أمر يفشل بشكل غريب

1. افصل: البرنامج **فهم** الأمر وفشل، ولا الشيل **غيّر** الأمر؟ الإجابة في الخرج: لو فيه رسالة من البرنامج نفسه يبقى البرنامج فهم.
2. شغّل الفاحص على نفس الأمر.
3. لو لسه مش واضح، اعرف البرنامج استلم إيه بالظبط بـ `scripts/selftest/argv_probe.py`، بإنك تحطه مكان البرنامج.
4. 23% من الفشل الحقيقي **أخطاء برامج فعلية مالهاش علاقة بويندوز**، فماتلومش الشيل على طول.

## الأدوات

| الملف | بيعمل إيه |
|---|---|
| `scripts/wincmd_lint.py` | فاحص الأوامر: 41 قاعدة، كل واحدة ليها دليل |
| `scripts/NativeExact.ps1` | `Invoke-NativeExact` و`ConvertTo-NativeCommandLineArg` لـ PS 5.1 |
| `scripts/selftest.py` | يعيد القياس بعد أي تحديث لويندوز أو PowerShell أو Git (`--quick` حوالي 10 ثواني، والكامل حوالي 70 ثانية) |
| `scripts/wincmd.yar` | YARA: سكربت ps1 فيه عربي ومن غير BOM، وملفات UTF-16 طالعة من `>`، وبصمة PS 5.1 وcmd |
| `scripts/selftest/*` | أدوات التجارب: `argv_probe`، والمصفوفات، والترميز، وحد MSYS2 |

## المراجع

| الملف | فيه إيه |
|---|---|
| `references/evidence.md` | كل أداة اتشغّلت وطلّعت إيه، والفرضيات، والأسئلة المفتوحة |
| `references/matrix.md` | 26 معامل × 5 طرق |
| `references/fixes.md` | الحلول، وكل واحد اتجرّب |
| `references/encoding.md` | الترميز بالبايت |
| `references/corpus.md` | الـ 4,246 أمر الحقيقي |
| `references/lint_eval.md` | تقييم الفاحص |

لو اتثبّت pwsh 7 أو اتحدّث Git، شغّل `selftest.py` وحدّث الأرقام.

## تكامل التنين الأسود v1990.2

للفحص فقط (لا تنفيذ للأمر المفحوص): `python3 scripts/dragon.py tool windows-lint --shell powershell "python -I -c ..."`، أو `--shell bash|cmd`، أو `--file PATH`.
`NativeExact.ps1` مرفق كاختيار مستقل على Windows PowerShell 5.1، ولن يُستدعى تلقائيًا. أرقام دقة الفحص والتجارب المذكورة في المهارة هي من صاحب الحزمة، ولم تُعاد معايرتها على جهاز ويندوز في هذا الدمج.
