#!/usr/bin/env python3
"""Black Dragon stock: free, open-licence footage and photos with a licence sidecar per file and ATTRIBUTION.md.

صور وفيديو مجانية للمونتاج: بحث وتحميل، ومع كل ملف ترخيصه (<file>.json) وسطر النسب (ATTRIBUTION.md).

    dragon.py tool stock search "night city" [--kind video|photo] [--orientation portrait] [--limit 6] [--commercial] ...
    dragon.py tool stock download ID... --out DIR [--kind video|photo] [--quality 1080] [--max-mb MB] [--dry-run]
    dragon.py tool stock sources [--kind video|photo]      # offline: the sites and their licences
    dragon.py tool stock credits DIR [--kind video|photo]  # offline: rebuild DIR/ATTRIBUTION.md from the sidecars
    dragon.py tool stock check                             # offline: validate the bundled sources database
    dragon.py tool stock video <free_footage args>         # the whole video client (search, download, preview, probe ...)
    dragon.py tool stock photo <free_photos args>          # the whole photo client (search, sheet, download ...)
    dragon.py tool stock pexels|mixkit|pixabay ID... -o DIR  # page/id fetcher (stock_fetch.py, no yt-dlp)

--kind defaults to video. For download it is chosen from the results files when the id is in one of them
(out/free-footage/last_search.json, out/free-photos/last_search.json, relative to the current folder), else from
the id's source (openverse:, met:, unsplash: are photos). Keys are optional and read only from the environment:
PEXELS_API_KEY, PIXABAY_API_KEY, UNSPLASH_ACCESS_KEY; never paste them in the chat. Without a key the key-less
sources are used. Python 3.8+ standard library only. A network failure (no internet, a blocked host, a proxy refusal,
a timeout) ends with one clear line and exit 3, never a traceback; nothing is bypassed.
"""
from __future__ import annotations

import json
import socket
import ssl
import sys
import urllib.error
from http.client import HTTPException
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.dont_write_bytecode = True  # no __pycache__ inside the skill folder (the clients import their siblings lazily)
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

PHOTO_ONLY = ("openverse", "met", "unsplash")
FETCHERS = ("pexels", "mixkit", "pixabay", "probe")
NET_HINT = ("no network reached the site (offline, the cloud sandbox blocks that host, or a proxy refused it). "
            "Nothing was bypassed. Try again on the PC, send the search links instead (references/FREE_STOCK.md §4), "
            "or ask the owner to upload the file.")


def _mod(name):
    keep = sys.dont_write_bytecode
    sys.dont_write_bytecode = True  # no __pycache__ inside the skill folder
    try:
        import importlib
        return importlib.import_module(name)
    finally:
        sys.dont_write_bytecode = keep


def _pop(argv, flag, default=None):
    """Remove `flag VALUE` (or `flag=VALUE`) from argv and return VALUE."""
    out, val, i = [], default, 0
    while i < len(argv):
        a = argv[i]
        if a == flag and i + 1 < len(argv):
            val, i = argv[i + 1], i + 2
            continue
        if a.startswith(flag + "="):
            val, i = a.split("=", 1)[1], i + 1
            continue
        out.append(a)
        i += 1
    argv[:] = out
    return val


def _ids_in(path: Path) -> set:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return set()
    return {r.get("id") for r in (data.get("results") or []) if isinstance(r, dict)}


def kind_for_ids(ids, video_results=None, photo_results=None) -> str:
    """photo when every id is a photo result (or from a photo-only source), else video."""
    ids = [i for i in ids if not i.startswith("-")]
    if not ids:
        return "video"
    vids = _ids_in(Path(video_results or Path("out") / "free-footage" / "last_search.json"))
    pics = _ids_in(Path(photo_results or Path("out") / "free-photos" / "last_search.json"))
    def photo(i):
        if i in pics and i not in vids:
            return True
        if i in vids:
            return False
        return i.split(":", 1)[0].lower() in PHOTO_ONLY
    return "photo" if all(photo(i) for i in ids) else "video"


def _positional_ids(argv) -> list:
    """The download targets: arguments before the first option (ids or URLs)."""
    ids = []
    for a in argv:
        if a.startswith("-"):
            break
        ids.append(a)
    return ids


def dispatch(argv) -> int:
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(__doc__)
        return 0
    cmd, rest = argv[0], list(argv[1:])
    if cmd in ("video", "footage"):
        return _mod("free_footage").main(rest)
    if cmd in ("photo", "photos"):
        return _mod("free_photos").main(rest)
    if cmd in FETCHERS:
        return _mod("stock_fetch").main([cmd] + rest)
    if cmd == "check":
        return _mod("free_footage").main(["check"] + rest)
    if cmd in ("search", "download", "sources", "credits"):
        kind = _pop(rest, "--kind")
        if kind not in (None, "video", "photo"):
            print("error: --kind is video or photo", file=sys.stderr)
            return 2
        if kind is None and cmd == "download":
            results = _pop(list(rest), "--results")
            kind = kind_for_ids(_positional_ids(rest), results, results)
        mod = _mod("free_photos" if kind == "photo" else "free_footage")
        return mod.main([cmd] + rest)
    print(f"error: unknown stock command {cmd!r} (search, download, sources, credits, check, video, photo, "
          f"pexels, mixkit, pixabay); see: dragon.py tool stock --help", file=sys.stderr)
    return 2


NET_CMDS = ("search", "download", "probe", "preview") + FETCHERS
NET_WORDS = ("Connection refused", "timed out", "Name or service not known", "Temporary failure in name resolution",
             "getaddrinfo", "Network is unreachable", "urlopen error", "Tunnel connection failed", "CERTIFICATE_VERIFY",
             "ConnectionRefusedError", "TimeoutError", "ConnectionResetError")


class _Tee:
    """Pass a stream through and remember whether a line looked like a network failure."""

    def __init__(self, inner):
        self.inner, self.net = inner, False

    def write(self, s):
        if any(w in s for w in NET_WORDS):
            self.net = True
        return self.inner.write(s)

    def flush(self):
        return self.inner.flush()

    def __getattr__(self, name):
        return getattr(self.inner, name)


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else list(argv)
    out, err = _Tee(sys.stdout), _Tee(sys.stderr)
    real = sys.stdout, sys.stderr
    sys.stdout, sys.stderr = out, err
    try:
        rc = _guarded(argv)
    finally:
        sys.stdout, sys.stderr = real
    if rc and (out.net or err.net):
        print(f"hint: {NET_HINT}", file=sys.stderr)
    return rc


def _guarded(argv) -> int:
    try:
        return dispatch(argv)
    except (urllib.error.URLError, HTTPException, ConnectionError, TimeoutError, socket.gaierror, ssl.SSLError) as e:
        # refused, DNS, TLS, timeout, proxy: a failure the client did not word itself
        print(f"error: network: {type(e).__name__}: {e}. {NET_HINT}", file=sys.stderr)
        return 3
    except OSError as e:
        print(f"error: file: {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
