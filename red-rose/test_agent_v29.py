"""Tests for rose_agent (W07): understand, route with abstention, brief decisions, budgets, CLI.

Run: python -X utf8 -W error::ResourceWarning -m unittest test_agent_v29 -v
"""
from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import rose_agent as A  # noqa: E402

FIXTURES = json.loads((HERE / 'agent' / 'understand_tests.json').read_text(encoding='utf-8'))
ROUTES = json.loads((HERE / 'agent' / 'route_examples.json').read_text(encoding='utf-8'))
ROSE_PY = str(HERE / 'rose.py')

EVAL_KINETIC = 'hulg uk,hk ljpv; ggvdg. fhsl hg,v]m hgplvhx'
AUDIT_TITLE = 'اعمل عنوان متحرك للريلز باسم الوردة الحمراء'
AUDIT_SHOTS = 'شوف الفديو ده وقولي انهي لقطات احسن وقصهالي ريل ٣٠ ثانيه'
AUDIT_BANK = 'عايز اطابق كشف حساب البنك مع الدفتر وطلعلي الفروقات'

FORTY_REQUESTS = [e['text'] for e in ROUTES['examples']] + [
    EVAL_KINETIC, 'اعمل مونتاج', 'ازيك عامل ايه', 'شكرا', 'كمل', 'الطقس النهارده حر ولا لأ',
    'ظبطلي صوت الفديو ده وبعدين ارفعه على يوتيوب', 'حط كابشن على الريل ده بكلامي بالظبط من غير ما تغير ولا كلمه',
    'الكلام طالع مقطع ومش متوصل صلحه', AUDIT_SHOTS, AUDIT_BANK, AUDIT_TITLE, 'فين وصلت',
    'https://example.com/page', 'git status', 'npm install', 'اكتب قصيدة عن البحر',
]


