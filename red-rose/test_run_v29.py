"""V29 W01: safe call layer (rose_ext loader, rose_io, `run`)."""
import argparse
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import rose_ext  # noqa: E402
import rose_io as rio  # noqa: E402
import rose_run  # noqa: E402

WIRED = 'rose_ext' in (ROOT / 'rose.py').read_text(encoding='utf-8')
ENTRY = ROOT / ('rose.py' if WIRED else 'rose_run.py')


def listing(path):
    p = Path(path)
    return sorted(str(x.relative_to(p)) for x in p.rglob('*')) if p.exists() else None


def wrap(adapter, out):
    """What capability_runtime.execute returns around a module result."""
    return {'audit_id': None, 'capability': adapter, 'status': 'executed', 'effect': 'read',
            'result': out, 'legacy_runtime_called': False}


class CliMixin:
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONIOENCODING='utf-8')
        self.env['RED_ROSE_DB'] = str(self.dir / 'dbdir' / 'rose.sqlite3')

    def tearDown(self):
        self.tmp.cleanup()

    def cli(self, *args, env=None):
        r = subprocess.run([sys.executable, '-X', 'utf8', str(ENTRY), 'run', *args], cwd=str(ROOT),
                           capture_output=True, env=env or self.env, timeout=300)
        out = r.stdout.decode('utf-8')
        return r.returncode, out, r.stderr.decode('utf-8', 'replace')

    def one_json(self, out):
        lines = [x for x in out.splitlines() if x.strip()]
        self.assertEqual(len(lines), 1, out[:500])
        return json.loads(lines[0])


