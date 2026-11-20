"""make_golden_dragon.py — builds the source of «التنين الذهبي» (Golden Dragon).

Golden Dragon = the Golden Bird (= the White Bird = the Black Dragon app + patches) + the fusion layer made from the reverse
engineering of every installed skill and of the whole «مهارات» folder (2026-11-15). The Black Dragon, the White Bird and
the Golden Bird are not touched. This script:
  1. loads the Golden Bird forge (..\\..\\الطائر الذهبي\\forge\\make_golden_bird.py, which loads the White Bird forge) and replays
     its pipeline into a temp folder: every White Bird patch, the gold layer, the steer patches, the golden_* modules and
     catalogs. A fix that lands upstream reaches the Golden Dragon on the next regeneration;
  2. gives it its own identity: name, mutex, %APPDATA%\\GoldenDragon, %USERPROFILE%\\.goldendragon-build, install folder
     %USERPROFILE%\\GoldenDragon, Chrome-bridge port 47851, its own extension, the dragon CSS layer and icon;
  3. fixes the stale paths: the engine repo, the app source and the montage folder are found wherever they live now
     (env var, Desktop, Desktop\\مهارات): the folders were moved into «مهارات» on 2026-11-15;
  4. adds the fusion layer: dragon_fusion.py + data\\fusion (index, recipes, lessons), the `fusion` tool, its
     subscription-mode command and the «التنين الذهبي: الانصهار» prompt section;
  5. bundles the fusion data and keeps the test gate (..\\tests\\run_tests.ps1 = the Golden Dragon tests).
Every patch counts its anchor, so a changed upstream stops the script instead of producing a half-patched app.

  python -X utf8 make_golden_dragon.py          regenerate ..\\app (refuses if app\\ was edited by hand; --force overrides)
  python -X utf8 make_golden_dragon.py --seed   also copy settings + chats once from %APPDATA%\\GoldenBird (else WhiteBird, BlackDragon)
"""
import hashlib, importlib.util, json, os, re, shutil, sys, time
from pathlib import Path

FORGE = Path(__file__).resolve().parent
GD = FORGE.parent                                       # ...\مهارات\التنين الذهبي
OUT = GD / "app"
OV = FORGE / "overlay"
FUSION = FORGE / "data" / "fusion"
DESK = GD.parent                                        # «مهارات»: the sibling apps live here now
GB_FORGE = Path(os.environ.get("GOLDEN_BIRD_HOME", DESK / "الطائر الذهبي")) / "forge" / "make_golden_bird.py"
STAMP = OUT / ".gd_generated.json"
UNTRACKED = {"ui/version.txt", ".gd_generated.json"}
NAME_GB, NAME_GD = "الطائر الذهبي", "التنين الذهبي"
PORT_GB, PORT_GD = "47841", "47851"
log = []


def load_golden_bird():
    if not GB_FORGE.is_file():
        raise SystemExit(f"✗ سكربت الطائر الذهبي مش موجود: {GB_FORGE}")
    spec = importlib.util.spec_from_file_location("make_golden_bird", GB_FORGE)
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


def read(p):
    return Path(p).read_text(encoding="utf-8")


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


# ---------------------------------------------------------------- identity: Golden Bird -> Golden Dragon
RENAMES = [(NAME_GB, NAME_GD), ("Golden Bird", "Golden Dragon"), ("GoldenBird", "GoldenDragon"), ("goldenbird", "goldendragon"),
           ("GOLDEN_BIRD_HOME", "GOLDEN_DRAGON_HOME"), (PORT_GB, PORT_GD), ("golden-bird", "golden-dragon"), ("🦅", "🐉")]


def rename(t, where):
    for old, new in RENAMES:
        n = t.count(old)
        if n:
            t = t.replace(old, new)
            log.append(f"  {where}: {old} → {new}: {n}×")
    return t


def fusion_counts():
    idx = json.loads(read(FUSION / "index.json"))
    rec = json.loads(read(FUSION / "recipes.json"))
    les = json.loads(read(FUSION / "lessons.json")) if (FUSION / "lessons.json").is_file() else []
    return idx["counts"], len(rec), les


# ---------------------------------------------------------------- the prompt
IDENTITY_OLD = ("أنت «التنين الذهبي» (أحدث نسخة من تطبيق التنين: كل قدرات الطائر الأبيض، ومعاها استوديو البرامج ومكتبة الموشن اللي "
                "اتجمعت بالهندسة العكسية، بواجهة ذهبية):")
IDENTITY_NEW = ("أنت «التنين الذهبي» (أحدث نسخة من تطبيق التنين: كل قدرات الطائر الذهبي والطائر الأبيض، ومعاهم عقل الانصهار اللي بيجمع "
                "كل المهارات والبرامج والمحركات والمكتبات في فهرس واحد بيوجّه أي طلب لأحسن خلطة، بواجهة ذهبية):")
GB_SECTION_OLD = "## قدرات التنين الذهبي (اتجمعت بالهندسة العكسية لمجلد «مهارات»، 2026-11-14)"
GB_SECTION_NEW = "## الاستوديو ومكتبة الموشن ومزامنة الكلام (موروثة من الطائر الذهبي، اتجمعت بالهندسة العكسية لمجلد «مهارات»، 2026-11-14)"


def _measured():
    """The router's measured accuracy on the owner's hidden real requests, read from the evaluation files (not typed)."""
    out = {}
    for key, name in (("test", "route_eval_test_hybrid.json"), ("old", "route_eval_old_hybrid.json")):
        f = GD / "analysis" / name
        if f.is_file():
            d = json.loads(f.read_text(encoding="utf-8").strip().splitlines()[-1])
            out[key] = (round(d["top1"] * 100), round(d["top3"] * 100))
    return out


