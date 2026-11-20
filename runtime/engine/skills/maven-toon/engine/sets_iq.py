"""Maven sets: Iraqi and Arab everyday places for Maven Toon.

chaikhana  - Iraqi tea house: kashi-tile wall, samovar, istikan shelf, radio, benches, backgammon on the near table
souq       - covered market alley: brick vault with skylights and light shafts, spice cones, carpets, lanterns
shatt      - riverside (Tigris / Shatt al-Arab): date palms, shanasheel houses and a dome across the water, a balam boat
classroom  - school room: green chalkboard with Arabic chalk text (set_args {"board": "..."}), desks, map, windows
rooftop    - Baghdad roof: beds with mosquito nets, air cooler, water tank, dish, palms and a skyline (best at night)

Same plane conventions as sets.py: subject plane z = 1.0, far planes 2-14, sky ~30 (grade=False), blurred near plane
0.55-0.65. Copyright (c) 2026 Maven. See rights/MAVEN-RIGHTS.txt.
"""
import math

import skia

from .paint import (fill, stroke, ink, shade, mix, path_poly, path_smooth, rrect, ellipse, lin_grad, rad_grad,
                    argb, rng, surface, draw_tex_quad, INK)
from . import textures as tx
from . import setkit as sk
from .light import MOODS, halo, pool, god_rays, window_slash
from .text import draw_text

NIGHT = ('night',)


# =============================================================================== pieces
def kashi_tiles(w, h, size=120, base='#2f7f9a', star='#f4f0e6', accent='#e6b43c', seed=1):
    """Iraqi glazed tiles: blue squares with a white eight-point star and a gold centre."""
    s = surface(w, h, shade(base, -0.35))
    cv = s.getCanvas()
    r = rng(seed)
    for j in range(int(h / size) + 1):
        for i in range(int(w / size) + 1):
            x, y = i * size, j * size
            col = shade(base, r.uniform(-0.08, 0.08))
            cv.drawPath(rrect(x + 3, y + 3, size - 6, size - 6, 6), fill(col))
            cx, cy, R = x + size / 2, y + size / 2, size * 0.36
            pts = []
            for k in range(16):
                rr = R if k % 2 == 0 else R * 0.55
                a = k * math.pi / 8
                pts.append((cx + math.cos(a) * rr, cy + math.sin(a) * rr))
            cv.drawPath(path_poly(pts), fill(star))
            cv.drawCircle(cx, cy, R * 0.3, fill(accent))
            for (qx, qy) in ((x, y), (x + size, y), (x, y + size), (x + size, y + size)):
                cv.drawCircle(qx, qy, size * 0.12, fill('#1f4a6a'))
            cv.drawPath(rrect(x + 3, y + 3, size - 6, size * 0.3, 6), fill('#ffffff', 0.12))
    return s.makeImageSnapshot()


def plaster(w, h, base='#e8d8b8', seed=2):
    s = surface(w, h, base)
    cv = s.getCanvas()
    r = rng(seed)
    for _ in range(int(w * h / 9000)):
        x, y = r.uniform(0, w), r.uniform(0, h)
        cv.drawPath(ellipse(x, y, r.uniform(20, 70), r.uniform(10, 40)), fill(shade(base, r.uniform(-0.06, 0.05)), 0.5))
    return s.makeImageSnapshot()


def palm(cv, x, ground, h, lean=0.0, col='#3f8a46', trunk='#8a6038', seed=0, dates=True, ink_w=3.0):
    """Date palm: a ringed trunk with a slight curve and a crown of arched fronds."""
    r = rng(seed)
    top = (x + lean * h, ground - h)
    w0, w1 = h * 0.055, h * 0.04
    n = 22
    left, right = [], []
    for k in range(n + 1):
        u = k / n
        cx = x + lean * h * (u ** 1.6)
        cy = ground - h * u
        ww = w0 + (w1 - w0) * u
        left.append((cx - ww, cy)); right.append((cx + ww, cy))
    tr = path_poly(left + right[::-1])
    cv.drawPath(tr, fill(trunk))
    cv.save(); cv.clipPath(tr, doAntiAlias=True)
    for k in range(n * 2):
        u = k / (n * 2)
        cx = x + lean * h * (u ** 1.6)
        cy = ground - h * u
        ww = w0 + (w1 - w0) * u
        cv.drawPath(path_smooth([(cx - ww, cy), (cx, cy + ww * 0.5), (cx + ww, cy)], close=False), stroke(shade(trunk, -0.3), max(1.5, ww * 0.18)))
    cv.drawRect(skia.Rect.MakeLTRB(x - w0 * 3 + lean * h * 0.5, ground - h, x + lean * h * 0.4, ground), fill('#ffffff', 0.08))
    cv.restore()
    cv.drawPath(tr, ink(ink_w))
    if dates:
        for k in range(3):
            a = -0.6 + k * 0.6
            cx, cy = top[0] + math.sin(a) * h * 0.06, top[1] + h * 0.07
            for j in range(9):
                cv.drawCircle(cx + r.uniform(-1, 1) * h * 0.03, cy + r.uniform(0, 1) * h * 0.06, h * 0.011, fill('#c8642e'))
            cv.drawPath(ellipse(cx, cy + h * 0.03, h * 0.035, h * 0.045), ink(ink_w * 0.6, 0.6))
    for k in range(13):
        a = math.radians(-180 + k * 15 + r.uniform(-6, 6))
        L = h * r.uniform(0.32, 0.46)
        droop = r.uniform(0.25, 0.55)
        p0 = top
        p2 = (p0[0] + math.cos(a) * L, p0[1] + math.sin(a) * L * 0.55 + L * droop)
        p1 = (p0[0] + math.cos(a) * L * 0.55, p0[1] + math.sin(a) * L * 0.6 - L * 0.12)
        spine = skia.Path(); spine.moveTo(*p0); spine.quadTo(*p1, *p2)
        lc = shade(col, r.uniform(-0.18, 0.12))
        for j in range(1, 14):
            u = j / 14
            bx = (1 - u) ** 2 * p0[0] + 2 * (1 - u) * u * p1[0] + u * u * p2[0]
            by = (1 - u) ** 2 * p0[1] + 2 * (1 - u) * u * p1[1] + u * u * p2[1]
            ll = L * 0.16 * (1 - u * 0.6)
            for sgn in (-1, 1):
                ang = a + sgn * 1.1 + 0.6
                cv.drawLine(bx, by, bx + math.cos(ang) * ll, by + math.sin(ang) * ll + ll * 0.6, stroke(lc, max(2.0, h * 0.012)))
        cv.drawPath(spine, stroke(shade(lc, -0.25), max(2.5, h * 0.012)))
    cv.drawCircle(top[0], top[1], h * 0.03, fill(shade(trunk, -0.2)))