class TestNormaliserApprovalStyles(unittest.TestCase):
    """Five approval-signalling styles, one fabricated and one real case each."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        (self.dir / 'src').mkdir()
        (self.dir / 'out').mkdir()
        self.wav = self.dir / 'src' / 'tone.wav'
        with wave.open(str(self.wav), 'wb') as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(8000)
            w.writeframes(b'\x00\x01' * 800)

    def tearDown(self):
        self.tmp.cleanup()

    def _wav(self):
        return self.wav

    def _real(self, style):
        out_dir = self.dir / 'out'
        if style == 'execute_status':  # studio.render write op through execute()
            env = rose_run.run_op('studio.render.render_timeline',
                                  {'spec': {'width': 64, 'height': 64}, 'output': str(out_dir / 'x.mp4')})
            return env, env['outcome']
        if style == 'permission_error':  # audio_v25._approved
            import audio_v25
            try:
                raw = wrap('audio.process', audio_v25.run('extract_pcm', {'source': str(self._wav()),
                                                                           'output': str(out_dir / 'a.wav')}))
            except Exception as exc:
                raw = exc
            self.assertIsInstance(raw, PermissionError)
            return raw, None
        if style == 'value_error':  # automation_v25._approve
            import automation_v25
            try:
                raw = wrap('automation.run', automation_v25.run('perf_log', {
                    'work_dir': str(out_dir), 'stage': 's', 'started_at': 0, 'ended_at': 1, 'result': 'ok'}))
            except Exception as exc:
                raw = exc
            self.assertIsInstance(raw, ValueError)
            return raw, None
        if style == 'nested_result_status':  # database_v25._approval
            import database_v25
            return wrap('database.manage', database_v25.run('safe_schema', {})), None
        if style == 'op_level_status':  # knowledge_v25._approval
            import knowledge_v25
            return wrap('knowledge.store', knowledge_v25.run('index_source', {
                'db': str(out_dir / 'k.sqlite3'), 'source': 's', 'licence': 'MIT', 'url_or_path': 'x',
                'revision': '1', 'text': 'hello'})), None
        raise AssertionError(style)

    FABRICATED = {
        'execute_status': {'capability': 'studio.render', 'op': 'render_timeline', 'status': 'approval_required',
                           'effect': 'write', 'detail': 'Use --approve-write ...'},
        'permission_error': PermissionError('this op writes a new file: pass approve_write=True after the owner approves'),
        'value_error': ValueError('perf_log writes inside work_dir and requires approve_write=True'),
        'nested_result_status': wrap('database.manage', {'op': 'safe_schema', 'result': {
            'status': 'approval_required', 'effect': 'write', 'changed': False}}),
        'op_level_status': wrap('knowledge.store', {'op': 'index_source', 'status': 'approval_required',
                                                     'result': {'status': 'approval_required', 'written': False}}),
    }

    def test_table(self):
        for style, raw in self.FABRICATED.items():
            with self.subTest(case='fabricated', style=style):
                n = rose_run.normalise(raw)
                self.assertEqual(n['outcome'], 'approval_required')
                self.assertFalse(n['ok'])
                self.assertEqual(rio.OUTCOME_EXIT[n['outcome']], 3)
        for style in self.FABRICATED:
            with self.subTest(case='real', style=style):
                before = listing(self.dir)
                raw, env_outcome = self._real(style)
                outcome = env_outcome or rose_run.normalise(raw)['outcome']
                self.assertEqual(outcome, 'approval_required')
                self.assertEqual(rio.OUTCOME_EXIT[outcome], 3)
                self.assertEqual(listing(self.dir), before, 'a file was created')

    def test_fail_closed(self):
        cases = [
            ({'status': 'executed', 'result': {'op': 'x', 'result': {'qa': {'passed': False}}}}, 'error'),
            (wrap('automation.run', {'op': 'release_gate', 'result': {'decision': 'blocked', 'reasons': ['r']}}), 'error'),
            (wrap('a.b', {'op': 'x', 'result': {'ok': False}}), 'error'),
            (wrap('a.b', {'op': 'x', 'result': {'warnings': ['arabic_unshaped: frame 1']}}), 'error'),
            (wrap('a.b', {'op': 'x', 'result': {'input': 'built_in_example'}}), 'example_only'),
            (ValueError('pc_only: playbook index not found at C:/x'), 'unavailable_here'),
            (ModuleNotFoundError("No module named 'cairosvg'", name='cairosvg'), 'unavailable_here'),
            (wrap('a.b', {'op': 'x', 'result': {'status': 'rendered_and_verified', 'warnings': ['w1']}}), 'ok'),
        ]
        for raw, want in cases:
            with self.subTest(raw=str(raw)[:80]):
                self.assertEqual(rose_run.normalise(raw)['outcome'], want)
        self.assertEqual(rose_run.normalise(cases[-1][0])['warnings'], ['w1'])


class TestIo(unittest.TestCase):
    def test_declared_string_stays_string(self):
        schema = {'title': {'type': 'string'}, 'n': {'type': 'integer'}, 'x': {'type': 'number'},
                  'flag': {'type': 'bool'}, 'rows': {'type': 'list'}}
        got = rio.parse_pairs(['title=123', 'n=5', 'x=0.8', 'flag=true', 'rows=[1,2]'], schema)
        self.assertEqual(got, {'title': '123', 'n': 5, 'x': 0.8, 'flag': True, 'rows': [1, 2]})
        self.assertEqual(rio.parse_pairs(['title=123', 'b=true']), {'title': '123', 'b': 'true'})
        self.assertEqual(rio.parse_pairs(['title:=123', 'o:={"a": 1}']), {'title': 123, 'o': {'a': 1}})
        with self.assertRaises(rio.ParamError):
            rio.parse_pairs(['n=abc'], schema)

    def test_inline_json_refused_with_hint(self):
        with self.assertRaises(rio.ParamError) as cm:
            rio.parse_pairs(['{text:abc}'])
        self.assertIn('--params-file', cm.exception.hint)

    def test_read_params_merge_order(self):
        with tempfile.TemporaryDirectory() as d:
            pf = Path(d) / 'p.json'
            pf.write_bytes('\ufeff{"text": "من الملف", "t": 1}'.encode('utf-8'))
            tf = Path(d) / 'w.txt'
            tf.write_bytes('كلام'.encode('utf-16'))
            ns = argparse.Namespace(params_file=str(pf), stdin=True, params=['t=0.5'],
                                    file_param=[f'words={tf}'])
            stdin = io.TextIOWrapper(io.BytesIO('{"style": "pop"}'.encode('utf-8')), encoding='utf-8')
            got = rio.read_params(ns, {'t': {'type': 'number'}}, stdin=stdin)
            stdin.detach()
        self.assertEqual(got, {'text': 'من الملف', 't': 0.5, 'style': 'pop', 'words': 'كلام'})

    def test_decode_cp1256_fallback(self):
        text, warning = rio.decode_bytes('مرحبا'.encode('cp1256'))
        self.assertEqual(text, 'مرحبا')
        self.assertIn('cp1256', warning)

    def test_save_fields_and_no_overwrite(self):
        import base64
        result = {'result': {'result': {'svg': '<svg>الوردة</svg>', 'png_base64': base64.b64encode(b'\x89PNG').decode()}}}
        with tempfile.TemporaryDirectory() as d:
            saved = rio.save_fields(result, [f'svg={d}/a.svg', f'png={d}/a.png'])
            self.assertEqual(Path(saved['svg']).read_bytes(), '<svg>الوردة</svg>'.encode('utf-8'))
            self.assertEqual(Path(saved['png']).read_bytes(), b'\x89PNG')
            with self.assertRaises(rio.ParamError):
                rio.save_fields(result, [f'svg={d}/a.svg'])
            with self.assertRaises(rio.ParamError) as cm:
                rio.save_fields(result, [f'nope={d}/n.txt'])
            self.assertIn('svg', cm.exception.allowed)
            with self.assertRaises(rio.ParamError):
                rio.parse_save_pairs([f'svg={d}/b.svg,png={d}/b.png'])
            self.assertEqual(sorted(os.listdir(d)), ['a.png', 'a.svg'])

    def test_write_json_no_bom(self):
        with tempfile.TemporaryDirectory() as d:
            p = rio.write_json(Path(d) / 'x.json', {'a': 'ورد'})
            data = Path(p).read_bytes()
            self.assertFalse(data.startswith(b'\xef\xbb\xbf'))
            self.assertTrue(data.endswith(b'\n'))
            with self.assertRaises(FileExistsError):
                rio.write_json(p, {}, overwrite=False)


class TestResolve(unittest.TestCase):
    def test_ids(self):
        self.assertEqual(rose_run.resolve_id('video.edit_suggest'), ('video.edit_suggest', None, 'flat'))
        self.assertEqual(rose_run.resolve_id('text.motion.kinetic_text'), ('text.motion', 'kinetic_text', 'module'))
        adapter, op, _ = rose_run.resolve_id('video.edit.' + next(iter(rose_run._module('video.edit').OPS)))
        self.assertEqual(adapter, 'video.edit')
        with self.assertRaises(rose_run.IdError) as cm:
            rose_run.resolve_id('text.motion')
        self.assertIn('text.motion.kinetic_text', cm.exception.allowed)
        with self.assertRaises(rose_run.IdError) as cm:
            rose_run.resolve_id('text.motion.kinetik_text')
        self.assertEqual(len(cm.exception.allowed), 5)
        self.assertIn('text.motion.kinetic_text', cm.exception.allowed)
        with self.assertRaises(rose_run.IdError):
            rose_run.resolve_id('video.recut.extra')

    def test_flat_schema_from_execute_source(self):
        schema, complete, _ = rose_run.schema_for('video.shot_score', None)
        self.assertTrue(complete)
        self.assertEqual(schema['max_clips']['type'], 'integer')
        self.assertTrue(schema['source']['required'])

    def test_unavailable_when_need_missing(self):
        orig = rose_run.needs_of
        rose_run.needs_of = lambda *a, **k: {'programs': ['no-such-program-zz-v29'], 'python': [], 'db': False, 'pc_only': False}
        try:
            env = rose_run.run_op('text.motion.kinetic_text', {'text': 'x'})
        finally:
            rose_run.needs_of = orig
        self.assertEqual(env['outcome'], 'unavailable_here')
        self.assertEqual(rose_run.exit_code(env), 4)
        self.assertIn('no-such-program-zz-v29', env['hint'])

    def test_db_op_without_db_is_unavailable_not_created(self):
        old = os.environ.pop('RED_ROSE_DB', None)
        orig = rose_run.PRIVATE_DB
        with tempfile.TemporaryDirectory() as d:
            rose_run.PRIVATE_DB = Path(d) / 'private' / 'memory.sqlite3'
            try:
                env = rose_run.run_op('memory.recall', {'query': 'x'})
            finally:
                rose_run.PRIVATE_DB = orig
                if old is not None:
                    os.environ['RED_ROSE_DB'] = old
            self.assertEqual(env['outcome'], 'unavailable_here')
            self.assertEqual(os.listdir(d), [])

    def test_envelope_keys(self):
        env = rose_run.run_op('text.motion.kinetic_text', {'text': 'الوردة', 't': 0.5})
        self.assertEqual(tuple(env), rose_run.ENVELOPE_KEYS)
        self.assertEqual(env['outcome'], 'ok')
        self.assertIsNone(env['audit_id'])


class TestRunCli(CliMixin, unittest.TestCase):
    def test_example_only(self):
        code, out, _ = self.cli('accounting.check.bank_reconcile')
        env = self.one_json(out)
        self.assertEqual((code, env['outcome'], env['ok']), (5, 'example_only', False))
        code, out, _ = self.cli('accounting.check.bank_reconcile', '--example-ok')
        env = json.loads(out)
        self.assertEqual(code, 0)
        self.assertFalse(env['ok'])
        self.assertTrue(any(w.startswith('NOT REAL DATA') for w in env['warnings']))

    def test_400_rows_params_file(self):
        rows = lambda p: [{'id': f'{p}{i}', 'date': f'2026-01-{1 + i % 28:02d}', 'amount': f'{100 + i}.00',
                           'ref': f'INV-{i}'} for i in range(400)]
        pf = self.dir / 'rows.json'
        rio.write_json(pf, {'ledger': rows('L'), 'bank': rows('B')})
        code, out, err = self.cli('accounting.check.bank_reconcile', '--params-file', str(pf))
        env = json.loads(out)
        self.assertEqual((code, env['outcome']), (0, 'ok'), err[-500:])
        self.assertEqual(rio.find_field(env['result'], 'counts')['matched'], 400)

    def test_unknown_param_lists_allowed(self):
        code, out, err = self.cli('studio.render.preview_frame', 'zzz=1')
        env = self.one_json(out)
        self.assertEqual(code, 1)
        self.assertNotIn('Traceback', out + err)
        for name in ('spec', 't', 'rasterize', 'png_width'):
            self.assertIn(name, env['allowed'])

    def test_save_needs_approval_then_writes(self):
        work = self.dir / 'work'
        work.mkdir()
        svg = (work / 'k.svg').as_posix()
        args = ['text.motion.kinetic_text', 'text=الوردة الحمراء', '--save', f'svg={svg}',
                'style=fade_up', 't=0.8', '--out', (work / 'step.json').as_posix()]
        code, out, _ = self.cli(*args)
        env = json.loads(out)
        self.assertEqual((code, env['outcome']), (3, 'approval_required'))
        self.assertEqual(len(env['would_write']), 2)
        self.assertIn('--approve-write', env['rerun_with'])
        self.assertEqual(os.listdir(work), [])
        code, out, _ = self.cli(*args, '--approve-write')
        self.assertEqual(code, 0, out[:500])
        self.assertIn('الوردة'.encode('utf-8'), Path(svg).read_bytes())
        step = json.loads((work / 'step.json').read_text(encoding='utf-8'))
        self.assertEqual(step['saved']['svg'], str(Path(svg).resolve()))
        code, out, _ = self.cli(*args, '--approve-write')  # never overwrite
        self.assertEqual(code, 1)
        self.assertIn('overwrite', json.loads(out)['error'])

    def test_write_op_without_approval(self):
        target = self.dir / 'render'
        target.mkdir()
        pf = self.dir / 'p.json'
        rio.write_json(pf, {'spec': {'width': 64, 'height': 64}, 'output': str(target / 'x.mp4')})
        code, out, _ = self.cli('studio.render.render_timeline', '--params-file', str(pf))
        env = json.loads(out)
        self.assertEqual((code, env['outcome'], env['effect']), (3, 'approval_required', 'write'))
        self.assertIn(str(target / 'x.mp4'), env['would_write'])
        self.assertEqual(os.listdir(target), [])

    def test_read_only_proof(self):
        db = Path(self.env['RED_ROSE_DB'])
        r = subprocess.run([sys.executable, '-X', 'utf8', str(ENTRY), 'run', '--help'], cwd=str(ROOT),
                           capture_output=True, env=self.env, timeout=120)
        self.assertEqual(r.returncode, 0)
        code, out, _ = self.cli('nope.not_an_op')
        self.assertEqual(code, 1)
        self.assertEqual(len(self.one_json(out)['allowed']), 5)
        code, _, _ = self.cli('studio.render.preview_frame', 'zzz=1')
        self.assertEqual(code, 1)
        code, _, _ = self.cli('text.motion.kinetic_text', '--bogus-flag')
        self.assertEqual(code, 2)
        self.assertFalse(db.exists())
        self.assertFalse(db.parent.exists())


class TestLoader(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = Path(self.tmp.name)
        (d / 'rose_broken_zz_v29.py').write_text('raise RuntimeError("broken on import")\n', encoding='utf-8')
        (d / 'rose_badreg_zz_v29.py').write_text(
            'def register(sub):\n    sub.add_parser("badreg-zz")\n    raise ValueError("register failed")\n',
            encoding='utf-8')
        sys.path.insert(0, str(d))

    def tearDown(self):
        sys.path.remove(self.tmp.name)
        for m in ('rose_broken_zz_v29', 'rose_badreg_zz_v29'):
            sys.modules.pop(m, None)
        self.tmp.cleanup()

    def test_missing_and_broken_modules_are_recorded(self):
        parser = argparse.ArgumentParser()
        sub = parser.add_subparsers(dest='command')
        sub.add_parser('doctor')
        res = rose_ext.load(sub, ['rose_run', 'rose_missing_zz_v29', 'rose_broken_zz_v29', 'rose_badreg_zz_v29'])
        failed = {f['module'] for f in res['failed']}
        self.assertEqual(failed, {'rose_missing_zz_v29', 'rose_broken_zz_v29', 'rose_badreg_zz_v29'})
        self.assertIn('rose_run', res['loaded'])
        self.assertEqual({f['module'] for f in rose_ext.LAST_LOAD['failed']}, failed)
        self.assertNotIn('badreg-zz', sub.choices)  # rolled back
        args = parser.parse_args(['run', 'x.y'])
        self.assertIs(args.ext_func, rose_run.handler)
        self.assertEqual(parser.parse_args(['doctor']).command, 'doctor')

    def test_rose_py_survives_a_missing_extension(self):
        with tempfile.TemporaryDirectory() as d:
            report = Path(d) / 'last_load.json'
            driver = Path(d) / 'driver.py'
            driver.write_text(
                'import sys, json\n'
                f'sys.path.insert(0, {str(ROOT)!r})\n'
                'import rose_ext\n'
                'rose_ext.EXT_MODULES.append("rose_missing_zz_v29")\n'
                'import rose\n'
                'code = 0\n'
                'try:\n'
                '    rose.main([sys.argv[1]])\n'
                'except SystemExit as e:\n'
                '    code = e.code or 0\n'
                f'open({str(report)!r}, "w", encoding="utf-8").write(json.dumps(rose_ext.LAST_LOAD))\n'
                'sys.exit(code)\n', encoding='utf-8')
            env = dict(os.environ, RED_ROSE_DB=str(Path(d) / 'db.sqlite3'), PYTHONDONTWRITEBYTECODE='1')
            for cmd in ('doctor', 'capabilities'):
                with self.subTest(cmd=cmd):
                    r = subprocess.run([sys.executable, '-X', 'utf8', str(driver), cmd], cwd=str(ROOT),
                                       capture_output=True, env=env, timeout=300)
                    self.assertEqual(r.returncode, 0, r.stderr[-800:])
                    if WIRED:
                        last = json.loads(report.read_text(encoding='utf-8'))
                        self.assertIn('rose_missing_zz_v29', [f['module'] for f in last['failed']])


if __name__ == '__main__':
    unittest.main()
