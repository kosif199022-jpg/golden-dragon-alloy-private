"""Offline unit tests for scripts/grab.py (no network). Run:  python -m pytest tests/grab -q
Live downloads: set VG_LIVE=1 and run tests/grab/live_grab.py.
"""
import sys
import types
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import grab  # noqa: E402


def args(*extra):
    a, _ = grab.parse_args(["http://x", *extra])
    return a


# ---------------------------------------------------------------- helpers
def test_safe_name_keeps_arabic_and_strips_windows_chars():
    assert grab.safe_name('فيديو: "تجربة" <1>?') == "فيديو_ _تجربة_ _1__"
    assert grab.safe_name("CON") == "_CON"
    assert grab.safe_name("  ...  ") == "video"
    assert grab.safe_name("a‮b") == "ab"


def test_parse_section():
    assert grab.parse_section("00:01:00-00:02:30") == ("00:01:00", "00:02:30")
    assert grab.parse_section("10-") == ("10", "inf")
    assert grab.parse_section(None) is None
    with pytest.raises(SystemExit):
        grab.parse_section("abc")
    assert grab._secs("01:02:03") == 3723 and grab._secs("inf") == float("inf")


@pytest.mark.parametrize("text,kind", [
    ("ERROR: [youtube] x: This video is DRM protected", "drm"),
    ("ERROR: [youtube] x: Private video. Sign in if you've been granted access", "private"),
    ("ERROR: [youtube] x: This video is unavailable", "removed"),
    ("ERROR: The uploader has not made this video available in your country", "geo_blocked"),
    ("ERROR: [youtube] x: Sign in to confirm you're not a bot. Use --cookies-from-browser", "login_required"),
    ("ERROR: unable to download video data: HTTP Error 403: Forbidden", "forbidden"),
    ("ERROR: HTTP Error 429: Too Many Requests", "rate_limited"),
    ("ERROR: Unsupported URL: https://example.com/page", "unsupported"),
    ("[tls @ 0x1] Peer certificate failed verification\nERROR: ffmpeg exited with code 1", "tls"),
    ("ERROR: something odd", "failed"),
])
def test_classify(text, kind):
    assert grab.classify(text) == kind


# ---------------------------------------------------------------- yt-dlp command
def test_build_ytdlp_best_quality(tmp_path):
    cmd = grab.build_ytdlp("http://v", args(), tmp_path, None, True, tmp_path / "l.txt")
    s = " ".join(cmd)
    assert "-f bv*+ba/b" in s and "--merge-output-format mp4/mkv" in s
    assert "--windows-filenames" in s and "--no-playlist" in s and "-N 8" in s
    assert cmd[-2:] == ["--", "http://v"]


def test_build_ytdlp_compat_quality_subs_section_proxy(tmp_path):
    a = args("--quality", "1080", "--compat", "--subs", "ar,en", "--section", "1:00-2:00", "--proxy", "http://p:1")
    cmd = grab.build_ytdlp("http://v", a, tmp_path, "http://p:1", True, tmp_path / "l.txt")
    s = " ".join(cmd)
    assert "-S res:1080,vcodec:h264,acodec:m4a" in s and "--merge-output-format mp4" in s
    assert "--sub-langs ar,en" in s and "--embed-subs" in s
    assert "--download-sections *1:00-2:00" in s
    assert "--proxy http://p:1" in s
    assert "--downloader" not in cmd  # sections use ffmpeg, not aria2c


def test_build_ytdlp_audio_playlist_cookies_headers(tmp_path):
    a = args("--audio-only", "mp3", "--playlist", "--limit", "5", "--browser-cookies", "edge")
    cmd = grab.build_ytdlp("http://v", a, tmp_path, None, False, tmp_path / "l.txt",
                           headers={"Referer": "http://page"})
    s = " ".join(cmd)
    assert "-x --audio-format mp3" in s and "-I :5" in s and "--yes-playlist" in s
    assert "--cookies-from-browser edge" in s and "--add-headers Referer:http://page" in s


# ---------------------------------------------------------------- pipeline (mocked)
def _fake_file(tmp_path, name="v.mp4"):
    f = tmp_path / name
    f.write_bytes(b"x")
    return f


@pytest.fixture
def no_probe(monkeypatch):
    monkeypatch.setattr(grab, "probe_direct", lambda *a, **k: False)
    monkeypatch.setattr(grab, "ffprobe", lambda p: {"path": str(p), "verified": True, "has_audio": True})


