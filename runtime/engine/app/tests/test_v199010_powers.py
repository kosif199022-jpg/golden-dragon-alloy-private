"""v1990.10: `tool powers` (every power and connection), brain ⑪ connections, package header label. Offline, ~1 s."""
import importlib.util, json, subprocess, sys
from pathlib import Path

import pytest

SKILL = Path(__file__).resolve().parents[2]
POW = SKILL / "tools" / "powers"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m


P = load("bd_powers_t", POW / "powers.py")
REG = json.loads((POW / "powers.json").read_text(encoding="utf-8"))


def test_registry_schema():
    ids = [p["id"] for p in REG["powers"]]
    assert len(ids) == len(set(ids)) and len(ids) >= 45
    for p in REG["powers"]:
        assert p["layer"] in REG["layers"] and p["layer"] in P.LAYERS_ORDER, p["id"]
        assert p["cost"] in P.BADGE, p["id"]
        assert p["where"] in ("pc", "cloud", "both"), p["id"]
        assert p["triggers"].strip() and p["how"].strip() and p["ar"].strip(), p["id"]
        assert p["probe"]["type"] in ("none", "program", "path", "module", "skill", "mcp", "session"), p["id"]
        if p["where"] == "pc":
            assert p.get("cloud_alt"), f"{p['id']}: laptop-only power needs a cloud alternative"
    # every paid generation path is marked paid, never free
    assert {p["id"] for p in REG["powers"] if p["cost"] == "paid"} >= {"hf-generate", "suno"}


@pytest.mark.parametrize("q,top", [
    ("حوّل الفيديو ده لكرتون زي بيكسار", "eng-toon"),
    ("ارندر الفيلم على السحابة عشان الجهاز يرتاح", "hf-sandbox"),
    ("حلل البرنامج ده exe وشوف بيكلم انهي سيرفر", "rea-mcp"),
    ("اعملي اغنية على سونو", "suno"),
    ("افتح كروم وخد سكرين شوت للصفحة", "chrome"),
    ("نزل الفيديو ده من يوتيوب بسرعة", "prog-download"),
    ("وزع الشغل على وكلاء بالتوازي", "cc-agents"),
    ("شيل الخلفية من الصورة", "prog-image"),
    ("عايز اعرف الماكينة دي بتشتغل ازاي", "teardown"),
    ("فرغ الكلام من الفيديو ده", "prog-audio"),
    ("طور تطبيق التنين وضيف زرار", "desktop-app"),
])
def test_route_real_requests(q, top):
    rows = P.route(q, 3, where="pc")
    assert rows and rows[0]["id"] == top, [r["id"] for r in rows]


def test_free_road_wins_a_tie_and_paid_is_flagged():
    rows = P.route("شيل الخلفية من الصورة", 4, where="pc")
    ids = [r["id"] for r in rows]
    assert ids.index("prog-image") < ids.index("hf-generate")
    assert next(r for r in rows if r["id"] == "hf-generate")["cost"] == "paid"


def test_cloud_gets_the_alternative_not_a_laptop_path():
    r = P.route("نزل الفيديو ده من يوتيوب", 1, where="cloud")[0]
    assert r["id"] == "prog-download" and r["here"] == "cloud_alt" and "C:\\" not in r["how_here"]


def test_arabic_tokens_strip_prefixes():
    assert "كرتون" in P.tokens("لكرتون") and "سحابه" in P.tokens("بالسحابة")


def test_brain_has_connections():
    B = load("bd_brain_t", SKILL / "tools" / "brain" / "brain.py")
    b = B.brief("حوّل الفيديو ده لكرتون", use_live=False)
    assert b["connections"] and b["connections"][0]["id"] == "eng-toon"


def test_registered_in_launcher_and_catalog():
    src = (SKILL / "scripts" / "dragon.py").read_text(encoding="utf-8")
    assert '"powers": "tools/powers/powers.py"' in src and '"package": "tools/package/package.py"' in src
    ids = {t["id"] for t in json.loads((SKILL / "app/data/own_tools.json").read_text(encoding="utf-8"))["tools"]}
    assert {"powers", "package"} <= ids


def run(*args):
    return subprocess.run([sys.executable, "-X", "utf8", str(POW / "powers.py"), *args], capture_output=True, text=True,
                          encoding="utf-8", timeout=60)


def test_doctor_offline_json_and_session_tools():
    r = run("doctor", "--json")
    assert r.returncode == 0, r.stderr
    d = json.loads(r.stdout)
    st = {x["id"]: x["state"] for x in d["powers"]}
    assert d["mcp_checked"] is False and st["hf-sandbox"] == "unchecked"
    assert st["chrome"] == "session"            # injected by the session, not by `claude mcp list`
    assert st["teardown"] == "present"          # bundled skill


def test_map_md_lists_every_power_and_show_unknown_fails():
    r = run("map", "--md")
    assert r.returncode == 0 and all(f"(`{p['id']}`)" in r.stdout for p in REG["powers"])
    assert run("show", "no-such-power").returncode == 2
    assert run("first", "شيل الخلفية").stdout.startswith("**فهمت إنك عايز:**")


def test_generated_reference_is_current():
    ref = (SKILL / "references" / "ALL_POWERS_V199010.md").read_text(encoding="utf-8")
    assert all(f"(`{p['id']}`)" in ref for p in REG["powers"])


def test_package_header_accepts_a_label(tmp_path):
    K = load("bd_pkg_t", SKILL / "tools" / "package" / "package.py")
    (tmp_path / "__init__.py").write_text('__version__ = "1990.9.0"\n', encoding="utf-8")
    (tmp_path / "library.json").write_text('{"version": "1990.9.0"}', encoding="utf-8")
    (tmp_path / "SKILL.md").write_text("---\nname: x\n---\n\n# Black Dragon — التنين الأسود (v1990.9.0 candidate، 2026-11-12)\n",
                                       encoding="utf-8")
    K.INIT, K.LIBRARY_JSON, K.SKILL_MD = tmp_path / "__init__.py", tmp_path / "library.json", tmp_path / "SKILL.md"
    K.set_version("1990.10.0")
    assert "(v1990.10.0 candidate، " in K.SKILL_MD.read_text(encoding="utf-8")


def test_skill_front_door():
    md = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    assert "tool powers" in md[:4000] and "فهمت إنك عايز" in md[:2500]
    assert "VERSION_NOTES.md" in md and "## ⛔ v1990.9.0" in (SKILL / "references" / "VERSION_NOTES.md").read_text(encoding="utf-8")
