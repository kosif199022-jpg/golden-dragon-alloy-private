# Black Dragon v1990.6.0 candidate — test report (2026-11-11)

Run in a Claude Code cloud container: `PYTHONPATH=app python3 -m pytest -q app/tests --deselect app/tests/test_mod_dragon_montage.py`.

| Run | Result |
|---|---|
| New `test_v19906_project_looks.py` (4) + `test_v19905_looks.py` (6) + `test_v19905_effects.py` (10) + content | **21 passed** |
| Full suite (montage module deselected) | **729 passed, 45 failed, 1 error, 123 skipped** |

The failures were read. None comes from this release:
- Version pins to older numbers (`10.*` or `1990`, `1990.3.1`, `v1990.3`) in `test_v12`, `test_v12_integration`, `test_v199031_safety`, `test_v19903_machine`, `test_v1990_hf_free`: they failed the same way on 1990.5.0.
- `test_v12_docs`: SKILL.md over 320 lines (366 now, 356 in 1990.5.0) and two older references not named in SKILL.md; both pre-existing.
- Missing modules in this container: `librosa` (`test_phase2`), `cv2` (`test_v108_visual_forge`), `httpx` (`test_v1010_guardian`), chrome module (`test_mod_chrome`, error). Missing fonts/browser/assets: `test_mod_image_studio`, `test_mod_kosif`, `test_mod_talking_head`, `test_v1016_paint`, `test_v1016_grab`, `test_v12_styles`, `test_v12_songs`. This container had fewer Python packages than the 1990.5.0 run (39 failures there), so the counts are not comparable one to one.
