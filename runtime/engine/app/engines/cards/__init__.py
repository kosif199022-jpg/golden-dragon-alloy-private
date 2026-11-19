"""ONE interpreter for every method card: data/cards/*.json -> fixture, method, measurement, known-answer checks.

A data card's ``program`` is straight-line formula text (engines.cards.formula) over ops it binds by name:
``core.check``/``core.fx`` (the old harness) and helper packs in engines/cards/lib (fixtures such as click
tracks, tones, index clips; ffmpeg/numpy operations; measurements such as ebur128, peak frequency, frame
index). ``custom`` cards run a hand port from engines/cards/custom.py. The verdict rule is the old one:
executed = every check passed and at least one non-empty output file exists.
"""
from __future__ import annotations

import ast
import collections
import importlib
import json
import shutil
import tempfile
import time
import traceback
from functools import lru_cache
from pathlib import Path

from . import formula

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "cards"
TASK = "اعمل فيديو موشن عربي قصير"  # the task string the old --build passed to every runner


@lru_cache(maxsize=1)
def cards() -> dict:
    out = {}
    for f in sorted(DATA.glob("*.json")):
        if f.name.startswith("_"):
            continue
        for r in json.loads(f.read_text(encoding="utf-8")):
            out[r["id"]] = r
    return out


def op(ref: str):
    """'core.check' / 'fam_music_beat_sound.song_fixture' -> the callable (packs import lazily)."""
    mod, _, name = ref.rpartition(".")
    return getattr(importlib.import_module("engines.cards.lib." + mod), name)


def _env(prog: dict) -> dict:
    env = {k: ast.literal_eval(v) for k, v in prog.get("consts", {}).items()}  # exact literals (tuples, sets)
    for local, spec in prog.get("imports", {}).items():
        env[local] = formula.resolve_import(spec)                            # whitelisted modules only
    for local, ref in prog.get("bind", {}).items():
        env[local] = op(ref)
    return env


def execute(rec: dict, wd: Path):
    """Run one card in ``wd``; returns (checks as dicts, output paths)."""
    corpus = rec["source"]["corpus"]
    if rec["status"] == "custom":
        from .custom import CUSTOM
        value = CUSTOM[rec["id"]](Path(wd))
    else:
        prog = rec["program"]
        args = [TASK if a == "task" else Path(wd) for a in prog["args"]]
        value = formula.run_card(prog["def"], args, _env(prog))
    if corpus == "runner" or rec["status"] == "custom":
        checks, outputs = value
        return [dict(c) for c in checks], [Path(o) for o in outputs or []]
    rows = [{"check": str(n), "passed": bool(ok), "measured": str(obs)[:400], "expected": None} for n, ok, obs in value]
    return rows, [p for p in sorted(Path(wd).rglob("*")) if p.is_file()]


def run(card_id: str, wd: Path | None = None) -> dict:
    rec = cards().get(card_id)
    if rec is None:
        return {"id": card_id, "verdict": "unknown", "reason": "no such card"}
    res = {"id": card_id, "family": rec["family"], "status": rec["status"]}
    if rec["status"] not in ("data", "custom"):
        res.update(verdict="not-ported", reason=rec.get("reason"))
        return res
    own = wd is None
    wd = Path(tempfile.mkdtemp(prefix="card-")) if own else Path(wd)
    wd.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    try:
        checks, outputs = execute(rec, wd)
    except Exception as exc:  # the card's program failed: report, never pretend
        res.update(verdict="error", reason="%s: %s" % (type(exc).__name__, str(exc)[:300]), trace=traceback.format_exc()[-600:],
                   seconds=round(time.time() - t0, 3))
        return res
    outs = [{"path": o.name, "bytes": o.stat().st_size if o.is_file() else 0} for o in outputs]
    ok = bool(checks) and all(c["passed"] for c in checks) and any(o["bytes"] > 0 for o in outs)
    res.update(verdict="executed" if ok else "failed", seconds=round(time.time() - t0, 3), checks=checks, outputs=outs[:50])
    if not ok:
        res["reason"] = "failed checks: " + ", ".join(c["check"] for c in checks if not c["passed"]) if checks else "no checks"
    if own:
        shutil.rmtree(wd, ignore_errors=True)
    return res


def stats() -> dict:
    rs = list(cards().values())
    st = collections.Counter(r["status"] for r in rs)
    runnable = sum(v for k, v in st.items() if k != "gap")
    fam = collections.defaultdict(collections.Counter)
    for r in rs:
        fam[r["family"]][r["status"]] += 1
    return {"cards": len(rs), "status": dict(st),
            "coverage_of_runnable_pct": {k: round(100 * st[k] / max(1, runnable), 1) for k in ("data", "custom", "not_ported")},
            "families": {f: dict(c) for f, c in sorted(fam.items())}}
