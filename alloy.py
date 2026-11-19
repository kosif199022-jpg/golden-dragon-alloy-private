#!/usr/bin/env python3
"""التنين الذهبي — السبيكة (Golden Dragon Alloy): the one door.

Every capability of the golden-dragon repository behind a single command:
  knowledge  find · show · roads · rules · lessons · thinking · tools · ledger · stats
  mind       route (blended: the measured rd.py router + the unified knowledge)
             + every rd.py command passes straight through (plan, brief, check, consent, learn, …)
  engines    x (Black Dragon engine) · ultra · wd · cinema · fusion · gold · run <script>
  health     doctor · selftest

Standard library only. Works on the owner's Windows laptop (full engine room in runtime/)
and in a cloud sandbox without runtime/ (knowledge + mind only; it says what needs the laptop).
"""
from __future__ import annotations

import json
import os
import platform
import re
import shutil
import sqlite3
import subprocess
import sys
import unicodedata
import zlib
from pathlib import Path

VERSION = "4.0.0"
ROOT = Path(__file__).resolve().parent
RUNTIME = ROOT / "runtime"
KB = ROOT / "kb" / "alloy.db"

try:  # Arabic output on a cp1252 Windows console
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# --------------------------------------------------------------------------- Arabic-aware normalisation
_DIAC = re.compile(r"[ؐ-ًؚ-ٰٟۖ-ۭـ]")
_MAP = str.maketrans({
    "أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ى": "ي", "ئ": "ي", "ی": "ي", "ؤ": "و",
    "ة": "ه", "گ": "ك", "ک": "ك", "ڤ": "ف", "پ": "ب", "چ": "ج",
    **{chr(0x0660 + i): str(i) for i in range(10)}, **{chr(0x06F0 + i): str(i) for i in range(10)},
})
_STOP = set("""
في من على الى إلى عن مع و او أو يا ده دي دا اللي الي انا انت انتي هو هي احنا ايه إيه كده كدا عشان علشان لو بس كل
بتاع بتاعي بتاعت عايز عاوز عايزه ممكن يعني لما ازاي إزاي هل ما مش مفيش فيه فيها ليه له لها بيه بها هذا هذه ذلك
the a an to of for in on at by with and or is are be it this that my me i you your please can could would
""".split())


def norm(text: str) -> str:
    """Lower-case, NFKC, no tashkeel/tatweel, unified alef/ya/ta-marbuta, ASCII digits."""
    text = unicodedata.normalize("NFKC", text or "")
    return _DIAC.sub("", text).translate(_MAP).casefold()


def terms(text: str) -> list[str]:
    """Search terms of a request: normalised words minus stop words, plus the form without «ال»/«و»."""
    out: list[str] = []
    for w in re.findall(r"\w+", norm(text)):
        if w in _STOP or len(w) < 2:
            continue
        out.append(w)
        if re.match(r"^[؀-ۿ]", w):
            for pre in ("وال", "بال", "لل", "ال", "و"):
                if w.startswith(pre) and len(w) - len(pre) >= 3:
                    out.append(w[len(pre):])
                    break
    seen, uniq = set(), []
    for t in out:
        if t not in seen:
            seen.add(t)
            uniq.append(t)
    return uniq[:40]


# --------------------------------------------------------------------------- knowledge base
KIND_BOOST = {"road": 1.6, "rule": 1.4, "lesson": 1.3, "thinking": 1.25, "skill": 1.2, "module": 1.2,
              "tool": 1.1, "engine": 1.1, "studio": 1.1, "program": 1.05, "script": 0.9, "reference": 1.0,
              "power": 0.85, "superpower": 0.85, "lib": 0.95, "catalog-skill": 0.75, "memory": 0.6}
HIDDEN_BY_DEFAULT = {"memory"}


