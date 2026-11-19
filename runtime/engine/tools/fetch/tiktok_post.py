#!/usr/bin/env python3
"""TikTok photo post -> its images and its sound, for the owner's own editing.

yt-dlp stops on photo posts ("Unsupported URL: https://www.tiktok.com/@user/photo/...").
The post page already carries the whole post as JSON in <script id="__UNIVERSAL_DATA_FOR_REHYDRATION__">.
This tool reads that block and downloads the image and sound links listed in it, the way a phone browser
opening the post would. Nothing is worked around: when TikTok answers with a login wall, a captcha or a
region block, the block is missing and the tool stops with a clear message.

    python tools/fetch/tiktok_post.py URL --out DIR [--no-images | --no-music] [--html SAVED_PAGE]

URL is a share link (https://vt.tiktok.com/XXXX/) or a post link (https://www.tiktok.com/@user/photo/ID).
DIR gets 00.jpg, 01.jpg ... in post order, music.mp3 and manifest.json. The extension follows the real
format when the CDN sends something else (.webp/.heic for a picture, .m4a/.aac for the sound).
Exit 0 when everything asked for was saved; 1 when the post could not be read or a file failed; 2 for
wrong arguments.

Python API:
    parse(html) -> {"id", "desc", "music": {"title", "author", "url"}, "images": [url, ...], "creator", "scope"}
    fetch(url, out_dir, images=True, music=True, html=None, opener=None) -> manifest dict
Both raise PostError when the page has no post data. Standard library only (Python 3.8+), any OS.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import gzip
import html as _html
import http.client
import http.cookiejar
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zlib
from pathlib import Path

SCRIPT_ID = "__UNIVERSAL_DATA_FOR_REHYDRATION__"
SCOPES = ("webapp.reflow.video.detail", "webapp.video-detail")  # phone page first, then the desktop page
# a stock iPhone Safari string: nothing about the owner, no cookies, no account
UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 "
      "(KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1")
NOTE = "for the owner personal editing; rights stay with the post creator"
SCHEMA = "dragon.tiktok_post.v1"
TIMEOUT = 30            # seconds per request
RETRY_PAUSE = 1.5       # seconds before the one retry of a cut or busy download
PAGE_CAP = 8 << 20
IMAGE_CAP = 60 << 20
MUSIC_CAP = 200 << 20
ACCEPT = {"page": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
          "image": "image/jpeg,image/png,image/*;q=0.8,*/*;q=0.5",
          "music": "audio/mpeg,audio/*;q=0.9,*/*;q=0.5"}
SCRIPT_RE = re.compile(r"<script\b[^>]*\bid\s*=\s*[\"']?%s(?=[\"'\s>])[^>]*>(.*?)</script\s*>" % SCRIPT_ID,
                       re.S | re.I)
NET_ERRORS = (urllib.error.URLError, http.client.HTTPException, OSError)  # refusals, resets, timeouts, short reads


class PostError(Exception):
    """The post cannot be read: the page was refused, or it has no post data (nothing is saved then)."""


class _FileError(Exception):
    """One image or sound link failed; `retry` marks a cut or busy connection worth one more try."""

    def __init__(self, msg, retry=False):
        super().__init__(msg)
        self.retry = retry


# ---------- reading the page ----------

def _dig(obj, *keys):
    """obj[k1][k2]... or None when a step is missing or has the wrong type."""
    for k in keys:
        if isinstance(obj, dict):
            obj = obj.get(k)
        elif isinstance(obj, list) and isinstance(k, int) and -len(obj) <= k < len(obj):
            obj = obj[k]
        else:
            return None
    return obj


def _text(*values):
    """The first non-empty string among values ('' when none)."""
    return next((v for v in values if isinstance(v, str) and v), "")


def _title(html):
    m = re.search(r"<title[^>]*>(.*?)</title", html or "", re.S | re.I)
    return " ".join(_html.unescape(m.group(1)).split())[:80] if m else ""


def page_data(html):
    """The JSON object inside <script id="__UNIVERSAL_DATA_FOR_REHYDRATION__">."""
    m = SCRIPT_RE.search(html or "")
    if not m:
        title = _title(html)
        raise PostError(
            f"no {SCRIPT_ID} data in the page ({len(html or '')} characters"
            + (f", title {title!r}" if title else "") + "). TikTok sent a login wall, a captcha or a region "
            "block instead of the post, or it changed its page. Open the link in a browser on the owner's "
            "computer, or ask for the images and the sound; this tool does not work around it.")
    try:
        data = json.loads(m.group(1))
    except ValueError as e:
        raise PostError(f"the {SCRIPT_ID} block is not valid JSON ({e}); TikTok may have changed its page") from None
    if not isinstance(data, dict):
        raise PostError(f"the {SCRIPT_ID} block is not a JSON object; TikTok may have changed its page")
    return data


def item_struct(data):
    """(scope name, itemStruct): the phone scope first, then the desktop scope."""
    scope = _dig(data, "__DEFAULT_SCOPE__")
    if not isinstance(scope, dict):
        raise PostError("the page data has no __DEFAULT_SCOPE__; TikTok may have changed its page")
    status = []
    for name in SCOPES:
        item = _dig(scope, name, "itemInfo", "itemStruct")
        if isinstance(item, dict) and item:
            return name, item
        code, msg = _dig(scope, name, "statusCode"), _dig(scope, name, "statusMsg")
        if code or msg:
            status.append(f"{name} says statusCode {code} {msg or ''}".rstrip())
    found = (", ".join(sorted(map(str, scope))) or "nothing")[:300]
    raise PostError("the page data has no post (looked in " + " and ".join(SCOPES) + f"; found {found})"
                    + ("; " + "; ".join(status) if status else "")
                    + ". The post may be private, removed or blocked in this region, or a login wall was served.")


def _links(node):
    """Links of a TikTok url node: a plain string, {"urlList": [...]} or {"url_list": [...]}."""
    if isinstance(node, str):
        return [node] if node.strip() else []
    lst = _dig(node, "urlList") or _dig(node, "url_list")
    return [u for u in lst if isinstance(u, str) and u.strip()] if isinstance(lst, list) else []


def _image_links(item):
    """Candidate links of every image, in post order (first = imageURL.urlList[0])."""
    imgs = _dig(item, "imagePost", "images")
    return [_links(_dig(img, "imageURL")) for img in imgs] if isinstance(imgs, list) else []


def _music_links(item):
    return _links(_dig(item, "music", "playUrl"))


def _summary(scope, item):
    music = _music_links(item)
    return {
        "id": str(_dig(item, "id") or ""),
        "desc": _text(_dig(item, "desc")),
        "music": {"title": _text(_dig(item, "music", "title")),
                  "author": _text(_dig(item, "music", "authorName"), _dig(item, "music", "author")),
                  "url": music[0] if music else ""},
        "images": [links[0] for links in _image_links(item) if links],
        "creator": _text(_dig(item, "author", "uniqueId")),  # the post creator's public handle, for credit
        "scope": scope,
    }


def parse(html):
    """Post facts from a TikTok post page. Raises PostError when the page has no post data.
    images = imageURL.urlList[0] of each picture; music.url = music.playUrl ('' when the page lists none)."""
    return _summary(*item_struct(page_data(html)))


# ---------- network ----------

def make_opener(proxies=None):
    """One urllib session with a cookie jar, like one browser tab (nothing is stored on disk).
    proxies=None: the system / environment proxy; {}: no proxy."""
    handlers = [urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())]
    if proxies is not None:
        handlers.append(urllib.request.ProxyHandler(proxies))
    return urllib.request.build_opener(*handlers)


def _web(url):
    """True for an http(s) link with a host. Links read from the page are opened only when this holds."""
    try:
        p = urllib.parse.urlsplit(url)
    except ValueError:
        return False
    return p.scheme in ("http", "https") and bool(p.netloc)


def _clean(url):
    """The link without query and fragment: resolved share links carry the sharer's account ids."""
    p = urllib.parse.urlsplit(url)
    return urllib.parse.urlunsplit((p.scheme, p.netloc, p.path, "", ""))


