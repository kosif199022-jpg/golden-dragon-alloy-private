"""Focused v1990.2 smoke and integration tests (no paid services)."""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
DRAGON=ROOT/'scripts/dragon.py'
ARENA=ROOT/'skills/montage-arena/scripts/arena.py'
LINTER=ROOT/'skills/windows-commands/scripts/wincmd_lint.py'

def call(*args, env=None):
    return subprocess.run([sys.executable, str(DRAGON), 'tool', *args], text=True, capture_output=True,
                          env=env, timeout=25)

class MontageWindowsIntegrationTests(unittest.TestCase):
    def test_source_ledger(self):
        manifest=json.loads((ROOT/'SOURCE_MONTAGE_WINDOWS.json').read_text(encoding='utf-8'))
        self.assertEqual(manifest['sources']['montage-arena']['files'], 16)
        self.assertEqual(manifest['sources']['windows-commands']['files'], 19)
        self.assertIn('github-atlas(1).zip',manifest['duplicates'])

    def test_old_arena_preserved(self):
        self.assertTrue((ROOT/'tools/arena/bracket.py').is_file())
        self.assertTrue(ARENA.is_file())
        self.assertNotEqual((ROOT/'tools/arena/bracket.py').read_bytes(),ARENA.read_bytes())

    def test_montage_roster(self):
        r=call('montage-arena','roster','--type','reel')
        self.assertEqual(r.returncode,0,r.stderr)
        self.assertIn('hook',r.stdout)

    def test_arena_creates_separate_workdir(self):
        with tempfile.TemporaryDirectory() as d:
            env=dict(os.environ,MONTAGE_ARENA_HOME=str(Path(d)/'memory'), DRAGON_STATE=str(Path(d)/'state'))
            r=call('montage-arena','new','ريل تجريبي','--type','reel','--size','quick','--dir',d,env=env)
            self.assertEqual(r.returncode,0,r.stderr)
            self.assertTrue(list(Path(d).glob('*/arena.json')))
            self.assertTrue((Path(d)/'memory/last.txt').is_file())

    def test_windows_lint_flags_msys_switch(self):
        r=call('windows-lint','--shell','bash','--json','taskkill /F /IM test.exe')
        self.assertEqual(r.returncode,2,r.stderr)
        rules={x['rule'] for x in json.loads(r.stdout)}
        self.assertIn('SH001',rules)

    def test_windows_lint_clean(self):
        r=call('windows-lint','--shell','bash','--json','echo hello')
        self.assertEqual(r.returncode,0,r.stderr)
        self.assertEqual(json.loads(r.stdout),[])

    def test_windows_lint_never_executes_passed_text(self):
        with tempfile.TemporaryDirectory() as d:
            sentinel=Path(d)/'sentinel.txt'
            command=f'python3 -c "open(\'{sentinel}\', \'w\').write(\'HI\')"'
            r=call('windows-lint','--shell','powershell','--json',command)
            self.assertFalse(sentinel.exists())
            self.assertIn(r.returncode,(0,1,2))

    def test_helpers_not_autorun(self):
        r=call('windows-lint','--help')
        self.assertEqual(r.returncode,0,r.stderr)
        self.assertIn('--shell',r.stdout)
        self.assertTrue((ROOT/'skills/windows-commands/scripts/NativeExact.ps1').is_file())

if __name__=='__main__':unittest.main()
