"""V65: native local montage with verified resumable chunks and frame-exact cuts.
General montage only, not a dua/reference-style renderer. No external services.
"""
from pathlib import Path
import json,hashlib,subprocess,os,math,tempfile,shutil
from fractions import Fraction
from contextlib import contextmanager
SCHEMA=1
def integer(v,a,b):
    if type(v)!=int or not a<=v<=b:raise ValueError("invalid integer")
    return v
def scalar(v,a,b):
    if type(v) not in (int,float) or not math.isfinite(v) or not a<=v<=b:raise ValueError("invalid numeric value")
    return float(v)
def digest(p):
    with Path(p).open("rb") as f:return hashlib.file_digest(f,"sha256").hexdigest()
def key(j):
    return hashlib.sha256(json.dumps(j,sort_keys=True,ensure_ascii=False,allow_nan=False,separators=(",",":")).encode()).hexdigest()
def local_file(root,name,extensions):
    if not isinstance(name,str) or len(name)>1024:raise ValueError("invalid path")
    p=Path(name)
    if p.is_absolute() or ".." in p.parts:raise ValueError("relative paths only")
    p=(root/p).resolve(strict=True)
    if not p.is_relative_to(root) or not p.is_file() or p.suffix.lower() not in extensions:raise ValueError("invalid local asset")
    return p
def run(args,timeout=180):
    r=subprocess.run([str(x) for x in args],capture_output=True,timeout=timeout)
    if r.returncode:raise RuntimeError("media command failed: "+r.stderr.decode("utf-8",errors="replace")[-1200:])
    return r.stdout
def ff(args,timeout=180):
    return run(["ffmpeg","-hide_banner","-loglevel","error","-nostdin","-xerror","-filter_threads","2","-filter_complex_threads","2",*args],timeout)
def probe(p,count=False):
    return json.loads(run(["ffprobe","-v","error","-protocol_whitelist","file,pipe",*(["-count_frames"] if count else []),"-show_streams","-show_format","-of","json",p]))
def plan(j):
    if j.get("kind")!="general":
        if str(j.get("kind","")).casefold().strip() in ("dua","duaa","azkar","prayer","دعاء","أذكار","اذكار") and "dua_gate" in j:
            from rose_dua_gate_v69 import check
            check(j["dua_gate"])
        raise ValueError("only explicitly declared general montage; dua must use mandatory owner workflow")
    if "dua_gate" in j:raise ValueError("dua contract cannot be passed as general montage")
    if j.get("rights_confirmed") is not True:raise ValueError("approved asset rights declaration required")
    fps=integer(j.get("fps",30),24,60)
    if fps not in (24,25,30,50,60):raise ValueError("unsupported fps")
    w=integer(j.get("width",1080),64,2160);h=integer(j.get("height",1920),64,3840)
    if w%2 or h%2:raise ValueError("even dimensions")
    root=Path(j["workspace"]).resolve(strict=True)
    if not root.is_dir():raise ValueError("workspace required")
    shots=j["shots"]
    if type(shots)!=list or not 1<=len(shots)<=24:raise ValueError("1-24 shots")
    out=[];pos=0
    for i,s in enumerate(shots):
        p=local_file(root,s["file"],{".mp4",".mov",".mkv",".webm",".png",".jpg",".jpeg"})
        still=p.suffix.lower() in (".png",".jpg",".jpeg")
        n=integer(s["frames"],1,fps*120);start=integer(s.get("source_start_frame",0),0,fps*3600)
        overlap=integer(s.get("overlap_frames",0),0,n-1);transition=s.get("transition","cut")
        if (overlap==0 and transition!="cut") or (overlap>0 and transition not in ("fade","smooth-fade")):raise ValueError("transition/overlap mismatch")
        if i==0 and overlap:raise ValueError("first shot overlap")
        if i and overlap+out[-1]["overlap"]>=out[-1]["frames"]:raise ValueError("overlap consumes prior shot or creates triple blend")
        if still and start:raise ValueError("still cannot have source offset")
        zoom=scalar(s.get("zoom_end",1),1,1.5)
        if not still and zoom!=1:raise ValueError("zoom currently available for stills only")
        pos-=overlap
        out.append({"file":str(p),"sha256":digest(p),"still":still,"start":start,"frames":n,"overlap":overlap,"transition":transition,"zoom_end":zoom,"timeline_start":pos})
        pos+=n
    if pos>fps*300:raise ValueError("timeline exceeds 5 minutes")
    audio=None
    if j.get("audio") is not None:
        p=local_file(root,j["audio"],{".wav",".mp3",".m4a",".aac",".flac",".mp4"})
        audio={"file":str(p),"sha256":digest(p),"normalize":j.get("normalize_audio",False)}
        if type(audio["normalize"])!=bool:raise ValueError("normalize_audio boolean")
    elif j.get("allow_silent") is not True:raise ValueError("explicit audio or allow_silent required")
    return {"schema":SCHEMA,"workspace":str(root),"fps":fps,"width":w,"height":h,"frames":pos,"shots":out,"audio":audio,"rights_declared":True,"artistic_verified":False}
