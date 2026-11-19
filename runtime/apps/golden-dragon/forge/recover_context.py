"""Recover original surrounding lines for flagged instruction fragments; never execute sources."""
import argparse
import json
import re
from pathlib import Path

def recover(items, root, max_items=None):
    root = Path(root).resolve()
    cache = {}
    output = []
    for item in items[:max_items]:
        matches = []
        for source in item.get("sources", []):
            relative = source.get("path", "")
            path = (root / relative).resolve()
            if not path.is_relative_to(root) or not path.is_file() or path.is_symlink():
                continue
            if path not in cache:
                try:
                    if path.stat().st_size > 2_000_000:
                        cache[path] = None
                    else:
                        cache[path] = path.read_text(encoding="utf-8-sig").splitlines()
                except (OSError, UnicodeError):
                    cache[path] = None
            lines = cache[path]
            if lines is None:
                continue
            needle = item["text"].strip()
            exact = [i for i, line in enumerate(lines) if needle in line]
            if not exact:
                continue
            i = exact[0]
            snippet = "\n".join(lines[max(0, i-2):min(len(lines), i+3)])
            matches.append({"source": relative, "line": i+1, "context": snippet})
            if len(matches) >= 2:
                break
        text = item["text"].strip()
        metadata = bool(re.match(r"^(?:name|description|version|author|license):", text, re.I))
        output.append({"text": text, "reasons": item.get("reasons", []),
                       "category": "metadata" if metadata else "review",
                       "context_matches": matches, "sources": item.get("sources", [])})
    return output

def run(issues_file, root, output):
    issues = json.loads(Path(issues_file).read_text(encoding="utf-8"))
    result = recover(issues, root)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    (output / "context_recovery.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    report = {"issues": len(result), "source_context_found": sum(bool(x["context_matches"]) for x in result),
              "metadata_candidates": sum(x["category"] == "metadata" for x in result),
              "unresolved": sum(not x["context_matches"] for x in result),
              "auto_replaced": 0}
    (output / "context_recovery_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("issues")
    parser.add_argument("source_root")
    parser.add_argument("--output", required=True)
    a = parser.parse_args()
    print(json.dumps(run(a.issues, a.source_root, a.output)))
