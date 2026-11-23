"""Red Rose V29 packaging (W10): check-skill, pack, pack-verify, install-skill.

Policy lives in PACKAGE_MANIFEST.json (an allowlist, not shipped as is).
pack writes red-rose.skill: a zip with one top folder ``red-rose/`` holding the
allowlisted files plus a generated ``red-rose/PACKAGE_MANIFEST.json`` (file list,
sha256 per file, version, no dates).

Nothing here opens the owner's private database or its store. Writes need
--approve-write; without it the command exits 3 and writes nothing.
Exit codes follow rose_io: 0 ok, 1 error, 2 usage, 3 approval_required.
"""
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

import rose_io as rio

ROOT = Path(__file__).resolve().parent
POLICY_FILE = ROOT / 'PACKAGE_MANIFEST.json'
GENERATED_NAME = 'PACKAGE_MANIFEST.json'
PACK_DIR = 'red-rose'
MANIFEST_SCHEMA = 'red-rose/package-manifest/1'


class PackError(Exception):
    """A packaging rule failed; the message is shown to the owner as is."""


def load_policy(path=POLICY_FILE):
    try:
        data = json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        raise PackError(f'policy unreadable: {type(exc).__name__}: {exc}') from exc
    for key in ('root_files_required', 'dirs', 'exclude_dir_names', 'exclude_file_names', 'limits', 'scan'):
        if key not in data:
            raise PackError(f'policy missing key: {key}')
    return data


def _excluded(rel, policy):
    """True when a relative posix path must never be packed (name or folder rules)."""
    parts = rel.split('/')
    if any(p in policy['exclude_dir_names'] for p in parts[:-1]):
        return True
    name = parts[-1]
    return any(fnmatch.fnmatchcase(name, pat) for pat in policy['exclude_file_names'])


def collect(root=ROOT, policy=None):
    """Allowlisted files -> {files: [rel], problems: [str], skipped: int, bytes: int}."""
    policy = policy or load_policy()
    root = Path(root)
    found, problems, skipped = set(), [], 0
    for name in policy['root_files_required']:
        if not (root / name).is_file():
            problems.append(f'missing required file: {name}')
        else:
            found.add(name)
    for name in policy.get('root_files_optional', []):
        if (root / name).is_file():
            found.add(name)
    py = policy.get('root_python', {})
    for path in sorted(root.iterdir()):
        if path.is_file() and path.suffix == py.get('include_suffix', '.py'):
            if any(fnmatch.fnmatchcase(path.name, pat) for pat in py.get('exclude_names', [])):
                skipped += 1
                continue
            found.add(path.name)
    for name in policy.get('root_json', []):
        if (root / name).is_file():
            found.add(name)
    for folder in policy['dirs']:
        base = root / folder
        if not base.is_dir():
            problems.append(f'missing folder: {folder}/')
            continue
        for path in sorted(base.rglob('*')):
            if not path.is_file():
                continue
            rel = path.relative_to(root).as_posix()
            if _excluded(rel, policy):
                skipped += 1
                continue
            found.add(rel)
    files = sorted(found)
    limits = policy['limits']
    total = 0
    for rel in files:
        size = (root / rel).stat().st_size
        total += size
        if size > limits['max_file_bytes']:
            problems.append(f'file over {limits["max_file_bytes"]} bytes: {rel} ({size})')
    if total > limits['max_total_bytes']:
        problems.append(f'package over {limits["max_total_bytes"]} bytes: {total}')
    return {'files': files, 'problems': problems, 'skipped': skipped, 'bytes': total}


def _text_files(files, policy):
    suffixes = tuple(policy.get('text_suffixes', []))
    return [rel for rel in files if rel.lower().endswith(suffixes)]


def scan_text(rel, text, policy):
    """Findings for one text file: secrets, user-profile paths, legacy imports (.py)."""
    findings = []
    scan = policy['scan']
    groups = [('secret', scan['secret_patterns']), ('profile_path', scan['profile_path_patterns'])]
    if rel.endswith('.py'):
        groups.append(('legacy_import', scan['legacy_import_patterns']))
    for kind, patterns in groups:
        for pat in patterns:
            match = re.search(pat, text)
            if match:
                line = text.count('\n', 0, match.start()) + 1
                findings.append({'file': rel, 'rule': kind, 'line': line, 'pattern': pat[:60]})
                break
    return findings


def scan_files(root, files, policy):
    findings = []
    for rel in _text_files(files, policy):
        try:
            text = (Path(root) / rel).read_bytes().decode('utf-8', errors='replace')
        except OSError as exc:
            findings.append({'file': rel, 'rule': 'unreadable', 'line': 0, 'pattern': str(exc)[:60]})
            continue
        findings.extend(scan_text(rel, text, policy))
    return findings


