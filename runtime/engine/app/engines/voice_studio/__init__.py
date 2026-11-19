"""Voice studio: speech with word timings, voice cloning and design, transcription to JSON/SRT/VTT/TXT, measured audio.

Engines (auto order: voicestudio > edge > piper for speech; voicestudio > whisper for listening):
  voicestudio  a running VoiceStudio app over HTTP (backend.py): speak, clone, design, transcribe
  edge         edge-tts: free, online, no key; Egyptian voices and word timings
  piper        piper-tts: offline CPU speech with a downloaded .onnx voice
  whisper      faster-whisper: offline transcription with word timings (fed a 16 kHz array decoded by ffmpeg)
Never reports audio it did not measure; a failed engine is reported, never hidden. Cloning needs consent."""
import asyncio
import hashlib
import importlib.util
import json
import os
import re
import shutil
import ssl
import subprocess
import sys
import tempfile
from pathlib import Path

from ..media import exe
from .backend import PRESETS, Fail, VoiceStudio

INSTALL_ = PRESETS["install"]
EDGE_DEFAULT, PIPER_DEFAULT = PRESETS["edge_default"], PRESETS["piper_default"]
PIPER_DIR = Path(os.environ.get("PIPER_VOICES_DIR", Path(PRESETS["piper_dir"]).expanduser()))
INSTALL = {**INSTALL_, "piper": INSTALL_["piper"].format(piper_dir=PIPER_DIR, piper_voice=PIPER_DEFAULT)}
ARABIC = re.compile(r"[؀-ۿ]")


# ---------------------------------------------------------------- helpers
def has_module(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def tool(name: str):
    """Full path of ffmpeg/ffprobe (PATH or WinGet), or None."""
    try:
        return exe(name)
    except FileNotFoundError:
        return None


def lang_of(text: str) -> str:
    return "ar" if ARABIC.search(text or "") else "en"


def sha256(path: Path) -> str:
    with open(path, "rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def ca_context():
    """Honour a corporate/proxy CA bundle when the user set one (SSL_CERT_FILE or REQUESTS_CA_BUNDLE)."""
    for var in ("SSL_CERT_FILE", "REQUESTS_CA_BUNDLE"):
        path = os.environ.get(var)
        if path and Path(path).is_file():
            return ssl.create_default_context(cafile=path)
    return None


def ticks_to_s(t: int) -> float:  # edge-tts offsets are 100 ns ticks
    return round(t / 10_000_000, 3)


def clean_words(words: list) -> list:
    """Sorted, non-overlapping [{word,start,end}]."""
    words = sorted((w for w in words if str(w.get("word", "")).strip()), key=lambda w: w["start"])
    for a, b in zip(words, words[1:]):
        a["end"] = min(a["end"], b["start"])
    for w in words:
        w["end"] = max(w["end"], w["start"])
    return words


def edge_words(events: list) -> list:
    out = []
    for e in events:
        if e.get("type") == "WordBoundary" and str(e.get("text", "")).strip():
            start = ticks_to_s(int(e["offset"]))
            out.append({"word": e["text"].strip(), "start": start, "end": round(start + ticks_to_s(int(e["duration"])), 3)})
    return clean_words(out)


def fmt_ts(sec: float, sep: str) -> str:
    h, ms = divmod(int(round(sec * 1000)), 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d}{sep}{ms:03d}"


def to_subtitles(segments: list, kind: str) -> str:
    """SRT or VTT text from [{start,end,text}]."""
    sep = "," if kind == "srt" else "."
    lines = ["WEBVTT", ""] if kind == "vtt" else []
    for i, s in enumerate(segments, 1):
        lines += ([str(i)] if kind == "srt" else []) + [f"{fmt_ts(s['start'], sep)} --> {fmt_ts(s['end'], sep)}", s["text"].strip(), ""]
    return "\n".join(lines)


def _write_json(path: Path, obj, indent=1):
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=indent), encoding="utf-8")


