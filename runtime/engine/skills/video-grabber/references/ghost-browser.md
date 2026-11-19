# Ghost browser (headless) - reference

Files: `scripts/ghost_browser.py`, `scripts/proxy_pool.py`, `config/proxies.example.txt`, tests in `tests/browser/`.

Purpose: open JS-heavy pages in hidden Chromium, find the real stream URLs, export cookies for yt-dlp, read text, screenshot. Egress IP can rotate through a proxy pool.

Out of scope by design: CAPTCHA solving, login brute forcing, paywall or DRM circumvention. CAPTCHA and DRM are detected and reported (`captcha: true`, `drm: true`, `drm_systems`, `notes`); stop there and tell the user.

## Python API

```python
import sys; sys.path.insert(0, r"C:\Users\cinde\.claude\skills\video-grabber\scripts")
from ghost_browser import GhostBrowser, sniff
with GhostBrowser(proxy=None|"auto"|"socks5://h:p"|"none", headless=True, rotate_identity=True,
                  profile_dir=None, retries=2) as gb:
    r = gb.sniff(url, wait=15, click_play=True, scroll=True)
    gb.fetch_text(url); gb.get_html(url); gb.screenshot(url, "out.png", full_page=True)
    gb.export_cookies("cookies.txt", url=url)
```

`sniff()` returns:
`{url, final_url, title, media:[{url, kind: hls|dash|mp4|webm|audio|other, content_type, size, height, master, drm, headers:{Referer, User-Agent, Cookie?}, score, source: network|dom, via}], best, segments:[{base,count,ext,sample}], embeds, cookies_file, user_agent, identity, proxy, exit_ip, captcha, drm, drm_systems, notes, browser}`.
`media` is sorted by score (master playlists, resolution, first-party, `<video>`-referenced rank higher; ads, tiny previews, DRM rank lower). `best` is the top non-DRM item or `None`.

Handing off to yt-dlp / ffmpeg:
```
yt-dlp --cookies <cookies_file> --user-agent "<user_agent>" --referer "<best.headers.Referer>" "<best.url>"
```
Add `--proxy <url>` if the browser used a proxy (use the same one so IP-bound tokens work).

## CLI

```
python ghost_browser.py sniff URL [--proxy auto|URL|none] [--wait 20] [--json] [--headful] [--no-click] [--no-embeds] [--cookies-out F]
python ghost_browser.py text URL [--json]
python ghost_browser.py shot URL out.png [--viewport-only]
python ghost_browser.py cookies URL out.txt
python ghost_browser.py html URL [out.html]
```
Exit codes: 0 ok, 3 sniff found nothing, 1 error. Extra flags: `--tor`, `--free` (with `--proxy auto`), `--profile DIR`, `--no-rotate`, `--retries N`.

## Proxy pool

Sources: file `%USERPROFILE%\.video-grabber\proxies.txt`, env `VG_PROXIES`, `--tor` (socks5://127.0.0.1:9050, NEWNYM via 9051), `--free` (public lists).
Free proxies are UNTRUSTED: cookies are not exported and no Cookie header is attached while one is in use. Chromium cannot use SOCKS proxies with credentials.
Empty or fully failed pool means a DIRECT connection, and every output says `direct (no proxy)`.
Health cache: `%USERPROFILE%\.video-grabber\cache\healthy_proxies.json`, TTL 30 min.

```
python proxy_pool.py check [--free] [--tor] [--json]
python proxy_pool.py ip [--proxy URL|none]
python proxy_pool.py newnym
```
Library: `ProxyPool.from_sources(file, env, tor, free, check)`, `.next(trusted_only=False)` (None = direct), `.mark_bad(p, reason)`, `ProxyPool.current_ip(p)`, `.summary()`.

Rotation: on timeout, HTTP 403/429/5xx (non-CAPTCHA) or connection errors, `GhostBrowser` marks the proxy bad, takes the next one, builds a fresh context with a new identity and retries up to `retries` times.

## Identity

Per context: UA (built from the real Chrome major version, Windows), viewport, locale, Accept-Language and timezone drawn together from consistent profiles. Hardening is only `navigator.webdriver = false`. No fingerprint spoofing.

## Troubleshooting

- Nothing found: raise `--wait 30`, try `--headful`, or give the page URL straight to yt-dlp.
- `captcha: true`: stop; the user may solve it themselves with `--headful --profile DIR`.
- `drm: true`: protected stream; cannot be saved with these tools.
- Browsers missing: `python -m playwright install chromium` (installed Chrome is preferred automatically).
- Tests: `python -m pytest tests/browser -q` (offline, local server) and `python tests/browser/live_sites.py OUT_DIR` (internet).