def _sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def _version():
    try:
        import rose_env
        return rose_env.SKILL_VERSION, rose_env._commit()
    except Exception:  # keep packing even if the env module cannot load
        return 'unknown', None


def build_manifest(root, files):
    version, commit = _version()
    entries = []
    for rel in files:
        data = (Path(root) / rel).read_bytes()
        entries.append({'path': rel, 'bytes': len(data), 'sha256': _sha256_bytes(data)})
    return {
        'schema': MANIFEST_SCHEMA,
        'name': 'red-rose',
        'version': version,
        'commit': commit,
        'file_count': len(entries),
        'total_bytes': sum(e['bytes'] for e in entries),
        'files': entries,
    }


def _stamp():
    return datetime.now().strftime('%Y%m%d-%H%M%S')


def _out(obj, code):
    rio.emit(obj)
    return code


def _check_pack(root=ROOT):
    """Shared gate for pack and install: returns (plan, error_doc or None)."""
    policy = load_policy()
    plan = collect(root, policy)
    if plan['problems']:
        return plan, {'ok': False, 'outcome': 'error', 'error': 'packaging rules failed',
                      'problems': plan['problems']}
    findings = scan_files(root, plan['files'], policy)
    if findings:
        return plan, {'ok': False, 'outcome': 'error', 'error': 'content scan found forbidden material',
                      'findings': findings[:50],
                      'hint': 'remove or move the file (never print the value), then run check-skill again'}
    return plan, None


def _guard(fn):
    """Turn a PackError into one JSON error line with exit 1 (never a traceback)."""
    def inner(args):
        try:
            return fn(args)
        except PackError as exc:
            return _out({'ok': False, 'outcome': 'error', 'error': str(exc)}, 1)
    inner.__name__ = fn.__name__
    return inner


# ---------------------------------------------------------------- check-skill

def check_skill(root=ROOT):
    policy = load_policy()
    plan = collect(root, policy)
    findings = scan_files(root, plan['files'], policy) if not plan['problems'] else []
    sizes = sorted(((rel, (Path(root) / rel).stat().st_size) for rel in plan['files']),
                   key=lambda x: -x[1])
    ok = not plan['problems'] and not findings
    return {
        'ok': ok, 'outcome': 'ok' if ok else 'error', 'command': 'check-skill',
        'files': len(plan['files']), 'bytes': plan['bytes'], 'skipped': plan['skipped'],
        'largest': [{'path': r, 'bytes': s} for r, s in sizes[:10]],
        'problems': plan['problems'], 'findings': findings[:50],
        'archive': policy['archive'], 'read_only': True,
    }


@_guard
def _h_check_skill(args):
    doc = check_skill()
    return _out(doc, 0 if doc['ok'] else 1)


# ---------------------------------------------------------------- pack

def pack(out_dir, approve_write=False, root=ROOT):
    """Build <out_dir>/red-rose.skill. Returns (doc, exit_code)."""
    policy = load_policy()
    target = Path(out_dir).resolve() / policy['archive']
    rerun = f'rose.py pack --out {out_dir} --approve-write'
    if not approve_write:
        return ({'ok': False, 'outcome': 'approval_required', 'command': 'pack', 'nothing_written': True,
                  'would_write': [str(target)], 'rerun_with': rerun}, 3)
    plan, err = _check_pack(root)
    if err:
        return err, 1
    if target.exists():
        return ({'ok': False, 'outcome': 'error', 'error': 'archive already exists; choose a new --out folder',
                 'path': str(target)}, 1)
    manifest = build_manifest(root, plan['files'])
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix('.skill.tmp')
    with zipfile.ZipFile(tmp, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        for rel in plan['files']:
            zf.write(Path(root) / rel, arcname=f'{PACK_DIR}/{rel}')
        zf.writestr(f'{PACK_DIR}/{GENERATED_NAME}',
                    json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=False) + '\n')
    os.replace(tmp, target)
    return ({
        'ok': True, 'outcome': 'ok', 'command': 'pack', 'path': str(target),
        'files': manifest['file_count'] + 1, 'bytes': target.stat().st_size,
        'uncompressed_bytes': manifest['total_bytes'], 'sha256': _sha256_file(target),
        'version': manifest['version'], 'commit': manifest['commit'],
        'next': [f'rose.py pack-verify "{target}"'],
    }, 0)


def _sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


@_guard
def _h_pack(args):
    doc, code = pack(args.out, approve_write=args.approve_write)
    return _out(doc, code)


