"""restore_skill_files.py — gives installed skills back the files their own SKILL.md tells Claude to open or run
(found by scan_skills.py: `missing` inside the skill, `missing_shared` = ../references/... of the original plugin), taken
from the original sources already on this PC. Nothing is downloaded and nothing is executed.

Rules (2026-11-15, approved by the owner as part of «صلح كل حاجة»):
  - a source counts only if it is a folder with the SAME skill name that has its own SKILL.md;
  - a source whose SKILL.md is byte-identical to the installed one wins («exact»); otherwise all remaining sources must
    agree byte-for-byte on the file («same-content»), else the file is skipped as ambiguous;
  - ADD ONLY: an existing destination is never overwritten; files over 5 MB are skipped;
  - every added file goes into analysis\\restored_skill_files.json, so `--rollback` removes exactly those files.

  python -X utf8 restore_skill_files.py [--dry-run] | --rollback
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import zipfile
from collections import defaultdict
from pathlib import Path

FORGE = Path(__file__).resolve().parent
SK = Path.home() / ".claude" / "skills"
DESK = FORGE.parent.parent                                      # «مهارات»
MANIFEST = FORGE.parent / "analysis" / "restored_skill_files.json"
DIRS = [Path.home() / "dragon-repos", Path.home() / "kosif-tool", SK / "kosif-tool-main", SK / "kosif-claude-app", SK / "synced",
        SK / "bd_src", Path.home() / ".goldenbird-re" / "src"]
CAP = 5 * 1024 * 1024
RG = shutil.which("rg") or next((str(p) for p in (Path.home() / "AppData/Local/Microsoft/WinGet/Packages").glob(
    "BurntSushi.ripgrep*/*/rg.exe")), "rg")         # winget adds its package folder to the user PATH; new shells see it


def sha(b):
    return hashlib.sha256(b).hexdigest()


def targets():
    d = json.loads((FORGE / "data" / "skills.json").read_text(encoding="utf-8"))
    out = []
    for s in d["skills"]:
        for rel in s.get("missing") or []:
            out.append((s["id"], rel))
        for rel in s.get("missing_shared") or []:
            out.append((s["id"], rel))
    return out


def dir_skill_folders(names):
    """name -> [folder] for every folder named like an installed skill that has a SKILL.md, in the source dirs."""
    found = defaultdict(list)
    for root in DIRS:
        if not root.is_dir():
            continue
        p = subprocess.run([RG, "--files", "--no-messages", "-g", "SKILL.md", str(root)], capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        for line in p.stdout.splitlines():
            folder = Path(line).parent
            if folder.name in names and not folder.resolve().is_relative_to((SK / folder.name).resolve()):
                found[folder.name].append(("dir", folder))
    return found


def zip_skill_folders(names):
    found = defaultdict(list)
    for z in sorted(DESK.glob("*.zip")):
        try:
            zf = zipfile.ZipFile(z)
            entries = set(zf.namelist())
        except (zipfile.BadZipFile, OSError):
            continue
        for e in entries:
            if e.endswith("/SKILL.md"):
                prefix = e[: -len("SKILL.md")]
                name = prefix.rstrip("/").split("/")[-1]
                if name in names:
                    found[name].append(("zip", (z, prefix, entries)))
    return found


def read_candidate(src, rel):
    """bytes of `rel` relative to a source skill folder (rel may start with ../), or None."""
    kind, where = src
    if kind == "dir":
        p = (where / rel).resolve()
        return p.read_bytes() if p.is_file() and p.stat().st_size <= CAP else None
    z, prefix, entries = where
    parts = prefix.rstrip("/").split("/")
    up = rel.count("../")
    name = "/".join(parts[: len(parts) - up] + [rel.replace("../", "")])
    if name not in entries:
        return None
    zf = zipfile.ZipFile(z)
    if zf.getinfo(name).file_size > CAP:
        return None
    return zf.read(name)


def skill_md(src):
    kind, where = src
    if kind == "dir":
        return (where / "SKILL.md").read_bytes()
    z, prefix, _ = where
    return zipfile.ZipFile(z).read(prefix + "SKILL.md")


def label(src):
    kind, where = src
    return str(where) if kind == "dir" else f"{where[0].name}!{where[1]}"


def rollback():
    if not MANIFEST.exists():
        print("مفيش manifest")
        return 0
    rec = json.loads(MANIFEST.read_text(encoding="utf-8"))
    n = 0
    for f in rec.get("added", []):
        p = Path(f["dest"])
        if p.is_file() and sha(p.read_bytes()) == f["sha256"]:
            p.unlink()
            n += 1
    print(f"✓ اتشال {n} ملف من اللي اتضافوا")
    return 0


def main(argv):
    if "--rollback" in argv:
        return rollback()
    dry = "--dry-run" in argv
    tg = targets()
    names = {s for s, _ in tg}
    sources = dir_skill_folders(names)
    for k, v in zip_skill_folders(names).items():
        sources[k].extend(v)
    added, skipped = [], defaultdict(list)
    for skill, rel in tg:
        dest = (SK / skill / rel).resolve()
        limit = SK.resolve() if rel.startswith("../") else (SK / skill).resolve()
        if not dest.is_relative_to(limit):
            skipped["outside"].append(f"{skill}: {rel}")
            continue
        if dest.exists():
            skipped["exists"].append(f"{skill}: {rel}")
            continue
        installed_md = (SK / skill / "SKILL.md").read_bytes()
        cands = []
        for src in sources.get(skill, []):
            try:
                b = read_candidate(src, rel)
            except (OSError, KeyError, zipfile.BadZipFile):
                b = None
            if b is not None:
                cands.append((skill_md(src) == installed_md, sha(b), b, src))
        if not cands:
            skipped["no-source"].append(f"{skill}: {rel}")
            continue
        exact = [c for c in cands if c[0]]
        pool = exact or cands
        if len({c[1] for c in pool}) != 1:
            skipped["ambiguous"].append(f"{skill}: {rel} ({len({c[1] for c in pool})} versions)")
            continue
        c = pool[0]
        rec = {"skill": skill, "file": rel, "dest": str(dest), "sha256": c[1], "bytes": len(c[2]),
               "provenance": "exact" if exact else "same-content", "source": label(c[3])}
        if not dry:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(c[2])
        added.append(rec)
    if not dry:
        old = json.loads(MANIFEST.read_text(encoding="utf-8")) if MANIFEST.exists() else {"added": []}
        old["added"] += added
        old.setdefault("runs", []).append({"time": time.strftime("%Y-%m-%d %H:%M:%S"), "added": len(added),
                                           "skipped": {k: len(v) for k, v in skipped.items()}})
        old["skipped_last_run"] = {k: v for k, v in skipped.items()}
        MANIFEST.write_text(json.dumps(old, ensure_ascii=False, indent=1), encoding="utf-8")
    ex = sum(1 for a in added if a["provenance"] == "exact")
    print(f"{'(تجربة) ' if dry else ''}✓ {len(added)} ملف ({ex} من نسخة مطابقة بالظبط، {len(added) - ex} محتوى متفق عليه) "
          f"في {len({a['skill'] for a in added})} مهارة، من {len(tg)} ملف ناقص")
    for k, v in skipped.items():
        print(f"  اتساب {k}: {len(v)}" + (f" — مثال: {v[0]}" if v else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
