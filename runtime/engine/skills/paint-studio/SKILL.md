---
name: paint-studio
description: Full Windows 11 Paint feature set as a scriptable skill. Use when the user wants to draw, paint, sketch, make shapes/diagrams/callouts, add text (Arabic or English) to an image, fill/erase/crop/resize/rotate/flip/skew/invert, work with layers, remove or blur a background, erase an object, make stickers or a coloring page, generate an image from text (Image Creator), turn a sketch into art (Cocreator), restyle a photo (Reimagine), or generative-fill a region — or says "ارسم", "الرسام", "Paint", "mspaint". Runs locally and free (Pillow/OpenCV/rembg + SD-Turbo on CPU); can also open/drive the real Paint app.
---

# Paint Studio

Every Paint 11 tool, re-implemented as a command-line engine Claude can drive precisely
(coordinates, colors, layers) — plus the real Paint app when the user wants to see it there.
Feature map (Paint menu → command): `reference/features.md`. How the feature list was derived: `reference/analysis.md`.

## Two engines
| Script | Python | What |
|---|---|---|
| `scripts/paint.py` | system `python` | canvas, brushes, shapes, fill, text, selection, image ops, layers, background removal/blur, magic erase, coloring page, sticker border, upscale, preview/grid/rulers, print, wallpaper, open in Paint |
| `scripts/paint_ai.py` | `%USERPROFILE%\dragon-models\toon\venv\Scripts\python.exe` | Copilot features with local SD-Turbo: `create` (Image Creator), `cocreator`, `reimagine`, `fill` (Generative fill), `erase` (Generative erase), `sticker`, `coloring` |

Paths below: `P=python "%USERPROFILE%\.claude\skills\paint-studio\scripts\paint.py"`,
`AI="%USERPROFILE%\dragon-models\toon\venv\Scripts\python.exe" "%USERPROFILE%\.claude\skills\paint-studio\scripts\paint_ai.py"`.

## Workflow
1. **Plan in pixels.** Paint's default canvas is 1152×648. Decide the canvas size first, then lay out coordinates.
2. **Create**: `$P new out\canvas.png --size 1152x648 --bg white` (use `.dpaint` for a layered project, `--bg transparent` for stickers/logos).
3. **Write ops as JSON** (a list, or `{"ops":[...]}`) and run `$P draw IN OUT --ops ops.json`. Short jobs: repeat `--op '{...}'`.
   IN and OUT can be the same `.dpaint` to keep editing a project. `$P ops` prints every op and parameter.
4. **Look at the result** with the Read tool (view the PNG). For detail: `$P preview IN prev.png --zoom 3 --box x0,y0,x1,y1 --grid 10 --rulers`.
5. **Export**: `$P export proj.dpaint final.png` (also jpg/webp/avif/heic/bmp/gif/tiff/ico). Save AI outputs and finals in the user's work folder (`output/`).

## Op cheat-sheet (all coordinates in canvas pixels)
```json
[
 {"op":"brush","points":[[40,40],[120,90],[200,60]],"size":12,"color":"red","smooth":2},
 {"op":"watercolor","points":[[40,200],[400,220]],"size":30,"color":"#3f48cc"},
 {"op":"star5","box":[500,40,620,160],"fill":"gold","outline":"black","size":3,"rotate":10},
 {"op":"callout_oval","box":[650,40,900,180],"fill":"white","outline":"black","size":3},
 {"op":"text","x":670,"y":80,"width":210,"align":"center","text":"أهلاً!","size":36,"font":"Arial","bold":true},
 {"op":"line","start":[100,400],"end":[400,400],"size":5,"outline":"black","arrow_head":true},
 {"op":"curve","start":[100,500],"end":[500,500],"control1":[200,380],"control2":[400,620],"size":4},
 {"op":"fill","x":560,"y":100,"color":"orange","tolerance":40},
 {"op":"layer_add","name":"Sky"}, {"op":"layer_move","to":"bottom"},
 {"op":"remove_background"}, {"op":"crop","box":[0,0,800,600]}
]
```
- Brushes: `pencil brush calligraphy_brush calligraphy_pen airbrush oil crayon marker natural_pencil watercolor eraser`.
- Shapes (20): `ellipse rectangle rounded_rectangle polygon triangle right_triangle diamond pentagon hexagon arrow_right/left/up/down star4/5/6 callout_rect callout_oval callout_cloud heart lightning`; `outline_style` can be `solid crayon marker oil natural_pencil watercolor` like Paint's outline menu; `fill:"none"` = no fill.
- Colors: hex `#RRGGBB(AA)`, CSS names, or Paint palette names (`dark_red, gold, turquoise, indigo, lavender, rose, lime…`).
- Selection ops (`crop delete move copy invert_colors`) take `box`, `polygon` (free-form), `subject:true` (AI object select, optional `box` to aim it), `mask` file, and `invert:true` (invert selection).
- Layers: any op may carry `"layer": index|name` to target that layer. Blend modes: normal multiply screen overlay darken lighten.
- Text: Arabic is shaped and right-to-left automatically (Pillow + raqm). Use `width` for wrapping, `background` for a filled text box, `stroke` for outlined text.

## AI features (local, free, CPU)
```
$AI create out\img.png --prompt "..." --style watercolor --size 768x512 --n 2
$AI cocreator sketch.png out\art.png --prompt "what the sketch is" --creativity 0.6 --style digital_art
$AI reimagine photo.jpg out\re.png --prompt "same scene in winter" --strength 0.5
$AI fill photo.jpg out\filled.png --prompt "a red balloon" --box 300,80,420,220
$AI erase photo.jpg out\clean.png --box 330,180,430,300
$AI sticker out\cat.png --prompt "happy cat astronaut" --style cartoon
$AI coloring out\page.png --prompt "castle with dragons"
$AI styles
```
SD-Turbo needs ~4 GB free RAM. Status 2026-11-10: `paint_ai.py` is written but not yet verified on this PC — a 512 px test
with only 1–3 GB RAM free (Excel/Chrome open) did not finish in 30 min. Before using it: check free RAM, ask the user to
close heavy apps, run in the background, and try one 512 px image with `--steps 1` first. If it is still too slow, tell the user
and offer the cloud route (costs money → needs explicit approval) or Paint's own Image Creator via the GUI. For larger finals, chain `{"op":"upscale","scale":4}` (upscayl). Run long batches in the background.
Cloud services (Higgsfield, etc.) cost money — only with the user's explicit approval.

## The real Paint app
- `$P gui file.png` opens a file in Paint. To operate Paint's own UI, use the computer tool (screenshot → click → verify).
- Paint's own features like Image Creator need a Microsoft account and credits. Prefer the local engine.

## Rules
- Never overwrite the user's originals; write to a new file or `output/`.
- `$P print` and `$P wallpaper` change things outside the canvas. Say exactly what will happen and wait for the user's OK first.
- Always view the output image before saying it's done; report size and path.
