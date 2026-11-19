"""v1.2 TikTok photo posts: tools/fetch/tiktok_post.py reads the post JSON that yt-dlp cannot use
(yt-dlp: "Unsupported URL ... /photo/") and saves the pictures and the sound.
parse() runs on a synthetic page (fixtures/tiktok_photo_post.html) under both scope names and on broken pages;
fetch() and the CLI run against a loopback HTTP server that plays the short link, the post page and the CDN,
serving tiny media made with ffmpeg lavfi in tmp_path. No internet, no owner files."""
import importlib.util, json, os, subprocess, sys, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parent.parent            # app/
TOOL = ROOT.parent / "tools" / "fetch" / "tiktok_post.py"
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "tiktok_photo_post.html"
if not TOOL.exists():
    pytest.skip(f"{TOOL} is not in this copy (only app/ was copied)", allow_module_level=True)
sys.path.insert(0, str(ROOT))
from engines.media import exe, ffmpeg  # noqa: E402


def _load_tool():
    keep = sys.dont_write_bytecode
    sys.dont_write_bytecode = True        # no __pycache__ inside the skill's tools/fetch
    try:
        spec = importlib.util.spec_from_file_location("tiktok_post", TOOL)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    finally:
        sys.dont_write_bytecode = keep


tp = _load_tool()
PAGE = FIXTURE.read_text(encoding="utf-8")
REFLOW, DESKTOP = "webapp.reflow.video.detail", "webapp.video-detail"
POST_ID = "7300000000000000001"
POST_PATH = "/@example_creator/photo/" + POST_ID
MUSIC_PATH = "/music/obj/ies-music-example/7300000000000000002.mp3"
LOGIN = '<!DOCTYPE html><html><head><title>Log in | TikTok</title></head><body><div id="login"></div></body></html>'


def img_path(host, n):
    return f"/{host}/obj/photomode-example/img-{n:02d}~tplv-photomode-image.jpeg"


def page(data, title="TikTok"):
    """A minimal post page around a JSON object, escaped like TikTok ('/' as \\u002F)."""
    body = json.dumps(data, ensure_ascii=False).replace("/", "\\u002F")
    return (f'<!DOCTYPE html><html><head><meta charset="utf-8"><title>{title}</title></head><body>'
            f'<script id="{tp.SCRIPT_ID}" type="application/json">{body}</script></body></html>')


def fixture_data():
    return tp.page_data(PAGE)


def run_cli(*args):
    env = dict(os.environ, NO_PROXY="127.0.0.1,localhost", no_proxy="127.0.0.1,localhost")
    env.pop("PYTHONIOENCODING", None)      # the tool must set UTF-8 output itself (Arabic captions)
    return subprocess.run([sys.executable, "-B", str(TOOL), *map(str, args)], capture_output=True, text=True,
                          encoding="utf-8", env=env, timeout=60)


# ---------- parse ----------

def test_parse_phone_scope():
    p = tp.parse(PAGE)
    assert p["scope"] == REFLOW and p["id"] == POST_ID and p["creator"] == "example_creator"
    assert p["desc"] == "منشور صور تجريبي للاختبار #اختبار #test"
    assert p["music"] == {"title": "original sound - example_creator", "author": "Example Creator",
                          "url": "https://sf16-ies-music.tiktokcdn.com/obj/ies-music-example/7300000000000000002.mp3"}
    # imageURL.urlList[0] of each picture, in order, with / decoded
    assert p["images"] == ["https://p16-sign.tiktokcdn.com/obj/photomode-example/img-%02d~tplv-photomode-image.jpeg"
                           "?x-expires=1700000000&x-signature=AbC%%2Fd%d%%3D" % (n, n) for n in range(3)]


def test_parse_desktop_scope_gives_the_same_post():
    p = tp.parse(PAGE.replace(REFLOW, DESKTOP))
    assert p["scope"] == DESKTOP
    assert {k: v for k, v in p.items() if k != "scope"} == {k: v for k, v in tp.parse(PAGE).items() if k != "scope"}


