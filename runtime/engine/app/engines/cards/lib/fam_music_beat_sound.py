"""Helpers of runners/fam_music_beat_sound.py used by data cards, copied verbatim (the extractor binds a card to them only when
their AST hash with every dependency equals the original's)."""
from __future__ import annotations

from pathlib import Path
from .core import check
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


def tone(f, d, amp=0.5, sr=SR):
    return amp * np.sin(2 * np.pi * f * tt(d, sr))


def save(wd, name, x, sr=SR):
    return fx.write_wav(Path(wd) / name, x, sr)


def load(p):
    x, sr = fx.read_wav(p)
    return x.mean(1), sr


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


def peak_hz(x, sr=SR):
    w = np.hanning(len(x))
    X = np.abs(np.fft.rfft(x * w))
    f = np.fft.rfftfreq(len(x), 1 / sr)
    X[f < 15] = 0
    return float(f[int(np.argmax(X))])


def band_db(x, sr, lo, hi):
    X = np.abs(np.fft.rfft(x * np.hanning(len(x)))) ** 2
    f = np.fft.rfftfreq(len(x), 1 / sr)
    return 10 * math.log10(float(X[(f >= lo) & (f < hi)].sum()) + 1e-20)


def envelope(x, sr, ms=5.0):
    n = max(1, int(sr * ms / 1000))
    return np.sqrt(np.convolve(np.square(x), np.ones(n) / n, mode="same"))


def onsets(x, sr, rel=0.3, gap=0.06, ms=5.0):
    """Independent measurement: rising crossings of rel·max of a short RMS envelope, at least gap apart."""
    e = envelope(x, sr, ms)
    thr = rel * e.max()
    up = np.flatnonzero((e[1:] >= thr) & (e[:-1] < thr)) + 1
    out, last = [], -1e9
    for i in up:
        if i / sr - last >= gap:
            out.append(i / sr)
            last = i / sr
    return out


def clicks(bpm, secs, sr=SR, f=1000.0, dur=0.03, amp=0.8, offset=0.0, accent=4):
    x = np.zeros(int(secs * sr))
    times, k = [], 0
    t0 = tt(dur, sr)
    while offset + k * 60 / bpm < secs - dur:
        t = offset + k * 60 / bpm
        i = int(round(t * sr))
        a = amp if k % accent == 0 else amp * 0.6
        x[i:i + len(t0)] += a * np.sin(2 * np.pi * f * t0) * np.exp(-t0 * 120)
        times.append(round(t, 4))
        k += 1
    return x, times


def kick(sr=SR, amp=0.9):
    t = tt(0.25, sr)
    return amp * np.sin(2 * np.pi * np.cumsum(46 + 110 * np.exp(-t / 0.032)) / sr) * np.exp(-t / 0.08)


def drum_loop(bpm, secs, sr=SR, seed=1):
    """A kick (with a 2 ms click transient) on every beat: a rhythmic fixture at a known tempo."""
    rng = np.random.default_rng(seed)
    x = np.zeros(int(secs * sr))
    k, times = kick(sr), []
    nc = int(0.01 * sr)
    k = k.copy()
    k[:nc] += 0.3 * rng.standard_normal(nc) * np.exp(-np.arange(nc) / sr / 0.002)
    b = 0
    while b * 60 / bpm < secs - 0.3:
        i = int(b * 60 / bpm * sr)
        x[i:i + len(k)] += k[: len(x) - i]
        times.append(round(b * 60 / bpm, 4))
        b += 1
    return x, times


def speechlike(secs, spans, sr=SR, f0=140.0, amp=0.35, seed=3):
    """Voiced harmonic bursts (f0 + 10 partials, ~4 Hz syllable envelope) inside the given spans; silence elsewhere."""
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


def music_bed(secs, sr=SR, amp=0.3):
    t = tt(secs, sr)
    x = sum(np.sin(2 * np.pi * f * t) for f in (220, 277.2, 329.6, 440))
    return amp * x / 4 * (0.85 + 0.15 * np.sin(2 * np.pi * 0.5 * t))


