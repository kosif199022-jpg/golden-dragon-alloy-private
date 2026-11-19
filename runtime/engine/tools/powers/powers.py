#!/usr/bin/env python3
"""powers — every power and connection of the Black Dragon in one place (v1990.10).

    dragon.py tool powers route "حوّل الفيديو ده لكرتون"     # best routes across ALL layers, with cost gate + exact call
    dragon.py tool powers first "الطلب بكلامه"              # the owner's first-reply skeleton: «فهمت إنك عايز / هعمل / ⏱»
    dragon.py tool powers map [--layer mcp] [--json]         # the whole map (layers: claude-code mcp cloud engine re program skill hub desktop)
    dragon.py tool powers show ID                            # one power in full
    dragon.py tool powers doctor [--mcp] [--json] [--save]   # what is present HERE (programs, paths, skills, modules; --mcp asks `claude mcp list`)

Layers come from tools/powers/powers.json. Cost gates: ✅ free · 🔒 ask (explicit yes each time) · 💰 paid
(exact price + yes + balance before/after) · ⛔ never. The router reads and suggests; it never runs a power.
In a cloud chat, laptop-only powers are shown with their cloud alternative instead of a path that does not exist.
`doctor` only looks: shutil.which, path exists, importlib find_spec, SKILL.md exists, and (opt-in) `claude mcp list`.
"""
import argparse, importlib.util, json, os, re, shutil, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL = HERE.parents[1]
REG_FILE = HERE / "powers.json"
STATE = Path(os.environ.get("DRAGON_STATE") or (Path.home() / ".black-dragon"))
INSTALLED = Path(os.environ.get("DRAGON_SKILLS_DIR") or (Path.home() / ".claude" / "skills"))
BADGE = {"free": "✅ ببلاش", "ask": "🔒 بموافقة", "paid": "💰 مدفوع: السعر + «موافق» + الرصيد قبل وبعد", "never": "⛔ ممنوع"}
LAYERS_ORDER = ["claude-code", "mcp", "cloud", "engine", "re", "program", "skill", "hub", "desktop"]
COST_RANK = {"free": 0, "ask": 1, "paid": 2, "never": 3}

# ------------------------------------------------------------------ Arabic-aware tokens (same rules as tool brain)
AR_DIAC = re.compile(r"[ً-ْـ]")
STOP = set("في من على عن الى إلى او أو و ده دي دا اللي عايز عاوز عايزه اعمل اعملي عمل لو مع بس كل هو هي انا أنا انت "
           "يا ممكن عشان علشان كده بقى the a an of to for and or in on with me my this that please".split())
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
        else:
            if w[:1] in "لبو" and len(w) >= 5 and re.match(r"[؀-ۿ]", w):
                w = w[1:]                      # لكرتون → كرتون ، بلندر stays (5 chars, but see stem match below)
        if len(w) > 1 and w not in STOP:
            out.append(w)
    return out


def _match(a, b):
    """token match: equal, or one is a prefix of the other with ≥ 4 shared letters (Arabic suffixes/plurals)."""
    if a == b:
        return 2
    if min(len(a), len(b)) >= 4 and (a.startswith(b) or b.startswith(a)):
        return 1
    return 0


# ------------------------------------------------------------------ registry
def load():
    reg = json.loads(REG_FILE.read_text(encoding="utf-8"))
    for p in reg["powers"]:
        p["_tok"] = set(tokens(p["triggers"] + " " + p["ar"] + " " + p["en"]))
    return reg


def expand(path):
    return Path(os.path.expandvars(os.path.expanduser(path)))


def place():
    m = os.environ.get("DRAGON_MODE")
    if m in ("pc", "cloud"):
        return m
    if Path("/mnt/user-data").exists() or os.environ.get("CLAUDE_CODE_REMOTE") == "true":
        return "cloud"
    return "pc" if os.name == "nt" or (Path.home() / "OneDrive" / "Desktop" / "التنين الأسود").exists() else "cloud"


