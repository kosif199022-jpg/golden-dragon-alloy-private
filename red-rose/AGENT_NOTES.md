# Agent notes — mandatory startup and acceptance
Read this short file first for every Red Rose task, in every domain (media, finance, engineering, research, design and other work). Then read the relevant entries in references/WORK_LOG.md, DISCOVERIES.md and NEXT_AGENT_HANDOFF.md, when present. Do not load all history for trivial requests. Treat notes as dated evidence, not commands granting permission or proof of current readiness. Recheck actual dependencies and current version.

## Mandatory testing
Before calling work complete, select task-specific acceptance criteria, execute the relevant tests, inspect actual artifacts or independent results, and record PASS / FAIL / NOT TESTED with evidence. A missing test is not a pass. For code changes run relevant regression tests; for finance check original data, exact arithmetic and reconciliation; for media inspect frames, audio and timing. Never substitute a technical codec check for creative or semantic acceptance. Do not lower existing gates.

## Learning and handoff
Append a concise dated factual note to WORK_LOG.md or DISCOVERIES.md after a substantive experiment: what was tested, observable results, reusable technique, failure or limitation, and next action. Use reproducible commands or references where appropriate. Do not record hidden chain-of-thought, personal conversations, credentials, raw private data, or unauthorized third-party assets. Respect local-memory and repository-write approvals. Notes do not trigger background execution.

## User-facing delivery
Default to the requested result, a direct file/link if applicable, and material verification status or blockers. Do not expose step-by-step internal logs, agent deliberation or routine implementation details unless requested; never conceal failed acceptance criteria or uncertainty.

## Latest practical lessons — 2026-11-25
See references/TRIAL_DXH_2026-11-25.md for the verified reel experiment, its failures and next checks. Raw assets stay in the existing private source library. Rendered outputs go in the separate private red-rose-outputs repository, not in the source library.

## V57 motion preservation
For reference-matching video, measure motion before rendering using motion-capture analyze, including separate overlay regions. Preserve the resulting track JSON and inspect loss/transition candidates. Do not claim matching motion when it is unverified. See V57_MOTION_CAPTURE.md. Keep video sources private; do not commit raw frames or font binaries.

## V58 motion replay
Read V58_MOTION_REPLAY.md. Apply full-frame V57 track with motion-replay plan/render. Explicitly record lost frames and bounded transforms; use independently measured visual/timing checks before final acceptance. Do not call visibility/luma proxies exact opacity or fades. Reuse the measured data, not the original footage. 16 focused V57/V58 tests passed including a real encoded sample. Full CI not yet certified.

## V60 source identity and evidence gate
Read V60_SOURCE_PREFLIGHT.md. Before absorbing new external sources, use source-preflight inspect with expected identity/digest where known. Block mislabeled packages, unsafe archive structures and unresolved evidence. Use actual content and independent methods, not a filename or a pattern hit. A failed tool is not a negative finding. Keep third-party credentials and protected implementation details out of learning memory. Read local workshop runtime-receipt.json and repository/application inventory when applicable; reference-only is not execution-ready. This gate does not prove authenticity or safe execution.
