#!/usr/bin/env python3
"""Red Rose mimic: copy the text of a reference video to the pixel.

  fonts                      build the font pool index (every font file we have) -> ~/.red-rose/mimic_fonts.json
  google [FAMILY ...] [--set arabic|latin|all]
                             download Google Fonts (TTF, OFL/Apache) into ~/.red-rose/fonts/google, then re-index
  detect VIDEO [--t0 --t1]   find the text that stays still over the footage (headers, handles, stickers)
  measure FRAME --box x0,y0,x1,y1 [--text "..."]
                             ink box, fill colour, outline colour and width, shadow, and (with --text)
                             the best fonts by pixel overlap -> element JSON usable by main.js ink()
  trace FRAME --box ...      no font close enough: trace the reference ink into an SVG path (a font built
                             from the reference for this exact word), with its fill and outline colours.
                             Over moving footage use --tmin T0,T1 (per-pixel minimum: clean, keeps the dots);
                             a multi-colour header is one trace per colour with --colour #rrggbb [--tol N]
  verify REF OURS --elements elements.json
                             compare our frame with the reference element by element (overlap + colour)

All coordinates are in a 1080x1920 frame (smaller references are scaled up first).
Run with python3 -I. Nothing here needs the network.
"""
import argparse, json, os, subprocess, sys, hashlib, tempfile
import numpy as np, cv2

HERE = os.path.dirname(os.path.abspath(__file__))
W, H = 1080, 1920
POOL = os.path.expanduser('~/.red-rose/mimic_fonts.json')
ARABIC = ['Amiri', 'Amiri Quran', 'Aref Ruqaa', 'Aref Ruqaa Ink', 'Alkalami', 'Almarai', 'Alexandria', 'Baloo Bhaijaan 2', 'Blaka',
          'Blaka Hollow', 'Cairo', 'Cairo Play', 'Changa', 'El Messiri', 'Gulzar', 'Harmattan', 'IBM Plex Sans Arabic', 'Jomhuria',
          'Katibeh', 'Kufam', 'Lalezar', 'Lateef', 'Lemonada', 'Mada', 'Marhey', 'Markazi Text', 'Mirza', 'Noto Kufi Arabic',
          'Noto Naskh Arabic', 'Noto Nastaliq Urdu', 'Noto Sans Arabic', 'Qahiri', 'Rakkas', 'Readex Pro', 'Reem Kufi', 'Reem Kufi Fun',
          'Reem Kufi Ink', 'Ruwudu', 'Scheherazade New', 'Tajawal', 'Vibes', 'Zain', 'Handjet', 'Noto Sans Arabic UI', 'Rubik',
          'Vazirmatn', 'Playpen Sans Arabic', 'Badeen Display', 'Beiruti', 'Kalam', 'Lalezar', 'Mestika']
LATIN = ['Tinos', 'Arimo', 'Cousine', 'Noto Serif', 'PT Serif', 'Libre Baskerville', 'Playfair Display', 'Merriweather', 'Source Serif 4',
         'Crimson Text', 'Cormorant Garamond', 'EB Garamond', 'Lora', 'Roboto', 'Roboto Slab', 'Roboto Condensed', 'Montserrat', 'Open Sans',
         'Poppins', 'Oswald', 'Bebas Neue', 'Anton', 'Inter', 'Lato', 'Raleway', 'Nunito', 'Work Sans', 'DM Serif Display', 'Abril Fatface',
         'Cinzel', 'Great Vibes', 'Dancing Script', 'Pacifico', 'Lobster', 'Satisfy', 'Sacramento', 'Allura', 'Parisienne', 'Josefin Sans',
         'Quicksand', 'Comfortaa', 'Fredoka', 'Archivo Black', 'Alfa Slab One', 'Righteous', 'Permanent Marker', 'Caveat', 'Kaushan Script',
         'Marcellus', 'Philosopher', 'Prata', 'Old Standard TT', 'Bodoni Moda', 'Spectral', 'Zilla Slab', 'Bitter', 'Arvo', 'Ubuntu',
         'Barlow', 'Barlow Condensed', 'Manrope', 'Outfit', 'Sora', 'Urbanist', 'Teko', 'Fjalla One', 'Passion One', 'Russo One']
