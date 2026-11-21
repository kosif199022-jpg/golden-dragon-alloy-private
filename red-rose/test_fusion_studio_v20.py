"""Original, safe V20 media fusion engine tests (no source runtime imports)."""
import unittest,tempfile,json,math,subprocess,shutil
from pathlib import Path
from fusion_studio_v20 import greatcircle,plan,frame_svg,render_video,iphone_export

class FusionV20Tests(unittest.TestCase):
    def example(self):
        return [{'kind':'clay','title':'قطة تنقذ صديقها','duration':.5},
                {'kind':'map','title':'رحلة','duration':.5,'from':[39.19,21.49],'to':[46.67,24.71]}]
    def test_greatcircle_endpoints_and_distance(self):
        r=greatcircle([39.19,21.49],[46.67,24.71],41)
        self.assertEqual(len(r['coordinates']),41)
        self.assertEqual(r['coordinates'][0],[39.19,21.49])
        self.assertTrue(700<r['distance_km']<1000)
    def test_route_dateline(self):
        r=greatcircle([179,0],[-179,0],11)
        self.assertAlmostEqual(r['distance_km'],222.39,delta=1)
    def test_route_reject_bad(self):
        for a,b in [([190,1],[3,4]),([1],[2,3]),([0,0],[180,0])]:
            with self.assertRaises(ValueError):greatcircle(a,b)
    def test_timeline_frame_totals(self):
        r=plan(self.example(),fps=12)
        self.assertEqual(r['frames'],12)
        self.assertEqual(r['scenes'][1]['start_frame'],6)
    def test_reject_unknown_scene_fields_and_preset(self):
        with self.assertRaises(ValueError):plan([dict(self.example()[0],unexpected=True)])
        with self.assertRaises(ValueError):plan(self.example(),preset='arbitrary')
    def test_svg_is_stable_escaped(self):
        p=plan([{'kind':'clay','title':'<script>bad</script>','duration':.5}],fps=12)
        a=frame_svg(p,0)
        self.assertIn('&lt;script&gt;',a)
        self.assertNotIn('<script>',a)
        self.assertEqual(a,frame_svg(p,0))
    def test_route_svg(self):
        self.assertIn('SCHEMATIC',frame_svg(plan(self.example(),fps=12),7))
    def test_out_of_bounds(self):
        p=plan(self.example(),fps=12)
        with self.assertRaises(ValueError):frame_svg(p,p['frames'])
    def test_reject_excessive_timeline(self):
        with self.assertRaises(ValueError):plan([{'kind':'clay','duration':12}]*3)
    def test_render_write_gate(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(PermissionError):
                render_video(plan(self.example(),fps=12),Path(d)/'x.mp4')
            self.assertFalse((Path(d)/'x.mp4').exists())
    @unittest.skipUnless(shutil.which('ffmpeg'),'FFmpeg unavailable')
    def test_original_scenes_render(self):
        with tempfile.TemporaryDirectory() as d:
            p=plan(self.example(),fps=12)
            p['width']=270;p['height']=480
            out=Path(d)/'render.mp4'
            result=render_video(p,out,approve_write=True)
            self.assertTrue(out.stat().st_size>2000)
            self.assertEqual(result['frames'],12)
            with self.assertRaises(ValueError):render_video(p,out,approve_write=True)
    @unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'),'FFmpeg unavailable')
    def test_iphone_transcode_and_gate(self):
        with tempfile.TemporaryDirectory() as d:
            source=Path(d)/'source.mp4';out=Path(d)/'iphone.mp4'
            subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i',
                            'color=c=blue:s=160x90:r=12:d=0.5',
                            '-f','lavfi','-i','sine=frequency=450:sample_rate=16000:duration=0.5',
                            '-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac',
                            '-shortest',str(source)],check=True,capture_output=True,timeout=30)
            with self.assertRaises(PermissionError):iphone_export(source,out)
            self.assertFalse(out.exists())
            iphone_export(source,out,approve_write=True,preset='social-square')
            p=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_entries',
                    'stream=codec_type,codec_name,width,height','-of','json',str(out)]))
            video=next(x for x in p['streams'] if x['codec_type']=='video')
            self.assertEqual((video['width'],video['height']),(720,720))
            self.assertTrue(any(x['codec_name']=='aac' for x in p['streams']))
            with self.assertRaises(ValueError):iphone_export(source,out,approve_write=True,preset='social-square')
    def test_export_reject_url(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):
                iphone_export('https://example.com/video.mp4',Path(d)/'new.mp4',approve_write=True)

if __name__=='__main__':unittest.main()
