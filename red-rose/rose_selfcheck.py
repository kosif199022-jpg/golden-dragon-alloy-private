"""Red Rose V29 (W03): run the catalogue's runnable examples and record what really passed.

selfcheck runs every op that the catalogue says runs with defaults (read ops only) as a
separate child process `rose_run.py run ID` with a bounded timeout, inside a temp folder
and a temp database, never with --approve-write. Each write op is called once WITHOUT
approval and must answer approval_required while leaving its folder unchanged. Ops that
need input, the owner PC, the network or an external program are not executed; they are
listed with their status. Nothing is written unless --save-status --approve-write is given,
and then only references/VERIFIED_STATUS.json (no dates, no timings in that file).

sample-media writes the synthetic fixtures (rose_fixtures.make) only with --approve-write.
"""
from __future__ import annotations

import concurrent.futures as cf
import hashlib
import importlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import rose_env
import rose_fixtures
import rose_io as rio

ROOT = rose_env.ROOT
RUNNER = ROOT / 'rose_run.py'
STATUS_SCHEMA = 'red-rose/verified-status/1'
TOTAL_KEYS = ('verified', 'runs_with_defaults', 'needs_input', 'not_run_needs_approval',
              'unavailable_here', 'failed')
SAVED_STATUSES = ('verified', 'runs_with_defaults', 'not_run_needs_approval', 'unavailable_here', 'failed')
OK_PROGRAMS = frozenset({'ffmpeg', 'ffprobe'})
DEFAULT_TIMEOUT = {'quick': 20.0, 'full': 60.0}
WORKERS = 4
SAMPLE_FRAMES = 180
SAMPLE_SECONDS = 6.0


def _platform():
    return f'{sys.platform} py{sys.version_info.major}.{sys.version_info.minor}'


def _rerun(*parts):
    return ' '.join(['python -X utf8 "' + (ROOT / 'rose.py').as_posix() + '"', *parts])


def _approval(hint, rerun, would_write):
    return {'ok': False, 'outcome': 'approval_required', 'error': None, 'allowed': None,
            'hint': hint, 'would_write': list(would_write), 'rerun_with': rerun, 'next': [rerun]}


# --------------------------------------------------------------------------- classification

def _classify(op_id, entry):
    """-> (kind, status, reason). kind 'static' carries its final status; 'run' and 'gate' are executed."""
    needs = entry.get('needs') or {}
    required = [p['name'] for p in entry.get('params', []) if p.get('required')]
    if needs.get('pc_only'):
        return 'static', 'unavailable_here', 'pc_only: needs the owner PC private memory'
    external = sorted(set(needs.get('programs') or []) - OK_PROGRAMS)
    if needs.get('network') or external:
        why = ['network'] if needs.get('network') else []
        return 'static', 'unavailable_here', 'not executed here: ' + ', '.join(why + external)
    if entry.get('effect') == 'write':
        if required:
            return 'static', 'needs_input', 'needs input first: ' + ', '.join(required)
        return 'gate', None, None
    if entry.get('runs_with_defaults') and entry.get('example'):
        return 'run', None, None
    return 'static', 'needs_input', ('needs input: ' + ', '.join(required)) if required else 'no runnable example'


# --------------------------------------------------------------------------- child process

def _listing(folder):
    rows = []
    for path in sorted(Path(folder).rglob('*')):
        rel = path.relative_to(folder).as_posix()
        rows.append(f"{rel}|{path.stat().st_size if path.is_file() else '/'}")
    return hashlib.sha256('\n'.join(rows).encode('utf-8')).hexdigest()


