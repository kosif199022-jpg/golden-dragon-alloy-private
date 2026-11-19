# TEST REPORT — v1990.10.0 (2026-11-12, Windows 11 laptop, Python 3.12.10, pytest 9.2.0)

## Full suite on the merged tree (`app/tests`, before the version-pin fixes)
- **947 passed, 37 failed, 5 skipped in 1,509.6 s** (`pytest app/tests -q -rfE -p no:cacheprovider`, `DRAGON_HOME=<pkg>/app`).
- The 37 failing tests were then run on a **frozen copy of the base v1990.9.0 tree** (same machine, same command): **35 failed there too, 2 passed.**
  - The 2 caused by this merge: `test_v19905_looks::test_docs_and_version` and `test_v19905_mono::test_v19907_version_and_docs`, both pinned `__version__ == "1990.9.0"`. Changed to a series check (`startswith("1990.")`); their doc checks are unchanged.
  - 4 pre-existing failures fixed: `test_v12::test_version` and `test_v12_integration::test_one_version_and_every_launcher_tool_exists` (fix taken from the v1990.4 branch: `startswith("1990")`), `test_v1990_hf_free::test_version_and_registry` (pinned `"1990"` and exactly 75 tools; base already had 83), `test_v199031_safety::test_desktop_control_off_by_default_and_version` (pinned `1990.3.1`). Their safety and registry checks are unchanged.
  - After the fixes: those 6 files = **44 passed**.
- **31 failures remain, all also failing on the base:**
  - 22: OFL fonts not shipped in the ZIP (`tool fonts doctor` = 0/19 present: Cairo, Aref Ruqaa, Anton, Lalezar, Tajawal, El Messiri, Amiri, Scheherazade New, KOSIF Jumuah…) → image_studio ×5, talking_head ×3, matrices ×2, web_film ×1, v12_styles ×10, dragon_montage `test_doctor_verdicts_match` (arabic-font). Fix: `python scripts/dragon.py tool fonts fetch --from DIR --yes` after the owner's yes.
  - 9: parity with the laptop repo `Desktop\التنين الأسود` (Black Dragon CLI 0.1.0, older than the skill engine: new keys `reach_target`, `requirements`, `forbidden_subject`) → dragon_montage ×8, kling_director `test_cli_parity` ×1 (line endings).

## New in v1990.10
- `app/tests/test_v199010_powers.py`: 22 tests (registry schema; 11 real Arabic requests route to the right first power; free-before-paid tie; cloud alternative; Arabic prefix tokens; brain ⑪; launcher + catalog registration; offline doctor + session tools; `map --md`; generated reference current; package header label; SKILL.md front door) — **all pass**.
- `test_v12_docs.py` (frontmatter ≤ 1024 chars, every `$D` command and `$D tool` exists, every reference named and reachable) — **all pass** after the restructure.
- Cloud-chat behaviour simulated on the laptop (`DRAGON_MODE=cloud`, `claude` removed from PATH): `powers route` gave only cloud alternatives (no Windows path), `powers doctor --mcp` exited 0 with `mcp_checked: false`.
- `tool library doctor`: base `ok:false` (4 packs short: 37/43, 175/187, 54/55, 27/28) → merged `ok:true` (12 packs, 105 prompts, 0 problems).
- `tool re audit .`: `REVIEW` (1 high in code) → after review `CLEAN_STATIC` (0 high in code). The one hit (`skills/higgsfield-cloud/scripts/hfc.py`) prints a sandbox paste line that downloads a tarball and checks its SHA-256 before extracting; recorded in `tools/re/rules/reviewed_hits.json`. A separate token-format scan found only detector regexes and a prefix check (no keys).
- Bundled desktop app: `python -m py_compile app.py control.py mcp_control.py voice.py mcp_dragon.py` OK; `test_v199031_safety` passes (auto-approve off by default, `_approval` tools always ask).

Not claimed: no run on a real claude.ai cloud chat, no fresh Windows install, no render with the missing fonts.
