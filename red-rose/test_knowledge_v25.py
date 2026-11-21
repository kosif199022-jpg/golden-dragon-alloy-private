import ast
import hashlib
import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

import knowledge_v25 as kv
from knowledge_v25 import run

MSA = 'ذهبَ الطالبُ إلى المدرسةِ الجديدةِ في الصباحِ'
EN = 'The Quick Brown Fox jumps over the lazy dog near the river bank'


def file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.db = str(self.dir / 'k.sqlite3')

    def tearDown(self):
        self._tmp.cleanup()

    def add(self, text, licence='MIT', source='src', revision='r1'):
        out = run('index_source', {'db': self.db, 'source': source, 'licence': licence,
                                   'url_or_path': 'https://example.org/' + source,
                                   'revision': revision, 'text': text, 'approve_write': True})
        return out['result']['id']


class TestInterface(Base):
    def test_effects_cover_ops_and_topics(self):
        self.assertEqual(set(kv.EFFECTS), set(kv.OPS))
        self.assertEqual(set(kv.TOPICS.values()), set(kv.OPS))
        self.assertTrue(set(kv.EFFECTS.values()) <= {'read', 'write'})

    def test_every_op_with_empty_params(self):
        for op in kv.OPS:
            with self.subTest(op=op):
                try:
                    out = run(op, {})
                except ValueError:
                    continue
                json.dumps(out)
                self.assertEqual(out['op'], op)
                if kv.EFFECTS[op] == 'write':
                    self.assertEqual(out['status'], 'approval_required')

    def test_unknown_param_and_bad_op(self):
        with self.assertRaises(ValueError):
            run('search_fts', {'query': 'x', 'bogus': 1})
        with self.assertRaises(ValueError):
            run('nope', {})
        with self.assertRaises(ValueError):
            run('search_fts', [])

    def test_private_db_refused(self):
        private = str(Path.home() / '.red-rose' / 'memory.sqlite3')
        with self.assertRaises(ValueError):
            run('search_fts', {'db': private, 'query': 'x'})
        with self.assertRaises(ValueError):
            run('workspace_isolation', {'db': private, 'workspace': 'a', 'key': 'k', 'value': 'v',
                                        'approve_write': True})
        with self.assertRaises(ValueError):
            run('search_fts', {'db': 'file:x.db?mode=rw', 'query': 'x'})

    def test_write_without_approval_writes_nothing(self):
        out = run('index_source', {'db': self.db, 'source': 's', 'licence': 'MIT', 'url_or_path': 'p',
                                   'revision': 'r', 'text': 't'})
        self.assertEqual(out['status'], 'approval_required')
        self.assertFalse(Path(self.db).exists())

    def test_source_is_stdlib_only(self):
        src = Path(kv.__file__).read_text(encoding='utf-8')
        tree = ast.parse(src)
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports |= {a.name.split('.')[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom):
                imports.add((node.module or '').split('.')[0])
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                self.assertNotIn(node.func.id, {'exec', 'eval', 'print', 'compile', '__import__'})
        self.assertTrue(imports <= {'__future__', 'hashlib', 'json', 're', 'sqlite3', 'unicodedata',
                                    'contextlib', 'datetime', 'pathlib'}, imports)
        for bad in ('subprocess', 'socket', 'urllib', 'requests', 'ctypes'):
            self.assertNotIn(bad, src)


class TestIndexSource(Base):
    def test_roundtrip_exact_text_and_hash(self):
        text = MSA + '\n\tline two  with  spaces ✓'
        doc = self.add(text)
        got = run('index_source', {'db': self.db, 'action': 'get', 'doc_id': doc})['result']
        self.assertEqual(got['text'], text)
        self.assertEqual(got['sha256'], hashlib.sha256(text.encode('utf-8')).hexdigest())
        self.assertTrue(got['hash_ok'])
        self.assertEqual(got['licence'], 'MIT')

    def test_unknown_licence_rejected(self):
        with self.assertRaises(ValueError):
            run('index_source', {'db': self.db, 'source': 's', 'licence': 'Proprietary-Whatever',
                                 'url_or_path': 'p', 'revision': 'r', 'text': 't', 'approve_write': True})


class TestSearch(Base):
    def test_arabic_variant_and_english(self):
        ar = self.add(MSA, source='ar')
        en = self.add(EN, source='en')
        out = run('search_fts', {'db': self.db, 'query': 'الي المدرسه'})['result']
        self.assertEqual([h['id'] for h in out['hits']], [ar])
        out = run('search_fts', {'db': self.db, 'query': 'فى الصباح'})['result']
        self.assertEqual([h['id'] for h in out['hits']], [ar])
        out = run('search_fts', {'db': self.db, 'query': 'QUICK fox'})['result']
        self.assertEqual([h['id'] for h in out['hits']], [en])
        self.assertGreater(out['hits'][0]['score'], 0)


class TestLegacy(Base):
    def test_read_only_and_not_executable(self):
        legacy = self.dir / 'legacy.db'
        with closing(sqlite3.connect(legacy)) as c:
            c.execute('CREATE TABLE summaries(id INTEGER PRIMARY KEY, title TEXT, summary TEXT, '
                      'origin TEXT, licence TEXT)')
            c.execute("INSERT INTO summaries VALUES(1,'dragon','import black_dragon; black_dragon.go()',"
                      "'old/kb','unknown')")
            c.execute("INSERT INTO summaries VALUES(2,'notes','plain summary','old/notes','MIT')")
            c.commit()
        before = file_sha(legacy)
        out = run('legacy_summaries', {'db': str(legacy)})['result']
        run('legacy_summaries', {'db': str(legacy), 'contains': 'dragon'})
        self.assertEqual(file_sha(legacy), before)
        item = out['items'][0]
        self.assertEqual(item['summary'], 'import black_dragon; black_dragon.go()')
        self.assertIs(item['executable'], False)
        self.assertTrue(item['mentions_code'])
        self.assertEqual(out['total_rows'], 2)


class TestOwner(Base):
    def test_recall_after_reconnect_and_consent(self):
        denied = run('owner_instructions', {'db': self.db, 'instruction': 'no fades', 'approve_write': True})
        self.assertEqual(denied['status'], 'approval_required')
        self.assertIn('consent', denied['result']['needs'])
        self.assertFalse(Path(self.db).exists())
        run('owner_instructions', {'db': self.db, 'instruction': 'AAC audio always',
                                   'approve_write': True, 'consent': True})
        got = run('owner_instructions', {'db': self.db, 'action': 'recall'})['result']
        self.assertEqual([i['instruction'] for i in got['items']], ['AAC audio always'])
        self.assertTrue(got['items'][0]['hash_ok'])


class TestErrorMemory(Base):
    def test_correction_keeps_history(self):
        base = {'db': self.db, 'key': 'ffmpeg.filter_script', 'approve_write': True}
        run('error_memory', {**base, 'cause': 'old flag', 'fix': 'use -filter_complex_script',
                             'evidence': 'ffmpeg 6 docs'})
        run('error_memory', {**base, 'action': 'correct', 'cause': 'flag removed in ffmpeg 9',
                             'fix': 'use -/filter_complex FILE', 'evidence': 'ffmpeg 9 run',
                             'reason': 'outdated'})
        got = run('error_memory', {'db': self.db, 'action': 'get', 'key': 'ffmpeg.filter_script',
                                   'history': True})['result']
        self.assertEqual(got['latest']['fix'], 'use -/filter_complex FILE')
        self.assertEqual([h['fix'] for h in got['history']],
                         ['use -filter_complex_script', 'use -/filter_complex FILE'])
        self.assertFalse(got['history'][0]['current'])
        self.assertEqual(got['history'][0]['superseded_by'], got['latest']['id'])


class TestConflicts(Base):
    def test_disagreeing_sources_shown_with_links(self):
        for v, s in ((9.81, 'a'), (9.8, 'b'), (9.81, 'c')):
            run('reference_conflicts', {'db': self.db, 'ref_key': 'g', 'value': v, 'source': s,
                                        'origin': f'https://{s}.example/g', 'approve_write': True})
        run('reference_conflicts', {'db': self.db, 'ref_key': 'pi', 'value': 3.14, 'source': 'a',
                                    'origin': 'https://a.example/pi', 'approve_write': True})
        rep = run('reference_conflicts', {'db': self.db, 'action': 'report'})['result']
        self.assertEqual(rep['conflict_count'], 1)
        conf = rep['conflicts'][0]
        self.assertEqual(conf['ref_key'], 'g')
        links = {s['origin'] for v in conf['values'] for s in v['sources']}
        self.assertEqual(links, {'https://a.example/g', 'https://b.example/g', 'https://c.example/g'})
        self.assertEqual(sorted(v['value'] for v in conf['values']), [9.8, 9.81])


class TestTrust(Base):
    def test_summary_only_rejected_and_newer_tested_higher(self):
        out = run('trust_score', {'as_of': '2026-11-21', 'references': [
            {'id': 'old', 'source_tier': 'primary', 'date': '2016-01-01', 'original_text': 'x'},
            {'id': 'new', 'source_tier': 'primary', 'date': '2026-06-01', 'original_text': 'y',
             'test': 'passed'},
            {'id': 'sum', 'source_tier': 'primary', 'date': '2026-06-01', 'summary': 'only a summary'},
        ]})['result']
        self.assertEqual([r['id'] for r in out['rejected']], ['sum'])
        scores = {r['id']: r['score'] for r in out['admitted']}
        self.assertGreater(scores['new'], scores['old'])
        self.assertLessEqual(max(scores.values()), 1.0)


class TestReceipt(Base):
    def test_replay_and_break(self):
        a = self.add(MSA, source='ar')
        self.add(EN, source='en')
        saved = run('search_receipt', {'db': self.db, 'query': 'إلى المدرسة', 'approve_write': True})['result']
        self.assertEqual(saved['result_ids'], [a])
        rep = run('search_receipt', {'db': self.db, 'action': 'replay',
                                     'receipt_id': saved['receipt_id']})['result']
        self.assertTrue(rep['replay_ok'], rep['reasons'])
        self.assertEqual(rep['replayed_hashes'], saved['result_hashes'])
        run('index_source', {'db': self.db, 'action': 'revise', 'doc_id': a, 'revision': 'r2',
                             'text': MSA + ' مع أصدقائه', 'approve_write': True})
        rep = run('search_receipt', {'db': self.db, 'action': 'replay',
                                     'receipt_id': saved['receipt_id']})['result']
        self.assertFalse(rep['replay_ok'])
        self.assertTrue(any(f'document {a} text changed' in r for r in rep['reasons']), rep['reasons'])


class TestMigration(Base):
    def setUp(self):
        super().setUp()
        with closing(sqlite3.connect(self.db)) as c:
            c.execute('CREATE TABLE notes(id INTEGER PRIMARY KEY, body TEXT)')
            c.executemany('INSERT INTO notes(body) VALUES(?)', [('a',), ('b',), ('c',)])
            c.commit()

    def test_injected_error_rolls_back(self):
        migs = [{'name': 'add_tag', 'sql': ['ALTER TABLE notes ADD COLUMN tag TEXT',
                                            "UPDATE notes SET tag='x'"]},
                {'name': 'bad', 'sql': ['INSERT INTO missing_table VALUES(1)']}]
        out = run('migrate_memory', {'db': self.db, 'migrations': migs, 'approve_write': True})['result']
        self.assertEqual(out['status'], 'rolled_back')
        self.assertTrue(out['unchanged'])
        self.assertEqual(out['before'], out['after'])
        self.assertEqual(out['after']['notes']['rows'], 3)
        out = run('migrate_memory', {'db': self.db, 'migrations': migs[:1], 'simulate_failure_after': 1,
                                     'approve_write': True})['result']
        self.assertEqual(out['status'], 'rolled_back')
        self.assertEqual(out['before'], out['after'])
        with closing(sqlite3.connect(self.db)) as c:
            cols = [r[1] for r in c.execute('PRAGMA table_info(notes)')]
        self.assertNotIn('tag', cols)

    def test_successful_migration_and_destructive_refused(self):
        out = run('migrate_memory', {'db': self.db, 'approve_write': True, 'migrations': [
            {'name': 'add_tag', 'sql': 'ALTER TABLE notes ADD COLUMN tag TEXT'}]})['result']
        self.assertEqual(out['status'], 'committed')
        self.assertEqual(out['after']['notes']['rows'], 3)
        self.assertIn('schema_migrations', out['after'])
        with self.assertRaises(ValueError):
            run('migrate_memory', {'db': self.db, 'approve_write': True,
                                   'migrations': [{'name': 'x', 'sql': 'DROP TABLE notes'}]})


class TestWorkspace(Base):
    def test_cross_workspace_refused(self):
        rid = run('workspace_isolation', {'db': self.db, 'workspace': 'company-b', 'key': 'secret',
                                          'value': 'B data', 'approve_write': True})['result']['id']
        run('workspace_isolation', {'db': self.db, 'workspace': 'company-a', 'key': 'k', 'value': 'A',
                                    'approve_write': True})
        cross = run('workspace_isolation', {'db': self.db, 'action': 'get', 'workspace': 'company-a',
                                            'record_id': rid})['result']
        self.assertFalse(cross['found'])
        self.assertEqual(cross['records'], [])
        own = run('workspace_isolation', {'db': self.db, 'action': 'get', 'workspace': 'company-b',
                                          'record_id': rid})['result']
        self.assertEqual(own['records'][0]['value'], 'B data')
        listed = run('workspace_isolation', {'db': self.db, 'action': 'list', 'workspace': 'company-a'})
        self.assertEqual([r['value'] for r in listed['result']['records']], ['A'])
        with self.assertRaises(ValueError):
            run('workspace_isolation', {'db': self.db, 'action': 'list'})


if __name__ == '__main__':
    unittest.main()
