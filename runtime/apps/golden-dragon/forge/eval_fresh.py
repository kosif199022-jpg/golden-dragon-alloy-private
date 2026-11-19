"""eval_fresh.py — measures the Golden Dragon router on the owner's REAL requests, labelled blind by two annotators.

Data (read-only): ~/.claude/skills/golden-dragon/mind/route_eval/fresh_cc.json (226 owner messages from local Claude Code
sessions) + labels_fresh_consensus.json (best playbook + acceptable ones, 38 Red Dragon playbooks). The labels name Red
Dragon playbooks, so MAP below translates each playbook to the Golden Dragon recipes that serve it. MAP was written
BEFORE the first run; a playbook with no recipe is a GAP and stays in the coverage number. Split like the Red Dragon:
dev = even id (tune on it), test = odd id (report it, measured once after tuning).

  python -X utf8 eval_fresh.py [--split dev|test|all] [--misses N]
"""
import importlib.util
import json
import os
import re
import sys
from pathlib import Path

FORGE = Path(__file__).resolve().parent
EVAL = Path.home() / ".claude" / "skills" / "golden-dragon" / "mind" / "route_eval"
GB_APP = FORGE.parent.parent / "الطائر الذهبي" / "app"           # golden_tools: Arabic tokens + synonyms
NONE = "NONE"                                                    # "where is my file?" / chit-chat: the right answer is no recipe
MAP = {
    "reel-montage": {"reel-footage-song", "talking-head-reel"}, "lyric-quran": {"arabic-captions", "reel-footage-song"},
    "motion-code": {"motion-html-film", "logo-intro", "data-chart"}, "machine-sim": {"machine-teardown"},
    "image-identity": {"image-design"}, "blender-3d": {"blender-3d-shot"}, "toon": {"cartoon-look"},
    "voice": {"voice-over", "arabic-captions", "song-music"}, "download": {"download-media"},
    "trend": {"social-analytics", "instagram", "youtube"}, "re-file": {"reverse-engineer"},
    "re-site": {"reverse-engineer", "web-app"}, "re-repo": {"reverse-engineer", "new-skill"}, "re-apk": {"reverse-android"},
    "audit-install": {"reverse-engineer"}, "build-skill": {"new-skill"}, "pc-task": {"pc-browser-control"},
    "chrome-task": {"pc-browser-control"}, "cloud-render": {"heavy-cloud"}, "paid-gen": set(), "docs-office": {"office-docs"},
    "web-build": {"web-app"}, "deep-research": set(), "app-dev": {"app-self-develop"}, "ship": {"app-self-develop"},
    "design-static": {"image-design"}, "think-hard": {"hard-decision"}, "self-improve": {"app-self-develop", "new-skill"},
    "reconcile": set(), "excel-pro": {"office-docs"}, "app-to-skill": {"new-skill"}, "site-style": {"web-app", "image-design"},
    "clone-own-tool": {"web-app", "app-self-develop"}, "status": NONE, "nature-palette": {"image-design"},
    "shadow-puppet": set(), "draw-math": {"math-explainer"}, "character-memory": set(), "none": NONE,
}
# Recipes added AFTER the first dev run (2026-11-15: dev top1 0.229, ok 0.325, top3 0.554, coverage 0.847), declared here
# so the change of the denominator is visible. The test half had not been run yet.
EXTRA = {"reconcile": {"reconcile-statements"}, "excel-pro": {"reconcile-statements"}, "re-repo": {"github-repos"},
         "clone-own-tool": {"own-tool-build"}, "ship": {"ship-package"}, "think-hard": {"prompt-writing"},
         "deep-research": {"deep-research"}, "shadow-puppet": {"shadow-theatre-film"}, "paid-gen": {"paid-generation"},
         "status": {"status-check"}, "lyric-quran": {"lyrics-film"}}
# tuning v3 (dev only): «ابحث عن 500 موقع فيه فيديوهات وصور» is labelled deep-research; the media-hunt recipe serves it
EXTRA["deep-research"] = EXTRA["deep-research"] | {"media-hunt"}


