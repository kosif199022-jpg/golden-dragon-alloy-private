"""W11 routing evaluation for Red Rose.

Usage (from the skill folder or any folder):
    python -X utf8 evals/routing/run_eval.py --split dev|test [--json]
    python -X utf8 evals/routing/run_eval.py --split test --record [--force]

dev  = even request ids (tuning split).
test = odd request ids. `--record` is the single measurement run: it writes
FREEZE.json (sha256 of the requests, labels, decoder cases and every code file
that produces the result) BEFORE measuring, then writes REPORT.json and, when
floor.json is missing, creates it. A second test record for the same hash is
refused unless --force (the forced run is counted in FREEZE.json).

Labels: `best` is the gold adapter id, `ok` lists acceptable adapter ids. The
router returns a recipe or an op; both are mapped to an adapter id from
label_space.txt (recipe -> its first step op -> longest known prefix).
"""
import argparse
import datetime
import glob
import hashlib
import json
import math
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent.parent
sys.path.insert(0, str(SKILL))
import rose_agent as A  # noqa: E402

REQUESTS = HERE / "requests.jsonl"
LABELS_B = HERE / "labels_b.jsonl"
LABEL_SPACE = HERE / "label_space.txt"
FREEZE = HERE / "FREEZE.json"
REPORT = HERE / "REPORT.json"
FLOOR = HERE / "floor.json"
DECODER = HERE.parent / "decoder" / "cases.jsonl"
ABSTAIN_TIER_MIN = 0.8
ABSTAIN_PRECISION_MIN = 0.8
LABELLER_AGREEMENT = {
    "value": 1.0,
    "source": "frozen-set workflow stats: agreed_directly 160 of 160 (recorded, not re-measured by run_eval)",
}


def _read_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def _labels():
    with open(LABEL_SPACE, encoding="utf-8") as f:
        return {line.strip() for line in f if line.strip()}


KNOWN = None


def label_of(route_id, route_type):
    """Map a router result (recipe or op id) to a gold adapter id, or 'none'."""
    global KNOWN
    if KNOWN is None:
        KNOWN = _labels()
    if route_type == "none" or not route_id:
        return "none"
    if route_type == "recipe":
        steps = json.loads((SKILL / "recipes" / f"{route_id}.json").read_text(encoding="utf-8")).get("steps", [])
        route_id = steps[0].get("op", "") if steps else route_id
    cand = route_id
    while cand and cand not in KNOWN:
        if "." not in cand:
            return cand
        cand = cand.rsplit(".", 1)[0]
    return cand or "none"


def code_files():
    files = [HERE / "run_eval.py", HERE / "label_space.txt"]
    for name in ("rose_agent.py", "rose_io.py", "rose_recipes.py", "rose_catalog.py", "rose_run.py", "rose_env.py"):
        files.append(SKILL / name)
    files += [Path(p) for p in sorted(glob.glob(str(SKILL / "agent" / "*.json")))]
    files += [Path(p) for p in sorted(glob.glob(str(SKILL / "agent" / "*.txt")))]
    files += [Path(p) for p in sorted(glob.glob(str(SKILL / "recipes" / "*.json")))]
    files.append(SKILL / "references" / "OPS_CATALOG.json")
    return files


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def hashes():
    data_files = {"requests.jsonl": REQUESTS, "labels_b.jsonl": LABELS_B, "decoder/cases.jsonl": DECODER}
    out = {"data": {k: _sha(v) for k, v in data_files.items()}, "code": {}}
    for p in code_files():
        out["code"][p.relative_to(SKILL).as_posix()] = _sha(p)
    blob = json.dumps({"data": out["data"], "code": out["code"]}, sort_keys=True).encode("utf-8")
    out["total_sha256"] = hashlib.sha256(blob).hexdigest()
    return out


def _split(rows, split):
    if split == "dev":
        return [r for r in rows if r["id"] % 2 == 0]
    if split == "test":
        return [r for r in rows if r["id"] % 2 == 1]
    return rows


def _p95(values):
    if not values:
        return None
    s = sorted(values)
    return round(s[max(0, math.ceil(0.95 * len(s)) - 1)], 3)


def _frac(num, den):
    return round(num / den, 4) if den else None


def evaluate(split):
    rows = _split(_read_jsonl(REQUESTS), split)
    recs, route_ms = [], []
    for r in rows:
        t0 = time.perf_counter()
        res = A.route(r["request"], r.get("prev"))
        route_ms.append((time.perf_counter() - t0) * 1000)
        pred = label_of(res.get("id"), res.get("type"))
        top3 = [label_of(c["id"], c["type"]) for c in res.get("candidates", [])[:3]]
        best, ok = r["best"], set(r.get("ok") or [])
        is_none = best == "none"
        if is_none:
            top1 = pred == "none"
            acc = pred == "none"
            t3 = pred == "none"
        else:
            top1 = pred == best
            acc = pred == best or pred in ok
            t3 = best in top3 or top1
        recs.append({"id": r["id"], "style": r["style"], "tags": r["tags"], "best": best,
                     "pred": pred, "is_none": is_none, "top1": top1, "acceptable": acc, "top3": t3,
                     "pred_none": pred == "none", "correct_abstain": is_none and pred == "none"})
    return recs, route_ms


