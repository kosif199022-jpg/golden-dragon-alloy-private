"""Songs engine (v1.2): which pieces of a song a montage uses, and the lyrics written on a video.

align() / spans(): a reel's audio is pieces of a song, cut and joined. The smoothed loudness envelope of each few
seconds of the reel is matched against the whole song (normalised cross-correlation with numpy's FFT); those offsets
are the candidates, and spans() then gives every 5 ms of the reel to the offset that explains it (or to "not the song").
A jump in the offset is the editor's cut: up = song material skipped, down = something inserted while the song waits.
In Nov 2026 this showed that a reference montage used song 3:50.6-4:37.1, then a 6.25 s spoken quote while the song
waited, then 4:37.0-4:47.8 (fading out): the editor's cut points, which whisper or listening by ear did not give.
lyrics_sheet(): whisper garbles sung Arabic, so lyrics are read from the video itself: one crop of the caption band per
time, stacked in a labelled grid (JPG) that a person or Claude can read.

ffmpeg does all decoding (engines.media.exe); numpy and Pillow do the rest. Paths may be Arabic, on Linux or Windows.

    python -m engines.songs align REF SONG [--win 6] [--hop 3] [--out match.json]
    python -m engines.songs lyrics VIDEO OUT.jpg [--band 925:1010] [--times 17,21] [--every 4] [--transcript words.json]
"""
import io, json, math, subprocess
from functools import lru_cache
from pathlib import Path

import numpy as np

from .media import exe, probe

HOP_S = 0.005    # envelope step (5 ms)
SMOOTH = 5       # moving average over 5 steps (25 ms) after the per-step mean |x|
FLAT = 1e-3      # local variance under this (z units): silence, no shape to compare
TIE = 0.03       # a window keeps the previous window's offset when that scores within this of its best match
LOCAL_S = 0.4    # local correlation window (s) used to tell, step by step, which offset explains the ref
SAME = 0.5       # local correlation above this counts as "the same audio"
SWITCH = 0.5     # cost of one cut, in seconds of perfect match: chance matches in non-song audio cannot pay it
MIN_SPAN = 1.0   # pieces shorter than this (s) are not trusted
NEAR = 1.0       # an offset is only tried within this many window lengths of a window that found it
BAN = -1e6       # evidence where an offset is not allowed
REFINE_S = 1.0   # each piece edge is re-placed within this many seconds from the step-by-step misfit
FADE_S = 0.3     # running-median span (s) taken off the residual: fades and volume steps do not count against a piece
K_SIGMA = 4.0    # a step fits a piece while its residual stays within this many times the piece's own typical residual
SHEET_PAD, SHEET_LABEL = 6, 22   # lyrics sheet: px around tiles, px of the time label strip above each tile


# ---------------------------------------------------------------- audio alignment

def decode(path, sr=8000):
    """Mono float32 samples of the first audio stream, through an ffmpeg f32le pipe."""
    r = subprocess.run([exe("ffmpeg"), "-nostdin", "-hide_banner", "-v", "error", "-i", str(path), "-map", "0:a:0",
                        "-ac", "1", "-ar", str(int(sr)), "-f", "f32le", "-"], capture_output=True)
    if r.returncode or not r.stdout:
        raise ValueError(f"no audio decoded from {path}: {r.stderr.decode('utf-8', 'ignore').strip()[-300:]}")
    return np.frombuffer(r.stdout, dtype="<f4")


def envelope(x, sr=8000):
    """Loudness envelope on a 5 ms grid: mean |x| per step, log-compressed (40 dB under the loud parts is ~0, so codec
    noise in quiet parts does not count), 25 ms moving average, z-normalised."""
    n = max(1, int(round(sr * HOP_S)))
    k = len(x) // n
    if k < 2:
        return np.zeros(k)
    e = np.abs(np.asarray(x[:k * n], dtype=np.float64)).reshape(k, n).mean(axis=1)
    e = np.log1p(e / (0.01 * np.percentile(e, 95) + 1e-9))
    if k > SMOOTH:
        e = np.convolve(e, np.ones(SMOOTH) / SMOOTH, mode="same")
    sd = e.std()
    return (e - e.mean()) / sd if sd > 1e-12 else np.zeros(k)


@lru_cache(maxsize=8)
def _env_cached(path, size, mtime, sr):
    e = envelope(decode(path, sr), sr)
    e.setflags(write=False)
    return e


def _env(path, sr):
    """Envelope of a file, cached on (path, size, mtime, sr) so align() can be re-run with other windows for free."""
    p = Path(path)
    st = p.stat()
    return _env_cached(str(p.resolve()), st.st_size, st.st_mtime_ns, int(sr))


class Windows(list):
    """align() result: a plain list of window dicts (JSON-ready). It also carries both envelopes (.env) so spans() can
    decide step by step, and the two durations (.ref_s, .song_s)."""
    env = None
    ref_s = song_s = 0.0


