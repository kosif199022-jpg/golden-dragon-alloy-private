"""Dua reel maker: the measured trending style, on backgrounds from a footage library.

Built from real work (the Sunday dua reel, 2026-11-22):
- fixed header (hijri day + month, day name, date with a yellow rule) and gold footer salawat
- one white dua line per shot, appearing and leaving with the words
- a new background for every line, cut in the gap between lines, soft transitions
- slow push-in or drift on each shot, no overlay effects on the footage
- optional colour match to a reference video (per-shot LUT)
- silent AAC track unless an audio file is given (a trend sound is added inside TikTok)

Plan (JSON):
  lines      ["text", ...] or [{"text", "t0", "t1", "tail", "tail_emoji"}]   (t0/t1 optional)
  fixed      {hijri_day, hijri_month, hijri_month_latin, day, date_a, date_b, footer, handle}
  library    folder with videos/ and photos/ (or a name from ~/.red-rose/libraries.json)
  clips      optional explicit list of files, one per line
  reference  optional video to match colour to
  audio      optional audio file;  seed  int;  exclude  [file names]

Needs Pillow (with raqm) and ffmpeg. Every write needs approve_write.
"""
from __future__ import annotations

import json
import random
import subprocess
from pathlib import Path

W, H, FPS, T, FADE = 720, 1280, 30, 0.5, 0.15
FONT_DIR = Path.home() / '.red-rose' / 'fonts'
LIBRARIES = Path.home() / '.red-rose' / 'libraries.json'
TRANSITIONS = ['smoothup', 'circleopen', 'smoothleft', 'dissolve', 'smoothdown', 'radial', 'smoothright']
GOLD_TOP, GOLD_BOT = (255, 236, 40), (238, 146, 0)
YELLOW, OUTLINE = (255, 214, 0, 255), (52, 26, 0, 255)
VIDEO_EXT, PHOTO_EXT = {'.mp4', '.mov', '.m4v', '.webm'}, {'.jpg', '.jpeg', '.png'}


# ----------------------------------------------------------------- timing

def timed_lines(lines):
    """Give every line t0/t1. Lines without times get a reading pace: 0.9 s + 0.38 s per word."""
    out, t = [], 0.4
    for ln in lines:
        item = {'text': ln} if isinstance(ln, str) else dict(ln)
        if not str(item.get('text', '')).strip():
            raise ValueError('empty dua line')
        if 't0' not in item or 't1' not in item:
            dur = max(1.3, 0.9 + 0.38 * len(item['text'].split()))
            item['t0'], item['t1'] = round(t, 2), round(t + dur, 2)
        if item['t1'] <= item['t0'] or (out and item['t0'] < out[-1]['t1']):
            raise ValueError(f"line times overlap or run backwards: {item['text']}")
        t = item['t1'] + 0.45
        out.append(item)
    if not out:
        raise ValueError('no dua lines')
    return out


def shot_plan_cut(lines):
    """Hard cuts in the gaps between lines (no overlap): for the spin transition."""
    cuts = [round((lines[k]['t1'] + lines[k + 1]['t0']) / 2, 3) for k in range(len(lines) - 1)]
    total = round(lines[-1]['t1'] + 0.35, 3)
    starts = [0.0] + cuts
    ends = cuts + [total]
    return [round(e - s, 3) for s, e in zip(starts, ends)], starts, total


def shot_plan(lines):
    cuts = [round((lines[k]['t1'] + lines[k + 1]['t0']) / 2, 3) for k in range(len(lines) - 1)]
    total = round(lines[-1]['t1'] + 0.35, 3)
    offsets = [0.0] + [max(0.0, c - T / 2) for c in cuts]
    ends = [o + T for o in offsets[1:]] + [total]
    return [round(e - o, 3) for o, e in zip(offsets, ends)], offsets, total


# ----------------------------------------------------------------- library

def resolve_library(lib):
    if not lib:
        raise ValueError('plan needs "library" (a folder, or a name in ~/.red-rose/libraries.json) or "clips"')
    p = Path(str(lib)).expanduser()
    if p.is_dir():
        return p
    if LIBRARIES.is_file():
        named = json.loads(LIBRARIES.read_text(encoding='utf-8')).get(str(lib))
        if named and Path(named).is_dir():
            return Path(named)
    raise FileNotFoundError(f'library not found: {lib}')


