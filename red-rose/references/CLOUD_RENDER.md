# Rendering on Higgsfield: fallback only (superseded 2026-11-24)

> Since 2026-11-24 render **locally first**; see `SPEED_AUDIT_2026-11-24.md`. Keep this page for jobs the
> local machine cannot run, and for downloads the local network refuses.


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

## Where the hour goes (measured 2026-11-24 on a 59 s dua reel)

| Stage | Time on XL |
|---|---|
| Cut 18 clips to frames | 16 s |
| Render 1,775 frames, 4 workers | 171 s (0.1 s a frame) |
| Encode, preset slow | 85 s |
| Encode, preset veryfast (crf 18, same look, 20 % smaller) | 24 s |
| Download the result | 1 s |

The machine needs about 4 minutes. The same request took 153 minutes end to end: 124 of them were four
restarts of the Claude cloud session, where nothing ran until the next event arrived. Each restart came right
after a `sandbox_exec` poll timed out at 60 s.

Rules from this:
1. Poll with `sleep 30` at most (the tool call itself times out at 60 s; `sleep 55` + overhead times out).
2. Encode with `-preset veryfast -crf 18` (`render_job.sh` does); keep `slow` only when asked.
3. Make the job deliver itself: render, encode, upload and build the page parts inside one background job, so a
   dropped session loses nothing.
4. Before the full render, render one frame per line and check that every line fits and reads; a fix found
   after the full render costs a second render.
5. Always `size: "xl"`; a 1-CPU sandbox is about 4x slower.
