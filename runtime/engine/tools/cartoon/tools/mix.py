"""Level lock from SKILL.md: music 16 dB under the voice's gated RMS,
SFX at 50 % or less with peaks capped at 0.7x the voice peak. No ducking. usage: mix.py voice music sfx
v1.3: a silent stem (gated RMS 0 or NaN) stops with exit 1 instead of a NaN silent mix: a film on an existing song
skips mix.py (extract the song with -c copy and let `dragon.py mux` put it on the video). The mix is stereo."""
import subprocess, sys, wave, numpy as np
SR = 48000; MUSIC_DB = -16.0
def load(p):
    return np.frombuffer(subprocess.run(['ffmpeg', '-v', 'error', '-i', p, '-ac', '1', '-ar', str(SR), '-f', 'f32le', '-'], capture_output=True).stdout, np.float32).copy()
def grms(x, floor_db=-40):
    h = int(.05 * SR); n = len(x) // h
    r = np.sqrt((x[:n * h].reshape(n, h) ** 2).mean(1)); g = r[r > r.max() * 10 ** (floor_db / 20)]
    return float(np.sqrt((g ** 2).mean()))
db = lambda v: 20 * np.log10(max(v, 1e-9))
def grms_ok(x, name):
    try:
        r = grms(x) if len(x) else 0.0
    except ValueError:
        r = 0.0
    if not np.isfinite(r) or r <= 0:
        sys.exit(f"mix.py: the {name} stem is silent or empty (gated RMS {r}): a song-only film does not go through "
                 f"mix.py; extract the song with ffmpeg -c copy and use `python3 <skill>/scripts/dragon.py mux`")
    return r
v, m, s = (load(p) for p in sys.argv[1:4]); N = len(v)
for x, name in ((v, "voice"), (m, "music"), (s, "sfx")): grms_ok(x, name); fit = lambda x: np.pad(x, (0, max(0, N - len(x))))[:N]; m, s = fit(m), fit(s)
vr = grms(v); m = m * (10 ** (MUSIC_DB / 20) * vr / grms(m)); s = s * (.5 * vr / grms(s))
cap = .7 * np.abs(v).max()
if np.abs(s).max() > cap: s = s * (cap / np.abs(s).max())
print(f'music {db(grms(m)) - db(vr):+.1f} dB vs voice, sfx {db(grms(s)) - db(vr):+.1f} dB vs voice, sfx peak {db(np.abs(s).max()) - db(np.abs(v).max()):+.1f} dB vs voice peak')
x = v + m + s; x = x / max(1, np.abs(x).max())
with wave.open('mix_raw.wav', 'wb') as w:
    pcm = (x * 32767).astype(np.int16); st = np.repeat(pcm, 2)   # stereo: the same signal on L and R
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(st.tobytes())
