"""Offline tests for ghost_browser.py: pure helpers + a real headless run against a local HTTP server.

    python -m pytest tests/browser -q
"""
import functools
import http.server
import sys
import threading
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import ghost_browser as gbm  # noqa: E402
from ghost_browser import GhostBrowser, classify, netscape_cookies, parse_dash, parse_hls, score_media  # noqa: E402

MASTER = """#EXTM3U
#EXT-X-STREAM-INF:BANDWIDTH=800000,RESOLUTION=640x360
low/index.m3u8
#EXT-X-STREAM-INF:AVERAGE-BANDWIDTH=4000000,BANDWIDTH=5000000,RESOLUTION=1920x1080
hi/index.m3u8
"""
MEDIA = """#EXTM3U
#EXT-X-TARGETDURATION:4
#EXT-X-KEY:METHOD=AES-128,URI="key.bin"
#EXTINF:4,
seg0.ts
#EXT-X-ENDLIST
"""
DRM_MPD = """<MPD type="static"><Period><AdaptationSet>
<ContentProtection schemeIdUri="urn:uuid:edef8ba9-79d6-4ace-a3c8-27dcd51d21ed"/>
<Representation height="1080" bandwidth="6000000"/><Representation height="720" bandwidth="3000000"/>
</AdaptationSet></Period></MPD>"""


@pytest.mark.parametrize("url,ct,kind", [
    ("https://x/a/master.m3u8?t=1", "", "hls"),
    ("https://x/manifest.mpd", "", "dash"),
    ("https://x/v.mp4", "", "mp4"),
    ("https://x/v.webm", "", "webm"),
    ("https://x/a.m4a", "", "audio"),
    ("https://x/seg_001.ts", "", "segment"),
    ("https://x/chunk-3.m4s", "", "segment"),
    ("https://x/getvideo?id=1", "video/mp4", "mp4"),
    ("https://x/pl", "application/vnd.apple.mpegurl", "hls"),
    ("https://x/page.html", "text/html", None),
    ("https://x/img.jpg", "image/jpeg", None),
])
def test_classify(url, ct, kind):
    assert classify(url, ct) == kind


def test_parse_hls_master_and_media():
    m = parse_hls(MASTER)
    assert m["master"] and m["variants"] == 2 and m["max_height"] == 1080 and m["max_bandwidth"] == 5000000
    md = parse_hls(MEDIA)
    assert not md["master"] and md["aes128"] and md["drm"] is None and md["live"] is False
    assert parse_hls('#EXTM3U\n#EXT-X-KEY:METHOD=SAMPLE-AES,KEYFORMAT="com.apple.streamingkeydelivery"\n')["drm"]


def test_parse_dash_drm():
    d = parse_dash(DRM_MPD)
    assert d["max_height"] == 1080 and d["drm"] == "Widevine" and d["live"] is False


def test_scoring_prefers_master_hd_firstparty():
    page = "https://site.example/watch"
    master = {"url": "https://cdn.site.example/m.m3u8", "kind": "hls", "master": True, "height": 1080}
    media_pl = {"url": "https://cdn.site.example/360.m3u8", "kind": "hls", "height": 360}
    mp4_small = {"url": "https://site.example/preview.mp4", "kind": "mp4", "size": 100_000}
    ad = {"url": "https://pubads.g.doubleclick.net/x.mp4", "kind": "mp4", "size": 9_000_000}
    scores = [score_media(x, page) for x in (master, media_pl, mp4_small, ad)]
    assert scores == sorted(scores, reverse=True)


def test_netscape_cookie_format():
    txt = netscape_cookies([
        {"name": "a", "value": "1", "domain": ".ex.com", "path": "/", "expires": 2000000000, "secure": True,
         "httpOnly": False},
        {"name": "b", "value": "2", "domain": "ex.com", "path": "/", "expires": -1, "secure": False, "httpOnly": True},
    ])
    lines = txt.splitlines()
    assert lines[0] == "# Netscape HTTP Cookie File"
    assert ".ex.com\tTRUE\t/\tTRUE\t2000000000\ta\t1" in lines
    assert "#HttpOnly_ex.com\tFALSE\t/\tFALSE\t0\tb\t2" in lines


