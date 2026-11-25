"""V57: measured camera and overlay tracks; local, no external model/service."""
from pathlib import Path
import math,json,hashlib,os
try:
    import numpy as np
    import cv2
except ImportError:
    np=cv2=None

def pair(a,b,mask=None):
    """Forward/backward LK + robust similarity; source-to-next pixel coordinates."""
    if mask is not None:
        # Suppress overlay motion in both pyramids, and keep feature centers off artificial mask edges.
        a=a.copy();b=b.copy();a[mask==0]=0;b[mask==0]=0
        mask=cv2.erode(mask,np.ones((25,25),np.uint8))
    p=cv2.goodFeaturesToTrack(a,maxCorners=400,qualityLevel=.012,minDistance=6,mask=mask)
    if p is None or len(p)<12:return None
    q,s,_=cv2.calcOpticalFlowPyrLK(a,b,p,None,winSize=(21,21),maxLevel=3)
    if q is None:return None
    back,s2,_=cv2.calcOpticalFlowPyrLK(b,a,q,None,winSize=(21,21),maxLevel=3)
    if back is None:return None
    ok=(s.ravel()==1)&(s2.ravel()==1)&(np.linalg.norm((back-p).reshape(-1,2),axis=1)<1.5)
    p=p.reshape(-1,2)[ok];q=q.reshape(-1,2)[ok]
    if len(p)<12:return None
    m,inl=cv2.estimateAffinePartial2D(p,q,method=cv2.RANSAC,ransacReprojThreshold=2,maxIters=1000)
    if m is None or inl is None:return None
    z=inl.ravel().astype(bool);n=int(z.sum());ratio=n/len(p)
    if n<12 or ratio<.55:return None
    spread=np.ptp(p[z],axis=0);coverage=float(spread[0]*spread[1]/(a.shape[0]*a.shape[1]))
    if coverage<.035:return None
    err=float(np.median(np.linalg.norm(p[z]@m[:,:2].T+m[:,2]-q[z],axis=1)))
    scale=math.hypot(m[0,0],m[1,0])
    if not .70<=scale<=1.43 or err>2:return None
    return m,{"inliers":n,"ratio":round(ratio,4),"coverage":round(coverage,4),"median_error_proxy_px":round(err,4)}

def overlay(frame,box,kind):
    """Observed bright/yellow ink proxy, not OCR or recovered alpha."""
    h,w=frame.shape[:2];x,y,X,Y=[round(v*s) for v,s in zip(box,(w,h,w,h))]
    c=frame[y:Y,x:X];b,g,r=cv2.split(c);lo=c.min(2);hi=c.max(2)
    m=((lo>175)&(hi.astype(int)-lo<45)) if kind=="white" else ((r>170)&(g>140)&(b<130)&(g.astype(int)-b>50))
    m=m.astype("uint8")
    n,l,stats,_=cv2.connectedComponentsWithStats(m,8)
    for i in range(1,n):
        _,_,ww,hh,area=stats[i]
        if area<3 or ww>=c.shape[1]*.96 or hh>=c.shape[0]*.95:m[l==i]=0
    ys,xs=np.where(m)
    if len(xs)<6:return {"visible":False,"ink_pixels_proxy":int(len(xs)),"bbox":None}
    return {"visible":True,"ink_pixels_proxy":int(len(xs)),"bbox":[round((x+xs.min())/w,6),round((y+ys.min())/h,6),round((x+xs.max()+1)/w,6),round((y+ys.max()+1)/h,6)],
            "median_rgb":[int(v) for v in np.median(c[m>0],axis=0)[::-1]]}

def validate_regions(regions):
    if not isinstance(regions,list) or len(regions)>12:raise ValueError("0..12 regions")
    ids=set()
    for r in regions:
        if set(r)!={"id","box","kind"} or not isinstance(r["id"],str) or not r["id"] or r["id"] in ids or r["kind"] not in ("white","yellow"):raise ValueError("invalid region")
        ids.add(r["id"]);b=r["box"]
        if not isinstance(b,list) or len(b)!=4 or any(type(x) not in (float,int) or not 0<=x<=1 for x in b) or b[2]-b[0]<.02 or b[3]-b[1]<.02:raise ValueError("normalized region required")