def _summarise(recs):
    n = len(recs)
    none_rows = [x for x in recs if x["is_none"]]
    pred_none = [x for x in recs if x["pred_none"]]
    correct_ab = sum(1 for x in recs if x["correct_abstain"])
    by_style, by_tag = {}, {}
    for x in recs:
        for key, bucket in ((x["style"], by_style),):
            b = bucket.setdefault(key, {"n": 0, "top1": 0, "acceptable": 0, "top3": 0})
            b["n"] += 1
            b["top1"] += x["top1"]
            b["acceptable"] += x["acceptable"]
            b["top3"] += x["top3"]
        for tag in x["tags"]:
            b = by_tag.setdefault(tag, {"n": 0, "top1": 0, "acceptable": 0, "top3": 0})
            b["n"] += 1
            b["top1"] += x["top1"]
            b["acceptable"] += x["acceptable"]
            b["top3"] += x["top3"]
    for bucket in (by_style, by_tag):
        for b in bucket.values():
            b["top1"] = _frac(b["top1"], b["n"])
            b["acceptable"] = _frac(b["acceptable"], b["n"])
            b["top3"] = _frac(b["top3"], b["n"])
    return {
        "n": n,
        "top1": _frac(sum(x["top1"] for x in recs), n),
        "acceptable": _frac(sum(x["acceptable"] for x in recs), n),
        "top3": _frac(sum(x["top3"] for x in recs), n),
        "abstention": {"none_rows": len(none_rows), "correct_abstentions": correct_ab,
                       "precision": _frac(correct_ab, len(pred_none)),
                       "recall": _frac(correct_ab, len(none_rows))},
        "by_style": by_style,
        "by_tag": by_tag,
    }


def decoder_eval():
    cases = _read_jsonl(DECODER)
    exact = fp_english = 0
    counts = {"layout": 0, "english": 0, "arabic": 0}
    layout_exact = 0
    for c in cases:
        dec = A.understand(c["in"])["text"]
        counts[c["kind"]] += 1
        ok = dec == c["out"]
        exact += ok
        if c["kind"] == "layout":
            layout_exact += ok
        if c["kind"] == "english" and dec != c["in"]:
            fp_english += 1
    return {"n": len(cases), "exact": exact, "false_positives_on_english": fp_english,
            "by_kind": counts, "layout_exact": layout_exact}


def measure(split):
    dev_recs, _ = evaluate("dev")
    recs, route_ms = evaluate(split)
    summary = _summarise(recs)
    return {"split": split, "summary": summary, "dev_summary": _summarise(dev_recs),
            "route_p95_ms": _p95(route_ms), "decoder": decoder_eval(),
            "labeller_agreement": LABELLER_AGREEMENT,
            "baseline": {"capability_plan_top3_on_same_rows": "not measured"}}


def _floor_from(value):
    return math.floor(value * 1000) / 1000


def record(split, force):
    if split != "test":
        raise SystemExit("--record is only for the test split")
    h = hashes()
    prev = json.loads(FREEZE.read_text(encoding="utf-8-sig")) if FREEZE.exists() else None
    # runs counts every test measurement of this split across code changes, not per hash
    runs = prev.get("runs", 1) + 1 if prev else 1
    same_hash = bool(prev) and prev.get("total_sha256") == h["total_sha256"]
    if same_hash and not force:
        raise SystemExit("refused: test split already measured for this hash (use --force; recorded)")
    freeze = {"split": "test", "runs": runs, "forced": bool(force and same_hash),
              "frozen_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
              "total_sha256": h["total_sha256"], "data_sha256": h["data"], "code_sha256": h["code"]}
    FREEZE.write_text(json.dumps(freeze, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    result = measure("test")
    recall = result["summary"]["abstention"]["recall"]
    precision = result["summary"]["abstention"]["precision"]
    # "measured" needs abstention recall AND precision; recall alone (the W11 rule) is not enough
    tier = ("measured" if recall is not None and recall >= ABSTAIN_TIER_MIN
            and precision is not None and precision >= ABSTAIN_PRECISION_MIN else "unmeasured")
    report = {"freeze_total_sha256": h["total_sha256"], "runs": runs, "tier": tier,
              "abstain_recall_min": ABSTAIN_TIER_MIN, "abstain_precision_min": ABSTAIN_PRECISION_MIN,
              "routing": {"dev": {k: result["dev_summary"][k] for k in ("n", "top1", "acceptable", "top3")},
                          "test": {k: result["summary"][k] for k in ("n", "top1", "acceptable", "top3")}},
              "abstention": {"test": result["summary"]["abstention"],
                             "dev": result["dev_summary"]["abstention"]},
              "per_style": {"test": result["summary"]["by_style"], "dev": result["dev_summary"]["by_style"]},
              "per_tag": {"test": result["summary"]["by_tag"]},
              "decoder": result["decoder"], "route_p95_ms": result["route_p95_ms"],
              "labeller_agreement": LABELLER_AGREEMENT, "baseline": result["baseline"]}
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if not FLOOR.exists():
        t = result["summary"]
        floor = {"top1": _floor_from(t["top1"]), "top3": _floor_from(t["top3"]),
                 "abstention_recall": _floor_from(recall or 0.0),
                 "history": [{"run": runs, "split": "test", "top1": t["top1"], "top3": t["top3"],
                              "abstention_recall": recall, "freeze_total_sha256": h["total_sha256"]}]}
        FLOOR.write_text(json.dumps(floor, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", choices=["dev", "test"], required=True)
    ap.add_argument("--record", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    if args.record:
        out = record(args.split, args.force)
    else:
        out = measure(args.split)
    if args.json:
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        s = out["summary"] if "summary" in out else out["routing"][args.split]
        print(json.dumps(s, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
