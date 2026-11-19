"""v1990.6: project-wide harvest, method looks with pictures, find/remind. Offline."""
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT.parent
LOOKS = SKILL / "tools" / "looks"


def run(*a):
    return subprocess.run([sys.executable, str(SKILL / "scripts" / "dragon.py"), *a],
                          capture_output=True, text=True, encoding="utf-8")


def data():
    return json.loads((LOOKS / "looks.json").read_text(encoding="utf-8"))


def test_method_cards_have_pictures_and_how():
    ms = [x for x in data()["looks"] if x["kind"] == "method"]
    assert [x["id"] for x in ms] == [f"PM{i:02d}" for i in range(1, 16)]
    for x in ms:
        img = LOOKS / x["image"]
        assert img.is_file() and img.stat().st_size < 120_000, x["id"]
        assert x.get("use") and x.get("notes") and x.get("example") and x.get("aliases"), x["id"]
    assert len(data()["looks"]) >= 59 and data().get("remind_rule")


def test_find_ranks_aliases():
    cases = {"عايز الراجل والست": "C01", "زي فيلم الخريطة بتاع ميار": "PM08", "ستايل الظلال": "PM09",
             "كاريوكي سونو": "PM02", "شتا اسكندرية": "W07", "W05": "W05"}
    for q, want in cases.items():
        r = run("tool", "looks", "find", q)
        assert r.returncode == 0, q
        if q == "ستايل الظلال":  # v1990.7: ST10 (shadow play, 11 Nov) and PM09 (shadow theatre) both fit; remind shows both pictures
            assert r.stdout.split()[0] in ("PM09", "ST10") and "PM09" in r.stdout and "ST10" in r.stdout, r.stdout
            continue
        assert r.stdout.split()[0] == want, (q, r.stdout)
    assert run("tool", "looks", "find", "xyzzy-nothing").returncode == 1


def test_remind_writes_picture_cards(tmp_path):
    r = run("tool", "looks", "remind", "مسرح الظل", "--out", str(tmp_path), "--top", "2")
    assert r.returncode == 0 and "PM09" in r.stdout and "SEND" in r.stdout
    assert (tmp_path / "PM09.jpg").is_file()


def test_harvest_reference_named_in_skill():
    skill = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    assert "PROJECT_HARVEST_V19906.md" in skill and "looks remind" in skill
    h = (SKILL / "references" / "PROJECT_HARVEST_V19906.md").read_text(encoding="utf-8")
    assert "82" in h and "remind" in h