def shanasheel_house(cv, x, ground, w, h, wall='#d8b088', wood='#7a4a2e', glass='#f2d48a', E=None, lit=False, seed=0):
    """Old Baghdad / Basra house: yellow brick with a projecting wooden shanasheel (lattice oriel) upstairs."""
    r = rng(seed)
    body = rrect(x, ground - h, w, h, 4)
    cv.drawPath(body, fill(wall))
    cv.save(); cv.clipPath(body, doAntiAlias=True)
    for j in range(int(h / 18)):
        y = ground - h + j * 18
        cv.drawLine(x, y, x + w, y, stroke(shade(wall, -0.12), 1.5, 0.7))
    cv.restore()
    cv.drawPath(body, ink(3))
    cv.drawRect(skia.Rect.MakeXYWH(x - 6, ground - h - 14, w + 12, 16), fill(shade(wall, -0.15)))
    cv.drawRect(skia.Rect.MakeXYWH(x - 6, ground - h - 14, w + 12, 16), ink(2.5))
    # shanasheel box
    bx, by, bw, bh = x + w * 0.12, ground - h * 0.86, w * 0.76, h * 0.42
    cv.drawPath(path_poly([(bx - 10, by + bh), (bx + bw + 10, by + bh), (bx + bw - 6, by + bh + 26), (bx + 6, by + bh + 26)]), fill(shade(wood, -0.2)))
    box = rrect(bx - 10, by, bw + 20, bh, 3)
    cv.drawPath(box, fill(wood)); cv.drawPath(box, ink(3))
    nw = 3
    for i in range(nw):
        wx = bx + i * bw / nw + 8
        ww = bw / nw - 16
        win = skia.Rect.MakeXYWH(wx, by + 12, ww, bh - 26)
        cv.drawRect(win, fill(glass if lit else shade(wood, -0.35)))
        if E is not None and lit:
            E.append(dict(kind='window', rect=(wx, by + 12, ww, bh - 26)))
        for k in range(1, 5):                                 # lattice
            cv.drawLine(wx + ww * k / 5, by + 12, wx + ww * k / 5, by + bh - 14, stroke(shade(wood, 0.1), 2.2))
        for k in range(1, 6):
            cv.drawLine(wx, by + 12 + (bh - 26) * k / 6, wx + ww, by + 12 + (bh - 26) * k / 6, stroke(shade(wood, 0.1), 2.2))
        cv.drawRect(win, ink(2))
    # door + small window downstairs
    dw = w * 0.22
    door = path_smooth([(x + w * 0.5 - dw / 2, ground), (x + w * 0.5 - dw / 2, ground - h * 0.3), (x + w * 0.5, ground - h * 0.38),
                        (x + w * 0.5 + dw / 2, ground - h * 0.3), (x + w * 0.5 + dw / 2, ground)])
    cv.drawPath(door, fill(shade(wood, -0.1))); cv.drawPath(door, ink(2.5))
    cv.drawCircle(x + w * 0.5 + dw * 0.3, ground - h * 0.16, 3, fill('#e6c25a'))


def dome_minaret(cv, x, ground, s=1.0, col='#e8d8b8', dome='#3a8aa0', gold='#e6b43c'):
    """A mosque skyline piece: tiled dome on a drum and a slim minaret."""
    bw = 260 * s
    cv.drawPath(rrect(x - bw / 2, ground - 160 * s, bw, 160 * s, 3), fill(col)); cv.drawPath(rrect(x - bw / 2, ground - 160 * s, bw, 160 * s, 3), ink(3))
    cv.drawPath(rrect(x - 90 * s, ground - 220 * s, 180 * s, 64 * s, 3), fill(shade(col, -0.05))); cv.drawPath(rrect(x - 90 * s, ground - 220 * s, 180 * s, 64 * s, 3), ink(3))
    d = path_smooth([(x - 96 * s, ground - 218 * s), (x - 92 * s, ground - 300 * s), (x - 40 * s, ground - 360 * s),
                     (x, ground - 384 * s), (x + 40 * s, ground - 360 * s), (x + 92 * s, ground - 300 * s), (x + 96 * s, ground - 218 * s)])
    cv.drawPath(d, fill(dome))
    cv.save(); cv.clipPath(d, doAntiAlias=True)
    for k in range(-5, 6):
        cv.drawLine(x + k * 18 * s, ground - 400 * s, x + k * 22 * s, ground - 210 * s, stroke(shade(dome, 0.15), 3 * s))
    cv.drawPath(ellipse(x - 40 * s, ground - 320 * s, 18 * s, 40 * s), fill('#ffffff', 0.25))
    cv.restore()
    cv.drawPath(d, ink(3))
    cv.drawLine(x, ground - 384 * s, x, ground - 430 * s, stroke(gold, 5 * s))
    cv.drawCircle(x, ground - 436 * s, 9 * s, fill(gold))
    mx = x + 190 * s
    cv.drawPath(path_poly([(mx - 22 * s, ground), (mx + 22 * s, ground), (mx + 16 * s, ground - 520 * s), (mx - 16 * s, ground - 520 * s)]), fill(col))
    cv.drawPath(path_poly([(mx - 22 * s, ground), (mx + 22 * s, ground), (mx + 16 * s, ground - 520 * s), (mx - 16 * s, ground - 520 * s)]), ink(3))
    for yy in (380, 520):
        cv.drawPath(rrect(mx - 32 * s, ground - yy * s, 64 * s, 18 * s, 4), fill(shade(col, -0.1))); cv.drawPath(rrect(mx - 32 * s, ground - yy * s, 64 * s, 18 * s, 4), ink(2.5))
    cv.drawPath(path_poly([(mx - 16 * s, ground - 520 * s), (mx + 16 * s, ground - 520 * s), (mx, ground - 600 * s)]), fill(dome))
    cv.drawPath(path_poly([(mx - 16 * s, ground - 520 * s), (mx + 16 * s, ground - 520 * s), (mx, ground - 600 * s)]), ink(2.5))
    cv.drawCircle(mx, ground - 608 * s, 6 * s, fill(gold))


def lantern(cv, x, y, s=1.0, glass='#f8c860', E=None, lit=True, chain=300):
    """Hanging brass lantern with coloured glass."""
    cv.drawLine(x, y - chain * s, x, y - 40 * s, stroke('#4a3a2a', 3 * s))
    body = path_poly([(x - 30 * s, y - 40 * s), (x + 30 * s, y - 40 * s), (x + 40 * s, y + 10 * s), (x + 22 * s, y + 52 * s),
                      (x - 22 * s, y + 52 * s), (x - 40 * s, y + 10 * s)])
    cv.drawPath(body, fill(glass))
    for k in (-1, 0, 1):
        cv.drawLine(x + k * 18 * s, y - 40 * s, x + k * 22 * s, y + 52 * s, stroke('#b07a30', 4 * s))
    cv.drawPath(body, ink(3))
    cv.drawPath(path_poly([(x - 34 * s, y - 40 * s), (x + 34 * s, y - 40 * s), (x, y - 70 * s)]), fill('#c89040')); cv.drawPath(path_poly([(x - 34 * s, y - 40 * s), (x + 34 * s, y - 40 * s), (x, y - 70 * s)]), ink(3))
    cv.drawPath(path_poly([(x - 22 * s, y + 52 * s), (x + 22 * s, y + 52 * s), (x, y + 76 * s)]), fill('#c89040')); cv.drawPath(path_poly([(x - 22 * s, y + 52 * s), (x + 22 * s, y + 52 * s), (x, y + 76 * s)]), ink(3))
    if E is not None:
        E.append(dict(kind='lamp', pos=(x, y + 6 * s), r=240 * s, lit=lit))


