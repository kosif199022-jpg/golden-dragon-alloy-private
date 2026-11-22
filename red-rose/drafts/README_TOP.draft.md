# Red Rose (الوردة الحمراء)

## If you are an AI agent arriving from the link

Red Rose is a private skill for Arabic video and bank-statement work. The skill folder is `red-rose/` in this repository. Do this, in order:

1. **Check for an installed copy first.** If a skill named `red-rose` is loaded, or `~/.claude/skills/red-rose/SKILL.md` exists, use that folder and go to step 4. Do not clone.
2. **No installed copy: ask one question.** A pasted link is not approval for a network clone. Ask the owner, in Arabic, exactly this: «أنزّل نسخة الوردة من الرابط؟ (فولدر red-rose بس، للقراية والتشغيل)». Only a clear yes counts. «كمل» or «تمام» are not a yes for this.
3. **After a yes, sparse-clone the folder only.** A full clone fails on Windows long paths. These three lines are the same in PowerShell 5.1 and Git Bash. They were measured earlier, not re-run since: run them one at a time.

   ```
   gh repo clone kosif199022-jpg/golden-dragon-alloy-private rr-src -- -c core.longpaths=true --depth 1 --filter=blob:none --no-checkout
   git -C rr-src sparse-checkout set --no-cone "red-rose/"
   git -C rr-src checkout main
   ```

   The working copy is `rr-src/red-rose`. For a trial, set `RED_ROSE_DB` to a file inside your work folder and `PYTHONDONTWRITEBYTECODE=1` (see `references/BOOTSTRAP.md`).
4. **Run the first command.** Replace `<skill folder>` with the folder that holds `SKILL.md`:

   ```
   python -X utf8 "<skill folder>/rose.py" start
   ```

   It is read-only and prints the absolute skill path. Use that path in every later command.

Then read `SKILL.md` in the skill folder, and use only that file to work. Use the four commands it lists: `start`, `brief`, `run`, `check`.

## Notes for the owner

- On claude.ai a pasted private link loads nothing, and the sandbox cannot reach the repository. Save `red-rose.skill` once (Customize, then Skills, then upload) and the skill works in new chats. Whether that Save step appears on your account is not measured yet.
- The link shows GitHub `main`. Work that is not pushed is not reachable from the link. Until the owner approves a push and merge, the link gives the older skill.
- To install a copy into your Claude Code profile so new chats need no link, run `rose.py install-skill --approve-write` only after the owner's explicit yes. The old copy is moved to a dated backup beside it, and nothing is deleted.

Do not read the rest of this file to use the skill. Developer notes are in `references/DEVELOPING.md`.
