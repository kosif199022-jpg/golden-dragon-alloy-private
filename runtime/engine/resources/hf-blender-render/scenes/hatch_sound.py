# Procedural score + cartoon SFX for «فقس» (5.000 s, 48 kHz stereo). No samples, no licences.
import numpy as np, wave, sys

SR, DUR = 48000, 5.0
n = int(SR * DUR)
L = np.zeros(n); R = np.zeros(n)
rng = np.random.default_rng(3)
fr = lambda f: (f - 1) / 30.0  # frame -> seconds

def add(sig, t0, pan=0.0, g=1.0):
    i0 = int(t0 * SR)
    if i0 >= n: return
    sig = sig[: n - i0] * g
    L[i0:i0 + len(sig)] += sig * np.sqrt(0.5 * (1 - pan))
    R[i0:i0 + len(sig)] += sig * np.sqrt(0.5 * (1 + pan))

def env(length, a=0.005, d=0.3):
    t = np.arange(int(length * SR)) / SR
    e = np.minimum(1, t / a) * np.exp(-t / d)
    return t, e

def bell(freq, length=2.2, d=0.7):
    t, e = env(length, 0.002, d)
    s = (np.sin(2*np.pi*freq*t) + 0.45*np.sin(2*np.pi*freq*2.0*t)*np.exp(-t*3)
         + 0.25*np.sin(2*np.pi*freq*3.01*t)*np.exp(-t*5) + 0.12*np.sin(2*np.pi*freq*4.2*t)*np.exp(-t*8))
    return s * e

def pad(freqs, length, a=0.6, rel=0.8):
    t = np.arange(int(length * SR)) / SR
    s = sum(np.sin(2*np.pi*f*t + 0.3*np.sin(2*np.pi*0.3*t)) + 0.3*np.sin(2*np.pi*f*2.003*t) for f in freqs)
    e = np.minimum(1, t / a) * np.minimum(1, (length - t) / rel).clip(0)
    return s * e / len(freqs)

def noise_burst(length, lo, hi, d):
    t, e = env(length, 0.001, d)
    x = rng.standard_normal(len(t))
    X = np.fft.rfft(x); f = np.fft.rfftfreq(len(x), 1/SR)
    X[(f < lo) | (f > hi)] = 0
    return np.fft.irfft(X, len(x)) * e * 3

def tok(freq=520):  # egg knock (woody)
    t, e = env(0.18, 0.001, 0.035)
    return (np.sin(2*np.pi*freq*t*(1 + 0.4*np.exp(-t*60))) * e + 0.3 * noise_burst(0.18, 800, 4000, 0.01))

def slide(f0, f1, length, d=None):  # cartoon slide whistle / boing
    t = np.arange(int(length * SR)) / SR
    f = f0 * (f1 / f0) ** (t / length)
    ph = 2*np.pi*np.cumsum(f)/SR
    vib = 1 + 0.03*np.sin(2*np.pi*14*t)
    e = np.minimum(1, t/0.01) * np.minimum(1, (length - t)/0.05).clip(0)
    return np.sin(ph*vib) * e

def boing(f=180, length=0.5):
    t = np.arange(int(length * SR)) / SR
    fm = f * (1 + 0.6*np.exp(-t*8)*np.sin(2*np.pi*22*t))
    return np.sin(2*np.pi*np.cumsum(fm)/SR) * np.exp(-t*6) * np.minimum(1, t/0.004)

# --- music: C lydian, warm pad + celesta arpeggio
C = {"C4": 261.63, "D4": 293.66, "E4": 329.63, "F#4": 369.99, "G4": 392.0, "A4": 440.0, "B4": 493.88,
     "C5": 523.25, "D5": 587.33, "E5": 659.25, "G5": 783.99, "A5": 880.0, "B5": 987.77, "C6": 1046.5, "E6": 1318.5}
