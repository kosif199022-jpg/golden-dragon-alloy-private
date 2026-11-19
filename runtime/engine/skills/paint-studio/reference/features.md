# Paint 11.2609 → paint-studio feature map

Every row is a feature found in the Paint binaries/UI strings (see analysis.md) and the command that reproduces it.

| Paint feature (internal name) | paint-studio |
|---|---|
| New canvas 1152×648, New from scanner/camera | `paint.py new --size WxH --bg ...` (camera/scanner: give a file) |
| Open/Save/Save as (21 formats + `.paint` project) | load any image; save by extension: png jpg webp avif heic bmp gif tiff ico; layered project = `.dpaint` |
| Image properties (size, DPI, units) | `paint.py info` |
| Selection: rectangular / free-form (`SelectionTool`, `FreeFormSelectionTool`) | `box` / `polygon` on `crop delete move copy` |
| Select all / Invert selection / Delete / Transparent selection | omit region / `invert:true` / `delete` / layers are transparent by default |
| Object select (`ObjectSelectTool`, AI) | `subject:true` (+ optional `box`) |
| Crop / Resize & skew / Rotate (90, 180, custom) / Flip H/V | `crop`, `resize`, `skew`, `rotate`, `flip` |
| Canvas size (drag handles) | `canvas_size` |
| Invert colors (`OnInvertColor`) | `invert_colors` (whole layer or selection) |
| Pencil / Fill bucket / Text / Eraser / Color picker / Magnifier | `pencil`, `fill`, `text`, `eraser`, `paint.py pick`, `paint.py preview --zoom` |
| Brushes: Brush, Calligraphy brush, Calligraphy pen, Airbrush, Oil, Crayon, Marker, Natural pencil, Watercolor | ops with the same names |
| Brush size / opacity sliders | `size`, `opacity` |
| Shapes (23 incl. line & curve, `ShapeFactory::Create*`) | same names; `outline`, `fill`, `outline_style`, `rotate` |
| Text: font, size, bold, italic, underline, strikethrough, fill background | `text` op fields |
| Colors: palette, custom colors, primary/secondary | color names / hex per op |
| Layers panel: add, duplicate, delete, hide/show, move up/down, merge down, background color/visibility, opacity | `layer_*` ops, `background`, `layer_props` |
| Copy merged / copy visible layers | `paint.py export` or `flatten` |
| Remove background (`BackgroundRemoval`) | `remove_background` |
| Background blur (`BackgroundBlur`) | `blur_background` |
| Generative erase / Magic eraser (`MagicEraserTool`) | `magic_erase` (fast, OpenCV) or `paint_ai.py erase` (AI refine) |
| Generative fill (`GenerativeFillTool`) | `paint_ai.py fill --box/--mask --prompt` |
| Image Creator (DALL·E, cloud credits) | `paint_ai.py create` (local SD-Turbo, free) |
| Cocreator (sketch + prompt + creativity slider) | `paint_ai.py cocreator --creativity` |
| Reimagine | `paint_ai.py reimagine` |
| Stickers / Generative stickers | `paint_ai.py sticker` or any PNG + `sticker_outline`, `paste_image` |
| Coloring book creator | `paint_ai.py coloring` or `coloring_book` on a photo |
| Super resolution (Copilot+ PC feature) | `upscale` (upscayl-bin) |
| Rulers / Gridlines / Zoom / Full screen / Thumbnail | `paint.py preview --rulers --grid --zoom --box` |
| Print / Print preview | `paint.py print` (ask first) / `preview` |
| Set as desktop background (fill/tile/center) | `paint.py wallpaper --style` (ask first) |
| C2PA "made with AI" signing (`PaintProvenanceNet`, `c2pa_c.dll`) | not reproduced (needs Microsoft signing service) |
| Open in the real Paint | `paint.py gui file` + computer tool |