def test_phone_scope_wins_and_desktop_scope_is_the_fallback():
    detail = fixture_data()["__DEFAULT_SCOPE__"][REFLOW]
    other = json.loads(json.dumps(detail))
    other["itemInfo"]["itemStruct"]["id"] = "999"
    assert tp.parse(page({"__DEFAULT_SCOPE__": {DESKTOP: other, REFLOW: detail}}))["id"] == POST_ID
    status_only = {"statusCode": 10204, "statusMsg": "item doesn't exist"}
    p = tp.parse(page({"__DEFAULT_SCOPE__": {REFLOW: status_only, DESKTOP: other}}))
    assert (p["id"], p["scope"]) == ("999", DESKTOP)


def test_video_post_has_no_images_but_keeps_the_sound():
    data = fixture_data()
    del data["__DEFAULT_SCOPE__"][REFLOW]["itemInfo"]["itemStruct"]["imagePost"]
    p = tp.parse(page(data))
    assert p["images"] == [] and p["music"]["url"].endswith("7300000000000000002.mp3")


def test_missing_script_tag_is_a_clear_error():
    with pytest.raises(tp.PostError) as e:
        tp.parse(LOGIN)
    msg = str(e.value)
    assert tp.SCRIPT_ID in msg and "login wall" in msg and "region block" in msg and "Log in | TikTok" in msg
    assert "does not work around it" in msg


def test_broken_data_and_missing_post_are_clear_errors():
    raw = f'<script id="{tp.SCRIPT_ID}" type="application/json">{{"__DEFAULT_SCOPE__": </script>'
    with pytest.raises(tp.PostError, match="not valid JSON"):
        tp.parse(raw)
    with pytest.raises(tp.PostError, match="no __DEFAULT_SCOPE__"):
        tp.parse(page({"something": 1}))
    private = {"__DEFAULT_SCOPE__": {"webapp.app-context": {}, REFLOW: {"statusCode": 10222, "statusMsg": "private"}}}
    with pytest.raises(tp.PostError) as e:
        tp.parse(page(private))
    assert "no post" in str(e.value) and "10222" in str(e.value) and "private" in str(e.value)


# ---------- command line without a server ----------

def test_cli_stops_on_a_login_wall_and_writes_nothing(tmp_path):
    saved = tmp_path / "login.html"
    saved.write_text(LOGIN, encoding="utf-8")
    out = tmp_path / "منشور"                      # Arabic folder name
    r = run_cli("https://vt.tiktok.com/ZSfake123/", "--out", out, "--html", saved)
    assert r.returncode == 1 and "login wall" in r.stderr and not out.exists()


def test_cli_rejects_both_skip_flags_and_non_web_links(tmp_path):
    r = run_cli("https://vt.tiktok.com/ZSfake123/", "--out", tmp_path / "o", "--no-images", "--no-music")
    assert r.returncode == 2 and "not allowed with" in r.stderr
    r = run_cli("file:///etc/passwd", "--out", tmp_path / "o")
    assert r.returncode == 1 and "not a web link" in r.stderr and not (tmp_path / "o").exists()


def test_links_from_the_page_are_never_opened_unless_web(tmp_path):
    secret = tmp_path / "secret.txt"
    secret.write_text("local file", encoding="utf-8")
    data = fixture_data()
    data["__DEFAULT_SCOPE__"][REFLOW]["itemInfo"]["itemStruct"]["imagePost"]["images"] = [
        {"imageURL": {"urlList": [secret.as_uri()]}}]
    out = tmp_path / "o"
    m = tp.fetch("https://vt.tiktok.com/ZSfake123/", out, music=False, html=page(data))
    assert m["files"] == [] and m["failed"][0].startswith("image 00: not a web link")
    assert sorted(p.name for p in out.iterdir()) == ["manifest.json"]


# ---------- fetch against a loopback server ----------

