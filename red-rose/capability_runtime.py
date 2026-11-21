"""Red Rose V15: executable, evidence-aware adapter registry.

Only native Red Rose functions appear in this registry. Legacy skill descriptions
are retrieved as references but NEVER treated as working tools or executed.
"""
from __future__ import annotations
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
import shutil
import sqlite3
from pathlib import Path

from alloy_fusion import find_fused, stats_fused
from knowledge_router import route as knowledge_route
from verify_media import verify_video
from lip_sync import levels_from_audio
from rig import rig_character
from pipeline_v15 import prepare_project, render_project, budget
from styles import list_styles
from scene_edit_v16 import analyze_cuts, recut
from audio_scene_v17 import detect_silences, timeline_analyze, suggest_edit
from qa_trace import trace as qa_trace
from shot_quality_v19 import score_shots
import roadmap_1400
import physics_v20
import geometry_v20
import science_v20
import thinking_v21
import decision_v21
import code_analysis_v21
import accounting_v21
import governance_v22
import architecture_v22
import agents_v22
import learning_v22
import compose_v22

# Pure-computation adapters: one explicit op whitelist per module, no I/O.
PURE_MODULES = {'physics.simulate': physics_v20, 'math.geometry': geometry_v20,
                'science.compute': science_v20, 'thinking.reason': thinking_v21,
                'decision.make': decision_v21, 'code.analyze': code_analysis_v21,
                'accounting.check': accounting_v21, 'governance.audit': governance_v22,
                'architecture.check': architecture_v22, 'agents.coordinate': agents_v22,
                'learning.evolve': learning_v22, 'compose.pipeline': compose_v22}
from fusion_studio_v20 import greatcircle, plan as fusion_plan, frame_svg as fusion_frame, render_video as fusion_render, iphone_export, PRESETS

