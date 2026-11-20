#!/usr/bin/env python3
"""video-grabber: download (almost) any video from any site with one command, best quality.

Strategy per URL (stops at the first success):
  0. direct media file (server answers with a media Content-Type)  -> aria2c, 16 connections, resumable
  1. yt-dlp, best format (bv*+ba merged to mp4 when compatible, else mkv), aria2c for plain http files,
     concurrent fragments for HLS/DASH, retries
  2. on 403 / 429 / geo / network errors -> retry through the proxy pool (proxy_pool.py)
  3. unsupported site / nothing found     -> GhostBrowser.sniff (ghost_browser.py) finds the stream,
     then yt-dlp generic with Referer/UA/cookies, or ffmpeg for HLS/DASH, or aria2c for mp4
Every file is verified with ffprobe and logged to <out>/sources.txt. The last stdout line is JSON.

Only download content you have the right to. DRM is never circumvented and CAPTCHAs are never solved.

Examples:
  python grab.py URL
  python grab.py URL --quality 1080 --compat -o D:/clips
  python grab.py URL --audio-only mp3
  python grab.py URL --section 00:01:00-00:02:30 --subs ar,en
  python grab.py --batch urls.txt --json
  python grab.py URL --info --json
  python grab.py --update
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

DEFAULT_OUT = Path.home() / "Downloads" / "video-grabber"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36")
MEDIA_EXT = re.compile(r"\.(mp4|m4v|mov|webm|mkv|avi|flv|ts|mp3|m4a|aac|wav|flac|ogg|opus)(\?|#|$)", re.I)
STREAM_EXT = re.compile(r"\.(m3u8|mpd)(\?|#|$)", re.I)

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

QUIET = False  # set by --json: human chatter goes to stderr only


def log(*a):
    print(*a, file=sys.stderr, flush=True)


# --------------------------------------------------------------------------- tools

def find_exe(name: str) -> str | None:
    p = shutil.which(name)
    if p:
        return p
    root = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Packages"
    if root.exists():
        hits = list(root.glob(f"**/{name}.exe"))
        if hits:
            return str(hits[0])
    return None


def ytdlp_cmd() -> list[str]:
    try:
        import yt_dlp  # noqa: F401
        return [sys.executable, "-m", "yt_dlp"]
    except Exception:
        exe = find_exe("yt-dlp")
        if not exe:
            raise SystemExit("yt-dlp not found: python -m pip install -U yt-dlp")
        return [exe]


def child_env() -> dict:
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    return env


def run_stream(cmd: list[str], tail: int = 300) -> tuple[int, str]:
    """Run a command, echo its output to stderr live, return (code, last lines)."""
    lines: list[str] = []
    try:
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                             encoding="utf-8", errors="replace", env=child_env())
    except FileNotFoundError as e:
        return 127, str(e)
    assert p.stdout
    for line in p.stdout:
        line = line.rstrip("\r\n")
        lines.append(line)
        if len(lines) > tail:
            del lines[0]
        log(line)
    return p.wait(), "\n".join(lines)


# --------------------------------------------------------------------------- helpers

_WIN_BAD = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}


def safe_name(name: str, limit: int = 120) -> str:
    """Windows-safe file name that keeps Arabic and other Unicode letters."""
    name = _WIN_BAD.sub("_", name or "").strip()
    name = re.sub(r"[\u200e\u200f\u202a-\u202e\u2066-\u2069]", "", name)  # bidi marks
    name = re.sub(r"\s+", " ", name).strip(" .")
    if not name:
        name = "video"
    if name.split(".")[0].upper() in _RESERVED:
        name = "_" + name
    return name[:limit].rstrip(" .")


def unique_path(p: Path) -> Path:
    if not p.exists():
        return p
    for i in range(2, 1000):
        q = p.with_name(f"{p.stem} ({i}){p.suffix}")
        if not q.exists():
            return q
    return p


def parse_section(s: str | None) -> tuple[str, str] | None:
    if not s:
        return None
    m = re.fullmatch(r"\s*([\d:.]+)?\s*-\s*([\d:.]+|inf)?\s*", s)
    if not m:
        raise SystemExit(f"bad --section '{s}', use 00:01:00-00:02:30")
    return (m.group(1) or "0", m.group(2) or "inf")


def probe_direct(url: str, headers: dict | None = None, proxy: str | None = None) -> bool:
    """True when the server sends a media file (not a web page). Asks the server, not just the URL text."""
    if not MEDIA_EXT.search(urllib.parse.urlparse(url).path + "?"):
        return False
    h = {"User-Agent": UA, "Range": "bytes=0-0", **(headers or {})}
    handlers = []
    if proxy and proxy.startswith("http"):
        handlers.append(urllib.request.ProxyHandler({"http": proxy, "https": proxy}))
    handlers.append(urllib.request.HTTPSHandler(context=_ssl_ctx()))
    opener = urllib.request.build_opener(*handlers)
    for method in ("HEAD", "GET"):
        try:
            req = urllib.request.Request(url, method=method, headers=h)
            with opener.open(req, timeout=20) as r:
                ctype = (r.headers.get("Content-Type") or "").lower()
            return not ctype.startswith(("text/", "application/xhtml", "application/json"))
        except Exception:
            continue
    return False


# --------------------------------------------------------------------------- error classification

PATTERNS = [
    ("drm", r"drm|widevine|playready|fairplay|encrypted media"),
    ("captcha", r"captcha|are you a robot|verify you are human|cloudflare challenge"),
    ("private", r"private video|this video is private|video is private|is not public"),
    ("removed", r"video (is )?(currently )?unavailable|this content isn.t available|has been removed|no longer available|account .* terminated|"
                r"http error 404|404: not found|does not exist|deleted"),
    ("geo_blocked", r"not available in your country|geo.?restrict|georestricted|"
                    r"not made this video available in your (country|region)|blocked in your (country|region)"),
    ("login_required", r"sign in to confirm|login required|log ?in to|requires? (authentication|login|account)|"
                       r"use --cookies|cookies-from-browser|registered users|members.only|age.restricted|"
                       r"confirm your age|subscriber|premium|not a bot|rate-limited by the server.*account"),
    ("rate_limited", r"http error 429|too many requests|rate.?limit"),
    ("forbidden", r"http error 403|403: forbidden|forbidden"),
    ("unsupported", r"unsupported url|no video formats found|unable to extract|no media found|"
                    r"no suitable (info )?extractor|is not a valid url|requested format is not available"),
    ("tls", r"peer certificate failed verification|certificate verify failed|tls @"),
    ("network", r"timed out|timeout|connection (reset|refused|aborted)|getaddrinfo|"
                r"name resolution|ssl|unable to download webpage|remote end closed|proxy"),
]

HINTS = {
    "drm": "DRM protected: cannot be downloaded (and must not be circumvented). Use the site's own offline/download feature.",
    "captcha": "The site shows a CAPTCHA/bot check. It is not solved automatically: open it in a real browser, "
               "then retry with --browser-cookies chrome|edge|firefox.",
    "private": "Private video: only the owner/allowed accounts can see it. If your account has access, use --browser-cookies.",
    "removed": "Removed / unavailable / wrong link. Check the URL in a browser.",
    "geo_blocked": "Geo-blocked: retry with --proxy URL of an allowed country (or proxies.txt / VG_PROXIES).",
    "login_required": "Login / age / bot check required: log in with your browser, then add --browser-cookies chrome "
                      "(or edge|firefox), or --cookies cookies.txt.",
    "rate_limited": "HTTP 429 rate limit: wait, use --proxy auto with a proxy pool, or add --browser-cookies.",
    "forbidden": "HTTP 403: try --browser-cookies, --proxy auto, or python grab.py --update.",
    "unsupported": "yt-dlp has no extractor / found no media. The ghost-browser sniff is the fallback (remove --no-browser).",
    "tls": "TLS certificate check failed inside ffmpeg (verification is never disabled). Try without --section, or --update.",
    "network": "Network error: check connection / proxy and retry.",
    "failed": "Unknown failure: run python grab.py --update and retry; see the log above.",
}

TERMINAL = {"drm", "private", "removed", "login_required", "captcha"}
PROXY_WORTHY = {"forbidden", "rate_limited", "geo_blocked", "network"}
SNIFF_WORTHY = {"unsupported", "forbidden", "failed", "network", "rate_limited"}


def classify(text: str) -> str:
    err = "\n".join(l for l in text.splitlines() if re.search(r"error|certificate|warning.*(drm|login|sign in)", l, re.I)) or text[-2000:]
    low = err.lower()
    for kind, pat in PATTERNS:
        if re.search(pat, low):
            return kind
    return "failed"


def last_error(text: str) -> str:
    errs = [l.strip() for l in text.splitlines() if "ERROR" in l or "error" in l.lower()[:20]]
    return (errs[-1] if errs else text.strip().splitlines()[-1] if text.strip() else "")[:500]


# --------------------------------------------------------------------------- ffprobe verify

def ffprobe(path: Path) -> dict:
    fp = find_exe("ffprobe")
    info: dict = {"path": str(path), "size_mb": round(path.stat().st_size / 1048576, 2) if path.exists() else 0}
    if not fp or not path.exists():
        info["verified"] = False
        return info
    try:
        r = subprocess.run([fp, "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        d = json.loads(r.stdout or "{}")
    except Exception as e:
        info.update(verified=False, probe_error=str(e))
        return info
    streams = d.get("streams", [])
    v = next((s for s in streams if s.get("codec_type") == "video" and s.get("disposition", {}).get("attached_pic") != 1), None)
    a = next((s for s in streams if s.get("codec_type") == "audio"), None)
    subs = [s.get("tags", {}).get("language", "?") for s in streams if s.get("codec_type") == "subtitle"]
    dur = d.get("format", {}).get("duration") or (v or a or {}).get("duration")
    info.update(
        verified=bool(v or a) and dur is not None,
        container=d.get("format", {}).get("format_name"),
        duration=round(float(dur), 2) if dur else None,
        width=v.get("width") if v else None,
        height=v.get("height") if v else None,
        fps=_fps(v.get("avg_frame_rate")) if v else None,
        vcodec=v.get("codec_name") if v else None,
        acodec=a.get("codec_name") if a else None,
        has_video=bool(v),
        has_audio=bool(a),
        subtitles=subs,
    )
    return info


def _fps(r: str | None):
    try:
        n, d = (r or "0/1").split("/")
        return round(int(n) / int(d), 3) if int(d) else None
    except Exception:
        return None


def append_source(out: Path, url: str, files: list[dict], method: str, page: str | None = None):
    try:
        with open(out / "sources.txt", "a", encoding="utf-8") as f:
            ts = _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            for fi in files:
                line = f"{ts}\t{url}\t{Path(fi['path']).name}\t{method}"
                if page and page != url:
                    line += f"\tstream={page}"
                f.write(line + "\n")
    except Exception as e:
        log(f"[warn] could not write sources.txt: {e}")


# --------------------------------------------------------------------------- yt-dlp

def build_ytdlp(url: str, a, out: Path, proxy: str | None, use_aria: bool, list_file: Path,
                headers: dict | None = None, cookies_file: str | None = None, generic: bool = False) -> list[str]:
    cmd = ytdlp_cmd() + [
        "--newline", "--no-colors", "--ignore-config",
        "-P", str(out),
        "-o", "%(title).150B [%(id)s].%(ext)s",
        "--windows-filenames", "--trim-filenames", "180",
        "--retries", "10", "--fragment-retries", "10", "--extractor-retries", "3",
        "--retry-sleep", "exp=1:20", "--socket-timeout", "30",
        "-N", "8",
        "--no-mtime",
        "--print-to-file", "after_move:%(filepath)s", str(list_file),
    ]
    sec = parse_section(a.section)
    # -------- formats
    if a.audio_only:
        cmd += ["-f", "ba/b", "-x", "--audio-format", a.audio_only, "--audio-quality", "0"]
    else:
        sort = []
        if a.quality and a.quality != "best":
            sort.append(f"res:{a.quality}")
        if a.compat:
            sort += ["vcodec:h264", "acodec:m4a"]
        cmd += ["-f", "bv*+ba/b"]
        if sort:
            cmd += ["-S", ",".join(sort)]
        cmd += ["--merge-output-format", "mp4" if a.compat else "mp4/mkv"]
    if sec:
        cmd += ["--download-sections", f"*{sec[0]}-{sec[1]}"]
        if a.exact_cuts:
            cmd += ["--force-keyframes-at-cuts"]
    # -------- extras
    if a.subs:
        cmd += ["--write-subs", "--write-auto-subs", "--sub-langs", a.subs, "--convert-subs", "srt"]
        if not a.audio_only:
            cmd += ["--embed-subs"]
    if a.info_json:
        cmd += ["--write-info-json"]
    if a.thumbnail:
        cmd += ["--write-thumbnail", "--convert-thumbnails", "jpg"]
        if not sec:
            cmd += ["--embed-thumbnail"]
    if not a.audio_only:
        cmd += ["--embed-metadata"]
    # -------- playlist
    if a.playlist:
        cmd += ["--yes-playlist"]
        if a.limit:
            cmd += ["-I", f":{a.limit}"]
    else:
        cmd += ["--no-playlist"]
    # -------- network / auth
    if proxy:
        cmd += ["--proxy", proxy]
    if cookies_file:
        cmd += ["--cookies", cookies_file]
    elif a.cookies:
        cmd += ["--cookies", a.cookies]
    elif a.browser_cookies:
        cmd += ["--cookies-from-browser", a.browser_cookies]
    for k, v in (headers or {}).items():
        if v:
            cmd += ["--add-headers", f"{k}:{v}"]
    if generic:
        cmd += ["--force-generic-extractor"]
    aria = find_exe("aria2c")
    if use_aria and aria and not sec:
        cmd += ["--downloader", f"http,https:{aria}",
                "--downloader-args", "aria2c:-x 16 -s 16 -k 1M --file-allocation=none --console-log-level=warn "
                                     "--summary-interval=0 --auto-file-renaming=false"]
    cmd += ["--", url]
    return cmd


def try_ytdlp(url: str, a, out: Path, proxy: str | None, headers=None, cookies_file=None, generic=False) -> dict:
    """One yt-dlp attempt (with aria2c, then native downloader if aria2c broke). Returns attempt dict."""
    res = {}
    for use_aria in ((True, False) if find_exe("aria2c") and not a.no_aria else (False,)):
        fd, lf = tempfile.mkstemp(prefix="vg_", suffix=".txt")
        os.close(fd)
        list_file = Path(lf)
        cmd = build_ytdlp(url, a, out, proxy, use_aria, list_file, headers, cookies_file, generic)
        log(f"[yt-dlp] {'aria2c' if use_aria else 'native'}{' via proxy ' + _mask(proxy) if proxy else ''}"
            f"{' (generic, sniffed headers)' if generic or headers else ''}")
        code, out_text = run_stream(cmd)
        files = []
        try:
            files = [Path(l.strip()) for l in list_file.read_text(encoding="utf-8", errors="replace").splitlines() if l.strip()]
        except Exception:
            pass
        list_file.unlink(missing_ok=True)
        files = list(dict.fromkeys(f for f in files if f.exists()))
        kind = "ok" if code == 0 and files else classify(out_text)
        if code == 0 and not files:
            kind = "unsupported" if re.search(r"no video|no formats|0 items", out_text, re.I) else "failed"
            if re.search(r"has already been downloaded", out_text):
                m = re.findall(r"\[download\] (.+?) has already been downloaded", out_text)
                files = [Path(x) for x in m if Path(x).exists()]
                kind = "ok" if files else kind
        res = {"kind": kind, "files": files, "error": "" if kind == "ok" else last_error(out_text), "log": out_text}
        if kind == "ok" or kind in TERMINAL or kind in ("unsupported", "geo_blocked", "tls"):
            break
        if use_aria:
            log("[yt-dlp] retrying with the native downloader (no aria2c) ...")
            _cleanup_aria_parts(out)
    return res


def _cleanup_aria_parts(out: Path):
    for p in out.glob("*.aria2"):
        try:
            p.unlink()
            Path(str(p)[:-6]).unlink(missing_ok=True)
        except Exception:
            pass


def _mask(proxy: str | None) -> str:
    if not proxy:
        return "direct"
    return re.sub(r"//[^@/]+@", "//***@", proxy)


# --------------------------------------------------------------------------- direct / ffmpeg

def direct_aria(url: str, out: Path, headers: dict | None = None, proxy: str | None = None,
                cookies_file: str | None = None, name: str | None = None) -> dict:
    aria = find_exe("aria2c")
    if not name:
        base = urllib.parse.unquote(Path(urllib.parse.urlparse(url).path).name) or "video.mp4"
        name = base
    stem, ext = os.path.splitext(name)
    name = safe_name(stem) + (ext if ext else ".mp4")
    target = out / name
    if target.exists() and not (out / (name + ".aria2")).exists():
        info = ffprobe(target)
        if info.get("verified"):
            log(f"[direct] already downloaded: {target}")
            return {"kind": "ok", "files": [target], "error": ""}
    if not aria:
        return _direct_urllib(url, target, headers, proxy)
    for conn in ("16", "4"):
        cmd = [aria, "-x", conn, "-s", conn, "-k", "1M", "-c", "--file-allocation=none",
               "--console-log-level=warn", "--summary-interval=5", "--auto-file-renaming=false",
               "--allow-overwrite=true", "--max-tries=10", "--retry-wait=3", "--check-certificate=true",
               "-d", str(out), "-o", name]
        hdrs = {"User-Agent": UA, **(headers or {})}
        for k, v in hdrs.items():
            if v:
                cmd += ["--header", f"{k}: {v}"]
        if cookies_file:
            cmd += ["--load-cookies", cookies_file]
        if proxy and proxy.startswith("http"):
            cmd += ["--all-proxy", proxy]
        cmd.append(url)
        log(f"[direct] aria2c x{conn} -> {target}")
        code, text = run_stream(cmd)
        if code == 0 and target.exists():
            return {"kind": "ok", "files": [target], "error": ""}
        log("[direct] aria2c failed, retrying with fewer connections ...")
    return {"kind": classify(text), "files": [], "error": last_error(text)}


def _direct_urllib(url, target: Path, headers, proxy) -> dict:
    try:
        handlers = [urllib.request.ProxyHandler({"http": proxy, "https": proxy})] if proxy else []
        handlers.append(urllib.request.HTTPSHandler(context=_ssl_ctx()))
        opener = urllib.request.build_opener(*handlers)
        req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
        with opener.open(req, timeout=60) as r, open(target, "wb") as f:
            shutil.copyfileobj(r, f, 1 << 20)
        return {"kind": "ok", "files": [target], "error": ""}
    except Exception as e:
        return {"kind": classify(str(e)), "files": [], "error": str(e)}


# --------------------------------------------------------------------------- section fallbacks
# Some ffmpeg builds on Windows fail TLS verification on certain hosts ("Peer certificate failed
# verification") while Python (certifi) verifies them fine. TLS checks are never disabled; instead the
# needed bytes are fetched by Python and ffmpeg only cuts local files.

def _ssl_ctx():
    """Verified TLS context using certifi's CA bundle (same trust store yt-dlp uses)."""
    import ssl
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def _http_get(url: str, headers: dict, proxy: str | None, timeout=60) -> bytes:
    handlers = [urllib.request.ProxyHandler({"http": proxy, "https": proxy})] if proxy and proxy.startswith("http") else []
    handlers.append(urllib.request.HTTPSHandler(context=_ssl_ctx()))
    opener = urllib.request.build_opener(*handlers)
    last = None
    for i in range(5):
        try:
            with opener.open(urllib.request.Request(url, headers=headers), timeout=timeout) as r:
                return r.read()
        except Exception as e:  # retry with backoff
            last = e
            time.sleep(min(2 ** i, 10))
    raise last  # type: ignore[misc]


