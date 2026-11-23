"""Fetch a footage library that lives as a private GitHub Release asset, and register it for dua-reel.

  rose.py library list                                   registered libraries (~/.red-rose/libraries.json)
  rose.py library fetch dua --approve-write              download + unzip the 'dua' library from GitHub
  rose.py library fetch pins --approve-write             602 Pinterest clips in the dua-reel look (6 zip packs, ~1.3 GB)

GitHub libraries use the `gh` CLI with the owner's login (the repository is private).
URL libraries ('pins') download plain HTTPS packs with urllib; their catalogue (Pinterest link per
clip, size, search phrase) ships in agent/pins_catalog.csv. Nothing is uploaded.
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
    'pins': {'folder': 'pins-library-v1', 'catalog': 'agent/pins_catalog.csv',
             'about': '602 vertical Pinterest clips found by searching the @oaun.11 look (roses, Quran, incense, '
                      'candles, home decor); links per clip in agent/pins_catalog.csv; for private editing use',
             'urls': [
                 'https://d2ol7oe51mr4n9.cloudfront.net/user_36qP6wVjfYmaRqhniKJVy5dJHoh/88f8b653-6fdc-4d04-b6cb-b88b16cf9e27.zip',
                 'https://d2ol7oe51mr4n9.cloudfront.net/user_36qP6wVjfYmaRqhniKJVy5dJHoh/a905323f-e560-487d-941c-01805e0c3fe8.zip',
                 'https://d2ol7oe51mr4n9.cloudfront.net/user_36qP6wVjfYmaRqhniKJVy5dJHoh/d2f539cb-6fc9-41e0-bb6e-777045ac7c0b.zip',
                 'https://d2ol7oe51mr4n9.cloudfront.net/user_36qP6wVjfYmaRqhniKJVy5dJHoh/7cae15d5-b2bc-45c3-b8c7-c85bdc59558b.zip',
                 'https://d2ol7oe51mr4n9.cloudfront.net/user_36qP6wVjfYmaRqhniKJVy5dJHoh/22721833-a588-47a5-8114-fce53929c5bc.zip',
                 'https://d2ol7oe51mr4n9.cloudfront.net/user_36qP6wVjfYmaRqhniKJVy5dJHoh/95c078a5-030d-45e9-b3fc-be51c751c6d2.zip',
             ]},
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
                     'release': f"{REPO}@{info['tag']}" if 'tag' in info else f"{len(info['urls'])} HTTPS packs",
                     'about': info['about']})
    for name, path in regs.items():
        if name not in KNOWN:
            rows.append({'name': name, 'registered_at': path, 'present': Path(path).is_dir()})
    return {'ok': True, 'libraries': rows}


def _safe_extract(zpath, into):
    with zipfile.ZipFile(zpath) as z:
        bad = [n for n in z.namelist() if n.startswith('/') or '..' in Path(n).parts]
        if bad:
            raise ValueError(f'unsafe paths in zip: {bad[:3]}')
        z.extractall(into)


def _fetch_urls(name, info, dest, target):
    """Download each pack, unzip into target/videos, copy the catalogue next to it, register."""
    import urllib.request
    vids = target / 'videos'
    vids.mkdir(parents=True, exist_ok=True)
    got = []
    for k, url in enumerate(info['urls'], 1):
        zpath = dest / f'{name}-pack{k}.zip'
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'red-rose'})
            with urllib.request.urlopen(req, timeout=120) as r, open(zpath, 'wb') as fh:
                shutil.copyfileobj(r, fh, 1 << 20)
            _safe_extract(zpath, vids)
        except Exception as e:  # report which pack failed; packs already unzipped stay
            return {'ok': False, 'outcome': 'error', 'error': f'pack {k}: {e}', 'packs_done': got}
        finally:
            if zpath.exists():
                zpath.unlink()
        got.append(k)
    cat = Path(__file__).resolve().parent / info['catalog']
    if cat.is_file():
        shutil.copy2(cat, target / cat.name)
    regs = _load()
    regs[name] = str(target)
    LIBS.parent.mkdir(parents=True, exist_ok=True)
    LIBS.write_text(json.dumps(regs, ensure_ascii=False, indent=1), encoding='utf-8')
    return {'ok': True, 'saved': [str(target)], 'registered': name, 'packs': got,
            'clips': len(list(vids.glob('*.mp4')))}


def fetch(name: str, dest=None, approve_write=False):
    if name not in KNOWN:
        raise ValueError(f'unknown library {name!r}; known: {sorted(KNOWN)}')
    info = KNOWN[name]
    dest = Path(dest).expanduser() if dest else Path.home() / '.red-rose' / 'libraries'
    target = dest / info['folder']
    if not approve_write:
        return {'ok': False, 'outcome': 'approval_required', 'would_write': [str(target), str(LIBS)],
                'download': (f"{REPO} release {info['tag']} / {info['asset']}" if 'tag' in info
                             else f"{len(info['urls'])} zip packs over HTTPS")}
    if 'urls' in info:
        return _fetch_urls(name, info, dest, target)
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
