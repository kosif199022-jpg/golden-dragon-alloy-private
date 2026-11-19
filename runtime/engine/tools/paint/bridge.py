#!/usr/bin/env python3
"""Black Dragon v10.16: Paint Studio front door (the owner's paint-studio skill, bundled verbatim).

Examples:
    python scripts/dragon.py tool paint doctor
    python scripts/dragon.py tool paint ops
    python scripts/dragon.py tool paint new out/canvas.png --size 1152x648 --bg white
    python scripts/dragon.py tool paint draw out/canvas.png out/card.png --ops ops.json
    python scripts/dragon.py tool paint draw proj.dpaint proj.dpaint --op "{\\"op\\":\\"rectangle\\",\\"box\\":[10,10,200,120]}"
    python scripts/dragon.py tool paint export proj.dpaint out/final.png
    python scripts/dragon.py tool paint preview out/card.png out/prev.png --zoom 3 --grid 10 --rulers
    python scripts/dragon.py tool paint info IN | pick IN X Y | gui [IN]
    python scripts/dragon.py tool paint print IN --yes          (sends to the printer: ask the owner first)
    python scripts/dragon.py tool paint wallpaper IN --yes      (changes the desktop: ask the owner first)
    python scripts/dragon.py tool paint ai create out/img.png --prompt "..." --steps 1   (local SD-Turbo venv)

Engine: skills/paint-studio/scripts/paint.py (system Python: Pillow/NumPy/OpenCV, rembg optional).
AI:     skills/paint-studio/scripts/paint_ai.py run with the toon venv python
        (%USERPROFILE%\\dragon-models\\toon\\venv\\Scripts\\python.exe, override BD_TOON_VENV_PY).

Guards (the bundled scripts are not modified):
  * never overwrites an existing output file; the only exception is paint.py's own
    project editing, `draw X.dpaint X.dpaint` (same .dpaint as input and output);
  * writes only to the output path you name (AI --n N writes OUT_1..OUT_N; all are checked);
  * no network: rembg ops run only when a model is already on disk, AI runs with HF offline flags,
    nothing is installed;
  * print / wallpaper change things outside the canvas and need --yes;
  * Arabic / non-ASCII paths: paint.py reads and writes through Pillow/zipfile (Unicode-safe);
    OpenCV is used only on in-memory arrays (no cv2.imread/imwrite), and child output is forced to UTF-8.
Exit codes: 0 ok, 2 refused/bad input/missing venv, 3 needs --yes, otherwise the engine's own code.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
SKILL_DIR = ROOT / 'skills' / 'paint-studio'
PAINT = SKILL_DIR / 'scripts' / 'paint.py'
PAINT_AI = SKILL_DIR / 'scripts' / 'paint_ai.py'
SOURCE_JSON = SKILL_DIR / 'SOURCE_PAINT_STUDIO.json'
SCHEMA = 'black-dragon.paint.v1'

PAINT_CMDS = {'new', 'info', 'draw', 'export', 'preview', 'pick', 'ops', 'gui', 'print', 'wallpaper'}
AI_CMDS = {'create', 'cocreator', 'reimagine', 'fill', 'erase', 'sticker', 'coloring', 'styles'}
OUT_EXT = {'.png', '.jpg', '.jpeg', '.jpe', '.jfif', '.webp', '.avif', '.heic', '.heif', '.bmp', '.dib',
           '.gif', '.tif', '.tiff', '.ico', '.dpaint'}
REMBG_OPS = {'remove_background', 'blur_background'}
OFFLINE_ENV = {'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1', 'HF_DATASETS_OFFLINE': '1',
               'DIFFUSERS_OFFLINE': '1', 'HF_HUB_DISABLE_TELEMETRY': '1'}


class Refused(Exception):
    pass


def _utf8_stdio():
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            pass


def json_print(obj):
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def home():
    return Path(os.environ.get('USERPROFILE') or Path.home())


def venv_python():
    override = os.environ.get('BD_TOON_VENV_PY')
    if override:
        return Path(override), True
    return home() / 'dragon-models' / 'toon' / 'venv' / 'Scripts' / 'python.exe', False


def sd_model_dir():
    return Path(os.environ.get('PAINT_SD_MODEL') or (Path.home() / 'dragon-models' / 'toon' / 'sd-turbo'))


def rembg_model_on_disk():
    """Mirror of paint.py's _find_rembg_model, but only reports what is already on disk."""
    homes = [os.environ.get('U2NET_HOME'), str(Path.home() / '.u2net'),
             str(Path.home() / '.rembg' / 'models' / 'u2net')]
    for h in [x for x in homes if x]:
        for name in ('isnet-general-use', 'u2net', 'silueta'):
            f = Path(h) / f'{name}.onnx'
            if f.exists() and not Path(str(f) + '.aria2').exists() and f.stat().st_size > 1_000_000:
                return str(f)
    return None