def _secs(t: str) -> float:
    if t == "inf":
        return float("inf")
    parts = [float(x) for x in t.split(":")]
    v = 0.0
    for p in parts:
        v = v * 60 + p
    return v


def hls_section_local(url: str, out: Path, title: str, a, headers: dict | None = None,
                      proxy: str | None = None) -> dict:
    """Download only the HLS segments that cover --section (Python TLS), then cut with ffmpeg locally."""
    from concurrent.futures import ThreadPoolExecutor
    ff = find_exe("ffmpeg")
    hdrs = {"User-Agent": UA, **(headers or {})}
    sec = parse_section(a.section) or ("0", "inf")
    start, end = _secs(sec[0]), _secs(sec[1])
    try:
        text = _http_get(url, hdrs, proxy).decode("utf-8", "replace")
        base = url
        audio_url = None
        if "#EXT-X-STREAM-INF" in text:  # master playlist: pick the best variant within --quality
            variants, lines = [], text.splitlines()
            for i, l in enumerate(lines):
                if l.startswith("#EXT-X-STREAM-INF"):
                    bw = int((re.search(r"BANDWIDTH=(\d+)", l) or [0, 0])[1])
                    res = re.search(r"RESOLUTION=\d+x(\d+)", l)
                    h = int(res.group(1)) if res else 0
                    j = i + 1
                    while j < len(lines) and (not lines[j].strip() or lines[j].startswith("#")):
                        j += 1
                    if j < len(lines):
                        variants.append((h, bw, urllib.parse.urljoin(url, lines[j].strip()), l))
            cap = int(a.quality) if a.quality not in (None, "best") else 10 ** 6
            ok = [v for v in variants if not v[0] or v[0] <= cap] or variants
            h, bw, base, line = max(ok, key=lambda v: (v[0], v[1]))
            grp = re.search(r'AUDIO="([^"]+)"', line)
            if grp:  # separate audio rendition
                m = re.search(r'#EXT-X-MEDIA:[^\n]*TYPE=AUDIO[^\n]*GROUP-ID="%s"[^\n]*URI="([^"]+)"' % re.escape(grp.group(1)), text)
                audio_url = urllib.parse.urljoin(url, m.group(1)) if m else None
            log(f"[hls-local] variant {h or '?'}p {bw // 1000}kbps")
            text = _http_get(base, hdrs, proxy).decode("utf-8", "replace")

        def plan(pl_text: str, pl_url: str):
            if re.search(r"#EXT-X-KEY:.*METHOD=(?!NONE)", pl_text):
                raise RuntimeError("encrypted HLS (EXT-X-KEY) - not handled by the local fallback")
            init, segs, t, dur = None, [], 0.0, None
            for l in pl_text.splitlines():
                l = l.strip()
                if l.startswith("#EXT-X-MAP"):
                    m = re.search(r'URI="([^"]+)"', l)
                    init = urllib.parse.urljoin(pl_url, m.group(1)) if m else None
                elif l.startswith("#EXTINF:"):
                    dur = float(l[8:].split(",")[0])
                elif l and not l.startswith("#") and dur is not None:
                    if t + dur > start and t < end:
                        segs.append((t, urllib.parse.urljoin(pl_url, l)))
                    t += dur
                    dur = None
            if not segs:
                raise RuntimeError("no segments in the requested section")
            return init, segs

        tmp = Path(tempfile.mkdtemp(prefix="vg_hls_", dir=out))
        parts = []
        for name, pl_text, pl_url in [("v", text, base)] + (
                [("a", _http_get(audio_url, hdrs, proxy).decode("utf-8", "replace"), audio_url)] if audio_url else []):
            init, segs = plan(pl_text, pl_url)
            log(f"[hls-local] {name}: {len(segs)} segments from {segs[0][0]:.1f}s")
            with ThreadPoolExecutor(8) as ex:
                blobs = list(ex.map(lambda s: _http_get(s[1], hdrs, proxy), segs))
            ext = ".mp4" if init else ".ts"
            pth = tmp / f"{name}{ext}"
            with open(pth, "wb") as f:
                if init:
                    f.write(_http_get(init, hdrs, proxy))
                for b in blobs:
                    f.write(b)
            parts.append((pth, segs[0][0]))
        ext = f".{a.audio_only}" if a.audio_only else ".mp4"
        tag = f" [{sec[0]}-{sec[1]}]".replace(":", "-")
        target = unique_path(out / (safe_name(title) + tag + ext))
        cmd = [ff, "-hide_banner", "-loglevel", "warning", "-y"]
        for pth, t0 in parts:
            cmd += ["-ss", f"{max(0.0, start - t0):.3f}"]
            if end != float("inf"):
                cmd += ["-t", f"{end - start:.3f}"]
            cmd += ["-i", str(pth)]
        if a.audio_only:
            cmd += ["-vn", *{"mp3": ["-c:a", "libmp3lame", "-q:a", "0"], "m4a": ["-c:a", "aac", "-b:a", "256k"],
                             "wav": ["-c:a", "pcm_s16le"]}[a.audio_only]]
        else:
            cmd += ["-map", "0:v:0?", "-map", f"{len(parts) - 1}:a:0?", "-c", "copy", "-movflags", "+faststart"]
        cmd.append(str(target))
        code, text_out = run_stream(cmd)
        shutil.rmtree(tmp, ignore_errors=True)
        if code == 0 and target.exists() and target.stat().st_size > 0:
            return {"kind": "ok", "files": [target], "error": "", "method": "hls-local-section"}
        return {"kind": "failed", "files": [], "error": last_error(text_out)}
    except Exception as e:
        try:
            shutil.rmtree(tmp, ignore_errors=True)  # type: ignore[possibly-undefined]
        except Exception:
            pass
        return {"kind": classify(str(e)), "files": [], "error": f"hls-local: {e}"}


