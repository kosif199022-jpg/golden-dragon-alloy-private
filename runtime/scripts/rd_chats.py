#!/usr/bin/env python3
"""Red Dragon — memory of every past conversation with the owner + a guard against two sessions
writing the same folder. Standard library only. Called from rd.py, or on its own:

  rd.py chats "<سؤال>"        اتكلمنا عن كده فين، اتقرر إيه، واتعمل إيه (من خلاصة كل محادثة)
  rd.py chats --list          كل المحادثات بالتاريخ
  rd.py chats --show ID       خلاصة محادثة واحدة كاملة
  rd.py files "<كلمة>"        مسارات الملفات اللي اتسلّمت في المحادثات + موجودة على الجهاز دلوقتي ولا لأ
  rd.py guard PATH [--minutes 10]   حد تاني بيكتب في المجلد ده دلوقتي؟ (ملفات بتتغيّر/بتكبر، أقفال)
  rd.py lock PATH --note "…" / rd.py unlock PATH   قفل استشاري قبل البناء في مجلد مشترك

It only reads, except lock/unlock which write one small file: PATH/.rd-lock.json."""
import json, math, os, re, socket, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHATS = ROOT / "mind" / "chats"
INDEX = ROOT / "mind" / "chats_index.json"
LOCK_NAME = ".rd-lock.json"
MEM = Path(os.environ.get("RED_DRAGON_HOME") or Path.home() / ".red-dragon")
AUTO = MEM / "chats"                                    # deltas made by --refresh (the skill folder stays read-only)
LIB = Path(os.environ.get("RED_DRAGON_CHAT_LIBRARY") or Path(os.environ.get("APPDATA") or Path.home()) / "BlackDragon" / "chat_library")

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ------------------------------------------------------------------ words (same rules as rd.py)
AR_DIAC = re.compile("[ً-ْـ]")
STOP = set("في من على عن الى إلى ده دي دا اللي عايز عاوز اعمل اعملي ممكن يا كل مع او أو و هو هي انا انت كام ايه إيه "
           "فين امتى ازاي ليه هل اللى بتاع بتاعت the a an of to for and or in on with me my this that please make do".split())
PREFIXES = ("وبال", "فبال", "وال", "فال", "بال", "كال", "لل", "ال")
# Egyptian / voice-typing words -> what the summaries actually say
SYN = {
    "اكسل": "excel xlsx", "excel": "اكسل xlsx", "فديو": "فيديو", "فيديو": "فيلم mp4", "فيلم": "فيديو mp4",
    "كتكوت": "chick فقس", "فقس": "chick كتكوت", "ديزني": "disney toon flux", "كرتون": "toon cartoon",
    "تطبيق": "app apk", "برنامج": "app exe", "مهاره": "skill", "مهارات": "skill skills",
    "تنين": "dragon", "اسود": "black", "ابيض": "white", "احمر": "red",
    "هيجز": "higgsfield", "هيجزفيلد": "higgsfield", "فيلد": "higgsfield", "هيكسفيلد": "higgsfield", "رصيد": "كريدت credit balance",
    "كريدت": "رصيد credit", "مستخرج": "extractor apk", "متصفح": "browser سحاب", "سحاب": "cloud browser",
    "تحميل": "download kosif", "حمل": "download", "بلندر": "blender", "غساله": "washer teardown",
    "كورنيش": "corniche alex اسكندريه", "اسكندريه": "alex corniche", "زيب": "zip", "مضغوط": "zip",
    "اختبارات": "tests pytest", "نسخه": "version", "مونتاج": "montage", "مونتاتج": "مونتاج montage",
    "محاكي": "teardown simulator", "محكي": "محاكي teardown", "خطوط": "fonts", "خط": "font",
    "موشن": "motion", "الوان": "palette chroma", "هويه": "identity chroma", "قوائم": "financial مالي",
    "ماليه": "financial قوائم", "مواقع": "sites links", "ريل": "reel", "ريلز": "reel", "صوت": "audio lufs",
    "تحليل": "rea analysis", "هندسه": "rea reverse", "عكسيه": "reverse rea", "نوفا": "novaplay", "novaplay": "نوفا iptv",
    # English words the owner writes in Arabic letters (voice typing) → what the summaries say
    "سكيل": "skill مهاره", "اسكيل": "skill مهاره", "سكيلز": "skill مهارات", "اسكيلات": "skill مهارات", "سكيلات": "skill مهارات",
    "كرييتف": "creative ابداع", "كريتف": "creative ابداع", "كريتيف": "creative ابداع", "كرياتيف": "creative ابداع",
    "كلينك": "kling", "كلنج": "kling", "كلينج": "kling", "كلنك": "kling",
    "ميموري": "memory ذاكره رام", "رام": "ram ذاكره", "فول": "full",
    "برومبت": "prompt برومت", "برومبتات": "prompt", "برومت": "prompt", "بروميت": "prompt",
    "ستايل": "style اسلوب", "ستايلات": "style اساليب", "فولدر": "مجلد folder", "ريبو": "repo مستودع", "مستودع": "repo github",
    "بث": "stream hls live", "لايف": "live stream", "قص": "cut trim", "قصيته": "قص cut",
    "وقع": "سقوط fall", "سقط": "سقوط", "فريم": "frame fps فريمات", "فريمات": "frame fps",
    "تيك": "tiktok", "توك": "tiktok", "تيكتوك": "tiktok", "انستا": "instagram", "يوتيوب": "youtube",
    "مطر": "rain مؤثرات", "جوي": "weather مؤثرات", "جويه": "weather مؤثرات",
    "ابديت": "update تحديث", "سيرفر": "server", "سيرفرات": "server", "اندرويد": "android apk", "بروجكت": "project مشروع",
    "ماكينه": "machine teardown", "مكنه": "ماكينه teardown", "لوجو": "logo شعار", "شعار": "logo",
    "اغنيه": "song music", "مزيكا": "music", "موسيقي": "music", "ترجمه": "subtitles captions", "كابشن": "caption",
    "فوتوشوب": "photoshop psd",
}
SUFFIXES = ("تها", "تهم", "ته", "ها", "هم", "كم", "نا", "ات", "ين", "ون", "وا", "يه", "ه", "ي")
VERB_PRE = ("بي", "بت", "بن", "هي", "هت", "هن", "ات", "ا", "ي", "ت", "ن", "ب", "ه")
AR_WORD = re.compile(r"^[؀-ۿ]+$")


