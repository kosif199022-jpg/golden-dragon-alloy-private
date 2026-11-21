"""Tests for automation_v25 (Red Rose V25 automation ops 21.01-21.10, no 21.04)."""
import ast
import hashlib
import json
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path

import automation_v25 as A

HAS_FF = bool(shutil.which('ffmpeg') and shutil.which('ffprobe'))
PY = sys.executable


def _ffmpeg(wd, name, src, extra=(), frames=None, audio=True):
    """Make a tiny synthetic clip through the module's own run_command op."""
    args = ['-v', 'error', '-y', '-f', 'lavfi', '-i', src]
    if audio:
        args += ['-f', 'lavfi', '-i', 'sine=frequency=440:duration=1']
    if frames is not None:
        args += ['-frames:v', str(frames)]
    args += ['-c:v', 'libx264', '-pix_fmt', 'yuv420p']
    args += (['-c:a', 'aac', '-shortest'] if audio else ['-an'])
    args += list(extra) + [name]
    out = A.run('run_command', {'work_dir': wd, 'executable': 'ffmpeg', 'args': args,
                                'timeout': 60, 'approve_write': True})
    if out['result']['exit_code'] != 0:
        raise RuntimeError(out['result']['stderr'])
    return Path(wd) / name


class Interface(unittest.TestCase):
    def test_topics_ops_effects(self):
        self.assertEqual(set(A.TOPICS), {'21.01', '21.02', '21.03', '21.05', '21.06',
                                         '21.07', '21.08', '21.09', '21.10'})
        self.assertEqual(set(A.TOPICS.values()), set(A.OPS))
        self.assertEqual(set(A.EFFECTS), set(A.OPS))
        self.assertTrue(set(A.EFFECTS.values()) <= {'read', 'write'})
        for op in ('smart_retry', 'render_qa', 'release_gate'):
            self.assertEqual(A.EFFECTS[op], 'read')

    def test_empty_params_raise_valueerror(self):
        for op in A.OPS:
            with self.subTest(op=op), self.assertRaises(ValueError):
                A.run(op, {})

    def test_unknown_param_and_bad_op(self):
        with tempfile.TemporaryDirectory() as wd:
            with self.assertRaises(ValueError):
                A.run('render_qa', {'work_dir': wd, 'path': 'x.mp4', 'bogus': 1})
        with self.assertRaises(ValueError):
            A.run('nope', {})

    def test_source_rules(self):
        src = Path(A.__file__).read_text(encoding='utf-8')
        tree = ast.parse(src)
        banned = {'socket', 'urllib', 'http', 'requests', 'ctypes'}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                self.assertFalse({a.name.split('.')[0] for a in node.names} & banned)
            if isinstance(node, ast.ImportFrom):
                self.assertNotIn((node.module or '').split('.')[0], banned)
            if isinstance(node, ast.Call):
                f = node.func
                fname = f.id if isinstance(f, ast.Name) else getattr(f, 'attr', '')
                self.assertNotIn(fname, {'eval', 'exec', 'print', 'system', 'popen'})
                if fname in ('run', 'Popen') and isinstance(f, ast.Attribute) \
                        and getattr(f.value, 'id', '') == 'subprocess':
                    self.assertIsInstance(node.args[0], ast.List)
                    kws = {k.arg: k.value for k in node.keywords}
                    self.assertNotIn('shell', kws)
                    if fname == 'run':
                        self.assertIn('timeout', kws)
                        self.assertTrue(getattr(kws.get('capture_output'), 'value', False))

    def test_write_requires_approval_and_workdir(self):
        with tempfile.TemporaryDirectory() as wd:
            with self.assertRaises(ValueError):
                A.run('run_command', {'work_dir': wd, 'executable': 'python', 'args': ['-c', 'pass']})
            with self.assertRaises(ValueError):
                A.run('run_command', {'work_dir': str(Path(wd) / 'missing'), 'executable': 'python',
                                      'args': ['-c', 'pass'], 'approve_write': True})


