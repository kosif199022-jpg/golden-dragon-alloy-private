#!/usr/bin/env python3
"""Black Dragon — start door + machine map (v1990.3).

    dragon.py start                         # FIRST command when this package reaches Claude: what it is + the question to ask
    dragon.py tool machine ask              # the exact question for the owner: «على اللابتوب ولا لأ؟»
    dragon.py tool machine mode laptop|cloud|show   # record the owner's answer and print the matching playbook
    dragon.py tool machine map [--cat CAT] [--json] # every program/tool path recorded on the owner's laptop
    dragon.py tool machine find WORDS       # search the map (Arabic or English)
    dragon.py tool machine path ID          # one full path (for scripts)
    dragon.py tool machine re               # the reverse-engineering toolbox: id, path, example
    dragon.py tool machine env [--shell ps|bash]    # PATH lines so every program is callable by name
    dragon.py tool machine doctor           # laptop only: which recorded paths still exist
    dragon.py tool machine scan [--write]   # laptop only: rescan and (with --write) refresh machine_map.json + MACHINE_MAP.md
    dragon.py tool machine pc ACTION [--target T] [--text T] [--amount N] [--yes]   # laptop only: whole-PC control
    dragon.py tool machine app ACTION [--sid S] [--text T] [--wait N]               # laptop only: talk to the Black Dragon desktop app

The map is a record made on the owner's laptop. In a cloud chat those paths do not exist: `mode cloud` says what to use
instead. Nothing here installs, uploads or spends. `pc` actions that stop or remove something need --yes, which is written
only after the owner agrees in the chat.
"""
import argparse, importlib.util, json, os, platform, re, shutil, subprocess, sys, time, urllib.error, urllib.request
from datetime import datetime
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent.parent
MAP_FILE = HERE / "machine_map.json"
MAP_MD = SKILL / "references" / "MACHINE_MAP.md"
HOME = Path.home()
STATE = HOME / ".black-dragon" / "where.json"
DESKTOP_APP_SRC = SKILL / "app" / "apps" / "dragon_desktop"
IS_WIN = os.name == "nt"

QUESTION = ("قبل ما أبدأ: أنا شغّال دلوقتي على جهازك اللابتوب (Claude Code أو تطبيق التنين الأسود على ويندوز)، "
            "ولا في محادثة سحابية (claude.ai على الموبايل أو المتصفح)؟\n"
            "  A) على اللابتوب  ← هستخدم برامج الجهاز بمساراتها: Blender وffmpeg وأدوات الهندسة العكسية والتحكم في الكمبيوتر وتطبيق التنين.\n"
            "  B) مش على اللابتوب ← هشتغل بمحركات الحزمة نفسها في السحابة، ومش هعتمد على أي مسار من الجهاز.")

CATS = {"video": "فيديو ومونتاج", "image": "صور وتصميم", "audio": "صوت وتفريغ", "3d": "ثلاثي الأبعاد", "download": "تحميل",
        "docs": "مستندات وأرشيف وبحث", "dev": "برمجة وتشغيل", "ai": "واجهات الذكاء الاصطناعي", "browser": "متصفحات",
        "dragon": "أجزاء التنين الأسود", "re": "هندسة عكسية وتحليل", "pylib": "مكتبات بايثون"}

