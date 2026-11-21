"""Red Rose V15: one shared nonlegacy video pipeline for CLI and capability runner.

The explicit video production action is bounded and opt-in.  No agent,
model API, or legacy dragon code is invoked by this module.
"""
from __future__ import annotations
import copy
import json
import math
from pathlib import Path

from production import produce
from storyboard import validate_shots
from speech import parse_srt, apply_captions
from identity import apply_profiles
from lip_sync import levels_from_audio, apply_lipsync
from visemes import estimate_words_from_srt, apply_visemes, validate_words

MAX_FRAMES = 3600
MAX_PIXELS = 1920 * 1080


def prepare_project(storyboard_file, *, srt=None, profiles=None, audio=None,
                    lip_sync=False, viseme_sync=False, words_json=None):
    """Prepare shots without mutating the input storyboard or writing output."""
    shots = json.loads(Path(storyboard_file).expanduser().read_text(encoding='utf-8'))
    if not isinstance(shots, list):
        raise ValueError('storyboard must contain a list of shots')
    shots = copy.deepcopy(shots)
    duration = validate_shots(shots)
    cues = None
    if srt:
        cues = parse_srt(Path(srt).expanduser().read_text(encoding='utf-8-sig'))
        shots = apply_captions(shots, cues)
    identities = {}
    if profiles:
        shots, identities = apply_profiles(shots, json.loads(Path(profiles).expanduser().read_text(encoding='utf-8')))
    if viseme_sync and not lip_sync:
        raise ValueError('viseme sync requires audio-driven lip sync')
    if words_json and not viseme_sync:
        raise ValueError('words-json requires viseme sync')
    sync = None
    if lip_sync:
        if not audio:
            raise ValueError('lip-sync requires speech audio')
        shots, sync = apply_lipsync(shots, levels_from_audio(audio))
        if not sync['processed_shots']:
            raise ValueError('no director2d/ik2d shot found for lip sync')
    viseme_report = None
    if viseme_sync:
        if words_json:
            words = validate_words(json.loads(Path(words_json).expanduser().read_text(encoding='utf-8')), duration)
            timing_source = 'provided_word_timestamps'
        elif cues is not None:
            words = estimate_words_from_srt(cues, duration)
            timing_source = 'estimated_from_srt_cues'
        else:
            raise ValueError('viseme-sync requires --words-json or --srt')
        shots, viseme_report = apply_visemes(shots, words)
        viseme_report['timing_source'] = timing_source
    return shots, {'locked_characters': identities, 'voice_sync': sync,
                   'viseme_sync': viseme_report, 'duration': duration}


def budget(shots, fps=24, width=540, height=960):
    """Predict and cap work BEFORE FFmpeg creates an output folder."""
    if any(type(v) is not int for v in (fps, width, height)):
        raise ValueError('fps and dimensions must be integers')
    if not 1 <= fps <= 60 or not 64 <= width <= 1920 or not 64 <= height <= 1080:
        raise ValueError('unsupported render settings')
    if width * height > MAX_PIXELS:
        raise ValueError('video pixel budget exceeded')
    if width % 2 or height % 2:
        raise ValueError('H264 yuv420p dimensions must be even')
    seconds = validate_shots(shots)
    if not math.isfinite(seconds):
        raise ValueError('invalid duration')
    frames = round(seconds * fps)
    if not 1 <= frames <= MAX_FRAMES:
        raise ValueError('video frame budget exceeded')
    return {'frames': frames, 'fps': fps, 'width': width, 'height': height,
            'seconds': seconds, 'pixels': width * height, 'shots': len(shots)}


def render_project(storyboard_file, output, *, fps=24, width=540, height=960,
                   audio=None, srt=None, profiles=None, lip_sync=False,
                   viseme_sync=False, words_json=None, overwrite=False):
    """Render with safeguards and a complete local editable project manifest."""
    shots, metadata = prepare_project(storyboard_file, srt=srt, profiles=profiles,
                                     audio=audio, lip_sync=lip_sync,
                                     viseme_sync=viseme_sync, words_json=words_json)
    estimated = budget(shots, fps=fps, width=width, height=height)
    target = Path(output).expanduser().resolve()
    if target == Path.cwd().resolve() or target == Path.home().resolve() or target.parent == target:
        raise ValueError('output directory must be a dedicated folder')
    if target.exists() and any(target.iterdir()):
        if not overwrite:
            raise FileExistsError('output directory not empty; explicitly allow overwrite')
        # Never accept a casual overwrite of an unrelated folder.
        previous = target / 'project.json'
        try:
            prior = json.loads(previous.read_text(encoding='utf-8'))
        except (FileNotFoundError, ValueError, UnicodeError) as exc:
            raise ValueError('overwrite is allowed only for an existing Red Rose project') from exc
        if prior.get('schema') != 'red-rose-storyboard-v11':
            raise ValueError('overwrite refused: unrecognized existing project')
    report = produce(shots, target, fps=fps, width=width, height=height, audio=audio)
    report.update({'locked_characters': metadata['locked_characters'],
                   'voice_sync': metadata['voice_sync'],
                   'viseme_sync': metadata['viseme_sync'],
                   'budget': estimated,
                   'style_save_question': 'هل تريد حفظ هذا الأسلوب باسم معين؟'})
    (target / 'manifest.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    return report
