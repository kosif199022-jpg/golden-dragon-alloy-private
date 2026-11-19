"""Does the skill's fusion overlay steal requests from the base recipes?
For every base recipe, each of its `when` examples is routed; top-1 must be the recipe itself.
Run from the repo root: python -X utf8 overlay_eval.py REPO
"""
import sys
from pathlib import Path

repo = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(repo / "scripts"))
sys.argv = ["rd.py"]
import rd          # noqa: E402
import rd_fusion   # noqa: E402

RD = rd.rd_self()


def measure(use_overlay):
    rd_fusion._df = None
    rd_fusion.OVERLAY = (repo / "mind" / "fusion_overlay.json") if use_overlay else (repo / "mind" / "_none_.json")
    df = rd_fusion.load(RD)
    base = [r for r in df.recipes() if r["id"] != "skill-self-develop"]
    hit, total, moved = 0, 0, []
    for r in base:
        for q in r["when"]:
            res = df.route(q)
            got = res["recipes"][0][1]["id"] if res["recipes"] else "none"
            total += 1
            if got == r["id"]:
                hit += 1
            elif got == "skill-self-develop":
                moved.append((r["id"], q))
    return hit, total, moved


h0, t0, _ = measure(False)
h1, t1, moved = measure(True)
print(f"base recipes, own examples top-1: without overlay {h0}/{t0}  with overlay {h1}/{t1}")
print("examples pulled to skill-self-develop:", moved or "none")
