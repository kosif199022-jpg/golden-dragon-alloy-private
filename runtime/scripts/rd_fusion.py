"""rd_fusion.py — the Golden Dragon's fusion brain inside the skill itself (v3.4.0).

The fused index (skills, programs, engines, libraries, studio programs, MCP servers), the recipes, the owner's lessons
and the 22 thinking tools live in apps/golden-dragon/app/fusion (built on the owner's laptop by
apps/golden-dragon/forge/build_fusion.py). Until v3.3 only the Windows app used them, through a helper process that
looked for rd.py in ~/.claude/skills/golden-dragon and ran `python` by name, so on claude.ai or a Linux sandbox the
router silently fell back to plain keyword scoring. This module loads the same dragon_fusion.py in this process and
gives it the Red Dragon's own reading of the request (understand + route) directly, so it behaves the same everywhere.
It reads only; nothing is written.

  rd.py fuse brief "<request>"                    depth L0-L3, intent sheet, 3 alternatives, pre-mortem, thinking tools
  rd.py fuse route "<request>"                    best recipe(s), extra units, approvals, warnings
  rd.py fuse check --request "<request>" --draft FILE|-   critic gate on the answer before it is sent
  rd.py fuse find "<words>" [--kind K] [--limit N] · show ID · recipes · lessons "<words>" · doctor · stats
  rd.py fuse tools ["<request>"]                  the thinking tools (all, or the ones picked for a request)
  rd.py fuse protocol                             the 8-step right-first-time ladder and its tools
  rd.py fuse selftest                             offline checks
  rd.py check --request … --draft …               the same as fuse check
"""
import importlib.util
import json
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OVERLAY = ROOT / "mind" / "fusion_overlay.json"      # the skill's own recipes on top of the app's generated data
_df = None


def _overlay():
    try:
        return json.loads(OVERLAY.read_text(encoding="utf-8")) if OVERLAY.is_file() else {}
    except (OSError, ValueError):
        return {}


def _apply_overlay(df):
    """Add the skill's recipes, its playbook->recipe order and task types, before any index is built."""
    ov = _overlay()
    if not ov:
        return
    base = df.recipes()
    have = {r["id"] for r in base}
    df._cache["recipes"] = base + [r for r in ov.get("recipes", []) if r.get("id") not in have]
    m = dict(df.rd_map())
    m.update(ov.get("rd_map") or {})
    df._cache["rd_map"] = m
    df.TASK_TYPE.update(ov.get("task_type") or {})
    df._cache.pop("rix", None)


def module_path():
    """dragon_fusion.py next to its fusion/ data (the app copy); GOLDEN_FUSION_PY overrides."""
    env = os.environ.get("GOLDEN_FUSION_PY")
    for p in ([Path(env)] if env else []) + [ROOT / "apps" / "golden-dragon" / "app" / "dragon_fusion.py"]:
        if p.is_file():
            return p
    return None


def available():
    """False when the copy has no fusion data, or RD_NO_FUSION=1 (selftest: plan must still work without it)."""
    if os.environ.get("RD_NO_FUSION"):
        return False
    p = module_path()
    return bool(p and (p.parent / "fusion" / "index.json").is_file())


def load(rd):
    """The dragon_fusion module, with its Red Dragon reading served by `rd` (this rd.py) in-process."""
    global _df
    if _df is not None:
        return _df
    p = module_path()
    if not p:
        raise FileNotFoundError("dragon_fusion.py مش موجود (apps/golden-dragon/app). النسخة دي من غير عقل الانصهار.")
    here = str(p.parent)
    added = here not in sys.path
    if added:
        sys.path.append(here)             # its sibling golden_tools.py (Arabic tokens + synonyms); last, so it shadows nothing
    try:
        spec = importlib.util.spec_from_file_location("dragon_fusion_rd", p)
        df = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(df)
    finally:
        if added:
            sys.path.remove(here)

    def rd_info(text):
        key = (text or "").strip()
        memo = df._cache.setdefault("rd", {})
        if key in memo:
            return memo[key]
        info = None
        if key:
            try:
                u = rd.understand(key)
                pb, _ = rd.route(u["text"], limit=6)
                info = {"ok": True, "text": u["text"], "playbooks": [[round(float(s), 3), x["id"]] for s, x in pb],
                        "version": getattr(rd, "VERSION", "")}
            except Exception:
                info = None
        memo[key] = info
        return info

    df.rd_info = rd_info
    _apply_overlay(df)
    _df = df
    return df


