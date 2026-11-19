"""Validate proposed repairs and produce a review queue; never auto-apply."""
import argparse
import collections
import json
import re
from pathlib import Path

BAD = re.compile(r"(?:```|<script|</script>|\b(?:api[_-]?key|password|secret|token)\s*[:=])", re.I)
BOUNDARY = re.compile(r"^\s*(?:#|[-*] |\d+[.)] |\||>)")
def validate(items):
    reviewed = []
    for item in items:
        proposals = []
        for s in item.get("suggestions", []):
            original = item["original"].strip()
            candidate = s["candidate"].strip()
            reasons = []
            if not candidate.startswith(original):
                reasons.append("not_original_prefix")
            suffix = candidate[len(original):].strip() if candidate.startswith(original) else ""
            if not suffix or len(suffix) > 350:
                reasons.append("invalid_continuation")
            if BAD.search(candidate) or BOUNDARY.match(suffix):
                reasons.append("unsafe_or_structural_content")
            if len(candidate) > 700:
                reasons.append("too_long")
            proposals.append({**s, "classification": "reviewable" if not reasons else "rejected",
                              "reasons": reasons})
        reviewed.append({"original": item["original"], "proposals": proposals,
                         "auto_applied": False})
    return reviewed

def run(input_path, output):
    items = json.loads(Path(input_path).read_text(encoding="utf-8"))
    reviewed = validate(items)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    (output / "validated_repairs.json").write_text(
        json.dumps(reviewed, ensure_ascii=False, indent=2), encoding="utf-8")
    counts = collections.Counter(p["classification"] for x in reviewed for p in x["proposals"])
    report = {"input_cases": len(reviewed),
              "cases_with_reviewable_proposal": sum(any(p["classification"] == "reviewable" for p in x["proposals"]) for x in reviewed),
              "reviewable_proposals": counts["reviewable"], "rejected_proposals": counts["rejected"],
              "auto_applied": 0}
    (output / "validated_repairs_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("repairs")
    parser.add_argument("--output", required=True)
    a = parser.parse_args()
    print(json.dumps(run(a.repairs, a.output)))
