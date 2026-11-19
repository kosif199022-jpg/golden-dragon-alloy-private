"""Helpers of power_programs/api_testing.py used by data cards, copied verbatim (the extractor binds a card to them only when
their AST hash with every dependency equals the original's)."""
from __future__ import annotations

from pathlib import Path
import base64
import hashlib
import hmac
import json
import re


def _w(work: Path, name: str, data) -> Path:
    p = work / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(data if isinstance(data, str) else json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


def parse_bru(text: str) -> dict:
    """Parse top-level Bru blocks: `tag {` ... `}`; dictionary blocks become dicts, body/script/tests stay text."""
    blocks, lines, i = {}, text.splitlines(), 0
    while i < len(lines):
        m = re.match(r"^([\w:-]+)\s*\{\s*$", lines[i])
        if not m:
            i += 1
            continue
        tag, i, inner = m.group(1), i + 1, []
        while i < len(lines) and lines[i] != "}":
            inner.append(lines[i])
            i += 1
        i += 1
        if tag.startswith(("body", "script", "tests", "docs")):
            blocks[tag] = "\n".join(l[2:] if l.startswith("  ") else l for l in inner)
        else:
            d = {}
            for l in inner:
                if ":" in l:
                    k, v = l.strip().split(":", 1)
                    d[k.strip()] = v.strip()
            blocks[tag] = d
    return blocks


def dump_bru(blocks: dict) -> str:
    out = []
    for tag, val in blocks.items():
        out.append(f"{tag} {{")
        if isinstance(val, dict):
            out += [f"  {k}: {v}" for k, v in val.items()]
        else:
            out += [f"  {l}" for l in val.splitlines()]
        out.append("}\n")
    return "\n".join(out)


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def jwt_sign(payload: dict, secret: str, header=None) -> str:
    header = header or {"alg": "HS256", "typ": "JWT"}
    seg = _b64(json.dumps(header, separators=(",", ":")).encode()) + "." + _b64(json.dumps(payload, separators=(",", ":")).encode())
    return seg + "." + _b64(hmac.new(secret.encode(), seg.encode(), hashlib.sha256).digest())


def jwt_verify(token: str, secret: str) -> bool:
    seg, sig = token.rsplit(".", 1)
    return hmac.compare_digest(_b64(hmac.new(secret.encode(), seg.encode(), hashlib.sha256).digest()), sig)