def ebur(p):
    """ffmpeg ebur128 (BS.1770) measurement: integrated LUFS, LRA, true peak dBTP."""
    err = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(p), "-af", "ebur128=peak=true", "-f", "null", "-"],
                         capture_output=True, text=True, timeout=60, stdin=subprocess.DEVNULL).stderr
    summ = err[err.rfind("Summary:"):]
    g = lambda pat: float(re.search(pat, summ, re.S).group(1))
    return {"I": g(r"I:\s+(-?[\d.]+|-inf) LUFS"), "LRA": g(r"LRA:\s+(-?[\d.]+) LU"),
            "TP": g(r"True peak:\s+Peak:\s+(-?[\d.]+|-inf) dBFS")}


def loudnorm_measure(p, I, TP, LRA):
    err = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(p), "-af",
                          "loudnorm=I=%s:TP=%s:LRA=%s:print_format=json" % (I, TP, LRA), "-f", "null", "-"],
                         capture_output=True, text=True, timeout=60, stdin=subprocess.DEVNULL).stderr
    return json.loads(err[err.rfind("{"):err.rfind("}") + 1])


def loudnorm2(src, out, I=-14, TP=-1.5, LRA=11, post="", codec=("-c:a", "pcm_s16le"), sr=48000):
    m = loudnorm_measure(src, I, TP, LRA)
    af = ("loudnorm=I=%s:TP=%s:LRA=%s:measured_I=%s:measured_TP=%s:measured_LRA=%s:measured_thresh=%s:offset=%s:"
          "linear=true:print_format=summary,aresample=%d" % (I, TP, LRA, m["input_i"], m["input_tp"], m["input_lra"],
                                                            m["input_thresh"], m["target_offset"], sr))
    if post:
        af += "," + post
    ff("-i", src, "-af", af, *codec, out)
    return m


def song_fixture(wd, secs=4.0, level=-30.0, name="mix_in.wav", sr=SR):
    """A music-like mix (chord + kicks) scaled to a known RMS level in dBFS."""
    x = music_bed(secs, sr) + 0.6 * drum_loop(120, secs, sr)[0]
    x *= 10 ** ((level - dbfs(x)) / 20)
    return save(wd, name, x, sr), x


def sidechain(music, voice, out, thr=0.02, ratio=12, attack=20, release=300, makeup=1, extra=""):
    ff("-i", music, "-i", voice, "-filter_complex",
       "[0:a][1:a]sidechaincompress=threshold=%s:ratio=%s:attack=%s:release=%s:makeup=%s%s[d]"
       % (thr, ratio, attack, release, makeup, extra), "-map", "[d]", "-c:a", "pcm_s16le", out)
    return Path(out)


def write_video(path, frame_fn, n, fps=30, size=(160, 90), audio=None, extra=()):
    w, h = size
    buf = b"".join(np.ascontiguousarray(np.clip(frame_fn(i), 0, 255).astype(np.uint8)).tobytes() for i in range(n))
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "%dx%d" % (w, h),
           "-r", str(fps), "-i", "-"]
    if audio:
        cmd += ["-i", str(audio), "-map", "0:v", "-map", "1:a", *fx.fit_audio(n / fps), "-c:a", "aac", "-b:a", "192k",
                "-frames:v", str(n)]
    cmd += ["-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p", *extra, str(path)]
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


def cut_video(path, cuts, secs, fps=30, size=(96, 54), audio=None):
    """A shot plan rendered: each shot a different colour field with a moving bar, hard cuts at the given times."""
    bounds = [0.0] + list(cuts) + [secs + 1]

    def frame(i):
        t = i / fps
        k = max(j for j in range(len(bounds) - 1) if bounds[j] <= t + 1e-9)
        a = solid(size, PAL[k % len(PAL)])
        x = int((t * 40) % size[0])
        a[:, x:x + 3] = 255
        return a
    return write_video(path, frame, int(round(secs * fps)), fps, size, audio)


