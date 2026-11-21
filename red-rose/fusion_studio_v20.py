"""Red Rose V20: independent original-code fusion of 5 owner-provided media archives.

Original SVG clay figure, editable frame timeline, spherical route geometry,
offline H264 MP4 rendering, and compatible iPhone export. No source engine is
called, imported or needed at runtime. Schematic illustration, NOT real GIS,
3D, full Remotion, content downloading or semantic AI media understanding.
"""
from __future__ import annotations
from html import escape
from functools import lru_cache
import io,base64,json,math,shutil,subprocess
from pathlib import Path

EARTH_KM=6371.0088
PRESETS={'iphone-vertical':(540,960),'iphone-story':(720,1280),'social-square':(720,720)}
PALETTES={'clay':('#b9dded','#8ec0a9','#e7ac76','#bf7255','#fdf0d5'),
          'night':('#122239','#304a69','#a18cbc','#dcae82','#fbe9d9'),
          'map':('#111b37','#203d5a','#32c4ac','#f4b75b','#e8f2f5')}

def number(value,lo,hi,name):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not lo<=value<=hi:
        raise ValueError(f'{name} must be a finite number in [{lo},{hi}]')
    return float(value)

def smooth(t):
    t=max(0.,min(1.,float(t)))
    return t*t*(3-2*t)

def greatcircle(a,b,samples=25):
    """Spherical interpolation of [longitude,latitude], not a road route."""
    if type(samples) is not int or not 2<=samples<=181:raise ValueError('samples must be 2..181')
    def coord(x):
        if not isinstance(x,(tuple,list)) or len(x)!=2:raise ValueError('coordinates must be [lon,lat]')
        return (number(x[0],-180,180,'lon'),number(x[1],-90,90,'lat'))
    x1,y1=coord(a);x2,y2=coord(b)
    def unit(x,y):
        x,y=math.radians(x),math.radians(y)
        return (math.cos(y)*math.cos(x),math.cos(y)*math.sin(x),math.sin(y))
    u,v=unit(x1,y1),unit(x2,y2)
    angle=math.acos(max(-1,min(1,sum(x*y for x,y in zip(u,v)))))
    if angle>math.pi-1e-7:raise ValueError('antipodal route requires waypoint')
    points=[]
    for i in range(samples):
        t=i/(samples-1)
        if angle<1e-9:vec=u
        else:
            aa=math.sin((1-t)*angle)/math.sin(angle);bb=math.sin(t*angle)/math.sin(angle)
            vec=tuple(aa*x+bb*y for x,y in zip(u,v))
        points.append([round(math.degrees(math.atan2(vec[1],vec[0])),6),
                       round(math.degrees(math.atan2(vec[2],math.hypot(vec[0],vec[1]))),6)])
    points[0]=[x1,y1];points[-1]=[x2,y2]
    return {'distance_km':round(EARTH_KM*angle,3),'coordinates':points,
            'method':'great-circle spherical interpolation, NOT travel directions',
            'has_geographic_basemap':False}

def plan(scenes,fps=24,preset='iphone-vertical'):
    if not isinstance(scenes,list) or not 1<=len(scenes)<=16:raise ValueError('scenes must have 1..16 items')
    if type(fps) is not int or fps not in (12,18,24,25,30,60):raise ValueError('unsupported fps')
    if preset not in PRESETS:raise ValueError('unknown preset')
    total=0;shots=[]
    for i,scene in enumerate(scenes):
        if not isinstance(scene,dict) or set(scene)-{'kind','title','duration','palette','from','to'}:
            raise ValueError('unknown scene fields')
        kind=scene.get('kind');palette=scene.get('palette',kind)
        if kind not in ('clay','map') or palette not in PALETTES:raise ValueError('unknown scene kind/palette')
        duration=number(scene.get('duration'),.25,12,'duration')
        title=scene.get('title','')
        if not isinstance(title,str) or len(title)>100:raise ValueError('title must be <=100 chars')
        n=max(1,round(fps*duration))
        if total+n>360:raise ValueError('render frame limit 360 exceeded')
        shot={'index':i,'kind':kind,'title':title,'palette':palette,
              'start_frame':total,'end_frame':total+n,'duration_frames':n}
        if kind=='map':shot['route']=greatcircle(scene.get('from'),scene.get('to'))
        shots.append(shot);total+=n
    w,h=PRESETS[preset]
    return {'schema':'red-rose-fusion-v20','fps':fps,'width':w,'height':h,
            'preset':preset,'frames':total,'duration_seconds':round(total/fps,5),
            'scenes':shots,'sources_runtime_required':False,'user_media_used':False}

