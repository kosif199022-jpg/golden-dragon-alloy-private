"""Expert Council bridge (v10.4): role scaffold, evidence-aware review, private lessons.

No agents, paid services, third-party providers, or project code are executed here.
A passed review is a schema/integrity check, not proof of an expert opinion.
"""
from __future__ import annotations
import datetime as dt
import hashlib
import json
import math
import os
import re
import tempfile
from pathlib import Path

DOMAINS = ('editing', 'cinematography', 'directing', 'literary', 'general', 'software', 'accounting', 'strategy')
SIZES = (3, 5, 7)
LENSES = {
 'editing': ('story-emotion', 'rhythm-continuity', 'audio-accessibility', 'audience', 'red-team', 'feasibility', 'outside-view'),
 'cinematography': ('composition-light', 'exposure-camera', 'continuity-color', 'audience', 'red-team', 'feasibility', 'outside-view'),
 'directing': ('story-objective', 'actor-blocking', 'visual-coverage', 'audience', 'red-team', 'feasibility', 'outside-view'),
 'literary': ('close-reading', 'structure-rhetoric', 'style-context', 'audience', 'red-team', 'feasibility', 'outside-view'),
 'general': ('domain-specialist', 'independent-method', 'alternative-framing', 'audience', 'red-team', 'feasibility', 'outside-view'),
 'software': ('architecture', 'testing-security', 'operability', 'user', 'red-team', 'feasibility', 'outside-view'),
 'accounting': ('standards-interpretation', 'controls-evidence', 'reconciliation', 'stakeholder', 'red-team', 'feasibility', 'outside-view'),
 'strategy': ('first-principles', 'base-rates', 'opportunity-cost', 'stakeholder', 'red-team', 'feasibility', 'outside-view'),
}

def _text(v: object, limit: int=4000) -> bool:
    return isinstance(v, str) and bool(v.strip()) and len(v) <= limit


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as fh:
        for part in iter(lambda: fh.read(1024*1024), b''):
            h.update(part)
    return h.hexdigest()


def _safe_file(root: Path, relative: str) -> Path:
    if not _text(relative, 1000):
        raise ValueError('empty evidence file path')
    raw = Path(relative)
    if raw.is_absolute() or '..' in raw.parts:
        raise ValueError('absolute or traversing evidence path')
    root = root.resolve()
    result = (root/raw).resolve(strict=True)
    if not result.is_relative_to(root) or not result.is_file():
        raise ValueError('evidence outside packet directory or not a file')
    if result.stat().st_size > 100*1024*1024:
        raise ValueError('evidence file exceeds 100MiB limit')
    return result


def plan(task: str, domain: str='general', size: int=5) -> dict:
    if not _text(task, 10000): raise ValueError('task is required (1..10000 chars)')
    if not _text(domain, 80): raise ValueError('domain is required')
    if size not in SIZES: raise ValueError('council size must be 3, 5 or 7')
    seq = LENSES.get(domain, LENSES['general'])
    # 3 seats: specialist, audience, skeptic. 5 seats: two specialists, audience, skeptic, executor.
    indexes = {3:(0,3,4), 5:(0,1,3,4,5), 7:(0,1,2,3,4,5,6)}[size]
    seats = [{'id':f'seat-{i+1}', 'lens':seq[j],
              'required_submission':{'position':'', 'observations':[{'claim':'', 'locator':'', 'action':''}],
                                     'confidence':None}} for i,j in enumerate(indexes)]
    return {'kind':'black-dragon.v10.4/council-plan','task':task.strip(),'domain':domain,'size':size,
            'seats':seats,'rounds':['recall-existing-lessons','independent-judgments','steelman-disagreements',
                                   'red-team-and-evidence','chair-verdict-and-dissent','record-corrections'],
            'domain_reference':{'editing':'editing.md','cinematography':'cinematography.md',
                                'directing':'directing.md','literary':'literary-criticism.md'}.get(domain, 'personas.md (generic council construction)'),
            'gate':'Do not claim a council convened until round-one opinions and evidence have been supplied.',
            'agents_called':False,'actual_expert_participation':False,'opinions_generated':False,
            'requires_paid_api':False,'source':'uploaded expert-council SKILL.md and council-protocol.md'}


