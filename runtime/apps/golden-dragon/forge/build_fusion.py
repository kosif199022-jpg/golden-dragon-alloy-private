"""build_fusion.py — builds the fused index of «التنين الذهبي» (forge\\data\\fusion\\*.json).

Sources (all read-only; nothing from a skill or an archive is executed):
  data\\skills.json            scan_skills.py: every installed skill, versions, flags
  ..\\..\\الطائر الذهبي\\forge\\data  the Golden Bird catalogs: motion/web/AI library (154) + studio programs (10)
  ..\\..\\الطائر الذهبي\\app\\app.py  the app's own tools (parsed from its tool(...) table) + the new `fusion` tool
  python -m dragon engines     the Black Dragon engines, from wherever the engine repo lives now
  ~/re-tools/retool.py list    the reverse-engineering toolbox
  PATH                         the programs the owner's prompt lists (shutil.which: status ok / missing)
  recipes.py                   the fused pipelines; EVERY id they name must exist (else the build stops)
  ..\\analysis\\lessons.json     lessons mined from the owner's history (optional)

  python -X utf8 build_fusion.py
"""
import json
import re
import shutil
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

FORGE = Path(__file__).resolve().parent
GD = FORGE.parent
DESK = GD.parent                                     # «مهارات»: the siblings live here now
GB = DESK / "الطائر الذهبي"
OUT = FORGE / "data" / "fusion"
HOME = Path.home()
sys.path.insert(0, str(FORGE))
from recipes import RD_MAP, RECIPES                  # noqa: E402

BOOKS = FORGE / "data" / "thinking_books.json"      # thinking tools distilled from the books king sent (kept in the repo)


def merge_books(toolkit, books=None):
    """The thinkers' toolkit + data\\thinking_books.json: new tools appended (an id already in the toolkit wins), each
    protocol step gets the book tools that serve it, the Arabic «سبل التفكير» paths ride along. Idempotent."""
    if books is None:
        if not BOOKS.is_file():
            return toolkit
        books = json.loads(BOOKS.read_text(encoding="utf-8"))
    tk = dict(toolkit)
    have = {t.get("id") for t in tk.get("tools") or []}
    tk["tools"] = list(tk.get("tools") or []) + [t for t in books.get("tools") or [] if t.get("id") not in have]
    proto = list(tk.get("protocol_ar") or [])
    for i, add in enumerate(books.get("protocol_add") or []):
        if add and i < len(proto) and add not in proto[i]:
            proto[i] = f"{proto[i]} · من الكتب: {add}"
    tk["protocol_ar"] = proto
    ids = {t.get("id") for t in tk["tools"]}
    missing = [(p["id"], x) for p in books.get("paths") or [] for x in p.get("tools") or [] if x not in ids]
    if missing:
        raise SystemExit(f"✗ thinking_books.json: سبيل بيشاور على أداة مش موجودة {missing[:5]}")
    tk["paths"] = books.get("paths") or []
    tk["sources_read"] = list(dict.fromkeys(list(tk.get("sources_read") or []) + list(books.get("sources_books") or [])))
    return tk


