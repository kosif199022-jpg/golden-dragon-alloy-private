"""V18 tests: attributable decision trace, no fabricated 1400 originals."""
from __future__ import annotations
import contextlib
from contextlib import closing
import io
import json
from pathlib import Path
import shutil
import sqlite3
import tempfile
import unittest

from qa_trace import ROOT, load_trace, trace
from capability_runtime import REGISTRY, execute
from rose import main as rose_main


class QATraceTests(unittest.TestCase):
    def test_all_decisions_and_dynamic_registry_verified(self):
        data, coverage = load_trace(registry=REGISTRY)
        self.assertEqual(len(data), 35)
        self.assertEqual(set(data), {f'A{i:02d}' for i in range(1,36)})
        self.assertEqual(coverage['historical_design_target'],1400)
        self.assertFalse(coverage['original_1400_question_archive_complete'])
        self.assertEqual(len(REGISTRY),65)
        self.assertIn('qa.trace',REGISTRY)
        self.assertEqual(REGISTRY['qa.trace'][1],'read')

    def test_summary_discloses_caveats_and_never_1400_implemented(self):
        out=trace(registry=REGISTRY)
        self.assertEqual(out['tracked_decisions'],35)
        self.assertEqual(out['registered_native_adapters_current'],len(REGISTRY))
        self.assertFalse(out['original_question_archive_complete'])
        self.assertEqual(out['historical_design_target'],1400)
        self.assertEqual(len(out['historical_ranges']),3)
        self.assertGreater(out['decisions_linked_to_native_adapters'],0)
        self.assertLess(out['decisions_linked_to_native_adapters'],35)
        self.assertIn('paraphrase',out['status'])

    def test_retrieval_preserves_actual_answer_attribution(self):
        out=trace('A17',registry=REGISTRY)
        self.assertIn('ذاكرة',out['answer_paraphrase'])
        self.assertEqual(out['provenance_class'],'U')
        self.assertEqual(out['assessment'],'related_partial')
        self.assertIn('memory.recall',[r['id'] for r in out['linked_native_capabilities']])
        self.assertIn('learning.record',[r['id'] for r in out['linked_native_capabilities']])
        self.assertFalse(out['verbatim_original_question'])
        self.assertFalse(out['link_is_proof_of_full_completion'])

    def test_unrecovered_historical_numbers_are_rejected(self):
        for q in ('451','1400','Q451','A36','A00',None,4, 'A17; rm -rf /'):
            if q is None:
                continue  # None means a summary, not an original question
            with self.subTest(q=q), self.assertRaises(ValueError):
                trace(q,registry=REGISTRY)

    def test_unknown_capability_id_rejected_in_index(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)
            for name in ('QA_TRACEABILITY.json','QUESTION_COVERAGE.json','QUESTIONS_AND_ANSWERS.md'):
                shutil.copy2(ROOT/name,p/name)
            raw=json.loads((p/'QA_TRACEABILITY.json').read_text(encoding='utf-8'))
            raw['rows'][16]['linked_native_capabilities']=['legacy.black-dragon.run']
            (p/'QA_TRACEABILITY.json').write_text(json.dumps(raw),encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'Nonexecutable'):
                load_trace(directory=p,registry=REGISTRY)

    def test_fabricated_original_verbatim_flag_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)
            for name in ('QA_TRACEABILITY.json','QUESTION_COVERAGE.json','QUESTIONS_AND_ANSWERS.md'):
                shutil.copy2(ROOT/name,p/name)
            raw=json.loads((p/'QA_TRACEABILITY.json').read_text(encoding='utf-8'))
            raw['rows'][0]['original_question_verbatim']=True
            (p/'QA_TRACEABILITY.json').write_text(json.dumps(raw),encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'paraphrases'):
                load_trace(directory=p,registry=REGISTRY)

    def test_native_dispatch_read_only_and_audited(self):
        with closing(sqlite3.connect(':memory:')) as db:
            output=execute(db,'qa.trace',{'question_id':'A27'})
            self.assertEqual(output['status'],'executed')
            self.assertEqual(output['effect'],'read')
            self.assertFalse(output['legacy_runtime_called'])
            self.assertIn('video.edit_suggest',[r['id'] for r in output['result']['linked_native_capabilities']])
            self.assertEqual(db.execute('SELECT count(*) FROM capability_execution_audit').fetchone()[0],1)
            with self.assertRaisesRegex(ValueError,'unknown parameters'):
                execute(db,'qa.trace',{'question_id':'A01','command':'powershell'})

    def test_cli_does_not_open_personal_database(self):
        with tempfile.TemporaryDirectory() as d:
            missing=Path(d)/'should-not-create.sqlite3'
            capture=io.StringIO()
            with contextlib.redirect_stdout(capture):
                rose_main(['--db',str(missing),'question-trace','A25'])
            result=json.loads(capture.getvalue())
            self.assertEqual(result['id'],'A25')
            self.assertFalse(missing.exists())
            capture=io.StringIO()
            with contextlib.redirect_stdout(capture):
                rose_main(['--db',str(missing),'question-audit'])
            self.assertEqual(json.loads(capture.getvalue())['tracked_decisions'],35)
            self.assertFalse(missing.exists())


if __name__=='__main__':
    unittest.main()
