"""Helpers of runners/fam_w3_05.py used by data cards, copied verbatim (the extractor binds a card to them only when
their AST hash with every dependency equals the original's)."""
from __future__ import annotations

from pathlib import Path
from .core import fx
import json
import math
import numpy as np
import re
import subprocess


SR = 48000


def ff(*args, timeout=60):
    return fx.ffmpeg(*args, timeout=timeout)


def tt(d, sr=SR):
    return np.arange(int(round(d * sr))) / sr


def sine(f, d, amp=0.5, sr=SR):
    return amp * np.sin(2 * np.pi * f * tt(d, sr))


def save(wd, name, x, sr=SR):
    return fx.write_wav(Path(wd) / name, x, sr)


def load_any(p, sr=SR, ch=1):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(p), "-f", "f32le", "-ac", str(ch), "-ar", str(sr), "-"],
                         capture_output=True, timeout=60, stdin=subprocess.DEVNULL).stdout
    a = np.frombuffer(raw, dtype="<f4").astype(float)
    return (a.reshape(-1, ch) if ch > 1 else a), sr


def rms(x):
    return float(np.sqrt(np.mean(np.square(x)) + 1e-20))


def dbfs(x):
    return 20 * math.log10(rms(x) + 1e-12)


def seg_db(x, sr, a, b):
    return dbfs(x[int(a * sr):int(b * sr)])


def peak_db(x):
    return 20 * math.log10(float(np.max(np.abs(x))) + 1e-12)


def band_db(x, sr, lo, hi):
    X = np.abs(np.fft.rfft(x * np.hanning(len(x)))) ** 2
    f = np.fft.rfftfreq(len(x), 1 / sr)
    return 10 * math.log10(float(X[(f >= lo) & (f < hi)].sum()) + 1e-20)


def peak_hz(x, sr=SR, lo=15):
    X = np.abs(np.fft.rfft(x * np.hanning(len(x))))
    f = np.fft.rfftfreq(len(x), 1 / sr)
    X[f < lo] = 0
    return float(f[int(np.argmax(X))])


def centroid(x, sr=SR):
    X = np.abs(np.fft.rfft(x * np.hanning(len(x))))
    f = np.fft.rfftfreq(len(x), 1 / sr)
    return float((X * f).sum() / (X.sum() + 1e-12))


def envelope(x, sr, ms=5.0):
    n = max(1, int(sr * ms / 1000))
    return np.sqrt(np.convolve(np.square(x), np.ones(n) / n, mode="same"))


def onsets(x, sr, rel=0.3, gap=0.06, ms=5.0):
    """Independent measurement: rising crossings of rel*max of a short RMS envelope, at least gap apart."""
    e = envelope(x, sr, ms)
    thr = rel * e.max()
    up = np.flatnonzero((e[1:] >= thr) & (e[:-1] < thr)) + 1
    out, last = [], -1e9
    for i in up:
        if i / sr - last >= gap:
            out.append(i / sr)
            last = i / sr
    return out


def addp(*arrs):
    n = max(len(a) for a in arrs)
    out = np.zeros(n)
    for a in arrs:
        out[:len(a)] += a
    return out


def kick(sr=SR, amp=0.9):
    t = tt(0.25, sr)
    return amp * np.sin(2 * np.pi * np.cumsum(46 + 110 * np.exp(-t / 0.032)) / sr) * np.exp(-t / 0.08)


def drum_loop(bpm, secs, sr=SR, offset=0.0, seed=1):
    rng = np.random.default_rng(seed)
    x = np.zeros(int(secs * sr))
    k = kick(sr).copy()
    nc = int(0.01 * sr)
    k[:nc] += 0.3 * rng.standard_normal(nc) * np.exp(-np.arange(nc) / sr / 0.002)
    times, b = [], 0
    while offset + b * 60 / bpm < secs - 0.3:
        t = offset + b * 60 / bpm
        i = int(round(t * sr))
        x[i:i + len(k)] += k[: len(x) - i]
        times.append(round(t, 4))
        b += 1
    return x, times


def clicks(times, secs, sr=SR, f=1000.0, dur=0.03, amp=0.8):
    x = np.zeros(int(secs * sr))
    t0 = tt(dur, sr)
    c = amp * np.sin(2 * np.pi * f * t0) * np.exp(-t0 * 120)
    for t in times:
        i = int(round(t * sr))
        x[i:i + len(c)] += c[: max(0, len(x) - i)]
    return x


def speechlike(secs, spans, sr=SR, f0=140.0, amp=0.35):
    t = tt(secs, sr)
    v = sum((1.0 / k) * np.sin(2 * np.pi * f0 * k * t + k) for k in range(1, 11))
    v /= np.abs(v).max()
    syl = 0.55 + 0.45 * np.abs(np.sin(2 * np.pi * 2.0 * t))
    g = np.zeros_like(t)
    for a, b in spans:
        i0, i1 = int(a * sr), int(b * sr)
        n = i1 - i0
        r = min(int(0.02 * sr), n // 2)
        w = np.ones(n)
        w[:r] = np.linspace(0, 1, r)
        w[-r:] = np.linspace(1, 0, r)
        g[i0:i1] = w
    return amp * v * syl * g


def music_bed(secs, sr=SR, amp=0.3, freqs=(220, 277.2, 329.6, 440)):
    t = tt(secs, sr)
    x = sum(np.sin(2 * np.pi * f * t) for f in freqs)
    return amp * x / len(freqs) * (0.85 + 0.15 * np.sin(2 * np.pi * 0.5 * t))


def noise(n, seed=0):
    return np.random.default_rng(seed).standard_normal(n)


def bandpass(x, lo, hi, sr=SR, order=4):
    from scipy.signal import butter, sosfilt
    return sosfilt(butter(order, [lo, hi], btype="band", fs=sr, output="sos"), x)


def lowpass(x, fc, sr=SR, order=4):
    from scipy.signal import butter, sosfilt
    return sosfilt(butter(order, fc, btype="low", fs=sr, output="sos"), x)


def highpass(x, fc, sr=SR, order=4):
    from scipy.signal import butter, sosfilt
    return sosfilt(butter(order, fc, btype="high", fs=sr, output="sos"), x)


def place(dst, src, t, sr=SR, gain=1.0):
    i = int(round(t * sr))
    n = min(len(src), len(dst) - i)
    if n > 0:
        dst[i:i + n] += gain * src[:n]
    return dst


def at_level(x, db):
    """Scale x so that its peak sits at db dBFS."""
    return x * 10 ** ((db - peak_db(x)) / 20)


def ebur(p):
    err = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(p), "-af", "ebur128=peak=true", "-f", "null", "-"],
                         capture_output=True, text=True, timeout=60, stdin=subprocess.DEVNULL).stderr
    summ = err[err.rfind("Summary:"):]
    g = lambda pat: float(re.search(pat, summ, re.S).group(1))
    return {"I": g(r"I:\s+(-?[\d.]+|-inf) LUFS"), "LRA": g(r"LRA:\s+(-?[\d.]+) LU"),
            "TP": g(r"True peak:\s+Peak:\s+(-?[\d.]+|-inf) dBFS")}


def loudnorm2(src, out, I=-14, TP=-1.0, LRA=11, sr=48000):
    err = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(src), "-af",
                          "loudnorm=I=%s:TP=%s:LRA=%s:print_format=json" % (I, TP, LRA), "-f", "null", "-"],
                         capture_output=True, text=True, timeout=60, stdin=subprocess.DEVNULL).stderr
    m = json.loads(err[err.rfind("{"):err.rfind("}") + 1])
    af = ("loudnorm=I=%s:TP=%s:LRA=%s:measured_I=%s:measured_TP=%s:measured_LRA=%s:measured_thresh=%s:offset=%s:"
          "linear=true:print_format=summary,aresample=%d" % (I, TP, LRA, m["input_i"], m["input_tp"], m["input_lra"],
                                                            m["input_thresh"], m["target_offset"], sr))
    ff("-i", src, "-af", af, "-c:a", "pcm_s16le", out)
    return m


def jdump(p, obj):
    Path(p).write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
    return Path(p)


def tdump(p, text):
    Path(p).write_text(text, encoding="utf-8")
    return Path(p)


def beat_err(found, truth):
    return max(min(abs(f - t) for f in found) for t in truth) if found and truth else 9.0


def write_video(path, frame_fn, n, fps=30, size=(160, 90), audio=None):
    w, h = size
    buf = b"".join(np.ascontiguousarray(np.clip(frame_fn(i), 0, 255).astype(np.uint8)).tobytes() for i in range(n))
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "%dx%d" % (w, h),
           "-r", str(fps), "-i", "-"]
    if audio:
        cmd += ["-i", str(audio), "-map", "0:v", "-map", "1:a", *fx.fit_audio(n / fps), "-c:a", "aac", "-b:a", "192k",
                "-frames:v", str(n)]
    cmd += ["-c:v", "libx264", "-crf", "14", "-pix_fmt", "yuv420p", str(path)]
    done = subprocess.run(cmd, input=buf, capture_output=True, timeout=90)
    if done.returncode:
        raise RuntimeError(done.stderr.decode(errors="replace")[-400:])
    return Path(path)


PAL = [(230, 60, 60), (60, 200, 90), (60, 90, 230), (240, 200, 40), (200, 60, 220), (40, 220, 220), (250, 140, 30), (120, 120, 120)]


def solid(size, rgb):
    w, h = size
    a = np.empty((h, w, 3), np.uint8)
    a[:] = rgb
    return a


def cut_frames(path, size=(48, 27), thr=40.0):
    fr = fx.frames(path, size)
    d = np.abs(np.diff(fr, axis=0)).mean(axis=(1, 2, 3))
    return [int(i + 1) for i in np.flatnonzero(d > thr)], fr


def frame_err(found, expected):
    if not expected:
        return 0
    if not found:
        return 999
    return max(min(abs(f - e) for f in found) for e in expected)


def cut_video(path, cuts, secs, fps=30, size=(96, 54), audio=None):
    bounds = [0.0] + list(cuts) + [secs + 1]

    def frame(i):
        t = i / fps
        k = max(j for j in range(len(bounds) - 1) if bounds[j] <= t + 1e-9)
        a = solid(size, PAL[k % len(PAL)])
        x = int((t * 40) % size[0])
        a[:, x:x + 3] = 255
        return a
    return write_video(path, frame, int(round(secs * fps)), fps, size, audio)


def rises_at(x, sr, times, pre=0.05, post=0.04):
    """dB rise of the short-term level just after each time over just before it: a sound starts there."""
    out = []
    for t in times:
        a = rms(x[max(0, int((t - pre) * sr)):max(1, int((t - 0.004) * sr))])
        b = rms(x[int((t + 0.002) * sr):int((t + post) * sr)])
        out.append(20 * math.log10((b + 1e-9) / (a + 1e-9)))
    return out