# id, category, what (Arabic), executable names to look for, example
PROGRAMS = [
    ("ffmpeg", "video", "قص وتجميع وترميز الفيديو والصوت", ["ffmpeg"], "ffmpeg -i in.mp4 -c:v libx264 -crf 17 out.mp4"),
    ("ffprobe", "video", "قياس الفيديو والصوت (مدة، أبعاد، فريمات)", ["ffprobe"], "ffprobe -v error -show_streams in.mp4"),
    ("blender", "3d", "Blender: تصميم ورندر 3D في الخلفية", ["blender"], "blender -b scene.blend -P script.py"),
    ("melt", "video", "محرك Kdenlive/MLT للمونتاج من سطر الأوامر", ["melt"], "melt in.mp4 -consumer avformat:out.mp4"),
    ("kdenlive", "video", "Kdenlive: مونتاج بواجهة", ["kdenlive"], ""),
    ("natron", "video", "Natron: كومبوزيتنج ورندر", ["NatronRenderer"], "NatronRenderer project.ntp"),
    ("mkvmerge", "video", "دمج وفصل مسارات MKV", ["mkvmerge"], "mkvmerge -o out.mkv in.mp4"),
    ("scenedetect", "video", "كشف القطعات في الفيديو", ["scenedetect"], "scenedetect -i in.mp4 detect-adaptive list-scenes"),
    ("auto-editor", "video", "قص السكتات تلقائي", ["auto-editor"], "auto-editor in.mp4 --margin 0.2sec"),
    ("handbrake", "video", "HandBrake: ترميز", ["HandBrakeCLI"], ""),
    ("obs", "video", "OBS: تسجيل الشاشة", ["obs64"], ""),
    ("magick", "image", "ImageMagick: تحويل وتعديل الصور", ["magick"], "magick in.png -resize 1080x1920 out.jpg"),
    ("gimp", "image", "GIMP في الخلفية", ["gimp-console-3.2", "gimp-console-3.0", "gimp-console"], "gimp-console-3.2 -i -b \"(…)\""),
    ("inkscape", "image", "Inkscape: فيكتور وSVG", ["inkscape"], "inkscape in.svg --export-type=png"),
    ("upscayl", "image", "تكبير الصور 4× بالذكاء الاصطناعي", ["upscayl-bin"], "upscayl-bin -i in.png -o out.png -s 4"),
    ("krita", "image", "Krita في الخلفية", ["kritarunner"], ""),
    ("darktable", "image", "darktable: تحميض RAW", ["darktable-cli"], "darktable-cli in.raw out.jpg"),
    ("rawtherapee", "image", "RawTherapee: تحميض RAW", ["rawtherapee-cli"], "rawtherapee-cli -o out.jpg -c in.raw"),
    ("rembg", "image", "شيل الخلفية من الصور", ["rembg"], "rembg i in.png out.png"),
    ("exiftool", "image", "قراية وتعديل بيانات الملفات (EXIF)", ["exiftool"], "exiftool file.jpg"),
    ("paint", "image", "الرسام (Windows Paint)", ["mspaint"], ""),
    ("whisperx", "audio", "تفريغ بتوقيت الكلمات", ["whisperx"], "whisperx audio.wav --language ar"),
    ("faster-whisper", "audio", "تفريغ سريع", ["faster-whisper", "whisper-ctranslate2"], ""),
    ("demucs", "audio", "فصل الصوت عن الموسيقى", ["demucs"], "demucs --two-stems=vocals song.mp3"),
    ("deep-filter", "audio", "تنضيف الصوت من الدوشة", ["deep-filter"], "deep-filter in.wav -o outdir"),
    ("edge-tts", "audio", "تحويل نص لصوت (أصوات مايكروسوفت)", ["edge-tts"], "edge-tts --voice ar-EG-SalmaNeural --text \"…\" --write-media out.mp3"),
    ("sox", "audio", "معالجة صوت", ["sox"], ""),
    ("audacity", "audio", "Audacity: تحرير صوت بواجهة", ["audacity"], ""),
    ("yt-dlp", "download", "تحميل فيديو من يوتيوب وتيك توك وانستجرام وغيرهم", ["yt-dlp"], "yt-dlp -f bv*+ba/b URL"),
    ("aria2c", "download", "تحميل مسرّع بتعدد اتصالات", ["aria2c"], "aria2c -x16 -s16 URL"),
    ("gallery-dl", "download", "تحميل ألبومات صور", ["gallery-dl"], ""),
    ("curl", "download", "طلبات HTTP وتحميل", ["curl"], ""),
    ("pandoc", "docs", "تحويل المستندات (Word/Markdown/HTML/PDF)", ["pandoc"], "pandoc in.docx -o out.md"),
    ("7z", "docs", "ضغط وفك كل الأرشيفات", ["7z"], "7z x archive.zip -oout"),
    ("jq", "docs", "قراية وتعديل JSON", ["jq"], "jq . file.json"),
    ("rg", "docs", "بحث سريع جوه الملفات (ripgrep)", ["rg"], "rg \"كلمة\" folder"),
    ("tesseract", "docs", "قراية النص من الصور (OCR)", ["tesseract"], "tesseract in.png out -l ara"),
    ("libreoffice", "docs", "LibreOffice في الخلفية (تحويل Office لـ PDF)", ["soffice"], "soffice --headless --convert-to pdf in.docx"),
    ("python", "dev", "بايثون الأساسي على الجهاز", ["python"], "python -X utf8 script.py"),
    ("node", "dev", "Node.js", ["node"], ""),
    ("npm", "dev", "مدير حزم Node", ["npm"], ""),
    ("git", "dev", "Git", ["git"], ""),
    ("gh", "dev", "GitHub CLI (المستخدم مسجّل بيها)", ["gh"], "gh repo list --limit 50"),
    ("winget", "dev", "مثبّت برامج ويندوز", ["winget"], "winget install -e --id <ID>  (بموافقة المستخدم)"),
    ("vscode", "dev", "VS Code", ["code"], ""),
    ("uv", "dev", "uv: مدير بيئات بايثون", ["uv"], ""),
    ("dotnet", "dev", ".NET SDK", ["dotnet"], ""),
    ("java", "dev", "Java (JDK)", ["java"], ""),
    ("powershell", "dev", "PowerShell", ["pwsh", "powershell"], ""),
    ("claude", "ai", "Claude Code CLI", ["claude"], "claude -p \"…\""),
    ("codex", "ai", "OpenAI Codex CLI (اشتراك ChatGPT)", ["codex"], ""),
    ("gemini", "ai", "Gemini CLI", ["gemini"], ""),
    ("ollama", "ai", "Ollama: موديلات محلية", ["ollama"], ""),
    ("chrome", "browser", "Google Chrome", ["chrome"], ""),
    ("edge", "browser", "Microsoft Edge", ["msedge"], ""),
    ("firefox", "browser", "Firefox", ["firefox"], ""),
]

