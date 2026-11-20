"""Maven cast: Iraqi and Arab everyday characters for Maven Toon (hajji, hajjiya, mother, teacher, student,
schoolgirl, tea seller, farmer, doctor, footballer, shopkeeper, grandma) plus animals (cat, camel).

Same drawing rules as character.py: head radius 100, feet at (0, 0), y grows down, thick plum ink, flat colours with
real costume detail. character.py calls the hooks below for every hat, hair, costume part and prop it does not know.
Copyright (c) 2026 Maven. See rights/MAVEN-RIGHTS.txt.
"""
import math

import skia

from .paint import fill, stroke, ink, shade, mix, path_poly, path_smooth, rrect, ellipse, INK

# --------------------------------------------------------------------------------------------- archetypes
ARCHETYPES = {
    'hajji':      dict(torso='#f2f0ea', accent='#c8343c', pants='#e8e4da', shoes='#5a3a2a', hat='shmagh',
                       parts=['dishdasha'], prop='misbaha', beard='#e4e0d8', moustache=True, moustache_col='#d8d4d0',
                       gown=True, width=1.12),
    'hajjiya':    dict(torso='#2a2430', accent='#2a2430', pants='#2a2430', shoes='#2a2230', hat='hijab',
                       parts=['abaya_trim'], prop='tray', gown=True, width=1.14, hijab_col='#2a2430'),
    'mom':        dict(torso='#7a5aa8', accent='#e8a0b8', pants='#5a4080', shoes='#3a2a3a', hat='hijab',
                       parts=['dress_buttons'], prop='phone', gown=True, width=1.06, hijab_col='#e8a0b8'),
    'grandma':    dict(torso='#5a6a8a', accent='#f2f0ea', pants='#4a5a7a', shoes='#3a2a3a', hat='hijab',
                       parts=['cardigan'], prop='samoon', gown=True, width=1.12, hijab_col='#f2f0ea', glasses=True),
    'teacher':    dict(torso='#f2f0ea', accent='#3a4a7a', pants='#3a3e52', shoes='#3a2430', hat=None,
                       parts=['shirt_v', 'tie', 'waistcoat'], prop='pointer', hair='side_part', glasses=True,
                       moustache=True, moustache_col='#2e2430', width=1.08),
    'student':    dict(torso='#f4f2ee', accent='#3a6ab0', pants='#6a6e7a', shoes='#2a2230', hat=None,
                       parts=['collar', 'center_buttons', 'straps'], prop='book', hair='short_black', backpack='#3a6ab0',
                       width=0.98),
    'schoolgirl': dict(torso='#f4f2ee', accent='#2a3a6a', pants='#2a3a6a', shoes='#2a2230', hat='hijab',
                       parts=['pinafore'], prop='book', kid=True, width=0.92, hijab_col='#f4f2ee', backpack='#d84a6a',
                       gown=True),
    'chaichi':    dict(torso='#f2e6c8', accent='#8a2a2a', pants='#4a3a3a', shoes='#3a2430', hat='kufi',
                       parts=['tea_vest', 'sash'], prop='teapot', moustache=True, moustache_col='#2e2430', width=1.12),
    'fallah':     dict(torso='#b88a5a', accent='#e8dcc0', pants='#a07a4a', shoes='#5a3a2a', hat='turban',
                       parts=['dishdasha', 'sash'], prop='shovel', moustache=True, moustache_col='#2e2430', gown=True,
                       width=1.08),
    'doctor':     dict(torso='#f6f6f2', accent='#3aa0a0', pants='#3a7a8a', shoes='#2a2a3a', hat=None,
                       parts=['labcoat', 'shirt_v_blue', 'stethoscope', 'name_tag'], prop='clipboard', hair='side_part',
                       width=1.04, coat=True),
    'footballer': dict(torso='#2f9a5a', accent='#f4f2ee', pants='#f4f2ee', shoes='#2a2230', hat=None,
                       parts=['jersey'], prop='football', hair='short_black', width=1.0, number='10', shorts=True),
    'shopkeeper': dict(torso='#c8b090', accent='#2f6a5a', pants='#4a4a5a', shoes='#3a2430', hat=None,
                       parts=['shirt_v', 'waistcoat'], prop='money', hair='bald_ring', moustache=True,
                       moustache_col='#5a5a6a', width=1.2),
}

ANIMALS = ('cat', 'camel')


