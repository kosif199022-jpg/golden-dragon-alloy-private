"""Golden Dragon capability ledger: passive evidence, not a claimed execution test.

Usage:
  python capability_ledger.py --index forge/data/fusion/index.json \
    --recipes forge/data/fusion/recipes.json [--out audit.json]

Safe: reads JSON and local file metadata; never imports target project code,
starts third-party programs, changes app files, or calls network services.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
from collections import Counter
from pathlib import Path


def _present(path: str) -> bool:
    """Check a catalog path without executing or opening the target code."""
    if not path:
        return False
    p = Path(os.path.expandvars(os.path.expanduser(path)))
    return p.is_file()


def _program_present(probe: str) -> bool:
    if not probe:
        return False
    if probe.startswith("py:"):
        module = probe[3:]
        if not module.isidentifier():
            return False
        try:
            return importlib.util.find_spec(module) is not None
        except (ImportError, AttributeError, ValueError):
            return False
    return shutil.which(probe) is not None


def build_ledger(index: dict, recipes: list | None = None) -> dict:
    """Catalog claims and passive observations are separate from runtime proof."""
    units = index.get("units") or []
    if not isinstance(units, list):
        raise ValueError("index.units must be an array")
    if recipes is None:
        recipes = []
    if not isinstance(recipes, list):
        raise ValueError("recipes must be an array")

    ids = set()
    repeated = []
    counts = Counter()
    catalog_status = Counter()
    evidence = Counter()
    records = []
    for u in units:
        if not isinstance(u, dict) or not isinstance(u.get("id"), str):
            raise ValueError("unit has no valid id")
        ident = u["id"]
        if ident in ids:
            repeated.append(ident)
        ids.add(ident)
        kind = str(u.get("kind") or "unknown")
        declared = str(u.get("status") or "unknown")
        observed = "catalog_only"
        if kind == "skill":
            observed = ("skill_source_present" if _present(str(u.get("path") or ""))
                        else "skill_source_missing")
        elif kind == "program":
            observed = ("program_found_on_path" if _program_present(str(u.get("probe") or ""))
                        else "program_not_found_on_path")
        record = {
            "id": ident, "kind": kind, "catalog_status": declared,
            "passive_observation": observed,
            "runtime_verified": False,
            "note": "No capability executed; catalog OK never proves functional readiness",
        }
        records.append(record)
        counts[kind] += 1
        catalog_status[declared] += 1
        evidence[observed] += 1

    recipe_issues = []
    for recipe in recipes:
        if not isinstance(recipe, dict):
            recipe_issues.append({"recipe": None, "error": "invalid_recipe"})
            continue
        rid = str(recipe.get("id") or "")
        for i, step in enumerate(recipe.get("steps") or [], 1):
            if not isinstance(step, dict):
                recipe_issues.append({"recipe": rid, "step": i, "error": "invalid_step"})
                continue
            for field in ("read", "use"):
                for ref in step.get(field) or []:
                    if ref not in ids:
                        recipe_issues.append({
                            "recipe": rid, "step": i, "field": field,
                            "unit": ref, "error": "unknown_unit",
                        })
            if not step.get("gate_ar"):
                recipe_issues.append({"recipe": rid, "step": i, "error": "missing_gate"})

    return {
        "schema": "golden-dragon.capability-evidence.v1",
        "generated_catalog": index.get("generated"),
        "counts": {
            "indexed_units": len(units),
            "kinds": dict(counts),
            "catalog_status": dict(catalog_status),
            "passive_observations": dict(evidence),
            "runtime_verified": 0,
            "recipes_checked": len(recipes),
            "recipe_issues": len(recipe_issues),
            "duplicate_unit_ids": len(repeated),
        },
        "duplicate_ids": repeated,
        "recipe_issues": recipe_issues,
        "units": records,
        "limitations": [
            "A source file existing is not proof that a skill works.",
            "An executable on PATH is not proof that an operation succeeds.",
            "A recipe naming a valid unit is not an execution test.",
            "REA/Ghidra must produce independent evidence for binary claims.",
            "No user code or third-party executable was run.",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", type=Path, required=True)
    parser.add_argument("--recipes", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    index = json.loads(args.index.read_text(encoding="utf-8-sig"))
    recipes = json.loads(args.recipes.read_text(encoding="utf-8-sig")) if args.recipes else []
    ledger = build_ledger(index, recipes)
    if args.out:
        if args.out.exists():
            parser.error("refusing to overwrite an existing report")
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(ledger, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(ledger["counts"], ensure_ascii=False, indent=2))
    return 1 if ledger["recipe_issues"] or ledger["duplicate_ids"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
