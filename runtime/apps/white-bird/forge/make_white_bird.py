"""make_white_bird.py — builds the source of «الطائر الأبيض» (White Bird) from the Black Dragon desktop app.

The Black Dragon app (apps/dragon_desktop) stays untouched. This script copies it into ..\\app and applies:
  1. its own identity: name, window/mutex, settings folder, update staging, install folder, Chrome-bridge port, extension
  2. the Apple design layer (overlay/white-bird.css) + bundled fonts (Noto Sans Arabic, Inter: OFL) + the white bird icon
  3. Spotlight (overlay/spotlight.js, Ctrl+K) and the «بروتوكول الطائر الأبيض» reasoning section in the system prompt
  4. a test gate at the top of build.ps1: ..\\tests\\run_tests.ps1 must pass before anything is built (-SkipTests skips it)
Every patch checks how many times its anchor occurs, so a changed Black Dragon source stops the script instead of
producing a half-patched app.

  python -X utf8 make_white_bird.py            regenerate ..\\app (refuses if app\\ was edited by hand; --force overrides)
  python -X utf8 make_white_bird.py --seed     also copy settings + chats from %APPDATA%\\BlackDragon once (never overwrites)
"""
import hashlib, json, os, re, shutil, sys, time
from pathlib import Path

FORGE = Path(__file__).resolve().parent
WB = FORGE.parent                                   # ...\Desktop\الطائر الأبيض
OUT = WB / "app"
OV = FORGE / "overlay"
DESK = WB.parent
SRC = Path(os.environ.get("BLACK_DRAGON_HOME", DESK / "التنين الأسود")) / "apps" / "dragon_desktop"
STAMP = OUT / ".wb_generated.json"
UNTRACKED = {"ui/version.txt", ".wb_generated.json"}          # build.ps1 stamps version.txt on every build
PORT_OLD, PORT_NEW = "47821", "47831"
log = []


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def sub(text, old, new, count=1, name=""):
    n = text.count(old)
    if (count is None and n == 0) or (count is not None and n != count):
        raise SystemExit(f"✗ {name}: expected {count if count is not None else '≥1'} × {old[:70]!r}, found {n}")
    log.append(f"  {name}: {n}×")
    return text.replace(old, new)


def resub(text, pattern, new, name="", minimum=1):
    out, n = re.subn(pattern, new, text)
    if n < minimum:
        raise SystemExit(f"✗ {name}: pattern {pattern!r} matched {n}×")
    log.append(f"  {name}: {n}×")
    return out


def guard(force):
    if not OUT.exists() or force:
        return
    if not STAMP.exists():
        raise SystemExit(f"✗ {OUT} موجود ومش متولّد بالسكربت ده. شغّل بـ --force لو متأكد إنك عايز تكتب فوقه.")
    rec = json.loads(STAMP.read_text(encoding="utf-8"))["files"]
    changed = [p for p, h in rec.items() if not (OUT / p).exists() or sha(OUT / p) != h]
    now = {p.relative_to(OUT).as_posix() for p in OUT.rglob("*") if p.is_file() and "__pycache__" not in p.parts}
    added = sorted(now - set(rec) - UNTRACKED)
    if changed or added:
        raise SystemExit("✗ فيه تعديلات يدوية في app\\ بعد آخر توليد (هتضيع لو كتبت فوقها):\n  " +
                         "\n  ".join(changed + added) + "\nانقلها لـ forge\\overlay أو شغّل بـ --force.")


def write(p, text):
    Path(p).write_text(text, encoding="utf-8", newline="")


# ---------------------------------------------------------------- app.py
SYSTEM_PROTOCOL = """
## بروتوكول الطائر الأبيض (الذكاء الفائق)
- **ابدأ من الآخر:** قبل أول أداة، اكتب لنفسك في سطر شكل التسليم المثالي: الملف، ومكانه، والمقياس اللي هيثبت إنه صح.
- **تشريح قبل الفشل:** تخيّل إن التسليم رجع مرفوض. إيه أرجح 3 أسباب؟ اقفل كل سبب بخطوة أو فحص جوه الخطة.
- **وازي:** الأجزاء المستقلة (قراية ملفات، قياسات، بحث، رندر مقاطع) تتعمل مع بعض في نفس الرسالة أو على الوكلاء، مش ورا بعض.
- **أقل سؤال، أكتر تحقق:** اللي تقدر تعرفه من الملفات أو بأمر، اعرفه بنفسك بدل ما تسأل.
- **ناقد داخلي:** قبل «خلص»، اقرا الناتج بعين ناقد صارم: إيه أضعف حاجة فيه؟ صلّحها لو التصليح رخيص، أو قولها بصراحة.
- **أسلوب Apple في الرد:** النتيجة في أول سطر، وبعدها أقل كلام يوصّل المعنى. كل جملة ليها لازمة، ومفيش حشو ولا تكرار.
"""

