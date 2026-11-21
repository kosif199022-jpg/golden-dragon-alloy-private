"""Tests for audio_v25 (V25 audio topics 16.01, 16.03, 16.04, 16.06-16.10).

Synthetic media only (python wave + FFmpeg lavfi) inside a TemporaryDirectory.
Run: python -X utf8 -W error::ResourceWarning -m unittest test_audio_v25 -v
"""
from __future__ import annotations

import array
import ast
import hashlib
import json
import math
import random
import shutil
import subprocess
import sys
import tempfile
import unittest
import wave
from pathlib import Path

import audio_v25 as A

ROOT = Path(__file__).resolve().parent
HAVE_FFMPEG = bool(shutil.which('ffmpeg') and shutil.which('ffprobe'))
R = 48000


def write_wav(path, samples, rate=R, channels=1):
    data = array.array('h', (max(-32768, min(32767, int(round(v * 32767)))) for v in samples))
    if sys.byteorder == 'big':
        data.byteswap()
    with wave.open(str(path), 'wb') as fh:
        fh.setnchannels(channels)
        fh.setsampwidth(2)
        fh.setframerate(rate)
        fh.writeframes(data.tobytes())


def ffmpeg(*args):
    subprocess.run(['ffmpeg', '-hide_banner', '-nostdin', '-v', 'error', '-y', *args],
                   capture_output=True, timeout=60, check=True)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def tone(seconds, amp=0.5, freq=440.0, rate=R):
    return [amp * math.sin(2 * math.pi * freq * i / rate) for i in range(int(seconds * rate))]


