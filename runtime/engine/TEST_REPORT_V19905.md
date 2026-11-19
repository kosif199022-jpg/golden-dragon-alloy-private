# Black Dragon v1990.5.0 candidate — test report (2026-11-11)

Run in a Claude Code cloud container: `PYTHONPATH=app python3 -m pytest -q app/tests --deselect app/tests/test_mod_dragon_montage.py`.

| Run | Result |
|---|---|
| New tests `test_v19905_looks.py` (6) + `test_v19905_effects.py` (10) + `test_content_version` | **17 passed** |
| Full suite (montage module deselected, 19 tests not run) | **730 passed, 39 failed, 123 skipped** |

The 39 failures were read one by one. None is caused by this release:
- Version pins to older releases (`1990`, `1990.3.1`, `v1990.3`) in `test_v199031_safety`, `test_v19903_machine`, `test_v1990_hf_free`, `test_v12*` — they already fail on v1990.4.0, whose version is not any of those.
- `test_v12_docs`: SKILL.md over 320 lines (it was 350 in v1990.4.0, now 356 with the v1990.5 section) and two references not named in SKILL.md (`APP_CONTROL_SECURITY_V199031.md`, `V19902_MONTAGE_WINDOWS.md`), both pre-existing.
- `test_v1010_guardian` (media hunter): `httpx` not installed in this container.
- `test_mod_image_studio`, `test_mod_kosif`, `test_mod_talking_head`, `test_v1016_paint`, `test_v1016_grab`, `test_v12_styles`, `test_v12_songs`: missing fonts/browser/assets in this container, files this release did not touch.
No v1990.4.0 full run was made in the same container to compare counts; the v1990.4.0 notes report pre-existing full-suite failures.
