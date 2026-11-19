"""Replace the Windows user folder with %USERPROFILE% in NEW or CHANGED files only (git status), byte-level.
usage: python -X utf8 sanitize_paths.py REPO [--apply] [--user NAME]
NAME = the Windows user folder name (default: %USERNAME%, else the current login).
Covers: references/REPOS_*.md and library/**/SOURCE.json. JSON files must still parse afterwards.
"""
import getpass
import json
import os
import subprocess
import sys
from pathlib import Path

repo = Path(sys.argv[1]).resolve()
apply = "--apply" in sys.argv
user = sys.argv[sys.argv.index("--user") + 1] if "--user" in sys.argv else (os.environ.get("USERNAME") or getpass.getuser())
u = user.encode("utf-8")
PAIRS = [(b"C:\\\\Users\\\\" + u, b"%USERPROFILE%"),      # JSON-escaped form first
         (b"C:\\Users\\" + u, b"%USERPROFILE%"),
         (b"C:/Users/" + u, b"%USERPROFILE%")]
out = subprocess.run(["git", "-C", str(repo), "status", "--porcelain", "-z", "--untracked-files=all"],
                     capture_output=True, check=True).stdout.decode("utf-8").split("\0")
paths = [e[3:] for e in out if len(e) > 3]
targets = [p for p in paths if (p.startswith("references/REPOS_") and p.endswith(".md"))
           or (p.startswith("library/") and p.endswith("/SOURCE.json"))]
changed = 0
for p in targets:
    f = repo / p
    b = f.read_bytes()
    nb = b
    for a, r in PAIRS:
        nb = nb.replace(a, r)
    if nb == b:
        continue
    if p.endswith(".json"):
        json.loads(nb.decode("utf-8"))
    changed += 1
    print(("fixed " if apply else "would fix ") + p)
    if apply:
        f.write_bytes(nb)
print(f"{changed} of {len(targets)} candidate files {'changed' if apply else 'to change'}")