def cut_frames(path, size=(48, 27), thr=40.0):
    fr = fx.frames(path, size)
    d = np.abs(np.diff(fr, axis=0)).mean(axis=(1, 2, 3))
    return [int(i + 1) for i in np.flatnonzero(d > thr)], fr


def rises_at(x, sr, times, pre=0.05, post=0.04):
    """dB rise of the short-term level just after each time over just before it: a sound starts there."""
    out = []
    for t in times:
        a = rms(x[max(0, int((t - pre) * sr)):max(1, int((t - 0.004) * sr))])
        b = rms(x[int((t + 0.004) * sr):int((t + post) * sr)])
        out.append(20 * math.log10((b + 1e-9) / (a + 1e-9)))
    return out


def frame_err(found, expected):
    """Worst distance in frames between expected cut frames and the nearest detected cut."""
    if not expected:
        return 0
    if not found:
        return 999
    return max(min(abs(f - e) for f in found) for e in expected)


def grid(bpm, n, offset=0.0):
    return [round(offset + k * 60.0 / bpm, 6) for k in range(n)]


def jdump(p, obj):
    Path(p).write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
    return Path(p)


def _loud(wd, I, TP, LRA, level=-30.0, tol=0.5, tp_lim=None, codec=("-c:a", "pcm_s16le"), ext="wav", name="norm", post=""):
    src, _ = song_fixture(wd, 4.0, level)
    out = Path(wd) / ("%s.%s" % (name, ext))
    loudnorm2(src, out, I, TP, LRA, post=post, codec=codec)
    a, b = ebur(src), ebur(out)
    tp_lim = TP + 0.5 if tp_lim is None else tp_lim
    return [check("%s integrated loudness on target" % name, abs(b["I"] - I) <= tol, b["I"], I),
            check("%s true peak under ceiling" % name, b["TP"] <= tp_lim, b["TP"], "<= %s" % tp_lim),
            check("negative control: input is not on target", abs(a["I"] - I) > tol, a["I"], "!= %s" % I)], [out]


BED_F = (233.0, 311.0, 466.0)


def bed(secs, amp=0.3, sr=SR, freqs=BED_F):
    t = tt(secs, sr)
    return amp * sum(np.sin(2 * np.pi * f * t) for f in freqs) / len(freqs)


def narrow_db(x, sr, f, a, b, bw=4.0):
    """Level of one partial inside [a, b] s: power within ±bw Hz of f (Hann window), so the bed can be read under a voice."""
    s = x[int(a * sr):int(b * sr)]
    w = np.hanning(len(s))
    X = np.abs(np.fft.rfft(s * w)) ** 2
    fr = np.fft.rfftfreq(len(s), 1 / sr)
    return 10 * math.log10(float(X[(fr > f - bw) & (fr < f + bw)].sum()) / (np.sum(w ** 2) * len(s)) + 1e-20)


def bed_drop(x, sr, span, pre=(0.2, 0.9), margin=0.35, f=BED_F[0]):
    a, b = span
    return narrow_db(x, sr, f, a + margin, b - 0.1) - narrow_db(x, sr, f, *pre)


def flat(x, a, b, c=0.2, e=0.9, sr=SR):
    """Partial level in [a,b] minus in [c,e] on an unprocessed signal (the negative control value)."""
    return narrow_db(x, sr, BED_F[0], a, b) - narrow_db(x, sr, BED_F[0], c, e)


def voice_bed(wd, secs=4.0, span=(1.0, 2.6), amp_v=0.35):
    v = speechlike(secs, [span], f0=170, amp=amp_v)
    m = bed(secs)
    return save(wd, "voice.wav", v), save(wd, "music.wav", m), v, m