# ---------------------------------------------------------------- measuring
def verify_audio(path) -> dict:
    """Measured duration, codec, sample rate, channels, sha256 and mean loudness; ok = long enough and not silent."""
    path = Path(path)
    if not path.is_file() or path.stat().st_size == 0:
        raise Fail(f"no audio at {path} (missing or empty)")
    probe = tool("ffprobe")
    if not probe:
        raise Fail("ffprobe not found; " + INSTALL["ffmpeg"])
    p = subprocess.run([probe, "-v", "error", "-select_streams", "a:0", "-show_entries",
                        "stream=codec_name,sample_rate,channels:format=duration", "-of", "json", str(path)],
                       capture_output=True, text=True)
    info = json.loads(p.stdout or "{}")
    streams = info.get("streams") or []
    if p.returncode or not streams:
        head = path.read_bytes()[:200].decode("utf-8", "replace")
        raise Fail(f"{path} is not audio (ffprobe found no audio stream); first bytes: {head!r}")
    st, dur = streams[0], float(info.get("format", {}).get("duration") or 0)
    rep = {"path": str(path), "bytes": path.stat().st_size, "sha256": sha256(path), "codec": st.get("codec_name"),
           "sample_rate": int(st.get("sample_rate") or 0), "channels": st.get("channels"), "duration_s": round(dur, 3)}
    ff = tool("ffmpeg")
    if ff:
        v = subprocess.run([ff, "-hide_banner", "-nostats", "-i", str(path), "-af", "volumedetect", "-f", "null", "-"],
                           capture_output=True, text=True)
        m = re.search(r"mean_volume:\s*(-?[\d.]+|-inf) dB", v.stderr)
        if m:
            rep["mean_volume_db"] = -999.0 if m.group(1) == "-inf" else float(m.group(1))
    lim = PRESETS["verify"]
    rep["ok"] = dur > lim["min_duration_s"] and rep.get("mean_volume_db", 0.0) > lim["min_mean_db"]
    if not rep["ok"]:
        rep["problem"] = "too short or silent"
    return rep


def to_format(src: Path, out: Path) -> None:
    """Re-encode src into out's extension (wav/mp3/ogg/m4a); same extension = move."""
    if src.suffix.lower() == out.suffix.lower():
        shutil.move(str(src), out)
        return
    ff = tool("ffmpeg")
    if not ff:
        raise Fail("ffmpeg needed to write " + out.suffix + "; " + INSTALL["ffmpeg"])
    codec = PRESETS["codecs"].get(out.suffix.lower())
    if codec is None:
        raise Fail(f"unsupported output extension {out.suffix} (use .wav .mp3 .m4a .ogg)", 2)
    subprocess.run([ff, "-v", "error", "-y", "-i", str(src), *codec, str(out)], check=True)
    src.unlink(missing_ok=True)


# ---------------------------------------------------------------- local engines
def _edge(ctx_mods=()):
    if not has_module("edge_tts"):
        raise Fail("edge-tts not installed; " + INSTALL["edge"])
    import edge_tts
    ctx = ca_context()
    if ctx is not None:  # the library pins certifi; use the CA bundle the user configured
        for name in ("edge_tts.communicate", *ctx_mods):
            importlib.import_module(name)._SSL_CTX = ctx
    return edge_tts


def edge_speak(text: str, out: Path, voice, rate: str) -> list:
    edge_tts = _edge()
    voice = voice or EDGE_DEFAULT[lang_of(text)]
    events = []

    async def run():
        c = edge_tts.Communicate(text, voice, rate=rate, boundary="WordBoundary")
        with open(out, "wb") as f:
            async for ch in c.stream():
                f.write(ch["data"]) if ch["type"] == "audio" else events.append(ch)
    try:
        asyncio.run(run())
    except Exception as e:  # network, bad voice name, service change
        raise Fail(f"edge-tts failed ({type(e).__name__}: {str(e)[:200]})")
    return edge_words(events)


def piper_model(voice) -> Path:
    v = voice or PIPER_DEFAULT
    if Path(v).suffix == ".onnx" and Path(v).is_file():
        return Path(v)
    cand = PIPER_DIR / f"{v}.onnx"
    if cand.is_file():
        return cand
    raise Fail(f"piper voice {v} not downloaded; {INSTALL['piper']}")


def piper_speak(text: str, out_wav: Path, voice) -> None:
    if not has_module("piper"):
        raise Fail("piper-tts not installed; " + INSTALL["piper"])
    p = subprocess.run([sys.executable, "-m", "piper", "-m", str(piper_model(voice)), "-f", str(out_wav)],
                       input=text, capture_output=True, text=True, encoding="utf-8")
    if p.returncode:
        raise Fail("piper failed: " + p.stderr.strip()[-300:])