def spice_cone(cv, x, y, w, col, sack='#d8c08a'):
    """An open sack with a heaped cone of spice."""
    sk_ = path_smooth([(x - w * 0.55, y), (x - w * 0.6, y - w * 0.45), (x - w * 0.5, y - w * 0.62), (x + w * 0.5, y - w * 0.62),
                       (x + w * 0.6, y - w * 0.45), (x + w * 0.55, y)])
    cv.drawPath(sk_, fill(sack)); cv.drawPath(sk_, ink(max(1.5, w * 0.03)))
    cone = path_smooth([(x - w * 0.5, y - w * 0.6), (x - w * 0.2, y - w * 0.95), (x, y - w * 1.05), (x + w * 0.2, y - w * 0.95), (x + w * 0.5, y - w * 0.6)])
    cv.drawPath(cone, fill(col))
    cv.drawPath(ellipse(x - w * 0.12, y - w * 0.88, w * 0.12, w * 0.06), fill('#ffffff', 0.3))
    cv.drawPath(cone, ink(max(1.5, w * 0.03)))
    cv.drawPath(path_smooth([(x - w * 0.5, y - w * 0.6), (x, y - w * 0.52), (x + w * 0.5, y - w * 0.6)], close=False), stroke(shade(sack, -0.25), max(2, w * 0.05)))


def samovar(cv, x, y, s=1.0, E=None, lit=False):
    """Brass samovar with a teapot on top (y = base)."""
    g = '#d8a848'
    cv.drawPath(path_poly([(x - 50 * s, y), (x + 50 * s, y), (x + 34 * s, y - 40 * s), (x - 34 * s, y - 40 * s)]), fill(shade(g, -0.15)))
    cv.drawPath(path_poly([(x - 50 * s, y), (x + 50 * s, y), (x + 34 * s, y - 40 * s), (x - 34 * s, y - 40 * s)]), ink(3))
    b = path_smooth([(x - 46 * s, y - 40 * s), (x - 62 * s, y - 130 * s), (x - 44 * s, y - 200 * s), (x + 44 * s, y - 200 * s),
                     (x + 62 * s, y - 130 * s), (x + 46 * s, y - 40 * s)])
    cv.drawPath(b, fill(g))
    cv.drawPath(ellipse(x - 26 * s, y - 130 * s, 12 * s, 50 * s), fill('#fff4c0', 0.5))
    cv.drawPath(b, ink(3.5))
    cv.drawPath(rrect(x - 50 * s, y - 70 * s, 100 * s, 12 * s, 4), fill(shade(g, -0.25)))
    cv.drawPath(rrect(x + 50 * s, y - 92 * s, 40 * s, 10 * s, 3), fill('#c8ccd8')); cv.drawPath(rrect(x + 50 * s, y - 92 * s, 40 * s, 10 * s, 3), ink(2.5))
    # teapot on top
    tp = path_smooth([(x - 40 * s, y - 200 * s), (x - 44 * s, y - 250 * s), (x, y - 270 * s), (x + 44 * s, y - 250 * s), (x + 40 * s, y - 200 * s)])
    cv.drawPath(tp, fill('#f4f0ea')); cv.drawPath(path_smooth([(x - 40 * s, y - 232 * s), (x, y - 226 * s), (x + 40 * s, y - 232 * s)], close=False), stroke('#3a6ab0', 5 * s))
    cv.drawPath(tp, ink(3))
    cv.drawPath(path_smooth([(x + 40 * s, y - 236 * s), (x + 72 * s, y - 256 * s), (x + 80 * s, y - 280 * s), (x + 70 * s, y - 280 * s), (x + 40 * s, y - 248 * s)]), fill('#f4f0ea'))
    if lit and E is not None:
        cv.drawPath(rrect(x - 20 * s, y - 34 * s, 40 * s, 20 * s, 4), fill('#ff9a40'))
        E.append(dict(kind='lamp', pos=(x, y - 24 * s), r=160 * s, lit=True))


def radio(cv, x, y, s=1.0):
    cv.drawPath(rrect(x - 90 * s, y - 120 * s, 180 * s, 120 * s, 14 * s), fill('#8a4a2a')); cv.drawPath(rrect(x - 90 * s, y - 120 * s, 180 * s, 120 * s, 14 * s), ink(3))
    cv.drawPath(rrect(x - 74 * s, y - 104 * s, 96 * s, 88 * s, 8 * s), fill('#e8d8b0'))
    for k in range(6):
        cv.drawLine(x - 70 * s, y - 94 * s + k * 14 * s, x + 18 * s, y - 94 * s + k * 14 * s, stroke('#8a6a4a', 2.5 * s))
    for k in range(2):
        cv.drawCircle(x + 52 * s, y - 84 * s + k * 46 * s, 14 * s, fill('#e6c25a')); cv.drawCircle(x + 52 * s, y - 84 * s + k * 46 * s, 14 * s, ink(2.5))
    cv.drawLine(x + 60 * s, y - 120 * s, x + 110 * s, y - 220 * s, stroke('#9aa2b4', 3 * s))


def tawli(cv, x, y, w):
    """An open backgammon board seen from above at an angle (y = near edge)."""
    q = [(x - w * 0.42, y - w * 0.5), (x + w * 0.42, y - w * 0.5), (x + w * 0.5, y), (x - w * 0.5, y)]
    cv.drawPath(path_poly(q), fill('#8a4a2a')); cv.drawPath(path_poly(q), ink(4))
    iq = [(x - w * 0.38, y - w * 0.46), (x + w * 0.38, y - w * 0.46), (x + w * 0.45, y - w * 0.04), (x - w * 0.45, y - w * 0.04)]
    cv.drawPath(path_poly(iq), fill('#e8d0a0'))
    for k in range(12):
        u0 = k / 12
        for (yy0, yy1, sg) in ((-0.46, -0.3, 1), (-0.04, -0.2, -1)):
            xa = x + (-0.38 + 0.76 * u0) * w * (1 + (yy0 + 0.46) * 0.4)
            xb = x + (-0.38 + 0.76 * (u0 + 1 / 12)) * w * (1 + (yy0 + 0.46) * 0.4)
            cv.drawPath(path_poly([(xa, y + yy0 * w), (xb, y + yy0 * w), ((xa + xb) / 2, y + yy1 * w)]), fill('#a03a2a' if k % 2 else '#2a4a3a'))
    cv.drawLine(x, y - w * 0.46, x, y - w * 0.04, stroke('#6a3a1e', w * 0.03))
    for k, (dx, dy, c) in enumerate(((-0.2, -0.36, '#f4f0ea'), (-0.14, -0.33, '#2a2232'), (0.18, -0.12, '#f4f0ea'), (0.24, -0.15, '#2a2232'))):
        cv.drawPath(ellipse(x + dx * w, y + dy * w, w * 0.035, w * 0.022), fill(c)); cv.drawPath(ellipse(x + dx * w, y + dy * w, w * 0.035, w * 0.022), ink(2))


def _lights(E, night, extra=None):
    def f(cv, mm):
        sk.draw_emitters(cv, E, mm, night)
        if extra:
            extra(cv, mm)
    return f


