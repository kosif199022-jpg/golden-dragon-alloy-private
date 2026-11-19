#!/usr/bin/env python3
"""Black Dragon Absolute Creativity bridge, v10.6. No network or paid calls.

Local creative briefs, deterministic stimulus generation, human-scored rubric
validation, a style-bible checklist, and an optional Arabic shaping lab.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'skills' / 'absolute-creativity'
IDEAS = SOURCE / 'scripts' / 'idea_forge.py'
FONTS = SOURCE / 'scripts' / 'font_lab.py'
CATEGORIES = ('originality', 'emotional_truth', 'clarity', 'feasibility', 'memorability')
PALETTE_RE = re.compile(r'^#[a-fA-F0-9]{6}$')
MAX_JSON_BYTES = 512_000


def load_ideas():
    if not IDEAS.is_file():
        raise ValueError('bundled idea_forge.py is missing')
    spec = importlib.util.spec_from_file_location('dragon_v106_idea_forge', IDEAS)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def bounded_string(value, name, max_chars=8000):
    if not isinstance(value, str) or not value.strip() or len(value) > max_chars:
        raise ValueError(f'{name}: non-empty string required (max {max_chars})')
    return value.strip()


def load_json(path):
    path = Path(path)
    if not path.is_file() or path.stat().st_size > MAX_JSON_BYTES:
        raise ValueError(f'JSON missing or too large (max {MAX_JSON_BYTES} bytes)')
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (UnicodeError, OSError, ValueError) as exc:
        raise ValueError(f'invalid JSON: {type(exc).__name__}') from exc
    if not isinstance(data, dict):
        raise ValueError('JSON root must be an object')
    return data


def brief(task):
    task = bounded_string(task, 'task', 2000)
    return {
        'schema': 'black-dragon.creativity.v1',
        'task': task,
        'audience': '', 'emotion': '', 'central_message': '',
        'platform': '', 'duration_s': None, 'aspect': '',
        'available_media': [], 'rejected_cliches': ['', '', ''],
        'creative_constraint': '',
        'concepts': [
            {'id': f'C{i}', 'name': '', 'logline': '', 'mechanism': '',
             'distinctive_image': '', 'scores': {k: None for k in CATEGORIES},
             'scorer': '', 'score_basis': ''}
            for i in range(1, 4)
        ],
        'chosen_id': '', 'selection_reason': '',
        '_instructions': 'Fill the fields. Scores MUST be entered by a named reviewer; 1..5 per criterion. A generated score is not objective proof of originality.'
    }


def audit(data):
    issues, warnings = [], []
    if data.get('schema') != 'black-dragon.creativity.v1':
        issues.append('schema must be black-dragon.creativity.v1')
    for k in ('task', 'audience', 'emotion', 'central_message', 'platform', 'aspect', 'creative_constraint'):
        try: bounded_string(data.get(k), k, 2000)
        except ValueError as exc: issues.append(str(exc))
    n = data.get('duration_s')
    if isinstance(n, bool) or not isinstance(n,(int,float)) or not 0 < n <= 3600:
        issues.append('duration_s must be a positive number <=3600')
    cliches = data.get('rejected_cliches')
    if not isinstance(cliches,list) or len(cliches)<3 or len({str(c).strip().casefold() for c in cliches if isinstance(c,str) and c.strip()}) < 3:
        issues.append('provide 3 distinct rejected cliches')
    concepts = data.get('concepts')
    if not isinstance(concepts,list) or len(concepts)!=3:
        issues.append('exactly 3 concept alternatives are required')
        concepts=[]
    reports=[]; names=[]; mechanisms=[]; ids=[]
    for i,c in enumerate(concepts):
        if not isinstance(c,dict): issues.append(f'concept[{i}] must be an object'); continue
        cid=c.get('id')
        if not isinstance(cid,str) or not re.fullmatch(r'C[1-3]',cid): issues.append(f'concept[{i}].id invalid')
        else:ids.append(cid)
        for k in ('name','logline','mechanism','distinctive_image','scorer','score_basis'):
            try: bounded_string(c.get(k),f'concept[{i}].{k}',2000)
            except ValueError as exc:issues.append(str(exc))
        names.append(str(c.get('name','')).strip().casefold())
        mechanisms.append(str(c.get('mechanism','')).strip().casefold())
        scores=c.get('scores')
        valid = isinstance(scores,dict) and all(type(scores.get(k)) is int and 1 <= scores[k] <= 5 for k in CATEGORIES)
        if not valid:
            issues.append(f'concept[{i}] must have 5 human-entered integer scores (1..5)')
            reports.append({'id':cid,'complete':False,'passes_rubric':False})
        else:
            total=sum(scores[k] for k in CATEGORIES)
            eligible = total >=18 and scores['originality']>=4
            reports.append({'id':cid,'complete':True,'total':total,'max':25,
                            'originality':scores['originality'], 'passes_rubric':eligible,
                            'scorer_declared':bool(str(c.get('scorer','')).strip())})
    if len(ids)!=len(set(ids)):issues.append('duplicate concept IDs')
    if len(names)!=len(set(names)) or '' in names:issues.append('concept names must be distinct')
    if len(mechanisms)!=len(set(mechanisms)) or '' in mechanisms:issues.append('concept mechanisms must be different, not merely different palettes')
    chosen=data.get('chosen_id')
    if chosen not in ids:issues.append('chosen_id must identify one of the three concepts')
    try:bounded_string(data.get('selection_reason'),'selection_reason',2000)
    except ValueError as exc:issues.append(str(exc))
    winner=next((r for r in reports if r.get('id')==chosen),None)
    if winner and not winner['passes_rubric']:
        issues.append('chosen concept fails threshold (total >=18/25 and originality >=4/5)')
    warnings.append('Human rubric scores are subjective claims, not objective originality proof.')
    warnings.append('A passing structural audit does not prove factual truth, independent expert review or creative quality.')
    return {'ok':not issues, 'issues':issues, 'scores':reports, 'warnings':warnings,
            'execution_performed':False, 'agent_calls_verified':False, 'originality_verified':False}


def style_bible_check(data):
    issues=[]; warnings=[]
    for k in ('title','concept_id','story_beats','camera','edit_rhythm','sound','typography','art_direction'):
        try:bounded_string(data.get(k), k, 10000)
        except ValueError as exc:issues.append(str(exc))
    p=data.get('palette')
    if not isinstance(p,list) or len(p)!=3 or not all(isinstance(c,str) and PALETTE_RE.fullmatch(c) for c in p):
        issues.append('palette must contain 3 #RRGGBB color tokens')
    constraints=data.get('constraints')
    if not isinstance(constraints,list) or not constraints or any(not isinstance(v,str) or not v.strip() for v in constraints):
        issues.append('constraints must be non-empty list of strings')
    assets=data.get('assets',[])
    if not isinstance(assets,list):issues.append('assets must be a list');assets=[]
    for i,a in enumerate(assets):
        if not isinstance(a,dict):issues.append(f'asset[{i}] must be object');continue
        for key in ('source','licence','usage_permission'):
            if not isinstance(a.get(key),str) or not a[key].strip():issues.append(f'asset[{i}].{key} required')
        if a.get('usage_permission')!='verified':
            issues.append(f'asset[{i}] cannot be used in production until rights are verified')
    warnings.append('No image/video rendered or license verified by this form alone.')
    return {'ok':not issues,'issues':issues,'warnings':warnings,
            'structure_checked':True,'rights_checked_against_external_sources':False,
            'render_executed':False}


def doctor():
    try:
        pillow = importlib.util.find_spec('PIL') is not None
        if pillow:
            from PIL import features
            raqm = bool(features.check('raqm'))
        else:raqm=False
    except (ImportError, AttributeError):
        pillow=False;raqm=False
    fonttools=importlib.util.find_spec('fontTools') is not None
    return {'skill_loaded':(SOURCE/'SKILL.md').is_file(),
            'reference_guides':len(list((SOURCE/'references').glob('*.md'))),
            'idea_engine_present':IDEAS.is_file(), 'pillow':pillow,
            'libraqm':raqm, 'fonttools':fonttools,
            'arabic_title_render_ready':pillow and raqm,
            'fonts_bundled':False, 'font_cache_bundled':(SOURCE/'scripts/.font_cache.json').exists(),
            'network_used':False,'render_performed':False}


def call_font(args):
    d=doctor()
    if not d['arabic_title_render_ready']:
        raise ValueError('Arabic title generation requires Pillow with libraqm; no bad RTL fallback permitted')
    command=args.cmd.replace('font-', '')
    if command in ('list','specimen') and not d['fonttools']:
        raise ValueError('fontTools needed to enumerate Arabic-capable fonts')
    cmd=[sys.executable, str(FONTS), command]
    if command=='title':
        text=bounded_string(args.text,'text',1000)
        f=Path(args.font)
        if not f.is_file() or f.suffix.lower() not in {'.ttf','.ttc','.otf'}:
            raise ValueError('provide an existing local .ttf/.ttc/.otf font file')
        out=Path(args.out)
        if out.exists():raise ValueError('output already exists; never overwrite it')
        if out.suffix.lower()!='.png':raise ValueError('title output must be PNG')
        if not 8<=args.size<=512 or not 0<=args.stroke<=30 or not 0<=args.shadow<=40 or not 0<=args.width<=4096:
            raise ValueError('font size/stroke/shadow/width outside safe bounds')
        for c in (args.color,args.stroke_color):
            if not PALETTE_RE.fullmatch(c):raise ValueError('color must be #RRGGBB')
        out.parent.mkdir(parents=True,exist_ok=True)
        cmd += [text,'--font',str(f),'--out',str(out),'--size',str(args.size),
                '--stroke',str(args.stroke),'--shadow',str(args.shadow),'--width',str(args.width),
                '--color',args.color,'--stroke-color',args.stroke_color]
    elif command=='list':
        if args.refresh:cmd+=['--refresh']
        if args.json:cmd+=['--json']
        for d in args.dir:cmd+=['--dir',d]
    elif command=='specimen':
        out=Path(args.out)
        if out.exists():raise ValueError('output already exists')
        if not 12 <= args.size <= 192 or not 1 <= args.max <= 40:raise ValueError('size/max out of range')
        out.parent.mkdir(parents=True,exist_ok=True)
        cmd += [bounded_string(args.text,'text',2000),'--out',str(out),'--size',str(args.size),'--max',str(args.max)]
        if args.filter:cmd+=['--filter',args.filter]
        for d in args.dir:cmd+=['--dir',d]
    try:
        r=subprocess.run(cmd,timeout=90)
        return r.returncode
    except subprocess.TimeoutExpired:
        raise ValueError('font operation exceeded 90-second limit')


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    sub=p.add_subparsers(dest='cmd',required=True)
    sub.add_parser('doctor')
    s=sub.add_parser('brief');s.add_argument('--task',required=True);s.add_argument('--out')
    s=sub.add_parser('spin');s.add_argument('task');s.add_argument('--n',type=int,default=12);s.add_argument('--seed',type=int);s.add_argument('--json',action='store_true')
    s=sub.add_parser('card');s.add_argument('--n',type=int,default=3);s.add_argument('--seed',type=int,default=7)
    sub.add_parser('score')
    s=sub.add_parser('audit');s.add_argument('file')
    s=sub.add_parser('style-check');s.add_argument('file')
    sub.add_parser('font-doctor')
    s=sub.add_parser('font-list');s.add_argument('--dir',action='append',default=[]);s.add_argument('--json',action='store_true');s.add_argument('--refresh',action='store_true')
    s=sub.add_parser('font-title');s.add_argument('text');s.add_argument('--font',required=True);s.add_argument('--out',required=True)
    s.add_argument('--size',type=int,default=160);s.add_argument('--stroke',type=int,default=6);s.add_argument('--shadow',type=int,default=10)
    s.add_argument('--width',type=int,default=1080);s.add_argument('--color',default='#F5C542');s.add_argument('--stroke-color',default='#000000')
    s=sub.add_parser('font-specimen');s.add_argument('text');s.add_argument('--out',required=True);s.add_argument('--filter');s.add_argument('--dir',action='append',default=[])
    s.add_argument('--max',type=int,default=12);s.add_argument('--size',type=int,default=64)
    a=p.parse_args(argv)
    try:
        if a.cmd in ('doctor','font-doctor'):
            out=doctor()
        elif a.cmd=='brief':
            out=brief(a.task)
            if a.out:
                path=Path(a.out)
                if path.exists():raise ValueError('output already exists; refusing overwrite')
                path.parent.mkdir(parents=True,exist_ok=True)
                path.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
                out={'written_to':str(path),'ready_for_audit':False,'filled_by_reviewer':False}
        elif a.cmd=='spin':
            if not 1<=a.n<=100:raise ValueError('spin count must be 1..100')
            task=bounded_string(a.task,'task',2000)
            seed=a.seed if a.seed is not None else int(hashlib.sha256(task.encode('utf-8')).hexdigest()[:8],16)
            out={'task':task,'seed':seed,'count':a.n,'seeds':load_ideas().spin(task,a.n,seed),
                 'ideas_executed':False,'content_originality_verified':False}
        elif a.cmd=='card':
            from random import Random
            src=load_ideas()
            if not 1<=a.n<=len(src.CARDS):raise ValueError('card count outside deck')
            out={'cards':Random(a.seed).sample(src.CARDS,k=a.n),'seed':a.seed,'execution_performed':False}
        elif a.cmd=='score':
            out={'rubric':load_ideas().RUBRIC,'weights':'1..5 each, human-entered','min_total':18,'min_originality':4}
        elif a.cmd=='audit':out=audit(load_json(a.file))
        elif a.cmd=='style-check':out=style_bible_check(load_json(a.file))
        elif a.cmd.startswith('font-'):return call_font(a)
        else:raise ValueError('unknown subcommand')
        print(json.dumps(out,ensure_ascii=False,indent=2))
        return 0 if out.get('ok',True) else 2
    except (ValueError,OSError) as exc:
        print(f'creativity: {exc}',file=sys.stderr)
        return 2


if __name__=='__main__':sys.exit(main())
