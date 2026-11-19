# خريطة جهاز صاحب التنين (MACHINE_MAP)

اتسجّلت بالفحص الفعلي يوم 2026-11-11T16:10:37 على `Windows-11-10.0.26300-SP0`، ومجلد المستخدم `C:\Users\cinde`.

**المسارات دي موجودة على اللابتوب بس.** في محادثة سحابية ماتستخدمهاش: اشتغل بمحركات الحزمة (`dragon.py tool machine mode cloud`).
للتحديث على الجهاز: `python scripts/dragon.py tool machine scan --write`. للتأكد إن المسارات لسه موجودة: `tool machine doctor`.

## فيديو ومونتاج

| الاسم | بيعمل إيه | المسار | مثال |
|---|---|---|---|
| `ffmpeg` | قص وتجميع وترميز الفيديو والصوت | `C:\Users\cinde\AppData\Local\Microsoft\WinGet\Links\ffmpeg.EXE` | `ffmpeg -i in.mp4 -c:v libx264 -crf 17 out.mp4` |
| `ffprobe` | قياس الفيديو والصوت (مدة، أبعاد، فريمات) | `C:\Users\cinde\AppData\Local\Microsoft\WinGet\Links\ffprobe.EXE` | `ffprobe -v error -show_streams in.mp4` |
| `melt` | محرك Kdenlive/MLT للمونتاج من سطر الأوامر | `C:\Users\cinde\AppData\Local\Programs\Kdenlive\bin\melt.EXE` | `melt in.mp4 -consumer avformat:out.mp4` |
| `kdenlive` | Kdenlive: مونتاج بواجهة | `C:\Users\cinde\AppData\Local\Programs\Kdenlive\bin\kdenlive.EXE` |  |
| `natron` | Natron: كومبوزيتنج ورندر | `C:\Users\cinde\AppData\Local\Programs\Natron\bin\NatronRenderer.EXE` | `NatronRenderer project.ntp` |
| `mkvmerge` | دمج وفصل مسارات MKV | `C:\Program Files\MKVToolNix\mkvmerge.EXE` | `mkvmerge -o out.mkv in.mp4` |
| `scenedetect` | كشف القطعات في الفيديو | `C:\Users\cinde\AppData\Local\Programs\Python\Python312\Scripts\scenedetect.EXE` | `scenedetect -i in.mp4 detect-adaptive list-scenes` |
| `auto-editor` | قص السكتات تلقائي | `C:\Users\cinde\AppData\Local\Programs\Python\Python312\Scripts\auto-editor.EXE` | `auto-editor in.mp4 --margin 0.2sec` |
| `handbrake` | HandBrake: ترميز | ✗ مش موجود وقت الفحص |  |
| `obs` | OBS: تسجيل الشاشة | `C:\Program Files\obs-studio\bin\64bit\obs64.EXE` |  |

## صور وتصميم

| الاسم | بيعمل إيه | المسار | مثال |
|---|---|---|---|
| `magick` | ImageMagick: تحويل وتعديل الصور | `C:\Program Files\ImageMagick-7.1.2-Q16-HDRI\magick.EXE` | `magick in.png -resize 1080x1920 out.jpg` |
| `gimp` | GIMP في الخلفية | `C:\Users\cinde\AppData\Local\Programs\GIMP 3\bin\gimp-console-3.2.EXE` | `gimp-console-3.2 -i -b "(…)"` |
| `inkscape` | Inkscape: فيكتور وSVG | `C:\Program Files\Inkscape\bin\inkscape.COM` | `inkscape in.svg --export-type=png` |
| `upscayl` | تكبير الصور 4× بالذكاء الاصطناعي | `C:\Program Files\Upscayl\resources\bin\upscayl-bin.EXE` | `upscayl-bin -i in.png -o out.png -s 4` |
| `krita` | Krita في الخلفية | `C:\Program Files\Krita (x64)\bin\kritarunner.COM` |  |
| `darktable` | darktable: تحميض RAW | `C:\Users\cinde\AppData\Local\Programs\darktable\bin\darktable-cli.EXE` | `darktable-cli in.raw out.jpg` |
| `rawtherapee` | RawTherapee: تحميض RAW | `C:\Program Files\RawTherapee\5.13\rawtherapee-cli.EXE` | `rawtherapee-cli -o out.jpg -c in.raw` |
| `rembg` | شيل الخلفية من الصور | `C:\Users\cinde\AppData\Local\Programs\Python\Python312\Scripts\rembg.EXE` | `rembg i in.png out.png` |
| `exiftool` | قراية وتعديل بيانات الملفات (EXIF) | `C:\Users\cinde\AppData\Local\Programs\ExifTool\exiftool.EXE` | `exiftool file.jpg` |
| `paint` | الرسام (Windows Paint) | `C:\Users\cinde\AppData\Local\Microsoft\WindowsApps\mspaint.EXE` |  |

