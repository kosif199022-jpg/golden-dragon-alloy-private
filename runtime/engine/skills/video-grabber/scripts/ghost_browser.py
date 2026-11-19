#!/usr/bin/env python3
"""ghost_browser.py - headless browser for legitimate media retrieval and page reading.

What it does
  * opens JS-heavy pages in headless Chromium (installed Chrome preferred, bundled fallback)
  * sniffs network + DOM for real media URLs (HLS/DASH/MP4/WebM/audio), groups segments,
    reads <video>/<source>, og:video, JSON-LD contentUrl, recurses into embed iframes
  * exports cookies in Netscape format for yt-dlp (--cookies)
  * reads page text + links, takes screenshots, returns HTML
  * rotates identity per session (UA/viewport/locale/timezone/Accept-Language kept consistent)
    and egress IP via proxy_pool (retry with next proxy on timeout/403/429/connection error)

What it does NOT do (by design)
  * no CAPTCHA solving, no login brute forcing, no paywall/DRM circumvention.
    CAPTCHA / bot-challenge pages and DRM (EME/Widevine/PlayReady/FairPlay) are DETECTED and
    REPORTED (result["captcha"], result["drm"], notes) and the caller should stop there.

Importable:
    from ghost_browser import GhostBrowser
    with GhostBrowser(proxy="auto") as gb:          # None/"none" = direct, "auto" = pool, or URL
        r = gb.sniff("https://example.com/video")   # dict, see sniff() docstring
        r["best"]["url"], r["best"]["headers"], r["cookies_file"]

CLI:
    python ghost_browser.py sniff URL [--proxy auto|URL|none] [--wait 20] [--json] [--headful]
    python ghost_browser.py text URL [--json]
    python ghost_browser.py shot URL out.png [--viewport-only]
    python ghost_browser.py cookies URL out.txt
    python ghost_browser.py html URL [out.html]
"""
from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
import time
from pathlib import Path
from typing import Any, Callable, Optional
from urllib.parse import urljoin, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))
from proxy_pool import DIRECT_LABEL, Proxy, ProxyPool, describe  # noqa: E402

from playwright.sync_api import Error as PWError  # noqa: E402
from playwright.sync_api import TimeoutError as PWTimeout  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

HOME = Path(os.environ.get("USERPROFILE") or Path.home())
COOKIE_DIR = HOME / ".video-grabber" / "cache" / "cookies"

# ----------------------------------------------------------------------------- identities
# Each profile is internally consistent: locale <-> Accept-Language <-> timezone.
# The UA is built from the real browser major version so UA and engine never disagree.
# We stay on the real host OS (Windows) to avoid platform mismatches.
LOCALE_PROFILES = [
    {"locale": "en-US", "accept_language": "en-US,en;q=0.9", "timezone_id": "America/New_York"},
    {"locale": "en-US", "accept_language": "en-US,en;q=0.9", "timezone_id": "America/Chicago"},
    {"locale": "en-US", "accept_language": "en-US,en;q=0.9", "timezone_id": "America/Los_Angeles"},
    {"locale": "en-GB", "accept_language": "en-GB,en;q=0.9", "timezone_id": "Europe/London"},
    {"locale": "de-DE", "accept_language": "de-DE,de;q=0.9,en;q=0.8", "timezone_id": "Europe/Berlin"},
    {"locale": "fr-FR", "accept_language": "fr-FR,fr;q=0.9,en;q=0.8", "timezone_id": "Europe/Paris"},
    {"locale": "ar-EG", "accept_language": "ar-EG,ar;q=0.9,en;q=0.8", "timezone_id": "Africa/Cairo"},
]
VIEWPORTS = [(1920, 1080), (1536, 864), (1440, 900), (1366, 768), (1600, 900), (1280, 800)]
DEFAULT_IDENTITY = {**LOCALE_PROFILES[0], "viewport": (1920, 1080)}

STEALTH_JS = """
Object.defineProperty(Navigator.prototype, 'webdriver', {get: () => false, configurable: true});
"""

# Records EME (DRM) usage so we can report it. Does NOT interfere with it.
EME_PROBE_JS = """
(() => {
  window.__vg_eme = [];
  const log = s => { try { window.__vg_eme.push(s); } catch (e) {} };
  const orig = navigator.requestMediaKeySystemAccess;
  if (orig) {
    navigator.requestMediaKeySystemAccess = function(ks, cfg) {
      log('probe:' + ks);
      return orig.apply(this, arguments).then(acc => {
        try {
          const cmk = acc.createMediaKeys.bind(acc);
          acc.createMediaKeys = () => { log('keys:' + ks); return cmk(); };
        } catch (e) {}
        return acc;
      });
    };
  }
  const sm = window.HTMLMediaElement && HTMLMediaElement.prototype.setMediaKeys;
  if (sm) {
    HTMLMediaElement.prototype.setMediaKeys = function(mk) {
      if (mk) log('active');
      return sm.apply(this, arguments);
    };
  }
})();
"""

DOM_SCAN_JS = r"""
() => {
  const out = {media: [], iframes: [], blob: false, jsonld: [], meta: [], players: []};
  const abs = u => { try { return new URL(u, location.href).href } catch (e) { return null } };
  document.querySelectorAll('video, audio').forEach(v => {
    const tag = v.tagName.toLowerCase();
    [v.currentSrc, v.src, v.getAttribute('src'), v.getAttribute('data-src')].forEach(s => {
      if (!s) return;
      if (s.startsWith('blob:')) { out.blob = true; return; }
      const a = abs(s); if (a) out.media.push({url: a, via: tag + '@src', type: v.getAttribute('type') || '',
        width: v.videoWidth || 0, height: v.videoHeight || 0});
    });
    v.querySelectorAll('source').forEach(s => {
      const u = s.getAttribute('src') || s.getAttribute('data-src'); if (!u) return;
      if (u.startsWith('blob:')) { out.blob = true; return; }
      const a = abs(u); if (a) out.media.push({url: a, via: tag + '>source', type: s.getAttribute('type') || '',
        label: s.getAttribute('label') || s.getAttribute('size') || s.getAttribute('res') || ''});
    });
  });
  ['og:video', 'og:video:url', 'og:video:secure_url', 'og:audio', 'twitter:player:stream'].forEach(p => {
    document.querySelectorAll(`meta[property="${p}"], meta[name="${p}"]`).forEach(m => {
      const a = abs(m.content); if (a) out.meta.push({url: a, via: 'meta:' + p});
    });
  });
  const walk = (o) => {
    if (!o || typeof o !== 'object') return;
    if (Array.isArray(o)) return o.forEach(walk);
    if (o.contentUrl) out.jsonld.push({url: abs(o.contentUrl), via: 'jsonld:contentUrl'});
    if (o.embedUrl) out.jsonld.push({url: abs(o.embedUrl), via: 'jsonld:embedUrl', embed: true});
    Object.values(o).forEach(v => { if (v && typeof v === 'object') walk(v); });
  };
  document.querySelectorAll('script[type="application/ld+json"]').forEach(s => {
    try { walk(JSON.parse(s.textContent)); } catch (e) {}
  });
  document.querySelectorAll('a[href]').forEach(a => {
    const h = a.href || '';
    if (/\.(m3u8|mpd|mp4|m4v|webm|mov|mp3|m4a|ogg|ogv|opus|flac|wav)(\?|#|$)/i.test(h))
      out.media.push({url: h, via: 'a@href', label: (a.innerText || '').trim().slice(0, 120)});
  });
  document.querySelectorAll('iframe').forEach(f => {
    const u = f.src || f.getAttribute('data-src'); if (u && !u.startsWith('about:')) out.iframes.push(abs(u));
  });
  return out;
}
"""