class RunCommand(unittest.TestCase):
    def test_shell_requests_refused(self):
        with tempfile.TemporaryDirectory() as wd:
            bad = [{'executable': 'cmd /c del', 'args': []},
                   {'executable': 'cmd', 'args': ['/c', 'del', '*']},
                   {'executable': 'sh', 'args': ['-c', 'rm -rf x']},
                   {'executable': 'sh -c', 'args': []},
                   {'executable': 'python', 'args': 'python -c pass'},
                   {'executable': 'python', 'args': ['-c', 'pass', '&&', 'del', 'x']},
                   {'executable': 'python', 'args': ['-c', 'pass'], 'shell': True},
                   {'executable': 'node', 'args': []}]
            for b in bad:
                with self.subTest(b=b), self.assertRaises(ValueError):
                    A.run('run_command', dict(b, work_dir=wd, approve_write=True))

    def test_python_one_liner_runs_in_work_dir(self):
        with tempfile.TemporaryDirectory() as wd:
            out = A.run('run_command', {'work_dir': wd, 'executable': 'python', 'approve_write': True,
                                        'args': ['-c', "import os;open('hi.txt','w').write('ok');print('done')"]})
            r = out['result']
            self.assertEqual(r['exit_code'], 0)
            self.assertEqual(r['status'], 'ok')
            self.assertIn('done', r['stdout'])
            self.assertEqual((Path(wd) / 'hi.txt').read_text(), 'ok')

    def test_timeout_reported(self):
        with tempfile.TemporaryDirectory() as wd:
            r = A.run('run_command', {'work_dir': wd, 'executable': PY, 'timeout': 0.5, 'approve_write': True,
                                      'args': ['-c', 'import time; time.sleep(20)']})['result']
            self.assertTrue(r['timed_out'])
            self.assertLess(r['duration_s'], 10)


class TaskQueue(unittest.TestCase):
    def _task(self, tid, prio=0, **kw):
        code = f"open('log.txt','a').write('{tid}\\n')"
        return dict({'id': tid, 'priority': prio, 'executable': 'python', 'args': ['-c', code]}, **kw)

    def test_crash_then_restart_exactly_once(self):
        with tempfile.TemporaryDirectory() as wd:
            tasks = [self._task('a', 1), self._task('b', 5, resources=['gpu']), self._task('c', 3),
                     self._task('d', 0), self._task('e', 2)]
            A.run('task_queue', {'work_dir': wd, 'action': 'enqueue', 'tasks': tasks, 'approve_write': True})
            first = A.run('task_queue', {'work_dir': wd, 'action': 'run', 'max_run': 2,
                                         'approve_write': True})['result']
            self.assertEqual([t['id'] for t in first['ran']], ['b', 'c'])  # priority order
            # simulate a hard crash while 'e' was running (process died before recording)
            qf = Path(wd) / 'main.queue.json'
            state = json.loads(qf.read_text(encoding='utf-8'))
            for t in state['tasks']:
                if t['id'] == 'e':
                    t['state'] = 'running'
                    t['idempotent'] = True
            qf.write_text(json.dumps(state), encoding='utf-8')
            second = A.run('task_queue', {'work_dir': wd, 'action': 'run', 'approve_write': True})['result']
            self.assertEqual(second['recovered'], [{'id': 'e', 'now': 'pending'}])
            self.assertTrue(second['complete'])
            lines = (Path(wd) / 'log.txt').read_text().split()
            self.assertEqual(sorted(lines), ['a', 'b', 'c', 'd', 'e'])  # each exactly once
            third = A.run('task_queue', {'work_dir': wd, 'action': 'run', 'approve_write': True})['result']
            self.assertEqual(third['ran'], [])

    def test_non_idempotent_interrupted_not_rerun(self):
        with tempfile.TemporaryDirectory() as wd:
            A.run('task_queue', {'work_dir': wd, 'action': 'enqueue', 'tasks': [self._task('x')],
                                 'approve_write': True})
            qf = Path(wd) / 'main.queue.json'
            state = json.loads(qf.read_text(encoding='utf-8'))
            state['tasks'][0]['state'] = 'running'
            qf.write_text(json.dumps(state), encoding='utf-8')
            r = A.run('task_queue', {'work_dir': wd, 'action': 'run', 'approve_write': True})['result']
            self.assertEqual(r['counts']['interrupted'], 1)
            self.assertFalse((Path(wd) / 'log.txt').exists())
            A.run('task_queue', {'work_dir': wd, 'action': 'requeue', 'ids': ['x'], 'approve_write': True})
            r = A.run('task_queue', {'work_dir': wd, 'action': 'run', 'approve_write': True})['result']
            self.assertTrue(r['complete'])

    def test_resource_filter_and_duplicates(self):
        with tempfile.TemporaryDirectory() as wd:
            A.run('task_queue', {'work_dir': wd, 'action': 'enqueue', 'approve_write': True,
                                 'tasks': [self._task('g', resources=['gpu']), self._task('c')]})
            r = A.run('task_queue', {'work_dir': wd, 'action': 'run', 'available_resources': ['cpu'],
                                     'approve_write': True})['result']
            self.assertEqual([t['id'] for t in r['ran']], ['c'])
            with self.assertRaises(ValueError):
                A.run('task_queue', {'work_dir': wd, 'action': 'enqueue', 'tasks': [self._task('g')],
                                     'approve_write': True})
            with self.assertRaises(ValueError):
                A.run('task_queue', {'work_dir': wd, 'action': 'enqueue', 'approve_write': True,
                                     'tasks': [{'id': 'z', 'executable': 'cmd', 'args': ['/c', 'dir']}]})


