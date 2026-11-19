"""make_golden_bird.py — builds the source of «الطائر الذهبي» (Golden Bird).

Golden Bird = the White Bird (itself generated from the Black Dragon app) + what the reverse engineering of the owner's
«مهارات» folder found (2026-11-14). Neither the Black Dragon nor the White Bird is touched. This script:
  1. loads the White Bird forge (..\\..\\الطائر الأبيض\\forge\\make_white_bird.py) and applies ALL its patches to the Black Dragon
     source, so every future White Bird fix reaches the Golden Bird on the next regeneration;
  2. gives it its own identity on top: name, window mutex, settings folder %APPDATA%\\GoldenBird, build staging
     %USERPROFILE%\\.goldenbird-build, install folder %USERPROFILE%\\GoldenBird, Chrome-bridge port 47841, its own extension,
     gold design layer (overlay\\golden-bird.css) and the golden bird icon;
  3. adds the new capabilities: golden_tools.py (studio + motion library), the data in data\\ (made by build_catalog.py),
     three tools in the app (studio, studio_run, motion_lib), the subscription-mode mapping and the «قدرات الطائر الذهبي»
     section of the system prompt;
  4. puts a test gate at the top of build.ps1 (..\\tests\\run_tests.ps1; -SkipTests skips it);
  5. applies the feature patches in patches\\ (steer.py: a message sent while it works is read at once) and copies
     every modules\\golden_*.py next to app.py.
Every patch counts its anchor, so a changed upstream stops the script instead of producing a half-patched app.

  python -X utf8 make_golden_bird.py          regenerate ..\\app (refuses if app\\ was edited by hand; --force overrides)
  python -X utf8 make_golden_bird.py --seed   also copy settings + chats once from %APPDATA%\\WhiteBird (else BlackDragon)
"""
import hashlib, importlib.util, json, os, re, shutil, sys, time
from pathlib import Path

FORGE = Path(__file__).resolve().parent
GB = FORGE.parent                                       # ...\Desktop\الطائر الذهبي
OUT = GB / "app"
OV = FORGE / "overlay"
DATA = FORGE / "data"
DESK = GB.parent
WB_FORGE = Path(os.environ.get("WHITE_BIRD_HOME", DESK / "الطائر الأبيض")) / "forge" / "make_white_bird.py"
STAMP = OUT / ".gb_generated.json"
UNTRACKED = {"ui/version.txt", ".gb_generated.json"}
MODULES = FORGE / "modules"                             # golden_*.py: copied next to app.py and bundled into the exe
sys.path.insert(0, str(FORGE))
from patches import steer                               # noqa: E402  «تغيير المسار وهو شغال»
PORT_WB, PORT_GB = "47831", "47841"
NAME_WB, NAME_GB = "الطائر الأبيض", "الطائر الذهبي"
log = []


def load_white_bird():
    if not WB_FORGE.is_file():
        raise SystemExit(f"✗ سكربت الطائر الأبيض مش موجود: {WB_FORGE}")
    spec = importlib.util.spec_from_file_location("make_white_bird", WB_FORGE)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def sub(text, old, new, count=1, name=""):
    n = text.count(old)
    if (count is None and n == 0) or (count is not None and n != count):
        raise SystemExit(f"✗ {name}: expected {count if count is not None else '≥1'} × {old[:70]!r}, found {n}")
    log.append(f"  {name}: {n}×")
    return text.replace(old, new)


def resub(text, pattern, new, name="", count=1):
    out, n = re.subn(pattern, new, text)
    if n != count:
        raise SystemExit(f"✗ {name}: pattern {pattern!r} matched {n}×, expected {count}")
    log.append(f"  {name}: {n}×")
    return out


def write(p, text):
    Path(p).write_text(text, encoding="utf-8", newline="")


def guard(force):
    if not OUT.exists() or force:
        return
    if not STAMP.exists():
        raise SystemExit(f"✗ {OUT} موجود ومش متولّد بالسكربت ده. شغّل بـ --force لو متأكد.")
    rec = json.loads(STAMP.read_text(encoding="utf-8"))["files"]
    changed = [p for p, h in rec.items() if not (OUT / p).exists() or sha(OUT / p) != h]
    now = {p.relative_to(OUT).as_posix() for p in OUT.rglob("*") if p.is_file() and "__pycache__" not in p.parts}
    added = sorted(now - set(rec) - UNTRACKED)
    if changed or added:
        raise SystemExit("✗ فيه تعديلات يدوية في app\\ هتضيع:\n  " + "\n  ".join(changed + added) +
                         "\nانقلها لـ forge أو شغّل بـ --force.")