def fusion_section(c, n_recipes):
    # Lands inside app.py's SYSTEM f-string: no braces in the resulting text.
    m = _measured()
    acc = ""
    if m:
        acc = ("اتقاس على طلباتك الحقيقية المخفية: الأولى صح " + " و".join(f"{a}%" for a, _ in m.values()) +
               "، والصح في أول 3 بنسبة " + " و".join(f"{b}%" for _, b in m.values()) + ". يعني مرشد قوي مش حكم نهائي.")
    total = sum(c.values())
    return f"""
## التنين الذهبي: الانصهار وبروتوكول الصح من أول مرة (2026-11-15)
- **أداة `fusion`:** فهرس واحد منصهر فيه {total} قدرة: {c.get('skill', 0)} مهارة، و{c.get('playbook', 0)} playbook و{c.get('cmd', 0)} أمر من التنين الأحمر، و{c.get('power', 0)} أداة سوبر باور، و{c.get('tool', 0)} أداة في التطبيق، و{c.get('engine', 0)} محرك تنين، و{c.get('lib', 0)} مكتبة ومستودع، و{c.get('studio', 0)} برامج استوديو، و{c.get('program', 0)} برنامج، و{c.get('re', 0)} أداة تحليل، و{c.get('mcp', 0)} خوادم MCP. وفوقهم {n_recipes} وصفة منصهرة.
  - الموجّه بيفهم الطلب بعقل التنين الأحمر كمان (بيفك الكتابة بالكيبورد الإنجليزي وغلطات الصوت، وبيستخدم الأمثلة اللي اتعلمها). {acc}
  - الأوامر: `brief` و`route` و`check`، و`find` و`show` و`recipes` و`doctor` و`lessons`، و`discover` و`local`.
  - **كل اللي على الجهاز دلوقتي (2026-11-16):** `fusion discover` بيلف على الفولدرات اللي صاحب الجهاز شغّال فيها (سطح المكتب وجواه، والتنزيلات، والمستندات، وقايمة ابدأ، و~/.claude) ويضيف اللي لقاه لنفس الفهرس بأنواع `pc-*`: مهارات برّه المتثبّت، وإضافات Claude، وخوادم MCP، وبرامج واختصارات، وسكربتات، وفولدرات أدوات، ومستودعات، وأرشيفات مهارات. بعدها `find` و`show` و`route` بيشوفوهم (`find` بالنوع `pc` = كل اللي على الجهاز). الفولدرات والقايمة على الجهاز بس (`%APPDATA%/GoldenDragon/discover.json` و`local_units.json`). لو `doctor` قال الكتالوج قديم أو مش موجود، أو صاحب الجهاز قال «نزّلت/حطيت حاجة جديدة»: `discover` الأول. أي `pc-app` أو `pc-script` أو `pc-tool` تشغيله محتاج موافقة، والسكربت يتقري قبل ما يشتغل، و`copy` أو `archive` معناها مش النسخة المتثبّتة.
- **بروتوكول الصح من أول مرة: عقل العلماء وأدوات التنين في سلّم واحد (لأي طلب فيه أكتر من خطوة):**
  ① **افهم وصنّف:** `fusion brief` بالطلب **كامل بكلامك ومعاه سياقه** (مش «كمل» أو «أيوه»). بيقولك العمق: L0 سؤال أو أمر قصير (① و⑧ بس)، وL1 وصفة معروفة (① ② ③ ⑥ ⑧)، وL2 وL3 البروتوكول كله، ومعاه خطة على الديسك بـ `rd.py think start` لو الشغل طويل. اكتب Task وDeliverable وConstraints وDone-when، وسجّل كل كلمة بتقلب المعنى (بوليا: إيه المجهول، وإيه المعطى، وإيه الشرط).
  ② **أسأل ولا أفترض:** الخطر = الأثر × عدم اليقين، كل واحد من 0 لـ 3. لو 6 أو أكتر: سؤال واحد باختيارات، أولها مقترحك ⭐. لو أقل: افترض، وقول الافتراض في أول الرد. واللي يتعرف من ملف أو أمر في أقل من دقيقة ماتسألش عليه.
  ③ **ابدأ من الآخر:** قبل أول أداة اكتب سطر التسليم (الملف ومكانه) ومعيار «صح» اللي هيتقاس.
  ④ **ارجع خطوة لورا:** المعدل الأساسي قبل تفاصيل الحالة (كانيمان: النظرة من برّه)، والمبادئ الأولى قبل «ده اللي بيتعمل عادة». وأي رقم يتفكّك بفيرمي ويتحسب بكود.
  ⑤ **عصف ذهني:** 2 لـ 4 طرق أو تفسيرات مختلفة فعلًا (brief بيقترح 3)، والدليل اللي يفرّق بينهم (هوير: الفرضيات المتنافسة). واختار بسبب مكتوب: الوقت، والمخاطرة، والجودة.
  ⑥ **نفّذ صغير بالوصفة:** اقرا SKILL.md بتاع مهارات الخطوة، واعمل عيّنة رخيصة الأول. كل API أو خيار من المصدر مش من الذاكرة، والباج: إعادة إنتاج مصغّرة، وبعدين السبب الجذري. وكل بوابة تتقاس قبل اللي بعدها. وقبل أي فعل برّه الجهاز (نشر، رفع، مسح، صرف): `rd.py consent "<رسالة صاحب الشغل>"`، ولو مفيش موافقة صريحة وقّف واسأل.
  ⑦ **اكسر حلّك:** تشريح قبل الفشل (كلاين): كل خطر في brief يتقفل بخطوة. اعكس (مانجر): إيه اللي يضمن الفشل؟ كذّب (بوبر): إيه الملاحظة اللي لو ظهرت تهدّ استنتاجك؟ ودوّر عليها فعلًا. وللحاجات الغالية: ناقد مستقل، وكيل ماشافش استنتاجك.
  ⑧ **اتحقق وسلّم واتعلّم:** افحص بطريقة غير اللي طلّعت الناتج. وبعدين `fusion check` (query = الطلب، draft = ردك): صلّح كل ✗، وجاوب أسئلة الناقد بدليل من ردك. النتيجة في أول سطر، وكل جملة مهمة متعلّم عليها: ✅ اتقاس، 🟡 استنتاج، ❓ مجهول (تيتلوك: المعايرة). ولو صاحب الشغل صحّح: `rd.py teach` للتوجيه، و`rd.py learn` للدرس.""" + scholars_section() + """
- **قواعد الفهرس:**
  - استخدم أحدث إصدار من أي مهارة.
  - لو المهارة «ناقصها ملفات»، ماتخترعش الناقص.
  - البرنامج اللي `doctor` بيقول إنه مش موجود، ماتفترضش وجوده.
  - أي وحدة 💲 محتاجة موافقة صريحة على الأداة والسعر.
"""


