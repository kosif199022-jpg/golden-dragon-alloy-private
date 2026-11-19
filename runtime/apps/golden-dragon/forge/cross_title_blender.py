"""Cross-title semantic candidates, with lossless provenance and no false claims of LLM synthesis."""
import argparse
import collections
import json
import re
from pathlib import Path

STOP = set("the and for with from into this that your you are use using skill skills tools tool when then how what where which about should must can will file files data create make run guide overview introduction reference examples notes".split())

def terms(text):
    title = next((x.strip(" #\t") for x in text.splitlines() if x.strip()), "")
    return set(w for w in re.findall(r"[a-z][a-z0-9_-]{2,}", title.lower()) if w not in STOP)

def group(entries, threshold=0.8):
    tokens = [terms(e["text"]) for e in entries]
    inverted = collections.defaultdict(list)
    for i, ts in enumerate(tokens):
        for term in ts:
            inverted[term].append(i)
    parent = list(range(len(entries)))
    def root(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    def union(a, b):
        a, b = root(a), root(b)
        if a != b:
            parent[max(a, b)] = min(a, b)
    checked = set()
    for i, ts in enumerate(tokens):
        if len(ts) < 2:
            continue
        candidates = collections.Counter(j for t in ts if len(inverted[t]) <= 250 for j in inverted[t] if j > i)
        for j, overlap in candidates.items():
            if overlap < 2:
                continue
            sim = overlap / len(ts | tokens[j])
            if sim >= threshold:
                union(i, j)
    clusters = collections.defaultdict(list)
    for i, entry in enumerate(entries):
        clusters[root(i)].append({"id": entry["id"], "title": next((x.strip(" #\t") for x in entry["text"].splitlines() if x.strip()), ""), "sources": entry["sources"]})
    return [v for v in clusters.values() if len(v) > 1]

def run(index, output):
    entries = json.loads(Path(index).read_text(encoding="utf-8"))
    clusters = group(entries)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    (output / "cross_title_candidates.json").write_text(json.dumps(clusters, ensure_ascii=False), encoding="utf-8")
    report = {"input_sections": len(entries), "candidate_clusters": len(clusters), "sections_in_clusters": sum(map(len, clusters)), "method": "conservative title-token Jaccard; candidates only, no information discarded"}
    (output / "cross_title_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("index")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.index, args.output), ensure_ascii=False))