def load_router():
    sys.path.insert(0, str(GB_APP))
    os.environ.setdefault("GOLDEN_FUSION_DATA", str(FORGE / "data" / "fusion"))
    spec = importlib.util.spec_from_file_location("dragon_fusion", FORGE / "modules" / "dragon_fusion.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def clean(q):
    """Drop the blocks the app prepends ([فريق الوكلاء…], [تحديث من كل المحادثات…], [مجلد الشغل…]) and keep the owner's words."""
    q = q.strip()
    while q.startswith("["):
        depth, i = 0, 0
        for i, ch in enumerate(q):
            depth += ch == "["
            depth -= ch == "]"
            if depth == 0:
                break
        q = q[i + 1:].strip()
    return " ".join(q.split())


def rows_old(split):
    """The 101 requests from the app archive (owner_requests.json + labels_1..4.json, labelled blind WITHOUT the previous
    message). Never used for tuning the Golden Dragon router, so the whole set is unseen."""
    reqs = {r["id"]: r["q"] for r in json.loads((EVAL / "owner_requests.json").read_text(encoding="utf-8"))}
    out = []
    for k in range(1, 5):
        for x in json.loads((EVAL / f"labels_{k}.json").read_text(encoding="utf-8")):
            i = x["id"]
            if x.get("best") in (None, "skip") or (split == "dev" and i % 2) or (split == "test" and not i % 2):
                continue
            q = clean(reqs[i])
            if q:
                out.append({"id": i, "q": q, "best": x["best"], "ok": [o for o in x.get("ok", []) if o != "skip"]})
    return out


def rows(split, which="fresh"):
    if which == "old":
        return rows_old(split)
    reqs = {r.get("id", i): r for i, r in enumerate(json.loads((EVAL / "fresh_cc.json").read_text(encoding="utf-8")))}
    out = []
    for x in json.loads((EVAL / "labels_fresh_consensus.json").read_text(encoding="utf-8")):
        if x.get("best") in (None, "skip"):
            continue
        fid = x["fid"]
        if (split == "dev" and fid % 2) or (split == "test" and not fid % 2):
            continue
        q = clean(reqs[fid]["q"])
        if q:
            out.append({"id": fid, "q": q, "best": x["best"], "ok": [o for o in x.get("ok", []) if o != "skip"]})
    return out


def mapped(pb):
    m = MAP.get(pb, set())
    if m == NONE:
        return set(EXTRA[pb]) if pb in EXTRA else NONE
    return set(m) | EXTRA.get(pb, set())


def load_bridge():
    spec = importlib.util.spec_from_file_location("rd_bridge", FORGE / "modules" / "rd_bridge.py")
    b = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(b)
    return b


def hide_everything(bridge):
    """Hide every request of both sets (raw and cleaned) from the Red Dragon's example memory: no row is ever graded
    with itself (or its twin) in the memory, whichever split is measured."""
    texts = [r["q"] for r in json.loads((EVAL / "fresh_cc.json").read_text(encoding="utf-8"))]
    texts += [r["q"] for r in json.loads((EVAL / "owner_requests.json").read_text(encoding="utf-8"))]
    keys = set(bridge.keys_for(texts)) | set(bridge.keys_for([clean(x) for x in texts]))
    bridge.load().EX_EXCLUDE.update(keys)
    return len(keys)


def evaluate(f, rs, infos=None):
    cov = top1 = ok = top3 = abst_n = abst_ok = 0
    gaps, misses = {}, []
    for r in rs:
        best = mapped(r["best"])
        res = f.route(r["q"], rd=(infos or {}).get(r["q"]))
        chosen = [rec["id"] for _, rec in res["recipes"]]
        ranked = [rid for _, rid in res["ranked"]]
        top = chosen[0] if chosen else None
        if best == NONE:
            abst_n += 1
            abst_ok += top is None
            continue
        if not best:
            gaps[r["best"]] = gaps.get(r["best"], 0) + 1
            continue
        cov += 1
        okset = set(best)
        for o in r["ok"]:
            m = mapped(o)
            if m != NONE:
                okset |= m
        top1 += top in best
        ok += top in okset
        top3 += any(rid in okset for rid in ranked[:3])
        if top not in okset:
            misses.append((r["id"], r["best"], top, r["q"][:110]))
    n = len(rs)
    return {"n": n, "covered": cov, "coverage": round(cov / max(1, n - abst_n), 3), "top1": round(top1 / max(1, cov), 3),
            "ok": round(ok / max(1, cov), 3), "top3": round(top3 / max(1, cov), 3), "abstain": f"{abst_ok}/{abst_n}",
            "gaps": dict(sorted(gaps.items(), key=lambda kv: -kv[1]))}, misses


def main(argv):
    split = argv[argv.index("--split") + 1] if "--split" in argv else "dev"
    which = argv[argv.index("--set") + 1] if "--set" in argv else "fresh"
    show = int(argv[argv.index("--misses") + 1]) if "--misses" in argv else 0
    hybrid, tune = "--hybrid" in argv or "--tune" in argv, "--tune" in argv
    f = load_router()
    rs = rows(split, which)
    infos = None
    if hybrid:
        bridge = load_bridge()
        hidden = hide_everything(bridge)
        infos = {r["q"]: bridge.route_info(r["q"]) for r in rs}
        print(f"(red dragon {next(iter(infos.values()))['version'] if infos else '?'}: {hidden} example keys hidden)")
    if tune:
        best = None
        for w in (0.5, 1.0, 1.5, 2.0, 3.0):
            for b0 in (5.0, 10.0, 20.0):
                for pick in (0.2, 0.3, 0.45):
                    f.W_RD, f.B0, f.PICK = w, b0, pick
                    res, _ = evaluate(f, rs, infos)
                    key = (res["top1"], res["top3"], res["ok"])
                    print(f"W_RD={w} B0={b0} PICK={pick}: top1 {res['top1']} ok {res['ok']} top3 {res['top3']} abstain {res['abstain']}")
                    if best is None or key > best[0]:
                        best = (key, w, b0, pick)
        print(f"BEST on {which}/{split}: W_RD={best[1]} B0={best[2]} PICK={best[3]} -> top1/top3/ok {best[0]}")
        return 0
    res, misses = evaluate(f, rs, infos)
    res = {"set": which, "split": split, "hybrid": hybrid, **res}
    print(json.dumps(res, ensure_ascii=False))
    for m in misses[:show]:
        print(f"  ✗ #{m[0]} want {m[1]} got {m[2]}: {m[3]}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
