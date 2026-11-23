"""Red Rose V26: chapter 28 — final integration and release checks (topics 28.01-28.10).

Every op audits THIS project folder (the folder that holds this file) unless a caller
supplies another input. Read ops never write. The two write ops (integrated_video,
portable_release) need approve_write=True and an existing caller-supplied work_dir
outside the project folder, and they never overwrite anything.

Child processes are started only as subprocess.run([...], capture_output=True,
timeout=...) with sys.executable, ffmpeg or ffprobe; never through a shell.
No network modules, no exec/eval, no printing. Results are plain JSON:
{'op', 'result', 'assumptions', 'limits'}.
"""
from __future__ import annotations

import ast
import fnmatch
import hashlib
import json
import math
import re
import subprocess
import sys
import tempfile
import time
import tracemalloc
import zipfile
from datetime import datetime, timezone
from os import environ as _ENVIRON
from pathlib import Path

import roadmap_1400
import governance_v22
import architecture_v22
import security_v24
import agents_v22
from pipeline_v15 import prepare_project, render_project, budget
from verify_media import verify_video

ROOT = Path(__file__).resolve().parent
MAX_PARAMS = 24
SUBPROCESS_TIMEOUT = 300

TOPICS = {
    '28.01': 'independence_audit',
    '28.02': 'registry_reality',
    '28.03': 'closure_matrix',
    '28.04': 'integrated_video',
    '28.05': 'device_checklist',
    '28.06': 'load_test',
    '28.07': 'release_privacy',
    '28.08': 'edit_rubric',
    '28.09': 'portable_release',
    '28.10': 'handoff_resume',
}

TOPIC_NAMES_AR = {
    '28.01': 'تدقيق استقلالية الحزمة',
    '28.02': 'تحقق قائمة قدرات حقيقية',
    '28.03': 'إغلاق متطلبات 1400',
    '28.04': 'تشغيل فيديو متكامل',
    '28.05': 'التجربة على الهاتف والحاسوب',
    '28.06': 'اختبار أداء وحمل',
    '28.07': 'مراجعة خصوصية الإصدار',
    '28.08': 'تقييم جودة المونتاج بشريًا',
    '28.09': 'إصدار محمول قابل للاستعادة',
    '28.10': 'تسليم لأي وكيل تالٍ',
}

# Folders that are never part of a release, whatever .gitignore says.
_SKIP_DIRS = {'__pycache__', '.pytest_cache', '.git', '.mypy_cache'}
# Hard exclusions for the portable release (on top of .gitignore).
_RELEASE_EXCLUDE = ('*.sqlite*', '*.db', '*.pyc', '*.mp4', '*.mov', '*.mkv', '*.webm', '*.wav',
                    '*.mp3', '*.m4a', '*.aac', '*.flac', '.env*', 'memory*.json')
_RELEASE_EXCLUDE_DIRS = {'owner-memory', 'private', 'credentials', 'media'}


# --------------------------------------------------------------------------- validation

def _no_extra(extra):
    if extra:
        raise ValueError('unknown parameter(s): ' + ', '.join(sorted(map(str, extra))))


def _bool(value, name):
    if not isinstance(value, bool):
        raise ValueError(f'{name} must be true or false')
    return value


def _int(value, low, high, name):
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise ValueError(f'{name} must be an integer from {low} to {high}')
    return value


def _num(value, low, high, name):
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value) or not low < value <= high):
        raise ValueError(f'{name} must be a number in ({low}, {high}]')
    return float(value)


def _str(value, name, max_len=1000, allow_empty=False):
    if not isinstance(value, str) or len(value) > max_len or (not allow_empty and not value.strip()):
        raise ValueError(f'{name} must be a non-empty string of at most {max_len} characters')
    if '\x00' in value:
        raise ValueError(f'{name} must not contain NUL')
    return value


def _choice(value, options, name):
    if not isinstance(value, str) or value not in options:
        raise ValueError(f'{name} must be one of {sorted(options)}')
    return value


def _name(value, name, suffix=None):
    value = _str(value, name, 120)
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,119}', value) or '..' in value:
        raise ValueError(f'{name} must be a plain file/folder name (letters, digits, . _ -)')
    if suffix and not value.lower().endswith(suffix):
        raise ValueError(f'{name} must end with {suffix}')
    return value


def _approve(approve_write, op):
    if approve_write is not True:
        raise ValueError(f'{op} writes into work_dir and requires approve_write=True')


def _inside(path, folder):
    try:
        path.relative_to(folder)
        return True
    except ValueError:
        return False


def _work_dir(work_dir):
    if work_dir is None:
        raise ValueError('work_dir is required (an existing folder outside the project)')
    _str(work_dir, 'work_dir', 1024)
    p = Path(work_dir).expanduser()
    if not p.is_dir():
        raise ValueError('work_dir must be an existing folder')
    p = p.resolve()
    if _inside(p, ROOT):
        raise ValueError('work_dir must be outside the Red Rose project folder')
    return p


def _project(project):
    if project is None:
        return ROOT
    _str(project, 'project', 1024)
    p = Path(project).expanduser()
    if not p.is_dir():
        raise ValueError('project must be an existing folder')
    return p.resolve()


def _pack(op, result, assumptions, limits):
    return {'op': op, 'result': result, 'assumptions': list(assumptions), 'limits': list(limits)}


def _sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def _now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def _clean_env(home, extra=None):
    """Scrubbed child environment: only SYSTEMROOT, PATH and TEMP from the parent, plus a
    throw-away home folder (knowledge_v25 calls Path.home() at import) and explicit extras."""
    env = {}
    for key in ('SYSTEMROOT', 'PATH', 'TEMP'):
        val = _ENVIRON.get(key)
        if val:
            env[key] = val
    env['USERPROFILE'] = env['HOME'] = str(home)
    env.update(extra or {})
    return env


def _registry():
    import capability_runtime  # lazy: capability_runtime may one day import this module
    return capability_runtime


# --------------------------------------------------------------------------- file listing

def _gitignore_patterns(project):
    gi = project / '.gitignore'
    if not gi.is_file():
        return []
    out = []
    for line in gi.read_text(encoding='utf-8', errors='replace').splitlines():
        line = line.strip()
        if line and not line.startswith(('#', '!')):
            out.append(line)
    return out


def _matches(rel, patterns, dir_names=()):
    """fnmatch subset of gitignore: 'dir/' matches any folder part, 'a/b' the path, else any part."""
    parts = rel.split('/')
    low_parts = [p.lower() for p in parts]
    if any(p in dir_names for p in low_parts[:-1]):
        return 'dir:' + next(p for p in low_parts[:-1] if p in dir_names)
    for pat in patterns:
        p = pat.lower().lstrip('/')
        if p.endswith('/'):
            d = p.rstrip('/')
            if any(fnmatch.fnmatchcase(x, d) for x in low_parts[:-1]):
                return pat
        elif '/' in p:
            if fnmatch.fnmatchcase(rel.lower(), p) or fnmatch.fnmatchcase(rel.lower(), p + '/*'):
                return pat
        elif any(fnmatch.fnmatchcase(x, p) for x in low_parts):
            return pat
    return None


def _release_files(project, extra_patterns=(), extra_dirs=()):
    """Files git would track: walk project, skip caches, .gitignore matches and extras."""
    patterns = _gitignore_patterns(project) + list(extra_patterns)
    included, excluded = [], []
    for p in sorted(project.rglob('*')):
        if p.is_symlink() or not p.is_file():
            continue
        rel = p.relative_to(project).as_posix()
        if any(part in _SKIP_DIRS for part in rel.split('/')):
            continue
        hit = _matches(rel, patterns, set(extra_dirs))
        if hit:
            excluded.append({'path': rel, 'pattern': hit})
            continue
        included.append(rel)
    return included, excluded


# --------------------------------------------------------------------------- 28.01 independence

