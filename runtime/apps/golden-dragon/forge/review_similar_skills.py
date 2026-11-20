#!/usr/bin/env python3
"""Conservative near-duplicate candidate groups for distilled skills.

This is NOT semantic fusion. Similar passages are only proposed for human review.
No source is removed and no merged instructions are invented.
"""
import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

def words(value):
    return set(re.findall(r"[^\W_]+", value.casefold(), re.UNICODE))

def candidate_groups(index, threshold=0.82, min_words=8):
    if not 0 < threshold <= 1:
        raise ValueError("threshold must be between 0 and 1")
    entries = index.get("knowledge", [])
    groups = []
    parent = list(range(len(entries)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    signatures = [words(entry.get("body", "")) for entry in entries]
    inverted = defaultdict(list)
    for i, signature in enumerate(signatures):
        if len(signature) < min_words:
            continue
        for token in signature:
            inverted[token].append(i)

    pair_overlap = defaultdict(int)
    for postings in inverted.values():
        if len(postings) > 200:
            continue  # very common tokens are not useful evidence
        for a_pos, a in enumerate(postings):
            for b in postings[a_pos + 1:]:
                pair_overlap[(a, b)] += 1

    edges = []
    for (a, b), overlap in pair_overlap.items():
        union = len(signatures[a]) + len(signatures[b]) - overlap
        similarity = overlap / union if union else 0
        if similarity >= threshold:
            parent[find(b)] = find(a)
            edges.append({"left": a, "right": b, "jaccard": round(similarity, 4)})

    components = defaultdict(list)
    for i in range(len(entries)):
        components[find(i)].append(i)
    for members in components.values():
        if len(members) < 2:
            continue
        groups.append({
            "members": [{"source": entries[i].get("source"), "heading": entries[i].get("heading"),
                         "fingerprint": entries[i].get("fingerprint")} for i in members],
            "status": "review_required",
            "warning": "Similarity is lexical, not evidence of interchangeable instructions",
        })
    return {"schema_version": 1, "candidate_groups": groups,
            "compared_sections": len(entries), "similarity_edges": len(edges),
            "sources_preserved": True}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("index", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--threshold", type=float, default=0.82)
    args = parser.parse_args()
    index = json.loads(args.index.read_text(encoding="utf-8"))
    if index.get("schema_version") != 1:
        parser.error("unsupported index schema")
    result = candidate_groups(index, threshold=args.threshold)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"groups": len(result["candidate_groups"]),
                      "compared_sections": result["compared_sections"]}))

if __name__ == "__main__":
    main()