# --------------------------------------------------------------------------------------------- head covers
def _cover(x, hx, hy, col, fo, drape=170, chin=False, pattern=None, opening=(80, 84), open_front=False):
    """Head cloth (hijab / shmagh): a big soft shape around the head with the face cut out."""
    cv = x.cv
    wd = 1.0 if not chin else 0.86                               # a hijab sits closer to the head than a shmagh
    tp_ = 126 if not chin else 114
    outer = path_smooth([(hx - 120 * wd, hy + drape), (hx - 130 * wd, hy + 10), (hx - 104 * wd, hy - 92), (hx, hy - tp_),
                         (hx + 104 * wd, hy - 92), (hx + 130 * wd, hy + 10), (hx + 120 * wd, hy + drape),
                         (hx + (60 if chin else 96), hy + drape + (34 if chin else 10)),
                         (hx, hy + drape + (46 if chin else 0)),
                         (hx - (60 if chin else 96), hy + drape + (34 if chin else 10))])
    face = skia.Path()
    face.addOval(skia.Rect.MakeLTRB(hx + fo * 0.6 - opening[0], hy + 14 - opening[1],
                                    hx + fo * 0.6 + opening[0], hy + 14 + opening[1] * (0.9 if chin else 1.0)))
    if open_front:                                                # shmagh: the front hangs open below the face
        face.addRect(skia.Rect.MakeLTRB(hx + fo * 0.6 - opening[0] * 0.62, hy + 14, hx + fo * 0.6 + opening[0] * 0.62, hy + 600))
    cloth = skia.Op(outer, face, skia.PathOp.kDifference_PathOp)
    cv.drawPath(cloth, x.f(col))
    cv.save(); cv.clipPath(cloth, doAntiAlias=True)
    if pattern:                                                   # red check of a shmagh
        pc = x.g(pattern)
        for k in range(-14, 15):
            cv.drawLine(hx + k * 22 - 200, hy - 200, hx + k * 22 + 200, hy + 200, stroke(pc, 4.2, 0.85))
            cv.drawLine(hx + k * 22 + 200, hy - 200, hx + k * 22 - 200, hy + 200, stroke(pc, 4.2, 0.85))
    # soft folds and the shade side
    for sx in (-1, 1):
        cv.drawPath(path_smooth([(hx + sx * 100, hy + 20), (hx + sx * 112, hy + 90), (hx + sx * 104, hy + drape)], close=False),
                    stroke(x.g(shade(col, -0.25)), 5, 0.7))
    sh = skia.Path(); sh.addCircle(hx + 120, hy + 70, 150)
    cv.drawPath(sh, fill(x.g((0x4a, 0x30, 0x66)), 0.18))
    cv.restore()
    cv.drawPath(cloth, ink(6))
    return cloth


def hat(x, sp, hx, hy, h, wob):
    """Hats/head covers character.py does not know. Return True if drawn."""
    cv = x.cv
    fo = sp['face'] * 22
    if h == 'shmagh':
        _cover(x, hx, hy, '#f6f2ea', fo, drape=165, pattern=sp.get('accent', '#c8343c'), opening=(78, 88),
               open_front=True)
        for k, (dy, rx) in enumerate(((-82, 104), (-98, 98))):      # black double agal
            cv.drawPath(ellipse(hx, hy + dy, rx, 20), stroke(x.g('#1f1a24'), 13))
            cv.drawPath(ellipse(hx, hy + dy, rx, 20), stroke(x.g('#4a4250'), 3, 0.8))
        return True
    if h == 'hijab':
        col = sp.get('hijab_col', sp['accent'])
        cloth = _cover(x, hx, hy, col, fo, drape=100, chin=True, opening=(74, 80))
        band = path_smooth([(hx + fo * 0.6 - 76, hy - 20), (hx + fo * 0.6 - 40, hy - 70), (hx + fo * 0.6, hy - 80),
                            (hx + fo * 0.6 + 40, hy - 70), (hx + fo * 0.6 + 76, hy - 20)], close=False)
        cv.drawPath(band, stroke(x.g(shade(col, -0.18)), 7))      # the folded edge framing the face
        return True
    if h == 'kufi':
        c = '#f4f0e6'
        cap = skia.Path(); cap.addArc(skia.Rect.MakeLTRB(hx - 88, hy - 150, hx + 88, hy - 18), 180, 180); cap.close()
        cv.drawPath(cap, x.f(c))
        cv.save(); cv.clipPath(cap, doAntiAlias=True)
        for row in range(3):
            for k in range(-6, 7):
                cv.drawCircle(hx + k * 16 + (row % 2) * 8, hy - 96 + row * 18, 3.2, x.f('#c8b48a'))
        cv.restore()
        cv.drawPath(cap, ink(6))
        return True
    if h == 'turban':
        c = sp.get('accent', '#e8dcc0')
        for k in range(3):
            y0 = hy - 70 - k * 30
            w = 112 - k * 16
            band = path_smooth([(hx - w, y0 + 14), (hx - w + 8, y0 - 18), (hx, y0 - 30 + k * 2), (hx + w - 8, y0 - 18),
                                (hx + w, y0 + 14), (hx, y0 + 4)])
            cv.drawPath(band, x.f(shade(c, -0.06 * k))); cv.drawPath(band, ink(5))
        tail = path_smooth([(hx - 96, hy - 60), (hx - 132, hy - 10), (hx - 124, hy + 60), (hx - 104, hy + 50), (hx - 108, hy - 20)])
        cv.drawPath(tail, x.f(c)); cv.drawPath(tail, ink(4.5))
        return True
    return False


