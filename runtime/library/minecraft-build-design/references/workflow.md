# Workflow, step by step

Commands assume `M="python <skill>/scripts/mcb.py"` (`python3` on macOS/Linux) and `-p <project>` (or the project
folder as working directory). Use absolute paths; quote paths with spaces.

0. **Environment + intake** - `$M doctor --brief`; ask the one round of questions ([intake.md](intake.md)); save
   stable answers with `$M config …`.
1. **Project** - `$M init <folder> --name 名称/Name --id AsciiId --source <voxy|anvil|schematic|flat|none> --lang <zh|en>
   --images <attachments>` (or omit the folder when the profile has `projects_dir`). Write `artifacts/brief.md`
   (where / data / what / size / style / deliverables / constraints, with the defaults you chose).
2. **Data** - `$M find-data` (profile + launcher folders; `--dir <folder>` to look only there); set `[site]`
   (server name or world/region folder or schematic + origin, a generous `box`); `$M site`; look at
   `artifacts/site-map.png`. Missing Voxy sections → the player never visited there.
3. **Locate** - F3 data: `$M camera set --f3 "<text>" [--image input/image1.png --fov N]`, then `$M camera ray`;
   coordinates → `$M map --box=… --mark=x,z,label`; no F3 → `camera fit` + `outline`/`ray`
   ([site-and-location.md](site-and-location.md)); "near my house" → `$M analyze` builds + waypoints. Record origin,
   orientation (`turns`) and reasons in the brief.
4. **Context & style** - `$M analyze --footprint WxD`; `$M style --box=…` for a reference build; decide the palette
   ([style.md](style.md)) and the terrain-fitting pattern ([design-guide.md](design-guide.md) §4).
5. **Design** - edit `design.py` (the template shows frame / PAL / foundation / roof / door / lights / garden). Set
   `[design] origin, turns`. `$M design` → look at `artifacts/drawings/*.png`. Iterate massing → façades →
   interior → landscape.
6. **Preview loop** - `$M export && $M verify && $M preview --shots`; inspect `artifacts/shots/` (overview, front,
   eye, cut-aways; night with `$M shots overview@0.15`) and the screenshot view if a camera exists. Fix, repeat.
7. **Verify** - `$M verify` PASS (walk targets from `F.w(...)`); fix every error in the design. Older game version?
   set `[export] target_version` before exporting ([setup.md](setup.md) §6).
8. **In-game** (optional, site builds, only if `doctor` says it is possible and the user agrees: a game window opens) -
   `$M ingame [--showcase]`; `All` must be 0 mismatches (`With non-air` too, unless the design clears terrain).
9. **Deliver** - `$M materials && $M preview && $M release`; reply in the player's language with origin, paste mode,
   results, decisions, deviations, file links; offer to copy the schematic into their `schematics` folder.
10. **Optional video** - [video.md](video.md).

Shortcut once the design is stable: `$M all [--ingame] [--no-shots]`.

Typical timings on a mid-range PC: site read 5–20 s; design < 1 s for 10k blocks; verify 2–20 s; preview 5–20 s;
shots ~1 s each after loading (GPU) or several seconds (software rendering); in-game test 2–5 min after the first
setup.