# ---------------------------------------------------------------- identity: White Bird -> Golden Bird
RENAMES = [(NAME_WB, NAME_GB), ("White Bird", "Golden Bird"), ("WhiteBird", "GoldenBird"), ("whitebird", "goldenbird"),
           ("WHITE_BIRD_HOME", "GOLDEN_BIRD_HOME"), (PORT_WB, PORT_GB), ("white-bird", "golden-bird"), ("🕊", "🦅")]


def rename(t, where):
    for old, new in RENAMES:
        n = t.count(old)
        if n:
            t = t.replace(old, new)
            log.append(f"  {where}: {old} → {new}: {n}×")
    return t


def catalog_counts():
    lib = json.loads((DATA / "library.json").read_text(encoding="utf-8"))
    studio = json.loads((DATA / "studio.json").read_text(encoding="utf-8"))
    items = lib["items"]
    return len(items), sum(1 for i in items if i.get("offline_entry")), len(studio["programs"]), studio["programs"]


def golden_section(n_lib, n_ready, programs):
    # braces: this f-string -> app.py's SYSTEM f-string -> the model. A literal @{x} must be written @{{{{x}}}} here.
    names = "، ".join(p["name"] for p in programs[:8])
    return f"""
## قدرات الطائر الذهبي (اتجمعت بالهندسة العكسية لمجلد «مهارات»، 2026-11-14)
- **استوديو البرامج:** فيه أداتين. `studio` للعرض: `list` و`show ID`. و`studio_run` للفك والتشغيل، وبموافقة: `install` و`run`. البرامج مفتوحة المصدر، وبصمة كل أرشيف اتطابقت مع المصدر الرسمي، وعددها {len(programs)}، منها: {names}.
  - **ترتيب الاستخدام:** `list`، وبعدين `show ID` (فيه الأمر والأمثلة من دليل البرنامج نفسه)، وبعدين `install` مرة واحدة، وبعدين `run`. وجرّب على عيّنة صغيرة الأول.
- **مكتبة الموشن:** أداة `motion_lib`، وفيها {n_lib} مكتبة ومحرك، منهم GSAP بإضافاته وanime.js وthree.js وlottie-web وtween.js. كل واحدة معاها رخصتها وحالتها وإزاي تستخدمها.
  - **أفلام HTML:** `kit` بيحط النسخة الجاهزة جوه `vendor` في مجلد الشغل، ومعاها ملف الرخص ({n_ready} مكتبة جاهزة من غير نت). كده الرندر يشتغل من غير CDN ومن غير نت.
- **الوقت مربوط بالكلام:** أداة `speech_sync`. الفكرة جاية من دراسة hypit، والكود بتاعنا. السكريبت مايبقاش فيه ثواني، ويبقى فيه علامات على الكلمات: `@{{{{x}}}}…@{{{{/x}}}}` لمدى، و`@{{{{x!}}}}` للحظة، و`||` أو سطر جديد لقفل سطر الكابشن.
  - **الخطوات:** طلّع ملف الكلمات من التسجيل الحقيقي (whisperx بـ `--output_format json`، أو faster-whisper بـ word_timestamps)، وبعدين `speech_sync`. الناتج `sync.json`، وفيه كل علامة بالثانية وبالفريم، و`captions.srt`.
  - **القطع والمؤثرات:** اربطها بالعلامات مش بالثواني. ولو التسجيل اتغيّر، أعد `speech_sync` بس.
- **مهارات اتضافت 2026-11-14 (اقراها بأداة skill قبل ما تستخدمها):**
  - `arabic-captions-khatt`: كابشن عربي محروق صح (حروف متوصّلة ومن اليمين للشمال وتشكيل)، وبياخد ناتج `speech_sync` على طول.
  - `taste-distillation` و`taste-application`: LUT وإيقاع قطع مقاسين من ريلز مرجعية، من غير نت. وFAL مدفوع وممنوع من غير موافقة.
  - `motion-doctrine` و`cut-the-curve` و`seam-craft`: قواعد حركة وانتقالات HyperFrames.
  - 13 قالب `video-template-*`.
- **الرخص قبل أي شغل تجاري:** أي حاجة رخصتها مش «yes» قول للمستخدم الأول، زي غير التجاري، وGPL/AGPL، وCommons Clause، وRemotion للشركات.
- **بروتوكول الذهب:**
  1. قبل ما تبني من الصفر، دوّر في `motion_lib` و`studio`: الأداة الجاهزة اللي اتحقق منها أحسن من كود جديد.
  2. اقرا الأمر من `show` (دليل البرنامج)، وماتخمّنش الخيارات.
  3. كل ناتج يتقاس بـ verify_media أو view_image قبل ما تقول خلص، وفي التسليم اكتب إيه اللي اتقاس وإيه اللي ماتجربش.
"""


