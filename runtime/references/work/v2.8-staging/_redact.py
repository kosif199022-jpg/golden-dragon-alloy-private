"""Find (and with --apply, mask) secrets in every staging text file. Never prints a secret: only file, row and a masked preview."""
import json, re, sys
from pathlib import Path

ST = Path(__file__).resolve().parent
APPLY = "--apply" in sys.argv
SECRET = re.compile(r"(sk-ant-[A-Za-z0-9_\-]{10,}|sk-[A-Za-z0-9]{32,}|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|gho_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}"
                    r"|xox[bpas]-[A-Za-z0-9\-]{10,}|AIza[0-9A-Za-z_\-]{30,}|(?i:password|passwd|api[_-]?key|secret|token)\s*[:=]\s*[\"']?[A-Za-z0-9_\-\.]{12,})")
SECRET = re.compile(SECRET.pattern + r"|(?i:user\s?name)\s*[:=]\s*[^\s\"\\\],]+|(?<!\d)00\d{9}(?!\d)")     # + the login name / phone number next to a password
MASK = "«سر مخفي»"
total = 0
for f in sorted(ST.rglob("*")):
    if not f.is_file() or f.suffix.lower() not in (".json", ".jsonl", ".md", ".py", ".txt", ".tsv") or "__pycache__" in f.parts:
        continue
    if f.name == "_redact.py" or f.name == "_stage_diff.py":
        continue
    txt = f.read_text(encoding="utf-8", errors="ignore")
    ms = list(SECRET.finditer(txt))
    if not ms:
        continue
    total += len(ms)
    for m in ms:
        a, b = max(0, m.start() - 50), min(len(txt), m.end() + 30)
        ctx = (txt[a:m.start()] + MASK + txt[m.end():b]).replace("\n", " ")
        print(f"{f.relative_to(ST).as_posix()} @{m.start()}: …{ctx}…")
    if APPLY:
        new = SECRET.sub(MASK, txt)
        if f.suffix.lower() in (".json",):
            json.loads(new)          # the file must stay valid JSON
        elif f.suffix.lower() == ".jsonl":
            [json.loads(ln) for ln in new.splitlines() if ln.strip()]
        f.write_text(new, encoding="utf-8")
print(f"{'masked' if APPLY else 'found'}: {total}")