add(pad([130.81, 196.0, 329.63], 1.65, a=0.9, rel=0.3), 0.0, g=0.10)
add(pad([146.83, 220.0, 369.99, 493.88], 1.9, a=0.05, rel=0.5), 1.6, g=0.13)   # D lydian lift at the pop
add(pad([130.81, 196.0, 329.63, 493.88, 587.33], 1.75, a=0.3, rel=1.0), 3.25, g=0.13)
arp = [("C5",0.10),("E5",0.40),("G5",0.70),("B5",1.00),("E5",1.25)]
for nm, t in arp: add(bell(C[nm], 1.6, 0.5), t, pan=-0.3 + 0.15*(t), g=0.10)
for k, nm in enumerate(["D5","F#4","A5","B5","D5","A5"]):
    add(bell(C.get(nm, 0) or 369.99, 1.4, 0.45), 2.15 + k*0.2, pan=0.3 - 0.12*k, g=0.09)
for k, nm in enumerate(["G5","E5","C5","B4","G5","C6"]):
    add(bell(C[nm], 1.8 if k == 5 else 1.2, 0.8 if k == 5 else 0.4), 3.35 + k*0.17, pan=-0.2 + 0.08*k, g=0.10)
add(bell(C["E6"], 1.5, 0.9), 4.25, pan=0.2, g=0.06)

# --- SFX synced to the animation (frames from hatch.py)
for f, fq, p in [(8,560,-.2),(14,500,.2),(24,600,-.25),(28,540,.25),(32,620,-.25),(36,520,.25)]:
    add(tok(fq), fr(f), pan=p, g=0.35)
add(tok(300), fr(36), g=0.3)                                   # landing of the little hop
add(slide(500, 260, 0.14), fr(43), g=0.12)                     # squash (anticipation)
add(noise_burst(0.35, 300, 6000, 0.05), fr(48.5), g=0.5)        # shell crack/pop
add(boing(240, 0.25), fr(48.5), g=0.25)
sh = noise_burst(1.2, 5000, 14000, 0.35)                        # sparkle shimmer
add(sh * np.sin(np.linspace(0, np.pi, len(sh))), fr(49), g=0.25)
for k in range(10): add(bell(1800 + 260*k, 0.5, 0.12), fr(49) + 0.035*k, pan=(k%2-0.5)*0.8, g=0.05)
add(slide(330, 900, 0.22), fr(51), g=0.13)                      # pop-up slide whistle
add(boing(150, 0.5), fr(61), g=0.28)                            # landing squash
for f in (61, 102, 141): add(bell(2600, 0.12, 0.02), fr(f), g=0.06)   # blinks
add(slide(420, 520, 0.12), fr(73), pan=-0.3, g=0.06); add(slide(520, 400, 0.12), fr(89), pan=0.3, g=0.06)  # head turns
for f in range(108, 132, 8): add(noise_burst(0.12, 200, 1800, 0.04), fr(f), g=0.25)  # wing flaps
add(slide(400, 800, 0.16), fr(112), g=0.12); add(boing(200, 0.35), fr(122), g=0.22)  # happy hop
for k in range(8): add(bell(2200 + 300*k, 0.4, 0.1), fr(116) + 0.03*k, pan=(0.5-k%2)*0.8, g=0.045)

# light room reverb (multi-tap) and master
def verb(x):
    y = x.copy()
    for dly, g in [(0.031,.32),(0.047,.27),(0.071,.22),(0.113,.17),(0.167,.12),(0.229,.08)]:
        d = int(dly*SR); y[d:] += x[:-d] * g
    return y
L, R = verb(L), verb(R[::-1])[::-1] * 0 + verb(R)
fade = np.ones(n); fo = int(0.45*SR); fade[-fo:] = np.linspace(1, 0, fo) ** 1.5
fi = int(0.02*SR); fade[:fi] = np.linspace(0, 1, fi)
L *= fade; R *= fade
peak = max(np.abs(L).max(), np.abs(R).max()); L /= peak / 0.7; R /= peak / 0.7
st = (np.stack([L, R], 1) * 32767).astype("<i2")
with wave.open(sys.argv[1], "wb") as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(st.tobytes())
print("wrote", sys.argv[1], n / SR, "s")
