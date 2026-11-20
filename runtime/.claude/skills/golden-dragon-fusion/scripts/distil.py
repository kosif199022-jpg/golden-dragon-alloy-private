"""Distil recurring practices from the installed sources into one operating brief."""
import argparse
import json
import re
from pathlib import Path

# Each clause has an observable deliverable or acceptance check.
PRACTICES = [
    (r"reference image|style guide|design token|character sheet", "Carry a shared visual reference through every shot or component. Check the delivered result against it."),
    (r"storyboard|shot list|timeline|keyframe", "Map the requested sequence to shots or states before production. Preserve their timing when composing the final output."),
    (r"caption|subtitle|transcript", "Derive captions from the actual speech, preserve language and direction, then inspect timing and readability in the export."),
    (r"aspect ratio|frame rate|ffprobe", "Set dimensions and timing from the requested delivery format and measure both in the exported media."),
    (r"schema|reconcil|spreadsheet|worksheet", "Carry field names, units and identifiers through transformations. Reconcile counts and totals against the input."),
    (r"sha256|checksum|file signature|provenance", "Identify the input and record its provenance before interpreting or converting it."),
    (r"test case|regression|acceptance criteria", "Turn the user's success condition into a check and exercise the actual entry point with representative input."),
    (r"accessibility|contrast ratio|right.to.left", "Inspect the output in its intended language, reading direction and display size."),
    (r"render|export|deliverable", "Open the delivered artifact and check its contents and format. Report any unverified property.")
]


def distil(index):
    units = json.loads(index.read_text(encoding="utf-8-sig"))["units"]
    ids = {unit["id"] for unit in units}
    if len(ids) != len(units):
        raise ValueError("Duplicate capability IDs")
    support = [set() for _ in PRACTICES]
    documents = 0
    matched = set()
    for unit in units:
        parts = [str(unit.get(key) or "") for key in ("name", "what", "what_ar")]
        if unit["kind"] == "skill" and unit.get("path"):
            path = Path(unit["path"])
            if path.is_file():
                parts.append(path.read_text(encoding="utf-8-sig", errors="replace"))
                documents += 1
        body = " ".join(parts)
        for i, (pattern, _) in enumerate(PRACTICES):
            if re.search(pattern, body, re.I):
                support[i].add(unit["id"])
                matched.add(unit["id"])
    lines = ["# Combined working method", "",
             "Apply the relevant checks together to produce one final deliverable. Use the output of each step as the next step's input.", ""]
    for (_, instruction), evidence in zip(PRACTICES, support):
        if len(evidence) >= 2:
            lines.append("- " + instruction)
    return "\n".join(lines) + "\n", (len(ids), documents, len(matched))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("index", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    brief, coverage = distil(args.index)
    args.output.write_text(brief, encoding="utf-8")
    print("Catalog inputs: %s; full skill files read: %s; inputs matching one or more practices: %s" % coverage)
