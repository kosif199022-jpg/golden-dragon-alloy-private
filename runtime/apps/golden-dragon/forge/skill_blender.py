"""Golden Dragon skill blender: source-preserving, non-executing distillation."""
import argparse
import hashlib
import json
import re
from pathlib import Path

def blend(root: Path, output: Path):
    if output.resolve().is_relative_to(root.resolve()):
        raise ValueError("Output must be outside source tree")
    groups = {}
    files = 0
    for file in sorted(root.rglob("SKILL.md")):
        if file.is_symlink() or any(p.is_symlink() for p in file.parents if p != root.parent):
            continue
        try:
            body = file.read_text(encoding="utf-8-sig")
        except (UnicodeError, OSError):
            continue
        files += 1
        parts = re.split(r"(?=^#{1,6}\s+)", body, flags=re.M)
        for i, part in enumerate(parts):
            part = part.strip()
            if not part:
                continue
            normalized = re.sub(r"\s+", " ", part).casefold()
            digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
            record = groups.setdefault(digest, {"text": part, "sources": []})
            record["sources"].append({"path": str(file.relative_to(root)), "section": i})
    output.mkdir(parents=True, exist_ok=True)
    entries = [{"id": key, **val} for key, val in sorted(groups.items())]
    (output / "knowledge.json").write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# Golden Dragon Unified Knowledge", "", "Generated knowledge; sources retained. No executable adapters created.", ""]
    for entry in entries:
        lines += [entry["text"], "", "Sources: " + ", ".join(f"{s['path']}#{s['section']}" for s in entry["sources"]), ""]
    (output / "SKILL.md").write_text("\n".join(lines), encoding="utf-8")
    report = {"files_scanned": files, "unique_sections": len(entries), "source_sections": sum(len(e["sources"]) for e in entries), "output": str(output)}
    (output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("skills_dir", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(blend(args.skills_dir, args.output), ensure_ascii=False))
