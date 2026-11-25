"""V58: apply measured V57 camera/overlay tracks to independent footage."""
from pathlib import Path
import json,math,hashlib,subprocess,os
try:
    import numpy as np
    import cv2
except ImportError:
    np=cv2=None

def digest(p):
    with Path(p).open("rb") as f:return hashlib.file_digest(f,"sha256").hexdigest()

def read_json(p,limit=24*1024*1024):
    p=Path(p)
    if p.stat().st_size>limit:raise ValueError("JSON too large")
    return json.loads(p.read_text(encoding="utf-8"))

def plan(track,scenes):
    """CFR only. Rebase within each chosen scene and measured tracking segment."""
    if np is None:raise RuntimeError("OpenCV and numpy required")
    if track["schema"]!=1 or track["sample_step"]!=1:raise ValueError("full-frame V57 track required")
    fps=track["source_fps"];rows=track["records"];n=len(rows)
    if not 1<=fps<=60 or not 1<=n<=18000 or n!=track["source_frames"] or n!=track["decoded_frames"]:raise ValueError("invalid frame count")
    if any(r["frame"]!=i or abs(r["t"]-i/fps)>1e-5 for i,r in enumerate(rows)):raise ValueError("CFR timeline required")
    if not 1<=len(scenes)<=100:raise ValueError("invalid scenes")
    w,h=track["proxy_geometry"];c=np.array([w/2,h/2]);out=[];last=0;losses=0;clamps=0
    for si,sc in enumerate(scenes):
        a=round(sc["a"]*fps);b=round(sc["b"]*fps)
        if a!=last or not a<b<=n:raise ValueError("scenes must cover contiguous frames")
        last=b;anchor=None;seg=None;seq=rows[a:b]
        ref=rows[min(b-1,max(a,round(sc["reference_frame"]*fps)))]["overlays"]["caption"]
        if not ref["visible"] or not ref["bbox"]:raise ValueError("reference caption missing")
        bx=ref["bbox"];refw=bx[2]-bx[0];refh=bx[3]-bx[1];area=max(1,ref["ink_pixels_proxy"])
        titlebase=max(1,float(np.percentile([r["overlays"]["title"]["ink_pixels_proxy"] for r in seq],90)))
        typical=max(1,float(np.percentile([r["luma"] for r in seq],80)))
        f=[];need=1.0
        for row in seq:
            tr=row["transform"]
            if tr is None:
                anchor=None;seg=None;losses+=1;dx=dy=rot=0.;scale=1.;state="unmeasured_identity"
            else:
                m=np.vstack([np.asarray(tr["matrix"],float),[0,0,1]])
                if not np.isfinite(m).all() or abs(np.linalg.det(m[:2,:2]))<.01:raise ValueError("invalid transform")
                if anchor is None or seg!=row["segment"]:anchor=m;seg=row["segment"]
                rel=m@np.linalg.inv(anchor);v=rel[:2,:2]@c+rel[:2,2]-c
                dx=float(v[0]/w);dy=float(v[1]/h);scale=math.hypot(rel[0,0],rel[1,0]);rot=math.degrees(math.atan2(rel[1,0],rel[0,0]));state="measured_rebased"
                if not (.55<=scale<=2.5 and abs(dx)<=.4 and abs(dy)<=.4 and abs(rot)<=35):
                    dx=max(-.4,min(.4,dx));dy=max(-.4,min(.4,dy));scale=max(.55,min(2.5,scale));rot=max(-35,min(35,rot));clamps+=1;state="bounded"
            # A constant overscan per scene prevents blank edges without per-frame zoom correction.
            angle=abs(math.radians(rot));co=abs(math.cos(angle));ss=abs(math.sin(angle))
            need=max(need,((1+2*abs(dx))*co+(h/w)*(1+2*abs(dy))*ss)/scale,((1+2*abs(dy))*co+(w/h)*(1+2*abs(dx))*ss)/scale)
            o=row["overlays"]["caption"];box=o["bbox"]
            if not o["visible"] or not box:alpha=0.;sx=sy=1.;tx=ty=0.
            else:
                sx=max(.45,min(1.65,(box[2]-box[0])/refw));sy=max(.45,min(1.65,(box[3]-box[1])/refh))
                # Ink occupancy is a visibility proxy, not recovered alpha.
                alpha=max(0.,min(1.,o["ink_pixels_proxy"]/(area*max(.1,sx*sy))))
                tx=(box[0]+box[2]-bx[0]-bx[2])/2;ty=(box[1]+box[3]-bx[1]-bx[3])/2
            title=min(1.,row["overlays"]["title"]["ink_pixels_proxy"]/titlebase)
            # Reference brightness trough, not a certified fade curve.
            gain=min(1.,max(.04,row["luma"]/(typical*.72)))
            f.append({"frame":row["frame"],"camera":[dx,dy,scale,rot],"camera_state":state,"caption":[sx,sy,tx,ty,alpha],"header_alpha_proxy":title,"background_gain_proxy":gain})
        if need>3.2:raise ValueError("overscan required exceeds 3.2x")
        out.append({"a":a,"b":b,"overscan":round(need*1.015,6),"caption_reference_box":bx,"frames":f})
    if last!=n:raise ValueError("incomplete timeline")
    return {"fps":fps,"frames":n,"geometry":track["geometry"],"source_sha256":track["source_sha256"],"scenes":out,"loss_frames":losses,"bounded_frames":clamps,"style_verified":False,"limitations":["camera motion is relative to the chosen scene and segment, and added to new footage's existing motion","caption box and visibility are proxies, not exact opacity or speech alignment","luma troughs are not validated transition classification","header opacity approximated from title ink"]}

