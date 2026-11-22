"""Red Rose V29 (W03): what is true on this machine.

Read-only by design. probe() and readiness() never open or create a database,
never read the owner's private memory (only check that a path exists), never
write a file and never use the network. The only subprocesses are `ffmpeg
-version` and `ffprobe -version` with a timeout.

Public API (see references/INTERFACE.md):
    probe()            -> dict describing the skill, Python, DB path, deps, fonts, shaping
    readiness(op_id)   -> one of LABELS, or None for an id that is not in the catalogue
    usable_counts()    -> {label: n} over every catalogue op
    load_status()      -> the op rows of references/VERIFIED_STATUS.json
CLI (standalone, same commands rose.py will expose): start, doctor-deps.
"""
from __future__ import annotations

import importlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import rose_io as rio

ROOT = Path(__file__).resolve().parent
SKILL_VERSION = 'V29'
VERIFIED_JSON = ROOT / 'references' / 'VERIFIED_STATUS.json'
PRIVATE_DIR = Path.home() / '.red-rose'
PRIVATE_DB = PRIVATE_DIR / 'memory.sqlite3'
PLAYBOOK_INDEX = PRIVATE_DIR / 'playbooks_v28.sqlite3'
PROBE_TIMEOUT = 15
SAMPLE_ARABIC = 'الوردة الحمراء'
LABELS = ('verified', 'runs_with_defaults', 'needs_input', 'needs_owner_approval', 'pc_only',
          'coded_untested', 'known_broken', 'unavailable_here')

_STATUS_CACHE = {}


# --------------------------------------------------------------------------- small probes

def _commit():
    """Short commit from a plain .git folder (no git subprocess); None when there is none."""
    try:
        git = ROOT / '.git'
        if not git.is_dir():
            return None
        head = (git / 'HEAD').read_text(encoding='utf-8').strip()
        if head.startswith('ref: '):
            ref = git / head[5:].strip()
            if not ref.is_file():
                return None
            head = ref.read_text(encoding='utf-8').strip()
        return head[:12] or None
    except (OSError, ValueError):
        return None


def _place():
    if os.name != 'nt':
        return 'sandbox'
    return 'owner_pc' if PRIVATE_DB.exists() else 'other_pc'


def _db_info():
    env = os.environ.get('RED_ROSE_DB')
    path = Path(env).expanduser() if env else PRIVATE_DB
    try:
        resolved = path.resolve()
    except OSError:
        resolved = path
    return {'path': str(path.absolute()), 'exists': path.exists(),
            'is_private_default': resolved == PRIVATE_DB.resolve()}


def _program_version(name):
    exe = shutil.which(name)
    if not exe:
        return 'MISSING'
    try:
        done = subprocess.run([exe, '-version'], capture_output=True, timeout=PROBE_TIMEOUT, check=False)
    except (OSError, subprocess.SubprocessError):
        return 'present'
    lines = (done.stdout or b'').decode('utf-8', 'replace').splitlines()
    first = lines[0].split() if lines else []
    return first[2] if len(first) >= 3 and first[1] == 'version' else 'present'


def _module_version(module, dist=None):
    try:
        mod = importlib.import_module(module)
    except Exception:  # missing package or missing native library (for example cairo)
        return 'MISSING'
    version = getattr(mod, '__version__', None)
    if version:
        return str(version)
    try:
        from importlib import metadata
        return metadata.version(dist or module)
    except Exception:
        return 'present'


def _font_candidates():
    windir = Path(os.environ.get('SYSTEMROOT') or os.environ.get('WINDIR') or r'C:\Windows')
    return [windir / 'Fonts' / 'arial.ttf', windir / 'Fonts' / 'tahoma.ttf',
            windir / 'Fonts' / 'segoeui.ttf',
            Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'),
            Path('/usr/share/fonts/truetype/noto/NotoNaskhArabic-Regular.ttf')]


def _has_presentation_forms(path):
    try:
        from fontTools.ttLib import TTFont
    except Exception:
        return None
    try:
        font = TTFont(str(path), lazy=True)
        try:
            cmap = font.getBestCmap() or {}
        finally:
            font.close()
        return any(0xFB50 <= code <= 0xFEFC for code in cmap)
    except Exception:
        return None


def _fonts():
    font = next((p for p in _font_candidates() if p.is_file()), None)
    if font is None:
        return {'arabic_font': None, 'has_presentation_forms': None}
    return {'arabic_font': str(font), 'has_presentation_forms': _has_presentation_forms(font)}


def _arabic_shaping():
    """pass | fail | skipped:<reason>. Uses arabic_shape.selftest() when it exists."""
    try:
        mod = importlib.import_module('arabic_shape')
    except Exception as exc:
        return f'skipped:arabic_shape not importable ({type(exc).__name__})'
    fn = getattr(mod, 'selftest', None)
    try:
        if callable(fn):
            res = fn()
        elif callable(getattr(mod, 'shape', None)) and callable(getattr(mod, 'is_shaped', None)):
            out = mod.shape(SAMPLE_ARABIC)['visual']
            res = bool(mod.is_shaped(out)) and not mod.unshaped_runs(out)
        else:
            return 'skipped:no shaping API in arabic_shape'
    except Exception:
        return 'fail'
    if res is None:
        return 'pass'
    if isinstance(res, dict):
        return 'pass' if res.get('ok', True) else 'fail'
    return 'pass' if bool(res) else 'fail'


