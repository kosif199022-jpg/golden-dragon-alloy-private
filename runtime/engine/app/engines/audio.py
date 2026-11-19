"""Audio engine: WAV conversion, beat grid, sung/spoken words with timings, and the film mix
(song section + voices, song ducks under the voice, padded to the film length, normalised loudness)."""
import json
from pathlib import Path
from .media import ffmpeg


def to_wav(src, dst=None, sr=48000):
    """librosa/soundfile cannot read m4a/aac: convert once to WAV."""
    dst = Path(dst or Path(src).with_suffix(".wav"))
    ffmpeg("-i", src, "-ac", "2", "-ar", sr, dst)
    return dst


def beats(path):
    """{'tempo', 'beats': [s...], 'duration'} from librosa's beat tracker."""
    import librosa, numpy as np
    y, sr = librosa.load(str(path), sr=22050, mono=True)
    tempo, frames = librosa.beat.beat_track(y=y, sr=sr)
    return {"duration": round(len(y) / sr, 3), "tempo": round(float(np.atleast_1d(tempo)[0]), 2),
            "beats": [round(float(t), 3) for t in librosa.frames_to_time(frames, sr=sr)]}


MODEL_SIZES = {"tiny": "75 MB", "base": "145 MB", "small": "480 MB", "medium": "1.5 GB", "large-v2": "3 GB",
               "large-v3": "3 GB", "large": "3 GB", "large-v3-turbo": "1.6 GB"}


class ModelNotCached(RuntimeError):
    """The faster-whisper model is not on this machine: downloading it needs the owner's yes (size, network, disk)."""


FALLBACK_ORDER = ("large-v3-turbo", "small", "large-v3", "medium", "base", "tiny")  # v10.8


def load_model(model="small", threads=0, local_only=True):
    """WhisperModel from the local cache only (v1.3): no silent download from the HF Hub on a tight disk.
    v10.8: when the asked model is not cached, use another model that IS cached (one stderr line says which), so a
    transcription no longer dies in the background («Transcribe Arabic audio with Whisper failed», 2026-11-06)."""
    import sys
    from faster_whisper import WhisperModel
    first_error = None
    for name in (model,) + tuple(m for m in FALLBACK_ORDER if m != model):
        try:
            wm = WhisperModel(name, device="cpu", compute_type="int8", cpu_threads=int(threads or 0),
                              local_files_only=local_only)
        except MemoryError:
            raise MemoryError(f"not enough free RAM to load whisper '{name}': close other programs or use --model small")
        except Exception as e:  # noqa: BLE001 - huggingface_hub raises several types for "not in the cache"
            if not local_only:
                raise
            first_error = first_error or e
            continue
        if name != model:
            print(f"note: whisper '{model}' is not cached here; using the cached '{name}' instead "
                  f"(add --download to fetch '{model}', about {MODEL_SIZES.get(model, 'several hundred MB')})",
                  file=sys.stderr)
        return wm
    raise ModelNotCached(f"no faster-whisper model is cached here (asked '{model}'); downloading it takes about "
                         f"{MODEL_SIZES.get(model, 'several hundred MB')} of network and disk: needs yes "
                         f"(then run again with --download). ({type(first_error).__name__})") from None


def words(path, language="ar", model="small", offset=0.0, duration=None, vad=True, threads=0, download=False):
    """Lines with word timings (faster-whisper). Audio goes in as a 16 kHz array: the library's own decoder breaks
    with some PyAV builds (`metadata_errors`). MP4/M4A/AAC/MP3 are converted to a 16 kHz WAV first (librosa cannot
    read them). The model comes from the local cache only unless download=True (the owner said yes)."""
    import librosa
    import tempfile
    wm = load_model(model, threads, local_only=not download)
    src, tmp = Path(path), None
    if src.suffix.lower() not in (".wav", ".flac"):
        tmp = Path(tempfile.mkdtemp(prefix="dragon_words_")) / "a.wav"
        to_wav(src, tmp, 16000)
        src = tmp
    try:
        audio, _ = librosa.load(str(src), sr=16000, mono=True, offset=offset, duration=duration)
    finally:
        if tmp:
            tmp.unlink(missing_ok=True)
            tmp.parent.rmdir()
    segs, _ = wm.transcribe(
        audio, language=language, word_timestamps=True, vad_filter=vad, condition_on_previous_text=False)
    return [{"start": round(s.start + offset, 2), "end": round(s.end + offset, 2), "text": s.text.strip(),
             "words": [{"w": w.word.strip(), "s": round(w.start + offset, 2), "e": round(w.end + offset, 2)} for w in (s.words or [])]}
            for s in segs]


def mix_graph(n_voices, dur, song_gain=1.0, fade_in=0.4, fade_out=2.5, song_at=0.0, voices=(), lufs=-14):
    """filter_complex for input 0 = song section, inputs 1..n = voice clips. Returns the graph text."""
    delay = int(song_at * 1000)
    f = [f"[0:a]aformat=sample_rates=48000:channel_layouts=stereo,volume={song_gain},afade=t=in:d={fade_in},"
         f"afade=t=out:st={dur - fade_out - song_at:.3f}:d={fade_out},adelay={delay}|{delay}[song]"]
    labels = []
    for k, v in enumerate(voices, start=1):
        dl = int(v["at"] * 1000)
        f.append(f"[{k}:a]aformat=sample_rates=48000:channel_layouts=stereo,volume={v.get('gain', 1.0)},"
                 f"afade=t=in:d=0.15,afade=t=out:st={v['d'] - 0.4:.3f}:d=0.4,adelay={dl}|{dl}[v{k}]")
        labels.append(f"[v{k}]")
    tail = f"atrim=0:{dur:.3f},loudnorm=I={lufs}:TP=-1.5:LRA=11[out]"  # TP -1.5 like deliver.LOUDNORM (v1.2)
    if labels:
        # pad the voice bus to the full film: sidechaincompress stops at its shortest input (the film-2 bug)
        f.append(f"{''.join(labels)}amix=inputs={len(labels)}:normalize=0:duration=longest,apad=whole_dur={dur:.3f},asplit[vox][voxsc]")
        f.append("[song][voxsc]sidechaincompress=threshold=0.015:ratio=10:attack=15:release=450:makeup=1[songd]")
        f.append(f"[songd][vox]amix=inputs=2:normalize=0:duration=longest,{tail}")
    else:
        f.append(f"[song]{tail}")
    return ";".join(f)


def mix(song, start, dur, out, voices=(), **kw):
    """song section [start, start+dur] + voices [{src, in, d, at, gain}] -> 24-bit WAV of exactly `dur` seconds."""
    inputs = ["-ss", start, "-t", f"{dur + 0.5:.3f}", "-i", song]
    for v in voices:
        inputs += ["-ss", v["in"], "-t", v["d"], "-i", v["src"]]
    graph = mix_graph(len(voices), dur, voices=voices, **kw)
    ffmpeg(*inputs, "-filter_complex", graph, "-map", "[out]", "-ar", 48000, "-c:a", "pcm_s24le", out)
    return Path(out)


def save(obj, path):
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
    return Path(path)