# ---------------------------------------------------------------- pack-verify

def _archive_problems(zf, policy):
    problems = []
    names = zf.namelist()
    for name in names:
        if name.startswith('/') or '..' in name.split('/') or '\\' in name:
            problems.append(f'unsafe entry name: {name}')
    tops = {n.split('/')[0] for n in names if n}
    if tops != {PACK_DIR}:
        problems.append(f'top folder must be only {PACK_DIR}/, found {sorted(tops)[:5]}')
    try:
        manifest = json.loads(zf.read(f'{PACK_DIR}/{GENERATED_NAME}').decode('utf-8'))
    except (KeyError, ValueError) as exc:
        return problems + [f'manifest unreadable: {type(exc).__name__}'], None
    listed = {e['path']: e for e in manifest.get('files', [])}
    for rel, entry in listed.items():
        member = f'{PACK_DIR}/{rel}'
        if member not in names:
            problems.append(f'listed file missing: {rel}')
            continue
        data = zf.read(member)
        if _sha256_bytes(data) != entry['sha256'] or len(data) != entry['bytes']:
            problems.append(f'hash mismatch: {rel}')
        if _excluded(rel, policy):
            problems.append(f'forbidden name in archive: {rel}')
    for name in names:
        if name.endswith('/'):
            continue
        rel = name[len(PACK_DIR) + 1:] if name.startswith(PACK_DIR + '/') else name
        if rel == GENERATED_NAME:
            continue
        if rel not in listed:
            problems.append(f'unlisted entry: {rel}')
    if names.count(f'{PACK_DIR}/SKILL.md') != 1:
        problems.append('red-rose/SKILL.md must appear exactly once')
    return problems, manifest


def _archive_findings(zf, names, policy):
    findings = []
    for rel in _text_files([n[len(PACK_DIR) + 1:] for n in names if n.startswith(PACK_DIR + '/')
                            and not n.endswith('/')], policy):
        if rel == GENERATED_NAME:
            continue
        text = zf.read(f'{PACK_DIR}/{rel}').decode('utf-8', errors='replace')
        findings.extend(scan_text(rel, text, policy))
    return findings


def pack_verify(archive, timeout=900):
    policy = load_policy()
    path = Path(archive)
    if not path.is_file():
        return {'ok': False, 'outcome': 'error', 'error': f'archive not found: {path}'}, 1
    try:
        zf = zipfile.ZipFile(path)
    except zipfile.BadZipFile:
        return {'ok': False, 'outcome': 'error', 'error': 'not a zip archive'}, 1
    with zf:
        problems, manifest = _archive_problems(zf, policy)
        findings = _archive_findings(zf, zf.namelist(), policy) if manifest else []
        if problems or findings or manifest is None:
            return ({'ok': False, 'outcome': 'error', 'command': 'pack-verify', 'archive': str(path),
                     'problems': problems[:50], 'findings': findings[:50]}, 1)
        work = Path(tempfile.mkdtemp(prefix='red-rose-verify-'))
        steps = []
        try:
            zf.extractall(work)
            skill = work / PACK_DIR
            env = dict(os.environ)
            env['RED_ROSE_DB'] = str(work / 'verify.sqlite3')
            env['PYTHONDONTWRITEBYTECODE'] = '1'
            for words in policy['verify_commands']:
                cmd = [sys.executable, '-X', 'utf8', str(skill / 'rose.py'), *words]
                try:
                    proc = subprocess.run(cmd, capture_output=True, timeout=timeout, env=env, cwd=str(skill))
                    rc, out = proc.returncode, proc.stdout.decode('utf-8', errors='replace')
                except subprocess.TimeoutExpired:
                    rc, out = 124, ''
                step = {'command': ' '.join(words), 'exit': rc, 'stdout_bytes': len(out)}
                if words[0] == 'selfcheck' and out.strip():
                    try:
                        report = json.loads(out)
                        step['totals'] = report.get('totals')
                        step['failed_ops'] = report.get('failed', [])
                    except ValueError:
                        step['failed_ops'] = ['selfcheck output not JSON']
                steps.append(step)
        finally:
            shutil.rmtree(work, ignore_errors=True)
    ok = all(s['exit'] == 0 for s in steps)
    doc = {'ok': ok, 'outcome': 'ok' if ok else 'error', 'command': 'pack-verify', 'archive': str(path),
           'version': manifest.get('version'), 'files': manifest.get('file_count'),
           'manifest_hashes': 'ok', 'forbidden_names': 'none', 'content_scan': 'no findings',
           'steps': steps, 'work_folder_removed': True}
    return doc, 0 if ok else 1


