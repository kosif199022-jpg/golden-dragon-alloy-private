# Golden Dragon × Maven Reels — private integration bridge

This adapter invokes a **separately installed, authorized** Maven Reels copy. It does not bundle or republish Maven's code.

## Licensing
The supplied `rights/MAVEN-RIGHTS.txt` allows private use and changes to a private copy, but forbids publishing/sharing Maven's code or modified copies without written permission. Therefore do **not** commit the supplied Maven ZIP or extracted code into this repository.

## Windows setup
1. Extract your licensed/private Maven archive locally.
2. Install its documented dependencies in that private folder.
3. Set `MAVEN_REELS_HOME` to the extracted `maven-reels` directory.
4. Run `python apps/golden-dragon/integrations/maven_bridge.py doctor`.
5. Run `python apps/golden-dragon/integrations/maven_bridge.py analyze reference.mp4 analysis-out`.
6. Run `python apps/golden-dragon/integrations/maven_bridge.py new my-reel`.
7. After authoring reel.html, run `python apps/golden-dragon/integrations/maven_bridge.py render my-reel/reel.html output.mp4 --voice voice.mp3`.

## Status
Bridge code only; not yet registered as a `fusion` tool in the generated application, and no end-to-end render test has passed. Next: add a forge-owned tool registration and automated smoke tests, then rebuild EXE on Windows. Do not manually edit generated `apps/golden-dragon/app`.

## Security
No shell execution or automatic remote download. User-provided paths are passed as separate process arguments. Never store API credentials in project files.
