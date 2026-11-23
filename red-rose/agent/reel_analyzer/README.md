# Reel analyzer (تحليل ريلز حساب: لقطات، حركة كاميرا، انتقالات، صوت، كلام)

`analyze.py pick.json OUT [workers]` — run in the Higgsfield sandbox (yt-dlp with `--impersonate chrome`,
faster-whisper, OpenCV in `/home/user/pylib`). For each video in `pick.json` (`id`, `url`, `date`, `plays`,
`desc`) it downloads, measures and deletes the video, keeping `OUT/<id>/a.json` and one frame per shot:

- shots: ffmpeg scene score > 0.25, hits closer than 0.35 s merged; shot length;
- camera move per shot: ORB features + `estimateAffinePartial2D` between frames 0.6 s apart →
  still / zoom_in / zoom_out / rotate / pan_x / pan_y with per-second rates;
- transition look at each cut from luma and sharpness around it → cut / flash / dip / blur_move;
- loudness (EBU R128), mean colour per shot, Whisper words with times, speech start, words per second.

Resumable: finished videos are skipped. Use `base` Whisper on a 1-CPU sandbox, `small` on XL.
`label_sheets.py list.txt OUTDIR` makes labelled contact sheets from `code<TAB>thumbnail-url` lines.
Pick the 60 most viewed plus the 60 latest; 85 to 114 reels were enough for stable medians.
