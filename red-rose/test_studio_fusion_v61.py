import unittest,tempfile,sqlite3
from pathlib import Path
from studio_fusion_v61 import shot_contract,motion_curve,catalog,words
def job():
    return {"identity":"Nour, reference cartoon","setting":"Alexandria beach","style":"3D family cartoon","camera":"slow dolly","duration":8,"fps":30,"reference_required":True,"reference_id":"nour-reference.png","beats":[{"seconds":4,"action":"looks at sea","speaker":"Nour","dialogue":"بحرنا جميل لازم نحافظ عليه"},{"seconds":4,"action":"smiles"}]}
class StudioFusionTests(unittest.TestCase):
    def test_shot(self):
        r=shot_contract(job());self.assertEqual(r["status"],"plan_ready");self.assertEqual(r["frames"],240);self.assertIn("بحرنا جميل لازم نحافظ عليه",r["prompt"]);self.assertFalse(r["actual_lip_sync_verified"])
    def test_speech(self):
        j=job();j["beats"][0]["dialogue"]="كلمة "*30;r=shot_contract(j);self.assertEqual(r["issues"][0]["code"],"speech_budget_exceeded");self.assertIsNone(r["prompt"])
    def test_missing_reference(self):
        j=job();j.pop("reference_id");self.assertEqual(shot_contract(j)["issues"][0]["code"],"missing_reference")
    def test_duration(self):
        j=job();j["duration"]=10
        with self.assertRaises(ValueError):shot_contract(j)
    def test_frame_mismatch(self):
        j=job();j["beats"][1]["seconds"]=3;self.assertEqual(shot_contract(j)["issues"][0]["code"],"timeline_duration_mismatch")
    def test_dua_gate(self):
        j=job();j["kind"]="dua";self.assertEqual(shot_contract(j)["issues"][0]["code"],"dua_requires_existing_mandatory_source_gate")
    def test_diacritics(self):
        self.assertEqual(words('حُبّ جَمِيلٌ'),2)
    def test_arabic_dua_gate(self):
        j=job();j['kind']='ريل دعاء';self.assertEqual(shot_contract(j)['issues'][0]['code'],'dua_requires_existing_mandatory_source_gate')
    def test_curve(self):
        j={"frames":5,"keyframes":[{"frame":0,"value":0,"ease":"smooth"},{"frame":4,"value":100}]}
        self.assertEqual(motion_curve(j)["values"],[0,15.625,50,84.375,100]);self.assertEqual(motion_curve(j),motion_curve(j))
    def test_curve_boundary(self):
        j={"frames":6,"keyframes":[{"frame":0,"value":0},{"frame":3,"value":5},{"frame":5,"value":1}]};r=motion_curve(j);self.assertEqual(r["values"][3],5);self.assertEqual(r["values"][-1],1)
    def test_invalid_curve(self):
        with self.assertRaises(ValueError):motion_curve({"frames":3,"keyframes":[{"frame":0,"value":0},{"frame":0,"value":1}]})
    def test_literal_search(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"i.db";db=sqlite3.connect(p);db.execute("CREATE TABLE docs(path,digest,size,category,license,status)");db.execute("INSERT INTO docs VALUES('foo_1/SKILL.md','abc',12,'media',NULL,'reference_only')");db.commit();db.close()
            self.assertEqual(len(catalog("foo_1",path=p)["matches"]),1);self.assertEqual(len(catalog("%",path=p)["matches"]),0)
if __name__=="__main__":unittest.main()