# =============================================================================== CHAIKHANA (tea house)
def chaikhana(mood):
    from .interiors import room_box
    m = MOODS[mood]
    night = mood in NIGHT
    E, E2 = [], []
    back = (60, 240, 1020, 1250)

    def room(cv):
        wall_t = surface(960, 1010, '#e8d8b8')
        wc = wall_t.getCanvas()
        wc.drawImage(plaster(960, 1010), 0, 0)
        wc.drawImage(kashi_tiles(960, 440, size=120), 0, 570)
        wc.drawRect(skia.Rect.MakeXYWH(0, 556, 960, 18), fill('#2a5a7a'))
        room_box(cv, back, back_tex=wall_t.makeImageSnapshot(),
                 left_tex=kashi_tiles(1300, 1700, size=130, base='#3a8aa0', seed=3),
                 right_tex=plaster(1300, 1700, base='#dcc8a0', seed=4),
                 floor_tex=tx.checker_tiles(1400, 1400, size=150, c1='#e8dcc8', c2='#a8483a'),
                 ceil_tex=tx.wood_planks(1400, 1200, plank=120, base='#8a5a3a', seed=5))
        # framed pictures, clock and a shelf of istikan glasses
        sk.frame_pic(cv, 130, 330, 170, 210, col='#7a4a2a', art=lambda c, r: (c.drawRect(r, fill('#c8a070')), c.drawPath(ellipse(r.centerX(), r.centerY() - 10, 40, 50), fill('#5a4a3a'))))
        sk.frame_pic(cv, 330, 360, 150, 120, col='#a0703a', art=lambda c, r: (c.drawRect(r, fill('#8ab0d0')), c.drawPath(path_poly([(r.left(), r.bottom()), (r.centerX(), r.top() + 20), (r.right(), r.bottom())]), fill('#5a8a5a'))))
        sk.wall_clock(cv, 560, 380, 70)
        cv.drawPath(rrect(660, 520, 320, 20, 4), fill('#7a4a2a')); cv.drawPath(rrect(660, 520, 320, 20, 4), ink(3))
        for k in range(7):
            gx = 690 + k * 42
            cv.drawPath(path_smooth([(gx - 12, 470), (gx - 8, 494), (gx - 11, 518), (gx + 11, 518), (gx + 8, 494), (gx + 12, 470)]), fill('#fff4e0', 0.6))
            cv.drawPath(path_smooth([(gx - 12, 470), (gx - 8, 494), (gx - 11, 518), (gx + 11, 518), (gx + 8, 494), (gx + 12, 470)]), ink(2))
        radio(cv, 820, 510, 0.9)
        # serving counter with the samovar (right)
        cv.drawPath(rrect(600, 980, 400, 270, 6), fill('#7a3e26')); cv.drawPath(rrect(600, 980, 400, 270, 6), ink(4))
        cv.drawImage(kashi_tiles(380, 200, size=100, base='#2f7f9a', seed=7), 610, 1030)
        cv.drawPath(rrect(590, 960, 420, 30, 6), fill('#a0603a')); cv.drawPath(rrect(590, 960, 420, 30, 6), ink(4))
        samovar(cv, 800, 960, 1.15, E, lit=night or mood in ('golden', 'interior'))
        for k in range(3):
            cv.drawPath(ellipse(660 + k * 50, 958, 18, 5), fill('#f4f0ea'))
        # benches (takhta) with carpet seats on the left
        for k in range(2):
            by = 1120 + k * 120
            cv.drawPath(rrect(70 - k * 60, by, 440, 60, 6), fill('#9a6232')); cv.drawPath(rrect(70 - k * 60, by, 440, 60, 6), ink(3.5))
            cv.drawImage(tx.carpet(420, 40, seed=k), 80 - k * 60, by - 30)
            cv.drawRect(skia.Rect.MakeXYWH(80 - k * 60, by - 30, 420, 40), ink(2.5))
            for lx in (90, 470):
                cv.drawRect(skia.Rect.MakeXYWH(lx - k * 60, by + 60, 18, 70), fill('#6a3a1e'))
        # ceiling fan and hanging lanterns
        cv.drawLine(540, -400, 540, 140, stroke('#3a2a2a', 6))
        for a in (-0.15, 0.95, 2.05):
            cv.drawPath(path_poly([(540, 140), (540 + math.cos(a) * 260, 140 + math.sin(a) * 30), (540 + math.cos(a + 0.18) * 260, 140 + math.sin(a + 0.18) * 30)]), fill('#5a3a2a'))
        cv.drawCircle(540, 140, 22, fill('#c89040')); cv.drawCircle(540, 140, 22, ink(3))
        lantern(cv, 230, 230, 1.0, glass='#f8b050', E=E, lit=True, chain=600)
        lantern(cv, 860, 250, 0.9, glass='#90d0a0', E=E, lit=True, chain=600)

    def near(cv):
        # near table corner with istikan, sugar bowl and an open backgammon board
        top = 1980
        cv.drawPath(path_poly([(-500, top - 260), (700, top - 200), (900, 2600), (-500, 2600)]), fill('#9a6232'))
        cv.drawPath(path_poly([(-500, top - 260), (700, top - 200)], close=False), ink(5))
        tawli(cv, 260, 2000, 560)
        from .cast_iq import istikan, _HoldCtx
        istikan(_HoldCtx(cv, 0.0, mood), 660, 1900, 2.2)

    return [
        ('room', 1.6, room, dict(lights=_lights(E, True, (lambda c, mm: god_rays(c, (230, 230), 90, 60, 1100, n=5, col=mm['key'], a=0.12)) if night else None))),
        ('near', 0.6, near, dict(blur=12)),
    ], dict(ground_y=1500, samovar=(800, 900))


