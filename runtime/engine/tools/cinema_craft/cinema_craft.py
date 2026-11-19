#!/usr/bin/env python3
"""Safe offline commands extracted from user-supplied black-dragon-cinema ideas.

    doctor
    spec-audit --input FILM_SPEC.json
    style --input FILM_SPEC.json --out NEW_SPEC.json
    cut --input VIDEO --start SEC --end SEC --out OUTPUT.mp4 [--fps N]

Never downloads media, installs packages, invokes a cloud provider or overwrites a file.
Original archive is retained as reference; this is a separately reviewed implementation.
"""
import argparse
import copy
import json
import math
import shutil
import subprocess
import sys
from pathlib import Path


def emit(x):
    print(json.dumps(x,ensure_ascii=False,indent=2))


def _run(args):
    return subprocess.run(args,capture_output=True,text=True,check=True)


def _load_spec(path):
    obj=json.loads(Path(path).read_text(encoding='utf-8-sig'))
    if not isinstance(obj,dict) or not isinstance(obj.get('shots'),list) or not isinstance(obj.get('texts',[]),list):
        raise ValueError('Film spec must contain shots list and optional texts list')
    if len(obj['shots'])>10000:raise ValueError('Too many shots')
    total=0
    for i,sh in enumerate(obj['shots']):
        if not isinstance(sh,dict) or not isinstance(sh.get('d'),(float,int)) or not math.isfinite(sh['d']) or sh['d']<=0:
            raise ValueError(f'shot {i}: positive finite d required')
        total+=sh['d']
    if 'duration' in obj and (not isinstance(obj['duration'],(float,int)) or not math.isfinite(obj['duration']) or obj['duration']<=0):
        raise ValueError('duration must be positive')
    for i,t in enumerate(obj.get('texts',[])):
        if not isinstance(t,dict):raise ValueError(f'text {i} must be a mapping')
    return obj,total


def audit(path):
    spec,total=_load_spec(path)
    duration=spec.get('duration',total)
    warnings=[]
    if abs(duration-total)>0.05:warnings.append(f'Shot durations total {total:.3f}s, expected {duration:.3f}s')
    missing=[i for i,s in enumerate(spec['shots']) if s.get('type','clip')=='clip' and not s.get('src')]
    if missing:warnings.append('Clip shots without src: '+','.join(map(str,missing)))
    return {'schema':'kosif.cinema-craft.audit.v1','shots':len(spec['shots']),'texts':len(spec.get('texts',[])), 'duration_sec':round(float(duration),6), 'shots_total_sec':round(total,6),'warnings':warnings, 'passed':not bool(warnings),'executed_media':False}