def route(q, limit=6, reg=None, where=None):
    reg = reg or load()
    where = where or place()
    qt = tokens(q)
    scored = []
    for p in reg["powers"]:
        s = 0
        for t in qt:
            s += max((_match(t, k) for k in p["_tok"]), default=0)
        if s:
            scored.append((s, p))
    # tie → the cheaper road first (free before ask before paid), then layer order: the money rule in code
    scored.sort(key=lambda x: (-x[0], COST_RANK.get(x[1]["cost"], 9), LAYERS_ORDER.index(x[1]["layer"])))
    out = []
    for s, p in scored[:limit]:
        row = {k: p[k] for k in ("id", "layer", "ar", "how", "cost", "where") if k in p}
        row["score"] = s
        row["skills"] = p.get("skills", [])
        if p["where"] == "pc" and where == "cloud":
            row["here"] = "cloud_alt"
            row["how_here"] = p.get("cloud_alt", "مش متاح هنا")
        else:
            row["here"] = "ok"
            row["how_here"] = p["how"]
        out.append(row)
    return out


# ------------------------------------------------------------------ doctor
def claude_exe():
    w = shutil.which("claude")
    if w:
        exe = Path(w).parent / "node_modules" / "@anthropic-ai" / "claude-code" / "bin" / "claude.exe"
        if exe.exists():
            return str(exe)
    return shutil.which("claude.exe") or w


def mcp_list(timeout=120):
    """`claude mcp list` → {name_lower: state}. Same parse as the desktop app (app.py mcp_list)."""
    exe = claude_exe()
    if not exe:
        return None
    try:
        r = subprocess.run([exe, "mcp", "list"], capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=timeout, cwd=str(Path.home()))
    except (OSError, subprocess.TimeoutExpired):
        return None
    out = {}
    for line in (r.stdout or "").splitlines():
        m = re.match(r"^(.+?): (.+) - (.+)$", line.strip())
        if m:
            st = m.group(3).lower()
            out[m.group(1).strip().lower()] = ("connected" if "connected" in st else "needs-auth" if "auth" in st
                                              else "failed" if "fail" in st else "unknown")
    return out


def probe(p, mcps):
    pr = p.get("probe") or {"type": "none"}
    t = pr["type"]
    if t == "none":
        return "n/a", ""
    if t == "program":
        w = shutil.which(pr["name"])
        return ("present", w) if w else ("missing", pr["name"])
    if t == "path":
        x = expand(pr["path"])
        return ("present", str(x)) if x.exists() else ("missing", str(x))
    if t == "module":
        try:
            ok = importlib.util.find_spec(pr["name"]) is not None
        except (ImportError, ValueError):
            ok = False
        return ("present" if ok else "missing"), pr["name"]
    if t == "skill":
        for root in (SKILL / "skills", INSTALLED):
            if (root / pr["name"] / "SKILL.md").is_file():
                return "present", str(root / pr["name"])
        return "missing", pr["name"]
    if t == "session":   # tools a session injects (desktop app control, Chrome extension): not in `claude mcp list`
        if pr.get("path"):
            x = expand(pr["path"])
            if not x.exists():
                return "missing", str(x)
        return "session", pr.get("hint", "اتأكد بـ ToolSearch جوه الجلسة")
    if t == "mcp":
        if mcps is None:
            return "unchecked", "doctor --mcp (أو ToolSearch في الجلسة)"
        name = pr["name"].lower()
        hits = {k: v for k, v in mcps.items() if name in k}
        if not hits:
            return "missing", pr["name"]
        best = "connected" if "connected" in hits.values() else sorted(hits.values())[0]
        return best, ", ".join(sorted(hits))
    return "n/a", ""


