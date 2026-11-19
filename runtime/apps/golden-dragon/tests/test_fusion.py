"""dragon_fusion: the fused index, the recipes, the router, doctor, the CLI, and the routing floor on the owner's real,
blind-labelled requests (held-out half)."""
import importlib.util
import json
import os
import re
import sys
from pathlib import Path

import pytest

from conftest import APP, FORGE


def test_index_counts_and_kinds(fz):
    st = fz.stats()
    k = st["kinds"]
    assert k["skill"] >= 500 and k["lib"] >= 150 and k["engine"] >= 10 and k["re"] >= 30 and k["tool"] >= 24
    assert st["recipes"] >= 40 and st["lessons"] >= 30
    ids = [u["id"] for u in fz.units()]
    assert len(ids) == len(set(ids))


def test_every_recipe_names_existing_units_and_no_older_version(fz):
    m = fz.by_id()
    for r in fz.recipes():
        assert len(r["steps"]) >= 2 and len(r["when"]) >= 2, r["id"]
        for s in r["steps"]:
            assert s["gate_ar"], (r["id"], s["do_ar"])
            for i in s["read"] + s["use"]:
                assert i in m, (r["id"], i)
                assert m[i]["status"] != "older", (r["id"], i)
            assert all(i.startswith("skill:") for i in s["read"]), r["id"]


def test_older_versions_point_to_an_existing_newer_one(fz):
    """Whatever is installed: an «older» unit must name a newer one that exists and is not older itself. (On 2026-11-15
    the five older copies, black-dragon-2..5 and red-dragon-2, were moved to skills_backup, so today there are none.)"""
    import re
    for u in fz.units():
        if u.get("status") == "older":
            newer = re.search(r"`skill:([^`]+)`", u["warn_ar"][0]).group(1)
            assert fz.resolve("skill:" + newer)["status"] != "older", (u["id"], newer)


