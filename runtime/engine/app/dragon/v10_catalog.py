"""Honest taxonomy of local index entries. Database rows are NOT runnable adapters."""
from __future__ import annotations
import sqlite3
from collections import Counter
from . import catalog
from .capabilities import probe_tools


def audit(limit: int = 12) -> dict:
    if not 0 <= limit <= 100: raise ValueError("limit must be 0..100")
    with sqlite3.connect(f"file:{catalog.DB}?mode=ro", uri=True) as db:
        db.row_factory=sqlite3.Row
        by_kind = {r[0]:r[1] for r in db.execute("SELECT kind,COUNT(*) FROM items GROUP BY kind")}
        by_source = {r[0]:r[1] for r in db.execute("SELECT source,COUNT(*) FROM items GROUP BY source")}
        total = sum(by_kind.values())
        # A catalog tool is an INDEX RECORD until matched to our own installed adapter.
        sampled = [dict(r) for r in db.execute("SELECT id,kind,source,name,status FROM items ORDER BY id LIMIT ?", (limit,))]
    probe=probe_tools()
    return {"kind":"black-dragon.v10/catalog-audit", "total_index_records":total,
            "catalog_by_kind":by_kind,"catalog_by_source":by_source,
            "registered_local_tools":probe["total"],
            "static_discoverable":probe["discoverable"],
            "missing_dependencies":probe["missing_dependencies"],
            "unverified_entrypoint":probe["unverified_entrypoint"],
            "executed_in_this_audit":0,
            "classification":{
                "method_description":"power/superpower records and textual skills are guidance, not executors",
                "tool_without_verified_adapter":"tool records outside the local registered execution map are unproven",
                "skill_program_without_verified_adapter":"some indexed skills may contain programs; this audit has not discovered or run them",
                "registered_but_unexecuted":"a discoverable CLI is not a passing execution receipt",
            },
            "sample_records":sampled,
            "full_coverage":False,
            "notice":"Historical reports claiming 72 or 6,773 executed refer to another environment and cannot be inferred from this index."}
