"""v1990.5 (ported from v10.3): the smart-effects gate (`dragon fx`). Pure logic, no media and no network."""
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT.parent
sys.path.insert(0, str(ROOT))
from dragon import effects

GOOD = {"name": "petals", "kind": "particles", "shots": ["s8"], "serves": "meaning",
        "why": "الكلمة «ورد» بتتقال في اللقطة دي والورد نازل ورا الشخصية مش عليها",
        "if_removed": "الكلمة تفضل من غير صورتها", "covers_subject": False, "coverage": 0.06}
PAGE = "function dust(t){}\nfunction petals(t){}\nfunction render(t){drawShot();%s}"


def m(material, *fx):
    return {"material": material, "effects": [dict(e) for e in fx]}


def test_clean_film_passes():
    r = effects.check(m("footage"), PAGE % "")
    assert r["ok"] and r["effects"] == 0 and r["page_draws"] == {}


def test_reasoned_effect_on_illustration_passes():
    r = effects.check(m("illustration", GOOD), PAGE % "petals(t);")
    assert r["ok"], r["fails"]
    assert r["page_draws"] == {"petals": 1}


def test_gold_dust_on_footage_is_refused():
    dust = dict(GOOD, name="dust", kind="particles")
    r = effects.check(m("footage", dust), PAGE % "dust(t);")
    assert not r["ok"] and any("ممنوع" in f for f in r["fails"])


def test_owner_asked_needs_his_words():
    dust = dict(GOOD, name="dust", owner_asked=True)
    assert not effects.check(m("footage", dust))["ok"]
    dust["owner_words"] = "«حط غبار دهبي» 2026-11-10"
    assert effects.check(m("footage", dust))["ok"]


def test_generic_reason_and_decoration_are_refused():
    for why in ("شكله حلو", "cinematic", "يدي جو", ""):
        assert not effects.check(m("illustration", dict(GOOD, why=why)))["ok"], why
    assert not effects.check(m("illustration", dict(GOOD, serves="decoration")))["ok"]
    assert not effects.check(m("illustration", dict(GOOD, if_removed="")))["ok"]


def test_covering_the_subject_is_refused():
    assert not effects.check(m("illustration", dict(GOOD, covers_subject=True)))["ok"]


def test_undeclared_page_effect_is_refused():
    r = effects.check(m("illustration", GOOD), PAGE % "petals(t);dust(t);")
    assert not r["ok"] and any("dust" in f for f in r["fails"])


def test_budget_per_shot_and_per_film():
    a, b = dict(GOOD, name="petals"), dict(GOOD, name="hearts")
    r = effects.check(m("illustration", a, b))
    assert not r["ok"] and any("s8" in f for f in r["fails"])
    three = [dict(GOOD, name=n, kind=k, shots=[s]) for n, k, s in
             (("petals", "particles", "s1"), ("grain", "grain", "s2"), ("glow", "glow", "s3"))]
    assert not effects.check(m("illustration", *three))["ok"]
    assert not effects.check(m("illustration", dict(GOOD, coverage=0.5)))["ok"]


def test_cli_exit_codes(tmp_path):
    man, page = tmp_path / "effects.json", tmp_path / "index.html"
    page.write_text(PAGE % "dust(t);", encoding="utf-8")
    run = lambda *a: subprocess.run([sys.executable, str(SKILL / "scripts" / "dragon.py"), "fx", *a],
                                    capture_output=True, text=True, encoding="utf-8")
    assert run("new", str(man)).returncode == 0
    assert json.loads(man.read_text(encoding="utf-8"))["effects"] == []
    bad = run("check", str(man), "--html", str(page))
    assert bad.returncode == 1 and "dust" in bad.stdout
    page.write_text(PAGE % "", encoding="utf-8")
    ok = run("check", str(man), "--html", str(page))
    assert ok.returncode == 0 and "FX OK" in ok.stdout
    assert "الأسئلة الخمسة" in run("rules").stdout


def test_rule_is_written_into_the_skill():
    skill = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    assert "fx check" in skill and "المؤثرات الذكية" in skill
    assert (SKILL / "references" / "EFFECTS_SMART.md").is_file()
    assert "2026-11-09" in (SKILL / "references" / "LESSONS.md").read_text(encoding="utf-8")
