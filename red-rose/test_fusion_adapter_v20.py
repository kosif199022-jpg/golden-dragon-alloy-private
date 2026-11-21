"""V20 concrete registry integration and approval tests."""
from contextlib import redirect_stdout
import io,json,shutil,tempfile,unittest
from pathlib import Path
from capability_runtime import REGISTRY,execute,plan_task
from rose import main as rose_main,connect

SCENES=[{'kind':'clay','title':'قطة','duration':.25},
        {'kind':'map','title':'رحلة','duration':.25,'from':[39.2,21.5],'to':[46.7,24.7]}]

class FusionAdapterTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.db=connect(self.root/'local.sqlite3')
        self.addCleanup(self.db.close)
    def test_five_adapters_registered(self):
        for name in ('fusion.route','fusion.plan','fusion.frame','fusion.render','media.iphone_export'):
            self.assertIn(name,REGISTRY)
        self.assertEqual(REGISTRY['fusion.render'][1],'write')
        self.assertEqual(REGISTRY['media.iphone_export'][1],'write')
    def test_read_actions_have_no_file_effect(self):
        before={p.name for p in self.root.iterdir()}
        a=execute(self.db,'fusion.route',{'from':[39.2,21.5],'to':[46.7,24.7]})
        self.assertTrue(a['result']['distance_km']>500)
        b=execute(self.db,'fusion.plan',{'scenes':SCENES,'fps':12})
        self.assertEqual(b['status'],'executed')
        c=execute(self.db,'fusion.frame',{'scenes':SCENES,'fps':12,'frame':3})
        self.assertIn('<svg',c['result']['svg'])
        self.assertEqual(before,{p.name for p in self.root.iterdir()})
    def test_write_approval_gate(self):
        dest=self.root/'output.mp4'
        for name,params in [('fusion.render',{'scenes':SCENES,'fps':12,'output':str(dest)}),
                            ('media.iphone_export',{'source':str(dest),'output':str(self.root/'other.mp4')})]:
            r=execute(self.db,name,params)
            self.assertEqual(r['status'],'approval_required')
        self.assertFalse(dest.exists())
    def test_injection_keys_rejected(self):
        with self.assertRaisesRegex(ValueError,'unknown parameters'):
            execute(self.db,'fusion.plan',{'scenes':SCENES,'shell':'cat ~/.ssh/id_rsa'})
    def test_planner_arabic_route_clay_iphone(self):
        r=plan_task(self.db,'خريطة صلصال آيفون')
        self.assertIn('fusion.route',r['suggested_native_adapters'])
        self.assertIn('fusion.render',r['suggested_native_adapters'])
        self.assertIn('media.iphone_export',r['suggested_native_adapters'])
    @unittest.skipUnless(shutil.which('ffmpeg'),'FFmpeg missing')
    def test_real_approved_production_with_qa(self):
        dest=self.root/'combined.mp4'
        r=execute(self.db,'fusion.render',{'scenes':SCENES,'fps':12,'preset':'iphone-vertical','output':str(dest)},approve_write=True)
        self.assertTrue(dest.exists())
        self.assertTrue(r['result']['qa']['passed'])
        self.assertFalse(r['legacy_runtime_called'])
    def test_cli_plan(self):
        src=self.root/'scenes.json'
        src.write_text(json.dumps(SCENES),encoding='utf-8')
        capture=io.StringIO()
        with redirect_stdout(capture):
            rose_main(['--db',str(self.root/'local.sqlite3'),'fusion-plan',str(src),'--fps','12'])
        self.assertEqual(json.loads(capture.getvalue())['capability'],'fusion.plan')

if __name__=='__main__':unittest.main()
