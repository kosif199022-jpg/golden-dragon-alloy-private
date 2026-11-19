"""v1990.5: mono story kit (ST08): spec checks, two-line subtitles, doodle card frames. Offline and fast."""
import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

SKILL = Path(__file__).resolve().parents[2]
KIT = SKILL / "tools" / "mono_story"
spec_ = importlib.util.spec_from_file_location("mono_build", KIT / "build.py")
mono = importlib.util.module_from_spec(spec_)
spec_.loader.exec_module(mono)

SPEC = {"dur": 9.0, "shots": [{"start": 0, "end": 4.5, "src": "a.mp4"}, {"start": 4.5, "end": 6.0, "src": "b.jpg"}],
        "subs": [[0.2, 4.4, "سطر أول", "سطر تاني", 1.5], [4.6, 7.0, "سطر واحد", ""]],
        "card": {"start": 6.0, "title": "اسم الأغنية", "by": "المطرب"}}


def test_shots_must_tile_until_card():
    assert mono.check(SPEC) == 6.0
    bad = dict(SPEC, shots=[{"start": 0, "end": 4.0, "src": "a.mp4"}, {"start": 4.5, "end": 6.0, "src": "b.jpg"}])
    with pytest.raises(SystemExit):
        mono.check(bad)


def test_ass_second_line_fades_in_and_stops_at_card(tmp_path):
    p = tmp_path / "s.ass"
    mono.ass(SPEC, 6.0, p)
    t = p.read_text(encoding="utf-8")
    assert "0:00:01.50" in t and "سطر تاني" in t and "\\fad(" in t
    assert "0:00:06.00,Sub" in t  # the 4.6-7.0 line is cut at the card
    assert "Mahmoud Elkosif" in t and "Credit" not in t.split("[Events]")[1]  # credit lives on the card


def test_ass_credit_on_picture_without_card(tmp_path):
    p = tmp_path / "s.ass"
    s = dict(SPEC, card=None)
    mono.ass(s, 9.0, p)
    assert "مونتاج وإخراج Mahmoud Elkosif" in p.read_text(encoding="utf-8")


def test_card_frames_draw_title(tmp_path):
    pytest.importorskip("PIL")
    if subprocess.run(["ffmpeg", "-version"], capture_output=True).returncode:
        pytest.skip("ffmpeg missing")
    out = mono.card_frames({"title": "كائن تلاتيني", "by": "نور"}, 6, 0.1, tmp_path)
    assert out.is_file() and out.stat().st_size > 2000


def test_registered_in_dragon_and_fonts():
    assert '"mono": "tools/mono_story/build.py"' in (SKILL / "scripts" / "dragon.py").read_text(encoding="utf-8")
    assert {p.name for p in (KIT / "fonts").glob("*.ttf")} >= {"Lalezar-Regular.ttf", "Almarai-Bold.ttf", "Changa-700.ttf"}
    r = subprocess.run([sys.executable, str(KIT / "build.py"), "--help"], capture_output=True, text=True)
    assert r.returncode == 0 and "spec.json" in r.stdout


def test_comic_look_big_yellow_subtitles(tmp_path):
    p = tmp_path / "c.ass"
    mono.ass(dict(SPEC, look="comic", mono=False), 6.0, p)
    t = p.read_text(encoding="utf-8")
    assert "Style: Sub,Changa,84,&H0040B7F6" in t and "\\pos(540,1360)" in t


def test_styles_saved_st08_st09_st10():
    import json
    d = json.loads((SKILL / "tools" / "looks" / "looks.json").read_text(encoding="utf-8"))
    ids = {x["id"]: x for x in d["looks"]}
    for i in ("ST07", "ST08", "ST09", "ST10", "ST11", "ST12", "ST13", "ST14"):
        assert i in ids and (SKILL / "tools" / "looks" / ids[i]["image"]).is_file(), i
    for kit in ("surreal_minimal", "shadow_play", "ink_essay", "pulse_line", "glow_line", "chalk_board"):
        html = (SKILL / "tools" / kit / "template.html").read_text(encoding="utf-8")
        assert "window.__kosif" in html and "Math.random" not in html and "Date.now" not in html, kit
        assert (SKILL / "tools" / kit / "README.md").is_file()


def test_v19907_version_and_docs():
    sys.path.insert(0, str(SKILL / "app"))
    from importlib import import_module
    assert import_module("dragon").__version__.startswith("1990.")  # v1990.10: series check, not a pinned release
    skill = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    assert "v1990.7.0" in skill and "tool mono" in skill and "Changa" in skill
    assert "PROJECT_HARVEST_V19906" in skill  # the owner's v1990.6 content is kept
    import json
    ids = {x["id"] for x in json.loads((SKILL / "tools" / "looks" / "looks.json").read_text(encoding="utf-8"))["looks"]}
    assert {"PM01", "PM15", "ST06", "ST11"} <= ids