# Each item has a concrete in-process implementation and a narrow allowed effect.
REGISTRY = {
 'qa.trace': ('Find attributed Red Rose decisions and corresponding native adapters; never invent original Q&A', 'read', 'builtin'),
 'roadmap.status': ('Report verified progress on the owner-approved 1,400-question roadmap by topic or question', 'read', 'builtin'),
 'fusion.route': ('Generate spherical route coordinates without imagery', 'read', 'builtin'),
 'fusion.plan': ('Plan original clay/map shots in explicit frames', 'read', 'builtin'),
 'fusion.frame': ('Generate an original illustrated SVG frame', 'read', 'pillow_cairosvg'),
 'fusion.render': ('Render a short original SVG illustrated MP4', 'write', 'pillow_cairosvg'),
 'media.iphone_export': ('Transcode authorized local video into AVC/AAC MP4', 'write', 'ffmpeg'),
 'knowledge.search': ('Search imported reference descriptions', 'read', 'database'),
 'knowledge.route': ('Match request to reference descriptions; not execute them', 'read', 'database'),
 'knowledge.stats': ('Count imported reference units', 'read', 'database'),
 'memory.recall': ('Retrieve saved private lessons', 'read', 'database'),
 'learning.record': ('Store an approved lesson tied to an observed execution', 'write', 'database'),
 'style.list': ('List saved style names', 'read', 'database'),
 'audio.analyze': ('Decode local speech audio and summarize amplitude envelope', 'read', 'ffmpeg'),
 'video.verify': ('Full decode and FFprobe check of local video', 'read', 'ffmpeg'),
 'video.scene_analyze': ('Detect approximate cuts in original local footage', 'read', 'ffmpeg'),
 'video.recut': ('Join approved source time ranges into a verified original-media MP4', 'write', 'ffmpeg'),
 'video.timeline_analyze': ('Combine approximate visual scene cuts with acoustic silence intervals', 'read', 'ffmpeg'),
 'video.edit_suggest': ('Suggest reviewable EDL based on acoustic activity and scene boundaries', 'read', 'ffmpeg'),
 'video.shot_score': ('Measure per-shot exposure, clipping, detail and motion; rank shots into a reviewable EDL', 'read', 'ffmpeg'),
 'video.preview': ('Validate storyboard and estimate bounded render work', 'read', 'cairosvg'),
 'video.produce': ('Render editable SVG storyboard to verified MP4', 'write', 'cairosvg'),
 'character.svg': ('Create standalone original IK character SVG', 'write', 'builtin'),
 'physics.simulate': ('Deterministic motion physics: fall, collision, friction, spring, projectile, cloth, motion blur, flow, shading, particles', 'read', 'builtin'),
 'math.geometry': ('Scene geometry: transforms, perspective, curves, aspect fit, depth of field, two-bone IK, camera paths, homography, timecode, lens distortion', 'read', 'builtin'),
 'science.compute': ('Exact units, smoothed derivatives, Jacobian IK, intrinsics, quaternions, FFT, z-buffer, seeded RNG, ODE solvers, model reports', 'read', 'builtin'),
 'thinking.reason': ('Structured thinking: first principles, alternatives, causal do(), weighted decisions with sensitivity, pre-mortem, budgets, plan gaps, lessons, PoC gate, aesthetic review', 'read', 'builtin'),
 'decision.make': ('Decision rules: intent state, confidence labels, tool choice, phase machine, blind review, conflict priority, failure log, tested routing, gaps, auditable records', 'read', 'builtin'),
 'code.analyze': ('Static code analysis on supplied source text: syntax, import cycles, duplicates, resources, masked secrets, races, tracebacks, complexity, boundaries, diff review', 'read', 'builtin'),
 'accounting.check': ('Decimal checks on owner-supplied records: bank reconciliation, duplicate invoices, trial balance, payroll, item codes, costing, cash flow, allocation, checklists, approvals', 'read', 'builtin'),
 'governance.audit': ('Skill governance: contracts, provenance cards, copy guard, overlaps, legacy-import audit, adapter reality, passports, approval lifecycle, snapshots, completion matrix', 'read', 'builtin'),
 'architecture.check': ('Architecture checks: CLI spec, versioned messages, distribution guard, dependency status, redacted config, cache keys, checkpoint resume, path portability, SemVer migrations', 'read', 'builtin'),
 'agents.coordinate': ('Agent coordination: task contract, stage DAG, roster, safe batches, critique, handoff check, injection guard, claim check, progress monitor, rigor level', 'read', 'builtin'),
 'learning.evolve': ('Evidence-based learning: similar errors, lesson ranking, reviewed rule proposals, capability gaps, regression cases, rule versions, lesson benefit, local-only guard, forget plans', 'read', 'builtin'),
 'compose.pipeline': ('Capability composition: SVG layers, audio-aware EDL, IK with physics, retrieve-then-dispatch, tenant accounting workflow, seeded variations, critique roles, contracts, proposals, originality', 'read', 'builtin'),
}
ALIASES = {
 'صلصال': ('fusion.plan','fusion.frame','fusion.render'),
 'خريطة': ('fusion.route','fusion.plan','fusion.render'),
 'آيفون': ('media.iphone_export',),
 'iphone': ('media.iphone_export',),
 'video': ('video.scene_analyze','video.recut','video.preview','video.produce','video.verify'),
 'render': ('video.preview','video.produce'),
 'cuts': ('video.scene_analyze','video.timeline_analyze','video.edit_suggest','video.recut'),
 'scene': ('video.scene_analyze',),
 'قص': ('video.scene_analyze','video.recut'),
 'edit': ('video.scene_analyze','video.recut'),
 'مونتاج': ('video.scene_analyze','video.timeline_analyze','video.edit_suggest','video.recut','video.preview','video.produce'),
 'فيديو': ('video.scene_analyze','video.timeline_analyze','video.edit_suggest','video.recut','video.preview','video.produce'),
 'تحريك': ('character.svg','video.preview'),
 'character': ('character.svg',),
 'شخصية': ('character.svg',),
 'speech': ('audio.analyze',),
 'audio': ('audio.analyze','video.timeline_analyze'),
 'silence': ('video.timeline_analyze','video.edit_suggest'),
 'صمت': ('video.timeline_analyze','video.edit_suggest'),
 'تلقائي': ('video.edit_suggest',),
 'quality': ('video.shot_score',),
 'جودة': ('video.shot_score',),
 'لقطات': ('video.shot_score','video.scene_analyze'),
 'shots': ('video.shot_score','video.scene_analyze'),
 'exposure': ('video.shot_score',),
 'إضاءة': ('video.shot_score',),
 'صوت': ('audio.analyze',),
 'بحث': ('knowledge.search','knowledge.route'),
 'knowledge': ('knowledge.search','knowledge.route'),
 'أسئلة': ('qa.trace','roadmap.status'),
 'roadmap': ('roadmap.status',),
 'فيزياء': ('physics.simulate',),
 'physics': ('physics.simulate',),
 'جاذبية': ('physics.simulate',),
 'نابض': ('physics.simulate',),
 'جسيمات': ('physics.simulate',),
 'هندسة': ('math.geometry',),
 'geometry': ('math.geometry',),
 'منظور': ('math.geometry',),
 'timecode': ('math.geometry',),
 'تايم كود': ('math.geometry',),
 'عمق المجال': ('math.geometry',),
 'رياضيات': ('math.geometry','science.compute'),
 'علوم': ('science.compute',),
 'science': ('science.compute',),
 'وحدات': ('science.compute',),
 'fft': ('science.compute',),
 'تردد': ('science.compute',),
 'بدائل': ('thinking.reason',),
 'سبب': ('thinking.reason',),
 'مصفوفة قرار': ('thinking.reason',),
 'قرار': ('decision.make','thinking.reason'),
 'ثقة': ('decision.make',),
 'تعارض': ('decision.make',),
 'كود': ('code.analyze',),
 'code': ('code.analyze',),
 'أسرار': ('code.analyze',),
 'diff': ('code.analyze',),
 'محاسبة': ('accounting.check',),
 'مطابقة': ('accounting.check',),
 'فواتير': ('accounting.check',),
 'ميزان': ('accounting.check',),
 'رواتب': ('accounting.check',),
 'تكلفة': ('accounting.check',),
 'حوكمة': ('governance.audit',),
 'ترخيص': ('governance.audit',),
 'نسب': ('governance.audit',),
 'معمارية': ('architecture.check',),
 'إعدادات': ('architecture.check',),
 'ترحيل': ('architecture.check',),
 'وكلاء': ('agents.coordinate',),
 'تسليم': ('agents.coordinate',),
 'حقن': ('agents.coordinate',),
 'دروس': ('learning.evolve','memory.recall'),
 'نسيان': ('learning.evolve',),
 'دمج': ('compose.pipeline',),
 'طبقات': ('compose.pipeline',),
 '1400': ('roadmap.status',),
 'خطة': ('roadmap.status',),
 'تقدم': ('roadmap.status',),
 'اجابات': ('qa.trace',),
 'إجابات': ('qa.trace',),
 'متطلبات': ('qa.trace',),
 'requirements': ('qa.trace',),
 'questions': ('qa.trace',),
 'معرفة': ('knowledge.search','knowledge.route'),
 'ذاكرة': ('memory.recall',),
 'memory': ('memory.recall',),
 'lesson': ('memory.recall','learning.record'),
 'تعلم': ('memory.recall','learning.record'),
 'درس': ('memory.recall','learning.record'),
}