_IMPORT_KINDS = {'import', 'from_import', 'from_import_name', 'dynamic_import'}
_CHILD_IMPORT = (
    "import sys, json\n"
    "root = sys.argv[1]\n"
    "sys.path.insert(0, root)\n"
    "preloaded = set(sys.modules)  # loaded by the interpreter before the project (site hooks): not ours to judge\n"
    "import capability_runtime\n"
    "import os.path as op\n"
    "pref = [op.normcase(op.abspath(x)) for x in {sys.prefix, sys.base_prefix, sys.exec_prefix}]\n"
    "proj = op.normcase(op.abspath(root))\n"
    "foreign, local = [], 0\n"
    "for name, m in sorted(sys.modules.items()):\n"
    "    f = getattr(m, '__file__', None)\n"
    "    if not f or name in preloaded:\n"
    "        continue\n"
    "    f = op.normcase(op.abspath(f))\n"
    "    if f.startswith(proj + op.sep):\n"
    "        local += 1\n"
    "    elif not any(f.startswith(p + op.sep) for p in pref):\n"
    "        foreign.append(name)\n"
    "sys.stdout.write(json.dumps({'registry': len(capability_runtime.REGISTRY),\n"
    "    'project_modules_loaded': local, 'foreign_modules': foreign,\n"
    "    'isolated': bool(sys.flags.isolated)}))\n"
)


def _chunks(items, max_chars, max_files):
    out, cur, size = [], {}, 0
    for k, v in items:
        if cur and (size + len(v) > max_chars or len(cur) >= max_files):
            out.append(cur)
            cur, size = {}, 0
        cur[k] = v
        size += len(v)
    if cur:
        out.append(cur)
    return out


def _subprocess_calls_with_legacy(name, src, legacy):
    """Own AST pass: string constants inside real subprocess.*/os.* calls that name legacy engines."""
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return []
    hits = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and getattr(node.func.value, 'id', None) in ('subprocess', 'os'):
            for sub in ast.walk(node):
                if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                    low = sub.value.casefold()
                    for n in legacy:
                        if n in low:
                            hits.append({'file': name, 'line': node.lineno, 'legacy_name': n})
    return hits


