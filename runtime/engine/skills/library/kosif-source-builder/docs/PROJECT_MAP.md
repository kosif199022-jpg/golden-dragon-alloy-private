# KOSIF Project Map

## KOSIF source repositories

- `kosif-tool`: motion style atlas, playbooks, KOSIF Superpowers, renders and QA.
- `kosif-studio`: pixel-by-pixel drawing with animation/video export.
- `kosif-one`: integrates KOSIF montage-motion, mimic, social, Omni and Studio subtools.
- `kosif-omni`: multimodal skills, cinema/audio, orchestration.
- `kosif-render-lab`: distributed render test bench.
- `fastify-motion-bro`: storyboard, planning, HTML/Canvas previews and rendering.

These are pointers to the owner's repositories. They are **not** included as complete copies in the ZIP.

## Locally runnable parts packaged here

- `kosif.py`: orchestrator.
- `src/kosif_studio.py`: standalone ffmpeg-based storyboard/video render module.
- `src/kosif_registry.py`: repository listing and authorized Git cloning.
- `tests/test_kosif.py`: offline unit tests.

## Source is separate from model weights

Wan and HunyuanVideo can be cloned as code, but model checkpoints need separate official downloads and substantial hardware.
