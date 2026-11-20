# -*- coding: utf-8 -*-
"""Tests for claude-app: prompt generator, brain hook, standalone MCP server, installer. Offline; nothing outside tmp is touched
(the MCP registration is skipped with --no-mcp, and the approval box is replaced)."""
import json, subprocess, sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
import gen_prompt  # noqa: E402
import golden_mcp  # noqa: E402
import install  # noqa: E402


# ---------------------------------------------------------------- prompt
def test_prompt_is_the_apps_own_text():
    t = gen_prompt.build()
    assert len(t) > 20000
    assert "التنين الذهبي" in t and "وضع الاشتراك" in t and "بروتوكول التنين الذهبي" in t
    assert "mcp__golden-dragon-app__" in t
    assert "{_home_of" not in t and "{REPO}" not in t and "{APP_SOURCE}" not in t
    assert str((HERE.parent / "app").resolve()) in t          # APP_SOURCE points at the app next to us


def test_reviewer_prompt():
    r = gen_prompt.reviewer()
    assert "REVIEWER" in r and len(r) > 300


# ---------------------------------------------------------------- hook
def run_hook(payload, env_extra=None):
    import os
    env = dict(os.environ, PYTHONIOENCODING="utf-8", **(env_extra or {}))
    return subprocess.run([sys.executable, "-X", "utf8", str(HERE / "brief_hook.py")], input=json.dumps(payload, ensure_ascii=False),
                          capture_output=True, text=True, encoding="utf-8", env=env, timeout=30)


def test_hook_never_blocks():
    r = run_hook({"prompt": ""})
    assert r.returncode == 0 and r.stdout.strip() == ""
    r = run_hook({"prompt": "اعمل ريل"}, {"GD_RD": "C:/nope/rd.py"})
    assert r.returncode == 0 and r.stdout.strip() == ""


@pytest.mark.skipif(not (Path.home() / ".claude/skills/golden-dragon/scripts/rd.py").is_file(), reason="rd.py not installed")
def test_hook_gives_brain_note():
    r = run_hook({"prompt": "استخرج ألوان الطائر ده من الصورة"})
    assert r.returncode == 0
    assert r.stdout.startswith("🐉 عقل التنين الذهبي") and len(r.stdout) <= 2100


# ---------------------------------------------------------------- MCP server
def rpc(msgs, env=None):
    p = subprocess.run([sys.executable, "-X", "utf8", str(HERE / "golden_mcp.py")], input="\n".join(json.dumps(m) for m in msgs) + "\n",
                       capture_output=True, text=True, encoding="utf-8", timeout=120, env=env)
    return {m["id"]: m for m in map(json.loads, p.stdout.splitlines())}


def test_mcp_protocol_and_tools():
    out = rpc([{"jsonrpc": "2.0", "id": 0, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}},
               {"jsonrpc": "2.0", "method": "notifications/initialized"},
               {"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
               {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "control", "arguments": {"action": "status"}}},
               {"jsonrpc": "2.0", "id": 3, "method": "nope"}])
    assert out[0]["result"]["serverInfo"]["name"] == "golden-dragon-app"
    names = {t["name"] for t in out[1]["result"]["tools"]}
    assert names == {"computer", "system", "browser", "fusion", "gold", "skills", "voice", "compare", "control"}
    st = json.loads(out[2]["result"]["content"][0]["text"])
    assert st["halted"] is False
    assert "error" in out[3]


def test_tool_answers_while_stdin_stays_open():
    """Regression: Claude Code keeps the server's stdin open. A child that inherited it hung `fusion doctor` for 600 s."""
    import threading, time
    p = subprocess.Popen([sys.executable, "-X", "utf8", str(HERE / "golden_mcp.py")], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                         text=True, encoding="utf-8")
    try:
        def send(m):
            p.stdin.write(json.dumps(m) + "\n")
            p.stdin.flush()
        send({"jsonrpc": "2.0", "id": 0, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}})
        p.stdout.readline()
        send({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "fusion", "arguments": {"args": ["doctor"]}}})
        got = []
        threading.Thread(target=lambda: got.append(p.stdout.readline()), daemon=True).start()
        t0 = time.time()
        while not got and time.time() - t0 < 60:
            time.sleep(0.2)
        assert got, "fusion doctor didn't answer within 60 s with stdin open"
        assert "فحص التنين الذهبي" in json.loads(got[0])["result"]["content"][0]["text"]
    finally:
        p.kill()