def _playbook_index():
    return 'present' if PLAYBOOK_INDEX.exists() else 'absent'


def _extensions_failed():
    try:
        status = importlib.import_module('rose_ext').status()
    except Exception:
        return ['rose_ext: not importable']
    return [str(f.get('module', '?')) for f in status.get('failed', [])]


def extensions_status():
    """{loaded, failed, skipped} from the last rose_ext.load() call in this process."""
    try:
        return importlib.import_module('rose_ext').status()
    except Exception:
        return {'loaded': [], 'failed': [], 'skipped': []}


# --------------------------------------------------------------------------- public: probe

def probe():
    """Everything `start` and `doctor-deps` report. Read-only (see module docstring)."""
    return {
        'version': SKILL_VERSION,
        'commit': _commit(),
        'skill_root': str(ROOT),
        'place': _place(),
        'python': sys.version.split()[0],
        'db': _db_info(),
        'deps': {'ffmpeg': _program_version('ffmpeg'), 'ffprobe': _program_version('ffprobe'),
                 'cairosvg': _module_version('cairosvg'), 'pillow': _module_version('PIL', 'pillow')},
        'fonts': _fonts(),
        'arabic_shaping': _arabic_shaping(),
        'playbook_index': _playbook_index(),
        'extensions_failed': _extensions_failed(),
    }


def missing_programs(deps):
    """Names in the deps block that are MISSING."""
    return sorted(name for name, value in deps.items() if value == 'MISSING')


# --------------------------------------------------------------------------- public: readiness

def load_status(path=None):
    """The `ops` mapping of VERIFIED_STATUS.json ({} when absent or unreadable). Cached by mtime."""
    target = Path(path) if path is not None else Path(VERIFIED_JSON)
    try:
        st = target.stat()
    except OSError:
        return {}
    key = (str(target), st.st_mtime_ns, st.st_size)
    if _STATUS_CACHE.get('key') != key:
        try:
            doc = json.loads(target.read_text(encoding='utf-8'))
            ops = doc.get('ops') if isinstance(doc, dict) else None
            ops = ops if isinstance(ops, dict) else {}
        except (OSError, ValueError):
            ops = {}
        _STATUS_CACHE.clear()
        _STATUS_CACHE.update({'key': key, 'ops': ops})
    return _STATUS_CACHE['ops']


def missing_here(needs):
    """Programs and Python modules named by an op's needs that this machine does not have."""
    missing = []
    for prog in (needs or {}).get('programs') or []:
        if not shutil.which(prog):
            missing.append(prog)
    for mod in (needs or {}).get('python') or []:
        try:
            importlib.import_module(mod)
        except Exception:
            missing.append(mod)
    return missing


def readiness(op_id):
    """One label for a catalogue op (static label + VERIFIED_STATUS row + live check). None if unknown."""
    catalog = importlib.import_module('rose_catalog')
    entry = catalog.get(op_id)
    if not isinstance(entry, dict):
        return None
    row = load_status().get(op_id)
    row_status = row.get('status') if isinstance(row, dict) else None
    static = entry.get('static_label')
    needs = entry.get('needs') or {}
    if static == 'known_broken' or row_status == 'failed':
        return 'known_broken'
    if needs.get('pc_only'):
        return 'pc_only'
    if missing_here(needs):
        return 'unavailable_here'
    if row_status == 'verified':
        return 'verified'
    if row_status == 'runs_with_defaults':
        return 'runs_with_defaults'
    if (entry.get('approval') or {}).get('needed'):
        return 'needs_owner_approval'
    if static == 'needs_input':
        return 'needs_input'
    if static == 'coded_untested':
        return 'coded_untested'
    return 'runs_with_defaults'


def usable_counts():
    """{label: n} over every catalogue op; every label is present (zero when unused)."""
    catalog = importlib.import_module('rose_catalog')
    counts = {label: 0 for label in LABELS}
    for op_id in catalog.load()['entries']:
        label = readiness(op_id)
        if label:
            counts[label] = counts.get(label, 0) + 1
    return counts


# --------------------------------------------------------------------------- CLI: start, doctor-deps

def _usable_text(counts):
    return ' | '.join(f'{label} {counts.get(label, 0)}' for label in LABELS)


def _run_prefix():
    return f'python -X utf8 "{(ROOT / "rose.py").as_posix()}"'


def _command_lines():
    """(name, arguments after the run prefix)."""
    return [
        ('start', '(this status, read only)'),
        ('brief', 'brief "<the owner words>"'),
        ('run', 'run ADAPTER.OP key=value ...   (or recipe run ID ...)'),
        ('check', 'check --request "<request>" --draft FILE'),
    ]


