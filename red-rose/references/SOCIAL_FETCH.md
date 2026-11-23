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

## More that worked (2026-11-23, second round)

| Need | Way that worked | Cost |
|---|---|---|
| A TikTok profile's numbers (followers, video count) | ScrapeCreators `/v1/tiktok/profile?handle=…` | 1 credit |
| Instagram reels by topic (not by account) | ScrapeCreators `/v2/instagram/reels/search?query=…` (key `reels`; each has a link and a thumbnail) | 1 credit / page |
| Pinterest clips per scene of a song | one `/v1/pinterest/search` per line idea («rain window», «hands holding», «old book pages»…), keep 16 to 18 video pins per idea, then a labelled contact sheet of their thumbnails to choose from | 1 credit / idea |
| Lyrics of a sung song | Whisper garbles singing: read the burnt-in captions from frames (one frame per caption change) and use Whisper only for the times | free |
| A whole account's audio, sorted by day | read all posts with `/v3/tiktok/profile/videos`, label each by the day or occasion named in the caption (friday, friday_night, sunday … ramadan, eid), then yt-dlp `-x` in the sandbox in resumable 14-minute runs | credits for the list only |
| Camera moves and transitions of a reference | in the sandbox: OpenCV ORB features + `estimateAffinePartial2D` between frames 0.6 s apart gives zoom in/out, rotate, pan; luma and sharpness around each cut tell flash, dip, blur-move or plain cut | free |

- TikTok gives hashtags, region, music and post time per video (`desc`, `region`, `music`, `create_time`); POI is usually empty.
- Audio of other creators (dua voices) is for private study only. To publish, use TikTok's "use this sound" in the app, or the owner's own voice.
- GitHub from the cloud: files up to 100 MB each can be pushed to a branch of the private repo; for bigger libraries keep a CDN copy and put the links in a catalogue CSV in Git.
