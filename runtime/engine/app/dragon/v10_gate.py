"""Seven-stage, tamper-evident (not signed) video job gate for Black Dragon v10.

Stages are explicit: brief → concept → color-design → shots → produce → qa-color → deliver.
Records protect local evidence with SHA256. They do NOT manufacture execution receipts
or certify aesthetic quality. Running paid APIs, installing, or publishing is never automatic.
"""
from __future__ import annotations
import hashlib
import json
import re
import subprocess
import shutil
import sys
from pathlib import Path
from .v10_media import digest
from .v10_cognition import validate_decision

STAGES=("brief","concept","color-design","shots","produce","qa-color","deliver")
BRIEF=("goal","audience","platform","aspect","duration_s","message","hero")
HEX=re.compile(r'^#[0-9a-fA-F]{6}$')


def _canonical(doc)->bytes:
    return json.dumps(doc,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')


def _sha_bytes(doc)->str:
    return hashlib.sha256(_canonical(doc)).hexdigest()


def _read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def _atomic(path, doc):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    t=p.with_suffix(p.suffix+'.tmp')
    t.write_text(json.dumps(doc,ensure_ascii=False,indent=2,sort_keys=True),encoding='utf-8')
    t.replace(p)


def _state(job):
    p=Path(job)/'job-v10.json'
    if not p.is_file():raise ValueError('job not initialized; use gate init')
    d=_read(p)
    if d.get('schema')!='black-dragon.v10/job':raise ValueError('wrong job format')
    return d


def _brief_validation(b):
    if not isinstance(b,dict):return ['brief must be an object']
    missing=[x for x in BRIEF if not str(b.get(x,'')).strip()]
    errors=['missing brief: '+', '.join(missing)] if missing else []
    try:
        if float(b.get('duration_s',0))<=0:errors.append('duration_s must be positive')
    except (ValueError,TypeError):errors.append('invalid duration_s')
    return errors


def init(job, brief_path):
    j=Path(job).resolve();b=_read(brief_path)
    errors=_brief_validation(b)
    if errors:raise ValueError('; '.join(errors))
    if (j/'job-v10.json').exists():raise ValueError('job exists; never overwrite evidence')
    (j/'inputs').mkdir(parents=True,exist_ok=True)
    _atomic(j/'inputs'/'brief.json',b)
    s={'schema':'black-dragon.v10/job','version':'10.0.0',
       'brief':b,'brief_sha256':_sha_bytes(b),'stages':[],
       'source_media_modified':False,'note':'SHA256 proves local file integrity only; it is not an external signature.'}
    _atomic(j/'job-v10.json',s)
    return {'kind':'v10-gate-init','job':str(j),'stages_complete':0,'next_stage':'brief'}


def _is_file(path):return isinstance(path,str) and Path(path).is_file()


def _validate_stage(stage, doc, state):
    if not isinstance(doc,dict):return ['stage data must be a JSON object']
    errs=[]
    if stage=='brief':
        errs=_brief_validation(doc)
        if _sha_bytes(doc)!=state['brief_sha256']:errs.append('brief changed since init')
    elif stage=='concept':
        errs=validate_decision(doc)
        if not str(doc.get('hook','')).strip():errs.append('concept hook is required')
    elif stage=='color-design':
        colors=doc.get('palette')
        if not isinstance(colors,list) or len(colors)!=3 or not all(isinstance(c,str) and HEX.fullmatch(c) for c in colors):
            errs.append('palette must be three #RRGGBB values (base/support/accent)')
        if not str(doc.get('accent_on','')).strip():errs.append('accent_on element required')
        if doc.get('ratios')!=[60,30,10]:errs.append('color design ratios should be [60,30,10]')
    elif stage=='shots':
        shots=doc.get('shots')
        if not isinstance(shots,list) or not shots:errs.append('shots must be a nonempty EDL list')
        else:
            end=0.0
            for i,s in enumerate(shots):
                try:
                    a,b=float(s['start_s']),float(s['end_s'])
                    if a!=end or b<=a:errs.append(f'shot {i} has a gap/overlap or nonpositive length')
                    if not str(s.get('reason','')).strip() or not str(s.get('what','')).strip():
                        errs.append(f'shot {i} must explain what/why')
                    end=b
                except (ValueError,KeyError,TypeError):errs.append(f'shot {i} invalid')
            if abs(end-float(state['brief']['duration_s']))>0.001:errs.append('EDL does not cover intended duration')
        if not _is_file(doc.get('storyboard')):errs.append('a real storyboard file must exist')
        if not (doc.get('preview_approved') is True or state['brief'].get('execute_directly') is True):
            errs.append('preview approval is required before final render')
    elif stage=='produce':
        if not _is_file(doc.get('video_file')):errs.append('video_file must exist')
        if not str(doc.get('renderer','')).strip():errs.append('renderer description required')
        if doc.get('paid',False) and doc.get('spend_approved') is not True:errs.append('paid action needs explicit spend approval')
        receipt=doc.get('render_receipt')
        if receipt:
            if not _is_file(receipt):errs.append('render_receipt path missing')
            else:
                rec=_read(receipt)
                if rec.get('kind')!='black-dragon.v10/render-run' or rec.get('exit_code')!=0:
                    errs.append('not a successful v10 render-run receipt')
                elif _is_file(doc.get('video_file')) and rec.get('output_sha256')!=digest(Path(doc['video_file'])):
                    errs.append('render receipt does not match output hash')
    elif stage=='deliver':
        for k in ('summary','executed','not_executed'):
            if k not in doc:errs.append(f'missing deliver field {k}')
        if doc.get('rights_reviewed') is not True:errs.append('rights_reviewed true required')
    return errs


def _save_record(j,state,stage,data,artifacts=()):
    records=[]
    for path in artifacts:
        p=Path(path).resolve()
        if not p.is_file():raise ValueError(f'cannot attest missing artifact: {p}')
        records.append({'path':str(p),'sha256':digest(p),'bytes':p.stat().st_size})
    record={'stage':stage,'data':data,'data_sha256':_sha_bytes(data),'artifacts':records}
    record['receipt_sha256']=_sha_bytes(record)
    _atomic(j/'stages'/f'{stage}.json',record)
    state['stages'].append({'stage':stage,'receipt_path':str(j/'stages'/f'{stage}.json'),
                            'receipt_sha256':digest(j/'stages'/f'{stage}.json')})
    _atomic(j/'job-v10.json',state)
    return {'stage':stage,'recorded':True,'artifact_count':len(records),'receipt':str(j/'stages'/f'{stage}.json')}


def record(job,stage,data_path):
    j=Path(job).resolve();s=_state(j)
    want=STAGES[len(s['stages'])] if len(s['stages'])<len(STAGES) else None
    if stage!=want:raise ValueError(f'expected stage {want}, got {stage}; no stage may be skipped')
    if stage=='qa-color':raise ValueError('use gate qa for measured output QA; manual QA records are forbidden')
    d=_read(data_path)
    errors=_validate_stage(stage,d,s)
    if errors:raise ValueError('; '.join(errors))
    att=[]
    if stage=='shots':att=[d['storyboard']]
    elif stage=='produce':
        att=[d['video_file']]
        if d.get('render_receipt'):att.append(d['render_receipt'])
    return _save_record(j,s,stage,d,att)


def qa(job,*,expect=None,deep=True):
    j=Path(job).resolve();s=_state(j)
    if len(s['stages'])!=STAGES.index('qa-color'):raise ValueError('expected stage qa-color after produce')
    produced=_read(j/'stages'/'produce.json')['data']
    path=Path(produced['video_file']).resolve()
    if not path.is_file():raise ValueError('produced video missing')
    from .verify import probe_file
    x=probe_file(path,expect=expect or s['brief'].get('resolution') or
                 ('1080x1920' if s['brief']['aspect']=='9:16' else '1920x1080' if s['brief']['aspect']=='16:9' else None),
                 duration=float(s['brief']['duration_s']),black=deep)
    # Strict 9:16, if no custom-resolution override.
    require_size=expect or s['brief'].get('resolution') or ('1080x1920' if s['brief']['aspect']=='9:16' else None)
    ok=bool(x.get('ok')) and bool(deep)
    if require_size and f"{x.get('width')}x{x.get('height')}"!=require_size:ok=False
    from .v10_color import analyze as analyze_color
    color_doc=_read(j/'stages'/'color-design.json')['data']
    color_result=analyze_color(path,duration_s=float(s['brief']['duration_s']),palette=color_doc['palette'])
    if color_result['sampled_frames']<color_result['requested_frames']:
        ok=False
    if color_doc.get('enforce_pixel_ratio') is True:
        ok=ok and color_result['passes_approximate_accent_range'] and color_result['planned_contrast_gte_40']
    data={'video_file':str(path),'sha256':digest(path),'technical_qa_pass':ok,
          'deep_black_scan':bool(deep),'requested_resolution':require_size,
          'technical_verifier':{'errors':x.get('errors',[]),'warnings':x.get('warnings',[]),
                                 'width':x.get('width'),'height':x.get('height'),
                                 'frames':(x.get('frame_check') or {}).get('frames'),
                                 'black':x.get('black',{})},
          'color_qa':color_result,
          'color_policy':'enforced' if color_doc.get('enforce_pixel_ratio') is True else 'measured-and-reported',
          'aesthetic_approval':'not_proven_by_technical_scan'}
    if not ok:raise ValueError('technical QA failed: '+json.dumps(data['technical_verifier'],ensure_ascii=False)[:800])
    return _save_record(j,s,'qa-color',data,[path])


def check(job):
    j=Path(job).resolve();s=_state(j);issues=[];complete=[]
    if _sha_bytes(s['brief'])!=s['brief_sha256']:
        issues.append('stored brief hash changed')
    if _sha_bytes(_read(j/'inputs'/'brief.json'))!=s['brief_sha256']:
        issues.append('input brief changed')
    for idx,entry in enumerate(s['stages']):
        if idx>=len(STAGES) or entry.get('stage')!=STAGES[idx]:
            issues.append('stage order changed');continue
        p=j/'stages'/f"{entry['stage']}.json"
        if not p.is_file() or digest(p)!=entry.get('receipt_sha256'):
            issues.append(f"{entry['stage']}: record missing or tampered");continue
        r=_read(p)
        h=r.pop('receipt_sha256',None)
        if _sha_bytes(r)!=h or r.get('data_sha256')!=_sha_bytes(r.get('data')):
            issues.append(f"{entry['stage']}: data hash tampered");continue
        for a in r.get('artifacts',[]):
            file=Path(a['path'])
            if not file.is_file() or digest(file)!=a['sha256']:
                issues.append(f"{entry['stage']}: artifact missing or changed: {file.name}")
        if entry['stage']=='qa-color':
            if not r['data'].get('technical_qa_pass') or not r['data'].get('deep_black_scan'):
                issues.append('qa-color: technical evidence missing')
            prod=_read(j/'stages'/'produce.json')['data'] if (j/'stages'/'produce.json').is_file() else {}
            if Path(prod.get('video_file','/nonexistent')).resolve()!=Path(r['data']['video_file']).resolve():
                issues.append('qa refers to another file')
        complete.append(entry['stage'])
    if len(s['stages'])!=len(STAGES):issues.append(f'incomplete stages: {len(s["stages"])}/{len(STAGES)}')
    prod=_read(j/'stages'/'produce.json')['data'] if (j/'stages'/'produce.json').is_file() else {}
    executed_proven=bool(prod.get('render_receipt')) and not any('produce' in x for x in issues)
    return {'kind':'black-dragon.v10/gate-check','pass':not issues,
            'completed_stages':complete,'total_stages':len(STAGES),
            'render_executed_with_receipt':executed_proven,
            'visual_creative_review':'separate human/editor review required',
            'errors':issues,'local_integrity_only':True}


def render_run(output,argv,*,execute=False,overwrite=False,job=None):
    """Explicit local ffmpeg execution, no shell. Never calls paid services or external URLs."""
    if not argv:raise ValueError('missing command after --')
    command=argv[1:] if argv[0]=='--' else argv
    name=Path(command[0]).name.lower()
    if name not in {'ffmpeg','ffmpeg.exe'}:
        raise ValueError('only the local ffmpeg executable is allowed; other tools run separately')
    if any(re.search(r'\b(?:https?://|rtmp://|ftp://|s3://)',arg,re.I) for arg in command):
        raise ValueError('remote network inputs/outputs are disabled')
    p=Path(output).resolve()
    if p.exists() and not overwrite:raise ValueError('output exists; refusing to overwrite user media')
    if not execute:return {'kind':'black-dragon.v10/render-preview','execution_performed':False,'command':command,'out':str(p)}
    if job is None:raise ValueError('render execution requires --job with a recorded, approved storyboard')
    state=_state(job)
    if len(state['stages'])!=STAGES.index('produce'):
        raise ValueError('render execution is only allowed after an approved shots stage and before produce')
    check_state=check(job)
    if check_state['errors'] and any('tamper' in e or 'changed' in e or 'missing' in e for e in check_state['errors'] if not e.startswith('incomplete stages:')):
        raise ValueError('prior job evidence changed; refuse render')
    if not shutil.which(command[0]):raise ValueError('ffmpeg executable not installed')
    c=subprocess.run(command,capture_output=True,text=True,timeout=900)
    result={'kind':'black-dragon.v10/render-run','command':command,'exit_code':c.returncode,
            'stdout_tail':c.stdout[-3000:],'stderr_tail':c.stderr[-3000:],
            'output_file':str(p),'output_sha256':digest(p) if p.is_file() else None,
            'executed':True}
    if c.returncode!=0 or not p.is_file():raise RuntimeError('render failed: '+c.stderr[-650:])
    return result