class BoundedPool(unittest.TestCase):
    def test_bound_and_same_path_serialised(self):
        sleep = "import time,sys; time.sleep(0.35)"
        append = "import time,sys; f=open(sys.argv[1],'a'); f.write('s'); f.flush(); time.sleep(0.35); f.write('e'); f.close()"
        with tempfile.TemporaryDirectory() as wd:
            tasks = [{'id': f't{i}', 'executable': 'python', 'args': ['-c', sleep]} for i in range(4)]
            tasks += [{'id': 'w1', 'executable': 'python', 'args': ['-c', append, '{output}'], 'output': 'same.txt'},
                      {'id': 'w2', 'executable': 'python', 'args': ['-c', append, '{output}'], 'output': 'same.txt'}]
            r = A.run('bounded_pool', {'work_dir': wd, 'tasks': tasks, 'max_workers': 2,
                                       'approve_write': True})['result']
            self.assertTrue(r['all_ok'])
            self.assertLessEqual(r['max_concurrent_observed'], 2)
            self.assertEqual(r['max_concurrent_observed'], 2)
            self.assertEqual(r['same_path_overlaps'], [])
            self.assertEqual((Path(wd) / 'same.txt').read_text(), 'sese')
            w = {t['id']: t for t in r['tasks'] if t['id'] in ('w1', 'w2')}
            a, b = sorted(w.values(), key=lambda t: t['start_s'])
            self.assertLessEqual(a['end_s'], b['start_s'])

    def test_output_outside_workdir_refused(self):
        with tempfile.TemporaryDirectory() as wd:
            with self.assertRaises(ValueError):
                A.run('bounded_pool', {'work_dir': wd, 'approve_write': True, 'tasks': [
                    {'id': 'x', 'executable': 'python', 'args': ['-c', 'pass'], 'output': '../evil.txt'}]})


class TimeoutCancel(unittest.TestCase):
    def test_killed_and_no_partial_then_rerun(self):
        hang = "import sys,time; f=open(sys.argv[1],'w'); f.write('partial'); f.flush(); time.sleep(30)"
        with tempfile.TemporaryDirectory() as wd:
            t0 = time.monotonic()
            r = A.run('timeout_cancel', {'work_dir': wd, 'executable': 'python', 'args': ['-c', hang, '{output}'],
                                         'output': 'result.txt', 'timeout': 1.0, 'approve_write': True})['result']
            self.assertLess(time.monotonic() - t0, 15)
            self.assertEqual(r['status'], 'timeout_killed')
            self.assertTrue(r['timed_out'])
            self.assertTrue(r['partial_existed'])
            self.assertTrue(r['partial_removed'])
            self.assertEqual(list(Path(wd).iterdir()), [])  # no partial or final file left
            ok = "import sys; open(sys.argv[1],'w').write('full')"
            r2 = A.run('timeout_cancel', {'work_dir': wd, 'executable': 'python', 'args': ['-c', ok, '{output}'],
                                          'output': 'result.txt', 'timeout': 20, 'approve_write': True})['result']
            self.assertEqual(r2['status'], 'ok')
            self.assertEqual((Path(wd) / 'result.txt').read_text(), 'full')
            self.assertEqual([p.name for p in Path(wd).iterdir()], ['result.txt'])
            with self.assertRaises(ValueError):  # no silent overwrite
                A.run('timeout_cancel', {'work_dir': wd, 'executable': 'python', 'args': ['-c', ok, '{output}'],
                                         'output': 'result.txt', 'approve_write': True})


