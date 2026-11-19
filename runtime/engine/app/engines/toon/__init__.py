"""Toon engine: turn a video or photo into a cartoon / anime look with open-source models, offline on CPU.

Styles (models live in ~/dragon-models/toon):
  3d        DCT-Net 3D cartoon (Apache-2.0) — soft 3D-animated-film look ("Disney/Pixar-like")
  hayao     AnimeGANv3 Hayao — hand-painted anime (non-commercial licence)
  shinkai   AnimeGANv3 Shinkai — bright cinematic anime (non-commercial licence)
  paint     AnimeGANv2 face_paint_512_v2 — painted portrait (MIT)

Video pipeline: ffmpeg extracts frames at a lower "animation" frame rate (default 12 fps, animated "on twos"), every frame
is stylised with onnxruntime, then ffmpeg rebuilds the video at the source size with the original audio, a light deflicker
and H.264 BT.709 output.
"""
import json, os, shutil, subprocess, tempfile, time
from pathlib import Path

import numpy as np

MODELS = Path(os.environ.get("BD_TOON_MODELS", Path.home() / "dragon-models" / "toon"))
STYLES = {
    "3d": {"file": "dct3d_cartoon_bg.onnx", "layout": "hwc", "order": "rgb", "range": 255, "mult": 16, "name": "كارتون 3D (DCT-Net)"},
    "hayao": {"file": "AnimeGANv3_Hayao_36.onnx", "layout": "nhwc", "order": "rgb", "mult": 8, "name": "أنمي مرسوم (Hayao)"},
    "shinkai": {"file": "AnimeGANv3_Shinkai_37.onnx", "layout": "nhwc", "order": "rgb", "mult": 8, "name": "أنمي سينمائي (Shinkai)"},
    "paint": {"file": "face_paint_512_v2_0.onnx", "layout": "nchw", "order": "rgb", "fixed": 512, "name": "رسم بورتريه"},
    "ai3d": {"file": "sd-turbo", "diffusion": True, "name": "كارتون 3D بالذكاء الاصطناعي (SD-Turbo، أبطأ وأقوى)"},
}
AI3D_PROMPT = ("3d animated feature film still, stylized cartoon characters, big expressive eyes, soft subsurface skin, "
               "smooth clean shapes, warm cinematic lighting, pixar-like 3d render, high quality")
AI3D_NEGATIVE = "photo, realistic skin texture, noise, blurry, deformed, extra limbs, text, watermark"
_pipe = {}
_sessions = {}


def ffmpeg_exe():
    return shutil.which("ffmpeg") or "ffmpeg"


def session(style):
    import onnxruntime as ort
    if style not in STYLES:
        raise ValueError(f"style must be one of {list(STYLES)}")
    if style not in _sessions:
        f = MODELS / STYLES[style]["file"]
        if not f.exists():
            raise FileNotFoundError(f"model missing: {f} (run: python -m engines.toon setup)")
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = max(1, (os.cpu_count() or 4) - 1)
        _sessions[style] = ort.InferenceSession(str(f), opts, providers=["CPUExecutionProvider"])
    return _sessions[style]


