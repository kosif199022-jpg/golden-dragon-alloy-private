#!/usr/bin/env python3
"""Red Rose lift: take the burned-in text of a reference video pixel for pixel, with its motion, and put it on new footage.

A text overlay is pixels laid over the footage: I = a*O + (1-a)*B (O = text colour, a = its opacity, B = footage).
  1. sprite  - in frames where the text stands still, estimate B by inpainting around the text and solve for the
               smallest a and its O per pixel (min-alpha un-compositing); over many frames (each with another
               background) keep the upper percentile of a, so every pixel of fill, outline, shadow and anti-aliasing
               comes from the source itself.
  2. track   - follow the text in every frame: an affine warp (zoom, shift) by ECC on the text-colour map, its
               opacity by projecting (I-B) on (O-B), and a horizontal motion blur during whip cuts.
  3. render  - warp the sprite with those numbers, blur, multiply by the opacity and write RGBA overlay frames
               (1080x1920) for the fast-reel engine (spec "overlay").
  4. verify  - compare the overlay with the source in every frame: colour difference on the text core and
               overlap of the text masks.

usage:
  lift.py extract VIDEO items.json OUTDIR          sprites + tracks (OUTDIR/items/*.png, tracks.json)
  lift.py render  OUTDIR [--fps 30] [--dur S]      OUTDIR/ov/f0001.png ...
  lift.py verify  VIDEO OUTDIR                     per-item colour difference and mask overlap vs the source
items.json: [{"name": "line3", "box": [x0,y0,x1,y1] (1080x1920 coords), "span": [t_in, t_out] (when it shows),
              "steady": [[t0,t1], ...] (frames where it stands still), "colours": ["#fbfbfb"], "tol": 110,
              "samples": 8 (frames taken per steady span), "matting": "regression" (many backgrounds: exact opacity),
              "neutral_edges": true (white text: no tint), "dark_edges": true (rim = black shadow), "show": [t0,t1], "borrow": [...]}, ...]
Everything runs on the source's own resolution; the overlay is scaled to 1080x1920 at render time.
"""
import argparse, json, os, subprocess, sys
import numpy as np, cv2

FPS = 30


def probe(video):
    out = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height',
                          '-of', 'csv=p=0', video], capture_output=True, text=True).stdout.strip().split(',')
    return int(out[0]), int(out[1])


