"""fix_moved_paths.py — teaches the skills' code where the dragon folders live since 2026-11-15 (Desktop -> Desktop\\مهارات).

Additive and reversible: every edit ADDS the new «مهارات» location next to the old one (nothing that still works is
removed), is anchored on an exact text that must occur exactly once, keeps each file's BOM and newline style, and backs
the file up first to ~/.claude/skills_backup/2026-11-15-moved-paths/<same relative path>. Python files are compiled
after the edit and restored from the backup if they don't compile. Running it twice changes nothing.
The env vars BLACK_DRAGON_HOME / DRAGON_HOME already cover the code that reads them; this covers the hard-coded lists.

  python -X utf8 fix_moved_paths.py [--group main|red-dragon] [--dry-run]
"""
import json
import py_compile
import shutil
import sys
import time
from pathlib import Path

SK = Path.home() / ".claude" / "skills"
BACKUP = Path.home() / ".claude" / "skills_backup" / "2026-11-15-moved-paths"
MANIFEST = Path(__file__).resolve().parent.parent / "analysis" / "moved_paths_manifest.json"
MOVED = "# the folder moved into «مهارات» on 2026-11-15"

P = {
    "dragon_candidates": (
        '    HOME / "OneDrive" / "Desktop" / "التنين الأسود",\n    HOME / "Desktop" / "التنين الأسود",',
        '    HOME / "OneDrive" / "Desktop" / "التنين الأسود",\n    HOME / "OneDrive" / "Desktop" / "مهارات" / "التنين الأسود",   ' + MOVED +
        '\n    HOME / "Desktop" / "التنين الأسود",'),
    "fonts_candidates": (
        '    HOME / "OneDrive" / "Desktop" / "التنين الأسود",\n    HOME / ".claude" / "skills" / "black-dragon-cinema",',
        '    HOME / "OneDrive" / "Desktop" / "التنين الأسود",\n    HOME / "OneDrive" / "Desktop" / "مهارات" / "التنين الأسود",   ' + MOVED +
        '\n    HOME / ".claude" / "skills" / "black-dragon-cinema",'),
    "machine_src": (
        '(DESKTOP_APP_SRC, HOME / "OneDrive" / "Desktop" / "التنين الأسود" / "apps" / "dragon_desktop")',
        '(DESKTOP_APP_SRC, HOME / "OneDrive" / "Desktop" / "التنين الأسود" / "apps" / "dragon_desktop", '
        'HOME / "OneDrive" / "Desktop" / "مهارات" / "التنين الأسود" / "apps" / "dragon_desktop")'),
    "font_lab": (
        '    HOME / "OneDrive/Desktop/التنين الأسود/engines",',
        '    HOME / "OneDrive/Desktop/التنين الأسود/engines",\n    HOME / "OneDrive/Desktop/مهارات/التنين الأسود/engines",   ' + MOVED),
    "owner_check": (
        '(Path.home() / "OneDrive" / "Desktop" / "التنين الأسود").exists() or (Path.home() / "re-tools" / "retool.py").exists()',
        '(Path.home() / "OneDrive" / "Desktop" / "التنين الأسود").exists() or '
        '(Path.home() / "OneDrive" / "Desktop" / "مهارات" / "التنين الأسود").exists() or (Path.home() / "re-tools" / "retool.py").exists()'),
    "health_list": (
        '("تطبيق التنين (مصدر)", H / "OneDrive/Desktop/التنين الأسود/apps/dragon_desktop/app.py")',
        '("تطبيق التنين (مصدر)", next((p for p in (H / "OneDrive/Desktop/مهارات/التنين الأسود/apps/dragon_desktop/app.py", '
        'H / "OneDrive/Desktop/التنين الأسود/apps/dragon_desktop/app.py") if p.exists()), '
        'H / "OneDrive/Desktop/مهارات/التنين الأسود/apps/dragon_desktop/app.py"))'),
    "md_creative_studio": (
        r"from `C:\Users\cinde\OneDrive\Desktop\التنين الأسود`.",
        r"from `C:\Users\cinde\OneDrive\Desktop\مهارات\التنين الأسود` (or `%BLACK_DRAGON_HOME%`; the folder moved there on 2026-11-15)."),
    "md_kosif": (
        r"Run from `C:\Users\cinde\OneDrive\Desktop\التنين الأسود`:",
        r"Run from `C:\Users\cinde\OneDrive\Desktop\مهارات\التنين الأسود` (or `%BLACK_DRAGON_HOME%`):"),
    "md_black_dragon": (
        r"(`DRAGON_HOME`، `Desktop\التنين الأسود`، `~/kosif-own/black-dragon`)",
        r"(`DRAGON_HOME`، `Desktop\مهارات\التنين الأسود`، `Desktop\التنين الأسود`، `~/kosif-own/black-dragon`)"),
}

