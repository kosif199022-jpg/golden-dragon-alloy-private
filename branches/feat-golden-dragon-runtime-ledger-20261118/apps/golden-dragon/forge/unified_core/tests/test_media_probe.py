"""FFprobe native engine tests: explicit inputs, no shell/network execution."""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import wave

import pytest

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("gd_runtime_media", ROOT / "runtime.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def test_rejects_network_and_missing_local_media(tmp_path):
    with pytest.raises(ValueError, match="existing local"):
        mod.inspect_media("https://example.com/movie.mp4")
    with pytest.raises(ValueError, match="existing local"):
        mod.inspect_media(tmp_path / "not-here.mp4")
    bogus = tmp_path / "a.txt"
    bogus.write_bytes(b"not media")
    with pytest.raises(ValueError, match="existing local"):
        mod.inspect_media(bogus)


def test_executes_ffprobe_using_array_without_shell(tmp_path, monkeypatch):
    path = tmp_path / "sample.wav"
    path.write_bytes(b"sample")
    args_seen = []

    def fake_run(args, **kwargs):
        args_seen.extend(args)
        assert kwargs["shell"] is False
        assert kwargs["timeout"] == 30
        assert kwargs["check"] is False
        return SimpleNamespace(
            returncode=0,
            stdout=json.dumps({
                "format": {"format_name": "wav", "duration": "2.5"},
                "streams": [{"index": 0, "codec_type": "audio",
                             "codec_name": "pcm_s16le", "sample_rate": "8000",
                             "channels": 1}],
            }).encode("utf-8"),
            stderr=b"",
        )

    monkeypatch.setattr(mod.shutil, "which", lambda _: "/bin/mock-ffprobe")
    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    core = mod.GoldenDragonCore(tmp_path, media=path)
    result = core.execute("media.probe")["result"]
    assert result["ffprobe_executed"]
    assert result["transcode_performed"] is False
    assert result["duration_seconds"] == 2.5
    assert result["streams"][0]["channels"] == 1
    assert "-protocol_whitelist" in args_seen
    assert args_seen[args_seen.index("-protocol_whitelist")+1] == "file,pipe"


def test_missing_ffprobe_fails_closed(tmp_path, monkeypatch):
    path = tmp_path / "a.mp4"
    path.write_bytes(b"a")
    monkeypatch.setattr(mod.shutil, "which", lambda _: None)
    with pytest.raises(ValueError, match="ffprobe is not installed"):
        mod.inspect_media(path)


def test_timeout_is_reported(tmp_path, monkeypatch):
    path = tmp_path / "a.mp4"
    path.write_bytes(b"a")
    monkeypatch.setattr(mod.shutil, "which", lambda _: "/bin/mock")
    def fail(*_, **__):
        raise mod.subprocess.TimeoutExpired(cmd=["ffprobe"], timeout=30)
    monkeypatch.setattr(mod.subprocess, "run", fail)
    with pytest.raises(ValueError, match="timed out"):
        mod.inspect_media(path)


def test_real_ffprobe_local_wav(tmp_path):
    """Integration test; skip cleanly when FFprobe is not installed."""
    if not mod.shutil.which("ffprobe"):
        pytest.skip("FFprobe is not available")
    path = tmp_path / "tone.wav"
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(8000)
        wav.writeframes(b"\x00\x00" * 8000)
    data = mod.inspect_media(path)
    assert data["ffprobe_executed"]
    assert data["streams"][0]["codec"] == "pcm_s16le"
    assert data["duration_seconds"] == pytest.approx(1.0, abs=0.01)