def decode(video, t0, t1, crop):
    """Frames [t0, t1) at 30 fps, cropped to (x, y, w, h) in native pixels -> (times, uint8 array)."""
    x, y, w, h = crop
    t0 = round(max(0, t0) * FPS) / FPS                          # on the frame grid: frame i is exactly t0 + i/FPS
    cmd = ['ffmpeg', '-v', 'error', '-ss', f'{max(0, t0):.3f}', '-i', video, '-t', f'{t1 - t0:.3f}', '-vf',
           f'fps={FPS},crop={w}:{h}:{x}:{y}', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-']
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    fr = np.frombuffer(raw, np.uint8).reshape(-1, h, w, 3)
    return [t0 + i / FPS for i in range(len(fr))], fr


def hexbgr(c):
    c = c.lstrip('#'); return np.array([int(c[4:6], 16), int(c[2:4], 16), int(c[0:2], 16)], np.float32)


def softfill(img, cols, tol):
    """1 on the text colours, falling to 0 at distance tol (sum of |dB|+|dG|+|dR|)."""
    f = img.astype(np.float32); s = np.zeros(img.shape[:2], np.float32)
    for c in cols:
        s = np.maximum(s, np.clip(1 - np.abs(f - c).sum(2) / tol, 0, 1))
    return s


def unblend(I, B):
    """Smallest opacity a and colour O with I = a*O + (1-a)*B."""
    I = I.astype(np.float32); B = B.astype(np.float32)
    up = np.where(I > B, (I - B) / np.maximum(255 - B, 1), (B - I) / np.maximum(B, 1))
    a = np.clip(up.max(2), 0, 1)
    O = np.clip(B + (I - B) / np.maximum(a, 1e-3)[..., None], 0, 255)
    return a, O


def ecc(template, img, warp, iters=80):
    try:
        cc, w = cv2.findTransformECC(template, img, warp.copy(), cv2.MOTION_AFFINE,
                                     (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, iters, 1e-5), None, 5)
        return cc, w
    except cv2.error:
        return -1, warp


def build_sprite(frames, cols, tol, pad, neutral=False, regress=False, dark_edges=False):
    """frames: steady frames (cropped). Returns RGBA sprite (float O, float a) in the reference frame's coordinates."""
    k = np.ones((3, 3), np.uint8)
    fills = [softfill(f, cols, tol) for f in frames]
    # reference: the frame whose background around the text is darkest (text separates best)
    def ring_luma(f, s):
        m = (s > 0.5).astype(np.uint8); r = cv2.dilate(m, k, iterations=6) - cv2.dilate(m, k, iterations=2)
        return cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)[r > 0].mean() if r.any() else 255
    ri = int(np.argmin([ring_luma(f, s) for f, s in zip(frames, fills)]))
    def feat(f, s):      # text colour + its edges: holds on a bright background where the colour map alone floods
        g = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY).astype(np.float32)
        e = cv2.magnitude(cv2.Sobel(g, cv2.CV_32F, 1, 0), cv2.Sobel(g, cv2.CV_32F, 0, 1)); e /= max(float(np.percentile(e, 99)), 1)
        return cv2.GaussianBlur(np.clip(e, 0, 1) * 0.6 + s * 0.4, (5, 5), 0)
    ref = feat(frames[ri], fills[ri])
    aligned = []
    for f, s in zip(frames, fills):
        cc, w = ecc(ref, feat(f, s), np.eye(2, 3, dtype=np.float32))
        if cc < 0.6: continue
        g = cv2.warpAffine(f, w, (f.shape[1], f.shape[0]), flags=cv2.INTER_CUBIC | cv2.WARP_INVERSE_MAP, borderMode=cv2.BORDER_REPLICATE)
        aligned.append((g, cv2.warpAffine(s, w, (f.shape[1], f.shape[0]), flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP)))
    if not aligned: sys.exit('no steady frame aligned with the reference: check the steady spans')
    # where the text is: the text colour in most frames (median), so hairlines, dots and tanween count too,
    # and a bright background patch (only behind it in some frames) does not
    med = np.median(np.stack([x[1] for x in aligned]), 0)
    core = (med > 0.3).astype(np.uint8)
    # small marks a little away from the letters (tanween, hamza): text-coloured in most frames, lighter than the
    # ring around them (their outline), within a few pixels of a letter
    mimg0 = cv2.cvtColor(np.median(np.stack([x[0] for x in aligned]), 0).astype(np.uint8), cv2.COLOR_BGR2GRAY).astype(np.float32)
    hi = np.percentile(np.stack([x[1] for x in aligned]), 80, axis=0)     # 1-px marks blur under alignment: upper quantile
    cand = ((hi > 0.15) & (cv2.dilate(core, k, iterations=10) > 0) & (core == 0)).astype(np.uint8)
    cand = cv2.dilate(cand, k)
    n, lab, st, _ = cv2.connectedComponentsWithStats(cand, 8)
    for i in range(1, n):
        if st[i, cv2.CC_STAT_AREA] > 60: continue
        comp = (lab == i).astype(np.uint8); ring = cv2.dilate(comp, k, iterations=2) - comp
        if ring.any() and mimg0[comp > 0].mean() - mimg0[ring > 0].mean() >= 30: core[comp > 0] = 1
    if len(aligned) >= 6:
        # and every pixel that keeps its colour while the footage under it changes (outlines, hairlines, tashkeel)
        G = np.stack([x[0] for x in aligned]).astype(np.float32)
        sd = G.std(0).mean(2); bgsd = np.median(sd)
        still = (sd < max(10.0, 0.35 * bgsd)).astype(np.uint8)
        near = cv2.dilate(core, k, iterations=4)
        core = core | (still & near)
    n, lab, st, _ = cv2.connectedComponentsWithStats(core, 8)
    keep = np.zeros_like(core)
    for i in range(1, n):
        if st[i, cv2.CC_STAT_AREA] >= 2: keep[lab == i] = 1
    U = cv2.dilate(keep, k, iterations=pad)                          # text + outline + shadow live here
    As, Os, Is, Bs = [], [], [], []
    for g, _ in aligned:
        B = cv2.inpaint(g, cv2.dilate(U, k, iterations=2), 4, cv2.INPAINT_TELEA)
        a, O = unblend(g, B); a[U == 0] = 0
        As.append(a); Os.append(O); Is.append(g.astype(np.float32)); Bs.append(B.astype(np.float32))
    if not As: sys.exit('no steady frame aligned with the reference: check the steady spans')
    A = np.stack(As); O = np.stack(Os)
    a = np.percentile(A, 75, axis=0)
    w = A ** 2 + 1e-6
    o = (O * w[..., None]).sum(0) / w.sum(0)[..., None]
    if regress and len(Is) >= 20:
        # many backgrounds under the same pixel: I_k = a*O + (1-a)*B_k is a straight line in B_k, its slope is
        # 1-a and its intercept a*O, so a dark outline is told apart from a see-through shadow exactly
        I = np.stack(Is); Bk = np.stack(Bs); mI, mB = I.mean(0), Bk.mean(0)
        vB = ((Bk - mB) ** 2).mean(0); cIB = ((I - mB * 0 - mI) * (Bk - mB)).mean(0)
        okc = vB > 150
        slope = np.where(okc, cIB / np.maximum(vB, 1e-3), np.nan)
        sl = np.nanmean(np.where(okc, slope, np.nan), axis=2)
        ok = (okc.sum(2) >= 2) & (U > 0)
        ar = np.clip(1 - sl, 0, 1)
        orr = np.clip((mI - (1 - ar)[..., None] * mB) / np.maximum(ar, 1e-3)[..., None], 0, 255)
        use = ok & (ar > 0.05)
        a = np.where(use, ar, a); o = np.where(use[..., None], orr, o)
    a[a < 0.04] = 0
    seed = (core > 0).astype(np.uint8)
    # a text piece is lighter than the ring around it (its outline / shadow); a light patch of footage is not
    mimg = cv2.cvtColor(np.median(np.stack([x[0] for x in aligned]), 0).astype(np.uint8), cv2.COLOR_BGR2GRAY).astype(np.float32)
    n, lab, st, _ = cv2.connectedComponentsWithStats(seed, 8)
    for i in range(1, n):
        comp = (lab == i).astype(np.uint8); ring = cv2.dilate(comp, k, iterations=2) - comp
        if ring.any() and mimg[comp > 0].mean() - mimg[ring > 0].mean() < 25: seed[comp > 0] = 0
    n, lab, st, _ = cv2.connectedComponentsWithStats((a > 0.1).astype(np.uint8), 8)
    for i in range(1, n):
        comp = lab == i
        if seed[comp].sum() < max(1, 0.12 * comp.sum()): a[comp] = 0   # a still patch of footage, not text
    if neutral:    # white text: outline and shadow are neutral; a tint at the soft edge is footage leaking in
        lum = o.mean(2, keepdims=True); edge = (np.abs(o - cols[0]).sum(2) > 90)[..., None]
        o = np.where(edge, lum, o)
    if dark_edges:   # the soft rim around the letters is the source's shadow: black with partial opacity, not the footage tint
        far = np.ones(o.shape[:2], bool)
        for c in cols: far &= np.abs(o - c).sum(2) > 160
        o = np.where(far[..., None], np.minimum(o, 24), o)
    return o, a, len(As), ri


