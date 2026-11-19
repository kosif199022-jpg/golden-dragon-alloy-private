"""Read-only dependency and capability map for Golden Dragon source.

Run:
 python forge/unified_core/map_dependencies.py apps/golden-dragon --out dependency-map.json

This is static analysis, not a runtime verification. It never imports target code.
"""
from __future__ import annotations
import argparse
import ast
import json
from collections import Counter, defaultdict
from pathlib import Path

SKIP = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build"}
CAPABILITY_TERMS = {
    "video": ("video", "ffmpeg", "remotion", "reels", "render", "motion"),
    "reverse_engineering": ("ghidra", "rea", "decompile", "reverse", "binary"),
    "fusion": ("fusion", "route", "recipe", "skills", "registry"),
    "audio": ("audio", "whisper", "speech", "tts", "voice"),
    "ui": ("interface", "ui", "frontend", "window", "html", "css"),
}
def scan(root: Path) -> dict:
    records = []
    errors = []
    imports = Counter()
    external_refs = []
    for p in sorted(root.rglob("*")):
        if not p.is_file() or any(part in SKIP for part in p.relative_to(root).parts):
            continue
        if p.suffix.lower() not in {".py", ".js", ".ts", ".tsx", ".ps1", ".sh"}:
            continue
        rel = p.relative_to(root).as_posix()
        try:
            source = p.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeError) as exc:
            errors.append({"file": rel, "error": str(exc)})
            continue
        low = (rel + "\n" + source).lower()
        categories = [name for name, words in CAPABILITY_TERMS.items()
                      if any(word in low for word in words)]
        record = {"path": rel, "categories": categories, "imports": [],
                  "functions": [], "classes": []}
        if p.suffix == ".py":
            try:
                tree = ast.parse(source, filename=rel)
                record["functions"] = [n.name for n in ast.walk(tree)
                                       if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
                record["classes"] = [n.name for n in ast.walk(tree)
                                     if isinstance(n, ast.ClassDef)]
                names = []
                for n in ast.walk(tree):
                    if isinstance(n, ast.Import):
                        names.extend(a.name for a in n.names)
                    elif isinstance(n, ast.ImportFrom):
                        names.append("." * n.level + (n.module or ""))
                record["imports"] = sorted(set(names))
                imports.update(name.split(".")[0] for name in names if name and not name.startswith("."))
            except SyntaxError as exc:
                errors.append({"file": rel, "error": f"SyntaxError: {exc}"})
        for line_no, line in enumerate(source.splitlines(), 1):
            if any(marker in line.lower() for marker in
                   ("make_golden_bird", "make_white_bird", "goldenbird", "whitebird")):
                external_refs.append({"file": rel, "line": line_no,
                                      "excerpt": line.strip()[:220]})
        records.append(record)
    return {
        "root": str(root), "summary": {
            "scanned_source_files": len(records), "parse_or_read_errors": len(errors),
            "category_hits": dict(Counter(c for r in records for c in r["categories"])),
            "top_imports": imports.most_common(40),
            "upstream_reference_hits": len(external_refs),
        },
        "files": records, "upstream_references": external_refs, "errors": errors,
        "verification": {
            "method": "static source scan only",
            "executed_target_code": False, "runtime_capabilities_verified": False,
            "complete_repository_coverage": False,
            "note": "Run against a complete checkout; inspect generated JSON before claiming coverage.",
        },
    }

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("--out", type=Path, default=Path("dependency-map.json"))
    args = parser.parse_args()
    if not args.root.is_dir():
        parser.error("root must be a directory")
    result = scan(args.root.resolve())
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
