#!/usr/bin/env python3
"""KOSIF Reel DNA: offline, evidence-oriented reference-to-owned-footage editing.

No downloads, remote calls, generation, or Higgsfield execution. The Katana commands
printed here are a guide based on a user's 2026-11-11 --help report, NOT verified here.

CLI:
    reel-dna doctor
    reel-dna katana-commands --workdir /home/user/rr/reel1 --url URL
    reel-dna extract --analysis analysis.json --duration 8 --fps 30 --out dna.json
        [--energy energy.json] [--beats beats.json] [--cutsync cutsync.json] [--words words.json]
    reel-dna apply --recipe dna.json --clips own1.mp4 own2.png --out edl.json
    reel-dna render --edl edl.json --out preview.mp4 [--width 540 --height 960] [--audio own.wav]
    reel-dna compare --reference dna.json --ours other_dna.json

Parser accepts a small transparent, documented set of field names. Unrecognized fields
are NOT silently interpreted as events. Every transformed event preserves source data.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys

IMAGE_SUFFIXES = {'.png', '.jpg', '.jpeg', '.webp', '.bmp'}
VIDEO_SUFFIXES = {'.mp4', '.mov', '.mkv', '.webm', '.m4v', '.avi'}
EVENT_TYPES = {'flash', 'shake', 'pan', 'punch', 'color_invert', 'zoom', 'black', 'white'}


def read_obj(path):
    p = Path(path)
    if not p.is_file():
        raise ValueError(f'file not found: {p}')
    try:
        data = json.loads(p.read_text('utf-8'))
    except (ValueError, UnicodeError) as exc:
        raise ValueError(f'Invalid JSON at {p}: {exc}') from exc
    if not isinstance(data, dict):
        raise ValueError(f'JSON root must be an object: {p}')
    return data


def write_obj(path, obj):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    if p.exists():
        raise ValueError(f'output already exists, refusing to overwrite: {p}')
    with p.open('x', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write('\n')
    return p


def file_hash(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def lookup(d, keys):
    for key in keys:
        if key in d and d[key] is not None:
            return d[key]
    return None


def parse_fps(value):
    try:
        if isinstance(value, str) and '/' in value:
            left, right = value.split('/', 1)
            value = float(left) / float(right)
        f = float(value)
    except (TypeError, ValueError, ZeroDivisionError) as exc:
        raise ValueError('fps must be positive and numeric, e.g. 30 or 30000/1001') from exc
    if not math.isfinite(f) or not 0 < f <= 240:
        raise ValueError('fps must be > 0 and <= 240')
    return f


def seconds(value, context, fps):
    if isinstance(value, dict):
        if value.get('frame') is not None:
            return float(value['frame']) / fps
        v = lookup(value, ['time', 'seconds', 'timestamp', 't', 'start_time', 'start_s', 'start'])
        if v is None:
            raise ValueError(f'{context}: missing time/frame')
        value = v
    try:
        t = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f'{context}: invalid time {value!r}') from exc
    if not math.isfinite(t) or t < 0:
        raise ValueError(f'{context}: time must be finite, >= 0')
    return t


def to_frame(t, fps, nframes, context):
    frame = int(round(t * fps))
    if frame < 0 or frame > nframes:
        raise ValueError(f'{context}: time {t} lies outside reference duration')
    return frame


def find_list(obj, names):
    for name in names:
        result = obj.get(name)
        if isinstance(result, list):
            return result, name
    return None, None


def extract(args):
    analysis = read_obj(args.analysis)
    katana = str(analysis.get('schema', '')).startswith('rr.analysis') and isinstance(analysis.get('ref'), dict)
    if katana:  # v1990: real Katana analyze_ref.py output
        ref = analysis['ref']
        if args.fps is None:
            args.fps = ref.get('fps') or ref.get('fps_float')
        if args.duration is None and ref.get('nb_frames') and args.fps is not None:
            args.duration = float(ref['nb_frames']) / parse_fps(args.fps)
        elif args.duration is None:
            args.duration = ref.get('video_duration')
    metadata = analysis.get('metadata') if isinstance(analysis.get('metadata'), dict) else {}
    media = analysis.get('video') if isinstance(analysis.get('video'), dict) else {}
    fps = parse_fps(args.fps if args.fps is not None else lookup(analysis, ['fps', 'frame_rate']) or lookup(media, ['fps','frame_rate']) or lookup(metadata, ['fps','frame_rate']))
    duration = args.duration if args.duration is not None else (lookup(analysis, ['duration', 'duration_s', 'duration_seconds']) or lookup(media, ['duration', 'duration_s']) or lookup(metadata, ['duration', 'duration_s']))
    if duration is None:
        raise ValueError('duration not found in input; provide --duration from ffprobe (no guessing)')
    try:
        duration = float(duration)
    except (TypeError, ValueError) as exc:
        raise ValueError('duration must be a finite number of seconds') from exc
    if not math.isfinite(duration) or duration <= 0 or duration > 24 * 3600:
        raise ValueError('duration must be positive and <= 24 h')
    total = int(round(duration * fps))
    if total < 1:
        raise ValueError('duration is shorter than one frame')
    cut_arr, cuts_field = find_list(analysis, ['cuts', 'cut_points', 'scene_cuts', 'shot_boundaries'])
    shots_arr, shots_field = find_list(analysis, ['shots', 'segments', 'scenes'])
    notes = []
    cut_frames = {0, total}
    confidences = {}
    if katana and cut_arr is not None:
        for i, raw in enumerate(cut_arr):
            if not isinstance(raw, dict) or not isinstance(raw.get('f0'), int) or isinstance(raw.get('f0'), bool):
                raise ValueError(f'Katana cut[{i}] lacks integer f0')
            f = raw['f0']
            if f < 0 or f >= total:
                raise ValueError(f'Katana cut[{i}] f0={f} lies outside the reference ({total} frames)')
            cut_frames.add(f)
            if f and raw.get('confidence') is not None:
                try:
                    confidences[f] = float(raw['confidence'])
                except (TypeError, ValueError):
                    notes.append(f'Invalid confidence for cut[{i}]; ignored')
    elif cut_arr is not None:
        for i, raw in enumerate(cut_arr):
            t = seconds(raw, f'cut[{i}]', fps)
            f = to_frame(t, fps, total, f'cut[{i}]')
            cut_frames.add(f)
            if isinstance(raw, dict) and raw.get('confidence') is not None:
                try:
                    confidences[f] = float(raw['confidence'])
                except (TypeError, ValueError):
                    notes.append(f'Invalid confidence for cut[{i}]; ignored')
    if shots_arr is not None:
        for i, raw in enumerate(shots_arr):
            if not isinstance(raw, dict):
                raise ValueError(f'{shots_field}[{i}] needs start/end object')
            start = lookup(raw, ['start_frame', 'start_time', 'start_s', 'start'])
            end = lookup(raw, ['end_frame', 'end_time', 'end_s', 'end'])
            if start is None or end is None:
                raise ValueError(f'{shots_field}[{i}] lacks start/end')
            s = (float(start)/fps if 'start_frame' in raw else seconds(start, f'{shots_field}[{i}].start', fps))
            e = (float(end)/fps if 'end_frame' in raw else seconds(end, f'{shots_field}[{i}].end', fps))
            a, b = to_frame(s, fps, total, 'start'), to_frame(e, fps, total, 'end')
            if b <= a:
                raise ValueError(f'{shots_field}[{i}] has nonpositive duration')
            cut_frames.update([a,b])
        if cut_arr is not None:
            notes.append('Both cuts and shots supplied; boundaries combined. Review possible duplicate/false positives.')
    if cut_arr is None and shots_arr is None:
        raise ValueError('No supported cuts or shots list. Request the actual Katana JSON and map its field names; do not invent cuts.')
    boundaries = sorted(cut_frames)
    shots = []
    for i, (a, b) in enumerate(zip(boundaries, boundaries[1:]), 1):
        if b <= a:
            continue
        shots.append({'id': f'c{i:03d}', 'start_frame':a, 'end_frame':b, 'duration_frames':b-a,
                      'start_s': round(a/fps, 6), 'end_s':round(b/fps, 6)})
    events, beats, words = [], [], []
    rates, sync = None, None
    inputs = {'analysis': {'sha256':file_hash(args.analysis), 'file':Path(args.analysis).name}}
    if args.energy:
        energy = read_obj(args.energy)
        inputs['energy'] = {'sha256':file_hash(args.energy), 'file':Path(args.energy).name}
        event_arr, field = find_list(energy, ['events', 'timeline_events', 'hits'])
        if event_arr is None and isinstance(energy.get('events'), dict):  # v1990: Katana energy.py map
            event_arr, field = [], 'events{}'
            for key, typ in (('flashes', 'flash'), ('shakes', 'shake'), ('pans', 'pan'), ('hits', 'punch')):
                for e in energy['events'].get(key) or []:
                    if isinstance(e, dict):
                        row = dict(e)
                        if typ == 'flash' and row.get('type') in ('white', 'black'):
                            row['flash_color'] = row['type']
                        row['type'] = typ
                        if typ == 'shake' and row.get('amp_px') is not None:
                            row['amplitude'] = row['amp_px']
                        event_arr.append(row)
            if isinstance(energy.get('rates'), dict):
                rates = {k: v for k, v in energy['rates'].items() if k != 'path'}
        if event_arr is None:
            notes.append('energy.json event fields unrecognized; no events imported')
        else:
            for i, e in enumerate(event_arr):
                if not isinstance(e, dict):
                    notes.append(f'energy event {i} unrecognized; skipped');continue
                typ = str(lookup(e, ['type','kind','event','effect']) or '').lower().replace('-', '_')
                if typ not in EVENT_TYPES:
                    notes.append(f'energy event {i} type {typ!r} not mapped; skipped');continue
                try:
                    t = seconds(e, f'energy event {i}', fps)
                    f = to_frame(t, fps, total, f'energy event {i}')
                except ValueError:
                    notes.append(f'energy event {i} missing/out of range time; skipped');continue
                if f == total:
                    continue
                val = lookup(e, ['intensity', 'strength', 'amplitude'])
                try:
                    intensity = float(val) if val is not None else None
                    if intensity is not None and not math.isfinite(intensity): intensity = None
                except (ValueError, TypeError): intensity = None
                events.append({'frame': f, 'time_s':round(f/fps,6),'type':typ, 'intensity':intensity,
                               'original':e})
    if args.beats:
        obj = read_obj(args.beats)
        inputs['beats'] = {'sha256':file_hash(args.beats), 'file':Path(args.beats).name}
        arr, key = find_list(obj, ['beats','beat_times','onsets'])
        if arr is None:
            notes.append('beats.json beat array unrecognized')
        else:
            for i,v in enumerate(arr):
                try:
                    t = seconds(v, f'beat {i}', fps)
                    f = to_frame(t,fps,total,f'beat {i}')
                    if f < total: beats.append(f)
                except ValueError:
                    notes.append(f'Beat {i} skipped (invalid time)')
    if args.words:
        obj = read_obj(args.words)
        inputs['words']={'sha256':file_hash(args.words), 'file':Path(args.words).name}
        arr, key = find_list(obj, ['words', 'segments', 'transcript'])
        if arr is None:
            notes.append('words.json no recognized timed words array')
        else:
            for i,v in enumerate(arr):
                if not isinstance(v,dict):
                    notes.append(f'Word {i} unrecognized; skipped'); continue
                a,b=lookup(v,['start','start_time']),lookup(v,['end','end_time'])
                label = lookup(v,['word','text'])
                if a is None or b is None or label is None:
                    notes.append(f'Word {i} missing start/end/text; skipped');continue
                try:
                    sa=to_frame(seconds(a,'word start',fps),fps,total,'word start')
                    sb=to_frame(seconds(b,'word end',fps),fps,total,'word end')
                except ValueError:
                    notes.append(f'Word {i} out of range');continue
                if sa < sb:
                    words.append({'start_frame':sa,'end_frame':sb,'text':str(label),
                                  'confidence':v.get('confidence') if v.get('confidence') is not None else v.get('prob')})
    if args.cutsync:
        obj=read_obj(args.cutsync)
        inputs['cutsync']={'sha256':file_hash(args.cutsync), 'file':Path(args.cutsync).name}
        if str(obj.get('schema', '')).startswith('rr.cutsync') and isinstance(obj.get('summary'), dict):  # v1990
            sync = {'bpm': obj.get('bpm'), 'verdict': obj.get('verdict'),
                    **{k: v for k, v in obj['summary'].items() if isinstance(v, (int, float))}}
        else:
            notes.append('Cutsync analysis retained as source fingerprint only (schema unverified).')
    recipe = {'schema':'kosif.reel-dna.v1','version':'1990', 'fps':fps,
              'reference_duration_s':duration,'total_frames':total,
              'cuts':[{'frame': f, 'confidence':confidences.get(f)} for f in boundaries[1:-1]],
              'shots':shots, 'energy_events': sorted(events,key=lambda e:e['frame']),
              'beat_frames':sorted(set(beats)), 'words':sorted(words,key=lambda w:w['start_frame']),
              'energy_rates': rates, 'cut_sync': sync,
              'source_schema': analysis.get('schema') if katana else None,
              'sources':inputs, 'warnings':notes,
              'limitations':{'fonts':'Not recognized from image; must be chosen by user',
                             'copyright':'Do not copy third-party footage/music/characters without permission',
                             'verification':('Katana rr.analysis/1 field names verified against a real 2026-11-11 run; detectors only propose, the every-frame sheets are the ground truth'
                                             if katana else 'Imported metadata, not Katana runtime execution'),
                             'visual_matching':'Event detectors suggest timing; manual review required'}}
    write_obj(args.out,recipe)
    print(json.dumps({'recipe':str(args.out),'shots':len(shots),'events':len(events),'beats':len(recipe['beat_frames']),
                      'warnings':notes,'executed_higgsfield':False},ensure_ascii=False,indent=2))
    return 0


def apply(args):
    recipe = read_obj(args.recipe)
    if recipe.get('schema') != 'kosif.reel-dna.v1':
        raise ValueError('unsupported DNA recipe schema')
    shots = recipe.get('shots',[])
    clips=[str(Path(c).expanduser().resolve()) for c in args.clips]
    if len(clips) != len(shots):
        raise ValueError(f'Need exactly {len(shots)} clips for {len(shots)} reference shots (received {len(clips)})')
    rows=[]
    for i,(shot,clip) in enumerate(zip(shots,clips)):
        p=Path(clip)
        if not p.is_file():
            raise ValueError(f'Clip missing: {p}')
        if p.suffix.lower() not in IMAGE_SUFFIXES|VIDEO_SUFFIXES:
            raise ValueError(f'Unsupported clip file: {p.name}')
        duration_frames=shot['duration_frames']
        if not isinstance(duration_frames,int) or duration_frames<=0:
            raise ValueError('invalid duration_frames')
        rows.append({'id':shot['id'],'file':str(p),'file_sha256':file_hash(p),
                     'duration_frames':duration_frames, 'reference_start_frame':shot['start_frame']})
    edl={'schema':'kosif.reel-dna.edl.v1','fps':recipe['fps'],'total_frames':recipe['total_frames'],
         'clips':rows,'energy_events':recipe.get('energy_events',[]),
         'notes':['Only user-supplied media included; reference sound/footage are NOT copied.',
                  'Local renderer currently supports visual flash only; shake/pan/punch kept as metadata for Katana.'],
         'sources':{'recipe_sha256':file_hash(args.recipe),'recipe_name':Path(args.recipe).name}}
    if sum(x['duration_frames'] for x in rows) != edl['total_frames']:
        raise ValueError('EDL duration does not equal recipe duration')
    write_obj(args.out,edl)
    print(json.dumps({'edl':str(args.out),'clips':len(rows), 'total_frames':edl['total_frames'],
                      'no_generation':True},ensure_ascii=False,indent=2));return 0


def render(args):
    edl=read_obj(args.edl)
    if edl.get('schema') != 'kosif.reel-dna.edl.v1':
        raise ValueError('unknown EDL schema')
    if not shutil.which('ffmpeg') or not shutil.which('ffprobe'):
        raise ValueError('Requires installed ffmpeg + ffprobe')
    if args.width%2 or args.height%2 or min(args.width,args.height)<32 or max(args.width,args.height)>4320:
        raise ValueError('width/height must be even and between 32 and 4320')
    out=Path(args.out)
    if out.exists():raise ValueError(f'output exists; refusing to overwrite: {out}')
    out.parent.mkdir(parents=True,exist_ok=True)
    fps=parse_fps(edl.get('fps'))
    shots=edl.get('clips',[])
    if not shots or len(shots)>200:
        raise ValueError('EDL requires 1..200 clips')
    cmd=['ffmpeg','-nostdin','-hide_banner','-v','error']
    filt=[]
    for i,clip in enumerate(shots):
        p=Path(clip['file']); ext=p.suffix.lower()
        if not p.is_file() or ext not in IMAGE_SUFFIXES | VIDEO_SUFFIXES:
            raise ValueError(f'missing/unsupported owned media: {p}')
        if file_hash(p) != clip['file_sha256']:
            raise ValueError(f'file differs from approved EDL fingerprint: {p.name}')
        frames=int(clip['duration_frames'])
        if frames<=0:raise ValueError('Invalid frame count')
        duration=frames/fps
        if ext in IMAGE_SUFFIXES:
            cmd.extend(['-loop','1','-framerate',str(fps),'-t',f'{duration:.9f}','-i',str(p)])
        else:
            cmd.extend(['-stream_loop','-1','-i',str(p)])
        filt.append(f'[{i}:v]scale={args.width}:{args.height}:force_original_aspect_ratio=increase,'
                    f'crop={args.width}:{args.height},setsar=1,fps={fps:.7f},'
                    f'trim=end_frame={frames},setpts=PTS-STARTPTS[v{i}]')
    n = len(shots)
    filt.append(''.join(f'[v{i}]' for i in range(n))+f'concat=n={n}:v=1:a=0[vconcat]')
    flashes=[]
    for item in edl.get('energy_events',[]):
        if item.get('type')=='flash':
            f=item.get('frame')
            if isinstance(f,int) and 0<=f<edl['total_frames']:
                start=f/fps
                flashes.append(f'drawbox=x=0:y=0:w=iw:h=ih:color=white@0.7:t=fill:enable=\'between(t,{start:.6f},{start+min(0.08,2/fps):.6f})\'')
    chain='[vconcat]'+(','.join(flashes)+',' if flashes else '')+'format=yuv420p[vout]'
    filt.append(chain)
    audio_idx = n
    if args.audio:
        ap=Path(args.audio)
        if not ap.is_file():raise ValueError('own audio file not found')
        cmd.extend(['-stream_loop','-1','-i',str(ap)])
    cmd.extend(['-filter_complex',';'.join(filt), '-map','[vout]'])
    if args.audio:
        cmd.extend(['-map',f'{audio_idx}:a:0','-c:a','aac','-b:a','192k'])
    else:cmd.append('-an')
    cmd.extend(['-c:v','libx264','-preset','ultrafast' if args.preview else 'medium',
                '-crf','28' if args.preview else '19','-pix_fmt','yuv420p',
                '-movflags','+faststart','-frames:v',str(edl['total_frames']),
                '-t',f'{edl["total_frames"]/fps:.9f}','-n',str(out)])
    proc=subprocess.run(cmd, capture_output=True,text=True,timeout=args.timeout)
    if proc.returncode != 0:
        raise ValueError('FFmpeg render failed: '+proc.stderr[-1800:])
    probe=subprocess.run(['ffprobe','-v','error','-select_streams','v:0','-show_entries',
                          'stream=nb_frames,width,height','-of','json',str(out)],capture_output=True,text=True,check=True)
    streams=json.loads(probe.stdout)['streams']
    frames=int(streams[0].get('nb_frames') or 0)
    if frames != edl['total_frames']:
        raise ValueError(f'Output failed frame verification: got {frames}, expected {edl["total_frames"]}')
    print(json.dumps({'output':str(out),'frames':frames,'width':args.width,'height':args.height,
                      'no_paid_generation':True,'unsupported_effects_preserved_in_edl':True},ensure_ascii=False,indent=2))
    return 0


def katana_commands(args):
    w = str(Path(args.workdir).expanduser())
    if '\n' in w or '\n' in args.url:
        raise ValueError('newlines not permitted in shell command generator')
    q = shlex.quote
    scripts='"$HF_WORKFLOWS/katana/scripts"'
    print('# COMMAND PLAN ONLY. Nothing here has been executed or pricing verified.')
    print('# Only analyze references you have permission to download/use. Never bypass site restrictions.')
    print('source "$HF_WORKFLOWS/katana/scripts/rr.sh"')
    print(f'W={q(w)}')
    commands=[f'python3 {scripts}/fetch_ref.py "$W" {q(args.url)}',
              f'python3 {scripts}/analyze_ref.py "$W" --review-size',
              f'python3 {scripts}/energy.py map "$W"',
              f'python3 {scripts}/audio.py extract "$W"',
              f'python3 {scripts}/audio.py beats "$W"',
              f'python3 {scripts}/audio.py cutsync "$W"',
              f'python3 {scripts}/audio.py words "$W"',
              f'python3 {scripts}/frames.py keyframes "$W" --which best']
    for c in commands:
        print(c)
    print('# Verify commands/locations against live --help; do NOT copy third-party media/audio into final video.')
    print('# Inspect JSON field names; use reel-dna extract with --duration/--fps as needed.')
    return 0


def compare(args):
    a,b=read_obj(args.reference),read_obj(args.ours)
    if a.get('schema')!='kosif.reel-dna.v1' or b.get('schema')!='kosif.reel-dna.v1':
        raise ValueError('requires two kosif.reel-dna.v1 recipes')
    da,db=a['reference_duration_s'],b['reference_duration_s']
    a_cuts=[x['frame']/a['fps']/da for x in a['cuts']]
    b_cuts=[x['frame']/b['fps']/db for x in b['cuts']]
    # For each reference cut find closest cut in normalized time; simple descriptive score, not perceptual QA.
    diffs=[round(min((abs(x-y)*da for y in b_cuts),default=da),3) for x in a_cuts]
    r={'reference_shots':len(a['shots']), 'ours_shots':len(b['shots']),
       'duration_diff_s':round(db-da,3), 'reference_cuts':len(a_cuts),'ours_cuts':len(b_cuts),
       'mean_nearest_cut_offset_s':round(sum(diffs)/len(diffs),3) if diffs else None,
       'cut_offset_samples_s':diffs,
       'note':'Cut-timing proxy ONLY, not energy/audio or visual match. No media analyzed in this step.'}
    print(json.dumps(r,ensure_ascii=False,indent=2));return 0


def library(args):
    """User-controlled local DNA recipe library; no cloud uploads or remote files."""
    folder=Path(args.library).expanduser()
    if args.operation=='add':
        source=read_obj(args.recipe)
        if source.get('schema')!='kosif.reel-dna.v1':
            raise ValueError('library only accepts kosif.reel-dna.v1 recipes')
        name=args.name.strip()
        if not name or len(name)>120 or len(args.description)>400:
            raise ValueError('name required (<=120 chars), description <=400 chars')
        tags=sorted({x.strip().casefold() for x in args.tags.split(',') if x.strip()})
        if any(len(t)>40 for t in tags):
            raise ValueError('tag must be <=40 chars')
        uid=hashlib.sha256((name.casefold()+'\0'+file_hash(args.recipe)).encode()).hexdigest()[:14]
        folder.mkdir(parents=True,exist_ok=True)
        dest=folder/(uid+'.json')
        write_obj(dest,{'schema':'kosif.reel-dna.library-item.v1','id':uid,'name':name,
                        'description':args.description,'tags':tags,'recipe':source})
        print(json.dumps({'added':uid,'file':str(dest),'tags':tags,'offline':True},ensure_ascii=False,indent=2))
        return 0
    if not folder.is_dir():
        print('[]' if args.json else 'Library empty (nothing saved yet)')
        return 0
    records=[]
    for p in sorted(folder.glob('*.json')):
        try:
            obj=read_obj(p)
            if obj.get('schema')!='kosif.reel-dna.library-item.v1':continue
            if args.operation=='show' and obj.get('id') != args.id:continue
            if args.operation=='list':
                if args.query and args.query.casefold() not in (obj.get('name','')+' '+obj.get('description','')+' '+' '.join(obj.get('tags',[]))).casefold():continue
                if args.tag and args.tag.casefold() not in obj.get('tags',[]):continue
            records.append(obj)
        except (OSError,ValueError):continue
    if args.operation=='show':
        if not records:raise ValueError('recipe id not found')
        print(json.dumps(records[0],ensure_ascii=False,indent=2));return 0
    if args.json:
        print(json.dumps([{'id':o['id'],'name':o['name'],'description':o['description'],'tags':o['tags'],
                           'shots':len(o['recipe'].get('shots',[]))} for o in records],ensure_ascii=False,indent=2))
    else:
        for o in records:print(f"{o['id']}  {o['name']}  shots={len(o['recipe'].get('shots',[]))}  tags={','.join(o['tags'])}")
        if not records:print('No matching recipes.')
    return 0


def doctor(args):
    print(json.dumps({'tool':'KOSIF Reel DNA','version':'1990',
          'ffmpeg':shutil.which('ffmpeg'),'ffprobe':shutil.which('ffprobe'),
          'higgsfield_connected':False,'katana_scripts_bundled':False,
          'can_extract_reported_schema':True,'can_render_owned_clips_locally':bool(shutil.which('ffmpeg') and shutil.which('ffprobe')),
          'cost':'No generation calls from this tool. External sandbox billing unverified.',
          'caveat':'Katana JSON schema not independently tested; field mismatches produce errors or warnings.'},
          ensure_ascii=False,indent=2));return 0


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    sub=parser.add_subparsers(dest='action',required=True)
    sub.add_parser('doctor')
    a=sub.add_parser('katana-commands');a.add_argument('--workdir',required=True);a.add_argument('--url',required=True)
    a=sub.add_parser('extract');a.add_argument('--analysis',required=True);a.add_argument('--energy');a.add_argument('--beats');a.add_argument('--cutsync');a.add_argument('--words');a.add_argument('--duration',type=float);a.add_argument('--fps');a.add_argument('--out',required=True)
    a=sub.add_parser('apply');a.add_argument('--recipe',required=True);a.add_argument('--clips',nargs='+',required=True);a.add_argument('--out',required=True)
    a=sub.add_parser('render');a.add_argument('--edl',required=True);a.add_argument('--out',required=True);a.add_argument('--width',type=int,default=540);a.add_argument('--height',type=int,default=960);a.add_argument('--audio');a.add_argument('--preview',action='store_true');a.add_argument('--timeout',type=int,default=240)
    a=sub.add_parser('compare');a.add_argument('--reference',required=True);a.add_argument('--ours',required=True)
    a=sub.add_parser('library'); b=a.add_subparsers(dest='operation',required=True)
    for op in ('add','list','show'):
        c=b.add_parser(op);c.add_argument('--library',default='~/.kosif/reel-dna')
        if op=='add':
            c.add_argument('--recipe',required=True);c.add_argument('--name',required=True)
            c.add_argument('--description',default='');c.add_argument('--tags',default='')
        if op=='list':
            c.add_argument('--query',default='');c.add_argument('--tag',default='');c.add_argument('--json',action='store_true')
        if op=='show':c.add_argument('id')
    args=parser.parse_args(argv)
    try:return {'doctor':doctor,'katana-commands':katana_commands,'extract':extract,
                'apply':apply,'render':render,'compare':compare,'library':library}[args.action](args)
    except (ValueError,OSError,subprocess.TimeoutExpired,subprocess.CalledProcessError) as exc:
        print('reel-dna: '+str(exc),file=sys.stderr);return 2

if __name__=='__main__':
    sys.exit(main())
