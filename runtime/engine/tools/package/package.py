#!/usr/bin/env python3
"""package — stamp, checksum and zip the Black Dragon skill to a folder (default: Desktop).

    dragon.py tool package                  # zip the current version to the Desktop, refresh checksums, verify
    dragon.py tool package --out DIR        # choose the output folder (default: the owner's Desktop, else cwd)
    dragon.py tool package --set-version X  # stamp a new version first (X like 10.18.0), then package
    dragon.py tool package --check          # only verify the installed tree against MANIFEST_SHA256.json (no zip)
    dragon.py tool package --no-zip         # refresh MANIFEST_SHA256.json + SHA256SUMS.txt in place, no zip

Everything is local and offline. SHA-256 is taken over every packaged file (the two integrity files
themselves excluded, plus __pycache__/*.pyc and VCS cruft). The zip's single top folder is `black-dragon/`.
After writing it the tool runs a zip-integrity test and prints the file count and the zip's own SHA-256,
so a claim of "packaged" is measured, not assumed.
"""
import argparse, datetime, hashlib, json, os, re, sys, zipfile
from pathlib import Path

SKILL = Path(__file__).resolve().parents[2]
MANIFEST = SKILL / "MANIFEST_SHA256.json"
SUMS = SKILL / "SHA256SUMS.txt"
INIT = SKILL / "app" / "dragon" / "__init__.py"
LIBRARY_JSON = SKILL / "app" / "data" / "library.json"
SKILL_MD = SKILL / "SKILL.md"

# names excluded from the hash list (but the integrity files ARE still placed in the zip)
HASH_EXCLUDE = {"MANIFEST_SHA256.json", "SHA256SUMS.txt"}
# never hashed and never zipped
SKIP_DIRS = {"__pycache__", ".git", ".pytest_cache", ".mypy_cache", "node_modules"}
SKIP_NAMES = {".DS_Store", "Thumbs.db"}
SKIP_SUFFIX = {".pyc", ".pyo"}


def iter_files(root: Path):
    """Yield (abs_path, posix_relpath) for every packageable file, sorted, skipping cruft."""
    out = []
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        parts = set(p.relative_to(root).parts)
        if parts & SKIP_DIRS or p.name in SKIP_NAMES or p.suffix in SKIP_SUFFIX:
            continue
        out.append((p, p.relative_to(root).as_posix()))
    out.sort(key=lambda t: t[1])
    return out


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_version() -> str:
    m = re.search(r'__version__\s*=\s*"([^"]+)"', INIT.read_text(encoding="utf-8"))
    if not m:
        sys.exit("package: cannot find __version__ in app/dragon/__init__.py")
    return m.group(1)


def set_version(new: str) -> str:
    """Stamp the machine-read version markers and the SKILL.md header. Returns the new version."""
    if not re.fullmatch(r"\d+\.\d+(\.\d+)?", new):
        sys.exit(f"package: --set-version expects a number like 10.18.0, got {new!r}")
    # app/dragon/__init__.py
    t = INIT.read_text(encoding="utf-8")
    t2 = re.sub(r'(__version__\s*=\s*")[^"]+(")', rf"\g<1>{new}\g<2>", t, count=1)
    INIT.write_text(t2, encoding="utf-8")
    # app/data/library.json
    try:
        data = json.loads(LIBRARY_JSON.read_text(encoding="utf-8"))
        data["version"] = new
        LIBRARY_JSON.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    except Exception as e:
        print(f"package: warning, could not stamp library.json: {e}", file=sys.stderr)
    # SKILL.md header line:  # Black Dragon — التنين الأسود (vX، DATE)  or  (vX candidate، DATE)  (v1990.10: label allowed)
    today = datetime.date.today().isoformat()
    md = SKILL_MD.read_text(encoding="utf-8")
    md2 = re.sub(r"(# Black Dragon.*?\(v)[\d.]+((?: [A-Za-z]+)?[،,] )[\d-]+(\))",
                 rf"\g<1>{new}\g<2>{today}\g<3>", md, count=1)
    if md2 != md:
        SKILL_MD.write_text(md2, encoding="utf-8")
    else:
        print("package: warning, SKILL.md header version line not found/updated", file=sys.stderr)
    return new


