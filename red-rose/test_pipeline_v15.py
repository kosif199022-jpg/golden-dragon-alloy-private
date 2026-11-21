import json
import tempfile
import unittest
from pathlib import Path
from pipeline_v15 import budget,prepare_project,render_project


class PipelineV15Tests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
  self.root=Path(self.temp.name)
  self.story=self.root/'story.json'
  self.shots=[{'duration':.4,'recipe':{'mode':'director2d','actor':{'rig':'ik2d','character_id':'hero'}}}]
  self.story.write_text(json.dumps(self.shots))
  self.profiles=self.root/'profiles.json'
  self.profiles.write_text(json.dumps({'hero':{'skin':'#e6b393','hair':'#29202f','coat':'#bd4763','trousers':'#1a2b47'}}))
 def test_profiles_preserve_source(self):
  shots,report=prepare_project(self.story,profiles=self.profiles)
  self.assertIn('hero',report['locked_characters'])
  self.assertEqual(json.loads(self.story.read_text()),self.shots)
  self.assertEqual(shots[0]['recipe']['actor']['coat'],'#bd4763')
 def test_budget_realistic(self):
  self.assertEqual(budget(self.shots,fps=10,width=320,height=568)['frames'],4)
 def test_budget_reject_4k_and_giant(self):
  with self.assertRaises(ValueError):budget(self.shots,24,4096,2160)
  with self.assertRaises(ValueError):budget(self.shots,24,160,287)
  many=[{'duration':120,'recipe':{}}]*6
  with self.assertRaises(ValueError):budget(many,24,320,568)
 def test_nonexistent_storyboard(self):
  with self.assertRaises(FileNotFoundError):prepare_project(self.root/'missing.json')
 def test_refuse_non_list_storyboard(self):
  self.story.write_text('{"shots": []}')
  with self.assertRaises(ValueError):prepare_project(self.story)
 def test_safe_output_new(self):
  out=render_project(self.story,self.root/'out',fps=8,width=160,height=288,profiles=self.profiles)
  self.assertEqual(out['frames'],3)
  self.assertTrue(out['qa']['passed'])
  self.assertEqual(len(out['locked_characters']['hero']),64)
  self.assertEqual(json.loads((self.root/'out'/'project.json').read_text())['shots'][0]['recipe']['actor']['profile_sha256'],out['locked_characters']['hero'])
 def test_nonempty_destination_refused(self):
  p=self.root/'out';p.mkdir();(p/'existing.txt').write_text('protect')
  with self.assertRaises(FileExistsError):render_project(self.story,p,fps=8,width=160,height=288)
  self.assertEqual((p/'existing.txt').read_text(),'protect')
 def test_overwrite_requires_known_red_rose_project(self):
  path=self.root/'unknown';path.mkdir();(path/'important.txt').write_text('dont touch')
  with self.assertRaisesRegex(ValueError,'existing Red Rose project'):
   render_project(self.story,path,fps=8,width=160,height=288,overwrite=True)
  self.assertEqual((path/'important.txt').read_text(),'dont touch')
 def test_overwrite_allowed_for_own_project_only(self):
  path=self.root/'ours'
  first=render_project(self.story,path,fps=8,width=160,height=288)
  second=render_project(self.story,path,fps=8,width=160,height=288,overwrite=True)
  self.assertTrue(second['qa']['passed'])
  self.assertEqual(first['frames'],second['frames'])
 def test_reject_current_directory(self):
  with self.assertRaises(ValueError):render_project(self.story,Path.cwd(),fps=8,width=160,height=288)
 def test_no_silent_auto_visemes(self):
  with self.assertRaisesRegex(ValueError,'viseme sync'):
   prepare_project(self.story,viseme_sync=True)
 def test_no_lip_without_audio(self):
  with self.assertRaises(ValueError):prepare_project(self.story,lip_sync=True)

if __name__=='__main__':unittest.main()
