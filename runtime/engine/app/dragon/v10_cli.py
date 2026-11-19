"""Black Dragon v10 CLI: grounded thinking, catalog truth, sample media, Kling and 7-stage gates."""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
from . import v10_cognition,v10_catalog,v10_media,v10_kling,v10_gate,v103_ultra,v104_council


def _out(payload,out=None):
    s=json.dumps(payload,ensure_ascii=False,indent=2)
    if out:
        p=Path(out);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(s+'\n',encoding='utf-8')
    print(s)


def main(argv=None):
    p=argparse.ArgumentParser(prog='dragon v10',description='Version 10 execution-honest workflows')
    s=p.add_subparsers(dest='action',required=True)
    t=s.add_parser('think',help='source-grounded cognitive review, not AI retraining')
    t.add_argument('task');t.add_argument('--domain',choices=('general','video','data','decision','research'),default='general')
    t.add_argument('--decision');t.add_argument('--out')
    cat=s.add_parser('catalog-audit',help='read-only counts, separate catalog methods from executable adapters')
    cat.add_argument('--limit',type=int,default=12);cat.add_argument('--out')
    media=s.add_parser('audit-media',help='read-only ffprobe fingerprint and optional deep QA')
    media.add_argument('files',nargs='+');media.add_argument('--deep',action='store_true');media.add_argument('--expect');media.add_argument('--out')
    kling=s.add_parser('kling-pack',help='text-only director pack; no generation or credits')
    kling.add_argument('spec');kling.add_argument('--out')
    link=s.add_parser('links',help='search the uploaded reference link index offline; never downloads')
    link.add_argument('--keyword',default='');link.add_argument('--limit',type=int,default=20);link.add_argument('--out')
    gate=s.add_parser('gate',help='7-stage job: init / record / qa / check / render')
    g=gate.add_subparsers(dest='gate_action',required=True)
    i=g.add_parser('init');i.add_argument('--job',required=True);i.add_argument('--brief',required=True)
    r=g.add_parser('record');r.add_argument('--job',required=True);r.add_argument('--stage',required=True,choices=tuple(x for x in v10_gate.STAGES if x!='qa-color'));r.add_argument('--data',required=True)
    q=g.add_parser('qa');q.add_argument('--job',required=True);q.add_argument('--expect')
    ck=g.add_parser('check');ck.add_argument('--job',required=True)
    rd=g.add_parser('render');rd.add_argument('--output',required=True);rd.add_argument('--job');rd.add_argument('--execute',action='store_true')
    rd.add_argument('--overwrite',action='store_true');rd.add_argument('--receipt');rd.add_argument('command',nargs=argparse.REMAINDER)
    ultra=s.add_parser('ultra',help='Ultra Mind: adaptive thinking scaffolds, falsification audit, forecast calibration')
    um=ultra.add_subparsers(dest='ultra_action',required=True)
    up=um.add_parser('plan',help='read-only 7-stage task-specific thinking plan')
    up.add_argument('task');up.add_argument('--domain',choices=v103_ultra.DOMAINS,default='general')
    up.add_argument('--level',choices=v103_ultra.LEVELS,default='L2');up.add_argument('--out')
    ua=um.add_parser('audit',help='validate review packet and independently hash local evidence files')
    ua.add_argument('packet');ua.add_argument('--out')
    uc=um.add_parser('calibrate',help='compute observed binary-forecast Brier score')
    uc.add_argument('predictions');uc.add_argument('--out')
    council=s.add_parser('council',help='Expert Council v10.4: plans, evidence-audits and private lessons')
    co=council.add_subparsers(dest='council_action',required=True)
    cp=co.add_parser('plan',help='Generate multi-lens council scaffold; never invokes agents')
    cp.add_argument('task');cp.add_argument('--domain',default='general')
    cp.add_argument('--size',choices=v104_council.SIZES,type=int,default=5);cp.add_argument('--out')
    ca=co.add_parser('audit',help='Review completed council packet and local SHA-256 evidence')
    ca.add_argument('packet');ca.add_argument('--out')
    cl=co.add_parser('lessons',help='Private ledger for user corrections and verified fixes')
    ls=cl.add_subparsers(dest='lessons_action',required=True)
    ladd=ls.add_parser('add');ladd.add_argument('--domain',required=True)
    for flag in ('trigger','mistake','lesson'):ladd.add_argument('--'+flag,required=True)
    ladd.add_argument('--severity',choices=('low','med','high'),default='med')
    ladd.add_argument('--source',choices=('user','self','test'),default='user')
    lsearch=ls.add_parser('search');lsearch.add_argument('query');lsearch.add_argument('--domain')
    ll=ls.add_parser('list');ll.add_argument('--domain')
    lstats=ls.add_parser('stats');lstats.add_argument('--domain')
    cl.add_argument('--store',help='Private JSONL outside skill (default ~/.black-dragon/expert-council/lessons.jsonl)')
    cl.add_argument('--limit',type=int,default=10)
    a=p.parse_args(argv)
    try:
        if a.action=='council':
            if a.council_action=='plan':_out(v104_council.plan(a.task,domain=a.domain,size=a.size),a.out)
            elif a.council_action=='audit':
                packet_file=Path(a.packet).resolve()
                result=v104_council.audit(json.loads(packet_file.read_text(encoding='utf-8')),packet_file.parent)
                _out(result,a.out)
                if not result['structure_pass']:return 5
            elif a.council_action=='lessons':
                store=Path(a.store).expanduser().resolve() if a.store else v104_council.default_ledger()
                if a.lessons_action=='add':obj=v104_council.add_lesson(store,a.domain,a.trigger,a.mistake,a.lesson,
                                                                     severity=a.severity,source=a.source)
                else:obj=v104_council.lessons(store,a.lessons_action,query=getattr(a,'query',''),
                                              domain=getattr(a,'domain',None),limit=a.limit)
                _out(obj)
            else:raise ValueError('unknown council command')
        elif a.action=='ultra':
            if a.ultra_action=='plan': _out(v103_ultra.plan(a.task,domain=a.domain,level=a.level),a.out)
            elif a.ultra_action=='audit':
                f=Path(a.packet).resolve()
                result=v103_ultra.audit(json.loads(f.read_text(encoding='utf-8')),f.parent)
                _out(result,a.out)
                if not result['structure_pass']:return 5
            elif a.ultra_action=='calibrate':
                _out(v103_ultra.calibrate(json.loads(Path(a.predictions).read_text(encoding='utf-8'))),a.out)
            else:raise ValueError('unknown ultra command')
        elif a.action=='think':
            doc=v10_cognition.checklist(a.task,domain=a.domain)
            if a.decision:
                d=json.loads(Path(a.decision).read_text(encoding='utf-8'))
                doc['decision_validation']={'errors':v10_cognition.validate_decision(d)}
            _out(doc,a.out)
        elif a.action=='catalog-audit':_out(v10_catalog.audit(a.limit),a.out)
        elif a.action=='audit-media':
            obj=v10_media.inspect(a.files,deep=a.deep,expect=a.expect);_out(obj,a.out)
            if not obj['all_probed']:return 1
        elif a.action=='kling-pack':_out(v10_kling.make_pack(json.loads(Path(a.spec).read_text(encoding='utf-8'))),a.out)
        elif a.action=='links':
            index=json.loads((Path(__file__).resolve().parent.parent/'data'/'v10_media_links.json').read_text(encoding='utf-8'))
            q=a.keyword.strip().casefold(); rows=[r for r in index['numbered']+index['extras'] if q in (r['url']+' '+r.get('caption','')).casefold()]
            if not 0<=a.limit<=200:raise ValueError('limit must be 0..200')
            _out({'kind':'black-dragon.v10/reference-index','total':len(index['numbered'])+len(index['extras']),
                  'matches':len(rows),'results':rows[:a.limit],'network_access':False,'rights_verified':False},a.out)
        else:
            ac=a.gate_action
            if ac=='init':obj=v10_gate.init(a.job,a.brief)
            elif ac=='record':obj=v10_gate.record(a.job,a.stage,a.data)
            elif ac=='qa':obj=v10_gate.qa(a.job,expect=a.expect)
            elif ac=='check':obj=v10_gate.check(a.job)
            elif ac=='render':obj=v10_gate.render_run(a.output,a.command,execute=a.execute,overwrite=a.overwrite,job=a.job)
            else:raise ValueError('unknown gate action')
            _out(obj,a.receipt if ac=='render' and a.receipt else None)
            if ac=='check' and not obj['pass']:return 5
        return 0
    except (ValueError,RuntimeError,OSError,TypeError,KeyError,json.JSONDecodeError) as exc:
        print(f'v10 {a.action}: {type(exc).__name__}: {exc}',file=sys.stderr)
        return 2

if __name__=='__main__':sys.exit(main())