def video_check(p,n,fps,w,h,audio=False,pts=False):
    info=probe(p,True);v=[s for s in info["streams"] if s["codec_type"]=="video"];a=[s for s in info["streams"] if s["codec_type"]=="audio"]
    if len(v)!=1 or len(a)!=int(audio):raise ValueError("stream count mismatch")
    v=v[0]
    if not (v["codec_name"]=="h264" and v["pix_fmt"]=="yuv420p" and v["width"]==w and v["height"]==h and int(v.get("nb_read_frames",-1))==n and Fraction(v["avg_frame_rate"])==fps):raise ValueError("video contract mismatch")
    dur=n/fps
    if abs(float(v["duration"])-dur)>1/fps+.001:raise ValueError("video duration mismatch")
    if audio and (a[0]["codec_name"]!="aac" or abs(float(a[0]["duration"])-dur)>.08):raise ValueError("audio duration/codec mismatch")
    ff(["-i",p,"-map","0:v:0","-map","0:a?","-f","null","-"])
    if pts:
        frames=json.loads(run(["ffprobe","-v","error","-select_streams","v:0","-show_frames","-show_entries","frame=best_effort_timestamp","-of","json",p]))["frames"]
        tb=Fraction(v["time_base"])
        if len(frames)!=n or any(Fraction(int(x["best_effort_timestamp"]))*tb!=Fraction(i,fps) for i,x in enumerate(frames)):raise ValueError("nonconstant presentation timestamps")
    return {"frames":n,"sha256":digest(p),"full_decode":True,"exact_pts":bool(pts)}
def encode_args(fps,n):
    return ["-frames:v",n,"-an","-c:v","libx264","-preset","veryfast","-crf","18","-threads","2","-pix_fmt","yuv420p","-r",fps,"-video_track_timescale","90000","-movflags","+faststart"]