def cut_local(src: Path, a) -> Path | None:
    """Cut --section out of an already downloaded local file (stream copy)."""
    ff = find_exe("ffmpeg")
    sec = parse_section(a.section)
    if not ff or not sec:
        return None
    target = unique_path(src.with_name(f"{src.stem} [{sec[0]}-{sec[1]}]{src.suffix}".replace(":", "-")))
    cmd = [ff, "-hide_banner", "-loglevel", "warning", "-y", "-ss", sec[0]]
    if sec[1] != "inf":
        cmd += ["-to", sec[1]]
    cmd += ["-i", str(src), "-map", "0", "-c", "copy", str(target)]
    code, _ = run_stream(cmd)
    if code == 0 and target.exists() and target.stat().st_size > 0:
        src.unlink(missing_ok=True)
        return target
    return None


def section_fallback(url: str, a, out: Path, proxy: str | None, headers=None, cookies_file=None,
                     title: str | None = None) -> dict:
    if STREAM_EXT.search(url) and ".m3u8" in url.lower():
        r = hls_section_local(url, out, title or Path(urllib.parse.urlparse(url).path).stem, a, headers, proxy)
        if r["kind"] == "ok":
            return r
        log(f"[section] HLS-local failed: {r.get('error')}")
    log("[section] downloading full media, then cutting locally ...")
    sec_saved = a.section
    a.section = None
    try:
        r = try_ytdlp(url, a, out, proxy, headers=headers, cookies_file=cookies_file)
    finally:
        a.section = sec_saved
    if r["kind"] != "ok":
        return r
    cut = [cut_local(Path(f), a) for f in r["files"]]
    if all(cut):
        return {"kind": "ok", "files": cut, "error": "", "method": "yt-dlp-full+local-cut"}
    return {"kind": "ok", "files": r["files"], "error": "", "method": "yt-dlp-full (cut failed)",
            "warning": "could not cut the section locally; full file kept"}


