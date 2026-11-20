#!/usr/bin/env python3
"""Golden Dragon: non-destructive skill distillation into a unified knowledge index.

This is a static extractor, NOT a claim that tools are executable or that an LLM
has understood every skill. It never executes imported code or deletes sources.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path

HEAD = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.M)
MAX_FILE_BYTES = 2_000_000

def normalize(value):
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", value.casefold())).strip()

def extract(path, root):
    if path.stat().st_size > MAX_FILE_BYTES:
        return None
    raw = path.read_text(encoding="utf-8", errors="replace")
    matches = list(HEAD.finditer(raw))
    sections = []
    if matches and raw[:matches[0].start()].strip():
        intro = raw[:matches[0].start()].strip()
        sections.append({"heading": "Preamble", "body": intro,
                         "fingerprint": hashlib.sha256(normalize(intro).encode()).hexdigest()})
    if not matches and raw.strip():
        sections.append({"heading": "Full document", "body": raw.strip(),
                         "fingerprint": hashlib.sha256(normalize(raw).encode()).hexdigest()})
    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(raw)
        body = raw[match.end():end].strip()
        if not body:
            continue
        sections.append({"heading": match.group(2).strip(),
                         "body": body, "fingerprint": hashlib.sha256(normalize(body).encode()).hexdigest()})
    return {"source": str(path.relative_to(root)), "sha256": hashlib.sha256(raw.encode()).hexdigest(),
            "sections": sections, "status": "extracted_not_verified"}

def distill(root):
    files = sorted(p for p in root.rglob("SKILL.md") if p.is_file() and not p.is_symlink()
                   and not any(part.startswith(".") for part in p.relative_to(root).parts))
    items = []
    errors = []
    for path in files:
        try:
            item = extract(path, root)
            if item:
                items.append(item)
            else:
                errors.append({"source": str(path.relative_to(root)), "reason": "oversized"})
        except (OSError, ValueError) as exc:
            errors.append({"source": str(path.relative_to(root)), "reason": str(exc)})
    seen = {}
    unique = []
    duplicates = []
    for item in items:
        for section in item["sections"]:
            key = section["fingerprint"]
            origin = {"source": item["source"], "heading": section["heading"]}
            if key in seen:
                duplicates.append({"duplicate": origin, "original": seen[key]})
            else:
                seen[key] = origin
                unique.append({**origin, "body": section["body"], "fingerprint": key})
    return {"schema_version": 1, "mode": "static_non_destructive",
            "statistics": {"skills": len(items), "unique_sections": len(unique),
                           "duplicate_sections": len(duplicates), "errors": len(errors)},
            "skills": items, "knowledge": unique, "duplicates": duplicates, "errors": errors,
            "limitations": ["Static text extraction only; no semantic synthesis",
                            "No executability, security, or accuracy verification",
                            "Original sources are preserved"]}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path, help="Directory containing skills")
    parser.add_argument("--output", type=Path, required=True, help="JSON output path")
    args = parser.parse_args()
    root = args.root.expanduser().resolve()
    if not root.is_dir():
        parser.error("root must be an existing directory")
    result = distill(root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result["statistics"], ensure_ascii=False))

if __name__ == "__main__":
    main()
