"""Extract actionable instruction candidates, preserve every source and flag conflicting modalities."""
import argparse
import collections
import json
import re
from pathlib import Path

VERBS = re.compile(r"\b(?:must|should|never|always|ensure|verify|check|validate|avoid|require|run|execute|write|read|create|install|test|use|don't|do not)\b|(?:يجب|لازم|تأكد|تحقق|افحص|اختبر|استخدم|شغل|نفذ|لا تستخدم|ممنوع)", re.I)
NEG = re.compile(r"\b(?:never|avoid|don't|do not|must not|should not)\b|(?:لا تستخدم|ممنوع|لا تفعل)", re.I)
def canonical(s):
    return re.sub(r"\s+", " ", re.sub(r"^[\s*#>\-\d.)]+", "", s)).strip().casefold()
def extract(entries):
    found = collections.defaultdict(lambda: {"text": "", "sources": [], "negative": False})
    for entry in entries:
        for line in entry["text"].splitlines():
            line = line.strip()
            if not line or line.startswith(("#", "---", "|")) or not VERBS.search(line):
                continue
            if len(line) > 700:
                continue
            key = canonical(line)
            if len(key) < 12:
                continue
            item = found[key]
            item["text"] = item["text"] or line
            item["negative"] = bool(NEG.search(line))
            item["sources"].extend(entry["sources"])
    return list(found.values())
def run(index, output):
    entries = json.loads(Path(index).read_text(encoding="utf-8"))
    instructions = extract(entries)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    (output / "instruction_candidates.json").write_text(json.dumps(instructions, ensure_ascii=False), encoding="utf-8")
    stats = {"input_sections": len(entries), "instruction_candidates": len(instructions), "negative_instructions": sum(x["negative"] for x in instructions), "status": "candidate extraction only; contradictions and semantic equivalence not automatically resolved"}
    (output / "instruction_report.json").write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
    return stats
if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("index")
    ap.add_argument("--output", required=True)
    a = ap.parse_args()
    print(json.dumps(run(a.index, a.output), ensure_ascii=False))
