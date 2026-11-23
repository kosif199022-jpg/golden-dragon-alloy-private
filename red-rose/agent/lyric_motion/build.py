#!/usr/bin/env python3
"""Lyric motion reel, step 1: song.json -> web/lines.js, web/clips.json and one 9:16 frame sequence per line.

usage: python3 build.py song.json        (run where ffmpeg can reach the clip links, e.g. the Higgsfield sandbox)

song.json:
  {"audio": "song.wav", "dur": 44.9, "title": "اسم المطرب", "subtitle": "ARTIST", "handle": "@elkosif",
   "lines": [["أول سطر", 0.0, 2.48], ["تاني سطر", 2.48, 5.24], ...],      # sung line, start, end (s)
   "clips": [{"video": "https://v1.pinimg.com/...m3u8 or a local mp4", "pin": "link"}, ...],  # one per line
   "bursts": [[5.24, 7.58]], "chorus": [31.76, 36.22], "big_lines": [12, 13]}
Line times: Whisper garbles singing; read the burnt-in captions of the reference frame by frame and use
Whisper only for the times. Word times are spread over the first 72 % of each line (max 3.2 s).
"""
import json, os, subprocess, sys
FPS, PAD = 30, 0.3
S = json.load(open(sys.argv[1], encoding='utf-8'))
L, C, DUR = S['lines'], S['clips'], float(S['dur'])
assert len(C) == len(L), f'one clip per line: {len(C)} clips for {len(L)} lines'
words = []
for text, a, b in L:
    ws = text.split(); span = min(b - a, 3.2) * .72
    words.append([[w, round(a + k * span / len(ws), 2)] for k, w in enumerate(ws)])
os.makedirs('web', exist_ok=True)
open('web/lines.js', 'w', encoding='utf-8').write('const LINES=' + json.dumps(words, ensure_ascii=False) + ';\nconst LEND=' + json.dumps([x[2] for x in L]) + ';\n')
CUTS = [0] + [round(l[1] - .12, 2) for l in L[1:]]
ZOOM = [(1.02, 1.14), (1.10, 1.02), (1.03, 1.13), (1.02, 1.12), (1.12, 1.02), (1.02, 1.15), (1.03, 1.16), (1.12, 1.03)]
TINT = ['#ffb070', '#ffa080', '#ffb060', '#ffc090', '#ff9060', '#ffb070', '#ff9a8a', '#ffc080']
os.makedirs('src', exist_ok=True); clips = []
for i, c in enumerate(C):
    mp4 = c['video'] if os.path.exists(c['video']) else f'src/{i:02d}.mp4'
    if not os.path.exists(mp4):
        subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-i', c['video'], '-c', 'copy', mp4], timeout=180)
    d = float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', mp4], capture_output=True, text=True).stdout.strip() or 0)
    end = CUTS[i + 1] if i + 1 < len(CUTS) else DUR
    length = end - CUTS[i] + 2 * PAD + .2
    ss = c.get('start', max(0, min(d * .25, d - length)) if d > length else 0)
    out = f'web/fx/c{i:02d}'; os.makedirs(out, exist_ok=True)
    for f in os.listdir(out): os.remove(f'{out}/{f}')
    loop = ['-stream_loop', '-1'] if d < length else []
    subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', *loop, '-ss', f'{ss:.2f}', '-i', mp4, '-t', f'{length:.3f}',
                    '-vf', f'fps={FPS},scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280,eq=saturation=1.06:contrast=1.04',
                    '-q:v', '4', f'{out}/%04d.jpg'], check=True)
    z0, z1 = ZOOM[i % len(ZOOM)]
    clips.append(dict(pin=c.get('pin', ''), frames=len(os.listdir(out)), z0=z0, z1=z1, px=0, py=0, tint=c.get('tint', TINT[i % len(TINT)])))
    print(i, f'{d:.1f}s', clips[-1]['frames'], 'frames', flush=True)
cfg = dict(pad=PAD, dur=DUR, clips=clips, **{k: S[k] for k in ('title', 'subtitle', 'handle', 'bursts', 'chorus', 'big_lines') if k in S})
json.dump(cfg, open('web/clips.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('ok', len(clips), 'clips; next: node render.mjs web frames 0-%d 4' % (round(DUR * FPS) - 1))
