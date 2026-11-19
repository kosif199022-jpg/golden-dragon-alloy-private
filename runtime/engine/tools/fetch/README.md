# tools/fetch — TikTok photo posts

`tiktok_post.py` saves the pictures and the sound of a TikTok **photo post** (a slideshow of pictures
over a sound) so the owner can edit with them.

## When to use it

Use it when yt-dlp refuses a photo post:

```
ERROR: Unsupported URL: https://www.tiktok.com/@user/photo/7702414294251523348
```

A short link (`https://vt.tiktok.com/XXXX/`) that ends at a `/photo/` page gives the same error.
For **video** posts keep using yt-dlp. This tool only saves the sound of a video post.

## Commands

From the skill folder (cloud or PC):

```
python3 tools/fetch/tiktok_post.py https://vt.tiktok.com/XXXX/ --out out/tiktok-post
python3 scripts/dragon.py tool tiktok-post https://vt.tiktok.com/XXXX/ --out out/tiktok-post
```

Windows:

```
py tools\fetch\tiktok_post.py https://vt.tiktok.com/XXXX/ --out "%USERPROFILE%\Desktop\منشور تيك توك"
```

| option | effect |
|---|---|
| `--no-images` | save only the sound |
| `--no-music` | save only the pictures |
| `--html FILE` | read a saved copy of the post page instead of downloading it (the links inside must still work) |

Exit codes: `0` everything asked for was saved · `1` the post could not be read, or a file failed (the reason is
printed and kept in `manifest.json`) · `2` wrong arguments.

## What it saves

| file | content |
|---|---|
| `00.jpg`, `01.jpg` … | the pictures in post order, at the size the page declares (often not 9:16, e.g. 1080×178 up to 1080×1920) |
| `music.mp3` | the post's sound as TikTok serves it (usually MP3 128 kbps, 44.1 kHz stereo) |
| `manifest.json` | `source_url`, `resolved_url`, `id`, `creator`, `desc`, `music_title`, `music_author`, `files`, `failed`, `skipped`, `fetched_at`, `note` |

If the CDN sends another format, the extension follows the real bytes: `.webp`/`.png`/`.heic` for a picture,
`.m4a`/`.aac` for the sound.

**Before the sound goes into a film:** an MP3 must not be copied into an MP4 as is, because it plays silent on
iPhone. `dragon mux` re-encodes it to AAC, and `engines/qa.audio_check` flags the problem.

Live check (2026-11-08, from this cloud sandbox): a 9-picture post saved 9 JPEGs (8–67 KB each, sizes equal to
the page's `imageWidth`×`imageHeight`) and a 57.65 s MP3, in about 5 s.

## How it works

1. One GET of the link with a stock iPhone Safari User-Agent. The tool follows the short-link redirect, keeps
   cookies in memory for this run only, and uses no login or account. Nothing about the owner is sent.
2. It reads the JSON in `<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__">`, then
   `__DEFAULT_SCOPE__["webapp.reflow.video.detail"]` (phone page) or `["webapp.video-detail"]` (desktop page),
   then `itemInfo.itemStruct`.
3. The pictures come from `imagePost.images[].imageURL.urlList[0]`, and from `urlList[1]` when the first link
   fails. The sound comes from `music.playUrl`. Each file is written through a `.part` file. A cut download is
   tried once more, and a web page served in place of a picture counts as a failure.
4. `resolved_url` is stored without its query: resolved share links carry the sharer's account ids.

Python 3.8+ standard library only. Windows, macOS and Linux all work, and Arabic folder names are fine.

## Limits

- **Login wall, captcha, region block, private or removed post:** the JSON block is missing, so the tool exits
  `1` and says why. It never tries to get around this. Cloud machines are sometimes blocked: then run it on the
  owner's PC, or ask the owner for the pictures and the sound.
- **The links inside the page are signed and expire** within hours. Run the tool again rather than reusing old links.
- **The sound can be missing** (muted, or not offered in that region). This is noted in `skipped`, and the
  pictures are still saved.
- **One post per run.** Use a new folder for each post: files from an earlier run that have other names are left alone.
- **TikTok changes its page now and then.** If parsing breaks, update `SCOPES` and the paths in
  `tiktok_post.py` together with the synthetic page `app/tests/fixtures/tiktok_photo_post.html`.

## Rights

The files are **for the owner's personal editing; rights stay with the post creator**. This is written into
every manifest. Credit the creator (`creator` in the manifest), and do not republish their pictures or sound
without their permission.

## Tests

```
cd app && python3 -m pytest -q tests/test_v12_tiktok_post.py
```

The tests run offline: the synthetic page is checked under both scope names, along with broken pages, and the
CLI and `fetch()` run against a loopback server. That server plays the short link, the post page and the CDN,
using tiny media made with ffmpeg.
