"""Helpers of power_programs/atlas_code.py used by data cards, copied verbatim (the extractor binds a card to them only when
their AST hash with every dependency equals the original's)."""
from __future__ import annotations

from collections import Counter
from pathlib import Path
import ast
from collections import defaultdict
import hashlib
import hmac
import json
import math
import os
import random
import re
import subprocess


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
               GIT_COMMITTER_EMAIL="t@example.invalid", GIT_CONFIG_NOSYSTEM="1", HOME=str(repo.parent),
               GIT_AUTHOR_DATE="2026-01-01T00:00:00Z", GIT_COMMITTER_DATE="2026-01-01T00:00:00Z")
    r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, env=env)
    if check and r.returncode:
        raise RuntimeError(f"git {args}: {r.stderr}")
    return r.stdout if check else r


def _repo(root: Path, files: dict, msg="init") -> Path:
    root.mkdir(parents=True, exist_ok=True)
    _git(root, "init", "-q", "-b", "main")
    _tree(root, files)
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", msg)
    return root


def _commit(repo: Path, files: dict, msg: str) -> str:
    _tree(repo, files)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", msg)
    return _git(repo, "rev-parse", "HEAD").strip()


def _hmac_hex(secret: bytes, body: bytes) -> str:
    return hmac.new(secret, body, hashlib.sha256).hexdigest()


def _fake_secret(kind: str) -> str:
    return {"aws": "AKIA" + "Q3EXAMPLEKEY7ZZ9", "slack": "xoxb-" + "9988-7766-abcdefghij",
            "npm": "npm_" + "a1" * 18, "gh": "ghp_" + "Zx9" * 12,
            "pk": "-----BEGIN OPENSSH " + "PRIVATE KEY-----"}[kind]


DOC_KEY = "AKIA" + "IOSFODNN7EXAMPLE"


SECRET_RE = re.compile(r"AKIA[0-9A-Z]{16}|ASIA[0-9A-Z]{16}|xox[baprs]-[0-9A-Za-z-]{10,}|npm_[A-Za-z0-9]{36}|"
                       r"ghp_[A-Za-z0-9]{36}|-----BEGIN [A-Z ]*PRIVATE KEY-----|sk-[A-Za-z0-9_-]{16,}")


def _redact(text: str) -> str:
    return SECRET_RE.sub(lambda m: m.group(0)[:4] + "…[REDACTED]", text)


def _backoff(attempt: int, base: float, cap: float, rng: random.Random, jitter=1.0) -> float:
    return min(cap, base * 2 ** attempt) + rng.uniform(0, jitter)


def _raises(fn, exc) -> bool:
    try:
        fn()
    except exc:
        return True
    return False


def _der_len(n):
    return bytes([n]) if n < 128 else bytes([0x81, n]) if n < 256 else bytes([0x82, n >> 8, n & 255])


