"""Count files that still contain a leaked key or login (prints only paths + counts, never the text).
    python -I -X utf8 _count_secret.py ROOT...
"""
import re, sys
from pathlib import Path

PATS = {"phone-login": re.compile(r"(?<!\d)00\d{9}(?!\d)"), "user-name": re.compile(r"(?i)user\s?name\s*[:=]\s*\S+"),
        "password": re.compile(r"(?i)pass(word|wd)\s*[:=]\s*\S{4,}"),
        "anthropic-key": re.compile(r"sk-ant-[A-Za-z0-9_\-]{10,}"), "api-key-hdr": re.compile(r"(?i)x-api-key\s*:\s*[A-Za-z0-9_\-]{12,}")}
for root in (Path(p) for p in sys.argv[1:]):
    found = 0
    for f in root.rglob("*"):
        if not f.is_file() or f.stat().st_size > 30_000_000 or f.suffix.lower() in (".png", ".jpg", ".mp4", ".zip", ".pyc", ".ttf", ".otf", ".woff2", ".exe", ".dll"):
            continue
        if f.name in ("_count_secret.py", "_redact.py", "_stage_diff.py", "_peek_key.py"):
            continue
        try:
            t = f.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        c = {k: len(rx.findall(t)) for k, rx in PATS.items()}
        c = {k: v for k, v in c.items() if v}
        if c:
            found += 1
            print(f"  {f.relative_to(root).as_posix()}: {c}")
    print(f"== {root}: {found} file(s)")
