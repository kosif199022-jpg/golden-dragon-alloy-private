---
name: golden-dragon-fusion
description: Take one task in Arabic or English and produce a verified deliverable by combining analysis, production and quality checks. Accept a goal and its input files directly.
---

Work from the user's requested result. Infer the operations from the inputs and the delivery conditions. The user supplies one request and any necessary files. They do not have to identify a skill, search a catalog, select recipes or assemble a plan.

Start by reading references/working-method.md. Apply its cross-domain checks to one deliverable. Start with the intended output, source material and acceptance criteria. Read references/combined.md for the combined methods grouped by work stage. Compose across stages: use inspection findings to set constraints, pass the plan and inputs to production, pass actual production outputs to verification, and deliver only verified results. When two capabilities overlap, apply their complementary checks once. For reverse analysis, use passive inspection of documented formats, metadata, dependencies and provenance. Treat references as knowledge, partial capabilities as limited, and missing prerequisites as unavailable. Resolve installed execution details with the project's dragon_fusion.py show command. Preserve applicable permissions and costs. Distinguish a plan from an executed output.

Without the bundled archive, the same operations run from this skill directory: for a requested 1080x1920 vertical MP4 from a local video, run python scripts/render_vertical.py INPUT NEW_OUTPUT.mp4 from this skill directory. It preserves the complete frame with padding and verifies the exported stream. Use python scripts/fusion.py inspect-windows FILE for read-only Windows binary identification, section inventory and SHA-256. Use python scripts/fusion.py vertical-video INPUT OUTPUT for the verified video workflow. For a request involving vertical conversion, Windows file inspection, or both, pass the full request and its attached file paths to scripts/request.py in one call. Supply --output for video. Report only the completed fields in its JSON; handle any additional requested work separately.

For a task, the bundled application can supply a unified quality brief directly: python golden_dragon.pyz --method "TASK". Use these checks to guide work. In execution mode, verified_properties reports observed measurements while review_checks lists further checks to consider. The policy is embedded in the archive and requires no runtime catalog lookup.

Keep one working record for the entire task: the supplied inputs, requested changes, output format, constraints, intermediate results and acceptance evidence. Start with the output and determine what information it depends on. Inspect each input once. Carry its stable identifiers, units, language, timing and provenance through every transformation. When an intermediate result changes, repeat the checks that depend on it.

For a data-driven visual, reconcile records and freeze the checked figures before designing the graphic. For narrated media, derive the timeline from the audio, preserve character or product references across shots, align captions with the actual speech, and inspect readability in the exported frame. For a mechanism, establish the relation between parts and motion before camera animation. For a program or package, identify the format and provenance using read-only inspection and report observed fields. For software changes, test the normal entry point with a representative input and inspect the delivered output.

Execute supported local file requests through the single bundled application, from this directory:

    python golden_dragon.pyz "full request" INPUT [INPUT ...] [--output NEW_OUTPUT.mp4]

It accepts a vertical-video conversion, Windows binary inspection, both in one request, or an inventory CSV converted into a verified vertical summary. For other tasks, use the host assistant's available tools directly within the same working record. Check additional requirements independently; the local program returning successfully certifies only its reported operations. When a required capability is unavailable, identify the unfinished operation in the response.

Deliver the requested artifact and its observed verification. For a video, verify dimensions, frame rate, duration and relevant content; for a reconciliation, check row identity and totals; for a package, exercise a clean copy. Report the result in the user's language.

Runtime prerequisites are Python 3.11+, pefile for Windows inspection, Pillow 10.1+ for inventory cards, and FFmpeg and FFprobe for media. The output filesystem must support hard links. The Python application can be copied independently of the source tree. The catalog and coverage files are development evidence and are optional for using this skill.

Convert a numbered UTF-8 SRT subtitle file by requesting WebVTT and supplying a new .vtt output. The bundled parser comes from engine/skills/library/ai-motion-graphics/scripts/srt_words.py. For local source analysis, scripts/codebook.py REPOSITORY OUTPUT.html builds an offline navigable book of capability-to-file links, imports, definitions and duplicated function bodies.

For captioned edits, use the final edit timeline, split cues at cuts, and leave silent gaps empty. For Arabic, shape complete lines and check joined letters and numbers on the exported picture. Reserve caption space before placing animated titles. Check overlapping elements, an early and late cue, a silent interval, duration and audio. These decisions are built into the standalone --method response.
