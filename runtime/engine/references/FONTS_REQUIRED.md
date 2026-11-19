# Font assets are intentionally NOT bundled in this redistributed ZIP

The original user-supplied v1.2 archives contain binary font assets. Their original paths are retained in the code; for the upgraded release restore the font files **locally from your original licensed archives**, or configure your own licensed equivalents in the engine style presets. This ZIP contains no `.ttf`, `.otf`, `.woff` or `.woff2` files.

Some typography / preview / motion templates require these fonts to achieve the intended look, while other commands can work with system font fallbacks. Check local licenses before installing or publishing a video that embeds the fonts. Neither this skill nor Superpowers installs font binaries automatically.

## v10.15: `python scripts/dragon.py tool fonts fetch`

All fonts the engines read are SIL OFL 1.1 (Google Fonts families, plus the owner's own OFL derivative KOSIF Jumuah).
One tool gets them back without putting them in the ZIP:

    python scripts/dragon.py tool fonts doctor                    # present / missing per folder (exit 1 if missing)
    python scripts/dragon.py tool fonts fetch                     # plan only
    python scripts/dragon.py tool fonts fetch --yes               # copy from local folders (kosif-own/black-dragon, kosif-tool, canvas-fonts, ...)
    python scripts/dragon.py tool fonts fetch --download --yes    # + download what is still missing from github.com/google/fonts (ofl/ only)

Files go straight into the folders the engines already read (no engine change), an existing file is never overwritten,
each font must open with PIL and carry the expected family name, its licence text is placed beside it when the folder
has none, and `fonts.lock.json` in that folder records SHA-256, source path/URL and licence.

| folder | files |
|---|---|
| app/engines/cinema/assets/fonts | ArefRuqaa-Bold, Cairo-900/700/400, Amiri-Bold, ElMessiri-700, Tajawal-Black, ReemKufi-700, InstrumentSerif-Italic (.ttf) — also read by image_studio |
| app/engines/talking_head/data/fonts | Anton-Regular.ttf |
| app/engines/web_film/assets/fonts | Cairo.ttf (variable Cairo[slnt,wght]) |
| tools/styles/fonts | ArefRuqaa-Bold, Tajawal-Bold, Lalezar-Regular, ElMessiri-700, Amiri-Bold, ScheherazadeNew-Bold (.ttf) |
| tools/cartoon/fonts | Lalezar-Regular.ttf |
| app/engines/matrices/assets | KOSIFJumuah-Bold.woff2 (local only: not on Google Fonts) |

Cairo-900/700/400, ElMessiri-700, ReemKufi-700 and KOSIFJumuah-Bold are static cuts with no upstream file of that
name, so they come from local copies only.

**Packing exclusion (keep the ZIP font-free):** exclude `*.ttf`, `*.otf`, `*.woff`, `*.woff2` and `fonts.lock.json`
under the six folders above (the licence `.txt` files may stay).
