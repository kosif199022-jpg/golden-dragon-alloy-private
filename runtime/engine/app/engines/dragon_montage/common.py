"""Shared contracts and plumbing for every Dragon Montage station (see CONTRACTS in __init__).

Job files are plain JSON with a "schema"; every external tool call appends a receipt line to receipts.jsonl.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from functools import lru_cache
from pathlib import Path

from ..deliver import fit_audio
from ..media import exe

PKG = Path(__file__).resolve().parent
DATA = PKG / "data"
MODELS = PKG / "models"
# caption fonts: $DRAGON_FONT_DIRS (os.pathsep list) first, then the repo's shipped Arabic fonts
FONT_DIRS = [Path(p) for p in os.environ.get("DRAGON_FONT_DIRS", "").split(os.pathsep) if p] + [
    PKG / "assets" / "fonts", PKG.parent / "cinema" / "assets" / "fonts"]

SCHEMAS = {k: f"kosif.dm.{k}.v1" for k in ("job", "analysis", "brief", "concepts", "look", "edl", "render", "review")}
REQUIRED = {
    "analysis": ["clips", "music", "tools_used", "missing"],
    "brief": ["task", "platform", "aspect", "target_seconds", "feeling", "content_type"],
    "concepts": ["concepts", "decision"],
    "look": ["style_id", "grade", "transitions", "captions"],
    "edl": ["width", "height", "fps", "events", "audio", "captions", "duration"],
    "render": ["final", "verify"],
    "review": ["round", "checks", "fixes", "verdict"],
}
ASPECTS = {"9:16": (1080, 1920), "16:9": (1920, 1080), "1:1": (1080, 1080), "4:5": (1080, 1350)}
TEXT = {"text": True, "encoding": "utf-8", "errors": "replace"}


class ContractError(ValueError):
    pass


def validate(kind: str, data: dict) -> dict:
    if not isinstance(data, dict):
        raise ContractError(f"{kind}: not an object")
    if data.get("schema") != SCHEMAS[kind]:
        raise ContractError(f"{kind}: schema must be {SCHEMAS[kind]}, got {data.get('schema')!r}")
    missing = [k for k in REQUIRED.get(kind, []) if k not in data]
    if missing:
        raise ContractError(f"{kind}: missing keys {missing}")
    for i, ev in enumerate(data["events"] if kind == "edl" else []):
        for k in ("id", "clip", "src_in", "src_out", "rec_in", "reason"):
            if k not in ev:
                raise ContractError(f"edl.events[{i}] missing {k}")
        if not ev["src_out"] > ev["src_in"]:
            raise ContractError(f"edl.events[{i}] src_out must be > src_in")
        if not str(ev["reason"]).strip():
            raise ContractError(f"edl.events[{i}] needs a reason")
    return data


def new(kind: str, **fields) -> dict:
    return {"schema": SCHEMAS[kind], **fields}


def job_dir(path) -> Path:
    p = Path(path).resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p


def read(job, kind: str) -> dict:
    f = Path(job) / f"{kind}.json"
    if not f.exists():
        raise FileNotFoundError(f"{f} not found: run the station that writes {kind}.json first")
    return validate(kind, json.loads(f.read_text(encoding="utf-8")))


def read_opt(job, kind: str, default=None):
    try:
        return read(job, kind)
    except (FileNotFoundError, ContractError, ValueError):
        return default


def write(job, kind: str, data: dict) -> Path:
    validate(kind, data)
    return save(Path(job) / f"{kind}.json", data)


def save(path, obj, indent=2) -> Path:
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=indent), encoding="utf-8")
    return Path(path)


@lru_cache(maxsize=None)
def data(name: str):
    """A table from data/ (cached; callers must not mutate it)."""
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def sha256(path) -> str | None:
    p = Path(path)
    if not p.is_file():
        return None
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def have(binary: str) -> bool:
    try:
        return bool(exe(binary)) if binary in ("ffmpeg", "ffprobe") else shutil.which(binary) is not None
    except FileNotFoundError:
        return False


def have_module(name: str) -> bool:
    import importlib.util
    return importlib.util.find_spec(name) is not None


def utf8_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError, OSError):
            pass


def receipt(job, station, tool, argv, rc, seconds, out=None, note="", owner_media=True) -> None:
    rec = {"station": station, "tool": tool, "argv": [str(a) for a in argv][:40], "rc": rc,
           "seconds": round(seconds, 3), "owner_media": owner_media,
           "sha256_out": sha256(out) if out else None, "stderr_tail": note[-400:]}
    with (Path(job) / "receipts.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


def run(job, station: str, tool: str, argv: list, *, out=None, timeout: int = 900, owner_media: bool = True,
        check: bool = True, cwd=None) -> subprocess.CompletedProcess:
    """Run a command with a receipt. ffmpeg/ffprobe resolve through engines.media.exe. A timeout comes back as
    rc=124 (stations degrade it into `missing`); check=True turns a failure into RuntimeError."""
    t0 = time.time()
    args = [str(a) for a in argv]
    if args and args[0] in ("ffmpeg", "ffprobe"):
        args[0] = exe(args[0])
    try:
        res = subprocess.run(args, capture_output=True, timeout=timeout, cwd=str(cwd) if cwd else None, **TEXT)
    except subprocess.TimeoutExpired as exc:
        dec = lambda x: x.decode("utf-8", "replace") if isinstance(x, bytes) else (x or "")  # noqa: E731
        res = subprocess.CompletedProcess(args, 124, dec(exc.stdout), dec(exc.stderr) + f"\n[timeout after {timeout}s]")
    receipt(job, station, tool, argv, res.returncode, time.time() - t0, out,
            res.stderr if res.returncode else "", owner_media)
    if check and res.returncode != 0:
        raise RuntimeError(f"{tool} failed rc={res.returncode}: {res.stderr[-600:]}")
    return res


def receipts(job) -> list[dict]:
    f = Path(job) / "receipts.jsonl"
    return [json.loads(x) for x in f.read_text(encoding="utf-8").splitlines() if x.strip()] if f.exists() else []


def lookup(table: str, key):
    """Entry `key` (id or alias, `_` = `-`) in data/<table>: {list_key: [{id, aliases}]}."""
    if not key:
        return None
    doc = data(table)
    items = next((v for v in doc.values() if isinstance(v, list) and v and isinstance(v[0], dict)), [])
    k = str(key).strip().lower().replace("_", "-")
    for it in items:
        if str(it.get("id", "")).strip().lower().replace("_", "-") == k:
            return it
    for it in items:
        if k in {str(a).strip().lower().replace("_", "-") for a in it.get("aliases") or []}:
            return it
    return None


def make_test_clip(path: Path, seconds: float = 6.0, *, tone: int = 440, size: str = "1280x720",
                   color: str = "testsrc2") -> Path:
    """Synthetic clip for tests: moving pattern + tone, with a hard scene change half way."""
    half = seconds / 2
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([exe("ffmpeg"), "-y", "-v", "error",
                    "-f", "lavfi", "-i", f"{color}=size={size}:rate=30:duration={half}",
                    "-f", "lavfi", "-i", f"smptebars=size={size}:rate=30:duration={half}",
                    "-f", "lavfi", "-i", f"sine=frequency={tone}:duration={seconds}",
                    "-filter_complex", "[0:v][1:v]concat=n=2:v=1:a=0,format=yuv420p[v]",
                    "-map", "[v]", "-map", "2:a", "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac",
                    "-frames:v", str(round(seconds * 30)), "-af", fit_audio(seconds),  # exact length, no -shortest
                    str(path)], check=True, timeout=120)
    return path
