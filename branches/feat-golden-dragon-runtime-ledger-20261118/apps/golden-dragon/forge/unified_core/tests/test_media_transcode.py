"""Real, confined FFmpeg media conversion tests; never touch user input files."""
import hashlib
import importlib.util
from pathlib import Path
import shutil
import subprocess
import tempfile
import wave

import pytest

p = Path(__file__).resolve().parent.parent / "runtime.py"
spec = importlib.util.spec_from_file_location("gd_runtime_transcode", p)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def _wav(path):
    with wave.open(str(path), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(16000)
        f.writeframes(b"\x00\x00" * 16000)


def test_missing_input_or_bad_profile_fails(tmp_path):
    with pytest.raises(ValueError, match="existing local"):
        mod.transcode_media(tmp_path / "not.mp4")
    source = tmp_path / "source.wav"
    _wav(source)
    with pytest.raises(ValueError, match="unsupported media profile"):
        mod.transcode_media(source, profile="arbitrary_shell_code")


def test_real_audio_conversion_preserves_original(tmp_path):
    if not mod.shutil.which("ffmpeg") or not mod.shutil.which("ffprobe"):
        pytest.skip("FFmpeg/FFprobe not available")
    source = tmp_path / "tone.wav"
    _wav(source)
    original_sha = hashlib.sha256(source.read_bytes()).hexdigest()
    result = None
    try:
        result = mod.GoldenDragonCore(tmp_path, media=source, profile="mp3").execute("media.transcode")["result"]
        output = Path(result["output"])
        assert output.is_file()
        assert output.is_relative_to(Path(tempfile.gettempdir()).resolve())
        assert output.suffix == ".mp3"
        assert result["transcode_performed"]
        assert result["original_overwritten"] is False
        assert result["metadata"]["streams"][0]["type"] == "audio"
        assert hashlib.sha256(source.read_bytes()).hexdigest() == original_sha
    finally:
        if result:
            shutil.rmtree(Path(result["output"]).parent)


def test_real_video_and_audio_mp4_conversion(tmp_path):
    ffmpeg = mod.shutil.which("ffmpeg")
    if not ffmpeg or not mod.shutil.which("ffprobe"):
        pytest.skip("FFmpeg/FFprobe not available")
    source = tmp_path / "sample.mp4"
    creation = [
        ffmpeg, "-nostdin", "-hide_banner", "-v", "error",
        "-f", "lavfi", "-i", "testsrc=size=192x108:rate=24",
        "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=44100",
        "-t", "1", "-c:v", "mpeg4", "-c:a", "aac",
        "-y", str(source),
    ]
    subprocess.run(creation, check=True, timeout=20)
    result = None
    try:
        result = mod.transcode_media(source, profile="mp4-compatible")
        out = result["metadata"]
        assert result["output"] != str(source)
        assert any(s["type"] == "video" and s["width"] == 192 for s in out["streams"])
        assert any(s["type"] == "audio" for s in out["streams"])
        assert source.is_file()
    finally:
        if result:
            shutil.rmtree(Path(result["output"]).parent)
