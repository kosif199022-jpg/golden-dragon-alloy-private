"""Cloud browser «سحاب»: a real Chromium on this machine/server, streamed live to any browser (tabs, input, Arabic, downloads).

The server (server.py) runs headless Chromium through Playwright, streams CDP screencast JPEG frames over a WebSocket
and replays mouse/keyboard/touch through CDP Input.*. This module starts/stops it in the background and remembers
its URL + token in %LOCALAPPDATA%\\BlackDragon\\sahab\\engine.json so every Dragon command finds the same session.
"""
import json, os, secrets, subprocess, sys, time, urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = Path(os.environ.get("SAHAB_DATA") or Path(os.environ.get("LOCALAPPDATA", HERE)) / "BlackDragon" / "sahab")
STATE = DATA / "engine.json"


def _state() -> dict:
    try:
        return json.loads(STATE.read_text("utf-8"))
    except Exception:
        return {}


def _alive(pid) -> bool:
    if not pid:
        return False
    out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True).stdout if os.name == "nt" \
        else ("x" if Path(f"/proc/{pid}").exists() else "")
    return str(pid) in out


def _up(port, host="127.0.0.1") -> bool:
    try:
        urllib.request.urlopen(f"http://{host}:{port}/static/index.html", timeout=2)
        return True
    except Exception:
        return False


def status() -> dict:
    s = _state()
    running = _alive(s.get("pid")) and _up(s.get("port", 0))
    return {"running": running, **({k: s[k] for k in ("url", "port", "pid", "host") if k in s} if running else {}),
            "data": str(DATA)}


def start(port=8800, host="127.0.0.1", open_browser=False, extra=(), wait=60) -> dict:
    """Start the server in the background (idempotent). Returns {"url": ..., "pid": ...}."""
    st = status()
    if st["running"] and st.get("port") != port:
        raise RuntimeError(f"سحاب شغال بالفعل على المنفذ {st.get('port')} — اقفله بـ stop الأول أو استخدم نفس المنفذ")
    if st["running"]:
        if open_browser:
            os.startfile(st["url"]) if os.name == "nt" else None
        return st
    DATA.mkdir(parents=True, exist_ok=True)
    token = _state().get("token") or secrets.token_urlsafe(18)
    log = open(DATA / "server.log", "w", encoding="utf-8")
    flags = (subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW) if os.name == "nt" else 0
    p = subprocess.Popen([sys.executable, str(HERE / "server.py"), "--host", host, "--port", str(port), "--token", token,
                          "--data", str(DATA), *extra],
                         cwd=str(HERE), stdout=log, stderr=subprocess.STDOUT, creationflags=flags,
                         env=dict(os.environ, PYTHONIOENCODING="utf-8"))
    shown = "127.0.0.1" if host in ("0.0.0.0", "::") else host
    url = f"http://{shown}:{port}/?token={token}"
    STATE.write_text(json.dumps({"pid": p.pid, "port": port, "host": host, "token": token, "url": url}), "utf-8")
    t0 = time.time()
    while time.time() - t0 < wait:
        if p.poll() is not None:
            raise RuntimeError("سحاب وقف وهو بيبدأ:\n" + (DATA / "server.log").read_text("utf-8", "replace")[-1500:])
        if _up(port, shown):
            if open_browser and os.name == "nt":
                os.startfile(url)
            return {"running": True, "url": url, "pid": p.pid, "port": port, "host": host, "data": str(DATA)}
        time.sleep(0.5)
    raise TimeoutError(f"سحاب مافتحش على المنفذ {port} خلال {wait} ثانية؛ اللوج: {DATA / 'server.log'}")


def stop() -> dict:
    s = _state()
    pid = s.get("pid")
    if pid and _alive(pid):
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)
        else:
            os.kill(pid, 15)
        return {"stopped": True, "pid": pid}
    return {"stopped": False, "reason": "مش شغال"}


def doctor() -> dict:
    import importlib.util as u
    mods = {m: bool(u.find_spec(m)) for m in ("playwright", "aiohttp")}
    pw = Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright"
    chromium = sorted(p.name for p in pw.glob("chromium-*")) if pw.exists() else []
    return {"modules": mods, "playwright_chromium": chromium, "server": str(HERE / "server.py"), **status()}