# fixed places on the owner's laptop (written with {home}; resolved at scan time)
PLACES = [
    ("dragon-app", "dragon", "تطبيق التنين الأسود (ويندوز)", r"{local}\BlackDragon\BlackDragon.exe", "start \"\" \"<path>\""),
    ("dragon-repo", "dragon", "مستودع التنين الأسود (المحركات والكتالوج)", r"{home}\OneDrive\Desktop\التنين الأسود", "cd <path>; python -m dragon find \"…\""),
    ("dragon-app-source", "dragon", "كود تطبيق التنين (app.py، control.py، الواجهة)", r"{home}\OneDrive\Desktop\التنين الأسود\apps\dragon_desktop", ""),
    ("dragon-mcp", "dragon", "خادم MCP بتاع التنين (أدوات blackdragon_*)", r"{home}\OneDrive\Desktop\التنين الأسود\apps\dragon_desktop\mcp_dragon.py", ""),
    ("dragon-app-data", "dragon", "بيانات التطبيق: المحادثات والإعدادات", r"{roaming}\BlackDragon", ""),
    ("skills-dir", "dragon", "كل مهارات Claude المتثبتة", r"{home}\.claude\skills", ""),
    ("montage-dir", "dragon", "مجلد المونتاج", r"{home}\OneDrive\Desktop\المونتاج", ""),
    ("kosif-tool", "dragon", "مستودع KOSIF (سوبر باور 212 أداة)", r"{home}\kosif-tool", ""),
    ("superpowers-hub", "dragon", "باب سوبر باور", r"{home}\kosif-tool\.claude\skills\kosif-superpowers\scripts\hub.py", "python <path> find \"…\""),
    ("dragon-tools", "dragon", "أدوات مساعدة (fast_dl.py وغيره)", r"{home}\dragon-tools", ""),
    ("fast-dl", "download", "تحميل سريع", r"{home}\dragon-tools\fast_dl.py", "python <path> URL"),
    ("dragon-repos", "dragon", "مستودعات المونتاج المحمّلة (video-use، hyperframes، whisperX…)", r"{home}\dragon-repos", ""),
    ("re-tools", "re", "صندوق أدوات الهندسة العكسية", r"{home}\re-tools", ""),
    ("retool", "re", "باب صندوق الهندسة العكسية", r"{home}\re-tools\retool.py", "python <path> triage FILE --deep"),
    ("omni", "re", "المحلل الشامل: تعرّف وخطة تحليل لأي هدف", r"{home}\.claude\skills\omni-analyst\scripts\omni.py", "python -X utf8 <path> classify TARGET"),
    ("rea-digest", "re", "تلخيص نواتج REA الكبيرة", r"{home}\.claude\skills\rea-ultra\scripts\rea_digest.py", "python <path> FILE --grep كلمة"),
    ("antigravity", "ai", "Google Antigravity", r"{local}\Programs\antigravity\Antigravity.exe", ""),
    ("claude-desktop", "ai", "تطبيق Claude لسطح المكتب", r"shell:AppsFolder\Claude_pzs8sxrjxfjjc!Claude", ""),
]

PYLIBS = ["numpy", "cv2", "mediapipe", "librosa", "moviepy", "PIL", "torch", "playwright", "pptx", "docx", "openpyxl", "pymupdf",
          "pydub", "soundfile", "pyloudnorm", "faster_whisper", "scenedetect", "rembg", "arabic_reshaper", "bidi", "requests", "yt_dlp"]

EXTRA_DIRS = [r"C:\Program Files\Blender Foundation\Blender 5.2", r"C:\Program Files\MKVToolNix", r"C:\Program Files\Inkscape\bin",
              r"{local}\Programs\GIMP 3\bin", r"C:\Program Files\Upscayl\resources\bin", r"{local}\Programs\Kdenlive\bin",
              r"C:\Program Files\Natron\bin", r"{local}\Programs\Natron\bin", r"C:\Program Files\Krita (x64)\bin",
              r"{local}\Programs\darktable\bin", r"C:\Program Files\RawTherapee\5.13", r"C:\Program Files\7-Zip", r"{local}\Pandoc",
              r"C:\Program Files\Pandoc", r"{home}\dragon-tools", r"{home}\dragon-tools\bin", r"{local}\Microsoft\WinGet\Links",
              r"C:\Program Files\Google\Chrome\Application", r"C:\Program Files (x86)\Microsoft\Edge\Application",
              r"C:\Program Files\Mozilla Firefox", r"C:\Program Files\LibreOffice\program", r"C:\Program Files\Tesseract-OCR",
              r"C:\Program Files\Audacity", r"C:\Program Files\obs-studio\bin\64bit", r"C:\Program Files\HandBrake",
              r"C:\Program Files\ImageMagick", r"{roaming}\npm"]


def _fill(s):
    return (s.replace("{home}", str(HOME)).replace("{local}", os.environ.get("LOCALAPPDATA", str(HOME / "AppData" / "Local")))
            .replace("{roaming}", os.environ.get("APPDATA", str(HOME / "AppData" / "Roaming"))))


