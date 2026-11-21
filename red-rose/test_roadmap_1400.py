"""Owner-approved 1,400 roadmap tracker and the agent-drafted 1,500 bank."""
from __future__ import annotations

import ast
import copy
import importlib
import json
import tempfile
import time
import unittest
from pathlib import Path

import roadmap_1400 as rm
from capability_runtime import REGISTRY
from question_bank import load_bank, summarize, find, SOURCE as DRAFT_SOURCE

ROOT = Path(__file__).resolve().parent
# Pure-computation modules built for the roadmap; each must expose TOPICS/OPS/run.
PURE_MODULES = ('physics_v20', 'geometry_v20', 'science_v20')
FORBIDDEN_IMPORTS = {'subprocess', 'socket', 'urllib', 'http', 'shutil', 'os', 'sqlite3', 'ctypes'}


class OwnerRoadmapTests(unittest.TestCase):
    def test_source_hash_structure_and_provenance(self):
        rows = rm.load_questions()
        self.assertEqual(len(rows), 1400)
        topics = rm.topics(rows)
        self.assertEqual(len(topics), 280)
        self.assertTrue(all(sorted(t['question_ids']) == sorted(rm.LENS_KEYS) for t in topics.values()))
        self.assertEqual(rm.APPROVAL['owner_words'], 'نفذ الاجابات موافق على الكل')
        self.assertFalse(rm.APPROVAL['verbatim_historical_questions'])
        self.assertIn('paid services', rm.APPROVAL['does_not_cover'])

    def test_tampered_source_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake = Path(tmp) / 'x.json'
            fake.write_bytes(rm.SOURCE.read_bytes().replace('السقوط'.encode(), 'الطيران'.encode(), 1))
            with self.assertRaisesRegex(ValueError, 'hash differs'):
                rm.load_questions(fake)

    def test_every_status_entry_verified_against_code(self):
        entries = rm.load_status(registry=REGISTRY)
        self.assertGreaterEqual(len(entries), 11)
        s = rm.summary(registry=REGISTRY)
        self.assertEqual(sum(s['topics_by_level'].values()), 280)
        self.assertLess(s['questions_answered_in_tested_code'], 1400)
        self.assertFalse(s['complete'])
        self.assertEqual(s['questions_answered_in_tested_code'] + s['questions_remaining'], 1400)

    def _status_with(self, key, entry):
        base = json.loads(rm.STATUS_FILE.read_text(encoding='utf-8'))
        base['topics'][key] = entry
        tmp = tempfile.NamedTemporaryFile('w', suffix='.json', delete=False, encoding='utf-8')
        with tmp:
            json.dump(base, tmp, ensure_ascii=False)
        self.addCleanup(Path(tmp.name).unlink)
        return tmp.name

    def test_fabricated_progress_is_rejected(self):
        good = {'status': 'unit_tested', 'module': 'scene_edit_v16', 'symbol': 'analyze_cuts',
                'test': 'test_scene_edit_v16.py', 'adapter': 'video.scene_analyze',
                'lenses': ['algorithm']}
        cases = {
            'missing module': dict(good, module='no_such_module_v99'),
            'missing symbol': dict(good, symbol='does_not_exist'),
            'test does not exercise symbol': dict(good, test='test_render.py'),
            'unknown adapter': dict(good, adapter='legacy.black_dragon.run'),
            'bad lens': dict(good, lenses=['magic']),
            'e2e without receipt': dict(good, status='e2e_verified'),
            'bad level': dict(good, status='done'),
        }
        for label, entry in cases.items():
            with self.subTest(label=label), self.assertRaises(ValueError):
                rm.load_status(registry=REGISTRY, status_file=self._status_with('01.01', entry))
        with self.assertRaisesRegex(ValueError, 'unknown topic'):
            rm.load_status(registry=REGISTRY, status_file=self._status_with('99.01', good))

    def test_question_lookup_reports_honest_state(self):
        answered = rm.explain_question(701, registry=REGISTRY)  # 15.01 contract lens
        self.assertEqual(answered['topic_key'], '15.01')
        self.assertTrue(answered['answered_in_tested_code'])
        self.assertTrue(answered['owner_approved'])
        untouched = rm.explain_question(1151, registry=REGISTRY)  # 24.01 bank reconciliation
        self.assertFalse(untouched['answered_in_tested_code'])
        self.assertEqual(untouched['topic_status'], 'proposed')
        for bad in (0, 1401, '5', True):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                rm.explain_question(bad, registry=REGISTRY)


