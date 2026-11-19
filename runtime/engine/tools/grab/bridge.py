#!/usr/bin/env python3
"""Black Dragon v10.16: guarded bridge to the bundled video-grabber skill.

    python scripts/dragon.py tool grab doctor
    python scripts/dragon.py tool grab plan "https://www.tiktok.com/@u/video/1"
    python scripts/dragon.py tool grab URL -o out --quality 1080 [--section 0:10-0:40] [--audio-only mp3]
    python scripts/dragon.py tool grab URL --proxy-file my_proxies.txt     (proxy rotation, user file only)
    python scripts/dragon.py tool grab ghost sniff URL --wait 15            (headless browser stream sniffer)
    python scripts/dragon.py tool grab proxies check --file my_proxies.txt

Anything that is not doctor/plan/ghost/proxies goes to skills/video-grabber/scripts/grab.py unchanged.
Complements `tool fetch` (simple, credited downloads): grab adds proxy rotation, ghost browser, clip ranges,
audio-only. Guards: proxies only from a user-supplied file (no URL proxies, Tor, free lists), no
self-update/installs, existing output files are never overwritten by the bridge, credentials are masked.
"""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import urllib.parse

ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / 'skills' / 'video-grabber'
GRAB = SKILL / 'scripts' / 'grab.py'
GHOST = SKILL / 'scripts' / 'ghost_browser.py'
POOL = SKILL / 'scripts' / 'proxy_pool.py'
SCHEMA = 'black-dragon.grab.v1'
MEDIA_EXT = {'.mp4', '.mov', '.webm', '.mkv', '.m4v', '.avi', '.mp3', '.m4a', '.wav', '.flac', '.ogg', '.aac', '.ts'}
FAMILIES = [
    ('youtube', ('youtube.com', 'youtu.be', 'youtube-nocookie.com')),
    ('tiktok', ('tiktok.com',)),
    ('instagram', ('instagram.com', 'instagr.am')),
    ('facebook', ('facebook.com', 'fb.watch', 'fb.com')),
    ('x', ('x.com', 'twitter.com', 't.co')),
    ('vimeo', ('vimeo.com',)),
]
FETCH_FAMILIES = {'youtube', 'tiktok', 'instagram', 'facebook', 'x', 'vimeo', 'direct'}


def jprint(obj):
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def mask(text):
    """Hide user:pass@ in anything URL-like before it is printed."""
    return re.sub(r'(://)[^@/\s]+@', r'\1***@', str(text))


def classify(url):
    p = urllib.parse.urlparse(url.strip())
    host = (p.hostname or '').lower()
    ext = Path(urllib.parse.unquote(p.path)).suffix.lower()
    if ext == '.m3u8':
        return 'm3u8'
    if ext == '.mpd':
        return 'mpd'
    for name, hosts in FAMILIES:
        if any(host == h or host.endswith('.' + h) for h in hosts):
            return name
    if ext in MEDIA_EXT:
        return 'direct'
    return 'other'


def plan(url, out='downloads', proxy_file=None):
    fam = classify(url)
    shown = mask(url)
    me = 'python scripts/dragon.py tool grab'
    steps = []
    if fam in FETCH_FAMILIES:
        steps.append({'tool': 'fetch', 'why': 'simple credited download (yt-dlp / aria2c), supported site',
                      'cmd': f'python scripts/dragon.py tool fetch "{shown}" --dir {out}'})
    steps.append({'tool': 'grab', 'why': 'yt-dlp + aria2c + ffmpeg, verified with ffprobe',
                  'cmd': f'{me} "{shown}" -o {out} --proxy none'})
    if fam not in ('m3u8', 'mpd', 'direct'):
        pf = proxy_file or 'MY_PROXIES.txt'
        steps.append({'tool': 'grab', 'why': 'on 403/429/geo-block: rotate proxies from YOUR file',
                      'cmd': f'{me} "{shown}" -o {out} --proxy auto --proxy-file {pf}'})
        steps.append({'tool': 'ghost', 'why': 'yt-dlp failed: sniff the real m3u8/mpd with the headless browser',
                      'cmd': f'{me} ghost sniff "{shown}" --wait 15'})
        steps.append({'tool': 'grab', 'why': 'download the stream the ghost browser found (or in one go)',
                      'cmd': f'{me} "{shown}" -o {out} --sniff --proxy none'})
    return {'schema': SCHEMA, 'url': shown, 'family': fam, 'network': False, 'steps': steps,
            'extras': {'clip': '--section 00:01:00-00:02:30', 'audio_only': '--audio-only mp3',
                       'compat_h264': '--compat'}}


def doctor():
    def exe(name):
        p = shutil.which(name)
        return {'found': bool(p), 'path': p}

    ytdlp = exe('yt-dlp')
    if not ytdlp['found'] and importlib.util.find_spec('yt_dlp'):
        ytdlp = {'found': True, 'path': 'python -m yt_dlp'}
    pw = bool(importlib.util.find_spec('playwright'))
    cands = []
    base = os.environ.get('PLAYWRIGHT_BROWSERS_PATH')
    if base and base != '0':
        cands.append(Path(base))
    if os.environ.get('LOCALAPPDATA'):
        cands.append(Path(os.environ['LOCALAPPDATA']) / 'ms-playwright')
    cands += [Path.home() / '.cache' / 'ms-playwright', Path.home() / 'Library' / 'Caches' / 'ms-playwright']
    found = []
    for c in cands:
        try:
            found += [d.name for d in c.glob('chromium*') if d.is_dir()]
        except OSError:
            pass
    return {'schema': SCHEMA, 'yt_dlp': ytdlp, 'aria2c': exe('aria2c'), 'ffmpeg': exe('ffmpeg'),
            'ffprobe': exe('ffprobe'), 'playwright_importable': pw,
            'chromium_installed': bool(found), 'chromium_dirs': sorted(set(found)),
            'skill_present': GRAB.is_file(),
            'hint': 'ghost browser needs: pip install playwright && playwright install chromium (not done by this tool)'}


