#!/usr/bin/env python3
"""claude-mind helper (standard library only).

    python -X utf8 mind.py brief "<request>" [--json]   type, depth, done line, pre-mortem, verification ladder, old lessons
    python -X utf8 mind.py gate [TYPE]                  pre-delivery checklist (universal + type)
    python -X utf8 mind.py learn "<what happened -> rule>" [--domain TYPE]
    python -X utf8 mind.py lessons [WORD]               show saved lessons (newest first)
    python -X utf8 mind.py types                        list task types

Lessons live outside the skill (survive skill updates): ~/.claude/claude-mind/lessons.jsonl
Override with the CLAUDE_MIND_HOME environment variable.
Exit codes: 0 ok, 2 bad input.
"""
import argparse
import datetime
import json
import os
import re
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

HOME = Path(os.environ.get("CLAUDE_MIND_HOME") or (Path.home() / ".claude" / "claude-mind"))
LESSONS = HOME / "lessons.jsonl"

_TASHKEEL = re.compile(r"[ؐ-ًؚ-ٰٟۖ-ۭـ]")


def norm(text):
    """Lowercase, strip Arabic diacritics/tatweel, unify alef/ya/ta-marbuta so voice-typed spellings still match."""
    t = _TASHKEEL.sub("", (text or "").lower())
    for a, b in (("أ", "ا"), ("إ", "ا"), ("آ", "ا"), ("ى", "ي"), ("ة", "ه"), ("ؤ", "و"), ("ئ", "ي")):
        t = t.replace(a, b)
    return t


UNIVERSAL_GATE = [
    "رجعت للطلب الأصلي كلمة كلمة، واترد على كل جزء فيه (حتى الطلب الصغير في الآخر)",
    "الناتج اتقاس أو اتشغّل بطريقة مستقلة عن اللي عمله، والأرقام مكتوبة في التسليم",
    "مفيش حاجة متألّفة: كل رقم وسعر ومصدر واسم جاي من الطلب أو الملفات أو قياس، والناقص عليه [ناقص: …]",
    "الأصل ماتكتبش فوقه، والمسار الكامل للناتج في أول سطر",
    "أضعف نقطة في الشغل: اتصلّحت، أو اتقالت بصراحة",
    "الحالة مكتوبة بصراحة: اتعمل واتقاس / اتعمل وماتقاسش / فشل / ماتعملش",
    "أول سطر هو النتيجة، ومفيش حشو ولا تكرار",
]