# =============================================================================== SOUQ (covered market)
def souq(mood):
    from .sets import Ground
    m = MOODS[mood]
    night = mood in NIGHT
    vx, h0 = 540, 900
    G = Ground(vx, h0, 1.55)
    E = []
    WALL_X, WALL_H = 3.0, 4.6
    spices = ['#d84a2a', '#e8a83a', '#c8642e', '#7a8a3a', '#a0402a', '#e8c84a', '#5a7a3a', '#b8582a']

    def alley(cv):
        # end opening (bright street beyond)
        ex0, ey0 = G.proj(-WALL_X, 60); ex1, ey1 = G.proj(WALL_X, 60)
        top_y = h0 - G.K / 60 * (WALL_H / 1.55) + (ey0 - h0)
        p = skia.Paint(AntiAlias=True)
        p.setShader(lin_grad((0, top_y), (0, ey0), [argb(mix(m['key'], (255, 255, 255), 0.5)), argb(m['fog'])]))
        cv.drawRect(skia.Rect.MakeLTRB(ex0 - 40, top_y - 60, ex1 + 40, ey0 + 4), p)
        # floor
        G.tile(cv, tx.stone_blocks(800, 800, bw=150, bh=110, base='#b8a890', seed=4), 1.6, 1.2, xr=(-WALL_X, WALL_X), zr=(0.5, 60))
        G.line(cv, -0.3, 0.6, -0.3, 60, stroke('#8a7a68', 6, 0.5))
        # side walls (bricks) and the vault
        for sgn in (-1, 1):
            nb, fb = G.proj(sgn * WALL_X, 0.55), G.proj(sgn * WALL_X, 60)
            s_n, s_f = G.scale(0.55), G.scale(60)
            q = [(nb[0], nb[1] - WALL_H * s_n), (fb[0], fb[1] - WALL_H * s_f), fb, nb] if sgn < 0 else [(fb[0], fb[1] - WALL_H * s_f), (nb[0], nb[1] - WALL_H * s_n), nb, fb]
            draw_tex_quad(cv, tx.bricks(2400, 400, bw=90, bh=34, base='#c8945a', mortar='#e8cfa0', seed=6 + sgn), q)
            cv.drawPath(path_poly(q), fill('#4a2e66', 0.12 if sgn < 0 else 0.22))
        vq = [G.proj(-WALL_X, 0.55), G.proj(WALL_X, 0.55), G.proj(WALL_X, 60), G.proj(-WALL_X, 60)]
        vq = [(vq[0][0], vq[0][1] - WALL_H * G.scale(0.55)), (vq[1][0], vq[1][1] - WALL_H * G.scale(0.55)),
              (vq[2][0], vq[2][1] - WALL_H * G.scale(60)), (vq[3][0], vq[3][1] - WALL_H * G.scale(60))]
        draw_tex_quad(cv, tx.bricks(800, 2400, bw=80, bh=30, base='#b8844a', mortar='#d8bf90', seed=9), vq)
        cv.drawPath(path_poly(vq), fill('#2a1a3a', 0.28))
        # arches across the vault + skylights
        Z = 2.2
        while Z < 55:
            s = G.scale(Z)
            lx, ly = G.proj(-WALL_X, Z); rx, ry = G.proj(WALL_X, Z)
            yt = ly - WALL_H * s
            arch = skia.Path(); arch.moveTo(lx, ly - WALL_H * 0.55 * s)
            arch.quadTo(lx, yt, (lx + rx) / 2, yt - 0.1 * s); arch.quadTo(rx, yt, rx, ry - WALL_H * 0.55 * s)
            cv.drawPath(arch, stroke('#a0703a', max(3, 0.32 * s))); cv.drawPath(arch, ink(max(1.5, 0.05 * s), 0.8))
            sx_, sy_ = (lx + rx) / 2, yt + 0.25 * s
            cv.drawPath(ellipse(sx_, sy_, 0.55 * s, 0.16 * s), fill('#fff4d8' if not night else '#2a3a8a'))
            cv.drawPath(ellipse(sx_, sy_, 0.55 * s, 0.16 * s), ink(max(1.2, 0.04 * s)))
            Z *= 1.55
        # shops on both sides: dark openings, awnings, goods
        r = rng(3)
        Z = 1.6
        k = 0
        while Z < 40:
            Lz = 1.7
            for sgn in (-1, 1):
                p0 = G.proj(sgn * WALL_X, Z); p1 = G.proj(sgn * WALL_X, Z + Lz)
                s0, s1 = G.scale(Z), G.scale(Z + Lz)
                op = [(p0[0], p0[1] - 2.5 * s0), (p1[0], p1[1] - 2.5 * s1), p1, p0]
                cv.drawPath(path_poly(op), fill('#3a2230')); cv.drawPath(path_poly(op), ink(max(1.2, 0.03 * s0)))
                if night or mood in ('interior', 'golden'):
                    E.append(dict(kind='quad', quad=op))
                # awning
                aw = [(p0[0], p0[1] - 2.7 * s0), (p1[0], p1[1] - 2.7 * s1), (p1[0] - sgn * 0.5 * s1, p1[1] - 2.3 * s1), (p0[0] - sgn * 0.5 * s0, p0[1] - 2.3 * s0)]
                ac = ['#c8343c', '#2f6a8a', '#e8a83a', '#3f8a5a'][(k + (sgn > 0)) % 4]
                cv.drawPath(path_poly(aw), fill(ac))
                for j in range(1, 6):
                    u = j / 6
                    cv.drawLine(aw[0][0] + (aw[1][0] - aw[0][0]) * u, aw[0][1] + (aw[1][1] - aw[0][1]) * u,
                                aw[3][0] + (aw[2][0] - aw[3][0]) * u, aw[3][1] + (aw[2][1] - aw[3][1]) * u, stroke('#f4f0e6', max(1.5, 0.06 * s0)))
                cv.drawPath(path_poly(aw), ink(max(1.2, 0.03 * s0)))
                # goods in front: spice cones or a hanging carpet
                if (k + (sgn > 0)) % 3 != 2:
                    for j in range(3):
                        gz = Z + 0.3 + j * 0.5
                        gx, gy_ = G.proj(sgn * (WALL_X - 0.45), gz)
                        spice_cone(cv, gx, gy_, 0.55 * G.scale(gz), spices[(k * 3 + j + (sgn > 0)) % len(spices)])
                else:
                    cq = [(p0[0], p0[1] - 2.3 * s0), (p1[0], p1[1] - 2.3 * s1), (p1[0], p1[1] - 0.2 * s1), (p0[0], p0[1] - 0.2 * s0)]
                    draw_tex_quad(cv, tx.carpet(300, 420, base=['#8a2a33', '#2d3a78', '#6a3a7a'][k % 3], seed=k), cq)
                    cv.drawPath(path_poly(cq), ink(max(1.2, 0.03 * s0)))
            # hanging lantern in the middle
            lx, ly = G.proj(0.4 * (1 if k % 2 else -1), Z + 0.8)
            s = G.scale(Z + 0.8)
            lantern(cv, lx, ly - 3.3 * s, s / 340, glass=['#f8b050', '#90d0a0', '#f08a8a'][k % 3], E=E, lit=night or mood in ('interior',), chain=1.2 * s / (s / 340))
            Z += Lz + 0.25
            k += 1

    def lights(cv, mm):
        sk.draw_emitters(cv, [e for e in E if e['kind'] == 'lamp'], mm, night or mood == 'interior')
        if night:
            for e in E:
                if e['kind'] == 'quad':
                    cv.drawPath(path_poly(e['quad']), fill(mix(mm['key'], (255, 200, 120), 0.5), 0.35, blend=skia.BlendMode.kScreen))
        else:
            Z = 2.2
            while Z < 55:
                s = G.scale(Z)
                lx, ly = G.proj(0, Z)
                god_rays(cv, (lx, ly - WALL_H * s + 0.25 * s), 90, 18, 4.4 * s, n=4, col=mm['key'], a=0.22, seed=int(Z * 10))
                Z *= 1.55

    def near(cv):
        # a near spice stall corner and a hanging carpet edge
        for j, c in enumerate(('#d84a2a', '#e8a83a', '#7a8a3a')):
            spice_cone(cv, -120 + j * 220, 2420, 260, c)
        cv.drawImage(tx.carpet(360, 1500, base='#2d3a78', seed=8), 1180, -200)
        cv.drawRect(skia.Rect.MakeXYWH(1180, -200, 360, 1500), ink(5))

    return [
        ('alley', 1.0, alley, dict(lights=lights)),
        ('near', 0.6, near, dict(blur=12)),
    ], dict(ground=G, ground_y=1600, h0=h0, vx=vx)