def extra_path_dirs():
    dirs = [Path(_fill(d)) for d in EXTRA_DIRS]
    pk = Path(_fill(r"{local}\Microsoft\WinGet\Packages"))
    if pk.is_dir():
        dirs += sorted({f.parent for f in pk.glob("*/*.exe")} | {f.parent for f in pk.glob("*/*/*.exe")} | {f.parent for f in pk.glob("*/*/bin/*.exe")})
    for g in ("C:/Program Files/ImageMagick*", "C:/Program Files/Blender Foundation/Blender*", "C:/Program Files/RawTherapee/*"):
        dirs += [Path(p) for p in sorted(map(str, Path(g).parent.glob(Path(g).name)))] if Path(g).parent.is_dir() else []
    return [d for d in dict.fromkeys(dirs) if d.is_dir()]


def load_map():
    try:
        return json.loads(MAP_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"schema": "black-dragon.machine-map.v1", "scanned": None, "items": [], "path_dirs": [], "pylibs": {}}


def on_owner_laptop():
    """Evidence only (the owner's answer decides): Windows + the recorded home + at least one Black Dragon place present."""
    m = load_map()
    if os.environ.get("DRAGON_MODE") == "cloud":
        return False, "DRAGON_MODE=cloud"
    if not IS_WIN:
        return False, f"النظام {platform.system()} مش ويندوز"
    rec = m.get("home")
    here = sum(1 for i in m.get("items", []) if i["cat"] == "dragon" and i.get("path") and Path(i["path"]).exists())
    if rec and Path(rec) == HOME and here:
        return True, f"ويندوز، ونفس مجلد المستخدم المسجّل، و{here} من أماكن التنين موجودة"
    if here:
        return True, f"ويندوز، و{here} من أماكن التنين موجودة"
    return False, "ويندوز، بس أماكن التنين المسجّلة مش موجودة هنا (جهاز تاني؟)"


def evidence():
    cloud_marks = [p for p in ("/mnt/user-data", "/mnt/skills") if Path(p).exists()]
    if os.environ.get("CLAUDE_CODE_REMOTE") == "true":
        cloud_marks.append("CLAUDE_CODE_REMOTE=true")
    lap, why = on_owner_laptop()
    return {"os": platform.system(), "looks_like_laptop": lap, "why": why, "cloud_marks": cloud_marks,
            "inside_dragon_app": bool(os.environ.get("BD_IN_APP")), "python": sys.version.split()[0]}


# ------------------------------------------------------------------------------------------------------------ scan
def scan():
    dirs = extra_path_dirs()
    path = os.pathsep.join([os.environ.get("PATH", "")] + [str(d) for d in dirs])
    items = []
    for pid, cat, what, exes, example in PROGRAMS:
        found = next((w for w in (shutil.which(e, path=path) for e in exes) if w), None)
        items.append({"id": pid, "cat": cat, "what": what, "call": exes[0] if found is None else Path(found).stem, "path": found, "example": example})
    for pid, cat, what, p, example in PLACES:
        full = _fill(p)
        ok = full.startswith("shell:") or Path(full).exists()
        items.append({"id": pid, "cat": cat, "what": what, "call": "", "path": full if ok else None, "example": example.replace("<path>", full)})
    retool = HOME / "re-tools" / "retool.py"
    if retool.is_file():
        try:
            r = subprocess.run([sys.executable, "-X", "utf8", str(retool), "list", "--json"], capture_output=True, text=True, encoding="utf-8",
                               errors="replace", timeout=60)
            for t in json.loads(r.stdout):
                exe = t.get("exe") or ""
                items.append({"id": "re:" + t["id"], "cat": "re", "what": f"{t.get('name', t['id'])} ({t.get('kind', '')}): {t.get('what_ar', '')}",
                              "call": f"retool run {t['id']}", "path": exe if exe and Path(exe).exists() else None,
                              "example": t.get("example") or f"python \"{retool}\" run {t['id']} <args>", "gui": "واجهة" in (t.get("kind") or "")})
        except Exception as e:
            print(f"retool list failed: {e}", file=sys.stderr)
    libs = {m: bool(importlib.util.find_spec(m)) for m in PYLIBS}
    return {"schema": "black-dragon.machine-map.v1", "scanned": datetime.now().isoformat(timespec="seconds"), "host_os": platform.platform(),
            "home": str(HOME), "python": sys.executable, "items": items, "path_dirs": [str(d) for d in dirs], "pylibs": libs}