# Lessons that go into the prompt itself: high severity, frequent, and NOT already in the inherited prompt (checked on
# 2026-11-15: AAC, storyboard, overlay, black frames, focus, cookies all had 0 mentions). The rest: `fusion lessons`.
PROMPT_LESSONS = ["GD-L17", "GD-L18", "GD-L19", "GD-L21", "GD-L23", "GD-L24", "GD-L45", "GD-L62"]


def scholars_section():
    """The thinkers' toolkit line under the protocol (analysis\\thinking_toolkit.json, distilled from the thinking skills
    and books on this PC). The protocol above it is the toolkit's protocol_ar with the fusion commands at each step;
    the per-request tools, their steps and their critic questions come from `fusion brief` / `fusion check`."""
    f = GD / "analysis" / "thinking_toolkit.json"
    if not f.is_file():
        f = FUSION / "thinking.json"  # self-contained fallback: equivalent 22 tools / 8 steps
    if not f.is_file():
        raise SystemExit(f"✗ صندوق أدوات التفكير مش موجود: {f}")
    tk = json.loads(f.read_text(encoding="utf-8"))
    # The older source tree has no thinking_books.json or merge_books helper.
    # Preserve the existing verified toolkit instead of inventing book entries.
    import build_fusion as _fusion_builder
    _books = FORGE / "data" / "thinking_books.json"
    if hasattr(_fusion_builder, "merge_books"):
        tk = _fusion_builder.merge_books(tk)
    elif _books.is_file():
        raise SystemExit("thinking_books.json exists but merge_books is missing; refusing to drop tools")
    else:
        log.append("  thinkers: optional book overlay absent; kept existing toolkit")
    tools, proto = tk.get("tools") or [], tk.get("protocol_ar") or []
    if len(proto) != 8 or len(tools) < 12:      # the protocol in fusion_section is written for these 8 steps
        raise SystemExit(f"✗ thinking_toolkit.json اتغيّر شكله: {len(proto)} خطوة و{len(tools)} أداة (المتوقع 8 خطوات)")
    def short(t):               # «مراحل بوليا الأربعة: افهم، خطّط…» -> «مراحل بوليا الأربعة»; one-word heads keep the full name
        n = str(t.get("name_ar") or t["id"])
        head = n.split(":")[0].strip()
        return (head if len(head.split()) >= 2 else n).replace("\\", "\\\\").replace("{", "(").replace("}", ")")
    names = "، ".join(f"«{short(t)}»" for t in tools)
    return (f"\n- **أدوات العلماء ({len(tools)}، من كتب التفكير والمهارات اللي على الجهاز):** {names}. "
            "`fusion brief` بيختار 2 أو 3 منها لكل طلب بخطواتها وسؤال الناقد بتاعها، و`fusion check` بيسألك أسئلة الناقد قبل الرد."
            "\n- **سبل التفكير (`fusion think`):** سبيل الخيال، والتفكير العميق، والإبداعي، والمنطق والاحتمال، وخطوة بخطوة، "
            "والتحليل، والقرار. لو الطلب فيه «تخيّل» أو «بعمق» أو «احتمال» أو «خطوة بخطوة»، `fusion brief` بيجيب أدوات السبيل ده الأول.")


def mind_additions(lessons):
    by = {x.get("id"): x for x in lessons}
    top = [by[i] for i in PROMPT_LESSONS if i in by] or [x for x in lessons if x.get("severity") == "high"][:8]
    les = ""
    if top:
        les = "\n- **دروس من تاريخ الشغل (أهمها؛ الباقي بـ `fusion lessons`):**\n" + "\n".join(
            "  - " + x["lesson_ar"].replace("\\", "\\\\").replace("{", "(").replace("}", ")") for x in top)   # f-string-safe
    return """
## خبرة التنين الذهبي (منصهرة من المهارات وتاريخ الشغل)
- **طرق شغل مجرّبة:**
  - الأعطال: اعمل reproduce بأمر واحد، وبعدين فرضية واحدة واختبار يكذّبها، وبعدين أصغر تصليح، وبعدين اختبار يمنع رجوعها (مهارة systematic-debugging).
  - أي مسح أو كتابة فوق ملف: افحص الهدف واعمل نسخة الأول (مهارة guarding-destructive-operations).
  - ماتخترعش دالة أو خيار في مكتبة أو برنامج: اقرا `--help` أو الدوكس (مهارة strict-api).
  - الشغل المستقل يتقسم على وكلاء بالتوازي (مهارة dispatching-parallel-agents)، والشغل اللي بيعدّل نفس الملفات يفضل في إيد واحدة.
  - قبل «خلص»: اقرا الناتج بعين ناقد صارم (requesting-code-review للكود، وmotion-design-critique للحركة).""" + les + "\n"