CHECK_CMD = '`rd.py check --request "<الطلب>" --draft <ملف الرد>`'
DRAFT_HEAD, DRAFT_TAIL = 30_000, 10_000      # characters of a very long answer the critic reads (~0.12 s per KB)


def read_draft(src):
    """(text, warning) of the answer to check: a file, or - for stdin, read as bytes so the console code page never
    garbles Arabic. UTF-16 with a BOM (PowerShell 5.1 `>`), else UTF-8 with or without BOM, else cp1256."""
    raw = sys.stdin.buffer.read() if src == "-" else Path(src).read_bytes()
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return raw.decode("utf-16"), ""
    try:
        return raw.decode("utf-8-sig"), ""
    except UnicodeDecodeError:
        return raw.decode("cp1256", errors="replace"), "⚠ ملف الرد مش UTF-8، فاتقري كـ cp1256 (لو العربي باين غلط احفظه UTF-8)."


def _opt(args, name):
    """--name VALUE or --name=VALUE; None when it is missing or has no value."""
    for i, a in enumerate(args):
        if a == name:
            return args[i + 1] if i + 1 < len(args) else None
        if a.startswith(name + "="):
            return a[len(name) + 1:]
    return None


def _skill_words(text):
    """The app's wording -> the skill's commands."""
    return (text.replace("`fusion check` على ردك (query = الطلب، draft = الرد)", CHECK_CMD + " على ردك")
                .replace("`fusion check`", CHECK_CMD)
                .replace("في draft، والطلب في query", "في --draft، والطلب في --request")
                .replace("studio_run install", "rd.py gold studio install --yes")
                .replace("forge\\build_fusion.py", "apps/golden-dragon/forge/build_fusion.py"))


def brief(rd, request):
    df = load(rd)
    return _skill_words(df.md_brief(request))


def route_md(rd, request):
    return _skill_words(load(rd).md_route(request))


def check_md(rd, request, draft):
    df = load(rd)
    df.rd_info(request)                    # md_check reuses the cached reading
    note = ""
    if len(draft or "") > DRAFT_HEAD + DRAFT_TAIL:   # its word coverage costs ~0.12 s per KB: read the head and the tail
        note = (f"\n- ⚠ الرد طويل ({len(draft) // 1024} KB): الفحص اتعمل على أول {DRAFT_HEAD // 1000} ألف حرف "
                f"وآخر {DRAFT_TAIL // 1000} آلاف بس.")
        draft = draft[:DRAFT_HEAD] + "\n" + draft[-DRAFT_TAIL:]
    return _skill_words(df.md_check(request, draft)) + note


def failed(check_output):
    """True when the critic found something to fix (a «- ✗» line, or the empty-answer message)."""
    return check_output.startswith("✗") or any(ln.startswith("- ✗ ") for ln in check_output.splitlines())


def _route_light(df, request):
    """route() without the extra-unit search (BM25 over ~1100 units). Depth and tools need only the recipes,
    their approvals and the confidence, so `plan` doesn't pay for an index it never shows."""
    real = df.find
    df.find = lambda *a, **k: []
    try:
        return df.route(request)
    finally:
        df.find = real


def depth_and_tools(rd, request, limit=3):
    """(level, why, [tool dicts]) for a request: protocol step ① and the thinking tools picked for it."""
    df = load(rd)
    r = _route_light(df, request)
    top = r["recipes"][0][1] if r["recipes"] else None
    lvl, why = df.depth(r, request)
    return lvl, why, df.thinking_for(request, top, limit=limit), r