@pytest.fixture
def skills(tmp_path, monkeypatch):
    d = tmp_path / "skills"
    (d / "demo-skill").mkdir(parents=True)
    (d / "demo-skill" / "SKILL.md").write_text("---\nname: demo-skill\ndescription: blender demo for tests\n---\nhello", encoding="utf-8")
    (d / "demo-skill" / "ref.md").write_text("ref", encoding="utf-8")
    monkeypatch.setattr(golden_mcp, "SKILLS", d)
    monkeypatch.setattr(golden_mcp, "HOME", tmp_path)
    return d


def test_skills_list_read_and_traversal(skills):
    r = golden_mcp.call_tool("skills", {"action": "list", "query": "blender"})
    assert "demo-skill" in r["content"][0]["text"] and not r["isError"]
    r = golden_mcp.call_tool("skills", {"action": "read", "name": "demo-skill"})
    assert "hello" in r["content"][0]["text"] and "ref.md" in r["content"][0]["text"]
    r = golden_mcp.call_tool("skills", {"action": "read", "name": "demo-skill", "file": "../../x"})
    assert r["isError"]
    r = golden_mcp.call_tool("skills", {"action": "read", "name": "..\\x"})
    assert r["isError"]


def test_skill_install_and_remove_need_yes(skills, tmp_path, monkeypatch):
    src = tmp_path / "new"
    src.mkdir()
    (src / "SKILL.md").write_text("---\nname: new-one\ndescription: x\n---\n", encoding="utf-8")
    asked = []
    monkeypatch.setattr(golden_mcp, "confirm", lambda t, *a: asked.append(t) or False)
    r = golden_mcp.call_tool("skills", {"action": "install", "source": str(src)})
    assert r["isError"] and not (skills / "new-one").exists() and asked
    monkeypatch.setattr(golden_mcp, "confirm", lambda t, *a: True)
    r = golden_mcp.call_tool("skills", {"action": "install", "source": str(src)})
    assert not r["isError"] and (skills / "new-one" / "SKILL.md").exists()
    # zip with a path-traversal member is contained
    import zipfile
    z = tmp_path / "s.zip"
    with zipfile.ZipFile(z, "w") as f:
        f.writestr("pkg/SKILL.md", "---\nname: zipped\ndescription: z\n---\n")
        f.writestr("pkg/../../evil.txt", "x")
    r = golden_mcp.call_tool("skills", {"action": "install", "source": str(z)})
    assert not r["isError"] and (skills / "zipped" / "SKILL.md").exists()
    assert not (tmp_path / "evil.txt").exists()
    r = golden_mcp.call_tool("skills", {"action": "remove", "name": "new-one"})
    assert not r["isError"] and not (skills / "new-one").exists()
    assert list((tmp_path / ".claude" / "skills_backup").rglob("new-one/SKILL.md"))


def test_dangerous_system_action_needs_yes(monkeypatch):
    ran = []

    class FakeSys:
        def describe(self, act, a):
            return act

        def run(self, act, a):
            ran.append(act)
            return "done"

    class FakeComp:
        halted = False

        def check(self):
            pass

    monkeypatch.setattr(golden_mcp, "_system", FakeSys())
    monkeypatch.setattr(golden_mcp, "_computer", FakeComp())
    monkeypatch.setattr(golden_mcp, "confirm", lambda *a: False)
    r = golden_mcp.call_tool("system", {"action": "shutdown"})
    assert r["isError"] and ran == []
    r = golden_mcp.call_tool("system", {"action": "volume", "amount": 30})     # not dangerous: no box
    assert not r["isError"] and ran == ["volume"]
    monkeypatch.setattr(golden_mcp, "confirm", lambda *a: True)
    r = golden_mcp.call_tool("system", {"action": "kill", "target": "notepad"})
    assert not r["isError"] and ran == ["volume", "kill"]


