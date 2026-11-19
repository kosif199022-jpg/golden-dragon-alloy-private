"""krita_live.py - paint LIVE in the real Krita GUI with Krita's own brush presets.

    python -X utf8 krita_live.py status
    python -X utf8 krita_live.py install      # copies plugin, enables it in kritarc (Krita must be closed)
    python -X utf8 krita_live.py start        # opens Krita (if needed) and waits for the bridge heartbeat
    python -X utf8 krita_live.py run job.py [--timeout 600]
    python -X utf8 krita_live.py quit         # closes Krita WITHOUT saving open documents (ask the user first!)
    python -X utf8 krita_live.py uninstall    # removes plugin + kritarc entry (Krita must be closed)

The plugin (live_plugin/claude_bridge) polls %APPDATA%/krita/claude_bridge/inbox every 250 ms and runs
.py jobs on Krita's GUI thread; see the plugin docstring for the helper API (canvas, brush, stroke...).
Exit codes: 0 ok, 2 bad usage, 3 Krita not found/not running, 4 job failed/timed out, 5 refused (Krita open).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLUGIN_SRC = HERE.parent / "live_plugin"
APPDATA = Path(os.environ["APPDATA"])
PYKRITA = APPDATA / "krita" / "pykrita"
BRIDGE = APPDATA / "krita" / "claude_bridge"
KRITARC = Path(os.environ["LOCALAPPDATA"]) / "kritarc"
KEY = "enable_claude_bridge"


def krita_bin():
    sys.path.insert(0, str(HERE))
    from krita_draw import find_krita
    return find_krita()


def krita_running():
    out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq krita.exe", "/FO", "CSV", "/NH"],
                         capture_output=True, text=True).stdout
    return "krita.exe" in out.lower()


def heartbeat():
    hb = BRIDGE / "heartbeat.json"
    if not hb.exists():
        return None
    try:
        d = json.loads(hb.read_text(encoding="utf-8"))
        d["age_s"] = round(time.time() - d["time"], 1)
        return d
    except Exception:  # noqa: BLE001
        return None


def set_kritarc(enable: bool):
    """Text-level edit of the KConfig INI (configparser would rewrite the whole file)."""
    text = KRITARC.read_text(encoding="utf-8") if KRITARC.exists() else ""
    if KRITARC.exists():
        bak = KRITARC.with_name("kritarc.claude_bak_" + time.strftime("%Y%m%d_%H%M%S"))
        shutil.copy2(KRITARC, bak)
    lines = text.splitlines()
    out, in_py, done = [], False, False
    for ln in lines:
        s = ln.strip()
        if s.startswith("[") and s.endswith("]"):
            if in_py and enable and not done:
                out.append(KEY + "=true")
                done = True
            in_py = s == "[python]"
        if in_py and s.startswith(KEY + "="):
            if enable:
                out.append(KEY + "=true")
                done = True
            continue
        out.append(ln)
    if enable and not done:
        if in_py:
            out.append(KEY + "=true")
        else:
            out += ["", "[python]", KEY + "=true"]
    KRITARC.write_text("\n".join(out) + "\n", encoding="utf-8")


def cmd_status(_):
    info = {"krita_running": krita_running(), "plugin_installed": (PYKRITA / "claude_bridge.desktop").exists(),
            "enabled_in_kritarc": KRITARC.exists() and (KEY + "=true") in KRITARC.read_text(encoding="utf-8"),
            "heartbeat": heartbeat()}
    info["ready"] = bool(info["heartbeat"] and info["heartbeat"]["age_s"] < 5 and info["krita_running"])
    print(json.dumps(info, ensure_ascii=False, indent=1))
    return 0


def cmd_install(_):
    if krita_running():
        print(json.dumps({"ok": False, "error": "Krita is open. It rewrites kritarc on exit, so close it first (ask the user)."}))
        return 5
    PYKRITA.mkdir(parents=True, exist_ok=True)
    shutil.copytree(PLUGIN_SRC / "claude_bridge", PYKRITA / "claude_bridge", dirs_exist_ok=True)
    shutil.copy2(PLUGIN_SRC / "claude_bridge.desktop", PYKRITA / "claude_bridge.desktop")
    shutil.rmtree(PYKRITA / "claude_bridge" / "__pycache__", ignore_errors=True)
    set_kritarc(True)
    print(json.dumps({"ok": True, "plugin": str(PYKRITA / "claude_bridge"), "kritarc": str(KRITARC)}, ensure_ascii=False))
    return 0


def cmd_uninstall(_):
    if krita_running():
        print(json.dumps({"ok": False, "error": "close Krita first"}))
        return 5
    shutil.rmtree(PYKRITA / "claude_bridge", ignore_errors=True)
    (PYKRITA / "claude_bridge.desktop").unlink(missing_ok=True)
    set_kritarc(False)
    print(json.dumps({"ok": True}))
    return 0


def cmd_start(a):
    hb = heartbeat()
    if krita_running() and hb and hb["age_s"] < 5:
        print(json.dumps({"ok": True, "already_running": True, "heartbeat": hb}))
        return 0
    if not krita_running():
        kb = krita_bin()
        if not kb:
            print(json.dumps({"ok": False, "error": "Krita not found"}))
            return 3
        (BRIDGE / "heartbeat.json").unlink(missing_ok=True)
        subprocess.Popen([str(kb / "krita.exe"), "--nosplash"], cwd=str(kb), close_fds=True,
                         creationflags=0x00000008 | 0x00000200)  # DETACHED_PROCESS | NEW_PROCESS_GROUP
    t0 = time.time()
    while time.time() - t0 < a.timeout:
        hb = heartbeat()
        if hb and hb["age_s"] < 5 and hb.get("windows", 0) > 0:
            print(json.dumps({"ok": True, "seconds": round(time.time() - t0, 1), "heartbeat": hb}))
            return 0
        time.sleep(1)
    print(json.dumps({"ok": False, "error": "no heartbeat - plugin not enabled? run status/install",
                      "krita_running": krita_running()}))
    return 3


def cmd_run(a):
    hb = heartbeat()
    if not (hb and hb["age_s"] < 5):
        print(json.dumps({"ok": False, "error": "bridge not running - use start"}))
        return 3
    src = Path(a.job)
    name = "job_%d_%d" % (int(time.time() * 1000), os.getpid())
    (BRIDGE / "inbox").mkdir(parents=True, exist_ok=True)
    tmp = BRIDGE / "inbox" / (name + ".tmp")
    tmp.write_text(src.read_text(encoding="utf-8-sig"), encoding="utf-8")
    tmp.replace(BRIDGE / "inbox" / (name + ".py"))
    res_file = BRIDGE / "outbox" / (name + ".json")
    t0 = time.time()
    while time.time() - t0 < a.timeout:
        if res_file.exists():
            res = json.loads(res_file.read_text(encoding="utf-8"))
            res_file.unlink(missing_ok=True)
            print(json.dumps(res, ensure_ascii=False, indent=1))
            return 0 if res.get("ok") else 4
        time.sleep(0.3)
    print(json.dumps({"ok": False, "error": "timeout waiting for job %s" % name}))
    return 4


def cmd_quit(a):
    job = HERE / "_quit_job.py"
    job.write_text("quit_krita(close_unsaved=True)\nresult = {'quitting': True}\n", encoding="utf-8")
    a.job, a.timeout = str(job), 30
    rc = cmd_run(a)
    job.unlink(missing_ok=True)
    for _ in range(30):
        if not krita_running():
            break
        time.sleep(1)
    print(json.dumps({"krita_running": krita_running()}))
    return rc


def main():
    import argparse
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for n, fn in (("status", cmd_status), ("install", cmd_install), ("uninstall", cmd_uninstall), ("quit", cmd_quit)):
        sub.add_parser(n).set_defaults(fn=fn)
    s = sub.add_parser("start")
    s.add_argument("--timeout", type=int, default=120)
    s.set_defaults(fn=cmd_start)
    r = sub.add_parser("run")
    r.add_argument("job")
    r.add_argument("--timeout", type=int, default=600)
    r.set_defaults(fn=cmd_run)
    a = ap.parse_args()
    sys.exit(a.fn(a))


if __name__ == "__main__":
    main()
