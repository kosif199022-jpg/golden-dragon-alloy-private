"""V29 W03: rose_selfcheck (runs, gates, status file) and rose_fixtures / sample-media."""
import hashlib
import json
import os
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from unittest import mock

import rose_catalog
import rose_env as env
import rose_fixtures
import rose_selfcheck as sc

ROOT = Path(__file__).resolve().parent
PY = sys.executable
HAVE_FFMPEG = bool(shutil.which('ffmpeg') and shutil.which('ffprobe'))
SKIP_MEDIA = 'ffmpeg/ffprobe not on PATH: media checks skipped'


def _tree_hash(folder, skip_dirs=('__pycache__',)):
    rows = []
    for path in sorted(Path(folder).rglob('*')):
        if any(part in skip_dirs for part in path.relative_to(folder).parts):
            continue
        rel = path.relative_to(folder).as_posix()
        rows.append(f"{rel}|{path.stat().st_size if path.is_file() else '/'}")
    return hashlib.sha256('\n'.join(rows).encode('utf-8')).hexdigest()


def _mtime_or_none(path):
    try:
        return path.stat().st_mtime_ns
    except OSError:
        return None


def _write_gate_op():
    """(adapter, op_id) for a write op that takes no required parameter, or (None, None)."""
    for op_id, entry in sorted(rose_catalog.load()['entries'].items()):
        required = [p for p in entry['params'] if p['required']]
        if entry['effect'] == 'write' and not required and not entry['needs']['pc_only'] \
                and not entry['needs']['network'] and not (set(entry['needs']['programs']) - {'ffmpeg', 'ffprobe'}):
            return entry['adapter'], op_id
    return None, None


class ClassifyTests(unittest.TestCase):
    def test_every_op_is_classified_consistently(self):
        entries = rose_catalog.load()['entries']
        for op_id, entry in entries.items():
            kind, status, reason = sc._classify(op_id, entry)
            self.assertIn(kind, ('static', 'run', 'gate'), op_id)
            if kind == 'static':
                self.assertIn(status, ('needs_input', 'unavailable_here'), op_id)
                self.assertTrue(reason, op_id)
            if kind == 'run':
                self.assertTrue(entry['runs_with_defaults'] and entry['example'], op_id)
            if kind == 'gate':
                self.assertEqual(entry['effect'], 'write', op_id)

    def test_write_op_with_required_input_is_not_called(self):
        entry = {'effect': 'write', 'params': [{'name': 'x', 'required': True}],
                 'needs': {'pc_only': False, 'network': False, 'programs': []}}
        self.assertEqual(sc._classify('a.b', entry)[0], 'static')


class RunTests(unittest.TestCase):
    def test_small_adapter_run_is_clean_and_writes_nothing(self):
        # The skill folder must be byte-for-byte the same listing, the default DB must not be touched,
        # and the parent process must not use the network while selfcheck runs.
        private_db = Path.home() / '.red-rose' / 'memory.sqlite3'
        before_tree = _tree_hash(ROOT)
        before_db = _mtime_or_none(private_db)
        before_status = (ROOT / 'references' / 'VERIFIED_STATUS.json').read_bytes()

        class NoNetwork:
            def __init__(self, *a, **k):
                raise OSError('network is not allowed in selfcheck')

        with mock.patch.object(socket, 'socket', NoNetwork):
            result = sc.run(adapter='agents.coordinate', quick=True)

        self.assertEqual(result['failed'], [])
        self.assertEqual(sum(result['totals'].values()), len(result['ops']))
        self.assertEqual(set(result['totals']), set(sc.TOTAL_KEYS))
        for op_id, row in result['ops'].items():
            self.assertIn(row['status'], sc.TOTAL_KEYS, op_id)
            self.assertIsInstance(row['seconds'], float)
        self.assertGreaterEqual(result['totals']['verified'] + result['totals']['runs_with_defaults'], 1)
        self.assertEqual(_tree_hash(ROOT), before_tree)
        self.assertEqual(_mtime_or_none(private_db), before_db)
        self.assertEqual((ROOT / 'references' / 'VERIFIED_STATUS.json').read_bytes(), before_status)

    def test_write_gate_holds_without_approval(self):
        adapter, op_id = _write_gate_op()
        if op_id is None:
            self.skipTest('no write op without required input in the catalogue')
        result = sc.run(adapter=adapter, quick=False)
        row = result['ops'][op_id]
        self.assertEqual(row['status'], 'not_run_needs_approval', row)
        self.assertEqual(row['outcome'], 'approval_required')

    def test_unknown_adapter_is_refused(self):
        with self.assertRaises(ValueError):
            sc.run(adapter='no.such.adapter')


