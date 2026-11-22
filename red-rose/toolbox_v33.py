"""Red Rose toolbox: the outside programs, Python libraries, repos and fonts on this PC.

Red Rose stays able to run without any of them. This module only finds them and says
what each is for, so an agent picks a real installed tool instead of guessing.
Nothing here runs a tool, installs anything or touches the network.

    rose.py toolbox                     everything, with ready / missing
    rose.py toolbox --domain montage    one domain
    rose.py toolbox --find "كلمات"      search by Arabic or English words
    rose.py toolbox --missing           only what is not installed
"""
from __future__ import annotations

import glob
import importlib.util
import os
import shutil
from pathlib import Path

HOME = Path.home()
REPOS = HOME / 'dragon-repos'
FONTS = HOME / '.red-rose' / 'fonts'
_LOCAL = os.environ.get('LOCALAPPDATA', str(HOME / 'AppData' / 'Local'))

# extra places to look when a program is installed but not on this process's PATH
_FALLBACK = {
    '7z': [r'C:\Program Files\7-Zip\7z.exe'],
    'sox': [_LOCAL + r'\Microsoft\WinGet\Packages\ChrisBagwell.SoX*\**\sox.exe'],
    'HandBrakeCLI': [_LOCAL + r'\Microsoft\WinGet\Packages\HandBrake.HandBrake.CLI*\**\HandBrakeCLI.exe'],
    'inkscape': [r'C:\Program Files\Inkscape\bin\inkscape.exe'],
    'deep-filter': [str(HOME / 'dragon-tools' / 'bin' / 'deep-filter.exe')],
    'rife-ncnn-vulkan': [str(HOME / 'dragon-tools' / 'rife_x' / '**' / 'rife-ncnn-vulkan.exe')],
    'blender': [r'C:\Program Files\Blender Foundation\Blender *\blender.exe'],
    'magick': [r'C:\Program Files\ImageMagick-*\magick.exe'],
}

