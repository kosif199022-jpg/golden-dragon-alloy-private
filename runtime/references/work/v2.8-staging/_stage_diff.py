"""staging vs installed: which files are new / changed (sha256), which staging files are excluded, and a secret scan of what would ship.
    python -I -X utf8 _stage_diff.py [--copy-list FILE]
"""
import hashlib, json, re, sys
from pathlib import Path

ST = Path(__file__).resolve().parent
INST = Path.home() / ".claude" / "skills" / "red-dragon"
PARTS = ["scripts", "mind", "references", "SKILL.md"]
EXCL_NAMES = {"__pycache__", "turns_all.json", "fresh_candidates.json", "proposals_dictation.json", "proposals_triggers.json", "wrappers_proposal.py"}


def excluded(rel):
    parts = rel.split("/")
    if any(p in EXCL_NAMES for p in parts):
        return True
    if rel.startswith("mind/route_eval/") and any(p.startswith("_") for p in parts[2:]):
        return True
    return False


SECRET = re.compile(r"(sk-ant-[A-Za-z0-9_\-]{10,}|sk-[A-Za-z0-9]{32,}|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|gho_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}"
                    r"|xox[bpas]-[A-Za-z0-9\-]{10,}|AIza[0-9A-Za-z_\-]{30,}|(?i:password|passwd|api[_-]?key|secret|token)\s*[:=]\s*[\"']?[A-Za-z0-9_\-\.]{12,})")


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


new, changed, same, excl = [], [], 0, []
for part in PARTS:
    base = ST / part
    files = [base] if base.is_file() else [f for f in base.rglob("*") if f.is_file()]
    for f in files:
        rel = f.relative_to(ST).as_posix()
        if excluded(rel):
            excl.append(rel)
            continue
        t = INST / rel
        if not t.is_file():
            new.append(rel)
        elif sha(t) != sha(f):
            changed.append(rel)
        else:
            same += 1
hits = []
for rel in new + changed:
    try:
        txt = (ST / rel).read_text(encoding="utf-8", errors="ignore")
    except OSError:
        continue
    for m in SECRET.finditer(txt):
        s = m.group(0)
        hits.append(f"{rel}: {s[:6]}…{s[-3:]} (len {len(s)})")
missing = []
for part in PARTS:
    base = INST / part
    files = [base] if base.is_file() else [f for f in base.rglob("*") if f.is_file()]
    for f in files:
        rel = f.relative_to(INST).as_posix()
        if "__pycache__" not in rel and not (ST / rel).exists():
            missing.append(rel)
print(json.dumps({"new": new, "changed": changed, "unchanged": same, "excluded_count": len(excl), "excluded": excl[:40],
                  "only_in_installed": missing[:30], "only_in_installed_count": len(missing), "secret_hits": hits}, ensure_ascii=False, indent=1))
if "--copy-list" in sys.argv:
    Path(sys.argv[sys.argv.index("--copy-list") + 1]).write_text("\n".join(new + changed), encoding="utf-8")
