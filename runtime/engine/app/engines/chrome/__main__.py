"""python -m engines.chrome <cmd> — drive the real Google Chrome (Dragon profile, CDP port 9222).

  doctor                          Chrome path/version, is the Dragon Chrome running
  launch [URL] [--headless]       open the Dragon Chrome window (idempotent)
  tabs | use N|TEXT | open URL | close [N] | go URL | back | forward | reload
  snapshot [--max 150]            numbered interactive elements (links/buttons/inputs) -> use with --ref
  text [--selector CSS] [--max N] page text          links          eval "JS expression"
  click (--ref N | --selector CSS | --text T | --xy X Y) [--double] [--right]
  type "VALUE" (--ref N | --selector CSS | --text T) [--enter] [--append]
  press KEY   scroll [DY]   wait (--selector CSS | --ms N)
  shot OUT.png [--full] [--selector CSS]     pdf OUT.pdf     quit
"""
import argparse, json, sys
from . import doctor, launch, quit, session


def _target_args(p):
    p.add_argument("--ref", type=int); p.add_argument("--selector"); p.add_argument("--text")


def main(argv=None):
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(prog="engines.chrome", description="تحكم التنين في Google Chrome",
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument("--port", type=int, default=None)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for n in ("doctor", "tabs", "back", "forward", "reload", "links", "quit"):
        sub.add_parser(n)
    x = sub.add_parser("launch"); x.add_argument("url", nargs="?"); x.add_argument("--headless", action="store_true")
    x = sub.add_parser("use"); x.add_argument("which")
    x = sub.add_parser("open"); x.add_argument("url", nargs="?", default="about:blank")
    x = sub.add_parser("close"); x.add_argument("which", nargs="?")
    x = sub.add_parser("go"); x.add_argument("url")
    x = sub.add_parser("snapshot"); x.add_argument("--max", type=int, default=150)
    x = sub.add_parser("text"); x.add_argument("--selector"); x.add_argument("--max", type=int, default=20000)
    x = sub.add_parser("eval"); x.add_argument("js")
    x = sub.add_parser("click"); _target_args(x); x.add_argument("--xy", nargs=2, type=float)
    x.add_argument("--double", action="store_true"); x.add_argument("--right", action="store_true")
    x = sub.add_parser("type"); x.add_argument("value"); _target_args(x)
    x.add_argument("--enter", action="store_true"); x.add_argument("--append", action="store_true")
    x = sub.add_parser("press"); x.add_argument("key")
    x = sub.add_parser("scroll"); x.add_argument("dy", nargs="?", type=float, default=800)
    x = sub.add_parser("wait"); x.add_argument("--selector"); x.add_argument("--ms", type=int)
    x = sub.add_parser("shot"); x.add_argument("out"); x.add_argument("--full", action="store_true"); x.add_argument("--selector")
    x = sub.add_parser("pdf"); x.add_argument("out")
    a = ap.parse_args(argv)
    kw = {"port": a.port} if a.port else {}

    if a.cmd == "doctor":
        out = doctor(**kw)
    elif a.cmd == "launch":
        out = launch(a.url, a.headless, **kw)
    elif a.cmd == "quit":
        out = quit(**kw)
    else:
        with session(**kw) as s:
            c = a.cmd
            out = (s.tabs() if c == "tabs" else
                   s.use(a.which) if c == "use" else
                   s.open(a.url) if c == "open" else
                   s.close(a.which) if c == "close" else
                   s.go(a.url) if c == "go" else
                   s.nav(c) if c in ("back", "forward", "reload") else
                   s.snapshot(a.max) if c == "snapshot" else
                   s.text(a.selector, a.max) if c == "text" else
                   s.links() if c == "links" else
                   s.evaluate(a.js) if c == "eval" else
                   s.click(a.ref, a.selector, a.text, a.xy, "right" if a.right else "left", a.double) if c == "click" else
                   s.type(a.value, a.ref, a.selector, a.text, a.enter, a.append) if c == "type" else
                   s.press(a.key) if c == "press" else
                   s.scroll(a.dy) if c == "scroll" else
                   s.wait(a.selector, a.ms) if c == "wait" else
                   s.shot(a.out, a.full, a.selector) if c == "shot" else
                   s.pdf(a.out))
    print(json.dumps(out, ensure_ascii=False, indent=1, default=str))


if __name__ == "__main__":
    try:
        main()
    except (PermissionError, LookupError, ValueError, ConnectionError, TimeoutError, FileNotFoundError) as e:
        print(json.dumps({"error": type(e).__name__, "message": str(e)}, ensure_ascii=False))
        sys.exit(2)
