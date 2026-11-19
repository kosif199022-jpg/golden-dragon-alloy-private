"""v1990.5: looks library (the couple, outfits, styles, models with pictures) and the lyric film kit. Offline."""
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT.parent
LOOKS = SKILL / "tools" / "looks"
KIT = SKILL / "tools" / "lyric_couple"
REFS = {"d684961b-6a65-4c48-b2a9-45cd479bd43e", "81dfa2e9-ecfd-44f1-bb50-4b722437a67a"}


def run(*a):
    return subprocess.run([sys.executable, str(SKILL / "scripts" / "dragon.py"), *a],
                          capture_output=True, text=True, encoding="utf-8")


def data():
    return json.loads((LOOKS / "looks.json").read_text(encoding="utf-8"))


def test_every_look_has_unique_id_kind_and_existing_picture():
    d = data()
    ids = [x["id"] for x in d["looks"]]
    assert len(ids) == len(set(ids)) and len(ids) >= 40
    assert set(d["refs"]) == REFS
    kinds = {x["kind"] for x in d["looks"]}
    assert {"character", "wardrobe", "singer", "expression", "scene", "style", "layout", "model"} <= kinds
    for x in d["looks"]:
        if x["kind"] != "model":
            assert x.get("image"), x["id"]
            assert (LOOKS / x["image"]).is_file(), x["image"]
            assert (LOOKS / x["image"]).stat().st_size < 120_000, x["image"]


def test_modesty_rule_in_every_dress_prompt():
    for x in data()["looks"]:
        p = x.get("prompt", "").lower()
        if x["kind"] in ("wardrobe", "singer") and "dress" in p:
            assert "neckline" in p or "collar" in p, x["id"]


def test_cli_list_show_prompt():
    r = run("tool", "looks", "list", "--kind", "wardrobe")
    assert r.returncode == 0 and "W07" in r.stdout
    r = run("tool", "looks", "show", "W05")
    assert r.returncode == 0 and "image:" in r.stdout and ".mp4" in r.stdout
    r = run("tool", "looks", "prompt", "C01", "W07", "E03", "--scene", "she holds a hot drink by the sea")
    assert r.returncode == 0
    j = json.loads(r.stdout)
    assert j["params"]["model"] == "gpt_image_2_6" and {m["value"] for m in j["params"]["medias"]} == REFS
    assert "camel coat" in j["prompt"] and "hot drink" in j["prompt"] and '"' not in j["prompt"]
    assert run("tool", "looks", "show", "NOPE").returncode == 1


def test_sheet(tmp_path):
    out = tmp_path / "s.jpg"
    r = run("tool", "looks", "sheet", str(out), "--kind", "expression")
    if "Pillow is needed" in r.stdout:
        return
    assert r.returncode == 0 and out.stat().st_size > 10_000


def test_lyric_kit_builds_a_clean_page(tmp_path):
    spec = {"dur": 12.0, "title": "تجربة", "credit": 9.0,
            "shots": [[0, 4, "a1"], [4, 8, "a2"], [8, None, "a3"]], "seq": {"a2": 120},
            "ly": [[0.3, 3.8, "سطر أبيض", "سطر أحمر"], [4.2, 7.8, "سطر تاني", ""]]}
    (tmp_path / "spec.json").write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
    r = run("tool", "lyric", str(tmp_path), str(tmp_path / "spec.json"))
    assert r.returncode == 0, r.stderr
    html = (tmp_path / "film" / "index.html").read_text(encoding="utf-8")
    assert "DUR=12.0" in html and "'seq','s/a2',{n:120" in html and "img/a1.jpg" in html
    assert "const PRG=!G?null:" in html and "سطر أبيض" in html and "credit(t,9.0);" in html
    assert {p.name for p in (tmp_path / "film" / "fonts").glob("*.ttf")} >= {"ArefRuqaa-Bold.ttf", "Tajawal-Bold.ttf"}
    sys.path.insert(0, str(ROOT))
    from dragon import effects
    rep = effects.check({"material": "illustration", "effects": []}, html)
    assert rep["ok"] and rep["page_draws"] == {}, rep


def test_docs_and_version():
    from importlib import import_module
    sys.path.insert(0, str(ROOT))
    assert import_module("dragon").__version__.startswith("1990.")  # v1990.10: series check, not a pinned release
    skill = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    assert "tool looks" in skill and "SESSION_HARVEST_V19905" in skill
    for f in ("SESSION_HARVEST_V19905.md", "LOOKS_LIBRARY_V19905.md", "EFFECTS_SMART.md"):
        assert (SKILL / "references" / f).is_file(), f
    assert "render.sh" in (KIT / "render.sh").read_text(encoding="utf-8") and "--from" in (KIT / "render.sh").read_text(encoding="utf-8")


def test_kinetic_nasheed_style_saved():
    st = [x for x in data()["looks"] if x["id"] == "ST06"]
    assert st and st[0]["kind"] == "style"
    kit = SKILL / "tools" / "kinetic_nasheed"
    html = (kit / "template.html").read_text(encoding="utf-8")
    assert "window.__kosif" in html and "__kosifReady" in html and "Math.random" not in html
    assert {p.name for p in (kit / "fonts").glob("*.ttf")} >= {"NotoNaskhArabic-700.ttf", "Tajawal-Bold.ttf"}
    assert "#c4506a" in (kit / "README.md").read_text(encoding="utf-8")
