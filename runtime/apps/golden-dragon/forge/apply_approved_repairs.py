"""Apply explicitly approved repair choices to a NEW brain preview; never edit original data."""
import argparse
import json
from pathlib import Path

def apply(brain, queue, decisions):
    choices = {item["original"]: {v["candidate"] for v in item["choices"]} for item in queue}
    approvals = {}
    for item in decisions:
        original, candidate = item["original"], item["approved_candidate"]
        if original in approvals:
            raise ValueError("Duplicate decision for instruction")
        if original not in choices or candidate not in choices[original]:
            raise ValueError("Decision is not a validated review-queue choice")
        approvals[original] = candidate
    all_active = brain.get("instructions", [])
    quarantined = brain.get("quality_quarantine", [])
    originals = [x["instruction"]["text"] for x in quarantined]
    if len(originals) != len(set(originals)):
        raise ValueError("Ambiguous duplicate quarantine text")
    if any(original not in originals for original in approvals):
        raise ValueError("Approval does not match a quality-quarantined instruction")
    repaired = []
    remaining = []
    for entry in quarantined:
        item = entry["instruction"]
        if item["text"] in approvals:
            replacement = {**item, "text": approvals[item["text"]],
                           "repair_provenance": {"original": item["text"],
                                                 "approved_from_review_queue": True}}
            repaired.append(replacement)
        else:
            remaining.append(entry)
    return {"instructions": all_active + repaired, "quality_quarantine": remaining,
            "requires_review": brain.get("requires_review", []),
            "status": "approved repair preview; no executable adapters"}, len(repaired)

def run(brain_file, queue_file, approvals_file, output):
    brain = json.loads(Path(brain_file).read_text(encoding="utf-8"))
    queue = json.loads(Path(queue_file).read_text(encoding="utf-8"))
    decisions = json.loads(Path(approvals_file).read_text(encoding="utf-8-sig"))
    if not isinstance(decisions, list):
        raise ValueError("Approvals must be a JSON list")
    updated, count = apply(brain, queue, decisions)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    (output / "brain_approved_preview.json").write_text(
        json.dumps(updated, ensure_ascii=False, indent=2), encoding="utf-8")
    report = {"approved_applied": count, "active": len(updated["instructions"]),
              "quality_quarantined": len(updated["quality_quarantine"]),
              "conflict_quarantined": len(updated["requires_review"])}
    (output / "approved_repairs_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("quality_gated_brain")
    p.add_argument("review_queue")
    p.add_argument("approvals")
    p.add_argument("--output", required=True)
    a = p.parse_args()
    print(json.dumps(run(a.quality_gated_brain, a.review_queue, a.approvals, a.output)))