FUSION_TOOL = '''    tool("fusion", "Golden Dragon fusion core: ONE index of every capability on this PC (installed Claude skills, the Red Dragon's "
         "playbooks and commands, KOSIF Superpowers tools, app tools, Black Dragon engines, studio programs, motion libraries, "
         "PATH programs, reverse-engineering tools, MCP servers) plus fused recipes. Routing also asks the installed Red Dragon "
         "how it understands the request (keyboard-layout and dictation fixes, learned examples). action 'brief' = FIRST, before a "
         "multi-step task: the request as understood, the intent sheet to fill, three alternatives, a pre-mortem from the Red "
         "Dragon's known pitfalls and the owner's lessons, thinking tools, the gates. 'route' = the recipe(s) with steps, gates, "
         "approvals, ambiguity warning. 'check' = LAST, before replying: self-critique of your draft answer (query = the request, "
         "draft = your answer). 'find' (optional kind: skill, tool, engine, studio, lib, program, re, mcp, playbook, cmd, power, "
         "or pc / pc-skill, pc-plugin, pc-mcp, pc-app, pc-script, pc-tool, pc-repo, pc-pack for what discover found on this PC), "
         "'show' one id, 'recipes', 'doctor' (live check of this PC), 'lessons', 'think' (the Arabic thinking paths from the books: "
         "imagination, deep, creative, logic/probability, step by step, analysis, decision; query = a path or empty for the map). 'discover' = walk the owner's folders now and "
         "add every skill, plugin, MCP server, program, shortcut, script, tool folder, repo and skill archive to the index (run it "
         "when doctor says the PC catalog is missing or stale, or the owner added something); 'local' = list that catalog "
         "(optional kind). 'audit' = passive catalog evidence and recipe-link verification without running indexed tools. "
         "'probe_media' = inspect ONE local audio/video file using FFprobe (path required; no network or transcode). "
         "'inspect_binary_imports' = static REA PE import scan of ONE local Windows binary (path required; no execution). "
         "'transcode_media' = FFmpeg convert local audio/video to a NEW TEMP file (path and optional profile; never overwrite input). "
         "'native_status' = list ONLY explicitly implemented adapters and passive prerequisites (not proof of runtime success). "
         "'native_exec' = invoke one registered native operation using 'operation' and optional local 'path'; "
         "creating a new temporary output requires approve_new_file=true. "
         "Native operation blender.render creates a fixed mechanical_gear or machine_piston scene using Blender; "
         "pass preset and resolution=256,512,1024; no user scripts. "
         "Read-only except discover, which writes only its own catalog in %APPDATA%\\\\GoldenDragon.",
         {"action": {"type": "string", "enum": ["brief", "route", "check", "find", "show", "recipes", "doctor", "lessons", "think", "stats",
                                                "discover", "local", "audit", "probe_media", "inspect_binary_imports", "transcode_media", "native_status", "native_exec"]},
          "query": S, "draft": S, "id": S, "kind": S, "path": S, "profile": S, "preset": S, "resolution": {"type":"integer", "enum":[256,512,1024]}, "operation": S, "approve_new_file": {"type":"boolean"}, "limit": {"type": "integer", "minimum": 1, "maximum": 30}}, ["action"]),
'''

FUSION_DISPATCH = '''def fusion_dispatch(a):
    """«التنين الذهبي» fusion tool (generated by forge/make_golden_dragon.py): read-only views of the fused index."""
    import dragon_fusion as fz
    act = a.get("action") or ""
    q = a.get("query") or a.get("id") or ""
    try:
        if act == "route":
            if not q.strip():
                raise ValueError("INVALID_JSON: query")
            return fz.md_route(q), False
        if act == "brief":
            if not q.strip():
                raise ValueError("INVALID_JSON: query")
            return fz.md_brief(q), False
        if act == "check":
            return fz.md_check(q, a.get("draft") or ""), False
        if act == "find":
            return fz.md_find(q, a.get("kind") or None, int(a.get("limit") or 10)), False
        if act == "show":
            return fz.md_show(a.get("id") or q), False
        if act == "recipes":
            return fz.md_recipes(), False
        if act == "doctor":
            return fz.md_doctor(), False
        if act == "lessons":
            return fz.md_lessons(q, int(a.get("limit") or 8)), False
        if act == "think":
            return fz.md_think(q), False
        if act == "stats":
            return json.dumps(fz.stats(), ensure_ascii=False), False
        if act == "discover":
            return fz.md_discover(), False
        if act == "local":
            return fz.md_local(a.get("kind") or None, int(a.get("limit") or 40)), False
        if act == "native_status":
            from pathlib import Path as _Path
            import native_registry as _native
            return _native.native_report_json(_Path(__file__).resolve().parent), False
        if act == "native_exec":
            from pathlib import Path as _Path
            import native_registry as _native
            operation = (a.get("operation") or "").strip()
            if not operation:
                raise ValueError("INVALID_JSON: operation is required for native_exec")
            outcome = _native.native_execute(
                _Path(__file__).resolve().parent, operation,
                local_path=a.get("path"), profile=a.get("profile") or "mp4-compatible",
                preset=a.get("preset") or "mechanical_gear", resolution=a.get("resolution") or 512,
                approve_new_file=a.get("approve_new_file") is True)
            return json.dumps(outcome, ensure_ascii=False), False
        if act == "audit":
            from pathlib import Path as _Path
            import gd_runtime as _gd_runtime
            _here = _Path(__file__).resolve().parent
            _core = _gd_runtime.GoldenDragonCore(
                _here, _here / "fusion" / "index.json",
                _here / "fusion" / "recipes.json")
            return json.dumps(_core.execute("catalog.audit"), ensure_ascii=False), False
        if act == "inspect_binary_imports":
            import gd_runtime as _gd_runtime
            from pathlib import Path as _Path
            _local_path = (a.get("path") or "").strip()
            if not _local_path:
                raise ValueError("INVALID_JSON: path is required for inspect_binary_imports")
            _core = _gd_runtime.GoldenDragonCore(_Path(__file__).resolve().parent,
                                                  binary=_Path(_local_path))
            return json.dumps(_core.execute("binary.imports"), ensure_ascii=False), False
        if act == "transcode_media":
            import gd_runtime as _gd_runtime
            from pathlib import Path as _Path
            _local_path = (a.get("path") or "").strip()
            if not _local_path:
                raise ValueError("INVALID_JSON: path is required for transcode_media")
            _core = _gd_runtime.GoldenDragonCore(_Path(__file__).resolve().parent,
                                                  media=_Path(_local_path),
                                                  profile=a.get("profile") or "mp4-compatible")
            return json.dumps(_core.execute("media.transcode"), ensure_ascii=False), False
        if act == "probe_media":
            import gd_runtime as _gd_runtime
            from pathlib import Path as _Path
            _local_path = (a.get("path") or "").strip()
            if not _local_path:
                raise ValueError("INVALID_JSON: path is required for probe_media")
            _core = _gd_runtime.GoldenDragonCore(_Path(__file__).resolve().parent,
                                                  media=_Path(_local_path))
            return json.dumps(_core.execute("media.probe"), ensure_ascii=False), False
        raise ValueError("INVALID_JSON: action must be brief, route, check, find, show, recipes, doctor, lessons, think, stats, discover, local, audit, probe_media, inspect_binary_imports, transcode_media, native_status or native_exec")
    except (KeyError, FileNotFoundError, ValueError, OSError, ImportError) as e:
        return f"✗ {e.args[0] if e.args else e}", True


def skills_index():'''