def _probe(path):
    r = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v', '-show_entries', 'stream=width,height',
                        '-show_entries', 'format=duration', '-of', 'json', str(path)], capture_output=True, text=True)
    try:
        j = json.loads(r.stdout)
        st = j['streams'][0]
        return st['width'], st['height'], float(j['format'].get('duration', 0) or 0)
    except (ValueError, KeyError, IndexError):
        return None


TEXT_SHARE_MAX = 0.004   # measured: clips above this carry burned-in text


def _text_flags(folder):
    """File names a library's _analysis.json (from its analysis run) marks as carrying on-screen text."""
    for p in (Path(folder) / '_analysis.json', Path(folder).parent / '_analysis.json'):
        if p.is_file():
            try:
                rows = json.loads(p.read_text(encoding='utf-8'))
                return {r['file'] for r in rows if r.get('text_share', 0) > TEXT_SHARE_MAX}
            except (ValueError, KeyError):
                return set()
    return set()


def scan_library(folder):
    """Usable vertical clips and photos in a library folder (searched recursively).
    Thumbnails (*_thumb.*) and clips with burned-in text (per _analysis.json) are skipped."""
    vids, pics = [], []
    texty = _text_flags(folder)
    for p in sorted(Path(folder).rglob('*')):
        ext = p.suffix.lower()
        if ext not in VIDEO_EXT and ext not in PHOTO_EXT:
            continue
        if '_thumb' in p.name or p.name in texty:
            continue
        info = _probe(p)
        if not info:
            continue
        w, h, dur = info
        if w < 480 or h / w < 1.3:
            continue
        (vids if ext in VIDEO_EXT else pics).append({'file': str(p), 'w': w, 'h': h, 'dur': round(dur, 2)})
    return vids, pics


def choose_clips(lengths, folder, seed=1, exclude=()):
    vids, pics = scan_library(folder)
    rng = random.Random(seed)
    ex = set(exclude)
    vids = [v for v in vids if Path(v['file']).name not in ex]
    pics = [p for p in pics if Path(p['file']).name not in ex]
    rng.shuffle(vids)
    rng.shuffle(pics)
    chosen = []
    for length in lengths:
        need = length + 0.7
        pick = next((v for v in vids if v['dur'] >= need), None)
        if pick:
            vids.remove(pick)
            start = round(rng.uniform(0.3, pick['dur'] - length - 0.3), 2)
            chosen.append({'file': pick['file'], 'kind': 'video', 'start': start})
        elif pics:
            chosen.append({'file': pics.pop()['file'], 'kind': 'photo', 'start': 0.0})
        else:
            raise ValueError(f'library has too few usable clips: need {len(lengths)}, got {len(chosen)}')
    return chosen


# ----------------------------------------------------------------- text layers

# font roles a plan can change by name ("fonts": {"line": "Meral Sans Black", ...}); values are looked up in
# the font library (rose.py fonts). The defaults are the measured trending look.
ROLE_DEFAULT = {'line': 'Lalezar-Regular.ttf', 'calligraphy': 'ArefRuqaa-Bold.ttf', 'title': 'Amiri-Bold.ttf',
                'latin': 'Cinzel.ttf'}
_FONT_OVERRIDE: dict = {}


def set_fonts(roles: dict | None) -> dict:
    """Resolve plan font names through the font library. Returns {role: path} actually used."""
    _FONT_OVERRIDE.clear()
    used = {}
    for role, name in (roles or {}).items():
        if role not in ROLE_DEFAULT:
            raise ValueError(f'unknown font role {role!r}; use one of {sorted(ROLE_DEFAULT)}')
        p = Path(str(name)).expanduser()
        if not p.is_file():
            if p.is_absolute():
                raise FileNotFoundError(f'approved font disappeared: {p}')
            import font_library_v35 as fl
            hit = fl.find_one(str(name))
            if not hit:
                raise FileNotFoundError(f'font not in the library: {name} (run: rose.py fonts find "{name}")')
            if hit.get('glyph_font'):
                raise ValueError(f'{hit["name"]} is a calligraphy-piece font (digits map to artwork), not for text lines')
            p = Path(hit['file'])
        _FONT_OVERRIDE[ROLE_DEFAULT[role]] = p
        used[role] = str(p)
    return used


