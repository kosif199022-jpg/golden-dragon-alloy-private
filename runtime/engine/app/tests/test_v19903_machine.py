"""v1990.3: start door, laptop-or-cloud question, machine map, gated PC control."""
import json, os, subprocess, sys
from pathlib import Path

SKILL = Path(__file__).resolve().parents[2]
DRAGON = SKILL / "scripts" / "dragon.py"


def run(*args, env=None):
    e = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1", **(env or {}))
    p = subprocess.run([sys.executable, "-X", "utf8", str(DRAGON), *args], capture_output=True, text=True, encoding="utf-8", errors="replace", env=e)
    return p.returncode, p.stdout, p.stderr


def test_start_asks_the_question():
    code, out, _ = run("start")
    assert code == 0 and "على اللابتوب" in out and "tool machine mode laptop" in out and "tool machine mode cloud" in out
    code2, out2, _ = subprocess.run([sys.executable, "-X", "utf8", str(SKILL / "start.py")], capture_output=True, text=True, encoding="utf-8").returncode, out, ""
    assert code2 == 0


def test_start_json_and_tool_registered():
    code, out, _ = run("start", "--json")
    d = json.loads(out)
    assert code == 0 and d["tools_registered"] >= 59 and "evidence" in d and d["machine_map"]["found"] > 50
    assert '"machine": "tools/machine/machine.py"' in DRAGON.read_text(encoding="utf-8")


def test_cloud_playbook_never_uses_laptop_paths(tmp_path):
    # the answer is saved under the home folder: point it at a temp folder so the test leaves nothing in the package
    code, out, _ = run("tool", "machine", "mode", "cloud", env={"DRAGON_MODE": "cloud", "USERPROFILE": str(tmp_path), "HOME": str(tmp_path)})
    assert (tmp_path / ".black-dragon" / "where.json").is_file()
    assert code == 0 and "وضع السحابة" in out and "re-tools\\" not in out


def test_laptop_claim_with_cloud_evidence_is_honest():
    code, out, _ = run("tool", "machine", "mode", "laptop", env={"DRAGON_MODE": "cloud"})
    assert code == 0 and "الدليل هنا بيقول غير كده" in out


def test_map_has_reverse_engineering_and_media():
    m = json.loads((SKILL / "tools" / "machine" / "machine_map.json").read_text(encoding="utf-8"))
    ids = {i["id"] for i in m["items"] if i.get("path")}
    assert {"ffmpeg", "blender", "re:ghidra", "re:jadx", "re:die", "retool", "dragon-app"} <= ids
    assert not any("token" in json.dumps(i).lower() for i in m["items"])
    code, out, _ = run("tool", "machine", "path", "ffmpeg")
    assert code == 0 and out.strip().lower().endswith("ffmpeg.exe")
    code, out, _ = run("tool", "machine", "find", "بلندر")
    assert code == 0 and "blender" in out


def test_pc_control_is_gated():
    code, _, err = run("tool", "machine", "pc", "info", env={"DRAGON_MODE": "cloud"})
    assert code == 3 and "لابتوب" in err                      # refused off the laptop
    if os.name == "nt":
        code, _, err = run("tool", "machine", "pc", "shutdown")
        assert code == 3 and "--yes" in err                   # dangerous action without the owner's yes
        code, _, err = run("tool", "machine", "pc", "kill", "--target", "notepad")
        assert code == 3


def test_docs_present():
    for f in ("START_HERE.md", "start.py", "references/MACHINE_MAP.md", "references/CLAUDE_AND_APP_POWERS_V19903.md",
              "app/apps/dragon_desktop/control.py", "app/apps/dragon_desktop/app.py"):
        assert (SKILL / f).is_file(), f
    assert "v1990.3" in (SKILL / "SKILL.md").read_text(encoding="utf-8")[:2500]
