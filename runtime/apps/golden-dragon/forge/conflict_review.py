"""Flag possible instruction contradictions for review, never silently resolve them."""
import argparse
import collections
import json
import re
from pathlib import Path

NEG = re.compile(r"\b(?:never|avoid|don't|do not|must not|should not)\b|(?:ممنوع|لا تستخدم|لا تفعل)", re.I)
POS = re.compile(r"\b(?:always|must|should|ensure|use|run|execute|verify)\b|(?:يجب|لازم|استخدم|نفذ|شغل|تأكد)", re.I)
MODAL = re.compile(r"\b(?:never|avoid|don't|do not|must not|should not|always|must|should|ensure|use|run|execute|verify)\b|(?:ممنوع|لا تستخدم|لا تفعل|يجب|لازم|استخدم|نفذ|شغل|تأكد)", re.I)
def key(text):
    text = MODAL.sub(" ", text.casefold())
    return re.sub(r"\W+", " ", text, flags=re.UNICODE).strip()
def detect(items):
    buckets = collections.defaultdict(lambda: {"positive": [], "negative": []})
    for item in items:
        text = item["text"]
        neg = bool(NEG.search(text))
        pos = bool(POS.search(text))
        if not (neg or pos):
            continue
        k = key(text)
        if len(k) < 12:
            continue
        buckets[k]["negative" if neg else "positive"].append(item)
    return [{"subject": k, "positive": v["positive"], "negative": v["negative"], "status": "possible conflict; human review required"} for k, v in buckets.items() if v["positive"] and v["negative"]]
def run(source, output):
    items = json.loads(Path(source).read_text(encoding="utf-8"))
    conflicts = detect(items)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    (output / "conflict_candidates.json").write_text(json.dumps(conflicts, ensure_ascii=False), encoding="utf-8")
    report = {"instructions_checked": len(items), "possible_conflicts": len(conflicts), "auto_resolved": 0}
    (output / "conflict_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report
if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("instructions")
    ap.add_argument("--output", required=True)
    a = ap.parse_args()
    print(json.dumps(run(a.instructions, a.output)))