@contextmanager
def job_lock(path):
    # The kernel releases the byte/file lock if a process crashes. The lock file
    # itself stays in place, avoiding stale-PID checks and split-lock races.
    if path.is_symlink():raise ValueError("lock symlink")
    with path.open("a+b") as f:
        f.seek(0,2)
        if not f.tell():f.write(b"0");f.flush()
        f.seek(0)
        if os.name=="nt":
            import msvcrt
            msvcrt.locking(f.fileno(),msvcrt.LK_NBLCK,1)
        else:
            import fcntl
            fcntl.flock(f.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        yield

def measure_loudness(path):
    proc=subprocess.run(["ffmpeg","-hide_banner","-nostdin","-i",str(path),"-map","0:a:0","-af","loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json","-f","null","-"],capture_output=True,timeout=180)
    if proc.returncode:raise RuntimeError("audio measurement failed")
    t=proc.stderr.decode("utf-8",errors="replace")
    a=t.rfind("{");b=t.rfind("}")
    m=json.loads(t[a:b+1])
    i=float(m["input_i"]);tp=float(m["input_tp"])
    if not math.isfinite(i) or not math.isfinite(tp):raise ValueError("unmeasurable loudness")
    return {"integrated_lufs":i,"true_peak_dbtp":tp,"target_lufs":-16,"target_peak_dbtp":-1.5,"within_tolerance":abs(i+16)<=1.5 and tp<=-1.0}

def render(j,output,approved=False):
    if not approved:raise PermissionError("--approve-write required")
    p=plan(j);root=Path(p["workspace"]);out=Path(output).resolve()
    if out.suffix.lower()!=".mp4" or not out.is_relative_to(root) or out.exists():raise ValueError("new MP4 inside workspace required")
    if not out.parent.is_dir():raise ValueError("output parent missing")
    fps,w,h=p["fps"],p["width"],p["height"];n=p["frames"]
    tool=run(["ffmpeg","-version"]).decode("utf-8",errors="replace").splitlines()[0]
    identity=key({"plan":p,"tool":tool,"engine":digest(__file__)})
    cache=root/".rose-montage-v65"/identity
    if cache.resolve()!=cache or out.is_relative_to(root/".rose-montage-v65"):raise ValueError("cache path unsafe")
    cache.mkdir(parents=True,exist_ok=True)
    lock=cache/"render.lock"
    commands=[];hits=[];built=[]
    with job_lock(lock):
        def chunk(name,frames,args):
            dest=cache/(name+".mp4");receipt=cache/(name+".json")
            signature=key({"name":name,"frames":frames,"args":[str(x) for x in args],"identity":identity})
            if dest.is_symlink() or receipt.is_symlink():raise ValueError("cache symlink")
            if dest.is_file() and receipt.is_file():
                try:
                    prev=json.loads(receipt.read_text(encoding="utf-8"))
                    if prev["signature"]==signature and digest(dest)==prev["sha256"]:
                        video_check(dest,frames,fps,w,h);hits.append(name);return dest
                except (ValueError,OSError,KeyError,RuntimeError,subprocess.SubprocessError):pass
            tmp=cache/(name+".partial.mp4")
            if tmp.is_symlink():raise ValueError("cache temp symlink")
            cmd=[*args,*encode_args(fps,frames),"-y",tmp]
            ff(cmd);commands.append([str(x) for x in cmd])
            info=video_check(tmp,frames,fps,w,h);os.replace(tmp,dest)
            receipt.write_text(json.dumps({"signature":signature,**info}),encoding="utf-8")
            built.append(name);return dest
        normalized=[]
        for i,s in enumerate(p["shots"]):
            f=Path(s["file"]);frames=s["frames"]
            info=probe(f);v=next((v for v in info["streams"] if v["codec_type"]=="video"),None)
            if v is None:raise ValueError("missing video")
            if v.get("color_transfer") in ("smpte2084","arib-std-b67"):raise ValueError("HDR requires explicit color-managed workflow")
            if s["still"]:
                # Render on a double-size canvas to reduce rounded crop jitter.
                u=f"min(1,on/{max(1,frames-1)})";ease=f"({u}*{u}*(3-2*{u}))"
                z=f"1+{s['zoom_end']-1:.8f}*{ease}"
                vf=f"scale={w*2}:{h*2}:force_original_aspect_ratio=increase,crop={w*2}:{h*2},zoompan=z='{z}':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d={frames}:s={w}x{h}:fps={fps},setsar=1,format=yuv420p"
            else:
                vf=f"fps={fps}:start_time=0,trim=start_frame={s['start']}:end_frame={s['start']+frames},setpts=PTS-STARTPTS,scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},setsar=1,format=yuv420p"
            normalized.append(chunk(f"shot-{i:03}",frames,["-protocol_whitelist","file,pipe","-i",f,"-map","0:v:0","-vf",vf]))
        segments=[];counts=[]
        for i,s in enumerate(p["shots"]):
            left=s["overlap"];right=p["shots"][i+1]["overlap"] if i+1<len(p["shots"]) else 0
            if left:
                prev=p["shots"][i-1]["frames"]
                t=f"clip((N-1)/{max(1,left-1)},0,1)" if left>1 else "1"
                if s["transition"]=="smooth-fade":t=f"({t}*{t}*(3-2*{t}))"
                graph=f"[0:v]trim=start_frame={prev-left}:end_frame={prev},setpts=PTS-STARTPTS[a];[1:v]trim=end_frame={left},setpts=PTS-STARTPTS[b];[a][b]blend=all_expr='A*(1-{t})+B*{t}':shortest=1[v]"
                segments.append(chunk(f"blend-{i:03}",left,["-i",normalized[i-1],"-i",normalized[i],"-filter_complex",graph,"-map","[v]"]));counts.append(left)
            body=s["frames"]-left-right
            if body:
                if left==right==0:seg=normalized[i]
                else:seg=chunk(f"body-{i:03}",body,["-i",normalized[i],"-vf",f"trim=start_frame={left}:end_frame={s['frames']-right},setpts=PTS-STARTPTS"])
                segments.append(seg);counts.append(body)
        if sum(counts)!=n:raise RuntimeError("internal timeline mismatch")
        # Names are generated by this module; relative concat list avoids user path syntax.
        listing=cache/"segments.txt"
        if listing.is_symlink():raise ValueError("cache list symlink")
        listing.write_text("".join("file '"+seg.name+"'\n" for seg in segments),encoding="utf-8")
        fd,stage=tempfile.mkstemp(prefix="final-",suffix=".partial.mp4",dir=cache);os.close(fd);tmp=Path(stage)
        # Each independently encoded H264 chunk must have its own decoder.
        # The concat demuxer can lose reordered frames across MP4 boundaries.
        cmd=[]
        for seg in segments:cmd+=["-i",seg]
        chain=";".join(f"[{i}:v]settb=1/{fps},setpts=N[v{i}]" for i in range(len(segments)))
        chain+=";"+"".join(f"[v{i}]" for i in range(len(segments)))+f"concat=n={len(segments)}:v=1:a=0,settb=1/{fps},setpts=N[assembled]"
        if p["audio"]:
            a=p["audio"];info=probe(Path(a["file"]));streams=[x for x in info["streams"] if x["codec_type"]=="audio"]
            if not streams:raise ValueError("audio stream missing")
            duration=float(streams[0].get("duration",info["format"].get("duration",0)))
            if not math.isfinite(duration) or duration+0.001<n/fps:raise ValueError("audio shorter than timeline; no silent padding")
            cmd+=["-protocol_whitelist","file,pipe","-i",a["file"],"-filter_complex",chain,"-map","[assembled]","-map",f"{len(segments)}:a:0"]
            filt=f"atrim=duration={n/fps:.9f},asetpts=PTS-STARTPTS"
            if a["normalize"]:filt+=",loudnorm=I=-16:TP=-1.5:LRA=11"
            cmd+=["-af",filt,"-c:a","aac","-b:a","192k","-ar","48000","-ac","2"]
        else:cmd+=["-filter_complex",chain,"-map","[assembled]","-an"]
        cmd+=["-c:v","libx264","-preset","veryfast","-crf","18","-threads","2","-pix_fmt","yuv420p","-r",fps,"-video_track_timescale","90000","-movflags","+faststart","-y",tmp]
        ff(cmd,300);commands.append([str(x) for x in cmd])
        result=video_check(tmp,n,fps,w,h,p["audio"] is not None,True)
        first=ff(["-i",tmp,"-map","0:v:0","-frames:v","1","-vf","scale=64:64","-pix_fmt","rgb24","-f","rawvideo","pipe:1"])
        if len(first)!=64*64*3 or sum(first)/len(first)<=8:raise ValueError("near-black first frame; manual review required")
        if any(digest(Path(s["file"]))!=s["sha256"] for s in p["shots"]) or (p["audio"] and digest(Path(p["audio"]["file"]))!=p["audio"]["sha256"]):raise ValueError("source changed")
        loudness=measure_loudness(tmp) if p["audio"] and p["audio"]["normalize"] else None
        if loudness and not loudness["within_tolerance"]:raise ValueError("measured final audio outside declared tolerance")
        # Same-filesystem hard link publishes only a fully validated file, exclusively.
        # Unique staging name is never reused, even if the process was interrupted.
        os.link(tmp,out);tmp.unlink()
        if digest(out)!=result["sha256"]:raise RuntimeError("output digest mismatch")
        result.update({"output":str(out),"fps":fps,"width":w,"height":h,"seconds":n/fps,"cache_hits":hits,"chunks_built":built,"tool":tool,"commands":commands,"technical_pass":True,"first_frame_nonblack":True,"artistic_verified":False,"audio_loudness_verified":bool(loudness and loudness["within_tolerance"]),"loudness":loudness,"source_style_verified":False})
        receipt=cache/"last-render.json"
        if receipt.is_symlink():raise ValueError("receipt symlink")
        receipt.write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding="utf-8")
        return result

def handle(a):
    try:
        spec=Path(a.spec)
        if spec.stat().st_size>256*1024:raise ValueError("spec too large")
        j=json.loads(spec.read_text(encoding="utf-8"))
        r=plan(j) if a.action=="plan" else render(j,a.output,a.approve_write)
        print(json.dumps(r,ensure_ascii=False,allow_nan=False));return 0
    except (ValueError,OSError,KeyError,TypeError,RuntimeError,subprocess.SubprocessError) as e:
        print(json.dumps({"error":str(e)[:1500]},ensure_ascii=False));return 1
def register(sub):
    p=sub.add_parser("montage-code",help="resumable frame-exact local general montage")
    p.add_argument("action",choices=["plan","render"]);p.add_argument("spec");p.add_argument("--output");p.add_argument("--approve-write",action="store_true");p.set_defaults(ext_func=handle)