def find_mspaint():
    p = shutil.which('mspaint')
    if p:
        return p
    for c in (Path(os.environ.get('LOCALAPPDATA', '')) / 'Microsoft' / 'WindowsApps' / 'mspaint.exe',
              Path(os.environ.get('WINDIR', r'C:\Windows')) / 'System32' / 'mspaint.exe'):
        if str(c) and c.exists():
            return str(c)
    return None


def child_env(extra=None):
    env = dict(os.environ, PYTHONIOENCODING='utf-8', PYTHONUTF8='1')
    env.update(OFFLINE_ENV)
    env.update(extra or {})
    return env


def _mask(p):
    s = str(p)
    h = str(home())
    return s.replace(h, '%USERPROFILE%') if h and s.lower().startswith(h.lower()) else s


# ───────────────────────────── doctor ─────────────────────────────
def doctor():
    def mod(name):
        return importlib.util.find_spec(name) is not None

    pillow = {'available': mod('PIL')}
    if pillow['available']:
        try:
            import PIL
            from PIL import features
            pillow.update(version=PIL.__version__, raqm_arabic_shaping=bool(features.check_feature('raqm')))
        except Exception as e:
            pillow['error'] = str(e)[:200]
    cv = {'available': mod('cv2')}
    if cv['available']:
        try:
            from importlib.metadata import version
            cv['version'] = next((version(d) for d in ('opencv-python', 'opencv-python-headless',
                                                       'opencv-contrib-python') if _has_dist(d)), None)
        except Exception:
            pass
    model = rembg_model_on_disk()
    vpy, overridden = venv_python()
    hashes = check_hashes()
    mspaint = find_mspaint()
    ready = pillow['available'] and mod('numpy') and PAINT.is_file() and hashes['ok']
    return {
        'schema': SCHEMA, 'ok': True, 'ready': bool(ready),
        'skill_dir': str(SKILL_DIR.relative_to(ROOT)).replace('\\', '/'),
        'scripts_present': {'paint.py': PAINT.is_file(), 'paint_ai.py': PAINT_AI.is_file()},
        'source_hashes_match': hashes['ok'], 'hash_errors': hashes['errors'],
        'pillow': pillow, 'numpy': mod('numpy'), 'opencv': cv,
        'rembg': {'available': mod('rembg'), 'model_on_disk': bool(model),
                  'model': _mask(model) if model else None,
                  'note': 'background/subject ops run only with a model already on disk (no download)'},
        'sd_turbo_venv': {'python': _mask(vpy), 'exists': vpy.is_file(), 'env_override': overridden,
                          'override_var': 'BD_TOON_VENV_PY', 'model_dir_exists': sd_model_dir().is_dir()},
        'mspaint': {'available': bool(mspaint), 'path': _mask(mspaint) if mspaint else None},
        'upscayl_bin': bool(shutil.which('upscayl-bin')),
        'network': False, 'installs': False,
        'notes': ['paint_ai (SD-Turbo, CPU) needs ~4 GB free RAM; try one 512px image with --steps 1 first',
                  'print/wallpaper need --yes; outputs are never overwritten (except same .dpaint editing)'],
    }


def _has_dist(name):
    try:
        from importlib.metadata import version
        version(name)
        return True
    except Exception:
        return False


def check_hashes():
    errors = []
    try:
        data = json.loads(SOURCE_JSON.read_text(encoding='utf-8'))
        for f in data['files']:
            p = SKILL_DIR / f['path']
            if not p.is_file():
                errors.append(f"missing {f['path']}")
            elif sha(p) != f['sha256'] or p.stat().st_size != f['size']:
                errors.append(f"changed {f['path']}")
    except Exception as e:
        errors.append(f'source manifest unreadable: {e}'[:200])
    return {'ok': not errors, 'errors': errors}


# ───────────────────────────── guards ─────────────────────────────
def check_out(out, src=None):
    p = Path(out).absolute()
    if p.suffix.lower() not in OUT_EXT:
        raise Refused(f'output must be an image or .dpaint file: {out}')
    if p.exists() or p.is_symlink():
        same = src is not None and p.suffix.lower() == '.dpaint' and Path(src).absolute() == p
        if not same:
            raise Refused(f'refusing to overwrite existing file: {out} (choose a new name)')
    if p.is_dir():
        raise Refused(f'output is a folder: {out}')
    for parent in p.parents:
        if parent.exists():
            if not parent.is_dir():
                raise Refused(f'output parent is not a folder: {parent}')
            break
    return p


