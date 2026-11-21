"""V17: test visual-cut + soundtrack silence on original synthetic test footage."""
from __future__ import annotations
from contextlib import closing
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

from audio_scene_v17 import detect_silences, timeline_analyze, suggest_edit
from scene_edit_v16 import recut
from capability_runtime import REGISTRY, execute
from verify_media import verify_video

@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'ffmpeg required')
class AudioSceneV17Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.dir = Path(cls.tmp.name)
        wav=cls.dir/'audio.wav'
        with wave.open(str(wav),'wb') as w:
            w.setnchannels(1);w.setsampwidth(2);w.setframerate(16000)
            samples=[]
            for n in range(16000*3):
                sec=n/16000
                v=int(16000*math.sin(2*math.pi*260*sec)) if 1.02<=sec<1.96 else 0
                samples.append(v)
            w.writeframes(struct.pack('<'+str(len(samples))+'h',*samples))
        cls.source=cls.dir/'scene-source.mp4'
        cmd=['ffmpeg','-hide_banner','-nostdin','-v','error','-y',
             '-f','lavfi','-i','color=c=red:s=160x96:r=12:d=1',
             '-f','lavfi','-i','color=c=green:s=160x96:r=12:d=1',
             '-f','lavfi','-i','color=c=blue:s=160x96:r=12:d=1',
             '-i',str(wav),'-filter_complex','[0:v][1:v][2:v]concat=n=3:v=1:a=0[v]',
             '-map','[v]','-map','3:a:0','-c:v','libx264','-pix_fmt','yuv420p',
             '-c:a','aac','-shortest',str(cls.source)]
        subprocess.run(cmd,capture_output=True,check=True,timeout=35)
        cls.no_audio=cls.dir/'no-audio.mp4'
        subprocess.run(['ffmpeg','-v','error','-nostdin','-y','-i',str(cls.source),
                        '-an','-c:v','copy',str(cls.no_audio)],capture_output=True,check=True,timeout=25)

    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()

    def test_acoustic_silence_intervals(self):
        r=detect_silences(self.source)
        self.assertTrue(r['audio_available'])
        self.assertGreaterEqual(len(r['silences']),2,r)
        self.assertLess(r['silences'][0]['start'],.2)
        self.assertAlmostEqual(r['silences'][0]['end'],1.02,delta=.15)
        self.assertAlmostEqual(r['silences'][-1]['start'],1.96,delta=.15)

    def test_visual_audio_timeline_finds_middle_active_scene(self):
        report=timeline_analyze(self.source)
        self.assertEqual(len(report['visual_cuts']),2)
        self.assertEqual(len(report['scenes']),3)
        first,middle,last=report['scenes']
        self.assertGreater(first['quiet_fraction'],.8)
        self.assertGreater(middle['audible_fraction'],.75)
        self.assertGreater(last['quiet_fraction'],.8)
        self.assertEqual(report['status'],'analyzed_not_edited')

    def test_suggestion_proposes_only_acoustically_active_shot(self):
        r=suggest_edit(self.source,max_clips=3,min_audible_ratio=.6)
        self.assertEqual(r['status'],'proposal_only_not_rendered')
        self.assertEqual(len(r['suggested_edl']),1)
        self.assertAlmostEqual(r['suggested_edl'][0]['start'],1,delta=.2)
        self.assertTrue(r['requires_explicit_approved_video_recut'])
        self.assertFalse(any(x.name.endswith('.recut.mp4') for x in self.dir.iterdir()))

    def test_audio_free_video_does_not_claim_speech(self):
        r=timeline_analyze(self.no_audio)
        self.assertFalse(r['audio_available'])
        self.assertEqual(r['silences'],[])
        self.assertTrue(all(s['audible_fraction'] is None for s in r['scenes']))
        plan=suggest_edit(self.no_audio,max_clips=2)
        self.assertTrue(plan['suggested_edl'])

    def test_invalid_parameters_and_paths(self):
        with self.assertRaises(ValueError):detect_silences(self.source,noise_db=-200)
        with self.assertRaises(ValueError):detect_silences(self.source,min_silence=0)
        with self.assertRaises(ValueError):suggest_edit(self.source,max_clips=17)
        with self.assertRaises(ValueError):suggest_edit(self.source,max_clips=True)
        with self.assertRaises(ValueError):suggest_edit(self.source,min_audible_ratio=2)
        with self.assertRaises(ValueError):detect_silences('http://example.com/video.mp4')

    def test_two_new_read_only_capabilities(self):
        self.assertEqual(REGISTRY['video.timeline_analyze'][1],'read')
        self.assertEqual(REGISTRY['video.edit_suggest'][1],'read')
        with closing(sqlite3.connect(':memory:')) as db:
            t=execute(db,'video.timeline_analyze',{'source':str(self.source)})
            self.assertEqual(t['status'],'executed')
            self.assertFalse(t['legacy_runtime_called'])
            p=execute(db,'video.edit_suggest',{'source':str(self.source),'min_audible_ratio':.6})
            self.assertEqual(p['status'],'executed')
            self.assertEqual(len(p['result']['suggested_edl']),1)
            with self.assertRaisesRegex(ValueError,'unknown parameters'):
                execute(db,'video.edit_suggest',{'source':str(self.source),'shell':'rm -rf'})

    def test_explicit_existing_recut_adapter_works_with_suggestion(self):
        plan=suggest_edit(self.source,min_audible_ratio=.6)
        dest=self.dir/'approved_v17_edit.mp4'
        with closing(sqlite3.connect(':memory:')) as db:
            params={'source':str(self.source),'segments':plan['suggested_edl'],
                    'output':str(dest),'fps':12}
            denied=execute(db,'video.recut',params)
            self.assertEqual(denied['status'],'approval_required')
            self.assertFalse(dest.exists())
            executed=execute(db,'video.recut',params,approve_write=True)
            self.assertEqual(executed['status'],'executed')
            self.assertTrue(executed['result']['qa']['passed'])
            self.assertTrue(verify_video(dest,expected_fps=12,width=160,height=96,expected_audio=True)['passed'])

    def test_score_and_order_are_deterministic(self):
        a=suggest_edit(self.source,min_audible_ratio=.6)['suggested_edl']
        b=suggest_edit(self.source,min_audible_ratio=.6)['suggested_edl']
        self.assertEqual(a,b)

if __name__=='__main__':unittest.main()
