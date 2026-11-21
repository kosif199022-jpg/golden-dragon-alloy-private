"""Red Rose V25: read-only frame analysis of local video/image files.

Standard library + FFmpeg/FFprobe only (through scene_edit_v16.probe_source and
list-form subprocess.run calls with capture_output and a timeout). Every op
decodes the source into a SMALL grayscale or RGB proxy held in memory through an
FFmpeg rawvideo pipe, caps the number of frames, and never writes, moves or
modifies any file. URLs and non-local inputs are rejected.

All results are technical heuristics measured on proxies. Nothing here
recognises faces, persons, identities, objects or story content, and no op
claims a single "quality" verdict. Each op returns the assumptions it makes and
the limits it enforces next to its result:
    run(op, params) -> {'op', 'result', 'assumptions', 'limits'}
"""
from __future__ import annotations

import colorsys
import json
import math
import operator
import re
import shutil
import subprocess
from pathlib import Path

from scene_edit_v16 import probe_source, ALLOWED_VIDEO
from shot_quality_v19 import PROXY_W, PROXY_H  # shared 64x36 analysis proxy

MAX_PARAMS = 24
MAX_IMAGE_BYTES = 200_000_000
ALLOWED_IMAGE = {'.png', '.jpg', '.jpeg', '.bmp', '.webp', '.tif', '.tiff'}
DECODE_TIMEOUT = 120

TOPICS = {
    '20.02': 'scene_cuts_eval',
    '20.03': 'motion_stats',
    '20.04': 'saliency_point',
    '20.05': 'perceptual_dupes',
    '20.06': 'sharpness',
    '20.08': 'colour_stats',
    '20.09': 'quality_compare',
    '20.10': 'frame_borders',
}

TOPIC_NAMES_AR = {
    '20.02': 'كشف المشاهد بتحليل الإطار',
    '20.03': 'تحليل سرعة الحركة',
    '20.04': 'تحديد نقطة الاهتمام',
    '20.05': 'كشف الصور المكررة',
    '20.06': 'تقييم وضوح الصورة',
    '20.08': 'تحليل ألوان المشاهد',
    '20.09': 'مقارنة نسخة قبل وبعد',
    '20.10': 'تحليل حدود المجال المرئي',
}

_COMMON_ASSUMPTIONS = (
    'input is a local file validated with ffprobe; it is only read, never modified',
    'frames are decoded to a small in-memory proxy through an FFmpeg rawvideo pipe',
    'no face, person, identity or object recognition is performed',
)


# --------------------------------------------------------------------------- validation

def _no_extra(extra):
    if extra:
        raise ValueError('unknown parameter(s): ' + ', '.join(sorted(map(str, extra))))


def _num(value, low, high, name):
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value)):
        raise ValueError(f'{name} must be a finite number')
    value = float(value)
    if not low <= value <= high:
        raise ValueError(f'{name} must be in [{low}, {high}]')
    return value


def _int(value, low, high, name):
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise ValueError(f'{name} must be an integer from {low} to {high}')
    return value


def _pack(op, result, assumptions, limits):
    return {'op': op, 'result': result,
            'assumptions': list(_COMMON_ASSUMPTIONS) + list(assumptions),
            'limits': list(limits)}


def _probe_image(path):
    """ffprobe-validated still image (probe_source accepts video containers only)."""
    if not 0 < path.stat().st_size <= MAX_IMAGE_BYTES:
        raise ValueError('image must be a non-empty local file under 200 MB')
    if not shutil.which('ffprobe') or not shutil.which('ffmpeg'):
        raise RuntimeError('FFmpeg and FFprobe must be installed')
    cmd = ['ffprobe', '-v', 'error', '-show_entries', 'stream=codec_type,width,height',
           '-of', 'json', str(path)]
    try:
        completed = subprocess.run(cmd, capture_output=True, text=True, timeout=30, check=True)
    except subprocess.CalledProcessError as exc:
        raise ValueError('image could not be read by ffprobe') from exc
    streams = [s for s in json.loads(completed.stdout).get('streams', [])
               if s.get('codec_type') == 'video']
    if len(streams) != 1:
        raise ValueError('image must contain exactly one picture stream')
    width, height = int(streams[0]['width']), int(streams[0]['height'])
    if not 8 <= width <= 8192 or not 8 <= height <= 8192:
        raise ValueError('image dimensions outside supported bounds')
    return {'source': str(path), 'kind': 'image', 'duration': None, 'width': width,
            'height': height, 'fps': None, 'audio': False, 'bytes': path.stat().st_size}


def _media(source, name='source', *, allow_image=True):
    if source is None:
        raise ValueError(f'{name} is required' if name != 'source' else 'source is required')
    if not isinstance(source, str):
        raise ValueError(f'{name} must be a local file path string')
    if '://' in source or source.lower().startswith(('http:', 'https:', 'ftp:', 'data:')):
        raise ValueError(f'{name} must be a local file, URLs are rejected')
    path = Path(source).expanduser().resolve()
    if not path.is_file():
        raise ValueError(f'{name} must be an existing local file')
    suffix = path.suffix.lower()
    if suffix in ALLOWED_VIDEO:
        meta = dict(probe_source(path))
        meta['kind'] = 'video'
        return meta
    if suffix in ALLOWED_IMAGE:
        if not allow_image:
            raise ValueError(f'{name} must be a video for this op')
        return _probe_image(path)
    raise ValueError(f'{name} must be a supported video ({sorted(ALLOWED_VIDEO)}) '
                     f'or image ({sorted(ALLOWED_IMAGE)})')


