---
name: kosif-downloads
description: KOSIF «كوسيف» — مدير تحميل مسرّع زي Internet Download Manager مدموج في التنين الأسود. بينزّل أي لينك مباشر بتعدد اتصالات لحد 32 مع تقسيم ديناميكي، ويكمّل التحميل المقطوع، وينزّل فيديوهات يوتيوب وتيك توك وانستجرام وفيسبوك وX وm3u8 بأعلى جودة عن طريق yt-dlp، وبيقيس كل ملف (الحجم وSHA-256 والمدة والأبعاد)، وبيتحكم في برنامج KOSIF وإضافته على كروم وإيدج. Use for «نزّل/حمّل الملف ده»، «تحميل سريع/مسرّع»، «داونلود»، «كمّل التحميل»، «نزّل فيديو/فوتيج/خامات»، «مدير تحميل»، «IDM / انترنت داونلود مانجر»، «KOSIF», accelerated download, download manager, resume download, multi-connection download, fetch video from page.
---

# KOSIF downloads (Black Dragon engine `kosif`)

Run from `%USERPROFILE%\OneDrive\Desktop\مهارات\التنين الأسود` (or `%BLACK_DRAGON_HOME%`):
```
python -m dragon run kosif doctor
python -m dragon run kosif probe URL                                  # name, size, resumable — no download
python -m dragon run kosif fetch URL [URL..] -o WORKDIR -c 16         # wait + verify (path, size, SHA-256, duration/WxH)
python -m dragon run kosif fetch PAGE_URL --video --quality 1080 -o WORKDIR   # best|2160|1080|720|480|audio
python -m dragon run kosif fetch URL --referer PAGE --cookies "a=b" --limit 2048 --proxy socks5://127.0.0.1:1080 --json
python -m dragon run kosif send URL [--video] [--show]                # queue in the user's KOSIF window
python -m dragon run kosif list | pause ID | resume ID | remove ID | open | quit
```
Python: `from engines import kosif; kosif.fetch(urls, out, connections=16)` returns measured records.

Facts (tested in `tests/test_mod_kosif.py`): byte-exact SHA-256 with 8 connections, no-Range fallback to one
connection, servers capping connections (failing connections give their range back), fast fail on 401/403/404/410,
resume of an interrupted run when the same link is fetched into the same folder.

Rules: write every downloaded media source to the work folder's `sources.txt`; respect site terms and licences;
never use it to bypass paywalls, DRM or logins the user does not own. The desktop app is `Desktop\KOSIF\KOSIF.exe`
(Chrome/Edge extension in `Desktop\KOSIF\extension`, native host `com.kosif.dm`).