def stem(w):
    """Light Egyptian/Arabic stem: «بيشطب»/«تشطب» → «شطب», «الكليشيهات»/«كليشيه» → «كليشي», «مهارات»/«مهاره» → «مهار».
    Only for Arabic words longer than 4 letters; never below 3 letters."""
    if len(w) <= 4 or not AR_WORD.match(w):
        return w
    for p in VERB_PRE:
        if w.startswith(p) and len(w) - len(p) >= 3:
            w = w[len(p):]
            break
    for _ in range(2):
        for s in SUFFIXES:
            if w.endswith(s) and len(w) - len(s) >= 3:
                w = w[:-len(s)]
                break
    return w


def norm(s):
    s = AR_DIAC.sub("", str(s).lower())
    return re.sub("[إأآا]", "ا", s).replace("ة", "ه").replace("ى", "ي").replace("ؤ", "و").replace("ئ", "ي")


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


def query_terms(q, syn_w=None):
    """[(token, weight)] — the owner's words weigh 1.0, their synonyms less."""
    syn_w = P["syn"] if syn_w is None else syn_w
    base = tokens(q)
    terms = {t: 1.0 for t in base}
    for t in base:
        for s in tokens(SYN.get(t) or SYN.get(stem(t), "")):
            terms.setdefault(s, syn_w)
    return list(terms.items())


def match(a, b):
    if a == b:
        return 2
    if min(len(a), len(b)) >= 4 and (a.startswith(b) or b.startswith(a)):
        return 1
    return 0


def best(t, bag, sbag=None, st=None):
    """2 exact · P['stem'] same light stem · 1 shared prefix (4+ letters) · 0."""
    if t in bag:
        return 2
    if sbag is not None and (st or stem(t)) in sbag:
        return P["stem"]
    if len(t) < 4:
        return 0
    return max((match(t, k) for k in bag), default=0)


# ranking knobs — tuned on HALF of a blind set (mind/chats_eval_blind.json, even items), checked on the other half
P = {"ext": 0.7, "syn": 0.6, "fz": 0.7, "stem": 1.6, "title": 0.8, "lit": 3.0, "w_doc": 1.0, "len_norm": 0.0,
     "w_line1": 1.6, "w_line2": 0.35, "rec": 0.0, "rec_state": 1.2}


# ------------------------------------------------------------------ data
def jload(p, default=None):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:
        return default


_CACHE = {}


def _lines(txt):
    """[(text, tokens, stems)] for every meaningful line."""
    out = []
    for ln in txt.splitlines():
        s = ln.strip()
        if len(s) < 4 or s.startswith("<!--"):
            continue
        tk = set(tokens(s))
        out.append((s, tk, {stem(t) for t in tk}))
    return out


