#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""فكّر وخطّط (Think & Plan) — the Red Dragon request pipeline for multi-step work.

    افهم ← بُص ← اسأل (كله مرة واحدة) ← خطة + مجلس + نقد ← موافقة ← نفّذ بعين ناقدة ← سلّم واتعلّم

The script does the bookkeeping that must not depend on memory: it reads the router, the old chats, the lessons and the
mistakes ledger, writes every question with a recommended answer, builds the step table with skills and calibrated
times, and lays out the council and the logic checks that the model then has to fill in. `check` refuses a plan whose
council, critique, pre-mortem or mistake checks are empty, so they cannot be skipped.

    python -X utf8 think.py start "<request>" [--prev "<previous message>"] [--answers "k=v; k=v"]
    python -X utf8 think.py revise ID "<what to change>"
    python -X utf8 think.py check ID|PLAN.md
    python -X utf8 think.py time ID STEP MINUTES          (real minutes of a finished step: estimates learn from it)
    python -X utf8 think.py mistake "<what went wrong>" --rule "<the rule from now on>" --trigger "words" [--domain D]
    python -X utf8 think.py mistakes [query]
    python -X utf8 think.py selftest
"""
import argparse, datetime, importlib.util, json, math, os, re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent
DATA = SKILL / "data"
RD_ROOT = SKILL.parent.parent.parent if (SKILL.parent.parent.parent / "scripts" / "rd.py").is_file() else Path.home() / ".claude" / "skills" / "red-dragon"
STATE = Path(os.environ.get("RED_DRAGON_HOME") or (Path.home() / ".red-dragon")) / "think"
PLANS = STATE / "plans"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


RD = _load("rd_core", RD_ROOT / "scripts" / "rd.py") if (RD_ROOT / "scripts" / "rd.py").is_file() else None
PM = _load("planning_mind", HERE / "plan.py")
_AG = SKILL.parent / "arena-gate" / "scripts" / "arena_gate.py"
AG = _load("arena_gate", _AG) if _AG.is_file() else None      # v2.19: the arena is a required step


def jl(path):
    if not Path(path).is_file():
        return []
    out = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                out.append(json.loads(line))
            except ValueError:
                pass
    return out


def toks(s):
    if RD:
        return set(RD.tokens(s))
    return set(re.findall(r"[\w؀-ۿ]{2,}", (s or "").lower()))


# ---------------------------------------------------------------- the mistakes ledger (never repeat a mistake)
def mistakes():
    """Seeded mistakes (in the package) + the owner's own (in ~/.red-dragon/think/mistakes.jsonl, survives updates)."""
    return jl(DATA / "mistakes_seed.jsonl") + jl(STATE / "mistakes.jsonl")


def mistakes_for(text, domain=None, k=6):
    q = toks(text)
    scored = []
    for m in mistakes():
        trig = toks(m.get("trigger", ""))
        body = toks(m.get("mistake", "") + " " + m.get("rule", ""))
        s = 2 * len(q & trig) + 0.5 * len(q & body)
        if domain and domain in m.get("domains", []):
            s += 1.5
        if m.get("always"):
            s += 2
        if s >= 2:
            scored.append((s, m))
    scored.sort(key=lambda x: -x[0])
    return [m for _, m in scored[:k]]


# ---------------------------------------------------------------- times: estimates that learn from real minutes
def step_minutes(step):
    t = step.lower()
    rules = [(r"رندر|render|صدّر|export|تصدير", 12), (r"نزّل|تنزيل|download|حمّل", 4), (r"حلّل|حلل|analy|تفريغ|whisper|ترجم", 6),
             (r"معاينة|preview|ستوري ?بورد|storyboard", 5), (r"اكتب|سكريبت|script|برومبت|prompt", 5), (r"اختبار|test|verify|فحص|راجع", 4),
             (r"صمّم|صمم|design|ارسم|رسم|كادر", 10), (r"ابني|build|كود|code|برمج", 15), (r"اقرا|read|افتح", 2), (r"ارفع|upload|انشر", 3)]
    for rx, m in rules:
        if re.search(rx, t):
            return m
    return 5


