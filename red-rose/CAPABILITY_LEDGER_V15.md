# 🌹 Red Rose V15 — tested execution ledger

This file distinguishes **tested native executable adapters** from **knowledge
references**, design requirements, tool descriptions and unavailable features.

| Native adapter | Effect | Independent test coverage | Preconditions |
|---|---|---|---|
| `knowledge.search` | read | `test_read_knowledge_search_with_evidence` | Imported safe Alloy summaries |
| `knowledge.route` | read | `test_reference_routing_is_not_execution` | Local SQLite DB |
| `knowledge.stats` | read | `test_read_knowledge_search_with_evidence` | Local SQLite DB |
| `memory.recall` | read | `test_recall_read_only_from_local_db` | Local private memory DB |
| `learning.record` | approved write | `test_evidence_linked_lesson_persists_and_is_recalled` | Successful audit ID and consent |
| `style.list` | read | `test_list_styles` | Local SQLite DB |
| `audio.analyze` | read | `test_silence_audio_analysis` | FFmpeg and local audio |
| `video.verify` | read | `test_real_video_production_verify_and_no_overwrite` | FFprobe, FFmpeg, local MP4 |
| `video.preview` | read | `test_video_preview_no_output` | Valid storyboard JSON |
| `video.produce` | approved write | `test_real_video_production_verify_and_no_overwrite` | FFmpeg, CairoSVG, bounded project |
| `character.svg` | approved write | `test_svg_real_output_and_collision` | New SVG destination |

The CLI's write approval is an **execution gate**, not a general-purpose
filesystem authorization bypass. Arbitrary shell commands or external agents
are not recognized. The `capability_execution_audit` stores **hashes** of
parameters/evidence, not raw user prompt data; verified lessons themselves
are locally private and require a separate approval.

## Original knowledge ingestion / requirements

A previous on-device import examined 26,363 source units and stored **25,675
summary/metadata entries**, excluding 688 per heuristic rules. This is
searchable documentation, not 25,675 runnable programs. The privacy filter
is heuristic and cannot prove the total absence of sensitive information in
arbitrary third-party summaries. Do not export the destination SQLite file.

The **1,400 user requirements** are not fully available here as individual
verifiable specifications, so the ledger deliberately **does not invent**
requirement IDs, a completion percentage, or implementation claims.