def write_md(m):
    lines = ["# خريطة جهاز صاحب التنين (MACHINE_MAP)", "",
             f"اتسجّلت بالفحص الفعلي يوم {m.get('scanned')} على `{m.get('host_os')}`، ومجلد المستخدم `{m.get('home')}`.",
             "", "**المسارات دي موجودة على اللابتوب بس.** في محادثة سحابية ماتستخدمهاش: اشتغل بمحركات الحزمة (`dragon.py tool machine mode cloud`).",
             "للتحديث على الجهاز: `python scripts/dragon.py tool machine scan --write`. للتأكد إن المسارات لسه موجودة: `tool machine doctor`.", ""]
    for cat, title in CATS.items():
        rows = [i for i in m["items"] if i["cat"] == cat]
        if cat == "pylib":
            ok = [k for k, v in m.get("pylibs", {}).items() if v]
            no = [k for k, v in m.get("pylibs", {}).items() if not v]
            lines += [f"## {title}", "", "متثبتة في بايثون الأساسي: " + ("، ".join(f"`{x}`" for x in ok) or "—"),
                      ("مش متثبتة: " + "، ".join(f"`{x}`" for x in no)) if no else "", ""]
            continue
        if not rows:
            continue
        lines += [f"## {title}", "", "| الاسم | بيعمل إيه | المسار | مثال |", "|---|---|---|---|"]
        for i in rows:
            p = f"`{i['path']}`" if i.get("path") else "✗ مش موجود وقت الفحص"
            lines.append(f"| `{i['id']}` | {i['what']} | {p} | {('`' + i['example'] + '`') if i.get('example') else ''} |")
        lines.append("")
    lines += ["## مجلدات تتضاف للـ PATH", "", "```"] + m.get("path_dirs", []) + ["```", ""]
    MAP_MD.write_text("\n".join(lines), encoding="utf-8")


# ------------------------------------------------------------------------------------------------------------ playbooks
def playbook(mode):
    m = load_map()
    n_ok = sum(1 for i in m["items"] if i.get("path"))
    n_re = sum(1 for i in m["items"] if i["cat"] == "re" and i.get("path"))
    D = "python scripts/dragon.py"
    if mode == "laptop":
        lap, why = on_owner_laptop()
        if not lap:
            return ("⚠ صاحب التنين قال «على اللابتوب»، بس الدليل هنا بيقول غير كده: " + why + ".\n"
                    "قوله ده بصراحة في سطر واحد، واعرض عليه طريقين:\n"
                    "  1) يفتح نفس الطلب من Claude Code أو تطبيق التنين الأسود على اللابتوب (هناك كل المسارات شغالة).\n"
                    "  2) تكمّل هنا بمحركات الحزمة، وأي خطوة محتاجة برنامج من الجهاز تكتبها أمر جاهز (PowerShell) يشغّله هو هناك:\n"
                    f"     المسارات في references/MACHINE_MAP.md و`{D} tool machine path <id>`.\n"
                    "ماتدّعيش إن أمر اتنفّذ على جهازه وهو ماتنفّذش.")
        return "\n".join([
            f"✅ وضع اللابتوب ({why}). المسجّل: {n_ok} برنامج ومكان، منهم {n_re} للهندسة العكسية.",
            "الترتيب:",
            f"  1) {D} tool machine doctor            ← أنهي مسار لسه موجود",
            f"  2) {D} tool machine env --shell ps    ← سطر PATH عشان كل البرامج تتنادى باسمها",
            f"  3) {D} where ثم {D} doctor            ← محرك التنين والبرامج",
            f"  4) {D} tool brain \"<الطلب>\"          ← الأدوات والمهارات والدروس المناسبة",
            "اللي متاح هنا ومش متاح في السحابة:",
            "  • Blender 5.2 محلي، وyt-dlp بكوكيز المتصفح، وwhisperx/demucs/rembg/upscayl، وكل برامج references/MACHINE_MAP.md.",
            f"  • الهندسة العكسية كاملة: {D} tool re plan|investigate|audit FILE، و{D} tool machine re للمسارات، وأدوات mcp__rea__* لو متوصلة.",
            f"  • التحكم في الكمبيوتر كله: {D} tool machine pc info|processes|apps|launch|volume|brightness|settings|… (الخطير بـ --yes بعد موافقته).",
            f"  • تطبيق التنين: {D} tool machine app status|chats|read|send|ask (أو أداة blackdragon_app لو خادم black-dragon متسجّل في Claude Code).",
            "  • مهارات Claude Code المتثبتة (Skill)، والوكلاء (Task/Agent)، وClaude in Chrome، وخوادم MCP: القايمة في references/CLAUDE_AND_APP_POWERS_V19903.md.",
            "القواعد زي ما هي: فولدر شغل اسمه إنجليزي برّه OneDrive، الأصل مايتعدّلش، ومفيش صرف ولا نشر ولا تثبيت من غير «موافق».",
        ])
    return "\n".join([
        "☁ وضع السحابة: مفيش مسار من الجهاز هيشتغل هنا، فماتكتبش `C:\\Users\\…` في أي أمر.",
        "الترتيب:",
        f"  1) {D} where ثم {D} setup            ← setup عرض بس؛ التثبيت بـ --yes بعد موافقته",
        f"  2) {D} tool brain \"<الطلب>\"         ← الأدوات والمهارات والدروس المناسبة",
        f"  3) محركات الحزمة: {D} run dragon_montage …، {D} film …، {D} mux/verify …، وأدوات tool (framecheck، critic، onscreen، tags، hf…).",
        "بدائل اللي ناقص:",
        "  • Blender المحلي ← 3D Jutsu المستضاف لو Higgsfield متوصل (`tool hf blender rules`)، وإلا stills + حركة بالكود.",
        "  • يوتيوب/تيك توك غالبًا مقفولين ← اطلب منه يرفع الملف (سطر واحد)، من غير تحايل.",
        "  • GPU (whisperx/demucs) ← faster-whisper على CPU، أو sandbox بتاع Higgsfield بـ size:xl لو متوصل.",
        f"  • الهندسة العكسية ← التحليل الساكن اللي جوه الحزمة بس: {D} tool re plan|audit FILE، و{D} tool omni classify|probe، و{D} tool rea-ultra triage.",
        "    Ghidra وjadx وfrida وباقي الصندوق على اللابتوب: اكتبله الأمر الجاهز من references/MACHINE_MAP.md يشغّله هناك لو محتاجهم.",
        "  • التحكم في الكمبيوتر وتطبيق التنين ← مش متاحين من السحابة. قول كده بصراحة.",
        "الملفات: المرفوع في /mnt/user-data/uploads، والتسليم في /mnt/user-data/outputs (أو SendUserFile في جلسة Claude Code السحابية).",
    ])


