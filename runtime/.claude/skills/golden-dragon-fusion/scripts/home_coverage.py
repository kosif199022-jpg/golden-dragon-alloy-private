"""Measure the text-search scope of the configured Golden Dragon home locations."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
from source_map import TEXT, SKIP


def scan(repo):
    catalog = json.loads((repo/"apps/golden-dragon/app/fusion/index.json").read_text(encoding="utf-8-sig"))
    resolved = []
    missing = []
    for name, options in catalog["homes"].items():
        for value in options:
            candidate = Path(os.path.expandvars(value)).expanduser()
            if candidate.exists():
                resolved.append(candidate.resolve())
                break
        else:
            missing.append(name)
    roots = []
    for path in sorted(set(resolved), key=lambda p:len(p.parts)):
        if not any(path.is_relative_to(parent) for parent in roots):
            roots.append(path)
    if not roots:
        raise ValueError("No registered home found")
    args = ["rg","--stats","--count","--threads","6","--max-filesize","4M","--hidden","--no-ignore"]
    for ext in sorted(TEXT):
        args += ["-g", "*"+ext]
    for folder in sorted(SKIP):
        args += ["-g","!**/"+folder+"/**"]
    args += ["-i",r"ffprobe|ffmpeg|storyboard|keyframe|subtitle|caption|worksheet|spreadsheet|reconcil|accessibility|acceptance.criteria|regression","--"]
    # Counts are kept locally; the portable report contains aggregates only.
    with subprocess.Popen(args+[str(p) for p in roots],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL) as proc:
        totals={}
        for raw in proc.stdout:
            match=re.fullmatch(rb"(\d+) (files searched|files contained matches|bytes searched)",raw.strip())
            if match:
                totals[match[2].decode()]=int(match[1])
        code=proc.wait()
    if len(totals)!=3:
        raise RuntimeError("Search ended without statistics")
    return {"registered_groups":len(catalog["homes"]),"resolved_groups":len(resolved),
            "unresolved_groups":missing,"distinct_roots_after_overlap":len(roots),
            "ripgrep_exit":code,"searches":totals["files searched"],
            "files_with_terms":totals["files contained matches"],"bytes_searched":totals["bytes searched"]}


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repo",type=Path)
    parser.add_argument("output",type=Path)
    args=parser.parse_args()
    result=scan(args.repo.resolve())
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),"utf-8")
    print(json.dumps(result))