def audit(packet: object, directory: Path) -> dict:
    failures, warnings, evidence = [], [], []
    if not isinstance(packet, dict): raise ValueError('review packet must be JSON object')
    task, domain, size = packet.get('task'), packet.get('domain'), packet.get('size')
    if not _text(task):failures.append('missing task')
    if not _text(domain,80):failures.append('missing domain')
    if type(size) is not int or size not in SIZES:failures.append('size must be 3, 5 or 7')
    seats = packet.get('round1')
    if not isinstance(seats, list):
        seats=[]; failures.append('round1 independent judgments required as array')
    if type(size) is int and size in SIZES and len(seats) != size:
        failures.append(f'exactly {size} round1 seats required')
    ids, lenses, claims = [], [], []
    for index, seat in enumerate(seats):
        if not isinstance(seat, dict):failures.append(f'seat {index} is not object');continue
        sid,lens=seat.get('seat_id'),seat.get('lens')
        if not _text(sid, 80):failures.append(f'seat {index}: missing seat_id')
        else:ids.append(sid)
        if not _text(lens,80):failures.append(f'seat {index}: missing lens')
        else:lenses.append(lens.casefold().strip())
        if not _text(seat.get('position')): failures.append(f'seat {index}: missing position')
        c=seat.get('confidence')
        if type(c) not in (int,float) or not math.isfinite(c) or not 0<=c<=1:
            failures.append(f'seat {index}: confidence must be 0..1')
        observations=seat.get('observations')
        if not isinstance(observations,list) or not observations:
            failures.append(f'seat {index}: observations required')
            continue
        for j,obs in enumerate(observations):
            if not isinstance(obs,dict):failures.append(f'seat {index}/observation {j} must be object');continue
            for name in ('claim','locator','action'):
                if not _text(obs.get(name)):
                    failures.append(f'seat {index}/observation {j}: missing {name}')
            if _text(obs.get('claim')):claims.append(obs['claim'].strip().casefold())
    if len(ids)!=len(set(ids)):failures.append('duplicate seat IDs')
    if len(lenses)!=len(set(lenses)):failures.append('duplicate seat lenses; perspectives must differ')
    if len(claims)!=len(set(claims)):failures.append('duplicate findings across independent seats')
    if seats and not any('red' in x or 'متشكك' in x for x in lenses):
        failures.append('red-team seat required')
    if seats and not any('audience' in x or 'stakeholder' in x or 'user' in x or 'جمهور' in x for x in lenses):
        failures.append('audience/stakeholder seat required')
    if size in (5,7) and seats and not any('feasib' in x or 'practical' in x or 'operab' in x or 'عملي' in x for x in lenses):
        failures.append('practical/feasibility seat required for full council')
    debates=packet.get('debates')
    if size in (5,7):
        if not isinstance(debates,list) or not debates:failures.append('full council requires at least one debate')
    if debates is not None and not isinstance(debates,list):failures.append('debates must be an array')
    if isinstance(debates,list):
        for j,d in enumerate(debates):
            if not isinstance(d,dict) or not all(_text(d.get(k)) for k in ('topic','steelman_a','steelman_b','discriminator')):
                failures.append(f'debate {j}: include topic, steelman_a, steelman_b, discriminator')
    rt=packet.get('red_team')
    if not isinstance(rt,dict) or not _text(rt.get('premortem')):
        failures.append('red_team.premortem required')
    verdict=packet.get('verdict')
    if not isinstance(verdict,dict): failures.append('verdict object required')
    else:
        for k in ('decision','reasoning','strongest_dissent'):
            if not _text(verdict.get(k)):failures.append(f'verdict.{k} required')
        actions=verdict.get('actions')
        if not isinstance(actions,list) or not actions or not all(_text(x) for x in actions):
            failures.append('verdict.actions must be non-empty actionable strings')
    entries=packet.get('evidence', [])
    if not isinstance(entries,list): failures.append('evidence must be array');entries=[]
    for j,item in enumerate(entries):
        if not isinstance(item,dict):failures.append(f'evidence {j}: invalid object');continue
        kind=item.get('kind')
        if kind=='file-sha256':
            expected=item.get('sha256')
            if not isinstance(expected,str) or not re.fullmatch('[a-fA-F0-9]{64}',expected):
                failures.append(f'evidence {j}: invalid sha256');continue
            try:
                target=_safe_file(Path(directory),item.get('file',''))
                actual=_sha256(target)
                matched = actual.lower()==expected.lower()
                evidence.append({'index':j,'kind':kind,'file':str(target.relative_to(Path(directory).resolve())),
                                 'integrity_match':matched,'claim_truth_verified':False})
                if not matched:failures.append(f'evidence {j}: digest mismatch')
            except (ValueError,OSError) as exc:
                failures.append(f'evidence {j}: {exc}')
        elif kind=='declared-reference':
            if not _text(item.get('citation')):failures.append(f'evidence {j}: missing reference')
            else:
                evidence.append({'index':j,'kind':kind,'status':'declared-unverified'})
                warnings.append(f'evidence {j}: reference not independently verified')
        else:
            failures.append(f'evidence {j}: unsupported kind; no command execution')
    if not entries:
        warnings.append('no byte-level evidence checks; observations have only user-supplied locators')
    return {'kind':'black-dragon.v10.4/council-audit','structure_pass':not failures,
            'violations':failures,'warnings':warnings,'evidence':evidence,
            'agent_calls_verified':False,'seat_independence_verified':False,
            'factual_correctness_verified':False,'artistic_quality_verified':False,
            'notice':'PASS checks structural roles and available file hashes; locators, opinions, source truth and real multi-agent independence need separate verification.'}


