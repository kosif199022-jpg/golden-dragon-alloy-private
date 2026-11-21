"""Tests for release_v26 (chapter 28: final integration and release, topics 28.01-28.10)."""
import ast
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

import release_v26 as R
import roadmap_1400
from capability_runtime import REGISTRY

ROOT = Path(R.__file__).resolve().parent
HAS_FFMPEG = all(subprocess.run([t, '-version'], capture_output=True, timeout=30).returncode == 0
                 for t in ('ffmpeg', 'ffprobe'))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class StructureTests(unittest.TestCase):
    def test_topics_ops_effects(self):
        self.assertEqual(sorted(R.TOPICS), [f'28.{i:02d}' for i in range(1, 11)])
        self.assertEqual(set(R.TOPICS.values()), set(R.OPS))
        self.assertEqual(set(R.EFFECTS), set(R.OPS))
        self.assertEqual({op for op, e in R.EFFECTS.items() if e == 'write'},
                         {'integrated_video', 'portable_release'})
        self.assertTrue(set(R.EFFECTS.values()) <= {'read', 'write'})

    def test_run_validation(self):
        with self.assertRaises(ValueError):
            R.run('not_an_op', {})
        with self.assertRaises(ValueError):
            R.run('closure_matrix', {'shell': 'rm -rf /'})
        with self.assertRaises(ValueError):
            R.run('edit_rubric', [])
        with self.assertRaises(ValueError):
            R.run('closure_matrix', {'rows': 'everything'})
        with self.assertRaises(ValueError):
            R.run('load_test', {'workloads': ['nope']})
        with self.assertRaises(ValueError):
            R.run('device_checklist', {'evidence': {'items': {'unknown/item': {}}}})

    def test_source_rules(self):
        tree = ast.parse((ROOT / 'release_v26.py').read_text(encoding='utf-8'))
        banned = {'socket', 'urllib', 'http', 'requests', 'ctypes'}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                self.assertFalse({a.name.split('.')[0] for a in node.names} & banned)
            elif isinstance(node, ast.ImportFrom):
                self.assertNotIn((node.module or '').split('.')[0], banned)
            elif isinstance(node, ast.Call):
                f = node.func
                fname = f.id if isinstance(f, ast.Name) else getattr(f, 'attr', '')
                self.assertNotIn(fname, {'eval', 'exec', 'print', 'system', 'popen', 'Popen'})
                for kw in node.keywords:
                    self.assertNotEqual(kw.arg, 'shell')
                if isinstance(f, ast.Attribute) and getattr(f.value, 'id', '') == 'subprocess':
                    self.assertEqual(f.attr, 'run')
                    self.assertIsInstance(node.args[0], ast.List)
                    kws = {k.arg: k.value for k in node.keywords}
                    self.assertIn('timeout', kws)
                    self.assertTrue(getattr(kws.get('capture_output'), 'value', False))
                if isinstance(f, ast.Attribute) and getattr(f.value, 'id', '') == 'shutil':
                    self.assertEqual(f.attr, 'copytree')


class IndependenceTests(unittest.TestCase):
    def test_zero_external_legacy_imports_and_clean_import(self):
        r = R.run('independence_audit', {})['result']
        self.assertEqual(r['external_legacy_imports'], [])
        self.assertEqual(r['unparsed_files'], [])
        self.assertEqual(r['legacy_names_in_subprocess_calls'], [])
        self.assertGreaterEqual(r['files_scanned'], len(list(ROOT.glob('*.py'))) - 1)
        clean = r['clean_import']
        self.assertEqual(clean['exit_code'], 0, clean['stderr_tail'])
        self.assertEqual(clean['report']['registry'], len(REGISTRY))
        self.assertEqual(clean['report']['foreign_modules'], [])
        self.assertTrue(clean['report']['isolated'])
        self.assertTrue(r['passed'])

    def test_external_import_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / 'local_mod.py').write_text('X = 1\n', encoding='utf-8')
            (Path(tmp) / 'bad.py').write_text('import black_dragon\nimport local_mod\n', encoding='utf-8')
            r = R.run('independence_audit', {'project': tmp, 'run_clean_import': False})['result']
        self.assertGreaterEqual(r['external_count'], 1)  # one finding per matching legacy name
        self.assertEqual({f['target'] for f in r['external_legacy_imports']}, {'black_dragon'})
        self.assertFalse(r['passed'])