def align(ref, song, win=6.0, hop=3.0, sr=8000):
    """Where each `win`-second window of `ref` (a reel, a montage) sits in `song`. One dict per window, every `hop`
    seconds plus one flush with the end of the ref: {ref_t, song_t, offset, score, win}, offset = song_t - ref_t,
    score = normalised cross-correlation of the envelopes (0.95-1 for the same audio; a window across a cut, or
    unrelated audio, can still reach 0.5-0.7 somewhere in a long song, which is why spans() checks every step).
    A silent window has score 0 and offset None. A ref shorter than `win` is one window. Windows under ~3 s let chance
    matches through; 4-10 s gave the same pieces on the Nov 2026 reel."""
    r, s = _env(ref, sr), _env(song, sr)
    fs = max(1, int(round(sr * HOP_S))) / sr
    out = Windows()
    out.env, out.ref_s, out.song_s = (r, s, fs), round(len(r) * fs, 3), round(len(s) * fs, 3)
    n = min(int(round(win / fs)), len(r))
    if n < int(round(1.0 / fs)) or len(s) < n:      # under 1 s of ref, or a song shorter than the window
        return out
    step = max(1, int(round(hop / fs)))
    starts = list(range(0, len(r) - n + 1, step))
    if len(r) - n - starts[-1] > step // 4:
        starts.append(len(r) - n)                   # cover the tail too
    nfft = 1 << (len(s) - 1).bit_length()           # lags 0..len(s)-n never wrap
    spec = np.fft.rfft(s, nfft)
    c1, c2 = np.concatenate(([0.0], np.cumsum(s))), np.concatenate(([0.0], np.cumsum(s * s)))
    m = len(s) - n + 1
    sums = c1[n:n + m] - c1[:m]
    var = c2[n:n + m] - c2[:m] - sums * sums / n    # n x variance of the song under each placement
    live = var > FLAT * n
    sd = np.sqrt(np.where(live, var, 1.0))
    prev = None
    for i0 in starts:
        ref_t = i0 * fs
        seg = r[i0:i0 + n] - r[i0:i0 + n].mean()
        e2 = float(seg @ seg)
        if e2 <= FLAT * n:
            out.append({"ref_t": round(ref_t, 3), "song_t": None, "offset": None, "score": 0.0, "win": round(n * fs, 3)})
            prev = None
            continue
        ncc = np.fft.irfft(spec * np.conj(np.fft.rfft(seg, nfft)), nfft)[:m] / (math.sqrt(e2) * sd)
        ncc[~live] = 0.0
        p = int(np.argmax(ncc))
        if prev is not None:                         # repeated choruses: keep the running offset on a near tie
            q = int(round((ref_t + prev) / fs))
            if 0 <= q < m:
                lo = max(0, q - 2)
                q = lo + int(np.argmax(ncc[lo:q + 3]))
                if ncc[q] >= ncc[p] - TIE:
                    p = q
        d = 0.0
        if 0 < p < m - 1:                            # parabolic peak: sub-step offset
            y0, y1, y2 = ncc[p - 1], ncc[p], ncc[p + 1]
            den = y0 - 2 * y1 + y2
            if den < 0:
                d = max(-0.5, min(0.5, 0.5 * (y0 - y2) / den))
        song_t, score = float((p + d) * fs), float(ncc[p])
        out.append({"ref_t": round(ref_t, 3), "song_t": round(song_t, 3), "offset": round(song_t - ref_t, 3),
                    "score": round(score, 3), "win": round(n * fs, 3)})
        prev = song_t - ref_t if score >= SAME else None
    return out


def spans(windows, tol=0.08, min_score=0.5, refine=True):
    """The pieces of the song that the ref uses: {ref_start, ref_end, song_start, song_end, offset, score, windows}.
    Windows under `min_score` are ignored; offsets that agree within `tol` s are one candidate.
    When `windows` comes straight from align() (it carries both envelopes), every 5 ms step of the ref is given to the
    candidate offset whose local correlation explains it best, or to "not the song", with a cost per cut (Viterbi). So a
    window that straddles a cut, or a chance match inside inserted material, does not become a piece. Edges are then
    re-placed sample by sample: a cut between two pieces lands within a frame, a fade in or out stays in its piece.
    score = mean local correlation over the piece (1.0 = the same audio, fades and level changes included);
    windows = how many windows had this piece as their main content.
    A plain list (e.g. reloaded from JSON) is merged at window precision only: consecutive windows with one offset make
    a piece, a lone window that overlaps a stronger piece is dropped, overlaps are split in the middle. It cannot reject
    chance matches as well."""
    keep = sorted((w for w in windows if w.get("offset") is not None and (w.get("score") or 0) >= min_score),
                  key=lambda w: w["ref_t"])
    if not keep:
        return []
    env = getattr(windows, "env", None)
    segs = _segment(keep, *env, tol=tol, min_score=min_score) if refine and env is not None else _merge(keep, tol)
    return [{"ref_start": round(x["ref_start"], 3), "ref_end": round(x["ref_end"], 3),
             "song_start": round(x["ref_start"] + x["offset"], 3), "song_end": round(x["ref_end"] + x["offset"], 3),
             "offset": round(x["offset"], 3), "score": round(x["score"], 3), "windows": x["windows"]} for x in segs]