def track(times, frames, O, A, cols, tol):
    """Per frame: affine warp (sprite -> frame), opacity, horizontal blur (px). Frames where the text is not found get
    the nearest warp; opacity and blur are then measured with that warp."""
    h, w = frames[0].shape[:2]
    tmpl = cv2.GaussianBlur(softfill(O.astype(np.uint8), cols, tol) * np.minimum(A * 1.5, 1), (5, 5), 0).astype(np.float32)
    core = (A > 0.85) & (softfill(O.astype(np.uint8), cols, tol) > 0.5)
    k = np.ones((3, 3), np.uint8)
    warps, good = [None] * len(frames), [False] * len(frames)
    sf = [cv2.GaussianBlur(softfill(f, cols, tol), (5, 5), 0) for f in frames]
    # start where the text is best seen (the sprite's own frame lies in the steady middle) and walk both ways,
    # so the fade-in / fade-out frames start from a warp that already fits
    scores = [ecc(tmpl, sf[i], np.eye(2, 3, dtype=np.float32), 40)[0] for i in range(0, len(frames), max(1, len(frames) // 12))]
    mid = int(np.argmax(scores)) * max(1, len(frames) // 12)
    for order in (range(mid, len(frames)), range(mid - 1, -1, -1)):
        W = np.eye(2, 3, dtype=np.float32) if not good[mid] else warps[mid]
        for i in order:
            cc, w2 = ecc(tmpl, sf[i], W)
            if cc >= 0.6:
                warps[i], good[i], W = w2, True, w2
    gi = [i for i, g in enumerate(good) if g]
    if not gi: return None
    for i in range(len(frames)):
        if warps[i] is None: warps[i] = warps[min(gi, key=lambda j: abs(j - i))]
    out = []
    for i, f in enumerate(frames):
        Wi = warps[i]; blur = 0
        if not good[i]:          # whip / fade: try motion blur and a sideways shift on the nearest warp
            sf = cv2.GaussianBlur(softfill(f, cols, tol), (5, 5), 0)
            best = (-1, 0, 0)
            for kb in (0, 4, 8, 16, 32, 64):
                tw = cv2.warpAffine(tmpl, Wi, (w, h))
                if kb: tw = cv2.blur(tw, (kb, 1))
                for dx in range(-40, 41, 4):
                    t2 = np.roll(tw, dx, 1); c = float((t2 * sf).sum() / (np.sqrt((t2 ** 2).sum() * (sf ** 2).sum()) + 1e-6))
                    if c > best[0]: best = (c, kb, dx)
            blur = best[1]; Wi = Wi.copy(); Wi[0, 2] += best[2]
        # opacity: project the frame on the sprite colour over the text core
        cw = cv2.warpAffine(core.astype(np.uint8), Wi, (w, h), flags=cv2.INTER_NEAREST)
        Ow = cv2.warpAffine(O.astype(np.float32), Wi, (w, h))
        if blur: Ow = cv2.blur(Ow, (blur, 1)); cw = cv2.erode(cw, np.ones((1, blur + 1), np.uint8))
        aw = cv2.warpAffine(A.astype(np.float32), Wi, (w, h))
        B = cv2.inpaint(f, cv2.dilate((aw > 0.03).astype(np.uint8), k, iterations=2), 4, cv2.INPAINT_TELEA).astype(np.float32)
        I = f.astype(np.float32); m = (cw > 0) & (np.abs(Ow - B).sum(2) > 60)
        op = float(((I - B) * (Ow - B)).sum(2)[m].sum() / max(((Ow - B) ** 2).sum(2)[m].sum(), 1)) if m.sum() > 20 else 0.0
        out.append(dict(t=round(times[i], 4), warp=Wi.tolist(), opacity=round(float(np.clip(op, 0, 1)), 3), blur=int(blur), found=good[i]))
    return out


def cmd_extract(a):
    W, H = probe(a.video); s = W / 1080
    items = json.load(open(a.items)); os.makedirs(os.path.join(a.out, 'items'), exist_ok=True)
    meta = dict(native=[W, H], items=[])
    for it in items:
        x0, y0, x1, y1 = [int(round(v * s)) // 2 * 2 for v in it['box']]      # even: ffmpeg crops yuv420 on even pixels
        crop = (x0, y0, x1 - x0, y1 - y0); cols = [hexbgr(c) for c in it.get('colours', ['#fbfbfb'])]; tol = it.get('tol', 110)
        steady = []
        for t0, t1 in it['steady']:
            ts, fr = decode(a.video, t0, t1, crop); step = max(1, len(fr) // it.get('samples', 8)); steady += list(fr[::step])
        O, A, used, ri = build_sprite(steady, cols, tol, it.get('pad', 4), it.get('neutral_edges', False), it.get('matting') == 'regression', it.get('dark_edges', False))
        p = os.path.join(a.out, 'items', it['name'] + '.png')
        cv2.imwrite(p, np.dstack([O.astype(np.uint8), (A * 255).astype(np.uint8)]))
        ts, fr = decode(a.video, it['span'][0], it['span'][1], crop)
        tr = track(ts, fr, O, A, cols, tol)
        if tr is None: sys.exit(f'{it["name"]}: the text was not found in its span')
        if it.get('show'):      # outside its own time the same font in the same place belongs to the line before/after
            for r in tr:
                if not (it['show'][0] <= r['t'] <= it['show'][1]): r['opacity'] = 0.0
        nf = sum(x['found'] for x in tr)
        print(f'{it["name"]}: sprite from {used} frames, tracked {nf}/{len(tr)} frames directly')
        meta['items'].append(dict(name=it['name'], crop=list(crop), sprite=os.path.relpath(p, a.out), track=tr))
    # borrow: a mark that cannot be separated in its own shot (white hamza over a white wall) is taken from the same
    # mark in another line of the same source: {"borrow": [{"from": "line07", "src": [x0,y0,x1,y1], "dst": [x, y]}]}
    for it in items:
        for b in it.get('borrow', []):
            dp = os.path.join(a.out, 'items', it['name'] + '.png'); D = cv2.imread(dp, cv2.IMREAD_UNCHANGED).astype(np.float32)
            Sx = cv2.imread(os.path.join(a.out, 'items', b['from'] + '.png'), cv2.IMREAD_UNCHANGED).astype(np.float32)
            x0, y0, x1, y1 = b['src']; X, Y = b['dst']; P = Sx[y0:y1, x0:x1]; T = D[Y:Y + y1 - y0, X:X + x1 - x0]
            pa, ta = P[..., 3:4] / 255, T[..., 3:4] / 255; oa = pa + ta * (1 - pa)
            oc = (P[..., :3] * pa + T[..., :3] * ta * (1 - pa)) / np.maximum(oa, 1e-4)
            D[Y:Y + y1 - y0, X:X + x1 - x0] = np.dstack([oc, oa * 255]); cv2.imwrite(dp, np.clip(D, 0, 255).astype(np.uint8))
            print(f"{it['name']}: borrowed {b['src']} from {b['from']}")
    json.dump(meta, open(os.path.join(a.out, 'tracks.json'), 'w'))


def cmd_render(a):
    M = json.load(open(os.path.join(a.out, 'tracks.json'))); NW, NH = M['native']; s = 1080 / NW
    dur = a.dur or max(x['track'][-1]['t'] for x in M['items']) + 0.5
    n = int(round(dur * FPS)); od = os.path.join(a.out, 'ov'); os.makedirs(od, exist_ok=True)
    spr = {}
    for it in M['items']:
        im = cv2.imread(os.path.join(a.out, it['sprite']), cv2.IMREAD_UNCHANGED).astype(np.float32) / 255
        spr[it['name']] = (im[..., :3] * im[..., 3:4], im[..., 3])          # premultiplied
    byf = {}
    for it in M['items']:
        for r in it['track']: byf.setdefault(int(round(r['t'] * FPS + 1e-6)), []).append((it, r))
    S = np.array([[s, 0, 0], [0, s, 0], [0, 0, 1]], np.float64)
    for fi in range(n):
        rgb = np.zeros((1920, 1080, 3), np.float32); al = np.zeros((1920, 1080), np.float32)
        for it, r in byf.get(fi, []):
            if r['opacity'] <= 0.01: continue
            x, y = it['crop'][:2]
            Wn = np.vstack([np.array(r['warp']), [0, 0, 1]]); Tc = np.array([[1, 0, x], [0, 1, y], [0, 0, 1]], np.float64)
            # sprite (native crop coords) -> native frame -> 1080 frame; the sprite itself is sampled at native size
            Mx = (S @ Tc @ Wn)[:2]
            pc, pa = spr[it['name']]
            wc = cv2.warpAffine(pc, Mx, (1080, 1920), flags=cv2.INTER_CUBIC); wa = cv2.warpAffine(pa, Mx, (1080, 1920), flags=cv2.INTER_CUBIC)
            if r['blur']:
                kb = max(1, int(round(r['blur'] * s))); wc = cv2.blur(wc, (kb, 1)); wa = cv2.blur(wa, (kb, 1))
            o = r['opacity']; wc = np.clip(wc, 0, 1) * o; wa = np.clip(wa, 0, 1) * o
            rgb = wc + rgb * (1 - wa[..., None]); al = wa + al * (1 - wa)
        un = np.where(al[..., None] > 1e-4, rgb / np.maximum(al[..., None], 1e-4), 0)
        cv2.imwrite(os.path.join(od, f'f{fi + 1:04d}.png'), np.dstack([np.clip(un * 255, 0, 255), np.clip(al * 255, 0, 255)]).astype(np.uint8),
                    [cv2.IMWRITE_PNG_COMPRESSION, 1])
    print(f'{n} overlay frames -> {od}')


def cmd_verify(a):
    """Every tracked frame: the sprite, warped by its track at the source's own size, against the source pixels.
    Colour difference where the text is opaque (> 0.9) and fully shown (opacity > 0.9, no whip blur)."""
    M = json.load(open(os.path.join(a.out, 'tracks.json'))); NW, NH = M['native']; ok = True
    for it in M['items']:
        x, y, w, h = it['crop']; tr = [r for r in it['track'] if r['opacity'] >= 0.9 and not r['blur']]
        if not tr: continue
        im = cv2.imread(os.path.join(a.out, it['sprite']), cv2.IMREAD_UNCHANGED).astype(np.float32)
        ts, fr = decode(a.video, it['track'][0]['t'], it['track'][-1]['t'] + 0.05, (x, y, w, h)); diffs = []
        for r in tr[::2]:
            fi = int(round((r['t'] - ts[0]) * FPS))
            if fi >= len(fr): continue
            Wm = np.array(r['warp'], np.float32)
            c = cv2.warpAffine(im[..., :3], Wm, (w, h), flags=cv2.INTER_LINEAR); al = cv2.warpAffine(im[..., 3], Wm, (w, h), flags=cv2.INTER_LINEAR)
            m = al > 230
            if m.sum() > 30: diffs.append(float(np.abs(fr[fi].astype(np.float32)[m] - c[m]).mean()))
        if diffs:
            d = float(np.median(diffs)); good = d <= a.max_diff; ok &= good
            print(f"{'✅' if good else '❌'} {it['name']}: median colour difference on opaque text {d:.1f}/255 ({len(diffs)} frames)")
    print('✅ text matches the source' if ok else '❌ some items differ: re-check their steady spans / colours')
    sys.exit(0 if ok else 1)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter); s = p.add_subparsers(dest='cmd', required=True)
    e = s.add_parser('extract'); e.add_argument('video'); e.add_argument('items'); e.add_argument('out')
    r = s.add_parser('render'); r.add_argument('out'); r.add_argument('--dur', type=float)
    v = s.add_parser('verify'); v.add_argument('video'); v.add_argument('out'); v.add_argument('--max-diff', type=float, default=12)
    a = p.parse_args(); {'extract': cmd_extract, 'render': cmd_render, 'verify': cmd_verify}[a.cmd](a)


if __name__ == '__main__':
    main()
