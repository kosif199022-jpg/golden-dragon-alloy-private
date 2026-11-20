---
name: video-grabber
description: >-
  نزّل فيديو من أي موقع بأمر واحد وبأعلى جودة — تحميل فيديو، حمّل من يوتيوب / تيك توك / انستجرام / فيسبوك / تويتر (X) / فيميو / أي موقع،
  رابط فيديو، استخرج رابط البث (m3u8/mpd)، صوت بس mp3، جزء من الفيديو، ترجمة، متصفح مخفي، تغيير الآي بي، بروكسي.
  Download video from any site with one command, best quality, reliably: yt-dlp + aria2c + ffmpeg, proxy rotation
  on 403/429/geo-blocks, a headless "ghost" browser (playwright) that sniffs the real stream when yt-dlp can't,
  direct-file downloads with 16 connections and resume, ffprobe verification. Use for "download video", "grab this
  link", "save this reel/tiktok/tweet video", "extract the stream URL", "audio only", "clip 1:00-2:30",
  "headless browser", "proxy", "change IP", "screenshot/read a JS page".
---

# video-grabber

One command: `python "%USERPROFILE%\.claude\skills\video-grabber\scripts\grab.py" URL`.
Only content the user has rights to; DRM is never circumvented and CAPTCHAs are never solved — detect, report, stop.

## Quick start

```bash
G="$HOME/.claude/skills/video-grabber/scripts/grab.py"
python "$G" URL                                  # best quality (mp4 if compatible, else mkv)
python "$G" URL -o "D:/clips" --quality 1080      # cap height (2160|1440|1080|720|480|360)
python "$G" URL --compat                          # H.264/AAC .mp4 for Premiere/Resolve/CapCut
python "$G" URL --audio-only mp3                  # mp3|m4a|wav
python "$G" URL --section 00:01:00-00:02:30       # only that part
python "$G" URL --subs ar,en                      # subtitles (+auto captions), embedded + .srt
python "$G" URL --playlist --limit 10             # playlist / channel
python "$G" --batch urls.txt --json               # many links (# comments ok)
python "$G" URL --info --json                     # metadata only (heights, codecs, DRM flag, subs)
python "$G" URL --browser-cookies chrome          # login/age/bot-check sites (or --cookies cookies.txt)
python "$G" URL --sniff                           # skip yt-dlp, find the stream in the ghost browser
python "$G" --update                              # pip install -U "yt-dlp[default]"
```

Always pass `--json` when you (Claude) parse the result: stdout is then a single JSON line
`{"ok", "out_dir", "done", "failed", "results":[{url, ok, status, method, files:[{path, duration, width, height,
fps, vcodec, acodec, has_audio, size_mb, verified}], attempts, error, hint}]}`. Logs go to stderr.
Exit code 0 = all ok. Every saved file is appended to `<out>/sources.txt` (time, URL, file, method).
Default output: `%USERPROFILE%\Downloads\video-grabber` (or env `VG_OUT`).

## Decision flow (automatic, stops at first success)

1. **Direct media file?** (server answers with a media Content-Type) → aria2c, 16 connections, resume.
2. **yt-dlp** best format `bv*+ba/b`, merged mp4/mkv, aria2c for plain http files, 8 concurrent fragments for HLS/DASH, retries. 1800+ sites.
   - `--section` and ffmpeg fails (e.g. its TLS check on Windows) → HLS segments for just that range are fetched by Python (verified TLS), cut locally; other sources → full download, local cut.
3. **403 / 429 / geo / network** with `--proxy auto` (default) → retry through the proxy pool (next proxy each try, bad ones marked).
4. **Unsupported / nothing found / still failing** → **ghost browser** opens the page, clicks play, sniffs HLS/DASH/MP4, then downloads `best` with its Referer/UA/cookies (yt-dlp → ffmpeg → aria2c).
5. **URL ends in .mp4/.webm/...** but everything failed → aria2c last resort.

Stops immediately and reports (with `hint`) on: `drm`, `private`, `removed`, `login_required`, `captcha`.
Other statuses: `geo_blocked`, `forbidden`, `rate_limited`, `unsupported`, `tls`, `network`, `failed`.

## Ghost browser (helper tool, also usable alone)

```bash
B="$HOME/.claude/skills/video-grabber/scripts/ghost_browser.py"
python "$B" sniff URL --json [--wait 20] [--proxy auto|URL|none] [--headful]   # media URLs + headers + cookies
python "$B" text URL --json            # readable text + links of a JS page
python "$B" shot URL out.png           # full-page screenshot
python "$B" cookies URL cookies.txt    # Netscape cookies for yt-dlp --cookies
python "$B" html URL out.html
```
Reports `captcha: true` / `drm: true` instead of bypassing them. `--headful --profile DIR` lets the user log in themselves once.

## Proxy setup (change egress IP)

- File: `%USERPROFILE%\.video-grabber\proxies.txt`, one per line (`http://user:pass@host:port`, `socks5://host:1080`, `host:port`). Template: `config/proxies.example.txt`.
- Env: `VG_PROXIES="http://u:p@h1:8080, socks5://h2:1080"`.
- Tor: run Tor (port 9050), then `--tor`. Free public proxies: `--free-proxies` (slow, untrusted, no cookies sent).
- One fixed proxy: `--proxy http://host:port`. Never: `--proxy none`.
- Check the pool / exit IP: `python scripts/proxy_pool.py check` · `python scripts/proxy_pool.py ip --proxy auto`.
- Empty pool = direct connection (said explicitly in the log).

## Troubleshooting

| Symptom (`status`) | Do this |
|---|---|
| `login_required` / "Sign in to confirm you're not a bot" | `--browser-cookies chrome` (or edge/firefox; close the browser if the cookie DB is locked) or `--cookies file.txt` |
| `forbidden` 403 / `rate_limited` 429 | `--update`; add a proxy pool; `--browser-cookies`; `--no-aria` (some CDNs hate 16 connections) |
| `geo_blocked` | `--proxy http://<proxy in an allowed country>` or proxies.txt |
| `unsupported` | let the ghost browser run (no `--no-browser`); `--sniff --sniff-wait 30`; for pages needing a click/login use `ghost_browser.py sniff --headful` |
| `drm` | Cannot be downloaded. Tell the user; use the platform's own offline feature |
| `captcha` | Not solved automatically. User opens the page in a real browser, then `--browser-cookies` |
| `private` / `removed` | Check the link; private needs an account that has access (cookies) |
| `tls` / `network` | Retry; check proxy; `--update` |
| YouTube extraction breaks | `python grab.py --update` (needs Deno/Node for YouTube JS challenges — installed) |
| Old yt-dlp | Off by default (rule §2: installing needs a yes). The grabber says yt-dlp is old and prints `grab.py --update`. With the owner's yes: `--auto-update` (or `VG_AUTOUPDATE=1`) refreshes it before the first try when older than 30 days, and once after a failed try (retried only if the version changed). `--no-auto-update` always wins |
| Editor can't open the file (AV1/VP9/Opus) | `--compat` |

Details: `references/downloader.md` (options, JSON fields, internals) · `references/sites.md` (per-site notes).
Tests: `python -m pytest tests/grab -q` (offline) · `python tests/grab/live_grab.py OUT_DIR` (real downloads).