## صوت وتفريغ

| الاسم | بيعمل إيه | المسار | مثال |
|---|---|---|---|
| `whisperx` | تفريغ بتوقيت الكلمات | `C:\Users\cinde\AppData\Local\Programs\Python\Python312\Scripts\whisperx.EXE` | `whisperx audio.wav --language ar` |
| `faster-whisper` | تفريغ سريع | ✗ مش موجود وقت الفحص |  |
| `demucs` | فصل الصوت عن الموسيقى | `C:\Users\cinde\AppData\Local\Programs\Python\Python312\Scripts\demucs.EXE` | `demucs --two-stems=vocals song.mp3` |
| `deep-filter` | تنضيف الصوت من الدوشة | `C:\Users\cinde\dragon-tools\bin\deep-filter.EXE` | `deep-filter in.wav -o outdir` |
| `edge-tts` | تحويل نص لصوت (أصوات مايكروسوفت) | `C:\Users\cinde\AppData\Local\Programs\Python\Python312\Scripts\edge-tts.EXE` | `edge-tts --voice ar-EG-SalmaNeural --text "…" --write-media out.mp3` |
| `sox` | معالجة صوت | ✗ مش موجود وقت الفحص |  |
| `audacity` | Audacity: تحرير صوت بواجهة | ✗ مش موجود وقت الفحص |  |

## ثلاثي الأبعاد

| الاسم | بيعمل إيه | المسار | مثال |
|---|---|---|---|
| `blender` | Blender: تصميم ورندر 3D في الخلفية | `C:\Program Files\Blender Foundation\Blender 5.2\blender.EXE` | `blender -b scene.blend -P script.py` |

## تحميل

| الاسم | بيعمل إيه | المسار | مثال |
|---|---|---|---|
| `yt-dlp` | تحميل فيديو من يوتيوب وتيك توك وانستجرام وغيرهم | `C:\Users\cinde\AppData\Local\Programs\Python\Python312\Scripts\yt-dlp.EXE` | `yt-dlp -f bv*+ba/b URL` |
| `aria2c` | تحميل مسرّع بتعدد اتصالات | `C:\Users\cinde\AppData\Local\Microsoft\WinGet\Packages\aria2.aria2_Microsoft.Winget.Source_8wekyb3d8bbwe\aria2-1.37.0-win-64bit-build1\aria2c.EXE` | `aria2c -x16 -s16 URL` |
| `gallery-dl` | تحميل ألبومات صور | ✗ مش موجود وقت الفحص |  |
| `curl` | طلبات HTTP وتحميل | `C:\Program Files\Git\ucrt64\bin\curl.EXE` |  |
| `fast-dl` | تحميل سريع | `C:\Users\cinde\dragon-tools\fast_dl.py` | `python C:\Users\cinde\dragon-tools\fast_dl.py URL` |

## مستندات وأرشيف وبحث