def convs():
    """[{id, title, date, updated, paths, lines:[(text, tokenset)], bag}] from the skill's mind/chats/*.md
    (agent summaries) + ~/.red-dragon/chats/*.md (automatic deltas written by --refresh)."""
    if "c" in _CACHE:
        return _CACHE["c"]
    idx = {c["id"]: c for c in (jload(INDEX, {}) or {}).get("convs", [])}
    auto = (jload(AUTO / "index.json", {}) or {}).get("convs", {})
    by = {}
    for f in sorted(CHATS.glob("[cst]*.md")):
        cid, meta, txt = f.stem, idx.get(f.stem, {}), f.read_text(encoding="utf-8")
        by[cid] = {"id": cid, "title": meta.get("title") or (txt.splitlines()[0].lstrip("# ").strip() if txt else cid),
                   "date": meta.get("date", ""), "updated": meta.get("updated", ""), "paths": list(meta.get("paths", [])),
                   "lines": _lines(txt), "raw": norm(txt), "auto": False}
    for cid, meta in auto.items():
        f = AUTO / f"{cid}.md"
        if not f.is_file():
            continue
        txt = f.read_text(encoding="utf-8")
        c = by.setdefault(cid, {"id": cid, "title": meta.get("title", cid), "date": meta.get("date", ""), "updated": "",
                                "paths": [], "lines": [], "raw": "", "auto": True})
        c["lines"] += _lines(txt)
        c["raw"] += "\n" + norm(txt)
        c["updated"] = meta.get("updated") or c["updated"]
        c["paths"] = list(dict.fromkeys(meta.get("paths", []) + c["paths"]))      # newest deliverables first
    out = list(by.values())
    for c in out:
        c["bag"] = set().union(*[t for _, t, _ in c["lines"]]) if c["lines"] else set()
        c["sbag"] = {stem(t) for t in c["bag"]}
        c["tbag"] = set(tokens(c["title"]))
        c["tsbag"] = {stem(t) for t in c["tbag"]}
    _CACHE["c"] = out
    return out


# ------------------------------------------------------------------ live refresh from the app's chat library
SECRET = re.compile(r"(AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|sk-ant-[A-Za-z0-9_-]{10,}|sk-[A-Za-z0-9]{24,}|AIza[0-9A-Za-z_-]{35}|xox[baprs]-[A-Za-z0-9-]{10,}|-----BEGIN [A-Z ]*PRIVATE KEY-----)")
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE = re.compile(r"(?<![\d.])(?:\+?20|0)1[0125]\d{8}(?!\d)|(?<![\d.])(?:\+?966|0)5\d{8}(?!\d)")
_ROOTP = r"(?:[A-Za-z]:\\|~[/\\]|%[A-Z_]+%)[^`*|<>\"\n]+"
DELIVER_ANY = re.compile(_ROOTP + r"\.(?:mp4|mov|mkv|webm|zip|7z|html|xlsx|docx|pptx|pdf|apk|apks|exe|msi|wav|mp3|psd|blend|glb|jpg|jpeg|png|gif|srt|ass|md|txt|json|py)", re.I)
DELIVER_MAIN = re.compile(_ROOTP + r"\.(?:mp4|mov|mkv|webm|zip|7z|html|xlsx|docx|pptx|pdf|apk|apks|exe|msi|wav|mp3|psd|blend|glb)", re.I)
MARK = ("🧑", "🤖", "⚙", "↳", "📄")


def deliverables(text, files=()):
    """Paths with spaces (خطابة 2) are only trusted from markdown links, `code` spans and 📄 lists — never from free prose.
    From the reply: any file type. From 📄 lists (dozens of stills and scratch files): deliverable types only."""
    out = []
    for c in re.findall(r"\]\(([^)\n]+)\)", text) + re.findall(r"`([^`\n]+)`", text):
        c = c.strip()
        if DELIVER_ANY.fullmatch(c):
            out.append(c)
    out += [f.strip() for f in files if DELIVER_MAIN.fullmatch(f.strip())]
    return list(dict.fromkeys(out))


def mask(s):
    s = SECRET.sub("(سر مقنّع)", s)
    s = EMAIL.sub(lambda m: m.group(0) if m.group(0).split("@")[0] in ("noreply", "x", "ana", "temp") else "(إيميل مقنّع)", s)
    return PHONE.sub("(رقم مقنّع)", s)


def parse_library_chat(f):
    """→ {title, updated, turns:[{user, final, files}]} from one chat_library/*.md (🧑 user · 🤖 assistant · ⚙/↳ tools · 📄 files)."""
    txt = f.read_text(encoding="utf-8", errors="replace")
    lines = txt.splitlines()
    title = lines[0].lstrip("# ").strip() if lines else f.stem
    m = re.search(r"آخر تحديث (\S+?)\)", "\n".join(lines[:8]))
    turns, kind, buf = [], None, []

    def flush():
        if kind == "user":
            turns.append({"user": "\n".join(buf).replace("🧑 المستخدم:", "", 1).strip(), "bot": [], "files": []})
        elif kind == "bot" and turns:
            turns[-1]["bot"].append("\n".join(buf).lstrip("🤖").strip())
        elif kind == "files" and turns:
            turns[-1]["files"] += [p.strip() for p in "\n".join(buf).lstrip("📄").split(",") if p.strip()]

    for ln in lines:                                  # the title can wrap onto 2 lines: start at the first marker
        if ln.startswith(MARK):
            flush()
            kind = {"🧑": "user", "🤖": "bot", "📄": "files"}.get(ln[0], "tool")
            buf = [ln]
        elif kind:
            buf.append(ln)
    flush()
    for t in turns:
        t["final"] = t["bot"][-1] if t["bot"] else ""
    return {"title": title, "updated": m.group(1) if m else "", "turns": turns}


