"""For skills that differ between the laptop and the repo, say which side is newer.
usage: python -X utf8 skilldiff.py REPO SKILLS_DIR INVENTORY.json
Newer = laptop file mtime vs the repo's last commit time for that path (git log -1 --format=%ct).
"""
import datetime
import hashlib
import json
import subprocess
import sys
from pathlib import Path

repo, skills, inv = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
rows = json.loads(inv.read_text(encoding="utf-8"))


def h(p):
    return hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def files(root):
    return {str(p.relative_to(root)).replace("\\", "/"): p for p in root.rglob("*")
            if p.is_file() and "__pycache__" not in p.parts and ".git" not in p.parts}


def commit_time(path):
    r = subprocess.run(["git", "-C", str(repo), "log", "-1", "--format=%ct", "--", path],
                       capture_output=True, text=True)
    return int(r.stdout.strip() or 0)


def ts(t):
    return datetime.datetime.fromtimestamp(t).strftime("%m-%d %H:%M") if t else "-"


for r in rows:
    if r.get("status") != "differs":
        continue
    a = skills / r["name"]
    b = repo / r["where"][0]
    A, B = files(a), files(b)
    only_a = sorted(set(A) - set(B))
    only_b = sorted(set(B) - set(A))
    diff = sorted(k for k in set(A) & set(B) if h(A[k]) != h(B[k]))
    newest_laptop = max((A[k].stat().st_mtime for k in diff + only_a), default=0)
    repo_t = max((commit_time(f"{r['where'][0]}/{k}") for k in diff + only_b), default=0)
    side = "LAPTOP newer" if newest_laptop > repo_t else "REPO newer"
    print(f"\n## {r['name']}  ({side}: laptop {ts(newest_laptop)} vs repo commit {ts(repo_t)})  repo={r['where'][0]}")
    for k in only_a[:12]:
        print("   + laptop only:", k)
    for k in only_b[:12]:
        print("   - repo only:  ", k)
    for k in diff[:12]:
        print(f"   ~ differs:     {k}  (laptop {ts(A[k].stat().st_mtime)} / repo {ts(commit_time(r['where'][0] + '/' + k))})")