class PureModuleContractTests(unittest.TestCase):
    """Lens 4 (permission) and lens 5 (performance) for the pure-computation modules."""

    def test_no_io_imports_and_contract_shape(self):
        for name in PURE_MODULES:
            with self.subTest(module=name):
                tree = ast.parse((ROOT / f'{name}.py').read_text(encoding='utf-8'))
                imported = set()
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        imported |= {a.name.split('.')[0] for a in node.names}
                    elif isinstance(node, ast.ImportFrom) and node.module:
                        imported.add(node.module.split('.')[0])
                    elif isinstance(node, ast.Call) and getattr(node.func, 'id', None) in ('open', 'exec', 'eval'):
                        self.fail(f'{name} calls {node.func.id}')
                self.assertFalse(imported & FORBIDDEN_IMPORTS, imported & FORBIDDEN_IMPORTS)
                module = importlib.import_module(name)
                self.assertEqual(len(module.TOPICS), 10)
                self.assertTrue(set(module.TOPICS.values()) <= set(module.OPS))
                with self.assertRaises(ValueError):
                    module.run('not_an_op', {})
                with self.assertRaises(ValueError):
                    module.run(next(iter(module.OPS)), {'shell': 'rm -rf /'})

    def test_every_topic_op_runs_with_defaults_within_budget(self):
        for name in PURE_MODULES:
            module = importlib.import_module(name)
            for key, op in module.TOPICS.items():
                with self.subTest(module=name, topic=key):
                    start = time.perf_counter()
                    try:
                        out = module.run(op, {})
                    except (ValueError, TypeError):
                        continue  # op needs explicit inputs; covered by its own tests
                    elapsed = time.perf_counter() - start
                    self.assertLess(elapsed, 3.0, f'{name}.{op} took {elapsed:.2f}s')
                    json.dumps(out)
                    self.assertTrue(out['assumptions'] and out['limits'])


class RegistryDispatchTests(unittest.TestCase):
    def test_pure_adapters_dispatch_and_reject(self):
        import sqlite3
        from contextlib import closing
        from capability_runtime import execute, PURE_MODULES
        with tempfile.TemporaryDirectory() as tmp, closing(sqlite3.connect(Path(tmp) / 'a.db')) as db:
            for cap in PURE_MODULES:
                self.assertEqual(REGISTRY[cap][1], 'read')
            out = execute(db, 'physics.simulate', {'op': 'projectile', 'params': {'speed': 30.0, 'angle_deg': 30.0}})
            self.assertEqual(out['status'], 'executed')
            self.assertAlmostEqual(out['result']['result']['range'], 900 * 0.8660254037844386 / 9.81, places=6)
            tc = execute(db, 'math.geometry', {'op': 'timecode', 'params': {
                'action': 'frame_to_tc', 'fps': '30000/1001', 'frame': 107892, 'drop_frame': True}})
            self.assertEqual(tc['result']['result']['tc'], '01:00:00;00')
            for cap, params in (('physics.simulate', {'op': 'os.system'}),
                                ('math.geometry', {'op': 'timecode', 'shell': 'x'}),
                                ('science.compute', {})):
                with self.subTest(cap=cap, params=params), self.assertRaises(ValueError):
                    execute(db, cap, params)
            status = execute(db, 'roadmap.status', {'topic': '08.04'})
            self.assertEqual(status['result']['status'], 'unit_tested')
            with self.assertRaises(ValueError):
                execute(db, 'roadmap.status', {'topic': '08.04', 'question': 5})


class DraftBankTests(unittest.TestCase):
    def test_draft_bank_is_labelled_and_separate(self):
        bank = load_bank(registry=REGISTRY)
        self.assertEqual(len(bank), 1500)
        self.assertTrue(all(i['source'] == DRAFT_SOURCE and not i['owner_approved'] for i in bank))
        s = summarize(bank)
        self.assertFalse(s['are_these_the_original_1400_questions'])
        self.assertEqual(s['owner_approved'], 0)
        self.assertEqual(sum(s['by_state'].values()), 1500)
        self.assertTrue(find(bank, query='LUFS', limit=5))
        with self.assertRaises(ValueError):
            find(bank, state='done')

    def test_draft_validation_rejects_bad_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = ROOT / 'questions'
            for f in src.glob('G*.json'):
                (Path(tmp) / f.name).write_bytes(f.read_bytes())
            g = json.loads((Path(tmp) / 'G02.json').read_text(encoding='utf-8'))
            broken = copy.deepcopy(g)
            broken['items'][0]['cap'] = 'legacy.black_dragon.run'
            (Path(tmp) / 'G02.json').write_text(json.dumps(broken, ensure_ascii=False), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'unknown capability'):
                load_bank(registry=REGISTRY, directory=tmp)
            broken = copy.deepcopy(g)
            broken['items'][1]['q'] = broken['items'][0]['q']
            (Path(tmp) / 'G02.json').write_text(json.dumps(broken, ensure_ascii=False), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'repeats'):
                load_bank(registry=REGISTRY, directory=tmp)


if __name__ == '__main__':
    unittest.main()
