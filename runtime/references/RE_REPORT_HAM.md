# تحليل مجلد «هام» بأدوات الهندسة العكسية — 2026-11-12

**النتيجة:** مجلد «هام» شغل صاحب التنين نفسه، ومفيهوش حاجة مريبة. فيه 5 نسخ من التنانين (حزم مهارات)، وعيّنتين exe متطابقين بالبايت مع ملفات ويندوز الأصلية وعليهم توقيع مايكروسوفت صالح. مفيش أسرار حقيقية، ومفيش كود بينزّل حاجة ويشغّلها لوحده. اتشغّلت الـ 34 أداة اللي صاحب الشغل علّم عليها، وكل أداة ليها قسم تحت. الأداة اللي مالقتش هدف يناسبها مكتوب جنبها السبب في سطر.

## اللي في المجلد (اتقاس)
- 7,848 ملف، 768 MB. فيهم 2,487 ملف `.py`، و1,811 `.md`، و1,279 `.json`، و814 `.js`، و124 `.pyc`، و9 `.yar`، و5 `.onnx`، و5 `.sqlite`.
- `black-dragon-v10.17.0.zip` و`v1990.4-all-powers.zip` و`v1990.9.0.zip`، ومعاهم `output\black-dragon-v1990.10.0.zip` (النسخة اللي اتدمج فيها التلاتة، والفك والسجل في `output\_src` و`output\_work`)، و`white-dragon-v1.0.0.zip` و`white-dragon\` (اللي فيه `data\powers.json` بس).
- `white-dragon-workspace\re\samples\`: `notepad.exe` (PE native) و`InstallUtil.exe` (‎.NET). دول الملفين التنفيذيين الوحيدين في المجلد. مفيش APK ولا pcap ولا wasm ولا ماكرو Office ولا PyInstaller.
- omni: المجلد نفسه `folder`، والـ zip `archive` بإنتروبي 8.0، وده طبيعي لأي ملف مضغوط.

## الفرضيات وحكمها
| | الفرضية | الحكم | الدليل (أداتين مستقلتين على الأقل) |
|---|---|---|---|
| ف1 | المجلد شغل صاحبه + عيّنات تدريب من ويندوز | ✅ اتأكدت | باقي الفرضيات اتنفت، والمحتوى نسخ تنانين بنفس بنية الشجرة |
| ف2 | فيه مفاتيح أو بيانات شخصية متسرّبة هتنتقل للتنين الأحمر | ❌ اتنفت | yara + yara-x: 190 تطابق متطابقين 100% وكلهم إنذار غلط، وAWS=0 وGoogle=0 · فحص مستقل بـ ripgrep على `red-dragon` المتثبت: النتيجة الوحيدة نمط المفتاح جوه `dragon_audit.yar`، والإيميلات أمثلة (`ana@`، `x@`، `temp@`)، والرقم اللي شكله تليفون سعودي طلع جزء من معامل تحويل ألوان OKLab (`0.0514459929`، في 7 ملفات ألوان) |
| ف3 | العيّنتين متعدّل فيهم | ❌ اتنفت | `Get-FileHash` (PowerShell): SHA-256 مطابق لـ `C:\Windows\System32\notepad.exe` و`C:\Windows\Microsoft.NET\Framework64\v4.0.30319\InstallUtil.exe` · `rz-diff` distance 0 · `Get-AuthenticodeSignature` Valid، والموقّع «Microsoft Windows» · LIEF `verify_signature()=OK` |
| ف4 | كود بينزّل حاجة ويشغّلها من غير موافقة | ❌ اتنفت (~95%) | ripgrep على `curl\|sh` و`iwr\|iex`: كل اللي طلع قواعد كشف أو تحذيرات أو اختبارات أو نصوص تثبيت في JSON · `engine\app\engines\dragon_montage\doctor.py` بيقول «never installs»، و`subprocess` الوحيد فيه بيشغّل `npm root -g` و`fc-list` (قراية بس) |

## علاقة الحزم ببعض
`references/PACKAGES_ANALYSIS.md` (اتعمل في الجلسة اللي بنت v2.0.0، بـ CRC ملف بملف): `v10.17.0` و`v1990.9.0` و`v1990.4` كلهم جوه `v1990.10.0` بالكامل. و`white-dragon` = لقطة أقدم شوية من نفس المحرك + عقل `wd.py`.

## دروس الأدوات (دخلت في الدروس)
- المسار اللي فيه عربي بيوقّع `upx` (FileNotFoundException) و`LIEF` (Failed to open): اشتغل بالاسم النسبي من جوه الفولدر، أو ادّي البايتات (`io.BytesIO`).
- `rea list-strings` مش أمر CLI في REA 6.8، موجود كأداة MCP بس: استخدم `string_count` من `rea analyze` + FLOSS.
- `capa -r` على فولدر فرعي من القواعد بيقع (exit 12، missing rule dependency): ادّيله فولدر القواعد كله.
- إنذار «analysis tools strings» في capa على notepad طلع غلط: regex لقط `<IDAT` جوه صورة PNG في الموارد.
- وقت كتابة التقرير ده: heredoc في Bash حوّل `\\` لشرطة واحدة فبقت `\b` و`\v` حروف تحكّم جوه المسارات. اتكتب من جديد بأداة الكتابة (الدرس s03 اتكرر).

---

# تفاصيل كل أداة (التقرير الكامل للوكيل، اتراجع)


> كل الشغل اتعمل على **نسخ** في `C:\Users\cinde\OneDrive\Desktop\هام\output\_red_work\re\samples\`.
> ولا ملف من الملفات المحلَّلة اتشغّل. والنصوص والكود اللي طلعت من الملفات اتعاملت كبيانات بس، ومحدش نفّذ أي حاجة مكتوبة جواها.
> المخرجات الخام كلها في `_red_work\re\raw\`، والسكربتات في `_red_work\re\scripts\`.

**اختصارات بنستخدمها في الأوامر تحت:**
- `RT` = `python -I -X utf8 "C:\Users\cinde\re-tools\retool.py"`
- `RE` = `C:\Users\cinde\OneDrive\Desktop\هام\output\_red_work\re`
- أوامر اتشغّلت من جوه `RE\samples` بأسماء ملفات نسبية (upx وrizin وrz-bin وrz-diff وfloss وilspy وpydisasm وwebcrack)، عشان شوية أدوات (أولها UPX) مابتعرفش تفتح مسار فيه حروف عربي (`هام`).

## 0) التجهيز والتعرّف الأولي (قبل الأدوات)

| الملف (النسخة) | الحجم | SHA-256 |
|---|---|---|
| `samples\notepad.exe` | 360,448 | `2d0b3948c1edc5c6a1d1f3e3658613252cfbbfa1b98b46cb7cc8e5bf2efb158f` |
| `samples\InstallUtil.exe` | 35,184 | `94d8e3ceeabba9b9c55e2219181c5c138050825b63d78b0d82988ed1c13a4118` |
| `samples\re.cpython-312.pyc` | 39,657 | `9d0ef0c1923c07a6cab4088aa18ee6ffd2b265fb9a155f3cafa5db0400f7d174` |
| `samples\re.py` (المصدر، للمقارنة) | 25,952 | `229e20cf28f48ddfc48a167c066feea27959a71f4341899b9023c33a8ce8a70c` |
| `samples\js\three.min.js` | 749,765 | `d59478ac9949ea8a70ee49493b833381569fa1ab2770ccceffcfd77bf3afc864` |
| `samples\js\mo.umd.js` | 120,660 | `7ed8e439c075b79de974b9ea60f4988edbf4425cfefa93ff7be26302af5b64f7` |

- الأمر: `sha256sum samples/* /c/Windows/System32/notepad.exe /c/Windows/Microsoft.NET/Framework64/v4.0.30319/InstallUtil.exe`
  - **النتيجة المهمة:** `notepad.exe` **نفس بصمة** `C:\Windows\System32\notepad.exe` بالظبط، و`InstallUtil.exe` **نفس بصمة** `C:\Windows\Microsoft.NET\Framework64\v4.0.30319\InstallUtil.exe` بالظبط. يعني العينتين نسخ طبق الأصل من ملفات ويندوز اللي على الجهاز.
- `python -X utf8 "C:\Users\cinde\.claude\skills\omni-analyst\scripts\omni.py" classify <file>` لكل exe ← `family=binary, kind=pe`.
- `... omni.py probe <file>` ← `raw\omni_probe_*.txt`: notepad إنتروبي 6.48 «عادي» ومفيش علامات باكر، و`dotnet=false` و`signed_blob=false` و315 import. InstallUtil إنتروبي 6.0 «عادي»، و`dotnet=true` و`signed_blob=true` و0 import.
- `RT triage <file> --deep --out RE\raw\triage_<name>` ← `raw\triage_notepad\notepad.triage.md` و`raw\triage_InstallUtil\InstallUtil.triage.md` (فيها die وPE وcapa وFLOSS مع بعض).

---

## die

**الأمر:** `RT run die "RE\samples\notepad.exe"` و`RT run die -e ...` (إنتروبي) و`RT run die -j ...` (JSON ← `raw\die_*.json`)، ونفس الكلام لـ InstallUtil.

**النتيجة:**
- notepad: `PE64`، Linker `Microsoft Linker 14.38.33145`، Compiler `MSVC 19.38.33145 [LTCG/C]`، `Visual Studio 2022 17.8`، Debug: `CodeView, Ext-DLL Characteristics, POGO, REPRO`. الإنتروبي الكلي `6.48 not packed`. القسم `.rsrc` إنتروبيه 6.97 وdie كتب جنبه «packed».
- InstallUtil: `PE64`، `.NET Framework (CLR 4.0.30319)`، `Sign tool: Windows Authenticode (2.0) [PKCS #7]`، Debug: CodeView. فيه Overlay من offset 25088 حجمه 10096 بايت وإنتروبيه 7.51.

**يعني إيه:** notepad برنامج C/C++ عادي متبني بـ Visual Studio ومش مضغوط. كلمة «packed» على `.rsrc` إنذار غلط: القسم ده فيه 22 أيقونة (REA عدّهم، شوف قسم rea)، ومنها صور PNG مضغوطة أصلًا، وده باين من chunk `IDAT` اللي capa لقاه جوه `.rsrc`. وكلمة `REPRO` معناها إن تاريخ البناء في الهيدر (2018-09-16) مش تاريخ حقيقي، ده «هاش» بتاع build قابل للتكرار. InstallUtil برنامج ‎.NET 4، والـ Overlay اللي في آخره هو التوقيع الرقمي نفسه (offset وحجم التوقيع اللي طلّعهم REA وpefile مطابقين بالظبط)، فمش حاجة مستخبية.

## capa

**الأمر:** `RT run capa -r "C:\Users\cinde\re-tools\capa-rules\rules-v10.0.0" "RE\samples\<file>"` ← `raw\capa_notepad.txt` و`raw\capa_InstallUtil.txt` (capa 10.0.0). وكمان `-vv` على notepad ← `raw\capa_notepad_vv.txt` عشان نعرف كل قاعدة اتطابقت فين.

**النتيجة:**
- notepad: 31 قدرة. أهمها: clipboard، وقراءة/كتابة/مسح ملفات، وقراءة وكتابة ومسح Registry، و`create process` (مرتين)، وmutex، و`get keyboard layout`، و`identify system language`، و`get geographical location` (3 مرات)، و`link function at runtime` (16 مرة)، و`parse PE header`/`enumerate PE sections`، و`encode data using XOR` (10 مرات)، و`execute anti-debugging instructions`، و`reference analysis tools strings`. ATT&CK: T1115 وT1564.003 وT1112 وT1027 وT1083 وT1057 وT1012 وT1082 وT1614 وT1059 وT1129.
- InstallUtil: 4 قدرات بس: `contains PDB path`، و`access .NET resource` (مرتين)، و`manipulate console buffer`، و`compiled to the .NET platform`.

**الأدلة من `-vv` على الحاجات اللي شكلها مريب (`raw\capa_notepad_vv.txt`):**
- `reference analysis tools strings`: اتطابق على regex `/\bida?(\.exe)?$/i` بنص `"<IDAT"` عند `file+0x4BC4F`. الـ offset ده جوه `.rsrc` (0x38000 لـ 0x57000)، و`IDAT` ده اسم chunk بيانات جوه صورة PNG بتاعة أيقونة. **إنذار غلط أكيد**، ومالوش علاقة ببرنامج IDA.
- `execute anti-debugging instructions`: السبب إن فيه تعليمتين `rdtsc` أو أكتر جوه `0x140013150` (عند `0x1400149B9` و`0x1400150C8` و`0x14001BDE9` و`0x14001C1ED`). ومفيش أي فحص للديباجر بعدهم ظهر في الدليل. (`IsDebuggerPresent` موجودة في الـ imports، بس capa ماربطهاش بالقاعدة دي.)
- `encode data using XOR` (10 مرات): لوب ضيق فيه `xor` كتير عند `0x140013DA4` جوه نفس الدالة `0x140013150`.
- `parse PE header`: في `0x1400022B4`، ودي الدالة اللي الـ CRT main بيناديها على `0x140001947` (تحقق الـ CRT القياسي).
- `create process`: `ShellExecute @ 0x14001FDB0` و`CreateProcess @ 0x140023CD2`. الدالة `fcn.140023c00` بتبني سطر أوامر `"<path>" …` قبل `CreateProcessW` (rizin `pd`).
- `get geographical location`: نداءات `GetLocaleInfo` (لغة وإعدادات المنطقة).
- `hide graphical window`: `ShowWindow(…, SW_HIDE)` في `0x14001FA28`.

**يعني إيه:** أغلب قدرات notepad طبيعية لمحرر نصوص: حفظ وفتح، وطباعة، وclipboard، وإعداداته في Registry، وفتح لينك بـ `ShellExecuteW`، ولغة النظام. الحاجات اللي شكلها «مريب» يا إما إنذار غلط بالدليل (IDAT) يا إما كود قياسي (فحص الـ PE في الـ CRT، و`rdtsc`/XOR في دالة التجهيز). والملف كمان مطابق بالبايت لنسخة System32 (rz-diff). capa بيوصف الكود الموجود، مش بيقول إنه بيتنفّذ. InstallUtil تقريبًا مفيهوش منطق خاص بيه، والسبب في قسم ilspy.

## floss

**الأمر:** `RT run floss -j -q notepad.exe > RE\raw\floss_notepad.json` (FLOSS v3.2.0، خد حوالي 3 دقايق)، و`RT run floss -q InstallUtil.exe > RE\raw\floss_InstallUtil.txt`.

**النتيجة:**
- notepad: `static_strings=3665`، `stack_strings=1` (القيمة `Lucida C`، أول حروف اسم الخط Lucida Console)، `decoded_strings=0`، `tight_strings=0`. حلّل 23 دالة مرشحة للفك و369 دالة للـ stack strings.
- InstallUtil: FLOSS كتب `WARNING: .NET language-specific string extraction is not supported yet` و`FLOSS does NOT attempt to deobfuscate any strings from .NET binaries`، وطلّع النصوص الثابتة بس (أسماء الـ metadata زي `InstallUtilSignOnMessage` و`GetConsoleFallbackUICulture`).

**يعني إيه:** notepad مفيهوش نصوص متشفرة أو مستخبية. الـ stack string الوحيد اسم خط. أما InstallUtil فـ FLOSS مش الأداة الصح ليه (‎.NET)، وبدلها اتغطّى بـ ilspy وREA `inspect-managed-members` وdnfile.

## yara

**ملفات القواعد:** لقيت 9 ملفات `.yar` تحت `هام` (الأمر: `find . -iname "*.yar"`). بالبصمة طلعوا ملفين مختلفين بس:
- `wincmd.yar` (sha256 `4c78a342…`) ×4 نسخ: `output\black-dragon\skills\windows-commands\scripts\` و`output\_src\black-dragon-v1990.4-all-powers\…` و`output\_src\black-dragon-v1990.9.0\…` و`output\_work\pristine\skills\windows-commands\scripts\`. فيه 4 قواعد: `ps1_utf8_without_bom_non_ascii` و`text_utf16le_from_ps51_redirect` و`ps51_legacy_native_arg_binder` و`cmd_default_pathext_and_cwd_search`.
- `dragon_audit.yar` (sha256 `5d8e1a39…`) ×5 نسخ: `output\black-dragon\tools\re\rules\` و`output\_src\black-dragon-v10.17.0\…` و`…v1990.4-all-powers\…` و`…v1990.9.0\…` و`output\_work\pristine\tools\re\rules\`. فيه 7 قواعد: `bd_secret_api_key` و`bd_private_key` و`bd_obfuscated_exec` و`bd_remote_pipe_shell` و`bd_credential_read` و`bd_destructive_ops` و`bd_shell_true`.

**(أ) الـ 9 ملفات على الـ exe الاتنين:**
`for y in <9 files>; do for f in notepad.exe InstallUtil.exe; do RT run yara -s -w "<y>" "RE\samples\<f>"; done; done` ← `raw\yara_exes.txt`
- **النتيجة: 0 تطابق** في الـ 18 تشغيلة، وكلها خرجت بـ exit=0.
- **ضبط إيجابي (عشان نتأكد إن الماسح شغال فعلًا):** `RT run yara RE\scripts\control.yar <file>` طلّع `ctl_is_pe` و`ctl_notepad_pdb` على notepad، و`ctl_is_pe` و`ctl_installutil_pdb` على InstallUtil. يعني الصفر فوق نتيجة حقيقية، مش عطل.
- **يعني إيه:** متوقع. قواعد `wincmd` معمولة لـ `cmd.exe` و`System.Management.Automation` وسكربتات ps1، وقواعد `dragon_audit` معمولة لحزم سكربتات (مفاتيح وcurl|sh وshell=True)، ومفيش أي واحدة منهم تخص notepad أو InstallUtil.

**(ب) قاعدة الأسرار الجديدة:** `RE\scripts\secrets.yar`، فيها 7 قواعد: `sec_aws_access_key` و`sec_github_token` و`sec_openai_anthropic_key` و`sec_google_api_key` و`sec_private_key_block` و`sec_slack_token` و`sec_generic_assignment`، بالأنماط اللي اتطلبت بالظبط.
- الأمر (عن طريق السكربت اللي بيشغّل المحرّكين ويخفي القيم): `python -I -X utf8 RE\scripts\secrets_scan.py RE\scripts\secrets.yar RE\raw\secrets "…\هام\output\black-dragon" "…\هام\white-dragon"`. وجواه بيتنفّذ `RT run yara -s -r -w secrets.yar <dir>`.
- المخرجات (القيم متخفية): `raw\secrets.hits.tsv` و`raw\secrets.summary.txt`.

| القاعدة | عدد التطابقات (yara) | ملفات | الحكم |
|---|---|---|---|
| sec_aws_access_key | 0 | 0 | — |
| sec_google_api_key | 0 | 0 | — |
| sec_openai_anthropic_key | 177 | 16 | كلها إنذار غلط |
| sec_generic_assignment | 4 | 3 | كلها إنذار غلط |
| sec_github_token | 3 | 2 | كلها إنذار غلط |
| sec_slack_token | 3 | 3 | كلها إنذار غلط |
| sec_private_key_block | 3 | 1 | كلها إنذار غلط |
| **المجموع** | **190** | **25 (قاعدة×ملف)** | **0 مفتاح حقيقي** |

`white-dragon` (فيه ملف واحد بس) طلع **0 تطابق**.

**الملفات اللي فيها تطابق وسببه (القيم متخفية: أول 4 حروف + ****):**
- `output\black-dragon\app\data\catalog.sqlite` (112 + slack 1): كلمات فيها شرطة زي `ri`+`sk-m****` (من risk-management) و`ta`+`sk-c****` (من task-…). دي أسماء مهارات، مش مفاتيح. والـ slack `xoxb****` جاي من نص توثيق «a bot (`xoxb-`)».
- `output\black-dragon\skills\github-atlas\data\raw\p10.json` (44) و`…\data\atlas.jsonl` (2) و`…\data\top1000.csv` (2) و`…\data\raw\downloads.json` (1) و`output\black-dragon\tools\github_atlas\atlas.jsonl` (2): كلها `sk-Q****` جاية من اسم المستودع `How-To-A`+`sk-Q…` (Ask-Questions…). اسم ريبو، مش مفتاح.
- `output\black-dragon\app\apps\dragon_desktop\app.py` (2) و`…\ui\index.html` (1): البادئة لوحدها `sk-a****` (= `sk-ant-`) في كود فحص صيغة المفتاح وفي placeholder بتاع خانة password.
- `output\black-dragon\app\engines\cards\lib\security_safety.py` (openai 2، github 2، slack 1) و`output\black-dragon\tools\stock\_secrets.py` (openai 1، github 1): أنماط regex لكشف الأسرار وبادئات لوحدها (`gith****` و`xoxb****`).
- `output\black-dragon\app\data\cards\agent-orchestration.json` (1) و`prompt-craft.json` (2): شكلها `sk-` + 20 حرف كابيتال. اتأكدت إنها الأبجدية بالترتيب (`ABCDEFGHIJ…`) أو نفس الحرف متكرر، يعني fixtures بتاعة اختبار حجب المفاتيح.
- `output\black-dragon\app\data\cards\atlas-mind.json` (generic 2): `secret=sk-l****` شكلها `aa-aaaa-9a9a9a` (مفتاح وهمي «live» جوه كود اختبار curl)، و`token=CONF****` (كلمة تأكيد merge، مش سر).
- `output\black-dragon\app\data\cards\security-safety.json` و`skills.json` (generic 1 لكل واحد): `API_****` اسم متغير/نمط جوه كود.
- `output\black-dragon\app\data\cards\protocols.json` و`references\prompts\USIP_PORTABLE_v5_6.md` و`app\engines\dragon_montage\data\mind_registry.json` و`app\tests\test_v1014_re_brain.py`: `A25-ta`+`sk-…` و`counterparty-a`+`sk-…` وأسماء `task-…` في اختبارات. كلمات، مش مفاتيح.
- `output\black-dragon\tools\re\rules\dragon_audit.yar` (private key 3): نصوص القاعدة نفسها `-----BEGIN … PRIVATE KEY-----`.

**يعني إيه:** مفيش ولا مفتاح حقيقي في الفولدرين. نمط `sk-[A-Za-z0-9_-]{20,}` من غير حد كلمة قبله بيلقط أي كلمة إنجليزي آخرها `…sk-` (task وrisk وask). لو حبيت تقلّل الإزعاج ده، ضيف قبله `(?<![A-Za-z0-9])` (بايثون) أو `\b` (yara).

## yara-x

**الأمر (أ):** `RT run yara-x scan -s -w "<y>" "RE\samples\notepad.exe"` ونفس الكلام لـ InstallUtil، على الـ 9 ملفات ← `raw\yarax_exes.txt` (yara-x-cli 1.23.0). وقبلها `RT run yara-x check RE\scripts\secrets.yar` ← `[ PASS ]`.
- النتيجة: **0 تطابق** (نفس yara بالظبط). والضبط الإيجابي `control.yar` طلّع نفس التطابقات الأربعة.

**الأمر (ب):** جوه `secrets_scan.py`: `RT run yara-x scan -s -r -w -o ndjson secrets.yar <dir>` على `output\black-dragon` و`white-dragon`.
- النتيجة: نفس الأرقام بالظبط: 177/4/3/3/3 = **190 تطابق في 25 (قاعدة×ملف)**، و0 لـ AWS وGoogle، و0 في white-dragon.
- **مقارنة المحرّكين على مستوى (قاعدة، ملف، offset):** `both=190 yara_only=0 yarax_only=0`.

**يعني إيه:** المحرّكين متفقين 100%، فالنتيجة مش خطأ في محرّك واحد. وقاعدة `secrets.yar` نفسها شغالة على الاتنين من غير تحذيرات.

## upx

**الأمر:** (من جوه `RE\samples`) `RT run upx -t notepad.exe` و`RT run upx -l notepad.exe`، ونفس الكلام لـ InstallUtil.exe (UPX 5.3.0).

**النتيجة:**
- الأربع تشغيلات: `NotPackedException: not packed by UPX` (exit=2).
- ملحوظة: أول محاولة بالمسار الكامل فشلت بـ `FileNotFoundException`، لأن UPX مش بيفهم الحروف العربي في المسار (`???`). اتحلّت لما اشتغلنا بالاسم النسبي.
- دليل تاني مستقل: `grep -c -a "UPX!"` و`grep -c -a "UPX0"` ← 0 في الملفين. وأسماء الأقسام (rz-bin -S) مفيهاش UPX0/UPX1.

**يعني إيه:** الملفين مش مضغوطين بـ UPX، وده متفق مع die («not packed») ومع الإنتروبي العادي.

## pe-sieve

**ماتشغّلش، لأن القاعدة إن ممنوع تشغيل الملف المحلَّل، ومحتاج إذن صريح.**
pe-sieve بيفحص **عملية شغالة** (`/pid`)، فكان لازم نشغّل notepad أو InstallUtil الأول.
**كان هيورّينا إيه:** لو اشتغل على PID للعملية، كان هيقارن صورة الملف في الذاكرة بالملف على الديسك ويطلّع أي hooks أو كود محقون أو أقسام متبدلة أو PE مخفي (ويعمل dump في `/dir`). وبما إن الملفين مطابقين لملفات ويندوز وموقّعين، المتوقع إنه يطلع «0 modified / 0 implanted».
الأمر لو جه إذن: `RT run pe-sieve /pid <PID> /dir RE\raw\pesieve`.

## ilspy

**الأمر:** (من جوه `RE\samples`) `RT run ilspy -p -o "RE\ilspy_out" InstallUtil.exe` (ilspycmd 11.2.0.10050، خلص في ثانية) ← `RE\ilspy_out\` (13 ملف، 348 سطر C#).

**النتيجة (من `ilspy_out\System.Configuration\InstallUtil.cs`):** فيه كلاس واحد بس فيه منطق: `System.Configuration.InstallUtil` جواه `Main(string[] args)`، وده اللي بيعمله:
1. يظبط لغة الواجهة على `GetConsoleFallbackUICulture()`. ولو ترميز الكونسول مش UTF-8 ولا OEM ولا ANSI بتوع اللغة دي، يرجع لـ `en-US`.
2. يطبع رسالة البداية `InstallUtilSignOnMessage` بالنسخة `4.8.10001.0` وحقوق النشر.
3. ينادي `ManagedInstallerClass.InstallHelper(args)` من `System.Configuration.Install.dll` ويبعتله الأرجيومنتس زي ما هي.
4. لو حصل Exception يطبع الرسالة ويرجّع `-1`، ولو مفيش يرجّع `0`.

الباقي كلاسات موارد ونصوص (`Res` و`CommonResStrings` و`ResDescriptionAttribute` و`ResCategoryAttribute`). الـ `AssemblyInfo` بيقول `AssemblyFileVersion 4.8.10001.0` و`AssemblyDelaySign(true)` ومفتاح `FinalPublicKey.snk`. والـ `app.manifest` بيقول `requestedExecutionLevel level="asInvoker"`. والـ csproj: `net40`، `PlatformTarget x64`.

**يعني إيه:** InstallUtil.exe «غلاف» رفيع: كل الشغل الحقيقي (تحميل الـ assembly اللي بتديهوله وتشغيل كلاسات `Installer` اللي جواه، Install أو Uninstall) موجود في `System.Configuration.Install.dll`، مش في الملف ده. البرنامج نفسه مفيهوش شبكة ولا P/Invoke ولا ملفات. اتأكدت من ده بـ REA `inspect-managed-native-boundaries` (`pinvoke_import_count=0`) وبـ dnfile (`ImplMap rows=0`)، وتسلسل النداءات في Main طالع نفسه في REA `call_edges` (… `WriteLine` ← `InstallHelper` ← `get_Message` ← `WriteLine`).

## pyinstxtractor

**ماتشغّلش، لأن مفيش ولا ملف PyInstaller في الفولدر.** الدليل: `find "…\هام" -iname "*.exe" -o -iname "*.dll"` لقى ملفين exe بس (العينتين)، و`grep -l -a -P 'MEI\x0c\x0b\x0a\x0b\x0e'` (الكوكي بتاع PyInstaller) رجّع صفر. die كمان مالقاش PyInstaller في أي واحد منهم.

## pydisasm

**الأمر:** (من جوه `RE\samples`) `RT run pydisasm re.cpython-312.pyc > RE\raw\pydisasm_re.txt` (pydisasm 6.3.0، فيه 5976 سطر).

**النتيجة:**
- الهيدر: `CPython 3.12 (magic 3531)`، `Timestamp in code: 1794466341 (2026-11-12 09:52:21)`، `Source code size: 25952 bytes`، `Filename: …\_work\pristine\tools\re\re.py`.
- عدد الـ code objects (`# Method Name:`) = **33**: الموديول، و20 دالة على المستوى الأعلى (`_read` و`pe_info` و`identify` و`step_cmd` و`plan` و`report_skeleton` و`context_of` و`load_ack` و`acked` و`_mask` و`scan_tree` و`yara_x` و`safe_extract` و`audit` و`_capture` و`investigate` و`_short` و`render_report` و`retool` و`main`)، و10 `<genexpr>` و2 `<lambda>`.
- الثوابت فيها الـ docstring («re — Black Dragon reverse-engineering front door (v10.14)…») و`dragon_audit.yar` و`DRAGON_RETOOL` وقايمة الأدوات اللي محتاجة موافقة (`frida` و`pe-sieve` و`x64dbg` و`adb` …).

**مقارنة الـ pyc بالمصدر:** سكربت `RE\scripts\pyc_vs_source.py` بيقرا الهيدر وبيعمل `marshal.loads` للـ pyc، وبيعمل `compile()` للمصدر (ومحدش اتنفّذ في الحالتين)، وبيقارن كل code object بالترتيب.
- الأمر: `python -I -X utf8 RE\scripts\pyc_vs_source.py RE\samples\re.cpython-312.pyc RE\samples\re.py "…\_work\pristine\tools\re\re.py"` ← `raw\pyc_vs_source.txt`
- النتيجة: الـ magic `cb0d0d0a` مطابق لبايثون 3.12 اللي على الجهاز. flags=0، يعني pyc معتمد على timestamp. الـ mtime في الهيدر `1794466341` = الـ mtime الحقيقي لـ re.py ✓. والحجم في الهيدر `25952` = حجم re.py ✓. الـ code objects 33 = 33، و**0 اختلاف** في `co_names` و`co_varnames` و`co_consts` و`co_firstlineno` و`co_code` ← **`VERDICT: pyc MATCHES source (bytecode identical)`**.

**يعني إيه:** الـ pyc ده نسخة مترجمة من `re.py` الحالي بالظبط، مفيش كود زيادة ولا ناقص. وده اتأكد بأداة تالتة مستقلة: REA `inspect-python-pyc` طلّعت 33 code object و`source_mtime=1794466341` و`source_size=25952`.

## rizin

**الأمر:** (من جوه `RE\samples`) `RT run rizin -q -c "aaa;afl~?;iI;ie;afl~entry0;afl~main" notepad.exe` ← `raw\rizin_notepad.txt` (خد حوالي 5 ثواني). وبعدها `RT run rizin -q -e scr.color=0 -c "aaa;pd 140 @ 0x140001840~call" notepad.exe` عشان نلاقي WinMain.

**النتيجة:**
- `afl~?` = **341 دالة** (rizin من غير PDB). `iI`: `PE32+` و`AMD 64` و`Windows GUI` و`canary true` و`nx true` و`pie true` و`dbg_file notepad.pdb` و`compiled Sun Sep 16 2018` (ده تاريخ REPRO الوهمي).
- `ie`: نقطة الدخول `entry0 = 0x1400019c0`.
- جوه `0x140001840` (`__scrt_common_main_seh`): نداء `_o__get_wide_winmain_command_line` على `0x14000192c`، وبعده على طول `call fcn.1400101d8` على `0x140001940`. **يعني wWinMain = `0x1400101d8`.**

**يعني إيه:** الهيكل هو هيكل برنامج MSVC قياسي: entry ← security cookie ← CRT main ← wWinMain. وعدد الدوال (341) أقل من Ghidra (853، شوف قسم ghidra) لأن كل أداة بتكتشف الدوال بطريقة مختلفة. ده مش تناقض.

## rz-bin

**الأمر:** (من جوه `RE\samples`) `RT run rz-bin -I <f>` و`-i` و`-S` على الملفين ← `raw\rzbin_<name>_info.txt` و`_imports.txt` و`_sections.txt`.
(ملحوظة: أول تشغيلة كانت الأسماء فيها `_I`/`_i`، وويندوز مابيفرّقش بين الحروف الكبيرة والصغيرة في أسماء الملفات، فالملف اتكتب فوق بعضه. اتعادت بأسماء مختلفة.)

**النتيجة:**
- notepad: `-i` = **340 import** (أكتر DLLs: `USER32.dll` 87، و`api-ms-win-crt-private` 39، و`GDI32.dll` 25، و`api-ms-win-core-synch` 17، و`api-ms-win-core-file` 13، و`COMCTL32.dll` 11). من الدوال اللي تستاهل نظرة: `CreateProcessW` و`ShellExecuteW` و`IsDebuggerPresent` و`GetProcAddress` و`RegSetValueExW` و`RegDeleteKeyExW`. و`-S`: 8 أقسام (`.text` و`fothk` و`.rdata` و`.data` و`.pdata` و`.didat` و`.rsrc` و`.reloc`)، ومفيش قسم قابل للكتابة والتنفيذ مع بعض. و`-I`: `canary/nx/pie = true`، و`overlay false`.
- InstallUtil: `-i` = **0 import** (جدول فاضي). `-S`: قسمين بس `.text` و`.rsrc`. `-I`: `subsys Windows CUI`، و`compiler Linker 48.00`، و`signed true`، و`compiled Tue Jul 21 00:50:06 2026 UTC+3`.

**يعني إيه:** الـ 340 import في notepad = 315 عادي + 25 delay-load، وده نفس اللي طلع في REA وpefile بالظبط. الـ 0 import في InstallUtil طبيعي لملف ‎.NET بصيغة PE32+ (x64): الويندوز لودر بيشغّل الـ CLR بنفسه، ومش محتاج `mscoree!_CorExeMain`. وده اتأكد من 4 أدوات (omni وrz-bin وREA «IMAGE_DIRECTORY_ENTRY_IMPORT is absent» وpefile)، ونقطة الدخول `AddressOfEntryPoint = 0`.

## rz-diff

**الأمر:**
1. البصمة الأول: `sha256sum samples/notepad.exe /c/Windows/System32/notepad.exe` ← الاتنين `2d0b3948…b158f`، **متطابقين**.
2. (من جوه `RE\samples`) `RT run rz-diff -C -d myers notepad.exe "C:/Windows/System32/notepad.exe"` و`-d leven` و`-t imports` و`-t sections` و`-t entries` و`-t strings` و`-d ssdeep` ← `raw\rzdiff_notepad.txt`.

**النتيجة:**
- `-d myers`: `similarity: 1.000 distance: 0`. و`-d leven`: `similarity: 1.000 distance: 0`.
- `-t imports/sections/entries/strings`: صفر سطر اختلاف (غير سطرين العنوان `---/+++`). سطور `ERROR: Incomplete buffer read` اللي ظهرت على stderr تحذيرات تحميل من rz-diff نفسه، و`rz-bin -i` على نفس الملف ماطلّعهاش.
- `-d ssdeep` **فشل**: `ERROR: diff: the expected hashes are not in ssdeep format` (الوضع ده محتاج تديله قيم ssdeep، مش ملفات).

**يعني إيه:** نسخة notepad اللي في `white-dragon-workspace` هي `notepad.exe` بتاعة ويندوز بالبايت، مفيش أي تعديل.

## ghidra

**الأمر (عن طريق REA، الـ provider = Ghidra 12.1.4، على notepad بس):**
1. `rea analyze "RE\samples\notepad.exe" --provider ghidra --snapshot RE\raw\notepad.rea-snapshot --format md > RE\raw\rea_analyze_notepad.md` (خلص في **5 دقايق و44 ثانية**، exit=0).
2. `rea decompile "RE\samples\notepad.exe" 0x1400019c0 --provider ghidra --snapshot … --format md > RE\raw\rea_decompile_entry_notepad.md` (4 دقايق و55 ثانية).
3. `rea decompile "RE\samples\notepad.exe" 0x1400101d8 --provider ghidra --snapshot … --format md > RE\raw\rea_decompile_winmain_notepad.md` (wWinMain).

**النتيجة:**
- analyze: `procedure_count=853`، و`string_count=638`، و10 segments (`Headers` و`.text` و`fothk` و`.rdata` و`.data` و`.pdata` و`.didat` و`.rsrc` و`.reloc` و`tdb`)، و`image_base 0x140000000`. Ghidra شاف إشارة لـ `notepad.pdb` (GUID `3a948121-747c-b385-e78f-a83b9dae2a69`) بس الـ PDB نفسه مش موجود، فأسماء الدوال `FUN_…`.
- decompile لنقطة الدخول:
```c
void entry(void)
{
  FUN_140001f98();   // (استنتاج) __security_init_cookie
  FUN_140001840();   // (استنتاج) __scrt_common_main_seh -> wWinMain 0x1400101d8
  return;
}
```
- decompile لـ wWinMain `FUN_1400101d8` (خد 5 دقايق و15 ثانية): الملخص من الكود (الكود كله في `raw\rea_decompile_winmain_notepad.md`):
  `GetCommandLineW` ← `CoCreateGuid` ← `EventRegister`/`EventSetInformation` (تسجيل ETW) ← `HeapSetInformation(HeapEnableTerminationOnCorruption)` ← `CoInitializeEx(…,2)` ← يعدّي اسم البرنامج في سطر الأوامر (ومراعي علامات `"`) ← `FUN_140013150(hInstance)` (تجهيز الشباك) ← `SetWinEventHook(0x800b,0x800b,…, GetCurrentProcessId())` على عمليته هو بس ← لوب الرسائل `GetMessageW` / `TranslateAcceleratorW` / `IsDialogMessageW` (شبابيك البحث والاستبدال) / `TranslateMessage` / `DispatchMessageW`.
  وفيه `swi(0x29)` بالرقم 5، وده `__fastfail` (إنهاء أمان فوري)، مش حيلة ضد الديباجر.

**يعني إيه:** Ghidra شغال كويس على الجهاز عن طريق REA. ونقطة الدخول هي نقطة دخول MSVC القياسية (أول تعليمات اتأكدت بـ capstone: `sub rsp,0x28; call 0x140001f98; add rsp,0x28; jmp 0x140001840`). Ghidra ماشتغلش على أي ملف كبير.

## jadx
ماتشغّلش، لأن مفيش ولا APK/DEX في `هام` (`find … -iname "*.apk" -o -iname "*.dex" -o -iname "*.aab" -o -iname "*.xapk"` رجّع صفر).

## apktool
ماتشغّلش، لنفس السبب: مفيش APK يتفك.

## adb
**الأمر (مرة واحدة زي ما اتطلب):** `RT run adb devices` ← `List of devices attached` (فاضية). adb 1.0.41.
**يعني إيه:** مفيش موبايل متوصّل. الأمر شغّل الـ adb daemon، فقفلته بعدها بـ `RT run adb kill-server` عشان يرجع الجهاز زي ما كان.

## apkleaks
ماتشغّلش، لأن مفيش APK.

## androguard
ماتشغّلش، لأن مفيش APK/DEX/AXML.

## frida
**ماتشغّلش، لأن القاعدة إن ممنوع تشغيل الملف المحلَّل، ومحتاج إذن صريح.**
Frida بيدخل جوه عملية شغالة أو بيعمل spawn للملف، وده تشغيل.
**كان هيورّينا إيه:** لو اتعمل attach لـ notepad، كنا هنشوف النداءات الحقيقية وهي بتحصل: `CreateFileW`/`WriteFile` وقت الحفظ، و`RegSetValueExW` (الإعدادات تحت `HKCU\Software\Microsoft\Notepad`)، و`ShellExecuteW` (فتح لينكات المساعدة `go.microsoft.com/fwlink`). ولو InstallUtil، كنا هنشوف `Assembly.LoadFrom` للـ assembly اللي اتبعتتله وتشغيل `Installer.Install/Uninstall`.

## frida-ps
**الأمر (قراءة بس، عشان نثبت إن الأداة شغالة):** `RT run frida-ps` ← (frida 17.26.2) **195 عملية محلية**. ماسجلتش أسماء البرامج.
**يعني إيه:** Frida متثبت وشايف العمليات. ومفيش أي نسخة من العينات من ضمنهم شغالة، لأننا ماشغلناش حاجة.

## frida-trace
**ماتشغّلش، لأن القاعدة إن ممنوع تشغيل الملف المحلَّل، ومحتاج إذن صريح.**
**كان هيورّينا إيه:** `RT run frida-trace -i "RegSetValueExW" -i "ShellExecuteW" -i "CreateFileW" -p <PID>` كان هيطبع كل نداء للدوال دي ومعاه الأرجيومنتس وقت التشغيل الحقيقي.

## tshark
ماتشغّلش، لأن مفيش ملفات pcap/pcapng/cap تحت `هام` (`find … -iname "*.pcap" -o -iname "*.pcapng" -o -iname "*.cap"` رجّع صفر). والتقاط ترافيك حي يحتاج تشغيل الملفات، وده ممنوع.

## mitmdump
**ماتشغّلش، لأن القاعدة إن ممنوع تشغيل الملف المحلَّل، ومحتاج إذن صريح.** وكمان مفيش ملفات flows/har تحت `هام`.
**كان هيورّينا إيه:** أي طلبات HTTP/HTTPS العينة بتعملها وهي شغالة. ومن التحليل الثابت، notepad فيه لينكات `go.microsoft.com/fwlink` بس (مساعدة/feedback)، وInstallUtil مفيهوش أي كود شبكة (اللينكات اللي ظهرت في triage جوه شهادة التوقيع نفسها: CRL/CRT).

## webcrack

**اختيار الملف:** `find "…\output\black-dragon" -iname "*.js" -o -iname "*.mjs" -o -iname "*.cjs"` (230 ملف، ومفيش `node_modules`) وبعدها قسته (متوسط طول السطر ونسبة المسافات):
- الأكبر خالص `tools\cartoon\vendor\three.module.js` (1.27MB)، بس **مش مضغوط** (53045 سطر، والمسافات 21%).
- **أكبر ملف مضغوط/مجمّع:** `tools\codekit\vendor\three\three.min.js` (749,765 بايت، 4234 سطر، أطول سطر 242,945 حرف، المسافات 5%، ومكتوب `var THREE=(()=>{var Jh=Object.defineProperty…`، وده شكل bundle بتاع esbuild).
- تاني ملف: `tools\codekit\vendor\mojs\mo.umd.js` (120,660 بايت في 6 سطور، UMD bundle).
- سكربت الواجهة/الإضافة `skills\library\pro-motion\extras\panel\main.js` (85KB، لوحة After Effects) **مش مضغوط** (متوسط السطر 74 حرف)، فمفيش داعي نعمله فك.
- الملفين اتنسخوا لـ `RE\samples\js\`.

**الأمر:** (من جوه `RE\samples\js`) `RT run webcrack three.min.js -o RE\raw\webcrack_three -f` و`RT run webcrack mo.umd.js -o RE\raw\webcrack_mo -f`.

**النتيجة:**
- three.min.js: `prepare 3697 changes`، و`deobfuscate 0 changes`، و`transpile, unminify 15856 changes`، و`self-defending, debug-protection 0 changes`. الناتج ملف واحد `deobfuscated.js` (1,129,240 بايت، 38,915 سطر مقروء). وخد دقيقة و13 ثانية.
- mo.umd.js: `prepare 783`، و`deobfuscate 0`، و`unminify 4073`، و`self-defending/debug-protection 0`. الناتج ملف واحد `deobfuscated.js` (7,260 سطر).
- في الحالتين مفيش ولا module اتفك لملف لوحده، لأن webcrack مالقاش صيغة webpack/browserify.

**يعني إيه:** الملفين مكتبات طرف تالت معروفة (Three.js وmo.js) **متصغّرة بس، مش متشوّشة**: صفر تغييرات deobfuscate، وصفر حماية ذاتية أو anti-debug. webcrack رجّع الكود مقروء ومتنسق. ومفيش في `black-dragon` سكربت واجهة مجمّع بـ webpack يستاهل فك أعمق.

## wasm2wat
ماتشغّلش، لأن مفيش ملفات `.wasm` تحت `هام` (`find … -iname "*.wasm"` رجّع صفر).

## wasm-objdump
ماتشغّلش، لنفس السبب: مفيش WASM.

## pylibs

**السكربت:** `RE\scripts\pe_facts.py` (pefile 2024.8.26 + LIEF 1.0.0 + dnfile 0.18.0 + capstone 5.0.7). وفيه ملحوظة: LIEF مابيعرفش يفتح مسار عربي، فبنديله البايتات (`io.BytesIO`).
**الأمر:** `RT run pylibs -I -X utf8 "RE\scripts\pe_facts.py" "RE\samples\notepad.exe" "RE\samples\InstallUtil.exe" > RE\raw\pylibs_pe_facts.txt`

**النتيجة — notepad:**
- `PE32+`، subsystem 2 (GUI). `TimeDateStamp 2018-09-16 05:58:28 UTC`، بس الـ debug directory فيه `REPRO`، يعني التاريخ ده هاش مش تاريخ.
- الـ checksum في الهيدر `0x5af26` = المحسوب ✓. وASLR وHighEntropyVA وNX وCFG كلهم شغالين.
- الأقسام والإنتروبي: `.text 6.238`، و`fothk 0.016`، و`.rdata 5.582`، و`.data 1.624`، و`.pdata 3.320`، و`.didat 0.252`، و`.rsrc 6.968`، و`.reloc 1.619`. والـ overlay = 0.
- الـ imports: **50 DLL / 315 دالة + delay-load 6 DLL / 25 دالة = 340**. و`imphash 0e6bccf88f4251909d1746dba78cba57` (نفس قيمة REA). والـ exports = 0.
- التوقيع: **مفيش توقيع مدموج** (`security directory size=0`).
- نقطة الدخول (capstone): `0x1400019c0: sub rsp,0x28 / call 0x140001f98 / add rsp,0x28 / jmp 0x140001840`.

**النتيجة — InstallUtil:**
- `PE32+`، subsystem 3 (CUI). `TimeDateStamp 2026-07-20 21:50:06 UTC`. الـ checksum مطابق ✓. وCFG=False (عادي في ‎.NET).
- الأقسام: `.text 4.924`، و`.rsrc 5.073`. والـ **overlay = 10096 بايت** (هو التوقيع نفسه).
- الـ imports: **0**، والـ imphash مفيش.
- التوقيع: `security directory offset=25088 size=10096`. الشهادات: `CN=Microsoft Corporation` ← `Microsoft Code Signing PCA 2024` ← `Microsoft Root Certificate Authority 2011`. **`LIEF verify_signature(): VERIFICATION_FLAGS.OK`**، والـ authentihash المحسوب `a10fdf9c…5281928` **مطابق** للـ digest الموقّع.
- ‎.NET (dnfile): runtime 2.5، و`flags=0x9` (IL-only + strong-name signed)، و`entry token=0x06000004` (= `InstallUtil.Main`)، وmetadata `v4.0.30319`. TypeDef=9، وMethodDef=16، وTypeRef=41، وMemberRef=56، وAssemblyRef=3 (`mscorlib` و`System` و`System.Configuration.Install`)، و**ImplMap (P/Invoke)=0**، وModuleRef=0. وفيه 8 user strings (`Microsoft_Copyright_CommandLine_Logo` و`InstallUtilSignOnMessage` و`4.8.10001.0` و`en-US` …). والـ TypeDefs بنفس الأسماء والدوال اللي طلعت في ILSpy وREA.
- `AddressOfEntryPoint = 0` (طبيعي لـ PE32+ IL-only).

**يعني إيه:** ده تأكيد مستقل لكل الحاجات المهمة: عدد الـ imports وغياب التوقيع المدموج في notepad، ووجود توقيع مايكروسوفت **سليم** في InstallUtil (الملف ماتغيّرش بعد ما اتوقّع)، وشكل الـ metadata بتاع ‎.NET.

## olevba
ماتشغّلش، لأن مفيش ملفات Office ولا ماكرو تحت `هام`. `find … -iname "*.doc*" -o -iname "*.xls*" -o -iname "*.ppt*" -o -iname "*.dotm" -o -iname "*.xlam" -o -iname "*.rtf" -o -iname "*.mht*" -o -iname "*.slk" -o -iname "*.vbs" -o -iname "*.bas"` رجّع صفر.

## x64dbg
**ماتفتحش، لسببين:** (1) لو x64dbg فتح أي ملف فهو **بيشغّله** (بيعمل له create process ويقف عند أول breakpoint)، والقاعدة إن ممنوع تشغيل الملف المحلَّل ومحتاج إذن صريح. (2) هو برنامج بواجهة رسومية وهيفتح شبابيك على شاشة صاحب الجهاز.
- الأمر لو جه إذن: `RT run x64dbg` (بيفتح `C:\Users\cinde\re-tools\x64dbg\release\x96dbg.exe`) وبعدين File > Open ← `RE\samples\notepad.exe`. أو على طول: `"C:\Users\cinde\re-tools\x64dbg\release\x64\x64dbg.exe" "RE\samples\notepad.exe"`.
- **كان هيورّينا إيه:** تتبّع خطوة بخطوة من `entry 0x1400019c0` لحد `wWinMain 0x1400101d8` ولحد ما الشباك يتعمل. وجزء التحليل الثابت من ده موجود في أقسام **ghidra** و**rizin** وcapstone (pylibs).

## imhex
**ماتفتحش (واجهة رسومية).**
- الأمر: `RT run imhex "RE\samples\notepad.exe"` (ونفس الكلام لـ `InstallUtil.exe`، عشان تشوف الـ overlay بتاع التوقيع من 0x6200).
- نفس المعلومات موجودة في أقسام: **die** (`-e` إنتروبي كل قسم)، و**pylibs** (الأقسام والإنتروبي والـ overlay)، و**rz-bin** (`-S`).

## ilspy-gui
**ماتفتحش (واجهة رسومية).**
- الأمر: `RT run ilspy-gui "RE\samples\InstallUtil.exe"`.
- نفس المعلومات موجودة في قسم **ilspy** (الكود C# كله في `RE\ilspy_out\`)، وفي REA `inspect-managed-members` وdnfile (pylibs).

## die-gui
**ماتفتحش (واجهة رسومية).**
- الأمر: `RT run die-gui "RE\samples\notepad.exe"` (و`InstallUtil.exe`).
- نفس المعلومات موجودة في قسم **die** (CLI بـ `-j` و`-e`).

## rea

**الأوامر (REA 6.8.0، كلها قراءة ثابتة، والمخرجات في `raw\rea_*`):**
- `rea inspect-artifact <f> --format md`، و`rea inspect-pe-imports <f>`، و`rea inspect-pe-certificates <f>`، و`rea inspect-pe-resources <f>`، و`rea inspect-pe-load-config <f>`، على الملفين (`--format md` و`--format json`).
- InstallUtil: `rea inspect-managed-artifact` و`rea inspect-managed-members` و`rea inspect-managed-native-boundaries` (`--format json`).
- الـ pyc: `rea inspect-python-pyc RE\samples\re.cpython-312.pyc --format json`.
- Ghidra: `rea analyze` و`rea decompile` (شوف قسم ghidra).
- `list-strings` مش موجود كأمر CLI في REA 6.8 (موجود كأداة MCP بس). عدد النصوص اتاخد من `rea analyze` (`string_count=638`)، والنصوص نفسها من FLOSS (3665 static).

**النتيجة:**
- `inspect-artifact` (الاتنين): `root_format=pe`، وhypothesis واحد بس («ممكن managed أو native»)، والخطوة الجاية المقترحة `inspect_managed_artifact`.
- `inspect-pe-imports`: notepad: 50 DLL / 315 import + 6 DLL delay / 25، و`imphash 0e6bccf8…cba57`. والـ delay-load هي: `ADVAPI32` (`DecryptFileW` و`DuplicateEncryptionInfoFile`)، و`COMDLG32` (Open/Save/Font/Print/Find/Replace)، و`PROPSYS`، و`SHELL32` (`ShellExecuteW` و`SHGetKnownFolderPath` و`SHAddToRecentDocs` و`DragAcceptFiles` …)، و`WINSPOOL.DRV` (الطباعة)، و`urlmon` (`FindMimeFromData`). أما InstallUtil: `IMAGE_DIRECTORY_ENTRY_IMPORT is absent or empty`.
- `inspect-pe-certificates`: notepad: `entries=[]`، و«IMAGE_DIRECTORY_ENTRY_SECURITY is absent. That is not proof the image is unsigned». أما InstallUtil: PKCS#7 signedData بـ SHA-256، والموقّع `Microsoft Corporation` (serial `330000021d4d19c84ed70f574800000000021d`، صالح من 2026-04-16 لـ 2027-04-15) والمُصدِر `Microsoft Code Signing PCA 2024`. REA قال صراحة إنه **مابيتحققش** من صحة التوقيع، والتحقق اتعمل بـ LIEF وبـ PowerShell.
- `inspect-pe-resources`: notepad فيه 31 مورد: 22 أيقونة (type 3)، و4 icon groups، وversion (16)، وmanifest (24)، و`EDPENLIGHTENEDAPPINFOID` و`EDPPERMISSIVEAPPINFOID` و`MUI`. أما InstallUtil: version + manifest بس.
- `inspect-pe-load-config`: notepad: مفيش TLS callbacks، وCFG شغال (`guard_cf_function_count=131` و`IMAGE_GUARD_CF_INSTRUMENTED` و`…EH_CONTINUATION_TABLE_PRESENT`…). أما InstallUtil: مفيش load config ولا TLS.
- `inspect-managed-artifact`: `il-only` و`strong-name-signed`، و`entry_point 0x06000004`، وmetadata `v4.0.30319`، وAssembly `InstallUtil 4.0.0.0` (public key token `b03f5f7f11d50a3a`، بتاع مايكروسوفت)، والـ references: `mscorlib` و`System` و`System.Configuration.Install`، والـ resources: `InstallUtil.resources` و`CommonResStrings.resources`.
- `inspect-managed-members`: 9 types و16 methods و63 call edge. Main بينادي بالترتيب: `get_CurrentUICulture` و`GetConsoleFallbackUICulture` و`get_CodePage` و`get_OEMCodePage` و`get_ANSICodePage` و`GetEntryAssembly` و`GetCustomAttributes` و`get_CopyrightForCmdLine` و`GetString` و`WriteLine` و**`InstallHelper`** و`get_Message` و`WriteLine`.
- `inspect-managed-native-boundaries`: `pinvoke_import_count=0`، و`module_ref_count=0`، و`mixed_mode_or_native_header=false`.
- `inspect-python-pyc`: `magic 3531 (3.12)`، و`hash_based=false`، و`source_mtime=1794466341`، و`source_size=25952`، و33 code object.
- **التحقق من التوقيع بأداة خارج REA** (PowerShell `Get-AuthenticodeSignature -LiteralPath <copy>`، قراءة بس): notepad `Status=Valid | SignatureType=Catalog | IsOSBinary=True | Signer=CN=Microsoft Windows`. وInstallUtil `Status=Valid | SignatureType=Catalog | IsOSBinary=True`، وكمان جواه توقيع مدموج سليم (LIEF).

**يعني إيه:** REA أكّد كل حاجة طلعت من rz-bin وpefile وILSpy بأرقام مطابقة (imports وتوقيع وmetadata وcall graph). وnotepad «من غير توقيع مدموج» مش معناها إنه مش موقّع: هو **موقّع بكتالوج ويندوز** وطلع Valid.

---

## الخلاصة: دليل / استنتاج / مجهول

### ✅ متأكد بالدليل
1. **العينتين نسخ طبق الأصل من ملفات ويندوز:** notepad = `C:\Windows\System32\notepad.exe` وInstallUtil = `…\Framework64\v4.0.30319\InstallUtil.exe`. الدليل: `sha256sum` (نفس البصمة)، و`rz-diff -d myers/leven` (distance 0)، و`-t imports/sections/entries/strings` (0 اختلاف).
2. **الملفين موقّعين من مايكروسوفت وسليمين:** `Get-AuthenticodeSignature` ← Valid / Catalog / IsOSBinary=True للاتنين. وInstallUtil كمان فيه توقيع مدموج: REA `inspect-pe-certificates` (شهادة Microsoft Corporation / PCA 2024) + `LIEF verify_signature()=OK` (الـ authentihash مطابق) + die («Windows Authenticode»).
3. **notepad مفيهوش توقيع مدموج** (موقّع بكتالوج بس): REA (`entries=[]`)، وpefile (`security dir size=0`)، وomni (`signed_blob=false`).
4. **مفيش ضغط ولا تشفير:** die («not packed»)، وUPX `-t`/`-l` (`NotPackedException`)، و`grep UPX!` = 0، وإنتروبي عادي (omni وpefile)، وFLOSS (0 decoded و0 tight وstack string واحد بس `Lucida C`).
5. **notepad فيه 340 import (315 + 25 delay):** rz-bin `-i` = 340، وREA (315+25) وpefile (315+25)، والـ imphash نفسه في REA وpefile.
6. **InstallUtil مفيهوش import table ومفيهوش P/Invoke:** omni وrz-bin وREA وpefile (0 imports)، وREA boundaries وdnfile (`ImplMap=0`).
7. **InstallUtil.Main بيطبع banner ويبعت الأرجيومنتس لـ `ManagedInstallerClass.InstallHelper`:** ILSpy (`InstallUtil.cs`) + REA `call_edges` + dnfile (entry token `0x06000004` = Main).
8. **الـ pyc مطابق للمصدر `re.py` بالبايت:** `pyc_vs_source.py` (0 اختلاف في 33 code object، والـ mtime والحجم مطابقين) + pydisasm (33، و25952، و1794466341) + REA `inspect-python-pyc` (33، و25952، و1794466341).
9. **قواعد الـ 9 ملفات `.yar` (ملفين فريدين) ماطابقتش ولا exe:** yara وyara-x (0)، مع ضبط إيجابي نجح على المحرّكين.
10. **مفيش أسرار حقيقية في `output\black-dragon` و`white-dragon`:** yara وyara-x طلّعوا 190 تطابق متطابقين 100% (`both=190`)، وكلهم اتراجعوا ونوعهم إنذار غلط. وAWS = 0، وGoogle = 0.
11. **Ghidra شغال عن طريق REA:** `rea analyze` (853 دالة و638 نص في 5:44) و`rea decompile` لنقطة الدخول (`entry` ← `FUN_140001f98` ← `FUN_140001840`)، وده متطابق مع capstone وrizin.
12. **مفيش موبايل متوصّل** (`adb devices` فاضية)، و**مفيش APK/pcap/wasm/Office/PyInstaller** تحت `هام` (أوامر `find`/`grep` في أقسامها).

### 🟡 استنتاج (مش دليل مباشر)
- الملفين **سليمين ومش متعدّلين** ومحطوطين في `white-dragon-workspace\re\samples` كأهداف تدريب على الهندسة العكسية: **~99%** (البصمة مطابقة لملفات النظام + التوقيع سليم).
- قدرات capa «المريبة» في notepad مش سلوك خبيث: `analysis tools strings` إنذار غلط **بالدليل** (`<IDAT` جوه PNG)، و`parse PE header` تحقق الـ CRT، و`rdtsc`/XOR في دالة التجهيز `0x140013150` غالبًا توقيت أو hash داخلي: **~90%** (الملف مطابق لملف النظام. أماكن التطابق في `capa_notepad_vv.txt`).
- `CreateProcessW` في `fcn.140023c00` (بيبني `"<path>" …`) غالبًا notepad بيفتح نسخة جديدة من نفسه (شباك جديد أو إعادة تشغيل): **~75%** ← تحسمها بقراية الكود كله: `rea decompile <copy> 0x140023c00`.
- InstallUtil نفسه سليم، **بس** هو أداة «مزدوجة الاستخدام» معروفة (LOLBin، ATT&CK T1218.004): أي حد يقدر يستخدمه عشان يشغّل كود من DLL ‎.NET عن طريق كلاسات `Installer`: **~95%**. ده من المعرفة العامة ومن إن Main بيبعت الأرجيومنتس لـ `InstallHelper` من غير أي فحص، والمنطق نفسه في `System.Configuration.Install.dll` اللي ماتحللش هنا.
- تاريخ notepad (2018) ملوش أي معنى، أما تاريخ InstallUtil (2026-07-20) فهو تاريخ بناء حقيقي تقريبًا لتحديث .NET 4.8.1: **~85%** (notepad فيه REPRO، وInstallUtil مفيهوش REPRO، وشهادته صالحة من 2026-04-16).
- قسم `fothk` في notepad حاجة طبيعية في بناء ويندوز الحديث (thunks)، مش إضافة غريبة: **~90%** (لأنه موجود في ملف System32 الأصلي اللي بصمته هي هي).

### ❓ مجهول (والخطوة اللي تحسمه)
- **InstallHelper بيعمل إيه بالظبط جوه** ← انسخ `C:\Windows\Microsoft.NET\Framework64\v4.0.30319\System.Configuration.Install.dll` لـ `samples` واعمله `RT run ilspy -p -o RE\ilspy_out_sci <copy>`، وبعدين اقرا `ManagedInstallerClass.InstallHelper`.
- **سلوك الملفين وهما شغالين** (ذاكرة/شبكة/Registry) ← محتاج إذن صريح منك، وبعدها تشغيل في VM معزولة مع pe-sieve وfrida-trace وmitmdump.
- **الـ PDB الحقيقي** (`notepad.pdb` بـ GUID `3a948121-747c-b385-e78f-a83b9dae2a69`) عشان أسماء الدوال الحقيقية بدل `FUN_…` ← تنزيله من Microsoft Symbol Server، وده محتاج إذن لأنه اتصال بالنت.
- **أسرار برا الفولدرين اللي اتفحصوا** (مثلًا `output\_src` و`output\_work` وباقي `هام`) ← `python -I -X utf8 RE\scripts\secrets_scan.py RE\scripts\secrets.yar RE\raw\secrets_all "C:\Users\cinde\OneDrive\Desktop\هام"`.
- **مين حط العينات في `white-dragon-workspace` وليه** (الـ mtime بتاعها 2026-11-12 10:26) ← راجع لوج/تاريخ جلسات white-dragon في نفس الوقت ده.

---

### أدوات فشلت أو كان فيها مشكلة
- `upx` بالمسار الكامل: `FileNotFoundException` (مابيفهمش الحروف العربي). **اتحلّت** بالاسم النسبي.
- `rz-diff -d ssdeep`: `ERROR: the expected hashes are not in ssdeep format` (الوضع ده محتاج قيم ssdeep مش ملفات). **ماأثرش** على النتيجة، لأن myers وleven قالوا distance 0.
- `capa -r <subfolder anti-analysis>`: exit 12 (`depends on missing rule`). **اتحلّت** بتشغيل `-vv` على مجلد القواعد كله.
- `LIEF` مع مسار عربي: `Failed to open` ← **اتحلّت** بإننا بنديله البايتات (`io.BytesIO`).
- `floss` على InstallUtil: شغال، بس بيقول إن ‎.NET مش مدعوم في فك النصوص (قيد في الأداة، مش عطل).
- REA `list-strings` مش موجود كأمر CLI في 6.8، فاستخدمنا `string_count` من `rea analyze` + FLOSS.
