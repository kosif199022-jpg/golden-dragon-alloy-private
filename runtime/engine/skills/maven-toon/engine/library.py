"""Library preview sheets: python toon.py library OUTDIR [--sets a,b] [--moods day,night] [--cast]

Renders every set (or the ones named) in the given moods at the wide framing, plus a cast sheet with every
character type, so you can see what is in the kit before you write a storyboard. Sets bake once into OUTDIR/.cache.
"""
import os

import skia

W, H = 1080, 1920


def set_previews(outdir, names=None, moods=('day', 'night'), cast=None):
    from .sets import build_set, _registry
    from .scene import Shot, Layer
    from .director import cam_from_frame
    from .render import Runtime
    from .light import MOODS
    os.makedirs(outdir, exist_ok=True)
    cache = os.path.join(outdir, '.cache')
    names = names or sorted(_registry())
    paths = []
    for n in names:
        for md in moods:
            layers, meta = build_set(n, md, cache)
            if cast:
                L = Layer('actors', 1.0)
                for c in cast.get(n, []):
                    L.live.append(_actor(c))
                layers.append(L)
            shot = Shot(layers, md, lambda t: cam_from_frame((540, 960, 1920, 0.0)))
            s = shot.render(0.5, subframes=1)
            p = os.path.join(outdir, 'set_%s_%s.png' % (n, md))
            s.makeImageSnapshot().save(p, skia.kPNG)
            paths.append(p)
            print(p)
    return paths


def _actor(c):
    from .character import make, draw_character
    from .cast_iq import ANIMALS, draw_animal

    def fn(cv, t, mood):
        if c['type'] in ANIMALS:
            draw_animal(cv, c['type'], c['x'], c['y'], c.get('scale', 1.0), t, mood)
        else:
            draw_character(cv, make(c['type'], pose=c.get('pose', 'stand'), expr=c.get('expr', 'neutral')), c['x'], c['y'],
                           c.get('scale', 1.0), t, mood)
    return fn


def contact(paths, out, cols=6, w=320):
    """Tile PNGs into one labelled JPG."""
    from .text import draw_text
    imgs = [skia.Image.open(p) for p in paths]
    h = int(w * H / W)
    rows = (len(imgs) + cols - 1) // cols
    s = skia.Surface(cols * w, rows * (h + 34))
    cv = s.getCanvas(); cv.clear(skia.Color(0x1b, 0x12, 0x20))
    for i, (im, p) in enumerate(zip(imgs, paths)):
        x, y = (i % cols) * w, (i // cols) * (h + 34)
        cv.drawImageRect(im, skia.Rect.MakeXYWH(x, y, w, h), skia.SamplingOptions(skia.FilterMode.kLinear))
        lab = os.path.splitext(os.path.basename(p))[0].replace('set_', '').replace('_', ' / ', 1)
        draw_text(cv, lab, x + w / 2, y + h + 25, 20, '#e8e0f0')
    s.makeImageSnapshot().save(out, skia.kJPEG)
    return out


def cast_sheet(out):
    """Every character type standing, then a row of poses and expressions, plus the animals."""
    from .character import make, draw_character, ARCHETYPES
    from .cast_iq import draw_animal, ANIMALS
    from .text import draw_text
    names = list(ARCHETYPES)
    per = 13
    rows = (len(names) + per - 1) // per
    cw = 230
    Wt = cw * per
    Ht = rows * 640 + 700
    s = skia.Surface(Wt, Ht)
    cv = s.getCanvas(); cv.clear(skia.Color(0xd8, 0xdc, 0xea))
    for i, n in enumerate(names):
        x, y = cw / 2 + (i % per) * cw, 540 + (i // per) * 640
        draw_character(cv, make(n), x, y, 0.62, 0.3, 'day')
        draw_text(cv, n, x, y + 60, 28, '#2a2232')
    poses = ['stand', 'walk', 'run', 'point', 'shrug', 'arms_crossed', 'hips', 'hold', 'think', 'wave', 'cheer', 'sit']
    exprs = ['neutral', 'smug', 'angry', 'shocked', 'laughing', 'scared', 'sad', 'sly', 'happy', 'deadpan', 'happy', 'neutral']
    y = rows * 640 + 520
    for k, (p, e) in enumerate(zip(poses, exprs)):
        x = cw / 2 + k * cw
        draw_character(cv, make('teacher' if k % 2 else 'hajji', pose=p, expr=e), x, y, 0.56, 0.9 + k * 0.1, 'day')
        draw_text(cv, '%s / %s' % (p, e), x, y + 56, 22, '#2a2232')
    x = cw / 2 + 12 * cw
    draw_animal(cv, 'cat', x - 40, y, 0.7, 0.3, 'day')
    draw_text(cv, 'cat', x - 40, y + 56, 28, '#2a2232')
    s.makeImageSnapshot().save(out, skia.kPNG if out.endswith('.png') else skia.kJPEG)
    return out


def main(argv):
    out = argv[0] if argv and not argv[0].startswith('--') else 'library'
    opt = lambda k, d=None: argv[argv.index(k) + 1] if k in argv else d
    names = opt('--sets')
    names = names.split(',') if names else None
    moods = tuple(opt('--moods', 'day,night').split(','))
    os.makedirs(out, exist_ok=True)
    if '--cast-only' not in argv:
        paths = set_previews(out, names, moods)
        print(contact(paths, os.path.join(out, 'library_sets.jpg'), cols=len(moods) * 3 if len(moods) <= 2 else len(moods)))
    if '--cast' in argv or '--cast-only' in argv:
        print(cast_sheet(os.path.join(out, 'library_cast.jpg')))
    return 0