WB_BG = '''def _wb_bg():
    """Window color before the page paints: follows the Windows app theme (light = the White Bird's home look)."""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize") as k:
            return "#f5f5f7" if winreg.QueryValueEx(k, "AppsUseLightTheme")[0] else "#161618"
    except Exception:
        return "#f5f5f7"


def _wb_life(msg):
    """Black box: one line per start / close / crash in %APPDATA%\\\\WhiteBird\\\\run\\\\lifecycle.log, so «the window went away»
    always has an answer (closed with ✕, closed for an update, crashed, or killed from outside = a start with no end)."""
    try:
        f = SETTINGS.parent / "run" / "lifecycle.log"
        f.parent.mkdir(parents=True, exist_ok=True)
        with open(f, "a", encoding="utf-8") as h:
            h.write(time.strftime("%Y-%m-%d %H:%M:%S") + f" pid={os.getpid()} v={VERSION} {msg}\\n")
    except Exception:
        pass


def _wb_seed():
    """First run on this PC (outside Claude Desktop's sandbox): bring the White Bird data that a session inside Claude
    Desktop wrote into its package cache, else start from the Black Dragon's settings + chats. Copies; sources stay."""
    dst = SETTINGS.parent
    if SETTINGS.exists():
        return
    try:
        cache = sorted((Path(os.environ.get("LOCALAPPDATA", "")) / "Packages").glob("Claude_*/LocalCache/Roaming/WhiteBird/settings.json"))
        src = cache[0].parent if cache else dst.parent / "BlackDragon"
        if not (src / "settings.json").exists():
            return
        dst.mkdir(parents=True, exist_ok=True)
        for name in ("chats", "chat_library"):
            if (src / name).is_dir() and not (dst / name).exists():
                shutil.copytree(src / name, dst / name)
        d = json.loads((src / "settings.json").read_text(encoding="utf-8-sig"))
        if src.name == "BlackDragon":
            for k in ("spent", "balance", "balance_at"):
                d.pop(k, None)
        SETTINGS.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")   # last: a half copy retries
        _wb_life(f"first run: settings + chats copied from {src}")
    except Exception as e:
        _wb_life(f"first-run copy skipped: {e!r}")


def main():'''

WB_START_OLD = '''    api._window = win
    webview.start(api._wire_drop, debug=bool(os.environ.get("DRAGON_DEBUG")))'''
WB_START_NEW = '''    api._window = win
    _wb_life("start")
    try:
        import faulthandler
        _wb_life.faults = open(SETTINGS.parent / "run" / "faults.log", "a", encoding="utf-8")
        faulthandler.enable(_wb_life.faults, all_threads=True)
    except Exception:
        pass
    try:
        win.events.closing += lambda: _wb_life("closing: window closed (✕ / Alt+F4 / update)")
    except Exception:
        pass
    try:
        webview.start(api._wire_drop, debug=bool(os.environ.get("DRAGON_DEBUG")))
        _wb_life("closed for an update" if getattr(api, "_updating", False) else "closed normally")
    except BaseException as e:
        _wb_life(f"crashed: {e!r}")
        raise'''



# Safety guard for the two bird apps generated from the desktop source (Red Dragon security hotfix, 2026-11-14).
def enforce_approval_gate(text):
    old = 'self.auto = bool(api._settings.get("auto_approve", True))'
    new = 'self.auto = bool(api._settings.get("auto_approve", False))'
    if old in text:
        text = text.replace(old, new)
    if new not in text:
        raise SystemExit("approval gate: missing safe auto_approve default")
    old_gate = 'if need and not self.auto and not self.ask(cid, name, args):'
    new_gate = 'if need and not self.ask(cid, name, args):'
    if old_gate in text:
        text = text.replace(old_gate, new_gate)
    if new_gate not in text:
        raise SystemExit("approval gate: mandatory confirmation missing")
    return text