def _sc_card(wd, span=(1.0, 2.6), thr=0.02, ratio=12, attack=20, release=300, makeup=1, lo=10, hi=40, name="ducked"):
    vp, mp, v, m = voice_bed(wd, span=span)
    d = sidechain(mp, vp, Path(wd) / (name + ".wav"), thr, ratio, attack, release, makeup)
    mix = Path(wd) / (name + "_mix.wav")
    ff("-i", d, "-i", vp, "-filter_complex", "[0:a][1:a]amix=inputs=2:normalize=0[m]", "-map", "[m]", mix)
    y, sr = load_any(d)
    drop = bed_drop(y, sr, span)
    out_ch = narrow_db(y, sr, BED_F[0], 3.2, 3.9) - narrow_db(y, sr, BED_F[0], 0.2, 0.9)
    neg = bed_drop(m, SR, span)
    return drop, out_ch, neg, [d, mix]


def _duck_checks(drop, out_ch, neg, lo, hi):
    return [check("music drops %s..%s dB under the voice" % (lo, hi), -hi <= drop <= -lo, drop, "-%s..-%s" % (lo, hi)),
            check("music back to level after the voice (±1.5 dB)", abs(out_ch) <= 1.5, out_ch, 0),
            check("negative control: the unprocessed bed does not dip", abs(neg) < 0.5, neg, 0)]


def beat_err(found, truth):
    return max(min(abs(f - t) for f in found) for t in truth) if found else 9.0


def loops(wd):
    a, ta = drum_loop(120, 6.0)
    b, tb = drum_loop(96, 6.0)
    return save(wd, "loop120.wav", a), ta, save(wd, "loop96.wav", b), tb


def _tracker_checks(r120, r96, ta, name):
    return [check("%s: 120 BPM loop reads 120 ±2" % name, abs(r120["bpm"] - 120) <= 2, r120["bpm"], 120),
            check("%s: beats within 60 ms of the true kicks (analysis-window bias)" % name, beat_err(r120["beats"], ta[1:-1]) <= 0.06, beat_err(r120["beats"], ta[1:-1]), "<= 0.06"),
            check("%s: 96 BPM loop reads 96 ±2" % name, abs(r96["bpm"] - 96) <= 2, r96["bpm"], 96),
            check("negative control: the 120 answer does not fit the 96 BPM track", abs(r120["bpm"] - 96) > 10, r120["bpm"], "!= 96")]


def kick_band_detector(x, sr):
    """scripts/beat_detector.py method: Butterworth order-4 band-pass 50-250 Hz (SOS), 10 ms RMS envelope, half-wave
    onset difference, autocorrelation over 60-180 BPM, find_peaks height .15 distance .25 s, grid every 60/BPM."""
    from scipy.signal import butter, find_peaks, sosfiltfilt, resample_poly
    y = resample_poly(x, 22050, sr)
    sr2 = 22050
    y = sosfiltfilt(butter(4, [50, 250], "band", fs=sr2, output="sos"), y)
    hop = int(0.01 * sr2)
    env = np.array([np.sqrt(np.mean(y[i:i + hop] ** 2)) for i in range(0, len(y) - hop, hop)])
    on = np.maximum(0, np.diff(env, prepend=env[0]))
    on /= on.max() + 1e-9
    ac = np.correlate(on, on, "full")[len(on) - 1:]
    lags = np.arange(int(100 * 60 / 180), int(100 * 60 / 60) + 1)
    lag = lags[int(np.argmax(ac[lags]))]
    bpm = 6000.0 / lag
    pk, _ = find_peaks(on, height=0.15, distance=25)
    onsets_t = (pk / 100.0).tolist()
    first = onsets_t[0] if onsets_t else 0.0
    grid_b = [round(first + k * 60 / bpm, 3) for k in range(int((len(y) / sr2 - first) / (60 / bpm)) + 1)]
    return {"bpm": round(bpm, 2), "beat_interval": round(60 / bpm, 4), "first_downbeat": first, "grid_beats": grid_b, "onsets": onsets_t}