# =============================================================================== SHATT (riverside)
def shatt(mood):
    m = MOODS[mood]
    night = mood in NIGHT
    E_far, E_near = [], []
    sun = None
    if mood in ('sunset', 'dawn', 'golden'):
        sun = (300, 640, 90)
    elif mood == 'day':
        sun = (880, 220, 70)

    def sky(cv):
        sk.sky(cv, m, seed=41, clouds=6, cloud_band=(-400, 520), cloud_scale=1.2, sun=sun,
               moon=(820, 200, 64) if night else None, stars=170 if night else 0)

    def far(cv):
        base = 820
        sk.hills(cv, base + 4, -500, 1600, 30, mix('#6a8a6a', m['fog'], 0.5), seed=3, wav=200)
        r = rng(5)
        x = -460
        k = 0
        while x < 1560:
            w = r.uniform(150, 230)
            h = r.uniform(200, 290)
            if k == 3:
                dome_minaret(cv, x + 120, base, 0.62)
                x += 330
            else:
                shanasheel_house(cv, x, base, w, h, wall=['#d8b088', '#c8a078', '#e0c098', '#b8906a'][k % 4],
                                 wood=['#7a4a2e', '#5a3a2a', '#8a5a3a'][k % 3], E=E_far, lit=night and k % 2 == 0, seed=k)
                x += w + r.uniform(4, 20)
            k += 1
        for k in range(8):
            palm(cv, -380 + k * 270 + r.uniform(-40, 40), base + 6, r.uniform(260, 360), lean=r.uniform(-0.12, 0.12), seed=10 + k, dates=False, ink_w=2.2)
        cv.drawRect(skia.Rect.MakeLTRB(-500, base, 1600, base + 30), fill('#8a7a5a'))
        cv.drawLine(-500, base + 30, 1600, base + 30, ink(2.5))

    def water(cv):
        top, mid_, bot = m['sky']
        base = mix('#2a7a8a', mid_, 0.3) if not night else '#1c2a6a'
        p = skia.Paint(AntiAlias=True)
        p.setShader(lin_grad((0, 850), (0, 2400), [argb(mix(base, bot, 0.35)), argb(base), argb(shade(base, -0.2))]))
        cv.drawRect(skia.Rect.MakeLTRB(-600, 850, 1700, 2500), p)
        r = rng(9)
        for k in range(260):
            y = 860 + (r.random() ** 1.7) * 1400
            d = (y - 860) / 1400
            x = r.uniform(-500, 1600)
            L = 14 + 90 * d
            q = skia.Path(); q.moveTo(x - L, y); q.quadTo(x, y - 6 - 12 * d, x + L, y)
            cv.drawPath(q, stroke(mix(base, '#ffffff', 0.45), 2 + 3 * d, 0.7))
        if sun and mood in ('sunset', 'dawn', 'golden'):      # sun path on the water: broken glints, wider near
            for k in range(60):
                u = r.random()
                y = 870 + u * u * 700
                w = 18 + 140 * u * r.uniform(0.4, 1.0)
                q = skia.Path(); q.moveTo(sun[0] - w / 2 + r.uniform(-1, 1) * (20 + 120 * u), y)
                q.rLineTo(w, 0)
                cv.drawPath(q, stroke(mix(m['key'], (255, 255, 230), 0.55), 3 + 6 * u, 0.6))
        # a balam boat moored on the water
        bx, by = 720, 1240
        hull = path_smooth([(bx - 300, by - 60), (bx - 220, by + 20), (bx + 200, by + 20), (bx + 320, by - 70), (bx + 240, by - 20), (bx - 220, by - 20)])
        cv.drawPath(hull, fill('#8a4a2a')); cv.drawPath(path_smooth([(bx - 270, by - 40), (bx, by - 4), (bx + 280, by - 50)], close=False), stroke('#e6b43c', 6))
        cv.drawPath(hull, ink(3.5))
        cv.drawLine(bx - 60, by - 10, bx + 40, by - 220, stroke('#6a4022', 7)); cv.drawLine(bx - 60, by - 10, bx + 40, by - 220, ink(2))
        cv.drawPath(path_smooth([(bx - 290, by + 30), (bx, by + 50), (bx + 300, by + 26)], close=False), stroke('#ffffff', 3, 0.35))

    def bank(cv):
        top = 1440
        # stone river wall and the promenade
        cv.drawImage(tx.stone_blocks(2200, 220, bw=180, bh=70, base='#c8b08a', seed=3), -560, top)
        cv.drawLine(-560, top, 1640, top, ink(4))
        q = [(-560, top - 4), (1640, top - 4), (2100, 2500), (-1000, 2500)]
        draw_tex_quad(cv, tx.checker_tiles(1400, 1400, size=200, c1='#e2d2b2', c2='#c8b08a'), [(-560, top + 200), (1640, top + 200), (2600, 2600), (-1500, 2600)])
        cv.drawRect(skia.Rect.MakeLTRB(-560, top + 196, 1640, top + 214), fill('#a08a6a')); cv.drawLine(-560, top + 214, 1640, top + 214, ink(3))
        # iron railing
        for k in range(-6, 22):
            x = k * 90
            cv.drawLine(x, top - 130, x, top, stroke('#2a3a4a', 7))
        cv.drawLine(-560, top - 130, 1640, top - 130, stroke('#2a3a4a', 10)); cv.drawLine(-560, top - 70, 1640, top - 70, stroke('#2a3a4a', 5))
        sk.lamp_post(cv, 120, top + 220, h=560, col='#2a3a4a', E=E_near, lit=night or mood in ('sunset', 'dawn'))
        sk.lamp_post(cv, 980, top + 220, h=560, col='#2a3a4a', E=E_near, lit=night or mood in ('sunset', 'dawn'))
        # bench
        cv.drawPath(rrect(560, top + 120, 300, 26, 6), fill('#9a6232')); cv.drawPath(rrect(560, top + 120, 300, 26, 6), ink(3.5))
        cv.drawPath(rrect(560, top + 50, 300, 26, 6), fill('#9a6232')); cv.drawPath(rrect(560, top + 50, 300, 26, 6), ink(3.5))
        for lx in (580, 820):
            cv.drawRect(skia.Rect.MakeXYWH(lx, top + 146, 16, 80), fill('#2a3a4a'))
        palm(cv, -230, top + 230, 900, lean=0.08, seed=2, ink_w=3.5)

    def near(cv):
        palm(cv, 1420, 2700, 1500, lean=-0.06, seed=7, ink_w=5)

    return [
        ('sky', 30.0, sky, dict(grade=False)),
        ('far', 9.0, far, dict(lights=_lights(E_far, night), haze=0.12)),
        ('water', 4.0, water, dict()),
        ('bank', 1.0, bank, dict(lights=_lights(E_near, night or mood in ('sunset', 'dawn')))),
        ('near', 0.6, near, dict(blur=10)),
    ], dict(ground_y=1700)