# ------------------------------------------------------------------ local headless integration
PAGE = """<!doctype html><html><head><title>Local test</title>
<meta property="og:video" content="/og.mp4">
<script type="application/ld+json">{"@type":"VideoObject","contentUrl":"/ld.mp4"}</script>
</head><body><h1>Hello ghost</h1><a href="/other">other link</a>
<video id="v" controls muted><source src="/media/clip.mp4" type="video/mp4"></video>
<script>fetch('/hls/master.m3u8');</script></body></html>"""
CAPTCHA_PAGE = """<!doctype html><html><head><title>Just a moment...</title></head>
<body><div class="cf-turnstile"></div></body></html>"""


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        routes = {
            "/": ("text/html", PAGE.encode()),
            "/captcha": ("text/html", CAPTCHA_PAGE.encode()),
            "/hls/master.m3u8": ("application/vnd.apple.mpegurl", MASTER.encode()),
            "/media/clip.mp4": ("video/mp4", b"\x00" * 2048),
        }
        ct, body = routes.get(self.path, ("text/plain", b"nf"))
        self.send_response(200 if self.path in routes else 404)
        self.send_header("Content-Type", ct)
        self.send_header("Content-Length", str(len(body)))
        if self.path == "/":
            self.send_header("Set-Cookie", "sid=abc123; Path=/")
        self.end_headers()
        self.wfile.write(body)


@pytest.fixture(scope="module")
def server():
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


@pytest.fixture(scope="module")
def gb():
    with GhostBrowser(proxy=None, log=lambda m: None) as b:
        yield b


def test_sniff_local(server, gb, tmp_path):
    r = gb.sniff(server + "/", wait=6, cookies_path=str(tmp_path / "c.txt"))
    urls = {m["url"].replace(server, ""): m for m in r["media"]}
    assert "/hls/master.m3u8" in urls and urls["/hls/master.m3u8"]["master"] is True
    assert urls["/hls/master.m3u8"]["height"] == 1080
    assert "/media/clip.mp4" in urls and "/og.mp4" in urls and "/ld.mp4" in urls
    assert r["best"]["url"].endswith("/hls/master.m3u8")
    assert r["best"]["headers"]["User-Agent"] == r["user_agent"]
    assert "sid=abc123" in r["best"]["headers"].get("Cookie", "")
    assert r["captcha"] is False and r["drm"] is False
    assert r["proxy"] == gbm.DIRECT_LABEL
    assert "sid\tabc123" in Path(r["cookies_file"]).read_text(encoding="utf-8")
    assert "HeadlessChrome" not in r["user_agent"]


def test_webdriver_hidden_and_identity_consistent(server, gb):
    page = gb.context.new_page()
    page.goto(server + "/")
    assert page.evaluate("navigator.webdriver") is False
    lang = page.evaluate("navigator.language")
    tz = page.evaluate("Intl.DateTimeFormat().resolvedOptions().timeZone")
    page.close()
    assert lang == gb.identity["locale"] and tz == gb.identity["timezone_id"]
    assert gb.identity["accept_language"].startswith(gb.identity["locale"])


def test_captcha_detected_not_solved(server, gb):
    r = gb.sniff(server + "/captcha", wait=3)
    assert r["captcha"] is True
    assert any("not solved by design" in n for n in r["notes"])


def test_text_html_shot_cookies(server, gb, tmp_path):
    t = gb.fetch_text(server + "/")
    assert "Hello ghost" in t["text"] and any(l["href"].endswith("/other") for l in t["links"])
    assert "<h1>Hello ghost</h1>" in gb.get_html(server + "/")
    p = gb.screenshot(server + "/", str(tmp_path / "s.png"))
    assert Path(p).read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
    c = gb.export_cookies(str(tmp_path / "ck.txt"), url=server + "/")
    assert "abc123" in Path(c).read_text(encoding="utf-8")


def test_untrusted_proxy_blocks_cookie_export():
    b = GhostBrowser(proxy=gbm.Proxy.parse("1.2.3.4:80", source="free"), log=lambda m: None)
    assert b.cookies_allowed is False
