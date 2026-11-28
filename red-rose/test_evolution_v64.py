import unittest,tempfile,hashlib,json,sqlite3
from pathlib import Path
from rose_evolution_v64 import record,review,recall,status,corpus_find,fold
class Evolution(unittest.TestCase):
 def setUp(self):
    self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.p=Path(self.tmp.name);self.db=self.p/"memory.db"
 def item(self,i=1,scope="studio"):
    name=f"test{i}.txt";p=self.p/name;p.write_text("checked "+str(i))
    return {"domain":"media","scope":scope,"trigger":"فحص الرندر والحركة","action":"check decoded frames","run_id":"run"+str(i),"outcome":"pass","workspace":str(self.p),"evidence":[{"file":name,"sha256":hashlib.sha256(p.read_bytes()).hexdigest()}]}
 def approve(self,key):
    return review({"lesson_id":key,"reviewer":"owner","reason":"reviewed both runs","decision":"approve"},self.db,True)
 def test_missing_read_does_not_create(self):
    self.assertFalse(status(self.db)["database_present"]);self.assertFalse(self.db.exists())
 def test_approval(self):
    with self.assertRaises(PermissionError):record(self.item(),self.db)
    self.assertFalse(self.db.exists())
 def test_bad_digest(self):
    j=self.item();j["evidence"][0]["sha256"]="x"
    with self.assertRaises(ValueError):record(j,self.db,True)
 def test_path(self):
    j=self.item();j["evidence"][0]["file"]="../elsewhere"
    with self.assertRaises(ValueError):record(j,self.db,True)
 def test_dedup_and_promotion(self):
    j=self.item();a=record(j,self.db,True);self.assertTrue(record(j,self.db,True)["duplicate"]);self.assertEqual(status(self.db)["observations"],1)
    with self.assertRaises(ValueError):self.approve(a["lesson_id"])
    self.assertEqual(recall("الرندر",scope="studio",dbpath=self.db)["matches"],[])
    b=record(self.item(2),self.db,True);self.assertEqual(a["lesson_id"],b["lesson_id"]);self.approve(a["lesson_id"])
    self.assertEqual(len(recall("الرندر",scope="studio",dom="media",dbpath=self.db)["matches"]),1)
    self.assertEqual(recall("الرندر",scope="other",dbpath=self.db)["matches"],[])
 def test_same_evidence(self):
    j=self.item();a=record(j,self.db,True);j["run_id"]="run2";record(j,self.db,True)
    with self.assertRaises(ValueError):self.approve(a["lesson_id"])
 def test_changed_run(self):
    j=self.item();record(j,self.db,True);j["outcome"]="fail"
    with self.assertRaises(ValueError):record(j,self.db,True)
 def test_new_failure_requires_review(self):
    a=record(self.item(),self.db,True);record(self.item(2),self.db,True);self.approve(a['lesson_id']);j=self.item(3);j['outcome']='fail';record(j,self.db,True);self.assertEqual(recall('الرندر',scope='studio',dbpath=self.db)['matches'],[])
 def test_retire(self):
    a=record(self.item(),self.db,True);record(self.item(2),self.db,True);self.approve(a["lesson_id"])
    review({"lesson_id":a["lesson_id"],"reviewer":"owner","reason":"obsolete","decision":"retire"},self.db,True)
    self.assertEqual(recall("الرندر",scope="studio",dbpath=self.db)["matches"],[])
 def test_secrets(self):
    j=self.item();j["action"]="password=demo"
    with self.assertRaises(ValueError):record(j,self.db,True)
 def test_corpus(self):
    p=self.p/"corpus.db";db=sqlite3.connect(p);db.execute("CREATE TABLE docs(archive,path,digest,words,tags,license_label)")
    for archive in ("one","two"):db.execute("INSERT INTO docs VALUES(?,?,?,?,?,?)",(archive,"video/SKILL.md","same",100,'{"media":3}',None))
    db.commit();db.close()
    self.assertEqual(len(corpus_find("video","media",path=p)["matches"]),1);self.assertEqual(corpus_find("%",path=p)["matches"],[])
if __name__=="__main__":unittest.main()
