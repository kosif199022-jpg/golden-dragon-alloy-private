#!/usr/bin/env python3
"""«ستايل دعاء الترند»: cut one clip per dua line (sel.txt, absolute paths) into frames; write web/clips.json.
usage: python3 build.py WORKDIR   (WORKDIR has spec.json and sel.txt; one clip per line)"""
import json, subprocess, os, sys
W = sys.argv[1]; os.chdir(W)
FPS, PAD = 30, 0.3
S = json.load(open('spec.json')); DUR = S['dur']
STARTS = [l[0][1] for l in S['lines']]
CUTS = [0] + [round(s - .12, 2) for s in STARTS[1:]]
SEL = [l.strip() for l in open('sel.txt') if l.strip()]
ZOOM = [(1.02, 1.14), (1.10, 1.02), (1.03, 1.13), (1.02, 1.12), (1.12, 1.02), (1.02, 1.15), (1.03, 1.14), (1.12, 1.03), (1.02, 1.13), (1.10, 1.02), (1.03, 1.14), (1.02, 1.12), (1.04, 1.16)]
TINT = ['#ffc27a', '#ffb060', '#ffb6a0', '#ffcf9a', '#ffc488', '#ffa050', '#ff9fb0', '#ffd090', '#ffb6a0', '#ffd27a', '#ffa9a0', '#ffc27a', '#ffa050']
clips = []
for i in range(len(CUTS)):
    src = SEL[i % len(SEL)]
    d = float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', src], capture_output=True, text=True).stdout)
    end = CUTS[i + 1] if i + 1 < len(CUTS) else DUR
    length = end - CUTS[i] + 2 * PAD + .2
    ss = max(0, min(d * .3, d - length)) if d > length else 0
    out = f'web/fx/c{i:02d}'; os.makedirs(out, exist_ok=True)
    for x in os.listdir(out): os.remove(f'{out}/{x}')
    loop = ['-stream_loop', '-1'] if d < length else []
    subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', *loop, '-ss', f'{ss:.2f}', '-i', src, '-t', f'{length:.3f}', '-vf',
                    f'fps={FPS},scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280,eq=saturation=1.08:contrast=1.03', '-q:v', '4', f'{out}/%04d.jpg'], check=True)
    z0, z1 = ZOOM[i % len(ZOOM)]
    clips.append(dict(id=os.path.basename(src), frames=len(os.listdir(out)), z0=z0, z1=z1, px=0, py=0, tint=TINT[i % len(TINT)]))
json.dump(dict(pad=PAD, dur=DUR, clips=clips), open('web/clips.json', 'w'), indent=1)
print('clips', len(clips))
