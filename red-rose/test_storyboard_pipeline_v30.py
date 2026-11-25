"""V30 end-to-end: V29 planner to V20 verified MP4 with approval and fidelity gates."""
from __future__ import annotations

import json
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

from storyboard_pipeline_v30 import OPS, EFFECTS, compile_storyboard, run
from capability_runtime import REGISTRY, execute
from verify_media import verify_video


def sample_story(**changes):
    story = {"goal":"قصة توضيحية أصلية", "seconds":5, "fps":12,
             "style":"clay", "aspect":"9:16", "language":"ar",
             "assets_rights_confirmed":True,
             "beats":[{"label":"خطاف","caption":"بداية القصة","weight":1},
                      {"label":"نهاية","caption":"رحلة جميلة","weight":1}]}
    story.update(changes)
    return story


class V30BridgeTests(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root=Path(self.folder.name)
        self.db=sqlite3.connect(":memory:")
        self.addCleanup(self.db.close)

    def test_registered_mixed_adapter_whitelist(self):
        self.assertEqual(OPS,("compile","render"))
        self.assertEqual(EFFECTS,{"compile":"read","render":"write"})
        self.assertEqual(REGISTRY["storyboard.pipeline"][1],"mixed")
        self.assertEqual(len(REGISTRY),65)

    def test_compile_frame_exact_without_files(self):
        before={p.name for p in self.root.iterdir()}
        result=execute(self.db,"storyboard.pipeline",
                       {"op":"compile","params":{"story":sample_story()}})
        self.assertEqual(result["status"],"executed")
        self.assertEqual(result["effect"],"read")
        self.assertEqual(result["result"]["native_project"]["frames"],60)
        self.assertEqual(result["result"]["storyboard"]["total_frames"],60)
        self.assertTrue(result["result"]["human_approval_required_to_render"])
        self.assertFalse(result["legacy_runtime_called"])
        self.assertEqual(before,{p.name for p in self.root.iterdir()})

    def test_arabic_original_captions_preserved(self):
        c=compile_storyboard({"story":sample_story()})
        self.assertEqual(c["native_project"]["scenes"][0]["title"],"بداية القصة")
        self.assertEqual(c["storyboard"]["shots"][0]["text_direction"],"rtl")
        self.assertEqual(c["downgrades"],[])

    def test_3d_never_silently_becomes_clay(self):
        with self.assertRaisesRegex(ValueError,"cannot reproduce"):
            compile_storyboard({"story":sample_story(style="3d"),
                                "allow_illustrative_fallback":True})

    def test_other_styles_require_explicit_opt_in_and_disclose(self):
        with self.assertRaisesRegex(ValueError,"Opt into"):
            compile_storyboard({"story":sample_story(style="saas")})
        c=compile_storyboard({"story":sample_story(style="saas"),
                              "allow_illustrative_fallback":True})
        self.assertEqual(len(c["downgrades"]),2)
        self.assertEqual(c["native_project"]["scenes"][0]["kind"],"clay")

    def test_map_requires_routes_and_is_schematic_only(self):
        story=sample_story(style="map")
        with self.assertRaisesRegex(ValueError,"map route required"):
            compile_storyboard({"story":story})
        route={"from":[39.2,21.5],"to":[46.7,24.7]}
        c=compile_storyboard({"story":story,"map_routes":{"1":route,"2":route}})
        self.assertEqual(c["native_project"]["scenes"][0]["kind"],"map")
        self.assertFalse(c["native_project"]["scenes"][0]["route"]["has_geographic_basemap"])

    def test_rejects_unused_route_and_untrusted_keys(self):
        with self.assertRaisesRegex(ValueError,"unused"):
            compile_storyboard({"story":sample_story(),"map_routes":{
                "1":{"from":[39.2,21.5],"to":[46.7,24.7]}}})
        with self.assertRaisesRegex(ValueError,"unknown parameters"):
            compile_storyboard({"story":sample_story(),"execute":"bash"})
        with self.assertRaisesRegex(ValueError,"unknown parameters"):
            execute(self.db,"storyboard.pipeline",{"op":"compile",
                                                   "params":{"story":sample_story(),"command":"rm"}})

    def test_wide_aspect_and_frame_budget_not_supported(self):
        with self.assertRaisesRegex(ValueError,"only supports 9:16"):
            compile_storyboard({"story":sample_story(aspect="16:9")})
        with self.assertRaisesRegex(ValueError,"360 frames"):
            compile_storyboard({"story":sample_story(seconds=31, fps=24)})

    def test_oversize_caption_rejected(self):
        long_caption="أ"*101
        story=sample_story(beats=[{"label":"a","caption":long_caption},
                                  {"label":"b","caption":"نهاية"}])
        with self.assertRaisesRegex(ValueError,"caption limit"):
            compile_storyboard({"story":story})

    def test_approval_cannot_be_supplied_by_untrusted_inner_params(self):
        target=self.root/"unauthorized.mp4"
        r=execute(self.db,"storyboard.pipeline",{"op":"render","params":{
            "story":sample_story(), "output":str(target), "approve_write":True}})
        self.assertEqual(r["status"],"approval_required")
        self.assertFalse(target.exists())
        with self.assertRaises(PermissionError):
            run("render",{"story":sample_story(),"output":str(target)})
        self.assertFalse(target.exists())

    def test_does_not_overwrite_existing_file_or_symlink(self):
        target=self.root/"existing.mp4"
        target.write_bytes(b"sentinel")
        with self.assertRaisesRegex(ValueError,"new MP4"):
            run("render",{"story":sample_story(),"output":str(target),"approve_write":True})
        self.assertEqual(target.read_bytes(),b"sentinel")

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),"FFmpeg unavailable")
    def test_approved_real_mp4_verified(self):
        try:
            import cairosvg
            from PIL import Image
        except ImportError:
            self.skipTest("CairoSVG/Pillow unavailable")
        target=self.root/"storyboard_output.mp4"
        result=execute(self.db,"storyboard.pipeline",{"op":"render","params":{
            "story":sample_story(), "output":str(target)}},approve_write=True)
        self.assertEqual(result["status"],"executed")
        self.assertEqual(result["effect"],"write")
        self.assertFalse(result["legacy_runtime_called"])
        self.assertTrue(target.is_file())
        self.assertEqual(result["result"]["frames"],60)
        self.assertTrue(result["result"]["qa"]["passed"])
        self.assertEqual(result["result"]["qa"]["codec"],"h264")
        self.assertEqual(result["result"]["qa"]["audio_codec"],None)
        qa=verify_video(target,expected_fps=12,expected_frames=60,width=540,
                        height=960,expected_audio=False)
        self.assertTrue(qa["passed"])
        self.assertEqual(result["result"]["qa"]["sha256"],qa["sha256"])
        self.assertEqual(list(self.root.glob(".rose-v30-*")),[])


if __name__=="__main__":
    unittest.main()
