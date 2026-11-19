# Credits

- **Trickat StickMan**, made by Trickat: the Arabic edition: SRT-based sync (`engine/timing.py`), Arabic text shaping and right-to-left layout (`engine/artext.py`), Arabic defaults and fonts, and the Trickat workflow.
- Based on **ReachMora 2D Long-Form** by ReachMora: the original story.json engine, shot library, sets, props, alignment, music and mix.
- The puppet character, night-lighting and grade code in `engine/kit.py` is adapted from the "Claude 2D Animation Long Form" skill by aivxer.
- Latin fonts: Caveat Brush and Kalam (SIL Open Font License, `fonts/OFL.txt`), Permanent Marker (Apache License 2.0, `fonts/LICENSE-Apache.txt`), from Google Fonts.
- Arabic fonts: Marhey (Bold instance), Lalezar and Aref Ruqaa Bold, all SIL Open Font License 1.1 (`fonts/OFL.txt`), from Google Fonts.
- Text shaping: HarfBuzz via uharfbuzz (Apache 2.0 / Old MIT).
- Optional English speech alignment: sherpa-onnx (Apache 2.0) with the NVIDIA Parakeet TDT 0.6B v2 model (CC-BY-4.0), downloaded only with `setup.sh --with-asr`.
- skia-python (BSD), NumPy, SciPy, soundfile, FFmpeg.
