# Black Dragon v10.17.1 Candidate — Higgsfield Workflow Catalog Test Report

**2026-11-11.** Built as additive metadata integration from uploaded `black-dragon-v10.17.0.zip` and user-supplied Claude audit; original ZIP not overwritten.

- New report-derived 14-entry catalog: 13 distinct workflow implementations, as `microdrama-ads` aliases `drama-ads`.
- Read-only CLI: `tool hf workflows`, `tool hf workflow NAME`, `tool hf route TASK`.
- Historical 2026-11-10 XL 4 CPU / 16 GB record retained; 2026-11-11 Standard ~2 CPU / 8 GiB; XL not remeasured on 11 November.
- Credit policy: lack of historical debit does not guarantee no charge. `media_import_url` now unknown cost. No API or HF session invoked during this build.
- **17 focused local tests passed** (new metadata tests plus previous HF/merge regression tests), run on candidate with `pytest -q app/tests/test_v10171_hf_workflows.py app/tests/test_v1015_onscreen_hf.py app/tests/test_v10161_merge.py`.
- **Not validated:** actual Higgsfield workflow scripts, prices for XL, GPU on XL, real media upload, live remote generation, paid feature invocation. Test suite as a whole was not run.
- Package SHA256 manifest is local file-integrity checking, not a third-party cryptographic signature.