def patch_app(t):
    t = sub(t, '"""التنين الأسود — Windows desktop app.',
            '"""الطائر الأبيض — Windows desktop app, generated from the Black Dragon app by forge/make_white_bird.py.', 1, "docstring")
    t = sub(t, 'APP = "التنين الأحمر"', 'APP = "الطائر الأبيض"', 1, "APP name")
    # outside AppData on purpose: sessions inside Claude Desktop get AppData writes redirected into its package cache
    t = sub(t, 'Path(os.environ.get("TEMP", Path.home())) / "bd_build" / "dist" / "BlackDragon"',
            'Path.home() / ".whitebird-build" / "dist" / "WhiteBird"', 1, "update staging")
    t = sub(t, '/ "BlackDragon" / "settings.json"', '/ "WhiteBird" / "settings.json"', 1, "settings folder")
    t = sub(t, 'APP_SOURCE = REPO / "apps" / "dragon_desktop"',
            'APP_SOURCE = Path(os.environ.get("WHITE_BIRD_HOME", Path.home() / "OneDrive" / "Desktop" / "الطائر الأبيض")) / "app"', 1, "self-dev source")
    a = t.index('UPDATER_PS = r"""')
    b = t.index('"""', a + len('UPDATER_PS = r"""'))
    block = t[a:b]
    n = block.count("BlackDragon")
    if n < 4:
        raise SystemExit(f"✗ updater: expected ≥4 × BlackDragon, found {n}")
    t = t[:a] + block.replace("BlackDragon", "WhiteBird") + t[b:]
    log.append(f"  updater process/exe: {n}×")
    t = sub(t, '"Local\\\\BlackDragonDesktopApp"', '"Local\\\\WhiteBirdDesktopApp"', 1, "single-instance mutex")
    t = sub(t, r"%APPDATA%\\BlackDragon\\source_backups", r"%APPDATA%\\WhiteBird\\source_backups", 1, "backup path in prompt")
    t = sub(t, "أنت «التنين الأحمر» (الاسم الجديد لتطبيق التنين الأسود، ونفس محركه):",
            "أنت «الطائر الأبيض» (أحدث نسخة من تطبيق التنين، بنفس محركه وكل أدواته وبواجهة Apple):", 1, "identity")
    t = sub(t, "وابدأ ردك بالنتيجة.\n\n## عقل التنين الأحمر", "وابدأ ردك بالنتيجة.\n" + SYSTEM_PROTOCOL + "\n## عقل التنين الأحمر", 1, "reasoning protocol")
    t = sub(t, "«التنين الأحمر»", "«الطائر الأبيض»", None, "identity elsewhere")
    t = sub(t, "التنين الأحمر بيتحدّث دلوقتي", "الطائر الأبيض بيتحدّث دلوقتي", 1, "update message")
    t = sub(t, "Red Dragon app", "White Bird app", None, "english name")
    t = sub(t, 'desk / "التنين الأسود - إضافة كروم"', 'desk / "الطائر الأبيض - إضافة كروم"', 1, "extension folder")
    t = sub(t, "تثبيت إضافة التنين الأسود في كروم", "تثبيت إضافة الطائر الأبيض في كروم", 1, "extension readme")
    t = sub(t, "عشان التنين يتحكم في كروم", "عشان الطائر يتحكم في كروم", 1, "extension readme 2")
    t = sub(t, "control.BRIDGE_PORT if control else " + PORT_OLD, "control.BRIDGE_PORT if control else " + PORT_NEW, 1, "extension port")
    t = sub(t, "through the «التنين الأسود» extension", "through the «الطائر الأبيض» extension", 1, "browser tool text")
    t = sub(t, 'background_color="#0b0d12"', "background_color=_wb_bg()", 1, "window color")
    t = sub(t, "def main():", WB_BG, 1, "theme-aware window color + black box")
    t = sub(t, WB_START_OLD, WB_START_NEW, 1, "lifecycle log around the window")
    t = sub(t, "    api = Api()\n    win = webview.create_window(", "    _wb_seed()\n    api = Api()\n    win = webview.create_window(", 1, "first-run data copy")
    return enforce_approval_gate(t)


