#!/usr/bin/env python3
"""brain — Black Dragon's thinking front door (v10.14): one briefing from every source before any work.

    dragon.py tool brain "ريل تكريم بأغنية وطنية 30 ثانية"        # briefing (Arabic)
    dragon.py tool brain "حلل البرنامج ده" --file C:/x/app.exe     # + reverse-engineering plan for the file
    dragon.py tool brain "..." --json [--no-live]                # machine form; --no-live skips Superpowers/Atlas calls
    dragon.py tool brain learn "الدعاء: مفيش كتابة في الفوتيج" --domain video   # remember a lesson (local state)
    dragon.py tool brain lessons [--domain video]                 # what was learned

A briefing has: the domain(s), the Dragon tools and skills that fit (bundled + installed on this PC), live
Superpowers and Atlas matches, matching project lessons (references/LESSONS.md + learned ones), the 7-stage
ultra-mind loop with the model failure modes that matter for this kind of task, expert-council lenses,
acceptance criteria (how "done" is proven) and approval gates. It reads and suggests; it never executes the plan.
"""
import argparse, json, os, re, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL = HERE.parents[1]
PROTO = json.loads((HERE / "protocol.json").read_text(encoding="utf-8"))
STATE = Path(os.environ.get("DRAGON_STATE") or (Path.home() / ".black-dragon"))
LEARNED = STATE / "lessons.jsonl"
INSTALLED = Path(os.environ.get("DRAGON_SKILLS_DIR") or (Path.home() / ".claude" / "skills"))

# ------------------------------------------------------------------ Arabic-aware tokens
AR_DIAC = re.compile(r"[\u064B-\u0652\u0640]")
STOP = set("في من على عن الى إلى او أو و ده دي اللي عايز عاوز اعمل اعملي عمل لو مع بس كل هو هي انا أنا the a an of to for and or in on with".split())


def norm(s):
    s = AR_DIAC.sub("", s.lower())
    s = re.sub("[إأآا]", "ا", s).replace("ة", "ه").replace("ى", "ي")
    return s


def tokens(s):
    out = []
    for w in re.findall(r"[\w\u0600-\u06FF]+", norm(s)):
        if w.startswith("ال") and len(w) > 4:
            w = w[2:]
        if len(w) > 1 and w not in STOP:
            out.append(w)
    return out


# ------------------------------------------------------------------ domains
DOMAINS = {
    "video":      "فيديو فديو مونتاج مونتاتج ريل ريلز فيلم تكريم قص لقطه لقطات فوتيج تيك توك reel video montage edit film footage cut تسليم رندر",
    "audio":      "صوت اغنيه أغنية موسيقي دعاء تلاوه قران قرآن تفريغ كلمات lufs ميكس audio song music voice tts suno ضوضاء",
    "typography": "خط خطوط كتابه كابشن ترجمه عنوان تايتل تايبوجرافي font caption subtitle title typography srt ass",
    "image":      "صوره صور تصميم بوستر لوجو خلفيه photo image poster logo design thumbnail فوتوشوب psd",
    "motion":     "موشن انيميشن حركه جرافيك motion animation kinetic canvas remotion web",
    "3d":         "بلندر ثلاثي 3d blender رندر منتج render",
    "re":         "حلل تحليل هندسه عكسيه فك برنامج exe dll apk ملف تنفيذي decompile reverse malware باكر سيرفر binary electron",
    "sources":    "نزل حمل تحميل لينك رابط يوتيوب انستجرام ستوك download link stock footage",
    "creative":   "فكره افكار ابداع ابتكار كونسبت حبكه سيناريو قصه هوك idea concept creative story hook",
    "physics":    "احسب حساب فيزياء سرعه سقوط ارتداد فريمات تايم كود bpm easing fov عدسه",
}
DOMAIN_TOK = {d: set(tokens(w)) for d, w in DOMAINS.items()}
COUNCIL_FOR = {"video": ["editing", "cinematography", "directing"], "audio": ["audio"], "typography": ["design"],
               "image": ["design", "cinematography"], "motion": ["design", "editing"], "3d": ["cinematography", "design"],
               "creative": ["directing", "literary"], "re": [], "sources": [], "physics": ["cinematography"]}
