"""After `charmem_cli.py demo OUT` and the tests: comparison sheets, the transfer proof, the vector export, and
RESULTS.md written from the measurement files themselves (no number typed by hand).

    python -I -X utf8 make_deliverables.py OUT [RESULTS_COPY.md]
"""
import io
import json
import subprocess
import sys
from pathlib import Path

import cairosvg
import numpy as np
from PIL import Image, ImageDraw
from skimage.color import rgb2lab

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from charmem import analyze as A  # noqa: E402

OUT = Path(sys.argv[1])
jl = lambda p: json.loads(Path(p).read_text(encoding="utf-8"))  # noqa: E731


def frame_of(video, t, size=None):
    r = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(t), "-i", str(video), "-frames:v", "1", "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True, check=True)
    im = Image.open(io.BytesIO(r.stdout)).convert("RGB")
    return im.resize(size) if size else im


# 1. redraw comparison sheet (reference | redraw | diff x4)
tiles = [Image.open(p) for p in sorted((OUT / "03_redraw").glob("compare_*.png")) if "_crop" not in p.stem]  # zoom crops are separate files
w = max(t.width for t in tiles)
crop = [t.crop((0, int(t.height * 0.28), t.width, int(t.height * 0.86))) for t in tiles]
sheet = Image.new("RGB", (w, sum(c.height for c in crop)), "white")
y = 0
for c in crop:
    sheet.paste(c, (0, y))
    y += c.height
sheet.save(OUT / "compare_ref_redraw_diff_sheet.png")

# 2. transfer proof: the source character, the new scene, and the palette learned twice
mem, mem2 = jl(OUT / "character_memory.json"), jl(OUT / "05_reanalysis" / "character_memory_from_new_scene.json")
ref = frame_of(OUT / "01_reference" / "reference.mp4", 0.2).crop((150, 560, 650, 1580)).resize((250, 510))
scene = [frame_of(OUT / "04_new_scene" / "new_scene.mp4", t).crop((0, 700, 1080, 1700)).resize((270, 250)) for t in (0.6, 2.4, 4.6, 7.8)]
proof = Image.new("RGB", (250 + 270 * 2 + 20, 510 + 150), "white")
proof.paste(ref, (0, 0))
for k, s in enumerate(scene):
    proof.paste(s, (260 + 270 * (k % 2), 250 * (k // 2) + 5))
d = ImageDraw.Draw(proof)
pa = {p["role"]: p for p in mem["identity"]["palette"] if p["role"] != "unassigned"}
pb = {p["role"]: p for p in mem2["identity"]["palette"] if p["role"] != "unassigned"}
x = 6
des = {}
for role in [r for r in pa if r in pb]:
    a, b = np.array(pa[role]["rgb"], np.uint8), np.array(pb[role]["rgb"], np.uint8)
    de = float(np.linalg.norm(rgb2lab(a[None, None])[0, 0] - rgb2lab(b[None, None])[0, 0]))
    des[role] = round(de, 2)
    d.rectangle([x, 525, x + 50, 560], fill=tuple(int(v) for v in a))
    d.rectangle([x, 562, x + 50, 597], fill=tuple(int(v) for v in b))
    d.text((x, 602), f"{role}\ndE {de:.1f}", fill=(0, 0, 0))
    x += 58
proof.save(OUT / "transfer_proof.png")

# 3. vector export from memory, and a raster view of it
subprocess.run([sys.executable, "-I", "-X", "utf8", str(HERE / "charmem_cli.py"), "export", str(OUT / "character_memory.json"), str(OUT / "06_export")], check=True)
png = cairosvg.svg2png(url=str(OUT / "06_export" / "character_rest.svg"))
Image.open(io.BytesIO(png)).convert("RGB").save(OUT / "06_export" / "character_rest_preview.png")

# 4. RESULTS.md from the files
rm, tr, tests = jl(OUT / "03_redraw" / "redraw_metrics.json")["summary"], jl(OUT / "02_work" / "tracking_vs_truth.json"), jl(OUT / "tests_report.json")
cc = jl(OUT / "03_redraw" / "codec_ceiling.json") if (OUT / "03_redraw" / "codec_ceiling.json").exists() else []
L = ["# Results on «Tamtam», the original test character (made by `charmem_cli.py demo`)", "",
     f"Folder: `{OUT}`", "",
     "## Videos and images",
     "- `01_reference/reference.mp4`: the reference performance (8 s, 1080x1920, 30 fps); `gt.json` = ground truth, used by tests only",
     "- `03_redraw/redraw.mp4`: every frame redrawn from vector layers; `03_redraw/svg/*.svgz`: one SVG per frame",
     "- `03_redraw/compare_ref_redraw_diff.mp4` and `compare_ref_redraw_diff_sheet.png`: reference | redraw | difference x4",
     "- `04_new_scene/new_scene.mp4`: a new scene drawn from `character_memory.json` alone (the source video was hidden while it rendered)",
     "- `transfer_proof.png`: the source character, the new scene, and each colour learned from the source (top) and re-learned from the new scene (bottom)",
     "- `06_export/character_rest.svg`, `character_skeleton.json`: vector export and a bones/slots/displays file", "",
     "## Redraw (240 frames, character box)",
     "| metric | mean | worst frame |", "|---|---|---|"]
for k, v in rm.items():
    L.append(f"| {k} | {v['mean']} | {v['min']} (frame {v['worst_frame']}) |")
if cc:
    L += ["", "Where the error comes from (frames rendered again without compression):",
          *[f"- frame {c['frame']}: lossless vs H.264 {c['lossless_vs_h264_db']} dB; lossless vs redraw {c['lossless_vs_redraw_db']} dB" for c in cc],
          "(those numbers were measured with the first vectoriser, pixel contours + dilation; the shipped one uses marching squares)"]
L += ["", f"## Tracking vs ground truth (head = {tr['head_unit_px']:.0f} px)",
      f"All joints, median of medians: {tr['all_joints_median_px']} px. Joints marked inferred/interpolated were hidden (no pixels).", "",
      "| joint | median px | p95 px | jitter px/frame² | frames not measured |", "|---|---|---|---|---|"]
for k, v in tr["joints"].items():
    L.append(f"| {k} | {v['median_px']} | {v['p95_px']} | {v['jitter_rms_px']} | {v['interpolated_frames']} |")
L += ["", "Occlusion: " + "; ".join(f"{o['part']}: truth {o['hidden_truth']} hidden frames, said {o['hidden_said']}, precision {o['precision']}, recall {o['recall']}" for o in tr["occlusion"]), "",
      "## Identity carried to the new scene (re-learned from scratch from the new scene video)",
      "ΔE per colour role (source memory vs new-scene memory): " + ", ".join(f"{k} {v}" for k, v in des.items()), "",
      f"## Tests: {tests['passed']}/{tests['total']} passed", "", "| | test | measured | needs |", "|---|---|---|---|"]
for r in tests["results"]:
    L.append(f"| {'PASS' if r['pass'] else 'FAIL'} | {r['test']} | {r['measured']} | {r['threshold']} |")
text = "\n".join(L) + "\n"
(OUT / "RESULTS.md").write_text(text, encoding="utf-8")
if len(sys.argv) > 2:
    Path(sys.argv[2]).write_text(text, encoding="utf-8")
print("deliverables ->", OUT, "| dE", des)