def thinking_lines(rd, request):
    """The compact block `rd.py plan` prints: depth, 2-3 thinking tools with their check, and the critic gate."""
    lvl, why, tools, r = depth_and_tools(rd, request)
    out = [f"🧠 سلّم التفكير: العمق {lvl}: {why}"]
    for t in tools:
        first = (t.get("steps_ar") or [""])[0]
        out.append(f"   • {t.get('name_ar', t['id'])}: {first[:170]}")
        if t.get("check_ar"):
            out.append(f"     ✔ قبل «خلص»: {t['check_ar'][:170]}")
    if r["recipes"]:
        rec = r["recipes"][0][1]
        out.append(f"   وصفة الانصهار الأقرب: {rec['title_ar']} [{rec['id']}] · ثقة {r['confidence']} (التفاصيل: rd.py fuse route \"…\")")
    out.append(f"   قبل ما ترد: {CHECK_CMD} وصلّح كل ✗ · البروتوكول كامل: rd.py fuse protocol")
    return out


def protocol_md(rd):
    df = load(rd)
    th = df.thinking()
    by = {t["id"]: t for t in th.get("tools") or []}
    out = ["## سلّم «صح من أول مرة» (8 درجات)", ""]
    for step in th.get("protocol_ar") or []:
        head, _, ids = step.partition(" — ")
        names = [by[i.strip()]["name_ar"] for i in ids.replace("،", ",").split(",") if i.strip() in by]
        out.append(f"- **{head}**" + (f"\n  - الأدوات: {' · '.join(names)}" if names else ""))
    out += ["", "العمق بيتحسب لكل طلب: `rd.py fuse brief \"<الطلب>\"` (L0 = ① و⑧ بس، L1 = ①②③⑥⑧، L2 وL3 = الكل).",
            f"وقبل أي رد نهائي: {CHECK_CMD}."]
    return "\n".join(out)


def tools_md(rd, request=None):
    df = load(rd)
    if request:
        _, _, tools, _ = depth_and_tools(rd, request, limit=3)
    else:
        tools = df.thinking().get("tools") or []
    out = []
    for t in tools:
        out.append(f"### {t.get('name_ar', t['id'])} (`{t['id']}`)\n_{df._src_label(t)}_")
        out += [f"{n}. {s}" for n, s in enumerate(t.get("steps_ar") or [], 1)]
        if t.get("check_ar"):
            out.append(f"- ✔ {t['check_ar']}")
        out.append("")
    return "\n".join(out) if out else "مفيش أدوات تفكير في الفهرس."