def calibration(kind):
    rows = [r for r in jl(STATE / "times.jsonl") if r.get("kind") == kind and r.get("est") and r.get("real")]
    if len(rows) < 3:
        return 1.0, len(rows)
    ratios = sorted(r["real"] / r["est"] for r in rows[-20:])
    return round(min(4.0, max(0.25, ratios[len(ratios) // 2])), 2), len(rows)


# ---------------------------------------------------------------- the council
def council_for(domain, ttype):
    c = json.loads((DATA / "council.json").read_text(encoding="utf-8"))
    key = next((k for k, v in c["by_type"].items() if ttype in v), "general")
    return c["members"][key] + c["always"], c["chair"]


LOGIC = json.loads((DATA / "council.json").read_text(encoding="utf-8"))["logic_checks"] if (DATA / "council.json").is_file() else []


# ---------------------------------------------------------------- start
def is_chat(text):
    if not RD:
        return False
    u = RD.understand(text)["text"]
    _, kind = RD._pb_scores(u, RD.playbooks())
    return kind in ("greet", "cont")


# Guards: requests that need a hard, measured check no matter how small they look (the owner, 2026-11-13).
GUARDS = [
    {"id": "ref", "re": r"(نفس|زي|مطابق|بالظبط|ذات|same|match|exact)\W+(?:\w+\W+){0,3}?(ال)?(خط|فونت|الفونت|لون|ألوان|الوان|ستايل|باليت|هوية|font|colou?rs?|palette|style)|(خط|فونت|ألوان|الوان)\W+(?:\w+\W+){0,2}?(زي|نفس|مطابق)",
     "first": "🔒 اقفل المرجع قبل أي حاجة: `rd.py ref lock <اسم> <ملف المرجع> [--text \"النص اللي فيه\"]`، وحط ناتج `rd.py ref show <اسم>` كقيود في الكود أو البرومبت (hex والخط بالاسم، ممنوع «قريب منه»)",
     "last": "✅ قيس الناتج قدام المرجع: `rd.py ref verify <اسم> <الناتج>` لازم يرجع ✅ قبل «خلص». ❌ = صلّح، ⚠ = بُص بعينك",
     "q": {"key": "reference", "q": "فين المرجع بالظبط (الملف أو اللقطة)؟ ولو الخط ليه اسم تعرفه قوله", "rec": "ابعت الملف نفسه، مش وصفه", "default": "آخر ملف اتبعت في المحادثة", "risk": 99},
     "mistakes": ["M08"]},
    {"id": "sync", "re": r"(كابشن|كابشنز|ترجم|ترجمة|subtitle|caption|srt|نص|كلام|كلمات|تيكست|text|موشن|motion)\W+(?:\w+\W+){0,4}?(على|مع|فوق|في)\W+(?:\w+\W+){0,2}?(الفيديو|فيديو|الريل|ريل|الكلام|الصوت|الأغنية|الاغنية|اغنية|أغنية)|ترجم\w*\W+(?:\w+\W+){0,2}?(ال)?(فيديو|ريل|اغنية|أغنية)|تزامن|متزامن|sync|lip|مع الكلام|كاريوكي|karaoke",
     "first": "🎙 توقيت كل كلمة من الصوت: `rd.py sync words <الفيديو>` (أو ملف كلمات جاهز). النص والموشن يتبنوا على التوقيت ده، مش بالعين: سكربت بعلامات Moment/Selection ← `rd.py sync script` (كابشن كاريوكي + أحداث بأوقات)",
     "last": "⏱ فحص التزامن: `rd.py sync check <words.json> <الكابشن> --motion <cues.json>`. أي فرق فوق 0.12 ث ← `rd.py sync fix …` وبعدين check تاني لحد ✅",
     "q": None, "mistakes": ["M09", "M03"]},
]


def guards_for(text):
    return [g for g in GUARDS if re.search(g["re"], text, re.I)]


def start(request, prev="", answers=""):
    known = {}
    for part in filter(None, (x.strip() for x in answers.split(";"))):
        if "=" in part:
            k, v = part.split("=", 1)
            known[k.strip()] = v.strip()
    if is_chat(request):
        return {"mode": "chat", "text": "💬 دردشة أو استكمال: مفيش خطة. رد عادي، أو كمّل الخطة اللي شغالة."}
    a = PM.analyze(request, context=prev, known=known)
    understood = a["decoded"]["text"]
    pb, conf, alt, domain = None, "none", None, ""
    if RD:
        before = RD._pb_scores(prev, RD.playbooks())[0] if prev else None
        ranked, _ = RD.route(understood, prev=before or None)
        if ranked and ranked[0][0] >= 2:
            pb = ranked[0][1]
            conf = RD.CONF_AR.get(RD.confidence(ranked), RD.confidence(ranked))
            domain = pb.get("domain", "")
            alt = ranked[1][1] if len(ranked) > 1 and ranked[1][0] >= 0.6 * ranked[0][0] else None
    # one step = do it (the owner: the pipeline is for multi-step requests)
    multi = a["depth"] in ("L2", "L3") or len(pb.get("steps", [])) >= 3 if pb else a["depth"] in ("L2", "L3")
    gs = guards_for(request + " " + understood)
    if a["decision"] in ("go", "go_all") and not multi and not gs:
        ar = AG.size(request + " " + understood, depth=a["depth"]) if AG else None
        extra = ("\n" + AG.render_size(ar)) if ar and ar["agents"] else ""
        return {"mode": "direct", "understood": understood, "arena": ar, "text": "▶️ طلب واضح وخطوة واحدة: نفّذ على طول، وقول الافتراضات في سطر." + extra}
    # ② look: old chats and lessons that answer questions before they are asked
    seen = []
    if RD:
        try:
            seen = [{"id": h["id"], "title": h.get("title", "")[:90]} for h in RD.chats_mod().search(understood, limit=3)]
        except Exception:
            seen = []
    lessons = [l["text"][:220] for l in (RD.recall(understood, limit=4, domain=domain) if RD else [])]
    must = mistakes_for(understood + " " + (pb or {}).get("id", "") + " " + a["type"], domain)
    have = {m["id"] for m in must}
    for g in gs:
        for mid in g["mistakes"]:
            if mid not in have:
                mm = next((m for m in mistakes() if m["id"] == mid), None)
                if mm:
                    must.insert(0, mm)
                    have.add(mid)
    # ③ all questions at once, each with a ⭐ recommendation and the default that is used when there is no answer
    qs = []
    for s in a["slots"]:
        if s["status"] == "known":
            continue
        rec = s.get("suggest") or s.get("value") or "—"
        qs.append({"key": s["key"], "q": s["question"], "rec": rec.lstrip("⭐ ").strip(), "default": s.get("value") or rec.lstrip("⭐ ").strip(),
                   "risk": s["risk"], "status": s["status"]})
    qs += [dict(g["q"], status="missing") for g in gs if g["q"] and g["q"]["key"] not in known]
    qs.sort(key=lambda x: -x["risk"])
    qs = qs[:7]
    # ④ steps: the playbook's own steps (they name the commands), else the planning-mind template
    if pb:
        raw = [re.sub(r"\s+", " ", x).strip() for x in pb.get("steps", [])]
        skills = pb.get("skills", [])
    else:
        ty = PM.load_data()["types"][a["type"]]
        raw = [x if isinstance(x, str) else f"{x.get('do', '')} ({x.get('tool', '')})" for x in ty.get("workflow", [])] or ["افهم الخامة", "نفّذ", "راجع", "سلّم"]
        checks = [x.get("check") for x in ty.get("workflow", []) if isinstance(x, dict)]
        skills = []
    checks = locals().get("checks", [])
    if gs:                                   # hard guards wrap the plan: lock/measure first, verify last
        raw = [g["first"] for g in gs] + raw + [g["last"] for g in gs]
        checks = ([None] * len(gs) + checks) if checks else []
    arena = AG.size(request + " " + understood, depth=a["depth"]) if AG else None
    if arena and arena["agents"]:
        ap_ = arena["plan"]
        st_ = (f"⚔️ الحلبة (شرط أساسي) على الحل المكتوب قبل التنفيذ: {arena['agents']} وكيل، {ap_['rounds']} جولات — اكتب .arena/task.md، "
               f"`rd.py arena start \"…\" --task-file .arena/task.md`، وبعدين `rd.py arena next` و`jobs` لحد DONE، و`rd.py arena gate` ✅")
        pos = 1 if len(raw) >= 3 else max(0, len(raw) - 1)     # on the written plan/concept, before the expensive execution
        raw = raw[:pos] + [st_] + raw[pos:]
        if checks:
            checks = checks[:pos] + ["rd.py arena gate = ✅ (بطل، أو نهائي أعمى قدام الإجابة المرفوضة)"] + checks[pos:]
    kind = (pb or {}).get("id") or a["type"]
    ratio, nobs = calibration(kind)
    steps = []
    for i, s in enumerate(raw, 1):
        m = max(1, round(step_minutes(s) * ratio))
        ck = (checks[i - 1] if not pb and i - 1 < len(checks) and checks[i - 1] else "فحص بالأرقام أو بالعين قبل الخطوة اللي بعدها")
        steps.append({"n": i, "step": s, "minutes": m, "check": ck, "worker": worker_for(s)})
    total = sum(s["minutes"] for s in steps)
    ty = PM.load_data()["types"].get(a["type"], {})
    hints = {"approaches": [x if isinstance(x, str) else x.get("name", str(x)) for x in ty.get("approaches", [])][:3],
             "risks": [x if isinstance(x, str) else x.get("risk", str(x)) for x in ty.get("risks", [])][:4],
             "value_adds": [x if isinstance(x, str) else x.get("name", str(x)) for x in ty.get("value_adds", [])][:3]}
    members, chair = council_for(domain, a["type"])
    pid = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    plan = {"id": pid, "version": 1, "request": request, "understood": understood, "prev": prev, "type": a["type"], "type_name": a["type_name"],
            "depth": a["depth"], "playbook": (pb or {}).get("id"), "playbook_ar": (pb or {}).get("ar"), "confidence": conf,
            "alternative": (alt or {}).get("id"), "skills": skills, "seen": seen, "lessons": lessons,
            "mistakes": [{"id": m["id"], "rule": m["rule"]} for m in must], "questions": qs, "steps": steps, "total": total,
            "calibration": {"ratio": ratio, "observations": nobs}, "council": [m["name"] for m in members] + [chair["name"]],
            "gates": [g for g in (pb or {}).get("gates", [])], "arena": arena, "hints": hints, "approvals": a.get("confirm_before", []) + (pb or {}).get("ask", [])}
    d = PLANS / pid
    d.mkdir(parents=True, exist_ok=True)
    (d / "plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=1), encoding="utf-8")
    md = render(plan, members, chair)
    (d / "plan_v1.md").write_text(md, encoding="utf-8")
    return {"mode": "plan", "id": pid, "path": str(d / "plan_v1.md"), "text": md}


CM_TYPE = {"montage": "media", "design": "media", "writing": "writing", "app_dev": "code", "skill_dev": "code", "analysis_re": "analysis",
           "accounting": "data", "research": "research", "decision": "decision", "download": "system", "general": "project"}
# v2.15: mechanical steps go to the cheap Haiku worker (agents/rd-runner.md); taste and thinking stay with the main model
ROUTINE = re.compile(r"(حمّل|حمل|نزّل|نزل|تحميل|download|grab|yt-dlp|insta |ffmpeg|ffprobe|حوّل|convert|قص من|اقطع|استخرج (?:الصوت|فريمات)|انسخ|انقل|سمّي|rename|zip|اضغط|sha256|checksum|selftest|verify|sync check|ref verify|mux|جرد)", re.I)
TASTE = re.compile(r"(صمم|تصميم|ارسم|اكتب|كتابة|ابتكر|اختار|قرار|خطة|نقد|رأي|ستوري ?بورد|كونسبت|اتجاه|هوك|افهم|حلل|عينك|بعينك|اعرض)", re.I)


def worker_for(step):
    return "rd-runner" if ROUTINE.search(step) and not TASTE.search(step) else None


UM_TYPE = {"montage": "creative", "design": "creative", "writing": "writing", "app_dev": "code", "skill_dev": "code", "analysis_re": "analysis",
           "accounting": "analysis", "research": "analysis", "decision": "decision", "download": "general", "general": "general"}


def render(p, members, chair):
    L = [f"# 🐉 فكّر وخطّط — {p['id']} (نسخة {p['version']})", "",
         "## ① فهمت إيه",
         f"- **الطلب بكلامي:** {p['understood']}",
         "- **الهدف (ليه):** «اكتب هنا الهدف في سطر. لو مش واضح، ده أول سؤال»",
         f"- **النوع:** {p['type_name']} · العمق {p['depth']}",
         f"- **الطريق:** {p['playbook_ar'] or '—'} [`{p['playbook'] or '—'}`] · ثقة {p['confidence']}" + (f" · بديل: `{p['alternative']}`" if p['alternative'] else ""),
         f"- **المهارات:** {', '.join(p['skills']) or '—'}",
         f"- **عقل Claude (claude-mind):** الحلقة العشرة (اقرا الإنسان ← ابدأ من التسليم ← … ← اتحقق مستقل ← سلّم). قبل «خلص»: `rd.py mind gate {CM_TYPE.get(p.get('type'), 'project')}`",
         f"- **العقل الفائق (ultra-mind):** `python3 engine/skills/ultra-mind/scripts/scaffold.py {UM_TYPE.get(p.get('type'), 'general')} {p['depth'] if p['depth'] in ('L2', 'L3') else 'L2'}` ← خطواته السبعة (افهم، ارجع خطوة، بدائل، نفّذ، pre-mortem، تحقق مستقل، سلّم بثقة) هي اللي بتملا ⑤ و⑥ تحت", ""]
    L += ["## ② بصّيت فين قبل ما أسأل"]
    L += [f"- محادثة قديمة: `{s['id']}` {s['title']}" for s in p["seen"]] or ["- مفيش محادثة قديمة قريبة."]
    L += [f"- درس: {l}" for l in p["lessons"]]
    L += ["", "## ③ أسئلتي (كلها مرة واحدة · رد «زي اقتراحك» يكفي · لو مفيش رد هكمّل بالافتراضي)", "",
          "| # | السؤال | ⭐ اقتراحي | لو مارديتش |", "|---|---|---|---|"]
    L += [f"| {i} | {q['q']} | {q['rec']} | {q['default']} |" for i, q in enumerate(p["questions"], 1)] or ["| — | مفيش سؤال يغيّر الناتج | — | — |"]
    L += ["", "## ④ الخطة", "", "| # | الخطوة | الوقت | الفحص بعدها |", "|---|---|---|---|"]
    L += [f"| {s['n']} | {s['step']}{' · 🤖 rd-runner (Haiku)' if s.get('worker') else ''} | ~{s['minutes']} د | {s['check']} |" for s in p["steps"]]
    if any(s.get("worker") for s in p["steps"]):
        L += ["", "🤖 **الخطوات الروتينية** (تحميل، تحويل، نسخ، فحص) تتعمل بالعامل الرخيص: في Claude Code بـ `Agent(subagent_type=\"rd-runner\")` بعد `rd.py agents install`. لو مش متاح، اعملها إنت عادي. أي خطوة فيها ذوق أو قرار، لأ."]
    ar = p.get("arena")
    if ar:
        L += ["", AG.render_size(ar) if AG else f"⚔️ الحلبة: {ar.get('tier_ar')}"]
        if ar["agents"]:
            L += ["   الخطوات الروتينية بس هي اللي برا الحلبة. التسليم ممنوع قبل `rd.py arena gate` = ✅."]
    cal = p["calibration"]
    L += [f"\n**الإجمالي: ~{p['total']} دقيقة**" + (f" (متظبط على {cal['observations']} مرة سابقة × {cal['ratio']})" if cal["observations"] >= 3 else " (تقدير أولي؛ بيتظبط من الأوقات الحقيقية)")]
    if p["approvals"]:
        L += ["", "🔒 **وقفات موافقة:** " + " · ".join(p["approvals"])]
    if p["gates"]:
        L += ["✅ **بوابات الجودة:** " + " · ".join(p["gates"])]
    L += ["", "## ⑤ المجلس (كل عضو رأي مستقل الأول، وبعدين الرئيس يحكم)", ""]
    for m in members:
        L += [f"- **{m['name']}** — {m['lens']}", "  - رأيه: «…»"]
    L += [f"- **{chair['name']}** — {chair['lens']}", "  - الحكم: «…»", ""]
    h = p.get("hints", {})
    if any(h.values()):
        L += ["## ⑥ رأيي ونقدي (إلزامي، حتى على اختياراتك)", "_مواد للتفكير (من قوالب النوع، مش إجابة):_"]
        L += [f"_- طرق بديلة: {' · '.join(h['approaches'])}_"] if h.get("approaches") else []
        L += [f"_- مخاطر معروفة: {' · '.join(h['risks'])}_"] if h.get("risks") else []
        L += [f"_- إضافات ممكن تفرق: {' · '.join(h['value_adds'])}_"] if h.get("value_adds") else []
        L += ["- **نقطة ضعف في الطلب أو في الخطة:** «…»", "- **بديل أحسن لو موجود:** «…»",
              "- **pre-mortem — لو الناتج طلع وحش، هيكون ليه؟**", "  1. «…» ← العلاج في خطوة رقم «…»", "  2. «…» ← العلاج في خطوة رقم «…»",
              "- **تحقق مستقل (CoVe من العقل الفائق):** سؤالين أجاوبهم من غير ما أبص على الخطة، وأقارن: «…»", ""]
    else:
      L += ["## ⑥ رأيي ونقدي (إلزامي، حتى على اختياراتك)", "- **نقطة ضعف في الطلب أو في الخطة:** «…»", "- **بديل أحسن لو موجود:** «…»",
          "- **pre-mortem — لو الناتج طلع وحش، هيكون ليه؟**", "  1. «…» ← العلاج في خطوة رقم «…»", "  2. «…» ← العلاج في خطوة رقم «…»",
              "- **تحقق مستقل (CoVe من العقل الفائق):** سؤالين أجاوبهم من غير ما أبص على الخطة، وأقارن: «…»", ""]
    L += ["## ⑦ فحص المنطق (عين بني آدم) — قبل الخطة وبعد كل ناتج مرئي"]
    L += [f"- [ ] {c}" for c in LOGIC]
    L += ["", "## ⑧ أخطاء اتعملت قبل كده ولازم ماتتكررش"]
    L += [f"- [ ] `{m['id']}` {m['rule']}" for m in p["mistakes"]] or ["- مفيش خطأ مسجّل قريب من الطلب ده."]
    L += ["", "---", "**موافق؟** رد «موافق» وأبدأ، أو «غيّر رقم …» وأطلع نسخة جديدة. لو مارديتش على الأسئلة، هكمّل باقتراحاتي."]
    return "\n".join(L) + "\n"


# ---------------------------------------------------------------- revise / check / time / mistake
def latest(pid):
    d = PLANS / pid
    vs = sorted(d.glob("plan_v*.md"), key=lambda x: int(re.search(r"v(\d+)", x.name).group(1)))
    return d, vs[-1] if vs else None


def revise(pid, change):
    d, last = latest(pid)
    if not last:
        raise SystemExit(f"مفيش خطة بالرقم {pid}")
    n = int(re.search(r"v(\d+)", last.name).group(1)) + 1
    txt = last.read_text(encoding="utf-8")
    txt = re.sub(r"\(نسخة \d+\)", f"(نسخة {n})", txt, count=1)
    txt = txt.replace("## ① فهمت إيه", f"## التعديل في النسخة {n}\n- طلبت: {change}\n- اللي اتغيّر: «اكتب الفرق بس»\n- رأيي في التعديل: «…»\n\n## ① فهمت إيه", 1)
    out = d / f"plan_v{n}.md"
    out.write_text(txt, encoding="utf-8")
    return out


PLACEHOLDER = "«…»"


def check(target):
    p = Path(target)
    if not p.is_file():
        d, p = latest(target)
        if not p:
            raise SystemExit(f"مفيش خطة: {target}")
    t = p.read_text(encoding="utf-8")
    probs = []
    for sec, name in (("## ⑤", "المجلس"), ("## ⑥", "رأيي ونقدي"), ("## ⑦", "فحص المنطق"), ("## ⑧", "الأخطاء")):
        if sec not in t:
            probs.append(f"ناقص قسم {name}")
    for sec, name in (("## ⑤", "المجلس"), ("## ⑥", "رأيي ونقدي")):
        part = t.split(sec, 1)[-1].split("\n## ", 1)[0]
        if PLACEHOLDER in part:
            probs.append(f"{name}: فيه خانات لسه فاضية («…»)")
    if "الهدف (ليه):** «اكتب هنا" in t:
        probs.append("الهدف (ليه) مكتوبش")
    if "- [ ] `" in t.split("## ⑧", 1)[-1]:
        probs.append("فيه أخطاء قديمة لسه ماتعلّمش عليها [x] (اتأكد إن الخطة بتمنعها)")
    if not re.search(r"\*\*الإجمالي: ~\d+", t):
        probs.append("مفيش وقت إجمالي")
    return {"file": str(p), "ok": not probs, "problems": probs}


def log_time(pid, step, minutes):
    d = PLANS / pid
    plan = json.loads((d / "plan.json").read_text(encoding="utf-8"))
    st = next((s for s in plan["steps"] if s["n"] == int(step)), None)
    if not st:
        raise SystemExit(f"مفيش خطوة {step}")
    STATE.mkdir(parents=True, exist_ok=True)
    row = {"t": datetime.datetime.now().isoformat(timespec="seconds"), "plan": pid, "kind": plan["playbook"] or plan["type"],
           "step": st["step"][:120], "est": st["minutes"], "real": float(minutes)}
    with open(STATE / "times.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


def add_mistake(text, rule, trigger, domain=""):
    STATE.mkdir(parents=True, exist_ok=True)
    mid = "m" + datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    row = {"id": mid, "mistake": text, "rule": rule, "trigger": trigger, "domains": [d for d in domain.split(",") if d], "source": "owner"}
    with open(STATE / "mistakes.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    if RD:
        try:
            RD.learn(f"{text} ← {rule}", domain.split(",")[0] if domain else "general", trigger, "failure")
        except Exception:
            pass
    return row


# ---------------------------------------------------------------- selftest: the cases the pipeline must get right
def selftest():
    import tempfile
    global STATE, PLANS
    STATE = Path(tempfile.mkdtemp()) / "think"
    PLANS = STATE / "plans"
    cases = json.loads((SKILL / "evals" / "think_cases.json").read_text(encoding="utf-8"))
    bad = []
    for c in cases:
        r = start(c["q"], c.get("prev", ""))
        for must in c.get("must_text", []) if r["mode"] != "plan" else []:
            if must not in r["text"]:
                bad.append(f"«{c['q']}»: «{must}» مش في الرد")
        if r["mode"] != c["mode"]:
            bad.append(f"«{c['q']}»: mode {r['mode']} ≠ {c['mode']}")
            continue
        if r["mode"] == "plan":
            t = r["text"]
            for must in c.get("must_mistakes", []):
                if f"`{must}`" not in t:
                    bad.append(f"«{c['q']}»: الخطأ {must} ماطلعش في الخطة")
            if c.get("max_questions") is not None and t.count("\n| ") - t.count("| # |") - len(re.findall(r"\n\| \d+ \| .* \| ~\d+ د \|", t)) > c["max_questions"] + 1:
                bad.append(f"«{c['q']}»: أسئلة كتير")
            for must in c.get("must_text", []):
                if must not in t:
                    bad.append(f"«{c['q']}»: «{must}» مش في الخطة")
            ck = check(r["path"])
            if ck["ok"]:
                bad.append(f"«{c['q']}»: check قبل الخطة الفاضية وده غلط")
    for b in bad:
        print("FAIL", b)
    print(f"{len(cases) - len(bad)}/{len(cases)} cases" if not bad else f"{len(bad)} problem(s)")
    return 0 if not bad else 1


def main(argv=None):
    ap = argparse.ArgumentParser(prog="think", description="فكّر وخطّط — Red Dragon request pipeline")
    sp = ap.add_subparsers(dest="cmd", required=True)
    s = sp.add_parser("start"); s.add_argument("request"); s.add_argument("--prev", default=""); s.add_argument("--answers", default=""); s.add_argument("--json", action="store_true")
    s = sp.add_parser("revise"); s.add_argument("id"); s.add_argument("change")
    s = sp.add_parser("check"); s.add_argument("target")
    s = sp.add_parser("time"); s.add_argument("id"); s.add_argument("step"); s.add_argument("minutes", type=float)
    s = sp.add_parser("mistake"); s.add_argument("text"); s.add_argument("--rule", required=True); s.add_argument("--trigger", required=True); s.add_argument("--domain", default="")
    s = sp.add_parser("mistakes"); s.add_argument("query", nargs="?", default="")
    sp.add_parser("selftest")
    a = ap.parse_args(argv)
    if a.cmd == "start":
        r = start(a.request, a.prev, a.answers)
        print(json.dumps(r, ensure_ascii=False, indent=1) if a.json else (r["text"] + (f"\n📄 {r['path']}" if r.get("path") else "")))
    elif a.cmd == "revise":
        print(revise(a.id, a.change))
    elif a.cmd == "check":
        r = check(a.target)
        print(json.dumps(r, ensure_ascii=False, indent=1))
        return 0 if r["ok"] else 1
    elif a.cmd == "time":
        print(json.dumps(log_time(a.id, a.step, a.minutes), ensure_ascii=False))
    elif a.cmd == "mistake":
        print(json.dumps(add_mistake(a.text, a.rule, a.trigger, a.domain), ensure_ascii=False))
    elif a.cmd == "mistakes":
        rows = mistakes_for(a.query, k=20) if a.query else mistakes()
        for m in rows:
            print(f"`{m['id']}` {m['rule']}  ⟵ {m.get('trigger', '')}")
    elif a.cmd == "selftest":
        return selftest()
    return 0


if __name__ == "__main__":
    sys.exit(main())