def write_manifest(version: str):
    files = iter_files(SKILL)
    hashes = {}
    for ap, rel in files:
        if rel in HASH_EXCLUDE:
            continue
        hashes[rel] = sha256_file(ap)
    MANIFEST.write_text(json.dumps({
        "schema": "black-dragon.sha256-manifest.v1",
        "version": version,
        "method": "SHA256 of packaged content (manifest and checksum list excluded); integrity, not a third-party signature",
        "files": hashes,
    }, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    SUMS.write_text("".join(f"{h}  {rel}\n" for rel, h in sorted(hashes.items())), encoding="utf-8")
    return len(hashes)


def verify_against_manifest():
    if not MANIFEST.exists():
        sys.exit("package --check: MANIFEST_SHA256.json is missing; run `tool package --no-zip` first")
    man = json.loads(MANIFEST.read_text(encoding="utf-8"))
    recorded = man.get("files", {})
    on_disk = {rel: ap for ap, rel in iter_files(SKILL) if rel not in HASH_EXCLUDE}
    mismatched, missing, extra = [], [], []
    for rel, want in recorded.items():
        ap = on_disk.get(rel)
        if ap is None:
            missing.append(rel)
        elif sha256_file(ap) != want:
            mismatched.append(rel)
    for rel in on_disk:
        if rel not in recorded:
            extra.append(rel)
    ok = not (mismatched or missing)
    print(json.dumps({
        "manifest_version": man.get("version"),
        "files_recorded": len(recorded),
        "files_on_disk": len(on_disk),
        "mismatched": mismatched[:20],
        "missing": missing[:20],
        "untracked": extra[:20],
        "ok": ok,
    }, ensure_ascii=False, indent=1))
    return 0 if ok else 1


def default_out() -> Path:
    for c in (Path.home() / "OneDrive" / "Desktop", Path.home() / "Desktop"):
        if c.is_dir():
            return c
    return Path.cwd()


def build_zip(version: str, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    zpath = out_dir / f"black-dragon-v{version}.zip"
    files = iter_files(SKILL)
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for ap, rel in files:
            z.write(ap, arcname=f"black-dragon/{rel}")
    return zpath


def main(argv=None):
    ap = argparse.ArgumentParser(prog="dragon.py tool package", description="Package the Black Dragon skill to a zip.")
    ap.add_argument("--out", help="output folder for the zip (default: Desktop)")
    ap.add_argument("--set-version", metavar="X", help="stamp a new version (e.g. 10.18.0) before packaging")
    ap.add_argument("--no-zip", action="store_true", help="refresh checksums in place; do not build a zip")
    ap.add_argument("--check", action="store_true", help="verify the tree against MANIFEST_SHA256.json; do nothing else")
    args = ap.parse_args(argv)

    if args.check:
        return verify_against_manifest()

    version = set_version(args.set_version) if args.set_version else read_version()
    n = write_manifest(version)

    result = {"version": version, "files_hashed": n}
    if args.no_zip:
        result["zip"] = None
        result["note"] = "checksums refreshed in place (--no-zip)"
        print(json.dumps(result, ensure_ascii=False, indent=1))
        return 0

    out_dir = Path(args.out) if args.out else default_out()
    zpath = build_zip(version, out_dir)

    # measure, do not assume
    with zipfile.ZipFile(zpath) as z:
        bad = z.testzip()
        members = len(z.namelist())
    result["zip"] = str(zpath)
    result["zip_sha256"] = sha256_file(zpath)
    result["zip_size_mb"] = round(zpath.stat().st_size / 1e6, 2)
    result["zip_members"] = members
    result["zip_integrity_ok"] = bad is None
    result["first_bad_file"] = bad
    print(json.dumps(result, ensure_ascii=False, indent=1))
    return 0 if bad is None else 1


if __name__ == "__main__":
    raise SystemExit(main())