def problems(rd):
    """Offline checks for rd.py selftest. [] = fine."""
    bad = []
    if not available():
        return ["fusion: apps/golden-dragon/app/fusion مش موجود"]
    try:
        df = load(rd)
        st = df.stats()
        th = df.thinking()
        if st["units"] < 1000 or st["recipes"] < 40 or st["lessons"] < 60:
            bad.append(f"fusion: counts {st['units']} units / {st['recipes']} recipes / {st['lessons']} lessons")
        if len(th.get("tools") or []) < 20 or len(th.get("protocol_ar") or []) != 8:
            bad.append(f"fusion: {len(th.get('tools') or [])} thinking tools, {len(th.get('protocol_ar') or [])} protocol steps")
        req = "اعمل ريل 9:16 من الفيديو ده على الأغنية وزوّد كابشن على الكلام"
        b = brief(rd, req)
        if "العمق" not in b or "أدوات تفكير" not in b or "fusion check" in b or "rd.py check" not in b:
            bad.append("fusion brief: missing depth, thinking tools or the rd.py check line")
        info = df._cache.get("rd", {}).get(req.strip())
        if not info or not info.get("playbooks"):
            bad.append("fusion brief: the Red Dragon reading was not used")
        lvl, _, tools, _ = depth_and_tools(rd, "ازيك")
        if lvl != "L0":
            bad.append(f"fusion depth: «ازيك» → {lvl}, expected L0")
        ids = df.by_id()
        for r in _overlay().get("recipes", []):           # the skill's own recipes may only name units that exist
            for s in r.get("steps", []):
                for i in s.get("read", []) + s.get("use", []):
                    if i not in ids:
                        bad.append(f"fusion overlay {r['id']}: `{i}` مش في الفهرس")
        for q, want in (("طور قدرات المستودع واضف له كل المميزات وطور تفكيره وقدراته", "skill-self-develop"),
                        ("ضيف ميزة للتطبيق انه يعرض المحادثات المثبتة", "app-self-develop"),
                        ("طوّر التطبيق بالقدرات دي", "app-self-develop"),       # the Red Dragon reads it as self-improve
                        ("طوّر التنين الأحمر", "skill-self-develop"),
                        ("اعمل مهارة جديدة لبلندر", "new-skill")):
            r = df.route(q)
            got = r["recipes"][0][1]["id"] if r["recipes"] else "none"
            if got != want:
                bad.append(f"fusion route «{q[:40]}» → {got}, expected {want}")
        weak = check_md(rd, "اعمل فيديو ريل للمنتج", "خلص الفيديو.")
        if "✗" not in weak:
            bad.append("fusion check: a «done» with no evidence passed")
        good_draft = ("C:\\Users\\x\\Desktop\\reel.mp4\n"
                      "اتعمل الريل للمنتج: 30.0 ث، 1080x1920، اتقاس بـ ffprobe ✅، والصوت AAC.\n"
                      "اللي اتعمل: قص، كابشن، وفحص.")
        good = check_md(rd, "اعمل فيديو ريل للمنتج", good_draft)
        if "✗" in good:
            bad.append("fusion check: a well-formed answer got ✗: " + " | ".join(x for x in good.splitlines() if "✗" in x)[:200])
        if not failed(weak) or failed(good) or not failed(check_md(rd, "اعمل فيديو ريل للمنتج", "")):
            bad.append("fusion check: the exit status would not follow the ✗ lines")
        with tempfile.TemporaryDirectory(prefix="rd-fuse-") as tmp:     # PowerShell 5.1 `>` writes UTF-16; old editors cp1256
            for name, data in (("u16.txt", "خلص ✅".encode("utf-16")), ("ansi.txt", "خلص".encode("cp1256")),
                               ("bom8.txt", "﻿خلص".encode("utf-8"))):
                p = Path(tmp) / name
                p.write_bytes(data)
                text, _ = read_draft(str(p))
                if not text.startswith("خلص"):
                    bad.append(f"fusion read_draft {name}: {text[:20]!r}")
        t0 = time.perf_counter()
        long_out = check_md(rd, "اعمل فيديو ريل للمنتج", good_draft + "كلام كتير " * 6000)
        if "الرد طويل" not in long_out or time.perf_counter() - t0 > 60:
            bad.append(f"fusion check: a long answer took {time.perf_counter() - t0:.0f} s or was not marked as cut")
    except Exception as e:
        bad.append(f"fusion: {type(e).__name__}: {str(e)[:200]}")
    return bad


def main(argv, rd):
    argv = list(argv or [])
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    if argv[0] == "selftest":
        bad = problems(rd)
        print(json.dumps({"ok": not bad, "problems": bad}, ensure_ascii=False))
        return 1 if bad else 0
    if not available():
        print("✗ عقل الانصهار مش موجود في النسخة دي (apps/golden-dragon/app/fusion).")
        return 1
    act, rest = argv[0], argv[1:]
    try:
        if act == "brief" and rest:
            print(brief(rd, " ".join(rest)))
        elif act == "route" and rest:
            print(route_md(rd, " ".join(rest)))
        elif act == "check":
            req, src = _opt(rest, "--request"), _opt(rest, "--draft")
            if req is None or src is None:
                print('✗ الاستخدام: rd.py check --request "<الطلب>" --draft FILE|-   (ملف اسمه بيبدأ بـ - : --draft=./-x.txt)')
                return 2
            draft, warn = read_draft(src)
            out = check_md(rd, req, draft) + (f"\n- {warn}" if warn else "")
            print(out)
            return 1 if failed(out) else 0
        elif act == "protocol":
            print(protocol_md(rd))
        elif act == "tools":
            print(tools_md(rd, " ".join(rest) or None))
        elif act in ("find", "show", "recipes", "lessons", "doctor", "stats"):
            load(rd)
            return _df.main(argv) if act != "doctor" else (print(_skill_words(_df.md_doctor())) or 0)
        else:
            print(__doc__)
            return 2
    except OSError as e:                  # a missing file, a folder given as the draft, no permission
        print(f"✗ {e.strerror}: {e.filename}" if e.strerror else f"✗ {e.args[0] if e.args else e}")
        return 1
    except (KeyError, ValueError) as e:
        print(f"✗ {e.args[0] if e.args else e}")
        return 1
    return 0
