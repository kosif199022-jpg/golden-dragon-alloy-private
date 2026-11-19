"""Conservative similarity triage and reversible format-only fusion preview.

All original variants remain embedded in canonical records and an audit ledger.
"""
import argparse
import copy
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

NUMBERS = re.compile(r"\d+(?:[._-]\d+)*")
INLINE_CODE = re.compile(r"(?<!\x60)\x60[^\x60]+\x60(?!\x60)")
NEG_EN = re.compile(r"\b(?:not|never|cannot|can't|don't|do\s+not|avoid|forbid|prohibit)\b", re.I)
NEG_AR = re.compile(r"(?<!\w)(?:\u0644\u0627|\u0644\u064a\u0633|\u0628\u062f\u0648\u0646|\u062a\u062c\u0646\u0628|\u064a\u0645\u0646\u0639|\u0645\u0645\u0646\u0648\u0639)(?!\w)")
PERMISSIONS = re.compile(r"\b(?:allowed-tools|permissions|deny|allowlist|blocklist)\b", re.I)


def format_key(value):
    # Only ignore trailing sentence punctuation; never remove numbers or operators.
    return re.sub(r"[.;]+\Z", "", re.sub(r"\s+", " ", value.strip().casefold()))


def markers(value):
    return (tuple(sorted(x.casefold() for x in NEG_EN.findall(value))),
            tuple(sorted(NEG_AR.findall(value))))


def classify(left, right):
    risks = []
    if NUMBERS.findall(left) != NUMBERS.findall(right):
        risks.append("different_numbers")
    if INLINE_CODE.findall(left) != INLINE_CODE.findall(right):
        risks.append("different_inline_code")
    if markers(left) != markers(right):
        risks.append("different_negation")
    if PERMISSIONS.search(left) or PERMISSIONS.search(right):
        risks.append("permission_related")
    if format_key(left) != format_key(right) and (left.strip().startswith(right.strip()) or right.strip().startswith(left.strip())):
        risks.append("possible_truncation")
    safe = format_key(left) == format_key(right) and not risks
    return {"classification": "safe_format_only" if safe else "review_required",
            "risk_flags": risks}


def triage(brain, candidate_pairs):
    active = brain["instructions"]
    enriched = []
    safe_pairs = []
    for item in candidate_pairs:
        a, b = item["left_index"], item["right_index"]
        if a < 0 or b < 0 or a >= len(active) or b >= len(active) or a == b:
            raise ValueError("Invalid candidate indices")
        if active[a]["text"] != item["left_text"] or active[b]["text"] != item["right_text"]:
            raise ValueError("Candidate is not linked to the same source brain")
        verdict = classify(item["left_text"], item["right_text"])
        enriched.append({**item, **verdict})
        if verdict["classification"] == "safe_format_only":
            safe_pairs.append((a, b))
    return enriched, safe_pairs


def make_preview(brain, safe_pairs):
    original = brain["instructions"]
    parent = list(range(len(original)))
    def root(idx):
        while parent[idx] != idx:
            parent[idx] = parent[parent[idx]]
            idx = parent[idx]
        return idx
    for a, b in safe_pairs:
        if format_key(original[a]["text"]) != format_key(original[b]["text"]):
            raise ValueError("Refuse to combine non-identical knowledge")
        ra, rb = root(a), root(b)
        parent[max(ra, rb)] = min(ra, rb)
    grouped = defaultdict(list)
    for idx in range(len(original)):
        grouped[root(idx)].append(idx)
    active = []
    ledger = []
    for canonical, indices in sorted(grouped.items()):
        record = copy.deepcopy(original[canonical])
        if len(indices) > 1:
            variants = [{"original_index": idx, "record": copy.deepcopy(original[idx])}
                        for idx in indices]
            sources = []
            for idx in indices:
                for source in original[idx].get("sources", []):
                    if source not in sources:
                        sources.append(source)
            record["sources"] = sources
            record["verified_format_fusion"] = {
                "method": "format-only: whitespace and terminal punctuation",
                "variants": variants}
            ledger.append({"canonical_original_index": canonical,
                           "original_indices": indices,
                           "original_count": len(indices)})
        active.append(record)
    result = {**brain, "instructions": active,
              "fusion_status": "format-only equivalences; semantic equivalence pending"}
    return result, ledger


def run(brain_file, candidates_file, output_dir):
    brain = json.loads(Path(brain_file).read_text(encoding="utf-8-sig"))
    pairs = json.loads(Path(candidates_file).read_text(encoding="utf-8-sig"))
    enriched, safe = triage(brain, pairs)
    preview, ledger = make_preview(brain, safe)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "similarity_review_triage.json").write_text(
        json.dumps(enriched, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "format_fusion_preview.json").write_text(
        json.dumps(preview, ensure_ascii=False), encoding="utf-8")
    (out / "format_fusion_ledger.json").write_text(
        json.dumps(ledger, ensure_ascii=False, indent=2), encoding="utf-8")
    reason_counts = Counter(reason for row in enriched for reason in row["risk_flags"])
    report = {"input_active": len(brain["instructions"]),
              "similarity_candidates": len(pairs),
              "review_required": len(pairs) - len(safe),
              "safe_format_only_pairs": len(safe),
              "canonical_records": len(preview["instructions"]),
              "fusion_groups": len(ledger),
              "preserved_original_records": sum(
                  len(rec.get("verified_format_fusion", {}).get("variants", [rec]))
                  for rec in preview["instructions"]),
              "quality_quarantined": len(preview.get("quality_quarantine", [])),
              "conflict_quarantined": len(preview.get("requires_review", [])),
              "flagged": dict(sorted(reason_counts.items())),
              "semantically_fused": 0,
              "original_files_deleted": 0}
    (out / "format_fusion_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if report["preserved_original_records"] != report["input_active"]:
        raise RuntimeError("Loss of original records: do not publish preview")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("brain")
    parser.add_argument("candidates")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.brain, args.candidates, args.output), ensure_ascii=True))
