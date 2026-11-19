"""python -m engines.kosif <cmd> — KOSIF accelerated downloads from the Black Dragon.

  doctor                                   app location, running?, browser host, ffmpeg, yt-dlp
  probe URL [--referer R]                  file name, size, resumable, type (no download)
  fetch URL [URL..] [-o DIR] [-c 8] [--video] [--name F] [--quality best|2160|1080|720|480|audio]
        [--limit KB/s] [--proxy P] [--referer R] [--cookies "a=b; c=d"] [--json]
                                           download headless into DIR, wait, verify (size, SHA-256, ffprobe)
  send URL [URL..] [--video] [--quality Q] [--show]   queue in the KOSIF desktop app
  list                                     downloads in the desktop app
  pause|resume|restart|remove ID           act on one app download
  pause_all|resume_all|clear_done          act on all app downloads
  open | quit                              show the KOSIF window | stop the app
"""
import argparse
import json
import sys

from . import (app_action, app_list, app_open, app_quit, doctor, fetch, human, probe, send)


def main(argv=None):
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(prog="engines.kosif", description="KOSIF — تحميل مسرّع للتنين الأسود",
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for n in ("doctor", "list", "open", "quit", "pause_all", "resume_all", "clear_done"):
        sub.add_parser(n)
    x = sub.add_parser("probe"); x.add_argument("url"); x.add_argument("--referer", default="")
    x = sub.add_parser("fetch"); x.add_argument("urls", nargs="+"); x.add_argument("-o", "--out", default=".")
    x.add_argument("-c", "--connections", type=int, default=8); x.add_argument("--video", action="store_true")
    x.add_argument("--file", action="store_true", help="force a direct file download (no yt-dlp)")
    x.add_argument("--name", default=""); x.add_argument("--quality", default="best")
    x.add_argument("--limit", type=int, default=0); x.add_argument("--proxy", default="")
    x.add_argument("--referer", default=""); x.add_argument("--cookies", default="")
    x.add_argument("--no-verify", action="store_true"); x.add_argument("--json", action="store_true")
    x = sub.add_parser("send"); x.add_argument("urls", nargs="+"); x.add_argument("--video", action="store_true")
    x.add_argument("--quality", default="best"); x.add_argument("--referer", default=""); x.add_argument("--show", action="store_true")
    for n in ("pause", "resume", "restart", "remove"):
        x = sub.add_parser(n); x.add_argument("id")
    a = ap.parse_args(argv)

    if a.cmd == "doctor":
        out = doctor()
    elif a.cmd == "probe":
        out = probe(a.url, a.referer)
    elif a.cmd == "fetch":
        kind = "video" if a.video else "http" if a.file else "auto"
        res = fetch(a.urls, a.out, a.connections, kind, a.name, a.quality, a.referer, a.cookies, a.limit, a.proxy,
                    verify=not a.no_verify, log=lambda s: print(s, file=sys.stderr, flush=True))
        if a.json:
            out = res
        else:
            for r in res:
                if r["status"] == "done":
                    extra = r.get("media") or {}
                    dims = f" {extra.get('width')}x{extra.get('height')}" if extra.get("width") else ""
                    dur = f" {extra['duration']}s" if extra.get("duration") else ""
                    print(f"✓ {r['path']}  {human(r['size'])}{dims}{dur}  sha256={r.get('sha256', '')[:16]}")
                else:
                    print(f"✕ {r['url']}  {r['error']}")
            sys.exit(0 if all(r["status"] == "done" for r in res) else 1)
    elif a.cmd == "send":
        out = send(a.urls, "video" if a.video else "auto", a.quality, a.referer, a.show)
    elif a.cmd == "list":
        out = app_list()
    elif a.cmd in ("pause", "resume", "restart", "remove"):
        out = app_action(a.cmd, a.id)
    elif a.cmd in ("pause_all", "resume_all", "clear_done"):
        out = app_action(a.cmd)
    elif a.cmd == "open":
        out = app_open()
    else:
        out = app_quit()
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
