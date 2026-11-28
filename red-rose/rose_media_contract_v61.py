"""V61 frame-native production contract and short-video prompt compiler."""
from __future__ import annotations
import json,re,math,hashlib,subprocess,unicodedata
from pathlib import Path
from fractions import Fraction
from decimal import Decimal
from functools import lru_cache
def exact_int(v,lo,hi):
    if type(v)!=int or not lo<=v<=hi:raise ValueError("invalid integer")
    return v
def text(v,maxlen=1000):
    if not isinstance(v,str) or not v.strip() or len(v)>maxlen or any(ord(c)<32 and c not in "\n\t" for c in v):raise ValueError("invalid text")
    return v.strip()
def sec(f,fps):return round(f/fps,6)
def compile_plan(j):
    fps=exact_int(j.get("fps",60),1,120);width=exact_int(j.get("width",1080),64,7680);height=exact_int(j.get("height",1920),64,7680)
    if width%2 or height%2:raise ValueError("even dimensions required")
    max_seconds=exact_int(j.get("max_seconds_per_clip",8),1,60)
    mode=j.get("mode","veo")
    if mode not in ("veo","local","dua"):raise ValueError("unsupported mode")
    character=text(j["character"],600);setting=text(j["setting"],500);style=text(j["style"],300)
    raw=j["shots"]
    if not isinstance(raw,list) or not 1<=len(raw)<=100:raise ValueError("shot count")
    out=[];issues=[];pos=0;clip=0;clip_pos=0
    for i,s in enumerate(raw):
        n=exact_int(s["frames"],1,fps*300);overlap=exact_int(s.get("overlap_frames",0),0,n-1)
        if i==0 and overlap:raise ValueError("first scene cannot overlap")
        if i and overlap>=out[-1]["frames"]:raise ValueError("overlap exceeds previous shot")
        if i and overlap+out[-1]["overlap_frames"]>=out[-1]["frames"]:raise ValueError("overlap creates triple blend or consumes scene")
        if mode=="veo" and overlap:raise ValueError("Veo clips must use explicit non-overlapping generation intervals")
        size=s.get("shot_size","medium")
        if size not in ("wide","medium","close-up","extreme close-up","two-shot"):raise ValueError("invalid shot size")
        action=text(s["action"],500);camera=text(s.get("camera","steady camera"),150)
        dialogue=s.get("dialogue","");speaker=s.get("speaker","")
        if dialogue:
            dialogue=text(dialogue,500);speaker=text(speaker,80)
            words=len(re.findall(r"[^\W_]+","".join(c for c in unicodedata.normalize("NFC",dialogue) if not unicodedata.category(c).startswith("M"))))
            # Heuristic for natural delivery, not a measured speech duration.
            if words>max(1,(n/fps-.3)*2.5):issues.append({"shot":i+1,"code":"dialogue_budget","words":words,"seconds":sec(n,fps)})
        if n>max_seconds*fps and mode=="veo":issues.append({"shot":i+1,"code":"clip_too_long"})
        if mode=="veo" and clip_pos and clip_pos+n>max_seconds*fps:clip+=1;clip_pos=0
        start=pos-overlap;end=start+n
        out.append({"id":i+1,"start_frame":start,"end_frame":end,"frames":n,"overlap_frames":overlap,"clip":clip+1,"clip_start_frame":clip_pos,"shot_size":size,"action":action,"camera":camera,"dialogue":dialogue,"speaker":speaker})
        pos=end;clip_pos+=n
    if pos>fps*300:raise ValueError("timeline too long")
    cues=j.get("captions",[])
    if not isinstance(cues,list) or len(cues)>1000:raise ValueError("caption count")
    last=0;cc=[]
    for c in cues:
        a=exact_int(c["start_frame"],0,pos-1);b=exact_int(c["end_frame"],a+1,pos)
        if a<last:raise ValueError("overlapping captions")
        cc.append({"start_frame":a,"end_frame":b,"text":text(c["text"],500)});last=b
    groups=[]
    if mode=="veo":
        for k in range(1,clip+2):
            shots=[s for s in out if s["clip"]==k];duration=sum(s["frames"] for s in shots)
            lines=[f"Create a {sec(duration,fps):g}-second vertical 9:16 video." if width*16==height*9 else f"Create a {sec(duration,fps):g}-second video, {width}:{height} aspect ratio.",f"Character continuity: {character}.",f"Setting: {setting}. Style: {style}."]
            for s in shots:
                a=s["clip_start_frame"];b=a+s["frames"]
                line=f"[{sec(a,fps):g}-{sec(b,fps):g}s] {s['shot_size']} shot. {s['action']}. Camera: {s['camera']}."
                if s["dialogue"]:line+=f' {s["speaker"]} says exactly: "{s["dialogue"]}".'
                lines.append(line)
            lines.append("Natural expressive movement, consistent character identity and lighting. Prioritize exact spoken dialogue. No unrequested captions, logos or watermarks.")
            groups.append({"clip":k,"frames":duration,"prompt":None if issues else "\n".join(lines)})
    return {"mode":mode,"fps":fps,"width":width,"height":height,"frames":pos,"seconds":sec(pos,fps),"shots":out,"captions":cc,"clips":groups,"warnings":issues,"ready_for_review":not issues and mode!="dua","speech_sync_verified":False,"visual_match_verified":False,"dua_asset_gate_required":mode=="dua","generation_performed":False}