def _child(op_id, work, dbdir, timeout):
    db = dbdir / 'selfcheck.sqlite3'
    cmd = [sys.executable, '-X', 'utf8', '-B', str(RUNNER), '--db', str(db), 'run', op_id]
    env = dict(os.environ)
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    env['RED_ROSE_DB'] = str(db)
    t0 = time.monotonic()
    try:
        done = subprocess.run(cmd, cwd=str(work), env=env, capture_output=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired:
        return {'code': None, 'doc': None, 'error': f'timeout after {timeout:g}s',
                'seconds': round(time.monotonic() - t0, 2)}
    except OSError as exc:
        return {'code': None, 'doc': None, 'error': f'cannot start: {type(exc).__name__}',
                'seconds': round(time.monotonic() - t0, 2)}
    doc = None
    for line in reversed(done.stdout.decode('utf-8', 'replace').splitlines()):
        line = line.strip()
        if line.startswith('{'):
            try:
                doc = json.loads(line)
                break
            except ValueError:
                continue
    error = None
    if doc is None:
        tail = done.stderr.decode('utf-8', 'replace').strip().splitlines()[-1:] or ['no output']
        error = 'no JSON output: ' + tail[0][:200]
    return {'code': done.returncode, 'doc': doc, 'error': error, 'seconds': round(time.monotonic() - t0, 2)}


def _row(status, seconds, outcome=None, error=None):
    return {'status': status, 'seconds': seconds, 'outcome': outcome, 'error': error}


def _run_job(job):
    op, kind, work, dbdir, timeout, base = (job[k] for k in ('op', 'kind', 'work', 'dbdir', 'timeout', 'base'))
    try:
        before = _listing(work)
        ch = _child(op, work, dbdir, timeout)
        after = _listing(work)
        doc = ch['doc'] or {}
        outcome = doc.get('outcome')
        error = doc.get('error') or ch['error']
        if ch['error'] is None and error is None and ch['code'] not in (0, 3, 4, 5):
            error = f"exit code {ch['code']}"
        if error:
            error = str(error).replace(str(base), '<tmp>')[:300]
        seconds = ch['seconds']
        if after != before:
            return _row('failed', seconds, outcome, 'changed its folder without approval' if kind == 'gate'
                        else 'read op changed its folder')
        if kind == 'gate':
            if outcome == 'approval_required' and ch['code'] == rio.EXIT_APPROVAL:
                return _row('not_run_needs_approval', seconds, outcome)
            if outcome == 'ok':
                return _row('failed', seconds, outcome, 'write op returned ok without --approve-write')
            return _row('failed', seconds, outcome, error or 'write op did not answer approval_required')
        if ch['error'] is not None:
            return _row('failed', seconds, outcome, error)
        if outcome == 'ok' and ch['code'] == rio.EXIT_OK:
            return _row('verified', seconds, outcome)
        if outcome == 'example_only':
            return _row('runs_with_defaults', seconds, outcome)
        if outcome == 'approval_required':
            return _row('not_run_needs_approval', seconds, outcome)
        if outcome == 'unavailable_here':
            return _row('unavailable_here', seconds, outcome, error)
        return _row('failed', seconds, outcome, error or f'outcome {outcome!r}')
    except Exception as exc:  # never let one op stop the whole run
        return _row('failed', 0.0, None, f'{type(exc).__name__}: {exc}'[:300])


# --------------------------------------------------------------------------- public: run

def run(adapter=None, quick=False, timeout=None):
    """Execute the runnable examples (read ops) and gate-check the write ops. Returns a report dict.

    adapter: an adapter id to restrict to (None = all). quick: one executed op per adapter and kind;
    static statuses are still reported for every op. timeout: seconds per op.
    """
    catalog = importlib.import_module('rose_catalog')
    entries = catalog.load()['entries']
    if adapter is not None and not any(e.get('adapter') == adapter for e in entries.values()):
        raise ValueError(f'unknown adapter: {adapter}')
    limit = float(timeout) if timeout else DEFAULT_TIMEOUT['quick' if quick else 'full']
    selected = sorted(op for op, e in entries.items() if adapter is None or e.get('adapter') == adapter)
    ops, plan, seen, skipped_quick = {}, [], set(), 0
    for op in selected:
        kind, status, reason = _classify(op, entries[op])
        if kind == 'static':
            ops[op] = _row(status, 0.0, None, reason)
            continue
        key = (entries[op].get('adapter'), kind)
        if quick and key in seen:
            skipped_quick += 1
            continue
        seen.add(key)
        plan.append((op, kind))

    t0 = time.monotonic()
    base = Path(tempfile.mkdtemp(prefix='rose-selfcheck-'))
    try:
        jobs = []
        for index, (op, kind) in enumerate(plan):
            work = base / 'work' / f'{index:04d}'
            dbdir = base / 'db' / f'{index:04d}'
            work.mkdir(parents=True)
            dbdir.mkdir(parents=True)
            jobs.append({'op': op, 'kind': kind, 'work': work, 'dbdir': dbdir, 'timeout': limit, 'base': base})
        with cf.ThreadPoolExecutor(max_workers=WORKERS) as pool:
            for job, row in zip(jobs, pool.map(_run_job, jobs)):
                ops[job['op']] = row
    finally:
        shutil.rmtree(base, ignore_errors=True)

    totals = {key: 0 for key in TOTAL_KEYS}
    for row in ops.values():
        totals[row['status']] = totals.get(row['status'], 0) + 1
    failed = sorted(op for op, row in ops.items() if row['status'] == 'failed')
    return {'ok': not failed, 'outcome': 'ok' if not failed else 'error', 'adapter': adapter,
            'quick': bool(quick), 'timeout_s': limit, 'platform': _platform(),
            'checked': len(selected), 'executed': len(plan), 'skipped_quick': skipped_quick,
            'totals': totals, 'failed': failed, 'ops': dict(sorted(ops.items())),
            'seconds': round(time.monotonic() - t0, 2)}


# --------------------------------------------------------------------------- public: status file

def _read_ops(path):
    try:
        doc = json.loads(Path(path).read_text(encoding='utf-8'))
        ops = doc.get('ops') if isinstance(doc, dict) else None
        return dict(ops) if isinstance(ops, dict) else {}
    except (OSError, ValueError):
        return {}


def save_status(result, approve_write=False, path=None):
    """Write references/VERIFIED_STATUS.json from a run() report. Refuses without approve_write (writes nothing)."""
    target = Path(path) if path is not None else Path(rose_env.VERIFIED_JSON)
    if not approve_write:
        return _approval('selfcheck --save-status changes references/VERIFIED_STATUS.json; nothing was written',
                         _rerun('selfcheck', '--save-status', '--approve-write'), [str(target)])
    full = result.get('adapter') is None and not result.get('quick')
    merged = {} if full else _read_ops(target)
    for op, row in result['ops'].items():
        if row['status'] in SAVED_STATUSES:
            merged[op] = {'status': row['status'], 'outcome': row['outcome'], 'error': row['error']}
        else:
            merged.pop(op, None)
    counts = {}
    for row in merged.values():
        counts[row['status']] = counts.get(row['status'], 0) + 1
    doc = {'schema': STATUS_SCHEMA, 'platform': result['platform'], 'counts': dict(sorted(counts.items())),
           'ops': dict(sorted(merged.items()))}
    rio.write_json(str(target), doc, overwrite=True)
    return {'ok': True, 'outcome': 'ok', 'written': str(target), 'counts': doc['counts']}


# --------------------------------------------------------------------------- sample-media

def sample_media(out_dir, approve_write=False):
    """Create the synthetic fixtures in out_dir (only with approve_write). Verifies the clip with FFprobe."""
    target = Path(out_dir).expanduser()
    if not approve_write:
        return _approval('sample-media writes synthetic input files into the folder given by --out; nothing was written',
                         _rerun('sample-media', '--out', '<folder>', '--approve-write'), [str(target)])
    try:
        made = rose_fixtures.make(target)
    except (FileExistsError, ValueError) as exc:
        return {'ok': False, 'outcome': 'error', 'error': str(exc),
                'hint': 'choose an empty folder for --out', 'next': []}
    verify = None
    clip = made.get('SAMPLE_VIDEO')
    if clip:
        try:
            verify_media = importlib.import_module('verify_media')
            v = verify_media.verify_video(clip, expected_fps=30, width=540, height=960,
                                          expected_frames=SAMPLE_FRAMES, expected_audio=True)
            seconds = float(v.get('duration') or 0.0)
            verify = {'passed': bool(v.get('passed')) and abs(seconds - SAMPLE_SECONDS) < 0.1,
                      'frames': v.get('frames'), 'duration': round(seconds, 3), 'fps': v.get('fps'),
                      'codec': v.get('codec')}
        except Exception as exc:
            verify = {'passed': False, 'error': f'{type(exc).__name__}: {exc}'[:300]}
    if made['errors']:
        outcome, code = 'error', rio.EXIT_ERROR
    elif made['skipped']:
        outcome, code = 'unavailable_here', rio.EXIT_UNAVAILABLE
    elif verify is not None and not verify.get('passed'):
        outcome, code = 'error', rio.EXIT_ERROR
    else:
        outcome, code = 'ok', rio.EXIT_OK
    files = {k: v for k, v in made.items() if k not in ('out_dir', 'skipped', 'errors') and v}
    return {'ok': outcome == 'ok', 'outcome': outcome, 'code': code, 'out_dir': made['out_dir'],
            'files': files, 'skipped': made['skipped'], 'errors': made['errors'], 'verify': verify,
            'note': 'synthetic fixtures for tests and demos, not owner data'}


# --------------------------------------------------------------------------- CLI

def _text_totals(result):
    t = result['totals']
    return ' | '.join(f'{k} {t.get(k, 0)}' for k in TOTAL_KEYS)


def _h_selfcheck(args):
    if args.save_status and not args.approve_write:
        rio.emit(_approval('selfcheck --save-status changes references/VERIFIED_STATUS.json; nothing was run or written',
                           _rerun('selfcheck', '--save-status', '--approve-write'),
                           [str(rose_env.VERIFIED_JSON)]))
        return rio.EXIT_APPROVAL
    try:
        result = run(adapter=args.adapter, quick=args.quick, timeout=args.timeout)
    except ValueError as exc:
        return rio.fail(str(exc), hint='python -X utf8 rose.py ops lists the adapters')
    if args.save_status:
        result['saved'] = save_status(result, approve_write=True)
    if args.json:
        rio.emit(result)
    else:
        lines = [f"selfcheck {rose_env.SKILL_VERSION} | {'quick' if result['quick'] else 'full'} | "
                 f"adapter {result['adapter'] or 'all'} | checked {result['checked']} | executed {result['executed']} | "
                 f"{result['seconds']} s",
                 _text_totals(result),
                 'failed: ' + (', '.join(result['failed']) if result['failed'] else 'none')]
        if args.save_status:
            lines.append('saved: ' + result['saved']['written'])
        sys.stdout.buffer.write(('\n'.join(lines) + '\n').encode('utf-8'))
        sys.stdout.flush()
    return rio.EXIT_OK if result['ok'] else rio.EXIT_ERROR


def _h_sample_media(args):
    doc = sample_media(args.out, approve_write=args.approve_write)
    rio.emit(doc)
    return int(doc.get('code', rio.EXIT_APPROVAL if doc.get('outcome') == 'approval_required' else rio.EXIT_ERROR))


def register(subparsers):
    """Adds selfcheck and sample-media (see references/INTERFACE.md)."""
    p = subparsers.add_parser('selfcheck', help='run the runnable catalogue examples in a temp folder (--save-status --approve-write records them)')
    p.add_argument('--quick', action='store_true', help='one executed op per adapter and kind')
    p.add_argument('--adapter', default=None, metavar='ID', help='only this adapter (rose.py ops lists them)')
    p.add_argument('--timeout', type=float, default=None, help='seconds per op (default 20 quick, 60 full)')
    p.add_argument('--save-status', action='store_true', help='write references/VERIFIED_STATUS.json (needs --approve-write)')
    p.add_argument('--approve-write', action='store_true')
    p.add_argument('--json', action='store_true', help='one JSON document instead of text')
    rio.json_usage_errors(p)
    p.set_defaults(ext_func=_h_selfcheck)

    p = subparsers.add_parser('sample-media', help='write synthetic test inputs (clip, PNG, WAV, Arabic words, CSV pair) into --out')
    p.add_argument('--out', required=True, metavar='DIR', help='an empty folder (created when missing)')
    p.add_argument('--approve-write', action='store_true')
    rio.json_usage_errors(p)
    p.set_defaults(ext_func=_h_sample_media)