def _decode(meta, width, height, pix_fmt, *, sample_fps=None, max_frames=1):
    """Decode up to max_frames frames scaled to width x height into raw bytes frames."""
    bpp = 3 if pix_fmt == 'rgb24' else 1
    size = width * height * bpp
    filters = []
    if meta['kind'] == 'video' and sample_fps:
        filters.append(f'fps={sample_fps:.6f}')
    else:
        max_frames = 1
    filters.append(f'scale={width}:{height}:flags=area')
    filters.append(f'format={pix_fmt}')
    cmd = ['ffmpeg', '-hide_banner', '-nostdin', '-v', 'error', '-i', meta['source'],
           '-map', '0:v:0', '-an', '-vf', ','.join(filters), '-frames:v', str(max_frames),
           '-f', 'rawvideo', '-pix_fmt', pix_fmt, 'pipe:1']
    raw = subprocess.run(cmd, capture_output=True, timeout=DECODE_TIMEOUT, check=True).stdout
    if not raw or len(raw) % size:
        raise ValueError('decoder produced incomplete or empty frame data')
    count = len(raw) // size
    if count > max_frames:
        raise ValueError('decoder produced unexpected frame count')
    return [raw[i * size:(i + 1) * size] for i in range(count)]


def _even_fps(meta, frames):
    """Sampling rate that spreads `frames` samples across the whole clip."""
    if meta['kind'] != 'video':
        return None
    return max(frames / meta['duration'], 0.01)


# --------------------------------------------------------------------------- shared math

def _gray_from_rgb(frame):
    return bytes((r * 299 + g * 587 + b * 114) // 1000
                 for r, g, b in zip(frame[0::3], frame[1::3], frame[2::3]))


_Q64 = bytes(v >> 6 for v in range(256))


def _rgb_hist64(frame):
    q = frame.translate(_Q64)
    hist = [0] * 64
    for r, g, b in zip(q[0::3], q[1::3], q[2::3]):
        hist[r * 16 + g * 4 + b] += 1
    total = len(q) // 3
    return [h / total for h in hist]


def _detect_cuts(frames, sample_fps, duration, *, threshold, hist_weight, min_shot_seconds):
    """Combined histogram (0.5*L1) + mean-absolute luma difference cut detector."""
    cuts, scores, series = [], [], []
    prev_hist = prev_gray = None
    last = 0.0
    for i, frame in enumerate(frames):
        hist = _rgb_hist64(frame)
        gray = _gray_from_rgb(frame)
        if prev_hist is not None:
            hdiff = 0.5 * sum(abs(a - b) for a, b in zip(hist, prev_hist))
            mdiff = sum(map(abs, map(operator.sub, gray, prev_gray))) / (len(gray) * 255)
            score = hist_weight * hdiff + (1 - hist_weight) * mdiff
            t = i / sample_fps
            series.append(round(score, 5))
            if (score >= threshold and t - last >= min_shot_seconds
                    and (duration - t) >= min_shot_seconds * 0.5):
                cuts.append(round(t, 4))
                scores.append(round(score, 5))
                last = t
        prev_hist, prev_gray = hist, gray
    return cuts, scores, series


def _match_events(detected, labelled, tolerance):
    """One-to-one greedy matching by smallest time distance within tolerance."""
    pairs = sorted((abs(d - l), i, j) for i, d in enumerate(detected)
                   for j, l in enumerate(labelled) if abs(d - l) <= tolerance)
    used_d, used_l, matches = set(), set(), []
    for dist, i, j in pairs:
        if i in used_d or j in used_l:
            continue
        used_d.add(i)
        used_l.add(j)
        matches.append({'detected': detected[i], 'labelled': labelled[j],
                        'error_s': round(detected[i] - labelled[j], 4)})
    tp = len(matches)
    precision = tp / len(detected) if detected else None
    recall = tp / len(labelled) if labelled else None
    f1 = (2 * precision * recall / (precision + recall)
          if precision and recall else (0.0 if precision is not None and recall is not None else None))
    return {'true_positives': tp, 'false_positives': len(detected) - tp,
            'false_negatives': len(labelled) - tp,
            'precision': None if precision is None else round(precision, 5),
            'recall': None if recall is None else round(recall, 5),
            'f1': None if f1 is None else round(f1, 5),
            'matches': sorted(matches, key=lambda m: m['labelled']),
            'unmatched_detected': [d for i, d in enumerate(detected) if i not in used_d],
            'unmatched_labelled': [l for j, l in enumerate(labelled) if j not in used_l]}


# --------------------------------------------------------------------------- 20.02 scene_cuts_eval

