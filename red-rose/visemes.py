"""Text-assisted 2D mouth poses for timestamped words/caption cues.

This is NOT acoustic phoneme recognition. A supplied word-time file can provide
explicit timing; SRT text gives estimated timing within each caption. Sound
energy from lip_sync remains the gate that closes mouths during silence.
"""
from __future__ import annotations
import copy
import math
import re
from collections.abc import Sequence

SHAPES = ('closed', 'wide', 'round', 'open', 'teeth', 'neutral')
WORD_RE = re.compile(r"[\w\u0600-\u06ff']+", re.UNICODE)


def classify_letter(char: str) -> str:
    """Approximate *visible* mouth poses from written graphemes, not phonemes."""
    c = char.casefold()
    if c in 'bmpبم':
        return 'closed'
    if c in 'fvفڤ':
        return 'teeth'
    if c in 'ouwوؤ':
        return 'round'
    if c in 'aeiyاأإآىيئة':
        return 'open'
    return 'wide'


def validate_words(words, total_seconds: float) -> list[dict]:
    if not isinstance(total_seconds, (int, float)) or not math.isfinite(total_seconds) or total_seconds <= 0:
        raise ValueError('invalid project duration')
    if not isinstance(words, list) or not 1 <= len(words) <= 10000:
        raise ValueError('words must be a nonempty list')
    result = []
    last_end = 0.0
    for w in words:
        if not isinstance(w, dict) or not isinstance(w.get('text'), str):
            raise ValueError('word requires text')
        text = w['text'].strip()
        if not text or len(text) > 80 or not WORD_RE.search(text):
            raise ValueError('invalid word text')
        a,b = w.get('start'),w.get('end')
        if any(not isinstance(v, (int,float)) or isinstance(v,bool) or not math.isfinite(v) for v in (a,b)):
            raise ValueError('word times must be finite numbers')
        if not (last_end - 1e-8 <= a < b <= total_seconds + 1e-8):
            raise ValueError('words must be ordered, nonoverlapping, and within video')
        result.append({'start': float(a), 'end': float(b), 'text': text})
        last_end = float(b)
    return result


def estimate_words_from_srt(cues: Sequence, total_seconds: float) -> list[dict]:
    """Uniform-ish grapheme-length interpolation; no claim of word-level truth."""
    if not isinstance(cues, list) or not cues:
        raise ValueError('SRT cues required')
    words = []
    for cue in cues:
        a,b,txt = cue['start'],cue['end'],cue['text']
        if not 0 <= a < b <= total_seconds + 1e-8:
            raise ValueError('SRT cue beyond video duration')
        tokens=WORD_RE.findall(txt)
        if not tokens:
            raise ValueError('caption has no pronounceable words')
        weights=[max(1,len(w)) for w in tokens]
        cumul=0.0
        total=sum(weights)
        for i,(text,weight) in enumerate(zip(tokens,weights)):
            start=a+(b-a)*cumul/total
            cumul+=weight
            end=b if i==len(tokens)-1 else a+(b-a)*cumul/total
            words.append({'start':start,'end':end,'text':text})
    return validate_words(words,total_seconds)


def _letter_events(word: dict) -> list[tuple[float,str]]:
    # Weighted intervals: simplified orthography -> mouth shapes, not phonetics.
    letters=[c for c in word['text'] if c.isalpha()]
    if not letters:
        return []
    duration=word['end']-word['start']
    events=[]
    for index, letter in enumerate(letters):
        t=word['start']+duration*index/len(letters)
        shape=classify_letter(letter)
        if not events or events[-1][1]!=shape:
            events.append((t,shape))
    return events


def _sample_shape(keys, phase):
    if not isinstance(keys,list) or len(keys)>256:
        raise ValueError('invalid viseme track')
    active='neutral'
    prev=-1.0
    for key in keys:
        if not isinstance(key,dict) or set(key)!={'t','shape'}:
            raise ValueError('invalid viseme keyframe')
        t=key['t'];shape=key['shape']
        if not isinstance(t,(int,float)) or not math.isfinite(t) or t<0 or t>1 or t<=prev or shape not in SHAPES:
            raise ValueError('invalid viseme keyframe')
        prev=t
        if t <= phase+1e-9:
            active=shape
        else:
            break
    return active


def sample_viseme(keys, phase):
    if not isinstance(phase, (int, float)) or not math.isfinite(phase) or not 0 <= phase <= 1:
        raise ValueError('invalid viseme phase')
    if keys is None:
        return 'neutral'
    return _sample_shape(keys,phase)


def apply_visemes(shots, words, max_keys=256):
    """Add scene-local stepped viseme tracks for director2d/ik2d shots.

    The caller should separately use apply_lipsync for energy-gated mouth motion.
    """
    if not isinstance(shots,list) or not shots or not 8 <= max_keys <= 256:
        raise ValueError('invalid storyboard or keyframe budget')
    total=sum(float(s['duration']) for s in shots)
    words=validate_words(words,total)
    updated=copy.deepcopy(shots)
    events=[]
    for w in words:
        events.extend(_letter_events(w))
        events.append((w['end'],'neutral'))
    cursor=0.0
    count=0
    for shot in updated:
        duration=float(shot['duration'])
        end=cursor+duration
        recipe=shot.get('recipe',{})
        actor=recipe.get('actor',{})
        if recipe.get('mode')=='director2d' and actor.get('rig')=='ik2d':
            if 'viseme_keys' in actor:
                raise ValueError('existing viseme keys must not be overwritten')
            # Carry current shape across a scene boundary.
            start_shape='neutral'
            for at,shape in events:
                if at <= cursor+1e-9:
                    start_shape=shape
                else:
                    break
            track=[{'t':0.0,'shape':start_shape}]
            for at,shape in events:
                if at <= cursor+1e-9 or at >= end-1e-9:
                    continue
                t=round((at-cursor)/duration,7)
                if t<=track[-1]['t']:
                    continue
                if shape!=track[-1]['shape']:
                    track.append({'t':t,'shape':shape})
            # Deterministic reduction when one shot contains too many symbols.
            if len(track)>max_keys:
                track=[track[round(i*(len(track)-1)/(max_keys-1))] for i in range(max_keys)]
            actor['viseme_keys']=track
            count+=1
        cursor=end
    return updated, {'method':'text_grapheme_pose_with_optional_audio_gate',
                     'timing_is_acoustic_alignment':False,
                     'words':len(words),'processed_shots':count}