CC_LINES = """
- studio / studio_run: `python -X utf8 "{APP_SOURCE}\\\\golden_tools.py" studio list|show ID|install ID|cmd ID [args...]`. الأمر `cmd` بيطبع الأمر الكامل للبرنامج المتفكوك، وبعدين شغّله في مجلد الشغل.
- motion_lib: `python -X utf8 "{APP_SOURCE}\\\\golden_tools.py" lib find "..." | show ID | kit "<مجلد الشغل>" ID...`.
- speech_sync: `python -X utf8 "{APP_SOURCE}\\\\golden_tools.py" sync SCRIPT.txt WORDS.json "<مجلد الشغل>\\\\sync" [--fps 30]`."""

GOLDEN_TOOLS = '''    tool("studio", "Golden Bird studio: open-source command-line programs found by reverse engineering the owner's «مهارات» folder "
         "(Rhubarb lip sync, HandBrakeCLI, Synfig, Tahoma2D tcomposer, melt, whisper-cli, oiiotool…), each archive sha256-checked "
         "against the official release, with usage lines taken from the program's own docs. action 'list' = all programs and their "
         "state (ready / can unpack), 'show' = one program (id): usage, examples, licence, evidence. Read-only.",
         {"action": {"type": "string", "enum": ["list", "show"]}, "id": S}, ["action"]),
    tool("studio_run", "Golden Bird studio actions that change the PC. 'install' = verify the archive sha256 and unpack it into "
         "%USERPROFILE%/GoldenBird/studio/<id> (runs nothing). 'run' = run the unpacked program with args inside the working "
         "folder (pass absolute paths). Call studio 'show' first for the exact usage. Needs approval.",
         {"action": {"type": "string", "enum": ["install", "run"]}, "id": S, "args": {"type": "array", "items": S}, "reason": S,
          "timeout_minutes": {"type": "integer", "minimum": 1, "maximum": 240}}, ["action", "id", "reason"], approval=True),
    tool("motion_lib", "Golden Bird motion library: animation / 3D / shader / particles / text / video libraries and engines from the "
         "owner's clones (GSAP + plugins, anime.js, three.js, lottie-web, tween.js, two.js, manim, hyperframes…) with licence, readiness "
         "and how to use each. 'find' by words (Arabic or English; optional category), 'show' one id, 'kit' = copy the ready offline "
         "builds (+ licences) of the given ids into <working folder>/vendor and return the <script> tags, so an HTML film renders "
         "with no CDN and no internet.",
         {"action": {"type": "string", "enum": ["find", "show", "kit"]}, "query": S, "id": S,
          "ids": {"type": "array", "items": S}, "category": S, "limit": {"type": "integer", "minimum": 1, "maximum": 20}}, ["action"]),
    tool("speech_sync", "Golden Bird: time follows speech. Align a script whose words carry marks (@{name}…@{/name} = a range, "
         "@{name!} = a moment, || or a new line = caption break; NO seconds in the script) to the real recording's word timings "
         "(WhisperX JSON or faster-whisper word_timestamps JSON), with Arabic normalisation and a monotone DP (missing / extra / "
         "split words handled). Writes sync.json (every range, moment and word in seconds and frames) + captions.srt into out_dir "
         "(inside the working folder). Tie cuts, B-roll, effects and SFX to these marks, never to typed seconds.",
         {"script": S, "words": S, "out_dir": {"type": "string", "description": "default: <working folder>/sync"},
          "fps": {"type": "integer", "minimum": 1, "maximum": 240}}, ["script", "words"]),
'''

