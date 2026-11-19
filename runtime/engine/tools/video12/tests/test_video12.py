"""Offline regression suite for the Black Dragon 12-tool integration."""
import importlib.util
from pathlib import Path
import unittest

HOME=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('video12', HOME/'video12.py')
video12=importlib.util.module_from_spec(spec)
spec.loader.exec_module(video12)

class TestVideo12(unittest.TestCase):
    def test_twelve_unique_named_tools(self):
        self.assertEqual(len(video12.TOOLS), 12)
        self.assertEqual(set(video12.TOOLS), {'remotion','hyperframes','motion-canvas',
          'threejs','manim','roughjs','gsap','animejs','mojs','whisperx','auto-editor','ffmpeg'})
    def test_plan_selects_and_never_claims_render(self):
        p=video12.plan('فيديو 3D مع تعليق وترجمة وصمت وموشن مرسوم على السبورة')
        self.assertEqual(p['execution_status'],'planning-only')
        self.assertTrue({'threejs','whisperx','auto-editor','roughjs','motion-canvas'}.issubset(set(p['selected'])))
    def test_doctor_all_twelve(self):
        d=video12.doctor();self.assertEqual(d['total_count'],12)
        self.assertEqual(d['detected_count'],sum(x['available'] for x in d['tools']))
        self.assertEqual(d['status'],'dependency-check-only')
    def test_no_silent_install(self):
        class Args:
            node=False;python=False;all=False;yes=False
        self.assertEqual(video12.install(Args()),2)
    def test_no_cli_for_js_library(self):
        self.assertEqual(video12.run_tool('threejs',['--help'],None),2)
    def test_source_links_valid(self):
        for t in video12.TOOLS.values():
            self.assertTrue(t['url'].startswith('https://'))
            self.assertTrue(t['packages'])
    def test_run_needs_arguments(self):
        self.assertEqual(video12.run_tool('ffmpeg', [], None),2)

if __name__=='__main__':unittest.main()
