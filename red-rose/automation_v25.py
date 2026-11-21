"""Red Rose V25: bounded local automation helpers (commands, queues, pools, QA, receipts).

Standard library plus the project's own verify_media. Every op works only
inside a caller-supplied, already existing ``work_dir``. Ops whose EFFECTS
entry is 'write' refuse to touch the disk unless ``approve_write=True``.

Process rules enforced here:
- no shell: commands are lists ``[executable, *args]``; ``shell`` requests,
  whole command strings and standalone shell operators are refused;
- executables come from a fixed allow-list: this Python (``sys.executable``,
  alias 'python'), ``ffmpeg`` and ``ffprobe`` (resolved on PATH);
- every child has a timeout; on timeout it is killed;
- no network modules, no exec/eval, no printing.

Each op returns {'op', 'result', 'assumptions', 'limits'} like physics_v20.
"""
from __future__ import annotations

import concurrent.futures
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

from verify_media import verify_video

MAX_PARAMS = 24
MAX_ARGS = 64
MAX_ARG_CHARS = 8_000
MAX_TIMEOUT = 600.0
MAX_TASKS = 200
MAX_WORKERS = 8
MAX_CAPTURE = 8_000
MAX_LOG_LINES = 10_000
MAX_JSON_BYTES = 5_000_000

TOPICS = {
    '21.01': 'run_command',
    '21.02': 'task_queue',
    '21.03': 'bounded_pool',
    '21.05': 'timeout_cancel',
    '21.06': 'perf_log',
    '21.07': 'smart_retry',
    '21.08': 'render_qa',
    '21.09': 'release_gate',
    '21.10': 'execution_receipt',
}

TOPIC_NAMES_AR = {
    '21.01': 'تشغيل مهمة عبر أمر صريح',
    '21.02': 'جدولة خطوات طويلة',
    '21.03': 'تشغيل متوازي مضبوط',
    '21.05': 'إيقاف مهمة معلقة',
    '21.06': 'متابعة حالة الأداء',
    '21.07': 'إعادة المحاولة بذكاء',
    '21.08': 'أتمتة فحص جودة الرندر',
    '21.09': 'التحقق قبل نشر إصدار',
    '21.10': 'حفظ إيصالات التنفيذ',
}

EFFECTS = {
    'run_command': 'write',
    'task_queue': 'write',
    'bounded_pool': 'write',
    'timeout_cancel': 'write',
    'perf_log': 'write',
    'smart_retry': 'read',
    'render_qa': 'read',
    'release_gate': 'read',
    'execution_receipt': 'write',
}

ALLOWED_EXECUTABLES = ('python', 'ffmpeg', 'ffprobe')
SHELL_OPERATORS = {'&&', '||', '|', ';', '&', '>', '>>', '<', '<<', '2>', '2>&1', '1>', '|&'}
SHELL_NAMES = {'cmd', 'cmd.exe', 'sh', 'bash', 'zsh', 'powershell', 'powershell.exe',
               'pwsh', 'pwsh.exe', 'wsl', 'wsl.exe', 'bash.exe', 'sh.exe'}

# --------------------------------------------------------------------------- validation


def _no_extra(extra):
    if extra:
        if 'shell' in extra:
            raise ValueError('shell execution is refused; pass an allow-listed executable and an argument list')
        raise ValueError('unknown parameter(s): ' + ', '.join(sorted(map(str, extra))))


def _num(value, low, high, name):
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value) or not low <= value <= high):
        raise ValueError(f'{name} must be a finite number in [{low}, {high}]')
    return float(value)


def _int(value, low, high, name):
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise ValueError(f'{name} must be an integer from {low} to {high}')
    return value


def _bool(value, name):
    if not isinstance(value, bool):
        raise ValueError(f'{name} must be true or false')
    return value


def _text(value, name, max_len=200, allow_empty=False):
    if not isinstance(value, str) or (not value.strip() and not allow_empty) \
            or len(value) > max_len or '\x00' in value:
        raise ValueError(f'{name} must be a non-empty string of at most {max_len} characters')
    return value


def _choice(value, options, name):
    if not isinstance(value, str) or value not in options:
        raise ValueError(f'{name} must be one of {sorted(options)}')
    return value


def _pack(op, result, assumptions, limits):
    return {'op': op, 'result': result, 'assumptions': list(assumptions),
            'limits': list(limits)}


def _approve(approve_write, op):
    if approve_write is not True:
        raise ValueError(f'{op} writes inside work_dir and requires approve_write=True')


def _work_dir(work_dir):
    if work_dir is None:
        raise ValueError('work_dir is required (an existing folder)')
    if not isinstance(work_dir, (str, os.PathLike)) or '\x00' in os.fspath(work_dir):
        raise ValueError('work_dir must be a local folder path')
    p = Path(work_dir).expanduser()
    if not p.is_dir():
        raise ValueError('work_dir must be an existing folder')
    return p.resolve()


def _inside(wd, rel, name, *, must_exist=False):
    """Resolve rel (relative or absolute) and require it to stay inside wd."""
    if not isinstance(rel, (str, os.PathLike)) or not os.fspath(rel) or '\x00' in os.fspath(rel):
        raise ValueError(f'{name} must be a path inside work_dir')
    p = Path(rel)
    p = (p if p.is_absolute() else wd / p).resolve()
    if p == wd or not p.is_relative_to(wd):
        raise ValueError(f'{name} must point inside work_dir')
    if must_exist and not p.is_file():
        raise ValueError(f'{name} does not exist as a file in work_dir')
    return p


def _rel(wd, p):
    return p.relative_to(wd).as_posix()


def _resolve_exe(executable):
    if not isinstance(executable, str) or not executable.strip():
        raise ValueError('executable must be one of ' + ', '.join(ALLOWED_EXECUTABLES))
    if any(ch.isspace() for ch in executable.strip()) or executable.strip() != executable:
        raise ValueError('a whole command string is refused; pass executable and args separately (no shell)')
    if Path(executable).name.lower() in SHELL_NAMES:
        raise ValueError(f'shell interpreter {executable!r} is not allowed')
    if executable == 'python' or os.path.normcase(executable) == os.path.normcase(sys.executable):
        return 'python', sys.executable
    if executable in ('ffmpeg', 'ffprobe'):
        found = shutil.which(executable)
        if not found:
            raise RuntimeError(f'{executable} is not installed on PATH')
        return executable, found
    raise ValueError(f'executable {executable!r} is not allow-listed; allowed: {", ".join(ALLOWED_EXECUTABLES)}')