def _paint_parser():
    """Mirror of paint.py's argparse so the bridge knows which argument is the output."""
    ap = argparse.ArgumentParser(add_help=False)
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('new', add_help=False); p.add_argument('out'); p.add_argument('--size', default='1152x648'); p.add_argument('--bg', default='white')
    p = sub.add_parser('info', add_help=False); p.add_argument('src')
    p = sub.add_parser('draw', add_help=False); p.add_argument('src'); p.add_argument('out'); p.add_argument('--ops'); p.add_argument('--op', action='append', default=[])
    p = sub.add_parser('export', add_help=False); p.add_argument('src'); p.add_argument('out')
    p = sub.add_parser('preview', add_help=False); p.add_argument('src'); p.add_argument('out'); p.add_argument('--zoom', type=float, default=1)
    p.add_argument('--grid', type=int, default=0); p.add_argument('--rulers', action='store_true'); p.add_argument('--box')
    p = sub.add_parser('pick', add_help=False); p.add_argument('src'); p.add_argument('x', type=int); p.add_argument('y', type=int)
    sub.add_parser('ops', add_help=False)
    p = sub.add_parser('gui', add_help=False); p.add_argument('src', nargs='?')
    p = sub.add_parser('print', add_help=False); p.add_argument('src')
    p = sub.add_parser('wallpaper', add_help=False); p.add_argument('src'); p.add_argument('--style', default='fill')
    return ap


class _ParseError(Exception):
    pass


def _parse(parser, args):
    def err(msg):
        raise _ParseError(msg)
    parser.error = err
    for a in parser._subparsers._group_actions[0].choices.values():  # noqa: SLF001
        a.error = err
    return parser.parse_args(args)


def _load_ops(a):
    ops = []
    if a.ops:
        f = Path(a.ops)
        if not f.is_file():
            raise Refused(f'ops file not found: {a.ops}')
        data = json.loads(f.read_text(encoding='utf-8'))
        ops += data['ops'] if isinstance(data, dict) else data
    ops += [json.loads(s) for s in a.op]
    if not isinstance(ops, list) or not all(isinstance(o, dict) for o in ops):
        raise Refused('ops must be a JSON list of objects')
    return ops


def needs_rembg(o):
    op = o.get('op')
    return (op in REMBG_OPS or bool(o.get('subject'))
            or (op == 'magic_erase' and not o.get('mask')))


def guard_paint(args):
    """Validate a paint.py call; returns (args_to_pass, size_hint)."""
    a = _parse(_paint_parser(), args)
    if a.cmd == 'new':
        check_out(a.out)
        try:
            w, h = map(int, a.size.lower().split('x'))
        except ValueError:
            raise Refused('--size must look like 1152x648')
        if not (1 <= w <= 16384 and 1 <= h <= 16384) or w * h > 100_000_000:
            raise Refused('--size outside safe range (1..16384 per side)')
    elif a.cmd == 'draw':
        if not Path(a.src).exists():
            raise Refused(f'missing input {a.src} (create one with: tool paint new)')
        check_out(a.out, src=a.src)
        try:
            ops = _load_ops(a)
        except (ValueError, KeyError, TypeError) as e:
            raise Refused(f'invalid ops JSON: {e}')
        if any(needs_rembg(o) for o in ops) and not rembg_model_on_disk():
            raise Refused('this op needs a rembg model on disk (it would download one); '
                          'none found in U2NET_HOME / ~/.u2net. No network is used by the bridge.')
    elif a.cmd in ('export', 'preview'):
        if not Path(a.src).exists():
            raise Refused(f'missing input {a.src}')
        check_out(a.out)
        if a.cmd == 'export' and Path(a.out).suffix.lower() == '.dpaint':
            raise Refused('export writes a flat image (png/jpg/webp/...), not .dpaint')
    elif a.cmd in ('info', 'pick', 'print', 'wallpaper'):
        if not Path(a.src).is_file():
            raise Refused(f'missing input {a.src}')
    elif a.cmd == 'gui' and a.src and not Path(a.src).is_file():
        raise Refused(f'missing input {a.src}')
    return a


def run_child(cmd, extra_env=None):
    proc = subprocess.run(cmd, env=child_env(extra_env), stdin=subprocess.DEVNULL)
    return proc.returncode


