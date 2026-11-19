"""Fast video download, IDM-style: one file split into many parts downloaded in parallel, with resume.

usage:
  python fast_dl.py URL [URL ...] [--out DIR] [--conn 16] [--audio] [--max 1080]

- Direct file links (.mp4 .mov .webm .mkv .mp3 .wav .zip ...) go to aria2c (16 connections, resumable).
- Page links (YouTube, Vimeo, Pexels pages and every yt-dlp site) go to yt-dlp, which uses aria2c as its downloader
  and grabs several stream fragments at once.
Only download what you own or are licensed to use. Never bypass DRM or paywalls.
"""
import argparse, os, re, shutil, subprocess, sys
from pathlib import Path

DEFAULT_OUT = Path(r"C:\Users\cinde\OneDrive\Desktop\المونتاج\01_raw\downloads")
DIRECT = re.compile(r"\.(mp4|mov|m4v|webm|mkv|avi|mp3|m4a|wav|flac|aac|zip|png|jpg|jpeg|gif|cube|ttf|otf)(\?|$)", re.I)


def find(exe):
    p = shutil.which(exe)
    if p:
        return p
    root = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Packages"
    hits = list(root.glob(f"**/{exe}.exe"))
    return str(hits[0]) if hits else None


def is_direct(url):
    """True when the server sends a media/binary file, False for a web page. Asks the server, not the URL text."""
    import urllib.request
    if not DIRECT.search(url):
        return False
    for method in ("HEAD", "GET"):
        try:
            req = urllib.request.Request(url, method=method, headers={"User-Agent": "Mozilla/5.0", "Range": "bytes=0-0"})
            with urllib.request.urlopen(req, timeout=20) as r:
                ctype = (r.headers.get("Content-Type") or "").lower()
            return not ctype.startswith(("text/", "application/xhtml"))
        except Exception:
            continue
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("urls", nargs="+")
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--conn", type=int, default=16)
    ap.add_argument("--audio", action="store_true", help="audio only (best quality, original codec)")
    ap.add_argument("--max", type=int, default=1080, help="max video height for page links")
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    aria = find("aria2c")
    conn = str(max(1, min(a.conn, 16)))
    for url in a.urls:
        if is_direct(url):
            if not aria:
                sys.exit("aria2c not found: winget install -e --id aria2.aria2")
            cmd = [aria, "-x", conn, "-s", conn, "-k", "1M", "-c", "--file-allocation=none",
                   "--console-log-level=warn", "--summary-interval=0", "-d", str(out), url]
        else:
            fmt = "bestaudio/best" if a.audio else f"bv*[height<={a.max}]+ba/b[height<={a.max}]"
            cmd = ["yt-dlp", "-f", fmt, "-N", "8", "--no-playlist", "--restrict-filenames",
                   "-o", str(out / "%(title).80s [%(id)s].%(ext)s"), "--merge-output-format", "mp4"]
            if aria:
                cmd += ["--downloader", aria, "--downloader-args", f"aria2c:-x {conn} -s {conn} -k 1M"]
            cmd.append(url)
        print(">>", url, flush=True)
        r = subprocess.run(cmd)
        if r.returncode != 0:
            # some servers refuse many connections (HTTP 429): retry gently, resuming the partial file
            print("retrying with fewer connections ...", flush=True)
            if cmd[0] == aria:
                cmd = [c if c not in (conn,) else "4" for c in cmd]
            else:
                i = cmd.index("--downloader") if "--downloader" in cmd else None
                if i is not None:
                    del cmd[i:i + 4]  # drop aria2c, use yt-dlp's own downloader
                # aria2's partial file is not resumable by yt-dlp, so start that file again
                cmd.insert(-1, "--no-continue")
            r = subprocess.run(cmd)
        print("OK" if r.returncode == 0 else f"FAILED ({r.returncode})", flush=True)


if __name__ == "__main__":
    main()