def hair(x, sp, hx, hy, h):
    cv = x.cv
    fo = sp['face'] * 20
    R = 100
    if h in ('side_part', 'short_black'):
        c = '#2e2430'
        cv.save(); cv.clipPath(ellipse(hx, hy, R, R), doAntiAlias=True)
        if h == 'side_part':
            p = path_smooth([(hx - 112, hy - 6), (hx - 98, hy - 92), (hx - 10, hy - 120), (hx + 90, hy - 98), (hx + 112, hy - 20),
                             (hx + 76, hy - 50), (hx + 20 + fo, hy - 70), (hx - 30 + fo, hy - 62), (hx - 84, hy - 34)])
        else:
            p = path_smooth([(hx - 110, hy - 24), (hx - 84, hy - 98), (hx, hy - 116), (hx + 88, hy - 96), (hx + 110, hy - 30),
                             (hx + 70, hy - 60), (hx + fo, hy - 66), (hx - 70, hy - 56)])
        cv.drawPath(p, x.f(c))
        cv.drawPath(path_smooth([(hx - 50, hy - 92), (hx - 4, hy - 106), (hx + 44, hy - 96)], close=False), stroke(x.g('#5a4a60'), 4))
        cv.drawPath(p, ink(5))
        cv.restore()
        if h == 'side_part':
            cv.drawLine(hx - 34 + fo, hy - 110, hx - 26 + fo, hy - 64, stroke(x.g('#5a4a60'), 3))
        return True
    if h == 'bald_ring':
        c = '#5a5a6a'
        for sx in (-1, 1):
            tp = path_smooth([(hx + sx * 96, hy - 44), (hx + sx * 110, hy - 4), (hx + sx * 100, hy + 26), (hx + sx * 86, hy - 6)])
            cv.drawPath(tp, x.f(c)); cv.drawPath(tp, ink(4.5))
        cv.drawPath(ellipse(hx - 40, hy - 70, 18, 10), fill('#ffffff', 0.5))
        return True
    return False


# --------------------------------------------------------------------------------------------- costume parts
def back(x, sp, sw, hw, top, hem):
    """Things behind the torso (drawn before it)."""
    cv = x.cv
    if sp.get('backpack'):
        c = sp['backpack']
        bp = rrect(-hw - 34, top + 22, 86, 150, 26)
        cv.drawPath(bp, x.f(c)); cv.drawPath(bp, ink(5))
        cv.drawPath(rrect(-hw - 28, top + 96, 60, 52, 12), x.f(shade(c, -0.15))); cv.drawPath(rrect(-hw - 28, top + 96, 60, 52, 12), ink(3.5))


