"""V29 W03: rose_env (probe, readiness, start, doctor-deps). Read-only behaviour is checked too."""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import rose_env as env
import rose_catalog

ROOT = Path(__file__).resolve().parent
PY = sys.executable
HAVE_FFMPEG = bool(shutil.which('ffmpeg') and shutil.which('ffprobe'))


def _cli(args, path=None, extra_env=None):
    e = dict(os.environ)
    e['PYTHONDONTWRITEBYTECODE'] = '1'
    if path is not None:
        e['PATH'] = path
    if extra_env:
        e.update(extra_env)
    return subprocess.run([PY, '-X', 'utf8', '-B', str(ROOT / 'rose_env.py')] + list(args),
                          capture_output=True, timeout=240, env=e, cwd=tempfile.gettempdir())


def _ffmpeg_op():
    """An op whose needs name ffmpeg and that takes no required input (PATH-stripped test)."""
    for op_id, entry in sorted(rose_catalog.load()['entries'].items()):
        if 'ffmpeg' in (entry.get('needs') or {}).get('programs', []) \
                and not any(p.get('required') for p in entry.get('params', [])):
            return op_id
    return None


class ProbeTests(unittest.TestCase):
    def test_probe_shape(self):
        p = env.probe()
        self.assertEqual(set(p), {'version', 'commit', 'skill_root', 'place', 'python', 'db', 'deps',
                                  'fonts', 'arabic_shaping', 'playbook_index', 'extensions_failed'})
        self.assertEqual(p['skill_root'], str(ROOT))
        self.assertTrue(Path(p['skill_root']).is_absolute())
        self.assertIn(p['place'], ('owner_pc', 'other_pc', 'sandbox'))
        self.assertEqual(set(p['deps']), {'ffmpeg', 'ffprobe', 'cairosvg', 'pillow'})
        for value in p['deps'].values():
            self.assertIsInstance(value, str)
        self.assertEqual(set(p['fonts']), {'arabic_font', 'has_presentation_forms'})
        self.assertTrue(p['arabic_shaping'] in ('pass', 'fail') or p['arabic_shaping'].startswith('skipped:'),
                        p['arabic_shaping'])
        self.assertIn(p['playbook_index'], ('present', 'absent'))
        self.assertIsInstance(p['extensions_failed'], list)
        self.assertEqual(set(p['db']), {'path', 'exists', 'is_private_default'})
        self.assertIsInstance(p['db']['is_private_default'], bool)

    def test_db_probe_never_creates_or_opens(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / 'not_yet.sqlite3'
            old = os.environ.get('RED_ROSE_DB')
            os.environ['RED_ROSE_DB'] = str(missing)
            try:
                db = env.probe()['db']
                self.assertFalse(db['exists'])
                self.assertFalse(db['is_private_default'])
                self.assertFalse(missing.exists(), 'probe must not create the database')
                existing = Path(tmp) / 'exists.sqlite3'
                existing.write_bytes(b'not really sqlite: probe must not open it')
                before = (existing.stat().st_size, existing.stat().st_mtime_ns)
                os.environ['RED_ROSE_DB'] = str(existing)
                self.assertTrue(env.probe()['db']['exists'])
                env.usable_counts()
                env.start_doc()
                self.assertEqual(before, (existing.stat().st_size, existing.stat().st_mtime_ns))
            finally:
                if old is None:
                    os.environ.pop('RED_ROSE_DB', None)
                else:
                    os.environ['RED_ROSE_DB'] = old

    def test_commit_is_none_without_git_folder(self):
        if not (ROOT / '.git').exists():
            self.assertIsNone(env._commit())
        else:
            self.assertTrue(env._commit() is None or len(env._commit()) == 12)

    def test_arabic_shaping_status_is_one_of_the_allowed_values(self):
        status = env._arabic_shaping()
        self.assertTrue(status in ('pass', 'fail') or status.startswith('skipped:'), status)


class ReadinessTests(unittest.TestCase):
    def test_every_op_has_a_label_and_counts_add_up(self):
        entries = rose_catalog.load()['entries']
        for op_id in entries:
            label = env.readiness(op_id)
            self.assertIn(label, env.LABELS, op_id)
        counts = env.usable_counts()
        self.assertEqual(set(counts), set(env.LABELS))
        self.assertEqual(sum(counts.values()), len(entries))

    def test_unknown_op_is_none(self):
        self.assertIsNone(env.readiness('no.such.adapter.op'))

    def test_status_rows_override_the_static_label(self):
        entries = rose_catalog.load()['entries']
        runnable = [op for op, e in entries.items()
                    if e.get('static_label') == 'coded_untested' and not e['approval']['needed']
                    and not e['needs']['pc_only']]
        self.assertGreaterEqual(len(runnable), 2)
        verified_op, broken_op = runnable[0], runnable[1]
        with tempfile.TemporaryDirectory() as tmp:
            status = Path(tmp) / 'VERIFIED_STATUS.json'
            status.write_text(json.dumps({'ops': {
                verified_op: {'status': 'verified', 'outcome': 'ok', 'error': None},
                broken_op: {'status': 'failed', 'outcome': 'error', 'error': 'sample'}}}), encoding='utf-8')
            old = env.VERIFIED_JSON
            env.VERIFIED_JSON = status
            try:
                self.assertEqual(env.readiness(verified_op), 'verified')
                self.assertEqual(env.readiness(broken_op), 'known_broken')
            finally:
                env.VERIFIED_JSON = old

    def test_missing_status_file_falls_back_to_static_labels(self):
        old = env.VERIFIED_JSON
        env.VERIFIED_JSON = Path(tempfile.gettempdir()) / 'rose_env_test_absent_status.json'
        try:
            self.assertEqual(env.load_status(), {})
            entries = rose_catalog.load()['entries']
            for op_id, entry in list(entries.items())[:25]:
                label = env.readiness(op_id)
                if entry.get('static_label') == 'needs_input':
                    self.assertIn(label, ('needs_input', 'needs_owner_approval', 'pc_only', 'unavailable_here'))
        finally:
            env.VERIFIED_JSON = old


class StartTests(unittest.TestCase):
    def test_start_text_is_short_and_names_the_skill(self):
        text = env.start_text(env.start_doc())
        lines = text.splitlines()
        self.assertLessEqual(len(lines), 40)
        self.assertLess(len(text), 2500)
        self.assertIn(str(ROOT), text)
        self.assertIn('MISSING:', text)
        self.assertIn('usable here:', text)
        for name in ('start', 'brief', 'run', 'check'):
            self.assertIn(name + ':', text)

    def test_start_cli_exit_zero_and_json(self):
        done = _cli(['start', '--json'])
        self.assertEqual(done.returncode, 0, done.stderr.decode('utf-8', 'replace')[-400:])
        doc = json.loads(done.stdout.decode('utf-8'))
        self.assertTrue(doc['ok'])
        self.assertEqual(doc['probe']['skill_root'], str(ROOT))
        self.assertEqual(doc['probe']['version'], 'V69')
        self.assertIn('version: "V69"', (ROOT/'SKILL.md').read_text(encoding='utf-8'))
        self.assertEqual(set(doc['usable']), set(env.LABELS))

    def test_doctor_deps_cli(self):
        done = _cli(['doctor-deps', '--json'])
        self.assertEqual(done.returncode, 0)
        doc = json.loads(done.stdout.decode('utf-8'))
        self.assertEqual(set(doc['deps']), {'ffmpeg', 'ffprobe', 'cairosvg', 'pillow'})
        self.assertIsInstance(doc['missing'], list)

    def test_register_adds_the_commands(self):
        parser = argparse.ArgumentParser()
        sub = parser.add_subparsers(dest='command', required=True)
        env.register(sub)
        import rose_selfcheck
        rose_selfcheck.register(sub)
        names = set(sub.choices)
        self.assertTrue({'start', 'doctor-deps', 'selfcheck', 'sample-media'} <= names)

    @unittest.skipIf(_ffmpeg_op() is None, 'no catalogue op needs ffmpeg')
    def test_path_stripped_of_ffmpeg_reports_missing_and_unavailable(self):
        # PATH is empty for the child process: ffmpeg cannot be found, nothing may crash.
        op = _ffmpeg_op()
        done = _cli(['start'], path='')
        self.assertEqual(done.returncode, 0, done.stderr.decode('utf-8', 'replace')[-400:])
        text = done.stdout.decode('utf-8')
        self.assertIn('ffmpeg', text)
        self.assertIn('MISSING: ', text)
        self.assertIn('ffmpeg', [line for line in text.splitlines() if line.startswith('MISSING:')][0])

        probe_code = ('import json, rose_env as e; print(json.dumps({"label": e.readiness(%r), '
                      '"ffmpeg": e.probe()["deps"]["ffmpeg"]}))' % op)
        e = dict(os.environ)
        e['PATH'] = ''
        e['PYTHONDONTWRITEBYTECODE'] = '1'
        child = subprocess.run([PY, '-X', 'utf8', '-B', '-c', probe_code], capture_output=True, timeout=240,
                               env=e, cwd=str(ROOT))
        self.assertEqual(child.returncode, 0, child.stderr.decode('utf-8', 'replace')[-400:])
        out = json.loads(child.stdout.decode('utf-8').strip().splitlines()[-1])
        self.assertEqual(out['label'], 'unavailable_here')
        self.assertEqual(out['ffmpeg'], 'MISSING')

        with tempfile.TemporaryDirectory() as tmp:
            run = subprocess.run([PY, '-X', 'utf8', '-B', str(ROOT / 'rose_run.py'), '--db',
                                  str(Path(tmp) / 'x.sqlite3'), 'run', op],
                                 capture_output=True, timeout=240, env=e, cwd=tmp)
            self.assertEqual(run.returncode, 4, run.stdout.decode('utf-8', 'replace')[-300:])
            self.assertEqual(json.loads(run.stdout.decode('utf-8').strip().splitlines()[-1])['outcome'],
                             'unavailable_here')


if __name__ == '__main__':
    unittest.main()