FAIL_FOR = {"video": ["counting", "units", "edge_cases", "sycophancy"], "audio": ["units", "mental_arithmetic"],
            "re": ["invented_sources", "early_lock", "long_chain_overconfidence", "stale_knowledge"],
            "physics": ["mental_arithmetic", "units", "counting"], "creative": ["early_lock", "sycophancy"],
            "typography": ["edge_cases"], "image": ["sycophancy"], "motion": ["units"], "3d": ["units"],
            "sources": ["stale_knowledge", "invented_sources"]}
ACCEPT = {
    "video": ["`dragon.py verify FILM.mp4 --duration S --expect 1080x1920` exit 0 (no black, AAC, exact frames)",
              "`dragon.py tool sp qc FILM.mp4 --duration S` PASS (‎-14 LUFS ±1.5، 9:16، 30 fps)",
              "اتفرّج على ورقة كادرات (lyrics-sheet/contact sheet) بعينك قبل ما تقول خلص",
              "⛔ الكتابة على الشاشة: `tool onscreen check CAPTIONS --words words.json --lyrics lyrics.txt` PASS "
              "(كلامه بالحرف أو كلمات متأكّد منها أو الكريدت بس؛ مفيش مصدر = اسأله الأول)"],
    "audio": ["LUFS والذروة متقاسين (verify_media / sp qc)، والأغنية الأصلية MD5 ثابت لو اتنسخت",
              "لو فيه concat: اقرا skills/atlas-picks/joined-audio-transcript-drift وقيس الزحلقة"],
    "typography": ["⛔ مفيش وصف على الشاشة: `tool onscreen check` PASS قبل التصميم النهائي",
                   "تباين النص ≥ 4.5:1 (7:1 أحسن فوق فوتيج) — skills/atlas-picks/legibility-contrast-and-spacing",
                   "العربي متشكّل صح (font-doctor) ومقروء على شاشة موبايل"],
    "image": ["الصورة اتشافت بـ view_image، وأبعادها وصيغتها متقاسة"],
    "motion": ["الحركة متحسوبة (tool physics ease/spring) والفريمات متعدّة مش متخمّنة"],
    "3d": ["blender-pro validate قبل render، والمعاينة اتشافت قبل الرندر الكامل"],
    "re": ["كل ادعاء له مخرج أداة (Evidence) — `tool re investigate FILE --out DIR`",
           "التقرير بيفصل: اتأكد بدليل / استنتاج / مجهول، وأي أداة مش مناسبة مكتوب سببها"],
    "sources": ["كل ملف متنزّل مقاس (المدة والأبعاد) ومصدره في sources.txt مع الرخصة"],
    "creative": ["3 أفكار متباعدة + كليشيهات مرفوضة، والفكرة المختارة عدّت `tool creativity audit`"],
    "physics": ["كل رقم من `tool physics` مش من الذاكرة"],
}
GATES = ["أي أداة Higgsfield بتخصم رصيد: موافقة على الأداة والسعر بالظبط كل مرة (`tool hf check` ثم `tool hf ask`)",
         "أي صرف تاني (Kling/Suno/ElevenLabs)", "نشر أو push", "تثبيت برامج أو حزم",
         "مسح أو الكتابة فوق ملفات المستخدم", "أدوات وقت التشغيل في الهندسة العكسية (frida/pe-sieve/x64dbg/mitmdump/adb)"]


def classify(q):
    t = set(tokens(q))
    scores = {d: len(t & k) for d, k in DOMAIN_TOK.items()}
    ds = [d for d, s in sorted(scores.items(), key=lambda x: -x[1]) if s]
    return ds[:3] or ["video"]