GOLDEN_DISPATCH = '''def req_str(a, k):
    v = a.get(k)
    if not isinstance(v, str) or not v.strip():
        raise ValueError(f"INVALID_JSON: {k}")
    return v


def golden_dispatch(sess, name, a, cid=""):
    """«الطائر الذهبي» tools (generated by forge/make_golden_bird.py): studio (read-only), studio_run (install/run,
    approved by the user), motion_lib (find / show / kit into the working folder)."""
    import golden_tools as gt
    act = a.get("action") or ""
    try:
        if name == "studio":
            if act == "list":
                return gt.md_studio_list(), False
            if act == "show":
                return gt.md_studio_show(a.get("id") or ""), False
            raise ValueError("INVALID_JSON: action must be list or show")
        if name == "studio_run":
            ident = a.get("id") or ""
            if act == "install":
                out, ok = gt.studio_install(ident, on_line=lambda s: sess.emit("progress", id=cid, text=s))
                return out, not ok
            if act == "run":
                args = as_list(a.get("args") or [])
                cmd, _ = gt.studio_cmd(ident, args)
                rc, out = run(cmd, sess.wd() or Path.home(), int(a.get("timeout_minutes") or 30) * 60, **sess.live(cid))
                return clip(f"exit code {rc}\\n{out}", 40000), rc != 0
            raise ValueError("INVALID_JSON: action must be install or run")
        if name == "motion_lib":
            if act == "find":
                return gt.md_lib_find(a.get("query") or a.get("id") or "", int(a.get("limit") or 8), a.get("category") or None), False
            if act == "show":
                return gt.md_lib_show(a.get("id") or a.get("query") or ""), False
            if act == "kit":
                wd = sess.wd()
                if not wd:
                    return "اختار مجلد شغل الأول: kit بينسخ المكتبات لمجلد vendor جواه.", True
                ids = as_list(a.get("ids") or a.get("id") or [])
                if not ids:
                    raise ValueError("INVALID_JSON: ids")
                out, ok = gt.lib_kit(wd, ids)
                return out, not ok
            raise ValueError("INVALID_JSON: action must be find, show or kit")
        if name == "speech_sync":
            wd = sess.wd()
            if not wd:
                return "اختار مجلد شغل الأول: speech_sync بيكتب sync.json وcaptions.srt جواه.", True
            out = sess.resolve(a.get("out_dir") or "sync")
            if not any(out.is_relative_to(d.resolve()) for d in sess.dirs()):
                return "out_dir لازم يبقى جوه مجلد الشغل.", True
            return gt.speech_sync_files(sess.resolve(req_str(a, "script")), sess.resolve(req_str(a, "words")), out,
                                        int(a.get("fps") or 30)), False
    except (KeyError, FileNotFoundError, ValueError) as e:
        msg = e.args[0] if e.args else str(e)
        if isinstance(e, ValueError) and str(msg).startswith("INVALID_JSON"):
            raise
        return f"✗ {msg}", True
    raise ValueError(f"unknown tool {name}")


def skills_index():'''

# ---------------------------------------------------------------- «عقل الطائر الذهبي»: deeper, bilingual reasoning
# Plain raw string (no braces): it lands inside app.py's SYSTEM f-string, where "\\" renders as one backslash.
GOLDEN_MIND = r"""
## عقل الطائر الذهبي (تفكير فائق بالعربي والإنجليزي)
- **افهم بلغتين:** اقرا الطلب بالعربي زي ما صاحبه قاله، بلهجته وغلطات الكتابة بالصوت. وبعدين اكتب لنفسك سطر بالإنجليزي: Task / Deliverable / Constraints / Done-when.
  - لو الصياغتين مختلفين في أي نقطة، يبقى فيه غموض. احسمه من الملفات أو بأمر، ولو ماينفعش، اسأل سؤال واحد بس.
- **فكّر بالإنجليزي في التقني، واتكلم بالعربي:**
  - الكود والأوامر والأرقام وخيارات البرامج وقراية المراجع والبحث: بالإنجليزي، لأنه أدق وأوسع.
  - الشرح والخطة والتسليم: بالعربي المصري.
  - أول مرة تكتب فيها مصطلح تقني، اكتبه بالإنجليزي بين قوسين.
- **دوّر بلغتين:** في motion_lib والكتالوج والمهارات والنت، استخدم كلمات عربي وإنجليزي مع بعض. ولو النتيجة ضعيفة في لغة، جرّب التانية.
- **سلّم التفكير، وماتنطّش درجة:**
  1. فهم.
  2. 2 أو 3 طرق أو فرضيات مختلفة فعلًا، واختار واحدة بسبب مكتوب.
  3. تشريح قبل الفشل: إيه أرجح 3 أسباب تخلّي التسليم يترفض؟ واقفل كل سبب بفحص.
  4. خطة فيها أرخص اختبار يكشف الغلط بدري.
  5. نفّذ على عيّنة صغيرة الأول، وبعدين الشغل كله.
  6. تحقق مستقل بأداة غير اللي طلّعت النتيجة: قياس، أو إعادة حساب، أو عين على الفريم.
  7. معايرة: ✅ دليل، و🟡 استنتاج بنسبة تقريبية، و❓ مجهول ومعاه الخطوة اللي تحسمه.
- **الطلب اللي فيه أكتر من خطوة:** ابدأ بـ `python -X utf8 "%USERPROFILE%\\.claude\\skills\\red-dragon\\scripts\\rd.py" think start "<الطلب>"`، وقبل التسليم شغّل `think check`.
  - المسائل الصعبة: اقرا مهارة ultra-mind.
  - القرارات اللي ليها أكتر من زاوية: اقرا مهارة expert-council.
- **الصدق قبل الطلاقة:** لو مش متأكد، قول «مش متأكد» واقترح أرخص خطوة تحسم. ماتخمّنش رقم أو خيار برنامج: شغّل `--help` أو اقرا المصدر.
  - ولو اكتشفت إنك غلطت قبل كده، قولها صريحة وصلّحها.
- **اتعلّم:** أي تصحيح من صاحب الشغل يتسجّل في نفس الدور بـ `rd.py learn "<إيه اللي حصل ← إيه اللي يتعمل>"`.
"""