def overlay_image(path,w,h):
    im=cv2.imread(str(path),cv2.IMREAD_UNCHANGED)
    if im is None or im.shape!=(h,w,4):raise ValueError("overlay must be full-canvas BGRA PNG")
    y,x=np.where(im[:,:,3]>0)
    if not len(x):raise ValueError("empty overlay")
    x0,x1=int(x.min()),int(x.max()+1);y0,y1=int(y.min()),int(y.max()+1)
    return im[y0:y1,x0:x1].copy(),x0,y0

def blend(dst,layer,sx=1.,sy=1.,dx=0.,dy=0.,alpha=1.,anchor=None):
    if alpha<=.005:return
    im,x,y=layer;h,w=dst.shape[:2];hh,ww=im.shape[:2]
    cx,cy=anchor if anchor is not None else (x+ww/2,y+hh/2)
    X=round(cx+(x-cx)*sx+dx*w);Y=round(cy+(y-cy)*sy+dy*h)
    nw=max(1,round(ww*sx));nh=max(1,round(hh*sy))
    if nw!=ww or nh!=hh:im=cv2.resize(im,(nw,nh),interpolation=cv2.INTER_LINEAR)
    x0=max(0,X);y0=max(0,Y);x1=min(w,X+nw);y1=min(h,Y+nh)
    if x1<=x0 or y1<=y0:return
    src=im[y0-Y:y1-Y,x0-X:x1-X];a=src[:,:,3:4].astype(np.float32)*(alpha/255)
    dst[y0:y1,x0:x1]=(dst[y0:y1,x0:x1]*(1-a)+src[:,:,:3]*a).astype(np.uint8)

