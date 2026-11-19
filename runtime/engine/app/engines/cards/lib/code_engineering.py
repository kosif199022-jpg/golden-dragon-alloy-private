"""Helpers of power_programs/code_engineering.py used by data cards, copied verbatim (the extractor binds a card to them only when
their AST hash with every dependency equals the original's)."""
from __future__ import annotations

from pathlib import Path
import json
import os
import re
import subprocess
import time


def _w(work: Path, name: str, data) -> Path:
    p = work / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(data if isinstance(data, str) else json.dumps(data, ensure_ascii=False, indent=2, default=str),
                 encoding="utf-8")
    return p


def _tree(root: Path, files: dict) -> Path:
    for rel, text in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    return root


GIT_ENV = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid", "GIT_COMMITTER_NAME": "t",
           "GIT_COMMITTER_EMAIL": "t@example.invalid", "GIT_CONFIG_NOSYSTEM": "1", "HOME": "/nonexistent"}


def _git(repo: Path, *args) -> str:
    env = dict(os.environ, **GIT_ENV)
    env["HOME"] = str(repo.parent)
    r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, env=env)
    if r.returncode not in (0, 1):
        raise RuntimeError(r.stderr)
    return r.stdout


def _git_init(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-q", "-b", "main")


SECRET_RE = re.compile(r"sk-[A-Za-z0-9_-]{16,}|ghp_[A-Za-z0-9]{36}|AKIA[0-9A-Z]{16}|api_key\s*=")


DEBUG_RE = re.compile(r"console\.log|debugger|\bprint\(\s*['\"]debug")


def _timeit(fn):
    t = time.perf_counter()
    fn()
    return time.perf_counter() - t
