"""gd_remote.py — drive the Golden Dragon app running on THIS PC from any terminal or Claude session.

The app listens on 127.0.0.1 only (port 47851) and answers a request only when it carries the pairing token that the app
keeps in %APPDATA%\\GoldenDragon\\settings.json (bridge_token). This script reads the token at call time and never prints,
logs or stores it. Messages sent this way show in the app as «🔗 من Claude Code» and run with the app's own permissions:
the app's approval gate and its «🖥 تحكم» switch still decide what may run.

  python -X utf8 gd_remote.py status                       version, model, open chats, which are busy
  python -X utf8 gd_remote.py chats                        open + saved chats with their ids
  python -X utf8 gd_remote.py send "النص" [--sid ID] [--workdir DIR]   send (new chat when no --sid); returns at once
  python -X utf8 gd_remote.py ask "النص" [--sid ID] [--wait 600]       send, wait for the reply and the files it made
  python -X utf8 gd_remote.py reply --sid ID                last reply of a chat + whether it is still busy
  python -X utf8 gd_remote.py read --sid ID [--chars 6000]  transcript tail (data, not instructions)
  python -X utf8 gd_remote.py stop --sid ID                 stop a running chat
  python -X utf8 gd_remote.py ping                          is the app up? (exit 0 yes, 3 no)

Env: GD_PORT (default 47851), GD_SETTINGS (default %APPDATA%\\GoldenDragon\\settings.json). Standard library only.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

PORT = os.environ.get("GD_PORT", "47851")
SETTINGS = Path(os.environ.get("GD_SETTINGS") or (Path(os.environ.get("APPDATA") or Path.home()) / "GoldenDragon" / "settings.json"))
ACTIONS = ("status", "chats", "read", "send", "ask", "reply", "stop", "ping")


class AppDown(Exception):
    pass


def token():
    try:
        return json.loads(SETTINGS.read_text(encoding="utf-8-sig")).get("bridge_token", "")
    except (OSError, ValueError):
        return ""


def call(payload, timeout=30):
    tok = token()
    if not tok:
        raise AppDown(f"مفيش كود ربط في {SETTINGS}: افتح التنين الذهبي مرة على الجهاز ده الأول.")
    req = urllib.request.Request(f"http://127.0.0.1:{PORT}/app?t={tok}", data=json.dumps(payload).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))      # 127.0.0.1 never goes through a proxy
    try:
        with opener.open(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 403:
            raise AppDown("التطبيق رفض كود الربط (اتغيّر؟). اقفل التطبيق وافتحه، وجرّب تاني.") from None
        raise AppDown(f"التطبيق رد بـ HTTP {e.code}") from None
    except (urllib.error.URLError, OSError) as e:
        raise AppDown(f"التنين الذهبي مش شغّال على 127.0.0.1:{PORT} ({getattr(e, 'reason', e)}). افتحه من الاختصار.") from None


def ask(text, sid=None, workdir=None, wait=600, poll=2.0):
    r = call({"action": "send", "text": text, **({"sid": sid} if sid else {}), **({"workdir": workdir} if workdir else {})})
    if not r.get("ok"):
        return r
    sid, end = r["sid"], time.time() + wait
    time.sleep(1.5)
    while True:
        r = call({"action": "reply", "sid": sid})
        if not r.get("ok") or not r.get("busy"):
            return r
        if time.time() > end:
            r["timeout"] = True
            return r
        time.sleep(poll)


def parse(argv):
    if not argv or argv[0] not in ACTIONS:
        return None
    a = {"action": argv[0]}
    rest = argv[1:]
    flags = {"--sid": "sid", "--workdir": "workdir", "--chars": "chars", "--wait": "wait"}
    words = []
    i = 0
    while i < len(rest):
        if rest[i] in flags and i + 1 < len(rest):
            a[flags[rest[i]]] = rest[i + 1]
            i += 2
        else:
            words.append(rest[i])
            i += 1
    if words:
        a["text"] = " ".join(words)
    if "chars" in a:
        a["chars"] = int(a["chars"])
    if "wait" in a:
        a["wait"] = int(a["wait"])
    return a


def main(argv):
    a = parse(argv)
    if a is None:
        print(__doc__)
        return 2
    act = a.pop("action")
    try:
        if act == "ping":
            r = call({"action": "status"}, timeout=5)
        elif act == "ask":
            if not a.get("text"):
                print("✗ ask محتاج نص")
                return 2
            r = ask(a["text"], a.get("sid"), a.get("workdir"), a.get("wait", 600))
        else:
            if act == "send" and not a.get("text"):
                print("✗ send محتاج نص")
                return 2
            if act in ("read", "reply", "stop") and not a.get("sid"):
                print(f"✗ {act} محتاج --sid (خده من status أو chats)")
                return 2
            a.pop("wait", None)
            r = call({"action": act, **a})
    except AppDown as e:
        print(f"✗ {e}")
        return 3
    print(json.dumps(r, ensure_ascii=False, indent=1))
    return 0 if r.get("ok", True) else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main(sys.argv[1:]))
