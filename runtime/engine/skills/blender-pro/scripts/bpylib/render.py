"""Rendering: engine/samples/denoise/motion blur/transparency, Cycles GPU auto-detect
(OPTIX > CUDA > HIP > ONEAPI > METAL > CPU), compositor (glare/bloom, lens distortion,
vignette, exposure) for the Blender 5.x node-group compositor, still / image sequence /
MP4 (rendered as PNG frames then encoded by system ffmpeg, H.264 CRF high quality) and
contact sheets for quick visual checks."""
import glob
import json
import math
import os
import shutil
import subprocess
import time

import bpy

from . import util
from .util import log, warn


# --------------------------------------------------------------------------- devices
def gpu_setup(state=None, prefer=("OPTIX", "CUDA", "HIP", "ONEAPI", "METAL"), **_):
    """Enable the best Cycles GPU backend; falls back to CPU. Returns {'device','backend','devices'}."""
    sc = bpy.context.scene
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
    except KeyError:
        return {"device": "CPU", "backend": None, "devices": []}
    for backend in prefer:
        try:
            prefs.compute_device_type = backend
        except TypeError:
            continue
        try:
            prefs.get_devices()
        except Exception:
            continue
        gpus = [d for d in prefs.devices if d.type == backend]
        if gpus:
            for d in prefs.devices:
                d.use = d.type == backend
            sc.cycles.device = "GPU"
            info = {"device": "GPU", "backend": backend, "devices": [d.name for d in gpus]}
            log(f"Cycles GPU: {info}")
            return info
    try:
        prefs.compute_device_type = "NONE"
    except TypeError:
        pass
    sc.cycles.device = "CPU"
    return {"device": "CPU", "backend": None, "devices": []}


def render_settings(state, engine=None, samples=None, denoise=True, motion_blur=None, shutter=0.5,
                    transparent=None, resolution_percentage=None, device="AUTO", bounces=None, clamp_indirect=10.0,
                    adaptive_threshold=None, caustics=False, raytracing=True, volumetrics=None, preview=None,
                    frame_step=None, **_):
    """Configure the render engine.
    engine: CYCLES | EEVEE | WORKBENCH. samples: Cycles path samples / EEVEE TAA samples.
    motion_blur: bool (shutter in frames). transparent: film transparent (PNG alpha).
    device: AUTO (GPU if available) | CPU | GPU."""
    from .scene import engine_id
    sc = bpy.context.scene
    if engine:
        sc.render.engine = engine_id(engine)
    eng = sc.render.engine
    if eng == "CYCLES":
        if device.upper() == "AUTO" or device.upper() == "GPU":
            info = gpu_setup(state) if not (state or {}).get("_gpu_done") else None
            if state is not None:
                state["_gpu_done"] = True
                if info:
                    state["gpu"] = info
        else:
            sc.cycles.device = "CPU"
        if samples:
            sc.cycles.samples = int(samples)
        sc.cycles.use_denoising = bool(denoise)
        if denoise:
            try:
                sc.cycles.denoiser = "OPENIMAGEDENOISE"
            except TypeError:
                pass
            if hasattr(sc.cycles, "denoising_input_passes"):
                sc.cycles.denoising_input_passes = "RGB_ALBEDO_NORMAL"
        if adaptive_threshold is not None:
            sc.cycles.adaptive_threshold = float(adaptive_threshold)
        if bounces is not None:
            sc.cycles.max_bounces = int(bounces)
        sc.cycles.sample_clamp_indirect = float(clamp_indirect)
        sc.cycles.caustics_reflective = sc.cycles.caustics_refractive = bool(caustics)
        sc.cycles.transparent_max_bounces = max(sc.cycles.transparent_max_bounces, 16)
    elif eng.startswith("BLENDER_EEVEE"):
        ee = sc.eevee
        if samples:
            ee.taa_render_samples = int(samples)
        if hasattr(ee, "use_raytracing"):
            ee.use_raytracing = bool(raytracing)
        if hasattr(ee, "use_shadows"):
            ee.use_shadows = True
        if volumetrics is not None and hasattr(ee, "volumetric_tile_size"):
            ee.volumetric_tile_size = "4" if volumetrics == "high" else "8"
    if motion_blur is not None:
        sc.render.use_motion_blur = bool(motion_blur)
        sc.render.motion_blur_shutter = float(shutter)
    if transparent is not None:
        sc.render.film_transparent = bool(transparent)
    if resolution_percentage:
        sc.render.resolution_percentage = int(resolution_percentage)
    if frame_step:
        sc.frame_step = int(frame_step)
    return {"engine": eng, "samples": samples, "device": getattr(sc.cycles, "device", None)}