GB_MIND_UPGRADE = '''def _gb_mind_upgrade():
    """Golden Bird thinks harder by default: one time per install, raise a low/medium/high effort (often copied from the
    previous app on first run) to xhigh. Marked done in the settings, so any level the owner picks afterwards is kept."""
    try:
        d = json.loads(SETTINGS.read_text(encoding="utf-8-sig")) if SETTINGS.exists() else {}
        if d.get("gb_mind_v1"):
            return
        old = d.get("effort")
        if old in (None, "low", "medium", "high"):
            d["effort"] = "xhigh"
        d["gb_mind_v1"] = True
        SETTINGS.parent.mkdir(parents=True, exist_ok=True)
        SETTINGS.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
        _wb_life(f"golden mind: effort {old} -> {d.get('effort')}")
    except Exception as e:
        _wb_life(f"golden mind upgrade skipped: {e!r}")


def main():'''

SEED_OLD = 'src = cache[0].parent if cache else dst.parent / "BlackDragon"'
SEED_NEW = ('src = cache[0].parent if cache else next((dst.parent / n for n in ("WhiteBird", "BlackDragon") '
            'if (dst.parent / n / "settings.json").exists()), dst.parent / "BlackDragon")')


def patch_app(t, n_lib, n_ready, programs):
    t = rename(t, "app.py")
    t = sub(t, '"""الطائر الذهبي — Windows desktop app, generated from the Black Dragon app by forge/make_white_bird.py.',
            '"""الطائر الذهبي — Windows desktop app, generated from the Black Dragon app by forge/make_white_bird.py + forge/make_golden_bird.py.',
            1, "docstring")
    t = sub(t, "أنت «الطائر الذهبي» (أحدث نسخة من تطبيق التنين، بنفس محركه وكل أدواته وبواجهة Apple):",
            "أنت «الطائر الذهبي» (أحدث نسخة من تطبيق التنين: كل قدرات الطائر الأبيض، ومعاها استوديو البرامج ومكتبة الموشن اللي اتجمعت "
            "بالهندسة العكسية، بواجهة ذهبية):", 1, "identity")
    t = sub(t, "\n## عقل التنين الأحمر", golden_section(n_lib, n_ready, programs) + "\n## عقل التنين الأحمر", 1, "golden capabilities section")
    t = sub(t, "أو Read على ملف SKILL.md بتاع المهارة.", "أو Read على ملف SKILL.md بتاع المهارة." + CC_LINES, 1, "subscription mapping")
    t = sub(t, '    tool("rebuild_app",', GOLDEN_TOOLS + '    tool("rebuild_app",', 1, "3 golden tools")
    t = sub(t, '        if name == "skill":', '        if name in ("studio", "studio_run", "motion_lib", "speech_sync"):\n'
               '            return golden_dispatch(self, name, a, cid)\n        if name == "skill":', 1, "dispatch hook")
    t = sub(t, "def skills_index():", GOLDEN_DISPATCH, 1, "golden_dispatch()")
    t = sub(t, SEED_OLD, SEED_NEW, 1, "first run copies the White Bird's data first")
    t = sub(t, 'if src.name == "BlackDragon":', 'if src.name in ("BlackDragon", "WhiteBird"):', 1, "seed: drop spend counters")
    # «عقل الطائر الذهبي»: bilingual reasoning protocol right before the Red Dragon brain section, and more thinking
    t = sub(t, "\n## عقل التنين الأحمر", GOLDEN_MIND + "\n## عقل التنين الأحمر", 1, "golden mind (bilingual reasoning)")
    t = sub(t, '_settings.get("effort", "high")', '_settings.get("effort", "xhigh")', 6, "default effort xhigh")
    t = resub(t, r'if self\.deep and EFFORTS\.index\(effort\) < EFFORTS\.index\("xhigh"\):\n(\s+)effort = "xhigh"',
              r'if self.deep and EFFORTS.index(effort) < EFFORTS.index("max"):\n\1effort = "max"', "deep analysis thinks at max", 2)
    t = sub(t, "\ndef main():", "\n" + GB_MIND_UPGRADE, 1, "one-time effort upgrade")
    t = sub(t, "    _wb_seed()\n    api = Api()", "    _wb_seed()\n    _gb_mind_upgrade()\n    api = Api()", 1, "run the upgrade at start")
    # 2026-11-15: the dragon folders moved from the Desktop into Desktop\مهارات; find them wherever they live now
    t = sub(t, PATHS_OLD, PATHS_NEW, 1, "paths follow the moved folders")
    t = sub(t, MONTAGE_LINE_OLD, MONTAGE_LINE_NEW, 1, "program paths: where.exe (المونتاج\\CLAUDE.md is gone)")
    return t