def _click_music(wd, bpm, secs, name="music.wav", offset=0.0):
    x, times = clicks(bpm, secs, offset=offset)
    return save(wd, name, x), times


def _cut_card(wd, cut_times, secs, bpm=None, fps=30, lead=0, beat_times=None, tol=1, label="cuts"):
    """Render the cut plan over a click track, find the cuts in the picture, compare with the plan and with the beats."""
    audio = None
    if bpm:
        audio, beat_times = _click_music(wd, bpm, secs)
    planned = [int(round(t * fps)) - lead for t in cut_times]
    v = cut_video(Path(wd) / (label + ".mp4"), [f / fps for f in planned], secs, fps, audio=audio)
    found, _ = cut_frames(v)
    plain = cut_video(Path(wd) / "uncut.mp4", [], secs, fps)
    f0, _ = cut_frames(plain)
    checks = [check("rendered cuts at the planned frames", frame_err(found, planned) == 0 and len(found) == len(planned), found, planned)]
    if beat_times is not None and audio is not None:
        on = onsets(load_any(v)[0], SR, 0.3, 0.1)
        on_f = [o * fps for o in on]
        worst = max(min(abs(f + lead - o) for o in on_f) for f in found) if found and on_f else 99
        checks.append(check("each cut within %d frame(s) of a beat heard in the file" % tol, worst <= tol, worst, "<= %d" % tol))
    checks.append(check("negative control: the uncut clip has no cuts", frame_err(f0, planned) > tol, len(f0), "> 0 needed"))
    jdump(Path(wd) / (label + ".edl.json"), {"fps": fps, "cuts_s": [round(f / fps, 4) for f in planned], "bpm": bpm})
    return checks, [v, Path(wd) / (label + ".edl.json")]


def _every(bpm, n_beats, secs, offset=0.0, start=1):
    step = n_beats * 60.0 / bpm
    out, k = [], start
    while offset + k * step < secs - 0.15:
        out.append(round(offset + k * step, 6))
        k += 1
    return out, step


def _bar_card(wd, bpm, bars, fps=30, size=(160, 90), label_fn=None):
    """HUD counter rendered per frame from t: bar = floor(t·BPM/240)+1, beat = floor(t·BPM/60)%4+1; the HUD region must change
    exactly on the beat frames."""
    from PIL import Image, ImageDraw
    secs = bars * 240.0 / bpm
    n = int(round(secs * fps))
    labels = []

    def frame(i):
        t = i / fps
        bar = int(t * bpm / 240) + 1
        beat = int(t * bpm / 60) % 4 + 1
        lab = label_fn(bar, beat, t) if label_fn else "BAR %02d . BEAT %d" % (bar, beat)
        labels.append(lab)
        im = Image.new("RGB", size, (10, 10, 14))
        d = ImageDraw.Draw(im)
        d.text((6, 6), lab, fill=(255, 255, 255))
        for k in range(4):
            d.rectangle([6 + k * 12, 30, 14 + k * 12, 38], fill=(230, 60, 60) if k < beat else (60, 60, 60))
        return np.asarray(im)
    v = write_video(Path(wd) / "hud.mp4", frame, n, fps, size)
    fr = fx.frames(v, size)
    d = np.abs(np.diff(fr[:, :45, :], axis=0)).mean(axis=(1, 2, 3))
    changes = [int(i + 1) for i in np.flatnonzero(d > 1.0)]
    expect = sorted({int(math.ceil(k * 60 / bpm * fps - 1e-9)) for k in range(1, int(secs * bpm / 60)) if k * 60 / bpm * fps < n})
    jdump(Path(wd) / "hud_labels.json", labels[:n])
    return changes, expect, v, labels