@unittest.skipUnless(HAS_FF, 'ffmpeg/ffprobe required')
class PerfLog(unittest.TestCase):
    def test_frame_mismatch_flagged(self):
        with tempfile.TemporaryDirectory() as wd:
            _ffmpeg(wd, 'clip.mp4', 'testsrc2=size=64x48:rate=10', frames=10, audio=False)
            now = time.time()
            bad = A.run('perf_log', {'work_dir': wd, 'stage': 'render', 'started_at': now - 2, 'ended_at': now,
                                     'result': 'ok', 'frames_reported': 12, 'output': 'clip.mp4',
                                     'approve_write': True})['result']
            self.assertTrue(bad['mismatch'])
            self.assertEqual(bad['entry']['frames_measured'], 10)
            self.assertIn('frame_mismatch', bad['entry']['flags'])
            good = A.run('perf_log', {'work_dir': wd, 'stage': 'render', 'started_at': now - 1, 'ended_at': now,
                                      'result': 'ok', 'frames_reported': 10, 'output': 'clip.mp4',
                                      'approve_write': True})['result']
            self.assertFalse(good['mismatch'])
            self.assertTrue(good['reconciled'])
            lines = (Path(wd) / 'perf_log.jsonl').read_text(encoding='utf-8').splitlines()
            self.assertEqual(len(lines), 2)
            s = A.run('perf_log', {'work_dir': wd, 'action': 'summary'})['result']
            self.assertEqual(s['stages']['render']['count'], 2)
            self.assertEqual(len(s['flagged']), 1)


class SmartRetry(unittest.TestCase):
    def test_permanent_not_retried(self):
        calls = []

        def boom():
            calls.append(1)
            raise ValueError('bad input')
        r = A.run('smart_retry', {'operation': 'encode', 'idempotent': True, 'call': boom,
                                  'sleep': lambda s: None})['result']
        self.assertEqual(r['status'], 'permanent_error_not_retried')
        self.assertEqual(len(calls), 1)
        plan = A.run('smart_retry', {'operation': 'encode', 'idempotent': True,
                                     'outcomes': [{'exit_code': 1}, {'ok': True}]})['result']
        self.assertEqual(plan['retries'], 0)

    def test_transient_backoff_then_success(self):
        seq = iter([TimeoutError('slow'), 75, 'value'])
        slept = []

        def flaky():
            v = next(seq)
            if isinstance(v, Exception):
                raise v
            return v
        r = A.run('smart_retry', {'operation': 'fetch', 'idempotent': True, 'call': flaky,
                                  'base_delay': 0.5, 'sleep': slept.append})['result']
        self.assertEqual(r['status'], 'succeeded')
        self.assertEqual(slept, [0.5, 1.0])
        self.assertEqual(r['value'], 'value')

    def test_non_idempotent_refused_without_key(self):
        calls = []
        r = A.run('smart_retry', {'operation': 'publish', 'idempotent': False,
                                  'call': lambda: calls.append(1)})['result']
        self.assertEqual(r['status'], 'refused')
        self.assertEqual(calls, [])
        r = A.run('smart_retry', {'operation': 'publish', 'idempotent': False, 'idempotency_key': 'rel-25-1',
                                  'outcomes': [{'exception': 'TimeoutError'}] * 5, 'max_retries': 3})['result']
        self.assertEqual(r['status'], 'gave_up_retries_exhausted')
        self.assertEqual([a['delay_before_next_s'] for a in r['attempts']], [0.5, 1.0, 2.0, None])


