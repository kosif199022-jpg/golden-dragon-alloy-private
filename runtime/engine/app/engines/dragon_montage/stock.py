"""Station «مكتبة اللقطات المفتوحة»: search open-licence footage sites and bring licensed clips into the job.

Runs only when the owner asks (`edit … --stock "<english query>"`). It drives a free-footage client
(KOSIF free_footage.py: Pexels, Pixabay, Mixkit, Coverr, Commons, Internet Archive, NASA …) bundled in the
skill's tools/stock/ (the launcher passes it as $DRAGON_FREE_FOOTAGE), so every clip keeps a licence sidecar and ATTRIBUTION.md. Free sites only; nothing is bought.

  search --job DIR --query "coffee pouring" [--limit 4] [--commercial] [--orientation portrait]
  fetch  --job DIR [--top 3 | --ids mixkit:41865,coverr:abc] [--quality 1080] [--max-mb 200]
  sources [--find WORD]
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from . import common as C

STATION = "stock"
SCHEMA = "kosif.dm.stock.v1"
VIDEO_EXT = {".mp4", ".mov", ".webm", ".m4v", ".mkv"}


def client() -> Path:
    """$DRAGON_FREE_FOOTAGE only: scripts/dragon.py sets it to the skill's bundled tools/stock/free_footage.py.
    No path guessing here, so a run without it never reaches the network by surprise."""
    p = Path(os.environ.get("DRAGON_FREE_FOOTAGE", ""))
    if not os.environ.get("DRAGON_FREE_FOOTAGE") or not p.is_file():
        raise SystemExit("stock: DRAGON_FREE_FOOTAGE is not set to a free_footage.py client: run through "
                         "scripts/dragon.py (it sets it to the bundled tools/stock/free_footage.py) or set it yourself")
    return p


def orientation_for(job: Path):
    return {"9:16": "portrait", "4:5": "portrait", "16:9": "landscape"}.get((C.read_opt(job, "brief") or {}).get("aspect"))


def rank(r: dict) -> tuple:
    lic = r.get("licence") or {}
    return (not lic.get("verified"), lic.get("commercial") is not True, bool(lic.get("attribution_required")),
            "suspicious-licence" in (r.get("flags") or []), -((r.get("width") or 0) * (r.get("height") or 0)))


PLACES = ("riyadh", "mecca", "makkah", "jeddah", "cairo", "giza", "alexandria", "egypt", "saudi", "dubai", "luxor", "aswan",
          "nile", "sinai", "doha", "qatar", "kuwait", "oman", "jordan", "amman", "beirut", "paris", "london", "istanbul")


def has_place(query: str) -> bool:
    """A place name in the query (a known place or a Capitalised word): every word must match, or the Mecca clock tower
    ends up in a Riyadh film."""
    words = (query or "").split()
    return any(w.lower().strip(",.") in PLACES for w in words) or any(w[:1].isupper() for w in words[1:] + words[:1])


def match_mode(query: str) -> str:
    return "all" if has_place(query) else "any"


def search(job, query: str, limit: int = 4, commercial: bool = False, orientation=None) -> dict:
    job = C.job_dir(job)
    argv = [sys.executable, client(), "search", query, "--limit", str(limit), "--match", match_mode(query)]
    orient = orientation or orientation_for(job)
    argv += (["--orientation", orient] if orient else []) + (["--commercial"] if commercial else [])
    res = C.run(job, STATION, "free_footage.search", argv, timeout=600, owner_media=False, check=False, cwd=job)
    found = job / "out" / "free-footage" / "last_search.json"
    data = json.loads(found.read_text(encoding="utf-8")) if found.exists() else {"results": []}
    out = {"schema": SCHEMA, "query": query, "orientation": orient, "commercial_only": commercial,
           "results": sorted(data.get("results", []), key=rank), "searched": data.get("searches") or data.get("sources"),
           "warnings": data.get("warnings", []), "downloaded": [], "rc": res.returncode,
           "note": "licences are what each site declares; the tool records them, it does not grant them"}
    C.save(job / "stock.json", out)
    return out


def fetch(job, top: int = 0, ids: str = "", quality: int = 1080, max_mb: int = 200) -> list:
    """Downloads only the ids the owner (or you, after looking at the results) picked. `top` is kept for old callers
    and must be asked for explicitly; the pipeline never passes it (v1.3: no blind top-N)."""
    job = C.job_dir(job)
    stock = json.loads((job / "stock.json").read_text(encoding="utf-8"))
    pick = [i for i in (ids or "").split(",") if i] or [r["id"] for r in stock["results"][:max(0, int(top or 0))]]
    if not pick:
        return []
    dest = job / "stock"
    dest.mkdir(exist_ok=True)
    before = {p.name for p in dest.iterdir()}
    C.run(job, STATION, "free_footage.download", [sys.executable, client(), "download", *pick, "--out", dest, "--quality",
          str(quality), "--max-mb", str(max_mb)], timeout=1800, owner_media=False, check=False, cwd=job)
    got = []
    for p in sorted(p for p in dest.iterdir() if p.suffix.lower() in VIDEO_EXT and p.name not in before):
        side = next((s for s in (p.with_name(p.name + ".json"), p.with_suffix(".json")) if s.exists()), None)
        meta = json.loads(side.read_text(encoding="utf-8")) if side else {}
        got.append({"path": str(p), "id": meta.get("id") or (meta.get("result") or {}).get("id"),  # sidecar v1: result.id
                     "licence": meta.get("licence"), "attribution": meta.get("attribution")})
    stock["downloaded"] += got
    stock["attribution_file"] = "stock/ATTRIBUTION.md" if (dest / "ATTRIBUTION.md").exists() else None
    C.save(job / "stock.json", stock)
    return got


def main(argv=None) -> int:
    C.utf8_stdio()
    p = argparse.ArgumentParser(prog="dragon_montage stock", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("search")
    s.add_argument("--job", required=True)
    s.add_argument("--query", required=True)
    s.add_argument("--limit", type=int, default=4)
    s.add_argument("--orientation", choices=("portrait", "landscape"))
    s.add_argument("--commercial", action="store_true")
    f = sub.add_parser("fetch")
    f.add_argument("--job", required=True)
    f.add_argument("--top", type=int, default=0, help="take the first N results blindly (not recommended: use --ids)")
    f.add_argument("--ids")
    f.add_argument("--quality", type=int, default=1080)
    f.add_argument("--max-mb", type=int, default=200)
    sub.add_parser("sources").add_argument("--find")
    a = p.parse_args(argv)
    if a.cmd == "sources":
        return subprocess.call([sys.executable, str(client()), "sources"] + (["--find", a.find] if a.find else []))
    if a.cmd == "search":
        out = search(a.job, a.query, a.limit, a.commercial, a.orientation)
        print(json.dumps({"results": len(out["results"]), "top": [r["id"] for r in out["results"][:5]]}, ensure_ascii=False))
        return 0 if out["results"] or out["rc"] == 0 else 1
    if not a.ids and not a.top:
        raise SystemExit("stock fetch: pass --ids site:id,... after looking at stock.json (thumbs/titles) — no blind top-N")
    print(json.dumps({"downloaded": [g["path"] for g in fetch(a.job, a.top, a.ids, a.quality, a.max_mb)]}, ensure_ascii=False))
    return 0