def _pulse_video(wd, fn, secs, fps=30, size=(120, 120), name="pulse.mp4"):
    """Render a white disc whose scale is fn(t) and measure its scale back from the frames (area)."""
    w, h = size
    yy, xx = np.mgrid[0:h, 0:w]
    r0 = 0.3 * min(w, h)

    def frame(i):
        s = fn(i / fps)
        m = ((xx - w / 2) ** 2 + (yy - h / 2) ** 2) <= (r0 * s) ** 2
        a = np.zeros((h, w, 3), np.uint8)
        a[m] = 255
        return a
    v = write_video(Path(wd) / name, frame, int(round(secs * fps)), fps, size)
    fr = fx.frames(v, size)
    area = (fr.mean(axis=3) > 128).sum(axis=(1, 2))
    return v, np.sqrt(area / (math.pi * r0 * r0))


def _pulse_checks(scale, beats_t, fps, peak, base=1.0, tol=0.012):
    pk = [scale[int(round(b * fps))] for b in beats_t]
    mid = [scale[int(round(b * fps)) - 3] for b in beats_t[1:]]
    return [check("scale peaks at %.3f on each beat frame" % peak, all(abs(p - peak) <= tol for p in pk), [round(p, 3) for p in pk], peak),
            check("back near %.2f just before the next beat" % base, all(abs(m - base) <= tol + 0.01 for m in mid), [round(m, 3) for m in mid], base),
            check("negative control: off-beat frames are not at the peak", min(abs(m - peak) for m in mid) > tol, [round(m, 3) for m in mid], "!= peak")]


def _ballistic(beat_t, plat, g):
    """Solve vy = (dy + 0.5·g·T²)/T per hop so the arc from platform i-1 lands exactly at beat[i] (g < 0)."""
    hops = []
    for i in range(1, len(beat_t)):
        T = beat_t[i] - beat_t[i - 1]
        (x0, y0), (x1, y1) = plat[i - 1], plat[i]
        hops.append({"t0": beat_t[i - 1], "T": T, "vx": (x1 - x0) / T, "vy": ((y1 - y0) - 0.5 * g * T * T) / T, "p0": (x0, y0)})
    return hops


def _sim(hops, g, t):
    for h in hops:
        if h["t0"] <= t <= h["t0"] + h["T"] + 1e-9:
            u = t - h["t0"]
            return h["p0"][0] + h["vx"] * u, h["p0"][1] + h["vy"] * u + 0.5 * g * u * u
    return None