def list_capabilities():
    result=[]
    for ident,(description,effect,dependency) in REGISTRY.items():
        if dependency == 'ffmpeg':ready = bool(shutil.which('ffmpeg') and shutil.which('ffprobe'))
        elif dependency == 'pillow_cairosvg':
            try:
                import cairosvg
                import PIL
                ready=bool(shutil.which('ffmpeg') and shutil.which('ffprobe'))
            except ImportError:ready=False
        elif dependency == 'cairosvg':
            try:
                import cairosvg
                ready = bool(shutil.which('ffmpeg') and shutil.which('ffprobe'))
            except ImportError:ready=False
        else:ready=True
        result.append({'id':ident,'description':description,'effect':effect,
                       'dependency':dependency,'ready':ready,'status':'adapter_implemented',
                       'verification':'runtime_check_required'})
    return result


def plan_task(db, task, max_refs=4):
    """Propose explicit native adapters; references never become executable IDs."""
    if not isinstance(task,str) or not task.strip() or len(task)>1000:
        raise ValueError('task must be 1..1000 characters')
    text=task.casefold()
    candidates=[]
    for keyword,actions in ALIASES.items():
        if keyword in text:
            for action in actions:
                if action not in candidates:candidates.append(action)
    research=knowledge_route(db,task,max_refs)
    return {'task':task,'status':'planned_not_executed',
            'suggested_native_adapters':candidates,
            'missing_inputs':'choose capability ID and supply its explicit parameters',
            'knowledge_matches':research['matched_candidates'],
            'reference_titles':[{'id':r['id'],'title':r['title'],'license':r['license']} for r in research['references']],
            'legacy_executables_called':False}