@lru_cache(maxsize=3)
def _font():
    from PIL import ImageFont
    # Linux, Windows and macOS system fonts that contain Arabic glyphs.
    for p in ('/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf',
              '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
              'C:/Windows/Fonts/tahoma.ttf', 'C:/Windows/Fonts/arial.ttf',
              'C:/Windows/Fonts/segoeui.ttf', '/Library/Fonts/Arial Unicode.ttf'):
        if Path(p).is_file():return ImageFont.truetype(p,38,layout_engine=ImageFont.Layout.RAQM)
    return ImageFont.load_default(size=32)

def _caption(title,color):
    from PIL import Image,ImageDraw,ImageFont
    im=Image.new('RGBA',(540,112),(0,0,0,0))
    font=_font()
    opts={}
    # Text direction needs the RAQM layout engine; the bitmap fallback font has none.
    if getattr(font,'layout_engine',None)==ImageFont.Layout.RAQM:
        opts['direction']='rtl' if any('\u0600'<=c<='\u08ff' for c in title) else 'ltr'
    ImageDraw.Draw(im).text((270,53),title,font=font,anchor='mm',fill=color,**opts)
    buf=io.BytesIO();im.save(buf,format='PNG')
    return base64.b64encode(buf.getvalue()).decode('ascii')

def frame_svg(project,frame):
    if not isinstance(project,dict) or project.get('schema')!='red-rose-fusion-v20':raise ValueError('unknown timeline')
    if type(frame) is not int or frame<0 or frame>=project['frames']:raise ValueError('frame outside timeline')
    shot=next((s for s in project['scenes'] if s['start_frame']<=frame<s['end_frame']),None)
    if not shot:raise ValueError('timeline gap')
    t=(frame-shot['start_frame'])/max(1,shot['duration_frames']-1)
    p=PALETTES[shot['palette']]
    header=(f'<svg xmlns="http://www.w3.org/2000/svg" width="{project["width"]}" height="{project["height"]}" viewBox="0 0 540 960">'
            f'<defs><linearGradient id="sky" x2="0" y2="1"><stop stop-color="{p[0]}"/>'
            f'<stop offset="1" stop-color="{p[1]}"/></linearGradient><radialGradient id="clay">'
            f'<stop stop-color="{p[2]}"/><stop offset="1" stop-color="{p[3]}"/></radialGradient></defs>'
            '<rect width="540" height="960" fill="url(#sky)"/>')
    if shot['kind']=='clay':
        x=155+210*smooth(t);y=620+11*math.sin(6*math.pi*t)
        cat=(f'<path d="M0 55 Q-85 -15 -83 115 Q-30 155 0 117" fill="none" stroke="{p[3]}" stroke-width="28" stroke-linecap="round"/>'
             '<ellipse cx="0" cy="80" rx="89" ry="112" fill="url(#clay)"/>'
             f'<path d="M-79 -42 L-63 -144 L-11 -81 Z M15 -81 L74 -147 L83 -25 Z" fill="{p[3]}"/>'
             '<ellipse cx="0" cy="-47" rx="93" ry="83" fill="url(#clay)"/>'
             '<ellipse cx="-35" cy="-49" rx="10" ry="15" fill="#2d2535"/>'
             '<ellipse cx="35" cy="-49" rx="10" ry="15" fill="#2d2535"/>'
             '<path d="M-12 -12 L12 -12 L0 5 Z" fill="#a34b59"/>'
             '<path d="M0 5 Q-16 23 -26 6 M0 5 Q16 23 26 6" fill="none" stroke="#493a40" stroke-width="4"/>'
             f'<ellipse cx="-45" cy="165" rx="36" ry="19" fill="{p[3]}"/>'
             f'<ellipse cx="45" cy="165" rx="36" ry="19" fill="{p[3]}"/>')
        art=(f'<path d="M0 800 Q160 750 280 804 T540 807 V960 H0 Z" fill="{p[1]}"/>'
             f'<ellipse cx="{x}" cy="805" rx="103" ry="24" fill="#163b45" opacity=".25"/>'
             f'<g transform="translate({x:.2f} {y:.2f})">{cat}</g>')
    else:
        x1,y1=shot['route']['coordinates'][0];x2,y2=shot['route']['coordinates'][-1]
        sx,sy=100+340*((x1+180)%360)/360,225+470*(90-y1)/180
        ex,ey=100+340*((x2+180)%360)/360,225+470*(90-y2)/180
        if abs(ey-sy)<10:ey+=25
        bx,by=sx+(ex-sx)*smooth(t),sy+(ey-sy)*smooth(t)
        art='<rect x="48" y="210" width="444" height="520" rx="30" fill="#09203c" opacity=".7"/>'
        art+=''.join(f'<path d="M{x} 222 V720" stroke="#3e6e7a" opacity=".35"/>' for x in range(70,490,70))
        art+=''.join(f'<path d="M60 {y} H480" stroke="#3e6e7a" opacity=".35"/>' for y in range(250,720,65))
        art+=(f'<path d="M{sx:.1f} {sy:.1f} Q270 130 {ex:.1f} {ey:.1f}" fill="none" stroke="{p[3]}" stroke-width="5" stroke-dasharray="11 10"/>'
              f'<circle cx="{sx:.1f}" cy="{sy:.1f}" r="12" fill="{p[2]}"/>'
              f'<circle cx="{ex:.1f}" cy="{ey:.1f}" r="12" fill="{p[2]}"/>'
              f'<circle cx="{bx:.1f}" cy="{by:.1f}" r="15" fill="{p[3]}"/>'
              '<text x="270" y="780" text-anchor="middle" font-size="20" fill="#e3e9f4">SCHEMATIC • NOT A NAVIGATION MAP</text>')
    title=_caption(shot['title'],p[4])
    return header+art+'<title>'+escape(shot['title'])+'</title><image x="0" y="50" width="540" height="112" href="data:image/png;base64,'+title+'"/></svg>'

