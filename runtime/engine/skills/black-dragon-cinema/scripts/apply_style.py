"""Apply the saas-animation style rules to a film spec in place:
no cross-dissolves or light-leak packs (iris shape-morph instead), push-in only, text inside the reels safe zone."""
import json, os, sys
from pathlib import Path

for name in sys.argv[1:]:
    p = Path(os.environ.get("BDC_WORK", r"C:\Users\cinde\bdc_work")) / "films" / f"{name}.json"
    s = json.loads(p.read_text(encoding="utf-8"))
    for i, sh in enumerate(s["shots"]):
        tr = sh.get("tr")
        if tr and tr["type"] in ("dissolve", "leak"):
            tr["type"] = "iris"; tr["d"] = max(tr["d"], 0.6)
        kb = sh.get("kb")
        if kb and kb.get("s0", 1) > kb.get("s1", 1.06):  # direction never reverses: always push in
            kb["s0"], kb["s1"] = kb["s1"], kb["s0"]
    s["leaks"] = []
    for tx in s["texts"]:
        if tx.get("y", 0.5) > 0.74:          # bottom ~25% is covered by TikTok / Reels UI
            tx["y"] = 0.72 if tx.get("y") < 0.83 else 0.7
        if tx.get("glow") and not tx.get("gold"):
            tx.pop("glow")                   # no glow on everything
    p.write_text(json.dumps(s, ensure_ascii=False, indent=1), encoding="utf-8")
    print("styled", name)