def kb_connect() -> sqlite3.Connection:
    if not KB.exists():
        sys.exit(f"✗ القاعدة مش موجودة: {KB} — ابنيها بـ: python -X utf8 forge/blend.py --src <checkout> --out .")
    con = sqlite3.connect(f"file:{KB.as_posix()}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con


def search(query: str, kinds: list[str] | None = None, limit: int = 10, include_hidden: bool = False) -> list[dict]:
    words = terms(query)
    if not words:
        return []
    match = " OR ".join(f'"{w}"*' if len(w) >= 3 else f'"{w}"' for w in words)
    con = kb_connect()
    sql = ("SELECT u.id, u.kind, u.title, u.summary, u.path, u.how, u.status, u.origin, "
           "bm25(fts, 8.0, 4.0, 1.0) AS rank FROM fts JOIN units u ON u.rowid = fts.rowid "
           "WHERE fts MATCH ?")
    args: list = [match]
    if kinds:
        sql += " AND u.kind IN (%s)" % ",".join("?" * len(kinds))
        args += kinds
    elif not include_hidden:
        sql += " AND u.kind NOT IN (%s)" % ",".join("?" * len(HIDDEN_BY_DEFAULT))
        args += sorted(HIDDEN_BY_DEFAULT)
    sql += " ORDER BY rank LIMIT ?"
    args.append(max(limit * 6, 60))
    rows = [dict(r) for r in con.execute(sql, args)]
    for r in rows:
        boost = KIND_BOOST.get(r["kind"], 1.0) * (0.5 if r["status"] in ("superseded", "quarantined") else 1.0)
        r["score"] = round(-r["rank"] * boost, 3)
    rows.sort(key=lambda r: -r["score"])
    return rows[:limit]


def unit(uid: str) -> dict | None:
    con = kb_connect()
    r = con.execute("SELECT * FROM units WHERE id = ?", (uid,)).fetchone()
    if r is None:  # forgiving lookup: by name / path suffix
        r = con.execute("SELECT * FROM units WHERE id LIKE ? OR path LIKE ? ORDER BY length(id) LIMIT 1",
                        (f"%:{uid}", f"%{uid}")).fetchone()
    if r is None:
        return None
    d = dict(r)
    d["body"] = zlib.decompress(d["body"]).decode("utf-8") if d.get("body") else ""
    return d


def print_rows(rows: list[dict], as_json: bool = False) -> None:
    if as_json:
        print(json.dumps(rows, ensure_ascii=False, indent=1))
        return
    if not rows:
        print("مالقيتش حاجة. جرّب كلمات تانية (عربي أو إنجليزي) أو --kind.")
        return
    for i, r in enumerate(rows, 1):
        flag = "" if r.get("status") in (None, "", "active") else f" [{r['status']}]"
        print(f"{i:>2}. [{r['kind']}] {r['id']}{flag} — {r['title'] or ''}")
        if r.get("summary"):
            print(f"     {r['summary'][:180]}")
        where = r.get("how") or r.get("path")
        if where:
            print(f"     ↳ {where}")


# --------------------------------------------------------------------------- engine room (runtime/)
RD = RUNTIME / "scripts" / "rd.py"
ENGINES = {
    "rd": RD,
    "x": RUNTIME / "engine" / "scripts" / "dragon.py",
    "ultra": RUNTIME / "modules" / "ultra" / "scripts" / "dragon.py",
    "wd": RUNTIME / "legacy" / "white-dragon" / "wd.py",
    "cinema": RUNTIME / "modules" / "cinema" / "scripts" / "build.py",
    "fusion": RUNTIME / "apps" / "golden-dragon" / "app" / "dragon_fusion.py",
    "gold": RUNTIME / "apps" / "golden-dragon" / "app" / "golden_tools.py",
    "anatomy": RUNTIME / "apps" / "golden-dragon" / "app" / "anatomy_bridge.py",
    "maint": RUNTIME / "tools" / "dragon-maint",
}
RD_COMMANDS = set("""
understand plan fuse check brief map teach think skills math re repo intel repos chats files guard lock unlock
learn recall retro outcome memory consent ref sync arena md insta ig krita hypit agents docs start gold x why
""".split())


def runtime_ok() -> bool:
    return RD.exists()


def need_runtime(what: str) -> int:
    print(f"✗ «{what}» محتاج غرفة الماكينات (runtime/) ودي مش موجودة هنا.\n"
          "  على لابتوب صاحب الشغل: المهارة المتثبتة فيها runtime/.\n"
          "  في سحابة: نزّل المستودع جوه runtime/ بعد موافقة: "
          "git clone --depth 1 https://github.com/kosif199022-jpg/black-dragon-skill.git runtime")
    return 2


def passthrough(script: Path, args: list[str]) -> int:
    if not script.exists():
        return need_runtime(script.name)
    return subprocess.call([sys.executable, "-X", "utf8", str(script), *args])


# --------------------------------------------------------------------------- commands
def cmd_find(a: list[str]) -> int:
    kinds, limit, as_json, hidden, q = None, 10, False, False, []
    it = iter(a)
    for x in it:
        if x == "--kind":
            kinds = next(it, "").split(",")
        elif x == "--limit":
            limit = int(next(it, "10"))
        elif x == "--json":
            as_json = True
        elif x == "--all":
            hidden = True
        else:
            q.append(x)
    print_rows(search(" ".join(q), kinds, limit, hidden), as_json)
    return 0


def cmd_show(a: list[str]) -> int:
    if not a:
        print("الاستخدام: alloy show <ID أو اسم أو مسار>")
        return 2
    d = unit(a[0])
    if not d:
        print(f"✗ مالقيتش «{a[0]}». دوّر الأول: alloy find \"…\"")
        return 1
    meta = json.loads(d.get("meta") or "{}")
    print(f"# {d['title'] or d['id']}\n- id: {d['id']} · kind: {d['kind']} · status: {d['status']} · origin: {d['origin']}"
          f" · license: {d['license'] or '-'}")
    if d.get("path"):
        print(f"- المكان: {d['path']}")
    if d.get("how"):
        print(f"- التشغيل: {d['how']}")
    srcs = json.loads(d.get("sources") or "[]")
    if len(srcs) > 1:
        label = "نسخ متطابقة بالبايت اتدمجت" if d["kind"] in ("skill", "reference", "module", "memory") else "المصادر اللي اتصهرت فيها"
        print(f"- {label} ({len(srcs)}): " + ", ".join(s.get("path", s.get("ref", "?")) for s in srcs[:8])
              + (" …" if len(srcs) > 8 else ""))
    if meta:
        print("- meta: " + json.dumps(meta, ensure_ascii=False)[:600])
    if d.get("summary"):
        print(f"\n{d['summary']}")
    if d["body"]:
        body = d["body"]
        cut = "--full" not in a and len(body) > 12000
        print("\n" + (body[:12000] + "\n\n… (اتقصّ هنا؛ الباقي بـ --full أو اقرا الملف)" if cut else body))
    return 0


def cmd_kind_search(kind: str, a: list[str], digest: str) -> int:
    if not [x for x in a if not x.startswith("--")]:
        f = ROOT / "references" / digest
        print(f"الملخص المدموج كامل: {f}\n")
        con = kb_connect()
        n = con.execute("SELECT count(*) FROM units WHERE kind = ?", (kind,)).fetchone()[0]
        print(f"{n} وحدة من النوع «{kind}». دوّر جواها: alloy {kind}s \"<كلمات>\"")
        return 0
    return cmd_find([*a, "--kind", kind])


def cmd_tools(a: list[str]) -> int:
    kinds = "tool,script,engine,studio,program,power,superpower,lib,mcp,cmd,re"
    if not a:
        con = kb_connect()
        for k, n in con.execute("SELECT kind, count(*) FROM units WHERE kind IN (%s) GROUP BY kind ORDER BY 2 DESC"
                                % ",".join("?" * len(kinds.split(","))), kinds.split(",")):
            print(f"{n:>6}  {k}")
        print("\nدوّر: alloy tools \"<الشغل>\" · شغّل سكربت: alloy run <id أو مسار جوه runtime/> [args]")
        return 0
    return cmd_find([*a, "--kind", kinds])


_RD_MOD = None


def rd_module():
    """The measured router, loaded in-process (same functions mind/route_eval measures)."""
    global _RD_MOD
    if _RD_MOD is None:
        import importlib.util
        sys.path.insert(0, str(RD.parent))
        spec = importlib.util.spec_from_file_location("rd", RD)
        mod = importlib.util.module_from_spec(spec)
        argv, sys.argv = sys.argv, [str(RD)]
        try:
            spec.loader.exec_module(mod)
        finally:
            sys.argv = argv
        _RD_MOD = mod
    return _RD_MOD


def fused_roads(q: str, prev: str = "") -> dict:
    """Reciprocal-rank fusion of rd.route and the unified knowledge (k=2, w=0.5: fixed before the hidden test,
    which measured top-3 86% vs 80% for the router alone; references/BLEND_REPORT.md)."""
    rd = rd_module()
    u = rd.understand(q)
    pb, _ = rd.route(u["text"], prev=rd.understand(prev)["text"]) if prev else rd.route(u["text"])
    ranked = [p["id"] for _s, p in pb]
    pbs = {p["id"] for p in rd.playbooks()}
    kb = [x for x in (r["id"].split(":", 1)[1] for r in search(u["text"], ["road"], 8)) if x in pbs][:5]
    fused: dict[str, float] = {}
    for i, x in enumerate(ranked[:5]):
        fused[x] = fused.get(x, 0) + 1 / (3 + i)
    for i, x in enumerate(kb):
        fused[x] = fused.get(x, 0) + 0.5 / (3 + i)
    return {"none": not (pb and pb[0][0] >= 2), "rd": ranked[:3], "kb": kb[:3],
            "fused": sorted(fused, key=lambda x: -fused[x])[:3]}


def cmd_route(a: list[str]) -> int:
    q = " ".join(x for i, x in enumerate(a) if not x.startswith("--") and (i == 0 or a[i - 1] != "--prev"))
    prev = a[a.index("--prev") + 1] if "--prev" in a and a.index("--prev") + 1 < len(a) else ""
    if not q:
        print('الاستخدام: alloy route "<الطلب بنصه>" [--prev "<الرسالة اللي قبلها>"]')
        return 2
    rc = 0
    if runtime_ok():
        print("## 🧠 العقل المقاس (rd.py plan)\n")
        sys.stdout.flush()
        rc = passthrough(RD, ["plan", *a])
        try:
            f = fused_roads(q, prev)
            print("\n## 🔀 الطريق المدموج (الراوتر + المعرفة الموحّدة)\n")
            if f["none"]:
                print("- الراوتر شايفه دردشة أو رد قصير (none): ماتبدأش طريق جديد، كمّل اللي قبله.")
            print(f"- الراوتر: {' ← '.join(f['rd']) or '—'} · المعرفة: {' ← '.join(f['kb']) or '—'}")
            print(f"- المدموج: **{' ← '.join(f['fused']) or '—'}**")
            if f["rd"] and f["kb"] and f["rd"][0] != f["kb"][0] and not f["none"]:
                print(f"- ⚠ الاتنين مختلفين في الأول ({f['rd'][0]} ≠ {f['kb'][0]}): اقرا الطريقين "
                      "(`alloy show road:<id>`) واختار بسبب، أو اسأل سؤال واحد باختيارين.")
        except Exception as e:  # never let the blend hide the measured plan
            print(f"\nℹ الطريق المدموج مش متاح هنا ({type(e).__name__}: {e}).")
    else:
        print("ℹ مفيش runtime/ هنا: الطريق من المعرفة الموحّدة بس (من غير الراوتر المقاس).\n")
    # Retrieve only relevant owner corrections, never arbitrary commands.
    try:
        personal = memory_module().recall(q, norm, limit=3)
        if personal:
            print("\\n## 📚 الدروس المتراكمة (من الذاكرة الخاصة)\\n")
            for item in personal:
                print("- " + item["text"][:500])
    except (OSError, ValueError):
        pass
    print("\n## 🔎 من المعرفة الموحّدة (الطرق، والقواعد والدروس اللي تخصه، والمهارات والأدوات)\n")
    print_rows(search(q, ["road"], 3))
    print()
    print_rows(search(q, ["rule", "lesson"], 4))
    print()
    print_rows(search(q, ["skill", "module", "tool", "engine", "studio", "program", "script", "lib"], 5))
    return rc


def cmd_ledger(a: list[str]) -> int:
    if not a:
        con = kb_connect()
        for place, n in con.execute("SELECT substr(place,1,instr(place||'/', '/')-1), count(*) FROM ledger GROUP BY 1"):
            print(f"{n:>6}  {place}")
        print("\nملف بعينه: alloy ledger <مسار في المستودع الأصلي>")
        return 0
    con = kb_connect()
    q = a[0].replace("\\", "/")
    rows = con.execute("SELECT * FROM ledger WHERE path = ? OR path LIKE ? LIMIT 20", (q, f"%{q}%")).fetchall()
    for r in rows:
        print(f"{r['path']}\n  ← راح: {r['place']}  · وحدات: {r['units'] or '-'}  · {r['note'] or ''}")
    if not rows:
        print("✗ مش في الدفتر.")
        return 1
    return 0


def cmd_stats(_a: list[str]) -> int:
    con = kb_connect()
    meta = dict(con.execute("SELECT key, value FROM meta").fetchall())
    print(f"السبيكة v{meta.get('alloy_version', VERSION)} · المصدر {meta.get('source', '?')}")
    print("\nالوحدات حسب النوع:")
    for k, n in con.execute("SELECT kind, count(*) FROM units GROUP BY kind ORDER BY 2 DESC"):
        print(f"{n:>7}  {k}")
    print("\nحسب الحالة:")
    for k, n in con.execute("SELECT status, count(*) FROM units GROUP BY status ORDER BY 2 DESC"):
        print(f"{n:>7}  {k}")
    print(f"\nالدفتر: {con.execute('SELECT count(*) FROM ledger').fetchone()[0]} ملف أصلي متسجّل مكانه.")
    return 0


def where_am_i() -> str:
    if os.name == "nt":
        return "laptop" if (Path.home() / ".claude").exists() else "windows"
    if Path("/mnt/user-data").exists() or Path("/mnt/skills").exists():
        return "claude.ai"
    return "cloud/linux"


def cmd_doctor(_a: list[str]) -> int:
    print(f"🐉 السبيكة v{VERSION} · بايثون {platform.python_version()} · {platform.system()} · المكان: {where_am_i()}")
    print(f"- runtime/: {'✓ موجودة (كل حاجة شغالة)' if runtime_ok() else '✗ مش موجودة: المعرفة والطرق والقواعد والدروس شغالة، والراوتر المقاس والمحركات محتاجين runtime/ (أي ملف runtime/… نصه بيطلع بـ alloy show <المسار>)'}")
    print(f"- kb: {'✓ ' + str(round(KB.stat().st_size / 1e6, 1)) + ' ميجا' if KB.exists() else '✗'}")
    for name, p in ENGINES.items():
        print(f"  · {name:<8} {'✓' if p.exists() else '✗'}  {p.relative_to(ROOT).as_posix()}")
    print("- برامج على الـ PATH: " + " ".join(f"{p}{'✓' if shutil.which(p) else '✗'}"
                                            for p in ("ffmpeg", "ffprobe", "blender", "node", "git", "magick", "rg")))
    mem = Path(os.environ.get("RED_DRAGON_HOME") or Path.home() / ".red-dragon")
    print(f"- ذاكرة التعلّم (مشتركة مع rd.py): {mem} {'✓' if mem.exists() else '(لسه مااتعملتش)'}")
    return 0


def cmd_run(a: list[str]) -> int:
    if not a:
        print("الاستخدام: alloy run <script-id أو مسار جوه runtime/> [args…]  (ابحث: alloy tools \"…\")")
        return 2
    target, args = a[0], a[1:]
    p = None
    if not target.startswith("script:"):
        cand = RUNTIME / target
        if cand.is_file():
            p = cand
    if p is None:
        d = unit(target if target.startswith("script:") else f"script:{target}")
        if d and d.get("path"):
            p = ROOT / d["path"]
    if p is None or not p.exists():
        print(f"✗ مالقيتش سكربت «{target}». دوّر: alloy tools \"…\"")
        return 1
    rel = p.relative_to(ROOT).as_posix()
    if "/library/" in f"/{rel}" and "--yes" not in args:
        print(f"⚠ ده سكربت من مكتبة طرف تالت ({rel}). اقراه الأول، وبعدين أعد الأمر وزوّد --yes.")
        return 3
    args = [x for x in args if x != "--yes"]
    ext = p.suffix.lower()
    if ext == ".py":
        return subprocess.call([sys.executable, "-X", "utf8", str(p), *args])
    if ext in (".js", ".mjs"):
        return subprocess.call(["node", str(p), *args])
    if ext == ".ps1":
        return subprocess.call(["powershell", "-ExecutionPolicy", "Bypass", "-File", str(p), *args])
    if ext == ".sh":
        return subprocess.call(["bash", str(p), *args])
    print(f"✗ نوع مش معروف للتشغيل: {ext}")
    return 1



def memory_module():
    from forge import owner_memory
    return owner_memory


def cmd_memory(a: list[str]) -> int:
    """Persistent, append-only private memory. Never uploads without --push."""
    if not a or a[0] in ("-h", "--help", "help"):
        print("memory: stats | snapshot | recall <words> | remember <text> [--kind correction|fact|rule|decision|outcome] | sync [--push]")
        return 0
    mem = memory_module()
    action, args = a[0], a[1:]
    if action == "stats":
        con = kb_connect()
        historical = con.execute("SELECT COUNT(*) FROM units WHERE kind='memory' OR status='private'").fetchone()[0]
        print(json.dumps({
            "private_memories_in_kb": historical,
            "live_backup_files": len(list((mem.STORE / "live").rglob("*"))) if mem.STORE.exists() else 0,
            "journal_events": len(mem.records(mem.STORE / "journal.jsonl")),
            "private_store": str(mem.STORE),
            "automatic_public_uploads": 0}, ensure_ascii=False, indent=2))
        return 0
    if action == "snapshot":
        print(json.dumps(mem.snapshot(), ensure_ascii=False, indent=2))
        return 0
    if action == "remember":
        kind = "correction"
        if "--kind" in args:
            i = args.index("--kind")
            if i + 1 >= len(args):
                print("missing --kind value", file=sys.stderr)
                return 2
            kind = args[i+1]
            args = args[:i] + args[i+2:]
        try:
            result = mem.remember(" ".join(args), kind=kind)
            if runtime_ok():
                result["live_snapshot"] = mem.snapshot().get("snapshot_files", 0)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        except ValueError as error:
            print(str(error), file=sys.stderr)
            return 2
    if action == "recall":
        found = mem.recall(" ".join(args), norm, limit=6)
        if not found:
            # Older memory records remain in the main KB and are only revealed on explicit recall.
            found = search(" ".join(args), ["memory"], limit=6, include_hidden=True)
        print_rows(found) if found and "id" in found[0] else print(json.dumps(found, ensure_ascii=False, indent=2))
        return 0
    if action == "sync":
        try:
            result = mem.sync(push="--push" in args)
        except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as error:
            print(f"Memory sync rejected: {type(error).__name__}: {error}", file=sys.stderr)
            return 2
        print(json.dumps(result, ensure_ascii=False))
        return 0
    print("Unknown memory action. Use alloy memory help.")
    return 2


def cmd_learn_and_archive(a: list[str]) -> int:
    """Keep the measured old learning path, plus a private snapshot after success."""
    if not runtime_ok():
        print("No runtime; use 'memory remember <text>' for persistent private notes")
        return 2
    rc = passthrough(RD, ["learn", *a])
    if rc == 0:
        try:
            snapshot = memory_module().snapshot()
            print(f"Private learning snapshot: {snapshot.get('snapshot_files', 0)} files (not uploaded)")
        except (OSError, RuntimeError, ValueError) as error:
            print(f"WARNING: learned locally; private snapshot failed: {error}", file=sys.stderr)
            return 1
    return rc


def cmd_selftest(a: list[str]) -> int:
    sys.path.insert(0, str(ROOT / "forge"))
    from selftest import run  # noqa: E402  (forge/selftest.py)
    return run(ROOT, quick="--quick" in a, verbose="-v" in a)


HELP = f"""🐉 التنين الذهبي — السبيكة v{VERSION}  (alloy = الباب الواحد لكل التنين)

المعرفة الموحّدة (كل المستودع في فهرس واحد):
  find "<كلمات>" [--kind K] [--limit N] [--json] [--all]   دوّر في كل حاجة (عربي/إنجليزي/كلام صوت)
  show <ID|اسم|مسار> [--full]                              افتح وحدة: النص والمصدر والرخصة
  roads [كلمات] · rules [كلمات] · lessons [كلمات] · thinking [كلمات] · tools [كلمات]
  ledger [مسار أصلي]                                        كل ملف من المستودع راح فين
  stats                                                     الأعداد
العقل:
  route "<الطلب>" [--prev "<اللي قبله>"]                     الراوتر المقاس + المعرفة الموحّدة
  plan · brief · check · consent · learn · teach · think · understand · chats · files · … (أي أمر rd.py)
المحركات (غرفة الماكينات runtime/):
  x …  (محرك التنين الأسود) · ultra … · wd … · cinema … · fusion … · gold … · anatomy … · rd <أي أمر>
  run <script-id أو مسار> [args]
الصحة:
  doctor · selftest [--quick] · memory stats|snapshot|recall|remember|sync
"""


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(HELP)
        return 0
    cmd, rest = argv[0], argv[1:]
    table = {
        "find": cmd_find, "show": cmd_show, "route": cmd_route, "ledger": cmd_ledger, "stats": cmd_stats,
        "doctor": cmd_doctor, "selftest": cmd_selftest, "run": cmd_run, "tools": cmd_tools,
        "memory": cmd_memory, "learn": cmd_learn_and_archive,
        "roads": lambda a: cmd_kind_search("road", a, "ROADS.md"),
        "rules": lambda a: cmd_kind_search("rule", a, "RULES.md"),
        "lessons": lambda a: cmd_kind_search("lesson", a, "LESSONS.md"),
        "thinking": lambda a: cmd_kind_search("thinking", a, "THINKING.md"),
        "version": lambda a: print(VERSION) or 0,
    }
    if cmd in table:
        return table[cmd](rest) or 0
    if cmd in ENGINES and ENGINES[cmd].suffix == ".py":
        return passthrough(ENGINES[cmd], rest)
    if cmd in RD_COMMANDS:
        return passthrough(RD, [cmd, *rest])
    print(f"✗ أمر مش معروف: {cmd}\n")
    print(HELP)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