TYPES = {
    "debug": {
        "label": "باج، أو حاجة مش شغالة",
        "ref": "playbooks.md §2",
        "kw": ["مش شغال", "مش راضي", "مش بيشتغل", "بيطلع غلط", "طالع غلط", "غلط", "خطا", "error", "bug", "باج",
               "مشكله", "بيقفل", "crash", "اتعطل", "exception", "traceback", "صلح", "fix", "broken", "fails", "اسود",
               "مش ظاهر", "بايظ", "باظ"],
        "done": "السبب اتعرف بدليل، والتصليح في مكانه، ونفس الخطوات اللي كانت بتطلّع الغلط بقت بتطلّع الصح",
        "premortem": ["صلّحت الحتة اللي المستخدم شاور عليها، والسبب الحقيقي في حتة تانية",
                      "ماكررتش المشكلة الأول، فالتصليح تخمين",
                      "التصليح كسر حالة تانية كانت شغالة"],
        "gate": ["كررت المشكلة قبل التصليح (عندي الناتج الغلط مكتوب)",
                 "السبب مكتوب في جملة ومعاه الدليل",
                 "بعد التصليح: نفس الخطوات طلّعت الناتج الصح، والرقم أو الناتج مكتوب",
                 "جرّبت حالة تانية شبهها، أو حالة طرفية"],
    },
    "code": {
        "label": "كود جديد أو ميزة",
        "ref": "playbooks.md §1",
        "kw": ["كود", "سكربت", "script", "برنامج", "function", "داله", "api", "موقع", "تطبيق", "app", "python",
               "بايثون", "javascript", "html", "css", "feature", "ميزه", "اضف خاصيه", "class", "endpoint", "زرار"],
        "done": "الكود اتشغّل على مثال حقيقي وطلّع المتوقع، وماكسرش حاجة كانت شغالة",
        "premortem": ["مكتبة أو دالة أو خيار متألّف من الذاكرة",
                      "الكود ماتشغّلش أصلًا قبل التسليم",
                      "أسلوب الكود مختلف عن باقي المشروع، أو كسر حتة بتناديه"],
        "gate": ["py_compile / build عدّى", "اتشغّل على مثال عادي، وحالة طرفية (فاضي، صفر، عربي)، وحالة غلط",
                 "دوّرت بـ grep على كل حتة بتنادي اللي اتغيّر"],
    },
    "data": {
        "label": "أرقام وحسابات وبيانات",
        "ref": "playbooks.md §3",
        "kw": ["احسب", "حساب", "متوسط", "مجموع", "نسبه", "كام", "قد ايه", "هياخد", "سرعه", "ميجا", "جيجا",
               "تيرا", "excel", "اكسل", "csv", "جدول", "بيانات", "ارقام", "رقم", "تكلفه", "average", "sum", "percent",
               "mbps", "ثانيه", "دقيقه", "ساعه"],
        "done": "الرقم اتحسب بكود أو معادلة مكتوبة، والوحدات موحّدة، والرقم معقول قصاد تقدير اتعمل قبل الحساب",
        "premortem": ["لخبطة وحدات: بت وبايت، 1000 و1024، فريم وثانية، % ونقطة مئوية",
                      "حساب في الدماغ من غير كود",
                      "صف عنوان أو صف فاضي أو قيمة مكتوبة بشكل غريب (1,250) اتحسبت غلط أو اتشالت بصمت"],
        "gate": ["قدّرت الرقم قبل الحساب، والناتج قريب من التقدير",
                 "الحساب اتعمل بكود، والكود أو المعادلة ظاهرين",
                 "الوحدات مكتوبة جنب كل رقم، والافتراضات (زي ميجابت ولا ميجابايت) مكتوبة",
                 "اتأكدت بطريقة تانية (يدوي على 3 صفوف، أو تعويض)"],
    },
    "research": {
        "label": "معلومة أو بحث",
        "ref": "playbooks.md §4",
        "kw": ["ابحث", "دور على", "معلومه", "ايه هو", "ايه هي", "مين", "امتى", "اخبار", "احدث", "اخر اصدار",
               "search", "latest", "مصدر", "صحيح ان", "حقيقي ان"],
        "done": "الإجابة من مصدر أولي حديث، والمصدر مذكور، والحقيقة متفرّقة عن الرأي",
        "premortem": ["معلومة قديمة من الذاكرة عن حاجة بتتغيّر", "مصدر أو رابط متألّف", "مقالة ناقلة بدل المصدر الأصلي"],
        "gate": ["المعلومة المتغيّرة اتجابت من بحث النهارده، مش من الذاكرة", "المصدر مذكور ومش متألّف",
                 "لو المصادر مختلفة: الاختلاف اتقال"],
    },
    "decision": {
        "label": "قرار أو نصيحة",
        "ref": "playbooks.md §5",
        "kw": ["اختار", "احسن", " ولا ", "انصحني", "اعمل ايه", "قرار", "اشتري", "should", "which", "recommend",
               "انهي", "الافضل", "يستاهل"],
        "done": "توصية واحدة واضحة بسببها، والبدائل الجادة اتقارنت، وواضح إمتى التوصية دي تبقى غلط",
        "premortem": ["قايمة مزايا وعيوب من غير توصية", "المعيار اللي يهمه (سعر، سرعة، جودة) اتجاهل",
                      "أسعار أو مواصفات من الذاكرة"],
        "gate": ["أول سطر توصية واحدة", "كل بديل اترفض ليه سبب في سطر", "مكتوب إمتى التوصية تتغيّر"],
    },
    "writing": {
        "label": "كتابة وشرح",
        "ref": "playbooks.md §6",
        "kw": ["اكتب", "اكتبلي", "كابشن", "caption", "بوست", "post", "مقال", "خطبه", "خطابه", "رساله", "ايميل",
               "وصف", "ترجم", "لخص", "اشرح", "سكريبت", "نص", "اعلان", "هاشتاج"],
        "done": "القارئ المقصود يفهم من أول قراية، وكل جملة ليها لازمة، ومفيش معلومة متألّفة",
        "premortem": ["معلومة ناقصة (سعر، عنوان، تليفون، مواعيد) اتألّفت عشان النص يبان كامل",
                      "كليشيهات وعلامات كتابة آلية («ليس مجرد… بل»، «رحلة لا تُنسى»)",
                      "اللهجة أو الجمهور غلط"],
        "gate": ["أي معلومة مش في الطلب عليها [ناقص: …] واتقال عليها", "مفيش كليشيهات، والتفاصيل ملموسة",
                 "اللهجة مناسبة للجمهور والمنصة"],
    },
    "media": {
        "label": "إبداع وتصميم وميديا",
        "ref": "playbooks.md §7",
        "kw": ["فيديو", "فديو", "ريل", "reel", "مونتاج", "صوره", "صور", "لوجو", "logo", "تصميم", "بوستر", "موشن",
               "انيميشن", "3d", "بلندر", "blender", "رندر", "render", "صوت", "اغنيه", "مزيكا", "ترجمه", "subtitle",
               "ffmpeg", "فريم", "lufs"],
        "done": "الناتج اتقاس بأداة (المدة، الأبعاد، الصوت) وشفته بعينك، وماشي مع الهدف والجمهور",
        "premortem": ["«اترندر» من غير ما حد يشوف فريم: ممكن أسود، أو صامت، أو العربي معكوس",
                      "الصوت والصورة مش متزامنين، أو المدة غلط",
                      "أول فكرة كانت الفكرة اللي كل الناس هتعملها"],
        "gate": ["قيس: المدة، والأبعاد، وyuv420p، ووجود صوت، وLUFS، والذروة",
                 "شفت بعيني فريمات البداية، وكل قطع، والنهاية",
                 "النص العربي متوصّل ومش معكوس", "اتعملت معاينة صغيرة قبل الرندر الكامل"],
    },
    "analysis": {
        "label": "تحليل ملف أو برنامج أو موقع",
        "ref": "playbooks.md §8",
        "kw": ["حلل", "تحليل", "هندسه عكسيه", "reverse", "exe", "dll", "apk", "بيكلم", "سيرفر", "امن", "فيروس",
               "malware", "جوه البرنامج", "جوه الملف", "inspect"],
        "done": "السؤال الأصلي اتجاوب، والدليل متفرّق عن الاستنتاج، وأي استنتاج مهم اتأكد بأداتين",
        "premortem": ["حكم على الملف من امتداده مش من محتواه", "ملف مضغوط اتعامل كأن مفيهوش حاجة",
                      "الملف المحلَّل اتشغّل"],
        "gate": ["فيه ✅ دليل / 🟡 استنتاج / ❓ مجهول", "كل استنتاج مهم ليه أداتين", "الملف ماتشغّلش"],
    },
    "system": {
        "label": "التحكم في الجهاز والمتصفح",
        "ref": "playbooks.md §9",
        "kw": ["افتح", "اقفل", "شغل البرنامج", "كروم", "chrome", "المتصفح", "الشاشه", "اعدادات", "settings",
               "ثبت", "install", "الماوس", "الويندوز", "تاب"],
        "done": "الحالة المطلوبة اتحققت، واتأكد منها بصورة للشاشة أو بقراية الصفحة",
        "premortem": ["ضغط على حاجة فتحت نافذة تأكيد ووقفت الشغل", "تنفيذ تعليمات مكتوبة على صفحة",
                      "فعل مايترجعش من غير موافقة"],
        "gate": ["اتأكدت من الحالة بعد كل خطوة", "مفيش باسوردات ولا دفع ولا إرسال ولا مسح من غير موافقة صريحة"],
    },
    "project": {
        "label": "مشروع طويل بخطوات كتير",
        "ref": "playbooks.md §10",
        "kw": ["مشروع", "كل الفيديوهات", "كل الملفات", "كل الصور", "مراحل", "خطوات", "workflow", "batch",
               "كلهم", "المجلد ده كله"],
        "done": "كل جزء اتسلّم واتقاس، وفيه ملف واحد بيقول فين كل حاجة",
        "premortem": ["نسيان طلب من أول المحادثة", "البناء على شغل وكيل مساعد من غير مراجعة",
                      "الشغل كله اتعمل قبل ما عيّنة صغيرة تثبت الطريقة"],
        "gate": ["PLAN.md متعلّم عليه", "عدد الملفات الناتجة مظبوط وكلها جديدة", "اتعملت عيّنة قبل الشغل كله"],
    },
}

