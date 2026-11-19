"""Offline-only tests for HF Blender v1990.4 pilot. Never calls Higgsfield."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]
CLI=ROOT/'scripts/dragon.py'
SRC=ROOT/'skills/hf-blender-render'


def call(*parts):
    return subprocess.run([sys.executable,str(CLI),'tool','hf-blender',*map(str,parts)],cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=30)

class HiggsfieldBlenderPilot(unittest.TestCase):
    def test_doctor_is_local_only(self):
        r=call('doctor');self.assertEqual(r.returncode,0,r.stderr)
        x=json.loads(r.stdout)
        self.assertEqual(x['status'],'LOCAL_INSPECTION_ONLY')
        self.assertEqual(x['sandbox'],'NOT_CONNECTED')

    def test_source_ledger(self):
        x=json.loads(call('source').stdout)
        self.assertEqual(len(x['archive_files']),7)
        self.assertTrue(len(x['source_sha256'])==64)

    def test_plan_ranges_cover_every_frame(self):
        r=call('plan','--frames','101','--workers','7');self.assertEqual(r.returncode,0,r.stderr)
        x=json.loads(r.stdout)
        frames=[q for a,b in x['ranges'] for q in range(a,b+1)]
        self.assertEqual(frames,list(range(1,102)))
        self.assertEqual(x['sandbox_cost'],'UNVERIFIED')

    def test_plan_one_frame(self):
        self.assertEqual(json.loads(call('plan','--frames','1','--workers','3').stdout)['ranges'],[[1,1]])

    def test_invalid_frames_rejected(self):
        self.assertNotEqual(call('plan','--frames','-1').returncode,0)

    def test_invalid_workers_rejected(self):
        self.assertNotEqual(call('plan','--workers','0').returncode,0)

    def test_wrong_engine_rejected(self):
        self.assertNotEqual(call('plan','--engine','CUDA').returncode,0)

    def test_safe_pack_command_and_no_remote_execution(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/'handoff.sh'
            r=call('pack','hatch',SRC/'scenes/hatch_scene.py',SRC/'scenes/hatch_sound.py','--out',out)
            self.assertEqual(r.returncode,0,r.stderr)
            body=out.read_text()
            self.assertIn('PACK_OK',body)
            self.assertIn('KOSIF_DATA',body)
            self.assertLess(len(body),200000)
            self.assertNotIn('sandbox_exec',body)

    def test_injection_job_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/'handoff.sh'
            r=call('pack','evil;echo_no',SRC/'scenes/hatch_sound.py','--out',out)
            self.assertNotEqual(r.returncode,0)
            self.assertFalse(out.exists())

    def test_pack_overwrite_blocked(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/'handoff.sh'
            out.write_text('original')
            r=call('pack','hatch',SRC/'scenes/hatch_sound.py','--out',out)
            self.assertNotEqual(r.returncode,0)
            self.assertEqual(out.read_text(),'original')

    def test_bash_script_syntax(self):
        for p in (SRC/'scripts').glob('*.sh'):
            r=subprocess.run(['bash','-n',str(p)],capture_output=True,text=True)
            self.assertEqual(r.returncode,0,f'{p}: {r.stderr}')

    def test_local_png_gate_pass_and_missing_fail(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as d:
            folder=Path(d)
            for i in range(1,5):Image.new('RGB',(64,96),(65,105,150)).save(folder/f'f_{i:04d}.png')
            self.assertEqual(call('check-frames',folder,'--frames','4').returncode,0)
            r=call('check-frames',folder,'--frames','5')
            self.assertEqual(r.returncode,1)
            self.assertIn('f_0005.png',r.stdout)

    def test_truncated_png_fail(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d)/'f_0001.png').write_bytes(b'\x89PNG\r\n\x1a\n' + b'0'*30)
            r=call('check-frames',d,'--frames','1')
            self.assertEqual(r.returncode,1)
            self.assertIn('f_0001.png',r.stdout)

    @unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'),'FFmpeg not installed')
    def test_short_ffmpeg_delivery_pass(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as d:
            folder=Path(d)
            (folder/'frames').mkdir()
            for i in range(1,13):Image.new('RGB',(64,96),(66,116,168)).save(folder/'frames'/f'f_{i:04d}.png')
            cmd=['bash',str(SRC/'scripts/hf_finish.sh'),str(folder),'test.mp4','0.4','none','64x96']
            r=subprocess.run(cmd,capture_output=True,text=True,timeout=40)
            self.assertEqual(r.returncode,0,r.stdout+'\n'+r.stderr)
            self.assertIn('GATE_PASS',r.stdout)
            self.assertTrue((folder/'test.mp4').stat().st_size>0)

    @unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'),'FFmpeg not installed')
    def test_delivery_fails_if_frame_missing(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d)/'frames').mkdir()
            cmd=['bash',str(SRC/'scripts/hf_finish.sh'),d,'test.mp4','0.4','none','64x96']
            r=subprocess.run(cmd,capture_output=True,text=True,timeout=20)
            self.assertNotEqual(r.returncode,0)
            self.assertIn('FRAME_MISSING',r.stdout)

    def test_skill_frontmatter_at_start(self):
        self.assertTrue((SRC/"SKILL.md").read_text().startswith("---\nname: hf-blender-render"))

    def test_auto_download_opt_in_required(self):
        s=(SRC/'scripts/hf_bootstrap.sh').read_text()
        self.assertIn('HF_BLENDER_ALLOW_DOWNLOAD',s)
        self.assertNotIn('apt-get',s)
        self.assertNotIn('pip install',s)

    def test_sample_scene_has_node_setups(self):
        s=(SRC/'scenes/hatch_scene.py').read_text()
        self.assertIn('m.use_nodes = True',s)
        self.assertIn('egg.use_nodes = True',s)
        self.assertIn('w.use_nodes = True',s)

if __name__=='__main__':unittest.main()
