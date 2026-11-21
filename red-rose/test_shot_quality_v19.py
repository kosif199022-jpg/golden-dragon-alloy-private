"""V19: measured per-shot technical quality on original synthetic FFmpeg footage."""
from __future__ import annotations
from contextlib import closing
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from shot_quality_v19 import shot_quality, frame_metrics, GRID_W, GRID_H
from capability_runtime import REGISTRY, execute, plan_task
from verify_media import verify_video

DIR = Path(__file__).resolve().parent


def _ffmpeg(*args):
    subprocess.run(['ffmpeg', '-hide_banner', '-nostdin', '-v', 'error', '-y', *args],
                   capture_output=True, check=True, timeout=40)


@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'ffmpeg required')
class ShotQualityV18Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.dir = Path(cls.tmp.name)
        # Shot 1 detailed+moving, 2 near-black, 3 heavily blurred static bars, 4 blown white.
        cls.source = cls.dir / 'quality-source.mp4'
        _ffmpeg('-f', 'lavfi', '-i', 'testsrc2=s=160x96:r=12:d=1',
                '-f', 'lavfi', '-i', 'color=c=0x0a0a0a:s=160x96:r=12:d=1',
                '-f', 'lavfi', '-i', 'smptebars=s=160x96:r=12:d=1,gblur=sigma=12',
                '-f', 'lavfi', '-i', 'color=c=white:s=160x96:r=12:d=1',
                '-f', 'lavfi', '-i', 'sine=frequency=330:sample_rate=16000:duration=4',
                '-filter_complex', '[0:v][1:v][2:v][3:v]concat=n=4:v=1:a=0,format=yuv420p[v]',
                '-map', '[v]', '-map', '4:a:0', '-c:v', 'libx264', '-c:a', 'aac',
                '-shortest', str(cls.source))
        cls.before = sorted(p.name for p in cls.dir.iterdir())
        cls.report = shot_quality(cls.source)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_four_shots_detected_and_measured(self):
        shots = self.report['shots']
        self.assertEqual(len(shots), 4, shots)
        for s, start in zip(shots, (0, 1, 2, 3)):
            self.assertAlmostEqual(s['start'], start, delta=.3)
            self.assertGreaterEqual(s['samples'], 1)
            self.assertTrue(0 <= s['score'] <= 1)
        self.assertEqual(self.report['status'], 'analyzed_not_edited')

    def test_flags_match_known_defects(self):
        good, dark, blurred, white = self.report['shots']
        self.assertEqual(good['flags'], [], good)
        self.assertIn('underexposed', dark['flags'])
        self.assertNotIn('overexposed', dark['flags'])
        self.assertIn('low_detail', blurred['flags'])
        self.assertNotIn('underexposed', blurred['flags'])
        self.assertIn('static', blurred['flags'])
        self.assertIn('overexposed', white['flags'])
        self.assertNotIn('underexposed', white['flags'])

    def test_detailed_moving_shot_ranks_first_and_alone_by_default(self):
        scores = [s['score'] for s in self.report['shots']]
        self.assertEqual(scores.index(max(scores)), 0)
        self.assertGreater(scores[0], .8)
        self.assertLess(max(scores[1], scores[3]), .2)
        self.assertEqual(len(self.report['suggested_edl']), 1)
        self.assertAlmostEqual(self.report['suggested_edl'][0]['start'], 0, delta=.05)
        self.assertTrue(self.report['requires_explicit_approved_video_recut'])

    def test_lower_min_score_adds_shots_in_source_order(self):
        r = shot_quality(self.source, min_score=.3, max_clips=4)
        starts = [e['start'] for e in r['suggested_edl']]
        self.assertEqual(starts, sorted(starts))
        self.assertEqual(len(starts), 2)  # good + blurred; black/white stay excluded

    def test_detail_metric_separates_sharp_from_blurred_same_content(self):
        sharp, soft = self.dir / 'sharp.gray', self.dir / 'soft.gray'
        for out, vf in ((sharp, 'scale=%d:%d' % (GRID_W, GRID_H)),
                        (soft, 'gblur=sigma=6,scale=%d:%d' % (GRID_W, GRID_H))):
            _ffmpeg('-f', 'lavfi', '-i', 'testsrc2=s=320x180:d=1', '-frames:v', '1',
                    '-vf', vf + ',format=gray', '-f', 'rawvideo', str(out))
        a = frame_metrics(sharp.read_bytes())
        b = frame_metrics(soft.read_bytes())
        self.assertGreater(a['detail'], 3 * b['detail'], (a, b))
        with self.assertRaises(ValueError):
            frame_metrics(b'\x00' * 10)

    def test_analysis_writes_nothing_and_is_deterministic(self):
        self.assertEqual(sorted(p.name for p in self.dir.iterdir() if not p.suffix == '.gray'),
                         self.before)
        again = shot_quality(self.source)
        self.assertEqual(again['shots'], self.report['shots'])
        self.assertEqual(again['suggested_edl'], self.report['suggested_edl'])

    def test_invalid_parameters_and_paths(self):
        with self.assertRaises(ValueError): shot_quality(self.source, sample_fps=1)
        with self.assertRaises(ValueError): shot_quality(self.source, sample_fps=True)
        with self.assertRaises(ValueError): shot_quality(self.source, max_clips=0)
        with self.assertRaises(ValueError): shot_quality(self.source, min_score=1.5)
        with self.assertRaises(ValueError): shot_quality(self.source, max_duration=float('nan'))
        with self.assertRaises(ValueError): shot_quality('http://example.com/v.mp4')
        with self.assertRaises(ValueError): shot_quality(self.dir / 'missing.mp4')

    def test_registered_read_only_adapter_and_injection_guard(self):
        self.assertEqual(REGISTRY['video.shot_quality'][1], 'read')
        with closing(sqlite3.connect(':memory:')) as db:
            r = execute(db, 'video.shot_quality', {'source': str(self.source)})
            self.assertEqual(r['status'], 'executed')
            self.assertFalse(r['legacy_runtime_called'])
            self.assertEqual(r['result']['suggested_edl'], self.report['suggested_edl'])
            with self.assertRaisesRegex(ValueError, 'unknown parameters'):
                execute(db, 'video.shot_quality', {'source': str(self.source), 'cmd': 'del *'})
            plan = plan_task(db, 'رتّب اللقطات حسب الجودة')
            self.assertIn('video.shot_quality', plan['suggested_native_adapters'])
            self.assertEqual(plan['status'], 'planned_not_executed')

    def test_proposal_feeds_approval_gated_recut(self):
        dest = self.dir / 'v19_best_shots.mp4'
        with closing(sqlite3.connect(':memory:')) as db:
            params = {'source': str(self.source), 'segments': self.report['suggested_edl'],
                      'output': str(dest), 'fps': 12}
            self.assertEqual(execute(db, 'video.recut', params)['status'], 'approval_required')
            self.assertFalse(dest.exists())
            done = execute(db, 'video.recut', params, approve_write=True)
            self.assertTrue(done['result']['qa']['passed'])
        qa = verify_video(dest, expected_fps=12, width=160, height=96, expected_audio=True)
        self.assertTrue(qa['passed'])
        self.assertAlmostEqual(qa['duration'], 1.0, delta=.25)

    def test_cli_shot_quality(self):
        env = {**os.environ, 'PYTHONIOENCODING': 'utf-8'}
        out = subprocess.run([sys.executable, str(DIR / 'rose.py'), '--db', str(self.dir / 'cli.sqlite3'),
                              'shot-quality', str(self.source)],
                             capture_output=True, text=True, encoding='utf-8', env=env,
                             timeout=120, check=True).stdout
        data = json.loads(out)
        self.assertEqual(data['capability'], 'video.shot_quality')
        self.assertEqual(len(data['result']['shots']), 4)


if __name__ == '__main__':
    unittest.main()
