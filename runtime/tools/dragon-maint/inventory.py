"""Which skills installed on this laptop are missing from (or older in) the repo?
usage: python -X utf8 inventory.py REPO SKILLS_DIR OUT.json
Reads only. A skill counts as "in the repo" when a folder with the same name holds a SKILL.md
under engine/skills, library, modules, legacy or apps (any depth <= 3).
"""
import hashlib
import json
import os
import re
import sys
from pathlib import Path

repo, skills, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])


def norm_hash(p):
    return hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def front(p):
    t = p.read_text(encoding="utf-8", errors="replace")
    m = re.match(r"^---\s*\n(.*?)\n---", t, re.S)
    meta = {}
    if m:
        for line in m.group(1).splitlines():
            if ":" in line and not line.startswith(" "):
                k, v = line.split(":", 1)
                meta[k.strip()] = v.strip().strip('"')
    return meta, t


repo_skills = {}
for base in ("engine/skills", "library", "modules", "legacy", "apps"):
    b = repo / base
    if not b.is_dir():
        continue
    for sk in b.rglob("SKILL.md"):
        rel = sk.relative_to(repo)
        if len(rel.parts) > 5:
            continue
        repo_skills.setdefault(sk.parent.name.lower(), []).append(sk)

rows = []
for d in sorted(skills.iterdir()):
    if not d.is_dir():
        continue
    sk = d / "SKILL.md"
    try:
        is_link = d.is_symlink() or bool(os.readlink(d))
    except OSError:
        is_link = False
    if not sk.is_file():
        rows.append({"name": d.name, "status": "no-skill-md", "link": is_link})
        continue
    meta, text = front(sk)
    name = (meta.get("name") or d.name).lower()
    desc = meta.get("description", "")
    arabic = bool(re.search(r"[؀-ۿ]", desc))
    nfiles = sum(1 for _ in d.rglob("*") if _.is_file() and "__pycache__" not in _.parts)
    hits = repo_skills.get(d.name.lower()) or repo_skills.get(name) or []
    status = "missing"
    where = []
    if hits:
        h = norm_hash(sk)
        same = [x for x in hits if norm_hash(x) == h]
        status = "same" if same else "differs"
        where = [str(x.relative_to(repo).parent).replace(os.sep, "/") for x in hits]
    src = d / "SOURCE.json"
    bd = d / ".blackdragon.json"
    rows.append({
        "name": d.name, "status": status, "where": where, "arabic_desc": arabic,
        "files": nfiles, "mtime": sk.stat().st_mtime, "link": is_link,
        "from_library": bd.is_file(), "has_source": src.is_file(),
        "desc": desc[:160],
    })

out.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
from collections import Counter
c = Counter(r["status"] for r in rows)
print("totals", dict(c))
print("\nMISSING with Arabic description (owner-made, likely):")
for r in rows:
    if r["status"] == "missing" and r.get("arabic_desc"):
        print(f"  {r['name']:<34} files={r['files']:<5} {r['desc'][:90]}")
print("\nMISSING (English description):")
for r in rows:
    if r["status"] == "missing" and not r.get("arabic_desc"):
        print(f"  {r['name']:<34} files={r['files']:<5} lib={r['from_library']} src={r['has_source']}")
print("\nDIFFERS (repo copy not identical):")
for r in rows:
    if r["status"] == "differs":
        print(f"  {r['name']:<34} files={r['files']:<5} repo={r['where']}")