def restyle(src,dst):
    src=Path(src).resolve(); dst=Path(dst).resolve()
    if not src.is_file():raise FileNotFoundError(src)
    if src==dst or dst.exists():raise FileExistsError('Output must be new and different from source')
    spec,total=_load_spec(src)
    mod=copy.deepcopy(spec)
    changes=[]
    for i,sh in enumerate(mod['shots']):
        transition=sh.get('tr')
        if isinstance(transition,dict) and transition.get('type') in ('dissolve','leak'):
            before=transition['type'];transition['type']='iris'
            transition['d']=max(float(transition.get('d') or .0),.6)
            changes.append(f'shot {i} transition {before} -> iris')
        kb=sh.get('kb')
        if isinstance(kb,dict) and isinstance(kb.get('s0'),(float,int)) and isinstance(kb.get('s1'),(float,int)) and kb['s0']>kb['s1']:
            kb['s0'],kb['s1']=kb['s1'],kb['s0']
            changes.append(f'shot {i} camera scale now push-in')
    for i,tx in enumerate(mod.get('texts',[])):
        y=tx.get('y')
        if isinstance(y,(float,int)) and y>.74:
            tx['y']=.72 if y<.83 else .70
            changes.append(f'text {i} safe-zone y adjusted')
        if tx.get('glow') and not tx.get('gold'):
            tx.pop('glow');changes.append(f'text {i} excessive glow removed')
    dst.parent.mkdir(parents=True,exist_ok=True)
    dst.write_text(json.dumps(mod,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    emit({'created':str(dst),'source_unchanged':True,'changes':changes,'changes_count':len(changes)})


def probe(src,show_count=False):
    cmd=['ffprobe','-v','error','-select_streams','v:0']
    if show_count:cmd+=['-count_frames']
    cmd+=['-show_entries','stream=codec_name,width,height,avg_frame_rate,nb_read_frames','-of','json',str(src)]
    data=json.loads(_run(cmd).stdout)
    if not data.get('streams'):raise ValueError('No video stream')
    return data['streams'][0]


def cut(src,out,start,end,fps):
    src=Path(src).resolve();out=Path(out).resolve()
    if not src.is_file():raise FileNotFoundError(src)
    if out==src or out.exists():raise FileExistsError('Refusing to overwrite source or an existing output')
    if not all(math.isfinite(v) for v in [start,end]) or start<0 or end<=start:
        raise ValueError('start and end must be finite, with 0 <= start < end')
    if fps<=0 or fps>120:raise ValueError('fps must be 1..120')
    info=probe(src)
    frames=round((end-start)*fps)
    if frames<1:raise ValueError('Segment duration shorter than one output frame')
    if frames>54000:raise ValueError('Refusing cuts over 15 minutes in one operation')
    # Full reencode avoids the head/copy tail GOP and timestamp mismatch risk in legacy smart_cut.py.
    # Fixed CFR target means count is independent of source VFR layout.
    video=f'trim=start={start:.9f}:end={end:.9f},setpts=PTS-STARTPTS,fps={fps},scale=ceil(iw/2)*2:ceil(ih/2)*2,format=yuv420p'
    # A trimmed intermediate may have fewer frames than the exact requested CFR if source ends too early;
    # verify independently and fail rather than claiming success.
    audio_streams=json.loads(_run(['ffprobe','-v','error','-select_streams','a','-show_entries','stream=index','-of','json',str(src)]).stdout).get('streams',[])
    out.parent.mkdir(parents=True,exist_ok=True)
    tmp=out.with_name(out.stem+'.partial'+out.suffix)
    if tmp.exists():raise FileExistsError('Temporary output exists: '+str(tmp))
    cmd=['ffmpeg','-hide_banner','-nostdin','-v','error','-i',str(src),'-map','0:v:0']
    if audio_streams:cmd+=['-map','0:a:0']
    cmd+=['-vf',video,'-c:v','libx264','-crf','19','-preset','veryfast','-pix_fmt','yuv420p','-r',str(fps)]
    if audio_streams:
        cmd+=['-af',f'atrim=start={start:.9f}:end={end:.9f},asetpts=PTS-STARTPTS','-c:a','aac','-b:a','192k']
    cmd+=['-frames:v',str(frames),'-movflags','+faststart','-y',str(tmp)]
    try:
        _run(cmd)
        actual=probe(tmp,True)
        count=int(actual.get('nb_read_frames') or -1)
        if count!=frames:raise ValueError(f'Frame verification failed: expected {frames}, got {count}')
        tmp.replace(out)
    finally:
        if tmp.exists():tmp.unlink()
    emit({'created':str(out),'frames_verified':count,'expected_frames':frames,'fps':fps,'source_unchanged':True,'gpu_used':False,'cloud_used':False})


def main(argv=None):
    ap=argparse.ArgumentParser(prog='dragon.py tool cinema-craft',description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    sub=ap.add_subparsers(dest='command',required=True)
    sub.add_parser('doctor')
    c=sub.add_parser('spec-audit');c.add_argument('--input',required=True)
    c=sub.add_parser('style');c.add_argument('--input',required=True);c.add_argument('--out',required=True)
    c=sub.add_parser('cut');c.add_argument('--input',required=True);c.add_argument('--out',required=True);c.add_argument('--start',type=float,required=True);c.add_argument('--end',type=float,required=True);c.add_argument('--fps',type=int,default=30)
    args=ap.parse_args(argv)
    try:
        if args.command=='doctor':
            emit({'tool':'cinema-craft','status':'reviewed-local-adapter','ffmpeg':bool(shutil.which('ffmpeg')),'ffprobe':bool(shutil.which('ffprobe')),'node':bool(shutil.which('node')),'source':'_skills.rar','source_bundle':'references/source_archives/skills-rar/','reference_scripts_executed':False,'paid_generation':False});return 0
        if args.command=='spec-audit':
            report=audit(args.input);emit(report);return 0 if report['passed'] else 2
        if args.command=='style':restyle(args.input,args.out);return 0
        if args.command=='cut':cut(args.input,args.out,args.start,args.end,args.fps);return 0
    except (ValueError,FileNotFoundError,FileExistsError,subprocess.CalledProcessError, OSError, KeyError, json.JSONDecodeError) as ex:
        print(f'FAILED: {ex}',file=sys.stderr);return 2
    return 1

if __name__=='__main__':sys.exit(main())