def _origin(url):
    p = urllib.parse.urlsplit(url)
    return f"{p.scheme}://{p.netloc}/"


def _headers(kind, user_agent, referer=None):
    h = {"User-Agent": user_agent, "Accept": ACCEPT[kind], "Accept-Language": "en-US,en;q=0.9"}
    if referer:
        h["Referer"] = referer
    return h


def _reason(e):
    """Plain words for a network error."""
    if isinstance(e, urllib.error.HTTPError):
        return f"HTTP {e.code} {e.reason}"
    text = str(getattr(e, "reason", None) or e) or type(e).__name__
    if "Tunnel connection failed" in text:
        text += " (this machine's network proxy does not allow that host)"
    return text


def get_page(url, opener=None, user_agent=UA):
    """GET the post page, following the short link. Returns (html, final_url)."""
    if not _web(url):
        raise PostError(f"not a web link: {url!r}")
    opener = opener or make_opener()
    host = urllib.parse.urlsplit(url).netloc
    req = urllib.request.Request(url, headers=_headers("page", user_agent))
    try:
        with opener.open(req, timeout=TIMEOUT) as r:
            raw, final = r.read(PAGE_CAP + 1), r.geturl()
            coding = (r.headers.get("Content-Encoding") or "").strip().lower()
            charset = r.headers.get_content_charset() or "utf-8"
    except urllib.error.HTTPError as e:
        hint = {403: "TikTok refused this machine (cloud machines are often blocked); run it on the owner's "
                     "computer or ask for the files",
                404: "no such post (removed, private or a wrong link)", 410: "the post was removed",
                429: "TikTok is rate-limiting this machine; try once more later"}.get(e.code, "")
        raise PostError(f"{host} answered HTTP {e.code} {e.reason}" + (f": {hint}" if hint else "")) from None
    except NET_ERRORS as e:
        raise PostError(f"could not reach {host}: {_reason(e)}") from None
    if len(raw) > PAGE_CAP:
        raise PostError(f"the page is bigger than {PAGE_CAP >> 20} MB: not a TikTok post page")
    try:
        if coding in ("gzip", "x-gzip"):
            raw = gzip.decompress(raw)
        elif coding == "deflate":
            try:
                raw = zlib.decompress(raw)
            except zlib.error:
                raw = zlib.decompress(raw, -zlib.MAX_WBITS)  # raw deflate without the zlib header
        elif coding not in ("", "identity"):
            raise PostError(f"the page came compressed as {coding!r}, which this tool cannot read")
    except (OSError, EOFError, zlib.error) as e:
        raise PostError(f"the page could not be decompressed ({coding}): {e}") from None
    try:
        return raw.decode(charset, errors="replace"), final
    except LookupError:  # unknown charset name in the header
        return raw.decode("utf-8", errors="replace"), final