def render(track_path,job_path,out,approved=False):
    if not approved:raise PermissionError("explicit write approval required")
    out=Path(out);job=read_json(job_path);track=read_json(track_path)
    if out.exists() or out.suffix.lower()!=".mp4":raise ValueError("new MP4 path required")
    p=plan(track,job["scenes"]);W,H=p["geometry"];fps=p["fps"]
    if not (64<=W<=1920 and 64<=H<=1920 and W%2==H%2==0):raise ValueError("unsupported render geometry")
    # Paths are explicit local job inputs; no commands from the JSON.
    header=overlay_image(job["header"],W,H)
    layers=[overlay_image(s["caption_png"],W,H) for s in job["scenes"]]
    audio=Path(job["audio"]).resolve(strict=True)
    tmp=out.with_name(out.stem+".rendering.mp4")
    if tmp.exists():raise ValueError("temporary output exists")
    ff=["ffmpeg","-hide_banner","-nostdin","-v","error"]
    encoder=subprocess.Popen(ff+["-f","rawvideo","-pix_fmt","bgr24","-s",f"{W}x{H}","-r",str(fps),"-i","pipe:0","-i",str(audio),"-map","0:v:0","-map","1:a:0","-c:v","libx264","-preset","veryfast","-crf","20","-threads","4","-pix_fmt","yuv420p","-c:a","aac","-b:a","192k","-t",str(p["frames"]/fps),"-movflags","+faststart","-n",str(tmp)],stdin=subprocess.PIPE)
    done=0;bw=720 if W>=720 else W;bh=round(H*bw/W/2)*2;size=bw*bh*3;cv2.setNumThreads(2)
    try:
        for j,(sc,measured,layer) in enumerate(zip(job["scenes"],p["scenes"],layers)):
            src=Path(sc["clip"]).resolve(strict=True)
            duration=float(sc["clip_duration"]);start=max(0,min(duration*.2,duration-(measured["b"]-measured["a"])/fps-.1))
            dec=subprocess.Popen(ff+["-threads","2","-stream_loop","-1","-ss",str(start),"-i",str(src),"-an","-vf",f"fps={fps},scale={bw}:{bh}:force_original_aspect_ratio=increase,crop={bw}:{bh},setsar=1","-frames:v",str(measured["b"]-measured["a"]),"-pix_fmt","bgr24","-f","rawvideo","pipe:1"],stdout=subprocess.PIPE)
            try:
                for row in measured["frames"]:
                    raw=dec.stdout.read(size)
                    if len(raw)!=size:raise RuntimeError("background decode truncated")
                    img=np.frombuffer(raw,np.uint8).reshape(bh,bw,3)
                    dx,dy,z,rot=row["camera"]
                    mat=cv2.getRotationMatrix2D((bw/2,bh/2),-rot,z*measured["overscan"])
                    mat[:,2]+=(dx*bw,dy*bh)
                    img=cv2.warpAffine(img,mat,(bw,bh),flags=cv2.INTER_LINEAR,borderMode=cv2.BORDER_REFLECT_101)
                    gain=.86*row["background_gain_proxy"];img=cv2.convertScaleAbs(img,alpha=gain)
                    dst=cv2.resize(img,(W,H),interpolation=cv2.INTER_LINEAR)
                    blend(dst,header,alpha=row["header_alpha_proxy"])
                    bx=measured["caption_reference_box"];anchor=((bx[0]+bx[2])*W/2,(bx[1]+bx[3])*H/2)
                    blend(dst,layer,*row["caption"],anchor=anchor)
                    encoder.stdin.write(dst.tobytes());done+=1
                if dec.wait(timeout=30):raise RuntimeError("decoder failed")
            finally:
                if dec.poll() is None:dec.kill();dec.wait()
                dec.stdout.close()
            print(f"scene {j+1}/{len(layers)} frames {done}/{p['frames']}",flush=True)
        encoder.stdin.close()
        if encoder.wait(timeout=120):raise RuntimeError("encoder failed")
        if done!=p["frames"]:raise RuntimeError("frame count mismatch")
        from verify_media import verify_video
        qa=verify_video(tmp,expected_fps=fps,width=W,height=H,expected_frames=p["frames"],expected_audio=True)
        if not qa["passed"]:raise RuntimeError("technical QA failed")
        if out.exists():raise ValueError('destination appeared during render')
        os.rename(tmp,out)
        return {"technical_qa":qa,"track_sha256":digest(track_path),"frames_applied":done,"loss_frames":p["loss_frames"],"bounded_frames":p["bounded_frames"],"style_verified":False,"limitations":p["limitations"]}
    finally:
        if encoder.poll() is None:
            encoder.kill();encoder.wait()
        if not encoder.stdin.closed:encoder.stdin.close()
        tmp.unlink(missing_ok=True)

def handle(a):
    try:
        if a.action=="plan":
            job=read_json(a.job);p=plan(read_json(a.track),job["scenes"])
            print(json.dumps({k:v for k,v in p.items() if k!="scenes"}));return 0
        if not a.approve_write or not a.output:print(json.dumps({"ok":False,"approval_required":True}));return 3
        result=render(a.track,a.job,a.output,True);print(json.dumps(result));return 0
    except (OSError,ValueError,RuntimeError,KeyError,TypeError,PermissionError) as e:print(json.dumps({"ok":False,"error":str(e)}));return 1
def register(sub):
    p=sub.add_parser("motion-replay",help="reapply measured motion to local footage")
    p.add_argument("action",choices=["plan","render"]);p.add_argument("track");p.add_argument("job");p.add_argument("--output");p.add_argument("--approve-write",action="store_true");p.set_defaults(ext_func=handle)
