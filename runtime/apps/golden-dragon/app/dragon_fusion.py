"""dragon_fusion.py — «التنين الذهبي» (Golden Dragon): one fused index of everything this PC can do, and a router.

  units    every skill in ~/.claude/skills (scanned statically), the app's own tools, the Black Dragon engines, the
           studio programs and motion libraries (Golden Bird catalogs), programs on the PATH, local AI repos, the
           reverse-engineering toolbox, MCP servers and the analysed repos: one record each (what, how to call it,
           cost, status, warnings).
  recipes  fused pipelines: ordered steps, each naming the skills to read, the units that execute it and the gate that
           proves it worked. Every id a recipe names was checked when the index was built (forge/build_fusion.py).
  route    a request (Arabic or English) -> the best recipe(s) + the strongest single units, approvals and warnings.
  doctor   live check of this PC now: programs, homes, skills added or removed since the index was built.
  discover walk the folders the owner works in (gd_discover.py) and add what is there NOW to the same index as pc-*
           units: skills outside ~/.claude/skills, Claude plugins, MCP servers, programs and shortcuts, scripts, tool
           folders, repos and skill archives. The list and the folders to walk live in %APPDATA%\\GoldenDragon only.

  brief    before a task: the request as understood (Red Dragon decoding), its depth (L0-L3), the intent sheet to fill,
           three real alternatives, a pre-mortem from the owner's own lessons, the gates, and 2-3 thinking tools from
           the thinkers' toolkit (fusion\\thinking.json: Polya, Kahneman, Klein, Heuer, Popper, Munger, Tetlock...).
           check after: a deterministic self-critique of the draft answer against the request (path first, evidence
           for every «done», calibration, approvals, coverage of the request's words), then the thinkers' critic
           questions to answer with evidence from the draft.

CLI (the subscription mode runs commands instead of app tools):
  python -X utf8 dragon_fusion.py brief "..." | route "..." | find "..." [--kind K] [--limit N] | show ID | recipes
                                  | doctor | stats | lessons "..." | check --request "..." --draft FILE|-
                                  | discover | local [KIND] | think ["سبيل"]
  think    «سبل التفكير» (من كتب Kahneman وGreetham وJaynes والمسرحية والـ IFRS): الخيال، العميق، الإبداعي، المنطق والاحتمال،
           خطوة بخطوة، التحليل، القرار. بدون كلمة = خريطة السبل؛ بكلمة = خطوات أدوات السبيل وسؤال الناقد بتاعها.
Standard library only. Data: .\\fusion\\index.json, recipes.json, lessons.json (made by forge\\build_fusion.py).
"""
import bisect
import json
import math
import os
import re
import shutil
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = Path(os.environ.get("GOLDEN_FUSION_DATA") or (HERE / "fusion"))
SKILLS_DIR = Path(os.environ.get("GOLDEN_SKILLS_DIR") or (Path.home() / ".claude" / "skills"))
K1, B = 1.4, 0.72
KIND_AR = {"skill": "مهارة", "tool": "أداة في التطبيق", "engine": "محرك تنين", "studio": "برنامج استوديو", "lib": "مكتبة",
           "program": "برنامج على الجهاز", "local-ai": "موديل محلي", "re": "أداة تحليل", "mcp": "خادم MCP", "repo": "مستودع",
           "playbook": "playbook التنين الأحمر", "cmd": "أمر التنين الأحمر", "power": "أداة سوبر باور",
           "pc-skill": "مهارة على الجهاز", "pc-plugin": "إضافة Claude", "pc-mcp": "خادم MCP على الجهاز", "pc-app": "برنامج/اختصار",
           "pc-script": "سكربت", "pc-tool": "فولدر أداة", "pc-repo": "مستودع على الجهاز", "pc-pack": "أرشيف مهارة"}
STATUS_AR = {"ok": "✓", "older": "إصدار أقدم", "partial": "ناقصها ملفات", "missing": "مش موجود", "reference": "مرجع",
             "needs-setup": "يحتاج تجهيز", "local": "على الجهاز", "copy": "نسخة برّه المتثبّت", "archive": "مضغوط/مش متثبّت"}
PENALTY = {"older": 0.15, "missing": 0.6, "partial": 0.85, "local": 0.9, "copy": 0.5, "archive": 0.45}
PC_KINDS = ("pc-skill", "pc-plugin", "pc-mcp", "pc-app", "pc-tool", "pc-script", "pc-repo", "pc-pack")

try:                                          # «discover»: what this PC has beyond the build-time index (local catalog)
    import gd_discover as _gdd
except Exception:
    _gdd = None

try:                                          # the Golden Bird's Arabic-aware tokens (normalisation, synonyms, «ال» prefixes)
    import golden_tools as _gt
    _norm, _qtokens, _ar_stem = _gt.norm, _gt._tokens, _gt._stem
except Exception:                             # standalone copy: the same normalisation without the synonyms
    _AR = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ة": "ه", "ى": "ي"})

    def _norm(t):
        t = re.sub(r"[ً-ٰـ]", "", str(t or "").lower()).translate(_AR)
        return re.sub(r"\s+", " ", t).strip()

    def _ar_stem(w):
        for p in ("وبال", "وال", "بال", "فال", "كال", "لل", "ال"):
            if w.startswith(p) and len(w) - len(p) >= 3:
                return w[len(p):]
        return w

    def _qtokens(q):
        return [w for w in re.split(r"[\s,،/|+]+", _norm(q)) if len(w) > 1]


def _stem(w):
    """Light stemming on both sides: Arabic article/prefix off, a few English suffixes off (editing -> edit)."""
    w = _ar_stem(w)
    if w.isascii() and len(w) > 4:
        for suf in ("ings", "ing", "ies", "ed", "es", "s"):
            if w.endswith(suf) and len(w) - len(suf) >= 3 and not w.endswith("ss"):
                return w[: -len(suf)] + ("y" if suf == "ies" else "")
    return w


# Function words of Egyptian/MSA Arabic and English: on the owner's real requests they matched recipes by accident
# («الموجود» sent «حدّث التطبيق» to the reel recipe). Normalised like the text (ة->ه, ى->ي, أ->ا).
STOP = set("""
عايز عاوز عايزه عاوزه اعمل اعملي عمل ده دي دا دول دى في فى من على علي عن الى الي لو مش مو اللي الي كل بس ايه اية ازاي ليه
هو هي انا انت انتي احنا هم موجود موجوده يكون تكون يبقي تبقي ممكن كده كدا برضه برضو خلاص يعني طيب عشان علشان لان
او ولا وال مع كمان تاني بتاع بتاعي بتاعه بتاعت حاجه حاجات شويه اوي جدا هنا هناك دلوقتي ما لا لم لن قد انه انها
the a an to of in for and or is are be this that it its with on my me i you your we our can please do does make want need
from at by as into about it's just also all any some
""".split())


def _words(text):
    return [s for s in (_stem(w) for w in re.findall(r"[^\W_]+", _norm(text)) if len(w) > 1) if s not in STOP]


