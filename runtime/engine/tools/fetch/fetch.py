#!/usr/bin/env python3
"""Fetch media at the best quality and log where it came from (sources.txt), so every asset in a job is credited.

    python fetch.py URL [URL...] --dir JOB [--audio] [--max 2160] [--licence "CC BY 4.0"] [--note "..."]
    python fetch.py --sources JOB          # print the job's sources.txt

Video/audio pages -> yt-dlp (best video+audio, merged to MP4/M4A, original title kept).
Direct files (.jpg .png .webp .mp4 .wav ...) -> aria2c (16 connections) or urllib.
Every success appends one line to JOB/sources.txt: date | file | url | licence | note.
Only download what you have the right to use; this tool never bypasses DRM or logins.
"""
import argparse, datetime, json, shutil, subprocess, sys, urllib.parse, urllib.request
from pathlib import Path

DIRECT = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".tif", ".tiff", ".svg", ".mp4", ".mov", ".webm", ".mkv",
          ".wav", ".mp3", ".flac", ".m4a", ".ogg", ".zip", ".pdf", ".exr", ".hdr", ".blend", ".glb", ".fbx", ".obj"}


def is_direct(url):
    return Path(urllib.parse.urlparse(url).path).suffix.lower() in DIRECT


def log(job, file, url, licence="", note=""):
    line = " | ".join([datetime.date.today().isoformat(), Path(file).name, url, licence or "?", note]).rstrip(" |")
    with open(Path(job) / "sources.txt", "a", encoding="utf-8") as f:
        f.write(line + "\n")
    return line


def direct(url, job):
    name = Path(urllib.parse.unquote(urllib.parse.urlparse(url).path)).name or "download.bin"
    out = Path(job) / name
    if shutil.which("aria2c"):
        r = subprocess.run(["aria2c", "-x16", "-s16", "-k1M", "--allow-overwrite=false", "--auto-file-renaming=true",
                            "-d", str(job), "-o", name, url], capture_output=True, text=True, encoding="utf-8", errors="replace")
        if r.returncode == 0 and out.exists():
            return out
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 BlackDragon"})
    with urllib.request.urlopen(req, timeout=120) as resp, open(out, "wb") as f:
        shutil.copyfileobj(resp, f)
    return out


def page(url, job, audio=False, max_h=2160):
    ytdlp = shutil.which("yt-dlp") or [sys.executable, "-m", "yt_dlp"]
    base = [ytdlp] if isinstance(ytdlp, str) else ytdlp
    tmpl = str(Path(job) / "%(title).80B [%(id)s].%(ext)s")
    if audio:
        fmt = ["-f", "bestaudio/best", "-x", "--audio-format", "m4a", "--audio-quality", "0"]
    else:
        fmt = ["-f", f"bv*[height<={max_h}]+ba/b[height<={max_h}]/bv*+ba/b", "--merge-output-format", "mp4",
               "-S", f"res:{max_h},fps,vcodec:h264,acodec:m4a"]
    cmd = base + fmt + ["--no-playlist", "--restrict-filenames", "-N", "8", "--print", "after_move:filepath", "-o", tmpl, url]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode:
        raise RuntimeError((r.stderr or r.stdout)[-800:])
    paths = [l.strip() for l in r.stdout.splitlines() if l.strip() and Path(l.strip()).exists()]
    if not paths:
        raise RuntimeError("yt-dlp finished but no file was reported")
    return Path(paths[-1])


def main(argv=None):
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(prog="fetch", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("urls", nargs="*"); ap.add_argument("--dir", default=".")
    ap.add_argument("--audio", action="store_true"); ap.add_argument("--max", type=int, default=2160)
    ap.add_argument("--licence", default=""); ap.add_argument("--note", default=""); ap.add_argument("--sources")
    a = ap.parse_args(argv)
    if a.sources:
        p = Path(a.sources) / "sources.txt"
        print(p.read_text(encoding="utf-8") if p.exists() else "(no sources.txt yet)"); return 0
    if not a.urls:
        ap.print_help(); return 2
    job = Path(a.dir); job.mkdir(parents=True, exist_ok=True)
    rows, bad = [], 0
    for url in a.urls:
        try:
            out = direct(url, job) if is_direct(url) else page(url, job, a.audio, a.max)
            rows.append({"ok": True, "file": str(out), "bytes": out.stat().st_size, "source": log(job, out, url, a.licence, a.note)})
        except Exception as e:  # keep going, report each failure
            bad += 1; rows.append({"ok": False, "url": url, "error": str(e)[-400:]})
    print(json.dumps(rows, ensure_ascii=False, indent=1))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
