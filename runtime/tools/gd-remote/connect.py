"""connect.py — wire Claude on this PC (Claude Code and Claude Desktop) to the running Golden Dragon app.

It registers ONE MCP server named «golden-dragon» that runs this repo's apps/golden-dragon/app/mcp_dragon.py with
BD_SCOPE=claude-code and BD_PORT=47851. That gives any Claude session on the PC the `blackdragon_app` tool (status / chats /
read / send / ask / reply / stop on the Golden Dragon's chats) plus the dragon catalog tools; raw mouse/keyboard control is
NOT exposed (it stays behind the app's own «🖥 تحكم» switch and approval gate).

  python -X utf8 connect.py            show what would change (nothing is written)
  python -X utf8 connect.py --apply    write it: a timestamped .bak of each config first; other servers are left as they are
  python -X utf8 connect.py --remove --apply   take «golden-dragon» out again

No token is written anywhere: the server reads the pairing token from %APPDATA%\\GoldenDragon\\settings.json when it runs.
Standard library only.
"""
import json
import os
import shutil
import sys
import time
from pathlib import Path

NAME = "golden-dragon"
HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
SERVER = REPO / "apps" / "golden-dragon" / "app" / "mcp_dragon.py"


def entry(python="python"):
    return {"type": "stdio", "command": python, "args": ["-X", "utf8", str(SERVER)],
            "env": {"BD_SCOPE": "claude-code", "BD_PORT": "47851", "PYTHONIOENCODING": "utf-8"}}


def targets():
    home = Path.home()
    appdata = Path(os.environ.get("APPDATA") or home / "AppData" / "Roaming")
    return [("Claude Code", home / ".claude.json"), ("Claude Desktop", appdata / "Claude" / "claude_desktop_config.json")]


def plan(remove=False):
    out = []
    for label, p in targets():
        if not p.is_file():
            out.append((label, p, "skip", "الملف مش موجود (البرنامج مش متثبّت أو ماتفتحش قبل كده)"))
            continue
        try:
            cfg = json.loads(p.read_text(encoding="utf-8-sig"))
        except ValueError:
            out.append((label, p, "skip", "الملف مش JSON سليم: ماتلمسش"))
            continue
        cur = (cfg.get("mcpServers") or {}).get(NAME)
        if remove:
            out.append((label, p, "remove" if cur else "skip", "هيتشال" if cur else "مش متسجّل أصلًا"))
        elif cur == entry(cur.get("command", "python") if isinstance(cur, dict) else "python"):
            out.append((label, p, "skip", "متسجّل بالظبط كده"))
        else:
            out.append((label, p, "update" if cur else "add", "هيتحدّث" if cur else "هيتضاف"))
    return out


def apply(rows, remove=False):
    stamp = time.strftime("%Y%m%d-%H%M%S")
    for label, p, act, _ in rows:
        if act == "skip":
            continue
        shutil.copy2(p, p.with_name(p.name + f".bak-gd-{stamp}"))
        cli = shutil.which("claude") if label == "Claude Code" and not os.environ.get("GD_CONNECT_NO_CLI") else None
        if cli:              # Claude Code rewrites ~/.claude.json while it runs: let its own CLI make the change
            import subprocess
            cmd = ([cli, "mcp", "remove", NAME, "-s", "user"] if remove else
                   [cli, "mcp", "add-json", NAME, json.dumps(entry()), "-s", "user"])
            if not remove:
                subprocess.run([cli, "mcp", "remove", NAME, "-s", "user"], capture_output=True)
            r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
            if r.returncode == 0:
                continue
            print(f"  (claude mcp فشل: {r.stderr.strip()[:200]}، هعدّل الملف مباشرة)")
        cfg = json.loads(p.read_text(encoding="utf-8-sig"))
        servers = cfg.setdefault("mcpServers", {})
        if remove:
            servers.pop(NAME, None)
        else:
            servers[NAME] = entry()
        tmp = p.with_name(p.name + ".gd-tmp")
        tmp.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, p)


def main(argv):
    remove, do = "--remove" in argv, "--apply" in argv
    if not remove and not SERVER.is_file():
        print(f"✗ مش لاقي {SERVER}")
        return 1
    rows = plan(remove)
    print(f"خادم «{NAME}»: {SERVER}")
    for label, p, act, why in rows:
        print(f"- {label}: {why}  ({p.name})")
    if not do:
        print("\nده عرض بس. للتنفيذ: --apply (وبعدها اقفل Claude Desktop وافتحه، وفي Claude Code افتح جلسة جديدة).")
        return 0
    apply(rows, remove)
    print("✓ اتكتب، ومعاه نسخة .bak-gd-* من كل ملف اتغيّر.")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main(sys.argv[1:]))
