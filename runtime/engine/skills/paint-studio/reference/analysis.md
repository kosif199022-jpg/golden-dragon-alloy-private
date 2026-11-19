# Windows Paint 11.2609.401.0: analysis report (2026-11-10)

Target: `C:\Program Files\WindowsApps\Microsoft.Paint_11.2609.401.0_x64__8wekyb3d8bbwe` (Store/MSIX, x64).
Copies were analyzed in a scratch folder; the installed files were never modified.
The purpose was to inventory features so they could be re-implemented. No Microsoft code or assets are copied into this skill.

## Package layout
- `PaintApp\mspaint.exe` (4.3 MB, MFC + XAML Islands host)
- Libraries: `PaintUI.dll` (10.6 MB, WinUI/Direct2D/Direct3D11), `PaintTools.dll` (tools), `BasePaint.dll` (operations and shapes), `ProjectFile.dll` (layered .paint files), `ImageProcessing.dll` (GDI+)
- AI: `AIServices.dll`, `AIServicesCS.dll`, `PaintAIManager.dll`, `Microsoft.ImageCreation.dll`, `AIStore.dll`
- Provenance: `PaintProvenanceNet.dll`, `c2pa_c.dll`, `ProvenanceHelper.dll`, `Watermarker.dll`
- Local models (encrypted `.onnxe`): `mager.onnxe` (302 MB), `seg.onnxe`, `inseg_enc.onnxe`, `inseg_dec.onnxe` (segmentation and interactive selection)
- Stroke shaders (`CapsuleStroke*`, `StampStroke*` `.cso`)

## Results per tool
- **Detect It Easy:** all binaries are PE64, built with MSVC 19.44/19.50, VS2022 17.14, with LTCG and CodeView/POGO debug records. mspaint.exe uses MFC 14 Unicode; PaintUI uses Direct2D and Direct3D11. No packer or protector was found.
- **UPX:** `NotPackedException` (not packed).
- **FLOSS** (PaintTools.dll): no stack strings or decoded strings, so nothing is hidden.
- **capa** (mspaint.exe):
  - File I/O, registry read/write, mutex, runtime linking, PE parsing.
  - "Keylogging via polling" (GetKeyState/GetAsyncKeyState, used for modifier keys while drawing).
  - RC4 PRGA, XOR, FNV, Base64: library code, such as hashing and telemetry IDs.
  - "Geographical location": GetUserGeoID, which most likely gates AI features by region.
  - BasePaint and PaintTools: only key-state polling and the PDB path.
- **YARA / YARA-X** (custom rules):
  - HTTP client found in AIServices, AIServicesCS, PaintAIManager, PaintProvenanceNet, PaintUI and mspaint.
  - C2PA/provenance strings in 7 files.
  - D2D/GDI+ rendering in 6 files.
  - `IsDebuggerPresent` in all files, which is the standard MSVC CRT and not anti-debugging.
- **pylibs (pefile):** none of the files has a CLR header. AIServicesCS and PaintProvenanceNet are C# compiled with NativeAOT (their strings mention `nativeaot-compatibility`).
- **ILSpy:** not run, because there is no .NET metadata to decompile (NativeAOT is native code).
- **rz-bin:** the exported C++ classes reveal the whole tool set. See the list below.
- **rizin:** PaintTools.dll has 130 functions after `aa`, 8 sections and 212 imports.
- **REA / Ghidra 12.1.4** (PaintTools.dll): 1,152 procedures and 711 strings. The PDB is referenced but not available.
- **PE-sieve** (PID 6864): 186 modules scanned, 0 patched and 0 hooked. There were 3 implanted modules without a file on disk:
  - 1 is the Frida agent from this session's trace, identified by its `swiftCore` and `symsrv` strings.
  - 2 are VS2017 modules that import wininet/winhttp. Most likely a third-party injector such as a download-manager browser hook. This was not confirmed.
- **Frida / frida-ps / frida-trace:** attached to mspaint.exe and hooked CreateFileW and WinHttpConnect. There were no calls during 15 s of idle time.
- **Not applicable:** pyinstxtractor and pydisasm (not Python); jadx, apktool, apkleaks, androguard and adb (not Android); webcrack, wasm2wat and wasm-objdump (no JS bundle or WASM); olevba (not Office). tshark and mitmdump were not run, because that needs a live capture while using the cloud AI. rz-diff was not run, because there is only one version to compare. x64dbg, ImHex and the GUI tools are interactive only.

## Feature inventory (evidence)
- **Tools** (PaintTools exports):
  - Drawing: Pencil, Brush, Calligraphic, AirBrush, Eraser.
  - Lines and shapes: Line, Bezier, Polygon, Rect, AutoShape.
  - Fill and picking: Flood fill, PickColor, Zoom, Text.
  - Selection: Selection, FreeFormSelection, ObjectSelect, MaskBasedSelection.
  - AI: MagicEraser, GenerativeFill and NewGenerativeFill.
  - Tool actions: Flip H/V, Rotate, Skew, Resize, InvertColor, InvertSelection.
- **Shapes** (BasePaint `ShapeFactory::Create*`): Ellipse, Rectangle, RoundedRectangle, Triangle, RightAngledTriangle, Diamond, Pentagon, Hexagon, Arrows (up, down, left, right), 4-, 5- and 6-pointed stars, RoundedRectangularCallout, OvalCallout, CloudCallout, Heart, Lightning.
- **Brushes** (UI assets): Brush, Calligraphy brush, Calligraphy pen, Airbrush, Oil, Crayon, Marker, Natural pencil, Watercolor.
- **Layers** (ProjectFile exports and UI strings): LayerStack, ImageLayer, Background color and visibility; add, duplicate, delete, hide, move up/down, merge down, copy merged.
- **Formats** (AppxManifest): avci avif bmp dib emf gif heic heif hif ico jfif jpe jpeg jpg paint png rle tif tiff webp wmf.
- **Copilot/AI** (UI strings): CoCreator (creativity slider), ImageCreator (credits), Reimagine, Generative Fill, Generative Erase, BackgroundRemoval, BackgroundBlur, GenerativeStickers, ColoringBookCreator, and a model selector (local or cloud).
- **Cloud endpoints** (AIServices.dll): `https://apsaiservices-a0fqcjc6bzbhgdcd.b02.azurefd.net/`, with these paths:
  - `paint-cocreator/image/{}`, `paint-cocreator/reimagine`, `reimagine-prompt`
  - `v1/dalle/submitImageLLM`, `v1/dalle/image/`, `v1/dalle/userstatus`
  - `v1/paint-cocreator/moderate-prompt`, `image-sign`, `edge-hash`
  - `v1/targeting/groups/Paint`
- **View and other** (UI strings): Rulers, Gridlines, Zoom, Full screen, Image properties, Print and print preview, Desktop background (fill, tile, center), From scanner or camera, Recent files.

## Evidence vs inference vs unknown
- **Evidence:** the export names, manifest, UI string keys, URLs, DiE, capa, YARA and pe-sieve outputs above.
- **Inference:**
  - The capa "keylogging", "geo" and "RC4" hits are benign library behaviour.
  - The `.onnxe` models are encrypted ONNX models used for selection, segmentation and background removal.
  - The 2 unknown injected modules come from a third-party tool.
- **Unknown:**
  - Exact request and response formats of the cloud API (no traffic was captured).
  - The contents of the `.onnxe` models.
  - The identity of the 2 VS2017 modules.
