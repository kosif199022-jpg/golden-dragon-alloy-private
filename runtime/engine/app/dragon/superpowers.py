"""Superpowers bridge (v10.13): find the freshest local kosif-superpowers checkout and hand off to its hub.

This module never imports or executes repository code and never runs shell commands. Live calls into
hub.py (find / doctor / tool / run) live in tools/superpowers/sp.py (`dragon.py tool sp ...`).

v10.13 fix: the owner's PC has two checkouts (~/kosif-tool, current; ~/kosif-own/kosif-tool, older).
v10.0-v10.12 only looked at the older one. Now every known place is checked and the freshest wins,
unless DRAGON_SUPERPOWERS_ROOT names one explicitly.
"""
import os
import sys
from pathlib import Path

SUB = Path('.claude') / 'skills' / 'kosif-superpowers'
FRESHNESS_FILES = ('manifest.json', 'data/tools.json', 'SKILL.md', 'scripts/hub.py')


def candidates() -> list[Path]:
    """Every place a kosif-superpowers skill may live, explicit override first."""
    env = os.environ.get('DRAGON_SUPERPOWERS_ROOT', '').strip()
    home = Path.home()
    roots = ([Path(env)] if env else []) + [
        home/'kosif-tool'/SUB,
        home/'kosif-own'/'kosif-tool'/SUB,
        home/'.claude'/'skills'/'kosif-superpowers',
    ]
    return list(dict.fromkeys(p.expanduser() for p in roots))


def git_time(root: Path) -> float:
    """Time of the checkout's last HEAD move (commit, merge, pull), read from .git/logs/HEAD; 0 if unknown.
    File mtimes are not enough: a fresh clone of an old commit has newer mtimes than an updated checkout."""
    import re
    try:
        last = (repo_of(root)/'.git'/'logs'/'HEAD').read_text(encoding='utf-8', errors='replace').strip().splitlines()[-1]
    except (OSError, IndexError):
        return 0.0
    m = re.search(r'>\s+(\d{9,})\s+[+-]\d{4}', last)
    return float(m.group(1)) if m else 0.0


def freshness(root: Path) -> float:
    """git HEAD time when known, else the newest mtime of the files that change on a rebuild (0 when absent)."""
    g = git_time(root)
    if g:
        return g
    best = 0.0
    for rel in FRESHNESS_FILES:
        try:
            best = max(best, (Path(root)/rel).stat().st_mtime)
        except OSError:
            pass
    return best


def survey(roots: list[Path] | None = None) -> list[dict]:
    """All candidate roots with presence and freshness, explicit override marked."""
    env = os.environ.get('DRAGON_SUPERPOWERS_ROOT', '').strip()
    rows = []
    for p in (roots if roots is not None else candidates()):
        ok = (p/'SKILL.md').is_file() and (p/'scripts'/'hub.py').is_file()
        rows.append({'path': str(p), 'present': ok, 'freshness': freshness(p) if ok else 0.0,
                     'explicit': bool(env) and Path(env).expanduser() == p})
    return rows


def pick(roots: list[Path] | None = None) -> Path | None:
    """The explicit root when it is valid, else the freshest valid root."""
    rows = [r for r in survey(roots) if r['present']]
    if not rows:
        return None
    explicit = [r for r in rows if r['explicit']]
    best = explicit[0] if explicit else max(rows, key=lambda r: r['freshness'])
    return Path(best['path'])


def repo_of(root: Path) -> Path:
    """kosif-tool repo folder for a skill root (.../kosif-tool/.claude/skills/kosif-superpowers)."""
    root = Path(root)
    return root.parents[2] if root.parts[-3:] == SUB.parts else root


def bridge(query: str, full: bool = False, root: Path | None = None) -> dict:
    """Prepare exact commands (absolute paths, this Python) without running any of them."""
    roots = [Path(root)] if root is not None else candidates()
    valid = pick(roots)
    if valid is None:
        return {
            'connected_locally': False, 'repository': 'kosif199022-jpg/kosif-tool',
            'integration_mode': 'documentation_only', 'executed': False,
            'searched': [str(p) for p in roots],
            'missing': ['local kosif-superpowers/SKILL.md + scripts/hub.py'],
            'steps': [
                'Use the bundled indexed catalog as historical metadata, not as proof of local tools.',
                'Clone or connect kosif-tool only after approval, then set DRAGON_SUPERPOWERS_ROOT.',
            ],
        }
    py, q = sys.executable, query.replace('"', "'")
    cmds = []
    for f, args, purpose in [
        ('scripts/skill_loader.py', 'full' if full else f'need "{q}" --json',
         'Load only relevant skill ranges, or the full matching protocol on request'),
        ('scripts/hub.py', f'find "{q}" --json', 'Ranked tools (readiness + first command), powers and guides'),
        ('scripts/hub.py', 'doctor --json', 'Which of the 212 tools run on this machine now'),
        ('scripts/think.py', f'ladder "{q}"', 'Structured independent reasoning'),
    ]:
        if (valid/f).is_file():
            cmds.append({'purpose': purpose, 'command': f'"{py}" "{valid/f}" {args}',
                         'command_template': f'python {f} {args}',  # v10.0 field, kept for callers
                         'available_locally': True, 'run': False, 'file': str(valid/f)})
    others = [r['path'] for r in survey() if r['present'] and Path(r['path']) != valid] if root is None else []
    return {'connected_locally': True, 'repository': 'kosif199022-jpg/kosif-tool',
            'integration_mode': 'read_only_handoff', 'root': str(valid), 'executed': False,
            'other_checkouts': others, 'full_power_requested': full, 'steps': cmds,
            'live': 'python scripts/dragon.py tool sp find "<request>"  (runs hub.py find, read-only)',
            'policy': 'Read LOADER first; match relevant appendices; verify evidence; get approval before '
                      'install, spend, push or publish. hub.py run gates consent tools behind --yes.'}
