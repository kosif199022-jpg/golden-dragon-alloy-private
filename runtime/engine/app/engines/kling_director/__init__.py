"""Kling director: a Kling 4.0 short-film prompt pack from one story line, then the lint.

plan()   splits a film into blocks of 30 s or less (20 s with Flash): 60 s = 2 blocks, 90 s = 3.
build()  writes per block a master prompt in template H's 15-header order (block_NN.txt), a 3x3 storyboard prompt
         whose 9 panels follow the block's clock (storyboard_NN.txt) and plan.json (settings box, takes plan, lint).
         Shots are at most 6 s and their ranges touch end to end; the story goes into SCENE CONTEXT untouched.
Text only: never calls Kling, Higgsfield or Nano Banana and spends no credits. Templates live in data/templates.json."""
import json
import math
from pathlib import Path

from .lint import lint as lint_prompt, report, sections

TPL = json.loads((Path(__file__).resolve().parent / "data" / "templates.json").read_text(encoding="utf-8"))
RATIOS = tuple(TPL["ratios"])
PLANTED = {k: tuple(v) for k, v in TPL["planted"].items()}


def plan(seconds: int, flash: bool = False) -> list:
    """Even blocks of whole seconds, none longer than the model's limit (30 s, Flash 20 s)."""
    n = max(1, math.ceil(seconds / TPL["flash_block_max_s" if flash else "block_max_s"]))
    base, extra = divmod(seconds, n)
    out, t = [], 0
    for i in range(n):
        size = base + (1 if i < extra else 0)
        out.append((t, t + size))
        t += size
    return out


def cuts(duration: float, parts: int) -> list:
    """parts ranges from 0 to duration that touch end to end (one decimal)."""
    edges = [round(duration * i / parts, 1) for i in range(parts)] + [float(duration)]
    return list(zip(edges, edges[1:]))


def master_prompt(task: str, index: int, total: int, duration: int, ratio: str) -> str:
    shots = cuts(duration, max(1, math.ceil(duration / TPL["shot_max_s"])))
    f, m = TPL["framings"], TPL["moves"]
    timing = "\n".join(TPL["shot_line"].format(a=f"{a:.1f}", b=f"{b:.1f}", n=n, frame=f[(n - 1) % len(f)],
                                               move=m[(n - 1) % len(m)], end=TPL["shot_end"][n == len(shots)])
                       for n, (a, b) in enumerate(shots, 1))
    fields = dict(index=index, total=total, duration=duration, ratio=ratio, story=" ".join(task.split()),
                  shots=len(shots), timing=timing)
    return "\n".join(line.format(**fields) for line in TPL["master"])


def storyboard_prompt(task: str, index: int, duration: int, ratio: str) -> str:
    fields = dict(ratio=ratio, index=index, story=" ".join(task.split()))
    lines = [line.format(**fields) for line in TPL["storyboard"]]
    lines += [TPL["panel_line"].format(n=n, name=name, a=f"{a:.1f}", b=f"{b:.1f}")
              for n, (name, (a, b)) in enumerate(zip(TPL["panels"], cuts(duration, 9)), 1)]
    return "\n".join(lines) + "\n"


def summarize(results: list) -> dict:
    return {"result": "FAIL" if any(t["status"] == "FAIL" for t in results) else "PASS",
            "failed": [t["name"] for t in results if t["status"] == "FAIL"],
            "warnings": [t["name"] for t in results if t["status"] == "warn"], "tests": results}


def build(task: str, seconds: int, out, ratio: str = "9:16", flash: bool = False) -> dict:
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    blocks, rows, p = plan(seconds, flash), [], TPL["plan"]
    for i, (a, b) in enumerate(blocks, 1):
        dur = b - a
        text = master_prompt(task, i, len(blocks), dur, ratio)
        (out / f"block_{i:02d}.txt").write_text(text, encoding="utf-8")
        (out / f"storyboard_{i:02d}.txt").write_text(storyboard_prompt(task, i, dur, ratio), encoding="utf-8")
        rows.append({"block": i, "film_range_s": [a, b], "duration_s": dur, "prompt": f"block_{i:02d}.txt",
                     "storyboard": f"storyboard_{i:02d}.txt", "lint": summarize(lint_prompt(text, dur, flash))})
    s = p["settings"]
    doc = {"schema": p["schema"], "task": task, "seconds": seconds, "ratio": ratio,
           "model": p["flash_model"] if flash else p["model"], "blocks": rows,
           "settings": {"mode": s["mode"], "resolution": s["resolution"],
                        "flash_allowed": all(r["duration_s"] <= TPL["flash_block_max_s"] for r in rows),
                        "upload_order": s["upload_order"]},
           "takes_plan": p["takes_plan"], "continuity": p["continuity"], "credits_spent": 0,
           "result": "PASS" if all(r["lint"]["result"] == "PASS" for r in rows) else "FAIL"}
    (out / "plan.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return doc


def plant(text: str) -> str:
    """Four known mistakes: polish words, a camera brand, Arabic dialogue, and a gap in the clock."""
    for old, new in PLANTED.values():
        text = text.replace(old, new, 1)
    lines = text.splitlines()
    for k, line in enumerate(lines):  # move SHOT 2's start 0.5 s later: a gap after SHOT 1
        if "SHOT 2 —" in line:
            a, rest = line.split("-", 1)
            lines[k] = f"{float(a) + 0.5:.1f}-{rest}"
            break
    return "\n".join(lines) + "\n"


def self_test(tmp) -> list:
    """Known-answer checks: [(name, ok)]."""
    tmp = Path(tmp)
    def even(s, b):
        sizes = [y - x for x, y in b]
        return (b[0][0] == 0 and b[-1][1] == s and all(p[1] == q[0] for p, q in zip(b, b[1:]))
                and max(sizes) <= TPL["block_max_s"] and max(sizes) - min(sizes) <= 1)
    checks = [(f"plan {s} s: even blocks of 30 s or less that touch", even(s, plan(s))) for s in (3, 29, 30, 31, 45, 60, 90, 100)]
    checks.append(("90 s = 3 blocks of 30 s", plan(90) == [(0, 30), (30, 60), (60, 90)]))
    checks.append(("Flash 45 s = 3 blocks of at most 20 s", plan(45, True) == [(0, 15), (15, 30), (30, 45)]))
    doc = build("A courier races the rain to deliver one last letter.", 60, tmp)
    checks.append(("60 s builds 2 blocks of 30 s", [r["film_range_s"] for r in doc["blocks"]] == [[0, 30], [30, 60]]))
    checks.append(("every built block passes the lint", doc["result"] == "PASS"))
    bad = summarize(lint_prompt(plant((tmp / "block_01.txt").read_text(encoding="utf-8")), 30))
    checks.append(("all 4 planted flaws caught", set(PLANTED) <= set(bad["failed"])))
    loud = build("Perfect 8K hero shot on an ARRI camera.", 10, tmp / "loud")
    checks.append(("polish and brand words in the story are reported",
                   {"polish", "brands"} <= set(loud["blocks"][0]["lint"]["failed"])))
    return checks