def env_db_track(x, sr, hop=0.01, win=0.05):
    n, h = int(win * sr), int(hop * sr)
    return np.array([20 * math.log10(rms(x[i:i + n]) + 1e-9) for i in range(0, max(1, len(x) - n), h)])


def _decay(d, tau, sr=SR):
    return np.exp(-tt(d, sr) / tau)


def _attack(n, ms, sr=SR):
    a = np.ones(n)
    k = min(n, max(1, int(ms * sr / 1000)))
    a[:k] = np.linspace(0, 1, k)
    return a


FOLEY = {
    "soft steps": lambda s: lowpass(noise(int(.12 * SR), s), 600) * _decay(.12, .03) * 0.9,
    "wind": lambda s: lowpass(noise(int(.5 * SR), s), 500) * _attack(int(.5 * SR), 20) * np.hanning(int(.5 * SR)) ** 0.2 * 0.8,
    "cloth": lambda s: bandpass(noise(int(.18 * SR), s), 1500, 5000) * _decay(.18, .05) * 0.7,
    "shoe scuff": lambda s: bandpass(noise(int(.2 * SR), s), 800, 3000) * _decay(.2, .07) * 0.8,
    "tap": lambda s: bandpass(noise(int(.05 * SR), s), 2000, 6000) * _decay(.05, .008) * 1.2,
    "paper": lambda s: highpass(noise(int(.25 * SR), s), 2500) * _decay(.25, .08) * 0.8,
    "squeak": lambda s: 0.6 * np.sin(2 * np.pi * np.cumsum(np.linspace(1800, 3200, int(.15 * SR))) / SR) * _decay(.15, .06),
    "double step": lambda s: np.concatenate([FOLEY["soft steps"](s), np.zeros(int(.08 * SR)), FOLEY["soft steps"](s + 1)]),
    "cartoon pop": lambda s: 0.8 * np.sin(2 * np.pi * np.cumsum(np.linspace(300, 900, int(.08 * SR))) / SR) * _decay(.08, .02),
    "paper flutter": lambda s: highpass(noise(int(.3 * SR), s), 3000) * (0.6 + 0.4 * np.sin(2 * np.pi * 25 * tt(.3))) * _decay(.3, .12) * 0.8,
    "thud": lambda s: (0.9 * np.sin(2 * np.pi * 70 * tt(.2)) + 0.3 * lowpass(noise(int(.2 * SR), s), 300)) * _decay(.2, .05),
    "whoosh": lambda s: bandpass(noise(int(.35 * SR), s), 400, 3000) * np.hanning(int(.35 * SR)) * 0.9,
    "ending sting": lambda s: sum(0.25 * np.sin(2 * np.pi * f * tt(.5)) for f in (523.3, 659.3, 784)) * _decay(.5, .2),
}


def _crackle(n, rate, seed, lo=2000, hi=9000, amp=0.6, tau=0.002):
    rng = np.random.default_rng(seed)
    x = np.zeros(n)
    k = int(rate * n / SR)
    c = bandpass(rng.standard_normal(int(0.004 * SR)), lo, hi) * np.exp(-np.arange(int(0.004 * SR)) / SR / tau)
    for i in rng.integers(0, n - len(c), k):
        x[i:i + len(c)] += amp * rng.uniform(0.3, 1) * c
    return x


TASTING = {
    "crust crackle": lambda: _crackle(int(.5 * SR), 60, 1, 1500, 7000),
    "straw slurp": lambda: bandpass(noise(int(.6 * SR), 2), 400, 1800) * np.linspace(0.2, 1, int(.6 * SR)) * 0.6,
    "fizzy sip": lambda: _crackle(int(.8 * SR), 200, 3, 5000, 12000, 0.3),
    "crispy crunch": lambda: _crackle(int(.3 * SR), 120, 4, 800, 6000, 0.9, 0.004),
    "juicy bite": lambda: lowpass(noise(int(.25 * SR), 5), 1200) * _decay(.25, .06) * 0.8,
    "soft chew": lambda: lowpass(noise(int(.6 * SR), 6), 600) * (0.5 + 0.5 * np.sin(2 * np.pi * 3 * tt(.6))) * 0.5,
    "noodle slurp": lambda: bandpass(noise(int(.9 * SR), 7), 600, 2500) * np.hanning(int(.9 * SR)) * 0.5,
    "ice crunch": lambda: _crackle(int(.35 * SR), 80, 8, 2500, 9000, 1.0, 0.006),
    "gulp": lambda: 0.7 * np.sin(2 * np.pi * np.cumsum(np.linspace(260, 120, int(.18 * SR))) / SR) * _decay(.18, .05),
    "lip smack": lambda: bandpass(noise(int(.04 * SR), 9), 1000, 4000) * _decay(.04, .006) * 1.2,
}


ACTION = {
    "ice on glass": lambda: sum(0.3 * np.sin(2 * np.pi * f * tt(.6)) * np.exp(-np.clip(tt(.6) - d, 0, None) / .04) * (tt(.6) >= d) for f, d in ((2600, .01), (3100, .17), (2850, .33))),
    "wet sauce scrape": lambda: bandpass(noise(int(.5 * SR), 11), 300, 2000) * (0.6 + 0.4 * np.sin(2 * np.pi * 9 * tt(.5))) * 0.4,
    "frying sizzle": lambda: _crackle(int(1.0 * SR), 400, 12, 3000, 12000, 0.25, 0.001),
    "cellophane crinkle": lambda: _crackle(int(.6 * SR), 90, 13, 2000, 10000, 0.7, 0.003),
}


def SFX_EAT(name):
    """The final-bite sound: a named tasting preset, else the generic bite fallback."""
    return (TASTING.get(name) or TASTING["juicy bite"])(), (name if name in TASTING else "juicy bite (generic fallback)")


def _feat(x):
    on = onsets(x, SR, 0.25, 0.008, 2.0)
    return {"centroid": centroid(x), "dur": len(x) / SR, "onset_rate": len(on) / (len(x) / SR),
            "crest": float(np.max(np.abs(x)) / (rms(x) + 1e-12))}


def _distinct(fs):
    ks = list(fs)
    worst = 9.0
    for i in range(len(ks)):
        for j in range(i + 1, len(ks)):
            a, b = fs[ks[i]], fs[ks[j]]
            d = max(abs(a[k] - b[k]) / (max(abs(a[k]), abs(b[k])) + 1e-9) for k in a)
            worst = min(worst, d)
    return worst


def polyblep_saw(f, d, sr=SR):
    n = int(d * sr)
    dt = f / sr
    ph = (np.arange(n) * dt) % 1.0
    y = 2 * ph - 1
    m1 = ph < dt
    t1 = ph[m1] / dt
    y[m1] -= t1 + t1 - t1 * t1 - 1
    m2 = ph > 1 - dt
    t2 = (ph[m2] - 1) / dt
    y[m2] -= t2 * t2 + t2 + t2 + 1
    return y


def naive_saw(f, d, sr=SR):
    return 2 * ((np.arange(int(d * sr)) * f / sr) % 1.0) - 1


def alias_db(y, f, sr=SR):
    """Energy off the harmonic series of f (aliases), relative to the total, in dB."""
    X = np.abs(np.fft.rfft(y * np.hanning(len(y)))) ** 2
    fq = np.fft.rfftfreq(len(y), 1 / sr)
    h = np.abs(fq / f - np.round(fq / f)) * f < 15
    return 10 * math.log10(X[~h].sum() / X.sum())


def karplus(f, d, sr=SR, seed=0):
    N = int(round(sr / f))
    buf = np.random.default_rng(seed).uniform(-1, 1, N)
    out = np.empty(int(d * sr))
    for i in range(len(out)):
        out[i] = buf[i % N]
        buf[i % N] = 0.996 * 0.5 * (buf[i % N] + buf[(i + 1) % N])
    return out


def adsr(n, a, d, s, r, sr=SR):
    A, D, R = int(a * sr), int(d * sr), int(r * sr)
    S = max(0, n - A - D - R)
    return np.concatenate([np.linspace(0, 1, A, False), np.linspace(1, s, D, False), np.full(S, s), np.linspace(s, 0, R)])[:n]


def rbj_lowpass(fc, q=0.7071, sr=SR):
    w = 2 * np.pi * fc / sr
    al = np.sin(w) / (2 * q)
    b = np.array([(1 - np.cos(w)) / 2, 1 - np.cos(w), (1 - np.cos(w)) / 2])
    a = np.array([1 + al, -2 * np.cos(w), 1 - al])
    return b / a[0], a / a[0]


def rbj_peaking(f0, gain_db, q, sr=SR):
    A = 10 ** (gain_db / 40)
    w = 2 * np.pi * f0 / sr
    al = np.sin(w) / (2 * q)
    b = np.array([1 + al * A, -2 * np.cos(w), 1 - al * A])
    a = np.array([1 + al / A, -2 * np.cos(w), 1 - al / A])
    return b / a[0], a / a[0]


def bs1770(x, sr=48000):
    """ITU-R BS.1770-4 integrated loudness (K-weighting, 400 ms blocks, 75 % overlap, absolute and relative gates)."""
    from scipy.signal import lfilter
    x = np.atleast_2d(np.asarray(x, float).T).T if np.ndim(x) == 1 else np.asarray(x, float)
    if x.ndim == 1:
        x = x[:, None]
    y = lfilter([1.53512485958697, -2.69169618940638, 1.19839281085285], [1, -1.69065929318241, 0.73248077421585], x, axis=0)
    y = lfilter([1, -2, 1], [1, -1.99004745483398, 0.99007225036621], y, axis=0)
    n, h = int(0.4 * sr), int(0.1 * sr)
    z = np.array([np.mean(y[i:i + n] ** 2, axis=0).sum() for i in range(0, len(y) - n + 1, h)])
    L = -0.691 + 10 * np.log10(z + 1e-20)
    z = z[L > -70]
    Lr = -0.691 + 10 * np.log10(z.mean()) - 10
    z = z[-0.691 + 10 * np.log10(z) > Lr]
    return float(-0.691 + 10 * np.log10(z.mean()))


def lookahead_limit(x, ceiling=0.5, la=0.005, rel=0.05, sr=SR):
    n = int(la * sr)
    from scipy.ndimage import maximum_filter1d
    pk = maximum_filter1d(np.abs(x), size=2 * n + 1)
    g = np.minimum(1.0, ceiling / (pk + 1e-12))
    a = math.exp(-1 / (rel * sr))
    out = np.empty_like(g)
    cur = 1.0
    for i, v in enumerate(g):
        cur = v if v < cur else a * cur + (1 - a) * v
        out[i] = cur
    return x * out


def note_hz(n):
    m = re.match(r"([A-G]#?)(-?\d)", n)
    idx = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"].index(m.group(1))
    return 440.0 * 2 ** ((idx + 12 * (int(m.group(2)) + 1) - 69) / 12)