def part(x, p, sp, tp, sw, hw, top, hem, fo):
    cv, g = x.cv, x.g
    T, A = sp['torso'], sp['accent']
    mid = (top + hem) / 2
    if p == 'dishdasha':
        cv.drawPath(path_smooth([(fo - 30, top - 2), (fo, top + 14), (fo + 30, top - 2)], close=False), ink(4))
        cv.drawLine(fo, top + 12, fo, top + 120, ink(3))
        for k in range(3):
            cv.drawCircle(fo + 6, top + 30 + k * 30, 4.5, x.f(shade(T, -0.2))); cv.drawCircle(fo + 6, top + 30 + k * 30, 4.5, ink(2))
        for sx in (-1, 1):
            cv.drawPath(path_smooth([(sx * 30 + fo, mid), (sx * 40 + fo, hem - 60), (sx * 52 + fo, hem)], close=False),
                        stroke(g(shade(T, -0.12)), 3.5))
    elif p == 'abaya_trim':
        for sx in (-1, 1):
            cv.drawLine(fo + sx * 12, top + 6, fo + sx * 22, hem, stroke(g('#4a4256'), 6))
            for k in range(8):
                cv.drawCircle(fo + sx * (13 + k * 1.2), top + 30 + k * ((hem - top - 40) / 8), 3, x.f('#c8a050'))
    elif p == 'dress_buttons':
        cv.drawLine(fo, top + 10, fo, mid + 40, ink(3))
        for k in range(4):
            cv.drawCircle(fo + 6, top + 34 + k * 30, 5, x.f(A)); cv.drawCircle(fo + 6, top + 34 + k * 30, 5, ink(2.2))
        cv.save(); cv.clipPath(tp, doAntiAlias=True)
        cv.drawRect(skia.Rect.MakeLTRB(-200, mid + 10, 200, mid + 26), x.f(shade(T, -0.2)))
        cv.restore()
    elif p == 'cardigan':
        for sx in (-1, 1):
            pn = path_poly([(fo + sx * 4, top + 40), (sx * (sw + 6), top), (sx * (hw + 8), hem + 4), (fo + sx * 10, hem + 4)])
            cv.drawPath(pn, x.f(shade(T, -0.12))); cv.drawPath(pn, ink(3.5))
        for k in range(4):
            cv.drawCircle(fo + 14, top + 70 + k * 34, 5, x.f('#e6c25a')); cv.drawCircle(fo + 14, top + 70 + k * 34, 5, ink(2))
    elif p == 'waistcoat':
        c = A
        for sx in (-1, 1):
            pn = path_poly([(fo + sx * 6, top + 64), (sx * (sw - 2), top + 2), (sx * (hw + 4), hem - 10), (fo + sx * 12, hem + 8)])
            cv.drawPath(pn, x.f(c)); cv.drawPath(pn, ink(4))
        for k in range(4):
            cv.drawCircle(fo + 16, top + 90 + k * 26, 5, x.f('#e6c25a')); cv.drawCircle(fo + 16, top + 90 + k * 26, 5, ink(2))
        cv.drawPath(rrect(fo - hw * 0.62, top + 110, 26, 6, 2), ink(2.5))
    elif p == 'straps':
        c = sp.get('backpack', A)
        for sx in (-1, 1):
            cv.drawLine(sx * (sw - 10) + fo * 0.3, top + 2, sx * (sw - 4) + fo * 0.3, top + 120, stroke(g(c), 13))
            cv.drawLine(sx * (sw - 10) + fo * 0.3, top + 2, sx * (sw - 4) + fo * 0.3, top + 120, ink(2.5))
    elif p == 'pinafore':
        pf = path_poly([(fo - 40, top + 60), (fo + 40, top + 60), (hw + 6, hem + 4), (-hw - 6, hem + 4)])
        cv.drawPath(pf, x.f(A)); cv.drawPath(pf, ink(4))
        for sx in (-1, 1):
            cv.drawLine(fo + sx * 34, top + 62, fo + sx * 40, top + 2, stroke(g(A), 12)); cv.drawLine(fo + sx * 34, top + 62, fo + sx * 40, top + 2, ink(2.5))
        cv.drawPath(path_smooth([(fo - 22, top - 2), (fo, top + 12), (fo + 22, top - 2)], close=False), ink(3.5))
    elif p == 'tea_vest':
        for sx in (-1, 1):
            pn = path_poly([(fo + sx * 14, top + 30), (sx * (sw - 4), top + 2), (sx * (hw + 2), mid + 30), (fo + sx * 20, mid + 50)])
            cv.drawPath(pn, x.f(A)); cv.drawPath(pn, ink(4))
            cv.drawPath(path_poly([(fo + sx * 20, top + 40), (sx * (sw - 10), top + 14), (sx * (hw - 6), mid + 22)], close=False),
                        stroke(g('#e6c25a'), 3))
    elif p == 'sash':
        sc = '#d8a040' if T != '#d8a040' else '#c8343c'
        cv.save(); cv.clipPath(tp, doAntiAlias=True)
        cv.drawRect(skia.Rect.MakeLTRB(-200, mid + 30, 200, mid + 58), x.f(sc))
        for k in range(-10, 11):
            cv.drawLine(k * 14, mid + 30, k * 14 + 8, mid + 58, stroke(g(shade(sc, -0.25)), 2))
        cv.drawLine(-200, mid + 30, 200, mid + 30, ink(3)); cv.drawLine(-200, mid + 58, 200, mid + 58, ink(3))
        cv.restore()
    elif p == 'stethoscope':
        tube = skia.Path(); tube.moveTo(-sw + 8, top + 4); tube.cubicTo(-sw + 4, top + 80, fo - 4, top + 96, fo + 6, top + 110)
        tube.moveTo(sw - 8, top + 4); tube.cubicTo(sw - 4, top + 70, fo + 30, top + 90, fo + 6, top + 110)
        cv.drawPath(tube, stroke(g('#3a3a4a'), 7)); cv.drawPath(tube, stroke(g('#6a6a7a'), 2.5, 0.7))
        cv.drawCircle(fo + 6, top + 120, 13, x.f('#c8ccd8')); cv.drawCircle(fo + 6, top + 120, 13, ink(3.5))
    elif p == 'jersey':
        from .text import draw_text
        cv.drawPath(path_poly([(fo - 28, top - 4), (fo + 28, top - 4), (fo, top + 40)]), x.f(A))
        cv.drawPath(path_poly([(fo - 28, top - 4), (fo, top + 40), (fo + 28, top - 4)], close=False), ink(3.5))
        cv.save(); cv.clipPath(tp, doAntiAlias=True)
        for sx in (-1, 1):
            cv.drawRect(skia.Rect.MakeLTRB(sx * hw - 14, top, sx * hw + 14, hem), x.f(A))
        cv.restore()
        draw_text(cv, str(sp.get('number', '10')), fo + 6, top + 122, 64, x.g(A), outline=INK, ow=5)
    else:
        return False
    return True


# --------------------------------------------------------------------------------------------- props
def istikan(x, cx, cy, s=1.0):
    """Iraqi tea glass on a saucer, centred at the saucer."""
    cv = x.cv
    cv.drawPath(ellipse(cx, cy, 30 * s, 8 * s), x.f('#f4f0ea')); cv.drawPath(ellipse(cx, cy, 30 * s, 8 * s), ink(3 * s))
    gl = path_smooth([(cx - 16 * s, cy - 62 * s), (cx - 10 * s, cy - 32 * s), (cx - 14 * s, cy - 4 * s), (cx + 14 * s, cy - 4 * s),
                      (cx + 10 * s, cy - 32 * s), (cx + 16 * s, cy - 62 * s)])
    cv.drawPath(gl, fill(x.g('#fff4e0'), 0.55))
    tea = path_smooth([(cx - 12 * s, cy - 48 * s), (cx - 10 * s, cy - 32 * s), (cx - 13 * s, cy - 6 * s), (cx + 13 * s, cy - 6 * s),
                       (cx + 10 * s, cy - 32 * s), (cx + 12 * s, cy - 48 * s)])
    cv.drawPath(tea, x.f('#b8402a'))
    cv.drawLine(cx - 8 * s, cy - 44 * s, cx - 6 * s, cy - 14 * s, stroke('#ffffff', 2.5 * s, 0.6))
    cv.drawPath(gl, ink(3.2 * s))
    t = x.t
    for k in (-6, 6):
        st = skia.Path(); st.moveTo(cx + k * s, cy - 70 * s)
        st.quadTo(cx + (k + 8 * math.sin(t * 3 + k)) * s, cy - 88 * s, cx + k * s, cy - 104 * s)
        cv.drawPath(st, stroke(x.g('#ffffff'), 3 * s, 0.55))


