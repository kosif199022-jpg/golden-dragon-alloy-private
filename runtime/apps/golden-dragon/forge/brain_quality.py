"""Audit instruction extraction quality without changing the original knowledge."""
import argparse
import json
import re
from pathlib import Path

BAD_START = re.compile(r"^(?:and|or|but|because|before|after|when|then|which|that|to|of|for|with|from|mechanisms)\b", re.I)
END = re.compile(r"[.!?。！？:؛]$")

def audit(items):
    issues = []
    for item in items:
        s = item["text"].strip()
        reasons = []
        if BAD_START.search(s):
            reasons.append("fragment_start")
        if len(s.split()) < 4:
            reasons.append("too_short")
        if s.endswith((" before", " after", " and", " or", " to", " with", " from", " the", " a")):
            reasons.append("incomplete_end")
        if reasons:
            issues.append({"text": s, "reasons": reasons, "sources": item["sources"]})
    return issues

def run(source, out):
    items = json.loads(Path(source).read_text(encoding="utf-8"))
    issues = audit(items)
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "quality_review.json").write_text(json.dumps(issues, ensure_ascii=False), encoding="utf-8")
    stats = {"instructions_checked": len(items), "flagged_for_review": len(issues), "automatically_deleted": 0}
    (out / "quality_report.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")
    return stats

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("instructions")
    ap.add_argument("--output", required=True)
    a = ap.parse_args()
    print(json.dumps(run(a.instructions, a.output)))
