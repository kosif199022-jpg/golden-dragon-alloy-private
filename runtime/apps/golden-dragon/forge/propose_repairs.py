"""Suggest source-grounded repairs; never silently change the active brain."""
import argparse
import json
import re
from pathlib import Path

def suggest(records):
    result = []
    for item in records:
        text = item["text"].strip()
        suggestions = []
        for match in item.get("context_matches", []):
            lines = match["context"].splitlines()
            exact = [i for i, line in enumerate(lines) if text in line]
            if not exact:
                continue
            i = exact[0]
            original = lines[i].strip()
            candidate = original
            if i + 1 < len(lines) and not re.match(r"^\s*(?:#|[-*] |\d+[.)] |\||```)", lines[i+1]):
                continuation = lines[i+1].strip()
                if continuation and len(candidate) + len(continuation) < 900:
                    candidate += " " + continuation
            if candidate != text and len(candidate) > len(text):
                suggestions.append({"candidate": candidate, "source": match["source"],
                                    "line": match["line"], "status": "review_required"})
        result.append({"original": text, "reasons": item.get("reasons", []),
                       "source_matches": len(item.get("context_matches", [])),
                       "suggestions": suggestions, "auto_applied": False})
    return result

def run(input_file, output_dir):
    records = json.loads(Path(input_file).read_text(encoding="utf-8"))
    proposals = suggest(records)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "repair_proposals.json").write_text(
        json.dumps(proposals, ensure_ascii=False, indent=2), encoding="utf-8")
    report = {"reviewed": len(proposals),
              "with_repair_proposals": sum(bool(x["suggestions"]) for x in proposals),
              "without_repair_proposals": sum(not x["suggestions"] for x in proposals),
              "auto_applied": 0}
    (output_dir / "repair_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("context_recovery")
    p.add_argument("--output", required=True)
    a = p.parse_args()
    print(json.dumps(run(a.context_recovery, a.output)))