# =============================================================================== CLASSROOM
def classroom(mood, board='الدرس الأول'):
    from .interiors import room_box
    m = MOODS[mood]
    night = mood in NIGHT
    E = []
    back = (40, 260, 1040, 1230)

    def room(cv):
        wall_t = surface(1000, 970, '#e8e0c8')
        wc = wall_t.getCanvas()
        wc.drawImage(plaster(1000, 970, base='#dfe6d0', seed=6), 0, 0)
        wc.drawRect(skia.Rect.MakeXYWH(0, 640, 1000, 330), fill('#7a9a8a'))
        wc.drawRect(skia.Rect.MakeXYWH(0, 630, 1000, 14), fill('#5a7a6a'))
        room_box(cv, back, back_tex=wall_t.makeImageSnapshot(),
                 left_tex=plaster(1300, 1700, base='#dfe6d0', seed=7), right_tex=plaster(1300, 1700, base='#d4dcc4', seed=8),
                 floor_tex=tx.checker_tiles(1400, 1400, size=140, c1='#e8e2d4', c2='#9aa0a8'),
                 ceil_tex=tx.ceiling_tiles(1400, 1200, size=170, base='#eceae2'))
        # chalkboard with Arabic chalk writing
        cv.drawPath(rrect(150, 380, 780, 420, 8), fill('#7a5a3a')); cv.drawPath(rrect(150, 380, 780, 420, 8), ink(4))
        cv.drawPath(rrect(170, 398, 740, 384, 4), fill('#2f5a46'))
        r = rng(4)
        for _ in range(40):
            x, y = r.uniform(180, 900), r.uniform(410, 770)
            cv.drawPath(ellipse(x, y, r.uniform(30, 90), r.uniform(6, 16)), fill('#ffffff', 0.04))
        draw_text(cv, board, 540, 540, 92, '#f4f2ea')
        cv.drawLine(320, 580, 760, 580, stroke('#f4f2ea', 4, 0.8))
        draw_text(cv, '١ + ١ = ٢', 540, 700, 64, '#f2e6a0')
        cv.drawPath(rrect(170, 782, 740, 18, 3), fill('#9a7a5a')); cv.drawPath(rrect(170, 782, 740, 18, 3), ink(2.5))
        for k in range(3):
            cv.drawPath(rrect(240 + k * 40, 774, 26, 9, 3), fill(['#ffffff', '#f2c640', '#f08a8a'][k]))
        sk.wall_clock(cv, 540, 320, 44)
        # world-map poster and a poster of letters
        cv.drawPath(rrect(60, 870, 200, 150, 4), fill('#f4ecd8')); cv.drawPath(rrect(60, 870, 200, 150, 4), ink(3))
        for k in range(5):
            cv.drawPath(path_smooth([(80 + k * 36, 900 + (k % 2) * 20), (100 + k * 36, 920), (90 + k * 36, 960 - (k % 3) * 10)]), fill('#6ab04a'))
        cv.drawPath(rrect(820, 870, 180, 150, 4), fill('#f8f2e2')); cv.drawPath(rrect(820, 870, 180, 150, 4), ink(3))
        draw_text(cv, 'أ ب ت', 910, 960, 46, '#c8343c')
        # windows on the right wall with sunlight
        for k, wy in enumerate((420,)):
            q = [(1060, wy), (1260, wy - 150), (1260, wy + 520), (1060, wy + 420)]
            cv.drawPath(path_poly(q), fill('#9cc4e8' if not night else '#1c2a6a')); cv.drawPath(path_poly(q), ink(4))
            cv.drawLine(1160, wy - 75, 1160, wy + 470, stroke('#f2ece0', 10))
        # teacher's desk
        cv.drawPath(rrect(330, 1000, 420, 240, 6), fill('#9a6232')); cv.drawPath(rrect(330, 1000, 420, 240, 6), ink(4))
        cv.drawPath(rrect(310, 980, 460, 30, 6), fill('#b07a45')); cv.drawPath(rrect(310, 980, 460, 30, 6), ink(4))
        cv.drawPath(rrect(400, 940, 90, 40, 4), fill('#c8343c')); cv.drawPath(rrect(400, 940, 90, 40, 4), ink(3))
        sk.plant_pot(cv, 680, 980, s=0.9)

    def desks(cv):
        # two rows of double desks on the floor (subject plane), seen from behind the back row
        for row, (y, s) in enumerate(((1560, 0.8), (1820, 1.0))):
            for k, x in enumerate((-60, 620) if row == 0 else (-260, 760)):
                w, h = 460 * s, 60 * s
                cv.drawPath(path_poly([(x, y), (x + w, y), (x + w - 30 * s, y - 70 * s), (x + 30 * s, y - 70 * s)]), fill('#b07a45'))
                cv.drawPath(path_poly([(x, y), (x + w, y), (x + w - 30 * s, y - 70 * s), (x + 30 * s, y - 70 * s)]), ink(3.5))
                cv.drawPath(rrect(x, y, w, h, 4), fill('#8a5a32')); cv.drawPath(rrect(x, y, w, h, 4), ink(3.5))
                for lx in (x + 20 * s, x + w - 36 * s):
                    cv.drawRect(skia.Rect.MakeXYWH(lx, y + h, 16 * s, 160 * s), fill('#5a5a6a')); cv.drawRect(skia.Rect.MakeXYWH(lx, y + h, 16 * s, 160 * s), ink(2.5))
                cv.drawPath(rrect(x + 80 * s, y - 60 * s, 90 * s, 50 * s, 4), fill(['#3a6ab0', '#e8a83a', '#2f9a5a', '#c8343c'][(row * 2 + k) % 4]))
                cv.drawPath(rrect(x + 80 * s, y - 60 * s, 90 * s, 50 * s, 4), ink(2.5))

    def lights(cv, mm):
        if not night:
            window_slash(cv, [(1060, 470), (1240, 360), (900, 1500), (520, 1500)], col=mm['key'], a=0.22)
        sk.draw_emitters(cv, E, mm, night)

    def near(cv):
        cv.drawPath(path_poly([(-500, 2240), (560, 2200), (640, 2600), (-500, 2600)]), fill('#b07a45'))
        cv.drawPath(path_poly([(-500, 2240), (560, 2200)], close=False), ink(5))
        cv.drawPath(rrect(20, 2120, 300, 90, 8), fill('#f4f0e6')); cv.drawPath(rrect(20, 2120, 300, 90, 8), ink(4))
        cv.drawLine(170, 2120, 170, 2210, ink(3))
        cv.drawPath(rrect(380, 2160, 220, 22, 10), fill('#f2c640')); cv.drawPath(rrect(380, 2160, 220, 22, 10), ink(3))

    return [
        ('room', 1.6, room, dict(lights=lights)),
        ('desks', 1.05, desks, dict()),
        ('near', 0.6, near, dict(blur=12)),
    ], dict(ground_y=1500, board=(540, 590))