| الاسم | بيعمل إيه | المسار | مثال |
|---|---|---|---|
| `pandoc` | تحويل المستندات (Word/Markdown/HTML/PDF) | `C:\Users\cinde\AppData\Local\Pandoc\pandoc.EXE` | `pandoc in.docx -o out.md` |
| `7z` | ضغط وفك كل الأرشيفات | `C:\Program Files\7-Zip\7z.EXE` | `7z x archive.zip -oout` |
| `jq` | قراية وتعديل JSON | `C:\Users\cinde\AppData\Local\Microsoft\WinGet\Packages\jqlang.jq_Microsoft.Winget.Source_8wekyb3d8bbwe\jq.EXE` | `jq . file.json` |
| `rg` | بحث سريع جوه الملفات (ripgrep) | ✗ مش موجود وقت الفحص | `rg "كلمة" folder` |
| `tesseract` | قراية النص من الصور (OCR) | `C:\Program Files\Tesseract-OCR\tesseract.EXE` | `tesseract in.png out -l ara` |
| `libreoffice` | LibreOffice في الخلفية (تحويل Office لـ PDF) | ✗ مش موجود وقت الفحص | `soffice --headless --convert-to pdf in.docx` |

## برمجة وتشغيل

| الاسم | بيعمل إيه | المسار | مثال |
|---|---|---|---|
| `python` | بايثون الأساسي على الجهاز | `C:\Users\cinde\AppData\Local\Programs\Python\Python312\python.EXE` | `python -X utf8 script.py` |
| `node` | Node.js | `C:\Program Files\nodejs\node.EXE` |  |
| `npm` | مدير حزم Node | `C:\Program Files\nodejs\npm.CMD` |  |
| `git` | Git | `C:\Program Files\Git\ucrt64\bin\git.EXE` |  |
| `gh` | GitHub CLI (المستخدم مسجّل بيها) | `C:\Program Files\GitHub CLI\gh.EXE` | `gh repo list --limit 50` |
| `winget` | مثبّت برامج ويندوز | `C:\Users\cinde\AppData\Local\Microsoft\WindowsApps\winget.EXE` | `winget install -e --id <ID>  (بموافقة المستخدم)` |
| `vscode` | VS Code | ✗ مش موجود وقت الفحص |  |
| `uv` | uv: مدير بيئات بايثون | ✗ مش موجود وقت الفحص |  |
| `dotnet` | .NET SDK | `C:\Program Files\dotnet\dotnet.EXE` |  |
| `java` | Java (JDK) | `C:\Users\cinde\re-tools\jdk\jdk-21.0.13+9\bin\java.EXE` |  |
| `powershell` | PowerShell | `C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.EXE` |  |

## واجهات الذكاء الاصطناعي

| الاسم | بيعمل إيه | المسار | مثال |
|---|---|---|---|
| `claude` | Claude Code CLI | `C:\Users\cinde\AppData\Roaming\npm\claude.CMD` | `claude -p "…"` |
| `codex` | OpenAI Codex CLI (اشتراك ChatGPT) | `C:\Users\cinde\AppData\Roaming\npm\codex.CMD` |  |
| `gemini` | Gemini CLI | `C:\Users\cinde\AppData\Roaming\npm\gemini.CMD` |  |
| `ollama` | Ollama: موديلات محلية | ✗ مش موجود وقت الفحص |  |
| `antigravity` | Google Antigravity | `C:\Users\cinde\AppData\Local\Programs\antigravity\Antigravity.exe` |  |
| `claude-desktop` | تطبيق Claude لسطح المكتب | `shell:AppsFolder\Claude_pzs8sxrjxfjjc!Claude` |  |

## متصفحات

| الاسم | بيعمل إيه | المسار | مثال |
|---|---|---|---|
| `chrome` | Google Chrome | `C:\Program Files\Google\Chrome\Application\chrome.EXE` |  |
| `edge` | Microsoft Edge | `C:\Program Files (x86)\Microsoft\Edge\Application\msedge.EXE` |  |
| `firefox` | Firefox | `C:\Program Files\Mozilla Firefox\firefox.EXE` |  |

## أجزاء التنين الأسود