class StatusFileTests(unittest.TestCase):
    def test_save_without_approval_writes_nothing(self):
        result = {'adapter': 'x', 'quick': True, 'platform': 'test', 'ops': {}}
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / 'VERIFIED_STATUS.json'
            target.write_text('{"ops": {}}', encoding='utf-8')
            doc = sc.save_status(result, approve_write=False, path=target)
            self.assertEqual(doc['outcome'], 'approval_required')
            self.assertEqual(target.read_text(encoding='utf-8'), '{"ops": {}}')

    def test_save_with_approval_has_no_dates_or_timings(self):
        result = {'adapter': None, 'quick': False, 'platform': 'win32 py3.12', 'ops': {
            'a.b': {'status': 'verified', 'seconds': 1.23, 'outcome': 'ok', 'error': None},
            'a.c': {'status': 'needs_input', 'seconds': 0.0, 'outcome': None, 'error': 'needs input'},
            'a.d': {'status': 'failed', 'seconds': 2.0, 'outcome': 'error', 'error': 'boom'}}}
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / 'VERIFIED_STATUS.json'
            sc.save_status(result, approve_write=True, path=target)
            doc = json.loads(target.read_text(encoding='utf-8'))
            self.assertEqual(set(doc['ops']), {'a.b', 'a.d'})
            self.assertEqual(doc['ops']['a.d']['status'], 'failed')
            self.assertNotIn('seconds', json.dumps(doc))
            self.assertEqual(doc['counts'], {'failed': 1, 'verified': 1})
            self.assertEqual(doc['platform'], 'win32 py3.12')
            text = target.read_text(encoding='utf-8')
            self.assertNotRegex(text, r'20\d\d-\d\d-\d\d')

    def test_cli_save_status_without_approval_exits_3_and_writes_nothing(self):
        before = (ROOT / 'references' / 'VERIFIED_STATUS.json').read_bytes()
        e = dict(os.environ)
        e['PYTHONDONTWRITEBYTECODE'] = '1'
        done = subprocess.run([PY, '-X', 'utf8', '-B', str(ROOT / 'rose_env.py'), 'selfcheck', '--save-status',
                               '--json'], capture_output=True, timeout=240, env=e, cwd=tempfile.gettempdir())
        self.assertEqual(done.returncode, 3)
        self.assertEqual(json.loads(done.stdout.decode('utf-8'))['outcome'], 'approval_required')
        self.assertEqual((ROOT / 'references' / 'VERIFIED_STATUS.json').read_bytes(), before)