# ------------------------------------------------------------------ sources
def skill_rows(root, origin):
    rows = []
    if not root.is_dir():
        return rows
    for md in list(root.glob("*/SKILL.md")) + list(root.glob("*/*/SKILL.md")):
        try:
            head = md.read_text(encoding="utf-8", errors="replace")[:3000]
        except OSError:
            continue
        name = re.search(r"^name:\s*(.+)$", head, re.M)
        desc = re.search(r"^description:\s*(.+?)(?=^\w[\w-]*:|^---)", head, re.M | re.S)
        rows.append({"name": (name.group(1).strip().strip('"') if name else md.parent.name), "origin": origin,
                     "path": str(md), "text": (desc.group(1) if desc else head[:600])})
    return rows


def rank(rows, q, key="text", limit=5):
    qt = set(tokens(q))
    scored = []
    for r in rows:
        rt = set(tokens(r["name"] + " " + r[key]))
        s = len(qt & rt) + 2 * len(qt & set(tokens(r["name"])))
        if s:
            scored.append((s, r))
    scored.sort(key=lambda x: -x[0])
    return [dict(r, score=s) for s, r in scored[:limit]]


def dragon_tools():
    src = (SKILL / "scripts" / "dragon.py").read_text(encoding="utf-8")
    block = src.split("TOOLS = {", 1)[1].split("\n}", 1)[0]
    rows = []
    for m in re.finditer(r'^\s*"([\w-]+)":\s*"([^"]+)",?\s*(?:#\s*(.*))?$', block, re.M):
        rows.append({"name": m.group(1), "path": m.group(2), "text": (m.group(3) or "") + " " + m.group(2)})
    return rows


TOOL_DOMAIN = {"video": ["onscreen", "sp", "care", "fetch", "tags", "hf"], "audio": ["song-map", "musicmap", "sp"],
               "typography": ["onscreen", "lyric-ass", "creativity", "atlas"],
               "image": ["visual-forge", "styles"], "motion": ["motion", "physics", "three-frames"], "3d": ["blender-pro", "3d"],
               "re": ["re", "rea-ultra"], "sources": ["hunter615", "hunter", "stock", "fetch"],
               "creative": ["creativity", "arena", "promptlib"], "physics": ["physics", "physics-bake"]}


def lessons(q, domains, limit=6):
    out = []
    f = SKILL / "references" / "LESSONS.md"
    qt = set(tokens(q))
    if f.is_file():
        for line in f.read_text(encoding="utf-8").splitlines():
            if line.startswith("- ") and len(line) > 20:
                s = len(qt & set(tokens(line)))
                if s:
                    out.append((s, {"from": "LESSONS.md", "text": line[2:].strip()[:260]}))
    for row in learned():
        s = len(qt & set(tokens(row["text"]))) + (2 if row.get("domain") in domains else 0)
        if s:
            out.append((s, {"from": f"learned {row.get('date', '')}", "text": row["text"][:260]}))
    out.sort(key=lambda x: -x[0])
    return [r for _, r in out[:limit]]


def learned():
    try:
        return [json.loads(l) for l in LEARNED.read_text(encoding="utf-8").splitlines() if l.strip()]
    except (OSError, ValueError):
        return []


def live(cmd, timeout=90):
    try:
        r = subprocess.run([sys.executable] + cmd + ["--json"], capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=timeout, env=dict(os.environ, PYTHONIOENCODING="utf-8"))
        return json.loads(r.stdout) if r.returncode == 0 else {"error": (r.stderr or r.stdout)[-300:]}
    except (OSError, ValueError, subprocess.TimeoutExpired) as e:
        return {"error": type(e).__name__}


def re_plan(path):
    sys.path.insert(0, str(SKILL / "tools" / "re"))
    try:
        from importlib import util
        spec = util.spec_from_file_location("bd_re", SKILL / "tools" / "re" / "re.py")
        m = util.module_from_spec(spec); spec.loader.exec_module(m)
        return m.plan(path)
    finally:
        sys.path.pop(0)


ATLAS_EN = {"video": "video ffmpeg reels editing", "audio": "audio transcript loudness music", "typography": "typography legibility captions",
            "image": "image photo design", "motion": "motion animation", "3d": "blender 3d", "re": "reverse engineering binary",
            "sources": "download stock footage", "creative": "hooks storyboard", "physics": "animation easing"}