def _args(args, name='args'):
    if isinstance(args, str):
        raise ValueError(f'{name} must be a list of strings, not a command string (no shell)')
    if not isinstance(args, (list, tuple)) or len(args) > MAX_ARGS:
        raise ValueError(f'{name} must be a list of at most {MAX_ARGS} strings')
    out = []
    for i, a in enumerate(args):
        if not isinstance(a, str) or len(a) > MAX_ARG_CHARS or '\x00' in a:
            raise ValueError(f'{name}[{i}] must be a string of at most {MAX_ARG_CHARS} characters')
        if a.strip() in SHELL_OPERATORS or '$(' in a or '`' in a:
            raise ValueError(f'{name}[{i}] looks like a shell operator/substitution; no shell is used, refused')
        out.append(a)
    return out


def _env():
    env = dict(os.environ)
    env['PYTHONIOENCODING'] = 'utf-8'
    env['PYTHONUTF8'] = '1'
    return env


def _clip(data):
    if data is None:
        return ''
    text = data.decode('utf-8', 'replace') if isinstance(data, bytes) else str(data)
    return text if len(text) <= MAX_CAPTURE else text[:MAX_CAPTURE] + '…[truncated]'


def _exec(wd, exe_path, argv, timeout):
    """Run [exe_path, *argv] in wd without a shell; never raises on exit/timeout."""
    t0 = time.time()
    m0 = time.monotonic()
    try:
        done = subprocess.run([exe_path, *argv], capture_output=True, timeout=timeout,
                              cwd=str(wd), env=_env(), stdin=subprocess.DEVNULL)
        code, out, err, timed_out = done.returncode, done.stdout, done.stderr, False
    except subprocess.TimeoutExpired as exc:
        code, out, err, timed_out = None, exc.stdout, exc.stderr, True
    return {'exit_code': code, 'timed_out': timed_out, 'started_at': round(t0, 3),
            'ended_at': round(time.time(), 3), 'duration_s': round(time.monotonic() - m0, 4),
            'stdout': _clip(out), 'stderr': _clip(err)}