def patch_control(t):
    t = sub(t, "BRIDGE_PORT = " + PORT_OLD, "BRIDGE_PORT = " + PORT_NEW, 1, "bridge port")
    t = sub(t, "ShowBalloonTip(6000, 'التنين الأحمر',", "ShowBalloonTip(6000, 'الطائر الأبيض',", 1, "notification title")
    t = sub(t, "إضافة «التنين الأسود» متثبتة", "إضافة «الطائر الأبيض» متثبتة", 1, "bridge error text")
    return t


def patch_mcp_control(t):
    t = sub(t, f'os.environ.get("BD_PORT", "{PORT_OLD}")', f'os.environ.get("BD_PORT", "{PORT_NEW}")', 1, "mcp default port")
    return sub(t, "«التنين الأسود»", "«الطائر الأبيض»", None, "mcp text")


def patch_mcp_dragon(t):
    # this copy must reach THIS app: its bridge port and its token in %APPDATA%\WhiteBird, not the Black Dragon's
    t = sub(t, f'os.environ.get("BD_PORT", "{PORT_OLD}")', f'os.environ.get("BD_PORT", "{PORT_NEW}")', 2, "mcp_dragon default port")
    return sub(t, '/ "BlackDragon" / "settings.json"', '/ "WhiteBird" / "settings.json"', 1, "mcp_dragon settings folder")


# ---------------------------------------------------------------- ui/index.html
COLORS = [("#0b0d12cc", "var(--glass-strong)"), ("#07080b", "var(--fill2)"), ("#ffb3ac", "var(--red)"), ("#c9ccd3", "var(--text)"),
          ("#16120a", "#fff"), ("#0b0d12", "var(--bg)"), ("#090b10", "var(--bg2)"), ("#1a1f2b", "var(--hover)"),
          ("#3b3320", "var(--accent-soft)"), ("#14120c", "var(--card)"), ("#2a2f3b", "var(--hover)"), ("#5a2a26", "var(--red)"),
          ("#244a36", "var(--green)"), ("#6b5320", "var(--orange)"), ("#5b4a22", "var(--orange)"), ("#3a3f4c", "var(--fill)"),
          ("#0d1016", "transparent"), ("#2a2010", "rgba(255,159,10,.12)"), ("#10131a", "var(--bg)"), ("#12151c", "var(--panel)")]

SEARCH_BTN = ('<button id="wbSpotBtn" class="wb-search" title="بحث سريع في المحادثات والأوامر والإعدادات (Ctrl+K)">'
              '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="11" cy="11" r="7"/>'
              '<path d="m20 20-3.6-3.6"/></svg><span class="wb-l">دوّر أو نفّذ أمر…</span><span class="wb-k">Ctrl K</span></button>\n  <div class="sp"></div>')