PROGRAMS = [   # (id, command probed on PATH, Arabic line)
    ("ffmpeg", "ffmpeg", "فيديو وصوت: تحويل وتقطيع وفلاتر وترميز"), ("ffprobe", "ffprobe", "قياس ملفات الميديا"),
    ("blender", "blender", "Blender 5.2 من غير واجهة (-b)"), ("melt", "melt", "محرك Kdenlive للمونتاج من سطر الأوامر"),
    ("natron", "NatronRenderer", "كومبوزيتنج بالنودز من غير واجهة"), ("mkvmerge", "mkvmerge", "دمج وتقسيم MKV"),
    ("scenedetect", "scenedetect", "كشف القطعات في الفيديو"), ("auto-editor", "auto-editor", "قص السكوت والوقفات تلقائي"),
    ("magick", "magick", "ImageMagick: معالجة صور بالأوامر"), ("gimp", "gimp-console-3.2", "GIMP من غير واجهة"),
    ("inkscape", "inkscape", "رسوم SVG وتصديرها"), ("upscayl", "upscayl-bin", "تكبير الصور 4×"),
    ("krita", "kritarunner", "Krita بالسكربت"), ("darktable", "darktable-cli", "تحميض صور RAW"),
    ("rawtherapee", "rawtherapee-cli", "تحميض صور RAW"), ("rembg", "rembg", "شيل خلفية الصور"),
    ("exiftool", "exiftool", "البيانات الوصفية للصور والفيديو"), ("whisperx", "whisperx", "تفريغ بتوقيت الكلمة"),
    ("faster-whisper", "py:faster_whisper", "تفريغ سريع (مكتبة بايثون: from faster_whisper import WhisperModel)"), ("demucs", "demucs", "فصل الصوت عن الموسيقى"),
    ("deep-filter", "deep-filter", "تنضيف الصوت من الدوشة"), ("edge-tts", "edge-tts", "تحويل نص لصوت"),
    ("yt-dlp", "yt-dlp", "تحميل فيديو من آلاف المواقع"), ("aria2c", "aria2c", "تحميل بأكتر من اتصال"),
    ("pandoc", "pandoc", "تحويل المستندات بين الصيغ"), ("7z", "7z", "فك وضغط الأرشيفات"), ("jq", "jq", "فلترة JSON"),
    ("rg", "rg", "بحث سريع جوه الملفات"), ("gh", "gh", "GitHub من سطر الأوامر"), ("node", "node", "Node.js"),
    ("git", "git", "Git"), ("python", "python", "بايثون (numpy وopencv وmediapipe وtorch وplaywright وpython-pptx…)"),
]
MCP = [   # (id, Arabic line, cost)
    ("rea", "REA: هندسة عكسية وتحليل عميق (mcp__rea__*)", "free"),
    ("higgsfield-free", "سحابة Higgsfield المجانية: sandbox_exec وbalance ورفع الملفات", "free"),
    ("higgsfield-paid", "توليد Higgsfield: صور وفيديو وصوت وupscale (بيصرف رصيد)", "paid"),
    ("suno", "Suno: أغاني وموسيقى (مدفوع)", "paid"),
    ("claude-docs", "Claude Docs: مستندات حية بتتعدّل", "free"),
    ("blackdragon", "التحكم في الجهاز وكروم: computer و browser و system", "approval"),
    ("desktop-commander", "Remote Desktop Commander: ملفات وعمليات على الأجهزة المصرّح بيها", "approval"),
]
PAID_HINTS = ("kling", "suno", "elevenlabs", "heygen", "atlas cloud", "fal.ai", "tikhub", "apify", "veed", "azure",
              "replicate", "runway", "bfl flux", "flux api")
HOMES = {
    "محركات وكتالوج التنين الأسود": ["%BLACK_DRAGON_HOME%", "~/OneDrive/Desktop/مهارات/التنين الأسود", "~/OneDrive/Desktop/التنين الأسود",
                                     "~/Desktop/مهارات/التنين الأسود", "~/Desktop/التنين الأسود"],
    "مصدر التنين الذهبي": ["%GOLDEN_DRAGON_HOME%/app", "~/OneDrive/Desktop/مهارات/التنين الذهبي/app", "~/OneDrive/Desktop/التنين الذهبي/app"],
    "مكتبات الموشن (مهارات)": ["~/OneDrive/Desktop/مهارات"],
    "صندوق الهندسة العكسية": ["~/re-tools/retool.py"],
    "عقل التنين الأحمر": ["~/.claude/skills/golden-dragon/scripts/rd.py"],
    "سوبر باور": ["~/kosif-tool/.claude/skills/kosif-superpowers/scripts/hub.py"],
    "برامج الاستوديو المتفكوكة": ["~/GoldenDragon/studio"],
}
LEGACY = [("~/OneDrive/Desktop/التنين الأسود", "التنين الأسود"), ("~/OneDrive/Desktop/الطائر الذهبي", "الطائر الذهبي"),
          ("~/OneDrive/Desktop/الطائر الأبيض", "الطائر الأبيض"), ("~/OneDrive/Desktop/المونتاج", "المونتاج")]