def atlas_query(q, domains):
    """Atlas is indexed in English: an Arabic request is searched by its domains' English words."""
    latin = [w for w in re.findall(r"[A-Za-z][\w-]+", q) if len(w) > 2]
    return " ".join(latin) if len(latin) >= 2 else " ".join(ATLAS_EN.get(d, "") for d in domains[:2])


def connections(q, limit=5):
    """v1990.10: the powers registry (tools/powers) — every connection with its cost gate. Never raises."""
    try:
        from importlib import util
        spec = util.spec_from_file_location("bd_powers", SKILL / "tools" / "powers" / "powers.py")
        m = util.module_from_spec(spec); spec.loader.exec_module(m)
        return m.route(q, limit)
    except Exception as e:  # a broken registry must not break the briefing
        return [{"error": f"{type(e).__name__}: {e}"}]


# ------------------------------------------------------------------ briefing
def brief(q, file=None, use_live=True):
    domains = classify(q + (" exe تحليل" if file else ""))
    if file and "re" not in domains:
        domains = ["re"] + domains
    tools = dragon_tools()
    by_name = {t["name"]: t for t in tools}
    picked = list(dict.fromkeys([n for d in domains for n in TOOL_DOMAIN.get(d, []) if n in by_name]
                                + [t["name"] for t in rank(tools, q, limit=4)]))[:7]
    bundled = skill_rows(SKILL / "skills", "bundled")
    installed = [r for r in skill_rows(INSTALLED, "installed") if r["name"] not in {b["name"] for b in bundled}
                 and r["name"] != "black-dragon"]
    fm = {f["id"]: f for f in PROTO["known_model_failure_modes"]}
    out = {
        "kind": "black-dragon/brain", "query": q, "domains": domains,
        "restate": f"المطلوب في سطر: {q.strip()}",
        "dragon_tools": [{"name": n, "path": by_name[n]["path"], "cmd": f"python scripts/dragon.py tool {n} --help"} for n in picked],
        "skills": [{k: r[k] for k in ("name", "origin", "path", "score")} for r in rank(bundled + installed, q, limit=6)],
        "lessons": lessons(q, domains),
        "stages": [{"id": s["id"], "ar": s["ar"], "checks": s["checks"]} for s in PROTO["stages"]
                   if s["id"] != "alternatives" or {"creative", "image", "motion", "typography"} & set(domains)],
        "failure_guards": [fm[i] for i in dict.fromkeys(i for d in domains for i in FAIL_FOR.get(d, [])) if i in fm][:6],
        "council": {c: PROTO["council_lenses"].get(c, [])[:3] for d in domains for c in COUNCIL_FOR.get(d, [])},
        "skeptic": PROTO.get("skeptic_checks", [])[:4],
        "acceptance": [a for d in domains for a in ACCEPT.get(d, [])],
        "confidence_language": PROTO.get("confidence_scale", []),
        "gates": GATES, "executed": False,
    }
    if file:
        out["re_plan"] = re_plan(file)
    out["connections"] = connections(q)          # v1990.10: MCP / cloud / engines / agents / PC control (offline registry)
    if use_live:
        out["superpowers"] = live([str(SKILL / "tools" / "superpowers" / "sp.py"), "find", q, "--limit", "3"])
        out["atlas"] = live([str(SKILL / "tools" / "atlas" / "atlas.py"), "find", atlas_query(q, domains), "--limit", "3"])
    return out