def apply_preview(state, scale=40, cycles_samples=12, eevee_samples=8, max_frames=24, **_):
    """Low-cost preview: smaller resolution, few samples, sparse animation frames."""
    sc = bpy.context.scene
    sc.render.resolution_percentage = int(scale)
    if sc.render.engine == "CYCLES":
        sc.cycles.samples = min(sc.cycles.samples, int(cycles_samples))
        sc.cycles.use_denoising = True
        sc.cycles.adaptive_threshold = max(sc.cycles.adaptive_threshold, 0.05)
    else:
        sc.eevee.taa_render_samples = min(sc.eevee.taa_render_samples, int(eevee_samples))
    n = sc.frame_end - sc.frame_start + 1
    sc.frame_step = max(1, math.ceil(n / int(max_frames)))
    return {"scale": scale, "frame_step": sc.frame_step}


# --------------------------------------------------------------------------- compositor
def _comp_tree(sc, reset=True):
    """Return (tree, input_socket, output_node_input) for 5.x node-group compositor or legacy."""
    if hasattr(sc, "compositing_node_group"):
        ng = sc.compositing_node_group
        if ng is None or reset:
            ng = bpy.data.node_groups.new("BLPro_Compositor", "CompositorNodeTree")
            ng.interface.new_socket("Image", in_out="OUTPUT", socket_type="NodeSocketColor")
            sc.compositing_node_group = ng
        nt = ng
        nt.nodes.clear()
        rl = nt.nodes.new("CompositorNodeRLayers")
        out = nt.nodes.new("NodeGroupOutput")
        out_in = out.inputs[0]
    else:  # Blender < 5
        sc.use_nodes = True
        nt = sc.node_tree
        nt.nodes.clear()
        rl = nt.nodes.new("CompositorNodeRLayers")
        out = nt.nodes.new("CompositorNodeComposite")
        out_in = out.inputs["Image"]
    rl.location, out.location = (-800, 0), (1200, 0)
    return nt, rl.outputs["Image"], out_in


def _menu(node, name, value):
    """Set a menu input (5.x) or the equivalent enum property (4.x)."""
    sock = next((s for s in node.inputs if s.name == name), None)
    if sock is not None and sock.type == "MENU":
        sock.default_value = value
        return
    prop = name.lower().replace(" ", "_")
    for p in (prop, "glare_type", "distortion_type"):
        if hasattr(node, p):
            try:
                setattr(node, p, value.upper().replace(" ", "_"))
                return
            except TypeError:
                continue
    warn(f"could not set {name}={value} on {node.bl_idname}")


def _try_input(node, name, value):
    try:
        util.set_input(node, name, value)
    except (KeyError, TypeError) as e:
        warn(f"{node.bl_idname}: {e}")