def _cli(*args):
    """Run rose.py with the current interpreter; return (exit code, stdout text)."""
    proc = subprocess.run([sys.executable, '-X', 'utf8', ROSE_PY, *args], capture_output=True,
                          timeout=120, env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
    return proc.returncode, proc.stdout.decode('utf-8', 'replace')


class UnderstandTests(unittest.TestCase):

    def test_fixture_cases(self):
        failures = []
        for case in FIXTURES['cases']:
            out = A.understand(case['input'])
            if 'text' in case and out['text'] != case['text']:
                failures.append((case['id'], out['text'], case['text']))
            if case.get('keep') and out['text'] != case['input']:
                failures.append((case['id'], 'kept', out['text']))
            if 'kind' in case and out['kind'] != case['kind']:
                failures.append((case['id'], 'kind', out['kind'], case['kind']))
            if 'attachments' in case and out['attachments'] != case['attachments']:
                failures.append((case['id'], 'attachments', out['attachments']))
        self.assertEqual(failures, [], f'{len(FIXTURES["cases"])} cases')

    def test_at_least_fifteen_english_commands_stay_byte_identical(self):
        keep = [c for c in FIXTURES['cases'] if c.get('keep')]
        self.assertGreaterEqual(len(keep), 15)
        for case in keep:
            self.assertEqual(A.understand(case['input'])['text'], case['input'], case['id'])

    def test_eval_kinetic_title_decoded_and_reported(self):
        out = A.understand(EVAL_KINETIC)
        self.assertTrue(out['changed'])
        self.assertEqual(out['text'], 'اعمل عنوان متحرك للريلز باسم الوردة الحمراء')
        self.assertTrue(all(f['why'] == 'layout' for f in out['fixes']))

    def test_prefixed_dictation_slip_fixed_in_stem(self):
        self.assertEqual(A.understand('للفديو')['text'], 'للفيديو')
        fixes = A.understand('للفديو')['fixes']
        self.assertEqual(fixes[0]['why'], 'dictation')

    def test_lhad_and_bank_decode(self):
        self.assertEqual(A.understand('lhad')['text'], 'ماشي')
        self.assertEqual(A.understand('hgfk;')['text'], 'البنك')

    def test_command_word_stops_decoding(self):
        self.assertEqual(A.understand('git commit -m fix hgfk;')['text'], 'git commit -m fix hgfk;')

    def test_wrapper_removed_and_attachment_listed(self):
        out = A.understand('اعمل عنوان [مرفق: a.mp4, b.json]')
        self.assertEqual(out['attachments'], ['a.mp4', 'b.json'])
        self.assertIn('wrapper', {f['why'] for f in out['fixes']})

    def test_fix_reasons_are_from_the_allowed_set(self):
        for case in FIXTURES['cases']:
            for fix in A.understand(case['input'])['fixes']:
                self.assertIn(fix['why'], ('layout', 'dictation', 'wrapper'))

    def test_kinds(self):
        self.assertEqual(A.understand('ازيك عامل ايه')['kind'], 'greet')
        self.assertEqual(A.understand('شكرا')['kind'], 'thanks')
        self.assertEqual(A.understand('كمل')['kind'], 'continue')
        self.assertEqual(A.understand('فين وصلت')['kind'], 'status')
        self.assertEqual(A.understand('https://example.com')['kind'], 'link')
        self.assertEqual(A.understand('اعمل مونتاج')['kind'], 'task')


class RouteTests(unittest.TestCase):

    def test_route_accuracy_leave_one_out(self):
        top1 = top3 = abstain = total = none_total = 0
        for ex in ROUTES['examples']:
            if not ex.get('measure', True):
                continue
            res = A._route(ex['text'], exclude=ex['text'])
            if ex['expect'] == 'none':
                none_total += 1
                abstain += res['type'] == 'none'
                continue
            total += 1
            kind, ident = ex['expect'].split(':', 1)
            if res['type'] != 'none' and (res['type'], res['id']) == (kind, ident):
                top1 += 1
            if any((c['type'], c['id']) == (kind, ident) for c in res['candidates']):
                top3 += 1
        print(f'\nroute: top1 {top1}/{total}, top3 {top3}/{total}, '
              f'correct abstain {abstain}/{none_total}')
        self.assertGreaterEqual(top1, int(total * 0.8))
        self.assertGreaterEqual(top3, int(total * 0.95))
        self.assertEqual(abstain, none_total)

    def test_three_audit_jobs_route_first(self):
        self.assertEqual(A.route(AUDIT_TITLE)['id'], 'title-frame-ar')
        self.assertEqual(A.route(AUDIT_SHOTS)['id'], 'shot-report-recut')
        self.assertEqual(A.route(AUDIT_BANK)['id'], 'bank-reconcile')

    def test_abstention_on_unrelated_requests(self):
        for text in ['ازيك عامل ايه', 'شكرا', 'كمل', 'الطقس النهارده حر ولا لأ', 'اكتب قصيدة عن البحر']:
            self.assertEqual(A.route(text)['type'], 'none', text)

    def test_route_shape(self):
        res = A.route(AUDIT_TITLE)
        self.assertEqual(set(res), {'type', 'id', 'matched', 'alternative', 'candidates', 'confidence'})
        self.assertIn(res['confidence'], ('unmeasured', 'measured') + ('verified', 'high', 'mid', 'low'))


class BriefTests(unittest.TestCase):

    def test_montage_asks_exactly_one_question(self):
        b = A.brief('اعمل مونتاج')
        self.assertEqual(b['decision'], 'ask')
        self.assertEqual(len(b['must_ask']), 1)
        self.assertEqual(b['must_ask'][0]['param'], 'source')
        self.assertIsNone(b['steps'][0]['command'] if b['steps'] else None)

    def test_delegation_turns_question_into_assumptions(self):
        b = A.brief('نفذ انت اللي تشوفه', prev='اعمل مونتاج', files=['clip.mp4'])
        self.assertEqual(b['decision'], 'go_with_assumptions')
        self.assertEqual(b['must_ask'], [])
        self.assertTrue(b['slots']['assumed'])
        self.assertEqual(b['route']['id'], 'shot-report-recut')

    def test_greeting_short_and_no_route(self):
        b = A.brief('ازيك يا ورده عامل ايه النهارده')
        self.assertEqual(b['kind'], 'greet')
        self.assertEqual(b['route']['type'], 'none')
        self.assertLess(b['chars'], 200)

    def test_bare_continue_without_prev_asks_for_previous(self):
        b = A.brief('كمل')
        self.assertEqual(b['route']['type'], 'none')
        self.assertLess(b['chars'], 200)
        self.assertIn('رسالتك', b['note_ar'])

    def test_complaint_keeps_route_with_prev_and_drops_without(self):
        with_prev = A.brief('الكلام طالع مقطع ومش متوصل صلحه', prev=AUDIT_TITLE)
        self.assertEqual(with_prev['kind'], 'complaint')
        self.assertEqual(with_prev['route']['id'], 'title-frame-ar')
        self.assertTrue(with_prev['used_context'])
        without = A.brief('الكلام طالع مقطع ومش متوصل صلحه')
        self.assertEqual(without['route']['type'], 'none')
        self.assertLess(without['chars'], 200)

    def test_upload_lists_approvals_first_and_no_upload_command(self):
        b = A.brief('ظبطلي صوت الفديو ده وبعدين ارفعه على يوتيوب', files=['talk.mp4'])
        self.assertIn('publish', b['approvals'])
        self.assertIn('write', b['approvals'])
        self.assertEqual(b['decision'], 'confirm')
        text = A.render_brief(b)
        self.assertTrue(text.splitlines()[0].startswith('الموافقات:'))
        for step in b['steps']:
            self.assertNotIn('upload', step['command'] or '')
            self.assertNotIn('youtube', (step['command'] or '').lower())

    def test_write_steps_run_without_flag_and_rerun_with_it(self):
        b = A.brief(AUDIT_SHOTS, files=['clip.mp4'])
        writes = [s for s in b['steps'] if s['effect'] == 'write']
        self.assertTrue(writes)
        for step in b['steps']:
            self.assertNotIn('--approve-write', step['command'] or '')
        for step in writes:
            self.assertTrue(step['rerun_with_approval'].endswith('--approve-write'))

    def test_eval_shot_report_is_go_with_duration_from_text(self):
        b = A.brief(AUDIT_SHOTS, files=['clip.mp4'])
        self.assertEqual(b['route']['id'], 'shot-report-recut')
        known = {k['param']: k['value'] for k in b['slots']['known']}
        self.assertEqual(known.get('max_duration'), 30)
        self.assertEqual(b['decision'], 'go')

    def test_kinetic_title_routes_and_declares_defaults(self):
        b = A.brief(EVAL_KINETIC)
        self.assertEqual(b['route']['id'], 'title-frame-ar')
        self.assertEqual(b['understood']['text'], 'اعمل عنوان متحرك للريلز باسم الوردة الحمراء')
        self.assertTrue(b['slots']['assumed'])
        self.assertEqual(b['must_ask'], [])

    def test_budgets_on_fixture_requests(self):
        failures = []
        for text in FORTY_REQUESTS:
            b = A.brief(text)
            budget = A.BUDGET[b['depth']]
            if b['chars'] > budget:
                failures.append((text[:40], b['depth'], b['chars'], budget))
        self.assertEqual(failures, [])
        self.assertGreaterEqual(len(FORTY_REQUESTS), 40)

    def test_brief_is_fast_per_call(self):
        A.brief(AUDIT_TITLE)  # warm the index once per process
        start = time.perf_counter()
        for text in [AUDIT_TITLE, AUDIT_SHOTS, AUDIT_BANK, 'اعمل مونتاج']:
            A.brief(text)
        per_call = (time.perf_counter() - start) / 4
        print(f'\nbrief warm: {per_call * 1000:.0f} ms per call')
        self.assertLess(per_call, 1.0)

    def test_no_database_created(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / 'never' / 'memory.sqlite3'
            old = os.environ.get('RED_ROSE_DB')
            os.environ['RED_ROSE_DB'] = str(missing)
            try:
                A.brief(AUDIT_TITLE)
                A.understand(EVAL_KINETIC)
            finally:
                if old is None:
                    os.environ.pop('RED_ROSE_DB', None)
                else:
                    os.environ['RED_ROSE_DB'] = old
            self.assertFalse(missing.exists())


class StepCommandTests(unittest.TestCase):

    @unittest.skipUnless(shutil.which('ffmpeg'), 'ffmpeg not on PATH')
    def test_shot_report_step_one_runs_and_exits_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            clip = Path(tmp) / 'clip.mp4'
            made = subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'lavfi', '-i',
                                   'testsrc=size=540x960:rate=30:duration=6', '-f', 'lavfi', '-i',
                                   'sine=frequency=440:duration=6', '-c:v', 'libx264', '-c:a', 'aac',
                                   '-shortest', str(clip)], capture_output=True, timeout=120)
            self.assertEqual(made.returncode, 0)
            b = A.brief(AUDIT_SHOTS, files=[clip.as_posix()])
            step = b['steps'][0]
            work = Path(tmp).as_posix()
            params = Path(tmp) / 'step1.params.json'
            params.write_text(step['params_file_content'].replace('<work>', work), encoding='utf-8')
            cmd = step['command'].replace('<work>', work)
            argv = shlex.split(cmd, posix=True)
            argv[0] = sys.executable
            proc = subprocess.run(argv, capture_output=True, cwd=tmp, timeout=300)
            self.assertIn(proc.returncode, (0, 3), proc.stdout[-400:])
            self.assertNotEqual(proc.returncode, 1, proc.stdout[-400:])


class CliTests(unittest.TestCase):

    def test_understand_cli_json(self):
        code, out = _cli('understand', EVAL_KINETIC)
        self.assertEqual(code, 0)
        doc = json.loads(out)
        self.assertEqual(doc['text'], 'اعمل عنوان متحرك للريلز باسم الوردة الحمراء')
        self.assertTrue(doc['changed'])

    def test_brief_cli_json_and_text(self):
        code, out = _cli('brief', AUDIT_BANK, '--json')
        self.assertEqual(code, 0)
        doc = json.loads(out)
        self.assertEqual(doc['route']['id'], 'bank-reconcile')
        code, text = _cli('brief', 'اعمل مونتاج', '--text')
        self.assertEqual(code, 0)
        self.assertTrue(text.splitlines()[0].startswith('الموافقات:'))

    def test_register_adds_both_commands(self):
        import argparse
        import rose_ext
        parser = argparse.ArgumentParser()
        subs = parser.add_subparsers(dest='cmd')
        result = rose_ext.load(subs, modules=['rose_agent'])
        self.assertIn('rose_agent', result['loaded'], result)
        self.assertIn('understand', subs.choices)
        self.assertIn('brief', subs.choices)


if __name__ == '__main__':
    unittest.main()
