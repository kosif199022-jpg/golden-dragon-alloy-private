"""Red Rose V29 (W08): recipes, gates, approval rule and the one-command runner.

Media tests need ffmpeg/ffprobe and skip with a printed reason when they are missing.
Nothing here touches the owner's ~/.red-rose folder or the network.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import rose_recipes as RR  # noqa: E402
import rose_fixtures as FX  # noqa: E402

HAVE_FFMPEG = bool(shutil.which('ffmpeg') and shutil.which('ffprobe'))
ARABIC_SAMPLE = 'الوردة الحمراء'
TASHKEEL_WORDS = [
    {'word': 'الوردة', 'start': 0.0, 'end': 0.6},
    {'word': 'الحَمْرَاءُ', 'start': 0.6, 'end': 1.4},
    {'word': 'تَفتَحُ', 'start': 1.4, 'end': 1.9},
    {'word': 'الآنَ', 'start': 1.9, 'end': 2.4},
]


def _listing(folder):
    if not folder.is_dir():
        return []
    return sorted((str(p.relative_to(folder)), p.stat().st_size) for p in folder.rglob('*'))


def _cli(*argv):
    """Run the recipe commands the way rose.py will wire them (rose_ext.register)."""
    code = (
        'import sys, argparse; sys.path.insert(0, sys.argv[1]); import rose_recipes as RR; '
        'p = argparse.ArgumentParser(prog="rose.py"); s = p.add_subparsers(dest="command"); '
        'RR.register(s); a = p.parse_args(sys.argv[2:]); raise SystemExit(a.ext_func(a))'
    )
    done = subprocess.run([sys.executable, '-X', 'utf8', '-B', '-c', code, str(ROOT), *argv],
                          capture_output=True, timeout=600)
    return done.returncode, done.stdout.decode('utf-8'), done.stderr.decode('utf-8')


class RecipeFilesTest(unittest.TestCase):
    def test_validate_clean(self):
        self.assertEqual(RR.validate(), [])

    def test_fixed_ids_and_files(self):
        ids = sorted(r['id'] for r in RR.load_all())
        self.assertEqual(ids, sorted(RR.EXPECTED_IDS))
        self.assertEqual(len(ids), 8)

    def test_examples_arabic_and_english(self):
        for rec in RR.load_all():
            arabic = [w for w in rec['when'] if RR._ARABIC.search(w)]
            english = [w for w in rec['when'] if RR._LATIN.search(w) and not RR._ARABIC.search(w)]
            self.assertGreaterEqual(len(arabic), 2, rec['id'])
            self.assertGreaterEqual(len(english), 1, rec['id'])

    def test_every_write_step_needs_approval_and_is_listed(self):
        for rec in RR.load_all():
            listed = {a['step'] for a in rec.get('approvals', [])}
            for step in rec['steps']:
                if RR._is_write(step):
                    self.assertTrue(step.get('approval'), (rec['id'], step['n']))
                    self.assertIn(step['n'], listed, (rec['id'], step['n']))

    def test_no_ffmpeg_filter_arguments_unless_requested(self):
        pattern = re.compile(r'(?<![a-z_])(fade|overlay|eq|bloom|hue|boxblur|vignette|colorbalance|drawtext)\s*=|overlay', re.I)
        for rec in RR.load_all():
            for step in rec['steps']:
                text = json.dumps(step.get('args', {}), ensure_ascii=False)
                self.assertIsNone(pattern.search(text), (rec['id'], step['n'], text[:200]))
                self.assertNotIn('"vf"', text, rec['id'])
                self.assertNotIn('"filter', text, rec['id'])


class GateTest(unittest.TestCase):
    def setUp(self):
        if not HAVE_FFMPEG:
            self.skipTest('ffmpeg/ffprobe missing')
        self.tmp = tempfile.TemporaryDirectory(prefix='rr-gate-')
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _ff(self, *args):
        subprocess.run(['ffmpeg', '-v', 'error', '-nostdin', '-y', *args], check=True,
                       capture_output=True, timeout=180)

    def test_mp3_audio_fails_final_gate(self):
        out = self.dir / 'mp3.mp4'
        try:
            self._ff('-f', 'lavfi', '-i', 'color=c=0x1e5fd6:s=320x568:r=30:d=1',
                     '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=44100:duration=1',
                     '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'libmp3lame', '-shortest', str(out))
        except (subprocess.CalledProcessError, FileNotFoundError):
            self.skipTest('libmp3lame encoder not available here')
        ok, reason = RR.check_video(str(out), audio='aac_or_none')
        self.assertFalse(ok)
        self.assertIn('aac', reason)

    def test_black_first_frame_fails_final_gate(self):
        out = self.dir / 'black.mp4'
        self._ff('-f', 'lavfi', '-i', 'color=c=black:s=320x568:r=30:d=1',
                 '-f', 'lavfi', '-i', 'color=c=white:s=320x568:r=30:d=1',
                 '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=48000:duration=2',
                 '-filter_complex', '[0:v][1:v]concat=n=2:v=1:a=0[v]', '-map', '[v]', '-map', '2:a',
                 '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-shortest', str(out))
        ok, reason = RR.check_video(str(out), audio='aac_or_none')
        self.assertFalse(ok)
        self.assertIn('black', reason)

    def test_good_clip_passes_final_gate(self):
        fixtures = self.dir / 'fx'
        made = FX.make(str(fixtures))
        ok, reason = RR.check_video(made['SAMPLE_VIDEO'], audio='aac')
        self.assertTrue(ok, reason)


class RunnerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='rr-run-')
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_bank_reconcile_on_fixtures_reports_one_pound_difference_and_writes_nothing(self):
        made = FX.make(str(self.dir / 'fx'))
        work = self.dir / 'work'
        before = _listing(work)
        out = RR.run('bank-reconcile', {'ledger_csv': made['LEDGER_CSV'], 'bank_csv': made['BANK_CSV']},
                     work=str(work), approve_write=False)
        self.assertEqual(out['outcome'], 'ok', out.get('error'))
        self.assertEqual(out['exit'], 0)
        self.assertEqual(_listing(work), before)
        result = json.dumps(out['steps'][0]['result'], ensure_ascii=False)
        self.assertIn('"amount_difference": "1.00"', result)
        self.assertFalse(out['steps'][0]['saved'])

    def test_unapproved_write_exits_3_and_lists_would_write(self):
        if not HAVE_FFMPEG:
            self.skipTest('ffmpeg/ffprobe missing')
        made = FX.make(str(self.dir / 'fx'))
        work = self.dir / 'work'
        work.mkdir()
        (work / 'note.txt').write_text('keep me', encoding='utf-8')
        before = _listing(work)
        out = RR.run('shot-report-recut', {'source': made['SAMPLE_VIDEO']}, work=str(work), approve_write=False)
        self.assertEqual(out['outcome'], 'approval_required')
        self.assertEqual(out['exit'], 3)
        self.assertTrue(any(p.endswith('recut.mp4') for p in out['would_write']))
        self.assertEqual(_listing(work), before)
        self.assertTrue(out['steps'][0]['result'], 'the read step (shot report) still ran')

    def test_captions_keep_tashkeel_byte_equal(self):
        if not HAVE_FFMPEG:
            self.skipTest('ffmpeg/ffprobe missing')
        words = self.dir / 'words.json'
        words.write_text(json.dumps({'words': TASHKEEL_WORDS}, ensure_ascii=False), encoding='utf-8')
        out = RR.run('captions-from-words', {'words': str(words)}, work=str(self.dir / 'cap'),
                     approve_write=True)
        self.assertEqual(out['outcome'], 'ok', out.get('error'))
        gate = out['steps'][0]['gates'][0]
        self.assertEqual(gate['check'], 'equals_input')
        self.assertEqual(gate['status'], 'pass')
        svg = (self.dir / 'cap' / 'caption-frame.svg').read_text(encoding='utf-8')
        for item in TASHKEEL_WORDS:
            self.assertIn(item['word'], svg)

    def test_captions_without_words_exits_6_needs_input_and_invents_nothing(self):
        work = self.dir / 'cap'
        out = RR.run('captions-from-words', {}, work=str(work), approve_write=False)
        self.assertEqual(out['outcome'], 'needs_input')
        self.assertEqual(out['status'], 'needs_input')
        self.assertEqual(out['exit'], 6)
        self.assertEqual(out['missing'][0]['key'], 'words')
        self.assertIn('ملف الكلمات', out['question_ar'])
        self.assertIn('JSON', out['missing'][0]['allowed'])
        self.assertTrue(out['next'])
        self.assertFalse(out['would_write'])
        self.assertFalse(work.exists())
        text = json.dumps(out, ensure_ascii=False)
        self.assertNotIn('الوردة', text)

    def test_missing_input_comes_before_the_work_folder_check(self):
        out = RR.run('shot-report-recut', {}, work=None)
        self.assertEqual((out['outcome'], out['exit']), ('needs_input', 6))
        self.assertEqual(out['missing'][0]['key'], 'source')

    def test_status_always_equals_outcome_and_recipe_status_is_separate(self):
        for kwargs in ({'inputs': {}, 'work': 'x'}, {'inputs': {'ledger_csv': 'a.csv', 'bank_csv': 'b.csv'}, 'work': None}):
            out = RR.run('bank-reconcile', kwargs['inputs'], work=kwargs['work'])
            self.assertEqual(out['status'], out['outcome'])
            self.assertEqual(out['recipe_status'], 'ready')
        out = RR.run('captions-from-words', {}, work=str(self.dir / 'c2'))
        self.assertEqual(out['status'], 'needs_input')
        self.assertEqual(out['recipe_status'], 'ready')

    def test_missing_work_folder_is_an_error(self):
        out = RR.run('bank-reconcile', {'ledger_csv': 'x.csv', 'bank_csv': 'y.csv'}, work=None)
        self.assertEqual(out['outcome'], 'error')
        self.assertIn('--work', out['error'])

    def test_plan_marks_write_steps(self):
        steps = RR.plan('shot-report-recut', {'source': 'C:/clips/a.mp4'}, 'C:/work')
        self.assertEqual([s['effect'] for s in steps], ['read', 'write'])
        self.assertIn('--approve-write', steps[1]['command'])
        self.assertNotIn('--approve-write', steps[0]['command'])

    def test_cli_list_validate_and_run_without_work(self):
        code, out, _err = _cli('recipes')
        self.assertEqual(code, 0)
        rows = json.loads(out)['recipes']
        self.assertEqual(sorted(r['id'] for r in rows), sorted(RR.EXPECTED_IDS))
        code, out, _err = _cli('recipe', 'validate')
        self.assertEqual(code, 0, out)
        self.assertTrue(json.loads(out)['ok'])
        code, out, _err = _cli('recipe', 'run', 'bank-reconcile', 'ledger_csv=a.csv', 'bank_csv=b.csv')
        self.assertEqual(code, 1)
        self.assertIn('--work', json.loads(out)['error'])

    def test_cli_unknown_recipe_is_one_json_line(self):
        code, out, _err = _cli('recipe', 'show', 'no-such-recipe')
        self.assertEqual(code, 1)
        self.assertIn('unknown recipe', json.loads(out)['error'])


class SelftestTest(unittest.TestCase):
    """Every recipe runs on fixtures: dry run changes nothing, the approved run passes its gates."""

    def test_every_recipe_selftest(self):
        results = {}
        for rec in RR.load_all():
            res = RR.selftest(rec['id'])
            results[rec['id']] = res
            if res['skipped']:
                print(f"\nselftest {rec['id']} skipped: {res['skipped']}", file=sys.stderr)
                continue
            failed = [c for c in res['checks'] if not c.get('passed')]
            self.assertFalse(failed, (rec['id'], failed))
            if rec.get('status') == 'ready':
                self.assertTrue(res['passed'], rec['id'])
        self.assertEqual(sorted(results), sorted(RR.EXPECTED_IDS))


if __name__ == '__main__':
    unittest.main()
