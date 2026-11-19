"""Build the release package: dist/minecraft-build-design-v<version>.zip (the skill folder at the zip root, as the
Claude apps, `npx skills` and manual installs expect) and dist/SHA256SUMS.txt.

usage: python .github/scripts/package.py [--check] [--tag vX.Y.Z] [--notes FILE]
  --check   build into a temporary folder and only report (CI on every push)
  --tag     fail unless the tag equals "v" + metadata.version in SKILL.md and CHANGELOG.md has that version
  --notes   also write that version's CHANGELOG section to FILE (release notes)

Only files tracked by git are packaged (fallback without git: every file), minus repository plumbing (.github,
.git*, dist) and caches. Timestamps are fixed so the same commit gives the same zip.
"""
import argparse, hashlib, re, subprocess, sys, tempfile, zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NAME = 'minecraft-build-design'
SKIP_TOP = {'.github', '.git', 'dist', '.gitignore', '.gitattributes'}
SKIP_ANY = {'__pycache__', 'node_modules', '.gradle', '.idea', '.vscode'}
STAMP = (2026, 1, 1, 0, 0, 0)
NOTES = """{section}

## Install

- **git**: `git clone https://github.com/yimeng-YM/minecraft-build-design ~/.claude/skills/minecraft-build-design`
  (or your agent's skills folder - see the README); update with `git pull`
- **skills CLI**: `npx skills add yimeng-YM/minecraft-build-design`
- **zip**: download `minecraft-build-design-v{ver}.zip` below, check it with `SHA256SUMS.txt`
  (`sha256sum -c SHA256SUMS.txt`, or `certutil -hashfile <zip> SHA256` on Windows), unzip into the skills folder

Then `python -m pip install -r <skills folder>/minecraft-build-design/scripts/requirements.txt` and
`python <skills folder>/minecraft-build-design/scripts/mcb.py selftest`.

NOT AN OFFICIAL MINECRAFT PRODUCT. NOT APPROVED BY OR ASSOCIATED WITH MOJANG OR MICROSOFT.
"""


def version():
    m = re.search(r'^\s*version:\s*"([^"]+)"', (ROOT / 'SKILL.md').read_text(encoding='utf-8'), re.M)
    if not m:
        sys.exit('SKILL.md has no metadata.version')
    return m.group(1)


def changelog_section(ver):
    text = (ROOT / 'CHANGELOG.md').read_text(encoding='utf-8')
    m = re.search(rf'^## \[{re.escape(ver)}\][^\n]*\n(.*?)(?=^## \[|^\[[^\]]+\]:)', text, re.M | re.S)
    return m.group(1).strip() if m else None


def files():
    try:
        out = subprocess.run(['git', 'ls-files', '-z'], cwd=ROOT, capture_output=True, check=True).stdout.decode('utf-8')
        paths = [ROOT / p for p in out.split('\0') if p]
    except (OSError, subprocess.CalledProcessError):
        paths = [p for p in ROOT.rglob('*') if p.is_file()]
    keep = []
    for p in sorted(paths):
        rel = p.relative_to(ROOT)
        if rel.parts[0] in SKIP_TOP or any(part in SKIP_ANY for part in rel.parts) or p.suffix == '.pyc' or not p.is_file():
            continue
        keep.append((p, rel))
    return keep


def build(out_dir):
    ver = version()
    out_dir.mkdir(parents=True, exist_ok=True)
    zpath = out_dir / f'{NAME}-v{ver}.zip'
    entries = files()
    with zipfile.ZipFile(zpath, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for p, rel in entries:
            info = zipfile.ZipInfo(f'{NAME}/{rel.as_posix()}', date_time=STAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            mode = 0o755 if p.name in ('gradlew', 'mcb.py') else 0o644
            info.external_attr = (0o100000 | mode) << 16
            z.writestr(info, p.read_bytes())
    digest = hashlib.sha256(zpath.read_bytes()).hexdigest()
    (out_dir / 'SHA256SUMS.txt').write_text(f'{digest}  {zpath.name}\n', encoding='utf-8')
    names = [rel.as_posix() for _, rel in entries]
    assert 'SKILL.md' in names, 'SKILL.md missing from the package'
    assert not any(n.startswith(('.github/', 'dist/')) for n in names)
    print(f'{zpath}  {len(entries)} files  {zpath.stat().st_size / 1e6:.2f} MB  sha256 {digest}')
    return zpath


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true')
    ap.add_argument('--tag')
    ap.add_argument('--notes')
    a = ap.parse_args()
    ver = version()
    section = changelog_section(ver)
    if a.tag and a.tag != f'v{ver}':
        sys.exit(f'tag {a.tag} does not match SKILL.md metadata.version {ver}')
    if section is None:
        sys.exit(f'CHANGELOG.md has no section for {ver}')
    if a.notes:
        Path(a.notes).write_text(NOTES.format(section=section, ver=ver), encoding='utf-8')
    if a.check:
        with tempfile.TemporaryDirectory() as d:
            build(Path(d))
    else:
        build(ROOT / 'dist')


if __name__ == '__main__':
    main()