def voices(engine: str = "edge", lang=None, vs=None):
    if engine == "voicestudio":
        return (vs or VoiceStudio()).voices()
    if engine == "piper":
        return sorted(p.stem for p in PIPER_DIR.glob("*.onnx"))
    edge_tts = _edge(("edge_tts.voices",))
    rows = [{"voice": v["ShortName"], "locale": v["Locale"], "gender": v["Gender"]} for v in asyncio.run(edge_tts.list_voices())]
    return [r for r in rows if not lang or r["locale"].lower().startswith(lang.lower())]


def pcm16k(audio: Path):
    """Mono float32 samples at 16 kHz, decoded by ffmpeg (faster-whisper's own decoder clashes with some PyAV builds)."""
    import wave
    import numpy as np
    ff = tool("ffmpeg")
    if not ff:
        raise Fail("ffmpeg needed for transcription; " + INSTALL["ffmpeg"])
    with tempfile.TemporaryDirectory() as td:
        wav = Path(td) / "a.wav"
        subprocess.run([ff, "-v", "error", "-y", "-i", str(audio), "-ar", "16000", "-ac", "1", str(wav)], check=True)
        with wave.open(str(wav)) as w:
            return np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768


def whisper_transcribe(audio: Path, model: str, lang) -> dict:
    if not has_module("faster_whisper"):
        raise Fail("faster-whisper not installed; " + INSTALL["whisper"])
    pcm = pcm16k(audio)
    from faster_whisper import WhisperModel
    segs, info = WhisperModel(model, device="cpu", compute_type="int8").transcribe(pcm, language=lang, word_timestamps=True)
    segments, words = [], []
    for s in segs:
        segments.append({"start": round(float(s.start), 3), "end": round(float(s.end), 3), "text": s.text.strip()})
        words += [{"word": w.word.strip(), "start": round(float(w.start), 3), "end": round(float(w.end), 3)} for w in s.words or []]
    return {"engine": "whisper", "model": model, "language": info.language,
            "text": " ".join(s["text"] for s in segments).strip(), "segments": segments, "words": clean_words(words)}


def normalise_vs_transcript(r: dict) -> dict:
    segs = [{"start": float(s.get("start", 0)), "end": float(s.get("end", 0)), "text": str(s.get("text", "")).strip()}
            for s in (r.get("segments") or [])]
    words = [{"word": str(w.get("word", "")).strip(), "start": float(w.get("start", 0)), "end": float(w.get("end", 0))}
             for w in (r.get("words") or [])]
    return {"engine": "voicestudio", "language": r.get("language"), "text": (r.get("text") or "").strip(),
            "segments": segs, "words": clean_words(words)}


# ---------------------------------------------------------------- doctor
def doctor(vs=None) -> dict:
    """What can run on this machine, and the install line for the rest."""
    vs = vs or VoiceStudio()
    try:
        vs_info, vs_ok = vs.health(), True
    except Fail as e:
        vs_info, vs_ok = str(e), False
    try:
        piper_voice = str(piper_model(None))
    except Fail:
        piper_voice = None
    ff = bool(tool("ffmpeg") and tool("ffprobe"))
    has = {"edge": has_module("edge_tts"), "piper": has_module("piper") and piper_voice is not None,
           "whisper": has_module("faster_whisper")}
    can = PRESETS["can"]
    rows = {"voicestudio": {"ready": vs_ok, "url": vs.url, "detail": vs_info if vs_ok else None, "can": can["voicestudio"],
                            "install": None if vs_ok else INSTALL["voicestudio"]},
            "edge": {"ready": has["edge"], "can": can["edge"], "install": None if has["edge"] else INSTALL["edge"]},
            "piper": {"ready": has["piper"], "voice": piper_voice, "can": can["piper"],
                      "install": None if has["piper"] else INSTALL["piper"]},
            "whisper": {"ready": has["whisper"], "can": can["whisper"], "install": None if has["whisper"] else INSTALL["whisper"]},
            "ffmpeg": {"ready": ff, "can": can["ffmpeg"], "install": None if tool("ffmpeg") else INSTALL["ffmpeg"]}}
    return {"engines": rows, "speak_order": [e for e in PRESETS["speak_order"] if rows[e]["ready"]],
            "transcribe_order": [e for e in PRESETS["transcribe_order"] if rows[e]["ready"]],
            "clone_and_design": "voicestudio" if vs_ok else PRESETS["no_clone"]}


