#!/usr/bin/env python3
"""KOSIF film CLI. Pure stdlib; FFmpeg/Git invoked externally only on explicit commands."""
import argparse, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'src'))
import kosif_registry as registry
import kosif_studio as studio

def main():
    p=argparse.ArgumentParser(description='KOSIF video production toolkit')
    s=p.add_subparsers(dest='command',required=True)
    a=s.add_parser('catalog',help='Show all KOSIF and third-party repository links')
    a.add_argument('--group',default='all'); a.add_argument('--json',action='store_true')
    a=s.add_parser('doctor',help='Check installed tools'); a.add_argument('--json',action='store_true')
    a=s.add_parser('install',help='Clone original sources to your machine; plan-only by default')
    a.add_argument('--group',default='own-video'); a.add_argument('--dest',default=str(ROOT/'workspace'/'sources'))
    a.add_argument('--execute',action='store_true',help='Actually run git clone; no install/build step')
    a=s.add_parser('storyboard',help='Create a JSON storyboard')
    a.add_argument('--output',default='project/storyboard.json'); a.add_argument('--title',default='KOSIF Film')
    a.add_argument('--duration',type=float,default=15); a.add_argument('--shots',type=int,default=3)
    a=s.add_parser('render',help='Make an MP4 from a storyboard and optional master audio')
    a.add_argument('--storyboard',required=True); a.add_argument('--output',required=True)
    a.add_argument('--audio'); a.add_argument('--width',type=int,default=1080); a.add_argument('--height',type=int,default=1920)
    a.add_argument('--fps',type=int,default=30); a.add_argument('--crf',type=int,default=20); a.add_argument('--keep-work',action='store_true')
    a=s.add_parser('probe',help='Print media metadata'); a.add_argument('file')
    args=p.parse_args()
    try:
        if args.command=='catalog': registry.catalog(ROOT,args.group,args.json)
        elif args.command=='doctor': registry.doctor(args.json)
        elif args.command=='install': registry.install(ROOT,args.group,Path(args.dest),args.execute)
        elif args.command=='storyboard': studio.storyboard(Path(args.output),args.title,args.duration,args.shots)
        elif args.command=='render': studio.render(Path(args.storyboard),Path(args.output),Path(args.audio) if args.audio else None,args.width,args.height,args.fps,args.crf,args.keep_work)
        elif args.command=='probe': print(studio.json_probe(Path(args.file)))
    except (ValueError,RuntimeError,FileNotFoundError) as err:
        print(f'KOSIF ERROR: {err}',file=sys.stderr); return 1
    return 0
if __name__=='__main__': sys.exit(main())
