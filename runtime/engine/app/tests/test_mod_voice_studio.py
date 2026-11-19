"""Parity: engines.voice_studio against the original kosif-voice-studio/scripts/voice_studio.py on the same inputs.
Offline only: word timings, SRT/VTT formatting, measured audio on synthetic WAVs, a fake VoiceStudio on loopback
(speak, transcribe, clone, design: same requests, same files, same receipts), and a real faster-whisper run on a
local Windows SAPI voice when both are already installed. edge-tts (network) is never called."""
import importlib.util, io, json, math, os, re, shutil, struct, subprocess, sys, threading, wave
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
OLD_PY = Path(r"C:\Users\cinde\kosif-tool\.claude\skills\kosif-voice-studio\scripts\voice_studio.py")
pytestmark = pytest.mark.skipif(not OLD_PY.is_file(), reason="original voice_studio.py not on this machine")

import engines.voice_studio as new  # noqa: E402
from engines.voice_studio.__main__ import main as new_main  # noqa: E402

HAS_FF = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))
need_ff = pytest.mark.skipif(not HAS_FF, reason="ffmpeg/ffprobe not installed")


@pytest.fixture(scope="module")
def old():
    spec = importlib.util.spec_from_file_location("old_voice_studio", OLD_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def tone_wav(seconds=0.6, amp=0.3, freq=440) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(b"".join(struct.pack("<h", int(amp * 32767 * math.sin(2 * math.pi * freq * i / 16000)))
                               for i in range(int(16000 * seconds))))
    return buf.getvalue()


def strip(obj, *dirs):
    """The same structure with each run directory replaced by a marker (paths are the only allowed difference)."""
    if isinstance(obj, str):
        for d in dirs:
            obj = obj.replace(json.dumps(str(d))[1:-1], "DIR").replace(str(d), "DIR")
        return obj
    text = json.dumps(obj, ensure_ascii=False)
    for d in dirs:
        text = text.replace(json.dumps(str(d))[1:-1], "DIR")
    return json.loads(text)


# ---------------------------------------------------------------- pure functions
EVENTS = [
    [{"type": "WordBoundary", "offset": 1_000_000, "duration": 5_875_000, "text": "أهلاً"},
     {"type": "WordBoundary", "offset": 5_000_000, "duration": 2_000_000, "text": "دي"},
     {"type": "SentenceBoundary", "offset": 0, "duration": 1, "text": "x"}],
    [{"type": "WordBoundary", "offset": 10_000_000, "duration": 9_000_000, "text": "أ"},
     {"type": "WordBoundary", "offset": 15_000_000, "duration": 1_000_000, "text": " ب "},
     {"type": "WordBoundary", "offset": 12_000_000, "duration": 1, "text": "  "},
     {"type": "WordBoundary", "offset": 3_333_333, "duration": 6_666_667, "text": "first"}],
    [],
]
SEGMENTS = [[{"start": 0.0, "end": 1.5, "text": "سلام"}, {"start": 61.0, "end": 62.0, "text": " تاني "}],
            [{"start": 3725.5, "end": 3726.0004, "text": "long"}, {"start": 0.0004999, "end": 0.0015, "text": "ms"}], []]


def test_pure_parity(old):
    for ev in EVENTS:
        assert old.edge_words(json.loads(json.dumps(ev))) == new.edge_words(json.loads(json.dumps(ev)))
    words = [{"word": "b", "start": 1.0, "end": 0.5}, {"word": "a", "start": 0.0, "end": 2}, {"word": "", "start": 0, "end": 1},
             {"word": "c", "start": 1.5, "end": 1.4}]
    assert old.clean_words(json.loads(json.dumps(words))) == new.clean_words(json.loads(json.dumps(words)))
    for sec in (0, 0.0005, 0.9995, 59.9999, 3599.9996, 3725.5, 86400.123, 1e-9):
        for sep in (",", "."):
            assert old.fmt_ts(sec, sep) == new.fmt_ts(sec, sep)
    for segs in SEGMENTS:
        for kind in ("srt", "vtt"):
            assert old.to_subtitles(segs, kind) == new.to_subtitles(segs, kind)
    for text in ("hello", "ازيك", "", None, "mixed كلام", "123"):
        assert old.lang_of(text) == new.lang_of(text)
    r = {"text": " صباح الفل ", "language": "ar", "segments": [{"start": 0, "end": "1.2", "text": " صباح "}, {}],
         "words": [{"word": "صباح", "start": 0, "end": 0.6}, {"word": "الفل", "start": "0.5", "end": 1.2}, {"word": " "}]}
    assert old.normalise_vs_transcript(json.loads(json.dumps(r))) == new.normalise_vs_transcript(json.loads(json.dumps(r)))
    assert old.normalise_vs_transcript({}) == new.normalise_vs_transcript({})
    assert old.INSTALL == new.INSTALL and old.EDGE_DEFAULT == new.EDGE_DEFAULT and old.PIPER_DIR == new.PIPER_DIR


def test_self_tests_pass():
    for cmd in ([sys.executable, str(OLD_PY), "--self-test"], [sys.executable, "-m", "engines.voice_studio", "--self-test"]):
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", cwd=ROOT, timeout=60,
                           env={**os.environ, "PYTHONIOENCODING": "utf-8"})
        assert r.returncode == 0 and "self-test: ok" in r.stdout, r.stderr


