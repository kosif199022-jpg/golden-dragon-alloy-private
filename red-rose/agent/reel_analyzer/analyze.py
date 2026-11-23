#!/usr/bin/env python3
"""Run in the Higgsfield sandbox. For each TikTok id in pick.json: download (yt-dlp, impersonate),
measure shots, loudness, palette, transcribe the dua with word times, save one frame per shot.
Resumable: a finished video has OUT/<id>/a.json. usage: python3 analyze.py pick.json OUT [workers]"""
import json, os, sys, subprocess, re
from concurrent.futures import ThreadPoolExecutor
from PIL import Image

pick, out = json.load(open(sys.argv[1])), sys.argv[2]
W = int(sys.argv[3]) if len(sys.argv) > 3 else 2
os.makedirs(out, exist_ok=True)
env = dict(os.environ, HOME='/home/user', PYTHONPATH='/home/user/pylib')
_model = None

def model():
    global _model
    if _model is None:
        from faster_whisper import WhisperModel
        _model = WhisperModel('small', compute_type='int8', cpu_threads=2)
    return _model

def run(cmd, **k):
    return subprocess.run(cmd, capture_output=True, text=True, env=env, **k)

def _gray_at(mp4, t, w=240):
    import numpy as np
    r = subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-ss', f'{max(0, t):.2f}', '-i', mp4, '-frames:v', '1',
                        '-vf', f'scale={w}:-2,format=gray', '-f', 'rawvideo', '-'], capture_output=True)
    if not r.stdout:
        return None
    h = len(r.stdout) // w
    return np.frombuffer(r.stdout[:w * h], np.uint8).reshape(h, w)


def shot_motion(mp4, bounds):
    """Per shot: camera move between two frames 0.6 s apart (ORB + partial affine): zoom, pan, rotate, still."""
    try:
        import cv2, numpy as np
    except Exception:
        return []
    orb = cv2.ORB_create(500); bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True); out = []
    for k in range(len(bounds) - 1):
        a, b = bounds[k], bounds[k + 1]
        if b - a < 0.9:
            out.append({'shot': k, 'move': 'short'}); continue
        t0 = a + (b - a) * 0.3; g0, g1 = _gray_at(mp4, t0), _gray_at(mp4, t0 + 0.6)
        if g0 is None or g1 is None:
            continue
        k0, d0 = orb.detectAndCompute(g0, None); k1, d1 = orb.detectAndCompute(g1, None)
        if d0 is None or d1 is None or len(k0) < 12 or len(k1) < 12:
            out.append({'shot': k, 'move': 'unknown'}); continue
        m = sorted(bf.match(d0, d1), key=lambda x: x.distance)[:120]
        if len(m) < 10:
            out.append({'shot': k, 'move': 'unknown'}); continue
        P0 = np.float32([k0[x.queryIdx].pt for x in m]); P1 = np.float32([k1[x.trainIdx].pt for x in m])
        M, _ = cv2.estimateAffinePartial2D(P0, P1)
        if M is None:
            out.append({'shot': k, 'move': 'unknown'}); continue
        sc = float(np.hypot(M[0, 0], M[1, 0])); ang = float(np.degrees(np.arctan2(M[1, 0], M[0, 0])))
        dx, dy = float(M[0, 2]) / g0.shape[1], float(M[1, 2]) / g0.shape[0]
        move = 'still'
        if abs(sc - 1) > 0.012: move = 'zoom_in' if sc > 1 else 'zoom_out'
        elif abs(ang) > 1.0: move = 'rotate'
        elif max(abs(dx), abs(dy)) > 0.01: move = 'pan_x' if abs(dx) > abs(dy) else 'pan_y'
        out.append({'shot': k, 'move': move, 'scale_per_s': round((sc - 1) / 0.6, 4), 'deg_per_s': round(ang / 0.6, 2),
                    'pan_per_s': [round(dx / 0.6, 4), round(dy / 0.6, 4)]})
    return out


def transition_look(mp4, cuts):
    """Around each cut: brightness jump (flash/dip) and sharpness drop (blur/whip/spin) over +-0.25 s."""
    try:
        import cv2, numpy as np
    except Exception:
        return []
    out = []
    for c in cuts:
        fr = [_gray_at(mp4, c + d) for d in (-0.4, -0.12, 0.0, 0.12, 0.4)]
        if any(f is None for f in fr):
            continue
        lum = [float(f.mean()) for f in fr]; sharp = [float(cv2.Laplacian(f, cv2.CV_64F).var()) for f in fr]
        base_l, base_s = (lum[0] + lum[4]) / 2, max(1.0, (sharp[0] + sharp[4]) / 2)
        kind = 'cut'
        if max(lum[1:4]) - base_l > 35: kind = 'flash'
        elif base_l - min(lum[1:4]) > 35: kind = 'dip'
        elif min(sharp[1:4]) / base_s < 0.35: kind = 'blur_move'
        out.append({'t': round(c, 2), 'kind': kind})
    return out


