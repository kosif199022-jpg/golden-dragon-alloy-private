"""High-recall character n-gram similarity suggestions for independent knowledge fusion.

Builds *review-only* candidate pairs, including Arabic and minor rewrites.
Similarity is lexical, not a proof of semantic equivalence. Never deletes sources.
"""
import argparse
import json
import re
from pathlib import Path

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

NEG_EN = re.compile(r"\b(?:not|never|don't|do not|cannot|can't|avoid|prohibit|forbid)\b", re.I)
NEG_AR = re.compile(r'(?:\u0644\u0627|\u0644\u064a\u0633|\u0628\u062f\u0648\u0646|\u062a\u062c\u0646\u0628|\u064a\u0645\u0646\u0639|\u0645\u0645\u0646\u0648\u0639)')
META = re.compile(r"^\s*(?:name|description|version|author|license):", re.I)


def opposition_hint(a, b):
    # Only a hint: never automatically classify these as actual contradictions.
    return bool(NEG_EN.search(a) or NEG_AR.search(a)) != bool(NEG_EN.search(b) or NEG_AR.search(b))


def find_pairs(items, threshold=0.78, max_neighbors=5, batch=128, max_pairs=25000):
    texts = [item.get("text", "") for item in items]
    valid = [(i, text) for i, text in enumerate(texts)
             if len(text.strip()) >= 32 and not META.match(text)]
    if len(valid) < 2:
        return [], {"compared": len(valid), "vocabulary": 0, "truncated": False}
    ids, content = zip(*valid)
    vectorizer = TfidfVectorizer(
        analyzer="char_wb", ngram_range=(3, 5), min_df=2 if len(valid) >= 10 else 1,
        max_df=0.25 if len(valid) >= 10 else 1.0, max_features=140000, sublinear_tf=True,
        dtype=np.float32, norm="l2")
    matrix = vectorizer.fit_transform(content)
    if not matrix.shape[1]:
        return [], {"compared": len(valid), "vocabulary": 0, "truncated": False}
    pairs = []
    truncated = False
    for offset in range(0, matrix.shape[0], batch):
        scores = (matrix[offset:offset + batch] @ matrix.T).tocsr()
        for local in range(scores.shape[0]):
            i = offset + local
            start, end = scores.indptr[local], scores.indptr[local + 1]
            near = [(j, float(sim)) for j, sim in zip(scores.indices[start:end], scores.data[start:end])
                    if j > i and sim >= threshold]
            near.sort(key=lambda x: (-x[1], x[0]))
            for j, sim in near[:max_neighbors]:
                original_i, original_j = ids[i], ids[j]
                pairs.append({
                    "left_index": original_i, "right_index": original_j,
                    "similarity": round(sim, 4),
                    "left_text": texts[original_i], "right_text": texts[original_j],
                    "left_sources": items[original_i].get("sources", []),
                    "right_sources": items[original_j].get("sources", []),
                    "possible_negation_difference": opposition_hint(texts[original_i], texts[original_j]),
                    "decision": "pending_manual_review"})
                if len(pairs) >= max_pairs:
                    truncated = True
                    break
            if truncated:
                break
        if truncated:
            break
    pairs.sort(key=lambda x: (-x["similarity"], x["left_index"], x["right_index"]))
    return pairs, {"compared": len(valid), "vocabulary": matrix.shape[1],
                   "truncated": truncated}


def run(brain, output, threshold=0.78):
    data = json.loads(Path(brain).read_text(encoding="utf-8-sig"))
    items = data["instructions"]
    pairs, stats = find_pairs(items, threshold=threshold)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(pairs, ensure_ascii=False, indent=2), encoding="utf-8")
    report = {"input_active": len(items), **stats, "candidate_pairs": len(pairs),
              "with_negation_difference": sum(x["possible_negation_difference"] for x in pairs),
              "auto_merged": 0, "deleted": 0, "threshold": threshold,
              "method": "TF-IDF character 3-5 gram cosine; review-only, NOT semantic entailment"}
    output.with_name("char_similarity_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("brain")
    p.add_argument("--output", required=True)
    p.add_argument("--threshold", type=float, default=0.78)
    a = p.parse_args()
    if not 0.5 <= a.threshold <= 1:
        p.error("threshold must be between 0.5 and 1")
    print(json.dumps(run(a.brain, a.output, a.threshold), ensure_ascii=True))