def prop(x, kind, ang):
    """Props held in the front hand. The canvas is at the hand, rotated so +y runs along the forearm."""
    cv = x.cv
    if kind == 'misbaha':
        cv.rotate(ang)                                            # beads hang straight down
        sw_ = math.sin(x.t * 2.3) * 6
        for k in range(16):
            a = k / 16 * 2 * math.pi
            bx, by = math.sin(a) * 16 + sw_ * (1 - math.cos(a)) / 2, 34 + 30 - math.cos(a) * 30
            cv.drawCircle(bx, by, 6, x.f('#2f8a6a')); cv.drawCircle(bx, by, 6, ink(2))
        cv.drawLine(sw_, 94, sw_ * 1.2, 118, stroke(x.g('#e6c25a'), 6))
    elif kind == 'teapot':
        cv.rotate(ang)
        body = path_smooth([(-34, 30), (-40, 64), (-24, 90), (24, 90), (40, 64), (34, 30)])
        cv.drawPath(path_smooth([(34, 46), (66, 36), (82, 14), (74, 10), (58, 32), (36, 34)]), x.f('#d8dce4'))
        cv.drawPath(path_smooth([(34, 46), (66, 36), (82, 14), (74, 10), (58, 32), (36, 34)]), ink(3.5))
        cv.drawPath(body, x.f('#d8dce4')); cv.drawPath(path_smooth([(-30, 54), (0, 62), (30, 54)], close=False), stroke(x.g('#3a6ab0'), 5))
        cv.drawPath(body, ink(4))
        cv.drawPath(ellipse(0, 28, 26, 9), x.f('#c8ccd8')); cv.drawPath(ellipse(0, 28, 26, 9), ink(3.5))
        cv.drawCircle(0, 16, 7, x.f('#e6c25a')); cv.drawCircle(0, 16, 7, ink(3))
        cv.drawPath(path_smooth([(-30, 30), (-6, -4), (6, -4), (30, 30)], close=False), ink(5))
    elif kind == 'tray':
        cv.rotate(ang)
        cv.translate(36, 10)
        tr = ellipse(0, 0, 92, 16)
        cv.drawPath(tr, x.f('#d8b048')); cv.drawPath(ellipse(0, -3, 80, 11), x.f('#e8c868')); cv.drawPath(tr, ink(4))
        istikan(x, -36, -4, 0.8); istikan(x, 30, -6, 0.8)
    elif kind == 'book':
        cv.drawPath(rrect(-30, 4, 60, 80, 6), x.f('#c8343c')); cv.drawPath(rrect(-30, 4, 60, 80, 6), ink(4))
        cv.drawRect(skia.Rect.MakeLTRB(-24, 8, -18, 80), x.f('#8a2a2a'))
        cv.drawPath(rrect(-12, 26, 32, 14, 3), x.f('#f2e6c8'))
    elif kind == 'pointer':
        cv.drawPath(rrect(-4, -10, 8, 170, 4), x.f('#b07a45')); cv.drawPath(rrect(-4, -10, 8, 170, 4), ink(3))
        cv.drawPath(rrect(-5, 150, 10, 22, 4), x.f('#f4f0ea')); cv.drawPath(rrect(-5, 150, 10, 22, 4), ink(3))
    elif kind == 'shovel':
        cv.drawPath(rrect(-6, -90, 12, 230, 5), x.f('#a07040')); cv.drawPath(rrect(-6, -90, 12, 230, 5), ink(3.5))
        bl = path_smooth([(-30, 136), (30, 136), (34, 190), (0, 214), (-34, 190)])
        cv.drawPath(bl, x.f('#9aa2b4')); cv.drawPath(bl, ink(4))
    elif kind == 'football':
        cv.rotate(ang)
        ball(cv, x, 0, 46, 38)
    elif kind == 'clipboard':
        cv.rotate(ang)
        cv.drawPath(rrect(-8, 10, 76, 100, 6), x.f('#b07a45')); cv.drawPath(rrect(-8, 10, 76, 100, 6), ink(4))
        cv.drawPath(rrect(0, 22, 60, 82, 3), x.f('#f8f6f0'))
        for k in range(4):
            cv.drawLine(8, 40 + k * 16, 52 - (k % 2) * 14, 40 + k * 16, stroke(x.g('#8a8090'), 4))
        cv.drawPath(rrect(18, 4, 24, 14, 4), x.f('#c8ccd8')); cv.drawPath(rrect(18, 4, 24, 14, 4), ink(3))
    elif kind == 'phone':
        cv.rotate(ang)
        cv.drawPath(rrect(-4, -6, 44, 80, 9), x.f('#2a2232')); cv.drawPath(rrect(-4, -6, 44, 80, 9), ink(3.5))
        cv.drawPath(rrect(1, 0, 34, 66, 5), fill(x.g('#8fd0ff')))
    elif kind == 'samoon':                                         # Iraqi diamond-shaped bread
        cv.rotate(ang)
        sm = path_smooth([(-10, 40), (30, 14), (80, 30), (40, 60)])
        cv.drawPath(sm, x.f('#e0a050')); cv.drawPath(path_smooth([(4, 38), (34, 28), (64, 34)], close=False), stroke(x.g('#f4d090'), 4))
        cv.drawPath(sm, ink(4))
    elif kind == 'money':
        cv.rotate(ang)
        for k in range(3):
            cv.save(); cv.rotate(-8 + k * 8)
            cv.drawPath(rrect(-10, 10, 80, 40, 4), x.f('#7ab07a')); cv.drawPath(rrect(-10, 10, 80, 40, 4), ink(3))
            cv.drawCircle(30, 30, 10, stroke(x.g('#3a6a3a'), 3))
            cv.restore()
    else:
        return False
    return True


