# Black Dragon v10.17.2 — local test report

- Source: user-provided v10.17.1 candidate and Claude/Higgsfield textual analysis; actual Katana code or raw analysis JSON was **not** supplied.
- Added standalone standard-library Reel DNA CLI, 2-second synthetic test data, repeatable unit/integration test, owned-media FFmpeg preview, and offline local library.
- Test commands: `python -m pytest -q app/tests/test_v10172_reel_dna.py app/tests/test_v10171_hf_workflows.py app/tests/test_v1015_onscreen_hf.py app/tests/test_v10161_merge.py app/tests/test_v1017_merge.py`.
- **34 tests passed** (10 Reel DNA and 24 selected compatibility tests) at 2026-11-11. This is **not** a full-suite claim.
- Measured preview: FFmpeg creates 60 frames from two owned sample images at 30fps; FFprobe frame count matches the recipe; SHA256 mismatch and output overwrite are rejected.
- Unverified: any real Katana `analysis.json` schema, remote `sandbox_exec`, actual beat alignment/cut detectors, all 338 SFX licences, XL or billing, shake/pan/punch execution, captions, GPU.
- Packaging hashes prove local integrity only, not cryptographic third-party identity.