def compositor(state, glare=None, bloom=None, lens=None, vignette=None, exposure=None, saturation=None,
               contrast=None, **_):
    """Post effects via the compositor (rebuilt each call).
    glare/bloom: {type: Bloom|Fog Glow|Streaks|Ghosts|Simple Star|Sun Beams, threshold: 1.0,
                  strength: 0.6, size: 0.5 (bloom: 0..1 relative), quality: Medium|High|Low, streaks: 4}
                 (bloom: true uses defaults)
    lens: {distortion: -0.02, dispersion: 0.01}  (chromatic aberration / barrel)
    vignette: {strength: 0.35, size: 0.8}  or true
    exposure: stops; saturation: 1.0 = unchanged; contrast: 0 = unchanged."""
    sc = bpy.context.scene
    nt, cur, out_in = _comp_tree(sc)
    x = -500

    def place(n):
        nonlocal x
        n.location = (x, 0)
        x += 250
        return n
    g = glare if glare is not None else bloom
    if g:
        g = {} if g is True else dict(g)
        node = place(nt.nodes.new("CompositorNodeGlare"))
        _menu(node, "Type", g.get("type", "Bloom"))
        _menu(node, "Quality", g.get("quality", "Medium"))
        for k, sock in (("threshold", "Threshold"), ("strength", "Strength"), ("size", "Size"),
                        ("streaks", "Streaks"), ("saturation", "Saturation"), ("smoothness", "Smoothness"),
                        ("fade", "Fade"), ("angle", "Streaks Angle")):
            if k in g:
                v = g[k]
                if k == "angle":
                    v = math.radians(v)
                _try_input(node, sock, v)
        if "threshold" not in g:
            _try_input(node, "Threshold", 0.9)
        if "strength" not in g:
            _try_input(node, "Strength", 0.5)
        if "tint" in g:
            _try_input(node, "Tint", g["tint"])
        nt.links.new(cur, node.inputs["Image"])
        cur = node.outputs[0]
    if exposure:
        node = place(nt.nodes.new("CompositorNodeExposure"))
        _try_input(node, "Exposure", float(exposure))
        nt.links.new(cur, node.inputs["Image"])
        cur = node.outputs[0]
    if saturation is not None or contrast is not None:
        if saturation is not None:
            node = place(nt.nodes.new("CompositorNodeHueSat"))
            _try_input(node, "Saturation", float(saturation))
            nt.links.new(cur, node.inputs["Image"])
            cur = node.outputs[0]
        if contrast is not None:
            node = place(nt.nodes.new("CompositorNodeBrightContrast"))
            _try_input(node, "Contrast", float(contrast))
            nt.links.new(cur, node.inputs["Image"])
            cur = node.outputs[0]
    if lens:
        lens = {} if lens is True else dict(lens)
        node = place(nt.nodes.new("CompositorNodeLensdist"))
        _try_input(node, "Distortion", float(lens.get("distortion", -0.015)))
        _try_input(node, "Dispersion", float(lens.get("dispersion", 0.012)))
        try:
            util.set_input(node, "Fit", True)
        except (KeyError, TypeError):
            if hasattr(node, "use_fit"):
                node.use_fit = True
        nt.links.new(cur, node.inputs["Image"])
        cur = node.outputs[0]
    if vignette:
        v = {} if vignette is True else dict(vignette)
        strength, size = float(v.get("strength", 0.35)), float(v.get("size", 0.85))
        em = nt.nodes.new("CompositorNodeEllipseMask")
        em.location = (x, -300)
        _try_input(em, "Size", [size * 1.15, size])
        _try_input(em, "Mask", 0.0)
        _try_input(em, "Value", 1.0)
        bl = nt.nodes.new("CompositorNodeBlur")
        bl.location = (x + 200, -300)
        res = max(sc.render.resolution_x, sc.render.resolution_y) * sc.render.resolution_percentage / 100
        try:
            util.set_input(bl, "Size", [res * 0.18, res * 0.18])
        except (KeyError, TypeError):
            bl.size_x = bl.size_y = int(res * 0.18)
        nt.links.new(util.node_output(em, "Mask"), bl.inputs["Image"])
        mr = nt.nodes.new("ShaderNodeMapRange")
        mr.location = (x + 400, -300)
        mr.inputs["To Min"].default_value = 1.0 - strength
        nt.links.new(bl.outputs[0], mr.inputs["Value"])
        mix = place(nt.nodes.new("ShaderNodeMix"))
        mix.data_type = "RGBA"
        mix.blend_type = "MULTIPLY"
        util.node_input(mix, "Factor").default_value = 1.0
        nt.links.new(cur, util.node_input(mix, "A"))
        nt.links.new(util.node_output(mr, "Result"), util.node_input(mix, "B"))
        cur = util.node_output(mix, "Result")
    nt.links.new(cur, out_in)
    return {"compositor": [k for k, v in (("glare", g), ("lens", lens), ("vignette", vignette), ("exposure", exposure)) if v]}


# --------------------------------------------------------------------------- output
def _set_image_format(fmt="PNG", transparent=False, depth=None, quality=92):
    s = bpy.context.scene.render.image_settings
    if hasattr(s, "media_type"):
        s.media_type = "IMAGE"
    s.file_format = fmt.upper().replace("JPG", "JPEG").replace("EXR", "OPEN_EXR")
    s.color_mode = "RGBA" if transparent and s.file_format in ("PNG", "OPEN_EXR", "WEBP", "TIFF") else "RGB"
    if depth:
        s.color_depth = str(depth)
    if s.file_format in ("JPEG", "WEBP"):
        s.quality = int(quality)
    if s.file_format == "PNG":
        s.compression = 15


