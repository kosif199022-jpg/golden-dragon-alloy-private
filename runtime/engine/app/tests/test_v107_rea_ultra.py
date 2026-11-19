"""REA Ultra v10.7: tests for safe non-executing inspection."""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
BRIDGE=ROOT/'tools'/'rea_ultra'/'bridge.py'
spec=importlib.util.spec_from_file_location('rea_bridge_v107',BRIDGE)
rea=importlib.util.module_from_spec(spec)
spec.loader.exec_module(rea)

class REAUltraTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.d=Path(self.tmp.name)

    def file(self,name,content):
        path=self.d/name
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(content)
        return path

    def run_cli(self,*args):
        return subprocess.run([sys.executable,str(BRIDGE),*map(str,args)],text=True,capture_output=True,timeout=15)

    def test_source_licence_bundled(self):
        self.assertTrue((ROOT/'skills/rea-ultra/references/upstream/LICENSE-REA.txt').is_file())
        self.assertTrue(rea.doctor()['source_skill_present'])

    def test_doctor_does_not_claim_external_tool_runtime(self):
        d=rea.doctor()
        self.assertTrue(d['python_static_triage_ready'])
        self.assertFalse(d['tested_external_tools'])
        self.assertFalse(d['network_used'])

    def test_pe_header(self):
        d=rea.triage(self.file('win.exe',b'MZ\x00\x00' + b'X'*90))
        self.assertEqual(d['format'],'pe')
        self.assertFalse(d['executed_target'])
        self.assertFalse(d['used_rea_cli'])
        self.assertEqual(d['entropy_scope'],'full file')

    def test_elf_header(self):
        self.assertEqual(rea.triage(self.file('bin',b'\x7fELFxxxx'))['format'],'elf')

    def test_macho(self):
        self.assertEqual(rea.triage(self.file('mac',b'\xcf\xfa\xed\xfeabc'))['format'],'mach-o')

    def test_wasm(self):
        p=self.file('module.wasm',b'\x00asm\x01\x00\x00\x00')
        self.assertEqual(rea.triage(p)['format'],'wasm')
        self.assertIn('inspect_wasm_artifact',rea.plan(p)['next_actions'])

    def test_sqlite_magic(self):
        self.assertEqual(rea.triage(self.file('a.db',b'SQLite format 3\x00a'))['format'],'sqlite')

    def test_empty_file(self):
        d=rea.triage(self.file('empty.bin',b''))
        self.assertEqual(d['entropy_sample_bits_per_byte'],0.)
        self.assertEqual(d['sampled_bytes'],0)

    def test_sample_is_bounded(self):
        p=self.file('large.bin', b'\x00'*400_000)
        d=rea.triage(p)
        self.assertEqual(d['sampled_bytes'],256*1024)
        self.assertIn('first and last',d['entropy_scope'])

    def test_hash_changes_when_suffix_changes(self):
        a=self.file('f.bin',b'MZ' + b'0'*550)
        first=rea.triage(a)['evidence_id']
        a.write_bytes(b'MZ'+b'0'*549+b'1')
        self.assertNotEqual(first,rea.triage(a)['evidence_id'])

    def test_apk_like_zip_only_inspected(self):
        p=self.d/'app.apk'
        with zipfile.ZipFile(p,'w') as z:
            z.writestr('AndroidManifest.xml',b'a');z.writestr('classes.dex',b'dex\n')
        d=rea.triage(p)
        self.assertEqual(d['archive']['package_guess'],'android-apk')
        self.assertFalse(d['archive']['extracted'])
        self.assertIn('inspect_android_package (JADX optional)',rea.plan(p)['next_actions'])

    def test_path_traversal_inside_zip_is_flagged_not_extracted(self):
        p=self.d/'unsafe.zip'
        with zipfile.ZipFile(p,'w') as z:z.writestr('../evil',b'bad')
        d=rea.triage(p)
        self.assertEqual(d['archive']['path_or_symlink_warning_count'],1)
        self.assertFalse((self.d.parent/'evil').exists())

    def test_zip_truncated_is_just_unreadable(self):
        p=self.file('bad.zip',b'PK\x03\x04notreallyzip')
        self.assertFalse(rea.triage(p)['archive']['archive_readable'])

    def test_strings_are_data_not_shell_commands(self):
        p=self.file('malware.js',b'#!/bin/sh\n touch /tmp/not-allowed\n')
        self.assertEqual(rea.triage(p)['format'],'javascript-source')
        self.assertFalse(rea.plan(p)['tool_invocation_done'])

    def test_identical_compare(self):
        a=self.file('a',b'hello');b=self.file('b',b'hello')
        self.assertTrue(rea.compare(a,b)['identical_content'])
        b.write_bytes(b'WORLD')
        self.assertFalse(rea.compare(a,b)['identical_content'])

    def test_evidence_verification_detects_modified_target(self):
        p=self.file('sample.bin',b'MZ' + b'123')
        report=self.d/'report.json';report.write_text(json.dumps(rea.triage(p)))
        self.assertTrue(rea.verify(report)['ok'])
        p.write_bytes(b'MZ' + b'124')
        self.assertFalse(rea.verify(report)['ok'])
        self.assertEqual(self.run_cli('verify',report).returncode,1)

    def test_symlink_rejected(self):
        p=self.file('test',b'hello')
        link=self.d/'link'
        try:link.symlink_to(p)
        except (OSError,NotImplementedError):self.skipTest('symlinks unsupported')
        with self.assertRaisesRegex(ValueError,'symlink'):rea.triage(link)

    def test_directory_rejected(self):
        with self.assertRaisesRegex(ValueError,'ordinary file'):rea.triage(self.d)

    def test_report_schema_rejected(self):
        p=self.file('fake.json',b'{"schema":"unrelated"}')
        self.assertEqual(self.run_cli('verify',p).returncode,2)

    def test_json_digest_select_path(self):
        p=self.file('e.json',json.dumps({'result':{'imports':[{'name':'CreateProcess'}]}}).encode())
        d=rea.digest(p,'result.imports')
        self.assertEqual(d['summary'][0]['name'],'CreateProcess')

    def test_json_digest_untrusted_is_not_executed(self):
        p=self.file('e.json',json.dumps({'instruction':'rm -rf /','nested':{'value':'CreateProcess'}}).encode())
        d=rea.digest(p,grep='CreateProcess')
        self.assertIn('CreateProcess',d['summary'][0]['value'])
        self.assertTrue(d['untrusted_evidence_data'])

    def test_digest_overlarge_rejected(self):
        p=self.file('a.json',b' '*(rea.MAX_JSON+1))
        with self.assertRaisesRegex(ValueError,'too large'):rea.digest(p)

    def test_digest_bad_selector_rejected(self):
        p=self.file('a.json',b'[]')
        with self.assertRaises(ValueError):rea.digest(p,'__class__')

    def test_output_is_exclusive(self):
        p=self.file('source',b'MZ123')
        out=self.file('out.json',b'preserve')
        r=self.run_cli('triage',p,'--out',out)
        self.assertEqual(r.returncode,2)
        self.assertEqual(out.read_bytes(),b'preserve')

    def test_cli_plan_and_triage(self):
        p=self.file('a.wasm',b'\x00asm\x01\x00\x00\x00')
        self.assertEqual(json.loads(self.run_cli('triage',p).stdout)['format'],'wasm')
        self.assertEqual(json.loads(self.run_cli('plan',p).stdout)['next_actions'][0],'inspect_wasm_artifact')

    def test_verify_cli_integrity_exit_zero(self):
        p=self.file('img.png',b'fakeimage')
        report=self.file('report.json',json.dumps(rea.triage(p)).encode())
        self.assertEqual(self.run_cli('verify',report).returncode,0)

if __name__=='__main__':unittest.main()
