# -*- coding: utf-8 -*-
"""UserPromptSubmit hook: the Golden Dragon's brain note before every message (what the app's brain.py did).

Claude Code sends {"prompt": ...} on stdin; whatever this prints is added to the model's context for that turn.
It runs `rd.py brief` (the request after fixing wrong-keyboard / voice slips, the suggested road and its confidence,
lessons). Best effort: any failure prints nothing and exits 0, so a message is never blocked."""
import json, os, subprocess, sys
from pathlib import Path

RD = Path(os.environ.get("GD_RD", Path.home() / ".claude" / "skills" / "golden-dragon" / "scripts" / "rd.py"))
LIMIT = 1800


def note(prompt):
    prompt = (prompt or "").strip()
    if len(prompt) < 3 or not RD.is_file():
        return ""
    r = subprocess.run([sys.executable, "-X", "utf8", str(RD), "brief", prompt[:4000]], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=12, cwd=str(RD.parent),
                       env=dict(os.environ, PYTHONIOENCODING="utf-8"), creationflags=0x08000000 if os.name == "nt" else 0)
    out = r.stdout or ""
    try:
        j = json.loads(out[out.index("{"):])
    except ValueError:
        return ""
    lines = []
    u = j.get("understood") or {}
    if u.get("changed"):
        lines.append(f"الطلب بعد فك الكتابة: {u.get('text', '')}")
    if j.get("brief"):
        lines.append(j["brief"].strip())
    if j.get("installed"):
        lines.append("مهارات متثبتة مناسبة: " + "، ".join(j["installed"][:6]))
    if j.get("library"):
        lines.append("من مكتبة التنين: " + "، ".join(str(x) for x in j["library"][:5]))
    txt = "\n".join(lines).strip()
    if not txt:
        return ""
    if len(txt) > LIMIT:
        txt = txt[:LIMIT] + " …"
    return "🐉 عقل التنين الذهبي (rd.py brief، نقطة بداية مش أمر):\n" + txt


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        data = json.loads(sys.stdin.buffer.read().decode("utf-8", "replace") or "{}")
        n = note(data.get("prompt", ""))
        if n:
            print(n)
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