def independence_audit(*, project=None, run_clean_import=True, **extra):
    """legacy_import_audit over every *.py + a clean, isolated `import capability_runtime`."""
    _no_extra(extra)
    root = _project(project)
    run_clean_import = _bool(run_clean_import, 'run_clean_import')
    sources = {p.name: p.read_text(encoding='utf-8', errors='replace')
               for p in sorted(root.glob('*.py')) if p.is_file()}
    if not sources:
        raise ValueError('project has no *.py files')
    internal_modules = {Path(n).stem for n in sources} | {
        d.name for d in root.iterdir() if d.is_dir() and (d / '__init__.py').is_file()}
    findings, warnings, unparsed = [], [], []
    for chunk in _chunks(sorted(sources.items()), governance_v22.MAX_AUDIT_CHARS // 2,
                         governance_v22.MAX_AUDIT_FILES // 2):
        r = governance_v22.legacy_import_audit(files=chunk)['result']
        findings += r['findings']
        warnings += r['warnings']
        unparsed += r['unparsed_files']
    internal, external, mentions = [], [], []
    for f in findings:
        if f['kind'] in _IMPORT_KINDS:
            top = f['target'].lstrip('.').split('.')[0]
            (internal if top in internal_modules else external).append(f)
        else:
            mentions.append(f)
    legacy = list(governance_v22.DEFAULT_LEGACY_NAMES)
    legacy_commands = [h for n, s in sources.items() for h in _subprocess_calls_with_legacy(n, s, legacy)]

    clean = None
    if run_clean_import:
        with tempfile.TemporaryDirectory(prefix='rr_home_') as home:
            env = _clean_env(home)
            proc = subprocess.run([sys.executable, '-I', '-X', 'utf8', '-B', '-c', _CHILD_IMPORT, str(root)],
                                  capture_output=True, text=True, encoding='utf-8', errors='replace',
                                  timeout=SUBPROCESS_TIMEOUT, cwd=str(root), env=env)
            home_left = sorted(p.name for p in Path(home).iterdir())
        payload = None
        if proc.returncode == 0:
            try:
                payload = json.loads(proc.stdout)
            except ValueError:
                payload = None
        clean = {'exit_code': proc.returncode, 'report': payload,
                 'stderr_tail': proc.stderr[-800:] if proc.returncode else '',
                 'env_keys': sorted(env), 'temp_home_entries_after_import': home_left,
                 'flags': ['-I', '-X utf8', '-B']}
    passed = (not external and not unparsed and not legacy_commands
              and (clean is None or (clean['exit_code'] == 0 and clean['report'] is not None
                                     and not clean['report']['foreign_modules'])))
    result = {'passed': passed, 'files_scanned': len(sources),
              'external_legacy_imports': external, 'external_count': len(external),
              'internal_findings_count': len(internal),
              'internal_modules_named_like_legacy': sorted({f['target'].lstrip('.').split('.')[0]
                                                            for f in internal}),
              'string_mentions_count': len(mentions),
              'string_mentions': mentions[:50],
              'legacy_names_in_subprocess_calls': legacy_commands,
              'unparsed_files': unparsed, 'dynamic_import_warnings': warnings,
              'clean_import': clean}
    return _pack('independence_audit', result,
                 ['static scan by governance_v22.legacy_import_audit (AST, nothing executed), batched '
                  'to respect its size caps',
                  'a finding is internal when its top-level module is a *.py file (or package) inside '
                  'this project, e.g. alloy_fusion.py: the name looks legacy but the code is local',
                  'string mentions (test data passed to run(...), docs) are listed, not counted as imports; '
                  'only string constants inside real subprocess.*/os.* calls count as legacy commands',
                  'the clean import runs `python -I -X utf8 -B` with cwd=project, only SYSTEMROOT/PATH/TEMP '
                  'kept from the parent environment plus an empty temporary USERPROFILE/HOME '
                  '(knowledge_v25 calls Path.home() at import and fails without one), and the project '
                  'folder inserted explicitly into sys.path (-I drops the script folder by design)',
                  'foreign_modules = loaded modules whose file is neither in the project nor under the '
                  'Python installation prefixes'],
                 ['dynamic import targets that are not string literals cannot be resolved (reported as warnings)',
                  'only top-level *.py files are scanned (the project has no sub-packages today)',
                  'imports done lazily inside functions that the import does not execute are only '
                  'covered by the static scan'])


# --------------------------------------------------------------------------- 28.02 registry

def _branch_ids_and_modules(cr_source):
    """capability ids compared in execute() branches, with the modules their bodies call."""
    tree = ast.parse(cr_source)
    imported = {}
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module:
            for a in node.names:
                imported[a.asname or a.name] = node.module
        elif isinstance(node, ast.Import):
            for a in node.names:
                imported[a.asname or a.name] = a.name
    execute = next((n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'execute'), None)
    if execute is None:
        return {}
    out = {}

    def ids_in(test):
        found = []
        for sub in ast.walk(test):
            if isinstance(sub, ast.Compare) and isinstance(sub.left, ast.Name) and sub.left.id == 'capability':
                for comp in sub.comparators:
                    for c in ast.walk(comp):
                        if isinstance(c, ast.Constant) and isinstance(c.value, str):
                            found.append(c.value)
        return found

    for node in ast.walk(execute):
        if isinstance(node, ast.If):
            ids = ids_in(node.test)
            if not ids:
                continue
            mods = set()
            for stmt in node.body:
                for sub in ast.walk(stmt):
                    if isinstance(sub, ast.Name) and sub.id in imported:
                        mods.add(imported[sub.id])
            for i in ids:
                out.setdefault(i, set()).update(mods)
    return out


def registry_reality(*, registry=None, **extra):
    """Every REGISTRY id needs a dispatch path in execute() and a test file that references it."""
    _no_extra(extra)
    cr = _registry()
    if registry is None:
        registry = cr.REGISTRY
    if not isinstance(registry, dict) or not 1 <= len(registry) <= 2000:
        raise ValueError('registry must be a dict of 1..2000 {id: [description, effect, dependency]}')
    for k, v in registry.items():
        _str(k, 'registry id', 120)
        if not (isinstance(v, (list, tuple)) and len(v) == 3 and all(isinstance(x, str) for x in v)):
            raise ValueError(f'registry[{k!r}] must be [description, effect, dependency]')
    cr_path = Path(cr.__file__).resolve()
    branches = _branch_ids_and_modules(cr_path.read_text(encoding='utf-8'))
    tests = {p.name: p.read_text(encoding='utf-8', errors='replace')
             for p in sorted(ROOT.glob('test_*.py'))}
    rows, phantoms, untested = [], [], []
    declared_untested = set(getattr(cr, 'CODED_UNTESTED', ()))
    for ident in registry:
        if ident in cr.PURE_MODULES:
            dispatch, modules = 'PURE_MODULES', {cr.PURE_MODULES[ident].__name__}
        elif ident in cr.IO_ADAPTERS:
            dispatch, modules = 'IO_ADAPTERS', {cr.IO_ADAPTERS[ident].__name__}
        elif ident in branches:
            dispatch, modules = 'execute_branch', branches[ident]
        else:
            dispatch, modules = None, set()
        refs = []
        quoted = (f"'{ident}'", f'"{ident}"')
        for tname, text in tests.items():
            if any(q in text for q in quoted):
                refs.append({'test': tname, 'via': 'id'})
            else:
                for m in sorted(modules):
                    if re.search(r'(?m)^\s*(?:from\s+' + re.escape(m) + r'\s+import|import\s+.*\b'
                                 + re.escape(m) + r'\b)', text):
                        refs.append({'test': tname, 'via': 'module ' + m})
                        break
        problems = []
        if dispatch is None:
            problems.append('no dispatch path in capability_runtime.execute')
        status = 'tested_reference'
        if not refs:
            if dispatch is not None and ident in declared_untested:
                # Owner-requested "coded, not tested" adapters: real code, honestly reported apart.
                status = 'coded_untested'
                untested.append(ident)
            else:
                problems.append('no test_*.py references the id or its module')
        row = {'id': ident, 'dispatch': dispatch, 'modules': sorted(modules),
               'test_refs': len(refs), 'example_tests': [r['test'] for r in refs[:3]],
               'status': status, 'problems': problems}
        rows.append(row)
        if problems:
            phantoms.append({'id': ident, 'problems': problems})
    result = {'checked': len(rows), 'phantoms': phantoms, 'phantom_count': len(phantoms),
              'coded_untested': untested, 'coded_untested_count': len(untested),
              'passed': not phantoms, 'rows': rows,
              'capability_runtime_sha256': _sha256_file(cr_path), 'test_files': len(tests)}
    return _pack('registry_reality', result,
                 ['dispatch path = id in PURE_MODULES or IO_ADAPTERS, or compared to `capability` in an '
                  'if/elif of capability_runtime.execute (found by AST, not by running it)',
                  "test reference = a test_*.py containing the quoted id, or importing a module that the "
                  "id's dispatch branch calls",
                  'a reference proves a test mentions the capability, not that the test passes'],
                 ['registry <= 2000 ids', 'only test_*.py in the project folder are searched'])


# --------------------------------------------------------------------------- 28.03 closure

def closure_matrix(*, rows='all', **extra):
    """question -> topic -> lens -> module/symbol/test; complete only when all 1,400 are answered."""
    _no_extra(extra)
    rows = _choice(rows, {'all', 'remaining', 'answered', 'none'}, 'rows')
    cr = _registry()
    live_sha = _sha256_file(roadmap_1400.SOURCE)
    questions = roadmap_1400.load_questions()
    status = roadmap_1400.load_status(registry=cr.REGISTRY)
    summary = roadmap_1400.summary(registry=cr.REGISTRY)
    matrix, answered = [], 0
    by_chapter = {}
    for q in questions:
        key = roadmap_1400.topic_key(q)
        lens = roadmap_1400.LENS_KEYS[roadmap_1400.LENSES.index(q['lens'])]
        entry = status.get(key) or {}
        level = entry.get('status', 'proposed')
        ok = level in ('unit_tested', 'e2e_verified') and lens in entry.get('lenses', [])
        answered += ok
        ch = by_chapter.setdefault(key[:2], {'answered': 0, 'total': 0})
        ch['total'] += 1
        ch['answered'] += ok
        if rows == 'all' or (rows == 'remaining' and not ok) or (rows == 'answered' and ok):
            matrix.append({'q': q['id'], 'topic': key, 'lens': lens, 'status': level,
                           'module': entry.get('module'), 'symbol': entry.get('symbol'),
                           'test': entry.get('test'), 'answered': ok})
    if answered != summary['questions_answered_in_tested_code']:
        raise RuntimeError('closure matrix disagrees with roadmap_1400.summary')
    result = {'complete': answered == 1400, 'questions': len(questions), 'answered': answered,
              'remaining': 1400 - answered, 'topics': summary['topics'],
              'topics_by_level': summary['topics_by_level'],
              'source': str(roadmap_1400.SOURCE.relative_to(ROOT).as_posix()),
              'source_sha256': live_sha, 'source_sha256_matches_approved': live_sha == roadmap_1400.SOURCE_SHA256,
              'by_chapter': by_chapter, 'rows_mode': rows, 'matrix': matrix,
              'claim': ('all 1,400 answered in tested code' if answered == 1400 else
                        f'NOT complete: {1400 - answered} of 1,400 questions still lack tested code')}
    return _pack('closure_matrix', result,
                 ['source = questions/owner_1400/RED_ROSE_1400.json, hash re-checked by roadmap_1400',
                  'a question is answered only if its topic is unit_tested/e2e_verified in '
                  'ROADMAP_1400_STATUS.json AND its lens is listed; load_status re-verifies module, '
                  'symbol and test file on every call',
                  'the count must equal roadmap_1400.summary or the op fails'],
                 ['answered means "tested code exists", not that a human reviewed the answer',
                  'rows=all returns 1,400 small rows; use remaining/answered/none to shrink'])


# --------------------------------------------------------------------------- 28.04 video

_MIN_STORYBOARD = [
    {'duration': 1.0, 'recipe': {'mode': 'director2d', 'title': 'RED ROSE',
                                 'palette': {'sky': '#3a4a7a', 'horizon': '#e8a08a', 'distant': '#7d8fb0',
                                             'middle': '#4d6688', 'ground': '#2a3f52', 'light': '#ffe0b0'}}},
]
BLACK_LUMA_MAX = 20.0  # mean 8-bit luma at or below this counts as a black frame (limited-range black = 16)


def _ffprobe(video):
    proc = subprocess.run(['ffprobe', '-v', 'error', '-show_entries',
                           'stream=codec_type,codec_name,pix_fmt,width,height,avg_frame_rate,nb_frames'
                           ':format=duration', '-of', 'json', str(video)],
                          capture_output=True, text=True, encoding='utf-8', errors='replace',
                          timeout=120)
    if proc.returncode:
        raise RuntimeError('ffprobe failed: ' + proc.stderr[-400:])
    return json.loads(proc.stdout)


def _first_frame_luma(video):
    proc = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(video), '-frames:v', '1',
                           '-vf', 'scale=16:16,format=gray', '-f', 'rawvideo', '-'],
                          capture_output=True, timeout=120)
    if proc.returncode or len(proc.stdout) != 256:
        raise RuntimeError('could not decode a 16x16 first frame')
    return sum(proc.stdout) / 256.0