# ---------------------------------------------------------------- measured audio
def _outcome(fn, *a):
    try:
        return "ok", fn(*a)
    except Exception as e:  # the same failure class and message
        return type(e).__name__, str(e)


@need_ff
def test_verify_parity(old, tmp_path):
    files = {"tone.wav": tone_wav(), "silence.wav": tone_wav(amp=0.0), "short.wav": tone_wav(seconds=0.02),
             "صوت عربي.wav": tone_wav(1.2, 0.5, 220), "error.wav": b'{"detail": "model not installed"}', "empty.wav": b""}
    for name, data in files.items():
        p = tmp_path / name
        p.write_bytes(data)
        assert _outcome(old.verify_audio, p) == _outcome(new.verify_audio, p), name
    assert _outcome(old.verify_audio, tmp_path / "missing.wav") == _outcome(new.verify_audio, tmp_path / "missing.wav")


@need_ff
def test_to_format_parity(old, tmp_path):
    for ext in (".mp3", ".m4a", ".ogg", ".wav", ".flac"):
        res = []
        for side, mod in (("old", old), ("new", new)):
            d = tmp_path / side
            d.mkdir(exist_ok=True)
            src = d / "src.wav"
            src.write_bytes(tone_wav(1.0))
            out = d / f"out{ext}"
            kind, val = _outcome(mod.to_format, src, out)
            if kind == "ok":
                val = strip(mod.verify_audio(out), d)
                if ext == ".ogg":  # Ogg writes a random stream serial: same code, different bytes each run
                    val.pop("sha256")
            res.append((kind, val, src.exists()))
        assert res[0] == res[1], ext


# ---------------------------------------------------------------- a fake VoiceStudio on loopback (no real service)
class Fake(BaseHTTPRequestHandler):
    seen: list = []

    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == "/health":
            return self._send(200, {"status": "ok", "device": "cpu"})
        if self.path == "/openapi.json":
            return self._send(200, {"paths": {"/api/profiles": {"post": {}, "get": {}}, "/api/design/describe": {"post": {}},
                                              "/v1/audio/speech": {"post": {}}}})
        if self.path == "/v1/audio/voices":
            return self._send(200, {"voices": [{"id": "p1", "name": "King"}]})
        self._send(404, {"detail": "nope"})

    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        Fake.seen.append((self.path, self.headers.get("Content-Type", ""), body))
        if self.path == "/v1/audio/speech":
            return self._send(200, tone_wav(), "audio/wav")
        if self.path == "/v1/audio/transcriptions":
            return self._send(200, {"text": "صباح الفل يا جماعة", "language": "ar",
                                    "segments": [{"start": 0, "end": 1.2, "text": "صباح الفل"},
                                                 {"start": 1.2, "end": 3725.5, "text": " يا جماعة "}],
                                    "words": [{"word": "صباح", "start": 0.0, "end": 0.6}, {"word": "الفل", "start": 0.5, "end": 1.2},
                                              {"word": "يا", "start": 1.2, "end": 1.4}, {"word": "جماعة", "start": 1.4, "end": 2.0}]})
        if self.path == "/api/design/describe":
            desc = json.loads(body)["description"]
            if "robot" in desc:
                return self._send(200, {"attrs": {}, "instruct": "", "matched": [], "unmatched": ["robot"]})
            return self._send(200, {"attrs": {"Gender": "male", "Age": "elderly"}, "instruct": "male, elderly",
                                    "matched": [{"category": "Gender", "token": "male"}], "unmatched": []})
        if self.path == "/api/profiles":
            return self._send(200, {"id": "prof_1"})
        self._send(404, {"detail": "nope"})


@pytest.fixture(scope="module")
def url():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), Fake)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def both(old, tmp_path, capsys, args_for):
    """Run the old and new CLI in-process on their own folder; return [(exit, stdout, stderr, files, requests)]."""
    out = []
    for side, fn in (("old", old.main), ("new", new_main)):
        d = tmp_path / side
        d.mkdir(exist_ok=True)
        Fake.seen.clear()
        code = fn(args_for(d))
        cap = capsys.readouterr()
        files = {p.name: p.read_bytes() for p in sorted(d.iterdir()) if p.is_file()}
        reqs = [(p, re.sub(r"boundary=\w+", "B", c), re.sub(rb"--[0-9a-f]{32}", b"--B", b)) for p, c, b in Fake.seen]
        out.append([code, strip(cap.out, d), strip(cap.err, d)] + [{k: strip(v.decode("utf-8", "replace"), d) for k, v in files.items()}, reqs])
    return out


