"""Plan an in-place skill update without losing local edits. Read-only.
usage: python -X utf8 install_plan.py REPO INSTALLED_DIR OLD_COMMIT NEW_COMMIT [--json OUT]
Compares git blob ids (sha1 of "blob <len>\\0" + bytes; the repo is `* -text`, so disk bytes == blob bytes):
  same      installed file == new version (nothing to do)
  update    installed file == old version (safe to overwrite)
  add       file only in the new version
  foreign   installed file differs from BOTH old and new (a local edit: never overwrite blindly)
  keep      file only in the installed folder (left alone)
"""
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

repo, inst, old, new = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3], sys.argv[4]
SKIP = {"__pycache__", ".git"}


def tree(commit):
    out = subprocess.run(["git", "-C", str(repo), "ls-tree", "-r", "-z", commit], capture_output=True, check=True).stdout
    rows = {}
    for ent in out.decode("utf-8").split("\0"):
        if ent:
            meta, path = ent.split("\t", 1)
            rows[path] = meta.split()[2]
    return rows


def blob_id(p):
    b = p.read_bytes()
    return hashlib.sha1(b"blob %d\0" % len(b) + b).hexdigest()


O, N = tree(old), tree(new)
have = {}
for d, dirs, files in os.walk(inst):
    dirs[:] = [x for x in dirs if x not in SKIP]
    for f in files:
        p = Path(d) / f
        have[str(p.relative_to(inst)).replace(os.sep, "/")] = p
plan = {"same": [], "update": [], "add": [], "foreign": [], "keep": []}
for path, nid in N.items():
    p = have.get(path)
    if p is None:
        plan["add"].append(path)
        continue
    hid = blob_id(p)
    if hid == nid:
        plan["same"].append(path)
    elif O.get(path) == hid:
        plan["update"].append(path)
    else:
        plan["foreign"].append(path)
plan["keep"] = sorted(p for p in have if p not in N)
print({k: len(v) for k, v in plan.items()})
for k in ("foreign", "keep"):
    for p in plan[k][:40]:
        print(f"  {k}: {p}")
if "--json" in sys.argv:
    Path(sys.argv[sys.argv.index("--json") + 1]).write_text(json.dumps(plan, ensure_ascii=False, indent=1), encoding="utf-8")