def _bars_render(wd, values, n_bars, fps=30, size=(200, 80), name="bars.mp4", gap=1):
    """Bars of height ∝ values[frame][k]; heights measured back from the frames."""
    w, h = size
    bw = w // n_bars

    def frame(i):
        a = np.zeros((h, w, 3), np.uint8)
        for k in range(n_bars):
            hh = int(round(values[i][k] * (h - 4)))
            if hh > 0:
                a[h - hh:, k * bw:(k + 1) * bw - gap] = (255, 110, 90)
        return a
    v = write_video(Path(wd) / name, frame, len(values), fps, size)
    fr = fx.frames(v, size)
    meas = np.array([[((fr[i][:, k * bw + bw // 2 - (1 if bw > 2 else 0)].mean(axis=1)) > 100).sum() / (h - 4) for k in range(n_bars)] for i in range(len(values))])
    return v, meas


def _frame_rms(x, sr, fps):
    hop = sr // fps
    return np.array([rms(x[i * hop:(i + 1) * hop]) for i in range(len(x) // hop)])


def _wave_bars_card(wd, n_bars, doc_name):
    t = tt(3.0)
    x = 0.6 * np.sin(2 * np.pi * 220 * t) * (0.15 + 0.85 * np.abs(np.sin(2 * np.pi * 0.7 * t)))
    p = save(wd, "voice.wav", x)
    r = _frame_rms(x, SR, 30)
    r = r / r.max()
    vals = [[float(r[max(0, min(len(r) - 1, i - n_bars // 2 + k))]) for k in range(n_bars)] for i in range(len(r))]
    v, meas = _bars_render(wd, vals, n_bars, size=(n_bars * 3, 60), gap=1)
    mid = meas[:, n_bars // 2]
    c = float(np.corrcoef(mid, r[: len(mid)])[0, 1])
    y = 0.6 * np.sin(2 * np.pi * 220 * t)
    r0 = _frame_rms(y, SR, 30)
    r0 = r0 / r0.max()
    return [check("bar heights follow the per-frame RMS (r > 0.98)", c > 0.98, c, "> 0.98"),
            check("%d bars drawn" % n_bars, meas.shape[1] == n_bars and (meas[10] > 0).sum() >= n_bars - 2, int((meas[10] > 0).sum()), n_bars),
            check("negative control: an unmodulated tone gives bars that do not move (std < 0.01)", float(np.std(r0[1:-1])) < 0.01, float(np.std(r0[1:-1])), "< 0.01"),
            check("the modulated voice gives moving bars (std > 0.1)", float(np.std(mid)) > 0.1, float(np.std(mid)), "> 0.1")], [v]


def band_frames(x, sr, fps=30, nfft=4096, bands=16, lo=40, hi=10000):
    """Per-frame FFT band energies (window 4096 centred on each frame, log-spaced bands, each band normalised over the track)."""
    hop = sr / fps
    n = int(len(x) / hop)
    w = np.hanning(nfft)
    edges = np.geomspace(lo, hi, bands + 1)
    f = np.fft.rfftfreq(nfft, 1 / sr)
    xp = np.pad(x, nfft)
    out = np.zeros((n, bands))
    rr = np.zeros(n)
    for i in range(n):
        c = int(i * hop + hop / 2) + nfft
        seg = xp[c - nfft // 2:c + nfft // 2]
        X = np.abs(np.fft.rfft(seg * w))
        out[i] = [X[(f >= edges[k]) & (f < edges[k + 1])].mean() if np.any((f >= edges[k]) & (f < edges[k + 1])) else 0 for k in range(bands)]
        rr[i] = rms(seg)
    out = out / (out.max(axis=0, keepdims=True) + 1e-12)
    return out, rr / (rr.max() + 1e-12), edges


def _band_fixture(secs=3.0):
    t = tt(secs)
    gate = lambda u: np.clip(np.minimum(u / 0.02, (0.3 - u) / 0.02), 0, 1) * (u < 0.3)
    bass = gate(np.mod(t, 1.0)) * 0.5 * np.sin(2 * np.pi * 60 * t)
    treb = gate(np.mod(t + 0.5, 1.0)) * 0.3 * np.sin(2 * np.pi * 6000 * t)
    return bass + treb


def _reactive_card(wd, smooth=None, kscale=0.06, doc_bands=(0, 1)):
    x = _band_fixture()
    save(wd, "track.wav", x)
    B, R, edges = band_frames(x, SR, 30, 4096, 16)
    bass = B[:, list(doc_bands)].mean(axis=1)
    if smooth:
        s = np.zeros_like(bass)
        for i in range(len(bass)):
            s[i] = (s[i - 1] if i else bass[0]) * smooth + bass[i] * (1 - smooth)
        bass = s
    scale = 1 + kscale * bass
    v, sc = _pulse_video(wd, lambda t: float(scale[min(len(scale) - 1, int(round(t * 30)))]), 3.0)
    pk_on = float(np.mean([sc[int(round((k + 0.2) * 30))] for k in range(3)]))
    pk_off = float(np.mean([sc[int(round((k + 0.7) * 30))] for k in range(3)]))
    return v, sc, scale, pk_on, pk_off


def am_rate(x, sr, lo=3, hi=30):
    """Dominant amplitude-modulation rate of a signal (Hz) from its envelope spectrum."""
    e = envelope(x, sr, 10)
    e = e - e.mean()
    d = sr // 200
    e = e[::d]
    E = np.abs(np.fft.rfft(e * np.hanning(len(e))))
    f = np.fft.rfftfreq(len(e), d / sr)
    m = (f >= lo) & (f <= hi)
    return float(f[m][int(np.argmax(E[m]))])


def _bp(x, lo, hi, sr=SR, order=4):
    from scipy.signal import butter, sosfilt
    return sosfilt(butter(order, [lo, hi], "band", fs=sr, output="sos"), x)


def _scratch(wd, lo, hi, rate, name, secs=2.0, grains=True, seed=2):
    rng = np.random.default_rng(seed)
    t = tt(secs)
    n = _bp(rng.standard_normal(len(t)), lo, hi)
    press = 0.55 + 0.45 * np.sin(2 * np.pi * rate * t)
    gate = ((t > 0.3) & (t < 1.6)).astype(float)
    gate = np.convolve(gate, np.ones(480) / 480, mode="same")
    y = n * press * gate
    if grains:
        for g in rng.uniform(0.35, 1.55, 25):
            i = int(g * SR)
            y[i:i + 48] += _bp(rng.standard_normal(480), lo, hi)[200:248] * 2.0
    y = 0.5 * y / np.abs(y).max()
    return save(wd, name, y), y


def _dur_of(x, sr, rel_db=-40):
    e = envelope(x, sr, 2)
    on = np.flatnonzero(e > e.max() * 10 ** (rel_db / 20))
    return (on[-1] - on[0]) / sr if len(on) else 0.0


def _events_audio(wd, events, secs, voice, name):
    x = np.zeros(int(secs * SR))
    for t in events:
        s = voice(t)
        i = int(t * SR)
        x[i:i + len(s)] += s[: len(x) - i]
    return save(wd, name, x), x


def _riser_impact(wd, cut, lead):
    rng = np.random.default_rng(6)
    secs = cut + 1.5
    x = np.zeros(int(secs * SR))
    n = int(lead * SR)
    u = np.arange(n) / n
    r = _bp(rng.standard_normal(n), 300, 6000) * u ** 2
    i0 = int((cut - lead) * SR)
    x[i0:i0 + n] += 0.4 * r / np.abs(r).max()
    m = int(0.8 * SR)
    v = np.arange(m) / SR
    imp = np.sin(2 * np.pi * np.cumsum(40 + 80 * np.exp(-v / 0.05)) / SR) * np.exp(-v / 0.25)
    i1 = int(cut * SR)
    x[i1:i1 + m] += 0.8 * imp
    p = save(wd, "transition.wav", x)
    vid = cut_video(Path(wd) / "transition.mp4", [cut], secs, 30, audio=p)
    return p, x, vid


def _ri_checks(x, cut, lead, vid):
    e = envelope(x, SR, 5)
    riser_start = np.flatnonzero(np.abs(x) > 1e-7)[0] / SR
    found, _ = cut_frames(vid)
    hit = rises_at(x, SR, [cut], pre=0.02, post=0.02)[0]
    pk = (int(cut * SR) + np.argmax(np.abs(x[int(cut * SR):int((cut + 0.1) * SR)]))) / SR
    return [check("riser starts %.2f s before the cut (±20 ms)" % lead, abs((cut - riser_start) - lead) < 0.02, cut - riser_start, lead),
            check("impact transient on the cut frame (peak within 1 frame)", 0 <= pk - cut <= 1 / 30, pk - cut, "0..1 frame"),
            check("picture cut where the impact lands", found == [int(round(cut * 30))], found, [int(round(cut * 30))]),
            check("impact steps the level up at the cut (>= 3 dB)", hit >= 3, hit, ">= 3"),
            check("negative control: nothing sounds before the riser", seg_db(x, SR, 0, max(0.05, cut - lead - 0.1)) < -90, seg_db(x, SR, 0, max(0.05, cut - lead - 0.1)), "< -90")]
