"""Read the reference reel's burnt-in lyrics: when each caption appears, plus crops to read the words.

usage: python3 -I captions.py v.mp4 OUTDIR [--band x,y,w,h]
  prints every caption change (time, pixels) and writes OUTDIR/sheet.jpg (1 fps contact sheet)
  and OUTDIR/caps.jpg (the caption band at the middle of each caption) to read the exact words.
Whisper garbles singing, so the words come from these crops; Whisper word times give the onsets inside a line.
"""
import os, subprocess, sys
import numpy as np
from PIL import Image

v, out = sys.argv[1], sys.argv[2]; os.makedirs(out, exist_ok=True)
w0, h0 = map(int, subprocess.check_output(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height', '-of', 'csv=p=0', v]).decode().split(',')[:2])
if '--band' in sys.argv:
    x, y, w, h = map(int, sys.argv[sys.argv.index('--band') + 1].split(','))
else:                                   # default: the usual lyric band, a little below the middle
    x, y, w, h = int(w0 * .18), int(h0 * .52), int(w0 * .64), int(h0 * .1)
x, y, w, h = x // 2 * 2, y // 2 * 2, w // 2 * 2, h // 2 * 2
fps = 10
raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', v, '-vf', f'fps={fps},crop={w}:{h}:{x}:{y},format=gray', '-f', 'rawvideo', '-'], capture_output=True).stdout
f = np.frombuffer(raw, np.uint8).reshape(-1, h, w); m = (f > 235).astype(np.int16)
thr = max(200, int(w * h * .004))
on, events = None, []
for i in range(1, len(m)):
    d = np.abs(m[i] - m[i - 1]).sum(); lit = m[i].sum() > thr
    if d > thr:
        print(f'{i / fps:6.1f}s  change {d:5d}  lit {int(m[i].sum())}')
    if lit and on is None:
        on = i
    if on is not None and (not lit or d > thr * 3) and i - on > 3:
        events.append((on / fps, i / fps)); on = i if lit else None
if on is not None:
    events.append((on / fps, len(m) / fps))
print('captions (start, end):', [(round(a, 1), round(b, 1)) for a, b in events])
crops = []
for a, b in events:
    t = (a + b) / 2
    p = os.path.join(out, f'cap_{t:.1f}.png')
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', str(t), '-i', v, '-frames:v', '1', '-vf', f'crop={w}:{int(h * 1.4)}:{x}:{max(0, y - int(h * .2))}', p])
    if os.path.exists(p):
        crops.append(Image.open(p).convert('RGB'))
if crops:
    sh = Image.new('RGB', (crops[0].width, sum(c.height for c in crops)))
    yy = 0
    for c in crops:
        sh.paste(c, (0, yy)); yy += c.height
    sh.thumbnail((900, 4000)); sh.save(os.path.join(out, 'caps.jpg'), quality=88)
fr = os.path.join(out, 'fr'); os.makedirs(fr, exist_ok=True)
subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', v, '-vf', 'fps=1,scale=240:-1', os.path.join(fr, '%02d.jpg')])
ims = [Image.open(os.path.join(fr, n)) for n in sorted(os.listdir(fr))]
if ims:
    c = 8; r = (len(ims) + c - 1) // c; s = Image.new('RGB', (ims[0].width * c, ims[0].height * r))
    for k, im in enumerate(ims):
        s.paste(im, ((k % c) * im.width, (k // c) * im.height))
    s.save(os.path.join(out, 'sheet.jpg'), quality=85)
print('wrote', os.path.join(out, 'caps.jpg'), os.path.join(out, 'sheet.jpg'))
