"""Deterministic JSON-storyboard editing with FFmpeg. Does not create generative AI content."""
import json, re, shutil, subprocess, tempfile
from pathlib import Path

def run(cmd):
    p=subprocess.run([str(x) for x in cmd],capture_output=True,text=True)
    if p.returncode:
        raise RuntimeError('FFmpeg command failed: '+p.stderr[-2200:])
    return p.stdout

def json_probe(path):
    if not shutil.which('ffprobe'): raise RuntimeError('ffprobe missing. Install FFmpeg first.')
    if not path.exists(): raise FileNotFoundError(str(path))
    out=run(['ffprobe','-v','error','-show_format','-show_streams','-of','json',str(path)])
    return json.dumps(json.loads(out),ensure_ascii=False,indent=2)

def duration_of(path):
    data=json.loads(json_probe(path))
    d=data.get('format',{}).get('duration')
    if d is None:
        raise ValueError('Cannot read media duration: '+str(path))
    return float(d)

def storyboard(path,title,duration,shots):
    if not 1<=shots<=100: raise ValueError('shots must be 1..100')
    if not (duration>0): raise ValueError('duration must be positive')
    colors=['0x122826','0x29392d','0x2a263b','0x513427','0x20334a','0x3f3632']
    scenes=[{'id':f'{i+1:02d}','description':f'Shot {i+1}: describe framing, movement, subject and lighting','source':'','duration':round(duration/shots,3),'color':colors[i%len(colors)]} for i in range(shots)]
    data={'project':'KOSIF','title':title,'orientation':'9:16','audio_master':True,'shots':scenes}
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Storyboard created:',path)

def valid_color(raw):
    raw=str(raw or '0x122826')
    if not re.fullmatch(r'(0x|#)[0-9a-fA-F]{6}',raw): raise ValueError('Scene color must be 0xRRGGBB')
    return '0x'+raw[2:] if raw.startswith('0x') else '0x'+raw[1:]

def source_path(storyboard_path,s):
    if not s: return None
    p=Path(s).expanduser()
    if not p.is_absolute():p=storyboard_path.parent/p
    if not p.exists(): raise FileNotFoundError('Missing scene media: '+str(p))
    return p.resolve()

def build_scene(scene,path,seconds,width,height,fps,crf,storyboard_path):
    src=source_path(storyboard_path,scene.get('source',''))
    cmd=['ffmpeg','-hide_banner','-loglevel','error','-y']
    if src:
        if src.suffix.lower() in ('.jpg','.jpeg','.png','.webp','.bmp'):
            cmd+=['-loop','1','-framerate',str(fps),'-i',str(src)]
        else:
            cmd+=['-stream_loop','-1','-i',str(src)]
        vf=f'scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},fps={fps},format=yuv420p'
    else:
        cmd+=['-f','lavfi','-i',f'color=c={valid_color(scene.get("color"))}:s={width}x{height}:r={fps}']
        vf='format=yuv420p'
    cmd+=['-t',f'{seconds:.6f}','-an','-vf',vf,'-c:v','libx264','-preset','veryfast','-crf',str(crf),'-pix_fmt','yuv420p','-r',str(fps),'-movflags','+faststart',str(path)]
    run(cmd)

def render(storyboard_path,output_path,audio_path,width,height,fps,crf,keep_work=False):
    if not shutil.which('ffmpeg') or not shutil.which('ffprobe'):
        raise RuntimeError('Requires FFmpeg and FFprobe installed and on PATH.')
    if not storyboard_path.exists():raise FileNotFoundError(str(storyboard_path))
    if width<128 or height<128 or width%2 or height%2 or not 1<=fps<=120 or not 0<=crf<=51:
        raise ValueError('Invalid width/height/fps/crf values; dimensions must be even.')
    data=json.loads(storyboard_path.read_text(encoding='utf-8'))
    shots=data.get('shots',[])
    if not shots:raise ValueError('Storyboarding JSON needs at least one shot')
    if len(shots)>250:raise ValueError('Maximum 250 shots')
    durations=[float(s.get('duration',0)) for s in shots]
    if any(d<=0 for d in durations):raise ValueError('All shot durations must be positive')
    master=None
    if audio_path:
        audio_path=audio_path.expanduser().resolve()
        master=duration_of(audio_path)
        if master<=0:raise ValueError('Audio has no usable duration')
        factor=master/sum(durations)
        durations=[d*factor for d in durations]
    output_path.parent.mkdir(parents=True,exist_ok=True)
    def produce(work):
        paths=[]
        for i,(scene,seconds) in enumerate(zip(shots,durations)):
            output=work/f'{i:04}.mp4'; build_scene(scene,output,seconds,width,height,fps,crf,storyboard_path)
            paths.append(output)
            print(f'KOSIF rendered shot {i+1}/{len(shots)} ({seconds:.2f}s)',flush=True)
        concat=work/'timeline.ffconcat'
        concat.write_text('ffconcat version 1.0\n'+''.join("file '"+p.name+"'\n" for p in paths),encoding='utf-8')
        silent=work/'timeline.mp4'
        run(['ffmpeg','-hide_banner','-loglevel','error','-y','-safe','0','-f','concat','-i',str(concat),'-c','copy',str(silent)])
        if audio_path:
            run(['ffmpeg','-hide_banner','-loglevel','error','-y','-i',str(silent),'-i',str(audio_path),'-map','0:v:0','-map','1:a:0','-c:v','copy','-c:a','aac','-b:a','192k','-t',f'{master:.6f}','-movflags','+faststart',str(output_path)])
        else:
            shutil.copy2(silent,output_path)
    if keep_work:
        temp=output_path.with_suffix('.work');temp.mkdir(parents=True,exist_ok=True);produce(temp)
    else:
        with tempfile.TemporaryDirectory(prefix='kosif-film-') as work:produce(Path(work))
    report={'title':data.get('title'),'output':str(output_path),'audio':str(audio_path) if audio_path else None,'master_audio_seconds':master,'shot_durations_seconds':durations,'dimensions':[width,height],'fps':fps,'notes':'KOSIF helper rendered via FFmpeg; original third-party apps and model weights not embedded.'}
    report_file=output_path.with_suffix('.report.json')
    report_file.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print('KOSIF VIDEO READY:',output_path,'\nReport:',report_file)