def test_emergency_stop_blocks_and_resume(monkeypatch):
    import control
    c = control.Computer()
    c.halted = True
    monkeypatch.setattr(golden_mcp, "_computer", c)
    r = golden_mcp.call_tool("system", {"action": "info"})
    assert r["isError"] and "Stopped" in r["content"][0]["text"]
    golden_mcp.call_tool("control", {"action": "resume"})
    assert c.halted is False


# ---------------------------------------------------------------- installer
def test_install_is_idempotent_and_uninstall_restores(tmp_path):
    cl = tmp_path / ".claude"
    cl.mkdir()
    repo = tmp_path / "Desktop" / "مهارات" / "التنين الأسود"
    repo.mkdir(parents=True)
    (cl / "CLAUDE.md").write_text("# mine\nkeep me\n", encoding="utf-8")
    (cl / "settings.json").write_text(json.dumps({"theme": "dark", "hooks": {"Stop": [{"hooks": [{"type": "command", "command": "x"}]}]}}),
                                      encoding="utf-8")
    for _ in range(2):
        assert install.main(["--home", str(tmp_path), "--no-mcp"]) == 0
    cm = (cl / "CLAUDE.md").read_text(encoding="utf-8")
    assert cm.count(install.START) == 1 and "keep me" in cm and "GOLDEN.md" in cm
    s = json.loads((cl / "settings.json").read_text(encoding="utf-8"))
    assert s["theme"] == "dark" and len(s["hooks"]["UserPromptSubmit"]) == 1 and "Stop" in s["hooks"]
    assert (cl / "golden-dragon" / "GOLDEN.md").stat().st_size > 20000
    rv = (cl / "agents" / "golden-reviewer.md").read_text(encoding="utf-8")
    assert rv.startswith("---\nname: golden-reviewer") and "REVIEWER" in rv
    assert s["permissions"]["additionalDirectories"] == [str(repo)]
    cmd = (cl / "golden-dragon" / "golden-dragon.cmd").read_text(encoding="utf-8")
    assert f'--add-dir "{repo}"' in cmd and "cc_system.md" not in cmd
    st = install.Inst(tmp_path).status()
    assert st["CLAUDE.md import"] and st["hook"] and all(st["agents"].values()) and st["launcher"]

    assert install.main(["--home", str(tmp_path), "--no-mcp", "--uninstall"]) == 0
    cm = (cl / "CLAUDE.md").read_text(encoding="utf-8")
    assert install.START not in cm and "keep me" in cm
    s = json.loads((cl / "settings.json").read_text(encoding="utf-8"))
    assert "UserPromptSubmit" not in s.get("hooks", {}) and "Stop" in s["hooks"] and s["theme"] == "dark"
    assert "permissions" not in s and not (cl / "golden-dragon" / "golden-dragon.cmd").exists()
    assert not (cl / "agents" / "golden-reviewer.md").exists()


def test_install_keeps_users_own_agent(tmp_path):
    a = tmp_path / ".claude" / "agents"
    a.mkdir(parents=True)
    (a / "golden-helper.md").write_text("---\nname: golden-helper\n---\nmine", encoding="utf-8")
    install.main(["--home", str(tmp_path), "--no-mcp"])
    assert (a / "golden-helper.md").read_text(encoding="utf-8").endswith("mine")      # never overwritten
    install.main(["--home", str(tmp_path), "--no-mcp", "--uninstall"])
    assert (a / "golden-helper.md").read_text(encoding="utf-8").endswith("mine")      # never removed
