"""Performance lens (lens 5) for file/media modules and pre-roadmap code,
plus the missing contract/permission lenses for audio.analyze and video.verify."""
from __future__ import annotations

import hashlib
import math
import shutil
import sqlite3
import struct
import tempfile
import unittest
import wave
from contextlib import closing
from pathlib import Path

import perf_lens_v26 as perf
from capability_runtime import execute, REGISTRY


@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'ffmpeg required')
class PerformanceLensTests(unittest.TestCase):
    def _check(self, report):
        self.assertEqual(report['failures'] + report['errors'], 0, report)
        for op, row in report['ops'].items():
            with self.subTest(module=report['module'], op=op):
                self.assertGreater(row['calls'], 0, f'{op} was never exercised by its tests')
                self.assertTrue(row['within_budget'], f'{op} exceeded {report["budget_s"]} s: {row}')

    def test_every_file_module_op_is_timed_within_budget(self):
        for report in perf.measure_io_modules().values():
            self._check(report)

    def test_pre_roadmap_symbols_are_timed_within_budget(self):
        for report in perf.measure_legacy().values():
            self._check(report)

    def test_budget_violation_is_detected(self):
        report = perf.measure('verify_media', 'test_verify_media', ('verify_video',), budget_s=1e-9)
        self.assertFalse(report['ops']['verify_video']['within_budget'])
        with self.assertRaises(ValueError):
            perf.measure('verify_media', 'test_verify_media', ('verify_video',), budget_s=0)


class LegacyContractPermissionTests(unittest.TestCase):
    """16.05 (audio.analyze) and 20.01 (video.verify) contract/permission lenses."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.wav = self.dir / 'tone.wav'
        with wave.open(str(self.wav), 'wb') as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000)
            frames = [int(12000 * math.sin(2 * math.pi * 220 * n / 16000)) if n < 8000 else 0
                      for n in range(16000)]
            w.writeframes(struct.pack('<' + 'h' * len(frames), *frames))

    def test_audio_analyze_contract_and_read_only(self):
        self.assertEqual(REGISTRY['audio.analyze'][1], 'read')
        before = hashlib.sha256(self.wav.read_bytes()).hexdigest()
        listing = sorted(p.name for p in self.dir.iterdir())
        with closing(sqlite3.connect(self.dir / 'audit.db')) as db:
            out = execute(db, 'audio.analyze', {'audio': str(self.wav)})
            self.assertEqual(out['effect'], 'read')
            self.assertIn('no word or phoneme alignment', out['result']['method'])
            self.assertGreater(out['result']['silence_ratio'], 0.3)
            for bad in ({'audio': str(self.wav), 'shell': 'x'}, {}):
                with self.subTest(bad=bad), self.assertRaises(ValueError):
                    execute(db, 'audio.analyze', bad)
        self.assertEqual(hashlib.sha256(self.wav.read_bytes()).hexdigest(), before)
        self.assertEqual(sorted(p.name for p in self.dir.iterdir()), sorted(listing + ['audit.db']))

    @unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'ffmpeg required')
    def test_video_verify_contract(self):
        import subprocess
        clip = self.dir / 'c.mp4'
        subprocess.run(['ffmpeg', '-v', 'error', '-nostdin', '-y', '-f', 'lavfi', '-i',
                        'testsrc2=s=160x96:r=12:d=1', '-pix_fmt', 'yuv420p', str(clip)],
                       capture_output=True, check=True, timeout=30)
        self.assertEqual(REGISTRY['video.verify'][1], 'read')
        with closing(sqlite3.connect(self.dir / 'audit.db')) as db:
            ok = execute(db, 'video.verify', {'video': str(clip), 'fps': 12, 'width': 160, 'height': 96})
            self.assertEqual(ok['status'], 'executed')
            for bad in ({'video': str(clip), 'overwrite': True}, {}):
                with self.subTest(bad=bad), self.assertRaises(ValueError):
                    execute(db, 'video.verify', bad)
            with self.assertRaises(Exception):
                execute(db, 'video.verify', {'video': str(clip), 'width': 999})


if __name__ == '__main__':
    unittest.main()