class RegistryRealityTests(unittest.TestCase):
    def test_real_registry_has_no_phantom(self):
        r = R.run('registry_reality', {})['result']
        self.assertEqual(r['checked'], len(REGISTRY))
        self.assertEqual(r['phantoms'], [], r['phantoms'])
        self.assertTrue(r['passed'])

    def test_fake_id_is_reported(self):
        fake = {k: list(v) for k, v in REGISTRY.items()}
        fake['phantom.teleport'] = ['Does nothing at all', 'read', 'builtin']
        r = R.run('registry_reality', {'registry': fake})['result']
        self.assertEqual([p['id'] for p in r['phantoms']], ['phantom.teleport'])
        self.assertFalse(r['passed'])
        with self.assertRaises(ValueError):
            R.run('registry_reality', {'registry': {'x': 'not a triple'}})


class ClosureTests(unittest.TestCase):
    def test_matrix_matches_summary_and_never_overclaims(self):
        s = roadmap_1400.summary(registry=REGISTRY)
        r = R.run('closure_matrix', {})['result']
        answered = s['questions_answered_in_tested_code']
        self.assertEqual(r['remaining'], 1400 - answered)
        self.assertEqual(r['answered'], answered)
        self.assertEqual(len(r['matrix']), 1400)
        self.assertEqual(sum(row['answered'] for row in r['matrix']), answered)
        self.assertEqual(r['complete'], answered == 1400)
        if answered < 1400:
            self.assertFalse(r['complete'])
            self.assertIn('NOT complete', r['claim'])
        self.assertTrue(r['source_sha256_matches_approved'])
        self.assertEqual(r['source_sha256'], roadmap_1400.SOURCE_SHA256)
        remaining = R.run('closure_matrix', {'rows': 'remaining'})['result']
        self.assertEqual(len(remaining['matrix']), 1400 - answered)


@unittest.skipUnless(HAS_FFMPEG, 'FFmpeg/FFprobe required')
class IntegratedVideoTests(unittest.TestCase):
    def test_refuses_without_approval_or_inside_project(self):
        with tempfile.TemporaryDirectory() as wd:
            with self.assertRaises(ValueError):
                R.run('integrated_video', {'work_dir': wd})
            self.assertEqual(list(Path(wd).iterdir()), [])
        with self.assertRaises(ValueError):
            R.run('integrated_video', {'work_dir': str(ROOT), 'approve_write': True})
        with self.assertRaises(ValueError):
            R.run('integrated_video', {'approve_write': True})

    def test_end_to_end_mp4_with_receipt(self):
        with tempfile.TemporaryDirectory() as wd:
            r = R.run('integrated_video', {'work_dir': wd, 'approve_write': True})['result']
            video = Path(r['video'])
            self.assertTrue(video.is_file())
            self.assertTrue(r['passed'], r['checks'])
            receipt = json.loads(Path(r['receipt']).read_text(encoding='utf-8'))
            self.assertEqual(receipt['sha256'], sha(video))
            self.assertEqual(receipt['codec'], 'h264')
            self.assertEqual(receipt['pix_fmt'], 'yuv420p')
            self.assertLessEqual(abs(receipt['duration'] - receipt['expected_duration']), 1 / receipt['fps'])
            self.assertGreater(receipt['first_frame_luma_mean_16x16'], R.BLACK_LUMA_MAX)
            # independent decode check from the test itself
            dec = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(video), '-f', 'null', '-'],
                                 capture_output=True, timeout=120)
            self.assertEqual(dec.returncode, 0)
            with self.assertRaises(ValueError):  # never overwrite
                R.run('integrated_video', {'work_dir': wd, 'approve_write': True})