def _no_overwrite(path):
    p = Path(path)
    if p.exists() or p.is_symlink():
        raise ValueError(f'refusing to overwrite existing file: {p.name}')


def _opt_values(args, name):
    vals = []
    for i, a in enumerate(args):
        if a == name and i + 1 < len(args):
            vals.append(args[i + 1])
        elif a.startswith(name + '='):
            vals.append(a.split('=', 1)[1])
    return vals


def _has(args, name):
    return any(a == name or a.startswith(name + '=') for a in args)


def guard_grab(args):
    for bad in ('--update', '--tor', '--free-proxies'):
        if _has(args, bad):
            raise ValueError(f'{bad} is blocked by the bridge (installs / non-user proxies)')
    for v in _opt_values(args, '--proxy'):
        if v not in ('none', 'auto'):
            raise ValueError('--proxy accepts only none|auto; put proxies in a file and use --proxy-file')
    for f in _opt_values(args, '--proxy-file') + _opt_values(args, '--batch'):
        if not Path(f).is_file():
            raise ValueError(f'file not found: {f}')
    out = list(args)
    if not _opt_values(args, '--proxy-file'):
        # without a user file, never let "auto" fall back to env/free pools
        if '--proxy' in out and out.index('--proxy') + 1 < len(out):
            out[out.index('--proxy') + 1] = 'none'
        elif not _has(out, '--proxy'):
            out += ['--proxy', 'none']
        else:
            out = [('--proxy=none' if a.startswith('--proxy=') else a) for a in out]
    return out


def guard_ghost(args):
    if not args:
        raise ValueError('ghost needs a command: sniff|text|shot|cookies|html')
    for bad in ('--free', '--tor'):
        if _has(args, bad):
            raise ValueError(f'{bad} is blocked by the bridge')
    for v in _opt_values(args, '--proxy'):
        if v != 'none':
            raise ValueError('ghost --proxy accepts only none via the bridge')
    cmd = args[0]
    pos = [a for a in args[1:] if not a.startswith('-')]
    if cmd in ('shot', 'cookies', 'html') and len(pos) >= 2:
        _no_overwrite(pos[1])
    for v in _opt_values(args, '--cookies-out'):
        _no_overwrite(v)
    return list(args)


def guard_pool(args):
    if not args:
        raise ValueError('proxies needs a command: check|ip')
    for bad in ('--free', '--tor'):
        if _has(args, bad):
            raise ValueError(f'{bad} is blocked by the bridge')
    if args[0] == 'newnym':
        raise ValueError('newnym (Tor) is blocked by the bridge')
    if args[0] == 'check':
        f = _opt_values(args, '--file')
        if not f or not Path(f[0]).is_file():
            raise ValueError('proxies check requires --file existing_proxies.txt')
        return list(args) + ['--no-env', '--no-cache']
    if args[0] == 'ip':
        for v in _opt_values(args, '--proxy'):
            if v != 'none':
                raise ValueError('ip accepts --proxy none only via the bridge')
    return list(args)


def run_py(script, args):
    if not script.is_file():
        print(f'missing {script}', file=sys.stderr)
        return 2
    env = dict(os.environ, PYTHONIOENCODING='utf-8')
    return subprocess.run([sys.executable, str(script), *args], env=env).returncode


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in ('-h', '--help', 'help'):
        print(__doc__)
        if GRAB.is_file():
            print('--- grab.py options (passthrough) ---')
            sys.stdout.flush()
            run_py(GRAB, ['--help'])
        return 0
    cmd = args[0]
    helping = bool({'-h', '--help'} & set(args[1:]))
    try:
        if cmd == 'doctor':
            jprint(doctor())
            return 0
        if cmd == 'plan':
            rest = args[1:]
            if helping or not rest:
                print('usage: tool grab plan URL [--out DIR] [--proxy-file FILE]   (offline, prints ordered commands)')
                return 0
            out, pf, url, i = 'downloads', None, None, 0
            while i < len(rest):
                if rest[i] in ('--out', '-o') and i + 1 < len(rest):
                    out = rest[i + 1]
                    i += 2
                elif rest[i] == '--proxy-file' and i + 1 < len(rest):
                    pf = rest[i + 1]
                    i += 2
                else:
                    url = url or rest[i]
                    i += 1
            jprint(plan(url, out, pf))
            return 0
        if cmd == 'ghost':
            return run_py(GHOST, args[1:] if helping else guard_ghost(args[1:]))
        if cmd == 'proxies':
            return run_py(POOL, args[1:] if helping else guard_pool(args[1:]))
        return run_py(GRAB, args if helping else guard_grab(args))
    except ValueError as e:
        print(json.dumps({'schema': SCHEMA, 'ok': False, 'error': mask(e)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
