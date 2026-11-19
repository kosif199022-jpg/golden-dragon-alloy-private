"""KOSIF downloads «كوسيف»: IDM-style accelerated downloads inside the Black Dragon — multi-connection dynamic segmentation, resume, page videos via yt-dlp, and control of the KOSIF desktop app.

Two ways to use it:
  1) fetch  — headless, in-process: the KOSIF core downloads straight into a work folder with up to 32 connections,
              waits, then measures every file (size, SHA-256, and ffprobe duration/size for media). Its own state lives in
              %LOCALAPPDATA%\\BlackDragon\\kosif, so these jobs never appear in the user's KOSIF window.
  2) send/list/pause/resume/remove/open/quit — talk to the KOSIF desktop app (KOSIF.exe) over its local token-protected
              API on 127.0.0.1:9614; the app is started in the background when needed.
Core: engines/kosif/core.py (vendored from KOSIF 1.0.0). App: Desktop\\KOSIF\\KOSIF.exe (or the source tree).
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

PORT = 9614
BASE = f"http://127.0.0.1:{PORT}"
APP_DATA = Path(os.environ.get("APPDATA", Path.home())) / "KOSIF"            # the desktop app's settings/state
DRAGON_DATA = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "BlackDragon" / "kosif"
SOURCE_TREE = Path.home() / ".claude" / "skills" / "output" / "KOSIF"
QUALITY = {"best": "", "2160": "bv*[height<=2160]+ba/b[height<=2160]", "1080": "bv*[height<=1080]+ba/b[height<=1080]",
           "720": "bv*[height<=720]+ba/b[height<=720]", "480": "bv*[height<=480]+ba/b[height<=480]", "audio": "ba/b"}
MEDIA_EXT = {".mp4", ".mkv", ".webm", ".mov", ".avi", ".m4v", ".ts", ".mp3", ".m4a", ".aac", ".wav", ".flac", ".ogg", ".opus"}


# ------------------------------------------------------------------ helpers
def _desktop() -> Path:
    if os.name == "nt":
        import ctypes
        buf = ctypes.create_unicode_buffer(260)
        ctypes.windll.shell32.SHGetFolderPathW(0, 0x10, 0, 0, buf)  # real Desktop (follows OneDrive)
        if buf.value:
            return Path(buf.value)
    return Path.home() / "Desktop"


def app_location() -> dict:
    """Where the KOSIF desktop app lives: packaged exe first, then the source tree."""
    for d in [os.environ.get("KOSIF_HOME"), _desktop() / "KOSIF", Path.home() / "Desktop" / "KOSIF"]:
        if d and (Path(d) / "KOSIF.exe").is_file():
            return {"kind": "exe", "dir": str(d), "start": [str(Path(d) / "KOSIF.exe"), "--background"]}
    if (SOURCE_TREE / "kosif_app.py").is_file():
        pyw = Path(sys.executable).with_name("pythonw.exe")
        py = str(pyw if pyw.exists() else sys.executable)
        return {"kind": "source", "dir": str(SOURCE_TREE), "start": [py, str(SOURCE_TREE / "kosif_app.py"), "--background"]}
    return {"kind": "missing", "dir": "", "start": []}


def human(n) -> str:
    n = float(n or 0)
    for u in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or u == "TB":
            return f"{n:.1f} {u}" if u != "B" else f"{int(n)} B"
        n /= 1024


def sha256(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def ffprobe(path) -> dict:
    exe = shutil.which("ffprobe")
    if not exe:
        return {}
    try:
        r = subprocess.run([exe, "-v", "error", "-show_entries", "format=duration:stream=codec_type,width,height",
                            "-of", "json", str(path)], capture_output=True, text=True, timeout=60)
        j = json.loads(r.stdout or "{}")
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return {}
    v = next((s for s in j.get("streams", []) if s.get("codec_type") == "video"), {})
    return {"duration": round(float(j.get("format", {}).get("duration", 0) or 0), 3),
            "width": v.get("width"), "height": v.get("height"),
            "audio": any(s.get("codec_type") == "audio" for s in j.get("streams", []))}


# ------------------------------------------------------------------ headless fetch (in-process core)
def _core():
    os.environ.setdefault("KOSIF_DATA_DIR", str(DRAGON_DATA))
    from . import core
    return core


def probe(url: str, referer: str = "", timeout: int = 20) -> dict:
    """Ask the server about a link without downloading it: final URL, file name, size, resumable, type."""
    core = _core()
    import httpx
    h = {"User-Agent": core.DEFAULT_UA, "Range": "bytes=0-0", "Accept-Encoding": "identity"}
    if referer:
        h["Referer"] = referer
    with httpx.Client(follow_redirects=True, timeout=timeout) as c, c.stream("GET", url, headers=h) as r:
        cr = r.headers.get("content-range", "")
        size = int(cr.split("/")[-1]) if r.status_code == 206 and "/" in cr and not cr.endswith("*") else \
            int(r.headers.get("content-length", -1) or -1) if r.status_code == 200 else -1
        return {"url": url, "final_url": str(r.url), "status": r.status_code,
                "filename": core.filename_from_headers(r.headers, str(r.url)), "size": size,
                "resumable": r.status_code == 206, "content_type": r.headers.get("content-type", ""),
                "page_video": core.Manager.looks_like_page_video(url)}


def fetch(urls, out=".", connections=8, kind="auto", filename="", quality="best", referer="", cookies="",
          speed_limit_kb=0, proxy="", timeout=30, retries=10, verify=True, log=print) -> list[dict]:
    """Download one or more links into `out` and wait. Returns one measured record per link."""
    urls = [urls] if isinstance(urls, str) else list(urls)
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    core = _core()
    m = core.Manager()
    m.settings.update({"download_dir": str(out), "use_categories": False, "connections": int(connections),
                       "max_active": max(1, min(len(urls), 4)), "speed_limit_kb": int(speed_limit_kb),
                       "proxy": proxy, "timeout": int(timeout), "retries": int(retries)})
    m.limiter.set(int(speed_limit_kb))
    fmt = QUALITY.get(str(quality), str(quality))
    with m.lock:
        leftovers = {(d.source_url or d.url, d.directory): d for d in m.downloads.values() if d.status != "done"}
        for d in leftovers.values():
            d.status = "paused"            # interrupted earlier runs wait unless asked for again
    jobs = []
    for u in urls:
        old = leftovers.get((u.strip(), str(out)))
        if old:                            # same link into the same folder -> resume where it stopped
            old.status, old.error, old.start_at = "queued", "", 0
            jobs.append(old)
            log(f"[kosif] resuming {old.filename or u} from {human(old.downloaded)}")
        else:
            jobs.append(m.add(u, kind=kind, filename=filename if len(urls) == 1 else "", directory=str(out),
                              referer=referer, cookies=cookies, connections=int(connections), video_format=fmt))
    last = 0.0
    try:
        while any(d.status not in ("done", "error") for d in jobs):
            time.sleep(0.25)
            if time.time() - last >= 1.0:
                last = time.time()
                for d in jobs:
                    if d.status in ("downloading", "probing"):
                        pct = f"{100 * d.downloaded / d.size:5.1f}%" if d.size > 0 else "  ?  "
                        log(f"[kosif] {pct} {human(d.downloaded):>10} {human(d.speed):>10}/s "
                            f"x{d.active_conns:<2} {d.filename or d.url}")
    except KeyboardInterrupt:
        m.shutdown()
        raise
    results = []
    for d in jobs:
        rec = {"url": d.url, "kind": d.kind, "status": d.status, "error": d.error, "path": d.path,
               "size": d.size, "resumable": d.resumable, "connections": d.connections}
        if d.status == "done" and d.path and os.path.isfile(d.path):
            rec["size"] = os.path.getsize(d.path)
            if verify:
                rec["sha256"] = sha256(d.path)
                if Path(d.path).suffix.lower() in MEDIA_EXT:
                    rec["media"] = ffprobe(d.path)
        results.append(rec)
        m.downloads.pop(d.id, None)        # keep the Dragon's own KOSIF state small
    m.save()
    return results


# ------------------------------------------------------------------ desktop app control
def _token() -> str:
    return json.loads((APP_DATA / "settings.json").read_text(encoding="utf-8"))["token"]


def app_running() -> bool:
    try:
        with urllib.request.urlopen(BASE + "/api/ping", timeout=1.5) as r:
            return json.load(r).get("app") == "KOSIF"
    except OSError:
        return False


def app_start(wait: float = 20) -> bool:
    if app_running():
        return True
    loc = app_location()
    if not loc["start"]:
        raise SystemExit("KOSIF app not found (Desktop\\KOSIF\\KOSIF.exe or the source tree); set KOSIF_HOME")
    flags = 0x00000008 | 0x00000200 if os.name == "nt" else 0
    subprocess.Popen(loc["start"], creationflags=flags, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, close_fds=True)
    end = time.time() + wait
    while time.time() < end:
        time.sleep(0.3)
        if app_running():
            return True
    return False


def app_call(path: str, body: dict | None = None, start: bool = True):
    if start and not app_start():
        raise SystemExit("KOSIF app did not start")
    req = urllib.request.Request(BASE + path, data=None if body is None else json.dumps(body).encode(),
                                 headers={"X-KOSIF-Token": _token(), "Content-Type": "application/json"},
                                 method="GET" if body is None else "POST")
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.load(r)


def send(urls, kind="auto", quality="best", referer="", show=False) -> dict:
    """Queue links in the KOSIF desktop app (they appear in its window, with its categories and queue)."""
    urls = [urls] if isinstance(urls, str) else list(urls)
    return app_call("/api/add", {"urls": urls, "kind": kind, "video_format": QUALITY.get(str(quality), str(quality)),
                                 "referer": referer, "show": show})


def app_list() -> list[dict]:
    keep = ("id", "status", "kind", "filename", "size", "downloaded", "speed", "active_conns", "path", "error", "url")
    return [{k: d.get(k) for k in keep} for d in app_call("/api/list")["downloads"]]


def app_action(action: str, item_id: str = "") -> dict:
    return app_call("/api/action", {"id": item_id, "action": action} if item_id else {"action": action})


def app_open() -> dict:
    return app_call("/api/show", {})


def app_quit() -> dict:
    return app_call("/api/quit", {}, start=False) if app_running() else {"ok": True, "note": "not running"}


# ------------------------------------------------------------------ doctor
def doctor() -> dict:
    loc = app_location()
    host = {}
    if os.name == "nt":
        import winreg
        for br, key in (("chrome", r"Software\Google\Chrome\NativeMessagingHosts\com.kosif.dm"),
                        ("edge", r"Software\Microsoft\Edge\NativeMessagingHosts\com.kosif.dm")):
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key) as h:
                    host[br] = winreg.QueryValue(h, None)
            except OSError:
                host[br] = None
    mods = {}
    for mod in ("httpx", "yt_dlp"):
        try:
            __import__(mod)
            mods[mod] = True
        except ImportError:
            mods[mod] = False
    return {"app": loc, "app_running": app_running(), "native_host": host,
            "ffmpeg": shutil.which("ffmpeg"), "ffprobe": shutil.which("ffprobe"), "python_modules": mods,
            "dragon_state": str(DRAGON_DATA), "core_version": _core().VERSION,
            "ok": mods["httpx"] and loc["kind"] != "missing"}