def ffmpeg_stream(url: str, out: Path, title: str, a, headers: dict | None = None, proxy: str | None = None) -> dict:
    ff = find_exe("ffmpeg")
    if not ff:
        return {"kind": "failed", "files": [], "error": "ffmpeg not found"}
    ext = f".{a.audio_only}" if a.audio_only else ".mp4"
    target = unique_path(out / (safe_name(title) + ext))
    hdrs = {"User-Agent": UA, **(headers or {})}
    cmd = [ff, "-hide_banner", "-loglevel", "warning", "-stats", "-y"]
    hs = "".join(f"{k}: {v}\r\n" for k, v in hdrs.items() if v and k.lower() != "user-agent")
    cmd += ["-user_agent", hdrs.get("User-Agent", UA)]
    if hs:
        cmd += ["-headers", hs]
    if proxy and proxy.startswith("http"):
        cmd += ["-http_proxy", proxy]
    sec = parse_section(a.section)
    if sec:
        cmd += ["-ss", sec[0]]
        if sec[1] != "inf":
            cmd += ["-to", sec[1]]
    cmd += ["-i", url]
    if a.audio_only:
        codec = {"mp3": ["-c:a", "libmp3lame", "-q:a", "0"], "m4a": ["-c:a", "aac", "-b:a", "256k"],
                 "wav": ["-c:a", "pcm_s16le"]}[a.audio_only]
        cmd += ["-vn", *codec]
    else:
        cmd += ["-map", "0:v:0?", "-map", "0:a:0?", "-c", "copy", "-bsf:a", "aac_adtstoasc", "-movflags", "+faststart"]
    cmd.append(str(target))
    log(f"[ffmpeg] {url[:120]} -> {target}")
    code, text = run_stream(cmd)
    if code == 0 and target.exists() and target.stat().st_size > 0:
        return {"kind": "ok", "files": [target], "error": ""}
    target.unlink(missing_ok=True)
    return {"kind": classify(text), "files": [], "error": last_error(text)}