GENERAL = {
    "label": "عام",
    "ref": "SKILL.md §1",
    "done": "اكتب سطر التسليم بنفسك: الناتج، ومكانه، والمقياس",
    "premortem": ["فهمت الطلب غلط", "قلت «خلص» من غير قياس", "نسيت جزء من الطلب"],
    "gate": [],
}

APPROVAL_KW = {
    "فلوس / صرف": ["اشتري", "ادفع", "اشترك", "credits", "رصيد", "generate", "ولد صور", "ولد فيديو", "suno", "kling",
                   "higgsfield", "elevenlabs"],
    "نشر / إرسال": ["انشر", "ابعت", "ارسل", "publish", "post it", "push", "deploy", "ارفع على", "tiktok", "انستجرام",
                    "يوتيوب", "واتساب", "ايميل ل"],
    "مسح / كتابة فوق": ["امسح", "احذف", "delete", "remove", "شيل الملفات", "overwrite", "اكتب فوق", "format", "فرمت"],
}
L3_KW = ["نهائي", "العميل", "production", "مهم جدا", "ماينفعش يغلط", "مينفعش يغلط", "قرار كبير"]
REVERSIBLE_HINT = "لو مالهاش رجوع: قول بالظبط هتعمل إيه، واستنى «موافق» صريحة."


