"""Dependency-free BM25 ranking over the quality-gated Golden Dragon brain."""
import argparse
import collections
import json
import math
import re
from pathlib import Path

TOKEN = re.compile(r"\w+", re.UNICODE)
META = re.compile(r"^\s*(?:name|description|version|author|license):", re.I)

def tokenize(value):
    return TOKEN.findall(value.casefold())

def search(brain, query, limit=5):
    terms = set(tokenize(query))
    if not terms:
        return []
    data = json.loads(Path(brain).read_text(encoding="utf-8-sig"))
    docs = []
    df = collections.Counter()
    for item in data["instructions"]:
        value = item.get("text", "")
        if not value or META.match(value):
            continue
        tokens = tokenize(value)
        if not tokens:
            continue
        freq = collections.Counter(tokens)
        docs.append((item, freq, len(tokens)))
        df.update(set(freq) & terms)
    if not docs:
        return []
    avg_length = sum(d[2] for d in docs) / len(docs)
    ranked = []
    for item, freq, length in docs:
        score = 0.0
        matched = 0
        for term in terms:
            tf = freq.get(term, 0)
            if not tf:
                continue
            matched += 1
            idf = math.log(1 + (len(docs) - df[term] + .5) / (df[term] + .5))
            score += idf * (tf * 2.2) / (tf + 1.2 * (.25 + .75 * length / avg_length))
        if score:
            ranked.append((matched, score, item))
    ranked.sort(key=lambda x: (-x[0], -x[1], len(x[2]["text"])))
    return [{"text": item["text"], "sources": item.get("sources", []),
             "score": round(score, 4), "matched_terms": matched}
            for matched, score, item in ranked[:max(1, limit)]]

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("brain")
    p.add_argument("query")
    p.add_argument("--limit", type=int, default=5)
    a = p.parse_args()
    print(json.dumps(search(a.brain, a.query, min(100, max(1, a.limit))), ensure_ascii=False, indent=2))
