import tempfile,unittest,zipfile,hashlib,stat
from pathlib import Path
from unittest.mock import patch
from rose_source_preflight_v60 import inspect,compare,header_kind

class SourcePreflightTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
    def archive(self,name,entries):
        p=self.root/name
        with zipfile.ZipFile(p,"w") as z:
            for k,v in entries:z.writestr(k,v)
        return p
    def test_mislabeled_zip(self):
        p=self.archive("video.mp4",[("readme.txt","not video")]);r=inspect(p,"mp4")
        self.assertEqual(r["kind"],"zip");self.assertEqual(r["disposition"],"blocked")
    def test_apk_manifest_identity(self):
        p=self.archive("frontrow.apk",[("AndroidManifest.xml",b"manifest"),("classes.dex",b"dex")])
        with patch("rose_source_preflight_v60.apk_identity",return_value={"status":"parsed_manifest","package":"com.example.store"}):
            r=inspect(p,"apk","com.example.editor");self.assertEqual(r["disposition"],"blocked")
            r=inspect(p,"apk","com.example.store");self.assertEqual(r["disposition"],"identity_candidate")
            self.assertFalse(r["authenticity_verified"]);self.assertFalse(r["safe_to_execute"])
    def test_apk_parse_failure(self):
        p=self.archive("fake.apk",[("AndroidManifest.xml",b"manifest"),("classes.dex",b"dex")])
        with patch("rose_source_preflight_v60.apk_identity",return_value={"status":"parser_failed"}):
            self.assertEqual(inspect(p)["disposition"],"blocked")
    def test_extension_only_apk(self):
        p=self.archive("fake.apk",[("notes.txt","no manifest")])
        self.assertEqual(inspect(p)["disposition"],"blocked")
    def test_traversal(self):
        p=self.archive("bad.zip",[("../escape.txt","x"),("C:/x","y")])
        self.assertIn("unsafe_member_name",inspect(p)["issues"])
    def test_case_collision(self):
        p=self.archive("bad.zip",[("Foo.txt","x"),("foo.txt","y")])
        self.assertIn("duplicate_normalized_member",inspect(p)["issues"])
    def test_symlink(self):
        z=zipfile.ZipInfo("link");z.create_system=3;z.external_attr=(stat.S_IFLNK|0o777)<<16
        p=self.archive("bad.zip",[(z,"../secret")]);self.assertIn("symlink_member",inspect(p)["issues"])
    def test_unknown(self):
        p=self.root/"a";p.write_bytes(b"nothing")
        self.assertEqual(inspect(p)["disposition"],"unresolved")
    def test_digest(self):
        p=self.archive("a.zip",[("x","ok")]);r=inspect(p,expected_sha256="a"*64)
        self.assertIn("expected_digest_mismatch",r["issues"])
        self.assertEqual(r["sha256"],hashlib.sha256(p.read_bytes()).hexdigest())
    def test_media_header_not_verified(self):
        p=self.root/"movie.mp4";p.write_bytes(b"\x00\x00\x00\x18ftypisom")
        r=inspect(p);self.assertEqual(r["kind"],"mp4");self.assertFalse(r["content_integrity_verified"])
    def test_office(self):
        p=self.archive("a.docx",[("[Content_Types].xml","x"),("word/document.xml","y")]);self.assertEqual(inspect(p)["kind"],"office")
    def record(self,fam,digest,value="same",status="observed"):
        return {"method_family":fam,"status":status,"value":value,"input_sha256":"a"*64,"evidence_sha256":digest*64}
    def test_agreement(self):
        r=compare([self.record("one","b"),self.record("two","c")],"a"*64)
        self.assertEqual(r["decision"],"corroboration_candidate");self.assertFalse(r["semantic_verified"])
    def test_duplicate_tools(self):
        r=compare([self.record("one","b"),self.record("one","c")],"a"*64)
        self.assertEqual(r["decision"],"review_required")
    def test_failed_not_pass(self):
        r=compare([self.record("one","b"),self.record("two","c",status="failed")],"a"*64)
        self.assertEqual(r["decision"],"review_required")
    def test_conflict(self):
        r=compare([self.record("one","b"),self.record("two","c","different")],"a"*64)
        self.assertTrue(r["conflict"]);self.assertEqual(r["decision"],"review_required")
    def test_wrong_input(self):
        with self.assertRaises(ValueError):compare([self.record("one","b"),self.record("two","c")],"d"*64)
if __name__=="__main__":unittest.main()