def integrated_video(*, work_dir=None, approve_write=False, storyboard=None, name='red_rose_e2e',
                     fps=12, width=270, height=480, **extra):
    """Storyboard -> prepare_project -> render_project -> verify_video + own ffprobe -> receipt."""
    _no_extra(extra)
    _approve(approve_write, 'integrated_video')
    wd = _work_dir(work_dir)
    name = _name(name, 'name')
    fps = _int(fps, 1, 60, 'fps')
    width = _int(width, 64, 1920, 'width')
    height = _int(height, 64, 1080, 'height')
    target = wd / name
    if target.exists():
        raise ValueError(f'{target.name} already exists in work_dir; refusing to overwrite')
    built_storyboard = False
    if storyboard is None:
        sb = ROOT / 'examples' / 'demo_v15.json'
        if not sb.is_file():
            sb = wd / (name + '_storyboard.json')
            if sb.exists():
                raise ValueError(f'{sb.name} already exists in work_dir; refusing to overwrite')
            sb.write_text(json.dumps(_MIN_STORYBOARD, ensure_ascii=False, indent=2), encoding='utf-8')
            built_storyboard = True
    else:
        sb = Path(_str(storyboard, 'storyboard', 1024)).expanduser()
        if not sb.is_file() or sb.suffix.lower() != '.json':
            raise ValueError('storyboard must be an existing .json file')
    sb = sb.resolve()
    shots, meta = prepare_project(sb)
    plan = budget(shots, fps=fps, width=width, height=height)
    t0 = time.perf_counter()
    report = render_project(sb, target, fps=fps, width=width, height=height, overwrite=False)
    render_seconds = time.perf_counter() - t0
    video = target / 'video.mp4'
    qa = verify_video(video, expected_fps=fps, width=width, height=height,
                      expected_frames=plan['frames'])
    probe = _ffprobe(video)
    vstreams = [s for s in probe.get('streams', []) if s.get('codec_type') == 'video']
    astreams = [s for s in probe.get('streams', []) if s.get('codec_type') == 'audio']
    v = vstreams[0] if vstreams else {}
    duration = float(probe.get('format', {}).get('duration', 'nan'))
    expected = plan['frames'] / fps
    luma = _first_frame_luma(video)
    checks = {
        'one_video_stream': len(vstreams) == 1,
        'h264': v.get('codec_name') == 'h264',
        'yuv420p': v.get('pix_fmt') == 'yuv420p',
        'even_dimensions': bool(v) and v.get('width', 1) % 2 == 0 and v.get('height', 1) % 2 == 0,
        'size_matches': v.get('width') == width and v.get('height') == height,
        'duration_within_1_frame': math.isfinite(duration) and abs(duration - expected) <= 1.0 / fps + 1e-6,
        'audio_aac_if_present': all(a.get('codec_name') == 'aac' for a in astreams),
        'first_frame_not_black': luma > BLACK_LUMA_MAX,
        'full_decode_verify_video': qa.get('passed') is True,
    }
    digest = _sha256_file(video)
    receipt = {'schema': 'red-rose-e2e-receipt-v26', 'created_utc': _now(), 'video': str(video),
               'sha256': digest, 'bytes': video.stat().st_size, 'duration': duration,
               'expected_duration': expected, 'frames': plan['frames'], 'fps': fps,
               'width': v.get('width'), 'height': v.get('height'), 'codec': v.get('codec_name'),
               'pix_fmt': v.get('pix_fmt'), 'audio_streams': [a.get('codec_name') for a in astreams],
               'first_frame_luma_mean_16x16': round(luma, 3), 'checks': checks,
               'passed': all(checks.values()), 'storyboard': str(sb), 'storyboard_sha256': _sha256_file(sb),
               'storyboard_built_by_op': built_storyboard, 'verify_video_sha256': qa.get('sha256')}
    receipt_path = target / 'receipt.json'
    if receipt_path.exists():
        raise RuntimeError('receipt.json unexpectedly exists; refusing to overwrite')
    receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding='utf-8')
    result = {**receipt, 'receipt': str(receipt_path), 'output_dir': str(target),
              'render_seconds': round(render_seconds, 3), 'shots': plan['shots'],
              'pipeline_manifest_frames': report.get('frames')}
    return _pack('integrated_video', result,
                 ['default storyboard = examples/demo_v15.json (a minimal one is written to work_dir '
                  'only if that file is missing)',
                  'rendering is pipeline_v15.render_project (CairoSVG frames + FFmpeg libx264); QA is '
                  'verify_video (full decode) plus an independent ffprobe pass',
                  f'first frame is "not black" when its 16x16 grey mean luma > {BLACK_LUMA_MAX}',
                  'no audio is added, so the AAC check passes vacuously unless the pipeline adds audio'],
                 ['fps <= 60, 64..1920 x 64..1080, pipeline frame cap 3600',
                  'checks container/stream facts and a black-frame heuristic; it does not judge '
                  'artistic quality (see edit_rubric)',
                  'writes only a new folder <work_dir>/<name> (and at most one storyboard file); '
                  'never overwrites'])


# --------------------------------------------------------------------------- 28.05 devices

VIEWPORTS = {'phone': (390, 844), 'desktop': (1440, 900)}
_CHECKS = {
    'rtl_direction': 'الواجهة من اليمين لليسار: dir=rtl، المحاذاة والأيقونات معكوسة صح',
    'arabic_text': 'النص العربي متصل الحروف، لا مربعات ولا حروف مقطّعة، التشكيل في مكانه',
    'scale_layout': 'لا تمرير أفقي، لا عناصر مقصوصة، المقاس مقروء بدون تكبير',
    'tabs': 'التبويبات تفتح وتُغلق بالترتيب الصحيح، الحالة النشطة واضحة',
    'captions': 'الكابشن العربي داخل المنطقة الآمنة، متزامن، كلام المتكلم بالحرف فقط',
    'touch_or_pointer': 'أهداف اللمس >= 44px على الهاتف، والمؤشر/لوحة المفاتيح على الحاسوب',
}
_SHA_RE = re.compile(r'^[0-9a-f]{64}$')
_DATE_RE = re.compile(r'^\d{4}-\d{2}-\d{2}$')


def _checklist(viewports):
    items = []
    for vname, (w, h) in viewports.items():
        for cid, text in _CHECKS.items():
            items.append({'id': f'{vname}-{w}x{h}/{cid}', 'viewport': vname, 'width': w, 'height': h,
                          'check': cid, 'how_ar': text})
    return items


def device_checklist(*, evidence=None, viewports=None, **extra):
    """RTL/scale checklist for phone 390x844 and desktop 1440x900; validates human evidence only."""
    _no_extra(extra)
    vps = dict(VIEWPORTS)
    if viewports is not None:
        if not isinstance(viewports, dict) or not 1 <= len(viewports) <= 8:
            raise ValueError('viewports must be a dict of 1..8 {name: [width, height]}')
        vps = {}
        for k, v in viewports.items():
            _name(k, 'viewport name')
            if not isinstance(v, (list, tuple)) or len(v) != 2:
                raise ValueError('viewport size must be [width, height]')
            vps[k] = (_int(v[0], 200, 8000, 'width'), _int(v[1], 200, 8000, 'height'))
    items = _checklist(vps)
    ids = [i['id'] for i in items]
    base = {'checklist': items, 'item_count': len(items), 'screenshots_taken_by_module': False}
    if evidence is None:
        result = {**base, 'status': 'needs_human_evidence', 'passed': None,
                  'missing_items': ids,
                  'instructions_ar': 'صوّر كل بند على الجهاز الحقيقي، واحسب sha256 للصورة، وسجّل '
                                     'الجهاز والتاريخ ونجح/فشل لكل بند.'}
    else:
        if not isinstance(evidence, dict) or set(evidence) - {'items'} or 'items' not in evidence:
            raise ValueError("evidence must be {'items': {item_id: {device, date, pass, screenshot_sha256"
                             ", screenshot_file?}}}")
        recs = evidence['items']
        if not isinstance(recs, dict) or len(recs) > 200:
            raise ValueError('evidence.items must be a dict of at most 200 records')
        unknown = sorted(set(recs) - set(ids))
        if unknown:
            raise ValueError('evidence for unknown checklist items: ' + ', '.join(unknown[:5]))
        rows, file_mismatch = [], []
        for iid, rec in recs.items():
            if not isinstance(rec, dict) or set(rec) - {'device', 'date', 'pass', 'screenshot_sha256',
                                                        'screenshot_file', 'note'}:
                raise ValueError(f'evidence[{iid}] has unknown or missing fields')
            device = _str(rec.get('device'), f'{iid}.device', 200)
            date = _str(rec.get('date'), f'{iid}.date', 10)
            if not _DATE_RE.match(date):
                raise ValueError(f'{iid}.date must be YYYY-MM-DD')
            datetime.strptime(date, '%Y-%m-%d')
            ok = _bool(rec.get('pass'), f'{iid}.pass')
            sha = rec.get('screenshot_sha256')
            if not isinstance(sha, str) or not _SHA_RE.match(sha.lower()):
                raise ValueError(f'{iid}.screenshot_sha256 must be 64 hex characters')
            sha = sha.lower()
            file_checked = False
            if rec.get('screenshot_file') is not None:
                f = Path(_str(rec['screenshot_file'], f'{iid}.screenshot_file', 1024)).expanduser()
                if not f.is_file():
                    raise ValueError(f'{iid}.screenshot_file does not exist')
                file_checked = True
                if _sha256_file(f) != sha:
                    file_mismatch.append(iid)
            rows.append({'id': iid, 'device': device, 'date': date, 'pass': ok,
                         'screenshot_sha256': sha, 'file_hash_checked': file_checked})
        missing = [i for i in ids if i not in recs]
        if file_mismatch:
            status = 'rejected_hash_mismatch'
        elif missing:
            status = 'incomplete_evidence'
        else:
            status = 'recorded'
        result = {**base, 'status': status, 'records': rows, 'missing_items': missing,
                  'hash_mismatch_items': file_mismatch,
                  'passed': (all(r['pass'] for r in rows) if status == 'recorded' else None),
                  'failed_items': [r['id'] for r in rows if not r['pass']],
                  'statement': 'the module did not take or view these screenshots; it only records '
                               'the human evidence and checks hashes of files it was given'}
    return _pack('device_checklist', result,
                 ['default viewports: phone 390x844 and desktop 1440x900 (CSS pixels)',
                  'checks: RTL direction, Arabic shaping, scale/no horizontal scroll, tabs, captions, '
                  'touch/pointer targets',
                  "without evidence the status is 'needs_human_evidence' and passed is null, never true"],
                 ['the module never opens a browser or device and never takes screenshots',
                  'a supplied hash proves which file was meant, not what it shows; only files passed as '
                  'screenshot_file are re-hashed'])


