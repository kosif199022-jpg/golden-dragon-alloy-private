# -*- coding: utf-8 -*-
"""اقتراح: شيل الأغلفة الثابتة اللي تطبيق التنين بيلزقها حوالين طلب صاحب الشغل.

strip_wrappers(text) -> (clean_text, removed_names)

- مكتبة قياسية بس، وكل الـ regex مترجمة مرة واحدة وقت الاستيراد.
- لو مفيش نمط اتطابق: النص بيرجع زي ما هو بالحرف والقايمة فاضية.
- لو الشيل ساب نص فاضي: بيرجع النص الأصلي، إلا لو اللي اتشال بلوك نظام
  (ساعتها بيرجع "" لأن الرسالة مفيهاش طلب أصلًا).
- «(مرفقات: ...)» و«[ملف مرفق ...: المسار]» بيفضلوا، لأن اسم الملف بيفيد التوجيه.

التشغيل:  python -I -X utf8 wrappers_proposal.py
"""
import re

# ---------------------------------------------------------------- بلوكات النظام
# بلوك بين أقواس مربعة في أول الرسالة، ورأسه لازم يكون من الأسماء المعروفة دي
# (أي قوس مربع تاني زي [OPTIONS] أو [ملف مرفق ...] مابيتلمسش).
_BLOCK_HEADS = (
    ("agents_team", r"فريق الوكلاء"),
    ("workdir", r"مجلد الشغل"),
    ("mind", r"عقل التنين(?: الأحمر| الأسود)?"),
    ("analysis_tools", r"أدوات التحليل المختارة"),
    ("cc_test_block", r"اختبار(?: ربط)? من Claude Code"),
    ("live_msg", r"رسالة جديدة من المستخدم"),
    ("device_control", r"التحكم في الجهاز"),
    ("chats_update", r"تحديث من كل المحادثات"),
)
_BLOCK_HEAD_RE = re.compile(
    r"\[\s*(?:" + "|".join("(?P<%s>%s)" % (n, p) for n, p in _BLOCK_HEADS) + ")"
)
_BLOCK_NAMES = frozenset(n for n, _ in _BLOCK_HEADS)
# قفلة احتياطية لو الأقواس الداخلية مش متوازنة: أول «]» في آخر سطر.
_EOL_CLOSE_RE = re.compile(r"\][ \t]*(?:\r?\n|\Z)")
# «[أدوات التحليل المختارة] ... الملاحظة دي.»: الكلام بعد القوس جزء من الغلاف.
_TOOLS_NOTE_END_RE = re.compile(r"الملاحظة دي[ \t]*[.。!]?")
_LINE_END_RE = re.compile(r"[^\n]*(?:\n|\Z)")
# ملخص المحادثات اللي بييجي بعد «[تحديث من كل المحادثات: ...]».
_DIGEST_RE = re.compile(
    r"(?:[ \t]*(?:###[ \t]*«|النص الكامل:|🧑|🤖|🐉)[^\n]*(?:\n|\Z)|[ \t]*\r?\n)+"
)

# ------------------------------------------------------------ بادئات قبل الطلب
_PREFIXES = (
    ("skills_all", re.compile(
        r"استخدم كل المهارات المتثبتة\s*(?:\(\s*\d+\s*مهارة\s*\))?\s*مع بعض\s*:\s*"
        r"(?:اختار منها[^\n]*?في إيه\s*\.\s*)?(?:الطلب\s*:\s*)?")),
    ("skills_set", re.compile(
        r"استخدم المهارات دي مع بعض\s*(?:\(\s*\d+\s*\))?\s*:\s*"
        r"(?:«[^»\n]*»\s*[،,]?\s*)+\.?\s*"
        r"(?:حم\u0651?لها[^\n]*?في إيه\s*\.\s*)?(?:الطلب\s*:\s*)?")),
    ("skill_one", re.compile(r"استخدم مهارة\s*«[^»\n]+»\s*:\s*")),
    ("cc_test", re.compile(
        r"اختبار(?: ربط)? من Claude Code[^:\n(\[]{0,40}(?:\([^)\n]*\))?\s*:\s*")),
)

