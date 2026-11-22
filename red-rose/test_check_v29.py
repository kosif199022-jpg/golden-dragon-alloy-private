"""Tests for rose_check (W09): the delivery gate. Media is generated with ffmpeg lavfi in a temp folder."""
import argparse
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

import rose_check
import rose_io as rio


def _ffmpeg(*args):
    subprocess.run(['ffmpeg', '-v', 'error', '-y', *args], check=True, timeout=300)


def _rules(result):
    return [f['rule'] for f in result['failures']]


def _details(result, rule):
    return [f['detail'] for f in result['failures'] if f['rule'] == rule]


def _run_cli(argv):
    """Run the registered `check` handler in-process; returns (exit_code, parsed JSON or text)."""
    parser = argparse.ArgumentParser(prog='rose')
    sub = parser.add_subparsers(dest='cmd')
    rose_check.register(sub)
    args = parser.parse_args(['check'] + argv)
    buf = io.BytesIO()
    wrapper = io.TextIOWrapper(buf, encoding='utf-8', write_through=True)
    old = sys.stdout
    sys.stdout = wrapper
    try:
        code = args.ext_func(args)
    finally:
        sys.stdout = old
    wrapper.flush()
    data = buf.getvalue().decode('utf-8')
    wrapper.detach()
    return code, data


class CheckTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix='rose_check_v29_')
        d = Path(cls.tmp)
        cls.good = d / 'good.mp4'
        cls.mp3 = d / 'mp3.mp4'
        cls.black = d / 'black.mp4'
        cls.odd = d / 'odd.mp4'
        cls.silent = d / 'silent.mp4'
        src = ['-f', 'lavfi', '-i', 'testsrc=size=640x360:rate=30', '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=48000']
        _ffmpeg(*src, '-t', '2', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac', str(cls.good))
        _ffmpeg(*src, '-t', '2', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'libmp3lame', str(cls.mp3))
        _ffmpeg('-f', 'lavfi', '-i', 'color=black:size=640x360:rate=30', '-t', '1',
                '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(cls.black))
        _ffmpeg('-f', 'lavfi', '-i', 'testsrc=size=641x360:rate=30', '-t', '1',
                '-c:v', 'libx264', '-pix_fmt', 'yuv444p', str(cls.odd))
        _ffmpeg('-f', 'lavfi', '-i', 'testsrc=size=640x360:rate=30', '-t', '2',
                '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(cls.silent))
        cls.ok_env = d / 'ok.json'
        cls.ok_env.write_text(json.dumps({'ok': True, 'outcome': 'ok', 'id': 'title-clip-mp4',
                                          'result': {'status': 'ok'}}), encoding='utf-8')

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def env_file(self, name, obj):
        p = Path(self.tmp) / name
        p.write_text(json.dumps(obj, ensure_ascii=False), encoding='utf-8')
        return str(p)

    def ok_evidence(self):
        return str(self.ok_env)

    # R1 / R4 / R5 -----------------------------------------------------------

    def test_r1_empty_draft_fails(self):
        r = rose_check.check('عايز فيديو', '   \n  ', [], [])
        self.assertFalse(r['passed'])
        self.assertIn('R1', _rules(r))

    def test_r4_done_claim_without_evidence_fails(self):
        r = rose_check.check('عايز فيديو', 'خلص الفيديو وجاهز ✅', [], [])
        self.assertIn('R4', _rules(r))

    def test_r4_done_english_without_evidence_fails(self):
        r = rose_check.check('make a clip', 'done. it will take 5 more minutes', [], [])
        self.assertIn('R4', _rules(r))

    def test_r4_negated_claim_is_not_a_claim(self):
        r = rose_check.check('عايز فيديو', 'لسه مش جاهز، هبدأ دلوقتي', [], [])
        self.assertNotIn('R4', _rules(r))

    def test_r5_example_only_with_claim_fails(self):
        ev = self.env_file('example.json', {'ok': False, 'outcome': 'example_only',
                                            'id': 'text.motion.kinetic_text', 'example_data': True})
        r = rose_check.check('عايز فيديو', 'خلص الفيديو', [ev], [])
        self.assertIn('R5', _rules(r))
        self.assertEqual(r['evidence'][0]['outcome'], 'example_only')

    def test_r5_arabic_unshaped_warning_fails_with_claim(self):
        ev = self.env_file('shape.json', {'ok': True, 'outcome': 'ok', 'id': 'studio.render',
                                          'result': {'warnings': ['arabic_unshaped: title frame']}})
        r = rose_check.check('عايز عنوان', 'خلص العنوان جاهز', [ev], [])
        self.assertIn('R5', _rules(r))
        self.assertEqual(r['evidence'][0]['outcome'], 'error')

    def test_r5_bad_evidence_must_be_mentioned_without_claim(self):
        ev = self.env_file('appr.json', {'ok': False, 'outcome': 'approval_required', 'id': 'audio.x'})
        silent = rose_check.check('عايز صوت', 'الشغل وقف عند الموافقة', [ev], [])
        self.assertNotIn('R5', _rules(silent))
        unmentioned = rose_check.check('عايز صوت', 'الشغل ماشي تمام', [ev], [])
        self.assertIn('R5', _rules(unmentioned))

    # R2 / R3 / R8 -----------------------------------------------------------

    def test_r2_path_on_line_five_fails(self):
        draft = '\n'.join(['فهمت الطلب', 'هعمل الفيديو', 'الخطوات دي', 'الناتج هيبقى كده', str(self.good)])
        r = rose_check.check('عايز فيديو', draft, [self.ok_evidence()], [str(self.good)])
        self.assertIn('R2', _rules(r))

    def test_r2_missing_path_in_draft_fails(self):
        draft = 'الناتج: ' + str(Path(self.tmp) / 'nothere.mp4')
        r = rose_check.check('عايز فيديو', draft, [self.ok_evidence()], [])
        self.assertIn('R2', _rules(r))

    def test_r3_long_reply_needs_done_section(self):
        draft = '\n'.join(f'سطر {i}' for i in range(10))
        r = rose_check.check('شرح', draft, [], [])
        self.assertIn('R3', _rules(r))
        r2 = rose_check.check('شرح', draft + '\nاللي اتعمل:\n- حاجة', [], [])
        self.assertNotIn('R3', _rules(r2))

    def test_r8_publish_word_without_approval_fails(self):
        r = rose_check.check('ارفع الفيديو', 'رفعت الفيديو على الموقع', [self.ok_evidence()], [])
        self.assertIn('R8', _rules(r))

    def test_r8_publish_word_with_approval_passes(self):
        r = rose_check.check('ارفع الفيديو', 'رفعته بعد موافقتك الصريحة', [self.ok_evidence()], [])
        self.assertNotIn('R8', _rules(r))

    # R6 media ---------------------------------------------------------------

    def test_r6_good_mp4_passes(self):
        r = rose_check.check('عايز فيديو', 'الفيديو اتعمل.', [self.ok_evidence()], [str(self.good)])
        self.assertEqual(_rules(r), [], r['failures'])
        m = r['media'][0]
        self.assertEqual((m['width'], m['height']), (640, 360))
        self.assertEqual(m['audio_codec'], 'aac')
        self.assertFalse(m['first_frame_black'])
        self.assertEqual(m['frames'], 60)

    def test_r6_mp3_audio_in_mp4_fails(self):
        r = rose_check.check('عايز فيديو', 'الفيديو اتعمل.', [self.ok_evidence()], [str(self.mp3)])
        self.assertIn('R6', _rules(r))
        self.assertTrue(any('AAC' in d for d in _details(r, 'R6')))

    def test_r6_silent_mp4_passes_audio_rule(self):
        r = rose_check.check('عايز فيديو', 'الفيديو اتعمل.', [self.ok_evidence()], [str(self.silent)])
        self.assertEqual(_rules(r), [], r['failures'])

    def test_r6_black_first_half_fails(self):
        r = rose_check.check('عايز فيديو', 'الفيديو اتعمل.', [self.ok_evidence()], [str(self.black)])
        self.assertTrue(any('سودا' in d for d in _details(r, 'R6')))
        self.assertIn('R6', _rules(r))

    def test_r6_odd_dimensions_fail(self):
        r = rose_check.check('عايز فيديو', 'الفيديو اتعمل.', [self.ok_evidence()], [str(self.odd)])
        self.assertTrue(any('زوجية' in d for d in _details(r, 'R6')))

    def test_r6_missing_file_fails(self):
        r = rose_check.check('عايز فيديو', 'الفيديو اتعمل.', [self.ok_evidence()],
                             [str(Path(self.tmp) / 'gone.mp4')])
        self.assertIn('R6', _rules(r))

    def test_r6_frames_rule_unit(self):
        entry = {'file': 'x.mp4', 'duration': 2.0, 'fps': 30.0, 'frames': 59, 'audio_codec': None,
                 'width': 640, 'height': 360, 'video_codec': 'h264', 'first_frame_black': False}
        failures = []
        rose_check._media_rules(entry, failures)
        self.assertTrue(any('round' in f['detail'] for f in failures))

    def test_r6_stated_numbers_must_match_file(self):
        draft = 'الفيديو 1920x1080 ومدته 2 ثانية.'
        r = rose_check.check('عايز فيديو', draft, [self.ok_evidence()], [str(self.good)])
        self.assertTrue(any('1920x1080' in d for d in _details(r, 'R6')))

    def test_r6_correct_stated_numbers_pass(self):
        draft = f'{self.good}\nالفيديو 640x360، مدته 2 ثانية، 60 فريم، 30 fps.'
        r = rose_check.check('عايز فيديو', draft, [self.ok_evidence()], [str(self.good)])
        self.assertEqual(_rules(r), [], r['failures'])

    # R7 captions ------------------------------------------------------------

    def test_r7_caption_not_in_words_fails(self):
        words = [{'start': 0, 'end': 0.4, 'text': 'الوردة'}, {'start': 0.4, 'end': 0.9, 'text': 'الحمراء'}]
        ev = self.env_file('cap.json', {'ok': True, 'outcome': 'ok', 'id': 'captions-from-words',
                                        'result': {'captions': [{'text': 'الوردة الحمراء'}, {'text': 'كلمة غلط'}]}})
        r = rose_check.check('كابشن', 'الكابشن اتعمل', [ev], [], words=words)
        self.assertIn('R7', _rules(r))
        self.assertTrue(any('كلمة غلط' in d for d in _details(r, 'R7')))

    def test_r7_caption_from_words_passes(self):
        words_file = self.env_file('words.json', [{'start': 0, 'end': 0.4, 'text': 'الوردة'},
                                                  {'start': 0.4, 'end': 0.9, 'text': 'الحمراء'}])
        ev = self.env_file('cap2.json', {'ok': True, 'outcome': 'ok', 'id': 'captions-from-words',
                                         'result': {'captions': [{'text': 'الوردة الحمراء'}]}})
        r = rose_check.check('كابشن', 'الكابشن اتعمل', [ev], [], words=words_file)
        self.assertNotIn('R7', _rules(r), r['failures'])

    # R9 advisory, fixed fields ----------------------------------------------

    def test_r9_request_item_missing_is_advisory_only(self):
        r = rose_check.check('صورة طائرة', 'اتعمل الملف', [self.ok_evidence()], [])
        self.assertTrue(any('طائرة' in a or 'طائره' in a for a in r['advisories']), r['advisories'])
        self.assertNotIn('R9', _rules(r))

    def test_fixed_critic_questions_and_note(self):
        r = rose_check.check('x', 'y', [], [])
        self.assertEqual(len(r['critic_questions']), 3)
        self.assertEqual(r['note_ar'], 'الفحص ده للشكل ووجود الدليل بس، مش للحقيقة')

    # Full good reply, CLI, exit codes, encodings, size, read-only ------------

    def test_good_reply_passes_via_cli_exit_zero(self):
        draft = (f'{self.good}\n'
                 'الفيديو اتعمل: 640x360، مدته 2 ثانية، 60 فريم.\n'
                 'اتقاس بـ ffprobe والصوت AAC.\n'
                 'اللي اتعمل:\n- الملف اتقرا\n')
        ev = self.ok_evidence()
        code, out = _run_cli(['--request', 'اعمل فيديو', '--draft', self._write('good_reply.txt', draft),
                              '--evidence', ev, '--files', str(self.good)])
        self.assertEqual(code, 0, out)
        doc = json.loads(out)
        self.assertTrue(doc['passed'])
        self.assertEqual(doc['outcome'], 'ok')
        self.assertEqual(doc['note_ar'], 'الفحص ده للشكل ووجود الدليل بس، مش للحقيقة')

    def test_cli_fail_exit_one(self):
        code, out = _run_cli(['--request', 'x', '--draft', self._write('empty.txt', '')])
        self.assertEqual(code, rio.EXIT_ERROR)
        self.assertFalse(json.loads(out)['passed'])

    def test_cli_missing_draft_is_usage_error(self):
        parser = argparse.ArgumentParser(prog='rose')
        sub = parser.add_subparsers(dest='cmd')
        rose_check.register(sub)
        old = sys.stderr
        sys.stderr = io.StringIO()
        try:
            with self.assertRaises(SystemExit) as ctx:
                parser.parse_args(['check', '--request', 'x'])
        finally:
            sys.stderr = old
        self.assertEqual(ctx.exception.code, rio.EXIT_USAGE)

    def test_utf16_bom_draft_is_read(self):
        path = Path(self.tmp) / 'utf16.txt'
        path.write_bytes('خلص الفيديو\n'.encode('utf-16'))  # Python writes a BOM for utf-16
        code, out = _run_cli(['--request', 'x', '--draft', str(path), '--evidence', self.ok_evidence()])
        self.assertEqual(code, 0, out)
        doc = json.loads(out)
        self.assertEqual(doc['failures'], [])  # decoded Arabic claim, ok evidence present, so no R4

    def test_large_draft_is_fast_and_sampled(self):
        big = Path(self.tmp) / 'big.txt'
        big.write_text(('سطر تجريبي للفحص 0123456789\n' * 80000), encoding='utf-8')
        size = big.stat().st_size
        self.assertGreater(size, 2_000_000)
        start = time.time()
        code, out = _run_cli(['--request', 'x', '--draft', str(big), '--evidence', self.ok_evidence()])
        elapsed = time.time() - start
        self.assertLess(elapsed, 5.0)
        doc = json.loads(out)
        self.assertTrue(any('أول' in a for a in doc['advisories']), doc['advisories'])

    def test_check_is_read_only_and_never_opens_db(self):
        work = Path(self.tmp) / 'readonly_work'
        work.mkdir()
        db = Path(self.tmp) / 'never_created.sqlite3'
        before = sorted(p.name for p in work.iterdir())
        old = os.environ.get('RED_ROSE_DB')
        os.environ['RED_ROSE_DB'] = str(db)
        try:
            rose_check.check('عايز فيديو', 'الفيديو اتعمل.', [self.ok_evidence()], [str(self.good)])
            _run_cli(['--request', 'x', '--draft', self._write('ro.txt', 'خلص'),
                      '--evidence', self.ok_evidence(), '--files', str(self.good)])
        finally:
            if old is None:
                os.environ.pop('RED_ROSE_DB', None)
            else:
                os.environ['RED_ROSE_DB'] = old
        self.assertFalse(db.exists())
        self.assertEqual(sorted(p.name for p in work.iterdir()), before)

    def test_unreadable_evidence_is_not_ok(self):
        bad = Path(self.tmp) / 'broken.json'
        bad.write_text('{not json', encoding='utf-8')
        r = rose_check.check('x', 'خلص', [str(bad)], [])
        self.assertEqual(r['evidence'][0]['outcome'], 'unreadable')
        self.assertIn('R4', _rules(r))

    def _write(self, name, text):
        p = Path(self.tmp) / name
        p.write_text(text, encoding='utf-8')
        return str(p)


if __name__ == '__main__':
    unittest.main()
