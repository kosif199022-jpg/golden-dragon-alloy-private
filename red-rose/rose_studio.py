"""Red Rose Studio: local-only dashboard, no external services or arbitrary shell."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = Path(__file__).resolve().parent
TOKEN = secrets.token_urlsafe(32)
LOCK = threading.Lock()
PY = sys.executable.replace("pythonw.exe", "python.exe")
ROSE = [PY, "-X", "utf8", str(ROOT / "rose.py")]
MAINT = [PY, "-X", "utf8", str(ROOT / "rose_maintenance.py")]

ACTIONS = {
    "start": (ROSE + ["start"], 90, False),
    "ops": (ROSE + ["ops"], 90, False),
    "brief": (ROSE + ["brief"], 90, True),
    "find": (ROSE + ["find"], 90, True),
    "describe": (ROSE + ["describe"], 90, True),
    "verify": (ROSE + ["verify"], 180, True),
    "audit": (MAINT + ["audit"], 90, False),
    "benchmark": (MAINT + ["benchmark"], 180, False),
    "test": (MAINT + ["test", "--timeout", "180"], 200, False),
    "repair_preview": (MAINT + ["repair"], 90, False),
    "repair": (MAINT + ["repair", "--approve-write"], 240, False),
}

def command(action, value="", approved=False):
    if action not in ACTIONS:
        raise ValueError("Unknown operation")
    if action == "repair" and approved is not True:
        raise ValueError("Explicit repair approval required")
    args, timeout, needs_value = ACTIONS[action]
    if needs_value:
        if not isinstance(value, str) or not value.strip() or len(value) > 4000 or value.lstrip().startswith("-"):
            raise ValueError("A valid input is required")
        return args + [value.strip()], timeout
    return list(args), timeout

def run(action, value="", approved=False):
    args, timeout = command(action, value, approved)
    if not LOCK.acquire(blocking=False):
        return {"ok": False, "error": "Another operation is already running"}
    begin = time.monotonic()
    try:
        with tempfile.TemporaryDirectory(prefix="red-rose-ui-") as tmp:
            env = dict(os.environ, PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1",
                       RED_ROSE_DB=str(Path(tmp) / "ui.sqlite3"))
            try:
                p = subprocess.run(args, cwd=ROOT, env=env, capture_output=True,
                                   text=True, encoding="utf-8", errors="replace", timeout=timeout,
                                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                return {"ok": p.returncode == 0, "exit": p.returncode,
                        "seconds": round(time.monotonic()-begin, 2),
                        "output": p.stdout[:120000], "error": p.stderr[:12000],
                        "truncated": len(p.stdout)>120000 or len(p.stderr)>12000}
            except subprocess.TimeoutExpired:
                return {"ok": False, "exit": 124, "seconds": round(time.monotonic()-begin, 2),
                        "error": "Time limit exceeded; command stopped"}
    finally:
        LOCK.release()

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass
    def send(self, code, body, kind="application/json; charset=utf-8"):
        if not isinstance(body, bytes):
            body=json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'")
        self.end_headers()
        self.wfile.write(body)
    def valid_host(self):
        return self.headers.get("Host") == f"127.0.0.1:{self.server.server_port}"
    def do_GET(self):
        if not self.valid_host():
            return self.send(403, {"error":"Forbidden"})
        if self.path == "/health":
            return self.send(200, {"ok":True, "app":"Red Rose Studio", "maintenance":(ROOT/"rose_maintenance.py").is_file()})
        if self.path != "/":
            return self.send(404, {"error":"Not found"})
        html=(ROOT/"rose_studio.html").read_text(encoding="utf-8").replace("__ROSE_TOKEN__", TOKEN)
        self.send(200, html.encode("utf-8"), "text/html; charset=utf-8")
    def do_POST(self):
        origin=f"http://127.0.0.1:{self.server.server_port}"
        if self.path != "/api/run" or not self.valid_host() or self.headers.get("Origin") != origin or self.headers.get("X-Rose-Token") != TOKEN:
            return self.send(403, {"error":"Forbidden"})
        try:
            length=int(self.headers.get("Content-Length","0"))
            if not 0 < length <= 24000: raise ValueError("Invalid request size")
            data=json.loads(self.rfile.read(length))
            if not isinstance(data,dict): raise ValueError("Invalid request")
            result=run(data.get("action"), data.get("value",""), data.get("approved",False))
            self.send(200,result)
        except (ValueError, TypeError, OSError) as e:
            self.send(400,{"ok":False,"error":str(e)})

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--no-browser", action="store_true")
    p.add_argument("--self-test", action="store_true")
    a=p.parse_args()
    if a.self_test:
        assert command("find","Arabic")[0][-1]=="Arabic"
        for action,value,approved in [("cmd","whoami",True),("brief","--help",False),("repair","",False)]:
            try: command(action,value,approved)
            except ValueError: continue
            raise AssertionError("Disallowed operation accepted")
        assert (ROOT/"rose_studio.html").is_file()
        print("Studio self-test passed")
        return
    server=ThreadingHTTPServer(("127.0.0.1",a.port),Handler)
    if not a.no_browser:
        webbrowser.open(f"http://127.0.0.1:{server.server_port}/")
    server.serve_forever()

if __name__=="__main__":
    main()
