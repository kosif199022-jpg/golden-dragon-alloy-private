"""Measurable, bounded accent-color QA using sampled actual video frames.

Values are approximate sample-based ΔE76 (not CIEDE2000); no aesthetic judgment.
Frames are decoded from the user-provided MP4, never written back to it.
"""
from __future__ import annotations
import colorsys
import io
import math
import shutil
import subprocess
from PIL import Image


def _rgb(hex_color):
    text=hex_color.lstrip('#');return tuple(int(text[i:i+2],16) for i in (0,2,4))


def _lab(rgb):
    def inverse(v):
        v=v/255.0
        return v/12.92 if v<=0.04045 else ((v+0.055)/1.055)**2.4
    r,g,b=map(inverse,rgb)
    x=(.4124564*r+.3575761*g+.1804375*b)/.95047
    y=(.2126729*r+.7151522*g+.0721750*b)
    z=(.0193339*r+.1191920*g+.9503041*b)/1.08883
    def f(t):return t**(1/3) if t>(6/29)**3 else t/(3*(6/29)**2)+4/29
    fx,fy,fz=map(f,(x,y,z))
    return 116*fy-16,500*(fx-fy),200*(fy-fz)


def _delta(a,b):return math.sqrt(sum((x-y)**2 for x,y in zip(a,b)))


def _hue(rgb):
    h,s,_=colorsys.rgb_to_hsv(*(x/255 for x in rgb))
    return h*360,s


def analyze(path,*,duration_s,palette,frame_count=7):
    if not isinstance(palette,list) or len(palette)!=3:raise ValueError('three planned colors required')
    if frame_count<1 or frame_count>30:raise ValueError('frame_count must be 1..30')
    ffmpeg=shutil.which('ffmpeg')
    if not ffmpeg:raise RuntimeError('ffmpeg unavailable for pixel QA')
    base,target=_lab(_rgb(palette[0])),_lab(_rgb(palette[2]))
    center_hue,center_sat=_hue(_rgb(palette[2]))
    if center_sat<0.14:
        # For achromatic accent, hue is undefined and LAB distance alone is used.
        center_hue=None
    samples=[]
    for i in range(frame_count):
        t=max(0.0,float(duration_s)*(i+.5)/frame_count)
        args=[ffmpeg,'-hide_banner','-loglevel','error','-nostdin','-ss',f'{t:.4f}','-i',str(path),
              '-frames:v','1','-vf','scale=240:-2','-f','image2pipe','-vcodec','png','-']
        res=subprocess.run(args,capture_output=True,timeout=25)
        if res.returncode or not res.stdout:
            samples.append({'at_s':round(t,3),'status':'undecodable'});continue
        with Image.open(io.BytesIO(res.stdout)) as img:
            im=img.convert('RGB').quantize(colors=64,method=Image.Quantize.MEDIANCUT)
            palette_values=im.getpalette();colors=im.getcolors(maxcolors=2**24) or []
            total=sum(n for n,_ in colors)
            matching=0
            for n,palette_index in colors:
                c=palette_values[palette_index*3:palette_index*3+3]
                if len(c)<3:continue
                # CIELAB76, sample-based tolerance; a matched color needs similar lightness and hue.
                delta=_delta(_lab(c),target)
                hue,sat=_hue(c)
                close_hue=(center_hue is None or (min(abs(hue-center_hue),360-abs(hue-center_hue))<=20 and sat>=0.20))
                if delta<=28 and close_hue:matching+=n
            samples.append({'at_s':round(t,3),'status':'sampled','accent_fraction':round(matching/max(1,total),5)})
    valid=[x for x in samples if x['status']=='sampled']
    ratio=sum(x['accent_fraction'] for x in valid)/len(valid) if valid else None
    return {'kind':'v10/pixel-color-audit','method':'7 evenly spaced frames, 240px width, 64-color quantization, CIELAB76 ΔE',
            'planned_palette':palette,'planned_base_vs_accent_delta_e76':round(_delta(base,target),2),
            'observed_accent_fraction':round(ratio,5) if ratio is not None else None,
            'accent_fraction_target_range':[0.005,0.18],
            'sampled_frames':len(valid),'requested_frames':frame_count,
            'sample_reports':samples,'passes_approximate_accent_range':ratio is not None and 0.005<=ratio<=0.18,
            'planned_contrast_gte_40':_delta(base,target)>=40,
            'caveat':'Not a full-frame scan or a creative/brand assessment. No proof that the accent is on the intended hero.'}
