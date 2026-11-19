"""v1990.8: the owner's nature-palette skill is bundled and reachable as `tool palette`. Offline."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

SKILL = Path(__file__).resolve().parents[2]
KIT = SKILL / "tools" / "nature_palette"


def test_bundled_and_registered():
    for f in ("scripts/nature_palette.py", "data/color_names.json", "assets/Cairo.ttf", "assets/Cairo-OFL.txt", "references/METHOD.md"):
        assert (KIT / f).is_file(), f
    assert '"palette": "tools/nature_palette/scripts/nature_palette.py"' in (SKILL / "scripts" / "dragon.py").read_text(encoding="utf-8")


def test_extract_makes_card_and_json(tmp_path):
    pytest.importorskip("numpy")
    pytest.importorskip("PIL")
    img = SKILL / "tools" / "looks" / "img" / "ref_couple_umbrellas.jpg"
    r = subprocess.run([sys.executable, str(SKILL / "scripts" / "dragon.py"), "tool", "palette", "extract", str(img),
                        "--title", "تجربة", "--out", str(tmp_path)], capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr[-400:]
    js = list(tmp_path.glob("*_palette.json"))
    assert js and list(tmp_path.glob("*_palette_card.png"))
    d = json.loads(js[0].read_text(encoding="utf-8"))
    assert "#" in json.dumps(d)
