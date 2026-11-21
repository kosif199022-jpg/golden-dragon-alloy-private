"""Real original-footage V16 integration tests; FFmpeg-generated synthetic source."""
from __future__ import annotations
from contextlib import closing
import json
import shutil
import sqlite3
import subprocess
import tempfile
import unittest
from pathlib import Path

from scene_edit_v16 import analyze_cuts, probe_source, recut, validate_edl
from capability_runtime import REGISTRY, execute, list_capabilities
from rose import main as rose_main
from verify_media import verify_video


@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'FFmpeg unavailable')
class SceneEditingV16(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name)
        cls.source = cls.root / 'three-color-cuts.mp4'
        # Clearly identifiable red -> green -> blue, plus one continuous audio track.
        cmd = ['ffmpeg', '-hide_banner', '-nostdin', '-v', 'error', '-y',
               '-f', 'lavfi', '-i', 'color=c=red:s=160x96:r=12:d=1',
               '-f', 'lavfi', '-i', 'color=c=green:s=160x96:r=12:d=1',
               '-f', 'lavfi', '-i', 'color=c=blue:s=160x96:r=12:d=1',
               '-f', 'lavfi', '-i', 'sine=frequency=300:sample_rate=16000:duration=3',
               '-filter_complex', '[0:v][1:v][2:v]concat=n=3:v=1:a=0[v]',
               '-map', '[v]', '-map', '3:a:0', '-c:v', 'libx264',
               '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-shortest', str(cls.source)]
        subprocess.run(cmd, capture_output=True, check=True, timeout=60)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_metadata_and_bounded_scanning(self):
        info = probe_source(self.source)
        self.assertEqual(info['width'], 160)
        self.assertEqual(info['height'], 96)
        self.assertTrue(info['audio'])
        self.assertAlmostEqual(info['duration'], 3, delta=.1)

    def test_detects_true_color_cuts(self):
        info = analyze_cuts(self.source, threshold=.23, sample_fps=6)
        self.assertEqual(len(info['cuts']), 2, info)
        self.assertAlmostEqual(info['cuts'][0], 1, delta=.2)
        self.assertAlmostEqual(info['cuts'][1], 2, delta=.2)
        self.assertEqual(len(info['scenes']), 3)
        self.assertEqual(info['status'], 'analyzed_not_edited')
        self.assertTrue(all(x > .23 for x in info['cut_strengths']))

    def test_threshold_can_disable_cuts(self):
        info = analyze_cuts(self.source, threshold=.95, sample_fps=6)
        self.assertEqual(info['cuts'], [])

    def test_bad_params(self):
        with self.assertRaises(ValueError): analyze_cuts(self.source, threshold=float('nan'))
        with self.assertRaises(ValueError): analyze_cuts(self.source, sample_fps=True)
        with self.assertRaises(ValueError): analyze_cuts(self.source, min_shot_seconds=0)

    def test_recut_two_nonadjacent_segments_preserves_audio(self):
        out = self.root/'edit1.mp4'
        result = recut(self.source, [{'start':2.,'end':3.}, {'start':0.,'end':1.}],out,fps=12)
        self.assertEqual(result['segments'], 2)
        self.assertTrue(result['audio_preserved'])
        qa=verify_video(out,expected_fps=12,width=160,height=96,expected_audio=True)
        self.assertAlmostEqual(qa['duration'],2,delta=.15)
        self.assertEqual(result['qa']['sha256'],qa['sha256'])

    def test_edit_safety_collision(self):
        p=self.root/'exists.mp4';p.write_bytes(b'do not overwrite')
        with self.assertRaisesRegex(ValueError,'new .mp4'):
            recut(self.source,[{'start':0,'end':1}],p)
        self.assertEqual(p.read_bytes(),b'do not overwrite')
        with self.assertRaises(ValueError):recut(self.source,[{'start':0,'end':1}],self.source)

    def test_edl_validation(self):
        info=probe_source(self.source)
        with self.assertRaises(ValueError):validate_edl(info,[{'start':2,'end':4}])
        with self.assertRaises(ValueError):validate_edl(info,[{'start':0,'end':0.01}])
        with self.assertRaises(ValueError):validate_edl(info,[{'start':0,'end':1,'command':'rm'}])
        with self.assertRaises(ValueError):validate_edl(info,[])
        with self.assertRaises(ValueError):validate_edl(info,[{'start':0,'end':1}]*17)

    def test_reject_nonlocal_or_invalid_source(self):
        with self.assertRaises(ValueError):probe_source('https://example.org/video.mp4')
        with self.assertRaises(ValueError):probe_source(self.root/'missing.mp4')

    def test_registered_two_native_adapters(self):
        self.assertIn('video.scene_analyze',REGISTRY)
        self.assertIn('video.recut',REGISTRY)
        self.assertEqual(len(list_capabilities()),13)

    def test_capability_read_analyze_executes(self):
        with closing(sqlite3.connect(':memory:')) as db:
            result=execute(db,'video.scene_analyze',{'source':str(self.source),'threshold':.23})
            self.assertEqual(result['status'],'executed')
            self.assertEqual(result['effect'],'read')
            self.assertEqual(len(result['result']['cuts']),2)
            self.assertFalse(result['legacy_runtime_called'])

    def test_capability_write_approval_gate_and_effect(self):
        dest=self.root/'api-edit.mp4'
        params={'source':str(self.source),'segments':[{'start':0,'end':.5}], 'output':str(dest),'fps':12}
        with closing(sqlite3.connect(':memory:')) as db:
            denied=execute(db,'video.recut',params)
            self.assertEqual(denied['status'],'approval_required')
            self.assertFalse(dest.exists())
            out=execute(db,'video.recut',params,approve_write=True)
            self.assertEqual(out['status'],'executed')
            self.assertTrue(dest.is_file())
            self.assertTrue(out['result']['qa']['passed'])

    def test_missing_command_rejected_by_whitelist(self):
        with closing(sqlite3.connect(':memory:')) as db:
            with self.assertRaisesRegex(ValueError,'unknown parameters'):
                execute(db,'video.recut',{'source':str(self.source),'output':'x.mp4','segments':[], 'shell':'powershell'},approve_write=True)

