#!/usr/bin/env python3
"""Red Dragon «التنين الأحمر» — the brain above the Black Dragon engine. Standard library only.

  python scripts/rd.py start                 first thing when the package reaches Claude
  python scripts/rd.py understand "<نص>"     fix wrong-keyboard and voice-typing slips
  python scripts/rd.py brief "<الطلب>"       short mission brief as JSON (used by the desktop app)
  python scripts/rd.py plan "<الطلب>"        mission plan: playbook + steps for this place + gates + lessons
                                             (--prev "<الرسالة اللي قبلها>"; default: the chat topic brief() kept for 45 min)
  python scripts/rd.py route|map|show        find / list / open a playbook or a power (route: confidence + the 3 nearest past requests)
  python scripts/rd.py learn|recall|outcome|retro|memory   self-learning (outcome … ok also keeps the request as a routing example)
  python scripts/rd.py teach "<الطلب>" ID|none   a request went to the wrong playbook: remember the right one
  python scripts/rd.py selftest [--quick]    registries + tests + the blind routing gate (mind/route_eval/floor.json, ~12 s more)
  python scripts/rd.py skills find "<كلمات>"  search the bundled library of 200 famous Claude skills (list / show NAME / install NAME)
  python scripts/rd.py re TARGET             what a file / folder / URL is, and the analysis road
  python scripts/rd.py repo PATH             dossier of a source repository (read-only)
  python scripts/rd.py intel "<words>"       search the dossiers bundled in mind/intel
  python scripts/rd.py doctor                what is reachable here
  python scripts/rd.py chats "<سؤال>"        memory of every past conversation (what was asked, decided, delivered)
  python scripts/rd.py files "<كلمة>"        delivered file paths from those chats + does each still exist
  python scripts/rd.py guard PATH            is another session writing this folder? (--save / --diff snapshot, lock / unlock)
  python scripts/rd.py x ARGS...             pass through to the engine (engine/scripts/dragon.py)
  python scripts/rd.py fuse brief|route|tools|protocol|find|show|recipes|lessons|doctor|selftest
                                             v3.4: the fusion brain (depth L0-L3, recipes, 22 thinking tools) in-process
  python scripts/rd.py check --request "<الطلب>" --draft FILE|-   v3.4: critic gate on the answer before sending it
It reads and advises; it never installs, publishes, spends or deletes."""
import argparse, datetime, hashlib, json, math, os, re, shutil, subprocess, sys, types
from pathlib import Path

VERSION = "3.5.8"
ROOT = Path(__file__).resolve().parent.parent
ENGINE = ROOT / "engine"
MIND = ROOT / "mind"
MEM = Path(os.environ.get("RED_DRAGON_HOME") or Path.home() / ".red-dragon")
# v2.4: what the white dragon learned on this machine is read too (read-only, never written).
LEGACY_MEM = [Path(os.environ.get("WHITE_DRAGON_HOME") or Path.home() / ".white-dragon")]
COST = {"free": "✅ ببلاش", "ask": "🔒 بموافقة", "paid": "💰 مدفوع", "never": "⛔ ممنوع"}
COST_RANK = {"free": 0, "ask": 1, "paid": 2, "never": 3}

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ------------------------------------------------------------------ words
AR_DIAC = re.compile("[ً-ْـ]")
STOP = set("في من على عن الى إلى ده دي دا اللي عايز عاوز اعمل اعملي ممكن يا كل مع او أو و the a an of to for and or in on with me my this that please make do".split())
PREFIXES = ("وبال", "فبال", "وال", "فال", "بال", "كال", "لل", "ال")


def norm(s):
    s = AR_DIAC.sub("", str(s).lower())
    return re.sub("[إأآا]", "ا", s).replace("ة", "ه").replace("ى", "ي")


def tokens(s):
    out = []
    for w in re.findall(r"[\w؀-ۿ]+", norm(s)):
        for p in PREFIXES:
            if w.startswith(p) and len(w) - len(p) >= 3:
                w = w[len(p):]
                break
        if len(w) > 1 and w not in STOP:
            out.append(w)
    return out


def match(a, b):
    if a == b:
        return 2
    if min(len(a), len(b)) >= 4 and (a.startswith(b) or b.startswith(a)):
        return 1
    return 0


def score(qt, bag):
    return sum(max((match(t, k) for k in bag), default=0) for t in qt)


# ------------------------------------------------------------------ place
def place():
    """cloud-chat (claude.ai), cloud-code (Claude Code remote), pc-owner (the owner's laptop), pc-other."""
    m = os.environ.get("RED_DRAGON_MODE") or os.environ.get("DRAGON_MODE")
    if m:
        return {"pc": "pc-owner", "cloud": "cloud-chat"}.get(m, m)
    if Path("/mnt/user-data").exists():
        return "cloud-chat"
    if os.environ.get("CLAUDE_CODE_REMOTE") == "true":
        return "cloud-code"
    owner = (Path.home() / "OneDrive" / "Desktop" / "التنين الأسود").exists() or (Path.home() / "OneDrive" / "Desktop" / "مهارات" / "التنين الأسود").exists() or (Path.home() / "re-tools" / "retool.py").exists()
    return "pc-owner" if owner else "pc-other"


def is_pc(p=None):
    return (p or place()).startswith("pc")


# ------------------------------------------------------------------ data
def jload(p, default=None):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:
        return default


def playbooks():
    d = jload(MIND / "playbooks.json", {"playbooks": []})
    for p in d["playbooks"]:
        p["_tok"] = set(tokens(p.get("triggers", "") + " " + p["ar"] + " " + p.get("en", "")))
        p["_ph"] = [norm(x).strip() for x in p.get("phrases", []) if len(norm(x).strip()) >= 4]     # v2.8: whole phrases = a bonus
    return d["playbooks"]


def powers():
    out = []
    for f, src in ((ENGINE / "tools" / "powers" / "powers.json", "engine"), (MIND / "connections.json", "red")):
        d = jload(f, {})
        for p in d.get("powers", []):
            p["_src"] = src
            p["_tok"] = set(tokens(p.get("triggers", "") + " " + p.get("ar", "") + " " + p.get("en", "")))
            out.append(p)
    return out


# ------------------------------------------------------------------ memory (self-learning)
def mem_file(name):
    MEM.mkdir(parents=True, exist_ok=True)
    return MEM / name


def lessons():
    """Bundled seed lessons + what this machine learned. Later lines win on the same id."""
    rows = {}
    for f in (MIND / "lessons_seed.jsonl", *[m / "lessons.jsonl" for m in LEGACY_MEM], MEM / "lessons.jsonl"):
        if f.is_file():
            for ln in f.read_text(encoding="utf-8").splitlines():
                try:
                    r = json.loads(ln)
                    rows[r["id"]] = {**rows.get(r["id"], {}), **r}
                except Exception:
                    continue
    return list(rows.values())


def lesson_id(text):
    return hashlib.sha1(" ".join(tokens(text)).encode("utf-8")).hexdigest()[:10]