PLAY_SELECTORS = [
    ".vjs-big-play-button", ".ytp-large-play-button", ".plyr__control--overlaid", ".jw-icon-playback",
    ".jw-display-icon-container", "button[aria-label*='play' i]", "[role=button][aria-label*='play' i]",
    "button[title*='play' i]", ".play-button", ".playButton", ".bmpui-ui-hugeplaybacktogglebutton",
    "[data-testid*='play' i]", "[class*='PlayButton']", "[class*='play-btn']",
]

CAPTCHA_PATTERNS = [
    r"google\.com/recaptcha", r"recaptcha/api", r"hcaptcha\.com", r"challenges\.cloudflare\.com",
    r"/cdn-cgi/challenge-platform", r"arkoselabs\.com", r"funcaptcha", r"geo\.captcha-delivery\.com",
    r"perimeterx", r"px-captcha",
]
CAPTCHA_TITLES = re.compile(r"just a moment|attention required|verify (you are|that you are) (a )?human|"
                            r"are you a robot|security check|captcha|access denied", re.I)
LICENSE_PATTERNS = re.compile(r"widevine|playready|fairplay|/license|drm[-_/]?(proxy|license)|"
                              r"lic\.(drm|staging)|wvproxy|getlicense|/acquirelicense", re.I)

AD_HOSTS = re.compile(r"doubleclick|googlesyndication|googleads|imasdk|adservice|/ads?/|adsystem|"
                      r"moatads|innovid|spotx|springserve|preroll|/vast|freewheel|tremorhub|viously|teads\.|"
                      r"connatix|primis|aniview|vidazoo|outbrain|taboola|adnxs|smartadserver", re.I)
EMBED_HOSTS = re.compile(r"player\.vimeo\.com|dailymotion\.com/(embed|player)|geo\.dailymotion\.com|"
                         r"youtube(-nocookie)?\.com/embed|jwplayer|jwplatform|brightcove|players\.brightcove|"
                         r"kaltura|wistia|vidyard|streamable\.com/[eo]/|ok\.ru/videoembed|rumble\.com/embed|"
                         r"bitchute\.com/embed|facebook\.com/plugins/video|player\.|/embed/|/player/", re.I)

MEDIA_EXT = {
    ".m3u8": "hls", ".m3u": "hls", ".mpd": "dash", ".mp4": "mp4", ".m4v": "mp4", ".mov": "mp4",
    ".webm": "webm", ".mkv": "other", ".flv": "other", ".mp3": "audio", ".m4a": "audio",
    ".aac": "audio", ".ogg": "audio", ".ogv": "other", ".oga": "audio", ".opus": "audio", ".wav": "audio", ".flac": "audio",
}
SEGMENT_EXT = {".ts", ".m4s", ".m4f", ".cmfv", ".cmfa", ".aac_seg", ".fmp4"}
CT_KIND = [
    (re.compile(r"mpegurl", re.I), "hls"),
    (re.compile(r"dash\+xml", re.I), "dash"),
    (re.compile(r"video/mp4|video/quicktime|video/x-m4v", re.I), "mp4"),
    (re.compile(r"video/webm", re.I), "webm"),
    (re.compile(r"audio/", re.I), "audio"),
    (re.compile(r"video/mp2t|video/iso\.segment|audio/iso\.segment", re.I), "segment"),
    (re.compile(r"video/", re.I), "other"),
]


class RetryableError(Exception):
    """Raised for conditions where trying another proxy/identity may help."""


class GhostError(Exception):
    pass


# ----------------------------------------------------------------------------- helpers
def classify(url: str, content_type: str = "") -> Optional[str]:
    """Return hls|dash|mp4|webm|audio|other|segment or None if not media."""
    ct = (content_type or "").split(";")[0].strip().lower()
    path = urlsplit(url).path.lower()
    ext = os.path.splitext(path)[1]
    if ext in SEGMENT_EXT:
        return "segment"
    if ext in MEDIA_EXT:
        k = MEDIA_EXT[ext]
        # init segments / fragmented chunks with mp4 ext but segment-ish path
        if k in ("mp4", "audio") and re.search(r"(/|_|-)(seg|segment|frag|chunk|init)[-_]?\d*", path):
            return "segment"
        return k
    for rx, kind in CT_KIND:
        if rx.search(ct):
            return kind
    if re.search(r"(format=m3u8|/hls/|\bm3u8\b)", url, re.I) and "mpegurl" in ct:
        return "hls"
    return None