def _turn_md(n, t):
    fin = [ln.strip() for ln in t["final"].splitlines() if ln.strip()]
    head = " ".join(fin[:2])[:420]
    done = []
    take = False
    for ln in fin:                                   # keep the «اللي اتعمل» bullets: that is where paths and numbers live
        if re.search(r"اللي اتعمل|What was done", ln):
            take = True
            continue
        if take and ln.startswith(("-", "•", "*")) and len(done) < 6:
            done.append(ln[:260])
    paths = deliverables(t["final"], t["files"])[:6]
    L = [f"- **طلب {n}:** {' '.join(t['user'].split())[:300] or '(فاضي)'}", f"  - **آخر رد:** {head or '(مفيش رد لسه)'}"]
    L += [f"  {d}" for d in done]
    if paths:
        L.append("  - **ملفات:** " + " ⏐ ".join(f"`{p}`" for p in paths))
    return mask("\n".join(L)), paths


def stale(lib=None):
    """Chats in the library whose user-message count is above what the memory covers (skill summary + last refresh)."""
    lib = Path(lib or LIB)
    if not (lib / "index.md").is_file():
        return None
    idx = {c["id"]: c for c in (jload(INDEX, {}) or {}).get("convs", [])}
    auto = (jload(AUTO / "index.json", {}) or {}).get("convs", {})
    out = []
    for f in sorted(lib.glob("c*.md")):
        n = len(re.findall(r"(?m)^🧑 المستخدم", f.read_text(encoding="utf-8", errors="replace")))
        covered = max(idx.get(f.stem, {}).get("n_user", 0), auto.get(f.stem, {}).get("n_to", 0))
        if n > covered:
            out.append((f.stem, covered, n))
    return out


def refresh(lib=None, quiet=False):
    """Write ~/.red-dragon/chats/<id>.md for every chat with user messages the memory does not cover yet."""
    lib = Path(lib or LIB)
    st = stale(lib)
    if st is None:
        if not quiet:
            print(f"أرشيف المحادثات مش موجود هنا ({lib}). التحديث بيشتغل على لابتوب صاحب الشغل بس.")
        return 0
    AUTO.mkdir(parents=True, exist_ok=True)
    ai = jload(AUTO / "index.json", {}) or {}
    ai.setdefault("convs", {})
    idx = {c["id"]: c for c in (jload(INDEX, {}) or {}).get("convs", [])}
    for cid, _, n in st:
        base = idx.get(cid, {}).get("n_user", 0)
        p = parse_library_chat(lib / f"{cid}.md")
        new = p["turns"][base:]
        body, allp = [], []
        for i, t in enumerate(new, base + 1):
            md, ps = _turn_md(i, t)
            body.append(md)
            allp += ps
        d = time.strptime(cid[1:16], "%Y%m%d-%H%M%S")
        head = (f"# {p['title']}\n\n<!-- {cid} · تحديث تلقائي من أرشيف التطبيق {time.strftime('%Y-%m-%d %H:%M')} · "
                f"رسايل {base + 1}–{n} (من غير تلخيص وكيل) -->\n\n**🔄 الجديد بعد آخر خلاصة (آخر تحديث للمحادثة {p['updated']}):**\n\n")
        (AUTO / f"{cid}.md").write_text(head + "\n".join(body) + "\n", encoding="utf-8")
        ai["convs"][cid] = {"title": idx.get(cid, {}).get("title") or p["title"], "date": time.strftime("%Y-%m-%d %H:%M", d),
                            "updated": p["updated"], "paths": list(dict.fromkeys(reversed(allp)))[:20], "n_from": base + 1, "n_to": n}
    ai["refreshed"] = time.time()
    ai["library_mtime"] = (lib / "index.md").stat().st_mtime
    (AUTO / "index.json").write_text(json.dumps(ai, ensure_ascii=False, indent=1), encoding="utf-8")
    _CACHE.clear()
    if not quiet:
        print(f"🔄 اتحدّث {len(st)} محادثة من الأرشيف ← {AUTO}" + ("".join(f"\n   • {c}: رسايل {b + 1}–{n}" for c, b, n in st) if st else " (مفيش جديد)"))
    return len(st)


def auto_refresh():
    """Before a search: refresh only when the app's library changed since the last refresh (cheap check)."""
    try:
        if not (LIB / "index.md").is_file():
            return 0
        ai = jload(AUTO / "index.json", {}) or {}
        if ai.get("library_mtime") == (LIB / "index.md").stat().st_mtime:
            return 0
        return refresh(quiet=True)
    except Exception:
        return 0


