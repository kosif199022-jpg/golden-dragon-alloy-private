#!/usr/bin/env python3
"""Search distilled knowledge without executing original skill files."""
import argparse
import json
import re
from pathlib import Path

def tokens(s):
    return set(re.findall(r"[^\W_]+", s.casefold(), flags=re.UNICODE))

def search(index, query, limit=5):
    q = tokens(query)
    if not q:
        return []
    scored = []
    for entry in index.get("knowledge", []):
        heading = tokens(entry.get("heading", ""))
        body = tokens(entry.get("body", ""))
        overlap = len(q & body)
        score = 3 * len(q & heading) + overlap
        if score:
            scored.append((score, entry))
    scored.sort(key=lambda pair: (-pair[0], pair[1].get("source", ""), pair[1].get("heading", "")))
    return [{"score": score, "source": entry["source"], "heading": entry["heading"],
             "body": entry["body"], "fingerprint": entry["fingerprint"]}
            for score, entry in scored[:limit]]

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("index", type=Path)
    parser.add_argument("query")
    parser.add_argument("--limit", type=int, default=5)
    args = parser.parse_args()
    if not 1 <= args.limit <= 100:
        parser.error("--limit must be between 1 and 100")
    index = json.loads(args.index.read_text(encoding="utf-8"))
    if index.get("schema_version") != 1:
        parser.error("unsupported index schema")
    print(json.dumps(search(index, args.query, args.limit), ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
