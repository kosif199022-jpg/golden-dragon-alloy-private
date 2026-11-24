# Red Rose V47 — VN prayer project analysis

## Source status
The owner supplied eleven VN files, seven Wednesday, two Monday, two Sunday. Attachment metadata confirms the sizes; one 4,714,685-byte sample was identified as application/zip. Raw archive analysis could not run in this session; none of the actual timelines, fonts or effects have been measured. No private media or project bodies are committed.

## Run on the owner PC
```bash
python vn_dua_v47.py "PATH_TO_VN_FOLDER" --sha256
python rose.py vn-dua-analyze "PATH_TO_VN_FOLDER" --sha256
python -m unittest test_vn_dua_v47
```
The report lists source hashes when requested, media types, JSON/plist metadata field candidates, raw numeric values and explicit-unit timing summaries. Only metadata is decompressed, with bounded per-file and total read budgets. Unsupported formats are reported, not fabricated. This is a schema-discovery step, not an end-to-end VN renderer or a confirmed style profile.

## Style promotion gate
1. Inspect reports and map actual project track/clip types and timebase; do not treat candidate fields as measured shots.
2. Obtain one exported reference per style and verify cut timings, exact Arabic text, font identity, animation curves, audio mix, first frame and color.
3. Separate days and styles; dedupe full source hashes; record sample counts and medians with source traceability.
4. Add a native preset only after verification, compare output on a held-out reference, and retain existing no-black-first-frame, exact wording and audio QA gates.
5. Existing Red Rose dua-reel renderer remains unchanged until mapped schema and output fidelity are validated.
