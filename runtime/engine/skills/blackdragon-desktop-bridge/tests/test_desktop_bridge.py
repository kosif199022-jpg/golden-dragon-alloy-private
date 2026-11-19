import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stdout,redirect_stderr
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "bridge.py"
spec = importlib.util.spec_from_file_location("bd_bridge", SCRIPT)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class TestBridge(unittest.TestCase):
    def run_main(self, argv, env=None):
        out, err=io.StringIO(),io.StringIO()
        with redirect_stdout(out),redirect_stderr(err):
            rc=m.main(argv,env if env is not None else {})
        return rc,out.getvalue(),err.getvalue()

    def test_catalog_exists(self):
        rc,output,_=self.run_main(["catalog"]);self.assertEqual(rc,0)
        cat=json.loads(output);self.assertIn("voice",cat["existing_groups"])
        self.assertIn("computer",cat["read_only_allowlist"])

    def test_doctor_does_not_print_secret(self):
        env={"BD_TOKEN":"SECRET" ,"BD_SID":"SESSION", "BD_PORT":"47821"}
        rc,out,_=self.run_main(["doctor"],env)
        self.assertEqual(rc,0);self.assertNotIn("SECRET",out);self.assertNotIn("SESSION",out)

    def test_default_denies_live_call(self):
        with patch.object(m,"_request") as request:
            rc,_,_=self.run_main(["read","system","info"])
            self.assertEqual(rc,3);request.assert_not_called()

    def test_deny_write_even_with_confirmation(self):
        with patch.object(m,"_request") as request:
            rc,_,_=self.run_main(["read","system","shutdown","--confirm-local-read"])
            self.assertEqual(rc,3);request.assert_not_called()

    def test_deny_browser_click(self):
        with patch.object(m,"_request") as request:
            rc,_,_=self.run_main(["read","browser","click","--confirm-local-read"])
            self.assertEqual(rc,3);request.assert_not_called()

    def test_no_token_no_session(self):
        with self.assertRaises(ValueError):m._request("system","info",{},env={})

    def test_bad_port(self):
        with self.assertRaises(ValueError):m._request("system","info",{},env={"BD_TOKEN":"t","BD_SID":"s","BD_PORT":"80/../../"})

    def test_no_proxy_network_mock(self):
        class Response:
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def read(self,n):return b'{"content": []}'
        class Opener:
            def open(self,req,timeout):
                self.req=req;return Response()
        o=Opener()
        with patch.object(m.urllib.request,"build_opener",return_value=o):
            r=m._request("system","info",{},env={"BD_TOKEN":"secret","BD_SID":"sid","BD_PORT":"47821"})
        self.assertEqual(r,{"content": []})
        self.assertTrue(o.req.full_url.startswith("http://127.0.0.1:47821/control?"))

    def test_summary_private_text_omitted(self):
        d=m._safe_summary({"content":[{"type":"text","text":"PASSWORD=SECRET private"}]})
        self.assertNotIn("SECRET",repr(d))

    def test_malformed_screenshot_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            with self.assertRaises(ValueError):m._save_image({"content":[{"type":"image","mime":"image/png","data":"aGVsbG8="}]},Path(t)/"x.png")

    def test_screenshot_saved_without_overwrite(self):
        import base64
        png=b"\x89PNG\r\n\x1a\n"+b"abcde"*20
        # valid test signature; validates envelope, not actual PNG decoding
        data={"content":[{"type":"image","mime":"image/png","data":base64.b64encode(png).decode()}]}
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/"shot.png";r=m._save_image(data,p);self.assertEqual(r["bytes"],len(png));self.assertEqual(p.read_bytes(),png)
            with self.assertRaises(FileExistsError):m._save_image(data,p)

    def test_empty_screenshot_rejected(self):
        with self.assertRaises(ValueError):m._save_image({"content":[]},"shot.jpg")

    def test_refuse_write_from_low_level(self):
        with self.assertRaises(ValueError):m._request("computer","click",{},env={"BD_TOKEN":"t","BD_SID":"s"})

    def test_live_fake_read_sanitized(self):
        with patch.object(m,"_request",return_value={"content":[{"type":"text","text":"secret in page"}]}):
            rc,out,_=self.run_main(["read","browser","read","--confirm-local-read"],{"BD_TOKEN":"t","BD_SID":"s"})
            self.assertEqual(rc,0);self.assertNotIn("secret in page",out)

if __name__=="__main__":unittest.main()
