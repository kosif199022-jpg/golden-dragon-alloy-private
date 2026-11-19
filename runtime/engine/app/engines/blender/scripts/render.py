# Runs INSIDE Blender: render the open .blend (one frame -> PNG, or a range -> image sequence -> MP4 via ffmpeg).
import argparse, json, os, shutil, subprocess, sys, tempfile
import bpy

argv = sys.argv[sys.argv.index("--") + 1:]
ap = argparse.ArgumentParser()
ap.add_argument("--out", required=True)
for k in ("frame", "start", "end", "samples", "fps"):
    ap.add_argument(f"--{k}", type=int)
ap.add_argument("--engine")
ap.add_argument("--res")
a = ap.parse_args(argv)

sc = bpy.context.scene
if a.engine:
    sc.render.engine = a.engine
if a.res:
    w, h = map(int, a.res.lower().split("x"))
    sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = w, h, 100
if a.samples:
    if sc.render.engine == "CYCLES":
        sc.cycles.samples = a.samples
    elif hasattr(sc, "eevee"):
        sc.eevee.taa_render_samples = a.samples
if a.fps:
    sc.render.fps = a.fps
out = os.path.abspath(a.out)
os.makedirs(os.path.dirname(out), exist_ok=True)
sc.render.image_settings.file_format = "PNG"
sc.view_settings.view_transform = sc.view_settings.view_transform  # keep the file's colour management (AgX/Filmic)

if a.frame is not None or out.lower().endswith(".png"):
    sc.frame_set(a.frame if a.frame is not None else sc.frame_current)
    sc.render.filepath = out
    bpy.ops.render.render(write_still=True)
    print("@@" + json.dumps({"still": out, "frame": sc.frame_current}))
else:
    if a.start is not None:
        sc.frame_start = a.start
    if a.end is not None:
        sc.frame_end = a.end
    tmp = tempfile.mkdtemp(prefix="bd-blender-")
    sc.render.filepath = os.path.join(tmp, "f_")
    bpy.ops.render.render(animation=True)
    ff = shutil.which("ffmpeg") or "ffmpeg"
    fps = sc.render.fps / sc.render.fps_base
    cmd = [ff, "-y", "-v", "error", "-framerate", f"{fps}", "-start_number", str(sc.frame_start), "-i", os.path.join(tmp, "f_%04d.png"),
           "-vf", "scale=out_color_matrix=bt709:out_range=tv,format=yuv420p", "-c:v", "libx264", "-preset", "slow", "-crf", "17",
           "-profile:v", "high", "-x264-params", "colorprim=bt709:transfer=bt709:colormatrix=bt709", "-movflags", "+faststart", out]
    subprocess.run(cmd, check=True)
    shutil.rmtree(tmp, ignore_errors=True)
    print("@@" + json.dumps({"video": out, "frames": sc.frame_end - sc.frame_start + 1, "fps": fps}))
