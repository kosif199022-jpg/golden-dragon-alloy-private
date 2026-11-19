"""v10.17.0 merge: dragon-genius + omni-analyst bundled verbatim, bridged, registered, privacy-clean.

These skills were created across the Black Dragon sessions and are the two that had not yet
been folded into the dragon. This test proves they are present, their bridges run offline, their
cards are registered, and no owner identity leaked into the shipped source.
"""
import ast
import json
import re
import subprocess
import sys
from pathlib import Path

SKILL = Path(__file__).resolve().parents[2]
GEN = SKILL / "skills" / "dragon-genius"
OMNI = SKILL / "skills" / "omni-analyst"
GEN_BRIDGE = SKILL / "tools" / "genius" / "bridge.py"
OMNI_BRIDGE = SKILL / "tools" / "omni" / "bridge.py"
OWN = json.loads((SKILL / "app" / "data" / "own_tools.json").read_text(encoding="utf-8"))["tools"]


def test_skills_bundled():
    assert (GEN / "SKILL.md").is_file()
    assert (OMNI / "SKILL.md").is_file()
    assert (GEN / "scripts" / "media_gate.py").is_file()
    assert (GEN / "scripts" / "transcript_qa.py").is_file()
    assert (OMNI / "scripts" / "omni.py").is_file()


def test_bridges_compile_and_registered():
    for b in (GEN_BRIDGE, OMNI_BRIDGE):
        assert b.is_file()
        ast.parse(b.read_text(encoding="utf-8"))
    launcher = (SKILL / "scripts" / "dragon.py").read_text(encoding="utf-8")
    assert '"genius": "tools/genius/bridge.py"' in launcher
    assert '"omni": "tools/omni/bridge.py"' in launcher


def test_cards_and_entrypoints_registered():
    ids = {t["id"] for t in OWN}
    assert {"genius", "omni"} <= ids
    for t in OWN:
        assert {"id", "ar", "en", "cmd", "what"} <= set(t)
    cap = (SKILL / "app" / "dragon" / "capabilities.py").read_text(encoding="utf-8")
    assert '"dragon-genius": ("file", "tools/genius/bridge.py")' in cap
    assert '"omni-analyst": ("file", "tools/omni/bridge.py")' in cap


def test_privacy_no_owner_identity_in_source():
    # Runtime output may legitimately contain the user's own home path; the shipped SOURCE must not.
    bad = re.compile(r"(?i)\bcinde\b|aghnam|@gmail")
    for root in (GEN, OMNI):
        for f in root.rglob("*"):
            if f.is_file() and f.suffix in {".py", ".md", ".json", ".txt"}:
                assert not bad.search(f.read_text(encoding="utf-8", errors="ignore")), str(f)


def _run(bridge, *args):
    return subprocess.run([sys.executable, str(bridge), *args],
                          capture_output=True, text=True, encoding="utf-8")


def test_genius_bridge_runs_offline(tmp_path):
    assert _run(GEN_BRIDGE, "doctor").returncode == 0
    srt = tmp_path / "cap.srt"
    srt.write_text("1\n00:00:00,000 --> 00:00:02,000\nمرحبا بالعالم\n", encoding="utf-8")
    r = _run(GEN_BRIDGE, "qa", str(srt), "--json")
    assert "verdict" in json.loads(r.stdout)


def test_omni_bridge_runs_offline():
    assert _run(OMNI_BRIDGE, "doctor").returncode == 0
    r = _run(OMNI_BRIDGE, "classify", str(OMNI_BRIDGE))
    assert r.returncode == 0
    assert json.loads(r.stdout)["kind"] == "python_src"
    r = _run(OMNI_BRIDGE, "bayes", "0.5", "2.0")
    assert r.returncode == 0


def test_omni_source_has_no_hardcoded_user_path():
    src = (OMNI / "scripts" / "omni.py").read_text(encoding="utf-8")
    assert "C:\\Users\\cinde" not in src
    assert "RETOOL = os.environ.get" in src