def parse_hls(text: str) -> dict:
    info = {"master": False, "variants": 0, "max_height": 0, "max_bandwidth": 0, "drm": None,
            "aes128": False, "live": None}
    if "#EXTM3U" not in text[:2000]:
        return info
    for m in re.finditer(r"#EXT-X-STREAM-INF:([^\n]*)", text):
        info["master"] = True
        info["variants"] += 1
        attrs = m.group(1)
        r = re.search(r"RESOLUTION=(\d+)x(\d+)", attrs)
        if r:
            info["max_height"] = max(info["max_height"], int(r.group(2)))
        b = re.search(r"(?<!AVERAGE-)BANDWIDTH=(\d+)", attrs)
        if b:
            info["max_bandwidth"] = max(info["max_bandwidth"], int(b.group(1)))
    for m in re.finditer(r"#EXT-X-(?:SESSION-)?KEY:([^\n]*)", text):
        attrs = m.group(1)
        if "METHOD=NONE" in attrs:
            continue
        if "METHOD=AES-128" in attrs and "KEYFORMAT" not in attrs:
            info["aes128"] = True
        elif re.search(r"SAMPLE-AES|KEYFORMAT=\"(urn:uuid:edef8ba9|com\.apple\.streamingkeydelivery|"
                       r"com\.microsoft\.playready|com\.widevine)", attrs, re.I):
            info["drm"] = "widevine/fairplay/playready (HLS SAMPLE-AES)"
    if not info["master"]:
        info["live"] = "#EXT-X-ENDLIST" not in text
    return info


def parse_dash(text: str) -> dict:
    info = {"max_height": 0, "max_bandwidth": 0, "drm": None, "live": None}
    for h in re.findall(r'\bheight="(\d+)"', text):
        info["max_height"] = max(info["max_height"], int(h))
    for b in re.findall(r'\bbandwidth="(\d+)"', text):
        info["max_bandwidth"] = max(info["max_bandwidth"], int(b))
    if re.search(r"<ContentProtection", text, re.I):
        schemes = re.findall(r'schemeIdUri="urn:uuid:([0-9a-f-]+)"', text, re.I)
        known = {"edef8ba9": "Widevine", "9a04f079": "PlayReady", "94ce86fb": "FairPlay", "e2719d58": "ClearKey"}
        names = sorted({known.get(s[:8].lower(), s) for s in schemes}) or ["CENC"]
        info["drm"] = ", ".join(names)
    info["live"] = 'type="dynamic"' in text
    return info


def height_from_url(url: str) -> int:
    m = re.findall(r"(?<![0-9])(2160|1440|1080|720|540|480|360|240|144)p?(?![0-9])", url)
    return max(int(x) for x in m) if m else 0


def _site(url: str) -> str:
    host = (urlsplit(url).hostname or "").lower()
    parts = host.split(".")
    n = 3 if len(parts) > 2 and len(parts[-2]) <= 3 and len(parts[-1]) == 2 else 2  # e.g. bbc.co.uk
    return ".".join(parts[-n:])


def score_media(m: dict, page_url: Optional[str] = None) -> int:
    kind = m["kind"]
    s = {"hls": 60, "dash": 55, "mp4": 50, "webm": 45, "audio": 20, "other": 10}.get(kind, 0)
    if m.get("master"):
        s += 40
    if kind == "dash":
        s += 30
    h = m.get("height") or 0
    s += min(h, 2160) // 36  # up to +60
    size = m.get("size") or 0
    if kind in ("mp4", "webm"):
        if size and size < 300_000:
            s -= 30  # tiny file: thumbnail/preview/ad
        elif size > 5_000_000:
            s += 10
    if m.get("drm"):
        s -= 50
    if AD_HOSTS.search(m["url"]):
        s -= 80
    if m.get("source") == "network":
        s += 5
    if str(m.get("via", "")).startswith("video"):
        s += 15  # referenced by a real <video> element on the page
    if page_url and _site(m["url"]) == _site(page_url):
        s += 20  # first-party media beats third-party widgets
    return s


def netscape_cookies(cookies: list[dict]) -> str:
    lines = ["# Netscape HTTP Cookie File", "# Generated by video-grabber ghost_browser.py", ""]
    for c in cookies:
        domain = c.get("domain", "")
        include_sub = "TRUE" if domain.startswith(".") else "FALSE"
        exp = c.get("expires", -1)
        exp = int(exp) if exp and exp > 0 else 0
        name = c.get("name", "")
        if c.get("httpOnly"):
            domain = "#HttpOnly_" + domain
        lines.append("\t".join([domain, include_sub, c.get("path", "/") or "/",
                                "TRUE" if c.get("secure") else "FALSE", str(exp), name, c.get("value", "")]))
    return "\n".join(lines) + "\n"


def _host(url: str) -> str:
    return (urlsplit(url).hostname or "page").replace(":", "_")


def _is_retryable_error(e: Exception) -> bool:
    msg = str(e)
    return isinstance(e, (PWTimeout, RetryableError)) or any(k in msg for k in (
        "net::ERR_PROXY", "net::ERR_TUNNEL", "net::ERR_CONNECTION", "net::ERR_TIMED_OUT",
        "net::ERR_EMPTY_RESPONSE", "net::ERR_SOCKS", "net::ERR_NAME_NOT_RESOLVED",
        "net::ERR_SSL", "net::ERR_HTTP2", "net::ERR_ADDRESS_UNREACHABLE", "Timeout"))