def banner():
    """One line for rd.py start/doctor: memory size + freshness."""
    n = len(list(CHATS.glob("[cst]*.md")))
    st = stale()
    extra = ""
    if st:
        extra = f" · ⚠ {len(st)} محادثة فيها رسايل أحدث من الذاكرة: rd.py chats --refresh (أو بتتحدّث لوحدها مع أول بحث)"
    elif st == []:
        extra = " · محدّثة مع أرشيف التطبيق ✓"
    return f"🗂 ذاكرة {n} محادثة{extra}"


def deletes(w):
    return {w[:i] + w[i + 1:] for i in range(len(w))}


def vocab(cs):
    """token → in how many chats, and a delete-one index so a one-letter typo («اكسيل», «مونتاتج») still finds the word."""
    if "v" in _CACHE:
        return _CACHE["v"]
    df, dix = {}, {}
    for c in cs:
        for t in c["bag"]:
            df[t] = df.get(t, 0) + 1
    for t in df:
        if len(t) >= 4:
            for d in deletes(t):
                dix.setdefault(d, set()).add(t)
    _CACHE["v"] = (df, dix)
    return df, dix


def fuzzy(t, df, dix, k=2):
    """Known words at edit distance 1 from t (insert / delete / substitute one letter), most common first."""
    if len(t) < 4 or t in df:
        return []
    cand = set(dix.get(t, ()))                               # t is missing a letter
    for d in deletes(t):
        if d in df:
            cand.add(d)                                      # t has an extra letter
        cand |= dix.get(d, set())                            # one letter substituted
    cand.discard(t)
    return sorted(cand, key=lambda w: -df.get(w, 0))[:k]


def search(q, limit=3, per=4, min_terms=1):
    cs = convs()
    if not cs:
        return []
    terms = query_terms(q)
    df_, dix = vocab(cs)
    have = {t for t, _ in terms}
    for t, w in list(terms):
        for f in fuzzy(t, df_, dix):
            if f not in have:
                terms.append((f, w * P["fz"]))
                have.add(f)
    stems = {t: stem(t) for t, _ in terms}
    n = len(cs)
    idf = {}
    for t, _ in terms:
        d = sum(1 for c in cs if best(t, c["bag"], c["sbag"], stems[t]) > 0)
        idf[t] = math.log((n + 1) / (d + 0.5)) if d else 0.0
    when = lambda c: ((c.get("date") or "")[:16].replace("T", " "), c["id"])   # v2.4: by start time, not id (ids now start with c/t/s)
    order = {c["id"]: i / max(1, n - 1) for i, c in enumerate(sorted(cs, key=when))}   # 0 = oldest, 1 = newest
    avg = sum(len(c["bag"]) for c in cs) / n or 1
    nq = norm(q)
    # literal identifiers (versions «1.2» / «v1990.10.0», file names, ids) are the strongest evidence when verbatim
    literals = [x for x in re.findall(r"[a-z0-9_][a-z0-9_.\-]{2,}", nq) if re.search(r"\d\.\d|[_-]|\d{3,}", x)]
    # questions about the current state («دلوقتي», «آخر», «الحالي») → the newest chat is the truth
    state = bool(re.search(r"(^|\s)(دلوقتي|دلوقت|حاليا|الحالي|اخر|الاخير|الاحدث|احدث|لسه|now|latest|current)(\s|$)", nq))
    top_idf = max(idf.values(), default=1.0) or 1.0

    def lscore(tk, sk):
        return sum(w * idf[t] * best(t, tk, sk, stems[t]) for t, w in terms)

    ranked = []
    for c in cs:
        doc = sum(w * idf[t] * best(t, c["bag"], c["sbag"], stems[t]) for t, w in terms)
        doc += P["title"] * sum(w * idf[t] * best(t, c["tbag"], c["tsbag"], stems[t]) for t, w in terms)
        hit_terms = sum(1 for t, _ in terms if idf[t] > 0 and best(t, c["bag"], c["sbag"], stems[t]))
        if doc <= 0 or hit_terms < min_terms:
            continue
        doc /= 1 + P["len_norm"] * (len(c["bag"]) / avg - 1)          # long chats match common words by sheer size
        ls = sorted((lscore(tk, sk) for _, tk, sk in c["lines"]), reverse=True)[:2] + [0, 0]
        s = P["w_doc"] * doc + P["w_line1"] * ls[0] + P["w_line2"] * ls[1]   # one line that holds the words together
        s += sum(P["lit"] * top_idf for x in literals if x in c["raw"])
        s *= 1 + (P["rec_state"] if state else P["rec"]) * order[c["id"]]
        if not c["id"].startswith("c"):
            s *= P.get("ext", 1.0)       # v2.4: project threads / cloud sessions are secondary to the laptop app chats (verified paths)
        ranked.append((s, ls[0], c))
    ranked.sort(key=lambda x: -x[0])
    if state and ranked:
        # «كام دلوقتي»: among chats that state the fact in ONE line, the newest one wins
        top = max(lb for _, lb, _ in ranked[:10])
        fresh = sorted([x for x in ranked[:10] if x[1] >= 0.6 * top], key=lambda x: when(x[2]), reverse=True)
        ranked = fresh + [x for x in ranked if x not in fresh]
    res = []
    for s, _, c in ranked[:limit]:
        ls = []
        for i, (txt, tk, sk) in enumerate(c["lines"]):
            v = lscore(tk, sk)
            if v > 0 and not txt.startswith("#"):
                ls.append((v, i, txt))
        ls.sort(key=lambda x: (-x[0], x[1]))
        res.append({"score": round(s, 2), "id": c["id"], "title": c["title"], "date": c["date"], "updated": c["updated"],
                    "lines": [t for _, _, t in sorted(ls[:per], key=lambda x: x[1])], "paths": c["paths"]})
    return res


