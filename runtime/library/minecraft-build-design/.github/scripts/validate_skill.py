"""Validate the skill against the Agent Skills specification (https://agentskills.io/specification):
name (1-64 chars, a-z 0-9 and single hyphens, equal to the folder name), description (1-1024 chars, no angle
brackets), compatibility (<= 500), metadata (string -> string), body length, and relative links that must exist.

usage: python .github/scripts/validate_skill.py [skill_dir]      (needs PyYAML)
"""
import re, sys
from pathlib import Path
import yaml

d = Path(sys.argv[1] if len(sys.argv) > 1 else '.').resolve()
text = (d / 'SKILL.md').read_text(encoding='utf-8')
m = re.match(r'^---\r?\n(.*?)\r?\n---\r?\n(.*)$', text, re.S)
if not m:
    sys.exit('SKILL.md: no YAML frontmatter')
fm, body = yaml.safe_load(m.group(1)), m.group(2)
errors = []
allowed = {'name', 'description', 'license', 'compatibility', 'metadata', 'allowed-tools'}
if set(fm) - allowed:
    errors.append(f'unknown frontmatter keys: {sorted(set(fm) - allowed)}')
name = fm.get('name', '')
if not (1 <= len(name) <= 64 and re.fullmatch(r'[a-z0-9]+(-[a-z0-9]+)*', name)):
    errors.append(f'bad name {name!r}')
if name != d.name:
    errors.append(f'name {name!r} differs from the folder name {d.name!r}')
desc = fm.get('description', '')
if not (1 <= len(desc) <= 1024):
    errors.append(f'description has {len(desc)} characters (1-1024)')
if '<' in desc or '>' in desc:
    errors.append('description contains angle brackets')
comp = fm.get('compatibility')
if comp is not None and not (1 <= len(comp) <= 500):
    errors.append(f'compatibility has {len(comp)} characters (1-500)')
md = fm.get('metadata', {}) or {}
if not all(isinstance(k, str) and isinstance(v, str) for k, v in md.items()):
    errors.append('metadata must map strings to strings')
lines = body.count('\n')
if lines > 500:
    errors.append(f'SKILL.md body has {lines} lines (> 500)')
nested = [p for p in d.rglob('SKILL.md') if p != d / 'SKILL.md' and '.git' not in p.parts]
if nested:
    errors.append(f'more than one SKILL.md: {nested}')
for f in [d / 'SKILL.md', d / 'README.md', d / 'README.zh-CN.md', *sorted((d / 'references').glob('*.md'))]:
    if not f.exists():
        continue
    for link in re.findall(r'\]\(([^)#\s]+)(?:#[^)]*)?\)', f.read_text(encoding='utf-8')):
        if '://' in link or link.startswith('mailto:'):
            continue
        if not (f.parent / link).exists() and not (d / link).exists():
            errors.append(f'{f.relative_to(d)}: broken link {link}')
print(f'{name}: description {len(desc)} chars, compatibility {len(comp or "")} chars, body {lines} lines, '
      f'version {md.get("version", "?")}')
if errors:
    print('ERRORS:\n  ' + '\n  '.join(errors))
    sys.exit(1)
print('OK')
