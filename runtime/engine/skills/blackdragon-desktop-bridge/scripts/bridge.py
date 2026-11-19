#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Explicit-consent, READ-ONLY bridge to the owner's running BlackDragon desktop app.

Never runs code from an archive; never reads a Chrome profile; never stores tokens.
It calls the *existing* authenticated local app control interface only after consent.
No write/action automation is supported. Designed for opt-in diagnostics / captures.
"""
import argparse
import base64
import json
import os
from pathlib import Path
import sys
import urllib.request

ACTIONS = {
    "computer": ("screenshot",),
    "browser": ("tabs", "read", "screenshot"),
    "system": ("info", "processes", "apps", "displays", "disks", "battery"),
}
REASON = "فحص قراءة فقط من تطبيق التنين الأسود بعد موافقة صاحب الجهاز"
MAX_IMAGE = 20 * 1024 * 1024


def catalog():
    return {
        "source": "BlackDragon(2).rar / _internal/mcp_control.py; present unchanged in Red Dragon v2.7.0",
        "status": "local integration only; no live desktop control verified in this build",
        "existing_groups": {
            "computer": "screenshot plus other user-interface actions in the existing app (not enabled by this adapter)",
            "browser": "tabs, read, screenshot plus actions in the existing app (not enabled by this adapter)",
            "system": "diagnostic info plus system controls in the existing app (not enabled by this adapter)",
            "voice": "faster-whisper local transcription via existing voice.py; depends on system installation and cached model",
        },
        "read_only_allowlist": ACTIONS,
        "notes": [
            "Permission switch, emergency stop, and session token belong to the running desktop app.",
            "This wrapper refuses commands that change windows, pages, files or system state.",
            "Browser contents/screenshots may contain personal data; explicit per-call consent required.",
            "Reference package contains private Chrome profiles; these were not copied or read.",
        ],
    }


def readiness(env):
    return {
        "token_supplied": bool(env.get("BD_TOKEN")),
        "session_supplied": bool(env.get("BD_SID")),
        "port_configured": bool(env.get("BD_PORT")),
        "desktop_available": "not tested: network access is disabled in doctor",
        "safe_to_call": bool(env.get("BD_TOKEN") and env.get("BD_SID")),
    }


def _request(name, action, args, env):
    if name not in ACTIONS or action not in ACTIONS[name]:
        raise ValueError("Refused: action is not in the read-only allowlist")
    token, sid = env.get("BD_TOKEN", ""), env.get("BD_SID", "")
    if not token or not sid:
        raise ValueError("BD_TOKEN and BD_SID must be supplied by the locally running app")
    port = env.get("BD_PORT", "47821")
    if not port.isascii() or not port.isdecimal() or not 1 <= int(port) <= 65535:
        raise ValueError("Invalid local-only port")
    # Retain the same local endpoint as the app's own MCP client, without proxies.
    from urllib.parse import quote
    url = f"http://127.0.0.1:{int(port)}/control?t={quote(token, safe='')}"
    body = json.dumps({"sid": sid, "name": name, "args": {"action": action, "reason": REASON, **args}}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req, timeout=25) as res:
        payload = res.read(MAX_IMAGE * 2)
    result = json.loads(payload)
    if result.get("error"):
        raise RuntimeError("Desktop app rejected the request")
    return result


def _safe_summary(result):
    # Never echo page content, tab URLs, cookies, file paths, credentials or image base64.
    content = result.get("content") or []
    return {"received": True, "items": len(content), "types": [b.get("type", "unknown") for b in content][:20],
            "private_content_omitted": True}


def _save_image(result, output):
    images = [b for b in result.get("content", []) if b.get("type") == "image"]
    if len(images) != 1:
        raise ValueError("Expected exactly one image from the running app")
    m = images[0].get("mime", "image/jpeg")
    if m not in ("image/png", "image/jpeg"):
        raise ValueError("Unexpected screenshot format")
    raw = base64.b64decode(images[0].get("data", ""), validate=True)
    if len(raw) > MAX_IMAGE or len(raw) < 20:
        raise ValueError("Invalid screenshot byte length")
    if not (raw.startswith(b"\x89PNG\r\n\x1a\n") or raw.startswith(b"\xff\xd8\xff")):
        raise ValueError("Invalid screenshot file signature")
    path = Path(output).expanduser()
    if path.suffix.lower() not in ((".png",) if m == "image/png" else (".jpg", ".jpeg")):
        raise ValueError("Output filename extension must match screenshot MIME type")
    # No overwrite even if the destination already exists. Never leave partial files.
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as file:
        file.write(raw)
    return {"written": str(path), "bytes": len(raw), "mime": m}


def main(argv=None, env=None):
    env = os.environ if env is None else env
    ap = argparse.ArgumentParser(description="Red Dragon ↔ BlackDragon local desktop bridge (READ ONLY)")
    sp = ap.add_subparsers(dest="command", required=True)
    sp.add_parser("catalog"); sp.add_parser("doctor")
    r = sp.add_parser("read", help="Read only, require explicit consent; never print actual private contents")
    r.add_argument("group", choices=ACTIONS);r.add_argument("action");r.add_argument("--tab-id", type=int)
    r.add_argument("--confirm-local-read", action="store_true")
    s = sp.add_parser("snapshot", help="Save screenshot on the local PC after explicit consent")
    s.add_argument("--source", choices=("computer", "browser"), required=True)
    s.add_argument("--out", required=True);s.add_argument("--tab-id", type=int)
    s.add_argument("--confirm-local-read", action="store_true")
    args = ap.parse_args(argv)
    if args.command == "catalog":
        print(json.dumps(catalog(), ensure_ascii=False, indent=2));return 0
    if args.command == "doctor":
        print(json.dumps(readiness(env), ensure_ascii=False, indent=2));return 0
    if not args.confirm_local_read:
        print("Refused: --confirm-local-read is required for each call", file=sys.stderr);return 3
    if args.command == "read":
        if args.group not in ACTIONS or args.action not in ACTIONS[args.group]:
            print("Refused: action is not read-only", file=sys.stderr);return 3
        name, action = args.group, args.action
    else:
        name, action = args.source, "screenshot"
    kwargs = {"tab_id": args.tab_id} if args.tab_id is not None and name == "browser" else {}
    try:
        result = _request(name, action, kwargs, env)
        print(json.dumps(_save_image(result, args.out) if args.command == "snapshot" else _safe_summary(result), ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        # Avoid echoing exceptions from HTTP libraries: error messages may include token URL.
        print(f"Local desktop read failed ({type(exc).__name__}); check session/control permissions", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