if __name__=='__main__':unittest.main()


@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'FFmpeg unavailable')
class AdditionalV16Regressions(unittest.TestCase):
    def test_no_audio_video_recut(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);src=root/'silent.mp4';dst=root/'clip.mp4'
            subprocess.run(['ffmpeg','-v','error','-nostdin','-f','lavfi','-i',
                            'testsrc2=duration=1:size=96x64:rate=12','-an','-c:v',
                            'libx264','-pix_fmt','yuv420p','-y',str(src)],
                           capture_output=True,timeout=30,check=True)
            result=recut(src,[{'start':0.1,'end':.7}],dst,fps=12)
            self.assertFalse(result['audio_preserved'])
            self.assertTrue(result['qa']['passed'])
            self.assertIsNone(result['qa']['audio_codec'])

    def test_cli_recut_requires_explicit_flag(self):
        import contextlib,io
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);source=root/'src.mp4';edl=root/'edl.json';dest=root/'out.mp4';db=root/'db.sqlite'
            subprocess.run(['ffmpeg','-v','error','-nostdin','-f','lavfi','-i',
                            'color=c=red:duration=1:size=96x64:rate=12','-an','-c:v',
                            'libx264','-pix_fmt','yuv420p','-y',str(source)],
                           capture_output=True,timeout=30,check=True)
            edl.write_text(json.dumps([{'start':0,'end':.6}]))
            buffer=io.StringIO()
            with contextlib.redirect_stdout(buffer):
                rose_main(['--db',str(db),'recut',str(source),str(edl),str(dest),'--fps','12'])
            self.assertEqual(json.loads(buffer.getvalue())['status'],'approval_required')
            self.assertFalse(dest.exists())

    def test_cut_results_are_editable_edl(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);source=root/'src.mp4'
            subprocess.run(['ffmpeg','-v','error','-nostdin','-f','lavfi','-i',
                            'color=c=blue:duration=1:size=96x64:rate=12','-an','-c:v',
                            'libx264','-pix_fmt','yuv420p','-y',str(source)],
                           capture_output=True,timeout=30,check=True)
            result=analyze_cuts(source)
            clean,total=validate_edl(probe_source(source),result['suggested_edl'])
            self.assertGreater(total,.8)
            self.assertEqual(len(clean),1)
