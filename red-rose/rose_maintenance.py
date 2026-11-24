"""V46 native bounded maintenance. No model, network, installation or owner memory access."""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parent
OLD_HASH = "    digest=hashlib.sha256(p.read_bytes()).hexdigest()"
NEW_HASH = """    # Stream large video hashes instead of allocating a second copy in RAM.
    h = hashlib.sha256()
    with p.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    digest = h.hexdigest()"""
RULES = {"verify_media.py": (OLD_HASH, NEW_HASH)}
TESTS = ("test_maintenance_v46", "test_env_v29", "test_verify_media")


def candidate(text, old, new):
    """Only exact single known regression patterns can be repaired automatically."""
    if text.count(old) != 1:
        return None
    changed = text.replace(old, new, 1)
    ast.parse(changed)
    return changed


def audit(root=ROOT):
    root = Path(root)
    syntax_errors, repairs = [], []
    files = sorted(root.glob("*.py"))
    for path in files:
        if path.is_symlink():
            syntax_errors.append({"file": path.name, "error": "symlink refused"})
            continue
        try:
            ast.parse(path.read_text(encoding="utf-8"), filename=path.name)
        except (SyntaxError, UnicodeError, OSError) as exc:
            syntax_errors.append({"file": path.name, "error": type(exc).__name__,
                                  "line": getattr(exc, "lineno", None)})
    for name, (old, new) in RULES.items():
        path = root / name
        if path.is_symlink() or not path.is_file():
            continue
        try:
            if candidate(path.read_text(encoding="utf-8"), old, new) is not None:
                repairs.append(name)
        except (OSError, UnicodeError, SyntaxError):
            pass
    return {"ok": bool(files) and not syntax_errors and not repairs,
            "files_checked": len(files), "syntax_errors": syntax_errors,
            "known_repairs": repairs, "unknown_errors": "require agent diagnosis and a regression test"}


def run_tests(root=ROOT, *, timeout=180, overlay=None, tests=TESTS):
    """Bounded isolated test process, never use the owner's actual memory database."""
    if not 1 <= timeout <= 900:
        raise ValueError("timeout must be 1..900 seconds")
    root = Path(root).resolve()
    with tempfile.TemporaryDirectory(prefix="rose-maintenance-test-") as tmp:
        env = dict(os.environ)
        env.update(RED_ROSE_DB=str(Path(tmp) / "test.sqlite3"),
                   PYTHONDONTWRITEBYTECODE="1", PYTHONUTF8="1",
                   PYTHONPATH=str(root))
        start = time.monotonic()
        try:
            proc = subprocess.run([sys.executable, "-m", "unittest", *tests],
                                  cwd=overlay or root, env=env, capture_output=True,
                                  text=True, encoding="utf-8", errors="replace", timeout=timeout)
            return {"ok": proc.returncode == 0, "returncode": proc.returncode,
                    "seconds": round(time.monotonic()-start, 3),
                    "summary": "\n".join(proc.stderr.splitlines()[-4:])}
        except subprocess.TimeoutExpired:
            return {"ok": False, "returncode": 124, "seconds": round(time.monotonic()-start, 3),
                    "summary": "test budget exceeded; no repair approved"}


def repair(root=ROOT, *, approve=False, timeout=180):
    """Test a known candidate in a temporary overlay, then atomically install it if unchanged."""
    root = Path(root).resolve()
    found = audit(root)
    names = found["known_repairs"]
    if not names:
        return {"ok": found["ok"], "status": "clean" if found["ok"] else "needs_agent",
                "changed": [], "audit": found}
    if not approve:
        return {"ok": False, "status": "approval_required", "would_change": names}
    # One repair per invocation. Never rewrite unknown source or user data.
    if found["syntax_errors"] or len(names) != 1:
        return {"ok": False, "status": "needs_agent", "changed": []}
    name = names[0]
    path = root / name
    original = path.read_bytes()
    before = hashlib.sha256(original).hexdigest()
    updated = candidate(original.decode("utf-8"), *RULES[name])
    if updated is None:
        return {"ok": False, "status": "source_changed", "changed": []}
    with tempfile.TemporaryDirectory(prefix="rose-candidate-") as tmp:
        (Path(tmp) / name).write_text(updated, encoding="utf-8")
        tests = run_tests(root, timeout=timeout, overlay=tmp,
                          tests=("test_maintenance_v46", "test_verify_media"))
        if not tests["ok"]:
            return {"ok": False, "status": "candidate_rejected", "tests": tests, "changed": []}
    # No commit, push, install or network. Preserve the original mode; check the source again.
    fd, staged = tempfile.mkstemp(prefix=".rose-repair-", dir=root)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(updated.encode("utf-8"))
        os.chmod(staged, path.stat().st_mode & 0o777)
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != before:
            return {"ok": False, "status": "source_changed", "changed": []}
        os.replace(staged, path)
    finally:
        if os.path.exists(staged):
            os.unlink(staged)
    return {"ok": True, "status": "repaired", "changed": names, "tests": tests,
            "before_sha256": before, "after_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def benchmark(repeats=3):
    """Compare original per-op lookup path against the snapshot; fail on different counts."""
    if not 1 <= repeats <= 5:
        raise ValueError("repeats must be 1..5")
    import rose_catalog
    import rose_env
    entries = rose_catalog.load()["entries"]
    def old():
        counts = dict.fromkeys(rose_env.LABELS, 0)
        for op in entries:
            label = rose_env.readiness(op)
            if label:
                counts[label] += 1
        return counts
    old_times, new_times = [], []
    for _ in range(repeats):
        t = time.perf_counter()
        baseline = old()
        old_times.append(time.perf_counter()-t)
        t = time.perf_counter()
        actual = rose_env.usable_counts()
        new_times.append(time.perf_counter()-t)
        if actual != baseline:
            return {"ok": False, "reason": "readiness counts differ"}
    a, b = statistics.median(old_times), statistics.median(new_times)
    return {"ok": True, "operations": len(entries), "repeats": repeats,
            "baseline_seconds": round(a, 6), "snapshot_seconds": round(b, 6),
            "speedup": round(a/b, 2) if b else None,
            "scope": "warm readiness count only, not media rendering or full startup"}


def handle(args):
    if args.action == "audit":
        result = audit()
    elif args.action == "test":
        result = run_tests(timeout=args.timeout)
    elif args.action == "repair":
        result = repair(approve=args.approve_write, timeout=args.timeout)
    else:
        result = benchmark(args.repeats)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 3 if result.get("status") == "approval_required" else 1


def register(subparsers):
    parser = subparsers.add_parser("maintain", help="bounded audit, tests, benchmark and approved exact repair")
    parser.add_argument("action", choices=("audit", "test", "repair", "benchmark"))
    parser.add_argument("--approve-write", action="store_true")
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--repeats", type=int, default=3)
    parser.set_defaults(ext_func=handle)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    subs = parser.add_subparsers(required=True)
    register(subs)
    args = parser.parse_args(["maintain", *sys.argv[1:]])
    raise SystemExit(handle(args))
