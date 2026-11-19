"""Generate a conservative standalone knowledge brain without silently losing unique instructions."""
import argparse
import json
from pathlib import Path

def build(instructions_file, conflicts_file, output):
    instructions = json.loads(Path(instructions_file).read_text(encoding="utf-8"))
    conflicts = json.loads(Path(conflicts_file).read_text(encoding="utf-8"))
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    conflict_texts = {item["text"] for c in conflicts for side in ("positive", "negative") for item in c[side]}
    safe = [i for i in instructions if i["text"] not in conflict_texts]
    review = [i for i in instructions if i["text"] in conflict_texts]
    (output / "brain.json").write_text(json.dumps({"instructions": safe, "requires_review": review}, ensure_ascii=False), encoding="utf-8")
    lines = ["# Golden Dragon Unified Brain (Knowledge Preview)", "", "This is a reference brain, NOT an executable tool adapter or fully validated semantic fusion.", "", "## Instructions"]
    for item in safe:
        lines.append("- " + item["text"].replace("\n", " "))
    lines += ["", "## Quarantined for conflict review"]
    for item in review:
        lines.append("- " + item["text"].replace("\n", " "))
    (output / "SKILL.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    report = {"instructions_in": len(instructions), "instructions_in_brain": len(safe), "requires_review": len(review), "conflict_groups": len(conflicts), "source_provenance_in_json": True}
    (output / "brain_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("instructions")
    parser.add_argument("conflicts")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.instructions, args.conflicts, args.output)))