# ----------------------------------------------------------------------------- browser
class GhostBrowser:
    """Headless Chromium session. Use as a context manager.

    proxy:   None / "none" -> direct; "auto" -> ProxyPool.from_sources(); "scheme://..." -> that proxy;
             a Proxy or ProxyPool object is accepted too.
    rotate_identity: random consistent UA/viewport/locale/timezone per context (True) or a fixed one.
    profile_dir: persistent profile dir (keeps cookies/logins you made yourself in --headful mode).
             Disables per-retry context rotation and refuses untrusted (free) proxies.
    retries: extra attempts with the next proxy/identity on timeout, 403/429 or connection errors.
    """

    def __init__(self, proxy: Any = None, headless: bool = True, rotate_identity: bool = True,
                 profile_dir: Optional[str] = None, retries: int = 2, nav_timeout: float = 45.0,
                 cookies_dir: Optional[str] = None, pool_kwargs: Optional[dict] = None,
                 log: Optional[Callable[[str], None]] = None):
        self.headless = headless
        self.rotate_identity = rotate_identity
        self.profile_dir = profile_dir
        self.retries = max(0, int(retries))
        self.nav_timeout_ms = int(nav_timeout * 1000)
        self.cookies_dir = Path(cookies_dir) if cookies_dir else COOKIE_DIR
        self.log = log or (lambda m: print(f"[ghost] {m}", file=sys.stderr))
        self.notes: list[str] = []
        self.pool: Optional[ProxyPool] = None
        self.proxy: Optional[Proxy] = None
        if isinstance(proxy, ProxyPool):
            self.pool = proxy
        elif isinstance(proxy, Proxy):
            self.proxy = proxy
        elif isinstance(proxy, str) and proxy.lower() == "auto":
            self.pool = ProxyPool.from_sources(**(pool_kwargs or {}))
            self.notes.extend(self.pool.notes)
        elif isinstance(proxy, str) and proxy and proxy.lower() not in ("none", "direct", "off"):
            self.proxy = Proxy.parse(proxy, source="cli")
        if self.pool is not None:
            self.proxy = self.pool.next()
        self._pw = self._browser = self._ctx = None
        self.identity: dict = {}
        self.channel = None
        self.browser_version = ""
        self.exit_ip: Optional[str] = None

    # ---- lifecycle ---------------------------------------------------------
    def __enter__(self) -> "GhostBrowser":
        self.start()
        return self

    def __exit__(self, *exc):
        self.close()

    def start(self):
        self._pw = sync_playwright().start()
        args = ["--disable-blink-features=AutomationControlled", "--autoplay-policy=no-user-gesture-required",
                "--mute-audio"]
        if self.profile_dir:
            if self.proxy is not None and not self.proxy.trusted:
                self.notes.append("untrusted proxy refused with a persistent profile -> direct")
                self.proxy = None
            self._new_context(persistent_args=args)
            return self
        last = None
        for channel in ("chrome", "msedge", None):
            try:
                self._browser = self._pw.chromium.launch(channel=channel, headless=self.headless, args=args)
                self.channel = channel or "chromium (bundled)"
                break
            except PWError as e:
                last = e
        if self._browser is None:
            raise GhostError(f"could not launch any chromium: {last}. Run: python -m playwright install chromium")
        self.browser_version = self._browser.version
        self._new_context()
        return self

    def close(self):
        for obj in (self._ctx, self._browser):
            try:
                if obj:
                    obj.close()
            except Exception:  # noqa: BLE001
                pass
        try:
            if self._pw:
                self._pw.stop()
        except Exception:  # noqa: BLE001
            pass
        self._ctx = self._browser = self._pw = None

    # ---- identity / context ------------------------------------------------
    def _make_identity(self) -> dict:
        base = dict(random.choice(LOCALE_PROFILES)) if self.rotate_identity else dict(DEFAULT_IDENTITY)
        vw = random.choice(VIEWPORTS) if self.rotate_identity else DEFAULT_IDENTITY["viewport"]
        major = (self.browser_version or "131.0").split(".")[0]
        ua = (f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
              f"Chrome/{major}.0.0.0 Safari/537.36")
        return {**base, "viewport": vw, "user_agent": ua}

    def _new_context(self, persistent_args=None):
        if self._ctx is not None:
            try:
                self._ctx.close()
            except Exception:  # noqa: BLE001
                pass
        self.identity = self._make_identity()
        ident = self.identity
        opts = dict(
            user_agent=ident["user_agent"], locale=ident["locale"], timezone_id=ident["timezone_id"],
            viewport={"width": ident["viewport"][0], "height": ident["viewport"][1]},
            extra_http_headers={"Accept-Language": ident["accept_language"]},
            ignore_https_errors=False, java_script_enabled=True, accept_downloads=True,
        )
        if self.proxy is not None:
            opts["proxy"] = self.proxy.playwright()
        if persistent_args is not None:
            Path(self.profile_dir).mkdir(parents=True, exist_ok=True)
            last = None
            for channel in ("chrome", "msedge", None):
                try:
                    self._ctx = self._pw.chromium.launch_persistent_context(
                        self.profile_dir, channel=channel, headless=self.headless, args=persistent_args, **opts)
                    self.channel = channel or "chromium (bundled)"
                    break
                except PWError as e:
                    last = e
            if self._ctx is None:
                raise GhostError(f"could not launch persistent context: {last}")
            self.browser_version = self._ctx.browser.version if self._ctx.browser else ""
        else:
            self._ctx = self._browser.new_context(**opts)
        self._ctx.set_default_navigation_timeout(self.nav_timeout_ms)
        self._ctx.set_default_timeout(15000)
        self._ctx.add_init_script(STEALTH_JS)
        self._ctx.add_init_script(EME_PROBE_JS)
        self.exit_ip = None
        return self._ctx

    def _rotate(self, reason: str):
        """Switch to next proxy (if a pool exists) and a fresh identity/context."""
        if self.pool is not None:
            self.pool.mark_bad(self.proxy, reason)
            if any(p.source == "tor" for p in self.pool.proxies) and self.proxy and self.proxy.source == "tor":
                self.pool.rotate_tor()
            self.proxy = self.pool.next()
        if self.profile_dir:
            self.notes.append(f"retry after: {reason} (persistent profile: same context)")
            return
        self._new_context()
        self.notes.append(f"rotated after: {reason} -> {describe(self.proxy)}")
        self.log(f"rotated -> {describe(self.proxy)}")

    @property
    def context(self):
        return self._ctx

    @property
    def cookies_allowed(self) -> bool:
        """Cookies are only exported/forwarded when the egress is direct or a trusted proxy."""
        return self.proxy is None or self.proxy.trusted

    def get_exit_ip(self) -> Optional[str]:
        if self.exit_ip is None:
            try:
                r = self._ctx.request.get("https://api.ipify.org?format=json", timeout=10000)
                self.exit_ip = r.json().get("ip") if r.ok else None
            except Exception:  # noqa: BLE001
                self.exit_ip = None
        return self.exit_ip

    def _with_retry(self, fn: Callable[[], Any]) -> Any:
        last = None
        for attempt in range(self.retries + 1):
            try:
                return fn()
            except Exception as e:  # noqa: BLE001
                if not _is_retryable_error(e) or attempt >= self.retries:
                    raise
                last = e
                reason = str(e).splitlines()[0][:160]
                self.log(f"attempt {attempt + 1} failed ({reason})")
                self._rotate(reason)
        raise last  # pragma: no cover

    def _goto(self, page, url: str, wait_until: str = "domcontentloaded"):
        resp = page.goto(url, wait_until=wait_until)
        status = resp.status if resp else None
        if status in (403, 429, 407, 502, 503):
            title = ""
            try:
                title = page.title()
            except Exception:  # noqa: BLE001
                pass
            # A 403 that is a CAPTCHA/bot wall is not retried blindly (detected and reported instead)
            if self._captcha_check(page, resp)[0]:
                return resp
            raise RetryableError(f"HTTP {status} on {url} {title[:60]}")
        return resp

    # ---- detection -----------------------------------------------------------
    def _captcha_check(self, page, resp=None) -> tuple[bool, list[str]]:
        why = []
        try:
            title = page.title() or ""
        except Exception:  # noqa: BLE001
            title = ""
        if CAPTCHA_TITLES.search(title):
            why.append(f"title looks like a bot check: {title[:80]!r}")
        for fr in page.frames:
            for pat in CAPTCHA_PATTERNS:
                if re.search(pat, fr.url or "", re.I):
                    why.append(f"captcha frame: {urlsplit(fr.url).netloc}")
                    break
        try:
            if resp is not None and resp.headers.get("cf-mitigated") == "challenge":
                why.append("cloudflare cf-mitigated: challenge")
        except Exception:  # noqa: BLE001
            pass
        try:
            if page.locator("iframe[src*='recaptcha'], iframe[src*='hcaptcha'], .cf-turnstile, #challenge-form, "
                            "div.g-recaptcha, div.h-captcha").count():
                why.append("captcha widget in DOM")
        except Exception:  # noqa: BLE001
            pass
        return (bool(why), sorted(set(why)))

    # ---- actions -------------------------------------------------------------
    def _click_play(self, page) -> list[str]:
        done = []
        for fr in page.frames:
            try:
                n = fr.evaluate("() => { let n=0; document.querySelectorAll('video,audio').forEach(v => "
                                "{ try { v.muted = true; const p = v.play(); if (p && p.catch) p.catch(()=>{}); n++; }"
                                " catch(e){} }); return n; }")
                if n:
                    done.append(f"play() on {n} media element(s) in {urlsplit(fr.url).netloc or 'about:blank frame'}")
            except Exception:  # noqa: BLE001
                pass
            for sel in PLAY_SELECTORS:
                try:
                    loc = fr.locator(sel).first
                    if loc.count() and loc.is_visible():
                        loc.click(timeout=1500, no_wait_after=True)
                        done.append(f"clicked {sel} in {urlsplit(fr.url).netloc or 'about:blank frame'}")
                        break
                except Exception:  # noqa: BLE001
                    continue
        if not done:
            # click the biggest video element center as a last resort
            try:
                v = page.locator("video").first
                if v.count():
                    v.click(timeout=1500, no_wait_after=True, force=True)
                    done.append("clicked <video>")
            except Exception:  # noqa: BLE001
                pass
        return done

    @staticmethod
    def _scroll(page, steps: int = 4):
        for _ in range(steps):
            try:
                page.mouse.wheel(0, 900)
                page.wait_for_timeout(350)
            except Exception:  # noqa: BLE001
                break
        try:
            page.evaluate("window.scrollTo(0, 0)")
        except Exception:  # noqa: BLE001
            pass

    def _cookie_header(self, url: str) -> Optional[str]:
        if not self.cookies_allowed:
            return None
        try:
            cs = self._ctx.cookies([url])
        except Exception:  # noqa: BLE001
            return None
        return "; ".join(f"{c['name']}={c['value']}" for c in cs) or None

    # ---- public API ----------------------------------------------------------
    def sniff(self, url: str, wait: float = 15, click_play: bool = True, scroll: bool = True,
              cookies_path: Optional[str] = None, follow_embeds: bool = True, _depth: int = 0,
              _referer: Optional[str] = None) -> dict:
        """Open url, capture media streams. Returns:
        {"url","final_url","title","media":[{"url","kind","content_type","size","headers":{Referer,User-Agent,Cookie?},
          "score","source","height","master","drm",...}],"best","segments":[...],"embeds":[...],
          "cookies_file","user_agent","identity","proxy","exit_ip","captcha","drm","drm_systems","notes","browser"}
        kind is one of hls|dash|mp4|webm|audio|other. Sorted by score desc.
        """
        def run():
            return self._sniff_once(url, wait, click_play, scroll, cookies_path, follow_embeds, _depth, _referer)
        return self._with_retry(run)

    def _sniff_once(self, url, wait, click_play, scroll, cookies_path, follow_embeds, depth, referer) -> dict:
        found: dict[str, dict] = {}
        segments: dict[str, dict] = {}
        license_hits: set[str] = set()
        notes: list[str] = []
        pending_bodies: list = []
        page = self._ctx.new_page()

        def on_request(req):
            u = req.url
            if u.startswith(("data:", "blob:")):
                return
            if LICENSE_PATTERNS.search(u) and req.method == "POST":
                license_hits.add(urlsplit(u).netloc + urlsplit(u).path[:60])
            k = classify(u)
            if k and k != "segment" and u not in found:
                fr_url = ""
                try:
                    fr_url = req.frame.url
                except Exception:  # noqa: BLE001
                    pass
                found[u] = {"url": u, "kind": k, "content_type": "", "size": None, "source": "network",
                            "frame": fr_url, "status": None}

        def on_response(resp):
            u = resp.url
            if u.startswith(("data:", "blob:")):
                return
            try:
                h = resp.headers
            except Exception:  # noqa: BLE001
                return
            ct = h.get("content-type", "")
            k = classify(u, ct)
            if not k:
                return
            size = None
            cr = h.get("content-range", "")
            if "/" in cr and cr.rsplit("/", 1)[1].isdigit():
                size = int(cr.rsplit("/", 1)[1])
            elif h.get("content-length", "").isdigit():
                size = int(h["content-length"])
            if k == "segment":
                base = re.sub(r"[^/]*$", "", urlsplit(u).path)
                key = urlsplit(u).netloc + base
                g = segments.setdefault(key, {"base": f"{urlsplit(u).scheme}://{key}", "count": 0,
                                              "ext": os.path.splitext(urlsplit(u).path)[1], "sample": u,
                                              "content_type": ct.split(";")[0]})
                g["count"] += 1
                return
            fr_url = ""
            try:
                fr_url = resp.frame.url
            except Exception:  # noqa: BLE001
                pass
            m = found.setdefault(u, {"url": u, "kind": k, "source": "network", "frame": fr_url})
            m.update({"kind": k, "content_type": ct.split(";")[0], "size": size or m.get("size"),
                      "status": resp.status})
            if k in ("hls", "dash") and resp.status < 400:
                pending_bodies.append((u, resp))

        self._ctx.on("request", on_request)
        self._ctx.on("response", on_response)
        try:
            if referer:
                page.set_extra_http_headers({"Referer": referer})
            resp = self._goto(page, url)
            try:
                page.wait_for_load_state("load", timeout=min(15000, int(wait * 1000)))
            except PWTimeout:
                notes.append("load event not reached in time; continuing")
            captcha, why = self._captcha_check(page, resp)
            if captcha:
                notes.append("CAPTCHA / bot challenge detected - not solved by design. "
                             "Open it yourself with --headful and a --profile dir, or use the site's official API.")
                notes.extend(why)
            else:
                if scroll:
                    self._scroll(page)
                if click_play:
                    acts = self._click_play(page)
                    notes.extend(acts or ["no play button / media element found to click"])
                # wait for network activity, finish early once a manifest is seen and things are quiet
                deadline = time.time() + wait
                last_n, quiet_since, reclicked = -1, time.time(), not click_play
                while time.time() < deadline:
                    page.wait_for_timeout(500)
                    n = len(found) + sum(g["count"] for g in segments.values())
                    if n != last_n:
                        last_n, quiet_since = n, time.time()
                    has_manifest = any(m["kind"] in ("hls", "dash") for m in found.values())
                    if (has_manifest or found) and time.time() - quiet_since > 3.0 and \
                            time.time() > deadline - wait + 5:
                        break
                    if not reclicked and not found and deadline - time.time() < wait / 2:
                        reclicked = True  # second chance: players that load lazily
                        self._click_play(page)

            # DOM scan in every frame
            dom = {"media": [], "iframes": [], "blob": False, "jsonld": [], "meta": []}
            for fr in page.frames:
                try:
                    d = fr.evaluate(DOM_SCAN_JS)
                except Exception:  # noqa: BLE001
                    continue
                for key in ("media", "iframes", "jsonld", "meta"):
                    dom[key].extend(d.get(key) or [])
                dom["blob"] = dom["blob"] or d.get("blob")
            for item in dom["media"] + dom["meta"] + [j for j in dom["jsonld"] if not j.get("embed")]:
                u = item.get("url")
                if not u or u.startswith(("blob:", "data:")):
                    continue
                k = classify(u, item.get("type", "")) or ("other" if "video" in item.get("via", "") else None)
                if k == "audio" and str(item.get("via", "")).startswith("video"):
                    k = "other"  # e.g. .ogg/.ogv inside a <video>
                if not k or k == "segment":
                    continue
                m = found.setdefault(u, {"url": u, "kind": k, "content_type": item.get("type", ""), "size": None,
                                         "source": "dom", "frame": page.url})
                m.setdefault("via", item.get("via"))
                if item.get("label"):
                    m.setdefault("label", item["label"])
                if item.get("height"):
                    m["height"] = max(m.get("height") or 0, item["height"])
            if dom["blob"]:
                notes.append("player uses MSE blob: URL - real stream URLs come from the network capture above")

            # manifests only referenced in the DOM (links / <source>): fetch a few to learn master/height/DRM
            seen_bodies = {u for u, _ in pending_bodies}
            dom_manifests = [m["url"] for m in found.values() if m["kind"] in ("hls", "dash")
                             and m.get("source") == "dom" and m["url"] not in seen_bodies][:10]
            for u in dom_manifests:
                try:
                    r = self._ctx.request.get(u, timeout=8000, headers={"Referer": page.url})
                    if r.ok:
                        pending_bodies.append((u, r))
                    else:
                        found[u]["status"] = r.status
                except Exception:  # noqa: BLE001
                    pass

            # manifest bodies (master playlist detection, resolution, DRM)
            drm_systems: set[str] = set()
            for u, r in pending_bodies:
                try:
                    body = r.text()[:400_000]
                except Exception:  # noqa: BLE001
                    continue
                m = found.get(u)
                if m is None:
                    continue
                if m["kind"] == "hls":
                    info = parse_hls(body)
                    m.update({"master": info["master"], "variants": info["variants"],
                              "height": max(m.get("height") or 0, info["max_height"]),
                              "bandwidth": info["max_bandwidth"], "live": info["live"]})
                    if info["aes128"]:
                        m["encryption"] = "AES-128 (standard HLS, key served by site; ffmpeg/yt-dlp handle it)"
                    if info["drm"]:
                        m["drm"] = info["drm"]
                        drm_systems.add(info["drm"])
                else:
                    info = parse_dash(body)
                    m.update({"height": max(m.get("height") or 0, info["max_height"]),
                              "bandwidth": info["max_bandwidth"], "live": info["live"], "master": True})
                    if info["drm"]:
                        m["drm"] = info["drm"]
                        drm_systems.add(info["drm"])
            try:
                eme = page.evaluate("() => window.__vg_eme || []")
                for fr in page.frames[1:]:
                    try:
                        eme += fr.evaluate("() => window.__vg_eme || []")
                    except Exception:  # noqa: BLE001
                        pass
            except Exception:  # noqa: BLE001
                eme = []
            eme = sorted(set(eme))
            if "active" in eme:  # MediaKeys actually attached to a <video>: protected playback
                keys = [k[5:] for k in eme if k.startswith("keys:") and "clearkey" not in k.lower()]
                if keys or not any("clearkey" in k.lower() for k in eme):
                    drm_systems.update(f"EME {k}" for k in (keys or ["(unknown key system)"]))
            elif any(k.startswith("probe:") for k in eme):
                notes.append("player probed EME key systems (" + ", ".join(k[6:] for k in eme if k.startswith("probe:"))[:160]
                             + ") but did not activate DRM for this stream")
            if license_hits:
                drm_systems.add("license server requests: " + ", ".join(sorted(license_hits))[:200])
            drm = bool(drm_systems)
            if drm:
                notes.append("DRM detected (" + "; ".join(sorted(drm_systems)) + "). Protected streams cannot "
                             "be downloaded/decrypted by this tool - by design. Use the site's own offline/download feature.")

            # embeds: recurse into player iframes when nothing (or nothing good) was found on the page
            embeds = []
            for u in dom["iframes"] + [j["url"] for j in dom["jsonld"] if j.get("embed")]:
                if u and EMBED_HOSTS.search(u) and u not in embeds and not AD_HOSTS.search(u):
                    embeds.append(u)
            final_url = page.url
            title = ""
            try:
                title = page.title()
            except Exception:  # noqa: BLE001
                pass
            cookie_list = self._ctx.cookies() if self.cookies_allowed else []
        finally:
            try:
                self._ctx.remove_listener("request", on_request)
                self._ctx.remove_listener("response", on_response)
            except Exception:  # noqa: BLE001
                pass
            try:
                page.close()
            except Exception:  # noqa: BLE001
                pass

        ua = self.identity.get("user_agent")
        media = []
        for m in found.values():
            if m.get("status") and m["status"] >= 400:
                continue
            m.setdefault("content_type", "")
            m.setdefault("size", None)
            if not m.get("height"):
                m["height"] = height_from_url(m["url"]) or None
            ref = m.pop("frame", None) or final_url
            if ref.startswith("about:"):
                ref = final_url
            headers = {"Referer": ref, "User-Agent": ua}
            ck = self._cookie_header(m["url"])
            if ck:
                headers["Cookie"] = ck
            m["headers"] = headers
            m["score"] = score_media(m, final_url)
            media.append(m)
        media.sort(key=lambda x: x["score"], reverse=True)

        result = {
            "url": url, "final_url": final_url, "title": title, "media": media,
            "best": None, "segments": list(segments.values()), "embeds": embeds,
            "cookies_file": None, "user_agent": ua, "identity": {k: v for k, v in self.identity.items()},
            "proxy": describe(self.proxy), "exit_ip": self.get_exit_ip(), "captcha": captcha, "drm": drm,
            "drm_systems": sorted(drm_systems), "notes": notes, "browser": f"{self.channel} {self.browser_version}",
        }
        if segments and not any(m["kind"] in ("hls", "dash") for m in media):
            notes.append(f"{sum(g['count'] for g in segments.values())} media segments seen but no manifest captured "
                         "- try a longer --wait or pass the page URL to yt-dlp")
        elif segments:
            notes.append(f"{sum(g['count'] for g in segments.values())} segments grouped under {len(segments)} base path(s)")

        if follow_embeds and depth < 1 and embeds and not captcha:
            good = [m for m in media if m["score"] >= 50]
            if not good:
                for e in embeds[:3]:
                    notes.append(f"following embed player: {e}")
                    try:
                        sub = self._sniff_once(e, max(8, wait * 0.7), click_play, False, None, False, depth + 1, final_url)
                    except Exception as ex:  # noqa: BLE001
                        notes.append(f"embed failed: {str(ex).splitlines()[0][:120]}")
                        continue
                    for sm in sub["media"]:
                        sm["via_embed"] = e
                        media.append(sm)
                    result["drm"] = result["drm"] or sub["drm"]
                    result["captcha"] = result["captcha"] or sub["captcha"]
                    result["drm_systems"] = sorted(set(result["drm_systems"]) | set(sub["drm_systems"]))
                    notes.extend(f"[embed] {n}" for n in sub["notes"])
                    if sub["media"]:
                        break
                media.sort(key=lambda x: x["score"], reverse=True)

        if depth == 0:
            if self.cookies_allowed:
                path = Path(cookies_path) if cookies_path else \
                    self.cookies_dir / f"{_host(final_url)}-{time.strftime('%Y%m%d-%H%M%S')}.txt"
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(netscape_cookies(cookie_list), encoding="utf-8")
                result["cookies_file"] = str(path)
            else:
                notes.append("egress is an UNTRUSTED proxy: cookies not exported and no Cookie headers attached")
            if self.proxy is None:
                notes.append("egress: direct connection (no proxy)")
            if not media:
                notes.append("no media candidates found. Try: longer --wait, --headful, or pass the page URL "
                             "directly to yt-dlp (it supports 1000+ sites).")
        result["best"] = next((m for m in media if not m.get("drm")), None) if media else None
        if result["best"] is None and media:
            notes.append("all candidates are DRM-protected")
        return result

    def fetch_text(self, url: str, wait: float = 3, max_chars: int = 200_000) -> dict:
        """Readable text + links. Returns {"url","final_url","title","text","links":[{"text","href"}],
        "captcha","proxy","exit_ip","notes"}."""
        def run():
            page = self._ctx.new_page()
            try:
                resp = self._goto(page, url)
                try:
                    page.wait_for_load_state("load", timeout=15000)
                except PWTimeout:
                    pass
                page.wait_for_timeout(int(wait * 1000))
                captcha, why = self._captcha_check(page, resp)
                data = page.evaluate(r"""() => {
                  const pick = document.querySelector('article, main, [role=main]') || document.body;
                  const clone = pick.cloneNode(true);
                  clone.querySelectorAll('script,style,noscript,svg,template').forEach(e => e.remove());
                  const text = (pick.innerText || clone.textContent || '').replace(/\n{3,}/g, '\n\n').trim();
                  const links = [...document.querySelectorAll('a[href]')].map(a => ({
                    text: (a.innerText || a.title || '').trim().slice(0, 200), href: a.href}))
                    .filter(l => l.href.startsWith('http'));
                  const seen = new Set();
                  return {text, links: links.filter(l => !seen.has(l.href) && seen.add(l.href))};
                }""")
                return {"url": url, "final_url": page.url, "title": page.title(),
                        "text": data["text"][:max_chars], "links": data["links"], "captcha": captcha,
                        "proxy": describe(self.proxy), "exit_ip": self.get_exit_ip(),
                        "notes": why + ([] if self.proxy else ["egress: direct connection (no proxy)"])}
            finally:
                page.close()
        return self._with_retry(run)

    def get_html(self, url: str, wait: float = 2) -> str:
        """Fully rendered HTML (after JS)."""
        def run():
            page = self._ctx.new_page()
            try:
                self._goto(page, url)
                try:
                    page.wait_for_load_state("load", timeout=15000)
                except PWTimeout:
                    pass
                page.wait_for_timeout(int(wait * 1000))
                return page.content()
            finally:
                page.close()
        return self._with_retry(run)

    def screenshot(self, url: str, path: str, full_page: bool = True, wait: float = 2) -> str:
        """Save a PNG/JPEG screenshot, returns the absolute path."""
        out = Path(path).resolve()
        out.parent.mkdir(parents=True, exist_ok=True)

        def run():
            page = self._ctx.new_page()
            try:
                self._goto(page, url)
                try:
                    page.wait_for_load_state("load", timeout=15000)
                except PWTimeout:
                    pass
                page.wait_for_timeout(int(wait * 1000))
                page.screenshot(path=str(out), full_page=full_page, timeout=30000)
                return str(out)
            finally:
                page.close()
        return self._with_retry(run)

    def export_cookies(self, path: str, url: Optional[str] = None, wait: float = 3) -> str:
        """Write context cookies as Netscape cookies.txt (for yt-dlp --cookies). If url is given, visit it first."""
        if not self.cookies_allowed:
            raise GhostError("refusing to export cookies obtained through an UNTRUSTED proxy")
        if url:
            def run():
                page = self._ctx.new_page()
                try:
                    self._goto(page, url)
                    page.wait_for_timeout(int(wait * 1000))
                finally:
                    page.close()
            self._with_retry(run)
        out = Path(path).resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(netscape_cookies(self._ctx.cookies()), encoding="utf-8")
        return str(out)


