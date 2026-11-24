"""Independent FFprobe + full decode checks for generated Red Rose videos."""
from __future__ import annotations
import hashlib
import json
import math
import shutil
import subprocess
from fractions import Fraction
from pathlib import Path


def verify_video(video, *, expected_fps=None, width=None, height=None, expected_frames=None, expected_audio=None):
    p=Path(video).resolve()
    if not p.is_file() or not p.stat().st_size:
        raise FileNotFoundError(p)
    if not shutil.which('ffprobe') or not shutil.which('ffmpeg'):
        raise RuntimeError('FFprobe and FFmpeg are required for independent QA')
    cmd=['ffprobe','-v','error','-count_frames','-show_entries',
         'format=duration:stream=index,codec_type,codec_name,width,height,avg_frame_rate,nb_read_frames',
         '-of','json',str(p)]
    data=json.loads(subprocess.run(cmd,capture_output=True,text=True,check=True).stdout)
    video_streams=[s for s in data.get('streams',[]) if s.get('codec_type')=='video']
    if len(video_streams)!=1:raise ValueError('expected exactly one video stream')
    v=video_streams[0]
    fps=float(Fraction(v['avg_frame_rate']))
    if not math.isfinite(fps) or fps<=0:raise ValueError('bad fps')
    frames=int(v['nb_read_frames']) if v.get('nb_read_frames','N/A')!='N/A' else None
    duration=float(data['format']['duration'])
    if expected_fps is not None and abs(fps-expected_fps)>0.02: raise ValueError(f'fps {fps} != {expected_fps}')
    if width is not None and v['width']!=width:raise ValueError(f'width {v["width"]} != {width}')
    if height is not None and v['height']!=height:raise ValueError(f'height {v["height"]} != {height}')
    if expected_frames is not None and frames!=expected_frames: raise ValueError(f'frames {frames} != {expected_frames}')
    audio_streams=[s for s in data['streams'] if s['codec_type']=='audio']
    if expected_audio is True and not audio_streams:raise ValueError('missing audio stream')
    if expected_audio is False and audio_streams:raise ValueError('unexpected audio stream')
    subprocess.run(['ffmpeg','-v','error','-xerror','-i',str(p),'-f','null','-'],
                   capture_output=True,text=True,check=True)
    # Stream large video hashes instead of allocating a second copy in RAM.
    h = hashlib.sha256()
    with p.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    digest = h.hexdigest()
    return {'passed':True,'codec':v['codec_name'],'fps':fps,'frames':frames,
            'width':v['width'],'height':v['height'],'duration':duration,
            'audio_codec':audio_streams[0]['codec_name'] if audio_streams else None,
            'sha256':digest,'bytes':p.stat().st_size}