# ---------- saving files ----------

def _sniff(head, kind):
    """File extension from the first bytes (None when unknown)."""
    if head[:3] == b"\xff\xd8\xff":
        return ".jpg"
    if head[:8] == b"\x89PNG\r\n\x1a\n":
        return ".png"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return ".webp"
    if head[4:8] == b"ftyp":
        if head[8:12] in (b"avif", b"avis"):
            return ".avif"
        return ".heic" if kind == "image" else ".m4a"
    if head[:3] == b"ID3":
        return ".mp3"
    if len(head) > 1 and head[0] == 0xFF and head[1] & 0xE0 == 0xE0:
        return ".aac" if head[1] & 0x06 == 0 else ".mp3"  # layer bits 00 = ADTS AAC, else MPEG audio
    if head[:4] == b"OggS":
        return ".ogg"
    return None


def _save_one(opener, url, out, stem, kind, cap, referer, user_agent):
    """Download one link into out/<stem><ext> (via a .part file). Returns the file name; raises _FileError."""
    req = urllib.request.Request(url, headers=_headers(kind, user_agent, referer))
    part = None
    try:
        with opener.open(req, timeout=TIMEOUT) as r:
            ctype = (r.headers.get("Content-Type") or "").lower()
            expected = (r.headers.get("Content-Length") or "").strip()
            head = r.read(64)
            if not head:
                raise _FileError("empty answer", retry=True)
            if ctype.startswith(("text/", "application/json")) or head.lstrip()[:1] in (b"<", b"{"):
                raise _FileError(f"got a web page ({ctype or 'no type'}) instead of the {kind}: "
                                 "the link expired or was blocked")
            ext = _sniff(head, kind) or (".jpg" if kind == "image" else ".mp3")
            part = out / f"{stem}{ext}.part"
            size = len(head)
            with open(part, "wb") as f:
                f.write(head)
                while True:
                    chunk = r.read(1 << 16)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > cap:
                        raise _FileError(f"bigger than {cap >> 20} MB, stopped")
                    f.write(chunk)
        if expected.isdigit() and int(expected) != size:
            raise _FileError(f"cut off at {size} of {expected} bytes", retry=True)
        final = out / f"{stem}{ext}"
        part.replace(final)
        part = None
        return final.name
    except urllib.error.HTTPError as e:
        raise _FileError(f"HTTP {e.code} {e.reason}", retry=e.code in (429, 500, 502, 503, 504)) from None
    except NET_ERRORS as e:
        raise _FileError(_reason(e), retry=True) from None
    finally:
        if part is not None and part.exists():
            part.unlink()