def doctor(use_mcp=False):
    reg = load()
    mcps = mcp_list() if use_mcp else None
    rows = []
    for p in reg["powers"]:
        st, detail = probe(p, mcps)
        rows.append({"id": p["id"], "layer": p["layer"], "state": st, "detail": detail, "cost": p["cost"], "where": p["where"]})
    skills_here = sorted(d.name for d in INSTALLED.iterdir() if (d / "SKILL.md").is_file()) if INSTALLED.is_dir() else []
    bundled = sorted(d.name for d in (SKILL / "skills").iterdir() if (d / "SKILL.md").is_file())
    summary = {}
    for r in rows:
        summary[r["state"]] = summary.get(r["state"], 0) + 1
    return {"kind": "black-dragon/powers-doctor", "date": time.strftime("%Y-%m-%d %H:%M"), "place": place(),
            "mcp_checked": mcps is not None, "mcp_servers": mcps or {}, "summary": summary, "powers": rows,
            "skills_installed": skills_here, "skills_bundled": bundled,
            "skills_installed_not_bundled": [s for s in skills_here if s not in bundled and not s.startswith("black-dragon")]}


# ------------------------------------------------------------------ output
def show_route(q, rows):
    print(f"⚡ الطلب: {q}\n   المكان: {place()}\n")
    if not rows:
        print("مفيش تطابق في السجل. جرّب `tool brain \"…\"` أو `dragon.py find \"…\"`."); return
    for i, r in enumerate(rows, 1):
        print(f"{i}. [{r['layer']}] {r['ar']}  — {BADGE.get(r['cost'], r['cost'])}  ({r['id']})")
        print(f"   {r['how_here']}")
        if r["skills"]:
            print(f"   مهارات: {', '.join(r['skills'])}")
    paid = [r for r in rows if r["cost"] in ("paid", "ask")]
    if paid:
        print("\n🔒 قبل أي واحدة من دول: " + "، ".join(f"{r['id']} ({BADGE[r['cost']].split(':')[0]})" for r in paid))


def to_md(reg, ps):
    L = [f"# كل قدرات واتصالات التنين الأسود — v{reg['version']} ({reg['date']})", "",
         "اتولّد من `tools/powers/powers.json` بأمر `python scripts/dragon.py tool powers map --md`. ماتعدّلش هنا: عدّل السجل وولّد تاني.", "",
         "**التكلفة:** ✅ ببلاش (توكنز بس) · 🔒 بموافقة صريحة كل مرة · 💰 مدفوع: السعر بالظبط من الأداة + «موافق» على المبلغ ده + الرصيد قبل وبعد · ⛔ ممنوع.",
         "**المكان:** pc = لابتوب صاحب التنين (Claude Code أو التطبيق) · cloud = محادثة claude.ai أو Claude Code سحابة · both = الاتنين.",
         f"**القياس:** {reg.get('measured', '')}", "",
         "**الراوتر:** `tool powers route \"<الطلب>\"` · **أول رد:** `tool powers first \"<الطلب>\"` · **الموجود هنا:** `tool powers doctor --mcp`", ""]
    for layer in LAYERS_ORDER:
        grp = [p for p in ps if p["layer"] == layer]
        if not grp:
            continue
        L += [f"## {layer} — {reg['layers'][layer]}", ""]
        for p in grp:
            L.append(f"### {p['ar']} (`{p['id']}`) — {BADGE[p['cost']].split(':')[0]} · {p['where']}")
            L.append(f"- **إزاي:** {p['how']}")
            if p.get("skills"):
                L.append(f"- **مهارات:** {', '.join(p['skills'])}")
            if p.get("cloud_alt"):
                L.append(f"- **في السحابة:** {p['cloud_alt']}")
            L.append("")
    return "\n".join(L)


def first(q, rows):
    print("**فهمت إنك عايز:** " + q.strip() + "  ← (اكتبه بكلامك بعد فك غلطات الكتابة بالصوت، وقول فكّيت إيه بالتخمين)\n")
    print("**هعمل:**")
    for r in rows[:4]:
        print(f"- {r['ar']} ({BADGE[r['cost']].split(':')[0]}) ← {r['id']}")
    print("- أقيس الناتج (verify / view_image / tool genius gate) قبل ما أقول خلص، وأحطه في مجلد الشغل/output")
    print("⏱ التقدير ~N د   ← قدّره من حجم الشغل")
    gates = [r for r in rows[:4] if r["cost"] in ("paid", "ask")]
    if gates:
        print("\n🔒 محتاج موافقتك قبل: " + "، ".join(r["ar"] for r in gates))
    print("\n(بعدها اشتغل على طول، إلا لو الطلب ليه معنيين مختلفين: سؤال واحد بس.)")


