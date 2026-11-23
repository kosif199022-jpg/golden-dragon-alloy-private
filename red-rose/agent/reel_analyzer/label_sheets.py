#!/usr/bin/env python3
"""Numbered review sheets: label<TAB>image(path or URL) -> OUT/r000.jpg ... (10 x 6 cells of 150 x 200, label in the corner)."""
import sys, os, subprocess
from concurrent.futures import ThreadPoolExecutor
from PIL import Image, ImageDraw, ImageFont
src, out = sys.argv[1], sys.argv[2]
os.makedirs(out + '/img', exist_ok=True)
rows = [l.rstrip('\n').split('\t', 1) for l in open(src) if '\t' in l]
def local(r):
    lab, s = r
    if not s.startswith('http'): return lab, s
    p = f'{out}/img/{lab}.jpg'
    if not os.path.exists(p):
        subprocess.run(['curl', '-sfL', '-m', '30', '-A', 'Mozilla/5.0', '-o', p, s])
    return lab, p
with ThreadPoolExecutor(12) as ex: rows = list(ex.map(local, rows))
CW, CH, C, R = 150, 200, 10, 6
try: font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 18)
except Exception: font = ImageFont.load_default()
for s in range(0, len(rows), C * R):
    sheet = Image.new('RGB', (CW * C, CH * R), (30, 30, 30)); d = ImageDraw.Draw(sheet)
    for k, (lab, p) in enumerate(rows[s:s + C * R]):
        x, y = (k % C) * CW, (k // C) * CH
        try:
            im = Image.open(p).convert('RGB'); w, h = im.size; tr = CW / CH
            if w / h > tr: nw = int(h * tr); im = im.crop(((w - nw) // 2, 0, (w - nw) // 2 + nw, h))
            else: nh = int(w / tr); im = im.crop((0, (h - nh) // 2, w, (h - nh) // 2 + nh))
            sheet.paste(im.resize((CW, CH)), (x, y))
        except Exception: pass
        d.rectangle([x, y, x + 52, y + 22], fill=(0, 0, 0)); d.text((x + 3, y + 1), lab, fill=(255, 230, 0), font=font)
    sheet.save(f'{out}/r{s // (C * R):03d}.jpg', quality=68)
print('sheets', (len(rows) + C * R - 1) // (C * R))