GROUPS = {
    "main": [
        ("black-dragon/scripts/dragon.py", ["dragon_candidates"]),
        ("white-dragon/engine/scripts/dragon.py", ["dragon_candidates"]),
        ("black-dragon/tools/fonts/fonts.py", ["fonts_candidates"]),
        ("white-dragon/engine/tools/fonts/fonts.py", ["fonts_candidates"]),
        ("black-dragon/tools/machine/machine.py", ["machine_src"]),
        ("white-dragon/engine/tools/machine/machine.py", ["machine_src"]),
        ("absolute-creativity/scripts/font_lab.py", ["font_lab"]),
        ("white-dragon/scripts/wd.py", ["owner_check", "health_list"]),
        ("creative-studio/SKILL.md", ["md_creative_studio"]),
        ("kosif-downloads/SKILL.md", ["md_kosif"]),
        ("black-dragon/SKILL.md", ["md_black_dragon"]),
    ],
    "red-dragon": [            # after the 2.14 update: same patterns in the Red Dragon and its engine copy
        ("red-dragon/scripts/rd.py", ["owner_check", "health_list"]),
        ("red-dragon/scripts/rd_chats.py", ["owner_check"]),
        ("red-dragon/engine/scripts/dragon.py", ["dragon_candidates"]),
        ("red-dragon/engine/tools/fonts/fonts.py", ["fonts_candidates"]),
        ("red-dragon/engine/tools/machine/machine.py", ["machine_src"]),
    ],
}


def load(p):
    raw = p.read_bytes()
    bom = raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8-sig")
    nl = "\r\n" if "\r\n" in text else "\n"
    return text, bom, nl


def save(p, text, bom):
    p.write_bytes((b"\xef\xbb\xbf" if bom else b"") + text.encode("utf-8"))


def main(argv):
    group = argv[argv.index("--group") + 1] if "--group" in argv else "main"
    dry = "--dry-run" in argv
    done, skipped, errors = [], [], []
    for rel, names in GROUPS[group]:
        f = SK / rel
        if not f.is_file():
            errors.append(f"{rel}: الملف مش موجود")
            continue
        text, bom, nl = load(f)
        new_text, changed = text, []
        for name in names:
            old, new = (s.replace("\n", nl) for s in P[name])
            if new in new_text:
                skipped.append(f"{rel}: {name} (اتعمل قبل كده)")
                continue
            n = new_text.count(old)
            if n != 1:
                errors.append(f"{rel}: {name}: المكان موجود {n}× (المتوقع 1)، ماتعدّلش")
                continue
            new_text = new_text.replace(old, new)
            changed.append(name)
        if not changed or dry:
            if changed:
                done.append({"file": rel, "patterns": changed, "dry_run": True})
            continue
        bak = BACKUP / rel
        bak.parent.mkdir(parents=True, exist_ok=True)
        if not bak.exists():
            shutil.copy2(f, bak)
        save(f, new_text, bom)
        if f.suffix == ".py":
            try:
                py_compile.compile(str(f), doraise=True, cfile=str(BACKUP / "_compile_check.pyc"))
            except py_compile.PyCompileError as e:
                shutil.copy2(bak, f)
                errors.append(f"{rel}: مااتترجمش بعد التعديل فرجع من النسخة الاحتياطية ({e.msg[:120]})")
                continue
        done.append({"file": rel, "patterns": changed, "backup": str(bak)})
    rec = json.loads(MANIFEST.read_text(encoding="utf-8")) if MANIFEST.exists() else {"runs": []}
    rec["runs"].append({"time": time.strftime("%Y-%m-%d %H:%M:%S"), "group": group, "dry_run": dry, "done": done,
                        "skipped": skipped, "errors": errors})
    if not dry:
        MANIFEST.write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
    for d in done:
        print("✓", d["file"], "←", ", ".join(d["patterns"]))
    for s in skipped:
        print("·", s)
    for e in errors:
        print("✗", e)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