def describe_matrix(m,w,h):
    # Center displacement in normalized frame, plus similarity transform.
    c=np.array([w/2,h/2]);p=m[:2,:2]@c+m[:2,2]-c
    return {"matrix":np.round(m[:2,:],7).tolist(),"x":round(float(p[0]/w),7),"y":round(float(p[1]/h),7),"scale":round(float(math.hypot(m[0,0],m[1,0])),7),"rotation_deg":round(math.degrees(math.atan2(m[1,0],m[0,0])),5)}

def analyze(source,regions=(),sample_fps=12,max_seconds=120):
    if cv2 is None or np is None:raise RuntimeError("OpenCV and numpy required; run doctor first")
    regions=list(regions);validate_regions(regions)
    if type(sample_fps) is not int or not 1<=sample_fps<=60 or not 1<=max_seconds<=300:raise ValueError("bounded rate/duration required")
    source=Path(source).resolve(strict=True)
    if not source.is_file() or source.stat().st_size>2*1024**3:raise ValueError("bounded local source required")
    with source.open("rb") as f:digest=hashlib.file_digest(f,"sha256").hexdigest()
    cap=cv2.VideoCapture(str(source))
    try:
        fps=cap.get(cv2.CAP_PROP_FPS);count=int(cap.get(cv2.CAP_PROP_FRAME_COUNT));sw=int(cap.get(cv2.CAP_PROP_FRAME_WIDTH));sh=int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        if not fps or not count or count/fps>max_seconds or sw<64 or sh<64 or max(sw,sh)>8192:raise ValueError("unsupported video geometry/duration")
        step=max(1,round(fps/sample_fps));w=320;h=round(sh*w/sw)
        if h>1024:w=round(w*1024/h);h=1024
        mask=np.full((h,w),255,np.uint8)
        for reg in regions:
            x,y,X,Y=[round(v*s) for v,s in zip(reg["box"],(w,h,w,h))]
            mask[max(0,y-3):min(h,Y+3),max(0,x-3):min(w,X+3)]=0
        if np.count_nonzero(mask)<w*h*.2:raise ValueError("too little background tracking area")
        prev=None;prev_hist=None;prev_luma=None;records=[];events=[];cum=np.eye(3);segment=0;i=0;valid=0
        while True:
            ok=cap.grab()
            if not ok:break
            if i%step:i+=1;continue
            ok,f=cap.retrieve()
            if not ok:raise RuntimeError("sample decode failed")
            f=cv2.resize(f,(w,h),interpolation=cv2.INTER_AREA);g=cv2.cvtColor(f,cv2.COLOR_BGR2GRAY)
            hist=cv2.calcHist([g],[0],mask,[32],[0,256]);cv2.normalize(hist,hist,alpha=1,norm_type=cv2.NORM_L1)
            lum=float(g[mask>0].mean());row={"frame":i,"t":round(i/fps,6),"luma":round(lum,3),"sharpness":round(float(cv2.Laplacian(g,cv2.CV_64F).var()),3),"overlays":{r["id"]:overlay(f,r["box"],r["kind"]) for r in regions}}
            if prev is None:row.update({"state":"anchor","segment":segment,"transform":describe_matrix(cum,w,h)})
            else:
                delta=float(cv2.compareHist(prev_hist,hist,cv2.HISTCMP_BHATTACHARYYA))
                change=float(np.mean(cv2.absdiff(prev,g)[mask>0])/255)
                measured=pair(prev,g,mask);row.update({"hist_delta":round(delta,5),"pixel_delta":round(change,5),"luma_delta":round(lum-prev_luma,4)})
                # Lost tracking is not automatically a scene cut.
                if measured is None or delta>.52 or change>.40:
                    segment+=1;cum=np.eye(3);reason="cut_candidate" if delta>.52 or change>.40 else "tracking_lost"
                    row.update({"state":reason,"segment":segment,"transform":None})
                    events.append({"t":row["t"],"kind":reason,"hist_delta":row["hist_delta"],"pixel_delta":row["pixel_delta"],"verified":False})
                else:
                    m,quality=measured;cum=np.vstack([m,[0,0,1]])@cum;valid+=1
                    row.update({"state":"tracked","segment":segment,"relative":describe_matrix(np.vstack([m,[0,0,1]]),w,h),"transform":describe_matrix(cum,w,h),"quality":quality})
            records.append(row);prev=g;prev_hist=hist;prev_luma=lum;i+=1
        if not records:raise RuntimeError("no frames decoded")
        # Dip candidates: local dark minima bracketed by brighter samples; group adjacent candidates.
        radius=max(2,round(fps/step*.45))
        for j in range(radius,len(records)-radius):
            l=records[j]["luma"];left=records[j-radius:j];right=records[j+1:j+radius+1]
            if l<=min(x["luma"] for x in left+right) and min(max(x["luma"] for x in left),max(x["luma"] for x in right))-l>18:
                events.append({"t":records[j]["t"],"kind":"dip_candidate","verified":False})
        events.sort(key=lambda x:x["t"])
        return {"schema":1,"source_sha256":digest,"geometry":[sw,sh],"proxy_geometry":[w,h],"source_fps":fps,"source_frames":count,"decoded_frames":i,"sample_step":step,"sample_fps":fps/step,"sample_count":len(records),"tracked_pairs":valid,"pair_coverage":round(valid/max(1,len(records)-1),4),"regions":regions,"records":records,"events":events,"limitations":["timestamps use nominal source FPS; variable-frame-rate timing not certified","similarity motion cannot separate parallax, object motion or perspective","overlay ink proxies are not OCR, font identity or true alpha","transition candidates require human verification; no interpolation across lost tracking"],"final_style_verified":False}
    finally:cap.release()

