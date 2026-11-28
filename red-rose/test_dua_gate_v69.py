import unittest, tempfile, json, subprocess, sys, shutil, copy
from pathlib import Path
from unittest.mock import patch
import rose_dua_gate_v69 as g
import dua_reel_v34 as v34
import rose_montage_v65 as montage
class DuaGate69(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory();self.addCleanup(self.t.cleanup)
  self.p=Path(self.t.name).resolve();self.v=self.p/"videos";self.f=self.p/"fonts";self.v.mkdir();self.f.mkdir()
  self.patch=patch.object(g,"roots",return_value=(self.v,self.f));self.patch.start();self.addCleanup(self.patch.stop)
  self.probe=patch.object(g,"duration",return_value=10.);self.probe.start();self.addCleanup(self.probe.stop)
  self.glyph=patch.object(g,"fast_glyph_check");self.glyph_mock=self.glyph.start();self.addCleanup(self.glyph.stop)
  self.clip=self.v/"clip.mp4";self.clip.write_bytes(b"synthetic video fixture")
  self.audio=self.p/"voice.m4a";self.audio.write_bytes(b"synthetic audio fixture")
  self.timing=self.p/"words.json"
  self.words=[{"text":"اللهم","start":.2,"end":.7},{"text":"ارحمنا","start":.8,"end":1.2},{"text":"يا","start":1.45,"end":1.7},{"text":"رب","start":1.8,"end":2.3}]
  self.timing.write_text(json.dumps({"audio_sha256":g.sha(self.audio),"method":"manual_audio_alignment","words":self.words}),encoding="utf-8")
  self.fonts={}
  for k in ("line","calligraphy","title","latin"):
   f=self.f/(k+".ttf");f.write_bytes(k.encode());self.fonts[k]=self.asset(f)
  self.job={"kind":"dua","clips":[{**self.asset(self.clip),"start":.3,"end":3.3}],"fonts":self.fonts,"audio":self.asset(self.audio),"word_timing":self.asset(self.timing),"captions":[{"text":"اللهم ارحمنا يا رب","start":.2,"end":2.3,"word_start":0,"word_end":4}]}
 def asset(self,p):return {"file":str(p),"sha256":g.sha(p)}
 def test_valid(self):
  r=g.check(self.job);self.assertTrue(r["ok"]);self.assertFalse(r["audio_alignment_independently_verified"])
 def test_external_video(self):
  p=self.p/"outside.mp4";shutil.copyfile(self.clip,p);self.job["clips"][0].update(self.asset(p))
  with self.assertRaisesRegex(ValueError,"outside approved"):g.check(self.job)
 def test_missing_digest(self):
  del self.job["clips"][0]["sha256"]
  with self.assertRaises(KeyError):g.check(self.job)
 def test_changed_video(self):
  self.clip.write_bytes(b"changed")
  with self.assertRaisesRegex(ValueError,"SHA-256"):g.check(self.job)
 def test_external_font(self):
  p=self.p/"foreign.ttf";p.write_bytes(b"x");self.job["fonts"]["line"]=self.asset(p)
  with self.assertRaisesRegex(ValueError,"outside approved"):g.check(self.job)
 def test_font_digest(self):
  Path(self.fonts["line"]["file"]).write_bytes(b"changed")
  with self.assertRaisesRegex(ValueError,"SHA-256"):g.check(self.job)
 def test_missing_trim(self):
  del self.job["clips"][0]["end"]
  with self.assertRaises(KeyError):g.check(self.job)
 def test_trim_bounds(self):
  self.job["clips"][0]["end"]=10.5
  with self.assertRaisesRegex(ValueError,"trim"):g.check(self.job)
 def replace_words(self,words,method="manual_audio_alignment",audio_sha=None):
  self.timing.write_text(json.dumps({"audio_sha256":audio_sha or g.sha(self.audio),"method":method,"words":words}),encoding="utf-8");self.job["word_timing"]=self.asset(self.timing)
 def test_uniform(self):
  w=[dict(text=x["text"],start=i*.5,end=(i+1)*.5) for i,x in enumerate(self.words)]
  self.replace_words(w)
  with self.assertRaisesRegex(ValueError,"uniform"):g.check(self.job)
 def test_guessed_method(self):
  self.replace_words(self.words,"equal_split")
  with self.assertRaisesRegex(ValueError,"provenance"):g.check(self.job)
 def test_wrong_audio(self):
  self.replace_words(self.words,audio_sha="0"*64)
  with self.assertRaisesRegex(ValueError,"another audio"):g.check(self.job)
 def test_wrong_caption_time(self):
  self.job["captions"][0]["end"]=2.4
  with self.assertRaisesRegex(ValueError,"timestamps"):g.check(self.job)
 def test_wrong_caption_text(self):
  self.job["captions"][0]["text"]="different"
  with self.assertRaisesRegex(ValueError,"text"):g.check(self.job)
 def test_incomplete_word_range(self):
  self.job["captions"][0].update(word_end=2,text="اللهم ارحمنا",end=1.2)
  with self.assertRaisesRegex(ValueError,"unmapped"):g.check(self.job)
 def v34_plan(self):
  # Actual one-line shot length is last word end + .35 s.
  self.job["clips"][0]["end"]=.3+2.65
  return {"dua_gate":self.job,"clips":[dict(self.job["clips"][0],kind="video")],"fonts":{k:v["file"] for k,v in self.fonts.items()},"audio":str(self.audio),"lines":[{"text":self.job["captions"][0]["text"],"t0":.2,"t1":2.3}]}
 def test_v34_positive_preflight(self):
  p=self.v34_plan();r=v34.build(p,self.p/"result.mp4",approve_write=False)
  self.assertEqual(r["outcome"],"approval_required");self.assertFalse((self.p/"result_work").exists())
 def test_v34_reject_before_write(self):
  p=self.v34_plan();p["clips"][0]["start"]=.4
  with self.assertRaisesRegex(ValueError,"trim"):v34.build(p,self.p/"result.mp4",approve_write=True)
  self.assertFalse((self.p/"result_work").exists())
 def test_v34_missing_gate(self):
  p=self.v34_plan();del p["dua_gate"]
  with self.assertRaises(KeyError):v34.build(p,self.p/"result.mp4",approve_write=True)
  self.assertFalse((self.p/"result_work").exists())
 def test_montage_still_blocks_dua(self):
  with self.assertRaisesRegex(ValueError,"general"):montage.plan({"kind":"dua","dua_gate":self.job})
  with self.assertRaisesRegex(ValueError,"contract"):montage.plan({"kind":"general","dua_gate":self.job})
 def fast_job(self):
  for n in g.FAST_FONTS:
   p=self.f/n;p.write_bytes(n.encode())
  self.job["fonts"]={n:self.asset(self.f/n) for n in g.FAST_FONTS}
  self.job["clips"][0]["end"]=.3+3+.2
  spec={"style":"dxh","dur":3.,"scenes":[{"a":0,"b":3,"ss":.3}],"lines":[[.2,self.job["captions"][0]["text"]]],"dua_gate":self.job}
  (self.p/"spec.json").write_text(json.dumps(spec),encoding="utf-8");(self.p/"sel.txt").write_text(str(self.clip),encoding="utf-8")
  return spec
 def test_fast_bind(self):
  self.fast_job();self.assertTrue(g.bind_fast(self.p)["ok"])
 def test_fast_glyph_refusal(self):
  self.fast_job();self.glyph_mock.side_effect=ValueError("unregistered font fallback")
  with self.assertRaisesRegex(ValueError,"fallback"):g.bind_fast(self.p)
 def test_real_synthetic_cmap(self):
  try:
   from fontTools.fontBuilder import FontBuilder
   from fontTools.pens.ttGlyphPen import TTGlyphPen
  except ImportError:self.skipTest("fontTools not installed")
  self.glyph.stop()
  f=self.f/"minimal.ttf";fb=FontBuilder(1000,isTTF=True)
  glyphs=[".notdef","A","space"];fb.setupGlyphOrder(glyphs);fb.setupCharacterMap({65:"A",32:"space"})
  fb.setupGlyf({n:TTGlyphPen(None).glyph() for n in glyphs})
  fb.setupHorizontalMetrics({n:(500,0) for n in glyphs});fb.setupHorizontalHeader(ascent=800,descent=-200)
  fb.setupNameTable({"familyName":"V69 synthetic","styleName":"Regular"})
  fb.setupOS2(sTypoAscender=800,sTypoDescender=-200,usWinAscent=800,usWinDescent=200);fb.setupPost();fb.save(f)
  spec={"style":"dxh","noHandle":True};job={"captions":[{"text":"A"}],"fonts":{"Amiri-Bold.ttf":str(f)}}
  g.fast_glyph_check(spec,job);job["captions"][0]["text"]="B"
  with self.assertRaisesRegex(ValueError,"fallback"):g.fast_glyph_check(spec,job)
 def test_fast_reject_implicit_trim(self):
  s=self.fast_job();del s["scenes"][0]["ss"];(self.p/"spec.json").write_text(json.dumps(s),encoding="utf-8")
  with self.assertRaises(KeyError):g.bind_fast(self.p)
 def test_fast_prepared_tamper(self):
  self.fast_job();g.stage_fast(self.p);web=self.p/"web"
  for n in ("index.html","main.js"):shutil.copyfile(Path(g.__file__).parent/"agent"/"fast_reel"/"web"/n,web/n)
  (web/"clips.json").write_text(json.dumps({"clips":[{"src":self.clip.name,"frames":96}]}),encoding="utf-8")
  p=web/"fx"/"c00"/"0001.jpg";p.parent.mkdir(parents=True)
  for i in range(1,97):(p.parent/f"{i:04d}.jpg").write_bytes(b"fixture")
  g.prepared_fast(self.p,seal=True);self.assertTrue(g.prepared_fast(self.p)["ok"])
  p.write_bytes(b"modified")
  with self.assertRaisesRegex(ValueError,"changed"):g.prepared_fast(self.p)
 def test_vn_render_preflight(self):
  import vn_dua_v47
  from types import SimpleNamespace
  from contextlib import redirect_stdout
  from io import StringIO
  j=self.p/"job.json";j.write_text(json.dumps(self.job),encoding="utf-8")
  with redirect_stdout(StringIO()) as f:
   self.assertEqual(vn_dua_v47.handler(SimpleNamespace(render_job=str(j))),0)
  self.assertFalse(json.loads(f.getvalue())["rendered"])
  del self.job["clips"][0]["end"];j.write_text(json.dumps(self.job),encoding="utf-8")
  with redirect_stdout(StringIO()):self.assertEqual(vn_dua_v47.handler(SimpleNamespace(render_job=str(j))),1)
 def test_cli_refuses_bad_job(self):
  j=self.p/"bad.json";j.write_text('{"kind":"dua"}',encoding="utf-8")
  proc=subprocess.run([sys.executable,"-X","utf8",str(Path(g.__file__).parent/"rose.py"),"dua-gate","check",str(j)],capture_output=True,timeout=30)
  self.assertEqual(proc.returncode,1);self.assertFalse(json.loads(proc.stdout)["ok"])
 @unittest.skipUnless(shutil.which("node"),"node required")
 def test_direct_fast_refuses_before_output(self):
  web=self.p/"web";web.mkdir()
  proc=subprocess.run(["node",str(Path(g.__file__).parent/"agent"/"fast_reel"/"render.mjs"),str(web),str(self.p/"frames"),"0"],capture_output=True,timeout=30)
  self.assertNotEqual(proc.returncode,0);self.assertIn(b"dua-gate",proc.stderr);self.assertFalse((self.p/"frames").exists())
 @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),"media tools required")
 def test_real_media_duration(self):
  # No private media or fonts used. Real synthetic MP4/AAC; font bytes remain hash fixtures.
  self.probe.stop()
  subprocess.run(["ffmpeg","-v","error","-y","-f","lavfi","-i","color=red:size=64x96:rate=30:duration=4","-c:v","libx264","-pix_fmt","yuv420p",str(self.clip)],check=True,capture_output=True,timeout=30)
  subprocess.run(["ffmpeg","-v","error","-y","-f","lavfi","-i","sine=frequency=400:duration=4","-c:a","aac",str(self.audio)],check=True,capture_output=True,timeout=30)
  self.job["clips"][0].update(self.asset(self.clip));self.job["audio"]=self.asset(self.audio);self.replace_words(self.words)
  self.assertTrue(g.check(self.job)["ok"])
  self.job["clips"][0]["end"]=5.
  with self.assertRaisesRegex(ValueError,"trim"):g.check(self.job)
if __name__=="__main__":unittest.main()