def scene_cuts_eval(*, source=None, labelled_cuts=None, tolerance=0.25, sample_fps=10,
                    threshold=0.30, hist_weight=0.6, min_shot_seconds=0.4,
                    max_frames=1200, **extra):
    """Detect hard cuts on a 64x36 RGB proxy and score them against labelled cut times."""
    _no_extra(extra)
    meta = _media(source, allow_image=False)
    tolerance = _num(tolerance, 0.0, 5.0, 'tolerance')
    sample_fps = _int(sample_fps, 2, 30, 'sample_fps')
    threshold = _num(threshold, 0.02, 1.0, 'threshold')
    hist_weight = _num(hist_weight, 0.0, 1.0, 'hist_weight')
    min_shot_seconds = _num(min_shot_seconds, 0.05, 60.0, 'min_shot_seconds')
    max_frames = _int(max_frames, 2, 6000, 'max_frames')
    labels = None
    if labelled_cuts is not None:
        if not isinstance(labelled_cuts, (list, tuple)) or len(labelled_cuts) > 1000:
            raise ValueError('labelled_cuts must be a list of at most 1000 times in seconds')
        labels = sorted(_num(v, 0.0, meta['duration'], f'labelled_cuts[{i}]')
                        for i, v in enumerate(labelled_cuts))
    frames = _decode(meta, 64, 36, 'rgb24', sample_fps=sample_fps, max_frames=max_frames)
    analysed = min(meta['duration'], len(frames) / sample_fps)
    cuts, strengths, _series = _detect_cuts(frames, sample_fps, meta['duration'],
                                            threshold=threshold, hist_weight=hist_weight,
                                            min_shot_seconds=min_shot_seconds)
    evaluation = None
    if labels is not None:
        in_range = [l for l in labels if l <= analysed + tolerance]
        evaluation = _match_events(cuts, in_range, tolerance)
        evaluation['tolerance_s'] = tolerance
        evaluation['labels_outside_analysed_span'] = len(labels) - len(in_range)
    bounds = [0.0] + cuts + [round(meta['duration'], 4)]
    shots = [{'index': k + 1, 'start': bounds[k], 'end': bounds[k + 1]}
             for k in range(len(bounds) - 1)]
    result = {'source': meta, 'method': 'rgb64_histogram_l1_plus_luma_mad',
              'proxy': {'width': 64, 'height': 36, 'sample_fps': sample_fps,
                        'sampled_frames': len(frames)},
              'analysed_seconds': round(analysed, 4),
              'truncated': len(frames) >= max_frames and analysed < meta['duration'] - 1 / sample_fps,
              'threshold': threshold, 'hist_weight': hist_weight,
              'cuts': cuts, 'cut_strengths': strengths, 'shots': shots,
              'evaluation': evaluation}
    return _pack('scene_cuts_eval', result,
                 ['a hard cut changes the colour distribution and/or luma of most of the frame',
                  'score = hist_weight * 0.5*L1(rgb 4x4x4 histogram) + (1-hist_weight) * mean |luma diff|',
                  'a detected cut matches a labelled cut if |dt| <= tolerance (one-to-one, closest first)'],
                 [f'cut times are quantised to 1/sample_fps = {1 / sample_fps:.3f} s',
                  'fades and dissolves are often missed; flashes, fast pans and strobes can add false cuts',
                  'precision/recall are None when their denominator is zero',
                  f'at most {max_frames} frames are decoded (64x36 RGB proxy)'])


# --------------------------------------------------------------------------- 20.03 motion_stats

_DIRECTIONS = ('E', 'NE', 'N', 'NW', 'W', 'SW', 'S', 'SE')


def _block_motion(prev, cur, w, h, block, search, texture_min):
    vectors = []
    textured = 0
    offsets = sorted(((dx, dy) for dx in range(-search, search + 1)
                      for dy in range(-search, search + 1)),
                     key=lambda d: (d[0] * d[0] + d[1] * d[1], d))
    for by in range(search, h - block - search + 1, block):
        for bx in range(search, w - block - search + 1, block):
            rows = [prev[(by + r) * w + bx:(by + r) * w + bx + block] for r in range(block)]
            pix = b''.join(rows)
            mean = sum(pix) / len(pix)
            std = math.sqrt(sum((p - mean) ** 2 for p in pix) / len(pix))
            if std < texture_min:
                continue
            textured += 1
            best = None
            zero_sad = None
            for dx, dy in offsets:
                sad = 0
                for r in range(block):
                    start = (by + dy + r) * w + bx + dx
                    sad += sum(map(abs, map(operator.sub, rows[r], cur[start:start + block])))
                    if best is not None and sad >= best[0]:
                        break
                if zero_sad is None:
                    zero_sad = sad
                if best is None or sad < best[0]:
                    best = (sad, dx, dy)
            sad, dx, dy = best
            # A displacement must clearly beat "no motion" to count (noise guard).
            if (dx or dy) and not (sad < 0.8 * zero_sad and zero_sad - sad > block * block * 2):
                dx = dy = 0
            vectors.append((dx, dy))
    return vectors, textured