P, L, R, F = 'program', 'pylib', 'repo', 'fonts'
# (id, kind, domain, name to detect, licence, Arabic purpose, English purpose, how to use)
_ITEMS = [
    # ---- montage / video
    ('ffmpeg', P, 'montage', 'ffmpeg', 'LGPL/GPL', 'قص ودمج وترميز وفلاتر الفيديو والصوت', 'cut, join, encode, filter video and audio', 'ffmpeg -i in.mp4 ...'),
    ('ffprobe', P, 'montage', 'ffprobe', 'LGPL/GPL', 'قياس المدة والمقاس والفريمات والصوت', 'measure duration, size, frames, audio', 'ffprobe -v error -show_entries ...'),
    ('blender', P, 'montage', 'blender', 'GPL', 'تصميم ورندر 3D في الخلفية', '3D design and headless render', 'blender -b -P script.py'),
    ('remotion', P, 'montage', 'remotion', 'Remotion licence (free for individuals; companies need a licence)', 'فيديو بالكود (React)', 'video from React code', 'npx remotion render'),
    ('scenedetect', P, 'montage', 'scenedetect', 'BSD-3', 'كشف القطعات بين اللقطات', 'detect cuts between shots', 'scenedetect -i in.mp4 detect-adaptive list-scenes'),
    ('auto-editor', P, 'montage', 'auto-editor', 'Unlicense', 'شيل السكتات تلقائيًا', 'remove silences automatically', 'auto-editor in.mp4 --margin 0.2sec'),
    ('HandBrakeCLI', P, 'montage', 'HandBrakeCLI', 'GPL', 'تحويل وضغط الفيديو ببريستات جاهزة', 'transcode with presets', 'HandBrakeCLI -i in -o out --preset "..."'),
    ('rife', P, 'montage', 'rife-ncnn-vulkan', 'MIT', 'تنعيم الحركة بزيادة الفريمات', 'frame interpolation for smooth motion', 'rife-ncnn-vulkan -i in_frames -o out_frames'),
    ('mediainfo', P, 'montage', 'mediainfo', 'BSD-2', 'تفاصيل ملف الميديا', 'media file details', 'mediainfo file'),
    ('exiftool', P, 'montage', 'exiftool', 'GPL/Artistic', 'قراءة ومسح بيانات الملف (metadata)', 'read or strip metadata', 'exiftool file'),
    ('yt-dlp', P, 'montage', 'yt-dlp', 'Unlicense', 'تنزيل فيديو مرجع من لينك', 'download a reference video from a link', 'yt-dlp URL'),
    ('aria2c', P, 'montage', 'aria2c', 'GPL', 'تنزيل سريع بأكتر من اتصال', 'fast multi-connection download', 'aria2c -x 8 URL'),
    ('moviepy', L, 'montage', 'moviepy', 'MIT', 'مونتاج بالبايثون', 'video editing in Python', 'import moviepy'),
    ('opencv', L, 'montage', 'cv2', 'Apache-2', 'تحليل الصورة والحركة والتتبع', 'image, motion and tracking analysis', 'import cv2'),
    ('pyav', L, 'montage', 'av', 'BSD-3', 'قراءة وكتابة الفريمات مباشرة', 'direct frame read/write', 'import av'),
    ('opentimelineio', L, 'montage', 'opentimelineio', 'Apache-2', 'تبادل التايم لاين مع برامج المونتاج (EDL/XML)', 'exchange timelines with editors (EDL/XML)', 'import opentimelineio'),
    ('mediapipe', L, 'montage', 'mediapipe', 'Apache-2', 'كشف الوش والإيد والجسم (لاستبعاد لقطات فيها ناس)', 'face, hand, body detection (e.g. to reject clips with people)', 'import mediapipe'),
    ('open_clip', L, 'montage', 'open_clip', 'MIT', 'بحث عن لقطة بالوصف (صورة ↔ نص)', 'find a shot by description (image ↔ text)', 'import open_clip'),
    ('colour', L, 'montage', 'colour', 'BSD-3', 'علم الألوان وتحويلات دقيقة', 'colour science and exact conversions', 'import colour'),
    # ---- audio
    ('whisperx', P, 'audio', 'whisperx', 'BSD-2', 'تفريغ الكلام بتوقيت كل كلمة', 'transcribe speech with word timings', 'whisperx audio --output_format json'),
    ('faster-whisper', L, 'audio', 'faster_whisper', 'MIT', 'تفريغ سريع بتوقيت الكلمات', 'fast transcription with word timestamps', 'from faster_whisper import WhisperModel'),
    ('demucs', P, 'audio', 'demucs', 'MIT', 'فصل الصوت عن الموسيقى', 'separate voice from music', 'demucs --two-stems=vocals file'),
    ('deep-filter', P, 'audio', 'deep-filter', 'MIT/Apache-2', 'تنضيف الصوت من الدوشة', 'remove noise from speech', 'deep-filter in.wav -o outdir'),
    ('sox', P, 'audio', 'sox', 'GPL', 'معالجة صوت سريعة وإحصائيات', 'quick audio processing and stats', 'sox in.wav out.wav ...'),
    ('ffmpeg-normalize', L, 'audio', 'ffmpeg_normalize', 'MIT', 'ضبط علو الصوت (LUFS) بمرّتين', 'two-pass loudness normalisation (LUFS)', 'ffmpeg-normalize in.mp4 -t -14 -c:a aac -o out.mp4'),
    ('pyloudnorm', L, 'audio', 'pyloudnorm', 'MIT', 'قياس LUFS', 'measure LUFS', 'import pyloudnorm'),
    ('noisereduce', L, 'audio', 'noisereduce', 'MIT', 'تقليل الدوشة بالبايثون', 'noise reduction in Python', 'import noisereduce'),
    ('silero-vad', L, 'audio', 'silero_vad', 'MIT', 'كشف مكان الكلام والسكوت', 'detect speech and silence', 'from silero_vad import load_silero_vad'),
    ('librosa', L, 'audio', 'librosa', 'ISC', 'كشف الإيقاع والبيت للقص على الموسيقى', 'beat and tempo detection for cutting on music', 'import librosa'),
    ('edge-tts', P, 'audio', 'edge-tts', 'GPL-3 (needs internet)', 'صوت مولّد مجاني (محتاج نت)', 'free generated voice (needs internet)', 'edge-tts --voice ar-EG-SalmaNeural --text "..."'),
    # ---- image / text on screen
    ('magick', P, 'image', 'magick', 'ImageMagick licence', 'تعديل وتجميع الصور', 'edit and compose images', 'magick in.png ...'),
    ('inkscape', P, 'image', 'inkscape', 'GPL', 'رسم وتحويل SVG', 'draw and convert SVG', 'inkscape in.svg --export-type=png'),
    ('rembg', P, 'image', 'rembg', 'MIT', 'شيل الخلفية', 'remove background', 'rembg i in.png out.png'),
    ('pillow', L, 'image', 'PIL', 'HPND', 'رسم نص عربي متوصّل (raqm)', 'draw shaped Arabic text (raqm)', 'from PIL import ImageFont'),
    ('easyocr', L, 'image', 'easyocr', 'Apache-2', 'قراءة الكتابة من فيديو مرجع', 'read on-screen text from a reference video', 'import easyocr'),
    ('pysubs2', L, 'image', 'pysubs2', 'MIT', 'قراءة وكتابة ملفات الترجمة (SRT/ASS)', 'read and write subtitles (SRT/ASS)', 'import pysubs2'),
    ('pyarabic', L, 'image', 'pyarabic', 'GPL', 'تنضيف وتوحيد النص العربي', 'clean and normalise Arabic text', 'import pyarabic.araby'),
    ('arabic-fonts', F, 'image', str(FONTS), 'OFL 1.1', 'خطوط عربية مفتوحة: رقعة وكوفي ونسخ وعناوين', 'open Arabic fonts: ruqaa, kufi, naskh, display', 'fonts in ~/.red-rose/fonts'),
    # ---- thinking / analysis
    ('sentence-transformers', L, 'thinking', 'sentence_transformers', 'Apache-2', 'بحث بالمعنى في المعرفة والدروس (مش بالكلمة بس)', 'search knowledge and lessons by meaning', 'from sentence_transformers import SentenceTransformer'),
    ('rapidfuzz', L, 'thinking', 'rapidfuzz', 'MIT', 'مطابقة نص تقريبية (غلطات الإملاء والصوت)', 'fuzzy text matching (typos, dictation errors)', 'from rapidfuzz import fuzz'),
    ('networkx', L, 'thinking', 'networkx', 'BSD-3', 'خرائط العلاقات وتبعيات الخطوات', 'graphs of relations and step dependencies', 'import networkx'),
    ('sympy', L, 'thinking', 'sympy', 'BSD-3', 'حل رياضيات بالرموز والتحقق من المعادلات', 'symbolic maths and equation checks', 'import sympy'),
    ('scikit-learn', L, 'thinking', 'sklearn', 'BSD-3', 'تصنيف وتجميع (مثلًا تجميع اللقطات المتشابهة)', 'classification and clustering (e.g. similar shots)', 'import sklearn'),
    ('pandas', L, 'thinking', 'pandas', 'BSD-3', 'جداول وحسابات وكشوفات', 'tables, accounts and statements', 'import pandas'),
    ('scipy', L, 'thinking', 'scipy', 'BSD-3', 'إحصاء وتحسين وإشارات', 'statistics, optimisation, signals', 'import scipy'),
    # ---- utility
    ('7z', P, 'utility', '7z', 'LGPL', 'فك وضغط الأرشيفات', 'pack and unpack archives', '7z x file'),
    ('pandoc', P, 'utility', 'pandoc', 'GPL', 'تحويل المستندات', 'convert documents', 'pandoc in.docx -o out.md'),
    ('git', P, 'utility', 'git', 'GPL', 'حفظ الإصدارات', 'version control', 'git ...'),
    # ---- reference repos (read for ideas; rebuild natively, never call at runtime)
    ('repo-pyscenedetect', R, 'montage', 'Breakthrough__PySceneDetect', 'BSD-3', 'مرجع: خوارزميات كشف القطعات', 'reference: cut-detection algorithms', 'read the source'),
    ('repo-ffmpeg-normalize', R, 'audio', 'slhck__ffmpeg-normalize', 'MIT', 'مرجع: ضبط علو الصوت', 'reference: loudness normalisation', 'read the source'),
    ('repo-opentimelineio', R, 'montage', 'AcademySoftwareFoundation__OpenTimelineIO', 'Apache-2', 'مرجع: صيغة التايم لاين', 'reference: timeline format', 'read the source'),
    ('repo-auto-editor', R, 'montage', 'auto-editor', 'Unlicense', 'مرجع: شيل السكتات', 'reference: silence removal', 'read the source'),
    ('repo-whisperx', R, 'audio', 'whisperX', 'BSD-2', 'مرجع: محاذاة الكلمات', 'reference: word alignment', 'read the source'),
    ('repo-editly', R, 'montage', 'mifi__editly', 'MIT', 'مرجع: مونتاج بملف وصف', 'reference: declarative editing', 'read the source'),
    ('repo-lossless-cut', R, 'montage', 'lossless-cut', 'GPL-2', 'مرجع: قص من غير إعادة ترميز', 'reference: cutting without re-encode', 'read the source (GPL: ideas only)'),
    ('repo-hyperframes', R, 'montage', 'hyperframes', 'see repo', 'مرجع: فيديو من HTML', 'reference: video from HTML', 'read the source; check its licence first'),
]