# =============================================================================== ROOFTOP (Baghdad roof)
def rooftop(mood):
    m = MOODS[mood]
    night = mood in NIGHT
    E_city, E_roof = [], []

    def sky(cv):
        sk.sky(cv, m, seed=51, clouds=4 if not night else 2, cloud_band=(-400, 300), sun=(260, 760, 80) if mood in ('sunset', 'dawn') else None,
               moon=(780, 180, 70) if night else None, stars=260 if night else 0)

    def city(cv):
        base = 960
        r = rng(7)
        x = -480
        k = 0
        while x < 1580:
            w, h = r.uniform(130, 240), r.uniform(120, 300)
            col = mix(['#c8a078', '#b89878', '#d8b890', '#a88a6a'][k % 4], m['fog'], 0.25)
            cv.drawPath(rrect(x, base - h, w, h, 2), fill(col)); cv.drawPath(rrect(x, base - h, w, h, 2), ink(2.5))
            for j in range(int(h / 70)):
                for i in range(int(w / 60)):
                    wx, wy = x + 18 + i * 60, base - h + 24 + j * 70
                    lit = night and r.random() < 0.45
                    cv.drawRect(skia.Rect.MakeXYWH(wx, wy, 26, 30), fill('#f2d48a' if lit else shade(col, -0.3)))
                    if lit:
                        E_city.append(dict(kind='window', rect=(wx, wy, 26, 30)))
            if r.random() < 0.5:                              # water tanks and dishes on far roofs
                cv.drawPath(rrect(x + w * 0.6, base - h - 40, 40, 40, 4), fill('#8a9aa8')); cv.drawPath(rrect(x + w * 0.6, base - h - 40, 40, 40, 4), ink(2))
            x += w + r.uniform(-10, 30)
            k += 1
            if k == 4:
                dome_minaret(cv, x + 60, base, 0.8, col=mix('#e8d8b8', m['fog'], 0.2))
                x += 360
        for k in range(6):
            palm(cv, -300 + k * 360 + r.uniform(-60, 60), base + 10, r.uniform(320, 460), lean=r.uniform(-0.1, 0.1), seed=30 + k, dates=False, ink_w=2.4)

    def roof(cv):
        top = 1250
        # roof floor (tiles) and the parapet with decorative breeze-block holes
        draw_tex_quad(cv, tx.checker_tiles(1400, 1400, size=170, c1='#d8ccb4', c2='#c4b498'), [(-560, top), (1640, top), (2700, 2600), (-1600, 2600)])
        cv.drawPath(rrect(-560, top - 230, 2200, 240, 4), fill('#d8c4a0')); cv.drawPath(rrect(-560, top - 230, 2200, 240, 4), ink(4))
        for k in range(-6, 26):
            x = k * 90
            cv.drawPath(path_poly([(x + 20, top - 170), (x + 45, top - 200), (x + 70, top - 170), (x + 45, top - 140)]), fill('#5a4a5a' if not night else '#141a40'))
            cv.drawPath(path_poly([(x + 20, top - 170), (x + 45, top - 200), (x + 70, top - 170), (x + 45, top - 140)]), ink(2.5))
        cv.drawRect(skia.Rect.MakeLTRB(-560, top - 240, 1640, top - 222), fill('#c8b490')); cv.drawLine(-560, top - 222, 1640, top - 222, ink(3))
        # water tank, satellite dish, air cooler
        cv.drawPath(rrect(-80, top - 560, 260, 260, 20), fill('#e8e8ec')); cv.drawPath(rrect(-80, top - 560, 260, 260, 20), ink(4))
        for k in range(3):
            cv.drawLine(-80, top - 500 + k * 80, 180, top - 500 + k * 80, stroke('#b8b8c4', 4))
        for lx in (-60, 150):
            cv.drawRect(skia.Rect.MakeXYWH(lx, top - 300, 14, 80), fill('#5a5a6a'))
        cv.drawPath(ellipse(890, top - 420, 120, 120), fill('#d8dce4')); cv.drawPath(ellipse(890, top - 420, 120, 120), ink(4))
        cv.drawPath(ellipse(890, top - 420, 80, 80), stroke('#b8bcc8', 4))
        cv.drawLine(890, top - 420, 960, top - 520, stroke('#5a5a6a', 6)); cv.drawLine(890, top - 300, 890, top - 230, stroke('#5a5a6a', 10))
        cv.drawPath(rrect(1040, top - 140, 300, 320, 10), fill('#c8ccd0')); cv.drawPath(rrect(1040, top - 140, 300, 320, 10), ink(4))
        for k in range(10):
            cv.drawLine(1070, top - 110 + k * 28, 1310, top - 110 + k * 28, stroke('#9aa0aa', 5))
        cv.drawPath(rrect(1120, top - 60, 140, 140, 70), fill('#9aa0aa')); cv.drawPath(rrect(1120, top - 60, 140, 140, 70), ink(3))
        # two metal beds with white mosquito nets (summer nights on the roof)
        for (bx, by, s) in ((80, 1520, 0.85), (560, 1600, 1.0)):
            w, h = 420 * s, 120 * s
            for lx in (bx, bx + w):
                cv.drawRect(skia.Rect.MakeXYWH(lx - 6 * s, by - 330 * s, 12 * s, 330 * s + 60 * s), fill('#3a5a8a'))
            cv.drawPath(rrect(bx, by - h, w, h, 10 * s), fill('#f4f0ea')); cv.drawPath(rrect(bx, by - h, w, h, 10 * s), ink(3.5))
            cv.drawPath(rrect(bx + 20 * s, by - h - 30 * s, 110 * s, 40 * s, 14 * s), fill('#f4f0ea')); cv.drawPath(rrect(bx + 20 * s, by - h - 30 * s, 110 * s, 40 * s, 14 * s), ink(3))
            cv.drawImage(tx.carpet(int(w * 0.7), int(h * 0.7), base='#c8343c', seed=int(bx)), bx + w * 0.28, by - h * 0.85)
            net = path_poly([(bx - 10 * s, by - 340 * s), (bx + w + 10 * s, by - 340 * s), (bx + w + 30 * s, by + 10 * s), (bx - 30 * s, by + 10 * s)])
            cv.drawPath(net, fill('#ffffff', 0.35))
            for k in range(14):
                u = k / 13
                cv.drawLine(bx - 10 * s + (w + 20 * s) * u, by - 340 * s, bx - 30 * s + (w + 60 * s) * u, by + 10 * s, stroke('#ffffff', 2, 0.35))
            cv.drawPath(net, ink(2.5, 0.6))
        # string of bulbs
        for k in range(12):
            x = -300 + k * 160
            y = 780 + 50 * math.sin(k * 0.9)
            cv.drawCircle(x, y, 13, fill('#f8e0a0')); cv.drawCircle(x, y, 13, ink(2.5))
            E_roof.append(dict(kind='lamp', pos=(x, y), r=90, lit=night or mood in ('sunset', 'dawn')))
        cv.drawPath(path_smooth([(-300 + k * 160, 770 + 50 * math.sin(k * 0.9)) for k in range(12)], close=False), stroke('#2a2232', 3))

    def near(cv):
        sk.plant_pot(cv, 1180, 2500, s=4.2, col='#c8603a', seed=4)

    return [
        ('sky', 30.0, sky, dict(grade=False)),
        ('city', 10.0, city, dict(lights=_lights(E_city, night), haze=0.15)),
        ('roof', 1.0, roof, dict(lights=_lights(E_roof, True))),
        ('near', 0.6, near, dict(blur=12)),
    ], dict(ground_y=1600)


REGISTRY = {'chaikhana': chaikhana, 'souq': souq, 'shatt': shatt, 'classroom': classroom, 'rooftop': rooftop}