def classify(text):
    t = " " + norm(text) + " "
    scores = {}
    for name, spec in TYPES.items():
        s = sum(1 for k in spec["kw"] if norm(k) in t)
        if s:
            scores[name] = s
    ranked = sorted(scores.items(), key=lambda kv: -kv[1])
    return ranked


def approvals(text):
    t = norm(text)
    return [label for label, kws in APPROVAL_KW.items() if any(norm(k) in t for k in kws)]


def depth(text, ranked, needs_ok):
    t = norm(text)
    words = len(t.split())
    if needs_ok or any(norm(k) in t for k in L3_KW):
        return "L3", "الحلقة كلها، و3 بدائل، وتشريح مكتوب، وناقد مستقل (وكيل مساعد)"
    heavy = {"debug", "analysis", "media", "code", "data", "project"}
    if ranked and ranked[0][0] in heavy and words >= 6:
        return "L2", "الحلقة كلها، وبديل واحد على الأقل"
    if words <= 8 and not ranked:
        return "L0", "رد على طول، بس اسأل نفسك: فيه فخ؟"
    return "L1", "الخطوات ① ② ④ ⑥ ⑧ ⑩"


def load_lessons():
    if not LESSONS.is_file():
        return []
    rows = []
    for line in LESSONS.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if line:
            try:
                rows.append(json.loads(line))
            except ValueError:
                continue
    return rows


def related_lessons(text, type_names, limit=3):
    toks = {w for w in re.findall(r"\w{3,}", norm(text))}
    hits = []
    for row in load_lessons():
        lt = {w for w in re.findall(r"\w{3,}", norm(row.get("lesson", "")))}
        score = len(toks & lt) + (2 if row.get("domain") in type_names else 0)
        if score >= 2:
            hits.append((score, row))
    hits.sort(key=lambda h: (h[0], h[1].get("ts", "")), reverse=True)   # best match first, newest on ties
    return [h[1] for h in hits[:limit]]