def jload(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def unit(kind, ident, name, what="", what_ar="", how="", status="ok", cost="free", **kw):
    u = {"id": f"{kind}:{ident}", "kind": kind, "name": name, "what": what, "what_ar": what_ar, "how": how,
         "status": status, "cost": cost}
    u.update({k: v for k, v in kw.items() if v not in (None, "", [], {})})
    return u


def skill_units():
    d = jload(FORGE / "data" / "skills.json")
    out = []
    for s in d["skills"]:
        if s.get("error"):
            continue
        flags, warn = s.get("flags", []), []
        status = "ok"
        if s.get("superseded_by"):
            status = "older"
            warn.append(f"إصدار أقدم (v{s.get('version')}): استخدم `skill:{s['superseded_by']}`")
        elif s.get("missing") or s.get("missing_shared"):
            status = "partial"
            gone = (s.get("missing") or []) + (s.get("missing_shared") or [])
            warn.append("بتذكر ملفات مش موجودة على الجهاز (" + "، ".join(gone[:3]) + "): لو الخطوة محتاجاها، "
                        "اتأكد الأول وقول لو ناقصة، ماتخترعش محتواها")
        desc = s.get("description", "")
        low = desc.lower()
        paid = [h for h in PAID_HINTS if h in low]
        if paid:
            warn.append("بتستخدم خدمة برّه الجهاز (" + "، ".join(paid) + "): غالبًا مفتاح API أو رصيد، فموافقة الأول")
        out.append(unit("skill", s["id"], s["id"], what=desc[:420], how=f"skill read {s['id']}", status=status,
                        cost="paid" if paid else "free", family=s.get("family"), lang=s.get("lang"),
                        path=str(Path(s["path"]) / "SKILL.md"), warn_ar=warn,
                        extra={"version": s.get("version"), "files": s.get("files"), "scripts": s.get("scripts_total"),
                               "versions": s.get("versions"), "mcp": s.get("mcp")}))
    return out, d


def library_units():
    lib = jload(GB / "forge" / "data" / "library.json")["items"]
    out = []
    for it in lib:
        ready = it.get("readiness")
        status = "ok" if it.get("offline_entry") else "reference" if ready == "reference-only" else "needs-setup"
        warn = [] if it.get("commercial_ok") == "yes" else [f"الرخصة {it.get('license')} ({it.get('commercial_ok')}): قول قبل أي شغل تجاري"]
        out.append(unit("lib", it["id"], it.get("name") or it["id"], what=it.get("cli") or "", what_ar=it.get("what_ar", ""),
                        how=f"motion_lib show {it['id']}" + (f" ← kit {it['id']}" if it.get("offline_entry") else ""),
                        status=status, family=it.get("category"), keywords=it.get("keywords") or [],
                        license=it.get("license"), warn_ar=warn, path=it.get("source")))
    return out


def studio_units():
    st = jload(GB / "forge" / "data" / "studio.json")["programs"]
    return [unit("studio", p["id"], p["name"], what=p.get("cli_usage", ""), what_ar=p.get("use_ar", ""),
                 how=f"studio show {p['id']} ← studio_run install {p['id']} ← studio_run run {p['id']}",
                 status="needs-setup", cost="approval", license=p.get("license"),
                 warn_ar=[p["cautions"]] if p.get("cautions") else []) for p in st]


def app_tool_units():
    t = (GB / "app" / "app.py").read_text(encoding="utf-8")
    tools = re.findall(r'^\s+tool\("([a-z_]+)",\s*"((?:[^"\\]|\\.)*)"', t, re.M)
    out = []
    approval = set(re.findall(r'tool\("([a-z_]+)".*?approval=True', t, re.S)) & {n for n, _ in tools}
    for name, desc in tools:
        if name == "deployment_status":
            continue                                       # not available in the subscription mode
        out.append(unit("tool", name, name, what=desc.replace("Golden Bird", "Golden Dragon")[:300], how=name,
                        cost="approval" if name in approval else "free"))
    out.append(unit("tool", "fusion", "fusion", what="Golden Dragon fusion: route a request to the best recipe of skills, "
                    "tools, engines and programs; find / show any capability; doctor checks this PC now.",
                    what_ar="عقل الانصهار: بيوجّه أي طلب لأحسن وصفة من المهارات والأدوات والمحركات والبرامج",
                    how='fusion route "<الطلب>"'))
    out.append(unit("tool", "viral_video_analyzer", "viral_video_analyzer",
                    what="Built-in discovery and guided analysis of public video via yt-dlp, ffmpeg and Whisper.",
                    what_ar="فحص وتجهيز تحليل الفيديوهات واللقطات والنص والتوقيتات",
                    how='viral_video_analyzer doctor | plan "<video URL>"'))
    out.append(unit("tool", "replica_skill", "replica_skill",
                    what="Built-in routing for eleven clean-room app reconstruction skills.",
                    what_ar="فحص وتخطيط 11 مهارة لإعادة بناء تطبيق أصلي واختباره",
                    how='replica_skill doctor | plan "<authorized app>"'))
    # These tools are registered by gd_patches/gd_anatomy.py in the Golden Dragon,
    # not in the Golden Bird app that this scanner introspects.
    out.append(unit("tool", "anatomy", "anatomy",
                    what="Read-only Anatomy MIT skill status and technical SVG/WebGL/3D plan.",
                    what_ar="فحص مهارة Anatomy المحلية وخطة الرسم الهندسي التفاعلي",
                    how='anatomy doctor | brief "<task>"'))
    out.append(unit("tool", "anatomy_scaffold", "anatomy_scaffold",
                    what="Copy the installed upstream Anatomy kit and example into a new workspace folder.",
                    what_ar="نسخ مثال ومكتبات Anatomy بترخيص MIT بعد موافقة المستخدم",
                    how="anatomy_scaffold destination=NAME example=dial-indicator",
                    cost="approval"))
    return out


def first(cands):
    import os
    for c in cands:
        p = Path(os.path.expandvars(os.path.expanduser(c)))
        if p.exists():
            return p
    return None


def engine_units():
    repo = first(HOMES["محركات وكتالوج التنين الأسود"])
    if not repo:
        raise SystemExit("✗ مستودع التنين الأسود مش موجود في أي مكان من الأماكن المعروفة")
    p = subprocess.run([sys.executable, "-X", "utf8", "-m", "dragon", "engines"], cwd=repo, capture_output=True,
                       text=True, encoding="utf-8", timeout=120)
    rows = re.findall(r"^\s{2}([a-z_]+)\s{2,}(.+)$", p.stdout, re.M)
    if len(rows) < 5:
        raise SystemExit(f"✗ python -m dragon engines رجّع {len(rows)} محرك بس:\n{p.stdout[-800:]}\n{p.stderr[-800:]}")
    return [unit("engine", n, n, what=d.strip(), how=f"run_engine {n} … (run_engine {n} --help الأول)",
                 cost="paid" if n == "kling_director" else "free",
                 warn_ar=["Kling مدفوع: البرومبتات ببلاش، التوليد نفسه بموافقة"] if n == "kling_director" else [])
            for n, d in rows], repo


def retool_units():
    rt = HOME / "re-tools" / "retool.py"
    p = subprocess.run([sys.executable, "-X", "utf8", str(rt), "list"], capture_output=True, text=True, encoding="utf-8", timeout=120)
    rows = re.findall(r"^\| `([a-z0-9-]+)` \| ([^|]+)\| ([^|]+)\| ([^|]+)\| ([^|]+)\|", p.stdout, re.M)
    if len(rows) < 20:
        raise SystemExit(f"✗ retool list رجّع {len(rows)} أداة بس")
    gui = {"x64dbg", "imhex", "ilspy-gui", "die-gui"}
    runtime = {"frida", "frida-trace", "pe-sieve", "mitmdump"}
    return [unit("re", i, name.strip(), what_ar=what.strip(), how=f"retool run {i} --help",
                 status="ok" if "✓" in inst else "missing", cost="approval" if i in runtime else "free",
                 warn_ar=(["واجهة رسومية بتفتح للمستخدم، مش للتحليل الأوتوماتيك"] if i in gui else []) +
                         (["وقت التشغيل: بإذن صريح، وماتحقنش في التطبيق اللي شغّال الجلسة"] if i in runtime else []))
            for i, name, kind, what, inst in rows]


def probe(cmd):
    if cmd.startswith("py:"):
        r = subprocess.run([sys.executable, "-c", f"import importlib.util,sys;sys.exit(0 if importlib.util.find_spec({cmd[3:]!r}) else 1)"],
                           capture_output=True, timeout=60)
        return r.returncode == 0
    return bool(shutil.which(cmd))


def program_units():
    out = []
    for i, cmd, ar in PROGRAMS:
        name = cmd[3:] if cmd.startswith("py:") else cmd
        how = f"python -c \"import {name}\"" if cmd.startswith("py:") else f"{cmd} --help"
        found = probe(cmd)
        warn = ["مش على الـ PATH: search_files بيرجع لبحث بايثون أبطأ؛ التثبيت (winget install BurntSushi.ripgrep.MSVC) بموافقة"] \
            if i == "rg" and not found else []
        out.append(unit("program", i, name, what_ar=ar, how=how, probe=cmd, status="ok" if found else "missing", warn_ar=warn))
    return out


def mcp_units():
    return [unit("mcp", i, i, what_ar=ar, how=f"mcp__{i.split('-')[0]}__…", cost=c,
                 warn_ar=["بيصرف رصيد: موافقة صريحة على الأداة والسعر"] if c == "paid" else []) for i, ar, c in MCP]


# ---------------------------------------------------------------- the other dragons, fused (2026-11-15, «اصهر كل قدراتهم»)
RD_SKILL = HOME / ".claude" / "skills" / "golden-dragon"
SUPERPOWERS = HOME / "kosif-tool" / ".claude" / "skills" / "kosif-superpowers"
RD_PY = r'python -X utf8 "%USERPROFILE%\.claude\skills\golden-dragon\scripts\rd.py"'
RD_CMD_AR = {   # one Arabic line per Red Dragon command (its own help text is used when it has one)
    "start": "ملخص بداية الجلسة", "where": "فين ملفات وإعدادات التنين الأحمر", "doctor": "فحص صحة التنين الأحمر",
    "docs": "الدليل", "retro": "مراجعة بعد الشغل: إيه اللي نفع وإيه اللي لأ", "selftest": "الفحص الذاتي وبوابة دقة التوجيه",
    "teach": "علّم الراوتر: طلب اتوجّه غلط ← الـ playbook الصح (بيحسّن توجيه التنين الذهبي كمان)",
    "map": "خريطة الـ playbooks والقدرات", "show": "تفاصيل playbook", "learn": "سجّل درس من تصحيح صاحب الشغل",
    "lessons": "الدروس المتسجّلة", "outcome": "سجّل نتيجة playbook: ok أو fail", "memory": "تصدير واستيراد ذاكرة التنين",
    "re": "هندسة عكسية لأي ملف أو لينك: النوع والطريق المناسب", "repo": "تحليل مستودع وتحويله لقدرة",
    "repos": "فهرس أشهر 500 مستودع GitHub", "skills": "مكتبة أشهر 500 مهارة Claude: بحث وعرض", "x": "أوامر محرك التنين (dragon.py)",
    "character": "ذاكرة الشخصية والروتوسكوب", "math": "حسابات الرسم والتحريك: نسب الجسم وIK والكاميرا",
    "dcm": "ذاكرة الشخصية v1 (المحرك التاني)", "desktop": "جسر تطبيق التنين على الديسكتوب: قراءة وفحص",
    "ref": "قفل المرجع وتطابق الخطوط", "mind": "عقل Claude: brief وgate وأنواع التفكير", "krita": "الرسم بـ Krita بالكود",
    "sync": "حارس المزامنة: توقيت الكلمات والكابشن", "gold": "أدوات الطائر الذهبي: studio وlib وsync",
    "consent": "بوابة الموافقة: أنهي فعل برّه الجهاز الرسالة دي وافقت عليه صراحة",
    "think": "فكّر وخطّط: start وcheck وrevise وسجل الأخطاء",
}


def _as_list(x):
    return x if isinstance(x, list) else [x] if x else []


def dragon_units():
    """The Red Dragon's 38 playbooks (steps, gates, pitfalls, questions to settle) and every rd.py command. The White
    Dragon's playbooks and commands are an older subset of these (checked 2026-11-15), so they are not duplicated."""
    out = []
    pbf = RD_SKILL / "mind" / "playbooks.json"
    if pbf.is_file():
        d = jload(pbf)
        for p in (d if isinstance(d, list) else d.get("playbooks") or list(d.values())):
            out.append(unit("playbook", p["id"], p["id"], what=p.get("en", ""), what_ar=p.get("ar", ""),
                            how=f'{RD_PY} think start "<الطلب>"   (playbook {p["id"]})', family=p.get("domain"),
                            keywords=[str(x) for x in _as_list(p.get("triggers"))[:20] + _as_list(p.get("phrases"))[:20]],
                            extra={"steps": len(p.get("steps") or []), "gates": _as_list(p.get("gates"))[:6],
                                   "pitfalls": _as_list(p.get("pitfalls"))[:6], "ask": _as_list(p.get("ask"))[:4],
                                   "skills": _as_list(p.get("skills"))[:8],
                                   "steps_text": [str(s)[:140] for s in _as_list(p.get("steps"))[:5]]}))
    rdpy = RD_SKILL / "scripts" / "rd.py"
    if rdpy.is_file():
        for name, helptext in re.findall(r'sub\.add_parser\("([a-z-]+)"(?:,\s*help="([^"]*)")?', rdpy.read_text(encoding="utf-8")):
            out.append(unit("cmd", f"rd-{name}", f"rd {name}", what=helptext, what_ar=RD_CMD_AR.get(name, ""),
                            how=f"{RD_PY} {name} --help"))
    return out


def power_units():
    """KOSIF Superpowers: the curated runnable tools (data/tools.json, schema kosif.tools.v1)."""
    f = SUPERPOWERS / "data" / "tools.json"
    if not f.is_file():
        return []
    hub = r'python -X utf8 "%USERPROFILE%\kosif-tool\.claude\skills\kosif-superpowers\scripts\hub.py"'
    return [unit("power", t["id"], t.get("title_en") or t["id"], what=(t.get("summary_en") or "")[:300],
                 what_ar=(t.get("title_ar") or "") + (" — " + t["summary_ar"][:200] if t.get("summary_ar") else ""),
                 how=f"{hub} tool {t['id']}", family=t.get("area"), keywords=[str(k) for k in (t.get("keywords") or [])[:15]],
                 cost="approval" if t.get("consent") else "free")
            for t in jload(f).get("tools", [])]


def validate(units):
    ids = {u["id"]: u for u in units}
    errors, seen = [], set()
    for r in RECIPES:
        if r["id"] in seen:
            errors.append(f"{r['id']}: id مكرر")
        seen.add(r["id"])
        if len(r["when"]) < 2 or not any(re.search(r"[؀-ۿ]", w) for w in r["when"]) \
                or not any(re.search(r"[A-Za-z]{3}", w) for w in r["when"]):
            errors.append(f"{r['id']}: محتاج أمثلة طلبات بالعربي والإنجليزي")
        if len(r["steps"]) < 2:
            errors.append(f"{r['id']}: أقل من خطوتين")
        for n, s in enumerate(r["steps"], 1):
            if not s.get("gate_ar"):
                errors.append(f"{r['id']} خطوة {n}: مفيش بوابة تحقق")
            for i in s["read"]:
                if not i.startswith("skill:"):
                    errors.append(f"{r['id']} خطوة {n}: read لازم يبقى مهارة: {i}")
            for i in s["read"] + s["use"]:
                u = ids.get(i)
                if not u:
                    errors.append(f"{r['id']} خطوة {n}: `{i}` مش موجود")
                elif u.get("status") == "older":
                    errors.append(f"{r['id']} خطوة {n}: `{i}` إصدار أقدم ({u['warn_ar'][0]})")
    return errors


def main():
    t0 = time.time()
    skills, scan = skill_units()
    engines, repo = engine_units()
    units = (skills + app_tool_units() + engines + studio_units() + library_units() + program_units() + retool_units()
             + mcp_units() + dragon_units() + power_units())
    dup = [i for i, n in Counter(u["id"] for u in units).items() if n > 1]
    if dup:
        raise SystemExit(f"✗ ids مكررة: {dup[:10]}")
    errors = validate(units)
    rids = {r["id"] for r in RECIPES}
    errors += [f"RD_MAP {pb}: وصفة `{r}` مش موجودة" for pb, rs in RD_MAP.items() for r in rs if r not in rids]
    if errors:
        raise SystemExit("✗ الوصفات فيها أخطاء:\n  " + "\n  ".join(errors))
    lessons_src = GD / "analysis" / "lessons.json"
    lessons = jload(lessons_src) if lessons_src.is_file() else []
    OUT.mkdir(parents=True, exist_ok=True)
    tk = GD / "analysis" / "thinking_toolkit.json"            # the thinkers' toolkit (distilled from the thinking skills)
    if tk.is_file():
        toolkit = merge_books(jload(tk))                          # + the tools and «سبل» distilled from king's books
        bad = [t.get("id") for t in toolkit.get("tools", []) if not (t.get("id") and t.get("steps_ar") and t.get("use_when"))]
        if bad:
            raise SystemExit(f"✗ thinking_toolkit.json: أدوات ناقصة ({bad[:5]})")
        (OUT / "thinking.json").write_text(json.dumps(toolkit, ensure_ascii=False, indent=1), encoding="utf-8")
    kinds = Counter(u["kind"] for u in units)
    idx = {"generated": time.strftime("%Y-%m-%d %H:%M:%S"), "skills_scanned": scan["generated"], "engine_repo": str(repo),
           "counts": dict(kinds), "homes": HOMES, "legacy": LEGACY, "units": units}
    (OUT / "index.json").write_text(json.dumps(idx, ensure_ascii=False, indent=0), encoding="utf-8")
    (OUT / "recipes.json").write_text(json.dumps(RECIPES, ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT / "lessons.json").write_text(json.dumps(lessons, ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT / "rd_map.json").write_text(json.dumps(RD_MAP, ensure_ascii=False, indent=1), encoding="utf-8")
    shutil.copy2(FORGE / "modules" / "rd_bridge.py", OUT / "rd_bridge.py")   # run by the system python, so it ships as data
    st = Counter(u["status"] for u in units)
    miss = [u["id"] for u in units if u["kind"] == "program" and u["status"] == "missing"]
    print(f"✓ {len(units)} وحدة ({', '.join(f'{k}×{v}' for k, v in kinds.most_common())}), {len(RECIPES)} وصفة، "
          f"{len(lessons)} درس — في {time.time() - t0:.1f} ث -> {OUT}")
    print("الحالات:", dict(st))
    print("برامج مش موجودة:", miss or "مفيش")
    print("محركات التنين من:", repo)


if __name__ == "__main__":
    main()