PATHS_OLD = '''REPO = Path(os.environ.get("BLACK_DRAGON_HOME", Path.home() / "OneDrive" / "Desktop" / REPO_DIRNAME))
APP_SOURCE = Path(os.environ.get("GOLDEN_BIRD_HOME", Path.home() / "OneDrive" / "Desktop" / "الطائر الذهبي")) / "app"        # this app's own source (self-development)
MONTAGE = Path.home() / "OneDrive" / "Desktop" / "المونتاج"
'''
PATHS_NEW = '''def _home_of(env, name):
    """A sibling folder wherever it lives now: $env, else Desktop\\\\<name>, else Desktop\\\\مهارات\\\\<name> (the dragon folders were
    moved into «مهارات» on 2026-11-15), OneDrive's Desktop first. Unknown -> the «مهارات» spot, so messages point there."""
    if os.environ.get(env):
        return Path(os.environ[env])
    cands = [base / sub / name for base in (Path.home() / "OneDrive" / "Desktop", Path.home() / "Desktop") for sub in ("", "مهارات")]
    return next((c for c in cands if c.is_dir()), cands[1])


REPO = _home_of("BLACK_DRAGON_HOME", REPO_DIRNAME)
APP_SOURCE = _home_of("GOLDEN_BIRD_HOME", "الطائر الذهبي") / "app"        # this app's own source (self-development)
MONTAGE = _home_of("DRAGON_MONTAGE_HOME", "المونتاج")
'''
MONTAGE_LINE_OLD = '  - المسارات الكاملة لكل برنامج مكتوبة في `{MONTAGE / "CLAUDE.md"}`.'
MONTAGE_LINE_NEW = '  - المسار الكامل لأي برنامج: `where.exe <الاسم>` (ملف `المونتاج\\\\CLAUDE.md` القديم مش موجود من 2026-11-15).'
MCP_REPO_OLD = '''if not REPO.exists():
    REPO = HOME / "Desktop" / "التنين الأسود"
'''
MCP_REPO_NEW = '''if not REPO.exists():                    # the folder moved into «مهارات» on 2026-11-15
    REPO = next((c for c in (HOME / "OneDrive" / "Desktop" / "مهارات" / "التنين الأسود", HOME / "Desktop" / "التنين الأسود",
                             HOME / "Desktop" / "مهارات" / "التنين الأسود") if c.exists()), HOME / "Desktop" / "التنين الأسود")
'''


def patch_ui(t, n_lib):
    t = rename(t, "index.html")
    css = (OV / "golden-bird.css").read_text(encoding="utf-8")
    t = sub(t, "</style>", css + "</style>", 1, "gold design layer")
    t = sub(t, "للبحث السريع في المحادثات والأوامر.</div>",
            f'للبحث السريع في المحادثات والأوامر.<br><span class="gb-badge">✦ جديد: استوديو البرامج ومكتبة الموشن ({n_lib} مكتبة)</span></div>',
            1, "welcome badge")
    return t


