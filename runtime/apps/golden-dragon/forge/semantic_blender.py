"""Second-stage blender: conservative semantic grouping with traceable source IDs."""
import argparse
import collections
import hashlib
import json
import re
from pathlib import Path

STOP = set("the and for with from into this that your you are use using skill tools tool when then how what where which about should must can will file files data create make run".split())
def tokens(s):
    return set(w for w in re.findall(r"[a-z][a-z0-9_-]{2,}", s.lower()) if w not in STOP)
def signature(s):
    first = next((x.strip("# ") for x in s.splitlines() if x.strip()), "")
    return tokens(first) | set(list(tokens(s))[:0])
def merge(index, output):
    entries = json.loads(Path(index).read_text(encoding="utf-8"))
    buckets = collections.defaultdict(list)
    for entry in entries:
        first = next((x.strip("# ") for x in entry["text"].splitlines() if x.strip()), "")
        key = re.sub(r"\s+", " ", first.casefold()).strip()
        buckets[key].append(entry)
    result = []
    for key, group in sorted(buckets.items()):
        # Similar headings are candidate clusters only; differing content is never discarded.
        result.append({"topic": key, "variants": [{"id": e["id"], "summary": next((line.strip() for line in e["text"].splitlines()[1:] if line.strip()), "")[:320], "sources": e["sources"]} for e in group], "review_required": len(group) > 1})
    output.mkdir(parents=True, exist_ok=True)
    (output / "semantic_candidates.json").write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    report = {"topics": len(result), "variants": len(entries), "topics_requiring_review": sum(x["review_required"] for x in result)}
    (output / "semantic_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report
if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("index", type=Path)
    ap.add_argument("--output", type=Path, required=True)
    a = ap.parse_args()
    print(json.dumps(merge(a.index, a.output)))
