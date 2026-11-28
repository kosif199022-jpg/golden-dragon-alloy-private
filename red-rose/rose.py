#!/usr/bin/env python3
"""Independent Red Rose memory, knowledge ingestion and planning core."""
# Read-only extension commands can bypass unrelated render imports.
if __name__ == '__main__':
    import sys as _sys
    from rose_fast_cli import dispatch as _fast_dispatch
    _fast_result = _fast_dispatch(_sys.argv[1:])
    if _fast_result is not None:
        raise SystemExit(_fast_result)

import argparse, hashlib, json, os, sqlite3, re, sys
from contextlib import closing
from pathlib import Path
from datetime import datetime, timezone
from styles import save as save_style, load as load_style, list_styles
from render import render
from production import produce
from speech import parse_srt, apply_captions
from alloy_fusion import import_alloy, find_fused, stats_fused
from knowledge_router import route as route_knowledge
from verify_media import verify_video
from identity import apply_profiles
from lip_sync import levels_from_audio, apply_lipsync
from visemes import estimate_words_from_srt, apply_visemes, validate_words
from pipeline_v15 import render_project
from scene_edit_v16 import analyze_cuts
from capability_runtime import list_capabilities, plan_task, execute as run_capability, audit_summary, REGISTRY
from qa_trace import trace as trace_qa

def connect(path):
    p=Path(path).expanduser(); p.parent.mkdir(parents=True,exist_ok=True)
    db=sqlite3.connect(p)
    db.execute('CREATE TABLE IF NOT EXISTS memories(id INTEGER PRIMARY KEY, created TEXT, category TEXT, content TEXT)')
    db.execute('CREATE TABLE IF NOT EXISTS knowledge(id INTEGER PRIMARY KEY, source TEXT, sha256 TEXT UNIQUE, content TEXT, imported TEXT)')
    db.execute('CREATE TABLE IF NOT EXISTS source_links(source TEXT, sha256 TEXT, origin TEXT, revision TEXT, license TEXT, PRIMARY KEY(source, sha256, origin, revision))')
    db.commit(); return db

SENSITIVE_NAMES={'.env','.npmrc','.pypirc','id_rsa','id_ed25519','credentials.json','secrets.json','settings.local.json'}
SENSITIVE_PARTS={'.git','node_modules','venv','.venv','owner-memory','private','secrets','credentials','.ssh'}

def ingest(db, directory, origin="local", revision="unversioned", license_id="unverified"):
    root=Path(directory).resolve(); count=0; skipped=0
    for p in root.rglob('*'):
        if not p.is_file() or p.is_symlink() or p.suffix.lower() not in {'.md','.txt','.py','.json','.yaml','.yml'} or p.stat().st_size>2_000_000: continue
        if p.name.lower() in SENSITIVE_NAMES or any(part.lower() in SENSITIVE_PARTS for part in p.relative_to(root).parts): skipped+=1; continue
        try: data=p.read_text(encoding='utf-8')
        except (UnicodeError,OSError): skipped+=1; continue
        # Do not send potential secrets to the knowledge database even on a PRIVATE repository.
        if re.search(r'-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----', data): skipped+=1; continue
        if re.search(r'(?im)^\s*(?:api[_-]?key|access[_-]?token|password|secret[_-]?key)\s*[:=]\s*[\"\']?[^\s\"\']{8,}', data): skipped+=1; continue
        digest=hashlib.sha256(data.encode()).hexdigest()
        cur=db.execute('INSERT OR IGNORE INTO knowledge(source,sha256,content,imported) VALUES(?,?,?,?)',(str(p.relative_to(root)),digest,data,datetime.now(timezone.utc).isoformat()))
        count+=cur.rowcount
        db.execute('INSERT OR IGNORE INTO source_links(source,sha256,origin,revision,license) VALUES(?,?,?,?,?)',
                   (str(p.relative_to(root)),digest,origin,revision,license_id))
    db.commit(); return {'imported':count,'unreadable':skipped}