@unittest.skipUnless(HAS_FF, 'ffmpeg/ffprobe required')
class RenderQA(unittest.TestCase):
    def test_good_passes_truncated_and_black_rejected(self):
        with tempfile.TemporaryDirectory() as wd:
            good = _ffmpeg(wd, 'good.mp4', 'testsrc2=size=64x48:rate=10:duration=1')
            r = A.run('render_qa', {'work_dir': wd, 'path': 'good.mp4'})['result']
            self.assertEqual(r['decision'], 'accepted', r['checks'])
            data = good.read_bytes()
            (Path(wd) / 'cut.mp4').write_bytes(data[:len(data) // 2])
            r = A.run('render_qa', {'work_dir': wd, 'path': 'cut.mp4'})['result']
            self.assertEqual(r['decision'], 'rejected')
            self.assertIn('probe_and_full_decode', r['failed_checks'])
            _ffmpeg(wd, 'black.mp4', 'color=c=black:size=64x48:rate=10:duration=1')
            r = A.run('render_qa', {'work_dir': wd, 'path': 'black.mp4'})['result']
            self.assertEqual(r['failed_checks'], ['first_frame_not_black'])
            _ffmpeg(wd, 'mute.mp4', 'testsrc2=size=64x48:rate=10:duration=1', audio=False)
            r = A.run('render_qa', {'work_dir': wd, 'path': 'mute.mp4'})['result']
            self.assertEqual(r['decision'], 'rejected')


class ReleaseGate(unittest.TestCase):
    def _setup(self, wd, tests):
        p = Path(wd) / 'app.zip'
        p.write_bytes(b'release bytes')
        digest = hashlib.sha256(b'release bytes').hexdigest()
        (Path(wd) / 'checksums.json').write_text(json.dumps({'version': '25.0', 'files': {'app.zip': digest}}))
        (Path(wd) / 'approval.json').write_text(json.dumps({'approved': True, 'approved_by': 'owner',
                                                            'action': 'tag v25', 'version': '25.0',
                                                            'scope': ['app.zip']}))
        (Path(wd) / 'test_record.json').write_text(json.dumps(tests))

    def test_failing_tests_block(self):
        with tempfile.TemporaryDirectory() as wd:
            self._setup(wd, {'status': 'passed', 'passed': 40, 'failed': 0, 'errors': 0,
                             'command': 'python -m unittest'})
            r = A.run('release_gate', {'work_dir': wd})['result']
            self.assertEqual(r['decision'], 'ready', r['reasons'])
            self.assertFalse(r['published'])
            self._setup(wd, {'status': 'failed', 'passed': 39, 'failed': 1, 'errors': 0,
                             'command': 'python -m unittest'})
            r = A.run('release_gate', {'work_dir': wd})['result']
            self.assertEqual(r['decision'], 'blocked')

    def test_missing_and_tampered_block(self):
        with tempfile.TemporaryDirectory() as wd:
            self._setup(wd, {'status': 'passed', 'passed': 1, 'failed': 0, 'errors': 0, 'command': 'x'})
            (Path(wd) / 'app.zip').write_bytes(b'tampered')
            r = A.run('release_gate', {'work_dir': wd})['result']
            self.assertEqual(r['decision'], 'blocked')
            (Path(wd) / 'approval.json').unlink()
            r = A.run('release_gate', {'work_dir': wd})['result']
            self.assertIn('approval missing', r['reasons'])


class ExecutionReceipt(unittest.TestCase):
    def test_redaction_and_tamper_detection(self):
        with tempfile.TemporaryDirectory() as wd:
            secret = 'ghp_' + 'A1b2C3d4E5f6G7h8I9j0K1l2'
            code = "import sys; open('out.bin','wb').write(b'abc')"
            r = A.run('execution_receipt', {'work_dir': wd, 'executable': 'python', 'execute': True,
                                            'args': ['-c', code, '--token', 'plain-secret-value',
                                                     f'--api-key={secret}', f'auth={secret}'],
                                            'outputs': ['out.bin'], 'approve_write': True})['result']
            text = (Path(wd) / 'receipt.json').read_text(encoding='utf-8')
            self.assertNotIn('plain-secret-value', text)
            self.assertNotIn(secret, text)
            self.assertEqual(r['record']['exit_code'], 0)
            self.assertGreaterEqual(r['record']['redactions'], 3)
            v = A.run('execution_receipt', {'work_dir': wd, 'action': 'verify'})['result']
            self.assertTrue(v['verified'], v)
            p = Path(wd) / 'out.bin'
            p.write_bytes(b'abd')
            v = A.run('execution_receipt', {'work_dir': wd, 'action': 'verify'})['result']
            self.assertFalse(v['verified'])
            self.assertEqual(v['problems'][0]['problem'], 'sha256 mismatch')
            with self.assertRaises(ValueError):  # no silent overwrite of a receipt
                A.run('execution_receipt', {'work_dir': wd, 'executable': 'python', 'exit_code': 0,
                                            'started_at': 1, 'ended_at': 2, 'approve_write': True})


if __name__ == '__main__':
    unittest.main()
