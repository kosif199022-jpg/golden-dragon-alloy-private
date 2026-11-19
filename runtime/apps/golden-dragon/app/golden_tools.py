"""golden_tools.py — what «التنين الذهبي» (Golden Dragon) adds on top of the White Bird: the programs and libraries found by
reverse engineering the owner's «مهارات» folder (2026-11-14), as two offline catalogs the agent can search and use.

  studio  open-source command-line programs from مهارات\\برامج (Rhubarb lip sync, HandBrakeCLI, Synfig, Tahoma2D, melt,
          whisper-cli, oiiotool…). list / show; install = check the archive's sha256 against the one recorded during the
          analysis, then unpack it into %USERPROFILE%\\GoldenDragon\\studio\\<id> (unpacking runs nothing); cmd = the exact
          command line that runs the program (the app runs it after the user's approval).
  lib     motion / web / video libraries (GSAP, anime.js, three.js, lottie-web… the 97 motion clones and the zips).
          find / show; kit = copy the ready offline build files of chosen libraries (with their licences) into
          <working folder>\\vendor, so an HTML film renders with no CDN and no internet.
  sync    time follows speech (idea from the hypit study, own code): a script with word marks (@{x}…@{/x} range,
          @{x!} moment, || or a new line = caption break) + WhisperX / faster-whisper word JSON -> sync.json (every mark
          in seconds and frames) + captions.srt.

CLI (the subscription mode runs commands instead of app tools):
  python -X utf8 golden_tools.py studio list | show ID | install ID | cmd ID [args...]
  python -X utf8 golden_tools.py lib find "words" [--limit N] | show ID | kit DEST ID [ID...]
  python -X utf8 golden_tools.py sync SCRIPT.txt WORDS.json OUT_DIR [--fps 30]
Standard library only. Data: .\\golden\\studio.json and .\\golden\\library.json (made by forge\\build_catalog.py).
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = Path(os.environ.get("GOLDEN_DATA") or (HERE / "golden"))
STUDIO_HOME = Path(os.environ.get("GOLDEN_STUDIO_HOME") or (Path.home() / "GoldenDragon" / "studio"))
KIT_CAP = 60 * 1024 * 1024          # one library copied into a project never exceeds this
SEVEN_ZIP = (r"C:\Program Files\7-Zip\7z.exe", r"C:\Program Files (x86)\7-Zip\7z.exe")


# ---------------------------------------------------------------- data
def _load(name):
    p = DATA / name
    if not p.is_file():
        raise FileNotFoundError(f"كتالوج التنين الذهبي مش موجود: {p}")
    return json.loads(p.read_text(encoding="utf-8"))


def studio_items():
    return _load("studio.json")["programs"]


def library():
    return _load("library.json")


def lib_items():
    return library()["items"]


def _by_id(items, ident):
    key = (ident or "").strip().lower()
    for it in items:
        if it["id"].lower() == key or it.get("name", "").lower() == key:
            return it
    raise KeyError(f"مفيش عنصر بالاسم «{ident}». جرّب find أو list الأول.")


# ---------------------------------------------------------------- search (Arabic-aware)
_AR = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ة": "ه", "ى": "ي"})
SYNONYMS = {   # Egyptian / Arabic request words -> the English words the catalog uses
    "انيميشن": "animation tween motion", "موشن": "motion animation", "حركه": "motion animation tween",
    "جزيئات": "particles", "جسيمات": "particles", "كونفيتي": "confetti", "شيدر": "shader glsl", "شيدرات": "shader glsl",
    "ثري": "3d three webgl", "3d": "3d three webgl", "ثلاثي": "3d three webgl", "مجسم": "3d", "كره": "globe",
    "نص": "text typography", "كتابه": "text typing typewriter", "خط": "text font typography", "تايبوجرافي": "typography text",
    "لوتي": "lottie", "فيديو": "video", "ترجمه": "subtitle caption", "كابشن": "caption subtitle", "سب": "subtitle",
    "شفايف": "lip mouth sync", "شفاه": "lip mouth sync", "بق": "lip mouth", "مزامنه": "sync", "ضغط": "encode compress",
    "تحويل": "convert encode", "رندر": "render", "كارتون": "cartoon toon", "انمي": "anime cartoon", "خلفيه": "background",
    "قص": "cut clip", "تقطيع": "cut clip", "تحميل": "download", "صوت": "audio voice", "رسم": "draw paint", "شخصيه": "character",
    "وش": "face portrait", "ريلز": "reel vertical short", "جرافيك": "graphics motion", "لوجو": "logo", "شعار": "logo",
    "سلايد": "slides presentation", "داتا": "data chart", "رسم بياني": "chart", "خريطه": "map globe", "سائل": "fluid",
    "دخان": "fluid smoke", "تدرج": "gradient", "ضوء": "light", "زجاج": "glass", "واجهه": "ui", "زرار": "button ui",
    "انتقال": "transition seam", "انتقالات": "transition seam", "تلوين": "color grade lut", "الوان": "color palette grade",
    "لوت": "lut grade", "ايقاع": "rhythm cadence beat", "بيت": "beat", "كاميرا": "camera", "شرح": "explainer manim",
    "رياضيات": "math manim", "عرض": "slides presentation", "تتبع": "tracking", "بانر": "banner", "اعلان": "ad promo",
    "منتج": "product promo", "عنوان": "title", "مقدمه": "intro opener", "خاتمه": "outro logo", "دعاء": "caption subtitle arabic",
}


def norm(t):
    t = re.sub(r"[\u064B-\u0670\u0640]", "", str(t or "").lower()).translate(_AR)
    return re.sub(r"\s+", " ", t).strip()


_PREFIXES = ("وبال", "وال", "بال", "فال", "كال", "لل", "ال")      # و/ب/ف/ك/ل + the article, longest first


def _stem(w):
    """Arabic surface form -> also its bare form: «والجزيئات» -> «جزيئات», «للشعار» -> «شعار»."""
    for p in _PREFIXES:
        if w.startswith(p) and len(w) - len(p) >= 3:
            return w[len(p):]
    return w


def _tokens(q):
    toks = [w for w in re.split(r"[\s,،/|+]+", norm(q)) if len(w) > 1]
    toks += [s for s in (_stem(w) for w in toks) if s not in toks]
    out = list(toks)
    for w in toks:
        for k, v in SYNONYMS.items():
            if w == norm(k) or (len(w) > 3 and w.startswith(norm(k))):
                out += v.split()
    return list(dict.fromkeys(out))


def _score(it, toks):
    heavy = norm(" ".join([it["id"], it.get("name", ""), " ".join(it.get("keywords") or [])]))
    mid = norm(" ".join([it.get("category", ""), it.get("lang", ""), it.get("group", "")]))
    light = norm(" ".join(str(it.get(k) or "") for k in ("what_ar", "use_ar", "requires", "cli")))
    s = 0.0
    for t in toks:
        s += 3 if t in heavy else 2 if t in mid else 1 if t in light else 0
    if s and it.get("readiness") == "ready-offline":
        s += 0.5
    return s


def lib_find(query, limit=8, category=None):
    toks = _tokens(query)
    pool = [it for it in lib_items() if not category or it.get("category") == category]
    if not toks:
        return pool[:limit]
    ranked = sorted(((s, it) for it in pool if (s := _score(it, toks)) > 0), key=lambda x: -x[0])
    return [it for _, it in ranked[:limit]]


# ---------------------------------------------------------------- kit: copy offline builds into a project
def _inside(p, roots):
    p = Path(p).resolve()
    return any(p.is_relative_to(Path(r).resolve()) for r in roots)


def _size(p):
    p = Path(p)
    return p.stat().st_size if p.is_file() else sum(f.stat().st_size for f in p.rglob("*") if f.is_file())


def _tag(rel, kind):
    rel = rel.replace("\\", "/")
    if rel.endswith(".css"):
        return f'<link rel="stylesheet" href="{rel}">'
    if kind == "esm" or rel.endswith((".mjs", ".module.js")):
        return f'<script type="module">import * as lib from "./{rel}";</script>'
    if rel.endswith(".js"):
        return f'<script src="{rel}"></script>'
    return f"(ملفات) {rel}"


_ESM_IMPORT = re.compile(r"""(?:\bfrom|\bimport)\s*\(?\s*['"](\.{1,2}/[^'"?#]+)['"]""")


def _esm_imports(entry, roots):
    """An ES module's relative imports, recursively. three.module.js imports ./three.core.js; copying the entry alone made
    the offline film 404 (measured 2026-11-14). Returns (inside, outside): files inside the entry's own folder and the
    library roots, which kit copies keeping their relative paths, and imports that point above that folder (reported)."""
    base = Path(entry).resolve().parent
    todo, seen, inside, outside = [Path(entry).resolve()], set(), [], []
    while todo:
        f = todo.pop()
        if f in seen or not f.is_file() or f.stat().st_size > KIT_CAP:
            continue
        seen.add(f)
        for rel in _ESM_IMPORT.findall(f.read_text(encoding="utf-8", errors="replace")):
            dep = (f.parent / rel).resolve()
            if not dep.is_file():
                continue
            if dep.is_relative_to(base) and _inside(dep, roots):
                if dep not in inside:
                    inside.append(dep)
                todo.append(dep)
            elif rel not in outside:
                outside.append(rel)
    return inside, outside


def lib_kit(project_dir, ids):
    """Copy each library's ready offline files (+ licence) into project_dir\\vendor\\<id>. Returns (report_md, ok)."""
    lib = library()
    roots = lib.get("roots") or []
    dest = Path(project_dir) / "vendor"
    lines, ok, notes = [], True, []
    for ident in ids:
        try:
            it = _by_id(lib["items"], ident)
        except KeyError as e:
            lines.append(f"✗ {e}")
            ok = False
            continue
        files = [f for f in [it.get("offline_entry")] + list(it.get("extras") or []) if f]
        if not files:
            lines.append(f"✗ {it['id']}: مفيش نسخة جاهزة من غير نت ({it.get('readiness')}). {it.get('requires') or ''}".strip())
            ok = False
            continue
        bad = [f for f in files if not _inside(f, roots) or not Path(f).exists()]
        if bad:
            lines.append(f"✗ {it['id']}: الملف مش موجود أو برّه مجلد المكتبات: {bad[0]}")
            ok = False
            continue
        entry = it.get("offline_entry")
        esm = bool(entry) and (it.get("offline_kind") == "esm" or str(entry).endswith((".mjs", ".module.js")))
        deps, outside = _esm_imports(entry, roots) if esm else ([], [])
        total = sum(_size(f) for f in files) + sum(_size(f) for f in deps)
        if total > KIT_CAP:
            lines.append(f"✗ {it['id']}: الحجم {total / 1e6:.0f}MB أكبر من الحد ({KIT_CAP / 1e6:.0f}MB)")
            ok = False
            continue
        d = dest / it["id"]
        d.mkdir(parents=True, exist_ok=True)
        tags = []
        for f in files:
            src = Path(f)
            if src.is_dir():
                shutil.copytree(src, d / src.name, dirs_exist_ok=True)
                tags.append(_tag(f"vendor/{it['id']}/{src.name}/", it.get("offline_kind")))
            else:
                shutil.copy2(src, d / src.name)
                tags.append(_tag(f"vendor/{it['id']}/{src.name}", it.get("offline_kind")))
        base = Path(entry).resolve().parent if esm else None
        for dep in deps:                                  # same relative path next to the entry, so ./x.js resolves offline
            (d / dep.relative_to(base)).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(dep, d / dep.relative_to(base))
        lic = it.get("license_file")
        if lic and Path(lic).is_file() and _inside(lic, roots):
            shutil.copy2(lic, d / "LICENSE.txt")
        warn = "" if it.get("commercial_ok") == "yes" else f" ⚠ الرخصة: {it.get('license')} ({it.get('commercial_ok')})"
        more = ""
        if deps:
            more += "\n  + معاه اللي بيستورده: " + "، ".join(dep.relative_to(base).as_posix() for dep in deps)
        if outside:                                       # can't work offline: say so instead of a ✓
            ok = False
            more += "\n  ✗ بيستورد ملفات برّه فولدره، فماتنسختش والفيلم مش هيشتغل من غير نت: " + "، ".join(outside)
        if esm:
            more += ("\n  ⚠ ES module: كروم العادي بيمنعه من file://. افتح الفيلم بمحرك الرندر (--allow-file-access-from-files)"
                     " أو من سيرفر محلي (python -m http.server).")
        lines.append(f"{'✗' if outside else '✓'} {it['id']} ({it.get('license')}, {total / 1e3:.0f}KB){warn}\n  " + "\n  ".join(tags) + more)
        notes.append(f"- {it['name']}: {it.get('license')} — {it.get('source')}")
    if notes:
        (dest / "LICENSES.md").parent.mkdir(parents=True, exist_ok=True)
        old = (dest / "LICENSES.md").read_text(encoding="utf-8") if (dest / "LICENSES.md").exists() else "# مكتبات متضمّنة في المشروع\n"
        new = [n for n in notes if n not in old]
        (dest / "LICENSES.md").write_text(old.rstrip("\n") + "\n" + "\n".join(new) + "\n", encoding="utf-8")
    return "\n".join(lines) + (f"\n\nالملفات في: {dest}" if notes else ""), ok


# ---------------------------------------------------------------- studio
def seven_zip():
    return shutil.which("7z") or next((p for p in SEVEN_ZIP if Path(p).is_file()), None)


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def studio_dir(it):
    return STUDIO_HOME / (it.get("unpack_as") or it["id"])      # programs from one archive share one folder


def studio_exe(it):
    d = studio_dir(it)
    if not d.is_dir():
        return None
    exact = d / it["exe"].replace("\\", "/")
    if exact.is_file():                   # the inner path recorded during the analysis wins over a same-named copy
        return exact
    name = Path(it["exe"]).name.lower()
    hits = sorted((p for p in d.rglob("*") if p.is_file() and p.name.lower() == name), key=lambda p: len(p.parts))
    return hits[0] if hits else None


def studio_state(it):
    if studio_exe(it):
        return "جاهز"
    return "متاح للفك" if Path(it["archive"]).is_file() else "الأرشيف مش موجود"


def studio_install(ident, on_line=None):
    """Verify the archive's sha256, then unpack it with 7-Zip into STUDIO_HOME\\<id>. Never runs the program."""
    it = _by_id(studio_items(), ident)
    exe = studio_exe(it)
    if exe:
        return f"✓ {it['name']} جاهز بالفعل: {exe}", True
    arc = Path(it["archive"])
    if not arc.is_file():
        return f"✗ الأرشيف مش موجود: {arc}", False
    z = seven_zip()
    if not z:
        return "✗ 7-Zip مش موجود على الجهاز", False
    if on_line:
        on_line(f"بحسب بصمة {arc.name}…")
    got = sha256_file(arc)
    want = (it.get("archive_sha256") or "").lower()
    if want and got != want:
        return f"✗ البصمة مش مطابقة للي اتسجّلت وقت التحليل، فمش هفك الأرشيف.\n  المتوقع {want}\n  الموجود {got}", False
    d = studio_dir(it)
    tmp = d.with_name(d.name + ".__new__")
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    if on_line:
        on_line(f"بفك {arc.name} في {d}…")
    p = subprocess.run([z, "x", "-y", "-bso0", "-bsp0", f"-o{tmp}", str(arc)], capture_output=True, text=True,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if p.returncode != 0:
        shutil.rmtree(tmp, ignore_errors=True)
        return f"✗ 7-Zip فشل (exit {p.returncode}): {(p.stderr or p.stdout)[-600:]}", False
    shutil.rmtree(d, ignore_errors=True)
    tmp.rename(d)
    exe = studio_exe(it)
    if not exe:
        return f"✗ اتفك، بس {Path(it['exe']).name} مش لاقيه جوه {d}", False
    return f"✓ {it['name']} {it.get('version', '')} اتفك واتحقق من بصمته ({got[:16]}…)\n  {exe}", True


def studio_cmd(ident, args):
    """[exe, *args] for an unpacked program; raises if it isn't unpacked yet."""
    it = _by_id(studio_items(), ident)
    exe = studio_exe(it)
    if not exe:
        raise FileNotFoundError(f"{it['name']} لسه مش متفك. شغّل install {it['id']} الأول.")
    if not all(isinstance(x, str) for x in args):
        raise ValueError("args لازم تبقى نصوص")
    if exe.suffix.lower() in (".cmd", ".bat") and any(ch in "".join(args) for ch in '&|^<>%"\r\n'):
        # cmd.exe re-parses a batch file's arguments (BatBadBut): metacharacters could run other commands
        raise ValueError('البرنامج ده ملف .cmd، فالمعاملات اللي فيها & | ^ < > % " مش مسموحة.')
    return [str(exe)] + list(args), exe.parent


# ---------------------------------------------------------------- speech sync: time follows the words
# Idea studied in hypit (Apache-2.0 with resale/SaaS limits, so no code was taken; this is our own implementation):
# the script carries NO seconds, only marks on words; word times come from the real recording (WhisperX / faster-whisper),
# a monotone DP aligns script words to transcript words, and every cue is computed from the words. Re-record or edit a
# line and the captions, cuts and effects follow on their own.
#   @{name} … @{/name}  a range        @{name!}  a moment (start of the next word)        ||  or a new line = caption break
COST_SPLIT, COST_MISSING, COST_EXTRA = 0.055, 0.5, 0.35
_SYNC_TOKEN = re.compile(r"\|\||\n|@\{(/?)([^}!\s]+)(!?)\}|(?:(?!@\{)[^\s|])+")    # a word stops at a glued mark
_AR_SYNC = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ة": "ه", "ى": "ي", "ؤ": "و", "ئ": "ي"})


def norm_word(w):
    w = re.sub(r"[ً-ٰٟـ]", "", str(w).lower()).translate(_AR_SYNC)
    return re.sub(r"[^\w]", "", w)


def parse_script(text):
    """-> (words, ranges {name: [i0, i1]}, moments {name: i}, lines [[i0, i1]]) with word indexes."""
    words, ranges, moments, opened, lines, line_start = [], {}, {}, {}, [], 0
    for m in _SYNC_TOKEN.finditer(text):
        tok = m.group(0)
        if tok in ("||", "\n"):
            if len(words) > line_start:
                lines.append([line_start, len(words) - 1])
            line_start = len(words)
        elif m.group(2):
            name = m.group(2)
            if m.group(3):
                moments[name] = len(words)
            elif m.group(1):
                if name not in opened:
                    raise ValueError(f"العلامة @{{/{name}}} مالهاش بداية")
                ranges[name] = [opened.pop(name), len(words) - 1]
            else:
                opened[name] = len(words)
        else:
            n = norm_word(tok)
            if n:
                words.append({"w": tok, "n": n})
    if len(words) > line_start:
        lines.append([line_start, len(words) - 1])
    if opened:
        raise ValueError("علامات مفتوحة من غير قفلة: " + ", ".join(opened))
    return words, ranges, moments, lines


def load_transcript_words(path):
    """Word list [{'w','n','start','end'}] from WhisperX / faster-whisper JSON (segments[].words, word_segments, or a list)."""
    d = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if isinstance(d, dict):
        raw = d.get("word_segments") or [w for s in d.get("segments", []) for w in (s.get("words") or [])]
    else:
        raw = d
    out = []
    for w in raw:
        text = w.get("word") if "word" in w else w.get("text", "")
        n = norm_word(text)
        if n:
            s, e = w.get("start"), w.get("end")
            out.append({"w": text.strip(), "n": n, "start": float(s) if s is not None else None,
                        "end": float(e) if e is not None else None})
    if not out:
        raise ValueError("ملف الكلمات فاضي أو مش بصيغة WhisperX / faster-whisper")
    return out


def _edit_ratio(a, b):
    if a == b:
        return 0.0
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return min(1.0, prev[-1] / max(len(a), len(b)))


def align(script, spoken):
    """Monotone DP, script words S vs transcript words T. Returns, per script word, the list of T indexes it took."""
    n, m = len(script), len(spoken)
    band = max(60, abs(n - m) + 60)
    INF = float("inf")
    cost = [[INF] * (m + 1) for _ in range(n + 1)]
    back = [[None] * (m + 1) for _ in range(n + 1)]
    cost[0][0] = 0.0
    S, T = [w["n"] for w in script], [w["n"] for w in spoken]
    for i in range(n + 1):
        centre = i * m // max(n, 1)
        for j in range(max(0, centre - band), min(m, centre + band) + 1):
            c = cost[i][j]
            if c == INF:
                continue
            steps = []
            if i < n and j < m:
                steps.append((i + 1, j + 1, _edit_ratio(S[i], T[j]), "sub"))
            if i < n:
                steps.append((i + 1, j, COST_MISSING, "miss"))
            if j < m:
                steps.append((i, j + 1, COST_EXTRA, "extra"))
            if i < n and j + 1 < m and S[i] == T[j] + T[j + 1]:
                steps.append((i + 1, j + 2, COST_SPLIT, "1:2"))
            if i + 1 < n and j < m and S[i] + S[i + 1] == T[j]:
                steps.append((i + 2, j + 1, COST_SPLIT, "2:1"))
            for a, b, k, kind in steps:
                if c + k < cost[a][b]:
                    cost[a][b], back[a][b] = c + k, (i, j, kind)
    if cost[n][m] == INF:
        raise ValueError("المحاذاة فشلت: السكريبت والتفريغ مختلفين جدًا")
    took = [[] for _ in range(n)]
    i, j = n, m
    while (i, j) != (0, 0):
        pi, pj, kind = back[i][j]
        if kind == "sub" and _edit_ratio(S[pi], T[pj]) < 0.5:
            took[pi].append(pj)
        elif kind == "1:2":
            took[pi] += [pj, pj + 1]
        elif kind == "2:1":
            took[pi].append(pj)
            took[pi + 1].append(pj)
        i, j = pi, pj
    return took


def time_words(script, spoken, took):
    """Start/end per script word: from its transcript words, else spread between known neighbours by letter count."""
    for w, ids in zip(script, took):
        st = [spoken[k]["start"] for k in ids if spoken[k]["start"] is not None]
        en = [spoken[k]["end"] for k in ids if spoken[k]["end"] is not None]
        w["start"], w["end"], w["matched"] = (min(st), max(en), True) if st and en else (None, None, False)
    known = [i for i, w in enumerate(script) if w["start"] is not None]
    if not known:
        raise ValueError("مفيش ولا كلمة اتطابقت بتوقيت")
    i = 0
    while i < len(script):
        if script[i]["start"] is not None:
            i += 1
            continue
        j = i
        while j < len(script) and script[j]["start"] is None:
            j += 1
        left = script[i - 1]["end"] if i > 0 else max(0.0, script[j]["start"] - 0.4 * (j - i)) if j < len(script) else 0.0
        right = script[j]["start"] if j < len(script) else left + 0.4 * (j - i)
        right = max(right, left)
        total = sum(len(script[k]["n"]) for k in range(i, j)) or 1
        t = left
        for k in range(i, j):
            d = (right - left) * len(script[k]["n"]) / total
            script[k]["start"], script[k]["end"] = round(t, 3), round(t + d, 3)
            t += d
        i = j
    return script


def _srt_time(t):
    ms = int(round(max(0.0, t) * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def speech_sync(script_text, words_path, fps=30):
    """Everything the timeline needs, in seconds and frames, plus the SRT text. Pure: writes nothing."""
    script, ranges, moments, lines = parse_script(script_text)
    if not script:
        raise ValueError("السكريبت مفيهوش كلام")
    spoken = load_transcript_words(words_path)
    took = align(script, spoken)
    time_words(script, spoken, took)
    fr = lambda t: int(round(t * fps))
    end_all = script[-1]["end"]
    out_ranges = {k: {"start": script[a]["start"], "end": script[b]["end"], "start_f": fr(script[a]["start"]),
                      "end_f": fr(script[b]["end"]), "text": " ".join(w["w"] for w in script[a:b + 1])} for k, (a, b) in ranges.items()}
    out_moments = {k: {"t": script[i]["start"] if i < len(script) else end_all,
                       "f": fr(script[i]["start"] if i < len(script) else end_all)} for k, i in moments.items()}
    caps, srt = [], []
    for n, (a, b) in enumerate(lines, 1):
        s, e = script[a]["start"], max(script[b]["end"], script[a]["start"] + 0.3)
        if caps and s < caps[-1]["end"]:
            s = caps[-1]["end"]
        caps.append({"start": round(s, 3), "end": round(e, 3), "text": " ".join(w["w"] for w in script[a:b + 1])})
        srt.append(f"{n}\n{_srt_time(s)} --> {_srt_time(e)}\n{caps[-1]['text']}\n")
    matched = sum(1 for w in script if w["matched"])
    return {"fps": fps, "words": [{"w": w["w"], "start": w["start"], "end": w["end"], "matched": w["matched"]} for w in script],
            "ranges": out_ranges, "moments": out_moments, "captions": caps,
            "stats": {"script_words": len(script), "spoken_words": len(spoken), "matched": matched,
                      "match_ratio": round(matched / len(script), 3)}}, "\n".join(srt)


def speech_sync_files(script_path, words_path, out_dir, fps=30):
    res, srt = speech_sync(Path(script_path).read_text(encoding="utf-8-sig"), words_path, fps)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "sync.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "captions.srt").write_text(srt, encoding="utf-8")
    st = res["stats"]
    warn = "" if st["match_ratio"] >= 0.8 else "\n⚠ أقل من 80% من الكلمات اتطابقت: راجع إن السكريبت هو نفس الكلام المتسجّل."
    rows = "\n".join(f"- {k}: {v['start']:.2f}→{v['end']:.2f} ث (فريم {v['start_f']}→{v['end_f']})" for k, v in res["ranges"].items())
    moms = "\n".join(f"- {k}: {v['t']:.2f} ث (فريم {v['f']})" for k, v in res["moments"].items())
    return (f"✓ اتطابق {st['matched']}/{st['script_words']} كلمة ({st['match_ratio']:.0%}) على {st['spoken_words']} كلمة متسجّلة.{warn}\n"
            f"المديات:\n{rows or '- (مفيش)'}\nاللحظات:\n{moms or '- (مفيش)'}\n"
            f"الكابشن: {len(res['captions'])} سطر.\nالملفات: {out / 'sync.json'} و{out / 'captions.srt'}")


# ---------------------------------------------------------------- Markdown views (what the model reads)
def md_studio_list():
    rows = ["| id | البرنامج | النسخة | الحالة | بيعمل إيه |", "|---|---|---|---|---|"]
    for it in studio_items():
        rows.append(f"| `{it['id']}` | {it['name']} | {it.get('version', '')} | {studio_state(it)} | {it.get('use_ar', '')} |")
    return "\n".join(rows) + f"\n\nالفك بيحصل في `{STUDIO_HOME}`. التفاصيل والأوامر: show ID."


def md_studio_show(ident):
    it = _by_id(studio_items(), ident)
    ex = "\n".join(f"  - `{e}`" for e in it.get("examples") or [])
    return (f"## {it['name']} {it.get('version', '')} (`{it['id']}`)\n- الحالة: {studio_state(it)}"
            f"{' — ' + str(studio_exe(it)) if studio_exe(it) else ''}\n- الأرشيف: `{it['archive']}`\n- البرنامج جواه: `{it['exe']}`"
            f"\n- الرخصة: {it.get('license', '?')}\n- التوقيع: {it.get('signed', '?')}\n- بيعمل إيه: {it.get('use_ar', '')}"
            f"\n- الاستخدام: {it.get('cli_usage', '')}\n- أمثلة:\n{ex}\n- محتاج جنبه: {it.get('deps', '')}"
            + (f"\n- ⚠ تنبيهات: {it['cautions']}" if it.get("cautions") else "")
            + f"\n- الدليل: {it.get('evidence', '')}")


READINESS_AR = {"ready-offline": "✓", "needs-build": "يحتاج بناء", "needs-install": "يحتاج تثبيت", "reference-only": "مرجع بس",
                "needs-unpack": "جوه أرشيف (يتفك الأول)"}


def md_lib_find(query, limit=8, category=None):
    hits = lib_find(query, limit, category)
    if not hits:
        return f"مفيش نتايج لـ «{query}». جرّب كلمة إنجليزي (animation, particles, shader, text, 3d, lottie, video)."
    rows = ["| id | الاسم | النوع | الرخصة | جاهز من غير نت | ده إيه |", "|---|---|---|---|---|---|"]
    for it in hits:
        ready = "✓" if it.get("offline_entry") else READINESS_AR.get(it.get("readiness"), it.get("readiness") or "؟")
        rows.append(f"| `{it['id']}` | {it.get('name')} | {it.get('category')} | {it.get('license')} | {ready} | {it.get('what_ar', '')} |")
    return "\n".join(rows) + "\n\nshow ID للتفاصيل، وkit ID… ينسخ النسخة الجاهزة لمجلد vendor في مجلد الشغل."


def md_lib_show(ident):
    it = _by_id(lib_items(), ident)
    keys = ("category", "lang", "license", "commercial_ok", "readiness", "requires", "cli", "offline_entry", "source", "installed_skill")
    body = "\n".join(f"- {k}: {it[k]}" for k in keys if it.get(k))
    extras = "\n".join(f"  - {e}" for e in it.get("extras") or [])
    return (f"## {it.get('name')} (`{it['id']}`)\n{it.get('what_ar', '')}\n\n**التنين الذهبي يستخدمه إزاي:** {it.get('use_ar', '')}\n\n"
            f"{body}" + (f"\n- ملفات إضافية:\n{extras}" if extras else "") + f"\n- الدليل: {it.get('evidence') or it.get('license_evidence') or ''}")


def stats():
    items = lib_items()
    progs = studio_items()
    return {"library": len(items), "ready_offline": sum(1 for i in items if i.get("offline_entry")),
            "studio": len(progs), "studio_ready": sum(1 for p in progs if studio_exe(p))}


# ---------------------------------------------------------------- CLI
def main(argv):
    if len(argv) < 2 or argv[0] not in ("studio", "lib", "sync") or argv[1] in ("-h", "--help"):
        print(__doc__)
        return 0 if len(argv) >= 2 else 2
    area, act, rest = argv[0], argv[1], argv[2:]
    try:
        if area == "sync":                     # sync SCRIPT WORDS_JSON OUT_DIR [--fps N]
            args = [act] + rest
            fps = 30
            if "--fps" in args:
                i = args.index("--fps")
                fps = int(args[i + 1])
                args = args[:i] + args[i + 2:]
            if len(args) != 3:
                print(__doc__)
                return 2
            print(speech_sync_files(args[0], args[1], args[2], fps))
            return 0
        if area == "studio":
            if act == "list":
                print(md_studio_list())
            elif act == "show" and rest:
                print(md_studio_show(rest[0]))
            elif act == "install" and rest:
                out, ok = studio_install(rest[0], on_line=print)
                print(out)
                return 0 if ok else 1
            elif act == "cmd" and rest:
                cmd, _ = studio_cmd(rest[0], rest[1:])
                print(subprocess.list2cmdline(cmd))
            else:
                print(__doc__)
                return 2
        else:
            if act == "find" and rest:
                limit = 8
                if "--limit" in rest:
                    i = rest.index("--limit")
                    limit = int(rest[i + 1])
                    rest = rest[:i] + rest[i + 2:]
                print(md_lib_find(" ".join(rest), limit))
            elif act == "show" and rest:
                print(md_lib_show(rest[0]))
            elif act == "kit" and len(rest) >= 2:
                out, ok = lib_kit(rest[0], rest[1:])
                print(out)
                return 0 if ok else 1
            elif act == "stats":
                print(json.dumps(stats(), ensure_ascii=False))
            else:
                print(__doc__)
                return 2
    except (KeyError, FileNotFoundError, ValueError) as e:
        print(f"✗ {e.args[0] if e.args else e}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