class FixtureTests(unittest.TestCase):
    def test_sample_media_without_approval_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / 'fx'
            doc = sc.sample_media(target, approve_write=False)
            self.assertEqual(doc['outcome'], 'approval_required')
            self.assertFalse(target.exists())

    def test_sample_media_refuses_to_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / 'ledger.csv').write_text('keep me\n', encoding='utf-8')
            doc = sc.sample_media(tmp, approve_write=True)
            self.assertEqual(doc['outcome'], 'error')
            self.assertEqual((Path(tmp) / 'ledger.csv').read_text(encoding='utf-8'), 'keep me\n')

    def test_fixtures_refuse_the_private_folder(self):
        private = Path.home() / '.red-rose' / 'rose_env_test_never_created'
        with self.assertRaises(ValueError):
            rose_fixtures.make(private)
        self.assertFalse(private.exists())

    def test_data_fixtures(self):
        with tempfile.TemporaryDirectory() as tmp:
            made = rose_fixtures.make(Path(tmp) / 'data')
            words = json.loads(Path(made['WORDS_JSON']).read_text(encoding='utf-8'))['words']
            self.assertEqual(len(words), 4)
            self.assertTrue(any(any('ً' <= ch <= 'ْ' for ch in w['word']) for w in words))
            for w in words:
                self.assertLess(w['start'], w['end'])
            ledger = Path(made['LEDGER_CSV']).read_text(encoding='utf-8').splitlines()
            bank = Path(made['BANK_CSV']).read_text(encoding='utf-8').splitlines()
            self.assertEqual(ledger[0], 'id,date,amount,ref')
            self.assertEqual(len(ledger), 4)
            led_total = sum(Decimal(line.split(',')[2]) for line in ledger[1:])
            bank_total = sum(Decimal(line.split(',')[2]) for line in bank[1:])
            self.assertEqual(bank_total - led_total, Decimal('1.00'))
            con = sqlite3.connect(made['TMP_DB'])
            try:
                self.assertEqual(con.execute('SELECT COUNT(*) FROM fixture_note').fetchone()[0], 1)
            finally:
                con.close()
            con = sqlite3.connect(made['PLAYBOOK_DB'])
            try:
                self.assertEqual(con.execute('SELECT COUNT(*) FROM playbooks').fetchone()[0], 5)
            finally:
                con.close()
            self.assertTrue(Path(made['WORK_DIR']).is_dir())

    @unittest.skipUnless(HAVE_FFMPEG, SKIP_MEDIA)
    def test_sample_clip_passes_verify_with_aac_audio(self):
        import verify_media
        with tempfile.TemporaryDirectory() as tmp:
            doc = sc.sample_media(Path(tmp) / 'media', approve_write=True)
            self.assertEqual(doc['outcome'], 'ok', doc)
            self.assertTrue(doc['verify']['passed'], doc['verify'])
            self.assertEqual(doc['verify']['frames'], 180)
            self.assertAlmostEqual(doc['verify']['duration'], 6.0, delta=0.1)
            clip = doc['files']['SAMPLE_VIDEO']
            probe = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'stream=codec_type,codec_name',
                                    '-of', 'json', clip], capture_output=True, timeout=120, check=True)
            streams = json.loads(probe.stdout.decode('utf-8'))['streams']
            audio = [s for s in streams if s['codec_type'] == 'audio']
            self.assertEqual(audio[0]['codec_name'], 'aac')
            self.assertTrue(verify_media.verify_video(clip, expected_audio=True)['passed'])

    @unittest.skipUnless(HAVE_FFMPEG, SKIP_MEDIA)
    def test_sample_wav_and_png_exist(self):
        with tempfile.TemporaryDirectory() as tmp:
            doc = sc.sample_media(Path(tmp) / 'media', approve_write=True)
            self.assertTrue(Path(doc['files']['SAMPLE_WAV']).is_file())
            self.assertTrue(Path(doc['files']['SAMPLE_PNG']).is_file())

    def test_playbook_fixture_is_searchable(self):
        import playbooks_v28
        with tempfile.TemporaryDirectory() as tmp:
            made = rose_fixtures.make(Path(tmp) / 'pb')
            found = playbooks_v28.search(db=made['PLAYBOOK_DB'], query='bank', limit=5)
            self.assertIsNotNone(found)
            self.assertIn('fixture.bank-reconcile', json.dumps(found, ensure_ascii=False))


if __name__ == '__main__':
    unittest.main()