def _tokens(text: str) -> set[str]:
    return {t for t in re.findall(r'[\w\u0600-\u06ff]+',text.casefold()) if len(t)>1}


def default_ledger() -> Path:
    return Path(os.environ.get('BLACK_DRAGON_COUNCIL_LESSONS',str(Path.home()/'.black-dragon'/'expert-council'/'lessons.jsonl')))


def read_lessons(store: Path) -> list[dict]:
    if not store.exists():return []
    if store.stat().st_size > 10*1024*1024:raise ValueError('ledger exceeds 10 MiB')
    rows=[]
    for n,line in enumerate(store.read_text(encoding='utf-8').splitlines(),1):
        if not line.strip():continue
        try:r=json.loads(line)
        except json.JSONDecodeError as exc:raise ValueError(f'corrupt ledger line {n}: {exc}') from exc
        if not isinstance(r,dict):raise ValueError(f'corrupt ledger record on line {n}')
        rows.append(r)
    return rows


def _atomic_save(store: Path,rows: list[dict]) -> None:
    store.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(dir=store.parent,prefix='.lessons-',suffix='.tmp')
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as f:
            for row in rows:f.write(json.dumps(row,ensure_ascii=False,sort_keys=True)+'\n')
        os.replace(tmp,store)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)


def add_lesson(store: Path,domain: str,trigger: str,mistake: str,lesson: str,severity: str='med',source: str='user') -> dict:
    if not _text(domain,80):raise ValueError('domain is required')
    if not all(_text(x,2000) for x in (trigger,mistake,lesson)):raise ValueError('trigger, mistake, lesson required')
    if severity not in ('low','med','high') or source not in ('user','self','test'):
        raise ValueError('unsupported severity/source')
    rows=read_lessons(store)
    canonical=_tokens(lesson)
    for row in rows:
        if row.get('domain')==domain and _tokens(str(row.get('lesson','')))==canonical:
            row['hits']=int(row.get('hits',0))+1
            _atomic_save(store,rows)
            return {'status':'reinforced-existing','lesson':row}
    item={'id':max((int(r.get('id',0)) for r in rows),default=0)+1,
          'date':dt.date.today().isoformat(),'domain':domain,'trigger':trigger.strip(),
          'mistake':mistake.strip(),'lesson':lesson.strip(), 'severity':severity,'source':source,'hits':0}
    rows.append(item);_atomic_save(store,rows)
    return {'status':'added','lesson':item}


def lessons(store: Path,mode: str,query: str='',domain: str|None=None,limit: int=10) -> dict:
    if domain is not None and not _text(domain,80):raise ValueError('domain is required')
    if not 1<=limit<=100:raise ValueError('limit must be 1..100')
    rows=[r for r in read_lessons(store) if domain is None or r.get('domain')==domain]
    if mode=='stats':
        by={}
        for r in rows:by[r.get('domain','unknown')]=by.get(r.get('domain','unknown'),0)+1
        return {'kind':'black-dragon.v10.4/council-lessons-stats','total':len(rows),'by_domain':by}
    if mode=='search':
        if not _text(query): raise ValueError('query required')
        qs=_tokens(query)
        scores=[]
        for r in rows:
            body=_tokens(' '.join(str(r.get(x,'')) for x in ('domain','trigger','mistake','lesson')))
            points=len(qs&body)*10 + (3 if r.get('severity')=='high' else 1) + int(r.get('hits',0))
            if qs&body or (domain is not None and r.get('severity')=='high'):
                scores.append((points,r))
        rows=[r for _,r in sorted(scores,key=lambda a:-a[0])]
    elif mode=='list': rows=list(reversed(rows))
    else:raise ValueError('invalid lesson query mode')
    return {'kind':f'black-dragon.v10.4/council-lessons-{mode}','total_matched':len(rows),'results':rows[:limit],
            'notice':'Private on-disk record, not persistent model weights or cross-device sync.'}
