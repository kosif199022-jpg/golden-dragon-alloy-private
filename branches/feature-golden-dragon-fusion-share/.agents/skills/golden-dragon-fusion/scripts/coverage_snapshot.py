"""Rebuild a reproducible text-source coverage snapshot for the portable skill."""
import collections
import hashlib
import json
from pathlib import Path
import subprocess

from source_map import RULES, TEXT


def snapshot(repo):
    catalog = json.loads((repo/"apps/golden-dragon/app/fusion/index.json").read_text("utf-8-sig"))
    tracked = subprocess.check_output(["git", "-C", str(repo), "ls-files", "-z"]).decode().split("\0")
    paths = {repo/name: "repository" for name in tracked if name and "skills/golden-dragon-fusion/" not in name}
    for unit in catalog["units"]:
        if unit["kind"] == "skill" and unit.get("path"):
            paths[Path(unit["path"])] = "installed-skill"
    coverage = collections.Counter()
    support = collections.Counter()
    seen = set()
    for path, origin in paths.items():
        if path.suffix.lower() not in TEXT:
            coverage["other-format"] += 1
            continue
        try:
            data = path.read_bytes()
            body = data.decode("utf-8-sig").lower()
        except (OSError, UnicodeError):
            coverage["unreadable"] += 1
            continue
        coverage[origin] += 1
        digest = hashlib.sha256(data).digest()
        if digest in seen:
            continue
        seen.add(digest)
        normalized = body.replace("-", " ").replace("_", " ")
        for domain, (first, second, _) in RULES.items():
            if all(any(token.replace(".", " ") in normalized for token in group.split("|")) for group in (first, second)):
                support[domain] += 1
    lines = ["# Repository and installed skill coverage", "",
             "The snapshot counts UTF-8 source files and installed skill definitions. Each production check counts identical content once.", "",
             "| Scope | Files |", "| --- | ---: |"]
    lines.extend(f"| {k} | {v} |" for k, v in sorted(coverage.items()))
    lines.extend(["", f"Distinct readable texts: {len(seen)}.", "", "| Combined production check | Matching distinct texts |", "| --- | ---: |"])
    lines.extend(f"| {rule[2]} | {support[domain]} |" for domain, rule in RULES.items())
    return "\n".join(lines)+"\n"


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repository", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result = snapshot(args.repository.resolve())
    args.output.write_text(result, encoding="utf-8")
    print(result)