# ------------------------------------------------------------------ paths
def is_owner_pc():
    return (Path.home() / "OneDrive" / "Desktop" / "التنين الأسود").exists() or (Path.home() / "OneDrive" / "Desktop" / "مهارات" / "التنين الأسود").exists() or (Path.home() / "re-tools" / "retool.py").exists()


def resolve(p):
    p = p.strip().rstrip(".,،؛)").strip()
    p = os.path.expandvars(os.path.expanduser(p.replace("%USERPROFILE%", str(Path.home()))))
    return Path(p)


def exists(p):
    if any(ch in p for ch in "*?<>|") or "…" in p or "..." in p:
        return None
    try:
        return resolve(p).exists()
    except (OSError, ValueError):
        return None


def mark(p):
    if not is_owner_pc():
        return "·"
    e = exists(p)
    return "✓" if e else ("✗" if e is False else "?")


# ------------------------------------------------------------------ guard / lock
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".pytest_cache", ".venv", "venv"}
SNAPS = Path(os.environ.get("RED_DRAGON_HOME") or Path.home() / ".red-dragon") / "guard"


def touched(st):
    """Copies that keep the old modified time (copy2, robocopy, tar) still get a NEW creation time on Windows
    (and a new change time on Linux) — so the newest of the two is when the file really landed here.
    Found the hard way: 2,055 files copied with 09:54 timestamps at 13:50 were invisible to an mtime-only guard."""
    return max(st.st_mtime, st.st_ctime)


def walk_files(root, cap=60000):
    n = 0
    for dp, dn, fn in os.walk(root):
        dn[:] = [d for d in dn if d not in SKIP_DIRS]
        for name in fn:
            if name == LOCK_NAME:
                continue
            n += 1
            if n > cap:
                return
            f = Path(dp) / name
            try:
                yield f, f.stat()
            except OSError:
                continue


def recent_files(root, minutes=10, cap=40000):
    now = time.time()
    seen, recent = 0, []
    for f, st in walk_files(root, cap):
        seen += 1
        age = now - touched(st)
        if age < minutes * 60:
            recent.append((age, st.st_size, f))
    recent.sort(key=lambda x: x[0])
    return recent, seen, seen >= cap


def snap_file(root):
    import hashlib
    return SNAPS / (hashlib.sha1(str(Path(root).resolve()).lower().encode("utf-8")).hexdigest()[:16] + ".json")


def snapshot(root):
    return {f.relative_to(root).as_posix(): [st.st_size, int(st.st_mtime)] for f, st in walk_files(root)}


def snap_save(root):
    SNAPS.mkdir(parents=True, exist_ok=True)
    s = snapshot(root)
    snap_file(root).write_text(json.dumps({"root": str(root), "ts": time.time(), "files": s}, ensure_ascii=False), encoding="utf-8")
    print(f"📸 لقطة اتحفظت: {len(s)} ملف ← {snap_file(root)}\n   بعدين قبل ما تكتب: rd.py guard PATH --diff (أي ملف جديد أو اتشال أو اتغيّر حجمه/وقته = حد اشتغل هنا)")