def paint(args):
    if len(args) >= 2 and args[1] in ('-h', '--help'):
        return run_child([sys.executable, str(PAINT), *args])
    yes = '--yes' in args
    args = [x for x in args if x != '--yes']
    a = guard_paint(args)
    if a.cmd in ('print', 'wallpaper') and not yes:
        what = 'send the image to the default printer' if a.cmd == 'print' else 'change the Windows desktop wallpaper'
        json_print({'ok': False, 'needs_yes': True,
                    'error': f'{a.cmd} will {what}. Ask the owner, then re-run with --yes.'})
        return 3
    if a.cmd == 'gui':
        exe = find_mspaint()
        if not exe:
            raise Refused('mspaint not found on this machine')
        # Launched without a shell (paint.py uses shell=True; the bridge avoids it for odd file names).
        subprocess.Popen([exe] + ([str(Path(a.src).resolve())] if a.src else []))
        json_print({'ok': True, 'opened': 'mspaint', 'file': str(Path(a.src).resolve()) if a.src else None})
        return 0
    return run_child([sys.executable, str(PAINT), *args])


# ───────────────────────────── AI ─────────────────────────────
def ai(args):
    if not args or args[0] in ('-h', '--help'):
        print(_ai_doc())
        return 0
    sub = args[0]
    if sub not in AI_CMDS:
        raise Refused('ai command must be one of: ' + ', '.join(sorted(AI_CMDS)))
    vpy, _ = venv_python()
    if not vpy.is_file():
        json_print({'ok': False, 'error': 'SD-Turbo venv python not found; nothing was installed.',
                    'expected': _mask(vpy), 'override_var': 'BD_TOON_VENV_PY'})
        return 2
    if '-h' in args[1:] or '--help' in args[1:]:
        return run_child([str(vpy), str(PAINT_AI), *args], {'PAINT_SYS_PY': sys.executable})
    outs = _ai_outputs(args)
    for o in outs:
        check_out(o)
    if sub in ('cocreator', 'reimagine', 'fill', 'erase'):
        src = args[1] if len(args) > 1 else ''
        if not Path(src).is_file():
            raise Refused(f'missing input {src}')
    if sub == 'sticker' and any(Path(o).suffix.lower() != '.png' for o in outs):
        raise Refused('sticker output must be .png (paint_ai rewrites it as a transparent PNG)')
    return run_child([str(vpy), str(PAINT_AI), *args], {'PAINT_SYS_PY': sys.executable})


def _ai_outputs(args):
    sub, rest = args[0], args[1:]
    pos = []
    i = 0
    while i < len(rest):
        x = rest[i]
        if x.startswith('--'):
            i += 1 if '=' in x else 2
            continue
        pos.append(x); i += 1
    if sub == 'styles':
        return []
    idx = 0 if sub in ('create', 'sticker', 'coloring') else 1
    if len(pos) <= idx:
        raise Refused(f'ai {sub}: missing output path')
    out = Path(pos[idx])
    n = 1
    for j, x in enumerate(rest):
        if x == '--n' and j + 1 < len(rest):
            n = int(rest[j + 1])
        elif x.startswith('--n='):
            n = int(x.split('=', 1)[1])
    if not 1 <= n <= 16:
        raise Refused('--n must be 1..16')
    if n > 1 and sub in ('create', 'sticker', 'coloring', 'reimagine'):
        return [str(out.with_name(f'{out.stem}_{k + 1}{out.suffix}')) for k in range(n)]
    return [str(out)]


def _ai_doc():
    try:
        text = PAINT_AI.read_text(encoding='utf-8')
        doc = text.split('"""', 2)[1]
    except Exception:
        doc = ''
    return ('usage: dragon.py tool paint ai <create|cocreator|reimagine|fill|erase|sticker|coloring|styles> ...\n'
            'Runs skills/paint-studio/scripts/paint_ai.py with the toon venv python (BD_TOON_VENV_PY overrides).\n'
            'Offline only (HF_HUB_OFFLINE=1); outputs are never overwritten.\n' + doc)


# ───────────────────────────── main ─────────────────────────────
def main(argv):
    _utf8_stdio()
    if not argv or argv[0] in ('-h', '--help', 'help'):
        print(__doc__)
        return 0
    cmd = argv[0]
    try:
        if cmd == 'doctor':
            json_print(doctor())
            return 0
        if cmd == 'verify':
            h = check_hashes()
            json_print({'schema': SCHEMA, **h})
            return 0 if h['ok'] else 5
        if cmd == 'ai':
            return ai(argv[1:])
        if cmd in PAINT_CMDS:
            return paint(argv)
        raise Refused('unknown paint command; use one of: doctor, verify, ai, ' + ', '.join(sorted(PAINT_CMDS)))
    except (Refused, _ParseError, ValueError, OSError) as e:
        json_print({'ok': False, 'error': str(e)[:600]})
        return 2


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
