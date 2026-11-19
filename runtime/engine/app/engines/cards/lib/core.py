"""check / fx: the old runner harness (kosif-dragon-mind/runners/_harness.py) that card formulas call."""
from __future__ import annotations

import hashlib
import json
import math
import shutil
import subprocess
import wave
from pathlib import Path


def check(name: str, passed, measured=None, expected=None) -> dict:
    return {"check": name, "passed": bool(passed), "measured": _plain(measured), "expected": _plain(expected)}


def _plain(v):
    if v is None or isinstance(v, (bool, int, str)):
        return v
    if isinstance(v, float):
        return round(v, 6)
    if isinstance(v, (list, tuple)):
        return [_plain(x) for x in v]
    if isinstance(v, dict):
        return {str(k): _plain(x) for k, x in v.items()}
    try:
        return round(float(v), 6)
    except (TypeError, ValueError):
        return str(v)


def sha(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class fx:
    """Deterministic fixtures and measurements (ffmpeg, numpy, wave)."""

    @staticmethod
    def run(cmd: list, timeout: int = 60) -> subprocess.CompletedProcess:
        done = subprocess.run([str(c) for c in cmd], capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL)
        if done.returncode:
            raise RuntimeError("command failed (%d): %s" % (done.returncode, done.stderr[-400:]))
        return done

    @staticmethod
    def ffmpeg(*args, timeout: int = 60):
        return fx.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args], timeout)

    @staticmethod
    def fit_audio(seconds) -> list:
        """-af that pads/trims audio to exactly `seconds` (with -frames:v N it replaces -shortest, which cut frames)."""
        s = "%.6f" % float(seconds)
        return ["-af", "apad=whole_dur=%s,atrim=end=%s" % (s, s)]

    @staticmethod
    def video_seconds(path) -> float:
        """Frames of the first video stream / its frame rate: the length an exact mux keeps."""
        out = fx.run(["ffprobe", "-v", "error", "-count_packets", "-select_streams", "v:0", "-show_entries",
                      "stream=nb_read_packets,r_frame_rate", "-of", "json", str(path)]).stdout
        s = json.loads(out)["streams"][0]
        num, _, den = s["r_frame_rate"].partition("/")
        return int(s["nb_read_packets"]) / (float(num) / float(den or 1))

    @staticmethod
    def color_clip(path, color: str = "red", seconds: float = 1.0, size: str = "320x180", fps: int = 30):
        fx.ffmpeg("-f", "lavfi", "-i", "color=c=%s:s=%s:r=%d:d=%s" % (color, size, fps, seconds),
                  "-pix_fmt", "yuv420p", "-c:v", "libx264", "-crf", "12", str(path))
        return Path(path)

    @staticmethod
    def test_clip(path, seconds: float = 1.0, size: str = "320x180", fps: int = 30):
        fx.ffmpeg("-f", "lavfi", "-i", "testsrc2=s=%s:r=%d:d=%s" % (size, fps, seconds),
                  "-pix_fmt", "yuv420p", "-c:v", "libx264", "-crf", "12", str(path))
        return Path(path)

    @staticmethod
    def probe(path) -> dict:
        return json.loads(fx.run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)]).stdout)

    @staticmethod
    def frames(path, size=(64, 36)):
        """All frames as float arrays (N, H, W, 3) in 0..255, scaled down for measuring."""
        import numpy as np
        w, h = size
        done = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-vf", "scale=%d:%d" % (w, h), "-f", "rawvideo",
                               "-pix_fmt", "rgb24", "-"], capture_output=True, timeout=120, stdin=subprocess.DEVNULL)
        if done.returncode:
            raise RuntimeError(done.stderr.decode(errors="replace")[-300:])
        return np.frombuffer(done.stdout, dtype=np.uint8).reshape(-1, h, w, 3).astype(float)

    @staticmethod
    def tone(path, freq: float = 440.0, seconds: float = 1.0, rate: int = 44100, amp: float = 0.5):
        n = int(seconds * rate)
        with wave.open(str(path), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(rate)
            w.writeframes(b"".join(int(amp * 32767 * math.sin(2 * math.pi * freq * i / rate)).to_bytes(2, "little", signed=True)
                                   for i in range(n)))
        return Path(path)

    @staticmethod
    def read_wav(path):
        import numpy as np
        with wave.open(str(path), "rb") as w:
            ch, sw, rate, n = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
            data = np.frombuffer(w.readframes(n), dtype={1: np.int8, 2: np.int16, 4: np.int32}[sw]).astype(float)
        return data.reshape(-1, ch) / float(2 ** (8 * sw - 1)), rate

    @staticmethod
    def write_wav(path, samples, rate: int = 44100):
        import numpy as np
        a = np.clip(np.asarray(samples, dtype=float), -1, 1)
        if a.ndim == 1:
            a = a[:, None]
        with wave.open(str(path), "wb") as w:
            w.setnchannels(a.shape[1])
            w.setsampwidth(2)
            w.setframerate(rate)
            w.writeframes((a * 32767).astype("<i2").tobytes())
        return Path(path)

    @staticmethod
    def have(module: str) -> bool:
        import importlib.util
        return importlib.util.find_spec(module) is not None

    @staticmethod
    def which(binary: str) -> bool:
        return shutil.which(binary) is not None