class DeviceChecklistTests(unittest.TestCase):
    def test_missing_evidence_needs_human(self):
        r = R.run('device_checklist', {})['result']
        self.assertEqual(r['status'], 'needs_human_evidence')
        self.assertIsNone(r['passed'])
        self.assertFalse(r['screenshots_taken_by_module'])
        sizes = {(i['width'], i['height']) for i in r['checklist']}
        self.assertEqual(sizes, {(390, 844), (1440, 900)})

    def test_complete_record_is_recorded_not_claimed(self):
        items = R.run('device_checklist', {})['result']['checklist']
        with tempfile.TemporaryDirectory() as tmp:
            recs = {}
            for n, it in enumerate(items):
                shot = Path(tmp) / f'shot{n}.png'
                shot.write_bytes(b'png-bytes-%d' % n)
                recs[it['id']] = {'device': 'iPhone 15' if it['viewport'] == 'phone' else 'Laptop',
                                  'date': '2026-11-21', 'pass': True,
                                  'screenshot_sha256': sha(shot), 'screenshot_file': str(shot)}
            r = R.run('device_checklist', {'evidence': {'items': recs}})['result']
            self.assertEqual(r['status'], 'recorded')
            self.assertTrue(r['passed'])
            self.assertFalse(r['screenshots_taken_by_module'])
            self.assertIn('did not take', r['statement'])
            first = next(iter(recs))
            recs[first] = dict(recs[first], screenshot_sha256='0' * 64)
            bad = R.run('device_checklist', {'evidence': {'items': recs}})['result']
            self.assertEqual(bad['status'], 'rejected_hash_mismatch')
        partial = {first: {'device': 'x', 'date': '2026-11-21', 'pass': False, 'screenshot_sha256': 'a' * 64}}
        r = R.run('device_checklist', {'evidence': {'items': partial}})['result']
        self.assertEqual(r['status'], 'incomplete_evidence')
        self.assertIsNone(r['passed'])
        with self.assertRaises(ValueError):
            R.run('device_checklist', {'evidence': {'items': {first: dict(partial[first], date='21/11/2026')}}})


class LoadTests(unittest.TestCase):
    def test_default_is_smoke_scale(self):
        # Full caps stress is opt-in; the default must stay cheap enough to run in a suite.
        r = R.run('load_test', {})['result']
        self.assertEqual(r['scale'], 'smoke')
        self.assertEqual({w['workload'] for w in r['workloads']}, set(R.DEFAULT_BUDGETS))
        for w in r['workloads']:
            self.assertGreater(w['seconds'], 0)

    def test_caps_measured(self):
        r = R.run('load_test', {'scale': 'caps', 'workloads': ['physics_particles', 'geometry_curves']})['result']
        self.assertEqual({w['workload'] for w in r['workloads']}, {'physics_particles', 'geometry_curves'})
        for w in r['workloads']:
            self.assertGreater(w['seconds'], 0)
            self.assertGreater(w['peak_bytes'], 0)

    def test_tiny_budget_flagged(self):
        r = R.run('load_test', {'scale': 'smoke', 'workloads': ['science_fft'],
                                'budgets': {'science_fft': {'seconds': 1e-9, 'peak_mib': 1e-9}}})['result']
        w = r['workloads'][0]
        self.assertGreater(w['seconds'], 0)
        self.assertEqual(set(w['exceeded']), {'seconds', 'peak_mib'})
        self.assertFalse(r['all_within_budget'])
        with self.assertRaises(ValueError):
            R.run('load_test', {'budgets': {'science_fft': {'seconds': -1}}})


class PrivacyTests(unittest.TestCase):
    def test_current_project_is_safe(self):
        r = R.run('release_privacy', {})['result']
        self.assertEqual(r['verdict'], 'safe', r['project']['unreviewed_findings'][:5])
        self.assertEqual(r['project']['blocked_paths'], [])
        self.assertIn('rose.py', r['project']['listed'])

    def test_zip_with_private_store_is_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            zp = Path(tmp) / 'release.zip'
            with zipfile.ZipFile(zp, 'w') as zf:
                zf.writestr('red-rose/rose.py', 'print(1)\n')
                zf.writestr('red-rose/data/memory.sqlite3', b'SQLite format 3\x00')
            r = R.run('release_privacy', {'zip_path': str(zp), 'include_project': False})['result']
            self.assertEqual(r['verdict'], 'blocked')
            self.assertTrue(r['zip']['blocked_paths'] or r['zip']['distribution_flagged'])

    def test_zip_with_vendor_key_is_blocked(self):
        key = 'AK' + 'IA' + 'Q7W3E9R1T5Y2U8I4'
        with tempfile.TemporaryDirectory() as tmp:
            zp = Path(tmp) / 'release.zip'
            with zipfile.ZipFile(zp, 'w') as zf:
                zf.writestr('red-rose/config.py', f"AWS_ID = '{key}'\n")
            r = R.run('release_privacy', {'zip_path': str(zp), 'include_project': False})['result']
            self.assertEqual(r['verdict'], 'blocked')
            self.assertNotIn(key, json.dumps(r))