DEFAULT_DIRS = ['~/.red-rose/fonts', '~/fastfonts', '/home/user/work/fonts/lib', '/home/user/work/tue2/gf',
                '/home/user/work/tue2/cal', '/mnt/skills/examples/canvas-design/canvas-fonts']


def load_frame(p, t=None):
    if p.lower().endswith(('.mp4', '.mov', '.webm', '.mkv')):
        tmp = tempfile.mktemp(suffix='.png')
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', str(t or 0), '-i', p, '-frames:v', '1', tmp], check=True)
        p = tmp
    im = cv2.imread(p, cv2.IMREAD_COLOR)
    if im is None: sys.exit(f'cannot read {p}')
    if im.shape[1] != W: im = cv2.resize(im, (W, round(im.shape[0] * W / im.shape[1])), interpolation=cv2.INTER_CUBIC)
    return im


def drop_border(m):
    """Pieces that touch the box edge belong to a neighbour (a descender from the line above, an underline)."""
    n, lab, st, _ = cv2.connectedComponentsWithStats(m, 8); h, w = m.shape; out = m.copy()
    for i in range(1, n):
        x, y, bw, bh = st[i, 0], st[i, 1], st[i, 2], st[i, 3]
        if (y == 0 or y + bh >= h or x == 0 or x + bw >= w) and st[i, cv2.CC_STAT_AREA] < m.sum() * 0.12 and bh < h * 0.5: out[lab == i] = 0
    return out


def ink_mask(crop, polarity='auto'):
    """Text ink inside a box: Otsu on luma, polarity = the side that touches the border less."""
    g = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    _, th = cv2.threshold(g, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    cand = {'light': th > 0, 'dark': th == 0}
    if polarity == 'auto':
        def border(m): return np.concatenate([m[0], m[-1], m[:, 0], m[:, -1]]).mean()
        polarity = min(cand, key=lambda k: border(cand[k]))
    m = cand[polarity].astype(np.uint8)
    n, lab, st, _ = cv2.connectedComponentsWithStats(m, 8)
    keep = np.zeros_like(m)
    for i in range(1, n):
        if st[i, cv2.CC_STAT_AREA] >= max(4, m.size * 0.0004): keep[lab == i] = 1
    return drop_border(keep), polarity


def colours(crop, m):
    """Fill = median under the eroded ink; outline = ring just outside when it differs from fill and background."""
    k = np.ones((3, 3), np.uint8)
    core = cv2.erode(m, k) if cv2.erode(m, k).sum() > 20 else m
    fill = np.median(crop[core > 0], axis=0)
    ring1 = cv2.dilate(m, k, iterations=3) - m
    ring2 = cv2.dilate(m, k, iterations=9) - cv2.dilate(m, k, iterations=5)
    c1, c2 = np.median(crop[ring1 > 0], axis=0), np.median(crop[ring2 > 0], axis=0)
    hexc = lambda c: '#%02x%02x%02x' % (int(c[2]), int(c[1]), int(c[0]))
    lum = lambda c: 0.114 * c[0] + 0.587 * c[1] + 0.299 * c[2]
    out = {'fill': hexc(fill)}
    if abs(lum(c1) - lum(fill)) > 60 and np.abs(c1 - c2).sum() > 60:
        width = 1
        for it in range(2, 9):
            r = cv2.dilate(m, k, iterations=it) - cv2.dilate(m, k, iterations=it - 1)
            if r.sum() == 0 or abs(lum(np.median(crop[r > 0], axis=0)) - lum(c1)) > 45: break
            width = it
        out['outline'] = hexc(c1); out['outline_px'] = width
    # soft shadow: background just below-right of the ink darker than further away
    sh = np.roll(np.roll(m, 4, 0), 2, 1) & (1 - cv2.dilate(m, k, iterations=2))
    if sh.sum() > 20 and lum(np.median(crop[sh > 0], axis=0)) < lum(c2) - 18: out['shadow'] = True
    return out


def box_of(m, x0, y0):
    ys, xs = np.nonzero(m)
    return [int(x0 + xs.min()), int(y0 + ys.min()), int(x0 + xs.max() + 1), int(y0 + ys.max() + 1)]


def cmd_fonts(a):
    dirs = a.dirs or DEFAULT_DIRS; seen = set(); pool = []
    for d in dirs:
        d = os.path.expanduser(d)
        for r, _, fs in os.walk(d):
            for f in fs:
                if f.startswith('._') or not f.lower().endswith(('.ttf', '.otf')): continue
                p = os.path.join(r, f)
                try: h = hashlib.md5(open(p, 'rb').read()).hexdigest()
                except OSError: continue
                if h in seen: continue
                seen.add(h); pool.append(p)
    os.makedirs(os.path.dirname(POOL), exist_ok=True)
    json.dump(pool, open(POOL, 'w'), ensure_ascii=False, indent=0)
    print(f'{len(pool)} unique fonts -> {POOL}')


def cmd_google(a):
    import urllib.request, re
    fam = list(a.families) + (ARABIC if a.set in ('arabic', 'all') else []) + (LATIN if a.set in ('latin', 'all') else [])
    out = os.path.expanduser('~/.red-rose/fonts/google'); os.makedirs(out, exist_ok=True); got = 0
    for f in dict.fromkeys(fam):
        for w in a.weights.split(','):
            url = 'https://fonts.googleapis.com/css2?family=' + f.replace(' ', '+') + f':wght@{w}'
            try:
                css = urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'curl'}), timeout=20).read().decode()
            except Exception:
                if w == a.weights.split(',')[0]:
                    try: css = urllib.request.urlopen(urllib.request.Request(url.split(':wght')[0], headers={'User-Agent': 'curl'}), timeout=20).read().decode()
                    except Exception: print('  not found:', f); break
                else: continue
            for src in dict.fromkeys(re.findall(r'url\((https://fonts.gstatic.com/[^)]+\.ttf)\)', css)):
                dst = os.path.join(out, f.replace(' ', '') + f'-{w}-' + os.path.basename(src))
                if not os.path.exists(dst):
                    try: open(dst, 'wb').write(urllib.request.urlopen(src, timeout=30).read()); got += 1
                    except Exception as e: print('  failed', f, w, e)
    print(f'downloaded {got} new files into {out}'); a.dirs = None; cmd_fonts(a)


