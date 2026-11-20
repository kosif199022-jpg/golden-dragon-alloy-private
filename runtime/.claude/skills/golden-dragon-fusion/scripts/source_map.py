"""Build a local source map and trace cross-domain production methods to files."""
import argparse
import collections
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

TEXT = set(".md .rst .txt .py .json .yaml .yml .toml .js .mjs .ts .tsx .html .css .sh .ps1 .csv .c .cpp .h .xml .svg .rs .go".split())
SKIP = {".git", "node_modules", ".venv", "__pycache__", ".cache"}
RULES = {
    "media": (r"ffmpeg|ffprobe", r"frame.rate|aspect.ratio|pixel.format", "Probe the input, choose export dimensions and timing, then measure the encoded stream."),
    "motion": (r"keyframe|storyboard", r"timeline|duration|easing", "Translate shots into timed states and verify transitions on the final timeline."),
    "captions": (r"subtitle|caption", r"timestamp|word.level|right.to.left", "Align words with speech and inspect the final rendered line in its target language."),
    "data": (r"spreadsheet|worksheet|reconcil", r"column|balance|formula", "Preserve row identifiers, reconcile totals, and verify calculated fields after export."),
    "design": (r"component|layout", r"contrast|accessibility|responsive", "Test layout, legibility and accessible controls at the requested display size."),
    "verification": (r"test.case|regression|acceptance.criteria", r"fixture|assert|expected", "Exercise the normal entry point with a known input and compare the observed output with the expected result."),
}
PATTERNS = {k:(re.compile(a,re.I),re.compile(b,re.I)) for k,(a,b,_) in RULES.items()}


def build(repo):
    catalog = json.loads((repo/"apps/golden-dragon/app/fusion/index.json").read_text("utf-8-sig"))
    files = {}
    counts = collections.Counter()
    def add(path, label):
        if path.is_symlink() or path.is_junction():
            return
        files.setdefault(path.resolve(), label)
    tracked = subprocess.check_output(["git","-C",str(repo),"ls-files","-z"]).decode().split("\0")
    for name in filter(None, tracked):
        if "skills/golden-dragon-fusion/" not in name:
            add(repo/name, "repo/"+name)
    roots = {}
    for unit in catalog["units"]:
        if unit.get("path"):
            p = Path(unit["path"])
            if unit["kind"]=="skill" and p.is_file():
                p=p.parent
            roots.setdefault(p,unit["id"])
    for label, alternatives in catalog["homes"].items():
        for candidate in alternatives:
            p=Path(os.path.expandvars(candidate)).expanduser()
            if p.exists():
                roots.setdefault(p,label)
                break
        else:
            counts["unresolved_home_groups"]+=1
    for root,label in roots.items():
        if root.is_file():
            add(root,label+"/"+root.name)
        elif root.is_dir():
            for parent,dirs,names in os.walk(root):
                dirs[:]=[d for d in dirs if d not in SKIP and not (Path(parent)/d).is_junction() and not (Path(parent)/d).is_symlink()]
                for name in names:
                    path=Path(parent)/name
                    add(path,label+"/"+path.relative_to(root).as_posix())
        else:
            counts["missing_paths"]+=1
    evidence=collections.defaultdict(list)
    urls=set()
    seen=set()
    for path,label in files.items():
        if path.suffix.lower() not in TEXT:
            counts["other_format"]+=1
            continue
        try:
            if path.stat().st_size>4_000_000:
                counts["over_size_limit"]+=1
                continue
            data=path.read_bytes()
            digest=hashlib.sha256(data).hexdigest()
            if digest in seen:
                counts["duplicate_content"]+=1
                continue
            seen.add(digest)
            body=data.decode("utf-8-sig")
        except (OSError,UnicodeError):
            counts["unreadable"]+=1
            continue
        counts["unique_texts"]+=1
        urls.update(re.findall(r"https?://[^\s<>\"()]+",body,re.I))
        for k,(a,b) in PATTERNS.items():
            if a.search(body) and b.search(body):
                evidence[k].append(label)
    counts["url_strings_discovered"]=len(urls)
    counts["catalog_entries"]=len(catalog["units"])
    return dict(counts),dict(evidence)


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("repository",type=Path)
    parser.add_argument("local_evidence",type=Path)
    parser.add_argument("brief",type=Path)
    args=parser.parse_args()
    counts,evidence=build(args.repository.resolve())
    args.local_evidence.write_text(json.dumps({"counts":counts,"sources":evidence},ensure_ascii=False),"utf-8")
    lines=["# Methods found across repository and linked local sources","", "Apply the relevant methods in dependency order. Source counts measure textual matches, not successful executions.",""]
    for k,paths in evidence.items():
        lines.append("- "+RULES[k][2]+" Matching source texts: "+str(len(paths))+".")
    args.brief.write_text("\n".join(lines)+"\n","utf-8")
    print(json.dumps(counts))
