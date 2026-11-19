"""Conservative quality gate: quarantine flagged instructions and preserve source context."""
import argparse
import json
from pathlib import Path

def build(brain_file, review_file, output):
    brain = json.loads(Path(brain_file).read_text(encoding="utf-8"))
    review = json.loads(Path(review_file).read_text(encoding="utf-8"))
    by_text = {x["text"]: x for x in review}
    safe = []
    flagged = []
    for item in brain["instructions"]:
        context = by_text.get(item["text"])
        if context:
            flagged.append({"instruction": item, "quality_review": context})
        else:
            safe.append(item)
    prior = brain.get("requires_review", [])
    result = {"instructions": safe, "quality_quarantine": flagged,
              "requires_review": prior, "status": "knowledge preview; not executable"}
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    (output / "brain_quality_gated.json").write_text(
        json.dumps(result, ensure_ascii=False), encoding="utf-8")
    report = {"original_active": len(brain["instructions"]),
              "active_after_gate": len(safe), "quality_quarantined": len(flagged),
              "conflict_quarantined": len(prior), "auto_rewritten": 0,
              "preserved_total": len(safe) + len(flagged) + len(prior)}
    (output / "quality_gate_report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8")
    return report

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("brain")
    ap.add_argument("context_review")
    ap.add_argument("--output", required=True)
    a = ap.parse_args()
    print(json.dumps(build(a.brain, a.context_review, a.output)))