def _needs_sim_stepping():
    sc = bpy.context.scene
    if sc.rigidbody_world is not None:
        return True
    for o in sc.objects:
        if any(m.type in ("CLOTH", "PARTICLE_SYSTEM", "FLUID", "SOFT_BODY", "DYNAMIC_PAINT") for m in o.modifiers):
            return True
    return False


def render_still(state, out="render.png", frame=None, format=None, transparent=None, **_):
    """Render one frame to an image file (PNG default; format from extension)."""
    sc = bpy.context.scene
    path = util.out_path(state, out)
    ext = os.path.splitext(path)[1].lower().lstrip(".")
    fmt = (format or {"jpg": "JPEG", "jpeg": "JPEG", "exr": "OPEN_EXR", "webp": "WEBP", "tif": "TIFF",
                      "tiff": "TIFF"}.get(ext, "PNG")).upper()
    if transparent is not None:
        sc.render.film_transparent = bool(transparent)
    _set_image_format(fmt, sc.render.film_transparent)
    f = int(frame if frame is not None else sc.frame_current)
    if _needs_sim_stepping() and f > sc.frame_start:
        for k in range(sc.frame_start, f + 1):
            sc.frame_set(k)
    sc.frame_set(f)
    _ensure_camera(state)
    sc.render.filepath = path
    t = time.time()
    bpy.ops.render.render(write_still=True)
    _record(state, path, "image", time.time() - t)
    return path


def _ensure_camera(state):
    if bpy.context.scene.camera is None:
        from . import camera
        warn("no camera in scene - auto framing all objects")
        camera.frame_objects(state)


def _record(state, path, kind, seconds=None, **extra):
    entry = {"path": path, "type": kind}
    if seconds is not None:
        entry["seconds"] = round(seconds, 1)
    entry.update(extra)
    if state is not None:
        state.setdefault("outputs", []).append(entry)
    print("BLPRO_OUTPUT " + json.dumps(entry, ensure_ascii=False), flush=True)
    return entry


def ffmpeg_exe():
    return shutil.which("ffmpeg")


def render_animation(state, out="anim.mp4", format=None, crf=16, preset="slow", keep_frames=False,
                     contact_sheet=True, audio=None, transparent=None, frame_start=None, frame_end=None, **_):
    """Render the frame range. out '*.mp4'/'*.mov'/'*.webm' -> video (PNG frames encoded with system
    ffmpeg, H.264 yuv420p CRF 16 by default; ProRes 4444 with alpha for .mov when transparent);
    out 'dir/name_####.png' or format 'PNG' -> image sequence.
    contact_sheet=True writes <out>_contact.png (6 frames tiled) for a quick look with Read.
    audio: optional audio file muxed into the video."""
    sc = bpy.context.scene
    if frame_start is not None:
        sc.frame_start = int(frame_start)
    if frame_end is not None:
        sc.frame_end = int(frame_end)
    if transparent is not None:
        sc.render.film_transparent = bool(transparent)
    _ensure_camera(state)
    path = util.out_path(state, out)
    ext = os.path.splitext(path)[1].lower()
    video = (format or "").upper() in ("MP4", "MOV", "WEBM", "MKV", "FFMPEG") or ext in (".mp4", ".mov", ".webm", ".mkv")
    t = time.time()
    if not video:
        if "#" not in os.path.basename(path):
            stem, e = os.path.splitext(path)
            path = stem + "_####" + (e or ".png")
        _set_image_format("PNG" if not format or format.upper() == "PNG" else format, sc.render.film_transparent)
        sc.render.filepath = path
        bpy.ops.render.render(animation=True)
        frames = sorted(glob.glob(path.replace("####", "*")))
        _record(state, path, "image_sequence", time.time() - t, frames=len(frames))
        if contact_sheet and frames:
            make_contact_sheet(state, frames, os.path.splitext(path.replace("_####", ""))[0] + "_contact.png")
        return path
    stem = os.path.splitext(path)[0]
    frames_dir = stem + "_frames"
    if os.path.isdir(frames_dir):
        shutil.rmtree(frames_dir, ignore_errors=True)
    os.makedirs(frames_dir, exist_ok=True)
    ff = ffmpeg_exe()
    if ff is None:
        warn("ffmpeg not on PATH - using Blender's built-in FFMPEG writer")
        return _render_blender_ffmpeg(state, path, t)
    _set_image_format("PNG", sc.render.film_transparent)
    sc.render.filepath = os.path.join(frames_dir, "f_####.png")
    bpy.ops.render.render(animation=True)
    frames = sorted(glob.glob(os.path.join(frames_dir, "f_*.png")))
    if not frames:
        raise RuntimeError("animation render produced no frames")
    # renumber contiguously (frame_step > 1 in previews)
    for i, fpath in enumerate(frames):
        os.replace(fpath, os.path.join(frames_dir, f"s_{i:05d}.png"))
    seq = sorted(glob.glob(os.path.join(frames_dir, "s_*.png")))
    fps = sc.render.fps / sc.render.fps_base
    in_rate = fps / max(1, sc.frame_step)
    cmd = [ff, "-y", "-hide_banner", "-loglevel", "error", "-framerate", f"{in_rate:.6f}",
           "-i", os.path.join(frames_dir, "s_%05d.png")]
    if audio:
        cmd += ["-i", util.resolve_path(state, audio)]
    if ext == ".mov" and sc.render.film_transparent:
        cmd += ["-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt", "yuva444p10le"]
    elif ext == ".webm":
        cmd += ["-c:v", "libvpx-vp9", "-crf", str(crf + 14), "-b:v", "0", "-pix_fmt",
                "yuva420p" if sc.render.film_transparent else "yuv420p"]
    else:
        cmd += ["-c:v", "libx264", "-preset", preset, "-crf", str(crf), "-pix_fmt", "yuv420p",
                "-movflags", "+faststart", "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2"]
    cmd += ["-r", f"{fps:.6f}"]
    if audio:
        cmd += ["-c:a", "aac", "-b:a", "256k", "-shortest"]
    cmd.append(path)
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {r.stderr[-800:]}")
    if contact_sheet:
        make_contact_sheet(state, seq, stem + "_contact.png")
    if not keep_frames:
        shutil.rmtree(frames_dir, ignore_errors=True)
    _record(state, path, "video", time.time() - t, frames=len(seq), fps=fps, frame_step=sc.frame_step)
    return path