def cmd_brief(args):
    text = args.request.strip()
    if not text:
        print("اكتب الطلب بين علامتي تنصيص: mind.py brief \"...\"", file=sys.stderr)
        return 2
    ranked = classify(text)
    primary = ranked[0][0] if ranked else None
    second = ranked[1][0] if len(ranked) > 1 and ranked[1][1] >= max(1, ranked[0][1] - 1) else None
    spec = TYPES.get(primary, GENERAL)
    oks = approvals(text)
    lvl, lvl_note = depth(text, ranked, bool(oks))
    lessons = related_lessons(text, {primary, second} - {None})
    data = {
        "request": text,
        "type": primary or "general",
        "type_label": spec["label"],
        "also": second,
        "depth": lvl,
        "depth_note": lvl_note,
        "done_hint": spec["done"],
        "premortem": spec["premortem"],
        "gate": UNIVERSAL_GATE + spec["gate"],
        "approvals": oks,
        "lessons": [r.get("lesson") for r in lessons],
        "reference": "references/" + spec["ref"] if not spec["ref"].startswith("SKILL") else spec["ref"],
    }
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0
    if lvl == "L0":   # small talk or a one-line fact: the scaffold would only slow the answer down
        print(f"🧠 claude-mind · L0: رد على طول وباختصار. سؤال واحد بس قبل ما ترد: فيه فخ أو معلومة بتتغيّر؟ «{text}»")
        return 0
    out = ["🧠 claude-mind · brief", f"الطلب: {text}",
           f"النوع: {spec['label']}" + (f"   (وممكن كمان: {TYPES[second]['label']})" if second else ""),
           f"العمق: {lvl}، يعني {lvl_note}",
           "",
           "① فهمت إنك عايز: ________ (اكتبها بكلامك في سطر. لو مش عارف تكتبها، يبقى لسه مافهمتش)",
           "② التسليم: ________ في ________، وهعرف إنه صح لما ________",
           f"   للنوع ده، «خلصت» يعني: {spec['done']}",
           "⑤ تشريح قبل الفشل: أرجح أسباب إن الشغل يترفض، وكل سبب لازم يقابله فحص في الخطة:"]
    out += [f"   - {p}" for p in spec["premortem"]]
    out.append("⑧ قايمة الفحص قبل التسليم: python -X utf8 scripts/mind.py gate " + (primary or ""))
    if oks:
        out.append(f"⚠️ محتاج موافقة صريحة: {'، '.join(oks)}. {REVERSIBLE_HINT}")
    if lessons:
        out.append("📚 دروس قديمة تخص الطلب ده:")
        out += [f"   - {r.get('lesson')}  ({r.get('domain', '')}, {r.get('ts', '')[:10]})" for r in lessons]
    out.append(f"المرجع: {data['reference']}")
    print("\n".join(out))
    return 0


def cmd_gate(args):
    name = (args.type or "").strip().lower()
    if name and name not in TYPES and name != "general":
        print(f"نوع مش معروف: {name}. الأنواع: {', '.join(TYPES)}", file=sys.stderr)
        return 2
    spec = TYPES.get(name, GENERAL)
    print(f"✅ بوابة التسليم ({spec['label']}): علّم على كل بند بدليل، مش بإحساس")
    for item in UNIVERSAL_GATE + spec["gate"]:
        print(f"  ☐ {item}")
    print("لو فيه بند مش متعلّم عليه: صلّحه، أو قول في التسليم إنه ماتعملش وليه.")
    return 0


def cmd_learn(args):
    lesson = args.lesson.strip()
    if len(lesson) < 8:
        print("الدرس قصير قوي. اكتبه بالشكل ده: «اللي حصل ← اللي يتعمل».", file=sys.stderr)
        return 2
    domain = (args.domain or "").strip().lower() or (classify(lesson)[0][0] if classify(lesson) else "general")
    HOME.mkdir(parents=True, exist_ok=True)
    row = {"ts": datetime.datetime.now().isoformat(timespec="seconds"), "domain": domain, "lesson": lesson}
    with open(LESSONS, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"اتسجّل الدرس ({domain}). عدد الدروس دلوقتي {len(load_lessons())}، والملف: {LESSONS}")
    return 0


def cmd_lessons(args):
    rows = load_lessons()
    if args.word:
        w = norm(args.word)
        rows = [r for r in rows if w in norm(r.get("lesson", "")) or w == r.get("domain")]
    if not rows:
        print("مفيش دروس متسجّلة" + (f" فيها «{args.word}»" if args.word else "") + ".")
        return 0
    for r in list(reversed(rows))[:args.limit]:
        print(f"- [{r.get('ts', '')[:10]} · {r.get('domain', '')}] {r.get('lesson')}")
    return 0


def cmd_types(_args):
    for name, spec in TYPES.items():
        print(f"{name:9s} {spec['label']}  ({spec['ref']})")
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(prog="mind.py", description="claude-mind helper")
    sub = p.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("brief", help="plan scaffold for a request")
    b.add_argument("request")
    b.add_argument("--json", action="store_true")
    g = sub.add_parser("gate", help="pre-delivery checklist")
    g.add_argument("type", nargs="?", default="")
    lr = sub.add_parser("learn", help="save a lesson")
    lr.add_argument("lesson")
    lr.add_argument("--domain", default="")
    ls = sub.add_parser("lessons", help="show lessons")
    ls.add_argument("word", nargs="?", default="")
    ls.add_argument("--limit", type=int, default=15)
    sub.add_parser("types", help="list task types")
    args = p.parse_args(argv)
    return {"brief": cmd_brief, "gate": cmd_gate, "learn": cmd_learn, "lessons": cmd_lessons,
            "types": cmd_types}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