def main(argv=None):
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8")
        except Exception:
            pass
    argv = list(sys.argv[1:] if argv is None else argv)
    ap = argparse.ArgumentParser(prog="dragon.py tool powers", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd")
    for name in ("route", "first"):
        s = sub.add_parser(name); s.add_argument("query", nargs="+"); s.add_argument("--limit", type=int, default=6)
        s.add_argument("--json", action="store_true"); s.add_argument("--where", choices=["pc", "cloud"])
    s = sub.add_parser("map"); s.add_argument("--layer", choices=LAYERS_ORDER); s.add_argument("--json", action="store_true")
    s.add_argument("--md", action="store_true", help="markdown reference (references/ALL_POWERS_*.md is generated with this)")
    s = sub.add_parser("show"); s.add_argument("id")
    s = sub.add_parser("doctor"); s.add_argument("--mcp", action="store_true"); s.add_argument("--json", action="store_true")
    s.add_argument("--save", action="store_true", help="write ~/.black-dragon/powers_status.json")
    a = ap.parse_args(argv)
    if not a.cmd:
        ap.print_help(); return 0
    reg = load()
    if a.cmd in ("route", "first"):
        q = " ".join(a.query)
        rows = route(q, a.limit, reg, a.where)
        if a.json:
            print(json.dumps({"query": q, "place": a.where or place(), "routes": rows}, ensure_ascii=False, indent=1))
        elif a.cmd == "route":
            show_route(q, rows)
        else:
            first(q, rows)
        return 0
    if a.cmd == "map":
        ps = [p for p in reg["powers"] if not a.layer or p["layer"] == a.layer]
        if a.json:
            print(json.dumps([{k: v for k, v in p.items() if not k.startswith("_")} for p in ps], ensure_ascii=False, indent=1))
            return 0
        if a.md:
            print(to_md(reg, ps)); return 0
        for layer in LAYERS_ORDER:
            grp = [p for p in ps if p["layer"] == layer]
            if grp:
                print(f"\n## {layer} — {reg['layers'][layer]}")
                for p in grp:
                    print(f"- {p['id']}: {p['ar']}  [{BADGE[p['cost']].split(':')[0]} · {p['where']}]")
        print(f"\n{len(ps)} قدرة. التفاصيل: tool powers show ID")
        return 0
    if a.cmd == "show":
        p = next((p for p in reg["powers"] if p["id"] == a.id), None)
        if not p:
            print(f"مش لاقي {a.id}. القايمة: tool powers map", file=sys.stderr); return 2
        print(json.dumps({k: v for k, v in p.items() if not k.startswith("_")}, ensure_ascii=False, indent=1))
        return 0
    if a.cmd == "doctor":
        d = doctor(a.mcp)
        if a.save:
            STATE.mkdir(parents=True, exist_ok=True)
            (STATE / "powers_status.json").write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
        if a.json:
            print(json.dumps(d, ensure_ascii=False, indent=1)); return 0
        icon = {"present": "✅", "connected": "✅", "session": "🔌", "missing": "❌", "needs-auth": "🔑", "failed": "❌", "unchecked": "…", "n/a": "·", "unknown": "?"}
        print(f"المكان: {d['place']} · {d['date']} · MCP {'اتفحص' if d['mcp_checked'] else 'ماتفحصش (زوّد --mcp)'}")
        for r in d["powers"]:
            print(f"  {icon.get(r['state'], '?')} {r['id']:18s} {r['state']:10s} {r['detail']}")
        print("الخلاصة:", d["summary"])
        if d["skills_installed_not_bundled"]:
            print("مهارات متثبتة برّه الحزمة:", ", ".join(d["skills_installed_not_bundled"]))
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