# --------------------------------------------------------------------------- proxy / browser (helper-6 modules)

def load_pool(a):
    try:
        from proxy_pool import ProxyPool  # type: ignore
    except Exception as e:
        log(f"[proxy] proxy_pool.py not available ({e.__class__.__name__}); no rotation")
        return None
    try:
        return ProxyPool.from_sources(file=a.proxy_file, env=True, tor=a.tor, free=a.free_proxies, check=True)
    except Exception as e:
        log(f"[proxy] could not build pool: {e}")
        return None


def sniff(url: str, a, proxy: str | None) -> dict | None:
    try:
        from ghost_browser import GhostBrowser  # type: ignore
    except Exception as e:
        log(f"[sniff] ghost_browser.py not available ({e.__class__.__name__}: {e})")
        return None
    try:
        log(f"[sniff] opening {url} in the ghost browser{' via ' + _mask(proxy) if proxy else ''} ...")
        with GhostBrowser(proxy=proxy) as gb:
            return gb.sniff(url, wait=a.sniff_wait)
    except Exception as e:
        log(f"[sniff] failed: {e}")
        return {"error": str(e), "media": []}


def download_sniffed(page_url: str, r: dict, a, out: Path, proxy: str | None) -> dict:
    media = sorted(r.get("media") or [], key=lambda m: m.get("score", 0), reverse=True)
    best = r.get("best")
    if isinstance(best, dict):
        media = [best] + [m for m in media if m.get("url") != best.get("url")]
    elif isinstance(best, str):
        media = [{"url": best, "kind": "hls" if ".m3u8" in best else "dash" if ".mpd" in best else "mp4"}] + \
                [m for m in media if m.get("url") != best]
    media = [m for m in media if m.get("kind") in ("hls", "dash", "mp4", "webm", "audio", "other")
             and m.get("url") and not m.get("drm")]  # per-item DRM flag: never touch protected streams
    if a.audio_only:
        pass
    else:
        media = [m for m in media if m.get("kind") != "audio"] + [m for m in media if m.get("kind") == "audio"]
    title = r.get("title") or urllib.parse.urlparse(page_url).netloc
    cookies = r.get("cookies_file")
    last = {"kind": "unsupported", "files": [], "error": "the browser found no media stream on the page"}
    for m in media[:4]:
        murl = m["url"]
        hdrs = dict(m.get("headers") or {})
        hdrs.setdefault("Referer", r.get("final_url") or page_url)
        hdrs.setdefault("User-Agent", r.get("user_agent") or UA)
        kind = m.get("kind")
        log(f"[sniff] trying {kind}: {murl[:140]}")
        if kind in ("mp4", "webm", "audio", "other") and not a.section and not a.audio_only and kind != "audio":
            ext = ".webm" if kind == "webm" else ".mp4"
            res = direct_aria(murl, out, hdrs, proxy, cookies, name=safe_name(title) + ext)
            if res["kind"] == "ok":
                res["method"], res["stream"] = "sniff+aria2c", murl
                return res
        res = try_ytdlp(murl, a, out, proxy, headers=hdrs, cookies_file=cookies, generic=False)
        if res["kind"] == "ok":
            res["method"], res["stream"] = "sniff+yt-dlp", murl
            return res
        if a.section and (kind == "hls" or ".m3u8" in murl.lower()):
            res = hls_section_local(murl, out, title, a, hdrs, proxy)
            if res["kind"] == "ok":
                res["method"], res["stream"] = "sniff+hls-local", murl
                return res
        if kind in ("hls", "dash") or STREAM_EXT.search(murl):
            res = ffmpeg_stream(murl, out, title, a, hdrs, proxy)
            if res["kind"] == "ok":
                res["method"], res["stream"] = "sniff+ffmpeg", murl
                return res
        last = res
    return last