def ball(cv, x, cx, cy, r):
    b = ellipse(cx, cy, r, r)
    cv.drawPath(b, x.f('#f8f8f4'))
    cv.save(); cv.clipPath(b, doAntiAlias=True)
    rot = x.t * 2
    for k in range(5):
        a = rot + k * 2 * math.pi / 5
        px, py = cx + math.cos(a) * r * 0.82, cy + math.sin(a) * r * 0.82
        pts = [(px + math.cos(a + j * 1.2566) * r * 0.28, py + math.sin(a + j * 1.2566) * r * 0.28) for j in range(5)]
        cv.drawPath(path_poly(pts), x.f('#2a2232'))
    cv.drawPath(path_poly([(cx + math.cos(rot + j * 1.2566 + 0.63) * r * 0.3, cy + math.sin(rot + j * 1.2566 + 0.63) * r * 0.3) for j in range(5)]), x.f('#2a2232'))
    cv.restore()
    cv.drawPath(b, ink(max(3, r * 0.1)))


# --------------------------------------------------------------------------------------------- hold items (acts "hold")
class _HoldCtx:
    def __init__(self, cv, t, mood):
        from .character import _g
        from .paint import rgb
        self.cv, self.t, self.mood = cv, t, mood
        self.g = lambda c: _g(rgb(c), mood)
        self.f = lambda c, a=1.0: fill(self.g(c), a)


def hold_item(name):
    """'tea', 'tray', 'teapot', 'book', 'phone', 'ball', 'samoon', 'money', 'dates', 'misbaha' -> fn(cv, t, mood)."""
    def fn(cv, t, md):
        x = _HoldCtx(cv, t, md)
        if name == 'tea':
            istikan(x, 0, -6, 1.1)
        elif name == 'ball':
            ball(cv, x, 0, -46, 44)
        elif name == 'dates':
            cv.drawPath(ellipse(0, -10, 60, 16), x.f('#c89a5a')); cv.drawPath(ellipse(0, -10, 60, 16), ink(4))
            for k in range(7):
                dx, dy = -40 + k * 13, -22 - (k % 2) * 10
                cv.drawPath(ellipse(dx, dy, 9, 14), x.f('#6a2a1a')); cv.drawPath(ellipse(dx, dy, 9, 14), ink(2.5))
        else:
            cv.save(); cv.translate(0, -60)
            prop(x, name, 0)
            cv.restore()
    return fn if name in ('tea', 'tray', 'teapot', 'book', 'phone', 'ball', 'samoon', 'money', 'dates', 'misbaha') else None