def _merge(keep, tol):
    """Window-precision pieces from a plain list of windows (no envelopes)."""
    groups = []
    for w in keep:
        last = groups[-1][-1] if groups else None
        if last and abs(w["offset"] - last["offset"]) <= tol and w["ref_t"] <= last["ref_t"] + last.get("win", 6.0) + 1e-6:
            groups[-1].append(w)
        else:
            groups.append([w])
    segs = [{"ref_start": g[0]["ref_t"], "ref_end": g[-1]["ref_t"] + g[-1].get("win", 6.0),
             "offset": float(np.median([w["offset"] for w in g])), "score": float(np.mean([w["score"] for w in g])),
             "windows": len(g)} for g in groups]
    over = lambda a, b: a["ref_start"] < b["ref_end"] - 1e-6 and b["ref_start"] < a["ref_end"] - 1e-6  # noqa: E731
    segs = [x for x in segs if x["windows"] > 1 or not any(y is not x and over(x, y) and y["score"] > x["score"] for y in segs)]
    for a, b in zip(segs, segs[1:]):
        if b["ref_start"] < a["ref_end"]:
            a["ref_end"] = b["ref_start"] = (a["ref_end"] + b["ref_start"]) / 2
    return segs


def _local_ncc(a, b, w):
    """Correlation of a and b over a w-step window centred on each step. flat = either side has no shape there."""
    n = len(a)
    cs = lambda v: np.concatenate(([0.0], np.cumsum(v)))  # noqa: E731
    A, B, AA, BB, AB = cs(a), cs(b), cs(a * a), cs(b * b), cs(a * b)
    i = np.arange(n)
    lo, hi = np.maximum(0, i - w // 2), np.minimum(n, i - w // 2 + w)
    k = (hi - lo).astype(np.float64)
    sa, sb = A[hi] - A[lo], B[hi] - B[lo]
    va, vb = AA[hi] - AA[lo] - sa * sa / k, BB[hi] - BB[lo] - sb * sb / k
    flat = (va <= FLAT * k) | (vb <= FLAT * k)
    rho = (AB[hi] - AB[lo] - sa * sb / k) / np.sqrt(np.where(flat, 1.0, va * vb))
    return np.where(flat, 0.0, rho), flat


def _evidence(r, s, off, fs, w):
    """Local correlation of the ref with the song at `off`, per ref step: (rho, flat, inside). flat: either side has no
    shape there (silence says nothing); inside: the song exists at that step."""
    j = np.arange(len(r)) + int(round(off / fs))
    inside = (j >= 0) & (j < len(s))
    b = np.zeros(len(r))
    b[inside] = s[j[inside]]
    rho, flat = _local_ncc(np.asarray(r, dtype=np.float64), b, w)
    return rho, flat, inside


def _viterbi(G, pen):
    """Best state per step for evidence G (states x steps): total evidence minus `pen` per change of state.
    On a tie a state keeps itself, so silence stays with the piece around it."""
    k, n = G.shape
    score = G[:, 0].copy()
    jump, src = np.zeros((n, k), dtype=bool), np.zeros(n, dtype=np.int64)
    for i in range(1, n):
        j = int(np.argmax(score))
        alt = score[j] - pen
        sw = alt > score
        jump[i], src[i] = sw, j
        score = np.where(sw, alt, score) + G[:, i]
    path, st = np.empty(n, dtype=np.int64), int(np.argmax(score))
    for i in range(n - 1, -1, -1):
        path[i] = st
        if jump[i, st]:
            st = int(src[i])
    return path


def _runs(path, none):
    """[state, first step, end step] of each run of one state, skipping `none`."""
    cut = np.flatnonzero(np.diff(path)) + 1
    starts, ends = np.concatenate(([0], cut)), np.concatenate((cut, [len(path)]))
    return [[int(path[a]), int(a), int(b)] for a, b in zip(starts, ends) if path[a] != none]


def _seen(ws, t0, t1):
    """How many of the windows ws have their centre inside t0..t1 s (the piece was their main content)."""
    return sum(1 for w in ws if t0 <= w["ref_t"] + (w.get("win") or 6.0) / 2 <= t1)


def _movavg(x, w):
    """Centred moving average over w steps (shorter at the ends)."""
    c, i = np.concatenate(([0.0], np.cumsum(x))), np.arange(len(x))
    lo, hi = np.maximum(0, i - w // 2), np.minimum(len(x), i - w // 2 + w)
    return (c[hi] - c[lo]) / (hi - lo)


def _runmed(x, w):
    """Centred running median over w steps (odd), ends padded: follows volume steps and fades without smearing them."""
    w |= 1
    return np.median(np.lib.stride_tricks.sliding_window_view(np.pad(x, w // 2, mode="edge"), w), axis=1)


def _fit(r, s, d, a, b, rho, w):
    """ref ~ alpha * song[i + d] + beta over the clean steps (local correlation >= 0.9) of the piece a..b, and sigma: the
    typical size (robust) of what is left once drifts slower than w steps are removed. None if the piece has no shape."""
    lo, hi = max(a, -d), min(b, len(s) - d)
    if hi - lo < 20:
        return None
    i = np.arange(lo, hi)
    clean = rho[i] >= 0.9
    if clean.sum() < 20:
        clean[:] = True
    x, y = s[i + d].astype(np.float64), r[i].astype(np.float64)
    xc, yc = x[clean], y[clean]
    vx = float(xc.var())
    if vx < 1e-9 or float(yc.var()) < 1e-9:
        return None
    alpha = float(np.mean((xc - xc.mean()) * (yc - yc.mean()))) / vx
    beta = float(yc.mean() - alpha * xc.mean())
    res = y - alpha * x - beta
    sigma = 1.4826 * float(np.median(np.abs((res - _movavg(res, w))[clean])))
    return alpha, beta, max(sigma, 1e-3)


def _cost(r, s, d, fit, lo, hi, w):
    """Per step lo..hi: how badly the piece (song at d, fitted) explains the ref, from 0 (same audio) to 2 (clearly not);
    "not the song" costs 1. The residual's running median is removed first, so fades and volume steps do not count,
    and the scale is the piece's own residual, so chance level matches in other audio do not pass."""
    alpha, beta, sigma = fit
    a, b = max(0, lo - w), min(len(r), hi + w)
    i = np.arange(a, b)
    j = i + d
    inside = (j >= 0) & (j < len(s))
    res = np.zeros(b - a)
    res[inside] = r[i[inside]] - alpha * s[j[inside]] - beta
    c = np.minimum(((res - _runmed(res, w)) / (K_SIGMA * sigma)) ** 2, 2.0)
    c[~inside] = 2.0
    return c[lo - a:hi - a]


def _cut(left, right):
    """Split p (0..len) that minimises sum(left[:p]) + sum(right[p:])."""
    cost = np.concatenate(([0.0], np.cumsum(left))) + np.concatenate((np.cumsum(right[::-1])[::-1], [0.0]))
    return int(np.argmin(cost))


def _ncc(a, b):
    a, b = a - a.mean(), b - b.mean()
    den = math.sqrt(float(a @ a) * float(b @ b))
    return float(a @ b) / den if den > 1e-12 else 0.0


def _score(r, s, a, b, d, w):
    """Mean local correlation of ref steps a..b with the song at lag d, over the steps where both sides have shape."""
    lo, hi = max(a, -d), min(b, len(s) - d)
    if hi - lo < 2:
        return 0.0
    rho, flat = _local_ncc(np.asarray(r[lo:hi], dtype=np.float64), np.asarray(s[lo + d:hi + d], dtype=np.float64), w)
    return float(np.mean(rho[~flat])) if (~flat).any() else 0.0


def _lag(r, s, a, b, d, clean, reach=3):
    """The piece's own lag: the whole step near d (+-reach) where ref steps a..b correlate best with the song (on its
    clean steps when there are 1 s of them), and the fraction of a step from a parabola through the peak. A window
    median can be a step off, and one step (5 ms) of error is enough to blur every edge."""
    i = np.arange(a, b)
    if clean.sum() >= 200:
        i = i[clean]
    cs = {}
    for dd in range(-reach, reach + 1):
        j = i + d + dd
        ok = (j >= 0) & (j < len(s))
        if ok.sum() >= 20:
            cs[dd] = _ncc(np.asarray(r[i[ok]], dtype=np.float64), np.asarray(s[j[ok]], dtype=np.float64))
    if not cs:
        return d, 0.0
    dd = max(cs, key=cs.get)
    frac = 0.0
    if dd - 1 in cs and dd + 1 in cs:
        y0, y1, y2 = cs[dd - 1], cs[dd], cs[dd + 1]
        den = y0 - 2 * y1 + y2
        if den < 0:
            frac = max(-0.5, min(0.5, 0.5 * (y0 - y2) / den))
    return d + dd, frac


def _refine(runs, r, s, fs, dr, rhos):
    """Re-place each edge within REFINE_S, step by step with _cost (the windowed correlation alone puts edges up to
    ~0.1 s late when the audio after a cut is quiet): between two pieces the cut goes where the second one explains
    the ref better, next to other audio where the piece stops explaining it. A fade in or out stays in its piece."""
    n, L, w = len(r), int(round(REFINE_S / fs)), max(5, int(round(FADE_S / fs))) | 1
    fits = [_fit(r, s, dr[i], a, b, rhos[k], w) for i, (k, a, b) in enumerate(runs)]
    cost = lambda i, lo, hi: _cost(r, s, dr[i], fits[i], lo, hi, w)  # noqa: E731
    for i, (k, a, b) in enumerate(runs):
        if fits[i] is None:
            continue
        if a > 0 and (i == 0 or runs[i - 1][2] < a):         # start, after other audio
            lo, hi = max(runs[i - 1][2] if i else 0, a - L), min(b - 1, a + L)
            if hi > lo:
                runs[i][1] = lo + _cut(np.ones(hi - lo), cost(i, lo, hi))
        nxt = runs[i + 1] if i + 1 < len(runs) else None
        if nxt is not None and nxt[1] == b:                  # cut straight into the next piece
            if fits[i + 1] is not None:
                lo, hi = max(runs[i][1] + 1, b - L), min(nxt[2] - 1, b + L)
                if hi > lo:
                    runs[i][2] = nxt[1] = lo + _cut(cost(i, lo, hi), cost(i + 1, lo, hi))
        elif b < n:                                          # end, before other audio
            lo, hi = max(runs[i][1] + 1, b - L), min(nxt[1] if nxt is not None else n, b + L)
            if hi > lo:
                runs[i][2] = lo + _cut(cost(i, lo, hi), np.ones(hi - lo))
    return runs


def _segment(keep, r, s, fs, tol, min_score=0.5):
    """Step-level pieces. Candidates are the window offsets (merged within tol), each tried only near the windows that
    found it. A piece must last MIN_SPAN, hold the centre of one of those windows and keep a mean local correlation of
    min_score, else that offset is forbidden there and the path solved again."""
    groups = []
    for w in sorted(keep, key=lambda w: w["offset"]):
        if groups and w["offset"] - groups[-1][-1]["offset"] <= tol:
            groups[-1].append(w)
        else:
            groups.append([w])
    n, lw = len(r), max(8, int(round(LOCAL_S / fs)))
    G = np.zeros((len(groups) + 1, n))              # last row: "not the song", evidence 0
    offs, ds, rhos, valid = [], [], [], []
    for k, ws in enumerate(groups):
        offs.append(float(np.median([w["offset"] for w in ws])))
        ds.append(int(round(offs[k] / fs)))
        rho, flat, inside = _evidence(r, s, offs[k], fs, lw)
        rhos.append(rho)
        valid.append(~flat & inside)
        ok = np.zeros(n, dtype=bool)
        for w in ws:
            win = w.get("win") or 6.0
            a, b = int((w["ref_t"] - NEAR * win) / fs), int(math.ceil((w["ref_t"] + (1 + NEAR) * win) / fs))
            ok[max(0, a):max(0, min(n, b))] = True
        g = np.where(flat, 0.0, rho - SAME)
        g[~inside] = -SAME
        G[k] = np.where(ok, g, BAN)
    pen, short = SWITCH / fs * (1 - SAME), int(round(MIN_SPAN / fs))

    def score(k, a, b):
        v = valid[k][a:b]
        return float(np.mean(rhos[k][a:b][v])) if v.any() else 0.0

    bad = lambda k, a, b: b - a < short or not _seen(groups[k], a * fs, b * fs) or score(k, a, b) < min_score  # noqa: E731
    for _ in range(8):
        runs = _runs(_viterbi(G, pen), len(groups))
        drop = [x for x in runs if bad(*x)]
        if not drop:
            break
        for k, a, b in drop:
            G[k, a:b] = BAN
    runs = [x for x in runs if not bad(*x)]
    lags = [_lag(r, s, a, b, ds[k], valid[k][a:b] & (rhos[k][a:b] >= 0.9)) for k, a, b in runs]
    runs = _refine(runs, r, s, fs, [d for d, _ in lags], rhos)
    out = []
    for (k, a, b), (d, frac) in zip(runs, lags):
        sc = _score(r, s, a, b, d, lw)
        if b - a >= short and sc >= min_score:
            out.append({"ref_start": a * fs, "ref_end": b * fs, "offset": (d + frac) * fs, "score": sc,
                        "windows": _seen(groups[k], a * fs, b * fs)})
    return out


def gaps(segs, total, min_len=0.25):
    """Stretches of the ref (0..total s) that no span covers and are at least min_len s long."""
    out, t = [], 0.0
    for x in sorted(segs, key=lambda x: x["ref_start"]):
        if x["ref_start"] - t >= min_len:
            out.append({"ref_start": round(t, 3), "ref_end": round(x["ref_start"], 3)})
        t = max(t, x["ref_end"])
    if total - t >= min_len:
        out.append({"ref_start": round(t, 3), "ref_end": round(total, 3)})
    return out


SILENT_DBFS = -50.0   # a ref step quieter than this is not song material (v1.3 edge trim)
FLAT_CV = 0.05        # a 0.25 s stretch whose level varies less than 5% is a test tone or hum, not the song


def _step_levels(x, sr):
    """Per 5 ms step: level in dBFS and how much the level varies over the 0.25 s around it (coefficient of variation
    of the step RMS; windows are cut at the edges, not padded with zeros)."""
    n = max(1, int(round(sr * HOP_S)))
    k = len(x) // n
    a = np.asarray(x[:k * n], dtype=np.float64).reshape(k, n)
    rms = np.sqrt((a ** 2).mean(axis=1))
    db = 20 * np.log10(np.maximum(rms, 1e-9))
    w = max(3, int(round(0.25 / HOP_S)))
    ones = np.ones(w)
    cnt = np.convolve(np.ones(k), ones, mode="same")
    m = np.convolve(rms, ones, mode="same") / cnt
    sq = np.convolve(rms ** 2, ones, mode="same") / cnt
    cv = np.sqrt(np.maximum(sq - m ** 2, 0)) / np.maximum(m, 1e-9)
    return db, cv


def trim_edges(segs, x, sr):
    """v1.3: the Viterbi folds leading silence, a tone or noise into the first piece (its first boundary came out
    0.4-2 s early). Steps at the start and end of each piece that are silent (< SILENT_DBFS) or flat (a tone) are cut
    off; they show up in gaps(). Returns the pieces with 'trimmed_head'/'trimmed_tail' seconds."""
    if not segs:
        return segs
    db, cv = _step_levels(x, sr)
    bad = (db < SILENT_DBFS) | (cv < FLAT_CV)
    n = len(bad)
    out = []
    for p in segs:
        a, b = int(round(p["ref_start"] / HOP_S)), min(n, int(round(p["ref_end"] / HOP_S)))
        a0, b0 = a, b
        while a < b and bad[a]:
            a += 1
        while b > a and bad[b - 1]:
            b -= 1
        if (b - a) * HOP_S < MIN_SPAN:
            continue
        ha, tb = (a - a0) * HOP_S, (b0 - b) * HOP_S
        q = dict(p)
        if ha or tb:
            q.update(ref_start=round(a * HOP_S, 3), ref_end=round(b * HOP_S, 3),
                     song_start=round(a * HOP_S + p["offset"], 3), song_end=round(b * HOP_S + p["offset"], 3),
                     trimmed_head=round(ha, 3), trimmed_tail=round(tb, 3))
        out.append(q)
    return out


def match(ref, song, win=6.0, hop=3.0, sr=8000, tol=0.08, min_score=0.5):
    """align + spans + gaps in one JSON-ready dict: what the CLI prints and saves. Piece edges are trimmed of silence
    and tones (trim_edges); align boundaries are good to about ±0.5 s for the editor's cuts: snap them to the
    reference's picture cuts (mimic / scdet) before cutting."""
    w = align(ref, song, win, hop, sr)
    segs = spans(w, tol, min_score)
    try:
        segs = trim_edges(segs, decode(ref, sr), sr)
    except ValueError:
        pass
    return {"ref": str(ref), "song": str(song), "ref_s": w.ref_s, "song_s": w.song_s, "win": win, "hop": hop,
            "spans": segs, "gaps": gaps(segs, w.ref_s), "windows": list(w)}


# ---------------------------------------------------------------- lyrics sheet

def _times(times, every, transcript, duration):
    """Union of explicit times, one per `every`-second slot (its middle: every/2, 3*every/2, ...) and transcript line
    midpoints; sorted, inside the video."""
    ts = []
    if times is not None:
        ts += [float(t) for t in (str(times).split(",") if isinstance(times, (str, int, float)) else times) if str(t).strip()]
    if every:
        k = 0
        while (k + 0.5) * float(every) < duration:
            ts.append((k + 0.5) * float(every))
            k += 1
    if transcript is not None:
        data = json.loads(Path(transcript).read_text(encoding="utf-8-sig")) if isinstance(transcript, (str, Path)) else transcript
        if isinstance(data, dict):
            data = data.get("lines") or data.get("segments") or []
        if not isinstance(data, list):
            raise ValueError("transcript must be a list of {start, end, text} lines (dragon words), "
                             "{\"lines\": [...]}, {\"segments\": [...]} or [start, end, text] rows")
        for ln in data:
            if isinstance(ln, dict) and ln.get("start") is not None:
                a = float(ln["start"])
                ts.append((a + float(ln.get("end", a))) / 2)
            elif isinstance(ln, (list, tuple)) and len(ln) >= 2 and all(isinstance(v, (int, float)) for v in ln[:2]):
                ts.append((float(ln[0]) + float(ln[1])) / 2)        # [start, end, text] rows
    late = [t for t in ts if t >= duration or t < 0]
    if late:
        import sys
        print(f"lyrics-sheet: {len(late)} time(s) outside the video (0..{duration:g} s) skipped: "
              f"{', '.join(f'{t:g}' for t in late[:10])}{' …' if len(late) > 10 else ''}", file=sys.stderr)
    out = []
    for t in sorted(t for t in ts if 0 <= t < duration):
        if not out or t - out[-1] > 0.01:
            out.append(t)
    return out


def _pixels(band, size, default):
    """(a, b) band in pixels; values all <= 1 are fractions of `size`; "925:1010" strings work too."""
    if band is None:
        band = default
    if isinstance(band, str):
        band = band.replace(",", ":").split(":")
    a, b = (float(v) for v in band)
    if max(a, b) <= 1.0:
        a, b = a * size, b * size
    a, b = max(0, min(int(round(a)), size - 1)), max(1, min(int(round(b)), size))
    if b <= a:
        raise ValueError(f"empty band {band} for a frame of {size} px")
    return a, b


def _frame(video, t):
    """The frame shown at t seconds (display orientation) as a Pillow RGB image, or None past the end."""
    from PIL import Image
    r = subprocess.run([exe("ffmpeg"), "-nostdin", "-hide_banner", "-v", "error", "-ss", f"{t:.3f}", "-i", str(video),
                        "-map", "0:v:0", "-frames:v", "1", "-pix_fmt", "rgb24", "-c:v", "ppm", "-f", "image2pipe", "-"],
                       capture_output=True)
    if r.returncode or not r.stdout:
        return None
    return Image.open(io.BytesIO(r.stdout)).convert("RGB")


def _clock(t):
    s = f"{t:.2f}".rstrip("0").rstrip(".") + "s"
    return s if t < 60 else f"{s}  {int(t // 60)}:{t % 60:04.1f}"


def _font(px):
    from PIL import ImageFont
    try:
        return ImageFont.load_default(size=px)
    except TypeError:                                # Pillow < 10.1
        return ImageFont.load_default()


def lyrics_sheet(video, out, band=None, times=None, every=None, transcript=None, cols=2, width=460, xband=None, min_h=48,
                 per_sheet=20):
    """Contact sheet of the caption band, for reading on-screen lyrics (whisper garbles sung Arabic).
    One frame per time: `times` (list or "17,21.5"), one per `every`-second slot, and/or each line midpoint of a
    `transcript` (dragon words JSON: [{start, end, text}], or {"lines": [...]} / {"segments": [...]}).
    band = (y0, y1) in source pixels (fractions if <= 1; default the bottom band 0.84-0.94 of the height); xband the
    same across (default full width). Each crop is scaled to `width`, but never under `min_h` px tall unless that would
    upscale past the source (a 1920-wide band 85 px tall stays readable). Tiles go left to right, `cols` per row, each
    under a strip with its time. Saves a JPG (or PNG/WEBP by suffix) and returns its path."""
    from PIL import Image, ImageDraw
    video, out = Path(video), Path(out)
    j = probe(video)
    if not any(st.get("codec_type") == "video" for st in j.get("streams", [])):
        raise ValueError(f"no video stream in {video}")
    vs = next(st for st in j["streams"] if st.get("codec_type") == "video")
    duration = float(j.get("format", {}).get("duration") or vs.get("duration") or 0)
    if every and not duration:
        raise ValueError(f"unknown duration for {video}: give times instead of every")
    ts = _times(times, every, transcript, duration or float("inf"))
    if not ts:
        raise ValueError("no times inside the video: give times, every or transcript")
    tiles, size = [], None
    for t in ts:
        im = _frame(video, t)
        if im is None:
            continue
        if size is None:
            W, H = im.size
            y0, y1 = _pixels(band, H, (0.84, 0.94))
            x0, x1 = _pixels(xband, W, (0.0, 1.0))
            scale = max(width / (x1 - x0), min(1.0, min_h / (y1 - y0)))
            size = (max(1, round((x1 - x0) * scale)), max(1, round((y1 - y0) * scale)))
        tiles.append((t, im.crop((x0, y0, x1, y1)).resize(size, getattr(Image, "Resampling", Image).LANCZOS)))
    if not tiles:
        raise ValueError(f"no frames decoded from {video} at {ts[:5]}")
    per = int(per_sheet or 0)
    if per and len(tiles) > per:          # v1.3: 100 tiles in one 938x5506 image cannot be read: one sheet per 20
        outs = []
        for k in range(0, len(tiles), per):
            o = out.with_name(f"{out.stem}_{k // per + 1:02d}{out.suffix or '.jpg'}")
            outs.append(_sheet(tiles[k:k + per], size, cols, o))
        return outs
    return _sheet(tiles, size, cols, out)


def _sheet(tiles, size, cols, out):
    from PIL import Image, ImageDraw
    cols = max(1, min(int(cols), len(tiles)))
    rows = math.ceil(len(tiles) / cols)
    tw, th = size
    sheet = Image.new("RGB", (cols * tw + (cols + 1) * SHEET_PAD, rows * (SHEET_LABEL + th) + (rows + 1) * SHEET_PAD),
                      (24, 24, 24))
    draw, font = ImageDraw.Draw(sheet), _font(SHEET_LABEL - 6)
    for i, (t, im) in enumerate(tiles):
        r, c = divmod(i, cols)
        x, y = SHEET_PAD + c * (tw + SHEET_PAD), SHEET_PAD + r * (SHEET_LABEL + th + SHEET_PAD)
        draw.text((x + 2, y + 2), _clock(t), fill=(255, 210, 80), font=font)
        sheet.paste(im, (x, y + SHEET_LABEL))
    out.parent.mkdir(parents=True, exist_ok=True)
    fmt = None if out.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp") else "JPEG"
    sheet.save(out, fmt, quality=92)
    return out


# ---------------------------------------------------------------- CLI

def _mmss(t):
    return f"{'-' if t < 0 else ''}{int(abs(t) // 60)}:{abs(t) % 60:05.2f}"


def main(argv=None):
    import argparse, sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    ap = argparse.ArgumentParser(prog="python -m engines.songs", description="song pieces in a montage; lyrics sheets")
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("align", help="which pieces of SONG the audio of REF uses, and where it was cut")
    a.add_argument("ref"); a.add_argument("song")
    a.add_argument("--win", type=float, default=6.0); a.add_argument("--hop", type=float, default=3.0)
    a.add_argument("--sr", type=int, default=8000); a.add_argument("--tol", type=float, default=0.08)
    a.add_argument("--min-score", type=float, default=0.5); a.add_argument("--out", help="save the full result as JSON")
    a.add_argument("--windows", action="store_true", help="also print every window")
    ly = sub.add_parser("lyrics", help="caption-band contact sheet (JPG) to read on-screen lyrics")
    ly.add_argument("video"); ly.add_argument("out")
    ly.add_argument("--band", help="y0:y1 in source pixels (default bottom 0.84:0.94)"); ly.add_argument("--xband", help="x0:x1")
    ly.add_argument("--times", help="17,21,26.5"); ly.add_argument("--every", type=float)
    ly.add_argument("--transcript", help="dragon words JSON: one tile per line midpoint")
    ly.add_argument("--cols", type=int, default=2); ly.add_argument("--width", type=int, default=460)
    ly.add_argument("--min-h", type=int, default=48)
    o = ap.parse_args(argv)
    if o.cmd == "align":
        res = match(o.ref, o.song, o.win, o.hop, o.sr, o.tol, o.min_score)
        print(f"ref {res['ref_s']:.2f} s · song {res['song_s']:.2f} s · {len(res['windows'])} windows "
              f"(win {o.win:g} s, hop {o.hop:g} s)")
        if o.windows:
            for w in res["windows"]:
                off = "   silent" if w["offset"] is None else f"{w['offset']:+9.3f}"
                print(f"  window ref {w['ref_t']:7.2f}  offset {off}  score {w['score']:.3f}")
        rows = [(x["ref_start"], "span", x) for x in res["spans"]] + [(g["ref_start"], "gap", g) for g in res["gaps"]]
        k = 0
        for _, kind, x in sorted(rows, key=lambda r: r[0]):
            if kind == "span":
                k += 1
                print(f"  piece {k}  ref {x['ref_start']:7.2f} - {x['ref_end']:7.2f}  =  song {x['song_start']:7.2f} - "
                      f"{x['song_end']:7.2f} ({_mmss(x['song_start'])} - {_mmss(x['song_end'])})  offset {x['offset']:+.3f}"
                      f"  score {x['score']:.2f}  ({x['windows']} windows)")
            else:
                print(f"  not song ref {x['ref_start']:7.2f} - {x['ref_end']:7.2f}  ({x['ref_end'] - x['ref_start']:.2f} s)")
        if not res["spans"]:
            print("  no piece of the song found (all windows under --min-score)")
        if o.out:
            Path(o.out).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
            print(f"saved -> {o.out}")
    else:
        p = lyrics_sheet(o.video, o.out, band=o.band, times=o.times, every=o.every, transcript=o.transcript,
                         cols=o.cols, width=o.width, xband=o.xband, min_h=o.min_h)
        print(f"lyrics sheet -> {p}")


if __name__ == "__main__":
    main()
