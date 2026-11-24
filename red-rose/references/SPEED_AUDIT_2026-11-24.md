# Speed audit, 2026-11-24: where the hours went

Measured from the session transcript (21-24 Nov 2026, 4,464 events, 336 Higgsfield sandbox calls).

| What | Measured |
|---|---|
| Higgsfield `sandbox_exec` calls | 336; median 32 s; **65 took over 3 min** (some 1-4 h) though each had a 60-90 s timeout |
| Time inside those calls | **1,969 min (~33 h)**; growing by day: 21 Nov 333 min, 23 Nov 676 min, 24 Nov 789 min |
| Session worker restarts | 39; 27 of them right after a sandbox call that never came back |
| Every other tool (Bash, Artifact, GitHub, uploads) | 438 Bash calls, 79 min in total; Artifact, upload and GitHub calls about 2 min in total |
| Local render of the same 810-frame cartoon | **9.5 s render + 10 s encode** on this container (4 CPU, 15 GB) vs 60 s on Higgsfield XL |
| Session transcript | 75 MB after three days and two context compactions: each restart and each step reloads all of it |

The renders themselves were never the slow part (1-5 min). The hours were sandbox calls that hung, then
the session restarting and reloading a very long conversation.

## Rules from now on

1. **Render, encode, Whisper and sound locally.** Playwright + Chromium, ffmpeg, faster-whisper, yt-dlp
   and sox are in the container (`sox` is now in the setup script).
2. **The Higgsfield sandbox is only for downloads the local network refuses** (TikTok, Instagram and
   Pinterest CDNs). One short call: download, then PUT to a signed URL; bring the file in from
   `d2ol7oe51mr4n9.cloudfront.net`. No polling loops, no image previews from the sandbox.
3. **Media for the fast lane**: zip the 10-20 selected clips in one sandbox call and bring them in once,
   instead of rendering there.
4. **Start a new session per big job** (one reel, one analysis). A three-day session with two compactions
   is slow on every step; the repos keep everything, so nothing is lost.
