"""Read-only bridge between the distilled knowledge preview and existing fusion router."""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from brain_query import search
from ranked_brain_query import search as ranked_search

HERE = Path(__file__).resolve().parent
DEFAULT_BRAIN = HERE / "data" / "unified-brain-preview" / "brain_quality_gated.json"
FUSION = HERE / "modules" / "dragon_fusion.py"
FUSION_DATA = HERE / "data" / "fusion"

def consult(query, brain=DEFAULT_BRAIN, include_route=True, limit=5, ranked=False):
    brain = Path(brain)
    if not brain.is_file():
        return {"query": query, "knowledge": [], "execution": "not attempted", "error": "Quality-gated brain missing; build quality gate or provide --brain"}
    result = {"query": query, "knowledge": (ranked_search if ranked else search)(brain, query, limit), "execution": "not attempted"}
    if include_route:
        if not (FUSION_DATA / "recipes.json").is_file() or not (FUSION_DATA / "index.json").is_file():
            result["fusion_route"] = {"error": "Fusion data missing; rebuild index before routing"}
            return result
        try:
            env = os.environ.copy()
            env["GOLDEN_FUSION_DATA"] = str(FUSION_DATA)
            env["PYTHONIOENCODING"] = "utf-8"
            completed = subprocess.run([sys.executable, str(FUSION), "route", query], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30, env=env)
            result["fusion_route"] = {"exit_code": completed.returncode, "output": completed.stdout[:12000], "error": completed.stderr[:2000]}
        except (OSError, subprocess.TimeoutExpired) as exc:
            result["fusion_route"] = {"error": str(exc)}
    return result

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("query")
    ap.add_argument("--brain", type=Path, default=DEFAULT_BRAIN)
    ap.add_argument("--no-route", action="store_true")
    ap.add_argument("--ranked", action="store_true", help="Use BM25 lexical relevance ranking")
    ap.add_argument("--limit", type=int, default=5)
    a = ap.parse_args()
    print(json.dumps(consult(a.query, a.brain, not a.no_route, max(1, min(100, a.limit)), a.ranked), ensure_ascii=False, indent=2))


