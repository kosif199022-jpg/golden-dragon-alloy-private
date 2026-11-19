#!/usr/bin/env python3
"""Media Hunter for Black Dragon v10.2: verified stock clients + offline site discovery.

    python scripts/dragon.py tool hunter sites "camel desert sunset" --type video
    python scripts/dragon.py tool hunter hunt "camel desert sunset" --type video --orientation portrait
    python scripts/dragon.py tool hunter search "museum portrait" --type art
    python scripts/dragon.py tool hunter links "HD aerial" --type video --out out/media-hunter/links.html
    python scripts/dragon.py tool hunter get 1 3 --out out/my-film/footage --dry-run
    python scripts/dragon.py tool hunter keys
    python scripts/dragon.py tool hunter build --out out/media-hunter/sources.json

IMPORTANT: The supplied SKILL.md is *documentation*, not the original 615-site/19-API program.
This replacement routes through already-bundled and tested stock providers. Other websites are
DISCOVERY-ONLY links (never silently counted as live APIs or verified commercial licences).
No source-code downloads, private uploads, auto-install, or credit spending.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import html
import json
import os
import re
import sys
import urllib.parse
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[2]
STOCK = ROOT / "tools" / "stock"
sys.dont_write_bytecode = True  # preserve the stock tool no-__pycache__ invariant
if str(STOCK) not in sys.path:
    sys.path.insert(0, str(STOCK))
import free_footage as FF  # noqa: E402
import free_photos as FP   # noqa: E402

SCHEMA = "black-dragon.media-hunter.v10.2"
DEFAULT_OUT = Path('out') / 'media-hunter'
KINDS = ('any','video','image','art','hdri','texture','3d','icon','gif','wallpaper')
# Online only if a bundled stock client has an actual supported adapter. The following are
# site-discovery metadata, NOT new implementations, rights assurances, or new API connections.
EXTRA = (
    ('europeana','Europeana','https://www.europeana.eu/en/search?query={q}',('video','image','art'),'per-item'),
    ('smithsonian','Smithsonian Open Access','https://www.si.edu/es/search/collection-images?edan_q={q}',('image','art'),'per-item'),
    ('wellcome','Wellcome Collection','https://wellcomecollection.org/search/images?query={q}',('image','art'),'per-item'),
    ('artic','Art Institute of Chicago','https://www.artic.edu/collection?query={q}',('image','art'),'per-item'),
    ('cleveland','Cleveland Museum of Art','https://www.clevelandart.org/art/collection/search?search={q}',('image','art'),'per-item'),
    ('vam','Victoria and Albert Museum','https://collections.vam.ac.uk/search/?q={q}',('image','art'),'per-item'),
    ('smk','Statens Museum for Kunst','https://open.smk.dk/en/search/?q={q}',('image','art'),'per-item'),
    ('polyhaven','Poly Haven','https://polyhaven.com/search?q={q}',('hdri','texture','3d'),'per-item'),
    ('ambientcg','ambientCG','https://ambientcg.com/list?search={q}',('texture','3d'),'per-item'),
    ('iconify','Iconify','https://icon-sets.iconify.design/?query={q}',('icon',),'per-item'),
    ('wallhaven','Wallhaven','https://wallhaven.cc/search?q={q}',('wallpaper','image'),'per-item'),
    ('giphy','GIPHY','https://giphy.com/search/{slug}',('gif',),'per-item'),
)
# This small fallback is not a translation service. Unmapped terms are passed through unchanged.
AR = {'جمل':'camel','الجمل':'camel','إبل':'camels','صحراء':'desert','الصحراء':'desert',
      'غروب':'sunset','الشروق':'sunrise','بحر':'sea','البحر':'sea','مطر':'rain',
      'مطيرة':'rainy','مطرية':'rainy','القاهرة':'cairo','اسكندرية':'alexandria',
      'الإسكندرية':'alexandria','الرياض':'riyadh','جدة':'jeddah','مشهد':'scene',
      'ليل':'night','نهار':'day','طائرة':'airplane','شمس':'sun','طبيعة':'nature',
      'مناظر':'landscape','أرشيف':'archive','مدينة':'city','شاطئ':'beach',
      'سيارات':'cars','سيارة':'car','خراف':'sheep','خروف':'sheep','قهوة':'coffee',
      'بنت':'girl','بنتين':'girls','ولد':'boy','السماء':'sky'}

def english_query(raw: str):
    pieces = re.findall(r'[\w\u0600-\u06ff]+',raw,flags=re.UNICODE)
    mapped = [AR.get(p,AR.get(p.removeprefix('ال'),p)) for p in pieces]
    return ' '.join(mapped).strip() or raw.strip()

def source_rows():
    video = FF.load_db()['sources']
    out = {}
    for v in video:
        sid=v['id']
        out[sid]={'id':sid,'name':v['name'],'types':['video'], 'search_url':v.get('search_url') or v['url'],
                  'adapter':'video' if sid in FF.SEARCHERS and v['tool']['search'] != 'none' else None,
                  'key':v['api'].get('key_env') if v['tool']['search']=='api-key' else None,
                  'category':v.get('category'),'licence':v.get('licence',{}).get('name','Unknown'),
                  'rights':'per-item' if v['licence']['per_item'] else 'source-terms'}
    for sid,v in FP.SOURCES.items():
        if sid in out:
            out[sid]['types'].extend(['image','art'] if sid=='met' else ['image'])
            out[sid]['photo_adapter']='photo'
            if not out[sid]['adapter']:out[sid]['adapter']='photo'
            if v['key']:out[sid]['key']=v['key']
        else:
            out[sid]={'id':sid,'name':v['name'],'types':['image','art'] if sid=='met' else ['image'],
                      'search_url':v['url'],'adapter':'photo','key':v['key'],'category':'open-collection' if sid=='met' else 'free-or-licensed',
                      'licence':v['licence'][0],'rights':'per-item' if v['commercial']=='per-item' else 'source-terms'}
    for sid,name,url,types,rights in EXTRA:
        if sid not in out:
            out[sid]={'id':sid,'name':name,'types':list(types),'search_url':url,'adapter':None,
                      'key': 'GIPHY_API_KEY' if sid=='giphy' else None, 'category':'discovery-only',
                      'licence':'verify individual asset','rights':rights}
    return list(out.values())

def compatible(row,typ):
    if typ=='any':return bool(set(row['types']) & {'video','image'})
    return typ in row['types']

def query_url(row, query, typ='any'):
    from urllib.parse import quote
    url=row['search_url']
    photo_templates={
        'openverse':'https://openverse.org/search/image?q={q}',
        'met':'https://www.metmuseum.org/art/collection/search?q={q}',
        'unsplash':'https://unsplash.com/s/photos/{slug}',
        'pexels':'https://www.pexels.com/search/{query}/',
        'pixabay':'https://pixabay.com/images/search/{q}/',
        'wikimedia':'https://commons.wikimedia.org/w/index.php?search={q}&title=Special:MediaSearch&type=image',
    }
    if typ in ('image','art') and row['id'] in photo_templates:
        url=photo_templates[row['id']]
    if '{query}' in url:url=url.replace('{query}',quote(query,safe=''))
    if '{q}' in url:url=url.replace('{q}',quote(query,safe=''))
    if '{slug}' in url:url=url.replace('{slug}',quote(query.replace(' ','-'),safe=''))
    return url

def shortlist(query,typ='any',free=False,limit=30):
    rows=[r.copy() for r in source_rows() if compatible(r,typ) and (not free or r['category']!='paid-stock')]
    words=set(query.lower().split())
    def score(r):
        s=3 if r['adapter'] else 0
        if typ in ('art','hdri','texture','3d','icon','gif','wallpaper') and typ in r['types']:s+=5
        if words & set(r['id'].split('-')):s+=2
        return -s,r['name'].casefold()
    rows.sort(key=score)
    return [{**r,'search_url':query_url(r,query,typ),'status':('discovery-only' if not r['adapter']
              else 'discovery-only for this type' if (typ=='video' and r['adapter']=='photo')
              else 'needs-key' if r['key'] and not os.environ.get(r['key'])
              else 'search adapter available; not queried')} for r in rows[:limit]]

def available_sources(typ, requested=None):
    # Modern stock photos and footage use different clients; both may support the same source.
    video=FF.default_sources(FF.load_db());photo=FP.default_sources()
    videos=video if typ in ('video','any') else []
    photos=photo if typ in ('image','any') else (['met','wikimedia'] if typ=='art' else [])
    if requested:
        req={x.strip() for x in requested.split(',') if x.strip()}
        known={r['id'] for r in source_rows()}
        bad=req-known
        if bad: raise ValueError('unknown source(s): '+', '.join(sorted(bad)))
        videos=[s for s in videos if s in req]
        photos=[s for s in photos if s in req]
    return [('video',s) for s in videos]+[('photo',s) for s in photos]

def normalize_record(r,kind):
    lic=r.get('licence') or {}
    return {'id':r.get('id'),'kind':kind,'source':r.get('source'), 'title':r.get('title'),
            'page_url':r.get('page_url'),'media_url':r.get('file_url'),
            'width':r.get('width'),'height':r.get('height'),'duration':r.get('duration'),
            'author':r.get('author'),'license':lic.get('name') or 'unknown',
            'license_url':lic.get('url'),'license_detail':lic,'attribution':r.get('attribution'),
            'rights_verified':False, 'downloadable_by_stock_client':True}

def _source_call(kind, sid, query, count, orientation, commercial):
    http=FF.Http(timeout=8,delay=0.5,max_retry_after=0)
    if kind=='video':
        report=FF.run_search(http,FF.load_db(),query,[sid],count,
                             {'orientation':orientation,'commercial':commercial,'allow_nd':False,
                              'any_licence':False,'no_ai':False,'max_bytes':None,'resolve':False})
    else:
        report=FP.run_search(http,query,[sid],count,
                             {'orientation':orientation,'commercial':commercial,'allow_nd':False})
    return {'kind':kind,'source':sid,'results':report.get('results',[]),
            'status':report.get('sources',{}).get(sid,{'status':'error'}),
            'warnings':report.get('warnings',[])}

def hunt(query,typ='any',orientation=None,min_width=None,free=False,limit=30,per_source=15,
         requested=None,out=DEFAULT_OUT):
    if not query.strip():raise ValueError('query must not be empty')
    if not 1<=limit<=200 or not 1<=per_source<=50:raise ValueError('limit 1..200 and per-source 1..50')
    if min_width is not None and min_width<0:raise ValueError('min-width must be nonnegative')
    english=english_query(query)
    tasks=available_sources(typ,requested)
    responses=[]
    # Each provider is limited to its own 8s/request timeout; the whole search is not guaranteed to finish in 8s.
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(6,max(1,len(tasks)))) as executor:
        future={executor.submit(_source_call,k,s,english,min(per_source,limit),orientation,False):(k,s) for k,s in tasks}
        for fut in concurrent.futures.as_completed(future):
            k,s=future[fut]
            try:responses.append(fut.result())
            except Exception as e:
                # Never leak query strings, credentials or proxy URLs in exception bodies.
                responses.append({'kind':k,'source':s,'results':[],
                                  'status':{'status':'error','detail':type(e).__name__},'warnings':[]})
    # Deterministic indexing, no duplicate media URLs. Preserve per-kind native result files for get.
    responses.sort(key=lambda v:(v['kind'],v['source']))
    raw={'video':[],'photo':[]};rows=[];seen=set()
    for p in responses:
        for rec in p['results']:
            nr=normalize_record(rec,p['kind']);url=nr['media_url'] or nr['page_url']
            key=(p['kind'],url)
            if not url or key in seen:continue
            seen.add(key)
            if orientation and nr['width'] and nr['height']:
                o=('portrait' if nr['height']>nr['width'] else 'landscape' if nr['width']>nr['height'] else 'square')
                if o!=orientation:continue
            if min_width and (nr['width'] is None or nr['width']<min_width):continue
            if len(rows)>=limit:continue
            nr['n']=len(rows)+1;rows.append(nr);raw[p['kind']].append(rec)
    sites=shortlist(english,typ,free,limit=5)
    found={f"{x['kind']}:{x['source']}":x['status'] for x in responses}
    report={'schema':SCHEMA,'query':query,'search_query':english,'searched_at':datetime.now(timezone.utc).isoformat(),
            'results':rows,'more_sites':sites,'searched_sources':found,'provider_requests':len(tasks),
            'actual_results':len(rows),'claims':{'original_615_catalog_included':False,
             'original_19_API_engine_included':False,'rights_verified_for_use':False,
             'network_calls_requested':bool(tasks)},
            'notice':'Per-asset rights must be checked at page_url before using or publishing; this tool never licenses assets.'}
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    (out/'last_hunt.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    # Stock download tools consume results with original schemas.
    schemas={'video':FF.RESULTS_SCHEMA,'photo':FP.RESULTS_SCHEMA}
    for k in ('video','photo'):
        (out/f'last_{k}.json').write_text(json.dumps({'schema':schemas[k], 'results':raw[k], 'query':english},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return report

def selected(result_path, indexes):
    d=json.loads(Path(result_path).read_text(encoding='utf-8'))
    if d.get('schema')!=SCHEMA:raise ValueError('not a Media Hunter results file')
    by_n={x['n']:x for x in d.get('results',[])}
    return [by_n[int(v)] if int(v) in by_n else (_ for _ in ()).throw(ValueError(f'no result #{v}')) for v in indexes]

def get(items,out,results,*,dry_run=False,max_mb=300,commercial=False,acknowledge_rights=False):
    if max_mb<=0 or max_mb>2048:raise ValueError('max-mb must be >0 and <=2048')
    path=Path(results); work=path.parent
    summary=[]
    for r in items:
        lic=(r.get('license') or '').lower()
        detail=r.get('license_detail') or {}
        risky=(detail.get('verified') is not True or detail.get('derivatives') is False or
               detail.get('commercial') is False or 'unknown' in lic or 'restricted' in lic or
               'noncommercial' in lic or 'by-nc' in lic or 'by-nd' in lic)
        if commercial and detail.get('commercial') is not True:
            risky=True
        if risky and not acknowledge_rights:
            summary.append({'n':r['n'],'status':'blocked-rights','license':r.get('license'),
                            'action':'Review per-asset licence; add --acknowledge-rights after confirming permission'});continue
        kind=r['kind'];suffix='video' if kind=='video' else 'photo'
        native_path=work/f'last_{suffix}.json'
        if not native_path.exists():
            summary.append({'n':r['n'],'status':'missing-native-results'});continue
        if not re.fullmatch(r'[a-z0-9-]+:[^\s/?#\\]+',r.get('id') or ''):
            summary.append({'n':r['n'],'status':'invalid-id'});continue
        native=json.loads(native_path.read_text(encoding='utf-8'))
        matches=[v for v in native.get('results',[]) if v.get('id')==r['id']]
        if len(matches)!=1 or matches[0].get('file_url')!=r.get('media_url') or matches[0].get('page_url')!=r.get('page_url'):
            summary.append({'n':r['n'],'status':'results-mismatch'});continue
        command=['download',r['id'],'--out',str(Path(out)), '--results',str(work/f'last_{suffix}.json'),
                 '--max-mb',str(max_mb)]
        if dry_run:command.append('--dry-run')
        if commercial and kind=='video':command.append('--commercial')
        # Existing clients validate URLs, page provenance, lengths and attribution sidecars.
        code=FF.main(command) if kind=='video' else FP.main(command)
        summary.append({'n':r['n'],'id':r['id'],'status':'ok' if code==0 else 'failed',
                        'dry_run':dry_run,'client':f'stock-{suffix}','exit_code':code})
    return summary

def write_links(rows,out,query):
    out=Path(out);out.parent.mkdir(parents=True,exist_ok=True)
    doc=['<!doctype html>','<html lang="ar" dir="rtl"><head><meta charset="utf-8">',
         '<meta http-equiv="Content-Security-Policy" content="default-src &#39;none&#39;; style-src &#39;unsafe-inline&#39;">',
         '<title>Media Hunter Links</title><style>body{font:18px sans-serif;max-width:850px;margin:3rem auto;line-height:1.8}a{color:#195c88}li{margin:12px 0}small{color:#777}</style></head><body>',
         '<h1>روابط بحث ميديا: '+html.escape(query)+'</h1><p>روابط اكتشاف، لا تعني أن الملفات مرخّصة.</p><ul>']
    for r in rows:
        link=html.escape(r['search_url'],quote=True)
        doc.append(f'<li><a rel="noopener noreferrer" target="_blank" href="{link}">{html.escape(r["name"])}</a> '
                   f'<small>{html.escape(r["status"])} · {html.escape(r["licence"])}</small></li>')
    doc.append('</ul></body></html>')
    out.write_text('\n'.join(doc)+'\n',encoding='utf-8')
    return out

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    sub=p.add_subparsers(dest='cmd',required=True)
    def qflags(sp):
        sp.add_argument('query');sp.add_argument('--type',choices=KINDS,default='any')
        sp.add_argument('--free',action='store_true')
    for cmd in ('sites','links'):
        a=sub.add_parser(cmd,help='offline source discovery; never claims live API results');qflags(a)
        a.add_argument('--limit',type=int,default=30)
        a.add_argument('--out',default='out/media-hunter/links.html' if cmd=='links' else None)
        a.add_argument('--json',action='store_true')
    for cmd in ('hunt','search'):
        a=sub.add_parser(cmd,help='live provider search via existing stock clients; never auto-downloads');qflags(a)
        a.add_argument('--orientation',choices=('portrait','landscape','square'))
        a.add_argument('--min-width',type=int)
        a.add_argument('--limit',type=int,default=30)
        a.add_argument('--per-source',type=int,default=15)
        a.add_argument('--sources',help='comma-separated provider IDs; others become discovery-only')
        a.add_argument('--out',default=str(DEFAULT_OUT),help='directory for results/last_hunt.json')
    a=sub.add_parser('get',help='download numbered results with stock client and attribution; requires explicit call')
    a.add_argument('numbers',nargs='+',type=int);a.add_argument('--out','-o',required=True)
    a.add_argument('--results',default=str(DEFAULT_OUT/'last_hunt.json'))
    a.add_argument('--max-mb',type=float,default=300);a.add_argument('--dry-run',action='store_true')
    a.add_argument('--commercial',action='store_true');a.add_argument('--acknowledge-rights',action='store_true')
    sub.add_parser('keys',help='show key names and configured status only; never values')
    a=sub.add_parser('build',help='snapshot documented source registry offline')
    a.add_argument('--out',default=str(DEFAULT_OUT/'sources.json'))
    args=p.parse_args(argv)
    try:
        if args.cmd=='keys':
            keys=sorted(set([s['key'] for s in source_rows() if s.get('key')]));
            print(json.dumps({'keys':{k:bool(os.environ.get(k)) for k in keys},'secrets_printed':False},ensure_ascii=False,indent=2));return 0
        if args.cmd=='build':
            rows=source_rows(); dest=Path(args.out);dest.parent.mkdir(parents=True,exist_ok=True)
            dest.write_text(json.dumps({'schema':SCHEMA,'sources':rows,'total':len(rows),'original_615_catalog':False},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
            print(json.dumps({'saved':str(dest),'sources':len(rows),'original_615_catalog':False}));return 0
        if args.cmd=='get':
            report=get(selected(args.results,args.numbers),args.out,args.results,dry_run=args.dry_run,
                       max_mb=args.max_mb,commercial=args.commercial,acknowledge_rights=args.acknowledge_rights)
            print(json.dumps({'results':report},ensure_ascii=False,indent=2))
            return 0 if all(v['status']=='ok' for v in report) else 4
        if args.cmd in ('sites','links'):
            if not 1<=args.limit<=500:raise ValueError('limit must be 1..500')
            rows=shortlist(english_query(args.query),args.type,args.free,args.limit)
            if args.cmd=='links':print(json.dumps({'file':str(write_links(rows,args.out,args.query)),
                                                  'sites':len(rows),'live_queries':0},ensure_ascii=False));return 0
            print(json.dumps({'query':args.query,'sites':rows,'listed':len(rows),'original_615_catalog':False},ensure_ascii=False,indent=2));return 0
        if args.cmd in ('hunt','search'):
            data=hunt(args.query,args.type,args.orientation,args.min_width,args.free,args.limit,
                      args.per_source,args.sources,args.out)
            if args.cmd=='hunt':print(json.dumps(data,ensure_ascii=False,indent=2))
            else:
                for r in data['results']:
                    print(f"{r['n']:>2} {r['source']:<12} {(r['title'] or '')[:48]:<48} {r['width']}x{r['height']} | {r['license']}")
                print(f"# {len(data['results'])} results, {len(data['searched_sources'])} providers attempted; report: {args.out}/last_hunt.json")
            return 0 if data['results'] or not data['searched_sources'] or any(v.get('status')=='ok' for v in data['searched_sources'].values()) else 3
    except (OSError,ValueError,TypeError,json.JSONDecodeError) as e:
        print(f'media-hunter: {type(e).__name__}: {str(e)[:200]}',file=sys.stderr);return 2
    return 2

if __name__=='__main__':sys.exit(main())