def patch_ui(t):
    t = sub(t, "<title>التنين الأحمر</title>", "<title>الطائر الأبيض</title>", 1, "title")
    t = sub(t, '<div><div class="logo">🐉 التنين الأحمر</div><div class="sub" id="st"><span class="dot"></span>بيحمّل…</div></div>\n  <div class="sp"></div>',
            '<div class="brand"><img src="white-bird.png" alt=""><div><div class="logo">الطائر الأبيض</div>'
            '<div class="sub" id="st"><span class="dot"></span>بيحمّل…</div></div></div>\n  <div class="sp"></div>\n  ' + SEARCH_BTN, 1, "toolbar brand + search")
    t = sub(t, '<div class="welcome"><h1>🐉 التنين الأحمر</h1>',
            '<div class="welcome"><img class="wb-hero" src="white-bird.png" alt=""><h1>الطائر الأبيض</h1>', 1, "welcome hero")
    t = sub(t, "وكل محركات التنين الأسود وسوبر باور والبرامج اللي على جهازك.</div>",
            "وكل محركات التنين الأسود وسوبر باور والبرامج اللي على جهازك.<br><span class=\"wb-k\">Ctrl K</span> للبحث السريع في المحادثات والأوامر.</div>",
            1, "welcome hint")
    t = sub(t, "عقل التنين الأحمر", "عقل الطائر", None, "brain label")
    t = sub(t, "التنين الأحمر", "الطائر الأبيض", None, "name")
    t = resub(t, r"(?<!كتالوج )(?<!مجلد )التنين(?! الأسود)(?! الأحمر)", "الطائر", "assistant name in hints")
    t = sub(t, "🐉", "🕊", None, "emoji")
    # shortcuts by key position (keyCode), so they also work while the keyboard is on Arabic (Ctrl+N gave «ى», not «n»)
    t = sub(t, "e.ctrlKey&&!e.shiftKey&&!e.altKey&&e.code==='KeyM'", "e.ctrlKey&&!e.shiftKey&&!e.altKey&&(e.code==='KeyM'||e.keyCode===77)", 1, "Ctrl+M any layout")
    for ch, kc in (("b", 66), ("n", 78), ("e", 69)):
        t = sub(t, f"e.ctrlKey&&(e.key==='{ch}'||e.key==='{ch.upper()}')", f"e.ctrlKey&&(e.key==='{ch}'||e.key==='{ch.upper()}'||e.keyCode==={kc})",
                1, f"Ctrl+{ch.upper()} any layout")
    for old, new in COLORS:
        n = t.count(old)
        if n:
            t = t.replace(old, new)
            log.append(f"  color {old} → {new}: {n}×")
    css = (OV / "white-bird.css").read_text(encoding="utf-8")
    t = sub(t, "</style>", css + "</style>", 1, "Apple design layer")
    js = (OV / "spotlight.js").read_text(encoding="utf-8")
    t = sub(t, "</script>\n</body>", js + "</script>\n</body>", 1, "Spotlight")
    return t


# ---------------------------------------------------------------- chrome extension
# The White Bird's own extension upgrade (v1.4.0, made 2026-11-14 directly in app\chrome_extension: watchdog, per-command
# timeout, offscreen keep-alive, tab group, «controlled» frame). Moved into the forge on 2026-11-15 so a regeneration keeps
# it and the Golden Bird / Golden Dragon (which reuse this function) get it too. Copied BEFORE the rebrand below.
EXT_OV = OV / "chrome_extension"


def patch_extension(root):
    from PIL import Image
    if EXT_OV.is_dir():
        for f in sorted(EXT_OV.iterdir()):
            if f.is_file():
                shutil.copy2(f, root / f.name)
                log.append(f"  extension {f.name}: White Bird v1.4 file")
    big = Image.open(OV / "icon" / "wb-1024.png").convert("RGBA")
    for f in sorted(root.rglob("*")):
        if f.suffix.lower() in (".js", ".json", ".html", ".css", ".txt"):
            t = f.read_text(encoding="utf-8")
            o = t
            t = t.replace(PORT_OLD, PORT_NEW).replace("التنين الأسود", "الطائر الأبيض").replace("Black Dragon", "White Bird").replace("🐉", "🕊")
            if t != o:
                write(f, t)
                log.append(f"  extension {f.name}: rebranded")
        elif f.suffix.lower() == ".png":
            w, h = Image.open(f).size
            big.resize((w, h), Image.LANCZOS).save(f)
            log.append(f"  extension {f.name}: bird icon {w}×{h}")
    t = (root / "background.js").read_text(encoding="utf-8")
    if f"const PORT = {PORT_NEW};" not in t:
        raise SystemExit("✗ extension port was not changed")


