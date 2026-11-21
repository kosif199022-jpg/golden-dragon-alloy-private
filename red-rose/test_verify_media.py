import json,subprocess,tempfile,unittest
from pathlib import Path
from production import produce
from verify_media import verify_video
class QATests(unittest.TestCase):
 def test_persist_editable_project_and_qa(self):
  with tempfile.TemporaryDirectory() as d:
   s=[{'duration':.3,'recipe':{'mode':'director2d'}}]
   result=produce(s,d, fps=10,width=320,height=568)
   report=result['qa']
   self.assertTrue(report['passed'])
   self.assertEqual(report['frames'],3)
   self.assertEqual(json.loads((Path(d)/'project.json').read_text())['shots'],s)
   self.assertEqual(json.loads((Path(d)/'qa.json').read_text())['sha256'],report['sha256'])
 def test_mismatching_requirements_are_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   s=[{'duration':.2,'recipe':{'mode':'director2d'}}]
   result=produce(s,d, fps=10,width=320,height=568)
   with self.assertRaises(ValueError):verify_video(result['video'],expected_frames=100)
 def test_short_audio_padded_to_video_duration(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'short.wav'
   subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','sine=frequency=380:duration=0.12','-y',str(p)],check=True)
   result=produce([{'duration':.5,'recipe':{'mode':'director2d'}}],d, fps=10,width=320,height=568,audio=p)
   self.assertEqual(result['qa']['audio_codec'],'aac')
   self.assertAlmostEqual(result['qa']['duration'],.5,places=1)
