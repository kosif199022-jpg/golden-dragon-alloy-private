# grab.py — reference

`scripts/grab.py` — Python 3.10+, needs `yt-dlp` (module or exe), `ffmpeg`/`ffprobe`; optional `aria2c`,
Deno/Node (YouTube JS challenges), and helper-6's `ghost_browser.py` / `proxy_pool.py` (imported lazily from the same folder).

## All options

| Option | Meaning |
|---|---|
| `URL [URL...]`, `--batch FILE` | links; batch file = one per line, `#` comments |
| `-o/--out DIR` | output folder (default `~/Downloads/video-grabber`, env `VG_OUT`) |
| `--quality best\|2160\|1440\|1080\|720\|480\|360` | height cap via `-S res:N` (best ≤ N, larger only if nothing smaller) |
| `--compat` | `-S vcodec:h264,acodec:m4a` + mp4 merge (editor friendly). 4K on YouTube has no H.264, so it may drop to 1080 |
| `--audio-only mp3\|m4a\|wav` | `-x --audio-quality 0` |
| `--subs ar,en` | `--write-subs --write-auto-subs --convert-subs srt` + `--embed-subs` |
| `--section A-B` | `--download-sections *A-B`; `--exact-cuts` re-encodes cut points (frame-exact) |
| `--playlist`, `--limit N` | default is `--no-playlist` |
| `--proxy auto\|none\|URL` | auto = direct first, rotate pool on 403/429/geo/network |
| `--proxy-file F`, `--proxy-tries N`, `--tor`, `--free-proxies` | pool sources (see proxy_pool.py) |
| `--browser-cookies chrome\|edge\|firefox\|brave\|opera\|chromium\|vivaldi`, `--cookies F` | auth |
| `--no-browser`, `--sniff`, `--sniff-wait S` | disable / force / tune the ghost-browser step |
| `--no-aria` | never use aria2c inside yt-dlp |
| `--info-json`, `--thumbnail` | extra side files (thumbnail embedded when no section) |
| `--info` | metadata only (`yt-dlp -J`; falls back to sniff listing) |
| `--json` | stdout = one JSON line only |
| `--update` | `pip install -U "yt-dlp[default]"` (includes yt-dlp-ejs) |

## Pipeline per URL

```
probe_direct (HEAD/GET Range 0-0, media Content-Type)  ── yes → aria2c x16 (-c resume) → retry x4
        │ no
yt-dlp (aria2c for http/https; native fragments -N 8 for HLS/DASH) ── fail → same with native downloader
        │ section + tls/failed → hls_section_local (only needed segments, certifi TLS) → else full + local cut
        │ forbidden / rate_limited / geo_blocked / network  and --proxy auto
proxy pool: next() → yt-dlp --proxy … → mark_bad on failure (up to --proxy-tries)
        │ unsupported / forbidden / failed / network / rate_limited  (not --no-browser)
GhostBrowser.sniff → drm? captcha? → media sorted by score:
        mp4/webm → aria2c with Referer/UA/cookies → yt-dlp with --add-headers/--cookies → (hls) local section → ffmpeg -c copy
        │
URL path looks like a media file → aria2c last resort
```

Terminal statuses (no further steps): `drm`, `private`, `removed`, `login_required`, `captcha`.

## Output

- Names: `%(title).150B [%(id)s].%(ext)s` with `--windows-filenames` (Arabic kept, `<>:"/\|?*` replaced).
  Sniffed/direct files use `safe_name()` (also strips bidi control marks, reserved names like `CON`).
- `sources.txt` in the output dir: `time<TAB>url<TAB>file<TAB>method[<TAB>stream=…]` — keep for credits/licensing.
- ffprobe facts per file: `duration, width, height, fps, vcodec, acodec, has_video, has_audio, subtitles, container, size_mb, verified`.
  `warning` is set when a video has no audio stream or ffprobe can't read it.

## JSON summary

```json
{"ok": true, "out_dir": "...", "done": 1, "failed": 0,
 "results": [{"url": "...", "ok": true, "status": "ok", "method": "yt-dlp",
   "files": [{"path": "...mkv", "duration": 19.02, "width": 320, "height": 240, "vcodec": "av1", "acodec": "opus",
              "has_audio": true, "verified": true, "size_mb": 0.45}],
   "attempts": [{"step": "yt-dlp", "proxy": "direct", "result": "ok", "error": ""}], "error": "", "hint": ""}]}
```
`method` values: `direct-aria2c`, `yt-dlp`, `yt-dlp+proxy`, `hls-local-section`, `yt-dlp-full+local-cut`,
`sniff+aria2c`, `sniff+yt-dlp`, `sniff+hls-local`, `sniff+ffmpeg`. Proxy credentials are masked (`//***@`).

## Known limitations

- This machine's ffmpeg 9 build fails TLS verification on some hosts (e.g. test-streams.mux.dev) while Python/certifi succeeds.
  Verification is never disabled; grab works around it by fetching bytes in Python. Encrypted HLS (`EXT-X-KEY`) is not handled by that local path.
- aria2c can't use SOCKS proxies (only http/https) — SOCKS proxies apply to yt-dlp/ffmpeg only.
- YouTube: very short/old videos may only exist as AV1/VP9; use `--compat` for H.264. Bot checks need cookies, not proxies.
- Sites that reset every connection from your IP (seen: test-videos.co.uk) fail with `network`; a proxy pool is the only remedy.
- Live streams download from "now" until stopped; use `--section` or Ctrl+C.