# --------------------------------------------------------------------------------------------- animals
def draw_cat(cv, x, y, scale, t, mood_name='day', dir=1, expr='happy', col='#e8913a', pose='stand'):
    """A round orange street cat (~230 units tall, a character head is 200 wide). Feet at (x, y).
    pose: stand | sit | walk. expr: happy | shocked | angry | sad | sly."""
    from .light import grade_color, MOODS as _M
    m = _M[mood_name]
    g = lambda c: grade_color(c, m)
    W = 6.0
    br = math.sin(t * 2 * math.pi / 2.4)
    cv.save(); cv.translate(x, y); cv.scale(scale * dir, scale)
    cv.translate(0, br * 1.5)
    sit = pose == 'sit'
    walk = pose == 'walk'
    ph = t * 2 * math.pi * 1.8
    # tail
    sway = math.sin(t * 2.2) * 14
    tail = skia.Path(); tail.moveTo(-70, -60 if not sit else -30)
    tail.cubicTo(-150, -70 + sway, -150, -190 + sway, -110 + sway * 0.5, -210)
    cv.drawPath(tail, stroke(INK, 22 + W * 1.6)); cv.drawPath(tail, stroke(g(col), 22))
    # legs
    for lx, sh, k in ((-50, -0.15, 0), (36, -0.15, 1), (-30, 0.0, 1), (56, 0.0, 0)):
        lift = (max(0, math.sin(ph + k * math.pi)) * 14) if walk else 0
        h = 40 if sit and lx > 0 else 70
        leg = rrect(lx - 14, -h - lift, 28, h, 13)
        cv.drawPath(leg, fill(g(shade(col, sh)))); cv.drawPath(leg, ink(W * 0.8))
        cv.drawPath(ellipse(lx + 4, -4 - lift, 20, 10), fill(g('#f6efe6'))); cv.drawPath(ellipse(lx + 4, -4 - lift, 20, 10), ink(W * 0.7))
    # body
    body = ellipse(0, -110 if not sit else -96, 92, 64 if not sit else 74)
    cv.drawPath(body, fill(g(col)))
    cv.save(); cv.clipPath(body, doAntiAlias=True)
    for k in range(4):
        cv.drawPath(path_smooth([(-60 + k * 26, -170), (-50 + k * 26, -120), (-62 + k * 26, -80)], close=False), stroke(g(shade(col, -0.25)), 9))
    cv.drawPath(ellipse(40, -80, 44, 30), fill(g('#f6efe6')))
    cv.drawPath(ellipse(-50, -70, 90, 40), fill(g('#3a2a5a'), 0.16))
    cv.restore()
    cv.drawPath(body, ink(W))
    # head
    hx, hy = 70, -186 if not sit else -196
    for sx in (-1, 1):                                       # ears
        ear = path_poly([(hx + sx * 22, hy - 52), (hx + sx * 54, hy - 102), (hx + sx * 66, hy - 30)])
        cv.drawPath(ear, fill(g(col))); cv.drawPath(path_poly([(hx + sx * 30, hy - 52), (hx + sx * 52, hy - 86), (hx + sx * 58, hy - 42)]), fill(g('#f4a0a8')))
        cv.drawPath(ear, ink(W * 0.9))
    head = ellipse(hx, hy, 74, 64)
    cv.drawPath(head, fill(g(col)))
    cv.save(); cv.clipPath(head, doAntiAlias=True)
    for k in (-1, 0, 1):
        cv.drawLine(hx + k * 18, hy - 66, hx + k * 14, hy - 38, stroke(g(shade(col, -0.25)), 7))
    cv.drawPath(ellipse(hx + 6, hy + 30, 46, 30), fill(g('#f6efe6')))
    cv.restore()
    cv.drawPath(head, ink(W))
    blink = (t * 0.31 + 0.4) % 1.0 < 0.04
    for sx in (-1, 1):
        ex, ey = hx + sx * 26 + 6, hy - 6
        if blink or expr == 'sly':
            cv.drawLine(ex - 11, ey, ex + 11, ey, ink(5))
        elif expr == 'shocked':
            cv.drawCircle(ex, ey, 15, fill('#ffffff')); cv.drawCircle(ex, ey, 15, ink(4)); cv.drawCircle(ex, ey, 5, fill(INK))
        else:
            cv.drawPath(ellipse(ex, ey, 10, 14), fill(INK)); cv.drawCircle(ex - 3, ey - 5, 3.5, fill('#ffffff'))
        if expr == 'angry':
            cv.save(); cv.translate(ex, ey - 22); cv.rotate(-sx * 22); cv.drawLine(-12, 0, 12, 0, ink(6)); cv.restore()
        if expr == 'sad':
            cv.save(); cv.translate(ex, ey - 22); cv.rotate(sx * 20); cv.drawLine(-12, 0, 12, 0, ink(6)); cv.restore()
    cv.drawPath(path_poly([(hx, hy + 16), (hx + 12, hy + 8), (hx - 12, hy + 8)]), fill(g('#e86a7a')))
    mo = skia.Path()
    if expr == 'shocked':
        mo.addOval(skia.Rect.MakeLTRB(hx - 8, hy + 22, hx + 8, hy + 40))
        cv.drawPath(mo, fill(g('#7a2a3a')))
    else:
        mo.moveTo(hx - 18, hy + 22); mo.quadTo(hx - 8, hy + 32, hx, hy + 20); mo.quadTo(hx + 8, hy + 32, hx + 18, hy + 22)
    cv.drawPath(mo, ink(4))
    for sx in (-1, 1):                                       # whiskers
        for k in (-1, 1):
            cv.drawLine(hx + sx * 36, hy + 20 + k * 6, hx + sx * 86, hy + 14 + k * 12, ink(2.5))
    cv.restore()


