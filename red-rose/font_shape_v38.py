"""Find fonts that look like a given font, by the shape of their letters.

  rose.py fonts similar NAME [--limit 8]

Each Arabic font draws the same words; the drawing is reduced to a small picture plus a few
measures (ink, stroke width and its spread, straight-edge share, height, corners, slant).
Fonts are compared by distance in that space; other weights of the same family are left out.

Tried and rejected (2026-11-23): predicting a style label from these shapes, trained on labels
taken from font names. Family-grouped cross-validation gave 28-32% accuracy, and confident
predictions were no better, so no label is ever written from shape.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

SAMPLE = 'الحبيبة سكينة كلها نور'
SIZE = 96
CACHE = Path.home() / '.red-rose' / 'fonts' / 'shape_cache.npz'


def features(path: str):
    import cv2
    from PIL import Image, ImageDraw, ImageFont
    try:
        f = ImageFont.truetype(path, SIZE, layout_engine=ImageFont.Layout.RAQM)
    except Exception:
        return None
    img = Image.new('L', (1400, 360), 0)
    ImageDraw.Draw(img).text((1380, 180), SAMPLE, font=f, fill=255, anchor='rm', direction='rtl')
    box = img.getbbox()
    if not box:
        return None
    a = np.asarray(img.crop(box))
    m = (a > 128).astype(np.uint8)
    if m.sum() < 50:
        return None
    h, w = m.shape
    dist = cv2.distanceTransform(m, cv2.DIST_L2, 3)
    skel = cv2.ximgproc.thinning(m * 255) if hasattr(cv2, 'ximgproc') else None
    vals = dist[skel > 0] if skel is not None else dist[m > 0]
    vals = vals[vals > 0]
    gx = cv2.Sobel(a.astype(np.float32), cv2.CV_32F, 1, 0)
    gy = cv2.Sobel(a.astype(np.float32), cv2.CV_32F, 0, 1)
    mag = np.hypot(gx, gy)
    ang = (np.degrees(np.arctan2(gy, gx)) + 180) % 90
    edges = mag > mag.max() * 0.25
    corners = cv2.goodFeaturesToTrack(a, 400, 0.05, 4)
    ys, xs = np.nonzero(m)
    measures = [m.mean(),
                float(vals.mean()) / SIZE if len(vals) else 0.0,
                float(vals.std() / (vals.mean() + 1e-6)) if len(vals) else 0.0,
                float(((ang[edges] < 8) | (ang[edges] > 82)).mean()) if edges.any() else 0.0,
                h / SIZE, w / (SIZE * len(SAMPLE)),
                (0 if corners is None else len(corners)) / max(1.0, m.sum() / 100),
                float(np.corrcoef(xs, ys)[0, 1]) if len(xs) > 10 else 0.0]
    picture = np.asarray(Image.fromarray(a).resize((96, 24)), dtype=np.float32).ravel() / 255
    return np.array(measures, dtype=np.float32), picture


def _vectors(rows):
    """Cached shape vectors keyed by the font's sha256."""
    cache = {}
    if CACHE.is_file():
        # an NpzFile re-reads a member on every z['x'] access: load each array once
        with np.load(CACHE, allow_pickle=False) as z:
            ks, ms, ps = z['k'], z['m'], z['p']
        cache = {str(k): (ms[i], ps[i]) for i, k in enumerate(ks)}
    keys, M, P, changed = [], [], [], False
    for r in rows:
        k = r['sha256']
        if k not in cache:
            fx = features(r['file'])
            if fx is None:
                continue
            cache[k] = fx
            changed = True
        keys.append(k)
        M.append(cache[k][0])
        P.append(cache[k][1])
    if changed:
        ks = list(cache)
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(CACHE, k=np.array(ks), m=np.stack([cache[x][0] for x in ks]),
                            p=np.stack([cache[x][1] for x in ks]))
    return keys, np.stack(M), np.stack(P)


def similar(name: str, limit: int = 8) -> dict:
    import font_library_v35 as fl
    from sklearn.decomposition import PCA
    from sklearn.preprocessing import StandardScaler
    base = fl.find_one(name)
    if not base:
        return {'ok': False, 'outcome': 'error', 'error': f'font not in the library: {name}'}
    rows = [r for r in fl.load() if r.get('arabic') and not r.get('glyph_font')]
    keys, M, P = _vectors(rows)
    if base['sha256'] not in keys:
        return {'ok': False, 'outcome': 'error', 'error': 'cannot draw that font'}
    X = np.hstack([StandardScaler().fit_transform(M) * 1.5, PCA(min(30, len(keys) - 1)).fit_transform(P)])
    by = {r['sha256']: r for r in rows}
    i = keys.index(base['sha256'])
    d = np.linalg.norm(X - X[i], axis=1)
    out, fams = [], {base['family']}
    for j in np.argsort(d):
        r = by[keys[j]]
        if r['family'] in fams:
            continue
        fams.add(r['family'])
        out.append({'name': r['name'], 'distance': round(float(d[j]), 2), 'licence': r['licence'],
                    'category': r.get('category')})
        if len(out) >= limit:
            break
    return {'ok': True, 'like': base['name'], 'count': len(out), 'fonts': out}