@need_ff
def test_speak_parity(old, url, tmp_path, capsys):
    a, b = both(old, tmp_path, capsys, lambda d: ["--url", url, "--json", "speak", "صباح الفل يا جماعة", "--engine",
                                                  "voicestudio", "--voice", "p1", "--out", str(d / "voice.mp3")])
    assert a == b and a[0] == 0 and "voice.mp3.receipt.json" in a[3]
    a, b = both(old, tmp_path, capsys, lambda d: ["--url", url, "speak", "   ", "--out", str(d / "x.wav")])
    assert a == b and a[0] == 2
    a, b = both(old, tmp_path, capsys, lambda d: ["--url", "http://127.0.0.1:9", "--json", "speak", "hi", "--engine",
                                                  "voicestudio", "--out", str(d / "x.wav")])
    assert a == b and a[0] == 1


@need_ff
@pytest.mark.parametrize("ext", [".srt", ".vtt", ".txt", ".json"])
def test_transcribe_parity(old, url, tmp_path, capsys, ext):
    src = tmp_path / "in put.wav"
    src.write_bytes(tone_wav())
    a, b = both(old, tmp_path, capsys, lambda d: ["--url", url, "--json", "transcribe", str(src), "--engine", "voicestudio",
                                                  "--out", str(d / f"نص{ext}")])
    assert a == b and a[0] == 0 and "words.json" in a[3]


@need_ff
def test_clone_and_design_parity(old, url, tmp_path, capsys):
    ref = tmp_path / "me.wav"
    ref.write_bytes(tone_wav())
    for args in (["clone", str(ref), "--name", "King"],
                 ["clone", str(ref), "--name", "King", "--ref-text", "النص المقروء", "--lang", "Arabic", "--i-own-this-voice"],
                 ["design", "old man, deep voice", "--name", "Grandpa"],
                 ["design", "old man, deep voice", "--name", "Grandpa", "--save"],
                 ["design", "a robot", "--name", "R", "--save"],
                 ["voices", "--engine", "voicestudio"], ["verify", str(ref)], ["verify", str(tmp_path / "nope.wav")]):
        a, b = both(old, tmp_path, capsys, lambda d: ["--url", url, "--json", *args])
        assert a == b, args


def test_doctor_and_piper_voices_parity(old, tmp_path, capsys, monkeypatch):
    dead = "http://127.0.0.1:9"
    assert old.doctor(old.VoiceStudio(dead)) == new.doctor(new.VoiceStudio(dead))
    for name in ("ar_JO-kareem-medium.onnx", "en_US-amy-low.onnx", "notes.txt"):
        (tmp_path / name).write_bytes(b"x")
    monkeypatch.setattr(old, "PIPER_DIR", tmp_path)
    monkeypatch.setattr(new, "PIPER_DIR", tmp_path)
    assert old.doctor(old.VoiceStudio(dead)) == new.doctor(new.VoiceStudio(dead))
    a, b = both(old, tmp_path, capsys, lambda d: ["--json", "voices", "--engine", "piper"])
    assert a == b and json.loads(a[1]) == ["ar_JO-kareem-medium", "en_US-amy-low"]


# ---------------------------------------------------------------- real offline transcription (only if installed)
def _whisper_ready():
    if not (HAS_FF and importlib.util.find_spec("faster_whisper") and sys.platform == "win32"):
        return False
    hub = Path(os.environ.get("HF_HOME", Path.home() / ".cache" / "huggingface")) / "hub"
    return (hub / "models--Systran--faster-whisper-small").is_dir()


@pytest.mark.skipif(not _whisper_ready(), reason="faster-whisper small model / ffmpeg / Windows SAPI not available")
def test_whisper_srt_parity(old, tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    wav = tmp_path / "speech.wav"
    ps = ("Add-Type -AssemblyName System.Speech; $s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
          f"$s.SetOutputToWaveFile('{wav}'); $s.Speak('The black dragon reads every word, then writes the subtitles.'); $s.Dispose()")
    r = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, timeout=60)
    if r.returncode or not wav.is_file():
        pytest.skip("Windows SAPI voice unavailable")
    a, b = both(old, tmp_path, capsys, lambda d: ["--json", "transcribe", str(wav), "--engine", "whisper", "--model", "small",
                                                  "--lang", "en", "--out", str(d / "speech.srt")])
    assert a == b and a[0] == 0, (a[:3], b[:3])
    assert "dragon" in a[3]["speech.srt"].lower() and json.loads(a[3]["words.json"])