# ---------------------------------------------------------------- commands
def speak(text: str, out, engine: str = "auto", voice=None, rate: str = "+0%", words=None, vs=None) -> dict:
    """Text to speech; writes OUT, OUT.receipt.json and (with word timings) words.json. Returns the receipt."""
    text = (text or "").strip()
    if not text:
        raise Fail("nothing to say: give TEXT or --file", 2)
    vs, out = vs or VoiceStudio(), Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    errors = {}
    for eng in [engine] if engine != "auto" else PRESETS["speak_order"]:
        tmp = out.with_name(out.stem + f".{eng}.tmp" + (".mp3" if eng == "edge" else ".wav"))
        try:
            got = []
            if eng == "voicestudio":
                if engine == "auto" and not vs.up():
                    raise Fail("not running")
                vs.speak(text, tmp, voice)
            elif eng == "edge":
                got = edge_speak(text, tmp, voice, rate)
            elif eng == "piper":
                piper_speak(text, tmp, voice)
            else:
                raise Fail(f"unknown engine {eng}", 2)
            verify_audio(tmp)
            to_format(tmp, out)
            rep = verify_audio(out)
            if not rep["ok"]:
                raise Fail(f"{eng} produced unusable audio: {rep.get('problem')}")
            default = {"edge": EDGE_DEFAULT[lang_of(text)], "piper": PIPER_DEFAULT}.get(eng, PRESETS["voicestudio_voice"])
            receipt = {"kind": PRESETS["receipt_kind"], "command": "speak", "engine": eng, "voice": voice or default,
                       "chars": len(text), "audio": rep, "skipped": errors}
            if got:
                wpath = Path(words) if words else out.with_name("words.json")
                _write_json(wpath, got)
                receipt["words_json"] = {"path": str(wpath), "count": len(got)}
            _write_json(Path(str(out) + ".receipt.json"), receipt, indent=2)
            return receipt
        except Fail as e:
            errors[eng] = str(e)
            tmp.unlink(missing_ok=True)
            if engine != "auto":
                raise
    raise Fail("no speech engine worked: " + json.dumps(errors, ensure_ascii=False))


def transcribe(audio, out, engine: str = "auto", model: str = "small", lang=None, words=None, vs=None) -> dict:
    """Audio to OUT (.json/.srt/.vtt/.txt by extension) plus words.json. Returns a short report."""
    audio, vs = Path(audio), vs or VoiceStudio()
    verify_audio(audio)
    errors, res = {}, None
    for eng in [engine] if engine != "auto" else PRESETS["transcribe_order"]:
        try:
            if eng == "voicestudio":
                if engine == "auto" and not vs.up():
                    raise Fail("not running")
                res = normalise_vs_transcript(vs.transcribe(audio))
            elif eng == "whisper":
                res = whisper_transcribe(audio, model, lang)
            else:
                raise Fail(f"unknown engine {eng}", 2)
            break
        except Fail as e:
            errors[eng] = str(e)
            if engine != "auto":
                raise
    if res is None:
        raise Fail("no transcription engine worked: " + json.dumps(errors, ensure_ascii=False))
    if not res["text"]:
        raise Fail(f"{res['engine']} returned an empty transcript (silence, music only, or wrong --lang)")
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    ext = out.suffix.lower()
    if ext in (".srt", ".vtt"):
        out.write_text(to_subtitles(res["segments"], ext[1:]), encoding="utf-8")
    elif ext == ".txt":
        out.write_text(res["text"] + "\n", encoding="utf-8")
    else:
        _write_json(out, res)
    if res["words"]:
        _write_json(Path(words) if words else out.with_name("words.json"), res["words"])
    return {"engine": res["engine"], "language": res.get("language"), "out": str(out), "segments": len(res["segments"]),
            "words": len(res["words"]), "preview": res["text"][:160], "skipped": errors}


def clone(ref, name: str, ref_text: str = "", lang: str = "Auto", consent: bool = False, vs=None) -> dict:
    """VoiceStudio clone; needs consent (the voice is the user's own or the speaker agreed)."""
    if not consent:
        raise Fail("cloning needs --i-own-this-voice: the voice is the user's own or the speaker consented", 2)
    verify_audio(Path(ref))
    return (vs or VoiceStudio()).clone(Path(ref), name, ref_text, lang)


def design(description: str, name: str, save: bool = False, vs=None) -> dict:
    vs = vs or VoiceStudio()
    return vs.design(description, name) if save else vs.describe(description)
