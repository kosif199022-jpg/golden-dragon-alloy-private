# V71 directing mind + available borrowings (2026-11-28)

## `rose.py borrow` — «الاستعارات المتاحة»
One read-only list of what Red Rose can borrow: 30 styles (`agent/style_registry_v70.json`) and 29
tools/engines/machines (`agent/tools_registry_v71.json`), each checked live (path exists / on PATH).
`--for "كلام المالك"` ranks by his words (e.g. «ماكينة قطاع تفكيك» → teardown first). Borrowing a tool means
running its own documented command after reading its doc; third-party engines need the owner's OK to run.

## `rose.py direct "<request>" --seconds S [--styles a+b+c] [--genre G]`
Director's ladder, all in whole frames:
1. Genre and intent from the owner's words: story, explainer, documentary, song, dua, ad, talking-head.
2. Hook: frame 0 already shows the hook image; it must read within 1.5 s without sound.
3. Beats per genre (story: hook → setup → escalation → pivot → payoff; documentary: cold-open → context →
   evidence → turn → verdict; …) with purpose, emotion, light and sound per beat.
4. Shot grammar: a new shot every ~2.5 s, shot size never repeats back to back, the camera always moves,
   cuts carry motion, hard cuts only for place/time jumps.
5. Cocktail: each beat gets the style whose layers fit it best (characters / places / type / maps…); ties go
   to the least-used style so the mix varies; `unused_styles` names any style no beat needed.
6. The shot list is passed through `continuity check` at once; the result is in the treatment.
7. Six critic questions to answer before rendering.
Output is a DRAFT (`draft_for_owner_review`): the owner approves, then real states and motions are filled,
continuity re-checked, a 3-second sample rendered per engine, and the final verified frame by frame.

## Style library added in V71 (8 packs, library now 24 packs)
arabic-case-file-documentary, arabic-minimal-reels (+ owner prompts in OWNER_PROMPTS.txt), archival-editorial,
talking-head-reels, faceless-shorts (6 sub-styles), growkaz-stickman (5 colour styles), saas-animation,
cartoon-audio-short (SKILL.md + new cartoon-short-kit version). Skipped: maven-gta.zip and maven-reels.zip
(byte-identical to installed packs), FigmaAutoLayoutExcercise.fig (design file, not a style).
Downloads they may ask for (need the owner's OK): case-file fetches free OFL fonts when missing;
faceless-shorts fetches the free Kokoro TTS model (~300 MB) on first voice run.
Tests: `test_direct_borrow_v71.py` (8).

## V72 additions (2026-11-28)
- Styles 30 → 34 (library 24 → 28 packs): ai-geek-2d-documentary (stick figures in 3D sets, 16:9, method doc),
  ai-geek-depth-documentary (flat-vector 2D, 16:9, method doc; its previews ask for an image generator),
  cartoon-face-history (2.5D cutouts with cartoon eyes/mouths, 9:16; its licence requires keeping the AI Geek
  start/end attribution banners), ai-geek-roblox-shorts (three.js toon Roblox-style, 9:16, kit).
  Five re-sent packs were byte-identical and skipped; billion-paper arrived twice (same hash).
- Tools 29 → 32: `skin-retexture-prompt` (recipe in agent/prompt_recipes_v72.json, needs a 2-image editor;
  paid generators need approval), and two NOT-installed candidates: `flow-mcp` (no licence, drives a Chrome
  profile signed in to Google Flow, Windows untested) and `cli-printing-press` (MIT, Go, curl|bash installer,
  some generated CLIs sniff unpublished APIs). Either is installed only on the owner's explicit OK.
