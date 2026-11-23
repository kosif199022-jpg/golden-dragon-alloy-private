# Getting reference videos from the cloud (measured 2026-11-23)

A Claude Code cloud container cannot reach Instagram, TikTok or Pinterest directly (the network policy
refuses the hosts). What worked, in order:

| Need | Way that worked | Cost |
|---|---|---|
| One Instagram reel | `yt-dlp` inside the Higgsfield sandbox (`sandbox_exec`), then `media_upload` + PUT, then curl it back | free |
| One TikTok video | same, but `yt-dlp[default,curl-cffi]` installed with `--target /home/user/pylib` and `--impersonate chrome`; plain yt-dlp gets "Unexpected response" | free |
| A whole Instagram account | ScrapeCreators `/v2/instagram/user/posts?handle=…` (12 posts a page, 1 credit a page). instaloader, yt-dlp, the embed page, Playwright and mirror sites were all refused from datacentre IPs | 1 credit / 12 posts |
| A whole TikTok account | ScrapeCreators `/v3/tiktok/profile/videos?handle=…&max_cursor=…` (10 a page) | 1 credit / 10 videos |
| Pinterest clips by look | ScrapeCreators `/v1/pinterest/search?query=…` (16 to 25 pins a page); every video pin carries a `v1.pinimg.com/videos/…m3u8` link that ffmpeg copies to mp4 in the sandbox | 1 credit / page, download free |
| Stock footage with a licence | Wikimedia Commons API (CC0 / CC BY / CC BY-SA) and Mixkit (free licence), both reachable from the sandbox; Pexels refuses datacentre IPs | free |

Notes
- The ScrapeCreators key is saved as a network secret on the cloud environment (header `x-api-key`); the
  proxy adds it, so code never sees it. Balance: `GET /v1/credit-balance`.
- The environment allowlist needs `d2ol7oe51mr4n9.cloudfront.net` (Higgsfield media, to pull results back)
  and `upload.higgsfield.ai` (to push code and data into the sandbox).
- The standard sandbox has 1 CPU; use `size: "xl"` (4 CPUs) for Whisper or many ffmpeg jobs, and run long
  work with `background: true` (15 minutes a job; make jobs resumable).
- A signed upload URL accepts one PUT (`If-None-Match`); a second PUT returns 412, a broken one 400:
  ask for a new URL.
- Downloaded reels of other accounts are for measuring style. Keep numbers, frames and transcripts; delete
  the videos; never republish their footage or voice.
