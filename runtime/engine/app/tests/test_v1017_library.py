"""v10.17.0 library: the owner's 12 skill packs + 4 prompt files bundled, indexed and searchable (read-only)."""
import hashlib
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

SKILL = Path(__file__).resolve().parents[2]
TOOL = SKILL / "tools" / "library" / "library.py"
spec = importlib.util.spec_from_file_location("bd_library", TOOL)
L = importlib.util.module_from_spec(spec)
spec.loader.exec_module(L)
LIB = json.loads((SKILL / "app" / "data" / "library.json").read_text(encoding="utf-8"))
PACK_IDS = {"ai-motion-graphics", "arabic-minimal-reels", "editorial-film-edit", "faceless-shorts", "growkaz-stickman",
            "living-site", "motion-reel", "saas-animation", "talking-head-reels", "pro-motion",
            "omar-hasan-kling-cinematic-director", "kosif-source-builder"}


def run(*args):
    r = subprocess.run([sys.executable, "-X", "utf8", str(TOOL), *args], capture_output=True, text=True, encoding="utf-8")
    return r.returncode, r.stdout, r.stderr


def test_index_schema_and_packs_present():
    assert LIB["schema"] == "black-dragon.library.v1"
    assert {p["id"] for p in LIB["packs"]} == PACK_IDS
    for p in LIB["packs"]:
        root = SKILL / "skills" / "library" / p["id"]
        assert (SKILL / p["entry"]).is_file(), p["id"]
        assert p["ar"] and p["en"] and p["overlap"]
        src = json.loads((root / "SOURCE.json").read_text(encoding="utf-8"))
        assert re.fullmatch(r"[0-9a-f]{64}", src["source_archive_sha256"]) and src["source_archive_sha256"] == p["source_archive_sha256"]
        have = sum(1 for f in root.rglob("*") if f.is_file() and f.name != "SOURCE.json" and "__pycache__" not in f.parts)
        assert have >= p["files"] > 0, p["id"]


def test_no_mac_junk_and_no_personal_photos():
    root = SKILL / "skills" / "library"
    assert not [f for f in root.rglob("*") if f.name == ".DS_Store" or f.name.startswith("._") or "__MACOSX" in f.parts]
    assert not list((root / "pro-motion" / "extras").rglob("*.jpg"))


def test_prompt_files_hashes_and_sections():
    assert {f["id"] for f in LIB["prompt_files"]} == {"hady", "minimal", "usip", "atlas"}
    for f in LIB["prompt_files"]:
        p = SKILL / f["file"]
        assert p.is_file() and hashlib.sha256(p.read_bytes()).hexdigest() == f["sha256"], f["file"]
    hady = [s for s in LIB["prompts"] if s["file"] == "hady"]
    atlas = [s for s in LIB["prompts"] if s["file"] == "atlas"]
    assert len(hady) == 19 and len(atlas) == 86
    lines = (SKILL / "references/prompts/hady-raie-prompt-library.md").read_text(encoding="utf-8").splitlines()
    for s in hady:
        assert lines[s["start"] - 1] == "### " + s["title"] and s["start"] <= s["end"] <= len(lines)
    assert len({s["id"] for s in LIB["prompts"]}) == len(LIB["prompts"])


def test_doctor_and_list():
    code, out, _ = run("doctor")
    rep = json.loads(out)
    assert code == 0 and rep["ok"] and rep["packs"] == 12 and rep["prompts"] == 105
    code, out, _ = run("list", "--json")
    rows = json.loads(out)
    assert code == 0 and len(rows) == 12 and all(r["present"] for r in rows)


@pytest.mark.parametrize("query,first", [
    ("ريل مينيمال عربي", "arabic-minimal-reels"),
    ("شورتس من غير وش", "faceless-shorts"),
    ("موقع حي 3D", "living-site"),
    ("product launch reel beat", "motion-reel"),
    ("kling cinematic director", "omar-hasan-kling-cinematic-director"),
])
def test_find_ranks_the_right_pack_first(query, first):
    code, out, _ = run("find", query, "--json")
    hits = json.loads(out)
    assert code == 0 and hits and hits[0]["id"] == first, hits[:3]


def test_find_reaches_prompts_and_misses_cleanly():
    code, out, _ = run("find", "seedance", "--json")
    assert code == 0 and {h["id"] for h in json.loads(out)} >= {"h07", "h08"}
    code, out, _ = run("find", "zzzqqqxxx")
    assert code == 1 and "مفيش نتيجة" in out


def test_prompt_hady_and_atlas_entries_are_bounded():
    code, out, _ = run("prompt", "h07", "--lines", "0")
    assert code == 0 and "Seedance 2.0 — Scene Architect" in out and "Seedance 2.5 Prompter" not in out
    code, out, _ = run("prompt", "a03", "--lines", "0", "--width", "300")
    assert code == 0 and "#03 — Shadow Puppet Theatre" in out and "#04 — " not in out
    code, out, _ = run("prompt", "shadow-puppet", "--lines", "4")
    assert code == 0 and "a03" in out.splitlines()[0]
    code, _, err = run("prompt", "nope")
    assert code == 2 and "unknown prompt id" in err


def test_show_and_grep():
    code, out, _ = run("show", "pro-motion", "--lines", "8")
    assert code == 0 and "name: pro-motion" in out and "SKILL.md" in out
    code, _, err = run("show", "nope")
    assert code == 2 and "faceless-shorts" in err
    code, out, _ = run("grep", "Slice of Life", "--limit", "3")
    assert code == 0 and "hady-raie-prompt-library.md" in out
    assert run("grep", "zzzqqqxxx")[0] == 1


def test_tool_is_read_only_source():
    src = TOOL.read_text(encoding="utf-8")
    assert not re.search(r"\bsubprocess\b|os\.system|\.write_text|\.write_bytes|open\([^)]*['\"][wa]", src)


def test_registered_in_dragon_and_registry():
    d = (SKILL / "scripts" / "dragon.py").read_text(encoding="utf-8")
    assert '"library": "tools/library/library.py"' in d
    ids = {t["id"] for t in json.loads((SKILL / "app/data/own_tools.json").read_text(encoding="utf-8"))["tools"]}
    assert "library" in ids
    r = subprocess.run([sys.executable, "-X", "utf8", str(SKILL / "scripts" / "dragon.py"), "tool", "library", "doctor"],
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0 and '"ok": true' in r.stdout


def test_brain_sees_library_packs_as_bundled_skills():
    names = {md.parent.name for md in (SKILL / "skills").glob("*/*/SKILL.md")}
    assert {"faceless-shorts", "living-site", "arabic-minimal-reels", "pro-motion", "ai-motion-graphics"} <= names
