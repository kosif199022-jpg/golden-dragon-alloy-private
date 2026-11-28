import unittest, shutil, tempfile, subprocess, json, sys
from pathlib import Path
from shot_detail_legacy_v19 import frame_metrics, GRID_W, GRID_H, shot_quality

class ShotDetailUnified(unittest.TestCase):
    def test_flat_vs_pattern(self):
        flat=bytes([128])*(GRID_W*GRID_H)
        pattern=bytes(255*((i%GRID_W+i//GRID_W)%2) for i in range(GRID_W*GRID_H))
        self.assertEqual(frame_metrics(flat)["detail"],0)
        self.assertGreater(frame_metrics(pattern)["detail"],1)
    def test_invalid_frame(self):
        with self.assertRaises(ValueError):frame_metrics(b"")
    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),"ffmpeg required")
    def test_cli_real_media(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"source.mp4"
            subprocess.run(["ffmpeg","-v","error","-f","lavfi","-i","testsrc2=size=160x96:rate=12","-t","2","-c:v","libx264",str(p)],check=True,timeout=30)
            out=subprocess.run([sys.executable,str(Path(__file__).with_name("rose.py")),"shot-detail",str(p)],capture_output=True,text=True,encoding="utf-8",check=True,timeout=60)
            d=json.loads(out.stdout)
            self.assertEqual(d["status"],"analyzed_not_edited")
            self.assertTrue(d["shots"])
            self.assertTrue(d["requires_explicit_approved_video_recut"])
            self.assertEqual(list(Path(tmp).iterdir()),[p])