def _save(opener, links, out, stem, kind, cap, referer, user_agent):
    """Try each candidate link in turn (one more try after a cut or busy connection). Returns the file name."""
    errors = []
    for url in links:
        if not _web(url):
            errors.append(f"not a web link, not opened: {url[:60]}")
            continue
        for attempt in (1, 2):
            try:
                return _save_one(opener, url, out, stem, kind, cap, referer, user_agent)
            except _FileError as e:
                errors.append(str(e))
                if not e.retry or attempt == 2:
                    break
                time.sleep(RETRY_PAUSE)
    raise _FileError("; ".join(errors) or "no link in the page")


def fetch(url, out_dir, images=True, music=True, html=None, opener=None, user_agent=UA):
    """Save a TikTok photo post into out_dir: 00.jpg, 01.jpg ... (numbered by position in the post),
    music.mp3 and manifest.json. `html` is a saved copy of the page to read instead of downloading it.
    Returns the manifest. Raises PostError, before writing anything, when the page cannot be read."""
    if not _web(url):
        raise PostError(f"not a web link: {url!r}")
    opener = opener or make_opener()
    resolved = url
    if html is None:
        html, resolved = get_page(url, opener, user_agent)
    scope, item = item_struct(page_data(html))
    post = _summary(scope, item)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    referer = _origin(resolved)
    files, failed, skipped = [], [], []
    if images:
        links = _image_links(item)
        if not links:
            skipped.append("images: this post has none (a video post? yt-dlp saves videos)")
        for i, cand in enumerate(links):
            try:
                files.append(_save(opener, cand, out, f"{i:02d}", "image", IMAGE_CAP, referer, user_agent))
            except _FileError as e:
                failed.append(f"image {i:02d}: {e}")
    else:
        skipped.append("images: --no-images")
    if music:
        cand = _music_links(item)
        if not cand:
            skipped.append("music: the page lists no sound link (muted, or not offered in this region)")
        else:
            try:
                files.append(_save(opener, cand, out, "music", "music", MUSIC_CAP, referer, user_agent))
            except _FileError as e:
                failed.append(f"music: {e}")
    else:
        skipped.append("music: --no-music")
    manifest = {
        "schema": SCHEMA,
        "source_url": url,
        "resolved_url": _clean(resolved),
        "id": post["id"],
        "creator": post["creator"],
        "desc": post["desc"],
        "music_title": post["music"]["title"],
        "music_author": post["music"]["author"],
        "files": files,
        "failed": failed,
        "skipped": skipped,
        "fetched_at": _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "note": NOTE,
    }
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return manifest


# ---------- command line ----------

def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="tiktok_post.py",
        description="Save a TikTok photo post (its pictures and its sound) for the owner's own editing. "
                    "Use it when yt-dlp says 'Unsupported URL' for a /photo/ link.")
    ap.add_argument("url", help="share link (https://vt.tiktok.com/XXXX/) or post link (.../@user/photo/ID)")
    ap.add_argument("--out", required=True, help="folder for 00.jpg ..., music.mp3 and manifest.json")
    only = ap.add_mutually_exclusive_group()
    only.add_argument("--no-images", action="store_true", help="save only the sound")
    only.add_argument("--no-music", action="store_true", help="save only the pictures")
    ap.add_argument("--html", metavar="FILE", help="read this saved copy of the post page instead of downloading it")
    a = ap.parse_args(argv)
    try:
        page = Path(a.html).read_text(encoding="utf-8", errors="replace") if a.html else None
        m = fetch(a.url, a.out, images=not a.no_images, music=not a.no_music, html=page)
    except (PostError, OSError) as e:  # OSError: unreadable --html file or unwritable --out folder
        print(f"tiktok_post: {e}", file=sys.stderr)
        return 1
    out = Path(a.out)
    pics = [f for f in m["files"] if not f.startswith("music")]
    sound = [f for f in m["files"] if f.startswith("music")]
    print(f"saved {len(pics)} images" + (f" and {sound[0]}" if sound else "") + f" into {out}")
    print(f"post {m['id']} by @{m['creator'] or '?'}: {m['desc'][:160]}")
    if m["music_title"]:
        print(f"sound: {m['music_title']}" + (f" - {m['music_author']}" if m["music_author"] else ""))
    print(f"manifest: {out / 'manifest.json'}")
    for s in m["skipped"]:
        print(f"note: {s}", file=sys.stderr)
    for f in m["failed"]:
        print(f"failed: {f}", file=sys.stderr)
    if not m["files"]:
        print("tiktok_post: nothing was saved", file=sys.stderr)
    return 1 if (m["failed"] or not m["files"]) else 0


def _utf8_console():
    """Arabic captions must print on a Windows console or pipe too."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


if __name__ == "__main__":
    _utf8_console()
    sys.exit(main())
