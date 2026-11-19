"""Read-only search over the Golden Dragon brain preview; no tool execution."""
import argparse
import json
import re
from pathlib import Path

def search(brain, query, limit=5):
    data = json.loads(Path(brain).read_text(encoding="utf-8"))
    words = set(re.findall(r"\w+", query.casefold(), re.UNICODE))
    if not words:
        return []
    scored = []
    for item in data["instructions"]:
        text = item["text"]
        if re.match(r"^\s*(?:name|description|version|author|license):", text, re.I):
            continue
        text_words = set(re.findall(r"\w+", text.casefold(), re.UNICODE))
        overlap = len(words & text_words)
        if overlap:
            scored.append((overlap / len(words), overlap, item))
    scored.sort(key=lambda x: (-x[0], -x[1], len(x[2]["text"])))
    return [{"text": x[2]["text"], "sources": x[2]["sources"], "score": round(x[0], 3)} for x in scored[:limit]]

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("brain")
    ap.add_argument("query")
    ap.add_argument("--limit", type=int, default=5)
    args = ap.parse_args()
    print(json.dumps(search(args.brain, args.query, max(1, min(args.limit, 100))), ensure_ascii=False, indent=2))