# --------------------------------------------------------------------------- 28.06 load

DEFAULT_BUDGETS = {'physics_particles': {'seconds': 60.0, 'peak_mib': 256.0},
                   'geometry_curves': {'seconds': 30.0, 'peak_mib': 128.0},
                   'science_fft': {'seconds': 60.0, 'peak_mib': 128.0}}


def _workload(name, scale):
    caps = scale == 'caps'
    if name == 'physics_particles':
        import physics_v20
        p = ({'count': 500, 'frames': 300, 'substeps': 4} if caps
             else {'count': 50, 'frames': 30, 'substeps': 2})
        return p, lambda: physics_v20.run('particles', dict(p))
    if name == 'geometry_curves':
        import geometry_v20
        n = 256 if caps else 32
        pts = [[math.cos(i / 10) * i, math.sin(i / 10) * i] for i in range(n)]
        p = ({'kind': 'catmull_rom', 'samples': 10000, 'table_size': 20000, 'constant_speed_samples': 10000}
             if caps else {'kind': 'catmull_rom', 'samples': 200, 'table_size': 400,
                           'constant_speed_samples': 100})
        return {**p, 'points': n}, lambda: geometry_v20.run('curves', {**p, 'points': pts})
    import science_v20
    n = 65536 if caps else 1024
    xs = [math.sin(2 * math.pi * 440 * i / 48000) + 0.3 * math.sin(2 * math.pi * 1000 * i / 48000)
          for i in range(n)]
    return ({'samples': n, 'sample_rate': 48000.0, 'peaks': 2},
            lambda: science_v20.run('spectrum', {'samples': xs, 'sample_rate': 48000.0, 'peaks': 2}))


def load_test(*, workloads=None, scale='smoke', budgets=None, **extra):
    """Bounded in-process stress runs; wall time (perf_counter) and peak memory (tracemalloc)."""
    _no_extra(extra)
    scale = _choice(scale, {'caps', 'smoke'}, 'scale')
    names = list(DEFAULT_BUDGETS)
    if workloads is not None:
        if not isinstance(workloads, list) or not 1 <= len(workloads) <= len(names) \
                or len(set(workloads)) != len(workloads):
            raise ValueError(f'workloads must be a list of distinct names from {names}')
        for w in workloads:
            _choice(w, set(names), 'workload')
        names = workloads
    use = {k: dict(v) for k, v in DEFAULT_BUDGETS.items()}
    if budgets is not None:
        if not isinstance(budgets, dict) or set(budgets) - set(DEFAULT_BUDGETS):
            raise ValueError(f'budgets keys must be among {sorted(DEFAULT_BUDGETS)}')
        for k, b in budgets.items():
            if not isinstance(b, dict) or not b or set(b) - {'seconds', 'peak_mib'}:
                raise ValueError(f'budgets[{k}] must be {{seconds?, peak_mib?}}')
            for kk, vv in b.items():
                use[k][kk] = _num(vv, 0, 1e6, f'budgets[{k}].{kk}')
    rows = []
    for name in names:
        size, fn = _workload(name, scale)
        was = tracemalloc.is_tracing()
        if was:
            tracemalloc.reset_peak()
            base = tracemalloc.get_traced_memory()[0]
        else:
            tracemalloc.start()
            base = 0
        try:
            t0 = time.perf_counter()
            out = fn()
            seconds = time.perf_counter() - t0
            peak = tracemalloc.get_traced_memory()[1] - base
        finally:
            if not was:
                tracemalloc.stop()
        del out
        b = use[name]
        peak_mib = peak / 2 ** 20
        exceeded = [k for k, val in (('seconds', seconds), ('peak_mib', peak_mib)) if val > b[k]]
        rows.append({'workload': name, 'size': size, 'seconds': round(seconds, 4),
                     'peak_mib': round(peak_mib, 3), 'peak_bytes': peak, 'budget': b,
                     'within_budget': not exceeded, 'exceeded': exceeded})
    result = {'scale': scale, 'workloads': rows, 'all_within_budget': all(r['within_budget'] for r in rows),
              'python': sys.version.split()[0], 'platform': sys.platform,
              'measured_utc': _now()}
    return _pack('load_test', result,
                 ['caps scale = the documented maxima: physics particles 500x300x4 substeps, Catmull-Rom '
                  '256 points with 10000 samples / 20000-entry table, FFT spectrum of 65536 samples',
                  'time is wall clock with tracemalloc active (tracing adds overhead, so numbers are '
                  'conservative); peak memory counts Python allocations only',
                  'workloads run one after another in this process; numbers vary with machine load'],
                 ['in-process only: no concurrency, GPU, disk or FFmpeg load is measured',
                  'default budgets are generous ceilings for an ordinary laptop, not targets'])


# --------------------------------------------------------------------------- 28.07 privacy

_VENDOR_KINDS = {'aws_access_key_id', 'github_token', 'slack_token', 'google_api_key', 'sk_token'}
_DEMO_MARKERS = ('demo', 'fake', 'placeholder', 'example', 'dummy', 'sample')
_SEQUENCES = ('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789',
              '0123456789' * 4)
_TEXT_SUFFIXES = {'.py', '.md', '.json', '.txt', '.srt', '.csv', '.toml', '.yaml', '.yml', '.ini',
                  '.cfg', '.html', '.css', '.js', '.svg', '.gitignore', ''}
MAX_ZIP_MEMBERS = 20_000
MAX_ZIP_TEXT = 262_144


def _token_at(text, line, column):
    lines = text.splitlines()
    if not 1 <= line <= len(lines):
        return ''
    m = re.match(r'[^\s"\'#,;`]+', lines[line - 1][column - 1:])
    return m.group(0) if m else ''


def _triage(finding, token):
    """Explain a heuristic secret finding, or leave it 'unreviewed' (which blocks a release)."""
    kind, base = finding['kind'], finding['path'].split('/')[-1].split('::')[0]
    low = token.lower()
    is_test = base.startswith('test_') and base.endswith('.py')
    if kind in _VENDOR_KINDS:
        return 'labelled_demo_value' if any(m in low for m in _DEMO_MARKERS) else 'unreviewed'
    if kind == 'private_key_header':
        return 'test_fixture' if is_test else 'unreviewed'
    if re.fullmatch(r'[0-9a-f]{32,}', low.strip('.:`)\'"')):
        return 'hex_digest'
    if any(m in low for m in _DEMO_MARKERS):
        return 'labelled_demo_value'
    if re.search(r'[a-z]{4,}', low) and any(c in token for c in '_/.('):
        return 'identifier_or_path'
    alnum = re.sub(r'[^A-Za-z0-9]', '', token)
    if alnum and (len(set(alnum)) == 1 or any(alnum in s for s in _SEQUENCES)):
        return 'trivial_sequence'
    if is_test:
        return 'test_fixture'
    return 'unreviewed'