# ----------------------------------------------------------------------------- convenience
def sniff(url: str, proxy: Any = None, wait: float = 15, headless: bool = True, **kw) -> dict:
    with GhostBrowser(proxy=proxy, headless=headless) as gb:
        return gb.sniff(url, wait=wait, **kw)


# ----------------------------------------------------------------------------- CLI
def _fmt_size(n):
    if not n:
        return "?"
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.0f}{unit}"
        n /= 1024
    return f"{n:.1f}TB"


def main(argv=None) -> int:
    for st in (sys.stdout, sys.stderr):
        try:
            st.reconfigure(encoding="utf-8")
        except Exception:  # noqa: BLE001
            pass
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--proxy", default="none", help="auto | none | scheme://[user:pass@]host:port")
    common.add_argument("--headful", action="store_true", help="show the browser window")
    common.add_argument("--json", action="store_true")
    common.add_argument("--retries", type=int, default=2)
    common.add_argument("--profile", default=None, help="persistent profile dir")
    common.add_argument("--no-rotate", action="store_true", help="fixed identity")
    common.add_argument("--tor", action="store_true", help="with --proxy auto: include Tor")
    common.add_argument("--free", action="store_true", help="with --proxy auto: include free public proxies (untrusted)")
    ap = argparse.ArgumentParser(description="video-grabber ghost browser")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sniff", parents=[common])
    s.add_argument("url")
    s.add_argument("--wait", type=float, default=15)
    s.add_argument("--no-click", action="store_true")
    s.add_argument("--no-scroll", action="store_true")
    s.add_argument("--no-embeds", action="store_true")
    s.add_argument("--cookies-out")
    t = sub.add_parser("text", parents=[common])
    t.add_argument("url")
    t.add_argument("--max-chars", type=int, default=200_000)
    h = sub.add_parser("shot", parents=[common])
    h.add_argument("url")
    h.add_argument("out")
    h.add_argument("--viewport-only", action="store_true")
    c = sub.add_parser("cookies", parents=[common])
    c.add_argument("url")
    c.add_argument("out")
    g = sub.add_parser("html", parents=[common])
    g.add_argument("url")
    g.add_argument("out", nargs="?")
    a = ap.parse_args(argv)

    pool_kwargs = {"tor": a.tor, "free": a.free}
    try:
        with GhostBrowser(proxy=a.proxy, headless=not a.headful, rotate_identity=not a.no_rotate,
                          profile_dir=a.profile, retries=a.retries, pool_kwargs=pool_kwargs) as gb:
            if a.cmd == "sniff":
                r = gb.sniff(a.url, wait=a.wait, click_play=not a.no_click, scroll=not a.no_scroll,
                             cookies_path=a.cookies_out, follow_embeds=not a.no_embeds)
                r["notes"] = gb.notes + r["notes"]
                if a.json:
                    print(json.dumps(r, ensure_ascii=False, indent=2))
                else:
                    print(f"page   : {r['title']!r}\nfinal  : {r['final_url']}\nproxy  : {r['proxy']}  exit_ip={r['exit_ip']}")
                    print(f"browser: {r['browser']}  UA={r['user_agent']}")
                    print(f"captcha: {r['captcha']}  drm: {r['drm']} {r['drm_systems'] or ''}")
                    print(f"cookies: {r['cookies_file']}")
                    print(f"media  : {len(r['media'])} candidate(s)")
                    for m in r["media"][:15]:
                        extra = " master" if m.get("master") else ""
                        extra += f" {m['height']}p" if m.get("height") else ""
                        extra += f" DRM={m['drm']}" if m.get("drm") else ""
                        print(f"  [{m['score']:>3}] {m['kind']:<5}{extra:<14} {_fmt_size(m.get('size')):>7}  {m['url'][:150]}")
                    for sg in r["segments"][:5]:
                        print(f"  segments x{sg['count']} {sg['ext']} {sg['base'][:120]}")
                    for e in r["embeds"][:5]:
                        print(f"  embed: {e}")
                    print("best   :", r["best"]["url"] if r["best"] else None)
                    for n in r["notes"]:
                        print("note   :", n)
                return 0 if r["media"] else 3
            if a.cmd == "text":
                r = gb.fetch_text(a.url, max_chars=a.max_chars)
                if a.json:
                    print(json.dumps(r, ensure_ascii=False, indent=2))
                else:
                    print(f"# {r['title']}\n{r['final_url']}  (via {r['proxy']}, ip {r['exit_ip']})\n")
                    print(r["text"])
                    print(f"\n--- {len(r['links'])} links ---")
                    for l in r["links"][:100]:
                        print(f"- {l['text'][:80]} -> {l['href']}")
                return 0
            if a.cmd == "shot":
                p = gb.screenshot(a.url, a.out, full_page=not a.viewport_only)
                out = {"screenshot": p, "proxy": describe(gb.proxy), "exit_ip": gb.get_exit_ip()}
                print(json.dumps(out, ensure_ascii=False, indent=2) if a.json else f"saved {p} (via {out['proxy']})")
                return 0
            if a.cmd == "cookies":
                p = gb.export_cookies(a.out, url=a.url)
                n = sum(1 for l in Path(p).read_text(encoding="utf-8").splitlines()
                        if l.strip() and (not l.startswith("#") or l.startswith("#HttpOnly_")))
                out = {"cookies_file": p, "count": n, "proxy": describe(gb.proxy)}
                print(json.dumps(out, ensure_ascii=False, indent=2) if a.json else f"saved {p}")
                return 0
            if a.cmd == "html":
                html = gb.get_html(a.url)
                if a.out:
                    Path(a.out).write_text(html, encoding="utf-8")
                    print(json.dumps({"html_file": str(Path(a.out).resolve()), "chars": len(html)}) if a.json
                          else f"saved {a.out} ({len(html)} chars)")
                else:
                    print(html)
                return 0
    except Exception as e:  # noqa: BLE001
        err = {"error": type(e).__name__, "message": str(e).splitlines()[0][:400], "proxy": a.proxy}
        print(json.dumps(err, ensure_ascii=False) if getattr(a, "json", False) else f"ERROR: {err}", file=sys.stdout)
        return 1
    return 2


if __name__ == "__main__":
    sys.exit(main())
