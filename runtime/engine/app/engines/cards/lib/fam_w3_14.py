"""Helpers of runners/fam_w3_14.py used by data cards, copied verbatim (the extractor binds a card to them only when
their AST hash with every dependency equals the original's)."""
from __future__ import annotations

from pathlib import Path
import json
import re
import shutil


def jw(path, obj):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
    return Path(path)


def route(prompt, attachments, installed, broad=False):
    p = prompt.lower()
    if re.fullmatch(r"\s*احسب\s+[\d\s+*/-]+", prompt):
        return {"action": "answer-direct", "skills": []}
    if "what can you do" in p:
        return {"action": "capability-summary", "skills": []}
    if any(w in p for w in ("انشر", "publish", "post to")):
        return {"action": "ask-approval", "skills": []}
    reel = "ريلز" in p or "reel" in p
    if reel and (broad or "audio" in attachments):
        skills = [s for s in ("audio-sync", "arabic-type") if s in installed]
        return {"action": "run", "skills": skills} if skills else {"action": "gap", "skills": []}
    if "بخط عربي" in p and "arabic-type" in installed:
        return {"action": "run", "skills": ["arabic-type"]}
    return {"action": "gap" if any(w in p for w in ("اعمل", "make")) else "answer", "skills": []}


def stale_probe(listing):
    return {k: ("downgraded" if (v == "ok" and not shutil.which(k)) else v) for k, v in listing.items()}
