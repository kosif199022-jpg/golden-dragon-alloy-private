"""Opt-in voice-energy lip animation for stylized rig characters.

Uses FFmpeg to decode mono PCM; this approximates speaking activity and does
NOT do word/phoneme alignment. Never infers transcript/identity from the audio.
"""
from __future__ import annotations
from array import array
import copy
import math
from pathlib import Path
import shutil
import subprocess
import sys

SAMPLE_RATE = 16000
HOP_HZ = 20


def levels_from_audio(path, max_seconds=600):
    src = Path(path).expanduser().resolve()
    if not src.is_file() or not 0 < src.stat().st_size <= 250_000_000:
        raise ValueError('audio file missing or too large')
    if not shutil.which('ffmpeg'):
        raise RuntimeError('FFmpeg required for voice envelope analysis')
    command = ['ffmpeg','-hide_banner','-nostdin','-v','error','-i',str(src),
               '-vn','-ac','1','-ar',str(SAMPLE_RATE),'-t',str(max_seconds),
               '-f','s16le','-acodec','pcm_s16le','pipe:1']
    try:
        raw = subprocess.run(command, capture_output=True, check=True, timeout=120).stdout
    except subprocess.CalledProcessError as e:
        raise ValueError('audio decode failed') from e
    if not raw:
        raise ValueError('audio has no decoded samples')
    samples = array('h')
    samples.frombytes(raw[:len(raw)//2*2])
    if sys.byteorder != 'little':
        samples.byteswap()
    hop = SAMPLE_RATE // HOP_HZ
    powers = []
    for start in range(0, len(samples), hop):
        seg = samples[start:start+hop]
        rms = math.sqrt(sum(int(x)*int(x) for x in seg)/len(seg))/32768
        powers.append(rms)
    # A robust speech-like peak avoids a rare spike dominating all animation.
    sorted_levels = sorted(powers)
    peak = sorted_levels[min(len(sorted_levels)-1, int(.96*(len(sorted_levels)-1)))]
    if peak < .0025:
        return [0.0]*len(powers)
    floor = max(.003, peak*.09)
    normalized = [min(1., max(0., (p-floor)/(peak-floor))**.65) for p in powers]
    # Two-sided smoothing prevents distracting lip flicker.
    smooth=[]
    for i, level in enumerate(normalized):
        prev = normalized[i-1] if i else 0
        nxt = normalized[i+1] if i+1 < len(normalized) else 0
        smooth.append(round(.20*prev + .60*level + .20*nxt, 5))
    return smooth


def value_at(levels, seconds):
    if seconds < 0 or not math.isfinite(seconds):
        raise ValueError('invalid voice timeline')
    index = int(seconds*HOP_HZ)
    return levels[index] if index < len(levels) else 0.0


def apply_lipsync(shots, levels, max_keys=64):
    """Map global voice intensity to per-shot normalized Keyframes.

    Only director2d/ik2d shots are modified; existing mouth keys are preserved
    by rejecting conflicts (caller can opt out of automatic synchronization).
    """
    if not isinstance(levels,list) or not levels or not 2 <= max_keys <= 64:
        raise ValueError('invalid voice levels or keyframe limit')
    if not all(isinstance(v,(float,int)) and math.isfinite(v) and 0 <= v <= 1 for v in levels):
        raise ValueError('invalid voice energy value')
    updated = copy.deepcopy(shots)
    cursor = 0.0
    processed=0
    for shot in updated:
        dur = float(shot['duration'])
        recipe = shot.get('recipe', {})
        actor = recipe.get('actor', {})
        if recipe.get('mode') == 'director2d' and actor.get('rig') == 'ik2d':
            if actor.get('mouth_keys') is not None:
                raise ValueError('automatic lip sync conflicts with existing manual mouth keys')
            count = min(max_keys, max(2, math.ceil(dur*HOP_HZ)+1))
            actor['mouth_keys'] = [
                {'t': round(i/(count-1),7),
                 'value': round(value_at(levels,cursor+dur*i/(count-1)),5),
                 'ease': 'linear'}
                for i in range(count)]
            processed+=1
        cursor += dur
    return updated, {'method':'voice_rms_envelope','timeline_hz':HOP_HZ,
                     'processed_shots':processed,'phoneme_alignment':False}