def test_scanner_marks_older_copies_by_numeric_version(tmp_path):
    """scan_skills groups name / name-2 / name-3 with the same title and keeps the NUMERICALLY newest (1.10 > 1.2)."""
    spec = importlib.util.spec_from_file_location("scan_skills_t", FORGE / "scan_skills.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    for name, ver in (("dragon", "1.2.0"), ("dragon-2", "1.0.0"), ("dragon-3", "1.10.0"), ("other", "9.9.9")):
        d = tmp_path / "skills" / name
        d.mkdir(parents=True)
        title = "Other" if name == "other" else "Dragon"
        (d / "SKILL.md").write_text(f"---\nname: {name}\ndescription: x {name}\n---\n# {title} v{ver}\n", encoding="utf-8")
    out = tmp_path / "skills.json"
    m.main(["--skills", str(tmp_path / "skills"), "--out", str(out)])
    s = {x["id"]: x for x in json.loads(out.read_text(encoding="utf-8"))["skills"]}
    assert s["dragon"]["superseded_by"] == "dragon-3" and s["dragon-2"]["superseded_by"] == "dragon-3"
    assert "superseded_by" not in s["dragon-3"] and "superseded_by" not in s["other"]


@pytest.mark.parametrize("q, want", [
    ("حط ترجمة عربي على الفيديو", "arabic-captions"),
    ("نزّل الفيديو ده من تيك توك", "download-media"),
    ("حلّل ملف exe ده وقولي بيكلّم مين", "reverse-engineer"),
    ("طابق كشف الحساب مع الحوالات وطلّع الفروقات", "reconcile-statements"),
    ("make a blender product render", "blender-3d-shot"),
    ("ضيف ميزة للتطبيق", "app-self-develop"),
])
def test_route_sanity(fz, q, want):
    """Sanity only (these sentences are close to the recipes' own examples); the real measure is the held-out floor."""
    r = fz.route(q)
    assert r["recipes"] and r["recipes"][0][1]["id"] == want


def test_route_flags_paid_steps(fz):
    r = fz.route("اعمل أغنية بسونو")
    assert any(rec["id"] == "song-music" for _, rec in r["recipes"])
    assert any("مدفوع" in a for a in r["approvals"])


def test_route_extras_need_two_words(fz):
    """«كشف» alone (scenedetect = «كشف القطعات») or «ملف» alone (the RE tools) must not land in a reconciliation answer."""
    r = fz.route("عايز أطابق كشف حساب البنك مع ملف الحوالات وأطلع الفروقات في اكسل")
    assert r["recipes"][0][1]["id"] == "reconcile-statements"
    assert not any(u["id"] in ("program:scenedetect", "re:die", "re:rz-bin") for u in r["units"])
    extras = [u["id"] for u in fz.route("اعمل فيديو موشن جرافيك بالكود فيه particles و three.js")["units"]]
    assert "lib:three-js" in extras or "skill:motion-particles" in extras


def test_route_empty_and_markdown(fz):
    assert fz.route("")["recipes"] == []
    md = fz.md_route("اعمل ريل من الفيديوهات دي على الأغنية")
    assert md.startswith("## 🐉 مسار الانصهار") and "| # | الخطوة |" in md and "الخطوة الجاية" in md


def test_tokens_stopwords_negation_filenames(fz):
    assert "موجود" not in fz.query_tokens("الملف موجود")
    assert "اتحدث" in fz.query_tokens("البرنامج ما اتحدثش")
    toks = fz.query_tokens("Account_Statement_0191.xlsx")
    assert "account" in toks and "statement" in toks


def test_find_show_and_kinds(fz):
    hits = fz.find("blender", kind="skill", limit=5)
    assert hits and all(u["kind"] == "skill" for u in hits) and any("blender" in u["id"] for u in hits)
    assert fz.resolve("video-use")["id"] == "skill:video-use"
    assert "## " in fz.md_show("engine:toon")
    with pytest.raises(KeyError):
        fz.resolve("مفيش-حاجة-كده")


def test_doctor_reports_skills_and_programs(fz, tmp_path, monkeypatch):
    sk = tmp_path / "skills"
    (sk / "video-use").mkdir(parents=True)
    (sk / "video-use" / "SKILL.md").write_text("---\nname: video-use\n---\n", encoding="utf-8")
    (sk / "brand-new").mkdir()
    (sk / "brand-new" / "SKILL.md").write_text("---\nname: brand-new\n---\n", encoding="utf-8")
    monkeypatch.setattr(fz, "SKILLS_DIR", sk)
    monkeypatch.setattr(fz, "_which", lambda cmd: "x" if cmd != "rg" else None)
    d = fz.doctor()
    assert d["skills"]["now"] == 2 and d["skills"]["new"] == ["brand-new"] and len(d["skills"]["gone"]) > 400
    assert ("program:rg", False) in d["programs"] and ("program:ffmpeg", True) in d["programs"]
    assert "🩺" in fz.md_doctor()


def test_lessons_search(fz):
    out = fz.md_lessons("فيديو صوت AAC")
    assert "AAC" in out


def test_cli(fz, capsys):
    assert fz.main(["recipes"]) == 0 and "reel-footage-song" in capsys.readouterr().out
    assert fz.main(["route", "حوّل", "صورتي", "لأنمي"]) == 0 and "cartoon-look" in capsys.readouterr().out
    assert fz.main(["show", "nothing-like-this"]) == 1
    assert fz.main([]) == 2


def _eval_and_bridge():
    spec = importlib.util.spec_from_file_location("eval_fresh_t", FORGE / "eval_fresh.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    spec = importlib.util.spec_from_file_location("rd_bridge_t", APP / "fusion" / "rd_bridge.py")
    b = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(b)
    return m, b


def test_routing_floor_on_held_out_real_requests(fz):
    """The owner's real requests, labelled blind by two annotators (Red Dragon route_eval), routed by the app's fusion
    router WITH the Red Dragon's understanding, every graded request hidden from its example memory (no leakage).
    Measured once after tuning on the dev half (2026-11-15): fresh test top1 0.528 top3 0.722 (n=108); old set (never
    tuned on) top1 0.658 top3 0.937 (n=79). Floors leave ~4 requests of slack. Raise them when a version measures higher;
    never lower them to make a version pass."""
    data = os.path.expanduser("~/.claude/skills/red-dragon/mind/route_eval/labels_fresh_consensus.json")
    if not os.path.isfile(data):
        pytest.skip("the Red Dragon evaluation set is not on this PC")
    m, b = _eval_and_bridge()
    m.hide_everything(b)
    fresh, old = m.rows("test"), m.rows("all", "old")
    infos = {r["q"]: b.route_info(r["q"]) for r in fresh + old}
    rf, _ = m.evaluate(fz, fresh, infos)
    ro, _ = m.evaluate(fz, old, infos)
    assert rf["covered"] >= 100 and rf["top1"] >= 0.49 and rf["top3"] >= 0.68, rf
    assert ro["top1"] >= 0.62 and ro["top3"] >= 0.90, ro


def test_red_dragon_signal_changes_the_route(fz):
    """A request BM25 alone sends to «trading» (a company named «… TRADING …») is a bank-statement reconciliation; the Red
    Dragon's reading (reconcile) must win once it is blended in."""
    q = "BOIGEVIS TRADING GUANGZHOU CO LTD ما تواريخ التحويل"
    rd = {"ok": True, "text": q, "playbooks": [[8.0, "reconcile"], [1.5, "draw-math"]]}
    assert fz.route(q, rd=rd)["recipes"][0][1]["id"] == "reconcile-statements"


def test_rd_bridge_decodes_english_keyboard():
    bridge = APP / "fusion" / "rd_bridge.py"
    if not (Path.home() / ".claude" / "skills" / "red-dragon" / "scripts" / "rd.py").is_file():
        pytest.skip("the Red Dragon is not installed here")
    import subprocess
    r = subprocess.run([sys.executable, "-X", "utf8", str(bridge), "hgfvkhl[ ugn hgjdk"], capture_output=True, text=True,
                       encoding="utf-8", timeout=120)
    d = json.loads(r.stdout.strip().splitlines()[-1])
    assert d["ok"] and "البرنامج" in d["text"] and d["playbooks"]


def test_brief_is_a_thinking_sheet(fz):
    md = fz.md_brief("اعمل ريل من الفيديوهات دي على الأغنية")
    for part in ("Task", "Deliverable", "Done-when", "عصف ذهني", "تشريح قبل الفشل", "fusion check", "reel-footage-song"):
        assert part in md, part
    assert "أسئلة لازم تتحسم" in md                      # the Red Dragon playbook's questions to settle


def test_thinking_toolkit_is_bundled_and_complete(fz):
    """The thinkers' toolkit (distilled from the thinking skills and books on this PC) ships inside the app."""
    tk = fz.thinking()
    tools = tk["tools"]
    assert len(tools) >= 20 and len(tk["protocol_ar"]) == 8
    for t in tools:
        assert t["steps_ar"] and t["use_when"] and t.get("check_ar") and t.get("trigger_words"), t["id"]
        label = fz._src_label(t)
        assert label and "[" not in label and "~/" not in label, (t["id"], label)
    used = {u for t in tools for u in t["use_when"]}
    assert set(fz.TASK_TYPE.values()) | {"create", "understand"} <= used     # every task type the router gives has tools


def test_brief_brings_depth_and_the_scholars_tools(fz):
    md = fz.md_brief("اعمل ريل من الفيديوهات دي على الأغنية")
    assert re.search(r"- \*\*العمق:\*\* L[0-3]: ", md)
    block = md.split("أدوات تفكير للطلب ده", 1)[1].split("\n- **", 1)[0]
    assert block.count("\n  - **") >= 2 and block.count("✔ في الآخر:") >= 2
    assert "['" not in block and "~/" not in block                         # the thinker/book, not the raw source list


def test_depth_follows_the_router_signals(fz):
    rec = fz.recipes()[0]
    assert fz.depth({"recipes": []}, "الساعة كام")[0] == "L0"
    assert fz.depth({"recipes": []}, "ابني نظام ري ذكي للمزرعة بحساسات رطوبة وتطبيق موبايل")[0] == "L3"
    strong = {"recipes": [(1.5, rec)], "confidence": "قوية", "ambiguous": False, "approvals": []}
    assert fz.depth(strong, "x")[0] == "L1"
    assert fz.depth(dict(strong, approvals=["نشر"]), "x")[0] == "L2"
    assert fz.depth(dict(strong, ambiguous=True), "x")[0] == "L2"
    assert fz.depth(dict(strong, confidence="ضعيفة"), "x")[0] == "L2"


def test_check_asks_the_critics_questions(fz):
    req = "حلّل البرنامج ده وقولي بيكلّم مين"
    md = fz.md_check(req, "C:\\x\\r.md\nتمام")
    assert "أسئلة الناقد" in md
    by = {t["id"]: t["check_ar"] for t in fz.thinking()["tools"]}
    for i in fz.FINAL_CRITIC:                                                # the three every answer must pass
        assert by[i] in md, i
    qs = fz.critic_questions(req, fz.route(req, rd=None)["recipes"][0][1])
    assert 4 <= len(qs) <= 5 and len({q for _, q in qs}) == len(qs)


def test_check_catches_the_owners_known_failures(fz):
    req = "حلّل البرنامج ده وقولي بيكلّم مين"
    bad = "\n".join(["اتعمل التحليل وخلص.", r"التقرير في C:\Users\x\report.md"])
    res, missed, _ = fz.check(req, bad)
    fails = [m for ok, m in res if not ok]
    assert any("أول سطر" in m for m in fails) and any("دليل" in m for m in fails) and any("✅" in m for m in fails)
    good = "\n".join([r"C:\Users\x\report.md", "البرنامج بيكلّم api.example.com (اتأكد بـ floss و rz-bin، 2 أداة).",
                      "✅ الدومين ظاهر في النصوص", "🟡 استنتاج 70%", "❓ وقت التشغيل", "اللي اتعمل: تحليل ثابت"])
    assert all(ok for ok, _ in fz.check(req, good)[0])
    assert "✗" in fz.md_check(req, bad) and fz.md_check(req, "").startswith("✗")


def test_dragons_are_fused_into_the_index(fz):
    k = fz.stats()["kinds"]
    assert k.get("playbook", 0) >= 30 and k.get("cmd", 0) >= 20
    assert fz.resolve("cmd:rd-consent")["kind"] == "cmd" and fz.resolve("playbook:reel-montage")["extra"]["steps"] > 0
    steps = {r["id"]: [i for s in r["steps"] for i in s["use"]] for r in fz.recipes()}
    assert "cmd:rd-think" in steps["hard-decision"] and "cmd:rd-consent" in steps["ship-package"]


def test_coverage_understands_arabic_word_forms(fz):
    """«امسح»/«المسح», «وحدّث»/«تحديث», «وثبّت»/«ماتثبّتش» are one request item each; an empty «تمام» misses them all."""
    req = "نفذ: امسح الأرشيف الأصلي، وثبّت التنين الأحمر 2.16، وحدّث الطائر الذهبي، وثبّت إضافة كروم"
    good = "المسح النهائي اترفض. التنين الأحمر 2.16 ماتثبّتش. تحديث الطائر الذهبي متجهّز. إضافة كروم جاهزة على سطح المكتب."
    assert fz.check(req, good)[1] == ["ارشيف"]
    assert len(fz.check(req, "تمام")[1]) >= 7


def test_book_tools_and_paths_are_bundled(fz):
    """The 22 tools distilled from king's books (Kahneman, Greetham, Jaynes, the Cursed Child play, the IFRS kit) ship
    in thinking.json next to the original toolkit, and every «سبيل» points at real tools."""
    import json
    books = json.loads((FORGE / "data" / "thinking_books.json").read_text(encoding="utf-8"))
    tk = fz.thinking()
    ids = {t["id"] for t in tk["tools"]}
    assert {t["id"] for t in books["tools"]} <= ids and len(books["tools"]) >= 20 and len(tk["protocol_ar"]) == 8
    for t in books["tools"]:
        assert t["steps_ar"] and t["use_when"] and t["check_ar"] and t["trigger_words"], t["id"]
        assert " — " in fz._src_label(t), t["id"]                        # labelled with the author and the book
    names = {p["name_ar"] for p in tk["paths"]}
    assert {"سبيل الخيال", "سبيل التفكير العميق", "سبيل التفكير الإبداعي", "سبيل المنطق والاحتمال", "سبيل خطوة بخطوة"} <= names
    assert all(x in ids for p in tk["paths"] for x in p["tools"])


def test_build_merges_the_books_once():
    src = (FORGE / "build_fusion.py").read_text(encoding="utf-8")
    ns = {"json": __import__("json"), "FORGE": FORGE}
    exec(src[src.index("BOOKS = FORGE"):src.index("PROGRAMS = [")], ns)       # just merge_books, no PC scan
    base = {"tools": [{"id": "premortem", "steps_ar": ["x"], "use_when": ["plan"]},
                      {"id": "first-principles", "steps_ar": ["x"], "use_when": ["plan"]}] + [
                     {"id": i, "steps_ar": ["x"], "use_when": ["plan"]} for i in
                     ("alternatives-before-commit", "competing-hypotheses", "falsify-it", "calibrate-and-update",
                      "polya-four-phases", "begin-with-the-end", "outside-view", "inversion")],
            "protocol_ar": [f"step {i}" for i in range(8)]}
    once = ns["merge_books"](base)
    assert ns["merge_books"](once) == once                                     # idempotent
    assert len(once["tools"]) == len(base["tools"]) + 22 and "من الكتب" in once["protocol_ar"][0]


def test_paths_steer_the_brief_and_think(fz):
    assert fz.thinking_paths("تخيل لو المحل اتفتح في مدينة تانية")[0]["id"] == "imagination"
    assert fz.thinking_paths("احسب احتمال ان العميل يرجع")[0]["id"] == "logic"
    assert fz.thinking_paths("اشرحلي خطوة بخطوة")[0]["id"] == "steps"
    ids = [t["id"] for t in fz.thinking_for("تخيل لو المحل اتفتح في مدينة تانية", None)]
    assert "what-if-timeline" in ids
    md = fz.md_brief("فكر بعمق: ليه المبيعات وقعت الشهر ده؟")
    assert "🧭 **سبيل التفكير العميق" in md
    assert fz.md_think("").count("- **سبيل") >= 7                               # the map
    one = fz.md_think("الخيال")
    assert one.startswith("## 🧭 سبيل الخيال") and "1. " in one and "✔" in one