def cmd_detect(a):
    """Static overlay text: low change over time + strong edges, grouped into boxes."""
    cap_t = np.linspace(a.t0, a.t1, a.n)
    frames = [cv2.cvtColor(load_frame(a.video, t), cv2.COLOR_BGR2GRAY).astype(np.float32) for t in cap_t]
    st = np.stack(frames); std = st.std(0); mean = st.mean(0).astype(np.uint8)
    edges = cv2.Laplacian(mean, cv2.CV_32F, ksize=3)
    text = ((std < a.std) & (np.abs(edges) > 25)).astype(np.uint8)
    text = cv2.morphologyEx(text, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
    text = cv2.morphologyEx(text, cv2.MORPH_CLOSE, np.ones((15, 41), np.uint8))
    n, lab, s, _ = cv2.connectedComponentsWithStats(text, 8)
    boxes = [[int(s[i, 0]), int(s[i, 1]), int(s[i, 0] + s[i, 2]), int(s[i, 1] + s[i, 3])] for i in range(1, n)
             if s[i, cv2.CC_STAT_AREA] > 600 and s[i, 3] > 16]
    merged = True                       # merge boxes that touch after a small pad (one word split in two)
    while merged:
        merged = False
        for i in range(len(boxes)):
            for j in range(i + 1, len(boxes)):
                A, B = boxes[i], boxes[j]
                if A[0] - 10 < B[2] and B[0] - 10 < A[2] and A[1] - 6 < B[3] and B[1] - 6 < A[3]:
                    boxes[i] = [min(A[0], B[0]), min(A[1], B[1]), max(A[2], B[2]), max(A[3], B[3])]; boxes.pop(j); merged = True; break
            if merged: break
    boxes.sort(key=lambda b: (b[1], b[0]))
    vis = cv2.cvtColor(mean, cv2.COLOR_GRAY2BGR)
    for i, b in enumerate(boxes):
        cv2.rectangle(vis, tuple(b[:2]), tuple(b[2:]), (0, 0, 255), 3); cv2.putText(vis, str(i), (b[0], b[1] - 6), 0, 1.2, (0, 0, 255), 3)
    out = a.out or 'detect'; cv2.imwrite(out + '.jpg', cv2.resize(vis, (540, 960)))
    json.dump(boxes, open(out + '.json', 'w')); print(json.dumps(boxes)); print('preview', out + '.jpg')


def run_match(mask_png, text, ltr, fonts, weights):
    job = tempfile.mktemp(suffix='.json')
    json.dump(dict(mask=mask_png, text=text, ltr=ltr, fonts=fonts, weights=weights), open(job, 'w'), ensure_ascii=False)
    # ES modules ignore NODE_PATH: run a copy of match.mjs next to a node_modules link to the global packages
    run = os.path.join(tempfile.gettempdir(), 'rr_mimic'); os.makedirs(run, exist_ok=True)
    nm = os.path.join(run, 'node_modules')
    if not os.path.exists(nm): os.symlink(subprocess.run(['npm', 'root', '-g'], capture_output=True, text=True).stdout.strip(), nm)
    open(os.path.join(run, 'match.mjs'), 'w').write(open(os.path.join(HERE, 'match.mjs')).read())
    r = subprocess.run(['node', os.path.join(run, 'match.mjs'), job], capture_output=True, text=True, cwd=run)
    if r.returncode: sys.exit(r.stderr[-800:])
    return json.loads(r.stdout)


def colour_mask(crop, hexc, tol=90):
    """Ink of one known colour (multi-colour headers: one trace per colour, the other colours stay out)."""
    f = np.array([int(hexc[j:j + 2], 16) for j in (5, 3, 1)], np.float32)
    m = (np.abs(crop.astype(np.float32) - f).sum(2) < tol).astype(np.uint8)
    n, lab, st, _ = cv2.connectedComponentsWithStats(m, 8); keep = np.zeros_like(m)
    for i in range(1, n):
        if st[i, cv2.CC_STAT_AREA] >= 12: keep[lab == i] = 1
    return keep


def static_mask(video, box, t0, t1, n=14, pol='auto', colour=None, tol=90):
    """Overlay text stays still while the footage moves: keep pixels with a low change over time, then
    take the ink polarity by Otsu on the time-median image."""
    x0, y0, x1, y1 = box
    st = np.stack([load_frame(video, t)[y0:y1, x0:x1] for t in np.linspace(t0, t1, n)]).astype(np.float32)
    med = np.median(st, 0).astype(np.uint8); std = st.mean(3).std(0)
    m, pol = (colour_mask(med, colour, tol), 'colour') if colour else ink_mask(med, pol)
    m0 = m.astype(bool)
    thr = max(14.0, 0.6 * float(np.median(std[~m0]))) if (~m0).any() else 14.0
    still = (std < thr).astype(np.uint8)
    m = (m & cv2.dilate(still, np.ones((3, 3), np.uint8)))
    n_, lab, stt, _ = cv2.connectedComponentsWithStats(m, 8); keep = np.zeros_like(m)
    for i in range(1, n_):
        if stt[i, cv2.CC_STAT_AREA] >= (12 if colour else max(6, m.size * 0.0006)): keep[lab == i] = 1   # colour key is clean: keep dots and hamzas
    return med, drop_border(keep), pol


def cmd_measure(a):
    x0, y0, x1, y1 = map(int, a.box.split(','))
    if a.static:
        t0, t1 = map(float, a.static.split(',')); crop, m, pol = static_mask(a.frame, (x0, y0, x1, y1), t0, t1, pol=a.polarity)
        im = load_frame(a.frame, (t0 + t1) / 2); im[y0:y1, x0:x1] = crop
    else:
        im = load_frame(a.frame, a.t); crop = im[y0:y1, x0:x1]; m, pol = ink_mask(crop, a.polarity)
    if m.sum() == 0: sys.exit('no ink found in the box')
    bx = box_of(m, x0, y0); col = colours(crop, m)
    el = dict(box=bx, cx=(bx[0] + bx[2]) / 2, top=bx[1], w=bx[2] - bx[0], h=bx[3] - bx[1], polarity=pol, **col)
    if a.text:
        mm = m[bx[1] - y0:bx[3] - y0, bx[0] - x0:bx[2] - x0] * 255
        mpng = tempfile.mktemp(suffix='.png'); cv2.imwrite(mpng, mm)
        fonts = json.load(open(POOL)) if os.path.exists(POOL) else sys.exit('run: mimic.py fonts')
        if a.only: fonts = [f for f in fonts if any(k.lower() in f.lower() for k in a.only.split(','))]
        sc = [r for r in run_match(mpng, a.text, a.ltr, fonts, [int(w) for w in a.weights.split(',')]) if 'score' in r]
        sc.sort(key=lambda r: -r['score'])
        el['text'] = a.text; el['ltr'] = a.ltr
        el['fonts'] = [dict(font=r['font'], weight=r['w'], score=r['score'], iou=r['iou'], stretch=r['sx']) for r in sc[:a.top]]
        best = sc[0]['score'] if sc else 0
        el['verdict'] = 'font' if best >= a.min_score else 'trace'
        if el['verdict'] == 'font':
            f0 = el['fonts'][0]; el['draw'] = dict(kind='text', text=a.text, ltr=a.ltr, font=f0['font'], weight=f0['weight'],
                                                     cx=el['cx'], top=el['top'], w=el['w'], h=el['h'], fill=el['fill'])
        else:
            el['note'] = f'best font scored {best:.2f} < {a.min_score}: the word is traced from the reference (exact shape)'
            el['draw'] = dict(kind='traced', **trace_mask(m, x0, y0, col))
            if a.text and el['fonts']:        # for another word in the same place: closest font, same box
                f0 = el['fonts'][0]; el['fallback'] = dict(kind='text', ltr=a.ltr, font=f0['font'], weight=f0['weight'],
                                                           cx=el['cx'], top=el['top'], w=el['w'], h=el['h'], fill=el['fill'])
        for k in ('outline', 'outline_px', 'shadow'):
            if k in el: el['draw'][k] = el[k]
        if a.preview: preview(im, bx, el, a.preview)
    out = json.dumps(el, ensure_ascii=False, indent=1)
    if a.out: open(a.out, 'w').write(out)
    print(out)


def preview(im, bx, el, path):
    """Reference ink on top, each candidate font fitted into the same box under it."""
    x0, y0, x1, y1 = bx; ref = im[y0:y1, x0:x1]; h = 120; w = max(1, round(ref.shape[1] * h / ref.shape[0]))
    rows = [cv2.resize(ref, (w, h))]
    try:
        from PIL import Image, ImageDraw, ImageFont, features
        raqm = features.check('raqm')
    except Exception: raqm = False
    for f in el['fonts'][:6]:
        canvas = np.zeros((h, w, 3), np.uint8) + 30
        if raqm:
            img = Image.new('L', (2000, 400)); d = ImageDraw.Draw(img)
            try: fnt = ImageFont.truetype(f['font'], 200, layout_engine=ImageFont.Layout.RAQM)
            except Exception: rows.append(canvas); continue
            d.text((1000, 200), el['text'], fill=255, font=fnt, anchor='mm', direction='ltr' if el['ltr'] else 'rtl')
            arr = np.array(img); ys, xs = np.nonzero(arr > 100)
            if len(xs): canvas[:, :, :] = cv2.resize(arr[ys.min():ys.max() + 1, xs.min():xs.max() + 1], (w, h))[:, :, None]
        cv2.putText(canvas, f"{os.path.basename(f['font'])[:28]} {f['score']:.2f}", (4, 16), 0, .45, (0, 200, 255), 1)
        rows.append(canvas)
    cv2.imwrite(path, np.vstack(rows))


def trace_mask(m, x0, y0, col):
    up = cv2.resize(m * 255, None, fx=4, fy=4, interpolation=cv2.INTER_CUBIC)
    up = cv2.GaussianBlur(up, (5, 5), 0); _, up = cv2.threshold(up, 127, 255, cv2.THRESH_BINARY)
    cs, _ = cv2.findContours(up, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_TC89_KCOS); d = []
    for c in cs:
        c = cv2.approxPolyDP(c, 1.2, True)
        if len(c) < 3: continue
        d.append('M' + ' L'.join(f'{x0 + p[0][0] / 4:.1f} {y0 + p[0][1] / 4:.1f}' for p in c) + ' Z')
    return dict(path=' '.join(d), fill=col['fill'], box=box_of(m, x0, y0))


def cmd_trace(a):
    x0, y0, x1, y1 = map(int, a.box.split(','))
    if a.tmin:   # still text over moving footage: the per-pixel minimum over the span keeps the light ink and darkens the rest
        t0, t1 = map(float, a.tmin.split(','))
        st = np.stack([load_frame(a.frame, t)[y0:y1, x0:x1] for t in np.linspace(t0, t1, a.n)])
        crop = (st.max(0) if a.polarity == 'dark' else st.min(0)).astype(np.uint8)
        m = colour_mask(crop, a.colour, a.tol) if a.colour else ink_mask(crop, 'dark' if a.polarity == 'dark' else 'light')[0]
    elif a.static:
        t0, t1 = map(float, a.static.split(',')); crop, m, _ = static_mask(a.frame, (x0, y0, x1, y1), t0, t1, pol=a.polarity,
                                                                         colour=a.colour, tol=a.tol)
    else:
        im = load_frame(a.frame, a.t); crop = im[y0:y1, x0:x1]
        m = colour_mask(crop, a.colour, a.tol) if a.colour else ink_mask(crop, a.polarity)[0]
    if not m.sum(): sys.exit('no ink found in the box (try another --colour/--tol or --polarity)')
    col = colours(crop, m)
    up = cv2.resize(m * 255, None, fx=4, fy=4, interpolation=cv2.INTER_CUBIC)
    up = cv2.GaussianBlur(up, (5, 5), 0); _, up = cv2.threshold(up, 127, 255, cv2.THRESH_BINARY)
    cs, hier = cv2.findContours(up, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_TC89_KCOS)
    d = []
    for c in cs:
        c = cv2.approxPolyDP(c, 1.2, True)
        if len(c) < 3: continue
        pts = [(x0 + p[0][0] / 4, y0 + p[0][1] / 4) for p in c]
        d.append('M' + ' L'.join(f'{x:.1f} {y:.1f}' for x, y in pts) + ' Z')
    path = ' '.join(d)
    el = dict(kind='traced', box=box_of(m, x0, y0), path=path, **col)
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}"><path d="{path}" fill="{col["fill"]}" fill-rule="evenodd"' + \
          (f' stroke="{col["outline"]}" stroke-width="{col["outline_px"] * 2}" paint-order="stroke"' if 'outline' in col else '') + '/></svg>'
    base = a.out or 'traced'; open(base + '.svg', 'w').write(svg); json.dump(el, open(base + '.json', 'w'))
    print(f'traced {len(d)} shapes -> {base}.svg / {base}.json (draw with new Path2D(el.path), fill-rule evenodd)')