@_guard
def _h_pack_verify(args):
    doc, code = pack_verify(args.archive)
    return _out(doc, code)


# ---------------------------------------------------------------- install-skill

def default_target():
    return Path.home() / '.claude' / 'skills' / 'red-rose'


def backup_dir(target):
    """Where an existing copy is moved. Never inside a Claude `skills` folder:
    a backup there still has SKILL.md and Claude loads it as a second skill."""
    target = Path(target)
    if target.parent.name.lower() == 'skills':
        return Path.home() / '.claude' / 'red-rose-backups'
    return target.parent


def install_skill(target=None, approve_write=False, root=ROOT):
    target = Path(target).resolve() if target else default_target().resolve()
    root = Path(root).resolve()
    if target == root or root in target.parents or target in root.parents:
        return ({'ok': False, 'outcome': 'error',
                 'error': 'target overlaps the working folder; choose another --target'}, 1)
    backup_guess = None
    if target.exists():
        backup_guess = str(backup_dir(target) / f'red-rose.backup-{_stamp()}')
    rerun = 'rose.py install-skill --approve-write' + (f' --target "{target}"' if target else '')
    if not approve_write:
        return ({'ok': False, 'outcome': 'approval_required', 'command': 'install-skill',
                 'nothing_written': True, 'would_write': [str(target)],
                 'existing_copy_moved_to': backup_guess, 'rerun_with': rerun}, 3)
    plan, err = _check_pack(root)
    if err:
        return err, 1
    stamp = _stamp()
    staging = target.parent / f'red-rose.staging-{stamp}'
    if staging.exists():
        return ({'ok': False, 'outcome': 'error', 'error': 'staging folder exists; retry in a second'}, 1)
    manifest = build_manifest(root, plan['files'])
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        for rel in plan['files']:
            dst = staging / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(root / rel, dst)
        (staging / GENERATED_NAME).write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        backup = None
        if target.exists():
            bdir = backup_dir(target)
            bdir.mkdir(parents=True, exist_ok=True)
            backup = bdir / f'red-rose.backup-{stamp}'
            n = 2
            while backup.exists():
                backup = bdir / f'red-rose.backup-{stamp}-{n}'
                n += 1
            os.replace(target, backup)
        os.replace(staging, target)
    except OSError as exc:
        shutil.rmtree(staging, ignore_errors=True)
        return ({'ok': False, 'outcome': 'error', 'error': f'install failed: {type(exc).__name__}: {exc}'}, 1)
    return ({
        'ok': True, 'outcome': 'ok', 'command': 'install-skill', 'installed_to': str(target),
        'version': manifest['version'], 'commit': manifest['commit'], 'files': manifest['file_count'],
        'backup': str(backup) if backup else None,
        'note': 'the backup folder keeps its old SKILL.md; delete it yourself when no longer needed',
    }, 0)


@_guard
def _h_install(args):
    doc, code = install_skill(args.target, approve_write=args.approve_write)
    return _out(doc, code)


# ---------------------------------------------------------------- CLI wiring

def register(subparsers):
    p = subparsers.add_parser(
        'check-skill', help='read only: list the files a red-rose.skill would hold, sizes, and the content scan')
    p.set_defaults(ext_func=_h_check_skill)
    rio.json_usage_errors(p)

    p = subparsers.add_parser(
        'pack', help='build red-rose.skill into --out (write: needs --approve-write)',
        description='Build a lean red-rose.skill zip. Without --approve-write: exit 3, nothing written.')
    p.add_argument('--out', required=True, metavar='DIR', help='folder that receives red-rose.skill (must not exist as a file)')
    p.add_argument('--approve-write', action='store_true', help='the owner approved writing the archive')
    p.set_defaults(ext_func=_h_pack)
    rio.json_usage_errors(p)

    p = subparsers.add_parser(
        'pack-verify', help='check a red-rose.skill: hashes, forbidden names, then run it from a temp copy')
    p.add_argument('archive', metavar='FILE', help='path to red-rose.skill')
    p.set_defaults(ext_func=_h_pack_verify)
    rio.json_usage_errors(p)

    p = subparsers.add_parser(
        'install-skill', help='copy the skill into ~/.claude/skills/red-rose (write: needs --approve-write)',
        description='Copies the skill. An existing copy is moved to a dated backup beside it, never deleted.')
    p.add_argument('--target', metavar='DIR', default=None, help='default: ~/.claude/skills/red-rose')
    p.add_argument('--approve-write', action='store_true', help='the owner approved the install')
    p.set_defaults(ext_func=_h_install)
    rio.json_usage_errors(p)
    return subparsers