# --------------------------------------------------------------- لواحق بعد الطلب
# رسايل الخطأ بتاعة الواجهة بتبدأ بعلامة ✕، وكل اللي بعدها (حتى زرار «نسخ») مش طلب.
_ERROR_TAIL_RE = re.compile(r"\s*✕.*\Z", re.S)
# الجملة الثابتة بعد «[ملف مرفق ...]»: القوس والمسار بيفضلوا والجملة بتتشال.
_ATTACH_HINT_RE = re.compile(
    r"(\[ملف مرفق[^\]\n]*\])[ \t]*استخدم المسار ده في الأدوات[ \t]*\([^)\n]*\)[ \t]*\.?")


def _block_end(t):
    """t بيبدأ بـ «[». بيرجّع موضع ما بعد القوس اللي بيقفله، أو -1 لو البلوك مقطوع."""
    depth = 0
    for i, ch in enumerate(t):
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                return i + 1
    m = _EOL_CLOSE_RE.search(t)
    return m.start() + 1 if m else -1


def strip_wrappers(text):
    """بيرجّع (النص من غير الأغلفة، أسماء الأنماط اللي اتشالت بالترتيب)."""
    if not isinstance(text, str) or not text:
        return text, []
    names = []

    def add(n):
        if n not in names:
            names.append(n)

    s = text
    while True:
        t = s.lstrip()
        m = _BLOCK_HEAD_RE.match(t)
        if m:
            name = m.lastgroup
            add(name)
            end = _block_end(t)
            if end < 0:  # بلوك نظام مقطوع (الرسالة اتقصّت): مفيش طلب باين
                s = ""
                break
            s = t[end:]
            if name == "analysis_tools":
                m2 = _TOOLS_NOTE_END_RE.search(s) or _LINE_END_RE.match(s)
                s = s[m2.end():]
            elif name == "chats_update":
                m2 = _DIGEST_RE.match(s)
                if m2:
                    s = s[m2.end():]
            continue
        for name, rx in _PREFIXES:
            m = rx.match(t)
            if m:
                add(name)
                s = t[m.end():]
                break
        else:
            break

    s, n = _ATTACH_HINT_RE.subn(r"\1", s)
    if n:
        add("attach_hint")
    m = _ERROR_TAIL_RE.search(s)
    if m:
        add("error_tail")
        s = s[:m.start()]

    if not names:
        return text, []
    clean = s.strip()
    if not clean:
        if _BLOCK_NAMES.intersection(names):
            return "", names
        return text, []
    return clean, names


