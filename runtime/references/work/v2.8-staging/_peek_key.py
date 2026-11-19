"""Is the x-api-key in a file a placeholder or a real key? Prints the shape only (prefix 4 chars, length, char classes)."""
import re, sys
from pathlib import Path
t = Path(sys.argv[1]).read_text(encoding="utf-8", errors="ignore")
for m in re.finditer(r"(?i)x-api-key\s*:\s*([A-Za-z0-9_\-\$\{\}<>]+)", t):
    v = m.group(1)
    a = max(0, m.start() - 60)
    shape = "placeholder" if re.fullmatch(r"[A-Z_\$\{\}<>]+|YOUR.*|.*KEY.*", v) else "looks real"
    print(f"len={len(v)} prefix={v[:4]!r} upper_only={v.isupper()} digits={sum(c.isdigit() for c in v)} → {shape}")
    print("   before:", t[a:m.start()].replace("\n", " ")[-60:])
