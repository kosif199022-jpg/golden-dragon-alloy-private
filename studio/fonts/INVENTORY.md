# Font inventory — evidence-first

**Status:** references found, binary inventory incomplete. Do not assert that the owner's ~1000-font archive has been located.

| Family | Evidence | Current binary status |
|---|---|---|
| Cairo, Lalezar | `kosif-tool/.claude/skills/kosif-superpowers/references/owner-uploads-review-20261023.md`; archive `arabic-ad-fonts.zip` | Reported integrated; verify actual TTF/OTF |
| El Messiri | Same review, `proofs/_shared/fonts/ElMessiri[wght].ttf` | Reported; verify |
| Poppins | Same review, `proofs/_shared/fonts/Poppins-Regular.ttf`, `Poppins-Bold.ttf` | Reported; verify |
| KOSIF Jumuah | `kosif-tool/fonts/kosif-jumuah/` | Font project documented; verify binaries |
| Amiri, Tajawal, Reem Kufi, Aref Ruqaa, Scheherazade New, Anton, Instrument Serif | `runtime/engine/references/FONTS_REQUIRED.md` | Required names; binaries intentionally excluded from redistributed ZIP |

Use the existing `runtime/engine/tools/fonts/fonts.py` recovery logic only after checking licensing and its actual command interface. Search all accessible repositories, binary files, archives and Git LFS pointers. Never copy or distribute proprietary font binaries without rights.