def parse_steps(s):
    """One token per 16th step: NOTE[:len] starts a note (len steps), '-' ties, '.' rests, prefixes '!' accent,
    '?' ghost, '~' glide. Each bar must have exactly 16 steps."""
    bars = [b.split() for b in s.split("|")]
    for b in bars:
        if len(b) != 16:
            raise ValueError("bar has %d steps, needs 16" % len(b))
    ev, step = [], 0
    for b in bars:
        for tok in b:
            if tok == "-":
                if ev:
                    ev[-1]["len"] += 1
            elif tok != ".":
                acc = "!" in tok
                ghost = "?" in tok
                glide = "~" in tok
                name = tok.strip("!?~")
                ln = 1
                if ":" in name:
                    name, ln = name.split(":")
                    ln = int(ln)
                ev.append({"step": step, "note": name, "len": ln, "vel": 1.0 if acc else 0.35 if ghost else 0.7, "glide": glide})
            step += 1
    for a, b in zip(ev, ev[1:]):
        if a["step"] + a["len"] > b["step"]:
            raise ValueError("note at step %d overlaps the next note" % a["step"])
    return ev, step


def render_steps(events, bpm, steps, swing=0.0, sr=SR):
    st = 60 / bpm / 4
    x = np.zeros(int((steps + 4) * st * sr))
    times = []
    for e in events:
        t = 0.1 + e["step"] * st + (swing * st if e["step"] % 2 else 0)
        d = e["len"] * st * 0.95
        f = note_hz(e["note"])
        tn = tt(d, sr)
        y = e["vel"] * 0.6 * np.sin(2 * np.pi * f * tn) * adsr(len(tn), 0.004, 0.03, 0.8, 0.02, sr)
        place(x, y, t, sr)
        times.append(t)
    return x, times


CARVE_BANDS = [(250, -7.4), (400, -7.4), (630, -7.4), (1000, -7.4), (1600, -14.8), (2500, -7.4)]


def carve(bed, voice, strength=0.8, sr=SR, points=273, floor=-19.2, q=2.06):
    """Spectral sidechain: peaking dips at the voice bands, scaled by strength/0.8, applied through an envelope that
    follows the voice level (273 points, floor -19.2 dB), plus a slow-release level-match gain."""
    from scipy.signal import lfilter
    full = bed.copy()
    chain = []
    for f0, g in CARVE_BANDS:
        gd = g * strength / 0.8
        b, a = rbj_peaking(f0, gd, q, sr)
        full = lfilter(b, a, full)
        chain.append({"type": "peaking", "freq": f0, "gain": round(gd, 2), "q": q, "fromCarve": True})
    n = len(voice)
    edges = np.linspace(0, n, points + 1).astype(int)
    lv = np.array([20 * math.log10(rms(voice[edges[i]:edges[i + 1]]) + 1e-9) for i in range(points)])
    lv -= lv.max()
    env = np.clip((lv - floor) / 6.0, 0, 1)
    g = np.interp(np.arange(n), (edges[:-1] + edges[1:]) / 2, env)
    match_db = -1.5 * strength / 0.8
    a = math.exp(-1 / (0.6 * sr))
    lm = np.empty(n)
    cur = 0.0
    for i in range(0, n, 48):
        tgt = g[i]
        cur = tgt if tgt > cur else a ** 48 * cur + (1 - a ** 48) * tgt
        lm[i:i + 48] = cur
    gain = 10 ** (match_db * lm / 20)
    out = (bed + (full - bed) * g) * gain
    chain.append({"type": "gain", "db": round(match_db, 2), "fromCarve": True})
    return out, chain, [round(float(v), 4) for v in env], g


def audiomap(path):
    """librosa analysis to an audiomap: tempo/grid (trusted only when rhythmic), onsets + onset_rate, silences,
    hard stops, energy phases (level/density/feel), key moments, phrases."""
    import librosa
    y, sr = librosa.load(str(path), sr=22050, mono=True)
    dur = len(y) / sr
    hop = 512
    oenv = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop)
    on = librosa.onset.onset_detect(onset_envelope=oenv, sr=sr, hop_length=hop, units="time")
    tempo, beats = librosa.beat.beat_track(onset_envelope=oenv, sr=sr, hop_length=hop, units="time")
    tempo = 60.0 * (len(beats) - 1) / float(beats[-1] - beats[0]) if len(beats) > 2 else float(np.atleast_1d(tempo)[0])
    rms_ = librosa.feature.rms(y=y, hop_length=hop)[0]
    db = 20 * np.log10(rms_ + 1e-9)
    ft = librosa.frames_to_time(np.arange(len(db)), sr=sr, hop_length=hop)
    sil, i = [], 0
    while i < len(db):
        if db[i] < -50:
            j = i
            while j < len(db) and db[j] < -50:
                j += 1
            if ft[min(j, len(ft) - 1)] - ft[i] >= 0.3:
                sil.append([round(float(ft[i]), 3), round(float(ft[min(j, len(ft) - 1)]), 3)])
            i = j
        else:
            i += 1
    hard = [s[0] for s in sil if s[0] > 0.1 and db[max(0, np.searchsorted(ft, s[0] - 0.15)):np.searchsorted(ft, s[0])].max() > -30]
    o = oenv - oenv.mean()
    ac = np.correlate(o, o, "full")[len(o) - 1:]
    ac /= ac[0] + 1e-12
    lags = (np.arange(len(ac)) * hop / sr)
    win = (lags > 0.3) & (lags < 1.0)
    rhythm = float(np.percentile(oenv, 95) / (np.median(oenv) + 1e-9))
    rhythmic = bool(rhythm > 20 and len(on) / dur > 1.0 and float(ac[win].max() if win.any() else 0) > 0.3)
    phases = []
    for a in np.arange(0, dur, 2.0):
        m = (ft >= a) & (ft < a + 2.0)
        lev = float(db[m].mean()) if m.any() else -90
        dens = sum(1 for t in on if a <= t < a + 2.0) / 2.0
        phases.append({"t": round(float(a), 2), "level": "high" if lev > -20 else "mid" if lev > -40 else "low", "density": round(dens, 2),
                       "feel": "driving" if dens >= 1.5 else "sparse" if dens > 0 else "still"})
    km = sorted(on, key=lambda t: -oenv[min(len(oenv) - 1, int(t * sr / hop))])[:3]
    return {"duration": round(dur, 3), "tempo": round(tempo, 2) if rhythmic else None, "bpm_trusted": rhythmic, "rhythmicity": round(rhythm, 3),
            "beats_sec": [round(float(b), 3) for b in beats] if rhythmic else [], "onsets": [round(float(t), 3) for t in on],
            "onset_rate": round(len(on) / dur, 3), "silences": sil, "hard_stops": hard, "phases": phases,
            "key_moments": [round(float(t), 3) for t in sorted(km)], "phrases": [[0.0, s[0]] for s in sil[:1]]}


def stft_shape(n, centre_fn, bw, seed=0, sr=SR):
    from scipy.signal import stft, istft
    w = noise(n, seed)
    f, t, Z = stft(w, fs=sr, nperseg=1024)
    c = centre_fn(t)
    G = np.exp(-0.5 * ((np.log2(f[:, None] + 1) - np.log2(c[None, :])) / bw) ** 2)
    return istft(Z * G, fs=sr, nperseg=1024)[1][:n]


def centroid_track(x, sr=SR, win=0.05):
    n = int(win * sr)
    return np.array([centroid(x[i:i + n], sr) for i in range(0, len(x) - n, n)])


def snare(sr=SR, seed=5):
    t = tt(0.18, sr)
    return (0.4 * np.sin(2 * np.pi * 190 * t) + 0.5 * highpass(noise(len(t), seed), 1500)) * np.exp(-t / 0.05)


def _layer_feats(x, sr=SR):
    e = envelope(x, sr, 5)
    pk = int(np.argmax(e))
    above = np.flatnonzero(e > e.max() * 0.1)
    return {"centroid": centroid(x), "attack": pk / sr - (above[0] / sr if len(above) else 0), "body": (above[-1] - above[0]) / sr if len(above) else 0,
            "level": dbfs(x)}


def swing_groove(bpm, swing, bars=2, sr=SR):
    beat = 60 / bpm
    secs = bars * 4 * beat + 0.3
    x = np.zeros(int(secs * sr))
    hats = []
    for k in range(bars * 4):
        place(x, kick(), 0.05 + k * beat)
        for j in range(2):
            t = 0.05 + k * beat + j * beat / 2 + (swing * beat / 2 if j else 0)
            place(x, 0.4 * highpass(noise(int(.03 * sr), k * 2 + j), 6000) * _decay(.03, .006), t)
            hats.append(t)
    return x, hats


def measure_swing(x, bpm, sr=SR):
    beat = 60 / bpm
    ho = onsets(highpass(x, 5000), sr, 0.3, beat / 4)
    ko = onsets(lowpass(x, 200), sr, 0.3, beat / 2)
    tempo = 60 * (len(ko) - 1) / (ko[-1] - ko[0])
    offs = [h for h in ho if min(abs(h - k) for k in ko) > beat / 8]
    sw = float(np.median([(h - max(k for k in ko if k <= h) - beat / 2) / (beat / 2) for h in offs]))
    return tempo, sw


REF_TUNES = {"twinkle": "C4 C4 G4 G4 A4 A4 G4 F4 F4 E4 E4 D4 D4 C4", "ode_to_joy": "E4 E4 F4 G4 G4 F4 E4 D4 C4 C4 D4 E4 E4 D4 D4",
             "frere_jacques": "C4 D4 E4 C4 C4 D4 E4 C4 E4 F4 G4 E4 F4 G4", "happy_birthday": "G4 G4 A4 G4 C5 B4 G4 G4 A4 G4 D5 C5"}


def midi(n):
    return int(round(69 + 12 * math.log2(note_hz(n) / 440)))


def intervals(notes):
    m = [midi(n) for n in notes]
    return [b - a for a, b in zip(m, m[1:])]


def shared_ngram(a, b, n=5):
    A = {tuple(a[i:i + n]) for i in range(len(a) - n + 1)}
    return any(tuple(b[i:i + n]) in A for i in range(len(b) - n + 1))


def originality(notes):
    iv = intervals(notes)
    return [k for k, v in REF_TUNES.items() if shared_ngram(iv, intervals(v.split()))]


def midi_from_hz(f):
    return int(round(69 + 12 * math.log2(f / 440)))


def pitch_track(x, sr=SR, win=0.02):
    n = int(win * sr)
    out = []
    for i in range(0, len(x) - n, n):
        seg = x[i:i + n]
        if rms(seg) < 1e-3:
            continue
        out.append(peak_hz(np.pad(seg, (0, 8 * n)), sr, 40))
    return np.array(out)


