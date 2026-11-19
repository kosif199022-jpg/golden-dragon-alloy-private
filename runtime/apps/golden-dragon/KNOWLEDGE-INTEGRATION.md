# Golden Dragon: Knowledge Runtime Integration

The Windows desktop app now includes a local, read-only Golden Dragon knowledge bridge.

## What is integrated
- knowledge/golden-dragon-runtime.zip: portable verified data bundle, around 3.8 MB
- App tool named knowledge: search and status only, with reference source paths
- Arabic UI button to open a searchable knowledge panel via pywebview
- Runtime Python module: search, status, integrity verification, SHA-256, JSON and CSV inspection
- Safe SQLite cache under the user's APPDATA/GoldenDragon/knowledge folder
- Windows PyInstaller build includes the bundle and both bridge modules

Read-only search never executes instructions from source skills. Retrieved text is
untrusted reference data. JSON, CSV and SHA-256 inspection are currently available
from the Python runtime but are not exposed to the AI model tool.

## Permanent integration
- forge/gd_patches/gd_knowledge.py patches app, UI, build
- forge/overlay/golden_knowledge_bridge.py implements the safe integration
- forge/overlay/knowledge_widget.html holds the searchable UI widget
- forge/make_golden_dragon.py re-applies the patch on future regeneration
- forge/integrate_existing_app.py integrates a previously generated app

The first integration used a safe direct patch with local backups under
forge/data/knowledge-app-integration-backup. After reconciling the upstream
main branch, the authentic analysis/thinking_toolkit.json became available.
The full Golden Dragon generator has now run successfully, producing the
committed app sources from the White Bird, Golden Bird, Anatomy, MarkItDown,
and knowledge patches together. The generated file stamp includes an
explicit knowledge_integration entry, and its integrity guard passes.

To regenerate this app from authentic dependencies:

    python -X utf8 apps/golden-dragon/forge/make_golden_dragon.py

The app in this repository is source/build output. Rebuilding and installing
the desktop executable is a separate, user-initiated step.

## Tests
From the repository root, run:

    python -m unittest discover -s apps/golden-dragon/tests -q
    python apps/golden-dragon/forge/package_runtime.py verify apps/golden-dragon/knowledge/golden-dragon-runtime.zip

The knowledge database includes 16,315 active canonical records, 1,914 quality
review records and 2 conflict review records. One formatting-only equivalence
was fused without losing original variants. All 16,316 original active entries
remain recoverable; 532 similarity candidates still require review.

This is NOT complete semantic skill fusion or arbitrary autonomous computer
control. The installed Windows executable was NOT rebuilt or deployed as part
of this repository integration.