def query_tokens(q):
    out = []
    for t in _qtokens(q):
        for w in _words(t):
            out.append(w)
            if len(w) >= 5 and w.endswith("ش") and not w.isascii():
                core = w[2:-1] if w.startswith("ما") else w[:-1]
                if len(core) >= 3:
                    out.append(_stem(core))
    return list(dict.fromkeys(out))


class _BM25:
    """BM25 over weighted fields, with prefix expansion for query words of 4+ letters (anim -> animation)."""

    def __init__(self, docs):
        self.post, df, self.len = defaultdict(list), Counter(), []
        for i, fields in enumerate(docs):
            c = Counter()
            for text, w in fields:
                for t in _words(text):
                    c[t] += w
            self.len.append(sum(c.values()) or 1.0)
            for t, f in c.items():
                self.post[t].append((i, f))
            df.update(c.keys())
        self.n = len(docs)
        self.avg = sum(self.len) / max(1, self.n)
        self.idf = {t: math.log(1 + (self.n - k + 0.5) / (k + 0.5)) for t, k in df.items()}
        self.vocab = sorted(self.idf)

    def _expand(self, q):
        hits = [(q, 1.0)] if q in self.idf else []
        if len(q) >= 4:
            i = bisect.bisect_left(self.vocab, q)
            while i < len(self.vocab) and self.vocab[i].startswith(q) and len(hits) < 40:
                if self.vocab[i] != q:
                    hits.append((self.vocab[i], 0.7))
                i += 1
        return hits

    def scores(self, qtoks):
        out = [0.0] * self.n
        for q in qtoks:
            for t, part in self._expand(q):
                idf = self.idf[t]
                for i, f in self.post[t]:
                    out[i] += part * idf * f * (K1 + 1) / (f + K1 * (1 - B + B * self.len[i] / self.avg))
        return out

    def hits(self, qtoks):
        """How many DIFFERENT query words each document matched (exact or by prefix)."""
        out = [0] * self.n
        for q in qtoks:
            seen = set()
            for t, _ in self._expand(q):
                seen.update(i for i, _ in self.post[t])
            for i in seen:
                out[i] += 1
        return out


# ---------------------------------------------------------------- data
_cache = {}


def _load(name, default=None):
    p = DATA / name
    if not p.is_file():
        if default is not None:
            return default
        raise FileNotFoundError(f"فهرس التنين الذهبي مش موجود: {p}")
    return json.loads(p.read_text(encoding="utf-8"))


def index():
    if "index" not in _cache:
        _cache["index"] = _load("index.json")
    return _cache["index"]


def local():
    """The local catalog (gd_discover): {"units": [...], "generated": ...}. Off with GOLDEN_NO_LOCAL=1 (the tests)."""
    if "local" not in _cache:
        if _gdd is None or os.environ.get("GOLDEN_NO_LOCAL"):
            _cache["local"] = {"units": [], "generated": "", "off": True}
        else:
            _cache["local"] = _gdd.load([u["name"] for u in index()["units"] if u["kind"] == "skill"])
    return _cache["local"]


def units():
    """The build-time index, then every pc-* unit the last discover found (never one that shadows an index id)."""
    if "units" not in _cache:
        base = index()["units"]
        ids = {u["id"] for u in base}
        _cache["units"] = base + [u for u in local().get("units") or [] if u.get("id") not in ids]
    return _cache["units"]


def discover():
    """Walk the PC again now and reload: -> the new local catalog."""
    if _gdd is None:
        raise FileNotFoundError("gd_discover.py مش موجود جنب dragon_fusion.py")
    data = _gdd.scan([u["name"] for u in index()["units"] if u["kind"] == "skill"])
    for k in ("local", "units", "by_id", "uix"):
        _cache.pop(k, None)
    return data


def recipes():
    if "recipes" not in _cache:
        _cache["recipes"] = _load("recipes.json")
    return _cache["recipes"]


def lessons():
    if "lessons" not in _cache:
        _cache["lessons"] = _load("lessons.json", [])
    return _cache["lessons"]


def by_id():
    if "by_id" not in _cache:
        _cache["by_id"] = {u["id"]: u for u in units()}
    return _cache["by_id"]


def _unit_index():
    if "uix" not in _cache:
        _cache["uix"] = _BM25([[(u["name"], 3.0), (u["id"].split(":", 1)[-1].replace("-", " "), 2.0),
                                (" ".join(u.get("keywords") or []), 2.0), (u.get("family", ""), 1.2),
                                (u.get("what", ""), 1.0), (u.get("what_ar", ""), 1.0)] for u in units()])
    return _cache["uix"]


def _recipe_index():
    if "rix" not in _cache:
        docs = []
        for r in recipes():
            names = " ".join(i.split(":", 1)[-1].replace("-", " ") for s in r["steps"] for i in s.get("read", []) + s.get("use", []))
            docs.append([(r["title_ar"], 3.0), (" ".join(r["when"]), 3.0), (" ".join(r.get("tags", [])), 2.5),
                         (r.get("deliver_ar", ""), 0.5), (" ".join(s["do_ar"] for s in r["steps"]), 0.5), (names, 0.4)])
        _cache["rix"] = _BM25(docs)
    return _cache["rix"]


def resolve(ident):
    """'skill:video-use', 'video-use' or 'engine:toon' -> unit. A bare name prefers a skill, then any kind."""
    key = (ident or "").strip()
    m = by_id()
    if key in m:
        return m[key]
    low = key.lower()
    for kind in ("skill", "tool", "engine", "studio", "lib", "program", "local-ai", "re", "mcp", "repo", "playbook", "cmd", "power") + PC_KINDS:
        if f"{kind}:{low}" in m:
            return m[f"{kind}:{low}"]
    for u in units():
        if u["name"].lower() == low:
            return u
    raise KeyError(f"مفيش قدرة بالاسم «{ident}». جرّب find الأول.")


# ---------------------------------------------------------------- search
def find(query, kind=None, limit=10, min_hits=1):
    """min_hits: how many different words of the query a unit must match. route's «كمان ممكن تفيد» asks for 2: one
    shared generic word («كشف», «ملف») pulled scenedetect and the RE tools into a bank-reconciliation answer."""
    q = query_tokens(query)
    pool = units()
    def kind_ok(u):
        return not kind or u["kind"] == kind or (kind == "pc" and u["kind"].startswith("pc-"))
    if not q:
        return [u for u in pool if kind_ok(u)][:limit]
    ix = _unit_index()
    sc = ix.scores(q)
    hits = ix.hits(q) if min_hits > 1 else None
    ranked = []
    for i, s in enumerate(sc):
        u = pool[i]
        if s <= 0 or not kind_ok(u) or (hits and hits[i] < min(min_hits, len(q))):
            continue
        ranked.append((s * PENALTY.get(u.get("status"), 1.0), u))
    ranked.sort(key=lambda x: -x[0])
    return [u for _, u in ranked[:limit]]


def _scored_recipes(q):
    sc = _recipe_index().scores(q)
    return sorted(((s, r) for s, r in zip(sc, recipes()) if s > 0), key=lambda x: -x[0])


