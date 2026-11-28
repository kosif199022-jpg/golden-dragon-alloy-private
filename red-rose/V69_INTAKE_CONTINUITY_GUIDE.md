# V69 supplementary intake + storyboard continuity ledger (2026-11-28)

## 1. `rose.py intake` — owner-approved sources the V66/V67 corpus does not cover
Append-only local FTS5 index at `~/.red-rose/intake-v69/intake.sqlite3`; V66/V67 are untouched.
- `intake add ARCHIVE.zip --label LABEL --origin "where it came from + sha" --approve-write`
  reads md/markdown/txt only (one nested `.zip`/`.skill` level, in memory). No extraction to disk,
  no execution, binaries/executables ignored, path-traversal entries skipped, secret-like and
  instruction-hijack chunks kept out of search. Same archive bytes or label twice is refused.
- `intake search "words" [--label L] [--limit N]`: BM25 lexical ranking, max 2 chunks per document.
- `intake inspect SHA256 [--line N --window W]`: re-hashes the archive and document before showing text.
- `intake status`: receipts per archive.
Results are **unreviewed references** (`instruction_authority: false`). Read the original, check rights,
implement independently, test, then record with `evolution`.

Indexed 2026-11-28 (sources kept in `~/.red-rose/intake-v69/sources/`):
| label | archive sha256 | docs | chunks | notes |
|---|---|---|---|---|
| kosif-video-mega-pack-2026-11-28 | f879353f…163d | 1,203 | 6,008 | 1,200 generated recipes = 40 techniques × 10 project types × 3 phases (self-declared), router, 45-repo list. `collect.py` NOT run. |
| telegram-export-2026-11-28 | c88a6178…c245 | 521 (+13 dup) | 9,606 | text-only repack of `Telegram Desktop.rar` (sha 9c4bbbe7…fee9e). Excluded: an APK (deleted unopened from the temp copy), audio SFX pack, video, HTML, 3 PDFs. 6 secret-like chunks blocked. |
| telegram-pdfs-2026-11-28 | cd960e28…1ffc | 3 | 25 | PyMuPDF text of the 3 PDFs (Animation Master System v1, TikTok Symphony prompt guide, special short-content prompt); each .md header keeps the PDF sha256. |

Already absorbed before V69 (verified by hash, not re-indexed): `skills.zip` = `shiyu-34k.zip`
(1a21b4e7…); `CLAUDE_SKILLS_COLLECTION.zip` = the same three V66 sources (hashes match V66 receipt).
Rights: third-party prompt systems and skills (incl. Hady Raie material) are for the owner's private
study; do not republish their text. Many target paid generators (Seedance/Higgsfield): adopt the
planning method only; any paid generation still needs explicit owner approval.

## 2. `rose.py continuity check STORY.json` — read-only storyboard continuity ledger
Method reviewed from `telegram-export-2026-11-28` → `Hady Raie storyboard-builder.md` (Golden Rule,
Step 3 ledger, Step 1.5 slideshow trap, pre-delivery checklist). Original implementation.
Per shot: `id, start_frame, end_frame` (whole frames, contiguous from 0), `shot_type`, `camera_move`,
`subject_motion`, optional `action_start` / `action_result`, `cut_in` (motion|match|hard|dissolve|whip)
+ `hard_cut_reason`, `state` {location, wardrobe.X, prop.X, scale.X …} and `changes` {key: reason}.
Unrestated state keys carry forward. Errors: timeline gap/overlap/duration mismatch, continuity drift
without a reason, repeated shot type in consecutive shots, static camera or no subject motion
(unless `allow_static`), dangling action, unjustified hard cut. Warnings: beat < 0.5 s, same camera
move > `max_same_camera_seconds` (default 3), unused change reason.
Example: `python -X utf8 rose.py continuity check examples/continuity_v69_example.json` → `pass`.
Structure only: it never renders and does not inspect frames; verify the actual video separately
(media-contract verify + visual review). Dua reels still follow the mandatory dua source/font gate.

Tests: `test_intake_v69.py` (7), `test_continuity_v69.py` (9).