# ---------------------------------------------------------------- build.ps1
def build_ps1():
    codes = ",".join(f"0x{ord(c):x}" for c in "الطائر الأبيض")
    return rf'''# Build «الطائر الأبيض» (WhiteBird.exe). Generated by forge\make_white_bird.py — edit the forge, not this file.
#   1) stamps ui\version.txt (the app compares it with the staged build and offers «حدّث دلوقتي»)
#   2) builds into %USERPROFILE%\.whitebird-build\dist_new, then stages it in ...\dist (never a half-built folder)
#   3) installs to %USERPROFILE%\WhiteBird unless that copy is running (then its update button does it)
#   4) (re)creates the Desktop shortcut «الطائر الأبيض» -> %USERPROFILE%\WhiteBird\WhiteBird.exe on every build
# Not in AppData on purpose: a build started from a session inside Claude Desktop gets AppData writes redirected into
# Claude's package cache, which Explorer can't see (the shortcut then breaks). It never touches the Black Dragon.
$ErrorActionPreference = "Continue"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$work = Join-Path $env:USERPROFILE ".whitebird-build"
Set-Location $here
(Get-Date -Format "yyyy.MM.dd-HHmm") | Set-Content -Encoding ascii (Join-Path $here "ui\version.txt")
Remove-Item -Recurse -Force (Join-Path $here "__pycache__") -ErrorAction SilentlyContinue
python -m PyInstaller --noconfirm --windowed --name WhiteBird --icon "$here\ui\white-bird.ico" `
  --add-data "$here\ui;ui" --add-data "$here\chrome_extension;chrome_extension" --add-data "$here\mcp_control.py;." --add-data "$here\voice.py;." `
  --hidden-import keyring.backends.Windows --hidden-import webview.dom --hidden-import control `
  --distpath "$work\dist_new" --workpath "$work\build" --specpath $work app.py
if ($LASTEXITCODE -ne 0) {{ throw "PyInstaller failed" }}
robocopy "$work\dist_new\WhiteBird" "$work\dist\WhiteBird" /MIR /NFL /NDL /NJH /NJS /NP | Out-Null
$dst = Join-Path $env:USERPROFILE "WhiteBird"
$exe = Join-Path $dst "WhiteBird.exe"
if (Get-Process WhiteBird -ErrorAction SilentlyContinue | Where-Object {{ $_.Path -eq $exe }}) {{
  Write-Output "staged (app is open: use the update button inside the app)"
}} else {{
  New-Item -ItemType Directory -Force $dst | Out-Null
  robocopy "$work\dist\WhiteBird\_internal" "$dst\_internal" /MIR /NFL /NDL /NJH /NJS /NP | Out-Null
  Copy-Item "$work\dist\WhiteBird\WhiteBird.exe" $exe -Force
  Write-Output "installed: $exe"
}}
$desk = [Environment]::GetFolderPath("Desktop")
$lnkPath = Join-Path $desk ((-join [char[]]({codes})) + ".lnk")
if (Test-Path -LiteralPath $exe) {{
  $ws = New-Object -ComObject WScript.Shell
  $lnk = $ws.CreateShortcut("$desk\WhiteBird.lnk")
  $lnk.TargetPath = $exe; $lnk.WorkingDirectory = $dst; $lnk.IconLocation = "$exe,0"; $lnk.Description = "White Bird"; $lnk.Save()
  Move-Item -LiteralPath "$desk\WhiteBird.lnk" -Destination $lnkPath -Force
  Write-Output "shortcut: $lnkPath -> $exe"
}}
'''


# ---------------------------------------------------------------- build.ps1: test gate
# The smoke tests live in ..\tests (outside app\, so regenerating never touches them). build.ps1 runs them first and
# builds nothing when one fails; -SkipTests is the explicit way around it.
BUILD_GATE = r'''param([switch]$SkipTests)          # -SkipTests: build without running the smoke tests first
$ErrorActionPreference = "Continue"
if ($SkipTests) {
  Write-Output "tests skipped (-SkipTests)"
} else {
  $tests = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\tests\run_tests.ps1"))
  if (-not (Test-Path -LiteralPath $tests)) { Write-Output "build stopped: test runner not found: $tests (-SkipTests builds anyway)"; exit 1 }
  powershell -NoProfile -ExecutionPolicy Bypass -File $tests
  if ($LASTEXITCODE -ne 0) { Write-Output "build stopped: tests failed (exit $LASTEXITCODE), nothing was built (-SkipTests builds anyway)"; exit 1 }
}
'''


def patch_build(t):
    t = sub(t, "#   1) stamps ui\\version.txt",
            "#   0) runs the smoke tests (..\\tests\\run_tests.ps1) and stops on any failure; -SkipTests skips them\n"
            "#   1) stamps ui\\version.txt", 1, "build: header")
    t = sub(t, '$ErrorActionPreference = "Continue"\n', BUILD_GATE, 1, "build: test gate + -SkipTests")
    return t