# ---------------------------------------------------------------- the Red Dragon's understanding (hybrid routing)
# The installed Red Dragon understands the owner's requests better than BM25 alone: it decodes Arabic typed on an English
# keyboard and dictation slips, and routes with examples it learned. rd_bridge.py asks it (system python, own process,
# writes nothing); its playbooks become recipes through rd_map.json. Weights tuned on the DEV half only (eval_fresh.py).
W_RD, B0, RD_FLOOR, PICK = 0.5, 20.0, 2.0, 0.2          # tuned on the DEV half (2026-11-15): top1 0.648
RD_TIMEOUT = 25


def rd_map():
    if "rd_map" not in _cache:
        _cache["rd_map"] = _load("rd_map.json", {})
    return _cache["rd_map"]


def rd_info(text):
    """{'text': understood request, 'playbooks': [[score, id]...]} from the Red Dragon, or None (not installed, disabled
    with GOLDEN_FUSION_NO_RD=1, or it failed). Cached per request."""
    if os.environ.get("GOLDEN_FUSION_NO_RD"):
        return None
    key = (text or "").strip()
    memo = _cache.setdefault("rd", {})
    if key in memo:
        return memo[key]
    info, bridge, py = None, DATA / "rd_bridge.py", shutil.which("python")
    if key and bridge.is_file() and py:
        try:
            import subprocess
            r = subprocess.run([py, "-X", "utf8", str(bridge), key], capture_output=True, text=True, encoding="utf-8",
                               errors="replace", timeout=RD_TIMEOUT, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            last = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else ""
            info = json.loads(last) if last.startswith("{") else None
            info = info if info and info.get("ok") else None
        except Exception:
            info = None
    memo[key] = info
    return info


def _blend(bm, pbs):
    """bm {recipe_id: BM25}, pbs [[score, playbook]] -> ({recipe_id: final}, {recipe_id: red-dragon share 0..1})."""
    top_bm = max(bm.values(), default=0.0)
    rd_top = max((s for s, _ in pbs), default=0.0)
    share = {}
    if rd_top >= RD_FLOOR:                      # the Red Dragon's own threshold for «this is a real route»
        for s, pb in pbs:
            for rank, rid in enumerate(rd_map().get(pb, [])):
                share[rid] = max(share.get(rid, 0.0), (s / rd_top) * (1.0, 0.6, 0.4)[min(rank, 2)])
    final = {rid: bm.get(rid, 0.0) / max(top_bm, B0) + W_RD * share.get(rid, 0.0) for rid in set(bm) | set(share)}
    return final, share


def route(request, limit_units=8, rd=...):
    """-> dict: recipes [(score, recipe)], confidence, ambiguous, understood, red_dragon, units, approvals, warnings.
    rd: precomputed rd_info (the evaluation passes one with the graded requests hidden); default = ask the bridge."""
    info = rd_info(request) if rd is ... else rd
    understood = (info or {}).get("text") or ""
    q = query_tokens(request + (" " + understood if understood and understood != request else ""))
    bm = {r["id"]: s for s, r in _scored_recipes(q)} if q else {}
    pbs = (info or {}).get("playbooks") or []
    final, share = _blend(bm, pbs)
    by_rid = {r["id"]: r for r in recipes()}
    ranked = sorted(((s, by_rid[rid]) for rid, s in final.items() if rid in by_rid and s > 0), key=lambda x: -x[0])
    top_bm = max(bm.values(), default=0.0)
    rd_top = max((s for s, _ in pbs), default=0.0)
    chosen = []
    if ranked and ranked[0][0] >= PICK and (top_bm >= 2.5 or rd_top >= RD_FLOOR):
        chosen.append(ranked[0])
        if len(ranked) > 1 and ranked[1][0] >= max(PICK, 0.62 * ranked[0][0]):
            chosen.append(ranked[1])
    conf, ambiguous = "ضعيفة", False
    if chosen:
        rid = chosen[0][1]["id"]
        agree = bm.get(rid, 0.0) >= 0.7 * top_bm and share.get(rid, 0.0) >= 0.6
        conf = "قوية" if agree or chosen[0][0] >= 1.3 else "متوسطة" if chosen[0][0] >= 0.6 else "ضعيفة"
        ambiguous = len(ranked) > 1 and ranked[1][0] >= 0.85 * ranked[0][0] and not agree
    in_recipe = {i for _, r in chosen for s in r["steps"] for i in s.get("read", []) + s.get("use", [])}
    extra = [u for u in find(request, limit=limit_units + len(in_recipe), min_hits=2) if u["id"] not in in_recipe][:limit_units]
    approvals, warnings = [], []
    for _, r in chosen:
        approvals += [a for a in r.get("approvals_ar", []) if a not in approvals]
        for s in r["steps"]:
            for i in s.get("read", []) + s.get("use", []):
                u = by_id().get(i)
                if not u:
                    warnings.append(f"`{i}` مش في الفهرس الحالي (الفهرس اتبنى قبل ما يتشال؟)")
                    continue
                if u.get("cost") == "paid":
                    msg = f"`{i}` مدفوع: محتاج موافقة صريحة على الأداة والسعر قبل التشغيل"
                    if msg not in approvals:
                        approvals.append(msg)
                for w in u.get("warn_ar", []):
                    line = f"`{i}`: {w}"
                    if line not in warnings:
                        warnings.append(line)
    return {"request": request, "recipes": chosen, "confidence": conf if chosen else "مفيش وصفة مناسبة",
            "ambiguous": ambiguous, "understood": understood if understood and understood != request else "",
            "red_dragon": pbs[:3], "ranked": [(round(s, 3), r["id"]) for s, r in ranked[:5]],
            "units": extra, "approvals": approvals, "warnings": warnings}


# ---------------------------------------------------------------- doctor: what is really here now
def _which(cmd):
    """'ffmpeg' -> on PATH?; 'py:faster_whisper' -> importable by the system python?; absolute path -> exists?"""
    if not cmd:
        return None
    if cmd.startswith("py:"):
        py = shutil.which("python")
        if not py:
            return None
        import subprocess
        mod = cmd[3:]
        r = subprocess.run([py, "-c", f"import importlib.util,sys;sys.exit(0 if importlib.util.find_spec({mod!r}) else 1)"],
                           capture_output=True, timeout=30, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return py if r.returncode == 0 else None
    p = Path(os.path.expandvars(cmd))
    if p.is_absolute():
        return str(p) if p.exists() else None
    return shutil.which(cmd)


def first_home(cands):
    for c in cands:
        p = Path(os.path.expandvars(os.path.expanduser(c)))
        if p.exists():
            return p
    return None


def doctor():
    idx = index()
    out = {"skills": {}, "programs": [], "homes": [], "moved": []}
    now = {d.name for d in SKILLS_DIR.iterdir() if (d / "SKILL.md").is_file()} if SKILLS_DIR.is_dir() else set()
    indexed = {u["name"] for u in units() if u["kind"] == "skill"}
    out["skills"] = {"dir": str(SKILLS_DIR), "now": len(now), "indexed": len(indexed),
                     "new": sorted(now - indexed), "gone": sorted(indexed - now)}
    for u in units():
        if u["kind"] in ("program", "local-ai") and u.get("probe"):
            out["programs"].append((u["id"], bool(_which(u["probe"]))))
    for name, cands in (idx.get("homes") or {}).items():
        hit = first_home(cands)
        out["homes"].append((name, str(hit) if hit else None, cands[0]))
    for old, label in idx.get("legacy") or []:
        p = Path(os.path.expandvars(old))
        if not p.exists():
            out["moved"].append((label, old))
    return out


# ---------------------------------------------------------------- Markdown views (what the model reads)
def _short(u, n=110):
    t = (u.get("what_ar") or u.get("what") or "").replace("|", "/").replace("\n", " ")
    return t[:n] + ("…" if len(t) > n else "")


def md_find(query, kind=None, limit=10):
    hits = find(query, kind, limit)
    if not hits:
        return f"مفيش نتايج لـ «{query}». جرّب كلمات إنجليزي أو كلمة أعم، أو route للطلب كله."
    rows = ["| id | النوع | الحالة | بيعمل إيه |", "|---|---|---|---|"]
    for u in hits:
        cost = " 💲" if u.get("cost") == "paid" else ""
        rows.append(f"| `{u['id']}` | {KIND_AR.get(u['kind'], u['kind'])} | {STATUS_AR.get(u.get('status'), u.get('status', ''))}{cost} | {_short(u)} |")
    return "\n".join(rows) + "\n\nshow ID للتفاصيل وإزاي تتنادى."


def _ids(ids):
    return "، ".join(f"`{i}`" for i in ids) or "—"


def md_route(request, limit_units=8):
    r = route(request, limit_units)
    lines = [f"## 🐉 مسار الانصهار: «{request[:120]}»"]
    if r["understood"]:
        lines.append(f"**فهمت الطلب كده:** «{r['understood'][:160]}» (اتفكت الكتابة)")
    if r["red_dragon"]:
        lines.append("**التنين الأحمر شايفه:** " + "، ".join(f"`{pb}` ({s:.1f})" for s, pb in r["red_dragon"][:2]))
    if r["ambiguous"] and len(r["recipes"]) > 1:
        a, b = r["recipes"][0][1], r["recipes"][1][1]
        lines.append(f"⚠ **الطلب محتمل معنيين:** «{a['title_ar']}» أو «{b['title_ar']}». احسمها من السياق أو الملفات؛ "
                     "ولو الاتنين بيغيّروا التسليم ومش عارف تحسم، اسأل سؤال واحد قبل التنفيذ.")
    if not r["recipes"]:
        lines.append("مفيش وصفة جاهزة قريبة كفاية. ابني الخطة بنفسك (مهارة planning-mind أو ultra-mind) من القدرات دي:")
    for score, rec in r["recipes"]:
        lines += [f"\n### الوصفة: {rec['title_ar']} (`{rec['id']}`) · الثقة: {r['confidence']} · {score:.1f}",
                  f"**التسليم:** {rec.get('deliver_ar', '')}",
                  "| # | الخطوة | اقرا الأول (مهارة) | نفّذ بـ | بوابة التحقق |", "|---|---|---|---|---|"]
        for n, s in enumerate(rec["steps"], 1):
            lines.append(f"| {n} | {s['do_ar']} | {_ids(s.get('read', []))} | {_ids(s.get('use', []))} | {s.get('gate_ar', '')} |")
    if r["approvals"]:
        lines.append("\n**🔒 موافقات قبل التنفيذ:**\n" + "\n".join(f"- {a}" for a in r["approvals"]))
    if r["warnings"]:
        lines.append("\n**⚠ تنبيهات:**\n" + "\n".join(f"- {w}" for w in r["warnings"][:12]))
    if r["units"]:
        lines.append("\n**كمان ممكن تفيد:**\n" + "\n".join(
            f"- `{u['id']}` ({KIND_AR.get(u['kind'], u['kind'])}{', ' + STATUS_AR.get(u.get('status'), '') if u.get('status') != 'ok' else ''}): {_short(u, 90)}"
            for u in r["units"]))
    lines.append("\n**الخطوة الجاية:** اقرا SKILL.md بتاع كل مهارة في الخطوة 1 (أداة skill)، وبعدين نفّذ، وماتعدّيش بوابة غير لما تتقاس.")
    return "\n".join(lines)


# ---------------------------------------------------------------- right the first time: brief before, check after
def lessons_for(text, limit=5):
    """The owner's recorded lessons that apply to this request (BM25 over lesson, rule and domain)."""
    ls = lessons()
    q = query_tokens(text)
    if not ls or not q:
        return []
    ix = _cache.get("lix")
    if ix is None:
        ix = _cache["lix"] = _BM25([[(x.get("lesson_ar", ""), 2.0), (x.get("rule_en", ""), 1.0), (x.get("domain", ""), 1.5)] for x in ls])
    sc = ix.scores(q)
    sev = {"high": 1.3, "medium": 1.0, "low": 0.8}
    ranked = sorted(((s * sev.get(x.get("severity"), 1.0), x) for s, x in zip(sc, ls) if s > 0), key=lambda t: -t[0])
    return [x for _, x in ranked[:limit]]


def md_brief(request):
    """Before any heavy tool: the request as understood, the intent sheet to fill, three real alternatives, a pre-mortem
    made of the owner's own past failures for this kind of request, and the gates that will prove the result."""
    r = route(request)
    top = r["recipes"][0][1] if r["recipes"] else None
    second = r["recipes"][1][1] if len(r["recipes"]) > 1 else None
    tags = " ".join(top.get("tags", [])) if top else ""
    les = lessons_for(" ".join([request, r["understood"], tags]), 5)
    out = [f"## 🧠 افهم قبل ما تنفّذ: «{request[:140]}»"]
    if r["understood"]:
        out.append(f"- **الطلب بعد فك الكتابة:** «{r['understood'][:200]}»")
    lvl, why = depth(r, request)
    out.append(f"- **العمق:** {lvl}: {why}" + ("، ولو الشغل طويل: خطة على الديسك بـ `rd.py think start` (مجلس ونقد وأوقات "
                                              "متعايرة)" if lvl in ("L2", "L3") else ""))
    out += ["- **اكتب لنفسك سطر لكل بند قبل أي أداة (بالإنجليزي):** Task · Deliverable (الملف ومكانه وصيغته) · "
            "Constraints (من الطلب ومن الدروس تحت) · Done-when (القياس اللي يثبت إنه صح)."]
    if top:
        gates = " · ".join(s["gate_ar"] for s in top["steps"] if s.get("gate_ar"))
        out.append(f"- **الأقرب:** {top['title_ar']} (`{top['id']}`) · الثقة {r['confidence']}\n  - **البوابات:** {gates}")
    else:
        out.append("- **مفيش وصفة قريبة:** الطلب جديد عليا، ابني الخطة بنفسك (planning-mind) وماتفترضش.")
    if r["ambiguous"] and second:
        out.append(f"- ⚠ **ممكن يكون معناه حاجة تانية:** «{second['title_ar']}». لو الفرق بيغيّر التسليم، احسمه من الملفات أو "
                   "اسأل سؤال واحد بس.")
    pb = _red_playbook(r, top)
    extra = ((by_id().get(f"playbook:{pb}") or {}).get("extra") or {}) if pb else {}
    if second:
        alt2 = f"{second['title_ar']} (`{second['id']}`): " + " ← ".join(s["do_ar"] for s in second["steps"])
    elif extra.get("steps_text"):
        alt2 = (f"طريق التنين الأحمر المجرّب (playbook `{pb}`، و$E = محرك التنين): "
                + " ← ".join(_clip(str(s), 150) for s in extra["steps_text"][:4]))
    else:
        alt2 = "أبسط طريق يكفي: أقل أداة وأقل خطوات توصل لنفس التسليم (MVP)، وبعدين حسّن."
    out += ["- **عصف ذهني — 3 طرق مختلفة فعلًا، واختار واحدة بسبب مكتوب (الوقت، والمخاطرة، والجودة):**",
            "  1. " + ((f"{top['title_ar']}: " + " ← ".join(s["do_ar"] for s in top["steps"])) if top else "الطريق المباشر."),
            "  2. " + alt2,
            "  3. الطريق الأعلى جودة: إيه اللي يخلّي النتيجة أحسن بوضوح؟ (مرجع أقوى، أداة أدق، أو قياس أكتر)"]
    if extra.get("ask"):
        out.append(f"- **أسئلة لازم تتحسم (من playbook التنين الأحمر `{pb}`):** احسمها من الملفات والسياق، واسأل بس اللي "
                   "مايتعرفش:\n" + "\n".join(f"  - {str(a)[:180]}" for a in extra["ask"][:3]))
    risks = [str(p)[:200] for p in (extra.get("pitfalls") or [])[:2]] + [x["lesson_ar"] for x in les[:3]]
    if r["approvals"]:
        risks.append("خطوة محتاجة موافقة: " + r["approvals"][0] + ". قبلها: `rd.py consent \"<رسالة صاحب الشغل>\"`")
    if top:
        risks.append(f"البوابة الأضعف: «{top['steps'][-1].get('gate_ar', '')}». اتأكد إنها هتتقاس فعلًا مش هتتوصف بس")
    out.append("- **تشريح قبل الفشل (أرجح أسباب الرفض، اقفل كل واحد بخطوة):**\n" + "\n".join(f"  - {x}" for x in risks[:5]))
    tools = thinking_for(request, top)
    for p in thinking_paths(request)[:2]:
        out.append(f"- 🧭 **{p['name_ar']}:** {p.get('hint_ar', '')} (`fusion think {p['id']}` للسبيل كله)")
    if tools:
        out.append("- **أدوات تفكير للطلب ده (من كتب العلماء والتفكير):**\n" + "\n".join(
            f"  - **{t.get('name_ar', t['id'])}** ({_src_label(t)}): " + " ← ".join(t.get("steps_ar", [])[:3])
            + (f"\n    - ✔ في الآخر: {t['check_ar']}" if t.get("check_ar") else "") for t in tools))
    shown = set(risks)
    more = [x for x in les if x["lesson_ar"] not in shown]
    if more:
        out.append("- **دروس تانية من تاريخ الشغل للطلب ده:**\n" + "\n".join(f"  - {x['lesson_ar']}" for x in more))
    out.append("- **قبل ما ترد:** `fusion check` على ردك (query = الطلب، draft = الرد)، وصلّح كل ✗. ولو التوجيه طلع غلط وصاحب الشغل "
               "صحّحك: `rd.py teach` عشان التنين الأحمر والذهبي يتعلموا.")
    return "\n".join(out)


def _red_playbook(r, top):
    """The Red Dragon playbook behind this request: its own top route if it maps to the chosen recipe, else the playbook
    whose main recipe it is."""
    m = rd_map()
    for _, pb in r.get("red_dragon") or []:
        if top and top["id"] in (m.get(pb) or []):
            return pb
    if top:
        return next((pb for pb, rs in m.items() if rs and rs[0] == top["id"]), None)
    return None


# Task type of a recipe, for picking thinking tools (the toolkit's use_when uses the same words)
TASK_TYPE = {"reverse-engineer": "analyze", "reverse-android": "analyze", "social-analytics": "analyze",
             "reconcile-statements": "analyze", "github-repos": "analyze", "debug-code": "debug", "hard-decision": "decide",
             "trading": "decide", "business-launch": "plan", "app-self-develop": "plan", "own-tool-build": "plan",
             "new-skill": "plan", "web-app": "plan", "deep-research": "learn", "media-hunt": "learn", "data-chart": "communicate",
             "office-docs": "communicate", "prompt-writing": "communicate", "status-check": "communicate",
             "math-explainer": "estimate", "heavy-cloud": "estimate", "ship-package": "review"}


def thinking():
    if "thinking" not in _cache:
        _cache["thinking"] = _load("thinking.json", {"tools": []})
    return _cache["thinking"]


# Which thinking tools matter most for each task type, best first. From the source skills themselves: the reverse-
# engineering method starts from competing hypotheses and the base rate and ends by trying to falsify the verdict;
# systematic-debugging reproduces before it hunts the root cause; creative work dies on misread constraints («no
# overlay unless asked»). Tools the brief already has as sections (3 alternatives, the pre-mortem) come later. Ties in
# the toolkit's use_when are broken by this order instead of by the order of the file.
TOOL_PRIORITY = {
    "analyze": ["restate-and-unknowns", "competing-hypotheses", "outside-view", "falsify-it", "independent-verification"],
    "debug": ["restate-and-unknowns", "minimal-repro", "root-cause-trace", "verify-api-not-memory", "falsify-it"],
    "decide": ["restate-and-unknowns", "outside-view", "inversion", "alternatives-before-commit", "red-team-council"],
    "plan": ["ask-or-assume-gate", "begin-with-the-end", "inversion", "outside-view", "premortem"],
    "estimate": ["polya-four-phases", "fermi-estimate", "outside-view", "calibrate-and-update"],
    "learn": ["restate-and-unknowns", "feynman-explain-back", "independent-verification", "calibrate-and-update"],
    "communicate": ["restate-and-unknowns", "one-big-idea-first", "feynman-explain-back"],
    "review": ["constraint-ledger", "red-team-council", "falsify-it", "independent-verification"],
    "create": ["constraint-ledger", "begin-with-the-end", "inversion", "independent-verification"],
}


def thinking_paths(request):
    """The Arabic «سبل التفكير» (thinking.json paths: الخيال، العميق، الإبداعي، المنطق، خطوة بخطوة، التحليل، القرار) whose
    trigger words appear in the request, best first. Lets «تخيّل…» or «فكّر بعمق» pull that path's tools to the top."""
    words = set(query_tokens(request))
    norm = _norm(request)
    hits = []
    for p in thinking().get("paths") or []:
        trig = p.get("trigger_words") or []
        n = len(words & set(query_tokens(" ".join(trig)))) + sum(1 for w in trig if " " in w and _norm(w) in norm)
        if n:
            hits.append((n, p))
    return [p for _, p in sorted(hits, key=lambda x: -x[0])]


def thinking_for(request, top, limit=3):
    """2-3 thinking tools for this request: one for understanding, then the rest. Score = the task type's priority
    order (TOOL_PRIORITY) + whether use_when has the task type + the request's own trigger words (capped, so one long
    phrase can't drown the rest; «اسألني لو مش واضح» still lifts the ask-or-assume gate to the top)."""
    tools = thinking().get("tools") or []
    if not tools:
        return []
    ttype = TASK_TYPE.get(top["id"], "create") if top else "plan"
    pri = TOOL_PRIORITY.get(ttype, [])
    words = set(query_tokens(request))
    paths = thinking_paths(request)
    on_path = {}
    for p in paths[:2]:                       # the request's own «سبيل»: its tools in order, the first path weighs more
        for i, tid in enumerate(p.get("tools") or []):
            on_path.setdefault(tid, (3.0 if p is paths[0] else 2.0) - i * 0.3)

    def score(t):
        trig = set(query_tokens(" ".join(t.get("trigger_words") or [])))
        rank = len(pri) - pri.index(t["id"]) if t["id"] in pri else 0
        return (rank + (ttype in (t.get("use_when") or [])) * 0.5 + min(len(words & trig), 2) * 2.5
                + on_path.get(t["id"], 0))
    first = next((t for t in sorted(tools, key=score, reverse=True) if "understand" in (t.get("use_when") or [])), None)
    rest = [t for t in sorted(tools, key=score, reverse=True) if t is not first and score(t) > 0]
    return ([first] if first else []) + rest[: limit - (1 if first else 0)]


def _src_label(t):
    """Who a thinking tool comes from: the thinker and book («Gary Klein — Pre-mortem (HBR 2007)»), else the skill."""
    srcs = t.get("source") or []
    srcs = [str(s) for s in (srcs if isinstance(srcs, list) else [srcs])]
    for s in srcs:
        if " — " in s:
            return re.split(r":\s*(?:~|[A-Za-z]:)", s, maxsplit=1)[0].strip()[:80]
    for s in srcs:
        m = re.search(r"skills[\\/](?:(?:red|golden)-dragon[\\/]engine[\\/]skills[\\/])?([\w.\-]+)", s)
        if m:
            return "مهارة " + m.group(1)
    return "صندوق أدوات التفكير"


def _clip(s, n):
    """At most n characters, cut at a word boundary with «…» (never in the middle of a word)."""
    s = " ".join(s.split())
    if len(s) <= n:
        return s
    cut = s[:n].rsplit(" ", 1)[0]
    return (cut if len(cut) >= n // 2 else s[:n]).rstrip(" ،,;:←-") + "…"


def depth(r, request):
    """Protocol step ①: how much thinking a request deserves. -> (level, why). L0 = a quick fact or a plain command,
    L1 = a known recipe chosen with strong confidence, L2 = ambiguous / weak / needs approval, L3 = nothing in the index
    looks like it. A heuristic over the router's own signals, not a measured classifier."""
    top = r["recipes"][0][1] if r.get("recipes") else None
    if not top:
        if len(query_tokens(request)) <= 3:
            return "L0", "سؤال أو أمر قصير: افهم (①) وسلّم متحقق (⑧) بس، من غير خطة طويلة"
        return "L3", "طلب جديد مالوش وصفة في الفهرس: البروتوكول كله ①–⑧، وماتفترضش حاجة مش مقاسة"
    if r.get("approvals"):
        return "L2", "فيه خطوة محتاجة موافقة: البروتوكول كله ①–⑧، و`rd.py consent` قبل الخطوة دي"
    if r.get("ambiguous") or r.get("confidence") == "ضعيفة":
        return "L2", "المعنى مش محسوم: البروتوكول كله ①–⑧، واحسم المعنى (②) قبل أي أداة تقيلة"
    if r.get("confidence") == "قوية":
        return "L1", "وصفة معروفة بثقة قوية: ① ② ③ ⑥ ⑧ (افهم، اسأل أو افترض، ابدأ من الآخر، نفّذ صغير، اتحقق)"
    return "L2", "ثقة متوسطة: البروتوكول كله ①–⑧"


# Questions every final answer must pass (the thinkers' own checks), after the ones picked for the request itself
FINAL_CRITIC = ("independent-verification", "calibrate-and-update", "one-big-idea-first")


def critic_questions(request, top=None, task_tools=2):
    """[(tool name, its check question)]: up to `task_tools` of the request's own thinking tools, then ALL of
    FINAL_CRITIC. Each question is answered «yes» with evidence from the answer, or the answer gets fixed."""
    by = {t["id"]: t for t in thinking().get("tools") or []}
    own = [t for t in thinking_for(request, top, limit=task_tools + 1) if t["id"] not in FINAL_CRITIC][:task_tools]
    picked = own + [by[i] for i in FINAL_CRITIC if i in by]
    return [(t.get("name_ar", t["id"]), t["check_ar"]) for t in picked if t.get("check_ar")]


_CLAIM = re.compile(r"خلص|خلاص|اتعمل|اتنفذ|جاهز|اتثبت|نجح|تم |تمام|done|verified|ready", re.I)
_EVIDENCE = re.compile(r"اتقاس|قست|اتأكد|اتأكدت|اتحقق|verify_media|اختبار|test|✅|\b\d+(?:[.,]\d+)?\s?(?:ث|ثانية|دقيقة|MB|GB|KB|ميجا|"
                       r"جيجا|LUFS|dBTP|%|fps|px|فريم|×|ملف|سطر|نجح)", re.I)
_PATH = re.compile(r"[A-Za-z]:\\[^\s`*|]+|%[A-Z]+%\\[^\s`*|]+|~[\\/][^\s`*|]+")
_ANALYSIS = re.compile(r"حلل|حلّل|تحليل|هندسه عكسيه|هندسة عكسية|analy|reverse|افحص|فحص")
_OUTWARD = re.compile(r"انشر|نشرت|ارفع|رفعت|امسح|مسحت|اشتري|كريدت|رصيد|publish|upload|delete|purchase", re.I)


def check(request, draft):
    """Deterministic self-critique of a final answer against its request. Returns [(ok, message)], missed words, lessons.
    It checks form and coverage, not truth: the measurements in the answer are what prove the content."""
    draft = draft or ""
    lines = [ln for ln in draft.splitlines() if ln.strip()]
    res = []
    has_path = bool(_PATH.search(draft))
    if has_path:                              # the owner's rule (L05): the full path on the FIRST line (or right under a title)
        first = lines[0] if lines else ""
        head = first + (" " + lines[1] if first.lstrip().startswith("#") and len(lines) > 1 else "")
        res.append((bool(_PATH.search(head)), "المسار الكامل للناتج في أول سطر (أو تحت العنوان على طول)"))
    if len(lines) > 8:
        res.append(("اللي اتعمل" in draft or "اتعمل:" in draft, "فيه قسم «اللي اتعمل» في الآخر"))
    if _CLAIM.search(draft):
        res.append((bool(_EVIDENCE.search(draft)), "أي «خلص/جاهز/اتعمل» معاه دليل مقاس (رقم، اختبار، أو ✅ بدليل)"))
    if _ANALYSIS.search(_norm(request)):
        res.append(("✅" in draft and ("🟡" in draft or "❓" in draft), "تحليل: فيه ✅ دليل و🟡 استنتاج و❓ مجهول"))
    if _OUTWARD.search(draft):
        res.append((bool(re.search(r"موافق|موافقة|approval|اترفض", draft)), "أي نشر أو رفع أو مسح أو صرف مذكور معاه الموافقة"))
    asked = [w for w in dict.fromkeys(query_tokens(request)) if len(w) >= 4 and not w.isdigit()]
    got = {_skeleton(g) for g in query_tokens(draft) if len(g) >= 3}
    missed = []
    for w in asked:
        sk = _skeleton(w)
        if len(sk) >= 3 and not any(sk in g or (len(g) >= 3 and g in sk) for g in got):
            missed.append(w)
    return res, missed[:8], lessons_for(request, 3)


def _skeleton(w):
    """A word's consonant skeleton, so Arabic forms of one root meet: «امسح»/«المسح» -> «مسح», «وحدّث»/«تحديث» -> «حدث»/«تحدث»,
    «وثبّت»/«ماتثبّتش» -> «ثبت»/«متثبتش». English words are kept as they are."""
    w = _ar_stem(w)
    if w.isascii():
        return w
    if len(w) > 3 and w[0] == "و":
        w = w[1:]
    return re.sub(r"[اويىءأإآؤئ]", "", w)


def md_check(request, draft):
    if not (draft or "").strip():
        return "✗ ابعت الرد اللي ناوي ترسله في draft، والطلب في query."
    res, missed, les = check(request, draft)
    bad = [m for ok, m in res if not ok]
    out = [f"## 🔍 الناقد الذاتي: {len(bad)} حاجة لازم تتصلّح قبل الإرسال" if bad else "## 🔍 الناقد الذاتي: الشكل سليم"]
    out += [f"- {'✓' if ok else '✗'} {m}" for ok, m in res]
    if missed:
        out.append("- ممكن تكون مارديتش على: " + "، ".join(missed) + " — ارجع للطلب بند بند.")
    if les:
        out.append("- دروس تخص الطلب ده، اتأكد إنك طبّقتها:\n" + "\n".join(f"  - {x['lesson_ar']}" for x in les))
    # the thinkers' critic questions; reuse the Red Dragon reading if brief already asked for it (no second subprocess)
    r = route(request, rd=_cache.get("rd", {}).get((request or "").strip()))
    qs = critic_questions(request, r["recipes"][0][1] if r["recipes"] else None)
    if qs:
        out.append("- **أسئلة الناقد (من كتب العلماء): جاوب كل سؤال بـ«أيوه» ودليل من ردك، أو صلّح الرد:**\n"
                   + "\n".join(f"  - {q} ({n})" for n, q in qs))
    out.append("- الفحص ده بيراجع الشكل والتغطية بس، مش صحة المحتوى. الصحة بتثبت بالقياس اللي في الرد.")
    return "\n".join(out)


def md_think(query=""):
    """«سبل التفكير»: one path with its tools' steps and critic question (by id, Arabic name or trigger word), or the map
    of all paths when nothing matches. Easy recall: «سبيل الخيال»، «التفكير العميق»، «الإبداعي»، «المنطق»، «خطوة بخطوة»."""
    paths = thinking().get("paths") or []
    if not paths:
        return "✗ مفيش سبل تفكير في fusion\\thinking.json (ابني تاني بـ build_fusion.py)."
    by = {t["id"]: t for t in thinking().get("tools") or []}
    q = _norm(query)
    pick = [p for p in paths if q and (q == p["id"] or q in _norm(p["name_ar"]))] or (thinking_paths(query) if q else [])
    if not pick:
        out = ["## 🧭 سبل التفكير (اكتب `fusion think <السبيل>` عشان خطواته):"]
        for p in paths:
            names = "، ".join(by[x].get("name_ar", x).split(":")[0] for x in p["tools"] if x in by)
            out.append(f"- **{p['name_ar']}** (`{p['id']}`): {p.get('hint_ar', '')}\n  - {names}")
        return "\n".join(out)
    p = pick[0]
    out = [f"## 🧭 {p['name_ar']}: {p.get('hint_ar', '')}"]
    for x in p["tools"]:
        t = by.get(x)
        if not t:
            continue
        out.append(f"- **{t.get('name_ar', x)}** ({_src_label(t)}):\n" + "\n".join(f"  {i}. {st}" for i, st in
                                                                                 enumerate(t.get("steps_ar") or [], 1))
                   + (f"\n  - ✔ {t['check_ar']}" if t.get("check_ar") else ""))
    return "\n".join(out)


def md_show(ident):
    u = resolve(ident)
    keys = [("النوع", KIND_AR.get(u["kind"], u["kind"])), ("الحالة", STATUS_AR.get(u.get("status"), u.get("status"))),
            ("التكلفة", {"free": "ببلاش", "paid": "💲 مدفوع (موافقة صريحة)", "approval": "محتاج موافقة"}.get(u.get("cost"), u.get("cost"))),
            ("إزاي تتنادى", f"`{u.get('how', '')}`"), ("المسار", u.get("path", "")), ("الرخصة", u.get("license", "")),
            ("العيلة", u.get("family", "")), ("اللغة", u.get("lang", ""))]
    body = "\n".join(f"- {k}: {v}" for k, v in keys if v)
    extra = u.get("extra") or {}
    more = "\n".join(f"- {k}: {', '.join(map(str, v)) if isinstance(v, list) else v}" for k, v in extra.items() if v)
    warn = "\n".join(f"- ⚠ {w}" for w in u.get("warn_ar", []))
    used = [r["id"] for r in recipes() if any(u["id"] in s.get("read", []) + s.get("use", []) for s in r["steps"])]
    return (f"## {u['name']} (`{u['id']}`)\n{u.get('what_ar') or ''}\n\n{u.get('what', '')}\n\n{body}"
            + (f"\n{more}" if more else "") + (f"\n{warn}" if warn else "")
            + (f"\n- في الوصفات: {_ids(used)}" if used else ""))


def md_recipes():
    rows = ["| id | الوصفة | خطوات | مثال |", "|---|---|---|---|"]
    for r in recipes():
        rows.append(f"| `{r['id']}` | {r['title_ar']} | {len(r['steps'])} | {r['when'][0]} |")
    return "\n".join(rows) + "\n\nroute \"<الطلب>\" بيختار الوصفة لوحده."


def md_doctor():
    d = doctor()
    s = d["skills"]
    lines = [f"## 🩺 فحص التنين الذهبي",
             f"- المهارات: {s['now']} موجودة دلوقتي، و{s['indexed']} في الفهرس"
             + (f"، جديدة مش في الفهرس: {', '.join(s['new'][:10])}" if s["new"] else "")
             + (f"، اتشالت: {', '.join(s['gone'][:10])}" if s["gone"] else "") + "."]
    ok = [i for i, good in d["programs"] if good]
    bad = [i for i, good in d["programs"] if not good]
    lines.append(f"- البرامج: {len(ok)} موجود من {len(d['programs'])}" + (f". مش لاقيه: {', '.join(f'`{b}`' for b in bad)}" if bad else "."))
    for name, hit, first in d["homes"]:
        if not hit and "الاستوديو" in name:
            lines.append(f"- {name}: لسه مااتفكّش ولا برنامج (المجلد بيتعمل أول ما تعمل studio_run install)")
            continue
        lines.append(f"- {name}: {hit if hit else '✗ مش موجود (أول مكان اتدوّر فيه: ' + first + ')'}")
    if d["moved"]:
        lines.append("- مسارات قديمة اتنقلت (التطبيق بيدوّر على المكان الجديد لوحده): " + "، ".join(f"{a} ({b})" for a, b in d["moved"]))
    if s["new"] or s["gone"]:
        lines.append("- لو المهارات اتغيّرت كتير: أعد بناء الفهرس (forge\\build_fusion.py) وبعدين ابني التطبيق.")
    lines.append(_local_line())
    return "\n".join(lines)


def _local_line():
    loc = local()
    if loc.get("off"):
        return "- كتالوج الجهاز: مقفول (GOLDEN_NO_LOCAL)."
    n = len(loc.get("units") or [])
    if not loc.get("generated"):
        return "- كتالوج الجهاز: لسه ماتعملش. شغّل `fusion discover`."
    age = _gdd.age_days(loc)
    try:
        limit = float(_gdd.load_config().get("max_age_days", 7))
    except (TypeError, ValueError):
        limit = 7.0
    kinds = _gdd.summary(loc)
    parts = "، ".join(f"{KIND_AR.get(k, k)} {v}" for k, v in sorted(kinds.items(), key=lambda x: -x[1]))
    return (f"- كتالوج الجهاز: {n} حاجة ({parts})، اتعمل {loc.get('generated')}"
            + (f". **قديم ({age:.0f} يوم): شغّل `fusion discover`**" if age is not None and age > limit else "") + ".")


def md_discover():
    d = discover()
    kinds = _gdd.summary(d)
    rows = ["## 🔭 اكتشاف الجهاز", f"- لقيت {len(d['units'])} حاجة في {d['seconds']} ث"
            + (f" (وقفت بدري: حد {d['cut']})" if d.get("cut") else "") + ":"]
    rows += [f"  - {KIND_AR.get(k, k)}: {v}" for k, v in sorted(kinds.items(), key=lambda x: -x[1])]
    rows.append("- الأماكن: " + "، ".join(f"{k} ({v})" for k, v in sorted(d["per_root"].items(), key=lambda x: -x[1])))
    rows.append(f"- الكتالوج والإعدادات على الجهاز بس: `{_gdd.CONFIG}` (ضيف فولدرات في roots أو استبعد بـ exclude).")
    rows.append("- دلوقتي `find` و`show` و`route` بيشوفوهم (النوع `pc` في find = كل اللي على الجهاز).")
    return "\n".join(rows)


def md_local(kind=None, limit=40):
    loc = local()
    us = [u for u in loc.get("units") or [] if not kind or u["kind"] == kind or (kind == "pc" and u["kind"].startswith("pc-"))]
    if not us:
        return _local_line()
    rows = [_local_line(), "", "| id | النوع | الحالة | بيعمل إيه |", "|---|---|---|---|"]
    for u in us[:limit]:
        rows.append(f"| `{u['id']}` | {KIND_AR.get(u['kind'], u['kind'])} | {STATUS_AR.get(u.get('status'), '')} | "
                    f"{_short(u, 80) or u['name']} |")
    if len(us) > limit:
        rows.append(f"\n… و{len(us) - limit} كمان. ضيّق بـ `find \"كلمة\" --kind pc-app` مثلًا.")
    return "\n".join(rows)


def md_lessons(query, limit=8):
    ls = lessons()
    if not ls:
        return "مفيش دروس متسجّلة في الفهرس."
    q = query_tokens(query)
    if q:
        ix = _BM25([[(x.get("lesson_ar", ""), 2.0), (x.get("rule_en", ""), 1.0), (x.get("domain", ""), 1.5)] for x in ls])
        sc = ix.scores(q)
        picked = [x for s, x in sorted(zip(sc, ls), key=lambda t: -t[0]) if s > 0][:limit]
    else:
        picked = [x for x in ls if x.get("severity") == "high"][:limit]
    if not picked:
        return f"مفيش دروس عن «{query}»."
    return "\n".join(f"- [{x.get('domain', '')}] {x.get('lesson_ar', '')} (الدليل: {x.get('evidence', '')})" for x in picked)


def stats():
    c = Counter(u["kind"] for u in units())
    st = Counter(u.get("status") for u in units())
    return {"units": len(units()), "kinds": dict(c), "status": dict(st), "recipes": len(recipes()), "lessons": len(lessons()),
            "generated": index().get("generated"), "local": len(local().get("units") or []),
            "local_generated": local().get("generated")}


# ---------------------------------------------------------------- CLI
def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0 if argv else 2
    act, rest = argv[0], argv[1:]
    try:
        if act == "route" and rest:
            print(md_route(" ".join(rest)))
        elif act == "find" and rest:
            kind, limit = None, 10
            if "--kind" in rest:
                i = rest.index("--kind")
                kind = rest[i + 1]
                rest = rest[:i] + rest[i + 2:]
            if "--limit" in rest:
                i = rest.index("--limit")
                limit = int(rest[i + 1])
                rest = rest[:i] + rest[i + 2:]
            print(md_find(" ".join(rest), kind, limit))
        elif act == "show" and rest:
            print(md_show(rest[0]))
        elif act == "recipes":
            print(md_recipes())
        elif act == "doctor":
            print(md_doctor())
        elif act == "discover":
            print(md_discover())
        elif act == "local":
            print(md_local(rest[0] if rest else None))
        elif act == "stats":
            print(json.dumps(stats(), ensure_ascii=False))
        elif act == "lessons":
            print(md_lessons(" ".join(rest)))
        elif act == "think":
            print(md_think(" ".join(rest)))
        elif act == "brief" and rest:
            print(md_brief(" ".join(rest)))
        elif act == "check" and "--request" in rest and "--draft" in rest:
            req = rest[rest.index("--request") + 1]
            src = rest[rest.index("--draft") + 1]
            draft = sys.stdin.read() if src == "-" else Path(src).read_text(encoding="utf-8-sig")
            print(md_check(req, draft))
        else:
            print(__doc__)
            return 2
    except (KeyError, FileNotFoundError, ValueError) as e:
        print(f"✗ {e.args[0] if e.args else e}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