# ============================================================================
if __name__ == "__main__":
    import collections
    import json
    import os

    here = os.path.dirname(os.path.abspath(__file__))
    S = strip_wrappers
    n_cases = [0]

    # ---------------------------------------------------------- asserts
    def same(x):
        n_cases[0] += 1
        assert S(x) == (x, []), "المفروض ماتتغيّرش: %r -> %r" % (x, S(x))

    # حالات لازم ماتتغيّرش
    same("اصنع فيلم كرتون 4 ثواني")
    same("طور المهارة والقدرات  (مرفقات: black-dragon-skill.zip)")
    same(r"C:\Users\cinde\Desktop\a.mp4 قص أول 5 ثواني")
    same('@"C:\\Users\\cinde\\Downloads\\a.xlsx" @"C:\\Users\\cinde\\b.xlsx"\nطابق')
    same("https://vt.tiktok.com/x/   استخدم كل المهارات والادوات في مجلد المونتاج في عمل مونتاج")
    same("Usage: codex exec resume [OPTIONS] [SESSION_ID] [PROMPT]")
    same("[ملف مرفق (application, 14 KB): C:\\a.zip]\nحدث المرفق")
    same("  مسافات في الأول والآخر  ")
    same("")
    same("✕ مفيش اتصال بالإنترنت أو بـ API.")       # خطأ لوحده: مفيش طلب، يرجع الأصل
    same("استخدم مهارة «teardown»:")                  # بادئة لوحدها: يرجع الأصل
    same("LK")

    # حالات لازم تتغيّر
    def eq(x, clean, names):
        got = S(x)
        n_cases[0] += 1
        assert got == (clean, names), "%r\n  متوقع %r\n  طلع   %r" % (x, (clean, names), got)

    eq("استخدم كل المهارات المتثبتة (34 مهارة) مع بعض: اختار منها كل اللي يفيد الطلب، "
       "وحمّلها قبل ما تبدأ، وقول استخدمت أنهي واحدة في إيه. الطلب:  ما وظيفة كل مهارة",
       "ما وظيفة كل مهارة", ["skills_all"])
    eq("استخدم المهارات دي مع بعض (4): «black-dragon-2»، «blender-pro»، «canvas-design»، "
       "«creative-studio». حمّلها كلها قبل ما تبدأ، وقول استخدمت كل واحدة في إيه. الطلب:   اصنع فيلم",
       "اصنع فيلم", ["skills_set"])
    eq("استخدم المهارات دي مع بعض (2): «a»، «b» اصنع فيلم", "اصنع فيلم", ["skills_set"])
    eq("استخدم مهارة «black-dragon-2»: LH R]VHJ HGLIHVM", "LH R]VHJ HGLIHVM", ["skill_one"])
    eq("استخدم مهارة «windows-commands»:ما قدراتها", "ما قدراتها", ["skill_one"])
    eq("[فريق الوكلاء: عندك 2 وكيل: 1) Claude Opus 5.5. استخدم أداة delegate.]\n"
       "[مجلد الشغل: C:\\Users\\cinde\\Desktop\\خطابة 2]\nهل عندك مودل يحول الفديو الى ديزني",
       "هل عندك مودل يحول الفديو الى ديزني", ["agents_team", "workdir"])
    eq("[مجلد الشغل: C:\\work [v2]\\out]\nكمل", "كمل", ["workdir"])          # قوس جوه قوس
    eq("[عقل التنين الأحمر — الطلب: «مونتاج»\nالطريق: [montage] ← [verify]\nدروس: لا يوجد]\n"
       "اعمل مونتاج (مرفقات: a.zip)", "اعمل مونتاج (مرفقات: a.zip)", ["mind"])
    eq("[أدوات التحليل المختارة] rea، retool [triage]، omni. استخدمها وتجاهل الملاحظة دي.\nحلل الملف",
       "حلل الملف", ["analysis_tools"])
    eq("[اختبار من Claude Code بعد التحديث، رد في 3 سطور وماتشغّلش أي أداة] P'DJ TDK",
       "P'DJ TDK", ["cc_test_block"])
    eq("اختبار من Claude Code بعد التحديث (ماتنفّذش حاجة تقيلة): عايز محاكي",
       "عايز محاكي", ["cc_test"])
    eq("كمل\n✕ مفيش اتصال بالإنترنت أو بـ API.", "كمل", ["error_tail"])
    eq("وطور NovaPlay✕ وقف بخطأ بعد 0ث\nنسخ", "وطور NovaPlay", ["error_tail"])
    eq("سؤال\n✕ error: unexpected argument '-s' found\n\nUsage: codex [OPTIONS] [PROMPT]",
       "سؤال", ["error_tail"])
    eq("[رسالة جديدة من المستخدم وأنت شغال، خدها في اعتبارك من دلوقتي:]\n"
       "[ملف مرفق (application, 14253 KB): C:\\Desktop\\bd.zip] استخدم المسار ده في الأدوات "
       "(verify_media، run_engine، run_command).\nحدث المرفق",
       "[ملف مرفق (application, 14253 KB): C:\\Desktop\\bd.zip]\nحدث المرفق",
       ["live_msg", "attach_hint"])
    eq("[فريق الوكلاء: عندك 1 وكيل.]\nاستخدم مهارة «x»: كمل\n✕ خطأ", "كمل",
       ["agents_team", "skill_one", "error_tail"])
    # بلوك نظام بس من غير طلب -> نص فاضي
    eq("[فريق الوكلاء: عندك 1 وكيل.]", "", ["agents_team"])
    eq("[التحكم في الجهاز وكروم متفعّل للمحادثة دي: عندك أداة (مقطوع", "", ["device_control"])
    eq("[فريق الوكلاء: عندك 1 وكيل.]\n[تحديث من كل المحادثات: دي المحادثات.]\n\n"
       "### «ازيك» (مفتوحة 2026)\nالنص الكامل: C:\\a.md\n🧑 ازيك\n\n🧑", "",
       ["agents_team", "chats_update"])
    print("asserts: %d حالة عدّت" % n_cases[0])

    # ---------------------------------------------------------- كل الرسايل
    rows = []
    for fn in ("fresh_cc.json", "turns_all.json", "owner_requests.json"):
        p = os.path.join(here, fn)
        if not os.path.exists(p):
            print("ملف ناقص:", p)
            continue
        with open(p, encoding="utf-8-sig") as f:
            for r in json.load(f):
                q = r.get("q") if isinstance(r, dict) else None
                if isinstance(q, str):
                    rows.append((fn, q))
    uniq = list(dict.fromkeys(q for _, q in rows))

    per_all = collections.Counter()
    per_uniq = collections.Counter()
    per_file = collections.Counter()
    changed_all = 0
    for fn, q in rows:
        c, names = S(q)
        if names:
            changed_all += 1
            per_file[fn] += 1
            per_all.update(names)
    examples = collections.defaultdict(list)
    changed_uniq = emptied = 0
    for q in uniq:
        c, names = S(q)
        # ثوابت: مفيش نمط = مفيش تغيير، والدالة ثابتة لو اتطبّقت مرتين
        assert names or c == q
        assert S(c)[0] == c, "مش ثابتة: %r" % q[:80]
        if not names:
            assert "(مرفقات" not in q or "(مرفقات" in c
            continue
        assert c != q
        if "attach_hint" not in names:
            assert c in q, "الناتج مش جزء من الأصل: %r" % q[:80]
        if "(مرفقات" in q and "error_tail" not in names:
            assert "(مرفقات" in c
        changed_uniq += 1
        emptied += (c == "")
        per_uniq.update(names)
        examples[names[0]].append((q, c, names))

    print("\nالرسايل: %d (فريدة %d) | اتغيّر: %d (فريدة %d) | بقت فاضية (بلوك نظام بس): %d"
          % (len(rows), len(uniq), changed_all, changed_uniq, emptied))
    print("لكل ملف:", dict(per_file))
    print("\nالنمط              كل الرسايل   الفريدة")
    for name, n in per_all.most_common():
        print("  %-18s %6d %9d" % (name, n, per_uniq[name]))

    # 20 مثال متنوعين: بالدور على الأنماط
    picked = []
    keys = sorted(examples, key=lambda k: -len(examples[k]))
    i = 0
    while len(picked) < 20 and any(examples[k][i:] for k in keys):
        for k in keys:
            if i < len(examples[k]) and len(picked) < 20:
                picked.append(examples[k][i])
        i += 1

    def one(x):
        return x[:90].replace("\n", "⏎")

    print("\n20 مثال قبل/بعد:")
    for n, (q, c, names) in enumerate(picked, 1):
        print("%2d) %s" % (n, "+".join(names)))
        print("    قبل: " + one(q))
        print("    بعد: " + (one(c) if c else "«فاضي: بلوك نظام من غير طلب»"))