def snap_diff(root):
    old = jload(snap_file(root), None)
    if not old:
        print("مفيش لقطة للمجلد ده. خد واحدة الأول: rd.py guard PATH --save")
        return None
    cur = snapshot(root)
    o = old["files"]
    new = sorted(set(cur) - set(o))
    gone = sorted(set(o) - set(cur))
    chg = sorted(k for k in set(cur) & set(o) if cur[k] != o[k])
    age = int((time.time() - old["ts"]) // 60)
    print(f"🔍 مقارنة باللقطة اللي من {age} د: جديد {len(new)} · اتشال {len(gone)} · اتغيّر {len(chg)}")
    for lab, xs in (("جديد", new), ("اتشال", gone), ("اتغيّر", chg)):
        for x in xs[:6]:
            print(f"   {lab}: {x}")
    return bool(new or gone or chg)


def locks_near(root):
    out = []
    p = Path(root).resolve()
    for d in [p] + list(p.parents)[:3]:
        f = d / LOCK_NAME
        if f.is_file():
            out.append((f, jload(f, {}) or {}))
    return out


def guard(path, minutes=10, sample=3.0, save=False, diff=False):
    root = Path(path).expanduser()
    if not root.exists():
        raise SystemExit(f"المسار مش موجود: {root}")
    target = root if root.is_dir() else root.parent
    if save:
        snap_save(target)
        return "free"
    if diff:
        changed = snap_diff(target)
        if changed:
            print("   ✋ الحكم: المجلد اتغيّر من ساعة اللقطة. حد تاني اشتغل هنا: ماتكتبش فوق شغله؛ ابني فوق الموجود دلوقتي.")
            return "busy"
        if changed is False:
            print("   ✅ الحكم: زي ما هو من ساعة اللقطة.")
            return "free"
    recent, seen, capped = recent_files(target, minutes)
    growing = []
    if recent:
        before = {f: sz for _, sz, f in recent[:25]}
        time.sleep(sample)
        for f, sz in before.items():
            try:
                now_sz = f.stat().st_size
            except OSError:
                continue
            if now_sz != sz:
                growing.append((f, sz, now_sz))
    lk = locks_near(target)
    live_locks = [(f, d) for f, d in lk if time.time() - d.get("ts", 0) < 6 * 3600]
    print(f"🛡 حارس المجلد: {target}")
    print(f"   اتفحص {seen}{'+ (وقف عند الحد)' if capped else ''} ملف · اتغيّر في آخر {minutes} دقيقة: {len(recent)} · بيكبر دلوقتي: {len(growing)} · أقفال: {len(live_locks)}")
    for f, a, b in growing[:8]:
        print(f"   ⚠ بيتكتب الآن: {f}  ({a:,} → {b:,} بايت في {sample:.0f} ث)")
    for age, sz, f in recent[:10]:
        print(f"   • من {int(age // 60)}د {int(age % 60)}ث  {f}")
    for f, d in live_locks:
        print(f"   🔒 قفل: {d.get('by', '?')} على {d.get('host', '?')} من {int((time.time() - d.get('ts', 0)) // 60)} د — {d.get('note', '')}  ({f})")
    if growing or live_locks:
        verdict = "busy"
        print("   ✋ الحكم: فيه حد تاني شغال هنا. ماتكتبش فوقه: اقرا بس، واشتغل في مجلد staging، وكمّل لما يقف (guard تاني) أو بعد موافقة صاحب الشغل.")
    elif recent:
        verdict = "recent"
        print("   ⚠ الحكم: فيه تعديلات حديثة. لو مش إنت اللي عملتها، استنى دقيقتين وشغّل guard تاني قبل ما تكتب.")
    else:
        verdict = "free"
        print("   ✅ الحكم: المجلد هادي. خد قفل قبل البناء: rd.py lock PATH --note \"…\"")
    return verdict


def who(by=""):
    """A stable name for this session: --by, else $RED_DRAGON_SESSION, else user@host."""
    return by or os.environ.get("RED_DRAGON_SESSION") or f"{os.environ.get('USERNAME') or os.environ.get('USER') or 'claude'}@{socket.gethostname()}"


def lock(path, note="", by=""):
    d = Path(path).expanduser()
    d.mkdir(parents=True, exist_ok=True)
    f = d / LOCK_NAME
    me = who(by)
    old = jload(f, {}) if f.is_file() else {}
    if old and time.time() - old.get("ts", 0) < 6 * 3600 and old.get("by") != me:
        print(f"⚠ فيه قفل موجود من «{old.get('by')}» ({old.get('note', '')}). مااتاخدش قفل جديد.")
        return False
    f.write_text(json.dumps({"by": me, "host": socket.gethostname(), "ts": time.time(),
                             "started": time.strftime("%Y-%m-%dT%H:%M:%S"), "note": note}, ensure_ascii=False), encoding="utf-8")
    print(f"🔒 اتاخد قفل باسم «{me}»: {f}")
    return True


def unlock(path, force=False, by=""):
    f = Path(path).expanduser() / LOCK_NAME
    if not f.is_file():
        print("مفيش قفل.")
        return
    d = jload(f, {}) or {}
    if not force and d.get("by") != who(by):
        print(f"القفل ده بتاع «{d.get('by')}». لو متأكد إنه خلص: unlock --force")
        return
    f.unlink()
    print(f"🔓 القفل اتشال: {f}")


# ------------------------------------------------------------------ printing
def print_hits(hits, show_paths=True):
    if not hits:
        print("مفيش محادثة اتكلمت عن كده في الذاكرة (mind/chats). جرّب كلمات تانية، أو دوّر في الأرشيف الكامل:")
        print("  %APPDATA%\\BlackDragon\\chat_library\\*.md  (على لابتوب صاحب الشغل)")
        return
    for h in hits:
        upd = f" · آخر تحديث {h['updated']}" if h.get("updated") and h["updated"] != h["date"] else ""
        print(f"### {h['title']}  ({h['date']}{upd}) — {h['id']}")
        for ln in h["lines"]:
            print(f"   {ln[:400]}")
        if show_paths and h["paths"]:
            print("   📁 " + " ⏐ ".join(f"{mark(p)} {p}" for p in h["paths"][:4]))
        print()


def cmd_chats(q=None, list_all=False, show=None, as_json=False, do_refresh=False):
    if do_refresh:
        refresh()
        if not q:
            return
    else:
        auto_refresh()
    if show:
        f, a = CHATS / f"{show}.md", AUTO / f"{show}.md"
        if not f.is_file() and not a.is_file():
            raise SystemExit(f"مفيش محادثة بالـ id ده: {show}  (rd.py chats --list)")
        print("\n\n".join(x.read_text(encoding="utf-8") for x in (f, a) if x.is_file()))
        return
    if list_all or not q:
        cs = sorted(convs(), key=lambda c: ((c.get("date") or "")[:16].replace("T", " "), c["id"]), reverse=True)
        print(f"🗂 ذاكرة المحادثات: {len(cs)} محادثة (الأحدث فوق، 🔄 = فيها تحديث تلقائي). خلاصة كل واحدة: rd.py chats --show ID")
        auto = (jload(AUTO / "index.json", {}) or {}).get("convs", {})
        for c in cs:
            print(f"  {c['id']}  {c['date'][:16]:<16} {'🔄' if c['id'] in auto else '  '} {c['title'][:90]}")
        return
    hits = search(q)
    if as_json:
        print(json.dumps(hits, ensure_ascii=False, indent=1))
    else:
        print_hits(hits)


def cmd_files(q, as_json=False):
    auto_refresh()
    hits = search(q, limit=4, per=0) if q else []
    rows = []
    for h in hits:
        for p in h["paths"]:
            rows.append({"path": p, "exists": exists(p) if is_owner_pc() else None, "chat": h["id"], "title": h["title"], "date": h["date"]})
    if q:   # keep paths that themselves mention the query words first
        qt = [t for t, _ in query_terms(q)]
        rows.sort(key=lambda r: -sum(best(t, set(tokens(r["path"]))) for t in qt))
    if as_json:
        print(json.dumps(rows, ensure_ascii=False, indent=1))
        return
    if not rows:
        print("مالقيتش مسار مطابق في ذاكرة المحادثات. جرّب: rd.py chats \"<نفس الكلام>\"")
        return
    print("📁 الملفات من المحادثات (✓ موجود دلوقتي · ✗ اتنقل أو اتمسح · ? مسار مش كامل · · مش على لابتوب صاحب الشغل)")
    for r in rows[:14]:
        e = "·" if r["exists"] is None and not is_owner_pc() else ("✓" if r["exists"] else ("✗" if r["exists"] is False else "?"))
        print(f"  {e} {r['path']}\n      ← {r['title'][:70]} ({r['date'][:10]}, {r['chat']})")


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(prog="rd_chats.py")
    sub = ap.add_subparsers(dest="cmd")
    s = sub.add_parser("chats"); s.add_argument("q", nargs="?"); s.add_argument("--list", action="store_true"); s.add_argument("--show"); s.add_argument("--json", action="store_true")
    s.add_argument("--refresh", action="store_true", help="اقرا أرشيف التطبيق وضيف الرسايل الجديدة للذاكرة")
    s = sub.add_parser("files"); s.add_argument("q", nargs="?", default=""); s.add_argument("--json", action="store_true")
    s = sub.add_parser("guard"); s.add_argument("path"); s.add_argument("--minutes", type=float, default=10)
    s.add_argument("--save", action="store_true", help="خد لقطة للمجلد"); s.add_argument("--diff", action="store_true", help="قارن باللقطة")
    s = sub.add_parser("lock"); s.add_argument("path"); s.add_argument("--note", default=""); s.add_argument("--by", default="")
    s = sub.add_parser("unlock"); s.add_argument("path"); s.add_argument("--force", action="store_true"); s.add_argument("--by", default="")
    a = ap.parse_args(argv)
    if a.cmd == "chats":
        cmd_chats(a.q, a.list, a.show, a.json, a.refresh)
    elif a.cmd == "files":
        cmd_files(a.q, a.json)
    elif a.cmd == "guard":
        sys.exit(0 if guard(a.path, a.minutes, save=a.save, diff=a.diff) == "free" else 3)
    elif a.cmd == "lock":
        sys.exit(0 if lock(a.path, a.note, a.by) else 3)
    elif a.cmd == "unlock":
        unlock(a.path, a.force, a.by)
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