| الاسم | بيعمل إيه | المسار | مثال |
|---|---|---|---|
| `dragon-app` | تطبيق التنين الأسود (ويندوز) | `C:\Users\cinde\AppData\Local\BlackDragon\BlackDragon.exe` | `start "" "C:\Users\cinde\AppData\Local\BlackDragon\BlackDragon.exe"` |
| `dragon-repo` | مستودع التنين الأسود (المحركات والكتالوج) | `C:\Users\cinde\OneDrive\Desktop\التنين الأسود` | `cd C:\Users\cinde\OneDrive\Desktop\التنين الأسود; python -m dragon find "…"` |
| `dragon-app-source` | كود تطبيق التنين (app.py، control.py، الواجهة) | `C:\Users\cinde\OneDrive\Desktop\التنين الأسود\apps\dragon_desktop` |  |
| `dragon-mcp` | خادم MCP بتاع التنين (أدوات blackdragon_*) | `C:\Users\cinde\OneDrive\Desktop\التنين الأسود\apps\dragon_desktop\mcp_dragon.py` |  |
| `dragon-app-data` | بيانات التطبيق: المحادثات والإعدادات | `C:\Users\cinde\AppData\Roaming\BlackDragon` |  |
| `skills-dir` | كل مهارات Claude المتثبتة | `C:\Users\cinde\.claude\skills` |  |
| `montage-dir` | مجلد المونتاج | ✗ مش موجود وقت الفحص |  |
| `kosif-tool` | مستودع KOSIF (سوبر باور 212 أداة) | `C:\Users\cinde\kosif-tool` |  |
| `superpowers-hub` | باب سوبر باور | `C:\Users\cinde\kosif-tool\.claude\skills\kosif-superpowers\scripts\hub.py` | `python C:\Users\cinde\kosif-tool\.claude\skills\kosif-superpowers\scripts\hub.py find "…"` |
| `dragon-tools` | أدوات مساعدة (fast_dl.py وغيره) | `C:\Users\cinde\dragon-tools` |  |
| `dragon-repos` | مستودعات المونتاج المحمّلة (video-use، hyperframes، whisperX…) | `C:\Users\cinde\dragon-repos` |  |

## هندسة عكسية وتحليل

