# Fast rendering on Higgsfield (the owner's choice, 2026-11-23)

The owner chose: **every heavy render (frames, ffmpeg encodes, Whisper, many downloads) runs on the
Higgsfield cloud sandbox, size XL** — free, the fastest and strongest free machine we have. Use it by
default; do not ask again. Use the local machine only for small checks, or when Higgsfield is not connected.

## What it is (measured)

| Machine | CPUs | Cost | Limits |
|---|---|---|---|
| Higgsfield sandbox `size: "xl"` | 4 | free | background job ≤ 15 min; `/home/user` kept 24 h; internet yes |
| Higgsfield sandbox standard | 1 | free | same; use for downloads, probes, polling |
| Higgsfield GPU rental (`gpu_rent`) | GPU | **paid: needs the owner's «أيوه» first** | only for 3D/AI models, not for canvas/ffmpeg |

Measured speeds: lyric motion 1080x1920 canvas ≈ 1 s/frame with 4 Playwright workers on XL;
dua reel ≈ 0.47 s/frame; a 45 s reel (1,347 frames) ≈ 15-25 min on XL, ≈ 50 min on 1 CPU.
Preinstalled: ffmpeg, Playwright + Chromium (`npm root -g` → link it as `node_modules`), faster-whisper,
ImageMagick, Pillow. pip only with `HOME=/home/user pip install --target /home/user/pylib …`.

## The workflow

1. **Push the job in:** zip the work folder (engine, fonts, plan, signed upload URLs for the outputs);
   `media_upload` → `curl -X PUT` (one PUT per URL) → `media_confirm` → in the sandbox `curl` it from
   `d2ol7oe51mr4n9.cloudfront.net/<user>/<media_id>.zip` and unzip.
2. **Start on XL:** `sandbox_exec` with `size: "xl"` and `background: true`, running
   `agent/cloud_render/render_job.sh`. XL refuses to start while another background job runs: wait or kill
   that job by PID first (never `pkill -f`, it kills its own shell).
3. **Check `nproc`** on the first poll: a replaced sandbox can come back with 1 CPU; if so, restart on XL.
4. **Poll** every ~50 s (`sleep 50` inside one call; calls time out at 60 s). After 15 min the job stops
   (exit 124): run the same script again, it skips finished frames.
5. **Bring it back:** the script PUTs the MP4 to the signed URL; `media_confirm` it; download it from the CDN
   in the local container; verify (frames sheet, loudness, first frame not black) and deliver with
   `tools/video-page/video_page.py`.
6. **Fix one scene** without a full render: delete only that scene's frames (line start − 0.3 s to next line
   + 0.3 s) and run the job again.

The environment's network allowlist needs `upload.higgsfield.ai` and `d2ol7oe51mr4n9.cloudfront.net`.