def cmd_verify(a):
    ref, ours = load_frame(a.ref, a.t), load_frame(a.ours, a.t_ours)
    els = json.load(open(a.elements)); els = els if isinstance(els, list) else [els]
    ok_all = True
    for i, e in enumerate(els):
        x0, y0, x1, y1 = e['box']; pad = 14
        X0, Y0, X1, Y1 = max(0, x0 - pad), max(0, y0 - pad), min(W, x1 + pad), min(H, y1 + pad)
        if e.get('fill'):          # the element's own ink colour decides what is text (robust on any footage)
            f = np.array([int(e['fill'][j:j + 2], 16) for j in (5, 3, 1)], np.float32)
            cm = lambda c: drop_border((np.abs(c.astype(np.float32) - f).sum(2) < e.get('tol', 90)).astype(np.uint8))
            mr, mo = cm(ref[Y0:Y1, X0:X1]), cm(ours[Y0:Y1, X0:X1])
        else:
            mr, _ = ink_mask(ref[Y0:Y1, X0:X1], e.get('polarity', 'auto')); mo, _ = ink_mask(ours[Y0:Y1, X0:X1], e.get('polarity', 'auto'))
        k = np.ones((3, 3), np.uint8); inter = (mr & mo).sum(); uni = (mr | mo).sum()
        soft = ((mr & cv2.dilate(mo, k)).sum() / max(1, mr.sum()) + (mo & cv2.dilate(mr, k)).sum() / max(1, mo.sum())) / 2
        br, bo = box_of(mr, X0, Y0) if mr.sum() else None, box_of(mo, X0, Y0) if mo.sum() else None
        cr, co = colours(ref[Y0:Y1, X0:X1], mr)['fill'], colours(ours[Y0:Y1, X0:X1], mo)['fill'] if mo.sum() else '#000000'
        dc = sum(abs(int(cr[j:j + 2], 16) - int(co[j:j + 2], 16)) for j in (1, 3, 5))
        shift = [bo[j] - br[j] for j in range(4)] if br and bo else None
        good = soft >= a.min and dc <= a.max_colour and shift and max(abs(s) for s in shift) <= a.max_px
        ok_all &= bool(good)
        print(f"{'✅' if good else '❌'} element {i} {e.get('text', '')[:24]}: overlap {soft:.2f} (iou {inter / max(1, uni):.2f}), "
              f"colour {cr} vs {co} (Δ{dc}), box shift px {shift}")
    print('✅ matches the reference' if ok_all else '❌ fix the elements marked ❌ (size/position from measure, font from the ranking)')
    sys.exit(0 if ok_all else 1)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter); s = p.add_subparsers(dest='cmd', required=True)
    f = s.add_parser('fonts'); f.add_argument('dirs', nargs='*')
    g = s.add_parser('google'); g.add_argument('families', nargs='*'); g.add_argument('--set', default='', choices=['', 'arabic', 'latin', 'all'])
    g.add_argument('--weights', default='400,700')
    d = s.add_parser('detect'); d.add_argument('video'); d.add_argument('--t0', type=float, default=0.5); d.add_argument('--t1', type=float, default=20)
    d.add_argument('--n', type=int, default=10); d.add_argument('--std', type=float, default=18); d.add_argument('--out')
    m = s.add_parser('measure'); m.add_argument('frame'); m.add_argument('--t', type=float); m.add_argument('--box', required=True)
    m.add_argument('--text'); m.add_argument('--static', help='t0,t1: text that stays still over this span (video input)'); m.add_argument('--ltr', action='store_true'); m.add_argument('--polarity', default='auto', choices=['auto', 'light', 'dark'])
    m.add_argument('--only', help='comma list: keep fonts whose path contains one of these words'); m.add_argument('--weights', default='400,700')
    m.add_argument('--top', type=int, default=8); m.add_argument('--min-score', type=float, default=0.62); m.add_argument('--preview'); m.add_argument('--out')
    t = s.add_parser('trace'); t.add_argument('frame'); t.add_argument('--t', type=float); t.add_argument('--box', required=True)
    t.add_argument('--polarity', default='auto', choices=['auto', 'light', 'dark']); t.add_argument('--out'); t.add_argument('--static')
    t.add_argument('--tmin', help='t0,t1: still light text over moving footage - trace the per-pixel minimum over the span (max with --polarity dark); keeps dots and hamzas')
    t.add_argument('--n', type=int, default=12, help='frames sampled for --tmin')
    t.add_argument('--colour', help='#rrggbb: keep only ink of this colour (one trace per colour of a multi-colour header)')
    t.add_argument('--tol', type=int, default=90, help='colour distance (sum of |dR|+|dG|+|dB|) for --colour')
    v = s.add_parser('verify'); v.add_argument('ref'); v.add_argument('ours'); v.add_argument('--elements', required=True)
    v.add_argument('--t', type=float); v.add_argument('--t-ours', type=float); v.add_argument('--min', type=float, default=0.80)
    v.add_argument('--max-colour', type=int, default=60); v.add_argument('--max-px', type=int, default=8)
    a = p.parse_args(); globals()['cmd_' + a.cmd](a)


if __name__ == '__main__':
    main()