| الاسم | بيعمل إيه | المسار | مثال |
|---|---|---|---|
| `re-tools` | صندوق أدوات الهندسة العكسية | `C:\Users\cinde\re-tools` |  |
| `retool` | باب صندوق الهندسة العكسية | `C:\Users\cinde\re-tools\retool.py` | `python C:\Users\cinde\re-tools\retool.py triage FILE --deep` |
| `omni` | المحلل الشامل: تعرّف وخطة تحليل لأي هدف | `C:\Users\cinde\.claude\skills\omni-analyst\scripts\omni.py` | `python -X utf8 C:\Users\cinde\.claude\skills\omni-analyst\scripts\omni.py classify TARGET` |
| `rea-digest` | تلخيص نواتج REA الكبيرة | `C:\Users\cinde\.claude\skills\rea-ultra\scripts\rea_digest.py` | `python C:\Users\cinde\.claude\skills\rea-ultra\scripts\rea_digest.py FILE --grep كلمة` |
| `re:die` | Detect It Easy (diec) (تعرّف): بيعرف نوع الملف، والكومبايلر، والباكر أو الحماية (UPX، Themida، ‎.NET، PyInstaller…) | `C:\Users\cinde\re-tools\die\diec.exe` | `run die -j file.exe` |
| `re:capa` | capa (قدرات): بيطلّع قدرات البرنامج من الكود: شبكة، ملفات، تشفير، حقن، تخفّي… مع ربطها بـ MITRE ATT&CK | `C:\Users\cinde\re-tools\capa\capa.exe` | `run capa -r <rules> file.exe` |
| `re:floss` | FLOSS (نصوص): بيطلّع النصوص المخفية والمتشفرة (stack strings و decoded strings) اللي strings العادية مش بتشوفها | `C:\Users\cinde\re-tools\floss\floss.exe` | `run floss --no static file.exe` |
| `re:yara` | YARA (قواعد): بيدوّر في الملفات بقواعد أنماط (توقيعات) | `C:\Users\cinde\re-tools\yara\yara64.exe` | `run yara rules.yar file` |
| `re:yara-x` | YARA-X (yr) (قواعد): النسخة الجديدة الأسرع من YARA | `C:\Users\cinde\re-tools\yara-x\yr.exe` | `run yara-x scan rules.yar file` |
| `re:upx` | UPX (فك ضغط): بيفك ضغط الملفات المضغوطة بـ UPX عشان تتحلل (‎-d) أو يختبرها (‎-t) | `C:\Users\cinde\re-tools\upx\upx-5.3.0-win64\upx.exe` | `run upx -d -o unpacked.exe packed.exe` |
| `re:pe-sieve` | PE-sieve (ذاكرة): بيفحص عملية شغالة ويطلّع أي كود محقون أو متبدّل في الذاكرة (unpacking من الذاكرة) | `C:\Users\cinde\re-tools\pe-sieve\pe-sieve.exe` | `run pe-sieve /pid 1234 /dir out` |
| `re:ilspy` | ILSpy (ilspycmd) (.NET): بيرجّع كود C# من ملفات ‎.NET (exe/dll) | `C:\Users\cinde\re-tools\ilspycmd\.store\ilspycmd\11.2.0.10050\ilspycmd.win-x64\11.2.0.10050\tools\any\win-x64\ilspycmd.exe` | `run ilspy -p -o outdir app.dll` |
| `re:pyinstxtractor` | pyinstxtractor-ng (Python): بيفك برامج بايثون المتغلّفة بـ PyInstaller ويطلّع ملفات ‎.pyc | `C:\Users\cinde\re-tools\pyinstxtractor-ng\pyinstxtractor-ng.exe` | `run pyinstxtractor app.exe` |
| `re:pydisasm` | xdis (pydisasm) (Python): بيعرض بايت كود ملفات ‎.pyc لأي نسخة بايثون | `C:\Users\cinde\re-tools\pyre\venv\Scripts\pydisasm.exe` | `run pydisasm file.pyc` |
| `re:rizin` | Rizin (ديس أسمبلر): إطار تحليل وديس أسمبلي من الترمنال (بديل radare2) | `C:\Users\cinde\re-tools\rizin\rizin-win-installer-vs2019_static-64\bin\rizin.exe` | `run rizin -q -c "aaa;afl" file.exe` |
| `re:rz-bin` | rz-bin (ديس أسمبلر): معلومات الملف التنفيذي: الأقسام، الاستيراد، التصدير، النصوص | `C:\Users\cinde\re-tools\rizin\rizin-win-installer-vs2019_static-64\bin\rz-bin.exe` | `run rz-bin -I file.exe` |
| `re:rz-diff` | rz-diff (مقارنة): مقارنة ملفين تنفيذيين | `C:\Users\cinde\re-tools\rizin\rizin-win-installer-vs2019_static-64\bin\rz-diff.exe` | `run rz-diff -t bytes a.exe b.exe` |
| `re:ghidra` | Ghidra headless (ديكومبايلر): ديكومبايلر NSA: تحليل كامل من غير واجهة (الأسهل عن طريق rea analyze/decompile) | `C:\Users\cinde\re-tools\ghidra\ghidra_12.1.4_PUBLIC\support\analyzeHeadless.bat` | `run ghidra <projDir> <projName> -import file.exe` |
| `re:jadx` | JADX (أندرويد): بيرجّع كود Java من APK/DEX | `C:\Users\cinde\re-tools\jadx\bin\jadx.bat` | `run jadx -d out app.apk` |
| `re:apktool` | Apktool (أندرويد): بيفك موارد الـ APK وملف AndroidManifest والـ smali | `C:\Users\cinde\re-tools\apktool\apktool.bat` | `run apktool d app.apk -o out` |
| `re:adb` | adb (أندرويد): التحكم في موبايل أندرويد متوصّل: سحب تطبيقات، logcat | `C:\Users\cinde\re-tools\platform-tools\platform-tools\adb.exe` | `run adb devices` |
| `re:apkleaks` | APKLeaks (أندرويد): بيدوّر جوه الـ APK على روابط و endpoints ومفاتيح متسابة | `C:\Users\cinde\re-tools\pylibs\venv\Scripts\apkleaks.exe` | `run apkleaks -f app.apk` |
| `re:androguard` | Androguard (أندرويد): تحليل APK/DEX من بايثون والترمنال | `C:\Users\cinde\re-tools\pylibs\venv\Scripts\androguard.exe` | `run androguard axml app.apk` |
| `re:frida` | Frida (وقت التشغيل): مراقبة وتعديل سلوك برنامج وهو شغال (hooks) | `C:\Users\cinde\re-tools\frida\venv\Scripts\frida.exe` | `run frida-ps` |
| `re:frida-ps` | frida-ps (وقت التشغيل): قايمة العمليات اللي Frida يقدر يدخلها | `C:\Users\cinde\re-tools\frida\venv\Scripts\frida-ps.exe` | `run frida-ps` |
| `re:frida-trace` | frida-trace (وقت التشغيل): تتبع استدعاءات دوال معينة في برنامج شغال | `C:\Users\cinde\re-tools\frida\venv\Scripts\frida-trace.exe` | `run frida-trace -i "recv*" -p 1234` |
| `re:tshark` | tshark (Wireshark) (شبكة): قراءة وتحليل ملفات pcap والتقاط الترافيك | `C:\Users\cinde\re-tools\wireshark\App\Wireshark\tshark.exe` | `run tshark -r cap.pcap -q -z conv,ip` |
| `re:mitmdump` | mitmproxy (mitmdump) (شبكة): بروكسي بيسجّل طلبات HTTP/HTTPS اللي برنامجك أو موبايلك بيبعتها | `C:\Users\cinde\re-tools\mitmproxy\venv\Scripts\mitmdump.exe` | `run mitmdump -w flows.mitm` |
| `re:webcrack` | webcrack (جافاسكربت): بيفك تشويش (obfuscation) وتجميع webpack/browserify لملفات JS ويرجّعها مقروءة | `C:\Users\cinde\re-tools\webcrack\node_modules\webcrack\dist\cli.js` | `run webcrack bundle.js -o out` |
| `re:wasm2wat` | WABT wasm2wat (WASM): بيحوّل WebAssembly لنص مقروء | `C:\Users\cinde\re-tools\wabt\wabt-1.0.42\bin\wasm2wat.exe` | `run wasm2wat mod.wasm -o mod.wat` |
| `re:wasm-objdump` | WABT wasm-objdump (WASM): تفاصيل ملف WASM: الدوال والاستيراد والتصدير | `C:\Users\cinde\re-tools\wabt\wabt-1.0.42\bin\wasm-objdump.exe` | `run wasm-objdump -x mod.wasm` |
| `re:pylibs` | Python RE libs (مكتبات): بايثون فيه LIEF و capstone و unicorn و pefile و dnfile و androguard و oletools و pyelftools لسكربتات التحليل | `C:\Users\cinde\re-tools\pylibs\venv\Scripts\python.exe` | `run pylibs script.py` |
| `re:olevba` | oletools (olevba) (مستندات): بيطلّع ويحلل الماكرو من ملفات Office | `C:\Users\cinde\re-tools\pylibs\venv\Scripts\olevba.exe` | `run olevba doc.docm` |
| `re:x64dbg` | x64dbg (ديباجر (واجهة)): ديباجر ويندوز بواجهة رسومية لتتبع البرنامج خطوة خطوة | `C:\Users\cinde\re-tools\x64dbg\release\x96dbg.exe` | `run x64dbg` |
| `re:imhex` | ImHex (هيكس (واجهة)): محرر هيكس للمحللين: أنماط، مقارنة، إنتروبي | `C:\Users\cinde\re-tools\imhex\imhex-gui.exe` | `run imhex file.bin` |
| `re:ilspy-gui` | ILSpy (واجهة) (.NET): واجهة ILSpy الرسومية | `C:\Users\cinde\re-tools\ilspy\ILSpy.exe` | `run ilspy-gui app.dll` |
| `re:die-gui` | Detect It Easy (واجهة) (تعرّف): واجهة DiE الرسومية | `C:\Users\cinde\re-tools\die\die.exe` | `run die-gui file.exe` |
| `re:rea` | REA 6.8 (شامل): المحلل الشامل: exe/.NET/Electron/مواقع/APK/فيرموير + Ghidra + وقت التشغيل | `C:\Users\cinde\AppData\Roaming\npm\rea.CMD` | `rea analyze file.exe --format md` |