def cmd_start(a):
    ev = evidence()
    saved = None
    try:
        saved = json.loads(STATE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass
    ver = "?"
    mt = re.search(r"\(v([\w.]+)", (SKILL / "SKILL.md").read_text(encoding="utf-8", errors="replace")[:4000])
    if mt:
        ver = mt.group(1)
    n_tools = "?"
    try:
        src = (SKILL / "scripts" / "dragon.py").read_text(encoding="utf-8")
        n_tools = len(re.findall(r'^    "[\w-]+": "', src, re.M))
    except OSError:
        pass
    m = load_map()
    out = {"package": "Black Dragon — التنين الأسود", "version": ver, "skill_dir": str(SKILL), "tools_registered": n_tools,
           "bundled_skills": sorted(p.name for p in (SKILL / "skills").iterdir() if p.is_dir()) if (SKILL / "skills").is_dir() else [],
           "evidence": ev, "machine_map": {"scanned": m.get("scanned"), "entries": len(m.get("items", [])),
                                           "found": sum(1 for i in m.get("items", []) if i.get("path"))},
           "saved_answer": saved}
    if a.json:
        print(json.dumps(out, ensure_ascii=False, indent=1)); return 0
    print(f"🐉 التنين الأسود v{ver} — مونتير ومخرج Mahmoud Elkosif: {n_tools} أداة، و{len(out['bundled_skills'])} مهارة متضمّنة.")
    print(f"   مكان الحزمة: {SKILL}")
    print(f"   الدليل هنا: النظام {ev['os']} · {ev['why']}" + (f" · علامات سحابة: {', '.join(ev['cloud_marks'])}" if ev["cloud_marks"] else "")
          + (" · جوه تطبيق التنين" if ev["inside_dragon_app"] else ""))
    print(f"   خريطة الجهاز: {out['machine_map']['found']} مسار متسجّل (فحص {m.get('scanned')}).")
    print()
    print("⛔ أول خطوة قبل أي شغل: اسأل صاحب التنين السؤال ده بالنص واستنى رده (حتى لو الدليل واضح، القرار قراره):")
    print()
    print(QUESTION)
    print()
    print("بعد رده:  A ← python scripts/dragon.py tool machine mode laptop     B ← python scripts/dragon.py tool machine mode cloud")
    if saved:
        print(f"(آخر إجابة متسجّلة على الجهاز ده: {saved.get('mode')} بتاريخ {saved.get('at')}. دي محادثة جديدة، فاسأل تاني.)")
    print("وبعدها اقرا SKILL.md (القواعد والبروتوكول) قبل أي فيلم، وreferences/CLAUDE_AND_APP_POWERS_V19903.md لقايمة القدرات في كل مكان.")
    return 0


def cmd_mode(a):
    if a.which == "show":
        try:
            print(STATE.read_text(encoding="utf-8"))
        except OSError:
            print("لسه مفيش إجابة متسجّلة. اسأل: python scripts/dragon.py tool machine ask")
        return 0
    try:
        STATE.parent.mkdir(parents=True, exist_ok=True)
        STATE.write_text(json.dumps({"mode": a.which, "at": datetime.now().isoformat(timespec="seconds"), "evidence": evidence()},
                                    ensure_ascii=False, indent=1), encoding="utf-8")
    except OSError as e:
        print(f"(مقدرتش أحفظ الإجابة: {e})", file=sys.stderr)
    print(playbook(a.which))
    return 0


def cmd_map(a):
    m = load_map()
    items = [i for i in m["items"] if not a.cat or i["cat"] == a.cat]
    if a.json:
        print(json.dumps({**m, "items": items}, ensure_ascii=False, indent=1)); return 0
    print(f"خريطة الجهاز (فحص {m.get('scanned')}، {m.get('home')}). المسارات دي على اللابتوب بس.")
    for cat, title in CATS.items():
        rows = [i for i in items if i["cat"] == cat]
        if rows:
            print(f"\n## {title}")
            for i in rows:
                print(f"  {'✓' if i.get('path') else '✗'} {i['id']:<22} {i.get('path') or '(مش موجود وقت الفحص)'}")
    if not a.cat:
        print("\n## مكتبات بايثون: " + " ".join(k for k, v in m.get("pylibs", {}).items() if v))
    return 0


AR = {"blender": "بلندر", "ffmpeg": "اف اف امبيج مونتاج قص", "gimp": "جيمب", "inkscape": "انكسكيب", "chrome": "كروم", "edge": "ايدج",
      "firefox": "فايرفوكس", "magick": "ايمدج ماجيك", "re:ghidra": "جيدرا", "re:frida": "فريدا", "re:jadx": "جادكس apk", "python": "بايثون",
      "krita": "كريتا", "yt-dlp": "يوتيوب تيك توك انستجرام تنزيل", "upscayl": "تكبير", "paint": "الرسام", "claude": "كلود", "7z": "فك ضغط zip rar",
      "dragon-app": "التطبيق", "whisperx": "تفريغ ويسبر", "demucs": "فصل الموسيقى", "pandoc": "وورد word pdf"}


def cmd_find(a):
    q = [w.lower() for w in a.words]
    hits = [i for i in load_map()["items"] if all(w in (i["id"] + " " + i["what"] + " " + (i.get("path") or "") + " " + CATS.get(i["cat"], "") + " " +
                                                         AR.get(i["id"], "")).lower() for w in q)]
    for i in hits[:40]:
        print(f"{'✓' if i.get('path') else '✗'} {i['id']} [{CATS.get(i['cat'], i['cat'])}] — {i['what']}\n    {i.get('path') or '(مش موجود)'}" +
              (f"\n    مثال: {i['example']}" if i.get("example") else ""))
    if not hits:
        print("مفيش حاجة بالكلمات دي في خريطة الجهاز. جرّب: python scripts/dragon.py find \"…\" (كتالوج التنين).")
    return 0 if hits else 1


def cmd_path(a):
    for i in load_map()["items"]:
        if i["id"] in (a.id, "re:" + a.id) and i.get("path"):
            print(i["path"]); return 0
    print(f"مفيش مسار متسجّل لـ {a.id}", file=sys.stderr)
    return 1


def cmd_re(a):
    m = load_map()
    rows = [i for i in m["items"] if i["cat"] == "re"]
    if a.json:
        print(json.dumps(rows, ensure_ascii=False, indent=1)); return 0
    print("أدوات الهندسة العكسية على اللابتوب (لملفات المستخدم بس، للفهم والفحص، مش لكسر حماية أو تخطّي ترخيص):")
    for i in rows:
        print(f"  {'✓' if i.get('path') else '✗'} {i['id'].replace('re:', ''):<16} {i['what'][:74]}\n      {i.get('path') or '(مش موجود)'}" +
              (f"\n      مثال: {i['example']}" if i.get("example") else ""))
    print("\nالترتيب: tool re plan FILE ← tool re investigate FILE --out DIR ← الأداة المناسبة للنوع ← تقرير (دليل / استنتاج / مجهول).")
    print("أدوات وقت التشغيل (frida، pe-sieve، x64dbg، mitmdump، adb) بتستنى موافقة صريحة.")
    return 0


def cmd_env(a):
    dirs = load_map().get("path_dirs", [])
    if a.shell == "bash":
        def b(d):
            d = d.replace("\\", "/")
            return "/" + d[0].lower() + d[2:] if len(d) > 1 and d[1] == ":" else d
        print('export PATH="$PATH:' + ":".join(b(d) for d in dirs) + '"')
    else:
        print("$env:PATH += ';" + ";".join(dirs) + "'")
    return 0


def cmd_doctor(a):
    lap, why = on_owner_laptop()
    m = load_map()
    if not IS_WIN:
        print(f"doctor بيتأكد من مسارات اللابتوب، وهنا {platform.system()}: {why}. استخدم `tool machine mode cloud`.")
        return 3
    bad = [i for i in m["items"] if i.get("path") and not i["path"].startswith("shell:") and not Path(i["path"]).exists()]
    ok = sum(1 for i in m["items"] if i.get("path")) - len(bad)
    print(f"{ok} مسار موجود، {len(bad)} اختفى، {sum(1 for i in m['items'] if not i.get('path'))} ماكانش موجود وقت الفحص ({m.get('scanned')}).")
    for i in bad:
        print(f"  ✗ {i['id']}: {i['path']}")
    if bad:
        print("حدّث الخريطة: python scripts/dragon.py tool machine scan --write")
    return 1 if bad else 0


def cmd_scan(a):
    if not IS_WIN:
        print("scan بيتشغّل على اللابتوب (ويندوز) بس.", file=sys.stderr); return 3
    m = scan()
    found = sum(1 for i in m["items"] if i.get("path"))
    print(f"scan: {found} موجود من {len(m['items'])}، و{sum(m['pylibs'].values())} مكتبة بايثون، و{len(m['path_dirs'])} مجلد PATH.")
    if a.write:
        MAP_FILE.write_text(json.dumps(m, ensure_ascii=False, indent=1), encoding="utf-8")
        write_md(m)
        print(f"اتكتب: {MAP_FILE}\n        {MAP_MD}")
    else:
        print("عرض بس. زوّد --write عشان الخريطة تتحدّث.")
    return 0


def cmd_pc(a):
    lap, why = on_owner_laptop()
    if not lap:
        print(f"التحكم في الكمبيوتر بيشتغل على لابتوب صاحب التنين بس ({why}).", file=sys.stderr); return 3
    src = next((p for p in (DESKTOP_APP_SRC, HOME / "OneDrive" / "Desktop" / "التنين الأسود" / "apps" / "dragon_desktop", HOME / "OneDrive" / "Desktop" / "مهارات" / "التنين الأسود" / "apps" / "dragon_desktop") if (p / "control.py").is_file()), None)
    if not src:
        print("control.py مش موجود (app/apps/dragon_desktop).", file=sys.stderr); return 2
    sys.path.insert(0, str(src))
    import control
    s = control.System()
    if a.action in ("list", "help"):
        print("actions: " + ", ".join(s.ACTIONS) + "\nمحتاجة --yes بعد موافقة المستخدم: " + ", ".join(sorted(s.DANGER))); return 0
    if a.action in s.DANGER and not a.yes:
        print(f"«{s.describe(a.action, {'target': a.target, 'text': a.text})}» فعل بيوقف أو يغيّر حاجة في الجهاز. "
              f"اسأل المستخدم في الشات، ولو وافق أعد الأمر بـ --yes.", file=sys.stderr)
        return 3
    args = {k: v for k, v in (("target", a.target), ("text", a.text), ("amount", a.amount)) if v is not None}
    out, err = s.run(a.action, args)
    print(out)
    return 1 if err else 0


def cmd_app(a):
    lap, why = on_owner_laptop()
    if not lap:
        print(f"تطبيق التنين على لابتوب صاحبه بس ({why}).", file=sys.stderr); return 3
    try:
        token = json.loads((Path(os.environ.get("APPDATA", HOME)) / "BlackDragon" / "settings.json").read_text(encoding="utf-8")).get("bridge_token", "")
    except (OSError, ValueError):
        token = ""

    def call(payload, timeout=30):
        req = urllib.request.Request(f"http://127.0.0.1:47821/app?t={token}", data=json.dumps(payload).encode("utf-8"),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    payload = {k: v for k, v in (("sid", a.sid), ("text", a.text)) if v}
    try:
        if a.action != "ask":
            r = call({"action": a.action, **payload})
        else:
            r = call({"action": "send", **payload})
            if r.get("ok"):
                sid, end = r["sid"], time.time() + a.wait
                time.sleep(1.5)
                while True:
                    r = call({"action": "reply", "sid": sid})
                    if not r.get("ok") or not r.get("busy") or time.time() > end:
                        break
                    time.sleep(2)
    except urllib.error.HTTPError as e:
        print(f"HTTP {e.code}: نسخة التطبيق المفتوحة قديمة ومفيهاش الربط. حدّث التطبيق.", file=sys.stderr); return 1
    except (urllib.error.URLError, OSError):
        print("تطبيق التنين الأسود مش مفتوح. افتحه وجرّب تاني: python scripts/dragon.py tool machine path dragon-app", file=sys.stderr); return 1
    print(json.dumps(r, ensure_ascii=False, indent=1))
    return 0 if r.get("ok") else 1


def main(argv=None):
    ap = argparse.ArgumentParser(prog="dragon.py tool machine", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd")
    p = sub.add_parser("start"); p.add_argument("--json", action="store_true"); p.set_defaults(fn=cmd_start)
    p = sub.add_parser("ask"); p.set_defaults(fn=lambda a: (print(QUESTION), 0)[1])
    p = sub.add_parser("mode"); p.add_argument("which", choices=["laptop", "cloud", "show"]); p.set_defaults(fn=cmd_mode)
    p = sub.add_parser("map"); p.add_argument("--cat", choices=list(CATS)); p.add_argument("--json", action="store_true"); p.set_defaults(fn=cmd_map)
    p = sub.add_parser("find"); p.add_argument("words", nargs="+"); p.set_defaults(fn=cmd_find)
    p = sub.add_parser("path"); p.add_argument("id"); p.set_defaults(fn=cmd_path)
    p = sub.add_parser("re"); p.add_argument("--json", action="store_true"); p.set_defaults(fn=cmd_re)
    p = sub.add_parser("env"); p.add_argument("--shell", choices=["ps", "bash"], default="ps"); p.set_defaults(fn=cmd_env)
    p = sub.add_parser("doctor"); p.set_defaults(fn=cmd_doctor)
    p = sub.add_parser("scan"); p.add_argument("--write", action="store_true"); p.set_defaults(fn=cmd_scan)
    p = sub.add_parser("pc"); p.add_argument("action"); p.add_argument("--target"); p.add_argument("--text"); p.add_argument("--amount", type=int)
    p.add_argument("--yes", action="store_true"); p.set_defaults(fn=cmd_pc)
    p = sub.add_parser("app"); p.add_argument("action", choices=["status", "chats", "read", "send", "ask", "reply", "stop"])
    p.add_argument("--sid"); p.add_argument("--text"); p.add_argument("--wait", type=int, default=600); p.set_defaults(fn=cmd_app)
    a = ap.parse_args(argv)
    if not a.cmd:
        ap.print_help(); return 2
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
