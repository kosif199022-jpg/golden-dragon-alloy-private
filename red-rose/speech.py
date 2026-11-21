"""Subtitle timeline import inspired by user-owned Golden Bird speech_sync behavior.
This implementation is original and does not invoke any prior skills.
"""
import copy
import re

STAMP = re.compile(r'^(\d{2}):(\d{2}):(\d{2})[,.](\d{3})$')

def seconds(stamp):
    match = STAMP.fullmatch(stamp.strip())
    if not match:
        raise ValueError('Invalid SRT timestamp')
    hours, minutes, sec, ms = map(int, match.groups())
    if minutes >= 60 or sec >= 60:
        raise ValueError('Invalid minutes/seconds')
    return (hours * 3600 + minutes * 60 + sec) + ms / 1000

def parse_srt(text):
    """Return timed captions; reject overlaps/empty bodies and invalid timestamps."""
    cues = []
    blocks = re.split(r'\n\s*\n', text.replace('\r\n', '\n').strip())
    for block in blocks:
        if not block.strip():
            continue
        lines = [s.strip() for s in block.split('\n')]
        if lines[0].isdigit():
            lines = lines[1:]
        if len(lines) < 2 or ' --> ' not in lines[0]:
            raise ValueError('Malformed SRT cue')
        start_stamp, end_stamp = lines[0].split(' --> ', 1)
        start, end = seconds(start_stamp), seconds(end_stamp)
        if end <= start or start < 0 or (cues and start < cues[-1]['end']):
            raise ValueError('Out-of-order or overlapping SRT cue')
        label = '\n'.join(lines[1:]).strip()
        if not label:
            raise ValueError('Empty SRT cue')
        cues.append({'start': start, 'end': end, 'text': label})
    if not cues:
        raise ValueError('No SRT cues')
    return cues

def apply_captions(shots, cues):
    """Map global cue times to scene-local captions. Captions display in character2d shots."""
    updated = copy.deepcopy(shots)
    elapsed = 0.0
    for shot in updated:
        duration = float(shot['duration'])
        end = elapsed + duration
        recipe = shot.setdefault('recipe', {})
        local = recipe.setdefault('captions', [])
        for cue in cues:
            a = max(cue['start'], elapsed)
            b = min(cue['end'], end)
            if a < b:
                local.append({'start': round(a - elapsed, 6),
                              'end': round(b - elapsed, 6), 'text': cue['text']})
        elapsed = end
    return updated