CC_FUSION = ("\n- fusion: `python -X utf8 \"{APP_SOURCE}\\\\dragon_fusion.py\" brief \"<الطلب>\" | route \"...\" | find \"...\" "
             "[--kind K] | show ID | recipes | doctor | lessons \"...\" | check --request \"...\" --draft FILE | discover | local [KIND]`. "
             "brief أول خطوة في أي طلب فيه أكتر من خطوة، وcheck قبل الرد، وdiscover لما الكتالوج المحلي قديم.")

MCP_REPO_OLD = '''if not REPO.exists():
    REPO = HOME / "Desktop" / "التنين الأسود"
'''
MCP_REPO_NEW = '''if not REPO.exists():                    # «التنين الذهبي»: the folder moved into «مهارات» on 2026-11-15
    REPO = next((c for c in (HOME / "OneDrive" / "Desktop" / "مهارات" / "التنين الأسود", HOME / "Desktop" / "التنين الأسود",
                             HOME / "Desktop" / "مهارات" / "التنين الأسود") if c.exists()), HOME / "Desktop" / "التنين الأسود")
'''
# The inherited mind had its own 7-rung ladder and sent multi-step work to `rd.py think`; one ladder now (the protocol in
# fusion_section), and the Red Dragon's on-disk plan is kept for the deep requests (L2/L3) where it earns its cost.
LADDER_OLD = ("- **سلّم التفكير، وماتنطّش درجة:**\n"
              "  1. فهم.\n"
              "  2. 2 أو 3 طرق أو فرضيات مختلفة فعلًا، واختار واحدة بسبب مكتوب.\n"
              "  3. تشريح قبل الفشل: إيه أرجح 3 أسباب تخلّي التسليم يترفض؟ واقفل كل سبب بفحص.\n"
              "  4. خطة فيها أرخص اختبار يكشف الغلط بدري.\n"
              "  5. نفّذ على عيّنة صغيرة الأول، وبعدين الشغل كله.\n"
              "  6. تحقق مستقل بأداة غير اللي طلّعت النتيجة: قياس، أو إعادة حساب، أو عين على الفريم.\n"
              "  7. معايرة: ✅ دليل، و🟡 استنتاج بنسبة تقريبية، و❓ مجهول ومعاه الخطوة اللي تحسمه.\n")
LADDER_NEW = ("- **سلّم التفكير، وماتنطّش درجة:** هو «بروتوكول الصح من أول مرة» (① لـ ⑧) في قسم الانصهار فوق، "
              "والعمق اللي `fusion brief` بيقوله بيحدد أنهي درجات تمشي عليها.\n")
THINK_HEAD_OLD = "- **الطلب اللي فيه أكتر من خطوة:** ابدأ بـ `python -X utf8 "
THINK_HEAD_NEW = ("- **الطلب اللي فيه أكتر من خطوة:** ابدأ بـ `fusion brief`. ولو العمق L2 أو L3 والشغل طويل، اعمل كمان خطة "
                  "على الديسك بـ `python -X utf8 ")
THINK_TAIL_OLD = 'think start "<الطلب>"`، وقبل التسليم شغّل `think check`.'
THINK_TAIL_NEW = ('think start "<الطلب>"` (فيها مجلس ونقد وأوقات متعايرة، و`think check` بيرفضها لو ناقصة). '
                  "وفي كل الأحوال، قبل الرد: `fusion check`.")
SEED_OLD = 'for n in ("WhiteBird", "BlackDragon") if (dst.parent / n / "settings.json").exists()'
SEED_NEW = 'for n in ("GoldenBird", "WhiteBird", "BlackDragon") if (dst.parent / n / "settings.json").exists()'


def patch_app(t, counts, n_recipes, lessons):
    t = rename(t, "app.py")
    # Avoid loading the Anthropic SDK's ~25s dependency chain before the GUI opens.
    # First actual API call still imports the genuine SDK, preserving behavior.
    t = sub(t, "\nimport anthropic\n",
            "\nimport importlib as _gd_importlib\n"
            "class _GoldenLazyAnthropic:\n"
            "    def __getattr__(self, attr):\n"
            "        module = _gd_importlib.import_module('anthropic')\n"
            "        globals()['anthropic'] = module\n"
            "        return getattr(module, attr)\n"
            "anthropic = _GoldenLazyAnthropic()\n",
            1, "lazy-load Anthropic SDK at first API request")
    t = sub(t, "generated from the Black Dragon app by forge/make_white_bird.py + forge/make_golden_bird.py.",
            "generated from the Black Dragon app by forge/make_white_bird.py + forge/make_golden_bird.py + forge/make_golden_dragon.py.",
            1, "docstring")
    t = sub(t, IDENTITY_OLD, IDENTITY_NEW, 1, "identity")
    t = sub(t, GB_SECTION_OLD, GB_SECTION_NEW, 1, "inherited golden section title")
    t = sub(t, "\n## عقل التنين الذهبي (تفكير فائق بالعربي والإنجليزي)",
            fusion_section(counts, n_recipes) + "\n## عقل التنين الذهبي (تفكير فائق بالعربي والإنجليزي)", 1, "fusion section")
    t = sub(t, "\n## عقل التنين الأحمر", mind_additions(lessons) + "\n## عقل التنين الأحمر", 1, "fused experience in the mind")
    t = sub(t, LADDER_OLD, LADDER_NEW, 1, "one thinking ladder (the inherited one points to the protocol)")
    t = sub(t, THINK_HEAD_OLD, THINK_HEAD_NEW, 1, "multi-step work starts with fusion brief")
    t = sub(t, THINK_TAIL_OLD, THINK_TAIL_NEW, 1, "think start/check by depth, fusion check always")
    t = sub(t, '[--fps 30]`.', '[--fps 30]`.' + CC_FUSION, 1, "subscription mapping: fusion")
    t = sub(t, '    tool("rebuild_app",', FUSION_TOOL + '    tool("rebuild_app",', 1, "fusion tool")
    t = sub(t, "            return golden_dispatch(self, name, a, cid)\n",
            "            return golden_dispatch(self, name, a, cid)\n        if name == \"fusion\":\n            return fusion_dispatch(a)\n",
            1, "dispatch hook")
    t = sub(t, "\ndef skills_index():", "\n" + FUSION_DISPATCH, 1, "fusion_dispatch()")
    if "def _home_of(env, name):" not in t or 'APP_SOURCE = _home_of("GOLDEN_DRAGON_HOME", "التنين الذهبي") / "app"' not in t:
        raise SystemExit("✗ the Golden Bird forge did not provide the path resolver (_home_of)")
    log.append("  paths follow the moved folders: inherited from the Golden Bird forge")
    t = sub(t, "`where.exe <الاسم>`", "`fusion show program:<id>` أو `where.exe <الاسم>`", 1, "program paths via fusion")
    t = sub(t, SEED_OLD, SEED_NEW, 1, "first run copies the Golden Bird's data first")
    t = sub(t, 'if src.name in ("BlackDragon", "WhiteBird"):', 'if src.name in ("BlackDragon", "WhiteBird", "GoldenBird"):', 1,
            "seed: drop spend counters")
    return t


