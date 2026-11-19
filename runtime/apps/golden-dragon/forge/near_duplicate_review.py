"""Find near-duplicate active instructions without discarding any source knowledge."""
import argparse
import collections
import json
import re
from pathlib import Path

STOP = set("the and for with from into this that your you are use using when then how what where which about should must can will file files data create make run tools tool skill skills".split())
WORD = re.compile(r"[^\W_]+", re.UNICODE)
def terms(text):
    return {w for w in WORD.findall(text.casefold()) if len(w) >= 3 and w not in STOP}
def candidates(instructions, threshold=.84, min_shared=5, max_posting=180):
    docs = [terms(x.get("text", "")) for x in instructions]
    inverted = collections.defaultdict(list)
    for i, words in enumerate(docs):
        for w in words:
            inverted[w].append(i)
    clusters = []
    pairs = set()
    for i, words in enumerate(docs):
        if len(words) < min_shared:
            continue
        neighbors = collections.Counter(j for w in words if len(inverted[w]) <= max_posting
                                        for j in inverted[w] if j > i)
        for j, shared in neighbors.items():
            if shared < min_shared or len(docs[j]) < min_shared:
                continue
            if (i, j) in pairs:
                continue
            score = shared / len(words | docs[j])
            if score >= threshold:
                pairs.add((i, j))
                clusters.append({"left": i, "right": j, "jaccard": round(score, 4),
                                 "left_text": instructions[i]["text"],
                                 "right_text": instructions[j]["text"],
                                 "left_sources": instructions[i].get("sources", []),
                                 "right_sources": instructions[j].get("sources", []),
                                 "decision": "review_required"})
    return sorted(clusters, key=lambda x: -x["jaccard"])
def run(brain, output, threshold=.84):
    data = json.loads(Path(brain).read_text(encoding="utf-8-sig"))
    instructions = data["instructions"]
    found = candidates(instructions, threshold=threshold)
    out = Path(output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(found, ensure_ascii=False), encoding="utf-8")
    report = {"active_input": len(instructions), "candidate_pairs": len(found),
              "auto_merged": 0, "source_deleted": 0,
              "method": "word-set Jaccard, candidate pairs only; no embedding-based semantics"}
    out.with_name("near_duplicate_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report
if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("brain")
    p.add_argument("--output", required=True)
    p.add_argument("--threshold", type=float, default=.84)
    a = p.parse_args()
    if not .5 <= a.threshold <= 1:
        p.error("threshold must be between 0.5 and 1")
    print(json.dumps(run(a.brain, a.output, a.threshold)))
