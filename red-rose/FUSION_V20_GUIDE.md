# 🌹 V20 — Five-file original media fusion, not blind archive concatenation

User provided five owner-controlled ZIP files. Hashes and file counts are in SOURCE_FUSION_AUDIT_V20.json. The original engines, font files and raw archives are not in the standalone runtime or GitHub commit.

| Source ZIP | Independently implemented inside Red Rose | Not yet equivalent |
|---|---|---|
| remotion-skills | Explicit editable frame timeline and easing | Remotion renderer and React/TSX skills |
| maven-toon-skill | Original illustrated clay-style kitten motion | Full 3D cast, lighting and environment engine |
| kitten_rescue_code | Original animated kitten illustration | Rescue story, 3D animation, sound-design engine |
| Cinema_C_V31_SmartMedia_iPhone | Local H264/yuv420p/AAC faststart transcode with padding | Downloader/accounts/iPhone device testing |
| maven-map-skill | Spherical great-circle coordinates and schematic route animation | GIS basemap, satellite imagery, borders |

## Five verified native actions

- fusion.route — READ; great-circle geometry on [longitude,latitude], not real driving or flight routing.
- fusion.plan — READ; bounded original two-type storyboards with exact shot/frame durations.
- fusion.frame — READ; SVG illustrated frames, Arabic shaping via installed fonts and Pillow/libraqm where available.
- fusion.render — WRITE, explicit approval required; SVG/CairoSVG/Pillow/FFmpeg -> H264 MP4, then independent full-decode QA.
- media.iphone_export — WRITE, explicit approval required; pad-without-crop to vertical/square MP4, AVC/AAC faststart. Never overwrite.

## Commands

    pip install cairosvg Pillow
    # install ffmpeg and ffprobe on PATH
    cd red-rose
    python rose.py fusion-plan demo_fusion_v20.json --fps 12
    python rose.py fusion-render demo_fusion_v20.json new_video.mp4 --fps 12 --approve-write
    python rose.py iphone-export new_video.mp4 new_iphone.mp4 --preset iphone-vertical --approve-write
    python rose.py verify new_iphone.mp4 --width 540 --height 960
    python -W error::ResourceWarning -m unittest discover -v

## Evidence and limitations

On a local V17 standalone baseline plus V20 code, 174/174 tests passed. A real synthetic 2-second 24-frame MP4 and 540x960 phone-target transcode passed FFprobe/FFmpeg independent decode. These demos have no audio. GitHub CI on the V18-based branch must be separately verified.

No runtime calls to the five ZIP engines, no secret data, no bundled fonts. The new cat is procedural original SVG, NOT a photorealistic 3D cartoon. The map drawing is schematic, NOT true imagery or borders. Arabic text rendering depends on a font and libraqm available on the render host. Codec verification is not a physical iPhone playback test.

V19 PR #16/#17 are separate overlapping open developments; do not overwrite or merge them blindly. Implementation of all 1,400 requirements or full functional equivalence of all five archives has NOT happened.
