import tempfile, json, unittest
from pathlib import Path
from contextlib import closing
from rose import connect, ingest
from character import character_frame
from storyboard import frame_at
from production import produce
class IntegrationTests(unittest.TestCase):
 def test_character_render_and_escape(self):
  svg=character_frame(.5,1,320,568,{'character':{'expression':'smile'},'captions':[{'start':0,'end':1,'text':'<not HTML>'}]})
  self.assertIn('&lt;not HTML&gt;',svg)
  self.assertIn('<circle',svg)
 def test_phase_changes_character(self):
  r={'mode':'character2d','character':{'speed':2}}
  self.assertNotEqual(character_frame(0,1,320,568,r),character_frame(.125,1,320,568,r))
 def test_xss_and_invalid(self):
  with self.assertRaises(ValueError):character_frame(0,1,320,568,{'character':{'scale':0}})
  with self.assertRaises(ValueError):character_frame(0,1,320,568,{'captions':[{'start':1,'end':0}]})
 def test_multishot_character_with_camera(self):
  s=[{'duration':1,'recipe':{'mode':'camera2_5d','layers':[]}},{'duration':1,'transition':'fade','recipe':{'mode':'character2d','character':{}}}]
  frame=frame_at(s,1.02,320,568)
  self.assertIn('opacity=',frame)
  self.assertNotIn('<rect width="100%" height="100%" fill="#000000"',frame) # no black fade overlay
 def test_knowledge_provenance_and_secret_guard(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);(root/'useful.md').write_text('Hello motion graphic',encoding='utf-8')
   (root/'credentials.txt').write_text('password=abcdefghijk',encoding='utf-8')
   (root/'key.txt').write_text('api_key=abcdefghijk',encoding='utf-8')
   with closing(connect(root/'memory.db')) as db:
    report=ingest(db,root,'example/repo','v1','MIT')
    self.assertEqual(report['imported'],1)
    self.assertEqual(db.execute('SELECT origin,revision,license FROM source_links').fetchone(),('example/repo','v1','MIT'))
    self.assertEqual(db.execute('SELECT count(*) FROM knowledge').fetchone()[0],1)
 def test_real_video(self):
  with tempfile.TemporaryDirectory() as d:
   s=[{'duration':.5,'recipe':{'mode':'character2d','character':{'scale':.6}}}]
   m=produce(s,d,fps=8,width=160,height=288)
   self.assertEqual(m['frames'],4)
   self.assertTrue(Path(m['video']).is_file())
if __name__=='__main__':unittest.main()
