"""Multi-shot video production and optional licensed audio muxing."""
import json, shutil, subprocess
from pathlib import Path
from storyboard import validate_shots, frame_at
from verify_media import verify_video

def produce(shots, output, fps=24, width=540, height=960, audio=None, keep_frames=False):
    if not isinstance(fps,int) or not 1<=fps<=120 or width<16 or height<16:
        raise ValueError('invalid video settings')
    duration=validate_shots(shots)
    if not shutil.which('ffmpeg'): raise RuntimeError('ffmpeg is required')
    try: import cairosvg
    except ImportError as e: raise RuntimeError('cairosvg is required') from e
    output=Path(output).resolve(); output.mkdir(parents=True,exist_ok=True)
    count=round(duration*fps)
    if count<1: raise ValueError('too few frames')
    for i in range(count):
        svg=frame_at(shots,i/fps,width,height)
        cairosvg.svg2png(bytestring=svg.encode(),write_to=str(output/f'frame_{i:05d}.png'))
    video=output/'video.mp4'
    cmd=['ffmpeg','-hide_banner','-loglevel','error','-y','-framerate',str(fps),'-i',str(output/'frame_%05d.png')]
    if audio:
        audio=Path(audio).resolve()
        if not audio.is_file(): raise FileNotFoundError(audio)
        cmd+=['-i',str(audio),'-map','0:v:0','-map','1:a:0','-c:a','aac','-af','apad','-t',f'{count/fps:.9f}']
    cmd+=['-c:v','libx264','-pix_fmt','yuv420p','-movflags','+faststart',str(video)]
    subprocess.run(cmd,check=True)
    qa=verify_video(video,expected_fps=fps,width=width,height=height,expected_frames=count,expected_audio=bool(audio))
    manifest={'shots':len(shots),'frames':count,'fps':fps,'duration':count/fps,'video':str(video),'audio':bool(audio),'qa':qa}
    (output/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    (output/'project.json').write_text(json.dumps({'schema':'red-rose-storyboard-v11','fps':fps,'width':width,'height':height,'shots':shots,'audio_source':str(audio) if audio else None},ensure_ascii=False,indent=2),encoding='utf-8')
    (output/'qa.json').write_text(json.dumps(qa,ensure_ascii=False,indent=2),encoding='utf-8')
    if not keep_frames:
        for i in range(count): (output/f'frame_{i:05d}.png').unlink()
    return manifest