class RubricTests(unittest.TestCase):
    REF = {'title': 'Own reference cut v1', 'licence': 'CC-BY-4.0',
           'note': 'Compared pacing and colour against the licensed reference edit.'}

    def test_no_scores_needs_review(self):
        r = R.run('edit_rubric', {})['result']
        self.assertEqual(r['status'], 'needs_human_review')
        self.assertEqual(set(r['rubric']), {'framing', 'colour', 'sound', 'story', 'captions_policy'})

    def test_two_reviewers_mean_and_spread(self):
        a = {'framing': 4, 'colour': 3, 'sound': 5, 'story': 4, 'captions_policy': 5}
        b = {'framing': 2, 'colour': 3, 'sound': 4, 'story': 4, 'captions_policy': 5}
        r = R.run('edit_rubric', {'reviews': [{'reviewer': 'A', 'scores': a}, {'reviewer': 'B', 'scores': b}],
                                  'reference': self.REF})['result']
        self.assertEqual(r['status'], 'reviewed')
        self.assertEqual(r['per_criterion']['framing']['mean'], 3.0)
        self.assertEqual(r['per_criterion']['framing']['spread'], 2)
        self.assertEqual(r['per_criterion']['sound']['mean'], 4.5)
        self.assertEqual(r['disagreements'], ['framing'])
        self.assertEqual(r['max_spread'], 2)

    def test_missing_licence_rejected(self):
        a = {'framing': 4, 'colour': 3, 'sound': 5, 'story': 4, 'captions_policy': 5}
        r = R.run('edit_rubric', {'reviews': [{'reviewer': 'A', 'scores': a}],
                                  'reference': {'title': 'x', 'note': 'compared the two cuts'}})['result']
        self.assertEqual(r['status'], 'rejected')
        with self.assertRaises(ValueError):
            R.run('edit_rubric', {'reviews': [{'reviewer': 'A', 'scores': dict(a, story=6)}],
                                  'reference': self.REF})


class PortableReleaseTests(unittest.TestCase):
    def test_refuses_without_approval(self):
        with tempfile.TemporaryDirectory() as wd:
            with self.assertRaises(ValueError):
                R.run('portable_release', {'work_dir': wd})
            self.assertEqual(list(Path(wd).iterdir()), [])

    def test_release_restores_and_smoke_tests(self):
        with tempfile.TemporaryDirectory() as wd:
            r = R.run('portable_release', {'work_dir': wd, 'approve_write': True})['result']
            self.assertTrue(r['passed'], r)
            self.assertEqual(r['smoke_test']['adapters'], len(REGISTRY))
            self.assertGreaterEqual(r['smoke_test']['adapters'], 50)
            self.assertEqual(r['mismatched'], [])
            self.assertEqual(r['zip_sha256'], sha(r['zip']))
            with zipfile.ZipFile(r['zip']) as zf:
                names = zf.namelist()
                manifest = json.loads(zf.read('red-rose/MANIFEST.json'))
            self.assertIn('red-rose/INSTALL.txt', names)
            self.assertIn('rose.py', manifest['files'])
            self.assertFalse([n for n in names if '__pycache__' in n or n.endswith(('.sqlite3', '.db'))])
            privacy = R.run('release_privacy', {'zip_path': r['zip'], 'include_project': False})['result']
            self.assertEqual(privacy['verdict'], 'safe', privacy['zip']['unreviewed_findings'][:5])
            with self.assertRaises(ValueError):  # never overwrite
                R.run('portable_release', {'work_dir': wd, 'approve_write': True})


class HandoffTests(unittest.TestCase):
    def test_resume_command_runs(self):
        r = R.run('handoff_resume', {})['result']
        self.assertTrue(r['cli_subcommand_exists'])
        self.assertTrue(r['in_handoff_section'])
        self.assertTrue(r['in_start_next_agent'])
        self.assertEqual(r['run']['exit_code'], 0, r['run']['stderr_tail'])
        self.assertEqual(r['run']['topics'], 280)
        self.assertEqual(r['run']['questions'], 1400)
        self.assertTrue(r['resumable_without_questions'])
        self.assertEqual(r['handoff_template']['fields_recognised'], 12)


if __name__ == '__main__':
    unittest.main()
