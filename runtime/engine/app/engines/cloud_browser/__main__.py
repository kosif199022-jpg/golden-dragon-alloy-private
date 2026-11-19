"""python -m engines.cloud_browser doctor | start [--port 8800] [--host 127.0.0.1] [--open] [-- server args] | stop | status | url | serve [server args]"""
import argparse, json, runpy, sys
from . import HERE, doctor, start, stop, status


def main(argv=None):
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(prog="engines.cloud_browser", description="سحاب — متصفح سحابي (Chromium بيتبث لايف)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("doctor"); sub.add_parser("stop"); sub.add_parser("status"); sub.add_parser("url")
    s = sub.add_parser("start", help="شغّله في الخلفية")
    s.add_argument("--port", type=int, default=8800); s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--open", action="store_true", help="افتح الواجهة في المتصفح الافتراضي")
    s.add_argument("rest", nargs=argparse.REMAINDER, help="خيارات إضافية للسيرفر بعد --")
    sv = sub.add_parser("serve", help="شغّله في الواجهة الأمامية (نفس خيارات server.py)")
    sv.add_argument("rest", nargs=argparse.REMAINDER)
    a = ap.parse_args(argv)
    if a.cmd == "doctor":
        out = doctor()
    elif a.cmd == "start":
        rest = a.rest[1:] if a.rest[:1] == ["--"] else a.rest
        out = start(a.port, a.host, a.open, rest)
    elif a.cmd == "stop":
        out = stop()
    elif a.cmd == "status":
        out = status()
    elif a.cmd == "url":
        st = status()
        print(st.get("url") or "مش شغال — شغّله بـ: python -m dragon run cloud_browser start")
        return
    else:  # serve
        sys.argv = [str(HERE / "server.py"), *a.rest]
        runpy.run_path(str(HERE / "server.py"), run_name="__main__")
        return
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
