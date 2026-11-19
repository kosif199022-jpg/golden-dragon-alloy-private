# Per-site notes

General rule: try plain `grab.py URL` first; add cookies only when the status says `login_required`.
Keep yt-dlp fresh (`grab.py --update`) — site extractors break often.

| Site | What works | Notes |
|---|---|---|
| YouTube / Shorts | yt-dlp | Needs Deno/Node for JS challenges (installed). "Sign in to confirm you're not a bot" → `--browser-cookies chrome`. Best quality is VP9/AV1 + Opus → mkv; `--compat` gives H.264/AAC mp4 (≤1080p). Playlists/channels: `--playlist --limit N`. Members/age-gated → cookies. |
| TikTok | yt-dlp | Photo posts (slideshows) are not video. If 403 → `--update`, then `--proxy auto`. Watermark-free when the API exposes it. |
| Instagram (reels/posts/stories) | yt-dlp + `--browser-cookies` | Mostly requires login now. Stories always need cookies. Carousels download every item. |
| Facebook / fb.watch | yt-dlp | Public videos work; group/private need cookies. Reels OK. |
| X / Twitter | yt-dlp | Some posts need login (cookies). Multiple videos in one post → all items. |
| Vimeo | yt-dlp | Private-link (unlisted hash) works with the full URL; password videos: add `--video-password` manually via yt-dlp. Vimeo OTT/On-Demand may be DRM. |
| Dailymotion, Twitch VODs/clips, Reddit, Bilibili, SoundCloud, Rumble, Odysee, Streamable, archive.org | yt-dlp | Twitch live: use `--section` or stop manually. |
| Telegram public posts (t.me/channel/123) | yt-dlp | Private channels not supported. |
| News sites / embedded players (JW Player, Brightcove, Kaltura, video.js) | yt-dlp generic, else ghost-browser sniff | sniff follows iframes, finds m3u8/mpd/mp4 and carries Referer. |
| Plain pages with `<video>` (e.g. w3schools) | yt-dlp generic or `--sniff` | Both verified. |
| Direct links (.mp4/.webm/.mov/.mp3…) | aria2c x16, resume | If a CDN rejects many connections it retries with 4. |
| Raw HLS/DASH (.m3u8/.mpd) | yt-dlp (native fragments) | `--section` uses the local segment fetch when ffmpeg TLS fails. |
| Netflix, Disney+, Prime Video, Shahid VIP, OSN+, Spotify, Apple TV+, most paid live TV | **DRM — not possible** | Reported as `drm`. Do not attempt circumvention. |
| Sites behind Cloudflare challenge / CAPTCHA | report `captcha` | User passes the check in a real browser, then `--browser-cookies`. Never auto-solve. |

Cookie tips: Chrome/Edge lock their cookie DB while running on Windows — if `--browser-cookies` fails, close the
browser, use Firefox, or export with `ghost_browser.py cookies URL cookies.txt` after logging in via `--headful --profile DIR`.
