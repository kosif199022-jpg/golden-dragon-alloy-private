"""Soundtrack for Kitten Rescue (20 s): worried-to-happy music, water, meows, foley, purr."""
import subprocess, sys
import numpy as np
SR = 48000; D = 20.0; n = int(D * SR); t = np.arange(n) / SR
mix = np.zeros(n); rng = np.random.default_rng(9)
def add(sig, at, g):
    i = int(at * SR); m = max(0, min(len(sig), n - i)); mix[i:i + m] += sig[:m] * g
def tone(f, dur, decay=5, harm=((1, 1),), att=0.004):
    k = np.arange(int(dur * SR)) / SR
    return sum(a * np.sin(2 * np.pi * f * h * k) for h, a in harm) * np.minimum(1, k / att) * np.exp(-k * decay)
def lp(x, fc):
    X = np.fft.rfft(x); fr = np.fft.rfftfreq(len(x), 1 / SR); return np.fft.irfft(X / (1 + (fr / fc) ** 4), len(x))
def bp(x, a, b):
    X = np.fft.rfft(x); fr = np.fft.rfftfreq(len(x), 1 / SR); return np.fft.irfft(X * ((fr > a) & (fr < b)), len(x))
pluck = lambda f: tone(f, 1.0, 6, ((1, 1), (2, 0.4), (3, 0.15)))
# worried minor ostinato 0-9.4, driving 9.4-12.3, happy major 12.3-20
minor = [440, 523, 659, 523, 494, 587, 698, 587]
for i, x in enumerate(np.arange(0, 9.4, 0.3)): add(pluck(minor[i % 8]), x, 0.09)
for i, x in enumerate(np.arange(9.4, 12.3, 0.15)): add(pluck([392, 440, 494, 523][i % 4]), x, 0.08)
major = [523, 659, 784, 659, 587, 698, 880, 698, 523, 659, 784, 1047]
for i, x in enumerate(np.arange(12.3, 20, 0.32)): add(tone(major[i % 12], 1.4, 3.5, ((1, 1), (4, 0.2))), x, 0.12)
for x in np.arange(0, 20, 1.2): add(tone(110 if x < 12.3 else 131, 1.4, 2.5, ((1, 1), (2, 0.3))), x, 0.12)
# water bed + paddling splashes
mix += lp(rng.normal(0, 1, n), 700) * 0.05 * (0.7 + 0.3 * np.sin(2 * np.pi * t / 3))
for x in np.arange(0.05, 8.5, 0.16): add(bp(rng.normal(0, 1, int(0.12 * SR)), 900, 5000) * np.exp(-np.arange(int(0.12 * SR)) / SR * 30), x + rng.uniform(0, .05), 0.09)
def meow(dur=0.6, f0=700, f1=520):
    k = np.arange(int(dur * SR)) / SR; f = f0 + (f1 - f0) * (k / dur) + 120 * np.sin(np.pi * k / dur)
    ph = 2 * np.pi * np.cumsum(f) / SR
    s = sum(np.sin(ph * h) / h for h in range(1, 6))
    return s * np.sin(np.pi * k / dur) ** 0.6
for x, f0 in ((0.4, 760), (1.6, 820), (3.4, 900), (5.6, 860), (8.0, 780)): add(meow(0.55, f0, f0 * 0.7), x, 0.18)
add(meow(0.35, 980, 1100), 9.3, 0.15)
k = np.arange(int(0.5 * SR)) / SR
add(np.sin(2 * np.pi * (200 + 520 * k) * k) * np.exp(-k * 6), 3.86, 0.3)                       # shock boing
for x in np.arange(2.0, 3.55, 0.36): add(tone(160, 0.1, 30), x, 0.25)                           # footsteps
for x in np.arange(5.15, 6.55, 0.21): add(tone(170, 0.08, 35), x, 0.25)
add(tone(1400, 0.3, 10), 4.9, 0.1)                                                               # grab
m = int(0.9 * SR); kk = np.arange(m) / SR
add(lp(rng.normal(0, 1, m), 1500) * np.sin(np.pi * kk / 0.9) ** 2, 7.5, 0.5)                    # throw whoosh
add(lp(rng.normal(0, 1, int(0.8 * SR)), 2500) * np.exp(-np.arange(int(0.8 * SR)) / SR * 5), 8.42, 0.6)  # splash
for x in np.arange(9.5, 12.2, 0.5): add(bp(rng.normal(0, 1, int(0.15 * SR)), 300, 1200) * np.exp(-np.arange(int(0.15 * SR)) / SR * 15), x, 0.25)  # rope pulls
add(tone(260, 0.5, 4, ((1, 1),)), 12.35, 0.15); add(tone(340, 0.3, 8), 13.1, 0.2)               # hop + land
for x in np.arange(13.6, 14.6, 0.04): add(bp(rng.normal(0, 1, int(0.03 * SR)), 2000, 8000), x, 0.08)  # shake spray
add(bp(rng.normal(0, 1, int(0.15 * SR)), 2000, 6000) * np.exp(-np.arange(int(0.15 * SR)) / SR * 20), 14.75, 0.25)  # sneeze
purr = lp(rng.normal(0, 1, n), 180) * (0.5 + 0.5 * np.sign(np.sin(2 * np.pi * 26 * t))) * (t > 16) * np.minimum(1, (t - 16).clip(0) / 0.8)
mix += purr * 0.35
for j, f in enumerate([1047, 1319, 1568, 2093]): add(tone(f, 1.2, 3), 16.2 + j * 0.25, 0.06)
mix *= np.minimum(1, (D - t) / 1.2)
out = mix.copy()
for dl, g in ((0.067, 0.25), (0.119, 0.2), (0.181, 0.14)):
    d = int(dl * SR); out[d:] += mix[:-d] * g
st = np.stack([out, np.roll(out, int(0.008 * SR))], 1); st /= np.abs(st).max() + 1e-9
p = sys.argv[1]; st.astype(np.float32).tofile(p + '.f32')
subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'f32le', '-ar', str(SR), '-ac', '2', '-i', p + '.f32', '-af', 'loudnorm=I=-14:TP=-1.5:LRA=11', '-ar', str(SR), p], check=True)
