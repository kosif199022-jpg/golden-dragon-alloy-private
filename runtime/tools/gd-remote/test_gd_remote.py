"""gd-remote tests: a fake Golden Dragon on 127.0.0.1 (random port) and fake config files in pytest's temp folder.
Run: python -X utf8 -m pytest -q tools/gd-remote"""
import importlib.util
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

HERE = Path(__file__).resolve().parent


def load(name):
    spec = importlib.util.spec_from_file_location(name, HERE / f"{name}.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


@pytest.fixture()
def fake_app(tmp_path, monkeypatch):
    seen = []
    state = {"busy": 2}

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_POST(self):
            q = parse_qs(urlparse(self.path).query)
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])).decode("utf-8"))
            if urlparse(self.path).path != "/app" or q.get("t", [""])[0] != "tok-123":
                self.send_response(403)
                self.end_headers()
                return
            seen.append(body)
            if body["action"] == "send":
                res = {"ok": True, "sid": "c1"}
            elif body["action"] == "reply":
                state["busy"] -= 1
                res = {"ok": True, "busy": state["busy"] > 0, "reply": "تمام"}
            else:
                res = {"ok": True, "chats": []}
            data = json.dumps(res).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps({"bridge_token": "tok-123"}), encoding="utf-8")
    monkeypatch.setenv("GD_PORT", str(srv.server_address[1]))
    monkeypatch.setenv("GD_SETTINGS", str(settings))
    gr = load("gd_remote")
    yield gr, seen, settings
    srv.shutdown()


def test_status_and_ask(fake_app, capsys):
    gr, seen, _ = fake_app
    assert gr.main(["status"]) == 0
    r = gr.ask("اعمل ريل", wait=30, poll=0.01)
    assert r["reply"] == "تمام" and not r["busy"]
    assert [b["action"] for b in seen] == ["status", "send", "reply", "reply"]
    assert seen[1]["text"] == "اعمل ريل"


def test_token_never_printed(fake_app, capsys):
    gr, _, _ = fake_app
    gr.main(["chats"])
    gr.main(["ping"])
    assert "tok-123" not in capsys.readouterr().out


def test_bad_token_and_app_down(fake_app, monkeypatch):
    gr, _, settings = fake_app
    settings.write_text(json.dumps({"bridge_token": "wrong"}), encoding="utf-8")
    assert gr.main(["status"]) == 3
    settings.write_text(json.dumps({"bridge_token": "tok-123"}), encoding="utf-8")
    monkeypatch.setattr(gr, "PORT", "1")
    assert gr.main(["ping"]) == 3


def test_missing_args():
    gr = load("gd_remote")
    assert gr.main(["send"]) == 2 and gr.main(["reply"]) == 2 and gr.main([]) == 2


def test_connect_plan_apply_remove(tmp_path, monkeypatch):
    monkeypatch.setenv("GD_CONNECT_NO_CLI", "1")
    c = load("connect")
    code = tmp_path / ".claude.json"
    desk = tmp_path / "claude_desktop_config.json"
    code.write_text(json.dumps({"mcpServers": {"rea": {"command": "x", "env": {"K": "secret"}}}, "other": 1}), encoding="utf-8")
    desk.write_text(json.dumps({"mcpServers": {}}), encoding="utf-8")
    monkeypatch.setattr(c, "targets", lambda: [("Claude Code", code), ("Claude Desktop", desk)])
    before = code.read_text(encoding="utf-8")
    assert c.main([]) == 0 and code.read_text(encoding="utf-8") == before, "dry run writes nothing"
    assert c.main(["--apply"]) == 0
    cfg = json.loads(code.read_text(encoding="utf-8"))
    assert cfg["mcpServers"]["rea"] == {"command": "x", "env": {"K": "secret"}} and cfg["other"] == 1
    gd = cfg["mcpServers"]["golden-dragon"]
    assert gd["env"]["BD_SCOPE"] == "claude-code" and gd["env"]["BD_PORT"] == "47851"
    assert "token" not in json.dumps(gd).lower()
    assert list(tmp_path.glob(".claude.json.bak-gd-*")), "backup made first"
    assert all(a == "skip" for _, _, a, _ in c.plan()), "second run changes nothing"
    assert c.main(["--remove", "--apply"]) == 0
    assert "golden-dragon" not in json.loads(desk.read_text(encoding="utf-8"))["mcpServers"]


def test_server_offers_app_tool_not_raw_control():
    src = (HERE.parent.parent / "apps" / "golden-dragon" / "app" / "mcp_dragon.py").read_text(encoding="utf-8")
    assert 'elif os.environ.get("BD_SCOPE") == "claude-code":' in src
    assert "TOOLS_WITH_ALIASES = TOOLS[:-2] + [APP_TOOL]" in src
    assert '"GoldenDragon" / "settings.json"' in src and '"BD_PORT", "47851"' in src