class InterfaceTests(unittest.TestCase):
    def test_topics_effects_and_dispatch(self):
        self.assertEqual(set(A.TOPICS), {'16.01', '16.03', '16.04', '16.06', '16.07',
                                         '16.08', '16.09', '16.10'})
        self.assertNotIn('16.05', A.TOPICS)
        self.assertTrue(set(A.TOPICS.values()) <= set(A.OPS))
        self.assertEqual(set(A.EFFECTS), set(A.OPS))
        self.assertTrue(set(A.EFFECTS.values()) <= {'read', 'write'})
        for op in ('denoise', 'extract_pcm', 'cut_crossfade', 'loudness_normalise'):
            self.assertEqual(A.EFFECTS[op], 'write')
        for op in ('loudness', 'word_alignment', 'av_sync', 'pause_trim', 'audio_rights'):
            self.assertEqual(A.EFFECTS[op], 'read')
        with self.assertRaises(ValueError):
            A.run('not_an_op', {})
        with self.assertRaises(ValueError):
            A.run('loudness', [])
        with self.assertRaises(ValueError):
            A.run('word_alignment', {'words': ['a'], 'timings': [], 'shell': 'rm -rf /'})

    def test_file_ops_require_source(self):
        for op in ('loudness', 'loudness_normalise', 'denoise', 'extract_pcm', 'cut_crossfade',
                   'av_sync', 'pause_trim', 'audio_rights'):
            with self.subTest(op=op), self.assertRaisesRegex(ValueError, '^source is required$'):
                A.run(op, {})
        with self.assertRaises(ValueError):
            A.run('word_alignment', {})

    def test_urls_and_network_paths_rejected(self):
        for bad in ('https://example.com/a.wav', 'http://x/a.mp3', 'file:///C:/a.wav',
                    '\\\\server\\share\\a.wav', 'ftp://h/a.wav'):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                A.run('loudness', {'source': bad})
        with self.assertRaises(ValueError):
            A.run('loudness', {'source': True})

    def test_source_code_rules(self):
        tree = ast.parse((ROOT / 'audio_v25.py').read_text(encoding='utf-8'))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported |= {a.name.split('.')[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split('.')[0])
            elif isinstance(node, ast.Call):
                fn = node.func
                name = (f'{getattr(fn.value, "id", "")}.{fn.attr}' if isinstance(fn, ast.Attribute)
                        else getattr(fn, 'id', ''))
                self.assertNotIn(name, ('os.system', 'os.popen', 'exec', 'eval', 'print',
                                        'subprocess.Popen', 'subprocess.call',
                                        'subprocess.check_output'))
                if name == 'subprocess.run':
                    kws = {k.arg for k in node.keywords}
                    self.assertTrue({'capture_output', 'timeout'} <= kws)
                    self.assertNotIn('shell', kws)
        self.assertFalse(imported & {'socket', 'urllib', 'http', 'requests', 'ctypes'})
        stdlib = set(sys.stdlib_module_names) | {'__future__'}
        self.assertTrue(imported <= stdlib | {'scene_edit_v16', 'audio_scene_v17', 'verify_media'},
                        imported - stdlib)


class WordAlignmentTests(unittest.TestCase):
    def test_hand_example_deviation_and_no_invention(self):
        words = ['Hello', 'brave', 'new', '[unclear]', 'world']
        timings = [{'word': 'hello,', 'start': 0.10, 'end': 0.40},
                   {'word': 'new', 'start': 0.60, 'end': 0.80},
                   {'word': 'mumble', 'start': 0.85, 'end': 0.95},
                   {'word': 'World!', 'start': 1.00, 'end': 1.50}]
        reference = [{'start': 0.00, 'end': 0.40}, {'start': 0.40, 'end': 0.60},
                     {'start': 0.70, 'end': 0.80}, None, {'start': 1.20, 'end': 1.40}]
        out = A.run('word_alignment', {'words': words, 'timings': timings, 'reference': reference})
        res = out['result']
        ws = res['words']
        self.assertEqual([w['word'] for w in ws], ['Hello', 'brave', 'new', '', 'world'])
        self.assertEqual((ws[0]['start'], ws[0]['end']), (0.10, 0.40))
        self.assertIsNone(ws[1]['start'])  # 'brave' not in the timing source -> stays empty
        self.assertEqual(ws[1]['status'], 'missing')
        self.assertEqual(ws[3]['status'], 'unclear')
        self.assertIsNone(ws[3]['start'])
        self.assertEqual(res['unclear'], [3])
        self.assertEqual(res['missing'], [{'index': 1, 'word': 'brave'}])
        self.assertEqual(res['timings_not_in_transcript'], [{'timing_index': 2, 'word': 'mumble'}])
        self.assertNotIn('mumble', [w['word'] for w in ws])
        dev = res['deviation']
        # start devs: 0.10, -0.10, -0.20 ; end devs: 0.0, 0.0, 0.10
        self.assertEqual(dev['start']['count'], 3)
        self.assertAlmostEqual(dev['start']['mean_signed'], (0.10 - 0.10 - 0.20) / 3, places=6)
        self.assertAlmostEqual(dev['start']['mean_abs'], 0.40 / 3, places=6)
        self.assertAlmostEqual(dev['start']['max_abs'], 0.20, places=6)
        self.assertAlmostEqual(dev['start']['median_abs'], 0.10, places=6)
        self.assertAlmostEqual(dev['start']['rms'], math.sqrt((0.01 + 0.01 + 0.04) / 3), places=6)
        self.assertAlmostEqual(dev['end']['max_abs'], 0.10, places=6)
        self.assertAlmostEqual(dev['within_tolerance_ratio'], 2 / 3, places=4)
        self.assertEqual(dev['words_without_reference_or_timing'], [1, 3])

    def test_arabic_normalisation_and_timings_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / 'aligner.json'
            f.write_text(json.dumps({'segments': [{'words': [
                {'word': 'السَّلامُ', 'start': 0.0, 'end': 0.5},
                {'word': 'عليكم', 'start': 0.5, 'end': 0.9}]}]}, ensure_ascii=False), encoding='utf-8')
            out = A.run('word_alignment', {'words': ['السلام', 'عليكم', None], 'timings_file': str(f)})
        ws = out['result']['words']
        self.assertEqual(ws[0]['word'], 'السلام')  # text comes from the transcript
        self.assertEqual(ws[1]['start'], 0.5)
        self.assertEqual(ws[2]['word'], '')
        self.assertIsNone(ws[2]['start'])

    def test_validation(self):
        for params in ({'words': 'abc', 'timings': []},
                       {'words': ['a'], 'timings': [{'word': 'a', 'start': 2, 'end': 1}]},
                       {'words': ['a'], 'timings': [{'word': 'a', 'start': True, 'end': 1}]},
                       {'words': ['a'], 'timings': [], 'reference': [None, None]},
                       {'words': ['a'], 'timings': [], 'timings_file': 'x.json'},
                       {'words': ['a'], 'timings_file': 'https://x/y.json'}):
            with self.subTest(params=params), self.assertRaises(ValueError):
                A.run('word_alignment', params)


@unittest.skipUnless(HAVE_FFMPEG, 'FFmpeg/FFprobe not installed')
class MediaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(tmp.cleanup)
        d = cls.dir = Path(tmp.name)
        f = cls.f = {}
        base = tone(3.0)
        f['tone'] = d / 'tone.wav'
        write_wav(f['tone'], base)
        f['quiet'] = d / 'quiet.wav'
        write_wav(f['quiet'], [v * 10 ** (-6 / 20) for v in base])
        rnd = random.Random(7)
        clean = [0.0] * int(0.5 * R) + tone(2.5)
        f['clean'] = d / 'clean.wav'
        write_wav(f['clean'], clean)
        f['noisy'] = d / 'noisy.wav'
        write_wav(f['noisy'], [c + rnd.gauss(0, 0.05) for c in clean])
        n = R
        f['a'] = d / 'seg_a.wav'
        write_wav(f['a'], [0.7 * math.cos(2 * math.pi * 440 * (i - (n - 1)) / R) for i in range(n)])
        f['b'] = d / 'seg_b.wav'
        write_wav(f['b'], [-0.7 * math.cos(2 * math.pi * 440 * i / R) for i in range(n)])
        # tone 0-1, silence 1-3, tone 3-4, silence 4-4.3, tone 4.3-5.3
        cls.audible = [(0.0, 1.0), (3.0, 4.0), (4.3, 5.3)]
        pause = tone(1) + [0.0] * (2 * R) + tone(1) + [0.0] * int(0.3 * R) + tone(1)
        f['pause'] = d / 'pause.wav'
        write_wav(f['pause'], pause)
        f['pause_mp4'] = d / 'pause.mp4'
        ffmpeg('-f', 'lavfi', '-i', 'color=c=gray:s=64x64:r=25:d=5.3', '-i', str(f['pause']),
               '-map', '0:v', '-map', '1:a', '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
               '-c:a', 'aac', '-shortest', str(f['pause_mp4']))
        stereo = 'aevalsrc=0.5*sin(2*PI*440*t)|0.5*sin(2*PI*660*t):s=48000:d=2'
        video = 'testsrc2=s=64x64:r=25:d=2'
        f['stereo_mp4'] = d / 'stereo.mp4'
        ffmpeg('-f', 'lavfi', '-i', video, '-f', 'lavfi', '-i', stereo, '-c:v', 'libx264',
               '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-shortest', str(f['stereo_mp4']))
        f['adelay_mp4'] = d / 'adelay.mp4'
        ffmpeg('-f', 'lavfi', '-i', video, '-f', 'lavfi', '-i', stereo, '-af', 'adelay=200|200',
               '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-t', '2',
               str(f['adelay_mp4']))
        f['offset_mp4'] = d / 'offset.mp4'
        ffmpeg('-f', 'lavfi', '-i', video, '-itsoffset', '0.2', '-f', 'lavfi', '-i', stereo,
               '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac', str(f['offset_mp4']))
        cls.hashes = {k: sha(p) for k, p in f.items()}

    @classmethod
    def tearDownClass(cls):
        for key, path in cls.f.items():
            assert sha(path) == cls.hashes[key], f'input {key} was modified'

    def assertInputsUnchanged(self):
        for key, path in self.f.items():
            self.assertEqual(sha(path), self.hashes[key], f'input {key} was modified')

    def out(self, name):
        return self.dir / 'out' / name

    def setUp(self):
        (self.dir / 'out').mkdir(exist_ok=True)

    # 16.01
    def test_loudness_quieter_copy_and_variation(self):
        loud = A.run('loudness', {'source': str(self.f['tone'])})['result']
        quiet = A.run('loudness', {'source': str(self.f['quiet']),
                                   'compare_to': str(self.f['tone'])})['result']
        self.assertAlmostEqual(loud['integrated_lufs'] - quiet['integrated_lufs'], 6.0, delta=0.5)
        self.assertAlmostEqual(quiet['comparison']['delta_integrated_lu'], 6.0, delta=0.5)
        self.assertAlmostEqual(loud['true_peak_dbtp'] - quiet['true_peak_dbtp'], 6.0, delta=0.5)
        self.assertIn('variation', loud)
        self.assertEqual(loud['variation']['segments_counted'], 3)
        self.assertLess(loud['variation']['range_db'], 0.2)
        self.assertAlmostEqual(loud['segments'][0]['rms_dbfs'], 20 * math.log10(0.5 / math.sqrt(2)),
                               delta=0.1)
        self.assertIn('other_variation', quiet['comparison'])
        self.assertInputsUnchanged()

    def test_loudness_normalise_gated_and_no_overwrite(self):
        target = self.out('norm.m4a')
        with self.assertRaises(PermissionError):
            A.run('loudness_normalise', {'source': str(self.f['quiet']), 'output': str(target)})
        self.assertFalse(target.exists())
        out = A.run('loudness_normalise', {'source': str(self.f['quiet']), 'output': str(target),
                                           'approve_write': True, 'target_lufs': -16.0})['result']
        self.assertTrue(target.is_file())
        self.assertEqual(out['codec'], 'aac')
        self.assertAlmostEqual(out['after']['integrated_lufs'], -16.0, delta=1.0)
        self.assertIn('variation', out['before'])
        self.assertIn('variation', out['after'])
        before = sha(target)
        with self.assertRaisesRegex(ValueError, 'already exists'):
            A.run('loudness_normalise', {'source': str(self.f['quiet']), 'output': str(target),
                                         'approve_write': True})
        self.assertEqual(sha(target), before)
        self.assertEqual([p.name for p in target.parent.iterdir() if p.name.startswith('.audio_v25_')], [])
        with self.assertRaises(ValueError):
            A.run('loudness_normalise', {'source': str(self.f['quiet']),
                                         'output': str(self.dir / 'missing_dir' / 'x.wav'),
                                         'approve_write': True})
        self.assertInputsUnchanged()

    # 16.03
    def test_denoise_improves_snr_and_needs_approval(self):
        target = self.out('denoised.wav')
        for approval in (False, 'yes', 1):
            with self.assertRaises(PermissionError):
                A.run('denoise', {'source': str(self.f['noisy']), 'output': str(target),
                                  'approve_write': approval})
            self.assertFalse(target.exists())
        with self.assertRaises(ValueError):
            A.run('denoise', {'source': str(self.f['noisy']), 'output': str(target),
                              'approve_write': True, 'strength_db': 60})
        self.assertFalse(target.exists())
        out = A.run('denoise', {'source': str(self.f['noisy']), 'output': str(target),
                                'approve_write': True, 'noise_region': [0.0, 0.45],
                                'reference': str(self.f['clean'])})['result']
        snr = out['snr']
        self.assertGreater(snr['after_db'], snr['before_db'] + 2.0, snr)
        self.assertAlmostEqual(out['noise_floor_db'], 20 * math.log10(0.05), delta=1.0)
        self.assertTrue(target.is_file())
        self.assertInputsUnchanged()

    # 16.06
    def test_extract_pcm_preserves_channels_and_rate(self):
        target = self.out('extracted.wav')
        with self.assertRaises(PermissionError):
            A.run('extract_pcm', {'source': str(self.f['stereo_mp4']), 'output': str(target)})
        self.assertFalse(target.exists())
        with self.assertRaises(ValueError):
            A.run('extract_pcm', {'source': str(self.f['stereo_mp4']),
                                  'output': str(self.out('x.mp3')), 'approve_write': True})
        out = A.run('extract_pcm', {'source': str(self.f['stereo_mp4']), 'output': str(target),
                                    'approve_write': True})['result']
        probe = json.loads(subprocess.run(
            ['ffprobe', '-v', 'error', '-show_entries', 'stream=channels,sample_rate,codec_name:format=duration',
             '-of', 'json', str(target)], capture_output=True, text=True, timeout=30, check=True).stdout)
        s = probe['streams'][0]
        self.assertEqual((s['channels'], int(s['sample_rate']), s['codec_name']), (2, 48000, 'pcm_s16le'))
        self.assertEqual((out['channels'], out['sample_rate']), (2, 48000))
        self.assertLessEqual(abs(out['duration_difference']), 1 / 25)
        self.assertLessEqual(abs(float(probe['format']['duration']) - 2.0), 1 / 25)
        self.assertInputsUnchanged()

    # 16.07
    def test_crossfade_removes_click(self):
        target = self.out('joined.wav')
        with self.assertRaises(PermissionError):
            A.run('cut_crossfade', {'source': str(self.f['a']), 'next_source': str(self.f['b']),
                                    'output': str(target)})
        self.assertFalse(target.exists())
        out = A.run('cut_crossfade', {'source': str(self.f['a']), 'next_source': str(self.f['b']),
                                      'output': str(target), 'approve_write': True,
                                      'crossfade_ms': 20})['result']
        c = out['clicks']
        self.assertGreater(c['hard_cut_joint_max_jump'], 1.2)
        self.assertLess(c['crossfade_joint_max_jump'], c['hard_cut_joint_max_jump'] / 5)
        self.assertTrue(c['hard_cut_click_suspected'])
        self.assertFalse(c['crossfade_click_suspected'])
        self.assertLessEqual(abs(out['output_frames'] - out['expected_output_frames']), 2)
        self.assertInputsUnchanged()

    # 16.08
    def test_av_sync_offsets_and_drift(self):
        aligned = A.run('av_sync', {'source': str(self.f['stereo_mp4']), 'decode_check': True})['result']
        self.assertLess(abs(aligned['start_offset']), 0.03)
        self.assertLess(abs(aligned['cumulative_drift']), 0.05)
        self.assertLess(abs(aligned['audio_content_onset']), 0.03)
        self.assertTrue(aligned['decode_check']['passed'])
        delayed = A.run('av_sync', {'source': str(self.f['adelay_mp4'])})['result']
        self.assertAlmostEqual(delayed['audio_content_onset'], 0.2, delta=0.03)
        shifted = A.run('av_sync', {'source': str(self.f['offset_mp4'])})['result']
        self.assertAlmostEqual(shifted['start_offset'], 0.2, delta=0.03)
        self.assertAlmostEqual(shifted['audio_content_onset'], 0.2, delta=0.03)
        with self.assertRaises(ValueError):
            A.run('av_sync', {'source': str(self.f['tone'])})  # audio-only: no frames to sync
        self.assertInputsUnchanged()

    # 16.09
    def _check_trim(self, res, pad_before, pad_after, max_removal):
        cuts = res['cuts']
        self.assertTrue(cuts)
        tol = 0.03
        for c in cuts:
            for a0, a1 in self.audible:
                self.assertLessEqual(max(0.0, min(c['end'], a1) - max(c['start'], a0)), 0.0, (c, a0, a1))
            prev_end = max(a1 for a0, a1 in self.audible if a1 <= c['start'] + tol)
            next_start = min(a0 for a0, a1 in self.audible if a0 >= c['end'] - tol)
            self.assertGreaterEqual(c['start'] - prev_end, pad_after - tol)
            self.assertGreaterEqual(next_start - c['end'], pad_before - tol)
            self.assertLessEqual(c['removed'], max_removal + 1e-6)
            self.assertFalse(4.0 <= c['start'] <= 4.3)  # 0.3 s gap is never cut
        self.assertTrue(all(res['checks'].values()), res['checks'])
        self.assertAlmostEqual(sum(e['end'] - e['start'] for e in res['edl']), res['new_duration'], delta=0.01)

    def test_pause_trim_audio_and_video(self):
        params = {'min_pause': 0.6, 'pad_before': 0.2, 'pad_after': 0.25, 'max_removal_per_gap': 1.0}
        wav = A.run('pause_trim', {'source': str(self.f['pause']), **params})['result']
        self._check_trim(wav, 0.2, 0.25, 1.0)
        self.assertEqual(len(wav['cuts']), 1)
        self.assertAlmostEqual(wav['cuts'][0]['removed'], 1.0, delta=1e-6)
        mp4 = A.run('pause_trim', {'source': str(self.f['pause_mp4']), **params})['result']
        self.assertEqual(mp4['silence_method'], 'audio_scene_v17.detect_silences')
        self._check_trim(mp4, 0.2, 0.25, 1.0)
        big = A.run('pause_trim', {'source': str(self.f['pause']), 'min_pause': 0.6,
                                   'pad_before': 0.1, 'pad_after': 0.1,
                                   'max_removal_per_gap': 10.0})['result']
        self._check_trim(big, 0.1, 0.1, 10.0)
        with self.assertRaises(ValueError):
            A.run('pause_trim', {'source': str(self.f['pause']), 'pad_before': -1})
        self.assertInputsUnchanged()

    # 16.10
    def test_audio_rights(self):
        digest = sha(self.f['tone'])
        good = {'file': str(self.f['tone']), 'sha256': digest, 'source': 'own studio recording',
                'licence': 'owner-original', 'permission_ref': 'contract-2026-11-01.pdf'}
        out = A.run('audio_rights', {'tracks': [good]})['result']
        self.assertEqual(out['included'], [0])
        self.assertTrue(out['all_cleared'])
        no_licence = dict(good, licence='')
        out = A.run('audio_rights', {'tracks': [good, no_licence]})['result']
        self.assertEqual(out['included'], [0])
        self.assertEqual(out['refused'], [1])
        self.assertIn('missing licence', out['tracks'][1]['reasons'])
        self.assertFalse(out['all_cleared'])
        no_perm = {k: v for k, v in good.items() if k != 'permission_ref'}
        bad_hash = dict(good, sha256='0' * 64)
        out = A.run('audio_rights', {'tracks': [no_perm, bad_hash]})['result']
        self.assertEqual(out['refused'], [0, 1])
        self.assertIn('sha256 does not match the file', out['tracks'][1]['reasons'])
        nc = A.run('audio_rights', {'tracks': [dict(good, licence='CC-BY-NC-4.0')]})['result']
        self.assertEqual(nc['included'], [0])
        self.assertTrue(nc['tracks'][0]['warnings'])
        with self.assertRaises(ValueError):
            A.run('audio_rights', {'tracks': [dict(good, file='https://x/y.wav')]})
        with self.assertRaises(ValueError):
            A.run('audio_rights', {'tracks': [dict(good, evil=1)]})
        self.assertInputsUnchanged()


if __name__ == '__main__':
    unittest.main()