def _fonts():
    from PIL import ImageFont
    raqm = ImageFont.Layout.RAQM

    def fnt(name, size, wght=None):
        path = _FONT_OVERRIDE.get(name) or FONT_DIR / name
        if not path.is_file():
            raise FileNotFoundError(f'font missing: {path}')
        f = ImageFont.truetype(str(path), size, layout_engine=raqm)
        if wght:
            try:
                f.set_variation_by_axes([wght])
            except Exception:
                pass
        return f

    def fit(name, text, width, wght=None, direction='rtl'):
        lo, hi, best = 10, 260, 10
        while lo <= hi:
            mid = (lo + hi) // 2
            if fnt(name, mid, wght).getlength(text, direction=direction) <= width:
                best, lo = mid, mid + 1
            else:
                hi = mid - 1
        return fnt(name, best, wght)
    return fnt, fit


def _draw(text, font, xy, anchor='mm', fill=(255, 255, 255, 255), gold=False, stroke=0, stroke_fill=OUTLINE,
          shadow=0, direction=None, embedded_color=False):
    from PIL import Image, ImageDraw, ImageFilter
    layer = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    kw = {'anchor': anchor}
    if direction:
        kw['direction'] = direction
    if shadow:
        sh = Image.new('L', (W, H), 0)
        ImageDraw.Draw(sh).text((xy[0] + 2, xy[1] + 3), text, font=font, fill=220, stroke_width=stroke + 2, **kw)
        layer = Image.composite(Image.new('RGBA', (W, H), (0, 0, 0, 255)), layer,
                                sh.filter(ImageFilter.GaussianBlur(shadow)))
    if stroke:
        ImageDraw.Draw(layer).text(xy, text, font=font, fill=stroke_fill, stroke_width=stroke,
                                   stroke_fill=stroke_fill, **kw)
    if gold:
        m = Image.new('L', (W, H), 0)
        ImageDraw.Draw(m).text(xy, text, font=font, fill=255, **kw)
        box = m.getbbox() or (0, 0, W, H)
        col = Image.new('RGBA', (1, H))
        for y in range(H):
            t = min(1.0, max(0.0, (y - box[1]) / max(1, box[3] - box[1])))
            col.putpixel((0, y), tuple(int(GOLD_TOP[i] + (GOLD_BOT[i] - GOLD_TOP[i]) * t) for i in range(3)) + (255,))
        grad = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        grad.paste(col.resize((W, H)), (0, 0), m)
        layer.alpha_composite(grad)
    else:
        ImageDraw.Draw(layer).text(xy, text, font=font, fill=fill, embedded_color=embedded_color, **kw)
    return layer


def base_layer(fixed):
    """Header and footer at the positions measured on the reference (720x1280)."""
    from PIL import Image, ImageDraw
    fnt, fit = _fonts()
    c = fixed or {}
    img = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    if c.get('hijri_day'):
        img.alpha_composite(_draw(c['hijri_day'], fnt('Amiri-Bold.ttf', 58), (122, 180), fill=(24, 214, 112, 255),
                                  stroke=2, stroke_fill=(0, 40, 16, 255), shadow=3))
    if c.get('hijri_month'):
        img.alpha_composite(_draw(c['hijri_month'], fit('ArefRuqaa-Bold.ttf', c['hijri_month'], 245), (232, 248),
                                  gold=True, stroke=3, shadow=4))
    if c.get('hijri_month_latin'):
        img.alpha_composite(_draw(c['hijri_month_latin'], fit('Cinzel.ttf', c['hijri_month_latin'], 212, 800, 'ltr'),
                                  (235, 314), fill=YELLOW, stroke=2, shadow=2))
    if c.get('day'):
        img.alpha_composite(_draw(c['day'], fit('Amiri-Bold.ttf', c['day'], 205), (522, 342), stroke=3,
                                  stroke_fill=(214, 150, 20, 255), shadow=5))
    a, b = c.get('date_a', ''), c.get('date_b', '')
    if a or b:
        f_t = fit('Cinzel.ttf', a + b, 258, 800, 'ltr')
        wa, wb = f_t.getlength(a), f_t.getlength(b)
        x0 = 510 - (wa + wb) / 2
        if a:
            img.alpha_composite(_draw(a, f_t, (x0, 437), anchor='lm', fill=YELLOW, stroke=2, shadow=3))
        if b:
            img.alpha_composite(_draw(b, f_t, (x0 + wa, 437), anchor='lm', stroke=2, shadow=3))
        rule = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(rule).line([(392, 469), (640, 469)], fill=YELLOW, width=4)
        img.alpha_composite(rule)
    if c.get('footer'):
        img.alpha_composite(_draw(c['footer'], fit('Amiri-Bold.ttf', c['footer'], 430), (360, 838), gold=True,
                                  stroke=4, shadow=6))
    if c.get('handle'):
        img.alpha_composite(_draw(c['handle'], fit('Cinzel.ttf', c['handle'], 210, 700, 'ltr'), (360, 700), shadow=3))
    return img


