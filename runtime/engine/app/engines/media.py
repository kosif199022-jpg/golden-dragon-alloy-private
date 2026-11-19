"""Shared FFmpeg helpers: locate the binaries once, probe a file once, run ffmpeg with clear errors."""
import json, os, shutil, subprocess
from functools import lru_cache
from pathlib import Path


def ascii_path(p) -> Path:
    """A path ffmpeg filters and OpenCV can open. On Windows, drawtext fontfile / ass / lut3d / OpenCV models fail when
    the path has non-ASCII characters (the skill under «التنين الأسود», a job under «خطابة 2»): «could not parse
    fontconfig pattern», exit -22. Such a file (or folder) is copied once to an ASCII temp folder keyed by its full
    path, refreshed when its size or mtime changes, and that copy is returned. ASCII paths are returned unchanged. v10.15"""
    import hashlib, tempfile
    p = Path(p)
    full = str(p.resolve())
    if full.isascii():
        return p
    for base in (Path(tempfile.gettempdir()), Path(os.environ.get("PUBLIC") or "C:/Users/Public"), Path.home()):
        root = base / "black_dragon_ascii"
        if not str(root).isascii():
            continue
        name = p.name if p.name.isascii() else "f" + "".join(c for c in p.suffix if c.isascii())
        dst = root / hashlib.sha1(full.encode("utf-8")).hexdigest()[:12] / name
        try:
            if p.is_dir():
                shutil.copytree(p, dst, dirs_exist_ok=True)
            else:
                st = p.stat()
                if not dst.is_file() or dst.stat().st_size != st.st_size or dst.stat().st_mtime < st.st_mtime:
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(p, dst)
            return dst
        except OSError:
            continue
    return p


@lru_cache(maxsize=None)
def exe(name: str) -> str:
    p = shutil.which(name)
    if p:
        return p
    root = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet"
    for base in (root / "Links", root / "Packages"):
        hit = next(base.rglob(f"{name}.exe"), None) if base.exists() else None
        if hit:
            return str(hit)
    raise FileNotFoundError(f"{name} not found: winget install -e --id Gyan.FFmpeg")


def probe(path) -> dict:
    """format + every stream (with per-stream duration and frame count when known)."""
    out = subprocess.run([exe("ffprobe"), "-v", "error", "-show_entries",
                          "format=duration,bit_rate:stream=index,codec_type,codec_name,profile,width,height,r_frame_rate,avg_frame_rate,"
                          "pix_fmt,sample_rate,channels,duration,nb_frames,color_primaries",
                          "-of", "json", str(path)], capture_output=True, text=True, encoding="utf-8")
    if out.returncode:
        raise ValueError(out.stderr.strip() or "ffprobe failed")
    return json.loads(out.stdout)


def fps(rate: str) -> float:
    n, _, d = (rate or "0/1").partition("/")
    return float(n) / float(d or 1) if float(d or 1) else 0.0


def ffmpeg(*args, check=True, capture=False):
    r = subprocess.run([exe("ffmpeg"), "-hide_banner", "-v", "error", "-y", *map(str, args)],
                       capture_output=capture, text=capture, encoding="utf-8" if capture else None, errors="ignore" if capture else None)
    if check and r.returncode:
        raise RuntimeError(f"ffmpeg failed ({r.returncode}): {' '.join(map(str, args))[:300]}\n{(r.stderr or '')[-800:] if capture else ''}")
    return r
