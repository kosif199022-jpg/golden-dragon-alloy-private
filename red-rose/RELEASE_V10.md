# 🌹 Red Rose V10 — verified incremental fusion report

Date: 2026-11-21. Scope: **knowledge descriptions and provenance**, not executable engine fusion.

## Source and destination
- Source: the owner's installed \`golden-dragon-alloy/kb/alloy.db\`, opened read-only (26,363 source units).
- Destination: private/local \`%USERPROFILE%\.red-rose\memory.sqlite3\`, table \`fused_knowledge\`.
- Migration script: \`red-rose/fuse_alloy_v10.py\`, independently runnable with Python stdlib.
- No source database, compressed body blobs, user memory, credentials, or fonts uploaded to GitHub.
- Search within the migrated table using \`fuse_alloy_v10.search(db, "query")\` or the full local V10 \`rose.py fuse-search\`.

## Device evidence
- Examined source SQLite schema and metadata; 26,363 units were present.
- First migration: 25,675 metadata units added, 688 entries excluded by policy.
- Second migration: 0 added and 0 updated (idempotent).
- Recorded private/memory entries in destination: 0 **by explicit kind/status markers**; this does not prove that all personal information has been detected in other fields.
- Independent Windows Python tests: 2 of 2 passed after fixing Windows SQLite file handle cleanup.

## Existing local V10 package (not fully uploaded to this branch)
- Full local code package extends V9 video timeline/character/camera/FFmpeg pipeline.
- 39 of 39 local tests passed. Video export verified with FFprobe separately.
- This branch currently holds the V10 importer and its tests; the full V10 video package still requires a separate code sync before calling the repository version V10-complete.

## Remaining gaps
- Reading descriptions is NOT proof of capability implementation.
- Original compressed bodies were intentionally not imported or executed; only safe metadata/summary fields were migrated.
- No complete rewriting of the previous dragons' engines, no professional character rigging, no finished 1,400-capability skill.
- Do not merge until repository implementation, packaging, licensing and CI tests are reviewed.