def line_layers(lines):
    from PIL import Image
    fnt, fit = _fonts()
    longest = max((ln['text'] for ln in lines), key=len)
    f = fit('Lalezar-Regular.ttf', longest, LINE_MAX_W)
    if f.size > LINE_MAX_PX:             # measured on the trending reels: the longest line nearly fills the width
        f = fnt('Lalezar-Regular.ttf', LINE_MAX_PX)
    emoji = Path(r'C:\Windows\Fonts\seguiemj.ttf')
    out = []
    for ln in lines:
        parts = [(ln['text'], f, False)]
        if ln.get('tail'):
            parts.append((ln['tail'], fnt('Amiri-Bold.ttf', int(f.size * 0.9)), False))
        if ln.get('tail_emoji') and emoji.is_file():
            from PIL import ImageFont
            parts.append((ln['tail_emoji'], ImageFont.truetype(str(emoji), int(f.size * 0.8),
                                                               layout_engine=ImageFont.Layout.RAQM), True))
        widths = [p[1].getlength(p[0], direction=None if p[2] else 'rtl') for p in parts]
        right = 362 + (sum(widths) + 12 * (len(parts) - 1)) / 2
        img = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        for (t, fo, emo), w in zip(parts, widths):
            if emo:
                img.alpha_composite(_draw(t, fo, (right - w, 640), anchor='lm', embedded_color=True))
            else:
                img.alpha_composite(_draw(t, fo, (right, 640), anchor='rm', stroke=2, stroke_fill=(20, 10, 0, 220),
                                          shadow=5, direction='rtl'))
            right -= w + 12
        out.append(img)
    return out


# ----------------------------------------------------------------- render

LINE_MAX_W, LINE_MAX_PX = 690, 74
SPIN_IN, MIRROR_OUT = 0.35, 0.25   # measured on the trending Monday-dua reel (2026-11-23)


def _spin_chain(i, clip, length, lut, first, last):
    """Trend transition, per shot: comes in spinning + zoomed + blurred and settles in 0.35 s;
    leaves with the bottom half mirrored from the top for the last 0.25 s. Shots meet with a hard cut."""
    base = _shot_chain(i, clip, length, lut).rsplit('[', 1)[0]     # same shot, without its output label
    steps = [base]
    if not first:
        z = f"pow(max(0,1-t/{SPIN_IN}),2)"
        steps.append(f"scale=w='trunc({W}*(1.02+0.38*{z})/2)*2':h=-2:eval=frame")
        steps.append(f"rotate=a='0.24*{z}':c=black")
        steps.append(f"crop={W}:{H}:(iw-{W})/2:(ih-{H})/2")
        steps.append(f"boxblur=luma_radius=14:chroma_radius=7:enable='lt(t,0.10)'")
        steps.append(f"boxblur=luma_radius=6:chroma_radius=3:enable='between(t,0.10,0.22)'")
    # per-frame zoom (scale eval=frame, h=-2) drifts the sample aspect ratio (seen: 4023:4024); concat needs
    # every input identical, so force size and SAR at the very end of each shot
    steps.append(f'scale={W}:{H},setsar=1,format=yuv420p')
    chain = ','.join(steps)
    if last:
        return chain + f'[v{i}]'
    t0 = max(0.0, length - MIRROR_OUT)
    return (chain + f',split[a{i}][b{i}];[b{i}]crop={W}:{H // 2}:0:0,vflip[m{i}];'
            f"[a{i}][m{i}]overlay=0:{H // 2}:enable='gte(t,{t0:.3f})',setsar=1[v{i}]")


def _shot_chain(i, clip, length, lut):
    if clip['kind'] == 'video':
        head = f"[{i}:v]trim=start={clip['start']}:duration={length + 0.1:.3f},setpts=PTS-STARTPTS,fps={FPS}"
    else:
        head = f"[{i}:v]fps={FPS}"
    chain = [head, f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}"]
    if lut:
        chain.append(f"lut3d=file={lut}")
    if i % 2 == 0:      # push-in
        chain.append(f"scale=w='trunc({W}*(1+0.06*t/{length})/2)*2':h=-2:eval=frame,crop={W}:{H}")
    else:               # drift
        cw = int(W * 1.08) // 2 * 2
        chain.append(f"scale={cw}:-2,crop={W}:{H}:x='(iw-{W})*t/{length}':y='(ih-{H})/2'")
    chain.append(f"trim=duration={length:.3f},setpts=PTS-STARTPTS,format=yuv420p,setsar=1[v{i}]")
    return ','.join(chain)