def learn(text, domain="general", trigger="", kind="rule", source="owner"):
    text = " ".join(str(text).split())
    if len(text) < 8:
        raise SystemExit("الدرس قصير قوي: اكتب إيه اللي حصل وإيه اللي يتعمل المرة الجاية.")
    if re.search(r"(sk-ant-|sk-[A-Za-z0-9]{24,}|ghp_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|password\s*[:=])", text):
        raise SystemExit("الدرس فيه حاجة شبه مفتاح أو باسورد: مااتحفظش.")
    lid = lesson_id(text)
    old = next((l for l in lessons() if l["id"] == lid), None)
    row = {"id": lid, "text": text, "domain": domain, "trigger": trigger, "kind": kind, "source": source,
           "date": datetime.date.today().isoformat(), "seen": (old or {}).get("seen", 0) + 1, "hits": (old or {}).get("hits", 0)}
    with mem_file("lessons.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row, bool(old)


def recall(q, limit=6, domain=None, minscore=2):
    qt = tokens(q)
    out = []
    for l in lessons():
        s = score(qt, set(tokens(l["text"] + " " + l.get("trigger", "") + " " + l.get("domain", ""))))
        if domain and l.get("domain") == domain:
            s += 1
        if s >= minscore:
            out.append((s + min(l.get("seen", 1), 3) * 0.3, l))      # a lesson repeated by the owner weighs more
    out.sort(key=lambda x: -x[0])
    return [l for _, l in out[:limit]]


def outcomes():
    """playbook id -> {ok, fail}. Read from the append-only outcome log."""
    d = {}
    for f in (*[m / "outcomes.jsonl" for m in LEGACY_MEM], MEM / "outcomes.jsonl"):
        if not f.is_file():
            continue
        for ln in f.read_text(encoding="utf-8").splitlines():
            try:
                r = json.loads(ln)
                d.setdefault(r["id"], {"ok": 0, "fail": 0})[r["result"]] += 1
            except Exception:
                continue
    return d


def trust(pid, oc):
    """Laplace-smoothed success rate: 0.5 with no history, moves with evidence."""
    o = oc.get(pid, {"ok": 0, "fail": 0})
    return (o["ok"] + 1) / (o["ok"] + o["fail"] + 2)


# ------------------------------------------------------------------ route / plan
# words that carry no task (Egyptian question words and filler); "فين", "خلصت", "عملت" stay: they mean status
QSTOP = set(norm(w) for w in "ايه ازاي ازى هل هو هي هى دي ده دا ما ماذا لماذا ليه لو عشان علشان بس كده برضه انا انت احنا لي ليا "
            "عندي عندك ممكن عايزك عاوزك اريد اريدك قم كمان تاني الان دلوقتي جدا اي اى ايضا كمان بكل جميع لكل الذي التي اللى".split())
SUFFIX = ("ات", "ين", "ون", "ها", "هم", "كم", "نا", "يه", "ه")
_idf = {}


def _stem(w):
    for suf in SUFFIX:
        if len(w) - len(suf) >= 3 and w.endswith(suf):
            return w[: -len(suf)]
    return w


def _lev1(a, b):
    """True when a and b differ by one insertion, deletion or substitution."""
    if abs(len(a) - len(b)) > 1:
        return False
    if len(a) > len(b):
        a, b = b, a
    i = j = d = 0
    while i < len(a) and j < len(b):
        if a[i] != b[j]:
            d += 1
            if d > 1:
                return False
            if len(a) == len(b):
                i += 1
            j += 1
        else:
            i += 1
            j += 1
    return d + (len(b) - j) + (len(a) - i) <= 1


def _tmatch(a, b):
    if a == b:
        return 2.0
    if min(len(a), len(b)) >= 4 and (a.startswith(b) or b.startswith(a)):
        return 1.0
    sa, sb = _stem(a), _stem(b)
    if len(sa) >= 3 and sa == sb:
        return 1.6
    if min(len(a), len(b)) >= 5 and _lev1(a, b):   # one slip of voice typing: فديو / فيديو, مهارهة / مهاره
        return 1.0
    return 0.0


def _route_idf(pbs):
    key = tuple(p["id"] for p in pbs)
    if _idf.get("k") != key:
        n = len(pbs)
        df = {}
        for p in pbs:
            for t in p["_tok"]:
                df[t] = df.get(t, 0) + 1
        w = {t: math.log((n + 1) / (c + 0.5)) for t, c in df.items()}
        mean = sum(w.values()) / max(1, len(w))
        _idf.update(k=key, w={t: v / mean for t, v in w.items()})
    return _idf["w"]


INTENT = [  # (pattern on the normalized text, playbook id, bonus): few, general, high precision
    (r"(حلل|افحص|ادرس)\S*.{0,80}(اصنع|اعمل|ابني|سوي)\S*.{0,40}(مثله|زيه|شبيه|شبهه|نسخه|نفسه)", "clone-own-tool", 6.0),
    (r"(طور|طوير|تطوير|ارفع|زود|حسن|قوي)\S*.{0,60}(التنين|نفسك|ذكاءك|ذكائك|قدراتك|(تفكير|ذكاء|ذكائ|عقل)(ه|ك|ها)(?!\w)"
     r"|(تفكير|ذكاء|عقل)\s+(ال)?(تنين|طائر))", "self-improve", 5.0),     # v2.14: «طور تفكيره وذكائه», «حسن عقل الطائر»
    (r"(فين|وين)\s+(الملف|الفيديو|الفديو|المهاره|النسخه|الناتج)|^(خلصت|عملت ايه|وصلت لفين)", "status", 5.0),
    (r"(اصنع|اعمل|ابني|سوي|انشئ)\S*\s+(لي\s+|لكلاود\s+)?مهار", "build-skill", 4.0),
    # v2.8, from the blind-labelled dev half: status questions, the owner's own app, and growing the dragon itself
    (r"^\W*(هل\s+)?(خلصت|خلصتي|خلصتو|انتهيت)\W*$|خلصت\s+ولا|ولا\s+لسه|^\W*هل\s+(صنعت|عملت|انتهيت|خلصت)|باقي\s+(لك|ليك)\s|قدامك\s+قد\s+ايه"
     r"|(فين|وين)\s+(مكان|الرابط|اللينك|مكانها|مكانه)|^\W*(ما|ايه)\s+(التطوير|اللي)\s+(الذي\s+|اللي\s+)?(قمت|عملته|عملت)|^\W*هل\s+(هو|هي)\s+شغال", "status", 5.0),
    (r"(التطبيق|البرنامج|النسخه)\S*\s.{0,30}(مش شغال|لا يعمل|ما يعمل|واقف|ما اتحدث|مااتحدث|ماتحدث|بايظ|بيقفل|فيه مشكله|في مشكله)"
     r"|^\W*(حدث|خدث)\s+(التطبيق|البرنامج|النسخه)|مشكله\s+التحديث|^\W*اضف\s+(فيه\s+|للتطبيق\s+|للبرنامج\s+)?(امكانيه|خاصيه|ميزه|زرار|زر)", "app-dev", 4.0),
    (r"ملف\s+(ال)?تعليمات|كل\s+(قدراتك|امكانياتك)|(حمل|نزل|ثبت)\S*\s.{0,40}(تساعد|تفيد)\S*\s+(claude|كلاود|التنين|نفسك)", "self-improve", 4.0),
]
URL_ONLY = [(r"github\.com/", "re-repo"), (r"(tiktok\.com|youtu\.?be|instagram\.com|facebook\.com|x\.com/|twitter\.com)", "download")]
# v2.8: chat that is never a task, and short replies that only continue the previous message
GREET_RX = (r"^\W*(ازيك|ازيكم|اهلا|مرحبا|السلام عليكم|صباح الخير|مساء الخير|من انت|مين انت|انت مين|شكرا|تمام|بالعربي|لا\W*كفايه|كفايه)\W*$")
NONE_EXTRA = r"^\W*(قول|قل|رد|اكتب)\W+(تم|كلمه واحده|بكلمه)|^\W*تم تسجيل الدخول|^\W*(رد|جاوب)\W+.{0,20}بكلمه"
CONT_RX = (r"^\W*(موافق|ماشي|اوك|ok|كمل|اكمل|يلا|ابدا|نعم|ايوه|اه|جرب|حلها|اصلح وكمل|كمل وصلح|نفذ|ثبتها|ثباها)\W*$")
# v3.0 (golden): a SHORT complaint about the work just done («التحميل لا يعمل», «حل المشكلة», «المحاكي ما فتحش ليه») is a
# follow-up, not a new task: its own words («تحميل», «محاكي») must not pick a fresh road over the topic of the chat.
FIX_RX = (r"(لا يعمل|لا تعمل|مش شغال|مش بيشتغل|مابيشتغلش|ما ?اشتغلش|ما ?فتحش|مش بيفتح|ما ?بيفتحش|لا يفتح|مش راضي|بايظ|باظ|"
          r"حل المشكله|صلح المشكله|اصلح المشكله|حل الخطا|صلح الخطا|فيه مشكله|في مشكله|فيه خطا|مش ظاهر|مش طالع|وقف|علق|مفيش حاجه حصلت)")
FIX_MAX = 8                 # tokens: longer messages carry their own task
NONE_RX = (r"^\W*(ازيك|ازيكم|اهلا|مرحبا|السلام عليكم|صباح الخير|مساء الخير|من انت|مين انت|انت مين|شكرا|تمام|موافق|ماشي|اوك|ok|كمل|اكمل|يلا)\W*$")  # v2.7, kept for older callers
# v2.8: a greeting with only small talk around it («ازيك يا تنين عامل ايه», «شكرا يا باشا») is chat too, and
# «تمام يا تنين كمل» is a follow-up: the small-talk words are taken off before CONT_RX is tried.
CHAT_HEAD = set(norm(w) for w in "ازيك ازيكم ازيكو اهلا هلا مرحبا هاي السلام صباح مساء شكرا متشكر متشكرين تسلم ميرسي تمام hi hello hey thanks thx".split())
CHAT_WORDS = CHAT_HEAD | set(norm(w) for w in "عليكم الخير النور الفل الورد عامل عامله عاملين اخبارك اخباركم الاخبار اخبار كيفك كيف حالك حالكم الحال "
                                              "ايه يا تنين التنين الاحمر الاسود دراجون كلود حبيبي حبيب باشا معلم يسطا صاحبي جدا اوي خالص كتير بجد والله "
                                              "الحمد لله كده خلاص الف مليون you how are".split())
NO_CARRY = {"none", "status"}       # v2.8: a status question asks about the work, it is not a topic the next message inherits
# ------------------------------------------------------------------ consent (v2.14)
# «كمل» keeps the work going; it is not a yes to anything that leaves the PC or can't be undone. Measured 2026-11-14: «كمل»
# right after «ارفعه؟» was read as a push approval and the safety layer refused the push. An action counts as approved only
# when the message itself names it; a bare «موافق/ايوه/نفذ» covers only what the last question named (the brain can't see it).
CONSENT_AR = {"publish": "الرفع أو النشر", "install": "التثبيت", "delete": "المسح", "spend": "الفلوس أو الرصيد", "merge": "الدمج في main"}
_C_OBJ = ("هالي", "هولي", "هملي", "هالك", "لي", "هم", "ها", "هو", "وه", "ه", "و", "وا", "ة", "ي", "يه", "ك", "")
_C_ROOT = {"publish": ("رفع", "نشر"), "install": ("ثبت", "سطب"), "delete": ("مسح", "حذف"),
           "spend": ("دفع", "شتري", "شتر", "صرف", "شحن"), "merge": ("دمج",)}
_C_IMP = {"publish": ("ارفع", "انشر"), "install": ("ثبت", "اثبت", "سطب"), "delete": ("امسح", "احذف"),
          "spend": ("ادفع", "اشتري", "اشتر", "اصرف", "اشحن"), "merge": ("ادمج",)}
_C_NOUN = {k: set(norm(v).split()) for k, v in {
    "publish": "الرفع رفع النشر نشر", "install": "التثبيت تثبيت التسطيب تسطيب التحديث تحديث",
    "delete": "المسح مسح الحذف حذف", "spend": "الدفع دفع الشرا الشراء شراء الاشتراك اشتراك السبونسر سبونسر", "merge": "الدمج دمج"}.items()}
_C_TRANS = {k: set(norm(v).split()) for k, v in {    # English verbs written in Arabic letters
    "publish": "بوش ابوش ديبلوي ابلود اببلود بوست", "install": "انستول انستل ابديت اپديت", "delete": "ديليت دليت",
    "spend": "سابسكرايب سبسكرايب", "merge": "ميرج"}.items()}
_C_SPOT = "تايتل عنوان نص كلام كابشن ترجمه لوجو شعار علامه عنصر ايقونه زرار طبقه مكان ركن فوق لفوق تحت لتحت يمين شمال وسط"
_C_CUT = "اول اخر ثواني ثانيه ثانيتين دقيقه دقايق جزء مشهد مشاهد لقطه لقطات فريم فريمات"
_C_TRAP = {k: set(norm(v).split()) for k, v in {   # the same verb on an edit or a layout, not on the PC or the repo
    "publish": "صوت جوده دقه حجم اضاءه سطوع فوليوم مستوي مستوى سرعه ريزوليوشن تباين كونتراست بيتريت فريم فريمات درجه نسبه قيمه "
               "حده لون الوان تشبع شارب ان in " + _C_SPOT,          # «اعمل بوش ان للكاميرا» = a camera push-in
    "install": "كاميرا كادر لقطه لقطات فيديو صوره شاشه تصوير حركه خط ايد موبايل تليفون عين نظر " + _C_SPOT,
    "delete": "خلفيه ضوضاء نويز صوت علامه ووترمارك لوجو كلام صدي اكو حروف ترجمه بقع بقعه كلمه كلمات سطر جمله ضوئي " + _C_CUT,
    "spend": "نظر دماغك دماغي دماغ كليب مقطع لقدام قدام لورا تايملاين",          # «ادفع الكليب لقدام» moves a clip
    "merge": "فيديو فيديوهين فيديوهات مقطع مقطعين مقاطع صور صورتين صوت اغنيه كليب كليبين لقطات لقطتين طبقات الطبقات للطبقات طبقتين لير لاير لايرز تراك تراكات"}.items()}
_C_FILES = set(norm("ملف ملفات فولدر مجلد ريبو مستودع نسخه نسخ فرع برانش شات شاتات حساب").split())
_C_PLACES = set(norm("يوتيوب اليوتيوب تيك تيكتوك توك انستا الانستا انستجرام فيسبوك الفيسبوك جيت جيتهاب github الموقع النت درايف الدرايف "
                     "صفحه الصفحه صفحتي بيدج البيدج جروب الجروب بروفايل البروفايل").split())
_C_SEND = set(norm("جروب الجروب الواتس واتس واتساب تليجرام ايميل الايميل ماسنجر الناس").split())
_C_PKG = set(norm("مهاره مهارات تطبيق برنامج نسخه سكيل سكيلز اسكيل اسكيلز مكتبه باكدج باكيج package plugin بلجن اضافه اكستنشن اداه ffmpeg درايفر npm pip").split())
_C_GEN = set(norm("شغل استخدم جرب ولد اعمل ارسم صمم").split())
_C_PAID = set(norm("مدفوع المدفوع بالمدفوع بالرصيد بالكريدت بالكريدتس").split())
_C_FILLER = set(norm("لي لنا ليا شويه شوية ده دي دول بقي كمان اي ال للـ").split())
_C_NEG1 = set(norm("لا بلاش اوعي اوعى اياك متخليش ماتخليش مفيش dont don't never not no").split())
_C_WANT = set(norm("ممكن عايزك عاوزك عايزين عاوزين محتاجك محتاجين لازم ياريت حاول يلا please موافق").split())
_C_GO = set(norm("موافق موافقه اوافق ماشي تمام اوك ok يلا ابدا اعمل نفذ خلص كمل").split())
_C_LATER_W = set(norm("بكره بعدين لسه استني استنى بنفسي").split())
_C_LATER_RX = r"مش\s+(النهارده|دلوقتي)|غير\s+بعد\s+ما|لما\s+(ا|ن)?(شوف|راجع|اراجع|تفرج|اتفرج|رجع|ارجع|قول|اقول|خلص|اخلص)"
_C_CONT = set(norm("كمل اكمل كملي وكمل يلا ابدا جرب حلها صلح اصلح اصلحها ماشي اوك اوكي ok okay تمام go continue براحتك بس كده").split())
_C_YES = set(norm("موافق موافقه ايوه ايوا اه نعم نفذ نفذها اكيد اتفقنا yes yep sure").split())
_C_FREE = r"اعمل\s+(اللي|الي)\s+(انت|انتا)\s+شايفه?|زي\s+ما\s+(انت\s+)?شايف|علي\s+راحتك|براحتك"
_C_EN = {"publish": r"\b(push|publish|upload|deploy|post)\b(?!-)", "install": r"\binstall\b", "delete": r"\b(delete|remove the files)\b",
         "spend": r"\b(buy|pay|purchase|subscribe)\b", "merge": r"\bmerge\b"}
_C_EN_TRAP = {"merge": r"\s+(\S+\s+)?(layers|clips|videos|tracks|audio|للطبقات|الطبقات|طبقات|المقاطع|الكليبات)",
              "delete": r"\s+(the\s+)?(first|last|seconds|frames)"}
_C_EN_NEG = {"dont", "don't", "never", "not", "no", "بلاش", "بدون", "غير", "مش"}
_ON = norm("على")                                  # «على» is «علي» once normalised
_C_SPLIT = r"[،,.;؛!\n]+|\s+(?:بس|وبعدين|وبعدها|وبعد\s+كده)\s+"          # «؟» stays inside its clause: it marks the question


def _c_tail(x, root):
    """'ارفعه' with stem 'ارفع' -> 'ه'; None when what follows the stem is not an object or a voice-typed ending."""
    return x[len(root):] if x.startswith(root) and x[len(root):] in _C_OBJ else None


def _c_bare(w):
    return w[1:] if w[:1] in "وف" and len(w) > 3 else w


def _c_form(w, act):
    """How one word names an action: ('imp'|'pres'|'fut'|'neg', object_suffix) or None (past, passive, habitual, other).
    imp «ارفعه», pres «ترفعه/نشتري», fut «هنرفعه», neg «ماترفعش/متدمجش/متترفعش». A glued و/ف is taken off first."""
    for x in dict.fromkeys((w, _c_bare(w))):
        if x.endswith("ش") and len(x) > 3:
            core = x[:-1]
            for pre in ("ما", "م", ""):
                c = core[len(pre):] if core.startswith(pre) else ""
                if c[:1] in ("ت", "ن", "ي"):
                    for body in (c[1:], c[2:] if c[1:2] == "ت" else None):      # «متترفعش»: a passive ت after the person
                        for r in _C_ROOT[act]:
                            if body is not None and _c_tail(body, r) is not None:
                                return "neg", _c_tail(body, r)
            continue
        for s in _C_IMP[act]:
            if _c_tail(x, s) is not None:
                return "imp", _c_tail(x, s)
        for r in _C_ROOT[act]:
            if x[:1] in ("ت", "ن", "ي") and _c_tail(x[1:], r) is not None:
                return "pres", _c_tail(x[1:], r)
            if x[:1] in ("ت", "ن", "ي") and x[1:2] == "ت" and _c_tail(x[2:], r) is not None:
                return "pres", _c_tail(x[2:], r)                  # passive «تترفع»، «تتصرف»
            if x[:1] == "ه":
                if _c_tail(x[1:], r) is not None:
                    return "fut", _c_tail(x[1:], r)
                if x[1:2] in ("ت", "ن", "ي") and _c_tail(x[2:], r) is not None:
                    return "fut", _c_tail(x[2:], r)
    return None


def _c_is_neg_word(w):
    x = _c_bare(w)
    return any(_c_form(w, a) and _c_form(w, a)[0] == "neg" for a in CONSENT_AR) or (x.endswith("ش") and x[:1] == "م" and len(x) > 3)


def _c_negated(words, i, negs=()):
    b1 = words[i - 1] if i >= 1 else ""
    b2 = words[i - 2:i] if i >= 2 else []
    b3 = words[i - 3:i - 1] if i >= 3 else []
    return (b1 in _C_NEG1 or b1 == "بدون" or bool({"مش", "مفيش"} & set(words[max(0, i - 3):i])) or b2 in (["من", "غير"], ["بدون", "ما"], ["do", "not"])
            or (b1 == "ما" and b3 == ["من", "غير"]) or (b1 == "ولا" and any(j < i for j in negs)))   # «ماترفعش ولا تدمج»


def _c_next(words, i, k=2):
    out = []
    for w in words[i + 1:]:
        w = w[2:] if w.startswith("ال") and len(w) > 3 else w
        if w in _C_FILLER:
            continue
        out.append(w)
        if len(out) == k:
            break
    return out


def _c_clause(words, question, approve, forbid):
    """One clause («، بس وبعدين» split the message): verbs, nouns, transliterations and special phrases."""
    negs = [i for i, w in enumerate(words) if _c_is_neg_word(w) or w in {"مش", "لا", "مفيش", "بلاش", "بدون"}]
    text = " ".join(words)
    later = bool(set(words) & _C_LATER_W) or bool(re.search(_C_LATER_RX, text))
    go_at = [i for i, w in enumerate(words) if _c_bare(w) in _C_GO]

    def mark(act, i):
        (forbid if _c_negated(words, i, negs) else approve).add(act)

    for i, w in enumerate(words):
        nxt = _c_next(words, i)
        either_or = question and "ولا" in words[i + 1:]          # «ادمجه ولا نستنى؟» decides nothing
        x = _c_bare(w)
        for act in CONSENT_AR:
            f = _c_form(w, act)
            if f:
                kind, obj = f
                if not obj and bool(nxt) and nxt[0] in _C_TRAP[act]:
                    continue                                      # «ارفع الصوت», «متثبتش الكاميرا», «احذف اول تلات ثواني»
                if kind == "neg":
                    forbid.add(act)
                elif kind == "imp":
                    if _c_negated(words, i, negs):
                        forbid.add(act)
                    elif not either_or:
                        approve.add(act)
                elif kind == "pres":
                    want = set(words[max(0, i - 2):i]) & _C_WANT or any(j < i for j in go_at if words[j] == "موافق")
                    if _c_negated(words, i, negs):
                        forbid.add(act)
                    elif want and not either_or and not (
                            question and (x[:1] != "ت" or not set(words[max(0, i - 2):i]) & {"ممكن", "ياريت", "please"})):
                        approve.add(act)                          # «ممكن ترفعه»، «موافق تنزلها وتثبتها»
                elif kind == "fut":
                    if _c_negated(words, i, negs) or later:
                        forbid.add(act)                           # «هنرفعه بكره»، «هرفعه بنفسي» = not now, not you
            if x in _C_NOUN[act] and not (nxt and nxt[0] in _C_TRAP[act]):
                before = words[max(0, i - 3):i]
                if (_c_negated(words, i, negs) or before[-2:] == ["من", "غير"] or set(before) & {"بلاش", "بدون", "مش"} or later
                        or "لا" in words[i + 1:i + 3]):
                    forbid.add(act)                               # «من غير الرفع»، «استنى على الدمج لحد بكره»
                elif set(before) & _C_GO and (w.startswith(("ال", "وال")) or set(words[max(0, i - 2):i]) & _C_GO):
                    approve.add(act)                              # «موافق على الرفع»، «اعمل اشتراك»
            xt = x[2:] if x.startswith("ال") and len(x) > 4 else x
            if xt in _C_TRANS[act] and not (nxt and nxt[0] in _C_TRAP[act]) and not (i and words[i - 1] in {"بتاع", "بتاعه", "بتاعت"}):
                if act == "install" and xt in ("ابديت", "اپديت") and not (set(words[max(0, i - 2):i]) & {"اعمل", "عمل"} or (nxt and nxt[0] in _C_PKG)):
                    continue                                      # «ابديت» needs «اعمل» or a package after it
                if later or _c_negated(words, i, negs):
                    forbid.add(act)
                elif not question:
                    approve.add(act)                              # «اعمل بوش»، «اعملها ديليت»، «اعمل ميرج» (a question decides nothing)
        if x in ("شيل", "شيله", "شيلها", "شيلهم") and nxt and nxt[0] in _C_FILES:
            mark("delete", i)
        if _c_tail(x, "حدث") is not None and set(nxt) & _C_PKG:
            mark("install", i)                                    # «حدّث مكتبة three.js»
        if x.endswith("ش") and re.match(r"^(ما|م)?(ت|ن|ي)حدث", x) and set(words[i + 1:i + 3]) & _C_PKG:
            forbid.add("install")                                 # «متحدثش اي باكدج»
        if (_c_tail(x, "نزل") is not None or re.match(r"^(ما|م)?(ت|ن|ي)نزل\w*ش$", x)) and (
                (_ON in words[i + 1:i + 6] and set(words[i + 1:i + 7]) & _C_PLACES) or "بوست" in words[i + 1:i + 5]):
            (forbid if x.endswith("ش") or later or _c_negated(words, i, negs) else approve).add("publish")   # «نزل الريل على انستا»
        if _c_tail(x, "ابعت") is not None and (set(words[i + 1:i + 7]) & _C_SEND or set(nxt) & {"لينك", "رابط"}):
            mark("publish", i)                                    # «ابعته في جروب العيله»
        if any(_c_tail(x, s) is not None for s in ("نزل", "فعل")) and not question and {y[2:] if y.startswith("ال") else y for y in words[:i]} & (_C_PKG - {"نسخه", "تطبيق"}):
            mark("install", i)                                    # «الاكستنشن الجديده … فنزلها وفعلها»
        if x in ("لينك", "رابط") and nxt and nxt[0] in ("عام", "public"):
            mark("publish", i)
        if any(_c_tail(y, g) is not None for y in (w, x) for g in _C_GEN) and set(words[i + 1:i + 6]) & _C_PAID:   # «ولدها»: the و is the verb's own
            mark("spend", i)                                      # «ولّدها على Higgsfield بالكريدت المدفوع»
    for act, rx in _C_EN.items():
        for m in re.finditer(rx, text):
            if act in _C_EN_TRAP and re.match(_C_EN_TRAP[act], text[m.end():]):
                continue                                          # «merge للطبقات»
            before = re.findall(r"[\w']+", text[:m.start()])[-3:]
            neg = set(before) & _C_EN_NEG or any(_c_is_neg_word(b) for b in before)
            if neg or later:
                forbid.add(act)                                   # «متعملش push»، «من غير ما تعمل push»
            elif not question:
                approve.add(act)


def consent(text):
    """Which outward actions this message explicitly approves or forbids. {'approve': [...], 'forbid': [...],
    'continue_only': bool («كمل» and friends: keep working, approve nothing), 'yes_only': bool (a bare «موافق/نفذ»)}."""
    t = norm(text)
    words = re.findall(r"[\w']+", t)
    approve, forbid = set(), set()
    for part in re.split(_C_SPLIT, str(text)):
        cw = re.findall(r"[\w']+", norm(part))
        if cw:
            _c_clause(cw, bool(re.search(r"[؟?]", part)) or cw[:1] == ["هل"], approve, forbid)
    approve -= forbid                                             # «ارفعه... لا ماترفعش»: the no wins
    rest = [w for w in words if w not in CHAT_WORDS]
    yes_only = not approve and not forbid and bool(rest) and all(w in _C_YES for w in rest)
    cont_only = not approve and not forbid and not yes_only and (
        (bool(words) and not rest) or (bool(rest) and all(w in _C_CONT | _C_YES | {"و"} for w in rest))
        or (len(words) <= 8 and bool(re.search(_C_FREE, t))))
    return {"approve": sorted(approve), "forbid": sorted(forbid), "continue_only": cont_only, "yes_only": yes_only}


def consent_lines(c):
    out = []
    if c["approve"]:
        out.append("✅ موافقة صريحة في الرسالة دي على: " + "، ".join(CONSENT_AR[a] for a in c["approve"])
                   + (" (الفلوس: بالسعر بالظبط قبل التنفيذ)" if "spend" in c["approve"] else ""))
    if c["forbid"]:
        out.append("⛔ قال صراحة ماتعملش: " + "، ".join(CONSENT_AR[a] for a in c["forbid"]))
    if c["yes_only"]:
        out.append("🔒 «موافق/ايوه/نفذ» لوحدها = موافقة على الفعل اللي اتسمّى في آخر سؤال بس. لو السؤال ماسمّاش رفع أو تثبيت أو مسح أو دمج أو فلوس، يبقى ولا واحد منهم متوافق عليه.")
    elif c["continue_only"]:
        out.append("🔒 «كمل» = كمّل الشغل المحلي بس. مش موافقة على رفع أو نشر أو تثبيت أو مسح أو دمج أو فلوس: اسأل بكلمة صريحة للفعل ده.")
    return out



def _chat_rest(t):
    """(is it only chat, the words left after the small talk is taken off)."""
    w = re.findall(r"[\w؀-ۿ]+", t)
    rest = [x for x in w if x not in CHAT_WORDS]
    return bool(w) and not rest and any(x in CHAT_HEAD for x in w), rest
# tuned on the dev half of two blind sets (mind/route_eval): examples vote, the previous message helps weak or short requests
EX_W, EX_K, EX_FLOOR, EX_P = 6.0, 5, 0.3, 2.0
CTX_HI, CTX_LO, CTX_CONT, WEAK = 0.5, 0.1, 1.0, 6.0
PH_W = 3.0
PUB_SHORT, PUB_LONG = 5.0, 1.5     # v2.14: an explicit publish approval in a short message points to «ship» (dev: «ارفعه على واعطيني الرابط»)
CONF_HI, CONF_MID = (6.0, 0.35), (3.0, 0.05)       # dev half: high 92% right, mid 79%, low 67%
CONF_SURE = ((10.0, 0.2), (3.0, 0.8))   # v3.0: «مؤكدة» = the road is decided; dev half (both sets, 148 routed): 100% of the simple rule
FIX_OWN = 0.3               # v3.0: weight of a short complaint's own words when the chat has a topic
EX_EXCLUDE = set()          # example keys hidden from the memory (the evaluation hides the requests it grades)
_ex = {}
_tr = {}


def ex_key(q):
    return hashlib.sha1(" ".join(tokens(understand(q)["text"])).encode("utf-8")).hexdigest()[:12]


def _ex_terms(text):
    return [_stem(w) for w in tokens(text) if w not in QSTOP and not w.isdigit()]


def _ex_vec(terms, idf, unk):
    tf = {}
    for t in terms:
        tf[t] = tf.get(t, 0) + 1
    v = {t: (1 + math.log(c)) * idf.get(t, unk) for t, c in tf.items()}
    z = math.sqrt(sum(x * x for x in v.values())) or 1.0
    return {t: x / z for t, x in v.items()}


def examples():
    """Past requests with the road that was right for them: the bundled blind-labelled set + what this machine was taught."""
    files = (MIND / "route_examples.jsonl", MEM / "route_examples.jsonl")
    sig = tuple(f.stat().st_mtime if f.is_file() else 0 for f in files)
    if _ex.get("sig") == sig:
        return _ex
    rows = []
    for f in files:
        if not f.is_file():
            continue
        for ln in f.read_text(encoding="utf-8").splitlines():
            try:
                r = json.loads(ln)
            except Exception:
                continue
            if r.get("q") and r.get("pb"):
                r.setdefault("key", ex_key(r["q"]))
                r["_t"] = _ex_terms(r["q"])
                rows.append(r)
    df = {}
    for r in rows:
        for t in set(r["_t"]):
            df[t] = df.get(t, 0) + 1
    n = len(rows)
    idf = {t: math.log((n + 1) / (c + 0.5)) for t, c in df.items()}
    unk = math.log(n + 2) if n else 1.0
    for r in rows:
        r["_v"] = _ex_vec(r["_t"], idf, unk)
    _ex.clear()
    _ex.update(sig=sig, rows=rows, idf=idf, unk=unk)
    return _ex


def ex_near(text, k=None, floor=None):
    """[(cosine, example)] of the most similar past requests (IDF-weighted stems), best first."""
    E = examples()
    qv = _ex_vec(_ex_terms(text), E["idf"], E["unk"]) if E["rows"] else {}
    if not qv:
        return []
    fl = EX_FLOOR if floor is None else floor
    out = []
    for r in E["rows"]:
        if r["key"] in EX_EXCLUDE:
            continue
        s = min(1.0, round(sum(w * r["_v"].get(t, 0.0) for t, w in qv.items()), 6))     # a word-for-word copy is exactly 1.0, not 0.99999
        if s >= fl:
            out.append((s, r))
    out.sort(key=lambda x: -x[0])
    return out[: k or EX_K]


def translit():
    """Arabic spellings of English tool words (بلندر → blender), so either spelling meets the triggers."""
    if "m" not in _tr:
        m = {}
        for k, v in (jload(MIND / "translit.json", {}) or {}).items():
            if not k.startswith("_"):
                kt, vt = tokens(k), tokens(v)
                if kt and vt:
                    m[kt[0]] = vt
        _tr["m"] = m
    return _tr["m"]


def _pb_scores(q, pbs):
    """Raw score per playbook id for one message, and its kind: url | greet | cont | text."""
    t = norm(q).strip()
    bare = re.sub(r"[a-z]:\\\S*|https?://\S+|\(مرفقات:[^)]*\)", " ", t)
    if len(tokens(bare)) == 0 and re.search(r"https?://", t):     # a bare link: the site says what to do with it
        pid = next((p for rx, p in URL_ONLY if re.search(rx, t)), None)
        return ({pid: 4.0} if pid else {}), "url"
    chat, rest = _chat_rest(t)
    if re.match(GREET_RX, t) or re.search(NONE_EXTRA, t) or chat:
        return {}, "greet"
    if re.match(CONT_RX, t) or len(tokens(bare)) == 0 or (0 < len(rest) <= 2 and re.match(CONT_RX, " ".join(rest))):   # «كمل», «تمام يا تنين كمل», or only a path / a wrapper
        return {}, "cont"
    fix = len(tokens(bare)) <= FIX_MAX and re.search(FIX_RX, t)
    tr = translit()
    qp = [w for w in tokens(q) if w not in QSTOP]
    idf = _route_idf(pbs)
    out = {}
    pub = "publish" in consent(t)["approve"]
    for p in pbs:
        tot = 0.0
        for w in qp:
            best = 0.0
            for v in [w] + tr.get(w, []):
                for k in p["_tok"]:
                    m = _tmatch(v, k)
                    if m:
                        best = max(best, m * idf.get(k, 1.0))
            tot += best
        for rx, pid, bonus in INTENT:
            if pid == p["id"] and re.search(rx, t):
                tot += bonus
        if pub and p["id"] == "ship":                 # v2.14: «ارفعه على …» is a release; «ارفع الصوت» is not (the consent gate tells them apart)
            tot += PUB_SHORT if len(qp) <= 7 else PUB_LONG
        tot += PH_W * sum(1 for ph in p.get("_ph", ()) if ph in t)
        if tot > 0:
            out[p["id"]] = tot
    for s, r in ex_near(t):
        out[r["pb"]] = out.get(r["pb"], 0.0) + EX_W * s ** EX_P      # EX_P > 1: a near-copy counts, a loose likeness barely does
    return out, ("fix" if fix else "text")


def route(q, limit=5, prev=None):
    """(playbooks, powers) ranked for one request. prev = the owner's previous message: it carries short follow-ups
    («كمل», «حلها», «فين الملف») and tips weak requests, and barely moves a clear one."""
    oc = outcomes()
    pbs = playbooks()
    s, kind = _pb_scores(q, pbs)
    if prev and kind in ("cont", "text", "fix"):
        sp = dict(prev) if isinstance(prev, dict) else _pb_scores(prev, pbs)[0]     # a dict = the decayed topic of the chat so far
        top = max((v for k, v in s.items() if k != "none"), default=0.0)
        if kind == "fix" and sp:            # v3.0: a short complaint follows the chat; its own words only break ties
            s = {k: FIX_OWN * v for k, v in s.items()}
        lam = CTX_CONT if kind in ("cont", "fix") else (CTX_HI if top < WEAK else CTX_LO)
        for k, v in sp.items():
            if k not in NO_CARRY:
                s[k] = s.get(k, 0.0) + lam * v
    nonev = s.pop("none", 0.0)
    pb = sorted([(s[p["id"]] * (0.7 + 0.6 * trust(p["id"], oc)), p) for p in pbs if s.get(p["id"], 0) > 0], key=lambda x: -x[0])
    if pb and nonev >= pb[0][0]:                    # the most similar past messages were plain chat
        pb = []
    pb = pb[:limit]
    qt = tokens(q)                      # powers keep the plain match below
    pw = [(score(qt, p["_tok"]), p) for p in powers()]
    pw = sorted([x for x in pw if x[0] > 0], key=lambda x: (-x[0], COST_RANK.get(x[1].get("cost"), 9)))[:limit + 2]
    return pb, pw


def confidence(pb, kind=None):
    """sure | high | mid | low | none, from the top score and its lead over the runner-up (calibrated on the dev half).
    kind = the message kind from _pb_scores: a follow-up («كمل», «لا يعمل») borrows its road from the chat, so it is never «sure»."""
    if not pb or pb[0][0] < 2:
        return "none"
    s1, s2 = pb[0][0], (pb[1][0] if len(pb) > 1 else 0.0)
    gap = (s1 - s2) / s1
    if kind not in ("cont", "fix") and any(s1 >= a and gap >= b for a, b in CONF_SURE):
        return "sure"
    if s1 >= CONF_HI[0] and gap >= CONF_HI[1]:
        return "high"
    if s1 >= CONF_MID[0] and gap >= CONF_MID[1]:
        return "mid"
    return "low"


CONF_AR = {"sure": "مؤكدة", "high": "عالية", "mid": "متوسطة", "low": "ضعيفة", "none": "مفيش"}
# the topic of the chat so far: every message adds its scores, older ones fade (0.7 per message). Dev half: 73% → 83% acceptable.
TOPIC_DECAY, TOPIC_CAP, TOPIC_TTL = 0.7, 20.0, 45 * 60


def topic_update(topic, s):
    s = {k: v for k, v in (s or {}).items() if k not in NO_CARRY and v > 0}
    m = max(s.values(), default=0.0)
    if m > TOPIC_CAP:
        s = {k: v * TOPIC_CAP / m for k, v in s.items()}
    t = {k: TOPIC_DECAY * (topic or {}).get(k, 0.0) + s.get(k, 0.0) for k in set(topic or {}) | set(s)}
    return {k: round(v, 3) for k, v in t.items() if v > 0.05}


def last_turn(max_age=TOPIC_TTL):
    """What brief() saw last on this machine (the chat topic), or None when it is older than max_age seconds."""
    lt = jload(MEM / "last_turn.json", None)
    if not isinstance(lt, dict) or datetime.datetime.now().timestamp() - lt.get("t", 0) > max_age:
        return None
    return lt


def _topic_for(text, lt):
    """The topic before this message: a re-brief of the same message reuses the topic it had."""
    if not lt:
        return None
    return lt.get("before") if lt.get("q") == text else lt.get("topic")


def add_example(q, pid, src):
    """Remember «a request like this one → this playbook» on this machine (MEM/route_examples.jsonl)."""
    q = " ".join(understand(q)["text"].split())[:500]
    if not [w for w in tokens(q) if w not in QSTOP]:
        return None
    k = ex_key(q)
    if any(r["key"] == k and r["pb"] == pid for r in examples()["rows"]):
        return None
    row = {"q": q, "pb": pid, "src": src, "key": k, "date": datetime.date.today().isoformat()}
    with mem_file("route_examples.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


def here_steps(p, where):
    """A step may start with [pc] or [cloud]; unmarked steps apply everywhere."""
    out = []
    for s in p.get("steps", []):
        m = re.match(r"\[(pc|cloud)\]\s*", s)
        if m and ((m.group(1) == "pc") != is_pc(where)):
            continue
        out.append(s[m.end():] if m else s)
    return out


def plan(q, as_json=False, prev=None):
    where = place()
    u = understand(q)
    q = u["text"]
    before = _pb_scores(understand(prev)["text"], playbooks())[0] if prev else _topic_for(q, last_turn())     # read-only: plan never moves the topic
    pb, pw = route(q, prev=before or None)
    conf = confidence(pb, _pb_scores(q, playbooks())[1])
    ls = recall(q, domain=pb[0][1].get("domain") if pb else None)
    if as_json:
        print(json.dumps({"place": where, "playbooks": [{k: v for k, v in p.items() if not k.startswith("_")} | {"score": round(s, 2)} for s, p in pb],
                          "powers": [{"id": p["id"], "ar": p.get("ar"), "cost": p.get("cost"), "score": s} for s, p in pw],
                          "lessons": ls, "confidence": conf, "used_context": bool(before), "consent": consent(q),
                          "thinking": thinking_info(q)}, ensure_ascii=False, indent=1))
        return
    P = print
    P(f"🐉 التنين الذهبي v{VERSION} · المكان: {where}")
    if u["changed"]:
        P("🔤 الطلب بعد فك الكتابة: " + q[:200] + ("  (الكيبورد كان إنجليزي)" if u["layout_fixed"] else "") + ("  · " + "، ".join(u["words_fixed"]) if u["words_fixed"] else ""))
    for line in consent_lines(consent(q)):         # v2.14
        P(line)
    P("\n① أول رد (قبل أي أداة):")
    P(f"   فهمت إنك عايز: «{' '.join(q.split())[:160]}» ← اكتبها بكلامك بعد فك غلطات الإملاء، وقول خمّنت إيه.")
    P("   هعمل: 3–5 نقط + الناتج فين + ⏱ التقدير. سؤال واحد بس لو الطلب ليه معنيين.")
    try:                                   # v3.4: depth L0-L3 + the thinking tools for this request (rd_fusion.py)
        fm = fusion_mod()
        if fm.available():
            P("")
            for line in fm.thinking_lines(rd_self(), q):
                P(line)
    except Exception as e:
        P(f"\n🧠 (سلّم التفكير ماطلعش: {type(e).__name__}; جرّب rd.py fuse brief \"…\")")
    if not pb:
        P("\n② مفيش playbook مطابق. استخدم: rd.py map ، أو المحرك: rd.py x find \"<الطلب>\" ، وبعد ما تخلص: rd.py learn …")
    for i, (s, p) in enumerate(pb[:2]):
        P(f"\n{'②' if i == 0 else '②ب (بديل)'} الطريق: {p['ar']}  [{p['id']}]  نجاح سابق {trust(p['id'], outcomes()):.0%}"
          + (f" · ثقة الاختيار: {CONF_AR[conf]}" + (" (بالسياق)" if before else "") if i == 0 else ""))
        if i:
            continue
        for n, st in enumerate(here_steps(p, where), 1):
            P(f"   {n}. {st}")
        if p.get("skills"):
            P("   مهارات تتحمّل الأول: " + "، ".join(p["skills"]))
        if p.get("ask"):
            P("   🔒 محتاج «أيوه» صريحة: " + " · ".join(p["ask"]))
        if p.get("gates"):
            P("   ✅ مايتسلّمش غير لما: " + " · ".join(p["gates"]))
        if p.get("pitfalls"):
            P("   ⚠ فخاخ معروفة: " + " · ".join(p["pitfalls"]))
    if pw:
        P("\n③ القدرات والاتصالات الأقرب:")
        for s, p in pw:
            how = p.get("how", "")
            if p.get("where") == "pc" and not is_pc(where):
                how = "هنا: " + p.get("cloud_alt", "مش متاح في السحابة")
            P(f"   • {COST.get(p.get('cost'), '')} {p.get('ar')} [{p['id']}] — {how[:230]}")
    ih = inst_find(q, 4)
    if ih:
        P("\n③ب مهارات متثبتة على الجهاز تفيد (حمّلها بأداة Skill أو اقرا SKILL.md):")
        for r in ih:
            P("   • " + inst_line(r))
    lb = lib_find(q, 4)
    if lb:
        P("\n③ج من مكتبة المهارات (مش متثبتة؛ اقرا SKILL.md بـ Read واستخدمها كمرجع):")
        for r in lb:
            P("   • " + lib_line(r))
    if ls:
        P("\n④ دروس اتعلمناها في حاجة شبه دي:")
        for l in ls:
            P(f"   • ({l.get('domain')}) {l['text'][:260]}")
            bump(l["id"])
    hits = chat_hits(q, 2)
    if hits:
        P("\n④ب من ذاكرة المحادثات (اتعمل قبل كده؟ اتقرر إيه؟ — التفاصيل: rd.py chats):")
        for h in hits:
            P(f"   • {h['title'][:70]} ({h['date'][:10]}, {h['id']})")
            for ln in h["lines"][:2]:
                P(f"       {ln[:220]}")
    P("\n⚑ لو هتكتب في مجلد مشترك أو مهارة متثبتة: rd.py guard PATH الأول (جلستين على نفس المجلد حصلت 5 مرات).")
    P("\n⑤ بعد التسليم: rd.py outcome " + (pb[0][1]["id"] if pb else "ID") + " ok|fail --note \"…\"  ، وأي تصحيح من صاحب الشغل: rd.py learn \"…\"")


def chats_mod():
    """scripts/rd_chats.py (memory of past conversations + guard). Imported by path so python -I works too."""
    here = str(Path(__file__).resolve().parent)
    if here not in sys.path:
        sys.path.insert(0, here)
    import rd_chats
    return rd_chats


def chat_hits(q, limit=2):
    try:
        return chats_mod().search(q, limit=limit, per=2, min_terms=2)
    except Exception:
        return []


def fusion_mod():
    """scripts/rd_fusion.py (v3.4): the Golden Dragon's fusion brain, run in this process. Imported by path like rd_chats."""
    here = str(Path(__file__).resolve().parent)
    if here not in sys.path:
        sys.path.insert(0, here)
    import rd_fusion
    return rd_fusion


def rd_self():
    """What rd_fusion needs from this file. A plain namespace, so it works when rd.py is imported under another name."""
    return types.SimpleNamespace(understand=understand, route=route, VERSION=VERSION)


def thinking_info(q):
    """{'depth': 'L2', 'why': …, 'tools': [ids]} for plan --json; {} when the fusion brain is not in this copy."""
    try:
        fm = fusion_mod()
        if not fm.available():
            return {}
        lvl, why, tools, _ = fm.depth_and_tools(rd_self(), q)
        return {"depth": lvl, "why": why, "tools": [t["id"] for t in tools]}
    except Exception as e:
        return {"error": f"{type(e).__name__}: {str(e)[:120]}"}


def bump(lid):
    try:
        with mem_file("hits.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps({"id": lid, "t": datetime.datetime.now().isoformat(timespec="seconds")}) + "\n")
    except OSError:
        pass


# ------------------------------------------------------------------ skill library (200 famous Claude skills, not auto-loaded)
LIBRARY = ROOT / "library"
_lib = {}


def library():
    if "rows" not in _lib:
        d = jload(LIBRARY / "index.json", {}) or {}
        rows = d.get("skills", [])
        for r in rows:
            r["_tok"] = set(tokens(r["name"].replace("-", " ") + " " + r.get("title", "") + " " + r["description"]))
        _lib["rows"] = rows
    return _lib["rows"]


LIB_AR = {"مونتاج": "video edit editing montage cut", "فيديو": "video", "ترجمه": "subtitle caption translate", "صوت": "audio voice sound", "موشن": "motion animation", "انيميشن": "animation",
          "تصميم": "design ui", "واجهه": "ui frontend interface", "موقع": "website web frontend", "بلندر": "blender 3d", "تسويق": "marketing", "انستجرام": "instagram", "يوتيوب": "youtube",
          "لينكدان": "linkedin", "تداول": "trading stock market", "اسهم": "stock equity trading", "برومبت": "prompt", "كتاب": "book", "اختبار": "test testing", "مراجعه": "review audit",
          "امان": "security audit", "قاعده": "database sql", "بيانات": "data database", "سيارات": "automotive vehicle", "سياره": "automotive vehicle", "اندرويد": "android", "متصفح": "browser",
          "خطه": "plan planning", "تخطيط": "plan planning", "كود": "code coding", "برمجه": "code programming", "مستند": "document docs", "عرض": "presentation slides", "رسم": "draw drawing sketch",
          "بيكسل": "pixel", "العاب": "game sprite", "لعبه": "game sprite", "شركه": "business startup founder", "مشروع": "business startup project", "كتابه": "writing copy", "محتوى": "content", "هندسه": "engineering reverse",
          "ظل": "shadow silhouette", "ظلال": "shadow silhouette", "دمي": "puppet puppetry", "دميه": "puppet puppetry", "عرائس": "puppet marionette puppetry",
          "مسافه": "distance measure", "مسافات": "distance measure", "رياضه": "math geometry", "رياضيه": "math geometry", "نسب": "proportion anthropometry",
          "زاويه": "angle geometry", "منظور": "perspective camera", "فيزيا": "physics", "فيزياء": "physics", "قياس": "measure", "روتوسكوب": "rotoscope trace", "شخصيه": "character", "كرتون": "cartoon character", "تتبع": "tracking",
          "حلبه": "arena compete tournament", "يتنافسوا": "arena compete", "يتعاركوا": "arena compete fight", "موبايل": "phone android iphone control", "تليفون": "phone android iphone", "فيجما": "figma design", "سيو": "seo keyword search", "كلمات مفتاحيه": "keyword research seo",
          "اسئله": "grill interview questions", "اسالني": "grill-me interview", "موشن": "motion animation graphics", "انيميشن": "animation motion", "معماريه": "architecture diagram codebase",
          "شرح": "explain teach html", "تسليم": "handoff summary", "متصفح": "playwright browser test",
          "توثيق": "documentation docs library api", "مكتبات": "library documentation api", "ثغرات": "security vulnerabilities", "ثغره": "security vulnerability",
          "تبسيط": "simplify simplification lazy", "مراجعه كود": "code review", "اختبارات": "test testing tdd", "باج": "debugging bug error", "واجهات": "ui ux design interface",
          "جراف": "graph knowledge codebase", "خريطه": "graph map codebase", "مهاره": "skill skills find", "مهارات": "skills find install", "مواصفات": "spec specification",
          "كريتا": "krita paint layered", "طبقات": "layers layered", "طبقه": "layer layered", "لوحه": "painting illustration", "تلوين": "paint painting"}


def lib_find(q, limit=8, hide_installed=True):
    """Arabic words map to the English the skill descriptions are written in."""
    qt = tokens(q)
    extra = []
    for t in qt:
        for k, v in LIB_AR.items():
            if match(t, norm(k)):
                extra += v.split()
    qt = qt + extra
    here = {r["dir"] for r in installed() if r["mode"] != "catalog"} if hide_installed else set()   # v2.10: never offer what this machine already has
    out = [(score(qt, r["_tok"]) + min(r["stars"], 50000) / 50000, r) for r in library() if r["name"] not in here]
    return [r for sc, r in sorted(out, key=lambda x: -x[0]) if sc >= 2][:limit]


# ------------------------------------------------------------------ top 500 GitHub repositories (index only: nothing is cloned)
_top = {}
WIN_AR = {"yes": "يشتغل على ويندوز", "docker": "محتاج Docker", "wsl": "محتاج WSL", "no": "مش لويندوز", "n/a": "مرجع للقراية"}


def repos_top():
    if "rows" not in _top:
        d = jload(MIND / "intel" / "top500.json", {}) or {}
        rows = d.get("repos", [])
        for r in rows:
            r["_tok"] = set(tokens(r["repo"].replace("/", " ").replace("-", " ") + " " + r.get("what", "") + " " + r.get("use_when", "") + " " + r.get("category", "").replace("-", " ")
                                   + " " + " ".join(r.get("keywords_en", [])) + " " + " ".join(r.get("keywords_ar", []))))
        _top["rows"] = rows
    return _top["rows"]


def repos_find(q, limit=8):
    qt = tokens(q)
    extra = []
    for t in qt:
        for k, v in LIB_AR.items():
            if match(t, norm(k)):
                extra += v.split()
    qt = qt + extra
    out = [(score(qt, r["_tok"]) + r.get("value_for_claude", 0) * 0.15 + min(r["stars"], 300000) / 600000, r) for r in repos_top()]
    return [r for sc, r in sorted(out, key=lambda x: -x[0]) if sc >= 2][:limit]


def repo_line(r):
    w = WIN_AR.get(str(r.get("windows_ok")), str(r.get("windows_ok")))
    inst = r.get("install_windows") or ""
    return (f"#{r['rank']} {r['repo']}  ★{r['stars']:,}  ({r.get('category')}، {r.get('license') or 'رخصة مش معروفة'}، {w})\n     {r.get('what', '')[:200]}\n     إمتى: {r.get('use_when', '')[:170]}"
            + (f"\n     التثبيت (بموافقة): {inst[:150]}" if inst and inst != "n/a" else "") + f"\n     {r.get('url', '')}")


def lib_line(r):
    flag = (" · ⚠ راجع قبل تشغيل سكربتاته: " + "، ".join(r["review"])) if r.get("review") else ""
    return f"{r['name']}  ★{r['stars']:,}  ({r['repo']}، {r['license']}){flag}\n     {r['description'][:210]}\n     اقرا: {LIBRARY / r['name'] / 'SKILL.md'}"


def lib_install(name, yes=False):
    r = next((x for x in library() if x["name"] == name), None)
    if not r:
        raise SystemExit(f"مفيش مهارة بالاسم ده في المكتبة: {name}")
    dst = Path.home() / ".claude" / "skills" / name
    if dst.exists():
        raise SystemExit(f"موجودة قبل كده: {dst}")
    if not yes:
        print(f"هيتنسخ: {LIBRARY / name}  →  {dst}\nالمصدر: {r['repo']} (★{r['stars']:,}، {r['license']})" + (f"\n⚠ فيها سكربتات بأنماط: {', '.join(r['review'])} — اقراها الأول." if r.get("review") else "")
              + "\nده تثبيت: محتاج موافقة صاحب الشغل، وبعدها نفس الأمر بـ --yes")
        return None
    shutil.copytree(LIBRARY / name, dst)
    (dst / ".blackdragon.json").write_text(json.dumps({"made_by": "black-dragon-app", "source": f"https://github.com/{r['repo']} ({r['license']})", "mode": "library",
                                                       "created": datetime.datetime.now().isoformat(timespec="seconds")}), encoding="utf-8")
    return dst


# ------------------------------------------------------------------ installed skills (every SKILL.md under ~/.claude/skills)
SKILLS_HOME = Path(os.environ.get("CLAUDE_SKILLS_HOME") or Path.home() / ".claude" / "skills")
_inst = {}


def _frontmatter(path):
    """name and description from a SKILL.md's YAML front matter (plain, quoted, or a folded > / | block)."""
    try:
        txt = Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}
    if not txt.startswith("---"):
        return {}
    end = txt.find("\n---", 3)
    lines = txt[3:end if end > 0 else 4000].splitlines()
    out, i = {}, 0
    while i < len(lines):
        m = re.match(r"^(name|description):\s*(.*)$", lines[i])
        if m:
            key, val = m.group(1), m.group(2).strip()
            if val in (">", "|", ">-", "|-", ""):
                buf = []
                while i + 1 < len(lines) and (lines[i + 1].startswith((" ", "\t")) or not lines[i + 1].strip()):
                    i += 1
                    buf.append(lines[i].strip())
                val = " ".join(b for b in buf if b)
            out[key] = val.strip().strip('"').strip("'")
        i += 1
    return out


def installed():
    """Every installed skill: name, description, mode ("own", or "library" when the app installed it from the library),
    path. Cached in ~/.red-dragon/installed_index.json on the folder's mtime and count, so a chat does not re-read 500 files."""
    try:
        st = SKILLS_HOME.stat()
        dirs = sorted(d.name for d in SKILLS_HOME.iterdir() if (d / "SKILL.md").is_file())
    except OSError:
        dirs = []
    if not dirs:            # v2.10: claude.ai / cloud / a fresh PC -> the owner's laptop skills from the shipped snapshot
        return catalog()
    sig = f"{st.st_mtime_ns}:{len(dirs)}"
    if _inst.get("sig") == sig:
        return _inst["rows"]
    cache = MEM / "installed_index.json"
    d = jload(cache, {}) or {}
    if d.get("sig") == sig:
        rows = d["rows"]
    else:
        rows = []
        for name in dirs:
            fm = _frontmatter(SKILLS_HOME / name / "SKILL.md")
            mk = jload(SKILLS_HOME / name / ".blackdragon.json", {}) or {}
            rows.append({"name": fm.get("name") or name, "dir": name, "description": (fm.get("description") or "")[:700],
                         "mode": mk.get("mode", "own"), "path": str(SKILLS_HOME / name / "SKILL.md")})
        try:
            MEM.mkdir(parents=True, exist_ok=True)
            cache.write_text(json.dumps({"sig": sig, "rows": rows}, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass
    for r in rows:
        r["_tok"] = set(tokens(r["name"].replace("-", " ").replace(":", " ") + " " + r["description"]))
    _inst.update(sig=sig, rows=rows)
    return rows


CATALOG = MIND / "installed_catalog.json"


def catalog():
    """Snapshot of every skill on the owner's laptop (name, description, kind) — no paths, no private files.
    Used when this machine has no ~/.claude/skills, so a cloud chat still knows what the laptop can do."""
    if "cat" not in _inst:
        rows = (jload(CATALOG, {}) or {}).get("skills", [])
        for r in rows:
            r["mode"] = "catalog"
            r["path"] = f"~/.claude/skills/{r.get('dir', r['name'])}/SKILL.md (على لابتوب صاحب الشغل)"
            r["_tok"] = set(tokens(r["name"].replace("-", " ").replace(":", " ") + " " + r.get("description", "")))
        _inst["cat"] = rows
    return _inst["cat"]


def snapshot_installed(dst=CATALOG):
    """Write the shipped catalog from this machine's installed skills (descriptions trimmed, no absolute paths)."""
    rows = installed()
    if not rows or rows is _inst.get("cat"):
        raise SystemExit(f"مفيش مهارات متثبتة هنا ({SKILLS_HOME}) — الـ snapshot بيتعمل من لابتوب صاحب الشغل.")
    home = re.compile(r"[A-Za-z]:[\\/]+Users[\\/]+[^\\/\s]+|/(?:c/)?(?:Users|home)/[^/\s]+", re.I)   # never ship a user folder name
    out = [{"name": r["name"], "dir": r["dir"], "kind": r["mode"], "description": home.sub("~", r["description"])[:400]} for r in rows]
    Path(dst).write_text(json.dumps({"kind": "red-dragon/installed-catalog", "date": datetime.date.today().isoformat(), "count": len(out),
                                     "_doc_ar": "كل المهارات المتثبتة على لابتوب صاحب الشغل (اسم ووصف بس). rd.py بيستخدمها لما الجهاز اللي شغال عليه مافيهوش ~/.claude/skills. التحديث: rd.py skills snapshot.",
                                     "skills": out}, ensure_ascii=False, indent=0), encoding="utf-8", newline="\n")   # LF on Windows too: no line-ending churn in git
    return len(out)


def inst_find(q, limit=8, mode=None):
    """Installed skills for a request (Arabic words widened to the English the descriptions use); own skills win ties."""
    qt = tokens(q)
    extra = []
    for t in qt:
        for k, v in LIB_AR.items():
            if match(t, norm(k)):
                extra += v.split()
    qt = qt + extra
    out = [(score(qt, r["_tok"]) + (0.5 if r["mode"] == "own" else 0.0), r) for r in installed() if mode in (None, r["mode"])]
    return [r for sc, r in sorted(out, key=lambda x: -x[0]) if sc >= 2.5][:limit]


def inst_line(r):
    tag = {"own": "مهارتك", "catalog": "على لابتوب صاحب الشغل، مش هنا", "library": "من المكتبة، متثبتة"}.get(r["mode"], "متثبتة")
    return f"{r['name']}  ({tag})\n     {r['description'][:200]}\n     {r['path']}"


# ------------------------------------------------------------------ understand: what did the owner actually type
# Arabic typed while the keyboard was on English (Arabic 101 layout). Seen 9 times in the owner's chats.
LAYOUT = dict(zip("qwertyuiop[]asdfghjkl;'zxcvnm,./`", "ضصثقفغعهخحجدشسيبلاتنمكطئءؤرىةوزظذ"))
LAYOUT["b"] = "لا"
DICTATION = jload(MIND / "dictation.json", {}) or {}


_TAG = re.compile(r"^\[[A-Z][A-Z0-9_\-]{2,}\]$")


def _garbled(run):
    """A run of Latin tokens that is not English: keys like ; ' , inside words, or almost no vowels."""
    toks = [t for t in run.split() if not _TAG.match(t)]    # v2.8: [ERROR] / [OPTIONS] are tags, not «ج…د» typed on the wrong keyboard
    run = " ".join(toks)
    letters = [c for c in run.lower() if c.isalpha()]
    if len(letters) < 5 or re.search(r"https?://|[\\/]\w+[\\/]|\.\w{2,4}\b|--\w|^\s*(pip|npm|npx|git|cd|python|curl)\b", run):
        return False
    eng = [t for t in toks if t.lower().strip(".,!?") in ENGLISH or _CONTRACTION.match(t.strip(".,!?"))]   # v2.14: don't / it's
    odd = sum(1 for t in toks if t not in eng and re.search(r"[A-Za-z][;',\[\]`][A-Za-z]|[;'\[\]`]$|^[;',\[\]`]", t))
    vowels = sum(1 for c in letters if c in "aeiou") / len(letters)
    known = len(eng)
    if known >= max(1, len(toks) // 2):
        return False
    return odd >= max(1, len(toks) // 4) or (vowels < 0.24 and len(toks) >= 2)


ENGLISH = set("the a an and or to of in on for with is are it this that you me my i we be do not no yes can will have has from at by as if so but ok okay please make create build run test install update fix "
              "open file files app video image skill skills dragon black white red claude code github repo link download upload render blender chrome windows "
              # v2.14: the commands the owner types in English (an English request must never be «decoded» into Arabic letters)
              "push pull merge commit branch main delete remove publish deploy buy pay stop wait cancel continue go ahead now yet later "
              "done good great thanks thank sure yep nope dont cant wont all just them now".split())
_CONTRACTION = re.compile(r"^(don|can|won|isn|aren|wasn|weren|doesn|didn|hasn|haven|hadn|shouldn|wouldn|couldn|mustn|it|that|there|what|"
                          r"let|he|she|i|you|we|they|who)'(t|s|re|ve|ll|d|m)$", re.I)


# ------------------------------------------------------------------ v2.8: the fixed text the app wraps around a request
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


def fix_layout(text):
    """Decode every garbled Latin run; leave real English, paths, links and commands alone."""
    changed = False

    def rep(m):
        nonlocal changed
        run = m.group(0)
        if not _garbled(run):
            return run
        changed = True
        return "".join(LAYOUT.get(c, c) for c in run.lower())
    out = re.sub(r"[A-Za-z;',\.\[\]`/]+(?:\s+[A-Za-z;',\.\[\]`/]+)*", rep, text)
    return out, changed


def fix_dictation(text):
    """Known voice-typing slips -> the intended word (mind/dictation.json)."""
    hits = []
    for bad, good in DICTATION.items():
        if re.search(r"(?<![؀-ۿ])" + re.escape(bad) + r"(?![؀-ۿ])", text):
            text = re.sub(r"(?<![؀-ۿ])" + re.escape(bad) + r"(?![؀-ۿ])", good, text)
            hits.append(f"{bad}→{good}")
    return text, hits


def understand(text):
    clean, wraps = strip_wrappers(str(text))          # v2.8: agents-team / work-folder / skills prefixes / error tails are not the request
    t1, lay = fix_layout(" ".join(clean.split()))
    t2, hits = fix_dictation(t1)
    return {"text": t2, "layout_fixed": lay, "words_fixed": hits, "changed": lay or bool(hits), "wrappers": wraps}


BRIEF_MIN_HITS = 2      # v2.8.1: a repo / library skill joins the brief only when 2+ different words of the request match it


def _hits(q, bag):
    """How many different words of the request match a row. An Arabic word counts once, however many English words it widens to."""
    n = 0
    for t in {w for w in tokens(q) if w not in QSTOP}:
        vs = [t] + [x for k, v in LIB_AR.items() if match(t, norm(k)) for x in v.split()]
        if any(match(x, k) for x in vs for k in bag):
            n += 1
    return n


def _named(q, name):
    """The request names this repo / skill itself («استخدم REA», «playwright»): then one word is enough."""
    head = re.split(r"[-_.]", name.lower().split("/")[-1])[0]
    return len(head) >= 3 and head in set(tokens(q))


def _relevant(q, r, name):
    return _named(q, name) or _hits(q, r["_tok"]) >= BRIEF_MIN_HITS


def _clip(s, n):
    """Cut at the last whole word before n characters (never in the middle of a word)."""
    s = " ".join(str(s).split())
    if len(s) <= n:
        return s
    cut = s[:n]
    sp = cut.rfind(" ")
    return (cut[:sp] if sp > n * 0.6 else cut).rstrip(" ،,.:;←-") + "…"


def understand_guard(kind, conf, pb, lt, text):
    """v3.0 (golden): how much to trust the road, said plainly, so the FIRST reply understands right.
    Dev half: «مؤكدة» was right every time; «عالية» ~91% on the owner's real messages; under that it is a guess."""
    last = _clip((lt or {}).get("task_q", ""), 160)
    if kind == "cont":
        return [f"🎯 فهم: رسالة متابعة قصيرة ← كمّل نفس الشغل اللي قبلها" + (f" («{last}»)" if last else "") + "، ماتبدأش طريق جديد."]
    if kind == "fix":
        return [f"🎯 فهم: شكوى على الشغل اللي اتعمل" + (f" («{last}»)" if last else "") + " ← اعمل reproduce للمشكلة دي وصلّحها في نفس الحاجة، "
                "ماتفتحش طريق جديد من كلمات الرسالة. لو مش واضح «أنهي حاجة مش شغالة»، اسأل سؤال واحد."]
    if kind == "greet" or not pb or pb[0][0] < 2:
        return [] if kind == "greet" else ["🎯 فهم: الطلب مالوش طريق معروف ← افهمه من كلامه هو، واكتب «فهمت إنك عايز:» قبل أي أداة."]
    alts = [p["id"] for s, p in pb[1:3] if s >= 2]
    if conf == "sure":
        return ["🎯 فهم: الطريق محسوم (ثقة مؤكدة) ← نفّذ."]
    if conf == "high":
        return ["🎯 فهم: الطريق غالبًا صح ← في «فهمت إنك عايز:» اكتب التسليم بالظبط، ولو الطلب بيقول حاجة غير الطريق امشي ورا الطلب."]
    return [f"🎯 فهم: مش متأكد (ثقة {CONF_AR[conf]}) ← الطرق القريبة: {pb[0][1]['id']}" + (", " + ", ".join(alts) if alts else "")
            + ". اقرا الطلب كلمة كلمة ومعاه آخر طلب" + (f" («{last}»)" if last else "") + ". لو قراءتين مختلفتين بيغيّروا التسليم: سؤال واحد قبل أي أداة تقيلة."]


def brief(text, limit=1400, prev=None):
    """A short mission brief for a host app to put in front of the model. Reads the mind files; writes only MEM/last_turn.json
    (the chat topic, so «كمل» / «حلها» / «فين الملف» are read in the light of what came before). prev: str or topic dict."""
    u = understand(text)
    lt = last_turn() if prev is None else None
    before = prev if isinstance(prev, dict) else (_pb_scores(prev, playbooks())[0] if prev else _topic_for(u["text"], lt))
    pb, pw = route(u["text"], prev=before or None)
    s_now, kind = _pb_scores(u["text"], playbooks())
    conf = confidence(pb, kind)
    try:                                            # best effort: a read-only disk never stops the brief
        qp = [w for w in tokens(u["text"]) if w not in QSTOP]
        task_q = u["text"] if kind == "text" and len(qp) >= 4 and conf != "none" else (lt or {}).get("task_q", "")
        mem_file("last_turn.json").write_text(json.dumps({"t": datetime.datetime.now().timestamp(), "q": u["text"][:1500], "before": before or {},
                                                           "topic": topic_update(before, s_now), "pb": pb[0][1]["id"] if pb and pb[0][0] >= 2 else None,
                                                           "task_q": task_q[:1500]}, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass
    where = place()
    L = []
    cons = consent(u["text"])
    if u["changed"]:
        L.append("الطلب بعد فك الكتابة: «" + u["text"][:300] + "»" + (" (كان مكتوب والكيبورد إنجليزي)" if u["layout_fixed"] else "") + (" · تصحيح: " + "، ".join(u["words_fixed"]) if u["words_fixed"] else ""))
    L += [] if kind == "greet" else consent_lines(cons)     # v2.14: what this message really approves (read before the road)
    if pb and pb[0][0] >= 2:
        p = pb[0][1]
        alt = pb[1][1] if len(pb) > 1 and conf in ("low", "mid") and pb[1][0] >= 2 else None
        L.append(f"الطريق المقترح: {p['ar']} [{p['id']}] · ثقة {CONF_AR[conf]}" + (f" · بديل قريب: {alt['ar']} [{alt['id']}]" if alt else ""))
        L += [f" {n}. {s}" for n, s in enumerate(here_steps(p, where)[:6], 1)]
        if p.get("skills"):
            L.append(" مهارات: " + "، ".join(p["skills"][:5]))
        if p.get("ask"):
            L.append(" 🔒 بموافقة: " + " · ".join(p["ask"]))
        if p.get("gates"):
            L.append(" ✅ قبل التسليم: " + " · ".join(p["gates"][:4]))
    L += understand_guard(kind, conf, pb, lt, u["text"])
    chat = kind in ("greet", "cont")    # v2.8.1: «ازيك يا تنين» / «شكرا» / «كمل» get no repos, skills or lessons searched from their own words
    tr = [] if chat else [r for r in repos_find(u["text"], 6) if _relevant(u["text"], r, r["repo"])][:2]
    if tr:
        L.append("من أشهر 500 مستودع GitHub (فهرس بس، مفيش حاجة متنزّلة): " + " ⏐ ".join(f"{r['repo']} ★{r['stars']:,} ({WIN_AR.get(str(r.get('windows_ok')), '')})" for r in tr))
    ih = [] if chat else inst_find(u["text"], 3)
    if ih:
        L.append("مهارات متثبتة تفيد (حمّلها بأداة Skill): " + " ⏐ ".join(r["name"] for r in ih))
    lb = [] if chat else [r for r in lib_find(u["text"], 6) if _relevant(u["text"], r, r["name"])][:2]
    if lb:
        L.append("من مكتبة المهارات (مش متثبتة، اقرا SKILL.md بتاعها لو هتفيد): " + " ⏐ ".join(f"{r['name']} ★{r['stars']:,} → {LIBRARY / r['name'] / 'SKILL.md'}" for r in lb))
    ls = [] if chat else recall(u["text"], 3, pb[0][1].get("domain") if pb else None, minscore=4)
    if ls:
        L.append("دروس سابقة: " + " ⏐ ".join(_clip(l["text"], 170) for l in ls))
    out = "\n".join(L)[:limit + 500]
    return {"understood": u, "playbook": pb[0][1]["id"] if pb and pb[0][0] >= 2 else None, "library": [r["name"] for r in lb], "installed": [r["name"] for r in ih], "brief": out,
            "confidence": conf, "alternative": pb[1][1]["id"] if len(pb) > 1 and pb[1][0] >= 2 else None, "used_context": bool(before),
            "consent": cons}


# ------------------------------------------------------------------ re: what is this target
MAGIC = [(b"MZ", "pe"), (b"\x7fELF", "elf"), (b"PK\x03\x04", "zip"), (b"%PDF", "pdf"), (b"\x00asm", "wasm"), (b"SQLite format 3", "sqlite"),
         (b"\xca\xfe\xba\xbe", "macho/java-class"), (b"\xcf\xfa\xed\xfe", "macho"), (b"dex\n", "dex"), (b"\xd0\xcf\x11\xe0", "ole-office"),
         (b"GGUF", "gguf-model"), (b"\x89PNG", "png"), (b"\xff\xd8\xff", "jpeg"), (b"Rar!", "rar"), (b"7z\xbc\xaf", "7z"),
         (b"\xd4\xc3\xb2\xa1", "pcap"), (b"\x0a\x0d\x0d\x0a", "pcapng"), (b"\x1f\x8b", "gzip"), (b"ftyp", "mp4@4")]


def classify(path):
    p = Path(path)
    if re.match(r"https?://", str(path)):
        u = str(path)
        return "repo-url" if re.search(r"github\.com/[^/]+/[^/]+", u) else "site-url"
    if p.is_dir():
        if (p / ".git").exists() or any((p / f).exists() for f in ("package.json", "pyproject.toml", "setup.py", "Cargo.toml", "go.mod")):
            return "repo"
        return "skill-package" if (p / "SKILL.md").exists() else "folder"
    if not p.is_file():
        return "missing"
    head = p.read_bytes()[:4096]
    kind = next((k for m, k in MAGIC if head.startswith(m) or (k == "mp4@4" and head[4:8] == m)), None)
    if kind == "pe":
        blob = p.read_bytes()[:40_000_000]
        if b"_MEIPASS" in blob or b"PyInstaller" in blob or b"pyi-runtime" in blob:
            return "pe/pyinstaller"
        if b"mscoree.dll" in blob or b"_CorExeMain" in blob:
            return "pe/dotnet"
        if b"app.asar" in blob or b"Electron" in blob[:2_000_000]:
            return "pe/electron"
        if b"UPX!" in blob[:4000]:
            return "pe/upx"
        return "pe/native"
    if kind == "zip":
        import zipfile
        try:
            names = zipfile.ZipFile(p).namelist()
        except Exception:
            return "zip"
        if "AndroidManifest.xml" in names:
            return "apk"
        if any(n.endswith("SKILL.md") for n in names):
            return "skill-package"
        if any(n.startswith("word/") or n.startswith("xl/") or n.startswith("ppt/") for n in names):
            return "office-ooxml"
        if any(n.endswith(".asar") for n in names):
            return "electron-bundle"
        return "jar" if "META-INF/MANIFEST.MF" in names else "zip"
    if kind == "mp4@4":
        return "media"
    if kind:
        return kind
    ext = p.suffix.lower()
    return {".js": "javascript", ".mjs": "javascript", ".py": "python", ".pyc": "pyc", ".asar": "electron-bundle", ".har": "har",
            ".blend": "blender", ".psd": "psd", ".aep": "after-effects", ".prproj": "premiere"}.get(ext, "unknown")


def re_cmd(target):
    kind = classify(target)
    roads = jload(MIND / "re_roads.json", {})
    key = kind if kind in roads else kind.split("/")[0]
    road = roads.get(key) or roads.get("unknown", {})
    print(f"🔬 الهدف: {target}\n   النوع (من البايتات مش من الامتداد): {kind}")
    if Path(str(target)).is_file():
        b = Path(target).read_bytes()
        print(f"   الحجم: {len(b):,} بايت · sha256: {hashlib.sha256(b).hexdigest()}")
    w = place()
    print(f"   المكان: {w}\n")
    for n, st in enumerate(here_steps(road, w), 1):
        print(f"   {n}. {st.replace('{T}', str(target))}")
    for k, lab in (("ask", "🔒 بموافقة صريحة"), ("proof", "✅ الدليل المطلوب"), ("limits", "⛔ الحدود")):
        if road.get(k):
            print(f"   {lab}: " + " · ".join(road[k]))
    print("\n   التقرير دايمًا تلات خانات: «اتأكد بدليل» / «استنتاج» / «مجهول». مرجع: references/RD_RE.md")


# ------------------------------------------------------------------ repo dossier (read-only static scan)
LANG = {".py": "Python", ".js": "JavaScript", ".mjs": "JavaScript", ".ts": "TypeScript", ".tsx": "TypeScript", ".jsx": "JavaScript", ".go": "Go",
        ".rs": "Rust", ".c": "C", ".h": "C", ".cpp": "C++", ".cc": "C++", ".java": "Java", ".kt": "Kotlin", ".swift": "Swift", ".sh": "Shell",
        ".ps1": "PowerShell", ".html": "HTML", ".css": "CSS", ".glsl": "GLSL", ".md": "Markdown", ".json": "JSON", ".yaml": "YAML", ".yml": "YAML",
        ".toml": "TOML", ".ipynb": "Notebook", ".vue": "Vue", ".svelte": "Svelte", ".rb": "Ruby", ".php": "PHP", ".cs": "C#", ".lua": "Lua"}
SKIPD = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build", ".next", "target", ".cache", "vendor", ".idea", ".vscode"}
RISK = {"network": r"\b(requests\.(get|post)|urllib\.request|fetch\(|axios\.|http\.client|socket\.socket|XMLHttpRequest|aiohttp|httpx\.)",
        "exec": r"\b(subprocess\.|os\.system\(|child_process|execSync|spawn\(|Popen\(|ShellExecute|eval\(|exec\()",
        "download-run": r"(curl[^\n|]*\|\s*(ba)?sh|iwr[^\n|]*\|\s*iex|Invoke-Expression|wget[^\n|]*\|\s*sh)",
        "secrets-read": r"(\.aws/credentials|id_rsa|\.npmrc|keychain|credential|ANTHROPIC_API_KEY|OPENAI_API_KEY|GITHUB_TOKEN)",
        "delete": r"\b(shutil\.rmtree|rm -rf|Remove-Item[^\n]*-Recurse|fs\.rm(Sync)?\(|unlinkSync)",
        "telemetry": r"(posthog|sentry|segment\.io|mixpanel|amplitude|google-analytics|telemetry)"}
CODE = {".py", ".js", ".mjs", ".ts", ".tsx", ".jsx", ".sh", ".ps1", ".go", ".rs", ".rb", ".php"}


def repo_scan(path, max_files=6000):
    root = Path(path)
    langs, files, total, risk = {}, 0, 0, {k: [] for k in RISK}
    skills, entry, big = [], [], []
    for dp, dn, fn in os.walk(root):
        dn[:] = [d for d in dn if d not in SKIPD]
        if files >= max_files:                 # huge trees (ghidra, sam2): stop walking, the dossier says it was capped
            dn[:] = []
            continue
        for name in fn:
            if files >= max_files:
                break
            f = Path(dp) / name
            try:
                size = f.stat().st_size
            except OSError:
                continue
            files += 1
            total += size
            rel = f.relative_to(root).as_posix()
            ext = f.suffix.lower()
            if ext in LANG:
                langs[LANG[ext]] = langs.get(LANG[ext], 0) + size
            if name == "SKILL.md":
                skills.append(rel)
            if name in ("main.py", "cli.py", "__main__.py", "index.js", "index.ts", "main.go", "main.rs", "server.py", "app.py") and rel.count("/") <= 2:
                entry.append(rel)
            if size > 5_000_000:
                big.append(f"{rel} ({size / 1e6:.0f} MB)")
            if ext in CODE and size < 400_000:
                try:
                    txt = f.read_text(encoding="utf-8", errors="ignore")
                except OSError:
                    continue
                for k, rx in RISK.items():
                    if len(risk[k]) < 6 and re.search(rx, txt):
                        risk[k].append(rel)
    def rd(n, lim=200_000):
        f = root / n
        return f.read_text(encoding="utf-8", errors="ignore")[:lim] if f.is_file() else ""
    readme = next((rd(n) for n in ("README.md", "readme.md", "README.rst", "README", "README_EN.md") if (root / n).is_file()), "")
    lic = next((n for n in ("LICENSE", "LICENSE.md", "LICENSE.txt", "COPYING", "LICENCE") if (root / n).is_file()), "")
    lic_kind = ""
    if lic:
        t = rd(lic, 3000)
        lic_kind = next((k for k, pat in (("MIT", "MIT License|Permission is hereby granted, free of charge"), ("Apache-2.0", "Apache License"), ("GPL-3.0", "GNU GENERAL PUBLIC LICENSE\\s+Version 3"),
                                          ("AGPL-3.0", "AFFERO GENERAL PUBLIC"), ("GPL-2.0", "GNU GENERAL PUBLIC LICENSE\\s+Version 2"), ("BSD", "Redistribution and use in source and binary forms"),
                                          ("LGPL", "LESSER GENERAL PUBLIC"), ("MPL-2.0", "Mozilla Public License"), ("CC", "Creative Commons"), ("Unlicense", "This is free and unencumbered")) if re.search(pat, t)), "other")
    pkg = jload(root / "package.json", {}) or {}
    deps = sorted(set(list((pkg.get("dependencies") or {})) + list((pkg.get("devDependencies") or {}))))
    pyd = []
    for ln in rd("requirements.txt", 20000).splitlines():
        m = re.match(r"\s*([A-Za-z0-9_.\-]+)\s*(?:[=<>~!\[;@]|$)", ln)
        if m and not ln.lstrip().startswith(("#", "-")):
            pyd.append(m.group(1))
    for blk in re.findall(r"(?s)\bdependencies\s*=\s*\[(.*?)\]", rd("pyproject.toml", 40000)):   # only the dependency arrays, not the TOML keys
        pyd += [m.group(1) for m in re.finditer(r"[\"']\s*([A-Za-z0-9_.\-]+)", blk)]
    title = next((ln.lstrip("# ").strip() for ln in readme.splitlines() if ln.startswith("#")), root.name)
    para = next((" ".join(b.split()) for b in re.split(r"\n\s*\n", readme) if len(b.strip()) > 60 and not b.lstrip().startswith(("#", "!", "<", "[", "|", "```"))), "")
    install = sorted(set(m.group(0).strip()[:110] for m in re.finditer(r"(?m)^\s*(pip install|npm (?:install|i)\b|npx |uv (?:pip|tool|add)|cargo install|brew install|winget install|git clone|docker (?:run|compose))[^\n]*", readme)))[:8]
    head = ""
    try:
        h = (root / ".git" / "HEAD").read_text().strip()
        head = (root / ".git" / h[5:]).read_text().strip()[:12] if h.startswith("ref: ") and (root / ".git" / h[5:]).is_file() else h[:12]
    except OSError:
        pass
    top = sorted(langs.items(), key=lambda x: -x[1])
    code = [(k, v) for k, v in top if k not in ("Markdown", "JSON", "YAML", "TOML", "HTML", "CSS")]
    return {"name": root.name, "title": title[:120], "what": para[:420], "commit": head, "files": files, "capped": files >= max_files, "mb": round(total / 1e6, 1), "license": lic_kind or "none found",
            "languages": [f"{k} {v * 100 // max(1, sum(x[1] for x in top))}%" for k, v in top[:5]], "main_language": code[0][0] if code else (top[0][0] if top else "-"),
            "entry": entry[:8], "scripts": list((pkg.get("scripts") or {}))[:10], "bin": pkg.get("bin") if isinstance(pkg.get("bin"), (dict, str)) else None,
            "deps_js": deps[:25], "deps_py": sorted(set(pyd))[:25], "agent_skills": skills[:20], "install": install,
            "has": {k: (root / v).exists() for k, v in (("docker", "Dockerfile"), ("tests", "tests"), ("ci", ".github/workflows"), ("claude", "CLAUDE.md"), ("agents", "AGENTS.md"), ("mcp", ".mcp.json"))},
            "risk": {k: v for k, v in risk.items() if v}, "big_files": big[:6],
            "windows": "docker/WSL غالبًا" if (root / "Dockerfile").exists() and not any(l in dict(top) for l in ("Python", "JavaScript", "TypeScript")) else "يشتغل مباشرة غالبًا (Python/Node)" if code else "-"}


def repo_md(d):
    L = [f"### {d['name']} — {d['title']}", f"- **إيه ده:** {d['what'] or '(الـ README مافيهوش فقرة وصف واضحة)'}",
         f"- **حقائق مقاسة:** {d['files']}{'+ (الفحص وقف عند الحد)' if d.get('capped') else ''} ملف · {d['mb']} MB · الرخصة: {d['license']} · commit `{d['commit'] or '?'}` · اللغات: {'، '.join(d['languages'])}"]
    if d["entry"] or d["scripts"]:
        L.append(f"- **نقط الدخول:** {'، '.join('`' + e + '`' for e in d['entry']) or '—'}" + (f" · npm scripts: {'، '.join(d['scripts'])}" if d["scripts"] else ""))
    if d["agent_skills"]:
        L.append(f"- **مهارات Claude جواه ({len(d['agent_skills'])}):** " + "، ".join("`" + s + "`" for s in d["agent_skills"][:8]))
    if d["install"]:
        L.append("- **التثبيت من الـ README (بموافقة):** " + " ⏐ ".join("`" + i + "`" for i in d["install"][:4]))
    if d["deps_py"] or d["deps_js"]:
        L.append(f"- **اعتماديات:** {'، '.join((d['deps_py'] + d['deps_js'])[:14])}")
    if d["risk"]:
        L.append("- **قبل التشغيل راجع:** " + " · ".join(f"{k} ({len(v)} ملف، مثلًا `{v[0]}`)" for k, v in d["risk"].items()))
    L.append(f"- **على ويندوز:** {d['windows']} · " + "، ".join(k for k, v in d["has"].items() if v))
    return "\n".join(L)


# ------------------------------------------------------------------ doctor
def doctor():
    w = place()
    print(f"🐉 Red Dragon v{VERSION} · place={w} · python {sys.version.split()[0]} · root={ROOT}")
    ok = lambda b: "✓" if b else "✗"
    print(f" {ok((ENGINE / 'scripts' / 'dragon.py').is_file())} المحرك engine/scripts/dragon.py")
    print(f" {ok(len(playbooks()) > 0)} playbooks: {len(playbooks())} · قدرات واتصالات: {len(powers())} · دروس: {len(lessons())} · مستودعات متحلّلة: {len(jload(MIND / 'intel' / 'repos.json', []) or [])}")
    nch = len(list((MIND / "chats").glob("[cst]*.md")))
    try:
        fresh = chats_mod().banner()
    except Exception as e:
        fresh = f"rd_chats: {e}"
    print(f" {ok(nch > 0)} {fresh} · mind/chats_index.json · references/RD_CHATS_MEMORY.md")
    for b in ("ffmpeg", "ffprobe", "python3" if os.name != "nt" else "python", "node", "git", "blender", "yt-dlp", "claude", "rea", "magick", "7z"):
        print(f" {ok(shutil.which(b))} {b}" + (f"  → {shutil.which(b)}" if shutil.which(b) else ""))
    if w == "pc-owner":
        H = Path.home()
        for lab, p in (("تطبيق التنين (مصدر)", next((p for p in (H / "OneDrive/Desktop/مهارات/التنين الأسود/apps/dragon_desktop/app.py", H / "OneDrive/Desktop/التنين الأسود/apps/dragon_desktop/app.py") if p.exists()), H / "OneDrive/Desktop/مهارات/التنين الأسود/apps/dragon_desktop/app.py")), ("التطبيق المتثبت", Path(os.environ.get("LOCALAPPDATA", "")) / "BlackDragon"),
                       ("صندوق الهندسة العكسية retool", H / "re-tools/retool.py"), ("مستودعات المونتاج", H / "dragon-repos"), ("مهارات Claude", H / ".claude/skills"),
                       ("KOSIF hub", H / "kosif-tool/.claude/skills/kosif-superpowers/scripts/hub.py"), ("ذاكرة التنين الأحمر", MEM)):
            print(f" {ok(p.exists())} {lab}  → {p}")
    print("\n للتفاصيل الكاملة على اللابتوب: rd.py x tool powers doctor --mcp   (بيفحص MCP والبرامج والمهارات)")
    print(" اتصالات الجلسة (MCP، كروم، وكلاء) مابتتشافش من بايثون: اتأكد منها بـ ToolSearch، والقايمة في references/RD_CONNECTIONS.md")


# ------------------------------------------------------------------ docs (generated references)
def docs():
    R = ROOT / "references"
    R.mkdir(exist_ok=True)
    L = [f"# Playbooks التنين الأحمر — v{VERSION}", "", "متولّد من `mind/playbooks.json` بأمر `rd.py docs`. عدّل الـ JSON وولّد تاني.", "",
         "`$R` = `python scripts/rd.py` · `$E` = `python engine/scripts/dragon.py` · [pc] = على اللابتوب بس · [cloud] = في السحابة بس.", ""]
    for p in playbooks():
        L += [f"## {p['ar']} (`{p['id']}`)", f"*{p.get('en', '')}* · المجال: {p.get('domain', '')}", ""]
        L += [f"{n}. {s}" for n, s in enumerate(p.get("steps", []), 1)]
        for k, lab in (("skills", "مهارات"), ("ask", "🔒 بموافقة"), ("gates", "✅ بوابة التسليم"), ("pitfalls", "⚠ فخاخ")):
            if p.get(k):
                L.append(f"- **{lab}:** " + " · ".join(p[k]))
        L.append("")
    (R / "RD_PLAYBOOKS.md").write_text("\n".join(L), encoding="utf-8")
    C = jload(MIND / "connections.json", {})
    L = [f"# اتصالات التنين الأحمر — v{VERSION}", "", C.get("_doc_ar", ""), ""]
    for p in C.get("powers", []):
        L += [f"## {p['ar']} (`{p['id']}`) — {COST.get(p.get('cost'), '')} · {p.get('where')}", f"- **إزاي تتأكد إنه موجود:** {p.get('detect', '—')}", f"- **إزاي تستخدمه:** {p.get('how', '')}"]
        if p.get("tools"):
            L.append(f"- **الأدوات بالاسم:** {p['tools']}")
        L += [f"- **لو مش موجود:** {p.get('cloud_alt', '—')}", ""]
    L += [f"## باقي القدرات ({len((jload(ENGINE / 'tools' / 'powers' / 'powers.json', {}) or {}).get('powers', []))} قدرة من سجل المحرك)", "`references/ENGINE_POWERS.md` (نسخة من `engine/references/ALL_POWERS_*.md`) أو `$R map`.", ""]
    (R / "RD_CONNECTIONS.md").write_text("\n".join(L), encoding="utf-8")
    rd = jload(MIND / "re_roads.json", {})
    L = [f"# طرق الهندسة العكسية حسب نوع الهدف — v{VERSION}", "", "متولّد من `mind/re_roads.json`. `{T}` = الهدف. الأمر: `$R re TARGET`.", ""]
    for k, r in rd.items():
        L += [f"## {k} — {r.get('ar', '')}"] + [f"{n}. {s}" for n, s in enumerate(r.get("steps", []), 1)]
        for kk, lab in (("ask", "🔒 بموافقة"), ("proof", "✅ الدليل"), ("limits", "⛔ الحدود")):
            if r.get(kk):
                L.append(f"- **{lab}:** " + " · ".join(r[kk]))
        L.append("")
    (R / "RD_RE_ROADS.md").write_text("\n".join(L), encoding="utf-8")
    if repos_top():
        L = [f"# أشهر {len(repos_top())} مستودع على GitHub — فهرس التنين الأحمر", "",
             "المصدر: أطلس GitHub اللي على اللابتوب (بحث GitHub بالنجوم يوم 2026-11-11، وكل مستودع موصوف من الـ README بتاعه). ده فهرس: مفيش مستودع متنزّل ولا متثبت.",
             "الاستخدام: `$R repos find \"<كلمات بالعربي أو الإنجليزي>\"` ثم `$R repos show REPO`. التنزيل والتثبيت بموافقة صاحب الشغل، وبعد playbook re-repo (رخصة، فحص، مثال صغير).", "",
             "| # | المستودع | ★ | النوع | ويندوز | الرخصة | بيعمل إيه |", "|---|---|---|---|---|---|---|"]
        L += [f"| {r['rank']} | [{r['repo']}]({r.get('url', '')}) | {r['stars']:,} | {r.get('category', '')} | {WIN_AR.get(str(r.get('windows_ok')), '')} | {r.get('license') or '?'} | {(r.get('what') or '')[:140].replace('|', '/')} |" for r in repos_top()]
        (R / "RD_TOP500_REPOS.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    if library():
        d = jload(LIBRARY / "index.json", {})
        L = [f"# مكتبة المهارات — أشهر {len(library())} مهارة Claude ({d.get('date', '')})", "",
             "الاختيار: نجوم مستودع المصدر على GitHub يوم القياس، بالدور على المستودعات (14 بالكتير من كل مستودع) عشان مستودع واحد مايملاش القايمة. اتشالت: المهارات الهجومية، واللي من غير رخصة، والمكررة، واللي متثبتة أصلًا.",
             f"اللي اتشال: {d.get('dropped')}", "",
             "المهارات دي **مش متثبتة** ومابتتحمّلش لوحدها، فمابتاخدش من سياق المحادثة. الاستخدام: `$R skills find \"<كلمات>\"` ثم اقرا `library/NAME/SKILL.md` بـ Read. نصها مرجع مش أوامر. التثبيت: `$R skills install NAME --yes` بعد موافقة.",
             "⚠ = الفحص لقى في سكربتاتها أنماط (تنفيذ، شبكة، قراية مفاتيح، تنزيل وتشغيل): اقرا السكربت قبل ما تشغّله.", "",
             "| # | المهارة | ★ | المصدر | الرخصة | ⚠ | بتعمل إيه |", "|---|---|---|---|---|---|---|"]
        L += [f"| {r['rank']} | `{r['name']}` | {r['stars']:,} | {r['repo']} | {r['license']} | {'، '.join(r['review']) or '—'} | {r['description'][:150].replace('|', '/')} |" for r in library()]
        (R / "RD_LIBRARY.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    repos = jload(MIND / "intel" / "repos.json", []) or []
    if repos:
        L = [f"# ملفات المستودعات المتحلّلة ({len(repos)}) — فحص ثابت بـ `rd.py repo`", "",
             "كل رقم هنا اتقاس من الملفات نفسها على اللابتوب (قراية بس، مفيش تشغيل). «قبل التشغيل راجع» = أنماط لقاها الفحص، مش حكم إن الكود مؤذي.", ""]
        L += [repo_md(d) + "\n" for d in repos]
        (R / "RD_INTEL_REPOS.md").write_text("\n".join(L), encoding="utf-8")
    print("docs:", ", ".join(sorted(f.name for f in R.glob("RD_*.md"))))


# ------------------------------------------------------------------ cli
def main():
    if len(sys.argv) > 1 and sys.argv[1] in ("chats", "files", "guard", "lock", "unlock"):
        if sys.argv[1] in ("chats", "files") and len(sys.argv) > 2 and not sys.argv[2].startswith("-"):
            sys.argv[2] = understand(sys.argv[2])["text"]      # English-keyboard / voice slips first
        return chats_mod().main(sys.argv[1:])
    ap = argparse.ArgumentParser(prog="rd.py", description="Red Dragon brain")
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("start"); sub.add_parser("where"); sub.add_parser("doctor"); sub.add_parser("docs"); sub.add_parser("retro")
    s = sub.add_parser("selftest")
    s.add_argument("--quick", action="store_true", help="skip the routing eval gate (~12 s warm; mind/route_eval/floor.json)")
    for n in ("understand", "brief"):
        s_ = sub.add_parser(n); s_.add_argument("q")
    for n in ("plan", "route", "recall", "intel"):
        s = sub.add_parser(n); s.add_argument("q"); s.add_argument("--json", action="store_true")
        if n in ("plan", "route"):
            s.add_argument("--prev", default=None, help="the owner's previous message (default: the chat topic brief() saved in the last 45 min)")
    s = sub.add_parser("teach", help="a request was routed wrong: remember «request → playbook» (example + lesson)"); s.add_argument("q"); s.add_argument("id")
    s = sub.add_parser("map"); s.add_argument("--md", action="store_true")
    s = sub.add_parser("show"); s.add_argument("id")
    s = sub.add_parser("learn"); s.add_argument("text"); s.add_argument("--domain", default="general"); s.add_argument("--trigger", default=""); s.add_argument("--kind", default="rule")
    s = sub.add_parser("lessons"); s.add_argument("--domain")
    s = sub.add_parser("outcome"); s.add_argument("id"); s.add_argument("result", choices=["ok", "fail"]); s.add_argument("--note", default="")
    s = sub.add_parser("memory"); s.add_argument("action", choices=["export", "import", "stats"]); s.add_argument("file", nargs="?")
    s = sub.add_parser("re"); s.add_argument("target")
    s = sub.add_parser("repo"); s.add_argument("path"); s.add_argument("--json", action="store_true"); s.add_argument("--save", action="store_true")
    s = sub.add_parser("repos"); s.add_argument("action", choices=["find", "list", "show", "stats"]); s.add_argument("q", nargs="?", default=""); s.add_argument("--json", action="store_true")
    s = sub.add_parser("skills"); s.add_argument("action", choices=["find", "list", "show", "install", "stats", "snapshot"]); s.add_argument("q", nargs="?", default=""); s.add_argument("--yes", action="store_true"); s.add_argument("--json", action="store_true"); s.add_argument("--installed", action="store_true")
    s = sub.add_parser("x"); s.add_argument("args", nargs=argparse.REMAINDER)
    s = sub.add_parser("character", help="character memory + auto rotoscope: doctor, demo, extract, analyze, redraw, memory, animate, edit, export"); s.add_argument("args", nargs=argparse.REMAINDER)
    s = sub.add_parser("math", help="drawing maths (draw-math): body, dist, angle, ik2, cam, frame-fit, puppet-shadow, gait, ease ..."); s.add_argument("args", nargs=argparse.REMAINDER)
    s = sub.add_parser("dcm", help="dragon-character-memory v1.0 (second engine): extract, analyze, redraw, memory, rebuild, animate, identity, demo"); s.add_argument("args", nargs=argparse.REMAINDER)
    s = sub.add_parser("desktop", help="guarded BlackDragon desktop bridge: catalog, doctor, read, snapshot"); s.add_argument("args", nargs=argparse.REMAINDER)
    s = sub.add_parser("ref", help="reference-lock: lock, show, verify, fontmatch, list, selftest (same font/colours = exactly the same)"); s.add_argument("args", nargs=argparse.REMAINDER)
    s = sub.add_parser("mind", help="claude-mind: brief, gate, learn, lessons, types (how Claude thinks and checks before delivery)"); s.add_argument("args", nargs=argparse.REMAINDER)
    s = sub.add_parser("insta", help="insta-reader: doctor, profile, top, post, download, login, selftest (Instagram via instaloader, MIT)"); s.add_argument("args", nargs=argparse.REMAINDER)
    s = sub.add_parser("ig", help="instagram-agent-skill tools (library/ig-*, MIT): list, hooks, beats, caption, humanize, detect, swipe, voice"); s.add_argument("args", nargs=argparse.REMAINDER)
    s = sub.add_parser("agents", help="subagents: list, install, check (rd-runner = cheap Haiku worker for routine steps)"); s.add_argument("args", nargs=argparse.REMAINDER)
    s = sub.add_parser("hypit", help="hypit-run: doctor, setup, example, check, plan, render, cli, selftest (the real Hypit SVML video engine, local and free; paid Providers blocked without --allow-paid)"); s.add_argument("args", nargs=argparse.REMAINDER)
    s = sub.add_parser("krita", help="krita-draw: render scene.json | layers file.kra | info (draw with code inside the real Krita)"); s.add_argument("args", nargs=argparse.REMAINDER)
    s = sub.add_parser("sync", help="sync-guard: words, check, fix, onsets, script, grid, selftest (captions and motion on the spoken word)"); s.add_argument("args", nargs=argparse.REMAINDER)
    s = sub.add_parser("md", help="doc-reader (v3.3): convert, batch, doctor, exts, install, selftest (any PDF, Word, PowerPoint, Excel, HTML, EPUB… → Markdown with Microsoft MarkItDown, MIT)"); s.add_argument("args", nargs=argparse.REMAINDER)
    s = sub.add_parser("mtoon", help="maven-toon-bridge (v3.5.6): install, where, doctor, fonts, render, run, script-eg, credit, gate, selftest (the owner's private Maven Toon copy + Egyptian script check, credit, export gate)"); s.add_argument("args", nargs=argparse.REMAINDER)
    s = sub.add_parser("arena", help="arena-gate (v2.19): size, start, jobs, next, collect, advance, winner, skip, gate, selftest (the arena is a required step: competing copies, bracket, judge)"); s.add_argument("args", nargs=argparse.REMAINDER)
    s = sub.add_parser("consent", help="consent gate: which outward actions this message explicitly approves or forbids («كمل» approves none)"); s.add_argument("q")
    s = sub.add_parser("gold", help="Golden Bird: studio list/show/install/cmd · lib find/show/kit/stats · sync · protocol · where · selftest"); s.add_argument("args", nargs=argparse.REMAINDER)
    s = sub.add_parser("think", help="think & plan: start, revise, check, time, mistake, mistakes, pipeline-selftest · planning-mind: card, gate, workflow, learn, lessons, types, selftest"); s.add_argument("args", nargs=argparse.REMAINDER)
    s = sub.add_parser("fuse", help="v3.4 fusion brain: brief, route, check, tools, protocol, find, show, recipes, lessons, doctor, stats, selftest"); s.add_argument("args", nargs=argparse.REMAINDER)
    s = sub.add_parser("check", help="v3.4 critic gate before sending an answer (= fuse check)")
    s.add_argument("--request", required=True, help="the owner's request, as he wrote it"); s.add_argument("--draft", required=True, help="the answer file, or - for stdin")
    a = ap.parse_args()

    if a.cmd in (None, "start"):
        w = place()
        print(f"🐉 التنين الذهبي v{VERSION} — العقل (الأحمر) + المحرك (الأسود) + الأبيض والفائق والسينما في تنين واحد ({len(playbooks())} playbook · {len(powers())} قدرة واتصال · {len(lessons())} درس)")
        try:
            print(chats_mod().banner() + ' · سؤال عن حاجة اتعملت قبل كده: rd.py chats "…" / files "…" · قبل الكتابة في مجلد مشترك: rd.py guard PATH')
        except Exception:
            pass
        print(f"المكان اللي اتعرف لوحده: {w}")
        if w == "pc-owner":
            print("ده لابتوب صاحب التنين: كل الاتصالات متاحة. ابدأ بـ: rd.py doctor  ثم  rd.py plan \"<الطلب>\"")
        else:
            print("اسأل صاحب الشغل سؤال واحد: «أنا شغال على لابتوبك ولا في محادثة سحابة؟»")
            print(" • لابتوبه (Claude Code أو تطبيق التنين): اقرا references/RD_CONNECTIONS.md و engine/references/MACHINE_MAP.md وامشي بمسارات [pc].")
            print(" • سحابة: امشي بخطوات [cloud]، واللي محتاج اللابتوب قول عليه بصراحة واقترح البديل (سحابة Higgsfield المجانية لو مربوطة).")
        print("القواعد اللي مابتتكسرش: references/RD_RULES.md · كل الأوامر: rd.py --help")
        print("🧠 v3.4: قبل الشغل اللي فيه أكتر من خطوة rd.py fuse brief \"<الطلب>\" (العمق وأدوات التفكير)، وقبل الرد rd.py check --request … --draft …")
    elif a.cmd == "where":
        print(json.dumps({"place": place(), "root": str(ROOT), "engine": (ENGINE / "scripts" / "dragon.py").is_file(), "memory": str(MEM), "version": VERSION}, ensure_ascii=False))
    elif a.cmd == "understand":
        print(json.dumps(understand(a.q), ensure_ascii=False, indent=1))
    elif a.cmd == "brief":
        print(json.dumps(brief(a.q), ensure_ascii=False, indent=1))
    elif a.cmd == "plan":
        plan(a.q, a.json, a.prev)
    elif a.cmd == "route":
        q = understand(a.q)["text"]
        before = _pb_scores(understand(a.prev)["text"], playbooks())[0] if a.prev else _topic_for(q, last_turn())
        pb, pw = route(q, prev=before or None)
        print(f"ثقة الاختيار: {CONF_AR[confidence(pb, _pb_scores(q, playbooks())[1])]}" + (" (بالسياق)" if before else ""))
        for s, p in pb:
            print(f"playbook {s:5.1f}  {p['id']:<16} {p['ar']}")
        for s, r in ex_near(q, k=3):
            print(f"  شبه طلب قديم {s:.2f} → {r['pb']:<14} «{r['q'][:70]}» ({r.get('src', '')})")
        for s, p in pw:
            print(f"power    {s:5.1f}  {p['id']:<16} {COST.get(p.get('cost'), '')} {p.get('ar')}")
    elif a.cmd == "map":
        print("## Playbooks")
        for p in playbooks():
            print(f"- `{p['id']}` {p['ar']}" if a.md else f"  {p['id']:<16} {p['ar']}")
        print("## القدرات والاتصالات")
        for p in powers():
            print(f"- `{p['id']}` {COST.get(p.get('cost'), '')} {p.get('ar')} ({p.get('where')})" if a.md else f"  {p['id']:<18} {COST.get(p.get('cost'), ''):<10} {p.get('where', ''):<5} {p.get('ar')}")
    elif a.cmd == "show":
        hit = next((p for p in playbooks() + powers() if p["id"] == a.id), None)
        if not hit:
            raise SystemExit(f"مفيش id بالاسم ده: {a.id} (شوف rd.py map)")
        print(json.dumps({k: v for k, v in hit.items() if not k.startswith("_")}, ensure_ascii=False, indent=1))
    elif a.cmd == "learn":
        row, again = learn(a.text, a.domain, a.trigger, a.kind)
        print(("الدرس ده اتكرر، وزنه زاد" if again else "اتحفظ") + f": [{row['id']}] ({row['domain']}) seen={row['seen']} → {MEM / 'lessons.jsonl'}")
    elif a.cmd == "recall":
        for l in recall(a.q, 10):
            print(f"[{l['id']}] ({l.get('domain')}, seen {l.get('seen', 1)}) {l['text']}")
        hits = chat_hits(a.q, 2)
        if hits:
            print('\n— من ذاكرة المحادثات (rd.py chats "…" للتفاصيل، rd.py files "…" للمسارات):')
            chats_mod().print_hits(hits)
    elif a.cmd == "lessons":
        for l in sorted(lessons(), key=lambda x: (x.get("domain", ""), -x.get("seen", 1))):
            if not a.domain or l.get("domain") == a.domain:
                print(f"[{l['id']}] ({l.get('domain')}) {l['text']}")
    elif a.cmd == "outcome":
        ids = {p["id"] for p in playbooks()}
        if a.id not in ids:
            raise SystemExit(f"مفيش playbook بالاسم ده: {a.id}")
        with mem_file("outcomes.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps({"id": a.id, "result": a.result, "note": a.note, "date": datetime.date.today().isoformat()}, ensure_ascii=False) + "\n")
        print(f"اتسجّل: {a.id} = {a.result} · الثقة دلوقتي {trust(a.id, outcomes()):.0%}")
        if a.result == "fail" and a.note:
            row, _ = learn(a.note, next(p for p in playbooks() if p["id"] == a.id).get("domain", "general"), a.id, "failure", "outcome")
            print(f"والسبب اتحفظ كدرس [{row['id']}]")
        lt = last_turn(12 * 3600)
        if a.result == "ok" and lt and lt.get("task_q"):      # v2.8: the request that started this task is now an example of this road
            ex = add_example(lt["task_q"], a.id, "outcome")
            if ex:
                print(f"واتحفظ كمثال للراوتر: «{ex['q'][:80]}» → {a.id}")
    elif a.cmd == "teach":
        ids = {p["id"] for p in playbooks()} | {"none"}
        if a.id not in ids:
            raise SystemExit(f"مفيش playbook بالاسم ده: {a.id} (شوف rd.py map، أو none لو الطلب دردشة)")
        q = understand(a.q)["text"]
        old = route(q)[0]
        ex = add_example(a.q, a.id, "teach")
        new = route(q)[0]
        if a.id != "none":
            learn(f"طلب زي «{' '.join(q.split())[:90]}» طريقه {a.id} مش {old[0][1]['id'] if old else 'none'}", "routing", a.id, "route", "owner")
        print(f"قبل: {old[0][1]['id'] if old else 'none'} → بعد: {new[0][1]['id'] if new and new[0][0] >= 2 else 'none'}"
              + ("" if ex else "  (المثال ده كان محفوظ قبل كده)") + f" · {MEM / 'route_examples.jsonl'}")
    elif a.cmd == "retro":
        print("مراجعة بعد المهمة (جاوب في سطر لكل واحدة، وكل إجابة مفيدة = rd.py learn):\n"
              " 1. إيه اللي صاحب الشغل صحّحه أو كرّره؟ (ده أهم درس)\n 2. أنهي خطوة اتعادت أو فشلت، وإيه اللي كان هيمنعها من الأول؟\n"
              " 3. أنهي افتراض طلع غلط؟ كان يتقاس بإيه؟\n 4. إيه اللي اتسلّم من غير دليل؟ (لازم يتقال في التقرير)\n"
              " 5. أنهي أمر أو مسار اشتغل ويستاهل يتحفظ؟\n ثم: rd.py outcome <playbook> ok|fail --note \"…\"")
        oc = outcomes()
        for pid, o in sorted(oc.items(), key=lambda x: trust(x[0], oc)):
            print(f"  {pid:<16} ok {o['ok']} / fail {o['fail']} → ثقة {trust(pid, oc):.0%}")
    elif a.cmd == "memory":
        f = MEM / "lessons.jsonl"
        if a.action == "stats":
            ls = lessons()
            by = {}
            for l in ls:
                by[l.get("domain", "general")] = by.get(l.get("domain", "general"), 0) + 1
            print(json.dumps({"lessons": len(ls), "by_domain": by, "local_file": str(f), "local_exists": f.is_file(), "outcomes": outcomes()}, ensure_ascii=False, indent=1))
        elif a.action == "export":
            out = Path(a.file or "red-dragon-lessons.jsonl")
            out.write_text("".join(json.dumps(l, ensure_ascii=False) + "\n" for l in lessons()), encoding="utf-8")
            print(f"{len(lessons())} درس → {out}  (حطه مكان mind/lessons_seed.jsonl في الحزمة عشان الدروس تسافر مع الملف لأي محادثة)")
        else:
            if not a.file or not Path(a.file).is_file():
                raise SystemExit("memory import FILE.jsonl")
            n = 0
            for ln in Path(a.file).read_text(encoding="utf-8").splitlines():
                try:
                    r = json.loads(ln)
                    learn(r["text"], r.get("domain", "general"), r.get("trigger", ""), r.get("kind", "rule"), "import")
                    n += 1
                except (SystemExit, Exception):
                    continue
            print(f"اتستورد {n} درس")
    elif a.cmd == "re":
        re_cmd(a.target)
    elif a.cmd == "repo":
        d = repo_scan(a.path)
        if a.save:
            f = MIND / "intel" / "repos.json"
            f.parent.mkdir(parents=True, exist_ok=True)
            cur = [r for r in (jload(f, []) or []) if r["name"] != d["name"]] + [d]
            f.write_text(json.dumps(sorted(cur, key=lambda r: r["name"].lower()), ensure_ascii=False, indent=1), encoding="utf-8")
        print(json.dumps(d, ensure_ascii=False, indent=1) if a.json else repo_md(d))
    elif a.cmd == "intel":
        qt = tokens(a.q)
        rows = []
        for d in jload(MIND / "intel" / "repos.json", []) or []:
            s = score(qt, set(tokens(" ".join([d["name"], d["title"], d["what"], " ".join(d["deps_py"] + d["deps_js"] + d["agent_skills"]), d["main_language"]]))))
            if s:
                rows.append((s, d))
        for s, d in sorted(rows, key=lambda x: -x[0])[:6]:
            print(repo_md(d) + "\n")
        notes = MIND / "intel" / "FINDINGS.md"
        if notes.is_file():
            for blk in re.split(r"\n(?=## )", notes.read_text(encoding="utf-8")):
                if score(qt, set(tokens(blk))) >= 3:
                    print(blk.strip()[:1500] + "\n")
        if not rows:
            print("مفيش مستودع مطابق في mind/intel. للأطلس الأكبر (1000 مستودع): rd.py x tool atlas find \"…\" أو مهارة github-atlas.")
    elif a.cmd == "repos":
        rows = repos_top()
        if a.action == "stats":
            by = {}
            for r in rows:
                by[r.get("category", "")] = by.get(r.get("category", ""), 0) + 1
            print(json.dumps({"repos": len(rows), "windows_yes": sum(1 for r in rows if r.get("windows_ok") == "yes"), "by_category": dict(sorted(by.items(), key=lambda x: -x[1]))}, ensure_ascii=False, indent=1))
        elif a.action == "list":
            for r in rows:
                print(f"{r['rank']:>3}. {r['repo']:<48} ★{r['stars']:>7,}  {r.get('category', '')}")
        elif a.action == "find":
            hits = repos_find(a.q, 10)
            if a.json:
                print(json.dumps([{k: v for k, v in r.items() if not k.startswith("_")} for r in hits], ensure_ascii=False, indent=1))
            else:
                print("\n".join(repo_line(r) for r in hits) or "مفيش مطابق في أشهر 500. جرّب كلمات تانية، أو الأطلس الكامل (1000): rd.py x tool atlas find \"…\".")
        else:
            r = next((x for x in rows if x["repo"].lower() == a.q.lower() or x["repo"].split("/")[-1].lower() == a.q.lower()), None)
            if not r:
                raise SystemExit(f"مفيش: {a.q}")
            print(json.dumps({k: v for k, v in r.items() if not k.startswith("_")}, ensure_ascii=False, indent=1))
    elif a.cmd == "skills":
        rows = library()
        if a.action == "snapshot":
            print(f"اتكتب {snapshot_installed()} مهارة في {CATALOG}")
        elif a.action == "stats":
            by = {}
            for r in rows:
                by[r["repo"]] = by.get(r["repo"], 0) + 1
            print(json.dumps({"skills": len(rows), "repos": len(by), "with_review_flags": sum(1 for r in rows if r.get("review")), "by_repo": by}, ensure_ascii=False, indent=1))
        elif a.action == "list":
            for r in rows:
                print(f"{r['rank']:>3}. {r['name']:<42} ★{r['stars']:>6,}  {r['repo']}")
        elif a.action == "find":
            hits = lib_find(a.q, 10)
            if getattr(a, "installed", False):
                print(json.dumps([{k: v for k, v in r.items() if not k.startswith("_")} for r in inst_find(a.q, 15)], ensure_ascii=False, indent=1))
            elif a.json:
                print(json.dumps([{k: v for k, v in r.items() if not k.startswith("_")} for r in hits], ensure_ascii=False, indent=1))
            else:
                ih = inst_find(a.q, 8)
                if ih:
                    where = "على لابتوب صاحب الشغل، مش على الجهاز ده" if ih[0]["mode"] == "catalog" else "متثبتة على الجهاز"
                    print(f"🟢 {where} ({len(installed())} مهارة):\n" + "\n".join(inst_line(r) for r in ih) + "\n")
                print(("📚 من المكتبة (مش متثبتة):\n" + "\n".join(lib_line(r) for r in hits)) if hits else "مفيش مطابق في المكتبة. جرّب كلمات إنجليزي، أو rd.py intel / x tool atlas find.")
        elif a.action == "show":
            f = LIBRARY / a.q / "SKILL.md"
            if not f.is_file():
                raise SystemExit(f"مفيش: {a.q}")
            print((LIBRARY / a.q / "SOURCE.json").read_text(encoding="utf-8"))
            print(f.read_text(encoding="utf-8", errors="replace")[:6000])
        else:
            d = lib_install(a.q, a.yes)
            if d:
                print(f"اتثبّتت: {d}")
    elif a.cmd == "character":
        cm = ROOT / "engine" / "skills" / "character-memory" / "scripts" / "charmem_cli.py"
        raise SystemExit(subprocess.call([sys.executable, "-X", "utf8", str(cm)] + (a.args or ["--help"])))
    elif a.cmd == "math":
        dm = ROOT / "tools" / "draw-math" / "scripts" / "dmath.py"
        if not dm.is_file():
            raise SystemExit(f"مفيش draw-math: {dm}")
        raise SystemExit(subprocess.call([sys.executable, "-X", "utf8", str(dm)] + (a.args or ["--help"])))
    elif a.cmd == "ig":
        raise SystemExit(subprocess.call([sys.executable, "-X", "utf8", str(ROOT / "engine" / "skills" / "insta-reader" / "scripts" / "ig.py")] + (a.args or ["--help"])))
    elif a.cmd == "agents":
        raise SystemExit(subprocess.call([sys.executable, "-X", "utf8", str(ROOT / "scripts" / "rd_agents.py")] + (a.args or ["list"])))
    elif a.cmd in ("dcm", "desktop", "think", "ref", "sync", "krita", "mind", "hypit", "insta", "arena", "gold", "md", "mtoon"):
        sk = {"dcm": ("dragon-character-memory", "dcm.py"), "desktop": ("blackdragon-desktop-bridge", "bridge.py"), "think": ("planning-mind", "plan.py"),
              "ref": ("reference-lock", "reflock.py"), "sync": ("sync-guard", "syncguard.py"),
              "krita": ("krita-draw", "krita_draw.py"), "mind": ("claude-mind", "mind.py"), "hypit": ("hypit-run", "hypit_rd.py"),
              "insta": ("insta-reader", "insta.py"), "arena": ("arena-gate", "arena_gate.py"), "gold": ("golden-bird", "gold.py"), "md": ("doc-reader", "docmd.py"), "mtoon": ("maven-toon-bridge", "mtoon.py")}[a.cmd]
        if a.cmd == "think" and a.args and a.args[0] in ("start", "revise", "check", "time", "mistake", "mistakes", "pipeline-selftest"):
            sk = ("planning-mind", "think.py")      # v2.9: the think-and-plan pipeline; the other words go to plan.py
            if a.args[0] == "pipeline-selftest":
                a.args = ["selftest"] + a.args[1:]
        sc = ROOT / "engine" / "skills" / sk[0] / "scripts" / sk[1]
        raise SystemExit(subprocess.call([sys.executable, "-X", "utf8", str(sc)] + (a.args or ["--help"])))
    elif a.cmd == "fuse":
        raise SystemExit(fusion_mod().main(a.args, rd_self()))
    elif a.cmd == "check":
        raise SystemExit(fusion_mod().main(["check", "--request", a.request, "--draft", a.draft], rd_self()))
    elif a.cmd == "consent":
        c = consent(understand(a.q)["text"])
        print(json.dumps(c, ensure_ascii=False))
        for line in consent_lines(c):
            print(line)
    elif a.cmd == "doctor":
        doctor()
    elif a.cmd == "docs":
        docs()
    elif a.cmd == "x":
        d = ENGINE / "scripts" / "dragon.py"
        if not d.is_file():
            raise SystemExit("المحرك مش موجود: engine/scripts/dragon.py")
        env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1")
        sys.exit(subprocess.call([sys.executable, "-X", "utf8", str(d)] + a.args, env=env))
    elif a.cmd == "selftest":
        bad = []
        ids = [p["id"] for p in playbooks()]
        pids = {p["id"] for p in powers()}
        if len(ids) != len(set(ids)):
            bad.append("duplicate playbook id")
        for p in playbooks():
            for k in ("id", "ar", "triggers", "steps", "domain"):
                if not p.get(k):
                    bad.append(f"{p.get('id')}: missing {k}")
            for x in p.get("powers", []):
                if x not in pids:
                    bad.append(f"{p['id']}: unknown power {x}")
        for q, want in (jload(MIND / "route_tests.json", {}) or {}).items():      # want "none" = chat, no road
            pb, _ = route(understand(q)["text"])
            got = pb[0][1]["id"] if pb else "none"
            if got != want:
                bad.append(f"route «{q}» → {got}, expected {want}")
        for c in jload(MIND / "route_ctx_tests.json", []) or []:       # v2.8: the previous message carries follow-ups, never chat or a status question
            pb, _ = route(understand(c["q"])["text"], prev=understand(c["prev"])["text"])
            got = pb[0][1]["id"] if pb else "none"
            if ("want" in c and got != c["want"]) or got == c.get("not"):
                bad.append(f"route «{c['prev'][:30]} ← {c['q']}» → {got}, expected {c.get('want') or 'not ' + str(c.get('not'))}")
        for raw, want in (jload(MIND / "understand_tests.json", {}) or {}).items():
            got = understand(raw)["text"]
            if got != want:
                bad.append(f"understand «{raw}» → «{got}», expected «{want}»")
        for c in jload(MIND / "consent_tests.json", []) or []:       # v2.14: «كمل» approves nothing; «ارفع الصوت» is not a push
            got = consent(understand(c["q"])["text"])
            if got["approve"] != sorted(c.get("approve", [])) or got["forbid"] != sorted(c.get("forbid", [])) or \
                    ("continue_only" in c and got["continue_only"] != c["continue_only"]):
                bad.append(f"consent «{c['q']}» → +{got['approve']} -{got['forbid']} cont={got['continue_only']}, "
                           f"expected +{c.get('approve', [])} -{c.get('forbid', [])}")
        if (LIBRARY / "index.json").is_file():
            for r in library():
                if not (LIBRARY / r["name"] / "SKILL.md").is_file():
                    bad.append(f"library: missing {r['name']}/SKILL.md")
            if not lib_find("مونتاج فيديو", 3, hide_installed=False):
                bad.append("library: Arabic search returned nothing")
        if CATALOG.is_file():
            cat = (jload(CATALOG, {}) or {}).get("skills", [])
            if len(cat) < 100 or any(re.search(r"[A-Za-z]:[\/]+Users[\/]", r.get("description", "")) for r in cat):
                bad.append(f"installed catalog: {len(cat)} rows or a user path leaked")
        if classify(__file__) != "python" or classify(str(ROOT)) not in ("skill-package", "repo"):
            bad.append("classify")
        idx = jload(MIND / "chats_index.json", {}) or {}
        nch = len(list((MIND / "chats").glob("[cst]*.md")))
        public = (MIND / "PUBLIC_EDITION.md").is_file() and not nch   # public repo: the owner's chats memory is left out on purpose
        if public:
            pass
        elif not nch or idx.get("count") != nch or any(not (MIND / "chats" / f"{c['id']}.md").is_file() for c in idx.get("convs", [])):
            bad.append(f"chats memory: index {idx.get('count')} vs files {nch}")
        try:
            C = chats_mod()
            for cq, want in ({} if public else (jload(MIND / "chats_tests.json", {}) or {})).items():
                if cq.startswith("_"):
                    continue
                h = C.search(cq, limit=1)
                if not h or h[0]["id"] != want:
                    bad.append(f"chats «{cq}» → {h[0]['id'] if h else None}, expected {want}")
            blind = [] if public else (jload(MIND / "chats_eval_blind.json", {}) or {}).get("items", [])
            if blind:                       # 30 questions written by an agent that never saw the search code
                t3 = sum(1 for it in blind if it["id"] in [h["id"] for h in C.search(it["q"], limit=3)])
                if t3 < 0.85 * len(blind):
                    bad.append(f"blind chats eval: top-3 {t3}/{len(blind)} < 85%")
        except Exception as e:
            bad.append(f"rd_chats: {e}")
        for sk, sc in (("reference-lock", "reflock.py"), ("sync-guard", "syncguard.py"), ("hypit-run", "hypit_rd.py"), ("insta-reader", "insta.py"), ("arena-gate", "arena_gate.py"), ("golden-bird", "gold.py"), ("doc-reader", "docmd.py"), ("maven-toon-bridge", "mtoon.py")):    # v2.9.1: exact reference + caption sync guards
            gp = ROOT / "engine" / "skills" / sk / "scripts" / sc
            if gp.is_file():
                r = subprocess.run([sys.executable, "-X", "utf8", str(gp), "selftest"], capture_output=True, text=True, encoding="utf-8", errors="replace",
                                   timeout=300, env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
                if r.returncode:
                    bad.append(f"{sk}: " + (r.stdout.strip().splitlines() or [r.stderr.strip()[-200:] or "?"])[-1][:200])
        try:                                     # v3.4: the fusion brain answers in-process (counts, brief, depth, check)
            bad += fusion_mod().problems(rd_self())
        except Exception as e:
            bad.append(f"fusion: {type(e).__name__}: {str(e)[:160]}")
        try:                                     # v3.4: plan shows the thinking block, and still works when a copy has no fusion data
            import tempfile
            with tempfile.TemporaryDirectory(prefix="rd-plan-") as tmp:      # plan bumps lesson hits: keep them out of the owner's memory
                broken = Path(tmp) / "broken"                                 # a copy whose fusion module does not even import
                (broken / "fusion").mkdir(parents=True)
                (broken / "fusion" / "index.json").write_text("{}", encoding="utf-8")
                (broken / "dragon_fusion.py").write_text("def broken(:\n", encoding="utf-8")
                for case, extra, want in (("with", {}, "🧠 سلّم التفكير"), ("off", {"RD_NO_FUSION": "1"}, None),
                                          ("broken", {"GOLDEN_FUSION_PY": str(broken / "dragon_fusion.py")}, "سلّم التفكير ماطلعش")):
                    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", RED_DRAGON_HOME=str(Path(tmp) / "mem"), **extra)
                    r = subprocess.run([sys.executable, "-X", "utf8", str(Path(__file__).resolve()), "plan", "اعمل ريل 9:16 من الفيديو ده على اغنية"],
                                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300, env=env)
                    shown = "🧠 سلّم التفكير" in r.stdout
                    ok = not r.returncode and "②" in r.stdout and (want in r.stdout if want else not shown and "ماطلعش" not in r.stdout)
                    if not ok:
                        bad.append(f"plan ({case} fusion): rc={r.returncode}, thinking block={shown}, {(r.stderr.strip().splitlines() or [''])[-1][:120]}")
        except Exception as e:
            bad.append(f"plan + fusion test: {type(e).__name__}: {str(e)[:160]}")
        if (ROOT / "agents").is_dir():          # v2.15: subagent files must stay valid
            r = subprocess.run([sys.executable, "-X", "utf8", str(ROOT / "scripts" / "rd_agents.py"), "check"], capture_output=True, text=True, encoding="utf-8", errors="replace")
            if r.returncode:
                bad.append("agents: " + r.stdout.strip()[:200])
        tp = ROOT / "engine" / "skills" / "planning-mind" / "scripts" / "think.py"
        if tp.is_file():                     # v2.9: the think-and-plan pipeline must still catch the known mistakes (M01: things on faces)
            r = subprocess.run([sys.executable, "-X", "utf8", str(tp), "selftest"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300,
                               env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
            if r.returncode:
                bad.append("think pipeline: " + (r.stdout.strip().splitlines() or ["?"])[-1][:200])
        gate, ev, fl = {}, MIND / "route_eval" / "route_eval2.py", jload(MIND / "route_eval" / "floor.json", {}) or {}
        if not a.quick and ev.is_file() and fl.get("floor"):     # v2.8: the blind test half may never get worse (old: no context, fresh: session topic)
            for s, extra in (("old", []), ("fresh", ["--topic"])):
                try:
                    r = subprocess.run([sys.executable, "-X", "utf8", str(ev), str(ROOT / "scripts"), "--set", s, "--split", "test", "--json", *extra], capture_output=True,
                                       text=True, encoding="utf-8", errors="replace", timeout=600, env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
                    res = json.loads(r.stdout.strip().splitlines()[-1])
                    gate[s] = {k: res[k] for k in ("n", "top1", "ok", "top3")}
                    for k, v in fl["floor"].get(s, {}).items():
                        if res[k] < v:
                            bad.append(f"route eval {s}/test: {k} {res[k]:.0%} < floor {v:.0%}")
                except Exception as e:
                    bad.append(f"route eval {s}: {type(e).__name__}: {str(e)[:160]}")
        print(json.dumps({"ok": not bad, "playbooks": len(ids), "powers": len(pids), "lessons": len(lessons()), "chats": nch, "edition": "public (no chats memory)" if public else "full",
                          "route_eval": gate or ("skipped (--quick)" if a.quick else "no floor.json"), "problems": bad}, ensure_ascii=False, indent=1))
        sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