def _ai3d(img, strength=0.55, steps=2, seed=7, side=512):
    """SD-Turbo image-to-image: redraws the frame as a 3D-animated-film still (CPU, bfloat16 to halve memory)."""
    import torch
    from PIL import Image
    if "p" not in _pipe:
        from diffusers import AutoPipelineForImage2Image
        path = MODELS / "sd-turbo"
        if not (path / "model_index.json").exists():
            raise FileNotFoundError(f"SD-Turbo missing: {path} (python -m engines.toon setup)")
        pipe = AutoPipelineForImage2Image.from_pretrained(str(path), variant="fp16", torch_dtype=torch.bfloat16)
        pipe.set_progress_bar_config(disable=True)
        torch.set_num_threads(max(1, (os.cpu_count() or 4) - 1))
        _pipe["p"] = pipe
    h, w = img.shape[:2]
    sc = side / max(h, w)
    tw, th = max(64, int(w * sc) // 8 * 8), max(64, int(h * sc) // 8 * 8)
    src = Image.fromarray(img).resize((tw, th), Image.LANCZOS)
    g = torch.Generator("cpu").manual_seed(seed)       # same seed every frame -> steadier video
    with torch.inference_mode():
        out = _pipe["p"](prompt=AI3D_PROMPT, negative_prompt=AI3D_NEGATIVE, image=src, strength=strength,
                         num_inference_steps=steps, guidance_scale=0.0, generator=g).images[0]
    return np.asarray(out.convert("RGB").resize((w, h), Image.LANCZOS))


def stylize(img, style="3d", max_side=720):
    """img: HxWx3 uint8 RGB -> stylised HxWx3 uint8 RGB (same size)."""
    from PIL import Image
    if STYLES.get(style, {}).get("diffusion"):
        return _ai3d(img)
    cfg, sess = STYLES[style], session(style)
    h, w = img.shape[:2]
    if cfg.get("fixed"):
        tw = th = cfg["fixed"]
    else:
        sc = min(1.0, max_side / max(h, w))
        m = cfg["mult"]
        tw, th = max(m, int(round(w * sc / m)) * m), max(m, int(round(h * sc / m)) * m)
    x = np.asarray(Image.fromarray(img).resize((tw, th), Image.LANCZOS), dtype=np.float32)
    if cfg["order"] == "bgr":
        x = x[..., ::-1]
    if cfg.get("range") != 255:      # AnimeGAN models work in [-1, 1]; DCT-Net takes raw 0-255 pixels
        x = x / 127.5 - 1.0
    if cfg["layout"] == "nhwc":
        x = x[None]
    elif cfg["layout"] == "nchw":
        x = x.transpose(2, 0, 1)[None]
    y = sess.run(None, {sess.get_inputs()[0].name: x.astype(np.float32)})[0]
    if cfg["layout"] != "hwc":
        y = y[0]
    if cfg["layout"] == "nchw":
        y = y.transpose(1, 2, 0)
    if cfg["order"] == "bgr":
        y = y[..., ::-1]
    y = np.clip(y if cfg.get("range") == 255 else (y + 1.0) * 127.5, 0, 255).astype(np.uint8)
    out = np.asarray(Image.fromarray(y).resize((w, h), Image.LANCZOS))
    if style == "3d":
        out = _faces_3d(img, out)
    return out


# ---- DCT-Net faces: detect, align each face to the model's training crop, cartoonise it, paste it back with a soft mask ----
_FACE = {}
_REF5 = np.float32([[30.29459953, 51.69630051], [65.53179932, 51.50139999], [48.02519989, 71.73660278],
                    [33.54930115, 92.3655014], [62.72990036, 92.20410156]]) + np.float32([8, 0])   # 96x112 -> square 112


def _face_tools():
    import cv2
    if not _FACE:
        det = MODELS / "face_detection_yunet_2023mar.onnx"
        alpha = MODELS / "dct3d_alpha.jpg"
        _FACE["det"] = cv2.FaceDetectorYN.create(str(det), "", (320, 320), 0.7, 0.3, 5000) if det.exists() else None
        a = cv2.imread(str(alpha), cv2.IMREAD_GRAYSCALE) if alpha.exists() else None
        _FACE["mask"] = cv2.resize(a, (288, 288), interpolation=cv2.INTER_AREA).astype(np.float32) / 255 if a is not None else None
    return _FACE["det"], _FACE["mask"]


def _faces_3d(src, styled, box=288, ratio=0.75):
    """src/styled: HxWx3 uint8 RGB. Returns styled with every detected face replaced by its aligned 3D-cartoon version."""
    import cv2
    det, mask = _face_tools()
    if det is None or mask is None:
        return styled
    h, w = src.shape[:2]
    det.setInputSize((w, h))
    _, faces = det.detect(cv2.cvtColor(src, cv2.COLOR_RGB2BGR))
    if faces is None:
        return styled
    ref = ((_REF5 - 56) * ratio + 56) * (box / 112.0)
    out = styled.astype(np.float32)
    sess = session("3d")
    for f in faces:
        if f[2] < 40 or f[3] < 40:          # tiny background faces: the whole-image pass is enough
            continue
        pts = np.float32(f[4:14]).reshape(5, 2)    # YuNet: right eye, left eye, nose, right mouth, left mouth (image order)
        M, _ = cv2.estimateAffinePartial2D(pts, ref, method=cv2.LMEDS)
        if M is None:
            continue
        crop = cv2.warpAffine(src, M, (box, box), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
        head = sess.run(None, {sess.get_inputs()[0].name: crop.astype(np.float32)})[0]
        head = np.clip(head, 0, 255).astype(np.float32)
        Minv = cv2.invertAffineTransform(M)
        back = cv2.warpAffine(head, Minv, (w, h), flags=cv2.INTER_LINEAR)
        m = cv2.warpAffine(mask, Minv, (w, h), flags=cv2.INTER_LINEAR)[..., None]
        out = m * back + (1 - m) * out
    return np.clip(out, 0, 255).astype(np.uint8)


def image(src, dst, style="3d", max_side=1280):
    from PIL import Image
    img = np.asarray(Image.open(src).convert("RGB"))
    out = stylize(img, style, max_side)
    Path(dst).parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(out).save(dst, quality=95)
    return {"out": str(dst), "style": style, "size": [img.shape[1], img.shape[0]]}


def video(src, dst, style="3d", fps=12, max_side=720, seconds=None, deflicker=True, progress=print):
    """Stylise a video. fps: animation frame rate (12 = classic 'on twos'; 0 = keep source fps)."""
    from PIL import Image
    ff = ffmpeg_exe()
    src, dst = Path(src), Path(dst)
    work = Path(tempfile.mkdtemp(prefix="bd_toon_"))
    try:
        vf = [f"fps={fps}"] if fps else []
        cmd = [ff, "-v", "error", "-y", *(["-t", str(seconds)] if seconds else []), "-i", str(src)]
        if vf:
            cmd += ["-vf", ",".join(vf)]
        subprocess.run(cmd + [str(work / "f_%06d.png")], check=True)
        frames = sorted(work.glob("f_*.png"))
        if not frames:
            raise RuntimeError("مفيش فريمات اتطلعت من الفيديو")
        t0 = time.time()
        for i, f in enumerate(frames, 1):
            img = np.asarray(Image.open(f).convert("RGB"))
            Image.fromarray(stylize(img, style, max_side)).save(work / f"s_{i:06d}.png")
            if progress and (i == 1 or i % 10 == 0 or i == len(frames)):
                el = time.time() - t0
                progress(f"frame {i}/{len(frames)}  {el / i:.2f}s/frame  ETA {el / i * (len(frames) - i):.0f}s")
        rate = fps or _source_fps(src)
        from ..deliver import fit_audio   # exact length: -shortest ended films frames short (v12 rule)
        post = ["deflicker=mode=pm:size=5"] if deflicker else []
        post += ["scale=trunc(iw/2)*2:trunc(ih/2)*2", "format=yuv420p"]
        dst.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([ff, "-v", "error", "-y", "-framerate", str(rate), "-i", str(work / "s_%06d.png"),
                        *(["-t", str(seconds)] if seconds else []), "-i", str(src),
                        "-map", "0:v", "-map", "1:a?", "-vf", ",".join(post), "-c:v", "libx264", "-preset", "slow", "-crf", "17",
                        "-x264-params", "colorprim=bt709:transfer=bt709:colormatrix=bt709", "-r", str(rate),
                        "-frames:v", str(len(frames)), "-af", fit_audio(len(frames) / float(rate)),
                        "-c:a", "aac", "-b:a", "256k", "-movflags", "+faststart", str(dst)], check=True)
        return {"out": str(dst), "style": style, "frames": len(frames), "fps": rate, "seconds_per_frame": round((time.time() - t0) / len(frames), 2)}
    finally:
        shutil.rmtree(work, ignore_errors=True)


def _source_fps(src):
    out = subprocess.run([shutil.which("ffprobe") or "ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=r_frame_rate",
                          "-of", "csv=p=0", str(src)], capture_output=True, text=True).stdout.strip()
    n, _, d = out.partition("/")
    return round(float(n) / float(d or 1), 3) if n else 25


def setup():
    """Report which style models are present; convert DCT-Net .pb files to ONNX once (needs tensorflow + tf2onnx)."""
    status = {}
    for k, cfg in STYLES.items():
        status[k] = (MODELS / cfg["file"] / "model_index.json").exists() if cfg.get("diffusion") else (MODELS / cfg["file"]).exists()
    if not status["3d"] and (MODELS / "dct3d_cartoon_bg.pb").exists():
        r = subprocess.run([shutil.which("python") or "python", "-m", "tf2onnx.convert", "--graphdef", str(MODELS / "dct3d_cartoon_bg.pb"),
                            "--inputs", "input_image:0", "--outputs", "output_image:0", "--opset", "13",
                            "--output", str(MODELS / "dct3d_cartoon_bg.onnx")], capture_output=True, text=True)
        status["3d"] = (MODELS / "dct3d_cartoon_bg.onnx").exists()
        if not status["3d"]:
            status["3d_error"] = r.stderr[-800:]
    return status