COLOUR_STYLES = Path(__file__).resolve().parent / 'agent' / 'colour_styles.json'


def colour_style(name):
    styles = json.loads(COLOUR_STYLES.read_text(encoding='utf-8')) if COLOUR_STYLES.is_file() else {}
    if name not in styles:
        raise ValueError(f'unknown colour style {name!r}; use one of {sorted(styles)} or give "reference"')
    return styles[name]


def build(plan: dict, out, work=None, approve_write: bool = False, storyboard_only: bool = False) -> dict:
    from rose_dua_gate_v69 import bind_v34
    lines = timed_lines(plan.get('lines') or [])
    spin = plan.get('transition') == 'spin'
    lengths, offsets, total = shot_plan_cut(lines) if spin else shot_plan(lines)
    verified = bind_v34(plan, lengths)  # fail before writes, font selection or implicit footage selection
    plan = dict(plan, fonts=verified['fonts'], audio=verified['audio'], clips=[dict(c,kind='video') for c in verified['clips']])
    fonts_used = set_fonts(plan.get('fonts'))
    n = len(lines)
    if plan.get('clips'):
        if len(plan['clips']) != n:
            raise ValueError(f'"clips" needs one file per line: {n} lines, {len(plan["clips"])} clips')
        clips = []
        for c in plan['clips']:
            c = {'file': c} if isinstance(c, str) else dict(c)
            if not Path(c['file']).is_file():
                raise FileNotFoundError(c['file'])
            c.setdefault('kind', 'photo' if Path(c['file']).suffix.lower() in PHOTO_EXT else 'video')
            c.setdefault('start', 0.3 if c['kind'] == 'video' else 0.0)
            clips.append(c)
    else:
        clips = choose_clips(lengths, resolve_library(plan.get('library')), plan.get('seed', 1),
                             plan.get('exclude', ()))
    out = Path(out).expanduser()
    work = Path(work).expanduser() if work else out.parent / (out.stem + '_work')
    report = {'lines': n, 'seconds': total, 'frames': round(total * FPS), 'size': [W, H],
              'fonts': fonts_used or 'defaults', 'colour': plan.get('style') or ('reference' if plan.get('reference') else 'as shot'),
              'shots': [{'line': ln['text'], 't0': ln['t0'], 't1': ln['t1'], 'clip': Path(c['file']).name,
                         'kind': c['kind'], 'start': c['start']} for ln, c in zip(lines, clips)]}
    targets = [str(work / 'storyboard.jpg')] if storyboard_only else [str(out), str(work)]
    if not approve_write:
        return {'ok': False, 'outcome': 'approval_required', 'would_write': targets,
                'hint': 'rerun with --approve-write after the owner says yes', **report}
    from PIL import Image
    work.mkdir(parents=True, exist_ok=True)
    base = base_layer(plan.get('fixed'))
    base.save(work / 'base.png')
    layers = line_layers(lines)
    for k, img in enumerate(layers, 1):
        img.save(work / f'line_{k}.png')

    # storyboard: one frame per shot with its text, to look at before rendering
    cols = min(7, n)
    sheet = Image.new('RGB', (cols * 184, ((n + cols - 1) // cols) * 324), 'black')
    for k, c in enumerate(clips):
        frame = work / '_f.png'
        seek = ['-ss', f"{c['start'] + lengths[k] / 2:.2f}"] if c['kind'] == 'video' else []
        subprocess.run(['ffmpeg', '-v', 'error', '-y', *seek, '-i', c['file'], '-frames:v', '1', '-vf',
                        f'scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}', str(frame)])
        im = Image.open(frame).convert('RGBA')
        im.alpha_composite(base)
        im.alpha_composite(layers[k])
        sheet.paste(im.convert('RGB').resize((180, 320)), ((k % cols) * 184, (k // cols) * 324))
    sheet.save(work / 'storyboard.jpg', quality=88)
    report['storyboard'] = str(work / 'storyboard.jpg')
    if storyboard_only:
        return {'ok': True, 'saved': [report['storyboard']], **report}

    luts = [None] * n
    style = colour_style(plan['style']) if plan.get('style') else None
    if plan.get('reference') or style:
        import reel_tools_v32 as rt
        (work / 'luts').mkdir(exist_ok=True)
        for k, c in enumerate(clips):
            if style:
                dur = lengths[k] if c['kind'] == 'video' else None
                rt.color_match(None, c['file'], work / 'luts' / f'shot_{k + 1}.cube', c['start'], dur,
                               strength=plan.get('strength', 0.8), approve_write=True, target=style)
                luts[k] = f'luts/shot_{k + 1}.cube'
                continue
            dur = lengths[k] if c['kind'] == 'video' else None
            rt.color_match(plan['reference'], c['file'], work / 'luts' / f'shot_{k + 1}.cube', c['start'], dur,
                           lift=plan.get('lift', 5.0), approve_write=True)
            luts[k] = f'luts/shot_{k + 1}.cube'

    inputs = []
    for k, c in enumerate(clips):
        if c['kind'] == 'photo':
            inputs += ['-loop', '1', '-framerate', str(FPS), '-t', f'{lengths[k] + 0.2:.3f}']
        inputs += ['-i', c['file']]
    for name in ['base.png'] + [f'line_{k}.png' for k in range(1, n + 1)]:
        inputs += ['-loop', '1', '-framerate', str(FPS), '-t', f'{total:.3f}', '-i', name]
    if spin:
        parts = [_spin_chain(i, c, lengths[i], luts[i], i == 0, i == n - 1) for i, c in enumerate(clips)]
        parts.append(''.join(f'[v{i}]' for i in range(n)) + f'concat=n={n}:v=1:a=0[xcat]')
        prev = 'xcat'
    else:
        parts = [_shot_chain(i, c, lengths[i], luts[i]) for i, c in enumerate(clips)]
        prev = 'v0'
        for i in range(1, n):
            kind = TRANSITIONS[(i - 1) % len(TRANSITIONS)]
            parts.append(f'[{prev}][v{i}]xfade=transition={kind}:duration={T}:offset={offsets[i]:.3f}[x{i}]')
            prev = f'x{i}'
    parts.append(f'[{n}:v]format=rgba[base]')
    parts.append(f'[{prev}][base]overlay=0:0:format=auto[o0]')
    for k, ln in enumerate(lines, 1):
        t0, t1 = max(0.0, ln['t0'] - FADE), ln['t1'] + FADE
        parts.append(f"[{n + k}:v]format=rgba,fade=t=in:st={t0:.3f}:d={FADE}:alpha=1,"
                     f"fade=t=out:st={ln['t1']:.3f}:d={FADE}:alpha=1[l{k}]")
        parts.append(f"[o{k - 1}][l{k}]overlay=0:0:format=auto:enable='between(t,{t0:.3f},{t1:.3f})'[o{k}]")
    parts.append(f'[o{n}]format=yuv420p[vout]')
    (work / 'filter.txt').write_text(';\n'.join(parts), encoding='utf-8')
    a_idx = 2 * n + 1
    if plan.get('audio'):
        inputs += ['-i', str(Path(plan['audio']).expanduser().resolve())]
    else:
        inputs += ['-f', 'lavfi', '-t', f'{total:.3f}', '-i', 'anullsrc=r=48000:cl=stereo']
    cmd = ['ffmpeg', '-v', 'error', '-y', *inputs, '-/filter_complex', 'filter.txt', '-map', '[vout]',
           '-map', f'{a_idx}:a', '-t', f'{total:.3f}', '-r', str(FPS), '-c:v', 'libx264', '-preset', 'medium',
           '-crf', '18', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k', '-ar', '48000',
           '-movflags', '+faststart', str(out.resolve())]
    out.parent.mkdir(parents=True, exist_ok=True)
    run = subprocess.run(cmd, cwd=work, capture_output=True, text=True)
    if run.returncode != 0 or not out.is_file():
        return {'ok': False, 'outcome': 'error', 'error': (run.stderr or 'ffmpeg failed')[:1200], **report}
    import reel_tools_v32 as rt
    flat = rt.flat_check(out)
    report.update(ok=flat['ok'], saved=[str(out)], flat_frames=flat['flat'],
                  audio='given file' if plan.get('audio') else 'silent AAC (add the sound inside TikTok)')
    return report
