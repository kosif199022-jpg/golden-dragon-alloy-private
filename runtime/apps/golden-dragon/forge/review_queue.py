"""Rank repair candidates and generate a compact, source-linked human review queue."""
import argparse
import json
import re
from pathlib import Path

def rank(records):
    queue = []
    for record in records:
        original = record["original"]
        options = [p for p in record.get("proposals", []) if p["classification"] == "reviewable"]
        if not options:
            continue
        unique = {}
        for option in options:
            candidate = re.sub(r"\s+", " ", option["candidate"]).strip()
            key = candidate.casefold()
            entry = unique.setdefault(key, {"candidate": candidate, "sources": [], "line_numbers": []})
            source = option.get("source")
            if source and source not in entry["sources"]:
                entry["sources"].append(source)
            if option.get("line") is not None:
                entry["line_numbers"].append(option["line"])
        ranked = sorted(unique.values(), key=lambda e: (-len(e["sources"]), len(e["candidate"]), e["candidate"]))
        queue.append({"original": original, "choices": ranked,
                      "suggested": ranked[0], "decision": "pending_manual_review"})
    queue.sort(key=lambda e: (-len(e["suggested"]["sources"]), len(e["choices"]), e["original"]))
    return queue

def run(source, out):
    records = json.loads(Path(source).read_text(encoding="utf-8"))
    queue = rank(records)
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "repair_review_queue.json").write_text(json.dumps(queue, ensure_ascii=False, indent=2), encoding="utf-8")
    report = {"cases_ready_for_review": len(queue), "unique_options": sum(len(e["choices"]) for e in queue),
              "cases_with_multiple_options": sum(len(e["choices"]) > 1 for e in queue),
              "approved": 0, "automatically_applied": 0}
    (out / "repair_review_queue_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("validated_repairs")
    parser.add_argument("--output", required=True)
    a = parser.parse_args()
    print(json.dumps(run(a.validated_repairs, a.output)))
