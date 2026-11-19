#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""العقل المخطِّط (Planning Mind) — helper script.

Turns a raw request into an intent card (decoded text, task type, depth, slot
status, ask-gate decision, questions with recommended defaults, proposals,
workflow, verification gates, related lessons), and validates plan files.

Usage:
  plan.py card "<request>" [--context "facts already known"] [--known key=value ...] [--json] [--plan-out FILE]
  plan.py gate --impact N --uncertainty N --redo N [--flag money|publish|delete|irreversible|ethics]
  plan.py workflow <type|all> [--md]
  plan.py check <plan.md>
  plan.py learn "<what happened -> what to do>" [--type T]
  plan.py lessons [query]
  plan.py types
  plan.py selftest

Exit codes: 0 ok · 1 check/selftest failed · 2 bad input / missing file.
Depends only on the Python standard library. Optionally uses red-dragon's
rd.py (keyboard-layout decoding) and dictation.json (voice typos) if present.
"""
import argparse
import datetime
import json
import os
import pathlib
import re
import subprocess
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "task_types.json"
LESSONS = ROOT / "data" / "lessons.jsonl"
EVALS = ROOT / "evals" / "evals.json"
HOME = pathlib.Path(os.path.expanduser("~"))
_RD_HOME = ROOT.parent.parent.parent if (ROOT.parent.parent.parent / "scripts" / "rd.py").is_file() else HOME / ".claude" / "skills" / "red-dragon"   # inside Red Dragon: engine/skills/planning-mind
RD = _RD_HOME / "scripts" / "rd.py"
DICT = _RD_HOME / "mind" / "dictation.json"

# Ask-gate thresholds. risk = impact (0-3) x uncertainty (0-3), max 9.
# >= 6 means: a wrong guess is likely AND it breaks a main part of the result.
ASK_RISK = 6
# >= 4 is enough when redoing is expensive (redo >= 2: hours of render, money, client-facing).
ASK_RISK_COSTLY = 4
COSTLY_REDO = 2
# More than 3 questions at once turns a conversation into a form (the owner dislikes it).
MAX_QUESTIONS = 3

ARABIC = re.compile(r"[\u0600-\u06FF]")
EN_AR = {
    "q": "ض", "w": "ص", "e": "ث", "r": "ق", "t": "ف", "y": "غ", "u": "ع", "i": "ه", "o": "خ", "p": "ح",
    "[": "ج", "]": "د", "a": "ش", "s": "س", "d": "ي", "f": "ب", "g": "ل", "h": "ا", "j": "ت", "k": "ن",
    "l": "م", ";": "ك", "'": "ط", "z": "ئ", "x": "ء", "c": "ؤ", "v": "ر", "b": "لا", "n": "ى", "m": "ة",
    ",": "و", ".": "ز", "/": "ظ", "`": "ذ",
}
COMMON_EN = set(
    "the a an to and of is are i you it this that for with my me make please video plan file app can do in on "
    "what how why build create write fix run download skill help think".split()
)
MINI_DICT = {"مونتاتج": "مونتاج", "فديو": "فيديو", "كلاود": "Claude", "كلود": "Claude", "جيت هاب": "GitHub",
             "برومنت": "برومبت", "محكي": "محاكي", "كلاينك": "Kling", "ورك فلو": "workflow"}

DECISION_TEXT = {
    "stop": "⛔ وقف: فيه حاجة مش هتتعمل ({labels}). قول السبب في سطر واعرض البديل المسموح",
    "go_all": "▶️ نفّذ من غير أسئلة (قال «نفّذ/اللي تشوفه»): افترض كل حاجة وقول الافتراضات",
    "discuss": "💬 وضع الحوار: ابدأ بسؤال مفتوح عن الغرض («عايز توصل لإيه وليه؟»)، وبعدها كمّل بأسلوب brainstorming",
    "ask": "❓ اسأل {n} سؤال (الأهم الأول، في رسالة واحدة) واشتغل على التجهيز وإنت مستني",
    "go": "▶️ ابدأ على طول بالافتراضات المعلنة",
}


# ---------------------------------------------------------------- data
def load_data():
    if not DATA.exists():
        print(f"✗ data file missing: {DATA}", file=sys.stderr)
        sys.exit(2)
    with open(DATA, encoding="utf-8") as f:
        d = json.load(f)
    macros = d.get("macros", {})

    def expand(p):
        for k, v in macros.items():
            p = p.replace("{" + k + "}", v)
        return p

    for ty in d["types"].values():
        ty["strong"] = [expand(p) for p in ty.get("strong", [])]
        ty["weak"] = [expand(p) for p in ty.get("weak", [])]
        for s in ty.get("slots", []):
            s["detect"] = [expand(p) for p in s.get("detect", [])]
    for s in d.get("common_slots", []):
        s["detect"] = [expand(p) for p in s.get("detect", [])]
    return d


def count(patterns, text):
    n = 0
    for p in patterns:
        try:
            n += sum(1 for _ in re.finditer(p, text, re.I))
        except re.error as e:
            print(f"⚠ bad regex {p!r}: {e}", file=sys.stderr)
    return n


def any_match(patterns, text):
    for p in patterns:
        try:
            if re.search(p, text, re.I):
                return True
        except re.error as e:
            print(f"⚠ bad regex {p!r}: {e}", file=sys.stderr)
    return False


# ---------------------------------------------------------------- decode
def decode(text):
    info = {"original": text, "text": text, "layout_fixed": False, "words_fixed": [], "via": "none"}
    t = text
    if RD.exists():
        try:
            r = subprocess.run([sys.executable, "-X", "utf8", str(RD), "understand", text],
                               capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=25)
            out = r.stdout or ""
            i, j = out.find("{"), out.rfind("}")
            if i >= 0 and j > i:
                js = json.loads(out[i:j + 1])
                if js.get("text"):
                    t = js["text"]
                    info["layout_fixed"] = bool(js.get("layout_fixed"))
                    for w in js.get("words_fixed") or []:
                        info["words_fixed"].append(w if isinstance(w, str) else json.dumps(w, ensure_ascii=False))
                    info["via"] = "red-dragon"
        except Exception as e:  # rd.py is optional
            info["via"] = f"fallback ({type(e).__name__})"
    if info["via"] != "red-dragon" and not ARABIC.search(t):
        words = re.findall(r"[a-zA-Z]+", t.lower())
        if words and not any(w in COMMON_EN for w in words):
            t2 = "".join(EN_AR.get(ch, ch) for ch in t.lower())
            if ARABIC.search(t2):
                t, info["layout_fixed"], info["via"] = t2, True, "internal-layout"
    dic = dict(MINI_DICT)
    if DICT.exists():
        try:
            with open(DICT, encoding="utf-8-sig") as f:
                dic.update({k: v for k, v in json.load(f).items() if isinstance(v, str)})
        except Exception:
            pass
    for wrong, right in sorted(dic.items(), key=lambda kv: -len(kv[0])):
        if not wrong or wrong == right:
            continue
        pat = r"(?<![\w])" + re.escape(wrong) + r"(?![\w])"
        if re.search(pat, t):
            t = re.sub(pat, right, t)
            info["words_fixed"].append(f"{wrong}→{right}")
    info["text"] = t
    return info


# ---------------------------------------------------------------- lessons
def load_lessons():
    out = []
    if LESSONS.exists():
        with open(LESSONS, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        out.append(json.loads(line))
                    except Exception:
                        pass
    return out


def tokens(s):
    return {w for w in re.findall(r"[\w]+", s.lower()) if len(w) > 2}


def related_lessons(text, ttype, k=3):
    tt = tokens(text)
    scored = []
    for les in load_lessons():
        sc = len(tt & tokens(les.get("lesson", "") + " " + les.get("trigger", "")))
        if les.get("type") == ttype:
            sc += 2
        if sc > 1:
            scored.append((sc, les))
    scored.sort(key=lambda x: -x[0])
    return [l for _, l in scored[:k]]


# ---------------------------------------------------------------- analyze
def slot_eval(slot, full, known):
    present = slot["key"] in known or any_match(slot.get("detect", []), full)
    has_default = slot.get("default") not in (None, "")
    unc = 0 if present else (1 if has_default else 3)
    risk = slot["impact"] * unc
    ask = (not present) and (risk >= ASK_RISK or (risk >= ASK_RISK_COSTLY and slot.get("redo", 0) >= COSTLY_REDO))
    if present:
        status, value = "known", known.get(slot["key"], "من الطلب")
    elif has_default:
        status, value = "assumed", slot["default"]
    else:
        status, value = "missing", None
    return {"key": slot["key"], "label": slot["label"], "status": status, "value": value,
            "impact": slot["impact"], "uncertainty": unc, "redo": slot.get("redo", 0), "risk": risk,
            "ask": ask, "question": slot.get("question"), "suggest": slot.get("suggest") or slot.get("default")}


def analyze(request, context="", known=None, data=None):
    data = data or load_data()
    known = dict(known or {})
    dec = decode(request)
    t = dec["text"]
    full = t + "\n" + (context or "")

    scores = {k: 2 * count(ty["strong"], full) + count(ty["weak"], full)
              for k, ty in data["types"].items() if k != "general"}
    ranked = sorted(scores.items(), key=lambda kv: -kv[1])
    primary = ranked[0][0] if ranked and ranked[0][1] > 0 else "general"
    secondary = None
    if primary != "general" and len(ranked) > 1:
        s1, (k2, s2) = ranked[0][1], ranked[1]
        if s2 >= 2 and s2 * 2 >= s1:
            secondary = k2
    ty = data["types"][primary]

    flags = [{"key": k, "label": f["label"], "action": f["action"]}
             for k, f in data["flags"].items() if any_match(f["patterns"], full)]
    modes = data["modes"]
    opt_out = any_match(modes["opt_out"], full)
    discuss = any_match(modes["discuss"], full)
    deep = any_match(modes["deep"], full)

    slots = [slot_eval(s, full, known) for s in ty.get("slots", [])]
    slots += [slot_eval(s, full, known) for s in data.get("common_slots", [])]
    max_risk = sum(s["impact"] * 3 for s in slots) or 1
    clarity = round(100 * (1 - sum(s["risk"] for s in slots) / max_risk))

    asks = sorted([s for s in slots if s["ask"]], key=lambda s: (-s["risk"], -s["redo"]))
    stops = [f for f in flags if f["action"] == "stop"]
    confirms = [f for f in flags if f["action"] == "confirm"]

    if stops:
        decision = "stop"
    elif opt_out:
        decision = "go_all"
    elif discuss:
        decision = "discuss"
    elif asks:
        decision = "ask"
    else:
        decision = "go"
    questions = asks[:MAX_QUESTIONS] if decision == "ask" else []

    depth = ty.get("depth", "L1")
    if deep:
        depth = "L3"
    elif len(t.split()) <= 6 and clarity >= 90 and depth == "L1":
        depth = "L0"
    mult = data["depth_multiplier"].get(depth, 1.0)
    lo, hi = ty.get("estimate", [5, 30])
    est = [max(1, round(lo * mult)), max(2, round(hi * mult))]

    return {
        "decoded": dec, "type": primary, "type_name": ty["name"], "secondary": secondary,
        "secondary_name": data["types"][secondary]["name"] if secondary else None,
        "scores": dict(ranked[:4]), "depth": depth, "clarity": clarity,
        "mode": {"opt_out": opt_out, "discuss": discuss, "deep": deep},
        "flags": flags, "decision": decision,
        "decision_text": DECISION_TEXT[decision].format(n=len(questions),
                                                        labels="، ".join(f["label"] for f in stops)),
        "confirm_before": [f["label"] for f in confirms],
        "slots": slots, "questions": questions,
        "pattern": ty.get("pattern"), "pattern_text": data["patterns"].get(ty.get("pattern"), ""),
        "approaches": ty.get("approaches", []), "value_adds": ty.get("value_adds", []),
        "risks": ty.get("risks", []), "checkpoints": ty.get("checkpoints", []),
        "workflow": ty.get("workflow", []), "gates": ty.get("gates", []),
        "estimate_min": est, "lessons": related_lessons(t, primary),
    }


# ---------------------------------------------------------------- render
ICON = {"known": "✅ معروف", "assumed": "🟡 افتراض", "missing": "❓ ناقص"}


def render_card(a):
    d = a["decoded"]
    L = ["🧠 العقل المخطِّط — كارت الفهم", ""]
    L.append(f"الطلب بعد الفك: {d['text']}")
    fixes = []
    if d["layout_fixed"]:
        fixes.append("كيبورد إنجليزي ← عربي")
    fixes += d["words_fixed"]
    if fixes:
        L.append(f"(اتصلّح: {'، '.join(fixes)})")
    sec = f" + {a['secondary_name']}" if a["secondary"] else ""
    L.append(f"النوع: {a['type_name']}{sec} · العمق: {a['depth']} · الوضوح: {a['clarity']}% · ⏱ ~{a['estimate_min'][0]}–{a['estimate_min'][1]} د")
    L.append(f"القرار: {a['decision_text']}")
    if a["confirm_before"]:
        L.append(f"🔐 تأكيد إجباري قبل: {'، '.join(a['confirm_before'])}")
    L += ["", "| البند | الحالة | القيمة / الافتراض | خطر |", "|---|---|---|---|"]
    for s in a["slots"]:
        L.append(f"| {s['label']} | {ICON[s['status']]} | {s['value'] or '—'} | {s['risk']} |")
    if a["questions"]:
        L += ["", "❓ الأسئلة (مرتبة بالأهمية — كارت قرار، المقترح الأول):"]
        for i, q in enumerate(a["questions"], 1):
            sug = f" — المقترح: {q['suggest']}" if q.get("suggest") else ""
            L.append(f"{i}. {q['question']}{sug}")
        L.append("   (واختم بـ: «أو قول (نفّذ) وأمشي بالمقترح»)")
    L += ["", "💡 بدائل الطريقة:"]
    for ap in a["approaches"]:
        L.append(f"- {ap['name']}: مكسب {ap['gain']} · تمن {ap['cost']}")
    if a["value_adds"]:
        L.append("💡 إضافات ممكن تتعرض (اختياري): " + "، ".join(a["value_adds"]))
    if a["risks"]:
        L.append("⚠️ تنبيهات: " + " · ".join(a["risks"]))
    L += ["", f"🗺 الورك فلو ({a['pattern_text']}):"]
    for i, st in enumerate(a["workflow"], 1):
        L.append(f"{i}. {st['do']} — أداة: {st['tool']} — ناتج: {st['out']} — فحص: {st['check']}")
    if a["checkpoints"]:
        L.append("⏸ نقاط موافقة: " + " · ".join(a["checkpoints"]))
    L.append("✅ بوابة التحقق: " + " · ".join(a["gates"]))
    if a["lessons"]:
        L += ["", "📚 دروس قديمة قريبة:"]
        for les in a["lessons"]:
            L.append(f"- ({les.get('type', '?')}) {les.get('lesson')}")
    L += ["", "ملاحظة: الكارت مسودة مش حكم. صحّحه بالسياق الحقيقي (الملفات، المحادثة، ملف صاحب الشغل)."]
    return "\n".join(L)


def render_plan(a):
    goal = a["decoded"]["text"]
    L = [f"# خطة: {goal[:80]}", "", "## الهدف", goal, "", "## الافتراضات"]
    assumed = [s for s in a["slots"] if s["status"] == "assumed"]
    L += [f"- {s['label']}: {s['value']} (قولّي لو غلط)" for s in assumed] or ["- مفيش"]
    missing = [s for s in a["slots"] if s["status"] == "missing"]
    if missing:
        L += ["", "## أسئلة مفتوحة"] + [f"- {s['question']}" for s in missing]
    L += ["", f"## الخطوات ({a['pattern_text']})"]
    for i, st in enumerate(a["workflow"], 1):
        L.append(f"{i}. {st['do']} — أداة: {st['tool']} — ناتج: {st['out']} — فحص: {st['check']}")
    L += ["", "## نقاط الموافقة"]
    cps = list(a["checkpoints"]) + [f"قبل: {x}" for x in a["confirm_before"]]
    L += [f"- {c}" for c in cps] or ["- مفيش"]
    L += ["", "## الخطر وأرخص اختبار"]
    L += [f"- {r}" for r in a["risks"][:3]] or ["- —"]
    L += ["", "## الناتج", "المسار: (اكتب المسار الكامل على سطح المكتب)", "",
          "## التقدير", f"~{a['estimate_min'][0]}–{a['estimate_min'][1]} د", "",
          "## سجل القرارات (يتضاف بس، مايتمسحش)", f"- {datetime.date.today()}: الخطة الأولى."]
    return "\n".join(L) + "\n"


# ---------------------------------------------------------------- check
REQUIRED = ["الهدف", "الافتراضات", "الخطوات", "نقاط الموافقة", "الناتج", "التقدير"]


def check_plan(path):
    p = pathlib.Path(path)
    if not p.exists():
        print(f"✗ الملف مش موجود: {p}")
        return 2
    text = p.read_text(encoding="utf-8-sig")
    sections, cur = {}, None
    for line in text.splitlines():
        m = re.match(r"^##\s+(.+?)\s*$", line)
        if m:
            cur = m.group(1)
            sections[cur] = []
        elif cur is not None:
            sections[cur].append(line)

    def find(name):
        for k, v in sections.items():
            if k.startswith(name):
                return v
        return None

    issues = []
    for name in REQUIRED:
        if find(name) is None:
            issues.append(f"ناقص قسم «## {name}». الأقسام الموجودة: {', '.join(sections) or 'مفيش'}")
    steps = find("الخطوات") or []
    numbered = [l for l in steps if re.match(r"^\s*\d+[\.\)]\s", l)]
    if find("الخطوات") is not None and not numbered:
        issues.append("قسم الخطوات مفيهوش خطوات مرقّمة (1. … ).")
    for l in numbered:
        if "فحص:" not in l:
            issues.append(f"خطوة من غير «فحص:» → {l.strip()[:70]}")
    assum = find("الافتراضات")
    if assum is not None and not any(l.strip().startswith("-") for l in assum):
        issues.append("قسم الافتراضات فاضي: اكتب «- مفيش» لو فعلًا مفيش.")
    out = find("الناتج")
    if out is not None and not any(re.search(r"[A-Za-z]:[\\/]|~[\\/]|/|المسار", l) for l in out):
        issues.append("قسم الناتج مفيهوش مسار.")
    est = find("التقدير")
    if est is not None and not any(re.search(r"\d", l) for l in est):
        issues.append("قسم التقدير مفيهوش رقم.")
    if issues:
        print(f"✗ الخطة محتاجة تتصلّح ({len(issues)}):")
        for i in issues:
            print(f"  - {i}")
        return 1
    print(f"✓ الخطة سليمة: {len(numbered)} خطوة، كل خطوة ليها فحص، والأقسام الستة موجودة.")
    return 0


# ---------------------------------------------------------------- commands
def cmd_card(args):
    known = {}
    for kv in args.known or []:
        if "=" in kv:
            k, v = kv.split("=", 1)
            known[k.strip()] = v.strip()
    a = analyze(args.request, args.context or "", known)
    if args.json:
        print(json.dumps(a, ensure_ascii=False, indent=1))
    else:
        print(render_card(a))
    if args.plan_out:
        outp = pathlib.Path(args.plan_out)
        outp.parent.mkdir(parents=True, exist_ok=True)
        outp.write_text(render_plan(a), encoding="utf-8")
        print(f"\n📝 مسودة الخطة اتكتبت: {outp.resolve()}  ← عدّلها وبعدين: plan.py check \"{outp}\"")
    return 0


def cmd_gate(args):
    risk = args.impact * args.uncertainty
    if args.flag in ("ethics",):
        verdict = "⛔ وقف واعرض البديل"
    elif args.flag:
        verdict = "🔐 تأكيد إجباري (موافقة صريحة) مهما كان الوضوح"
    elif risk >= ASK_RISK or (risk >= ASK_RISK_COSTLY and args.redo >= COSTLY_REDO):
        verdict = "❓ اسأل"
    else:
        verdict = "🟡 افترض وقول الافتراض"
    print(f"الخطر = {args.impact} × {args.uncertainty} = {risk} · تكلفة الإعادة {args.redo} → {verdict}")
    return 0


def workflow_md(key, ty, patterns):
    L = [f"## {ty['name']} (`{key}`)", "",
         f"**النمط:** {patterns.get(ty.get('pattern'), ty.get('pattern'))} · **العمق الافتراضي:** {ty.get('depth')} · **التقدير:** {ty['estimate'][0]}–{ty['estimate'][1]} د", "",
         "| # | الخطوة | الأداة | الناتج | الفحص |", "|---|---|---|---|---|"]
    for i, st in enumerate(ty["workflow"], 1):
        L.append(f"| {i} | {st['do']} | {st['tool']} | {st['out']} | {st['check']} |")
    L.append("")
    if ty.get("slots"):
        L.append("**بنود كارت الفهم:** " + " · ".join(
            f"{s['label']} (أثر {s['impact']}، افتراضي: {s['default'] or 'مفيش ← سؤال'})" for s in ty["slots"]))
        L.append("")
    if ty.get("approaches"):
        L.append("**بدائل:** " + " · ".join(f"{a['name']} (+{a['gain']} / −{a['cost']})" for a in ty["approaches"]))
        L.append("")
    if ty.get("checkpoints"):
        L.append("**نقاط موافقة:** " + " · ".join(ty["checkpoints"]))
        L.append("")
    L.append("**بوابة التحقق:** " + " · ".join(ty["gates"]))
    L.append("")
    if ty.get("risks"):
        L.append("**مخاطر:** " + " · ".join(ty["risks"]))
        L.append("")
    return "\n".join(L)


def cmd_workflow(args):
    data = load_data()
    keys = list(data["types"]) if args.type == "all" else [args.type]
    for k in keys:
        if k not in data["types"]:
            print(f"✗ نوع مش معروف: {k}. المتاح: {', '.join(data['types'])}")
            return 2
    chunks = []
    if args.md and args.type == "all":
        chunks.append("# قوالب الورك فلو لكل نوع طلب\n")
        chunks.append("> متولّد من `data/task_types.json` بأمر `plan.py workflow all --md --out references/workflows.md`. "
                      "ماتعدّلش هنا، عدّل الـ JSON وولّده تاني.\n")
        chunks.append("**الأنماط:** " + " · ".join(f"`{k}` = {v}" for k, v in data["patterns"].items()) + "\n")
    for k in keys:
        chunks.append(workflow_md(k, data["types"][k], data["patterns"]))
    text = "\n".join(chunks)
    if args.out:
        outp = pathlib.Path(args.out)
        outp.parent.mkdir(parents=True, exist_ok=True)
        outp.write_text(text + "\n", encoding="utf-8")
        print(f"✓ اتكتب: {outp.resolve()} ({len(keys)} نوع)")
    else:
        print(text)
    return 0


def cmd_learn(args):
    LESSONS.parent.mkdir(parents=True, exist_ok=True)
    rec = {"ts": datetime.datetime.now().isoformat(timespec="seconds"), "type": args.type or "general",
           "lesson": args.lesson, "trigger": args.trigger or ""}
    with open(LESSONS, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"✓ الدرس اتسجّل ({rec['type']}): {rec['lesson']}")
    return 0


def cmd_lessons(args):
    les = load_lessons()
    q = tokens(args.query or "")
    shown = 0
    for l in les:
        if not q or q & tokens(l.get("lesson", "") + " " + l.get("trigger", "") + " " + l.get("type", "")):
            print(f"- [{l.get('ts', '')[:10]}] ({l.get('type')}) {l.get('lesson')}")
            shown += 1
    print(f"({shown} من {len(les)} درس)")
    return 0


def cmd_types(_args):
    data = load_data()
    for k, ty in data["types"].items():
        print(f"{k:12} {ty['name']}  · {ty.get('pattern')} · {ty.get('depth')}")
    return 0


def cmd_selftest(_args):
    if not EVALS.exists():
        print(f"✗ مفيش ملف تقييم: {EVALS}")
        return 2
    with open(EVALS, encoding="utf-8") as f:
        ev = json.load(f)
    data = load_data()
    fails = 0
    cases = ev.get("script_cases", [])
    for c in cases:
        a = analyze(c["request"], c.get("context", ""), c.get("known"), data)
        errs = []
        if "type" in c and a["type"] != c["type"]:
            errs.append(f"type={a['type']} (المتوقع {c['type']})")
        if "decision" in c and a["decision"] != c["decision"]:
            errs.append(f"decision={a['decision']} (المتوقع {c['decision']})")
        for fl in c.get("flags", []):
            if fl not in [x["key"] for x in a["flags"]]:
                errs.append(f"flag {fl} ناقص")
        if "max_questions" in c and len(a["questions"]) > c["max_questions"]:
            errs.append(f"أسئلة {len(a['questions'])} > {c['max_questions']}")
        if "depth" in c and a["depth"] != c["depth"]:
            errs.append(f"depth={a['depth']} (المتوقع {c['depth']})")
        if "decoded_contains" in c and c["decoded_contains"] not in a["decoded"]["text"]:
            errs.append(f"الفك طلّع «{a['decoded']['text']}»")
        ok = not errs
        fails += 0 if ok else 1
        print(f"{'PASS' if ok else 'FAIL'}  {c['id']:<22} → {a['type']}/{a['decision']}/{a['depth']} وضوح {a['clarity']}%"
              + ("" if ok else "  ✗ " + "؛ ".join(errs)))
    # plan checker round-trip
    tmp = ROOT / "evals" / "_selftest_plan.md"
    tmp.write_text(render_plan(analyze("اعمل ريل 9:16 من الفيديوهات دي C:/clips", data=data)), encoding="utf-8")
    import io
    import contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = check_plan(tmp)
    tmp.unlink(missing_ok=True)
    print(f"{'PASS' if rc == 0 else 'FAIL'}  plan-roundtrip          → render_plan ثم check_plan = {rc}")
    fails += 0 if rc == 0 else 1
    # negative: a plan missing sections and with an unchecked step must be rejected
    bad = ROOT / "evals" / "_selftest_bad.md"
    bad.write_text("# خطة\n\n## الهدف\nريل\n\n## الخطوات\n1. رندر من غير فحص\n", encoding="utf-8")
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc_bad = check_plan(bad)
    bad.unlink(missing_ok=True)
    ok_bad = rc_bad == 1 and "فحص" in buf.getvalue()
    print(f"{'PASS' if ok_bad else 'FAIL'}  plan-reject-bad         → خطة ناقصة اترفضت = {rc_bad}")
    fails += 0 if ok_bad else 1
    total = len(cases) + 2
    print(f"\n{total - fails}/{total} PASS")
    return 0 if fails == 0 else 1


def main():
    ap = argparse.ArgumentParser(description="العقل المخطِّط — Planning Mind helper")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("card", help="intent card + ask-gate + workflow for a request")
    c.add_argument("request")
    c.add_argument("--context", default="")
    c.add_argument("--known", nargs="*", help="slot answers already known, e.g. inputs=D:/clips aspect=16:9")
    c.add_argument("--json", action="store_true")
    c.add_argument("--plan-out")
    g = sub.add_parser("gate", help="ask-or-assume decision for one slot")
    g.add_argument("--impact", type=int, required=True, choices=range(0, 4))
    g.add_argument("--uncertainty", type=int, required=True, choices=range(0, 4))
    g.add_argument("--redo", type=int, default=0, choices=range(0, 4))
    g.add_argument("--flag", choices=["money", "publish", "delete", "irreversible", "ethics"])
    w = sub.add_parser("workflow", help="workflow template for a type (or all)")
    w.add_argument("type")
    w.add_argument("--md", action="store_true")
    w.add_argument("--out", help="write to this file (utf-8) instead of printing")
    k = sub.add_parser("check", help="validate a plan.md")
    k.add_argument("path")
    le = sub.add_parser("learn", help="append a lesson")
    le.add_argument("lesson")
    le.add_argument("--type")
    le.add_argument("--trigger")
    ls = sub.add_parser("lessons", help="list lessons")
    ls.add_argument("query", nargs="?")
    sub.add_parser("types", help="list task types")
    sub.add_parser("selftest", help="run evals/evals.json script cases")
    args = ap.parse_args()
    fn = {"card": cmd_card, "gate": cmd_gate, "workflow": cmd_workflow, "check": lambda a: check_plan(a.path),
          "learn": cmd_learn, "lessons": cmd_lessons, "types": cmd_types, "selftest": cmd_selftest}[args.cmd]
    sys.exit(fn(args))


if __name__ == "__main__":
    main()
