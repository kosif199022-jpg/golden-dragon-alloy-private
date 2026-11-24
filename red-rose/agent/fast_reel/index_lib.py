#!/usr/bin/env python3
"""One-time library index for pick.py (run in the sandbox after fetching the pins and dxh_pins libraries):
per clip -> theme, duration, size, luma, warmth (R-B) and the luma of the dua-line band (y 860-1110).
usage: python3 index_lib.py > /dev/null   (writes ~/fast/library.json; 757 clips took ~1 min on XL)"""
import json, glob, os, subprocess
from concurrent.futures import ThreadPoolExecutor
PINS = {(43,83):'quran',(168,209):'bakhoor',(244,282):'candles',(283,318):'islamic',(520,562):'quran_roses',(400,440):'tasbih',
        (0,42):'roses',(84,124):'decor',(125,167):'tea_roses',(210,243):'orchid',(319,359):'white_roses',(360,399):'coffee_flowers',
        (441,481):'red_roses',(482,519):'living_room',(563,601):'coffee_dates'}
def theme(f):
    b = os.path.basename(f)
    if '/pins_v/' in f:
        i = int(b[:3]); return next((t for (a, z), t in PINS.items() if a <= i <= z), 'other')
    return f.split('/')[-2]
def one(f):
    try:
        pr = json.loads(subprocess.run(['ffprobe','-v','error','-show_entries','format=duration:stream=width,height','-of','json',f],capture_output=True,text=True).stdout)
        d = float(pr['format']['duration']); v = [s for s in pr['streams'] if 'width' in s][0]
        r = subprocess.run(['ffmpeg','-nostdin','-v','error','-ss',str(d*.35),'-i',f,'-frames:v','1','-vf','scale=27:48','-f','rawvideo','-pix_fmt','rgb24','-'],capture_output=True).stdout
        px = [r[i:i+3] for i in range(0, len(r), 3)]
        R = sum(p[0] for p in px)/len(px); G = sum(p[1] for p in px)/len(px); B = sum(p[2] for p in px)/len(px)
        band = [px[y*27+x] for y in range(21, 28) for x in range(27)]
        bl = sum(.299*p[0]+.587*p[1]+.114*p[2] for p in band)/len(band)
        return dict(f=f, theme=theme(f), dur=round(d,1), w=v['width'], h=v['height'], luma=round(.299*R+.587*G+.114*B,1), warm=round(R-B,1), band=round(bl,1))
    except Exception:
        return None
files = sorted(glob.glob('/home/user/pins_v/*.mp4')) + sorted(glob.glob('/home/user/dxhpins/p*/*/*.mp4'))
with ThreadPoolExecutor(8) as ex: out = [x for x in ex.map(one, files) if x]
os.makedirs('/home/user/fast', exist_ok=True); json.dump(out, open('/home/user/fast/library.json','w')); print(len(out))
