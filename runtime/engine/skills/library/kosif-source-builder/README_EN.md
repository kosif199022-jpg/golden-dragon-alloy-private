# KOSIF Cinematic Toolkit

This ZIP contains real, runnable **KOSIF glue code**, tests, a repository index, demo storyboard and safe Git clone tooling. It is not an offline distribution of Blender, Remotion, FFmpeg, Wan model weights, or the full source of private KOSIF repositories. Those must be obtained on an authorized machine.

Quick start:
```
python kosif.py doctor
python kosif.py catalog
python kosif.py install --group own-video --execute
python kosif.py storyboard --output project/demo.json --duration 12 --shots 3
python kosif.py render --storyboard project/demo.json --output output/demo.mp4 --width 720 --height 1280
```

Git must be available for install; FFmpeg and FFprobe are required for rendering; large AI models require separate hardware, installation and download. See `docs/`.
