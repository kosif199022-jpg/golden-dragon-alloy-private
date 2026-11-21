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
from shot_quality_v18 import shot_quality

# Each item has a concrete in-process implementation and a narrow allowed effect.
REGISTRY = {
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
 'video.shot_quality': ('Measure per-shot detail, exposure, contrast and motion; propose reviewable EDL', 'read', 'ffmpeg'),
 'video.preview': ('Validate storyboard and estimate bounded render work', 'read', 'cairosvg'),
 'video.produce': ('Render editable SVG storyboard to verified MP4', 'write', 'cairosvg'),
 'character.svg': ('Create standalone original IK character SVG', 'write', 'builtin'),
}
ALIASES = {
 'video': ('video.scene_analyze','video.recut','video.preview','video.produce','video.verify'),
 'render': ('video.preview','video.produce'),
 'cuts': ('video.scene_analyze','video.timeline_analyze','video.edit_suggest','video.shot_quality','video.recut'),
 'scene': ('video.scene_analyze',),
 'قص': ('video.scene_analyze','video.recut'),
 'edit': ('video.scene_analyze','video.recut'),
 'مونتاج': ('video.scene_analyze','video.timeline_analyze','video.edit_suggest','video.shot_quality','video.recut','video.preview','video.produce'),
 'فيديو': ('video.scene_analyze','video.timeline_analyze','video.edit_suggest','video.recut','video.preview','video.produce'),
 'تحريك': ('character.svg','video.preview'),
 'character': ('character.svg',),
 'شخصية': ('character.svg',),
 'speech': ('audio.analyze',),
 'audio': ('audio.analyze','video.timeline_analyze'),
 'silence': ('video.timeline_analyze','video.edit_suggest'),
 'صمت': ('video.timeline_analyze','video.edit_suggest'),
 'تلقائي': ('video.edit_suggest',),
 'quality': ('video.shot_quality',),
 'جودة': ('video.shot_quality',),
 'لقطة': ('video.shot_quality',),
 'لقطات': ('video.shot_quality',),
 'shots': ('video.shot_quality',),
 'صوت': ('audio.analyze',),
 'بحث': ('knowledge.search','knowledge.route'),
 'knowledge': ('knowledge.search','knowledge.route'),
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
    if capability=='knowledge.search':
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
    elif capability=='video.shot_quality':
        _guard_keys(params,('source','threshold','sample_fps','min_shot_seconds','max_clips','max_duration','min_score'),('source',))
        output=shot_quality(params['source'],threshold=params.get('threshold',.23),
                sample_fps=params.get('sample_fps',4),
                min_shot_seconds=params.get('min_shot_seconds',.65),
                max_clips=params.get('max_clips',3),max_duration=params.get('max_duration',30.),
                min_score=params.get('min_score',.5))
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