def show(b):
    p = print
    p(f"🧠 {b['restate']}\nالمجال: {' + '.join(b['domains'])}\n")
    p("① مراحل التفكير (ultra-mind):")
    for s in b["stages"]:
        p(f"  • {s['id']}: {s['ar']}")
    if b["failure_guards"]:
        p("\n② أخطاء النماذج اللي تخص الشغلانة دي وإزاي تتجنبها:")
        for f in b["failure_guards"]:
            p(f"  • {f['ar']} ← {f['guard']}")
    if b["lessons"]:
        p("\n③ دروس من شغل قبل كده:")
        for l in b["lessons"]:
            p(f"  • {l['text']}  ({l['from']})")
    p("\n④ أدوات التنين:")
    for t in b["dragon_tools"]:
        p(f"  • {t['name']}  ({t['path']})")
    if b.get("re_plan"):
        rp = b["re_plan"]
        p(f"\n⑤ ملف للتحليل: {rp['target']['kind']} — الترتيب:")
        for i, s in enumerate(rp["steps"], 1):
            p(f"  {i}. {s['tool']}{' 🔒' if s['gate'] else ''} — {s['why']}")
    if b["skills"]:
        p("\n⑥ مهارات تتقري (متضمّنة/متثبتة):")
        for s in b["skills"]:
            p(f"  • {s['name']} [{s['origin']}] {s['path']}")
    sp = b.get("superpowers") or {}
    if sp.get("tools"):
        p("\n⑦ سوبر باور:")
        for t in sp["tools"][:3]:
            p(f"  • {t['id']} [{(t.get('readiness') or {}).get('state')}] {t.get('title_ar') or t.get('title_en','')}")
    at = b.get("atlas")
    if isinstance(at, list) and at:
        p("\n⑧ أطلس (آمن بس):")
        for a in at[:3]:
            p(f"  • {a['skill']} [{a['license']}] {a['path']}")
    if b["council"]:
        p("\n⑨ عدسات المجلس:")
        for dom, lenses in b["council"].items():
            for l in lenses:
                p(f"  • [{dom}] {l['lens']} — {l['question']}")
    p("\n⑩ إمتى نقول خلص (لازم دليل):")
    for a in b["acceptance"]:
        p(f"  ✓ {a}")
    conns = [c for c in b.get("connections") or [] if "error" not in c]
    if conns:
        badge = {"free": "✅", "ask": "🔒", "paid": "💰", "never": "⛔"}
        p("\n⑪ الاتصالات والقدرات (tool powers route):")
        for c in conns:
            p(f"  • {badge.get(c['cost'], '?')} [{c['layer']}] {c['ar']} ({c['id']})")
    p("\n🔒 محتاج موافقة صريحة: " + "، ".join(b["gates"]))
    p("لغة الثقة: " + " · ".join(b["confidence_language"]))


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "learn":
        ap = argparse.ArgumentParser(prog="dragon.py tool brain learn")
        ap.add_argument("text"); ap.add_argument("--domain", choices=sorted(DOMAINS)); ap.add_argument("--source", default="")
        a = ap.parse_args(argv[1:])
        STATE.mkdir(parents=True, exist_ok=True)
        row = {"date": time.strftime("%Y-%m-%d"), "domain": a.domain or classify(a.text)[0], "text": a.text.strip(),
               "source": a.source}
        with LEARNED.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(f"اتسجّل الدرس ({row['domain']}) في {LEARNED}"); return 0
    if argv and argv[0] == "lessons":
        ap = argparse.ArgumentParser(prog="dragon.py tool brain lessons"); ap.add_argument("--domain")
        a = ap.parse_args(argv[1:])
        rows = [r for r in learned() if not a.domain or r.get("domain") == a.domain]
        for r in rows:
            print(f"{r['date']} [{r['domain']}] {r['text']}")
        print(f"{len(rows)} درس · {LEARNED}"); return 0
    ap = argparse.ArgumentParser(prog="dragon.py tool brain", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("query"); ap.add_argument("--file"); ap.add_argument("--json", action="store_true")
    ap.add_argument("--no-live", action="store_true", help="skip Superpowers/Atlas subprocess calls")
    a = ap.parse_args(argv)
    if a.file and not Path(a.file).exists():
        print(f"مش لاقي: {a.file}", file=sys.stderr); return 2
    b = brief(a.query, a.file, use_live=not a.no_live)
    if a.json:
        print(json.dumps(b, ensure_ascii=False, indent=1))
    else:
        show(b)
    return 0


if __name__ == "__main__":
    sys.exit(main())
