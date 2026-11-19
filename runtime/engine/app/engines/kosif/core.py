"""KOSIF download engine (vendored into the Black Dragon from KOSIF 1.0.0 kosif/engine.py).

Multi-connection HTTP(S) downloader with dynamic segmentation:
the file is split into N ranges; whenever a connection finishes its range
it steals half of the largest remaining range, so all connections stay busy
until the very end. State is persisted so downloads resume after restart.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import threading
import time
import urllib.parse
import uuid
from dataclasses import dataclass, field, asdict

import httpx

APP_NAME = "KOSIF"
VERSION = "1.0.0"
DATA_DIR = os.environ.get("KOSIF_DATA_DIR") or os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), APP_NAME)
STATE_FILE = os.path.join(DATA_DIR, "downloads.json")
SETTINGS_FILE = os.path.join(DATA_DIR, "settings.json")
PART_EXT = ".kosifpart"
CHUNK = 64 * 1024
MIN_SPLIT = 512 * 1024  # don't steal ranges smaller than this

CATEGORIES = {
    "Video": "mp4 mkv avi mov wmv flv webm m4v mpg mpeg 3gp ts m3u8",
    "Music": "mp3 m4a aac wav flac ogg opus wma",
    "Compressed": "zip rar 7z tar gz bz2 xz iso cab zst",
    "Documents": "pdf doc docx xls xlsx ppt pptx txt epub csv rtf odt",
    "Programs": "exe msi apk msix appx dmg deb rpm bat",
    "Images": "jpg jpeg png gif webp bmp svg tif tiff heic psd raw",
}
EXT_TO_CAT = {e: c for c, exts in CATEGORIES.items() for e in exts.split()}

DEFAULT_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")

DEFAULT_SETTINGS = {
    "download_dir": os.path.join(os.path.expanduser("~"), "Downloads", APP_NAME),
    "connections": 8,
    "max_active": 3,
    "speed_limit_kb": 0,          # 0 = unlimited (global)
    "retries": 10,
    "timeout": 30,
    "proxy": "",                  # e.g. http://127.0.0.1:8080 or socks5://127.0.0.1:1080
    "use_categories": True,
    "capture_exts": "zip rar 7z exe msi iso apk mp4 mkv avi mov mp3 m4a flac pdf "
                    "docx xlsx pptx tar gz bz2 xz dmg deb rpm webm wav",
    "min_capture_kb": 0,
    "auto_start": True,
    "token": "",
}


FROZEN = getattr(sys, "frozen", False)
APP_DIR = os.path.dirname(sys.executable) if FROZEN else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def ytdlp_cmd() -> list:
    """Source: python -m yt_dlp.  Packaged: kosif-cli.exe --yt-dlp (console exe, bundles yt-dlp)."""
    if FROZEN:
        return [os.path.join(APP_DIR, "kosif-cli.exe"), "--yt-dlp"]
    return [sys.executable, "-m", "yt_dlp"]


def human(n: float) -> str:
    for u in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024 or u == "TB":
            return f"{n:.1f} {u}" if u != "B" else f"{int(n)} B"
        n /= 1024
    return str(n)


def safe_name(name: str) -> str:
    name = urllib.parse.unquote(name).strip().strip(".")
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name)
    return name[:200] or "download"


def filename_from_headers(headers, url: str) -> str:
    cd = headers.get("content-disposition", "")
    m = re.search(r"filename\*\s*=\s*([^']*)'[^']*'([^;]+)", cd, re.I)
    if m:
        try:
            return safe_name(urllib.parse.unquote(m.group(2).strip('" '), encoding=m.group(1) or "utf-8"))
        except LookupError:
            return safe_name(m.group(2).strip('" '))
    m = re.search(r'filename\s*=\s*"([^"]+)"', cd, re.I) or re.search(r"filename\s*=\s*([^;]+)", cd, re.I)
    if m:
        raw = m.group(1).strip()
        try:  # servers often send UTF-8 bytes decoded as latin-1
            raw = raw.encode("latin-1").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            pass
        return safe_name(raw)
    path = urllib.parse.urlparse(url).path
    base = os.path.basename(path.rstrip("/"))
    if base:
        return safe_name(base)
    ctype = headers.get("content-type", "").split(";")[0].strip()
    import mimetypes
    ext = mimetypes.guess_extension(ctype) or ".bin"
    return "download" + ext


def category_of(name: str) -> str:
    ext = os.path.splitext(name)[1].lower().lstrip(".")
    return EXT_TO_CAT.get(ext, "General")


class FatalHTTP(Exception):
    """Non-retryable server answer (expired link, forbidden, missing)."""


class RateLimiter:
    """Global token bucket shared by every connection."""

    def __init__(self):
        self.lock = threading.Lock()
        self.rate = 0
        self.tokens = 0.0
        self.t = time.monotonic()

    def set(self, kb: int):
        with self.lock:
            self.rate = max(0, int(kb)) * 1024
            self.tokens = min(self.tokens, self.rate)

    def take(self, n: int):
        while True:
            with self.lock:
                if not self.rate:
                    return
                now = time.monotonic()
                self.tokens = min(self.rate, self.tokens + (now - self.t) * self.rate)
                self.t = now
                if self.tokens >= n or self.tokens >= self.rate:
                    self.tokens -= n
                    return
                wait = (n - self.tokens) / self.rate
            time.sleep(min(wait, 0.25))


@dataclass
class Segment:
    start: int
    end: int      # inclusive
    pos: int      # next byte to fetch

    @property
    def remaining(self) -> int:
        return max(0, self.end - self.pos + 1)


@dataclass
class Download:
    id: str
    url: str
    kind: str = "http"            # http | video (yt-dlp)
    filename: str = ""
    directory: str = ""
    size: int = -1
    downloaded: int = 0
    status: str = "queued"        # queued | probing | downloading | paused | done | error
    resumable: bool = False
    connections: int = 8
    referer: str = ""
    cookies: str = ""
    user_agent: str = ""
    headers: dict = field(default_factory=dict)
    segments: list = field(default_factory=list)
    created: float = field(default_factory=time.time)
    finished: float = 0
    start_at: float = 0           # scheduler: epoch seconds, 0 = now
    error: str = ""
    category: str = "General"
    video_format: str = ""
    source_url: str = ""          # the link as given (url may change after redirects)
    # runtime only
    speed: float = 0
    active_conns: int = 0

    def to_json(self):
        d = asdict(self)
        d.pop("speed"), d.pop("active_conns")
        return d

    def view(self):
        d = self.to_json()
        d.pop("cookies"), d.pop("headers"), d.pop("segments")
        d["speed"] = self.speed
        d["active_conns"] = self.active_conns
        d["eta"] = ((self.size - self.downloaded) / self.speed) if (self.speed > 0 and self.size > 0) else -1
        d["seg_map"] = [[s["start"], s["end"], s["pos"]] if isinstance(s, dict) else [s.start, s.end, s.pos]
                        for s in self.segments][:64]
        d["path"] = self.path
        return d

    @property
    def path(self):
        return os.path.join(self.directory, self.filename) if self.filename else ""


class Job:
    """Runtime worker for one download."""

    def __init__(self, mgr: "Manager", d: Download):
        self.mgr, self.d = mgr, d
        self.stop = threading.Event()
        self.lock = threading.Lock()
        self.segs: list[Segment] = []
        self.busy: set[int] = set()
        self.thread = threading.Thread(target=self.run, daemon=True, name=f"job-{d.id}")
        self.proc: subprocess.Popen | None = None
        self._last_bytes = 0

    # ------------------------------------------------------------ helpers
    def client(self) -> httpx.Client:
        s = self.mgr.settings
        h = {"User-Agent": self.d.user_agent or DEFAULT_UA, "Accept": "*/*",
             "Accept-Encoding": "identity"}
        if self.d.referer:
            h["Referer"] = self.d.referer
        if self.d.cookies:
            h["Cookie"] = self.d.cookies
        h.update(self.d.headers or {})
        return httpx.Client(headers=h, follow_redirects=True, timeout=httpx.Timeout(s["timeout"]),
                            proxy=s["proxy"] or None, verify=True, http2=False)

    def unique_path(self, directory: str, name: str) -> str:
        base, ext = os.path.splitext(name)
        cand, i = name, 1
        while (os.path.exists(os.path.join(directory, cand)) or
               os.path.exists(os.path.join(directory, cand + PART_EXT)) or
               self.mgr.name_taken(directory, cand, self.d.id)):
            cand = f"{base} ({i}){ext}"
            i += 1
        return cand

    def fail(self, msg: str):
        self.d.status, self.d.error = "error", msg[:400]
        self.d.speed = 0

    # ------------------------------------------------------------ main
    def run(self):
        d = self.d
        d.error = ""
        try:
            if d.kind == "video":
                self.run_video()
            else:
                self.run_http()
        except Exception as e:  # noqa: BLE001
            if not self.stop.is_set():
                self.fail(f"{type(e).__name__}: {e}")
        finally:
            d.active_conns = 0
            d.speed = 0
            if self.stop.is_set() and d.status in ("downloading", "probing"):
                d.status = "paused"
            self.mgr.job_finished(self)

    def probe(self, c: httpx.Client):
        d = self.d
        d.status = "probing"
        with c.stream("GET", d.url, headers={"Range": "bytes=0-"}) as r:
            if r.status_code >= 400:
                raise RuntimeError(f"HTTP {r.status_code}")
            d.url = str(r.url)  # follow redirects once, reuse final URL
            total = -1
            cr = r.headers.get("content-range", "")
            if r.status_code == 206 and "/" in cr and not cr.endswith("*"):
                total = int(cr.split("/")[-1])
                d.resumable = True
            elif r.headers.get("content-length"):
                total = int(r.headers["content-length"])
                d.resumable = r.headers.get("accept-ranges", "").lower() == "bytes"
            if r.headers.get("content-encoding", "identity") not in ("identity", ""):
                d.resumable = False
            d.size = total
            if not d.filename:
                d.filename = filename_from_headers(r.headers, d.url)
        if d.filename and not d.directory:
            d.category = category_of(d.filename)
            root = self.mgr.settings["download_dir"]
            d.directory = os.path.join(root, d.category) if self.mgr.settings["use_categories"] else root
        os.makedirs(d.directory, exist_ok=True)
        d.filename = self.unique_path(d.directory, safe_name(d.filename))
        d.category = category_of(d.filename)

    def run_http(self):
        d = self.d
        c = self.client()
        part = None
        try:
            fresh = not d.segments or not d.filename or not os.path.exists(d.path + PART_EXT)
            if fresh:
                d.segments, d.downloaded = [], 0
                self.probe(c)
            part = d.path + PART_EXT
            if self.stop.is_set():
                return
            d.status = "downloading"
            if d.resumable and d.size > 0:
                self.run_segmented(c, part, fresh)
            else:
                self.run_single(c, part)
            if self.stop.is_set() or d.status == "error":
                return
            if d.size > 0 and os.path.getsize(part) != d.size:
                raise RuntimeError("size mismatch after download")
            final = d.path
            if os.path.exists(final):
                d.filename = self.unique_path(d.directory, d.filename)
                final = d.path
            os.replace(part, final)
            d.size = d.downloaded = os.path.getsize(final)
            d.segments = []
            d.status, d.finished = "done", time.time()
        finally:
            c.close()

    # ---------------------------------------------------- segmented mode
    def run_segmented(self, c: httpx.Client, part: str, fresh: bool):
        d = self.d
        if fresh or not d.segments:
            with open(part, "wb") as f:
                f.truncate(d.size)  # pre-allocate
            n = max(1, min(int(d.connections), 32, d.size // MIN_SPLIT or 1))
            step = d.size // n
            self.segs = [Segment(i * step, (d.size - 1) if i == n - 1 else (i + 1) * step - 1, i * step)
                         for i in range(n)]
        else:
            self.segs = [Segment(**s) for s in d.segments]
        d.segments = self.segs
        d.downloaded = d.size - sum(s.remaining for s in self.segs)
        workers = []
        initial = [s for s in self.segs if s.remaining > 0]
        for s in initial:
            self.busy.add(id(s))
            t = threading.Thread(target=self.conn_worker, args=(part, s), daemon=True)
            workers.append(t)
            t.start()
        # extra connections steal work if we resumed with fewer open ranges
        for _ in range(max(0, int(d.connections) - len(initial))):
            s = self.steal()
            if not s:
                break
            t = threading.Thread(target=self.conn_worker, args=(part, s), daemon=True)
            workers.append(t)
            t.start()
        for t in workers:
            t.join()
        if not self.stop.is_set() and any(s.remaining for s in self.segs) and d.status != "error":
            self.fail("connections ended before all bytes arrived")
        interrupted = self.stop.is_set() or d.status == "error"
        d.segments = [asdict(s) for s in self.segs] if interrupted else []

    def steal(self) -> Segment | None:
        """Dynamic segmentation: adopt an orphaned range first, else split the
        biggest busy range in half so every connection stays useful."""
        with self.lock:
            for s in self.segs:
                if s.remaining > 0 and id(s) not in self.busy:
                    self.busy.add(id(s))
                    return s
            big = max(self.segs, key=lambda s: s.remaining, default=None)
            if not big or big.remaining < 2 * MIN_SPLIT:
                return None
            mid = big.pos + big.remaining // 2
            new = Segment(mid, big.end, mid)
            big.end = mid - 1
            self.segs.append(new)
            self.busy.add(id(new))
            return new

    def release(self, seg: Segment | None):
        if seg is not None:
            with self.lock:
                self.busy.discard(id(seg))

    def conn_worker(self, part: str, seg: Segment | None):
        """One connection. A connection that keeps failing while others work
        (server connection limits) gives its range back and quits; only the
        last connection alive retries up to the full retry budget."""
        d = self.d
        retries = self.mgr.settings["retries"]
        with self.lock:
            d.active_conns += 1
        try:
            with open(part, "r+b") as f, self.client() as c:
                while seg and not self.stop.is_set():
                    fails = 0
                    while seg.remaining > 0 and not self.stop.is_set():
                        try:
                            got = self.fetch_range(c, f, seg)
                            fails = 0 if got else fails + 1
                            if not got:
                                raise RuntimeError("no data")
                        except FatalHTTP as e:
                            with self.lock:
                                if d.status != "error":
                                    self.fail(str(e))
                            self.stop.set()
                            return
                        except Exception as e:  # noqa: BLE001
                            fails += 1
                            with self.lock:
                                others = d.active_conns > 1
                            if others and fails >= 3:
                                return          # hand the range back to the healthy connections
                            if fails > retries:
                                with self.lock:
                                    if d.status != "error":
                                        self.fail(f"connection failed: {e}")
                                self.stop.set()
                                return
                            self.stop.wait(min(30, 2 ** fails))
                    self.release(seg)
                    seg = None if self.stop.is_set() else self.steal()
        finally:
            self.release(seg)
            with self.lock:
                d.active_conns -= 1
            # last one out: pick up anything orphaned before giving up
            if not self.stop.is_set() and d.active_conns == 0 and any(s.remaining for s in self.segs):
                nxt = self.steal()
                if nxt:
                    self.conn_worker(part, nxt)

    def fetch_range(self, c: httpx.Client, f, seg: Segment):
        with c.stream("GET", self.d.url, headers={"Range": f"bytes={seg.pos}-{seg.end}"}) as r:
            if r.status_code in (401, 403, 404, 410):
                raise FatalHTTP(f"HTTP {r.status_code} (link expired or access denied)")
            if r.status_code != 206:
                raise RuntimeError(f"server answered {r.status_code} to a range request")
            got = 0
            for chunk in r.iter_bytes(CHUNK):
                if self.stop.is_set():
                    return got
                self.mgr.limiter.take(len(chunk))
                with self.lock:
                    room = seg.end - seg.pos + 1      # end may shrink when stolen
                    if room <= 0:
                        return got or 1
                    chunk = chunk[:room]
                    f.seek(seg.pos)
                    f.write(chunk)
                    seg.pos += len(chunk)
                    got += len(chunk)
                    self.d.downloaded += len(chunk)
                    if seg.remaining <= 0:
                        return got
            return got

    # ------------------------------------------------------- single mode
    def run_single(self, c: httpx.Client, part: str):
        d = self.d
        d.active_conns = 1
        d.downloaded = 0
        with open(part, "wb") as f, c.stream("GET", d.url) as r:
            if r.status_code >= 400:
                raise RuntimeError(f"HTTP {r.status_code}")
            for chunk in r.iter_bytes(CHUNK):
                if self.stop.is_set():
                    return
                self.mgr.limiter.take(len(chunk))
                f.write(chunk)
                d.downloaded += len(chunk)
        if d.size <= 0:
            d.size = d.downloaded

    # -------------------------------------------------------- video mode
    def run_video(self):
        """Page/stream URLs (YouTube, HLS, DASH...) through yt-dlp + ffmpeg."""
        d = self.d
        d.status = "downloading"
        root = self.mgr.settings["download_dir"]
        d.category = "Video"
        d.directory = d.directory or (os.path.join(root, "Video") if self.mgr.settings["use_categories"] else root)
        os.makedirs(d.directory, exist_ok=True)
        fmt = d.video_format or "bv*[height<=2160]+ba/b"
        cmd = ytdlp_cmd() + ["--newline", "--no-playlist", "--no-mtime",
               "-f", fmt, "--merge-output-format", "mp4", "-N", str(min(16, max(1, int(d.connections)))),
               "-P", d.directory, "-o", "%(title).150B [%(id)s].%(ext)s",
               "--print", "after_move:KOSIF_FILE:%(filepath)s",
               "--progress-template", "KOSIF_PROG:%(progress.downloaded_bytes)s:%(progress.total_bytes)s:"
               "%(progress.total_bytes_estimate)s:%(progress.speed)s"]
        if d.referer:
            cmd += ["--referer", d.referer]
        if d.user_agent:
            cmd += ["--user-agent", d.user_agent]
        if d.cookies:
            cmd += ["--add-headers", f"Cookie:{d.cookies}"]
        if self.mgr.settings["proxy"]:
            cmd += ["--proxy", self.mgr.settings["proxy"]]
        if self.mgr.settings["speed_limit_kb"]:
            cmd += ["-r", f"{self.mgr.settings['speed_limit_kb']}K"]
        cmd.append(d.url)
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                     encoding="utf-8", errors="replace", creationflags=flags)
        last_err, base = "", 0
        prev_total = None
        for line in self.proc.stdout:
            line = line.strip()
            if line.startswith("KOSIF_PROG:"):
                p = line.split(":")[1:]
                num = lambda x: float(x) if x not in ("NA", "None", "") else 0.0  # noqa: E731
                got, tot, est, spd = (num(x) for x in p[:4])
                tot = tot or est
                if prev_total is not None and tot and tot != prev_total and got < 1024 * 1024:
                    base += int(prev_total)  # second stream (audio) started
                prev_total = tot or prev_total
                d.downloaded = int(base + got)
                d.size = int(base + tot) if tot else -1
                d.speed = spd
                d.active_conns = 1
            elif line.startswith("KOSIF_FILE:"):
                path = line[len("KOSIF_FILE:"):]
                d.directory, d.filename = os.path.split(path)
            elif "ERROR" in line:
                last_err = line
            elif line.startswith("[") and not d.filename and "Destination:" in line:
                d.filename = os.path.basename(line.split("Destination:", 1)[1].strip())
            if self.stop.is_set():
                break
        if self.stop.is_set():
            self.proc.kill()
            return
        rc = self.proc.wait()
        if rc != 0:
            raise RuntimeError(last_err or f"yt-dlp exit {rc}")
        if d.path and os.path.exists(d.path):
            d.size = d.downloaded = os.path.getsize(d.path)
        d.status, d.finished = "done", time.time()

    def cancel(self):
        self.stop.set()
        if self.proc and self.proc.poll() is None:
            try:
                self.proc.kill()
            except OSError:
                pass


class Manager:
    def __init__(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        self.lock = threading.RLock()
        self.save_lock = threading.Lock()
        self.settings = dict(DEFAULT_SETTINGS)
        self.downloads: dict[str, Download] = {}
        self.jobs: dict[str, Job] = {}
        self.limiter = RateLimiter()
        self._speed_t = time.monotonic()
        self._prev: dict[str, int] = {}
        self.load()
        self.limiter.set(self.settings["speed_limit_kb"])
        threading.Thread(target=self.loop, daemon=True, name="scheduler").start()

    # ------------------------------------------------------- persistence
    def load(self):
        try:
            with open(SETTINGS_FILE, encoding="utf-8") as f:
                self.settings.update(json.load(f))
        except (OSError, ValueError):
            pass
        if not self.settings.get("token"):
            self.settings["token"] = uuid.uuid4().hex + uuid.uuid4().hex
            self.save_settings()
        try:
            with open(STATE_FILE, encoding="utf-8") as f:
                for row in json.load(f):
                    known = Download.__dataclass_fields__
                    d = Download(**{k: v for k, v in row.items() if k in known})
                    if d.status in ("downloading", "probing"):
                        d.status = "queued"   # resume after restart
                    self.downloads[d.id] = d
        except (OSError, ValueError, TypeError):
            pass

    def save_settings(self):
        tmp = SETTINGS_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.settings, f, ensure_ascii=False, indent=2)
        os.replace(tmp, SETTINGS_FILE)

    def save(self):
        with self.lock:
            rows = []
            for d in self.downloads.values():
                j = self.jobs.get(d.id)
                row = d.to_json()
                if j and j.segs:
                    with j.lock:
                        row["segments"] = [asdict(s) for s in j.segs]
                elif d.segments and not isinstance(d.segments[0], dict):
                    row["segments"] = [asdict(s) for s in d.segments]
                rows.append(row)
        with self.save_lock:
            tmp = STATE_FILE + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(rows, f, ensure_ascii=False)
            for attempt in range(10):      # AV/indexers may briefly lock the target on Windows
                try:
                    os.replace(tmp, STATE_FILE)
                    break
                except PermissionError:
                    time.sleep(0.05 * (attempt + 1))

    # ----------------------------------------------------------- actions
    def add(self, url: str, *, kind="auto", filename="", directory="", referer="", cookies="",
            user_agent="", headers=None, start_at=0, connections=None, start=True, video_format="") -> Download:
        url = url.strip()
        if not re.match(r"^(https?)://", url, re.I):
            raise ValueError("only http/https links are supported")
        if kind == "auto":
            kind = "video" if self.looks_like_page_video(url) else "http"
        d = Download(id=uuid.uuid4().hex[:12], url=url, source_url=url, kind=kind, filename=safe_name(filename) if filename else "",
                     directory=directory, referer=referer, cookies=cookies, user_agent=user_agent,
                     headers=headers or {}, start_at=float(start_at or 0), video_format=video_format,
                     connections=int(connections or self.settings["connections"]),
                     status="queued" if start else "paused")
        if d.filename:
            d.category = category_of(d.filename)
        with self.lock:
            self.downloads[d.id] = d
        self.save()
        return d

    @staticmethod
    def looks_like_page_video(url: str) -> bool:
        host = urllib.parse.urlparse(url).netloc.lower()
        path = urllib.parse.urlparse(url).path.lower()
        sites = ("youtube.com", "youtu.be", "tiktok.com", "instagram.com", "facebook.com", "fb.watch",
                 "twitter.com", "x.com", "vimeo.com", "dailymotion.com", "twitch.tv", "reddit.com",
                 "soundcloud.com", "bilibili.com")
        return any(host == s or host.endswith("." + s) for s in sites) or path.endswith((".m3u8", ".mpd"))

    def name_taken(self, directory, name, own_id):
        with self.lock:
            return any(o.id != own_id and o.directory == directory and o.filename == name
                       and o.status != "done" for o in self.downloads.values())

    def action(self, did: str, act: str):
        with self.lock:
            d = self.downloads.get(did)
            if not d:
                raise KeyError(did)
            job = self.jobs.get(did)
        if act == "pause":
            if job:
                job.cancel()
            elif d.status == "queued":
                d.status = "paused"
        elif act in ("resume", "start"):
            if d.status in ("paused", "error"):
                d.status, d.start_at = "queued", 0
        elif act == "restart":
            if job:
                job.cancel()
                job.thread.join(5)
            self._remove_part(d)
            d.segments, d.downloaded, d.status, d.error, d.start_at = [], 0, "queued", "", 0
        elif act in ("remove", "delete_file"):
            if job:
                job.cancel()
                job.thread.join(5)
            self._remove_part(d)
            if act == "delete_file" and d.status == "done" and d.path and os.path.isfile(d.path):
                os.remove(d.path)
            with self.lock:
                self.downloads.pop(did, None)
        elif act == "open":
            if d.status == "done" and os.path.isfile(d.path):
                os.startfile(d.path)  # type: ignore[attr-defined]
        elif act == "folder":
            target = d.path if d.status == "done" and os.path.exists(d.path) else (d.path + PART_EXT)
            if os.path.exists(target):
                subprocess.Popen(["explorer", "/select,", os.path.normpath(target)])
            elif d.directory and os.path.isdir(d.directory):
                os.startfile(d.directory)  # type: ignore[attr-defined]
        else:
            raise ValueError(act)
        self.save()

    @staticmethod
    def _remove_part(d: Download):
        if d.path and os.path.exists(d.path + PART_EXT):
            try:
                os.remove(d.path + PART_EXT)
            except OSError:
                pass

    def bulk(self, act: str):
        for d in list(self.downloads.values()):
            if act == "pause_all" and d.status in ("queued", "downloading", "probing"):
                self.action(d.id, "pause")
            elif act == "resume_all" and d.status in ("paused", "error"):
                self.action(d.id, "resume")
            elif act == "clear_done" and d.status == "done":
                self.action(d.id, "remove")

    def update_settings(self, new: dict):
        allowed = set(DEFAULT_SETTINGS) - {"token"}
        for k, v in new.items():
            if k in allowed:
                self.settings[k] = type(DEFAULT_SETTINGS[k])(v)
        self.settings["connections"] = max(1, min(32, self.settings["connections"]))
        self.settings["max_active"] = max(1, min(20, self.settings["max_active"]))
        self.limiter.set(self.settings["speed_limit_kb"])
        self.save_settings()

    # ------------------------------------------------------------ loop
    def job_finished(self, job: Job):
        with self.lock:
            self.jobs.pop(job.d.id, None)
        self.save()

    def loop(self):
        last_save = time.monotonic()
        while True:
            time.sleep(0.5)
            now = time.time()
            with self.lock:
                active = len(self.jobs)
                waiting = sorted((d for d in self.downloads.values()
                                  if d.status == "queued" and d.id not in self.jobs and d.start_at <= now),
                                 key=lambda d: d.created)
                for d in waiting[: max(0, self.settings["max_active"] - active)]:
                    j = Job(self, d)
                    self.jobs[d.id] = j
                    d.status = "probing" if d.kind == "http" else "downloading"
                    j.thread.start()
            mono = time.monotonic()
            dt = mono - self._speed_t
            if dt >= 1:
                self._speed_t = mono
                for d in list(self.downloads.values()):
                    if d.kind == "http":
                        prev = self._prev.get(d.id, d.downloaded)
                        inst = max(0, d.downloaded - prev) / dt
                        d.speed = 0 if d.id not in self.jobs else (0.6 * d.speed + 0.4 * inst)
                    self._prev[d.id] = d.downloaded
            if mono - last_save > 3 and self.jobs:
                last_save = mono
                self.save()

    def snapshot(self):
        with self.lock:
            items = [d.view() for d in sorted(self.downloads.values(), key=lambda x: -x.created)]
        return {"app": APP_NAME, "version": VERSION, "downloads": items,
                "total_speed": sum(i["speed"] for i in items),
                "settings": {k: v for k, v in self.settings.items() if k != "token"}}

    def shutdown(self):
        running = list(self.jobs.values())
        for j in running:
            j.cancel()
        for j in running:
            j.thread.join(3)
        for j in running:          # app exit is not a user pause: resume on next launch
            if j.d.status == "paused":
                j.d.status = "queued"
        self.save()
