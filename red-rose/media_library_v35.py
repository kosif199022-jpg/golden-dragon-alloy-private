"""Fetch a footage library that lives as a private GitHub Release asset, and register it for dua-reel.

  rose.py library list                                   registered libraries (~/.red-rose/libraries.json)
  rose.py library fetch dua --approve-write              download + unzip the 'dua' library from GitHub

Uses the `gh` CLI with the owner's login (the repository is private). Nothing is uploaded.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import zipfile
from pathlib import Path

LIBS = Path.home() / '.red-rose' / 'libraries.json'
REPO = 'kosif199022-jpg/golden-dragon-alloy-private'
KNOWN = {
    'dua': {'tag': 'dua-library-v1', 'asset': 'dua-library-v1.zip', 'folder': 'dua-library-v1',
            'about': '100 background clips (Quran, roses, incense, candles) from t.me/ijhbis, with _analysis.json'},
    'fonts': {'tag': 'fonts-library-v1', 'asset': 'fonts-library-v1.zip', 'folder': 'fonts-library-v1',
              'about': '1,076 unique Arabic-first fonts with licence files and library_index.json; indexed after fetch',
              'index_fonts': True},
}


def _load():
    return json.loads(LIBS.read_text(encoding='utf-8')) if LIBS.is_file() else {}


def listing():
    regs = _load()
    rows = []
    for name, info in KNOWN.items():
        path = regs.get(name)
        rows.append({'name': name, 'registered_at': path, 'present': bool(path and Path(path).is_dir()),
                     'release': f"{REPO}@{info['tag']}", 'about': info['about']})
    for name, path in regs.items():
        if name not in KNOWN:
            rows.append({'name': name, 'registered_at': path, 'present': Path(path).is_dir()})
    return {'ok': True, 'libraries': rows}


def fetch(name: str, dest=None, approve_write=False):
    if name not in KNOWN:
        raise ValueError(f'unknown library {name!r}; known: {sorted(KNOWN)}')
    info = KNOWN[name]
    dest = Path(dest).expanduser() if dest else Path.home() / '.red-rose' / 'libraries'
    target = dest / info['folder']
    if not approve_write:
        return {'ok': False, 'outcome': 'approval_required', 'would_write': [str(target), str(LIBS)],
                'download': f"{REPO} release {info['tag']} / {info['asset']}"}
    if not shutil.which('gh'):
        return {'ok': False, 'outcome': 'unavailable_here', 'error': 'gh (GitHub CLI) is not installed or not logged in'}
    dest.mkdir(parents=True, exist_ok=True)
    zpath = dest / info['asset']
    run = subprocess.run(['gh', 'release', 'download', info['tag'], '--repo', REPO, '--pattern', info['asset'],
                          '--dir', str(dest), '--clobber'], capture_output=True, text=True)
    if run.returncode != 0 or not zpath.is_file():
        return {'ok': False, 'outcome': 'error', 'error': (run.stderr or 'download failed')[-400:]}
    with zipfile.ZipFile(zpath) as z:
        bad = [n for n in z.namelist() if n.startswith('/') or '..' in Path(n).parts]
        if bad:
            return {'ok': False, 'outcome': 'error', 'error': f'unsafe paths in zip: {bad[:3]}'}
        z.extractall(dest)
    zpath.unlink()
    regs = _load()
    regs[name] = str(target)
    LIBS.parent.mkdir(parents=True, exist_ok=True)
    LIBS.write_text(json.dumps(regs, ensure_ascii=False, indent=1), encoding='utf-8')
    res = {'ok': True, 'saved': [str(target)], 'registered': name}
    if info.get('index_fonts'):
        import font_library_v35 as fl
        res['fonts'] = fl.scan([str(target)], approve_write=True)
    else:
        res['clips'] = len(list((target / 'videos').glob('*.mp4')))
    return res