def patch_ui(t, counts, n_recipes):
    t = rename(t, "index.html")
    t = sub(t, "</style>", read(OV / "golden-dragon.css") + "</style>", 1, "dragon design layer")
    t = re.sub(r'<span class="gb-badge">[^<]*</span>',
               f'<span class="gd-badge">🐉 جديد: عقل الانصهار — {counts.get("skill", 0)} مهارة و{sum(counts.values())} قدرة '
               f'و{n_recipes} وصفة في فهرس واحد</span>', t, count=1)
    if "gd-badge" not in t:
        raise SystemExit("✗ welcome badge not replaced")
    log.append("  index.html: fusion badge 1×")
    return t


def patch_extension(root):
    from PIL import Image
    big = Image.open(OV / "icon" / "gd-512.png").convert("RGBA")
    for f in sorted(root.rglob("*")):
        if f.suffix.lower() in (".js", ".json", ".html", ".css", ".txt"):
            o = read(f)
            t = rename(o, f"extension {f.name}")
            if t != o:
                write(f, t)
        elif f.suffix.lower() == ".png":
            w, h = Image.open(f).size
            big.resize((w, h), Image.LANCZOS).save(f)
            log.append(f"  extension {f.name}: dragon icon {w}×{h}")
    if f"const PORT = {PORT_GD};" not in read(root / "background.js"):
        raise SystemExit("✗ extension port was not changed")


def patch_build(t):
    t = rename(t, "build.ps1")
    codes_gb = ",".join(f"0x{ord(c):x}" for c in NAME_GB)
    codes_gd = ",".join(f"0x{ord(c):x}" for c in NAME_GD)
    t = sub(t, codes_gb, codes_gd, 1, "shortcut name")
    t = sub(t, '--add-data "$here\\golden;golden"', '--add-data "$here\\golden;golden" --add-data "$here\\fusion;fusion"', 1, "bundle fusion data")
    t = sub(t, "--hidden-import golden_tools", "--hidden-import golden_tools --hidden-import anthropic --hidden-import dragon_fusion --hidden-import gd_discover --hidden-import gd_runtime --hidden-import capability_ledger --hidden-import audit_tree --hidden-import native_registry --hidden-import blender_engine", 1, "bundle dragon_fusion and unified runtime")
    return t


# STRICT: anything that would make the Golden Dragon talk to, or share data with, its siblings.
STRICT = re.compile(r"478[234]1|Local\\+(?:WhiteBird|BlackDragon|GoldenBird)|/ \"(?:WhiteBird|BlackDragon|GoldenBird)\" / \"settings\.json\""
                    r"|\.whitebird-build|\.goldenbird-build|bd_build")
LEFTOVERS = re.compile(r"GoldenBird|goldenbird|Golden Bird|الطائر الذهبي|golden-bird|🦅|WhiteBird|whitebird|White Bird|الطائر الأبيض|white-bird|🕊")
# descriptive mentions on purpose, each reviewed on 2026-11-15; more = a new leftover:
#   app.py 7 = identity lineage ×2, inherited section title ×1, first-run copy order ×2, spend-counter reset ×2
#   ui/index.html 3 = CSS comments (Golden Bird layer ×2 «White Bird», dragon layer ×1 «Golden Bird»)
#   README.md 2 = lineage paths; dragon_fusion.py 2 = comments; golden_tools.py 1 = docstring
# Catalog data (golden/*.json, fusion/*.json) holds evidence paths (.goldenbird-re) and the moved-folder names doctor
# reports, so it gets the STRICT check only.
ALLOWED_LEFTOVER = {"app.py": 7, "golden_tools.py": 1, "README.md": 2, "ui/index.html": 3, "dragon_fusion.py": 2}
DATA_DIRS = ("golden/", "fusion/")


def check_leftovers(tmp, report=False):
    bad, seen = [], {}
    for p in tmp.rglob("*"):
        if p.is_file() and p.suffix.lower() in (".py", ".html", ".js", ".json", ".css", ".ps1", ".md", ".txt"):
            rel = p.relative_to(tmp).as_posix()
            text = p.read_text(encoding="utf-8-sig", errors="replace")
            # the lessons quote the three ports to explain the isolation rule; descriptive text, never read as config
            strict = [] if rel == "fusion/lessons.json" else STRICT.findall(text)
            if strict:
                bad.append(f"{rel}: STRICT {strict[:3]}")
            n = 0 if rel.startswith(DATA_DIRS) else len(LEFTOVERS.findall(text))
            if n:
                seen[rel] = n
            if n > ALLOWED_LEFTOVER.get(rel, 0):
                bad.append(f"{rel}: {n} (allowed {ALLOWED_LEFTOVER.get(rel, 0)}): {sorted(set(LEFTOVERS.findall(text)))}")
    if report:
        print("leftover counts:", seen)
    if bad:
        raise SystemExit("✗ فيه أسماء أو بورت الإخوات لسه موجودة:\n  " + "\n  ".join(bad))
    log.append(f"  leftovers: only the allowed lineage mentions {seen}")


