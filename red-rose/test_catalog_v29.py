"""V29 W02: generated operation catalogue, find/nearest, describe/ops/catalog-build CLI."""
import json
import os
import shlex
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import capability_runtime as cr  # noqa: E402
import rose_catalog as rc  # noqa: E402

PY = [sys.executable, '-X', 'utf8']
CAT_FILE = ROOT / 'references' / 'OPS_CATALOG.json'
MD_FILE = ROOT / 'references' / 'OPS.md'
BRANCH_FILE = ROOT / 'catalog' / 'branch_signatures.json'


def live_ids():
    """Every agent-facing id from the live registry, counted from code (not hard-coded)."""
    ids = []
    for adapter in cr.REGISTRY:
        module = cr.IO_ADAPTERS.get(adapter) or cr.PURE_MODULES.get(adapter)
        if module is None:
            ids.append(adapter)
        else:
            ids.extend(f'{adapter}.{op}' for op in module.OPS)
    return ids


def run_cli(*args, env_extra=None, script='rose_catalog.py'):
    env = dict(os.environ)
    env.update(env_extra or {})
    return subprocess.run(PY + [str(ROOT / script)] + list(args), cwd=str(ROOT), env=env,
                          capture_output=True, text=True, encoding='utf-8', timeout=300)


def run_rose(*args, env_extra=None):
    return run_cli(*args, env_extra=env_extra, script='rose.py')


class CatalogueContent(unittest.TestCase):
    def setUp(self):
        self.cat = rc.load()
        self.entries = self.cat['entries']

    def test_ids_match_live_registry_exactly_once(self):
        expected = live_ids()
        self.assertEqual(len(expected), len(set(expected)))
        self.assertEqual(set(expected), set(self.entries))
        self.assertEqual(self.cat['counts']['entries'], len(expected))
        self.assertEqual(self.cat['counts']['module_ops'] + self.cat['counts']['flat_adapters'], len(expected))

    def test_every_entry_has_name_summary_effect_params(self):
        for op_id, e in self.entries.items():
            with self.subTest(op=op_id):
                self.assertTrue(e['name_ar'].strip())
                self.assertTrue(e['summary'].strip())
                self.assertIn(e['effect'], ('read', 'write'))
                self.assertIsInstance(e['params'], list)
                self.assertEqual(e['id'], op_id)
                if e['example'] is None:
                    self.assertEqual(e['static_label'], 'needs_input')
                else:
                    self.assertEqual(e['example']['source'], 'defaults')

    def test_example_params_are_declared(self):
        for op_id, e in self.entries.items():
            if not e['example']:
                continue
            names = {p['name'] for p in e['params']}
            for token in e['example']['args']:
                with self.subTest(op=op_id, token=token):
                    self.assertIn(token.split('=', 1)[0], names)

    def test_write_ops_need_approval_and_flat_shape(self):
        for op_id, e in self.entries.items():
            if e['effect'] == 'write':
                self.assertTrue(e['approval']['needed'], op_id)
            if e['call_shape'] == 'flat':
                self.assertIsNone(e['op'])
                self.assertEqual(e['adapter'], op_id)
            else:
                self.assertEqual(f"{e['adapter']}.{e['op']}", op_id)

    def test_drift_guard_committed_json_equals_build(self):
        text = (json.dumps(rc.build(), sort_keys=True, ensure_ascii=False, indent=2) + '\n')
        self.assertEqual(CAT_FILE.read_bytes(), text.encode('utf-8'))

    def test_drift_guard_branch_signatures_match_introspection(self):
        branch = json.loads(BRANCH_FILE.read_text(encoding='utf-8'))
        for adapter, params in branch['adapters'].items():
            with self.subTest(adapter=adapter):
                names = {p['name'] for p in self.entries[adapter]['params']}
                self.assertEqual(set(params), names)

    def test_markdown_lists_every_entry(self):
        text = MD_FILE.read_text(encoding='utf-8')
        for op_id in self.entries:
            self.assertIn(f'`{op_id}`', text)

    def test_describe_facts_from_plan(self):
        kinetic = rc.schema('text.motion.kinetic_text')
        for name in ('font_size', 'fill', 'stroke', 'align', 'position'):
            self.assertIn(name, kinetic)
        self.assertEqual(len(self.entries['text.motion.kinetic_text']['sub_catalogue']['items']), 15)
        preview = rc.schema('studio.render.preview_frame')
        self.assertIn('rasterize', preview)
        self.assertIn('png_width', preview)

    def test_schema_shape_and_unknown_ids(self):
        sch = rc.schema('accounting.check.bank_reconcile')
        self.assertIsInstance(sch, dict)
        for spec in sch.values():
            self.assertEqual(set(spec), {'type', 'required', 'default', 'choices'})
        self.assertIsNone(rc.schema('no.such.op'))
        self.assertIsNone(rc.get('no.such.op'))

    def test_flat_adapters_have_their_branch_params(self):
        self.assertEqual({p['name'] for p in self.entries['video.recut']['params']},
                         {'source', 'segments', 'output', 'fps'})
        self.assertEqual(rc.schema('knowledge.stats'), {})

    def test_nearest_ids_returns_n(self):
        near = rc.nearest_ids('no.such.op', 5)
        self.assertEqual(len(near), 5)
        for op_id in near:
            self.assertIn(op_id, self.entries)


