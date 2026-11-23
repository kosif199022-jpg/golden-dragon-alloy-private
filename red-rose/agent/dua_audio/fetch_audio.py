#!/usr/bin/env python3
"""Dua audio library: for each video in audio_list.json keep only the audio (m4a, stream copy).
~/audio/<account>/<label>/<date>_<id>.m4a ; resumable; usage: audio_job.py audio_list.json [workers] [max_seconds]"""
import json, os, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor
L = json.load(open(sys.argv[1])); W = int(sys.argv[2]) if len(sys.argv) > 2 else 6
deadline = time.time() + (int(sys.argv[3]) if len(sys.argv) > 3 else 820)
env = dict(os.environ, HOME='/home/user', PYTHONPATH='/home/user/pylib')
base = os.path.expanduser('~/audio')
def one(v):
    d = f"{base}/{v['acc']}/{v['label']}"; os.makedirs(d, exist_ok=True)
    out = f"{d}/{v['date']}_{v['id']}.m4a"
    if os.path.exists(out) and os.path.getsize(out) > 5000: return 1
    if time.time() > deadline: return 0
    tmp = f"/tmp/a_{v['id']}"
    subprocess.run(['python3', '-m', 'yt_dlp', '--impersonate', 'chrome', '-f', 'b', '-o', tmp + '.%(ext)s', '--no-progress', '-q', v['url']], env=env, timeout=120, capture_output=True)
    src = next((tmp + e for e in ('.mp4', '.webm', '.m4a') if os.path.exists(tmp + e)), None)
    if not src: return 0
    subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-i', src, '-vn', '-c:a', 'copy', out])
    os.remove(src)
    return int(os.path.exists(out))
with ThreadPoolExecutor(W) as ex: ok = sum(ex.map(one, L))
print('audio ok', ok, 'of', len(L), flush=True)
