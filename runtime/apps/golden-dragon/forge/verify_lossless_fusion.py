"""Verify all original instructions survive the conservative format-only fusion."""
import argparse
import collections
import json
from pathlib import Path


def audit(source, fusion):
    original = json.loads(Path(source).read_text(encoding="utf-8-sig"))
    preview = json.loads(Path(fusion).read_text(encoding="utf-8-sig"))
    recovered = []
    for entry in preview["instructions"]:
        if "verified_format_fusion" in entry:
            recovered.extend(x["record"] for x in entry["verified_format_fusion"]["variants"])
        else:
            recovered.append(entry)
    encode = lambda x: json.dumps(x, sort_keys=True, ensure_ascii=False)
    expected = collections.Counter(map(encode, original["instructions"]))
    actual = collections.Counter(map(encode, recovered))
    lost = sum((expected - actual).values())
    extra = sum((actual - expected).values())
    quarantine_intact = all(preview.get(k, []) == original.get(k, [])
                            for k in ("quality_quarantine", "requires_review"))
    return {"original_records": len(original["instructions"]),
            "recovered_records": len(recovered),
            "canonical_records": len(preview["instructions"]),
            "missing": lost, "extra": extra,
            "quarantine_intact": quarantine_intact,
            "passed": lost == 0 and extra == 0 and quarantine_intact}


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("source")
    p.add_argument("fusion")
    p.add_argument("--report", required=True)
    a = p.parse_args()
    result = audit(a.source, a.fusion)
    Path(a.report).write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result))
    if not result["passed"]:
        raise SystemExit(1)