def main(argv=None):
    # Windows PowerShell may inherit cp1252; UTF-8 is required for Arabic JSON.
    # A redirected in-memory test stream is left unchanged.
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    a=argparse.ArgumentParser(); a.add_argument('--db',default=os.environ.get('RED_ROSE_DB',str(Path.home()/'.red-rose'/'memory.sqlite3')))
    sub=a.add_subparsers(dest='command',required=True)
    sub.add_parser('doctor')
    x=sub.add_parser('remember'); x.add_argument('content'); x.add_argument('--category',default='lesson')
    x=sub.add_parser('recall'); x.add_argument('query',nargs='?',default=''); x.add_argument('--limit',type=int,default=20)
    x=sub.add_parser('ingest'); x.add_argument('directory'); x.add_argument('--origin',default='local');x.add_argument('--revision',default='unversioned');x.add_argument('--license',default='unverified')
    x=sub.add_parser('search'); x.add_argument('query'); x.add_argument('--limit',type=int,default=10)
    x=sub.add_parser('plan'); x.add_argument('task')
    x=sub.add_parser('style-save'); x.add_argument('name'); x.add_argument('recipe_json')
    x=sub.add_parser('style-show'); x.add_argument('name')
    sub.add_parser('style-list')
    x=sub.add_parser('render'); x.add_argument('output'); x.add_argument('--style'); x.add_argument('--duration',type=float,default=10); x.add_argument('--fps',type=int,default=24); x.add_argument('--width',type=int,default=540); x.add_argument('--height',type=int,default=960); x.add_argument('--mp4',action='store_true')
    x=sub.add_parser('produce'); x.add_argument('storyboard_json'); x.add_argument('output'); x.add_argument('--fps',type=int,default=24); x.add_argument('--width',type=int,default=540); x.add_argument('--height',type=int,default=960); x.add_argument('--audio'); x.add_argument('--srt'); x.add_argument('--lip-sync',action='store_true'); x.add_argument('--profiles'); x.add_argument('--viseme-sync',action='store_true'); x.add_argument('--words-json')
    sub.add_parser('sources')
    x=sub.add_parser('verify'); x.add_argument('video'); x.add_argument('--fps',type=float); x.add_argument('--width',type=int); x.add_argument('--height',type=int)
    x=sub.add_parser('fuse-alloy'); x.add_argument('source_db'); x.add_argument('--limit',type=int)
    x=sub.add_parser('fuse-search'); x.add_argument('query'); x.add_argument('--limit',type=int,default=20)
    sub.add_parser('fuse-stats')
    x=sub.add_parser('dragon-sync',help='import every Black/Golden Dragon memory and capability into Red Rose (idempotent)'); x.add_argument('--root',help='golden-dragon-alloy folder (default: beside red-rose)')
    x=sub.add_parser('dragon',help='search all dragon memories and capabilities'); x.add_argument('query'); x.add_argument('--limit',type=int,default=12)
    x=sub.add_parser('fuse-gd-knowledge',help='import the Golden Dragon knowledge base (active records only)'); x.add_argument('source',nargs='?',help='golden_dragon.sqlite or golden-dragon-runtime.zip (default: found on this PC)'); x.add_argument('--limit',type=int)
    x=sub.add_parser('speech-sync',help='tie cuts and captions to spoken words: script with @{marks} + word timings'); x.add_argument('script'); x.add_argument('words'); x.add_argument('--out'); x.add_argument('--fps',type=int,default=30); x.add_argument('--approve-write',action='store_true')
    x=sub.add_parser('flat-check',help='find blank/flat frames that blackdetect misses'); x.add_argument('video'); x.add_argument('--step',type=float,default=0.3); x.add_argument('--threshold',type=float,default=25.0)
    x=sub.add_parser('color-stats',help='mean Lab colour and saturation of a video'); x.add_argument('video'); x.add_argument('--start',type=float,default=0.0); x.add_argument('--duration',type=float)
    x=sub.add_parser('color-match',help='build a .cube LUT moving a clip to a reference video colour'); x.add_argument('reference'); x.add_argument('clip'); x.add_argument('--out'); x.add_argument('--start',type=float,default=0.0); x.add_argument('--duration',type=float); x.add_argument('--strength',type=float,default=0.9); x.add_argument('--lift',type=float,default=0.0); x.add_argument('--approve-write',action='store_true')
    x=sub.add_parser('line-times',help='on/off times of white on-screen text in a crop box of a reference video'); x.add_argument('video'); x.add_argument('--box',required=True,help='x:y:w:h in source pixels')
    x=sub.add_parser('toolbox',help='outside programs, libraries, repos and fonts found on this PC'); x.add_argument('--domain',choices=['montage','audio','image','thinking','utility']); x.add_argument('--find'); x.add_argument('--missing',action='store_true'); x.add_argument('--fonts',action='store_true')
    x=sub.add_parser('dua-reel',help='make a dua reel in the measured trending style from a plan JSON and a footage library'); x.add_argument('plan_json'); x.add_argument('output'); x.add_argument('--work'); x.add_argument('--storyboard',action='store_true',help='only write the storyboard image'); x.add_argument('--approve-write',action='store_true')
    x=sub.add_parser('fonts',help='font library: scan, list, find, show, preview, path, suggest, render, ass'); x.add_argument('action',choices=['scan','list','find','show','preview','path','suggest','render','ass','similar']); x.add_argument('args',nargs='*'); x.add_argument('--arabic',action='store_true'); x.add_argument('--style'); x.add_argument('--category'); x.add_argument('--filter'); x.add_argument('--text'); x.add_argument('--font'); x.add_argument('--size',type=int,default=120); x.add_argument('--colour',default='gold',choices=['gold','white']); x.add_argument('--commercial',action='store_true'); x.add_argument('--limit',type=int,default=8); x.add_argument('--approve-write',action='store_true')
    x=sub.add_parser('library',help='footage libraries: list, fetch from the private GitHub release'); x.add_argument('action',choices=['list','fetch']); x.add_argument('name',nargs='?'); x.add_argument('--dest'); x.add_argument('--approve-write',action='store_true')
    x=sub.add_parser('social',help='ScrapeCreators (paid): Instagram/TikTok/YouTube/... public data'); x.add_argument('action'); x.add_argument('args',nargs='*'); x.add_argument('--approve-spend',action='store_true'); x.add_argument('--approve-write',action='store_true'); x.add_argument('--out',default=None); x.add_argument('--cap',type=int,default=100); x.add_argument('--allow-long',action='store_true'); x.add_argument('--full',action='store_true')
    x=sub.add_parser('gpt',help='ChatGPT via the Black Rose app: status, read, ask, image'); x.add_argument('action',choices=['status','read','ask','image','save']); x.add_argument('prompt',nargs='?',default=''); x.add_argument('--out',default=None); x.add_argument('--new-chat',action='store_true'); x.add_argument('--approve-send',action='store_true'); x.add_argument('--approve-write',action='store_true')
    x=sub.add_parser('samak',help='bridge to the Black Rose app (SamakHub): tabs, start'); x.add_argument('action',choices=['tabs','start','tools'])
    x=sub.add_parser('duas',help='dua text catalogue: list, find, day, show, quran'); x.add_argument('action',choices=['list','find','day','show','quran']); x.add_argument('args',nargs='*'); x.add_argument('--section',choices=['day','time','occasion','general'])
    x=sub.add_parser('route'); x.add_argument('task'); x.add_argument('--limit',type=int,default=6)
    x=sub.add_parser('scene-analyze'); x.add_argument('source'); x.add_argument('--threshold',type=float,default=.23); x.add_argument('--sample-fps',type=int,default=6); x.add_argument('--min-shot-seconds',type=float,default=.65)
    x=sub.add_parser('timeline-analyze'); x.add_argument('source'); x.add_argument('--noise-db',type=float,default=-35); x.add_argument('--sample-fps',type=int,default=6)
    x=sub.add_parser('edit-suggest'); x.add_argument('source'); x.add_argument('--max-clips',type=int,default=3); x.add_argument('--max-duration',type=float,default=30); x.add_argument('--min-audible-ratio',type=float,default=.2)
    x=sub.add_parser('shot-score'); x.add_argument('source'); x.add_argument('--max-clips',type=int,default=3); x.add_argument('--max-duration',type=float,default=30); x.add_argument('--sample-fps',type=int,default=6)
    x=sub.add_parser('recut'); x.add_argument('source'); x.add_argument('edl_json'); x.add_argument('output'); x.add_argument('--fps',type=int,default=24); x.add_argument('--approve-write',action='store_true')
    sub.add_parser('roadmap')
    x=sub.add_parser('roadmap-topic'); x.add_argument('topic')
    x=sub.add_parser('roadmap-question'); x.add_argument('question',type=int)
    sub.add_parser('question-audit')
    x=sub.add_parser('question-trace'); x.add_argument('question_id')
    x=sub.add_parser('fusion-plan'); x.add_argument('scenes_json'); x.add_argument('--fps',type=int,default=24); x.add_argument('--preset',default='iphone-vertical')
    x=sub.add_parser('fusion-render'); x.add_argument('scenes_json'); x.add_argument('output'); x.add_argument('--fps',type=int,default=24); x.add_argument('--preset',default='iphone-vertical'); x.add_argument('--approve-write',action='store_true')
    x=sub.add_parser('iphone-export'); x.add_argument('source'); x.add_argument('output'); x.add_argument('--preset',default='iphone-vertical'); x.add_argument('--approve-write',action='store_true')
    sub.add_parser('capabilities')
    sub.add_parser('capability-audit')
    x=sub.add_parser('capability-plan'); x.add_argument('task')
    x=sub.add_parser('capability-run'); x.add_argument('capability_id'); x.add_argument('params_json'); x.add_argument('--approve-write',action='store_true')
    try:
        import rose_ext; rose_ext.load(sub)
    except Exception: pass
    args=a.parse_args(argv)
    if hasattr(args,'ext_func'): raise SystemExit(args.ext_func(args))
    if args.command=='verify':
        print(json.dumps(verify_video(args.video,expected_fps=args.fps,width=args.width,height=args.height),ensure_ascii=False)); return
    if args.command=='produce':
        result=render_project(args.storyboard_json,args.output,fps=args.fps,width=args.width,
                              height=args.height,audio=args.audio,srt=args.srt,
                              lip_sync=args.lip_sync,viseme_sync=args.viseme_sync,
                              profiles=args.profiles,words_json=args.words_json)
        print(json.dumps(result,ensure_ascii=False)); return
    if args.command=='scene-analyze':
        print(json.dumps(analyze_cuts(args.source,threshold=args.threshold,sample_fps=args.sample_fps,min_shot_seconds=args.min_shot_seconds),ensure_ascii=False)); return
    if args.command in ('timeline-analyze','edit-suggest'):
        ident='video.timeline_analyze' if args.command=='timeline-analyze' else 'video.edit_suggest'
        params={'source':args.source}
        if ident=='video.timeline_analyze':
            params.update(noise_db=args.noise_db,sample_fps=args.sample_fps)
        else:
            params.update(max_clips=args.max_clips,max_duration=args.max_duration,
                          min_audible_ratio=args.min_audible_ratio)
        with closing(connect(args.db)) as db:
            result=run_capability(db,ident,params)
        print(json.dumps(result,ensure_ascii=False)); return
    if args.command=='shot-score':
        with closing(connect(args.db)) as db:
            result=run_capability(db,'video.shot_score',{'source':args.source,'max_clips':args.max_clips,
                        'max_duration':args.max_duration,'sample_fps':args.sample_fps})
        print(json.dumps(result,ensure_ascii=False)); return
    if args.command=='recut':
        edl=json.loads(Path(args.edl_json).expanduser().read_text(encoding='utf-8'))
        with closing(connect(args.db)) as db:
            result=run_capability(db,'video.recut',{'source':args.source,'segments':edl,
                        'output':args.output,'fps':args.fps},approve_write=args.approve_write)
        print(json.dumps(result,ensure_ascii=False)); return
    if args.command in ('roadmap','roadmap-topic','roadmap-question'):
        import roadmap_1400
        if args.command=='roadmap': result=roadmap_1400.summary(registry=REGISTRY)
        elif args.command=='roadmap-topic': result=roadmap_1400.explain_topic(args.topic,registry=REGISTRY)
        else: result=roadmap_1400.explain_question(args.question,registry=REGISTRY)
        print(json.dumps(result,ensure_ascii=False)); return
    if args.command in ('question-audit','question-trace'):
        print(json.dumps(trace_qa(args.question_id if args.command=='question-trace' else None,registry=REGISTRY),ensure_ascii=False)); return
    if args.command in ('fusion-plan','fusion-render','iphone-export'):
        if args.command=='iphone-export':
            action='media.iphone_export'
            params={'source':args.source,'output':args.output,'preset':args.preset}
        else:
            scenes=json.loads(Path(args.scenes_json).expanduser().read_text(encoding='utf-8'))
            action='fusion.plan' if args.command=='fusion-plan' else 'fusion.render'
            params={'scenes':scenes,'fps':args.fps,'preset':args.preset}
            if args.command=='fusion-render':params['output']=args.output
        with closing(connect(args.db)) as db:
            result=run_capability(db,action,params,approve_write=getattr(args,'approve_write',False))
        print(json.dumps(result,ensure_ascii=False));return
    if args.command in ('flat-check','color-stats','color-match','line-times'):
        import reel_tools_v32 as rt
        if args.command=='flat-check': result=rt.flat_check(args.video,args.step,args.threshold)
        elif args.command=='color-stats': result=rt.color_stats(args.video,args.start,args.duration)
        elif args.command=='color-match': result=rt.color_match(args.reference,args.clip,args.out,args.start,args.duration,args.strength,args.lift,args.approve_write)
        else:
            bx,by,bw,bh=[int(v) for v in args.box.split(':')]
            result=rt.line_times(args.video,bx,by,bw,bh)
        result={k:v for k,v in result.items() if not k.startswith('_')}
        print(json.dumps(result,ensure_ascii=False))
        if result.get('outcome')=='approval_required': raise SystemExit(3)
        if args.command=='flat-check' and not result['ok']: raise SystemExit(1)
        return
    if args.command=='dua-reel':
        import dua_reel_v34
        plan=json.loads(Path(args.plan_json).expanduser().read_text(encoding='utf-8-sig'))
        result=dua_reel_v34.build(plan,args.output,args.work,args.approve_write,args.storyboard)
        print(json.dumps(result,ensure_ascii=False))
        if result.get('outcome')=='approval_required': raise SystemExit(3)
        if not result.get('ok'): raise SystemExit(1)
        return
    if args.command=='library':
        import media_library_v35 as ml
        result=ml.listing() if args.action=='list' else ml.fetch(args.name or 'dua',args.dest,args.approve_write)
        print(json.dumps(result,ensure_ascii=False))
        if result.get('outcome')=='approval_required': raise SystemExit(3)
        return
    if args.command=='fonts':
        import font_library_v35 as fl
        a=args.action
        if a=='scan': result=fl.scan(args.args,args.approve_write)
        elif a=='list':
            result=fl.listing(args.arabic,args.style,args.filter)
            if args.category:
                result['fonts']=[f for f in result['fonts'] if f.get('category')==args.category]; result['count']=len(result['fonts'])
        elif a=='suggest': result=fl.suggest(' '.join(args.args) or 'ترند',args.limit,args.commercial)
        elif a=='ass': result=fl.ass_name(' '.join(args.args))
        elif a=='similar':
            import font_shape_v38 as fs
            result=fs.similar(' '.join(args.args),args.limit)
        elif a=='render':
            if len(args.args)<1 or not args.font: raise SystemExit('fonts render OUT.png --text "..." --font NAME')
            result=fl.render_text(args.text or fl.SAMPLE,args.args[0],args.font,args.size,args.colour,1080,args.approve_write)
        elif a=='find': result=fl.listing(args.arabic,args.style,' '.join(args.args))
        elif a in ('show','path'):
            r=fl.find_one(' '.join(args.args)); result={'ok':bool(r),'font':r} if a=='show' else {'ok':bool(r),'path':r and r['file']}
        else:
            if not args.args: raise SystemExit('fonts preview OUT.png')
            result=fl.preview(args.args[0],args.filter,args.text or fl.SAMPLE,True,60,args.approve_write)
        print(json.dumps(result,ensure_ascii=False))
        if result.get('outcome')=='approval_required': raise SystemExit(3)
        return
    if args.command=='social':
        import scrapecreators_v44 as sc
        a, rest = args.action, list(args.args)
        try:
            if a=='endpoints':
                result=sc.endpoints(' '.join(rest))
            elif a=='usage':
                result=sc.usage()
            else:
                if a=='credits':
                    path, params = '/v1/account/credit-balance', {}
                elif a=='get':
                    if not rest: raise sc.SocialError('usage: social get PATH key=value ...')
                    path, params = rest[0], dict(x.split('=',1) for x in rest[1:] if '=' in x)
                elif a in sc.SHORTCUTS:
                    path, field = sc.SHORTCUTS[a]
                    params = {field: ' '.join(rest)} if field else {}
                    if field and not rest: raise sc.SocialError(f'{a} needs a {field}')
                else:
                    raise sc.SocialError(f'unknown action {a!r}: endpoints, usage, credits, get, ' + ', '.join(sc.SHORTCUTS))
                if args.out and not args.approve_write:
                    raise sc.SocialError('--out writes a file: add --approve-write')
                result=sc.call(path, params, args.approve_spend, cap=args.cap, allow_long=args.allow_long)
                if result.get('ok') and args.out:
                    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
                    Path(args.out).write_text(json.dumps(result['data'],ensure_ascii=False,indent=1),encoding='utf-8')
                    result['saved']=str(Path(args.out).resolve())
                if 'data' in result and not args.full:
                    d=result['data']; result['data_keys']=list(d)[:25] if isinstance(d,dict) else type(d).__name__
                    result.pop('data')
        except sc.SocialError as exc:
            result={'ok':False,'outcome':'error','error':str(exc)}
        print(json.dumps(result,ensure_ascii=False))
        if not result.get('ok'): raise SystemExit(3 if result.get('outcome')=='approval_required' else 1)
        return
    if args.command=='gpt':
        import samak_bridge_v42 as sb
        import samak_gpt_v43 as g
        a=args.action
        if a in ('ask','image') and not args.prompt:
            print(json.dumps({'ok':False,'outcome':'error','error':'a prompt is required'},ensure_ascii=False)); raise SystemExit(2)
        if a in ('ask','image') and not args.approve_send:
            print(json.dumps({'ok':False,'outcome':'approval_required','nothing_sent':True,'needs':'--approve-send (sends the prompt to ChatGPT)'},ensure_ascii=False)); raise SystemExit(3)
        if a in ('image','save') and (not args.out or not args.approve_write):
            print(json.dumps({'ok':False,'outcome':'approval_required','nothing_sent':True,'needs':'--out DIR and --approve-write (saves the image)'},ensure_ascii=False)); raise SystemExit(3)
        try:
            result = g.status() if a=='status' else g.read() if a=='read' else                      g.ask(args.prompt, new_chat=args.new_chat) if a=='ask' else \
                     g.save(args.out) if a=='save' else g.image(args.prompt, args.out)
        except sb.BridgeError as exc:
            result={'ok':False,'outcome':'error','error':str(exc)}
        print(json.dumps(result,ensure_ascii=False))
        if not result.get('ok'): raise SystemExit(1)
        return
    if args.command=='samak':
        import samak_bridge_v42 as sb
        try:
            with sb.Bridge(timeout=120) as b:
                if args.action=='start':
                    result={'ok':True,'result':b.call('start_app')}
                elif args.action=='tools':
                    result={'ok':True,'tools':sorted(t['name'] for t in b._request('tools/list',{}).get('tools',[]))}
                else:
                    t=b.call('list_all_tabs')
                    result={'ok':True,'tabs':[{k:x.get(k) for k in ('key','company','url','open','is_popup')} for x in t.get('tabs',[])]}
        except sb.BridgeError as exc:
            result={'ok':False,'outcome':'error','error':str(exc),'hint':'open the Black Rose app, or run: rose.py samak start'}
        print(json.dumps(result,ensure_ascii=False))
        if not result.get('ok'): raise SystemExit(1)
        return
    if args.command=='duas':
        import dua_catalog_v40 as dc
        a=args.action
        if a=='list': result=dc.listing(args.section)
        elif a=='find': result=dc.find(' '.join(args.args))
        elif a=='day': result=dc.by_day(' '.join(args.args) or 'friday')
        elif a=='show': result=dc.show(' '.join(args.args))
        else: result=dc.quran()
        print(json.dumps(result,ensure_ascii=False))
        if not result.get('ok'): raise SystemExit(1)
        return
    if args.command=='toolbox':
        import toolbox_v33
        result={'ok':True,'fonts':toolbox_v33.fonts()} if args.fonts else toolbox_v33.summary(args.domain,args.find,args.missing)
        print(json.dumps(result,ensure_ascii=False)); return
    if args.command=='speech-sync':
        import speech_sync_v31
        result=speech_sync_v31.run(args.script,args.words,args.out,args.fps,args.approve_write)
        print(json.dumps(result,ensure_ascii=False))
        if result.get('outcome')=='approval_required': raise SystemExit(3)
        return
    if args.command=='capabilities':
        print(json.dumps(list_capabilities(),ensure_ascii=False)); return
    if args.command=='plan': print(json.dumps({'task':args.task,'steps':['inspect','plan','execute','verify','learn'],'status':'planned_not_executed'},ensure_ascii=False)); return
    with closing(connect(args.db)) as db:
        if args.command=='doctor': result={'memory':'ready','knowledge_documents':db.execute('SELECT count(*) FROM knowledge').fetchone()[0],'legacy_skill_runtime_required':False}
        elif args.command=='remember':
            cur=db.execute('INSERT INTO memories(created,category,content) VALUES(?,?,?)',(datetime.now(timezone.utc).isoformat(),args.category,args.content)); db.commit();result={'saved':True,'id':cur.lastrowid}
        elif args.command=='recall':
            rows=db.execute('SELECT id,category,content FROM memories WHERE content LIKE ? ORDER BY id DESC LIMIT ?',('%'+args.query+'%',max(1,min(args.limit,100)))).fetchall();result=[{'id':r[0],'category':r[1],'content':r[2]} for r in rows]
        elif args.command=='ingest': result=ingest(db,args.directory,args.origin,args.revision,args.license)
        elif args.command=='style-save': result=save_style(db,args.name,json.loads(args.recipe_json))
        elif args.command=='style-show': result=load_style(db,args.name)
        elif args.command=='style-list': result=list_styles(db)
        elif args.command=='fuse-alloy': result=import_alloy(db,args.source_db,args.limit)
        elif args.command=='fuse-search': result=find_fused(db,args.query,args.limit)
        elif args.command=='fuse-stats': result=stats_fused(db)
        elif args.command=='dragon-sync':
            from dragon_memory_v47 import dragon_sync
            result=dragon_sync(db,args.root)
        elif args.command=='dragon':
            from dragon_memory_v47 import dragon_search
            result=dragon_search(db,args.query,args.limit)
        elif args.command=='fuse-gd-knowledge':
            from gd_knowledge_v31 import import_gd_knowledge
            result=import_gd_knowledge(db,args.source,args.limit)
        elif args.command=='route': result=route_knowledge(db,args.task,args.limit)
        elif args.command=='capability-audit': result=audit_summary(db)
        elif args.command=='capability-plan': result=plan_task(db,args.task)
        elif args.command=='capability-run': result=run_capability(db,args.capability_id,json.loads(args.params_json),approve_write=args.approve_write)
        elif args.command=='sources': result=[dict(zip(('source','sha256','origin','revision','license'),r)) for r in db.execute('SELECT * FROM source_links ORDER BY origin,source LIMIT 1000')]
        elif args.command=='render':
            saved=load_style(db,args.style) if args.style else None
            if args.style and not saved: raise ValueError('Unknown style: '+args.style)
            result=render(args.output,args.duration,args.fps,args.width,args.height,saved['recipe'] if saved else None,args.mp4)
        elif args.command=='search':
            rows=db.execute('SELECT source,substr(content,1,500) FROM knowledge WHERE content LIKE ? LIMIT ?',('%'+args.query+'%',max(1,min(args.limit,100)))).fetchall();result=[{'source':r[0],'excerpt':r[1]} for r in rows]
    print(json.dumps(result,ensure_ascii=False))
if __name__=='__main__':main()