def start_doc():
    p = probe()
    counts = usable_counts()
    ext = extensions_status()
    db = p['db']
    trial = None
    if db['exists']:
        trial = ('trial runs: PowerShell  $env:RED_ROSE_DB="<workdir>\\rose.sqlite3"   '
                 'Git Bash  export RED_ROSE_DB="<workdir>/rose.sqlite3"')
    return {'ok': True, 'outcome': 'ok', 'probe': p, 'usable': counts,
            'extensions': {'loaded': len(ext.get('loaded', [])), 'failed': ext.get('failed', [])},
            'missing': missing_programs(p['deps']),
            'commands': [[name, f'{_run_prefix()} {args}'] for name, args in _command_lines()],
            'trial_db_hint': trial,
            'shell_rule': 'PowerShell 5.1 and Git Bash: never inline JSON; use --params-file FILE or key=value',
            'update': 'rose.py install-skill --approve-write (only after an explicit yes)'}


def start_text(doc):
    p = doc['probe']
    db = p['db']
    fonts = p['fonts']
    lines = [
        f"الوردة الحمراء {p['version']} | read only: no database, no file, no network",
        f"skill: {p['skill_root']}",
        f"version: {p['version']}  commit: {p['commit'] or 'none (no .git folder here)'}  place: {p['place']}  python: {p['python']}",
        f"database: {db['path']}  exists: {'yes' if db['exists'] else 'no'}  private default: {'yes' if db['is_private_default'] else 'no'}",
        "  (never opened by start; an op creates it only when it needs it)",
    ]
    if doc['trial_db_hint']:
        lines.append('  ' + doc['trial_db_hint'])
    deps = p['deps']
    lines.append('deps: ' + ' | '.join(f'{k} {v}' for k, v in deps.items()))
    missing = doc['missing']
    lines.append('MISSING: ' + (', '.join(missing) if missing else 'none'))
    font = fonts['arabic_font'] or 'none'
    lines.append(f"fonts: {Path(font).name if fonts['arabic_font'] else font}  presentation forms: "
                 f"{'yes' if fonts['has_presentation_forms'] else ('no' if fonts['has_presentation_forms'] is False else 'unknown')}")
    lines.append(f"arabic shaping: {p['arabic_shaping']}")
    lines.append(f"playbook index: {p['playbook_index']}")
    failed = p['extensions_failed']
    lines.append('extensions failed: ' + (', '.join(failed) if failed else 'none'))
    lines.append('usable here: ' + _usable_text(doc['usable']))
    lines.append(f'run as: {_run_prefix()} <command>')
    lines.append('commands:')
    lines.extend(f'  {name}: {args}' for name, args in _command_lines())
    lines.append('shell: ' + doc['shell_rule'])
    lines.append(f"update: {doc['update']}")
    lines.append('exit: 0 ok; 4 unavailable_here for the op you run')
    return '\n'.join(lines)


def _h_start(args):
    doc = start_doc()
    if args.json:
        rio.emit(doc)
    else:
        sys.stdout.buffer.write((start_text(doc) + '\n').encode('utf-8'))
        sys.stdout.flush()
    return rio.EXIT_OK


def _h_doctor_deps(args):
    p = probe()
    doc = {'ok': True, 'outcome': 'ok', 'deps': p['deps'], 'fonts': p['fonts'],
           'arabic_shaping': p['arabic_shaping'], 'missing': missing_programs(p['deps']),
           'db': p['db']}
    if args.json:
        rio.emit(doc)
        return rio.EXIT_OK
    lines = ['deps: ' + ', '.join(f'{k} {v}' for k, v in p['deps'].items()),
             'MISSING: ' + (', '.join(doc['missing']) if doc['missing'] else 'none'),
             f"fonts: {p['fonts']['arabic_font'] or 'none'}",
             f"arabic shaping: {p['arabic_shaping']}",
             f"database path in use: {p['db']['path']} (exists: {'yes' if p['db']['exists'] else 'no'})"]
    sys.stdout.buffer.write(('\n'.join(lines) + '\n').encode('utf-8'))
    sys.stdout.flush()
    return rio.EXIT_OK


def register(subparsers):
    """Adds start and doctor-deps (see references/INTERFACE.md)."""
    p = subparsers.add_parser('start', help='read only: skill path, version, deps, shaping, usable counts, next command')
    p.add_argument('--json', action='store_true', help='one JSON document instead of text')
    rio.json_usage_errors(p)
    p.set_defaults(ext_func=_h_start)

    p = subparsers.add_parser('doctor-deps', help='read only: programs, fonts, Arabic shaping self-test')
    p.add_argument('--json', action='store_true', help='one JSON document instead of text')
    rio.json_usage_errors(p)
    p.set_defaults(ext_func=_h_doctor_deps)


def main(argv=None):
    """Standalone entry, same commands as rose.py: python -X utf8 rose_env.py start|doctor-deps|selfcheck|sample-media ..."""
    import argparse
    import rose_ext
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(prog='rose_env.py')
    sub = parser.add_subparsers(dest='command', required=True)
    rose_ext.load(sub)
    args = parser.parse_args(argv)
    return args.ext_func(args)


if __name__ == '__main__':
    raise SystemExit(main())
