"""v1990.8: the owner's chroma-motion skill is bundled and reachable as `tool chroma`. Offline (no subject model)."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

SKILL = Path(__file__).resolve().parents[2]
KIT = SKILL / "tools" / "chroma_motion"


def test_bundled_and_registered():
    for f in ("scripts/chroma_identity.py", "assets/fonts/Cairo.ttf", "assets/fonts/Amiri-Bold.ttf", "SKILL_chroma_motion.md"):
        assert (KIT / f).is_file(), f
    assert not list(KIT.rglob("*.pyc"))
    assert '"chroma": "tools/chroma_motion/scripts/chroma_identity.py"' in (SKILL / "scripts" / "dragon.py").read_text(encoding="utf-8")


def test_identity_without_video(tmp_path):
    pytest.importorskip("numpy")
    pytest.importorskip("PIL")
    img = SKILL / "tools" / "looks" / "img" / "ref_couple_umbrellas.jpg"
    r = subprocess.run([sys.executable, "-X", "utf8", str(SKILL / "scripts" / "dragon.py"), "tool", "chroma", str(img), "--name", "تجربة",
                        "--out", str(tmp_path), "--video", "none", "--subject", "off"], capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr[-400:]
    d = json.loads((tmp_path / "palette.json").read_text(encoding="utf-8"))
    assert (tmp_path / "brand_board.png").stat().st_size > 50_000 and (tmp_path / "tokens.css").is_file()
    assert "roles" in d or "primary" in json.dumps(d)