# --------------------------------------------------------------------------- per-URL pipeline

def grab_one(url: str, a, out: Path, pool_holder: dict) -> dict:
    t0 = time.time()
    result = {"url": url, "ok": False, "status": "failed", "method": None, "files": [], "attempts": [],
              "error": "", "hint": ""}
    fixed_proxy = None if a.proxy in ("auto", "none") else a.proxy

    def note(step, res, proxy=None):
        result["attempts"].append({"step": step, "proxy": _mask(proxy), "result": res.get("kind"),
                                   "error": (res.get("error") or "")[:300]})

    def finish(res, method, stream=None):
        files = [ffprobe(Path(f)) for f in res["files"]]
        files = [f for f in files if not f["path"].endswith((".json", ".jpg", ".webp", ".png", ".srt", ".vtt"))] or files
        result.update(ok=True, status="ok", method=res.get("method", method), files=files, error="", hint="")
        bad = [f for f in files if not f.get("verified")]
        if bad:
            result["warning"] = "ffprobe could not verify: " + ", ".join(Path(b["path"]).name for b in bad)
        if not a.audio_only and files and not any(f.get("has_audio") for f in files):
            result["warning"] = (result.get("warning", "") + " no audio stream in the output").strip()
        append_source(out, url, files, result["method"], res.get("stream") or stream)
        return result

    # 0) direct media file
    tried_direct = False
    if not a.section and not a.audio_only and probe_direct(url, proxy=fixed_proxy):
        tried_direct = True
        res = direct_aria(url, out, proxy=fixed_proxy, cookies_file=a.cookies)
        note("direct-aria2c", res, fixed_proxy)
        if res["kind"] == "ok":
            return finish(res, "direct-aria2c")

    # 1) yt-dlp  (skipped with --sniff: go straight to the ghost browser)
    if a.sniff:
        res = {"kind": "unsupported", "files": [], "error": "--sniff: yt-dlp skipped"}
    else:
        maybe_refresh_stale(a)
        res = try_ytdlp(url, a, out, fixed_proxy)
        note("yt-dlp", res, fixed_proxy)
        if res["kind"] in RETRY_AFTER_UPDATE and refresh_ytdlp(a, f"download failed ({res['kind']})"):
            res = try_ytdlp(url, a, out, fixed_proxy)
            note("yt-dlp after update", res, fixed_proxy)
    if res["kind"] == "ok":
        return finish(res, "yt-dlp" + ("+proxy" if fixed_proxy else ""))
    kind = res["kind"]

    # 1b) --section broke inside ffmpeg (often its TLS on Windows) -> fetch with Python, cut locally
    if a.section and kind in ("tls", "failed"):
        r1 = section_fallback(url, a, out, fixed_proxy)
        note("section-fallback", r1, fixed_proxy)
        if r1["kind"] == "ok":
            return finish(r1, r1.get("method", "section-fallback"))

    # 2) proxy rotation
    used_proxy = fixed_proxy
    if kind in PROXY_WORTHY and a.proxy == "auto":
        if "pool" not in pool_holder:
            pool_holder["pool"] = load_pool(a)
        pool = pool_holder["pool"]
        tried = 0
        while pool is not None and tried < a.proxy_tries:
            try:  # cookies must only travel through trusted proxies (not free public ones)
                pobj = pool.next(trusted_only=bool(a.cookies or a.browser_cookies))
            except TypeError:
                pobj = pool.next()
            if not pobj:
                log("[proxy] pool empty (no proxies configured / alive) - see SKILL.md 'Proxy setup'")
                break
            p = pobj if isinstance(pobj, str) else getattr(pobj, "url", str(pobj))
            tried += 1
            r2 = try_ytdlp(url, a, out, p)
            note("yt-dlp+proxy", r2, p)
            if r2["kind"] == "ok":
                result["proxy"] = _mask(p)
                return finish(r2, "yt-dlp+proxy")
            if r2["kind"] in TERMINAL or r2["kind"] == "unsupported":
                kind, res = r2["kind"], r2
                used_proxy = p
                break
            try:
                pool.mark_bad(pobj, r2["kind"])
            except Exception:
                pass
            kind, res = r2["kind"], r2

    # 3) ghost browser sniff
    if kind in SNIFF_WORTHY and not a.no_browser:
        r = sniff(url, a, used_proxy)
        if r is not None:
            sn = {"kind": "unsupported", "error": r.get("error") or ""}
            media_all = r.get("media") or []
            clear = [m for m in media_all if not m.get("drm")]
            if media_all and not clear:
                sn = {"kind": "drm", "error": "every stream the browser found is DRM protected (EME/Widevine/PlayReady)"}
            elif not media_all and r.get("drm"):
                sn = {"kind": "drm", "error": "browser saw DRM (EME) on the page and no clear stream"}
            elif clear:
                sn = download_sniffed(url, r, a, out, used_proxy)
                if sn["kind"] == "ok":
                    note("ghost-sniff", sn, used_proxy)
                    result["title"] = r.get("title")
                    return finish(sn, sn.get("method", "sniff"))
            elif r.get("captcha"):
                sn = {"kind": "captcha", "error": "the page shows a CAPTCHA / bot check"}
            note("ghost-sniff", sn, used_proxy)
            if r.get("notes"):
                result["sniff_notes"] = r.get("notes")
            if sn["kind"] != "unsupported" or kind == "failed":
                kind, res = sn["kind"], sn

    # 4) last resort for URLs that look like media files: aria2c (other TLS stack, 16 conns, resume)
    if kind not in TERMINAL and not tried_direct and MEDIA_EXT.search(urllib.parse.urlparse(url).path + "?")             and not a.audio_only:
        r4 = direct_aria(url, out, proxy=used_proxy, cookies_file=a.cookies)
        note("direct-aria2c", r4, used_proxy)
        if r4["kind"] == "ok":
            if a.section:
                c = cut_local(Path(r4["files"][0]), a)
                if c:
                    r4["files"] = [c]
            return finish(r4, "direct-aria2c")

    result.update(status=kind, error=res.get("error", ""), hint=HINTS.get(kind, HINTS["failed"]))
    result["seconds"] = round(time.time() - t0, 1)
    return result