def render_video(project,output,*,approve_write=False):
    if not approve_write:raise PermissionError('approve_write required')
    target=Path(output).expanduser().resolve()
    if target.suffix.lower()!='.mp4' or target.exists() or not target.parent.is_dir():raise ValueError('new .mp4 output required')
    if project.get('frames',0)>360 or project.get('width',0)>1080 or project.get('height',0)>1920:raise ValueError('render budget exceeded')
    if not shutil.which('ffmpeg'):raise RuntimeError('FFmpeg required')
    import cairosvg
    from PIL import Image
    cmd=['ffmpeg','-hide_banner','-nostdin','-v','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s',f'{project["width"]}x{project["height"]}',
         '-r',str(project['fps']),'-i','pipe:0','-an','-c:v','libx264','-preset','veryfast','-crf','22','-pix_fmt','yuv420p','-movflags','+faststart',str(target)]
    proc=subprocess.Popen(cmd,stdin=subprocess.PIPE,stderr=subprocess.PIPE)
    try:
        for i in range(project['frames']):
            png=cairosvg.svg2png(bytestring=frame_svg(project,i).encode(),output_width=project['width'],output_height=project['height'])
            with Image.open(io.BytesIO(png)) as img:raw=img.convert('RGB').tobytes()
            proc.stdin.write(raw)
        proc.stdin.close();proc.stdin=None
        _,err=proc.communicate(timeout=120)
        if proc.returncode:raise RuntimeError('FFmpeg render failed '+err.decode(errors='replace')[-220:])
        return {'output':str(target),'frames':project['frames'],'fps':project['fps'],
                'dimensions':[project['width'],project['height']],'mode':'original SVG illustrated silent MP4'}
    except Exception:
        proc.kill();proc.communicate();target.unlink(missing_ok=True)
        raise

def iphone_export(source,output,*,approve_write=False,preset='iphone-vertical'):
    if not approve_write:raise PermissionError('approve_write required')
    if preset not in PRESETS:raise ValueError('invalid preset')
    src=Path(source).expanduser().resolve();dst=Path(output).expanduser().resolve()
    if not src.is_file() or src.suffix.lower() not in ('.mp4','.mov') or src.stat().st_size>1_000_000_000:
        raise ValueError('local MP4/MOV <=1GB required')
    if dst.suffix.lower()!='.mp4' or dst.exists() or not dst.parent.is_dir() or src==dst:
        raise ValueError('new MP4 output required')
    if not (shutil.which('ffmpeg') and shutil.which('ffprobe')):raise RuntimeError('FFmpeg and FFprobe required')
    data=subprocess.run(['ffprobe','-v','error','-show_entries','format=duration','-of','json',str(src)],
                        capture_output=True,text=True,check=True,timeout=30)
    dur=number(float(json.loads(data.stdout)['format']['duration']),.01,600,'duration')
    w,h=PRESETS[preset]
    vf=f'scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1'
    cmd=['ffmpeg','-hide_banner','-nostdin','-v','error','-n','-i',str(src),'-vf',vf,'-c:v','libx264',
         '-preset','veryfast','-crf','23','-pix_fmt','yuv420p','-movflags','+faststart','-c:a','aac',
         '-b:a','160k','-ar','48000','-t',str(dur),str(dst)]
    try:subprocess.run(cmd,capture_output=True,check=True,timeout=150)
    except Exception:
        dst.unlink(missing_ok=True)
        raise
    return {'output':str(dst),'preset':preset,'video_codec':'h264','pixel_format':'yuv420p',
            'audio_codec_if_present':'aac','copy_original_audio_if_present':True}
