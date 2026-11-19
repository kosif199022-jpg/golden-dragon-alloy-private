"""chrome_unpacked.py — read-only: which UNPACKED extensions each Chrome profile has registered, from where, and whether
that folder still exists. Prints only extension id, name, path, state and disable reasons — nothing else from the files.

  python -X utf8 chrome_unpacked.py
"""
import json
import os
from pathlib import Path

ROOT = Path(os.environ.get("LOCALAPPDATA", "")) / "Google" / "Chrome" / "User Data"
for prof in sorted(p for p in ROOT.iterdir() if p.is_dir() and (p.name == "Default" or p.name.startswith("Profile "))):
    seen = {}
    for fname in ("Secure Preferences", "Preferences"):
        f = prof / fname
        if not f.is_file():
            continue
        try:
            d = json.loads(f.read_text(encoding="utf-8", errors="replace"))
        except ValueError:
            continue
        for ext_id, s in ((d.get("extensions") or {}).get("settings") or {}).items():
            if not isinstance(s, dict) or s.get("location") != 4:          # 4 = unpacked (loaded from a folder)
                continue
            path = s.get("path", "")
            name = ((s.get("manifest") or {}).get("name")) or "?"
            seen[ext_id] = (name, path, s.get("state"), s.get("disable_reasons"))
    for ext_id, (name, path, state, reasons) in seen.items():
        exists = Path(path).is_dir() if path else False
        print(f"{prof.name} | {ext_id} | {name} | {path} | exists={exists} | state={state} | disable={reasons}")