# --------------------------------------------------------------------------- --info

def info_one(url: str, a) -> dict:
    cmd = ytdlp_cmd() + ["-J", "--no-warnings", "--ignore-config", "--flat-playlist" if a.playlist else "--no-playlist"]
    proxy = None if a.proxy in ("auto", "none") else a.proxy
    if proxy:
        cmd += ["--proxy", proxy]
    if a.cookies:
        cmd += ["--cookies", a.cookies]
    elif a.browser_cookies:
        cmd += ["--cookies-from-browser", a.browser_cookies]
    cmd += ["--", url]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", env=child_env())
    if r.returncode == 0 and r.stdout.strip():
        d = json.loads(r.stdout)
        if d.get("_type") == "playlist":
            ents = d.get("entries") or []
            return {"url": url, "ok": True, "type": "playlist", "title": d.get("title"), "count": len(ents),
                    "entries": [{"title": e.get("title"), "url": e.get("url"), "duration": e.get("duration")}
                                for e in ents[: (a.limit or 50)]]}
        fmts = d.get("formats") or []
        heights = sorted({f.get("height") for f in fmts if f.get("height")})
        return {"url": url, "ok": True, "type": "video", "extractor": d.get("extractor_key"),
                "title": d.get("title"), "uploader": d.get("uploader"), "duration": d.get("duration"),
                "upload_date": d.get("upload_date"), "best_height": max(heights) if heights else d.get("height"),
                "heights": heights, "vcodecs": sorted({(f.get("vcodec") or "").split(".")[0] for f in fmts
                                                        if f.get("vcodec") not in (None, "none")}),
                "has_drm": any(f.get("has_drm") for f in fmts),
                "subtitles": sorted((d.get("subtitles") or {}).keys()),
                "auto_subtitles": len(d.get("automatic_captions") or {}),
                "is_live": d.get("is_live"), "webpage_url": d.get("webpage_url")}
    kind = classify(r.stderr)
    out = {"url": url, "ok": False, "status": kind, "error": last_error(r.stderr), "hint": HINTS.get(kind, "")}
    if kind in SNIFF_WORTHY and not a.no_browser:
        s = sniff(url, a, proxy)
        if s and s.get("media"):
            out.update(ok=True, type="sniffed", title=s.get("title"), drm=s.get("drm"), captcha=s.get("captcha"),
                       media=[{k: m.get(k) for k in ("url", "kind", "score")} for m in s["media"][:10]])
        elif s:
            out.update(drm=s.get("drm"), captcha=s.get("captcha"), sniff_notes=s.get("notes"))
    return out


# --------------------------------------------------------------------------- update

# yt-dlp breaks whenever a site changes; an old copy is the most common cause of a failed download
# (2026-11-16: an Instagram link failed only because yt-dlp was months old). So before the first
# yt-dlp attempt an old copy is refreshed, and after a failure yt-dlp is refreshed once and the
# attempt repeated if the version really changed. Only an already installed yt-dlp is upgraded.
# Dragon rule §2: installing needs the owner's explicit yes, so this is OFF by default and runs only
# with --auto-update or VG_AUTOUPDATE=1 (and never with --no-auto-update / VG_NO_AUTOUPDATE / KOSIF_NO_AUTOINSTALL).
# Without it the grabber only says that yt-dlp is old and prints the update command.
STALE_DAYS = 30
RETRY_AFTER_UPDATE = {"failed", "unsupported", "forbidden", "login_required"}
_refresh_state = {"done": False}


def ytdlp_version() -> str:
    try:
        r = subprocess.run(ytdlp_cmd() + ["--version"], capture_output=True, text=True, timeout=60)
        return (r.stdout or "").strip()
    except (OSError, subprocess.TimeoutExpired, SystemExit):
        return ""


def ytdlp_age_days(version: str, today: _dt.date | None = None) -> int | None:
    """yt-dlp versions are dates (2026.11.02 or 2026.11.02.123456); None when it cannot be read."""
    m = re.match(r"(\d{4})\.(\d{1,2})\.(\d{1,2})", version or "")
    if not m:
        return None
    try:
        built = _dt.date(int(m[1]), int(m[2]), int(m[3]))
    except ValueError:
        return None
    return ((today or _dt.date.today()) - built).days


def auto_update_allowed(a) -> bool:
    if getattr(a, "no_auto_update", False) or os.environ.get("VG_NO_AUTOUPDATE") or os.environ.get("KOSIF_NO_AUTOINSTALL"):
        return False
    return bool(getattr(a, "auto_update", False) or os.environ.get("VG_AUTOUPDATE") == "1")


_hinted = {"done": False}


def update_hint(reason: str) -> None:
    """Opt-in is off: say it once, with the exact command, and change nothing."""
    if not _hinted["done"]:
        _hinted["done"] = True
        log(f"[update] yt-dlp {reason}: an update may fix it. With the owner's yes: grab.py --update "
            "(or rerun with --auto-update)")


def _upgrade_ytdlp() -> None:
    """pip -U for this Python (falls back to --user); a standalone yt-dlp program also gets its own -U."""
    base = [sys.executable, "-m", "pip", "install", "-U", "--quiet", "--disable-pip-version-check", "yt-dlp[default]"]
    for extra in ([], ["--user"]):
        try:
            r = subprocess.run(base + extra, capture_output=True, text=True, timeout=300, env=child_env())
        except (OSError, subprocess.TimeoutExpired):
            break
        if r.returncode == 0:
            break
    try:
        cmd = ytdlp_cmd()
    except SystemExit:
        return
    if cmd[0] != sys.executable:  # yt-dlp.exe / winget / standalone binary: pip does not touch it
        try:
            subprocess.run(cmd + ["-U"], capture_output=True, text=True, timeout=300, env=child_env())
        except (OSError, subprocess.TimeoutExpired):
            pass


