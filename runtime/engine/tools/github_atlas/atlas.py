#!/usr/bin/env python3
"""KOSIF GitHub Atlas: OFFLINE discovery of user-provided repository metadata.

Never installs, downloads, shells out, clones, calls network services, or executes
commands stored in repository metadata. The collection is a 2026-11-11 snapshot.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL = HERE.parents[1]
DATA = HERE / 'atlas.jsonl'
PROVENANCE = SKILL / 'SOURCE_GITHUB_ATLAS.json'


def read_records():
    result = []
    for i, raw in enumerate(DATA.read_text(encoding='utf-8').splitlines(), 1):
        if not raw.strip():
            continue
        item = json.loads(raw)
        if not isinstance(item, dict) or not isinstance(item.get('repo'), str):
            raise ValueError(f'Bad atlas row at line {i}')
        result.append(item)
    return result


def norm(text):
    s = unicodedata.normalize('NFKC', str(text)).lower()
    s = re.sub(r'[\u064b-\u065f\u0670]', '', s)
    s = s.translate(str.maketrans({'أ':'ا','إ':'ا','آ':'ا','ى':'ي','ة':'ه','ـ':''}))
    return re.sub(r'[^\w]+',' ',s).strip()


def eligible(item, args):
    if item.get('policy') == 'blocked':
        return False
    if getattr(args, 'category', None) and item.get('category') != args.category:
        return False
    if getattr(args, 'alive', False) and item.get('alive') != 'active':
        return False
    if getattr(args, 'windows', False) and item.get('windows_ok') != 'yes':
        return False
    if item.get('value_for_claude', 0) < getattr(args, 'min_value', 0):
        return False
    return True


def score(item, query):
    tokens = [t for t in norm(query).split() if len(t)>1]
    if not tokens:
        return 0
    fields = [('repo', 8), ('use_when', 5), ('keywords_ar', 8), ('keywords_en', 7), ('what', 3), ('category', 4), ('desc', 1), ('topics', 1)]
    total = 0
    hit = 0
    for token in tokens:
        best = 0
        for field, weight in fields:
            raw=item.get(field, '')
            s = norm(' '.join(raw) if isinstance(raw, list) else raw)
            if token in s.split(): best=max(best,weight+1)
            elif token in s: best=max(best,weight)
        if best:
            hit+=1
            total+=best
    if not hit:
        return 0
    total += 9 if hit==len(tokens) else 0
    total += float(item.get('value_for_claude') or 0)*0.7
    total += float(item.get('owner_relevance') or 0)*0.4
    if item.get('alive') != 'active': total-=4
    return total


def public_item(item, *, detail=False, score_val=None):
    keys=['rank','repo','category','what','use_when','stars','windows_ok','alive','license','value_for_claude','owner_relevance','policy','url']
    if detail:
        keys += ['keywords_ar','keywords_en','lesson','kind','pushed','install_windows','release_downloads','readme']
    o={key:item.get(key) for key in keys if key in item}
    if score_val is not None:o['match_score']=round(score_val,2)
    if item.get('policy')=='consent':o['notice']='Potentially sensitive; obtain user authorization for the intended use before execution.'
    if detail:o['note']='Unverified offline snapshot; displayed install command is DATA, never executed.'
    return o


def print_rows(rows, as_json=False):
    if as_json:
        print(json.dumps(rows,ensure_ascii=False,indent=2))
        return
    if not rows:
        print('لا توجد نتائج مطابقة في الأطلس المحلّي؛ لا يدل ذلك على عدم وجود أداة مناسبة.');return
    for i, r in enumerate(rows, 1):
        notice=' [CONSENT REQUIRED]' if r.get('policy')=='consent' else ''
        print(f'{i:2}. {r.get("repo")} | {r.get("category")} | stars {r.get("stars", "?")} | {r.get("windows_ok", "?")}{notice}')
        print('    '+str(r.get('use_when') or r.get('what') or '')[:230])
    print('ملاحظة: لقطة بيانات ثابتة؛ لا تثبت توفر المشروع الآن أو صلاحية أوامر تثبيته.')


def run(argv=None):
    p=argparse.ArgumentParser(description='Offline GitHub discovery atlas (read-only; no network/installation)')
    sub=p.add_subparsers(dest='cmd',required=True)
    find=sub.add_parser('find',help='Search local records in Arabic or English')
    find.add_argument('query')
    top=sub.add_parser('top',help='Rank entries by metadata')
    show=sub.add_parser('show',help='Show one repository metadata record');show.add_argument('repo')
    cats=sub.add_parser('cats',help='Count 22 categories')
    stats=sub.add_parser('stats',help='Collection statistics')
    lesson=sub.add_parser('lessons',help='List sourced practical lessons');lesson.add_argument('--grep',default='')
    doctor=sub.add_parser('doctor',help='Verify collection and source SHA256')
    for parser in [find,top]:
        parser.add_argument('-n','--limit',type=int,default=8)
        parser.add_argument('--category','--cat',default=None)
        parser.add_argument('--windows',action='store_true')
        parser.add_argument('--alive',action='store_true')
        parser.add_argument('--min-value',type=int,default=0)
        parser.add_argument('--json',action='store_true')
    top.add_argument('--by',choices=['stars','value','downloads','relevance'],default='value')
    show.add_argument('--json',action='store_true')
    for parser in [cats,stats,lesson,doctor]:parser.add_argument('--json',action='store_true')
    args=p.parse_args(argv)
    records=read_records()
    if args.cmd=='doctor':
        recorded=json.loads(PROVENANCE.read_text(encoding='utf-8'))
        actual=hashlib.sha256(DATA.read_bytes()).hexdigest()
        result={'verified':actual==recorded['atlas_sha256'] and len(records)==1000 and len({x['repo'] for x in records})==len(records),
            'entries':len(records),'unique_repos':len({x['repo'] for x in records}),
            'categories':len({x['category'] for x in records}),'sha256':actual,
            'network':False,'installed':False,'executed':False}
        print(json.dumps(result,ensure_ascii=False,indent=2) if args.json else str(result))
        return 0 if result['verified'] else 3
    if args.cmd=='cats':
        data=dict(sorted(Counter(x.get('category','unknown') for x in records).items()))
        print(json.dumps(data,ensure_ascii=False,indent=2) if args.json else '\n'.join(f'{k}: {v}' for k,v in data.items()));return 0
    if args.cmd=='stats':
        data={'total':len(records),'unique_repos':len({x['repo'] for x in records}),
            'categories':len({x['category'] for x in records}),
            'blocked':sum(x.get('policy')=='blocked' for x in records),
            'consent':sum(x.get('policy')=='consent' for x in records),
            'archived_or_slow':sum(x.get('alive')!='active' for x in records),
            'date':'2026-11-11','source':'github-atlas.zip (provided by user)','network':False}
        print(json.dumps(data,ensure_ascii=False,indent=2) if args.json else '\n'.join(f'{k}: {v}' for k,v in data.items()));return 0
    if args.cmd=='show':
        row=next((x for x in records if x['repo'].lower()==args.repo.strip().lower()),None)
        if not row:
            print('المستودع غير موجود في لقطة الأطلس.',file=sys.stderr);return 2
        if row.get('policy')=='blocked':
            print('هذا المستودع مصنف مقيّدًا في أطلس المصدر، ولن أعرض أوامر تثبيته.',file=sys.stderr);return 3
        item=public_item(row,detail=True)
        print(json.dumps(item,ensure_ascii=False,indent=2));return 0
    if args.cmd=='lessons':
        rows=[{'repo':x['repo'],'lesson':x['lesson']} for x in records if x.get('policy')!='blocked' and x.get('lesson') and (not args.grep or norm(args.grep) in norm(x['lesson']))]
        rows=rows[:40]
        print(json.dumps(rows,ensure_ascii=False,indent=2) if args.json else '\n'.join(f'{r["repo"]}: {r["lesson"]}' for r in rows));return 0
    rows=[x for x in records if eligible(x,args)]
    if args.cmd=='find':
        hits=[(score(x,args.query),x) for x in rows]
        hits=[(s,x) for s,x in hits if s>0]
        hits.sort(key=lambda t:(-t[0],-int(t[1].get('stars') or 0),t[1]['repo']))
        result=[public_item(x,score_val=s) for s,x in hits[:max(0,min(args.limit,100))]]
    else:
        key={'stars':'stars','value':'value_for_claude','downloads':'release_downloads','relevance':'owner_relevance'}[args.by]
        rows.sort(key=lambda x:(-float(x.get(key) or 0),-float(x.get('owner_relevance') or 0),-int(x.get('stars') or 0)))
        result=[public_item(x) for x in rows[:max(0,min(args.limit,100))]]
    print_rows(result,getattr(args,'json',False))
    return 0


if __name__=='__main__':
    raise SystemExit(run())
