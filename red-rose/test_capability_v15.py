"""V15 focused tests: native execution, approvals, evidence, no legacy runtimes."""
from __future__ import annotations
import contextlib
import io
import json
import math
import sqlite3
import tempfile
import unittest
import wave
from pathlib import Path
from contextlib import closing

from rose import connect, main as rose_main
from alloy_fusion import init
from capability_runtime import (REGISTRY,list_capabilities,plan_task,execute,audit_summary)


def project(path, seconds=.25):
    path.write_text(json.dumps([{'duration':seconds,'recipe':{'mode':'director2d','actor':{'rig':'ik2d'}}}]),encoding='utf-8')
    return path


class CapabilityTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.db=connect(self.root/'memory.sqlite3')
        self.addCleanup(self.db.close)

    def test_native_adapter_registry_v16(self):
        records=list_capabilities()
        self.assertEqual(len(records),61)
        self.assertEqual({r['id'] for r in records},set(REGISTRY))
        self.assertTrue(all(r['status']=='adapter_implemented' for r in records))

    def test_unknown_action_not_executable(self):
        with self.assertRaisesRegex(ValueError,'not implemented'):
            execute(self.db,'legacy.exec',{'command':'rm -rf /'},approve_write=True)

    def test_injection_cannot_be_args(self):
        with self.assertRaisesRegex(ValueError,'unknown parameters'):
            execute(self.db,'knowledge.stats',{'os.system':'unsafe'},approve_write=True)

    def test_plan_never_executes(self):
        plan=plan_task(self.db,'اعمل فيديو مونتاج وشخصية')
        self.assertEqual(plan['status'],'planned_not_executed')
        self.assertIn('video.produce',plan['suggested_native_adapters'])
        self.assertFalse(plan['legacy_executables_called'])
        self.assertEqual(audit_summary(self.db)['execution_counts'],{})

    def test_no_references_means_no_made_up_executables(self):
        plan=plan_task(self.db,'بحث عن المنظومة غير الموجودة')
        self.assertEqual(plan['knowledge_matches'],0)
        self.assertFalse(plan['reference_titles'])

    def test_read_knowledge_search_with_evidence(self):
        init(self.db)
        self.db.execute('''INSERT INTO fused_knowledge
        (id,kind,title,summary,origin,license,source_path,status,sha256,imported)
        VALUES(?,?,?,?,?,?,?,?,?,?)''',('ref1','road','Motion plan','Frame timing','owner','owner','x.md','active','123','now'))
        self.db.commit()
        result=execute(self.db,'knowledge.search',{'query':'Motion'})
        self.assertEqual(result['status'],'executed')
        self.assertEqual(result['result'][0]['id'],'ref1')
        self.assertFalse(result['legacy_runtime_called'])
        stats=execute(self.db,'knowledge.stats',{})
        self.assertEqual(stats['result']['total'],1)

    def test_reference_routing_is_not_execution(self):
        out=execute(self.db,'knowledge.route',{'task':'animation'})
        self.assertEqual(out['result']['status'],'reference_retrieved_not_executed')
        self.assertEqual(out['effect'],'read')

    def test_recall_read_only_from_local_db(self):
        self.db.execute('INSERT INTO memories(created,category,content) VALUES(?,?,?)',('2026','lesson','example lesson'))
        self.db.commit()
        out=execute(self.db,'memory.recall',{'query':'example'})
        self.assertEqual(out['result'][0]['category'],'lesson')

    def test_list_styles(self):
        self.assertEqual(execute(self.db,'style.list',{})['result'],[])

    def test_svg_refuses_without_approval(self):
        path=self.root/'actor.svg'
        result=execute(self.db,'character.svg',{'output':str(path)},approve_write=False)
        self.assertEqual(result['status'],'approval_required')
        self.assertFalse(path.exists())

    def test_svg_real_output_and_collision(self):
        path=self.root/'actor.svg'
        out=execute(self.db,'character.svg',{'output':str(path)},approve_write=True)
        self.assertTrue(path.exists())
        self.assertIn('<svg',path.read_text())
        self.assertEqual(len(out['result']['sha256']),64)
        with self.assertRaises(ValueError):execute(self.db,'character.svg',{'output':str(path)},approve_write=True)

    def test_script_path_rejected(self):
        path=self.root/'actor.py'
        with self.assertRaisesRegex(ValueError,r'\.svg'):
            execute(self.db,'character.svg',{'output':str(path)},approve_write=True)
        self.assertFalse(path.exists())

    def test_video_preview_no_output(self):
        p=project(self.root/'shot.json')
        out=execute(self.db,'video.preview',{'storyboard':str(p),'fps':8,'width':160,'height':288})
        self.assertEqual(out['result']['budget']['frames'],2)
        self.assertEqual(out['result']['status'],'validated_not_rendered')
        self.assertFalse((self.root/'output').exists())

    def test_video_produce_denied_without_approval(self):
        p=project(self.root/'shot.json')
        dest=self.root/'output'
        out=execute(self.db,'video.produce',{'storyboard':str(p),'output':str(dest)},approve_write=False)
        self.assertEqual(out['status'],'approval_required')
        self.assertFalse(dest.exists())

    def test_real_video_production_verify_and_no_overwrite(self):
        p=project(self.root/'shot.json')
        dest=self.root/'output'
        params={'storyboard':str(p),'output':str(dest),'fps':8,'width':160,'height':288}
        out=execute(self.db,'video.produce',params,approve_write=True)
        self.assertEqual(out['status'],'executed')
        self.assertTrue((dest/'project.json').is_file())
        self.assertTrue((dest/'video.mp4').is_file())
        self.assertTrue(out['result']['qa']['passed'])
        info=execute(self.db,'video.verify',{'video':str(dest/'video.mp4'), 'fps':8,'width':160,'height':288})
        self.assertEqual(info['result']['frames'],2)
        with self.assertRaises(FileExistsError):execute(self.db,'video.produce',params,approve_write=True)

    def test_output_approval_only_doesnt_allow_shell(self):
        with self.assertRaises(ValueError):execute(self.db,'video.produce',
              {'storyboard':'ignored','output':'ignored','command':'powershell'},approve_write=True)

    def test_audit_never_stores_raw_user_content(self):
        execute(self.db,'knowledge.route',{'task':'classified project secret'})
        audit=audit_summary(self.db)
        self.assertEqual(audit['execution_counts']['knowledge.route'],1)
        serialized=' '.join(str(x) for x in self.db.execute('SELECT * FROM capability_execution_audit').fetchone())
        self.assertNotIn('classified',serialized)
        self.assertNotIn('secret',serialized)

    def test_cli_capability_run_end_to_end(self):
        output=io.StringIO()
        with contextlib.redirect_stdout(output):
            rose_main(['--db',str(self.root/'memory.sqlite3'),'capability-run','knowledge.stats','{}'])
        self.assertEqual(json.loads(output.getvalue())['capability'],'knowledge.stats')

    def test_cli_denied_run_end_to_end(self):
        output=io.StringIO()
        path=self.root/'no.svg'
        with contextlib.redirect_stdout(output):
            rose_main(['--db',str(self.root/'memory.sqlite3'),'capability-run','character.svg',json.dumps({'output':str(path)})])
        self.assertEqual(json.loads(output.getvalue())['status'],'approval_required')

    def test_learning_requires_explicit_approval(self):
        source=execute(self.db,'knowledge.stats',{})
        denied=execute(self.db,'learning.record',{'lesson':'Use a short video preview first',
            'source_audit_id':source['audit_id']})
        self.assertEqual(denied['status'],'approval_required')
        self.assertEqual(audit_summary(self.db)['evidence_linked_lessons'],0)

    def test_evidence_linked_lesson_persists_and_is_recalled(self):
        source=execute(self.db,'knowledge.stats',{})
        params={'lesson':'Check audio stream with ffprobe before release',
                'source_audit_id':source['audit_id'],'category':'improvement'}
        saved=execute(self.db,'learning.record',params,approve_write=True)
        self.assertTrue(saved['result']['recorded'])
        again=execute(self.db,'learning.record',params,approve_write=True)
        self.assertFalse(again['result']['recorded'])
        self.assertEqual(audit_summary(self.db)['evidence_linked_lessons'],1)
        recalled=execute(self.db,'memory.recall',{'query':'ffprobe'})
        self.assertEqual(len(recalled['result']),1)
        self.assertEqual(recalled['result'][0]['source_execution_id'],source['audit_id'])
        self.assertEqual(recalled['result'][0]['source'],'evidence_linked_lesson')

    def test_learning_rejects_unaudited_evidence(self):
        with self.assertRaises((ValueError,sqlite3.OperationalError)):
            execute(self.db,'learning.record',{'lesson':'fake finding','source_audit_id':999},approve_write=True)

    def test_learning_rejects_invalid_category(self):
        source=execute(self.db,'knowledge.stats',{})
        with self.assertRaises(ValueError):
            execute(self.db,'learning.record',{'lesson':'test','source_audit_id':source['audit_id'],
                                                'category':'password'},approve_write=True)

    def test_learning_never_exports_into_source_project(self):
        source=execute(self.db,'knowledge.stats',{})
        execute(self.db,'learning.record',{'lesson':'Private work note','source_audit_id':source['audit_id']},approve_write=True)
        self.assertEqual(len(list(self.root.glob('*.md'))),0)
        self.assertTrue((self.root/'memory.sqlite3').exists())

    def test_silence_audio_analysis(self):
        p=self.root/'quiet.wav'
        with wave.open(str(p),'wb') as wf:
            wf.setnchannels(1);wf.setsampwidth(2);wf.setframerate(16000)
            wf.writeframes(b'\x00\x00'*16000)
        out=execute(self.db,'audio.analyze',{'audio':str(p)})
        self.assertEqual(out['result']['peak'],0)
        self.assertEqual(out['result']['silence_ratio'],1)


if __name__=='__main__':unittest.main()
