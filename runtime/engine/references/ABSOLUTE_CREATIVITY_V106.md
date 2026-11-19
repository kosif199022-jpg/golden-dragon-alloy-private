# Black Dragon v10.6 — Absolute Creativity integration

Source: user-uploaded `absolute-creativity.zip` (November 9, 2026). The source contained 13 files: one `SKILL.md`, nine research/reference guides, two Python scripts and a Windows-specific font index. This release includes the skill, nine guides and both scripts, with portability/safety changes, **not** the cache (which included paths from another machine). No fonts, media, proprietary snippets or AI model weights were added.

## Included reference subjects

| File | Application |
| --- | --- |
| `references/innovation-engines.md` | SCAMPER, morphological matrices, distant analogy, constraints and cliché rejection |
| `references/story-drama.md` | Hooks, dramatic beats, reversal, payoff |
| `references/cinematography.md` | Lens choice, angle, movement, light, shot list |
| `references/montage.md` | EDL, cut logic, rhythm, transitions, editing QA |
| `references/art-direction.md` | Palette, materials, coherence and visual systems |
| `references/atmosphere.md` | Light, texture, ambiance and sound intention |
| `references/fashion.md` | Styling, garments, wardrobe and visual presentation |
| `references/prompts.md` | Prompt planning for stills, film and audio; no remote AI generation |
| `references/typography.md` | Arabic/Latin pairing, kinetic type, readability and legibility |

Read only relevant guides for the task (do not dump them all into every request).

## How to use

```bash
python scripts/dragon.py tool creativity doctor
python scripts/dragon.py tool creativity spin "وثائقي قصير عن القراءة" --n 12 --seed 42 --json
python scripts/dragon.py tool creativity card --n 3 --seed 42
python scripts/dragon.py tool creativity brief --task "وثائقي قصير عن القراءة" --out creative-brief.json
# Manually complete fields and score 3 genuinely different concepts
python scripts/dragon.py tool creativity audit creative-brief.json
python scripts/dragon.py tool creativity score
python scripts/dragon.py tool creativity style-check examples/v106-style-bible.json
python scripts/dragon.py tool creativity font-doctor
python scripts/dragon.py tool creativity font-list --json
python scripts/dragon.py tool creativity font-title "الإبداع المطلق" --font /path/to/licensed/Arabic.ttf --out output/title.png
```

### What each command actually proves

- `spin`: reproducible combinations of concept ingredients (seeded deterministic PRNG), **not** a film, trained creativity model, or demonstrated uniqueness.
- `brief`: writes an incomplete template without selecting or scoring concepts. `audit` should fail until it is filled honestly.
- `audit`: enforces 3 rejected clichés, 3 distinct named concepts with different mechanisms, a single deliberate visual per concept, an identifiable scorer and a stated score rationale. The **supplied** subjective ratings must be 1–5 for originality, emotional truth, clarity, feasibility and memorability, with the winning concept meeting at least 18/25 and originality at least 4/5. The CLI never claims its own votes are human or independently validates originality.
- `style-check`: structurally validates a one-page style bible and does not allow rights-pending listed media for production. A `verified` flag is **only a user-declared field**; it is not a live rights lookup.
- `font-doctor`: checks Pillow + libraqm + fontTools availability without installing. Without libraqm, actual raster operations refuse to produce incorrectly ordered Arabic. `font-title` actually generates a PNG on a machine with an Arabic font and Pillow-raqm, blocks existing output files, and does not include a bundled font. For scanning fonts, `DRAGON_FONT_DIRS` and `--dir` allow portable locations; optional scan cache is stored under the current user's `~/.cache/black-dragon/font_lab.json`, not inside the distributed skill.

## Recommended production sequence

1. Read user's brief and inspect original media; do not invent observed shots, speech or events.
2. Open `innovation-engines.md` and the appropriate 1–3 domain references. Write down 3 clichés to reject.
3. Generate ≥12 concept seeds using `spin --n 12`, then develop three truly different concepts **manually**. Score and document the selection, preferably with Expert Council's differing viewpoints (simulated roles unless actual agents are separately invoked).
4. Write a *Style Bible*: palette, typography, camera, sound, edit rhythm, beat structure, platform safe zones, and asset-license inventory.
5. Use Media Hunter only for justified footage needs and inspect the corresponding license; pass an approved shot plan to `v10 gate` or real local rendering engines. If user requires a preview approval, stop before rendering until they approve.
6. Run the video QC gate on actual output and inspect representative frames and sound; list which tools were actually called and which methods were read only. No automatic upload, installation, remote generation, credits or publishing.

## Known limitations

- The two original scripts were supplied. Their Python behavior has been adapted and locally tested; source reference content is methodology rather than an executable expert.
- Concept rubric/thresholds are procedural guidance, not a scientific creativity benchmark or automatic verification of novelty.
- `font_lab.py` checks listed Arabic characters; this does not guarantee every glyph in arbitrary text exists. Review rendered output visually.
- Film/3D render engines, remote image generators, and expert agents are not run by this bridge. Its font raster command is the sole actual graphic-render output path.
- Bundled catalog entries describe tools available for routing; the entry count does not indicate all tools have been executed.

## Regression and provenance

`SOURCE_INTEGRITY.json` records the original ZIP SHA-256 and integration exclusions. `TEST_REPORT.md` lists actual verification. `MANIFEST_SHA256.json` and `SHA256SUMS.txt` contain byte hashes of the packaged files, not externally signed authenticity guarantees.