class Server:
    """127.0.0.1 server playing vt.tiktok.com (/ZSfake/ redirects), the post page and the CDN hosts
    (/p16 and /p19 for pictures, /music for the sound). `routes` maps a path (no query) to
    (status, content type, body) or to a callable taking the handler."""

    def __init__(self, media):
        self.media, self.hits, self.routes = media, [], {}
        srv = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                path = self.path.split("?")[0]
                srv.hits.append((path, self.headers.get("User-Agent"), self.headers.get("Referer")))
                route = srv.routes.get(path)
                if callable(route):
                    return route(self)
                if route is None:
                    return self.send_error(404)
                code, ctype, body = route
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.base = f"http://127.0.0.1:{self.httpd.server_address[1]}"
        esc = self.base.replace("/", "\\u002F")
        html = (PAGE.replace("https:\\u002F\\u002Fp16-sign.tiktokcdn.com", esc + "\\u002Fp16")
                .replace("https:\\u002F\\u002Fp19-sign.tiktokcdn.com", esc + "\\u002Fp19")
                .replace("https:\\u002F\\u002Fsf16-ies-music.tiktokcdn.com", esc + "\\u002Fmusic"))
        self.routes["/ZSfake/"] = self.redirect
        self.routes[POST_PATH] = (200, "text/html; charset=utf-8", html.encode("utf-8"))
        for n, key in enumerate("abc"):
            for host in ("p16", "p19"):
                self.routes[img_path(host, n)] = (200, "image/jpeg", media[key])
        self.routes[MUSIC_PATH] = (200, "audio/mpeg", media["m"])
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def redirect(self, h):
        # a share link resolves with the sharer's ids in the query; the manifest must drop them
        h.send_response(301)
        h.send_header("Location", POST_PATH + "?_r=1&u_code=SHARER123&share_app_id=1233")
        h.send_header("Content-Length", "0")
        h.end_headers()

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()


@pytest.fixture
def cdn(tmp_path):
    try:
        exe("ffmpeg")
    except FileNotFoundError:
        pytest.skip("ffmpeg not installed")
    media = {}
    for key, colour in (("a", "red"), ("b", "green"), ("c", "blue")):
        f = tmp_path / f"{key}.jpg"
        ffmpeg("-f", "lavfi", "-i", f"color=c={colour}:s=32x32", "-frames:v", "1", f)
        media[key] = f.read_bytes()
    snd = tmp_path / "m.mp3"
    try:
        ffmpeg("-f", "lavfi", "-i", "sine=f=440:d=1", "-c:a", "libmp3lame", "-b:a", "64k", snd)
    except RuntimeError:                         # no LAME: MPEG layer 2 is still MPEG audio (.mp3)
        ffmpeg("-f", "lavfi", "-i", "sine=f=440:d=1", "-c:a", "mp2", "-f", "mp2", snd)
    media["m"] = snd.read_bytes()
    server = Server(media)
    yield server
    server.close()


def test_fetch_follows_the_short_link_and_saves_the_post(cdn, tmp_path):
    cdn.routes[img_path("p16", 1)] = (404, "text/plain", b"gone")   # dead first link: urlList[1] is used
    out = tmp_path / "منشور تيك توك"
    m = tp.fetch(cdn.base + "/ZSfake/", out, opener=tp.make_opener(proxies={}))
    assert m["files"] == ["00.jpg", "01.jpg", "02.jpg", "music.mp3"]
    assert [(out / f).read_bytes() for f in m["files"]] == [cdn.media[k] for k in "abcm"]
    assert (m["failed"], m["skipped"]) == ([], [])
    assert m["source_url"] == cdn.base + "/ZSfake/"
    assert m["resolved_url"] == cdn.base + POST_PATH                     # no sharer ids
    assert (m["id"], m["creator"], m["music_title"]) == (POST_ID, "example_creator", "original sound - example_creator")
    assert m["note"] == "for the owner personal editing; rights stay with the post creator"
    disk = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert disk == m and disk["desc"].startswith("منشور صور تجريبي")
    assert sorted(p.name for p in out.iterdir()) == sorted(m["files"] + ["manifest.json"])  # no .part left
    paths = [h[0] for h in cdn.hits]
    assert paths[:2] == ["/ZSfake/", POST_PATH] and img_path("p19", 1) in paths and img_path("p19", 0) not in paths
    assert {h[1] for h in cdn.hits} == {tp.UA} and "iPhone" in tp.UA          # one generic phone browser
    assert all(h[2] == cdn.base + "/" for h in cdn.hits[2:])               # media asked with the page origin