def seek(p,f):
    exact_int(f,0,p["frames"]-1)
    a=[s for s in p["shots"] if s["start_frame"]<=f<s["end_frame"]]
    if len(a)>2 or not a:raise ValueError("invalid overlap")
    mix=0.
    if len(a)==2:
        k=a[-1];u=(f-k["start_frame"])/max(1,k["overlap_frames"]-1)
        u=1. if k["overlap_frames"]==1 else max(0.,min(1.,u));mix=u*u*(3-2*u)
    return {"frame":f,"active":[s["id"] for s in a],"mix":round(mix,8),"caption":next((c["text"] for c in p["captions"] if c["start_frame"]<=f<c["end_frame"]),None)}
def verify(path,contract):
    """Independent metadata/decoded-count/decode + first-frame black test; no artistic certification."""
    p=Path(path).resolve(strict=True);fps=contract["fps"];frames=contract["frames"];w=contract["width"];h=contract["height"]
    exact_int(fps,1,120);exact_int(frames,1,fps*300);exact_int(w,64,7680);exact_int(h,64,7680)
    if p.suffix.lower()!=".mp4":raise ValueError("MP4 required")
    audio=contract.get("audio_required",True)
    if type(audio)!=bool:raise ValueError("audio_required must be boolean")
    def run(args):return subprocess.run(args,capture_output=True,check=True,timeout=180)
    raw=run(["ffprobe","-v","error","-count_frames","-show_streams","-show_format","-of","json",str(p)])
    info=json.loads(raw.stdout);v=[s for s in info["streams"] if s["codec_type"]=="video"];a=[s for s in info["streams"] if s["codec_type"]=="audio"]
    checks={}
    def ck(k,b):checks[k]=bool(b)
    ck("one_video",len(v)==1);ck("audio_streams",len(a)==int(audio))
    if len(v)!=1:return {"technical_pass":False,"checks":checks,"artistic_verified":False}
    v=v[0];dur=frames/fps;tol=max(1/fps,.04)
    def num(s,k):
        try:
            v=float(s.get(k,"nan"));return v if math.isfinite(v) else None
        except (TypeError,ValueError):return None
    def near(s,k,x,t):
        v=num(s,k);return v is not None and abs(v-x)<=t
    ck("frame_count",str(v.get("nb_read_frames"))==str(frames))
    ck("dimensions",v.get("width")==w and v.get("height")==h)
    try:ck("fps",abs(float(Fraction(v["avg_frame_rate"]))-fps)<.02 and abs(float(Fraction(v["r_frame_rate"]))-fps)<.02)
    except (KeyError,ValueError,ZeroDivisionError):ck("fps",False)
    ck("video_codec",v.get("codec_name")=="h264" and v.get("pix_fmt")=="yuv420p")
    ck("video_duration",near(v,"duration",dur,tol));ck("video_start",near(v,"start_time",0,tol))
    if audio and len(a)==1:
        ck("audio_codec",a[0].get("codec_name")=="aac")
        ck("audio_duration",near(a[0],"duration",dur,max(.08,tol)))
        ck("audio_start",near(a[0],"start_time",0,max(.04,tol)))
    ck("container_duration",near(info["format"],"duration",dur,max(.08,tol)))
    ck("rotation",all(abs(x.get("rotation",0))<.01 for x in v.get("side_data_list",[]) if isinstance(x.get("rotation",0),(int,float))))
    try:run(["ffmpeg","-v","error","-xerror","-i",str(p),"-map","0:v:0","-map","0:a?","-f","null","-"]);ck("full_decode",True)
    except subprocess.SubprocessError:ck("full_decode",False)
    # Read exactly one frame; near-black threshold on small RGB preview is a heuristic.
    try:
        data=run(["ffmpeg","-v","error","-i",str(p),"-map","0:v:0","-frames:v","1","-vf","scale=64:64","-pix_fmt","rgb24","-f","rawvideo","pipe:1"]).stdout
        ck("first_frame_nonblack",len(data)==64*64*3 and sum(data)/len(data)>8)
    except subprocess.SubprocessError:ck("first_frame_nonblack",False)
    with p.open("rb") as f:digest=hashlib.file_digest(f,"sha256").hexdigest()
    return {"technical_pass":all(checks.values()),"checks":checks,"sha256":digest,"video_duration":num(v,"duration"),"audio_duration":num(a[0],"duration") if a else None,"artistic_verified":False,"speech_sync_verified":False,"constant_per_frame_pts_verified":False}
def handle(a):
    try:
        f=Path(a.spec)
        if f.stat().st_size>1024*1024:raise ValueError("spec too large")
        j=json.loads(f.read_text(encoding="utf-8"))
        if a.action=="verify":
            if not a.video:raise ValueError("--video required")
            r=verify(a.video,j);rc=0 if r["technical_pass"] else 2
        else:
            r=compile_plan(j)
            if a.action=="seek":r=seek(r,a.frame)
            rc=2 if a.action=="plan" and not r["ready_for_review"] else 0
        print(json.dumps(r,ensure_ascii=False,allow_nan=False));return rc
    except (ValueError,TypeError,KeyError,OSError,subprocess.SubprocessError) as e:
        print(json.dumps({"ok":False,"error":str(e)},ensure_ascii=False));return 1
def register(sub):
    p=sub.add_parser("media-contract");p.add_argument("action",choices=["plan","seek","verify"]);p.add_argument("spec");p.add_argument("--frame",type=int,default=0);p.add_argument("--video");p.set_defaults(ext_func=handle)
