import unittest,tempfile,sqlite3,zipfile,json,hashlib
from pathlib import Path
from rose_knowledge_v67 import build,search,inspect,adoption,context
class Knowledge67(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory();self.addCleanup(self.t.cleanup);self.p=Path(self.t.name);(self.p/"sources").mkdir()
  self.raw=b"# Video\nAlways verify decoded frame count before export."
  self.d=hashlib.sha256(self.raw).hexdigest();z=self.p/"sources"/"tiny.zip"
  with zipfile.ZipFile(z,"w") as f:f.writestr("ffmpeg/SKILL.md",self.raw)
  (self.p/"manifest.json").write_text(json.dumps({"sources":[{"archive":"tiny.zip","sha256":hashlib.sha256(z.read_bytes()).hexdigest()}]}))
  self.base=self.p/"base.db";self.idx=self.p/"search.db"
  db=sqlite3.connect(self.base);db.execute("CREATE TABLE candidates(digest,status,line,section,excerpt)");db.execute("CREATE TABLE sources(digest,archive,path,tags)")
  db.execute("INSERT INTO candidates VALUES(?,?,?,?,?)",(self.d,"candidate",2,"Video","Always verify decoded frame count before export."))
  for n in ("ffmpeg/SKILL.md","copy/SKILL.md"):db.execute("INSERT INTO sources VALUES(?,?,?,?)",(self.d,"tiny.zip",n,'{"media":1}'))
  db.execute("UPDATE sources SET path='zcopy/SKILL.md' WHERE path='copy/SKILL.md'");db.commit();db.close()
 def test_build_approval(self):
  with self.assertRaises(PermissionError):build(self.base,self.idx)
  self.assertFalse(self.idx.exists())
 def test_rank_dedup(self):
  self.assertEqual(build(self.base,self.idx,True)["indexed_unique_candidates"],1)
  r=search("frame",path=self.idx,feature="media");self.assertEqual(len(r["matches"]),1);self.assertFalse(r["execution_allowed"]);self.assertNotIn("excerpt",r["matches"][0])
  self.assertEqual(search("frame",path=self.idx,feature="finance")["matches"],[])
  self.assertEqual(search('" OR *',path=self.idx)["matches"],[])
 def test_inspect(self):
  r=inspect(self.d,self.p,self.base);self.assertTrue(r["source_verified"]);self.assertEqual(r["source_context"][1]["line"],2)
  self.assertFalse(r["instruction_authority"])
 def test_archive_changed(self):
  with (self.p/"sources"/"tiny.zip").open("ab") as f:f.write(b"changed")
  with self.assertRaises(ValueError):inspect(self.d,self.p,self.base)
 def test_adoption(self):
  j=dict(source_sha256=self.d,problem="frame loss",mechanism="count decoded frames",preconditions="local video",implementation="independent probe",acceptance="exact count",counterexample="VFR",rights="unknown")
  self.assertEqual(len(adoption(j)["blockers"]),4)
  j.update(rights="independent_implementation",source_context_reviewed=True,existing_capability_checked=True,test_plan_reviewed=True)
  self.assertEqual(adoption(j)["status"],"ready_for_human_review");self.assertFalse(adoption(j)["promoted"])
 def test_context(self):
  build(self.base,self.idx,True);self.assertFalse(context("مونتاج",1,self.idx)["enabled"]);r=context("مونتاج",2,self.idx);self.assertEqual(len(r["matches"]),1);self.assertFalse(r["instruction_authority"])
if __name__=="__main__":unittest.main()
