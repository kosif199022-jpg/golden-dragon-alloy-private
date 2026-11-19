"""Phase 1 gate: Arabic normalisation, SKILL.md parsing, catalog build from fixtures, routing."""
import json, sqlite3, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dragon import arabic, catalog, router  # noqa: E402


def test_normalize_unifies_spellings():
    assert arabic.normalize("أَحْلِفُ بِسَمَاهَا") == arabic.normalize("احلف بسماها")
    assert arabic.normalize("مكتبة") == arabic.normalize("مكتبه")
    assert arabic.normalize("مستشفى") == arabic.normalize("مستشفي")
    assert arabic.normalize("٤٠٬٠٠٠") == "40000"


def test_tokens_drop_article_and_stopwords():
    assert arabic.tokens("عايز المونتاج في الفيديو") == ["مونتاج", "فيديو"]
    assert arabic.tokens("the cinematic montage") == ["cinematic", "montage"]


def test_frontmatter_folded_description():
    name, desc = catalog.parse_frontmatter("---\nname: demo\ndescription: >-\n  first line\n  second line\nlicense: MIT\n---\nbody")
    assert name == "demo" and desc == "first line second line"
    name, desc = catalog.parse_frontmatter('---\nname: x\ndescription: "quoted text"\n---')
    assert desc == "quoted text"


def _fixture(tmp_path):
    (tmp_path / "skills" / "cine").mkdir(parents=True)
    (tmp_path / "skills" / "cine" / "SKILL.md").write_text(
        "---\nname: cinema-montage\ndescription: مونتاج سينمائي لفيديوهات الريلز بكلام عربي متحرك\n---\n", encoding="utf-8")
    (tmp_path / "skills" / "excel").mkdir()
    (tmp_path / "skills" / "excel" / "SKILL.md").write_text(
        "---\nname: excel-pro\ndescription: Spreadsheet formulas and pivot tables\n---\n", encoding="utf-8")
    tools = {"tools": [{"id": "smart-cut", "path": "scripts/smart_cut.py", "title_ar": "قص ذكي بالفريم",
                        "title_en": "Frame-accurate smart cut", "summary_en": "lossless trim", "use_when": ["قص فيديو"],
                        "commands": [{"example": "python smart_cut.py in.mp4 1 5 out.mp4"}], "area": "video"}]}
    micro = {"powers": [{"id": "TYPE-17", "name_ar": "سطر يضيء كلمة كلمة", "name_en": "Word-lit line",
                         "what": "kinetic typography synced to speech", "tags": ["كاريوكي"], "family": "type", "group": "type"}],
             "superpowers": [{"id": "SP-1", "name_ar": "عناوين متحركة", "name_en": "Moving titles", "focus": ["titles"],
                              "family": "type", "domain": "motion", "members": ["TYPE-17"]}]}
    (tmp_path / "tools.json").write_text(json.dumps(tools, ensure_ascii=False), encoding="utf-8")
    (tmp_path / "micro.json").write_text(json.dumps(micro, ensure_ascii=False), encoding="utf-8")
    return {"skill_roots": [{"source": "fx", "path": str(tmp_path / "skills"), "depth": 3}],
            "tools_json": str(tmp_path / "tools.json"), "micro_index": str(tmp_path / "micro.json")}


def test_build_and_route(tmp_path):
    db = tmp_path / "c.sqlite"
    counts = catalog.build(db, _fixture(tmp_path), log=lambda *a: None)
    assert counts == {"skill:fx": 2, "tool:superpowers": 1, "power:superpowers": 1, "superpower:superpowers": 1}
    con = sqlite3.connect(db); con.row_factory = sqlite3.Row
    res = router.find("عايز مونتاج سينمائي للريلز", con=con)
    assert res["skill"][0]["name"] == "cinema-montage"
    assert all(r["name"] != "excel-pro" for r in res["skill"])
    res = router.find("قص الفيديو", con=con)
    assert res["tool"][0]["name"] == "smart-cut" and "smart_cut.py" in res["tool"][0]["command"]
    res = router.find("كاريوكي", con=con)
    assert res["power"][0]["name"] == "TYPE-17"
    assert router.show("smart-cut", con=con)["title_ar"] == "قص ذكي بالفريم"


def test_empty_query_returns_nothing(tmp_path):
    db = tmp_path / "c.sqlite"
    catalog.build(db, _fixture(tmp_path), log=lambda *a: None)
    con = sqlite3.connect(db); con.row_factory = sqlite3.Row
    assert all(v == [] for v in router.find("في من على", con=con).values())