def _render_blender_ffmpeg(state, path, t0):
    sc = bpy.context.scene
    s = sc.render.image_settings
    if hasattr(s, "media_type"):
        s.media_type = "VIDEO"
    s.file_format = "FFMPEG"
    ffs = sc.render.ffmpeg
    ffs.format = "MPEG4"
    ffs.codec = "H264"
    ffs.constant_rate_factor = "HIGH"
    ffs.ffmpeg_preset = "GOOD"
    sc.render.filepath = path
    bpy.ops.render.render(animation=True)
    _record(state, path, "video", time.time() - t0)
    return path


def make_contact_sheet(state, frames, out, count=6, cols=3, width=480):
    """Tile `count` evenly spaced frames into one PNG (needs ffmpeg)."""
    ff = ffmpeg_exe()
    if not ff or not frames:
        return None
    pick = [frames[round(i * (len(frames) - 1) / max(1, count - 1))] for i in range(min(count, len(frames)))]
    cmd = [ff, "-y", "-hide_banner", "-loglevel", "error"]
    for p in pick:
        cmd += ["-i", p]
    filt = "".join(f"[{i}:v]scale={width}:-2[v{i}];" for i in range(len(pick)))
    layout = "|".join(f"{(i % cols) * width}_" + ("0" if i // cols == 0 else "+".join(["h0"] * (i // cols)))
                      for i in range(len(pick)))
    if len(pick) == 1:
        filt += "[v0]copy[out]"
    else:
        filt += "".join(f"[v{i}]" for i in range(len(pick))) + f"xstack=inputs={len(pick)}:layout={layout}:fill=black[out]"
    cmd += ["-filter_complex", filt, "-map", "[out]", "-frames:v", "1", out]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        warn(f"contact sheet failed: {r.stderr[-300:]}")
        return None
    _record(state, out, "contact_sheet")
    return out


def render_op(state, type="still", out=None, **params):
    """Render dispatcher (also used for the recipe 'render' block).
    type: still | animation. out: file path (relative to --out dir)."""
    if type == "animation":
        return render_animation(state, out=out or "anim.mp4", **params)
    return render_still(state, out=out or "render.png", **params)


OPS = {
    "render_settings": render_settings,
    "gpu_setup": gpu_setup,
    "compositor": compositor,
    "render": render_op,
    "render_still": render_still,
    "render_animation": render_animation,
}
