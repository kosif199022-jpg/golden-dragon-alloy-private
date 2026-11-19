#!/usr/bin/env python3
"""Higgsfield Blender pilot: offline planning, packaging, source ledger, and local frame QA.
Never invokes a Higgsfield account, network installation, or paid API.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "skills" / "hf-blender-render"
REPORT = ROOT / "references" / "HF_BLENDER_RENDER_V19904.md"
SOURCE = ROOT / "references" / "HF_BLENDER_SOURCE_V19904.json"


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _plan(args):
    if args.frames < 1 or args.frames > 1_000_000:
        raise ValueError("frames must be between 1 and 1,000,000")
    if args.workers < 1 or args.workers > 16:
        raise ValueError("workers must be between 1 and 16")
    if args.samples < 1 or args.samples > 100_000:
        raise ValueError("samples out of range")
    if args.resolution < 10 or args.resolution > 100:
        raise ValueError("resolution must be 10..100 percent")
    size = (args.frames + args.workers - 1) // args.workers
    ranges = [[i * size + 1, min(args.frames, (i + 1) * size)] for i in range(args.workers) if i * size < args.frames]
    print(json.dumps({
        "status":"PLAN_ONLY", "engine":args.engine, "samples":args.samples,
        "resolution_percent":args.resolution, "total_frames":args.frames,
        "fps":args.fps, "duration_seconds":round(args.frames / args.fps, 4),
        "workers_requested":args.workers,"ranges":ranges,
        "gpu":"NOT_ASSUMED", "sandbox_cost":"UNVERIFIED",
        "requires_approval":["starting XL session", "downloading Blender", "remote execution", "uploading content"],
        "warning":"Parallel workers and memory load must be validated inside XL; renderer not executed here"
    },ensure_ascii=False,indent=2))


def _doctor(args):
    tools = ["python3", "blender", "ffmpeg", "ffprobe", "curl", "tar", "sha256sum"]
    print(json.dumps({
        "status":"LOCAL_INSPECTION_ONLY", "executables":{x:shutil.which(x) for x in tools},
        "script_files":{str(x.relative_to(SKILL)):x.exists() for x in sorted(SKILL.rglob("*")) if x.is_file()},
        "sandbox":"NOT_CONNECTED", "cloud_billing":"UNVERIFIED",
        "notes":"The bundled Cycles sample and shell render pipeline require separate runtime validation on an approved host."
    },ensure_ascii=False,indent=2))


def _pack(args):
    from importlib.util import module_from_spec, spec_from_file_location
    spec=spec_from_file_location("hf_pack",SKILL/"scripts"/"pack.py")
    mod=module_from_spec(spec);spec.loader.exec_module(mod)
    script_args=[args.job]+args.files+["--out",str(args.out)]
    if args.force:script_args+=["--force"]
    return mod.main(script_args)


def _check_frames(args):
    folder=Path(args.folder)
    files=sorted(folder.glob('f_*.png')) if folder.is_dir() else []
    by_name={x.name:x for x in files}
    expected={f'f_{i:04d}.png' for i in range(1,args.frames+1)}
    missing=sorted(expected-by_name.keys())
    extra=sorted(by_name.keys()-expected)
    truncated=[];dimensions=set()
    for name in sorted(by_name.keys() & expected):
        f=by_name[name]
        with f.open('rb') as fh:
            head=fh.read(24)
            size=f.stat().st_size
            if size>=12:
                fh.seek(-12,os.SEEK_END)
                end=fh.read()
            else:end=b''
        if len(head)<24 or head[:8]!=b'\x89PNG\r\n\x1a\n' or end[4:8]!=b'IEND':
            truncated.append(name)
        else:
            wh=(int.from_bytes(head[16:20],'big'),int.from_bytes(head[20:24],'big'))
            dimensions.add(wh)
    good=not (missing or extra or truncated or len(dimensions)>1)
    print(json.dumps({"status":"PASS" if good else "FAIL", "expected":args.frames,
                      "present":len(files), "missing":missing[:50], "extra":extra[:50],
                      "invalid":truncated[:50], "dimensions":[list(x) for x in sorted(dimensions)],
                      "checked":"PNG signature/IEND/size only; not a substitute for full decode or visual review"},indent=2))
    return 0 if good else 1


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    sub=p.add_subparsers(dest='command',required=True)
    sub.add_parser('doctor',help='local tools + bundled scripts (no network)')
    sub.add_parser('source',help='source ledger').set_defaults()
    sub.add_parser('policy',help='security/cost and remote operation notes')
    a=sub.add_parser('plan',help='offline chunk/frame plan')
    a.add_argument('--frames',type=int,default=150)
    a.add_argument('--workers',type=int,default=2)
    a.add_argument('--fps',type=int,choices=(24,25,30,60),default=30)
    a.add_argument('--samples',type=int,default=24)
    a.add_argument('--resolution',type=int,default=100)
    a.add_argument('--engine',choices=('CYCLES','EEVEE'),default='CYCLES')
    a=sub.add_parser('pack',help='package reviewed local scene files; does not upload or run them')
    a.add_argument('job')
    a.add_argument('files',nargs='+')
    a.add_argument('--out',required=True,type=Path)
    a.add_argument('--force',action='store_true')
    a=sub.add_parser('check-frames',help='verify local PNG frames 1..N')
    a.add_argument('folder')
    a.add_argument('--frames',type=int,required=True)
    args=p.parse_args(argv)
    try:
        if args.command=='doctor':_doctor(args)
        elif args.command=='plan':_plan(args)
        elif args.command=='pack':return _pack(args) or 0
        elif args.command=='source':print(SOURCE.read_text(encoding='utf-8'))
        elif args.command=='policy':print(REPORT.read_text(encoding='utf-8'))
        elif args.command=='check-frames':
            if not 1<=args.frames<=1_000_000:raise ValueError('frames out of range')
            return _check_frames(args)
    except (ValueError,FileNotFoundError,FileExistsError) as exc:
        print(f'ERROR: {exc}',file=sys.stderr);return 2
    return 0

if __name__=='__main__':raise SystemExit(main())