def _sha256(p):
    h = hashlib.sha256()
    with p.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def _write_json_atomic(path, data):
    tmp = path.with_name(f'.{path.name}.{uuid.uuid4().hex[:8]}.tmp')
    try:
        with tmp.open('x', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=1, allow_nan=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()


def _read_json(path, name):
    if not path.is_file():
        raise FileNotFoundError(name)
    if path.stat().st_size > MAX_JSON_BYTES:
        raise ValueError(f'{name} is larger than {MAX_JSON_BYTES} bytes')
    with path.open('r', encoding='utf-8-sig') as f:
        return json.load(f)


def _unlink_retry(p, tries=20):
    for _ in range(tries):
        try:
            p.unlink(missing_ok=True)
            return True
        except PermissionError:
            time.sleep(0.1)
    return not p.exists()


# --------------------------------------------------------------------------- 21.01 run_command

def run_command(*, work_dir=None, executable=None, args=None, timeout=30.0,
                approve_write=False, **extra):
    """Run one allow-listed executable with a list of args inside work_dir (no shell)."""
    _no_extra(extra)
    if executable is None:
        raise ValueError('executable is required (python, ffmpeg or ffprobe)')
    name, exe_path = _resolve_exe(executable)
    argv = _args([] if args is None else args)
    timeout = _num(timeout, 0.1, MAX_TIMEOUT, 'timeout')
    wd = _work_dir(work_dir)
    _approve(approve_write, 'run_command')
    res = _exec(wd, exe_path, argv, timeout)
    res.update({'executable': name, 'args': argv, 'cwd': str(wd),
                'status': 'timeout' if res['timed_out'] else ('ok' if res['exit_code'] == 0 else 'failed')})
    return _pack('run_command', res,
                 ['the child runs with cwd=work_dir but the OS does not sandbox it: an allowed '
                  'interpreter (python) can still read/write anywhere the user can',
                  'arguments are passed as a list without a shell, so shell syntax is never interpreted',
                  'environment is inherited, with PYTHONUTF8/PYTHONIOENCODING forced to UTF-8'],
                 [f'allow-list: {", ".join(ALLOWED_EXECUTABLES)}', f'<= {MAX_ARGS} args, each <= {MAX_ARG_CHARS} chars',
                  f'timeout <= {MAX_TIMEOUT} s; the direct child is killed on timeout (grandchildren may survive)',
                  f'stdout/stderr truncated to {MAX_CAPTURE} characters',
                  'standalone shell operators and $( ) / backticks in args are refused'])


# --------------------------------------------------------------------------- 21.02 task_queue

QUEUE_STATES = ('pending', 'running', 'done', 'failed', 'interrupted')


def _queue_path(wd, queue_name):
    queue_name = _text(queue_name, 'queue_name', 60)
    if not re.fullmatch(r'[A-Za-z0-9_\-]+', queue_name):
        raise ValueError('queue_name may contain only letters, digits, _ and -')
    return wd / f'{queue_name}.queue.json'


def _norm_task(t, seq):
    if not isinstance(t, dict):
        raise ValueError('each task must be a dict')
    allowed = {'id', 'priority', 'resources', 'executable', 'args', 'timeout', 'idempotent'}
    bad = set(t) - allowed
    if bad:
        raise ValueError('unknown task field(s): ' + ', '.join(sorted(map(str, bad))))
    tid = _text(t.get('id'), 'task id', 80)
    name, _ = _resolve_exe(t.get('executable'))
    return {'id': tid, 'seq': seq, 'priority': _int(t.get('priority', 0), -1000, 1000, 'priority'),
            'resources': sorted({_text(r, 'resource tag', 40) for r in (t.get('resources') or [])}),
            'executable': name, 'args': _args(t.get('args') or []),
            'timeout': _num(t.get('timeout', 60.0), 0.1, MAX_TIMEOUT, 'task timeout'),
            'idempotent': _bool(t.get('idempotent', False), 'idempotent'),
            'state': 'pending', 'attempts': 0, 'exit_code': None,
            'started_at': None, 'ended_at': None}


def task_queue(*, work_dir=None, action=None, tasks=None, queue_name='main',
               max_run=None, available_resources=None, ids=None, approve_write=False, **extra):
    """Persistent JSON queue: enqueue | run | status | requeue.

    'run' executes pending tasks by priority (high first, then FIFO). Each task
    is marked 'running' on disk before it starts and 'done'/'failed' after, so a
    restart never re-runs a completed task. A task found 'running' at restart
    was interrupted: idempotent tasks go back to pending, others become
    'interrupted' and need an explicit 'requeue'. max_run simulates a stop
    after N tasks.
    """
    _no_extra(extra)
    if action is None:
        raise ValueError('action is required: enqueue, run, status or requeue')
    action = _choice(action, {'enqueue', 'run', 'status', 'requeue'}, 'action')
    wd = _work_dir(work_dir)
    qpath = _queue_path(wd, queue_name)
    if action != 'status':
        _approve(approve_write, 'task_queue')
    state = _read_json(qpath, 'queue') if qpath.exists() else {'schema': 'red-rose.task_queue.v1', 'tasks': []}
    if not isinstance(state, dict) or not isinstance(state.get('tasks'), list):
        raise ValueError('queue file is malformed')
    qtasks = state['tasks']
    recovered = []
    ran = []

    if action == 'enqueue':
        if not isinstance(tasks, list) or not tasks:
            raise ValueError('tasks must be a non-empty list')
        if len(qtasks) + len(tasks) > MAX_TASKS:
            raise ValueError(f'queue may hold at most {MAX_TASKS} tasks')
        existing = {t['id'] for t in qtasks}
        seq = max((t['seq'] for t in qtasks), default=-1) + 1
        new = []
        for i, t in enumerate(tasks):
            nt = _norm_task(t, seq + i)
            if nt['id'] in existing:
                raise ValueError(f'duplicate task id {nt["id"]!r}')
            existing.add(nt['id'])
            new.append(nt)
        qtasks.extend(new)
        _write_json_atomic(qpath, state)
    elif action == 'requeue':
        if not isinstance(ids, list) or not ids:
            raise ValueError('ids must be a non-empty list of task ids to requeue')
        want = {_text(i, 'id', 80) for i in ids}
        for t in qtasks:
            if t['id'] in want:
                if t['state'] not in ('interrupted', 'failed'):
                    raise ValueError(f'task {t["id"]!r} is {t["state"]}; only interrupted/failed can be requeued')
                t['state'] = 'pending'
                want.discard(t['id'])
        if want:
            raise ValueError('unknown task id(s): ' + ', '.join(sorted(want)))
        _write_json_atomic(qpath, state)
    elif action == 'run':
        limit = MAX_TASKS if max_run is None else _int(max_run, 0, MAX_TASKS, 'max_run')
        res_ok = None if available_resources is None else \
            {_text(r, 'resource tag', 40) for r in available_resources}
        for t in qtasks:  # recovery of a crash mid-task
            if t['state'] == 'running':
                t['state'] = 'pending' if t['idempotent'] else 'interrupted'
                recovered.append({'id': t['id'], 'now': t['state']})
        if recovered:
            _write_json_atomic(qpath, state)
        order = sorted((t for t in qtasks if t['state'] == 'pending'),
                       key=lambda t: (-t['priority'], t['seq']))
        for t in order:
            if len(ran) >= limit:
                break
            if res_ok is not None and not set(t['resources']) <= res_ok:
                continue
            _, exe_path = _resolve_exe(t['executable'])
            t['state'] = 'running'
            t['attempts'] += 1
            t['started_at'] = round(time.time(), 3)
            _write_json_atomic(qpath, state)
            r = _exec(wd, exe_path, t['args'], t['timeout'])
            t['exit_code'] = r['exit_code']
            t['ended_at'] = r['ended_at']
            t['state'] = 'done' if r['exit_code'] == 0 else 'failed'
            _write_json_atomic(qpath, state)
            ran.append({'id': t['id'], 'state': t['state'], 'exit_code': r['exit_code'],
                        'timed_out': r['timed_out'], 'duration_s': r['duration_s']})
    counts = {s: sum(1 for t in qtasks if t['state'] == s) for s in QUEUE_STATES}
    result = {'action': action, 'queue_file': _rel(wd, qpath), 'counts': counts,
              'ran': ran, 'recovered': recovered,
              'tasks': [{'id': t['id'], 'priority': t['priority'], 'resources': t['resources'],
                         'state': t['state'], 'attempts': t['attempts']} for t in qtasks],
              'complete': counts['pending'] == 0 and counts['running'] == 0 and counts['interrupted'] == 0}
    return _pack('task_queue', result,
                 ['state is written atomically (temp file + os.replace) before and after every task',
                  'a crash between task exit and the "done" write leaves the task "running"; on restart '
                  'only tasks declared idempotent are re-run, others become "interrupted" for a human decision',
                  'single writer: no inter-process lock, so two runners on one queue file are not supported',
                  'priority: higher number first, ties in enqueue order; resource tags only filter which tasks may run'],
                 [f'<= {MAX_TASKS} tasks per queue', 'tasks run sequentially, one at a time',
                  'executables limited to the allow-list; per-task timeout <= 600 s'])


# --------------------------------------------------------------------------- 21.03 bounded_pool

_PATH_LOCKS = {}
_PATH_LOCKS_GUARD = threading.Lock()


def _path_lock(path):
    key = os.path.normcase(str(path))
    with _PATH_LOCKS_GUARD:
        lock = _PATH_LOCKS.get(key)
        if lock is None:
            lock = _PATH_LOCKS[key] = threading.Lock()
        return lock


def bounded_pool(*, work_dir=None, tasks=None, max_workers=2, approve_write=False, **extra):
    """Run command tasks on a bounded ThreadPoolExecutor with a per-output-path lock.

    task: {'id', 'executable', 'args', 'output'?, 'timeout'?}; the literal
    token '{output}' inside args is replaced by the absolute output path.
    Tasks naming the same output path never run at the same time.
    """
    _no_extra(extra)
    if not isinstance(tasks, list) or not tasks:
        raise ValueError('tasks must be a non-empty list')
    if len(tasks) > MAX_TASKS:
        raise ValueError(f'at most {MAX_TASKS} tasks')
    max_workers = _int(max_workers, 1, MAX_WORKERS, 'max_workers')
    wd = _work_dir(work_dir)
    norm = []
    seen = set()
    for t in tasks:
        if not isinstance(t, dict) or set(t) - {'id', 'executable', 'args', 'output', 'timeout'}:
            raise ValueError('each task must be a dict with id, executable, args, output?, timeout?')
        tid = _text(t.get('id'), 'task id', 80)
        if tid in seen:
            raise ValueError(f'duplicate task id {tid!r}')
        seen.add(tid)
        name, exe_path = _resolve_exe(t.get('executable'))
        out = _inside(wd, t['output'], 'output') if t.get('output') is not None else None
        argv = _args(t.get('args') or [])
        if out is not None:
            argv = [a.replace('{output}', str(out)) for a in argv]
        norm.append({'id': tid, 'exe': exe_path, 'name': name, 'argv': argv, 'out': out,
                     'timeout': _num(t.get('timeout', 60.0), 0.1, MAX_TIMEOUT, 'task timeout')})
    _approve(approve_write, 'bounded_pool')
    counter = {'running': 0, 'max': 0}
    guard = threading.Lock()
    m0 = time.monotonic()

    def work(t):
        lock = _path_lock(t['out']) if t['out'] is not None else None
        if lock is not None:
            lock.acquire()
        try:
            with guard:
                counter['running'] += 1
                counter['max'] = max(counter['max'], counter['running'])
            start = time.monotonic() - m0
            try:
                r = _exec(wd, t['exe'], t['argv'], t['timeout'])
            finally:
                end = time.monotonic() - m0
                with guard:
                    counter['running'] -= 1
        finally:
            if lock is not None:
                lock.release()
        return {'id': t['id'], 'output': _rel(wd, t['out']) if t['out'] is not None else None,
                'exit_code': r['exit_code'], 'timed_out': r['timed_out'],
                'start_s': round(start, 4), 'end_s': round(end, 4),
                'stderr': r['stderr'][-500:]}

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
        results = list(pool.map(work, norm))
    overlaps = []
    for i, a in enumerate(results):
        for b in results[i + 1:]:
            if a['output'] and a['output'] == b['output'] and \
                    a['start_s'] < b['end_s'] and b['start_s'] < a['end_s']:
                overlaps.append([a['id'], b['id']])
    result = {'max_workers': max_workers, 'max_concurrent_observed': counter['max'],
              'tasks': results, 'same_path_overlaps': overlaps,
              'all_ok': all(r['exit_code'] == 0 for r in results),
              'wall_s': round(time.monotonic() - m0, 4)}
    return _pack('bounded_pool', result,
                 ['threads only launch child processes, so the GIL does not limit the children',
                  'the per-path lock map is process-local: it does not protect against other programs '
                  'or other Python processes writing the same file',
                  'a task waiting for a path lock holds a worker slot but is not counted as running'],
                 [f'max_workers 1..{MAX_WORKERS}', f'<= {MAX_TASKS} tasks', 'per-task timeout <= 600 s',
                  'stderr tail of 500 characters per task'])


# --------------------------------------------------------------------------- 21.05 timeout_cancel

def timeout_cancel(*, work_dir=None, executable=None, args=None, output=None, timeout=30.0,
                   overwrite=False, approve_write=False, **extra):
    """Run a command that writes '{output}', with a hard timeout and temp-then-rename.

    The child writes to a hidden partial file next to output. On success
    (exit 0 and partial exists) the partial is renamed onto output. On timeout
    the child is killed and the partial is deleted; on failure it is deleted too.
    """
    _no_extra(extra)
    if executable is None or output is None:
        raise ValueError('executable, args and output are required')
    name, exe_path = _resolve_exe(executable)
    argv = _args([] if args is None else args)
    if not any('{output}' in a for a in argv):
        raise ValueError("args must contain the token '{output}' where the child writes its result")
    timeout = _num(timeout, 0.1, MAX_TIMEOUT, 'timeout')
    overwrite = _bool(overwrite, 'overwrite')
    wd = _work_dir(work_dir)
    target = _inside(wd, output, 'output')
    if not target.parent.is_dir():
        raise ValueError('output folder must already exist inside work_dir')
    if target.exists() and not overwrite:
        raise ValueError('output already exists; pass overwrite=True to replace it')
    _approve(approve_write, 'timeout_cancel')
    partial = target.with_name(f'.{target.stem}.partial-{uuid.uuid4().hex[:8]}{target.suffix}')
    argv = [a.replace('{output}', str(partial)) for a in argv]
    t0 = time.monotonic()
    timed_out = False
    with subprocess.Popen([exe_path, *argv], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          stdin=subprocess.DEVNULL, cwd=str(wd), env=_env()) as proc:
        try:
            out, err = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            proc.kill()
            out, err = proc.communicate(timeout=30)
        code = proc.returncode
    duration = round(time.monotonic() - t0, 4)
    partial_existed = partial.exists()
    if timed_out or code != 0 or not partial_existed:
        removed = _unlink_retry(partial)
        status = 'timeout_killed' if timed_out else ('failed' if code != 0 else 'no_output')
        final = None
    else:
        os.replace(partial, target)
        removed = True
        status = 'ok'
        final = _rel(wd, target)
    result = {'status': status, 'executable': name, 'exit_code': None if timed_out else code,
              'timed_out': timed_out, 'duration_s': duration, 'output': final,
              'partial_existed': partial_existed, 'partial_removed': removed and not partial.exists(),
              'output_exists': target.exists(), 'rerunnable': True,
              'stderr': _clip(err)[-1000:], 'stdout': _clip(out)[-1000:]}
    return _pack('timeout_cancel', result,
                 ['the child must write only to the path substituted for {output}; files it writes '
                  'elsewhere are not cleaned up',
                  'kill() stops the direct child only; grandchildren it spawned may keep running',
                  'os.replace is atomic on the same volume, so output is either absent, old or complete'],
                 ['timeout <= 600 s', 'an existing output is replaced only with overwrite=True',
                  'stale partial files from a crash of this Python process itself are not swept'])


# --------------------------------------------------------------------------- 21.06 perf_log

def _probe_frames(path, timeout=120):
    exe = shutil.which('ffprobe')
    if not exe:
        raise RuntimeError('ffprobe is not installed on PATH')
    done = subprocess.run([exe, '-v', 'error', '-select_streams', 'v:0', '-count_frames',
                           '-show_entries', 'stream=nb_read_frames,nb_frames', '-of', 'json', str(path)],
                          capture_output=True, timeout=timeout)
    if done.returncode != 0:
        raise ValueError('ffprobe could not read output: ' + _clip(done.stderr)[-300:])
    streams = json.loads(done.stdout.decode('utf-8', 'replace')).get('streams') or []
    if not streams:
        raise ValueError('output has no video stream')
    s = streams[0]
    read = s.get('nb_read_frames')
    declared = s.get('nb_frames')
    return (int(read) if str(read).isdigit() else None,
            int(declared) if str(declared).isdigit() else None)


def perf_log(*, work_dir=None, action='record', log_name='perf_log.jsonl', stage=None,
             started_at=None, ended_at=None, result=None, frames_reported=None,
             output=None, approve_write=False, **extra):
    """Append a structured JSONL stage record (action='record') or summarise the log ('summary').

    When output and frames_reported are given, the output's frames are counted
    by an ffprobe full decode and any mismatch is flagged.
    """
    _no_extra(extra)
    action = _choice(action, {'record', 'summary'}, 'action')
    wd = _work_dir(work_dir)
    log_name = _text(log_name, 'log_name', 80)
    if not re.fullmatch(r'[A-Za-z0-9_\-.]+\.jsonl', log_name):
        raise ValueError('log_name must be a simple *.jsonl file name')
    log = wd / log_name
    if action == 'summary':
        if not log.is_file():
            raise ValueError('log does not exist yet')
        entries = []
        with log.open('r', encoding='utf-8') as f:
            for i, line in enumerate(f):
                if i >= MAX_LOG_LINES:
                    break
                if line.strip():
                    entries.append(json.loads(line))
        stages = {}
        for e in entries:
            s = stages.setdefault(e.get('stage', '?'), {'count': 0, 'total_s': 0.0, 'failed': 0})
            s['count'] += 1
            s['total_s'] = round(s['total_s'] + float(e.get('duration_s') or 0), 4)
            s['failed'] += 1 if e.get('result') != 'ok' else 0
        flagged = [e for e in entries if e.get('flags')]
        out = {'action': 'summary', 'log': log_name, 'entries': len(entries),
               'stages': stages, 'flagged': flagged[:100]}
    else:
        if stage is None or started_at is None or ended_at is None or result is None:
            raise ValueError('record needs stage, started_at, ended_at and result')
        stage = _text(stage, 'stage', 80)
        started_at = _num(started_at, 0, 1e11, 'started_at')
        ended_at = _num(ended_at, 0, 1e11, 'ended_at')
        if ended_at < started_at:
            raise ValueError('ended_at must not be before started_at')
        result = _choice(result, {'ok', 'failed', 'skipped', 'timeout'}, 'result')
        if frames_reported is not None:
            frames_reported = _int(frames_reported, 0, 10_000_000, 'frames_reported')
        out_path = _inside(wd, output, 'output', must_exist=True) if output is not None else None
        _approve(approve_write, 'perf_log')
        entry = {'stage': stage, 'started_at': started_at, 'ended_at': ended_at,
                 'duration_s': round(ended_at - started_at, 4), 'result': result,
                 'frames_reported': frames_reported, 'frames_measured': None,
                 'frames_declared': None, 'output': None, 'flags': [],
                 'logged_at': round(time.time(), 3)}
        if out_path is not None:
            entry['output'] = _rel(wd, out_path)
            measured, declared = _probe_frames(out_path)
            entry['frames_measured'] = measured
            entry['frames_declared'] = declared
            if measured is None:
                entry['flags'].append('frames_unmeasurable')
            elif frames_reported is not None and measured != frames_reported:
                entry['flags'].append('frame_mismatch')
            if measured is not None and declared is not None and measured != declared:
                entry['flags'].append('container_decode_mismatch')
        with log.open('a', encoding='utf-8') as f:
            f.write(json.dumps(entry, ensure_ascii=False, allow_nan=False) + '\n')
        out = {'action': 'record', 'log': log_name, 'entry': entry,
               'mismatch': 'frame_mismatch' in entry['flags'],
               'reconciled': out_path is not None and frames_reported is not None and not entry['flags']}
    return _pack('perf_log', out,
                 ['timestamps are caller-reported epoch seconds; only frame counts are measured',
                  'measured frames = ffprobe -count_frames (decodes the first video stream)',
                  'append-only JSONL; concurrent writers from several processes may interleave lines'],
                 [f'summary reads at most {MAX_LOG_LINES} lines', 'ffprobe timeout 120 s',
                  'output must already exist inside work_dir'])


# --------------------------------------------------------------------------- 21.07 smart_retry

TRANSIENT_EXCEPTIONS = {'TimeoutError', 'TimeoutExpired', 'ConnectionError', 'ConnectionResetError',
                        'ConnectionAbortedError', 'BrokenPipeError', 'InterruptedError',
                        'BlockingIOError'}
DEFAULT_TRANSIENT_CODES = [75, 111, 124]  # EX_TEMPFAIL, ECONNREFUSED-style, timeout(1)


def _classify(outcome, transient_codes):
    """outcome -> ('ok'|'transient'|'permanent', detail)."""
    if outcome.get('ok') is True:
        return 'ok', 'ok'
    if 'exit_code' in outcome:
        code = outcome['exit_code']
        if code == 0:
            return 'ok', 'exit 0'
        return ('transient' if code in transient_codes else 'permanent'), f'exit {code}'
    exc = outcome.get('exception')
    if isinstance(exc, str):
        return ('transient' if exc in TRANSIENT_EXCEPTIONS else 'permanent'), exc
    return 'permanent', 'unclassified outcome'


def smart_retry(*, operation=None, idempotent=None, idempotency_key=None, outcomes=None,
                call=None, max_retries=3, base_delay=0.5, max_delay=30.0,
                max_total_delay=120.0, transient_exit_codes=None, sleep=None, **extra):
    """Exponential-backoff retry limited to transient errors.

    Plan mode: `outcomes` is a list of observed attempt results
    ({'ok': True} | {'exit_code': n} | {'exception': 'TimeoutError'}); returns
    the decision for each. Execute mode: `call` is an in-process callable
    returning an exit code (int) or any value (= success) or raising.
    Non-idempotent operations without an idempotency_key are refused.
    """
    _no_extra(extra)
    if operation is None or idempotent is None:
        raise ValueError('operation (name) and idempotent (bool) are required')
    operation = _text(operation, 'operation', 120)
    idempotent = _bool(idempotent, 'idempotent')
    if idempotency_key is not None:
        idempotency_key = _text(idempotency_key, 'idempotency_key', 200)
    if (outcomes is None) == (call is None):
        raise ValueError('give exactly one of outcomes (plan) or call (execute)')
    if call is not None and not callable(call):
        raise ValueError('call must be callable')
    if sleep is not None and not callable(sleep):
        raise ValueError('sleep must be callable')
    max_retries = _int(max_retries, 0, 10, 'max_retries')
    base_delay = _num(base_delay, 0, 60, 'base_delay')
    max_delay = _num(max_delay, 0, 600, 'max_delay')
    max_total_delay = _num(max_total_delay, 0, 3600, 'max_total_delay')
    codes = DEFAULT_TRANSIENT_CODES if transient_exit_codes is None else transient_exit_codes
    if not isinstance(codes, list) or not all(type(c) is int for c in codes):
        raise ValueError('transient_exit_codes must be a list of integers')
    codes = set(codes)
    if outcomes is not None and (not isinstance(outcomes, list) or not outcomes
                                 or not all(isinstance(o, dict) for o in outcomes)
                                 or len(outcomes) > 50):
        raise ValueError('outcomes must be a non-empty list (<= 50) of dicts')
    assumptions = ['transient = timeouts/connection errors or an exit code in transient_exit_codes; '
                   'everything else is permanent and never retried',
                   'delay before retry n (0-based) = min(max_delay, base_delay * 2**n), no jitter',
                   'an idempotency key is recorded, not enforced: the callee must dedupe on it']
    limits = ['max_retries <= 10', 'total planned/slept delay <= max_total_delay',
              'callables run in-process in the calling thread']
    if not idempotent and idempotency_key is None:
        return _pack('smart_retry', {'status': 'refused', 'operation': operation, 'attempts': [],
                                     'reason': 'non-idempotent operation without idempotency_key: '
                                               'retrying could apply it twice'},
                     assumptions, limits)
    attempts = []
    waited = 0.0
    status = 'gave_up'
    value = None
    i = 0
    while True:
        if outcomes is not None:
            if i >= len(outcomes):
                status = 'no_more_outcomes'
                break
            kind, detail = _classify(outcomes[i], codes)
        else:
            try:
                got = call()
                if type(got) is int:
                    kind, detail = _classify({'exit_code': got}, codes)
                else:
                    kind, detail = 'ok', 'returned'
                    value = got
            except subprocess.TimeoutExpired:
                kind, detail = 'transient', 'TimeoutExpired'
            except Exception as exc:  # classified, never swallowed silently
                name = type(exc).__name__
                kind = 'transient' if name in TRANSIENT_EXCEPTIONS or isinstance(
                    exc, (TimeoutError, ConnectionError, InterruptedError)) else 'permanent'
                detail = f'{name}: {str(exc)[:200]}'
        rec = {'attempt': i + 1, 'classified': kind, 'detail': detail, 'delay_before_next_s': None}
        attempts.append(rec)
        if kind == 'ok':
            status = 'succeeded'
            break
        if kind == 'permanent':
            status = 'permanent_error_not_retried'
            break
        if i >= max_retries:
            status = 'gave_up_retries_exhausted'
            break
        delay = min(max_delay, base_delay * (2 ** i))
        if waited + delay > max_total_delay:
            status = 'gave_up_delay_budget'
            break
        rec['delay_before_next_s'] = delay
        waited += delay
        if call is not None and delay > 0:
            (sleep or time.sleep)(delay)
        i += 1
    try:
        json.dumps(value)
    except (TypeError, ValueError):
        value = repr(value)[:500]
    result = {'status': status, 'operation': operation, 'mode': 'plan' if outcomes is not None else 'execute',
              'idempotent': idempotent, 'idempotency_key': idempotency_key, 'attempts': attempts,
              'retries': len(attempts) - 1, 'total_delay_s': round(waited, 4), 'value': value}
    return _pack('smart_retry', result, assumptions, limits)


# --------------------------------------------------------------------------- 21.08 render_qa

def render_qa(*, work_dir=None, path=None, video_codec='h264', audio_codec='aac',
              require_audio=True, black_luma=24.0, **extra):
    """Accept/reject a rendered file: verify_video (ffprobe + full decode), codecs,
    even dimensions, container-vs-decoded frame count and a non-black first frame."""
    _no_extra(extra)
    if path is None:
        raise ValueError('path (rendered file inside work_dir) is required')
    video_codec = _text(video_codec, 'video_codec', 20)
    audio_codec = _text(audio_codec, 'audio_codec', 20)
    require_audio = _bool(require_audio, 'require_audio')
    black_luma = _num(black_luma, 0, 255, 'black_luma')
    wd = _work_dir(work_dir)
    p = _inside(wd, path, 'path', must_exist=True)
    checks = []

    def check(name, ok, detail):
        checks.append({'check': name, 'passed': bool(ok), 'detail': detail})

    qa = None
    try:
        qa = verify_video(p, expected_audio=True if require_audio else None)
        check('probe_and_full_decode', True, 'ffprobe + ffmpeg -xerror full decode succeeded')
    except Exception as exc:
        detail = f'{type(exc).__name__}: {str(exc)[:300]}'
        stderr = getattr(exc, 'stderr', None)
        if stderr:
            detail += ' | ' + _clip(stderr)[-300:]
        check('probe_and_full_decode', False, detail)
    if qa is not None:
        check('video_codec', qa['codec'] == video_codec, f'{qa["codec"]} (expected {video_codec})')
        if require_audio or qa['audio_codec'] is not None:
            check('audio_codec', qa['audio_codec'] == audio_codec,
                  f'{qa["audio_codec"]} (expected {audio_codec})')
        even = qa['width'] % 2 == 0 and qa['height'] % 2 == 0
        check('even_dimensions', even, f'{qa["width"]}x{qa["height"]}')
        try:
            measured, declared = _probe_frames(p)
            ok = measured is not None and measured > 0 and (declared is None or declared == measured)
            check('frame_count_consistent', ok, f'decoded {measured}, container declares {declared}')
        except Exception as exc:
            check('frame_count_consistent', False, f'{type(exc).__name__}: {str(exc)[:200]}')
        try:
            done = subprocess.run([shutil.which('ffmpeg') or 'ffmpeg', '-v', 'error', '-nostdin', '-i', str(p),
                                   '-frames:v', '1', '-vf', 'scale=16:16,format=gray',
                                   '-f', 'rawvideo', 'pipe:1'], capture_output=True, timeout=60)
            raw = done.stdout
            if done.returncode != 0 or len(raw) != 256:
                check('first_frame_not_black', False, 'could not decode first frame')
            else:
                mean = sum(raw) / len(raw)
                check('first_frame_not_black', mean > black_luma,
                      f'mean luma {mean:.1f} (black if <= {black_luma})')
        except subprocess.TimeoutExpired:
            check('first_frame_not_black', False, 'first-frame decode timed out')
    passed = bool(checks) and all(c['passed'] for c in checks)
    result = {'path': _rel(wd, p), 'decision': 'accepted' if passed else 'rejected', 'passed': passed,
              'failed_checks': [c['check'] for c in checks if not c['passed']], 'checks': checks,
              'media': qa}
    return _pack('render_qa', result,
                 ['decode success with -xerror is the corruption test; a stream that decodes cleanly '
                  'but has wrong content is not detected',
                  'truncation is caught by probe/decode failure or by container nb_frames != decoded frames',
                  'black = mean 8-bit luma of a 16x16 downscale of frame 1 <= black_luma (limited-range black is 16)'],
                 ['verify_video (imported) runs its ffprobe/ffmpeg without its own timeout; very large or '
                  'pathological files may take long', 'expects exactly one video stream',
                  'no perceptual/visual quality judgement'])


# --------------------------------------------------------------------------- 21.09 release_gate

def release_gate(*, work_dir=None, test_record='test_record.json', manifest='checksums.json',
                 approval='approval.json', **extra):
    """Decide ready/blocked from three records in work_dir. Never publishes anything.

    test_record: {'status': 'passed', 'passed': N>0, 'failed': 0, 'errors': 0, 'command': str}
    manifest:    {'version': str, 'files': {'rel/path': 'sha256hex', ...}}
    approval:    {'approved': true, 'approved_by': str, 'version': str, 'scope': [rel paths], 'action': str}
    """
    _no_extra(extra)
    if work_dir is None:
        raise ValueError('work_dir is required')
    wd = _work_dir(work_dir)
    reasons = []
    details = {}

    def load(rel, name):
        try:
            p = _inside(wd, rel, name)
            data = _read_json(p, name)
            if not isinstance(data, dict):
                raise ValueError('not a JSON object')
            return data
        except FileNotFoundError:
            reasons.append(f'{name} missing')
        except (ValueError, json.JSONDecodeError) as exc:
            reasons.append(f'{name} unreadable: {str(exc)[:120]}')
        return None

    tr = load(test_record, 'test_record')
    if tr is not None:
        ok = (tr.get('status') == 'passed' and type(tr.get('passed')) is int and tr['passed'] > 0
              and tr.get('failed') == 0 and tr.get('errors', 0) == 0
              and isinstance(tr.get('command'), str) and tr['command'].strip())
        details['tests'] = {k: tr.get(k) for k in ('status', 'passed', 'failed', 'errors', 'command')}
        if not ok:
            reasons.append('test record is not a clean pass (needs status passed, passed>0, failed=0, errors=0, command)')
    mf = load(manifest, 'manifest')
    files = {}
    if mf is not None:
        files = mf.get('files')
        if not isinstance(files, dict) or not files:
            reasons.append('manifest has no files')
            files = {}
        bad = []
        for rel, digest in list(files.items())[:MAX_TASKS * 5]:
            try:
                fp = _inside(wd, rel, 'manifest file', must_exist=True)
            except ValueError as exc:
                bad.append({'file': rel, 'problem': str(exc)})
                continue
            if not isinstance(digest, str) or not re.fullmatch(r'[0-9a-fA-F]{64}', digest):
                bad.append({'file': rel, 'problem': 'checksum is not a sha256 hex string'})
            elif _sha256(fp) != digest.lower():
                bad.append({'file': rel, 'problem': 'sha256 mismatch'})
        details['checksums'] = {'files': len(files), 'problems': bad}
        if bad:
            reasons.append(f'{len(bad)} manifest file(s) missing or not matching')
    ap = load(approval, 'approval')
    if ap is not None:
        scope = ap.get('scope')
        ok = (ap.get('approved') is True and isinstance(ap.get('approved_by'), str) and ap['approved_by'].strip()
              and isinstance(ap.get('action'), str) and ap['action'].strip()
              and isinstance(scope, list) and scope)
        if not ok:
            reasons.append('approval record incomplete (needs approved=true, approved_by, action, scope list)')
        else:
            if set(map(str, scope)) != set(files):
                reasons.append('approval scope does not equal the manifest file set')
            if mf is not None and ap.get('version') != mf.get('version'):
                reasons.append('approval version differs from manifest version')
        details['approval'] = {k: ap.get(k) for k in ('approved', 'approved_by', 'action', 'version')}
    decision = 'blocked' if reasons else 'ready'
    result = {'decision': decision, 'reasons': reasons, 'details': details,
              'published': False, 'note': 'gate only: nothing was uploaded, pushed or published'}
    return _pack('release_gate', result,
                 ['the records are trusted as written: the gate does not re-run the tests',
                  'checksums are re-computed from the files on disk now',
                  'approval is a record a human wrote; the gate cannot prove who wrote it'],
                 ['records must be JSON objects inside work_dir, each <= 5 MB',
                  'any missing or inconsistent record blocks', 'the op never publishes'])


# --------------------------------------------------------------------------- 21.10 execution_receipt

_SECRET_FLAG = re.compile(r'^-{1,2}[A-Za-z0-9_\-]*(token|secret|passw(or)?d|passwd|api[_\-]?key|apikey|'
                          r'auth|credential|private[_\-]?key|access[_\-]?key)[A-Za-z0-9_\-]*$', re.I)
_SECRET_VALUE = [
    re.compile(r'(?i)\b(bearer|basic)\s+[A-Za-z0-9._~+/=\-]{8,}'),
    re.compile(r'\b(sk|pk|rk)[-_][A-Za-z0-9_\-]{16,}'),
    re.compile(r'\b(ghp|gho|ghs|ghu|github_pat|glpat|xox[abprs]|hf)[_-][A-Za-z0-9_\-]{10,}'),
    re.compile(r'\bAKIA[0-9A-Z]{16}\b'),
    re.compile(r'\beyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+'),
    re.compile(r'(?i)\b([A-Z0-9_]*(token|secret|password|passwd|api_?key)[A-Z0-9_]*)=([^\s&]+)'),
    re.compile(r'(?<![A-Za-z0-9])(?=[A-Za-z0-9_\-]*[0-9])(?=[A-Za-z0-9_\-]*[A-Za-z])[A-Za-z0-9_\-]{32,}(?![A-Za-z0-9])'),
]
REDACTED = '***REDACTED***'


def _redact(args):
    out = []
    count = 0
    hide_next = False
    for a in args:
        if hide_next:
            out.append(REDACTED)
            count += 1
            hide_next = False
            continue
        if '=' in a and a.startswith('-') and _SECRET_FLAG.match(a.split('=', 1)[0]):
            out.append(a.split('=', 1)[0] + '=' + REDACTED)
            count += 1
            continue
        if _SECRET_FLAG.match(a):
            out.append(a)
            hide_next = True
            continue
        new = a
        for pat in _SECRET_VALUE:
            if pat.groups >= 3:
                new, n = pat.subn(lambda m: m.group(1) + '=' + REDACTED, new)
            else:
                new, n = pat.subn(REDACTED, new)
            count += n
        out.append(new)
    return out, count


def execution_receipt(*, work_dir=None, action='write', receipt='receipt.json', executable=None,
                      args=None, exit_code=None, started_at=None, ended_at=None, outputs=None,
                      execute=False, timeout=60.0, overwrite=False, approve_write=False, **extra):
    """Write a receipt JSON (action='write') or verify one against the files ('verify').

    write: either execute=True (the op runs [executable, *args] itself and records
    the measured exit code/timings) or caller-reported exit_code/started_at/ended_at.
    Args are stored with secrets redacted; outputs (paths in work_dir) get sha256s.
    """
    _no_extra(extra)
    action = _choice(action, {'write', 'verify'}, 'action')
    wd = _work_dir(work_dir)
    receipt = _text(receipt, 'receipt', 120)
    if not re.fullmatch(r'[A-Za-z0-9_\-.]+\.json', receipt):
        raise ValueError('receipt must be a simple *.json file name')
    rpath = wd / receipt
    common_a = ['secret detection is pattern-based (flag names like --token, known key prefixes, '
                'KEY=VALUE, long mixed alphanumerics); an unusual secret format can slip through',
                'sha256 proves the outputs are byte-identical to when the receipt was written, not that '
                'the command produced them']
    common_l = ['receipt and outputs must live inside work_dir', 'existing receipt replaced only with overwrite=True']
    if action == 'verify':
        data = _read_json(rpath, 'receipt') if rpath.is_file() else None
        if data is None:
            raise ValueError('receipt file not found in work_dir')
        problems = []
        rows = data.get('outputs') if isinstance(data, dict) else None
        if data.get('schema') != 'red-rose.execution_receipt.v1' or not isinstance(rows, list):
            problems.append({'file': None, 'problem': 'not a red-rose execution receipt'})
            rows = []
        for row in rows:
            rel = row.get('path') if isinstance(row, dict) else None
            try:
                fp = _inside(wd, rel, 'output', must_exist=True)
            except ValueError as exc:
                problems.append({'file': rel, 'problem': str(exc)})
                continue
            digest = _sha256(fp)
            if digest != row.get('sha256'):
                problems.append({'file': rel, 'problem': 'sha256 mismatch', 'now': digest})
            elif fp.stat().st_size != row.get('bytes'):
                problems.append({'file': rel, 'problem': 'size mismatch'})
        res = {'action': 'verify', 'receipt': receipt, 'verified': not problems,
               'outputs_checked': len(rows), 'problems': problems}
        return _pack('execution_receipt', res, common_a, common_l)
    if executable is None:
        raise ValueError('executable is required to write a receipt')
    name, exe_path = _resolve_exe(executable)
    argv = _args([] if args is None else args)
    execute = _bool(execute, 'execute')
    overwrite = _bool(overwrite, 'overwrite')
    if outputs is None:
        outputs = []
    if not isinstance(outputs, list) or len(outputs) > MAX_TASKS:
        raise ValueError(f'outputs must be a list of at most {MAX_TASKS} paths')
    if rpath.exists() and not overwrite:
        raise ValueError('receipt already exists; pass overwrite=True')
    if not execute:
        if exit_code is None or started_at is None or ended_at is None:
            raise ValueError('without execute=True give exit_code, started_at and ended_at')
        exit_code = _int(exit_code, -2**31, 2**32, 'exit_code')
        started_at = _num(started_at, 0, 1e11, 'started_at')
        ended_at = _num(ended_at, 0, 1e11, 'ended_at')
        if ended_at < started_at:
            raise ValueError('ended_at must not be before started_at')
    timeout = _num(timeout, 0.1, MAX_TIMEOUT, 'timeout')
    _approve(approve_write, 'execution_receipt')
    timed_out = False
    if execute:
        r = _exec(wd, exe_path, argv, timeout)
        exit_code, started_at, ended_at, timed_out = r['exit_code'], r['started_at'], r['ended_at'], r['timed_out']
    out_rows = []
    for o in outputs:
        fp = _inside(wd, o, 'output', must_exist=True)
        out_rows.append({'path': _rel(wd, fp), 'sha256': _sha256(fp), 'bytes': fp.stat().st_size})
    red_args, n_red = _redact(argv)
    data = {'schema': 'red-rose.execution_receipt.v1', 'command': name, 'args': red_args,
            'redactions': n_red, 'exit_code': exit_code, 'timed_out': timed_out,
            'started_at': started_at, 'ended_at': ended_at,
            'duration_s': round(ended_at - started_at, 4),
            'measured_by_op': execute, 'outputs': out_rows, 'written_at': round(time.time(), 3)}
    _write_json_atomic(rpath, data)
    res = {'action': 'write', 'receipt': receipt, 'receipt_sha256': _sha256(rpath), 'record': data}
    return _pack('execution_receipt', res,
                 common_a + ['without execute=True exit code and timings are caller-reported'], common_l)


# --------------------------------------------------------------------------- dispatcher

OPS = {
    'run_command': run_command, 'task_queue': task_queue, 'bounded_pool': bounded_pool,
    'timeout_cancel': timeout_cancel, 'perf_log': perf_log, 'smart_retry': smart_retry,
    'render_qa': render_qa, 'release_gate': release_gate, 'execution_receipt': execution_receipt,
}


def run(op, params=None):
    """Validate and dispatch: run('render_qa', {...}) -> {'op','result','assumptions','limits'}."""
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