def patch_extension(root):
    from PIL import Image
    big = Image.open(OV / "icon" / "gb-1024.png").convert("RGBA")
    for f in sorted(root.rglob("*")):
        if f.suffix.lower() in (".js", ".json", ".html", ".css", ".txt"):
            o = f.read_text(encoding="utf-8")
            t = rename(o, f"extension {f.name}")
            if t != o:
                write(f, t)
        elif f.suffix.lower() == ".png":
            w, h = Image.open(f).size
            big.resize((w, h), Image.LANCZOS).save(f)
            log.append(f"  extension {f.name}: golden icon {w}×{h}")
    if f"const PORT = {PORT_GB};" not in (root / "background.js").read_text(encoding="utf-8"):
        raise SystemExit("✗ extension port was not changed")


def patch_build(t):
    t = rename(t, "build.ps1")
    codes_wb = ",".join(f"0x{ord(c):x}" for c in NAME_WB)
    codes_gb = ",".join(f"0x{ord(c):x}" for c in NAME_GB)
    t = sub(t, codes_wb, codes_gb, 1, "shortcut name")
    t = sub(t, '--add-data "$here\\voice.py;." `', '--add-data "$here\\voice.py;." --add-data "$here\\golden;golden" `', 1, "bundle catalogs")
    t = sub(t, "--hidden-import control `", "--hidden-import control --hidden-import golden_tools `", 1, "bundle golden_tools")
    return t


# STRICT: anything that would make the Golden Bird talk to, or share data with, the White Bird / the dragon.
STRICT = re.compile(r"47831|47821|Local\\+(?:White|Black)|/ \"(?:WhiteBird|BlackDragon)\" / \"settings\.json\"|\.whitebird-build|bd_build")
LEFTOVERS = re.compile(r"WhiteBird|whitebird|White Bird|الطائر الأبيض|white-bird|🕊")
# descriptive mentions that are on purpose (lineage, first-run copy of the White Bird's data); more = a new leftover
ALLOWED_LEFTOVER = {"app.py": 3, "golden_tools.py": 1, "README.md": 1, "ui/index.html": 2}


def check_leftovers(tmp):
    bad = []
    for p in tmp.rglob("*"):
        if p.is_file() and p.suffix.lower() in (".py", ".html", ".js", ".json", ".css", ".ps1", ".md", ".txt"):
            text = p.read_text(encoding="utf-8-sig", errors="replace")
            strict = STRICT.findall(text)
            if strict:
                bad.append(f"{p.relative_to(tmp)}: STRICT {strict[:3]}")
            n = len(LEFTOVERS.findall(text))
            if n > ALLOWED_LEFTOVER.get(p.relative_to(tmp).as_posix(), 0):
                bad.append(f"{p.relative_to(tmp)}: {n}")
    if bad:
        raise SystemExit("✗ فيه أسماء أو بورت الطائر الأبيض/التنين لسه موجودة:\n  " + "\n  ".join(bad))
    log.append("  leftovers: none (besides the White Bird seed source)")


def seed():
    appdata = Path(os.environ["APPDATA"])
    dst = appdata / "GoldenBird"
    src = next((appdata / n for n in ("WhiteBird", "BlackDragon") if (appdata / n / "settings.json").exists()), None)
    if not src:
        return
    dst.mkdir(parents=True, exist_ok=True)
    s = dst / "settings.json"
    if not s.exists():
        d = json.loads((src / "settings.json").read_text(encoding="utf-8-sig"))
        for k in ("spent", "balance", "balance_at"):
            d.pop(k, None)
        s.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
        log.append(f"  seed: settings from {src.name}")
    for name in ("chats", "chat_library"):
        if (src / name).exists() and not (dst / name).exists():
            shutil.copytree(src / name, dst / name)
            log.append(f"  seed: {name} from {src.name}")


