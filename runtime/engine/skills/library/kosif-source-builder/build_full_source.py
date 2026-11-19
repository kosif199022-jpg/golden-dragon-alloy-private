#!/usr/bin/env python3
"""KOSIF full-source collector: clone original GitHub trees and archive them.

Uses only Python stdlib + installed Git, and optionally Git LFS.
Never runs source build scripts or installs dependencies. Does not bundle model weights.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import shutil
import subprocess
import sys
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "manifest" / "repositories.json"
ALLOWED_GROUPS = {"all", "own", "own-video", "own-extended", "filming", "editing", "vfx", "ai-video", "audio", "motion-extras"}


def registry(group: str) -> list[dict]:
    items = json.loads(MANIFEST.read_text(encoding="utf-8"))["repos"]
    if group == "all":
        return items
    if group == "own":
        return [r for r in items if r["group"].startswith("own-")]
    return [r for r in items if r["group"] == group]


def run(cmd: list[str], *, cwd: Path | None = None, timeout: int = 3600, interactive: bool = False) -> tuple[bool, str]:
    try:
        options = {} if interactive else {"stdout": subprocess.PIPE, "stderr": subprocess.STDOUT, "text": True, "errors": "replace"}
        env = os.environ.copy()
        env["GIT_TERMINAL_PROMPT"] = "0"
        env.setdefault("GIT_LFS_SKIP_SMUDGE", "1")
        result = subprocess.run(cmd, cwd=cwd, timeout=timeout, check=False, env=env, **options)
        return result.returncode == 0, ("" if interactive else (result.stdout or "")[-2500:])
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, str(exc)


def git_target(dest: Path, repo: dict) -> Path:
    group = repo["group"]
    return dest / group / repo["name"]


def clone_one(item: dict, dest: Path, *, submodules: bool, update: bool, lfs: bool, timeout: int, preserve_history: bool) -> dict:
    target = git_target(dest, item)
    url = item["clone"]
    target.parent.mkdir(parents=True, exist_ok=True)
    record = {"name": item["name"], "group": item["group"], "url": item["url"], "path": str(target.relative_to(dest)), "status": "failed", "commit": None, "error": None}
    print(f"\n[{item['group']}] {item['name']}", flush=True)
    try:
        if target.exists():
            if not (target / ".git").exists() and not (target / ".git").is_file():
                record["error"] = "Destination exists but is not a Git clone. Will not overwrite."
                print("  FAIL: destination folder exists and is not a Git repository", flush=True)
                return record
            if update:
                ok, log = run(["git", "-C", str(target), "pull", "--ff-only"], timeout=timeout)
                if not ok:
                    record["error"] = "Git update error: " + log[-500:]
                    print("  FAIL: update unsuccessful", flush=True)
                    return record
        else:
            command = ["git", "-c", "core.longpaths=true", "clone"]
            if not preserve_history:
                command.extend(["--depth", "1", "--single-branch"])
            if submodules:
                command.append("--recurse-submodules")
                if not preserve_history:
                    command.extend(["--shallow-submodules"])
            command.extend([url, str(target)])
            print("  Clone source tree ...", flush=True)
            ok, log = run(command, timeout=timeout)
            if not ok:
                record["error"] = "Git clone error: " + log[-900:]
                print("  FAIL: cannot clone", flush=True)
                if target.exists():
                    # Git may have left a partially cloned folder; never wipe it automatically.
                    print("  Partial folder retained for inspection", flush=True)
                return record
        if submodules:
            subcmd = ["git", "-C", str(target), "submodule", "update", "--init", "--recursive"]
            if not preserve_history:
                subcmd.extend(["--depth", "1"])
            ok, log = run(subcmd, timeout=timeout)
            if not ok:
                record["error"] = "Submodule error: " + log[-500:]
                print("  FAIL: submodules not complete", flush=True)
                return record
        if lfs and shutil.which("git-lfs"):
            ok, log = run(["git", "-C", str(target), "lfs", "pull"], timeout=timeout)
            if not ok:
                record["error"] = "LFS error: " + log[-500:]
                print("  FAIL: LFS download was requested but incomplete", flush=True)
                return record
        elif lfs:
            record["error"] = "Git LFS was requested but is not installed."
            return record
        ok, sha = run(["git", "-C", str(target), "rev-parse", "HEAD"], timeout=90)
        if not ok:
            record["error"] = "Cannot read commit SHA"
            return record
        record["commit"] = sha.strip().splitlines()[-1]
        record["status"] = "complete"
        print("  OK:", record["commit"][:12], flush=True)
        return record
    except Exception as e:
        record["error"] = repr(e)
        print("  FAIL: unexpected error", flush=True)
        return record


def gather_files(source: Path, *, keep_git: bool = False):
    for root, dirs, files in os.walk(source):
        dirs[:] = sorted(d for d in dirs if d not in ({"__pycache__", ".pytest_cache"} | (set() if keep_git else {".git"})))
        for d in list(dirs):
            p = Path(root) / d
            if p.is_symlink():
                yield p
                dirs.remove(d)
        for f in sorted(files):
            if f == ".git" and not keep_git:
                continue
            path = Path(root) / f
            if path.is_file() or path.is_symlink():
                yield path


def add_files(archive: zipfile.ZipFile, base: Path, *, prefix: str, keep_git: bool):
    file_count = 0
    byte_count = 0
    for path in gather_files(base, keep_git=keep_git):
        name = prefix + "/" + path.relative_to(base).as_posix()
        if path.is_symlink():
            info = zipfile.ZipInfo(name)
            info.create_system = 3
            info.external_attr = (stat.S_IFLNK | 0o777) << 16
            archive.writestr(info, os.readlink(path).encode("utf-8"))
            byte_count += len(os.readlink(path).encode("utf-8"))
        else:
            size = path.stat().st_size
            archive.write(path, arcname=name)
            byte_count += size
        file_count += 1
    return file_count, byte_count


def create_zip(output: Path, source: Path, records: list[dict], *, keep_git: bool, include_toolkit: bool, zip_timeout: int = 0) -> tuple[int, int]:
    success = [r for r in records if r["status"] == "complete"]
    missing = [r for r in records if r["status"] != "complete"]
    output.parent.mkdir(parents=True, exist_ok=True)
    total = 0
    bytes_total = 0
    status = "COMPLETE" if not missing else "INCOMPLETE"
    record_data = {"status": status, "created_utc": datetime.now(timezone.utc).isoformat(), "requested": len(records), "included": len(success), "missing": len(missing), "submodules": "as_requested", "contents": records}
    print(f"\nCreating ZIP ({len(success)}/{len(records)} repositories)...", flush=True)
    tmp = output.with_name(output.name + ".writing")
    try:
        with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=3, allowZip64=True) as z:
            z.writestr("KOSIF_FULL_SOURCE/BUILD_REPORT.json", json.dumps(record_data, ensure_ascii=False, indent=2))
            z.writestr("KOSIF_FULL_SOURCE/README_FIRST_AR.txt", "KOSIF SOURCE PACKAGE\n" + "حالة الحزمة: " + status + "\n" + f"مستودعات مكتملة: {len(success)}/{len(records)}\n" + "اقرأ BUILD_REPORT.json لمعرفة الملفات والمستودعات الناقصة.\n" + "شيفرات الجهات الخارجية مملوكة لأصحابها وتخضع لتراخيصها.\n" + "لا تتضمن الحزمة أوزان نماذج الفيديو أو مثبتات التطبيقات أو الاعتماديات الخارجية.\n")
            for r in success:
                folder = source / r["path"]
                count, nbytes = add_files(z, folder, prefix="KOSIF_FULL_SOURCE/repositories/" + r["path"].replace("\\", "/"), keep_git=keep_git)
                print(f"  ZIP: {r['name']} — {count} files, {nbytes/1024**2:.1f} MiB", flush=True)
                total += count
                bytes_total += nbytes
            if include_toolkit:
                for p in gather_files(ROOT, keep_git=False):
                    if p.relative_to(ROOT).parts[0] in {"workspace", "output", "dist"}:
                        continue
                    z.write(p, arcname="KOSIF_FULL_SOURCE/KOSIF_TOOLKIT/" + p.relative_to(ROOT).as_posix())
        os.replace(tmp, output)
    finally:
        if tmp.exists():
            try: tmp.unlink()
            except OSError: pass
    return total, bytes_total


def main():
    ap = argparse.ArgumentParser(description="Download full original source trees and build an offline ZIP archive")
    ap.add_argument("--group", choices=sorted(ALLOWED_GROUPS), default="all", help="Repository group (all by default)")
    ap.add_argument("--dest", type=Path, default=ROOT / "workspace" / "full-source", help="Local clone cache")
    ap.add_argument("--out", type=Path, default=ROOT / "output" / "KOSIF_ALL_SOURCE.zip", help="Output ZIP path")
    ap.add_argument("--update", action="store_true", help="Update pre-existing clones with fast-forward only")
    ap.add_argument("--with-lfs", action="store_true", help="Fetch Git LFS assets too (can be huge; requires git-lfs)")
    ap.add_argument("--preserve-history", action="store_true", help="Clone full Git history instead of latest shallow source tree")
    ap.add_argument("--include-git", action="store_true", help="Also put .git histories in ZIP (can be very large)")
    ap.add_argument("--no-submodules", action="store_true", help="Skip third-party Git submodules")
    ap.add_argument("--no-toolkit", action="store_true", help="Exclude this collector's own source code")
    ap.add_argument("--limit", type=int, default=0, help="Limit repos for testing (0=all)")
    ap.add_argument("--archive-only", action="store_true", help="Use already cloned source directories without cloning")
    ap.add_argument("--allow-incomplete", action="store_true", help="Generate INCOMPLETE ZIP if some clones fail (default does not archive partial package)")
    ap.add_argument("--timeout", type=int, default=3600, help="Per-repo clone timeout in seconds")
    args = ap.parse_args()
    if not args.archive_only and not shutil.which("git"):
        ap.error("Git is required: https://git-scm.com/downloads")
    if args.include_git and not args.preserve_history:
        print("NOTE: archive includes shallow Git history by default; use --preserve-history for full commit history.")
    items = registry(args.group)
    if args.limit > 0:
        items = items[:args.limit]
    dest = args.dest.resolve()
    output = args.out.resolve()
    print(f"KOSIF SOURCE BUILDER — {len(items)} repositories — {datetime.now().isoformat(timespec='seconds')}")
    print(f"Cache: {dest}\nZIP:   {output}", flush=True)
    records = []
    for i, item in enumerate(items, 1):
        print(f"[{i}/{len(items)}]", end="", flush=True)
        if args.archive_only:
            target = git_target(dest, item)
            rec = {"name": item["name"], "group": item["group"], "url": item["url"], "path": str(target.relative_to(dest)), "status": "complete" if target.is_dir() else "failed", "commit": None, "error": None if target.is_dir() else "Source folder missing"}
        else:
            rec = clone_one(item, dest, submodules=not args.no_submodules, update=args.update, lfs=args.with_lfs, timeout=args.timeout, preserve_history=args.preserve_history)
        records.append(rec)
        # Keep a report even if interrupted.
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "KOSIF_DOWNLOAD_REPORT.json").write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    failures = [r for r in records if r["status"] != "complete"]
    if failures and not args.allow_incomplete:
        print(f"\nINCOMPLETE: {len(failures)}/{len(items)} repositories could not be collected.")
        print("A full archive has NOT been produced. Check workspace/full-source/KOSIF_DOWNLOAD_REPORT.json.")
        print("Retry after fixing access/network, then run the same command.")
        print("If a partial labeled archive is acceptable, add --allow-incomplete.")
        return 2
    if failures:
        output = output.with_name(output.stem + "_INCOMPLETE" + output.suffix)
    files, raw_bytes = create_zip(output, dest, records, keep_git=args.include_git, include_toolkit=not args.no_toolkit)
    digest = hashlib.sha256()
    with open(output, "rb") as stream:
        for block in iter(lambda: stream.read(1024*1024), b""):
            digest.update(block)
    verification = {"archive": str(output), "sha256": digest.hexdigest(), "files": files, "uncompressed_repo_bytes": raw_bytes, "repositories": len(items), "complete": len(items)-len(failures)}
    path = output.with_suffix(output.suffix + ".sha256.json")
    path.write_text(json.dumps(verification, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\nREADY:", output)
    print("SHA256:", digest.hexdigest())
    print("Repositories:", len(items)-len(failures), "/", len(items))
    return 0 if not failures else 2


if __name__ == "__main__":
    sys.exit(main())