def seed():
    appdata = Path(os.environ["APPDATA"])
    dst = appdata / "GoldenDragon"
    src = next((appdata / n for n in ("GoldenBird", "WhiteBird", "BlackDragon") if (appdata / n / "settings.json").exists()), None)
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
    force, do_seed, report = "--force" in sys.argv, "--seed" in sys.argv, "--report" in sys.argv
    gb = load_golden_bird()
    wb = gb.load_white_bird()
    SRC = wb.SRC
    if not (SRC / "app.py").exists():
        raise SystemExit(f"✗ كود التنين مش موجود في {SRC}")
    for need in (FUSION / "index.json", FUSION / "recipes.json", OV / "icon" / "golden-dragon.ico", OV / "golden-dragon.css"):
        if not need.is_file():
            raise SystemExit(f"✗ {need} مش موجود. شغّل build_fusion.py و make_icon.py الأول.")
    n_lib, n_ready, n_prog, programs = gb.catalog_counts()
    counts, n_recipes, lessons = fusion_counts()
    guard(force)
    tmp = GD / "app.__new__"
    shutil.rmtree(tmp, ignore_errors=True)
    if tmp.exists():
        raise SystemExit(f"✗ الفولدر المؤقت {tmp} مقفول (ترمنال أو برنامج فاتحه). اقفله وجرّب تاني.")
    shutil.copytree(SRC, tmp, ignore=shutil.ignore_patterns(".ruff_cache", "__pycache__", "*.bak*", "*.pyc", "dist", "build", "build.ps1",
                                                            ".rd-lock.json", "*.tmp"))
    log.append(f"copied {SRC} (app.py sha256 {sha(SRC / 'app.py')[:16]}…)")
    # 1) every White Bird patch, exactly as the White Bird forge applies them
    for name, fn in (("app.py", wb.patch_app), ("control.py", wb.patch_control), ("mcp_control.py", wb.patch_mcp_control),
                     ("mcp_dragon.py", wb.patch_mcp_dragon), ("ui/index.html", wb.patch_ui)):
        write(tmp / name, fn(read(tmp / name)))
    wb.patch_extension(tmp / "chrome_extension")
    # 2) the Golden Bird layer, exactly as the Golden Bird forge applies it
    write(tmp / "app.py", gb.patch_app(read(tmp / "app.py"), n_lib, n_ready, programs))
    for name in ("control.py", "mcp_control.py", "mcp_dragon.py"):
        write(tmp / name, gb.rename(read(tmp / name), name))
    write(tmp / "ui/index.html", gb.patch_ui(read(tmp / "ui/index.html"), n_lib))
    gb.patch_extension(tmp / "chrome_extension")
    write(tmp / "app.py", gb.steer.patch_app(read(tmp / "app.py"), gb.sub))
    write(tmp / "ui/index.html", gb.steer.patch_ui(read(tmp / "ui/index.html"), gb.sub))
    log.append(f"golden bird + white bird patches: {len(gb.log)} + {len(wb.log)} steps")
    # 3) the Golden Dragon on top
    write(tmp / "app.py", patch_app(read(tmp / "app.py"), counts, n_recipes, lessons))
    for name in ("control.py", "mcp_control.py"):
        write(tmp / name, rename(read(tmp / name), name))
    write(tmp / "mcp_dragon.py", sub(rename(read(tmp / "mcp_dragon.py"), "mcp_dragon.py"), MCP_REPO_OLD, MCP_REPO_NEW, 1,
                                     "mcp_dragon: engine repo follows the move"))
    write(tmp / "ui/index.html", patch_ui(read(tmp / "ui/index.html"), counts, n_recipes))
    # 2026-11-16 gd_patches\gd_extras.py: full-text chat search, 📌 pinned chats, «صح من أول مرة» delivery check, API thinking display
    _gx_spec = importlib.util.spec_from_file_location("gd_extras", FORGE / "gd_patches" / "gd_extras.py")
    gx = importlib.util.module_from_spec(_gx_spec)
    _gx_spec.loader.exec_module(gx)
    write(tmp / "app.py", gx.patch_app(read(tmp / "app.py"), sub))
    write(tmp / "ui/index.html", gx.patch_ui(read(tmp / "ui/index.html"), sub))
    # 2026-11-16 gd_patches\gd_reviewer.py: 🧐 a second, independent agent reviews the written thinking and corrects it mid-run
    _rv_spec = importlib.util.spec_from_file_location("gd_reviewer", FORGE / "gd_patches" / "gd_reviewer.py")
    rv = importlib.util.module_from_spec(_rv_spec)
    _rv_spec.loader.exec_module(rv)
    write(tmp / "app.py", rv.patch_app(read(tmp / "app.py"), sub))
    write(tmp / "ui/index.html", rv.patch_ui(read(tmp / "ui/index.html"), sub))
    # 2026-11-16 gd_patches\gd_markitdown.py: 📄 attached PDF/Word/PowerPoint/Excel/EPUB -> Markdown (MarkItDown) before the model reads it
    _md_spec = importlib.util.spec_from_file_location("gd_markitdown", FORGE / "gd_patches" / "gd_markitdown.py")
    mdp = importlib.util.module_from_spec(_md_spec)
    _md_spec.loader.exec_module(mdp)
    write(tmp / "app.py", mdp.patch_app(read(tmp / "app.py"), sub))
    # Anatomy: opt-in local skill bridge, reproducible tools/dispatch and permission-gated scaffold
    _an_spec = importlib.util.spec_from_file_location("gd_anatomy", FORGE / "gd_patches" / "gd_anatomy.py")
    an = importlib.util.module_from_spec(_an_spec)
    _an_spec.loader.exec_module(an)
    write(tmp / "app.py", an.patch_app(read(tmp / "app.py"), sub))
    # 2026-11-19 (before the knowledge patch, which adds a second </style>) gd_patches\gd_custom_api.py: 🔌 API مخصص (OpenRouter or any OpenAI-compatible site); key in the Windows keyring
    _cx_spec = importlib.util.spec_from_file_location("gd_custom_api", FORGE / "gd_patches" / "gd_custom_api.py")
    cx = importlib.util.module_from_spec(_cx_spec)
    _cx_spec.loader.exec_module(cx)
    write(tmp / "app.py", cx.patch_app(read(tmp / "app.py"), sub))
    write(tmp / "ui/index.html", cx.patch_ui(read(tmp / "ui/index.html"), sub))
    # Independent verified read-only knowledge runtime (committed source + bundle).
    _kk_spec = importlib.util.spec_from_file_location("gd_knowledge", FORGE / "gd_patches" / "gd_knowledge.py")
    kk = importlib.util.module_from_spec(_kk_spec)
    _kk_spec.loader.exec_module(kk)
    if not (GD / "knowledge" / "golden-dragon-runtime.zip").is_file():
        raise SystemExit("Missing verified independent knowledge bundle")
    write(tmp / "app.py", kk.patch_app(read(tmp / "app.py")))
    write(tmp / "ui/index.html", kk.patch_ui(read(tmp / "ui/index.html")))
    shutil.copy2(OV / "golden_knowledge_bridge.py", tmp / "golden_knowledge_bridge.py")
    shutil.copy2(FORGE / "golden_dragon_runtime.py", tmp / "golden_dragon_runtime.py")
    log.append("  Independent knowledge bridge: search UI + tool + read-only database")
    patch_extension(tmp / "chrome_extension")
    for mod in sorted(gb.MODULES.glob("golden_*.py")):                # the Golden Bird modules, renamed (studio home etc.)
        write(tmp / mod.name, rename(read(mod), mod.name))
    shutil.copy2(FORGE / "modules" / "dragon_fusion.py", tmp / "dragon_fusion.py")
    shutil.copy2(FORGE / "modules" / "gd_discover.py", tmp / "gd_discover.py")      # 2026-11-16: «discover» (PC catalog)
    shutil.copy2(FORGE / "modules" / "anatomy_bridge.py", tmp / "anatomy_bridge.py")  # user-installed MIT kit, opt-in
    shutil.copy2(FORGE / "modules" / "gd_core_integrations.py", tmp / "gd_core_integrations.py")  # viral video + replica core
    # Native unified core (read-only): no MCP bridge, imported by the fusion audit action.
    for module in ("runtime.py", "capability_ledger.py", "audit_tree.py", "native_registry.py", "blender_engine.py"):
        shutil.copy2(FORGE / "unified_core" / module,
                     tmp / ("gd_runtime.py" if module == "runtime.py" else module))
    (tmp / "golden").mkdir()
    for f in ("library.json", "studio.json"):
        shutil.copy2(gb.DATA / f, tmp / "golden" / f)
    (tmp / "fusion").mkdir()
    for f in sorted(x for x in FUSION.iterdir() if x.is_file()):
        shutil.copy2(f, tmp / "fusion" / f.name)
    # 2026-11-16: every dragon skill was fused into ONE skill, ~/.claude/skills/golden-dragon (red-dragon is a junction shim)
    for name in ("app.py", "brain.py"):
        p = tmp / name
        if p.exists():
            t0 = read(p)
            t1 = (t0.replace("skills\\\\red-dragon\\\\", "skills\\\\golden-dragon\\\\").replace("skills\\red-dragon\\", "skills\\golden-dragon\\")
                    .replace("skills/red-dragon", "skills/golden-dragon")
                    .replace('CANDIDATES = (("red-dragon", "rd.py"),', 'CANDIDATES = (("golden-dragon", "rd.py"), ("red-dragon", "rd.py"),')
                    .replace("مهارة التنين الأحمر مش متثبتة", "مهارة التنين الذهبي مش متثبتة"))
            if t1 != t0:
                write(p, t1)
                log.append(f"  {name}: dragon skill paths -> golden-dragon")
    for py in sorted(p.name for p in tmp.glob("*.py")):
        compile(read(tmp / py), py, "exec")                             # syntax gate before anything is replaced
    compile(read(tmp / "fusion" / "rd_bridge.py"), "rd_bridge.py", "exec")
    (tmp / "ui" / "fonts").mkdir(exist_ok=True)
    for f in (wb.OV / "fonts").iterdir():
        shutil.copy2(f, tmp / "ui" / "fonts" / f.name)
    shutil.copy2(OV / "icon" / "gd-256.png", tmp / "ui" / "golden-dragon.png")
    shutil.copy2(OV / "icon" / "golden-dragon.ico", tmp / "ui" / "golden-dragon.ico")
    for old in ("red-dragon.ico", "red-dragon.png", "white-bird.ico", "white-bird.png", "golden-bird.ico", "golden-bird.png"):
        (tmp / "ui" / old).unlink(missing_ok=True)
    build = gb.steer.patch_build(gb.patch_build(wb.patch_build(wb.build_ps1())), gb.sub)
    (tmp / "build.ps1").write_text(kk.patch_build(an.patch_build(patch_build(build), sub)), encoding="utf-8-sig")
    (tmp / "README.md").write_text(
        f"# {NAME_GD}: كود التطبيق\n\nالمجلد ده **متولّد**: كود التنين الأسود ← تعديلات `..\\..\\الطائر الأبيض\\forge\\make_white_bird.py` ← "
        "تعديلات `..\\..\\الطائر الذهبي\\forge\\make_golden_bird.py` ← طبقة `..\\forge\\make_golden_dragon.py`. أي تعديل دايم يتحط في "
        "`forge`، وبعدين ولّد من جديد وابني بـ `build.ps1`.\n", encoding="utf-8")
    check_leftovers(tmp, report)
    files = {p.relative_to(tmp).as_posix(): sha(p) for p in tmp.rglob("*") if p.is_file()}
    files = {k: v for k, v in files.items() if k not in UNTRACKED}
    (tmp / ".gd_generated.json").write_text(json.dumps({
        "generated": time.strftime("%Y-%m-%d %H:%M:%S"), "source": str(SRC).replace(str(Path.home()), "%USERPROFILE%"), "source_app_sha256": sha(SRC / "app.py"),
        "white_bird_forge_sha256": sha(wb.FORGE / "make_white_bird.py"), "golden_bird_forge_sha256": sha(GB_FORGE),
        "fusion_index_sha256": sha(FUSION / "index.json"), "fusion_counts": counts, "recipes": n_recipes,
        "lessons": len(lessons), "files": files,
        "knowledge_integration": {
            "mode": "generated-source-backed",
            "bundle_sha256": sha(GD / "knowledge" / "golden-dragon-runtime.zip"),
            "read_only": True,
            "bridge": "golden_knowledge_bridge.py"}}, ensure_ascii=False, indent=1), encoding="utf-8")
    if OUT.exists():
        shutil.rmtree(OUT)
    tmp.rename(OUT)
    if do_seed:
        seed()
    print("\n".join(log))
    print(f"✓ {OUT}  ({len(files)} files, {sum(counts.values())} fused units, {n_recipes} recipes, {len(lessons)} lessons)")


if __name__ == "__main__":
    main()
