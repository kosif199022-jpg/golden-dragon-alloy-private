"""Helpers of power_programs/security_safety.py used by data cards, copied verbatim (the extractor binds a card to them only when
their AST hash with every dependency equals the original's)."""
from __future__ import annotations

from pathlib import Path
import ipaddress
import json
import os
import re
import shlex
import subprocess
from urllib.parse import urlparse


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


def _git(repo: Path, *args, check=True):
    env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@example.invalid", GIT_COMMITTER_NAME="t",
               GIT_COMMITTER_EMAIL="t@example.invalid", GIT_CONFIG_NOSYSTEM="1", HOME=str(repo.parent))
    r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, env=env)
    if check and r.returncode:
        raise RuntimeError(r.stderr)
    return r


def _fakes() -> dict:
    return {"openai": "sk-" + "A1b2C3d4E5f6G7h8I9j0",
            "anthropic": "sk-ant-" + "api03-" + "x" * 20,
            "github": "ghp_" + "Ab3" * 12,
            "github_pat": "github_pat_" + "11ABCDEFG" + "0" * 20,
            "aws": "AKIA" + "IOSFODNN7EXAMPLE",
            "slack": "xoxb-" + "1234-5678-abcdef",
            "private_key": "-----BEGIN RSA " + "PRIVATE KEY-----",
            "bearer": "Authorization: Bearer " + "eyJhbGciOiJIUzI1NiJ9abc",
            "json_password": '"password": "' + "hunter22secret" + '"'}


CARD_SECRET_RE = re.compile(r'sk-[A-Za-z0-9_-]{16,}|sk-ant-|ghp_[A-Za-z0-9]{36}|github_pat_|AKIA[0-9A-Z]{16}|xox[baprs]-|'
                            r'-----BEGIN [A-Z ]*PRIVATE KEY-----|Authorization: Bearer [A-Za-z0-9._-]{12,}|'
                            r'"(password|token|secret)"\s*:\s*"[^"]{6,}"')


INJECTION_RE = re.compile(r"ignore (all )?previous instructions|run sudo|curl [^|]*\|\s*(ba)?sh|you are now|"
                          r"send (it|the|your) .* to https?://", re.I)


def _url_ok(url, resolver):
    u = urlparse(url)
    if u.scheme not in ("http", "https") or not u.hostname:
        return False
    ip = ipaddress.ip_address(resolver(u.hostname))
    return not (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast)


def _ver(v):
    return tuple(int(x) for x in v.split("."))


def segment(cmd):
    if re.search(r"\$\(|`", cmd):
        return None  # substitution: never auto-match
    lex = shlex.shlex(cmd, posix=True, punctuation_chars=";&|<>")
    lex.whitespace_split = True
    segs, cur = [], []
    for tok in lex:
        if tok in ("|", "&&", "||", ";", "&"):
            segs.append(cur)
            cur = []
        elif tok in (">", ">>", "<"):
            return None  # redirection: never auto-match
        else:
            cur.append(tok)
    segs.append(cur)
    return [s for s in segs if s]