def refresh_ytdlp(a, reason: str) -> bool:
    """Upgrade yt-dlp at most once per run. True only when the version actually changed."""
    if _refresh_state["done"]:
        return False
    if not auto_update_allowed(a):
        update_hint(reason)
        return False
    _refresh_state["done"] = True
    old = ytdlp_version()
    log(f"[update] yt-dlp {old or '?'}: {reason} -> updating ...")
    _upgrade_ytdlp()
    new = ytdlp_version()
    log(f"[update] yt-dlp {old or '?'} -> {new or '?'}")
    return bool(new) and new != old


def maybe_refresh_stale(a) -> None:
    if _refresh_state["done"]:
        return
    age = ytdlp_age_days(ytdlp_version())
    if age is not None and age > STALE_DAYS:
        refresh_ytdlp(a, f"{age} days old")


def update() -> int:
    log("[update] python -m pip install -U \"yt-dlp[default]\" (includes yt-dlp-ejs for YouTube)")
    r = subprocess.run([sys.executable, "-m", "pip", "install", "-U", "--disable-pip-version-check",
                        "yt-dlp[default]"], env=child_env())
    v = subprocess.run(ytdlp_cmd() + ["--version"], capture_output=True, text=True)
    print(json.dumps({"ok": r.returncode == 0, "yt_dlp": v.stdout.strip()}, ensure_ascii=False))
    return r.returncode


# --------------------------------------------------------------------------- main

def parse_args(argv=None):
    ap = argparse.ArgumentParser(prog="grab.py", description="Download (almost) any video, best quality, reliably.",
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__.split("Examples:")[1])
    ap.add_argument("urls", nargs="*")
    ap.add_argument("--batch", help="text file with one URL per line (# comments allowed)")
    ap.add_argument("-o", "--out", default=os.environ.get("VG_OUT", str(DEFAULT_OUT)), help="output folder")
    ap.add_argument("--quality", default="best", choices=["best", "2160", "1440", "1080", "720", "480", "360"])
    ap.add_argument("--compat", action="store_true", help="prefer H.264/AAC in .mp4 (best for editors)")
    ap.add_argument("--audio-only", choices=["mp3", "m4a", "wav"])
    ap.add_argument("--subs", help="subtitle languages, e.g. ar,en (also auto-captions)")
    ap.add_argument("--section", help="download only a part, e.g. 00:01:00-00:02:30")
    ap.add_argument("--exact-cuts", action="store_true", help="re-encode at section cuts for frame-exact start")
    ap.add_argument("--playlist", action="store_true", help="download the whole playlist/channel")
    ap.add_argument("--limit", type=int, help="max playlist items")
    ap.add_argument("--proxy", default="auto", help="auto (direct first, rotate pool on 403/429/geo) | none | URL")
    ap.add_argument("--proxy-file", help="proxies.txt for the pool (default: proxy_pool decides)")
    ap.add_argument("--proxy-tries", type=int, default=3)
    ap.add_argument("--tor", action="store_true", help="add local Tor (socks5://127.0.0.1:9050) to the pool")
    ap.add_argument("--free-proxies", action="store_true", help="add public free proxies to the pool (slow, unsafe)")
    ap.add_argument("--browser-cookies", choices=["chrome", "edge", "firefox", "brave", "opera", "chromium", "vivaldi"])
    ap.add_argument("--cookies", help="Netscape cookies.txt")
    ap.add_argument("--no-browser", action="store_true", help="never use the ghost-browser sniff fallback")
    ap.add_argument("--sniff", action="store_true", help="skip yt-dlp, find the stream with the ghost browser first")
    ap.add_argument("--sniff-wait", type=int, default=15)
    ap.add_argument("--no-aria", action="store_true", help="do not use aria2c inside yt-dlp")
    ap.add_argument("--info-json", action="store_true", help="also write .info.json")
    ap.add_argument("--thumbnail", action="store_true", help="also write/embed thumbnail")
    ap.add_argument("--info", action="store_true", help="only show metadata, no download")
    ap.add_argument("--json", action="store_true", help="stdout carries only the JSON summary")
    ap.add_argument("--update", action="store_true", help="pip install -U yt-dlp and exit")
    ap.add_argument("--auto-update", action="store_true",
                    help="with the owner's yes: refresh yt-dlp when older than 30 days or once after a failure (off by default)")
    ap.add_argument("--no-auto-update", action="store_true", help="never refresh yt-dlp on its own (wins over --auto-update)")
    a = ap.parse_args(argv)
    if a.proxy == "none":
        a.proxy = "none"
    return a, ap


def main(argv=None) -> int:
    global QUIET
    a, ap = parse_args(argv)
    QUIET = a.json
    if a.update:
        return update()
    urls = list(a.urls)
    if a.batch:
        for line in Path(a.batch).read_text(encoding="utf-8-sig").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                urls.append(line)
    if not urls:
        ap.print_help(sys.stderr)
        return 2
    if a.info:
        res = [info_one(u, a) for u in urls]
        print(json.dumps({"ok": all(r["ok"] for r in res), "results": res}, ensure_ascii=False))
        return 0 if all(r["ok"] for r in res) else 1
    out = Path(a.out).expanduser()
    out.mkdir(parents=True, exist_ok=True)
    pool_holder: dict = {}
    results = []
    for u in urls:
        log(f"\n>> {u}")
        r = grab_one(u, a, out, pool_holder)
        results.append(r)
        if not a.json:
            if r["ok"]:
                for f in r["files"]:
                    print(f"OK [{r['method']}] {f['path']}  {f.get('width')}x{f.get('height')} "
                          f"{f.get('vcodec')}/{f.get('acodec')} {f.get('duration')}s {f.get('size_mb')}MB")
            else:
                print(f"FAILED [{r['status']}] {u}\n  {r['error']}\n  hint: {r['hint']}")
    summary = {"ok": all(r["ok"] for r in results), "out_dir": str(out),
               "done": sum(r["ok"] for r in results), "failed": sum(not r["ok"] for r in results),
               "results": results}
    print(json.dumps(summary, ensure_ascii=False))
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