def motion_stats(*, source=None, sample_fps=8, max_frames=48, block=8, search=4,
                 texture_min=4.0, **extra):
    """Block-matching optical flow on a 64x36 gray proxy: magnitude + direction histogram."""
    _no_extra(extra)
    meta = _media(source, allow_image=False)
    sample_fps = _int(sample_fps, 1, 30, 'sample_fps')
    max_frames = _int(max_frames, 2, 240, 'max_frames')
    block = _int(block, 4, 12, 'block')
    search = _int(search, 1, 6, 'search')
    texture_min = _num(texture_min, 0.0, 128.0, 'texture_min')
    w, h = PROXY_W, PROXY_H
    frames = _decode(meta, w, h, 'gray', sample_fps=sample_fps, max_frames=max_frames)
    if len(frames) < 2:
        raise ValueError('at least two sampled frames are needed; the clip is too short')
    sx, sy = meta['width'] / w, meta['height'] / h
    hist = [0] * 8
    mags, sum_dx, sum_dy, total_vectors, moving, textured_total = [], 0.0, 0.0, 0, 0, 0
    series = []
    for prev, cur in zip(frames, frames[1:]):
        vectors, textured = _block_motion(prev, cur, w, h, block, search, texture_min)
        textured_total += textured
        pair = []
        for dx, dy in vectors:
            vx, vy = dx * sx * sample_fps, dy * sy * sample_fps  # source px / s, y down
            mag = math.hypot(vx, vy)
            pair.append(mag)
            mags.append(mag)
            sum_dx += vx
            sum_dy += vy
            total_vectors += 1
            if dx or dy:
                moving += 1
                angle = math.degrees(math.atan2(-vy, vx)) % 360
                hist[int(((angle + 22.5) % 360) // 45)] += 1
        series.append(round(sum(pair) / len(pair), 3) if pair else 0.0)
    mean_mag = sum(mags) / len(mags) if mags else 0.0
    dir_hist = {d: (round(c / moving, 4) if moving else 0.0) for d, c in zip(_DIRECTIONS, hist)}
    dominant = max(dir_hist, key=dir_hist.get) if moving else None
    result = {'source': meta, 'method': 'exhaustive_block_matching_sad',
              'proxy': {'width': w, 'height': h, 'sample_fps': sample_fps,
                        'sampled_frames': len(frames), 'block': block, 'search_px': search},
              'mean_magnitude_px_per_s': round(mean_mag, 4),
              'mean_magnitude_frame_widths_per_s': round(mean_mag / meta['width'], 5),
              'mean_vector_px_per_s': {'x': round(sum_dx / total_vectors, 4) if total_vectors else 0.0,
                                       'y_down': round(sum_dy / total_vectors, 4) if total_vectors else 0.0},
              'textured_blocks': textured_total, 'moving_blocks': moving,
              'moving_fraction': round(moving / total_vectors, 4) if total_vectors else 0.0,
              'direction_histogram': dir_hist, 'dominant_direction': dominant,
              'per_pair_mean_magnitude_px_per_s': series}
    return _pack('motion_stats', result,
                 ['motion is estimated per 8x8 block of a 64x36 gray proxy by minimum SAD within +/-search px',
                  'textureless blocks (std < texture_min) are skipped: their motion is unobservable',
                  'velocities are converted to source pixels per second; directions: N = up on screen',
                  'a displacement only counts if it beats the zero-motion SAD by a margin (noise guard)'],
                 [f'max measurable speed is search*source_width/64*sample_fps '
                  f'= {search * sx * sample_fps:.1f} px/s; faster motion aliases or is underestimated',
                  'integer-pixel proxy resolution: slow motion below ~1 proxy px per sample reads as 0',
                  'camera motion and object motion are not separated',
                  'aperture problem: blocks on edges parallel to the motion read as 0, so the mean '
                  'underestimates object speed (a 100 px/s square measured about 66 px/s)',
                  f'at most {max_frames} frames analysed'])


# --------------------------------------------------------------------------- 20.04 saliency_point

def _parse_aspect(aspect):
    if isinstance(aspect, str):
        m = re.fullmatch(r'\s*(\d{1,4}(?:\.\d+)?)\s*[:/x]\s*(\d{1,4}(?:\.\d+)?)\s*', aspect)
        if not m:
            raise ValueError("aspect must look like '9:16'")
        a, b = float(m.group(1)), float(m.group(2))
    elif isinstance(aspect, (list, tuple)) and len(aspect) == 2:
        a, b = (_num(v, 0.01, 10000, 'aspect') for v in aspect)
    else:
        raise ValueError("aspect must be 'W:H' or [W, H]")
    if not a > 0 or not b > 0 or not 0.1 <= a / b <= 10:
        raise ValueError('aspect ratio must be between 0.1 and 10')
    return a / b


def _box_blur3(img, w, h):
    out = [0.0] * (w * h)
    for y in range(h):
        y0, y1 = max(0, y - 1), min(h - 1, y + 1)
        for x in range(w):
            x0, x1 = max(0, x - 1), min(w - 1, x + 1)
            s = n = 0
            for yy in range(y0, y1 + 1):
                row = yy * w
                for xx in range(x0, x1 + 1):
                    s += img[row + xx]
                    n += 1
            out[y * w + x] = s / n
    return out


def saliency_point(*, source=None, aspect='9:16', frames=3, keep_fraction=0.6, **extra):
    """Global-contrast luma saliency -> point of interest + crop box for a target aspect."""
    _no_extra(extra)
    meta = _media(source)
    ratio = _parse_aspect(aspect)
    frames = _int(frames, 1, 12, 'frames')
    keep_fraction = _num(keep_fraction, 0.1, 0.95, 'keep_fraction')
    w, h = 96, 54
    decoded = _decode(meta, w, h, 'gray', sample_fps=_even_fps(meta, frames), max_frames=frames)
    sal = [0.0] * (w * h)
    for frame in decoded:
        blurred = _box_blur3(frame, w, h)
        mean = sum(blurred) / len(blurred)
        for i, v in enumerate(blurred):
            sal[i] += abs(v - mean)
    peak = max(sal)
    if peak <= 0:
        px, py, confident = 0.5, 0.5, False
    else:
        cut = keep_fraction * peak
        sw = sxw = syw = 0.0
        for i, s in enumerate(sal):
            if s >= cut:
                sw += s
                sxw += s * ((i % w) + 0.5)
                syw += s * ((i // w) + 0.5)
        px, py, confident = sxw / sw / w, syw / sw / h, True
    W, H = meta['width'], meta['height']
    point = {'x': round(px * W, 2), 'y': round(py * H, 2),
             'x_norm': round(px, 5), 'y_norm': round(py, 5)}
    if W / H > ratio:
        ch, cw = H, min(W, int(round(H * ratio)))
    else:
        cw, ch = W, min(H, int(round(W / ratio)))
    cx = int(round(min(max(px * W - cw / 2, 0), W - cw)))
    cy = int(round(min(max(py * H - ch / 2, 0), H - ch)))
    crop = {'x': cx, 'y': cy, 'width': cw, 'height': ch,
            'contains_point': cx <= point['x'] <= cx + cw and cy <= point['y'] <= cy + ch,
            'ffmpeg_crop': f'crop={cw}:{ch}:{cx}:{cy}'}
    result = {'source': meta, 'method': 'global_luma_contrast_saliency',
              'proxy': {'width': w, 'height': h, 'frames': len(decoded)},
              'point_of_interest': point, 'salient_signal': confident,
              'target_aspect': round(ratio, 5), 'suggested_crop': crop}
    return _pack('saliency_point', result,
                 ['saliency = |3x3 box-blurred luma - frame mean luma|, summed over sampled frames',
                  'point = saliency-weighted centroid of pixels >= keep_fraction * peak saliency',
                  'crop = largest box of the target aspect inside the frame, centred on the point and clamped',
                  'no faces, persons or identities are detected or recognised'],
                 ['contrast is not attention: a bright sky or logo can win over the real subject',
                  'luma only: equally bright hues of different colour are not salient to this measure',
                  'a moving subject is averaged over the sampled frames; a flat frame falls back to centre',
                  f'96x54 proxy: point precision about {W / w:.1f} x {H / h:.1f} source px'])


# --------------------------------------------------------------------------- 20.05 perceptual_dupes

def _hashes(meta, time_s):
    """aHash (8x8 > mean) and dHash (9x8, left > right), each 64 bits."""
    if meta['kind'] == 'video':
        t = min(time_s, max(0.0, meta['duration'] - 0.05))
        sel = ['-ss', f'{t:.4f}']
    else:
        sel = []
    out = {}
    for name, (w, h) in (('a', (8, 8)), ('d', (9, 8))):
        cmd = (['ffmpeg', '-hide_banner', '-nostdin', '-v', 'error'] + sel +
               ['-i', meta['source'], '-map', '0:v:0', '-an',
                '-vf', f'scale={w}:{h}:flags=area,format=gray', '-frames:v', '1',
                '-f', 'rawvideo', '-pix_fmt', 'gray', 'pipe:1'])
        raw = subprocess.run(cmd, capture_output=True, timeout=60, check=True).stdout
        if len(raw) != w * h:
            raise ValueError(f"could not decode a frame from {meta['source']}")
        bits = 0
        if name == 'a':
            mean = sum(raw) / 64
            for v in raw:
                bits = (bits << 1) | (v > mean)
        else:
            for y in range(8):
                row = raw[y * 9:(y + 1) * 9]
                for x in range(8):
                    bits = (bits << 1) | (row[x] > row[x + 1])
        out[name] = bits
    return out['a'], out['d']


def perceptual_dupes(*, sources=None, time=0.0, ahash_max=10, dhash_max=10, **extra):
    """Pairwise aHash/dHash Hamming distances with explicit duplicate thresholds."""
    _no_extra(extra)
    if sources is None:
        raise ValueError('source is required')
    if not isinstance(sources, (list, tuple)) or not 2 <= len(sources) <= 32:
        raise ValueError('sources must be a list of 2..32 local image/video paths')
    time = _num(time, 0.0, 600.0, 'time')
    ahash_max = _int(ahash_max, 0, 64, 'ahash_max')
    dhash_max = _int(dhash_max, 0, 64, 'dhash_max')
    metas = [_media(s, f'sources[{i}]') for i, s in enumerate(sources)]
    if len({m['source'] for m in metas}) != len(metas):
        raise ValueError('sources must be distinct files')
    items = []
    for m in metas:
        a, d = _hashes(m, time)
        items.append({'source': m['source'], 'kind': m['kind'],
                      'ahash': f'{a:016x}', 'dhash': f'{d:016x}', '_a': a, '_d': d})
    pairs, groups = [], {i: i for i in range(len(items))}

    def find(i):
        while groups[i] != i:
            groups[i] = groups[groups[i]]
            i = groups[i]
        return i
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            da = bin(items[i]['_a'] ^ items[j]['_a']).count('1')
            dd = bin(items[i]['_d'] ^ items[j]['_d']).count('1')
            dup = da <= ahash_max and dd <= dhash_max
            pairs.append({'a': i, 'b': j, 'ahash_distance': da, 'dhash_distance': dd,
                          'duplicate': dup})
            if dup:
                groups[find(i)] = find(j)
    clusters = {}
    for i in range(len(items)):
        clusters.setdefault(find(i), []).append(i)
    for it in items:
        del it['_a'], it['_d']
    result = {'method': 'ahash8x8_plus_dhash9x8_hamming', 'items': items, 'pairs': pairs,
              'thresholds': {'ahash_max': ahash_max, 'dhash_max': dhash_max},
              'duplicate_groups': [g for g in clusters.values() if len(g) > 1],
              'frame_time_s': time}
    return _pack('perceptual_dupes', result,
                 ['one frame per source (images: the picture; videos: the frame at `time`, clamped)',
                  'aHash: 8x8 area-scaled luma, bit = pixel > mean; dHash: 9x8, bit = left > right neighbour',
                  'a pair is a duplicate only if BOTH Hamming distances are within their thresholds'],
                 ['64-bit hashes are robust to scaling, mild brightness/contrast and compression, '
                  'not to crops, rotations, mirroring or heavy edits',
                  'unrelated images with similar coarse layout can collide; review flagged pairs',
                  'videos are compared by a single frame, not by their whole content',
                  'at most 32 sources (496 pairs)'])


# --------------------------------------------------------------------------- 20.06 sharpness

def _laplacian_variance(frame, w, h):
    vals = []
    for y in range(1, h - 1):
        row, up, down = y * w, (y - 1) * w, (y + 1) * w
        for x in range(1, w - 1):
            i = row + x
            vals.append(4 * frame[i] - frame[i - 1] - frame[i + 1] - frame[up + x] - frame[down + x])
    mean = sum(vals) / len(vals)
    return sum((v - mean) ** 2 for v in vals) / len(vals)


def _sharpness_of(meta, frames, w, h):
    decoded = _decode(meta, w, h, 'gray', sample_fps=_even_fps(meta, frames), max_frames=frames)
    per = [_laplacian_variance(f, w, h) for f in decoded]
    return {'source': meta, 'frames': len(decoded),
            'laplacian_variance_mean': round(sum(per) / len(per), 4),
            'laplacian_variance_min': round(min(per), 4),
            'laplacian_variance_max': round(max(per), 4)}


def sharpness(*, source=None, compare=None, frames=5, **extra):
    """Variance of the 4-neighbour Laplacian on a fixed 128x72 gray proxy."""
    _no_extra(extra)
    meta = _media(source)
    other = _media(compare, 'compare') if compare is not None else None
    frames = _int(frames, 1, 30, 'frames')
    w, h = 128, 72
    first = _sharpness_of(meta, frames, w, h)
    result = {'method': 'variance_of_laplacian', 'proxy': {'width': w, 'height': h},
              'source': first, 'compare': None, 'ratio_compare_to_source': None}
    if other is not None:
        second = _sharpness_of(other, frames, w, h)
        result['compare'] = second
        base = first['laplacian_variance_mean']
        result['ratio_compare_to_source'] = (round(second['laplacian_variance_mean'] / base, 5)
                                             if base > 0 else None)
    return _pack('sharpness', result,
                 ['every input is area-scaled to the SAME 128x72 gray proxy before measuring',
                  'higher variance of the Laplacian = more fine edge energy = usually sharper',
                  'frames are spread evenly over the clip and averaged'],
                 ['only comparable between versions of the SAME content (texture changes the scale)',
                  'noise, grain and compression ringing raise the value and can mimic sharpness',
                  'detail finer than the proxy (source px / 128 columns) is invisible to this measure',
                  'not a focus-point or subject-focus judgement; no regional analysis'])


# --------------------------------------------------------------------------- 20.08 colour_stats

_H_BINS, _S_BINS, _V_BINS, _GRAY_BINS = 12, 3, 3, 4
_N_BINS = _H_BINS * _S_BINS * _V_BINS + _GRAY_BINS
_HSV_CACHE = {}


def _hsv_bin(r, g, b):
    key = (r >> 4, g >> 4, b >> 4)
    hit = _HSV_CACHE.get(key)
    if hit is not None:
        return hit
    hh, ss, vv = colorsys.rgb_to_hsv(((key[0] << 4) + 8) / 255, ((key[1] << 4) + 8) / 255,
                                     ((key[2] << 4) + 8) / 255)
    if ss < 0.15 or vv < 0.12:
        idx = _H_BINS * _S_BINS * _V_BINS + min(_GRAY_BINS - 1, int(vv * _GRAY_BINS))
    else:
        hb = int(hh * _H_BINS) % _H_BINS
        sb = min(_S_BINS - 1, int((ss - 0.15) / 0.85 * _S_BINS))
        vb = min(_V_BINS - 1, int((vv - 0.12) / 0.88 * _V_BINS))
        idx = (hb * _S_BINS + sb) * _V_BINS + vb
    _HSV_CACHE[key] = idx
    return idx


def _bin_label(idx):
    base = _H_BINS * _S_BINS * _V_BINS
    if idx >= base:
        return f'neutral/value{idx - base + 1}of{_GRAY_BINS}'
    hb, rest = divmod(idx, _S_BINS * _V_BINS)
    sb, vb = divmod(rest, _V_BINS)
    width = 360 // _H_BINS
    return f'hue{hb * width:03d}-{(hb + 1) * width:03d}/sat{sb + 1}/val{vb + 1}'


def _hsv_hist(frame):
    hist = [0.0] * _N_BINS
    for r, g, b in zip(frame[0::3], frame[1::3], frame[2::3]):
        hist[_hsv_bin(r, g, b)] += 1
    n = len(frame) // 3
    return [v / n for v in hist]


def _mean_hist(hists):
    if not hists:
        return [0.0] * _N_BINS
    return [sum(col) / len(hists) for col in zip(*hists)]


def _intersection(a, b):
    return round(sum(min(x, y) for x, y in zip(a, b)), 5)


def _top_bins(hist, k=5):
    order = sorted(range(len(hist)), key=lambda i: -hist[i])[:k]
    return [{'bin': _bin_label(i), 'share': round(hist[i], 4)} for i in order if hist[i] > 0]


def _clip_colours(meta, sample_fps, max_frames, threshold):
    w, h = 64, 36
    frames = _decode(meta, w, h, 'rgb24', sample_fps=sample_fps if meta['kind'] == 'video' else None,
                     max_frames=max_frames)
    hists = [_hsv_hist(f) for f in frames]
    if meta['kind'] == 'video':
        cuts, _s, _series = _detect_cuts(frames, sample_fps, meta['duration'], threshold=threshold,
                                         hist_weight=0.6, min_shot_seconds=0.4)
        bounds = [0.0] + cuts + [meta['duration']]
    else:
        cuts, bounds = [], [0.0, 0.0]
    members = [[] for _ in range(len(bounds) - 1)]
    for i in range(len(frames)):
        t = i / sample_fps if meta['kind'] == 'video' else 0.0
        k = max(j for j in range(len(members)) if bounds[j] <= t)
        members[k].append(i)
    shots = []
    for k, idx in enumerate(members):
        lo, hi = bounds[k], bounds[k + 1]
        shot_hist = _mean_hist([hists[i] for i in idx])
        shots.append({'index': k + 1, 'start': round(lo, 4), 'end': round(hi, 4),
                      'sampled_frames': len(idx), 'dominant_bins': _top_bins(shot_hist),
                      'histogram': [round(v, 5) for v in shot_hist]})
    clip_hist = _mean_hist(hists)
    return {'source': meta, 'sampled_frames': len(frames), 'cuts': cuts, 'shots': shots[:64],
            'dominant_bins': _top_bins(clip_hist),
            'histogram': [round(v, 5) for v in clip_hist]}, clip_hist


def colour_stats(*, source=None, compare=None, palette=None, sample_fps=4, max_frames=240,
                 cut_threshold=0.30, **extra):
    """Per-shot HSV histograms and histogram-intersection similarity to a clip or palette."""
    _no_extra(extra)
    meta = _media(source)
    other = _media(compare, 'compare') if compare is not None else None
    sample_fps = _int(sample_fps, 1, 15, 'sample_fps')
    max_frames = _int(max_frames, 1, 900, 'max_frames')
    cut_threshold = _num(cut_threshold, 0.02, 1.0, 'cut_threshold')
    pal = None
    if palette is not None:
        if not isinstance(palette, (list, tuple)) or not 1 <= len(palette) <= 32:
            raise ValueError("palette must be a list of 1..32 '#rrggbb' colours")
        pal = []
        for i, c in enumerate(palette):
            if not isinstance(c, str) or not re.fullmatch(r'#?[0-9a-fA-F]{6}', c):
                raise ValueError(f"palette[{i}] must be '#rrggbb'")
            c = c.lstrip('#')
            pal.append((int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)))
    main, main_hist = _clip_colours(meta, sample_fps, max_frames, cut_threshold)
    result = {'method': 'hsv_12x3x3_plus_4_neutral_bins_from_srgb', 'bins': _N_BINS,
              'source': main, 'compare': None, 'similarity': {}}
    if other is not None:
        second, second_hist = _clip_colours(other, sample_fps, max_frames, cut_threshold)
        result['compare'] = second
        result['similarity']['source_vs_compare'] = _intersection(main_hist, second_hist)
    if pal is not None:
        ph = [0.0] * _N_BINS
        for r, g, b in pal:
            ph[_hsv_bin(r, g, b)] += 1 / len(pal)
        result['palette_histogram_dominant'] = _top_bins(ph, k=len(pal))
        result['similarity']['source_vs_palette'] = _intersection(main_hist, ph)
    return _pack('colour_stats', result,
                 ['pixels are treated as sRGB and converted to HSV (Python colorsys) after 4-bit quantisation',
                  f'bins: 12 hues x 3 saturations x 3 values + 4 neutral (low S or very dark) = {_N_BINS}',
                  'shots come from the same histogram+luma cut heuristic as scene_cuts_eval',
                  'similarity = histogram intersection (1 = identical distribution, 0 = disjoint)',
                  'a palette is weighted equally per colour'],
                 ['no white balance, gamma, HDR or colour-management handling; display transforms ignored',
                  'hue bins are 30 degrees wide: nearby hues can split across a boundary',
                  'intersection ignores where colours are in the frame and how they are arranged',
                  f'64x36 proxy, at most {max_frames} frames per clip, at most 64 shots reported'])


# --------------------------------------------------------------------------- 20.09 quality_compare

def _codec_context(meta):
    cmd = ['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries',
           'stream=codec_name,pix_fmt,bit_rate:format=bit_rate,format_name',
           '-of', 'json', meta['source']]
    info = json.loads(subprocess.run(cmd, capture_output=True, text=True,
                                     timeout=30, check=True).stdout)
    stream = (info.get('streams') or [{}])[0]
    fmt = info.get('format') or {}

    def _rate(v):
        try:
            return int(v)
        except (TypeError, ValueError):
            return None
    return {'kind': meta['kind'], 'width': meta['width'], 'height': meta['height'],
            'fps': meta['fps'], 'duration': meta['duration'], 'bytes': meta['bytes'],
            'codec': stream.get('codec_name'), 'pix_fmt': stream.get('pix_fmt'),
            'container': fmt.get('format_name'),
            'video_bit_rate': _rate(stream.get('bit_rate')),
            'total_bit_rate': _rate(fmt.get('bit_rate'))}


def _ssim(x, y, w, h, win=8, step=4):
    c1, c2 = (0.01 * 255) ** 2, (0.03 * 255) ** 2
    vals = []
    n = win * win
    for by in range(0, h - win + 1, step):
        for bx in range(0, w - win + 1, step):
            a = []
            b = []
            for r in range(win):
                s = (by + r) * w + bx
                a.extend(x[s:s + win])
                b.extend(y[s:s + win])
            ma, mb = sum(a) / n, sum(b) / n
            va = sum((p - ma) ** 2 for p in a) / (n - 1)
            vb = sum((p - mb) ** 2 for p in b) / (n - 1)
            cov = sum((p - ma) * (q - mb) for p, q in zip(a, b)) / (n - 1)
            vals.append(((2 * ma * mb + c1) * (2 * cov + c2)) /
                        ((ma * ma + mb * mb + c1) * (va + vb + c2)))
    return sum(vals) / len(vals)


def quality_compare(*, source=None, compare=None, frames=10, **extra):
    """PSNR + SSIM on 128x72 luma proxies, always with resolution/codec context.

    Refuses to collapse the comparison into a single "quality" number.
    """
    _no_extra(extra)
    meta = _media(source)
    if compare is None:
        raise ValueError('compare is required')
    other = _media(compare, 'compare')
    frames = _int(frames, 1, 30, 'frames')
    if meta['kind'] != other['kind']:
        raise ValueError('source and compare must both be videos or both be images')
    w, h = 128, 72
    if meta['kind'] == 'video':
        span = min(meta['duration'], other['duration'])
        fps = max(frames / span, 0.01)
    else:
        span, fps = None, None
    a = _decode(meta, w, h, 'gray', sample_fps=fps, max_frames=frames)
    b = _decode(other, w, h, 'gray', sample_fps=fps, max_frames=frames)
    count = min(len(a), len(b))
    se = 0
    ssims = []
    for fa, fb in zip(a[:count], b[:count]):
        se += sum(d * d for d in map(operator.sub, fa, fb))
        ssims.append(_ssim(fa, fb, w, h))
    mse = se / (count * w * h)
    identical = mse == 0
    psnr = None if identical else round(10 * math.log10(255 ** 2 / mse), 4)
    result = {'method': 'psnr_and_mean_ssim_on_luma_proxy',
              'proxy': {'width': w, 'height': h, 'frames_compared': count,
                        'compared_span_s': None if span is None else round(span, 4)},
              'psnr_db': psnr,
              'psnr_note': ('infinite: proxies are identical (reported as None)' if identical
                            else 'finite'),
              'mse': round(mse, 6),
              'ssim': round(sum(ssims) / len(ssims), 6),
              'ssim_min_frame': round(min(ssims), 6),
              'context': {'source': _codec_context(meta), 'compare': _codec_context(other),
                          'same_resolution': (meta['width'], meta['height']) ==
                                             (other['width'], other['height']),
                          'same_duration': (None if span is None else
                                            abs(meta['duration'] - other['duration']) < 0.05)},
              'single_quality_score': None,
              'single_quality_score_refused': ('PSNR and SSIM measure different things on a small '
                                               'proxy; collapsing them into one quality number would '
                                               'hide trade-offs, so none is produced')}
    return _pack('quality_compare', result,
                 ['both versions show the same content, time-aligned from their first frame',
                  'both are area-scaled to the same 128x72 luma proxy before comparison',
                  'PSNR uses peak 255 over all compared proxy pixels; SSIM = mean of 8x8 windows (step 4)',
                  'identical proxies give PSNR = infinity, reported as psnr_db None with a note'],
                 ['proxy metrics miss fine detail/compression artefacts smaller than ~1 proxy pixel',
                  'no temporal alignment search: a frame offset or trim makes both metrics drop',
                  'chroma is ignored (luma only); neither metric is a perceptual score like VMAF',
                  f'at most {frames} frames compared; no single quality number is ever produced'])


# --------------------------------------------------------------------------- 20.10 frame_borders

_STANDARD_ASPECTS = {'9:16': 9 / 16, '3:4': 3 / 4, '4:5': 4 / 5, '1:1': 1.0, '4:3': 4 / 3,
                     '3:2': 1.5, '16:9': 16 / 9, '1.85:1': 1.85, '2:1': 2.0, '2.39:1': 2.39}


def frame_borders(*, source=None, frames=5, black_level=24, margin_fraction=0.01, **extra):
    """Own luma scan for letterbox/pillarbox bars and the active picture rectangle."""
    _no_extra(extra)
    meta = _media(source)
    frames = _int(frames, 1, 30, 'frames')
    black_level = _int(black_level, 1, 128, 'black_level')
    margin_fraction = _num(margin_fraction, 0.0, 0.25, 'margin_fraction')
    w, h = 256, 144
    decoded = _decode(meta, w, h, 'gray', sample_fps=_even_fps(meta, frames), max_frames=frames)
    col = [0.0] * w
    row = [0.0] * h
    for f in decoded:
        for y in range(h):
            line = f[y * w:(y + 1) * w]
            row[y] += sum(line) / w
            for x, v in enumerate(line):
                col[x] += v / h
    n = len(decoded)
    col = [c / n for c in col]
    row = [r / n for r in row]
    active_cols = [x for x, v in enumerate(col) if v > black_level]
    active_rows = [y for y, v in enumerate(row) if v > black_level]
    W, H = meta['width'], meta['height']
    if not active_cols or not active_rows:
        result = {'source': meta, 'all_black': True, 'classification': 'all_black',
                  'active_rect': None, 'active_aspect': None}
    else:
        left, right = active_cols[0], active_cols[-1] + 1
        top, bottom = active_rows[0], active_rows[-1] + 1
        x0, x1 = round(left * W / w), round(right * W / w)
        y0, y1 = round(top * H / h), round(bottom * H / h)
        aw, ah = x1 - x0, y1 - y0
        side = (x0 > margin_fraction * W) or (W - x1 > margin_fraction * W)
        flat = (y0 > margin_fraction * H) or (H - y1 > margin_fraction * H)
        kind = ('windowbox' if side and flat else 'pillarbox' if side
                else 'letterbox' if flat else 'full_frame')
        aspect = aw / ah
        nearest = min(_STANDARD_ASPECTS, key=lambda k: abs(math.log(_STANDARD_ASPECTS[k] / aspect)))
        result = {'source': meta, 'all_black': False, 'classification': kind,
                  'borders_px': {'left': x0, 'right': W - x1, 'top': y0, 'bottom': H - y1},
                  'active_rect': {'x': x0, 'y': y0, 'width': aw, 'height': ah},
                  'active_aspect': round(aspect, 5), 'nearest_standard_aspect': nearest,
                  'frame_aspect': round(W / H, 5),
                  'ffmpeg_crop': f'crop={aw}:{ah}:{x0}:{y0}'}
    result.update({'method': 'mean_luma_row_column_scan',
                   'proxy': {'width': w, 'height': h, 'frames': n},
                   'black_level': black_level})
    return _pack('frame_borders', result,
                 ['a border row/column has mean luma <= black_level (0..255) over all sampled frames',
                  'the active picture is the bounding box of non-border rows and columns',
                  f'bars thinner than margin_fraction ({margin_fraction}) of the frame are ignored'],
                 [f'256x144 proxy: edges are accurate to about {W / w:.1f} x {H / h:.1f} source px',
                  'a genuinely dark scene edge (night sky, black clothing) can be read as a bar',
                  'non-black (coloured or blurred) pillar fill is not detected as a border',
                  f'at most {frames} frames sampled evenly; bars that change mid-clip are averaged'])


# --------------------------------------------------------------------------- dispatcher

OPS = {
    'scene_cuts_eval': scene_cuts_eval, 'motion_stats': motion_stats,
    'saliency_point': saliency_point, 'perceptual_dupes': perceptual_dupes,
    'sharpness': sharpness, 'colour_stats': colour_stats,
    'quality_compare': quality_compare, 'frame_borders': frame_borders,
}

EFFECTS = {op: 'read' for op in OPS}


def run(op, params=None):
    """Validate and dispatch: run('sharpness', {'source': 'a.mp4'}) -> {'op','result',...}."""
    if not isinstance(op, str) or op not in OPS:
        raise ValueError(f'op must be one of {sorted(OPS)}')
    if params is None:
        params = {}
    if not isinstance(params, dict):
        raise ValueError('params must be a dict')
    if len(params) > MAX_PARAMS:
        raise ValueError(f'params may have at most {MAX_PARAMS} keys')
    if not all(isinstance(key, str) for key in params):
        raise ValueError('param names must be strings')
    out = OPS[op](**params)
    try:
        json.dumps(out, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f'{op} produced a non-JSON-serialisable result: {exc}') from exc
    return out
