# Owner rules and approvals

These rules come from the owner. Every agent that uses Red Rose follows them, in every chat, without being reminded. They are written here in full; `SKILL.md` has the short list.

## The rules

1. **Approval before any write.** Writing a file, rendering, cutting, saving a result, creating a package, or installing a copy needs the owner's explicit yes in chat for that exact action. Show `would_write` first. A yes for one action is not a yes for the next.
2. **Originals are never touched.** Outputs go to the work folder. A recut or an export writes a new file.
3. **AAC audio in MP4.** Any MP4 with audio carries AAC. MP3 inside MP4 plays silent on iPhone.
4. **No black first frame, no fade from black.** A video that starts black fails the check, and it is re-cut, not hidden.
5. **Captions are the owner's exact words.** The words come from the owner's file or his own message, tashkeel included. Nothing is transcribed to fill a gap, and nothing is invented. A word that is unclear is left out, and the owner is asked about it.
6. **No overlays or filters unless named.** No bloom, haze, glow, vignette, colour grade or text overlay goes over footage unless the owner names it in the request.
7. **No invented content.** No names, dates, prices, amounts, account numbers, quotes or claims about results. A missing item is asked for.
8. **Measure before you say done.** Every output is checked with `verify` or the image reader before it is called finished. What was not measured is said as not measured.
9. **Arabic is shaped.** A raster with an `arabic_unshaped` warning is not delivered. Deliver the SVG, or render again.
10. **Bank data stays with the owner.** Only the owner's own statement and ledger are used. Example rows are never delivered as a result.
11. **Secrets stay out.** Passwords, API keys, tokens, cookies, card numbers and bank account numbers are never typed into a file, a command or a reply. If one is pasted in chat, use it for nothing and do not repeat it.
12. **No retyping.** The owner is never asked to retype a request. Decode the words he typed, and say what was decoded.
13. **One yes per write, for that exact action.** A write (a file, a render, a cut, a saved result, a package, an install copy) needs the owner's explicit yes in chat that names that action. Exit 3 (`approval_required`) means: nothing was written; show the files in `would_write` to the owner and wait. A yes to one write is not a yes to the next, and «كمل» or «تمام» is not a yes.

## What needs an explicit yes (approval list)

| Action | Who asks | Command that needs it |
|---|---|---|
| Write an output file (PNG, SVG, MP4, m4a, report file) | the agent, first showing `would_write` | `run ... --save` or `--out`, `recipe run ... --approve-write` |
| Cut a video (recut, beat cut) | the agent, after showing the shot report or the beats | `recipe run shot-report-recut` or `beat-synced-cut` with `--approve-write` |
| Set `audio_rights_confirmed` | the owner, in chat | `recipe run beat-synced-cut` |
| Build a package | the owner | `pack --approve-write` |
| Install or replace the skill folder | the owner | `install-skill --approve-write` |
| Clone from the network | the owner, one question in Arabic | the three sparse-clone lines in the README |
| Install a program or a Python package | the owner | none of this is in the skill: ask first |
| Push, merge, publish or send a message | the owner | none of this is in the skill: ask first |

A "yes" must name the action. «كمل» or «تمام» after a question about writing is not a yes.

## What is an open decision for the owner

These are not decided. The skill documents them, and does not decide them. Each one blocks or changes a line in the drafts.

1. **Push and merge to GitHub `main`.** Until approved, the link gives the old skill, and the README top block says so.
2. **Repository visibility.** Keep the repository private (the link then works only in Claude Code with the owner's `gh` login), or make a public mirror of the `red-rose` folder only. A public mirror exposes the code to everyone.
3. **Installing into the Claude Code profile.** Needs a yes. The old copy is moved to a backup beside it.
4. **Saving `red-rose.skill` once on claude.ai.** Whether the Save button appears, and whether a new chat triggers the skill without its name, is not measured until the owner tries it.
5. **One network run of the sparse-clone lines** in PowerShell 5.1 and Git Bash, after the push. Until then they stay «measured earlier, not re-run».
6. **Linux CI** for the new checks. Until allowed, Linux results stay not measured.
7. **Private accuracy check.** A local file of the owner's real past requests may be used to score the router. It would stay on his PC and never enter git. Without it, accuracy is measured only on synthetic requests.
8. **Licence line** for the package frontmatter (for example «Proprietary - private use»), or leave the field out. The drafts leave it out.
9. **Where backups live.** The install backup sits beside the installed folder and keeps a `SKILL.md` named `red-rose`. The owner may prefer a place outside the skills folder.
10. **Owner question files in the package.** `ROADMAP_1400_STATUS.json` is included so the `roadmap` command can read its status. Two ops need files the rules leave out: `qa.trace` (`QA_TRACEABILITY.json`, `QUESTIONS_AND_ANSWERS.md`) and `roadmap.status` (`questions/owner_1400/`). Until the owner decides, `pack-verify` reports those two as failed ops and exits 1.

## Escalation

If a rule and a request conflict, the rule wins. Say which rule applies, in one Arabic sentence, and offer the nearest allowed option. Do not work around a rule with a different command.