def analyze(v):
    vid = v['id']; d = f'{out}/{vid}'; os.makedirs(d, exist_ok=True)
    if os.path.exists(f'{d}/a.json'):
        return vid, 'cached'
    mp4 = f'{d}/v.mp4'
    if not os.path.exists(mp4):
        run(['python3', '-m', 'yt_dlp', '--impersonate', 'chrome', '-f', 'b', '-o', mp4, '--no-progress', v['url']], timeout=180)
    if not os.path.exists(mp4):
        return vid, 'download_failed'
    pr = json.loads(run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration:stream=width,height,r_frame_rate,codec_type', '-of', 'json', mp4]).stdout or '{}')
    dur = float(pr.get('format', {}).get('duration', 0))
    vs = [s for s in pr.get('streams', []) if s.get('codec_type') == 'video']
    # shots: scene score > .25 (dissolves/spins give several hits; we merge hits closer than .35 s)
    sc = run(['ffmpeg', '-nostdin', '-i', mp4, '-vf', "scale=180:-1,select='gt(scene,0.25)',showinfo", '-an', '-f', 'null', '-'])
    cuts = [float(x) for x in re.findall(r'pts_time:([0-9.]+)', sc.stderr)]
    merged = []
    for c in cuts:
        if not merged or c - merged[-1] > .35:
            merged.append(c)
    loud = re.findall(r'I:\s+(-?[0-9.]+) LUFS', run(['ffmpeg', '-nostdin', '-i', mp4, '-af', 'ebur128', '-f', 'null', '-']).stderr)
    # one frame per shot (middle), 270 px wide
    bounds = [0] + merged + [dur]
    frames = []
    for k in range(len(bounds) - 1):
        t = (bounds[k] + bounds[k + 1]) / 2
        f = f'{d}/s{k:02d}.jpg'
        run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-ss', f'{t:.2f}', '-i', mp4, '-frames:v', '1', '-vf', 'scale=270:-1', '-q:v', '5', f])
        if os.path.exists(f):
            frames.append(f)
    motion = shot_motion(mp4, bounds)
    trans = transition_look(mp4, merged)
    # palette: mean colour of each frame, quantised
    pal = []
    for f in frames:
        im = Image.open(f).convert('RGB').resize((1, 1), Image.BILINEAR)
        pal.append('#%02x%02x%02x' % im.getpixel((0, 0)))
    # header strip and caption strip from the 2nd shot for text-layout study
    if frames:
        run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-ss', '2.5', '-i', mp4, '-frames:v', '1', '-vf', 'scale=540:-1', '-q:v', '4', f'{d}/full.jpg'])
    # dua text with word times
    segs, info = model().transcribe(mp4, language='ar', word_timestamps=True, vad_filter=True)
    words, lines = [], []
    for s in segs:
        lines.append({'start': round(s.start, 2), 'end': round(s.end, 2), 'text': s.text.strip()})
        for w in s.words or []:
            words.append([round(w.start, 2), round(w.end, 2), w.word.strip()])
    speech_start = words[0][0] if words else None
    a = {'id': vid, 'url': v['url'], 'date': v['date'], 'plays': v['plays'], 'dur': round(dur, 2),
         'w': vs[0].get('width') if vs else None, 'h': vs[0].get('height') if vs else None, 'fps': vs[0].get('r_frame_rate') if vs else None,
         'cuts': merged, 'shots': len(bounds) - 1, 'shot_len_mean': round(dur / max(1, len(bounds) - 1), 2),
         'lufs': float(loud[-1]) if loud else None, 'palette': pal, 'speech_start': speech_start,
         'words_per_s': round(len(words) / max(.1, (words[-1][1] - words[0][0]) if words else 1), 2),
         'lines': lines, 'words': words, 'desc': v['desc'], 'motion': motion, 'transitions': trans}
    json.dump(a, open(f'{d}/a.json', 'w'), ensure_ascii=False)
    try:
        os.remove(mp4)          # keep frames and data, not the copyrighted video
    except OSError:
        pass
    return vid, f'ok shots={a["shots"]} words={len(words)}'

with ThreadPoolExecutor(W) as ex:
    for vid, st in ex.map(analyze, pick):
        print(vid, st, flush=True)