def program_path(name: str) -> str | None:
    hit = shutil.which(name)
    if hit:
        return hit
    for pattern in _FALLBACK.get(name, []):
        found = sorted(glob.glob(pattern, recursive=True))
        if found:
            return found[-1]
    return None


def _locate(kind: str, detect: str) -> str | None:
    if kind == P:
        return program_path(detect)
    if kind == L:
        try:
            spec = importlib.util.find_spec(detect)
        except (ImportError, ValueError):
            spec = None
        return (spec.origin or detect) if spec else None
    if kind == R:
        d = REPOS / detect
        return str(d) if d.is_dir() else None
    if kind == F:
        d = Path(detect)
        n = len(list(d.glob('*.ttf'))) if d.is_dir() else 0
        return f'{d} ({n} fonts)' if n else None
    return None


def items(domain: str | None = None, find: str | None = None, missing: bool = False) -> list[dict]:
    words = [w.lower() for w in (find or '').split() if w]
    out = []
    for ident, kind, dom, detect, lic, ar, en, use in _ITEMS:
        if domain and dom != domain:
            continue
        hay = f'{ident} {dom} {ar} {en}'.lower()
        if words and not any(w in hay for w in words):
            continue
        where = _locate(kind, detect)
        if missing and where:
            continue
        out.append({'id': ident, 'kind': kind, 'domain': dom, 'ready': bool(where), 'where': where,
                    'purpose_ar': ar, 'purpose_en': en, 'licence': lic, 'use': use})
    return out


def summary(domain=None, find=None, missing=False) -> dict:
    rows = items(domain, find, missing)
    by = {}
    for r in rows:
        d = by.setdefault(r['domain'], {'ready': 0, 'missing': 0})
        d['ready' if r['ready'] else 'missing'] += 1
    return {'ok': True, 'count': len(rows), 'ready': sum(r['ready'] for r in rows),
            'missing': [r['id'] for r in rows if not r['ready']], 'by_domain': by, 'items': rows,
            'note': 'Reference data only. Red Rose runs without these; repos are read for ideas, never called at runtime.'}


def fonts() -> list[str]:
    return sorted(str(p) for p in FONTS.glob('*.ttf')) if FONTS.is_dir() else []