def draw_camel(cv, x, y, scale, t, mood_name='day', dir=1, expr='happy', col='#d8a868', pose='stand'):
    """A friendly one-hump camel (~520 units tall). Feet at (x, y). pose: stand | walk | sit."""
    from .light import grade_color, MOODS as _M
    m = _M[mood_name]
    g = lambda c: grade_color(c, m)
    W = 6.0
    cv.save(); cv.translate(x, y); cv.scale(scale * dir, scale)
    walk, sit = pose == 'walk', pose == 'sit'
    ph = t * 2 * math.pi * 1.2
    br = math.sin(t * 2 * math.pi / 3.0)
    by = -250 if not sit else -110
    # legs (thin, knobbly knees)
    if not sit:
        for lx, sh, k in ((-110, -0.15, 0), (70, -0.15, 1), (-80, 0.0, 1), (100, 0.0, 0)):
            sw_ = math.sin(ph + k * math.pi) * (16 if walk else 0)
            knee = (lx + sw_ * 0.5, -120)
            cv.drawPath(path_poly([(lx - 14, by + 30), (lx + 14, by + 30), (knee[0] + 12, knee[1]), (knee[0] - 12, knee[1])]), fill(g(shade(col, sh))))
            cv.drawPath(path_poly([(knee[0] - 10, knee[1]), (knee[0] + 10, knee[1]), (lx + sw_ + 9, -10), (lx + sw_ - 9, -10)]), fill(g(shade(col, sh))))
            cv.drawPath(path_poly([(lx - 14, by + 30), (knee[0] - 12, knee[1]), (lx + sw_ - 9, -10)], close=False), ink(W * 0.8))
            cv.drawPath(path_poly([(lx + 14, by + 30), (knee[0] + 12, knee[1]), (lx + sw_ + 9, -10)], close=False), ink(W * 0.8))
            cv.drawCircle(knee[0], knee[1], 14, fill(g(shade(col, sh - 0.05)))); cv.drawCircle(knee[0], knee[1], 14, ink(W * 0.6))
            cv.drawPath(ellipse(lx + sw_ + 4, -6, 24, 10), fill(g(shade(col, -0.3)))); cv.drawPath(ellipse(lx + sw_ + 4, -6, 24, 10), ink(W * 0.7))
    # body + hump
    body = path_smooth([(-170, by + 20), (-150, by - 60), (-60, by - 70), (-20, by - 170 + br * 2), (40, by - 168 + br * 2),
                        (80, by - 70), (160, by - 50), (180, by + 10), (120, by + 60), (-120, by + 60)])
    cv.drawPath(body, fill(g(col)))
    cv.save(); cv.clipPath(body, doAntiAlias=True)
    cv.drawPath(ellipse(0, by + 70, 200, 60), fill(g('#3a2a5a'), 0.16))
    cv.drawPath(ellipse(-10, by - 140, 40, 22), fill(g('#ffffff'), 0.25))
    # a woven saddle blanket
    cv.drawPath(path_poly([(-90, by - 60), (90, by - 60), (100, by + 20), (-100, by + 20)]), fill(g('#c8343c')))
    for k in range(-4, 5):
        cv.drawPath(path_poly([(k * 22 - 8, by + 20), (k * 22 + 8, by + 20), (k * 22, by + 36)]), fill(g('#e6c25a')))
    cv.drawLine(-100, by - 30, 100, by - 30, stroke(g('#2a3a7a'), 8))
    cv.restore()
    cv.drawPath(body, ink(W))
    # tail
    tl = skia.Path(); tl.moveTo(-168, by - 10); tl.quadTo(-196, by + 30 + math.sin(t * 3) * 6, -186, by + 80)
    cv.drawPath(tl, ink(W * 1.3))
    # neck + head
    nk = path_smooth([(140, by - 40), (190, by - 120), (210, by - 230), (250, by - 250), (262, by - 214), (236, by - 120), (184, by + 10)])
    cv.drawPath(nk, fill(g(col))); cv.drawPath(nk, ink(W))
    hx, hy = 260, by - 262
    head = path_smooth([(hx - 40, hy + 20), (hx - 36, hy - 30), (hx + 10, hy - 44), (hx + 70, hy - 20), (hx + 84, hy + 16), (hx + 60, hy + 40), (hx - 10, hy + 40)])
    cv.drawPath(head, fill(g(col))); cv.drawPath(head, ink(W))
    ear = path_smooth([(hx - 30, hy - 30), (hx - 44, hy - 58), (hx - 20, hy - 40)])
    cv.drawPath(ear, fill(g(shade(col, -0.1)))); cv.drawPath(ear, ink(W * 0.7))
    blink = (t * 0.27 + 0.1) % 1.0 < 0.04
    ex, ey = hx + 10, hy - 8
    if blink:
        cv.drawLine(ex - 12, ey, ex + 12, ey, ink(5))
    elif expr == 'shocked':
        cv.drawCircle(ex, ey, 16, fill('#ffffff')); cv.drawCircle(ex, ey, 16, ink(4)); cv.drawCircle(ex + 2, ey, 6, fill(INK))
    else:
        cv.drawPath(ellipse(ex, ey, 11, 14), fill(INK)); cv.drawCircle(ex - 3, ey - 5, 3.5, fill('#ffffff'))
        lid = path_smooth([(ex - 16, ey - 10), (ex, ey - 22), (ex + 16, ey - 10)], close=False)
        cv.drawPath(lid, ink(5))                              # sleepy camel lid
    cv.drawPath(ellipse(hx + 66, hy + 4, 6, 4), fill(INK))
    mo = skia.Path(); mo.moveTo(hx + 34, hy + 28); mo.quadTo(hx + 56, hy + 36 + (6 if expr == 'happy' else -4), hx + 78, hy + 24)
    cv.drawPath(mo, ink(4))
    # lead rope
    cv.drawPath(path_smooth([(hx + 40, hy + 30), (hx + 20, hy + 120), (hx - 20, hy + 200)], close=False), stroke(g('#c8343c'), 5))
    cv.restore()


def draw_animal(cv, kind, x, y, scale, t, mood_name, **kw):
    if kind == 'cat':
        draw_cat(cv, x, y, scale, t, mood_name, **kw)
    elif kind == 'camel':
        draw_camel(cv, x, y, scale, t, mood_name, **kw)