def _split_text(name, text, limit):
    if len(text) <= limit:
        return {name: text}
    out, cur, size, n = {}, [], 0, 1
    for line in text.splitlines(keepends=True):
        if cur and size + len(line) > limit:
            out[f'{name}::part{n}'] = ''.join(cur)
            cur, size, n = [], 0, n + 1
        cur.append(line[:limit])
        size += len(line[:limit])
    if cur:
        out[f'{name}::part{n}'] = ''.join(cur)
    return out


def _scan(paths_sizes, texts):
    """distribution_guard + secret_ci_scan (batched) and triage of every secret finding."""
    guard = architecture_v22.distribution_guard(
        paths=[{'path': p, 'size': s} for p, s in paths_sizes])['result']
    pieces = {}
    for name, text in texts.items():
        pieces.update(_split_text(name, text, security_v24.MAX_TEXT))
    plist = [p for p, _ in paths_sizes]
    blocked, findings, truncated = [], [], []
    items = sorted(pieces.items())
    step = security_v24.MAX_SCAN_FILES
    queue = [dict(items[i:i + step]) for i in range(0, len(items), step)]
    while queue:
        chunk = queue.pop()
        r = security_v24.secret_ci_scan(files=chunk, paths=[])['result']
        if r['truncated']:
            # The scanner stops at MAX_FINDINGS: split the batch (or the text) and rescan.
            if len(chunk) > 1:
                keys = sorted(chunk)
                half = len(keys) // 2
                queue += [{k: chunk[k] for k in keys[:half]}, {k: chunk[k] for k in keys[half:]}]
                continue
            (name, text), = chunk.items()
            if len(text) > 2000:
                queue.append(_split_text(name, text, max(1000, len(text) // 2)))
                continue
            truncated.append(name)
        findings += [(f, chunk[f['path']]) for f in r['secret_findings']]
    for i in range(0, len(plist), security_v24.MAX_SCAN_PATHS):
        r = security_v24.secret_ci_scan(files={}, paths=plist[i:i + security_v24.MAX_SCAN_PATHS])['result']
        blocked += r['blocked_paths']
    triaged = []
    for f, text in findings:
        tok = _token_at(text, f['line'], f['column'])
        triaged.append({'path': f['path'], 'line': f['line'], 'kind': f['kind'], 'masked': f['masked'],
                        'triage': _triage(f, tok)})
    unreviewed = [t for t in triaged if t['triage'] == 'unreviewed']
    counts = {}
    for t in triaged:
        counts[t['triage']] = counts.get(t['triage'], 0) + 1
    safe = guard['safe_to_package'] and not blocked and not unreviewed and not truncated
    return {'verdict': 'safe' if safe else 'blocked', 'files': len(paths_sizes),
            'scan_truncated_in': truncated,
            'text_files_scanned': len(texts), 'distribution_flagged': guard['flagged'],
            'blocked_paths': blocked, 'secret_findings': len(triaged), 'triage_counts': counts,
            'unreviewed_findings': unreviewed, 'findings': triaged[:300]}


def _read_text_or_none(data):
    if b'\x00' in data[:4096]:
        return None
    try:
        return data.decode('utf-8')
    except UnicodeDecodeError:
        return None


def release_privacy(*, project=None, zip_path=None, include_project=True, **extra):
    """Privacy gate over the files a release would contain, and optionally over a supplied ZIP."""
    _no_extra(extra)
    include_project = _bool(include_project, 'include_project')
    if not include_project and zip_path is None:
        raise ValueError('nothing to scan: include_project is false and no zip_path given')
    out = {}
    if include_project:
        root = _project(project)
        files, excluded = _release_files(root)
        sizes, texts = [], {}
        for rel in files:
            p = root / rel
            data = p.read_bytes()
            sizes.append((rel, len(data)))
            text = _read_text_or_none(data)
            if text is not None:
                texts[rel] = text
        out['project'] = {**_scan(sizes, texts), 'root': str(root),
                          'gitignore_excluded': len(excluded), 'listed': files}
    if zip_path is not None:
        zp = Path(_str(zip_path, 'zip_path', 1024)).expanduser()
        if not zp.is_file() or not zipfile.is_zipfile(zp):
            raise ValueError('zip_path must be an existing ZIP file')
        sizes, texts = [], {}
        with zipfile.ZipFile(zp) as zf:
            infos = [i for i in zf.infolist() if not i.is_dir()]
            if len(infos) > MAX_ZIP_MEMBERS:
                raise ValueError(f'ZIP has more than {MAX_ZIP_MEMBERS} members')
            for info in infos:
                sizes.append((info.filename, info.file_size))
                if info.file_size <= MAX_ZIP_TEXT:
                    text = _read_text_or_none(zf.read(info))
                    if text is not None:
                        texts[info.filename] = text
        out['zip'] = {**_scan(sizes, texts), 'zip': str(zp.resolve()), 'zip_sha256': _sha256_file(zp)}
    verdict = 'safe' if all(v['verdict'] == 'safe' for v in out.values()) else 'blocked'
    result = {'verdict': verdict, **out}
    return _pack('release_privacy', result,
                 ['release listing = every file under the project except __pycache__/.pytest_cache/.git '
                  'and paths matched by the project .gitignore (fnmatch subset of gitignore syntax)',
                  'paths go through architecture_v22.distribution_guard and security_v24.secret_ci_scan; '
                  'texts through secret_ci_scan (large files split by lines, batched to its caps)',
                  'every heuristic secret finding is triaged: hex_digest, identifier_or_path, '
                  'labelled_demo_value, trivial_sequence, test_fixture (non-vendor patterns inside '
                  'test_*.py) or unreviewed; any unreviewed finding blocks the release',
                  'secret values are never returned, only the masked form from secret_ci_scan'],
                 ['heuristic: encoded, split or binary secrets are not found; triage rules can '
                  'misjudge a real secret that looks like an identifier',
                  f'ZIP members larger than {MAX_ZIP_TEXT} bytes or non-UTF-8 are checked by name/size only',
                  '.gitignore negation (!) and ** patterns are not interpreted'])


# --------------------------------------------------------------------------- 28.08 rubric

RUBRIC = {
    'framing': {1: 'مقصوص الرؤوس/مائل بلا سبب', 3: 'تكوين سليم بلا قصد واضح',
                5: 'كل لقطة مؤطرة لغرضها: ثلث، مساحة نظر، خلفية نظيفة'},
    'colour': {1: 'تفاوت لون وتعريض بين اللقطات، أسود مرفوع', 3: 'متسق مع هفوات بسيطة',
               5: 'تطابق لون وتعريض عبر الفيلم، بشرة طبيعية، لا فلاتر غير مطلوبة'},
    'sound': {1: 'قفزات ارتفاع/تقطيع/صوت ساكت على الآيفون', 3: 'مسموع ومتوازن تقريبًا',
              5: 'جهارة متسقة (LUFS)، انتقالات نظيفة، AAC، بلا تشويش'},
    'story': {1: 'ترتيب بلا خيط', 3: 'بداية ووسط ونهاية مفهومة',
              5: 'إيقاع يخدم القصة، قطع على الحركة والمعنى، نهاية واضحة'},
    'captions_policy': {1: 'نص وصفي أو شرح فوق الفيديو، أو كلمات غير مؤكدة',
                        3: 'كلام المتكلم مع أخطاء توقيت أو إملاء',
                        5: 'كلام المتكلم بالحرف فقط (أو لا شيء)، متزامن، عربي متصل صحيح'},
}


def edit_rubric(*, reviews=None, reference=None, **extra):
    """Aggregate human 1-5 scores per criterion; needs a licensed reference comparison note."""
    _no_extra(extra)
    criteria = list(RUBRIC)
    if reviews is None or reviews == []:
        result = {'status': 'needs_human_review', 'rubric': RUBRIC, 'criteria': criteria,
                  'reviewers': 0, 'scored_by_module': False}
    else:
        if not isinstance(reviews, list) or len(reviews) > 50:
            raise ValueError('reviews must be a list of at most 50 {reviewer, scores, note?}')
        names = []
        for i, r in enumerate(reviews):
            if not isinstance(r, dict) or set(r) - {'reviewer', 'scores', 'note'} or 'scores' not in r:
                raise ValueError(f'reviews[{i}] must be {{reviewer, scores, note?}}')
            names.append(_str(r.get('reviewer'), f'reviews[{i}].reviewer', 100).strip().casefold())
            s = r['scores']
            if not isinstance(s, dict) or set(s) != set(criteria):
                raise ValueError(f'reviews[{i}].scores must score exactly {criteria}')
            for c, v in s.items():
                _int(v, 1, 5, f'reviews[{i}].scores.{c}')
        if len(set(names)) != len(names):
            raise ValueError('each reviewer may submit only one review')
        ref_problem = None
        if not isinstance(reference, dict) or set(reference) - {'title', 'licence', 'note', 'source'}:
            ref_problem = 'a reference {title, licence, note, source?} is required'
        else:
            lic = reference.get('licence')
            if not isinstance(lic, str) or not lic.strip() or lic.strip().casefold() in (
                    'unknown', 'none', 'unlicensed', 'n/a', '?'):
                ref_problem = 'reference licence missing or unknown'
            elif not isinstance(reference.get('title'), str) or not reference['title'].strip():
                ref_problem = 'reference title missing'
            elif not isinstance(reference.get('note'), str) or len(reference['note'].strip()) < 10:
                ref_problem = 'reference comparison note missing (>= 10 characters)'
        if ref_problem:
            result = {'status': 'rejected', 'reason': ref_problem, 'reviewers': len(reviews),
                      'rubric': RUBRIC}
        else:
            per = {}
            for c in criteria:
                vals = [r['scores'][c] for r in reviews]
                mean = sum(vals) / len(vals)
                sd = math.sqrt(sum((v - mean) ** 2 for v in vals) / len(vals))
                per[c] = {'mean': round(mean, 3), 'min': min(vals), 'max': max(vals),
                          'spread': max(vals) - min(vals), 'stdev_population': round(sd, 3),
                          'disagreement': max(vals) - min(vals) >= 2}
            overall = sum(p['mean'] for p in per.values()) / len(per)
            weakest = min(per, key=lambda c: per[c]['mean'])
            result = {'status': 'reviewed' if len(reviews) >= 2 else 'single_reviewer',
                      'reviewers': len(reviews), 'per_criterion': per,
                      'overall_mean': round(overall, 3), 'weakest_criterion': weakest,
                      'max_spread': max(p['spread'] for p in per.values()),
                      'disagreements': [c for c in criteria if per[c]['disagreement']],
                      'reference': {'title': reference['title'].strip(),
                                    'licence': reference['licence'].strip(),
                                    'note': reference['note'].strip()[:1000]},
                      'rubric': RUBRIC, 'scored_by_module': False}
    return _pack('edit_rubric', result,
                 ['criteria: framing, colour, sound, story, captions_policy; integer scores 1-5 with '
                  'anchors at 1, 3 and 5',
                  'spread = max - min per criterion; population standard deviation; spread >= 2 is '
                  'flagged as disagreement',
                  'a licensed reference (title, licence, comparison note) is required before scores '
                  'are aggregated'],
                 ['the module never scores footage itself; with no human scores the status is '
                  "'needs_human_review'",
                  'one reviewer gives status single_reviewer: no inter-rater spread is meaningful',
                  'the licence text is recorded as given; it is not verified'])


# --------------------------------------------------------------------------- 28.09 release

_CHILD_ROSE = (
    "import sys, runpy\n"
    "d = sys.argv[1]\n"
    "sys.path.insert(0, d)\n"
    "sys.argv = [d + '/rose.py'] + sys.argv[2:]\n"
    "runpy.run_path(d + '/rose.py', run_name='__main__')\n"
)

INSTALL_TEXT = """Red Rose portable release
=========================
1. Extract this ZIP anywhere (it creates a red-rose/ folder).
2. Needs Python 3.12+, FFmpeg + FFprobe on PATH, and CairoSVG for rendering.
3. Check integrity: every file's sha256 is listed in red-rose/MANIFEST.json.
4. Smoke test:  cd red-rose  &&  python -X utf8 rose.py capabilities
5. Your private memory is NOT included: set RED_ROSE_DB to your own path.

الوردة الحمراء — إصدار محمول
فك الضغط، ثبّت بايثون 3.12 وFFmpeg وCairoSVG، تحقق من الهاشات في MANIFEST.json،
ثم شغّل: python -X utf8 rose.py capabilities . الذاكرة الخاصة غير مضمّنة.
"""


def _run_rose(folder, args, db_dir, timeout=SUBPROCESS_TIMEOUT):
    # db_dir doubles as the throw-away home folder, so nothing touches the real ~/.red-rose.
    env = _clean_env(db_dir, {'RED_ROSE_DB': str(Path(db_dir) / 'memory.sqlite3')})
    proc = subprocess.run([sys.executable, '-I', '-X', 'utf8', '-B', '-c', _CHILD_ROSE, str(folder), *args],
                          capture_output=True, text=True, encoding='utf-8', errors='replace',
                          timeout=timeout, cwd=str(folder), env=env)
    return proc


def portable_release(*, work_dir=None, approve_write=False, name='red-rose-release.zip', **extra):
    """ZIP of the source + MANIFEST.json + INSTALL.txt; re-extract, verify hashes, smoke-test rose.py."""
    _no_extra(extra)
    _approve(approve_write, 'portable_release')
    wd = _work_dir(work_dir)
    name = _name(name, 'name', '.zip')
    target = wd / name
    if target.exists():
        raise ValueError(f'{name} already exists in work_dir; refusing to overwrite')
    files, excluded = _release_files(ROOT, _RELEASE_EXCLUDE, _RELEASE_EXCLUDE_DIRS)
    manifest = {'schema': 'red-rose-release-manifest-v26', 'created_utc': _now(),
                'python_built_with': sys.version.split()[0], 'files': {}}
    t0 = time.perf_counter()
    with zipfile.ZipFile(target, 'x', compression=zipfile.ZIP_DEFLATED) as zf:
        for rel in files:
            data = (ROOT / rel).read_bytes()
            manifest['files'][rel] = {'sha256': _sha256_bytes(data), 'bytes': len(data)}
            zf.writestr('red-rose/' + rel, data)
        manifest['file_count'] = len(manifest['files'])
        zf.writestr('red-rose/INSTALL.txt', INSTALL_TEXT.encode('utf-8'))
        zf.writestr('red-rose/MANIFEST.json', json.dumps(manifest, ensure_ascii=False, indent=1).encode('utf-8'))
    zip_sha = _sha256_file(target)

    cr = _registry()
    expected_adapters = len(cr.REGISTRY)
    with tempfile.TemporaryDirectory(prefix='rr_restore_') as tmp, \
            tempfile.TemporaryDirectory(prefix='rr_db_') as dbdir:
        dest = Path(tmp)
        with zipfile.ZipFile(target) as zf:
            for info in zf.infolist():
                parts = info.filename.replace('\\', '/').split('/')
                if info.filename.startswith(('/', '\\')) or '..' in parts or ':' in parts[0]:
                    raise RuntimeError(f'unsafe member name in release: {info.filename!r}')
            zf.extractall(dest)
        root = dest / 'red-rose'
        restored = json.loads((root / 'MANIFEST.json').read_text(encoding='utf-8'))
        mismatched = [rel for rel, meta in restored['files'].items()
                      if not (root / rel).is_file() or _sha256_file(root / rel) != meta['sha256']]
        on_disk = {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()}
        unexpected = sorted(on_disk - set(restored['files']) - {'MANIFEST.json', 'INSTALL.txt'})
        proc = _run_rose(root, ['capabilities'], dbdir)
        adapters, ready = None, None
        if proc.returncode == 0:
            try:
                caps = json.loads(proc.stdout)
                adapters = len(caps)
                ready = sum(1 for c in caps if c.get('ready'))
            except ValueError:
                adapters = None
        smoke = {'exit_code': proc.returncode, 'adapters': adapters, 'ready': ready,
                 'expected_adapters': expected_adapters,
                 'stderr_tail': proc.stderr[-800:] if proc.returncode else '',
                 'db_created': (Path(dbdir) / 'memory.sqlite3').exists()}
    seconds = time.perf_counter() - t0
    checks = {'hashes_verified': not mismatched, 'no_unexpected_files': not unexpected,
              'smoke_exit_0': smoke['exit_code'] == 0,
              'adapter_count_matches': adapters == expected_adapters}
    result = {'zip': str(target), 'zip_sha256': zip_sha, 'zip_bytes': target.stat().st_size,
              'files': len(files), 'excluded': excluded, 'manifest_entries': len(manifest['files']),
              'mismatched': mismatched, 'unexpected': unexpected, 'smoke_test': smoke,
              'checks': checks, 'passed': all(checks.values()), 'seconds': round(seconds, 3)}
    return _pack('portable_release', result,
                 ['contents = project files minus __pycache__/caches, .gitignore matches and hard '
                  'exclusions (*.sqlite*, *.db, *.pyc, audio/video media, .env*, owner-memory/, private/, '
                  'credentials/, media/); questions/G*.json drafts are included',
                  'verification extracts into a fresh temporary folder, re-hashes every file and runs '
                  'rose.py capabilities with `python -I -X utf8 -B`, a scrubbed environment and a '
                  'temporary RED_ROSE_DB; the extracted folder is the only project path on sys.path',
                  'the temporary extraction and DB folders are deleted afterwards; only the ZIP stays'],
                 ['the smoke test proves the CLI starts and lists adapters from the extracted copy, not '
                  'that every adapter works there',
                  'third-party packages (CairoSVG, Pillow) and FFmpeg are not bundled',
                  'writes exactly one new file <work_dir>/<name>; refuses to overwrite'])


# --------------------------------------------------------------------------- 28.10 handoff

def _sections(md):
    out = []
    for m in re.finditer(r'(?m)^##\s+(\d+)\.\s*(.*)$', md):
        out.append((int(m.group(1)), m.group(2).strip(), m.start()))
    res = []
    for i, (num, title, start) in enumerate(out):
        end = out[i + 1][2] if i + 1 < len(out) else len(md)
        res.append({'number': num, 'title': title, 'text': md[start:end]})
    return res


def _commands(text):
    cmds = []
    for block in re.findall(r'```(?:bash|sh|text)?\n(.*?)```', text, flags=re.S):
        for line in block.splitlines():
            line = line.split('#')[0].strip()
            for seg in line.split('&&'):
                seg = seg.strip()
                if seg:
                    cmds.append(seg)
    return cmds


def handoff_resume(*, run_command=True, **extra):
    """Parse the latest roadmap handoff section + START_NEXT_AGENT.md and run the resume command."""
    _no_extra(extra)
    run_command = _bool(run_command, 'run_command')
    handoff = ROOT / 'NEXT_AGENT_HANDOFF.md'
    start = ROOT / 'START_NEXT_AGENT.md'
    if not handoff.is_file() or not start.is_file():
        raise ValueError('NEXT_AGENT_HANDOFF.md and START_NEXT_AGENT.md must exist in the project')
    md = handoff.read_text(encoding='utf-8')
    secs = _sections(md)
    roadmap_secs = [s for s in secs if re.search(r'1[,٬]?400', s['title'])]
    if not roadmap_secs:
        raise ValueError('no roadmap (1,400) section found in NEXT_AGENT_HANDOFF.md')
    latest = max(roadmap_secs, key=lambda s: s['number'])
    sec_cmds = _commands(latest['text'])
    start_text = start.read_text(encoding='utf-8')
    start_cmds = _commands(start_text)
    wanted = 'python rose.py roadmap'
    in_section = any(c == wanted for c in sec_cmds)
    in_start = any(c == wanted for c in start_cmds)
    rose_src = (ROOT / 'rose.py').read_text(encoding='utf-8')
    subcommand_exists = bool(re.search(r"add_parser\(\s*['\"]roadmap['\"]\s*\)", rose_src))
    snap = re.search(r'(\d[\d,]*)\s*من\s*1,400', latest['text'])
    documented_answered = int(snap.group(1).replace(',', '')) if snap else None

    template = next((s for s in secs if s['number'] == 6), None)
    template_check = None
    if template is not None:
        block = re.search(r'```text\n(.*?)```', template['text'], flags=re.S)
        if block:
            labels = [ln.strip().rstrip(':').strip() for ln in block.group(1).splitlines() if ln.strip()]
            filled = '\n'.join(f'{lab}: x' for lab in labels)
            hc = agents_v22.run('handoff_check', {'text': filled})['result']
            template_check = {'labels': len(labels), 'fields_recognised': 12 - len(hc['missing']),
                              'missing_fields': hc['missing']}

    run = None
    if run_command:
        with tempfile.TemporaryDirectory(prefix='rr_db_') as dbdir:
            proc = _run_rose(ROOT, ['roadmap'], dbdir)
            payload = None
            if proc.returncode == 0:
                try:
                    payload = json.loads(proc.stdout)
                except ValueError:
                    payload = None
        run = {'command': wanted, 'exit_code': proc.returncode,
               'stderr_tail': proc.stderr[-800:] if proc.returncode else ''}
        if payload is not None:
            run.update({'topics': payload.get('topics'), 'questions': payload.get('questions'),
                        'answered': payload.get('questions_answered_in_tested_code'),
                        'remaining': payload.get('questions_remaining'),
                        'complete': payload.get('complete'),
                        'source_sha256': payload.get('source_sha256')})
    resumable = (in_section and in_start and subcommand_exists and
                 (run is None or (run['exit_code'] == 0 and run.get('topics') == 280)))
    result = {'resumable_without_questions': resumable,
              'latest_roadmap_section': {'number': latest['number'], 'title': latest['title'],
                                         'commands': sec_cmds[:20]},
              'documented_first_command': wanted, 'in_handoff_section': in_section,
              'in_start_next_agent': in_start, 'cli_subcommand_exists': subcommand_exists,
              'documented_answered_snapshot': documented_answered,
              'snapshot_is_stale': (documented_answered is not None and run is not None
                                    and run.get('answered') is not None
                                    and documented_answered != run['answered']),
              'handoff_template': template_check, 'run': run}
    return _pack('handoff_resume', result,
                 ['latest roadmap section = highest-numbered "## N." heading of NEXT_AGENT_HANDOFF.md '
                  'whose title mentions 1,400',
                  'commands are read from fenced code blocks; "a && b" is split into steps',
                  'the resume command runs as `python -I -X utf8 -B` in the project folder with a '
                  'scrubbed environment and a temporary RED_ROSE_DB (rose.py roadmap only reads)',
                  'the section-6 template is checked by agents_v22.handoff_check on placeholder values'],
                 ['snapshot numbers written in the handoff can be stale; the live command output is '
                  'the source of truth',
                  'does not check git branch, HEAD or CI state (no git access)'])


# --------------------------------------------------------------------------- dispatcher

OPS = {
    'independence_audit': independence_audit,
    'registry_reality': registry_reality,
    'closure_matrix': closure_matrix,
    'integrated_video': integrated_video,
    'device_checklist': device_checklist,
    'load_test': load_test,
    'release_privacy': release_privacy,
    'edit_rubric': edit_rubric,
    'portable_release': portable_release,
    'handoff_resume': handoff_resume,
}

EFFECTS = {op: 'read' for op in OPS}
EFFECTS.update({'integrated_video': 'write', 'portable_release': 'write'})


def run(op, params=None):
    """Validate and dispatch: run('closure_matrix', {'rows': 'none'}) -> {'op','result','assumptions','limits'}."""
    if not isinstance(op, str) or op not in OPS:
        raise ValueError(f'op must be one of {sorted(OPS)}')
    if params is None:
        params = {}
    if not isinstance(params, dict):
        raise ValueError('params must be a dict')
    if len(params) > MAX_PARAMS:
        raise ValueError(f'params may have at most {MAX_PARAMS} keys')
    if not all(isinstance(key, str) for key in params):
        raise ValueError('param names must be strings')
    out = OPS[op](**params)
    try:
        json.dumps(out, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f'{op} produced a non-JSON-serialisable result: {exc}') from exc
    return out