def _require_dict(params):
    if not isinstance(params,dict) or len(params)>24:
        raise ValueError('params must be a small JSON object')
    return params


def _audit(db, action, params, status, *, evidence=None):
    # Store only a params HASH and result evidence; never raw user data, audio or secrets.
    db.execute('''CREATE TABLE IF NOT EXISTS capability_execution_audit (
      id INTEGER PRIMARY KEY, time_utc TEXT NOT NULL, capability TEXT NOT NULL,
      params_sha256 TEXT NOT NULL, outcome TEXT NOT NULL, evidence_sha256 TEXT)''')
    digest=hashlib.sha256(json.dumps(params,sort_keys=True,default=str,ensure_ascii=False).encode()).hexdigest()
    edigest=hashlib.sha256(json.dumps(evidence,sort_keys=True,default=str).encode()).hexdigest() if evidence else None
    db.execute('INSERT INTO capability_execution_audit(time_utc,capability,params_sha256,outcome,evidence_sha256) VALUES(?,?,?,?,?)',
               (datetime.now(timezone.utc).isoformat(), action,digest,status,edigest))
    db.commit()
    return db.execute('SELECT last_insert_rowid()').fetchone()[0]

def _guard_keys(params,allowed,required=()):
    unknown=set(params)-set(allowed)
    if unknown:raise ValueError('unknown parameters: '+', '.join(sorted(unknown)))
    missing=set(required)-set(params)
    if missing:raise ValueError('missing parameters: '+', '.join(sorted(missing)))


