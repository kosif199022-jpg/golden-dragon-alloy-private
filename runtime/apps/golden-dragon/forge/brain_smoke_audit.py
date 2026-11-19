"""Verify Golden Dragon knowledge preview is conserved and searchable."""
import argparse
import json
from pathlib import Path
from brain_query import search

def audit(brain_path, queries):
    brain_path = Path(brain_path)
    brain = json.loads(brain_path.read_text(encoding="utf-8-sig"))
    active = brain.get("instructions", [])
    quality = brain.get("quality_quarantine", [])
    conflict = brain.get("requires_review", [])
    missing_source = [i for i, x in enumerate(active) if not x.get("sources")]
    empty_text = [i for i, x in enumerate(active) if not x.get("text", "").strip()]
    results = {}
    for query in queries:
        hits = search(brain_path, query, limit=3)
        results[query] = {"hits": len(hits),
                          "top_score": hits[0]["score"] if hits else 0,
                          "top_source_count": len(hits[0]["sources"]) if hits else 0}
    return {"active": len(active), "quality_quarantined": len(quality),
            "conflict_quarantined": len(conflict),
            "preserved_total": len(active) + len(quality) + len(conflict),
            "active_missing_sources": len(missing_source),
            "active_empty_text": len(empty_text),
            "queries": results,
            "passed": not missing_source and not empty_text and all(v["hits"] for v in results.values())}

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("brain")
    p.add_argument("--output", required=True)
    p.add_argument("--query", action="append", default=[])
    a = p.parse_args()
    report = audit(a.brain, a.query or ["python", "testing", "security"])
    out = Path(a.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=True))
    if not report["passed"]:
        raise SystemExit(1)