## مكتبات بايثون

متثبتة في بايثون الأساسي: `numpy`، `cv2`، `mediapipe`، `librosa`، `moviepy`، `PIL`، `torch`، `playwright`، `pptx`، `docx`، `openpyxl`، `pymupdf`، `pydub`، `soundfile`، `pyloudnorm`، `faster_whisper`، `scenedetect`، `rembg`، `arabic_reshaper`، `bidi`، `requests`، `yt_dlp`


## مجلدات تتضاف للـ PATH

```
C:\Program Files\Blender Foundation\Blender 5.2
C:\Program Files\MKVToolNix
C:\Program Files\Inkscape\bin
C:\Users\cinde\AppData\Local\Programs\GIMP 3\bin
C:\Program Files\Upscayl\resources\bin
C:\Users\cinde\AppData\Local\Programs\Kdenlive\bin
C:\Users\cinde\AppData\Local\Programs\Natron\bin
C:\Program Files\Krita (x64)\bin
C:\Users\cinde\AppData\Local\Programs\darktable\bin
C:\Program Files\RawTherapee\5.13
C:\Program Files\7-Zip
C:\Users\cinde\AppData\Local\Pandoc
C:\Users\cinde\dragon-tools
C:\Users\cinde\dragon-tools\bin
C:\Users\cinde\AppData\Local\Microsoft\WinGet\Links
C:\Program Files\Google\Chrome\Application
C:\Program Files (x86)\Microsoft\Edge\Application
C:\Program Files\Mozilla Firefox
C:\Program Files\Tesseract-OCR
C:\Program Files\obs-studio\bin\64bit
C:\Program Files\HandBrake
C:\Users\cinde\AppData\Roaming\npm
C:\Users\cinde\AppData\Local\Microsoft\WinGet\Packages\aria2.aria2_Microsoft.Winget.Source_8wekyb3d8bbwe\aria2-1.37.0-win-64bit-build1
C:\Users\cinde\AppData\Local\Microsoft\WinGet\Packages\ch.LosslessCut_Microsoft.Winget.Source_8wekyb3d8bbwe
C:\Users\cinde\AppData\Local\Microsoft\WinGet\Packages\ch.LosslessCut_Microsoft.Winget.Source_8wekyb3d8bbwe\resources
C:\Users\cinde\AppData\Local\Microsoft\WinGet\Packages\DenoLand.Deno_Microsoft.Winget.Source_8wekyb3d8bbwe
C:\Users\cinde\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.2-full_build\bin
C:\Users\cinde\AppData\Local\Microsoft\WinGet\Packages\jqlang.jq_Microsoft.Winget.Source_8wekyb3d8bbwe
C:\Users\cinde\AppData\Local\Microsoft\WinGet\Packages\MediaArea.MediaInfo_Microsoft.Winget.Source_8wekyb3d8bbwe
C:\Users\cinde\AppData\Local\Microsoft\WinGet\Packages\sharkdp.fd_Microsoft.Winget.Source_8wekyb3d8bbwe\fd-v10.5.0-x86_64-pc-windows-msvc
C:\Users\cinde\AppData\Local\Microsoft\WinGet\Packages\SQLite.SQLite_Microsoft.Winget.Source_8wekyb3d8bbwe
C:\Users\cinde\AppData\Local\Microsoft\WinGet\Packages\yt-dlp.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-N-127043-g5a54fcf75e-win64-gpl\bin
C:\Users\cinde\AppData\Local\Microsoft\WinGet\Packages\yt-dlp.yt-dlp_Microsoft.Winget.Source_8wekyb3d8bbwe
C:\Program Files\ImageMagick-7.1.2-Q16-HDRI
```
