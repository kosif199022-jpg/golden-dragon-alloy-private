"""make_test_runner.py — writes ..\\tests\\run_tests.ps1 from the Golden Bird's runner (same logic, Golden Dragon names).
PowerShell 5.1 needs the UTF-8 BOM to read the Arabic lines, so the file is written as utf-8-sig.

  python -X utf8 make_test_runner.py
"""
from pathlib import Path

FORGE = Path(__file__).resolve().parent
SRC = FORGE.parent.parent / "الطائر الذهبي" / "tests" / "run_tests.ps1"
DST = FORGE.parent / "tests" / "run_tests.ps1"

t = SRC.read_text(encoding="utf-8-sig")
for old, new in (("الطائر الذهبي", "التنين الذهبي"), ("Golden Bird", "Golden Dragon"), ("make_golden_bird.py", "make_golden_dragon.py"),
                 ("gb_tests_", "gd_tests_")):
    if old not in t:
        raise SystemExit(f"✗ {old!r} not found in {SRC}")
    t = t.replace(old, new)
DST.write_text(t, encoding="utf-8-sig")
print(f"✓ {DST}")
