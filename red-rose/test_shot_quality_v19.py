"""V19: per-shot technical quality measured on original synthetic footage."""
from __future__ import annotations
from contextlib import closing, redirect_stdout
import hashlib
import io
import json
import math
import shutil
import sqlite3
import struct
import subprocess
import tempfile
import unittest
import wave
from pathlib import Path

from capability_runtime import REGISTRY, execute, plan_task
from rose import main as rose_main, connect
from scene_edit_v16 import recut
from shot_quality_v19 import (score_shots, _exposure_score, _motion_score,
                              REJECT_FLAGS, WEIGHTS, WEIGHTS_SILENT_SOURCE)


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'ffmpeg required')
class ShotQualityV19Tests(unittest.TestCase):
    """Shots: 1 detailed+moving+tone, 2 near black, 3 flat static gray+tone, 4 white."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.dir = Path(cls.tmp.name)
        wav = cls.dir/'audio.wav'
        with wave.open(str(wav), 'wb') as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000)
            samples = []
            for n in range(16000*6):
                sec = n/16000
                loud = .05 <= sec < 1.45 or 3.05 <= sec < 4.45
                samples.append(int(16000*math.sin(2*math.pi*260*sec)) if loud else 0)
            w.writeframes(struct.pack('<'+str(len(samples))+'h', *samples))
        cls.source = cls.dir/'quality-source.mp4'
        cmd = ['ffmpeg', '-hide_banner', '-nostdin', '-v', 'error', '-y',
               '-f', 'lavfi', '-i', 'testsrc2=s=160x96:r=12:d=1.5',
               '-f', 'lavfi', '-i', 'color=c=0x050505:s=160x96:r=12:d=1.5',
               '-f', 'lavfi', '-i', 'color=c=0x808080:s=160x96:r=12:d=1.5',
               '-f', 'lavfi', '-i', 'color=c=white:s=160x96:r=12:d=1.5',
               '-i', str(wav), '-filter_complex',
               '[0:v][1:v][2:v][3:v]concat=n=4:v=1:a=0,format=yuv420p[v]',
               '-map', '[v]', '-map', '4:a:0', '-c:v', 'libx264', '-crf', '12',
               '-c:a', 'aac', '-shortest', str(cls.source)]
        subprocess.run(cmd, capture_output=True, check=True, timeout=40)
        cls.no_audio = cls.dir/'quality-no-audio.mp4'
        subprocess.run(['ffmpeg', '-v', 'error', '-nostdin', '-y', '-i', str(cls.source),
                        '-an', '-c:v', 'copy', str(cls.no_audio)],
                       capture_output=True, check=True, timeout=25)
        cls.report = score_shots(cls.source, max_clips=2)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_four_shots_measured_with_expected_flags(self):
        shots = self.report['shots']
        self.assertEqual(len(shots), 4, self.report)
        detailed, black, gray, white = shots
        self.assertTrue(all(s['measured'] and s['sampled_frames'] >= 6 for s in shots))
        self.assertEqual(detailed['flags'], [], detailed)
        self.assertIn('too_dark', black['flags'])
        self.assertLess(black['mean_luma'], .08)
        self.assertGreater(black['crushed_black_fraction'], .9)
        self.assertIn('low_detail', gray['flags'])
        self.assertIn('static', gray['flags'])
        self.assertAlmostEqual(gray['mean_luma'], .5, delta=.06)
        self.assertIn('too_bright', white['flags'])
        self.assertGreater(white['mean_luma'], .9)
        # Only the test pattern actually moves or carries edges.
        self.assertGreater(detailed['detail'], 10*max(gray['detail'], 1e-6))
        self.assertGreater(detailed['motion'], gray['motion'])

    def test_ranking_and_proposal_skip_rejected_shots(self):
        r = self.report
        self.assertEqual(r['status'], 'proposal_only_not_rendered')
        self.assertTrue(r['requires_explicit_approved_video_recut'])
        self.assertEqual(r['ranking'][0], 1)
        self.assertEqual({x['index'] for x in r['rejected_shots']}, {2, 4})
        for item in r['rejected_shots']:
            self.assertTrue(set(item['flags']) & set(REJECT_FLAGS))
        self.assertEqual(len(r['suggested_edl']), 2)
        starts = [e['start'] for e in r['suggested_edl']]
        self.assertEqual(starts, sorted(starts), 'proposal must stay in source order')
        self.assertAlmostEqual(starts[0], 0., delta=.01)
        self.assertAlmostEqual(starts[1], 3., delta=.2)
        self.assertAlmostEqual(r['selected_seconds'], 3., delta=.4)
        self.assertEqual(r['weights'], WEIGHTS)
        self.assertIn('no focus', r['limitations'])

    def test_audio_is_joined_to_picture(self):
        detailed, black, gray, white = self.report['shots']
        self.assertGreater(detailed['audible_fraction'], .7)
        self.assertGreater(gray['audible_fraction'], .7)
        self.assertLess(black['audible_fraction'], .3)
        self.assertLess(white['audible_fraction'], .3)
        self.assertEqual(detailed['score_parts']['detail'], 1.)

    def test_analysis_is_read_only(self):
        before = _sha(self.source)
        listing = sorted(p.name for p in self.dir.iterdir())
        score_shots(self.source)
        self.assertEqual(_sha(self.source), before)
        self.assertEqual(sorted(p.name for p in self.dir.iterdir()), listing)

    def test_silent_source_uses_picture_only_weights(self):
        r = score_shots(self.no_audio)
        self.assertFalse(r['audio_available'])
        self.assertEqual(r['weights'], WEIGHTS_SILENT_SOURCE)
        self.assertEqual(r['weights']['audio'], 0.)
        self.assertIsNone(r['shots'][0]['audible_fraction'])
        self.assertEqual(r['ranking'][0], 1)
        self.assertEqual({x['index'] for x in r['rejected_shots']}, {2, 4})

    def test_budget_limits_selection(self):
        one = score_shots(self.source, max_clips=1)
        self.assertEqual(len(one['suggested_edl']), 1)
        self.assertAlmostEqual(one['suggested_edl'][0]['start'], 0., delta=.01)
        tiny = score_shots(self.source, max_clips=4, max_duration=.5)
        self.assertEqual(tiny['suggested_edl'], [])
        self.assertEqual(tiny['selected_seconds'], 0.)

    def test_invalid_inputs_rejected(self):
        for bad in ({'max_clips': 0}, {'max_clips': 17}, {'max_clips': True},
                    {'max_duration': 0}, {'max_duration': float('nan')},
                    {'sample_fps': 1}, {'sample_fps': 2.5}, {'threshold': 2}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                score_shots(self.source, **bad)
        for source in ('https://example.com/a.mp4', str(self.dir/'missing.mp4'),
                       str(self.dir/'audio.wav'), None):
            with self.subTest(source=source), self.assertRaises(ValueError):
                score_shots(source)

    def test_registered_read_adapter_dispatch_and_audit(self):
        self.assertEqual(REGISTRY['video.shot_score'][1], 'read')
        self.assertEqual(REGISTRY['video.shot_score'][2], 'ffmpeg')
        with closing(sqlite3.connect(self.dir/'audit.sqlite3')) as db:
            out = execute(db, 'video.shot_score', {'source': str(self.source), 'max_clips': 2})
            self.assertEqual(out['status'], 'executed')
            self.assertEqual(out['effect'], 'read')
            self.assertFalse(out['legacy_runtime_called'])
            self.assertEqual(out['result']['ranking'][0], 1)
            row = db.execute('SELECT capability,outcome FROM capability_execution_audit WHERE id=?',
                             (out['audit_id'],)).fetchone()
            self.assertEqual(row, ('video.shot_score', 'executed'))
            for params in ({'source': str(self.source), 'shell': 'rm -rf'},
                           {'source': str(self.source), 'output': 'x.mp4'}, {}):
                with self.subTest(params=params), self.assertRaises(ValueError):
                    execute(db, 'video.shot_score', params)

    def test_planner_and_cli_expose_shot_score(self):
        db_path = self.dir/'cli.sqlite3'
        with closing(connect(db_path)) as db:
            plan = plan_task(db, 'قيّم جودة اللقطات')
        self.assertIn('video.shot_score', plan['suggested_native_adapters'])
        self.assertEqual(plan['status'], 'planned_not_executed')
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            rose_main(['--db', str(db_path), 'shot-score', str(self.source), '--max-clips', '1'])
        result = json.loads(buffer.getvalue())
        self.assertEqual(result['capability'], 'video.shot_score')
        self.assertEqual(len(result['result']['suggested_edl']), 1)

    def test_proposal_feeds_approved_recut_only(self):
        target = self.dir/'recut-from-score.mp4'
        with closing(sqlite3.connect(self.dir/'gate.sqlite3')) as db:
            params = {'source': str(self.source), 'segments': self.report['suggested_edl'],
                      'output': str(target)}
            blocked = execute(db, 'video.recut', params)
            self.assertEqual(blocked['status'], 'approval_required')
            self.assertFalse(target.exists())
        made = recut(self.source, self.report['suggested_edl'], target)
        self.assertEqual(made['status'], 'rendered_and_verified')
        self.assertAlmostEqual(made['qa']['duration'], self.report['selected_seconds'], delta=.25)


class ShotScoreMathTests(unittest.TestCase):
    def test_exposure_score_bounds_and_shape(self):
        self.assertEqual(_exposure_score(.5, 0.), 1.)
        self.assertEqual(_exposure_score(0., 0.), 0.)
        self.assertEqual(_exposure_score(1., 0.), 0.)
        self.assertLess(_exposure_score(.5, .5), _exposure_score(.5, 0.))
        for mean in (0., .1, .5, .9, 1.):
            for clipped in (0., .2, 1., 2.):
                self.assertTrue(0. <= _exposure_score(mean, clipped) <= 1.)

    def test_motion_score_prefers_moderate_change(self):
        self.assertEqual(_motion_score(0.), 0.)
        self.assertEqual(_motion_score(.05), 1.)
        self.assertLess(_motion_score(.005), _motion_score(.05))
        self.assertLess(_motion_score(.15), _motion_score(.05))
        self.assertEqual(_motion_score(.5), 0.)

    def test_weights_sum_to_one(self):
        self.assertAlmostEqual(sum(WEIGHTS.values()), 1.)
        self.assertAlmostEqual(sum(WEIGHTS_SILENT_SOURCE.values()), 1.)


if __name__ == '__main__':
    unittest.main()