# ---------------------------------------------------------------- data seeding (once)
def seed():
    appdata = Path(os.environ["APPDATA"])
    src, dst = appdata / "BlackDragon", appdata / "WhiteBird"
    dst.mkdir(parents=True, exist_ok=True)
    s = dst / "settings.json"
    if not s.exists() and (src / "settings.json").exists():
        d = json.loads((src / "settings.json").read_text(encoding="utf-8-sig"))
        for k in ("spent", "balance", "balance_at"):
            d.pop(k, None)
        s.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
        log.append(f"  seed: settings ({', '.join(sorted(d))})")
    for name in ("chats", "chat_library"):
        if (src / name).exists() and not (dst / name).exists():
            shutil.copytree(src / name, dst / name)
            log.append(f"  seed: {name} ({sum(1 for _ in (dst / name).rglob('*') if _.is_file())} files)")


def main():
    force, do_seed = "--force" in sys.argv, "--seed" in sys.argv
    if not (SRC / "app.py").exists():
        raise SystemExit(f"✗ كود التنين مش موجود في {SRC}")
    guard(force)
    tmp = WB / "app.__new__"
    shutil.rmtree(tmp, ignore_errors=True)
    shutil.copytree(SRC, tmp, ignore=shutil.ignore_patterns(".ruff_cache", "__pycache__", "*.bak*", "*.pyc", "dist", "build", "build.ps1",
                                                            ".rd-lock.json", "*.tmp"))
    log.append(f"copied {SRC} (app.py sha256 {sha(SRC / 'app.py')[:16]}…)")
    for name, fn in (("app.py", patch_app), ("control.py", patch_control), ("mcp_control.py", patch_mcp_control),
                     ("mcp_dragon.py", patch_mcp_dragon), ("ui/index.html", patch_ui)):
        log.append(name)
        p = tmp / name
        write(p, fn(p.read_text(encoding="utf-8")))
    for py in sorted(p.name for p in tmp.glob("*.py")):
        compile((tmp / py).read_text(encoding="utf-8"), py, "exec")       # syntax gate before anything is replaced
    log.append("chrome_extension")
    patch_extension(tmp / "chrome_extension")
    (tmp / "ui" / "fonts").mkdir(exist_ok=True)
    for f in (OV / "fonts").iterdir():
        shutil.copy2(f, tmp / "ui" / "fonts" / f.name)
    shutil.copy2(OV / "icon" / "wb-256.png", tmp / "ui" / "white-bird.png")
    shutil.copy2(OV / "icon" / "white-bird.ico", tmp / "ui" / "white-bird.ico")
    for old in ("red-dragon.ico", "red-dragon.png"):
        (tmp / "ui" / old).unlink(missing_ok=True)
    log.append("build.ps1")
    (tmp / "build.ps1").write_text(patch_build(build_ps1()), encoding="utf-8-sig")
    rd = (tmp / "README.md")
    rd.write_text("# الطائر الأبيض: كود التطبيق\n\nالمجلد ده **متولّد** من كود التنين الأسود بسكربت `..\\forge\\make_white_bird.py`. "
                  "أي تعديل دايم يتحط في `forge` (التصميم في `overlay\\white-bird.css`، والبحث السريع في `overlay\\spotlight.js`، "
                  "والتعديلات على الكود جوه السكربت)، وبعدين ولّد من جديد وابني بـ `build.ps1`.\n", encoding="utf-8")
    files = {p.relative_to(tmp).as_posix(): sha(p) for p in tmp.rglob("*") if p.is_file()}
    files = {k: v for k, v in files.items() if k not in UNTRACKED}
    (tmp / ".wb_generated.json").write_text(json.dumps({"generated": time.strftime("%Y-%m-%d %H:%M:%S"), "source": str(SRC),
                                                        "source_app_sha256": sha(SRC / "app.py"), "files": files}, ensure_ascii=False, indent=1),
                                            encoding="utf-8")
    if OUT.exists():
        shutil.rmtree(OUT)
    tmp.rename(OUT)
    if do_seed:
        seed()
    print("\n".join(log))
    print(f"✓ {OUT}  ({len(files)} files)")


if __name__ == "__main__":
    main()
