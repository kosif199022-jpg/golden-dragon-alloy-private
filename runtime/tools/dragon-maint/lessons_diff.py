"""Which lessons learned on this laptop (~/.red-dragon/lessons.jsonl) are not in the repo's seed yet?
usage: python -X utf8 lessons_diff.py REPO [--write OUT.jsonl]
Read-only unless --write (then it writes the candidate rows to OUT.jsonl for review, never into the repo).
"""
import json
import re
import sys
from pathlib import Path

repo = Path(sys.argv[1])
seed_f = repo / "mind" / "lessons_seed.jsonl"
local_f = Path.home() / ".red-dragon" / "lessons.jsonl"


def rows(p):
    out = []
    if p.is_file():
        for ln in p.read_text(encoding="utf-8").splitlines():
            ln = ln.strip()
            if ln:
                try:
                    out.append(json.loads(ln))
                except ValueError:
                    pass
    return out


def key(t):
    return re.sub(r"\W+", " ", (t or "").lower()).strip()


seed, local = rows(seed_f), rows(local_f)
have = {key(r.get("text")) for r in seed}
ids = {r.get("id") for r in seed}
new = [r for r in local if key(r.get("text")) not in have]
print(f"seed {len(seed)} rows · local {len(local)} rows ({local_f}) · new {len(new)}")
SECRET = re.compile(r"(api[_-]?key|token|password|passwd|secret|cookie|bearer|sk-[A-Za-z0-9]{8,})", re.I)
for r in new:
    flag = " ⚠secret?" if SECRET.search(json.dumps(r, ensure_ascii=False)) else ""
    print(f"- [{r.get('id')}] ({r.get('domain')}, seen {r.get('seen', 1)}, src {r.get('src', '')}){flag}: {str(r.get('text'))[:230]}")
if "--write" in sys.argv:
    out = Path(sys.argv[sys.argv.index("--write") + 1])
    out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in new), encoding="utf-8")
    print("candidates ->", out, "| ids clash with seed:", sorted({r.get("id") for r in new} & ids))
