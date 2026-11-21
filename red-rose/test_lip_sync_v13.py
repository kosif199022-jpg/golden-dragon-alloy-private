"""Voice-sync tests use generated original simple speech-like tones, not music."""
import math, tempfile, unittest, wave, struct
from pathlib import Path
from lip_sync import levels_from_audio,apply_lipsync,value_at
from storyboard import frame_at

def make_audio(p, sr=16000, total=1.5):
    data=[]
    for n in range(int(sr*total)):
        t=n/sr
        # Silence, then a speech-energy interval, then silence.
        speech = 0.45 <= t < 1.05
        signal=round((9500*math.sin(2*math.pi*240*t) if speech else 0))
        data.append(signal)
    with wave.open(str(p),'wb') as w:
        w.setnchannels(1);w.setsampwidth(2);w.setframerate(sr)
        w.writeframes(struct.pack('<%dh'%len(data),*data))

class LipSyncTests(unittest.TestCase):
    def test_detect_speech_and_silence(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'voice.wav';make_audio(p)
            levels=levels_from_audio(p)
            self.assertLess(value_at(levels,.12),.02)
            self.assertGreater(value_at(levels,.7),.5)
            self.assertLess(value_at(levels,1.35),.02)
    def test_scene_local_tracks_and_no_mutation(self):
        s=[{'duration':.75,'recipe':{'mode':'director2d','actor':{'rig':'ik2d','expression':'serious'}}},
           {'duration':.75,'recipe':{'mode':'director2d','actor':{'rig':'ik2d','expression':'serious'}}}]
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'voice.wav';make_audio(p)
            updated,report=apply_lipsync(s,levels_from_audio(p))
        self.assertEqual(report['processed_shots'],2)
        self.assertFalse(report['phoneme_alignment'])
        self.assertNotIn('mouth_keys',s[0]['recipe']['actor'])
        for scene in updated:
            keys=scene['recipe']['actor']['mouth_keys']
            self.assertLessEqual(len(keys),64)
            self.assertEqual(keys[0]['t'],0)
            self.assertEqual(keys[-1]['t'],1)
        self.assertNotEqual(frame_at(updated,.12,320,568),frame_at(updated,.65,320,568))
    def test_long_shot_key_budget(self):
        s=[{'duration':120,'recipe':{'mode':'director2d','actor':{'rig':'ik2d'}}}]
        updated,_=apply_lipsync(s,[.5]*30)
        self.assertEqual(len(updated[0]['recipe']['actor']['mouth_keys']),64)
    def test_rejects_manual_track_conflict(self):
        s=[{'duration':1,'recipe':{'mode':'director2d','actor':{'rig':'ik2d','mouth_keys':[{'t':0,'value':0}]}}}]
        with self.assertRaisesRegex(ValueError,'conflicts'):apply_lipsync(s,[0]*20)
    def test_rejects_invalid_levels(self):
        s=[{'duration':1,'recipe':{'mode':'director2d','actor':{'rig':'ik2d'}}}]
        for levels in ([],[float('nan')],[2.0]):
            with self.assertRaises(ValueError):apply_lipsync(s,levels)
    def test_rejects_missing_audio(self):
        with self.assertRaises(ValueError):levels_from_audio('does-not-exist.wav')
    def test_silence_never_invents_speech(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'quiet.wav'
            with wave.open(str(p),'wb') as w:
                w.setnchannels(1);w.setsampwidth(2);w.setframerate(16000)
                w.writeframes(b'\0\0'*16000)
            self.assertTrue(all(level==0 for level in levels_from_audio(p)))

if __name__=='__main__':unittest.main()
