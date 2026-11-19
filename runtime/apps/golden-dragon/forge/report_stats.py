"""report_stats.py — the numbers of the analysis report, measured from the data (never typed by hand).
Writes ..\\analysis\\stats.json and prints a short summary.

  python -X utf8 report_stats.py
"""
import json
import os
from collections import Counter
from pathlib import Path

FORGE = Path(__file__).resolve().parent
GD = FORGE.parent
DESK = GD.parent
sk = json.loads((FORGE / "data" / "skills.json").read_text(encoding="utf-8"))
idx = json.loads((FORGE / "data" / "fusion" / "index.json").read_text(encoding="utf-8"))
S = sk["skills"]
units = idx["units"]
skill_units = [u for u in units if u["kind"] == "skill"]

top_level = Counter()
sizes = Counter()
for e in os.scandir(DESK):
    if e.is_dir(follow_symlinks=False):
        top_level["dirs"] += 1
    else:
        ext = Path(e.name).suffix.lower() or "(none)"
        top_level[ext] += 1
        sizes[ext] += e.stat().st_size

stats = {
    "skills": len(S),
    "skills_containers": [(c["id"], c["nested_skills"]) for c in sk["containers"]],
    "skills_loose_files": len(sk["loose_files"]),
    "skills_files_total": sum(s.get("files", 0) for s in S),
    "skills_bytes_total_gb": round(sum(s.get("bytes", 0) for s in S) / 1e9, 2),
    "skills_with_scripts": sum(1 for s in S if s.get("scripts_total")),
    "skills_scripts_total": sum(s.get("scripts_total", 0) for s in S),
    "langs": sk["langs"],
    "flags": sk["flags"],
    "families_top": list(sk["families"].items())[:25],
    "families_count": len(sk["families"]),
    "older_versions": [(s["id"], s.get("version"), s.get("superseded_by")) for s in S if s.get("superseded_by")],
    "name_differs": [(s["id"], s["name"]) for s in S if "name-differs-from-folder" in s.get("flags", [])],
    "desc_over_1024": [s["id"] for s in S if "description-over-1024" in s.get("flags", [])],
    "over_500_lines": [s["id"] for s in S if "skill-md-over-500-lines" in s.get("flags", [])],
    "partial_examples": [(s["id"], (s.get("missing") or s.get("missing_shared") or [])[:2]) for s in S
                         if s.get("missing") or s.get("missing_shared")][:15],
    "paid_or_external": sorted(u["name"] for u in skill_units if u.get("cost") == "paid"),
    "biggest_skills_mb": sorted(((s["id"], round(s.get("bytes", 0) / 1e6)) for s in S), key=lambda x: -x[1])[:10],
    "mcp_named": Counter(m for s in S for m in s.get("mcp", [])).most_common(12),
    "index_counts": idx["counts"],
    "index_status": dict(Counter(u["status"] for u in units)),
    "maharat_top_level": dict(top_level.most_common()),
    "maharat_top_level_gb_by_ext": {k: round(v / 1e9, 2) for k, v in sizes.most_common(8)},
}
(GD / "analysis" / "stats.json").write_text(json.dumps(stats, ensure_ascii=False, indent=1), encoding="utf-8")
for k in ("skills", "skills_files_total", "skills_bytes_total_gb", "skills_with_scripts", "skills_scripts_total", "langs", "flags",
          "families_count", "older_versions", "name_differs", "paid_or_external", "biggest_skills_mb", "mcp_named",
          "index_status", "maharat_top_level", "maharat_top_level_gb_by_ext", "skills_containers"):
    print(f"{k}: {stats[k]}")