def _rsa_spki(bits):
    mod = b"\x00" + bytes([0xC3]) + os.urandom(bits // 8 - 1)
    e = b"\x01\x00\x01"
    seq = b"\x02" + _der_len(len(mod)) + mod + b"\x02" + _der_len(len(e)) + e
    rsakey = b"\x30" + _der_len(len(seq)) + seq
    bitstr = b"\x03" + _der_len(len(rsakey) + 1) + b"\x00" + rsakey
    alg = bytes.fromhex("300d06092a864886f70d0101010500")
    body = alg + bitstr
    return b"\x30" + _der_len(len(body)) + body


def _spki_bits(der):
    i = der.index(b"\x02", 20)  # first INTEGER inside the RSA key
    ln = der[i + 1]
    if ln & 0x80:
        k = ln & 0x7F
        ln = int.from_bytes(der[i + 2:i + 2 + k], "big")
        i += k
    mod = der[i + 2:i + 2 + ln].lstrip(b"\x00")
    return mod[0].bit_length() + 8 * (len(mod) - 1)


def _stripe_sig(secret, payload: bytes, t: int):
    return f"t={t},v1=" + hmac.new(secret.encode(), f"{t}.".encode() + payload, hashlib.sha256).hexdigest()


def _callgraph(root: Path):
    defs, calls = {}, defaultdict(set)
    for p in sorted(root.rglob("*.py")):
        tree = ast.parse(p.read_text())
        for fn in [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]:
            defs[fn.name] = f"{p.relative_to(root)}:{fn.lineno}"
            for c in ast.walk(fn):
                if isinstance(c, ast.Call):
                    name = c.func.id if isinstance(c.func, ast.Name) else getattr(c.func, "attr", None)
                    if name:
                        calls[fn.name].add(name)
    return defs, calls


def _crc16_xmodem(data: bytes) -> int:
    crc = 0
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


def _redis_slot(key: str) -> int:
    s = key.find("{")
    if s != -1:
        e = key.find("}", s + 1)
        if e > s + 1:
            key = key[s + 1:e]
    return _crc16_xmodem(key.encode()) % 16384


def _system_fixture():
    """A toy service whose cache returns stale prices after an update: the planted root cause."""
    evidence = {"logs": ["price update id=7 -> 12", "GET id=7 -> 10 (cache hit)", "db row id=7 = 12"],
                "metrics": {"db_latency_ms": 4, "cache_ttl_s": 3600, "error_rate": 0.0}, "config": {"cache_invalidate_on_write": False}}
    hypotheses = {"db replication lag": lambda e: e["metrics"]["db_latency_ms"] > 100 or "db row id=7 = 10" in e["logs"],
                  "stale cache not invalidated on write": lambda e: not e["config"]["cache_invalidate_on_write"] and any("cache hit" in l for l in e["logs"]),
                  "client rounding bug": lambda e: any("round" in l for l in e["logs"]),
                  "network errors": lambda e: e["metrics"]["error_rate"] > 0.01}
    return evidence, hypotheses


def _classify_api_error(status, body, method="GET", keyed=False):
    if status is None:
        cls = "transport"
    elif status in (401,):
        cls = "auth"
    elif status in (402, 403):
        cls = "authorization/plan"
    elif status in (400, 404, 409, 422):
        cls = "validation"
    elif status == 429:
        cls = "rate limit"
    elif status >= 500:
        cls = "provider outage" if status in (502, 503, 504) else "upstream"
    elif status == 202:
        cls = "async-state"
    else:
        cls = "ok-empty" if body in ({}, [], {"data": []}) else "ok"
    retry = cls in ("transport", "rate limit", "provider outage", "upstream") and (method in ("GET", "HEAD", "PUT", "DELETE") or keyed)
    return cls, retry


def _tok(t):
    return re.findall(r"[a-z0-9]+", t.lower())


def _bm25(docs, q, k1=1.5, b=0.75):
    toks = [_tok(d) for d in docs]
    avg = sum(map(len, toks)) / len(toks)
    df = Counter(w for t in toks for w in set(t))
    N = len(docs)
    scores = []
    for t in toks:
        tf = Counter(t)
        s = 0.0
        for w in _tok(q):
            if w in tf:
                idf = math.log(1 + (N - df[w] + 0.5) / (df[w] + 0.5))
                s += idf * tf[w] * (k1 + 1) / (tf[w] + k1 * (1 - b + b * len(t) / avg))
        scores.append(s)
    return scores


def _embed(t, dim=64):
    v = [0.0] * dim
    for w in _tok(t):
        for g in (w[i:i + 3] for i in range(max(1, len(w) - 2))):
            v[int(hashlib.md5(g.encode()).hexdigest(), 16) % dim] += 1
    n = math.sqrt(sum(x * x for x in v)) or 1
    return [x / n for x in v]


def _rrf(rankings, k=60):
    s = defaultdict(float)
    for r in rankings:
        for i, d in enumerate(r):
            s[d] += 1 / (k + i + 1)
    return sorted(s, key=lambda d: (-s[d], d))