def execute(db, capability, params, *, approve_write=False):
    """Execute explicit native capability, with no arbitrary shell/agent dispatch."""
    if capability not in REGISTRY:raise ValueError('unknown or not implemented capability: '+str(capability))
    params=_require_dict(params)
    effect=REGISTRY[capability][1]
    if effect=='write' and not approve_write:
        return {'capability':capability,'status':'approval_required',
                'detail':'Use --approve-write after reviewing output destination; nothing executed.'}
    if capability=='fusion.route':
        _guard_keys(params,('from','to','samples'),('from','to'))
        output=greatcircle(params['from'],params['to'],params.get('samples',25))
    elif capability=='fusion.plan':
        _guard_keys(params,('scenes','fps','preset'),('scenes',))
        output=fusion_plan(params['scenes'],params.get('fps',24),params.get('preset','iphone-vertical'))
    elif capability=='fusion.frame':
        _guard_keys(params,('scenes','fps','preset','frame'),('scenes','frame'))
        project=fusion_plan(params['scenes'],params.get('fps',24),params.get('preset','iphone-vertical'))
        output={'frame':params['frame'],'svg':fusion_frame(project,params['frame']),
                'format':'original-illustration-svg','user_fonts_embedded':False}
    elif capability=='fusion.render':
        _guard_keys(params,('scenes','fps','preset','output'),('scenes','output'))
        project=fusion_plan(params['scenes'],params.get('fps',24),params.get('preset','iphone-vertical'))
        output=fusion_render(project,params['output'],approve_write=True)
        output['qa']=verify_video(output['output'],expected_fps=project['fps'],
                                  width=project['width'],height=project['height'])
    elif capability=='media.iphone_export':
        _guard_keys(params,('source','output','preset'),('source','output'))
        output=iphone_export(params['source'],params['output'],approve_write=True,
                             preset=params.get('preset','iphone-vertical'))
        width,height=PRESETS[output['preset']]
        output['qa']=verify_video(output['output'],width=width,height=height)
    elif capability=='qa.trace':
        _guard_keys(params,('question_id',))
        output=qa_trace(params.get('question_id'),registry=REGISTRY)
    elif capability in PURE_MODULES:
        _guard_keys(params,('op','params'),('op',))
        module=PURE_MODULES[capability]
        if params['op'] not in module.OPS:
            raise ValueError('unknown op for '+capability+'; allowed: '+', '.join(module.OPS))
        output=module.run(params['op'],params.get('params',{}))
    elif capability=='roadmap.status':
        _guard_keys(params,('topic','question'))
        if 'topic' in params and 'question' in params:
            raise ValueError('give topic or question, not both')
        if 'topic' in params:
            output=roadmap_1400.explain_topic(params['topic'],registry=REGISTRY)
        elif 'question' in params:
            output=roadmap_1400.explain_question(params['question'],registry=REGISTRY)
        else:
            output=roadmap_1400.summary(registry=REGISTRY)
    elif capability=='knowledge.search':
        _guard_keys(params,('query','limit'),('query',))
        output=find_fused(db,str(params['query']),int(params.get('limit',10)))
    elif capability=='knowledge.route':
        _guard_keys(params,('task','limit'),('task',))
        output=knowledge_route(db,str(params['task']),int(params.get('limit',6)))
    elif capability=='knowledge.stats':
        _guard_keys(params,())
        output=stats_fused(db)
    elif capability=='memory.recall':
        _guard_keys(params,('query','limit'),('query',))
        query=str(params['query'])
        if not query.strip():raise ValueError('memory query required')
        lim=max(1,min(int(params.get('limit',10)),50))
        rows=db.execute('SELECT id,created,category,content FROM memories WHERE content LIKE ? ORDER BY id DESC LIMIT ?',
                        ('%'+query+'%',lim)).fetchall()
        output=[{'id':r[0],'created':r[1],'category':r[2],'content':r[3],'source':'memory'} for r in rows]
        # Explicit evidence-linked lessons are stored locally and can be recalled.
        db.execute('''CREATE TABLE IF NOT EXISTS learning_lessons(
          id INTEGER PRIMARY KEY, created TEXT NOT NULL, category TEXT NOT NULL,
          content TEXT NOT NULL, content_hash TEXT NOT NULL,
          source_execution_id INTEGER NOT NULL,
          UNIQUE(source_execution_id,content_hash))''')
        learned=db.execute('''SELECT id,created,category,content,source_execution_id FROM learning_lessons
          WHERE content LIKE ? ORDER BY id DESC LIMIT ?''',('%'+query+'%',lim)).fetchall()
        output += [dict(zip(('id','created','category','content','source_execution_id'),r),source='evidence_linked_lesson') for r in learned]
        output=sorted(output,key=lambda r:r['created'],reverse=True)[:lim]
    elif capability=='learning.record':
        _guard_keys(params,('lesson','source_audit_id','category'),('lesson','source_audit_id'))
        lesson=params['lesson']
        if not isinstance(lesson,str) or not 1 <= len(lesson.strip()) <= 2000:
            raise ValueError('lesson must be 1..2000 characters')
        category=params.get('category','lesson')
        if category not in ('lesson','correction','failure','improvement'):
            raise ValueError('invalid learning category')
        audit_id=params['source_audit_id']
        if type(audit_id) is not int or audit_id < 1:
            raise ValueError('source_audit_id must be a positive integer')
        audit_row=db.execute('SELECT outcome FROM capability_execution_audit WHERE id=?',(audit_id,)).fetchone()
        if not audit_row or audit_row[0]!='executed':
            raise ValueError('lesson requires an earlier successfully executed capability audit ID')
        db.execute('''CREATE TABLE IF NOT EXISTS learning_lessons(
          id INTEGER PRIMARY KEY, created TEXT NOT NULL, category TEXT NOT NULL,
          content TEXT NOT NULL, content_hash TEXT NOT NULL,
          source_execution_id INTEGER NOT NULL,
          UNIQUE(source_execution_id,content_hash))''')
        checksum=hashlib.sha256(lesson.strip().encode()).hexdigest()
        cursor=db.execute('''INSERT OR IGNORE INTO learning_lessons
          (created,category,content,content_hash,source_execution_id) VALUES(?,?,?,?,?)''',
          (datetime.now(timezone.utc).isoformat(),category,lesson.strip(),checksum,audit_id))
        db.commit()
        output={'recorded':bool(cursor.rowcount),'linked_execution_id':audit_id,
                'lesson_sha256':checksum,'storage':'private_local_sqlite'}
    elif capability=='style.list':
        _guard_keys(params,())
        output=list_styles(db)
    elif capability=='audio.analyze':
        _guard_keys(params,('audio',),('audio',))
        lv=levels_from_audio(params['audio'])
        output={'duration_seconds':round(len(lv)/20,3),'samples':len(lv),
                'peak':max(lv),'mean':round(sum(lv)/len(lv),5),
                'silence_ratio':round(sum(x<.1 for x in lv)/len(lv),5),
                'method':'20-Hz RMS amplitude, no word or phoneme alignment'}
    elif capability=='video.verify':
        _guard_keys(params,('video','fps','width','height'),('video',))
        output=verify_video(params['video'],expected_fps=params.get('fps'),
                            width=params.get('width'),height=params.get('height'))
    elif capability=='video.scene_analyze':
        _guard_keys(params,('source','threshold','sample_fps','min_shot_seconds'),('source',))
        output=analyze_cuts(params['source'],
                            threshold=params.get('threshold',.23),
                            sample_fps=params.get('sample_fps',6),
                            min_shot_seconds=params.get('min_shot_seconds',.65))
    elif capability=='video.timeline_analyze':
        _guard_keys(params,('source','threshold','sample_fps','noise_db','min_silence'),('source',))
        output=timeline_analyze(params['source'],threshold=params.get('threshold',.23),
                sample_fps=params.get('sample_fps',6),noise_db=params.get('noise_db',-35),
                min_silence=params.get('min_silence',.30))
    elif capability=='video.edit_suggest':
        _guard_keys(params,('source','max_clips','max_duration','min_audible_ratio','threshold','sample_fps','noise_db','min_silence'),('source',))
        output=suggest_edit(params['source'],max_clips=params.get('max_clips',3),
                max_duration=params.get('max_duration',30.),
                min_audible_ratio=params.get('min_audible_ratio',.20),
                threshold=params.get('threshold',.23),
                sample_fps=params.get('sample_fps',6),noise_db=params.get('noise_db',-35),
                min_silence=params.get('min_silence',.30))
    elif capability=='video.shot_score':
        _guard_keys(params,('source','max_clips','max_duration','threshold','sample_fps','noise_db','min_silence'),('source',))
        output=score_shots(params['source'],max_clips=params.get('max_clips',3),
                max_duration=params.get('max_duration',30.),
                threshold=params.get('threshold',.23),
                sample_fps=params.get('sample_fps',6),noise_db=params.get('noise_db',-35),
                min_silence=params.get('min_silence',.30))
    elif capability=='video.recut':
        _guard_keys(params,('source','segments','output','fps'),('source','segments','output'))
        output=recut(params['source'],params['segments'],params['output'],fps=params.get('fps',24))
    elif capability in ('video.preview','video.produce'):
        fields=('storyboard','output','fps','width','height','audio','srt','profiles',
                'lip_sync','viseme_sync','words_json','overwrite')
        _guard_keys(params,fields,('storyboard',) if capability=='video.preview' else ('storyboard','output'))
        opts={key:params[key] for key in ('audio','srt','profiles','lip_sync','viseme_sync','words_json') if key in params}
        if capability=='video.preview':
            shots,metadata=prepare_project(params['storyboard'],**opts)
            output={'status':'validated_not_rendered','budget':budget(shots,int(params.get('fps',24)),
                int(params.get('width',540)),int(params.get('height',960))),
                'character_profiles':metadata['locked_characters'],
                'voice_sync':metadata['voice_sync'], 'viseme_sync':metadata['viseme_sync']}
        else:
            output=render_project(params['storyboard'],params['output'],fps=int(params.get('fps',24)),
              width=int(params.get('width',540)),height=int(params.get('height',960)),
              overwrite=params.get('overwrite',False),**opts)
    elif capability=='character.svg':
        _guard_keys(params,('output','x','y','scale','phase','actor'),('output',))
        path=Path(params['output']).expanduser().resolve()
        if path.suffix.lower()!='.svg' or path.is_file() or not path.parent.is_dir():
            raise ValueError('output needs a new .svg file in an existing directory')
        svg=rig_character(float(params.get('x',160)),float(params.get('y',280)),
                          float(params.get('scale',1)),float(params.get('phase',0)),params.get('actor',{}))
        full='<svg xmlns="http://www.w3.org/2000/svg" width="320" height="568" viewBox="0 0 320 568"><rect width="100%" height="100%" fill="#101827"/>'+svg+'</svg>'
        path.write_text(full,encoding='utf-8')
        output={'written':True,'format':'svg','sha256':hashlib.sha256(full.encode()).hexdigest(),
                'output':str(path)}
    else:raise AssertionError('unreachable capability handler')
    # Audit explicit invocation without content. This is NOT autonomous self-learning.
    audit_id=_audit(db,capability,params,'executed',evidence={'capability':capability,'result_type':type(output).__name__})
    return {'audit_id':audit_id,'capability':capability,'status':'executed','effect':effect,'result':output,
            'legacy_runtime_called':False}


def audit_summary(db):
    db.execute('''CREATE TABLE IF NOT EXISTS capability_execution_audit (
      id INTEGER PRIMARY KEY, time_utc TEXT NOT NULL, capability TEXT NOT NULL,
      params_sha256 TEXT NOT NULL, outcome TEXT NOT NULL, evidence_sha256 TEXT)''')
    rows=db.execute('SELECT capability,count(*) FROM capability_execution_audit GROUP BY capability').fetchall()
    has_lessons=bool(db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='learning_lessons'").fetchone())
    n_lessons=db.execute('SELECT COUNT(*) FROM learning_lessons').fetchone()[0] if has_lessons else 0
    return {'native_adapters_registered':len(REGISTRY),'implemented_ids':sorted(REGISTRY),
            'execution_counts':dict(rows),'evidence_linked_lessons':n_lessons,
            'imported_references_are_not_executables':True,
            'requirements_1400_fully_verified':False,
            'warning':'An adapter is a working function, not proof of all claimed upstream skills.'}