def test_fetch_records_blocked_links_and_skips_music(cdn, tmp_path):
    cdn.routes[img_path("p16", 2)] = (200, "text/html", b"<html>Access denied</html>")  # a block page, not a picture
    cdn.routes[img_path("p19", 2)] = (403, "text/plain", b"forbidden")
    out = tmp_path / "o"
    m = tp.fetch(cdn.base + "/ZSfake/", out, music=False, opener=tp.make_opener(proxies={}))
    assert m["files"] == ["00.jpg", "01.jpg"] and m["skipped"] == ["music: --no-music"]
    assert len(m["failed"]) == 1 and m["failed"][0].startswith("image 02:")
    assert "web page" in m["failed"][0] and "HTTP 403" in m["failed"][0]
    assert sorted(p.name for p in out.iterdir()) == ["00.jpg", "01.jpg", "manifest.json"]
    assert not any(h[0].startswith("/music") for h in cdn.hits)


def test_fetch_retries_a_cut_download_then_uses_the_next_link(cdn, tmp_path, monkeypatch):
    monkeypatch.setattr(tp, "RETRY_PAUSE", 0)
    cut = []

    def short_body(h):                                 # promises 5000 bytes, sends 100, closes
        cut.append(1)
        h.send_response(200)
        h.send_header("Content-Type", "image/jpeg")
        h.send_header("Content-Length", "5000")
        h.end_headers()
        h.wfile.write(cdn.media["a"][:100])
    cdn.routes[img_path("p16", 0)] = short_body
    m = tp.fetch(cdn.base + "/ZSfake/", tmp_path / "o", music=False, opener=tp.make_opener(proxies={}))
    assert len(cut) == 2                               # first link tried twice
    assert m["files"] == ["00.jpg", "01.jpg", "02.jpg"] and m["failed"] == []
    assert (tmp_path / "o" / "00.jpg").read_bytes() == cdn.media["a"]


def test_gzip_page_is_read(cdn):
    import gzip
    body = gzip.compress(PAGE.encode("utf-8"))

    def gz(h):                                         # some CDNs compress even when not asked to
        h.send_response(200)
        h.send_header("Content-Type", "text/html; charset=utf-8")
        h.send_header("Content-Encoding", "gzip")
        h.send_header("Content-Length", str(len(body)))
        h.end_headers()
        h.wfile.write(body)
    cdn.routes[POST_PATH] = gz
    html, final = tp.get_page(cdn.base + "/ZSfake/", tp.make_opener(proxies={}))
    assert final.startswith(cdn.base + POST_PATH) and tp.parse(html)["id"] == POST_ID


@pytest.mark.parametrize("head, kind, ext", [
    (b"\xff\xd8\xff\xe0\x00\x10JFIF", "image", ".jpg"),
    (b"\x89PNG\r\n\x1a\n\x00\x00", "image", ".png"),
    (b"RIFF\x10\x00\x00\x00WEBPVP8 ", "image", ".webp"),
    (b"\x00\x00\x00\x18ftypheic\x00\x00", "image", ".heic"),
    (b"ID3\x04\x00\x00\x00\x00\x00\x00", "music", ".mp3"),
    (b"\xff\xfb\x90\x64\x00\x00", "music", ".mp3"),          # MPEG-1 layer III frame
    (b"\xff\xf1\x50\x80\x00\x1f", "music", ".aac"),          # ADTS AAC: must not be called .mp3
    (b"\x00\x00\x00\x20ftypM4A \x00\x00", "music", ".m4a"),
    (b"OggS\x00\x02\x00\x00", "music", ".ogg"),
    (b"\x00\x01\x02\x03", "music", None),
])
def test_saved_files_are_named_by_their_real_format(head, kind, ext):
    assert tp._sniff(head, kind) == ext


def test_cli_saves_the_post_and_reports_failures(cdn, tmp_path):
    out = tmp_path / "post"
    r = run_cli(cdn.base + "/ZSfake/", "--out", out, "--no-music")
    assert r.returncode == 0, r.stderr
    assert "saved 3 images into" in r.stdout and "منشور صور تجريبي" in r.stdout and "@example_creator" in r.stdout
    assert "note: music: --no-music" in r.stderr
    assert sorted(p.name for p in out.iterdir()) == ["00.jpg", "01.jpg", "02.jpg", "manifest.json"]
    cdn.routes[MUSIC_PATH] = (404, "text/plain", b"gone")
    r = run_cli(cdn.base + "/ZSfake/", "--out", tmp_path / "sound", "--no-images")
    assert r.returncode == 1 and "failed: music: HTTP 404" in r.stderr and "nothing was saved" in r.stderr