def replay(data,t):
    """Nearest measured keyframe, never interpolate across missing measurements."""
    if not math.isfinite(t) or t<0 or not data["records"] or t>data["records"][-1]["t"]:raise ValueError("outside measured timeline")
    r=min(data["records"],key=lambda r:abs(r["t"]-t))
    return {"ok":r["transform"] is not None,"sample":r,"time_error_s":abs(r["t"]-t),"proxy_geometry":data["proxy_geometry"],"verified":False}

def handle(a):
    try:
        if a.action=="analyze":
            if not a.output or not a.approve_write:return print(json.dumps({"ok":False,"outcome":"approval_required"})) or 3
            p=Path(a.output)
            if p.exists():raise ValueError("output exists")
            regions=json.loads(Path(a.regions).read_text(encoding="utf-8")) if a.regions else []
            d=analyze(a.source,regions,a.fps,a.max_seconds)
            with p.open("x",encoding="utf-8") as f:json.dump(d,f,ensure_ascii=False,allow_nan=False,separators=(",",":"))
            print(json.dumps({"ok":True,"output":str(p),"samples":d["sample_count"],"pair_coverage":d["pair_coverage"],"events":len(d["events"]),"final_style_verified":False}));return 0
        d=json.loads(Path(a.source).read_text(encoding="utf-8"));r=replay(d,a.time);print(json.dumps(r));return 0 if r["ok"] else 1
    except (ValueError,OSError,RuntimeError,KeyError,TypeError) as e:print(json.dumps({"ok":False,"error":str(e)}));return 1
def register(sub):
    p=sub.add_parser("motion-capture",help="measure and preserve local video motion")
    p.add_argument("action",choices=["analyze","replay"]);p.add_argument("source")
    p.add_argument("--output");p.add_argument("--regions");p.add_argument("--fps",type=int,default=12);p.add_argument("--max-seconds",type=int,default=120)
    p.add_argument("--time",type=float,default=0);p.add_argument("--approve-write",action="store_true");p.set_defaults(ext_func=handle)