def sc_duck(music, voice, out, thr, ratio, attack, release, makeup=1):
    ff("-i", music, "-i", voice, "-filter_complex",
       "[0:a][1:a]sidechaincompress=threshold=%s:ratio=%s:attack=%s:release=%s:makeup=%s[d]" % (thr, ratio, attack, release, makeup),
       "-map", "[d]", "-c:a", "pcm_s16le", out)
    return Path(out)


def _voice_with_pauses(secs=4.0):
    spans = [(0.3, 1.3), (2.0, 3.2)]
    return speechlike(secs, spans, f0=150, amp=0.4), spans


def level_curve(x, sr, fps=100, win=0.05):
    n, h = int(win * sr), int(sr / fps)
    return np.array([20 * math.log10(rms(x[i:i + n]) + 1e-9) for i in range(0, max(1, len(x) - n), h)])


def find_drops(L, fps=100):
    out = []
    for i in range(4 * fps, len(L) - fps // 2):
        dip = L[i - int(1.2 * fps):i].mean()
        before = L[i - 4 * fps:i - int(1.5 * fps)].mean()
        after = L[i:i + fps // 2].mean()
        if dip <= before - 3.5 and after >= dip + 6:
            if not out or i / fps - out[-1] > 2:
                out.append(i / fps)
    return out


def find_hits(L, fps=100, rise=9):
    out = []
    for i in range(5, len(L)):
        if L[i] - L[i - 5] >= rise and (not out or i / fps - out[-1] > 0.4):
            out.append(i / fps)
    return out


def music_window(x, sr, length, after=0.0, fps=100):
    L = level_curve(x, sr, fps)
    drops, hits = find_drops(L, fps), find_hits(L, fps)
    lifts = []
    for i in range(2 * fps, len(L) - 2 * fps, fps // 2):
        if L[i:i + 2 * fps].mean() - L[i - 2 * fps:i].mean() >= 3 and not any(abs(i / fps - d) < 2 for d in drops):
            lifts.append(i / fps)
    best = []
    for s in np.arange(after, len(x) / sr - length + 1e-9, 0.5):
        e = s + length
        sc = 0
        if any(s <= d <= s + length / 4 for d in drops):
            sc += 8
        if any(s + 0.5 * length <= l_ <= s + 0.85 * length for l_ in lifts):
            sc += 5
        if any(e - 1.0 <= h <= e for h in hits):
            sc += 4
        best.append((sc, round(float(s), 2)))
    best.sort(key=lambda r: (-r[0], r[1]))
    return best, drops, lifts, hits


def window_track(secs=70.0, sr=SR):
    """120 BPM kicks over a pad, with a breath-then-drop at 34.2 s, a build at 40-44 s and a big final hit at 49.6 s."""
    x, _ = drum_loop(120, secs, sr)
    x = 0.5 * x + music_bed(secs, sr, 0.15)
    g = np.ones(len(x))
    g[int(33.0 * sr):int(34.2 * sr)] = 0.15
    ramp = (tt(secs, sr) >= 40) & (tt(secs, sr) < 44)
    g[ramp] = np.linspace(0.4, 1.4, ramp.sum())
    g[int(36 * sr):int(40 * sr)] = 0.4
    g[int(44 * sr):int(49.6 * sr)] = 1.0
    g[int(49.0 * sr):int(49.6 * sr)] = 0.3
    x = x * g
    place(x, addp(1.0 * kick(), 0.5 * highpass(noise(int(.4 * sr), 3), 2000) * _decay(.4, .15)), 49.6, sr)
    return x


def snap_times(times, accents, beats, win=0.35, fps=30):
    out = []
    for t in times:
        near = [a for a in accents if abs(a - t) <= win]
        if near:
            s, kind = min(near, key=lambda a: abs(a - t)), "accent"
        else:
            s, kind = min(beats, key=lambda b: abs(b - t)), "beat"
        out.append({"t": t, "snapped": round(s, 3), "kind": kind, "offset_s": round(s - t, 3), "offset_frames": round((s - t) * fps, 2), "frame": int(round(s * fps))})
    return out


def verify_hits(x, sr, hits, fps=30, win=0.0125, search=0.25):
    n = int(win * sr)
    L = np.array([rms(x[i:i + n]) for i in range(0, len(x) - n, n)])
    Ld = 20 * np.log10(L + 1e-9)
    k = int(round(0.05 / win))
    rep = []
    for h in hits:
        a, b = int((h - search) / win), int((h + search) / win)
        rise = [(Ld[i] - Ld[i - k:i].max(), i) for i in range(max(k, a), min(len(Ld), b))]
        r, i = max(rise)
        on = i * win
        off = on - h
        rep.append({"hit": h, "onset": round(on, 4), "offset_ms": round(off * 1000, 1), "frames": round(off * fps, 2),
                    "flag": "ok" if abs(off) <= 1 / fps else ("LATE" if off > 0 else "EARLY")})
    return rep


def cut_audio(x, sr, start, length, fade):
    a = x[int(round(start * sr)):int(round(start * sr)) + int(round(length * sr))].copy()
    fi = int(0.012 * sr)
    a[:fi] *= np.linspace(0, 1, fi)[:, None] if a.ndim == 2 else np.linspace(0, 1, fi)
    fo = int(fade * sr)
    rem = np.arange(fo, 0, -1) - 1
    g = (rem / fo) ** 1.5
    a[-fo:] *= g[:, None] if a.ndim == 2 else g
    return a


def astats_rms(path, fps=30, sr=48000):
    txt = Path(path).with_suffix(".astats.txt")
    ff("-i", path, "-af", "aresample=%d,asetnsamples=%d,astats=metadata=1:reset=1,ametadata=print:key=lavfi.astats.Overall.RMS_level:file=%s"
       % (sr, sr // fps, txt.as_posix()), "-f", "null", "-")
    vals = [float(v) if v not in ("-inf", "inf") else -120.0 for v in re.findall(r"RMS_level=(\S+)", txt.read_text())]
    return np.array(vals), txt


def analyser_level(x, sr, t, fft=256):
    i = int(t * sr)
    seg = x[i:i + fft]
    b = np.clip(np.round(128 + seg * 128), 0, 255).astype(np.uint8)
    v = (b.astype(float) - 128) / 128
    return min(1.0, math.sqrt(float(np.mean(v * v))) * 4)


def band_bars(x, sr, t, n=16, win=0.04, lo=50, hi=8000):
    i = int(t * sr)
    seg = x[i:i + int(win * sr)]
    if len(seg) < 16:
        return np.zeros(n)
    X = np.abs(np.fft.rfft(seg * np.hanning(len(seg))))
    f = np.fft.rfftfreq(len(seg), 1 / sr)
    edges = np.geomspace(lo, hi, n + 1)
    v = np.array([X[(f >= a) & (f < b)].sum() for a, b in zip(edges, edges[1:])])
    return v / (len(seg) / 4)


def accent_series(beats, n, fps, attack=2, tau=0.08):
    a = np.zeros(n)
    for b in beats:
        f0 = int(round(b * fps))
        for i in range(f0, n):
            d = i - f0
            v = d / attack if d < attack else math.exp(-(d - attack) / fps / tau)
            a[i] = max(a[i], v)
    return a


def disc_video(wd, scale, fps=30, size=(120, 120), name="pulse.mp4", r0f=0.3):
    w, h = size
    yy, xx = np.mgrid[0:h, 0:w]
    r0 = r0f * min(w, h)

    def frame(i):
        m = ((xx - w / 2) ** 2 + (yy - h / 2) ** 2) <= (r0 * scale[i]) ** 2
        a = np.zeros((h, w, 3))
        a[m] = 255
        return a
    v = write_video(Path(wd) / name, frame, len(scale), fps, size)
    fr = fx.frames(v, size)
    area = (fr.mean(axis=3) > 128).sum(axis=(1, 2))
    return v, np.sqrt(area / (math.pi * r0 * r0))


def token_boxes(tokens, x0=4, y0=20, cw=6):
    out, x = [], x0
    for t in tokens:
        out.append((x - 1, y0 - 2, x + cw * len(t), y0 + 10))
        x += cw * (len(t) + 1)
    return out


def _capture(wd, secs=12.0, fps=30, W=160, H=90):
    """Synthetic screen capture: a static marker square, and a fast-moving block only inside known busy windows."""
    busy = [(2.0, 3.6), (6.0, 7.6), (9.0, 10.6)]

    def frame(i):
        t = i / fps
        a = solid((W, H), (40, 44, 60)).astype(float)
        a[30:50, 70:90] = 230
        for k, (s0, s1) in enumerate(busy):
            if s0 <= t < s1:
                x = int(10 + ((t - s0) * 160) % (W - 30))
                a[60:75, x:x + 14] = PAL[k]
        return a
    v = write_video(Path(wd) / "capture.mp4", frame, int(secs * fps), fps, (W, H))
    return v, busy


def trailer(wd, bpm=150, fps=30, vertical=False, slowmo_shot=None):
    from PIL import Image
    W, H = 160, 90
    cap, busy = _capture(wd)
    bar = 4 * 60 / bpm
    shot_len = bar if bar <= 2.6 else 2 * 60 / bpm
    n_shots = 3
    end_card = 2.5
    secs = bar + n_shots * shot_len + end_card
    k, kt = drum_loop(bpm, secs + 0.3)
    for b in range(int(secs / bar) + 1):
        place(k, 0.5 * highpass(noise(int(.1 * SR), b), 3000) * _decay(.1, .03), b * bar)
    music = save(wd, "music.wav", k[:int(secs * SR)])
    on = onsets(lowpass(k[:int(secs * SR)], 200), SR, 0.3, 0.2)
    bar_on = [o for o in on if abs(o / bar - round(o / bar)) * bar < 0.03]
    fr = fx.frames(cap, (W, H))
    motion = np.r_[0, np.abs(np.diff(fr, axis=0)).mean(axis=(1, 2, 3))]
    L = int(round(shot_len * fps))
    score = np.convolve(motion, np.ones(L), "valid")
    picks = []
    for s in np.argsort(-score):
        if all(abs(s - p) >= L for p in picks):
            picks.append(int(s))
        if len(picks) == n_shots:
            break
    picks.sort()
    edl = [{"kind": "title", "start": 0.0, "dur": bar}]
    for j, s in enumerate(picks):
        diff = np.abs(np.diff(fr[s:s + L], axis=0)).mean(axis=(0, 3))
        yy, xx = np.unravel_index(np.argmax(diff), diff.shape)
        edl.append({"kind": "shot", "start": round(bar + j * shot_len, 4), "dur": shot_len, "src_frame": s, "src_s": round(s / fps, 3),
                    "push": [1.0, 1.25], "focus": [int(xx), int(yy)], "speed": 0.5 if slowmo_shot == j else 1.0})
    edl.append({"kind": "end", "start": round(bar + n_shots * shot_len, 4), "dur": end_card})
    total = int(round(secs * fps))
    frames_ = []
    for i in range(total):
        t = i / fps
        e = max((x for x in edl if x["start"] <= t + 1e-9), key=lambda x: x["start"])
        if e["kind"] == "title":
            a = solid((W, H), (250, 250, 250)).astype(float)
            a[40:50, 40:120] = 20
        elif e["kind"] == "end":
            a = solid((W, H), (10, 10, 10)).astype(float)
            a[40:50, 50:110] = 200
        else:
            u = (t - e["start"]) / e["dur"]
            src = fr[min(len(fr) - 1, e["src_frame"] + int((i - round(e["start"] * fps)) * e["speed"]))]
            z = 1.0 + 0.25 * u
            cw, ch = W / z, H / z
            fx_, fy_ = e["focus"]
            x0 = min(max(0, fx_ - cw / 2), W - cw)
            y0 = min(max(0, fy_ - ch / 2), H - ch)
            im = Image.fromarray(src.astype(np.uint8)).resize((W, H), Image.BILINEAR, box=(x0, y0, x0 + cw, y0 + ch))
            a = np.asarray(im).astype(float) * np.array([(1.0, 0.75, 0.75), (0.75, 1.0, 0.75), (0.75, 0.75, 1.0)][j_of(edl, e) % 3])
            prog = int((i % int(round(bar * fps))) / (bar * fps) * W)
            a[86:90, :prog] = (240, 200, 60)
        if vertical:
            from PIL import ImageFilter
            im = Image.fromarray(a.astype(np.uint8))
            bg = im.resize((90 * 16 // 9 * 2, 160)).crop((0, 0, 90, 160)).filter(ImageFilter.GaussianBlur(6))
            fg = im.resize((90, int(90 * H / W)))
            bg.paste(fg, (0, (160 - fg.height) // 2))
            a = np.asarray(bg).astype(float)
        frames_.append(a)
    size = (90, 160) if vertical else (W, H)
    v = write_video(Path(wd) / ("trailer_9x16.mp4" if vertical else "trailer.mp4"), lambda i: frames_[i], total, fps, size, audio=music)
    edl_p = jdump(Path(wd) / "edl.json", {"bpm": bpm, "bar_s": bar, "fps": fps, "edl": edl})
    return {"video": v, "edl": edl, "edl_path": edl_p, "busy": busy, "bar": bar, "shot_len": shot_len, "fps": fps, "secs": secs,
            "bar_onsets": bar_on, "capture": cap, "capture_s": 12.0, "frames": np.array(frames_), "size": size}


def j_of(edl, e):
    return [x for x in edl if x["kind"] == "shot"].index(e)


def _trailer_checks(r, verify_onsets=True):
    fps = r["fps"]
    fr = fx.frames(r["video"], r["size"])
    d = np.abs(np.diff(fr[:, :80] if r["size"][1] == 90 else fr, axis=0)).mean(axis=(1, 2, 3))
    found = [int(i + 1) for i in np.flatnonzero(d > 15)]
    planned = [int(round(e["start"] * fps)) for e in r["edl"][1:]]
    shots = [e for e in r["edl"] if e["kind"] == "shot"]
    ov = lambda e, b0, b1: max(0.0, min(e["src_s"] + e["dur"], b1) - max(e["src_s"], b0))
    in_busy = all(any(ov(e, b0, b1) >= 0.8 * min(e["dur"], b1 - b0) for b0, b1 in r["busy"]) for e in shots)
    worst = max(min(abs(f - o * fps) for o in r["bar_onsets"]) for f in found) if found and r["bar_onsets"] else 99
    return fr, found, planned, shots, in_busy, worst


def _marker_w(a):
    m = a.min(axis=-1) > 150
    rows = np.flatnonzero(m.any(1))
    cols = np.flatnonzero(m.any(0))
    return (cols[-1] - cols[0] + 1) if len(cols) else 0


def frame_table(bpms, fps=60, sr=48000):
    return {b: {"frames_per_bar": 240 * fps / b, "frames_per_beat": 60 * fps / b, "bar_s": 240 / b, "samples_per_bar": 240 * sr / b} for b in bpms}


def grid_drift(bpm, bars, fps=60):
    exact = [k * 240 * fps / bpm for k in range(1, bars + 1)]
    acc, t = [], 0
    for _ in range(bars):
        t += round(240 * fps / bpm)
        acc.append(t)
    return max(abs(a - e) for a, e in zip(acc, exact))


def _grid_video(wd, bpm, bars, fps=60):
    secs = bars * 240 / bpm
    cuts = [k * 240 / bpm for k in range(1, bars)]
    x, _ = drum_loop(bpm, secs + 0.2)
    a = save(wd, "grid%d.wav" % bpm, x)
    v = cut_video(Path(wd) / ("grid%d.mp4" % bpm), cuts, secs, fps, (32, 18), audio=a)
    found, _ = cut_frames(v, (32, 18), 30)
    return v, found, [int(round(c * fps)) for c in cuts]


def voiced_runs(x, sr=SR, win=0.04):
    n = int(win * sr)
    flags = []
    for i in range(0, len(x) - n, n):
        seg = x[i:i + n]
        if dbfs(seg) < -40:
            flags.append(False)
            continue
        seg = seg - seg.mean()
        ac = np.correlate(seg, seg, "full")[n - 1:]
        lo, hi = int(sr / 300), int(sr / 100)
        flags.append(bool(ac[lo:hi].max() > 0.5 * ac[0]))
    runs, cur = [], 0
    for f in flags + [False]:
        if f:
            cur += 1
        elif cur:
            runs.append(round(cur * win, 3))
            cur = 0
    return runs


def song_fixture(secs=13.0):
    """intro 0-2 quiet pad, verse 2-6 kicks + pad, build 6-8 rising, drop 8-11 loud, outro 11-13 quiet."""
    t = tt(secs)
    pad = music_bed(secs, amp=0.25)
    k, _ = drum_loop(120, secs)
    g = np.interp(t, [0, 2, 2.01, 6, 8, 8.01, 11, 11.01, 13], [0.05, 0.05, 0.35, 0.35, 0.8, 1.0, 1.0, 0.04, 0.02])
    kg = np.interp(t, [0, 1.99, 2, 11, 11.01, 13], [0, 0, 1, 1, 0, 0])
    return (pad + k * kg) * g


def structure_map(x, sr, hop=0.25):
    n, w = int(hop * sr), int(0.5 * sr)
    L = np.array([20 * math.log10(rms(x[i:i + w]) + 1e-9) for i in range(0, len(x) - w + 1, n)])
    top = L.max()
    lab = []
    for i, l in enumerate(L):
        if l >= top - 2.5:
            lab.append("drop")
        elif l < top - 18:
            lab.append("intro" if i < len(L) / 2 else "outro")
        else:
            lab.append("verse")
    first_drop = lab.index("drop")
    for i in range(first_drop - 1, 0, -1):
        if lab[i] == "verse" and L[i] > L[max(0, i - 4)] + 1.5:
            lab[i] = "build"
        else:
            break
    secs_ = []
    for i, l in enumerate(lab):
        if not secs_ or secs_[-1]["kind"] != l:
            secs_.append({"kind": l, "t": round(i * hop, 2)})
    for a, b in zip(secs_, secs_[1:]):
        a["end"] = b["t"]
    secs_[-1]["end"] = round(len(lab) * hop + 0.25, 2)
    merged = []
    for sct in secs_:
        if merged and sct["end"] - sct["t"] < 0.6:
            merged[-1]["end"] = sct["end"]
        elif merged and merged[-1]["kind"] == sct["kind"]:
            merged[-1]["end"] = sct["end"]
        else:
            merged.append(dict(sct))
    return merged


def spring_curve(n, fps, k=160.0, c=14.0, x0=0.8, target=1.0):
    x, v, out = x0, 0.0, []
    dt = 1 / fps / 20
    for _ in range(n):
        out.append(x)
        for _ in range(20):
            a = -k * (x - target) - c * v
            v += a * dt
            x += v * dt
    return np.array(out)


def eq_bars(x, sr, fps, n_side=16, tau=0.12, Hmax=0.6):
    nf = int(len(x) / sr * fps)
    vals = np.zeros((nf, n_side))
    cur = np.zeros(n_side)
    a = math.exp(-1 / (fps * tau))
    for i in range(nf):
        b = np.clip(band_bars(x, sr, i / fps, n_side, 0.04, 60, 8000), 0, 1)
        cur = np.maximum(b, a * cur + (1 - a) * b)
        vals[i] = cur * Hmax
    return vals


def fine_hz(x, sr=SR, lo=50, hi=2000):
    n = 1 << 17
    X = np.abs(np.fft.rfft(x * np.hanning(len(x)), n))
    f = np.fft.rfftfreq(n, 1 / sr)
    m = (f >= lo) & (f <= hi)
    k = int(np.flatnonzero(m)[np.argmax(X[m])])
    a, b, c = np.log(X[k - 1] + 1e-12), np.log(X[k] + 1e-12), np.log(X[k + 1] + 1e-12)
    return float(f[k] + 0.5 * (a - c) / (a - 2 * b + c) * (f[1] - f[0]))


def render_scale(cents, f0=261.63, d=0.3, sr=SR):
    out = []
    for c in cents:
        f = f0 * 2 ** (c / 1200)
        out.append((sine(f, d, 0.4) + sine(2 * f, d, 0.1)) * np.hanning(int(round(d * sr))))
    return np.concatenate(out)


def measure_scale(x, n, f0=261.63, d=0.3, sr=SR):
    L = int(round(d * sr))
    return [round(1200 * math.log2(fine_hz(x[i * L + L // 6:(i + 1) * L - L // 6]) / f0), 1) for i in range(n)]


def beat_durations(bpm, beats_per_bar=4):
    beat = 60.0 / bpm
    return {"beat": round(beat, 4), "bar": round(beat * beats_per_bar, 4), "8bar": round(beat * beats_per_bar * 8, 4)}


LIVING_ARTIST_PAT = re.compile(r"\b(in the style of|sounds? like|imitat\w*|voice of)\b", re.I)


BRIEF_FIELDS = ["genre_maqam", "bpm", "structure", "rhyme", "hook", "instrumentation", "vocal", "reference_feel"]


def lint_brief(b):
    errs = ["missing %s" % k for k in BRIEF_FIELDS if not b.get(k)]
    if LIVING_ARTIST_PAT.search(json.dumps(b, ensure_ascii=False)):
        errs.append("living-artist imitation")
    return errs


def bar_plan(sections, bpm, bpb=4, styles=None, key="A minor"):
    """ElevenLabs music_v2 composition plan in whole bars: seconds = bars·bpb·60/bpm (ms); first chunk global styles,
    tempo and key; later chunks repeat the tempo; instrumental sections get '{instrumental, no vocals}'."""
    plan, t = [], 0.0
    for i, s in enumerate(sections):
        ms = int(round(s["bars"] * bpb * 60000.0 / bpm))
        loc = list(s.get("styles", []))
        if s.get("instrumental"):
            loc.append("{instrumental, no vocals}")
        pos = (["%d bpm" % bpm, key] + list(styles or [])) if i == 0 else ["%d bpm" % bpm]
        plan.append({"section_name": s["name"], "duration_ms": ms, "positive_local_styles": pos + loc,
                     "negative_local_styles": list(s.get("avoid", [])), "lines": list(s.get("lines", [])), "start_ms": int(round(t * 1000))})
        t += ms / 1000.0
    return {"sections": plan, "total_ms": int(round(t * 1000))}


def lint_bar_plan(pl, bpm, bpb=4):
    bar_ms = bpb * 60000.0 / bpm
    errs = []
    for s in pl["sections"]:
        if abs(s["start_ms"] / bar_ms - round(s["start_ms"] / bar_ms)) > 0.01:
            errs.append("%s starts off a bar line" % s["section_name"])
        if not 3000 <= s["duration_ms"] <= 120000:
            errs.append("%s length %d ms outside 3-120 s" % (s["section_name"], s["duration_ms"]))
        if any(len(l) > 200 for l in s["lines"]):
            errs.append("%s has a line over 200 chars" % s["section_name"])
        if "%d bpm" % bpm not in s["positive_local_styles"]:
            errs.append("%s does not carry the tempo" % s["section_name"])
    if not 3000 <= pl["total_ms"] <= 600000:
        errs.append("song length outside 3 s-10 min")
    return errs


def sfx_source(layer, d, seed):
    n = int(d * SR)
    if layer == "ambience":
        return lowpass(noise(n, seed), 800) * np.hanning(n)
    if layer == "foley":
        return bandpass(noise(n, seed), 1500, 4000) * np.exp(-np.arange(n) / (0.05 * SR))
    if layer == "hard FX":
        k = kick(); return np.pad(k, (0, max(0, n - len(k))))[:n]
    if layer == "music":
        return music_bed(d, amp=0.3) * _fade(n)
    return sine(2000, d, 0.5) * _fade(n)


def _fade(n, a=0.004):
    """4 ms attack then a linear tail to zero, so a cue's start is where its timecode says."""
    k = max(1, int(a * SR))
    return np.minimum(np.arange(n) / k, 1.0) * np.linspace(1, 0, n) ** 0.5


def render_sheet(rows, secs, honour=True):
    out = np.zeros((int(secs * SR), 2))
    for i, r in enumerate(rows):
        s = sfx_source(r["layer"], r["dur"], i)
        s = s / (np.max(np.abs(s)) + 1e-12) * 10 ** (r["dbfs"] / 20)
        pan = r["pan"] if honour else 0.0
        th = (pan + 1) * math.pi / 4
        t = r["tc"] if honour else 0.0
        a = int(t * SR)
        out[a:a + len(s), 0] += s[:len(out) - a] * math.cos(th)
        out[a:a + len(s), 1] += s[:len(out) - a] * math.sin(th)
    return out


def licence_gate(manifest):
    ok, blocked = [], []
    for it in manifest:
        src = it.get("source", "")
        if src == "user-provided" and it.get("provided_by"):
            ok.append(it["file"])
        elif src == "licensed" and it.get("licence") and it.get("licence_id"):
            ok.append(it["file"])
        elif src in ("own-composition", "public-domain") and it.get("evidence"):
            ok.append(it["file"])
        else:
            blocked.append((it["file"], "no proof of licence for source %r" % (src or "unknown")))
    return ok, blocked


VOC = {
    "bpm": [r"\b\d{2,3}\s*bpm\b"],
    "vocal": [r"\bvocals?\b", r"\bvoice\b", r"\bbreathy\b", r"\braspy\b", r"\bfalsetto\b", r"\bbelted\b", r"\bbaritone\b", r"\btenor\b",
              r"\bchoir\b", r"\brapped\b", r"\bwhisper\w*\b"],
    "production": [r"\bmix\b", r"\bproduction\b", r"\breverb\b", r"\bsaturation\b", r"\bsidechain\w*\b", r"\bstereo\b", r"\bmaster\w*\b",
                   r"\banalog\b", r"\btape\b", r"\bpolished\b", r"\bcrisp\b", r"\bpunchy\b", r"\bdistortion\b"],
    "instrument": [r"\bpiano\b", r"\bguitar\b", r"\bbass\b", r"\bsynths?\b", r"\bstrings\b", r"\bviolin\b", r"\boud\b", r"\bqanun\b", r"\bney\b",
                   r"\bdarbu?o?u?ka\b", r"\baccordion\b", r"\bdrums\b", r"\b808s?\b", r"\bbrass\b", r"\bpads?\b", r"\bhi-hats\b", r"\bpercussion\b",
                   r"\btabla\b", r"\briq\b", r"\bdaf\b", r"\bcello\b", r"\bgroove\b", r"\bclaps\b"],
    "genre": [r"\bpop\b", r"\brock\b", r"\bhip-hop\b", r"\btrap\b", r"\bedm\b", r"\bhouse\b", r"\btechno\b", r"\bjazz\b", r"\bclassical\b",
              r"\bfolk\b", r"\bmetal\b", r"\bambient\b", r"\blo-?fi\b", r"\br&b\b", r"\brnb\b", r"\bsynthwave\b", r"\bsynth-pop\b", r"\bdream-pop\b",
              r"\bshoegaze\b", r"\bkhaleeji\b", r"\brai\b", r"\bshaabi\b", r"\bboom-bap\b", r"\bdisco\b", r"\bsoul\b", r"\btrailer\b"],
    "mood": [r"\bmelanchol\w*\b", r"\bnostalgic\b", r"\beuphoric\b", r"\bdark\b", r"\buplifting\b", r"\btense\b", r"\bdreamy\b", r"\bhopeful\b",
             r"\bromantic\b", r"\baggressive\b", r"\bintimate\b", r"\bbittersweet\b", r"\btriumphant\b", r"\bmysterious\b", r"\bwarm\b", r"\byearning\b"],
}


LAYERS6 = ["genre", "mood", "instrument", "vocal", "bpm", "production"]


def tag_cat(tag, order=("bpm", "vocal", "production", "genre", "instrument", "mood")):
    t = tag.lower()
    for c in order:
        if any(re.search(p, t) for p in VOC[c]):
            return c
    return "other"


def split_tags(style):
    return [t.strip() for t in style.split(",") if t.strip()]


def build_style6(d):
    tags = [d["genre"]] + d["moods"] + d["instruments"] + [d["vocal"], "%d BPM" % d["bpm"]] + d["production"]
    return ", ".join(tags)


def lint_style6(style, lyrics="", title=""):
    tags = split_tags(style)
    cats = [tag_cat(t) for t in tags]
    idx = [LAYERS6.index(c) if c in LAYERS6 else 99 for c in cats]
    errs = []
    if not 5 <= len(tags) <= 8:
        errs.append("%d tags (want 5-8)" % len(tags))
    if not cats or cats[0] != "genre":
        errs.append("genre not front-loaded")
    if idx != sorted(idx):
        errs.append("layers out of order: %s" % "→".join(cats))
    if 99 in idx:
        errs.append("unclassified tag")
    if set(LAYERS6) - set(cats):
        errs.append("missing layers %s" % sorted(set(LAYERS6) - set(cats)))
    if len(style) > 1000 or len(lyrics) > 5000 or len(title) > 100:
        errs.append("field over its limit")
    return errs, cats


STD_LABELS = ["Intro", "Verse", "Pre-Chorus", "Chorus", "Post-Chorus", "Hook", "Bridge", "Build-Up", "Drop", "Instrumental Break",
              "Interlude", "Break", "Outro", "End", "Fade Out"]


SEC_RE = re.compile(r"^\[([A-Za-z][A-Za-z\- ]*?)(?:\s+(\d+))?\s*(?:[:|]\s*(.*?))?\]$")


def parse_sections(text):
    out = []
    for ln in text.splitlines():
        m = SEC_RE.match(ln.strip())
        if m:
            desc = [d.strip() for d in re.split(r"[,|]", m.group(3) or "") if d.strip()]
            out.append({"label": m.group(1).strip(), "n": m.group(2), "desc": desc})
    return out


DENSE = re.compile(r"drums|harmon|choir|stack|full|layer|claps|808|strings", re.I)


def lint_sections(text):
    S = parse_sections(text)
    errs = []
    for s in S:
        if s["label"] not in STD_LABELS:
            errs.append("non-standard label [%s] (would be sung)" % s["label"])
        if s["desc"] and not 4 <= len(s["desc"]) <= 7:
            errs.append("[%s] has %d descriptors (want 4-7)" % (s["label"], len(s["desc"])))
    ch = [sum(bool(DENSE.search(d)) for d in s["desc"]) for s in S if s["label"] == "Chorus"]
    if len(ch) >= 2 and not (all(b >= a for a, b in zip(ch, ch[1:])) and ch[-1] > ch[0]):
        errs.append("choruses do not escalate %s" % ch)
    br = [s for s in S if s["label"] == "Bridge"]
    if br and ch and not (sum(bool(DENSE.search(d)) for d in br[0]["desc"]) < min(ch) or any(re.search(r"sparse|strip|no drums", d, re.I) for d in br[0]["desc"])):
        errs.append("bridge not stripped")
    return errs, S


def section_sheet(plan):
    return "\n".join("[%s%s: %s]\n%s" % (lab, (" %d" % n) if n else "", ", ".join(desc), "\n".join(lines)) for lab, n, desc, lines in plan) + "\n"


STRUCT_TAGS = {"Intro", "Verse", "Pre-Chorus", "Chorus", "Bridge", "Build-Up", "Drop", "Instrumental Break", "Outro", "End", "Fade Out", "Melodic Instrumental"}


VOCAL_TAGS = {"Whispered", "Belted", "Falsetto", "Choir", "Rapped", "Spoken Word"}


FX_TAGS = {"Crescendo", "Silence", "Echo"}


def lint_tags(text, hard_stop=True):
    errs, last = [], None
    for ln in text.splitlines():
        s = ln.strip()
        if not s:
            continue
        tags = re.findall(r"\[([^\]]+)\]", s)
        if tags and re.sub(r"\[[^\]]+\]", "", s).strip():
            errs.append("tag not on its own line: %r" % s)
        for tg in tags:
            base = re.sub(r"\s+\d+$", "", tg.split(":")[0].split("|")[0].strip())
            if base not in STRUCT_TAGS | VOCAL_TAGS | FX_TAGS:
                errs.append("unknown tag [%s]" % tg)
            last = base
        for cue in re.findall(r"\(([^)]*)\)", s):
            if not 1 <= len(cue.split()) <= 3:
                errs.append("cue (%s) is %d words (want 1-3)" % (cue, len(cue.split())))
    if hard_stop and last != "End":
        errs.append("no [End] for a hard stop")
    return errs


def tidy_tags(text):
    """Puts every tag on its own line, trims parenthesised cues to their first 3 words and closes with [End]."""
    out = []
    for ln in text.splitlines():
        s = ln.strip()
        if not s:
            continue
        s = re.sub(r"\(([^)]*)\)", lambda m: "(" + " ".join(m.group(1).split()[:3]) + ")", s)
        parts = re.split(r"(\[[^\]]+\])", s)
        for p_ in parts:
            if p_.strip():
                out.append(p_.strip())
    if not out or out[-1] != "[End]":
        out = [o for o in out if o != "[Fade Out]"] + ["[End]"]
    return "\n".join(out) + "\n"


VOWEL_RUN = re.compile(r"([aeiouAEIOU])\1+")


def perform(sections, turns, melisma, pause_before):
    """Applies the vocal tricks: ALL-CAPS on the section's turning words, +4 vowels on one sustained word, '...' before a
    held word, one phrase per line."""
    out = []
    for name, lines in sections:
        out.append("[%s]" % name)
        for ln in lines:
            for ph in [x.strip() for x in ln.split(",") if x.strip()]:
                words = ph.split()
                for i, w in enumerate(words):
                    if w.lower() in turns.get(name, []):
                        words[i] = w.upper()
                    if w.lower() == melisma:
                        v = max((m for m in re.finditer(r"[aeiou]", w)), key=lambda m: m.start())
                        words[i] = w[:v.end()] + v.group(0) * 4 + w[v.end():]
                    if w.lower() == pause_before and i:
                        words[i] = "... " + words[i]
                out.append(" ".join(words))
    return "\n".join(out) + "\n"


def lint_perf(text):
    errs, sec, caps = [], None, {}
    for ln in text.splitlines():
        if ln.startswith("["):
            sec = ln; caps[sec] = 0; continue
        caps[sec] = caps.get(sec, 0) + sum(1 for w in re.findall(r"[A-Za-z']+", ln) if len(w) > 1 and w.isupper())
        for m in VOWEL_RUN.finditer(ln):
            extra = len(m.group(0)) - 1
            if extra >= 20:
                errs.append("melisma of %d vowels glitches" % extra)
            elif not 3 <= extra <= 5 and extra > 1:
                errs.append("melisma +%d (want 3-5)" % extra)
        if "," in ln:
            errs.append("two phrases on one line")
    for s, c in caps.items():
        if not 1 <= c <= 2:
            errs.append("%s has %d caps words (want 1-2)" % (s, c))
    if "..." not in text:
        errs.append("no '...' breath pause")
    return errs, caps


GENDER = re.compile(r"\b(fe)?male\b|\bwoman\b|\bman\b|\bgirl\b|\bboy\b", re.I)


def anti_patterns(style, lyrics, artists, voice_model=False, want_instrumental=False):
    found = []
    for a in artists:
        if a.lower() in style.lower():
            found.append("artist name %s" % a)
    if re.search(r"\(x\d\)", lyrics):
        found.append("(xN) repeat marker")
    if re.search(r"\bno drums\b", style, re.I) and not re.search(r"\bonly\b", style, re.I):
        found.append("bare 'no drums'")
    gens = [t for t in split_tags(style) if tag_cat(t) == "genre" and "with" not in t]
    if len(gens) >= 3:
        found.append("%d equal genres" % len(gens))
    if want_instrumental and not ("[Melodic Instrumental]" in lyrics and "instrumental, no vocals" in style):
        found.append("vocals not ruled out")
    if voice_model and GENDER.search(style):
        found.append("gender descriptor with a voice model")
    return found


def fix_prompt(style, lyrics, artists, voice_model=False, want_instrumental=False):
    tags = []
    for t in split_tags(style):
        for a, desc in artists.items():
            if a.lower() in t.lower():
                t = desc
        if voice_model:
            t = GENDER.sub("", t).strip()
        if t:
            tags.append(t)
    gens = [t for t in tags if tag_cat(t) == "genre"]
    if len(gens) >= 3:
        tags = ["%s with %s textures" % (gens[0], gens[1])] + [t for t in tags if t not in gens]
    if any(re.search(r"\bno drums\b", t, re.I) for t in tags) and not any("only" in t for t in tags):
        tags = [("piano only, no drums" if re.search(r"\bno drums\b", t, re.I) else t) for t in tags]
    if want_instrumental:
        tags.append("instrumental, no vocals")
    out_l = []
    for ln in lyrics.splitlines():
        m = re.match(r"^(.*?)\s*\(x(\d)\)\s*$", ln)
        out_l += [m.group(1)] * int(m.group(2)) if m else [ln]
    lyr = "\n".join(out_l)
    if want_instrumental and "[Melodic Instrumental]" not in lyr:
        lyr = "[Melodic Instrumental]\n" + lyr
    return ", ".join(tags), lyr


AR = re.compile(r"[ء-ي]")


LAT = re.compile(r"[A-Za-z]")


RAI = {"bpm": (90, 130), "instruments": ["synth", "accordion", "darbouka", "bass"]}


def lint_arabic_pkg(pkg, artists=()):
    errs = []
    a, l = len(AR.findall(pkg["lyrics"])), len(LAT.findall(re.sub(r"\[[^\]]*\]", "", pkg["lyrics"])))
    if a / max(1, a + l) < 0.9:
        errs.append("lyrics not written in Arabic script (%.0f%%)" % (100 * a / max(1, a + l)))
    if "arabic" not in pkg["style"].lower():
        errs.append("style does not name the language")
    m = re.search(r"(\d{2,3})\s*bpm", pkg["style"], re.I)
    bpm = int(m.group(1)) if m else None
    if "rai" in pkg["style"].lower():
        if bpm is None or not RAI["bpm"][0] <= bpm <= RAI["bpm"][1]:
            errs.append("Rai at %s BPM (want 90-130)" % bpm)
        if sum(i in pkg["style"].lower() for i in RAI["instruments"]) < 3:
            errs.append("Rai palette thin")
    if any(x.lower() in pkg["style"].lower() for x in artists):
        errs.append("artist name in style")
    return errs


GENRE_TPL = {
    "pop": (100, 130, "catchy modern pop, bright, synth and guitar, polished female vocal"), "rock": (110, 150, "driving alt rock, gritty guitars, live drums, belted vocal"),
    "hip-hop": (80, 100, "boom-bap hip-hop, dusty samples, punchy drums, rapped vocal"), "trap": (130, 170, "dark trap, 808s, rolling hi-hats, auto-tuned vocal"),
    "edm": (120, 130, "festival edm, supersaw synths, sidechain pump, big drop"), "jazz": (80, 160, "smoky jazz trio, upright bass, brushed drums, piano"),
    "classical": (60, 140, "orchestral classical, strings, woodwinds, no vocals"), "folk": (80, 120, "acoustic folk, fingerpicked guitar, warm close vocal"),
    "metal": (100, 200, "heavy metal, down-tuned guitars, double kick, screamed vocal"), "ambient": (50, 80, "ambient, evolving pads, field recordings, no percussion"),
    "lofi": (70, 90, "lofi hip-hop, vinyl crackle, mellow keys, jazzy chords"), "rnb": (60, 100, "smooth r&b, silky vocal, warm keys, finger snaps")}


def genre_template(g, bpm=None, **knobs):
    lo, hi, st = GENRE_TPL[g]
    b = bpm if bpm is not None else (lo + hi) // 2
    shell = ["[Melodic Instrumental]"] if g in ("ambient", "classical") else ["[Intro]", "[Verse 1]", "[Chorus]", "[Verse 2]", "[Chorus]", "[Outro]", "[End]"]
    return {"genre": g, "bpm": b, "style": "%s, %d BPM%s" % (st, b, "".join(", " + v for v in knobs.values())), "shell": shell, "knobs": sorted(knobs)}


def lint_template(t):
    lo, hi, _ = GENRE_TPL[t["genre"]]
    errs = []
    if not lo <= t["bpm"] <= hi:
        errs.append("%s at %d BPM outside %d-%d" % (t["genre"], t["bpm"], lo, hi))
    if "%d BPM" % t["bpm"] not in t["style"]:
        errs.append("BPM not in style")
    if t["genre"] == "ambient" and re.search(r"\bdrums|percussion\b(?<!no percussion)", t["style"].replace("no percussion", "")):
        errs.append("ambient bed carries percussion")
    if lint_tags("\n".join(t["shell"]), hard_stop=False):
        errs.append("shell has bad tags")
    return errs


TASHKEEL = re.compile(r"[ً-ْ]")


SUNO_ORDER = ["genre", "bpm", "mood", "instrument", "vocal", "era"]


SONG_SECTIONS = ["Intro", "Verse 1", "Pre-Chorus", "Chorus", "Verse 2", "Bridge", "Final Chorus", "Outro"]


def bare(w):
    w = TASHKEEL.sub("", w)
    return w.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا").replace("ة", "ه").replace("ى", "ي")


def rhyme_scheme(lines):
    keys, out = {}, []
    for ln in lines:
        w = bare(ln.split()[-1])
        k = w[-2:] if len(w) >= 2 else w
        if k not in keys:
            keys[k] = chr(ord("A") + len(keys))
        out.append(keys[k])
    return "".join(out)


def lyric_blocks(lyrics):
    blocks, cur = [], None
    for ln in lyrics.splitlines():
        m = re.match(r"^\[(.+)\]$", ln.strip())
        if m:
            cur = [m.group(1), []]; blocks.append(cur)
        elif ln.strip() and cur:
            cur[1].append(ln.strip())
    return blocks


def suno_order_cat(tag):
    if re.search(r"\b(19|20)\d0s\b|\b\d0s\b|era\b", tag, re.I):
        return "era"
    c = tag_cat(tag)
    return {"production": "era"}.get(c, c)


def lint_song_pkg(pkg, risky=()):
    errs = []
    if len(pkg["style"]) > 200:
        errs.append("style %d chars (> 200)" % len(pkg["style"]))
    cats = [suno_order_cat(t) for t in split_tags(pkg["style"])]
    idx = [SUNO_ORDER.index(c) if c in SUNO_ORDER else 99 for c in cats]
    if idx != sorted(idx) or 99 in idx:
        errs.append("style tags not in [Genre][BPM][Mood][Instruments][Vocal][Era] order: %s" % cats)
    names = [b[0] for b in lyric_blocks(pkg["lyrics"])]
    if names != SONG_SECTIONS:
        errs.append("sections %s" % names)
    hook = pkg["hook"]
    n = sum(ln.strip() == hook for ln in pkg["lyrics"].splitlines())
    if not 2 <= n <= 4:
        errs.append("hook appears %d times (want 2-4)" % n)
    for w in risky:
        hits = [x for x in re.findall(r"[ء-ْ]+", pkg["lyrics"]) if bare(x) == bare(w)]
        if hits and not all(TASHKEEL.search(x) for x in hits):
            errs.append("risky word %s without tashkeel" % w)
    for k in ("title", "exclude", "alt_genre", "reel_hook"):
        if not pkg.get(k):
            errs.append("missing %s" % k)
    return errs


AR_PALETTE = ["oud", "qanun", "ney", "violin section", "darbuka", "tabla", "riq", "daf", "bendir", "mizmar", "rababa", "buzuq", "kawala",
              "tasfiq", "synth pads"]


OTHER_INSTR = ["sitar", "bagpipes", "banjo", "koto", "didgeridoo", "piano", "guitar"]


def palette_count(prompt):
    low = prompt.lower()
    inside = [i for i in AR_PALETTE if i in low]
    outside = [i for i in OTHER_INSTR if re.search(r"\b%s\b" % i, low)]
    return inside, outside


BRIEF10 = ["keep_sentence", "language_dialect", "narrator_addressee", "arc", "genre", "tempo_energy", "vocal", "duration_sections",
           "must_forbidden", "use"]


CONCRETE = ["باب", "شباك", "فنجان", "قهوة", "مطر", "رمل", "شارع", "قمر", "بحر", "نخل", "سيارة", "مفتاح", "ريح", "شمعة", "رسالة", "تلفون"]


TURN = re.compile(r"\b(بس|لكن|بعدين|ولو)\b")


def words_ar(ln):
    return re.findall(r"[ء-ْ]+", ln)


def lint_hook_first(brief, title, lyrics):
    errs = ["brief missing %s" % k for k in BRIEF10 if not brief.get(k)]
    B = lyric_blocks(lyrics)
    ch = [b for b in B if "Chorus" in b[0]]
    if len(words_ar(title)) > 6:
        errs.append("title longer than 6 words")
    if not ch or not all(any(bare(title) in bare(l) for l in c[1]) for c in ch):
        errs.append("title not in every chorus")
    if ch and not any(sum(bare(l) == bare(x) for x in c[1]) >= 2 for c in ch for l in c[1]):
        errs.append("no hook device (no repeated hook line)")
    if len(ch) >= 2 and not all(len(b[1]) > len(a[1]) or b[1] != a[1] for a, b in zip(ch, ch[1:])):
        errs.append("chorus repeats do not escalate")
    long = [l for b in B for l in b[1] if len(words_ar(l)) > 8]
    if long:
        errs.append("%d line(s) too long for one breath" % len(long))
    for b in B:
        if "Verse" in b[0] and sum(any(c in bare(l) for c in CONCRETE) for l in b[1]) < 2:
            errs.append("%s is not concrete" % b[0])
    br = [b for b in B if b[0] == "Bridge"]
    if not br or not any(TURN.search(l) for l in br[0][1]):
        errs.append("no bridge turn")
    return errs


DIALECT = {"egyptian": ["مش", "ازاي", "دلوقتي", "عايز", "عاوز", "ده", "دي"], "gulf": ["شلون", "الحين", "ابي", "ابغى", "وش", "مو", "هذي"]}


ELONG = re.compile(r"([ء-ي])\1{2,}")


AMBIG = {"عِشق", "حُب", "مَلك"}


def syllables(ln):
    return math.ceil(len(re.sub(r"[^ء-ي]", "", re.sub(r"\([^)]*\)", "", ln))) / 2)


def lint_dialect(lines, max_syl=12):
    errs = []
    seen = {d: [w for ln in lines for w in words_ar(ln) if bare(w) in [bare(m) for m in ms]] for d, ms in DIALECT.items()}
    if sum(1 for v in seen.values() if v) > 1:
        errs.append("mixed dialects %s" % {k: v for k, v in seen.items() if v})
    for ln in (re.sub(r"\([^)]*\)", "", x) for x in lines):
        if ELONG.search(ln):
            errs.append("typographic elongation in %r" % ln)
        if syllables(ln) > max_syl:
            errs.append("line too long at tempo (%d syllables)" % syllables(ln))
        for w in words_ar(ln):
            if TASHKEEL.search(w) and w not in AMBIG:
                errs.append("tashkeel on unambiguous word %s" % w)
    return errs


def fix_dialect(lines, dialect, max_syl=12):
    swap = {"egyptian": {"شلون": "ازاي", "الحين": "دلوقتي", "مو": "مش", "ابي": "عايز"},
            "gulf": {"ازاي": "شلون", "دلوقتي": "الحين", "مش": "مو", "عايز": "ابي"}}[dialect]
    out = []
    for ln in lines:
        stretched = bool(ELONG.search(ln))
        ln = ELONG.sub(lambda m: m.group(1), ln)
        ws = [swap.get(bare(w), w) for w in ln.split()]
        ws = [w if not TASHKEEL.search(w) or w in AMBIG else TASHKEEL.sub("", w) for w in ws]
        chunks, todo = [], [ws]
        while todo:
            c = todo.pop(0)
            if syllables(" ".join(c)) > max_syl and len(c) > 1:
                k = len(c) // 2
                todo[:0] = [c[:k], c[k:]]
            else:
                chunks.append(" ".join(c))
        if stretched:
            chunks[0] += " (مدّ على آخر كلمة)"
        out += chunks
    return out


X08_ORDER = ["genre", "tempo", "vocal", "instrument", "production", "atmosphere", "arrangement"]


def x08_cat(tag):
    t = tag.lower()
    if re.search(r"\bverse\b|\bchorus\b|\blift\b|\bbuilds?\b|\bdrops?\b", t):
        return "arrangement"
    if re.search(r"\bbpm\b|tempo|\bslow\b|\bupbeat\b|energy", t):
        return "tempo"
    if re.search(r"\batmosphere\b|nocturnal|misty|dusky|smoky room|night air", t):
        return "atmosphere"
    if re.search(r"\b(19|20)\d0s\b|\bmix\b|production|analog|tape", t):
        return "production"
    return {"bpm": "tempo", "mood": "atmosphere"}.get(tag_cat(t), tag_cat(t))


def lint_style_exclude(style, exclude, history=()):
    errs = []
    cats = [x08_cat(t) for t in split_tags(style)]
    idx = [X08_ORDER.index(c) if c in X08_ORDER else 99 for c in cats]
    if idx != sorted(idx) or 99 in idx:
        errs.append("style not in the 7-step order: %s" % cats)
    st = {t.lower() for t in split_tags(style)}
    for e in split_tags(exclude):
        if e.lower() in st or any(e.lower() in s for s in st):
            errs.append("'%s' is in both Style and Exclude" % e)
        if re.search(r"lyric|rhyme|words|line", e, re.I) or tag_cat(e) == "other" and x08_cat(e) == "other":
            errs.append("'%s' is not a true negative (genre/instrument/vocal/production)" % e)
    for a, b in zip(history, history[1:]):
        n = sum(a.get(k) != b.get(k) for k in set(a) | set(b))
        if n != 1:
            errs.append("iteration changed %d controls (want 1)" % n)
    return errs, cats


FIX_MAP = {"weak line": ("local lyric edit", "lyrics"), "weak chorus": ("Replace Section", "section"),
           "wrong ending": ("Extend or edit the outro", "ending"), "prompt slightly off": ("Reuse Prompt or edit Style", "style"),
           "broad style mismatch": ("fix Style/Exclude first", "style"), "mispronunciation": ("simplify spelling, add diacritics or rephrase", "lyrics")}


def iteration_plan(defects):
    """One round per defect, style-level problems first (a lyric fix is wasted under the wrong style), one variable a round."""
    order = sorted(defects, key=lambda d: 0 if FIX_MAP[d][1] == "style" else 1)
    return [{"round": i + 1, "defect": d, "fix": FIX_MAP[d][0], "variable": FIX_MAP[d][1]} for i, d in enumerate(order)]


def lint_iteration(plan):
    errs = []
    for r in plan:
        vs = r["variable"] if isinstance(r["variable"], list) else [r["variable"]]
        if len(vs) != 1:
            errs.append("round %d changes %d variables" % (r["round"], len(vs)))
        if "regenerate" in r["fix"].lower():
            errs.append("round %d regenerates everything" % r["round"])
        if r.get("defect") in FIX_MAP and r["fix"] != FIX_MAP[r["defect"]][0]:
            errs.append("round %d uses the wrong tool for %s" % (r["round"], r["defect"]))
    vs = [r["variable"] for r in plan if isinstance(r["variable"], str)]
    if "style" in vs and any(v != "style" for v in vs[:vs.index("style")]):
        errs.append("style fixed after lyric/section edits")
    return errs


def four_blocks(title, lyrics, style, exclude):
    return "\n\n".join("```\n%s\n```" % b for b in (title, lyrics, style, exclude))


def rubric(handoff, required=(), forbidden=(), dialect_lines=None):
    blocks = re.findall(r"```\n(.*?)\n```", handoff, re.S)
    res = {}
    res["copy_ready_blocks"] = len(blocks) == 4 and not re.search(r"TODO|<[^>]+>|\?\?\?", handoff)
    title, lyrics, style, exclude = (blocks + ["", "", "", ""])[:4]
    B = lyric_blocks(lyrics)
    ch = [b[1] for b in B if "Chorus" in b[0]]
    vs = [b[1] for b in B if "Verse" in b[0]]
    res["hook_identifiable"] = bool(ch) and any(sum(l == x for x in c) >= 2 for c in ch for l in c)
    res["chorus_lifts"] = bool(ch and vs) and bool(np.mean([len(words_ar(l)) for c in ch for l in c]) < np.mean([len(words_ar(l)) for v in vs for l in v]))
    res["singable"] = all(len(words_ar(l)) <= 8 for b in B for l in b[1])
    res["dialect_stable"] = lint_dialect([l for b in B for l in b[1]]) == []
    res["imagery_specific"] = sum(any(c in bare(l) for c in CONCRETE) for v in vs for l in v) >= 2
    ends = [l for v in vs for l in v]
    sch = rhyme_scheme(ends) if ends else ""
    res["rhyme_natural"] = bool(sch) and len(set(sch)) < len(sch) and len({bare(l.split()[-1]) for l in ends}) == len(ends)
    res["arc_changes"] = any(b[0] == "Bridge" and any(TURN.search(l) for l in b[1]) for b in B)
    res["style_lyrics_agree"] = ("arabic" in style.lower() or "khaleeji" in style.lower()) == bool(AR.search(lyrics))
    res["exclude_true_negatives"] = bool(exclude) and not [e for e in lint_style_exclude(style, exclude)[0] if "Exclude" in e or "true negative" in e]
    res["required_forbidden"] = all(r in lyrics for r in required) and not any(f in lyrics for f in forbidden)
    return res, all(res.values())