def test_pipeline_proxy_rotation_with_proxy_objects(tmp_path, monkeypatch, no_probe):
    """pool.next() returns Proxy objects (helper-6 API); grab must pass .url to yt-dlp and mark_bad the object."""
    calls = []
    f = _fake_file(tmp_path)

    def fake_try(url, a, out, proxy, **kw):
        calls.append(proxy)
        if proxy is None:
            return {"kind": "forbidden", "files": [], "error": "HTTP Error 403"}
        if proxy == "http://bad:1":
            return {"kind": "rate_limited", "files": [], "error": "429"}
        return {"kind": "ok", "files": [f], "error": ""}

    class P:
        def __init__(self, u):
            self.url = u

    marked = []

    class Pool:
        items = [P("http://bad:1"), P("http://good:2")]

        def next(self):
            return self.items.pop(0) if self.items else None

        def mark_bad(self, p, reason=""):
            marked.append(p.url)

    monkeypatch.setattr(grab, "try_ytdlp", fake_try)
    monkeypatch.setattr(grab, "load_pool", lambda a: Pool())
    r = grab.grab_one("http://site/v", args(), tmp_path, {})
    assert r["ok"] and r["method"] == "yt-dlp+proxy"
    assert calls == [None, "http://bad:1", "http://good:2"]
    assert marked == ["http://bad:1"]
    assert "sources.txt" in [p.name for p in tmp_path.iterdir()]


def test_pipeline_terminal_drm_stops(tmp_path, monkeypatch, no_probe):
    monkeypatch.setattr(grab, "try_ytdlp", lambda *a, **k: {"kind": "drm", "files": [], "error": "DRM"})
    monkeypatch.setattr(grab, "sniff", lambda *a, **k: pytest.fail("must not sniff DRM"))
    r = grab.grab_one("http://site/v", args(), tmp_path, {})
    assert not r["ok"] and r["status"] == "drm" and "DRM" in r["hint"]


def test_pipeline_sniff_fallback_with_fake_ghost_browser(tmp_path, monkeypatch, no_probe):
    f = _fake_file(tmp_path, "HTML Video.mp4")

    class GB:
        def __init__(self, proxy=None):
            self.proxy = proxy

        def __enter__(self):
            return self

        def __exit__(self, *e):
            return False

        def sniff(self, url, wait=15):
            m = {"url": "http://cdn/v.mp4", "kind": "mp4", "headers": {"Referer": url, "User-Agent": "UA"}, "score": 9}
            return {"final_url": url, "title": "HTML Video", "media": [m], "best": m, "cookies_file": None,
                    "user_agent": "UA", "proxy": None, "captcha": False, "drm": False, "notes": []}

    monkeypatch.setitem(sys.modules, "ghost_browser", types.SimpleNamespace(GhostBrowser=GB))
    monkeypatch.setattr(grab, "try_ytdlp", lambda *a, **k: {"kind": "unsupported", "files": [], "error": "Unsupported URL"})
    seen = {}

    def fake_aria(url, out, headers=None, proxy=None, cookies_file=None, name=None):
        seen.update(url=url, headers=headers, name=name)
        return {"kind": "ok", "files": [f], "error": ""}

    monkeypatch.setattr(grab, "direct_aria", fake_aria)
    r = grab.grab_one("http://page", args("--proxy", "none"), tmp_path, {})
    assert r["ok"] and r["method"] == "sniff+aria2c"
    assert seen["url"] == "http://cdn/v.mp4" and seen["headers"]["Referer"] == "http://page"
    assert seen["name"] == "HTML Video.mp4"


def test_pipeline_sniff_reports_drm_and_captcha(tmp_path, monkeypatch, no_probe):
    monkeypatch.setattr(grab, "try_ytdlp", lambda *a, **k: {"kind": "unsupported", "files": [], "error": "x"})
    monkeypatch.setattr(grab, "sniff", lambda *a, **k: {"media": [], "drm": True, "captcha": False})
    assert grab.grab_one("http://p", args(), tmp_path, {})["status"] == "drm"
    monkeypatch.setattr(grab, "sniff", lambda *a, **k: {"media": [], "drm": False, "captcha": True})
    assert grab.grab_one("http://p", args(), tmp_path, {})["status"] == "captcha"


def test_no_browser_flag_skips_sniff(tmp_path, monkeypatch, no_probe):
    monkeypatch.setattr(grab, "try_ytdlp", lambda *a, **k: {"kind": "unsupported", "files": [], "error": "x"})
    monkeypatch.setattr(grab, "sniff", lambda *a, **k: pytest.fail("sniff called"))
    r = grab.grab_one("http://p", args("--no-browser"), tmp_path, {})
    assert r["status"] == "unsupported" and "ghost-browser" in r["hint"]


def test_real_helper6_modules_import():
    """Contract check against helper-6's real files (skipped if absent)."""
    pp = pytest.importorskip("proxy_pool")
    gbm = pytest.importorskip("ghost_browser")
    assert hasattr(pp.ProxyPool, "from_sources") and hasattr(pp.ProxyPool, "next") and hasattr(pp.ProxyPool, "mark_bad")
    assert hasattr(gbm.GhostBrowser, "sniff")
    pool = pp.ProxyPool.from_sources(file=str(SCRIPTS / "__nonexistent__.txt"), env=False, tor=False, free=False, check=False)
    assert pool.next() is None  # empty pool -> direct
