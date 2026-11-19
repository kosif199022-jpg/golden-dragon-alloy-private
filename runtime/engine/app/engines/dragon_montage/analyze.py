"""Station 1 «العين الأولى»: footage (+ optional music) -> analysis.json (kosif.dm.analysis.v1).

probe · loudness (ebur128) · shots (PySceneDetect, fallback ffmpeg scdet) · per-shot quality / faces (YuNet) /
motion / colour / thumbnail · words (faster-whisper + VAD) · silences · RMS energy every 0.5 s ·
music beats + downbeats (librosa) · contact sheet. A missing optional tool leaves its field empty and is
listed in "missing"; the station never crashes because of it.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
import tempfile
import time
import wave
from pathlib import Path

from . import common as C
from ..media import exe

STATION = "analyze"
SAMPLE_FPS = 4.0          # frames per second sampled for quality / faces / colour
SAMPLE_W = 480            # width of the sampled frames (and thumbnails)
ENERGY_STEP = 0.5         # seconds between RMS energy points
MIN_SHOT = 0.5            # shorter detections are merged
LONG = 3600               # whole-file ffmpeg passes; a timeout degrades into `missing`


def r3(x):
    return None if x is None else round(float(x), 3)


def clamp01(x):
    return max(0.0, min(1.0, float(x)))


class Ctx:
    """tools_used / missing for the whole run, plus receipts."""

    def __init__(self, job: Path):
        self.job, self.used, self.missing = job, [], []

    def use(self, name):
        if name not in self.used:
            self.used.append(name)

    def miss(self, name):
        if name not in self.missing:
            self.missing.append(name)

    def receipt(self, tool, argv, rc, seconds, out=None, note=""):
        C.receipt(self.job, STATION, tool, argv, rc, seconds, out, note)

    def run(self, tool, argv, **kw):
        kw.setdefault("check", False)
        return C.run(self.job, STATION, tool, argv, **kw)

    def ffpass(self, tool, path, *af):
        """Whole-file ffmpeg audio/video pass to null; returns stderr or None (timeouts are reported)."""
        res = self.run(tool, ["ffmpeg", "-hide_banner", "-nostats", "-i", path, *af, "-f", "null", "-"], timeout=LONG)
        if res.returncode == 124:
            self.miss(f"{tool} (timeout)")
        return (res.stderr or "") if res.returncode == 0 else None


def rel(job: Path, p: Path) -> str:
    try:
        return str(p.resolve().relative_to(job))
    except ValueError:
        return str(p.resolve())


# ---------------------------------------------------------------- probe / audio
def probe_clip(ctx: Ctx, path: Path) -> dict:
    res = ctx.run("ffprobe", ["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", path])
    ctx.use("ffprobe")
    info = json.loads(res.stdout or "{}") if res.returncode == 0 else {}
    streams = info.get("streams", [])
    v = next((s for s in streams if s.get("codec_type") == "video"), {})
    a = next((s for s in streams if s.get("codec_type") == "audio"), None)
    try:
        num, den = (v.get("avg_frame_rate") or v.get("r_frame_rate") or "0/1").split("/")
        fps = float(num) / float(den) if float(den) else 0.0
    except (ValueError, ZeroDivisionError):
        fps = 0.0
    dur = info.get("format", {}).get("duration") or v.get("duration") or 0
    return {"duration": r3(float(dur)), "width": int(v.get("width") or 0), "height": int(v.get("height") or 0),
            "fps": round(fps, 3), "has_audio": a is not None, "has_video": bool(v)}


def loudness(ctx: Ctx, path: Path):
    err = ctx.ffpass("ffmpeg.ebur128", path, "-vn", "-af", "ebur128")
    m = re.findall(r"I:\s+(-?[\d.]+|-inf)\s+LUFS", err or "")
    if not m or m[-1] == "-inf":
        return None
    ctx.use("ffmpeg.ebur128")
    return round(float(m[-1]), 1)


def silences(ctx: Ctx, path: Path, duration: float) -> list[dict]:
    err = ctx.ffpass("ffmpeg.silencedetect", path, "-vn", "-af", "silencedetect=noise=-35dB:d=0.5")
    if err is None:
        return []
    ctx.use("ffmpeg.silencedetect")
    out, start = [], None
    for line in err.splitlines():
        m = re.search(r"silence_start:\s*(-?[\d.]+)", line)
        if m:
            start = max(0.0, float(m.group(1)))
        m = re.search(r"silence_end:\s*(-?[\d.]+)", line)
        if m and start is not None:
            out.append({"start": r3(start), "end": r3(float(m.group(1)))})
            start = None
    if start is not None and duration:
        out.append({"start": r3(start), "end": r3(duration)})
    return out


def extract_wav(ctx: Ctx, path: Path, out: Path, sr: int = 16000) -> Path | None:
    res = ctx.run("ffmpeg.extract_audio", ["ffmpeg", "-y", "-v", "error", "-i", path, "-vn", "-ac", "1", "-ar", str(sr),
                                           "-c:a", "pcm_s16le", out], out=out, timeout=LONG)
    return out if res.returncode == 0 and out.exists() and out.stat().st_size > 44 else None


def read_wav_mono(path: Path):
    """(float32 samples in -1..1, sample_rate)."""
    import numpy as np
    with wave.open(str(path), "rb") as w:
        sr, ch, raw = w.getframerate(), w.getnchannels(), w.readframes(w.getnframes())
    data = np.frombuffer(raw, dtype="<i2").astype("float32") / 32768.0
    return (data.reshape(-1, ch).mean(axis=1) if ch > 1 else data), sr


def energy_curve(ctx: Ctx, wav: Path | None) -> list[dict]:
    if not wav:
        return []
    t0 = time.time()
    data, sr = read_wav_mono(wav)
    step = int(sr * ENERGY_STEP)
    out = [{"t": r3(i / sr), "rms": round(float((data[i:i + step] ** 2).mean() ** 0.5), 4)}
           for i in range(0, len(data), step) if len(data[i:i + step])]
    ctx.receipt("rms_energy", ["rms", wav, f"step={ENERGY_STEP}"], 0, time.time() - t0)
    ctx.use("rms_energy")
    return out


_WHISPER: dict = {}


def transcribe(ctx: Ctx, wav: Path | None, model_name: str, language: str | None) -> list[dict]:
    if not wav:
        return []
    if not C.have_module("faster_whisper"):
        ctx.miss("faster-whisper")
        return []
    t0 = time.time()
    try:
        from faster_whisper import WhisperModel
        if model_name not in _WHISPER:
            _WHISPER[model_name] = WhisperModel(model_name, device="auto", compute_type="int8")
        model = _WHISPER[model_name]
    except Exception as exc:  # noqa: BLE001 — download blocked / no network / bad model
        ctx.miss("faster-whisper-model")
        ctx.receipt("faster-whisper", ["load", model_name], 1, time.time() - t0, note=str(exc))
        return []
    try:
        audio, _ = read_wav_mono(wav)              # 16 kHz mono float32: skips faster-whisper's PyAV decoder
        segs, _ = model.transcribe(audio, language=language or None, word_timestamps=True, vad_filter=True, beam_size=5)
        words = [{"w": w.word.strip(), "start": r3(w.start), "end": r3(w.end), "conf": round(float(w.probability or 0), 3)}
                 for s in segs for w in (s.words or []) if (w.word or "").strip()]
    except Exception as exc:  # noqa: BLE001
        ctx.receipt("faster-whisper", ["transcribe", wav, model_name], 1, time.time() - t0, note=str(exc))
        ctx.miss("faster-whisper-transcribe")
        return []
    ctx.receipt("faster-whisper", ["transcribe", wav, model_name, f"lang={language}", "vad"], 0, time.time() - t0)
    ctx.use("faster-whisper")
    return words


# ---------------------------------------------------------------- shots
def shots_pyscenedetect(ctx: Ctx, path: Path):
    t0 = time.time()
    try:
        from scenedetect import ContentDetector, detect
        scenes = detect(str(path), ContentDetector(threshold=27.0, min_scene_len=15))
    except Exception as exc:  # noqa: BLE001
        ctx.receipt("pyscenedetect", ["detect", path, "ContentDetector"], 1, time.time() - t0, note=str(exc))
        return None
    ctx.receipt("pyscenedetect", ["detect", path, "ContentDetector", "threshold=27"], 0, time.time() - t0)
    ctx.use("pyscenedetect")
    return [float(getattr(s[0], "seconds", None) or s[0].get_seconds()) for s in scenes[1:]]


def shots_scdet(ctx: Ctx, path: Path):
    err = ctx.ffpass("ffmpeg.scdet", path, "-an", "-vf", "scdet=threshold=10")
    if err is None:
        return None
    ctx.use("ffmpeg.scdet")
    return [float(m) for m in re.findall(r"lavfi\.scd\.time:\s*([\d.]+)", err)]


def build_shots(cuts, duration):
    starts = [0.0]
    for c in sorted(c for c in (cuts or []) if 0 < c < duration):
        if c - starts[-1] >= MIN_SHOT and duration - c >= MIN_SHOT:
            starts.append(c)
    return list(zip(starts, starts[1:] + [duration]))


# ---------------------------------------------------------------- frames, faces, quality
def sample_size(info: dict) -> tuple[int, int]:
    return SAMPLE_W, int(round(info["height"] * SAMPLE_W / max(1, info["width"]) / 2) * 2) or 270


def iter_frames(ctx: Ctx, path: Path, info: dict, timeout: float = 1800):
    """Stream SAMPLE_FPS frames SAMPLE_W wide -> (t, HxWx3 RGB uint8), one frame in memory at a time."""
    import numpy as np
    w, h = sample_size(info)
    argv = [exe("ffmpeg"), "-v", "error", "-i", str(path), "-an", "-vf", f"fps={SAMPLE_FPS},scale={w}:{h}",
            "-pix_fmt", "rgb24", "-f", "rawvideo", "-"]
    size, t0, n, note = w * h * 3, time.time(), 0, ""
    with tempfile.TemporaryFile() as err:
        proc = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=err, stdin=subprocess.DEVNULL)
        try:
            while True:
                if time.time() - t0 > timeout:
                    proc.kill()
                    note = f"timeout after {timeout}s ({n} frames kept)"
                    break
                buf = proc.stdout.read(size)
                if len(buf) < size:
                    break
                yield (n + 0.5) / SAMPLE_FPS, np.frombuffer(buf, dtype=np.uint8).reshape(h, w, 3)
                n += 1
        finally:
            if proc.poll() is None:
                proc.kill()
            proc.stdout.close()
            rc = proc.wait()
            err.seek(0)
            note = note or (err.read().decode("utf-8", "replace") if rc else "")
            ctx.receipt("ffmpeg.sample_frames", argv + [f"frames={n}"], 124 if note.startswith("timeout") else rc,
                        time.time() - t0, note=note)


def write_jpg(path: Path, rgb, quality: int = 85) -> bool:
    """cv2.imwrite fails on non-ASCII Windows paths: encode in memory, write with Python."""
    import cv2
    ok, buf = cv2.imencode(".jpg", cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR) if rgb.ndim == 3 else rgb,
                           [cv2.IMWRITE_JPEG_QUALITY, quality])
    try:
        return bool(ok) and Path(path).write_bytes(buf.tobytes()) is not None
    except OSError:
        return False


def read_img(path: Path):
    import cv2
    import numpy as np
    try:
        buf = np.frombuffer(Path(path).read_bytes(), dtype=np.uint8)
    except OSError:
        return None
    return cv2.imdecode(buf, cv2.IMREAD_COLOR) if buf.size else None


_FACE: dict = {}


def cv_safe_path(p: Path) -> str:
    """OpenCV on Windows cannot open a file whose path has non-ASCII characters (e.g. Desktop\\التنين الأسود, «خطابة 2»):
    FaceDetectorYN.create fails and face detection silently disappeared. Such a model is copied once to an ASCII temp
    folder and opened from there. v10.15."""
    s = str(p)
    if s.isascii():
        return s
    import os
    import shutil
    for base in (Path(tempfile.gettempdir()), Path(os.environ.get("PUBLIC") or "C:/Users/Public"), Path.home()):
        d = base / "black_dragon_models"
        if not str(d).isascii():
            continue
        try:
            d.mkdir(parents=True, exist_ok=True)
            dst = d / Path(p).name
            if not dst.is_file() or dst.stat().st_size != Path(p).stat().st_size:
                shutil.copy2(p, dst)
            return str(dst)
        except OSError:
            continue
    return s


def face_detector():
    """YuNet (OpenCV FaceDetectorYN) with models/face_detection_yunet_2023mar.onnx -> detect(rgb) -> boxes, or None.
    Without the model faces stay null and the model is reported missing (no skin-colour guessing)."""
    if "d" in _FACE:
        return _FACE["d"]
    _FACE["d"] = None
    from .doctor import model_path
    mp = model_path("yunet-face-model")
    try:
        import cv2
        import numpy as np
        if mp and hasattr(cv2, "FaceDetectorYN"):
            yn = cv2.FaceDetectorYN.create(cv_safe_path(mp), "", (320, 320), 0.7, 0.3, 5000)
            size = [(320, 320)]

            def detect(rgb, min_frac=0.004):
                h, w = rgb.shape[:2]
                if size[0] != (w, h):
                    yn.setInputSize((w, h))
                    size[0] = (w, h)
                _, faces = yn.detect(cv2.cvtColor(np.ascontiguousarray(rgb), cv2.COLOR_RGB2BGR))
                return [(int(max(0, f[0])), int(max(0, f[1])), int(f[2]), int(f[3]), round(float(f[-1]), 3))
                        for f in (faces if faces is not None else []) if float(f[2]) * float(f[3]) >= min_frac * w * h]
            _FACE["d"] = detect
    except Exception:  # noqa: BLE001
        pass
    return _FACE["d"]


def largest_face(boxes, w: int, h: int):
    if not boxes:
        return None
    x, y, bw, bh = max(boxes, key=lambda b: b[2] * b[3])[:4]
    return ((x + bw / 2) / w, (y + bh / 2) / h, [x / w, y / h, bw / w, bh / h])


class ShotAcc:
    """Per-shot running metrics fed one frame at a time; keeps <=5 frames (faces, clipping, thumbnail)."""

    def __init__(self, n: int):
        self.n = max(1, int(n))
        self.pick = sorted({0, self.n // 4, self.n // 2, (3 * self.n) // 4, self.n - 1})
        self.kept, self.last, self.k, self.prev = {}, None, 0, None
        self.sharp, self.luma, self.diffs, self.shifts, self.sats, self.rgbs = [], [], [], [], [], []

    def add(self, f) -> None:
        import cv2
        import numpy as np
        g = cv2.cvtColor(f, cv2.COLOR_RGB2GRAY)
        self.sharp.append(cv2.Laplacian(g, cv2.CV_64F).var())
        self.luma.append(g.mean() / 255.0)
        self.sats.append(cv2.cvtColor(f, cv2.COLOR_RGB2HSV)[..., 1].mean() / 255.0)
        self.rgbs.append(f.reshape(-1, 3).mean(axis=0) / 255.0)
        gf = g.astype("float32")
        if self.prev is not None:
            self.diffs.append(float(np.abs(gf - self.prev).mean()) / 255.0)
            self.shifts.append(cv2.phaseCorrelate(self.prev, gf)[0])
        self.prev = gf
        if self.k in self.pick:
            self.kept[self.k] = f
        self.last, self.k = f, self.k + 1

    def frames(self) -> list:
        out = dict(self.kept)
        if self.last is not None and (self.k - 1) not in out:
            out[self.k - 1] = self.last
        return [out[i] for i in sorted(out)]

    def mid(self):
        if self.n // 2 in self.kept:
            return self.kept[self.n // 2]
        fr = self.frames()
        return fr[len(fr) // 2] if fr else None

    def finish(self, ctx: Ctx) -> dict:
        import cv2
        import numpy as np
        frames = self.frames()
        lap = float(np.median(self.sharp)) if self.sharp else 0.0
        sharpness = lap / (lap + 150.0)                      # 150 = soft/sharp knee at 480 px wide
        L = float(np.mean(self.luma)) if self.luma else 0.0
        exposure, clipped = clamp01(1.0 - abs(L - 0.5) * 2.0), 0.0
        m = self.mid()
        if m is not None:
            g = cv2.cvtColor(m, cv2.COLOR_RGB2GRAY)
            clipped = float(((g < 8) | (g > 247)).mean())
            exposure = clamp01(exposure - 0.5 * clipped)
        shake = 0.0
        if len(self.shifts) >= 3:                              # jitter = change of the global translation
            j = float(np.sqrt((np.diff(np.array(self.shifts), axis=0) ** 2).sum(axis=1)).mean())
            shake = j / (j + 3.0)
        motion = clamp01(float(np.mean(self.diffs)) * 6.0) if self.diffs else 0.0
        score = clamp01(0.45 * sharpness + 0.30 * exposure + 0.25 * (1.0 - shake))
        faces = face_c = face_box = None
        det = face_detector()
        if det is None:
            ctx.miss("yunet-face-model")
        elif frames:
            faces, found = 0, []
            for f in frames:
                boxes = det(f)
                faces = max(faces, len(boxes))
                lf = largest_face(boxes, f.shape[1], f.shape[0])
                if lf:
                    found.append(lf)
            if found:   # median centre of the per-frame largest face -> crop anchor for the render
                face_c = [r3(float(np.median([f[0] for f in found]))), r3(float(np.median([f[1] for f in found])))]
                face_box = [r3(v) for v in max(found, key=lambda f: f[2][2] * f[2][3])[2]]
            ctx.use("kmm.faces.yunet")
        mean_rgb = np.mean(self.rgbs, axis=0).tolist() if self.rgbs else [0, 0, 0]
        return {"quality": {"sharpness": r3(sharpness), "exposure": r3(exposure), "shake": r3(shake), "score": r3(score),
                            "luma": r3(L), "clipped": r3(clipped)},
                "faces": faces, "face_center": face_c, "faces_box": face_box, "motion_energy": r3(motion),
                "color": {"mean_rgb": [r3(c) for c in mean_rgb], "saturation": r3(np.mean(self.sats) if self.sats else 0.0)}}


def expected_samples(s: float, e: float) -> int:
    lo = math.ceil(s * SAMPLE_FPS - 0.5 - 1e-9)
    hi = math.ceil(e * SAMPLE_FPS - 0.5 - 1e-9)
    return max(0, hi - max(0, lo))


def contact_sheet(ctx: Ctx, items, out: Path, cols: int = 4):
    """items: [(label, Path)] -> grid jpg."""
    import cv2
    import numpy as np
    t0, tw, tiles = time.time(), 320, []
    for label, p in items:
        img = read_img(p)
        if img is None:
            continue
        img = cv2.resize(img, (tw, int(img.shape[0] * tw / img.shape[1])))
        cv2.rectangle(img, (0, 0), (tw, 22), (0, 0, 0), -1)
        cv2.putText(img, label, (6, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
        tiles.append(img)
    if not tiles:
        return None
    th = max(t.shape[0] for t in tiles)
    tiles = [cv2.copyMakeBorder(t, 0, th - t.shape[0], 0, 0, cv2.BORDER_CONSTANT, value=(20, 20, 20)) for t in tiles]
    while len(tiles) % cols:
        tiles.append(np.full_like(tiles[0], 20))
    sheet = np.vstack([np.hstack(tiles[i:i + cols]) for i in range(0, len(tiles), cols)])
    ok = write_jpg(out, sheet[..., ::-1])
    ctx.receipt("opencv.contact_sheet", ["contact_sheet", out, f"tiles={len(items)}"], 0 if ok else 1, time.time() - t0,
                out=out if ok else None, note="" if ok else "jpeg write failed")
    return out if ok else None


# ---------------------------------------------------------------- clip
def analyze_clip(ctx: Ctx, cid: str, path: Path, adir: Path, no_transcribe: bool, model: str, language) -> dict:
    info = probe_clip(ctx, path)
    dur = info["duration"] or 0.0
    clip = {"id": cid, "path": str(path), "duration": dur, "width": info["width"], "height": info["height"],
            "fps": info["fps"], "has_audio": info["has_audio"], "loudness_lufs": None,
            "shots": [], "words": [], "silences": [], "energy": []}
    cuts = None
    if info["has_video"]:
        if C.have_module("scenedetect"):
            cuts = shots_pyscenedetect(ctx, path)
        else:
            ctx.miss("pyscenedetect")
        if cuts is None:
            cuts = shots_scdet(ctx, path)
        if cuts is None:
            ctx.miss("shot-detection")
    bounds = build_shots(cuts, dur) if info["has_video"] else []
    can_cv = C.have_module("cv2") and C.have_module("numpy")
    if not can_cv:
        ctx.miss("opencv")
    shots = [{"id": f"{cid}-s{i:03d}", "start": r3(s), "end": r3(e),
              "quality": {"sharpness": None, "exposure": None, "shake": None, "score": None},
              "faces": None, "face_center": None, "faces_box": None, "motion_energy": None,
              "color": {"mean_rgb": None, "saturation": None}, "thumb": None} for i, (s, e) in enumerate(bounds, 1)]
    if can_cv and bounds:
        accs, done, cur = {}, set(), 0

        def close(k):
            acc = accs.get(k)
            if acc is None or k in done:
                return
            done.add(k)
            shots[k].update(acc.finish(ctx))
            thumb, m = adir / f"{shots[k]['id']}.jpg", acc.mid()
            if m is not None and write_jpg(thumb, m):
                shots[k]["thumb"] = rel(ctx.job, thumb)
            accs[k] = None
        for t, f in iter_frames(ctx, path, info):
            while cur < len(bounds) - 1 and t >= bounds[cur][1]:
                close(cur)
                cur += 1
            if accs.get(cur) is None and cur not in done:
                accs[cur] = ShotAcc(expected_samples(*bounds[cur]))
            accs[cur].add(f)
        for k in list(accs):
            close(k)
        if done:
            ctx.use("opencv.quality")
    for shot, (s, e) in zip(shots, bounds):
        thumb = adir / f"{shot['id']}.jpg"
        if not shot["thumb"] and info["has_video"]:
            ctx.run("ffmpeg.thumb", ["ffmpeg", "-y", "-v", "error", "-ss", f"{(s + e) / 2:.3f}", "-i", path, "-frames:v",
                                     "1", "-vf", f"scale={SAMPLE_W}:-2", "-q:v", "4", thumb], out=thumb)
            if thumb.exists():
                shot["thumb"] = rel(ctx.job, thumb)
        clip["shots"].append(shot)
    if info["has_audio"]:
        clip["loudness_lufs"] = loudness(ctx, path)
        clip["silences"] = silences(ctx, path, dur)
        with tempfile.TemporaryDirectory(prefix="dm_an_") as td:
            wav = extract_wav(ctx, path, Path(td) / f"{cid}.wav")
            clip["energy"] = energy_curve(ctx, wav)
            if not no_transcribe:
                clip["words"] = transcribe(ctx, wav, model, language)
    return clip


# ---------------------------------------------------------------- music
def downbeats_from(beats, strength=None):
    """Every 4th beat, phase chosen where onset strength is highest."""
    if len(beats) < 4:
        return list(beats[:1])
    best, best_k = -1.0, 0
    for k in range(4):
        sel = range(k, len(beats), 4)
        v = sum(strength[i] for i in sel) / max(1, len(sel)) if strength is not None else (1.0 if k == 0 else 0.0)
        if v > best:
            best, best_k = v, k
    return beats[best_k::4]


def analyze_music(ctx: Ctx, path: Path | None) -> dict:
    out = {"path": str(path) if path else None, "bpm": None, "beats": [], "downbeats": []}
    if not path:
        return out
    if not C.have_module("librosa"):
        ctx.miss("librosa")
        ctx.miss("beat-tracking")
        return out
    t0, hop = time.time(), 256
    try:
        import librosa
        import numpy as np
        y, sr = librosa.load(str(path), sr=22050, mono=True)
        env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop)
        tempo, frames = librosa.beat.beat_track(onset_envelope=env, sr=sr, hop_length=hop, units="frames")
        frames = np.asarray(frames, dtype=int)
        beats = librosa.frames_to_time(frames, sr=sr, hop_length=hop).tolist()
        tempo = np.atleast_1d(tempo)
        bpm = float(tempo[0]) if len(tempo) else None
        if len(beats) >= 4:     # robust tempo: slope of beat time vs index (avoids frame-quantised IBI)
            slope = float(np.polyfit(np.arange(len(beats)), np.array(beats), 1)[0])
            bpm = 60.0 / slope if slope > 0 else bpm
        strength = [float(env[max(0, f - 2):f + 3].max()) if len(env) else 0.0 for f in frames]
    except Exception as exc:  # noqa: BLE001
        ctx.receipt("librosa.beat_track", ["beat_track", path], 1, time.time() - t0, note=str(exc))
        ctx.miss("beat-tracking")
        return out
    ctx.receipt("librosa.beat_track", ["beat_track", path, f"hop={hop}"], 0, time.time() - t0)
    ctx.use("librosa")
    out.update({"bpm": round(bpm, 2) if bpm else None, "beats": [r3(b) for b in beats],
                "downbeats": [r3(b) for b in downbeats_from(beats, strength)]})
    return out


# ---------------------------------------------------------------- station
def analyze(job, clips: list, music=None, no_transcribe=False, whisper_model="small", language="ar") -> dict:
    job = C.job_dir(job)
    ctx = Ctx(job)
    adir = job / "analysis"
    adir.mkdir(parents=True, exist_ok=True)
    if not (C.have("ffprobe") and C.have("ffmpeg")):
        raise SystemExit("ffmpeg/ffprobe are required for station 1 (العين الأولى)")
    result = C.new("analysis", clips=[], music={}, contact_sheet=None, tools_used=[], missing=[])
    for i, p in enumerate(clips, 1):
        result["clips"].append(analyze_clip(ctx, f"c{i:02d}", Path(p).resolve(), adir, no_transcribe, whisper_model,
                                            None if language == "auto" else language))
    result["music"] = analyze_music(ctx, Path(music).resolve() if music else None)
    items = [(s["id"], job / s["thumb"]) for c in result["clips"] for s in c["shots"] if s.get("thumb")]
    if items and C.have_module("cv2") and contact_sheet(ctx, items, adir / "contact.jpg"):
        result["contact_sheet"] = rel(job, adir / "contact.jpg")
        ctx.use("opencv.contact_sheet")
    if no_transcribe:
        result["transcribe"] = "skipped (--no-transcribe)"
    result["tools_used"], result["missing"] = ctx.used, ctx.missing
    C.write(job, "analysis", result)
    return result


def main(argv=None) -> int:
    C.utf8_stdio()
    ap = argparse.ArgumentParser(prog="dragon_montage station analyze", description=__doc__)
    ap.add_argument("--job", required=True)
    ap.add_argument("--clip", action="append", required=True, help="input video (repeatable, in order)")
    ap.add_argument("--music")
    ap.add_argument("--no-transcribe", action="store_true")
    ap.add_argument("--whisper-model", default="small")
    ap.add_argument("--language", default="ar", help="whisper language code, or 'auto'")
    a = ap.parse_args(argv)
    for f in a.clip + ([a.music] if a.music else []):
        if not Path(f).is_file():
            ap.error(f"not found: {f}")
    res = analyze(a.job, a.clip, a.music, a.no_transcribe, a.whisper_model, a.language)
    print(json.dumps({"analysis": str(Path(a.job).resolve() / "analysis.json"), "clips": len(res["clips"]),
                      "shots": sum(len(c["shots"]) for c in res["clips"]),
                      "words": sum(len(c["words"]) for c in res["clips"]),
                      "bpm": res["music"]["bpm"], "missing": res["missing"]}, ensure_ascii=False))
    return 0
