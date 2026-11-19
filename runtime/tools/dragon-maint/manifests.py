"""Rebuild the SHA256 manifests of the Golden Dragon repo: engine/ first (the root list hashes engine's files), then root.
usage: python -X utf8 manifests.py REPO VERSION DATE [--check]
Files = git ls-files --cached --others --exclude-standard (tracked + new, minus ignored), each list without its own
MANIFEST_SHA256.json and SHA256SUMS.txt. Order = sorted by path parts (reproduces the stored lists). count = len(files).
JSON layout (indent, ensure_ascii, final newline) is detected from the current file so only real changes show in git.
.gitattributes is `* -text`, so the bytes on disk are the bytes in the repo.
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

repo = Path(sys.argv[1]).resolve()
version, date = sys.argv[2], sys.argv[3]
check = "--check" in sys.argv
OWN = ("MANIFEST_SHA256.json", "SHA256SUMS.txt")


def listed(prefix=""):
    out = subprocess.run(["git", "-C", str(repo), "ls-files", "-z", "--cached", "--others", "--exclude-standard", "--", prefix or "."],
                         capture_output=True, check=True).stdout.decode("utf-8").split("\0")
    files = []
    for p in out:
        if not p or not (repo / p).is_file():
            continue
        rel = p[len(prefix):] if prefix else p
        if rel in OWN:
            continue
        files.append(rel)
    return sorted(set(files), key=lambda s: s.split("/"))


def layout(raw):
    """(indent, ensure_ascii) that reproduce this JSON file byte for byte."""
    d = json.loads(raw.decode("utf-8"))
    for ea in (False, True):
        for ind in (1, 2, None):
            if (json.dumps(d, ensure_ascii=ea, indent=ind) + "\n").encode("utf-8") == raw:
                return ind, ea, d
    raise SystemExit("cannot reproduce the current manifest layout; refusing to rewrite it")


def order_key(stored):
    """The stored lists were written by different sessions: engine/ is sorted by path parts, the root list as plain
    strings («claude_bridge.desktop» before «claude_bridge/__init__.py»). Keep whichever this file already uses."""
    for key in (lambda s: s.split("/"), lambda s: s):
        if sorted(stored, key=key) == list(stored):
            return key
    return lambda s: s.split("/")


def build(base, prefix, ver):
    man_f, sums_f = base / "MANIFEST_SHA256.json", base / "SHA256SUMS.txt"
    ind, ea, old = layout(man_f.read_bytes())
    files = sorted(listed(prefix), key=order_key(list(old.get("files", {}))))
    sums = {f: hashlib.sha256((base / f).read_bytes()).hexdigest() for f in files}
    new = {k: old[k] for k in old if k not in ("version", "date", "count", "files")}
    new.update({"version": ver, "date": date, "count": len(files), "files": sums})
    order = [k for k in old if k in new] + [k for k in new if k not in old]
    new = {k: new[k] for k in order}
    sums_txt = "".join(f"{h}  {f}\n" for f, h in sums.items())
    if check:
        ok = json.loads(man_f.read_text(encoding="utf-8")).get("files") == sums and sums_f.read_text(encoding="utf-8") == sums_txt
        print(f"{prefix or '/'}: {'OK' if ok else 'STALE'} ({len(files)} files)")
        return ok
    man_f.write_bytes((json.dumps(new, ensure_ascii=ea, indent=ind) + "\n").encode("utf-8"))
    sums_f.write_bytes(sums_txt.encode("utf-8"))
    print(f"{prefix or '/'}: {len(files)} files, version {ver}, count {len(files)} (was {old.get('count')}, listed {len(old.get('files', {}))})")
    return True


eng_ver = json.loads((repo / "engine" / "MANIFEST_SHA256.json").read_text(encoding="utf-8")).get("version")
ok = build(repo / "engine", "engine/", eng_ver)          # engine first: the root list hashes engine's manifest files
ok = build(repo, "", version) and ok
sys.exit(0 if ok else 1)