def main():
    force, do_seed = "--force" in sys.argv, "--seed" in sys.argv
    wb = load_white_bird()
    SRC = wb.SRC
    if not (SRC / "app.py").exists():
        raise SystemExit(f"✗ كود التنين مش موجود في {SRC}")
    for need in ("library.json", "studio.json"):
        if not (DATA / need).is_file():
            raise SystemExit(f"✗ {DATA / need} مش موجود. شغّل build_catalog.py الأول.")
    n_lib, n_ready, n_prog, programs = catalog_counts()
    guard(force)
    tmp = GB / "app.__new__"
    shutil.rmtree(tmp, ignore_errors=True)
    shutil.copytree(SRC, tmp, ignore=shutil.ignore_patterns(".ruff_cache", "__pycache__", "*.bak*", "*.pyc", "dist", "build", "build.ps1",
                                                            ".rd-lock.json", "*.tmp"))
    log.append(f"copied {SRC} (app.py sha256 {sha(SRC / 'app.py')[:16]}…)")
    # 1) every White Bird patch, exactly as the White Bird forge applies them
    for name, fn in (("app.py", wb.patch_app), ("control.py", wb.patch_control), ("mcp_control.py", wb.patch_mcp_control),
                     ("mcp_dragon.py", wb.patch_mcp_dragon), ("ui/index.html", wb.patch_ui)):
        p = tmp / name
        write(p, fn(p.read_text(encoding="utf-8")))
    wb.patch_extension(tmp / "chrome_extension")
    log.append(f"white bird patches: {len(wb.log)} steps")
    # 2) the Golden Bird on top
    write(tmp / "app.py", patch_app((tmp / "app.py").read_text(encoding="utf-8"), n_lib, n_ready, programs))
    for name in ("control.py", "mcp_control.py", "mcp_dragon.py"):
        write(tmp / name, rename((tmp / name).read_text(encoding="utf-8"), name))
    write(tmp / "mcp_dragon.py", sub((tmp / "mcp_dragon.py").read_text(encoding="utf-8"), MCP_REPO_OLD, MCP_REPO_NEW, 1,
                                     "mcp_dragon: engine repo follows the move"))
    write(tmp / "ui/index.html", patch_ui((tmp / "ui/index.html").read_text(encoding="utf-8"), n_lib))
    patch_extension(tmp / "chrome_extension")
    # 3) feature patches (forge\patches), on top of the gold layer
    write(tmp / "app.py", steer.patch_app((tmp / "app.py").read_text(encoding="utf-8"), sub))
    write(tmp / "ui/index.html", steer.patch_ui((tmp / "ui/index.html").read_text(encoding="utf-8"), sub))
    for mod in sorted(MODULES.glob("golden_*.py")):
        shutil.copy2(mod, tmp / mod.name)
    (tmp / "golden").mkdir()
    for f in ("library.json", "studio.json"):
        shutil.copy2(DATA / f, tmp / "golden" / f)
    for py in sorted(p.name for p in tmp.glob("*.py")):
        compile((tmp / py).read_text(encoding="utf-8"), py, "exec")       # syntax gate before anything is replaced
    (tmp / "ui" / "fonts").mkdir(exist_ok=True)
    for f in (wb.OV / "fonts").iterdir():
        shutil.copy2(f, tmp / "ui" / "fonts" / f.name)
    shutil.copy2(OV / "icon" / "gb-256.png", tmp / "ui" / "golden-bird.png")
    shutil.copy2(OV / "icon" / "golden-bird.ico", tmp / "ui" / "golden-bird.ico")
    for old in ("red-dragon.ico", "red-dragon.png", "white-bird.ico", "white-bird.png"):
        (tmp / "ui" / old).unlink(missing_ok=True)
    (tmp / "build.ps1").write_text(steer.patch_build(patch_build(wb.patch_build(wb.build_ps1())), sub), encoding="utf-8-sig")
    (tmp / "README.md").write_text(
        f"# {NAME_GB}: كود التطبيق\n\nالمجلد ده **متولّد**: كود التنين الأسود ← تعديلات `..\\..\\الطائر الأبيض\\forge\\make_white_bird.py` ← "
        "تعديلات `..\\forge\\make_golden_bird.py`. أي تعديل دايم يتحط في `forge`، وبعدين ولّد من جديد وابني بـ `build.ps1`.\n", encoding="utf-8")
    check_leftovers(tmp)
    files = {p.relative_to(tmp).as_posix(): sha(p) for p in tmp.rglob("*") if p.is_file()}
    files = {k: v for k, v in files.items() if k not in UNTRACKED}
    (tmp / ".gb_generated.json").write_text(json.dumps({
        "generated": time.strftime("%Y-%m-%d %H:%M:%S"), "source": str(SRC), "source_app_sha256": sha(SRC / "app.py"),
        "white_bird_forge_sha256": sha(WB_FORGE), "library_items": n_lib, "studio_programs": n_prog, "files": files},
        ensure_ascii=False, indent=1), encoding="utf-8")
    if OUT.exists():
        shutil.rmtree(OUT)
    tmp.rename(OUT)
    if do_seed:
        seed()
    print("\n".join(log))
    print(f"✓ {OUT}  ({len(files)} files, {n_lib} library items, {n_prog} studio programs)")


if __name__ == "__main__":
    main()