class Finding(unittest.TestCase):
    def top(self, query, n=3):
        return [row['id'] for row in rc.find(query, limit=8)][:n]

    def test_english_bank_reconciliation(self):
        self.assertIn('accounting.check.bank_reconcile',
                      self.top('bank reconciliation of a statement against the ledger'))

    def test_arabic_bank_reconciliation(self):
        self.assertIn('accounting.check.bank_reconcile', self.top('تسوية كشف حساب البنك مع الدفتر'))

    def test_kinetic_text_english(self):
        self.assertIn('text.motion.kinetic_text', self.top('kinetic text'))

    def test_kinetic_text_arabic_reel(self):
        self.assertIn('text.motion.kinetic_text', self.top('عنوان متحرك للريلز'))

    def test_arabic_folding(self):
        self.assertEqual(rc.tokens('الكابشن'), ['كابشن'])
        self.assertEqual(rc.tokens('تَسْوِيَة'), rc.tokens('تسويه'))
        self.assertEqual(rc.tokens('إسماعيل'), rc.tokens('اسماعيل'))
        self.assertEqual(rc.tokens('للريلز'), ['ريلز'])
        self.assertEqual(rc.tokens('والبنك'), ['بنك'])
        self.assertEqual(rc.fold('مَطَابَقَة'), 'مطابقه')
        self.assertEqual(rc.fold('ى'), 'ي')

    def test_find_is_stable_and_limited(self):
        first = rc.find('caption', limit=4)
        self.assertEqual(first, rc.find('caption', limit=4))
        self.assertLessEqual(len(first), 4)
        self.assertEqual(rc.find('', limit=4), [])


class Commands(unittest.TestCase):
    def test_describe_unknown_exits_1_with_five_nearest(self):
        res = run_cli('describe', 'no.such.op')
        self.assertEqual(res.returncode, 1, res.stderr)
        doc = json.loads(res.stdout)
        self.assertFalse(doc['ok'])
        self.assertEqual(len(doc['allowed']), 5)

    def test_describe_text_and_json(self):
        res = run_cli('describe', 'studio.render.preview_frame')
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn('rasterize', res.stdout)
        self.assertIn('png_width', res.stdout)
        self.assertIn('python -X utf8 rose.py run studio.render.preview_frame', res.stdout)
        res = run_cli('describe', 'studio.render.preview_frame', '--json')
        doc = json.loads(res.stdout)
        self.assertEqual(doc['entry']['id'], 'studio.render.preview_frame')
        self.assertIn('label', doc['entry'])

    def test_ops_lists_adapters_and_one_adapter(self):
        res = run_cli('ops')
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn('text.motion | ', res.stdout)
        res = run_cli('ops', 'text.motion')
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn('text.motion.kinetic_text', res.stdout)
        res = run_cli('ops', 'nope.adapter')
        self.assertEqual(res.returncode, 1)

    def test_find_command(self):
        res = run_cli('find', 'kinetic', 'text', '--json')
        self.assertEqual(res.returncode, 0, res.stderr)
        doc = json.loads(res.stdout)
        self.assertEqual(doc['results'][0]['kind'], 'op')
        self.assertIn('text.motion.kinetic_text', [r['id'] for r in doc['results']][:3])

    def test_catalog_build_refuses_without_approval_and_writes_nothing(self):
        before = (CAT_FILE.read_bytes(), MD_FILE.read_bytes(), BRANCH_FILE.read_bytes())
        res = run_cli('catalog-build')
        self.assertEqual(res.returncode, 3, res.stderr)
        self.assertEqual(json.loads(res.stdout)['outcome'], 'approval_required')
        self.assertEqual(before, (CAT_FILE.read_bytes(), MD_FILE.read_bytes(), BRANCH_FILE.read_bytes()))

    def test_ops_describe_find_do_not_create_the_database(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / 'missing' / 'memory.sqlite3'
            env = {'RED_ROSE_DB': str(db)}
            run_cli('ops', env_extra=env)
            run_cli('describe', 'text.motion.kinetic_text', env_extra=env)
            run_cli('find', 'kinetic', env_extra=env)
            self.assertFalse(db.exists())
            self.assertFalse(db.parent.exists())

    def test_sampled_defaults_lines_execute_with_exit_0_or_5(self):
        # the copy-paste line from describe, run through rose.py, for 20 spread-out runs_with_defaults ops
        ids = sorted(k for k, e in rc.load()['entries'].items() if e['runs_with_defaults'])
        step = max(1, len(ids) // 20)
        sample = ids[::step][:20]
        self.assertGreaterEqual(len(sample), 20)
        for op_id in sample:
            with self.subTest(op=op_id):
                doc = json.loads(run_cli('describe', op_id, '--json').stdout)
                line = doc['entry']['run']
                self.assertTrue(line.startswith('python -X utf8 rose.py run '), line)
                tokens = shlex.split(line.replace('python -X utf8 rose.py ', ''))
                res = run_rose(*tokens)
                self.assertIn(res.returncode, (0, 5), res.stdout[-400:] + res.stderr[-400:])


if __name__ == '__main__':
    unittest.main()
