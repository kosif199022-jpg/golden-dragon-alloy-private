"""What can this machine really run? Programs on PATH (or in their usual install folders) and Python modules."""
import importlib.util, os, shutil
from pathlib import Path

PROGRAMS = {
    "ffmpeg": "video/audio engine", "ffprobe": "media measurement", "node": "HTML/Remotion render",
    "blender": "3D", "magick": "image compositing", "tesseract": "OCR", "exiftool": "metadata",
    "aria2c": "parallel downloads", "yt-dlp": "video download", "git": "repos",
    "upscayl-bin": "AI upscale 4x", "rembg": "background removal", "inkscape": "vector / SVG",
    "gimp-console-3.2": "raster editing", "melt": "Kdenlive render", "mkvmerge": "MKV mux",
    "deep-filter": "voice denoise", "whisperx": "word alignment CLI", "demucs": "stem split CLI",
    "scenedetect": "shot detection CLI", "auto-editor": "silence cut CLI", "pandoc": "documents", "7z": "archives",
}
MODULES = {
    "numpy": "core", "PIL": "images", "cv2": "vision", "librosa": "beats", "soundfile": "audio io",
    "faster_whisper": "speech timing", "whisperx": "word alignment", "demucs": "stems", "pyloudnorm": "LUFS",
    "arabic_reshaper": "Arabic shaping", "bidi": "RTL", "rembg": "background removal", "mediapipe": "face/pose",
    "sam2": "video masks", "scenedetect": "shot detection", "auto_editor": "silence cut",
}
PF = os.environ.get("ProgramFiles", r"C:\Program Files")
EXTRA_DIRS = [rf"{PF}\Blender Foundation", rf"{PF}\Tesseract-OCR", rf"{PF}\ImageMagick*", rf"{PF}\Upscayl\resources\bin",
              rf"{PF}\Inkscape\bin", rf"{PF}\GIMP*", rf"{PF}\7-Zip", rf"{PF}\MKVToolNix", rf"{PF}\Pandoc",
              rf"{PF}\kdenlive*", os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Packages")]


def find_program(name):
    p = shutil.which(name)
    if p:
        return p
    for d in EXTRA_DIRS:
        for base in Path(d).parent.glob(Path(d).name) if "*" in d else [Path(d)]:
            if base.exists():
                hit = next(base.rglob(f"{name}.exe"), None)
                if hit:
                    return str(hit)
    return None


def check():
    progs = {n: find_program(n) for n in PROGRAMS}
    mods = {n: importlib.util.find_spec(n) is not None for n in MODULES}
    return progs, mods
